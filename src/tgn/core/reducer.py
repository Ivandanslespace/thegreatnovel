"""Pure reducer function to apply events to game state."""

from __future__ import annotations

import copy
from typing import Any

from .hashing import state_hash
from .invariants import check_invariants
from .models import DomainEvent, GameState
from ..gameplay.world_phase import is_action_blocked_by_phase


class ReducerError(Exception):
    """Raised when event cannot be applied to state."""
    pass


def reduce_event(state: GameState, event: DomainEvent) -> GameState:
    """
    Apply a domain event to a game state, producing a new state.
    
    IMPORTANT: This is a PURE FUNCTION. It must NOT:
    - Modify the input state in place
    - Perform any I/O
    - Use random numbers or wall-clock time
    - Access databases or files
    
    Args:
        state: Current game state (deep copy will be made internally)
        event: Domain event to apply
        
    Returns:
        New GameState with event applied
        
    Raises:
        ReducerError: If event violates invariants or is incompatible with state
    """
    # Deep copy to ensure immutability of input
    new_state = copy.deepcopy(state)
    
    # Validate event sequence continuity
    if event.event_seq != new_state.event_seq + 1:
        raise ReducerError(
            f"Event sequence gap: expected {new_state.event_seq + 1}, "
            f"got {event.event_seq}"
        )
    
    # Check decision_seq non-retrogression
    if event.decision_seq < new_state.decision_seq:
        raise ReducerError(
            f"Decision sequence regression: {event.decision_seq} < {new_state.decision_seq}"
        )
    
    # Update decision_seq if needed
    if event.decision_seq > new_state.decision_seq:
        new_state.decision_seq = event.decision_seq
    
    # Always validate game_minute non-retrogression
    if event.game_minute < new_state.game_minute:
        raise ReducerError(f"Game minute retrogression: {event.game_minute} < {new_state.game_minute}")
    
    previous_game_minute = new_state.game_minute

    # Only TIME_ADVANCED is valid in Phase 1
    if event.event_type == "TIME_ADVANCED":
        _apply_time_advanced(new_state, event)
    
    # Phase 3 expedition events (minimal extension per spec #19)
    elif event.event_type == "EXPEDITION_DROPPED":
        _apply_expedition_dropped(new_state, event)
    
    elif event.event_type == "SEARCH_RESOLVED":
        _apply_search_resolved(new_state, event)
    
    elif event.event_type == "EXPEDITION_EXTRACTED":
        _apply_expedition_extracted(new_state, event)
    
    # Phase 4 risk events
    elif event.event_type == "COMBAT_RESOLVED":
        _apply_combat_resolved(new_state, event)

    # Phase 10A capability-specific event.  The feature module owns the
    # exact payload and local state validation; this dispatch remains narrow.
    elif event.event_type == "DEVOUR_RESOLVED":
        from ..gameplay.devour_evolution import apply_devour_resolved

        try:
            apply_devour_resolved(new_state, event)
        except Exception as exc:
            raise ReducerError(f"Devour evolution event rejected: {exc}") from exc
    
    elif event.event_type == "EXPEDITION_FLED":
        _apply_expedition_fled(new_state, event)
    
    # Phase 6 progression events
    elif event.event_type == "PLAYER_PROGRESSION_ADVANCED":
        _apply_progression_advanced(new_state, event, "player")
    
    elif event.event_type == "BASE_PROGRESSION_ADVANCED":
        _apply_progression_advanced(new_state, event, "base")
    
    elif event.event_type == "REST_RESOLVED":
        _apply_rest_resolved(new_state, event)
    
    # Phase 7 build event
    elif event.event_type == "BUILD_SELECTED":
        _apply_build_selected(new_state, event)

    # Optional feature event; the feature module owns its local validation.
    elif event.event_type == "ACTOR_CONVERSATION_RESOLVED":
        from ..gameplay.named_actor import apply_actor_conversation_resolved

        try:
            apply_actor_conversation_resolved(new_state, event)
        except Exception as exc:
            raise ReducerError(f"Actor conversation rejected: {exc}") from exc
    
    else:
        raise ReducerError(f"Unknown event type '{event.event_type}'.")
    
    # A time-advancing player event may cause one deterministic off-screen
    # consequence.  It does not emit a second event or change the clock.
    # Phase 7.5 treats the autonomous actor step as a deterministic
    # consequence of the triggering time-advancing event. Separate actor
    # events and atomic multi-event decisions remain deferred.
    if new_state.game_minute > previous_game_minute:
        from ..gameplay.named_actor import apply_named_actor_autonomous_consequence

        apply_named_actor_autonomous_consequence(new_state)

    # Update sequence number
    new_state.event_seq = event.event_seq
    
    # Verify invariants after application
    try:
        check_invariants(new_state)
    except Exception as e:
        raise ReducerError(f"Invariant violation after applying event: {e}")
    
    return new_state


