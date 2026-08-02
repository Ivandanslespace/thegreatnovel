"""Campaign-bound Story persistence service for Phase 9C1."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from ..campaign.models import CampaignError, CampaignManifest
from ..narrator import NarrationContext, NarrationValidationError, create_builtin_registry, validate_narration
from .campaign_snapshot import (
    CampaignSnapshot,
    capture_campaign_snapshot,
    compare_request_prefix,
    verify_and_capture_campaign,
)
from .claims import validate_claims
from .common import (
    canonical_bytes,
    is_actual_directory,
    lexical_absolute,
    parse_json_bytes,
    path_overlaps,
    read_canonical_json_file,
    read_regular_file,
    require_actual_directory,
    sha256_bytes,
    validate_prose,
    validate_stable_id,
    validate_story_campaign_separation,
    write_fd_all,
)
from .models import (
    TURN_ARTIFACT_FORMAT_ID,
    NarrationRequest,
    NarrationResponse,
    StoryError,
    StoryManifest,
    TurnNarrationArtifact,
    request_hash,
    turn_artifact_hash,
)
from .publication import (
    BoundPublicationDirectory,
    PublicationBoundaryChanged,
    PublicationConflict,
    PublicationRuntime,
    PublicationUnavailable,
    atomic_no_replace_move,
    publish_bytes_no_replace,
)
from .reconstruction import CampaignHistory, ReconstructedTurn, reconstruct_campaign
from .verification import (
    StoryView,
    load_story_view,
    story_directory_identity_matches,
)


def _invalid(message: str) -> StoryError:
    return StoryError("INVALID_STORY_INPUT", message)


def _story_integrity(message: str) -> StoryError:
    return StoryError("STORY_INTEGRITY_MISMATCH", message)


def _campaign_integrity(message: str) -> StoryError:
    return StoryError("CAMPAIGN_INTEGRITY_MISMATCH", message)


def _map_campaign_error(error: CampaignError) -> StoryError:
    if error.code in {"CAMPAIGN_NOT_FOUND", "INVALID_CAMPAIGN_INPUT"}:
        return StoryError("INVALID_STORY_INPUT", "campaign_dir is not a valid Campaign locator")
    if error.code == "CAMPAIGN_PUBLICATION_UNAVAILABLE":
        return StoryError("CAMPAIGN_INTEGRITY_MISMATCH", "candidate Campaign is not valid")
    return StoryError("CAMPAIGN_INTEGRITY_MISMATCH", "candidate Campaign failed frozen verification")


def _validate_voice(voice_id: str) -> None:
    try:
        create_builtin_registry().get(voice_id)
    except Exception as exc:
        raise _invalid("voice_id is not an approved built-in Voice Profile") from exc


def _path_gate(story_dir: str | Path, campaign_dir: str | Path, *, story_may_be_missing: bool) -> tuple[Path, Path]:
    try:
        return validate_story_campaign_separation(
            story_dir,
            campaign_dir,
            story_may_be_missing=story_may_be_missing,
        )
    except StoryError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise _invalid("Story and Campaign directories are invalid or overlap") from exc


def _load_bound(view: StoryView, campaign_dir: str | Path) -> tuple[CampaignManifest, CampaignSnapshot]:
    _path_gate(view.root, campaign_dir, story_may_be_missing=False)
    try:
        campaign_manifest, snapshot = verify_and_capture_campaign(campaign_dir)
    except CampaignError as exc:
        raise _map_campaign_error(exc) from exc
    except (OSError, TypeError, ValueError) as exc:
        raise _campaign_integrity("candidate Campaign could not be captured") from exc
    story = view.manifest
    if (
        campaign_manifest.campaign_id != story.campaign_id
        or campaign_manifest.session_id != story.session_id
        or campaign_manifest.worldpack_hash != story.worldpack_hash
        or campaign_manifest.source_initial_state_hash != story.source_initial_state_hash
        or campaign_manifest.player_projection_hash != story.player_projection_hash
        or snapshot.campaign_manifest_hash != story.campaign_manifest_hash
    ):
        raise StoryError("CAMPAIGN_BINDING_MISMATCH", "candidate Campaign does not match Story bindings")
    _validate_voice(story.initial_voice_id)
    return campaign_manifest, snapshot


def _load_story_and_bound(story_dir: str | Path, campaign_dir: str | Path) -> tuple[StoryView, CampaignManifest, CampaignSnapshot]:
    try:
        view = load_story_view(story_dir)
    except StoryError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise _story_integrity("Story tree cannot be read safely") from exc
    campaign_manifest, snapshot = _load_bound(view, campaign_dir)
    return view, campaign_manifest, snapshot


def _stable_history(
    view: StoryView,
    campaign_dir: str | Path,
    snapshot: CampaignSnapshot,
) -> tuple[CampaignManifest, CampaignSnapshot, CampaignHistory]:
    try:
        history = reconstruct_campaign(view.manifest, snapshot)
    except StoryError:
        raise
    except Exception as exc:
        raise _campaign_integrity("Campaign history cannot be reconstructed") from exc
    after = _require_complete_snapshot_unchanged(campaign_dir, snapshot)
    try:
        campaign_manifest = CampaignManifest.from_dict(parse_json_bytes(after.file_bytes("campaign.json"), require_canonical=True))
    except Exception as exc:
        raise _campaign_integrity("Campaign manifest changed during Story operation") from exc
    return campaign_manifest, after, history


def _require_complete_snapshot_unchanged(
    campaign_dir: str | Path,
    before: CampaignSnapshot,
) -> CampaignSnapshot:
    """Require a full Campaign observable equality at a publication/read boundary."""

    try:
        after = capture_campaign_snapshot(campaign_dir)
    except Exception as exc:
        raise StoryError("CAMPAIGN_SNAPSHOT_CHANGED", "Campaign changed during Story operation") from exc
    if before.comparable() != after.comparable():
        raise StoryError("CAMPAIGN_SNAPSHOT_CHANGED", "Campaign changed during Story operation")
    return after


def _write_owned_file(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd: int | None = None
    try:
        fd = os.open(os.fspath(path), flags, 0o600)
        write_fd_all(fd, payload)
        os.fsync(fd)
        os.close(fd)
        fd = None
        read_regular_file(path)
    except Exception as exc:
        raise _story_integrity("temporary Story artifact could not be written") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _remove_owned_temp(path: Path | None) -> None:
    if path is None:
        return
    binding: BoundPublicationDirectory | None = None
    try:
        if not os.path.lexists(path):
            return
        binding = BoundPublicationDirectory.bind(path.parent)
        binding.adopt_existing(path, directory=True, owned=True)
        binding.cleanup_temp()
    except FileNotFoundError:
        return
    except Exception as exc:
        raise StoryError("STORY_PUBLICATION_UNAVAILABLE", "owned Story temporary cleanup failed") from exc
    finally:
        if binding is not None:
            binding.close_safely()


def _publish_directory(
    source: Path,
    target: Path,
    *,
    parent_binding: BoundPublicationDirectory | None = None,
    boundary_check: Any | None = None,
    before_atomic: Any | None = None,
) -> None:
    try:
        if parent_binding is None:
            atomic_no_replace_move(source, target, directory=True)
        else:
            if parent_binding.temp_name is None:
                parent_binding.adopt_existing(source, directory=True)
            parent_binding.publish_adopted(
                target.name,
                boundary_check=boundary_check,
                before_atomic=before_atomic,
            )
    except PublicationConflict as exc:
        raise StoryError("STORY_ALREADY_EXISTS", "Story target already exists") from exc
    except (PublicationUnavailable, PublicationRuntime) as exc:
        raise StoryError("STORY_PUBLICATION_UNAVAILABLE", "atomic Story publication is unavailable") from exc


def _publish_request(
    path: Path,
    payload: bytes,
    *,
    parent_binding: BoundPublicationDirectory | None = None,
    boundary_check: Any | None = None,
    before_atomic: Any | None = None,
) -> None:
    try:
        kwargs: dict[str, Any] = {}
        if parent_binding is not None:
            kwargs["parent_binding"] = parent_binding
        if boundary_check is not None:
            kwargs["boundary_check"] = boundary_check
        if before_atomic is not None:
            kwargs["before_atomic"] = before_atomic
        publish_bytes_no_replace(path, payload, **kwargs)
    except PublicationBoundaryChanged as exc:
        if str(exc) == "Campaign snapshot changed":
            raise StoryError("CAMPAIGN_SNAPSHOT_CHANGED", "Campaign changed during Story publication") from exc
        if str(exc).startswith("story-error:"):
            code = str(exc).split(":", 1)[1]
            if code == "CAMPAIGN_SNAPSHOT_CHANGED":
                raise StoryError("CAMPAIGN_SNAPSHOT_CHANGED", "Campaign changed during Story publication") from exc
            if code == "CAMPAIGN_INTEGRITY_MISMATCH":
                raise _campaign_integrity("request-bound Campaign history changed") from exc
            if code == "STORY_INTEGRITY_MISMATCH":
                raise _story_integrity("pending request changed during publication") from exc
        raise StoryError("STORY_PUBLICATION_UNAVAILABLE", "Story directory identity changed during publication") from exc
    except PublicationConflict as exc:
        raise StoryError("STORY_INTEGRITY_MISMATCH", "request target appeared during publication") from exc
    except (PublicationUnavailable, PublicationRuntime) as exc:
        raise StoryError("STORY_PUBLICATION_UNAVAILABLE", "request publication is unavailable") from exc


def _published_turn(
    path: Path,
    payload: bytes,
    *,
    parent_binding: BoundPublicationDirectory | None = None,
    boundary_check: Any | None = None,
    before_atomic: Any | None = None,
) -> str:
    try:
        kwargs: dict[str, Any] = {}
        if parent_binding is not None:
            kwargs["parent_binding"] = parent_binding
        if boundary_check is not None:
            kwargs["boundary_check"] = boundary_check
        if before_atomic is not None:
            kwargs["before_atomic"] = before_atomic
        publish_bytes_no_replace(path, payload, **kwargs)
        return "committed"
    except PublicationBoundaryChanged as exc:
        if str(exc) == "Campaign snapshot changed":
            raise StoryError("CAMPAIGN_SNAPSHOT_CHANGED", "Campaign changed during Story publication") from exc
        if str(exc).startswith("story-error:"):
            code = str(exc).split(":", 1)[1]
            if code == "CAMPAIGN_SNAPSHOT_CHANGED":
                raise StoryError("CAMPAIGN_SNAPSHOT_CHANGED", "Campaign changed during Story publication") from exc
            if code == "CAMPAIGN_INTEGRITY_MISMATCH":
                raise _campaign_integrity("request-bound Campaign history changed") from exc
            if code == "STORY_INTEGRITY_MISMATCH":
                raise _story_integrity("pending request changed during publication") from exc
        raise StoryError("STORY_PUBLICATION_UNAVAILABLE", "Story directory identity changed during publication") from exc
    except PublicationConflict:
        try:
            existing, _ = read_regular_file(path)
            if existing == payload:
                return "already_committed"
        except Exception:
            pass
        return "conflict"
    except (PublicationUnavailable, PublicationRuntime) as exc:
        raise StoryError("STORY_PUBLICATION_UNAVAILABLE", "turn publication is unavailable") from exc


def _story_publication_guard(view: StoryView, directory_name: str):
    """Bind one artifact writer to the Story directories already verified by load."""

    if directory_name == "requests":
        expected = view.requests_directory
        directory = view.root / "requests"
    elif directory_name == "turns":
        expected = view.turns_directory
        directory = view.root / "turns"
    else:
        raise ValueError("unsupported Story publication directory")
    root_expected = view.root_directory

    def check() -> None:
        if not story_directory_identity_matches(view.root, root_expected):
            raise PublicationRuntime("Story root directory identity changed")
        if not story_directory_identity_matches(directory, expected):
            raise PublicationRuntime(f"Story {directory_name} directory identity changed")

    return check


def _anchored_story_publication_guard(
    view: StoryView,
    directory_name: str,
    root_binding: BoundPublicationDirectory,
    directory_binding: BoundPublicationDirectory,
):
    path_check = _story_publication_guard(view, directory_name)

    def check() -> None:
        path_check()
        root_binding.check()
        directory_binding.check()

    return check


def _prepare_publication_guard(
    view: StoryView,
    campaign_dir: str | Path,
    before_snapshot: CampaignSnapshot,
    *,
    root_binding: BoundPublicationDirectory | None = None,
    directory_binding: BoundPublicationDirectory | None = None,
):
    story_check = _story_publication_guard(view, "requests")

    def check() -> None:
        try:
            _require_complete_snapshot_unchanged(campaign_dir, before_snapshot)
        except StoryError as exc:
            if exc.code == "CAMPAIGN_SNAPSHOT_CHANGED":
                raise PublicationBoundaryChanged("Campaign snapshot changed") from exc
            raise
        story_check()
        if root_binding is not None:
            root_binding.check()
        if directory_binding is not None:
            directory_binding.check()

    return check


def _pending_request_unchanged(
    view: StoryView,
    request: NarrationRequest,
    request_binding: BoundPublicationDirectory,
) -> None:
    expected_file = next(
        (item for item in view.files if item.relative_path == f"requests/{request.turn_id}.json"),
        None,
    )
    expected_payload = next(
        (payload for number, value, payload in view.requests if value.turn_id == request.turn_id),
        None,
    )
    if expected_file is None or expected_payload is None:
        raise PublicationBoundaryChanged("story-error:STORY_INTEGRITY_MISMATCH")
    try:
        current_payload, current_stat = request_binding.read_child_bytes(f"{request.turn_id}.json")
        current_identity = (
            ("posix", int(current_stat.st_dev), int(current_stat.st_ino))
            if getattr(current_stat, "st_dev", None) is not None
            and getattr(current_stat, "st_ino", None) is not None
            and not (current_stat.st_dev == 0 and current_stat.st_ino == 0)
            else (
                "fallback",
                int(getattr(current_stat, "st_file_attributes", 0)),
                int(getattr(current_stat, "st_ctime_ns", 0)),
                int(current_stat.st_mode),
            )
        )
        if (
            current_identity != expected_file.identity
            or current_payload != expected_payload
            or sha256_bytes(current_payload) != expected_file.sha256
            or len(current_payload) != expected_file.size
            or current_stat.st_mtime_ns != expected_file.mtime_ns
        ):
            raise PublicationBoundaryChanged("story-error:STORY_INTEGRITY_MISMATCH")
        current_value = NarrationRequest.from_dict(parse_json_bytes(current_payload, require_canonical=True))
    except Exception as exc:
        if isinstance(exc, PublicationBoundaryChanged):
            raise
        raise PublicationBoundaryChanged("story-error:STORY_INTEGRITY_MISMATCH") from exc
    if current_value.to_dict() != request.to_dict():
        raise PublicationBoundaryChanged("story-error:STORY_INTEGRITY_MISMATCH")


def _story_file_identity(file_stat: os.stat_result) -> tuple[Any, ...]:
    device = getattr(file_stat, "st_dev", None)
    inode = getattr(file_stat, "st_ino", None)
    if device is not None and inode is not None and not (device == 0 and inode == 0):
        return ("posix", int(device), int(inode))
    return (
        "fallback",
        int(getattr(file_stat, "st_file_attributes", 0)),
        int(getattr(file_stat, "st_ctime_ns", 0)),
        int(file_stat.st_mode),
    )


def _validate_committed_turn_unchanged(
    view: StoryView,
    turn: TurnNarrationArtifact,
    turns_binding: BoundPublicationDirectory,
) -> bytes:
    """Validate an existing committed turn through its anchored source parent."""

    expected_file = next(
        (item for item in view.files if item.relative_path == f"turns/{turn.turn_id}.json"),
        None,
    )
    expected_payload = next(
        (payload for number, value, payload in view.turns if value.turn_id == turn.turn_id),
        None,
    )
    if expected_file is None or expected_payload is None:
        raise _story_integrity("committed turn observable is missing")
    try:
        current_payload, current_stat = turns_binding.read_child_bytes(f"{turn.turn_id}.json")
    except Exception as exc:
        raise _story_integrity("committed turn source changed during recommit") from exc
    if (
        _story_file_identity(current_stat) != expected_file.identity
        or current_payload != expected_payload
        or sha256_bytes(current_payload) != expected_file.sha256
        or len(current_payload) != expected_file.size
        or current_stat.st_mtime_ns != expected_file.mtime_ns
    ):
        raise _story_integrity("committed turn source changed during recommit")
    try:
        current_value = TurnNarrationArtifact.from_dict(parse_json_bytes(current_payload, require_canonical=True))
    except Exception as exc:
        raise _story_integrity("committed turn artifact is invalid") from exc
    if (
        current_value.to_dict() != turn.to_dict()
        or current_value.turn_id != turn.turn_id
        or current_value.turn_artifact_hash != turn.turn_artifact_hash
        or turn_artifact_hash(current_value.to_dict()) != current_value.turn_artifact_hash
    ):
        raise _story_integrity("committed turn artifact changed during recommit")
    return current_payload


def _commit_publication_guard(
    view: StoryView,
    campaign_dir: str | Path,
    before_snapshot: CampaignSnapshot,
    request: NarrationRequest,
    root_binding: BoundPublicationDirectory,
    request_binding: BoundPublicationDirectory,
    directory_binding: BoundPublicationDirectory,
):
    story_check = _anchored_story_publication_guard(view, "turns", root_binding, directory_binding)

    def check() -> None:
        story_check()
        request_binding.check()
        try:
            _commit_prefix_check(campaign_dir, before_snapshot, request)
        except StoryError as exc:
            raise PublicationBoundaryChanged(f"story-error:{exc.code}") from exc
        _pending_request_unchanged(view, request, request_binding)

    return check


def _open_story_publication_bindings(
    view: StoryView,
    directory_name: str,
) -> tuple[BoundPublicationDirectory, BoundPublicationDirectory]:
    if directory_name not in {"requests", "turns"}:
        raise ValueError("unsupported Story publication directory")
    root_binding: BoundPublicationDirectory | None = None
    directory_binding: BoundPublicationDirectory | None = None
    try:
        root_binding = BoundPublicationDirectory.bind(view.root)
        directory_binding = BoundPublicationDirectory.bind(view.root / directory_name)
        return root_binding, directory_binding
    except Exception as exc:
        if directory_binding is not None:
            directory_binding.close_safely()
        if root_binding is not None:
            root_binding.close_safely()
        if isinstance(exc, StoryError):
            raise
        raise StoryError("STORY_PUBLICATION_UNAVAILABLE", "Story publication parent cannot be anchored") from exc


def _resource_map(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(key): int(quantity) for key, quantity in value.items()}
    if isinstance(value, list):
        return {item["resource_id"]: item["quantity"] for item in value if isinstance(item, dict)}
    return {}


def _prose_context(request: NarrationRequest) -> NarrationContext:
    brief = request.public_brief
    before = brief["observation_before"]
    after = brief["observation_after"]
    event_type = brief["action_result"]["event_types"][0]
    loot_gained: dict[str, int] = {}
    for claim in request.claim_requirements:
        if claim.get("kind") == "resource_delta" and claim.get("value", {}).get("scope") == "carried":
            value = claim["value"]
            if value.get("delta", 0) > 0:
                loot_gained[value["resource_id"]] = value["delta"]
    payload = {"loot_gained": loot_gained} if request.action_type == "SEARCH" and loot_gained else {}
    return NarrationContext(
        step=request.accepted_decision_number,
        action_type=request.action_type,
        event_type=event_type,
        game_minute_before=before.get("game_minute", 0),
        game_minute_after=after.get("game_minute", 0),
        location_before=before.get("location_id", ""),
        location_after=after.get("location_id", ""),
        stamina_before=before.get("stamina", 0),
        stamina_after=after.get("stamina", 0),
        max_stamina=before.get("max_stamina", 0),
        inventory_before=_resource_map(before.get("inventory", {})),
        inventory_after=_resource_map(after.get("inventory", {})),
        carried_before=_resource_map(before.get("carried_loot", {})),
        carried_after=_resource_map(after.get("carried_loot", {})),
        event_payload=payload,
    )


def _validate_prose_guard(request: NarrationRequest, prose: str) -> None:
    try:
        validate_prose(prose)
        validate_narration(_prose_context(request), prose)
    except (NarrationValidationError, ValueError, TypeError) as exc:
        raise StoryError("NARRATION_RESPONSE_INVALID", "prose failed bounded narration validation") from exc


def _validate_existing_artifacts(view: StoryView, history: CampaignHistory) -> None:
    request_map = view.request_map
    turn_map = view.turn_map
    request_numbers = sorted(request_map)
    turn_numbers = sorted(turn_map)
    expected_requests = list(range(1, len(request_numbers) + 1))
    expected_turns = list(range(1, len(turn_numbers) + 1))
    if request_numbers != expected_requests or turn_numbers != expected_turns:
        raise _story_integrity("Story requests or turns contain a gap")
    if len(turn_numbers) > len(request_numbers) or len(request_numbers) > history.accepted_decisions:
        raise _story_integrity("Story artifacts exceed authoritative Campaign history")
    if len(request_numbers) - len(turn_numbers) > 1:
        raise _story_integrity("Story has more than one pending request")
    for number, request, _payload in view.requests:
        if number > len(history.action_turns):
            raise _story_integrity("Story request exceeds accepted ACTION history")
        expected = history.action_turns[number - 1].request
        if request.to_dict() != expected.to_dict() or request_hash(request.to_dict()) != request.narration_request_hash:
            raise _story_integrity("Story request does not match deterministic reconstruction")
    for number, turn, _payload in view.turns:
        request = request_map.get(number)
        expected = history.action_turns[number - 1].request
        if request is None:
            raise _story_integrity("committed turn has no request")
        shared = (
            "story_id",
            "turn_id",
            "narration_request_id",
            "narration_request_hash",
            "source_request_hash",
            "campaign_id",
            "session_id",
            "accepted_decision_number",
            "recorded_decision_index",
            "request_fingerprint_before",
            "choice_id",
            "action_type",
            "action_id",
            "params",
            "duration_minutes",
            "stamina_cost",
            "event_seq_start",
            "event_seq_end",
            "state_hash_before",
            "state_hash_after",
            "narration_locale",
            "voice_id",
        )
        turn_value = turn.to_dict()
        request_value = expected.to_dict()
        if any(turn_value[field] != request_value[field] for field in shared):
            raise _story_integrity("committed turn is not bound to its request")
        try:
            validate_claims(turn.claims, expected.claim_requirements)
            _validate_prose_guard(expected, turn.prose)
        except StoryError:
            raise _story_integrity("committed turn prose is invalid")
        except Exception as exc:
            raise _story_integrity("committed turn claims are invalid") from exc
        if turn_artifact_hash(turn_value) != turn.turn_artifact_hash:
            raise _story_integrity("committed turn hash is invalid")


def _assert_story_read_only(view: StoryView) -> None:
    try:
        after = load_story_view(view.root)
    except StoryError:
        raise
    except Exception as exc:
        raise _story_integrity("Story changed during read-only verification") from exc
    if after.files != view.files or after.directories != view.directories:
        raise _story_integrity("Story observables changed during read-only verification")


def _derived_status(view: StoryView, history: CampaignHistory) -> dict[str, Any]:
    committed = len(view.turns)
    request_count = len(view.requests)
    pending = request_count == committed + 1
    missing_numbers = list(range(request_count + 1, history.accepted_decisions + 1))
    return {
        "story": view.manifest.to_dict(),
        "campaign_session": copy.deepcopy(history.session),
        "session": copy.deepcopy(history.session),
        "accepted_decisions": history.accepted_decisions,
        "recorded_decision_count": history.recorded_decision_count,
        "request_count": request_count,
        "committed_turn_count": committed,
        "committed_prefix": committed,
        "pending_turn_id": f"turn-{request_count:06d}" if pending else None,
        "missing_request_turn_ids": [f"turn-{number:06d}" for number in missing_numbers],
        "next_preparable_turn_id": (
            f"turn-{request_count + 1:06d}"
            if not pending and request_count < history.accepted_decisions
            else None
        ),
        "novel_status": "ABSENT",
        "phase_9c2_export_ready": False,
        "missing_narration_work": bool(missing_numbers or pending),
    }


def _parse_turn_id(value: str) -> int:
    if not isinstance(value, str) or not value.startswith("turn-"):
        raise _invalid("turn_id is invalid")
    try:
        number = int(value[5:])
    except ValueError as exc:
        raise _invalid("turn_id is invalid") from exc
    if number <= 0 or value != f"turn-{number:06d}":
        raise _invalid("turn_id is invalid")
    return number


def _response_value(response: Any) -> NarrationResponse:
    if isinstance(response, str):
        try:
            response = parse_json_bytes(response.encode("utf-8"), require_canonical=True)
        except Exception as exc:
            raise StoryError("NARRATION_RESPONSE_INVALID", "response JSON is invalid") from exc
    try:
        return NarrationResponse.from_dict(response)
    except Exception as exc:
        raise StoryError("NARRATION_RESPONSE_INVALID", "response schema is invalid") from exc


def _artifact_from_response(request: NarrationRequest, response: NarrationResponse) -> TurnNarrationArtifact:
    try:
        claims = validate_claims(response.claims, request.claim_requirements)
        _validate_prose_guard(request, response.prose)
    except StoryError:
        raise
    except Exception as exc:
        raise StoryError("NARRATION_RESPONSE_INVALID", "response claims are invalid") from exc
    if response.narration_request_id != request.narration_request_id or response.narration_request_hash != request.narration_request_hash:
        raise StoryError("NARRATION_RESPONSE_INVALID", "response request identity does not match pending request")
    if response.locale != request.narration_locale:
        raise StoryError("NARRATION_RESPONSE_INVALID", "response locale does not match request")
    value: dict[str, Any] = {
        "schema_version": 1,
        "artifact_format_id": TURN_ARTIFACT_FORMAT_ID,
        "turn_artifact_hash": "0" * 64,
    }
    request_value = request.to_dict()
    for field in (
        "story_id",
        "turn_id",
        "narration_request_id",
        "narration_request_hash",
        "source_request_hash",
        "campaign_id",
        "session_id",
        "accepted_decision_number",
        "recorded_decision_index",
        "request_fingerprint_before",
        "choice_id",
        "action_type",
        "action_id",
        "params",
        "duration_minutes",
        "stamina_cost",
        "event_seq_start",
        "event_seq_end",
        "state_hash_before",
        "state_hash_after",
        "narration_locale",
        "voice_id",
    ):
        value[field] = copy.deepcopy(request_value[field])
    value["claims"] = claims
    value["prose"] = response.prose
    value["turn_artifact_hash"] = turn_artifact_hash(value)
    try:
        return TurnNarrationArtifact.from_dict(value)
    except Exception as exc:
        raise StoryError("NARRATION_RESPONSE_INVALID", "turn artifact schema is invalid") from exc


def _commit_prefix_check(
    campaign_dir: str | Path,
    before: CampaignSnapshot,
    request: NarrationRequest,
) -> None:
    try:
        after = capture_campaign_snapshot(campaign_dir)
    except Exception as exc:
        raise StoryError("CAMPAIGN_SNAPSHOT_CHANGED", "Campaign changed during Story operation") from exc
    if before.comparable() == after.comparable():
        return
    if compare_request_prefix(
        before,
        after,
        event_seq=request.event_seq_start,
        recorded_decision_index=request.recorded_decision_index,
    ):
        return
    raise StoryError("CAMPAIGN_INTEGRITY_MISMATCH", "request-bound Campaign history changed")


class StoryService:
    """One-shot Story facade; every operation receives a Campaign locator."""

    def __init__(self, story_dir: str | Path) -> None:
        try:
            self.story_dir = lexical_absolute(story_dir)
        except (TypeError, ValueError) as exc:
            raise _invalid("story_dir is invalid") from exc

    @classmethod
    def init(
        cls,
        story_dir: str | Path,
        *,
        campaign_dir: str | Path,
        story_id: str,
        initial_narration_locale: str,
        initial_voice_id: str,
    ) -> dict[str, Any]:
        try:
            story_target = lexical_absolute(story_dir)
            campaign = require_actual_directory(campaign_dir, allow_missing=False)
            if path_overlaps(story_target, campaign):
                raise _invalid("Story and Campaign directories overlap")
            parent = require_actual_directory(story_target.parent, allow_missing=False)
        except StoryError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise _invalid("Story and Campaign directories are invalid or overlap") from exc
        if os.path.lexists(story_target):
            try:
                target_stat = os.lstat(story_target)
            except OSError as exc:
                raise _invalid("Story target cannot be inspected") from exc
            if not is_actual_directory(target_stat):
                raise _invalid("Story target is not an actual directory")
            raise StoryError("STORY_ALREADY_EXISTS", "Story target already exists")
        try:
            validate_stable_id(story_id, "story_id")
            if initial_narration_locale not in {"zh-CN", "en", "ar"}:
                raise ValueError("unsupported locale")
            validate_stable_id(initial_voice_id, "initial_voice_id")
        except Exception as exc:
            raise _invalid("Story initialization input is invalid") from exc
        _validate_voice(initial_voice_id)
        try:
            campaign_manifest, snapshot = verify_and_capture_campaign(campaign)
        except CampaignError as exc:
            raise _map_campaign_error(exc) from exc
        except Exception as exc:
            raise _campaign_integrity("candidate Campaign cannot be verified") from exc
        try:
            after = capture_campaign_snapshot(campaign)
        except Exception as exc:
            raise StoryError("CAMPAIGN_SNAPSHOT_CHANGED", "Campaign changed during Story initialization") from exc
        if snapshot.comparable() != after.comparable():
            raise StoryError("CAMPAIGN_SNAPSHOT_CHANGED", "Campaign changed during Story initialization")
        manifest = StoryManifest(
            schema_version=1,
            story_format_id="phase9c-story-v1",
            story_id=story_id,
            campaign_id=campaign_manifest.campaign_id,
            campaign_manifest_hash=snapshot.campaign_manifest_hash,
            worldpack_hash=campaign_manifest.worldpack_hash,
            source_initial_state_hash=campaign_manifest.source_initial_state_hash,
            player_projection_hash=campaign_manifest.player_projection_hash,
            session_id=campaign_manifest.session_id,
            initial_narration_locale=initial_narration_locale,
            initial_voice_id=initial_voice_id,
        )
        parent_binding: BoundPublicationDirectory | None = None
        try:
            parent_binding = BoundPublicationDirectory.bind(parent)
            # Checkpoint 1: bind and verify the caller-visible Story parent
            # before creating any owned temporary.
            parent_binding.checkpoint()
            temporary = parent_binding.create_temp_directory(story_target.name)
            # Checkpoint 2: the temporary Story root is now owned by the
            # anchored parent before any final publication attempt.
            parent_binding.checkpoint()
            (temporary / "requests").mkdir()
            (temporary / "turns").mkdir()
            _write_owned_file(temporary / "story.json", canonical_bytes(manifest.to_dict()))
            load_story_view(temporary)
            # _publish_directory performs checkpoint 3 and the anchored
            # no-replace publication.  The temporary is owned by the binding.
            _publish_directory(temporary, story_target, parent_binding=parent_binding)
            return {
                "ok": True,
                "story": manifest.to_dict(),
                "request_count": 0,
                "committed_turn_count": 0,
                "novel_status": "ABSENT",
            }
        except StoryError:
            raise
        except Exception as exc:
            raise StoryError("STORY_PUBLICATION_UNAVAILABLE", "Story initialization failed") from exc
        finally:
            if parent_binding is not None:
                cleanup_error: PublicationRuntime | None = None
                try:
                    if parent_binding.temp_name is not None:
                        parent_binding.cleanup_temp()
                except PublicationRuntime as exc:
                    cleanup_error = exc
                finally:
                    parent_binding.close_safely()
                if cleanup_error is not None:
                    raise StoryError(
                        "STORY_PUBLICATION_UNAVAILABLE",
                        "Story temporary cleanup is unavailable",
                    ) from cleanup_error

    def _bound_history(self, campaign_dir: str | Path) -> tuple[StoryView, CampaignManifest, CampaignSnapshot, CampaignHistory]:
        view, _campaign_manifest, snapshot = _load_story_and_bound(self.story_dir, campaign_dir)
        campaign_manifest, stable_snapshot, history = _stable_history(view, campaign_dir, snapshot)
        _validate_existing_artifacts(view, history)
        _assert_story_read_only(view)
        return view, campaign_manifest, stable_snapshot, history

    def prepare(
        self,
        *,
        campaign_dir: str | Path,
        turn_id: str | None = None,
        narration_locale: str | None = None,
    ) -> dict[str, Any]:
        view, campaign_manifest, snapshot, history = self._bound_history(campaign_dir)
        if narration_locale is not None and narration_locale != view.manifest.initial_narration_locale:
            raise _invalid("Phase 9C1 Story locale is fixed")
        request_map = view.request_map
        turn_map = view.turn_map
        requested_number = _parse_turn_id(turn_id) if turn_id is not None else None

        # An explicit existing request is always readable, even when a later
        # request is pending.  Requests and committed turns are immutable.
        if requested_number is not None and requested_number in request_map:
            _require_complete_snapshot_unchanged(campaign_dir, snapshot)
            return {
                "ok": True,
                "request": request_map[requested_number].to_dict(),
                "committed": requested_number in turn_map,
                "status": _derived_status(view, history),
            }

        pending_numbers = [number for number in sorted(request_map) if number not in turn_map]
        if pending_numbers:
            number = pending_numbers[0]
            if requested_number is not None and requested_number != number:
                raise StoryError("NARRATION_REQUEST_NOT_FOUND", "requested turn is not the current pending request")
            _require_complete_snapshot_unchanged(campaign_dir, snapshot)
            return {
                "ok": True,
                "request": request_map[number].to_dict(),
                "committed": False,
                "status": _derived_status(view, history),
            }
        next_number = len(request_map) + 1
        if requested_number is not None:
            if requested_number != next_number or requested_number > history.accepted_decisions:
                raise StoryError("NARRATION_REQUEST_NOT_FOUND", "requested turn is not preparable")
        if next_number > history.accepted_decisions:
            _require_complete_snapshot_unchanged(campaign_dir, snapshot)
            return {"ok": True, "request": None, "status": _derived_status(view, history)}
        expected = history.action_turns[next_number - 1].request
        payload = canonical_bytes(expected.to_dict())
        # Unlike commit, prepare cannot tolerate a later Campaign append: the
        # request is derived from one complete, stable Campaign boundary.
        _require_complete_snapshot_unchanged(campaign_dir, snapshot)
        root_binding, requests_binding = _open_story_publication_bindings(view, "requests")
        try:
            _publish_request(
                view.root / "requests" / f"turn-{next_number:06d}.json",
                payload,
                parent_binding=requests_binding,
                boundary_check=_prepare_publication_guard(
                    view,
                    campaign_dir,
                    snapshot,
                    root_binding=root_binding,
                    directory_binding=requests_binding,
                ),
            )
        except StoryError as exc:
            if exc.code != "STORY_INTEGRITY_MISMATCH":
                raise
            # A competing identical prepare may have won the no-replace race.
            refreshed = load_story_view(view.root)
            existing = refreshed.request_map.get(next_number)
            if existing is not None and existing.to_dict() == expected.to_dict():
                return {"ok": True, "request": existing.to_dict(), "committed": False, "status": _derived_status(refreshed, history)}
            raise
        finally:
            requests_binding.close_safely()
            root_binding.close_safely()
        refreshed = load_story_view(view.root)
        return {"ok": True, "request": expected.to_dict(), "committed": False, "status": _derived_status(refreshed, history)}

    def commit(self, *, campaign_dir: str | Path, response: Any) -> dict[str, Any]:
        view, _campaign_manifest, snapshot = _load_story_and_bound(self.story_dir, campaign_dir)
        try:
            history = reconstruct_campaign(view.manifest, snapshot)
        except StoryError:
            raise
        except Exception as exc:
            raise _campaign_integrity("Campaign history cannot be reconstructed") from exc
        _validate_existing_artifacts(view, history)
        response_value = _response_value(response)
        if not response_value.narration_request_id.startswith(view.manifest.story_id + ":"):
            raise StoryError("NARRATION_RESPONSE_INVALID", "response request identity is invalid")
        requested_turn = response_value.narration_request_id.split(":", 1)[1]
        number = _parse_turn_id(requested_turn)
        request = view.request_map.get(number)
        if request is None:
            raise StoryError("NARRATION_REQUEST_NOT_FOUND", "narration request is not present")
        if request.narration_request_id != response_value.narration_request_id:
            raise StoryError("NARRATION_RESPONSE_INVALID", "response request identity is invalid")
        if number in view.turn_map:
            root_binding, turns_binding = _open_story_publication_bindings(view, "turns")
            try:
                root_binding.check()
                turns_binding.check()
                _commit_prefix_check(campaign_dir, snapshot, request)
                existing_payload = _validate_committed_turn_unchanged(
                    view,
                    view.turn_map[number],
                    turns_binding,
                )
                artifact = _artifact_from_response(request, response_value)
                artifact_payload = canonical_bytes(artifact.to_dict())
                if existing_payload == artifact_payload:
                    return {
                        "ok": True,
                        "result": "already_committed",
                        "error_code": "TURN_ALREADY_COMMITTED",
                        "turn": artifact.to_dict(),
                    }
            except PublicationBoundaryChanged as exc:
                raise _story_integrity("Story directory identity changed during recommit") from exc
            finally:
                turns_binding.close_safely()
                root_binding.close_safely()
            raise StoryError("TURN_CONFLICT", "turn already has a different committed artifact")
        artifact = _artifact_from_response(request, response_value)
        artifact_payload = canonical_bytes(artifact.to_dict())
        target = view.root / "turns" / f"turn-{number:06d}.json"
        _commit_prefix_check(campaign_dir, snapshot, request)
        root_binding, requests_binding = _open_story_publication_bindings(view, "requests")
        turns_binding: BoundPublicationDirectory | None = None
        try:
            # Re-read the pending request through the already anchored request
            # parent.  A caller may take time to generate a response; a
            # replacement of the request during that interval must never be
            # paired with the old response.
            try:
                _pending_request_unchanged(view, request, requests_binding)
            except PublicationBoundaryChanged as exc:
                raise _story_integrity("pending request changed during commit") from exc
            turns_binding = BoundPublicationDirectory.bind(view.root / "turns")
            result = _published_turn(
                target,
                artifact_payload,
                parent_binding=turns_binding,
                boundary_check=_commit_publication_guard(
                    view,
                    campaign_dir,
                    snapshot,
                    request,
                    root_binding,
                    requests_binding,
                    turns_binding,
                ),
            )
        finally:
            if turns_binding is not None:
                turns_binding.close_safely()
            requests_binding.close_safely()
            root_binding.close_safely()
        if result == "conflict":
            raise StoryError("TURN_CONFLICT", "turn already has a different committed artifact")
        refreshed = load_story_view(view.root)
        return {
            "ok": True,
            "result": "committed" if result == "committed" else "already_committed",
            "turn": artifact.to_dict(),
            "status": _derived_status(refreshed, history),
        }

    def status(self, *, campaign_dir: str | Path) -> dict[str, Any]:
        view, _campaign_manifest, _snapshot, history = self._bound_history(campaign_dir)
        return {"ok": True, **_derived_status(view, history)}

    def verify(self, *, campaign_dir: str | Path) -> dict[str, Any]:
        view, _campaign_manifest, _snapshot, history = self._bound_history(campaign_dir)
        status = _derived_status(view, history)
        return {
            "ok": True,
            "valid": True,
            **status,
            "verification": {
                "valid": True,
                "committed_prefix": status["committed_prefix"],
                "pending_turn_id": status["pending_turn_id"],
                "missing_narration_work": status["missing_narration_work"],
                "novel_status": "ABSENT",
                "read_only": True,
            },
        }

def init_story(
    story_dir: str | Path,
    *,
    campaign_dir: str | Path,
    story_id: str,
    initial_narration_locale: str,
    initial_voice_id: str,
) -> dict[str, Any]:
    return StoryService.init(
        story_dir,
        campaign_dir=campaign_dir,
        story_id=story_id,
        initial_narration_locale=initial_narration_locale,
        initial_voice_id=initial_voice_id,
    )


def prepare_story(
    story_dir: str | Path,
    *,
    campaign_dir: str | Path,
    turn_id: str | None = None,
    narration_locale: str | None = None,
) -> dict[str, Any]:
    return StoryService(story_dir).prepare(
        campaign_dir=campaign_dir,
        turn_id=turn_id,
        narration_locale=narration_locale,
    )


def commit_story(story_dir: str | Path, *, campaign_dir: str | Path, response: Any) -> dict[str, Any]:
    return StoryService(story_dir).commit(campaign_dir=campaign_dir, response=response)


def status_story(story_dir: str | Path, *, campaign_dir: str | Path) -> dict[str, Any]:
    return StoryService(story_dir).status(campaign_dir=campaign_dir)


def verify_story(story_dir: str | Path, *, campaign_dir: str | Path) -> dict[str, Any]:
    return StoryService(story_dir).verify(campaign_dir=campaign_dir)


__all__ = [
    "StoryService",
    "commit_story",
    "init_story",
    "prepare_story",
    "status_story",
    "verify_story",
]
