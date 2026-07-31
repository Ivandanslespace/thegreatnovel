"""Phase 3 expedition action system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.models import DomainEvent, GameState
from ..actions.models import (
    ActionIntent,
    ValidatedAction,
    ActionValidationResult,
    ActionValidationError,
    ActionExecutionResult,
)


# Fixed costs per spec
DROP_COST = {"time": 10, "stamina": 1}
SEARCH_COST = {"time": 30, "stamina": 2}
EXTRACT_COST = {"time": 15, "stamina": 0}
FIGHT_COST = {"time": 10, "stamina": 1}
FLEE_COST = {"time": 15, "stamina": 0}


def get_legal_actions(state: GameState) -> tuple[LegalAction, ...]:
    """
    State-dependent legal actions builder.
    
    Returns immutable tuple of LegalAction objects representing currently valid actions.
    This is THE single source of truth for legality - both Observation and Validator
    derive their logic from this function's conditions.
    
    A supported action absent from the result means ACTION_NOT_LEGAL_IN_STATE.
    """
    if not state.data.get("expedition"):
        return (LegalAction(action_type="WAIT", duration_minutes=None, stamina_cost=0),)
    
    exp = state.data["expedition"]
    player = state.data["player"]
    stamina = player["stamina"]
    
    # Phase 4: Dead player cannot act (P0 invariant)
    hp = player.get("hp")
    if hp is not None and hp <= 0:
        return ()
    
    # Phase 4: Active encounter forces FIGHT or FLEE only
    encounter = exp.get("encounter")
    if encounter and encounter.get("active"):
        legal: list[LegalAction] = []
        if stamina >= FIGHT_COST["stamina"]:
            legal.append(LegalAction(
                action_type="FIGHT",
                duration_minutes=FIGHT_COST["time"],
                stamina_cost=FIGHT_COST["stamina"],
            ))
        legal.append(LegalAction(
            action_type="FLEE",
            duration_minutes=FLEE_COST["time"],
            stamina_cost=FLEE_COST["stamina"],
        ))
        return tuple(legal)
    
    # Normal expedition logic (Phase 3)
    legal = [
        LegalAction(action_type="WAIT", duration_minutes=None, stamina_cost=0)
    ]
    
    if not exp["active"]:
        # Not on expedition
        if player["location_id"] == exp["base_location_id"] and not exp["target_searched"]:
            # At base and target not yet searched, can DROP only if stamina sufficient
            if stamina >= DROP_COST["stamina"]:
                legal.append(LegalAction(
                    action_type="DROP",
                    duration_minutes=DROP_COST["time"],
                    stamina_cost=DROP_COST["stamina"]
                ))
    else:
        # On expedition
        if player["location_id"] == exp["target_location_id"]:
            # At target location
            if not exp["target_searched"]:
                # Target not yet searched, can SEARCH if stamina sufficient
                if stamina >= SEARCH_COST["stamina"]:
                    legal.append(LegalAction(
                        action_type="SEARCH",
                        duration_minutes=SEARCH_COST["time"],
                        stamina_cost=SEARCH_COST["stamina"]
                    ))
            
            # Can always EXTRACT from target location
            legal.append(LegalAction(
                action_type="EXTRACT",
                duration_minutes=EXTRACT_COST["time"],
                stamina_cost=EXTRACT_COST["stamina"]
            ))
        elif player["location_id"] == exp["base_location_id"]:
            # At base while expedition active - can retry DROP if target unsearched and stamina ok
            if not exp["target_searched"] and stamina >= DROP_COST["stamina"]:
                legal.append(LegalAction(
                    action_type="DROP",
                    duration_minutes=DROP_COST["time"],
                    stamina_cost=DROP_COST["stamina"]
                ))
    
    return tuple(legal)


def validate_action(
    state: GameState,
    intent: ActionIntent,
) -> ActionValidationResult:
    """Validate Phase 3/4 actions against state using single source of truth."""
    errors: list[ActionValidationError] = []
    
    # Check action type is supported
    if intent.action_type not in ["WAIT", "DROP", "SEARCH", "EXTRACT", "FIGHT", "FLEE"]:
        errors.append(ActionValidationError(
            code="UNKNOWN_ACTION",
            message=f"Unknown action type: {intent.action_type}",
            field="action_type",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    # WAIT reuses Phase 2 validation contract completely
    if intent.action_type == "WAIT":
        from tgn.actions.validation import validate_action as base_validate
        return base_validate(state, intent)
    
    # Get legal actions - this is THE source of truth for legality
    legal_actions = get_legal_actions(state)
    legal_action_types = tuple(la.action_type for la in legal_actions)
    
    # Check if action is currently legal in this state
    if intent.action_type not in legal_action_types:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message=f"Action {intent.action_type} not legal in current state",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    elif intent.action_type == "DROP":
        # No params allowed for DROP
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"DROP does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    elif intent.action_type == "SEARCH":
        # No params allowed for SEARCH
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"SEARCH does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    elif intent.action_type == "EXTRACT":
        # No params allowed for EXTRACT
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"EXTRACT does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    elif intent.action_type == "FIGHT":
        # No params allowed for FIGHT
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"FIGHT does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    elif intent.action_type == "FLEE":
        # No params allowed for FLEE
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"FLEE does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    if errors:
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    # Find the matching legal action for validated result
    for la in legal_actions:
        if la.action_type == intent.action_type:
            validated = ValidatedAction(
                action_id=intent.action_id,
                actor_id=intent.actor_id,
                action_type=intent.action_type,
                params={},
                duration_minutes=la.duration_minutes,
                stamina_cost=la.stamina_cost,
            )
            return ActionValidationResult(valid=True, action=validated)
    
    return ActionValidationResult(valid=False, action=None, errors=errors)


def execute_action(
    state: GameState,
    intent: ActionIntent,
) -> "ActionExecutionResult":
    """Execute validated action, produce event, apply via reducer."""
    
    # Handle Phase 3/4 actions directly
    if intent.action_type in ["DROP", "SEARCH", "EXTRACT", "FIGHT", "FLEE"]:
        return _execute_phase3_action(state, intent)
    
    # WAIT: check Phase 4 encounter gate first
    elif intent.action_type == "WAIT":
        # Phase 4: WAIT not legal during active encounter
        exp = state.data.get("expedition")
        if exp:
            encounter = exp.get("encounter")
            if encounter and encounter.get("active"):
                return ActionExecutionResult(
                    accepted=False,
                    validation=ActionValidationResult(
                        valid=False,
                        action=None,
                        errors=(
                            ActionValidationError(
                                code="ACTION_NOT_LEGAL_IN_STATE",
                                message="WAIT not legal during active hostile encounter",
                            ),
                        ),
                    ),
                    events=tuple(),
                    final_state=None,
                )
            # Phase 4: Dead player cannot WAIT
            player = state.data.get("player", {})
            if player.get("hp") is not None and player["hp"] <= 0:
                return ActionExecutionResult(
                    accepted=False,
                    validation=ActionValidationResult(
                        valid=False,
                        action=None,
                        errors=(
                            ActionValidationError(
                                code="ACTION_NOT_LEGAL_IN_STATE",
                                message="Dead player cannot act",
                            ),
                        ),
                    ),
                    events=tuple(),
                    final_state=None,
                )
        
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
            game_minute=state.game_minute,
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
    """Execute Phase 3/4 actions (DROP, SEARCH, EXTRACT, FIGHT, FLEE) with built-in validation."""
    
    # Validate using Phase 3/4 logic
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
            game_minute=state.game_minute,
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
                "time": EXTRACT_COST["time"],
            },
        )
    
    elif intent.action_type == "FIGHT":
        # Phase 4: Deterministic combat resolution
        player = state.data["player"]
        encounter = state.data["expedition"]["encounter"]
        
        # Compute combat outcome (engine authority)
        player_damage_dealt = player["attack"]
        new_enemy_hp = max(0, encounter["enemy_hp"] - player_damage_dealt)
        
        if new_enemy_hp > 0:
            enemy_damage_dealt = encounter["enemy_attack"]
        else:
            enemy_damage_dealt = 0
        
        new_player_hp = max(0, player["hp"] - enemy_damage_dealt)
        
        if new_player_hp <= 0:
            outcome = "PLAYER_DIED"
        elif new_enemy_hp <= 0:
            outcome = "ENEMY_DEFEATED"
        else:
            outcome = "ONGOING"
        
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="COMBAT_RESOLVED",
            game_minute=state.game_minute + FIGHT_COST["time"],
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "enemy_id": encounter["enemy_id"],
                "player_damage_dealt": player_damage_dealt,
                "enemy_damage_dealt": enemy_damage_dealt,
                "enemy_hp_after": new_enemy_hp,
                "player_hp_after": new_player_hp,
                "outcome": outcome,
                "time": FIGHT_COST["time"],
                "stamina_cost": FIGHT_COST["stamina"],
            },
        )
    
    elif intent.action_type == "FLEE":
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="EXPEDITION_FLED",
            game_minute=state.game_minute + FLEE_COST["time"],
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "time": FLEE_COST["time"],
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


@dataclass(frozen=True)
class LegalAction:
    """Legal action with metadata."""
    action_type: str
    duration_minutes: int | None
    stamina_cost: int


# Observation Builder - returns player-visible info
def build_observation(state: GameState) -> dict[str, Any]:
    """
    Build observation for player.
    
    Returns player-visible information including legal actions.
    
    Player MAY see:
    - game_minute, location_id, stamina, max_stamina
    - hp, max_hp (Phase 4)
    - inventory, carried_loot
    - expedition_active, target_searched
    - legal_actions with known costs
    - enemy state when encounter active (Phase 4)
    
    Player MUST NOT see:
    - target_loot (undiscovered information)
    - enemy data before encounter activation
    - future combat results
    """
    player = state.data["player"]
    exp = state.data["expedition"]
    
    # Deep copy to avoid mutating state
    observation = {
        "game_minute": state.game_minute,
        "location_id": player["location_id"],
        "stamina": player["stamina"],
        "max_stamina": player["max_stamina"],
        "inventory": dict(state.data["inventory"]),
        "carried_loot": dict(exp["carried_loot"]),
        "expedition_active": exp["active"],
        "target_searched": exp["target_searched"],
        "legal_actions": get_legal_actions(state),
    }
    
    # Phase 4: HP visible
    if "hp" in player:
        observation["hp"] = player["hp"]
        observation["max_hp"] = player["max_hp"]
    
    # Phase 4: Enemy visible only when encounter active
    encounter = exp.get("encounter")
    if encounter and encounter.get("active"):
        observation["enemy"] = {
            "enemy_id": encounter["enemy_id"],
            "enemy_hp": encounter["enemy_hp"],
            "enemy_max_hp": encounter["enemy_max_hp"],
            "enemy_attack": encounter["enemy_attack"],
        }
    
    # target_loot is always hidden (information asymmetry)
    
    return observation
