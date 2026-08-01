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
    
    # Phase 4 combat invariants
    if state.data.get("player") and "hp" in state.data.get("player", {}):
        _check_combat_invariants(state)
    
    # Phase 5 phase-cycle configuration invariants
    if state.data.get("phase_cycle") is not None:
        _check_phase_cycle_invariants(state)
    
    # Phase 6 progression invariants
    has_progression = state.data.get("progression") is not None
    has_gates = state.data.get("progression_gates") is not None
    if has_progression or has_gates:
        _check_progression_invariants(state, has_progression, has_gates)
    
    # Phase 7 build choice invariants
    has_build_choice = state.data.get("build_choice") is not None
    has_build = state.data.get("build") is not None
    if has_build_choice or has_build:
        _check_build_invariants(state, has_build_choice, has_build)

    # Phase 7.5 optional named-actor feature invariants.  The feature module
    # owns its local WorldPack contract; Core only invokes the boundary check.
    if any(key in state.data for key in ("named_actor", "world_facts", "player_knowledge")):
        from ..gameplay.named_actor import validate_named_actor_state

        try:
            validate_named_actor_state(state)
        except Exception as exc:
            raise InvariantError(f"Named actor feature invariant: {exc}") from exc


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


def _check_combat_invariants(state: "GameState") -> None:
    """Verify Phase 4 combat-specific invariants."""
    player = state.data.get("player", {})
    exp = state.data.get("expedition", {})
    
    # HP must be int, not bool
    hp = player.get("hp")
    if hp is not None:
        if isinstance(hp, bool):
            raise InvariantError("hp must be int, not bool")
        if not isinstance(hp, int):
            raise InvariantError(f"hp must be int, got {type(hp).__name__}")
    
    # max_hp must be positive int, not bool
    max_hp = player.get("max_hp")
    if max_hp is not None:
        if isinstance(max_hp, bool):
            raise InvariantError("max_hp must be int, not bool")
        if not isinstance(max_hp, int):
            raise InvariantError(f"max_hp must be int, got {type(max_hp).__name__}")
        if max_hp <= 0:
            raise InvariantError(f"max_hp must be positive, got {max_hp}")
    
    # HP range: 0 <= hp <= max_hp
    if hp is not None and max_hp is not None:
        if hp < 0:
            raise InvariantError(f"hp must be non-negative, got {hp}")
        if hp > max_hp:
            raise InvariantError(f"hp must be <= max_hp, got {hp} > {max_hp}")
    
    # attack must be non-negative int, not bool
    attack = player.get("attack")
    if attack is not None:
        if isinstance(attack, bool):
            raise InvariantError("attack must be int, not bool")
        if not isinstance(attack, int):
            raise InvariantError(f"attack must be int, got {type(attack).__name__}")
        if attack < 0:
            raise InvariantError(f"attack must be non-negative, got {attack}")
    
    # Encounter invariants
    encounter = exp.get("encounter")
    if encounter is not None:
        enemy_hp = encounter.get("enemy_hp")
        enemy_max_hp = encounter.get("enemy_max_hp")
        enemy_attack = encounter.get("enemy_attack")
        
        # enemy_hp must be int, not bool, and non-negative
        if enemy_hp is not None:
            if isinstance(enemy_hp, bool):
                raise InvariantError("enemy_hp must be int, not bool")
            if not isinstance(enemy_hp, int):
                raise InvariantError(f"enemy_hp must be int, got {type(enemy_hp).__name__}")
            if enemy_hp < 0:
                raise InvariantError(f"enemy_hp must be non-negative, got {enemy_hp}")
        
        # enemy_max_hp must be positive int
        if enemy_max_hp is not None:
            if isinstance(enemy_max_hp, bool):
                raise InvariantError("enemy_max_hp must be int, not bool")
            if not isinstance(enemy_max_hp, int):
                raise InvariantError(f"enemy_max_hp must be int, got {type(enemy_max_hp).__name__}")
            if enemy_max_hp <= 0:
                raise InvariantError(f"enemy_max_hp must be positive, got {enemy_max_hp}")
        
        # enemy_attack must be non-negative int
        if enemy_attack is not None:
            if isinstance(enemy_attack, bool):
                raise InvariantError("enemy_attack must be int, not bool")
            if not isinstance(enemy_attack, int):
                raise InvariantError(f"enemy_attack must be int, got {type(enemy_attack).__name__}")
            if enemy_attack < 0:
                raise InvariantError(f"enemy_attack must be non-negative, got {enemy_attack}")
        
        # Active encounter cannot have dead enemy
        if encounter.get("active") and enemy_hp is not None and enemy_hp <= 0:
            raise InvariantError("Active encounter cannot have dead enemy (enemy_hp <= 0)")
        
        # Active encounter consistency: requires active expedition and player at target
        if encounter.get("active"):
            if not exp.get("active"):
                raise InvariantError("Active encounter requires active expedition")
            player_location = player.get("location_id")
            target_location = exp.get("target_location_id")
            if player_location != target_location:
                raise InvariantError(
                    f"Active encounter requires player at target {target_location}, got {player_location}"
                )


