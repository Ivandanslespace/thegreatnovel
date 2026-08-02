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
    ActionExecutionResult,
)
from .world_phase import is_action_blocked_by_phase, get_current_phase, minutes_until_phase_change
from .progression import can_advance_track, get_track_stage, get_gate_cost, progression_enabled
from .build_choice import (
    build_choice_enabled, build_choice_trigger_ready, get_selected_build,
    get_available_build_ids, get_rest_duration,
    build_allows_drop_during_phase_window, build_allows_rest_at_target,
    get_player_visible_build_choices,
    BUILD_CHOICE_TIME,
)
from .named_actor import (
    ACTOR_CONVERSATION_RESOLVED,
    MARA_ACTOR_ID,
    MARA_FACT_ID,
    TALK_TO_ACTOR,
    TALK_TO_ACTOR_TIME,
    can_talk_to_actor,
)
from .devour_evolution import (
    DEVOUR_REMAINS,
    DEVOUR_RESOLVED,
    DEVOUR_STAMINA_COST,
    DEVOUR_TIME,
    build_devour_capability_observation,
    build_devour_event_payload,
    can_devour_remains,
)


# Fixed costs per spec
DROP_COST = {"time": 10, "stamina": 1}
SEARCH_COST = {"time": 30, "stamina": 2}
EXTRACT_COST = {"time": 15, "stamina": 0}
FIGHT_COST = {"time": 10, "stamina": 1}
FLEE_COST = {"time": 15, "stamina": 0}
UPGRADE_COST = {"time": 5, "stamina": 0}
REST_COST = {"time": 20, "stamina": 0}


