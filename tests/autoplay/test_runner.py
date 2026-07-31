"""Runner tests per spec section #38."""

import pytest
from tgn.autoplay import run_autoplay, AutoplayConfig, StopReason, choose_action
from tgn.actions.models import ActionIntent
from tgn.core.hashing import state_hash


class TestRunner:
    """Autoplay runner tests."""
    
    def test_runner_completes_phase3_vertical_slice(self, phase35_initial_state):
        """Default run completes the Phase 3 vertical slice."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        assert result.completed
        assert result.stop_reason == StopReason.POLICY_COMPLETE
        assert result.decisions == 3
        assert result.events == 3
    
    def test_runner_action_sequence_is_drop_search_extract(self, phase35_initial_state):
        """Default action sequence is DROP, SEARCH, EXTRACT."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        action_types = [frame.action_type for frame in result.frames]
        assert action_types == ["DROP", "SEARCH", "EXTRACT"]
    
    def test_runner_event_sequence_matches_actions(self, phase35_initial_state):
        """Event sequence matches action sequence."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        event_types = [frame.event_type for frame in result.frames]
        assert event_types == [
            "EXPEDITION_DROPPED",
            "SEARCH_RESOLVED",
            "EXPEDITION_EXTRACTED",
        ]
    
    def test_runner_stops_policy_complete(self, phase35_initial_state):
        """Run stops with POLICY_COMPLETE when only WAIT remains."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        assert result.stop_reason == StopReason.POLICY_COMPLETE
        assert result.completed
    
    def test_runner_respects_max_decisions(self, phase35_initial_state):
        """max_decisions=1 stops after DROP."""
        config = AutoplayConfig(max_decisions=1)
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        assert result.decisions == 1
        assert result.events == 1
        assert result.stop_reason == StopReason.MAX_DECISIONS
        assert not result.completed
        
        # Final state should be at target location
        final = result.final_state
        assert final.data["expedition"]["active"]
        assert final.data["player"]["location_id"] == "site-1"
    
    def test_runner_stops_on_rejected_action(self, phase35_initial_state):
        """Rejected action stops immediately with ACTION_REJECTED."""
        def bad_policy(obs, decision_number, actor_id):
            # Intentionally return invalid action
            return ActionIntent(
                action_id=f"bad-{decision_number:04d}",
                actor_id=actor_id,
                action_type="SEARCH",  # Not legal at base
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        assert result.stop_reason == StopReason.ACTION_REJECTED
        assert not result.completed
        assert result.decisions == 0
        assert result.events == 0
    
    def test_rejected_action_does_not_mutate_state(self, phase35_initial_state):
        """Rejected action leaves state unchanged."""
        initial_hash = state_hash(phase35_initial_state.__dict__)
        
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id=f"bad-{decision_number:04d}",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        assert result.final_state_hash == initial_hash
    
    def test_rejected_action_does_not_persist_event(self, phase35_initial_state):
        """Rejected action produces no frames."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id=f"bad-{decision_number:04d}",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        assert len(result.frames) == 0
        assert result.events == 0
    
    def test_run_result_final_hash_matches_final_state(self, phase35_initial_state):
        """RunResult.final_state_hash matches computed hash of final_state."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        computed_hash = state_hash(result.final_state.__dict__)
        assert result.final_state_hash == computed_hash
