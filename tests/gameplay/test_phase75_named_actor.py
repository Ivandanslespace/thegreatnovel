"""Unit and contract tests for the local Phase 7.5 named actor slice."""

from __future__ import annotations

import copy

import pytest

from tgn.actions.models import ActionIntent
from tgn.core.hashing import state_hash
from tgn.core.invariants import InvariantError, check_invariants
from tgn.core.models import DomainEvent
from tgn.gameplay.expedition import build_observation, execute_action
from tgn.gameplay.named_actor import (
    MARA_AUTONOMOUS_ACTION,
    MARA_FACT_ID,
    MARA_REPORT_GOAL,
    apply_named_actor_autonomous_consequence,
    NamedActorDecisionView,
    build_actor_decision_view,
    decide_named_actor_action,
    validate_named_actor_state,
)

from .phase75_helpers import action, copy_state, execute, make_phase75_state


def test_complete_phase75_configuration_passes_invariants():
    state = make_phase75_state()
    check_invariants(state)
    assert state.data["named_actor"]["actor_id"] == "mara"
    assert state.data["world_facts"] == {MARA_FACT_ID: "unstable"}
    assert state.data["player_knowledge"]["facts"] == {}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("named_actor", "actor_id"), 7),
        (("named_actor", "name"), 7),
        (("named_actor", "location_id"), 7),
        (("named_actor", "goal"), 7),
        (("named_actor", "relationship", "trust"), True),
        (("named_actor", "relationship", "trust"), -1),
        (("named_actor", "knowledge"), []),
        (("named_actor", "last_autonomous_action"), 7),
    ],
)
def test_invalid_named_actor_fields_are_rejected(path, value):
    state = make_phase75_state()
    target = state.data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(InvariantError):
        check_invariants(state)


@pytest.mark.parametrize("missing", ["named_actor", "world_facts", "player_knowledge"])
def test_partial_feature_configuration_is_rejected(missing):
    state = make_phase75_state()
    del state.data[missing]
    with pytest.raises(InvariantError):
        check_invariants(state)


def test_legacy_state_without_named_actor_feature_is_unchanged(phase3_initial_state):
    check_invariants(phase3_initial_state)
    observation = build_observation(phase3_initial_state)
    assert "actor" not in observation
    assert all(la.action_type != "TALK_TO_ACTOR" for la in observation["legal_actions"])


@pytest.mark.parametrize("mutation", [
    "unsupported_world_fact",
    "invalid_fact_value",
    "invalid_expedition_active",
    "invalid_encounter",
    "player_view_name",
    "player_view_goal",
    "player_knows_unknown_fact",
    "player_fact_before_report",
    "initial_actor_knowledge",
    "report_without_inspection",
    "report_with_player_change",
    "reported_without_fact",
    "reported_with_wrong_trust",
])
def test_named_actor_boundary_rejects_inconsistent_knowledge_states(mutation):
    state = make_phase75_state()
    actor = state.data["named_actor"]
    player_view = state.data["player_knowledge"]["actors"]["mara"]
    if mutation == "unsupported_world_fact":
        state.data["world_facts"] = {"other": "unstable"}
    elif mutation == "invalid_fact_value":
        state.data["world_facts"][MARA_FACT_ID] = "unknown"
    elif mutation == "invalid_expedition_active":
        state.data["expedition"]["active"] = 1
    elif mutation == "invalid_encounter":
        state.data["expedition"]["encounter"] = []
    elif mutation == "player_view_name":
        player_view["name"] = "Not Mara"
    elif mutation == "player_view_goal":
        player_view["known_goal"] = MARA_REPORT_GOAL
    elif mutation == "player_knows_unknown_fact":
        state.data["player_knowledge"]["facts"] = {"forged": "value"}
    elif mutation == "player_fact_before_report":
        actor["knowledge"] = {MARA_FACT_ID: "unstable"}
        state.data["player_knowledge"]["facts"] = {MARA_FACT_ID: "unstable"}
    elif mutation == "initial_actor_knowledge":
        actor["knowledge"] = {MARA_FACT_ID: "unstable"}
    elif mutation == "report_without_inspection":
        actor["goal"] = MARA_REPORT_GOAL
        actor["knowledge"] = {MARA_FACT_ID: "unstable"}
    elif mutation == "report_with_player_change":
        actor["goal"] = MARA_REPORT_GOAL
        actor["knowledge"] = {MARA_FACT_ID: "unstable"}
        actor["last_autonomous_action"] = MARA_AUTONOMOUS_ACTION
        state.data["player_knowledge"]["facts"] = {MARA_FACT_ID: "unstable"}
    elif mutation == "reported_without_fact":
        actor["goal"] = "reported"
        actor["knowledge"] = {MARA_FACT_ID: "unstable"}
    else:
        actor["goal"] = "reported"
        actor["knowledge"] = {MARA_FACT_ID: "unstable"}
        actor["last_autonomous_action"] = MARA_AUTONOMOUS_ACTION
        actor["relationship"]["trust"] = 0
        state.data["player_knowledge"]["facts"] = {MARA_FACT_ID: "unstable"}
        player_view["known_goal"] = "reported"
    if mutation == "invalid_encounter":
        with pytest.raises(ValueError):
            validate_named_actor_state(state)
        return
    with pytest.raises(InvariantError):
        check_invariants(state)


