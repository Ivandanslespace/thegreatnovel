"""把主题机制编译成可执行的世界注册表。

世界主题只负责选择一套机制档案；真正可玩的内容必须在创建存档时编译成
地点、敌人、区域、建造目录、行动目标和初始资源。运行时只读取这些注册表，
不会让 LLM 临时发明目标或数值。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Sequence


COMPILER_VERSION = "1.3"  # 类型合同定义移至 AGENTS.md；运行时不再硬编码合同

# ============================================================================
# 类型合同 (Genre Contract)
# ============================================================================
# 类型合同的唯一定义来源是 AGENTS.md「类型合同体系」章节。
# 运行时不在此处定义合同常量；genre_contract 数据由调用方
# （tools/create_save.py）根据玩家选择和 AGENTS.md 定义写入存档。


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

THEME_MOTIFS = {
    "废土列车": ["铁轨", "车厢", "车票", "站台", "广播", "燃料", "旧乘客", "行驶方向", "轨道", "列车"],
    "永夜冰川": ["冰层", "极光", "热洞", "霜轨", "白夜", "冻土", "冰晶", "暴风雪", "寒煤"],
    "巨兽背部": ["脊背", "寄生", "翻身", "锚桩", "苔田", "骨材", "索具", "巨兽"],
    "深渊裂隙": ["裂隙", "潮汐", "锚点", "回声", "污染", "深渊", "精神", "升降平台"],
    "generic": ["避难所", "资源", "危险", "探索", "信号"],
}

THEME_TABOO_DOMAINS = {
    "废土列车": ["身份", "邀请", "车厢所有权", "到站与下车", "记忆"],
    "永夜冰川": ["温度", "光源", "方向感", "声音"],
    "巨兽背部": ["平衡", "寄生", "巨兽意志", "坠落"],
    "深渊裂隙": ["凝视", "回声", "锚定", "深度"],
    "generic": ["安全", "信任", "方向"],
}

# ============================================================================
# 职业注册表 (Profession Registry)
# ============================================================================
# 职业档案定义了玩家在游戏中的专业角色；每个职业拥有专属能力、
# 独占行动、属性加成、起始技能和世界钩子。运行时通过 profession_registry
# 查找可玩职业列表并初始化玩家档案。
PROFESSION_REGISTRY = {
    "mechanic": {
        "id": "mechanic",
        "name": "缆车维修师",
        "category": "production",
        "description": "擅长维修载具和轨道系统",
        "capabilities": ["诊断机械故障", "紧急抢修", "改装载具模块"],
        "exclusive_actions": [
            {
                "action_type": "DIAGNOSE_FAILURE",
                "target_ids": ["load_bearing_cable", "engine_block"],
                "requirements": {"profession": "mechanic"},
                "time_minutes": 30,
                "stamina_cost": 2,
                "mental_cost": 3,
                "difficulty": 15,
            },
        ],
        "attribute_bonuses": {"agility": 2},
        "starting_skills": [{"id": "diagnosis_l1", "level": 1}],
        "consequence_radius": 0.7,
        "world_hooks": ["vehicle_breakdown_event", "region_transportation_interruption"],
        "autonomous_yield_profile": {
            "average_hours_worked": 180,
            "output_items": {"steel_parts": 2.5, "wire_rope": 1.2},
        },
        "comparative_weights": {
            "technical_efficiency": 0.3,
            "complexity_handled": 0.3,
            "resource_utilization": 0.2,
            "emergency_response": 0.2,
        },
    },
    "contract_signer": {
        "id": "contract_signer",
        "name": "契约签署员",
        "category": "social",
        "description": "负责处理资源交换协议与权益契约",
        "capabilities": ["起草交易契约", "验证权益条款", "仲裁利益冲突"],
        "exclusive_actions": [
            {
                "action_type": "DRAFT_CONTRACT",
                "target_ids": ["trade_agreement", "resource_rights"],
                "requirements": {"profession": "contract_signer"},
                "time_minutes": 60,
                "stamina_cost": 1,
                "mental_cost": 4,
                "difficulty": 18,
            },
        ],
        "attribute_bonuses": {"spirit": 2},
        "starting_skills": [{"id": "contract_l1", "level": 1}],
        "consequence_radius": 0.6,
        "world_hooks": ["trade_negotiation_event", "rights_dispute_scenario"],
        "autonomous_yield_profile": {
            "average_hours_worked": 150,
            "output_items": {"valid_contracts": 0.8, "trusted_partners": 0.3},
        },
        "comparative_weights": {
            "technical_efficiency": 0.1,
            "complexity_handled": 0.4,
            "resource_utilization": 0.2,
            "emergency_response": 0.1,
        },
    },
    "logger": {
        "id": "logger",
        "name": "日志记录者",
        "category": "exploration",
        "description": "收集环境数据并记录废土生态变迁",
        "capabilities": ["数据采样分析", "生态模式识别", "长期趋势追踪"],
        "exclusive_actions": [
            {
                "action_type": "HARVEST_DATA",
                "target_ids": ["environment_sample", "ecosystem_change"],
                "requirements": {"profession": "logger"},
                "time_minutes": 45,
                "stamina_cost": 1,
                "mental_cost": 2,
                "difficulty": 12,
            },
        ],
        "attribute_bonuses": {"spirit": 1, "agility": 1},
        "starting_skills": [{"id": "data_harvest_l1", "level": 1}],
        "consequence_radius": 0.5,
        "world_hooks": ["anomaly_detection_event", "long_term_pattern_emergence"],
        "autonomous_yield_profile": {
            "average_hours_worked": 200,
            "output_items": {"data_packets": 3.5, "pattern_notes": 0.5},
        },
        "comparative_weights": {
            "technical_efficiency": 0.2,
            "complexity_handled": 0.2,
            "resource_utilization": 0.3,
            "emergency_response": 0.1,
        },
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
    genre_contract: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """返回可直接放入 world.yaml 的完整生成包。
    
    Args:
        theme: 世界主题（废土列车、永夜冰川等）
        language: 游戏语言
        mechanics: 机制配置档案，可包含：
            - profile: 主题配置文件 ID
            - professions: 职业注册表字典（可选）
            - disaster_type: 灾难类型名称
            - genre_contract: 类型合同
        safe_base: 安全基地名称
        primary_resources: 基础资源列表
        genre_contract: 类型合同数据（来自 AGENTS.md 定义）。
            若为 None，回退到 solo_survival 最小默认值。
    """
    # 类型合同由调用方提供；未提供时回退到孤独生存最小默认值
    if genre_contract is None:
        genre_contract = {
            "id": "solo_survival",
            "name": "孤独生存",
            "collective_transmission": False,
            "public_system": {},
            "protagonist_contract": {"automatic_success": False},
        }
    
    # 提取 professions（如果传入）
    professions = mechanics.get("professions") if isinstance(mechanics.get("professions"), dict) else {}
    
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
        "definition_id": enemy_id,
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
        "status": "definition",
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
        "extraction_rule": {"return_to": "camp_core", "deadline_minutes": 120, "requires_discovered_location": True},
        "encounter_target_ids": [enemy_id],
    }
    action_constraints = {
        "system_tags": ["major_action", "requires_full_attention"],
        "exclusive_group": "field_exploration",
        "window_ids": ["白天", "黄昏"],
        "window_capacity": 1,
        "availability": {"allowed_periods": ["白天", "黄昏"]},
        "reservation": {"exclusive_group": "field_exploration", "window_id": "current_period", "capacity": 1},
        "commitment_axis": "route_commitment",
        "commitment_value": area_id,
    }
    action_targets = {
        area_id: {
            "id": area_id,
            "location_id": area_id,
            # 按全民系统投放标准调整难度
            "target_difficulty": 14,  # 从 25 降到 14（新手探索区间 10-16）
            "environment_penalty": 3,  # 从 5 降到 3
            "unknown_risk": 5,  # 从 12 大幅降到 5（减少新手死亡风险）
            "risk_warning": 0.7,  # 从 0.9 降低，给玩家更多试错空间
            "causal_chain": 0.85,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.8,
            "effects": {
                "success": {"discover_locations": [area_id], "resource_changes": {resource: 3}, "knowledge_additions": [f"{enemy_id}_behavior"]},
                "partial_failure": {"resource_changes": {resource: 1}, "knowledge_additions": [f"{enemy_id}_behavior"]},
            },
            "encounter_target_ids": [enemy_id],
            "constraints": action_constraints,
        },
        research_id: {
            "id": research_id,
            "location_id": research_id,
            "target_difficulty": 20,  # 从 30 降到 20（普通危险区间 18-24）
            "environment_penalty": 5,  # 从 8 降到 5
            "unknown_risk": 10,  # 从 15 降到 10
            "risk_warning": 0.8,
            "causal_chain": 0.85,
            "avoidable": 0.7,
            "rule_consistency": 1.0,
            "player_responsibility": 0.8,
            "effects": {"success": {"knowledge_additions": [f"{research_id}_principle"], "resource_changes": {rare_resource: 2}}},
            "constraints": {
                "system_tags": ["major_action", "requires_full_attention"],
                "exclusive_group": "research_window",
                "window_ids": ["白天", "黄昏"],
                "window_capacity": 1,
                "commitment_axis": "research_focus",
                "commitment_value": research_id,
            },
        },
        npc_id: {
            "id": npc_id,
            "location_id": "camp_core",
            # 按全民系统投放标准调整：日常交谈 4-8
            "target_difficulty": 6,  # 从 15 大幅降低
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.9,
            "rule_consistency": 1.0,
            "player_responsibility": 0.7,
            "effects": {"success": {"relationship_changes": {npc_id: {"trust": 3, "respect": 1}}, "knowledge_additions": [f"{npc_id}_goal", f"{npc_id}_routine"]}},
            "constraints": {"system_tags": ["short_action"], "commitment_axis": "social_relationship", "commitment_value": npc_id},
        },
        "camp_core": {"id": "camp_core", "target_difficulty": 0, "effects": {}},
    }
    action_targets[area_id]["primary_attribute"] = "agility"
    action_targets[research_id]["primary_attribute"] = "spirit"
    action_targets[npc_id]["primary_attribute"] = "spirit"
    action_targets[area_id]["action_type"] = "EXPLORATION"
    action_targets[research_id]["action_type"] = "RESEARCH"
    action_targets[npc_id]["action_type"] = "SOCIAL_INTERACTION"
    action_targets[npc_id]["is_npc"] = True
    for target_profile in action_targets.values():
        if target_profile.get("id") == area_id:
            target_profile["requirements"] = {"location": area_id}
        elif target_profile.get("id") == research_id:
            target_profile["requirements"] = {"location": research_id}
        elif target_profile.get("id") == npc_id:
            target_profile["requirements"] = {"location": "camp_core", "npc_available": npc_id}
        elif target_profile.get("id") != "camp_core":
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
        "equipment": {"main_weapon": {"id": "starter_weapon", "name": "初始武器", "rarity": "G", "attack": 18, "accuracy": 8, "ammo_resource": "ammo", "ammo_cost": 1, "durability": 12, "attack_type": "ranged"}},
        "items": [{"id": "field_kit", "name": "野外工具包", "rarity": "G", "quantity": 1}],
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
    result = {
        "compiler_version": COMPILER_VERSION,
        "theme": theme,
        "profile": profile,
        "starting_location": "camp_core",
        "locations": [
            {"id": "camp_core", "name": safe_base, "safe": True, "discovered": True, "travel_minutes_from_base": 0, "travel_stamina_from_base": 0, "extraction_minutes": 0, "extraction_stamina_cost": 0},
            {"id": area_id, "name": area_name, "safe": False, "discovered": False, "travel_minutes_from_base": 30, "travel_stamina_from_base": 5, "extraction_minutes": 30, "extraction_stamina_cost": 5, "extraction_mental_cost": 0, "extraction_rule": deepcopy(area["extraction_rule"])},
            {"id": research_id, "name": research_name, "safe": False, "discovered": False, "travel_minutes_from_base": 45, "travel_stamina_from_base": 8, "extraction_minutes": 45, "extraction_stamina_cost": 8, "extraction_mental_cost": 1},
        ],
        "enemies": [enemy],
        "targets": {},
        "enemy_definitions": {enemy_id: enemy},
        "encounter_entities": {},
        "combat_targets": {},
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

    # 添加 professions（如果已从 mechanics 传递）
    if professions:
        result["professions"] = professions
    else:
        # 默认使用 PROFESSION_REGISTRY（向后兼容）
        result["professions"] = {pid: pdef.copy() for pid, pdef in PROFESSION_REGISTRY.items()}

    # Creative slots for EventDirector
    if genre_contract and isinstance(genre_contract, dict) and genre_contract.get("creative_slots"):
        result["creative_slots"] = genre_contract["creative_slots"]
    else:
        result["creative_slots"] = {
            "signature_anomalies": 5,
            "living_resources": 3,
            "taboo_rules": 4,
            "macro_crises": 3,
            "forced_convergences": 2,
            "hidden_civilizations": 2,
            "system_irregularities": 3,
        }

    result["motifs"] = THEME_MOTIFS.get(profile, THEME_MOTIFS.get("generic", []))
    result["taboo_domains"] = THEME_TABOO_DOMAINS.get(profile, THEME_TABOO_DOMAINS.get("generic", []))

    return result
