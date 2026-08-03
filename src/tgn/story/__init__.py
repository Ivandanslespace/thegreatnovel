"""Fact-bound narration sidecar."""

from .narration import (
    NarrationError,
    NarrationResponse,
    build_narration_request,
    commit_narration,
    fallback_response,
    validate_narration_response,
    verify_story,
)

__all__ = [
    "NarrationError",
    "NarrationResponse",
    "build_narration_request",
    "commit_narration",
    "fallback_response",
    "validate_narration_response",
    "verify_story",
]
