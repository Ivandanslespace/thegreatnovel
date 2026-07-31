"""Deterministic autoplay policy."""

from __future__ import annotations

from typing import Any

from ..actions.models import ActionIntent


def choose_action(
    observation: dict[str, Any],
    decision_number: int,
    actor_id: str = "autoplay-bot",
) -> ActionIntent | None:
    """
    Deterministic policy that selects an action based on observation.
    
    Args:
        observation: Player-visible observation (NOT GameState)
        decision_number: Current decision count (1-indexed)
        actor_id: Bot actor ID
        
    Returns:
        ActionIntent to execute, or None to stop the run
        
    Policy priority (when legal):
        1. SEARCH (if legal)
        2. EXTRACT (if legal)
        3. DROP (if legal)
        4. STOP (None)
        
    WAIT is always legal but policy never selects it to avoid infinite loops.
    """
    legal_actions = observation.get("legal_actions", ())
    legal_types = [la.action_type for la in legal_actions]
    
    # Deterministic action_id
    action_id = f"auto-action-{decision_number:04d}"
    
    # Priority order: SEARCH > EXTRACT > DROP
    if "SEARCH" in legal_types:
        return ActionIntent(
            action_id=action_id,
            actor_id=actor_id,
            action_type="SEARCH",
            params={},
        )
    
    if "EXTRACT" in legal_types:
        return ActionIntent(
            action_id=action_id,
            actor_id=actor_id,
            action_type="EXTRACT",
            params={},
        )
    
    if "DROP" in legal_types:
        return ActionIntent(
            action_id=action_id,
            actor_id=actor_id,
            action_type="DROP",
            params={},
        )
    
    # Only WAIT remains - stop the run
    return None
