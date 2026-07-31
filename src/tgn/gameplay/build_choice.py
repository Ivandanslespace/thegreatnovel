"""Phase 7 minimal build choice helpers.

Pure, deterministic functions for permanent build selection.
No I/O, no DB, no LLM, no wall clock, no random.

Build IDs (window_runner, field_rest, quick_rest) are first-world local
semantics — this module operates on arbitrary configured candidate lists.
"""

from __future__ import annotations

from ..core.models import GameState

# Supported first-slice build IDs (engine knows their effects)
SUPPORTED_BUILDS = frozenset({"window_runner", "field_rest", "quick_rest"})

BUILD_CHOICE_TIME = 1


def build_choice_enabled(state: GameState) -> bool:
    """Check if build choice feature is configured."""
    return (
        state.data.get("build_choice") is not None
        and state.data.get("build") is not None
    )


def get_selected_build(state: GameState) -> str | None:
    """Get currently selected build ID, or None if not selected/feature absent."""
    build = state.data.get("build")
    if build is None:
        return None
    return build.get("selected")


def has_selected_build(state: GameState, build_id: str) -> bool:
    """Check if a specific build is selected."""
    return get_selected_build(state) == build_id


def build_choice_available(state: GameState) -> bool:
    """Check if build choice is currently actionable (trigger met, not yet selected)."""
    if not build_choice_enabled(state):
        return False

    if get_selected_build(state) is not None:
        return False

    config = state.data["build_choice"]
    required_track = config["required_track"]
    required_stage = config["required_stage"]

    progression = state.data.get("progression")
    if progression is None:
        return False

    current_stage = progression.get("tracks", {}).get(required_track)
    if current_stage is None:
        return False

    return current_stage >= required_stage


def get_available_build_ids(state: GameState) -> list[str]:
    """Get configured candidate build IDs (detached copy)."""
    config = state.data.get("build_choice")
    if config is None:
        return []
    return list(config.get("candidates", []))


def get_rest_duration(state: GameState) -> int:
    """Get authoritative REST duration based on selected build."""
    if has_selected_build(state, "quick_rest"):
        return 10
    return 20
