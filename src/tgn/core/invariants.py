"""Core invariant checks for game state validation."""

from __future__ import annotations


class InvariantError(Exception):
    """Raised when a game state invariant is violated."""
    pass


def check_invariants(state: "GameState") -> None:
    """
    Verify core game state invariants.
    
    Phase 1 checks truly core invariants, not gameplay-specific ones.
    Phase 3 adds expedition-specific invariants.
    """
    # Check non-negative counters
    if state.event_seq < 0:
        raise InvariantError(f"event_seq must be non-negative, got {state.event_seq}")
    
    if state.decision_seq < 0:
        raise InvariantError(
            f"decision_seq must be non-negative, got {state.decision_seq}"
        )
    
    if state.game_minute < 0:
        raise InvariantError(f"game_minute must be non-negative, got {state.game_minute}")
    
    # Verify schema_version
    if state.schema_version != 1:
        raise InvariantError(
            f"Unsupported schema version: {state.schema_version} "
            "(only version 1 supported)"
        )
    
    # Verify state is canonicalizable (no NaN/Infinity)
    from .hashing import verify_canonicalizability
    
    try:
        verify_canonicalizability(state.__dict__)
    except Exception as e:
        raise InvariantError(f"State contains non-canonical values: {e}")
    
    # Optional: check data dict structure (should be serializable)
    if not isinstance(state.data, dict):
        raise InvariantError(f"data field must be dict, got {type(state.data)}")
    
    # Phase 3 expedition invariants
    if state.data.get("expedition"):
        _check_expedition_invariants(state)


def _check_expedition_invariants(state: "GameState") -> None:
    """Verify Phase 3 expedition-specific invariants."""
    exp = state.data.get("expedition", {})
    player = state.data.get("player", {})
    
    # Stamina must be int, not bool
    stamina = player.get("stamina")
    if stamina is not None:
        if isinstance(stamina, bool):
            raise InvariantError("stamina must be int, not bool")
        if not isinstance(stamina, int):
            raise InvariantError(f"stamina must be int, got {type(stamina).__name__}")
    
    # max_stamina must be positive int, not bool
    max_stamina = player.get("max_stamina")
    if max_stamina is not None:
        if isinstance(max_stamina, bool):
            raise InvariantError("max_stamina must be int, not bool")
        if not isinstance(max_stamina, int):
            raise InvariantError(f"max_stamina must be int, got {type(max_stamina).__name__}")
        if max_stamina <= 0:
            raise InvariantError(f"max_stamina must be positive, got {max_stamina}")
    
    # stamina must be in valid range
    if stamina is not None and max_stamina is not None:
        if stamina < 0:
            raise InvariantError(f"stamina must be non-negative, got {stamina}")
        if stamina > max_stamina:
            raise InvariantError(f"stamina must be <= max_stamina, got {stamina} > {max_stamina}")
    
    # Check loot containers
    # inventory is in top-level data, target_loot and carried_loot are in expedition
    inventory = state.data.get("inventory")
    if inventory is not None:
        if not isinstance(inventory, dict):
            raise InvariantError(f"inventory must be dict, got {type(inventory).__name__}")
        
        for resource, qty in inventory.items():
            if not isinstance(resource, str):
                raise InvariantError(f"inventory resource ID must be string, got {type(resource).__name__}")
            if isinstance(qty, bool):
                raise InvariantError(f"inventory[{resource}] must be int, not bool")
            if not isinstance(qty, int):
                raise InvariantError(f"inventory[{resource}] must be int, got {type(qty).__name__}")
            if qty < 0:
                raise InvariantError(f"inventory[{resource}] must be non-negative, got {qty}")
    
    # target_loot and carried_loot are in expedition
    for container_name in ["target_loot", "carried_loot"]:
        container = exp.get(container_name)
        if container is not None:
            if not isinstance(container, dict):
                raise InvariantError(f"{container_name} must be dict, got {type(container).__name__}")
            
            for resource, qty in container.items():
                if not isinstance(resource, str):
                    raise InvariantError(f"{container_name} resource ID must be string, got {type(resource).__name__}")
                if isinstance(qty, bool):
                    raise InvariantError(f"{container_name}[{resource}] must be int, not bool")
                if not isinstance(qty, int):
                    raise InvariantError(f"{container_name}[{resource}] must be int, got {type(qty).__name__}")
                if qty < 0:
                    raise InvariantError(f"{container_name}[{resource}] must be non-negative, got {qty}")
    
    # Location consistency
    active = exp.get("active")
    if active is not None:
        location_id = player.get("location_id")
        base_location_id = exp.get("base_location_id")
        target_location_id = exp.get("target_location_id")
        
        if not active:
            # Not on expedition: must be at base
            if location_id != base_location_id:
                raise InvariantError(f"Inactive expedition: player must be at base {base_location_id}, got {location_id}")
            
            # Not on expedition: carried_loot must be empty
            carried_loot = exp.get("carried_loot")
            if carried_loot and any(qty > 0 for qty in carried_loot.values()):
                raise InvariantError("Inactive expedition: carried_loot must be empty")
        
        else:
            # On expedition: must be at target location
            if location_id != target_location_id:
                raise InvariantError(f"Active expedition: player must be at target {target_location_id}, got {location_id}")
    
    # Searched consistency
    target_searched = exp.get("target_searched")
    if target_searched:
        # If searched, target_loot must be empty
        target_loot = exp.get("target_loot")
        if target_loot and any(qty > 0 for qty in target_loot.values()):
            raise InvariantError("Target already searched: target_loot must be empty")
