"""Phase 6 scenario tests: resource acquisition, phase interaction, backward compat."""

import pytest
from tgn.core.models import GameState
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import (
    get_legal_actions,
    execute_action,
    build_observation,
)
from tgn.actions.models import ActionIntent


PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120,
    "boundary_minute": 60,
    "phase_before": "DAY",
    "phase_after": "NIGHT",
    "blocked_actions_by_phase": {"NIGHT": ["DROP"]},
}


def _make_phase6_state(game_minute: int = 0, **kwargs) -> GameState:
    inventory = kwargs.get("inventory", {})
    player_stage = kwargs.get("player_stage", 0)
    base_stage = kwargs.get("base_stage", 0)
    stamina = kwargs.get("stamina", 3)
    max_stamina = kwargs.get("max_stamina", 5)
    return GameState(
        schema_version=1, event_seq=0, decision_seq=0,
        game_minute=game_minute, seed="phase6-scenario",
        data={
            "player": {
                "location_id": "base-1", "stamina": stamina,
                "max_stamina": max_stamina, "hp": 10, "max_hp": 10, "attack": 5,
            },
            "inventory": inventory,
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
        },
    )


# --- Resource acquisition through existing expedition loop (spec #40) ---

class TestResourceAcquisition:
    def test_expedition_loop_earns_gate_resources(self):
        """DROP → SEARCH → EXTRACT earns salvage+parts, enabling upgrade."""
        state = _make_phase6_state(game_minute=0, stamina=5, max_stamina=5)

        # DROP
        r1 = execute_action(state, ActionIntent(
            action_id="d1", actor_id="p1", action_type="DROP", params={}))
        assert r1.accepted
        state = r1.final_state

        # SEARCH
        r2 = execute_action(state, ActionIntent(
            action_id="s1", actor_id="p1", action_type="SEARCH", params={}))
        assert r2.accepted
        state = r2.final_state

        # EXTRACT
        r3 = execute_action(state, ActionIntent(
            action_id="e1", actor_id="p1", action_type="EXTRACT", params={}))
        assert r3.accepted
        state = r3.final_state

        # Now at base with salvage=2, parts=1 in inventory
        assert state.data["inventory"]["salvage"] == 2
        assert state.data["inventory"]["parts"] == 1

        # UPGRADE_PLAYER now legal
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_PLAYER" in legal_types


# --- Progression / phase interaction (spec #50) ---

class TestProgressionPhaseInteraction:
    def test_upgrade_crossing_day_to_night_accepted(self):
        """UPGRADE_PLAYER at minute 55 (DAY) crosses to 60 (NIGHT), remains accepted."""
        state = _make_phase6_state(
            game_minute=55, inventory={"salvage": 2, "parts": 1}
        )
        intent = ActionIntent(
            action_id="up1", actor_id="p1", action_type="UPGRADE_PLAYER", params={}
        )
        result = execute_action(state, intent)
        assert result.accepted is True
        new_state = result.final_state
        assert new_state.game_minute == 60
        assert new_state.data["progression"]["tracks"]["player"] == 1
        # Phase is now NIGHT
        obs = build_observation(new_state)
        assert obs["world_phase"] == "NIGHT"


# --- Phase 5 regression compatibility (spec #49) ---

class TestPhase5RegressionCompat:
    def test_phase5_night_state_without_progression_blocks_drop(self):
        """Normal Phase 5 NIGHT state with no progression still blocks DROP."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0,
            game_minute=60, seed="phase5-compat",
            data={
                "player": {
                    "location_id": "base-1", "stamina": 3, "max_stamina": 3,
                    "hp": 10, "max_hp": 10, "attack": 5,
                },
                "inventory": {},
                "expedition": {
                    "active": False, "base_location_id": "base-1",
                    "target_location_id": "site-1", "target_searched": False,
                    "target_loot": {"salvage": 2}, "carried_loot": {},
                },
                "phase_cycle": dict(PHASE_CYCLE_CONFIG),
            },
        )
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types

    def test_legacy_state_unchanged_by_phase6(self):
        """Pre-Phase-6 state legal actions remain unchanged."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0,
            game_minute=0, seed="legacy",
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
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "WAIT" in legal_types
        assert "DROP" in legal_types
        assert "UPGRADE_PLAYER" not in legal_types
        assert "REST" not in legal_types
