"""Phase 8 request construction and visibility-boundary tests."""

from __future__ import annotations

import json

import pytest

from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import build_observation
from tgn.llm_player import (
    LLMActionChoice,
    LLMDecisionRequest,
    build_llm_decision_request,
    build_llm_prompt,
)

from tests.gameplay.phase75_helpers import execute, make_phase75_state, report_ready_state


def test_request_contains_only_detached_player_visible_information():
    state = execute(make_phase75_state(), "DROP", "drop-before-search")
    observation = build_observation(state)
    request = build_llm_decision_request(observation, 1)
    prompt = build_llm_prompt(request)

    assert "legal_actions" not in request.observation
    assert "target_loot" not in prompt
    assert "loot_gained" not in prompt
    assert "encounter result" not in prompt
    assert "salvage" not in prompt
    assert "world_facts" not in prompt
    assert "private_knowledge" not in prompt
    assert "named_actor.knowledge" not in prompt
    assert "report_finding" not in prompt
    assert "last_autonomous_action" not in prompt
    assert "site-1-condition" not in request.observation["actor"]["facts"]
    assert "unstable" not in prompt
    assert "event_seq" not in prompt
    assert "decision_seq" not in prompt
    assert "GameState" not in prompt
    assert "EventStore" not in prompt
    json.loads(prompt.split("REQUEST_JSON:\n", 1)[1])


def test_known_fact_can_appear_only_after_player_learns_it():
    state = execute(report_ready_state(), "TALK_TO_ACTOR", "talk-before-llm", actor_id="mara")
    request = build_llm_decision_request(build_observation(state), 1)
    assert request.observation["actor"]["facts"] == {
        "site-1-condition": "unstable"
    }
    assert "unstable" in build_llm_prompt(request)


def test_request_fingerprint_and_choice_ids_are_deterministic():
    observation_a = build_observation(make_phase75_state())
    observation_b = build_observation(make_phase75_state())
    request_a = build_llm_decision_request(observation_a, 1)
    request_b = build_llm_decision_request(observation_b, 1)

    assert request_a.request_fingerprint == request_b.request_fingerprint
    assert request_a.choices == request_b.choices
    assert [choice.choice_id for choice in request_a.choices] == [
        f"choice-{index:03d}" for index in range(len(request_a.choices))
    ]
    json.dumps(request_a.to_dict(), ensure_ascii=False)


def test_request_and_choice_mutation_is_detached_from_source_objects():
    state = make_phase75_state()
    before_hash = state_hash(state.__dict__)
    observation = build_observation(state)
    request = build_llm_decision_request(observation, 1)
    before_request = request.to_dict()
    before_fingerprint = request.request_fingerprint
    choice_params = request.choices[0].params
    source_choice = next(
        choice for choice in observation["legal_actions"] if choice.action_type == "DROP"
    )
    request_choice = next(choice for choice in request.choices if choice.action_type == "DROP")

    observation["inventory"]["forged"] = 1
    source_choice.params["source_forged"] = "source mutation"
    request.observation["inventory"]["forged"] = 2
    choice_params["forged"] = 3

    assert state_hash(state.__dict__) == before_hash
    assert request.to_dict() == before_request
    assert request.request_fingerprint == before_fingerprint
    assert "forged" not in request.observation["inventory"]
    assert "source_forged" not in next(
        choice for choice in request.choices if choice.action_type == "DROP"
    ).params
    assert "forged" not in request.choices[0].params
    assert "forged" not in source_choice.params


def test_choice_params_are_observationally_immutable():
    choice = LLMActionChoice("choice-000", "TALK_TO_ACTOR", {"actor_id": "mara"}, 5, 0)
    before = choice.to_dict()
    params = choice.params
    params["actor_id"] = "other"
    params["forged"] = True

    assert choice.to_dict() == before
    assert choice.params == {"actor_id": "mara"}


@pytest.mark.parametrize(
    "factory",
    [
        lambda: LLMActionChoice("", "WAIT", {}, None, 0),
        lambda: LLMActionChoice("choice", "", {}, None, 0),
        lambda: LLMActionChoice("choice", "WAIT", {}, True, 0),
        lambda: LLMActionChoice("choice", "WAIT", {}, None, True),
        lambda: LLMActionChoice("choice", "WAIT", [], None, 0),
    ],
)
def test_choice_model_rejects_invalid_engine_metadata(factory):
    with pytest.raises(ValueError):
        factory()


def test_request_model_rejects_invalid_identity_and_detaches_list_choices():
    choice = LLMActionChoice("choice-000", "WAIT", {}, None, 0)
    with pytest.raises(ValueError):
        LLMDecisionRequest(0, {}, (), "fingerprint")
    with pytest.raises(ValueError):
        LLMDecisionRequest(1, [], (), "fingerprint")
    with pytest.raises(ValueError):
        LLMDecisionRequest(1, {}, (), "")

    request = LLMDecisionRequest(1, {"visible": True}, [choice], "fingerprint")
    assert isinstance(request.choices, tuple)
    assert request.to_dict()["choices"][0]["choice_id"] == "choice-000"


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        ([], "observation"),
        ({}, "legal_actions"),
        ({"legal_actions": {}}, "tuple or list"),
        ({"legal_actions": [object()]}, "LegalAction-like"),
    ],
)
def test_request_builder_rejects_malformed_source_boundary(observation, expected):
    with pytest.raises(ValueError, match=expected):
        build_llm_decision_request(observation, 1)