def test_legacy_validation_helper_is_a_no_op(phase3_initial_state):
    validate_named_actor_state(phase3_initial_state)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            lambda state: state.data["named_actor"]["relationship"].__setitem__("trust", 1),
            id="initial-trust-must-be-zero",
        ),
        pytest.param(
            lambda state: state.data["player_knowledge"]["actors"]["mara"].__setitem__(
                "known_goal", "reported"
            ),
            id="initial-player-goal-must-be-inspect",
        ),
    ],
)
def test_initial_named_actor_state_is_exact(mutation):
    state = make_phase75_state()
    mutation(state)
    with pytest.raises(InvariantError):
        check_invariants(state)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            lambda state: state.data["named_actor"]["knowledge"].__setitem__(
                MARA_FACT_ID, "safe"
            ),
            id="report-ready-fact-must-match-world",
        ),
        pytest.param(
            lambda state: state.data["named_actor"].__setitem__(
                "last_autonomous_action", None
            ),
            id="report-ready-requires-inspection-action",
        ),
        pytest.param(
            lambda state: state.data["named_actor"]["relationship"].__setitem__("trust", 1),
            id="report-ready-trust-must-be-zero",
        ),
    ],
)
def test_report_ready_named_actor_state_is_exact(mutation):
    state = execute(make_phase75_state(), "DROP", "drop-for-exact-report")
    mutation(state)
    with pytest.raises(InvariantError):
        check_invariants(state)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            lambda state: state.data["named_actor"].__setitem__(
                "last_autonomous_action", None
            ),
            id="reported-requires-inspection-action",
        ),
        pytest.param(
            lambda state: state.data["named_actor"]["relationship"].__setitem__("trust", 0),
            id="reported-trust-must-be-one",
        ),
        pytest.param(
            lambda state: state.data["player_knowledge"]["actors"]["mara"].__setitem__(
                "known_goal", "inspect_signal"
            ),
            id="reported-player-goal-must-be-reported",
        ),
    ],
)
def test_reported_named_actor_state_is_exact(mutation):
    state = execute(
        execute(
            execute(make_phase75_state(), "DROP", "drop-for-exact-reported"),
            "EXTRACT",
            "extract-for-exact-reported",
        ),
        "TALK_TO_ACTOR",
        "talk-for-exact-reported",
        actor_id="mara",
    )
    mutation(state)
    with pytest.raises(InvariantError):
        check_invariants(state)


def test_autonomous_consequence_handles_missing_world_fact_without_mutation():
    state = make_phase75_state()
    state.data["player"]["location_id"] = "site-1"
    state.data["expedition"]["active"] = True
    del state.data["world_facts"][MARA_FACT_ID]
    before = copy_state(state)
    assert apply_named_actor_autonomous_consequence(state) is False
    assert state.data["named_actor"] == before.data["named_actor"]


