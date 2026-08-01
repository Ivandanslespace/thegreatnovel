"""Shared fixtures for the local Phase 7.5 contract tests."""

from __future__ import annotations

import copy

from tgn.actions.models import ActionIntent
from tgn.core.models import GameState
from tgn.gameplay.expedition import execute_action
from tgn.gameplay.named_actor import (
    MARA_ACTOR_ID,
    MARA_FACT_ID,
    MARA_INITIAL_GOAL,
    MARA_INITIAL_LOCATION_ID,
)


def make_phase75_state(*, fact_value: str = "unstable") -> GameState:
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="phase75-test",
        data={
            "player": {
                "hp": 10,
                "max_hp": 10,
                "location_id": MARA_INITIAL_LOCATION_ID,
                "stamina": 3,
                "max_stamina": 3,
                "attack": 2,
            },
            "inventory": {},
            "expedition": {
                "active": False,
                "base_location_id": MARA_INITIAL_LOCATION_ID,
                "target_location_id": "site-1",
                "target_searched": False,
                "target_loot": {"salvage": 2},
                "carried_loot": {},
            },
            "named_actor": {
                "actor_id": MARA_ACTOR_ID,
                "name": "Mara",
                "location_id": MARA_INITIAL_LOCATION_ID,
                "goal": MARA_INITIAL_GOAL,
                "relationship": {"trust": 0},
                "knowledge": {},
                "last_autonomous_action": None,
            },
            "world_facts": {MARA_FACT_ID: fact_value},
            "player_knowledge": {
                "facts": {},
                "actors": {
                    MARA_ACTOR_ID: {
                        "name": "Mara",
                        "last_known_location_id": MARA_INITIAL_LOCATION_ID,
                        "known_goal": MARA_INITIAL_GOAL,
                    }
                },
            },
        },
    )


def action(action_type: str, action_id: str = "phase75-action", **params: object) -> ActionIntent:
    return ActionIntent(
        action_id=action_id,
        actor_id="phase75-player",
        action_type=action_type,
        params=dict(params),
    )


def execute(state: GameState, action_type: str, action_id: str = "phase75-action", **params: object) -> GameState:
    result = execute_action(state, action(action_type, action_id, **params))
    assert result.accepted, result.validation.errors
    assert result.final_state is not None
    return result.final_state


def report_ready_state() -> GameState:
    state = make_phase75_state()
    state = execute(state, "DROP", "drop-for-report")
    return execute(state, "EXTRACT", "extract-for-report")


def copy_state(state: GameState) -> GameState:
    return GameState(**copy.deepcopy(state.__dict__))
