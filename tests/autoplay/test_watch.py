"""WatchFrame and renderer tests per spec sections #39 and #40."""

import pytest
from tgn.autoplay import run_autoplay, AutoplayConfig, choose_action, render_frame, render_run
from tgn.gameplay.expedition import build_observation


class TestWatchFrame:
    """WatchFrame contract tests."""
    
    def test_one_frame_per_accepted_decision(self, phase35_initial_state):
        """Each accepted decision produces exactly one frame."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        assert len(result.frames) == result.decisions
        assert len(result.frames) == 3
    
    def test_frame_contains_before_and_after_observation(self, phase35_initial_state):
        """Each frame has observation_before and observation_after."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        for frame in result.frames:
            assert frame.observation_before is not None
            assert frame.observation_after is not None
            assert isinstance(frame.observation_before, dict)
            assert isinstance(frame.observation_after, dict)
    
    def test_frame_contains_semantic_event_payload(self, phase35_initial_state):
        """Each frame has event_payload with action-specific data."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        # DROP frame
        drop_frame = result.frames[0]
        assert "destination" in drop_frame.event_payload
        assert "time" in drop_frame.event_payload
        assert "stamina_cost" in drop_frame.event_payload
        
        # SEARCH frame
        search_frame = result.frames[1]
        assert "loot_gained" in search_frame.event_payload
        assert "time" in search_frame.event_payload
        assert "stamina_cost" in search_frame.event_payload
        
        # EXTRACT frame
        extract_frame = result.frames[2]
        assert "carried_loot" in extract_frame.event_payload
        assert "time" in extract_frame.event_payload
    
    def test_frame_hash_chain_is_continuous(self, phase35_initial_state):
        """Frame hash chain is continuous: after[i] == before[i+1]."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        for i in range(len(result.frames) - 1):
            current_after = result.frames[i].state_hash_after
            next_before = result.frames[i + 1].state_hash_before
            assert current_after == next_before, f"Hash chain broken at frame {i}"
        
        # Last frame hash equals final state hash
        assert result.frames[-1].state_hash_after == result.final_state_hash
    
    def test_mutating_frame_data_does_not_mutate_game_state(self, phase35_initial_state):
        """Mutating frame dicts does not affect GameState."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        # Mutate frame data
        frame = result.frames[0]
        frame.observation_before["inventory"]["hack"] = 999
        frame.observation_after["inventory"]["hack"] = 999
        frame.event_payload["hack"] = 999
        
        # GameState should be unaffected
        final_state = result.final_state
        assert "hack" not in final_state.data["inventory"]
    
    def test_pre_search_frame_does_not_leak_target_loot(self, phase35_initial_state):
        """Before SEARCH, target_loot must not appear in observation_before."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        # Frame 0 (DROP) - before SEARCH
        drop_frame = result.frames[0]
        assert "target_loot" not in drop_frame.observation_before
        assert "target_loot" not in drop_frame.observation_after
        
        # Frame 1 (SEARCH) - before event
        search_frame = result.frames[1]
        assert "target_loot" not in search_frame.observation_before
        
        # After SEARCH, loot_gained appears in event_payload
        assert "loot_gained" in search_frame.event_payload


class TestRenderer:
    """Watch renderer tests."""
    
    def test_renderer_contains_action_and_event(self, phase35_initial_state):
        """Rendered output contains action and event types."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        output = render_run(result)
        
        assert "DROP" in output
        assert "SEARCH" in output
        assert "EXTRACT" in output
        assert "EXPEDITION_DROPPED" in output
        assert "SEARCH_RESOLVED" in output
        assert "EXPEDITION_EXTRACTED" in output
    
    def test_renderer_contains_known_action_costs(self, phase35_initial_state):
        """Rendered output shows action costs."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        output = render_run(result)
        
        # DROP cost
        assert "10 分钟" in output
        assert "1 体力" in output
        
        # SEARCH cost
        assert "30 分钟" in output
        assert "2 体力" in output
        
        # EXTRACT cost
        assert "15 分钟" in output
        assert "0 体力" in output
    
    def test_renderer_shows_carried_loot_after_search(self, phase35_initial_state):
        """After SEARCH, renderer shows carried loot."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        output = render_run(result)
        
        # After SEARCH, carried loot should appear
        assert "获得并携带" in output
        assert "salvage" in output
        assert "×2" in output
    
    def test_renderer_shows_banked_inventory_after_extract(self, phase35_initial_state):
        """After EXTRACT, renderer shows banked inventory."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        output = render_run(result)
        
        # After EXTRACT, inventory should appear
        assert "入库" in output
        assert "salvage" in output
        assert "×2" in output
    
    def test_renderer_does_not_reveal_loot_before_search(self, phase35_initial_state):
        """Before SEARCH, renderer must not reveal target_loot."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        output = render_run(result)
        
        # Find the DROP frame section (before SEARCH)
        drop_section_end = output.find("SEARCH_RESOLVED")
        drop_section = output[:drop_section_end]
        
        # Should not mention salvage in DROP section
        # (salvage only appears after SEARCH)
        assert "salvage" not in drop_section
    
    def test_renderer_outputs_run_summary(self, phase35_initial_state):
        """Renderer outputs run summary at end."""
        config = AutoplayConfig()
        result = run_autoplay(phase35_initial_state, choose_action, config)
        
        output = render_run(result)
        
        assert "=== RUN COMPLETE ===" in output
        assert "decisions: 3" in output
        assert "events: 3" in output
        assert "stop_reason: POLICY_COMPLETE" in output
        assert "final inventory:" in output
        assert "final_hash:" in output
