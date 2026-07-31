"""__init__.py - Storage module exports."""

from .event_store import EventStore, EventStoreError
from .replay import (
    replay_campaign,
    replay_events,
    verify_replay,
    verify_persistence_integrity,
    record_to_domain_event,
    ReplayResult,
)

__all__ = [
    "EventStore",
    "EventStoreError",
    "replay_events",      # Pure function: GameState + DomainEvent[]
    "replay_campaign",   # Persistence mode: from persisted records
    "verify_replay",     # Hash verification using pure replay
    "verify_persistence_integrity",  # Full DB integrity check
    "record_to_domain_event",      # Record → DomainEvent conversion
    "ReplayResult",
]
