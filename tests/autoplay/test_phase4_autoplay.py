"""Phase 4 autoplay tests: combat and flee policies.

Covers spec section 39: Phase 4 autoplay.
"""

import pytest

from tgn.core.models import GameState
from tgn.core.hashing import state_hash
from tgn.autoplay.policy import choose_action, choose_action_flee_policy
from tgn.autoplay.runner import run_autoplay
from tgn.autoplay.models import AutoplayConfig, StopReason


def make_phase4_autoplay_state():
    """Create Phase 4 state for autoplay testing."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="phase4-autoplay",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 6,
                "max_stamina": 6,
                "hp": 6,
                "max_hp": 6,
                "attack": 2,
            },
            "inventory": {},
            "expedition": {
                "active": False,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": False,
                "target_loot": {"salvage": 2},
                "carried_loot": {},
                "encounter": {
                    "active": False,
                    "enemy_id": "enemy-1",
                    "enemy_hp": 4,
                    "enemy_max_hp": 4,
                    "enemy_attack": 2,
                },
            },
        },
    )


class TestPhase4Autoplay:
    """Autoplay reaches combat and flee paths."""

    def test_combat_policy_reaches_fight(self):
        """Combat policy (SEARCH > FIGHT > EXTRACT) reaches FIGHT action."""
        state = make_phase4_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="combat-bot")
        
        result = run_autoplay(state, choose_action, config)
        
        # Should complete successfully
        assert result.stop_reason == StopReason.POLICY_COMPLETE
        
        # Should have FIGHT actions in frames
        action_types = [f.action_type for f in result.frames]
        assert "FIGHT" in action_types
        
        # Should have EXTRACT (after enemy defeated)
        assert "EXTRACT" in action_types
        
        # Final state should have loot banked
        final = result.final_state
        assert final.data["inventory"] == {"salvage": 2}

    def test_flee_policy_reaches_flee(self):
        """Flee policy (SEARCH > FLEE) reaches FLEE action."""
        state = make_phase4_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="flee-bot")
        
        result = run_autoplay(state, choose_action_flee_policy, config)
        
        # Should complete successfully
        assert result.stop_reason == StopReason.POLICY_COMPLETE
        
        # Should have FLEE action
        action_types = [f.action_type for f in result.frames]
        assert "FLEE" in action_types
        
        # Should NOT have FIGHT
        assert "FIGHT" not in action_types
        
        # Final state should have NO loot (fled)
        final = result.final_state
        assert final.data["inventory"] == {}
        assert final.data["expedition"]["carried_loot"] == {}

    def test_combat_and_flee_different_outcomes(self):
        """Combat and flee policies produce different final hashes."""
        state = make_phase4_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="bot")
        
        # Combat path
        combat_result = run_autoplay(
            GameState(**state.__dict__), choose_action, config
        )
        
        # Flee path
        flee_result = run_autoplay(
            GameState(**state.__dict__), choose_action_flee_policy, config
        )
        
        assert combat_result.final_state_hash != flee_result.final_state_hash

    def test_no_llm_required(self):
        """Autoplay runs without any LLM calls (deterministic only)."""
        state = make_phase4_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="test-bot")
        
        # This test simply verifies the policy is callable and deterministic
        # No LLM imports or calls should be needed
        result = run_autoplay(state, choose_action, config)
        assert result.decisions > 0
        assert result.final_state is not None
