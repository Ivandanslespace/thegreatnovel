"""Phase 2 - Action Contract Tests (Mandatory Acceptance Tests)."""

import pytest
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from tgn.core.models import GameState, DomainEvent
from tgn.actions.models import (
    ActionIntent,
    ValidatedAction,
    ActionValidationResult,
    ActionExecutionResult,
    ActionValidationError,
)
from tgn.actions.validation import validate_action, execute_action


class TestWaitActionIsLegal:
    """WAIT is the only legal action in Phase 2."""
    
    def test_wait_action_is_legal(self):
        """WAIT action should be accepted."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        
        state = GameState.initial()
        result = validate_action(state, intent)
        
        assert result.valid
        assert result.action is not None
        assert result.action.action_type == "WAIT"


class TestUnknownActionRejected:
    """Unknown actions must be rejected without side effects."""
    
    def test_unknown_action_is_rejected_without_state_change(self):
        """FLY_TO_MOON should be rejected and not change anything."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="FLY_TO_MOON",
            params={},
        )
        
        state_before = GameState.initial()
        result = validate_action(state_before, intent)
        
        assert not result.valid
        assert result.action is None
        assert len(result.errors) == 1
        assert result.errors[0].code == "UNKNOWN_ACTION"


class TestWaitRequiresMinutes:
    """WAIT requires minutes parameter."""
    
    def test_wait_requires_minutes(self):
        """Missing minutes should fail validation."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={},
        )
        
        state = GameState.initial()
        result = validate_action(state, intent)
        
        assert not result.valid
        assert any(e.code == "MISSING_FIELD" for e in result.errors)
    
    def test_wait_rejects_zero_minutes(self):
        """Zero minutes is invalid."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 0},
        )
        
        state = GameState.initial()
        result = validate_action(state, intent)
        
        assert not result.valid
        assert any(e.code == "INVALID_VALUE" for e in result.errors)
    
    def test_wait_rejects_negative_minutes(self):
        """Negative minutes is invalid."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": -30},
        )
        
        state = GameState.initial()
        result = validate_action(state, intent)
        
        assert not result.valid
        assert any(e.code == "INVALID_VALUE" for e in result.errors)


class TestWaitRejectsNonIntegerAndBoolean:
    """Minutes must be integer, not string/float/bool."""
    
    def test_wait_rejects_non_integer_minutes(self):
        """String minutes should fail."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": "60"},
        )
        
        state = GameState.initial()
        result = validate_action(state, intent)
        
        assert not result.valid
        assert any(e.code == "INVALID_TYPE" for e in result.errors)
    
    def test_wait_rejects_float_minutes(self):
        """Float minutes should fail."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 1.5},
        )
        
        state = GameState.initial()
        result = validate_action(state, intent)
        
        assert not result.valid
        assert any(e.code == "INVALID_TYPE" for e in result.errors)
    
    def test_wait_rejects_boolean_minutes(self):
        """Boolean minutes should fail (even though bool is subclass of int!)."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": True},
        )
        
        state = GameState.initial()
        result = validate_action(state, intent)
        
        assert not result.valid
        assert any(e.code == "INVALID_TYPE" for e in result.errors)


class TestActionIntentCannotControlMetadata:
    """Intent cannot control engine metadata like event_seq/game_minute."""
    
    @pytest.mark.parametrize("forbidden_field", [
        "event_seq",
        "decision_seq", 
        "game_minute",
        "state_hash",
        "event_id",
        "created_at",
    ])
    def test_action_intent_cannot_control_engine_metadata(self, forbidden_field):
        """Intent with forbidden metadata should be rejected."""
        params = {"minutes": 60}
        params[forbidden_field] = 999  # Try to inject metadata
        
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params=params,
        )
        
        state = GameState.initial()
        result = validate_action(state, intent)
        
        assert not result.valid
        assert result.action is None
        assert any(e.code == "FORBIDDEN_ENGINE_METADATA" for e in result.errors)


class TestValidationDoesNotMutateState:
    """Validation must be pure - no side effects."""
    
    def test_validation_does_not_mutate_state(self):
        """validate_action should not mutate input state."""
        state = GameState.initial(seed="test")
        original_event_seq = state.event_seq
        
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        
        validate_action(state, intent)
        
        # State should be unchanged
        assert state.event_seq == original_event_seq
        assert state.decision_seq == 0
        assert state.game_minute == 0


