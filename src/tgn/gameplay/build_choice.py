"""Phase 7 minimal first-WorldPack build choice helpers.

Pure, deterministic functions for permanent build selection.
No I/O, no DB, no LLM, no wall clock, no random.

This is the local Phase 7 slice for the first WorldPack. The configured
candidate count may be two or three, but the supported effect set is the
explicit first-slice set below. This is not a generic build-effect system.
"""

from __future__ import annotations

from ..core.models import GameState

# Player-visible contract and authoritative first-slice semantics live
# together here so the player-facing description cannot drift from the
# deterministic rules. This is deliberately a direct, local mapping rather
# than a general effect registry or plugin framework.
_FIRST_WORLD_BUILD_DETAILS: dict[str, dict[str, str]] = {
    "window_runner": {
        "build_id": "window_runner",
        "title": "Window Runner",
        "effect_summary": "Allows DROP during the NIGHT DROP phase window.",
        "relevant_condition_or_limitation": (
            "Only the phase-window block is bypassed: normal DROP location, "
            "stamina, and expedition rules still apply. If base progression "
            "is already stage 1 or higher, this part is already unlocked by "
            "the Phase 6 base progression."
        ),
        "permanence": "Permanent after selection; CHOOSE_BUILD is no longer legal.",
        "opportunity_cost": "You permanently give up Field Rest and Quick Rest.",
    },
    "field_rest": {
        "build_id": "field_rest",
        "title": "Field Rest",
        "effect_summary": "Allows REST at the expedition target while an expedition is active.",
        "relevant_condition_or_limitation": (
            "Requires player stage >= 1, being at the target, stamina below "
            "maximum, and no active encounter. It does not unlock REST "
            "elsewhere or change its time cost."
        ),
        "permanence": "Permanent after selection; CHOOSE_BUILD is no longer legal.",
        "opportunity_cost": "You permanently give up Window Runner and Quick Rest.",
    },
    "quick_rest": {
        "build_id": "quick_rest",
        "title": "Quick Rest",
        "effect_summary": "Changes the authoritative REST time from 20 to 10 minutes whenever REST is legal.",
        "relevant_condition_or_limitation": (
            "Does not unlock REST or change its progression, location, stamina, "
            "or encounter requirements."
        ),
        "permanence": "Permanent after selection; CHOOSE_BUILD is no longer legal.",
        "opportunity_cost": "You permanently give up Window Runner and Field Rest.",
    },
}

# The effect collection is intentionally explicit and limited to this local
# first-world slice. Candidate count remains configurable at two or three.
SUPPORTED_BUILDS = frozenset(_FIRST_WORLD_BUILD_DETAILS)

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
    """Get configured first-slice candidate IDs in configured order."""
    config = state.data.get("build_choice")
    if config is None:
        return []
    return list(config.get("candidates", []))


def get_player_visible_build_choices(state: GameState) -> list[dict[str, str]]:
    """Return detached player-visible descriptions for configured candidates."""
    return [
        dict(_FIRST_WORLD_BUILD_DETAILS[build_id])
        for build_id in get_available_build_ids(state)
        if build_id in SUPPORTED_BUILDS
    ]


def build_allows_drop_during_phase_window(state: GameState) -> bool:
    """Return whether the selected first-slice build unlocks the DROP window."""
    return has_selected_build(state, "window_runner")


def build_allows_rest_at_target(state: GameState) -> bool:
    """Return whether the selected first-slice build unlocks target REST."""
    return has_selected_build(state, "field_rest")


def get_rest_duration(state: GameState) -> int:
    """Get authoritative REST duration based on selected build."""
    if has_selected_build(state, "quick_rest"):
        return 10
    return 20
