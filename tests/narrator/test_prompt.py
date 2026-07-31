"""Tests for narrator prompt builder."""

import pytest
from tgn.narrator.prompt import build_narrator_prompt
from tgn.narrator.context import build_narration_context


class TestNarratorPrompt:
    """Tests for build_narrator_prompt."""
    
    def test_prompt_contains_non_negotiable_rules(self, drop_context):
        """Prompt contains non-negotiable fact rules."""
        prompt = build_narrator_prompt(drop_context)
        
        assert "NON-NEGOTIABLE RULES" in prompt
        assert "禁止创造新的" in prompt
        assert "禁止改变给定数值" in prompt
        assert "禁止暗示尚未发生的未来事实" in prompt
    
    def test_prompt_contains_facts(self, drop_context):
        """Prompt contains verified facts."""
        prompt = build_narrator_prompt(drop_context)
        
        assert "FACTS" in prompt
        assert "DROP" in prompt
        assert "EXPEDITION_DROPPED" in prompt
        assert "base-1 → site-1" in prompt
        assert "3 → 2" in prompt
    
    def test_prompt_forbids_inventing_rewards(self, drop_context):
        """Prompt explicitly forbids inventing rewards."""
        prompt = build_narrator_prompt(drop_context)
        
        assert "奖励" in prompt
        assert "禁止" in prompt
    
    def test_prompt_forbids_future_information(self, drop_context):
        """Prompt explicitly forbids future information."""
        prompt = build_narrator_prompt(drop_context)
        
        assert "未来事实" in prompt
    
    def test_drop_prompt_does_not_contain_salvage(self, drop_context):
        """DROP prompt does NOT contain salvage (future loot)."""
        prompt = build_narrator_prompt(drop_context)
        
        # salvage should not appear in DROP prompt
        assert "salvage" not in prompt
    
    def test_search_prompt_contains_salvage(self, search_context):
        """SEARCH prompt contains salvage (discovered loot)."""
        prompt = build_narrator_prompt(search_context)
        
        # salvage should appear in SEARCH prompt
        assert "salvage" in prompt
        assert "loot_gained" in prompt
    
    def test_prompt_does_not_dump_game_state(self, drop_context):
        """Prompt does not dump raw game state."""
        prompt = build_narrator_prompt(drop_context)
        
        # Should not contain raw game state fields
        assert "target_loot" not in prompt
        assert "event_seq" not in prompt
        assert "decision_seq" not in prompt
    
    def test_prompt_is_deterministic(self, drop_context):
        """Same context produces same prompt."""
        prompt1 = build_narrator_prompt(drop_context)
        prompt2 = build_narrator_prompt(drop_context)
        
        assert prompt1 == prompt2
    
    def test_prompt_with_previous_narration(self, search_context, drop_narration):
        """Prompt includes previous narration when provided."""
        prompt = build_narrator_prompt(search_context, previous_text=drop_narration)
        
        assert "PREVIOUS NARRATION" in prompt
        assert drop_narration in prompt


@pytest.fixture
def drop_context(drop_watch_frame):
    """DROP narration context."""
    return build_narration_context(drop_watch_frame)


@pytest.fixture
def search_context(search_watch_frame):
    """SEARCH narration context."""
    return build_narration_context(search_watch_frame)


@pytest.fixture
def drop_narration():
    """Sample DROP narration."""
    return "你从基地出发，沿着标记的路径向目标地点移动。十分钟后，你抵达了探索地点。"


# Reuse fixtures from test_context.py
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