class TestAcceptedActionIncrementsDecisionSeq:
    """Accepted actions increment decision_seq."""
    
    def test_accepted_action_increments_decision_seq_once(self):
        """One accepted action = +1 decision_seq."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        
        state = GameState.initial()
        result = execute_action(state, intent)
        
        assert result.accepted
        assert len(result.events) == 1
        assert result.events[0].decision_seq == 1
    
    def test_rejected_action_does_not_increment_decision_seq(self):
        """Rejected action does not increment decision_seq."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="UNKNOWN_ACTION",
            params={},
        )
        
        state = GameState.initial()
        result = execute_action(state, intent)
        
        assert not result.accepted
        assert len(result.events) == 0


class TestEventSequenceSemantics:
    """Event sequence must be controlled by engine, not by actions."""
    
    def test_accepted_action_uses_next_event_seq(self):
        """Accepted action produces event with event_seq = old + 1."""
        state = GameState(
            schema_version=1,
            event_seq=5,
            decision_seq=0,
            game_minute=0,
            seed="seq-test",
            data={},
        )
        
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        
        result = execute_action(state, intent)
        
        assert result.accepted
        assert len(result.events) == 1
        assert result.events[0].event_seq == 6
        assert result.final_state is not None
        assert result.final_state.event_seq == 6
    
    def test_rejected_action_does_not_increment_event_seq(self):
        """Rejected action produces no events and doesn't change event_seq."""
        state = GameState(
            schema_version=1,
            event_seq=10,
            decision_seq=0,
            game_minute=0,
            seed="reject-seq-test",
            data={},
        )
        
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="FLY_TO_MOON",
            params={},
        )
        
        result = execute_action(state, intent)
        
        assert not result.accepted
        assert len(result.events) == 0
        assert result.final_state is None
        
        # Original state should remain unchanged (no mutation occurred)
        assert state.event_seq == 10


class TestSequenceSemantics:
    """Combined sequence number semantics."""
    
    def test_second_action_uses_next_decision_and_event_sequence(self):
        """Second accepted action uses decision_seq=2 and event_seq=2."""
        state1 = GameState.initial()
        
        intent1 = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        result1 = execute_action(state1, intent1)
        
        state2 = result1.final_state
        assert state2 is not None
        assert state2.event_seq == 1
        assert state2.decision_seq == 1
        
        intent2 = ActionIntent(
            action_id="test-002",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 30},
        )
        result2 = execute_action(state2, intent2)
        
        assert result2.accepted
        assert result2.events[0].event_seq == 2
        assert result2.events[0].decision_seq == 2


class TestTimeSemantics:
    """WAIT must advance time exactly once."""
    
    def test_wait_advances_game_time_exactly_once(self):
        """WAIT advances game_minute by exactly the amount specified."""
        state = GameState(
            schema_version=1,
            event_seq=0,
            decision_seq=0,
            game_minute=0,
            seed="time-test",
            data={},
        )
        
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        
        result = execute_action(state, intent)
        
        assert result.accepted
        assert len(result.events) == 1
        assert result.events[0].game_minute == 60
        assert result.events[0].payload["minutes"] == 60
        assert result.final_state is not None
        assert result.final_state.game_minute == 60
    
    def test_rejected_action_does_not_advance_time(self):
        """Rejected actions do not change time."""
        state = GameState(
            schema_version=1,
            event_seq=0,
            decision_seq=0,
            game_minute=60,
            seed="reject-test",
            data={},
        )
        
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="UNKNOWN_ACTION",
            params={},
        )
        
        result = execute_action(state, intent)
        
        assert not result.accepted
        assert result.final_state is None


