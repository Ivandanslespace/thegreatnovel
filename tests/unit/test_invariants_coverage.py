"""Coverage tests for invariant edge cases."""

import pytest
from tgn.core.models import GameState
from tgn.core.invariants import check_invariants


@pytest.fixture
def base_state():
    """Base state with expedition data."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="invariant-test",
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


class TestInvariantNonIntTypes:
    """Test that non-int types are rejected for stamina and loot quantities."""
    
    def test_stamina_float_rejected(self, base_state):
        """Float stamina rejected."""
        base_state.data["player"]["stamina"] = 3.5
        
        with pytest.raises(Exception, match="stamina must be int"):
            check_invariants(base_state)
    
    def test_stamina_string_rejected(self, base_state):
        """String stamina rejected."""
        base_state.data["player"]["stamina"] = "3"
        
        with pytest.raises(Exception, match="stamina must be int"):
            check_invariants(base_state)
    
    def test_max_stamina_float_rejected(self, base_state):
        """Float max_stamina rejected."""
        base_state.data["player"]["max_stamina"] = 3.5
        
        with pytest.raises(Exception, match="max_stamina must be int"):
            check_invariants(base_state)
    
    def test_max_stamina_string_rejected(self, base_state):
        """String max_stamina rejected."""
        base_state.data["player"]["max_stamina"] = "3"
        
        with pytest.raises(Exception, match="max_stamina must be int"):
            check_invariants(base_state)
    
    def test_inventory_non_dict_rejected(self, base_state):
        """Non-dict inventory rejected."""
        base_state.data["inventory"] = ["not", "a", "dict"]
        
        with pytest.raises(Exception, match="inventory must be dict"):
            check_invariants(base_state)
    
    def test_inventory_quantity_float_rejected(self, base_state):
        """Float inventory quantity rejected."""
        base_state.data["inventory"]["gold"] = 5.5
        
        with pytest.raises(Exception, match="inventory\\[gold\\] must be int"):
            check_invariants(base_state)
    
    def test_inventory_quantity_string_rejected(self, base_state):
        """String inventory quantity rejected."""
        base_state.data["inventory"]["gold"] = "5"
        
        with pytest.raises(Exception, match="inventory\\[gold\\] must be int"):
            check_invariants(base_state)
    
    def test_target_loot_non_dict_rejected(self, base_state):
        """Non-dict target_loot rejected."""
        base_state.data["expedition"]["target_loot"] = "not a dict"
        
        with pytest.raises(Exception, match="target_loot must be dict"):
            check_invariants(base_state)
    
    def test_target_loot_quantity_float_rejected(self, base_state):
        """Float target_loot quantity rejected."""
        base_state.data["expedition"]["target_loot"]["salvage"] = 2.5
        
        with pytest.raises(Exception, match="target_loot\\[salvage\\] must be int"):
            check_invariants(base_state)
    
    def test_target_loot_quantity_string_rejected(self, base_state):
        """String target_loot quantity rejected."""
        base_state.data["expedition"]["target_loot"]["salvage"] = "2"
        
        with pytest.raises(Exception, match="target_loot\\[salvage\\] must be int"):
            check_invariants(base_state)
    
    def test_carried_loot_non_dict_rejected(self, base_state):
        """Non-dict carried_loot rejected."""
        base_state.data["expedition"]["carried_loot"] = 123
        
        with pytest.raises(Exception, match="carried_loot must be dict"):
            check_invariants(base_state)
    
    def test_carried_loot_quantity_float_rejected(self, base_state):
        """Float carried_loot quantity rejected."""
        base_state.data["expedition"]["carried_loot"]["salvage"] = 2.5
        
        with pytest.raises(Exception, match="carried_loot\\[salvage\\] must be int"):
            check_invariants(base_state)
    
    def test_carried_loot_quantity_string_rejected(self, base_state):
        """String carried_loot quantity rejected."""
        base_state.data["expedition"]["carried_loot"]["salvage"] = "2"
        
        with pytest.raises(Exception, match="carried_loot\\[salvage\\] must be int"):
            check_invariants(base_state)
