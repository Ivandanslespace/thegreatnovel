import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from engine_runtime.calculators import (
    ActionContext,
    advance_progression,
    calculate_build,
    calculate_combat,
    calculate_experience,
    calculate_farmability,
    calculate_resource_pressure,
    resolve_action,
    simulate_batch_action,
)
from engine_runtime.events import apply_event, parse_events, standard_event
from engine_runtime.narrative_log import record_narrative_turn
from engine_runtime.persistence import SQLiteEventStore
from engine_runtime.protocol import ProtocolError, derive_action_costs, validate_host_action
from engine_runtime.runtime import GameEngine
from engine_runtime.state import GameState, load_game_state
from tools.create_save import answers_to_package, build_files, generate_world_mechanics, normalize_package


def minimal_state(meta=None, world=None, player=None, inventory=None, npcs=None, factions=None):
    return {
        "world": world or {"name": "回归测试世界", "difficulty": "标准"},
        "player": player or {"level": 1, "exp": 0, "exp_to_next": 100, "attributes": {"strength": 8, "constitution": 8, "agility": 8, "spirit": 8}, "fatigue": 0, "hunger": 100, "mental": 100, "max_hp": 50, "hp": 50, "skills": []},
        "base": {"space_total": 3, "space_used": 0, "modules": []},
        "inventory": inventory or {"resources": {"wood": 2, "ammo": 20}, "equipment": {"main_weapon": {"attack": 20, "accuracy": 10, "ammo_resource": "ammo", "ammo_cost": 1, "durability": 10}}},
        "npcs": npcs or [],
        "factions": factions or [],
        "relationships": [],
        "event_queue": [],
        "meta": {"current_turn": 0, "game_day": 1, "time_of_day": "清晨", "day_elapsed_minutes": 0, "available_time_minutes": 720, "world_name": "回归测试世界", "difficulty": "标准", "campaign_status": "active", **(meta or {})},
    }


