from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import tgn.play.service as play_service_module
from tgn.campaign import choose_campaign, next_campaign, verify_campaign
from tgn.story import StoryError, init_story, prepare_story, status_story, verify_story
from tgn.story.common import canonical_bytes

from tgn.play import PlayError, PlayService

from .conftest import (
    create_campaign_for_context,
    narrator_argv,
    response_for,
    write_narrator,
    write_response,
)


def _manual_new(context: dict[str, Path], *, input_values: list[str], output: list[str] | None = None) -> PlayService:
    output = output if output is not None else []
    service = PlayService(context["workspace"])
    service.new(
        world_bundle_dir=context["world"],
        projection_bundle_dir=context["projection"],
        campaign_id="campaign-001",
        story_id="story-001",
        actor_id="player",
        max_decisions=20,
        locale="zh-CN",
        voice_id="cablecar_survival",
        input_fn=iter(input_values).__next__,
        output_fn=output.append,
    )
    return service


class _ScriptedActions:
    def __init__(self, campaign: Path, values: list[str]) -> None:
        self.campaign = campaign
        self.values = iter(values)

    def __call__(self) -> str:
        value = next(self.values)
        if value.startswith(":locale ") or value == "STOP":
            return value
        current = next_campaign(self.campaign)
        choices = current["canonical_request"]["choices"]
        for index, choice in enumerate(choices, start=1):
            if choice["action_type"] == value:
                return str(index)
        raise AssertionError(f"action {value} is not currently offered")


def _snapshot_tree(root: Path) -> dict[str, tuple[bytes, int, int]]:
    result: dict[str, tuple[bytes, int, int]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        value = path.stat()
        result[path.relative_to(root).as_posix()] = (path.read_bytes(), value.st_size, value.st_mtime_ns)
    return result


def _accept_actions(campaign: Path, action_types: list[str]) -> None:
    for action_type in action_types:
        current = next_campaign(campaign)
        request = current["canonical_request"]
        choice = next(choice for choice in request["choices"] if choice["action_type"] == action_type)
        choose_campaign(
            campaign,
            request_fingerprint=request["request_fingerprint"],
            choice_id=choice["choice_id"],
        )


def test_resume_drains_multiple_missing_story_turns_before_input(play_context, monkeypatch: pytest.MonkeyPatch) -> None:
    context = play_context
    campaign = create_campaign_for_context(context)
    _accept_actions(campaign, ["DROP", "SEARCH", "EXTRACT"])
    story = context["workspace"] / "story"
    init_story(story, campaign_dir=campaign, story_id="story-001", initial_narration_locale="zh-CN", initial_voice_id="cablecar_survival")
    narrator = write_narrator(context["root"] / "backlog_narrator.py")
    original_next = play_service_module.next_campaign

    def tracked_next(path: Path):
        # A next() call is legal only after all three historical turns have
        # been committed; the drain path deliberately uses status_campaign.
        assert len(list((story / "turns").glob("*.json"))) == 3
        return original_next(path)

    monkeypatch.setattr(play_service_module, "next_campaign", tracked_next)
    result = PlayService(context["workspace"]).resume(
        narrator_argv=narrator_argv(narrator),
        input_fn=iter(["STOP"]).__next__,
        output_fn=lambda _value: None,
    )
    assert result["terminal"] is True
    assert [item.name for item in sorted((story / "turns").glob("*.json"))] == [
        "turn-000001.json",
        "turn-000002.json",
        "turn-000003.json",
    ]


def test_resume_drains_terminal_max_decisions_without_input(play_context) -> None:
    context = play_context
    campaign = context["workspace"] / "campaign"
    context["workspace"].mkdir(parents=True, exist_ok=True)
    from tgn.campaign import create_campaign

    create_campaign(
        campaign,
        world_bundle_dir=context["world"],
        projection_bundle_dir=context["projection"],
        campaign_id="campaign-001",
        actor_id="player",
        max_decisions=2,
    )
    _accept_actions(campaign, ["DROP", "SEARCH"])
    story = context["workspace"] / "story"
    init_story(story, campaign_dir=campaign, story_id="story-001", initial_narration_locale="en", initial_voice_id="cablecar_survival")
    narrator = write_narrator(context["root"] / "max_narrator.py")

    def unexpected_input() -> str:
        raise AssertionError("terminal backlog must be drained before input")

    result = PlayService(context["workspace"]).resume(
        narrator_argv=narrator_argv(narrator),
        input_fn=unexpected_input,
        output_fn=lambda _value: None,
    )
    assert result["terminal"] is True
    assert result["export"]["novel_status"] == "CURRENT_FINAL"


def test_middle_backlog_narrator_failure_preserves_oldest_pending_turn(play_context) -> None:
    context = play_context
    campaign = create_campaign_for_context(context)
    _accept_actions(campaign, ["DROP", "SEARCH", "EXTRACT"])
    story = context["workspace"] / "story"
    init_story(story, campaign_dir=campaign, story_id="story-001", initial_narration_locale="zh-CN", initial_voice_id="cablecar_survival")
    narrator = write_narrator(context["root"] / "middle_failure.py", fail_on_call=3)
    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).resume(
            narrator_argv=narrator_argv(narrator),
            input_fn=lambda: (_ for _ in ()).throw(AssertionError("input called before backlog drain")),
            output_fn=lambda _value: None,
        )
    assert error.value.code == "PLAY_NARRATOR_FAILED"
    pending_bytes = (story / "requests" / "turn-000003.json").read_bytes()
    assert status_story(story, campaign_dir=campaign)["pending_turn_id"] == "turn-000003"
    resumed = PlayService(context["workspace"]).resume(
        narrator_argv=narrator_argv(narrator),
        input_fn=iter(["STOP"]).__next__,
        output_fn=lambda _value: None,
    )
    assert resumed["terminal"] is True
    assert (story / "requests" / "turn-000003.json").read_bytes() == pending_bytes


