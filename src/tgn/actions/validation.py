"""Action validation logic for Phase 2."""

from __future__ import annotations

from tgn.core.models import DomainEvent, GameState
from .models import (
    ActionIntent,
    ValidatedAction,
    ActionValidationResult,
    ActionValidationError,
    ActionExecutionResult,
)


# Only WAIT is legal in Phase 2
LEGAL_ACTION_TYPES = frozenset({"WAIT"})

# Reserved metadata that intents cannot control
FORBIDDEN_METADATA_FIELDS = frozenset({
    "event_seq",
    "decision_seq",
    "game_minute",
    "state_hash",
    "event_id",
    "created_at",
})


def validate_action(
    state: GameState,
    intent: ActionIntent,
) -> ActionValidationResult:
    """
    Validate an ActionIntent without mutating state.
    
    Returns:
        - valid=True if intent can be executed
        - valid=False with structured errors if invalid
        
    This is a PURE function - no side effects.
    """
    errors: list[ActionValidationError] = []
    
    # Check action type first
    if intent.action_type not in LEGAL_ACTION_TYPES:
        errors.append(ActionValidationError(
            code="UNKNOWN_ACTION",
            message=f"Unknown action type: {intent.action_type}",
            field="action_type",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    # Check for forbidden metadata (for WAIT only since unknown already rejected)
    _check_forbidden_metadata(intent, errors)
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    # Only WAIT allowed
    if intent.action_type == "WAIT":
        _validate_wait(intent, errors)
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    # Build validated action
    minutes = int(intent.params.get("minutes", 0))
    validated = ValidatedAction(
        action_id=intent.action_id,
        actor_id=intent.actor_id,
        action_type="WAIT",
        params={"minutes": minutes},
        duration_minutes=minutes,
    )
    
    return ActionValidationResult(valid=True, action=validated)


def _check_forbidden_metadata(intent: ActionIntent, errors: list[ActionValidationError]) -> None:
    """Check for forbidden engine-controlled metadata in params."""
    for key in FORBIDDEN_METADATA_FIELDS:
        if key in intent.params:
            errors.append(ActionValidationError(
                code="FORBIDDEN_ENGINE_METADATA",
                message=f"Metadata field '{key}' is controlled by the engine, not by player actions",
                field=f"params.{key}",
            ))
            return  # Single error for simplicity


def _validate_wait(intent: ActionIntent, errors: list[ActionValidationError]) -> None:
    """Validate WAIT action parameters."""
    params = intent.params
    
    # Check required field
    if "minutes" not in params:
        errors.append(ActionValidationError(
            code="MISSING_FIELD",
            message="Missing required field: minutes",
            field="params.minutes",
        ))
        return
    
    minutes = params["minutes"]
    
    # Reject boolean (bool is subclass of int in Python!)
    if isinstance(minutes, bool):
        errors.append(ActionValidationError(
            code="INVALID_TYPE",
            message="minutes must be integer, not boolean",
            field="params.minutes",
        ))
        return
    
    # Must be int
    if not isinstance(minutes, int):
        errors.append(ActionValidationError(
            code="INVALID_TYPE",
            message=f"minutes must be integer, got {type(minutes).__name__}",
            field="params.minutes",
        ))
        return
    
    # Must be positive
    if minutes <= 0:
        errors.append(ActionValidationError(
            code="INVALID_VALUE",
            message=f"minutes must be > 0, got {minutes}",
            field="params.minutes",
        ))
        return


def execute_action(
    state: GameState,
    intent: ActionIntent,
) -> ActionExecutionResult:
    """
    Attempt to execute an ActionIntent.
    
    Path:
      Intent → Validator → ValidatedAction → DomainEvent → Reducer → New State
    
    Returns ActionExecutionResult with:
      - accepted/rejected status
      - validation result
      - events produced (empty if rejected)
      - final_state (None if rejected, or after reducer if accepted)
    
    This may call reducer but must NOT mutate input state directly.
    Illegal actions produce NO side effects.
    
    Future Extension Seam:
    ----------------------
    The current path is intentionally minimal for Phase 2:
    
        ValidatedAction
          ↓
      [future opportunity candidate generation]
          ↓
      Deterministic resolution
          ↓
      DomainEvent(s)
    
    In future phases, fortune_bias may influence which legal opportunities
    enter a candidate pool before deterministic resolution. Important constraints:
    
    - Opportunity ≠ guaranteed reward
    - Opportunity ≠ automatic success  
    - Opportunity ≠ Narrator cheating
    
    Fortune should ONLY affect:
      - Which opportunities become visible/available
      - Probability of certain legal actions being presented
    
    Fortune should NEVER:
      - Modify the reducer's truth
      - Guarantee success after action execution
      - Rewrite action results after the fact
      - Bypass deterministic verification
    
    This keeps the engine core pure and verifiable while allowing future
    design features that operate BEFORE validation, not after.
    """
    # Step 1: Validate
    validation_result = validate_action(state, intent)
    
    if not validation_result.valid:
        return ActionExecutionResult(
            accepted=False,
            validation=validation_result,
            events=tuple(),
            final_state=None,
        )
    
    # Step 2: Generate DomainEvent from validated action
    validated = validation_result.action
    assert validated is not None
    
    event_seq = state.event_seq + 1
    decision_seq = state.decision_seq + 1
    
    event = DomainEvent(
        event_seq=event_seq,
        event_type="TIME_ADVANCED",
        game_minute=state.game_minute + validated.duration_minutes,
        decision_seq=decision_seq,
        actor_id=validated.actor_id,
        action_id=validated.action_id,
        payload={"minutes": validated.duration_minutes},
    )
    
    # Step 3: Apply through reducer
    new_state = _apply_event_to_state(state, event)
    
    return ActionExecutionResult(
        accepted=True,
        validation=validation_result,
        events=(event,),
        final_state=new_state,
    )


def _apply_event_to_state(state: GameState, event: DomainEvent) -> GameState:
    """
    Apply event to state using reducer.
    
    Pure function - returns new state without mutating old one.
    """
    from tgn.core.reducer import reduce_event
    return reduce_event(state, event)
