"""Phase 7 integrity tests: reducer anti-forgery, invariants, observation isolation."""

import pytest
from tgn.core.models import GameState, DomainEvent
from tgn.core.reducer import reduce_event, ReducerError
from tgn.core.invariants import check_invariants, InvariantError
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import get_legal_actions, execute_action, build_observation
from tgn.actions.models import ActionIntent


PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120, "boundary_minute": 60,
    "phase_before": "DAY", "phase_after": "NIGHT",
    "blocked_actions_by_phase": {"NIGHT": ["DROP"]},
}


def _make_phase7_state(game_minute=0, player_stage=1, base_stage=0,
                       selected=None, inventory=None, stamina=2, max_stamina=5,
                       candidates=None):
    cands = candidates or ["window_runner", "field_rest", "quick_rest"]
    return GameState(
        schema_version=1, event_seq=0, decision_seq=0,
        game_minute=game_minute, seed="phase7-int",
        data={
            "player": {
                "location_id": "base-1", "stamina": stamina,
                "max_stamina": max_stamina, "hp": 10, "max_hp": 10, "attack": 5,
            },
            "inventory": inventory or {},
            "expedition": {
                "active": False, "base_location_id": "base-1",
                "target_location_id": "site-1", "target_searched": False,
                "target_loot": {"salvage": 2, "parts": 1}, "carried_loot": {},
            },
            "phase_cycle": dict(PHASE_CYCLE_CONFIG),
            "progression": {"tracks": {"player": player_stage, "base": base_stage}},
            "progression_gates": {
                "player": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
                "base": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
            },
            "build_choice": {"required_track": "player", "required_stage": 1, "candidates": cands},
            "build": {"selected": selected},
        },
    )


# --- Reducer anti-forgery: BUILD_SELECTED (spec #55) ---

class TestReducerBuildForgery:
    def test_forged_before_trigger(self):
        state = _make_phase7_state(player_stage=0)
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "window_runner", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_unknown_candidate(self):
        state = _make_phase7_state()
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "hacker_build", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_candidate_not_in_two_choice(self):
        state = _make_phase7_state(candidates=["window_runner", "field_rest"])
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "quick_rest", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_second_selection(self):
        state = _make_phase7_state(selected="window_runner")
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "field_rest", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_while_expedition_active(self):
        state = _make_phase7_state()
        state.data["expedition"]["active"] = True
        state.data["player"]["location_id"] = "site-1"
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "window_runner", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_not_at_base(self):
        state = _make_phase7_state()
        state.data["player"]["location_id"] = "site-1"
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "window_runner", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_while_dead(self):
        state = _make_phase7_state()
        state.data["player"]["hp"] = 0
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "window_runner", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_wrong_time(self):
        state = _make_phase7_state()
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=5,
                             decision_seq=1, payload={"build_id": "window_runner", "time": 5})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_wrong_game_minute(self):
        state = _make_phase7_state(game_minute=10)
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=99,
                             decision_seq=1, payload={"build_id": "window_runner", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_legitimate_selection_accepted(self):
        state = _make_phase7_state()
        event = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                            decision_seq=1, payload={"build_id": "window_runner", "time": 1})
        new_state = reduce_event(state, event)
        assert new_state.data["build"]["selected"] == "window_runner"


# --- Reducer anti-forgery: build effects (spec #55) ---

