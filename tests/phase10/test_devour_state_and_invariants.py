from __future__ import annotations

import copy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from tgn.actions.models import ActionIntent
from tgn.core.hashing import state_hash
from tgn.core.invariants import InvariantError, check_invariants
from tgn.core.reducer import ReducerError, reduce_event
from tgn.gameplay.devour_evolution import (
    DEVOUR_REMAINS,
    DEVOUR_RESOLVED,
    can_devour_remains,
    validate_devour_evolution_state,
)
from tgn.gameplay.expedition import build_observation, execute_action, get_legal_actions, validate_action
from tgn.storage.replay import replay_events
from tgn.worldgen import devour_overlay
from tgn.worldgen.devour_overlay import apply_devour_overlay, bootstrap_devour_overlay
from tgn.worldgen.compiler import compile_world


def _base_state():
    return compile_world(
        {"schema_version": 1, "prompt": "legacy"},
        {
            "schema_version": 1,
            "mechanics_profile": "phase75_expedition_v1",
            "world_id": "legacy",
            "content_locale": "en",
            "title": "Legacy",
            "premise": "Legacy",
            "labels": {
                "base": "Base",
                "target": "Site",
                "resource": "Salvage",
                "hazard": "Hazard",
                "named_actor": "Mara",
                "named_actor_role": "Scout",
                "named_actor_public_goal": "Inspect",
            },
        },
        "seed",
    ).initial_state


def _after(state, *actions):
    events = []
    current = state
    for index, action in enumerate(actions, start=1):
        result = execute_action(current, ActionIntent(f"phase10-{index}", "player", action, {}))
        assert result.accepted, result.validation.errors
        assert len(result.events) == 1
        events.extend(result.events)
        current = result.final_state
    return current, events


def test_legacy_state_has_no_phase10_surface():
    state = _base_state()
    check_invariants(state)
    assert "capability_grants" not in state.data
    assert "devour_evolution" not in state.data
    assert "capabilities" not in build_observation(state)
    assert DEVOUR_REMAINS not in {action.action_type for action in get_legal_actions(state)}


def test_overlay_sequence_is_one_event_and_replayable():
    initial = apply_devour_overlay(_base_state())
    validate_devour_evolution_state(initial)
    assert initial.data["player"]["stamina"] == 5
    assert initial.data["devour_evolution"] == {"essence": 0}

    fought, events = _after(initial, "DROP", "SEARCH", "FIGHT")
    legal = get_legal_actions(fought)
    assert [action.action_type for action in legal] == ["WAIT", DEVOUR_REMAINS, "EXTRACT"]
    assert can_devour_remains(fought)
    assert build_observation(fought)["capabilities"] == [
        {
            "capability_id": "devour_evolution",
            "label": "Devour Evolution",
            "source_kind": "world_genesis",
        }
    ]

    final, devour_events = _after(fought, DEVOUR_REMAINS, "EXTRACT")
    events.extend(devour_events)
    assert events[3].event_type == DEVOUR_RESOLVED
    assert events[3].payload == {
        "capability_id": "devour_evolution",
        "grant_id": "player_devour_evolution_genesis",
        "enemy_id": "enemy-1",
        "essence_before": 0,
        "essence_gained": 1,
        "essence_after": 1,
        "time": 20,
        "stamina_cost": 1,
    }
    assert final.data["devour_evolution"]["essence"] == 1
    assert final.data["expedition"]["encounter"]["devour_yield"]["consumed"] is True
    assert final.data["player"]["stamina"] == 0
    assert final.data["expedition"]["active"] is False

    replay = replay_events(initial, events)
    assert replay.success
    assert replay.actual_hash == state_hash(final.__dict__)


def test_living_encounter_remains_fight_or_flee_only():
    initial = apply_devour_overlay(_base_state())
    after_search, _ = _after(initial, "DROP", "SEARCH")
    assert [action.action_type for action in get_legal_actions(after_search)] == ["FIGHT", "FLEE"]
    assert not can_devour_remains(after_search)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda state: state.data["player"].update({"stamina": 0}),
        lambda state: state.data["player"].update({"hp": 0}),
        lambda state: state.data["expedition"].update({"active": False}),
        lambda state: state.data["expedition"]["encounter"].update({"enemy_hp": 1}),
        lambda state: state.data["expedition"]["encounter"]["devour_yield"].update({"consumed": True}),
        lambda state: state.data["capability_grants"]["player_devour_evolution_genesis"].update({"holder_id": "other"}),
    ],
)
def test_each_applicability_boundary_is_fail_closed(mutation):
    state, _ = _after(apply_devour_overlay(_base_state()), "DROP", "SEARCH", "FIGHT")
    mutation(state)
    assert not can_devour_remains(state)


