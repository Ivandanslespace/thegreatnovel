import json
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
from engine_runtime.events import parse_events
from engine_runtime.narrative_log import record_narrative_turn
from engine_runtime.protocol import ProtocolError, derive_action_costs, validate_host_action
from engine_runtime.runtime import GameEngine
from engine_runtime.state import load_game_state


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


if __name__ == "__main__":
    unittest.main()
