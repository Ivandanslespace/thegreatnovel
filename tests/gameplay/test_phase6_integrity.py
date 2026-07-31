"""Phase 6 integrity tests: reducer anti-forgery, invariants, isolation."""

import pytest
from tgn.core.models import GameState, DomainEvent
from tgn.core.reducer import reduce_event, ReducerError
from tgn.core.invariants import check_invariants, InvariantError
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import get_legal_actions, execute_action
from tgn.actions.models import ActionIntent


PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120,
    "boundary_minute": 60,
    "phase_before": "DAY",
    "phase_after": "NIGHT",
    "blocked_actions_by_phase": {"NIGHT": ["DROP"]},
}


def _make_phase6_state(
    game_minute: int = 0,
    inventory: dict | None = None,
    player_stage: int = 0,
    base_stage: int = 0,
    stamina: int = 3,
    max_stamina: int = 5,
    event_seq: int = 0,
    decision_seq: int = 0,
) -> GameState:
    return GameState(
        schema_version=1,
        event_seq=event_seq,
        decision_seq=decision_seq,
        game_minute=game_minute,
        seed="phase6-test",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": stamina,
                "max_stamina": max_stamina,
                "hp": 10,
                "max_hp": 10,
                "attack": 5,
            },
            "inventory": inventory if inventory is not None else {},
            "expedition": {
                "active": False,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": False,
                "target_loot": {"salvage": 2, "parts": 1},
                "carried_loot": {},
            },
            "phase_cycle": dict(PHASE_CYCLE_CONFIG),
            "progression": {
                "tracks": {"player": player_stage, "base": base_stage},
            },
            "progression_gates": {
                "player": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
                "base": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
            },
        },
    )


def _make_encounter_state(game_minute: int = 30) -> GameState:
    """Phase 6 state with active encounter."""
    state = _make_phase6_state(game_minute=game_minute, inventory={"salvage": 4, "parts": 2})
    state.data["player"]["location_id"] = "site-1"
    state.data["expedition"]["active"] = True
    state.data["expedition"]["target_searched"] = True
    state.data["expedition"]["target_loot"] = {}
    state.data["expedition"]["carried_loot"] = {"salvage": 2}
    state.data["expedition"]["encounter"] = {
        "active": True,
        "enemy_id": "raider-1",
        "enemy_hp": 8,
        "enemy_max_hp": 8,
        "enemy_attack": 3,
    }
    return state


# --- Reducer anti-forgery: progression (spec #27, #57) ---

class TestReducerAntiForgeryProgression:
    def test_forged_player_progression_without_resources(self):
        state = _make_phase6_state(inventory={})
        forged = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 2, "parts": 1}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_base_progression_without_resources(self):
        state = _make_phase6_state(inventory={})
        forged = DomainEvent(
            event_seq=1, event_type="BASE_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 2, "parts": 1}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_wrong_resource_cost(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        forged = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 99}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_wrong_to_stage(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        forged = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 5, "resource_cost": {"salvage": 2, "parts": 1}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_duplicate_progression(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1}, player_stage=1)
        forged = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 2, "parts": 1}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_legitimate_player_progression_accepted(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        event = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 2, "parts": 1}, "time": 5},
        )
        new_state = reduce_event(state, event)
        assert new_state.data["progression"]["tracks"]["player"] == 1


# --- Reducer anti-forgery: REST (spec #28, #57) ---

