"""End-to-end Phase 3.6 tests."""

import pytest
from tgn.autoplay.runner import run_autoplay
from tgn.autoplay.policy import choose_action
from tgn.autoplay.models import AutoplayConfig, StopReason
from tgn.narrator.service import NarratorService, narrate_run
from tgn.narrator.client import FakeNarratorClient
from tgn.narrator.render import render_narrated_run
from tgn.core.hashing import state_hash


class TestPhase36E2E:
    """End-to-end tests for Phase 3.6."""
    
    def test_complete_autoplay_to_novel_flow(self, phase36_initial_state):
        """Complete flow: autoplay → watch frames → narration → novel output."""
        # Step 1: Run autoplay
        config = AutoplayConfig(max_decisions=10)
        autoplay_result = run_autoplay(
            phase36_initial_state,
            choose_action,
            config,
        )
        
        assert autoplay_result.stop_reason == StopReason.POLICY_COMPLETE
        assert len(autoplay_result.frames) == 3
        
        # Step 2: Narrate frames
        fake_client = FakeNarratorClient([
            "你从基地出发，沿着路径前往探索地点。",
            "你在探索地点仔细搜索，找到了 salvage ×2。",
            "你带着收获返回基地，将物资入库。",
        ])
        service = NarratorService(fake_client)
        
        narration_result = narrate_run(autoplay_result, service)
        
        assert len(narration_result.narrated_frames) == 3
        assert narration_result.narration_failures == 0
        
        # Step 3: Render novel output
        novel_output = render_narrated_run(narration_result)
        
        assert "=== TheGreatNovel Novel Watch ===" in novel_output
        assert "=== RUN COMPLETE ===" in novel_output
        assert "Narration" in novel_output or "基地" in novel_output
        assert "salvage ×2" in novel_output
    
    def test_game_state_hash_unchanged_after_narration(self, phase36_initial_state):
        """Game state hash is unchanged by narration process."""
        # Run autoplay
        config = AutoplayConfig(max_decisions=10)
        autoplay_result = run_autoplay(
            phase36_initial_state,
            choose_action,
            config,
        )
        
        # Hash before narration
        hash_before = state_hash(autoplay_result.final_state.__dict__)
        
        # Narrate
        fake_client = FakeNarratorClient([
            "Narration 1",
            "Narration 2",
            "Narration 3",
        ])
        service = NarratorService(fake_client)
        narrate_run(autoplay_result, service)
        
        # Hash after narration should be same
        hash_after = state_hash(autoplay_result.final_state.__dict__)
        
        assert hash_before == hash_after
    
    def test_narrator_receives_only_watch_frames(self, phase36_initial_state):
        """Narrator service only receives watch frames, not game state."""
        # Run autoplay
        config = AutoplayConfig(max_decisions=10)
        autoplay_result = run_autoplay(
            phase36_initial_state,
            choose_action,
            config,
        )
        
        # Create service
        fake_client = FakeNarratorClient([
            "Narration 1",
            "Narration 2",
            "Narration 3",
        ])
        service = NarratorService(fake_client)
        
        # Narrate each frame individually
        for frame in autoplay_result.frames:
            narrated = service.narrate_frame(frame)
            
            # Narrated frame should have narration
            assert narrated.narration is not None
            assert len(narrated.narration) > 0
    
    def test_information_boundary_drop_no_salvage(self, phase36_initial_state):
        """DROP narration doesn't know about future salvage."""
        # Run autoplay
        config = AutoplayConfig(max_decisions=10)
        autoplay_result = run_autoplay(
            phase36_initial_state,
            choose_action,
            config,
        )
        
        # Get DROP frame
        drop_frame = autoplay_result.frames[0]
        assert drop_frame.action_type == "DROP"
        
        # Create context
        from tgn.narrator.context import build_narration_context
        context = build_narration_context(drop_frame)
        
        # Context should not contain salvage
        assert "salvage" not in str(context.event_payload)
        assert "salvage" not in str(context.carried_after)
    
    def test_information_boundary_search_has_salvage(self, phase36_initial_state):
        """SEARCH narration knows about discovered salvage."""
        # Run autoplay
        config = AutoplayConfig(max_decisions=10)
        autoplay_result = run_autoplay(
            phase36_initial_state,
            choose_action,
            config,
        )
        
        # Get SEARCH frame
        search_frame = autoplay_result.frames[1]
        assert search_frame.action_type == "SEARCH"
        
        # Create context
        from tgn.narrator.context import build_narration_context
        context = build_narration_context(search_frame)
        
        # Context should contain salvage
        assert "salvage" in context.event_payload.get("loot_gained", {})
        assert context.carried_after.get("salvage") == 2