def _apply_time_advanced(state: GameState, event: DomainEvent) -> None:
    """Apply TIME_ADVANCED event to update game_minute."""
    minutes = event.payload.get("minutes", 0)
    
    if minutes < 0:
        raise ReducerError("Time advancement cannot be negative")
    
    # Phase 4: TIME_ADVANCED (WAIT) cannot bypass active hostile encounter
    exp = state.data.get("expedition")
    if exp:
        encounter = exp.get("encounter")
        if encounter and encounter.get("active"):
            raise ReducerError("Cannot WAIT during active hostile encounter")
    
    expected_minute = state.game_minute + minutes
    actual_minute = event.game_minute
    
    if actual_minute != expected_minute:
        raise ReducerError(
            f"Game minute mismatch: expected {expected_minute}, "
            f"got {actual_minute}"
        )
    
    state.game_minute = actual_minute


# Phase 3 expedition events handlers (minimal extension per spec #19)

def _apply_expedition_dropped(state: GameState, event: DomainEvent) -> None:
    """Apply EXPEDITION_DROPPED event."""
    payload = event.payload
    
    # Phase 5: reducer anti-forgery — reject DROP if phase blocks it at decision start
    # Phase 6: base stage >= 1 overrides the phase-window DROP block
    if is_action_blocked_by_phase(state, "DROP"):
        from ..gameplay.progression import get_track_stage
        from ..gameplay.build_choice import build_allows_drop_during_phase_window
        base_stage = get_track_stage(state, "base")
        drop_override = (
            (base_stage is not None and base_stage >= 1)
            or build_allows_drop_during_phase_window(state)
        )
        if not drop_override:
            raise ReducerError("Cannot drop: action blocked by current world phase")
    
    # Verify state preconditions
    if state.data["expedition"]["active"]:
        raise ReducerError("Cannot drop: expedition already active")
    
    if state.data["player"]["location_id"] != state.data["expedition"]["base_location_id"]:
        raise ReducerError("Cannot drop: not at base location")
    
    if state.data["expedition"]["target_searched"]:
        raise ReducerError("Cannot drop: target already searched")
    
    if state.data["player"]["stamina"] < 1:
        raise ReducerError("Cannot drop: insufficient stamina")
    
    # Verify payload matches expected costs
    if payload.get("destination") != state.data["expedition"]["target_location_id"]:
        raise ReducerError(f"Drop destination mismatch: {payload.get('destination')} != {state.data['expedition']['target_location_id']}")
    
    if payload.get("time") != 10:
        raise ReducerError(f"Drop time cost must be 10, got {payload.get('time')}")
    
    if payload.get("stamina_cost") != 1:
        raise ReducerError(f"Drop stamina cost must be 1, got {payload.get('stamina_cost')}")
    
    # Verify game_minute matches
    expected_minute = state.game_minute + 10
    if event.game_minute != expected_minute:
        raise ReducerError(f"Game minute mismatch: expected {expected_minute}, got {event.game_minute}")
    
    # Apply state changes
    state.data["player"]["location_id"] = payload["destination"]
    state.data["expedition"]["active"] = True
    state.data["player"]["stamina"] -= 1
    state.game_minute = expected_minute


