"""Replay and verification tests."""

import pytest
from tgn.core import GameState, DomainEvent, state_hash
from tgn.storage import replay_campaign, ReplayResult


class TestBasicReplay:
    """Basic replay functionality tests."""
    
    def test_replay_single_event(self):
        """Single event replay should work."""
        initial = GameState.initial(seed="replay-test")
        
        events = [
            DomainEvent(
                event_seq=1, decision_seq=0, game_minute=60,
                event_type="TIME_ADVANCED", payload={"minutes": 60}
            ),
        ]
        
        result = replay_campaign(initial.__dict__, events)
        
        assert result.success
        assert result.final_state["game_minute"] == 60
        assert result.states_replayed == 1
    
    def test_replay_multiple_events(self):
        """Multiple sequential events replay correctly."""
        initial = GameState.initial(seed="multi-replay")
        
        events = [
            DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
            DomainEvent(event_seq=2, decision_seq=0, game_minute=120,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
            DomainEvent(event_seq=3, decision_seq=0, game_minute=180,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
        ]
        
        result = replay_campaign(initial.__dict__, events)
        
        assert result.success
        assert result.final_state["game_minute"] == 180
        assert result.states_replayed == 3
    
    def test_replay_deterministic(self):
        """Same inputs must produce same output every time."""
        initial = GameState.initial(seed="determinism-test")
        
        events = [
            DomainEvent(event_seq=1, decision_seq=0, game_minute=120,
                       event_type="TIME_ADVANCED", payload={"minutes": 120}),
            DomainEvent(event_seq=2, decision_seq=1, game_minute=120, payload={}),
        ]
        
        hash1 = replay_campaign(initial.__dict__, events).actual_hash
        hash2 = replay_campaign(initial.__dict__, events).actual_hash
        hash3 = replay_campaign(initial.__dict__, events).actual_hash
        
        assert hash1 == hash2 == hash3


class TestReplayDivergenceLocalization:
    """Tests that identify exactly which event causes failure."""
    
    def test_failure_on_missing_middle_event(self):
        """Missing event in middle should fail at that seq number."""
        initial = GameState.initial()
        
        events = [
            DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
            DomainEvent(event_seq=3, decision_seq=0, game_minute=120,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),  # Gap!
        ]
        
        result = replay_campaign(initial.__dict__, events)
        
        assert not result.success
        assert result.failed_event_seq == 3
        assert "sequence gap" in result.error_message.lower()
    
    def test_failure_on_duplicate_event_seq(self):
        """Duplicate event_seq should be caught."""
        initial = GameState.initial()
        
        events = [
            DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
            DomainEvent(event_seq=1, decision_seq=0, game_minute=70,
                       event_type="TIME_ADVANCED", payload={"minutes": 10}),  # Duplicate!
        ]
        
        result = replay_campaign(initial.__dict__, events)
        
        assert not result.success
        assert result.failed_event_seq == 1
        assert result.error_message is not None


class TestCorruptionDetection:
    """Critical tests for detecting data corruption."""
    
    def test_detect_modified_payload(self):
        """Modified event payload will cause game_minute mismatch."""
        initial = GameState.initial(seed="corrupt-payload")
        
        original_events = [
            DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
            DomainEvent(event_seq=2, decision_seq=0, game_minute=120,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
        ]
        
        # Replay originals - should succeed
        original_result = replay_campaign(initial.__dict__, original_events)
        assert original_result.success
        
        # Corrupted - wrong minutes will cause game_minute mismatch
        corrupted_events = [
            DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
            DomainEvent(event_seq=2, decision_seq=0, game_minute=120,
                       event_type="TIME_ADVANCED", payload={"minutes": 999}),  # Wrong!
        ]
        
        corrupted_result = replay_campaign(initial.__dict__, corrupted_events)
        assert not corrupted_result.success  # Should fail
    
    def test_detect_reordered_events(self):
        """Event reordering should change results."""
        initial = GameState.initial()
        
        # Correct order
        ordered_events = [
            DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
            DomainEvent(event_seq=2, decision_seq=0, game_minute=120,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
        ]
        
        # Wrong order
        reversed_events = [
            DomainEvent(event_seq=2, decision_seq=0, game_minute=120,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
            DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
        ]
        
        result_ordered = replay_campaign(initial.__dict__, ordered_events)
        result_reversed = replay_campaign(initial.__dict__, reversed_events)
        
        assert result_ordered.success
        assert not result_reversed.success
        assert result_reversed.failed_event_seq == 2


class TestHashVerification:
    """Tests for hash-based integrity verification."""
    
    def test_correct_hash_verifies(self):
        """Correct hash should verify successfully."""
        initial = GameState.initial(seed="hash-verify")
        
        events = [
            DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
        ]
        
        result = replay_campaign(initial.__dict__, events)
        
        assert result.success
        assert result.expected_hash == result.actual_hash
    
    def test_hash_changes_with_data_modification(self):
        """Any state modification should change hash."""
        base_state = {
            "schema_version": 1, "event_seq": 1, "decision_seq": 0,
            "game_minute": 60, "seed": "test", "data": {},
        }
        
        hash_original = state_hash(base_state)
        
        modified_state = base_state.copy()
        modified_state["game_minute"] = 120
        
        hash_modified = state_hash(modified_state)
        
        assert hash_original != hash_modified
    
    def test_complex_state_hashes_deterministically(self):
        """Complex nested state hashes consistently."""
        complex_state = {
            "meta": {"version": 1, "nested": {"z": 1, "a": 2}},
            "resources": {"food": [{"id": "a"}, {"id": "b"}], "fuel": 50},
            "location": "camp_001",
        }
        
        hash1 = state_hash(complex_state)
        hash2 = state_hash(complex_state)
        
        assert hash1 == hash2
        assert len(hash1) == 64


class TestReplayWithHistory:
    """Test replay tracking intermediate states."""
    
    def test_history_tracking_enabled(self):
        """When enabled, replay should track all states."""
        initial = GameState.initial()
        
        events = [
            DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
            DomainEvent(event_seq=2, decision_seq=0, game_minute=120,
                       event_type="TIME_ADVANCED", payload={"minutes": 60}),
        ]
        
        result = replay_campaign(initial.__dict__, events, state_at_each_step=True)
        
        assert hasattr(result, 'history')
        assert len(result.history) == 3  # Initial + 2 steps