def _check_phase_cycle_invariants(state: "GameState") -> None:
    """Verify Phase 5 phase-cycle configuration validity."""
    config = state.data["phase_cycle"]
    
    if not isinstance(config, dict):
        raise InvariantError(f"phase_cycle must be dict, got {type(config).__name__}")
    
    # cycle_minutes: positive int, not bool
    cycle = config.get("cycle_minutes")
    if isinstance(cycle, bool):
        raise InvariantError("phase_cycle.cycle_minutes must be int, not bool")
    if not isinstance(cycle, int):
        raise InvariantError(f"phase_cycle.cycle_minutes must be int, got {type(cycle).__name__}")
    if cycle <= 0:
        raise InvariantError(f"phase_cycle.cycle_minutes must be positive, got {cycle}")
    
    # boundary_minute: positive int, not bool, < cycle_minutes
    boundary = config.get("boundary_minute")
    if isinstance(boundary, bool):
        raise InvariantError("phase_cycle.boundary_minute must be int, not bool")
    if not isinstance(boundary, int):
        raise InvariantError(f"phase_cycle.boundary_minute must be int, got {type(boundary).__name__}")
    if boundary <= 0:
        raise InvariantError(f"phase_cycle.boundary_minute must be positive, got {boundary}")
    if boundary >= cycle:
        raise InvariantError(
            f"phase_cycle.boundary_minute must be < cycle_minutes, got {boundary} >= {cycle}"
        )
    
    # phase_before / phase_after: non-empty strings, distinct
    phase_before = config.get("phase_before")
    if not isinstance(phase_before, str) or not phase_before:
        raise InvariantError("phase_cycle.phase_before must be non-empty string")
    
    phase_after = config.get("phase_after")
    if not isinstance(phase_after, str) or not phase_after:
        raise InvariantError("phase_cycle.phase_after must be non-empty string")
    
    if phase_before == phase_after:
        raise InvariantError("phase_cycle.phase_before and phase_after must differ")
    
    # blocked_actions_by_phase: mapping of str -> list of str
    blocked = config.get("blocked_actions_by_phase")
    if blocked is not None:
        if not isinstance(blocked, dict):
            raise InvariantError(
                f"phase_cycle.blocked_actions_by_phase must be mapping, got {type(blocked).__name__}"
            )
        for phase_key, action_list in blocked.items():
            if not isinstance(phase_key, str):
                raise InvariantError(
                    f"blocked_actions_by_phase key must be string, got {type(phase_key).__name__}"
                )
            if not isinstance(action_list, (list, tuple)):
                raise InvariantError(
                    f"blocked_actions_by_phase['{phase_key}'] must be list, got {type(action_list).__name__}"
                )
            for action in action_list:
                if not isinstance(action, str):
                    raise InvariantError(
                        f"blocked_actions_by_phase['{phase_key}'] entries must be string, got {type(action).__name__}"
                    )