def _apply_search_resolved(state: GameState, event: DomainEvent) -> None:
    """Apply SEARCH_RESOLVED event."""
    payload = event.payload
    
    # Verify state preconditions
    if not state.data["expedition"]["active"]:
        raise ReducerError("Cannot search: expedition not active")
    
    if state.data["player"]["location_id"] != state.data["expedition"]["target_location_id"]:
        raise ReducerError("Cannot search: not at target location")
    
    if state.data["expedition"]["target_searched"]:
        raise ReducerError("Cannot search: target already searched")
    
    if state.data["player"]["stamina"] < 2:
        raise ReducerError("Cannot search: insufficient stamina")
    
    # Verify payload loot matches target_loot
    if payload.get("loot_gained") != state.data["expedition"]["target_loot"]:
        raise ReducerError(f"Search loot mismatch: expected {state.data['expedition']['target_loot']}, got {payload.get('loot_gained')}")
    
    # Verify payload time and stamina costs
    if payload.get("time") != 30:
        raise ReducerError(f"Search time cost must be 30, got {payload.get('time')}")
    
    if payload.get("stamina_cost") != 2:
        raise ReducerError(f"Search stamina cost must be 2, got {payload.get('stamina_cost')}")
    
    # Verify game_minute matches
    expected_minute = state.game_minute + 30
    if event.game_minute != expected_minute:
        raise ReducerError(f"Game minute mismatch: expected {expected_minute}, got {event.game_minute}")
    
    # Apply state changes
    state.data["player"]["stamina"] -= 2
    state.game_minute = expected_minute
    
    # Move target_loot to carried_loot
    state.data["expedition"]["carried_loot"] = dict(state.data["expedition"]["target_loot"])
    state.data["expedition"]["target_loot"] = {}
    state.data["expedition"]["target_searched"] = True
    
    # Phase 4: Activate encounter after search (if encounter data exists)
    encounter = state.data["expedition"].get("encounter")
    if encounter is not None:
        encounter["active"] = True


def _apply_expedition_extracted(state: GameState, event: DomainEvent) -> None:
    """Apply EXPEDITION_EXTRACTED event."""
    payload = event.payload
    
    # Verify state preconditions
    if not state.data["expedition"]["active"]:
        raise ReducerError("Cannot extract: expedition not active")
    
    if state.data["player"]["location_id"] != state.data["expedition"]["target_location_id"]:
        raise ReducerError("Cannot extract: not at target location")
    
    # Phase 4: Cannot extract during active hostile encounter
    encounter = state.data["expedition"].get("encounter")
    if encounter and encounter.get("active"):
        raise ReducerError("Cannot extract: hostile encounter active")
    
    # Verify payload carried_loot matches actual carried_loot
    if payload.get("carried_loot") != state.data["expedition"]["carried_loot"]:
        raise ReducerError(f"Extract loot mismatch: expected {state.data['expedition']['carried_loot']}, got {payload.get('carried_loot')}")
    
    # Verify payload time cost
    if payload.get("time") != 15:
        raise ReducerError(f"Extract time cost must be 15, got {payload.get('time')}")
    
    # Verify game_minute matches
    expected_minute = state.game_minute + 15
    if event.game_minute != expected_minute:
        raise ReducerError(f"Game minute mismatch: expected {expected_minute}, got {event.game_minute}")
    
    # Apply state changes
    state.game_minute = expected_minute
    
    # Move carried_loot to inventory
    for resource, qty in state.data["expedition"]["carried_loot"].items():
        if resource in state.data["inventory"]:
            state.data["inventory"][resource] += qty
        else:
            state.data["inventory"][resource] = qty
    
    # Clear carried and deactivate
    state.data["expedition"]["carried_loot"] = {}
    state.data["expedition"]["active"] = False
    state.data["player"]["location_id"] = state.data["expedition"]["base_location_id"]


# Phase 4 risk event handlers

