"""Phase 3.6 narrator models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class NarrationContext:
    """
    Minimal context for LLM narrator.
    
    Built from WatchFrame only. Never contains GameState or EventStore.
    This is the ONLY input the narrator receives about game state.
    
    IMPORTANT: All dicts must be deep-copied to isolate from Engine state.
    """
    step: int
    
    action_type: str
    event_type: str
    
    game_minute_before: int
    game_minute_after: int
    
    location_before: str
    location_after: str
    
    stamina_before: int
    stamina_after: int
    max_stamina: int
    
    inventory_before: dict[str, int]
    inventory_after: dict[str, int]
    
    carried_before: dict[str, int]
    carried_after: dict[str, int]
    
    event_payload: dict[str, Any]


@dataclass(frozen=True)
class NarratedFrame:
    """
    A WatchFrame with LLM-generated narration.
    
    This is a presentation artifact, not runtime truth.
    The narration is prose only - it cannot modify game state.
    """
    step: int
    
    action_type: str
    event_type: str
    
    narration: str
    
    state_hash_before: str
    state_hash_after: str


@dataclass(frozen=True)
class NarrationRunResult:
    """
    Result of narrating an autoplay run.
    
    Contains narrated frames and source hashes for verification.
    Does NOT copy game state - only references hashes.
    """
    narrated_frames: tuple[NarratedFrame, ...]
    
    source_initial_hash: str
    source_final_hash: str
    
    narration_failures: int = 0
    
    # Optional reference to source run (for rendering)
    source_run: Any | None = None  # AutoplayRunResult


class NarrationError(Exception):
    """Raised when narration generation fails."""
    
    def __init__(self, step: int, action_type: str, event_type: str, message: str):
        self.step = step
        self.action_type = action_type
        self.event_type = event_type
        self.message = message
        super().__init__(f"Step {step} ({action_type}/{event_type}): {message}")


class NarratorClient(Protocol):
    """
    Protocol for LLM narrator clients.
    
    Implementations can be real (HTTP API) or fake (for testing).
    """
    
    def generate(self, prompt: str) -> str:
        """Generate narration text from prompt."""
        ...


@dataclass
class NarratorResponse:
    """Response from narrator client."""
    text: str
