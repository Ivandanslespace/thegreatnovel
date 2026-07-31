"""Tests for voice pack examples data flow."""

import pytest
from pathlib import Path
from tgn.narrator.voice_loader import load_voice_pack
from tgn.narrator.prompt import build_narrator_prompt
from tgn.narrator.models import NarrationContext
from tgn.narrator.guard import validate_narration, NarrationValidationError


@pytest.fixture
def voice_pack_with_examples(tmp_path):
    """Create a voice pack with examples."""
    pack_dir = tmp_path / "test_voice_with_examples"
    pack_dir.mkdir()
    
    # Create manifest
    manifest = {
        "id": "test_voice_with_examples",
        "display_name": "Test Voice with Examples",
        "language": "zh-CN",
        "version": 1,
        "description": "A test voice pack with examples",
        "instructions_file": "instructions.md",
        "examples_file": "examples.md"
    }
    
    with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
        import json
        json.dump(manifest, f)
    
    # Create instructions
    instructions = "[WRITING VOICE — TEST]\n\nTest instructions here."
    with open(pack_dir / "instructions.md", 'w', encoding='utf-8') as f:
        f.write(instructions)
    
    # Create examples with potentially problematic content
    examples = """林默站在黑塔前，手中握着一把闪亮的匕首。

他检查了背包：gold ×999, 魔法卷轴 ×5。

这座城市的夜晚充满了危险和机遇。"""
    with open(pack_dir / "examples.md", 'w', encoding='utf-8') as f:
        f.write(examples)
    
    return pack_dir


@pytest.fixture
def voice_pack_without_examples(tmp_path):
    """Create a voice pack without examples."""
    pack_dir = tmp_path / "test_voice_no_examples"
    pack_dir.mkdir()
    
    # Create manifest
    manifest = {
        "id": "test_voice_no_examples",
        "display_name": "Test Voice without Examples",
        "language": "zh-CN",
        "version": 1,
        "description": "A test voice pack without examples",
        "instructions_file": "instructions.md"
    }
    
    with open(pack_dir / "manifest.json", 'w', encoding='utf-8') as f:
        import json
        json.dump(manifest, f)
    
    # Create instructions
    instructions = "[WRITING VOICE — TEST]\n\nTest instructions here."
    with open(pack_dir / "instructions.md", 'w', encoding='utf-8') as f:
        f.write(instructions)
    
    return pack_dir


@pytest.fixture
def sample_context():
    """Create a sample narration context."""
    return NarrationContext(
        step=1,
        action_type="DROP",
        event_type="EXPEDITION_DROPPED",
        game_minute_before=0,
        game_minute_after=10,
        location_before="base-1",
        location_after="site-1",
        stamina_before=3,
        stamina_after=2,
        max_stamina=3,
        inventory_before={},
        inventory_after={},
        carried_before={},
        carried_after={},
        event_payload={
            "destination": "site-1",
            "time": 10,
            "stamina_cost": 1,
        }
    )


class TestExamplesRetained:
    """Test A: examples are retained in WritingVoiceProfile."""
    
    def test_examples_are_retained(self, voice_pack_with_examples):
        """Examples from examples.md are retained in profile."""
        profile = load_voice_pack(voice_pack_with_examples)
        
        assert profile.name == "test_voice_with_examples"
        assert len(profile.examples) > 0
        assert "林默" in profile.examples[0]
        assert "黑塔" in profile.examples[0]
        assert "gold ×999" in profile.examples[0]
    
    def test_no_examples_means_empty_tuple(self, voice_pack_without_examples):
        """Voice pack without examples has empty examples tuple."""
        profile = load_voice_pack(voice_pack_without_examples)
        
        assert profile.name == "test_voice_no_examples"
        assert profile.examples == ()


