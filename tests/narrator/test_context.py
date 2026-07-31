"""Tests for narration context builder."""

import copy
import pytest
from tgn.narrator.context import build_narration_context
from tgn.autoplay.models import WatchFrame


class TestNarrationContext:
    """Tests for build_narration_context."""
    
    def test_context_built_from_watch_frame(self, drop_watch_frame):
        """Context is built from watch frame only."""
        context = build_narration_context(drop_watch_frame)
        
        assert context.step == drop_watch_frame.step
        assert context.action_type == drop_watch_frame.action_type
        assert context.event_type == drop_watch_frame.event_type
    
    def test_context_contains_location_transition(self, drop_watch_frame):
        """Context contains before/after location."""
        context = build_narration_context(drop_watch_frame)
        
        assert context.location_before == "base-1"
        assert context.location_after == "site-1"
    
    def test_context_contains_stamina_transition(self, drop_watch_frame):
        """Context contains before/after stamina."""
        context = build_narration_context(drop_watch_frame)
        
        assert context.stamina_before == 3
        assert context.stamina_after == 2
        assert context.max_stamina == 3
    
    def test_context_contains_inventory(self, extract_watch_frame):
        """Context contains inventory before/after."""
        context = build_narration_context(extract_watch_frame)
        
        assert context.inventory_before == {}
        assert context.inventory_after == {"salvage": 2}
    
    def test_context_contains_carried_loot(self, search_watch_frame):
        """Context contains carried loot before/after."""
        context = build_narration_context(search_watch_frame)
        
        assert context.carried_before == {}
        assert context.carried_after == {"salvage": 2}
    
    def test_context_contains_event_payload(self, search_watch_frame):
        """Context contains event payload."""
        context = build_narration_context(search_watch_frame)
        
        assert "loot_gained" in context.event_payload
        assert context.event_payload["loot_gained"] == {"salvage": 2}
    
    def test_context_does_not_contain_target_loot(self, drop_watch_frame):
        """Context does NOT contain target_loot (hidden information)."""
        context = build_narration_context(drop_watch_frame)
        
        # target_loot should not be in context
        assert not hasattr(context, "target_loot")
        assert "target_loot" not in context.event_payload
    
    def test_context_is_deep_copy(self, drop_watch_frame):
        """Context is a deep copy, modifications don't affect original."""
        context = build_narration_context(drop_watch_frame)
        
        # Modify context
        context.inventory_after["hacked"] = 999
        
        # Original frame should be unchanged
        assert "hacked" not in drop_watch_frame.observation_after["inventory"]


@pytest.fixture
def drop_watch_frame():
    """Sample DROP watch frame."""
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
def extract_watch_frame():
    """Sample EXTRACT watch frame."""
    return WatchFrame(
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
