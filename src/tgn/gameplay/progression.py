"""Phase 6 minimal progression helpers.

Pure, deterministic functions for ProgressionTrack + ProgressionGate.
No I/O, no DB, no LLM, no wall clock, no random.

Resource names (salvage, parts) are WorldPack-local — this module
operates on arbitrary track IDs and cost mappings.
"""

from __future__ import annotations

from ..core.models import GameState


def get_track_stage(state: GameState, track_id: str) -> int | None:
    """Get current stage for a progression track.

    Returns None if progression feature is absent.
    """
    progression = state.data.get("progression")
    if progression is None:
        return None
    return progression.get("tracks", {}).get(track_id)


def get_progression_gate(state: GameState, track_id: str) -> dict | None:
    """Get the gate definition for a track.

    Returns None if progression_gates absent or track has no gate.
    """
    gates = state.data.get("progression_gates")
    if gates is None:
        return None
    return gates.get(track_id)


def can_advance_track(state: GameState, track_id: str) -> bool:
    """Check if a track can be advanced (gate satisfiable).

    Requirements:
    - progression enabled
    - gate exists for track
    - current stage == gate.from_stage
    - inventory satisfies all resource costs
    """
    stage = get_track_stage(state, track_id)
    if stage is None:
        return False

    gate = get_progression_gate(state, track_id)
    if gate is None:
        return False

    if stage != gate["from_stage"]:
        return False

    inventory = state.data.get("inventory", {})
    cost = gate.get("cost", {})
    for resource, qty in cost.items():
        if inventory.get(resource, 0) < qty:
            return False

    return True


def get_gate_cost(state: GameState, track_id: str) -> dict | None:
    """Get the resource cost for the next advancement.

    Returns None if no gate or track already past gate.
    Returns a detached copy to prevent observation aliasing canonical state.
    """
    gate = get_progression_gate(state, track_id)
    if gate is None:
        return None

    stage = get_track_stage(state, track_id)
    if stage is None:
        return None

    if stage != gate["from_stage"]:
        return None

    cost = gate.get("cost")
    if cost is None:
        return None
    return dict(cost)


def progression_enabled(state: GameState) -> bool:
    """Check if progression feature is enabled (both config keys present)."""
    return (
        state.data.get("progression") is not None
        and state.data.get("progression_gates") is not None
    )
