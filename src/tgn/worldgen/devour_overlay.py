"""Fixed Phase 10A WorldGen overlay and deterministic bootstrap."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from ..actions.models import ActionIntent
from ..autoplay.models import AutoplayConfig
from ..autoplay.runner import run_autoplay
from ..core.hashing import state_hash
from ..core.invariants import check_invariants
from ..core.models import GameState
from ..gameplay.devour_evolution import (
    DEVOUR_REMAINS,
    DEVOUR_EVOLUTION_CAPABILITY_ID,
    DEVOUR_EVOLUTION_GRANT_ID,
)


DEVOUR_OVERLAY_COMPILER_ID = "phase10a-devour-overlay-v1"
DEVOUR_OVERLAY_ID = "devour_evolution_genesis_v1"
BASE_COMPILER_ID = "phase9b-bounded-world-v1"
DEVOUR_MECHANICS_PROFILE = "phase75_expedition_v1"


def apply_devour_overlay(base_state: GameState) -> GameState:
    """Apply the one fixed Phase 10A transformation to a verified base state."""

    if not isinstance(base_state, GameState):
        raise ValueError("base_state must be GameState")
    if any(
        key in base_state.data
        for key in ("capability_grants", "devour_evolution")
    ):
        raise ValueError("overlay input already contains Phase 10A state")
    base_expedition = base_state.data.get("expedition")
    if not isinstance(base_expedition, dict) or "encounter" in base_expedition:
        raise ValueError("overlay input is not the verified base expedition state")

    state = copy.deepcopy(base_state)
    state.data["player"]["stamina"] = 5
    state.data["player"]["max_stamina"] = 5
    state.data["capability_grants"] = {
        DEVOUR_EVOLUTION_GRANT_ID: {
            "holder_id": "player",
            "capability_id": DEVOUR_EVOLUTION_CAPABILITY_ID,
            "source_kind": "world_genesis",
            "source_id": "protagonist_core_gift",
            "acquired_event_seq": 0,
        }
    }
    state.data["devour_evolution"] = {"essence": 0}
    state.data["expedition"]["encounter"] = {
        "enemy_id": "enemy-1",
        "enemy_hp": 2,
        "enemy_max_hp": 2,
        "enemy_attack": 1,
        "active": False,
        "devour_yield": {
            "capability_id": DEVOUR_EVOLUTION_CAPABILITY_ID,
            "essence": 1,
            "consumed": False,
        },
    }
    check_invariants(state)
    return state


def _bootstrap_policy(
    _observation: dict[str, Any], decision_number: int, actor_id: str
) -> ActionIntent | None:
    sequence = ("DROP", "SEARCH", "FIGHT", DEVOUR_REMAINS, "EXTRACT")
    if decision_number > len(sequence):
        return None
    return ActionIntent(
        action_id=f"{actor_id}-bootstrap-{decision_number}",
        actor_id=actor_id,
        action_type=sequence[decision_number - 1],
        params={},
    )


def bootstrap_devour_overlay(initial_state: GameState) -> dict[str, Any]:
    """Run the fixed five-action policy through the real engine and replay."""

    if not isinstance(initial_state, GameState):
        raise ValueError("initial_state must be GameState")
    result = run_autoplay(
        copy.deepcopy(initial_state),
        _bootstrap_policy,
        # Six is only the policy-completion bound: the five actions remain the
        # complete accepted decision sequence and no sixth action is emitted.
        AutoplayConfig(max_decisions=6, actor_id="phase10a-bootstrap"),
    )
    if not result.completed or result.decisions != 5 or result.events != 5:
        raise ValueError("Phase 10A bootstrap did not accept exactly five actions")
    if result.illegal_actions != 0 or not result.replay_verified:
        raise ValueError("Phase 10A bootstrap replay or legality failed")
    if result.final_state.event_seq != 5 or result.final_state.decision_seq != 5:
        raise ValueError("Phase 10A bootstrap sequence numbers are invalid")
    devour_frames = [frame for frame in result.frames if frame.action_type == DEVOUR_REMAINS]
    if len(devour_frames) != 1:
        raise ValueError("Phase 10A bootstrap must contain one DEVOUR_REMAINS action")
    devour_frame = devour_frames[0]
    final_state = result.final_state
    if devour_frame.observation_before.get("stamina") != 1:
        raise ValueError("stamina before DEVOUR_REMAINS is not 1")
    if devour_frame.observation_after.get("stamina") != 0:
        raise ValueError("stamina after DEVOUR_REMAINS is not 0")
    expedition = final_state.data["expedition"]
    if (
        final_state.data["devour_evolution"]["essence"] != 1
        or expedition["encounter"]["devour_yield"]["consumed"] is not True
        or final_state.data["player"]["stamina"] != 0
        or expedition["active"] is not False
        or final_state.data["player"]["location_id"] != expedition["base_location_id"]
    ):
        raise ValueError("Phase 10A bootstrap final state does not match the contract")

    return {
        "accepted_decisions": 5,
        "events": 5,
        "illegal_actions": 0,
        "essence": 1,
        "devour_yield_consumed": True,
        "replay_verified": True,
        "stamina_before_devour": 1,
        "stamina_after_devour": 0,
        "final_stamina_after_extract": 0,
        "final_state_hash": state_hash(final_state.__dict__),
    }


def build_devour_compile_report(
    *,
    base_initial_state_hash: str,
    worldpack_hash: str,
    overlay_state: GameState,
) -> dict[str, Any]:
    """Build the exact deterministic overlay compile report."""

    initial_state_hash = state_hash(overlay_state.__dict__)
    return {
        "schema_version": 1,
        "valid": True,
        "compiler_id": DEVOUR_OVERLAY_COMPILER_ID,
        "base_compiler_id": BASE_COMPILER_ID,
        "overlay_id": DEVOUR_OVERLAY_ID,
        "base_initial_state_hash": base_initial_state_hash,
        "worldpack_hash": worldpack_hash,
        "initial_state_hash": initial_state_hash,
        "errors": [],
        "bootstrap": bootstrap_devour_overlay(overlay_state),
    }


__all__ = [
    "BASE_COMPILER_ID",
    "DEVOUR_MECHANICS_PROFILE",
    "DEVOUR_OVERLAY_COMPILER_ID",
    "DEVOUR_OVERLAY_ID",
    "apply_devour_overlay",
    "bootstrap_devour_overlay",
    "build_devour_compile_report",
]
