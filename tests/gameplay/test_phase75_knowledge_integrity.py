"""Observation and knowledge-boundary tests for Phase 7.5."""

from __future__ import annotations

from copy import deepcopy

from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import build_observation, get_legal_actions
from tgn.gameplay.named_actor import (
    MARA_FACT_ID,
    count_knowledge_boundary_violations,
)

from .phase75_helpers import execute, make_phase75_state, report_ready_state


def test_initial_observation_exposes_only_player_known_actor_projection():
    state = make_phase75_state()
    observation = build_observation(state)
    actor = observation["actor"]
    assert actor["actor_id"] == "mara"
    assert actor["name"] == "Mara"
    assert actor["last_known_location_id"] == "base-1"
    assert actor["known_goal"] == "inspect_signal"
    assert actor["trust"] == 0
    assert actor["visible"] is True
    assert actor["facts"] == {}
    assert "site-1-condition" not in str(observation["actor"]["facts"])
    assert count_knowledge_boundary_violations(state, observation) == 0


def test_offscreen_inspection_does_not_leak_fact_private_knowledge_or_goal():
    state = execute(make_phase75_state(), "DROP", "drop-away")
    observation = build_observation(state)
    actor = observation["actor"]
    assert actor["visible"] is False
    assert actor["last_known_location_id"] == "base-1"
    assert actor["known_goal"] == "inspect_signal"
    assert actor["facts"] == {}
    assert actor["has_something_to_report"] is False
    assert "world_facts" not in observation
    assert "private_knowledge" not in observation
    assert "last_autonomous_action" not in observation
    assert count_knowledge_boundary_violations(state, observation) == 0


def test_returning_to_mara_shows_report_signal_but_not_fact_value():
    state = report_ready_state()
    observation = build_observation(state)
    actor = observation["actor"]
    assert actor["visible"] is True
    assert actor["has_something_to_report"] is True
    assert actor["known_goal"] == "inspect_signal"
    assert actor["facts"] == {}
    assert all(la.action_type != "TALK_TO_ACTOR" or la.duration_minutes == 5
               for la in get_legal_actions(state))
    assert count_knowledge_boundary_violations(state, observation) == 0


def test_fact_appears_only_after_successful_talk():
    state = report_ready_state()
    before = build_observation(state)
    assert before["actor"]["facts"] == {}
    state = execute(state, "TALK_TO_ACTOR", "talk", actor_id="mara")
    after = build_observation(state)
    assert after["actor"]["facts"] == {MARA_FACT_ID: "unstable"}
    assert after["actor"]["known_goal"] == "reported"
    assert count_knowledge_boundary_violations(state, after) == 0


def test_observation_and_legal_action_mutation_do_not_change_canonical_state():
    state = report_ready_state()
    before_hash = state_hash(state.__dict__)
    observation = build_observation(state)
    observation["actor"]["facts"]["forged"] = "leak"
    observation["actor"]["trust"] = 99
    talk = next(
        action for action in observation["legal_actions"]
        if action.action_type == "TALK_TO_ACTOR"
    )
    talk.params["actor_id"] = "forged"
    assert state_hash(state.__dict__) == before_hash
    assert state.data["player_knowledge"]["facts"] == {}
    assert state.data["named_actor"]["relationship"]["trust"] == 0


def test_boundary_detector_flags_only_explicit_local_leaks():
    state = make_phase75_state()
    observation = build_observation(state)
    leaked = deepcopy(observation)
    leaked["world_facts"] = {MARA_FACT_ID: "unstable"}
    leaked["actor"]["private_knowledge"] = {MARA_FACT_ID: "unstable"}
    leaked["actor"]["facts"] = {MARA_FACT_ID: "unstable"}
    assert count_knowledge_boundary_violations(state, leaked) == 3
