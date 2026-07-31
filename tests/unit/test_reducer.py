"""Unit tests for pure reducer function."""

import pytest
from tgn.core import GameState, DomainEvent, reduce_event, ReducerError


class TestReducerBasic:
    """Basic reducer functionality tests."""
    
    def test_initial_state_creation(self):
        """Can create initial state with given seed."""
        state = GameState.initial(seed="test-seed")
        
        assert state.schema_version == 1
        assert state.event_seq == 0
        assert state.decision_seq == 0
        assert state.game_minute == 0
        assert state.seed == "test-seed"
        assert state.data == {}
    
    def test_reducer_does_not_mutate_input(self):
        """Reducer must NOT modify input state."""
        original_state = GameState.initial(seed="immutable-test")
        original_hash = str(original_state.__dict__)
        
        event = DomainEvent.advance_time(game_minute=0, minutes=60, event_seq=1)
        new_state = reduce_event(original_state, event)
        
        # Verify input state unchanged
        assert str(original_state.__dict__) == original_hash
        assert new_state is not original_state
    
    def test_time_advanced_works(self):
        """TIME_ADVANCED event should increase game_minute."""
        state = GameState.initial(seed="time-test")
        
        event = DomainEvent.advance_time(game_minute=0, minutes=120, event_seq=1)
        new_state = reduce_event(state, event)
        
        assert new_state.game_minute == 120
        assert new_state.event_seq == 1
    
    def test_game_minute_calculation_correct(self):
        """game_minute in event must match expected value."""
        state = GameState.initial(seed="calc-test")
        state.event_seq = 5
        state.game_minute = 300
        
        # Event claims to advance time by 60 min from 300 to 360
        event = DomainEvent(
            event_id="evt_006",
            event_seq=6,
            decision_seq=0,
            game_minute=360,
            event_type="TIME_ADVANCED",
            payload={"minutes": 60},
        )
        
        new_state = reduce_event(state, event)
        assert new_state.game_minute == 360
    
    def test_negative_time_rejected(self):
        """TIME_ADVANCED with negative minutes should fail."""
        state = GameState.initial()
        
        # Manual construction with negative payload
        event = DomainEvent(
            event_seq=1,
            event_type="TIME_ADVANCED",
            game_minute=100,
            payload={"minutes": -60},  # Should be invalid
        )
        
        with pytest.raises(ReducerError):
            reduce_event(state, event)
    
    def test_sequence_continuity_check(self):
        """Gap in event sequence must be rejected."""
        state = GameState.initial()
        state.event_seq = 5
        
        event = DomainEvent(event_seq=7)  # Gap!
        
        with pytest.raises(ReducerError) as exc_info:
            reduce_event(state, event)
        
        assert "sequence gap" in str(exc_info.value).lower()
    
    def test_duplicate_sequence_rejected(self):
        """Duplicate event_seq must be rejected."""
        state = GameState.initial()
        state.event_seq = 10
        
        event = DomainEvent(event_seq=10)  # Duplicate!
        
        with pytest.raises(ReducerError) as exc_info:
            reduce_event(state, event)
        
        assert "gap" in str(exc_info.value).lower() or "sequence" in str(exc_info.value).lower()


class TestReducerSequenceConstraints:
    """Tests for sequence number constraints."""
    
    def test_decision_seq_non_retrogression(self):
        """decision_seq cannot decrease."""
        state = GameState.initial()
        state.event_seq = 5
        state.decision_seq = 3
        
        # Attempting to go back in decision_seq
        event = DomainEvent(
            event_seq=6,
            decision_seq=1,  # Less than current 3
            payload={},
        )
        
        with pytest.raises(ReducerError):
            reduce_event(state, event)
    
    def test_decision_seq_can_advance(self):
        """decision_seq can only move forward."""
        state = GameState.initial()
        state.event_seq = 5
        state.decision_seq = 2
        
        event = DomainEvent(
            event_seq=6,
            decision_seq=4,  # Advancing
            payload={},
        )
        
        new_state = reduce_event(state, event)
        assert new_state.decision_seq == 4
    
    def test_game_minute_non_retrogression(self):
        """game_minute cannot go backward."""
        state = GameState.initial()
        state.event_seq = 5
        state.game_minute = 500
        
        # Attempting to set game_minute lower than current (not through TIME_ADVANCED)
        event = DomainEvent(
            event_seq=6,
            event_type="UNKNOWN_EVENT",  # Not TIME_ADVANCED, so no time validation
            game_minute=400,  # Goes back in time!
            payload={},
        )
        
        # This should fail because we're trying to set an older time
        with pytest.raises(ReducerError) as exc_info:
            reduce_event(state, event)
        
        assert "retrogression" in str(exc_info.value).lower()
    
    def test_all_three_sequences_independent(self):
        """event_seq, decision_seq, game_minute are independent counters."""
        state = GameState.initial()
        state.event_seq = 10
        state.decision_seq = 5
        state.game_minute = 1000
        
        # Advance all three
        event = DomainEvent(
            event_seq=11,
            decision_seq=6,
            game_minute=1120,
            event_type="TIME_ADVANCED",
            payload={"minutes": 120},
        )
        
        new_state = reduce_event(state, event)
        assert new_state.event_seq == 11
        assert new_state.decision_seq == 6
        assert new_state.game_minute == 1120


class TestReducerHistoryTracking:
    """Tests for event history tracking in data."""
    
    def test_events_history_populated(self):
        """After applying TIME_ADVANCED, events_history should contain it."""
        state = GameState.initial(seed="history-test")
        
        event = DomainEvent.advance_time(game_minute=0, minutes=30, event_seq=1)
        new_state = reduce_event(state, event)
        
        assert "events_history" in new_state.data
        assert len(new_state.data["events_history"]) == 1
        assert new_state.data["events_history"][0]["event_type"] == "TIME_ADVANCED"
    
    def test_multiple_events_accumulate(self):
        """Multiple events accumulate in history."""
        state = GameState.initial()
        
        event1 = DomainEvent.advance_time(game_minute=0, minutes=60, event_seq=1)
        state = reduce_event(state, event1)
        
        event2 = DomainEvent.advance_time(game_minute=60, minutes=60, event_seq=2)
        state = reduce_event(state, event2)
        
        assert len(state.data["events_history"]) == 2
        assert state.data["events_history"][0]["game_minute"] == 60
        assert state.data["events_history"][1]["game_minute"] == 120