def test_complete_playable_proof_with_real_campaign_story_and_local_narrator(play_context) -> None:
    context = play_context
    narrator = write_narrator(context["root"] / "fake_narrator.py", fail_on_call=2)
    argv = narrator_argv(narrator)
    first_output: list[str] = []
    with pytest.raises(PlayError) as first_error:
        PlayService(context["workspace"]).new(
            world_bundle_dir=context["world"],
            projection_bundle_dir=context["projection"],
            campaign_id="campaign-001",
            story_id="story-001",
            actor_id="player",
            max_decisions=20,
            locale="zh-CN",
            voice_id="cablecar_survival",
            narrator_argv=argv,
            input_fn=_ScriptedActions(context["workspace"] / "campaign", ["DROP", "SEARCH"]),
            output_fn=first_output.append,
        )
    assert first_error.value.code == "PLAY_NARRATOR_FAILED"

    campaign = context["workspace"] / "campaign"
    story = context["workspace"] / "story"
    # DROP was narrated successfully; SEARCH is the exact pending request after
    # the second narrator call fails. This is the close/reopen boundary.
    assert verify_campaign(campaign)["session"]["accepted_decisions"] == 2
    pending = prepare_story(story, campaign_dir=campaign)["request"]
    assert pending["narration_locale"] == "zh-CN"
    assert pending["turn_id"] == "turn-000002"
    pending_bytes = (story / "requests" / "turn-000002.json").read_bytes()
    drop_turn_bytes = (story / "turns" / "turn-000001.json").read_bytes()
    assert status_story(story, campaign_dir=campaign)["pending_turn_id"] == "turn-000002"

    resume_output: list[str] = []
    resumed = PlayService(context["workspace"]).resume(
        narrator_argv=argv,
        input_fn=_ScriptedActions(campaign, [":locale ar", "EXTRACT", "TALK_TO_ACTOR", "STOP"]),
        output_fn=resume_output.append,
    )
    assert resumed["terminal"] is True
    assert resumed["export"]["novel_status"] == "CURRENT_FINAL"
    assert len(list((story / "turns").glob("*.json"))) == 4
    assert len(list((story / "requests").glob("*.json"))) == 4
    assert (story / "requests" / "turn-000002.json").read_bytes() == pending_bytes
    assert (story / "turns" / "turn-000001.json").read_bytes() == drop_turn_bytes
    requests = [
        json.loads((story / "requests" / f"turn-{index:06d}.json").read_bytes())
        for index in range(1, 5)
    ]
    assert [request["narration_locale"] for request in requests] == ["zh-CN", "zh-CN", "ar", "zh-CN"]
    assert (context["root"] / "fake_narrator.marker").read_text(encoding="utf-8") == "5"

    final_bytes = (story / "novel.md").read_bytes()
    assert "中文后果".encode("utf-8") in final_bytes
    assert "ظهرت نتيجة".encode("utf-8") in final_bytes
    assert b"private_goal" not in final_bytes
    assert b"World Truth" not in final_bytes
    assert verify_campaign(campaign)["verification"]["event_replay"] is True
    assert verify_story(story, campaign_dir=campaign)["valid"] is True
    status_before = PlayService(context["workspace"]).status()
    status_after = PlayService(context["workspace"]).status()
    assert status_before == status_after

    (story / "novel.md").unlink()
    rebuilt = PlayService(context["workspace"]).export(mode="final")
    assert rebuilt["novel_status"] == "CURRENT_FINAL"
    assert (story / "novel.md").read_bytes() == final_bytes
    records = json.loads((campaign / "session" / "recorded_decisions.json").read_text(encoding="utf-8"))["decisions"]
    assert [record["outcome"] for record in records] == ["ACTION"] * 4 + ["STOP"]


