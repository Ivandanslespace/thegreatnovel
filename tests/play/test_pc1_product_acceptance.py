from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

import tgn.play.service as service_module
from tgn.campaign import choose_campaign, next_campaign, verify_campaign
from tgn.play import PlayError, PlayService
from tgn.story import (
    NarrationRequest,
    TurnNarrationArtifact,
    commit_story,
    init_story,
    prepare_story,
    status_story,
)
from tgn.story.common import canonical_bytes

from .conftest import create_campaign_for_context, narrator_argv, response_for, write_narrator
from .test_service import _ScriptedActions


def _choose(campaign: Path, action_type: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    before = next_campaign(campaign)
    choice = next(item for item in before["canonical_request"]["choices"] if item["action_type"] == action_type)
    result = choose_campaign(
        campaign,
        request_fingerprint=before["canonical_request"]["request_fingerprint"],
        choice_id=choice["choice_id"],
    )
    after = next_campaign(campaign)
    return before, result, after


def _commit_current(campaign: Path, story: Path, prose: str) -> dict[str, Any]:
    request = prepare_story(story, campaign_dir=campaign)["request"]
    return commit_story(story, campaign_dir=campaign, response=response_for(request, prose=prose))


def _advance_to_target(campaign: Path, story: Path) -> None:
    _choose(campaign, "DROP")
    _commit_current(campaign, story, "public DROP")
    _choose(campaign, "SEARCH")
    _commit_current(campaign, story, "public SEARCH")


def test_external_failure_recovers_non_default_pending_locale_and_resets_next_request(play_context) -> None:
    context = play_context
    campaign = create_campaign_for_context(context)
    story = context["workspace"] / "story"
    init_story(
        story,
        campaign_dir=campaign,
        story_id="story-001",
        initial_narration_locale="zh-CN",
        initial_voice_id="cablecar_survival",
    )
    _advance_to_target(campaign, story)
    narrator = write_narrator(context["root"] / "fail-once.py", fail_first=True)

    with pytest.raises(PlayError) as failure:
        PlayService(context["workspace"]).resume(
            narrator_argv=narrator_argv(narrator),
            input_fn=_ScriptedActions(campaign, [":locale ar", "EXTRACT"]),
            output_fn=lambda _value: None,
        )
    assert failure.value.code == "PLAY_NARRATOR_FAILED"
    assert verify_campaign(campaign)["session"]["accepted_decisions"] == 3
    pending_path = story / "requests" / "turn-000003.json"
    pending_before = pending_path.read_bytes()
    pending = prepare_story(story, campaign_dir=campaign)["request"]
    assert pending["narration_locale"] == "ar"
    assert status_story(story, campaign_dir=campaign)["pending_turn_id"] == "turn-000003"
    assert not (story / "turns" / "turn-000003.json").exists()

    resumed = PlayService(context["workspace"]).resume(
        narrator_argv=narrator_argv(narrator),
        input_fn=_ScriptedActions(campaign, ["TALK_TO_ACTOR", "STOP"]),
        output_fn=lambda _value: None,
    )
    assert resumed["terminal"] is True
    assert pending_path.read_bytes() == pending_before
    assert json.loads((story / "requests" / "turn-000003.json").read_bytes())["narration_locale"] == "ar"
    assert json.loads((story / "turns" / "turn-000003.json").read_bytes())["narration_locale"] == "ar"
    assert json.loads((story / "requests" / "turn-000004.json").read_bytes())["narration_locale"] == "zh-CN"
    assert len(list((story / "requests").glob("*.json"))) == 4
    assert len(list((story / "turns").glob("*.json"))) == 4
    assert verify_campaign(campaign)["session"]["accepted_decisions"] == 4


def test_manual_narration_recovers_non_default_pending_locale_and_prints_after_commit(play_context) -> None:
    context = play_context
    campaign = create_campaign_for_context(context)
    story = context["workspace"] / "story"
    init_story(
        story,
        campaign_dir=campaign,
        story_id="story-001",
        initial_narration_locale="zh-CN",
        initial_voice_id="cablecar_survival",
    )
    _advance_to_target(campaign, story)
    output: list[str] = []
    with pytest.raises(PlayError) as pending_error:
        PlayService(context["workspace"]).resume(
            input_fn=_ScriptedActions(campaign, [":locale ar", "EXTRACT"]),
            output_fn=output.append,
        )
    assert pending_error.value.code == "PLAY_NARRATION_PENDING"
    request = prepare_story(story, campaign_dir=campaign)["request"]
    assert request["narration_locale"] == "ar"
    request_bytes = (story / "requests" / "turn-000003.json").read_bytes()
    response_path = context["root"] / "arabic-response.json"
    response_path.write_bytes(canonical_bytes(response_for(request, prose="نتيجة عربية عامة")))
    prose_output: list[str] = []
    result = PlayService(context["workspace"]).narrate(response_file=response_path, output_fn=prose_output.append)
    assert result["ok"] is True
    assert prose_output == ["نتيجة عربية عامة"]
    assert (story / "requests" / "turn-000003.json").read_bytes() == request_bytes
    assert json.loads((story / "turns" / "turn-000003.json").read_bytes())["narration_locale"] == "ar"

    next_output: list[str] = []
    with pytest.raises(PlayError) as next_pending:
        PlayService(context["workspace"]).resume(
            input_fn=_ScriptedActions(campaign, ["TALK_TO_ACTOR"]),
            output_fn=next_output.append,
        )
    assert next_pending.value.code == "PLAY_NARRATION_PENDING"
    next_request = prepare_story(story, campaign_dir=campaign)["request"]
    assert next_request["turn_id"] == "turn-000004"
    assert next_request["narration_locale"] == "zh-CN"


@pytest.mark.parametrize("mutation", ["manifest_ids", "session_ids", "actor", "max_decisions"])
def test_campaign_manifest_session_binding_is_checked_before_story_initialization(
    play_context, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    context = play_context
    campaign = create_campaign_for_context(context)
    original = verify_campaign(campaign)
    candidate = copy.deepcopy(original)
    if mutation == "manifest_ids":
        candidate["campaign"]["campaign_id"] = "other-campaign"
        candidate["campaign"]["session_id"] = "other-campaign"
    elif mutation == "session_ids":
        candidate["session"]["campaign_id"] = "other-campaign"
        candidate["session"]["session_id"] = "other-campaign"
    elif mutation == "actor":
        candidate["campaign"]["actor_id"] = "other-player"
    else:
        candidate["campaign"]["max_decisions"] = 21

    calls: list[str] = []
    monkeypatch.setattr(service_module, "verify_campaign", lambda *_args, **_kwargs: candidate)
    monkeypatch.setattr(service_module, "init_story", lambda *_args, **_kwargs: calls.append("init"))
    monkeypatch.setattr(service_module, "next_campaign", lambda *_args, **_kwargs: calls.append("next"))
    monkeypatch.setattr(service_module, "choose_campaign", lambda *_args, **_kwargs: calls.append("choose"))
    monkeypatch.setattr(service_module, "stop_campaign", lambda *_args, **_kwargs: calls.append("stop"))

    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).resume(
            locale="zh-CN",
            story_id="story-001",
            input_fn=iter(["STOP"]).__next__,
            output_fn=lambda _value: None,
        )
    assert error.value.code == "PLAY_CLIENT_INTEGRITY_MISMATCH"
    assert calls == []


@pytest.mark.parametrize("mutation", ["fields", "schema", "request_id", "request_hash", "locale", "claims", "prose"])
def test_external_response_invalidity_is_play_narrator_failed_and_preserves_pending(
    play_context, mutation: str
) -> None:
    context = play_context
    campaign = create_campaign_for_context(context)
    story = context["workspace"] / "story"
    init_story(story, campaign_dir=campaign, story_id="story-001", initial_narration_locale="zh-CN", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    pending_bytes = (story / "requests" / "turn-000001.json").read_bytes()
    response = response_for(request, prose="must not print")
    if mutation == "fields":
        response["unknown"] = True
    elif mutation == "schema":
        response["schema_version"] = 2
    elif mutation == "request_id":
        response["narration_request_id"] = "story-001:turn-000999"
    elif mutation == "request_hash":
        response["narration_request_hash"] = "0" * 64
    elif mutation == "locale":
        response["locale"] = "ar"
    elif mutation == "claims":
        response["claims"] = []
    else:
        response["prose"] = ""
    response_path = context["root"] / f"invalid-{mutation}.json"
    response_path.write_bytes(canonical_bytes(response))
    output: list[str] = []
    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).narrate(response_file=response_path, output_fn=output.append)
    assert error.value.code == "PLAY_NARRATOR_FAILED"
    assert output == []
    assert (story / "requests" / "turn-000001.json").read_bytes() == pending_bytes
    assert not (story / "turns" / "turn-000001.json").exists()
    assert status_story(story, campaign_dir=campaign)["pending_turn_id"] == "turn-000001"


def test_public_one_choice_one_consequence_and_time_pressure(play_context) -> None:
    context = play_context
    campaign_a = create_campaign_for_context(context, name="campaign-a", campaign_id="campaign-a")
    campaign_b = create_campaign_for_context(context, name="campaign-b", campaign_id="campaign-b")
    initial_a = next_campaign(campaign_a)
    initial_b = next_campaign(campaign_b)
    _, search_drop_a, after_a = _choose(campaign_a, "DROP")
    _, extract_drop_b, after_b = _choose(campaign_b, "DROP")
    assert search_drop_a["result"]["action_type"] == "DROP"
    assert extract_drop_b["result"]["action_type"] == "DROP"
    _, search_result, searched = _choose(campaign_a, "SEARCH")
    _, extract_result, extracted = _choose(campaign_b, "EXTRACT")
    assert search_result["result"]["action_type"] == "SEARCH"
    assert extract_result["result"]["action_type"] == "EXTRACT"
    assert verify_campaign(campaign_a)["session"]["accepted_decisions"] == 2
    assert verify_campaign(campaign_b)["session"]["accepted_decisions"] == 2
    assert searched["player_presentation"]["observation"] != extracted["player_presentation"]["observation"]
    assert initial_a["player_presentation"]["observation"]["game_minute"] == 0
    assert after_a["player_presentation"]["observation"]["game_minute"] == initial_a["canonical_request"]["choices"][1]["duration_minutes"]
    assert set(item["action_type"] for item in searched["canonical_request"]["choices"]) != set(
        item["action_type"] for item in initial_b["canonical_request"]["choices"]
    )


def test_public_growth_opportunity_cost_and_named_actor_value(play_context) -> None:
    context = play_context
    growth = create_campaign_for_context(context, name="growth", campaign_id="growth")
    for action in ("DROP", "SEARCH", "EXTRACT"):
        _choose(growth, action)
    before_upgrade = next_campaign(growth)
    _, upgrade_result, after_upgrade = _choose(growth, "UPGRADE_PLAYER")
    assert upgrade_result["result"]["action_type"] == "UPGRADE_PLAYER"
    assert after_upgrade["player_presentation"]["observation"]["progression"]["tracks"]["player"]["stage"] == 1
    assert after_upgrade["player_presentation"]["observation"] != before_upgrade["player_presentation"]["observation"]

    resource_route = create_campaign_for_context(context, name="resource-route", campaign_id="resource-route")
    relation_route = create_campaign_for_context(context, name="relation-route", campaign_id="relation-route")
    for campaign in (resource_route, relation_route):
        for action in ("DROP", "SEARCH", "EXTRACT"):
            _choose(campaign, action)
    _, resource_result, resource_after = _choose(resource_route, "UPGRADE_PLAYER")
    _, relation_result, relation_after = _choose(relation_route, "TALK_TO_ACTOR")
    assert resource_result["result"]["action_type"] == "UPGRADE_PLAYER"
    assert relation_result["result"]["action_type"] == "TALK_TO_ACTOR"
    resource_observation = resource_after["player_presentation"]["observation"]
    relation_observation = relation_after["player_presentation"]["observation"]
    assert (
        resource_observation["inventory"] != relation_observation["inventory"]
        or resource_observation["actor"]["trust"] != relation_observation["actor"]["trust"]
        or resource_after["canonical_request"]["choices"] != relation_after["canonical_request"]["choices"]
    )
    assert relation_observation["actor"]["trust"] == 1
    assert relation_observation["actor"]["facts"]
    assert "knowledge" not in relation_observation["actor"]
    assert "goal" not in relation_observation["actor"]


def test_deterministic_narrative_coherence_uses_only_public_request_material(play_context) -> None:
    context = play_context
    narrator = context["root"] / "public-scripted-narrator.py"
    narrator.write_text(
        "import json, sys\n"
        "request = json.load(sys.stdin)\n"
        "brief = request['public_brief']\n"
        "event_type = brief['action_result']['event_types'][0]\n"
        "prose = f\"turn={request['turn_id']} action={request['action_type']} public_event={event_type}\"\n"
        "response = {'schema_version': 1, 'narration_request_id': request['narration_request_id'],\n"
        "'narration_request_hash': request['narration_request_hash'], 'locale': request['narration_locale'],\n"
        "'claims': request['claim_requirements'], 'prose': prose}\n"
        "sys.stdout.write(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(',', ':')))\n",
        encoding="utf-8",
    )
    result = PlayService(context["workspace"]).new(
        world_bundle_dir=context["world"],
        projection_bundle_dir=context["projection"],
        campaign_id="campaign-001",
        story_id="story-001",
        actor_id="player",
        max_decisions=20,
        locale="zh-CN",
        voice_id="cablecar_survival",
        narrator_argv=narrator_argv(narrator),
        input_fn=_ScriptedActions(context["workspace"] / "campaign", ["DROP", "SEARCH", "STOP"]),
        output_fn=lambda _value: None,
    )
    assert result["terminal"] is True
    story = context["workspace"] / "story"
    request_one = NarrationRequest.from_dict(json.loads((story / "requests" / "turn-000001.json").read_bytes()))
    request_two = NarrationRequest.from_dict(json.loads((story / "requests" / "turn-000002.json").read_bytes()))
    turn_one = TurnNarrationArtifact.from_dict(json.loads((story / "turns" / "turn-000001.json").read_bytes()))
    turn_two = TurnNarrationArtifact.from_dict(json.loads((story / "turns" / "turn-000002.json").read_bytes()))
    for request, turn in ((request_one, turn_one), (request_two, turn_two)):
        public_event = request.public_brief["action_result"]["event_types"][0]
        assert turn.turn_id == request.turn_id
        assert turn.action_type == request.action_type
        assert f"turn={request.turn_id}" in turn.prose
        assert f"action={request.action_type}" in turn.prose
        assert f"public_event={public_event}" in turn.prose
        assert "private" not in turn.prose.lower()
        assert "world_truth" not in turn.prose.lower()
    assert request_two.public_brief["observation_before"] == request_one.public_brief["observation_after"]
    assert verify_campaign(context["workspace"] / "campaign")["verification"]["event_replay"] is True
