"""Additional coverage tests to reach 95% coverage."""

import pytest
from tgn.core.models import GameState, DomainEvent
from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import (
    validate_action,
    execute_action,
    get_legal_actions,
    build_observation,
)


@pytest.fixture
def base_state():
    """Base state at expedition base."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="coverage-test",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 3,
                "max_stamina": 3,
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
        },
    )


class TestWaitExecutionCoverage:
    """Tests to cover WAIT execution path in execute_action."""
    
    def test_execute_wait_produces_time_advanced_event(self, base_state):
        """execute_action with WAIT produces TIME_ADVANCED event."""
        intent = ActionIntent("w1", "p", "WAIT", {"minutes": 60})
        result = execute_action(base_state, intent)
        
        assert result.accepted
        assert len(result.events) == 1
        assert result.events[0].event_type == "TIME_ADVANCED"
        assert result.events[0].game_minute == 60
    
    def test_execute_wait_updates_state_correctly(self, base_state):
        """execute_action with WAIT updates game state."""
        intent = ActionIntent("w1", "p", "WAIT", {"minutes": 60})
        result = execute_action(base_state, intent)
        
        assert result.accepted
        assert result.final_state is not None
        assert result.final_state.game_minute == 60
        assert result.final_state.event_seq == 1
        assert result.final_state.decision_seq == 1
    
    def test_execute_wait_with_invalid_params_rejected(self, base_state):
        """execute_action with invalid WAIT params rejected."""
        intent = ActionIntent("w1", "p", "WAIT", {"minutes": -5})
        result = execute_action(base_state, intent)
        
        assert not result.accepted
        assert result.final_state is None
        assert len(result.events) == 0
    
    def test_execute_unknown_action_rejected(self, base_state):
        """execute_action with unknown action type rejected."""
        intent = ActionIntent("x1", "p", "UNKNOWN_ACTION", {})
        result = execute_action(base_state, intent)
        
        assert not result.accepted
        assert result.final_state is None
        assert len(result.events) == 0
    
    def test_execute_wait_with_forbidden_metadata_rejected(self, base_state):
        """execute_action with WAIT containing forbidden metadata rejected."""
        intent = ActionIntent("w1", "p", "WAIT", {"minutes": 60, "event_seq": 999})
        result = execute_action(base_state, intent)
        
        assert not result.accepted
        assert result.final_state is None
        assert len(result.events) == 0


class TestDropAtBaseWithTargetUnsearched:
    """Tests for DROP availability at base with unsearched target."""
    
    def test_drop_available_at_base_with_unsearched_target(self, base_state):
        """DROP available at base when target not yet searched."""
        base_state.data["player"]["location_id"] = "base-1"
        base_state.data["expedition"]["active"] = False
        base_state.data["expedition"]["target_searched"] = False
        base_state.data["player"]["stamina"] = 3
        
        legal_actions = get_legal_actions(base_state)
        action_types = [a.action_type for a in legal_actions]
        
        assert "DROP" in action_types
    
    def test_drop_not_available_at_base_with_searched_target(self, base_state):
        """DROP not available at base when target already searched."""
        base_state.data["player"]["location_id"] = "base-1"
        base_state.data["expedition"]["active"] = False
        base_state.data["expedition"]["target_searched"] = True
        base_state.data["player"]["stamina"] = 10
        
        legal_actions = get_legal_actions(base_state)
        action_types = [a.action_type for a in legal_actions]
        
        assert "DROP" not in action_types


class TestNoExpeditionDataEdgeCase:
    """Test behavior when state has no expedition data."""
    
    def test_get_legal_actions_no_expedition_data(self):
        """get_legal_actions returns only WAIT when no expedition data."""
        state = GameState(
            schema_version=1,
            event_seq=0,
            decision_seq=0,
            game_minute=0,
            seed="no-expedition",
            data={
                "player": {
                    "location_id": "base-1",
                    "stamina": 3,
                    "max_stamina": 3,
                },
                "inventory": {},
            },
        )
        
        legal_actions = get_legal_actions(state)
        action_types = [a.action_type for a in legal_actions]
        
        # Only WAIT should be available
        assert action_types == ["WAIT"]


class TestReducerErrorPaths:
    """Test reducer error paths for better coverage."""
    
    def test_reducer_rejects_drop_when_already_active(self, base_state):
        """Reducer rejects DROP when expedition already active."""
        # First DROP
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(base_state, drop_intent)
        
        # Try DROP again (should fail)
        from tgn.core.reducer import reduce_event
        
        forged_event = DomainEvent(
            event_seq=2,
            decision_seq=2,
            game_minute=20,
            event_type="EXPEDITION_DROPPED",
            payload={
                "destination": "site-2",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(drop_result.final_state, forged_event)
    
    def test_reducer_rejects_search_when_already_searched(self, base_state):
        """Reducer rejects SEARCH when target already searched."""
        # DROP and SEARCH
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(base_state, drop_intent)
        
        search_intent = ActionIntent("s1", "p", "SEARCH", {})
        search_result = execute_action(drop_result.final_state, search_intent)
        
        # Try SEARCH again (should fail)
        from tgn.core.reducer import reduce_event
        
        forged_event = DomainEvent(
            event_seq=3,
            decision_seq=3,
            game_minute=70,
            event_type="SEARCH_RESOLVED",
            payload={
                "loot_gained": {},
                "time": 30,
                "stamina_cost": 2,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(search_result.final_state, forged_event)
    
    def test_reducer_rejects_extract_when_not_active(self, base_state):
        """Reducer rejects EXTRACT when expedition not active."""
        from tgn.core.reducer import reduce_event
        
        forged_event = DomainEvent(
            event_seq=1,
            decision_seq=1,
            game_minute=15,
            event_type="EXPEDITION_EXTRACTED",
            payload={
                "carried_loot": {},
                "time": 15,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(base_state, forged_event)


class TestInvariantEdgeCases:
    """Additional invariant edge cases."""
    
    def test_inactive_expedition_at_wrong_location(self, base_state):
        """Invariant rejects inactive expedition at wrong location."""
        from tgn.core.invariants import check_invariants
        
        base_state.data["expedition"]["active"] = False
        base_state.data["player"]["location_id"] = "wrong-location"
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_active_expedition_at_wrong_location(self, base_state):
        """Invariant rejects active expedition at wrong location."""
        from tgn.core.invariants import check_invariants
        
        base_state.data["expedition"]["active"] = True
        base_state.data["player"]["location_id"] = "wrong-location"
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_inactive_expedition_with_carried_loot(self, base_state):
        """Invariant rejects inactive expedition with carried loot."""
        from tgn.core.invariants import check_invariants
        
        base_state.data["expedition"]["active"] = False
        base_state.data["expedition"]["carried_loot"] = {"gold": 5}
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_searched_target_with_remaining_target_loot(self, base_state):
        """Invariant rejects searched target with remaining loot."""
        from tgn.core.invariants import check_invariants
        
        base_state.data["expedition"]["target_searched"] = True
        base_state.data["expedition"]["target_loot"] = {"gold": 5}
        
        with pytest.raises(Exception):
            check_invariants(base_state)
