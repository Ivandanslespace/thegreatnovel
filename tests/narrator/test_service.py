"""Tests for narrator service."""

import pytest
from tgn.narrator.service import NarratorService, narrate_run
from tgn.narrator.client import FakeNarratorClient
from tgn.narrator.models import NarrationError
from tgn.autoplay.models import AutoplayRunResult, StopReason


class TestNarratorService:
    """Tests for NarratorService."""
    
    def test_narrate_frame_with_fake_client(self, drop_watch_frame, fake_client):
        """Service narrates frame using fake client."""
        service = NarratorService(fake_client)
        
        narrated = service.narrate_frame(drop_watch_frame)
        
        assert narrated.step == 1
        assert narrated.action_type == "DROP"
        assert "基地" in narrated.narration
    
    def test_narrate_frame_rejects_empty_output(self, drop_watch_frame):
        """Service rejects empty narration output."""
        empty_client = FakeNarratorClient([""])
        service = NarratorService(empty_client)
        
        with pytest.raises(NarrationError, match="empty"):
            service.narrate_frame(drop_watch_frame)
    
    def test_narrate_frame_passes_previous_text(self, search_watch_frame, fake_client, drop_narration):
        """Service passes previous narration for continuity."""
        service = NarratorService(fake_client)
        
        narrated = service.narrate_frame(search_watch_frame, previous_text=drop_narration)
        
        # Should succeed with previous text
        assert narrated.narration is not None
    
    def test_narrate_run_processes_all_frames(self, complete_run_result, fake_client_3_responses):
        """narrate_run processes all frames in order."""
        service = NarratorService(fake_client_3_responses)
        
        result = narrate_run(complete_run_result, service)
        
        assert len(result.narrated_frames) == 3
        assert result.narrated_frames[0].action_type == "DROP"
        assert result.narrated_frames[1].action_type == "SEARCH"
        assert result.narrated_frames[2].action_type == "EXTRACT"
    
    def test_narrate_run_preserves_source_hashes(self, complete_run_result, fake_client_3_responses):
        """narrate_run preserves source initial and final hashes."""
        service = NarratorService(fake_client_3_responses)
        
        result = narrate_run(complete_run_result, service)
        
        assert result.source_initial_hash == complete_run_result.initial_state_hash
        assert result.source_final_hash == complete_run_result.final_state_hash
    
    def test_narrate_run_handles_rejected_run(self, rejected_run_result, fake_client):
        """narrate_run handles rejected run (0 frames)."""
        service = NarratorService(fake_client)
        
        result = narrate_run(rejected_run_result, service)
        
        assert len(result.narrated_frames) == 0
        assert result.narration_failures == 0
    
    def test_narrate_run_counts_failures(self, complete_run_result):
        """narrate_run counts narration failures."""
        # Client that fails on second frame
        failing_client = FakeNarratorClient([
            "Narration 1",
            "",  # Empty = failure
            "Narration 3",
        ])
        service = NarratorService(failing_client)
        
        result = narrate_run(complete_run_result, service)
        
        assert result.narration_failures == 1
        assert len(result.narrated_frames) == 2  # 2 succeeded, 1 failed


class TestGameStateIsolation:
    """Tests ensuring narration doesn't modify game state."""
    
    def test_narration_does_not_change_game_state_hash(self, complete_run_result, fake_client_3_responses):
        """Narration process doesn't modify source game state hash."""
        service = NarratorService(fake_client_3_responses)
        
        # Hash before narration
        hash_before = complete_run_result.final_state_hash
        
        result = narrate_run(complete_run_result, service)
        
        # Hash after narration should be same
        hash_after = complete_run_result.final_state_hash
        assert hash_before == hash_after
        
        # And result should reference same hash
        assert result.source_final_hash == hash_before


@pytest.fixture
def fake_client():
    """Fake narrator client with one response."""
    return FakeNarratorClient(["你从基地出发，沿着路径前往探索地点。"])


@pytest.fixture
def fake_client_3_responses():
    """Fake narrator client with three responses."""
    return FakeNarratorClient([
        "你从基地出发，沿着路径前往探索地点。",
        "你在探索地点仔细搜索，找到了 salvage ×2。",
        "你带着收获返回基地，将物资入库。",
    ])


@pytest.fixture
def drop_narration():
    """Sample DROP narration."""
    return "你从基地出发，沿着路径前往探索地点。"


@pytest.fixture
def drop_watch_frame():
    """Sample DROP watch frame."""
    from tgn.autoplay.models import WatchFrame
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
def search_watch_frame():
    """Sample SEARCH watch frame."""
    from tgn.autoplay.models import WatchFrame
    return WatchFrame(
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


@pytest.fixture
def complete_run_result(drop_watch_frame, search_watch_frame):
    """Complete autoplay run result with 3 frames."""
    from tgn.autoplay.models import WatchFrame
    
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
    
    return AutoplayRunResult(
        completed=True,
        stop_reason=StopReason.POLICY_COMPLETE,
        initial_state_hash="initial_hash_abc123",
        final_state_hash="final_hash_xyz789",
        decisions=3,
        events=3,
        frames=(drop_watch_frame, search_watch_frame, extract_frame),
        final_state=None,  # Not needed for narrator tests
    )


@pytest.fixture
def rejected_run_result():
    """Rejected autoplay run result (0 frames)."""
    return AutoplayRunResult(
        completed=False,
        stop_reason=StopReason.ACTION_REJECTED,
        initial_state_hash="initial_hash",
        final_state_hash="initial_hash",
        decisions=0,
        events=0,
        frames=(),
        final_state=None,  # Not needed for narrator tests
    )
