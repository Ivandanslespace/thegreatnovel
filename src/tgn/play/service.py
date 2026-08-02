"""Thin orchestration for the PC1 local playable loop."""

from __future__ import annotations

import re
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
    PlayError,
    SUPPORTED_LOCALES,
    ensure_new_workspace,
    require_workspace,
    workspace_children,
)
from .narrator_process import DEFAULT_NARRATOR_TIMEOUT, run_narrator, validate_timeout


DEFAULT_VOICE_ID = "cablecar_survival"
_POSITIVE_INPUT = re.compile(r"[1-9][0-9]*\Z")
_CHOICE_FIELDS = ("choice_id", "action_type", "params", "duration_minutes", "stamina_cost")
InputFunction = Callable[[], str]
OutputFunction = Callable[[str], None]


def _map_boundary_error(error: Exception, *, operation: str) -> PlayError:
    if isinstance(error, PlayError):
        return error
    if isinstance(error, CampaignError):
        return PlayError("PLAY_CAMPAIGN_FAILED", f"Campaign {operation} failed", cause_code=error.code)
    if isinstance(error, StoryError):
        return PlayError("PLAY_STORY_FAILED", f"Story {operation} failed", cause_code=error.code)
    return PlayError("PLAY_STORY_FAILED", f"Playable Client {operation} failed")


def _present_directory(path: Path) -> bool:
    try:
        import os
        import stat

        value = os.lstat(path)
        reparse = bool(getattr(value, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400))
        return stat.S_ISDIR(value.st_mode) and not stat.S_ISLNK(value.st_mode) and not reparse
    except (FileNotFoundError, OSError):
        return False


def _validate_request_pair(campaign_value: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    request = campaign_value.get("canonical_request")
    presentation = campaign_value.get("player_presentation")
    if (request is None) != (presentation is None):
        raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "Campaign request and presentation are not paired")
    if request is None:
        return None, None
    if not isinstance(request, dict) or not isinstance(presentation, dict):
        raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "Campaign request and presentation are invalid")
    if request.get("request_fingerprint") != presentation.get("request_fingerprint"):
        raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "Campaign request and presentation fingerprints differ")
    canonical_choices = request.get("choices")
    presented_choices = presentation.get("choices")
    if not isinstance(canonical_choices, list) or not isinstance(presented_choices, list):
        raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "Campaign choice lists are invalid")
    if len(canonical_choices) != len(presented_choices):
        raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "Campaign choice counts differ")
    for canonical_choice, presented_choice in zip(canonical_choices, presented_choices):
        if not isinstance(canonical_choice, dict) or not isinstance(presented_choice, dict):
            raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "Campaign choice is invalid")
        for field in _CHOICE_FIELDS:
            if canonical_choice.get(field) != presented_choice.get(field):
                raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "Campaign choice authority differs from presentation")
    return request, presentation


def _render_presentation(presentation: dict[str, Any], output: OutputFunction) -> None:
    output("当前玩家可见状态：")
    output(canonical_json(presentation))
    output("可选行动：")
    for index, choice in enumerate(presentation.get("choices", []), start=1):
        action_type = choice.get("action_type", "UNKNOWN")
        display_params = choice.get("display_params")
        suffix = f" {canonical_json(display_params)}" if display_params else ""
        output(f"{index}. {action_type}{suffix}")
    output("输入选项编号、STOP，或 :locale zh-CN / :locale en / :locale ar")


