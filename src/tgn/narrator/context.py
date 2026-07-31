"""Build narration context from watch frame."""

from __future__ import annotations

import copy
from typing import Any

from ..autoplay.models import WatchFrame
from .models import NarrationContext


def build_narration_context(frame: WatchFrame) -> NarrationContext:
    """
    Build narration context from a watch frame.
    
    This function is:
    - pure
    - deterministic
    - no I/O
    - no database
    - no model call
    
    Deep-copies all mutable data to isolate from Engine state.
    
    CRITICAL: Context only contains information visible in the frame.
    - DROP context does NOT contain future loot information
    - SEARCH context contains loot_gained (already discovered)
    - No target_loot, no hidden state, no future events
    """
    obs_before = frame.observation_before
    obs_after = frame.observation_after
    
    return NarrationContext(
        step=frame.step,
        action_type=frame.action_type,
        event_type=frame.event_type,
        game_minute_before=frame.game_minute_before,
        game_minute_after=frame.game_minute_after,
        location_before=obs_before.get("location_id", ""),
        location_after=obs_after.get("location_id", ""),
        stamina_before=obs_before.get("stamina", 0),
        stamina_after=obs_after.get("stamina", 0),
        max_stamina=obs_before.get("max_stamina", 0),
        inventory_before=copy.deepcopy(obs_before.get("inventory", {})),
        inventory_after=copy.deepcopy(obs_after.get("inventory", {})),
        carried_before=copy.deepcopy(obs_before.get("carried_loot", {})),
        carried_after=copy.deepcopy(obs_after.get("carried_loot", {})),
        event_payload=copy.deepcopy(frame.event_payload),
    )
