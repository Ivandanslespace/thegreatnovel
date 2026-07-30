"""把主题机制编译成可执行的世界注册表。

世界主题只负责选择一套机制档案；真正可玩的内容必须在创建存档时编译成
地点、敌人、区域、建造目录、行动目标和初始资源。运行时只读取这些注册表，
不会让 LLM 临时发明目标或数值。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Sequence


PROFILE_CONTENT = {
    "永夜冰川": {
        "area": ("frost_moss_field", "霜苔荒野"),
        "research": ("heat_cave", "余烬热洞"),
        "enemy": ("ice_dead_lv1", "冰尸", "冰尸的骨节会在白夜风暴前提前结霜"),
        "npc": ("npc_rivet", "铆钉", "维护霜轨列车并寻找稳定燃料"),
        "modules": (("coal_stove", "寒煤炉", "把煤炭转化为基地热量"), ("crystal_storage", "寒晶储柜", "提高寒晶储存能力"), ("watch_car", "瞭望车厢", "提前发现冰尸和风暴")),
    },
    "巨兽背部": {
        "area": ("moss_field", "脊背苔田"),
        "research": ("anchor_tower", "锚桩塔"),
        "enemy": ("spine_parasite_lv1", "脊背寄生兽", "寄生兽会追随巨兽翻身前的震动"),
        "npc": ("npc_rivet", "铆钉", "维护背部索具并寻找安全锚点"),
        "modules": (("bone_workbench", "骨材工坊", "把骨材加工成工具"), ("anchor_shed", "锚桩仓", "储存并维护锚定材料"), ("lookout_rig", "脊背瞭望台", "扩大对巨兽动作的预警范围")),
    },
    "废土列车": {
        "area": ("scrap_yard", "废铁站场"),
        "research": ("signal_tower", "旧信号塔"),
        "enemy": ("wasteland_raider_lv1", "废土掠夺者", "掠夺者会追踪列车停靠时的热源"),
        "npc": ("npc_atai", "阿苔", "寻找净水并维护列车路线"),
        "modules": (("fuel_still", "燃油蒸馏器", "提高废燃料的回收效率"), ("water_tank", "净水罐", "储存和净化饮水"), ("scrap_bench", "废铁工台", "把废旧金属加工成装备")),
    },
    "深渊裂隙": {
        "area": ("rift_moss_layer", "裂隙苔层"),
        "research": ("anchor_tower", "稳定锚塔"),
        "enemy": ("abyssal_stalker_lv1", "深渊潜行兽", "潜行兽会在裂隙潮汐前靠近锚点"),
        "npc": ("npc_suture", "缝线", "维护升降平台并记录精神污染"),
        "modules": (("purifier", "净化台", "消耗净化药剂降低污染"), ("anchor_shed", "锚材仓", "储存锚定材料"), ("echo_lab", "回声实验室", "研究裂隙回声")),
    },
    "generic": {
        "area": ("outer_field", "外缘荒地"),
        "research": ("signal_ruin", "信号废墟"),
        "enemy": ("unknown_creature_lv1", "未知生物", "未知生物会在环境变化前离开巢穴"),
        "npc": ("npc_scout", "巡查员", "维护避难所并寻找可用资源"),
        "modules": (("repair_bench", "简易工台", "加工工具材料"), ("storage_shed", "储物棚", "扩大资源储存"), ("watch_post", "瞭望台", "提前发现环境灾害")),
    },
}


def _english(language: str) -> bool:
    return str(language or "").strip().lower() in {"en", "english", "英文", "英语"}


def compile_world_bundle(
    theme: str,
    language: str,
    mechanics: Mapping[str, Any],
    safe_base: str,
    primary_resources: Sequence[str],
) -> Dict[str, Any]:
    """返回可直接放入 world.yaml 的完整生成包。"""
    profile = str(mechanics.get("profile", "generic"))
    content = deepcopy(PROFILE_CONTENT.get(profile, PROFILE_CONTENT["generic"]))
    area_id, area_name = content["area"]
    research_id, research_name = content["research"]
    enemy_id, enemy_name, enemy_hint = content["enemy"]
    npc_id, npc_name, npc_goal = content["npc"]
    resources = [str(item) for item in primary_resources if str(item).strip()]
    resource = resources[0] if resources else "核心能源"
    secondary_resource = resources[1] if len(resources) > 1 else resource
    rare_resource = resources[2] if len(resources) > 2 else secondary_resource
    english = _english(language)
    if english:
        area_name = {"霜苔荒野": "Frostmoss Field", "脊背苔田": "Spine Moss Field", "废铁站场": "Scrap Yard", "裂隙苔层": "Rift Moss Layer", "外缘荒地": "Outer Field"}.get(area_name, area_name)
        research_name = {"余烬热洞": "Ember Heat Cave", "锚桩塔": "Anchor Tower", "旧信号塔": "Old Signal Tower", "稳定锚塔": "Stabilizer Tower", "信号废墟": "Signal Ruin"}.get(research_name, research_name)

    enemy = {
        "id": enemy_id,
        "name": enemy_name,
        "level": 1,
        "quality": "普通",
        "hp": 30,
        "max_hp": 30,
        "attack": 6,
        "accuracy": 5,
        "defense_skill": 2,
        "armor": 1,
        "attributes": {"strength": 4, "constitution": 3, "agility": 4, "spirit": 2},
        "drops": {resource: 2, secondary_resource: 1},
        "knowledge_hint": enemy_hint,
        "status": "alive",
        "location_id": area_id,
    }
    area = {
        "id": area_id,
        "name": area_name,
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
        "enemy_groups": [{"level": 1, "quality": "普通", "weight": 1, "drops": deepcopy(enemy["drops"])}],
        "farmability_components": {"combat_advantage": 50, "enemy_information": 35, "kill_stability": 55, "sustainability": 50, "route_familiarity": 25, "extraction_ability": 70, "unknown_danger_penalty": 20, "noise_exposure": 35, "fatigue_risk": 35, "injury_risk": 25, "area_alertness": 25, "daylight_change": 15, "monster_adaptation": 10},
        "extraction_rule": {"return_to": "camp_core", "deadline_minutes": 120},
        "encounter_target_ids": [enemy_id],
    }
    action_targets = {
        area_id: {
            "id": area_id,
            "target_difficulty": 25,
            "environment_penalty": 5,
            "unknown_risk": 12,
            "risk_warning": 0.9,
            "causal_chain": 0.9,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.8,
            "effects": {
                "success": {"discover_locations": [area_id], "resource_changes": {resource: 2}, "knowledge_additions": [f"{enemy_id}_behavior"]},
                "partial_failure": {"knowledge_additions": [f"{enemy_id}_behavior"]},
            },
            "encounter_target_ids": [enemy_id],
        },
        research_id: {
            "id": research_id,
            "target_difficulty": 30,
            "environment_penalty": 8,
            "unknown_risk": 15,
            "risk_warning": 0.9,
            "causal_chain": 0.9,
            "avoidable": 0.7,
            "rule_consistency": 1.0,
            "player_responsibility": 0.8,
            "effects": {"success": {"knowledge_additions": [f"{research_id}_principle"], "resource_changes": {rare_resource: 1}}},
        },
        npc_id: {
            "id": npc_id,
            "target_difficulty": 15,
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.7,
            "effects": {"success": {"relationship_changes": {npc_id: {"trust": 3, "respect": 1}}, "knowledge_additions": [f"{npc_id}_goal"]}},
        },
        "camp_core": {"id": "camp_core", "target_difficulty": 0, "effects": {}},
    }
    action_targets[area_id]["primary_attribute"] = "agility"
    action_targets[research_id]["primary_attribute"] = "spirit"
    action_targets[npc_id]["primary_attribute"] = "spirit"
    for target_profile in action_targets.values():
        if target_profile.get("id") != "camp_core":
            target_profile["requirements"] = {"location": "camp_core"}
    modules = {}
    for index, (module_id, module_name, description) in enumerate(content["modules"]):
        modules[module_id] = {
            "id": module_id,
            "name": module_name,
            "description": description,
            "space_cost": 1,
            "build_time": 60 + index * 30,
            "build_cost": {"wood": 1 + index, resource: 1},
            "maintenance": {resource: 1},
            "effects": {"base_defense": index + 1},
        }
    starting_inventory = {
        "resources": {**{resource_id: 2 for resource_id in resources}, "wood": 5, "ammo": 8},
        "equipment": {"main_weapon": {"id": "starter_weapon", "name": "初始武器", "attack": 18, "accuracy": 8, "ammo_resource": "ammo", "ammo_cost": 1, "durability": 12, "attack_type": "ranged"}},
        "items": [{"id": "field_kit", "name": "野外工具包", "quantity": 1}],
    }
    starting_npc = {
        "id": npc_id,
        "name": npc_name,
        "status": "alive",
        "location": "camp_core",
        "goal": npc_goal,
        "schedule": {"清晨": "base_maintenance", "白天": "resource_search", "黄昏": "return_to_base", "夜晚": "rest"},
        "autonomous_yield": {resource: 1},
        "utility_profile": {"goal_fit": 70, "survival_benefit": 70, "resource_benefit": 55, "relationship_impact": 30, "value_alignment": 60, "risk": 25, "cost": 20},
    }
    starting_faction = {
        "id": f"faction_{profile}_wayfarers",
        "name": "边缘行旅会" if not english else "Edge Wayfarers",
        "status": "neutral",
        "location": "camp_core",
        "goal": "在灾难周期中维持交换路线",
        "schedule": {"清晨": "route_planning", "白天": "trade_patrol", "黄昏": "collect_tax", "夜晚": "rest"},
        "treasury": {resource: 3},
        "tax_rate": {resource: 1},
        "influence": 10,
        "utility_profile": {"goal_fit": 75, "survival_benefit": 65, "resource_benefit": 60, "relationship_impact": 25, "value_alignment": 55, "risk": 20, "cost": 15},
    }
    disaster_type = mechanics.get("disaster_type", "大型环境灾难")
    return {
        "compiler_version": "1.0",
        "theme": theme,
        "profile": profile,
        "starting_location": "camp_core",
        "locations": [
            {"id": "camp_core", "name": safe_base, "safe": True, "discovered": True},
            {"id": area_id, "name": area_name, "safe": False, "discovered": False},
            {"id": research_id, "name": research_name, "safe": False, "discovered": False},
        ],
        "enemies": [enemy],
        "targets": {enemy_id: enemy},
        "combat_targets": {enemy_id: enemy},
        "areas": {area_id: area},
        "farm_areas": {area_id: area},
        "build_catalog": modules,
        "modules": modules,
        "recipes": [{"id": "field_repair", "name": "现场修补", "cost": {"wood": 1, resource: 1}, "time_minutes": 30}],
        "disasters": [{"id": "disaster_001", "type": disaster_type, "cycle_days": 7, "warning": True}],
        "action_targets": action_targets,
        "starting_inventory": starting_inventory,
        "starting_npcs": [starting_npc],
        "starting_factions": [starting_faction],
        "starting_relationships": [{"npc_id": npc_id, "trust": 0, "respect": 0, "affection": 0, "fear": 0, "dependency": 0}],
    }
