"""Novel watch renderer - renders narrated frames."""

from __future__ import annotations

from typing import Any

from ..autoplay.models import AutoplayRunResult, StopReason
from ..autoplay.watch import format_game_minute
from .models import NarratedFrame, NarrationRunResult


def render_narrated_run(
    narration_result: NarrationRunResult,
) -> str:
    """
    Render a narrated run as novel watch output.
    
    Combines:
    - LLM-generated narration (prose)
    - Deterministic system panels (from WatchFrame)
    - Run summary
    
    Format inspired by the spec example.
    """
    run = narration_result.source_run
    frames = narration_result.narrated_frames
    
    sections = []
    
    # Header
    sections.append("=== TheGreatNovel Novel Watch ===")
    sections.append("")
    
    # Render each narrated frame
    for narrated in frames:
        # Find corresponding watch frame
        watch_frame = run.frames[narrated.step - 1]  # step is 1-indexed
        
        sections.append(f"[{format_game_minute(watch_frame.game_minute_before)} → {format_game_minute(watch_frame.game_minute_after)}]")
        sections.append("")
        sections.append(narrated.narration)
        sections.append("")
        
        # System panel based on action type
        if narrated.action_type == "DROP":
            sections.append("[行动]")
            sections.append("DROP")
            sections.append(f"时间：{format_game_minute(watch_frame.game_minute_before)} → {format_game_minute(watch_frame.game_minute_after)}")
            sections.append(f"体力：{watch_frame.observation_before['stamina']} → {watch_frame.observation_after['stamina']}")
        
        elif narrated.action_type == "SEARCH":
            sections.append("[行动]")
            sections.append("SEARCH")
            
            # Show loot gained
            loot_gained = watch_frame.event_payload.get("loot_gained", {})
            if loot_gained:
                sections.append("[获得并携带]")
                for resource, qty in loot_gained.items():
                    sections.append(f"{resource} ×{qty}")
            
            sections.append(f"体力：{watch_frame.observation_before['stamina']} → {watch_frame.observation_after['stamina']}")
        
        elif narrated.action_type == "EXTRACT":
            sections.append("[行动]")
            sections.append("EXTRACT")
            
            # Show inventory gained
            inventory_before = watch_frame.observation_before.get("inventory", {})
            inventory_after = watch_frame.observation_after.get("inventory", {})
            
            # Calculate delta
            delta = {}
            for resource, qty in inventory_after.items():
                before = inventory_before.get(resource, 0)
                if qty > before:
                    delta[resource] = qty - before
            
            if delta:
                sections.append("[入库]")
                for resource, qty in delta.items():
                    sections.append(f"{resource} ×{qty}")
        
        sections.append("")
        sections.append("---")
        sections.append("")
    
    # Footer
    if run.stop_reason == StopReason.POLICY_COMPLETE:
        sections.append("=== RUN COMPLETE ===")
    else:
        sections.append("=== RUN STOPPED ===")
        sections.append(f"stop_reason: {run.stop_reason}")
    
    sections.append("")
    sections.append(f"decisions: {run.decisions}")
    sections.append(f"events: {run.events}")
    
    if narration_result.narration_failures > 0:
        sections.append(f"narration_failures: {narration_result.narration_failures}")
    
    return "\n".join(sections)