def get_legal_actions(state: GameState) -> tuple[LegalAction, ...]:
    """
    State-dependent legal actions builder.
    
    Returns immutable tuple of LegalAction objects representing currently valid actions.
    This is THE single source of truth for legality - both Observation and Validator
    derive their logic from this function's conditions.
    
    A supported action absent from the result means ACTION_NOT_LEGAL_IN_STATE.
    """
    player = state.data.get("player", {})
    
    # P0: Dead player cannot act — universally, before any other check
    hp = player.get("hp")
    if hp is not None and hp <= 0:
        return ()
    
    if not state.data.get("expedition"):
        return (LegalAction(action_type="WAIT", duration_minutes=None, stamina_cost=0),)
    
    exp = state.data["expedition"]
    stamina = player["stamina"]
    
    # Phase 4: Active encounter forces FIGHT or FLEE only
    encounter = exp.get("encounter")
    if encounter and encounter.get("active"):
        # Encounter legality requires: expedition active, player at target, enemy alive
        if (exp["active"]
                and player["location_id"] == exp["target_location_id"]
                and encounter.get("enemy_hp", 0) > 0):
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
        # Contradictory state — invariants should reject; offer nothing
        return ()
    
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
        
        # Phase 6: progression actions at base (expedition inactive)
        if player["location_id"] == exp["base_location_id"]:
            if can_advance_track(state, "player"):
                legal.append(LegalAction(
                    action_type="UPGRADE_PLAYER",
                    duration_minutes=UPGRADE_COST["time"],
                    stamina_cost=UPGRADE_COST["stamina"],
                ))
            if can_advance_track(state, "base"):
                legal.append(LegalAction(
                    action_type="UPGRADE_BASE",
                    duration_minutes=UPGRADE_COST["time"],
                    stamina_cost=UPGRADE_COST["stamina"],
                ))
            # REST: unlocked by player stage >= 1, only when stamina < max
            player_stage = get_track_stage(state, "player")
            max_stamina = player.get("max_stamina", 0)
            if player_stage is not None and player_stage >= 1 and stamina < max_stamina:
                rest_time = get_rest_duration(state)
                legal.append(LegalAction(
                    action_type="REST",
                    duration_minutes=rest_time,
                    stamina_cost=REST_COST["stamina"],
                ))
            
            # Phase 7: CHOOSE_BUILD variants at base (expedition inactive)
            if build_choice_trigger_ready(state):
                for build_id in get_available_build_ids(state):
                    legal.append(LegalAction(
                        action_type="CHOOSE_BUILD",
                        duration_minutes=BUILD_CHOICE_TIME,
                        stamina_cost=0,
                        params={"build_id": build_id},
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

            # Phase 10A: a defeated, eligible remains can be consumed only by
            # the explicit capability-specific action.  It is intentionally
            # placed before EXTRACT and is absent from legacy states.
            if can_devour_remains(state):
                legal.append(LegalAction(
                    action_type=DEVOUR_REMAINS,
                    duration_minutes=DEVOUR_TIME,
                    stamina_cost=DEVOUR_STAMINA_COST,
                    params={},
                ))
            
            # Can always EXTRACT from target location
            legal.append(LegalAction(
                action_type="EXTRACT",
                duration_minutes=EXTRACT_COST["time"],
                stamina_cost=EXTRACT_COST["stamina"]
            ))
            
            # Phase 7: selected target-rest build allows REST at target
            encounter = exp.get("encounter")
            if build_allows_rest_at_target(state):
                player_stage = get_track_stage(state, "player")
                max_stamina = player.get("max_stamina", 0)
                if (player_stage is not None and player_stage >= 1
                        and stamina < max_stamina
                        and not (encounter and encounter.get("active"))):
                    rest_time = get_rest_duration(state)
                    legal.append(LegalAction(
                        action_type="REST",
                        duration_minutes=rest_time,
                        stamina_cost=REST_COST["stamina"],
                    ))
        elif player["location_id"] == exp["base_location_id"]:
            # At base while expedition active - can retry DROP if target unsearched and stamina ok
            if not exp["target_searched"] and stamina >= DROP_COST["stamina"]:
                legal.append(LegalAction(
                    action_type="DROP",
                    duration_minutes=DROP_COST["time"],
                    stamina_cost=DROP_COST["stamina"]
                ))

    # Phase 7.5: the only local named-actor interaction is canonicalized here.
    # It is intentionally added before the phase filter and is suppressed by
    # the active-encounter early return above.
    if can_talk_to_actor(state, MARA_ACTOR_ID):
        legal.append(LegalAction(
            action_type=TALK_TO_ACTOR,
            duration_minutes=TALK_TO_ACTOR_TIME,
            stamina_cost=0,
            params={"actor_id": MARA_ACTOR_ID},
        ))
    
    # Phase 5: filter actions blocked by current world phase (opportunity layer only)
    # Phase 6: base stage >= 1 overrides the DROP phase-window block
    base_stage = get_track_stage(state, "base")
    drop_override = (
        (base_stage is not None and base_stage >= 1)
        or build_allows_drop_during_phase_window(state)
    )
    
    filtered = []
    for la in legal:
        if is_action_blocked_by_phase(state, la.action_type):
            if la.action_type == "DROP" and drop_override:
                filtered.append(la)
            # else: blocked by phase, omit
        else:
            filtered.append(la)
    
    return tuple(filtered)


def validate_action(
    state: GameState,
    intent: ActionIntent,
) -> ActionValidationResult:
    """Validate Phase 3/4 actions against state using single source of truth."""
    errors: list[ActionValidationError] = []
    
    # Check action type is supported
    if intent.action_type not in ["WAIT", "DROP", "SEARCH", "EXTRACT", "FIGHT", "FLEE",
                                   "UPGRADE_PLAYER", "UPGRADE_BASE", "REST", "CHOOSE_BUILD",
                                   TALK_TO_ACTOR, DEVOUR_REMAINS]:
        errors.append(ActionValidationError(
            code="UNKNOWN_ACTION",
            message=f"Unknown action type: {intent.action_type}",
            field="action_type",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    # ALL actions derive state legality from get_legal_actions (single source)
    legal_actions = get_legal_actions(state)
    
    # Parameterized actions match action_type AND params exactly.
    if intent.action_type in ("CHOOSE_BUILD", TALK_TO_ACTOR):
        matched_la = None
        for la in legal_actions:
            if la.action_type == intent.action_type and la.params == intent.params:
                matched_la = la
                break
        if matched_la is None:
            errors.append(ActionValidationError(
                code="ACTION_NOT_LEGAL_IN_STATE",
                message=f"{intent.action_type} with params {intent.params} not legal in current state",
            ))
            return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
        # Use engine-authoritative params (detached copy)
        validated = ValidatedAction(
            action_id=intent.action_id,
            actor_id=intent.actor_id,
            action_type=intent.action_type,
            params=dict(matched_la.params),
            duration_minutes=matched_la.duration_minutes,
            stamina_cost=matched_la.stamina_cost,
        )
        return ActionValidationResult(valid=True, action=validated)
    
    # For non-CHOOSE_BUILD: type-only matching (existing behavior)
    legal_action_types = tuple(la.action_type for la in legal_actions)
    
    if intent.action_type not in legal_action_types:
        errors.append(ActionValidationError(
            code="ACTION_NOT_LEGAL_IN_STATE",
            message=f"Action {intent.action_type} not legal in current state",
        ))
        return ActionValidationResult(valid=False, action=None, errors=tuple(errors))
    
    # WAIT: delegate only parameter/schema validation to Phase 2
    if intent.action_type == "WAIT":
        from tgn.actions.validation import validate_action as base_validate
        return base_validate(state, intent)
    
    # Phase 3/4 parameter validation
    if intent.action_type == "DROP":
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"DROP does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    elif intent.action_type == "SEARCH":
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"SEARCH does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    elif intent.action_type == "EXTRACT":
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"EXTRACT does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    elif intent.action_type == "FIGHT":
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"FIGHT does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    elif intent.action_type == "FLEE":
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"FLEE does not accept parameter: {key}",
                field=f"params.{key}",
            ))
    
    elif intent.action_type in ("UPGRADE_PLAYER", "UPGRADE_BASE", "REST"):
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"{intent.action_type} does not accept parameter: {key}",
                field=f"params.{key}",
            ))

    elif intent.action_type == DEVOUR_REMAINS:
        for key in intent.params:
            errors.append(ActionValidationError(
                code="UNEXPECTED_PARAMETER",
                message=f"{DEVOUR_REMAINS} does not accept parameter: {key}",
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
    
    # Handle Phase 3/4/6/7 actions directly
    if intent.action_type in ["DROP", "SEARCH", "EXTRACT", "FIGHT", "FLEE",
                               "UPGRADE_PLAYER", "UPGRADE_BASE", "REST", "CHOOSE_BUILD",
                               TALK_TO_ACTOR, DEVOUR_REMAINS]:
        return _execute_phase3_action(state, intent)
    
    # WAIT: validate via canonical source, then produce TIME_ADVANCED
    elif intent.action_type == "WAIT":
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
    
    elif intent.action_type == "UPGRADE_PLAYER":
        gate = state.data["progression_gates"]["player"]
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="PLAYER_PROGRESSION_ADVANCED",
            game_minute=state.game_minute + UPGRADE_COST["time"],
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "from_stage": gate["from_stage"],
                "to_stage": gate["to_stage"],
                "resource_cost": dict(gate["cost"]),
                "time": UPGRADE_COST["time"],
            },
        )
    
    elif intent.action_type == "UPGRADE_BASE":
        gate = state.data["progression_gates"]["base"]
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="BASE_PROGRESSION_ADVANCED",
            game_minute=state.game_minute + UPGRADE_COST["time"],
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "from_stage": gate["from_stage"],
                "to_stage": gate["to_stage"],
                "resource_cost": dict(gate["cost"]),
                "time": UPGRADE_COST["time"],
            },
        )
    
    elif intent.action_type == "REST":
        player = state.data["player"]
        rest_time = get_rest_duration(state)
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="REST_RESOLVED",
            game_minute=state.game_minute + rest_time,
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "stamina_before": player["stamina"],
                "stamina_after": player["max_stamina"],
                "time": rest_time,
            },
        )
    
    elif intent.action_type == "CHOOSE_BUILD":
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="BUILD_SELECTED",
            game_minute=state.game_minute + BUILD_CHOICE_TIME,
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "build_id": validated.params["build_id"],
                "time": BUILD_CHOICE_TIME,
            },
        )

    elif intent.action_type == DEVOUR_REMAINS:
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type=DEVOUR_RESOLVED,
            game_minute=state.game_minute + DEVOUR_TIME,
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload=build_devour_event_payload(state),
        )

    elif intent.action_type == TALK_TO_ACTOR:
        actor = state.data["named_actor"]
        event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type=ACTOR_CONVERSATION_RESOLVED,
            game_minute=state.game_minute + TALK_TO_ACTOR_TIME,
            decision_seq=state.decision_seq + 1,
            action_id=validated.action_id,
            actor_id=validated.actor_id,
            payload={
                "actor_id": validated.params["actor_id"],
                "time": TALK_TO_ACTOR_TIME,
                "trust_before": actor["relationship"]["trust"],
                "trust_after": actor["relationship"]["trust"] + 1,
                "shared_fact_ids": [MARA_FACT_ID],
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
    params: dict = field(default_factory=dict)


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
    legal_actions = get_legal_actions(state)
    
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
        "legal_actions": legal_actions,
    }
    
    # Phase 4: HP visible
    if "hp" in player:
        observation["hp"] = player["hp"]
        observation["max_hp"] = player["max_hp"]

    # Phase 10A exposes only the approved Capability identity.  Eligibility,
    # grant internals, and the encounter yield remain engine-private.
    capabilities = build_devour_capability_observation(state)
    if capabilities:
        observation["capabilities"] = capabilities
    
    # Phase 4: Enemy visible only when encounter active
    encounter = exp.get("encounter")
    if encounter and encounter.get("active"):
        observation["enemy"] = {
            "enemy_id": encounter["enemy_id"],
            "enemy_hp": encounter["enemy_hp"],
            "enemy_max_hp": encounter["enemy_max_hp"],
            "enemy_attack": encounter["enemy_attack"],
        }
    
    # Phase 5: world phase visible only when phase_cycle config present
    phase = get_current_phase(state)
    if phase is not None:
        observation["world_phase"] = phase
        observation["minutes_until_phase_change"] = minutes_until_phase_change(state)
    
    # Phase 6: progression visible only when progression enabled
    if progression_enabled(state):
        prog_tracks = {}
        for track_id in state.data["progression"]["tracks"]:
            stage = get_track_stage(state, track_id)
            cost = get_gate_cost(state, track_id)
            prog_tracks[track_id] = {
                "stage": stage,
                "next_cost": cost,
            }
        observation["progression"] = {"tracks": prog_tracks}

    # Phase 7.5: this is a detached player projection, never raw actor state.
    from .named_actor import build_actor_observation, named_actor_feature_enabled

    if named_actor_feature_enabled(state):
        observation["actor"] = build_actor_observation(state)
    
    # Phase 7: build visible only when build feature enabled
    if build_choice_enabled(state):
        observation["build"] = {
            "selected": get_selected_build(state),
            "choice_available": any(
                action.action_type == "CHOOSE_BUILD"
                for action in legal_actions
            ),
            "choices": get_player_visible_build_choices(state),
            "selection_rule": (
                "Choose one candidate once; after selection, no other build "
                "candidate can be chosen."
            ),
        }
    
    # target_loot is always hidden (information asymmetry)
    
    return observation
