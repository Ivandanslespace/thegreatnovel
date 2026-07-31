"""Gameplay system for Phase 3."""

from .expedition import (
    validate_action,
    execute_action,
    get_legal_actions,
    build_observation,
)

__all__ = [
    "validate_action",
    "execute_action", 
    "get_legal_actions",
    "build_observation",
]