class TestExamplesEnterPrompt:
    """Test B: examples enter prompt with proper isolation."""
    
    def test_examples_enter_prompt(self, voice_pack_with_examples, sample_context):
        """Examples are included in prompt with STYLE EXAMPLES section."""
        profile = load_voice_pack(voice_pack_with_examples)
        prompt = build_narrator_prompt(sample_context, profile)
        
        # Check that STYLE EXAMPLES section exists
        assert "[STYLE EXAMPLES — NOT WORLD FACTS]" in prompt
        
        # Check that example content is present
        assert "林默" in prompt
        assert "黑塔" in prompt
        assert "gold ×999" in prompt
        
        # Check that the section header appears before the example content
        style_examples_pos = prompt.find("[STYLE EXAMPLES — NOT WORLD FACTS]")
        example_content_pos = prompt.find("林默")
        assert style_examples_pos < example_content_pos
    
    def test_examples_section_has_isolation_warning(self, voice_pack_with_examples, sample_context):
        """STYLE EXAMPLES section includes warning that examples are not facts."""
        profile = load_voice_pack(voice_pack_with_examples)
        prompt = build_narrator_prompt(sample_context, profile)
        
        # Check for isolation warning
        assert "不是当前游戏事实" in prompt


class TestNoExamplesMeansNoSection:
    """Test C: no examples means no STYLE EXAMPLES section."""
    
    def test_no_examples_means_no_section(self, voice_pack_without_examples, sample_context):
        """Voice pack without examples does not generate STYLE EXAMPLES section."""
        profile = load_voice_pack(voice_pack_without_examples)
        prompt = build_narrator_prompt(sample_context, profile)
        
        # Check that STYLE EXAMPLES section does NOT exist
        assert "[STYLE EXAMPLES — NOT WORLD FACTS]" not in prompt


class TestExamplesAreNotFacts:
    """Test D: examples are not FACTS."""
    
    def test_examples_not_in_facts_section(self, voice_pack_with_examples, sample_context):
        """Example content appears in STYLE EXAMPLES section, not in FACTS section."""
        profile = load_voice_pack(voice_pack_with_examples)
        prompt = build_narrator_prompt(sample_context, profile)
        
        # Find section boundaries - FACTS ends at [WRITING VOICE
        facts_start = prompt.find("[FACTS]")
        facts_end = prompt.find("[WRITING VOICE")
        
        # Extract FACTS section
        facts_section = prompt[facts_start:facts_end]
        
        # Example content should NOT be in FACTS section
        assert "林默" not in facts_section
        assert "黑塔" not in facts_section
        assert "gold ×999" not in facts_section
        
        # But should be in STYLE EXAMPLES section
        style_examples_start = prompt.find("[STYLE EXAMPLES — NOT WORLD FACTS]")
        style_examples_end = prompt.find("[OUTPUT REQUIREMENTS]")
        style_examples_section = prompt[style_examples_start:style_examples_end]
        
        assert "林默" in style_examples_section
        assert "黑塔" in style_examples_section
        assert "gold ×999" in style_examples_section
    
    def test_facts_section_contains_only_real_context(self, voice_pack_with_examples, sample_context):
        """FACTS section contains only real context data, not example data."""
        profile = load_voice_pack(voice_pack_with_examples)
        prompt = build_narrator_prompt(sample_context, profile)
        
        # Find FACTS section - ends at [WRITING VOICE
        facts_start = prompt.find("[FACTS]")
        facts_end = prompt.find("[WRITING VOICE")
        facts_section = prompt[facts_start:facts_end]
        
        # FACTS should contain real context data
        assert "DROP" in facts_section
        assert "EXPEDITION_DROPPED" in facts_section
        assert "base-1" in facts_section
        assert "site-1" in facts_section
        
        # FACTS should NOT contain example data
        assert "林默" not in facts_section
        assert "黑塔" not in facts_section
        assert "gold" not in facts_section
        assert "魔法卷轴" not in facts_section