def _apply_combat_resolved(state: GameState, event: DomainEvent) -> None:
    """Apply COMBAT_RESOLVED event (Phase 4 deterministic combat)."""
    payload = event.payload
    exp = state.data["expedition"]
    player = state.data["player"]
    encounter = exp["encounter"]
    
    # Verify preconditions
    if player["hp"] <= 0:
        raise ReducerError("Cannot fight: player is dead")
    
    if not exp["active"]:
        raise ReducerError("Cannot fight: expedition not active")
    
    if player["location_id"] != exp["target_location_id"]:
        raise ReducerError("Cannot fight: player not at target location")
    
    if not encounter["active"]:
        raise ReducerError("Cannot fight: no active encounter")
    
    if encounter["enemy_hp"] <= 0:
        raise ReducerError("Cannot fight: enemy already defeated")
    
    if player["stamina"] < 1:
        raise ReducerError("Cannot fight: insufficient stamina")
    
    # Verify payload costs
    if payload.get("time") != 10:
        raise ReducerError(f"Fight time cost must be 10, got {payload.get('time')}")
    
    if payload.get("stamina_cost") != 1:
        raise ReducerError(f"Fight stamina cost must be 1, got {payload.get('stamina_cost')}")
    
    # Verify game_minute
    expected_minute = state.game_minute + 10
    if event.game_minute != expected_minute:
        raise ReducerError(f"Game minute mismatch: expected {expected_minute}, got {event.game_minute}")
    
    # Verify enemy_id matches
    if payload.get("enemy_id") != encounter["enemy_id"]:
        raise ReducerError(f"Enemy ID mismatch: expected {encounter['enemy_id']}, got {payload.get('enemy_id')}")
    
    # Compute deterministic combat resolution
    player_damage_dealt = player["attack"]
    new_enemy_hp = encounter["enemy_hp"] - player_damage_dealt
    if new_enemy_hp < 0:
        new_enemy_hp = 0
    
    # Enemy retaliates only if it survives
    if new_enemy_hp > 0:
        enemy_damage_dealt = encounter["enemy_attack"]
    else:
        enemy_damage_dealt = 0
    
    new_player_hp = player["hp"] - enemy_damage_dealt
    if new_player_hp < 0:
        new_player_hp = 0
    
    # Verify payload matches engine-computed values (anti-forgery)
    if payload.get("player_damage_dealt") != player_damage_dealt:
        raise ReducerError(
            f"Forged player_damage_dealt: expected {player_damage_dealt}, got {payload.get('player_damage_dealt')}"
        )
    
    if payload.get("enemy_damage_dealt") != enemy_damage_dealt:
        raise ReducerError(
            f"Forged enemy_damage_dealt: expected {enemy_damage_dealt}, got {payload.get('enemy_damage_dealt')}"
        )
    
    if payload.get("enemy_hp_after") != new_enemy_hp:
        raise ReducerError(
            f"Forged enemy_hp_after: expected {new_enemy_hp}, got {payload.get('enemy_hp_after')}"
        )
    
    if payload.get("player_hp_after") != new_player_hp:
        raise ReducerError(
            f"Forged player_hp_after: expected {new_player_hp}, got {payload.get('player_hp_after')}"
        )
    
    # Determine outcome
    if new_player_hp <= 0:
        expected_outcome = "PLAYER_DIED"
    elif new_enemy_hp <= 0:
        expected_outcome = "ENEMY_DEFEATED"
    else:
        expected_outcome = "ONGOING"
    
    if payload.get("outcome") != expected_outcome:
        raise ReducerError(
            f"Forged outcome: expected {expected_outcome}, got {payload.get('outcome')}"
        )
    
    # Apply state changes
    encounter["enemy_hp"] = new_enemy_hp
    player["hp"] = new_player_hp
    player["stamina"] -= 1
    state.game_minute = expected_minute
    
    # Deactivate encounter if enemy defeated
    if new_enemy_hp <= 0:
        encounter["active"] = False


def _apply_expedition_fled(state: GameState, event: DomainEvent) -> None:
    """Apply EXPEDITION_FLED event (Phase 4 flee mechanics)."""
    payload = event.payload
    exp = state.data["expedition"]
    player = state.data["player"]
    
    # Verify preconditions
    if not exp["active"]:
        raise ReducerError("Cannot flee: expedition not active")
    
    if player["location_id"] != exp["target_location_id"]:
        raise ReducerError("Cannot flee: player not at target location")
    
    if not exp["encounter"]["active"]:
        raise ReducerError("Cannot flee: no active encounter")
    
    if player["hp"] <= 0:
        raise ReducerError("Cannot flee: player is dead")
    
    # Verify payload time cost
    if payload.get("time") != 15:
        raise ReducerError(f"Flee time cost must be 15, got {payload.get('time')}")
    
    # Verify game_minute
    expected_minute = state.game_minute + 15
    if event.game_minute != expected_minute:
        raise ReducerError(f"Game minute mismatch: expected {expected_minute}, got {event.game_minute}")
    
    # Apply state changes
    state.game_minute = expected_minute
    
    # Discard carried loot (real sacrifice)
    exp["carried_loot"] = {}
    
    # Clear encounter
    exp["encounter"]["active"] = False
    
    # End expedition, return to base
    exp["active"] = False
    player["location_id"] = exp["base_location_id"]


