"""标准事件的读取、写入和状态增量应用。"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


EVENT_HEADER = re.compile(
    r"^## Turn\s+(\d+)\s+\|[^\n]*\n(.*?)(?=^---\s*$|^## |\Z)",
    re.MULTILINE | re.DOTALL,
)

DAY_MINUTES = 720
TIME_PERIODS = (
    (0, "清晨"),
    (120, "白天"),
    (480, "黄昏"),
    (600, "夜晚"),
)
TIME_PERIOD_STARTS = {name: start for start, name in TIME_PERIODS}

# 视角切分事件类型常量
PERSPECTIVE_CUTAWAY_CREATED = "PERSPECTIVE_CUTAWAY_CREATED"
PERSPECTIVE_CUTAWAY_ENDED = "PERSPECTIVE_CUTAWAY_ENDED"
PERSPECTIVE_CONVERGENCE = "PERSPECTIVE_CONVERGENCE"
PERSPECTIVE_INSIGHT_GAINED = "PERSPECTIVE_INSIGHT_GAINED"
OBSERVATION_OCCURRED = "OBSERVATION_OCCURRED"  # A character observes/assesses another


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


def _add_unique(values: list, additions: Any) -> None:
    if not isinstance(additions, list):
        return
    for value in additions:
        if value not in values:
            values.append(deepcopy(value))


def _apply_target_deltas(world: Dict[str, Any], target_deltas: Any) -> None:
    if not isinstance(target_deltas, Mapping):
        return
    for target_id, delta in target_deltas.items():
        if not isinstance(delta, Mapping):
            continue
        target_copy = None
        locations = []
        for registry_name in ("encounter_entities", "targets", "combat_targets"):
            registry = world.get(registry_name)
            if isinstance(registry, Mapping):
                key = target_id if target_id in registry else next(
                    (candidate for candidate, value in registry.items()
                     if isinstance(value, Mapping) and value.get("id", value.get("name")) == target_id),
                    None,
                )
                if key is not None and isinstance(registry.get(key), Mapping):
                    locations.append((registry, key, registry[key]))
            elif isinstance(registry, list):
                for index, value in enumerate(registry):
                    if isinstance(value, Mapping) and value.get("id", value.get("name")) == target_id:
                        locations.append((registry, index, value))
        if not locations:
            continue
        for key, value in delta.items():
            if isinstance(value, Mapping):
                continue
            if target_copy is None:
                target_copy = deepcopy(dict(locations[0][2]))
                _add_delta(target_copy, str(key), value)
            else:
                _add_delta(target_copy, str(key), value)
        if target_copy is None:
            target_copy = deepcopy(dict(locations[0][2]))
        if "hp" in target_copy:
            target_copy["hp"] = max(0.0, float(target_copy["hp"]))
            if target_copy["hp"] <= 0:
                target_copy["status"] = "dead"
        for registry, key, _ in locations:
            registry[key] = deepcopy(target_copy)


def _apply_area_deltas(world: Dict[str, Any], area_deltas: Any) -> None:
    if not isinstance(area_deltas, Mapping):
        return
    for area_id, delta in area_deltas.items():
        if not isinstance(delta, Mapping):
            continue
        locations = []
        for registry_name in ("areas", "farm_areas"):
            registry = world.get(registry_name)
            if not isinstance(registry, Mapping):
                continue
            key = area_id if area_id in registry else next(
                (candidate for candidate, value in registry.items() if isinstance(value, Mapping) and value.get("id", value.get("name")) == area_id),
                None,
            )
            if key is not None and isinstance(registry.get(key), Mapping):
                locations.append((registry, key, registry[key]))
        for registry, key, area in locations:
            updated_area = deepcopy(dict(area))
            for field, change in delta.items():
                if isinstance(change, Mapping):
                    continue
                _add_delta(updated_area, str(field), change)
            if "monster_population" in updated_area:
                updated_area["monster_population"] = max(0, updated_area["monster_population"])
            if "alertness" in updated_area:
                updated_area["alertness"] = max(0, min(100, updated_area["alertness"]))
            if "monster_adaptation" in updated_area:
                updated_area["monster_adaptation"] = max(0, min(100, updated_area["monster_adaptation"]))
            registry[key] = updated_area


def _apply_encounter_additions(meta: Dict[str, Any], world: Dict[str, Any], additions: Any) -> None:
    if not isinstance(additions, list):
        return
    encounters = meta.setdefault("active_encounters", [])
    if not isinstance(encounters, list):
        encounters = []
        meta["active_encounters"] = encounters
    for addition in additions:
        if not isinstance(addition, Mapping) or not addition.get("id"):
            continue
        entity_additions = addition.get("entity_additions", [])
        entities = world.setdefault("encounter_entities", {})
        if not isinstance(entities, dict):
            entities = {}
            world["encounter_entities"] = entities
        for entity in entity_additions if isinstance(entity_additions, list) else []:
            if isinstance(entity, Mapping) and entity.get("id"):
                entities[str(entity["id"])] = deepcopy(dict(entity))
        encounter = {key: deepcopy(value) for key, value in addition.items() if key != "entity_additions"}
        if not any(isinstance(item, Mapping) and item.get("id") == addition.get("id") for item in encounters):
            encounters.append(encounter)


def _apply_encounter_updates(meta: Dict[str, Any], updates: Any) -> None:
    if not isinstance(updates, list):
        return
    encounters = meta.setdefault("active_encounters", [])
    if not isinstance(encounters, list):
        encounters = []
        meta["active_encounters"] = encounters
    history = meta.setdefault("encounter_history", [])
    for update in updates:
        if not isinstance(update, Mapping) or not update.get("id"):
            continue
        encounter = next((item for item in encounters if isinstance(item, Mapping) and item.get("id") == update.get("id")), None)
        if encounter is None:
            continue
        encounter.update(deepcopy(dict(update)))
        if encounter.get("status", "active") != "active":
            history.append(deepcopy(dict(encounter)))
            encounters[:] = [item for item in encounters if not (isinstance(item, Mapping) and item.get("id") == encounter.get("id"))]
            if meta.get("current_encounter_id") == encounter.get("id"):
                meta["current_encounter_id"] = None
    del history[:-100]


def _cleanup_encounters(meta: Dict[str, Any]) -> None:
    encounters = meta.setdefault("active_encounters", [])
    if not isinstance(encounters, list):
        meta["active_encounters"] = []
        return
    current_turn = int(meta.get("current_turn", 0))
    current_location = meta.get("current_location")
    history = meta.setdefault("encounter_history", [])
    retained = []
    for encounter in encounters:
        if not isinstance(encounter, Mapping):
            continue
        expired = encounter.get("expires_turn") is not None and current_turn >= int(encounter["expires_turn"])
        escaped = current_location is not None and encounter.get("location_id") not in {None, current_location}
        if expired or escaped or encounter.get("status", "active") != "active":
            closed = deepcopy(dict(encounter))
            closed["status"] = "expired" if expired else "escaped" if escaped else closed.get("status")
            closed["closed_turn"] = current_turn
            history.append(closed)
            if meta.get("current_encounter_id") == encounter.get("id"):
                meta["current_encounter_id"] = None
        else:
            retained.append(encounter)
    meta["active_encounters"] = retained
    del history[:-100]


def _apply_relationship_changes(updated: Dict[str, Any], changes: Any) -> None:
    if not isinstance(changes, Mapping):
        return
    relationships = updated.setdefault("relationships", [])
    if not isinstance(relationships, list):
        relationships = []
        updated["relationships"] = relationships
    for relation_id, delta in changes.items():
        if not isinstance(delta, Mapping):
            continue
        relation = next(
            (item for item in relationships if isinstance(item, Mapping) and item.get("npc_id", item.get("id")) == relation_id),
            None,
        )
        if relation is None:
            relation = {"npc_id": relation_id, "trust": 0, "respect": 0, "affection": 0}
            relationships.append(relation)
        for key, value in delta.items():
            if isinstance(value, Mapping):
                continue
            _add_delta(relation, str(key), value)
        # P1-07: Clamp relationship dimensions to [-10, +10].
        for dim in ("trust", "respect", "affection", "fear", "loyalty"):
            if dim in relation:
                try:
                    relation[dim] = max(-10, min(10, float(relation[dim])))
                    if float(relation[dim]).is_integer():
                        relation[dim] = int(relation[dim])
                except (TypeError, ValueError):
                    pass


def _apply_actor_deltas(updated: Dict[str, Any], target_deltas: Any) -> None:
    if not isinstance(target_deltas, Mapping):
        return
    npcs = updated.get("npcs", [])
    for target_id, delta in target_deltas.items():
        if not isinstance(delta, Mapping):
            continue
        npc = next((item for item in npcs if isinstance(item, Mapping) and item.get("id", item.get("name")) == target_id), None) if isinstance(npcs, list) else None
        if npc is None:
            continue
        for field, change in delta.items():
            if not isinstance(change, Mapping):
                _add_delta(npc, str(field), change)
        if float(npc.get("hp", 1)) <= 0:
            npc["status"] = "dead"
            for relation in updated.setdefault("relationships", []) if isinstance(updated.setdefault("relationships", []), list) else []:
                if isinstance(relation, dict) and relation.get("npc_id") == target_id:
                    _add_delta(relation, "trust", -20)
                    _add_delta(relation, "fear", 20)
                    # P1-07: Clamp relationship dimensions to [-10, +10] after death penalty.
                    for dim in ("trust", "respect", "affection", "fear", "loyalty"):
                        if dim in relation:
                            try:
                                relation[dim] = max(-10, min(10, float(relation[dim])))
                                if float(relation[dim]).is_integer():
                                    relation[dim] = int(relation[dim])
                            except (TypeError, ValueError):
                                pass


def _advance_timeline(meta: Dict[str, Any], world: Mapping[str, Any], minutes: float) -> None:
    if minutes <= 0:
        return
    time_of_day = str(meta.get("time_of_day", "清晨"))
    legacy_window = bool(meta.get("time_window_mode") == "legacy" or ("day_elapsed_minutes" not in meta and float(meta.get("available_time_minutes", DAY_MINUTES)) < DAY_MINUTES))
    elapsed = meta.get("day_elapsed_minutes")
    if elapsed is None:
        elapsed = TIME_PERIOD_STARTS.get(time_of_day, 0)
    try:
        elapsed = float(elapsed) + float(minutes)
    except (TypeError, ValueError):
        elapsed = float(minutes)
    day_delta = int(elapsed // DAY_MINUTES)
    elapsed %= DAY_MINUTES
    meta["day_elapsed_minutes"] = int(elapsed) if elapsed.is_integer() else elapsed
    if day_delta:
        meta["game_day"] = int(meta.get("game_day", 1)) + day_delta
    meta["time_of_day"] = next(
        name for start, name in reversed(TIME_PERIODS) if elapsed >= start
    )
    # 新存档由当天已过分钟数直接推导。没有 day_elapsed_minutes 的旧存档保留
    # 原有行动窗口语义，并在本次推进后写入兼容标记，避免改变旧存档的节奏。
    if legacy_window:
        meta["time_window_mode"] = "legacy"
        remaining = max(0.0, float(meta.get("available_time_minutes", DAY_MINUTES)) - float(minutes))
        if day_delta:
            remaining += DAY_MINUTES * day_delta
    else:
        remaining = max(0.0, DAY_MINUTES - elapsed)
    meta["available_time_minutes"] = int(remaining) if remaining.is_integer() else remaining


def _update_narrative_state(meta: Dict[str, Any], player: Mapping[str, Any], inventory: Mapping[str, Any], record: Mapping[str, Any]) -> None:
    narrative = meta.setdefault("narrative_state", {})
    patterns = narrative.setdefault("event_pattern_history", [])
    event_type = str(record.get("type", "UNKNOWN"))
    patterns.append(event_type)
    del patterns[:-50]
    proposed = record.get("data", {}).get("proposed_events", []) if isinstance(record.get("data", {}), Mapping) else []
    irreversible = narrative.setdefault("recent_irreversible_changes", [])
    for item in proposed if isinstance(proposed, list) else []:
        if isinstance(item, Mapping) and item.get("type") in {"AREA_DISCOVERED", "CHARACTER_DIED", "LOOT_GENERATED", "BASE_UPGRADED"}:
            irreversible.append(deepcopy(dict(item)))
    del irreversible[:-20]
    open_loops = narrative.setdefault("open_loops", [])
    payload = record.get("data", {}) if isinstance(record.get("data", {}), Mapping) else {}
    for loop in payload.get("open_loops_additions", []) if isinstance(payload.get("open_loops_additions", []), list) else []:
        if loop not in open_loops:
            open_loops.append(deepcopy(loop))
    resolved_loops = payload.get("open_loops_resolved", [])
    if isinstance(resolved_loops, list):
        narrative["open_loops"] = [loop for loop in open_loops if loop not in resolved_loops and not (isinstance(loop, Mapping) and loop.get("id") in resolved_loops)]
    payoff_history = narrative.setdefault("payoff_history", [])
    metrics = payload.get("runtime_metrics")
    if isinstance(metrics, Mapping) and metrics.get("payoff_score") is not None:
        payoff_history.append({"turn": record.get("turn"), "score": metrics.get("payoff_score"), "event_type": event_type})
        del payoff_history[:-20]
    mystery_records = meta.get("active_mystery_records", [])
    if isinstance(mystery_records, list):
        for mystery in mystery_records:
            if isinstance(mystery, dict):
                mystery["waiting_turns"] = int(mystery.get("waiting_turns", 0)) + 1
    max_hp = max(float(player.get("max_hp", 50)), 1.0)
    hp = max(0.0, min(max_hp, float(player.get("hp", max_hp))))
    resources = inventory.get("resources", {}) if isinstance(inventory.get("resources", {}), Mapping) else {}
    missing_resources = sum(1 for value in resources.values() if float(value or 0) <= 0)
    available = float(meta.get("available_time_minutes", DAY_MINUTES))
    narrative["pressure_components"] = {
        "survival_threat": round((1.0 - hp / max_hp) * 100.0, 6),
        "resource_scarcity": min(100.0, missing_resources * 20.0),
        "time_pressure": max(0.0, min(100.0, (1.0 - available / DAY_MINUTES) * 100.0)),
        "information_unknown": min(100.0, max(0, 5 - len(player.get("knowledge", []))) * 20.0),
        "interpersonal_conflict": 0.0,
        "failure_accumulation": min(100.0, sum(1 for item in patterns[-5:] if "FAIL" in item or "FAILED" in item) * 20.0),
    }
    narrative["current_arc"] = {"last_event_type": event_type, "last_turn": record.get("turn"), "location": meta.get("current_location")}


def _advance_npcs_and_scheduled_events(updated: Dict[str, Any]) -> None:
    meta = updated.setdefault("meta", {})
    time_of_day = str(meta.get("time_of_day", "清晨"))
    system_events = meta.setdefault("system_event_history", [])
    npcs = updated.get("npcs", [])
    from .calculators import calculate_npc_utility

    schedule_slot = f"{int(meta.get('game_day', 1))}:{time_of_day}"
    if isinstance(npcs, list):
        for npc in npcs:
            if not isinstance(npc, dict) or npc.get("status", "alive") != "alive":
                continue
            schedule = npc.get("schedule", {}) if isinstance(npc.get("schedule", {}), Mapping) else {}
            action = schedule.get(time_of_day)
            if not action:
                continue
            if npc.get("last_schedule_execution") == schedule_slot:
                continue
            npc["last_schedule_execution"] = schedule_slot
            if action == "return_to_base":
                # P0-05: 解析真实基地位置，而非玩家当前位置
                base = updated.get("base", {}) if isinstance(updated.get("base", {}), Mapping) else {}
                world = updated.get("world", {}) if isinstance(updated.get("world", {}), Mapping) else {}
                bundle = world.get("generation_bundle", {}) if isinstance(world.get("generation_bundle", {}), Mapping) else {}
                base_location = str(
                    meta.get("base_location")
                    or base.get("location_id")
                    or world.get("starting_location")
                    or bundle.get("starting_location")
                    or "camp_core"
                )
                npc["location"] = base_location
            npc["last_autonomous_action"] = action
            utility = calculate_npc_utility(npc.get("utility_profile", {}))
            if action == "resource_search":
                resources = updated.setdefault("inventory", {}).setdefault("resources", {})
                for resource, quantity in (npc.get("autonomous_yield", {}) or {}).items():
                    _add_delta(resources, str(resource), quantity)
            system_events.append({"type": "NPC_AUTONOMOUS_ACTION", "target": npc.get("id"), "action": action, "utility_score": utility, "time_of_day": time_of_day, "turn": meta.get("current_turn")})
    factions = updated.get("factions", [])
    if isinstance(factions, list):
        for faction in factions:
            if not isinstance(faction, dict) or faction.get("status") == "dissolved":
                continue
            schedule = faction.get("schedule", {}) if isinstance(faction.get("schedule", {}), Mapping) else {}
            action = schedule.get(time_of_day)
            if not action:
                continue
            if faction.get("last_schedule_execution") == schedule_slot:
                continue
            faction["last_schedule_execution"] = schedule_slot
            if action == "collect_tax":
                faction["last_tax_turn"] = meta.get("current_turn")
                faction["treasury"] = deepcopy(faction.get("treasury", {}))
                tax_collected = {}
                resources = updated.setdefault("inventory", {}).setdefault("resources", {})
                for resource, rate in (faction.get("tax_rate", {}) or {}).items():
                    amount = min(max(0.0, float(resources.get(resource, 0))), max(0.0, float(rate)))
                    if amount:
                        _add_delta(resources, str(resource), -amount)
                        _add_delta(faction["treasury"], str(resource), amount)
                        tax_collected[str(resource)] = amount
            faction["last_autonomous_action"] = action
            system_events.append({"type": "FACTION_AUTONOMOUS_ACTION", "target": faction.get("id"), "action": action, "tax_collected": tax_collected if action == "collect_tax" else {}, "utility_score": calculate_npc_utility(faction.get("utility_profile", {})), "time_of_day": time_of_day, "turn": meta.get("current_turn")})
    queue = updated.get("event_queue", [])
    if isinstance(queue, list):
        current_turn = int(meta.get("current_turn", 0))
        current_day = int(meta.get("game_day", 1))
        # P0-02: Use world_turn for time-based scheduled events
        world_turn = int(meta.get("world_turn", current_turn))
        for item in queue:
            if not isinstance(item, dict) or item.get("status", "pending") != "pending":
                continue
            conditions = item.get("trigger_conditions", {}) if isinstance(item.get("trigger_conditions", {}), Mapping) else {}
            trigger_day = conditions.get("day") or conditions.get("game_day")
            trigger_turn = conditions.get("turn")
            # P0-04: ALL declared conditions must be simultaneously satisfied (AND logic).
            # Previously used OR which caused events to fire prematurely when EITHER condition was met.
            # If only one condition type is declared, that single condition is sufficient.
            day_met = trigger_day is None or current_day >= int(trigger_day)
            turn_met = trigger_turn is None or world_turn >= int(trigger_turn)
            has_condition = trigger_day is not None or trigger_turn is not None
            if has_condition and day_met and turn_met:
                item["status"] = "triggered"
                item["triggered_turn"] = current_turn
                system_events.append({"type": "SCHEDULED_EVENT_TRIGGERED", "target": item.get("id"), "turn": current_turn})
    social_state = meta.get("social_state", {}) if isinstance(meta.get("social_state", {}), Mapping) else {}
    for promise in social_state.get("promises", []) if isinstance(social_state.get("promises", []), list) else []:
        if not isinstance(promise, dict) or promise.get("status") != "open":
            continue
        # P0-03: Handle due_turn carefully with proper type checking
        due_turn = promise.get("due_turn")
        if due_turn is not None and isinstance(due_turn, (int, float)):
            if world_turn >= int(due_turn):
                promise["status"] = "broken"
                _apply_relationship_changes(updated, {promise.get("npc_id"): {"trust": -10, "respect": -3}})
                system_events.append({"type": "PROMISE_BROKEN", "target": promise.get("npc_id"), "promise_id": promise.get("id"), "turn": current_turn})
    disaster_day = meta.get("next_disaster_day")
    disaster = updated.get("world", {}).get("rules", {}).get("disaster", {}) if isinstance(updated.get("world", {}).get("rules", {}), Mapping) else {}
    cycle = int(disaster.get("cycle_days", 7) or 7)
    disaster_type = updated.get("world", {}).get("setting", {}).get("disaster_type", "大型灾难")
    current_day = int(meta.get("game_day", 1))
    if disaster_day is None and cycle > 0:
        first_event = str(disaster.get("first_event", ""))
        match = re.search(r"\d+", first_event)
        disaster_day = int(match.group(0)) if match else cycle
    if disaster_day is not None and cycle > 0 and current_day >= int(disaster_day):
        # 旧实现会按漏掉的每一个周期循环；损坏存档的超大日期会让一次
        # 普通行动卡住。保留最近 50 次可见灾难，并以 O(1) 推进下次日期。
        first_due_day = int(disaster_day)
        missed_count = (current_day - first_due_day) // cycle + 1
        visible_count = min(50, missed_count)
        first_visible_day = first_due_day + (missed_count - visible_count) * cycle
        if missed_count > visible_count:
            system_events.append({
                "type": "DISASTER_HISTORY_COMPACTED",
                "target": disaster_type,
                "skipped_count": missed_count - visible_count,
                "from_day": first_due_day,
                "to_day": first_visible_day - cycle,
            })
        for offset in range(visible_count):
            system_events.append({
                "type": "DISASTER_OCCURRED", "target": disaster_type,
                "day": first_visible_day + offset * cycle,
            })
        disaster_day = first_due_day + missed_count * cycle
    if disaster_day is not None:
        meta["next_disaster_day"] = int(disaster_day)
    del system_events[:-50]


def apply_event(data: Dict[str, Any], record: Mapping[str, Any]) -> Dict[str, Any]:
    """将标准事件中的显式增量应用到状态快照。

    事件必须携带变化，叙述文本不参与状态计算。未知字段保留在事件中，
    但不会被猜测性地写入状态。
    """
    updated = deepcopy(data)
    payload = record.get("data", {})
    if not isinstance(payload, Mapping):
        payload = {}
    event_type = str(record.get("type", ""))
    if isinstance(payload.get("state_restore"), Mapping):
        updated = deepcopy(dict(payload["state_restore"]))
    player = updated.setdefault("player", {})
    meta = updated.setdefault("meta", {})
    inventory = updated.setdefault("inventory", {})
    world = updated.setdefault("world", {})

    # 展示选项是可恢复的主持状态，不是玩家行动：不推进回合、时间、
    # NPC 日程或叙事指标，只保存已经预验证的行动契约。
    if event_type == "OPTIONS_PRESENTED":
        pending_options = payload.get("pending_options", {})
        meta["pending_options"] = deepcopy(dict(pending_options)) if isinstance(pending_options, Mapping) else {}
        meta["pending_options_state_turn"] = int(payload.get("state_turn", meta.get("current_turn", 0)))
        return updated

    # 存档格式升级也必须通过事件账本。只接受固定的投影根键，避免把迁移
    # 事件变成任意状态写入通道。
    if event_type == "PROJECTION_SCHEMA_MIGRATED":
        projection_state = payload.get("projection_state", {})
        allowed_projection_keys = {
            "region_state", "population_state", "public_system_state", "market_state",
            "ranking_state", "comparative_state", "rival_state", "player_talent",
        }
        if isinstance(projection_state, Mapping):
            for key, value in projection_state.items():
                if key in allowed_projection_keys:
                    updated[key] = deepcopy(value)
        return updated

    # 公共系统推进与主角行动分开落账：前者只能覆盖固定的群体投影，
    # 不能借由事件变成任意状态写入入口。这样 SQLite 重放也能复原同区
    # 人口、频道、排行榜和对比状态。
    if event_type == "PUBLIC_SYSTEM_ADVANCED":
        projection_state = payload.get("projection_state", {})
        allowed_public_keys = {
            "population_state", "public_system_state", "market_state",
            "ranking_state", "comparative_state", "rival_state",
        }
        if isinstance(projection_state, Mapping):
            for key, value in projection_state.items():
                if key in allowed_public_keys and isinstance(value, Mapping):
                    updated[key] = deepcopy(dict(value))
        return updated
    
    # 视角切分事件处理
    if event_type == PERSPECTIVE_CUTAWAY_CREATED:
        cutaway_context = payload.get("cutaway_context", {})
        if isinstance(cutaway_context, Mapping):
            cutaway_contexts = meta.setdefault("cutaway_contexts", [])
            if not isinstance(cutaway_contexts, list):
                cutaway_contexts = []
                meta["cutaway_contexts"] = cutaway_contexts
            thread_id = cutaway_context.get("thread_id") or cutaway_context.get("id")
            if thread_id:
                existing_indices = [
                    i for i, ctx in enumerate(cutaway_contexts)
                    if isinstance(ctx, Mapping) and (ctx.get("thread_id") or ctx.get("id")) == thread_id
                ]
                if existing_indices:
                    cutaway_contexts[existing_indices[0]] = deepcopy(dict(cutaway_context))
                else:
                    cutaway_contexts.append(deepcopy(dict(cutaway_context)))
            active_threads = meta.setdefault("active_perspective_threads", 0)
            meta["active_perspective_threads"] = int(active_threads) + 1
    
    elif event_type == PERSPECTIVE_CUTAWAY_ENDED:
        thread_id = payload.get("thread_id") or payload.get("cutaway_id")
        if thread_id:
            cutaway_contexts = meta.get("cutaway_contexts", [])
            if isinstance(cutaway_contexts, list):
                ended_contexts = [
                    ctx for ctx in cutaway_contexts
                    if isinstance(ctx, Mapping) and (ctx.get("thread_id") or ctx.get("id")) == thread_id
                ]
                if ended_contexts:
                    ended_contexts[0]["ended"] = True
                    ended_contexts[0]["end_turn"] = int(record.get("turn", meta.get("current_turn", 0)))
            active_threads = meta.get("active_perspective_threads", 1)
            if active_threads > 0:
                meta["active_perspective_threads"] = int(active_threads) - 1

    elif event_type == OBSERVATION_OCCURRED:
        # Record observation in meta without changing protagonist knowledge
        observations = meta.setdefault("observations", [])
        if not isinstance(observations, list):
            observations = []
            meta["observations"] = observations

        observation_record = {
            "observer_id": payload.get("observer_id"),
            "target_id": payload.get("target_id"),
            "subject": payload.get("subject"),
            "turn": record.get("turn"),
            "prior_belief": payload.get("prior_belief", {}),
            "evidence": payload.get("evidence", {}),
            "revealed_result": payload.get("revealed_result", {}),
            "belief_change": payload.get("belief_change", {}),
            "behavioral_consequences": payload.get("behavioral_consequences", []),
            "assessment_style": payload.get("assessment_style", "qualitative_band"),
        }
        observations.append(observation_record)

        # Also update observer's belief if they're an NPC/peer
        # P0-06: 兼容 NPC 存储为列表和 dict 两种格式
        observer_id = payload.get("observer_id")
        if observer_id:
            npcs = updated.get("npcs", [])
            observer_npc = None
            if isinstance(npcs, dict):
                if observer_id in npcs and isinstance(npcs[observer_id], dict):
                    observer_npc = npcs[observer_id]
            elif isinstance(npcs, list):
                observer_npc = next(
                    (n for n in npcs if isinstance(n, dict) and n.get("id") == observer_id),
                    None,
                )
            if observer_npc is not None:
                beliefs = observer_npc.setdefault("beliefs", {})
                beliefs[payload.get("subject", "unknown")] = (
                    payload.get("belief_change", {}).get("new_estimate", "unknown")
                )

        return updated

    for key, delta in (payload.get("player_delta", {}) or {}).items():
        if isinstance(delta, Mapping):
            target_mapping = player.setdefault(str(key), {})
            if isinstance(target_mapping, dict):
                for nested_key, nested_delta in delta.items():
                    if not isinstance(nested_delta, Mapping):
                        _add_delta(target_mapping, str(nested_key), nested_delta)
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
    
    # P1-07: Apply per-resource minimum limits from world registry instead of blanket max(0)
    world = updated.setdefault("world", {})
    if isinstance(world, Mapping):
        resource_rules = world.get("resource_rules", {})
    else:
        resource_rules = {}
    
    for key in list(resources):
        try:
            value = float(resources[key])
            # Check if there's a specific minimum for this resource
            rule = resource_rules.get(str(key), {})
            if isinstance(rule, Mapping):
                minimum = float(rule.get("minimum", 0.0))
            else:
                minimum = 0.0
            value = max(minimum, value)
            if value.is_integer():
                value = int(value)
            resources[key] = value
        except (TypeError, ValueError):
            pass

    item_additions = payload.get("item_additions", [])
    if isinstance(item_additions, list):
        items = inventory.setdefault("items", [])
        if not isinstance(items, list):
            items = []
            inventory["items"] = items
        for addition in item_additions:
            if not isinstance(addition, Mapping):
                continue
            item_id = addition.get("id", addition.get("name"))
            existing = next((item for item in items if isinstance(item, Mapping) and item.get("id", item.get("name")) == item_id), None)
            if existing is None:
                items.append(deepcopy(dict(addition)))
            elif "quantity" in addition:
                _add_delta(existing, "quantity", addition.get("quantity", 0))

    _add_unique(player.setdefault("knowledge", []), payload.get("knowledge_additions"))
    _add_unique(player.setdefault("discovered_locations", []), payload.get("discover_locations"))
    _add_unique(player.setdefault("status_effects", []), payload.get("status_additions"))
    if "current_location" in payload and payload.get("current_location") is not None:
        meta["current_location"] = payload["current_location"]
    if "current_location_name" in payload and payload.get("current_location_name") is not None:
        meta["current_location_name"] = payload["current_location_name"]
    if "current_encounter_id" in payload:
        meta["current_encounter_id"] = payload.get("current_encounter_id")
    if payload.get("information_completeness") is not None:
        meta["last_information_completeness"] = float(payload["information_completeness"])
    _apply_target_deltas(world, payload.get("target_deltas"))
    _apply_actor_deltas(updated, payload.get("target_deltas"))
    _apply_area_deltas(world, payload.get("area_deltas"))
    _apply_encounter_additions(meta, world, payload.get("encounter_additions"))
    _apply_encounter_updates(meta, payload.get("encounter_updates"))
    _apply_relationship_changes(updated, payload.get("relationship_changes"))
    social_state = meta.setdefault("social_state", {"promises": [], "deceptions": []})
    if isinstance(social_state, dict):
        for promise in payload.get("promise_additions", []) if isinstance(payload.get("promise_additions", []), list) else []:
            if isinstance(promise, Mapping):
                social_state.setdefault("promises", []).append(deepcopy(dict(promise)))
        for deception in payload.get("deception_attempts", []) if isinstance(payload.get("deception_attempts", []), list) else []:
            if isinstance(deception, Mapping):
                social_state.setdefault("deceptions", []).append(deepcopy(dict(deception)))

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

        talent_deck = world.get("talent_deck", []) if isinstance(world, Mapping) else []
        updated["player"] = advance_progression(player, payload["experience_gain"], talent_deck)
        player = updated["player"]

    talent_choice = payload.get("talent_choice")
    if isinstance(talent_choice, Mapping):
        selected_id = str(talent_choice.get("id", ""))
        pending = player.get("pending_decision", {}) if isinstance(player.get("pending_decision", {}), Mapping) else {}
        options = pending.get("options", []) if isinstance(pending, Mapping) else []
        if selected_id and any(isinstance(option, Mapping) and str(option.get("id")) == selected_id for option in options):
            selected = deepcopy(dict(talent_choice))
            player.setdefault("talents", []).append(selected)
            effect = selected.get("effect", {}) if isinstance(selected.get("effect", {}), Mapping) else {}
            for attribute, delta in (effect.get("attribute_bonus", {}) or {}).items():
                _add_delta(player.setdefault("attributes", {}), str(attribute), delta)
            modifiers = player.setdefault("talent_effects", {}).setdefault("action_modifiers", {})
            for action_type, values in (effect.get("action_modifiers", {}) or {}).items():
                target = modifiers.setdefault(str(action_type), {})
                for key, delta in (values or {}).items():
                    _add_delta(target, str(key), delta)
            # P1-08: Advance the pending_decision_queue. Remove the resolved
            # entry and promote the next one (if any) to pending_decision.
            queue = player.get("pending_decision_queue", []) if isinstance(player.get("pending_decision_queue"), list) else []
            if queue:
                queue.pop(0)
            player["pending_decision_queue"] = queue
            if queue:
                player["pending_decision"] = deepcopy(dict(queue[0]))
                player["talent_choice_required"] = True
            else:
                player.pop("pending_decision", None)
                player["talent_choice_required"] = False

    # P0-02: current_turn increments for every event, world_turn only for time_cost > 0
    if payload.get("time_cost") is not None:
        _advance_timeline(meta, world, float(payload.get("time_cost", 0)))
            
        # Increment world_turn only when time_cost > 0 (P0-02 fix)
        world_turn = meta.get("world_turn", meta.get("current_turn", 0))
        if float(payload.get("time_cost", 0)) > 0:
            meta["world_turn"] = world_turn + 1
        
    if isinstance(payload.get("narrative_state"), Mapping):
        meta["narrative_state"] = deepcopy(dict(payload["narrative_state"]))
    if isinstance(payload.get("runtime_metrics"), Mapping):
        meta["runtime_metrics"] = deepcopy(dict(payload["runtime_metrics"]))

    # 玩家一旦提交行动，旧选项立即失效。清理由投影器执行，保证实时
    # 状态与 SQLite 事件重放拥有相同语义。
    if record.get("actor") == "player":
        meta.pop("pending_options", None)
        meta.pop("pending_options_state_turn", None)
        if event_type == "REACTION_RESOLVED":
            meta.pop("pending_reaction", None)
    if event_type in {"COMBAT_RESOLVED", "COMBAT_ENDED"}:
        meta["total_combats"] = int(meta.get("total_combats", 0)) + 1
    if event_type in {"ACTION_RESOLVED", "EXPLORATION_RESOLVED", "ATTRIBUTES_ALLOCATED"}:
        meta["total_decisions"] = int(meta.get("total_decisions", 0)) + 1
        if str(payload.get("action", {}).get("type", "")) == "EXPLORATION":
            meta["total_explorations"] = int(meta.get("total_explorations", 0)) + 1
    if payload.get("target_died"):
        stats = player.setdefault("stats", {})
        _add_delta(stats, "kills", 1)
    if payload.get("player_died"):
        stats = player.setdefault("stats", {})
        _add_delta(stats, "deaths", 1)
        player["status"] = "dead"
        player["death_turn"] = int(record.get("turn", meta.get("current_turn", 0)))
        meta["campaign_status"] = "ended"
        meta["ending_id"] = f"death_day_{meta.get('game_day', 1)}_turn_{record.get('turn', meta.get('current_turn', 0))}"
        meta["ending_summary"] = {
            "ending_id": meta["ending_id"],
            "reason": payload.get("death_reason", "玩家生命归零"),
            "turn": int(record.get("turn", meta.get("current_turn", 0))),
        }
    if payload.get("checkpoint_increment"):
        meta["checkpoints_used"] = int(meta.get("checkpoints_used", 0)) + int(payload.get("checkpoint_increment", 0))
    _update_narrative_state(meta, player, inventory, record)

    # P0-01: Every time-advancing action decrements cooldown_remaining by 1
    # for all skills. Zero-time actions (ATTRIBUTE_ALLOCATION, TALENT_SELECTION)
    # are excluded because their time_cost is 0.
    time_cost = float(payload.get("time_cost", 0) or 0)
    # P1-05: Only decrement cooldowns when the actor is the player
    if record.get("actor") == "player" and time_cost > 0:
        from .calculators import tick_cooldowns
        player.update(tick_cooldowns(player))

    cooldown_changes = payload.get("cooldown_changes", {})
    for skill in player.get("skills", []) if isinstance(player.get("skills"), list) else []:
        if isinstance(skill, dict) and skill.get("id") in cooldown_changes:
            skill["cooldown_remaining"] = max(0, int(cooldown_changes[skill["id"]]))

    meta["current_turn"] = int(record.get("turn", meta.get("current_turn", 0)))
    _cleanup_encounters(meta)
    # P0-07: 零时间行动（time_cost == 0，如 ATTRIBUTE_ALLOCATION、TALENT_CHOICE）
    # 不应推进 NPC 日程、定时事件队列和灾难计时器。
    if time_cost > 0:
        _advance_npcs_and_scheduled_events(updated)
    meta["event_format_version"] = max(2, int(meta.get("event_format_version", 1)))
    # 回放必须得到同一状态；不能在投影器里写入当前墙上时间。
    meta["last_played"] = str(record.get("timestamp") or meta.get("last_played", ""))
    return updated
