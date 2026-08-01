"""Phase 8 strict completion response and intent-boundary tests."""

from __future__ import annotations

import json

import pytest

from tgn.actions.models import ActionIntent
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import build_observation
from tgn.llm_player import (
    LLMOutputError,
    LLMPlayerPolicy,
    build_llm_decision_request,
    parse_llm_response,
)

from tests.gameplay.phase75_helpers import make_phase75_state, report_ready_state


def test_policy_requires_an_injected_callable():
    with pytest.raises(TypeError):
        LLMPlayerPolicy(None)


def test_valid_choice_and_stop_responses_are_exact():
    state = make_phase75_state()
    request = build_llm_decision_request(build_observation(state), 1)
    choice = parse_llm_response('{"choice_id":"choice-001"}', request)
    assert choice is not None
    assert choice == request.choices[1]
    assert parse_llm_response('{"stop":true}', request) is None


@pytest.mark.parametrize(
    "raw_response",
    [
        None,
        "not json",
        "```json\n{\"stop\":true}\n```",
        "[]",
        "null",
        "{\"choice_id\":\"choice-001\",\"reward\":999}",
        "{\"choice_id\":\"choice-999\"}",
        "{\"choice_id\":7}",
        "{\"stop\":false}",
        "{\"choice_id\":\"choice-001\",\"stop\":true}",
        "{\"choice_id\":\"choice-001\"}{\"stop\":true}",
        "{\"actor_id\":\"mara\",\"params\":{\"actor_id\":\"other\"}}",
    ],
)
def test_invalid_output_is_rejected_before_state_or_intent_changes(raw_response):
    state = make_phase75_state()
    observation = build_observation(state)
    before_hash = state_hash(state.__dict__)
    policy = LLMPlayerPolicy(lambda _prompt: raw_response)

    with pytest.raises(LLMOutputError):
        policy(observation, 1, "llm-player")

    assert state_hash(state.__dict__) == before_hash
    assert state.event_seq == 0
    assert state.decision_seq == 0
    assert policy.recorded_decisions == ()


def test_stop_is_recorded_and_record_snapshot_is_detached():
    state = make_phase75_state()
    policy = LLMPlayerPolicy(lambda _prompt: '{"stop":true}')
    assert policy(build_observation(state), 1, "llm-player") is None

    records = policy.recorded_decisions
    assert len(records) == 1
    assert records[0].outcome == "STOP"
    assert records[0].choice_id is None
    assert records[0].action_type is None
    assert records[0].params == {}
    records[0].params["forged"] = True
    assert policy.recorded_decisions[0].params == {}


def test_parameterized_action_uses_engine_choice_and_runner_actor_id():
    state = report_ready_state()
    observation = build_observation(state)
    request = build_llm_decision_request(observation, 1)
    talk = next(choice for choice in request.choices if choice.action_type == "TALK_TO_ACTOR")
    policy = LLMPlayerPolicy(
        lambda _prompt: json.dumps({"choice_id": talk.choice_id}, separators=(",", ":"))
    )

    intent = policy(observation, 1, "configured-autoplay-actor")

    assert isinstance(intent, ActionIntent)
    assert intent.action_id == "configured-autoplay-actor-llm-1"
    assert intent.actor_id == "configured-autoplay-actor"
    assert intent.action_type == "TALK_TO_ACTOR"
    assert intent.params == {"actor_id": "mara"}
