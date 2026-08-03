"""Pure deterministic state engine for the first TGN implementation."""

from __future__ import annotations

import hashlib
import hmac
import json
import random
from copy import deepcopy
from typing import Any, Mapping

from ..contracts import ActionPreview, EngineResolution, EventDraft
from ..hashing import canonical_json, sha256_json


BUSINESS_ROOTS = {"player", "actors", "world", "opportunities", "unlocks", "metrics"}


def state_hash(state: Mapping[str, Any]) -> str:
    return sha256_json(state)


def _path_parts(path: str) -> list[str]:
    if not isinstance(path, str) or not path or path.startswith(".") or path.endswith("."):
        raise ValueError("invalid_state_path")
    parts = path.split(".")
    if parts[0] not in BUSINESS_ROOTS or any(not p or p.startswith("_") for p in parts):
        raise ValueError("invalid_state_path")
    return parts


def _get(state: Any, path: str, default: Any = None) -> Any:
    try:
        parts = _path_parts(path)
    except ValueError:
        return default
    node = state
    for part in parts:
        if not isinstance(node, Mapping) or part not in node:
            return default
        node = node[part]
    return node


def _set(state: dict[str, Any], path: str, value: Any) -> None:
    parts = _path_parts(path)
    node: dict[str, Any] = state
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = deepcopy(value)


def _delete(state: dict[str, Any], path: str) -> None:
    parts = _path_parts(path)
    node: Any = state
    for part in parts[:-1]:
        if not isinstance(node, Mapping) or part not in node:
            return
        node = node[part]
    if isinstance(node, dict):
        node.pop(parts[-1], None)
    elif isinstance(node, list):
        try:
            node.remove(parts[-1])
        except ValueError:
            pass


def _state_value(state: Mapping[str, Any], value: Any, *, path_hint: bool = False) -> Any:
    if isinstance(value, Mapping) and set(value) == {"path"}:
        return _get(state, str(value["path"]))
    if isinstance(value, str) and (value.startswith("$") or path_hint):
        path = value[1:] if value.startswith("$") else value
        if path.split(".", 1)[0] in BUSINESS_ROOTS:
            return _get(state, path)
    return value


def evaluate_condition(state: Mapping[str, Any], condition: Any) -> bool:
    if condition is None:
        return True
    if not isinstance(condition, Mapping) or len(condition) != 1:
        return False
    op, operand = next(iter(condition.items()))
    if op == "all":
        return all(evaluate_condition(state, child) for child in operand)
    if op == "any":
        return any(evaluate_condition(state, child) for child in operand)
    if op == "not":
        return not evaluate_condition(state, operand)
    if op == "truthy":
        return bool(_state_value(state, operand, path_hint=True))
    if op in {"eq", "ne", "gte", "lte", "gt", "lt", "contains"}:
        if not isinstance(operand, (list, tuple)) or len(operand) != 2:
            return False
        left = _state_value(state, operand[0], path_hint=True)
        right = _state_value(state, operand[1], path_hint=False)
        try:
            if op == "eq":
                return left == right
            if op == "ne":
                return left != right
            if op == "gte":
                return left >= right
            if op == "lte":
                return left <= right
            if op == "gt":
                return left > right
            if op == "lt":
                return left < right
            return right in left
        except (TypeError, ValueError):
            return False
    return False


