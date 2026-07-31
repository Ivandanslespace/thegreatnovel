"""Tests for VoiceRegistry."""

import pytest
from tgn.narrator.voice import (
    VoiceRegistry,
    VoiceNotFoundError,
    DuplicateVoiceError,
    DEFAULT_VOICE_ID,
    create_builtin_registry,
    WritingVoiceProfile,
)


class TestVoiceRegistry:
    """Tests for VoiceRegistry."""
    
    def test_registry_initializes_empty(self):
        """Registry starts with no voices."""
        registry = VoiceRegistry()
        assert len(registry.list()) == 0
    
    def test_register_voice(self):
        """Can register a voice profile."""
        registry = VoiceRegistry()
        profile = WritingVoiceProfile(
            name="test_voice",
            instructions="Test instructions"
        )
        registry.register(profile)
        
        assert len(registry.list()) == 1
        assert registry.get("test_voice") == profile
    
    def test_register_multiple_voices(self):
        """Can register multiple voice profiles."""
        registry = VoiceRegistry()
        
        profile1 = WritingVoiceProfile(name="voice1", instructions="Instructions 1")
        profile2 = WritingVoiceProfile(name="voice2", instructions="Instructions 2")
        
        registry.register(profile1)
        registry.register(profile2)
        
        assert len(registry.list()) == 2
        assert registry.get("voice1") == profile1
        assert registry.get("voice2") == profile2
    
    def test_get_voice_not_found(self):
        """Getting non-existent voice raises VoiceNotFoundError."""
        registry = VoiceRegistry()
        
        with pytest.raises(VoiceNotFoundError) as exc_info:
            registry.get("nonexistent")
        
        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.voice_id == "nonexistent"
        assert exc_info.value.available_voices == ()
    
    def test_get_voice_not_found_shows_available(self):
        """VoiceNotFoundError lists available voices."""
        registry = VoiceRegistry()
        
        profile1 = WritingVoiceProfile(name="voice1", instructions="Instructions 1")
        profile2 = WritingVoiceProfile(name="voice2", instructions="Instructions 2")
        
        registry.register(profile1)
        registry.register(profile2)
        
        with pytest.raises(VoiceNotFoundError) as exc_info:
            registry.get("nonexistent")
        
        assert "voice1" in str(exc_info.value)
        assert "voice2" in str(exc_info.value)
    
    def test_duplicate_voice_rejected(self):
        """Cannot register duplicate voice ID."""
        registry = VoiceRegistry()
        
        profile1 = WritingVoiceProfile(name="test_voice", instructions="Instructions 1")
        profile2 = WritingVoiceProfile(name="test_voice", instructions="Instructions 2")
        
        registry.register(profile1)
        
        with pytest.raises(DuplicateVoiceError) as exc_info:
            registry.register(profile2)
        
        assert "test_voice" in str(exc_info.value)
        assert exc_info.value.voice_id == "test_voice"
    
    def test_list_voices_sorted(self):
        """list() returns voices in sorted order."""
        registry = VoiceRegistry()
        
        profile_c = WritingVoiceProfile(name="voice_c", instructions="C")
        profile_a = WritingVoiceProfile(name="voice_a", instructions="A")
        profile_b = WritingVoiceProfile(name="voice_b", instructions="B")
        
        registry.register(profile_c)
        registry.register(profile_a)
        registry.register(profile_b)
        
        voices = registry.list()
        assert len(voices) == 3
        assert voices[0].name == "voice_a"
        assert voices[1].name == "voice_b"
        assert voices[2].name == "voice_c"
    
    def test_list_voices_deterministic(self):
        """list() returns deterministic order."""
        registry = VoiceRegistry()
        
        profile1 = WritingVoiceProfile(name="voice1", instructions="1")
        profile2 = WritingVoiceProfile(name="voice2", instructions="2")
        
        registry.register(profile1)
        registry.register(profile2)
        
        voices1 = registry.list()
        voices2 = registry.list()
        
        assert voices1 == voices2
    
    def test_default_voice_id(self):
        """DEFAULT_VOICE_ID is cablecar_survival."""
        assert DEFAULT_VOICE_ID == "cablecar_survival"
    
    def test_create_builtin_registry(self):
        """create_builtin_registry() creates registry with built-in voices."""
        registry = create_builtin_registry()
        
        voices = registry.list()
        assert len(voices) == 2
        
        voice_names = [v.name for v in voices]
        assert "cablecar_survival" in voice_names
        assert "jingxuan" in voice_names
    
    def test_builtin_registry_get_cablecar(self):
        """Can get cablecar_survival from built-in registry."""
        registry = create_builtin_registry()
        
        voice = registry.get("cablecar_survival")
        assert voice.name == "cablecar_survival"
        assert len(voice.instructions) > 0
    
    def test_builtin_registry_get_jingxuan(self):
        """Can get jingxuan from built-in registry."""
        registry = create_builtin_registry()
        
        voice = registry.get("jingxuan")
        assert voice.name == "jingxuan"
        assert len(voice.instructions) > 0
    
    def test_builtin_registry_cannot_override(self):
        """Cannot override built-in voices."""
        registry = create_builtin_registry()
        
        # Try to register duplicate
        duplicate = WritingVoiceProfile(
            name="cablecar_survival",
            instructions="Different instructions"
        )
        
        with pytest.raises(DuplicateVoiceError):
            registry.register(duplicate)
