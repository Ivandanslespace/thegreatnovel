"""Thin orchestration for the local playable Campaign/Story loop."""

from __future__ import annotations

import os
import re
import stat
import hashlib
from pathlib import Path
from typing import Any, Callable, Sequence

from ..campaign import (
    CampaignError,
    choose_campaign,
    create_campaign,
    next_campaign,
    status_campaign,
    stop_campaign,
    verify_campaign,
)
from ..core.hashing import canonical_json
from ..story import (
    StoryError,
    commit_story,
    export_story,
    init_story,
    prepare_story,
    status_story,
    verify_story,
)
from .common import (
    MAX_PLAYER_OPTION_DIGITS,
    PlayError,
    SUPPORTED_LOCALES,
    canonical_document,
    ensure_new_workspace,
    lexical_absolute,
    read_external_json,
    require_workspace,
    terminal_safe_text,
    validate_json_value,
    workspace_children,
)
from .narrator_process import DEFAULT_NARRATOR_TIMEOUT, run_narrator, validate_timeout


DEFAULT_VOICE_ID = "cablecar_survival"
_POSITIVE_INPUT = re.compile(r"[1-9][0-9]*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_STABLE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_TURN_ID = re.compile(r"turn-([0-9]{6,})\Z")
_CHOICE_FIELDS = ("choice_id", "action_type", "params", "duration_minutes", "stamina_cost")
_SESSION_FIELDS = {
    "schema_version",
    "session_id",
    "campaign_id",
    "actor_id",
    "max_decisions",
    "accepted_decisions",
    "recorded_decision_count",
    "status",
    "stop_reason",
    "current_event_seq",
    "current_state_decision_seq",
    "current_state_hash",
    "current_request_fingerprint",
}
_CAMPAIGN_MANIFEST_FIELDS = {
    "schema_version",
    "campaign_format_id",
    "campaign_id",
    "worldpack_hash",
    "source_initial_state_hash",
    "world_bundle_manifest_hash",
    "player_projection_hash",
    "projection_bundle_manifest_hash",
    "initial_request_fingerprint",
    "initial_presentation_hash",
    "session_id",
    "actor_id",
    "max_decisions",
    "initial_session_state_hash",
}
_STORY_MANIFEST_FIELDS = {
    "schema_version",
    "story_format_id",
    "story_id",
    "campaign_id",
    "campaign_manifest_hash",
    "worldpack_hash",
    "source_initial_state_hash",
    "player_projection_hash",
    "session_id",
    "initial_narration_locale",
    "initial_voice_id",
}
_SESSION_STATUSES = {"AWAITING_DECISION", "STOPPED", "MAX_DECISIONS", "NO_LEGAL_ACTIONS"}
_TERMINAL_STATUSES = {"STOPPED", "MAX_DECISIONS", "NO_LEGAL_ACTIONS"}
_NOVEL_STATUSES = {"ABSENT", "CURRENT_SNAPSHOT", "HISTORICAL_SNAPSHOT", "CURRENT_FINAL"}
_SHARED_SESSION_FIELDS = (
    "session_id",
    "campaign_id",
    "actor_id",
    "max_decisions",
    "accepted_decisions",
    "recorded_decision_count",
    "status",
    "stop_reason",
    "current_event_seq",
    "current_state_decision_seq",
    "current_state_hash",
    "current_request_fingerprint",
)
_RESPONSE_ORIGIN_STORY_CODES = {
    "NARRATION_RESPONSE_INVALID",
    "NARRATION_REQUEST_NOT_FOUND",
}
InputFunction = Callable[[], str]
OutputFunction = Callable[[str], None]


def _integrity(message: str) -> PlayError:
    return PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", message)


def _invalid(message: str) -> PlayError:
    return PlayError("INVALID_PLAY_INPUT", message)


def _strict_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise _integrity(f"{field} must be a boolean")
    return value


def _strict_int(value: Any, field: str, *, nonnegative: bool = False, positive: bool = False) -> int:
    if type(value) is not int:
        raise _integrity(f"{field} must be an integer")
    if nonnegative and value < 0:
        raise _integrity(f"{field} must be non-negative")
    if positive and value <= 0:
        raise _integrity(f"{field} must be positive")
    return value


def _strict_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise _integrity(f"{field} must be a lowercase SHA-256")
    return value


def _strict_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or _STABLE_ID.fullmatch(value) is None:
        raise _integrity(f"{field} is invalid")
    return value


def _strict_turn_id(value: Any, field: str = "turn_id") -> str:
    if not isinstance(value, str):
        raise _integrity(f"{field} is invalid")
    match = _TURN_ID.fullmatch(value)
    if match is None:
        raise _integrity(f"{field} is invalid")
    number = int(match.group(1))
    if number <= 0 or value != f"turn-{number:06d}":
        raise _integrity(f"{field} is not canonical")
    return value


def _canonical_equal(left: Any, right: Any) -> bool:
    try:
        return type(left) is type(right) and canonical_document(left) == canonical_document(right)
    except Exception:
        return False


def _map_boundary_error(error: Exception, *, operation: str, boundary: str = "story") -> PlayError:
    if isinstance(error, PlayError):
        return error
    if isinstance(error, CampaignError):
        return PlayError("PLAY_CAMPAIGN_FAILED", f"Campaign {operation} failed", cause_code=error.code)
    if isinstance(error, StoryError):
        return PlayError("PLAY_STORY_FAILED", f"Story {operation} failed", cause_code=error.code)
    if boundary == "campaign":
        return PlayError("PLAY_CAMPAIGN_FAILED", f"Campaign {operation} failed")
    if boundary == "narrator":
        return PlayError("PLAY_NARRATOR_FAILED", f"Narrator {operation} failed")
    return PlayError("PLAY_STORY_FAILED", f"Story {operation} failed")


def _present_directory(path: Path) -> bool:
    try:
        value = os.lstat(path)
        reparse = bool(getattr(value, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400))
        return stat.S_ISDIR(value.st_mode) and not stat.S_ISLNK(value.st_mode) and not reparse
    except (FileNotFoundError, OSError):
        return False


def _validate_session_summary(session: Any, *, label: str = "session") -> dict[str, Any]:
    if not isinstance(session, dict) or set(session) != _SESSION_FIELDS:
        raise _integrity(f"{label} has an invalid field set")
    _strict_int(session["schema_version"], f"{label}.schema_version", positive=True)
    _strict_id(session["session_id"], f"{label}.session_id")
    _strict_id(session["campaign_id"], f"{label}.campaign_id")
    _strict_id(session["actor_id"], f"{label}.actor_id")
    max_decisions = _strict_int(session["max_decisions"], f"{label}.max_decisions", positive=True)
    accepted = _strict_int(session["accepted_decisions"], f"{label}.accepted_decisions", nonnegative=True)
    recorded = _strict_int(session["recorded_decision_count"], f"{label}.recorded_decision_count", nonnegative=True)
    _strict_int(session["current_event_seq"], f"{label}.current_event_seq", nonnegative=True)
    _strict_int(session["current_state_decision_seq"], f"{label}.current_state_decision_seq", nonnegative=True)
    _strict_sha(session["current_state_hash"], f"{label}.current_state_hash")
    status = session["status"]
    if not isinstance(status, str) or status not in _SESSION_STATUSES:
        raise _integrity(f"{label}.status is unsupported")
    expected_stop_reason = {
        "AWAITING_DECISION": None,
        "STOPPED": "EXPLICIT_STOP",
        "MAX_DECISIONS": "MAX_DECISIONS",
        "NO_LEGAL_ACTIONS": "NO_LEGAL_ACTIONS",
    }[status]
    if session["stop_reason"] != expected_stop_reason:
        raise _integrity(f"{label}.status and stop_reason disagree")
    current_fingerprint = session["current_request_fingerprint"]
    if current_fingerprint is not None:
        _strict_sha(current_fingerprint, f"{label}.current_request_fingerprint")
    if accepted > max_decisions or recorded < accepted:
        raise _integrity(f"{label} decision counts are invalid")
    if status == "AWAITING_DECISION" and current_fingerprint is None:
        raise _integrity(f"{label}.current_request_fingerprint is required")
    if status in _TERMINAL_STATUSES and current_fingerprint is not None:
        raise _integrity(f"{label}.terminal session has a request fingerprint")
    return session


def _validate_manifest(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _integrity(f"{label} is invalid")
    expected_fields = _CAMPAIGN_MANIFEST_FIELDS if label == "campaign" else _STORY_MANIFEST_FIELDS
    if set(value) != expected_fields:
        raise _integrity(f"{label} has an invalid field set")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise _integrity(f"{label}.schema_version is invalid")
    expected_format = "phase9b2b-campaign-v1" if label == "campaign" else "phase9c-story-v1"
    if value["campaign_format_id" if label == "campaign" else "story_format_id"] != expected_format:
        raise _integrity(f"{label}.format_id is invalid")
    for field in ("campaign_id", "session_id", "worldpack_hash", "source_initial_state_hash", "player_projection_hash"):
        if field.endswith("_hash"):
            _strict_sha(value.get(field), f"{label}.{field}")
        else:
            _strict_id(value.get(field), f"{label}.{field}")
    if value["campaign_id"] != value["session_id"]:
        raise _integrity(f"{label} session binding is invalid")
    if label == "campaign":
        _strict_sha(value.get("initial_request_fingerprint"), f"{label}.initial_request_fingerprint")
        _strict_sha(value.get("world_bundle_manifest_hash"), f"{label}.world_bundle_manifest_hash")
        _strict_sha(value.get("projection_bundle_manifest_hash"), f"{label}.projection_bundle_manifest_hash")
        _strict_sha(value.get("initial_presentation_hash"), f"{label}.initial_presentation_hash")
        _strict_sha(value.get("initial_session_state_hash"), f"{label}.initial_session_state_hash")
        _strict_id(value.get("actor_id"), f"{label}.actor_id")
        _strict_int(value.get("max_decisions"), f"{label}.max_decisions", positive=True)
    else:
        _strict_id(value.get("story_id"), f"{label}.story_id")
        if value.get("initial_narration_locale") not in SUPPORTED_LOCALES:
            raise _integrity(f"{label}.initial_narration_locale is invalid")
        _strict_id(value.get("initial_voice_id"), f"{label}.initial_voice_id")
        _strict_sha(value.get("campaign_manifest_hash"), f"{label}.campaign_manifest_hash")
    return value


def _validate_choice(choice: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(choice, dict):
        raise _integrity(f"{label} is invalid")
    for field in _CHOICE_FIELDS:
        if field not in choice:
            raise _integrity(f"{label}.{field} is missing")
    choice_id = choice["choice_id"]
    action_type = choice["action_type"]
    if not isinstance(choice_id, str) or not choice_id or not isinstance(action_type, str) or not action_type:
        raise _integrity(f"{label} identity is invalid")
    params = choice["params"]
    if not isinstance(params, dict):
        raise _integrity(f"{label}.params is invalid")
    try:
        validate_json_value(params, path=f"{label}.params")
    except Exception as exc:
        raise _integrity(f"{label}.params is not canonical JSON") from exc
    duration = choice["duration_minutes"]
    if duration is not None and type(duration) is not int:
        raise _integrity(f"{label}.duration_minutes is invalid")
    if type(choice["stamina_cost"]) is not int or choice["stamina_cost"] < 0:
        raise _integrity(f"{label}.stamina_cost is invalid")
    return choice


def _validate_request_pair(campaign_value: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(campaign_value, dict):
        raise _integrity("Campaign result is invalid")
    session = campaign_value.get("session")
    if session is not None:
        session = _validate_session_summary(session)
    if "canonical_request" not in campaign_value or "player_presentation" not in campaign_value:
        raise _integrity("Campaign request/presentation fields are missing")
    request = campaign_value["canonical_request"]
    presentation = campaign_value["player_presentation"]
    if (request is None) != (presentation is None):
        raise _integrity("Campaign request and presentation are not paired")
    if request is None:
        if session is not None and session["status"] == "AWAITING_DECISION":
            raise _integrity("AWAITING_DECISION has no request")
        if session is not None and session["status"] not in _TERMINAL_STATUSES:
            raise _integrity("Campaign status is inconsistent with a terminal request")
        return None, None
    if not isinstance(request, dict) or not isinstance(presentation, dict):
        raise _integrity("Campaign request and presentation are invalid")
    if session is not None and session["status"] != "AWAITING_DECISION":
        raise _integrity("terminal Campaign has a request")
    request_fingerprint = request.get("request_fingerprint")
    presentation_fingerprint = presentation.get("request_fingerprint")
    _strict_sha(request_fingerprint, "canonical_request.request_fingerprint")
    _strict_sha(presentation_fingerprint, "player_presentation.request_fingerprint")
    if request_fingerprint != presentation_fingerprint:
        raise _integrity("Campaign request and presentation fingerprints differ")
    if session is not None and session["current_request_fingerprint"] != request_fingerprint:
        raise _integrity("Campaign session fingerprint differs from request")
    canonical_choices = request.get("choices")
    presented_choices = presentation.get("choices")
    if not isinstance(canonical_choices, list) or not canonical_choices:
        raise _integrity("canonical request choices must be a non-empty list")
    if not isinstance(presented_choices, list) or not presented_choices:
        raise _integrity("player presentation choices must be a non-empty list")
    if len(canonical_choices) != len(presented_choices):
        raise _integrity("Campaign choice counts differ")
    canonical_ids: set[str] = set()
    presented_ids: set[str] = set()
    for index, (canonical_choice, presented_choice) in enumerate(zip(canonical_choices, presented_choices), start=1):
        canonical_choice = _validate_choice(canonical_choice, label=f"canonical choice {index}")
        presented_choice = _validate_choice(presented_choice, label=f"presented choice {index}")
        if canonical_choice["choice_id"] in canonical_ids or presented_choice["choice_id"] in presented_ids:
            raise _integrity("Campaign choice IDs are not unique")
        canonical_ids.add(canonical_choice["choice_id"])
        presented_ids.add(presented_choice["choice_id"])
        if not all(_canonical_equal(canonical_choice[field], presented_choice[field]) for field in _CHOICE_FIELDS):
            raise _integrity("Campaign choice authority differs from presentation")
    if canonical_ids != presented_ids:
        raise _integrity("Campaign choice IDs differ")
    return request, presentation


def _validate_campaign_result(campaign: Any, *, require_verification: bool = False) -> dict[str, Any]:
    if not isinstance(campaign, dict) or campaign.get("ok") is not True:
        raise _integrity("Campaign result is invalid")
    _validate_manifest(campaign.get("campaign"), label="campaign")
    _validate_session_summary(campaign.get("session"), label="campaign.session")
    _validate_request_pair(campaign)
    if require_verification:
        verification = campaign.get("verification")
        if not isinstance(verification, dict) or verification.get("valid") is not True:
            raise _integrity("Campaign verification proof is incomplete")
    return campaign


def _validate_story_status(story: Any) -> dict[str, Any]:
    if not isinstance(story, dict) or story.get("ok") is not True:
        raise _integrity("Story result is invalid")
    required = {
        "story",
        "campaign_session",
        "session",
        "accepted_decisions",
        "recorded_decision_count",
        "request_count",
        "committed_turn_count",
        "committed_prefix",
        "pending_turn_id",
        "missing_request_turn_ids",
        "next_preparable_turn_id",
        "novel_status",
        "export_readiness",
        "phase_9c2_export_ready",
        "missing_narration_work",
    }
    if not required.issubset(story):
        raise _integrity("Story status fields are incomplete")
    manifest = story["story"]
    _validate_manifest(manifest, label="story")
    if manifest["campaign_id"] != manifest["session_id"]:
        raise _integrity("Story session binding is invalid")
    campaign_session = _validate_session_summary(story["campaign_session"], label="story.campaign_session")
    session = _validate_session_summary(story["session"], label="story.session")
    if campaign_session != session:
        raise _integrity("Story session summaries differ")
    for field in ("accepted_decisions", "recorded_decision_count", "request_count", "committed_turn_count", "committed_prefix"):
        _strict_int(story[field], f"story.{field}", nonnegative=True)
    accepted = story["accepted_decisions"]
    if accepted != session["accepted_decisions"] or story["recorded_decision_count"] != session["recorded_decision_count"]:
        raise _integrity("Story progress counters do not match its Session summary")
    request_count = story["request_count"]
    committed = story["committed_turn_count"]
    if committed != story["committed_prefix"] or committed > request_count or request_count > accepted:
        raise _integrity("Story progress counters are inconsistent")
    pending = story["pending_turn_id"]
    if pending is not None:
        _strict_turn_id(pending, "story.pending_turn_id")
        if request_count != committed + 1 or pending != f"turn-{request_count:06d}":
            raise _integrity("Story pending request is inconsistent")
    missing = story["missing_request_turn_ids"]
    if not isinstance(missing, list):
        raise _integrity("Story missing request list is invalid")
    expected_missing = [f"turn-{number:06d}" for number in range(request_count + 1, accepted + 1)]
    if missing != expected_missing:
        raise _integrity("Story missing request list is inconsistent")
    next_preparable = story["next_preparable_turn_id"]
    if next_preparable is not None:
        _strict_turn_id(next_preparable, "story.next_preparable_turn_id")
        expected_next = f"turn-{request_count + 1:06d}"
        if pending is not None or request_count >= accepted or next_preparable != expected_next:
            raise _integrity("Story next preparable turn is inconsistent")
    readiness = story["export_readiness"]
    if not isinstance(readiness, dict) or set(readiness) != {"snapshot_exportable_through", "current_snapshot_ready", "final_ready"}:
        raise _integrity("Story export readiness is invalid")
    _strict_int(readiness["snapshot_exportable_through"], "story.snapshot_exportable_through", nonnegative=True)
    if readiness["snapshot_exportable_through"] != committed:
        raise _integrity("Story snapshot readiness is inconsistent")
    current_ready = _strict_bool(readiness["current_snapshot_ready"], "story.current_snapshot_ready")
    final_ready = _strict_bool(readiness["final_ready"], "story.final_ready")
    expected_current = committed == accepted
    if current_ready != expected_current or final_ready != (current_ready and session["status"] in _TERMINAL_STATUSES and pending is None and not missing):
        raise _integrity("Story export readiness flags are inconsistent")
    if story["novel_status"] not in _NOVEL_STATUSES or not isinstance(story["novel_status"], str) or not story["novel_status"]:
        raise _integrity("Story novel status is invalid")
    missing_work = _strict_bool(story["missing_narration_work"], "story.missing_narration_work")
    if missing_work != (pending is not None or bool(missing)):
        raise _integrity("Story missing narration flag is inconsistent")
    export_ready = _strict_bool(story["phase_9c2_export_ready"], "story.phase_9c2_export_ready")
    if export_ready != (current_ready or final_ready):
        raise _integrity("Story export-ready flag is inconsistent")
    return story


def _cross_check(campaign: dict[str, Any], story: dict[str, Any]) -> None:
    campaign_manifest = _validate_manifest(campaign.get("campaign"), label="campaign")
    campaign_session = _validate_session_summary(campaign.get("session"), label="campaign.session")
    story = _validate_story_status(story)
    for field in _SHARED_SESSION_FIELDS:
        if campaign_session[field] != story["campaign_session"][field] or campaign_session[field] != story["session"][field]:
            raise _integrity(f"Campaign and Story session field {field} differs")
    story_manifest = story["story"]
    for story_field, campaign_field in (
        ("campaign_id", "campaign_id"),
        ("session_id", "session_id"),
        ("campaign_manifest_hash", "_manifest_hash"),
        ("worldpack_hash", "worldpack_hash"),
        ("source_initial_state_hash", "source_initial_state_hash"),
        ("player_projection_hash", "player_projection_hash"),
    ):
        expected = (
            hashlib.sha256(canonical_document(campaign_manifest)).hexdigest()
            if campaign_field == "_manifest_hash"
            else campaign_manifest[campaign_field]
        )
        if story_manifest[story_field] != expected:
            raise _integrity(f"Story and Campaign binding field {story_field} differs")


def _render_presentation(presentation: dict[str, Any], output: OutputFunction) -> None:
    output("当前玩家可见状态：")
    output(terminal_safe_text(canonical_json(presentation)))
    output("可选行动：")
    for index, choice in enumerate(presentation["choices"], start=1):
        action_type = terminal_safe_text(choice["action_type"])
        display_params = choice.get("display_params")
        suffix = f" {terminal_safe_text(canonical_json(display_params))}" if display_params is not None else ""
        output(f"{index}. {action_type}{suffix}")
    output("输入选项编号、STOP，或 :locale zh-CN / :locale en / :locale ar")


def _validate_callable(value: Any, field: str) -> None:
    if not callable(value):
        raise _invalid(f"{field} must be callable")


def _validate_path(value: Any, field: str) -> Path:
    try:
        path = lexical_absolute(value)
    except PlayError as exc:
        raise _invalid(f"{field} is invalid") from exc
    if "\x00" in str(path):
        raise _invalid(f"{field} is invalid")
    return path


def _validate_id_input(value: Any, field: str) -> None:
    if not isinstance(value, str) or _STABLE_ID.fullmatch(value) is None:
        raise _invalid(f"{field} is invalid")


def _validate_narrator_argv(value: Sequence[str] | None) -> None:
    if value is None:
        return
    if not isinstance(value, (list, tuple)) or not value or not all(isinstance(item, str) and item and "\x00" not in item for item in value):
        raise _invalid("narrator argv is invalid")


def _validate_common_callbacks(input_fn: Any, output_fn: Any) -> None:
    _validate_callable(input_fn, "input_fn")
    _validate_callable(output_fn, "output_fn")


def _validate_response_path(path: Any, workspace: Path) -> Path:
    if isinstance(path, str) and path == "-":
        raise _invalid("response file '-' is not supported")
    candidate = _validate_path(path, "response_file")
    try:
        common = os.path.commonpath([os.path.normcase(str(workspace)), os.path.normcase(str(candidate))])
    except (ValueError, OSError) as exc:
        raise _invalid("response file path is invalid") from exc
    if common == os.path.normcase(str(workspace)):
        raise _invalid("response file must be outside the Play workspace")
    return candidate


class PlayService:
    """One workspace-bound facade over public Campaign and Story functions."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = lexical_absolute(workspace)

    def _layout(self, *, existing: bool) -> tuple[Path, Path]:
        workspace = require_workspace(self.workspace) if existing else ensure_new_workspace(self.workspace)
        return workspace_children(workspace)

    @staticmethod
    def _call_campaign(function: Callable[..., dict[str, Any]], *args: Any, operation: str, **kwargs: Any) -> dict[str, Any]:
        try:
            result = function(*args, **kwargs)
        except Exception as exc:
            raise _map_boundary_error(exc, operation=operation, boundary="campaign") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise PlayError("PLAY_CAMPAIGN_FAILED", f"Campaign {operation} returned an invalid result")
        return result

    @staticmethod
    def _call_story(function: Callable[..., dict[str, Any]], *args: Any, operation: str, **kwargs: Any) -> dict[str, Any]:
        try:
            result = function(*args, **kwargs)
        except Exception as exc:
            raise _map_boundary_error(exc, operation=operation, boundary="story") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise PlayError("PLAY_STORY_FAILED", f"Story {operation} returned an invalid result")
        return result

    def _verify_pair(self, campaign_dir: Path, story_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        if not _present_directory(campaign_dir) or not _present_directory(story_dir):
            raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace requires campaign and story directories")
        campaign = self._call_campaign(verify_campaign, campaign_dir, operation="verification")
        _validate_campaign_result(campaign, require_verification=True)
        story = self._call_story(verify_story, story_dir, campaign_dir=campaign_dir, operation="verification")
        _validate_story_status(story)
        verification = story.get("verification")
        if not isinstance(verification, dict) or verification.get("valid") is not True or verification.get("read_only") is not True:
            raise _integrity("Story verification proof is incomplete")
        _cross_check(campaign, story)
        return campaign, story

    def _compose_status(self, campaign: dict[str, Any], story: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(campaign, dict) or not isinstance(story, dict):
            raise _integrity("Campaign/Story status result is invalid")
        _validate_manifest(campaign.get("campaign"), label="campaign")
        session = _validate_session_summary(campaign.get("session"), label="campaign.session")
        if "canonical_request" in campaign or "player_presentation" in campaign:
            _validate_request_pair(campaign)
        _cross_check(campaign, story)
        readiness = story["export_readiness"]
        terminal = session["status"] in _TERMINAL_STATUSES
        return {
            "ok": True,
            "campaign_status": {"campaign": campaign["campaign"], "session": session},
            "story_status": story,
            "terminal": terminal,
            "pending_narration": story["pending_turn_id"] is not None,
            "missing_narration_work": story["missing_narration_work"],
            "snapshot_ready": readiness["current_snapshot_ready"],
            "final_ready": readiness["final_ready"],
            "novel_status": story["novel_status"],
        }

    def _read_status_pair(self, campaign_dir: Path, story_dir: Path, *, validate_request: bool = True) -> dict[str, Any]:
        status_value = self._call_campaign(status_campaign, campaign_dir, operation="status")
        story = self._call_story(status_story, story_dir, campaign_dir=campaign_dir, operation="status")
        if not validate_request:
            return self._compose_status(status_value, story)
        current = self._call_campaign(next_campaign, campaign_dir, operation="status request validation")
        _validate_campaign_result(current)
        if status_value.get("campaign") != current.get("campaign"):
            raise _integrity("Campaign status and current manifest are inconsistent")
        status_session = _validate_session_summary(status_value.get("session"), label="campaign.status.session")
        if status_session != current["session"]:
            raise _integrity("Campaign status and current request are inconsistent")
        return self._compose_status(current, story)

    def status(self) -> dict[str, Any]:
        campaign_dir, story_dir = self._layout(existing=True)
        if not _present_directory(campaign_dir) or not _present_directory(story_dir):
            raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace requires campaign and story directories")
        return self._read_status_pair(campaign_dir, story_dir)

    def verify(self) -> dict[str, Any]:
        campaign_dir, story_dir = self._layout(existing=True)
        campaign, story = self._verify_pair(campaign_dir, story_dir)
        composed = self._compose_status(campaign, story)
        return {
            "ok": True,
            "valid": True,
            "campaign_verification": campaign["verification"],
            "story_verification": story["verification"],
            **composed,
        }

    def export(self, *, mode: str, accepted_decisions: int | None = None) -> dict[str, Any]:
        if type(mode) is not str or mode not in {"snapshot", "final"}:
            raise _invalid("export mode must be snapshot or final")
        if mode == "final" and accepted_decisions is not None:
            raise _invalid("final export does not accept accepted_decisions")
        if mode == "snapshot" and accepted_decisions is not None:
            if type(accepted_decisions) is not int or accepted_decisions < 0:
                raise _invalid("snapshot accepted_decisions must be a non-negative integer")
        campaign_dir, story_dir = self._layout(existing=True)
        if not _present_directory(campaign_dir) or not _present_directory(story_dir):
            raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace requires campaign and story directories")
        combined = self._read_status_pair(campaign_dir, story_dir)
        if mode == "snapshot" and accepted_decisions is None:
            accepted_decisions = combined["story_status"]["committed_prefix"]
        result = self._call_story(
            export_story,
            story_dir,
            campaign_dir=campaign_dir,
            mode=mode,
            accepted_decisions=accepted_decisions,
            operation="export",
        )
        if mode == "final":
            refreshed = self._read_status_pair(campaign_dir, story_dir)
            if refreshed["story_status"]["novel_status"] != "CURRENT_FINAL":
                raise _integrity("final export did not produce CURRENT_FINAL Story status")
            result = dict(result)
            result["story_status"] = refreshed["story_status"]
            result["status"] = refreshed
        return result

    def _preflight_new(
        self,
        *,
        world_bundle_dir: Any,
        projection_bundle_dir: Any,
        campaign_id: Any,
        story_id: Any,
        actor_id: Any,
        max_decisions: Any,
        locale: Any,
        voice_id: Any,
        narrator_argv: Sequence[str] | None,
        narrator_timeout: Any,
        input_fn: Any,
        output_fn: Any,
    ) -> tuple[float, Path, Path]:
        if not isinstance(locale, str) or locale not in SUPPORTED_LOCALES:
            raise _invalid("locale is unsupported")
        if type(max_decisions) is not int or max_decisions <= 0:
            raise _invalid("max_decisions must be a positive integer")
        timeout = validate_timeout(narrator_timeout)
        _validate_narrator_argv(narrator_argv)
        _validate_common_callbacks(input_fn, output_fn)
        for value, field in ((campaign_id, "campaign_id"), (story_id, "story_id"), (actor_id, "actor_id"), (voice_id, "voice_id")):
            _validate_id_input(value, field)
        return timeout, _validate_path(world_bundle_dir, "world_bundle_dir"), _validate_path(projection_bundle_dir, "projection_bundle_dir")

    def new(
        self,
        *,
        world_bundle_dir: str | Path,
        projection_bundle_dir: str | Path,
        campaign_id: str,
        story_id: str,
        actor_id: str,
        max_decisions: int,
        locale: str,
        voice_id: str,
        narrator_argv: Sequence[str] | None = None,
        narrator_timeout: float = DEFAULT_NARRATOR_TIMEOUT,
        input_fn: InputFunction = input,
        output_fn: OutputFunction = print,
    ) -> dict[str, Any]:
        timeout, world_path, projection_path = self._preflight_new(
            world_bundle_dir=world_bundle_dir,
            projection_bundle_dir=projection_bundle_dir,
            campaign_id=campaign_id,
            story_id=story_id,
            actor_id=actor_id,
            max_decisions=max_decisions,
            locale=locale,
            voice_id=voice_id,
            narrator_argv=narrator_argv,
            narrator_timeout=narrator_timeout,
            input_fn=input_fn,
            output_fn=output_fn,
        )
        campaign_dir, story_dir = self._layout(existing=False)
        self._call_campaign(
            create_campaign,
            campaign_dir,
            world_bundle_dir=world_path,
            projection_bundle_dir=projection_path,
            campaign_id=campaign_id,
            actor_id=actor_id,
            max_decisions=max_decisions,
            operation="creation",
        )
        self._call_story(
            init_story,
            story_dir,
            campaign_dir=campaign_dir,
            story_id=story_id,
            initial_narration_locale=locale,
            initial_voice_id=voice_id,
            operation="initialization",
        )
        self._verify_pair(campaign_dir, story_dir)
        return self._loop(
            campaign_dir,
            story_dir,
            locale_override=None,
            narrator_argv=narrator_argv,
            narrator_timeout=timeout,
            input_fn=input_fn,
            output_fn=output_fn,
        )

    def _preflight_resume(
        self,
        *,
        locale: Any,
        story_id: Any,
        voice_id: Any,
        narrator_argv: Sequence[str] | None,
        narrator_timeout: Any,
        input_fn: Any,
        output_fn: Any,
    ) -> float:
        if locale is not None and (not isinstance(locale, str) or locale not in SUPPORTED_LOCALES):
            raise _invalid("locale is unsupported")
        if story_id is not None:
            _validate_id_input(story_id, "story_id")
        _validate_id_input(voice_id, "voice_id")
        timeout = validate_timeout(narrator_timeout)
        _validate_narrator_argv(narrator_argv)
        _validate_common_callbacks(input_fn, output_fn)
        return timeout

    def resume(
        self,
        *,
        locale: str | None = None,
        story_id: str | None = None,
        voice_id: str = DEFAULT_VOICE_ID,
        narrator_argv: Sequence[str] | None = None,
        narrator_timeout: float = DEFAULT_NARRATOR_TIMEOUT,
        input_fn: InputFunction = input,
        output_fn: OutputFunction = print,
    ) -> dict[str, Any]:
        timeout = self._preflight_resume(
            locale=locale,
            story_id=story_id,
            voice_id=voice_id,
            narrator_argv=narrator_argv,
            narrator_timeout=narrator_timeout,
            input_fn=input_fn,
            output_fn=output_fn,
        )
        campaign_dir, story_dir = self._layout(existing=True)
        if not _present_directory(campaign_dir):
            raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace has no Campaign")
        campaign = self._call_campaign(verify_campaign, campaign_dir, operation="verification")
        _validate_campaign_result(campaign, require_verification=True)
        if not _present_directory(story_dir):
            if story_id is None or locale is None:
                raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "missing Story requires story_id and locale for safe initialization")
            self._call_story(
                init_story,
                story_dir,
                campaign_dir=campaign_dir,
                story_id=story_id,
                initial_narration_locale=locale,
                initial_voice_id=voice_id,
                operation="recovery initialization",
            )
            locale = None
        self._verify_pair(campaign_dir, story_dir)
        return self._loop(
            campaign_dir,
            story_dir,
            locale_override=locale,
            narrator_argv=narrator_argv,
            narrator_timeout=timeout,
            input_fn=input_fn,
            output_fn=output_fn,
        )

    def narrate(self, *, response_file: str | Path, output_fn: OutputFunction = print) -> dict[str, Any]:
        _validate_callable(output_fn, "output_fn")
        response_path = _validate_response_path(response_file, self.workspace)
        campaign_dir, story_dir = self._layout(existing=True)
        self._verify_pair(campaign_dir, story_dir)
        combined = self._read_status_pair(campaign_dir, story_dir, validate_request=False)
        pending_id = combined["story_status"]["pending_turn_id"]
        if pending_id is None:
            raise _invalid("there is no existing pending narration request")
        prepared = self._call_story(
            prepare_story,
            story_dir,
            campaign_dir=campaign_dir,
            turn_id=pending_id,
            operation="pending request lookup",
        )
        request = prepared.get("request")
        if not isinstance(request, dict) or prepared.get("committed") is not False:
            raise _integrity("pending narration request is invalid")
        response = read_external_json(response_path)
        if not isinstance(response, dict):
            raise PlayError("PLAY_NARRATOR_FAILED", "narrator response must be a JSON object")
        committed = self._commit_response(campaign_dir, story_dir, response, output_fn=output_fn)
        return {"ok": True, "result": committed.get("result"), "turn": committed.get("turn")}

    def _commit_response(
        self,
        campaign_dir: Path,
        story_dir: Path,
        response: dict[str, Any],
        *,
        output_fn: OutputFunction,
    ) -> dict[str, Any]:
        try:
            committed = commit_story(story_dir, campaign_dir=campaign_dir, response=response)
        except StoryError as exc:
            if exc.code in _RESPONSE_ORIGIN_STORY_CODES:
                raise PlayError("PLAY_NARRATOR_FAILED", "external narrator response was rejected", cause_code=exc.code) from exc
            raise _map_boundary_error(exc, operation="narration commit") from exc
        except Exception as exc:
            raise _map_boundary_error(exc, operation="narration commit", boundary="story") from exc
        if not isinstance(committed, dict) or committed.get("ok") is not True:
            raise PlayError("PLAY_STORY_FAILED", "Story narration commit returned an invalid result")
        turn = committed.get("turn")
        if not isinstance(turn, dict) or not isinstance(turn.get("prose"), str):
            raise _integrity("committed turn has no public prose")
        output_fn(terminal_safe_text(turn["prose"]))
        return committed

    @staticmethod
    def _manual_pending(request: dict[str, Any], workspace: Path, output_fn: OutputFunction) -> None:
        output_fn("--- NARRATION REQUEST BEGIN ---")
        output_fn(terminal_safe_text(canonical_json(request)))
        output_fn("--- NARRATION REQUEST END ---")
        output_fn("Narration pending. Create one Narration Response JSON outside the workspace.")
        output_fn("Response fields: schema_version, narration_request_id, narration_request_hash, locale, claims, prose")
        workspace_text = terminal_safe_text(str(workspace))
        output_fn(f"Run: python -m tgn.play narrate --workspace {workspace_text} --response-file <response.json>")
        output_fn(f"Then run: python -m tgn.play resume --workspace {workspace_text}")

    def _drain_narration_work(
        self,
        campaign_dir: Path,
        story_dir: Path,
        *,
        narrator_argv: Sequence[str] | None,
        narrator_timeout: float,
        output_fn: OutputFunction,
        creation_locale: str | None = None,
    ) -> dict[str, Any]:
        combined = self._read_status_pair(campaign_dir, story_dir, validate_request=False)
        while combined["story_status"]["missing_narration_work"]:
            before_story = combined["story_status"]
            pending_id = before_story["pending_turn_id"]
            initial_locale = before_story["story"]["initial_narration_locale"]
            prepare_locale = initial_locale if pending_id is not None else (creation_locale or initial_locale)
            prepared = self._call_story(
                prepare_story,
                story_dir,
                campaign_dir=campaign_dir,
                turn_id=pending_id,
                narration_locale=prepare_locale,
                operation="narration preparation",
            )
            request = prepared.get("request")
            if not isinstance(request, dict) or prepared.get("committed") is not False:
                raise _integrity("narration backlog did not yield one pending request")
            if narrator_argv is None:
                self._manual_pending(request, self.workspace, output_fn)
                raise PlayError("PLAY_NARRATION_PENDING", "narration response is required before another action")
            response = run_narrator(narrator_argv, request, timeout=narrator_timeout)
            self._commit_response(campaign_dir, story_dir, response, output_fn=output_fn)
            after = self._read_status_pair(campaign_dir, story_dir, validate_request=False)
            after_story = after["story_status"]
            if after_story["committed_prefix"] != before_story["committed_prefix"] + 1 or after_story["committed_turn_count"] != before_story["committed_turn_count"] + 1:
                raise _integrity("narration commit made no single-turn progress")
            if pending_id is not None and after_story["pending_turn_id"] == pending_id:
                raise _integrity("oldest narration request was not removed")
            if pending_id is None and after_story["request_count"] != before_story["request_count"] + 1:
                raise _integrity("narration request progress is invalid")
            creation_locale = None
            combined = after
        return combined

    def _loop(
        self,
        campaign_dir: Path,
        story_dir: Path,
        *,
        locale_override: str | None = None,
        locale: str | None = None,
        narrator_argv: Sequence[str] | None,
        narrator_timeout: float,
        input_fn: InputFunction,
        output_fn: OutputFunction,
    ) -> dict[str, Any]:
        if locale_override is None and locale is not None:
            locale_override = locale
        next_locale_override = locale_override
        while True:
            self._drain_narration_work(
                campaign_dir,
                story_dir,
                narrator_argv=narrator_argv,
                narrator_timeout=narrator_timeout,
                output_fn=output_fn,
            )
            current = self._call_campaign(next_campaign, campaign_dir, operation="next")
            _validate_campaign_result(current)
            story_status_value = self._call_story(status_story, story_dir, campaign_dir=campaign_dir, operation="status")
            composed = self._compose_status(current, story_status_value)
            request, presentation = _validate_request_pair(current)
            if request is None:
                if composed["final_ready"]:
                    exported = self.export(mode="final")
                    refreshed_story = exported.get("story_status")
                    if not isinstance(refreshed_story, dict):
                        refreshed_story = self._read_status_pair(campaign_dir, story_dir)["story_status"]
                    output_fn("final novel exported: story/novel.md")
                    return {
                        "ok": True,
                        "terminal": True,
                        "export": exported,
                        "campaign": current["session"],
                        "story": refreshed_story,
                    }
                return {"ok": True, "terminal": composed["terminal"], "campaign": current["session"], "story": story_status_value}
            if presentation is None:
                raise _integrity("non-terminal Campaign has no presentation")
            while True:
                _render_presentation(presentation, output_fn)
                try:
                    raw_input = input_fn()
                except (EOFError, KeyboardInterrupt) as exc:
                    raise _invalid("player input ended") from exc
                if not isinstance(raw_input, str):
                    raise _invalid("player input is invalid")
                locale_commands = {f":locale {item}" for item in sorted(SUPPORTED_LOCALES)}
                if raw_input in locale_commands:
                    next_locale_override = raw_input.split(" ", 1)[1]
                    output_fn(f"narration locale set for the next request: {terminal_safe_text(next_locale_override)}")
                    continue
                if raw_input == "STOP":
                    self._call_campaign(
                        stop_campaign,
                        campaign_dir,
                        request_fingerprint=request["request_fingerprint"],
                        operation="STOP",
                    )
                    break
                if len(raw_input) > MAX_PLAYER_OPTION_DIGITS or _POSITIVE_INPUT.fullmatch(raw_input) is None:
                    output_fn("invalid input; choose one option number, STOP, or a locale command")
                    continue
                number = int(raw_input)
                choices = request["choices"]
                if number > len(choices):
                    output_fn("invalid option number")
                    continue
                selected = choices[number - 1]
                self._call_campaign(
                    choose_campaign,
                    campaign_dir,
                    request_fingerprint=request["request_fingerprint"],
                    choice_id=selected["choice_id"],
                    operation="choice",
                )
                self._drain_narration_work(
                    campaign_dir,
                    story_dir,
                    narrator_argv=narrator_argv,
                    narrator_timeout=narrator_timeout,
                    output_fn=output_fn,
                    creation_locale=next_locale_override,
                )
                next_locale_override = None
                break


__all__ = ["DEFAULT_VOICE_ID", "PlayService"]
