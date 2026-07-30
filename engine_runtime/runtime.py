"""面向新游戏的最小可运行引擎入口。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from uuid import uuid4

from .calculators import (
    ActionContext,
    apply_action_dilution,
    calculate_base_defense,
    calculate_base_maintenance,
    calculate_build,
    calculate_combat,
    calculate_combinability,
    calculate_experience,
    calculate_narrative_metrics,
    check_skill_use,
    resolve_action,
    simulate_batch_action,
    skill_cost,
)
from .events import standard_event
from .protocol import (
    canonicalize_attribute_allocations,
    derive_action_costs,
    derive_risk_modifiers,
    validate_host_action,
)
from .state import GameState, load_game_state


class GameEngine:
    def __init__(self, state: GameState):
        self.state = state

    def _build_action_context(self, action: Mapping[str, Any], costs: Mapping[str, float]) -> ActionContext:
        risk = derive_risk_modifiers(action)
        world_targets = self.state.data.get("world", {}).get("action_targets", {}) if isinstance(self.state.data.get("world", {}).get("action_targets", {}), Mapping) else {}
        target_profile = self._registry_lookup(world_targets, action.get("target")) or {}
        if not isinstance(target_profile, Mapping):
            target_profile = {}
        runtime_context = self.state.meta.get("runtime_context", {}) if isinstance(self.state.meta.get("runtime_context", {}), Mapping) else {}
        seed = f"{self.state.meta.get('rng_seed', self.state.meta.get('world_name', 'world'))}|turn:{self.state.current_turn + 1}|action:{action.get('action_id')}"
        attributes = self.state.player.get("attributes", {}) if isinstance(self.state.player.get("attributes", {}), Mapping) else {}
        primary_attribute = str(target_profile.get("primary_attribute", "spirit"))
        defaults = {
            "seed": seed,
            "action_id": str(action.get("action_id") or f"turn-{self.state.current_turn + 1}"),
            "target_difficulty": float(target_profile.get("target_difficulty", costs.get("target_difficulty", 20.0))),
            "preparation": float(target_profile.get("preparation", 0.0)) + risk["preparation"],
            "intelligence": float(runtime_context.get("intelligence", 0.0)),
            "teammate_assistance": float(runtime_context.get("teammate_assistance", 0.0)),
            "environment_advantage": float(runtime_context.get("environment_advantage", 0.0)),
            "environment_penalty": float(target_profile.get("environment_penalty", runtime_context.get("environment_penalty", 0.0))),
            "time_pressure": float(target_profile.get("time_pressure", 0.0)) + risk["time_pressure"],
            "unknown_risk": max(0.0, float(target_profile.get("unknown_risk", 0.0)) + risk["unknown_risk"]),
            "risk_warning": float(target_profile.get("risk_warning", 1.0 if target_profile else 0.0)),
            "causal_chain": float(target_profile.get("causal_chain", 1.0 if target_profile else 0.0)),
            "avoidable": float(target_profile.get("avoidable", 0.0)),
            "rule_consistency": float(target_profile.get("rule_consistency", 1.0 if target_profile else 0.0)),
            "player_responsibility": float(target_profile.get("player_responsibility", 0.0)),
            "difficulty_mode": str(self.state.meta.get("difficulty", "标准")),
        }
        for attribute in ("strength", "constitution", "agility", "spirit"):
            defaults[attribute] = float(attributes.get(attribute, 5.0))
        defaults["ability_match"] = defaults.get(primary_attribute, 5.0) * 2.0
        talent_effects = self.state.player.get("talent_effects", {}) if isinstance(self.state.player.get("talent_effects", {}), Mapping) else {}
        action_modifiers = talent_effects.get("action_modifiers", {}) if isinstance(talent_effects.get("action_modifiers", {}), Mapping) else {}
        modifier = action_modifiers.get(str(action.get("type")), {}) if isinstance(action_modifiers.get(str(action.get("type")), {}), Mapping) else {}
        for key in ("intelligence", "teammate_assistance", "environment_advantage", "preparation", "environment_penalty", "time_pressure", "unknown_risk"):
            if key in modifier:
                defaults[key] += float(modifier[key])
        values = {**defaults, "primary_attribute": primary_attribute}
        if action.get("skill_id"):
            skill = self._find_skill(action)
            values["skill_bonus"] = float(skill.get("level", 1)) * 2.0 if skill else 0.0
        # Apply attribute bonuses from player's profession (if any)
        current_profession_id = self.state.player.get("profession")
        if current_profession_id:
            # Check if profession exists in world bundle
            world_professions = self.state.data.get("world", {}).get("professions", {})
            if current_profession_id in world_professions:
                profession_def = world_professions[current_profession_id]
                attribute_bonuses = profession_def.get("attribute_bonuses", {})
                if isinstance(attribute_bonuses, Mapping):
                    for attr, bonus in attribute_bonuses.items():
                        if attr in ("strength", "constitution", "agility", "spirit"):
                            # Cap at half bonus for balance
                            values[attr] = float(values.get(attr, 0.0)) + bonus * 0.5
        
        # Apply profession-based action modifiers for specific actions
        action_type = str(action.get("type") or target_profile.get("action_type") or "")
        if current_profession_id == "mechanic" and action_type == "DIAGNOSE_FAILURE":
            values["ability_match"] += 5
            values["preparation"] += 3
        elif current_profession_id == "contract_signer" and action_type == "DRAFT_CONTRACT":
            values["intelligence"] += 5
            values["preparation"] += 2
        elif current_profession_id == "logger" and action_type == "HARVEST_DATA":
            values["ability_match"] += 2
        
        allowed = ActionContext.__dataclass_fields__
        return ActionContext(**{key: values[key] for key in allowed if key in values})

    def _find_skill(self, action: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        if isinstance(action.get("skill"), Mapping):
            return action["skill"]
        skill_id = action.get("skill_id")
        if not skill_id:
            return None
        for skill in self.state.player.get("skills", []) if isinstance(self.state.player.get("skills"), list) else []:
            if isinstance(skill, Mapping) and skill.get("id") == skill_id:
                return skill
        return None

    def _has_item(self, item_id: str) -> bool:
        inventory = self.state.inventory
        for item in inventory.get("items", []) if isinstance(inventory.get("items"), list) else []:
            if isinstance(item, Mapping) and (item.get("id") == item_id or item.get("name") == item_id) and float(item.get("quantity", 1)) > 0:
                return True
        for item in inventory.get("equipment", {}).values() if isinstance(inventory.get("equipment"), Mapping) else []:
            if isinstance(item, Mapping) and (item.get("id") == item_id or item.get("name") == item_id):
                return True
        return False

    def _active_encounter_allows(self, target_id: Any = None, location_id: Any = None) -> bool:
        encounter = self._current_active_encounter()
        if encounter is None:
            return False
        participants = set(encounter.get("participants", [])) | set(encounter.get("target_ids", []))
        if target_id is not None and target_id in participants:
            return True
        return location_id is not None and encounter.get("location_id") == location_id

    def _current_active_encounter(self) -> Optional[Mapping[str, Any]]:
        encounters = self.state.meta.get("active_encounters", [])
        current_encounter_id = self.state.meta.get("current_encounter_id")
        if not isinstance(encounters, list) or not current_encounter_id:
            return None
        current_location = self._current_location()
        for encounter in encounters:
            if not isinstance(encounter, Mapping):
                continue
            if encounter.get("id") != current_encounter_id or encounter.get("status", "active") != "active":
                continue
            if str(encounter.get("location_id")) != str(current_location):
                continue
            return encounter
        return None

    def _timeline_minutes(self) -> float:
        period_starts = {"清晨": 0.0, "白天": 120.0, "黄昏": 480.0, "夜晚": 600.0}
        elapsed = self.state.meta.get("day_elapsed_minutes")
        if elapsed is None:
            elapsed = period_starts.get(str(self.state.meta.get("time_of_day", "清晨")), 0.0)
        try:
            return max(0.0, (float(self.state.meta.get("game_day", 1)) - 1.0) * 720.0 + float(elapsed))
        except (TypeError, ValueError):
            return max(0.0, (float(self.state.meta.get("game_day", 1)) - 1.0) * 720.0)

    def _extraction_rule(self, location_id: Any) -> Mapping[str, Any]:
        profile = self._location_profile(location_id) or {}
        rule = profile.get("extraction_rule", {}) if isinstance(profile, Mapping) else {}
        return rule if isinstance(rule, Mapping) else {}

    def _extraction_errors(self, encounter: Optional[Mapping[str, Any]] = None) -> list[str]:
        current_location = self._current_location()
        encounter_rule = encounter.get("extraction_rule", {}) if isinstance(encounter, Mapping) else {}
        rule = encounter_rule if isinstance(encounter_rule, Mapping) and encounter_rule else self._extraction_rule(current_location)
        if not self._location_profile(current_location):
            return [f"当前地点没有注册撤离路线：{current_location}"]
        deadline_at = encounter.get("extraction_deadline_at_minutes") if isinstance(encounter, Mapping) else None
        if deadline_at is not None:
            extraction_finish = self._timeline_minutes() + float(self._derive_action_costs({"type": "EXTRACT", "action_id": "extraction-check"}).get("time_minutes", 0.0))
            if self._timeline_minutes() > float(deadline_at):
                return ["撤离截止时间已过，当前遭遇不能安全撤离"]
            if extraction_finish > float(deadline_at):
                return ["剩余时间不足以在撤离截止前返回基地"]
        allowed_periods = rule.get("allowed_periods", rule.get("open_periods", []))
        if isinstance(allowed_periods, list) and allowed_periods and str(self.state.meta.get("time_of_day", "清晨")) not in {str(item) for item in allowed_periods}:
            return [f"当前时段不在撤离窗口：允许 {', '.join(str(item) for item in allowed_periods)}"]
        required_item = rule.get("required_item", rule.get("extraction_key"))
        if required_item and not self._has_item(str(required_item)):
            return [f"缺少撤离所需物品：{required_item}"]
        if rule.get("requires_discovered_location"):
            discovered = self.state.player.get("discovered_locations", [])
            if current_location not in discovered:
                return ["尚未发现当前地点的撤离点"]
        return []

    def _reaction_errors(self, action: Mapping[str, Any]) -> list[str]:
        pending = self.state.meta.get("pending_reaction", {})
        if not isinstance(pending, Mapping) or not pending.get("id"):
            return ["当前没有待处理的即时危险"]
        allowed_types = pending.get("allowed_action_types", ["REACTION"])
        if isinstance(allowed_types, list) and "REACTION" not in {str(item) for item in allowed_types}:
            return ["当前即时危险不允许反应行动"]
        parameters = action.get("parameters", {}) if isinstance(action.get("parameters", {}), Mapping) else {}
        if not action.get("goal") and not parameters.get("objective"):
            return ["反应行动必须说明要处理的即时危险"]
        return []

    def _target_presence_errors(self, action: Mapping[str, Any]) -> list[str]:
        action_type = str(action.get("type"))
        current_location = self._current_location()
        base_location = self._base_location()
        movement_types = {"TRAVEL", "ENTER_LOCATION", "RETURN_TO_BASE", "EXTRACT", "LEAVE_ENCOUNTER"}
        active_encounter = self._current_active_encounter()
        # 遭遇一旦建立，玩家必须在同一条因果链内战斗、撤离或离开。允许
        # WAIT/探索/社交会令遭遇在无代价下过期，既破坏风险也会累积孤儿遭遇。
        if active_encounter and action_type not in {"COMBAT", "EXTRACT", "LEAVE_ENCOUNTER", "REACTION"}:
            return ["当前遭遇未处理：只能战斗、撤离或离开遭遇"]
        if action_type == "WAIT":
            return []
        if action_type == "REACTION":
            return self._reaction_errors(action)
        target_profile = self._action_target_profile(action)
        target_constraints = target_profile.get("constraints", {}) if isinstance(target_profile, Mapping) else {}
        availability = target_constraints.get("availability", {}) if isinstance(target_constraints, Mapping) else {}
        allowed_periods = availability.get("allowed_periods", target_constraints.get("allowed_periods", [])) if isinstance(availability, Mapping) else []
        if action_type not in movement_types and not allowed_periods:
            allowed_periods = self._system_action_constraints(action).get("allowed_periods", [])
        if action_type not in movement_types and isinstance(allowed_periods, list) and allowed_periods and str(self.state.meta.get("time_of_day", "清晨")) not in {str(item) for item in allowed_periods}:
            return [f"当前时段不可执行该行动：允许 {', '.join(str(item) for item in allowed_periods)}"]
        if action_type in movement_types:
            target = self._movement_target(action)
            if action_type in {"TRAVEL", "ENTER_LOCATION"}:
                if not target:
                    return ["移动行动必须指定目标地点"]
                if self._location_profile(target) is None:
                    return [f"目标地点未注册：{target}"]
                if str(target) == str(current_location):
                    return ["目标地点已经是当前位置，无需重复移动"]
                if self.state.meta.get("current_encounter_id"):
                    return ["当前仍在遭遇中：必须先使用 EXTRACT 或 LEAVE_ENCOUNTER"]
            elif action_type == "RETURN_TO_BASE":
                if action.get("target") and str(action.get("target")) != str(base_location):
                    return [f"RETURN_TO_BASE 只能返回基地：{base_location}"]
                if str(current_location) == str(base_location):
                    return ["当前已经在基地"]
                if self.state.meta.get("current_encounter_id"):
                    return ["当前仍在遭遇中：必须使用 EXTRACT 返回基地"]
            elif action_type == "EXTRACT":
                if str(current_location) == str(base_location):
                    return ["当前已经在基地，不需要撤离"]
                if action.get("target") and str(action.get("target")) != str(base_location):
                    return [f"EXTRACT 只能返回基地：{base_location}"]
                extraction_errors = self._extraction_errors(self._current_active_encounter())
                if extraction_errors:
                    return extraction_errors
            elif action_type == "LEAVE_ENCOUNTER":
                if not self._active_encounter_allows(location_id=current_location):
                    return ["当前没有可离开的活动遭遇"]
        if action_type == "COMBAT":
            target = self._registry_lookup(self.state.data.get("world", {}).get("encounter_entities"), action.get("target"))
            target = target or self._registry_lookup(self.state.data.get("world", {}).get("targets"), action.get("target"))
            target = target or self._registry_lookup(self.state.data.get("world", {}).get("combat_targets"), action.get("target"))
            target = target or self._registry_lookup(self.state.data.get("npcs", []), action.get("target"))
            if target and target.get("status") == "definition":
                return ["目标只是怪物类型定义，必须先进入一个具体遭遇"]
            if target and target.get("status") in {"dead", "destroyed"}:
                return ["目标已经死亡或不可战斗"]
            if not self._active_encounter_allows(action.get("target")):
                return ["没有与该目标绑定的当前遭遇：必须先进入对应地点并加入遭遇"]
        if action_type == "BATCH_ACTION":
            area = self._registry_lookup(self.state.data.get("world", {}).get("areas"), action.get("target"))
            area = area or self._registry_lookup(self.state.data.get("world", {}).get("farm_areas"), action.get("target"))
            location_id = area.get("location_id") if isinstance(area, Mapping) else None
            if location_id and self.state.meta.get("current_location") != location_id:
                return [f"刷怪区域不在当前地点：需要先进入 {location_id}"]
        if action_type == "EXPLORATION":
            profile = self._action_target_profile(action)
            if not profile:
                return [f"探索地点未注册：{action.get('target')}"]
            location_id = profile.get("location_id", action.get("target"))
            if location_id and str(location_id) != self._current_location():
                return [f"探索地点不在当前地点：需要先使用 TRAVEL/ENTER_LOCATION 进入 {location_id}"]
        if action_type in {"REST", "BUILD", "BASE_MANAGEMENT"}:
            if str(current_location) != str(base_location):
                return [f"{action_type} 只能在基地执行：当前地点为 {current_location}，基地为 {base_location}"]
            if self.state.meta.get("current_encounter_id"):
                return [f"当前仍在遭遇中，不能执行 {action_type}"]
        if action_type == "REST" and action.get("target") and str(action.get("target")) != str(current_location):
            if str(action.get("target")) != str(base_location):
                return [f"休息目标必须是当前位置或基地：{base_location}"]
        return []

    def _check_requirements(self, action: Mapping[str, Any]) -> list[str]:
        errors: list[str] = []
        action_type = str(action.get("type"))
        if (self.state.meta.get("campaign_status") == "ended" or self.state.player.get("status") == "dead") and action_type not in {"ENDING", "RESTART", "CHECKPOINT", "LEGACY_CREATE"}:
            errors.append("本局已经结束，只允许查看结局、重开、检查点或创建传承角色")
        pending = self.state.player.get("pending_decision")
        if pending and action_type != "TALENT_CHOICE":
            errors.append("必须先完成升级三选一")
        errors.extend(self._target_presence_errors(action))
        # 这些社会/经济动作需要世界注册表提供对手、成本和状态效果。协议层
        # 只校验意图形状，不能把“语法通过”误当成机制已经实现；否则会出现
        # 消耗时间却不改变任何真实状态的幽灵行动。
        registered_domain_actions = {
            "TRADE", "TEAM_FORMATION", "MARKET_ORDER", "VEHICLE_UPGRADE", "REGIONAL_EVENT_ENTRY",
        }
        if action_type in registered_domain_actions:
            profile = self._action_target_profile(action)
            effects = profile.get("effects", {}) if isinstance(profile, Mapping) else {}
            has_effect = isinstance(effects, Mapping) and any(
                isinstance(effects.get(branch), Mapping) and bool(effects.get(branch))
                for branch in ("success", "partial_failure", "failure")
            )
            if not profile:
                errors.append(f"{action_type} 尚未在当前世界注册目标")
            elif not has_effect:
                errors.append(f"{action_type} 的注册目标没有可提交的状态效果")
        registry_requirements = self._action_target_profile(action).get("requirements", {})
        requirements = dict(registry_requirements) if isinstance(registry_requirements, Mapping) else {}
        supplied_requirements = action.get("requirements", {}) if isinstance(action.get("requirements"), Mapping) else {}
        for key, value in supplied_requirements.items():
            requirements.setdefault(key, value)
        required_location = requirements.get("location")
        current_location = self._current_location()
        registry_location_only = "location" in supplied_requirements
        if action_type in {"TRAVEL", "ENTER_LOCATION", "RETURN_TO_BASE", "EXTRACT", "LEAVE_ENCOUNTER"} and not registry_location_only:
            required_location = None
        if required_location and required_location != current_location and (registry_location_only or action_type != "BATCH_ACTION"):
            errors.append(f"地点不符：需要 {required_location}")
        for item in requirements.get("items", []) if isinstance(requirements.get("items"), list) else []:
            item_id = item.get("id", item.get("name")) if isinstance(item, Mapping) else str(item)
            if item_id and not self._has_item(str(item_id)):
                errors.append(f"缺少物品：{item_id}")
        required_level = requirements.get("level")
        if required_level is not None and int(self.state.player.get("level", 1)) < int(required_level):
            errors.append("等级不足")
        required_skill = requirements.get("skill")
        if required_skill and not any(skill.get("id") == required_skill for skill in self.state.player.get("skills", []) if isinstance(skill, Mapping)):
            errors.append(f"未掌握技能：{required_skill}")
        npc_id = requirements.get("npc_available")
        if npc_id:
            npc = next((item for item in self.state.data.get("npcs", []) if isinstance(item, Mapping) and item.get("id") == npc_id), None)
            if not npc or npc.get("status", "alive") != "alive" or npc.get("location") != current_location:
                errors.append(f"NPC不可用：{npc_id}")
            else:
                schedule = npc.get("schedule", {}) if isinstance(npc.get("schedule", {}), Mapping) else {}
                scheduled_action = str(schedule.get(self.state.meta.get("time_of_day", "清晨"), "")).lower()
                if scheduled_action in {"rest", "休息", "unavailable", "不可用"}:
                    errors.append(f"NPC当前时段不可用：{npc_id}")
        knowledge = requirements.get("knowledge")
        if knowledge:
            known = self.state.player.get("knowledge", [])
            required_knowledge = knowledge if isinstance(knowledge, list) else [knowledge]
            for item in required_knowledge:
                if item not in known:
                    errors.append(f"未知信息：{item}")
        knowledge_absent = requirements.get("knowledge_absent", [])
        if knowledge_absent:
            known = self.state.player.get("knowledge", [])
            blocked = knowledge_absent if isinstance(knowledge_absent, list) else [knowledge_absent]
            for item in blocked:
                if item in known:
                    errors.append(f"该行动已经完成：{item}")
        profession_ok, profession_error = self._check_profession_requirement(
            self._action_target_profile(action), self.state
        )
        if not profession_ok:
            errors.append(profession_error)
        skill = self._find_skill(action)
        if skill:
            errors.extend(check_skill_use(skill, self.state.player, self.state.inventory))
        elif action.get("skill_id"):
            errors.append(f"未掌握技能：{action['skill_id']}")
        return errors

    def _check_profession_requirement(self, action_profile: Mapping[str, Any], state: GameState) -> Tuple[bool, str]:
        """Check if player satisfies profession requirement for this action."""
        requirements = action_profile.get("requirements", {})
        if not isinstance(requirements, Mapping):
            return True, ""
        
        required_profession = requirements.get("profession")
        if not required_profession:
            return True, ""
        
        player_profession = state.player.get("profession")
        if player_profession == required_profession:
            return True, ""
        
        # Check if player has access via skills
        player_skills = state.player.get("skills", [])
        for skill in player_skills:
            if isinstance(skill, Mapping) and skill.get("id") == f"{required_profession}_training":
                return True, ""
        
        error_msg = f"职业不符：执行该行动需要{required_profession}职业或相应技能，当前未拥有"
        return False, error_msg

    def _action_target_profile(self, action: Mapping[str, Any]) -> Mapping[str, Any]:
        registry = self.state.data.get("world", {}).get("action_targets", {})
        return self._registry_lookup(registry, action.get("target")) or {}

    def _base_location(self) -> str:
        world = self.state.data.get("world", {}) if isinstance(self.state.data.get("world", {}), Mapping) else {}
        bundle = world.get("generation_bundle", {}) if isinstance(world.get("generation_bundle", {}), Mapping) else {}
        base = self.state.data.get("base", {}) if isinstance(self.state.data.get("base", {}), Mapping) else {}
        return str(
            self.state.meta.get("base_location")
            or base.get("location_id")
            or world.get("starting_location")
            or bundle.get("starting_location")
            or "camp_core"
        )

    def _current_location(self) -> str:
        return str(self.state.meta.get("current_location") or self._base_location())

    def _location_profile(self, location_id: Any) -> Optional[Mapping[str, Any]]:
        if not location_id:
            return None
        world = self.state.data.get("world", {}) if isinstance(self.state.data.get("world", {}), Mapping) else {}
        return self._registry_lookup(world.get("locations", []), location_id)

    def _location_name(self, location_id: Any) -> str:
        profile = self._location_profile(location_id)
        return str(profile.get("name", location_id)) if isinstance(profile, Mapping) else str(location_id)

    def _movement_target(self, action: Mapping[str, Any]) -> str:
        action_type = str(action.get("type"))
        if action_type in {"RETURN_TO_BASE", "EXTRACT"}:
            return str(action.get("target") or self._base_location())
        if action_type == "LEAVE_ENCOUNTER":
            return self._current_location()
        return str(action.get("target") or "")

    def _derive_action_costs(self, action: Mapping[str, Any], skill: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
        costs = derive_action_costs(action, skill)
        action_type = str(action.get("type"))
        profile = self._action_target_profile(action)
        if isinstance(profile, Mapping):
            for field in ("time_minutes", "stamina_cost", "mental_cost", "target_difficulty"):
                if profile.get(field) is not None:
                    costs[field] = float(profile[field])
        if action_type == "WAIT":
            parameters = action.get("parameters", {}) if isinstance(action.get("parameters", {}), Mapping) else {}
            wait_minutes = max(5.0, min(720.0, float(parameters.get("wait_minutes", 30.0))))
            costs["time_minutes"] = wait_minutes
            costs["stamina_cost"] = 0.0
            costs["mental_cost"] = 0.0
            return costs
        if action_type not in {"TRAVEL", "ENTER_LOCATION", "RETURN_TO_BASE", "EXTRACT"}:
            return costs

        current = self._current_location()
        base = self._base_location()
        target = self._movement_target(action)
        if action_type in {"TRAVEL", "ENTER_LOCATION"}:
            route = self._location_profile(target) or self._location_profile(current) or {}
            minutes_key = "travel_minutes_from_base" if current == base else "travel_minutes"
            stamina_key = "travel_stamina_from_base" if current == base else "travel_stamina_cost"
            mental_key = "travel_mental_from_base" if current == base else "travel_mental_cost"
        elif action_type == "EXTRACT":
            route = self._location_profile(current) or {}
            minutes_key = "extraction_minutes"
            stamina_key = "extraction_stamina_cost"
            mental_key = "extraction_mental_cost"
        else:
            route = self._location_profile(current) or {}
            minutes_key = "return_minutes"
            stamina_key = "return_stamina_cost"
            mental_key = "return_mental_cost"
        costs["time_minutes"] = float(route.get(minutes_key, route.get("travel_minutes_from_base", costs["time_minutes"])))
        costs["stamina_cost"] = float(route.get(stamina_key, route.get("travel_stamina_from_base", costs["stamina_cost"])))
        costs["mental_cost"] = float(route.get(mental_key, route.get("travel_mental_from_base", costs["mental_cost"])))
        return costs

    @staticmethod
    def _deterministic_movement_resolution(action: Mapping[str, Any], costs: Mapping[str, float]) -> Dict[str, Any]:
        return {
            "formula_version": "1.0",
            "action_type": str(action.get("type")),
            "outcome": "普通成功",
            "movement_success": True,
            "probability": 1.0,
            "risk_mode": "deterministic_route",
            "time_cost": float(costs.get("time_minutes", 0.0)),
            "stamina_cost": float(costs.get("stamina_cost", 0.0)),
            "mental_cost": float(costs.get("mental_cost", 0.0)),
        }

    def _system_action_constraints(self, action: Mapping[str, Any], preview: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """只从世界/NPC注册表派生计划硬约束；LLM tags 仅保留在叙事账本。"""
        profile = preview.get("target_profile", {}) if isinstance(preview, Mapping) else self._action_target_profile(action)
        profile = profile if isinstance(profile, Mapping) else {}
        action_type = str(action.get("type"))
        world = self.state.data.get("world", {}) if isinstance(self.state.data.get("world", {}), Mapping) else {}
        rules = world.get("rules", {}) if isinstance(world.get("rules", {}), Mapping) else {}
        sources = []
        rule_constraints = rules.get("action_constraints", {}) if isinstance(rules.get("action_constraints", {}), Mapping) else {}
        for key in (action_type, str(action.get("target") or "")):
            candidate = rule_constraints.get(key)
            if isinstance(candidate, Mapping):
                sources.append(candidate)
        if action_type not in {"TRAVEL", "ENTER_LOCATION", "RETURN_TO_BASE", "EXTRACT", "LEAVE_ENCOUNTER"}:
            profile_constraints = profile.get("constraints", {})
            if isinstance(profile_constraints, Mapping):
                sources.append(profile_constraints)
            opportunity_id = profile.get("opportunity_id")
            opportunities = world.get("opportunities", {})
            opportunity = self._registry_lookup(opportunities, opportunity_id)
            if isinstance(opportunity, Mapping):
                sources.append(opportunity.get("constraints", opportunity))
        constraints: Dict[str, Any] = {}
        for source in sources:
            if isinstance(source, Mapping):
                constraints.update(deepcopy(dict(source)))
        availability_definition = constraints.get("availability")
        if isinstance(availability_definition, Mapping) and "allowed_periods" not in constraints:
            constraints["allowed_periods"] = deepcopy(availability_definition.get("allowed_periods", []))
        reservation = constraints.get("reservation")
        if isinstance(reservation, Mapping):
            for key in ("exclusive_group", "window_id", "window_ids", "capacity", "window_capacity"):
                if key in reservation and key not in constraints:
                    constraints[key] = deepcopy(reservation[key])
        commitment = constraints.get("commitment")
        if isinstance(commitment, Mapping):
            if "commitment_axis" not in constraints and commitment.get("axis") is not None:
                constraints["commitment_axis"] = commitment["axis"]
            if "commitment_value" not in constraints and commitment.get("value") is not None:
                constraints["commitment_value"] = commitment["value"]
        system_tags = set(str(tag).lower() for tag in constraints.get("system_tags", constraints.get("tags", [])) if tag)
        if action_type in {"EXPLORATION", "COMBAT", "BATCH_ACTION", "BUILD", "RESEARCH", "REST"}:
            system_tags.add("major_action")
        if action_type in {"EXPLORATION", "COMBAT", "BUILD", "RESEARCH"}:
            system_tags.add("requires_full_attention")

        commitments = []
        raw_commitments = constraints.get("commitments", [])
        if isinstance(raw_commitments, list):
            for item in raw_commitments:
                if isinstance(item, Mapping) and item.get("axis") is not None and item.get("value") is not None:
                    commitments.append((str(item["axis"]), str(item["value"])))
        if constraints.get("commitment_axis") is not None and constraints.get("commitment_value") is not None:
            commitments.append((str(constraints["commitment_axis"]), str(constraints["commitment_value"])))

        windows = []
        current_period = str(
            preview.get("start_period", self.state.meta.get("time_of_day", "清晨"))
            if isinstance(preview, Mapping)
            else self.state.meta.get("time_of_day", "清晨")
        )
        raw_windows = constraints.get("windows", [])
        if isinstance(raw_windows, list):
            for item in raw_windows:
                if isinstance(item, Mapping) and (item.get("exclusive_group") or item.get("group")):
                    window_ids = item.get("window_ids", item.get("window_id"))
                    if not isinstance(window_ids, list):
                        window_ids = [window_ids] if window_ids is not None else []
                    if not window_ids or any(str(value) in {"current_period", "period"} for value in window_ids):
                        window_ids = [current_period]
                    elif current_period in {str(value) for value in window_ids}:
                        window_ids = [current_period]
                    windows.append({"group": str(item.get("exclusive_group", item.get("group"))), "ids": sorted({str(value) for value in window_ids}), "capacity": int(item.get("capacity", item.get("window_capacity", 1)) or 1)})
        exclusive_group = constraints.get("exclusive_group")
        if exclusive_group:
            window_ids = constraints.get("window_ids", constraints.get("opportunity_windows", constraints.get("window_id")))
            if not isinstance(window_ids, list):
                window_ids = [window_ids] if window_ids is not None else []
            if not window_ids or any(str(value) in {"current_period", "period"} for value in window_ids):
                window_ids = [current_period]
            elif current_period in {str(value) for value in window_ids}:
                window_ids = [current_period]
            windows.append({"group": str(exclusive_group), "ids": sorted({str(value) for value in window_ids}), "capacity": int(constraints.get("window_capacity", 1) or 1)})

        target_id = action.get("target")
        npc = next((candidate for candidate in self.state.data.get("npcs", []) if isinstance(candidate, Mapping) and candidate.get("id", candidate.get("name")) == target_id), None)
        if npc is not None:
            schedule = npc.get("schedule", {}) if isinstance(npc.get("schedule", {}), Mapping) else {}
            period = current_period
            scheduled_action = schedule.get(period)
            if scheduled_action:
                windows.append({"group": f"npc:{target_id}", "ids": [period], "capacity": 1})
                if str(scheduled_action).lower() in {"rest", "休息", "unavailable", "不可用"}:
                    constraints["npc_unavailable"] = True
        return {
            "tags": sorted(system_tags),
            "commitments": commitments,
            "windows": windows,
            "allowed_periods": [str(value) for value in constraints.get("allowed_periods", [])] if isinstance(constraints.get("allowed_periods", []), list) else [],
            "npc_unavailable": bool(constraints.get("npc_unavailable")),
        }

    def _required_action_location(self, action: Mapping[str, Any]) -> Optional[str]:
        """返回行动真正需要的地点；这里只读取注册表，不接受 LLM 自报地点。"""
        def registered(location_id: Optional[str]) -> Optional[str]:
            if not location_id:
                return None
            if location_id == self._base_location() or self._location_profile(location_id):
                return location_id
            return None

        action_type = str(action.get("type"))
        base_location = self._base_location()
        if action_type in {"RETURN_TO_BASE", "EXTRACT", "REST", "BUILD", "BASE_MANAGEMENT"}:
            return base_location
        if action_type in {"TRAVEL", "ENTER_LOCATION"}:
            target = self._movement_target(action)
            return registered(target)
        if action_type == "LEAVE_ENCOUNTER":
            return self._current_location()

        profile = self._action_target_profile(action)
        requirements = profile.get("requirements", {}) if isinstance(profile, Mapping) else {}
        if isinstance(requirements, Mapping) and requirements.get("location"):
            return registered(str(requirements["location"]))
        if isinstance(profile, Mapping) and profile.get("location_id"):
            return registered(str(profile["location_id"]))

        if action_type == "BATCH_ACTION":
            area = self._registry_lookup(self.state.data.get("world", {}).get("areas", {}), action.get("target"))
            area = area or self._registry_lookup(self.state.data.get("world", {}).get("farm_areas", {}), action.get("target"))
            if isinstance(area, Mapping) and area.get("location_id"):
                return registered(str(area["location_id"]))
        if action_type == "COMBAT":
            world = self.state.data.get("world", {}) if isinstance(self.state.data.get("world", {}), Mapping) else {}
            for registry_name in ("encounter_entities", "targets", "combat_targets"):
                target = self._registry_lookup(world.get(registry_name, {}), action.get("target"))
                if isinstance(target, Mapping) and target.get("location_id"):
                    return registered(str(target["location_id"]))
        return None

    @staticmethod
    def _public_plan_step(step: Mapping[str, Any]) -> Dict[str, Any]:
        return {key: deepcopy(value) for key, value in step.items() if not str(key).startswith("_")}

    def _compile_action_plan_steps(self, steps: list[Dict[str, Any]], plan_id: str) -> list[Dict[str, Any]]:
        """按模拟中的当前位置补齐必需的路线步骤，避免把空间规则交给 LLM。"""
        compiled: list[Dict[str, Any]] = []
        simulated_location = self._current_location()
        for step in steps:
            source_id = str(step["action_id"])
            required_location = self._required_action_location(step)
            if required_location and required_location != simulated_location:
                if simulated_location != self._base_location():
                    compiled.append({
                        "action_id": f"{plan_id}-auto-extract-{len(compiled) + 1}",
                        "type": "EXTRACT",
                        "_source_action_id": source_id,
                        "_auto_generated": True,
                    })
                    simulated_location = self._base_location()
                if required_location != self._base_location():
                    compiled.append({
                        "action_id": f"{plan_id}-auto-travel-{len(compiled) + 1}",
                        "type": "TRAVEL",
                        "target": required_location,
                        "_source_action_id": source_id,
                        "_auto_generated": True,
                    })
                    simulated_location = required_location
            compiled_step = deepcopy(step)
            compiled_step["_source_action_id"] = source_id
            compiled.append(compiled_step)
            if str(step.get("type")) in {"TRAVEL", "ENTER_LOCATION"}:
                simulated_location = self._movement_target(step)
            elif str(step.get("type")) in {"RETURN_TO_BASE", "EXTRACT"}:
                simulated_location = self._base_location()
        return compiled

    def _spawn_exploration_encounter(self, action: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        profile = self._action_target_profile(action)
        definition_ids = profile.get("encounter_target_ids", []) if isinstance(profile.get("encounter_target_ids", []), list) else []
        if not definition_ids:
            return None
        world = self.state.data.get("world", {})
        definitions = world.get("enemy_definitions", {}) if isinstance(world.get("enemy_definitions", {}), Mapping) else {}
        legacy_definitions = world.get("combat_targets", {}) if isinstance(world.get("combat_targets", {}), Mapping) else {}
        entities = []
        target_ids = []
        turn = self.state.current_turn + 1
        location_id = str(profile.get("location_id") or self._current_location())
        extraction_rule = self._extraction_rule(location_id)
        exploration_costs = self._derive_action_costs(action)
        created_at_minutes = self._timeline_minutes() + float(exploration_costs.get("time_minutes", 0.0))
        for index, definition_id in enumerate(definition_ids, start=1):
            definition = self._registry_lookup(definitions, definition_id) or self._registry_lookup(legacy_definitions, definition_id)
            if not definition:
                continue
            instance_id = f"{definition_id}_instance_{turn:04d}_{index}"
            entity = deepcopy(dict(definition))
            entity.update({"id": instance_id, "instance_id": instance_id, "definition_id": str(definition_id), "status": "alive", "spawned_turn": turn, "location_id": location_id})
            entities.append(entity)
            target_ids.append(instance_id)
        if not target_ids:
            return None
        encounter_id = f"encounter_{turn:04d}_{location_id}"
        return {
            "id": encounter_id,
            "location_id": location_id,
            "target_ids": target_ids,
            "participants": ["player", *target_ids],
            "status": "active",
            "created_turn": turn,
            "expires_turn": turn + 3,
            "extraction_rule": deepcopy(dict(extraction_rule)),
            "extraction_deadline_at_minutes": created_at_minutes + float(extraction_rule.get("deadline_minutes", 0.0)) if extraction_rule.get("deadline_minutes") is not None else None,
            "entity_additions": entities,
        }

    def _domain_effects(self, action: Mapping[str, Any], resolution: Mapping[str, Any], dilution_multiplier: float = 1.0) -> Dict[str, Any]:
        action_type = str(action.get("type", ""))
        dilution_multiplier = max(0.25, min(1.0, float(dilution_multiplier)))
        if action_type == "REACTION":
            pending = self.state.meta.get("pending_reaction", {})
            pending = pending if isinstance(pending, Mapping) else {}
            effects = pending.get("effects", {}) if isinstance(pending.get("effects", {}), Mapping) else {}
            outcome = str(resolution.get("outcome", ""))
            if any(key in effects for key in ("success", "partial_failure", "failure")):
                if outcome in {"大成功", "普通成功", "成功但付出代价"}:
                    effects = effects.get("success", {})
                elif outcome == "失败但获得部分信息":
                    effects = effects.get("partial_failure", {})
                else:
                    effects = effects.get("failure", {})
                effects = effects if isinstance(effects, Mapping) else {}
            result = {
                "event_type": "REACTION_RESOLVED",
                "reaction_id": pending.get("id"),
                "reaction_effect": str(action.get("goal") or (action.get("parameters", {}) or {}).get("objective") or "即时处置"),
                "proposed_events": [{"type": "REACTION_RESOLVED", "target": pending.get("id")}],
            }
            result.update(deepcopy(dict(effects)))
            return result
        if action_type in {"TRAVEL", "ENTER_LOCATION", "RETURN_TO_BASE", "EXTRACT", "LEAVE_ENCOUNTER"} and not bool(resolution.get("movement_success")):
            raise ValueError("移动/撤离没有获得 Python 路线成功结果，拒绝修改地点状态")
        if action_type in {"TRAVEL", "ENTER_LOCATION"}:
            target = self._movement_target(action)
            return {
                "event_type": "TRAVEL_COMPLETED",
                "current_location": target,
                "current_location_name": self._location_name(target),
                "current_encounter_id": None,
                "movement": {"from": self._current_location(), "to": target, "mode": action_type},
                "discover_locations": [target],
                "proposed_events": [{"type": "LOCATION_ENTERED", "target": target}],
            }
        if action_type == "RETURN_TO_BASE":
            target = self._base_location()
            return {
                "event_type": "RETURN_TO_BASE_COMPLETED",
                "current_location": target,
                "current_location_name": self._location_name(target),
                "current_encounter_id": None,
                "movement": {"from": self._current_location(), "to": target, "mode": action_type},
                "proposed_events": [{"type": "RETURNED_TO_BASE", "target": target}],
            }
        if action_type == "EXTRACT":
            target = self._base_location()
            encounter_id = self.state.meta.get("current_encounter_id")
            return {
                "event_type": "EXTRACTION_COMPLETED",
                "current_location": target,
                "current_location_name": self._location_name(target),
                "current_encounter_id": None,
                "encounter_updates": [{"id": encounter_id, "status": "escaped", "closed_turn": self.state.current_turn + 1}] if encounter_id else [],
                "movement": {"from": self._current_location(), "to": target, "mode": action_type},
                "proposed_events": [{"type": "ENCOUNTER_EXTRACTED", "target": encounter_id}],
            }
        if action_type == "LEAVE_ENCOUNTER":
            encounter_id = self.state.meta.get("current_encounter_id")
            return {
                "event_type": "ENCOUNTER_LEFT",
                "current_encounter_id": None,
                "encounter_updates": [{"id": encounter_id, "status": "escaped", "closed_turn": self.state.current_turn + 1}] if encounter_id else [],
                "proposed_events": [{"type": "ENCOUNTER_LEFT", "target": encounter_id}],
            }
        if action_type == "REST":
            return {
                "fatigue_delta": -35.0,
                "mental_delta": 20.0,
                "hp_delta": 5.0,
                "proposed_events": [{"type": "REST_COMPLETED", "target": self._current_location()}],
            }
        if action_type == "WAIT":
            return {
                "event_type": "WAIT_COMPLETED",
                "proposed_events": [{"type": "TIME_ADVANCED", "target": self._current_location()}],
            }
        profile = self._action_target_profile(action)
        effects = profile.get("effects", {}) if isinstance(profile.get("effects", {}), Mapping) else {}
        outcome = str(resolution.get("outcome", ""))
        if outcome in {"大成功", "普通成功", "成功但付出代价"}:
            selected = effects.get("success", {})
        elif outcome == "失败但获得部分信息":
            selected = effects.get("partial_failure", {})
        else:
            selected = effects.get("failure", {})
        selected = deepcopy(dict(selected)) if isinstance(selected, Mapping) else {}
        if dilution_multiplier < 1.0:
            selected["effect_multiplier"] = dilution_multiplier
            if selected.get("resource_changes"):
                selected["resource_changes"] = {key: float(value) * dilution_multiplier for key, value in selected["resource_changes"].items()}
            if selected.get("relationship_changes"):
                selected["relationship_changes"] = {
                    relation_id: {key: float(value) * dilution_multiplier for key, value in changes.items()}
                    for relation_id, changes in selected["relationship_changes"].items()
                }
            if selected.get("knowledge_additions"):
                selected["information_completeness"] = dilution_multiplier
        parameters = action.get("parameters", {}) if isinstance(action.get("parameters", {}), Mapping) else {}
        relationship_intent = str(parameters.get("relationship_intent", "")).lower()
        if action_type == "SOCIAL_INTERACTION" and any(token in relationship_intent for token in ("promise", "承诺", "保证")):
            selected["promise_additions"] = [{"id": f"promise_{self.state.current_turn + 1}_{action.get('target')}", "npc_id": action.get("target"), "content": str(parameters.get("message") or action.get("goal") or action.get("approach") or "未注明承诺"), "created_turn": self.state.current_turn + 1, "due_turn": self.state.current_turn + 4, "status": "open"}]
        if action_type == "SOCIAL_INTERACTION" and any(token in relationship_intent for token in ("deceive", "欺骗", "隐瞒")):
            selected["deception_attempts"] = [{"id": f"deception_{self.state.current_turn + 1}_{action.get('target')}", "npc_id": action.get("target"), "content": str(parameters.get("message") or action.get("goal") or "未注明欺骗内容"), "detected": outcome not in {"大成功", "普通成功"}, "turn": self.state.current_turn + 1}]
        if action_type == "EXPLORATION" and outcome in {"大成功", "普通成功", "成功但付出代价", "失败但获得部分信息"}:
            encounter = self._spawn_exploration_encounter(action)
            if encounter:
                selected["encounter_additions"] = [encounter]
                selected["current_encounter_id"] = encounter["id"]
        proposed = []
        proposed.extend({"type": "AREA_DISCOVERED", "target": item} for item in selected.get("discover_locations", []))
        proposed.extend({"type": "KNOWLEDGE_GAINED", "target": item} for item in selected.get("knowledge_additions", []))
        proposed.extend({"type": "RESOURCE_CHANGED", "target": item, "quantity": quantity} for item, quantity in (selected.get("resource_changes", {}) or {}).items())
        proposed.extend({"type": "RELATIONSHIP_CHANGED", "target": item} for item in (selected.get("relationship_changes", {}) or {}))
        proposed.extend({"type": "ENCOUNTER_CREATED", "target": item.get("id")} for item in selected.get("encounter_additions", []) if isinstance(item, Mapping))
        selected["proposed_events"] = proposed
        if action_type == "EXPLORATION":
            selected["event_type"] = "EXPLORATION_RESOLVED"
        elif action_type == "RESEARCH":
            selected["event_type"] = "RESEARCH_RESOLVED"
        elif action_type == "SOCIAL_INTERACTION":
            selected["event_type"] = "SOCIAL_RESOLVED"
        return selected

    def _narrative_decision(self, action: Mapping[str, Any], preview: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        profile = self._action_target_profile(action)
        ledger = preview.get("action_ledger", {}) if isinstance(preview, Mapping) else {}
        action_row = ledger.get("actions", [{}])[0] if isinstance(ledger.get("actions", [{}]), list) else {}
        available = max(float(self.state.meta.get("available_time_minutes", 720)), 1.0)
        time_ratio = min(1.0, max(0.0, float(action_row.get("time_minutes", 0.0)) / available))
        unknown = min(1.0, max(0.0, float(profile.get("unknown_risk", 0.0)) / 30.0))
        irreversible = 1.0 if str(action.get("type")) in {"COMBAT", "BUILD", "SOCIAL_INTERACTION"} else 0.5
        risk_values = {
            "cost_fulfillment": 1.0 if action_row else 0.5,
            "failure_clarity": float(profile.get("causal_chain", 0.5)),
            "enemy_effectiveness": float(profile.get("risk_warning", 0.5)),
            "information_incompleteness": unknown,
            "limited_protection": 0.8 if self.state.meta.get("difficulty") != "休闲" else 0.5,
        }
        return {
            "consequence_difference": 0.8 if profile.get("effects") else 0.4,
            "opportunity_cost": time_ratio,
            "irreversibility": irreversible,
            "information_uncertainty": unknown,
            "value_impact": 0.7 if profile.get("effects") else 0.3,
            "route_divergence": 0.8 if profile else 0.3,
            "option_balance": 0.7,
            "information_sufficiency": max(0.0, 1.0 - unknown),
            "long_term_impact": irreversible,
            "uncertainty": {"danger_unknown": unknown, "rule_unknown": 0.1, "motive_unknown": 0.3, "world_unknown": 0.5, "reward_unknown": unknown},
            "risk_credibility": risk_values,
            "combinability": {"time_remaining": 1.0 - time_ratio, "resource_compatibility": 1.0, "location_proximity": 1.0, "goal_compatibility": 1.0, "npc_availability": 1.0},
            "permanent_growth": 0.8 if str(action.get("type")) in {"COMBAT", "BUILD"} else 0.0,
            "world_change": 0.8 if str(action.get("type")) in {"EXPLORATION", "BUILD"} else 0.0,
            "relationship_change": 0.8 if str(action.get("type")) == "SOCIAL_INTERACTION" else 0.0,
            "information_change": 0.8 if str(action.get("type")) in {"EXPLORATION", "RESEARCH"} else 0.0,
            "goal_progress": 0.7 if profile.get("effects") else 0.2,
            "new_playable_system": 0.6 if profile.get("effects") else 0.0,
        }

    def _narrative_payoff(self, action: Mapping[str, Any], resolution: Mapping[str, Any]) -> Dict[str, Any]:
        profile = self._action_target_profile(action)
        outcome = str(resolution.get("outcome", ""))
        positive = 0.0
        effects = profile.get("effects", {}) if isinstance(profile.get("effects", {}), Mapping) else {}
        for branch in ("success", "partial_failure"):
            values = effects.get(branch, {}) if isinstance(effects.get(branch, {}), Mapping) else {}
            positive += sum(max(0.0, float(value)) for value in (values.get("resource_changes", {}) or {}).values())
        return {
            "scarcity_pressure": float(self.state.meta.get("narrative_state", {}).get("pressure_components", {}).get("resource_scarcity", 0.0)),
            "setup_depth": min(100.0, float(len(self.state.meta.get("active_mystery_records", []))) * 20.0),
            "waiting_time": min(100.0, float(self.state.current_turn) * 5.0),
            "cost_paid": min(100.0, float(resolution.get("severity", 0.0)) + (20.0 if outcome == "成功但付出代价" else 0.0)),
            "chapter_rhythm": 50.0,
            "relative_gain": min(100.0, positive * 10.0),
            "restriction_removed": 50.0 if outcome in {"大成功", "普通成功"} else 0.0,
            "behavior_change": 40.0 if profile.get("effects") else 0.0,
            "long_term_value": 50.0 if profile.get("effects") else 0.0,
            "social_feedback": 40.0 if str(action.get("type")) == "SOCIAL_INTERACTION" else 0.0,
            "causal_chain": float(profile.get("causal_chain", 0.5)),
            "rule_consistency": float(profile.get("rule_consistency", 0.5)),
            "reward_foreshadowed": float(profile.get("risk_warning", 0.5)),
            "new_playable_system": 60.0 if profile.get("effects") else 0.0,
            "decision_change": 40.0 if outcome in {"大成功", "严重失败"} else 0.0,
            "higher_resource_need": 30.0 if profile.get("effects") else 0.0,
            "social_market_effect": 40.0 if str(action.get("type")) == "SOCIAL_INTERACTION" else 0.0,
            "fatigue": float(self.state.player.get("fatigue", 0.0)),
            "story_damage": 0.0,
        }

    def _host_seed(self, action: Mapping[str, Any]) -> str:
        """由存档状态生成种子，主机不能覆盖。"""
        return (
            f"{self.state.meta.get('rng_seed', self.state.meta.get('world_name', 'world'))}"
            f"|turn:{self.state.current_turn + 1}|action:{action.get('action_id')}"
        )

    def _derived_budget_errors(self, action: Mapping[str, Any], costs: Mapping[str, float]) -> list[str]:
        errors = self._check_requirements(action)
        available_time = float(self.state.meta.get("available_time_minutes", 240))
        if str(action.get("type")) != "REACTION" and float(costs["time_minutes"]) > available_time:
            errors.append("时间不足")
        if str(action.get("type")) == "REACTION" and not 0.0 <= float(costs["time_minutes"]) <= 5.0:
            errors.append("反应行动必须在0-5分钟内")
        if float(self.state.player.get("fatigue", 0)) + float(costs["stamina_cost"]) > 100:
            errors.append("体力不足")
        if float(self.state.player.get("mental", 100)) - float(costs["mental_cost"]) < 0:
            errors.append("精神不足")
        return errors

    @staticmethod
    def _registry_lookup(registry: Any, identifier: Any) -> Optional[Mapping[str, Any]]:
        if not identifier:
            return None
        if isinstance(registry, Mapping):
            value = registry.get(identifier)
            if isinstance(value, Mapping):
                return value
            return next((candidate for candidate in registry.values() if isinstance(candidate, Mapping) and candidate.get("id", candidate.get("name")) == identifier), None)
        if isinstance(registry, list):
            for value in registry:
                if isinstance(value, Mapping) and value.get("id", value.get("name")) == identifier:
                    return value
        return None

    def _lookup_target(self, target_id: Any) -> Mapping[str, Any]:
        world = self.state.data.get("world", {})
        target = self._registry_lookup(world.get("encounter_entities"), target_id)
        if target is None:
            target = self._registry_lookup(world.get("targets"), target_id)
        if target is None:
            target = self._registry_lookup(world.get("combat_targets"), target_id)
        if target is None:
            target = self._registry_lookup(self.state.data.get("npcs", []), target_id)
        if target is None:
            raise ValueError(f"世界注册表中不存在战斗目标：{target_id}")
        if target.get("status") == "definition":
            raise ValueError(f"目标 {target_id} 只是怪物类型定义，必须先进入遭遇")
        if target.get("status") in {"dead", "destroyed"}:
            raise ValueError(f"战斗目标已经死亡：{target_id}")
        return target

    def _lookup_module(self, module_id: Any) -> Mapping[str, Any]:
        world = self.state.data.get("world", {})
        module = self._registry_lookup(world.get("build_catalog"), module_id)
        if module is None:
            module = self._registry_lookup(world.get("modules"), module_id)
        if module is None:
            raise ValueError(f"世界建造目录中不存在模块：{module_id}")
        return module

    def _lookup_area(self, area_id: Any) -> Mapping[str, Any]:
        world = self.state.data.get("world", {})
        area = self._registry_lookup(world.get("areas"), area_id)
        if area is None:
            area = self._registry_lookup(world.get("farm_areas"), area_id)
        if area is None:
            raise ValueError(f"世界区域目录中不存在刷怪区域：{area_id}")
        return area

    def _combat_environment(self, target: Mapping[str, Any], costs: Mapping[str, float]) -> Dict[str, Any]:
        raw_environment = target.get("environment", {})
        environment = dict(raw_environment) if isinstance(raw_environment, Mapping) else {}
        environment.setdefault("difficulty", self.state.meta.get("difficulty", self.state.data.get("world", {}).get("difficulty", "标准")))
        environment["time_minutes"] = float(costs["time_minutes"])
        environment["stamina_cost"] = float(costs["stamina_cost"])
        environment["mental_cost"] = float(costs["mental_cost"])
        environment["available_time_minutes"] = float(self.state.meta.get("available_time_minutes", 240))
        return environment

    def _combat_weapon(self) -> Mapping[str, Any]:
        equipment = self.state.inventory.get("equipment", {})
        weapon = equipment.get("main_weapon", {}) if isinstance(equipment, Mapping) else {}
        weapon = dict(weapon) if isinstance(weapon, Mapping) else {}
        ammo_resource = weapon.get("ammo_resource")
        resources = self.state.inventory.get("resources", {})
        if ammo_resource and "ammo_available" not in weapon and isinstance(resources, Mapping):
            weapon["ammo_available"] = float(resources.get(ammo_resource, 0))
            weapon["_ammo_from_resource"] = True
        return weapon

    def _batch_internal_action(self, action: Mapping[str, Any], area: Mapping[str, Any], costs: Mapping[str, float]) -> Dict[str, Any]:
        equipment = self.state.inventory.get("equipment", {})
        weapon = equipment.get("main_weapon", {}) if isinstance(equipment, Mapping) else {}
        weapon = weapon if isinstance(weapon, Mapping) else {}
        area_ammo_resource = area.get("ammo_resource", weapon.get("ammo_resource"))
        resources = self.state.inventory.get("resources", {})
        resources = resources if isinstance(resources, Mapping) else {}
        if weapon.get("ammo_available") is not None:
            ammo_available = float(weapon.get("ammo_available", 0))
        elif area_ammo_resource:
            ammo_available = float(resources.get(area_ammo_resource, 0))
        else:
            ammo_available = 0.0
        internal = {
            "area": dict(area),
            "minutes": float(costs["time_minutes"]),
            "available_time_minutes": float(self.state.meta.get("available_time_minutes", 240)),
            "kill_success_rate": float(area.get("kill_success_rate", 0.0)),
            "ammo_available": ammo_available,
            "ammo_per_kill": float(area.get("ammo_per_kill", weapon.get("ammo_cost", 1))),
            "weapon_rate_per_hour": float(area.get("weapon_rate_per_hour", weapon.get("rate_per_hour", 0.0))),
            "recovery_efficiency": float(area.get("recovery_efficiency", 1.0)),
            "backpack_capacity_modifier": float(area.get("backpack_capacity_modifier", 1.0)),
            "enemy_groups": area.get("enemy_groups", []),
            "farmability_components": area.get("farmability_components", {}),
            "stop_conditions": action.get("stop_conditions", {}),
            "ammo_resource": area_ammo_resource,
            "action_type": "BATCH_ACTION",
            "target": action.get("target"),
            "stamina_cost": float(costs["stamina_cost"]),
            "mental_cost": float(costs["mental_cost"]),
            "tags": list(action.get("tags", [])),
        }
        return internal

    def preview_attribute_allocation(self, action: Mapping[str, Any]) -> Dict[str, Any]:
        """预览玩家分配自由属性点；这是零时间的直接状态操作，不走概率结算。"""
        validate_host_action(action)
        parameters = action.get("parameters", {}) if isinstance(action.get("parameters", {}), Mapping) else {}
        allocations = canonicalize_attribute_allocations(parameters.get("allocations"))
        try:
            points_before = int(self.state.player.get("free_points", 0) or 0)
        except (TypeError, ValueError):
            points_before = 0
        points_spent = sum(allocations.values())
        errors = self._check_requirements(action)
        if points_before < 0:
            errors.append("当前未分配属性点状态无效")
        if points_spent > points_before:
            errors.append(f"属性点不足：需要 {points_spent} 点，当前只有 {points_before} 点")
        resolution = {
            "formula_version": "attribute_allocation_v1",
            "action_type": "ATTRIBUTE_ALLOCATION",
            "outcome": "属性点分配完成",
            "allocation_success": not errors,
            "allocations": deepcopy(allocations),
            "points_before": points_before,
            "points_spent": points_spent,
            "points_after": points_before - points_spent,
        }
        return {
            "legal": not errors,
            "errors": errors,
            "resolution": resolution,
            "action_ledger": {
                "available_time_minutes": float(self.state.meta.get("available_time_minutes", 720)),
                "available_stamina": max(0.0, 100.0 - float(self.state.player.get("fatigue", 0))),
                "available_mental": float(self.state.player.get("mental", 100)),
                "actions": [{
                    "type": "ATTRIBUTE_ALLOCATION",
                    "target": None,
                    "time_minutes": 0.0,
                    "stamina_cost": 0.0,
                    "mental_cost": 0.0,
                    "tags": ["progression", "zero_time"],
                }],
            },
        }

    def execute_attribute_allocation(self, action: Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        """通过标准事件把已验证的属性点分配写入 SQLite 投影。"""
        preview = self.preview_attribute_allocation(action)
        if not preview["legal"]:
            raise ValueError("属性点分配不合法：" + "、".join(preview["errors"]))
        resolution = preview["resolution"]
        allocations = deepcopy(resolution["allocations"])
        turn = self.state.current_turn + 1
        payload = {
            "action": {"action_id": action.get("action_id"), "type": "ATTRIBUTE_ALLOCATION"},
            "action_ledger": preview["action_ledger"],
            "resolution": resolution,
            "attribute_allocations": allocations,
            "player_delta": {"attributes": allocations, "free_points": -int(resolution["points_spent"])},
            "time_cost": 0.0,
            "proposed_events": [{"type": "ATTRIBUTES_ALLOCATED", "target": "player", "allocations": allocations}],
        }
        event = standard_event(
            event_id=f"evt_{turn:04d}_001",
            event_type="ATTRIBUTES_ALLOCATED",
            actor="player",
            target="player",
            data=payload,
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        self.state.apply_and_append(event, persist=persist)
        if persist:
            self.state.save()
        return {"event": event, "resolution": resolution, "state": self.state.data}

    def preview_host_action(self, action: Mapping[str, Any], dilution_multiplier: float = 1.0) -> Dict[str, Any]:
        """预览唯一主机协议；专用行动的参数全部来自世界注册表。"""
        validate_host_action(action)
        if str(action.get("type")) == "ACTION_PLAN":
            return self.preview_action_plan(action)
        if str(action.get("type")) == "TALENT_CHOICE":
            return self.preview_talent_choice(action)
        if str(action.get("type")) == "ATTRIBUTE_ALLOCATION":
            return self.preview_attribute_allocation(action)
        if str(action.get("type")) in {"ENDING", "RESTART", "CHECKPOINT", "LEGACY_CREATE"}:
            return {"legal": True, "errors": [], "resolution": self._terminal_resolution(action), "action_ledger": {"available_time_minutes": float(self.state.meta.get("available_time_minutes", 720)), "actions": [{"type": action.get("type"), "target": action.get("target"), "time_minutes": 0.0, "stamina_cost": 0.0, "mental_cost": 0.0, "tags": ["terminal"]}]}}
        skill = self._find_skill(action)
        costs = self._derive_action_costs(action, skill)
        errors = self._derived_budget_errors(action, costs)
        action_type = str(action.get("type"))
        if action_type == "COMBAT":
            target = self._lookup_target(action.get("target"))
            environment = self._combat_environment(target, costs)
            weapon = self._combat_weapon()
            resolution = calculate_combat(self.state.player, target, weapon=weapon, skill=skill, environment=environment, seed=self._host_seed(action), dilution_multiplier=dilution_multiplier)
            combat_tags = list(action.get("tags", [])) if isinstance(action.get("tags", []), list) else []
            for tag in ("major_action", "requires_full_attention"):
                if tag not in combat_tags:
                    combat_tags.append(tag)
            return {"legal": not errors, "errors": errors, "resolution": resolution.to_dict(), "action_ledger": {"available_time_minutes": environment["available_time_minutes"], "actions": [{"type": "COMBAT", "target": action.get("target"), "time_minutes": costs["time_minutes"], "stamina_cost": costs["stamina_cost"], "mental_cost": costs["mental_cost"], "tags": combat_tags}]}}
        if action_type == "BUILD":
            module = self._lookup_module(action.get("target"))
            available_minutes = min(float(self.state.meta.get("available_time_minutes", 240)), float(costs["time_minutes"]))
            module_for_build = deepcopy(dict(module))
            effects = module_for_build.get("effects", {})
            normalized_dilution = max(0.25, min(1.0, float(dilution_multiplier)))
            if normalized_dilution < 1.0 and isinstance(effects, Mapping):
                module_for_build["effects"] = {key: float(value) * normalized_dilution if isinstance(value, (int, float)) else value for key, value in effects.items()}
            module_for_build["quality_multiplier"] = normalized_dilution
            result = calculate_build(self.state.data.get("base", {}), module_for_build, self.state.inventory, available_minutes)
            result["quality_multiplier"] = normalized_dilution
            errors.extend(result.get("errors", []))
            build_tags = list(action.get("tags", [])) if isinstance(action.get("tags", []), list) else []
            for tag in ("major_action", "requires_full_attention"):
                if tag not in build_tags:
                    build_tags.append(tag)
            return {"legal": not errors, "errors": errors, "resolution": result, "action_ledger": {"available_time_minutes": available_minutes, "actions": [{"type": "BUILD", "target": action.get("target"), "time_minutes": result.get("time_required", costs["time_minutes"]), "stamina_cost": costs["stamina_cost"], "mental_cost": costs["mental_cost"], "tags": build_tags}]}}
        if action_type == "BATCH_ACTION":
            area = self._lookup_area(action.get("target"))
            internal = self._batch_internal_action(action, area, costs)
            result = simulate_batch_action(
                area=internal["area"], player_level=int(self.state.player.get("level", 1)), minutes=internal["minutes"], kill_success_rate=internal["kill_success_rate"] * max(0.25, min(1.0, dilution_multiplier)), ammo_available=internal["ammo_available"], ammo_per_kill=internal["ammo_per_kill"], weapon_rate_per_hour=internal["weapon_rate_per_hour"], recovery_efficiency=internal["recovery_efficiency"] * max(0.25, min(1.0, dilution_multiplier)), backpack_capacity_modifier=internal["backpack_capacity_modifier"], enemy_groups=internal["enemy_groups"], farmability_components=internal["farmability_components"], stop_conditions=internal["stop_conditions"]
            )
            batch_tags = list(action.get("tags", [])) if isinstance(action.get("tags", []), list) else []
            if "major_action" not in batch_tags:
                batch_tags.append("major_action")
            return {"legal": not errors, "errors": errors, "resolution": result.to_dict(), "action_ledger": {"available_time_minutes": internal["available_time_minutes"], "actions": [{"type": "BATCH_ACTION", "target": action.get("target"), "time_minutes": costs["time_minutes"], "stamina_cost": costs["stamina_cost"], "mental_cost": costs["mental_cost"], "tags": batch_tags}]}}
        return self.preview_action(action, dilution_multiplier=dilution_multiplier)

    @staticmethod
    def _plan_step(step: Mapping[str, Any], plan_id: str, index: int) -> Dict[str, Any]:
        normalized = {key: deepcopy(value) for key, value in step.items() if key in {"action_id", "type", "target", "skill_id", "risk_preference", "tags", "goal", "parameters", "requirements"}}
        normalized["action_id"] = str(normalized.get("action_id") or f"{plan_id}-step-{index}")
        if step.get("approach"):
            parameters = normalized.setdefault("parameters", {})
            if isinstance(parameters, dict):
                parameters.setdefault("approach", step["approach"])
        return normalized

    def _ordered_plan_steps(self, action: Mapping[str, Any]) -> list[Dict[str, Any]]:
        plan_id = str(action.get("plan_id"))
        steps = [self._plan_step(step, plan_id, index) for index, step in enumerate(action.get("steps", []), start=1)]
        priority_order = action.get("priority_order")
        if not isinstance(priority_order, list) or not priority_order:
            return steps
        by_id = {str(step["action_id"]): step for step in steps}
        ordered: list[Dict[str, Any]] = []
        used = set()
        for priority in priority_order:
            key = str(priority)
            if key.isdigit() and 1 <= int(key) <= len(steps):
                key = str(steps[int(key) - 1]["action_id"])
            step = by_id.get(key)
            if step is not None and key not in used:
                ordered.append(step)
                used.add(key)
        ordered.extend(step for step in steps if str(step["action_id"]) not in used)
        return ordered

    def _simulate_plan_steps(self, steps: list[Dict[str, Any]], dilution_multiplier: float) -> tuple[list[Dict[str, Any]], list[str]]:
        original_data = deepcopy(self.state.data)
        original_pending = deepcopy(self.state.pending_records)
        previews: list[Dict[str, Any]] = []
        errors: list[str] = []
        try:
            self.state.clear_pending()
            for raw_step in steps:
                step = self._public_plan_step(raw_step)
                source_action_id = str(raw_step.get("_source_action_id", step["action_id"]))
                start_period = str(self.state.meta.get("time_of_day", "清晨"))
                start_location = self._current_location()
                try:
                    preview = self.preview_host_action(step, dilution_multiplier=dilution_multiplier)
                except (TypeError, ValueError) as exc:
                    preview = {"legal": False, "errors": [str(exc)], "resolution": {}, "action_ledger": {"actions": []}}
                if preview.get("legal"):
                    try:
                        self.execute_host_action(step, persist=False, dilution_multiplier=dilution_multiplier)
                    except (TypeError, ValueError) as exc:
                        preview["legal"] = False
                        preview.setdefault("errors", []).append(str(exc))
                step_errors = preview.get("errors", []) if isinstance(preview.get("errors", []), list) else []
                errors.extend(f"{source_action_id}：{error}" for error in step_errors)
                previews.append({
                    "action": step,
                    "preview": preview,
                    "source_action_id": source_action_id,
                    "start_period": start_period,
                    "start_location": start_location,
                    "auto_generated": bool(raw_step.get("_auto_generated")),
                })
        finally:
            self.state.data = original_data
            self.state.pending_records = original_pending
        return previews, errors

    def _plan_factors(self, previews: list[Dict[str, Any]], available: float, errors: list[str]) -> Dict[str, float]:
        used_time = sum(float(item["preview"].get("action_ledger", {}).get("actions", [{}])[0].get("time_minutes", 0)) for item in previews)
        time_compatibility = 1.0 if used_time <= available else available / max(used_time, 1.0)
        resource_error = any(token in error for error in errors for token in ("资源不足", "材料不足", "弹药不足", "武器耐久归零"))
        locations = set()
        major_count = 0
        short_count = 0
        attention_count = 0
        mental_load = 0.0
        commitment_values: Dict[str, set[str]] = {}
        opportunity_counts: Dict[tuple[str, str], int] = {}
        opportunity_capacities: Dict[tuple[str, str], int] = {}
        npc_targets = []
        npc_schedule_factor = 1.0
        auto_movement_present = False
        heavy_types = {"EXPLORATION", "COMBAT", "BATCH_ACTION", "BUILD", "RESEARCH", "REST"}
        for item in previews:
            step = item["action"]
            auto_movement_present = auto_movement_present or bool(item.get("auto_generated"))
            ledger = item["preview"].get("action_ledger", {}) if isinstance(item["preview"].get("action_ledger", {}), Mapping) else {}
            row = ledger.get("actions", [{}])[0] if isinstance(ledger.get("actions", [{}]), list) else {}
            action_type = str(step.get("type"))
            constraints = self._system_action_constraints(
                step,
                {**item["preview"], "start_period": item.get("start_period", self.state.meta.get("time_of_day", "清晨"))},
            )
            tags = {str(tag).lower() for tag in constraints.get("tags", []) if tag}
            if constraints.get("npc_unavailable"):
                npc_schedule_factor = 0.0
            time_minutes = float(row.get("time_minutes", 0.0))
            mental_load += float(row.get("mental_cost", 0.0))
            is_major = time_minutes >= 60.0 or action_type in heavy_types or "major_action" in tags
            if not item.get("auto_generated"):
                if is_major:
                    major_count += 1
                else:
                    short_count += 1
            if "requires_full_attention" in tags or action_type in heavy_types:
                attention_count += 1
            for axis, value in constraints.get("commitments", []):
                commitment_values.setdefault(str(axis), set()).add(str(value))
            for window in constraints.get("windows", []):
                if not isinstance(window, Mapping):
                    continue
                group = str(window.get("group", ""))
                ids = window.get("ids", set())
                ids = {str(value) for value in ids} if ids else {"*"}
                capacity = max(1, int(window.get("capacity", 1) or 1))
                for window_id in ids:
                    key = (group, window_id)
                    opportunity_counts[key] = opportunity_counts.get(key, 0) + 1
                    opportunity_capacities[key] = min(opportunity_capacities.get(key, capacity), capacity)
            if step.get("target"):
                npc = next((candidate for candidate in self.state.data.get("npcs", []) if isinstance(candidate, Mapping) and candidate.get("id", candidate.get("name")) == step.get("target")), None)
                if npc is not None:
                    npc_targets.append(str(step.get("target")))
            requirements = step.get("requirements", {}) if isinstance(step.get("requirements", {}), Mapping) else {}
            profile = item["preview"].get("target_profile", {}) if isinstance(item["preview"].get("target_profile", {}), Mapping) else {}
            if action_type in {"TRAVEL", "ENTER_LOCATION"}:
                locations.add(self._movement_target(step))
            elif action_type in {"RETURN_TO_BASE", "EXTRACT"}:
                locations.add(self._base_location())
            else:
                locations.add(str(requirements.get("location", profile.get("location_id", self._current_location()))))
        action_types = {str(item["action"].get("type")) for item in previews}
        capacity = int(self.state.player.get("action_slot_capacity", self.state.meta.get("action_slot_capacity", 1)) or 1)
        slot_factor = 1.0 if major_count <= capacity else capacity / max(major_count, 1)
        if short_count > 2:
            slot_factor = min(slot_factor, 2.0 / short_count)
        attention_factor = 1.0
        if attention_count >= 2:
            attention_factor = 0.60
        if mental_load > 16.0:
            attention_factor = min(attention_factor, 16.0 / mental_load)
        commitment_factor = 1.0
        if any(len(values) > 1 for values in commitment_values.values()):
            commitment_factor = 0.35
        opportunity_factor = 1.0
        for key, count in opportunity_counts.items():
            capacity = opportunity_capacities.get(key, 1)
            if count > capacity:
                opportunity_factor = min(opportunity_factor, capacity / max(count, 1))
        npc_factor = 1.0
        if len(npc_targets) != len(set(npc_targets)):
            npc_factor = 0.35
        return {
            "time_compatibility": max(0.0, min(1.0, time_compatibility)),
            "buffer_ratio": max(0.0, (available - used_time) / max(available, 1.0)),
            "resource_compatibility": 0.0 if resource_error else 1.0,
            "location_proximity": 1.0 if len(locations) <= 1 else 0.8,
            "goal_compatibility": 1.0 if len(action_types) == len(previews) else 0.8,
            "npc_availability": 0.0 if any("NPC不可用" in error for error in errors) else min(npc_factor, npc_schedule_factor),
            "attention_compatibility": max(0.0, min(1.0, attention_factor)),
            "action_slot_compatibility": max(0.0, min(1.0, slot_factor)),
            "commitment_compatibility": commitment_factor,
            "opportunity_window_compatibility": opportunity_factor,
            "movement_compatibility": 1.0 if auto_movement_present or len(locations) <= 1 else 0.8,
        }

    def preview_action_plan(self, action: Mapping[str, Any]) -> Dict[str, Any]:
        validate_host_action(action)
        plan_id = str(action.get("plan_id"))
        original_steps = self._ordered_plan_steps(action)
        steps = self._compile_action_plan_steps(original_steps, plan_id)
        available = float(self.state.meta.get("available_time_minutes", 720))
        provisional, provisional_errors = self._simulate_plan_steps(steps, 1.0)
        factors = self._plan_factors(provisional, available, provisional_errors)
        combinability = calculate_combinability(factors)
        partial = False
        selected_steps = steps
        if combinability < 20:
            if not action.get("priority_order"):
                provisional_errors.append("可组合度低于20，必须提供 priority_order 并明确只执行一个步骤")
            else:
                selected_source = str(original_steps[0]["action_id"])
                selected_steps = [step for step in steps if str(step.get("_source_action_id", step["action_id"])) == selected_source]
                partial = True
        elif combinability < 50:
            if not action.get("priority_order"):
                provisional_errors.append("可组合度为20-49，必须提供 priority_order 并只执行部分步骤")
            else:
                selected_source = str(original_steps[0]["action_id"])
                selected_steps = [step for step in steps if str(step.get("_source_action_id", step["action_id"])) == selected_source]
                partial = True
        elif combinability < 80 and not bool(action.get("accept_dilution")):
            provisional_errors.append("可组合度为50-79，必须明确 accept_dilution=true 才能执行")
        major_count = sum(1 for item in provisional if float(item["preview"].get("action_ledger", {}).get("actions", [{}])[0].get("time_minutes", 0)) >= 60)
        dilution_multiplier = 1.0 if partial or combinability >= 80 else 0.55 if major_count >= 3 else 0.75
        previews, errors = self._simulate_plan_steps(selected_steps, dilution_multiplier)
        used_time = sum(float(item["preview"].get("action_ledger", {}).get("actions", [{}])[0].get("time_minutes", 0)) for item in previews)
        used_stamina = sum(float(item["preview"].get("action_ledger", {}).get("actions", [{}])[0].get("stamina_cost", 0)) for item in previews)
        used_mental = sum(float(item["preview"].get("action_ledger", {}).get("actions", [{}])[0].get("mental_cost", 0)) for item in previews)
        if used_time > available:
            errors.append("计划总时间超过当前行动窗口")
        if used_stamina + float(self.state.player.get("fatigue", 0)) > 100:
            errors.append("计划总消耗超过体力")
        if float(self.state.player.get("mental", 100)) - used_mental < 0:
            errors.append("计划总消耗超过精神")
        if not partial:
            errors.extend(provisional_errors)
        return {
            "legal": not errors,
            "errors": errors,
            "plan_id": plan_id,
            "combinability": combinability,
            "components": factors,
            "dilution_multiplier": dilution_multiplier,
            "partial": partial,
            "deferred_steps": [
                str(step["action_id"])
                for step in original_steps
                if str(step["action_id"]) not in {str(item.get("_source_action_id", item["action_id"])) for item in selected_steps}
            ],
            "action_ledger": {"available_time_minutes": available, "available_stamina": max(0.0, 100.0 - float(self.state.player.get("fatigue", 0))), "available_mental": float(self.state.player.get("mental", 100)), "actions": [item["preview"].get("action_ledger", {}).get("actions", [{}])[0] for item in previews]},
            "steps": previews,
        }

    def execute_action_plan(self, action: Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        preview = self.preview_action_plan(action)
        if not preview["legal"]:
            raise ValueError("行动计划不合法：" + "、".join(preview["errors"]))
        before = deepcopy(self.state.data)
        self.state.clear_pending()
        results = []
        try:
            for item in preview["steps"]:
                results.append(self.execute_host_action(item["action"], persist=False, dilution_multiplier=float(preview.get("dilution_multiplier", 1.0))))
            if persist:
                self.state.commit_pending()
                self.state.save()
            else:
                self.state.clear_pending()
        except Exception:
            self.state.data = before
            self.state.clear_pending()
            raise
        return {"plan_id": preview["plan_id"], "combinability": preview["combinability"], "events": [item["event"] for item in results], "results": results, "state": self.state.data}

    def preview_action(self, action: Mapping[str, Any], dilution_multiplier: float = 1.0) -> Dict[str, Any]:
        validate_host_action(action)
        if str(action.get("type")) == "ATTRIBUTE_ALLOCATION":
            return self.preview_attribute_allocation(action)
        skill = self._find_skill(action)
        costs = self._derive_action_costs(action, skill)
        movement_types = {"TRAVEL", "ENTER_LOCATION", "RETURN_TO_BASE", "EXTRACT", "LEAVE_ENCOUNTER"}
        if str(action.get("type")) == "WAIT":
            resolution = {
                "formula_version": "1.0",
                "action_type": "WAIT",
                "outcome": "普通成功",
                "probability": 1.0,
                "risk_mode": "deterministic_wait",
                "time_cost": float(costs.get("time_minutes", 0.0)),
                "wait_minutes": float(costs.get("time_minutes", 0.0)),
            }
        elif str(action.get("type")) in movement_types:
            resolution = self._deterministic_movement_resolution(action, costs)
        else:
            context = self._build_action_context(action, costs)
            resolution = resolve_action(self.state.player, context, self.state.inventory)
            apply_action_dilution(resolution, dilution_multiplier)
        available_time = float(self.state.meta.get("available_time_minutes", 240))
        time_cost = float(costs["time_minutes"])
        stamina_cost = float(costs["stamina_cost"])
        mental_cost = float(costs["mental_cost"])
        legal_errors = self._check_requirements(action)
        if str(action.get("type")) != "REACTION" and time_cost > available_time:
            legal_errors.append("时间不足")
        if float(self.state.player.get("fatigue", 0)) + stamina_cost > 100:
            legal_errors.append("体力不足")
        if float(self.state.player.get("mental", 100)) - mental_cost < 0:
            legal_errors.append("精神不足")
        for resource, amount in skill_cost(skill).items() if skill else {}.items():
            if resource in {"stamina", "mental"}:
                continue
            current = float(self.state.inventory.get("resources", {}).get(resource, 0))
            if current < float(amount):
                legal_errors.append(f"资源不足：{resource}")
        action_tags = list(action.get("tags", [])) if isinstance(action.get("tags", []), list) else []
        if str(action.get("type")) in {"EXPLORATION", "COMBAT", "BATCH_ACTION", "BUILD", "RESEARCH", "REST"} and "major_action" not in action_tags:
            action_tags.append("major_action")
        if str(action.get("type")) in {"EXPLORATION", "COMBAT", "BUILD", "RESEARCH"} and "requires_full_attention" not in action_tags:
            action_tags.append("requires_full_attention")
        if str(action.get("type")) == "REACTION" and "immediate_reaction" not in action_tags:
            action_tags.append("immediate_reaction")
        return {
            "legal": not legal_errors,
            "errors": legal_errors,
            "resolution": resolution if isinstance(resolution, Mapping) else resolution.to_dict(),
            "target_profile": deepcopy(dict(self._action_target_profile(action))),
            "system_constraints": self._system_action_constraints(action, {"target_profile": self._action_target_profile(action)}),
            "action_ledger": {
                "available_time_minutes": available_time,
                "available_stamina": max(0.0, 100.0 - float(self.state.player.get("fatigue", 0))),
                "available_mental": float(self.state.player.get("mental", 100)),
                "actions": [{
                    "type": str(action.get("type", "GENERAL_ACTION")),
                    "target": action.get("target"),
                    "time_minutes": time_cost,
                    "stamina_cost": stamina_cost,
                    "mental_cost": mental_cost,
                    "tags": action_tags,
                }],
            },
            "skill": skill,
        }

    @staticmethod
    def _option_label(candidate: Mapping[str, Any], option_id: str) -> str:
        return str(candidate.get("label") or candidate.get("title") or candidate.get("name") or f"方案{option_id}")

    def _option_has_real_effect(self, action: Mapping[str, Any], preview: Mapping[str, Any]) -> bool:
        if not preview.get("legal"):
            return False
        action_type = str(action.get("type"))
        resolution = preview.get("resolution", {}) if isinstance(preview.get("resolution", {}), Mapping) else {}
        if action_type == "ACTION_PLAN":
            return any(
                self._option_has_real_effect(item.get("action", {}), item.get("preview", {}))
                for item in preview.get("steps", []) if isinstance(item, Mapping)
            )
        if action_type in {"TRAVEL", "ENTER_LOCATION", "RETURN_TO_BASE", "EXTRACT", "LEAVE_ENCOUNTER"}:
            return bool(resolution.get("movement_success"))
        if action_type == "ATTRIBUTE_ALLOCATION":
            return int(resolution.get("points_spent", 0) or 0) > 0
        if action_type in {"REST", "REACTION", "TALENT_CHOICE", "WAIT"}:
            return True
        if action_type == "BUILD":
            return bool(resolution.get("resource_changes") or resolution.get("space_cost") or resolution.get("module"))
        if action_type == "COMBAT":
            return any(float(resolution.get(key, 0) or 0) != 0 for key in ("damage", "incoming_damage", "ammo_consumed", "durability_cost"))
        if action_type == "BATCH_ACTION":
            return any(float(resolution.get(key, 0) or 0) != 0 for key in ("total_kills", "total_experience", "ammo_consumed", "durability_cost")) or bool(resolution.get("recovered_resources"))
        # 若目标注册表对任何结果分支定义了效果，则该行动潜在有实际效果，
        # 不应因本次预览随机落在空分支上而被过滤。
        profile = self._action_target_profile(action)
        profile_effects = profile.get("effects", {}) if isinstance(profile.get("effects", {}), Mapping) else {}
        if any(profile_effects.get(branch) for branch in ("success", "partial_failure", "failure")):
            return True
        try:
            effects = self._domain_effects(action, resolution)
        except (TypeError, ValueError):
            return False
        ignored = {"event_type", "proposed_events", "effect_multiplier"}
        return any(key not in ignored and value not in (None, 0, 0.0, "", [], {}, False) for key, value in effects.items())

    def compile_options(self, candidates: list[Mapping[str, Any]], *, persist: bool = True) -> Dict[str, Any]:
        """将主持器候选编译为已预验证、可直接执行的行动契约。"""
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("选项候选不能为空")
        compiled: Dict[str, Any] = {}
        ordinary_types = {"TRAVEL", "ENTER_LOCATION", "RETURN_TO_BASE", "EXTRACT", "LEAVE_ENCOUNTER", "EXPLORATION", "RESEARCH", "BUILD", "COMBAT", "BATCH_ACTION", "SOCIAL_INTERACTION", "SHORT_ACTION", "REST", "BASE_MANAGEMENT", "WAIT"}
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, Mapping):
                continue
            option_id = str(candidate.get("id") or candidate.get("option_id") or chr(65 + index)).strip().upper()
            raw_action = candidate.get("action") or candidate.get("contract")
            if not isinstance(raw_action, Mapping):
                raw_action = {key: deepcopy(value) for key, value in candidate.items() if key in {"action_id", "type", "target", "primary_attribute", "skill_id", "requirements", "risk_preference", "tags", "goal", "approach", "parameters", "stop_conditions", "plan_id", "steps", "priority_order", "accept_dilution"}}
            action = deepcopy(dict(raw_action))
            if not action.get("action_id"):
                action["action_id"] = f"option-{self.state.current_turn + 1}-{option_id}"
            # 选项可以只描述“去某地调查”；若当前位置不符，编译器把它
            # 固化为含自动移动步骤的 ACTION_PLAN，避免把空间规则交给LLM。
            required_location = self._required_action_location(action)
            if (
                required_location
                and required_location != self._current_location()
                and str(action.get("type")) not in {"ACTION_PLAN", "TRAVEL", "ENTER_LOCATION", "RETURN_TO_BASE", "EXTRACT", "LEAVE_ENCOUNTER"}
            ):
                action = {
                    "action_id": f"{action['action_id']}-compiled-plan",
                    "type": "ACTION_PLAN",
                    "plan_id": f"{action['action_id']}-compiled-plan",
                    "accept_dilution": True,
                    "steps": [action],
                }
            try:
                preview = self.preview_host_action(action)
            except (TypeError, ValueError):
                continue
            # ── 硬门槛：preview.legal 必须为 True 才可进入候选 ──
            # 时段(allowed_periods)、地点、物品、等级等所有前置校验
            # 都在 preview_host_action 内完成；不合法则直接丢弃。
            if not preview.get("legal", False):
                continue
            action_type = str(action.get("type"))
            if float(self.state.meta.get("available_time_minutes", 240)) <= 0 and action_type in ordinary_types:
                continue
            if not self._option_has_real_effect(action, preview):
                continue
            compiled[option_id] = {
                "id": option_id,
                "label": self._option_label(candidate, option_id),
                "description": str(candidate.get("description") or candidate.get("summary") or action.get("goal") or ""),
                "action": action,
                "preview": deepcopy(preview),
                "state_turn": self.state.current_turn,
            }
        # 两个选项如果产生完全相同的路线/结果，就不是两个真正的选择。
        distinct: Dict[str, Any] = {}
        fingerprints = set()
        for option_id, item in compiled.items():
            action = item["action"]
            preview = item["preview"]
            resolution = preview.get("resolution", {}) if isinstance(preview.get("resolution", {}), Mapping) else {}
            if str(action.get("type")) == "ACTION_PLAN":
                fingerprint = repr([
                    (step.get("action", {}).get("type"), step.get("action", {}).get("target"), step.get("preview", {}).get("resolution", {}).get("outcome"), step.get("preview", {}).get("resolution", {}).get("resource_changes"))
                    for step in preview.get("steps", []) if isinstance(step, Mapping)
                ])
            else:
                fingerprint = repr((action.get("type"), action.get("target"), resolution.get("outcome"), resolution.get("movement_success"), resolution.get("total_kills"), resolution.get("damage"), resolution.get("resource_changes"), resolution.get("knowledge_additions"), resolution.get("current_location"), resolution.get("allocations")))
            if fingerprint in fingerprints:
                continue
            fingerprints.add(fingerprint)
            distinct[option_id] = item
        compiled = distinct
        if not compiled:
            raise ValueError("没有可展示的合法且有实际状态效果的选项")
        pending = {"version": 1, "state_turn": self.state.current_turn, "options": compiled}
        if persist:
            event = standard_event(
                event_id=f"evt_{self.state.current_turn:04d}_options_{uuid4().hex[:8]}",
                event_type="OPTIONS_PRESENTED",
                actor="system",
                target=None,
                data={"pending_options": pending, "state_turn": self.state.current_turn},
                turn=self.state.current_turn,
                timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
            )
            self.state.apply_and_append(event, persist=True)
            self.state.save()
        else:
            self.state.meta["pending_options"] = pending
            self.state.meta["pending_options_state_turn"] = self.state.current_turn
        return {"state_turn": self.state.current_turn, "options": {key: {field: value for field, value in item.items() if field in {"id", "label", "description"}} for key, item in compiled.items()}, "contracts": compiled}

    def preview_player_choice(self, option_id: str | Mapping[str, Any]) -> Dict[str, Any]:
        if isinstance(option_id, Mapping):
            option_id = option_id.get("option_id") or option_id.get("id") or ""
        pending = self.state.meta.get("pending_options", {})
        pending = pending if isinstance(pending, Mapping) else {}
        options = pending.get("options", {}) if isinstance(pending.get("options", {}), Mapping) else {}
        raw_key = str(option_id).strip()
        key = raw_key.upper()
        selected = options.get(key) or options.get(raw_key)
        errors: list[str] = []
        if not selected:
            errors.append(f"不存在待执行选项：{option_id}")
        if pending.get("state_turn") is not None and int(pending.get("state_turn")) != self.state.current_turn:
            errors.append("选项对应的世界状态已经变化，必须重新生成选项")
        action = deepcopy(selected.get("action", {})) if isinstance(selected, Mapping) else {}
        preview: Dict[str, Any] = {}
        if selected and isinstance(action, Mapping):
            try:
                preview = self.preview_host_action(action)
            except (TypeError, ValueError) as exc:
                errors.append(str(exc))
            if preview and not preview.get("legal"):
                errors.extend(str(item) for item in preview.get("errors", []))
            if preview and not self._option_has_real_effect(action, preview):
                errors.append("选项已经不再产生实际状态变化")
        return {"legal": not errors, "errors": errors, "option_id": key, "action": action, "preview": preview, "stored_option": deepcopy(selected) if isinstance(selected, Mapping) else None}

    def execute_player_choice(self, option_id: str | Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        """玩家选择即授权：读取已保存契约并在同一调用内完成预览与提交。"""
        review = self.preview_player_choice(option_id)
        if not review["legal"]:
            raise ValueError("选项不可执行：" + "、".join(review["errors"]))
        result = self.execute_host_action(review["action"], persist=persist)
        result["selected_option"] = review["option_id"]
        return result

    def generate_candidates(self) -> list[Dict[str, Any]]:
        """从世界注册表自动生成当前状态下合理的候选行动列表。"""
        candidates: list[Dict[str, Any]] = []
        current_location = self._current_location()
        base_location = self._base_location()
        world = self.state.data.get("world", {}) if isinstance(self.state.data.get("world", {}), Mapping) else {}
        action_targets = world.get("action_targets", {}) if isinstance(world.get("action_targets", {}), Mapping) else {}
        index = 0
        for target_id, profile in action_targets.items():
            if not isinstance(profile, Mapping):
                continue
            location_id = str(profile.get("location_id", ""))
            if location_id != current_location:
                continue
            constraints = profile.get("constraints", {}) if isinstance(profile.get("constraints", {}), Mapping) else {}
            availability = constraints.get("availability", {}) if isinstance(constraints.get("availability", {}), Mapping) else {}
            allowed_periods = availability.get("allowed_periods", [])
            time_of_day = str(self.state.meta.get("time_of_day", "清晨"))
            if allowed_periods and time_of_day not in {str(p) for p in allowed_periods}:
                continue
            target_type = str(profile.get("action_type", "EXPLORATION"))
            index += 1
            candidates.append({
                "id": chr(64 + index),
                "label": str(profile.get("label") or profile.get("name") or target_id),
                "action": {"action_id": f"auto-{target_id}", "type": target_type, "target": target_id, "goal": str(profile.get("goal") or profile.get("label") or f"调查{target_id}")},
            })
        if current_location != base_location:
            index += 1
            candidates.append({
                "id": chr(64 + index),
                "label": "返回基地",
                "action": {"action_id": "auto-return", "type": "RETURN_TO_BASE"},
            })
        if current_location == base_location:
            index += 1
            candidates.append({
                "id": chr(64 + index),
                "label": "休息恢复",
                "action": {"action_id": "auto-rest", "type": "REST", "target": base_location},
            })
        locations = world.get("locations", []) if isinstance(world.get("locations", []), list) else []
        for loc in locations:
            if not isinstance(loc, Mapping):
                continue
            loc_id = str(loc.get("id", ""))
            if loc_id == current_location or not loc_id:
                continue
            if loc.get("safe") and loc_id == base_location:
                continue
            index += 1
            candidates.append({
                "id": chr(64 + index) if index <= 26 else f"X{index}",
                "label": f"前往{loc.get('name', loc_id)}",
                "action": {"action_id": f"auto-travel-{loc_id}", "type": "TRAVEL", "target": loc_id},
            })
            if index >= 8:
                break
        
        # Inject exclusive_actions from current profession
        from collections.abc import Mapping
        
        current_profession_id = self.state.player.get("profession")
        world_professions = world.get("professions", {}) if isinstance(world.get("professions", {}), Mapping) else {}
        
        exclusive_actions_list = world_professions.get(current_profession_id, {}).get("exclusive_actions", [])
        for excl_act in exclusive_actions_list:
            if not isinstance(excl_act, Mapping):
                continue
            
            # Get location requirement
            target_id = excl_act.get("target_id") or excl_act.get("target") or excl_act.get("action_type")
            location_id = excl_act.get("location_id")
            
            # Skip if no location match
            if location_id and location_id != current_location:
                continue
            
            # If no explicit location_id, check if action has required locations and skip if not current
            # Otherwise assume it's available at current location
            candidates.append({
                "id": f"excl-{index}",
                "label": excl_act.get("name") or excl_act.get("action_type"),
                "action": {
                    "action_id": f"excl-{excl_act['action_type']}",
                    "type": excl_act.get("action_type"),
                    "target": target_id,
                    "goal": excl_act.get("goal") or excl_act.get("action_type"),
                },
                "category": "professional_skill",
            })
            index += 1
        
        return candidates

    def execute_action(self, action: Mapping[str, Any], persist: bool = True, dilution_multiplier: float = 1.0) -> Dict[str, Any]:
        preview = self.preview_action(action, dilution_multiplier=dilution_multiplier)
        if not preview["legal"]:
            raise ValueError("行动不合法：" + "、".join(preview["errors"]))
        turn = self.state.current_turn + 1
        timestamp = f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}"
        ledger_action = preview["action_ledger"]["actions"][0]
        resource_costs = {}
        cooldown_changes = {}
        if preview.get("skill"):
            skill = preview["skill"]
            for resource, amount in skill_cost(skill).items():
                if resource not in {"stamina", "mental"}:
                    resource_costs[resource] = resource_costs.get(resource, 0.0) + amount
            cooldown_changes[skill.get("id", "skill")] = int(skill.get("cooldown", 0))
        payload = {
            "action": {key: action[key] for key in ("action_id", "type", "target", "primary_attribute") if key in action},
            "action_ledger": preview["action_ledger"],
            "system_constraints": preview.get("system_constraints", {}),
            "resolution": preview["resolution"],
            "fatigue_delta": float(ledger_action.get("stamina_cost", 0)),
            "mental_delta": -float(ledger_action.get("mental_cost", 0)),
            "time_cost": float(ledger_action.get("time_minutes", 0)),
            "hunger_delta": 0.0,
            "resource_changes": {key: -float(value) for key, value in resource_costs.items()},
        }
        domain_effects = self._domain_effects(action, preview["resolution"], dilution_multiplier=dilution_multiplier)
        event_type = domain_effects.pop("event_type", "ACTION_RESOLVED")
        domain_resource_changes = domain_effects.pop("resource_changes", {})
        if isinstance(domain_resource_changes, Mapping):
            for resource, delta in domain_resource_changes.items():
                payload["resource_changes"][str(resource)] = (
                    float(payload["resource_changes"].get(str(resource), 0.0))
                    + float(delta)
                )
        payload.update(domain_effects)
        payload["action"] = {key: action[key] for key in ("action_id", "type", "target") if key in action}
        narrative_decision = self._narrative_decision(action, preview)
        payload["runtime_metrics"] = calculate_narrative_metrics(
            self.state.data,
            [item["record"] for item in self.state.event_history()],
            payoff=self._narrative_payoff(action, preview["resolution"]),
            decision=narrative_decision,
        )
        payload["narrative_inputs"] = {"decision": narrative_decision, "payoff": self._narrative_payoff(action, preview["resolution"])}
        if cooldown_changes:
            payload["cooldown_changes"] = cooldown_changes
        event = standard_event(
            event_id=f"evt_{turn:04d}_001",
            event_type=event_type,
            actor="player",
            target=action.get("target"),
            data=payload,
            turn=turn,
            timestamp=timestamp,
        )
        self.state.apply_and_append(event, persist=persist)
        metrics = payload.get("runtime_metrics", {})
        self.state.meta["rng_seed"] = str(self.state.meta.get("rng_seed") or self.state.meta.get("world_name", "world"))
        if persist:
            self.state.save()
        return {"event": event, "resolution": preview["resolution"], "metrics": metrics, "state": self.state.data}

    def execute_host_action(self, action: Mapping[str, Any], persist: bool = True, dilution_multiplier: float = 1.0) -> Dict[str, Any]:
        """执行唯一允许由 LLM 主持器调用的入口。"""
        validate_host_action(action)
        action_type = str(action.get("type"))
        if (self.state.meta.get("campaign_status") == "ended" or self.state.player.get("status") == "dead") and action_type not in {"ENDING", "RESTART", "CHECKPOINT", "LEGACY_CREATE"}:
            raise ValueError("本局已经结束，只允许查看结局、重开、检查点或创建传承角色")
        if action_type in {"ENDING", "RESTART", "CHECKPOINT", "LEGACY_CREATE"}:
            return self._execute_terminal_action(action, persist=persist)
        if action_type == "ACTION_PLAN":
            return self.execute_action_plan(action, persist=persist)
        if action_type == "TALENT_CHOICE":
            return self.execute_talent_choice(action, persist=persist)
        if action_type == "ATTRIBUTE_ALLOCATION":
            return self.execute_attribute_allocation(action, persist=persist)
        # 自由行动和已绑定选项都必须先经过一次不写入的内部审查；审查通过
        # 后本调用立即提交，不把“确认”再暴露给玩家。
        review = self.preview_host_action(action, dilution_multiplier=dilution_multiplier)
        if not review.get("legal"):
            raise ValueError("行动不合法：" + "、".join(str(item) for item in review.get("errors", [])))
        skill = self._find_skill(action)
        costs = self._derive_action_costs(action, skill)
        errors = self._derived_budget_errors(action, costs)
        if errors:
            raise ValueError("行动不合法：" + "、".join(errors))
        action_type = str(action.get("type"))
        if action_type == "COMBAT":
            target = self._lookup_target(action.get("target"))
            return self.execute_combat(
                target,
                weapon=self._combat_weapon(),
                skill=skill,
                environment=self._combat_environment(target, costs),
                seed=self._host_seed(action),
                persist=persist,
                dilution_multiplier=dilution_multiplier,
            )
        if action_type == "BUILD":
            module = self._lookup_module(action.get("target"))
            available_minutes = min(float(self.state.meta.get("available_time_minutes", 240)), float(costs["time_minutes"]))
            return self.execute_build(module, available_minutes, action_costs=costs, persist=persist, dilution_multiplier=dilution_multiplier)
        if action_type == "BATCH_ACTION":
            area = self._lookup_area(action.get("target"))
            return self.execute_batch_action(self._batch_internal_action(action, area, costs), persist=persist, dilution_multiplier=dilution_multiplier)
        return self.execute_action(action, persist=persist, dilution_multiplier=dilution_multiplier)

    def _talent_choice_id(self, action: Mapping[str, Any]) -> str:
        parameters = action.get("parameters", {}) if isinstance(action.get("parameters", {}), Mapping) else {}
        return str(action.get("target") or parameters.get("option_id") or "")

    def preview_talent_choice(self, action: Mapping[str, Any]) -> Dict[str, Any]:
        pending = self.state.player.get("pending_decision", {}) if isinstance(self.state.player.get("pending_decision", {}), Mapping) else {}
        option_id = self._talent_choice_id(action)
        options = pending.get("options", []) if isinstance(pending, Mapping) else []
        selected = next((option for option in options if isinstance(option, Mapping) and str(option.get("id")) == option_id), None)
        errors = []
        if not pending or pending.get("type") != "TALENT_CHOICE":
            errors.append("当前没有待处理的升级选择")
        if selected is None:
            errors.append("所选天赋不在 Python 生成的候选列表中")
        return {"legal": not errors, "errors": errors, "resolution": {"options": deepcopy(options), "selected": deepcopy(selected)}, "action_ledger": {"available_time_minutes": float(self.state.meta.get("available_time_minutes", 720)), "actions": [{"type": "TALENT_CHOICE", "target": option_id, "time_minutes": 0.0, "stamina_cost": 0.0, "mental_cost": 0.0, "tags": ["mandatory_progression"]}]}}

    def execute_talent_choice(self, action: Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        preview = self.preview_talent_choice(action)
        if not preview["legal"]:
            raise ValueError("天赋选择不合法：" + "、".join(preview["errors"]))
        selected = preview["resolution"]["selected"]
        turn = self.state.current_turn + 1
        event = standard_event(
            event_id=f"evt_{turn:04d}_001",
            event_type="TALENT_CHOSEN",
            actor="player",
            target=selected.get("id"),
            data={"action": {"action_id": action.get("action_id"), "type": "TALENT_CHOICE", "target": selected.get("id")}, "talent_choice": selected, "proposed_events": [{"type": "TALENT_CHOSEN", "target": selected.get("id")}], "time_cost": 0.0},
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        self.state.apply_and_append(event, persist=persist)
        if persist:
            self.state.save()
        return {"event": event, "resolution": preview["resolution"], "state": self.state.data}

    def _terminal_resolution(self, action: Mapping[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type"))
        if self.state.meta.get("campaign_status") != "ended" and self.state.player.get("status") != "dead" and action_type != "ENDING":
            raise ValueError("只有本局结束后才能执行终局处理")
        return {
            "action_type": action_type,
            "campaign_status": self.state.meta.get("campaign_status", "active"),
            "ending_id": self.state.meta.get("ending_id"),
            "summary": deepcopy(self.state.meta.get("ending_summary", {})),
            "next_step": "需要由主持器创建新角色或传承存档" if action_type != "ENDING" else "仅查看结局",
        }

    def _execute_terminal_action(self, action: Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        action_type = str(action.get("type"))
        terminal = self._terminal_resolution(action)
        if action_type in {"ENDING", "CHECKPOINT", "LEGACY_CREATE"}:
            if action_type == "CHECKPOINT":
                terminal["checkpoint_available"] = self.state.store.snapshot_before(self.state.current_turn) is not None
            if action_type == "LEGACY_CREATE":
                terminal["inheritance_source"] = deepcopy(self.state.data)
            return {"terminal": terminal, "state": self.state.data}
        if self.state.meta.get("death_mode", "checkpoint") != "checkpoint":
            raise ValueError("当前死亡模式不允许检查点重来")
        checkpoints_used = int(self.state.meta.get("checkpoints_used", 0))
        max_checkpoints = int(self.state.meta.get("max_checkpoints", 0))
        if checkpoints_used >= max_checkpoints:
            raise ValueError("本篇章的检查点次数已用尽")
        restored = self.state.store.snapshot_before(self.state.current_turn)
        if restored is None:
            raise ValueError("没有可用的死亡前检查点")
        turn = self.state.current_turn + 1
        event = standard_event(
            event_id=f"evt_{turn:04d}_restart",
            event_type="CAMPAIGN_RESTARTED",
            actor="player",
            target="checkpoint",
            data={"state_restore": restored, "checkpoint_turn": restored.get("meta", {}).get("current_turn", 0), "checkpoint_increment": 1, "time_cost": 0.0},
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        self.state.apply_and_append(event, persist=persist)
        if persist:
            self.state.save()
        return {"event": event, "terminal": {"action_type": action_type, "checkpoint_turn": event["data"]["checkpoint_turn"]}, "state": self.state.data}

    def execute_combat(self, defender: Mapping[str, Any], weapon: Optional[Mapping[str, Any]] = None, skill: Optional[Mapping[str, Any]] = None, environment: Optional[Mapping[str, Any]] = None, seed: str = "", persist: bool = True, dilution_multiplier: float = 1.0) -> Dict[str, Any]:
        if defender.get("status") in {"dead", "destroyed"}:
            raise ValueError("战斗目标已经死亡")
        if self.state.meta.get("campaign_status") == "ended":
            raise ValueError("本局已经结束")
        target_id = defender.get("id", defender.get("name"))
        if not self._active_encounter_allows(target_id):
            raise ValueError("没有与该目标绑定的当前遭遇：必须先进入对应地点并加入遭遇")
        weapon = weapon or self._combat_weapon()
        if skill:
            skill_errors = check_skill_use(skill, self.state.player, self.state.inventory)
            if skill_errors:
                raise ValueError("技能不可用：" + "、".join(skill_errors))
        resolution = calculate_combat(self.state.player, defender, weapon=weapon, skill=skill, environment=environment, seed=seed or str(self.state.meta.get("rng_seed", "combat")), dilution_multiplier=dilution_multiplier)
        if not resolution.ammo_sufficient:
            raise ValueError("弹药不足")
        if weapon.get("durability") is not None and float(weapon.get("durability", 0)) <= 0:
            raise ValueError("武器耐久归零")
        turn = self.state.current_turn + 1
        skill_costs = skill_cost(skill) if skill else {}
        stamina_cost = number_for_runtime((environment or {}).get("stamina_cost", 10)) + skill_costs.get("stamina", 0)
        mental_cost = number_for_runtime((environment or {}).get("mental_cost", 0)) + skill_costs.get("mental", 0)
        resource_changes = {key: -value for key, value in skill_costs.items() if key not in {"stamina", "mental"}}
        ammo_resource = weapon.get("ammo_resource")
        if ammo_resource and resolution.ammo_consumed:
            resource_changes[str(ammo_resource)] = resource_changes.get(str(ammo_resource), 0.0) - resolution.ammo_consumed
        equipment_updates = {}
        if "ammo_available" in weapon and not weapon.get("_ammo_from_resource"):
            equipment_updates["main_weapon"] = {"ammo_available": max(0.0, float(weapon.get("ammo_available", 0)) - resolution.ammo_consumed)}
        cooldown_changes = {skill.get("id", "skill"): int(skill.get("cooldown", 0))} if skill else {}
        target_hp_before = max(1.0, number_for_runtime(defender.get("hp", number_for_runtime(defender.get("constitution", 3)) * 10.0)))
        target_hp_after = max(0.0, target_hp_before - float(resolution.damage))
        target_died = target_hp_after <= 0
        player_hp_before = number_for_runtime(self.state.player.get("hp", self.state.player.get("max_hp", 50)))
        incoming_damage = 0.0 if target_died else float(resolution.incoming_damage)
        player_hp_after = max(0.0, player_hp_before - incoming_damage)
        player_died = player_hp_after <= 0
        target_deltas = {str(target_id): {"hp": -float(resolution.damage)}} if target_id is not None and resolution.damage else {}
        experience_gain = 0.0
        if target_died:
            experience_gain = calculate_experience(int(self.state.player.get("level", 1)), int(number_for_runtime(defender.get("level", 1))), str(defender.get("quality", "普通")))
            for resource, quantity in (defender.get("drops", {}) or {}).items():
                resource_changes[str(resource)] = resource_changes.get(str(resource), 0.0) + float(quantity)
        proposed_events = [{"type": "DAMAGE_DEALT", "target": target_id, "quantity": resolution.damage}]
        if incoming_damage:
            proposed_events.append({"type": "DAMAGE_RECEIVED", "target": "player", "quantity": incoming_damage})
        if target_died:
            proposed_events.extend([{"type": "CHARACTER_DIED", "target": target_id}, {"type": "COMBAT_ENDED", "target": target_id}, {"type": "LOOT_GENERATED", "target": target_id}])
        if player_died:
            proposed_events.append({"type": "CHARACTER_DIED", "target": "player"})
        encounter_updates = []
        current_encounter_id = self.state.meta.get("current_encounter_id")
        if current_encounter_id:
            encounter = next((item for item in self.state.meta.get("active_encounters", []) if isinstance(item, Mapping) and item.get("id") == current_encounter_id), None)
            if isinstance(encounter, Mapping):
                remaining_targets = [item for item in encounter.get("target_ids", []) if not target_died or item != target_id]
                remaining_participants = [item for item in encounter.get("participants", []) if not target_died or item != target_id]
                encounter_updates.append({"id": current_encounter_id, "target_ids": remaining_targets, "participants": remaining_participants, "status": "resolved" if target_died and not remaining_targets else "active", "resolved_turn": turn if target_died and not remaining_targets else None})
                if player_died:
                    encounter_updates[-1]["status"] = "escaped"
        if any(update.get("status") == "resolved" for update in encounter_updates):
            proposed_events.append({"type": "ENCOUNTER_RESOLVED", "target": current_encounter_id})
        elif any(update.get("status") == "escaped" for update in encounter_updates):
            proposed_events.append({"type": "ENCOUNTER_ESCAPED", "target": current_encounter_id})
        event = standard_event(
            event_id=f"evt_{turn:04d}_001",
            event_type="COMBAT_RESOLVED",
            actor="player",
            target=target_id,
            data={
                "resolution": resolution.to_dict(),
                "action_ledger": {"available_time_minutes": (environment or {}).get("available_time_minutes", 30), "available_stamina": max(0.0, 100.0 - float(self.state.player.get("fatigue", 0))), "available_mental": float(self.state.player.get("mental", 100)), "actions": [{"type": "COMBAT", "target": defender.get("id", defender.get("name")), "time_minutes": (environment or {}).get("time_minutes", 30), "stamina_cost": stamina_cost, "mental_cost": mental_cost, "tags": ["combat"]}]},
                "fatigue_delta": stamina_cost,
                "mental_delta": -mental_cost,
                "time_cost": float((environment or {}).get("time_minutes", 30)),
                "resource_changes": resource_changes,
                "equipment_durability": {"main_weapon": resolution.weapon_durability_after} if resolution.weapon_durability_after is not None else {},
                "equipment_updates": equipment_updates,
                "target_deltas": target_deltas,
                "target_died": target_died,
                "player_died": player_died,
                "death_reason": f"与 {target_id} 的战斗中生命归零" if player_died else None,
                "player_delta": {"hp": -incoming_damage},
                "experience_gain": experience_gain,
                "proposed_events": proposed_events,
                "encounter_updates": encounter_updates,
                "combat_instance": {"id": f"combat_{turn:04d}", "participants": ["player", target_id], "round": 1, "status": "ended" if target_died or player_died else "active", "escape_allowed": True},
            },
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        if cooldown_changes:
            event["data"]["cooldown_changes"] = cooldown_changes
        self.state.apply_and_append(event, persist=persist)
        if persist:
            self.state.save()
        return {"event": event, "resolution": resolution.to_dict(), "state": self.state.data}

    def execute_batch_action(self, action: Mapping[str, Any], persist: bool = True, dilution_multiplier: float = 1.0) -> Dict[str, Any]:
        area = action.get("area", {}) if isinstance(action.get("area", {}), Mapping) else {}
        area_location = area.get("location_id", action.get("target"))
        if area_location and str(area_location) != self._current_location():
            raise ValueError(f"刷怪区域不在当前地点：需要先进入 {area_location}")
        dilution_multiplier = max(0.25, min(1.0, float(dilution_multiplier)))
        result = simulate_batch_action(
            area=action.get("area", {}),
            player_level=int(self.state.player.get("level", 1)),
            minutes=float(action.get("minutes", 0)),
            kill_success_rate=float(action.get("kill_success_rate", 0)) * dilution_multiplier,
            ammo_available=float(action.get("ammo_available", 0)),
            ammo_per_kill=float(action.get("ammo_per_kill", 1)),
            weapon_rate_per_hour=float(action.get("weapon_rate_per_hour", 0)),
            recovery_efficiency=float(action.get("recovery_efficiency", 1)) * dilution_multiplier,
            backpack_capacity_modifier=float(action.get("backpack_capacity_modifier", 1)),
            enemy_groups=action.get("enemy_groups", []),
            farmability_components=action.get("farmability_components", {}),
            stop_conditions=action.get("stop_conditions", {}),
        )
        result.components["dilution_multiplier"] = dilution_multiplier
        turn = self.state.current_turn + 1
        resource_changes = dict(result.recovered_resources)
        ammo_resource = action.get("ammo_resource")
        if ammo_resource:
            resource_changes[ammo_resource] = resource_changes.get(ammo_resource, 0) - result.ammo_consumed
        equipment_durability = {}
        main_weapon = self.state.inventory.get("equipment", {}).get("main_weapon") if isinstance(self.state.inventory.get("equipment", {}), Mapping) else None
        if isinstance(main_weapon, Mapping) and main_weapon.get("durability") is not None:
            equipment_durability["main_weapon"] = max(0.0, float(main_weapon.get("durability", 0)) - float(result.durability_cost))
        proposed_events = [{"type": "BATCH_KILLS", "target": action.get("target"), "quantity": result.total_kills}]
        proposed_events.extend({"type": "BATCH_INTERRUPTED", "target": action.get("target"), "reason": reason} for reason in result.interruption_reasons)
        area = action.get("area", {}) if isinstance(action.get("area", {}), Mapping) else {}
        area_deltas = {
            str(action.get("target")): {
                "monster_population": -result.total_kills,
                "alertness": float(result.components.get("alertness_after", area.get("alertness", 0.0))) - float(area.get("alertness", 0.0)),
                "monster_adaptation": float(result.components.get("monster_adaptation_after", area.get("monster_adaptation", 0.0))) - float(area.get("monster_adaptation", 0.0)),
            }
        } if action.get("target") else {}
        event = standard_event(
            event_id=f"evt_{turn:04d}_001",
            event_type="BATCH_ACTION_RESOLVED",
            actor="player",
            target=action.get("target"),
            data={
                "resolution": result.to_dict(),
                "action_ledger": {"available_time_minutes": action.get("available_time_minutes", action.get("minutes", 0)), "available_stamina": max(0.0, 100.0 - float(self.state.player.get("fatigue", 0))), "available_mental": float(self.state.player.get("mental", 100)), "actions": [{"type": action.get("action_type", "GRIND_AREA"), "target": action.get("target"), "time_minutes": action.get("minutes", 0), "stamina_cost": action.get("stamina_cost", 0), "mental_cost": action.get("mental_cost", 0), "tags": action.get("tags", [])}]},
                "resource_changes": resource_changes,
                "fatigue_delta": action.get("stamina_cost", 0),
                "mental_delta": -float(action.get("mental_cost", 0)),
                "time_cost": float(result.components.get("effective_action_time_hours", 0.0)) * 60.0,
                "experience_gain": result.total_experience,
                "equipment_durability": equipment_durability,
                "area_deltas": area_deltas,
                "proposed_events": proposed_events,
            },
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        self.state.apply_and_append(event, persist=persist)
        if persist:
            self.state.save()
        return {"event": event, "resolution": result.to_dict(), "state": self.state.data}

    def execute_build(self, module: Mapping[str, Any], available_minutes: float, action_costs: Optional[Mapping[str, float]] = None, persist: bool = True, dilution_multiplier: float = 1.0) -> Dict[str, Any]:
        if self._current_location() != self._base_location():
            raise ValueError(f"BUILD 只能在基地执行：当前地点为 {self._current_location()}，基地为 {self._base_location()}")
        dilution_multiplier = max(0.25, min(1.0, float(dilution_multiplier)))
        module_for_build = deepcopy(dict(module))
        effects = module_for_build.get("effects", {})
        if dilution_multiplier < 1.0 and isinstance(effects, Mapping):
            module_for_build["effects"] = {key: float(value) * dilution_multiplier if isinstance(value, (int, float)) else value for key, value in effects.items()}
        module_for_build["quality_multiplier"] = dilution_multiplier
        result = calculate_build(self.state.data.get("base", {}), module_for_build, self.state.inventory, available_minutes)
        result["quality_multiplier"] = dilution_multiplier
        if not result["success"]:
            raise ValueError("建造不合法：" + "、".join(result["errors"]))
        turn = self.state.current_turn + 1
        stamina_cost = float((action_costs or {}).get("stamina_cost", 0.0))
        mental_cost = float((action_costs or {}).get("mental_cost", 0.0))
        event = standard_event(
            event_id=f"evt_{turn:04d}_001",
            event_type="BUILDING_BUILT",
            actor="player",
            target=module.get("id", module.get("name")),
            data={"resolution": result, "action": {"action_id": module.get("id", module.get("name")), "type": "BUILD", "target": module.get("id", module.get("name"))}, "action_ledger": {"available_time_minutes": available_minutes, "available_stamina": max(0.0, 100.0 - float(self.state.player.get("fatigue", 0))), "available_mental": float(self.state.player.get("mental", 100)), "actions": [{"type": "BUILD", "target": module.get("id", module.get("name")), "time_minutes": result["time_required"], "stamina_cost": stamina_cost, "mental_cost": mental_cost, "tags": ["requires_full_attention"]}]}, "resource_changes": result["resource_changes"], "fatigue_delta": stamina_cost, "mental_delta": -mental_cost, "time_cost": float(result["time_required"]), "base_space_delta": result["space_cost"], "base_module": module_for_build, "proposed_events": [{"type": "BASE_UPGRADED", "target": module.get("id", module.get("name"))}]},
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        self.state.apply_and_append(event, persist=persist)
        if persist:
            self.state.save()
        return {"event": event, "resolution": result, "state": self.state.data}

    def apply_base_maintenance(self, days: float = 1.0, persist: bool = True) -> Dict[str, Any]:
        result = calculate_base_maintenance(self.state.data.get("base", {}), self.state.inventory, days)
        turn = self.state.current_turn + 1
        event = standard_event(
            event_id=f"evt_{turn:04d}_001",
            event_type="BASE_MAINTENANCE",
            actor="system",
            target="base",
            data={"resolution": result, "resource_changes": result["resource_changes"], "base_durability_delta": result["durability_delta"], "days": days, "time_cost": float(max(0.0, days)) * 720.0},
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        self.state.apply_and_append(event, persist=persist)
        if persist:
            self.state.save()
        return {"event": event, "resolution": result, "state": self.state.data}


def number_for_runtime(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 10.0
