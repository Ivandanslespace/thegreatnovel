"""Pure reducer function to apply events to game state."""

from __future__ import annotations

import copy
from typing import Any

from .hashing import state_hash
from .invariants import check_invariants
from .models import DomainEvent, GameState


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
    else:
        raise ReducerError(f"Unknown event type '{event.event_type}'. Phase 1 only supports 'TIME_ADVANCED'.")
    
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
    
    expected_minute = state.game_minute + minutes
    actual_minute = event.game_minute
    
    if actual_minute != expected_minute:
        raise ReducerError(
            f"Game minute mismatch: expected {expected_minute}, "
            f"got {actual_minute}"
        )
    
    state.game_minute = actual_minute