class FormulaTests(unittest.TestCase):
    def test_host_protocol_rejects_engine_values(self):
        validate_host_action({"action_id": "scout", "type": "EXPLORATION", "primary_attribute": "agility"})
        self.assertEqual(derive_action_costs({"action_id": "scout", "type": "EXPLORATION"})["time_minutes"], 120.0)
        with self.assertRaises(ProtocolError):
            validate_host_action({"action_id": "cheat", "type": "EXPLORATION", "target_difficulty": 1})
        with self.assertRaises(ProtocolError):
            validate_host_action({"action_id": "cheat", "type": "EXPLORATION", "parameters": {"resolution": {"probability": 1.0}}})
        with self.assertRaises(ProtocolError):
            validate_host_action({"action_id": "cheat", "type": "EXPLORATION", "parameters": {"minutes": 999}})

    def test_action_is_deterministic_and_state_linked(self):
        player = {"attributes": {"strength": 8, "constitution": 5, "agility": 5, "spirit": 5}, "fatigue": 0, "injuries": []}
        context = ActionContext(action_id="inspect", primary_attribute="strength", target_difficulty=20, seed="seed-1")
        first = resolve_action(player, context)
        second = resolve_action(player, context)
        self.assertEqual(first.to_dict(), second.to_dict())

        tired = dict(player, fatigue=100)
        tired_result = resolve_action(tired, context)
        self.assertLess(tired_result.advantage - tired_result.resistance, first.advantage - first.resistance)

    def test_combat_uses_attributes_equipment_state_and_environment(self):
        attacker = {"attributes": {"strength": 8, "constitution": 5, "agility": 6, "spirit": 5}, "fatigue": 0}
        defender = {"attributes": {"strength": 5, "constitution": 6, "agility": 4, "spirit": 5}, "fatigue": 0}
        weapon = {"attack": 20, "accuracy": 5, "durability": 3}
        result = calculate_combat(attacker, defender, weapon=weapon, environment={"difficulty": "标准"}, seed="combat-1")
        self.assertGreater(result.attacker_attack, 0)
        self.assertEqual(result.weapon_durability_after, 2)
        self.assertGreaterEqual(result.hit_probability, 0)
        self.assertLessEqual(result.hit_probability, 1)
        no_ammo = calculate_combat(attacker, defender, weapon={"attack": 20, "ammo_cost": 1, "ammo_available": 0}, seed="combat-1")
        self.assertFalse(no_ammo.ammo_sufficient)
        self.assertEqual(no_ammo.damage, 0.0)

    def test_experience_decay_and_level_up(self):
        self.assertEqual(calculate_experience(5, 4), 40.0)
        self.assertEqual(calculate_experience(5, 3), 18.0)
        self.assertEqual(calculate_experience(5, 2), 5.0)
        player = {"level": 1, "exp": 0, "exp_to_next": 100, "attributes": {"strength": 5, "constitution": 5, "agility": 5, "spirit": 5}, "free_points": 0}
        updated = advance_progression(player, 100)
        self.assertEqual(updated["level"], 2)
        self.assertEqual(updated["free_points"], 2)
        self.assertTrue(updated["talent_choice_required"])
        self.assertEqual(updated["pending_decision"]["type"], "TALENT_CHOICE")
        self.assertEqual(len(updated["pending_decision"]["options"]), 3)

    def test_macro_economy_and_resource_pressure(self):
        farmability = calculate_farmability({"combat_advantage": 90, "enemy_information": 90, "kill_stability": 90, "sustainability": 90, "route_familiarity": 90, "extraction_ability": 90, "unknown_danger_penalty": 0})
        self.assertEqual(farmability, 90.0)
        batch = simulate_batch_action(
            area={"monster_density_per_hour": 10, "route_coverage": 100, "search_efficiency": 100, "monster_alertness_modifier": 100},
            player_level=2,
            minutes=60,
            kill_success_rate=1,
            ammo_available=20,
            ammo_per_kill=1,
            weapon_rate_per_hour=20,
            recovery_efficiency=1,
            backpack_capacity_modifier=1,
            enemy_groups=[{"level": 1, "quality": "普通", "weight": 1, "drops": {"food": 2}}],
            farmability_components={"combat_advantage": 90, "enemy_information": 90, "kill_stability": 90, "sustainability": 90, "route_familiarity": 90, "extraction_ability": 90, "unknown_danger_penalty": 0},
        )
        self.assertEqual(batch.total_kills, 10.0)
        self.assertEqual(batch.recovered_resources["food"], 20.0)
        pressure = calculate_resource_pressure({"food": {"current": 1, "demand": 10, "income_rate": 2, "next_stage_need": 20, "blocked_count": 1, "perceived": 80}})
        self.assertGreater(pressure["score"], 50)

    def test_theme_generates_world_mechanics_without_player_fields(self):
        template_path = Path(__file__).resolve().parents[1] / "templates" / "world_template.yaml"
        template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        supplied_world, supplied_talent = answers_to_package({
            "world_name": "自动冰川",
            "theme": "永夜冰川",
            "difficulty": "标准",
            "narrative_length": 7,
            "language": "中文",
        })
        world, talent = normalize_package(template, supplied_world, supplied_talent)

        self.assertEqual(world["setting"]["safe_base"], "霜轨列车")
        self.assertEqual(world["setting"]["disaster_type"], "白夜风暴")
        self.assertEqual([item["name"] for item in world["resources"]["primary"]], ["煤炭", "食物", "寒晶"])
        self.assertEqual(talent["name"], "寒潮预兆")
        self.assertEqual(world["generation"]["theme_profile"], "永夜冰川")
        self.assertEqual(
            set(world["generation"]["generated_fields"]),
            {
                "setting.safe_base",
                "setting.external_dangers",
                "resources.primary",
                "player_talent",
                "setting.exploration_method",
                "setting.disaster_cycle",
                "generation_bundle",
            },
        )

    def test_custom_theme_uses_generic_mechanics_and_language_variant(self):
        generated = generate_world_mechanics("漂浮岛屿", "English")
        self.assertEqual(generated["profile"], "generic")
        self.assertEqual(generated["safe_base"], "A Mobile Shelter Built Around the Theme")
        self.assertEqual(len(generated["primary_resources"]), 3)

    def test_base_build_checks_cost_time_and_space(self):
        result = calculate_build(
            {"space_total": 3, "space_used": 2},
            {"id": "workbench", "space_cost": 1, "build_time": 60, "build_cost": {"wood": 2}, "maintenance": {"wood": 1}},
            {"resources": {"wood": 2}},
            60,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["resource_changes"]["wood"], -2.0)


