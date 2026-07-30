"""面向新游戏的最小可运行引擎入口。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .calculators import (
    ActionContext,
    calculate_base_defense,
    calculate_base_maintenance,
    calculate_build,
    calculate_combat,
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
        target_profile = world_targets.get(action.get("target"), {}) if isinstance(world_targets, Mapping) else {}
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
        values = {**defaults, "primary_attribute": action.get("primary_attribute", "spirit")}
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
        requirements = action.get("requirements", {}) if isinstance(action.get("requirements"), Mapping) else {}
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
            return value if isinstance(value, Mapping) else None
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
        if cooldown_changes:
            payload["cooldown_changes"] = cooldown_changes
        event = standard_event(
            event_id=f"evt_{turn:04d}_001",
            event_type="ACTION_RESOLVED",
            actor="player",
            target=action.get("target"),
            data=payload,
            turn=turn,
            timestamp=timestamp,
        )
        self.state.apply_and_append(event)
        metrics = calculate_narrative_metrics(self.state.data, [item["record"] for item in self.state.event_history()])
        self.state.meta["runtime_metrics"] = metrics
        self.state.meta["rng_seed"] = str(self.state.meta.get("rng_seed") or self.state.meta.get("world_name", "world"))
        if persist:
            self.state.save()
        return {"event": event, "resolution": preview["resolution"], "metrics": metrics, "state": self.state.data}

    def execute_host_action(self, action: Mapping[str, Any], persist: bool = True) -> Dict[str, Any]:
        """执行唯一允许由 LLM 主持器调用的入口。"""
        validate_host_action(action)
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
        event = standard_event(
            event_id=f"evt_{turn:04d}_001",
            event_type="COMBAT_RESOLVED",
            actor="player",
            target=defender.get("id", defender.get("name")),
            data={
                "resolution": resolution.to_dict(),
                "action_ledger": {"available_time_minutes": (environment or {}).get("available_time_minutes", 30), "available_stamina": max(0.0, 100.0 - float(self.state.player.get("fatigue", 0))), "available_mental": float(self.state.player.get("mental", 100)), "actions": [{"type": "COMBAT", "target": defender.get("id", defender.get("name")), "time_minutes": (environment or {}).get("time_minutes", 30), "stamina_cost": stamina_cost, "mental_cost": mental_cost, "tags": ["combat"]}]},
                "fatigue_delta": stamina_cost,
                "mental_delta": -mental_cost,
                "time_cost": float((environment or {}).get("time_minutes", 30)),
                "resource_changes": resource_changes,
                "equipment_durability": {"main_weapon": resolution.weapon_durability_after} if resolution.weapon_durability_after is not None else {},
                "equipment_updates": equipment_updates,
            },
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        if cooldown_changes:
            event["data"]["cooldown_changes"] = cooldown_changes
        self.state.apply_and_append(event)
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
                "time_cost": float(action.get("minutes", 0)),
                "experience_gain": result.total_experience,
            },
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        self.state.apply_and_append(event)
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
            data={"resolution": result, "action_ledger": {"available_time_minutes": available_minutes, "available_stamina": max(0.0, 100.0 - float(self.state.player.get("fatigue", 0))), "available_mental": float(self.state.player.get("mental", 100)), "actions": [{"type": "BUILD", "target": module.get("id", module.get("name")), "time_minutes": result["time_required"], "stamina_cost": stamina_cost, "mental_cost": mental_cost, "tags": ["requires_full_attention"]}]}, "resource_changes": result["resource_changes"], "fatigue_delta": stamina_cost, "mental_delta": -mental_cost, "time_cost": float(result["time_required"]), "base_space_delta": result["space_cost"], "base_module": dict(module)},
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        self.state.apply_and_append(event)
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
            data={"resolution": result, "resource_changes": result["resource_changes"], "base_durability_delta": result["durability_delta"], "days": days},
            turn=turn,
            timestamp=f"Day {self.state.meta.get('game_day', 1)} {self.state.meta.get('time_of_day', '清晨')}",
        )
        self.state.apply_and_append(event)
        self.state.meta["game_day"] = int(self.state.meta.get("game_day", 1)) + int(max(0, days))
        if persist:
            self.state.save()
        return {"event": event, "resolution": result, "state": self.state.data}


def number_for_runtime(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 10.0
