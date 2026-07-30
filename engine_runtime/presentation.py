"""将内部结算结果转换为可交给玩家的最小结果视图。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def player_facing_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """不暴露公式、事件协议、数据库或内部行动标识。"""
    event = result.get("event", {}) if isinstance(result.get("event", {}), Mapping) else {}
    payload = event.get("data", {}) if isinstance(event.get("data", {}), Mapping) else {}
    resolution = result.get("resolution", {}) if isinstance(result.get("resolution", {}), Mapping) else {}
    if not resolution and isinstance(result.get("results"), list):
        resolutions = [item.get("resolution", {}) for item in result["results"] if isinstance(item, Mapping)]
        resolution = next((item for item in reversed(resolutions) if isinstance(item, Mapping) and item), {})
    visible: dict[str, Any] = {}
    if resolution.get("outcome"):
        visible["outcome"] = resolution["outcome"]
    if resolution.get("allocations"):
        visible["attribute_allocations"] = deepcopy(resolution["allocations"])
    if payload.get("movement"):
        visible["movement"] = deepcopy(payload["movement"])
    for key in ("resource_changes", "knowledge_additions", "discover_locations", "relationship_changes", "base_module", "reaction_effect", "attribute_allocations"):
        if payload.get(key) not in (None, {}, []):
            visible[key] = deepcopy(payload[key])
    if payload.get("player_died"):
        visible["status"] = "死亡"
    elif payload.get("target_died"):
        visible["status"] = "目标已失去战斗能力"
    state = result.get("state", {}) if isinstance(result.get("state", {}), Mapping) else {}
    meta = state.get("meta", {}) if isinstance(state.get("meta", {}), Mapping) else {}
    if meta.get("current_location"):
        visible["current_location"] = meta["current_location"]
    if meta.get("game_day") is not None:
        visible["game_day"] = meta["game_day"]
    if meta.get("time_of_day"):
        visible["time_of_day"] = meta["time_of_day"]
    return visible