def test_partial_feature_state_fails_core_invariants():
    state = _base_state()
    state.data["devour_evolution"] = {"essence": 0}
    with pytest.raises(InvariantError):
        check_invariants(state)

    state = apply_devour_overlay(_base_state())
    state.data["devour_evolution"]["essence"] = True
    with pytest.raises(InvariantError):
        check_invariants(state)


def test_devour_params_and_payload_are_engine_authoritative():
    state, _ = _after(apply_devour_overlay(_base_state()), "DROP", "SEARCH", "FIGHT")
    invalid = validate_action(
        state,
        ActionIntent("bad", "player", DEVOUR_REMAINS, {"enemy_id": "enemy-1"}),
    )
    assert not invalid.valid
    assert invalid.errors[0].code == "UNEXPECTED_PARAMETER"

    valid = execute_action(state, ActionIntent("good", "player", DEVOUR_REMAINS, {}))
    assert valid.accepted
    forged = replace(
        valid.events[0],
        payload={**valid.events[0].payload, "essence_after": 99},
    )
    with pytest.raises(ReducerError):
        reduce_event(state, forged)


def test_second_use_is_not_legal():
    state, _ = _after(apply_devour_overlay(_base_state()), "DROP", "SEARCH", "FIGHT", DEVOUR_REMAINS)
    assert DEVOUR_REMAINS not in {action.action_type for action in get_legal_actions(state)}
    assert not can_devour_remains(state)


def test_overlay_bootstrap_report_is_exact():
    report = bootstrap_devour_overlay(apply_devour_overlay(_base_state()))
    assert report["accepted_decisions"] == 5
    assert report["events"] == 5
    assert report["illegal_actions"] == 0
    assert report["essence"] == 1
    assert report["devour_yield_consumed"] is True
    assert report["replay_verified"] is True
    assert report["stamina_before_devour"] == 1
    assert report["stamina_after_devour"] == 0
    assert report["final_stamina_after_extract"] == 0


def test_overlay_rejects_non_base_inputs():
    with pytest.raises(ValueError):
        apply_devour_overlay(object())
    with pytest.raises(ValueError):
        apply_devour_overlay(apply_devour_overlay(_base_state()))

    malformed = _base_state()
    malformed.data["expedition"] = None
    with pytest.raises(ValueError):
        apply_devour_overlay(malformed)


@pytest.mark.parametrize(
    "result",
    [
        SimpleNamespace(completed=False, decisions=0, events=0),
        SimpleNamespace(completed=True, decisions=5, events=5, illegal_actions=1, replay_verified=True),
        SimpleNamespace(
            completed=True,
            decisions=5,
            events=5,
            illegal_actions=0,
            replay_verified=True,
            final_state=SimpleNamespace(event_seq=4, decision_seq=5),
        ),
    ],
)
def test_overlay_bootstrap_rejects_incomplete_autoplay(monkeypatch, result):
    monkeypatch.setattr(devour_overlay, "run_autoplay", lambda *_args, **_kwargs: result)
    with pytest.raises(ValueError):
        bootstrap_devour_overlay(_base_state())


@pytest.mark.parametrize(
    "before,after,final_mutation",
    [
        (0, 0, None),
        (1, 1, None),
        (1, 0, lambda state: setattr(state, "event_seq", 4)),
        (1, 0, lambda state: state.data["devour_evolution"].update({"essence": 0})),
    ],
)
def test_overlay_bootstrap_rejects_invalid_frames_or_final_state(
    monkeypatch, before, after, final_mutation
):
    state = apply_devour_overlay(_base_state())
    if final_mutation is not None:
        final_state = copy.deepcopy(state)
        final_state.event_seq = 5
        final_state.decision_seq = 5
        final_mutation(final_state)
    else:
        final_state = state
    frame = SimpleNamespace(
        action_type=DEVOUR_REMAINS,
        observation_before={"stamina": before},
        observation_after={"stamina": after},
    )
    result = SimpleNamespace(
        completed=True,
        decisions=5,
        events=5,
        illegal_actions=0,
        replay_verified=True,
        final_state=final_state,
        frames=[frame],
    )
    monkeypatch.setattr(devour_overlay, "run_autoplay", lambda *_args, **_kwargs: result)
    with pytest.raises(ValueError):
        bootstrap_devour_overlay(state)


def test_overlay_bootstrap_rejects_non_state_input():
    with pytest.raises(ValueError):
        bootstrap_devour_overlay(object())