class TestReducerBuildEffectForgery:
    def test_forged_window_runner_drop_insufficient_stamina(self):
        state = _make_phase7_state(game_minute=60, selected="window_runner", stamina=0)
        forged = DomainEvent(event_seq=1, event_type="EXPEDITION_DROPPED", game_minute=70,
                             decision_seq=1, payload={"destination": "site-1", "time": 10, "stamina_cost": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_field_rest_wrong_location(self):
        """field_rest REST at base with expedition active should fail (not at target)."""
        state = _make_phase7_state(selected="field_rest", stamina=2)
        state.data["expedition"]["active"] = True
        state.data["player"]["location_id"] = "base-1"  # at base, not target
        forged = DomainEvent(event_seq=1, event_type="REST_RESOLVED", game_minute=20,
                             decision_seq=1,
                             payload={"stamina_before": 2, "stamina_after": 5, "time": 20})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_quick_rest_with_20_minute_payload(self):
        state = _make_phase7_state(selected="quick_rest", stamina=2)
        forged = DomainEvent(event_seq=1, event_type="REST_RESOLVED", game_minute=20,
                             decision_seq=1,
                             payload={"stamina_before": 2, "stamina_after": 5, "time": 20})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)


# --- Observation authority isolation (spec #54) ---

class TestObservationIsolation:
    def test_legal_action_params_detached(self):
        state = _make_phase7_state(player_stage=1)
        original_hash = state_hash(state.__dict__)
        obs = build_observation(state)
        # Find a CHOOSE_BUILD legal action and mutate its params
        for la in obs["legal_actions"]:
            if la.action_type == "CHOOSE_BUILD":
                la.params["build_id"] = "field_rest"
                break
        # Canonical state unchanged
        assert state_hash(state.__dict__) == original_hash
        assert state.data["build"]["selected"] is None

    def test_observation_build_mutation_no_effect(self):
        state = _make_phase7_state(player_stage=1)
        original_hash = state_hash(state.__dict__)
        obs = build_observation(state)
        obs["build"]["selected"] = "window_runner"
        assert state.data["build"]["selected"] is None
        assert state_hash(state.__dict__) == original_hash


# --- Build config invariants (spec #56) ---

class TestBuildInvariants:
    def test_build_without_build_choice(self):
        state = _make_phase7_state()
        del state.data["build_choice"]
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_build_choice_without_build(self):
        state = _make_phase7_state()
        del state.data["build"]
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_required_track_empty(self):
        state = _make_phase7_state()
        state.data["build_choice"]["required_track"] = ""
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_required_track_not_in_progression(self):
        state = _make_phase7_state()
        state.data["build_choice"]["required_track"] = "ghost_track"
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_required_stage_bool(self):
        state = _make_phase7_state()
        state.data["build_choice"]["required_stage"] = True
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_required_stage_negative(self):
        state = _make_phase7_state()
        state.data["build_choice"]["required_stage"] = -1
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_fewer_than_2_candidates(self):
        state = _make_phase7_state(candidates=["window_runner"])
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_duplicate_candidate(self):
        state = _make_phase7_state(candidates=["window_runner", "window_runner"])
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_empty_candidate_id(self):
        state = _make_phase7_state(candidates=["window_runner", ""])
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_unsupported_candidate(self):
        state = _make_phase7_state(candidates=["window_runner", "mega_build"])
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_selected_not_in_candidates(self):
        state = _make_phase7_state(selected="quick_rest", candidates=["window_runner", "field_rest"])
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_selected_before_trigger(self):
        state = _make_phase7_state(selected="window_runner", player_stage=0)
        with pytest.raises(InvariantError):
            check_invariants(state)


# --- Encounter isolation (spec #29) ---

class TestEncounterIsolation:
    def test_encounter_blocks_choose_build(self):
        state = _make_phase7_state(player_stage=1)
        state.data["player"]["location_id"] = "site-1"
        state.data["expedition"]["active"] = True
        state.data["expedition"]["target_searched"] = True
        state.data["expedition"]["target_loot"] = {}
        state.data["expedition"]["carried_loot"] = {"salvage": 2}
        state.data["expedition"]["encounter"] = {
            "active": True, "enemy_id": "r1", "enemy_hp": 8,
            "enemy_max_hp": 8, "enemy_attack": 3,
        }
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "FIGHT" in legal_types
        assert "FLEE" in legal_types
        assert "CHOOSE_BUILD" not in legal_types
        assert "REST" not in legal_types


# --- Additional reducer coverage ---

class TestReducerAdditionalCoverage:
    def test_forged_build_no_build_choice_config(self):
        state = _make_phase7_state()
        del state.data["build_choice"]
        del state.data["build"]
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "window_runner", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_build_no_progression(self):
        state = _make_phase7_state()
        del state.data["progression"]
        del state.data["progression_gates"]
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "window_runner", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_no_progression(self):
        state = _make_phase7_state(selected="window_runner", stamina=2)
        del state.data["progression"]
        del state.data["progression_gates"]
        forged = DomainEvent(event_seq=1, event_type="REST_RESOLVED", game_minute=20,
                             decision_seq=1,
                             payload={"stamina_before": 2, "stamina_after": 5, "time": 20})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_dead_player(self):
        state = _make_phase7_state(selected="window_runner", stamina=2)
        state.data["player"]["hp"] = 0
        forged = DomainEvent(event_seq=1, event_type="REST_RESOLVED", game_minute=20,
                             decision_seq=1,
                             payload={"stamina_before": 2, "stamina_after": 5, "time": 20})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_stamina_full(self):
        state = _make_phase7_state(selected="window_runner", stamina=5, max_stamina=5)
        forged = DomainEvent(event_seq=1, event_type="REST_RESOLVED", game_minute=20,
                             decision_seq=1,
                             payload={"stamina_before": 5, "stamina_after": 5, "time": 20})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_wrong_stamina_before(self):
        state = _make_phase7_state(selected="window_runner", stamina=2)
        forged = DomainEvent(event_seq=1, event_type="REST_RESOLVED", game_minute=20,
                             decision_seq=1,
                             payload={"stamina_before": 3, "stamina_after": 5, "time": 20})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_wrong_stamina_after(self):
        state = _make_phase7_state(selected="window_runner", stamina=2)
        forged = DomainEvent(event_seq=1, event_type="REST_RESOLVED", game_minute=20,
                             decision_seq=1,
                             payload={"stamina_before": 2, "stamina_after": 3, "time": 20})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_rest_wrong_game_minute(self):
        state = _make_phase7_state(selected="window_runner", stamina=2, game_minute=10)
        forged = DomainEvent(event_seq=1, event_type="REST_RESOLVED", game_minute=99,
                             decision_seq=1,
                             payload={"stamina_before": 2, "stamina_after": 5, "time": 20})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)

    def test_forged_build_active_encounter(self):
        state = _make_phase7_state()
        state.data["expedition"]["encounter"] = {"active": True, "enemy_id": "e", "enemy_hp": 5,
                                                  "enemy_max_hp": 5, "enemy_attack": 2}
        forged = DomainEvent(event_seq=1, event_type="BUILD_SELECTED", game_minute=1,
                             decision_seq=1, payload={"build_id": "window_runner", "time": 1})
        with pytest.raises(ReducerError):
            reduce_event(state, forged)


# --- Build choice helper edge cases ---

class TestBuildHelperEdgeCases:
    def test_build_choice_not_available_without_progression(self):
        state = _make_phase7_state()
        del state.data["progression"]
        del state.data["progression_gates"]
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "CHOOSE_BUILD" not in legal_types

    def test_build_choice_not_available_track_missing(self):
        state = _make_phase7_state()
        state.data["build_choice"]["required_track"] = "ghost"
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "CHOOSE_BUILD" not in legal_types
