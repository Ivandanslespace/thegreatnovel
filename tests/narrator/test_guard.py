"""Tests for hallucination guard."""

import pytest
from tgn.narrator.guard import validate_narration, NarrationValidationError
from tgn.narrator.context import build_narration_context


class TestHallucinationGuard:
    """Tests for validate_narration."""
    
    def test_guard_accepts_valid_narration(self, search_context, valid_search_narration):
        """Guard accepts narration that matches context."""
        # Should not raise
        validate_narration(search_context, valid_search_narration)
    
    def test_guard_rejects_wrong_resource_quantity(self, search_context):
        """Guard rejects narration with wrong resource quantity."""
        # Context says salvage ×2, narration says salvage ×999
        bad_narration = "你搜索了废墟，找到了 salvage ×999。"
        
        with pytest.raises(NarrationValidationError, match="Resource quantity mismatch"):
            validate_narration(search_context, bad_narration)
    
    def test_guard_rejects_wrong_stamina_transition(self, drop_context):
        """Guard rejects narration with wrong stamina transition."""
        # Context says 3→2, narration says 3→5
        bad_narration = "你出发前往目标地点。体力：3 → 5。"
        
        with pytest.raises(NarrationValidationError, match="Stamina transition mismatch"):
            validate_narration(drop_context, bad_narration)
    
    def test_guard_rejects_unknown_reward_resource(self, search_context):
        """Guard rejects narration with unknown reward resource."""
        # Context has salvage, narration invents gold
        bad_narration = "你搜索了废墟。获得：gold ×10。"
        
        with pytest.raises(NarrationValidationError, match="Unknown reward resource"):
            validate_narration(search_context, bad_narration)
    
    def test_guard_accepts_narration_without_numeric_restating(self, drop_context):
        """Guard accepts narration that doesn't restate numbers."""
        # Narration doesn't mention specific numbers
        narration = "你从基地出发，沿着路径前往探索地点。旅途消耗了一些体力。"
        
        # Should not raise
        validate_narration(drop_context, narration)
    
    def test_guard_rejects_empty_narration(self, drop_context):
        """Guard rejects empty narration."""
        with pytest.raises(NarrationValidationError, match="empty"):
            validate_narration(drop_context, "")
        
        with pytest.raises(NarrationValidationError, match="empty"):
            validate_narration(drop_context, "   ")
    
    def test_guard_does_not_modify_context(self, search_context, valid_search_narration):
        """Guard does not modify context."""
        # Deep copy for comparison
        original_carried = dict(search_context.carried_after)
        
        validate_narration(search_context, valid_search_narration)
        
        # Context should be unchanged
        assert search_context.carried_after == original_carried


@pytest.fixture
def drop_context(drop_watch_frame):
    """DROP narration context."""
    return build_narration_context(drop_watch_frame)


@pytest.fixture
def search_context(search_watch_frame):
    """SEARCH narration context."""
    return build_narration_context(search_watch_frame)


@pytest.fixture
def valid_search_narration():
    """Valid SEARCH narration."""
    return "你在探索地点仔细搜索，找到了 salvage ×2，携带在身上准备返回。"


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
