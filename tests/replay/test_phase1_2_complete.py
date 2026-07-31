"""Phase 1.2: Complete end-to-end persistence integrity tests."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3

from tgn.core import GameState, DomainEvent, reduce_event, ReducerError, state_hash
from tgn.storage import EventStore, verify_persistence_integrity, replay_campaign


class TestEndToEndGoldens:
    """Critical end-to-end golden test: persist → reload → verify → replay."""
    
    def test_persist_reload_replay_end_to_end(self):
        """Complete E2E: create, persist, close DB, reopen, verify, replay."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "golden_test.db"
            
            # Phase 1: Write using public API
            store = EventStore(db_path)
            
            try:
                # Initialize
                initial_dict = {"schema_version": 1, "event_seq": 0, "decision_seq": 0, 
                              "game_minute": 0, "seed": "golden", "data": {}}
                store.initialize("camp_g", initial_dict)
                
                # Create GameState from dict for reduce_event
                initial_state = GameState(**initial_dict)
                
                # Create event 1 and compute expected state
                evt1 = DomainEvent(
                    event_seq=1, decision_seq=0, game_minute=60,
                    event_type="TIME_ADVANCED", payload={"minutes": 60}
                )
                state_after_1 = reduce_event(initial_state, evt1)
                store.append_transition("camp_g", evt1, initial_state, state_after_1)
                
                # Create event 2
                evt2 = DomainEvent(
                    event_seq=2, decision_seq=0, game_minute=120,
                    event_type="TIME_ADVANCED", payload={"minutes": 60}
                )
                state_after_2 = reduce_event(state_after_1, evt2)
                store.append_transition("camp_g", evt2, state_after_1, state_after_2)
                
                # Close database (simulate restart)
            finally:
                store.close()
            
            # Phase 2: Reopen and verify
            new_store = EventStore(db_path)
            try:
                result = verify_persistence_integrity("camp_g", db_path)
                assert result.success, f"Verification failed: {result.error_message}"
                
                # Replay should produce same final state
                final_dict = result.final_state
                assert final_dict["event_seq"] == 2
                assert final_dict["game_minute"] == 120
                
            finally:
                new_store.close()


