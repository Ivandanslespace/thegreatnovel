"""Runtime experience gates for complete, playable world packages.

The blueprint compiler proves that a package is safe data.  These gates prove
that it contains enough interacting systems to enter a campaign.  Semantic
anti-reskin review remains a host responsibility and is reported explicitly.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping


class ExperienceGateError(ValueError):
    """Raised when a safe blueprint is still too incomplete to play."""

    def __init__(self, report: Mapping[str, Any]):
        self.report = deepcopy(dict(report))
        codes = ", ".join(issue["code"] for issue in report.get("issues", ()))
        super().__init__(f"world experience gate failed: {codes or 'unknown'}")


def _issue(code: str, message: str, *, path: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"severity": "error", "code": code, "message": message}
    if path:
        value["path"] = path
    return value


def _lookup(state: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    node: Any = state
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _all_actions(world: Mapping[str, Any]) -> Iterable[tuple[str, Mapping[str, Any]]]:
    for index, action in enumerate(world.get("actions", ())):
        yield f"actions[{index}]", action
    for expansion_index, expansion in enumerate(world.get("expansions", ())):
        for action_index, action in enumerate(expansion.get("candidate", {}).get("actions", ())):
            yield f"expansions[{expansion_index}].candidate.actions[{action_index}]", action


def _all_patch_groups(world: Mapping[str, Any]) -> Iterable[tuple[str, Iterable[Mapping[str, Any]]]]:
    for path, action in _all_actions(world):
        yield f"{path}.lever.extra_patches", action.get("lever", {}).get("extra_patches", ())
        yield f"{path}.success.patches", action.get("success", {}).get("patches", ())
        yield f"{path}.failure.patches", action.get("failure", {}).get("patches", ())
    for collection in ("processes", "milestones"):
        for index, item in enumerate(world.get(collection, ())):
            yield f"{collection}[{index}].patches", item.get("patches", ())
    for expansion_index, expansion in enumerate(world.get("expansions", ())):
        candidate = expansion.get("candidate", {})
        yield f"expansions[{expansion_index}].candidate.state_patches", candidate.get("state_patches", ())
        for collection in ("processes", "milestones"):
            for index, item in enumerate(candidate.get(collection, ())):
                yield f"expansions[{expansion_index}].candidate.{collection}[{index}].patches", item.get("patches", ())


def validate_experience(world: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic completeness report for a compiled world."""

    issues: list[dict[str, Any]] = []
    state = world.get("initial_state", {})
    actors = state.get("actors", {}) if isinstance(state, Mapping) else {}
    opportunities = state.get("opportunities", {}) if isinstance(state, Mapping) else {}
    minimums = (
        ("actions", len(world.get("actions", ())), 16, "至少需要 16 个基础行动"),
        ("processes", len(world.get("processes", ())), 2, "至少需要两个离屏世界过程"),
        ("milestones", len(world.get("milestones", ())), 3, "至少需要三个成长里程碑"),
        ("expansions", len(world.get("expansions", ())), 1, "至少需要一个更大世界候选"),
        ("initial_state.actors", len(actors) if isinstance(actors, Mapping) else 0, 3, "至少需要三个持续行动者"),
        ("initial_state.opportunities", len(opportunities) if isinstance(opportunities, Mapping) else 0, 3, "至少需要三个机会窗口"),
    )
    for path, actual, required, message in minimums:
        if actual < required:
            issues.append(_issue("insufficient_" + path.replace(".", "_"), message, path=path))

    for path, action in _all_actions(world):
        max_uses = action.get("max_uses")
        if isinstance(max_uses, bool) or not isinstance(max_uses, int) or max_uses <= 0:
            issues.append(_issue("unbounded_action", "每个行动都必须有正整数 max_uses", path=f"{path}.max_uses"))
        if not isinstance(action.get("time_cost"), int) or action.get("time_cost", 0) <= 0:
            issues.append(_issue("nonpositive_action_time", "可玩行动必须推进世界时间", path=f"{path}.time_cost"))
        for cost_index, cost in enumerate(action.get("costs", ()) if isinstance(action.get("costs"), list) else ()):
            found, current = _lookup(state, str(cost.get("path", "")))
            if found and (isinstance(current, bool) or not isinstance(current, (int, float))):
                issues.append(_issue("nonnumeric_cost_target", "资源成本必须指向数值状态", path=f"{path}.costs[{cost_index}].path"))

    for group_path, patches in _all_patch_groups(world):
        for index, patch in enumerate(patches):
            patch_path = f"{group_path}[{index}]"
            if patch.get("op") == "add":
                amount = patch.get("value")
                if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                    issues.append(_issue("nonnumeric_add_value", "add patch 的 value 必须是数值", path=f"{patch_path}.value"))
                found, current = _lookup(state, str(patch.get("path", "")))
                if found and (isinstance(current, bool) or not isinstance(current, (int, float))):
                    issues.append(_issue("nonnumeric_add_target", "add patch 不能作用于布尔值或文本", path=f"{patch_path}.path"))

    cycle = world.get("cycle", {})
    if len(cycle.get("compounding_chains", ())) < 2:
        issues.append(_issue("missing_compounding_routes", "至少需要两条不同的复利路线", path="cycle.compounding_chains"))
    relationship_id = cycle.get("relationship_reversal_milestone")
    milestones = {item.get("id"): item for item in world.get("milestones", ())}
    relationship = milestones.get(relationship_id, {})
    if not any("relationship" in str(fact.get("kind", "")) for fact in relationship.get("facts", ())):
        issues.append(_issue("missing_relationship_reversal_fact", "关系反转里程碑必须产生明确事实", path="cycle.relationship_reversal_milestone"))
    tier_id = cycle.get("tier_ascent_milestone")
    if milestones.get(tier_id, {}).get("tier_to") is None:
        issues.append(_issue("missing_tier_ascent", "阶层跃迁里程碑必须声明 tier_to", path="cycle.tier_ascent_milestone"))
    for index, expansion in enumerate(world.get("expansions", ())):
        candidate = expansion.get("candidate", {})
        if not candidate.get("actions") or not candidate.get("processes") or not candidate.get("milestones"):
            issues.append(_issue("thin_expansion", "更大世界必须同时提供行动、过程和里程碑", path=f"expansions[{index}].candidate"))

    panel_metrics = {"absolute_power", "effective_capacity", "relative_standing", "strategy_space"}
    metrics = state.get("metrics", {}) if isinstance(state, Mapping) else {}
    if not panel_metrics <= set(metrics if isinstance(metrics, Mapping) else ()):
        issues.append(_issue("missing_growth_panel", "初始 metrics 必须支持绝对成长、有效能力、相对地位和策略空间", path="initial_state.metrics"))

    return {
        "passed": not issues,
        "world_id": world.get("id"),
        "issues": issues,
        "warnings": [
            {
                "code": "semantic_review_required",
                "message": "编译与数量门禁不能代替杠杆消融、因果一致性和反换皮人工复核。",
            }
        ],
        "counts": {
            "actions": len(world.get("actions", ())),
            "processes": len(world.get("processes", ())),
            "milestones": len(world.get("milestones", ())),
            "expansions": len(world.get("expansions", ())),
            "actors": len(actors) if isinstance(actors, Mapping) else 0,
            "opportunities": len(opportunities) if isinstance(opportunities, Mapping) else 0,
        },
    }


def require_experience_ready(world: Mapping[str, Any]) -> dict[str, Any]:
    report = validate_experience(world)
    if not report["passed"]:
        raise ExperienceGateError(report)
    return report


__all__ = ["ExperienceGateError", "require_experience_ready", "validate_experience"]
