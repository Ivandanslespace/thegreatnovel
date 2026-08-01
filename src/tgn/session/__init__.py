"""Minimal Phase 9A external-client session protocol."""

from .models import SessionError, SessionManifest, validate_stable_id
from .service import (
    SessionService,
    choose_session,
    next_session,
    start_session,
    status_session,
    stop_session,
    verify_session,
)

__all__ = [
    "SessionError",
    "SessionManifest",
    "SessionService",
    "validate_stable_id",
    "choose_session",
    "next_session",
    "start_session",
    "status_session",
    "stop_session",
    "verify_session",
]