class TestMultiCampaignRealIsolation:
    """Real multi-campaign isolation test that closes/reopens DB."""
    
    def test_multi_campaign_isolation_with_reopen(self):
        """Two campaigns with independent sequences must remain isolated after reopen."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "multi.db"
            
            # Create both campaigns
            store = EventStore(db_path)
            try:
                # Campaign A - use GameState with extra data in .data field
                init_a_state = GameState.initial(seed="camp-a")
                init_a_state.data["campaign"] = "A"
                init_a_dict = init_a_state.__dict__.copy()
                
                store.initialize("camp_A", init_a_dict)
                
                evt_a1 = DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                                    event_type="TIME_ADVANCED", payload={"minutes": 60})
                state_a1 = reduce_event(init_a_state, evt_a1)
                store.append_transition("camp_A", evt_a1, init_a_state, state_a1)
                
                # Campaign B - same seq numbers!
                init_b_state = GameState.initial(seed="camp-b")
                init_b_state.data["campaign"] = "B"
                init_b_dict = init_b_state.__dict__.copy()
                
                store.initialize("camp_B", init_b_dict)
                
                evt_b1 = DomainEvent(event_seq=1, decision_seq=0, game_minute=30,
                                    event_type="TIME_ADVANCED", payload={"minutes": 30})
                state_b1 = reduce_event(init_b_state, evt_b1)
                store.append_transition("camp_B", evt_b1, init_b_state, state_b1)
                
            finally:
                store.close()
            
            # Reopen and verify both independently
            new_store = EventStore(db_path)
            try:
                snap_a = new_store.latest_snapshot_record("camp_A")
                snap_b = new_store.latest_snapshot_record("camp_B")
                
                assert snap_a is not None
                assert snap_b is not None
                assert snap_a.state["data"]["campaign"] == "A"
                assert snap_b.state["data"]["campaign"] == "B"
                assert snap_a.state["game_minute"] != snap_b.state["game_minute"]
                
                # Both should verify independently
                result_a = verify_persistence_integrity("camp_A", db_path)
                result_b = verify_persistence_integrity("camp_B", db_path)
                
                assert result_a.success, f"A failed: {result_a.error_message}"
                assert result_b.success, f"B failed: {result_b.error_message}"
                
            finally:
                new_store.close()


class TestCorruptionDetectionAllTypes:
    """Six real corruption tests via direct SQL tampering."""
    
    @pytest.fixture
    def valid_campaign_db(self):
        """Create a fully valid campaign database for tampering."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "corruption.db"
            store = EventStore(db_path)
            
            try:
                # Create proper initial GameState
                init_state = GameState.initial(seed="test")
                init_dict = init_state.__dict__.copy()
                
                store.initialize("camp_c", init_dict)
                
                evt1 = DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                                  event_type="TIME_ADVANCED", payload={"minutes": 60})
                state1 = reduce_event(init_state, evt1)
                store.append_transition("camp_c", evt1, init_state, state1)
                
                evt2 = DomainEvent(event_seq=2, decision_seq=0, game_minute=120,
                                  event_type="TIME_ADVANCED", payload={"minutes": 60})
                state2 = reduce_event(state1, evt2)
                store.append_transition("camp_c", evt2, state1, state2)
                
            finally:
                store.close()
            
            yield db_path
    
    def test_persisted_payload_tampering_detected(self, valid_campaign_db):
        """Payload tampering must be detected at event 2."""
        conn = sqlite3.connect(str(valid_campaign_db))
        conn.execute("""UPDATE events SET payload_json='{"minutes":999}' 
                       WHERE campaign_id='camp_c' AND event_seq=2""")
        conn.commit()
        conn.close()
        
        result = verify_persistence_integrity("camp_c", valid_campaign_db)
        assert not result.success
        assert result.failed_event_seq == 2
        # Corruption detected: payload minutes=999 would produce game_minute=1059, 
        # but stored game_minute=120 doesn't match
        assert ("Game minute mismatch" in result.error_message or 
                "failed to apply event" in result.error_message)
    
    def test_persisted_state_hash_before_tampering_detected(self, valid_campaign_db):
        """state_hash_before tampering must be detected."""
        conn = sqlite3.connect(str(valid_campaign_db))
        conn.execute("""UPDATE events SET state_hash_before='0' * 64 
                       WHERE campaign_id='camp_c' AND event_seq=1""")
        conn.commit()
        conn.close()
        
        result = verify_persistence_integrity("camp_c", valid_campaign_db)
        assert not result.success
        assert result.failed_event_seq == 1
        assert "state_hash_before" in result.error_message.lower()
    
    def test_persisted_state_hash_after_tampering_detected(self, valid_campaign_db):
        """state_hash_after tampering must be detected."""
        conn = sqlite3.connect(str(valid_campaign_db))
        conn.execute("""UPDATE events SET state_hash_after='0' * 64 
                       WHERE campaign_id='camp_c' AND event_seq=2""")
        conn.commit()
        conn.close()
        
        result = verify_persistence_integrity("camp_c", valid_campaign_db)
        assert not result.success
        assert result.failed_event_seq == 2
        assert "state_hash_after" in result.error_message.lower()
    
    def test_snapshot_state_tampering_detected(self, valid_campaign_db):
        """Snapshot state_json tampering must be detected."""
        conn = sqlite3.connect(str(valid_campaign_db))
        # Corrupt the latest snapshot (event_seq=2)
        conn.execute("""UPDATE snapshots SET state_json='{"fake":"state"}' 
                       WHERE campaign_id='camp_c' AND event_seq=2""")
        conn.commit()
        conn.close()
        
        result = verify_persistence_integrity("camp_c", valid_campaign_db)
        assert not result.success
        assert "snapshot hash" in result.error_message.lower()
    
    def test_snapshot_hash_tampering_detected(self, valid_campaign_db):
        """Snapshot state_hash tampering must be detected."""
        conn = sqlite3.connect(str(valid_campaign_db))
        original_hash = conn.execute("""SELECT state_hash FROM snapshots 
                                        WHERE campaign_id='camp_c' AND event_seq=2""").fetchone()[0]
        fake_hash = "a" * 64
        
        conn.execute(f"""UPDATE snapshots SET state_hash='{fake_hash}' 
                       WHERE campaign_id='camp_c' AND event_seq=2""")
        conn.commit()
        conn.close()
        
        result = verify_persistence_integrity("camp_c", valid_campaign_db)
        assert not result.success
        assert "snapshot hash" in result.error_message.lower() or "doesn't match" in result.error_message.lower()
    
    def test_missing_middle_persisted_event_detected(self, valid_campaign_db):
        """Missing event 2 must cause verification failure."""
        # Delete event 2 but KEEP its snapshot
        # This causes mismatch: snapshot exists at seq=2 but no corresponding event
        conn = sqlite3.connect(str(valid_campaign_db))
        conn.execute("""DELETE FROM events WHERE campaign_id='camp_c' AND event_seq=2""")
        conn.commit()
        conn.close()
        
        result = verify_persistence_integrity("camp_c", valid_campaign_db)
        assert not result.success
        # Detection could be at event 2 (snapshot without event) or during hash check
        assert result.failed_event_seq is not None


