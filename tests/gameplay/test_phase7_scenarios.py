"""Phase 7 scenario tests: build divergence, backward compatibility."""

import pytest
from tgn.core.models import GameState
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import get_legal_actions, execute_action, build_observation
from tgn.actions.models import ActionIntent


PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120, "boundary_minute": 60,
    "phase_before": "DAY", "phase_after": "NIGHT",
    "blocked_actions_by_phase": {"NIGHT": ["DROP"]},
}


def _make_phase7_state(game_minute=60, player_stage=1, base_stage=0,
                       selected=None, stamina=2, max_stamina=5):
    return GameState(
        schema_version=1, event_seq=0, decision_seq=0,
        game_minute=game_minute, seed="phase7-div",
        data={
            "player": {
                "location_id": "base-1", "stamina": stamina,
                "max_stamina": max_stamina, "hp": 10, "max_hp": 10, "attack": 5,
            },
            "inventory": {},
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
                "required_track": "player", "required_stage": 1,
                "candidates": ["window_runner", "field_rest", "quick_rest"],
            },
            "build": {"selected": selected},
        },
    )


# --- Build divergence hard product test (spec #46) ---

class TestBuildDivergence:
    def _run_branch_a(self):
        """window_runner: CHOOSE → REST → NIGHT DROP."""
        state = _make_phase7_state(game_minute=60, stamina=2, max_stamina=5)
        r1 = execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
            params={"build_id": "window_runner"}))
        assert r1.accepted
        state = r1.final_state
        r2 = execute_action(state, ActionIntent(
            action_id="r", actor_id="p1", action_type="REST", params={}))
        assert r2.accepted
        state = r2.final_state
        r3 = execute_action(state, ActionIntent(
            action_id="d", actor_id="p1", action_type="DROP", params={}))
        assert r3.accepted
        return r3.final_state

    def _run_branch_b(self):
        """field_rest: CHOOSE → WAIT → DAY DROP."""
        state = _make_phase7_state(game_minute=60, stamina=2, max_stamina=5)
        r1 = execute_action(state, ActionIntent(
            action_id="cb", actor_id="p1", action_type="CHOOSE_BUILD",
            params={"build_id": "field_rest"}))
        assert r1.accepted
        state = r1.final_state
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "DROP" not in legal_types
        r2 = execute_action(state, ActionIntent(
            action_id="w", actor_id="p1", action_type="WAIT", params={"minutes": 59}))
        assert r2.accepted
        state = r2.final_state
        r3 = execute_action(state, ActionIntent(
            action_id="d", actor_id="p1", action_type="DROP", params={}))
        assert r3.accepted
        return r3.final_state

    def test_branch_a_window_runner(self):
        state_a = self._run_branch_a()
        assert state_a.game_minute == 91
        assert state_a.data["player"]["location_id"] == "site-1"
        assert state_a.data["player"]["stamina"] == 4
        assert state_a.data["build"]["selected"] == "window_runner"

    def test_branch_b_field_rest(self):
        state_b = self._run_branch_b()
        assert state_b.game_minute == 130
        assert state_b.data["player"]["location_id"] == "site-1"
        assert state_b.data["player"]["stamina"] == 1
        assert state_b.data["build"]["selected"] == "field_rest"

    def test_divergence_different_hashes_and_actions(self):
        """Same pre-choice state → different builds → different outcomes."""
        state_a = self._run_branch_a()
        state_b = self._run_branch_b()

        # State hashes differ
        assert state_hash(state_a.__dict__) != state_hash(state_b.__dict__)

        # Selected builds differ
        assert state_a.data["build"]["selected"] == "window_runner"
        assert state_b.data["build"]["selected"] == "field_rest"

        # Legal actions differ at target
        legal_a = {la.action_type for la in get_legal_actions(state_a)}
        legal_b = {la.action_type for la in get_legal_actions(state_b)}
        # A has stamina 4 → SEARCH legal; B has stamina 1 → SEARCH not legal
        assert "SEARCH" in legal_a
        assert "SEARCH" not in legal_b
        # B has field_rest → REST legal at target
        assert "REST" in legal_b


# --- quick_rest divergence (spec #47) ---

class TestQuickRestDivergence:
    def test_quick_rest_vs_window_runner_hash_differ(self):
        state_qr = _make_phase7_state(game_minute=0, selected="quick_rest", stamina=2)
        state_wr = _make_phase7_state(game_minute=0, selected="window_runner", stamina=2)

        r_qr = execute_action(state_qr, ActionIntent(
            action_id="r", actor_id="p1", action_type="REST", params={}))
        r_wr = execute_action(state_wr, ActionIntent(
            action_id="r", actor_id="p1", action_type="REST", params={}))

        assert r_qr.accepted and r_wr.accepted
        assert r_qr.final_state.game_minute == 10
        assert r_wr.final_state.game_minute == 20
        assert state_hash(r_qr.final_state.__dict__) != state_hash(r_wr.final_state.__dict__)


# --- Legacy compatibility (spec #57) ---

class TestLegacyCompatibility:
    def test_phase6_state_unchanged(self):
        """Phase 6 state without build feature: no CHOOSE_BUILD, same behavior."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0,
            game_minute=0, seed="legacy",
            data={
                "player": {
                    "location_id": "base-1", "stamina": 3, "max_stamina": 5,
                    "hp": 10, "max_hp": 10, "attack": 5,
                },
                "inventory": {"salvage": 2, "parts": 1},
                "expedition": {
                    "active": False, "base_location_id": "base-1",
                    "target_location_id": "site-1", "target_searched": False,
                    "target_loot": {"salvage": 2, "parts": 1}, "carried_loot": {},
                },
                "phase_cycle": dict(PHASE_CYCLE_CONFIG),
                "progression": {"tracks": {"player": 1, "base": 0}},
                "progression_gates": {
                    "player": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
                    "base": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
                },
            },
        )
        legal_types = [la.action_type for la in get_legal_actions(state)]
        assert "CHOOSE_BUILD" not in legal_types
        assert "REST" in legal_types  # player stage 1
        obs = build_observation(state)
        assert "build" not in obs

    def test_phase6_rest_duration_unchanged(self):
        """Without build feature, REST remains 20 minutes."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0,
            game_minute=0, seed="legacy",
            data={
                "player": {
                    "location_id": "base-1", "stamina": 2, "max_stamina": 5,
                    "hp": 10, "max_hp": 10, "attack": 5,
                },
                "inventory": {},
                "expedition": {
                    "active": False, "base_location_id": "base-1",
                    "target_location_id": "site-1", "target_searched": False,
                    "target_loot": {"salvage": 2}, "carried_loot": {},
                },
                "progression": {"tracks": {"player": 1, "base": 0}},
                "progression_gates": {
                    "player": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
                    "base": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
                },
            },
        )
        rest_actions = [la for la in get_legal_actions(state) if la.action_type == "REST"]
        assert len(rest_actions) == 1
        assert rest_actions[0].duration_minutes == 20
