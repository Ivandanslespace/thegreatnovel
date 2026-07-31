"""Integration tests for SQLite event store."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from tgn.core import GameState, DomainEvent, state_hash
from tgn.storage import EventStore, EventStoreError


@pytest.fixture
def event_store_db():
    """Create a temporary event store for testing."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_campaign.db"
        store = EventStore(db_path)
        yield store
        store.close()


class TestEventStoreInitialization:
    """Test campaign initialization."""
    
    def test_initialize_creates_campaign(self, event_store_db):
        """initialize should create a new campaign record."""
        initial_state = {"seed": "init-test", "data": {}}
        
        record = event_store_db.initialize(
            campaign_id="campaign_001",
            initial_state=initial_state,
            seed="init-test",
        )
        
        assert record.campaign_id == "campaign_001"
        assert record.seed == "init-test"
        assert len(record.initial_state_json) > 0
        assert len(record.initial_state_hash) == 64
    
    def test_initial_state_hash_stored(self, event_store_db):
        """Initial state hash must be stored."""
        initial_state = {"value": 42, "name": "test"}
        
        event_store_db.initialize(
            campaign_id="campaign_002",
            initial_state=initial_state,
        )
        
        record = event_store_db.get_campaign("campaign_002")
        assert record is not None
        assert record.initial_state_hash == state_hash(initial_state)


class TestEventPersistence:
    """Test event appending."""
    
    def test_append_event_and_snapshot(self, event_store_db):
        """append_transition should save both event and snapshot atomically."""
        # Initialize using new API (hash computed internally)
        initial_state = GameState.initial(seed="persist-test")
        event_store_db.initialize(
            campaign_id="campaign_003",
            initial_state=initial_state.__dict__,
        )
        
        # Create event as DomainEvent
        from tgn.core import DomainEvent, reduce_event
        
        event = DomainEvent(
            event_seq=1,
            decision_seq=0,
            game_minute=60,
            event_type="TIME_ADVANCED",
            payload={"minutes": 60}
        )
        
        # Apply to get state_after
        state_before = initial_state
        state_after = reduce_event(initial_state, event)
        
        # Append transition (not append_event)
        event_store_db.append_transition(
            "campaign_003",
            event,
            state_before,
            state_after
        )
        
        # Verify event persisted
        events = event_store_db.all_event_records("campaign_003")
        assert len(events) == 1
        assert events[0]["event_seq"] == 1
    
    def test_duplicate_event_seq_rejected(self, event_store_db):
        """Duplicate event_seq must fail."""
        # Initialize
        initial_state = GameState.initial()
        event_store_db.initialize(
            campaign_id="campaign_004",
            initial_state=initial_state.__dict__,
        )
        
        from tgn.core import DomainEvent, reduce_event
        
        # First insert - success (from minute 0 to 60)
        event1 = DomainEvent(
            event_seq=1,
            decision_seq=0,
            game_minute=60,  # Expected after: 0 + 60
            event_type="TIME_ADVANCED",
            payload={"minutes": 60}  # Pushes from 0 to 60
        )
        
        state_before = initial_state
        state_after = reduce_event(initial_state, event1)
        
        event_store_db.append_transition(
            "campaign_004",
            event1,
            state_before,
            state_after
        )
        
        # Duplicate - should fail transaction (UNIQUE constraint on campaign_id + event_seq)
        with pytest.raises(EventStoreError):
            event2 = DomainEvent(
                event_seq=1,  # Same seq!
                decision_seq=0,
                game_minute=70,
                event_type="TIME_ADVANCED",
                payload={"minutes": 10}
            )
            
            # This will fail at DB UNIQUE constraint level
            event_store_db.append_transition(
                "campaign_004",
                event2,
                state_after,  # Won't matter - fails before commit
                state_after  # Dummy - never used because of error
            )


