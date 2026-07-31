"""Core invariant checks for game state validation."""

from __future__ import annotations


class InvariantError(Exception):
    """Raised when a game state invariant is violated."""
    pass


def check_invariants(state: "GameState") -> None:
    """
    Verify core game state invariants.
    
    Phase 1 only checks truly core invariants, not gameplay-specific ones.
    Gameplay rules (HP >= 0, inventory >= 0, etc.) will be added by world packs.
    
    Checks:
    - schema_version is valid
    - event_seq >= 0
    - decision_seq >= 0
    - game_minute >= 0
    - State can be serialized to canonical JSON
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
