"""Phase 6 progression gate reachability, atomic advancement, and strategy-unlock tests.

RED tests use ONLY existing public APIs (get_legal_actions, validate_action,
execute_action, build_observation). No import from tgn.gameplay.progression.
"""

import pytest
from tgn.core.models import GameState
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import (
    get_legal_actions,
    validate_action,
    execute_action,
    build_observation,
)
from tgn.actions.models import ActionIntent


# Phase 6 minimal configuration (CableCar first-world test values)
PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120,
    "boundary_minute": 60,
    "phase_before": "DAY",
    "phase_after": "NIGHT",
    "blocked_actions_by_phase": {
        "NIGHT": ["DROP"],
    },
}

PROGRESSION_CONFIG = {
    "tracks": {"player": 0, "base": 0},
}

PROGRESSION_GATES_CONFIG = {
    "player": {
        "from_stage": 0,
        "to_stage": 1,
        "cost": {"salvage": 2, "parts": 1},
    },
    "base": {
        "from_stage": 0,
        "to_stage": 1,
        "cost": {"salvage": 2, "parts": 1},
    },
}


def _make_phase6_state(
    game_minute: int = 0,
    inventory: dict | None = None,
    player_stage: int = 0,
    base_stage: int = 0,
    stamina: int = 3,
    max_stamina: int = 5,
) -> GameState:
    """Build a Phase-6-enabled state with progression config."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
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
                "player": dict(PROGRESSION_GATES_CONFIG["player"]),
                "base": dict(PROGRESSION_GATES_CONFIG["base"]),
            },
        },
    )


# --- Gate reachability tests (spec #39) ---

class TestGateReachability:
    def test_no_resources_upgrade_absent(self):
        state = _make_phase6_state(inventory={})
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_PLAYER" not in legal_types
        assert "UPGRADE_BASE" not in legal_types

    def test_only_resource_x_upgrade_absent(self):
        state = _make_phase6_state(inventory={"salvage": 5})
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_PLAYER" not in legal_types
        assert "UPGRADE_BASE" not in legal_types

    def test_only_resource_y_upgrade_absent(self):
        state = _make_phase6_state(inventory={"parts": 5})
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_PLAYER" not in legal_types
        assert "UPGRADE_BASE" not in legal_types

    def test_exact_resources_upgrade_legal(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_PLAYER" in legal_types
        assert "UPGRADE_BASE" in legal_types

    def test_excess_resources_upgrade_legal(self):
        state = _make_phase6_state(inventory={"salvage": 10, "parts": 5})
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_PLAYER" in legal_types
        assert "UPGRADE_BASE" in legal_types


# --- Atomic player progression test (spec #41) ---

class TestAtomicPlayerProgression:
    def test_player_progression_advances_track(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        original_hash = state_hash(state.__dict__)
        intent = ActionIntent(
            action_id="up1", actor_id="p1", action_type="UPGRADE_PLAYER", params={}
        )
        result = execute_action(state, intent)
        assert result.accepted is True
        assert len(result.events) == 1
        assert result.events[0].event_type == "PLAYER_PROGRESSION_ADVANCED"

        new_state = result.final_state
        assert new_state.data["progression"]["tracks"]["player"] == 1
        assert new_state.data["progression"]["tracks"]["base"] == 0
        assert new_state.data["inventory"] == {}
        assert new_state.game_minute == 5
        assert new_state.event_seq == 1
        assert new_state.decision_seq == 1
        # Original state unchanged
        assert state_hash(state.__dict__) == original_hash


# --- Atomic base progression test (spec #42) ---

class TestAtomicBaseProgression:
    def test_base_progression_advances_track(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        intent = ActionIntent(
            action_id="ub1", actor_id="p1", action_type="UPGRADE_BASE", params={}
        )
        result = execute_action(state, intent)
        assert result.accepted is True
        assert result.events[0].event_type == "BASE_PROGRESSION_ADVANCED"

        new_state = result.final_state
        assert new_state.data["progression"]["tracks"]["base"] == 1
        assert new_state.data["progression"]["tracks"]["player"] == 0
        assert new_state.data["inventory"] == {}
        assert new_state.game_minute == 5


# --- Duplicate advancement must fail (spec #43) ---

class TestDuplicateProgression:
    def test_player_upgrade_absent_after_advancement(self):
        state = _make_phase6_state(
            inventory={"salvage": 4, "parts": 2}, player_stage=1
        )
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_PLAYER" not in legal_types

    def test_base_upgrade_absent_after_advancement(self):
        state = _make_phase6_state(
            inventory={"salvage": 4, "parts": 2}, base_stage=1
        )
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_BASE" not in legal_types

    def test_direct_duplicate_player_upgrade_rejected(self):
        state = _make_phase6_state(
            inventory={"salvage": 4, "parts": 2}, player_stage=1
        )
        intent = ActionIntent(
            action_id="up1", actor_id="p1", action_type="UPGRADE_PLAYER", params={}
        )
        result = execute_action(state, intent)
        assert result.accepted is False
        assert result.events == ()
        assert result.final_state is None


# --- Player progression strategy-unlock: REST (spec #44) ---

class TestPlayerProgressionUnlocksRest:
    def test_rest_absent_before_player_progression(self):
        state = _make_phase6_state(stamina=2, max_stamina=5, player_stage=0)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "REST" not in legal_types

    def test_rest_legal_after_player_progression(self):
        state = _make_phase6_state(stamina=2, max_stamina=5, player_stage=1)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "REST" in legal_types

    def test_rest_absent_when_stamina_full(self):
        state = _make_phase6_state(stamina=5, max_stamina=5, player_stage=1)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "REST" not in legal_types


# --- REST behavioral test (spec #45) ---

class TestRestBehavior:
    def test_rest_restores_stamina(self):
        state = _make_phase6_state(stamina=2, max_stamina=5, player_stage=1)
        intent = ActionIntent(
            action_id="r1", actor_id="p1", action_type="REST", params={}
        )
        result = execute_action(state, intent)
        assert result.accepted is True
        assert len(result.events) == 1
        assert result.events[0].event_type == "REST_RESOLVED"

        new_state = result.final_state
        assert new_state.data["player"]["stamina"] == 5
        assert new_state.game_minute == 20
        # HP unchanged, inventory unchanged, progression unchanged
        assert new_state.data["player"]["hp"] == 10
        assert new_state.data["progression"]["tracks"]["player"] == 1


# --- Base progression strategy-unlock: NIGHT DROP (spec #47) ---

class TestBaseProgressionUnlocksNightDrop:
    def test_night_drop_blocked_before_base_progression(self):
        state = _make_phase6_state(game_minute=60, base_stage=0)  # NIGHT
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types

    def test_night_drop_legal_after_base_progression(self):
        state = _make_phase6_state(game_minute=60, base_stage=1)  # NIGHT
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" in legal_types

    def test_base_progression_does_not_bypass_stamina(self):
        state = _make_phase6_state(game_minute=60, base_stage=1, stamina=0)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types

    def test_base_progression_does_not_bypass_target_searched(self):
        state = _make_phase6_state(game_minute=60, base_stage=1)
        state.data["expedition"]["target_searched"] = True
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types


# --- Observation progression contract (spec #33) ---

class TestObservationProgression:
    def test_observation_exposes_progression_summary(self):
        state = _make_phase6_state(inventory={"salvage": 2, "parts": 1})
        obs = build_observation(state)
        assert "progression" in obs
        assert obs["progression"]["tracks"]["player"]["stage"] == 0
        assert obs["progression"]["tracks"]["player"]["next_cost"] == {"salvage": 2, "parts": 1}
        assert obs["progression"]["tracks"]["base"]["stage"] == 0

    def test_observation_after_advancement_shows_stage_1(self):
        state = _make_phase6_state(player_stage=1, base_stage=1)
        obs = build_observation(state)
        assert obs["progression"]["tracks"]["player"]["stage"] == 1
        assert obs["progression"]["tracks"]["base"]["stage"] == 1

    def test_legacy_state_no_progression_field(self):
        """Pre-Phase-6 state has no progression observation field."""
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
        obs = build_observation(state)
        assert "progression" not in obs


# --- Progression helper edge cases (coverage) ---

class TestProgressionHelperEdgeCases:
    def test_upgrade_absent_when_no_gate_for_track(self):
        """Track exists but no gate defined → upgrade absent."""
        state = _make_phase6_state(inventory={"salvage": 99, "parts": 99})
        del state.data["progression_gates"]["player"]
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_PLAYER" not in legal_types
        assert "UPGRADE_BASE" in legal_types

    def test_upgrade_absent_when_stage_past_gate(self):
        """Stage already past gate.from_stage → upgrade absent."""
        state = _make_phase6_state(inventory={"salvage": 99, "parts": 99}, player_stage=1)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "UPGRADE_PLAYER" not in legal_types

    def test_observation_next_cost_none_after_advancement(self):
        state = _make_phase6_state(player_stage=1, base_stage=1)
        obs = build_observation(state)
        assert obs["progression"]["tracks"]["player"]["next_cost"] is None
        assert obs["progression"]["tracks"]["base"]["next_cost"] is None
