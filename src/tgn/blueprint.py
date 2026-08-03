"""Strict, data-only world blueprint compiler.

The compiler deliberately accepts a small JSON language.  It never evaluates
Python, imports plugins, or fills missing world content with defaults.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .hashing import sha256_json


class BlueprintError(ValueError):
    """Raised when a blueprint is not a complete, safe world package."""


TOP_LEVEL = {
    "schema_version", "id", "title", "locale", "premise", "causal_model",
    "core_question", "control_deficit", "lever", "cycle", "initial_state",
    "actions", "processes", "milestones", "expansions",
}
REQUIRED_TOP_LEVEL = set(TOP_LEVEL)
ACTION_FIELDS = {
    "id", "label", "description", "tags", "time_cost", "visible_when",
    "legal_when", "costs", "check", "lever", "success", "failure",
    "known_risks", "unknowns", "opportunity_costs", "max_uses",
}
ACTION_REQUIRED = ACTION_FIELDS - {"max_uses"}
CONDITION_OPS = {"all", "any", "not", "eq", "ne", "gte", "lte", "gt", "lt", "contains", "truthy"}
PATCH_OPS = {"set", "add", "append_unique", "remove", "merge"}
BUSINESS_ROOTS = {"player", "actors", "world", "opportunities", "unlocks", "metrics"}
VISIBILITIES = {"public", "player", "hidden"}


def _fail(path: str, message: str) -> None:
    raise BlueprintError(f"{path}: {message}")


def _obj(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail(path, "must be an object")
    return dict(value)


def _keys(value: Mapping[str, Any], allowed: set[str], required: set[str], path: str) -> None:
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        _fail(path, f"unknown fields: {sorted(unknown)}")
    if missing:
        _fail(path, f"missing fields: {sorted(missing)}")


def _str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(path, "must be a non-empty string")
    return value


def _number(value: Any, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(path, "must be a number")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    return value


def _id_list(value: Any, path: str) -> None:
    for i, item in enumerate(_list(value, path)):
        _str(item, f"{path}[{i}]")


def _condition(value: Any, path: str) -> None:
    if value is None:
        return
    obj = _obj(value, path)
    if len(obj) != 1:
        _fail(path, "condition must contain exactly one operator")
    op, operand = next(iter(obj.items()))
    if op not in CONDITION_OPS:
        _fail(path, f"unknown condition operator {op!r}")
    if op in {"all", "any"}:
        for i, child in enumerate(_list(operand, f"{path}.{op}")):
            _condition(child, f"{path}.{op}[{i}]")
    elif op == "not":
        _condition(operand, f"{path}.not")
    elif op in {"eq", "ne", "gte", "lte", "gt", "lt", "contains"}:
        if not isinstance(operand, list) or len(operand) != 2:
            _fail(path, f"{op} requires a two-item array")
        # Nested conditions are useful for world-local rules, but no other DSL
        # is permitted.
        for i, item in enumerate(operand):
            if isinstance(item, Mapping):
                if set(item) == {"path"}:
                    _path(item["path"], f"{path}.{op}[{i}].path")
                else:
                    _condition(item, f"{path}.{op}[{i}]")
    elif op == "truthy":
        if isinstance(operand, Mapping) and set(operand) == {"path"}:
            _path(operand["path"], f"{path}.truthy.path")
        elif not isinstance(operand, str):
            _fail(path, "truthy requires a state path or nested condition")


def _path(path: Any, path_name: str) -> None:
    if not isinstance(path, str) or not path or path.startswith(".") or path.endswith("."):
        _fail(path_name, "invalid business path")
    parts = path.split(".")
    if parts[0] not in BUSINESS_ROOTS or any(not p or p in {"..", "."} for p in parts):
        _fail(path_name, "path must start with a business root")
    if any(p.startswith("_") for p in parts):
        _fail(path_name, "private paths are not allowed")


def _patch(value: Any, path: str) -> None:
    obj = _obj(value, path)
    if "op" not in obj or "path" not in obj:
        _fail(path, "patch requires op and path")
    unknown = set(obj) - {"op", "path", "value"}
    if unknown:
        _fail(path, f"unknown fields: {sorted(unknown)}")
    op = obj["op"]
    if op not in PATCH_OPS:
        _fail(path, f"unknown patch operator {op!r}")
    _path(obj["path"], f"{path}.path")
    if op != "remove" and "value" not in obj:
        _fail(path, f"{op} requires value")


def _facts(value: Any, path: str) -> None:
    for i, raw in enumerate(_list(value, path)):
        fact = _obj(raw, f"{path}[{i}]")
        _keys(fact, {"text", "visibility", "kind", "source"}, {"text", "visibility", "kind", "source"}, f"{path}[{i}]")
        _str(fact["text"], f"{path}[{i}].text")
        vis = _str(fact["visibility"], f"{path}[{i}].visibility")
        if vis not in VISIBILITIES and not vis.startswith("actor:"):
            _fail(f"{path}[{i}].visibility", "must be public/player/hidden/actor:<id>")
        _str(fact["kind"], f"{path}[{i}].kind")
        _str(fact["source"], f"{path}[{i}].source")


def _patches(value: Any, path: str) -> None:
    for i, item in enumerate(_list(value, path)):
        _patch(item, f"{path}[{i}]")


def _branch(value: Any, path: str) -> None:
    branch = _obj(value, path)
    _keys(branch, {"patches", "facts"}, {"patches", "facts"}, path)
    _patches(branch["patches"], f"{path}.patches")
    _facts(branch["facts"], f"{path}.facts")


def _action(raw: Any, path: str) -> dict[str, Any]:
    action = _obj(raw, path)
    _keys(action, ACTION_FIELDS, ACTION_REQUIRED, path)
    _str(action["id"], f"{path}.id")
    _str(action["label"], f"{path}.label")
    _str(action["description"], f"{path}.description")
    _id_list(action["tags"], f"{path}.tags")
    time_cost = _number(action["time_cost"], f"{path}.time_cost")
    if time_cost < 0 or int(time_cost) != time_cost:
        _fail(f"{path}.time_cost", "must be a non-negative integer")
    if action.get("max_uses") is not None and (isinstance(action["max_uses"], bool) or not isinstance(action["max_uses"], int) or action["max_uses"] <= 0):
        _fail(f"{path}.max_uses", "must be a positive integer")
    _condition(action["visible_when"], f"{path}.visible_when")
    _condition(action["legal_when"], f"{path}.legal_when")
    if not isinstance(action["costs"], (Mapping, list)):
        _fail(f"{path}.costs", "must be an object or array")
    if isinstance(action["costs"], list):
        for i, cost in enumerate(action["costs"]):
            c = _obj(cost, f"{path}.costs[{i}]")
            _keys(c, {"path", "amount"}, {"path", "amount"}, f"{path}.costs[{i}]")
            _path(c["path"], f"{path}.costs[{i}].path")
            _number(c["amount"], f"{path}.costs[{i}].amount")
    else:
        for key, amount in action["costs"].items():
            _path(key, f"{path}.costs.{key}")
            _number(amount, f"{path}.costs.{key}")
    check = action["check"]
    if check is not None:
        check_obj = _obj(check, f"{path}.check")
        _keys(check_obj, {"base", "terms", "lever_bonus"}, {"base", "terms", "lever_bonus"}, f"{path}.check")
        base = _number(check_obj["base"], f"{path}.check.base")
        if not 0 <= base <= 100:
            _fail(f"{path}.check.base", "must be between 0 and 100")
        for i, term in enumerate(_list(check_obj["terms"], f"{path}.check.terms")):
            term_obj = _obj(term, f"{path}.check.terms[{i}]")
            _keys(term_obj, {"path", "multiplier"}, {"path", "multiplier"}, f"{path}.check.terms[{i}]")
            _path(term_obj["path"], f"{path}.check.terms[{i}].path")
            _number(term_obj["multiplier"], f"{path}.check.terms[{i}].multiplier")
        _number(check_obj["lever_bonus"], f"{path}.check.lever_bonus")
    if action["lever"] is not None:
        lever = _obj(action["lever"], f"{path}.lever")
        _keys(lever, {"required", "extra_costs", "extra_patches"}, {"required", "extra_costs", "extra_patches"}, f"{path}.lever")
        if not isinstance(lever["required"], bool):
            _fail(f"{path}.lever.required", "must be boolean")
        if not isinstance(lever["extra_costs"], (Mapping, list)):
            _fail(f"{path}.lever.extra_costs", "must be an object or array")
        if isinstance(lever["extra_costs"], Mapping):
            for key, amount in lever["extra_costs"].items():
                _path(key, f"{path}.lever.extra_costs.{key}")
                _number(amount, f"{path}.lever.extra_costs.{key}")
        else:
            for i, cost in enumerate(lever["extra_costs"]):
                c = _obj(cost, f"{path}.lever.extra_costs[{i}]")
                _keys(c, {"path", "amount"}, {"path", "amount"}, f"{path}.lever.extra_costs[{i}]")
                _path(c["path"], f"{path}.lever.extra_costs[{i}].path")
                _number(c["amount"], f"{path}.lever.extra_costs[{i}].amount")
        _patches(lever["extra_patches"], f"{path}.lever.extra_patches")
    _branch(action["success"], f"{path}.success")
    _branch(action["failure"], f"{path}.failure")
    for field in ("known_risks", "unknowns", "opportunity_costs"):
        for i, item in enumerate(_list(action[field], f"{path}.{field}")):
            _str(item, f"{path}.{field}[{i}]")
    return action


def _entries(value: Any, path: str) -> list[dict[str, Any]]:
    items = _list(value, path)
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    for i, raw in enumerate(items):
        entry = _obj(raw, f"{path}[{i}]")
        ident = _str(entry.get("id"), f"{path}[{i}].id")
        if ident in ids:
            _fail(path, f"duplicate id {ident!r}")
        ids.add(ident)
        result.append(entry)
    return result


def _validate_processes(value: Any) -> list[dict[str, Any]]:
    result = _entries(value, "processes")
    allowed = {"id", "actor_id", "interval_minutes", "first_due_minute", "when", "patches", "facts"}
    for i, p in enumerate(result):
        _keys(p, allowed, {"id", "actor_id", "interval_minutes", "first_due_minute", "when", "patches", "facts"}, f"processes[{i}]")
        _str(p["actor_id"], f"processes[{i}].actor_id")
        if _number(p["interval_minutes"], f"processes[{i}].interval_minutes") <= 0:
            _fail(f"processes[{i}].interval_minutes", "must be positive")
        if _number(p["first_due_minute"], f"processes[{i}].first_due_minute") < 0:
            _fail(f"processes[{i}].first_due_minute", "must be non-negative")
        _patches(p["patches"], f"processes[{i}].patches")
        _facts(p["facts"], f"processes[{i}].facts")
        _condition(p["when"], f"processes[{i}].when")
    return result


def _validate_milestones(value: Any) -> list[dict[str, Any]]:
    result = _entries(value, "milestones")
    allowed = {"id", "when", "once", "patches", "facts", "tier_to"}
    for i, m in enumerate(result):
        _keys(m, allowed, allowed, f"milestones[{i}]")
        _condition(m["when"], f"milestones[{i}].when")
        _patches(m["patches"], f"milestones[{i}].patches")
        if not isinstance(m["once"], bool):
            _fail(f"milestones[{i}].once", "must be boolean")
        _facts(m["facts"], f"milestones[{i}].facts")
        if m["tier_to"] is not None and not isinstance(m["tier_to"], int):
            _fail(f"milestones[{i}].tier_to", "must be integer or null")
    return result


def _validate_expansions(value: Any) -> list[dict[str, Any]]:
    result = _entries(value, "expansions")
    allowed = {"id", "trigger", "anchors", "candidate"}
    for i, e in enumerate(result):
        _keys(e, allowed, allowed, f"expansions[{i}]")
        _id_list(e["anchors"], f"expansions[{i}].anchors")
        _condition(e["trigger"], f"expansions[{i}].trigger")
        candidate = _obj(e["candidate"], f"expansions[{i}].candidate")
        _keys(candidate, {"namespace", "state_patches", "actions", "processes", "milestones"}, {"namespace", "state_patches", "actions", "processes", "milestones"}, f"expansions[{i}].candidate")
        _str(candidate["namespace"], f"expansions[{i}].candidate.namespace")
        _patches(candidate["state_patches"], f"expansions[{i}].candidate.state_patches")
        for key in ("actions", "processes", "milestones"):
            if not isinstance(candidate[key], list):
                _fail(f"expansions[{i}].candidate.{key}", "must be an array")
        for j, item in enumerate(candidate["actions"]):
            _action(item, f"expansions[{i}].candidate.actions[{j}]")
        for j, item in enumerate(candidate["processes"]):
            _validate_processes([item])
        for j, item in enumerate(candidate["milestones"]):
            _validate_milestones([item])
    return result


def compile_blueprint(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and seal a complete JSON world package."""

    source = _obj(raw, "blueprint")
    _keys(source, TOP_LEVEL, REQUIRED_TOP_LEVEL, "blueprint")
    if source["schema_version"] != "tgn.world.v1":
        _fail("blueprint.schema_version", "must be tgn.world.v1")
    for field in ("id", "title", "locale", "premise", "causal_model", "core_question", "control_deficit"):
        _str(source[field], f"blueprint.{field}")
    lever = _obj(source["lever"], "blueprint.lever")
    _keys(lever, {"id", "name", "summary", "cost", "limits", "ordinary_baseline", "action_ids"}, {"id", "name", "summary", "cost", "limits", "ordinary_baseline", "action_ids"}, "blueprint.lever")
    for field in ("id", "name", "summary", "ordinary_baseline"):
        _str(lever[field], f"blueprint.lever.{field}")
    for field in ("cost", "limits"):
        for i, item in enumerate(_list(lever[field], f"blueprint.lever.{field}")):
            _str(item, f"blueprint.lever.{field}[{i}]")
    _id_list(lever["action_ids"], "blueprint.lever.action_ids")
    if not lever["action_ids"]:
        _fail("blueprint.lever.action_ids", "must not be empty")
    cycle = _obj(source["cycle"], "blueprint.cycle")
    _keys(cycle, {"rule_legibility_actions", "compounding_chains", "relationship_reversal_milestone", "tier_ascent_milestone", "larger_world_expansion"}, {"rule_legibility_actions", "compounding_chains", "relationship_reversal_milestone", "tier_ascent_milestone", "larger_world_expansion"}, "blueprint.cycle")
    _id_list(cycle["rule_legibility_actions"], "blueprint.cycle.rule_legibility_actions")
    chains = _list(cycle["compounding_chains"], "blueprint.cycle.compounding_chains")
    if len(chains) < 2:
        _fail("blueprint.cycle.compounding_chains", "requires at least two chains")
    for i, chain in enumerate(chains):
        if len(_list(chain, f"blueprint.cycle.compounding_chains[{i}]")) < 2:
            _fail(f"blueprint.cycle.compounding_chains[{i}]", "must contain at least two IDs")
        _id_list(chain, f"blueprint.cycle.compounding_chains[{i}]")
    for name in ("relationship_reversal_milestone", "tier_ascent_milestone", "larger_world_expansion"):
        _str(cycle[name], f"blueprint.cycle.{name}")
    state = _obj(source["initial_state"], "blueprint.initial_state")
    _keys(state, {"player", "actors", "world", "opportunities", "unlocks", "metrics"}, {"player", "actors", "world", "opportunities", "unlocks", "metrics"}, "blueprint.initial_state")
    for field in ("player", "actors", "world", "opportunities", "metrics"):
        if not isinstance(state[field], Mapping):
            _fail(f"blueprint.initial_state.{field}", "must be an object")
    if not isinstance(state["unlocks"], list):
        _fail("blueprint.initial_state.unlocks", "must be an array")
    actions = [_action(item, f"actions[{i}]") for i, item in enumerate(_list(source["actions"], "actions"))]
    action_ids = {a["id"] for a in actions}
    if len(action_ids) != len(actions):
        _fail("actions", "duplicate id")
    processes = _validate_processes(source["processes"])
    milestones = _validate_milestones(source["milestones"])
    expansions = _validate_expansions(source["expansions"])
    milestone_ids = {m["id"] for m in milestones}
    expansion_ids = {e["id"] for e in expansions}
    process_ids = {p["id"] for p in processes}
    collections = [("actions", action_ids), ("processes", process_ids), ("milestones", milestone_ids), ("expansions", expansion_ids)]
    seen_global: set[str] = set()
    for collection_name, identifiers in collections:
        overlap = seen_global & identifiers
        if overlap:
            _fail(collection_name, f"duplicate global id(s): {sorted(overlap)}")
        seen_global.update(identifiers)
    actor_ids = set(state["actors"]) | {"world"}
    for i, process in enumerate(processes):
        if process["actor_id"] not in actor_ids:
            _fail(f"processes[{i}].actor_id", "must reference an initial actor or world")
    for ei, expansion in enumerate(expansions):
        candidate = expansion["candidate"]
        for pi, process in enumerate(candidate["processes"]):
            if process["actor_id"] not in actor_ids:
                _fail(f"expansions[{ei}].candidate.processes[{pi}].actor_id", "must reference an initial actor or world")
        for collection in ("actions", "processes", "milestones"):
            identifiers = {item["id"] for item in candidate[collection]}
            overlap = seen_global & identifiers
            if overlap:
                _fail(f"expansions[{ei}].candidate.{collection}", f"duplicate global id(s): {sorted(overlap)}")
            seen_global.update(identifiers)
    known_ids = action_ids | milestone_ids | expansion_ids
    for i, action_id in enumerate(lever["action_ids"]):
        if action_id not in action_ids:
            _fail(f"blueprint.lever.action_ids[{i}]", "unknown action id")
    for i, action_id in enumerate(cycle["rule_legibility_actions"]):
        if action_id not in action_ids:
            _fail(f"blueprint.cycle.rule_legibility_actions[{i}]", "unknown action id")
    for i, chain in enumerate(chains):
        for j, item in enumerate(chain):
            if item not in known_ids:
                _fail(f"blueprint.cycle.compounding_chains[{i}][{j}]", "unknown id")
    if cycle["relationship_reversal_milestone"] not in milestone_ids:
        _fail("blueprint.cycle.relationship_reversal_milestone", "unknown milestone id")
    if cycle["tier_ascent_milestone"] not in milestone_ids:
        _fail("blueprint.cycle.tier_ascent_milestone", "unknown milestone id")
    if cycle["larger_world_expansion"] not in expansion_ids:
        _fail("blueprint.cycle.larger_world_expansion", "unknown expansion id")
    leverage_required = any(
        isinstance(a.get("lever"), Mapping) and bool(a["lever"].get("required", a["lever"].get("requires", False)))
        for a in actions if a["id"] in set(lever["action_ids"])
    )
    if not leverage_required:
        _fail("blueprint.lever", "at least one referenced action must require leverage")
    compiled = deepcopy(source)
    compiled["actions"] = deepcopy(actions)
    compiled["processes"] = deepcopy(processes)
    compiled["milestones"] = deepcopy(milestones)
    compiled["expansions"] = deepcopy(expansions)
    compiled["blueprint_hash"] = sha256_json(compiled)
    return compiled


# Kept here as a convenience for hosts that treat blueprint concerns as one
# module; the implementation remains in the pure engine package.
from .engine.expansion import validate_expansion  # noqa: E402

__all__ = ["BlueprintError", "compile_blueprint", "validate_expansion"]
