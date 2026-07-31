"""Phase 3.5 diagnostic tests for rejected actions and config validation."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from tgn.autoplay import (
    run_autoplay,
    AutoplayConfig,
    StopReason,
    choose_action,
    RejectedActionRecord,
    render_run,
    write_run_jsonl,
)
from tgn.actions.models import ActionIntent
from tgn.storage.event_store import EventStore


class TestAutoplayConfigValidation:
    """Test AutoplayConfig rejects invalid inputs per spec section #14."""
    
    def test_autoplay_config_rejects_true(self):
        """AutoplayConfig must reject bool True."""
        with pytest.raises(ValueError, match="must be int, not bool"):
            AutoplayConfig(max_decisions=True)
    
    def test_autoplay_config_rejects_false(self):
        """AutoplayConfig must reject bool False."""
        with pytest.raises(ValueError, match="must be int, not bool"):
            AutoplayConfig(max_decisions=False)
    
    def test_autoplay_config_rejects_zero(self):
        """AutoplayConfig must reject zero."""
        with pytest.raises(ValueError, match="must be > 0"):
            AutoplayConfig(max_decisions=0)
    
    def test_autoplay_config_rejects_negative(self):
        """AutoplayConfig must reject negative integers."""
        with pytest.raises(ValueError, match="must be > 0"):
            AutoplayConfig(max_decisions=-1)
    
    def test_autoplay_config_rejects_float(self):
        """AutoplayConfig must reject floats."""
        with pytest.raises(ValueError, match="must be int"):
            AutoplayConfig(max_decisions=1.5)
    
    def test_autoplay_config_rejects_string(self):
        """AutoplayConfig must reject strings."""
        with pytest.raises(ValueError, match="must be int"):
            AutoplayConfig(max_decisions="5")
    
    def test_autoplay_config_accepts_positive_int(self):
        """AutoplayConfig accepts positive integers."""
        config = AutoplayConfig(max_decisions=5)
        assert config.max_decisions == 5


class TestRejectionDiagnostics:
    """Test rejected action diagnostics per spec section #15."""
    
    def test_rejected_run_contains_rejection_record(self, phase35_initial_state):
        """Rejected run must contain RejectedActionRecord."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id=f"bad-{decision_number:04d}",
                actor_id=actor_id,
                action_type="SEARCH",  # Not legal at base
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        assert result.stop_reason == StopReason.ACTION_REJECTED
        assert result.rejection is not None
        assert isinstance(result.rejection, RejectedActionRecord)
    
    def test_rejection_contains_action_id(self, phase35_initial_state):
        """Rejection record must contain action_id."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        assert result.rejection.action_id == "bad-0001"
    
    def test_rejection_contains_actor_id(self, phase35_initial_state):
        """Rejection record must contain actor_id."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id="test-actor",
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig(actor_id="test-actor")
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        assert result.rejection.actor_id == "test-actor"
    
    def test_rejection_contains_action_type(self, phase35_initial_state):
        """Rejection record must contain action_type."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        assert result.rejection.action_type == "SEARCH"
    
    def test_rejection_contains_params(self, phase35_initial_state):
        """Rejection record must contain params (deep-copied)."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={"test_key": "test_value"},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        assert result.rejection.params == {"test_key": "test_value"}
    
    def test_rejection_contains_validation_error_code(self, phase35_initial_state):
        """Rejection record must contain validation errors."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        assert len(result.rejection.validation_errors) > 0
        error_codes = [err.code for err in result.rejection.validation_errors]
        assert "ACTION_NOT_LEGAL_IN_STATE" in error_codes
    
    def test_rejection_state_hash_matches_pre_action_state(self, phase35_initial_state):
        """Rejection state_hash_before must match initial state hash."""
        from tgn.core.hashing import state_hash
        
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        expected_hash = state_hash(phase35_initial_state.__dict__)
        assert result.rejection.state_hash_before == expected_hash
        assert result.rejection.state_hash_before == result.initial_state_hash
    
    def test_rejection_does_not_contain_game_state(self, phase35_initial_state):
        """Rejection record must NOT contain full GameState."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        # Rejection record should not have GameState attributes
        assert not hasattr(result.rejection, "game_state")
        assert not hasattr(result.rejection, "state")
        assert not hasattr(result.rejection, "data")
    
    def test_rejection_does_not_leak_target_loot(self, phase35_initial_state):
        """Rejection record must NOT leak target_loot."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        # Convert rejection to string and check for target_loot
        rejection_str = str(result.rejection)
        assert "target_loot" not in rejection_str
        assert "salvage" not in rejection_str


