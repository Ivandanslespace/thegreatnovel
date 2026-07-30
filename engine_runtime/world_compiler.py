"""将 LLM 创作的世界蓝图编译为可执行的世界注册表。

内容创作属于世界创建阶段：地点、敌人、NPC、势力、职业、母题和禁忌都由
本次世界蓝图给出。编译器只负责把这些语义内容接入稳定的行动、成本和状态
投影结构；它不根据主题关键词替换成预置世界内容。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Sequence


COMPILER_VERSION = "1.4"


def _mapping(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"world_blueprint.{label} 必须是对象")
    return deepcopy(dict(value))


def _text(record: Mapping[str, Any], key: str, label: str) -> str:
    value = str(record.get(key, "")).strip()
    if not value:
        raise ValueError(f"world_blueprint.{label}.{key} 不能为空")
    return value


def _record_id(record: Mapping[str, Any], label: str) -> str:
    return _text(record, "id", label)


def _profession_definitions(raw_professions: Any) -> Dict[str, Dict[str, Any]]:
    """职业仅接受本次世界包的原创定义，不存在全局职业白名单。"""
    if isinstance(raw_professions, Mapping):
        definitions = {
            str(profession_id): deepcopy(dict(definition))
            for profession_id, definition in raw_professions.items()
            if isinstance(definition, Mapping)
        }
    elif isinstance(raw_professions, list):
        definitions = {
            str(definition.get("id")): deepcopy(dict(definition))
            for definition in raw_professions
            if isinstance(definition, Mapping) and definition.get("id")
        }
    elif raw_professions in (None, {}):
        definitions = {}
    else:
        raise ValueError("professions 必须是对象或列表")

    for profession_id, definition in definitions.items():
        definition.setdefault("id", profession_id)
        if str(definition["id"]) != profession_id:
            raise ValueError(f"profession {profession_id} 的 id 必须与注册键一致")
        _text(definition, "name", f"professions.{profession_id}")
        if "attribute_bonuses" in definition:
            raise ValueError(f"profession {profession_id} 不能提交 attribute_bonuses；请使用 attribute_focus")
        attribute_focus = str(definition.get("attribute_focus") or "").strip()
        if attribute_focus:
            if attribute_focus not in {"strength", "constitution", "agility", "spirit"}:
                raise ValueError(f"profession {profession_id}.attribute_focus 不受支持")
            definition["attribute_bonuses"] = {attribute_focus: 2}
    return definitions


def _base_action_constraints(exclusive_group: str, commitment_axis: str, commitment_value: str, *, limited_to_daylight: bool) -> Dict[str, Any]:
    constraints = {
        "system_tags": ["major_action", "requires_full_attention"],
        "exclusive_group": exclusive_group,
        "window_ids": ["白天", "黄昏"],
        "window_capacity": 1,
        "commitment_axis": commitment_axis,
        "commitment_value": commitment_value,
    }
    if limited_to_daylight:
        constraints["availability"] = {"allowed_periods": ["白天", "黄昏"]}
        constraints["reservation"] = {"exclusive_group": exclusive_group, "window_id": "current_period", "capacity": 1}
    return constraints


def compile_world_bundle(
    theme: str,
    language: str,
    mechanics: Mapping[str, Any],
    safe_base: str,
    primary_resources: Sequence[str],
    genre_contract: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """将创意蓝图编译成可执行注册表。

    ``world_blueprint`` 是 LLM 在创建该世界时一次性创作的语义事实。它决定
    名称、危险、NPC、势力、模块和初始物件；数值成本和行动约束仍由这里统一
    派生，以避免叙述绕过规则引擎。
    """
    if not isinstance(mechanics, Mapping):
        raise ValueError("mechanics 必须是对象")
    blueprint = _mapping(mechanics.get("world_blueprint"), "")
    opening_area = _mapping(blueprint.get("opening_area"), "opening_area")
    area_id = _record_id(opening_area, "opening_area")
    area_name = _text(opening_area, "name", "opening_area")
    area_description = _text(opening_area, "description", "opening_area")
    danger_hint = _text(opening_area, "danger_hint", "opening_area")

    enemy = _mapping(blueprint.get("opening_enemy"), "opening_enemy")
    enemy_id = _record_id(enemy, "opening_enemy")
    enemy_name = _text(enemy, "name", "opening_enemy")
    enemy_hint = _text(enemy, "knowledge_hint", "opening_enemy")

    raw_modules = blueprint.get("base_modules")
    if not isinstance(raw_modules, list) or not raw_modules:
        raise ValueError("world_blueprint.base_modules 至少需要一个模块")
    module_specs = [_mapping(module, "base_modules") for module in raw_modules]
    module_ids = [_record_id(module, "base_modules") for module in module_specs]
    if len(set(module_ids)) != len(module_ids):
        raise ValueError("world_blueprint.base_modules 的 id 不能重复")
    for module in module_specs:
        _text(module, "name", "base_modules")
        _text(module, "description", "base_modules")

    starter_kit = _mapping(blueprint.get("starter_kit"), "starter_kit")
    main_weapon = _mapping(starter_kit.get("main_weapon"), "starter_kit.main_weapon")
    _record_id(main_weapon, "starter_kit.main_weapon")
    _text(main_weapon, "name", "starter_kit.main_weapon")
    starter_items = starter_kit.get("items", [])
    if not isinstance(starter_items, list):
        raise ValueError("world_blueprint.starter_kit.items 必须是列表")
    for item in starter_items:
        item_record = _mapping(item, "starter_kit.items")
        _record_id(item_record, "starter_kit.items")
        _text(item_record, "name", "starter_kit.items")

    recipe = _mapping(blueprint.get("starter_recipe"), "starter_recipe")
    recipe_id = _record_id(recipe, "starter_recipe")
    recipe_name = _text(recipe, "name", "starter_recipe")
    professions = _profession_definitions(mechanics.get("professions", {}))
    resources = [str(item).strip() for item in primary_resources if str(item).strip()]
    if not resources:
        raise ValueError("primary_resources 至少需要一种资源")
    primary_resource = resources[0]
    secondary_resource = resources[1] if len(resources) > 1 else primary_resource
    rare_resource = resources[2] if len(resources) > 2 else secondary_resource

    enemy_definition = {
        "id": enemy_id,
        "definition_id": enemy_id,
        "name": enemy_name,
        "description": str(enemy.get("description", "")).strip(),
        "level": 1,
        "quality": "普通",
        "hp": 30,
        "max_hp": 30,
        "attack": 6,
        "accuracy": 5,
        "defense_skill": 2,
        "armor": 1,
        "attributes": {"strength": 4, "constitution": 3, "agility": 4, "spirit": 2},
        "drops": {primary_resource: 2, secondary_resource: 1},
        "knowledge_hint": enemy_hint,
        "status": "definition",
        "location_id": area_id,
    }
    area = {
        "id": area_id,
        "name": area_name,
        "description": area_description,
        "location_id": area_id,
        "monster_density_per_hour": 4,
        "monster_population": 50,
        "alertness": 0,
        "monster_adaptation": 0,
        "route_coverage": 80,
        "search_efficiency": 80,
        "monster_alertness_modifier": 100,
        "kill_success_rate": 0.75,
        "ammo_per_kill": 1,
        "weapon_rate_per_hour": 6,
        "recovery_efficiency": 0.9,
        "backpack_capacity_modifier": 1.0,
        "enemy_groups": [{"level": 1, "quality": "普通", "weight": 1, "drops": deepcopy(enemy_definition["drops"])}],
        "farmability_components": {"combat_advantage": 50, "enemy_information": 35, "kill_stability": 55, "sustainability": 50, "route_familiarity": 25, "extraction_ability": 70, "unknown_danger_penalty": 20, "noise_exposure": 35, "fatigue_risk": 35, "injury_risk": 25, "area_alertness": 25, "daylight_change": 15, "monster_adaptation": 10},
        "extraction_rule": {"return_to": "camp_core", "deadline_minutes": 120, "requires_discovered_location": True},
        "encounter_target_ids": [enemy_id],
    }
    action_targets: Dict[str, Dict[str, Any]] = {
        area_id: {
            "id": area_id,
            "location_id": area_id,
            "action_type": "EXPLORATION",
            "primary_attribute": str(opening_area.get("primary_attribute") or "agility"),
            "target_difficulty": 14,
            "environment_penalty": 3,
            "unknown_risk": 5,
            "risk_warning": 0.7,
            "causal_chain": 0.85,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.8,
            "effects": {
                "success": {"discover_locations": [area_id], "resource_changes": {primary_resource: 3}, "knowledge_additions": [f"{enemy_id}_behavior"]},
                "partial_failure": {"resource_changes": {primary_resource: 1}, "knowledge_additions": [f"{enemy_id}_behavior"]},
            },
            "encounter_target_ids": [enemy_id],
            "requirements": {"location": area_id},
            "constraints": _base_action_constraints("field_exploration", "route_commitment", area_id, limited_to_daylight=True),
        },
        "camp_core": {"id": "camp_core", "target_difficulty": 0, "effects": {}},
    }
    locations = [
        {"id": "camp_core", "name": safe_base, "safe": True, "discovered": True, "travel_minutes_from_base": 0, "travel_stamina_from_base": 0, "extraction_minutes": 0, "extraction_stamina_cost": 0},
        {"id": area_id, "name": area_name, "description": area_description, "safe": False, "discovered": False, "travel_minutes_from_base": 30, "travel_stamina_from_base": 5, "extraction_minutes": 30, "extraction_stamina_cost": 5, "extraction_mental_cost": 0, "extraction_rule": deepcopy(area["extraction_rule"])},
    ]

    investigation = blueprint.get("investigation_site")
    if investigation is not None:
        investigation = _mapping(investigation, "investigation_site")
        investigation_id = _record_id(investigation, "investigation_site")
        investigation_name = _text(investigation, "name", "investigation_site")
        investigation_description = _text(investigation, "description", "investigation_site")
        locations.append({"id": investigation_id, "name": investigation_name, "description": investigation_description, "safe": False, "discovered": False, "travel_minutes_from_base": 45, "travel_stamina_from_base": 8, "extraction_minutes": 45, "extraction_stamina_cost": 8, "extraction_mental_cost": 1})
        action_targets[investigation_id] = {
            "id": investigation_id,
            "location_id": investigation_id,
            "action_type": "RESEARCH",
            "primary_attribute": str(investigation.get("primary_attribute") or "spirit"),
            "target_difficulty": 20,
            "environment_penalty": 5,
            "unknown_risk": 10,
            "risk_warning": 0.8,
            "causal_chain": 0.85,
            "avoidable": 0.7,
            "rule_consistency": 1.0,
            "player_responsibility": 0.8,
            "effects": {"success": {"knowledge_additions": [f"{investigation_id}_principle"], "resource_changes": {rare_resource: 2}}},
            "requirements": {"location": investigation_id},
            "constraints": _base_action_constraints("research_window", "research_focus", investigation_id, limited_to_daylight=False),
        }

    starting_npcs = []
    starting_relationships = []
    npc = blueprint.get("starting_npc")
    if npc is not None:
        npc = _mapping(npc, "starting_npc")
        npc_id = _record_id(npc, "starting_npc")
        npc_name = _text(npc, "name", "starting_npc")
        npc_goal = _text(npc, "goal", "starting_npc")
        npc_profession = str(npc.get("profession") or "").strip()
        if npc_profession and npc_profession not in professions:
            raise ValueError("starting_npc.profession 必须是本世界 professions 中由 LLM 定义的职业")
        npc_record = {
            "id": npc_id,
            "name": npc_name,
            "status": "alive",
            "location": "camp_core",
            "goal": npc_goal,
            "schedule": deepcopy(npc.get("schedule", {"清晨": "base_maintenance", "白天": "resource_search", "黄昏": "return_to_base", "夜晚": "rest"})),
            "autonomous_yield": {primary_resource: 1},
            "utility_profile": {"goal_fit": 70, "survival_benefit": 70, "resource_benefit": 55, "relationship_impact": 30, "value_alignment": 60, "risk": 25, "cost": 20},
        }
        if npc_profession:
            npc_record["profession"] = npc_profession
        starting_npcs.append(npc_record)
        starting_relationships.append({"npc_id": npc_id, "trust": 0, "respect": 0, "affection": 0, "fear": 0, "dependency": 0})
        action_targets[npc_id] = {
            "id": npc_id,
            "location_id": "camp_core",
            "action_type": "SOCIAL_INTERACTION",
            "is_npc": True,
            "primary_attribute": "spirit",
            "target_difficulty": 6,
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.9,
            "rule_consistency": 1.0,
            "player_responsibility": 0.7,
            "effects": {"success": {"relationship_changes": {npc_id: {"trust": 3, "respect": 1}}, "knowledge_additions": [f"{npc_id}_goal", f"{npc_id}_routine"]}},
            "requirements": {"location": "camp_core", "npc_available": npc_id},
            "constraints": {"system_tags": ["short_action"], "commitment_axis": "social_relationship", "commitment_value": npc_id},
        }

    modules = {}
    for index, module in enumerate(module_specs):
        module_id = _record_id(module, "base_modules")
        modules[module_id] = {
            "id": module_id,
            "name": _text(module, "name", "base_modules"),
            "description": _text(module, "description", "base_modules"),
            "space_cost": 1,
            "build_time": 60 + index * 30,
            "build_cost": {primary_resource: 1 + index, secondary_resource: 1},
            "maintenance": {primary_resource: 1},
            "effects": {"base_defense": index + 1},
        }

    starting_factions = []
    faction = blueprint.get("starting_faction")
    if faction is not None:
        faction = _mapping(faction, "starting_faction")
        faction_id = _record_id(faction, "starting_faction")
        starting_factions.append({
            "id": faction_id,
            "name": _text(faction, "name", "starting_faction"),
            "status": str(faction.get("status") or "neutral"),
            "location": "camp_core",
            "goal": _text(faction, "goal", "starting_faction"),
            "schedule": deepcopy(faction.get("schedule", {})),
            "treasury": {primary_resource: 3},
            "tax_rate": {},
            "influence": 10,
            "utility_profile": {"goal_fit": 75, "survival_benefit": 65, "resource_benefit": 60, "relationship_impact": 25, "value_alignment": 55, "risk": 20, "cost": 15},
        })

    for profession_id, profession in professions.items():
        exclusive_actions = profession.get("exclusive_actions", [])
        if not isinstance(exclusive_actions, list):
            raise ValueError(f"profession {profession_id}.exclusive_actions 必须是列表")
        for action_definition in exclusive_actions:
            if not isinstance(action_definition, Mapping):
                raise ValueError(f"profession {profession_id} 的专属行动必须是对象")
            action_key = str(action_definition.get("action_type", "")).strip()
            if not action_key:
                raise ValueError(f"profession {profession_id} 的专属行动缺少 action_type")
            target_id = f"profession:{profession_id}:{action_key}"
            completion_key = f"{target_id}:completed"
            action_targets[target_id] = {
                "id": target_id,
                "name": str(action_definition.get("name") or action_key),
                "location_id": str(action_definition.get("location_id") or "camp_core"),
                "action_type": "PROFESSION_ACTION",
                "target_difficulty": 15.0,
                "time_minutes": 30.0,
                "stamina_cost": 2.0,
                "mental_cost": 2.0,
                "primary_attribute": str(action_definition.get("primary_attribute") or "spirit"),
                "requirements": {
                    **(deepcopy(dict(action_definition.get("requirements", {}))) if isinstance(action_definition.get("requirements", {}), Mapping) else {}),
                    "profession": profession_id,
                    "location": str(action_definition.get("location_id") or "camp_core"),
                    "knowledge_absent": [completion_key],
                },
                "constraints": {"system_tags": ["short_action"]},
                "effects": {"success": {"knowledge_additions": [completion_key]}},
            }

    main_weapon = deepcopy(main_weapon)
    main_weapon.setdefault("attack", 18)
    main_weapon.setdefault("accuracy", 8)
    main_weapon.setdefault("durability", 12)
    main_weapon.setdefault("attack_type", "melee")
    main_weapon.setdefault("rarity", "G")
    starter_items = [deepcopy(dict(item)) for item in starter_items if isinstance(item, Mapping)]
    for item in starter_items:
        # 世界蓝图可省略通用品级；创建器补齐最低评级，避免有效的原创起始物
        # 品在存档校验阶段被拒绝，也不改变其名称、效果或世界语义。
        item.setdefault("rarity", "G")
    result = {
        "compiler_version": COMPILER_VERSION,
        "theme": str(theme),
        "profile": "llm_generated",
        "starting_location": "camp_core",
        "locations": locations,
        "enemies": [enemy_definition],
        "targets": {},
        "enemy_definitions": {enemy_id: enemy_definition},
        "encounter_entities": {},
        "combat_targets": {},
        "areas": {area_id: area},
        "farm_areas": {area_id: area},
        "build_catalog": modules,
        "modules": modules,
        "recipes": [{"id": recipe_id, "name": recipe_name, "description": str(recipe.get("description", "")).strip(), "cost": {primary_resource: 1}, "time_minutes": 30}],
        "disasters": [{"id": "disaster_001", "type": str(mechanics.get("disaster_type", "")).strip(), "cycle_days": int(mechanics.get("disaster_cycle_days", 0)), "warning": True}],
        "action_targets": action_targets,
        "professions": professions,
        "starting_inventory": {"resources": {resource: 2 for resource in resources}, "equipment": {"main_weapon": main_weapon}, "items": starter_items},
        "starting_npcs": starting_npcs,
        "starting_factions": starting_factions,
        "starting_relationships": starting_relationships,
        "creative_slots": deepcopy(dict(mechanics.get("creative_slots", {}))) if isinstance(mechanics.get("creative_slots", {}), Mapping) else {},
        "motifs": list(mechanics.get("motifs", [])) if isinstance(mechanics.get("motifs", []), list) else [],
        "taboo_domains": list(mechanics.get("taboo_domains", [])) if isinstance(mechanics.get("taboo_domains", []), list) else [],
    }
    if not result["disasters"][0]["type"] or result["disasters"][0]["cycle_days"] < 1:
        raise ValueError("灾难类型和灾难周期必须由世界包提供")
    return result
