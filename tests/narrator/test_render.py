"""Tests for novel watch renderer."""

import pytest
from tgn.narrator.render import render_narrated_run
from tgn.narrator.models import NarratedFrame, NarrationRunResult
from tgn.autoplay.models import AutoplayRunResult, StopReason, WatchFrame


class TestNovelRenderer:
    """Tests for render_narrated_run."""
    
    def test_renderer_contains_all_narrations(self, narrated_run_result):
        """Renderer output contains all narrations."""
        output = render_narrated_run(narrated_run_result)
        
        assert "Narration 1" in output
        assert "Narration 2" in output
        assert "Narration 3" in output
    
    def test_renderer_contains_action_panels(self, narrated_run_result):
        """Renderer contains action system panels."""
        output = render_narrated_run(narrated_run_result)
        
        assert "[行动]" in output
        assert "DROP" in output
        assert "SEARCH" in output
        assert "EXTRACT" in output
    
    def test_renderer_contains_search_loot_panel(self, narrated_run_result):
        """Renderer contains SEARCH loot panel."""
        output = render_narrated_run(narrated_run_result)
        
        assert "[获得并携带]" in output
        assert "salvage ×2" in output
    
    def test_renderer_contains_extract_inventory_panel(self, narrated_run_result):
        """Renderer contains EXTRACT inventory panel."""
        output = render_narrated_run(narrated_run_result)
        
        assert "[入库]" in output
    
    def test_renderer_contains_run_summary(self, narrated_run_result):
        """Renderer contains run summary."""
        output = render_narrated_run(narrated_run_result)
        
        assert "=== RUN COMPLETE ===" in output
        assert "decisions: 3" in output
        assert "events: 3" in output
    
    def test_renderer_marks_max_decisions_as_stopped(self):
        """Renderer marks MAX_DECISIONS as stopped."""
        # Create run with MAX_DECISIONS
        run_result = AutoplayRunResult(
            completed=False,
            stop_reason=StopReason.MAX_DECISIONS,
            initial_state_hash="hash1",
            final_state_hash="hash2",
            decisions=1,
            events=1,
            frames=(create_drop_frame(),),
            final_state=None,  # Not needed for narrator tests
        )
        
        narrated_frames = (
            NarratedFrame(
                step=1,
                action_type="DROP",
                event_type="EXPEDITION_DROPPED",
                narration="Narration",
                state_hash_before="hash1",
                state_hash_after="hash2",
            ),
        )
        
        narrated_run = NarrationRunResult(
            narrated_frames=narrated_frames,
            source_initial_hash="hash1",
            source_final_hash="hash2",
            narration_failures=0,
            source_run=run_result,
        )
        
        output = render_narrated_run(narrated_run)
        
        assert "=== RUN STOPPED ===" in output
        assert "MAX_DECISIONS" in output


def create_drop_frame():
    """Helper to create DROP watch frame."""
    return WatchFrame(
        step=1,
        action_id="action-001",
        actor_id="bot-001",
        action_type="DROP",
        event_type="EXPEDITION_DROPPED",
        game_minute_before=0,
        game_minute_after=10,
        observation_before={
            "location_id": "base-1",
            "stamina": 3,
            "max_stamina": 3,
            "inventory": {},
            "carried_loot": {},
        },
        observation_after={
            "location_id": "site-1",
            "stamina": 2,
            "max_stamina": 3,
            "inventory": {},
            "carried_loot": {},
        },
        event_payload={
            "destination": "site-1",
            "time_minutes": 10,
            "stamina_cost": 1,
        },
        state_hash_before="hash-before-drop",
        state_hash_after="hash-after-drop",
    )