def test_manual_mode_persists_engine_before_pending_and_prints_after_commit(play_context) -> None:
    context = play_context
    output: list[str] = []
    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).new(
            world_bundle_dir=context["world"],
            projection_bundle_dir=context["projection"],
            campaign_id="campaign-001",
            story_id="story-001",
            actor_id="player",
            max_decisions=20,
            locale="zh-CN",
            voice_id="cablecar_survival",
            input_fn=iter(["2"]).__next__,
            output_fn=output.append,
        )
    assert error.value.code == "PLAY_NARRATION_PENDING"
    campaign = context["workspace"] / "campaign"
    story = context["workspace"] / "story"
    assert verify_campaign(campaign)["session"]["accepted_decisions"] == 1
    request = prepare_story(story, campaign_dir=campaign)["request"]
    assert any(request["narration_request_id"] in item for item in output)
    assert any("--- NARRATION REQUEST BEGIN ---" in item for item in output)
    assert any("outside the workspace" in item for item in output)
    assert any("tgn.play narrate" in item and "--response-file <response.json>" not in item for item in output)
    assert not any("public consequence" in item for item in output)

    response_path = write_response(context["root"] / "response.json", request, prose="committed prose")
    prose_output: list[str] = []
    committed = PlayService(context["workspace"]).narrate(response_file=response_path, output_fn=prose_output.append)
    assert committed["result"] == "committed"
    assert prose_output == ["committed prose"]
    assert status_story(story, campaign_dir=campaign)["committed_prefix"] == 1

    resumed = PlayService(context["workspace"]).resume(input_fn=iter(["STOP"]).__next__, output_fn=output.append)
    assert resumed["export"]["novel_status"] == "CURRENT_FINAL"


def test_external_narrator_failure_preserves_exact_pending_request(play_context) -> None:
    context = play_context
    narrator = write_narrator(context["root"] / "failing_once.py", fail_first=True)
    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).new(
            world_bundle_dir=context["world"],
            projection_bundle_dir=context["projection"],
            campaign_id="campaign-001",
            story_id="story-001",
            actor_id="player",
            max_decisions=20,
            locale="zh-CN",
            voice_id="cablecar_survival",
            narrator_argv=narrator_argv(narrator),
            input_fn=_ScriptedActions(context["workspace"] / "campaign", ["DROP"]),
            output_fn=lambda _value: None,
        )
    assert error.value.code == "PLAY_NARRATOR_FAILED"
    campaign = context["workspace"] / "campaign"
    story = context["workspace"] / "story"
    request_before = prepare_story(story, campaign_dir=campaign)["request"]
    request_bytes = (story / "requests" / "turn-000001.json").read_bytes()
    resumed = PlayService(context["workspace"]).resume(
        narrator_argv=narrator_argv(narrator),
        input_fn=iter(["STOP"]).__next__,
        output_fn=lambda _value: None,
    )
    assert resumed["terminal"] is True
    assert (story / "requests" / "turn-000001.json").read_bytes() == request_bytes
    assert request_before["narration_request_id"] == "story-001:turn-000001"
    assert json.loads(request_bytes) == request_before


def test_invalid_combined_input_does_not_call_campaign_or_mutate_story(play_context) -> None:
    context = play_context
    values = iter(["1,2"])

    def input_fn() -> str:
        try:
            return next(values)
        except StopIteration as exc:
            raise EOFError from exc

    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).new(
            world_bundle_dir=context["world"],
            projection_bundle_dir=context["projection"],
            campaign_id="campaign-001",
            story_id="story-001",
            actor_id="player",
            max_decisions=20,
            locale="zh-CN",
            voice_id="cablecar_survival",
            input_fn=input_fn,
            output_fn=lambda _value: None,
        )
    assert error.value.code == "INVALID_PLAY_INPUT"
    campaign = context["workspace"] / "campaign"
    story = context["workspace"] / "story"
    assert verify_campaign(campaign)["session"]["accepted_decisions"] == 0
    assert not list((story / "requests").glob("*.json"))
    assert not list((story / "turns").glob("*.json"))


