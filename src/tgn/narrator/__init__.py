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
from .guard import validate_narration, NarrationValidationError
from .service import NarratorService, narrate_run
from .render import render_narrated_run
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
    
    # Guard
    "validate_narration",
    "NarrationValidationError",
    
    # Service
    "NarratorService",
    "narrate_run",
    
    # Render
    "render_narrated_run",
    
    # Clients
    "FakeNarratorClient",
    "OpenAICompatibleClient",
    "create_client_from_env",
]
