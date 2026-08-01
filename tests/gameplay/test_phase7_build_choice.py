"""Phase 7 build choice tests: trigger, binding, selection, permanence, strategy effects."""

import pytest
from tgn.core.models import GameState
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import (
    get_legal_actions, validate_action, execute_action, build_observation,
)
from tgn.actions.models import ActionIntent


PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120, "boundary_minute": 60,
    "phase_before": "DAY", "phase_after": "NIGHT",
    "blocked_actions_by_phase": {"NIGHT": ["DROP"]},
}

BUILD_CHOICE_CONFIG = {
    "required_track": "player",
    "required_stage": 1,
    "candidates": ["window_runner", "field_rest", "quick_rest"],
}


def _make_phase7_state(
    game_minute=0, player_stage=1, base_stage=0,
    selected=None, inventory=None, stamina=2, max_stamina=5,
    candidates=None,
):
    cands = candidates if candidates is not None else list(BUILD_CHOICE_CONFIG["candidates"])
    return GameState(
        schema_version=1, event_seq=0, decision_seq=0,
        game_minute=game_minute, seed="phase7-test",
        data={
            "player": {
                "location_id": "base-1", "stamina": stamina,
                "max_stamina": max_stamina, "hp": 10, "max_hp": 10, "attack": 5,
            },
            "inventory": inventory if inventory is not None else {},
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
            "build_choice": {
                "required_track": "player", "required_stage": 1, "candidates": cands,
            },
            "build": {"selected": selected},
        },
    )


# --- Trigger test (spec #37) ---

class TestBuildTrigger:
    def test_no_choose_build_before_progression(self):
        state = _make_phase7_state(player_stage=0)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "CHOOSE_BUILD" not in legal_types

    def test_choose_build_appears_after_progression(self):
        state = _make_phase7_state(player_stage=1)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "CHOOSE_BUILD" in legal_types

    def test_real_upgrade_triggers_build_choice(self):
        """UPGRADE_PLAYER → stage 1 → CHOOSE_BUILD appears (no manual mutation)."""
        state = _make_phase7_state(player_stage=0, inventory={"salvage": 2, "parts": 1})
        r = execute_action(state, ActionIntent(
            action_id="up1", actor_id="p1", action_type="UPGRADE_PLAYER", params={}))
        assert r.accepted
        legal_types = [la.action_type for la in get_legal_actions(r.final_state)]
        assert "CHOOSE_BUILD" in legal_types


# --- Three candidate binding test (spec #38) ---

class TestCandidateBinding:
    def test_three_candidates_offered(self):
        state = _make_phase7_state(player_stage=1)
        choose_actions = [la for la in get_legal_actions(state) if la.action_type == "CHOOSE_BUILD"]
        assert len(choose_actions) == 3
        build_ids = {la.params["build_id"] for la in choose_actions}
        assert build_ids == {"window_runner", "field_rest", "quick_rest"}

    def test_each_candidate_validates(self):
        state = _make_phase7_state(player_stage=1)
        for build_id in ["window_runner", "field_rest", "quick_rest"]:
            result = validate_action(state, ActionIntent(
                action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
                params={"build_id": build_id}))
            assert result.valid is True, f"{build_id} should validate"


# --- Two-candidate config test (spec #39) ---

class TestTwoCandidateConfig:
    def test_two_candidates_only(self):
        state = _make_phase7_state(player_stage=1, candidates=["window_runner", "field_rest"])
        choose_actions = [la for la in get_legal_actions(state) if la.action_type == "CHOOSE_BUILD"]
        assert len(choose_actions) == 2
        build_ids = {la.params["build_id"] for la in choose_actions}
        assert build_ids == {"window_runner", "field_rest"}


# --- Parameter tamper tests (spec #40) ---

class TestParameterTamper:
    def test_missing_build_id_rejected(self):
        state = _make_phase7_state(player_stage=1)
        result = execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD", params={}))
        assert result.accepted is False

    def test_unknown_build_id_rejected(self):
        state = _make_phase7_state(player_stage=1)
        result = execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
            params={"build_id": "unknown_build"}))
        assert result.accepted is False

    def test_extra_parameter_rejected(self):
        state = _make_phase7_state(player_stage=1)
        result = execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
            params={"build_id": "window_runner", "extra": "hack"}))
        assert result.accepted is False

    def test_candidate_not_in_config_rejected(self):
        state = _make_phase7_state(player_stage=1, candidates=["window_runner", "field_rest"])
        result = execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
            params={"build_id": "quick_rest"}))
        assert result.accepted is False

    def test_rejected_no_side_effects(self):
        state = _make_phase7_state(player_stage=1)
        original_hash = state_hash(state.__dict__)
        result = execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
            params={"build_id": "fake"}))
        assert result.events == ()
        assert result.final_state is None
        assert state_hash(state.__dict__) == original_hash


# --- Atomic selection test (spec #41) ---

class TestAtomicSelection:
    def test_select_window_runner(self):
        state = _make_phase7_state(player_stage=1, game_minute=10)
        original_hash = state_hash(state.__dict__)
        result = execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
            params={"build_id": "window_runner"}))
        assert result.accepted is True
        assert len(result.events) == 1
        assert result.events[0].event_type == "BUILD_SELECTED"
        new_state = result.final_state
        assert new_state.data["build"]["selected"] == "window_runner"
        assert new_state.game_minute == 11
        assert new_state.data["inventory"] == {}
        assert new_state.data["progression"]["tracks"]["player"] == 1
        # Original unchanged
        assert state_hash(state.__dict__) == original_hash