class TestReducerAntiForgeryRest:
    def test_forged_rest_before_player_progression(self):
        state = _make_phase6_state(stamina=2, player_stage=0)
        forged = DomainEvent(
            event_seq=1, event_type="REST_RESOLVED",
            game_minute=20, decision_seq=1,
            payload={"stamina_before": 2, "stamina_after": 5, "time": 20},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_wrong_stamina_result(self):
        state = _make_phase6_state(stamina=2, player_stage=1)
        forged = DomainEvent(
            event_seq=1, event_type="REST_RESOLVED",
            game_minute=20, decision_seq=1,
            payload={"stamina_before": 2, "stamina_after": 3, "time": 20},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_stamina_already_full(self):
        state = _make_phase6_state(stamina=5, max_stamina=5, player_stage=1)
        forged = DomainEvent(
            event_seq=1, event_type="REST_RESOLVED",
            game_minute=20, decision_seq=1,
            payload={"stamina_before": 5, "stamina_after": 5, "time": 20},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_legitimate_rest_accepted(self):
        state = _make_phase6_state(stamina=2, max_stamina=5, player_stage=1)
        event = DomainEvent(
            event_seq=1, event_type="REST_RESOLVED",
            game_minute=20, decision_seq=1,
            payload={"stamina_before": 2, "stamina_after": 5, "time": 20},
        )
        new_state = reduce_event(state, event)
        assert new_state.data["player"]["stamina"] == 5


# --- Reducer anti-forgery: NIGHT DROP (spec #29) ---

class TestReducerNightDropOverride:
    def test_forged_night_drop_before_base_progression(self):
        state = _make_phase6_state(game_minute=60, base_stage=0)  # NIGHT
        forged = DomainEvent(
            event_seq=1, event_type="EXPEDITION_DROPPED",
            game_minute=70, decision_seq=1,
            payload={"destination": "site-1", "time": 10, "stamina_cost": 1},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_legitimate_night_drop_after_base_progression(self):
        state = _make_phase6_state(game_minute=60, base_stage=1)  # NIGHT, base=1
        event = DomainEvent(
            event_seq=1, event_type="EXPEDITION_DROPPED",
            game_minute=70, decision_seq=1,
            payload={"destination": "site-1", "time": 10, "stamina_cost": 1},
        )
        new_state = reduce_event(state, event)
        assert new_state.data["expedition"]["active"] is True


# --- Encounter isolation (spec #31) ---

class TestEncounterIsolation:
    def test_encounter_blocks_all_phase6_actions(self):
        state = _make_encounter_state()
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "FIGHT" in legal_types
        assert "FLEE" in legal_types
        assert "UPGRADE_PLAYER" not in legal_types
        assert "UPGRADE_BASE" not in legal_types
        assert "REST" not in legal_types
        assert "WAIT" not in legal_types
        assert "DROP" not in legal_types


# --- Death isolation (spec #32) ---

class TestDeathIsolation:
    def test_dead_player_no_actions_with_progression(self):
        state = _make_phase6_state(inventory={"salvage": 4, "parts": 2})
        state.data["player"]["hp"] = 0
        assert get_legal_actions(state) == ()


# --- Progression invariants (spec #36) ---

class TestProgressionInvariants:
    def test_invalid_stage_bool(self):
        state = _make_phase6_state()
        state.data["progression"]["tracks"]["player"] = True
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_invalid_stage_negative(self):
        state = _make_phase6_state()
        state.data["progression"]["tracks"]["player"] = -1
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_gate_to_stage_not_from_plus_one(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["player"]["to_stage"] = 5
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_gate_cost_empty_rejected(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["player"]["cost"] = {}
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_gate_cost_quantity_bool_rejected(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["player"]["cost"] = {"salvage": True}
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_progression_without_gates_rejected(self):
        state = _make_phase6_state()
        del state.data["progression_gates"]
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_gates_without_progression_rejected(self):
        state = _make_phase6_state()
        del state.data["progression"]
        with pytest.raises(InvariantError):
            check_invariants(state)


# --- Zero side-effect on rejection (spec #58) ---

class TestZeroSideEffect:
    def test_rejected_upgrade_no_side_effect(self):
        state = _make_phase6_state(inventory={})
        original_hash = state_hash(state.__dict__)
        intent = ActionIntent(
            action_id="up1", actor_id="p1", action_type="UPGRADE_PLAYER", params={}
        )
        result = execute_action(state, intent)
        assert result.accepted is False
        assert result.events == ()
        assert result.final_state is None
        assert state_hash(state.__dict__) == original_hash


# --- Additional reducer anti-forgery coverage ---

class TestReducerAdditionalForgery:
    def test_forged_progression_not_at_base(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        state.data["player"]["location_id"] = "site-1"
        state.data["expedition"]["active"] = True
        forged = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 2, "parts": 1}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_progression_expedition_active(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        state.data["expedition"]["active"] = True
        state.data["player"]["location_id"] = "site-1"
        forged = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 2, "parts": 1}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_progression_dead_player(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        state.data["player"]["hp"] = 0
        forged = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 2, "parts": 1}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_progression_wrong_time(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        forged = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=10, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 2, "parts": 1}, "time": 10},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_progression_no_progression_config(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        del state.data["progression"]
        del state.data["progression_gates"]
        forged = DomainEvent(
            event_seq=1, event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"salvage": 2, "parts": 1}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_not_at_base(self):
        state = _make_phase6_state(stamina=2, player_stage=1)
        state.data["player"]["location_id"] = "site-1"
        state.data["expedition"]["active"] = True
        forged = DomainEvent(
            event_seq=1, event_type="REST_RESOLVED",
            game_minute=20, decision_seq=1,
            payload={"stamina_before": 2, "stamina_after": 5, "time": 20},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_dead_player(self):
        state = _make_phase6_state(stamina=2, player_stage=1)
        state.data["player"]["hp"] = 0
        forged = DomainEvent(
            event_seq=1, event_type="REST_RESOLVED",
            game_minute=20, decision_seq=1,
            payload={"stamina_before": 2, "stamina_after": 5, "time": 20},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_wrong_time(self):
        state = _make_phase6_state(stamina=2, player_stage=1)
        forged = DomainEvent(
            event_seq=1, event_type="REST_RESOLVED",
            game_minute=10, decision_seq=1,
            payload={"stamina_before": 2, "stamina_after": 5, "time": 10},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_no_progression(self):
        state = _make_phase6_state(stamina=2, player_stage=1)
        del state.data["progression"]
        del state.data["progression_gates"]
        forged = DomainEvent(
            event_seq=1, event_type="REST_RESOLVED",
            game_minute=20, decision_seq=1,
            payload={"stamina_before": 2, "stamina_after": 5, "time": 20},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_base_progression_wrong_cost(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        forged = DomainEvent(
            event_seq=1, event_type="BASE_PROGRESSION_ADVANCED",
            game_minute=5, decision_seq=1,
            payload={"from_stage": 0, "to_stage": 1, "resource_cost": {"gold": 99}, "time": 5},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)


# --- Additional invariant coverage ---

class TestAdditionalInvariants:
    def test_progression_not_dict(self):
        state = _make_phase6_state()
        state.data["progression"] = "invalid"
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_tracks_not_dict(self):
        state = _make_phase6_state()
        state.data["progression"]["tracks"] = [1, 2]
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_track_id_empty_string(self):
        state = _make_phase6_state()
        state.data["progression"]["tracks"][""] = 0
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_stage_not_int(self):
        state = _make_phase6_state()
        state.data["progression"]["tracks"]["player"] = "zero"
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_gates_not_dict(self):
        state = _make_phase6_state()
        state.data["progression_gates"] = []
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_gate_refers_nonexistent_track(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["ghost"] = {
            "from_stage": 0, "to_stage": 1, "cost": {"x": 1}
        }
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_gate_not_dict(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["player"] = "bad"
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_from_stage_bool(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["player"]["from_stage"] = False
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_to_stage_bool(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["player"]["to_stage"] = True
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_cost_resource_empty_string(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["player"]["cost"] = {"": 1}
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_cost_quantity_zero(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["player"]["cost"] = {"salvage": 0}
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_cost_quantity_not_int(self):
        state = _make_phase6_state()
        state.data["progression_gates"]["player"]["cost"] = {"salvage": 2.5}
        with pytest.raises(InvariantError):
            check_invariants(state)
