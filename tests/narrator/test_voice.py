"""Tests for Writing Voice contract."""

import pytest
from tgn.narrator.voice import WritingVoiceProfile
from tgn.narrator.voices.jingxuan import JINGXUAN_WRITING_VOICE
from tgn.narrator.prompt import build_narrator_prompt
from tgn.narrator.context import build_narration_context


class TestWritingVoiceProfile:
    """Tests for WritingVoiceProfile dataclass."""
    
    def test_writing_voice_profile_is_frozen(self):
        """WritingVoiceProfile is immutable."""
        profile = WritingVoiceProfile(name="test", instructions="test instructions")
        
        with pytest.raises(Exception):  # FrozenInstanceError
            profile.name = "modified"
    
    def test_jingxuan_voice_exists(self):
        """JINGXUAN_WRITING_VOICE is defined."""
        assert JINGXUAN_WRITING_VOICE is not None
        assert JINGXUAN_WRITING_VOICE.name == "jingxuan"
    
    def test_default_voice_id_is_cablecar(self):
        """DEFAULT_VOICE_ID is cablecar_survival (Phase 3.7 change)."""
        from tgn.narrator.voice import DEFAULT_VOICE_ID
        assert DEFAULT_VOICE_ID == "cablecar_survival"


class TestJingxuanVoiceInstructions:
    """Tests for Jingxuan voice instruction content."""
    
    def test_voice_requires_comma_chain_long_sentence_rhythm(self):
        """Voice instructions require comma chains and long sentences."""
        instructions = JINGXUAN_WRITING_VOICE.instructions
        
        assert "逗号链" in instructions
        assert "长句" in instructions
        assert "七成" in instructions or "70%" in instructions
    
    def test_voice_limits_short_sentence_overuse(self):
        """Voice instructions limit short sentence overuse."""
        instructions = JINGXUAN_WRITING_VOICE.instructions
        
        assert "短句" in instructions
        assert "重锤" in instructions or "强调" in instructions
        assert "机关枪" in instructions
    
    def test_voice_requests_cross_domain_sensory_metaphor(self):
        """Voice instructions request cross-domain synesthesia."""
        instructions = JINGXUAN_WRITING_VOICE.instructions
        
        assert "比喻" in instructions or "隐喻" in instructions
        assert "感觉" in instructions
        # Cross-domain examples
        assert "食物" in instructions or "地理" in instructions or "天气" in instructions
    
    def test_voice_allows_gentle_self_irony(self):
        """Voice instructions allow gentle self-irony."""
        instructions = JINGXUAN_WRITING_VOICE.instructions
        
        assert "自嘲" in instructions or "自省" in instructions
    
    def test_voice_forbids_theme_copying(self):
        """Voice instructions forbid copying romance/love themes."""
        instructions = JINGXUAN_WRITING_VOICE.instructions
        
        # Should NOT contain romance themes
        assert "恋爱" not in instructions
        assert "爱情" not in instructions
        assert "浪漫" not in instructions
    
    def test_voice_says_facts_override_style(self):
        """Voice instructions explicitly state facts override style."""
        instructions = JINGXUAN_WRITING_VOICE.instructions
        
        assert "FACTS" in instructions or "事实" in instructions
        assert "优先" in instructions or "override" in instructions.lower()


class TestVoiceInPrompt:
    """Tests for voice profile integration in prompts."""
    
    def test_prompt_contains_jingxuan_voice_section(self, drop_context):
        """Prompt contains [WRITING VOICE — JINGXUAN] section."""
        prompt = build_narrator_prompt(drop_context, JINGXUAN_WRITING_VOICE)
        
        assert "[WRITING VOICE" in prompt
        assert "JINGXUAN" in prompt
    
    def test_voice_profile_does_not_receive_game_state(self, drop_context):
        """Voice profile is used with context only, not GameState."""
        # Voice profile is a simple dataclass with name and instructions
        # It has no access to GameState
        profile = JINGXUAN_WRITING_VOICE
        
        assert not hasattr(profile, "game_state")
        assert not hasattr(profile, "state")
    
    def test_same_context_and_voice_produce_same_prompt(self, drop_context):
        """Same context + voice profile produces deterministic prompt."""
        prompt1 = build_narrator_prompt(drop_context, JINGXUAN_WRITING_VOICE)
        prompt2 = build_narrator_prompt(drop_context, JINGXUAN_WRITING_VOICE)
        
        assert prompt1 == prompt2
    
    def test_different_voice_profiles_produce_different_prompts(self, drop_context):
        """Different voice profiles produce different prompts."""
        custom_voice = WritingVoiceProfile(
            name="custom",
            instructions="[CUSTOM VOICE]\nWrite differently.",
        )
        
        prompt1 = build_narrator_prompt(drop_context, JINGXUAN_WRITING_VOICE)
        prompt2 = build_narrator_prompt(drop_context, custom_voice)
        
        assert prompt1 != prompt2
        assert "JINGXUAN" in prompt1
        assert "CUSTOM" in prompt2


class TestStyleVsFactPriority:
    """Tests ensuring facts always override style requirements."""
    
    def test_jingxuan_voice_cannot_override_fact_contract(self, drop_context):
        """
        CRITICAL: Even though Jingxuan voice encourages rich imagery,
        the prompt still forbids inventing new facts.
        """
        prompt = build_narrator_prompt(drop_context, JINGXUAN_WRITING_VOICE)
        
        # Prompt must still contain non-negotiable rules
        assert "NON-NEGOTIABLE" in prompt or "禁止" in prompt
        
        # Prompt must forbid inventing new facts
        assert "不能" in prompt or "禁止" in prompt
        assert "新" in prompt  # "new" in Chinese
        
        # Voice instructions must acknowledge fact priority
        assert "FACTS" in prompt or "事实" in prompt
        assert "优先" in prompt or "override" in prompt.lower()
    
    def test_voice_instructions_appear_after_fact_rules(self, drop_context):
        """Voice instructions appear AFTER fact rules in prompt."""
        prompt = build_narrator_prompt(drop_context, JINGXUAN_WRITING_VOICE)
        
        # Find positions
        fact_rules_pos = prompt.find("NON-NEGOTIABLE")
        if fact_rules_pos == -1:
            fact_rules_pos = prompt.find("禁止")
        
        voice_pos = prompt.find("WRITING VOICE")
        
        # Voice should come after fact rules
        assert voice_pos > fact_rules_pos


@pytest.fixture
def drop_context(drop_watch_frame):
    """DROP narration context."""
    return build_narration_context(drop_watch_frame)


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
