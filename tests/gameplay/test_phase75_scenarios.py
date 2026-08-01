"""Scenario and reducer anti-forgery tests for Phase 7.5."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tgn.actions.models import ActionIntent
from tgn.core.hashing import state_hash
from tgn.core.models import DomainEvent
from tgn.core.reducer import ReducerError, reduce_event
from tgn.gameplay.expedition import execute_action, get_legal_actions, validate_action

from .phase75_helpers import action, copy_state, make_phase75_state, report_ready_state


def _valid_talk_event(state):
    result = execute_action(state, action("TALK_TO_ACTOR", "talk", actor_id="mara"))
    assert result.accepted
    assert len(result.events) == 1
    return result.events[0]


def _forged_result(state, event, **payload_changes):
    payload = deepcopy(event.payload)
    payload.update(payload_changes)
    forged = DomainEvent(
        event_id=event.event_id,
        event_seq=event.event_seq,
        decision_seq=event.decision_seq,
        game_minute=event.game_minute,
        event_type=event.event_type,
        actor_id=event.actor_id,
        action_id=event.action_id,
        payload=payload,
        created_at=event.created_at,
    )
    before_hash = state_hash(state.__dict__)
    with pytest.raises(ReducerError):
        reduce_event(state, forged)
    assert state_hash(state.__dict__) == before_hash
    return state


def test_report_conversation_is_canonical_legal_action_with_five_minutes():
    state = report_ready_state()
    legal = [la for la in get_legal_actions(state) if la.action_type == "TALK_TO_ACTOR"]
    assert len(legal) == 1
    assert legal[0].params == {"actor_id": "mara"}
    assert legal[0].duration_minutes == 5
    validation = validate_action(state, action("TALK_TO_ACTOR", "talk", actor_id="mara"))
    assert validation.valid
    assert validation.action is not None
    assert validation.action.duration_minutes == 5


def test_successful_talk_transfers_one_fact_and_one_trust_point():
    state = report_ready_state()
    event = _valid_talk_event(state)
    result = reduce_event(state, event)
    assert result.game_minute == 30
    assert result.data["named_actor"]["relationship"]["trust"] == 1
    assert result.data["named_actor"]["goal"] == "reported"
    assert result.data["player_knowledge"]["facts"] == {"site-1-condition": "unstable"}
    assert result.data["player_knowledge"]["actors"]["mara"]["known_goal"] == "reported"
    assert event.event_type == "ACTOR_CONVERSATION_RESOLVED"
    assert set(event.payload) >= {
        "actor_id", "time", "trust_before", "trust_after", "shared_fact_ids"
    }


def test_talk_is_not_legal_remotely_with_unknown_actor_or_after_report():
    remote = execute_action(
        make_phase75_state(), action("TALK_TO_ACTOR", "remote", actor_id="mara")
    )
    assert not remote.accepted
    at_site = execute_action(make_phase75_state(), action("DROP", "drop"))
    assert at_site.final_state is not None
    unknown = execute_action(
        report_ready_state(), action("TALK_TO_ACTOR", "unknown", actor_id="unknown")
    )
    assert not unknown.accepted
    completed = reduce_event(report_ready_state(), _valid_talk_event(report_ready_state()))
    assert all(la.action_type != "TALK_TO_ACTOR" for la in get_legal_actions(completed))


def test_active_encounter_and_dead_player_cannot_talk():
    encounter_state = report_ready_state()
    encounter_state.data["expedition"]["encounter"] = {"active": True}
    result = execute_action(
        encounter_state, action("TALK_TO_ACTOR", "encounter", actor_id="mara")
    )
    assert not result.accepted
    assert get_legal_actions(encounter_state) == ()

    dead_state = report_ready_state()
    dead_state.data["player"]["hp"] = 0
    assert get_legal_actions(dead_state) == ()
    result = execute_action(dead_state, action("TALK_TO_ACTOR", "dead", actor_id="mara"))
    assert not result.accepted


def test_talk_cannot_share_fact_actor_does_not_know():
    state = report_ready_state()
    state.data["named_actor"]["knowledge"] = {}
    state.data["named_actor"]["goal"] = "report_finding"
    result = execute_action(state, action("TALK_TO_ACTOR", "no-fact", actor_id="mara"))
    assert not result.accepted


def test_talk_rejects_repeated_player_fact_before_reducer_changes_state():
    state = report_ready_state()
    state.data["player_knowledge"]["facts"]["site-1-condition"] = "unstable"
    assert all(la.action_type != "TALK_TO_ACTOR" for la in get_legal_actions(state))


def test_talk_rejects_actor_knowledge_with_no_fact_value():
    state = report_ready_state()
    state.data["named_actor"]["knowledge"]["site-1-condition"] = None
    event = _valid_talk_event(report_ready_state())
    before_hash = state_hash(state.__dict__)
    with pytest.raises(ReducerError):
        reduce_event(state, event)
    assert state_hash(state.__dict__) == before_hash


@pytest.mark.parametrize(
    "changes",
    [
        {"trust_before": 99},
        {"trust_after": 99},
        {"shared_fact_ids": ["forged-fact"]},
        {"time": 99},
        {"shared_fact_ids": []},
    ],
)
def test_forged_conversation_payload_is_rejected_without_state_change(changes):
    state = report_ready_state()
    event = _valid_talk_event(state)
    _forged_result(state, event, **changes)


def test_forged_conversation_game_minute_is_rejected_without_state_change():
    state = report_ready_state()
    event = _valid_talk_event(state)
    forged = DomainEvent(
        event_id=event.event_id,
        event_seq=event.event_seq,
        decision_seq=event.decision_seq,
        game_minute=event.game_minute - 1,
        event_type=event.event_type,
        actor_id=event.actor_id,
        action_id=event.action_id,
        payload=deepcopy(event.payload),
        created_at=event.created_at,
    )
    before_hash = state_hash(state.__dict__)
    with pytest.raises(ReducerError):
        reduce_event(state, forged)
    assert state_hash(state.__dict__) == before_hash


@pytest.mark.parametrize("mutation", ["remote", "dead", "encounter", "wrong_goal", "duplicate"])
def test_forged_conversation_preconditions_are_rejected_without_state_change(mutation):
    state = report_ready_state()
    event = _valid_talk_event(state)
    if mutation == "remote":
        state.data["player"]["location_id"] = "site-1"
    elif mutation == "dead":
        state.data["player"]["hp"] = 0
    elif mutation == "encounter":
        state.data["expedition"]["encounter"] = {"active": True}
    elif mutation == "wrong_goal":
        state.data["named_actor"]["goal"] = "inspect_signal"
    else:
        state = reduce_event(state, event)
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type=event.event_type,
            game_minute=state.game_minute + 5,
            decision_seq=state.decision_seq + 1,
            payload=deepcopy(event.payload),
        )
    before_hash = state_hash(state.__dict__)
    with pytest.raises(ReducerError):
        reduce_event(state, event)
    assert state_hash(state.__dict__) == before_hash


def test_unknown_actor_event_is_rejected_without_state_change():
    state = report_ready_state()
    event = _valid_talk_event(state)
    payload = deepcopy(event.payload)
    payload["actor_id"] = "unknown"
    forged = DomainEvent(
        event_seq=event.event_seq,
        event_type=event.event_type,
        game_minute=event.game_minute,
        decision_seq=event.decision_seq,
        payload=payload,
    )
    before_hash = state_hash(state.__dict__)
    with pytest.raises(ReducerError):
        reduce_event(state, forged)
    assert state_hash(state.__dict__) == before_hash