# Phase 6 progression event handlers

def _apply_progression_advanced(state: GameState, event: DomainEvent, track_id: str) -> None:
    """Apply PLAYER_PROGRESSION_ADVANCED or BASE_PROGRESSION_ADVANCED event."""
    payload = event.payload
    player = state.data["player"]
    exp = state.data["expedition"]
    
    # Preconditions
    if player.get("hp", 1) <= 0:
        raise ReducerError(f"Cannot upgrade {track_id}: player is dead")
    
    if player["location_id"] != exp["base_location_id"]:
        raise ReducerError(f"Cannot upgrade {track_id}: not at base")
    
    if exp["active"]:
        raise ReducerError(f"Cannot upgrade {track_id}: expedition active")
    
    encounter = exp.get("encounter")
    if encounter and encounter.get("active"):
        raise ReducerError(f"Cannot upgrade {track_id}: active encounter")
    
    # Verify progression state
    progression = state.data.get("progression")
    if progression is None:
        raise ReducerError(f"Cannot upgrade {track_id}: progression not enabled")
    
    gates = state.data.get("progression_gates")
    if gates is None:
        raise ReducerError(f"Cannot upgrade {track_id}: progression_gates not configured")
    
    gate = gates.get(track_id)
    if gate is None:
        raise ReducerError(f"Cannot upgrade {track_id}: no gate defined")
    
    current_stage = progression["tracks"].get(track_id)
    if current_stage is None:
        raise ReducerError(f"Cannot upgrade {track_id}: track not found")
    
    # Anti-forgery: verify from_stage matches current
    if payload.get("from_stage") != current_stage:
        raise ReducerError(
            f"Forged from_stage: expected {current_stage}, got {payload.get('from_stage')}"
        )
    
    # Anti-forgery: verify to_stage == from_stage + 1
    expected_to = current_stage + 1
    if payload.get("to_stage") != expected_to:
        raise ReducerError(
            f"Forged to_stage: expected {expected_to}, got {payload.get('to_stage')}"
        )
    
    # Anti-forgery: verify gate from_stage matches
    if current_stage != gate["from_stage"]:
        raise ReducerError(f"Cannot upgrade {track_id}: gate not applicable at stage {current_stage}")
    
    # Anti-forgery: verify resource cost matches gate
    expected_cost = gate["cost"]
    if payload.get("resource_cost") != expected_cost:
        raise ReducerError(
            f"Forged resource_cost: expected {expected_cost}, got {payload.get('resource_cost')}"
        )
    
    # Verify resources available
    inventory = state.data.get("inventory", {})
    for resource, qty in expected_cost.items():
        if inventory.get(resource, 0) < qty:
            raise ReducerError(f"Cannot upgrade {track_id}: insufficient {resource}")
    
    # Verify time cost
    if payload.get("time") != 5:
        raise ReducerError(f"Upgrade time cost must be 5, got {payload.get('time')}")
    
    expected_minute = state.game_minute + 5
    if event.game_minute != expected_minute:
        raise ReducerError(f"Game minute mismatch: expected {expected_minute}, got {event.game_minute}")
    
    # Apply: consume resources + advance track
    for resource, qty in expected_cost.items():
        inventory[resource] -= qty
        if inventory[resource] == 0:
            del inventory[resource]
    
    progression["tracks"][track_id] = expected_to
    state.game_minute = expected_minute


