"""标准事件的读取、写入和状态增量应用。"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


EVENT_HEADER = re.compile(
    r"^## Turn\s+(\d+)\s+\|[^\n]*\n(.*?)(?=^---\s*$|^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def parse_events(text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for match in EVENT_HEADER.finditer(text):
        json_match = re.search(r"```json\s*(.*?)```", match.group(0), re.DOTALL)
        if not json_match:
            continue
        try:
            payload = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            continue
        records = payload if isinstance(payload, list) else [payload]
        for record in records:
            if isinstance(record, dict):
                events.append({"turn": int(match.group(1)), "record": record})
    return sorted(events, key=lambda item: (item["turn"], item["record"].get("event_id", "")))


def standard_event(event_id: str, event_type: str, actor: str, target: Any, data: Mapping[str, Any], turn: int, timestamp: str) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "type": event_type,
        "actor": actor,
        "target": target,
        "data": deepcopy(dict(data)),
        "turn": int(turn),
        "timestamp": timestamp,
    }


def append_event(path: Path, record: Mapping[str, Any]) -> None:
    if not path.exists():
        path.write_text("# 事件日志\n\n", encoding="utf-8")
    existing = path.read_text(encoding="utf-8")
    turn = int(record.get("turn", 0))
    timestamp = record.get("timestamp", "")
    block = "\n---\n## Turn {turn} | {timestamp}\n```json\n{payload}\n```\n".format(
        turn=turn,
        timestamp=timestamp,
        payload=json.dumps([dict(record)], ensure_ascii=False, indent=2),
    )
    path.write_text(existing.rstrip() + block, encoding="utf-8")


def _add_delta(mapping: Dict[str, Any], key: str, delta: Any) -> None:
    try:
        mapping[key] = float(mapping.get(key, 0)) + float(delta)
        if mapping[key].is_integer():
            mapping[key] = int(mapping[key])
    except (TypeError, ValueError):
        mapping[key] = delta


def apply_event(data: Dict[str, Any], record: Mapping[str, Any]) -> Dict[str, Any]:
    """将标准事件中的显式增量应用到状态快照。

    事件必须携带变化，叙述文本不参与状态计算。未知字段保留在事件中，
    但不会被猜测性地写入状态。
    """
    updated = deepcopy(data)
    payload = record.get("data", {})
    if not isinstance(payload, Mapping):
        payload = {}
    player = updated.setdefault("player", {})
    meta = updated.setdefault("meta", {})
    inventory = updated.setdefault("inventory", {})

    for key, delta in (payload.get("player_delta", {}) or {}).items():
        if isinstance(delta, Mapping):
            continue
        _add_delta(player, str(key), delta)
    for key, delta in {
        "fatigue": payload.get("fatigue_delta", 0),
        "hunger": payload.get("hunger_delta", 0),
        "mental": payload.get("mental_delta", 0),
        "hp": payload.get("hp_delta", 0),
    }.items():
        if delta:
            _add_delta(player, key, delta)
    if "fatigue" in player:
        player["fatigue"] = max(0, min(100, player["fatigue"]))
    if "hunger" in player:
        player["hunger"] = max(0, min(100, player["hunger"]))
    if "mental" in player:
        player["mental"] = max(0, min(100, player["mental"]))
    if "hp" in player and "max_hp" in player:
        player["hp"] = max(0, min(player["max_hp"], player["hp"]))

    resources = inventory.setdefault("resources", {})
    for key, delta in (payload.get("resource_changes", {}) or {}).items():
        _add_delta(resources, str(key), delta)

    base = updated.setdefault("base", {})
    if payload.get("base_space_delta"):
        _add_delta(base, "space_used", payload["base_space_delta"])
    if payload.get("base_durability_delta"):
        _add_delta(base, "durability", payload["base_durability_delta"])
    if isinstance(payload.get("base_module"), Mapping):
        base.setdefault("modules", []).append(deepcopy(dict(payload["base_module"])))
    for slot, durability in (payload.get("equipment_durability", {}) or {}).items():
        equipment = inventory.setdefault("equipment", {})
        if isinstance(equipment.get(slot), dict):
            equipment[slot]["durability"] = durability
    for slot, updates in (payload.get("equipment_updates", {}) or {}).items():
        equipment = inventory.setdefault("equipment", {})
        if isinstance(equipment.get(slot), dict) and isinstance(updates, Mapping):
            equipment[slot].update(deepcopy(dict(updates)))

    if payload.get("experience_gain"):
        from .calculators import advance_progression

        updated["player"] = advance_progression(player, payload["experience_gain"])
        player = updated["player"]

    if payload.get("time_cost") is not None:
        try:
            available = float(meta.get("available_time_minutes", 240))
            remaining = max(0.0, available - float(payload.get("time_cost", 0)))
            meta["available_time_minutes"] = int(remaining) if remaining.is_integer() else remaining
        except (TypeError, ValueError):
            pass

    cooldown_changes = payload.get("cooldown_changes", {})
    for skill in player.get("skills", []) if isinstance(player.get("skills"), list) else []:
        if isinstance(skill, dict) and skill.get("id") in cooldown_changes:
            skill["cooldown_remaining"] = max(0, int(cooldown_changes[skill["id"]]))

    meta["current_turn"] = int(record.get("turn", meta.get("current_turn", 0)))
    meta["event_format_version"] = max(2, int(meta.get("event_format_version", 1)))
    meta["last_played"] = datetime.now().astimezone().isoformat(timespec="seconds")
    return updated
