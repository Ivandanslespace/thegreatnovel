"""Unit tests for invariant checks."""

import pytest
from tgn.core import GameState, check_invariants, InvariantError


class TestInvariantChecks:
    """Tests for core invariant validation."""
    
    def test_valid_state_passes(self):
        """Valid state should pass all invariants."""
        state = GameState.initial(seed="valid-test")
        
        # Should not raise
        check_invariants(state)
    
    def test_negative_event_seq_rejected(self):
        """event_seq must be non-negative."""
        state = GameState.initial()
        state.event_seq = -1
        
        with pytest.raises(InvariantError) as exc_info:
            check_invariants(state)
        
        assert "non-negative" in str(exc_info.value).lower()
    
    def test_negative_decision_seq_rejected(self):
        """decision_seq must be non-negative."""
        state = GameState.initial()
        state.decision_seq = -5
        
        with pytest.raises(InvariantError) as exc_info:
            check_invariants(state)
        
        assert "non-negative" in str(exc_info.value).lower()
    
    def test_negative_game_minute_rejected(self):
        """game_minute must be non-negative."""
        state = GameState.initial()
        state.game_minute = -100
        
        with pytest.raises(InvariantError) as exc_info:
            check_invariants(state)
        
        assert "non-negative" in str(exc_info.value).lower()
    
    def test_unsupported_schema_version_rejected(self):
        """Only schema version 1 is supported."""
        state = GameState.initial()
        state.schema_version = 2
        
        with pytest.raises(InvariantError) as exc_info:
            check_invariants(state)
        
        assert "schema version" in str(exc_info.value).lower()
    
    def test_zero_values_allowed(self):
        """Zero values are valid for counters."""
        state = GameState(
            schema_version=1,
            event_seq=0,
            decision_seq=0,
            game_minute=0,
            seed="zero-test",
            data={},
        )
        
        # Should not raise
        check_invariants(state)
    
    def test_data_must_be_dict(self):
        """data field must be a dict."""
        state = GameState.initial()
        state.data = "not a dict"
        
        with pytest.raises(InvariantError):
            check_invariants(state)
    
    def test_nan_in_state_detected(self):
        """NaN values in state should fail canonicalizability check."""
        state = GameState.initial()
        state.data = {"value": float("nan")}
        
        with pytest.raises(InvariantError):
            check_invariants(state)
    
    def test_infinity_in_state_detected(self):
        """Infinity values should fail."""
        state = GameState.initial()
        state.data = {"value": float("inf")}
        
        with pytest.raises(InvariantError):
            check_invariants(state)
