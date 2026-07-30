"""面向新游戏的最小可运行引擎入口。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .calculators import (
    ActionContext,
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
from .protocol import derive_action_costs, derive_risk_modifiers, validate_host_action
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
        defaults = {
            "seed": seed,
            "action_id": str(action.get("action_id") or f"turn-{self.state.current_turn + 1}"),
            "target_difficulty": float(target_profile.get("target_difficulty", costs["target_difficulty"])),
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
        }
        talent_effects = self.state.player.get("talent_effects", {}) if isinstance(self.state.player.get("talent_effects", {}), Mapping) else {}
        action_modifiers = talent_effects.get("action_modifiers", {}) if isinstance(talent_effects.get("action_modifiers", {}), Mapping) else {}
        modifier = action_modifiers.get(str(action.get("type")), {}) if isinstance(action_modifiers.get(str(action.get("type")), {}), Mapping) else {}
        for key in ("intelligence", "teammate_assistance", "environment_advantage", "preparation", "environment_penalty", "time_pressure", "unknown_risk"):
            if key in modifier:
                defaults[key] += float(modifier[key])
        values = {**defaults, "primary_attribute": target_profile.get("primary_attribute", "spirit")}
        if action.get("skill_id"):
            skill = self._find_skill(action)
            values["skill_bonus"] = float(skill.get("level", 1)) * 2.0 if skill else 0.0
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

    def _check_requirements(self, action: Mapping[str, Any]) -> list[str]:
        errors: list[str] = []
        pending = self.state.player.get("pending_decision")
        if pending and str(action.get("type")) != "TALENT_CHOICE":
            errors.append("必须先完成升级三选一")
        registry_requirements = self._action_target_profile(action).get("requirements", {})
        requirements = dict(registry_requirements) if isinstance(registry_requirements, Mapping) else {}
        supplied_requirements = action.get("requirements", {}) if isinstance(action.get("requirements"), Mapping) else {}
        for key, value in supplied_requirements.items():
            requirements.setdefault(key, value)
        required_location = requirements.get("location")
        if required_location and required_location != self.state.meta.get("current_location"):
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
            if not npc or npc.get("status", "alive") != "alive" or npc.get("location") != self.state.meta.get("current_location"):
                errors.append(f"NPC不可用：{npc_id}")
        knowledge = requirements.get("knowledge")
        if knowledge:
            known = self.state.player.get("knowledge", [])
            if knowledge not in known:
                errors.append(f"未知信息：{knowledge}")
        skill = self._find_skill(action)
        if skill:
            errors.extend(check_skill_use(skill, self.state.player, self.state.inventory))
        elif action.get("skill_id"):
            errors.append(f"未掌握技能：{action['skill_id']}")
        return errors

    def _action_target_profile(self, action: Mapping[str, Any]) -> Mapping[str, Any]:
        registry = self.state.data.get("world", {}).get("action_targets", {})
        return self._registry_lookup(registry, action.get("target")) or {}

    def _domain_effects(self, action: Mapping[str, Any], resolution: Mapping[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type", ""))
        if action_type == "REST":
            return {
                "fatigue_delta": -35.0,
                "mental_delta": 20.0,
                "hp_delta": 5.0,
                "proposed_events": [{"type": "REST_COMPLETED", "target": self.state.meta.get("current_location")}],
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
        parameters = action.get("parameters", {}) if isinstance(action.get("parameters", {}), Mapping) else {}
        relationship_intent = str(parameters.get("relationship_intent", "")).lower()
        if action_type == "SOCIAL_INTERACTION" and any(token in relationship_intent for token in ("promise", "承诺", "保证")):
            selected["promise_additions"] = [{"id": f"promise_{self.state.current_turn + 1}_{action.get('target')}", "npc_id": action.get("target"), "content": str(parameters.get("message") or action.get("goal") or action.get("approach") or "未注明承诺"), "created_turn": self.state.current_turn + 1, "due_turn": self.state.current_turn + 4, "status": "open"}]
        if action_type == "SOCIAL_INTERACTION" and any(token in relationship_intent for token in ("deceive", "欺骗", "隐瞒")):
            selected["deception_attempts"] = [{"id": f"deception_{self.state.current_turn + 1}_{action.get('target')}", "npc_id": action.get("target"), "content": str(parameters.get("message") or action.get("goal") or "未注明欺骗内容"), "detected": outcome not in {"大成功", "普通成功"}, "turn": self.state.current_turn + 1}]
        proposed = []
        proposed.extend({"type": "AREA_DISCOVERED", "target": item} for item in selected.get("discover_locations", []))
        proposed.extend({"type": "KNOWLEDGE_GAINED", "target": item} for item in selected.get("knowledge_additions", []))
        proposed.extend({"type": "RESOURCE_CHANGED", "target": item, "quantity": quantity} for item, quantity in (selected.get("resource_changes", {}) or {}).items())
        proposed.extend({"type": "RELATIONSHIP_CHANGED", "target": item} for item in (selected.get("relationship_changes", {}) or {}))
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
        if float(costs["time_minutes"]) > available_time:
            errors.append("时间不足")
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
        target = self._registry_lookup(world.get("targets"), target_id)
        if target is None:
            target = self._registry_lookup(world.get("combat_targets"), target_id)
        if target is None:
            target = self._registry_lookup(self.state.data.get("npcs", []), target_id)
        if target is None:
            raise ValueError(f"世界注册表中不存在战斗目标：{target_id}")
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

    def preview_host_action(self, action: Mapping[str, Any]) -> Dict[str, Any]:
        """预览唯一主机协议；专用行动的参数全部来自世界注册表。"""
        validate_host_action(action)
        if str(action.get("type")) == "ACTION_PLAN":
            return self.preview_action_plan(action)
        if str(action.get("type")) == "TALENT_CHOICE":
            return self.preview_talent_choice(action)
        skill = self._find_skill(action)
        costs = derive_action_costs(action, skill)
        errors = self._derived_budget_errors(action, costs)
        action_type = str(action.get("type"))
        if action_type == "COMBAT":
            target = self._lookup_target(action.get("target"))
            environment = self._combat_environment(target, costs)
            weapon = self._combat_weapon()
            resolution = calculate_combat(self.state.player, target, weapon=weapon, skill=skill, environment=environment, seed=self._host_seed(action))
            return {"legal": not errors, "errors": errors, "resolution": resolution.to_dict(), "action_ledger": {"available_time_minutes": environment["available_time_minutes"], "actions": [{"type": "COMBAT", "target": action.get("target"), "time_minutes": costs["time_minutes"], "stamina_cost": costs["stamina_cost"], "mental_cost": costs["mental_cost"], "tags": list(action.get("tags", []))}]}}
        if action_type == "BUILD":
            module = self._lookup_module(action.get("target"))
            available_minutes = min(float(self.state.meta.get("available_time_minutes", 240)), float(costs["time_minutes"]))
            result = calculate_build(self.state.data.get("base", {}), module, self.state.inventory, available_minutes)
            errors.extend(result.get("errors", []))
            return {"legal": not errors, "errors": errors, "resolution": result, "action_ledger": {"available_time_minutes": available_minutes, "actions": [{"type": "BUILD", "target": action.get("target"), "time_minutes": result.get("time_required", costs["time_minutes"]), "stamina_cost": costs["stamina_cost"], "mental_cost": costs["mental_cost"], "tags": list(action.get("tags", []))}]}}
        if action_type == "BATCH_ACTION":
            area = self._lookup_area(action.get("target"))
            internal = self._batch_internal_action(action, area, costs)
            result = simulate_batch_action(
                area=internal["area"], player_level=int(self.state.player.get("level", 1)), minutes=internal["minutes"], kill_success_rate=internal["kill_success_rate"], ammo_available=internal["ammo_available"], ammo_per_kill=internal["ammo_per_kill"], weapon_rate_per_hour=internal["weapon_rate_per_hour"], recovery_efficiency=internal["recovery_efficiency"], backpack_capacity_modifier=internal["backpack_capacity_modifier"], enemy_groups=internal["enemy_groups"], farmability_components=internal["farmability_components"], stop_conditions=internal["stop_conditions"]
            )
            return {"legal": not errors, "errors": errors, "resolution": result.to_dict(), "action_ledger": {"available_time_minutes": internal["available_time_minutes"], "actions": [{"type": "BATCH_ACTION", "target": action.get("target"), "time_minutes": costs["time_minutes"], "stamina_cost": costs["stamina_cost"], "mental_cost": costs["mental_cost"], "tags": list(action.get("tags", []))}]}}
        return self.preview_action(action)

    @staticmethod
    def _plan_step(step: Mapping[str, Any], plan_id: str, index: int) -> Dict[str, Any]:
        normalized = {key: deepcopy(value) for key, value in step.items() if key in {"action_id", "type", "target", "skill_id", "risk_preference", "tags", "goal", "parameters", "requirements"}}
        normalized["action_id"] = str(normalized.get("action_id") or f"{plan_id}-step-{index}")
        if step.get("approach"):
            parameters = normalized.setdefault("parameters", {})
            if isinstance(parameters, dict):
                parameters.setdefault("approach", step["approach"])
        return normalized

    def preview_action_plan(self, action: Mapping[str, Any]) -> Dict[str, Any]:
        validate_host_action(action)
        plan_id = str(action.get("plan_id"))
        steps = [self._plan_step(step, plan_id, index) for index, step in enumerate(action.get("steps", []), start=1)]
        available = float(self.state.meta.get("available_time_minutes", 720))
        used_time = used_stamina = used_mental = 0.0
        previews = []
        errors = []
        for step in steps:
            preview = self.preview_host_action(step)
            previews.append({"action": step, "preview": preview})
            step_ledger = preview.get("action_ledger", {}).get("actions", [{}])[0]
            used_time += float(step_ledger.get("time_minutes", 0))
            used_stamina += float(step_ledger.get("stamina_cost", 0))
            used_mental += float(step_ledger.get("mental_cost", 0))
            errors.extend(f"{step['action_id']}：{error}" for error in preview.get("errors", []))
        factors = {
            "time_remaining": max(0.0, (available - used_time) / max(available, 1.0)),
            "resource_compatibility": 1.0,
            "location_proximity": 1.0 if len({str(item["action"].get("requirements", {}).get("location", "camp_core")) for item in previews}) <= 1 else 0.7,
            "goal_compatibility": 1.0 if len({str(item["action"].get("type")) for item in previews}) == len(previews) else 0.8,
            "npc_availability": 1.0 if not any("NPC不可用" in error for error in errors) else 0.0,
        }
        combinability = calculate_combinability(factors)
        if combinability < 20:
            errors.append("可组合度低于20，只能明确放弃部分步骤")
        elif combinability < 50:
            errors.append("可组合度为20-49，必须重新排序并只执行部分步骤")
        elif combinability < 80 and not bool(action.get("accept_dilution")):
            errors.append("可组合度为50-79，必须明确 accept_dilution=true 才能执行")
        if used_time > available:
            errors.append("计划总时间超过当前行动窗口")
        if used_stamina + float(self.state.player.get("fatigue", 0)) > 100:
            errors.append("计划总消耗超过体力")
        if float(self.state.player.get("mental", 100)) - used_mental < 0:
            errors.append("计划总消耗超过精神")
        return {
            "legal": not errors,
            "errors": errors,
            "plan_id": plan_id,
            "combinability": combinability,
            "components": factors,
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
                results.append(self.execute_host_action(item["action"], persist=False))
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

    def preview_action(self, action: Mapping[str, Any]) -> Dict[str, Any]:
        validate_host_action(action)
        skill = self._find_skill(action)
        costs = derive_action_costs(action, skill)
        context = self._build_action_context(action, costs)
        resolution = resolve_action(self.state.player, context, self.state.inventory)
        available_time = float(self.state.meta.get("available_time_minutes", 240))
        time_cost = float(costs["time_minutes"])
        stamina_cost = float(costs["stamina_cost"])
        mental_cost = float(costs["mental_cost"])
        legal_errors = self._check_requirements(action)
        if time_cost > available_time:
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
        return {
            "legal": not legal_errors,
            "errors": legal_errors,
            "resolution": resolution.to_dict(),
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
                    "tags": list(action.get("tags", [])),
                }],
            },
            "skill": skill,
        }

    def execute_action(self, action: Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        preview = self.preview_action(action)
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
            "resolution": preview["resolution"],
            "fatigue_delta": float(ledger_action.get("stamina_cost", 0)),
            "mental_delta": -float(ledger_action.get("mental_cost", 0)),
            "time_cost": float(ledger_action.get("time_minutes", 0)),
            "hunger_delta": 0.0,
            "resource_changes": {key: -float(value) for key, value in resource_costs.items()},
        }
        domain_effects = self._domain_effects(action, preview["resolution"])
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

    def execute_host_action(self, action: Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        """执行唯一允许由 LLM 主持器调用的入口。"""
        validate_host_action(action)
        if str(action.get("type")) == "ACTION_PLAN":
            return self.execute_action_plan(action, persist=persist)
        if str(action.get("type")) == "TALENT_CHOICE":
            return self.execute_talent_choice(action, persist=persist)
        skill = self._find_skill(action)
        costs = derive_action_costs(action, skill)
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
            )
        if action_type == "BUILD":
            module = self._lookup_module(action.get("target"))
            available_minutes = min(float(self.state.meta.get("available_time_minutes", 240)), float(costs["time_minutes"]))
            return self.execute_build(module, available_minutes, action_costs=costs, persist=persist)
        if action_type == "BATCH_ACTION":
            area = self._lookup_area(action.get("target"))
            return self.execute_batch_action(self._batch_internal_action(action, area, costs), persist=persist)
        return self.execute_action(action, persist=persist)

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

    def execute_combat(self, defender: Mapping[str, Any], weapon: Optional[Mapping[str, Any]] = None, skill: Optional[Mapping[str, Any]] = None, environment: Optional[Mapping[str, Any]] = None, seed: str = "", persist: bool = True) -> Dict[str, Any]:
        weapon = weapon or self._combat_weapon()
        if skill:
            skill_errors = check_skill_use(skill, self.state.player, self.state.inventory)
            if skill_errors:
                raise ValueError("技能不可用：" + "、".join(skill_errors))
        resolution = calculate_combat(self.state.player, defender, weapon=weapon, skill=skill, environment=environment, seed=seed or str(self.state.meta.get("rng_seed", "combat")))
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
        target_id = defender.get("id", defender.get("name"))
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
                "player_delta": {"hp": -incoming_damage},
                "experience_gain": experience_gain,
                "proposed_events": proposed_events,
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

    def execute_batch_action(self, action: Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        result = simulate_batch_action(
            area=action.get("area", {}),
            player_level=int(self.state.player.get("level", 1)),
            minutes=float(action.get("minutes", 0)),
            kill_success_rate=float(action.get("kill_success_rate", 0)),
            ammo_available=float(action.get("ammo_available", 0)),
            ammo_per_kill=float(action.get("ammo_per_kill", 1)),
            weapon_rate_per_hour=float(action.get("weapon_rate_per_hour", 0)),
            recovery_efficiency=float(action.get("recovery_efficiency", 1)),
            backpack_capacity_modifier=float(action.get("backpack_capacity_modifier", 1)),
            enemy_groups=action.get("enemy_groups", []),
            farmability_components=action.get("farmability_components", {}),
            stop_conditions=action.get("stop_conditions", {}),
        )
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

    def execute_build(self, module: Mapping[str, Any], available_minutes: float, action_costs: Optional[Mapping[str, float]] = None, persist: bool = True) -> Dict[str, Any]:
        result = calculate_build(self.state.data.get("base", {}), module, self.state.inventory, available_minutes)
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
            data={"resolution": result, "action": {"action_id": module.get("id", module.get("name")), "type": "BUILD", "target": module.get("id", module.get("name"))}, "action_ledger": {"available_time_minutes": available_minutes, "available_stamina": max(0.0, 100.0 - float(self.state.player.get("fatigue", 0))), "available_mental": float(self.state.player.get("mental", 100)), "actions": [{"type": "BUILD", "target": module.get("id", module.get("name")), "time_minutes": result["time_required"], "stamina_cost": stamina_cost, "mental_cost": mental_cost, "tags": ["requires_full_attention"]}]}, "resource_changes": result["resource_changes"], "fatigue_delta": stamina_cost, "mental_delta": -mental_cost, "time_cost": float(result["time_required"]), "base_space_delta": result["space_cost"], "base_module": dict(module), "proposed_events": [{"type": "BASE_UPGRADED", "target": module.get("id", module.get("name"))}]},
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
