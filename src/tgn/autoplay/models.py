"""Phase 3.5 autoplay models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StopReason(str, Enum):
    """Why an autoplay run stopped."""
    POLICY_COMPLETE = "POLICY_COMPLETE"
    MAX_DECISIONS = "MAX_DECISIONS"
    ACTION_REJECTED = "ACTION_REJECTED"


@dataclass(frozen=True)
class AutoplayConfig:
    """Configuration for autoplay runs."""
    max_decisions: int = 20
    actor_id: str = "autoplay-bot"
    
    def __post_init__(self):
        # Reject bool explicitly (bool is subclass of int in Python)
        if isinstance(self.max_decisions, bool):
            raise ValueError(f"max_decisions must be int, not bool")
        if not isinstance(self.max_decisions, int):
            raise ValueError(f"max_decisions must be int, got {type(self.max_decisions).__name__}")
        if self.max_decisions <= 0:
            raise ValueError(f"max_decisions must be > 0, got {self.max_decisions}")


@dataclass(frozen=True)
class WatchFrame:
    """
    Structured frame for one accepted decision.
    
    This is display/analysis data, not runtime truth.
    It comes from: Observation + Intent + Event + resulting State
    
    IMPORTANT: All dicts must be deep-copied to isolate from Engine state.
    """
    step: int
    
    action_id: str
    actor_id: str
    action_type: str
    
    event_type: str
    
    game_minute_before: int
    game_minute_after: int
    
    observation_before: dict[str, Any]
    observation_after: dict[str, Any]
    
    event_payload: dict[str, Any]
    
    state_hash_before: str
    state_hash_after: str


@dataclass(frozen=True)
class RejectedActionRecord:
    """
    Diagnostic record for a rejected action.
    
    Preserves the full intent, validation errors, and state hash before the action
    was attempted. This allows future LLM players to debug illegal moves.
    
    IMPORTANT: Does NOT contain full GameState to prevent hidden state leakage.
    Only contains Intent + Validation Errors + State Hash.
    """
    action_id: str
    actor_id: str
    action_type: str
    params: dict[str, Any]
    
    validation_errors: tuple[Any, ...]  # tuple[ActionValidationError, ...]
    
    state_hash_before: str


@dataclass(frozen=True)
class AutoplayRunResult:
    """Result of a complete autoplay run."""
    completed: bool
    stop_reason: str
    
    initial_state_hash: str
    final_state_hash: str
    
    decisions: int
    events: int
    
    frames: tuple[WatchFrame, ...]
    
    final_state: Any  # GameState

    rejection: RejectedActionRecord | None = None

    # Phase 7.5 scripted integrity telemetry. Defaults preserve older callers.
    illegal_actions: int = 0
    knowledge_boundary_violations: int = 0
    actor_autonomous_actions: int = 0
    knowledge_transfers: int = 0
    relationship_changes: int = 0
    replay_verified: bool = False
    persistence_integrity_verified: bool = False

    def summary(self) -> dict[str, Any]:
        """Structured run summary."""
        result = {
            "completed": self.completed,
            "stop_reason": self.stop_reason,
            "decisions": self.decisions,
            "events": self.events,
            "illegal_actions": self.illegal_actions,
            "knowledge_boundary_violations": self.knowledge_boundary_violations,
            "actor_autonomous_actions": self.actor_autonomous_actions,
            "knowledge_transfers": self.knowledge_transfers,
            "relationship_changes": self.relationship_changes,
            "replay_verified": self.replay_verified,
            "persistence_integrity_verified": self.persistence_integrity_verified,
            "start_game_minute": self.frames[0].game_minute_before if self.frames else 0,
            "end_game_minute": self.frames[-1].game_minute_after if self.frames else 0,
            "final_state_hash": self.final_state_hash,
        }
        
        # Include rejection diagnostics if present
        if self.rejection is not None:
            result["rejection"] = {
                "action_id": self.rejection.action_id,
                "actor_id": self.rejection.actor_id,
                "action_type": self.rejection.action_type,
                "validation_error_codes": [err.code for err in self.rejection.validation_errors],
                "state_hash_before": self.rejection.state_hash_before,
            }
        
        return result
