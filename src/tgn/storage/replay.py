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
        initial_state: Starting game state as dictionary
        events: Events to replay
        expected_final_hash: Expected SHA-256 hash of final state
        
    Returns:
        ReplayResult indicating whether replay matched expected hash
    """
    from .event_store import EventStore
    
    # Perform basic replay first
    result = replay_campaign(initial_state, events, state_at_each_step=True)
    
    if not result.success:
        return result
    
    # Now compare hashes
    result.expected_hash = expected_final_hash
    
    if result.expected_hash != result.actual_hash:
        result.success = False
        result.error_message = f"Hash mismatch: expected {result.expected_hash[:16]}..., got {result.actual_hash[:16]}..."
    
    return result


def verify_persistence_integrity(campaign_id: str, db_path: str | Path) -> ReplayResult:
    """
    Full verification of campaign persistence integrity.
    
    Verifies:
    - Initial state/hash match
    - Each event's state_hash_before/after are correct
    - Latest snapshot matches final state
    """
    store = EventStore(db_path)
    
    try:
        # Get campaign metadata
        record = store.get_campaign(campaign_id)
        if record is None:
            return ReplayResult(
                success=False,
                error_message=f"Campaign '{campaign_id}' not found",
            )
        
        # Verify initial state
        initial_state = json.loads(record.initial_state_json)
        if state_hash(initial_state) != record.initial_state_hash:
            return ReplayResult(
                success=False,
                error_message="Initial state hash mismatch with stored metadata",
            )
        
        # Get all events and verify step-by-step
        events = store.all_events(campaign_id)
        
        if not events:
            return ReplayResult(
                success=True,
                final_state=initial_state,
                expected_hash=record.initial_state_hash,
                actual_hash=record.initial_state_hash,
            )
        
        current_state = initial_state
        
        for event_dict in events:
            event_seq = event_dict["event_seq"]
            
            # Check before-hash
            expected_before_hash = event_dict["state_hash_before"]
            actual_before_hash = state_hash(current_state)
            
            if expected_before_hash != actual_before_hash:
                return ReplayResult(
                    success=False,
                    failed_event_seq=event_seq,
                    error_message=f"Event {event_seq}: state_hash_before ({actual_before_hash[:16]}...) doesn't match stored ({expected_before_hash[:16]}...)",
                )
            
            # Apply event to get next state
            domain_event = DomainEvent.from_dict(event_dict)
            
            # For Phase 1, only TIME_ADVANCED is valid
            if domain_event.event_type == "TIME_ADVANCED":
                minutes = domain_event.payload.get("minutes", 0)
                expected_next_minute = current_state.get("game_minute", 0) + minutes
                
                if domain_event.game_minute != expected_next_minute:
                    return ReplayResult(
                        success=False,
                        failed_event_seq=event_seq,
                        error_message=f"Event {event_seq}: game_minute calculation incorrect",
                    )
                
                # Create new state
                current_state = current_state.copy()
                current_state["event_seq"] = event_seq
                current_state["game_minute"] = domain_event.game_minute
            
            # Check after-hash
            expected_after_hash = event_dict["state_hash_after"]
            actual_after_hash = state_hash(current_state)
            
            if expected_after_hash != actual_after_hash:
                return ReplayResult(
                    success=False,
                    failed_event_seq=event_seq,
                    error_message=f"Event {event_seq}: state_hash_after ({actual_after_hash[:16]}...) doesn't match stored ({expected_after_hash[:16]}...)",
                )
        
        # Final verification: latest snapshot must match final state
        snapshot = store.latest_snapshot(campaign_id)
        if snapshot:
            # Parse and hash the snapshot state
            from json import loads
            snapshot_state = loads(snapshot["state_json"])
            snapshot_hash = snapshot["state_hash"]
            
            # Both should be identical (snapshot IS the final state)
            final_state_hash = state_hash(current_state)
            
            if snapshot_hash != final_state_hash:
                return ReplayResult(
                    success=False,
                    error_message=f"Final state hash ({final_state_hash[:16]}...) doesn't match snapshot hash ({snapshot_hash[:16]}...)",
                )
            
            # Also verify snapshot hash against its own content
            snapshot_content_hash = state_hash(snapshot_state)
            if snapshot_hash != snapshot_content_hash:
                return ReplayResult(
                    success=False,
                    error_message=f"Snapshot hash ({snapshot_hash[:16]}...) doesn't match its own content hash ({snapshot_content_hash[:16]}...)",
                )
        
        return ReplayResult(
            success=True,
            final_state=current_state,
            expected_hash=final_state_hash if 'final_state_hash' in locals() else None,
            actual_hash=final_state_hash if 'final_state_hash' in locals() else None,
        )
    
    finally:
        store.close()