class PlayService:
    """One workspace-bound facade over public Campaign and Story functions."""

    def __init__(self, workspace: str | Path) -> None:
        try:
            self.workspace = Path(workspace)
        except (TypeError, ValueError) as exc:
            raise PlayError("INVALID_PLAY_INPUT", "workspace path is invalid") from exc

    def _layout(self, *, existing: bool) -> tuple[Path, Path]:
        workspace = require_workspace(self.workspace) if existing else ensure_new_workspace(self.workspace)
        return workspace_children(workspace)

    @staticmethod
    def _call_campaign(function: Callable[..., dict[str, Any]], *args: Any, operation: str, **kwargs: Any) -> dict[str, Any]:
        try:
            result = function(*args, **kwargs)
        except Exception as exc:
            raise _map_boundary_error(exc, operation=operation) from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise PlayError("PLAY_CAMPAIGN_FAILED", f"Campaign {operation} returned an invalid result")
        return result

    @staticmethod
    def _call_story(function: Callable[..., dict[str, Any]], *args: Any, operation: str, **kwargs: Any) -> dict[str, Any]:
        try:
            result = function(*args, **kwargs)
        except Exception as exc:
            raise _map_boundary_error(exc, operation=operation) from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise PlayError("PLAY_STORY_FAILED", f"Story {operation} returned an invalid result")
        return result

    def _verify_pair(self, campaign_dir: Path, story_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        if not _present_directory(campaign_dir) or not _present_directory(story_dir):
            raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace requires campaign and story directories")
        campaign = self._call_campaign(verify_campaign, campaign_dir, operation="verification")
        story = self._call_story(verify_story, story_dir, campaign_dir=campaign_dir, operation="verification")
        return campaign, story

    def _compose_status(self, campaign: dict[str, Any], story: dict[str, Any]) -> dict[str, Any]:
        session = campaign.get("session")
        if not isinstance(session, dict):
            raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "Campaign status has no public session summary")
        readiness = story.get("export_readiness", {})
        if not isinstance(readiness, dict):
            raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "Story status has no export readiness")
        return {
            "ok": True,
            "campaign_status": {
                "campaign": campaign.get("campaign"),
                "session": session,
            },
            "story_status": story,
            "terminal": session.get("status") in {"STOPPED", "TERMINAL"},
            "pending_narration": story.get("pending_turn_id") is not None,
            "missing_narration_work": bool(story.get("missing_narration_work")),
            "snapshot_ready": bool(readiness.get("current_snapshot_ready")),
            "final_ready": bool(readiness.get("final_ready")),
            "novel_status": story.get("novel_status"),
        }

    def status(self) -> dict[str, Any]:
        campaign_dir, story_dir = self._layout(existing=True)
        if not _present_directory(campaign_dir) or not _present_directory(story_dir):
            raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace requires campaign and story directories")
        campaign = self._call_campaign(status_campaign, campaign_dir, operation="status")
        story = self._call_story(status_story, story_dir, campaign_dir=campaign_dir, operation="status")
        return self._compose_status(campaign, story)

    def verify(self) -> dict[str, Any]:
        campaign_dir, story_dir = self._layout(existing=True)
        campaign, story = self._verify_pair(campaign_dir, story_dir)
        return {
            "ok": True,
            "valid": True,
            "campaign_verification": campaign.get("verification"),
            "story_verification": story.get("verification"),
            **self._compose_status(campaign, story),
        }

    def export(self, *, mode: str, accepted_decisions: int | None = None) -> dict[str, Any]:
        campaign_dir, story_dir = self._layout(existing=True)
        if not _present_directory(campaign_dir) or not _present_directory(story_dir):
            raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace requires campaign and story directories")
        return self._call_story(
            export_story,
            story_dir,
            campaign_dir=campaign_dir,
            mode=mode,
            accepted_decisions=accepted_decisions,
            operation="export",
        )

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
        if locale not in SUPPORTED_LOCALES:
            raise PlayError("INVALID_PLAY_INPUT", "locale is unsupported")
        narrator_timeout = validate_timeout(narrator_timeout)
        if not isinstance(max_decisions, int) or isinstance(max_decisions, bool) or max_decisions <= 0:
            raise PlayError("INVALID_PLAY_INPUT", "max_decisions must be a positive integer")
        campaign_dir, story_dir = self._layout(existing=False)
        campaign = self._call_campaign(
            create_campaign,
            campaign_dir,
            world_bundle_dir=world_bundle_dir,
            projection_bundle_dir=projection_bundle_dir,
            campaign_id=campaign_id,
            actor_id=actor_id,
            max_decisions=max_decisions,
            operation="creation",
        )
        try:
            self._call_story(
                init_story,
                story_dir,
                campaign_dir=campaign_dir,
                story_id=story_id,
                initial_narration_locale=locale,
                initial_voice_id=voice_id,
                operation="initialization",
            )
        except PlayError:
            # Campaign is authoritative and must remain available for resume.
            raise
        self._verify_pair(campaign_dir, story_dir)
        return self._loop(
            campaign_dir,
            story_dir,
            locale=locale,
            narrator_argv=narrator_argv,
            narrator_timeout=narrator_timeout,
            input_fn=input_fn,
            output_fn=output_fn,
        )

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
        if locale is not None and locale not in SUPPORTED_LOCALES:
            raise PlayError("INVALID_PLAY_INPUT", "locale is unsupported")
        narrator_timeout = validate_timeout(narrator_timeout)
        campaign_dir, story_dir = self._layout(existing=True)
        if not _present_directory(campaign_dir):
            raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace has no Campaign")
        self._call_campaign(verify_campaign, campaign_dir, operation="verification")
        if not _present_directory(story_dir):
            if story_id is None or locale is None:
                raise PlayError(
                    "PLAY_WORKSPACE_INCOMPLETE",
                    "missing Story requires story_id and locale for safe initialization",
                )
            self._call_story(
                init_story,
                story_dir,
                campaign_dir=campaign_dir,
                story_id=story_id,
                initial_narration_locale=locale,
                initial_voice_id=voice_id,
                operation="recovery initialization",
            )
        self._verify_pair(campaign_dir, story_dir)
        return self._loop(
            campaign_dir,
            story_dir,
            locale=locale,
            narrator_argv=narrator_argv,
            narrator_timeout=narrator_timeout,
            input_fn=input_fn,
            output_fn=output_fn,
        )

    def narrate(self, *, response_file: str | Path, output_fn: OutputFunction = print) -> dict[str, Any]:
        from .common import read_external_json

        campaign_dir, story_dir = self._layout(existing=True)
        self._verify_pair(campaign_dir, story_dir)
        status_value = self._call_story(
            status_story,
            story_dir,
            campaign_dir=campaign_dir,
            operation="pending status",
        )
        if status_value.get("pending_turn_id") is None:
            raise PlayError("PLAY_NARRATION_PENDING", "there is no existing pending narration request")
        prepared = self._call_story(
            prepare_story,
            story_dir,
            campaign_dir=campaign_dir,
            operation="pending request lookup",
        )
        request = prepared.get("request")
        if not isinstance(request, dict) or prepared.get("committed") is True:
            raise PlayError("PLAY_NARRATION_PENDING", "there is no pending narration request")
        response = read_external_json(response_file)
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
        committed = self._call_story(
            commit_story,
            story_dir,
            campaign_dir=campaign_dir,
            response=response,
            operation="narration commit",
        )
        turn = committed.get("turn")
        if not isinstance(turn, dict) or not isinstance(turn.get("prose"), str):
            raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "committed turn has no public prose")
        output_fn(turn["prose"])
        return committed

    def _complete_pending(
        self,
        campaign_dir: Path,
        story_dir: Path,
        *,
        narrator_argv: Sequence[str] | None,
        narrator_timeout: float,
        output_fn: OutputFunction,
        narration_locale: str | None = None,
    ) -> bool:
        prepared = self._call_story(
            prepare_story,
            story_dir,
            campaign_dir=campaign_dir,
            narration_locale=narration_locale,
            operation="narration preparation",
        )
        request = prepared.get("request")
        if not isinstance(request, dict) or prepared.get("committed") is True:
            return False
        if narrator_argv is None:
            output_fn(canonical_json(request))
            raise PlayError("PLAY_NARRATION_PENDING", "narration response is required before another action")
        response = run_narrator(narrator_argv, request, timeout=narrator_timeout)
        self._commit_response(campaign_dir, story_dir, response, output_fn=output_fn)
        return True

    def _loop(
        self,
        campaign_dir: Path,
        story_dir: Path,
        *,
        locale: str | None,
        narrator_argv: Sequence[str] | None,
        narrator_timeout: float,
        input_fn: InputFunction,
        output_fn: OutputFunction,
    ) -> dict[str, Any]:
        active_locale = locale
        while True:
            self._complete_pending(
                campaign_dir,
                story_dir,
                narrator_argv=narrator_argv,
                narrator_timeout=narrator_timeout,
                output_fn=output_fn,
            )
            current = self._call_campaign(next_campaign, campaign_dir, operation="next")
            request, presentation = _validate_request_pair(current)
            if request is None:
                story_status_value = self._call_story(
                    status_story,
                    story_dir,
                    campaign_dir=campaign_dir,
                    operation="status",
                )
                readiness = story_status_value.get("export_readiness", {})
                if isinstance(readiness, dict) and readiness.get("final_ready"):
                    exported = self.export(mode="final")
                    output_fn("final novel exported: story/novel.md")
                    return {
                        "ok": True,
                        "terminal": True,
                        "export": exported,
                        "campaign": current.get("session"),
                        "story": story_status_value,
                    }
                return {"ok": True, "terminal": True, "campaign": current.get("session"), "story": story_status_value}
            assert presentation is not None
            while True:
                _render_presentation(presentation, output_fn)
                try:
                    raw_input = input_fn()
                except (EOFError, KeyboardInterrupt) as exc:
                    raise PlayError("INVALID_PLAY_INPUT", "player input ended") from exc
                if not isinstance(raw_input, str):
                    raise PlayError("INVALID_PLAY_INPUT", "player input is invalid")
                if raw_input in {f":locale {item}" for item in sorted(SUPPORTED_LOCALES)}:
                    active_locale = raw_input.split(" ", 1)[1]
                    output_fn(f"narration locale set for the next request: {active_locale}")
                    continue
                if raw_input == "STOP":
                    self._call_campaign(
                        stop_campaign,
                        campaign_dir,
                        request_fingerprint=request["request_fingerprint"],
                        operation="STOP",
                    )
                    break
                if _POSITIVE_INPUT.fullmatch(raw_input) is None:
                    output_fn("invalid input; choose one option number, STOP, or a locale command")
                    continue
                number = int(raw_input)
                choices = request.get("choices", [])
                if number > len(choices):
                    output_fn("invalid option number")
                    continue
                selected = choices[number - 1]
                if not isinstance(selected, dict) or not isinstance(selected.get("choice_id"), str):
                    raise PlayError("PLAY_CLIENT_INTEGRITY_MISMATCH", "canonical choice cannot be selected")
                self._call_campaign(
                    choose_campaign,
                    campaign_dir,
                    request_fingerprint=request["request_fingerprint"],
                    choice_id=selected["choice_id"],
                    operation="choice",
                )
                self._complete_pending(
                    campaign_dir,
                    story_dir,
                    narrator_argv=narrator_argv,
                    narrator_timeout=narrator_timeout,
                    output_fn=output_fn,
                    narration_locale=active_locale,
                )
                break


__all__ = ["DEFAULT_VOICE_ID", "PlayService"]
