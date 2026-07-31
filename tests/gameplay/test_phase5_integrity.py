"""Phase 5 integrity tests: reducer anti-forgery, invariants, backward compatibility."""

import pytest
from tgn.core.models import GameState, DomainEvent
from tgn.core.reducer import reduce_event, ReducerError
from tgn.core.invariants import check_invariants, InvariantError
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import (
    get_legal_actions,
    validate_action,
    execute_action,
    build_observation,
)
from tgn.actions.models import ActionIntent


PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120,
    "boundary_minute": 60,
    "phase_before": "DAY",
    "phase_after": "NIGHT",
    "blocked_actions_by_phase": {
        "NIGHT": ["DROP"],
    },
}


def _make_phase5_state(game_minute: int, event_seq: int = 0, decision_seq: int = 0) -> GameState:
    """Build a Phase-5-enabled state at given game_minute."""
    return GameState(
        schema_version=1,
        event_seq=event_seq,
        decision_seq=decision_seq,
        game_minute=game_minute,
        seed="phase5-test",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 3,
                "max_stamina": 3,
                "hp": 10,
                "max_hp": 10,
                "attack": 5,
            },
            "inventory": {},
            "expedition": {
                "active": False,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": False,
                "target_loot": {"salvage": 2},
                "carried_loot": {},
            },
            "phase_cycle": dict(PHASE_CYCLE_CONFIG),
        },
    )


def _make_legacy_state(game_minute: int = 0) -> GameState:
    """Pre-Phase-5 state without phase_cycle config."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=game_minute,
        seed="legacy-test",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 3,
                "max_stamina": 3,
            },
            "inventory": {},
            "expedition": {
                "active": False,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": False,
                "target_loot": {"salvage": 2},
                "carried_loot": {},
            },
        },
    )


# --- Direct night DROP rejection (spec #35) ---

class TestNightDropRejection:
    def test_night_drop_validation_rejects(self):
        state = _make_phase5_state(60)  # NIGHT
        intent = ActionIntent(
            action_id="a1", actor_id="p1", action_type="DROP", params={}
        )
        result = validate_action(state, intent)
        assert result.valid is False
        assert result.errors[0].code == "ACTION_NOT_LEGAL_IN_STATE"

    def test_night_drop_execution_rejects(self):
        state = _make_phase5_state(60)  # NIGHT
        original_hash = state_hash(state.__dict__)
        intent = ActionIntent(
            action_id="a1", actor_id="p1", action_type="DROP", params={}
        )
        result = execute_action(state, intent)
        assert result.accepted is False
        assert result.events == ()
        assert result.final_state is None
        # Original state unchanged
        assert state_hash(state.__dict__) == original_hash

    def test_night_drop_absent_from_legal_actions(self):
        state = _make_phase5_state(60)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types


# --- Reducer forged-event test (spec #36) ---

class TestReducerAntiForgery:
    def test_forged_drop_rejected_when_phase_blocks_drop(self):
        """Forging EXPEDITION_DROPPED at NIGHT must raise ReducerError."""
        state = _make_phase5_state(60)  # NIGHT, DROP blocked
        forged_event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_DROPPED",
            game_minute=70,
            decision_seq=1,
            action_id="forged-1",
            actor_id="p1",
            payload={
                "destination": "site-1",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged_event)

    def test_forged_drop_does_not_mutate_state(self):
        state = _make_phase5_state(60)
        original_hash = state_hash(state.__dict__)
        forged_event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_DROPPED",
            game_minute=70,
            decision_seq=1,
            payload={
                "destination": "site-1",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged_event)
        assert state_hash(state.__dict__) == original_hash

    def test_legitimate_drop_at_day_accepted_by_reducer(self):
        """DROP at DAY passes reducer (control test)."""
        state = _make_phase5_state(0)  # DAY
        event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_DROPPED",
            game_minute=10,
            decision_seq=1,
            action_id="a1",
            actor_id="p1",
            payload={
                "destination": "site-1",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        new_state = reduce_event(state, event)
        assert new_state.data["expedition"]["active"] is True


# --- Invalid configuration invariant tests (spec #43) ---

class TestPhaseConfigInvariants:
    @pytest.mark.parametrize("bad_value", [0, -1, True, "x", 3.5])
    def test_invalid_cycle_minutes(self, bad_value):
        state = _make_phase5_state(0)
        state.data["phase_cycle"]["cycle_minutes"] = bad_value
        with pytest.raises(InvariantError):
            check_invariants(state)

    @pytest.mark.parametrize("bad_value", [0, -1, True, 120, 200])
    def test_invalid_boundary_minute(self, bad_value):
        state = _make_phase5_state(0)
        state.data["phase_cycle"]["boundary_minute"] = bad_value
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_same_phase_ids_rejected(self):
        state = _make_phase5_state(0)
        state.data["phase_cycle"]["phase_after"] = "DAY"
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_empty_phase_before_rejected(self):
        state = _make_phase5_state(0)
        state.data["phase_cycle"]["phase_before"] = ""
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_blocked_actions_not_mapping_rejected(self):
        state = _make_phase5_state(0)
        state.data["phase_cycle"]["blocked_actions_by_phase"] = ["NIGHT"]
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_blocked_action_value_not_string_rejected(self):
        state = _make_phase5_state(0)
        state.data["phase_cycle"]["blocked_actions_by_phase"] = {"NIGHT": [123]}
        with pytest.raises(InvariantError):
            check_invariants(state)


# --- Backward compatibility (spec #42) ---

class TestBackwardCompatibility:
    def test_legacy_state_legal_actions_unchanged(self):
        state = _make_legacy_state(0)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "WAIT" in legal_types
        assert "DROP" in legal_types

    def test_legacy_state_observation_has_no_phase_fields(self):
        state = _make_legacy_state(0)
        obs = build_observation(state)
        assert "world_phase" not in obs
        assert "minutes_until_phase_change" not in obs

    def test_legacy_state_passes_invariants(self):
        state = _make_legacy_state(0)
        check_invariants(state)  # Should not raise

    def test_legacy_wait_produces_same_hash(self):
        """WAIT on legacy state produces deterministic hash."""
        state = _make_legacy_state(0)
        intent = ActionIntent(
            action_id="w1", actor_id="p1", action_type="WAIT",
            params={"minutes": 10},
        )
        result = execute_action(state, intent)
        assert result.accepted is True
        h1 = state_hash(result.final_state.__dict__)

        # Repeat from same initial state
        state2 = _make_legacy_state(0)
        result2 = execute_action(state2, intent)
        h2 = state_hash(result2.final_state.__dict__)
        assert h1 == h2
