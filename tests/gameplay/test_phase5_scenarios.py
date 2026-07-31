"""Phase 5 behavioral scenario tests: boundary crossing, isolation, window reopening."""

import pytest
from tgn.core.models import GameState, DomainEvent
from tgn.core.reducer import reduce_event, ReducerError
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


def _make_encounter_state(game_minute: int) -> GameState:
    """Phase 5 state with active encounter (Phase 4 contract)."""
    return GameState(
        schema_version=1,
        event_seq=5,
        decision_seq=5,
        game_minute=game_minute,
        seed="phase5-encounter",
        data={
            "player": {
                "location_id": "site-1",
                "stamina": 3,
                "max_stamina": 3,
                "hp": 10,
                "max_hp": 10,
                "attack": 5,
            },
            "inventory": {},
            "expedition": {
                "active": True,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": True,
                "target_loot": {},
                "carried_loot": {"salvage": 2},
                "encounter": {
                    "active": True,
                    "enemy_id": "raider-1",
                    "enemy_hp": 8,
                    "enemy_max_hp": 8,
                    "enemy_attack": 3,
                },
            },
            "phase_cycle": dict(PHASE_CYCLE_CONFIG),
        },
    )


# --- Start-time legality boundary test (spec #37) ---

class TestStartTimeLegality:
    def test_drop_started_before_boundary_can_finish_after_boundary(self):
        """DROP at minute 55 (DAY) is legal even though it ends at 65 (NIGHT)."""
        state = _make_phase5_state(55)
        intent = ActionIntent(
            action_id="a1", actor_id="p1", action_type="DROP", params={}
        )
        result = execute_action(state, intent)
        assert result.accepted is True
        assert result.final_state is not None
        assert result.final_state.game_minute == 65
        # Derived phase at 65 is NIGHT, but action was accepted
        obs = build_observation(result.final_state)
        assert obs["world_phase"] == "NIGHT"


# --- Reopen-window test (spec #38) ---

class TestWindowReopening:
    def test_phase_cycle_reopens_drop_opportunity(self):
        """WAIT from NIGHT to next DAY reopens DROP."""
        state = _make_phase5_state(65)  # NIGHT
        # DROP blocked
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types

        # WAIT 55 minutes to reach 120 (DAY)
        intent = ActionIntent(
            action_id="w1", actor_id="p1", action_type="WAIT",
            params={"minutes": 55},
        )
        result = execute_action(state, intent)
        assert result.accepted is True
        new_state = result.final_state
        assert new_state.game_minute == 120

        # DROP legal again
        legal_types = [la.action_type for la in get_legal_actions(new_state)]
        assert "DROP" in legal_types


# --- Encounter isolation tests (spec #39) ---

class TestEncounterIsolation:
    def test_phase_config_does_not_change_active_encounter_actions_day(self):
        state = _make_encounter_state(30)  # DAY
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "FIGHT" in legal_types
        assert "FLEE" in legal_types
        assert "WAIT" not in legal_types
        assert "DROP" not in legal_types
        assert "SEARCH" not in legal_types

    def test_phase_config_does_not_change_active_encounter_actions_night(self):
        state = _make_encounter_state(90)  # NIGHT
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "FIGHT" in legal_types
        assert "FLEE" in legal_types
        assert "WAIT" not in legal_types
        assert "DROP" not in legal_types
        assert "SEARCH" not in legal_types


# --- Death isolation test (spec #40) ---

class TestDeathIsolation:
    def test_dead_player_gets_no_actions_with_phase_config(self):
        state = _make_phase5_state(0)  # DAY
        state.data["player"]["hp"] = 0
        legal = get_legal_actions(state)
        assert legal == ()


# --- WAIT bypass protection (spec #41) ---

class TestWaitEncounterProtection:
    def test_wait_rejected_during_encounter_with_phase_config(self):
        state = _make_encounter_state(30)
        intent = ActionIntent(
            action_id="w1", actor_id="p1", action_type="WAIT",
            params={"minutes": 10},
        )
        result = execute_action(state, intent)
        assert result.accepted is False

    def test_forged_time_advanced_rejected_during_encounter(self):
        state = _make_encounter_state(30)
        forged = DomainEvent(
            event_seq=6,
            event_type="TIME_ADVANCED",
            game_minute=40,
            decision_seq=6,
            payload={"minutes": 10},
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged)


# --- No PHASE_CHANGED event test (spec #49) ---

class TestNoPhaseChangedEvent:
    def test_wait_across_boundary_produces_only_time_advanced(self):
        state = _make_phase5_state(55)
        intent = ActionIntent(
            action_id="w1", actor_id="p1", action_type="WAIT",
            params={"minutes": 10},
        )
        result = execute_action(state, intent)
        assert result.accepted is True
        assert len(result.events) == 1
        assert result.events[0].event_type == "TIME_ADVANCED"

    def test_drop_across_boundary_produces_only_expedition_dropped(self):
        state = _make_phase5_state(55)
        intent = ActionIntent(
            action_id="a1", actor_id="p1", action_type="DROP", params={}
        )
        result = execute_action(state, intent)
        assert result.accepted is True
        assert len(result.events) == 1
        assert result.events[0].event_type == "EXPEDITION_DROPPED"


# --- Action-option mismatch (spec #50) ---

class TestActionOptionMismatch:
    def test_night_drop_hidden_and_rejected(self):
        state = _make_phase5_state(60)
        # Not in legal actions
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types
        # Direct validation also rejects
        intent = ActionIntent(
            action_id="a1", actor_id="p1", action_type="DROP", params={}
        )
        result = validate_action(state, intent)
        assert result.valid is False

    def test_day_drop_shown_and_accepted(self):
        state = _make_phase5_state(0)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" in legal_types
        intent = ActionIntent(
            action_id="a1", actor_id="p1", action_type="DROP", params={}
        )
        result = validate_action(state, intent)
        assert result.valid is True


# --- Phase config does not bypass other legality (spec #51) ---

class TestPhaseDoesNotBypassOtherLegality:
    def test_day_does_not_force_drop_when_stamina_insufficient(self):
        state = _make_phase5_state(0)  # DAY
        state.data["player"]["stamina"] = 0
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types

    def test_day_does_not_force_drop_when_target_searched(self):
        state = _make_phase5_state(0)  # DAY
        state.data["expedition"]["target_searched"] = True
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types
