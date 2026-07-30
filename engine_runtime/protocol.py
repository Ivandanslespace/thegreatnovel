"""LLM 主持器与 Python 引擎之间的唯一输入协议。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional


PROTOCOL_VERSION = "1.0"

# LLM 只能描述意图；成本、难度、概率、结果和状态增量属于 Python 内部字段。
ENGINE_ONLY_FIELDS = {
    "advantage", "resistance", "probability", "random_roll", "roll", "severity",
    "outcome", "resolution", "action_ledger", "formula_version", "death_fairness",
    "damage", "hit_probability", "attacker_attack", "defender_defense", "retreat_probability",
    "experience_gain", "xp", "drop", "drops", "loot", "resource_changes", "player_delta",
    "time_minutes", "stamina_cost", "mental_cost", "hunger_cost", "resources", "seed",
    "target_difficulty", "equipment_bonus", "ability_match", "preparation", "intelligence",
    "teammate_assistance", "environment_advantage", "environment_penalty", "time_pressure",
    "unknown_risk", "risk_warning", "causal_chain", "avoidable", "rule_consistency",
    "player_responsibility", "current_turn", "game_day", "hp", "fatigue", "mental",
    "minutes", "duration", "time_cost", "available_time_minutes", "cost", "difficulty",
    "damage_taken", "hp_delta", "fatigue_delta", "mental_delta", "hunger_delta",
    "ammo_available", "ammo_consumed", "durability", "durability_cost", "status_effects",
    "kill_success_rate", "enemy_groups", "farmability_components", "farmability", "net_value",
    "module", "area", "target_profile", "death_risk", "experience",
}

ALLOWED_ACTION_FIELDS = {
    "action_id", "type", "target", "primary_attribute", "skill_id", "requirements",
    "risk_preference", "tags", "goal", "approach", "parameters", "stop_conditions", "plan_id",
    "steps", "priority_order", "accept_dilution",
}

NESTED_INTENT_FIELDS = {
    "requirements": {"location", "items", "level", "skill", "npc_available", "knowledge"},
    "parameters": {"approach", "relationship_intent", "message", "order", "objective"},
    "stop_conditions": {"ammo_below", "risk_above", "environment_change"},
}

ACTION_PLAN_FIELDS = {"action_id", "type", "target", "skill_id", "risk_preference", "tags", "goal", "approach", "parameters", "requirements"}

ACTION_PROFILES = {
    "SHORT_ACTION": {"time_minutes": 30.0, "stamina_cost": 2.0, "mental_cost": 4.0, "target_difficulty": 10.0},
    "SOCIAL_INTERACTION": {"time_minutes": 30.0, "stamina_cost": 2.0, "mental_cost": 4.0, "target_difficulty": 15.0},
    "EXPLORATION": {"time_minutes": 120.0, "stamina_cost": 15.0, "mental_cost": 10.0, "target_difficulty": 25.0},
    "COMBAT": {"time_minutes": 30.0, "stamina_cost": 10.0, "mental_cost": 5.0, "target_difficulty": 30.0},
    "BATCH_ACTION": {"time_minutes": 120.0, "stamina_cost": 15.0, "mental_cost": 10.0, "target_difficulty": 25.0},
    "SKILL_ACTION": {"time_minutes": 30.0, "stamina_cost": 0.0, "mental_cost": 0.0, "target_difficulty": 20.0},
    "BUILD": {"time_minutes": 120.0, "stamina_cost": 20.0, "mental_cost": 5.0, "target_difficulty": 20.0},
    "RESEARCH": {"time_minutes": 120.0, "stamina_cost": 5.0, "mental_cost": 20.0, "target_difficulty": 25.0},
    "TRAVEL": {"time_minutes": 30.0, "stamina_cost": 5.0, "mental_cost": 0.0, "target_difficulty": 5.0},
    "ENTER_LOCATION": {"time_minutes": 30.0, "stamina_cost": 5.0, "mental_cost": 0.0, "target_difficulty": 5.0},
    "RETURN_TO_BASE": {"time_minutes": 45.0, "stamina_cost": 6.0, "mental_cost": 0.0, "target_difficulty": 5.0},
    "EXTRACT": {"time_minutes": 60.0, "stamina_cost": 8.0, "mental_cost": 2.0, "target_difficulty": 10.0},
    "LEAVE_ENCOUNTER": {"time_minutes": 15.0, "stamina_cost": 2.0, "mental_cost": 0.0, "target_difficulty": 5.0},
    "BASE_MANAGEMENT": {"time_minutes": 30.0, "stamina_cost": 2.0, "mental_cost": 4.0, "target_difficulty": 0.0},
    "REST": {"time_minutes": 360.0, "stamina_cost": 0.0, "mental_cost": 0.0, "target_difficulty": 0.0},
    # 只处理已经发生的即时危险，不占用普通行动槽；运行时还会把
    # pending_reaction 的实际时间限制在 0-5 分钟内。
    "REACTION": {"time_minutes": 5.0, "stamina_cost": 1.0, "mental_cost": 1.0, "target_difficulty": 10.0},
    "TALENT_CHOICE": {"time_minutes": 0.0, "stamina_cost": 0.0, "mental_cost": 0.0, "target_difficulty": 0.0},
    "ACTION_PLAN": {"time_minutes": 0.0, "stamina_cost": 0.0, "mental_cost": 0.0, "target_difficulty": 0.0},
    "ENDING": {"time_minutes": 0.0, "stamina_cost": 0.0, "mental_cost": 0.0, "target_difficulty": 0.0},
    "RESTART": {"time_minutes": 0.0, "stamina_cost": 0.0, "mental_cost": 0.0, "target_difficulty": 0.0},
    "CHECKPOINT": {"time_minutes": 0.0, "stamina_cost": 0.0, "mental_cost": 0.0, "target_difficulty": 0.0},
    "LEGACY_CREATE": {"time_minutes": 0.0, "stamina_cost": 0.0, "mental_cost": 0.0, "target_difficulty": 0.0},
}


class ProtocolError(ValueError):
    """LLM 主机提交了不允许的输入。"""


def _find_forbidden(value: Any, path: str = "action") -> list[str]:
    found = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in ENGINE_ONLY_FIELDS:
                found.append(child_path)
            found.extend(_find_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_forbidden(child, f"{path}[{index}]"))
    return found


def validate_host_action(action: Mapping[str, Any]) -> None:
    if not isinstance(action, Mapping):
        raise ProtocolError("主机行动必须是 JSON 对象")
    unknown = sorted(set(action) - ALLOWED_ACTION_FIELDS)
    forbidden = _find_forbidden(action)
    errors = []
    if unknown:
        errors.append("不允许或未知字段：" + ", ".join(unknown))
    if forbidden:
        errors.append("LLM不得提交引擎字段：" + ", ".join(forbidden))
    action_type = str(action.get("type", ""))
    for field, allowed_fields in NESTED_INTENT_FIELDS.items():
        nested = action.get(field)
        if isinstance(nested, Mapping):
            nested_unknown = sorted(set(nested) - allowed_fields)
            if nested_unknown:
                errors.append(f"{field} 含不允许字段：" + ", ".join(nested_unknown))
    if action_type == "ACTION_PLAN":
        steps = action.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append("ACTION_PLAN 必须包含非空 steps")
        else:
            for index, step in enumerate(steps):
                if not isinstance(step, Mapping):
                    errors.append(f"steps[{index}] 必须是对象")
                    continue
                unknown_step = sorted(set(step) - ACTION_PLAN_FIELDS)
                if unknown_step:
                    errors.append(f"steps[{index}] 含不允许字段：" + ", ".join(unknown_step))
                if str(step.get("type", "")) not in set(ACTION_PROFILES) - {"ACTION_PLAN"}:
                    errors.append(f"steps[{index}].type 不是有效行动类型")
        if not str(action.get("plan_id", "")).strip():
            errors.append("ACTION_PLAN 缺少 plan_id")
        if action.get("priority_order") is not None and not isinstance(action.get("priority_order"), list):
            errors.append("priority_order 必须是列表")
    elif action.get("steps") is not None:
        errors.append("只有 ACTION_PLAN 才能提交 steps")
    requirements = action.get("requirements")
    if isinstance(requirements, Mapping) and isinstance(requirements.get("items"), list):
        for index, item in enumerate(requirements["items"]):
            if isinstance(item, Mapping):
                item_unknown = sorted(set(item) - {"id", "name", "quantity"})
                if item_unknown:
                    errors.append(f"requirements.items[{index}] 含不允许字段：" + ", ".join(item_unknown))
    if action_type not in ACTION_PROFILES:
        errors.append("type 必须是：" + ", ".join(sorted(ACTION_PROFILES)))
    if not str(action.get("action_id", "")).strip():
        errors.append("缺少 action_id")
    if errors:
        raise ProtocolError("；".join(errors))


def derive_action_costs(action: Mapping[str, Any], skill: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
    """只由 Python 根据行动类型和技能定义派生成本。"""
    action_type = str(action.get("type", ""))
    if action_type not in ACTION_PROFILES:
        raise ProtocolError(f"未知行动类型：{action_type}")
    costs = deepcopy(ACTION_PROFILES[action_type])
    if skill:
        from .calculators import skill_cost

        for resource, amount in skill_cost(skill).items():
            if resource in {"stamina", "mental"}:
                costs[f"{resource}_cost"] += amount
    return costs


def derive_risk_modifiers(action: Mapping[str, Any]) -> Dict[str, float]:
    preference = str(action.get("risk_preference", "标准"))
    if preference in {"谨慎", "cautious"}:
        return {"preparation": 5.0, "unknown_risk": -5.0, "time_pressure": 3.0}
    if preference in {"激进", "aggressive"}:
        return {"preparation": -3.0, "unknown_risk": 5.0, "time_pressure": -2.0}
    return {"preparation": 0.0, "unknown_risk": 0.0, "time_pressure": 0.0}
