"""Core data models for game state and events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class GameState:
    """
    Minimal deterministic game state.
    
    First version contains only runtime metadata and an empty domain data container.
    No gameplay-specific content yet - that belongs to future world packs.
    """
    schema_version: int = 1
    event_seq: int = 0  # Number of domain events processed
    decision_seq: int = 0  # Number of player decisions made
    game_minute: int = 0  # In-game time in minutes
    seed: str = ""  # Deterministic seed for reproducibility
    
    # Empty container for world-specific data (populated by world packs later)
    data: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def initial(cls, seed: str = "default-seed") -> "GameState":
        """Create initial game state with given seed."""
        return cls(
            schema_version=1,
            event_seq=0,
            decision_seq=0,
            game_minute=0,
            seed=seed,
            data={},
        )


@dataclass
class DomainEvent:
    """
    Immutable domain event representing a fact about the game world.
    
    Required fields for full provenance:
    - event_id: unique identifier
    - event_seq: sequence number (monotonically increasing)
    - decision_seq: which player decision triggered this (if any)
    - game_minute: game time when this occurred
    - event_type: categorical type of event
    - actor_id: who/what caused this
    - action_id: which action was taken
    - causation_id: links to preceding event if causal chain
    - correlation_id: groups related events
    - payload: event-specific data
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_seq: int = 0
    decision_seq: int = 0
    game_minute: int = 0
    event_type: str = ""
    actor_id: str | None = None
    action_id: str | None = None
    causation_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @classmethod
    def advance_time(cls, game_minute: int, minutes: int, event_seq: int = 0, **kwargs) -> "DomainEvent":
        """Helper to create TIME_ADVANCED event."""
        if minutes < 0:
            raise ValueError("Time advancement cannot be negative")
        
        return cls(
            event_seq=event_seq,
            event_type="TIME_ADVANCED",
            actor_id=kwargs.get("actor_id"),
            action_id=kwargs.get("action_id"),
            game_minute=game_minute + minutes,
            payload={"minutes": minutes},
            **{k: v for k, v in kwargs.items() if k not in ["game_minute", "minutes", "event_seq"]},
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_seq": self.event_seq,
            "decision_seq": self.decision_seq,
            "game_minute": self.game_minute,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "action_id": self.action_id,
            "causation_id": self.causation_id,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DomainEvent":
        """Reconstruct from dictionary."""
        return cls(**data)
