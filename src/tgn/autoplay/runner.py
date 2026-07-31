"""Autoplay runner."""

from __future__ import annotations

import copy
from typing import Any, Callable

from ..actions.models import ActionIntent
from ..core.models import GameState
from ..core.hashing import state_hash
from ..gameplay.expedition import build_observation, execute_action
from .models import AutoplayConfig, AutoplayRunResult, StopReason, WatchFrame


def run_autoplay(
    initial_state: GameState,
    policy: Callable[[dict[str, Any], int, str], ActionIntent | None],
    config: AutoplayConfig,
    *,
    event_store: Any | None = None,
    campaign_id: str | None = None,
) -> AutoplayRunResult:
    """
    Run autoplay with deterministic policy.
    
    Args:
        initial_state: Starting GameState
        policy: Function that chooses action from observation
        config: AutoplayConfig with max_decisions and actor_id
        event_store: Optional EventStore for persistence
        campaign_id: Optional campaign ID for persistence
        
    Returns:
        AutoplayRunResult with all frames and final state
    """
    state = initial_state
    initial_state_hash = state_hash(state.__dict__)
    
    # Initialize campaign if EventStore provided
    if event_store is not None and campaign_id is not None:
        event_store.initialize(campaign_id, state.__dict__)
    
    frames: list[WatchFrame] = []
    decisions = 0
    events = 0
    
    while decisions < config.max_decisions:
        # Build observation (player-visible only)
        observation_before = build_observation(state)
        state_hash_before = state_hash(state.__dict__)
        game_minute_before = state.game_minute
        
        # Policy decides
        intent = policy(observation_before, decisions + 1, config.actor_id)
        
        # Policy says stop
        if intent is None:
            break
        
        # Execute action
        result = execute_action(state, intent)
        
        # Rejected action - stop immediately
        if not result.accepted:
            # Record rejection but don't add to frames
            return AutoplayRunResult(
                completed=False,
                stop_reason=StopReason.ACTION_REJECTED,
                initial_state_hash=initial_state_hash,
                final_state_hash=state_hash_before,
                decisions=decisions,
                events=events,
                frames=tuple(frames),
                final_state=state,
            )
        
        # Accepted - build frame
        decisions += 1
        events += len(result.events)
        
        new_state = result.final_state
        assert new_state is not None
        
        observation_after = build_observation(new_state)
        state_hash_after = state_hash(new_state.__dict__)
        game_minute_after = new_state.game_minute
        
        # Get event (should be exactly 1)
        assert len(result.events) == 1
        event = result.events[0]
        
        # Persist if EventStore provided (pass GameState objects, not dicts)
        if event_store is not None and campaign_id is not None:
            event_store.append_transition(campaign_id, event, state, new_state)
        
        # Deep-copy all dicts for isolation
        frame = WatchFrame(
            step=decisions,
            action_id=intent.action_id,
            actor_id=intent.actor_id,
            action_type=intent.action_type,
            event_type=event.event_type,
            game_minute_before=game_minute_before,
            game_minute_after=game_minute_after,
            observation_before=copy.deepcopy(observation_before),
            observation_after=copy.deepcopy(observation_after),
            event_payload=copy.deepcopy(event.payload),
            state_hash_before=state_hash_before,
            state_hash_after=state_hash_after,
        )
        frames.append(frame)
        
        state = new_state
    
    # Determine stop reason
    if decisions >= config.max_decisions:
        stop_reason = StopReason.MAX_DECISIONS
    else:
        stop_reason = StopReason.POLICY_COMPLETE
    
    final_state_hash = state_hash(state.__dict__)
    
    return AutoplayRunResult(
        completed=(stop_reason == StopReason.POLICY_COMPLETE),
        stop_reason=stop_reason,
        initial_state_hash=initial_state_hash,
        final_state_hash=final_state_hash,
        decisions=decisions,
        events=events,
        frames=tuple(frames),
        final_state=state,
    )