def test_presentation_mismatch_fails_before_choice(monkeypatch: pytest.MonkeyPatch, play_context) -> None:
    context = play_context
    original = play_service_module.next_campaign

    def mismatched(campaign: Path) -> dict[str, Any]:
        value = original(campaign)
        value["player_presentation"]["choices"][1]["duration_minutes"] += 1
        return value

    monkeypatch.setattr(play_service_module, "next_campaign", mismatched)
    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).new(
            world_bundle_dir=context["world"],
            projection_bundle_dir=context["projection"],
            campaign_id="campaign-001",
            story_id="story-001",
            actor_id="player",
            max_decisions=20,
            locale="zh-CN",
            voice_id="cablecar_survival",
            input_fn=iter(["2"]).__next__,
            output_fn=lambda _value: None,
        )
    assert error.value.code == "PLAY_CLIENT_INTEGRITY_MISMATCH"
    assert verify_campaign(context["workspace"] / "campaign")["session"]["accepted_decisions"] == 0


def test_resume_can_initialize_only_the_missing_story(play_context) -> None:
    context = play_context
    campaign = create_campaign_for_context(context)
    result = PlayService(context["workspace"]).resume(
        locale="zh-CN",
        story_id="story-001",
        input_fn=iter(["STOP"]).__next__,
        output_fn=lambda _value: None,
    )
    assert result["terminal"] is True
    assert (context["workspace"] / "story" / "story.json").exists()
    assert verify_campaign(campaign)["session"]["status"] == "STOPPED"


def test_status_and_verify_are_read_only(play_context) -> None:
    context = play_context
    campaign = create_campaign_for_context(context)
    story = context["workspace"] / "story"
    init_story(
        story,
        campaign_dir=campaign,
        story_id="story-001",
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    before = {"campaign": _snapshot_tree(campaign), "story": _snapshot_tree(story)}
    status = PlayService(context["workspace"]).status()
    verified = PlayService(context["workspace"]).verify()
    after = {"campaign": _snapshot_tree(campaign), "story": _snapshot_tree(story)}
    assert status["pending_narration"] is False
    assert verified["valid"] is True
    assert before == after


def test_narrate_without_existing_pending_request_fails_closed(play_context) -> None:
    context = play_context
    _manual_new(context, input_values=["STOP"], output=[])
    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).narrate(
            response_file=context["root"] / "missing-response.json",
            output_fn=lambda _value: None,
        )
    assert error.value.code == "INVALID_PLAY_INPUT"


def test_relative_workspace_is_lexically_fixed_and_response_must_be_external(play_context, monkeypatch: pytest.MonkeyPatch) -> None:
    context = play_context
    campaign = create_campaign_for_context(context)
    story = context["workspace"] / "story"
    init_story(story, campaign_dir=campaign, story_id="story-001", initial_narration_locale="en", initial_voice_id="cablecar_survival")
    monkeypatch.chdir(context["root"])
    service = PlayService(Path("play"))
    other = context["root"] / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    assert service.status()["ok"] is True
    with pytest.raises(PlayError) as error:
        service.narrate(response_file=context["workspace"] / "response.json", output_fn=lambda _value: None)
    assert error.value.code == "INVALID_PLAY_INPUT"


def test_commit_failure_prints_no_prose_and_preserves_pending(play_context, monkeypatch: pytest.MonkeyPatch) -> None:
    context = play_context
    with pytest.raises(PlayError):
        _manual_new(context, input_values=["2"], output=[])
    campaign = context["workspace"] / "campaign"
    story = context["workspace"] / "story"
    request = prepare_story(story, campaign_dir=campaign)["request"]
    response_path = write_response(context["root"] / "outside-response.json", request, prose="must not print")
    monkeypatch.setattr(
        play_service_module,
        "commit_story",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(StoryError("STORY_PUBLICATION_UNAVAILABLE", "injected")),
    )
    output: list[str] = []
    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).narrate(response_file=response_path, output_fn=output.append)
    assert error.value.code == "PLAY_STORY_FAILED"
    assert output == []
    assert status_story(story, campaign_dir=campaign)["pending_turn_id"] == "turn-000001"
    assert not list((story / "turns").glob("*.json"))


def test_terminal_renderer_escapes_raw_prose_but_story_keeps_exact_bytes(play_context) -> None:
    context = play_context
    with pytest.raises(PlayError):
        _manual_new(context, input_values=["2"], output=[])
    campaign = context["workspace"] / "campaign"
    story = context["workspace"] / "story"
    request = prepare_story(story, campaign_dir=campaign)["request"]
    raw_prose = "\x1b[31m公开后果\n中文\x1b[0m"
    response_path = write_response(context["root"] / "control-response.json", request, prose=raw_prose)
    output: list[str] = []
    PlayService(context["workspace"]).narrate(response_file=response_path, output_fn=output.append)
    assert all("\x1b" not in item for item in output)
    stored = json.loads((story / "turns" / "turn-000001.json").read_bytes())
    assert stored["prose"] == raw_prose