class TestRejectedActionPersistence:
    """Test rejected actions don't pollute database per spec section #16."""
    
    def test_rejected_action_creates_no_event_row(self, phase35_initial_state):
        """Rejected action must not create event row in SQLite."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            campaign_id = "test-campaign"
            
            store = EventStore(db_path)
            config = AutoplayConfig()
            result = run_autoplay(
                phase35_initial_state,
                bad_policy,
                config,
                event_store=store,
                campaign_id=campaign_id,
            )
            
            store.close()
            
            # Verify no event rows added
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM events WHERE campaign_id = ?", (campaign_id,))
            event_count = cursor.fetchone()[0]
            conn.close()
            
            assert result.stop_reason == StopReason.ACTION_REJECTED
            assert event_count == 0
    
    def test_rejected_action_creates_no_transition_snapshot(self, phase35_initial_state):
        """Rejected action must not create transition snapshot."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            campaign_id = "test-campaign"
            
            store = EventStore(db_path)
            config = AutoplayConfig()
            result = run_autoplay(
                phase35_initial_state,
                bad_policy,
                config,
                event_store=store,
                campaign_id=campaign_id,
            )
            
            store.close()
            
            # Verify only initial snapshot exists
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM snapshots WHERE campaign_id = ?", (campaign_id,))
            snapshot_count = cursor.fetchone()[0]
            conn.close()
            
            assert result.stop_reason == StopReason.ACTION_REJECTED
            # No transition snapshots created (initialize doesn't create snapshots)
            assert snapshot_count == 0


class TestRendererRejectionOutput:
    """Test renderer shows rejection info per spec section #17."""
    
    def test_renderer_marks_policy_complete_as_complete(self, phase35_initial_state):
        """Successful run shows RUN COMPLETE."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        output = render_run(result)
        assert "=== RUN COMPLETE ===" in output
    
    def test_renderer_marks_rejected_run_as_stopped(self, phase35_initial_state):
        """Rejected run shows RUN STOPPED."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        output = render_run(result)
        assert "=== RUN STOPPED ===" in output
        assert "=== RUN COMPLETE ===" not in output
    
    def test_renderer_marks_max_decisions_as_stopped(self, phase35_initial_state):
        """Max decisions run shows RUN STOPPED."""
        config = AutoplayConfig(max_decisions=1)
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        output = render_run(result)
        assert "=== RUN STOPPED ===" in output
        assert "=== RUN COMPLETE ===" not in output
    
    def test_renderer_shows_rejected_action_type(self, phase35_initial_state):
        """Renderer shows rejected action type."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        output = render_run(result)
        assert "rejected action:" in output
        assert "SEARCH" in output
    
    def test_renderer_shows_validation_error_code(self, phase35_initial_state):
        """Renderer shows validation error codes."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        output = render_run(result)
        assert "validation:" in output
        assert "ACTION_NOT_LEGAL_IN_STATE" in output


class TestJSONLRejectionExport:
    """Test JSONL export includes rejection info per spec section #18."""
    
    def test_jsonl_successful_run_still_exports_frames(self, phase35_initial_state):
        """Successful run JSONL exports all frames."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "run.jsonl"
            write_run_jsonl(result, jsonl_path)
            
            lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
            
            # 3 frames + 1 summary
            assert len(lines) == 4
    
    def test_jsonl_rejected_run_has_zero_frames(self, phase35_initial_state):
        """Rejected run JSONL has zero frames."""
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "run.jsonl"
            write_run_jsonl(result, jsonl_path)
            
            lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
            
            # Only summary line, no frames
            assert len(lines) == 1
    
    def test_jsonl_rejected_run_contains_rejection_summary(self, phase35_initial_state):
        """Rejected run JSONL summary contains rejection info."""
        import json
        
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "run.jsonl"
            write_run_jsonl(result, jsonl_path)
            
            lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
            summary = json.loads(lines[0])
            
            assert summary["stop_reason"] == "ACTION_REJECTED"
            assert "rejection" in summary
            assert summary["rejection"]["action_id"] == "bad-0001"
            assert summary["rejection"]["action_type"] == "SEARCH"
    
    def test_jsonl_rejection_summary_contains_error_codes(self, phase35_initial_state):
        """JSONL rejection summary contains validation error codes."""
        import json
        
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "run.jsonl"
            write_run_jsonl(result, jsonl_path)
            
            lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
            summary = json.loads(lines[0])
            
            assert "validation_error_codes" in summary["rejection"]
            assert "ACTION_NOT_LEGAL_IN_STATE" in summary["rejection"]["validation_error_codes"]
    
    def test_jsonl_rejection_summary_contains_state_hash(self, phase35_initial_state):
        """JSONL rejection summary contains state_hash_before."""
        import json
        
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "run.jsonl"
            write_run_jsonl(result, jsonl_path)
            
            lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
            summary = json.loads(lines[0])
            
            assert "state_hash_before" in summary["rejection"]
            assert summary["rejection"]["state_hash_before"] == result.initial_state_hash
    
    def test_jsonl_rejection_summary_does_not_leak_target_loot(self, phase35_initial_state):
        """JSONL rejection summary must not leak target_loot."""
        import json
        
        def bad_policy(obs, decision_number, actor_id):
            return ActionIntent(
                action_id="bad-0001",
                actor_id=actor_id,
                action_type="SEARCH",
                params={},
            )
        
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, bad_policy, config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "run.jsonl"
            write_run_jsonl(result, jsonl_path)
            
            content = jsonl_path.read_text(encoding="utf-8")
            
            # Should not contain target_loot or salvage
            assert "target_loot" not in content
            assert "salvage" not in content
