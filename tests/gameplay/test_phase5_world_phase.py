"""Phase 5 world phase calculation and legality divergence tests."""

import pytest
from tgn.core.models import GameState
from tgn.gameplay.world_phase import (
    get_current_phase,
    minutes_until_phase_change,
    is_action_blocked_by_phase,
)
from tgn.gameplay.expedition import get_legal_actions, build_observation


# Phase 5 minimal configuration fixture (CableCar first-world test values)
PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120,
    "boundary_minute": 60,
    "phase_before": "DAY",
    "phase_after": "NIGHT",
    "blocked_actions_by_phase": {
        "NIGHT": ["DROP"],
    },
}


def _make_phase5_state(game_minute: int, **overrides) -> GameState:
    """Build a Phase-5-enabled state at given game_minute."""
    data = {
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
    }
    data.update(overrides)
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=game_minute,
        seed="phase5-test",
        data=data,
    )


# --- Phase calculation tests (spec #32) ---

class TestPhaseCalculation:
    def test_before_boundary_is_day(self):
        state = _make_phase5_state(59)
        assert get_current_phase(state) == "DAY"

    def test_exact_boundary_is_night(self):
        state = _make_phase5_state(60)
        assert get_current_phase(state) == "NIGHT"

    def test_before_cycle_wrap_is_night(self):
        state = _make_phase5_state(119)
        assert get_current_phase(state) == "NIGHT"

    def test_cycle_wrap_is_day(self):
        state = _make_phase5_state(120)
        assert get_current_phase(state) == "DAY"

    def test_multiple_cycles(self):
        state = _make_phase5_state(180)
        assert get_current_phase(state) == "NIGHT"

    def test_zero_is_day(self):
        state = _make_phase5_state(0)
        assert get_current_phase(state) == "DAY"

    def test_no_phase_config_returns_none(self):
        """Pre-Phase-5 state without phase_cycle returns None."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0,
            game_minute=50, seed="legacy",
            data={
                "player": {"location_id": "base-1", "stamina": 3, "max_stamina": 3},
                "inventory": {},
                "expedition": {
                    "active": False, "base_location_id": "base-1",
                    "target_location_id": "site-1", "target_searched": False,
                    "target_loot": {"salvage": 2}, "carried_loot": {},
                },
            },
        )
        assert get_current_phase(state) is None


# --- Minutes-until-change tests (spec #33) ---

class TestMinutesUntilChange:
    def test_minute_55_day_next_in_5(self):
        state = _make_phase5_state(55)
        assert minutes_until_phase_change(state) == 5

    def test_minute_60_night_next_in_60(self):
        state = _make_phase5_state(60)
        assert minutes_until_phase_change(state) == 60

    def test_minute_119_night_next_in_1(self):
        state = _make_phase5_state(119)
        assert minutes_until_phase_change(state) == 1

    def test_minute_120_day_next_in_60(self):
        state = _make_phase5_state(120)
        assert minutes_until_phase_change(state) == 60

    def test_no_phase_config_returns_none(self):
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0,
            game_minute=50, seed="legacy", data={},
        )
        assert minutes_until_phase_change(state) is None


# --- Legal action divergence tests (spec #34) ---

class TestLegalActionDivergence:
    def test_day_offers_drop(self):
        state = _make_phase5_state(0)  # DAY
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "WAIT" in legal_types
        assert "DROP" in legal_types

    def test_night_blocks_drop(self):
        state = _make_phase5_state(60)  # NIGHT
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "WAIT" in legal_types
        assert "DROP" not in legal_types

    def test_phase_does_not_affect_search_at_target(self):
        """Phase blocking DROP does not block SEARCH at target."""
        state = _make_phase5_state(60)  # NIGHT
        # Put player at target with active expedition
        state.data["expedition"]["active"] = True
        state.data["player"]["location_id"] = "site-1"
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "SEARCH" in legal_types
        assert "EXTRACT" in legal_types


# --- Observation tests (spec #44) ---

class TestObservation:
    def test_day_observation_exposes_phase(self):
        state = _make_phase5_state(55)
        obs = build_observation(state)
        assert obs["world_phase"] == "DAY"
        assert obs["minutes_until_phase_change"] == 5

    def test_night_observation_exposes_phase(self):
        state = _make_phase5_state(65)
        obs = build_observation(state)
        assert obs["world_phase"] == "NIGHT"
        assert obs["minutes_until_phase_change"] == 55

    def test_observation_does_not_leak_config(self):
        state = _make_phase5_state(55)
        obs = build_observation(state)
        assert "blocked_actions_by_phase" not in obs
        assert "phase_cycle" not in obs

    def test_no_phase_config_no_phase_fields(self):
        """Pre-Phase-5 state observation has no world_phase fields."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0,
            game_minute=50, seed="legacy",
            data={
                "player": {"location_id": "base-1", "stamina": 3, "max_stamina": 3},
                "inventory": {},
                "expedition": {
                    "active": False, "base_location_id": "base-1",
                    "target_location_id": "site-1", "target_searched": False,
                    "target_loot": {"salvage": 2}, "carried_loot": {},
                },
            },
        )
        obs = build_observation(state)
        assert "world_phase" not in obs
        assert "minutes_until_phase_change" not in obs
