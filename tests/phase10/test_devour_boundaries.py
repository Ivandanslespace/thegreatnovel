from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from tests.phase10.test_devour_state_and_invariants import _after, _base_state
from tgn.actions.models import ActionIntent
from tgn.core.models import DomainEvent, GameState
from tgn.gameplay import devour_evolution as devour
from tgn.gameplay.expedition import execute_action
from tgn.worldgen.devour_overlay import apply_devour_overlay


def _ready_state() -> GameState:
    return _after(apply_devour_overlay(_base_state()), "DROP", "SEARCH", "FIGHT")[0]


def test_feature_validator_rejects_non_state_and_exact_section_mutations():
    with pytest.raises(ValueError):
        devour.validate_devour_evolution_state(object())

    mutations = [
        lambda state: state.data.__setitem__("capability_grants", []),
        lambda state: state.data["capability_grants"][devour.DEVOUR_EVOLUTION_GRANT_ID].update(
            {"extra": True}
        ),
        lambda state: state.data["capability_grants"][devour.DEVOUR_EVOLUTION_GRANT_ID].update(
            {"holder_id": "other"}
        ),
        lambda state: state.data["devour_evolution"].update({"extra": 1}),
        lambda state: state.data["expedition"].pop("encounter"),
        lambda state: state.data["expedition"]["encounter"]["devour_yield"].update(
            {"extra": True}
        ),
        lambda state: state.data["expedition"]["encounter"]["devour_yield"].update(
            {"capability_id": "other"}
        ),
        lambda state: state.data["expedition"]["encounter"]["devour_yield"].update(
            {"essence": 2}
        ),
        lambda state: state.data["expedition"]["encounter"]["devour_yield"].update(
            {"consumed": 1}
        ),
    ]
    for mutate in mutations:
        state = apply_devour_overlay(_base_state())
        mutate(state)
        with pytest.raises(ValueError):
            devour.validate_devour_evolution_state(state)


def test_feature_presence_ownership_and_public_observation_fail_closed():
    legacy = _base_state()
    assert devour.devour_evolution_enabled(legacy) is False
    assert devour.build_devour_capability_observation(legacy) == []

    partial = _base_state()
    partial.data["devour_evolution"] = {"essence": 0}
    assert devour.player_owns_devour_evolution(partial) is False
    assert devour.build_devour_capability_observation(partial) == []

    invalid_owner = apply_devour_overlay(_base_state())
    invalid_owner.data["capability_grants"].pop(devour.DEVOUR_EVOLUTION_GRANT_ID)
    assert devour.player_owns_devour_evolution(invalid_owner) is False
    assert devour.build_devour_capability_observation(invalid_owner) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: state.data.pop("player"),
        lambda state: state.data["player"].update({"location_id": "elsewhere"}),
        lambda state: state.data["player"].update({"stamina": True}),
        lambda state: state.data["expedition"]["encounter"]["devour_yield"].update(
            {"capability_id": "other"}
        ),
        lambda state: state.data["expedition"]["encounter"]["devour_yield"].update(
            {"essence": 2}
        ),
    ],
)
def test_can_devour_remains_rejects_shape_and_public_boundary_mutations(mutate):
    state = _ready_state()
    mutate(state)
    assert devour.can_devour_remains(state) is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: state.data["expedition"].pop("encounter"),
        lambda state: state.data["expedition"]["encounter"].pop("devour_yield"),
        lambda state: state.data["expedition"]["encounter"]["devour_yield"].update(
            {"capability_id": "other"}
        ),
        lambda state: state.data["expedition"]["encounter"]["devour_yield"].update(
            {"essence": 2}
        ),
    ],
)
def test_legality_checks_each_public_encounter_boundary(monkeypatch, mutate):
    state = _ready_state()
    mutate(state)
    # The exact-state validator normally rejects these malformed feature
    # states first.  This isolated test proves the legality helper's own
    # fail-closed checks without weakening the invariant boundary.
    monkeypatch.setattr(devour, "validate_devour_evolution_state", lambda _state: None)
    assert devour.can_devour_remains(state) is False


def test_event_builder_and_application_reject_invalid_boundaries():
    with pytest.raises(ValueError):
        devour.build_devour_event_payload(_base_state())

    state = _ready_state()
    execution = execute_action(
        state,
        ActionIntent("phase10-boundary", "player", devour.DEVOUR_REMAINS, {}),
    )
    assert execution.accepted and len(execution.events) == 1
    event = execution.events[0]

    with pytest.raises(ValueError):
        devour.apply_devour_resolved(state, replace(event, event_type="OTHER"))
    with pytest.raises(ValueError):
        devour.apply_devour_resolved(state, replace(event, payload={**event.payload, "extra": True}))
    blocked = copy.deepcopy(state)
    blocked.data["player"]["stamina"] = 0
    with pytest.raises(ValueError):
        devour.apply_devour_resolved(blocked, event)
    with pytest.raises(ValueError):
        devour.apply_devour_resolved(state, replace(event, game_minute=event.game_minute + 1))


@pytest.mark.parametrize(
    "payload_change",
    [
        {"essence_after": True},
        {"essence_gained": True},
        {"time": 20.0},
        {"stamina_cost": True},
    ],
)
def test_event_numeric_fields_reject_bool_or_non_integer(payload_change):
    state = _ready_state()
    execution = execute_action(
        state,
        ActionIntent("phase10-numeric", "player", devour.DEVOUR_REMAINS, {}),
    )
    event = execution.events[0]
    payload = dict(event.payload)
    payload.update(payload_change)
    with pytest.raises(ValueError):
        devour.apply_devour_resolved(state, replace(event, payload=payload))
