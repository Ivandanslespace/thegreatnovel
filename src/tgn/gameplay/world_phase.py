"""Phase 5 minimal world phase derivation.

Phase 5 minimal configuration — NOT the final WorldPack schema.

Pure, deterministic helpers that derive world phase from canonical game_minute
and a slice-local phase_cycle configuration stored in state.data["phase_cycle"].

No I/O, no DB, no LLM, no wall clock, no random.
"""

from __future__ import annotations

from typing import Any

from ..core.models import GameState


def get_current_phase(state: GameState) -> str | None:
    """Derive current world phase from game_minute + phase_cycle config.

    Returns None if phase_cycle configuration is absent (pre-Phase-5 state).
    """
    config = state.data.get("phase_cycle")
    if config is None:
        return None

    cycle = config["cycle_minutes"]
    boundary = config["boundary_minute"]
    position = state.game_minute % cycle

    if position < boundary:
        return config["phase_before"]
    return config["phase_after"]


def minutes_until_phase_change(state: GameState) -> int | None:
    """Minutes until the next phase boundary crossing.

    Returns None if phase_cycle configuration is absent.
    """
    config = state.data.get("phase_cycle")
    if config is None:
        return None

    cycle = config["cycle_minutes"]
    boundary = config["boundary_minute"]
    position = state.game_minute % cycle

    if position < boundary:
        return boundary - position
    return cycle - position


def is_action_blocked_by_phase(state: GameState, action_type: str) -> bool:
    """Check if action_type is blocked by the current world phase.

    Returns False if phase_cycle configuration is absent (feature optional).
    """
    config = state.data.get("phase_cycle")
    if config is None:
        return False

    phase = get_current_phase(state)
    if phase is None:
        return False

    blocked_map: dict[str, list[str]] = config.get("blocked_actions_by_phase", {})
    blocked_list = blocked_map.get(phase, [])
    return action_type in blocked_list
