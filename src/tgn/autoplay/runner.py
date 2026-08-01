"""Autoplay runner."""

from __future__ import annotations

import copy
from typing import Any, Callable

from ..actions.models import ActionIntent
from ..core.models import GameState
from ..core.hashing import state_hash
from ..gameplay.expedition import build_observation, execute_action
from ..gameplay.named_actor import (
    count_knowledge_boundary_violations,
    named_actor_metric_delta,
)
from .models import AutoplayConfig, AutoplayRunResult, StopReason, WatchFrame, RejectedActionRecord


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
    accepted_events = []
    decisions = 0
    events = 0
    illegal_actions = 0
    knowledge_boundary_violations = 0
    actor_autonomous_actions = 0
    knowledge_transfers = 0
    relationship_changes = 0
    
    while decisions < config.max_decisions:
        # Build observation (player-visible only)
        observation_before = build_observation(state)
        knowledge_boundary_violations += count_knowledge_boundary_violations(
            state, observation_before
        )
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
            illegal_actions += 1
            # Create rejection diagnostic record
            rejection = RejectedActionRecord(
                action_id=intent.action_id,
                actor_id=intent.actor_id,
                action_type=intent.action_type,
                params=copy.deepcopy(intent.params),
                validation_errors=result.validation.errors,
                state_hash_before=state_hash_before,
            )
            
            return AutoplayRunResult(
                completed=False,
                stop_reason=StopReason.ACTION_REJECTED,
                initial_state_hash=initial_state_hash,
                final_state_hash=state_hash_before,
                decisions=decisions,
                events=events,
                frames=tuple(frames),
                final_state=state,
                rejection=rejection,
                illegal_actions=illegal_actions,
                knowledge_boundary_violations=knowledge_boundary_violations,
                actor_autonomous_actions=actor_autonomous_actions,
                knowledge_transfers=knowledge_transfers,
                relationship_changes=relationship_changes,
            )
        
        # Accepted - build frame
        decisions += 1
        events += len(result.events)
        
        new_state = result.final_state
        assert new_state is not None
        
        observation_after = build_observation(new_state)
        knowledge_boundary_violations += count_knowledge_boundary_violations(
            new_state, observation_after
        )
        metric_delta = named_actor_metric_delta(state, new_state)
        actor_autonomous_actions += metric_delta["actor_autonomous_actions"]
        knowledge_transfers += metric_delta["knowledge_transfers"]
        relationship_changes += metric_delta["relationship_changes"]
        state_hash_after = state_hash(new_state.__dict__)
        game_minute_after = new_state.game_minute
        
        # Get event (should be exactly 1)
        assert len(result.events) == 1
        event = result.events[0]
        accepted_events.append(event)
        
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

    from ..storage.replay import replay_events, verify_persistence_integrity

    replay_result = replay_events(initial_state, accepted_events)
    replay_verified = (
        replay_result.success and replay_result.actual_hash == final_state_hash
    )
    sqlite_reopen_verified = False
    if event_store is not None and campaign_id is not None:
        sqlite_reopen_verified = verify_persistence_integrity(
            campaign_id, event_store.db_path
        ).success
    
    return AutoplayRunResult(
        completed=(stop_reason == StopReason.POLICY_COMPLETE),
        stop_reason=stop_reason,
        initial_state_hash=initial_state_hash,
        final_state_hash=final_state_hash,
        decisions=decisions,
        events=events,
        frames=tuple(frames),
        final_state=state,
        illegal_actions=illegal_actions,
        knowledge_boundary_violations=knowledge_boundary_violations,
        actor_autonomous_actions=actor_autonomous_actions,
        knowledge_transfers=knowledge_transfers,
        relationship_changes=relationship_changes,
        replay_verified=replay_verified,
        sqlite_reopen_verified=sqlite_reopen_verified,
    )
