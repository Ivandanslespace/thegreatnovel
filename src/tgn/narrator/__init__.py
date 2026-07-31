"""Phase 3.6 narrator - LLM-powered novel watch mode."""

from .models import (
    NarrationContext,
    NarratedFrame,
    NarrationRunResult,
    NarrationError,
    NarratorClient,
)
from .context import build_narration_context
from .prompt import build_narrator_prompt
from .voice import (
    WritingVoiceProfile,
    VoiceRegistry,
    VoiceNotFoundError,
    DuplicateVoiceError,
    DEFAULT_VOICE_ID,
    create_builtin_registry,
)
from .voice_loader import (
    load_voice_pack,
    load_voice_packs,
    validate_voice_id,
    InvalidVoicePackError,
    VoicePackManifestError,
    VoicePackSecurityError,
)
from .voices import CABLECAR_SURVIVAL_VOICE, JINGXUAN_WRITING_VOICE
from .guard import validate_narration, NarrationValidationError
from .service import NarratorService, narrate_run
from .render import render_narrated_run, write_narrated_run_text
from .client import FakeNarratorClient, OpenAICompatibleClient, create_client_from_env

__all__ = [
    # Models
    "NarrationContext",
    "NarratedFrame",
    "NarrationRunResult",
    "NarrationError",
    "NarratorClient",
    
    # Context
    "build_narration_context",
    
    # Prompt
    "build_narrator_prompt",
    
    # Voice
    "WritingVoiceProfile",
    "VoiceRegistry",
    "VoiceNotFoundError",
    "DuplicateVoiceError",
    "DEFAULT_VOICE_ID",
    "create_builtin_registry",
    "CABLECAR_SURVIVAL_VOICE",
    "JINGXUAN_WRITING_VOICE",
    
    # Voice Loader
    "load_voice_pack",
    "load_voice_packs",
    "validate_voice_id",
    "InvalidVoicePackError",
    "VoicePackManifestError",
    "VoicePackSecurityError",
    
    # Guard
    "validate_narration",
    "NarrationValidationError",
    
    # Service
    "NarratorService",
    "narrate_run",
    
    # Render
    "render_narrated_run",
    "write_narrated_run_text",
    
    # Clients
    "FakeNarratorClient",
    "OpenAICompatibleClient",
    "create_client_from_env",
]
