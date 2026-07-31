"""Watch rendering and export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AutoplayRunResult, WatchFrame


def format_game_minute(minutes: int) -> str:
    """Format game minute as HH:MM string."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def render_frame(frame: WatchFrame) -> str:
    """
    Render a single watch frame as deterministic text.
    
    100% based on structured frame data.
    No prose, no invented facts.
    """
    lines = []
    
    # Decision header
    lines.append(f"[{format_game_minute(frame.game_minute_before)}] 决策 #{frame.step}")
    
    obs_before = frame.observation_before
    lines.append(f"位置: {obs_before.get('location_id', '?')}")
    lines.append(f"体力: {obs_before.get('stamina', '?')}/{obs_before.get('max_stamina', '?')}")
    
    # Legal actions
    legal_actions = obs_before.get("legal_actions", ())
    lines.append("可选行动:")
    for la in legal_actions:
        if la.action_type == "WAIT":
            lines.append(f"  - {la.action_type}")
        else:
            duration = la.duration_minutes if la.duration_minutes is not None else 0
            stamina = la.stamina_cost
            lines.append(f"  - {la.action_type} ({duration} 分钟 / {stamina} 体力)")
    
    lines.append("")
    lines.append(f"[BOT] {frame.action_type}")
    lines.append("")
    
    # Event
    lines.append(f"[{format_game_minute(frame.game_minute_after)}] {frame.event_type}")
    
    obs_after = frame.observation_after
    
    # Action-specific rendering
    if frame.action_type == "DROP":
        lines.append(f"位置: {obs_before.get('location_id', '?')} → {obs_after.get('location_id', '?')}")
        lines.append(f"体力: {obs_before.get('stamina', '?')} → {obs_after.get('stamina', '?')}")
    
    elif frame.action_type == "SEARCH":
        # Show carried loot gained
        carried = obs_after.get("carried_loot", {})
        if carried:
            lines.append("获得并携带:")
            for resource_id, qty in carried.items():
                lines.append(f"  - {resource_id} ×{qty}")
        lines.append(f"体力: {obs_before.get('stamina', '?')} → {obs_after.get('stamina', '?')}")
    
    elif frame.action_type == "EXTRACT":
        # Show inventory gained
        inventory_before = obs_before.get("inventory", {})
        inventory_after = obs_after.get("inventory", {})
        
        # Calculate what was added
        added = {}
        for resource_id, qty in inventory_after.items():
            old_qty = inventory_before.get(resource_id, 0)
            if qty > old_qty:
                added[resource_id] = qty - old_qty
        
        lines.append(f"安全返回: {obs_after.get('location_id', '?')}")
        if added:
            lines.append("入库:")
            for resource_id, qty in added.items():
                lines.append(f"  - {resource_id} ×{qty}")
    
    return "\n".join(lines)


def render_run(run_result: AutoplayRunResult) -> str:
    """
    Render complete autoplay run as deterministic text.
    
    Returns human-readable watch mode output.
    """
    lines = []
    
    lines.append("=== TheGreatNovel Watch Mode ===")
    lines.append("")
    lines.append(f"Initial hash: {run_result.initial_state_hash[:16]}...")
    lines.append("")
    
    for frame in run_result.frames:
        lines.append(render_frame(frame))
        lines.append("")
        lines.append("-" * 50)
        lines.append("")
    
    lines.append("=== RUN COMPLETE ===")
    lines.append("")
    lines.append(f"decisions: {run_result.decisions}")
    lines.append(f"events: {run_result.events}")
    
    # Handle StopReason enum
    stop_reason = run_result.stop_reason
    if hasattr(stop_reason, "value"):
        stop_reason = stop_reason.value
    lines.append(f"stop_reason: {stop_reason}")
    
    # Final inventory
    final_obs = run_result.frames[-1].observation_after if run_result.frames else {}
    inventory = final_obs.get("inventory", {})
    if inventory:
        lines.append("final inventory:")
        for resource_id, qty in inventory.items():
            lines.append(f"  - {resource_id} ×{qty}")
    
    lines.append("")
    lines.append(f"final_hash: {run_result.final_state_hash[:16]}...")
    
    return "\n".join(lines)


def write_run_jsonl(run_result: AutoplayRunResult, path: Path) -> None:
    """
    Export run as JSONL file.
    
    Each line is one frame.
    Last line is run summary.
    
    JSONL is export/debug artifact, not runtime truth.
    """
    with open(path, "w", encoding="utf-8") as f:
        # Write frames
        for frame in run_result.frames:
            frame_data = {
                "step": frame.step,
                "action_id": frame.action_id,
                "actor_id": frame.actor_id,
                "action_type": frame.action_type,
                "event_type": frame.event_type,
                "game_minute_before": frame.game_minute_before,
                "game_minute_after": frame.game_minute_after,
                "event_payload": frame.event_payload,
                "state_hash_before": frame.state_hash_before,
                "state_hash_after": frame.state_hash_after,
            }
            f.write(json.dumps(frame_data, ensure_ascii=False, sort_keys=True) + "\n")
        
        # Write summary
        summary = run_result.summary()
        f.write(json.dumps(summary, ensure_ascii=False, sort_keys=True) + "\n")
