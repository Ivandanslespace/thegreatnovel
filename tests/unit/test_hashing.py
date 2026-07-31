"""Unit tests for state hashing and canonical serialization."""

import math
from tgn.core.hashing import DeterministicHashError, canonical_json, state_hash


class TestCanonicalJson:
    """Tests for canonical JSON conversion."""
    
    def test_dict_order_independent(self):
        """Dict insertion order should not affect canonical form."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 2, "a": 1}
        
        assert canonical_json(dict1) == canonical_json(dict2)
    
    def test_nested_dict_order_independent(self):
        """Nested dict key order should not matter."""
        nested1 = {"outer": {"b": 2, "a": 1}}
        nested2 = {"outer": {"a": 1, "b": 2}}
        
        assert canonical_json(nested1) == canonical_json(nested2)
    
    def test_list_order_matters(self):
        """List order MUST affect canonical form (different data)."""
        list1 = [1, 2, 3]
        list2 = [3, 2, 1]
        
        assert canonical_json(list1) != canonical_json(list2)
    
    def test_value_change_affects_hash(self):
        """Different values must produce different JSON."""
        value1 = {"count": 10}
        value2 = {"count": 11}
        
        assert canonical_json(value1) != canonical_json(value2)
    
    def test_unicode_preserved(self):
        """Unicode characters should be preserved, not escaped."""
        unicode_data = {"message": "你好", "emoji": "🎮"}
        json_str = canonical_json(unicode_data)
        
        assert "你好" in json_str
        assert "🎮" in json_str
    
    def test_nan_rejected(self):
        """NaN values should raise DeterministicHashError."""
        data = {"value": float("nan")}
        
        try:
            canonical_json(data)
            assert False, "Should have raised DeterministicHashError"
        except (DeterministicHashError, ValueError):
            pass
    
    def test_infinity_rejected(self):
        """Infinity values should raise error."""
        data = {"positive": float("inf"), "negative": float("-inf")}
        
        try:
            canonical_json(data)
            assert False, "Should have raised an error"
        except (DeterministicHashError, ValueError):
            pass


class TestStateHash:
    """Tests for state hashing."""
    
    def test_same_state_same_hash(self):
        """Same state must produce identical hash."""
        state = {
            "schema_version": 1,
            "event_seq": 5,
            "game_minute": 120,
            "data": {},
        }
        
        hash1 = state_hash(state)
        hash2 = state_hash(state)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_different_values_different_hash(self):
        """States with different values must have different hashes."""
        state1 = {"value": 1}
        state2 = {"value": 2}
        
        hash1 = state_hash(state1)
        hash2 = state_hash(state2)
        
        assert hash1 != hash2
    
    def test_dict_order_does_not_affect_hash(self):
        """Hash should be independent of dict key order."""
        state1 = {"a": 1, "b": 2, "c": 3}
        state2 = {"c": 3, "a": 1, "b": 2}
        
        assert state_hash(state1) == state_hash(state2)
    
    def test_nested_structure_hash(self):
        """Complex nested structures should hash correctly."""
        state1 = {
            "meta": {
                "version": 1,
                "nested": {"z": 1, "a": 2}
            },
            "items": [1, 2, 3]
        }
        state2 = {
            "meta": {
                "version": 1,
                "nested": {"a": 2, "z": 1}
            },
            "items": [1, 2, 3]
        }
        
        assert state_hash(state1) == state_hash(state2)
    
    def test_empty_state(self):
        """Empty state should hash consistently."""
        empty1 = {}
        empty2 = {}
        
        hash1 = state_hash(empty1)
        hash2 = state_hash(empty2)
        
        assert hash1 == hash2
        assert hash1 == state_hash({})
    
    def test_complex_realistic_state(self):
        """A realistic GameState structure should hash properly."""
        base_state = {
            "schema_version": 1,
            "event_seq": 10,
            "decision_seq": 3,
            "game_minute": 720,
            "seed": "test-seed-123",
            "data": {
                "location": "camp_001",
                "resources": {
                    "food": 50,
                    "fuel": 30,
                },
            },
        }
        
        hash1 = state_hash(base_state)
        hash2 = state_hash(base_state)
        
        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert all(c in '0123456789abcdef' for c in hash1)
