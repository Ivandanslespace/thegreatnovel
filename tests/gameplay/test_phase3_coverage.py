"""Additional coverage tests for Phase 3."""

import pytest
from tgn.core.models import GameState, DomainEvent
from tgn.core.reducer import reduce_event
from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import (
    validate_action,
    execute_action,
    get_legal_actions,
)


@pytest.fixture
def base_state():
    """Initial state at base."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="test",
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


class TestEdgeCases:
    """Edge cases for better coverage."""
    
    def test_validate_unknown_action_type(self, base_state):
        """Unknown action type rejected."""
        intent = ActionIntent("test", "p", "INVALID_ACTION", {})
        result = validate_action(base_state, intent)
        
        assert not result.valid
        assert result.errors[0].code == "UNKNOWN_ACTION"
    
    def test_validate_wait_with_bool_minutes(self, base_state):
        """WAIT with boolean minutes rejected."""
        intent = ActionIntent("test", "p", "WAIT", {"minutes": True})
        result = validate_action(base_state, intent)
        
        assert not result.valid
        assert any(e.code == "INVALID_TYPE" for e in result.errors)
    
    def test_validate_wait_with_negative_minutes(self, base_state):
        """WAIT with negative minutes rejected."""
        intent = ActionIntent("test", "p", "WAIT", {"minutes": -5})
        result = validate_action(base_state, intent)
        
        assert not result.valid
        assert any(e.code == "INVALID_VALUE" for e in result.errors)
    
    def test_validate_wait_with_zero_minutes(self, base_state):
        """WAIT with zero minutes rejected."""
        intent = ActionIntent("test", "p", "WAIT", {"minutes": 0})
        result = validate_action(base_state, intent)
        
        assert not result.valid
        assert any(e.code == "INVALID_VALUE" for e in result.errors)
    
    def test_validate_wait_with_unexpected_params(self, base_state):
        """WAIT with unexpected params rejected."""
        intent = ActionIntent("test", "p", "WAIT", {"minutes": 60, "extra": "param"})
        result = validate_action(base_state, intent)
        
        assert not result.valid
        assert any(e.code == "UNEXPECTED_PARAMETER" for e in result.errors)
    
    def test_reducer_rejects_search_when_inactive(self, base_state):
        """SEARCH rejected when expedition not active."""
        forged_event = DomainEvent(
            event_seq=1,
            decision_seq=1,
            game_minute=30,
            event_type="SEARCH_RESOLVED",
            payload={
                "loot_gained": {"salvage": 2},
                "time": 30,
                "stamina_cost": 2,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(base_state, forged_event)
    
    def test_reducer_rejects_search_when_already_searched(self, base_state):
        """SEARCH rejected when target already searched."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # SEARCH
        search_result = execute_action(drop_result.final_state, ActionIntent("s1", "p", "SEARCH", {}))
        
        # SEARCH again
        forged_event = DomainEvent(
            event_seq=3,
            decision_seq=3,
            game_minute=70,
            event_type="SEARCH_RESOLVED",
            payload={
                "loot_gained": {},  # Empty since target_loot is now empty
                "time": 30,
                "stamina_cost": 2,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(search_result.final_state, forged_event)
    
    def test_reducer_rejects_search_from_wrong_location(self, base_state):
        """SEARCH rejected when at wrong location."""
        # DROP to move to target
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # Manually change location back to base (simulate bug)
        corrupted_state = drop_result.final_state
        corrupted_state.data["player"]["location_id"] = "base-1"
        
        forged_event = DomainEvent(
            event_seq=2,
            decision_seq=2,
            game_minute=40,
            event_type="SEARCH_RESOLVED",
            payload={
                "loot_gained": {"salvage": 2},
                "time": 30,
                "stamina_cost": 2,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(corrupted_state, forged_event)
    
    def test_reducer_rejects_wrong_search_stamina_cost(self, base_state):
        """SEARCH event with wrong stamina cost rejected."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # Try SEARCH with wrong stamina cost
        forged_event = DomainEvent(
            event_seq=2,
            decision_seq=2,
            game_minute=40,
            event_type="SEARCH_RESOLVED",
            payload={
                "loot_gained": {"salvage": 2},
                "time": 30,
                "stamina_cost": 5,  # Wrong: should be 2
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(drop_result.final_state, forged_event)
    
    def test_reducer_rejects_wrong_extract_time(self, base_state):
        """EXTRACT event with wrong time rejected."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # SEARCH
        search_result = execute_action(drop_result.final_state, ActionIntent("s1", "p", "SEARCH", {}))
        
        # Try EXTRACT with wrong time
        forged_event = DomainEvent(
            event_seq=3,
            decision_seq=3,
            game_minute=70,  # Wrong: should be 55
            event_type="EXPEDITION_EXTRACTED",
            payload={
                "carried_loot": {"salvage": 2},
                "time": 15,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(search_result.final_state, forged_event)
    
    def test_reducer_rejects_extract_from_wrong_location(self, base_state):
        """EXTRACT rejected when at wrong location."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # SEARCH
        search_result = execute_action(drop_result.final_state, ActionIntent("s1", "p", "SEARCH", {}))
        
        # Manually change location (simulate bug)
        corrupted_state = search_result.final_state
        corrupted_state.data["player"]["location_id"] = "wrong-location"
        
        forged_event = DomainEvent(
            event_seq=3,
            decision_seq=3,
            game_minute=55,
            event_type="EXPEDITION_EXTRACTED",
            payload={
                "carried_loot": {"salvage": 2},
                "time": 15,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(corrupted_state, forged_event)


class TestInvariantEdgeCases:
    """Test expedition invariant edge cases."""
    
    def test_stamina_must_be_int_not_bool(self, base_state):
        """Stamina must be int, not bool."""
        from tgn.core.invariants import check_invariants
        
        # Set stamina to bool
        base_state.data["player"]["stamina"] = True
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_max_stamina_must_be_int_not_bool(self, base_state):
        """max_stamina must be int, not bool."""
        from tgn.core.invariants import check_invariants
        
        # Set max_stamina to bool
        base_state.data["player"]["max_stamina"] = False
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_stamina_must_be_non_negative(self, base_state):
        """Stamina must be non-negative."""
        from tgn.core.invariants import check_invariants
        
        # Set stamina to negative
        base_state.data["player"]["stamina"] = -1
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_stamina_must_not_exceed_max(self, base_state):
        """Stamina must not exceed max_stamina."""
        from tgn.core.invariants import check_invariants
        
        # Set stamina > max_stamina
        base_state.data["player"]["stamina"] = 10
        base_state.data["player"]["max_stamina"] = 5
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_loot_quantities_must_be_non_negative(self, base_state):
        """Loot quantities must be non-negative."""
        from tgn.core.invariants import check_invariants
        
        # Set negative loot
        base_state.data["inventory"]["gold"] = -5
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_inactive_expedition_must_be_at_base(self, base_state):
        """Inactive expedition: player must be at base."""
        from tgn.core.invariants import check_invariants
        
        # Move player away from base while inactive
        base_state.data["player"]["location_id"] = "site-1"
        base_state.data["expedition"]["active"] = False
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_inactive_expedition_carried_loot_must_be_empty(self, base_state):
        """Inactive expedition: carried_loot must be empty."""
        from tgn.core.invariants import check_invariants
        
        # Set carried_loot while inactive
        base_state.data["expedition"]["active"] = False
        base_state.data["expedition"]["carried_loot"] = {"gold": 5}
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_active_expedition_must_be_at_target(self, base_state):
        """Active expedition: player must be at target."""
        from tgn.core.invariants import check_invariants
        
        # Set active but player at wrong location
        base_state.data["expedition"]["active"] = True
        base_state.data["player"]["location_id"] = "base-1"
        
        with pytest.raises(Exception):
            check_invariants(base_state)
    
    def test_searched_target_must_have_empty_target_loot(self, base_state):
        """Searched target: target_loot must be empty."""
        from tgn.core.invariants import check_invariants
        
        # Set searched but target_loot not empty
        base_state.data["expedition"]["target_searched"] = True
        base_state.data["expedition"]["target_loot"] = {"gold": 5}
        
        with pytest.raises(Exception):
            check_invariants(base_state)