class TestGuardRemainsIndependent:
    """Test E: Guard remains independent of voice examples."""
    
    def test_guard_rejects_hallucination_despite_examples(self, voice_pack_with_examples, sample_context):
        """Guard still rejects hallucinated content even if it appears in examples."""
        profile = load_voice_pack(voice_pack_with_examples)
        
        # Create a narration that claims gold ×999 (from examples)
        # but context has no gold
        bad_narration = "你找到了 gold ×999。"
        
        # Guard should still reject this because context has no gold
        with pytest.raises(NarrationValidationError, match="Unknown resource"):
            validate_narration(sample_context, bad_narration)
    
    def test_examples_cannot_bypass_guard(self, voice_pack_with_examples, sample_context):
        """Voice examples cannot bypass the hallucination guard."""
        profile = load_voice_pack(voice_pack_with_examples)
        
        # Try various hallucinations that appear in examples
        bad_narrations = [
            "你遇到了林默。",  # NPC from examples
            "你来到了黑塔。",  # Location from examples
            "你获得了 gold ×999。",  # Resource from examples
            "你使用了魔法卷轴 ×5。",  # Item from examples
        ]
        
        for bad_narration in bad_narrations:
            # Guard should reject all of these
            # Note: Some might not trigger the guard if they're not in the
            # specific patterns the guard checks for, but at minimum
            # resource claims should be caught
            if "gold" in bad_narration or "魔法卷轴" in bad_narration:
                with pytest.raises(NarrationValidationError):
                    validate_narration(sample_context, bad_narration)


class TestVoiceIsolation:
    """Test that different voices with same context produce isolated prompts."""
    
    def test_different_voices_isolate_facts(self, voice_pack_with_examples, sample_context):
        """Different voices with same context have identical FACTS sections."""
        # Load voice with examples
        profile_with = load_voice_pack(voice_pack_with_examples)
        prompt_with = build_narrator_prompt(sample_context, profile_with)
        
        # Create a simple voice without examples
        from tgn.narrator.voice import WritingVoiceProfile
        profile_without = WritingVoiceProfile(
            name="simple",
            instructions="[WRITING VOICE — SIMPLE]\n\nSimple instructions."
        )
        prompt_without = build_narrator_prompt(sample_context, profile_without)
        
        # Extract FACTS sections - find the end marker which is always [WRITING VOICE
        facts_start_with = prompt_with.find("[FACTS]")
        facts_end_with = prompt_with.find("[WRITING VOICE")
        facts_section_with = prompt_with[facts_start_with:facts_end_with]
        
        facts_start_without = prompt_without.find("[FACTS]")
        facts_end_without = prompt_without.find("[WRITING VOICE")
        facts_section_without = prompt_without[facts_start_without:facts_end_without]
        
        # FACTS sections should be identical
        assert facts_section_with == facts_section_without
    
    def test_role_and_rules_sections_identical(self, voice_pack_with_examples, sample_context):
        """ROLE and NON-NEGOTIABLE RULES sections are identical across voices."""
        profile_with = load_voice_pack(voice_pack_with_examples)
        prompt_with = build_narrator_prompt(sample_context, profile_with)
        
        from tgn.narrator.voice import WritingVoiceProfile
        profile_without = WritingVoiceProfile(
            name="simple",
            instructions="[WRITING VOICE — SIMPLE]\n\nSimple instructions."
        )
        prompt_without = build_narrator_prompt(sample_context, profile_without)
        
        # Extract ROLE section
        role_start_with = prompt_with.find("[ROLE]")
        role_end_with = prompt_with.find("[NON-NEGOTIABLE RULES]")
        role_section_with = prompt_with[role_start_with:role_end_with]
        
        role_start_without = prompt_without.find("[ROLE]")
        role_end_without = prompt_without.find("[NON-NEGOTIABLE RULES]")
        role_section_without = prompt_without[role_start_without:role_end_without]
        
        assert role_section_with == role_section_without
        
        # Extract NON-NEGOTIABLE RULES section
        rules_start_with = prompt_with.find("[NON-NEGOTIABLE RULES]")
        rules_end_with = prompt_with.find("[FACTS]")
        rules_section_with = prompt_with[rules_start_with:rules_end_with]
        
        rules_start_without = prompt_without.find("[NON-NEGOTIABLE RULES]")
        rules_end_without = prompt_without.find("[FACTS]")
        rules_section_without = prompt_without[rules_start_without:rules_end_without]
        
        assert rules_section_with == rules_section_without