def _has_hidden_marker(value: Any) -> bool:
    if isinstance(value, Mapping):
        if value.get("visibility") not in (None, "public", "player"):
            return True
        return any(_has_hidden_marker(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_hidden_marker(item) for item in value)
    return False


def _condition_touches_hidden(state: Mapping[str, Any], condition: Any) -> bool:
    if not isinstance(condition, Mapping) or len(condition) != 1:
        return False
    op, operand = next(iter(condition.items()))
    if op in {"all", "any"}:
        return any(_condition_touches_hidden(state, child) for child in operand)
    if op == "not":
        return _condition_touches_hidden(state, operand)
    values = operand if op in {"eq", "ne", "gte", "lte", "gt", "lt", "contains"} and isinstance(operand, list) else [operand]
    for value in values:
        path = value.get("path") if isinstance(value, Mapping) and set(value) == {"path"} else value if isinstance(value, str) and value.split(".", 1)[0] in BUSINESS_ROOTS else None
        if path and _has_hidden_marker(_get(state, path)):
            return True
    return False


def apply_patch(state: dict[str, Any], patch: Mapping[str, Any]) -> None:
    op = patch.get("op")
    path = patch.get("path")
    if op not in {"set", "add", "append_unique", "remove", "merge"}:
        raise ValueError("unknown_patch_operator")
    _path_parts(path)
    if op == "set":
        _set(state, path, patch.get("value"))
    elif op == "add":
        amount = patch.get("value")
        current = _get(state, path, 0)
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("add_requires_number")
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            raise ValueError("add_target_requires_number")
        _set(state, path, current + amount)
    elif op == "append_unique":
        current = _get(state, path)
        if current is None:
            current = []
            _set(state, path, current)
        if not isinstance(current, list):
            raise ValueError("append_target_requires_array")
        value = deepcopy(patch.get("value"))
        if value not in current:
            current.append(value)
    elif op == "remove":
        current = _get(state, path)
        if isinstance(current, list) and "value" in patch:
            value = deepcopy(patch.get("value"))
            if value in current:
                current.remove(value)
        else:
            _delete(state, path)
    elif op == "merge":
        value = patch.get("value")
        current = _get(state, path, {})
        if not isinstance(value, Mapping) or not isinstance(current, dict):
            raise ValueError("merge_requires_objects")
        current.update(deepcopy(dict(value)))


def apply_event(state: Mapping[str, Any], event: EventDraft | Mapping[str, Any]) -> dict[str, Any]:
    """Replay one committed event without consulting a world or an LLM."""

    result = deepcopy(dict(state))
    patches = event.patches if isinstance(event, EventDraft) else event.get("patches", ())
    for patch in patches:
        apply_patch(result, patch)
    details = event.details if isinstance(event, EventDraft) else event.get("details", {})
    campaign = result.setdefault("campaign", {})
    if "turn_after" in details:
        campaign["turn"] = int(details["turn_after"])
    if "time_after" in details:
        campaign["time_minute"] = int(details["time_after"])
        # World-local clocks that drive process windows are kept in lockstep
        # with the campaign clock for deterministic storage replay.
        result.setdefault("world", {})["minute"] = int(details["time_after"])
    if "tier_after" in details:
        campaign["current_tier"] = details["tier_after"]
    return result


def _normalize_costs(action: Mapping[str, Any]) -> list[dict[str, Any]]:
    costs = action.get("costs", {})
    if isinstance(costs, Mapping):
        return [{"path": key, "amount": value} for key, value in costs.items()]
    return [dict(item) for item in costs]


def _normalize_extra_costs(action: Mapping[str, Any], use_lever: bool) -> list[dict[str, Any]]:
    if not use_lever or not isinstance(action.get("lever"), Mapping):
        return []
    costs = action["lever"].get("extra_costs", {})
    if isinstance(costs, Mapping):
        return [{"path": key, "amount": value} for key, value in costs.items()]
    return [dict(item) for item in costs]


def _aggregate_costs(costs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, int | float] = {}
    order: list[str] = []
    for cost in costs:
        path = cost["path"]
        if path not in totals:
            order.append(path)
            totals[path] = 0
        totals[path] += cost["amount"]
    return [{"path": path, "amount": totals[path]} for path in order]


def _all_actions(compiled: Mapping[str, Any]) -> list[dict[str, Any]]:
    actions = list(compiled.get("actions", ()))
    for expansion in compiled.get("expansions", ()):
        actions.extend(expansion.get("candidate", {}).get("actions", ()))
    return actions


def _all_processes(compiled: Mapping[str, Any]) -> list[dict[str, Any]]:
    processes = list(compiled.get("processes", ()))
    for expansion in compiled.get("expansions", ()):
        processes.extend(expansion.get("candidate", {}).get("processes", ()))
    return processes


def _all_milestones(compiled: Mapping[str, Any]) -> list[dict[str, Any]]:
    milestones = list(compiled.get("milestones", ()))
    for expansion in compiled.get("expansions", ()):
        milestones.extend(expansion.get("candidate", {}).get("milestones", ()))
    return milestones


def _action_map(compiled: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(a["id"]): a for a in _all_actions(compiled)}


def _active_ids(state: Mapping[str, Any], key: str) -> list[str]:
    values = _get(state, f"world.{key}", [])
    return list(values) if isinstance(values, list) else []


def _action_available(compiled: Mapping[str, Any], state: Mapping[str, Any], action: Mapping[str, Any], *, use_lever: bool = True) -> tuple[bool, str | None]:
    active = _active_ids(state, "active_actions")
    if "active_actions" in state.get("world", {}) and action["id"] not in active:
        return False, "expansion_inactive"
    max_uses = action.get("max_uses")
    if max_uses is not None and int(state.get("world", {}).get("action_counts", {}).get(action["id"], 0)) >= max_uses:
        return False, "max_uses_reached"
    if _condition_touches_hidden(state, action.get("visible_when")) or not evaluate_condition(state, action.get("visible_when")):
        return False, "not_visible"
    if _condition_touches_hidden(state, action.get("legal_when")) or not evaluate_condition(state, action.get("legal_when")):
        return False, "illegal_condition"
    lever = action.get("lever")
    if not use_lever and isinstance(lever, Mapping) and bool(lever.get("required", lever.get("requires", False))):
        return False, "lever_required"
    for cost in _aggregate_costs(_normalize_costs(action) + _normalize_extra_costs(action, use_lever)):
        amount = cost.get("amount", 0)
        if amount < 0:
            return False, "invalid_cost"
        current = _get(state, cost["path"], 0)
        try:
            insufficient = current < amount
        except TypeError:
            return False, "invalid_cost_target"
        if insufficient:
            return False, "insufficient_resource"
    return True, None


def initial_state(compiled: Mapping[str, Any], campaign_id: str, seed: Any) -> dict[str, Any]:
    if not isinstance(campaign_id, str) or not campaign_id:
        raise ValueError("invalid_campaign_id")
    result = deepcopy(dict(compiled["initial_state"]))
    world = result.setdefault("world", {})
    initial_tier = world.get("tier", result.get("player", {}).get("tier", 0))
    result["campaign"] = {
        "campaign_id": campaign_id,
        "seed": deepcopy(seed),
        "status": "active",
        "turn": 0,
        "time_minute": 0,
        "current_tier": initial_tier,
        "worldpack_hash": compiled["blueprint_hash"],
    }
    world.setdefault("process_last_run", {})
    world.setdefault("completed_milestones", [])
    world.setdefault("materialized_expansions", [])
    world.setdefault("action_counts", {})
    for action in _all_actions(compiled):
        world["action_counts"].setdefault(action["id"], 0)
    world["active_actions"] = [a["id"] for a in compiled["actions"]]
    world["active_processes"] = [p["id"] for p in compiled["processes"]]
    return result


def legal_actions(compiled: Mapping[str, Any], state: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for action in _all_actions(compiled):
        legal, reason = _action_available(compiled, state, action)
        if legal:
            result.append({
                "id": action["id"],
                "label": action["label"],
                "description": action["description"],
                "tags": deepcopy(action["tags"]),
                "time_cost": action["time_cost"],
                "known_risks": deepcopy(action["known_risks"]),
                "unknowns": deepcopy(action["unknowns"]),
                "opportunity_costs": deepcopy(action["opportunity_costs"]),
                "requires_lever": isinstance(action.get("lever"), Mapping) and bool(action["lever"].get("required", action["lever"].get("requires", False))),
            })
    return result


def _preview_key(compiled: Mapping[str, Any], state: Mapping[str, Any]) -> bytes:
    material = sha256_json({"seed": state["campaign"].get("seed"), "blueprint_hash": compiled["blueprint_hash"]})
    return material.encode("utf-8")


def _preview_token(compiled: Mapping[str, Any], state: Mapping[str, Any], action_id: str, use_lever: bool) -> str:
    payload = {
        "blueprint_hash": compiled["blueprint_hash"],
        "action_id": action_id,
        "turn": state["campaign"]["turn"],
        "state_hash": state_hash(state),
        "use_lever": bool(use_lever),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(_preview_key(compiled, state), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def preview_action(compiled: Mapping[str, Any], state: Mapping[str, Any], action_id: str, use_lever: bool = True) -> ActionPreview:
    actions = _action_map(compiled)
    action = actions.get(action_id)
    current_hash = state_hash(state)
    turn = int(state["campaign"]["turn"])
    token = _preview_token(compiled, state, action_id, use_lever)
    if action is None:
        return ActionPreview(action_id, turn, current_hash, False, "unknown_action", 0, (), (), (), (), token)
    legal, reason = _action_available(compiled, state, action, use_lever=use_lever)
    if int(action["time_cost"]) <= 0:
        legal, reason = False, "zero_time_action"
    costs = tuple(_aggregate_costs(_normalize_costs(action) + _normalize_extra_costs(action, use_lever)))
    return ActionPreview(action_id, turn, current_hash, legal, reason, int(action["time_cost"]), costs, tuple(action["known_risks"]), tuple(action["unknowns"]), tuple(action["opportunity_costs"]), token)


def _rng_for(state: Mapping[str, Any], action_id: str) -> random.Random:
    campaign = state["campaign"]
    seed_material = canonical_json({"seed": campaign.get("seed"), "turn": campaign["turn"], "action_id": action_id, "state_hash": state_hash(state)})
    digest = hashlib.sha256(seed_material.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))


def _action_success(state: Mapping[str, Any], action: Mapping[str, Any], rng: random.Random, use_lever: bool) -> tuple[bool, float, float]:
    draw = rng.random()
    check = action.get("check")
    if not check:
        return True, draw, 100.0
    probability = float(check.get("base", 0))
    for term in check.get("terms", []):
        value = _get(state, term["path"], 0)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            probability += float(value) * float(term["multiplier"])
    if use_lever:
        probability += float(check.get("lever_bonus", 0))
    probability = max(0.0, min(100.0, probability))
    return draw * 100.0 < probability, draw, probability


def _event(event_type: str, actor_id: str, patches: list[dict[str, Any]], facts: list[dict[str, Any]], details: dict[str, Any]) -> EventDraft:
    return EventDraft(event_type, actor_id, tuple(deepcopy(patches)), tuple(deepcopy(facts)), deepcopy(details))


def _fact_list(items: list[Mapping[str, Any]], source: str, start: int = 0) -> list[dict[str, Any]]:
    facts = []
    for index, item in enumerate(items, start):
        # Fact IDs are allocated by storage when an Event is committed.  An
        # EventDraft must carry only the contract's source fields.
        fact = {key: deepcopy(item[key]) for key in ("text", "visibility", "kind", "source")}
        facts.append(fact)
    return facts


def _process_events(compiled: Mapping[str, Any], state: dict[str, Any], old_time: int, new_time: int, turn: int) -> list[EventDraft]:
    events: list[EventDraft] = []
    process_last_run = state["world"].setdefault("process_last_run", {})
    active_ids = set(_active_ids(state, "active_processes"))
    for process in _all_processes(compiled):
        pid = process["id"]
        if pid not in active_ids:
            continue
        if not evaluate_condition(state, process.get("when")) or not evaluate_condition(state, process.get("active_when")):
            continue
        due_count = 0
        patches: list[dict[str, Any]] = []
        last_run = process_last_run.get(pid)
        next_due = int(process["first_due_minute"]) if last_run is None else int(last_run) + int(process["interval_minutes"])
        while next_due <= new_time:
            patches.extend(deepcopy(process["patches"]))
            last_run = next_due
            next_due += int(process["interval_minutes"])
            process_last_run[pid] = last_run
            due_count += 1
            if due_count > 10000:
                raise ValueError("process_due_overflow")
        if due_count:
            # Keep scheduling data in business `world`, so replay remains patch-only.
            patches.append({"op": "set", "path": f"world.process_last_run.{pid}", "value": process_last_run[pid]})
            facts = _fact_list(process.get("facts", []), f"process:{pid}")
            due_start = int(process["first_due_minute"]) if process_last_run.get(pid) is None else int(process_last_run[pid]) - (due_count - 1) * int(process["interval_minutes"])
            due_times = list(range(due_start, int(process_last_run[pid]) + 1, int(process["interval_minutes"])))
            events.append(_event("PROCESS_TICK", process.get("actor_id", "world"), patches, facts, {"turn_after": turn, "time_after": new_time, "process_id": pid, "due_count": due_count, "due_times": due_times, "old_time": old_time}))
    return events


def _milestone_events(compiled: Mapping[str, Any], state: dict[str, Any], turn: int, time_minute: int) -> list[EventDraft]:
    events: list[EventDraft] = []
    completed = state["world"].setdefault("completed_milestones", [])
    top_milestone_ids = {item["id"] for item in compiled.get("milestones", ())}
    materialized = set(state["world"].get("materialized_expansions", []))
    candidate_milestones: dict[str, str] = {
        item["id"]: expansion["id"]
        for expansion in compiled.get("expansions", ())
        for item in expansion.get("candidate", {}).get("milestones", ())
    }
    for milestone in _all_milestones(compiled):
        if milestone["id"] not in top_milestone_ids and candidate_milestones.get(milestone["id"]) not in materialized:
            continue
        mid = milestone["id"]
        if milestone.get("once", True) and mid in completed:
            continue
        if not evaluate_condition(state, milestone.get("when")):
            continue
        patches = deepcopy(milestone.get("patches", []))
        patches.append({"op": "append_unique", "path": "world.completed_milestones", "value": mid})
        details: dict[str, Any] = {"turn_after": turn, "time_after": time_minute, "milestone_id": mid}
        if milestone.get("tier_to") is not None:
            details["tier_after"] = milestone["tier_to"]
            state["campaign"]["current_tier"] = milestone["tier_to"]
        events.append(_event("MILESTONE_REACHED", "player", patches, _fact_list(milestone.get("facts", []), f"milestone:{mid}"), details))
    return events


def _expansion_events(compiled: Mapping[str, Any], state: dict[str, Any], turn: int, time_minute: int) -> list[EventDraft]:
    events: list[EventDraft] = []
    materialized = state["world"].setdefault("materialized_expansions", [])
    active_actions = state["world"].setdefault("active_actions", [])
    active_processes = state["world"].setdefault("active_processes", [])
    for expansion in compiled.get("expansions", ()):
        eid = expansion["id"]
        if eid in materialized or not evaluate_condition(state, expansion.get("trigger")):
            continue
        candidate = expansion["candidate"]
        patches = [{"op": "append_unique", "path": "world.materialized_expansions", "value": eid}]
        patches.extend(deepcopy(candidate.get("state_patches", [])))
        for item in candidate.get("actions", []):
            aid = item.get("id") if isinstance(item, Mapping) else item
            if aid not in active_actions:
                active_actions.append(aid)
                patches.append({"op": "append_unique", "path": "world.active_actions", "value": aid})
        for item in candidate.get("processes", []):
            pid = item.get("id") if isinstance(item, Mapping) else item
            if pid not in active_processes:
                active_processes.append(pid)
                patches.append({"op": "append_unique", "path": "world.active_processes", "value": pid})
        events.append(_event("EXPANSION_ACTIVATED", "world", patches, [], {"turn_after": turn, "time_after": time_minute, "expansion_id": eid, "parent_hash": compiled["blueprint_hash"], "anchors": deepcopy(expansion["anchors"]), "namespace": candidate["namespace"]}))
    return events


def resolve_action(compiled: Mapping[str, Any], state: Mapping[str, Any], preview_token: str, request_id: str) -> EngineResolution:
    try:
        encoded, signature = preview_token.rsplit(".", 1)
        payload = json.loads(encoded)
        if not hmac.compare_digest(hmac.new(_preview_key(compiled, state), encoded.encode("utf-8"), hashlib.sha256).hexdigest(), signature):
            raise ValueError("tampered_preview")
    except (ValueError, json.JSONDecodeError, AttributeError):
        raise ValueError("tampered_preview") from None
    current_hash = state_hash(state)
    turn = int(state["campaign"]["turn"])
    if payload.get("blueprint_hash") != compiled.get("blueprint_hash") or payload.get("state_hash") != current_hash or payload.get("turn") != turn:
        raise ValueError("stale_preview")
    action_id = payload.get("action_id")
    action = _action_map(compiled).get(action_id)
    if action is None:
        raise ValueError("unknown_action")
    preview = preview_action(compiled, state, action_id, bool(payload.get("use_lever", True)))
    if not preview.legal:
        raise ValueError(preview.reason_code or "illegal_action")
    working = deepcopy(dict(state))
    old_time = int(working["campaign"]["time_minute"])
    new_time = old_time + int(action["time_cost"])
    new_turn = turn + 1
    rng = _rng_for(working, action_id)
    use_lever = bool(payload.get("use_lever", True))
    success, draw, probability = _action_success(working, action, rng, use_lever)
    patches: list[dict[str, Any]] = []
    for cost in _normalize_costs(action) + _normalize_extra_costs(action, use_lever):
        patches.append({"op": "add", "path": cost["path"], "value": -cost["amount"]})
    lever = action.get("lever")
    if use_lever and isinstance(lever, Mapping):
        patches.extend(deepcopy(lever.get("extra_patches", [])))
    branch = action["success"] if success else action["failure"]
    patches.extend(deepcopy(branch["patches"]))
    patches.append({"op": "add", "path": f"world.action_counts.{action_id}", "value": 1})
    detail: dict[str, Any] = {"turn_after": new_turn, "time_after": new_time, "success": success, "use_lever": use_lever, "request_id": request_id, "state_before_hash": current_hash, "success_probability": probability}
    detail["rng_draw"] = draw
    action_event = _event("ACTION_RESOLVED", "player", patches, _fact_list(branch["facts"], f"action:{action_id}"), detail)
    working = apply_event(working, action_event)
    events: list[EventDraft] = [action_event]
    for event in _process_events(compiled, working, old_time, new_time, new_turn):
        working = apply_event(working, event)
        events.append(event)
    for event in _milestone_events(compiled, working, new_turn, new_time):
        working = apply_event(working, event)
        events.append(event)
    for event in _expansion_events(compiled, working, new_turn, new_time):
        working = apply_event(working, event)
        events.append(event)
    # Attach replay/audit metadata without making it an additional source of
    # state.  The shared EventDraft remains intentionally small; persistence
    # can promote these details to its full Event record.
    enriched: list[EventDraft] = []
    replayed = deepcopy(dict(state))
    for event in events:
        before = state_hash(replayed)
        after = apply_event(replayed, event)
        details = deepcopy(event.details)
        details.update({"state_before_hash": before, "state_after_hash": state_hash(after)})
        details["draft_hash"] = sha256_json({"event_type": event.event_type, "actor_id": event.actor_id, "patches": event.patches, "facts": event.facts, "details": details})
        enriched_event = EventDraft(event.event_type, event.actor_id, event.patches, event.facts, details)
        enriched.append(enriched_event)
        replayed = after
    events = enriched
    if replayed != working:
        raise AssertionError("event_replay_divergence")
    from ..projection import project_player_view
    return EngineResolution(action_id, turn, current_hash, working, tuple(events), project_player_view(compiled, working, events))
