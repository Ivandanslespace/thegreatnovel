"""Phase 3.5 E2E tests per spec sections #25, #26, #30, #31."""

import json
import tempfile
from pathlib import Path

import pytest
from tgn.autoplay import (
    run_autoplay,
    AutoplayConfig,
    StopReason,
    choose_action,
    write_run_jsonl,
)
from tgn.core.hashing import state_hash
from tgn.storage.event_store import EventStore
from tgn.storage import verify_persistence_integrity


class TestPhase35E2E:
    """End-to-end autoplay tests."""
    
    def test_default_e2e_vertical_slice(self, phase35_initial_state):
        """Default run produces expected Phase 3 vertical slice per spec #25."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        # Counts
        assert result.decisions == 3
        assert result.events == 3
        
        # Sequences
        action_types = [f.action_type for f in result.frames]
        event_types = [f.event_type for f in result.frames]
        
        assert action_types == ["DROP", "SEARCH", "EXTRACT"]
        assert event_types == ["EXPEDITION_DROPPED", "SEARCH_RESOLVED", "EXPEDITION_EXTRACTED"]
        
        # Final state
        final = result.final_state
        assert final.game_minute == 55
        assert final.data["player"]["stamina"] == 0
        assert final.data["player"]["location_id"] == "base-1"
        assert final.data["inventory"] == {"salvage": 2}
        assert final.data["expedition"]["carried_loot"] == {}
        assert final.data["expedition"]["target_loot"] == {}
        assert final.data["expedition"]["target_searched"] is True
        assert final.data["expedition"]["active"] is False
        
        # Stop reason
        assert result.stop_reason == StopReason.POLICY_COMPLETE
    
    def test_determinism_across_runs(self, phase35_initial_state):
        """Two independent runs produce identical semantic results per spec #26."""
        config = AutoplayConfig()
        
        # Run A
        result_a = run_autoplay(phase35_initial_state, choose_action, config)
        
        # Run B (from fresh state copy)
        from copy import deepcopy
        state_b = deepcopy(phase35_initial_state)
        result_b = run_autoplay(state_b, choose_action, config)
        
        # Action type sequence identical
        actions_a = [f.action_type for f in result_a.frames]
        actions_b = [f.action_type for f in result_b.frames]
        assert actions_a == actions_b
        
        # Event type sequence identical
        events_a = [f.event_type for f in result_a.frames]
        events_b = [f.event_type for f in result_b.frames]
        assert events_a == events_b
        
        # Semantic event payloads identical
        for frame_a, frame_b in zip(result_a.frames, result_b.frames):
            assert frame_a.event_payload == frame_b.event_payload
        
        # Final state hash identical
        assert result_a.final_state_hash == result_b.final_state_hash
        
        # Stop reason identical
        assert result_a.stop_reason == result_b.stop_reason
    
    def test_autoplay_persistence_reopen_integrity(self, phase35_initial_state):
        """Autoplay with EventStore persists and reopens correctly per spec #30."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            campaign_id = "test-campaign"
            
            # Run autoplay with persistence (initializes campaign internally)
            store = EventStore(db_path)
            config = AutoplayConfig()
            result = run_autoplay(
                phase35_initial_state,
                choose_action,
                config,
                event_store=store,
                campaign_id=campaign_id,
            )
            
            store.close()
            
            # Reopen and verify
            store2 = EventStore(db_path)
            verification = verify_persistence_integrity(campaign_id, db_path)
            store2.close()
            
            assert verification.success
    
    def test_persisted_final_hash_matches_run_result(self, phase35_initial_state):
        """Persisted final hash matches RunResult final hash per spec #30."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            campaign_id = "test-campaign"
            
            # Run autoplay with persistence
            store = EventStore(db_path)
            config = AutoplayConfig()
            result = run_autoplay(
                phase35_initial_state,
                choose_action,
                config,
                event_store=store,
                campaign_id=campaign_id,
            )
            
            store.close()
            
            # Reopen and verify persistence integrity
            store2 = EventStore(db_path)
            verification = verify_persistence_integrity(campaign_id, db_path)
            store2.close()
            
            # The actual_hash from persistence should match RunResult final hash
            assert verification.actual_hash == result.final_state_hash
    
    def test_jsonl_export_has_one_record_per_frame(self, phase35_initial_state):
        """JSONL export has one record per frame plus summary per spec #31."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "run.jsonl"
            write_run_jsonl(result, jsonl_path)
            
            # Read back
            lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
            
            # 3 frames + 1 summary
            assert len(lines) == 4
            
            # Parse frames
            for i in range(3):
                frame_data = json.loads(lines[i])
                assert frame_data["step"] == i + 1
                assert "action_type" in frame_data
                assert "event_type" in frame_data
    
    def test_jsonl_export_contains_hashes(self, phase35_initial_state):
        """JSONL export contains state hashes per spec #31."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "run.jsonl"
            write_run_jsonl(result, jsonl_path)
            
            lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
            
            # Check frames have hashes
            for i in range(3):
                frame_data = json.loads(lines[i])
                assert "state_hash_before" in frame_data
                assert "state_hash_after" in frame_data
            
            # Check summary has final hash
            summary = json.loads(lines[-1])
            assert "final_state_hash" in summary
    
    def test_jsonl_does_not_leak_target_loot_before_search(self, phase35_initial_state):
        """JSONL must not leak target_loot before SEARCH per spec #31."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "run.jsonl"
            write_run_jsonl(result, jsonl_path)
            
            lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
            
            # Frame 0 (DROP) - before SEARCH
            drop_frame = json.loads(lines[0])
            assert "target_loot" not in drop_frame.get("event_payload", {})
            
            # Frame 1 (SEARCH) - loot_gained appears after event
            search_frame = json.loads(lines[1])
            assert "loot_gained" in search_frame["event_payload"]
