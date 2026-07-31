"""Phase 3 expedition action system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.models import DomainEvent, GameState
from ..actions.models import (
    ActionIntent,
    ValidatedAction,
    ActionValidationResult,
    ActionValidationError,
)


# Fixed costs per spec
DROP_COST = {"time": 10, "stamina": 1}
SEARCH_COST = {"time": 30, "stamina": 2}
EXTRACT_COST = {"time": 15, "stamina": 0}


def get_legal_actions(state: GameState) -> list[str]:
    """
    State-dependent legal actions builder.
    
    Returns list of action_type strings that are currently valid based on state.
    This is the single source of truth for legality - both Validator and Observation
    use this same function.
    """
    if not state.data.get("expedition"):
        return ["WAIT"]
    
    exp = state.data["expedition"]
    player = state.data["player"]
    stamina = player["stamina"]
    max_stamina = player["max_stamina"]
    
    # Always can WAIT
    actions = ["WAIT"]
    
    if not exp["active"]:
        # Not on expedition
        if player["location_id"] == exp["base_location_id"]:
            # At base, can DROP
            actions.append("DROP")
    else:
        # On expedition
        if player["location_id"] == exp["target_location_id"]:
            # At target location
            if not exp["target_searched"]:
                # Target not yet searched
                if stamina >= SEARCH_COST["stamina"]:
                    actions.append("SEARCH")
            
            # Can always EXTRACT from target location
            actions.append("EXTRACT")
        # If at base while active, shouldn't happen but just in case
        elif player["location_id"] == exp["base_location_id"]:
            actions.append("EXTRACT")
    
    return actions


def validate_action(
    state: GameState,
    intent: ActionIntent,
) -> ActionValidationResult:
    """Validate Phase 3 actions against state."""
    errors: list[ActionValidationError] = []
    
    # Check action type is supported
    if intent.action_type not in ["WAIT", "DROP", "SEARCH", "EXTRACT"]:
        errors.append(ActionValidationError(
            code="UNKNOWN_ACTION",
            message=f"Unknown action type: {intent.action_type}",
            field="action_type",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    if intent.action_type == "WAIT":
        return _validate_wait(state, intent, errors)
    
    elif intent.action_type == "DROP":
        return _validate_drop(state, intent, errors)
    
    elif intent.action_type == "SEARCH":
        return _validate_search(state, intent, errors)
    
    elif intent.action_type == "EXTRACT":
        return _validate_extract(state, intent, errors)
    
    return ActionValidationResult(valid=False, action=None, errors=tuple(errors))


def execute_action(
    state: GameState,
    intent: ActionIntent,
) -> "ActionExecutionResult":
    """Execute validated action, produce event, apply via reducer."""
    
    # Handle Phase 3 actions directly
    if intent.action_type in ["DROP", "SEARCH", "EXTRACT"]:
        return _execute_phase3_action(state, intent)
    
    # Delegate WAIT to Phase 2 validation (preserves Phase 2 behavior)
    elif intent.action_type == "WAIT":
        from tgn.actions.validation import validate_action as base_validate
        
        validation = base_validate(state, intent)
        
        if not validation.valid:
            return ActionExecutionResult(
                accepted=False,
                validation=validation,
                events=tuple(),
                final_state=None,
            )
        
        validated = validation.action
        assert validated is not None
        
        # Produce TIME_ADVANCED event (existing Phase 2 pattern)
        event = DomainEvent.advance_time(
            game_minute=state.game_minute + validated.duration_minutes,
            minutes=validated.duration_minutes,
            event_seq=state.event_seq + 1,
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
        )
        
        # Apply via reducer
        from ..core.reducer import reduce_event
        
        new_state = reduce_event(state, event)
        
        return ActionExecutionResult(
            accepted=True,
            validation=validation,
            events=(event,),
            final_state=new_state,
        )
    
    # Reject unknown action types
    else:
        return ActionExecutionResult(
            accepted=False,
            validation=ActionValidationResult(
                valid=False,
                action=None,
                errors=(
                    ActionValidationError(
                        code="UNKNOWN_ACTION",
                        message=f"Unknown action type: {intent.action_type}",
                        field="action_type",
                    ),
                ),
            ),
            events=tuple(),
            final_state=None,
        )


def _execute_phase3_action(
    state: GameState,
    intent: ActionIntent,
) -> ActionExecutionResult:
    """Execute Phase 3 actions (DROP, SEARCH, EXTRACT) with built-in validation."""
    
    # Validate using Phase 3 logic
    validation = validate_action(state, intent)
    
    if not validation.valid:
        return ActionExecutionResult(
            accepted=False,
            validation=validation,
            events=tuple(),
            final_state=None,
        )
    
    validated = validation.action
    assert validated is not None
    
    # Produce semantic event based on action type
    if intent.action_type == "WAIT":
        # Use existing time advance event
        event = DomainEvent.advance_time(
            game_minute=state.game_minute + validated.duration_minutes,
            minutes=validated.duration_minutes,
            event_seq=state.event_seq + 1,
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
        )
    
    elif intent.action_type == "DROP":
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="EXPEDITION_DROPPED",
            game_minute=state.game_minute + DROP_COST["time"],
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "destination": state.data["expedition"]["target_location_id"],
                "time": DROP_COST["time"],
                "stamina_cost": DROP_COST["stamina"],
            },
        )
    
    elif intent.action_type == "SEARCH":
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="SEARCH_RESOLVED",
            game_minute=state.game_minute + SEARCH_COST["time"],
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "loot_gained": dict(state.data["expedition"]["target_loot"]),
                "location_match": True,
                "time": SEARCH_COST["time"],
                "stamina_cost": SEARCH_COST["stamina"],
            },
        )
    
    elif intent.action_type == "EXTRACT":
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="EXPEDITION_EXTRACTED",
            game_minute=state.game_minute + EXTRACT_COST["time"],
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "carried_loot": dict(state.data["expedition"]["carried_loot"]),
                "carried_matches": True,
                "time": EXTRACT_COST["time"],
            },
        )
    
    # Apply via reducer
    from ..core.reducer import reduce_event
    
    new_state = reduce_event(state, event)
    
    return ActionExecutionResult(
        accepted=True,
        validation=validation,
        events=(event,),
        final_state=new_state,
    )


def _validate_wait(
    state: GameState,
    intent: ActionIntent,
    errors: list[ActionValidationError],
) -> ActionValidationResult:
    """Validate WAIT action (preserves Phase 2 contract)."""
    params = intent.params
    
    # Require minutes
    if "minutes" not in params:
        errors.append(ActionValidationError(
            code="MISSING_FIELD",
            message="Missing required field: minutes",
            field="params.minutes",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    minutes = params["minutes"]
    
    # Validate types (bool rejection like Phase 2)
    if isinstance(minutes, bool):
        errors.append(ActionValidationError(
            code="INVALID_TYPE",
            message="minutes must be integer, not boolean",
            field="params.minutes",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    if not isinstance(minutes, int):
        errors.append(ActionValidationError(
            code="INVALID_TYPE",
            message=f"minutes must be integer, got {type(minutes).__name__}",
            field="params.minutes",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    if minutes <= 0:
        errors.append(ActionValidationError(
            code="INVALID_VALUE",
            message=f"minutes must be > 0, got {minutes}",
            field="params.minutes",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    # Reject unexpected parameters
    unexpected = set(params.keys()) - {"minutes"}
    if unexpected:
        for field_name in unexpected:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"Unexpected parameter: {field_name}",
                field=f"params.{field_name}",
            ))
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    validated = ValidatedAction(
        action_id=intent.action_id,
        actor_id=intent.actor_id,
        action_type="WAIT",
        params={"minutes": minutes},
        duration_minutes=minutes,
        stamina_cost=0,
    )
    
    return ActionValidationResult(valid=True, action=validated)


def _validate_drop(
    state: GameState,
    intent: ActionIntent,
    errors: list[ActionValidationError],
) -> ActionValidationResult:
    """Validate DROP action - leave base and enter expedition."""
    params = intent.params
    
    # Must have no extra params
    if params:
        for key in params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"DROP cannot accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    exp = state.data["expedition"]
    
    # Must not be already on expedition
    if exp["active"]:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message="DROP not legal while expedition is active",
        ))
    
    # Must be at base
    if state.data["player"]["location_id"] != exp["base_location_id"]:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message="DROP only legal at base location",
        ))
    
    # Must not have already searched target
    if exp["target_searched"]:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message="DROP not legal after target already searched",
        ))
    
    # Must have sufficient stamina
    if state.data["player"]["stamina"] < DROP_COST["stamina"]:
        errors.append(ActionValidationError(
            code="INSUFFICIENT_STAMINA",
            message=f"Need {DROP_COST['stamina']} stamina for DROP",
        ))
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    validated = ValidatedAction(
        action_id=intent.action_id,
        actor_id=intent.actor_id,
        action_type="DROP",
        params={},
        duration_minutes=DROP_COST["time"],
        stamina_cost=DROP_COST["stamina"],
    )
    
    return ActionValidationResult(valid=True, action=validated)


def _validate_search(
    state: GameState,
    intent: ActionIntent,
    errors: list[ActionValidationError],
) -> ActionValidationResult:
    """Validate SEARCH action - obtain carried loot from target."""
    params = intent.params
    
    # No extra params allowed
    if params:
        for key in params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"SEARCH cannot accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    exp = state.data["expedition"]
    player = state.data["player"]
    
    # Must be on active expedition
    if not exp["active"]:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message="SEARCH only legal during active expedition",
        ))
    
    # Must be at target location
    if player["location_id"] != exp["target_location_id"]:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message="SEARCH only legal at target location",
        ))
    
    # Must not have searched already
    if exp["target_searched"]:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message="Target already searched - search again rejected",
        ))
    
    # Must have sufficient stamina
    if player["stamina"] < SEARCH_COST["stamina"]:
        errors.append(ActionValidationError(
            code="INSUFFICIENT_STAMINA",
            message=f"Need {SEARCH_COST['stamina']} stamina for SEARCH",
        ))
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    validated = ValidatedAction(
        action_id=intent.action_id,
        actor_id=intent.actor_id,
        action_type="SEARCH",
        params={},
        duration_minutes=SEARCH_COST["time"],
        stamina_cost=SEARCH_COST["stamina"],
    )
    
    return ActionValidationResult(valid=True, action=validated)


def _validate_extract(
    state: GameState,
    intent: ActionIntent,
    errors: list[ActionValidationError],
) -> ActionValidationResult:
    """Validate EXTRACT action - return expedition and bank loot."""
    params = intent.params
    
    # No extra params allowed
    if params:
        for key in params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"EXTRACT cannot accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    exp = state.data["expedition"]
    player = state.data["player"]
    
    # Must be on active expedition
    if not exp["active"]:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message="EXTRACT only legal during active expedition",
        ))
    
    # Must be at target location (or base if somehow back there)
    if player["location_id"] not in [exp["target_location_id"], exp["base_location_id"]]:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message="EXTRACT requires being at target or base",
        ))
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    validated = ValidatedAction(
        action_id=intent.action_id,
        actor_id=intent.actor_id,
        action_type="EXTRACT",
        params={},
        duration_minutes=EXTRACT_COST["time"],
        stamina_cost=EXTRACT_COST["stamina"],
    )
    
    return ActionValidationResult(valid=True, action=validated)


@dataclass(frozen=True)
class LegalAction:
    """Legal action with metadata."""
    action_type: str
    duration_minutes: int | None
    stamina_cost: int


@dataclass
class ActionExecutionResult:
    """Result of attempting to execute an ActionIntent."""
    accepted: bool
    validation: ActionValidationResult
    events: tuple = ()
    final_state: Any | None = None


# Observation Builder - returns player-visible info
def build_observation(state: GameState) -> dict[str, Any]:
    """
    Build observation for player.
    
    Returns player-visible information including legal actions.
    Hides sensitive information like target_loot.
    
    DO NOT COPY Mutable dict - copy before modifying!
    """
    # Deep copy to avoid mutating state
    observation = {
        "game_minute": state.game_minute,
        "location_id": state.data["player"]["location_id"],
        "stamina": state.data["player"]["stamina"],
        "max_stamina": state.data["player"]["max_stamina"],
        "inventory": dict(state.data["inventory"]),
        "expedition_active": state.data["expedition"]["active"],
        "target_searched": state.data["expedition"]["target_searched"],
        "legal_actions": get_legal_actions(state),
    }
    
    # Note: carrying_loot is hidden until EXTRACT banks it
    # target_loot is always hidden (information asymmetry)
    
    return observation