class RuntimeIntegrationTests(unittest.TestCase):
    def test_compiled_world_supports_core_loop_and_sql_replay(self):
        project_root = Path(__file__).resolve().parents[1]
        template = yaml.safe_load((project_root / "templates" / "world_template.yaml").read_text(encoding="utf-8"))
        supplied_world, supplied_talent = answers_to_package({
            "world_name": "巨兽背部验收",
            "theme": "巨兽背部",
            "difficulty": "标准",
            "narrative_length": 7,
            "language": "中文",
        })
        world, talent = normalize_package(template, supplied_world, supplied_talent)
        files = build_files(project_root / "templates" / "save_template", world, talent)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for filename, content in files.items():
                destination = root / filename
                if filename.endswith((".yaml", ".yml")):
                    destination.write_text(yaml.safe_dump(content, allow_unicode=True, sort_keys=False), encoding="utf-8")
                else:
                    destination.write_text(content, encoding="utf-8")
            engine = GameEngine(load_game_state(root))
            bundle = engine.state.data["world"]["generation_bundle"]
            area_id = next(iter(bundle["areas"]))
            enemy_id = next(iter(bundle["combat_targets"]))
            module_id = next(iter(bundle["build_catalog"]))

            plan = engine.execute_host_action({
                "action_id": "plan-1",
                "type": "ACTION_PLAN",
                "plan_id": "plan-1",
                "accept_dilution": True,
                "steps": [
                    {"action_id": "social-1", "type": "SOCIAL_INTERACTION", "target": bundle["starting_npcs"][0]["id"], "goal": "确认基地目标"},
                    {"action_id": "research-1", "type": "RESEARCH", "target": next(key for key in bundle["action_targets"] if key not in {area_id, "camp_core", bundle["starting_npcs"][0]["id"]}), "goal": "建立第一条工程假设"},
                ],
            })
            self.assertEqual(len(plan["events"]), 2)
            self.assertEqual(engine.state.meta["time_of_day"], "白天")
            explored = engine.execute_host_action({"action_id": "explore-1", "type": "EXPLORATION", "target": area_id, "risk_preference": "谨慎"})
            self.assertEqual(explored["event"]["type"], "EXPLORATION_RESOLVED")
            combat = engine.execute_host_action({"action_id": "combat-1", "type": "COMBAT", "target": enemy_id})
            self.assertIn("target_deltas", combat["event"]["data"])
            built = engine.execute_host_action({"action_id": "build-1", "type": "BUILD", "target": module_id})
            self.assertEqual(built["event"]["type"], "BUILDING_BUILT")
            rested = engine.execute_host_action({"action_id": "rest-1", "type": "REST", "target": "camp_core"})
            self.assertEqual(rested["event"]["type"], "ACTION_RESOLVED")
            self.assertEqual(engine.state.meta["game_day"], 2)
            farmed = engine.execute_host_action({"action_id": "farm-1", "type": "BATCH_ACTION", "target": area_id})
            self.assertEqual(farmed["event"]["type"], "BATCH_ACTION_RESOLVED")
            self.assertLess(engine.state.data["world"]["areas"][area_id]["monster_population"], 50)
            self.assertGreater(engine.state.data["world"]["areas"][area_id]["alertness"], 0)
            self.assertTrue((root / "campaign.sqlite3").exists())
            verification = engine.state.store.verify_projection(apply_event)
            self.assertTrue(verification["ok"], verification)

    def test_host_dispatches_specialized_actions_and_consumes_derived_costs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            values = {
                "world.yaml": {"world": {"name": "注册表世界", "difficulty": "标准", "targets": {"ice-zombie": {"id": "ice-zombie", "attributes": {"strength": 3, "constitution": 3, "agility": 3, "spirit": 3}}}, "build_catalog": {"workbench": {"id": "workbench", "space_cost": 1, "build_time": 60, "build_cost": {"wood": 1}, "maintenance": {"wood": 1}}}, "areas": {"edge": {"monster_density_per_hour": 10, "route_coverage": 100, "search_efficiency": 100, "monster_alertness_modifier": 100, "kill_success_rate": 1, "ammo_per_kill": 1, "weapon_rate_per_hour": 20, "enemy_groups": [{"level": 1, "quality": "普通", "weight": 1, "drops": {"food": 1}}], "farmability_components": {"combat_advantage": 80, "enemy_information": 80, "kill_stability": 80, "sustainability": 80, "route_familiarity": 80, "extraction_ability": 80}}}}, "player_talent": {}},
                "player.yaml": {"player": {"level": 1, "exp": 0, "exp_to_next": 100, "attributes": {"strength": 8, "constitution": 5, "agility": 6, "spirit": 5}, "fatigue": 0, "hunger": 100, "mental": 100, "max_hp": 50, "hp": 50, "skills": []}},
                "base.yaml": {"base": {"space_total": 3, "space_used": 0, "modules": []}},
                "inventory.yaml": {"inventory": {"equipment": {"main_weapon": {"attack": 20, "durability": 2, "ammo_resource": "ammo", "ammo_cost": 1, "rate_per_hour": 20}}, "resources": {"ammo": 20, "wood": 1}}},
                "npcs.yaml": {"npcs": []}, "factions.yaml": {"factions": []}, "relationships.yaml": {"relationships": []}, "event_queue.yaml": {"event_queue": []},
                "meta.yaml": {"meta": {"current_turn": 1, "game_day": 1, "time_of_day": "白天", "world_name": "注册表世界", "difficulty": "标准", "available_time_minutes": 240, "event_format_version": 2}},
            }
            for filename, value in values.items():
                (root / filename).write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
            (root / "event_log.md").write_text("# 事件日志\n", encoding="utf-8")
            (root / "story.md").write_text("# 故事摘要\n", encoding="utf-8")

            engine = GameEngine(load_game_state(root))
            combat = engine.execute_host_action({"action_id": "fight", "type": "COMBAT", "target": "ice-zombie"})
            self.assertEqual(combat["event"]["type"], "COMBAT_RESOLVED")
            self.assertEqual(engine.state.inventory["resources"]["ammo"], 19.0)
            self.assertEqual(engine.state.inventory["equipment"]["main_weapon"]["durability"], 1.0)

            built = engine.execute_host_action({"action_id": "build", "type": "BUILD", "target": "workbench"})
            self.assertEqual(built["event"]["type"], "BUILDING_BUILT")
            self.assertEqual(engine.state.inventory["resources"]["wood"], 0.0)

            batch = engine.execute_host_action({"action_id": "farm", "type": "BATCH_ACTION", "target": "edge"})
            self.assertEqual(batch["event"]["type"], "BATCH_ACTION_RESOLVED")
            self.assertEqual(engine.state.meta["available_time_minutes"], 30)
            self.assertEqual(engine.state.player["fatigue"], 45)

    def test_execute_action_writes_event_and_updates_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            values = {
                "world.yaml": {"world": {"name": "测试世界", "difficulty": "标准"}, "player_talent": {}},
                "player.yaml": {"player": {"level": 1, "exp": 0, "exp_to_next": 100, "attributes": {"strength": 5, "constitution": 5, "agility": 5, "spirit": 5}, "fatigue": 0, "hunger": 100, "mental": 100, "max_hp": 50, "hp": 50, "skills": []}},
                "base.yaml": {"base": {}},
                "inventory.yaml": {"inventory": {"resources": {"food": 3}}},
                "npcs.yaml": {"npcs": []},
                "factions.yaml": {"factions": []},
                "relationships.yaml": {"relationships": []},
                "event_queue.yaml": {"event_queue": []},
                "meta.yaml": {"meta": {"current_turn": 1, "game_day": 1, "time_of_day": "白天", "world_name": "测试世界", "event_format_version": 2}},
            }
            for filename, value in values.items():
                (root / filename).write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
            (root / "event_log.md").write_text("# 事件日志\n", encoding="utf-8")
            (root / "story.md").write_text("# 故事摘要\n", encoding="utf-8")

            engine = GameEngine(load_game_state(root))
            engine.state.player["skills"] = [{"id": "scan", "level": 1, "cost": {"stamina": 5, "mental": 7, "energy": 1}, "cooldown": 2, "cooldown_remaining": 0}]
            engine.state.inventory["resources"]["energy"] = 2
            action = {"action_id": "eat", "type": "SHORT_ACTION", "target": "food", "primary_attribute": "constitution"}
            before_state = deepcopy(engine.state.data)
            result = engine.execute_action(action)

            self.assertEqual(result["event"]["type"], "ACTION_RESOLVED")
            self.assertEqual(result["event"]["data"]["action_ledger"]["actions"][0]["time_minutes"], 30.0)
            self.assertEqual(engine.state.current_turn, 2)
            self.assertEqual(engine.state.inventory["resources"]["food"], 3)
            self.assertEqual(engine.state.player["level"], 1)
            record_narrative_turn(root, "我先检查食物储备。", "车厢深处，冷白色的系统光幕在雾气中亮起。", action=action, before_state=before_state, result=result)
            novel_text = (root / "novel_draft.md").read_text(encoding="utf-8")
            conversation_text = (root / "conversation_log.md").read_text(encoding="utf-8")
            audit_record = json.loads((root / "decision_audit.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertIn("冷白色的系统光幕", novel_text)
            self.assertIn("我先检查食物储备", conversation_text)
            self.assertEqual(audit_record["status"], "EXECUTED")
            self.assertIn("player.fatigue", audit_record["player_database_impact"]["state_diff"])
            self.assertIn("python.resolution", audit_record["joint"]["decision_chain"])
            with self.assertRaises(ValueError):
                record_narrative_turn(root, "重复输入", "重复回答")
            engine.execute_action({"action_id": "scan", "type": "SKILL_ACTION", "skill_id": "scan"})
            self.assertEqual(engine.state.player["fatigue"], 7)
            self.assertEqual(engine.state.player["mental"], 89)
            self.assertEqual(engine.state.inventory["resources"]["energy"], 1.0)
            self.assertEqual(engine.state.player["skills"][0]["cooldown_remaining"], 2)
            engine.state.data["base"] = {"space_total": 3, "space_used": 0, "defense": 10, "modules": []}
            engine.state.inventory["resources"]["wood"] = 2
            built = engine.execute_build({"id": "workbench", "name": "简易工作台", "space_cost": 1, "build_time": 30, "build_cost": {"wood": 2}, "maintenance": {"wood": 1}}, 60)
            self.assertEqual(built["event"]["type"], "BUILDING_BUILT")
            self.assertEqual(engine.state.data["base"]["space_used"], 1)
            maintenance = engine.apply_base_maintenance(1)
            self.assertEqual(maintenance["resolution"]["status"], "maintenance_shortage")
            self.assertEqual(engine.state.inventory["resources"]["wood"], 0)
            combat = engine.execute_combat({"id": "ice-zombie", "attributes": {"strength": 3, "constitution": 3, "agility": 3, "spirit": 3}}, weapon={"attack": 20, "durability": 2}, seed="integration-combat")
            self.assertEqual(combat["event"]["type"], "COMBAT_RESOLVED")
            self.assertEqual(engine.state.current_turn, 6)
            events = parse_events((root / "event_log.md").read_text(encoding="utf-8"))
            self.assertEqual(len(events), 5)
            self.assertEqual(events[0]["record"]["data"]["resolution"]["formula_version"], "1.0")
            stored_meta = yaml.safe_load((root / "meta.yaml").read_text(encoding="utf-8"))["meta"]
            self.assertEqual(stored_meta["current_turn"], 6)

    def test_action_plan_sequential_preview_priority_and_dilution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            world = {
                "name": "计划回归世界",
                "difficulty": "标准",
                "action_targets": {
                    "site-a": {"id": "site-a", "location_id": "site-a", "target_difficulty": 0, "effects": {"success": {"resource_changes": {"wood": 4}}}},
                    "site-b": {"id": "site-b", "location_id": "site-b", "target_difficulty": 0, "effects": {"success": {"resource_changes": {"wood": 4}}}},
                },
                "build_catalog": {
                    "module-a": {"id": "module-a", "space_cost": 1, "build_time": 120, "build_cost": {"wood": 2}},
                    "module-b": {"id": "module-b", "space_cost": 1, "build_time": 120, "build_cost": {"wood": 2}},
                },
            }
            engine = GameEngine(GameState(root, minimal_state(world=world)))
            single = engine.preview_host_action({"action_id": "single", "type": "SHORT_ACTION", "target": "site-a"})
            plan = {"action_id": "diluted", "type": "ACTION_PLAN", "plan_id": "diluted", "accept_dilution": True, "steps": [{"action_id": "a", "type": "SHORT_ACTION", "target": "site-a"}, {"action_id": "b", "type": "SHORT_ACTION", "target": "site-b"}]}
            preview = engine.preview_action_plan(plan)
            self.assertTrue(preview["legal"], preview)
            self.assertEqual(preview["dilution_multiplier"], 0.75)
            self.assertLess(preview["steps"][0]["preview"]["resolution"]["probability"], single["resolution"]["probability"])
            self.assertEqual(engine.state.inventory["resources"]["wood"], 2)

            sequential = {"action_id": "sequential", "type": "ACTION_PLAN", "plan_id": "sequential", "accept_dilution": True, "steps": [{"action_id": "m1", "type": "BUILD", "target": "module-a"}, {"action_id": "m2", "type": "BUILD", "target": "module-b"}]}
            invalid_preview = engine.preview_action_plan(sequential)
            self.assertFalse(invalid_preview["legal"])
            self.assertTrue(any("m2：材料不足" in error for error in invalid_preview["errors"]))
            self.assertEqual(engine.state.data["base"]["space_used"], 0)
            prioritized = dict(sequential, priority_order=["m2", "m1"])
            valid_partial = engine.preview_action_plan(prioritized)
            self.assertTrue(valid_partial["legal"], valid_partial)
            self.assertTrue(valid_partial["partial"])
            self.assertEqual(valid_partial["deferred_steps"], ["m1"])
            engine.execute_action_plan(prioritized)
            self.assertEqual(engine.state.data["base"]["modules"][0]["id"], "module-b")
            self.assertEqual(engine.state.inventory["resources"]["wood"], 0)

    def test_death_is_terminal_and_dead_targets_are_not_reusable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = {"id": "dead-enemy", "status": "dead", "hp": 0, "attributes": {"strength": 2, "constitution": 2, "agility": 2, "spirit": 2}}
            engine = GameEngine(GameState(root, minimal_state(meta={"death_mode": "checkpoint", "checkpoints_used": 0, "max_checkpoints": 1}, world={"name": "终局世界", "difficulty": "标准", "combat_targets": {"dead-enemy": target}})))
            death = standard_event("death-1", "COMBAT_RESOLVED", "player", "enemy", {"player_died": True, "player_delta": {"hp": -50}, "death_reason": "回归测试死亡", "time_cost": 0}, 1, "Day 1 清晨")
            engine.state.apply_and_append(death)
            self.assertEqual(engine.state.player["status"], "dead")
            self.assertEqual(engine.state.meta["campaign_status"], "ended")
            self.assertIn("ending_id", engine.state.meta)
            with self.assertRaises(ValueError):
                engine.execute_host_action({"action_id": "after-death", "type": "SHORT_ACTION", "target": "nothing"})
            ending = engine.execute_host_action({"action_id": "ending", "type": "ENDING"})
            self.assertEqual(ending["terminal"]["ending_id"], engine.state.meta["ending_id"])
            restarted = engine.execute_host_action({"action_id": "restart", "type": "RESTART"})
            self.assertEqual(restarted["event"]["type"], "CAMPAIGN_RESTARTED")
            self.assertEqual(engine.state.meta["campaign_status"], "active")
            self.assertEqual(engine.state.player.get("status", "alive"), "alive")

            with self.assertRaises(ValueError):
                engine.execute_host_action({"action_id": "attack-dead", "type": "COMBAT", "target": "dead-enemy"})

    def test_timeline_disaster_boundary_and_cross_day_budget(self):
        disaster_world = {"name": "灾难边界", "setting": {"disaster_type": "边界灾难"}, "rules": {"disaster": {"cycle_days": 7}}}
        state = minimal_state(world=disaster_world, meta={"game_day": 6, "day_elapsed_minutes": 0, "available_time_minutes": 720, "next_disaster_day": 7})
        record = standard_event("day-7", "ACTION_RESOLVED", "player", None, {"time_cost": 720}, 1, "Day 6 清晨")
        updated = apply_event(state, record)
        self.assertEqual(updated["meta"]["game_day"], 7)
        self.assertEqual(updated["meta"]["available_time_minutes"], 720)
        self.assertEqual(updated["meta"]["next_disaster_day"], 14)
        self.assertEqual([item["day"] for item in updated["meta"]["system_event_history"] if item["type"] == "DISASTER_OCCURRED"], [7])

        cross_day = minimal_state(meta={"game_day": 1, "day_elapsed_minutes": 600, "available_time_minutes": 120})
        crossed = apply_event(cross_day, standard_event("cross-day", "REST_COMPLETED", "player", None, {"time_cost": 360}, 1, "Day 1 夜晚"))
        self.assertEqual(crossed["meta"]["game_day"], 2)
        self.assertEqual(crossed["meta"]["day_elapsed_minutes"], 240)
        self.assertEqual(crossed["meta"]["available_time_minutes"], 480)

    def test_npc_and_faction_schedule_are_idempotent_per_period(self):
        npc = {"id": "npc-1", "status": "alive", "location": "camp_core", "schedule": {"白天": "resource_search"}, "autonomous_yield": {"wood": 1}, "utility_profile": {}}
        state = minimal_state(meta={"time_of_day": "白天", "day_elapsed_minutes": 120, "available_time_minutes": 600}, npcs=[npc], inventory={"resources": {"wood": 0}, "equipment": {}})
        first = standard_event("npc-1", "ACTION_RESOLVED", "player", None, {"time_cost": 30}, 1, "Day 1 白天")
        second = standard_event("npc-2", "ACTION_RESOLVED", "player", None, {"time_cost": 30}, 2, "Day 1 白天")
        after_first = apply_event(state, first)
        after_second = apply_event(after_first, second)
        self.assertEqual(after_first["inventory"]["resources"]["wood"], 1)
        self.assertEqual(after_second["inventory"]["resources"]["wood"], 1)

        faction = {"id": "faction-1", "status": "neutral", "schedule": {"黄昏": "collect_tax"}, "tax_rate": {"wood": 1}, "treasury": {"wood": 0}, "utility_profile": {}}
        faction_state = minimal_state(meta={"time_of_day": "黄昏", "day_elapsed_minutes": 480, "available_time_minutes": 240}, factions=[faction], inventory={"resources": {"wood": 3}, "equipment": {}})
        taxed_once = apply_event(faction_state, standard_event("tax-1", "ACTION_RESOLVED", "player", None, {"time_cost": 30}, 1, "Day 1 黄昏"))
        taxed_twice = apply_event(taxed_once, standard_event("tax-2", "ACTION_RESOLVED", "player", None, {"time_cost": 30}, 2, "Day 1 黄昏"))
        self.assertEqual(taxed_once["factions"][0]["treasury"]["wood"], 1)
        self.assertEqual(taxed_twice["factions"][0]["treasury"]["wood"], 1)

    def test_duplicate_event_id_fails_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = SQLiteEventStore(root / "campaign.sqlite3")
            state = minimal_state()
            store.initialize(state)
            record = standard_event("duplicate", "ACTION_RESOLVED", "player", None, {"time_cost": 0}, 1, "Day 1 清晨")
            store.append_transaction(record, state)
            with self.assertRaises(sqlite3.IntegrityError):
                store.append_transaction(record, state)
            self.assertEqual(len(store.events()), 1)

    def test_combat_requires_current_presence_or_active_encounter(self):
        target = {"id": "wolf", "status": "alive", "hp": 20, "max_hp": 20, "location_id": "forest", "attributes": {"strength": 2, "constitution": 2, "agility": 2, "spirit": 2}}
        world = {"name": "地点世界", "difficulty": "标准", "combat_targets": {"wolf": target}}
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world)))
            with self.assertRaises(ValueError):
                engine.execute_host_action({"action_id": "wrong-place", "type": "COMBAT", "target": "wolf"})
            engine.state.meta["active_encounters"] = [{"id": "encounter-1", "location_id": "forest", "target_ids": ["wolf"], "status": "active"}]
            preview = engine.preview_host_action({"action_id": "right-place", "type": "COMBAT", "target": "wolf"})
            self.assertTrue(preview["legal"], preview)

    def test_balanced_100_turn_simulation_has_no_projection_drift(self):
        world = {
            "name": "百回合回归世界",
            "difficulty": "标准",
            "setting": {"disaster_type": "周期灾难"},
            "rules": {"disaster": {"cycle_days": 7}},
            "action_targets": {"camp_core": {"id": "camp_core", "target_difficulty": 0, "effects": {}}},
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world)))
            for index in range(100):
                available = float(engine.state.meta.get("available_time_minutes", 0))
                fatigue = float(engine.state.player.get("fatigue", 0))
                mental = float(engine.state.player.get("mental", 100))
                if available >= 360 and (fatigue >= 20 or mental <= 40):
                    action = {"action_id": f"rest-{index}", "type": "REST", "target": "camp_core"}
                else:
                    action = {"action_id": f"act-{index}", "type": "SHORT_ACTION", "target": "camp_core"}
                engine.execute_host_action(action)
            resources = engine.state.inventory.get("resources", {})
            self.assertTrue(all(not isinstance(value, (int, float)) or value >= 0 for value in resources.values()))
            self.assertEqual(engine.state.current_turn, 100)
            self.assertEqual(engine.state.meta["campaign_status"], "active")
            self.assertTrue(any(item.get("type") == "DISASTER_OCCURRED" for item in engine.state.meta.get("system_event_history", [])))
            self.assertTrue(engine.state.store.verify_projection(apply_event)["ok"])


if __name__ == "__main__":
    unittest.main()
