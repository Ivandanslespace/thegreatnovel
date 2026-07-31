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
        """append_event should save both event and snapshot atomically."""
        # Initialize
        initial_state = GameState.initial(seed="persist-test")
        event_store_db.initialize(
            campaign_id="campaign_003",
            initial_state=initial_state.__dict__,
            initial_state_hash=state_hash(initial_state.__dict__),
        )
        
        # Create event
        event_dict = {
            "event_id": "evt_001",
            "event_seq": 1,
            "decision_seq": 0,
            "game_minute": 60,
            "event_type": "TIME_ADVANCED",
            "payload": {"minutes": 60},
        }
        
        event_store_db.append_event(
            campaign_id="campaign_003",
            event_dict=event_dict,
            state_hash_before=state_hash(initial_state.__dict__),
            state_hash_after=state_hash({"event_seq": 1}),
        )
        
        # Verify event persisted
        events = event_store_db.all_events("campaign_003")
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
        
        event_dict = {
            "event_id": "evt_001",
            "event_seq": 1,
            "decision_seq": 0,
            "game_minute": 60,
            "event_type": "TIME_ADVANCED",
            "payload": {},
        }
        
        # First insert - success
        event_store_db.append_event(
            campaign_id="campaign_004",
            event_dict=event_dict,
            state_hash_before="",
            state_hash_after="",
        )
        
        # Duplicate - should fail transaction
        with pytest.raises(EventStoreError):
            event_store_db.append_event(
                campaign_id="campaign_004",
                event_dict={**event_dict, "event_id": "evt_001_dup"},
                state_hash_before="",
                state_hash_after="",
            )


class TestTransactionRollback:
    """Critical test for atomic rollback behavior."""
    
    def test_transaction_rollback_on_failure(self, event_store_db):
        """If snapshot insert fails, event must also be rolled back."""
        # Initialize
        initial_state = GameState.initial()
        event_store_db.initialize(
            campaign_id="campaign_rollback",
            initial_state=initial_state.__dict__,
        )
        
        # Normal event first
        normal_event = {
            "event_id": "normal_evt",
            "event_seq": 1,
            "decision_seq": 0,
            "game_minute": 60,
            "event_type": "TIME_ADVANCED",
            "payload": {"minutes": 60},
        }
        event_store_db.append_event(
            campaign_id="campaign_rollback",
            event_dict=normal_event,
            state_hash_before=state_hash(initial_state.__dict__),
            state_hash_after="",
        )
        
        # This will fail due to duplicate event_seq
        bad_event = {
            "event_id": "bad_evt",
            "event_seq": 1,  # Same as normal_event!
            "decision_seq": 0,
            "game_minute": 70,
            "event_type": "TIME_ADVANCED",
            "payload": {"minutes": 10},
        }
        
        try:
            event_store_db.append_event(
                campaign_id="campaign_rollback",
                event_dict=bad_event,
                state_hash_before="",
                state_hash_after="",
            )
            assert False, "Should have raised EventStoreError"
        except EventStoreError:
            pass
        
        # Verify ONLY the first event exists, not the bad one
        events = event_store_db.all_events("campaign_rollback")
        assert len(events) == 1
        assert events[0]["event_id"] == "normal_evt"


class TestSnapshotLoading:
    """Test snapshot retrieval."""
    
    def test_latest_snapshot_returns_current(self, event_store_db):
        """latest_snapshot should return state after all events."""
        initial_state = GameState.initial(seed="snapshot-test")
        event_store_db.initialize(
            campaign_id="snap_test",
            initial_state=initial_state.__dict__,
        )
        
        event_dict = {
            "event_id": "evt_snap",
            "event_seq": 1,
            "decision_seq": 1,
            "game_minute": 120,
            "event_type": "TIME_ADVANCED",
            "payload": {"minutes": 120},
            "_state_snapshot": {"event_seq": 1, "decision_seq": 1},
        }
        
        event_store_db.append_event(
            campaign_id="snap_test",
            event_dict=event_dict,
            state_hash_before="",
            state_hash_after=state_hash(event_dict["_state_snapshot"]),
        )
        
        snapshot = event_store_db.latest_snapshot("snap_test")
        assert snapshot is not None
        assert snapshot["event_seq"] == 1
        assert snapshot["decision_seq"] == 1


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
        events = event_store_db.all_events("corrupt_json")
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