@pytest.fixture
def narrated_run_result():
    """Complete narrated run result."""
    drop_frame = create_drop_frame()
    
    search_frame = WatchFrame(
        step=2,
        action_id="action-002",
        actor_id="bot-001",
        action_type="SEARCH",
        event_type="SEARCH_RESOLVED",
        game_minute_before=10,
        game_minute_after=40,
        observation_before={
            "location_id": "site-1",
            "stamina": 2,
            "max_stamina": 3,
            "inventory": {},
            "carried_loot": {},
        },
        observation_after={
            "location_id": "site-1",
            "stamina": 0,
            "max_stamina": 3,
            "inventory": {},
            "carried_loot": {"salvage": 2},
        },
        event_payload={
            "loot_gained": {"salvage": 2},
            "time_minutes": 30,
            "stamina_cost": 2,
        },
        state_hash_before="hash-before-search",
        state_hash_after="hash-after-search",
    )
    
    extract_frame = WatchFrame(
        step=3,
        action_id="action-003",
        actor_id="bot-001",
        action_type="EXTRACT",
        event_type="EXPEDITION_EXTRACTED",
        game_minute_before=40,
        game_minute_after=55,
        observation_before={
            "location_id": "site-1",
            "stamina": 0,
            "max_stamina": 3,
            "inventory": {},
            "carried_loot": {"salvage": 2},
        },
        observation_after={
            "location_id": "base-1",
            "stamina": 0,
            "max_stamina": 3,
            "inventory": {"salvage": 2},
            "carried_loot": {},
        },
        event_payload={
            "destination": "base-1",
            "time_minutes": 15,
            "stamina_cost": 0,
        },
        state_hash_before="hash-before-extract",
        state_hash_after="hash-after-extract",
    )
    
    run_result = AutoplayRunResult(
        completed=True,
        stop_reason=StopReason.POLICY_COMPLETE,
        initial_state_hash="initial_hash",
        final_state_hash="final_hash",
        decisions=3,
        events=3,
        frames=(drop_frame, search_frame, extract_frame),
        final_state=None,  # Not needed for narrator tests
    )
    
    narrated_frames = (
        NarratedFrame(
            step=1,
            action_type="DROP",
            event_type="EXPEDITION_DROPPED",
            narration="Narration 1",
            state_hash_before="hash1",
            state_hash_after="hash2",
        ),
        NarratedFrame(
            step=2,
            action_type="SEARCH",
            event_type="SEARCH_RESOLVED",
            narration="Narration 2",
            state_hash_before="hash2",
            state_hash_after="hash3",
        ),
        NarratedFrame(
            step=3,
            action_type="EXTRACT",
            event_type="EXPEDITION_EXTRACTED",
            narration="Narration 3",
            state_hash_before="hash3",
            state_hash_after="hash4",
        ),
    )
    
    return NarrationRunResult(
        narrated_frames=narrated_frames,
        source_initial_hash="initial_hash",
        source_final_hash="final_hash",
        narration_failures=0,
        source_run=run_result,
    )


class TestTextExport:
    """Tests for write_narrated_run_text."""
    
    def test_write_narrated_run_text_creates_utf8_file(self, narrated_run_result, tmp_path):
        """write_narrated_run_text creates UTF-8 file."""
        from tgn.narrator.render import write_narrated_run_text
        
        output_path = tmp_path / "output.txt"
        write_narrated_run_text(narrated_run_result, output_path)
        
        assert output_path.exists()
        # Verify it's valid UTF-8
        content = output_path.read_text(encoding="utf-8")
        assert len(content) > 0
    
    def test_written_text_matches_render_narrated_run(self, narrated_run_result, tmp_path):
        """Written text matches render_narrated_run output."""
        from tgn.narrator.render import write_narrated_run_text, render_narrated_run
        
        output_path = tmp_path / "output.txt"
        write_narrated_run_text(narrated_run_result, output_path)
        
        written = output_path.read_text(encoding="utf-8")
        rendered = render_narrated_run(narrated_run_result)
        
        assert written == rendered
    
    def test_written_text_contains_all_narrated_frames(self, narrated_run_result, tmp_path):
        """Written text contains all narrated frames."""
        from tgn.narrator.render import write_narrated_run_text
        
        output_path = tmp_path / "output.txt"
        write_narrated_run_text(narrated_run_result, output_path)
        
        content = output_path.read_text(encoding="utf-8")
        
        assert "Narration 1" in content
        assert "Narration 2" in content
        assert "Narration 3" in content
    
    def test_written_text_contains_run_complete(self, narrated_run_result, tmp_path):
        """Written text contains RUN COMPLETE marker."""
        from tgn.narrator.render import write_narrated_run_text
        
        output_path = tmp_path / "output.txt"
        write_narrated_run_text(narrated_run_result, output_path)
        
        content = output_path.read_text(encoding="utf-8")
        
        assert "=== RUN COMPLETE ===" in content