def test_time_advancing_action_away_from_mara_triggers_one_inspection():
    state = make_phase75_state()
    before_hash = state_hash(state.__dict__)
    result = execute_action(state, action("DROP", "drop-away"))
    assert result.accepted
    after = result.final_state
    assert after is not None
    assert after.game_minute == 10
    assert after.data["named_actor"]["knowledge"] == {MARA_FACT_ID: "unstable"}
    assert after.data["named_actor"]["goal"] == MARA_REPORT_GOAL
    assert after.data["named_actor"]["last_autonomous_action"] == MARA_AUTONOMOUS_ACTION
    assert after.data["player_knowledge"]["facts"] == {}
    assert after.data["named_actor"]["relationship"] == {"trust": 0}
    assert state_hash(state.__dict__) == before_hash


def test_no_time_progression_does_not_trigger_actor():
    state = execute(make_phase75_state(), "DROP", "drop-away")
    before = copy_state(state)
    event = DomainEvent(
        event_seq=state.event_seq + 1,
        event_type="TIME_ADVANCED",
        game_minute=state.game_minute,
        decision_seq=state.decision_seq + 1,
        payload={"minutes": 0},
    )
    from tgn.core.reducer import reduce_event

    after = reduce_event(state, event)
    assert after.game_minute == before.game_minute
    assert after.data["named_actor"] == before.data["named_actor"]


def test_player_present_suppresses_offscreen_actor_step():
    state = make_phase75_state()
    result = execute_action(state, action("WAIT", "wait-nearby", minutes=5))
    assert result.accepted
    assert result.final_state is not None
    assert result.final_state.data["named_actor"]["knowledge"] == {}
    assert result.final_state.data["named_actor"]["last_autonomous_action"] is None


def test_illegal_action_does_not_trigger_or_mutate_actor():
    state = make_phase75_state()
    before_hash = state_hash(state.__dict__)
    result = execute_action(state, action("SEARCH", "illegal-search"))
    assert not result.accepted
    assert result.events == ()
    assert state_hash(state.__dict__) == before_hash
    assert state.data["named_actor"]["knowledge"] == {}


def test_repeated_time_progression_does_not_repeat_inspection():
    state = execute(make_phase75_state(), "DROP", "drop-away")
    before = copy_state(state)
    after = execute(state, "WAIT", "wait-after-inspect", minutes=5)
    assert after.data["named_actor"] == before.data["named_actor"]


def test_observation_does_not_execute_autonomous_behavior():
    state = make_phase75_state()
    before_hash = state_hash(state.__dict__)
    first = build_observation(state)
    second = build_observation(state)
    assert first == second
    assert state_hash(state.__dict__) == before_hash
    assert state.data["named_actor"]["knowledge"] == {}


def test_same_state_and_event_produce_same_actor_result_and_hash():
    state_a = make_phase75_state()
    state_b = copy_state(state_a)
    intent = action("DROP", "same-drop")
    result_a = execute_action(state_a, intent)
    result_b = execute_action(state_b, intent)
    assert result_a.accepted and result_b.accepted
    assert result_a.final_state is not None and result_b.final_state is not None
    assert result_a.final_state.data["named_actor"] == result_b.final_state.data["named_actor"]
    assert state_hash(result_a.final_state.__dict__) == state_hash(result_b.final_state.__dict__)


def test_decision_view_excludes_world_truth_and_uses_same_policy_for_different_truth():
    unstable = make_phase75_state(fact_value="unstable")
    safe = make_phase75_state(fact_value="safe")
    # Keep the actor-local view identical while making the player absent.
    unstable.data["player"]["location_id"] = "site-1"
    unstable.data["expedition"]["active"] = True
    safe.data["player"]["location_id"] = "site-1"
    safe.data["expedition"]["active"] = True
    view_a = build_actor_decision_view(unstable)
    view_b = build_actor_decision_view(safe)
    assert view_a == view_b
    assert decide_named_actor_action(view_a) == MARA_AUTONOMOUS_ACTION
    assert decide_named_actor_action(view_b) == MARA_AUTONOMOUS_ACTION
    assert not hasattr(view_a, "world_facts")


def test_decision_function_is_stable_for_present_or_known_actor():
    base_view = NamedActorDecisionView(
        location_id="base-1",
        goal="inspect_signal",
        knowledge={},
        player_present=True,
        game_minute=5,
    )
    known_view = NamedActorDecisionView(
        location_id="base-1",
        goal="inspect_signal",
        knowledge={MARA_FACT_ID: "safe"},
        player_present=False,
        game_minute=5,
    )
    assert decide_named_actor_action(base_view) is None
    assert decide_named_actor_action(known_view) is None
