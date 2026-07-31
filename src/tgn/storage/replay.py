"""Replay and verification from events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.hashing import state_hash
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


def replay_events(
    initial_state: GameState,
    events: list[DomainEvent],
    state_at_each_step: bool = False,
) -> ReplayResult:
    """
    Pure replay: apply DomainEvents to a GameState.
    
    This is the core capability used by:
    - verify_replay()
    - Autoplay simulation
    - Branch comparison
    - Scenario replay
    
    Args:
        initial_state: Starting GameState (will be deep copied)
        events: Sequence of DomainEvent objects
        state_at_each_step: If True, track all intermediate states
        
    Returns:
        ReplayResult with final state or error details
    """
    from copy import deepcopy
    
    # Deep copy initial state
    current_state = deepcopy(initial_state)
    
    history = []
    if state_at_each_step:
        history = [current_state.__dict__.copy()]
    
    # Track successful reductions separately from history
    processed_count = 0
    
    for i, event in enumerate(events):
        try:
            # Apply event using ONLY the reducer - no duplicate logic
            from ..core.reducer import reduce_event
            
            current_state = reduce_event(current_state, event)
            
            if state_at_each_step:
                history.append(current_state.__dict__.copy())
            
            # Increment count only after successful reduction
            processed_count += 1
                
        except Exception as e:
            return ReplayResult(
                success=False,
                final_state=None,
                expected_hash=None,
                actual_hash=None,
                failed_event_seq=event.event_seq,
                error_message=str(e),
                states_replayed=processed_count,  # Number of events successfully reduced
            )
    
    # Calculate final hash
    from ..core.hashing import state_hash
    final_hash = state_hash(current_state.__dict__)
    final_dict = current_state.__dict__
    
    result = ReplayResult(
        success=True,
        final_state=final_dict,
        expected_hash=final_hash,
        actual_hash=final_hash,
        states_replayed=processed_count,  # Always >= 0
    )
    
    if state_at_each_step:
        result.history = history
    
    return result


def record_to_domain_event(record: dict[str, Any]) -> DomainEvent:
    """Convert persisted event record to DomainEvent.
    
    Persisted records contain extra fields (campaign_id, state_hash_*) that are not part
    of the domain event. This strips those away.
    """
    return DomainEvent(
        event_id=record["event_id"],
        event_seq=record["event_seq"],
        decision_seq=record["decision_seq"],
        game_minute=record["game_minute"],
        event_type=record["event_type"],
        actor_id=record.get("actor_id"),
        action_id=record.get("action_id"),
        causation_id=record.get("causation_id"),
        correlation_id=record.get("correlation_id"),
        payload=record["payload"],
        created_at=record.get("created_at"),
    )


def verify_persistence_integrity(campaign_id: str, db_path: str | Path) -> ReplayResult:
    """
    Full verification of campaign persistence integrity.
    
    Verifies:
    - Initial state/hash match
    - Each event's state_hash_before/after are correct
    - Latest snapshot matches final state
    
    Uses ONLY the public reducer - no duplicate TIME_ADVANCED logic.
    """
    from .event_store import EventStore
    
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
        try:
            initial_state = json.loads(record.initial_state_json)
        except json.JSONDecodeError as e:
            return ReplayResult(
                success=False,
                error_message=f"Malformed JSON in initial state: {e}",
            )
        
        if state_hash(initial_state) != record.initial_state_hash:
            return ReplayResult(
                success=False,
                error_message="Initial state hash mismatch with stored metadata",
            )
        
        # Get all event records
        try:
            event_records = store.all_event_records(campaign_id)
        except ValueError as e:
            # Raised for malformed JSON
            return ReplayResult(
                success=False,
                error_message=str(e),
            )
        
        if not event_records:
            return ReplayResult(
                success=True,
                final_state=initial_state,
                expected_hash=record.initial_state_hash,
                actual_hash=record.initial_state_hash,
            )
        
        current_state = initial_state
        
        for event_record in event_records:
            event_seq = event_record["event_seq"]
            
            # Check before-hash
            expected_before_hash = event_record["state_hash_before"]
            actual_before_hash = state_hash(current_state)
            
            if expected_before_hash != actual_before_hash:
                return ReplayResult(
                    success=False,
                    failed_event_seq=event_seq,
                    error_message=f"Event {event_seq}: state_hash_before ({actual_before_hash[:16]}...) doesn't match stored ({expected_before_hash[:16]}...)",
                )
            
            # Convert to DomainEvent
            domain_event = record_to_domain_event(event_record)
            
            # Apply event using reducer
            from ..core.reducer import reduce_event
            
            try:
                # We need to convert current_state (dict) to GameState temporarily
                temp_state = GameState(**current_state)
                temp_state = reduce_event(temp_state, domain_event)
                current_state = temp_state.__dict__
            except Exception as e:
                return ReplayResult(
                    success=False,
                    failed_event_seq=event_seq,
                    error_message=f"Event {event_seq}: failed to apply event: {e}",
                )
            
            # Check after-hash
            expected_after_hash = event_record["state_hash_after"]
            actual_after_hash = state_hash(current_state)
            
            if expected_after_hash != actual_after_hash:
                return ReplayResult(
                    success=False,
                    failed_event_seq=event_seq,
                    error_message=f"Event {event_seq}: state_hash_after ({actual_after_hash[:16]}...) doesn't match stored ({expected_after_hash[:16]}...)",
                )
        
        # Final verification: snapshot must exist and match final state
        if not event_records:
            # No events - check for orphan snapshots
            all_snapshots = store.all_event_records(campaign_id)
            # Just verify by attempting to get latest snapshot
            snapshot = store.latest_snapshot_record(campaign_id)
            if snapshot and snapshot.event_seq > 0:
                return ReplayResult(
                    success=False,
                    error_message="Orphan snapshot exists without any events",
                    failed_event_seq=snapshot.event_seq,
                )
        else:
            # Must have a snapshot matching the last event
            snapshot = store.latest_snapshot_record(campaign_id)
            if snapshot is None:
                return ReplayResult(
                    success=False,
                    error_message=f"Missing snapshot for campaign with {len(event_records)} events",
                    failed_event_seq=event_records[-1]["event_seq"],
                )
            
            if snapshot.event_seq != event_records[-1]["event_seq"]:
                return ReplayResult(
                    success=False,
                    error_message=f"Snapshot seq ({snapshot.event_seq}) doesn't match last event seq ({event_records[-1]['event_seq']})",
                    failed_event_seq=event_records[-1]["event_seq"],
                )
            
            final_state_hash = state_hash(current_state)
            
            if snapshot.state_hash != final_state_hash:
                return ReplayResult(
                    success=False,
                    error_message=f"Final state hash ({final_state_hash[:16]}...) doesn't match snapshot hash ({snapshot.state_hash[:16]}...)",
                    failed_event_seq=snapshot.event_seq,
                )
            
            # Also verify snapshot hash against its own content
            snapshot_content_hash = state_hash(snapshot.state)
            if snapshot.state_hash != snapshot_content_hash:
                return ReplayResult(
                    success=False,
                    error_message=f"Snapshot hash ({snapshot.state_hash[:16]}...) doesn't match its own content hash ({snapshot_content_hash[:16]}...)",
                    failed_event_seq=snapshot.event_seq,
                )
        
        return ReplayResult(
            success=True,
            final_state=current_state,
            expected_hash=final_state_hash if 'final_state_hash' in locals() else None,
            actual_hash=final_state_hash if 'final_state_hash' in locals() else None,
        )
    
    finally:
        store.close()


def verify_replay(
    initial_state: GameState,
    events: list[DomainEvent],
    expected_final_hash: str,
) -> ReplayResult:
    """Verify that pure replay produces expected hash.
    
    This is the pure function layer - it uses replay_events() which operates on
    GameState + DomainEvent[], not persisted records. It has no knowledge of:
    - SQLite
    - PersistedEventRecord  
    - state_hash_before/after
    """
    result = replay_events(initial_state, events, state_at_each_step=True)
    
    if not result.success:
        return result
    
    result.expected_hash = expected_final_hash
    
    if result.expected_hash != result.actual_hash:
        result.success = False
        result.error_message = f"Hash mismatch: expected {result.expected_hash[:16]}..., got {result.actual_hash[:16]}..."
    
    return result