def _apply_rest_resolved(state: GameState, event: DomainEvent) -> None:
    """Apply REST_RESOLVED event."""
    payload = event.payload
    player = state.data["player"]
    exp = state.data["expedition"]
    
    # Preconditions
    if player.get("hp", 1) <= 0:
        raise ReducerError("Cannot rest: player is dead")
    
    encounter = exp.get("encounter")
    if encounter and encounter.get("active"):
        raise ReducerError("Cannot rest: active encounter")
    
    # Verify player progression >= 1
    progression = state.data.get("progression")
    if progression is None:
        raise ReducerError("Cannot rest: progression not enabled")
    
    player_stage = progression["tracks"].get("player", 0)
    if player_stage < 1:
        raise ReducerError("Cannot rest: player track < 1")
    
    # Phase 7: two valid location contexts
    # A: inactive expedition + at base
    # B: the selected target-rest build + active expedition + at target
    from ..gameplay.build_choice import build_allows_rest_at_target, get_rest_duration
    
    at_base_inactive = (
        player["location_id"] == exp["base_location_id"] and not exp["active"]
    )
    selected_build_at_target = (
        build_allows_rest_at_target(state)
        and exp["active"]
        and player["location_id"] == exp["target_location_id"]
    )

    if not at_base_inactive and not selected_build_at_target:
        raise ReducerError("Cannot rest: invalid location context")
    
    # Verify stamina not already full
    stamina = player["stamina"]
    max_stamina = player["max_stamina"]
    if stamina >= max_stamina:
        raise ReducerError("Cannot rest: stamina already full")
    
    # Anti-forgery: verify stamina_before
    if payload.get("stamina_before") != stamina:
        raise ReducerError(
            f"Forged stamina_before: expected {stamina}, got {payload.get('stamina_before')}"
        )
    
    # Anti-forgery: verify stamina_after == max_stamina
    if payload.get("stamina_after") != max_stamina:
        raise ReducerError(
            f"Forged stamina_after: expected {max_stamina}, got {payload.get('stamina_after')}"
        )
    
    # Verify the authoritative selected-build REST duration.
    expected_time = get_rest_duration(state)
    if payload.get("time") != expected_time:
        raise ReducerError(f"Rest time cost must be {expected_time}, got {payload.get('time')}")
    
    expected_minute = state.game_minute + expected_time
    if event.game_minute != expected_minute:
        raise ReducerError(f"Game minute mismatch: expected {expected_minute}, got {event.game_minute}")
    
    # Apply
    player["stamina"] = max_stamina
    state.game_minute = expected_minute


# Phase 7 build selection handler

def _apply_build_selected(state: GameState, event: DomainEvent) -> None:
    """Apply BUILD_SELECTED event."""
    payload = event.payload
    player = state.data["player"]
    exp = state.data["expedition"]
    
    # Preconditions
    if player.get("hp", 1) <= 0:
        raise ReducerError("Cannot choose build: player is dead")
    
    if player["location_id"] != exp["base_location_id"]:
        raise ReducerError("Cannot choose build: not at base")
    
    if exp["active"]:
        raise ReducerError("Cannot choose build: expedition active")
    
    encounter = exp.get("encounter")
    if encounter and encounter.get("active"):
        raise ReducerError("Cannot choose build: active encounter")
    
    # Verify build feature configured
    build_choice = state.data.get("build_choice")
    if build_choice is None:
        raise ReducerError("Cannot choose build: build_choice not configured")
    
    build = state.data.get("build")
    if build is None:
        raise ReducerError("Cannot choose build: build not configured")
    
    # Verify not already selected (permanence)
    if build.get("selected") is not None:
        raise ReducerError("Cannot choose build: already selected")
    
    # Verify trigger progression
    required_track = build_choice["required_track"]
    required_stage = build_choice["required_stage"]
    
    progression = state.data.get("progression")
    if progression is None:
        raise ReducerError("Cannot choose build: progression not enabled")
    
    current_stage = progression["tracks"].get(required_track)
    if current_stage is None or current_stage < required_stage:
        raise ReducerError("Cannot choose build: trigger progression not met")
    
    # Verify build_id is a configured candidate
    build_id = payload.get("build_id")
    candidates = build_choice.get("candidates", [])
    if build_id not in candidates:
        raise ReducerError(f"Cannot choose build: '{build_id}' not in candidates")
    
    # Verify time cost
    if payload.get("time") != 1:
        raise ReducerError(f"Build choice time cost must be 1, got {payload.get('time')}")
    
    expected_minute = state.game_minute + 1
    if event.game_minute != expected_minute:
        raise ReducerError(f"Game minute mismatch: expected {expected_minute}, got {event.game_minute}")
    
    # Apply
    build["selected"] = build_id
    state.game_minute = expected_minute
