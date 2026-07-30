"""TheGreatNovel 的确定性计算器。

所有输入数值都在这里归一化、计算并返回中间值。LLM 可以负责解析玩家意图
和把结果写成小说，但不能覆盖这里产生的结果。
"""

from __future__ import annotations

import hashlib
import math
import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .models import ActionContext, ActionResolution, BatchResolution, CombatResolution


FORMULA_VERSION = "1.0"
DIFFICULTY_K = {"休闲": 14.0, "标准": 10.0, "硬核": 6.0}
QUALITY_MULTIPLIER = {"普通": 1.0, "精英": 2.5, "首领": 5.0, "传说": 10.0}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def rounded(value: float) -> float:
    return round(float(value), 6)


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def deterministic_roll(seed: str, key: str) -> float:
    """由存档 seed 和 action_id 得到可复盘的 [0,1) 随机数。"""
    digest = hashlib.sha256(f"{seed}|{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def attribute_value(entity: Mapping[str, Any], attribute: str, default: float = 5.0) -> float:
    attributes = entity.get("attributes", {})
    if isinstance(attributes, Mapping):
        return number(attributes.get(attribute), default)
    return default


def _properties(equipment: Mapping[str, Any]) -> str:
    values = equipment.get("properties", [])
    if isinstance(values, list):
        return " ".join(str(value) for value in values)
    return str(values or "")


def equipment_stat(equipment: Optional[Mapping[str, Any]], key: str) -> float:
    if not isinstance(equipment, Mapping):
        return 0.0
    attributes = equipment.get("attributes", {})
    if isinstance(attributes, Mapping) and key in attributes:
        return number(attributes[key])
    aliases = {
        "attack": ("attack", "攻击", "攻击力"),
        "defense": ("defense", "防御", "防御力"),
        "accuracy": ("accuracy", "命中", "精度"),
        "evasion": ("evasion", "闪避"),
        "speed": ("speed", "速度"),
        "ammo": ("ammo", "弹药"),
    }
    text = _properties(equipment)
    for alias in aliases.get(key, (key,)):
        match = re.search(rf"{re.escape(alias)}\s*\+\s*(-?\d+(?:\.\d+)?)", text, re.I)
        if match:
            return float(match.group(1))
    return 0.0


def equipped_items(inventory: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    equipment = inventory.get("equipment", {})
    if not isinstance(equipment, Mapping):
        return []
    return [item for item in equipment.values() if isinstance(item, Mapping)]


def total_equipment_stat(inventory: Mapping[str, Any], key: str) -> float:
    return sum(equipment_stat(item, key) for item in equipped_items(inventory))


def injury_severity(entity: Mapping[str, Any]) -> float:
    injuries = entity.get("injuries", [])
    if not isinstance(injuries, list):
        return 0.0
    total = 0.0
    for injury in injuries:
        if isinstance(injury, Mapping):
            total += number(injury.get("severity"), number(injury.get("penalty"), 0.0) * 100)
    return clamp(total, 0.0, 100.0)


def state_modifier(entity: Mapping[str, Any]) -> float:
    fatigue = clamp(number(entity.get("fatigue")), 0.0, 100.0)
    injury = injury_severity(entity)
    fatigue_modifier = 1.0 - 0.20 * fatigue / 100.0
    injury_modifier = 1.0 - 0.40 * injury / 100.0
    return clamp(fatigue_modifier * injury_modifier, 0.4, 1.0)


def _action_context(value: ActionContext | Mapping[str, Any]) -> ActionContext:
    if isinstance(value, ActionContext):
        return value
    fields = ActionContext.__dataclass_fields__
    return ActionContext(**{key: value[key] for key in fields if key in value})


def calculate_death_fairness(values: Mapping[str, Any]) -> float:
    factors = [
        clamp(number(values.get(name)), 0.0, 1.0)
        for name in ("risk_warning", "causal_chain", "avoidable", "rule_consistency", "player_responsibility")
    ]
    result = 1.0
    for factor in factors:
        result *= factor
    return rounded(result)


def calculate_severity(values: Mapping[str, Any]) -> Tuple[float, str, Dict[str, float]]:
    """Severity = 正向风险总和 - 准备/能力/支持/保命资产。各输入为0-20。"""
    positive_names = ("difficulty", "injury", "resource_shortage", "information_missing", "time_pressure", "continuous_errors")
    negative_names = ("preparation", "ability_match", "teammate_support", "survival_assets")
    positive = {name: clamp(number(values.get(name)), 0.0, 20.0) for name in positive_names}
    negative = {name: clamp(number(values.get(name)), 0.0, 20.0) for name in negative_names}
    score = clamp(sum(positive.values()) - sum(negative.values()), 0.0, 100.0)
    if score <= 30:
        band = "成功区"
    elif score <= 50:
        band = "代价区"
    elif score <= 70:
        band = "失败区"
    elif score <= 85:
        band = "严重战败区"
    else:
        band = "死亡或永久结局区"
    return rounded(score), band, {**positive, **negative}


def resolve_action(player: Mapping[str, Any], context: ActionContext | Mapping[str, Any], inventory: Optional[Mapping[str, Any]] = None) -> ActionResolution:
    context = _action_context(context)
    inventory = inventory or {}
    ability = context.ability_match
    if ability is None:
        ability = attribute_value(player, context.primary_attribute) * 2.0 + context.skill_bonus
    equipment = context.equipment_bonus
    if equipment is None:
        equipment = total_equipment_stat(inventory, "attack") / 2.0

    advantage_components = {
        "ability_match": rounded(ability),
        "equipment_advantage": rounded(equipment),
        "preparation": rounded(clamp(context.preparation, 0.0, 20.0)),
        "intelligence": rounded(clamp(context.intelligence, 0.0, 15.0)),
        "teammate_assistance": rounded(clamp(context.teammate_assistance, 0.0, 20.0)),
        "environment_advantage": rounded(clamp(context.environment_advantage, 0.0, 15.0)),
    }
    fatigue_penalty = clamp(number(player.get("fatigue")) * 0.20, 0.0, 20.0)
    injury_penalty = clamp(injury_severity(player) * 0.20, 0.0, 20.0)
    resistance_components = {
        "target_difficulty": rounded(clamp(context.target_difficulty, 0.0, 100.0)),
        "environment_penalty": rounded(clamp(context.environment_penalty, 0.0, 20.0)),
        "injury": rounded(injury_penalty),
        "fatigue": rounded(fatigue_penalty),
        "time_pressure": rounded(clamp(context.time_pressure, 0.0, 20.0)),
        "unknown_risk": rounded(clamp(context.unknown_risk, 0.0, 30.0)),
    }
    advantage = rounded(sum(advantage_components.values()))
    resistance = rounded(sum(resistance_components.values()))
    k = DIFFICULTY_K.get(context.difficulty_mode, DIFFICULTY_K["标准"])
    probability = rounded(sigmoid((advantage - resistance) / k))
    random_roll = rounded(deterministic_roll(context.seed, context.action_id))

    severity_values = {
        "difficulty": clamp(context.target_difficulty / 5.0, 0.0, 20.0),
        "injury": injury_penalty,
        "resource_shortage": context.resource_shortage,
        "information_missing": clamp(context.unknown_risk / 1.5, 0.0, 20.0),
        "time_pressure": context.time_pressure,
        "continuous_errors": context.continuous_errors,
        "preparation": context.preparation,
        "ability_match": clamp(ability, 0.0, 20.0),
        "teammate_support": context.teammate_assistance,
        "survival_assets": context.survival_assets,
    }
    severity, severity_band, severity_components = calculate_severity(severity_values)
    death_fairness = calculate_death_fairness({
        "risk_warning": context.risk_warning,
        "causal_chain": context.causal_chain,
        "avoidable": context.avoidable,
        "rule_consistency": context.rule_consistency,
        "player_responsibility": context.player_responsibility,
    })
    death_allowed = severity >= 86 and death_fairness >= 0.5

    # P 是“成功或更好”的累计概率；random_roll 必须真正参与所有结果分支。
    # 大成功/普通成功/代价成功只是把 P 这段概率再细分，不能用概率区间替代随机判定。
    critical_threshold = probability * 0.10
    normal_threshold = probability * 0.65
    costly_threshold = probability
    partial_failure_threshold = probability + (1.0 - probability) * 0.25
    severe_failure_threshold = probability + (1.0 - probability) * 0.90

    if random_roll < critical_threshold:
        outcome = "大成功"
    elif random_roll < normal_threshold:
        outcome = "普通成功"
    elif random_roll < costly_threshold:
        outcome = "成功但付出代价"
    elif random_roll < partial_failure_threshold:
        outcome = "失败但获得部分信息"
    elif random_roll < severe_failure_threshold:
        outcome = "严重失败"
    elif death_allowed:
        outcome = "死亡"
    else:
        outcome = "战败"

    return ActionResolution(
        formula_version=FORMULA_VERSION,
        action_id=context.action_id,
        advantage_components=advantage_components,
        resistance_components=resistance_components,
        advantage=advantage,
        resistance=resistance,
        k=k,
        probability=probability,
        random_roll=random_roll,
        severity=severity,
        severity_band=severity_band,
        death_fairness=death_fairness,
        outcome=outcome,
        death_allowed=death_allowed,
        components={
            "severity": severity_components,
            "death_fairness_inputs": {"risk_warning": context.risk_warning, "causal_chain": context.causal_chain, "avoidable": context.avoidable, "rule_consistency": context.rule_consistency, "player_responsibility": context.player_responsibility},
            "outcome_thresholds": {
                "critical": rounded(critical_threshold),
                "normal": rounded(normal_threshold),
                "costly": rounded(costly_threshold),
                "partial_failure": rounded(partial_failure_threshold),
                "severe_failure": rounded(severe_failure_threshold),
            },
        },
    )


def apply_action_dilution(resolution: ActionResolution, multiplier: float) -> ActionResolution:
    """将行动计划的稀释修正应用到优势、成功率和结果分支。"""
    multiplier = clamp(number(multiplier, 1.0), 0.25, 1.0)
    if multiplier >= 1.0:
        return resolution
    resolution.advantage_components = {
        key: rounded(value * multiplier) for key, value in resolution.advantage_components.items()
    }
    resolution.advantage = rounded(sum(resolution.advantage_components.values()))
    resolution.probability = rounded(sigmoid((resolution.advantage - resolution.resistance) / resolution.k))
    critical_threshold = resolution.probability * 0.10
    normal_threshold = resolution.probability * 0.65
    costly_threshold = resolution.probability
    partial_failure_threshold = resolution.probability + (1.0 - resolution.probability) * 0.25
    severe_failure_threshold = resolution.probability + (1.0 - resolution.probability) * 0.90
    if resolution.random_roll < critical_threshold:
        resolution.outcome = "大成功"
    elif resolution.random_roll < normal_threshold:
        resolution.outcome = "普通成功"
    elif resolution.random_roll < costly_threshold:
        resolution.outcome = "成功但付出代价"
    elif resolution.random_roll < partial_failure_threshold:
        resolution.outcome = "失败但获得部分信息"
    elif resolution.random_roll < severe_failure_threshold:
        resolution.outcome = "严重失败"
    elif resolution.death_allowed:
        resolution.outcome = "死亡"
    else:
        resolution.outcome = "战败"
    resolution.components = deepcopy(resolution.components)
    resolution.components["dilution_multiplier"] = multiplier
    resolution.components["outcome_thresholds"] = {
        "critical": rounded(critical_threshold),
        "normal": rounded(normal_threshold),
        "costly": rounded(costly_threshold),
        "partial_failure": rounded(partial_failure_threshold),
        "severe_failure": rounded(severe_failure_threshold),
    }
    return resolution


def apply_combat_dilution(
    resolution: CombatResolution,
    multiplier: float,
    *,
    attacker: Optional[Mapping[str, Any]] = None,
    defender: Optional[Mapping[str, Any]] = None,
    weapon: Optional[Mapping[str, Any]] = None,
    skill: Optional[Mapping[str, Any]] = None,
    environment: Optional[Mapping[str, Any]] = None,
    seed: str = "",
) -> CombatResolution:
    """用原始战斗输入重新计算稀释后的全部派生字段。"""
    multiplier = clamp(number(multiplier, 1.0), 0.25, 1.0)
    if multiplier >= 1.0:
        return resolution
    if attacker is None or defender is None:
        raise ValueError("战斗稀释必须提供 attacker 和 defender 以重新计算完整结果")
    return calculate_combat(
        attacker,
        defender,
        weapon=weapon,
        skill=skill,
        environment=environment,
        seed=seed,
        dilution_multiplier=multiplier,
    )


def _skill_modifier(skill: Optional[Mapping[str, Any]]) -> float:
    if not isinstance(skill, Mapping):
        return 1.0
    if "multiplier" in skill:
        return max(0.0, number(skill.get("multiplier"), 1.0))
    return 1.0 + max(0.0, number(skill.get("level"), 1.0) - 1.0) * 0.10


def _environment_modifier(environment: Mapping[str, Any], key: str) -> float:
    return max(0.1, 1.0 + number(environment.get(key), 0.0) / 100.0)


def calculate_combat(attacker: Mapping[str, Any], defender: Mapping[str, Any], weapon: Optional[Mapping[str, Any]] = None, skill: Optional[Mapping[str, Any]] = None, environment: Optional[Mapping[str, Any]] = None, seed: str = "", dilution_multiplier: float = 1.0) -> CombatResolution:
    environment = environment or {}
    weapon = weapon or {}
    dilution_multiplier = clamp(number(dilution_multiplier, 1.0), 0.25, 1.0)
    attacker_state = state_modifier(attacker)
    defender_state = state_modifier(defender)
    attack_attribute = "agility" if weapon.get("attack_type") == "ranged" else "strength"
    base_attribute = attribute_value(attacker, attack_attribute)
    weapon_attack = number(weapon.get("attack"), equipment_stat(weapon, "attack"))
    armor_defense = number(defender.get("armor"), 0.0) + number(defender.get("equipment_defense"), 0.0)
    skill_modifier = _skill_modifier(skill)
    equipment_modifier = 1.0 + weapon_attack / 100.0
    environment_modifier = _environment_modifier(environment, "attack_bonus")
    attack = base_attribute * skill_modifier * equipment_modifier * attacker_state * environment_modifier * dilution_multiplier

    defense_skill = number(defender.get("defense_skill"), 0.0)
    terrain_cover = number(environment.get("terrain_cover"), 0.0)
    injury_penalty = injury_severity(defender) * 0.20
    defense = attribute_value(defender, "constitution") + armor_defense + defense_skill + terrain_cover - injury_penalty
    defense = max(0.0, defense)

    weapon_accuracy = number(weapon.get("accuracy"), equipment_stat(weapon, "accuracy"))
    skill_accuracy = number(skill.get("accuracy"), 0.0) if isinstance(skill, Mapping) else 0.0
    raw_attacker_accuracy = attribute_value(attacker, "agility") * 2.0 + weapon_accuracy + skill_accuracy + number(environment.get("accuracy_bonus"), 0.0)
    defender_evasion = attribute_value(defender, "agility") * 2.0 + number(defender.get("equipment_evasion"), 0.0) + number(environment.get("defender_evasion_bonus"), 0.0)
    attacker_accuracy = defender_evasion + (raw_attacker_accuracy - defender_evasion) * dilution_multiplier
    k = DIFFICULTY_K.get(str(environment.get("difficulty", "标准")), 10.0)
    hit_probability = rounded(sigmoid((attacker_accuracy - defender_evasion) / k))
    random_roll = rounded(deterministic_roll(seed, "combat-hit"))
    hit = random_roll < hit_probability
    raw_damage = max(0.0, attack - defense * 0.50) if hit else 0.0
    damage_multiplier = number(skill.get("damage_multiplier"), 1.0) if isinstance(skill, Mapping) else 1.0
    damage_multiplier = 1.0 + (damage_multiplier - 1.0) * dilution_multiplier
    damage = rounded(max(0.0, raw_damage * damage_multiplier))
    retreat_probability = rounded(clamp(0.4 + (attribute_value(attacker, "agility") - attribute_value(defender, "agility")) / 20.0 + number(environment.get("retreat_bonus"), 0.0), 0.05, 0.95))

    ammo_cost = int(max(0, number(weapon.get("ammo_cost"), 0)))
    ammo_available = number(weapon.get("ammo_available"), float("inf"))
    ammo_sufficient = ammo_available >= ammo_cost
    durability_available = weapon.get("durability") is None or number(weapon.get("durability")) > 0
    if not ammo_sufficient or not durability_available:
        hit = False
        damage = 0.0
    durability = weapon.get("durability")
    durability_after = None if durability is None else max(0.0, number(durability) - 1.0)
    status_effects = []
    if hit and isinstance(skill, Mapping):
        for effect in skill.get("effects", []) if isinstance(skill.get("effects"), list) else []:
            if isinstance(effect, Mapping) and effect.get("type") in {"status", "debuff"}:
                effect_copy = deepcopy(dict(effect))
                if dilution_multiplier < 1.0:
                    effect_copy["dilution_multiplier"] = dilution_multiplier
                    for key in ("magnitude", "strength", "chance"):
                        if isinstance(effect_copy.get(key), (int, float)):
                            effect_copy[key] = rounded(float(effect_copy[key]) * dilution_multiplier)
                status_effects.append(effect_copy)
    damage_ratio = damage / max(attribute_value(defender, "constitution") * 10.0, 1.0)
    target_hp = max(1.0, number(defender.get("hp"), attribute_value(defender, "constitution") * 10.0))
    target_downed = damage >= target_hp

    # 目标有攻击力时，未被击倒的目标会进行一次反击；旧的自定义目标没有
    # attack 字段，因此保持原有单向攻击行为兼容。
    defender_attack = max(0.0, number(defender.get("attack"), 0.0))
    counterattack_hit = False
    incoming_damage = 0.0
    counterattack_probability = 0.0
    if defender_attack > 0 and not target_downed and environment.get("counterattack", True):
        defender_accuracy = attribute_value(defender, "agility") * 2.0 + number(defender.get("accuracy"), 0.0)
        attacker_evasion = attribute_value(attacker, "agility") * 2.0 + number(attacker.get("equipment_evasion"), 0.0)
        counterattack_probability = sigmoid((defender_accuracy - attacker_evasion) / k)
        counterattack_hit = deterministic_roll(seed, "combat-counter-hit") < counterattack_probability
        if counterattack_hit:
            incoming_damage = rounded(max(0.0, defender_attack - number(attacker.get("armor"), 0.0) * 0.50))

    death_risk = rounded(clamp(damage_ratio * 100.0 + incoming_damage / max(number(attacker.get("max_hp"), 50.0), 1.0) * 100.0, 0.0, 100.0))
    return CombatResolution(
        formula_version=FORMULA_VERSION,
        attacker_attack=rounded(attack),
        defender_defense=rounded(defense),
        attacker_accuracy=rounded(attacker_accuracy),
        defender_evasion=rounded(defender_evasion),
        hit_probability=hit_probability,
        random_roll=random_roll,
        hit=hit,
        ammo_sufficient=ammo_sufficient,
        outcome="命中" if hit else "未命中",
        damage=damage,
        retreat_probability=retreat_probability,
        ammo_consumed=ammo_cost,
        weapon_durability_after=durability_after,
        status_effects=status_effects,
        death_risk=death_risk,
        components={"base_attribute": base_attribute, "skill_modifier": skill_modifier, "equipment_modifier": equipment_modifier, "state_modifier": attacker_state, "environment_modifier": environment_modifier, "defender_state_modifier": defender_state, "injury_penalty": injury_penalty, "ammo_available": ammo_available, "durability_available": durability_available, "target_hp": target_hp, "counterattack_probability": rounded(counterattack_probability), "dilution_multiplier": dilution_multiplier},
        incoming_damage=incoming_damage,
        counterattack_hit=counterattack_hit,
    )


def experience_decay(player_level: int, monster_level: int) -> float:
    """采用用户最新指定的低级怪经验衰减：低1/2/3/4+级=100/60/25/5%。"""
    difference = int(player_level) - int(monster_level)
    if difference <= 1:
        return 1.0
    if difference == 2:
        return 0.60
    if difference == 3:
        return 0.25
    return 0.05


def calculate_experience(player_level: int, monster_level: int, quality: str = "普通", quantity: int = 1) -> float:
    base = number(monster_level) * 10.0 * QUALITY_MULTIPLIER.get(quality, 1.0)
    return rounded(base * experience_decay(player_level, monster_level) * max(0, int(quantity)))


def level_threshold(level: int) -> int:
    return int(100 * (2 ** max(0, int(level) - 1)))


def talent_options_for_level(level: int) -> List[Dict[str, Any]]:
    """为升级生成稳定的三选一；候选由规则引擎生成，LLM 只能选择其一。"""
    level = int(level)
    return [
        {
            "id": f"level_{level}_field_sense",
            "category": "信息类",
            "name": "野外感知",
            "description": "探索时更容易从环境中提取有效线索。",
            "effect": {"action_modifiers": {"EXPLORATION": {"intelligence": 5, "unknown_risk": -3}}},
        },
        {
            "id": f"level_{level}_iron_body",
            "category": "个人类",
            "name": "耐受强化",
            "description": "体质永久提高一点，伤势和疲劳造成的行动阻力降低。",
            "effect": {"attribute_bonus": {"constitution": 1}, "action_modifiers": {"COMBAT": {"preparation": 2}}},
        },
        {
            "id": f"level_{level}_salvage_hand",
            "category": "建设类",
            "name": "回收巧手",
            "description": "建造和修理时能把准备工作转化为更稳定的施工结果。",
            "effect": {"action_modifiers": {"BUILD": {"preparation": 5}}},
        },
    ]


def advance_progression(player: Mapping[str, Any], gained_exp: float) -> Dict[str, Any]:
    updated = deepcopy(dict(player))
    updated["level"] = int(number(updated.get("level"), 1))
    updated["exp"] = number(updated.get("exp"), 0.0) + max(0.0, number(gained_exp))
    updated["exp_to_next"] = level_threshold(updated["level"])
    levels_gained = 0
    while updated["exp"] >= updated["exp_to_next"]:
        updated["exp"] -= updated["exp_to_next"]
        updated["level"] += 1
        levels_gained += 1
        updated["exp_to_next"] = level_threshold(updated["level"])
        attributes = updated.setdefault("attributes", {})
        for key in ("strength", "constitution", "agility", "spirit"):
            attributes[key] = number(attributes.get(key), 5.0) + 1
        updated["free_points"] = int(number(updated.get("free_points"), 0)) + 2
    updated["exp"] = rounded(updated["exp"])
    updated["levels_gained"] = levels_gained
    updated["talent_choice_required"] = levels_gained > 0
    if levels_gained > 0:
        updated["pending_decision"] = {
            "type": "TALENT_CHOICE",
            "level": updated["level"],
            "options": talent_options_for_level(updated["level"]),
            "must_resolve_before_continue": True,
        }
    return updated


def skill_cost(skill: Mapping[str, Any]) -> Dict[str, float]:
    cost = skill.get("cost", {})
    if isinstance(cost, Mapping):
        return {str(key): number(value) for key, value in cost.items()}
    if cost in (None, ""):
        return {}
    return {"stamina": number(cost)}


def check_skill_use(skill: Mapping[str, Any], player: Mapping[str, Any], inventory: Mapping[str, Any]) -> List[str]:
    errors = []
    if int(number(skill.get("cooldown_remaining"), 0)) > 0:
        errors.append("技能仍在冷却中")
    cost = skill_cost(skill)
    if number(player.get("fatigue"), 0) + cost.get("stamina", 0) > 100:
        errors.append("体力不足")
    if number(player.get("mental", 100), 100) - cost.get("mental", 0) < 0:
        errors.append("精神不足")
    resources = inventory.get("resources", {}) if isinstance(inventory, Mapping) else {}
    for resource, amount in cost.items():
        if resource in {"stamina", "mental"}:
            continue
        if number(resources.get(resource), 0) < amount:
            errors.append(f"资源不足：{resource}")
    return errors


def apply_skill_cost(skill: Mapping[str, Any], player: Mapping[str, Any], inventory: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    new_player, new_inventory = deepcopy(dict(player)), deepcopy(dict(inventory))
    cost = skill_cost(skill)
    new_player["fatigue"] = clamp(number(new_player.get("fatigue")) + cost.get("stamina", 0.0), 0.0, 100.0)
    new_player["mental"] = clamp(number(new_player.get("mental"), 100.0) - cost.get("mental", 0.0), 0.0, 100.0)
    resources = new_inventory.setdefault("resources", {})
    for resource, amount in cost.items():
        if resource not in {"stamina", "mental"}:
            resources[resource] = number(resources.get(resource)) - amount
    return new_player, new_inventory


def tick_cooldowns(player: Mapping[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(dict(player))
    skills = updated.get("skills", [])
    if isinstance(skills, list):
        for skill in skills:
            if isinstance(skill, dict):
                skill["cooldown_remaining"] = max(0, int(number(skill.get("cooldown_remaining"), 0)) - 1)
    return updated


def calculate_farmability(components: Mapping[str, Any]) -> float:
    score = (
        0.25 * clamp(number(components.get("combat_advantage")))
        + 0.20 * clamp(number(components.get("enemy_information")))
        + 0.15 * clamp(number(components.get("kill_stability")))
        + 0.15 * clamp(number(components.get("sustainability")))
        + 0.15 * clamp(number(components.get("route_familiarity")))
        + 0.10 * clamp(number(components.get("extraction_ability")))
        - clamp(number(components.get("unknown_danger_penalty")), 0.0, 20.0)
    )
    return rounded(clamp(score))


def farmability_mode(score: float) -> str:
    if score < 40:
        return "逐场详处"
    if score < 60:
        return "批量3-10只"
    if score < 80:
        return "模拟几十只"
    return "长时间刷怪"


def simulate_batch_action(area: Mapping[str, Any], player_level: int, minutes: float, kill_success_rate: float, ammo_available: float, ammo_per_kill: float, weapon_rate_per_hour: float, recovery_efficiency: float, backpack_capacity_modifier: float, enemy_groups: Sequence[Mapping[str, Any]], farmability_components: Mapping[str, Any], stop_conditions: Optional[Mapping[str, Any]] = None) -> BatchResolution:
    """按10分钟时间片模拟刷怪，任何中断条件在下一时间片前生效。"""
    farmability = calculate_farmability(farmability_components)
    hours = max(0.0, number(minutes)) / 60.0
    density = number(area.get("monster_density_per_hour"), number(area.get("monster_density"), 0.0))
    route_coverage = clamp(number(area.get("route_coverage"), 100.0)) / 100.0
    search_efficiency = clamp(number(area.get("search_efficiency"), 100.0)) / 100.0
    alertness_modifier = clamp(number(area.get("monster_alertness_modifier"), 100.0), 0.0, 200.0) / 100.0
    encounter_count = max(0.0, density * route_coverage * hours * search_efficiency * alertness_modifier)
    population = area.get("monster_population", area.get("population"))
    population_remaining = max(0.0, number(population)) if population is not None else None
    alertness = clamp(number(area.get("alertness", 0.0)))
    adaptation = clamp(number(area.get("monster_adaptation", 0.0)))
    alertness_gain = max(0.0, number(area.get("alertness_gain_per_kill", 1.5)))
    adaptation_gain = max(0.0, number(area.get("adaptation_gain_per_kill", 0.5)))
    starting_alertness_factor = max(0.25, 1.0 - alertness / 200.0)
    starting_adaptation_factor = max(0.25, 1.0 - adaptation / 200.0)
    weights = [max(0.0, number(group.get("weight"), 1.0)) for group in enemy_groups]
    total_weight = sum(weights) or 1.0
    kills_by_level: Dict[str, float] = {}
    total_experience = 0.0
    theoretical_drops: Dict[str, float] = {}
    stop_conditions = stop_conditions or {}
    interruptions = []
    total_kills = 0
    processed_minutes = 0.0
    processed_encounters = 0.0
    encounter_pool = 0.0
    slices = max(1, int(math.ceil(max(0.0, number(minutes)) / 10.0)))
    for slice_index in range(slices):
        slice_end = min(max(0.0, number(minutes)), (slice_index + 1) * 10.0)
        slice_minutes = max(0.0, slice_end - processed_minutes)
        slice_hours = slice_minutes / 60.0
        slice_encounters = max(0.0, density * route_coverage * slice_hours * search_efficiency * alertness_modifier * starting_alertness_factor)
        if population_remaining is not None:
            slice_encounters = min(slice_encounters, population_remaining)
        encounter_pool += slice_encounters
        remaining_ammo = max(0.0, number(ammo_available) - total_kills * max(0.0, number(ammo_per_kill)))
        cumulative_weapon_limit = max(0.0, number(weapon_rate_per_hour)) * (slice_end / 60.0)
        cumulative_ammo_limit = max(0.0, number(ammo_available)) / max(1.0, number(ammo_per_kill))
        cumulative_success_limit = encounter_pool * clamp(number(kill_success_rate), 0.0, 1.0) * starting_adaptation_factor
        cumulative_capacity = math.floor(min(cumulative_success_limit, cumulative_weapon_limit, cumulative_ammo_limit) + 1e-9)
        slice_kills = max(0, cumulative_capacity - total_kills)
        total_kills += slice_kills
        processed_minutes = slice_end
        processed_encounters += slice_encounters
        if population_remaining is not None:
            population_remaining = max(0.0, population_remaining - slice_kills)
        alertness = clamp(alertness + slice_kills * alertness_gain)
        adaptation = clamp(adaptation + slice_kills * adaptation_gain)
        if not enemy_groups:
            slice_kills = 0
        if slice_kills:
            allocated = [int(math.floor(slice_kills * weight / total_weight)) for weight in weights]
            for index in range(slice_kills - sum(allocated)):
                allocated[index % len(allocated)] += 1
            for index, group in enumerate(enemy_groups):
                kills = allocated[index]
                if kills <= 0:
                    continue
                level = int(number(group.get("level"), player_level))
                quality = str(group.get("quality", "普通"))
                key = str(level)
                kills_by_level[key] = int(kills_by_level.get(key, 0) + kills)
                total_experience += calculate_experience(player_level, level, quality, int(kills))
                for resource, amount in (group.get("drops", {}) or {}).items():
                    theoretical_drops[str(resource)] = theoretical_drops.get(str(resource), 0.0) + kills * number(amount)
                for resource, amount in (group.get("rare_drops", {}) or {}).items():
                    theoretical_drops[str(resource)] = theoretical_drops.get(str(resource), 0.0) + kills * number(amount)
                    if stop_conditions.get("stop_on_rare_drop") or stop_conditions.get("rare_drop"):
                        interruptions.append("发现稀有掉落")
        consumed = total_kills * max(0.0, number(ammo_per_kill))
        if stop_conditions.get("ammo_below") is not None and number(ammo_available) - consumed <= number(stop_conditions["ammo_below"]):
            interruptions.append("弹药达到停止阈值")
        slice_risk = clamp(sum(clamp(number(farmability_components.get(key)), 0.0, 100.0) for key in ("noise_exposure", "fatigue_risk", "injury_risk", "area_alertness", "daylight_change", "monster_adaptation")) / 6.0 + slice_index * 2.0)
        if stop_conditions.get("risk_above") is not None and slice_risk >= number(stop_conditions["risk_above"]):
            interruptions.append("刷怪风险达到停止阈值")
        if stop_conditions.get("environment_change") and slice_index >= 0:
            interruptions.append("环境变化")
        if population_remaining is not None and population_remaining <= 0:
            interruptions.append("区域怪物数量耗尽")
        if interruptions:
            break
    recovered = {resource: rounded(amount * clamp(recovery_efficiency, 0.0, 1.0) * clamp(backpack_capacity_modifier, 0.0, 1.0)) for resource, amount in theoretical_drops.items()}
    risk = rounded(clamp(sum(clamp(number(farmability_components.get(key)), 0.0, 100.0) for key in ("noise_exposure", "fatigue_risk", "injury_risk", "area_alertness", "daylight_change", "monster_adaptation")) / 6.0))
    return BatchResolution(
        formula_version=FORMULA_VERSION,
        farmability=farmability,
        mode=farmability_mode(farmability),
        encounter_count=rounded(processed_encounters),
        kills_by_level=kills_by_level,
        total_kills=int(total_kills),
        total_experience=rounded(total_experience),
        outcome="批量结算（已完成）" if not interruptions else "批量结算（触发中断）",
        recovered_resources=recovered,
        ammo_consumed=rounded(total_kills * max(0.0, number(ammo_per_kill))),
        durability_cost=rounded(total_kills),
        risk=risk,
        interruption_reasons=interruptions,
        components={"density": density, "route_coverage": route_coverage, "effective_action_time_hours": processed_minutes / 60.0, "time_slice_minutes": 10, "search_efficiency": search_efficiency, "monster_alertness_modifier": alertness_modifier, "population_remaining": population_remaining, "alertness_after": alertness, "monster_adaptation_after": adaptation, "theoretical_drops": theoretical_drops},
    )


def calculate_grind_net_value(experience_value: float, drop_value: float, area_clear_value: float, ammo_cost: float, durability_cost: float, injury_risk: float, time_cost: float, missed_event_value: float) -> float:
    return rounded(experience_value + drop_value + area_clear_value - ammo_cost - durability_cost - injury_risk - time_cost - missed_event_value)


def calculate_resource_pressure(resources: Mapping[str, Any]) -> Dict[str, Any]:
    per_resource = {}
    for resource_id, raw in resources.items():
        record = raw if isinstance(raw, Mapping) else {"current": raw}
        current = number(record.get("current"), 0.0)
        demand = max(0.0, number(record.get("demand"), number(record.get("consumption_rate"), 0.0)))
        income = max(0.0, number(record.get("income_rate"), 0.0))
        gap = clamp((demand - current) / max(demand, 1.0) * 100.0)
        consumption_income = clamp(number(record.get("consumption_income_ratio"), (demand / max(income, 1.0)) * 50.0))
        blocked = clamp(number(record.get("blocked_count"), 0.0) * 20.0)
        next_need = max(0.0, number(record.get("next_stage_need"), 0.0))
        next_stage = clamp((next_need - current) / max(next_need, 1.0) * 100.0)
        perceived = clamp(number(record.get("perceived", record.get("perceived_level", 0.0))))
        score = rounded(0.30 * gap + 0.20 * consumption_income + 0.20 * blocked + 0.15 * next_stage + 0.15 * perceived)
        per_resource[str(resource_id)] = {"score": score, "components": {"current_gap": rounded(gap), "consumption_income_ratio": rounded(consumption_income), "recent_blocked": rounded(blocked), "next_stage_need": rounded(next_stage), "perceived": rounded(perceived)}}
    scores = [item["score"] for item in per_resource.values()]
    return {"score": rounded(sum(scores) / len(scores)) if scores else 0.0, "resources": per_resource}


def calculate_npc_utility(components: Mapping[str, Any]) -> float:
    positive = sum(clamp(number(components.get(key))) for key in ("goal_fit", "survival_benefit", "resource_benefit", "relationship_impact", "value_alignment"))
    negative = sum(clamp(number(components.get(key))) for key in ("risk", "cost"))
    return rounded(positive - negative)


def calculate_build(base: Mapping[str, Any], module: Mapping[str, Any], inventory: Mapping[str, Any], available_minutes: float) -> Dict[str, Any]:
    """检查基地模块的材料、时间和空间，不直接改变库存。"""
    build_cost = module.get("build_cost", module.get("cost", {}))
    build_cost = build_cost if isinstance(build_cost, Mapping) else {}
    resources = inventory.get("resources", {}) if isinstance(inventory.get("resources", {}), Mapping) else {}
    missing = {str(key): rounded(number(amount) - number(resources.get(key), 0.0)) for key, amount in build_cost.items() if number(resources.get(key), 0.0) < number(amount)}
    space_total = number(base.get("space_total"), number(base.get("space"), 0.0))
    space_used = number(base.get("space_used"), 0.0)
    space_cost = number(module.get("space_cost"), 0.0)
    time_required = number(module.get("build_time"), number(module.get("construction_time"), 0.0))
    errors = []
    if missing:
        errors.append("材料不足")
    if space_used + space_cost > space_total:
        errors.append("基地空间不足")
    if time_required > number(available_minutes):
        errors.append("建造时间不足")
    return {"formula_version": FORMULA_VERSION, "success": not errors, "errors": errors, "time_required": rounded(time_required), "space_cost": rounded(space_cost), "maintenance": module.get("maintenance", {}), "resource_changes": {str(key): -number(value) for key, value in build_cost.items()}, "missing_resources": missing}


def calculate_base_maintenance(base: Mapping[str, Any], inventory: Mapping[str, Any], days: float = 1.0) -> Dict[str, Any]:
    required: Dict[str, float] = {}
    for module in base.get("modules", []) if isinstance(base.get("modules"), list) else []:
        if not isinstance(module, Mapping):
            continue
        maintenance = module.get("maintenance", {})
        if isinstance(maintenance, Mapping):
            for resource, amount in maintenance.items():
                required[str(resource)] = required.get(str(resource), 0.0) + number(amount) * max(0.0, days)
    resources = inventory.get("resources", {}) if isinstance(inventory.get("resources", {}), Mapping) else {}
    missing = {resource: rounded(amount - number(resources.get(resource), 0.0)) for resource, amount in required.items() if number(resources.get(resource), 0.0) < amount}
    resource_changes = {key: -rounded(min(value, number(resources.get(key), 0.0))) for key, value in required.items()}
    durability_delta = -5.0 * max(0.0, days) if missing else 0.0
    return {"formula_version": FORMULA_VERSION, "days": rounded(days), "required": {key: rounded(value) for key, value in required.items()}, "missing_resources": missing, "resource_changes": resource_changes, "durability_delta": rounded(durability_delta), "status": "maintained" if not missing else "maintenance_shortage"}


def calculate_base_defense(base: Mapping[str, Any], player_power: float = 0.0, teammate_power: float = 0.0, incoming_power: float = 0.0) -> Dict[str, Any]:
    defense = number(base.get("defense"), 0.0)
    module_bonus = 0.0
    for module in base.get("modules", []) if isinstance(base.get("modules"), list) else []:
        if isinstance(module, Mapping):
            module_bonus += number(module.get("defense_bonus"), 0.0)
            effects = module.get("effects", {})
            if isinstance(effects, Mapping):
                module_bonus += number(effects.get("defense"), 0.0)
    total = defense + module_bonus + number(player_power) + number(teammate_power)
    ratio = total / max(number(incoming_power), 1.0)
    if ratio > 1.5:
        result = "完胜"
    elif ratio > 1.0:
        result = "胜利"
    elif ratio >= 0.5:
        result = "惨胜"
    else:
        result = "基地毁灭"
    return {"defense": rounded(total), "incoming_power": rounded(incoming_power), "ratio": rounded(ratio), "result": result}


def calculate_combinability(components: Mapping[str, Any]) -> float:
    time_factor = components.get("time_compatibility", components.get("time_remaining"))
    factors = [clamp(number(time_factor), 0.0, 1.0)]
    factors.extend(
        clamp(number(components.get(key), 1.0), 0.0, 1.0)
        for key in (
            "resource_compatibility",
            "location_proximity",
            "goal_compatibility",
            "npc_availability",
            "attention_compatibility",
            "action_slot_compatibility",
            "commitment_compatibility",
            "opportunity_window_compatibility",
            "movement_compatibility",
        )
    )
    return rounded(math.prod(factors) * 100.0)


def calculate_repetition_fatigue(event_history: Sequence[Mapping[str, Any]], window: int = 10) -> Dict[str, Any]:
    recent = list(event_history[-window:])
    occurrences: Dict[str, List[int]] = {}
    for index, event in enumerate(recent):
        event_type = str(event.get("type", event.get("event_type", "UNKNOWN")))
        occurrences.setdefault(event_type, []).append(index)
    scores = {}
    for event_type, indexes in occurrences.items():
        if len(indexes) <= 1:
            score = 0.0
        else:
            intervals = [right - left for left, right in zip(indexes, indexes[1:])]
            score = sum(30.0 if interval < 3 else 15.0 if interval <= 5 else 0.0 for interval in intervals) / len(intervals)
        scores[event_type] = rounded(score)
    return {"max": max(scores.values(), default=0.0), "by_type": scores}


def calculate_risk_credibility(values: Mapping[str, Any]) -> float:
    result = 1.0
    for key in ("cost_fulfillment", "failure_clarity", "enemy_effectiveness", "information_incompleteness", "limited_protection"):
        result *= clamp(number(values.get(key)), 0.0, 1.0)
    return rounded(result)


def calculate_narrative_metrics(state: Mapping[str, Any], event_history: Sequence[Mapping[str, Any]], payoff: Optional[Mapping[str, Any]] = None, decision: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    meta = state.get("meta", {}) if isinstance(state.get("meta"), Mapping) else {}
    narrative_state = meta.get("narrative_state", {}) if isinstance(meta.get("narrative_state"), Mapping) else {}
    pressure = meta.get("pressure_inputs", {}) if isinstance(meta.get("pressure_inputs"), Mapping) else {}
    if not pressure:
        pressure = narrative_state.get("pressure_components", {}) if isinstance(narrative_state.get("pressure_components"), Mapping) else {}
    pressure_score = rounded(0.25 * clamp(number(pressure.get("survival_threat"))) + 0.20 * clamp(number(pressure.get("resource_scarcity"))) + 0.20 * clamp(number(pressure.get("time_pressure"))) + 0.15 * clamp(number(pressure.get("information_unknown"))) + 0.10 * clamp(number(pressure.get("interpersonal_conflict"))) + 0.10 * clamp(number(pressure.get("failure_accumulation"))))
    irreversible_types = {"LEVEL_UP", "CHARACTER_DIED", "AREA_DISCOVERED", "MYSTERY_RESOLVED", "FACTION_JOINED", "BASE_UPGRADED", "WORLD_EVENT"}
    total = len(event_history)
    stagnant = sum(1 for event in event_history[-20:] if str(event.get("type", event.get("event_type", ""))) not in irreversible_types)
    stagnation = rounded(stagnant / max(min(total, 20), 1))
    payoff = payoff or {}
    maturity = rounded(0.25 * clamp(number(payoff.get("scarcity_pressure"))) + 0.20 * clamp(number(payoff.get("setup_depth"))) + 0.20 * clamp(number(payoff.get("waiting_time"))) + 0.20 * clamp(number(payoff.get("cost_paid"))) + 0.15 * clamp(number(payoff.get("chapter_rhythm"))))
    impact = rounded(0.25 * clamp(number(payoff.get("relative_gain"))) + 0.25 * clamp(number(payoff.get("restriction_removed"))) + 0.20 * clamp(number(payoff.get("behavior_change"))) + 0.15 * clamp(number(payoff.get("long_term_value"))) + 0.15 * clamp(number(payoff.get("social_feedback"))))
    novelty = rounded(clamp(100.0 - number(payoff.get("same_type_last_20")) * 15.0 - number(payoff.get("similar_structure_last_50")) * 8.5))
    causality = rounded(0.30 * clamp(number(payoff.get("causal_chain"))) + 0.25 * clamp(number(payoff.get("rule_consistency"))) + 0.25 * clamp(number(payoff.get("cost_paid"))) + 0.20 * clamp(number(payoff.get("reward_foreshadowed"))))
    aftermath = rounded(0.30 * clamp(number(payoff.get("new_playable_system"))) + 0.25 * clamp(number(payoff.get("decision_change"))) + 0.25 * clamp(number(payoff.get("higher_resource_need"))) + 0.20 * clamp(number(payoff.get("social_market_effect"))))
    payoff_score = rounded(clamp(0.25 * maturity + 0.25 * impact + 0.15 * novelty + 0.15 * causality + 0.20 * aftermath - 0.10 * clamp(number(payoff.get("fatigue"))) - 0.10 * clamp(number(payoff.get("story_damage")))))
    mysteries = meta.get("active_mystery_records", []) if isinstance(meta.get("active_mystery_records"), list) else []
    if not mysteries and isinstance(meta.get("active_mysteries"), list):
        mysteries = [{"id": value, "importance": 1, "waiting_turns": 0, "reminder_count": 0, "visibility": 1, "progress": 0} for value in meta["active_mysteries"]]
    narrative_debt = []
    for mystery in mysteries:
        if isinstance(mystery, Mapping):
            debt = number(mystery.get("importance"), 1) * number(mystery.get("waiting_turns"), 0) * number(mystery.get("reminder_count"), 0) * clamp(number(mystery.get("visibility")), 0.0, 1.0) / max(number(mystery.get("progress"), 1), 1.0)
            narrative_debt.append({"id": mystery.get("id"), "score": rounded(debt)})
    progress = decision or {}
    progress_score = rounded(0.20 * clamp(number(progress.get("permanent_growth"))) + 0.20 * clamp(number(progress.get("world_change"))) + 0.15 * clamp(number(progress.get("relationship_change"))) + 0.15 * clamp(number(progress.get("information_change"))) + 0.15 * clamp(number(progress.get("goal_progress"))) + 0.15 * clamp(number(progress.get("new_playable_system"))))
    decision_value = rounded(math.prod(clamp(number(decision.get(key)), 0.0, 1.0) for key in ("consequence_difference", "opportunity_cost", "irreversibility", "information_uncertainty", "value_impact", "route_divergence"))) if decision else 0.0
    agency = rounded(math.prod(clamp(number(decision.get(key)), 0.0, 1.0) for key in ("option_balance", "consequence_difference", "information_sufficiency", "opportunity_cost", "long_term_impact"))) if decision else 0.0
    uncertainty_inputs = decision.get("uncertainty", {}) if decision and isinstance(decision.get("uncertainty"), Mapping) else {}
    uncertainty = rounded(0.30 * clamp(number(uncertainty_inputs.get("danger_unknown"))) + 0.25 * clamp(number(uncertainty_inputs.get("rule_unknown"))) + 0.20 * clamp(number(uncertainty_inputs.get("motive_unknown"))) + 0.15 * clamp(number(uncertainty_inputs.get("world_unknown"))) + 0.10 * clamp(number(uncertainty_inputs.get("reward_unknown"))))
    risk_credibility = calculate_risk_credibility(decision.get("risk_credibility", {}) if decision and isinstance(decision.get("risk_credibility"), Mapping) else {})
    repetition = calculate_repetition_fatigue(event_history)
    combinability = calculate_combinability(decision.get("combinability", {})) if decision and isinstance(decision.get("combinability"), Mapping) else 0.0
    return {"pressure": pressure_score, "payoff_maturity": maturity, "payoff_impact": impact, "payoff_score": payoff_score, "narrative_debt": narrative_debt, "progress": progress_score, "stagnation_rate": stagnation, "repetition_fatigue": repetition, "agency": agency, "uncertainty": uncertainty, "risk_credibility": risk_credibility, "decision_value": decision_value, "combinability": combinability}
