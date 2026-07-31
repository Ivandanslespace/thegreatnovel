"""Writing Voice profiles and registry for narrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Optional


@dataclass(frozen=True)
class WritingVoiceProfile:
    """
    Writing voice profile for narrator.
    
    This is a PRESENTATION CONTRACT only.
    It determines HOW to write, never WHAT happens.
    
    Voice profile must never:
    - Access GameState
    - Access hidden world state
    - Override facts
    - Create new game mechanics
    """
    name: str
    instructions: str
    examples: Tuple[str, ...] = ()


class VoiceNotFoundError(Exception):
    """Raised when a requested voice pack is not found in the registry."""
    
    def __init__(self, voice_id: str, available_voices: Tuple[str, ...]):
        self.voice_id = voice_id
        self.available_voices = available_voices
        super().__init__(
            f"Voice pack '{voice_id}' not found. "
            f"Available voices: {', '.join(available_voices)}"
        )


class DuplicateVoiceError(Exception):
    """Raised when attempting to register a voice with an ID that already exists."""
    
    def __init__(self, voice_id: str):
        self.voice_id = voice_id
        super().__init__(
            f"Voice pack '{voice_id}' already registered. "
            f"Built-in voices cannot be overridden by local packs."
        )


class VoiceRegistry:
    """
    Registry for managing voice packs.
    
    Provides deterministic, offline voice selection without hardcoding
    voice knowledge into NarratorService.
    """
    
    def __init__(self):
        self._voices: Dict[str, WritingVoiceProfile] = {}
    
    def register(self, profile: WritingVoiceProfile) -> None:
        """
        Register a voice profile.
        
        Raises DuplicateVoiceError if voice_id already exists.
        """
        if profile.name in self._voices:
            raise DuplicateVoiceError(profile.name)
        self._voices[profile.name] = profile
    
    def get(self, voice_id: str) -> WritingVoiceProfile:
        """
        Get a voice profile by ID.
        
        Raises VoiceNotFoundError if voice_id not found.
        """
        if voice_id not in self._voices:
            raise VoiceNotFoundError(voice_id, tuple(sorted(self._voices.keys())))
        return self._voices[voice_id]
    
    def list(self) -> Tuple[WritingVoiceProfile, ...]:
        """
        List all registered voice profiles.
        
        Returns deterministic sorted order.
        """
        return tuple(sorted(self._voices.values(), key=lambda v: v.name))


# Default voice for Phase 3.7
DEFAULT_VOICE_ID = "cablecar_survival"


def create_builtin_registry() -> VoiceRegistry:
    """Create a registry pre-loaded with built-in voices."""
    # Import here to avoid circular dependency
    from .voices import CABLECAR_SURVIVAL_VOICE, JINGXUAN_WRITING_VOICE
    
    registry = VoiceRegistry()
    registry.register(CABLECAR_SURVIVAL_VOICE)
    registry.register(JINGXUAN_WRITING_VOICE)
    return registry
