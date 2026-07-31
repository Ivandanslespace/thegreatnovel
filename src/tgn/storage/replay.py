"""Replay and verification from events."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from ..core.hashing import canonical_json, state_hash
from ..core.models import DomainEvent, GameState


@dataclass
class ReplayResult:
    """Result of a replay operation."""
    success: bool
    final_state: dict[str, Any] | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None
    failed_event_seq: int | None = None
    error_message: str | None = None
    states_replayed: int = 0


def replay_campaign(
    initial_state: dict[str, Any],
    events: list[DomainEvent],
    state_at_each_step: bool = False,
) -> ReplayResult:
    """
    Replay a sequence of events from an initial state.
    
    This is a READ-ONLY operation that does not modify the database.
    
    Args:
        initial_state: Starting game state as dictionary OR GameState object
        events: List of events to apply in sequence
        state_at_each_step: If True, track all intermediate states (memory intensive)
        
    Returns:
        ReplayResult with final state or error details
    """
    from ..core.reducer import reduce_event
    from ..core.models import GameState
    
    # Convert dict to GameState if needed
    if isinstance(initial_state, dict):
        current_state = GameState(
            schema_version=initial_state.get("schema_version", 1),
            event_seq=initial_state.get("event_seq", 0),
            decision_seq=initial_state.get("decision_seq", 0),
            game_minute=initial_state.get("game_minute", 0),
            seed=initial_state.get("seed", ""),
            data=initial_state.get("data", {}),
        )
    else:
        current_state = copy.deepcopy(initial_state)
    
    history = []
    
    if state_at_each_step:
        history = [copy.deepcopy(current_state)]
    
    for event in events:
        try:
            # Convert dict back to object if needed
            if isinstance(event, dict):
                event = DomainEvent.from_dict(event)
            
            current_state = reduce_event(current_state, event)
            
            if state_at_each_step:
                history.append(copy.deepcopy(current_state))
                
        except Exception as e:
            failed_seq = getattr(event, 'event_seq', 0) if hasattr(event, 'event_seq') else 0
            return ReplayResult(
                success=False,
                final_state=None,
                expected_hash=None,
                actual_hash=None,
                failed_event_seq=failed_seq,
                error_message=str(e),
                states_replayed=len(history),
            )
    
    # Calculate final hash
    if isinstance(current_state, GameState):
        final_hash = state_hash(current_state.__dict__)
        final_state_dict = current_state.__dict__
    else:
        final_hash = state_hash(current_state)
        final_state_dict = current_state
    
    result = ReplayResult(
        success=True,
        final_state=final_state_dict,
        expected_hash=final_hash,
        actual_hash=final_hash,
        states_replayed=len(events),
    )
    
    if state_at_each_step:
        result.history = history
    
    return result


def verify_replay(
    initial_state: dict[str, Any],
    events: list[DomainEvent],
    expected_final_hash: str,
) -> ReplayResult:
    """
    Verify that replay produces expected hash.
    
    This is used to detect corruption in persisted events or states.
    
    Args:
        initial_state: Starting game state
        events: Events to replay
        expected_final_hash: Expected SHA-256 hash of final state
        
    Returns:
        ReplayResult indicating whether replay matched expected hash
    """
    result = replay_campaign(initial_state, events, state_at_each_step=True)
    
    if not result.success:
        return result
    
    result.expected_hash = expected_final_hash
    result.actual_hash = result.final_hash if hasattr(result, 'final_hash') else None
    
    if result.expected_hash != result.actual_hash:
        result.success = False
        result.error_message = f"Hash mismatch: expected {result.expected_hash[:16]}..., got {result.actual_hash[:16]}..."
    
    return result