# --- Permanence test (spec #42) ---

class TestPermanence:
    def test_choose_build_absent_after_selection(self):
        state = _make_phase7_state(player_stage=1, selected="window_runner")
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "CHOOSE_BUILD" not in legal_types

    def test_second_selection_rejected(self):
        state = _make_phase7_state(player_stage=1, selected="window_runner")
        result = execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
            params={"build_id": "field_rest"}))
        assert result.accepted is False
        assert result.events == ()

    def test_selected_remains_after_rejected_second(self):
        state = _make_phase7_state(player_stage=1, selected="window_runner")
        execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
            params={"build_id": "field_rest"}))
        assert state.data["build"]["selected"] == "window_runner"


# --- window_runner strategy test (spec #43) ---

class TestWindowRunnerStrategy:
    def test_night_drop_legal_with_window_runner(self):
        state = _make_phase7_state(game_minute=60, base_stage=0, selected="window_runner")
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" in legal_types

    def test_night_drop_blocked_with_field_rest(self):
        state = _make_phase7_state(game_minute=60, base_stage=0, selected="field_rest")
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types

    def test_window_runner_stamina_still_required(self):
        state = _make_phase7_state(game_minute=60, base_stage=0, selected="window_runner", stamina=0)
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types

    def test_window_runner_dead_player_no_actions(self):
        state = _make_phase7_state(selected="window_runner")
        state.data["player"]["hp"] = 0
        assert get_legal_actions(state) == ()


# --- field_rest strategy test (spec #44) ---

class TestFieldRestStrategy:
    def _make_at_target_state(self, selected, stamina=2):
        state = _make_phase7_state(selected=selected, stamina=stamina)
        state.data["expedition"]["active"] = True
        state.data["player"]["location_id"] = "site-1"
        state.data["expedition"]["target_searched"] = True
        state.data["expedition"]["target_loot"] = {}
        state.data["expedition"]["carried_loot"] = {"salvage": 2}
        return state

    def test_field_rest_rest_legal_at_target(self):
        state = self._make_at_target_state("field_rest")
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "REST" in legal_types

    def test_window_runner_no_rest_at_target(self):
        state = self._make_at_target_state("window_runner")
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "REST" not in legal_types

    def test_field_rest_rest_execution(self):
        state = self._make_at_target_state("field_rest", stamina=2)
        result = execute_action(state, ActionIntent(
            action_id="r1", actor_id="p1", action_type="REST", params={}))
        assert result.accepted is True
        new_state = result.final_state
        assert new_state.data["player"]["stamina"] == 5
        assert new_state.game_minute == 20
        assert new_state.data["expedition"]["active"] is True
        assert new_state.data["player"]["location_id"] == "site-1"


# --- quick_rest strategy test (spec #45) ---

class TestQuickRestStrategy:
    def test_quick_rest_duration_10(self):
        state = _make_phase7_state(selected="quick_rest", stamina=2)
        choose_actions = [la for la in get_legal_actions(state) if la.action_type == "REST"]
        assert len(choose_actions) == 1
        assert choose_actions[0].duration_minutes == 10

    def test_default_rest_duration_20(self):
        state = _make_phase7_state(selected="window_runner", stamina=2)
        rest_actions = [la for la in get_legal_actions(state) if la.action_type == "REST"]
        assert len(rest_actions) == 1
        assert rest_actions[0].duration_minutes == 20

    def test_quick_rest_execution(self):
        state = _make_phase7_state(selected="quick_rest", stamina=2, game_minute=50)
        result = execute_action(state, ActionIntent(
            action_id="r1", actor_id="p1", action_type="REST", params={}))
        assert result.accepted is True
        assert result.final_state.game_minute == 60
        assert result.final_state.data["player"]["stamina"] == 5


# --- Observation contract (spec #26) ---

class TestObservation:
    def test_build_player_visible_contract(self):
        state = _make_phase7_state(player_stage=1)
        obs = build_observation(state)

        assert obs["build"]["choice_available"] is True
        assert "Choose one candidate once" in obs["build"]["selection_rule"]
        choices = obs["build"]["choices"]
        assert [choice["build_id"] for choice in choices] == [
            "window_runner", "field_rest", "quick_rest",
        ]

        required_fields = {
            "build_id", "title", "effect_summary",
            "relevant_condition_or_limitation", "permanence",
            "opportunity_cost",
        }
        assert all(required_fields <= set(choice) for choice in choices)
        by_id = {choice["build_id"]: choice for choice in choices}
        assert "NIGHT DROP" in by_id["window_runner"]["effect_summary"]
        assert "target" in by_id["field_rest"]["effect_summary"]
        assert "10" in by_id["quick_rest"]["effect_summary"]
        assert all("permanently" in choice["opportunity_cost"] for choice in choices)

    def test_build_selected_visible(self):
        state = _make_phase7_state(selected="window_runner")
        obs = build_observation(state)
        assert obs["build"]["selected"] == "window_runner"
        assert obs["build"]["choice_available"] is False

    def test_build_null_visible(self):
        state = _make_phase7_state(selected=None)
        obs = build_observation(state)
        assert obs["build"]["selected"] is None

    def test_no_build_field_without_feature(self):
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
        assert "build" not in obs
