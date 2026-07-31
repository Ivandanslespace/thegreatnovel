"""Action contract data models for Phase 2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionIntent:
    """
    Untrusted request from player/bot/LLM.
    
    This is a REQUEST, not a fact. It cannot directly modify GameState.
    Must be validated before execution.
    """
    action_id: str
    actor_id: str
    action_type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidatedAction:
    """
    Action that has passed validation.
    
    Contains only safe, validated data that can be used to construct
    a DomainEvent. duration_minutes is confirmed by validator/resolver.
    
    Phase 3 added stamina_cost.
    """
    action_id: str
    actor_id: str
    action_type: str
    params: dict[str, Any]
    duration_minutes: int
    stamina_cost: int = 0  # Phase 3 addition


@dataclass(frozen=True)
class ActionValidationError:
    """Single validation error with context."""
    code: str
    message: str
    field: str | None = None


@dataclass(frozen=True)
class ActionValidationResult:
    """Result of validating an ActionIntent."""
    valid: bool
    action: ValidatedAction | None
    errors: tuple[ActionValidationError, ...] = field(default_factory=tuple)


@dataclass
class ActionExecutionResult:
    """
    Result of attempting to execute an ActionIntent.
    
    For WAIT:
      - accepted: exactly 1 event produced
      - rejected: 0 events, state unchanged
    
    The final_state is computed by reducer over events.
    """
    accepted: bool
    validation: ActionValidationResult
    events: tuple = field(default_factory=tuple)
    final_state: Any | None = None  # Will be GameState after reduce_event()