class TestIllegalActionZeroSideEffects:
    """Comprehensive integration test proving illegal actions have ZERO side effects."""
    
    def test_illegal_action_has_zero_side_effects_end_to_end(self):
        """One complete test proving all zero side effect invariants."""
        from pathlib import Path
        from tgn.storage import EventStore
        from tgn.core.hashing import state_hash
        
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "zero_side.db"
            
            # Setup
            store = EventStore(db_path)
            try:
                initial = GameState.initial(seed="zero-test")
                store.initialize("camp_zero", initial.__dict__)
                
                # Record canonical state hash BEFORE illegal action
                initial_hash_before = state_hash(initial.__dict__)
                
                conn = sqlite3.connect(str(db_path))
                events_before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                snapshots_before = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
                conn.close()
                
                # Execute illegal action
                intent = ActionIntent(
                    action_id="illegal-001",
                    actor_id="player",
                    action_type="FLY_TO_MOON",  # Unknown, illegal action
                    params={},
                )
                
                result = execute_action(initial, intent)
                
                # Record canonical state hash AFTER illegal action
                initial_hash_after = state_hash(initial.__dict__)
                
                # Assert 1: Execution returns rejected
                assert not result.accepted
                assert len(result.events) == 0
                assert result.final_state is None
                
                # Assert 2: Original state unchanged (by value and by hash)
                assert initial.event_seq == 0
                assert initial.decision_seq == 0
                assert initial.game_minute == 0
                # Canonical proof: hash must be identical
                assert initial_hash_after == initial_hash_before
                
                # Assert 3: No database changes
                conn = sqlite3.connect(str(db_path))
                events_after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                snapshots_after = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
                conn.close()
                
                assert events_after == events_before, "Event count changed!"
                assert snapshots_after == snapshots_before, "Snapshot count changed!"
                
            finally:
                store.close()


class TestCausation:
    """Action → Event causation chain."""
    
    def test_action_id_propagates_to_domain_event(self):
        """action_id from Intent must be in DomainEvent."""
        state = GameState.initial()
        
        intent = ActionIntent(
            action_id="my-action-123",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        
        result = execute_action(state, intent)
        
        assert result.accepted
        assert result.events[0].action_id == "my-action-123"
    
    def test_actor_id_propagates_to_domain_event(self):
        """actor_id from Intent must be in DomainEvent."""
        state = GameState.initial()
        
        intent = ActionIntent(
            action_id="test-001",
            actor_id="my-player-456",
            action_type="WAIT",
            params={"minutes": 60},
        )
        
        result = execute_action(state, intent)
        
        assert result.accepted
        assert result.events[0].actor_id == "my-player-456"


class TestDeterminismAndReplay:
    """Phase 2 must be deterministic."""
    
    def test_same_state_and_intent_produce_same_final_state_hash(self):
        """Identical inputs must produce identical outputs."""
        from tgn.core.hashing import state_hash
        
        state = GameState.initial(seed="determinism-test")
        
        intent1 = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        result1 = execute_action(state, intent1)
        
        intent2 = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        result2 = execute_action(state, intent2)
        
        assert result1.final_state is not None
        assert result2.final_state is not None
        
        hash1 = state_hash(result1.final_state.__dict__)
        hash2 = state_hash(result2.final_state.__dict__)
        
        assert hash1 == hash2, "Same inputs produced different hashes!"
    
    def test_action_generated_event_replays_to_same_final_state(self):
        """Events generated by actions must replay correctly via verifier."""
        state = GameState.initial(seed="replay-test")
        
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        
        result = execute_action(state, intent)
        assert result.accepted
        
        # Replay via standard replay mechanism
        from tgn.storage.replay import replay_events
        replay_result = replay_events(state, list(result.events))
        
        assert replay_result.success
        assert replay_result.final_state == result.final_state.__dict__


class TestPersistenceIntegration:
    """Integration with Phase 1 persistence layer."""
    
    def test_execute_persist_reopen_verify_end_to_end(self):
        """Full E2E: execute → persist → close → reopen → verify."""
        from tgn.storage import EventStore, verify_persistence_integrity
        
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "action_e2e.db"
            
            # Setup
            store = EventStore(db_path)
            try:
                initial = GameState.initial(seed="e2e-test")
                store.initialize("camp_e2e", initial.__dict__)
                
                # Execute action
                intent = ActionIntent(
                    action_id="e2e-action-001",
                    actor_id="player",
                    action_type="WAIT",
                    params={"minutes": 60},
                )
                
                exec_result = execute_action(initial, intent)
                assert exec_result.accepted
                
                # Persist using Phase 1 API (no new API!)
                event = exec_result.events[0]
                final_state = exec_result.final_state
                
                store.append_transition(
                    "camp_e2e",
                    event,
                    initial,
                    final_state,
                )
            finally:
                store.close()
            
            # Reopen and verify
            new_store = EventStore(db_path)
            try:
                verify_result = verify_persistence_integrity("camp_e2e", db_path)
                
                assert verify_result.success
                assert verify_result.final_state == final_state.__dict__
            finally:
                new_store.close()