def _check_progression_invariants(state: "GameState", has_progression: bool, has_gates: bool) -> None:
    """Verify Phase 6 progression configuration validity."""
    # Both must exist together
    if has_progression and not has_gates:
        raise InvariantError("progression exists without progression_gates")
    if has_gates and not has_progression:
        raise InvariantError("progression_gates exists without progression")
    
    progression = state.data["progression"]
    gates = state.data["progression_gates"]
    
    if not isinstance(progression, dict):
        raise InvariantError(f"progression must be dict, got {type(progression).__name__}")
    
    tracks = progression.get("tracks")
    if not isinstance(tracks, dict):
        raise InvariantError(f"progression.tracks must be dict, got {type(tracks).__name__}")
    
    for track_id, stage in tracks.items():
        if not isinstance(track_id, str) or not track_id:
            raise InvariantError("progression track id must be non-empty string")
        if isinstance(stage, bool):
            raise InvariantError(f"progression.tracks['{track_id}'] must be int, not bool")
        if not isinstance(stage, int):
            raise InvariantError(f"progression.tracks['{track_id}'] must be int, got {type(stage).__name__}")
        if stage < 0:
            raise InvariantError(f"progression.tracks['{track_id}'] must be >= 0, got {stage}")
    
    if not isinstance(gates, dict):
        raise InvariantError(f"progression_gates must be dict, got {type(gates).__name__}")
    
    for track_id, gate in gates.items():
        if not isinstance(track_id, str) or not track_id:
            raise InvariantError("progression_gates key must be non-empty string")
        if track_id not in tracks:
            raise InvariantError(f"progression_gates['{track_id}'] refers to nonexistent track")
        if not isinstance(gate, dict):
            raise InvariantError(f"progression_gates['{track_id}'] must be dict")
        
        from_stage = gate.get("from_stage")
        if isinstance(from_stage, bool) or not isinstance(from_stage, int) or from_stage < 0:
            raise InvariantError(f"gate '{track_id}' from_stage must be int >= 0")
        
        to_stage = gate.get("to_stage")
        if isinstance(to_stage, bool) or not isinstance(to_stage, int):
            raise InvariantError(f"gate '{track_id}' to_stage must be int")
        if to_stage != from_stage + 1:
            raise InvariantError(f"gate '{track_id}' to_stage must be from_stage + 1")
        
        cost = gate.get("cost")
        if not isinstance(cost, dict) or not cost:
            raise InvariantError(f"gate '{track_id}' cost must be non-empty mapping")
        
        for resource, qty in cost.items():
            if not isinstance(resource, str) or not resource:
                raise InvariantError(f"gate '{track_id}' cost resource must be non-empty string")
            if isinstance(qty, bool):
                raise InvariantError(f"gate '{track_id}' cost['{resource}'] must be int, not bool")
            if not isinstance(qty, int) or qty <= 0:
                raise InvariantError(f"gate '{track_id}' cost['{resource}'] must be positive int")


def _check_build_invariants(state: "GameState", has_build_choice: bool, has_build: bool) -> None:
    """Verify Phase 7 build choice configuration validity."""
    from ..gameplay.build_choice import SUPPORTED_BUILDS
    
    if has_build_choice and not has_build:
        raise InvariantError("build_choice exists without build")
    if has_build and not has_build_choice:
        raise InvariantError("build exists without build_choice")
    
    config = state.data["build_choice"]
    build = state.data["build"]
    
    if not isinstance(config, dict):
        raise InvariantError(f"build_choice must be dict, got {type(config).__name__}")
    
    # required_track
    required_track = config.get("required_track")
    if not isinstance(required_track, str) or not required_track:
        raise InvariantError("build_choice.required_track must be non-empty string")
    
    # required_track must refer to existing progression track
    progression = state.data.get("progression")
    if progression is not None:
        tracks = progression.get("tracks", {})
        if required_track not in tracks:
            raise InvariantError(f"build_choice.required_track '{required_track}' not in progression tracks")
    
    # required_stage
    required_stage = config.get("required_stage")
    if isinstance(required_stage, bool):
        raise InvariantError("build_choice.required_stage must be int, not bool")
    if not isinstance(required_stage, int) or required_stage < 0:
        raise InvariantError(f"build_choice.required_stage must be int >= 0, got {required_stage}")
    
    # candidates
    candidates = config.get("candidates")
    if not isinstance(candidates, (list, tuple)):
        raise InvariantError(f"build_choice.candidates must be list, got {type(candidates).__name__}")
    if len(candidates) < 2:
        raise InvariantError(f"build_choice.candidates must have >= 2 entries, got {len(candidates)}")
    
    seen = set()
    for c in candidates:
        if not isinstance(c, str) or not c:
            raise InvariantError("build_choice candidate must be non-empty string")
        if c in seen:
            raise InvariantError(f"duplicate build candidate '{c}'")
        seen.add(c)
        if c not in SUPPORTED_BUILDS:
            raise InvariantError(f"unsupported build candidate '{c}'")
    
    # build mapping
    if not isinstance(build, dict):
        raise InvariantError(f"build must be dict, got {type(build).__name__}")
    
    selected = build.get("selected")
    if selected is not None:
        if not isinstance(selected, str):
            raise InvariantError(f"build.selected must be None or string, got {type(selected).__name__}")
        if selected not in candidates:
            raise InvariantError(f"build.selected '{selected}' not in candidates")
        # If selected, trigger must already be satisfied
        if progression is not None:
            current_stage = progression.get("tracks", {}).get(required_track)
            if current_stage is None or current_stage < required_stage:
                raise InvariantError("build.selected set but trigger progression not satisfied")