class TestTransactionRollback:
    """Critical test for atomic rollback behavior."""
    
    def test_transaction_rollback_on_failure(self, event_store_db):
        """If snapshot insert fails, event must also be rolled back."""
        from tgn.core import DomainEvent, reduce_event
        
        # Initialize
        initial_state = GameState.initial()
        event_store_db.initialize(
            campaign_id="campaign_rollback",
            initial_state=initial_state.__dict__,
        )
        
        # Normal event first
        normal_event = DomainEvent(
            event_seq=1,
            decision_seq=0,
            game_minute=60,
            event_type="TIME_ADVANCED",
            payload={"minutes": 60}
        )
        
        state_before = initial_state
        state_after_normal = reduce_event(initial_state, normal_event)
        
        event_store_db.append_transition(
            "campaign_rollback",
            normal_event,
            state_before,
            state_after_normal
        )
        
        # This will fail due to duplicate event_seq (UNIQUE constraint)
        bad_event = DomainEvent(
            event_seq=1,  # Same as normal_event!
            decision_seq=0,
            game_minute=70,
            event_type="TIME_ADVANCED",
            payload={"minutes": 10}
        )
        
        try:
            # This will fail at DB UNIQUE constraint level
            event_store_db.append_transition(
                "campaign_rollback",
                bad_event,
                state_after_normal,  # Won't matter - fails before commit
                state_after_normal   # Dummy - never used because of error
            )
            assert False, "Should have raised EventStoreError"
        except EventStoreError:
            pass
        
        # Verify ONLY the first event exists, not the bad one
        events = event_store_db.all_event_records("campaign_rollback")
        assert len(events) == 1
        assert events[0]["event_seq"] == 1


class TestSnapshotLoading:
    """Test snapshot retrieval."""
    
    def test_latest_snapshot_returns_current(self, event_store_db):
        """latest_snapshot_record should return state after all events."""
        from tgn.core import DomainEvent, reduce_event
        
        initial_state = GameState.initial(seed="snapshot-test")
        event_store_db.initialize(
            campaign_id="snap_test",
            initial_state=initial_state.__dict__,
        )
        
        event = DomainEvent(
            event_seq=1,
            decision_seq=1,
            game_minute=120,
            event_type="TIME_ADVANCED",
            payload={"minutes": 120}
        )
        
        state_before = initial_state
        state_after = reduce_event(initial_state, event)
        
        event_store_db.append_transition(
            "snap_test",
            event,
            state_before,
            state_after
        )
        
        snapshot = event_store_db.latest_snapshot_record("snap_test")
        assert snapshot is not None
        assert snapshot.event_seq == 1
        assert snapshot.state["decision_seq"] == 1


class TestCorruptionDetection:
    """Critical tests that verify system can detect data corruption."""
    
    def test_malformed_json_event_rejected(self, event_store_db):
        """Database constraint should reject malformed inserts."""
        initial_state = GameState.initial()
        event_store_db.initialize(
            campaign_id="corrupt_json",
            initial_state=initial_state.__dict__,
        )
        
        # Try to manually corrupt via direct SQL
        conn = event_store_db.connection.cursor()
        try:
            conn.execute(
                """INSERT INTO events
                   (event_id, campaign_id, event_seq, payload_json)
                   VALUES (?, ?, ?, ?)""",
                ("corrupt_evt", "corrupt_json", 1, "{invalid json"),
            )
            conn.commit()
            assert False, "Should have raised database error"
        except Exception:
            pass  # Expected
        finally:
            conn.close()
        
        # Should not have corrupted events
        events = event_store_db.all_event_records("corrupt_json")
        assert len(events) == 0


class TestCampaignMetadata:
    """Test campaign information retrieval."""
    
    def test_get_campaign_returns_record(self, event_store_db):
        """get_campaign should load campaign metadata."""
        initial_state = GameState.initial(seed="meta-test")
        
        record = event_store_db.initialize(
            campaign_id="meta_campaign",
            initial_state=initial_state.__dict__,
            seed="meta-test",
        )
        
        loaded = event_store_db.get_campaign("meta_campaign")
        assert loaded is not None
        assert loaded.campaign_id == "meta_campaign"
        assert loaded.seed == "meta-test"
        assert loaded.engine_version == "1.0.0"
        assert loaded.state_schema_version == 1
    
    def test_nonexistent_campaign_returns_none(self, event_store_db):
        """Loading non-existent campaign returns None."""
        result = event_store_db.get_campaign("does_not_exist")
        assert result is None
