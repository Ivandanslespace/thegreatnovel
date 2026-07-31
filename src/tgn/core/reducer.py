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
    
    elif event.event_type == "EXPEDITION_FLED":
        _apply_expedition_fled(new_state, event)
    
    else:
        raise ReducerError(f"Unknown event type '{event.event_type}'.")
    
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
    if is_action_blocked_by_phase(state, "DROP"):
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