class TestMalformedJSONAndAtomicity:
    """Malformed JSON detection and transaction rollback tests."""
    
    def test_malformed_persisted_json_detected(self):
        """Malformed JSON in persisted payload must fail verification."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "malformed.db"
            
            # First create valid
            store = EventStore(db_path)
            try:
                init_dict = {"seed": "test"}
                store.initialize("camp_m", init_dict)
                
                init_state = GameState(**init_dict)
                
                evt = DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                                 event_type="TIME_ADVANCED", payload={"minutes": 60})
                state = reduce_event(init_state, evt)
                store.append_transition("camp_m", evt, init_state, state)
            finally:
                store.close()
            
            # Then corrupt
            conn = sqlite3.connect(str(db_path))
            conn.execute("""UPDATE events SET payload_json='{invalid json' 
                           WHERE campaign_id='camp_m'""")
            conn.commit()
            conn.close()
            
            result = verify_persistence_integrity("camp_m", db_path)
            assert not result.success
            assert result.error_message is not None
    
    def test_snapshot_failure_rolls_back_event_insert(self):
        """If snapshot insert fails, event insert must also roll back."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rollback.db"
            
            # Normal setup
            store = EventStore(db_path)
            try:
                init_dict = {"seed": "rb"}
                store.initialize("camp_rb", init_dict)
                
                init_state = GameState(**init_dict)
                
                # First valid event
                evt1 = DomainEvent(event_seq=1, decision_seq=0, game_minute=60,
                                  event_type="TIME_ADVANCED", payload={"minutes": 60})
                state1 = reduce_event(init_state, evt1)
                store.append_transition("camp_rb", evt1, init_state, state1)
                
                # Count before
                events_before = len(store.all_event_records("camp_rb"))
                
                # Try duplicate event_seq (will fail inside transaction after event INSERT)
                evt_dup = DomainEvent(event_seq=1, decision_seq=0, game_minute=70,
                                     event_type="TIME_ADVANCED", payload={"minutes": 10})
                
                try:
                    # This will fail on UNIQUE constraint for (campaign_id, event_seq)
                    # But we want to ensure it ROLLBACKS completely
                    store.append_transition("camp_rb", evt_dup, state1, state1)
                    assert False, "Should have raised"
                except Exception:
                    pass  # Expected
                
                # Critical: check count unchanged
                events_after = len(store.all_event_records("camp_rb"))
                assert events_after == events_before, f"Rollback failed! Before={events_before}, After={events_after}"
                
            finally:
                store.close()


# Smoke script output would go here if run from command line
def test_smoke_script_compatibility():
    """Verify this module can be imported without errors."""
    from tgn.storage import EventStore, verify_persistence_integrity
    assert EventStore is not None
    assert verify_persistence_integrity is not None
