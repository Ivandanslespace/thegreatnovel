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
from engine_runtime.narrative_log import validate_player_narrative
from engine_runtime.persistence import SQLiteEventStore
from engine_runtime.presentation import player_facing_result
from engine_runtime.protocol import ProtocolError, derive_action_costs, validate_host_action
from engine_runtime.ratings import RATING_SCALE, normalize_rating, shift_rating
from engine_runtime.runtime import GameEngine
from engine_runtime.state import GameState, load_game_state
from tools.create_save import answers_to_package, build_files, generate_world_mechanics, normalize_package
from tools.validate_save import assert_startable


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
    def test_talent_and_equipment_use_letter_ratings(self):
        self.assertEqual(RATING_SCALE, ("G", "F", "E", "D", "C", "B", "A", "S", "SS", "SSS"))
        self.assertEqual(normalize_rating("a"), "A")
        self.assertEqual(normalize_rating("颜色", default="B"), "B")
        self.assertEqual(shift_rating("A", 1), "S")
        self.assertEqual(shift_rating("SSS", 1), "SSS")
        self.assertEqual(shift_rating("G", -1), "G")

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

    def test_combat_dilution_recomputes_counterattack_and_outcome(self):
        attacker = {"attributes": {"strength": 20, "constitution": 8, "agility": 10, "spirit": 5}, "fatigue": 0, "max_hp": 50}
        defender = {"id": "target", "hp": 20, "max_hp": 20, "attack": 30, "accuracy": 20, "attributes": {"strength": 5, "constitution": 2, "agility": 2, "spirit": 2}}
        weapon = {"attack": 100, "accuracy": 50, "durability": 3}
        full = calculate_combat(attacker, defender, weapon=weapon, seed="seed-0")
        diluted = calculate_combat(attacker, defender, weapon=weapon, seed="seed-0", dilution_multiplier=0.25)
        self.assertTrue(full.hit)
        self.assertGreaterEqual(full.damage, defender["hp"])
        self.assertTrue(diluted.hit)
        self.assertLess(diluted.damage, defender["hp"])
        self.assertFalse(full.counterattack_hit)
        self.assertTrue(diluted.counterattack_hit)
        self.assertGreater(diluted.incoming_damage, 0)

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
        self.assertTrue(all(option["rarity"] == "B" for option in updated["pending_decision"]["options"]))

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
        self.assertEqual(talent["rarity"], "A")
        self.assertEqual(world["generation_bundle"]["starting_inventory"]["equipment"]["main_weapon"]["rarity"], "G")
        self.assertEqual(world["generation"]["theme_profile"], "永夜冰川")
        self.assertEqual(world["generation_bundle"]["compiler_version"], "1.1")
        self.assertTrue(world["generation_bundle"]["locations"][1]["extraction_rule"]["requires_discovered_location"])
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
    def test_attribute_allocation_is_validated_and_projected(self):
        player = {
            "level": 1,
            "exp": 0,
            "exp_to_next": 100,
            "attributes": {"strength": 5, "constitution": 5, "agility": 5, "spirit": 5},
            "free_points": 4,
            "fatigue": 0,
            "mental": 100,
            "max_hp": 50,
            "hp": 50,
            "skills": [],
        }
        action = {
            "action_id": "allocate-opening-points",
            "type": "ATTRIBUTE_ALLOCATION",
            "parameters": {"allocations": {"力量": 2, "spirit": 2}},
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(player=player)))
            preview = engine.preview_host_action(action)
            self.assertTrue(preview["legal"], preview)
            self.assertEqual(preview["resolution"]["allocations"], {"strength": 2, "spirit": 2})
            self.assertEqual(preview["resolution"]["points_after"], 0)

            result = engine.execute_host_action(action)
            self.assertEqual(result["event"]["type"], "ATTRIBUTES_ALLOCATED")
            self.assertEqual(engine.state.player["attributes"]["strength"], 7)
            self.assertEqual(engine.state.player["attributes"]["spirit"], 7)
            self.assertEqual(engine.state.player["free_points"], 0)
            self.assertEqual(engine.state.current_turn, 1)
            self.assertEqual(engine.state.meta["available_time_minutes"], 720)
            self.assertEqual(player_facing_result(result)["attribute_allocations"], {"strength": 2, "spirit": 2})
            self.assertTrue(engine.state.store.verify_projection(apply_event)["ok"])

    def test_attribute_allocation_rejects_invalid_or_excess_points_without_event(self):
        player = {
            "attributes": {"strength": 5, "constitution": 5, "agility": 5, "spirit": 5},
            "free_points": 1,
            "fatigue": 0,
            "mental": 100,
            "skills": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(player=player)))
            excessive = {
                "action_id": "allocate-too-much",
                "type": "ATTRIBUTE_ALLOCATION",
                "parameters": {"allocations": {"strength": 2}},
            }
            preview = engine.preview_host_action(excessive)
            self.assertFalse(preview["legal"])
            self.assertIn("属性点不足", "；".join(preview["errors"]))
            with self.assertRaises(ValueError):
                engine.execute_host_action(excessive)
            self.assertEqual(engine.state.current_turn, 0)
            self.assertEqual(engine.state.player["free_points"], 1)
            with self.assertRaises(ProtocolError):
                validate_host_action({
                    "action_id": "allocate-unknown",
                    "type": "ATTRIBUTE_ALLOCATION",
                    "parameters": {"allocations": {"luck": 1}},
                })

    def test_attribute_allocation_option_is_executable_without_second_confirmation(self):
        player = {
            "attributes": {"strength": 5, "constitution": 5, "agility": 5, "spirit": 5},
            "free_points": 2,
            "fatigue": 0,
            "mental": 100,
            "skills": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(player=player, world=self._option_world())))
            compiled = engine.compile_options([{
                "id": "A",
                "label": "分配属性",
                "action": {
                    "action_id": "stored-allocation",
                    "type": "ATTRIBUTE_ALLOCATION",
                    "parameters": {"allocations": {"agility": 2}},
                },
            }])
            self.assertIn("A", compiled["options"])
            result = engine.execute_player_choice("A")
            self.assertEqual(result["event"]["type"], "ATTRIBUTES_ALLOCATED")
            self.assertEqual(engine.state.player["attributes"]["agility"], 7)
            self.assertEqual(engine.state.player["free_points"], 0)

    def _option_world(self):
        return {
            "name": "选项回归世界",
            "difficulty": "标准",
            "starting_location": "camp_core",
            "locations": [
                {"id": "camp_core", "name": "基地", "safe": True, "travel_minutes_from_base": 0, "travel_stamina_from_base": 0},
                {"id": "forest", "name": "森林", "safe": False, "travel_minutes_from_base": 30, "travel_stamina_from_base": 5},
            ],
            "action_targets": {
                "camp_core": {"id": "camp_core", "location_id": "camp_core", "target_difficulty": 0, "effects": {}},
                "forest": {"id": "forest", "location_id": "forest", "requirements": {"location": "forest"}, "target_difficulty": 0, "effects": {"success": {"resource_changes": {"wood": 1}}}},
            },
        }

    def test_player_choice_is_implicit_confirmation_and_bound_to_contract(self):
        world = self._option_world()
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world, meta={"current_location": "camp_core"})))
            compiled = engine.compile_options([
                {"id": "A", "label": "前往森林", "action": {"action_id": "stored-travel", "type": "TRAVEL", "target": "forest"}},
                {"id": "B", "label": "无变化伪选项", "action": {"action_id": "noop", "type": "SHORT_ACTION", "target": "camp_core"}},
                {"id": "C", "label": "直接调查森林", "action": {"action_id": "stored-explore", "type": "EXPLORATION", "target": "forest"}},
            ])
            self.assertEqual(set(compiled["options"]), {"A", "C"})
            self.assertEqual(compiled["contracts"]["C"]["action"]["type"], "ACTION_PLAN")
            self.assertEqual(compiled["contracts"]["C"]["preview"]["steps"][0]["action"]["type"], "TRAVEL")
            self.assertTrue(engine.state.meta["pending_options"]["options"]["A"]["preview"]["legal"])
            result = engine.execute_player_choice("A")
            self.assertEqual(result["selected_option"], "A")
            self.assertEqual(engine.state.meta["current_location"], "forest")
            self.assertNotIn("pending_options", engine.state.meta)
            self.assertTrue(engine.state.store.verify_projection(apply_event)["ok"])

    def test_zero_action_time_only_allows_reactions(self):
        world = self._option_world()
        with tempfile.TemporaryDirectory() as temp:
            state = GameState(Path(temp), minimal_state(world=world, meta={"current_location": "camp_core", "available_time_minutes": 0, "pending_reaction": {"id": "shadow", "effects": {"hp_delta": -1}}}))
            engine = GameEngine(state)
            compiled = engine.compile_options([
                {"id": "A", "action": {"action_id": "explore", "type": "EXPLORATION", "target": "forest"}},
                {"id": "B", "label": "应对黑影", "action": {"action_id": "react", "type": "REACTION", "goal": "挡住黑影"}},
            ])
            self.assertEqual(set(compiled["options"]), {"B"})
            result = engine.execute_player_choice("B")
            self.assertEqual(result["event"]["type"], "REACTION_RESOLVED")
            self.assertNotIn("pending_reaction", engine.state.meta)

    def test_player_raw_input_and_narrative_claim_are_auditable(self):
        world = self._option_world()
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world, meta={"current_location": "camp_core"})))
            action = {"action_id": "inspect", "type": "SHORT_ACTION", "target": "camp_core"}
            before = deepcopy(engine.state.data)
            result = engine.execute_action(action)
            raw = "  我检查基地的角落。  "
            record_narrative_turn(Path(temp), raw, "冷风掠过空车厢。", action=action, before_state=before, result=result)
            self.assertIn(raw, (Path(temp) / "conversation_log.md").read_text(encoding="utf-8"))
            with self.assertRaises(ValueError):
                validate_player_narrative("【系统】预览合法，确认执行。", result)

    def test_narrative_cannot_claim_uncommitted_state_change(self):
        world = self._option_world()
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world, meta={"current_location": "camp_core"})))
            action = {"action_id": "wait", "type": "SHORT_ACTION", "target": "camp_core"}
            before = deepcopy(engine.state.data)
            result = engine.execute_action(action)
            with self.assertRaises(ValueError):
                record_narrative_turn(Path(temp), "我等待。", "基地已加固。", action=action, before_state=before, result=result)

    def test_player_facing_result_hides_host_protocol(self):
        public = player_facing_result({"resolution": {"outcome": "普通成功", "probability": 0.8}, "event": {"data": {"action": {"action_id": "secret"}}}, "state": {"meta": {"current_location": "camp_core"}}})
        text = str(public)
        self.assertNotIn("probability", text)
        self.assertNotIn("action_id", text)

    def test_game_does_not_start_with_invalid_world_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "world.yaml").write_text("world: {}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                assert_startable(root)

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
        world["action_targets"][next(iter(world["areas"]))]["target_difficulty"] = 0
        area_id = next(iter(world["areas"]))
        research_id = next(key for key in world["action_targets"] if key not in {area_id, "camp_core", world["starting_npcs"][0]["id"]})
        self.assertEqual(world["action_targets"][research_id]["location_id"], research_id)
        self.assertEqual(world["action_targets"][research_id]["requirements"]["location"], research_id)
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
            enemy_definition_id = next(iter(bundle["enemy_definitions"]))
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
            self.assertEqual(len(plan["events"]), 3)
            self.assertEqual([event["type"] for event in plan["events"]], ["SOCIAL_RESOLVED", "TRAVEL_COMPLETED", "RESEARCH_RESOLVED"])
            self.assertEqual(engine.state.meta["current_location"], research_id)
            self.assertEqual(engine.state.meta["time_of_day"], "白天")
            travel = engine.execute_host_action({"action_id": "travel-1", "type": "TRAVEL", "target": area_id})
            self.assertEqual(travel["event"]["type"], "TRAVEL_COMPLETED")
            self.assertEqual(engine.state.meta["current_location"], area_id)
            explored = engine.execute_host_action({"action_id": "scout", "type": "EXPLORATION", "target": area_id, "risk_preference": "谨慎"})
            self.assertEqual(explored["event"]["type"], "EXPLORATION_RESOLVED")
            encounter_additions = explored["event"]["data"].get("encounter_additions", [])
            initial_entity_count = len(engine.state.data["world"]["encounter_entities"])
            if encounter_additions:
                self.assertEqual(encounter_additions[0]["target_ids"][0].split("_instance_")[0], enemy_definition_id)
                enemy_id = next(iter(engine.state.data["world"]["encounter_entities"]))
                combat = engine.execute_host_action({"action_id": "combat-1", "type": "COMBAT", "target": enemy_id})
                self.assertIn("target_deltas", combat["event"]["data"])
            if engine.state.meta.get("current_encounter_id"):
                engine.execute_host_action({"action_id": "extract-1", "type": "EXTRACT"})
            else:
                engine.execute_host_action({"action_id": "return-1", "type": "RETURN_TO_BASE"})
            self.assertEqual(engine.state.meta["current_location"], "camp_core")
            built = engine.execute_host_action({"action_id": "build-1", "type": "BUILD", "target": module_id})
            self.assertEqual(built["event"]["type"], "BUILDING_BUILT")
            engine.execute_host_action({"action_id": "travel-2", "type": "ENTER_LOCATION", "target": area_id})
            second_exploration = engine.execute_host_action({"action_id": "explore-2", "type": "EXPLORATION", "target": area_id, "risk_preference": "谨慎"})
            self.assertEqual(engine.state.data["world"]["enemy_definitions"][enemy_definition_id]["status"], "definition")
            if second_exploration["resolution"].get("outcome") in {"大成功", "普通成功", "成功但付出代价", "失败但获得部分信息"}:
                self.assertGreaterEqual(len(engine.state.data["world"]["encounter_entities"]), initial_entity_count + 1)
            else:
                self.assertGreaterEqual(len(engine.state.data["world"]["encounter_entities"]), initial_entity_count)
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
                "world.yaml": {"world": {"name": "注册表世界", "difficulty": "标准", "enemy_definitions": {"ice-zombie-def": {"id": "ice-zombie-def", "status": "definition", "attributes": {"strength": 3, "constitution": 3, "agility": 3, "spirit": 3}}}, "encounter_entities": {"ice-zombie-instance": {"id": "ice-zombie-instance", "definition_id": "ice-zombie-def", "status": "alive", "location_id": "edge", "hp": 30, "max_hp": 30, "attributes": {"strength": 3, "constitution": 3, "agility": 3, "spirit": 3}}}, "build_catalog": {"workbench": {"id": "workbench", "space_cost": 1, "build_time": 60, "build_cost": {"wood": 1}, "maintenance": {"wood": 1}}}, "areas": {"edge": {"monster_density_per_hour": 10, "route_coverage": 100, "search_efficiency": 100, "monster_alertness_modifier": 100, "kill_success_rate": 1, "ammo_per_kill": 1, "weapon_rate_per_hour": 20, "enemy_groups": [{"level": 1, "quality": "普通", "weight": 1, "drops": {"food": 1}}], "farmability_components": {"combat_advantage": 80, "enemy_information": 80, "kill_stability": 80, "sustainability": 80, "route_familiarity": 80, "extraction_ability": 80}}}, "player_talent": {}},
                },
                "player.yaml": {"player": {"level": 1, "exp": 0, "exp_to_next": 100, "attributes": {"strength": 8, "constitution": 5, "agility": 6, "spirit": 5}, "fatigue": 0, "hunger": 100, "mental": 100, "max_hp": 50, "hp": 50, "skills": []}},
                "base.yaml": {"base": {"space_total": 3, "space_used": 0, "modules": []}},
                "inventory.yaml": {"inventory": {"equipment": {"main_weapon": {"attack": 20, "durability": 2, "ammo_resource": "ammo", "ammo_cost": 1, "rate_per_hour": 20}}, "resources": {"ammo": 20, "wood": 1}}},
                "npcs.yaml": {"npcs": []}, "factions.yaml": {"factions": []}, "relationships.yaml": {"relationships": []}, "event_queue.yaml": {"event_queue": []},
                "meta.yaml": {"meta": {"current_turn": 1, "game_day": 1, "time_of_day": "白天", "world_name": "注册表世界", "difficulty": "标准", "available_time_minutes": 240, "current_location": "edge", "current_encounter_id": "encounter-1", "active_encounters": [{"id": "encounter-1", "location_id": "edge", "target_ids": ["ice-zombie-instance"], "participants": ["player", "ice-zombie-instance"], "status": "active"}], "event_format_version": 2}},
            }
            values["world.yaml"]["world"]["locations"] = [
                {"id": "camp_core", "name": "基地", "safe": True},
                {"id": "edge", "name": "边缘", "safe": False, "travel_minutes_from_base": 30, "travel_stamina_from_base": 5, "return_minutes": 30, "return_stamina_cost": 5, "extraction_minutes": 30, "extraction_stamina_cost": 5},
            ]
            values["world.yaml"]["world"]["areas"]["edge"]["location_id"] = "edge"
            values["meta.yaml"]["meta"]["available_time_minutes"] = 720
            for filename, value in values.items():
                (root / filename).write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
            (root / "event_log.md").write_text("# 事件日志\n", encoding="utf-8")
            (root / "story.md").write_text("# 故事摘要\n", encoding="utf-8")

            engine = GameEngine(load_game_state(root))
            combat = engine.execute_host_action({"action_id": "fight", "type": "COMBAT", "target": "ice-zombie-instance"})
            self.assertEqual(combat["event"]["type"], "COMBAT_RESOLVED")
            self.assertEqual(engine.state.inventory["resources"]["ammo"], 19.0)
            self.assertEqual(engine.state.inventory["equipment"]["main_weapon"]["durability"], 1.0)

            if engine.state.meta.get("current_encounter_id"):
                engine.execute_host_action({"action_id": "extract", "type": "EXTRACT"})
            else:
                engine.execute_host_action({"action_id": "return", "type": "RETURN_TO_BASE"})
            built = engine.execute_host_action({"action_id": "build", "type": "BUILD", "target": "workbench"})
            self.assertEqual(built["event"]["type"], "BUILDING_BUILT")
            self.assertEqual(engine.state.inventory["resources"]["wood"], 0.0)

            engine.execute_host_action({"action_id": "travel", "type": "TRAVEL", "target": "edge"})
            batch = engine.execute_host_action({"action_id": "farm", "type": "BATCH_ACTION", "target": "edge"})
            self.assertEqual(batch["event"]["type"], "BATCH_ACTION_RESOLVED")
            self.assertEqual(engine.state.meta["available_time_minutes"], 330)
            self.assertEqual(engine.state.player["fatigue"], 55)

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
            engine.state.meta["current_location"] = "camp_core"
            engine.state.meta["current_encounter_id"] = "encounter-direct"
            engine.state.meta["active_encounters"] = [{"id": "encounter-direct", "location_id": "camp_core", "target_ids": ["ice-zombie"], "participants": ["player", "ice-zombie"], "status": "active"}]
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

            slot_state = minimal_state(world=world, inventory={"resources": {"wood": 4, "ammo": 20}, "equipment": {"main_weapon": {"attack": 20, "accuracy": 10, "durability": 10}}})
            slot_state["base"]["space_total"] = 4
            slot_engine = GameEngine(GameState(root / "slot", slot_state))
            slot_preview = slot_engine.preview_action_plan({"action_id": "slot-plan", "type": "ACTION_PLAN", "plan_id": "slot-plan", "accept_dilution": True, "steps": [{"action_id": "slot-a", "type": "BUILD", "target": "module-a"}, {"action_id": "slot-b", "type": "BUILD", "target": "module-b"}]})
            self.assertFalse(slot_preview["legal"])
            self.assertEqual(slot_preview["components"]["action_slot_compatibility"], 0.5)
            self.assertLess(slot_preview["components"]["attention_compatibility"], 1.0)

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

    def test_movement_is_explicit_and_base_actions_are_location_bound(self):
        world = {
            "name": "空间约束世界",
            "difficulty": "标准",
            "starting_location": "camp_core",
            "locations": [
                {"id": "camp_core", "name": "基地", "safe": True},
                {"id": "forest", "name": "森林", "safe": False, "travel_minutes_from_base": 30, "travel_stamina_from_base": 5, "return_minutes": 25, "return_stamina_cost": 4, "extraction_minutes": 20, "extraction_stamina_cost": 3},
            ],
            "action_targets": {"forest": {"id": "forest", "location_id": "forest", "requirements": {"location": "forest"}}},
            "build_catalog": {"workbench": {"id": "workbench", "space_cost": 1, "build_time": 30, "build_cost": {"wood": 1}}},
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world, meta={"current_location": "camp_core"})))
            travel = engine.execute_host_action({"action_id": "travel", "type": "TRAVEL", "target": "forest"})
            self.assertEqual(travel["event"]["type"], "TRAVEL_COMPLETED")
            self.assertEqual(engine.state.meta["current_location"], "forest")
            self.assertEqual(engine.state.meta["available_time_minutes"], 690)
            with self.assertRaisesRegex(ValueError, "只能在基地"):
                engine.execute_host_action({"action_id": "rest-away", "type": "REST", "target": "camp_core"})
            with self.assertRaisesRegex(ValueError, "只能在基地"):
                engine.execute_host_action({"action_id": "build-away", "type": "BUILD", "target": "workbench"})

            engine.state.meta["current_encounter_id"] = "encounter-leave"
            engine.state.meta["active_encounters"] = [{"id": "encounter-leave", "location_id": "forest", "target_ids": [], "participants": ["player"], "status": "active"}]
            left = engine.execute_host_action({"action_id": "leave", "type": "LEAVE_ENCOUNTER"})
            self.assertEqual(left["event"]["type"], "ENCOUNTER_LEFT")
            self.assertIsNone(engine.state.meta["current_encounter_id"])
            self.assertEqual(engine.state.meta["current_location"], "forest")

            returned = engine.execute_host_action({"action_id": "return", "type": "RETURN_TO_BASE"})
            self.assertEqual(returned["event"]["type"], "RETURN_TO_BASE_COMPLETED")
            self.assertEqual(engine.state.meta["current_location"], "camp_core")

            engine.execute_host_action({"action_id": "travel-again", "type": "ENTER_LOCATION", "target": "forest"})
            engine.state.meta["current_encounter_id"] = "encounter-extract"
            engine.state.meta["active_encounters"] = [{"id": "encounter-extract", "location_id": "forest", "target_ids": [], "participants": ["player"], "status": "active"}]
            extracted = engine.execute_host_action({"action_id": "extract", "type": "EXTRACT"})
            self.assertEqual(extracted["event"]["type"], "EXTRACTION_COMPLETED")
            self.assertEqual(engine.state.meta["current_location"], "camp_core")
            self.assertEqual(engine.state.meta["encounter_history"][-1]["status"], "escaped")

    def test_movement_is_deterministic_but_extraction_rules_are_hard_gates(self):
        world = {
            "name": "路线规则世界",
            "difficulty": "标准",
            "starting_location": "camp_core",
            "locations": [
                {"id": "camp_core", "name": "基地", "safe": True},
                {
                    "id": "forest",
                    "name": "森林",
                    "safe": False,
                    "travel_minutes_from_base": 30,
                    "travel_stamina_from_base": 5,
                    "extraction_minutes": 20,
                    "extraction_stamina_cost": 3,
                    "extraction_rule": {"return_to": "camp_core", "deadline_minutes": 120},
                },
            ],
            "action_targets": {"forest": {"id": "forest", "location_id": "forest", "requirements": {"location": "forest"}}},
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world, meta={"time_of_day": "白天", "day_elapsed_minutes": 120})))
            travel = {"action_id": "travel", "type": "TRAVEL", "target": "forest"}
            travel_preview = engine.preview_host_action(travel)
            self.assertTrue(travel_preview["legal"], travel_preview)
            self.assertTrue(travel_preview["resolution"]["movement_success"])
            self.assertEqual(travel_preview["resolution"]["probability"], 1.0)
            self.assertNotIn("random_roll", travel_preview["resolution"])
            engine.execute_host_action(travel)

            engine.state.meta["current_encounter_id"] = "encounter-expired"
            engine.state.meta["active_encounters"] = [{
                "id": "encounter-expired",
                "location_id": "forest",
                "target_ids": [],
                "participants": ["player"],
                "status": "active",
                "extraction_deadline_at_minutes": engine._timeline_minutes() - 1,
            }]
            expired = engine.preview_host_action({"action_id": "extract-expired", "type": "EXTRACT"})
            self.assertFalse(expired["legal"])
            self.assertTrue(any("截止时间" in error for error in expired["errors"]))
            with self.assertRaisesRegex(ValueError, "截止时间"):
                engine.execute_host_action({"action_id": "extract-expired", "type": "EXTRACT"})
            self.assertEqual(engine.state.meta["current_location"], "forest")
            self.assertEqual(engine.state.meta["current_encounter_id"], "encounter-expired")

            engine.state.meta["active_encounters"][0]["extraction_deadline_at_minutes"] = engine._timeline_minutes() + 10
            with self.assertRaisesRegex(ValueError, "剩余时间不足"):
                engine.execute_host_action({"action_id": "extract-too-late", "type": "EXTRACT"})
            engine.state.meta["active_encounters"][0]["extraction_deadline_at_minutes"] = engine._timeline_minutes() + 120
            extracted = engine.execute_host_action({"action_id": "extract-valid", "type": "EXTRACT"})
            self.assertEqual(extracted["event"]["type"], "EXTRACTION_COMPLETED")
            self.assertEqual(engine.state.meta["current_location"], "camp_core")
            self.assertIsNone(engine.state.meta["current_encounter_id"])

            with self.assertRaisesRegex(ValueError, "拒绝修改地点状态"):
                engine._domain_effects({"type": "TRAVEL", "target": "forest"}, {"movement_success": False})

    def test_opportunity_availability_uses_actual_current_period(self):
        constraints = {
            "availability": {"allowed_periods": ["白天", "黄昏"]},
            "reservation": {"exclusive_group": "field_exploration", "window_id": "current_period", "capacity": 1},
        }
        world = {
            "name": "窗口规则世界",
            "difficulty": "标准",
            "starting_location": "camp_core",
            "locations": [{"id": "camp_core", "name": "基地", "safe": True}, {"id": "forest", "name": "森林", "safe": False}],
            "action_targets": {
                "forest": {"id": "forest", "location_id": "forest", "requirements": {"location": "forest"}, "constraints": constraints},
                "camp_core": {"id": "camp_core", "location_id": "camp_core", "constraints": constraints, "effects": {}},
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world, meta={"current_location": "camp_core", "time_of_day": "清晨", "day_elapsed_minutes": 0})))
            with self.assertRaisesRegex(ValueError, "当前时段不可执行"):
                engine.execute_host_action({"action_id": "too-early", "type": "EXPLORATION", "target": "forest"})

            engine.state.meta.update({"time_of_day": "白天", "day_elapsed_minutes": 120, "available_time_minutes": 720})
            engine.state.player["action_slot_capacity"] = 2
            plan = engine.preview_action_plan({
                "action_id": "period-plan",
                "type": "ACTION_PLAN",
                "plan_id": "period-plan",
                "accept_dilution": True,
                "steps": [
                    {"action_id": "day-rest", "type": "REST", "target": "camp_core"},
                    {"action_id": "dusk-short", "type": "SHORT_ACTION", "target": "camp_core"},
                ],
            })
            self.assertTrue(plan["legal"], plan)
            self.assertEqual([item["start_period"] for item in plan["steps"]], ["白天", "黄昏"])
            self.assertEqual(plan["components"]["opportunity_window_compatibility"], 1.0)

    def test_action_plan_compiler_inserts_route_and_return_steps(self):
        world = {
            "name": "计划路线世界",
            "difficulty": "标准",
            "starting_location": "camp_core",
            "locations": [
                {"id": "camp_core", "name": "基地", "safe": True},
                {"id": "forest", "name": "森林", "safe": False, "travel_minutes_from_base": 30, "extraction_minutes": 20, "extraction_stamina_cost": 3},
            ],
            "action_targets": {
                "forest": {"id": "forest", "location_id": "forest", "requirements": {"location": "forest"}, "effects": {}},
                "camp_core": {"id": "camp_core", "location_id": "camp_core", "requirements": {"location": "camp_core"}, "effects": {}},
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world, player={"level": 1, "exp": 0, "exp_to_next": 100, "attributes": {"strength": 8, "constitution": 8, "agility": 8, "spirit": 8}, "fatigue": 0, "hunger": 100, "mental": 100, "max_hp": 50, "hp": 50, "skills": [], "action_slot_capacity": 2})))
            plan = engine.preview_action_plan({
                "action_id": "route-plan",
                "type": "ACTION_PLAN",
                "plan_id": "route-plan",
                "accept_dilution": True,
                "steps": [
                    {"action_id": "field-work", "type": "SHORT_ACTION", "target": "forest"},
                    {"action_id": "base-work", "type": "SHORT_ACTION", "target": "camp_core"},
                ],
            })
            self.assertTrue(plan["legal"], plan)
            self.assertEqual([item["action"]["type"] for item in plan["steps"]], ["TRAVEL", "SHORT_ACTION", "EXTRACT", "SHORT_ACTION"])
            self.assertEqual([item["action"].get("target") for item in plan["steps"]], ["forest", "forest", None, "camp_core"])
            result = engine.execute_action_plan({
                "action_id": "route-plan",
                "type": "ACTION_PLAN",
                "plan_id": "route-plan",
                "accept_dilution": True,
                "steps": [
                    {"action_id": "field-work", "type": "SHORT_ACTION", "target": "forest"},
                    {"action_id": "base-work", "type": "SHORT_ACTION", "target": "camp_core"},
                ],
            })
            self.assertEqual([event["type"] for event in result["events"]], ["TRAVEL_COMPLETED", "ACTION_RESOLVED", "EXTRACTION_COMPLETED", "ACTION_RESOLVED"])
            self.assertEqual(engine.state.meta["current_location"], "camp_core")

    def test_plan_hard_constraints_come_from_registry_not_llm_tags(self):
        def profile(action_id, value, window_id=None, capacity=1, constraints=True):
            result = {"id": action_id, "location_id": "camp_core", "requirements": {"location": "camp_core"}}
            if constraints:
                result["constraints"] = {"commitment_axis": "faction_loyalty", "commitment_value": value, "exclusive_group": "evening_major_action", "window_id": window_id, "window_capacity": capacity}
            return result

        world = {
            "name": "结构化计划世界",
            "difficulty": "标准",
            "action_targets": {
                "a": profile("a", "faction_A", "morning", 2),
                "b": profile("b", "faction_B", "morning", 2),
                "c": profile("c", "faction_A", "evening", 1),
                "d": profile("d", "ignored", None, 1, constraints=False),
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world, meta={"current_location": "camp_core"})))

            same_commitment = engine.preview_action_plan({"action_id": "same", "type": "ACTION_PLAN", "plan_id": "same", "accept_dilution": True, "steps": [{"action_id": "a1", "type": "SHORT_ACTION", "target": "a"}, {"action_id": "a2", "type": "SHORT_ACTION", "target": "a"}]})
            self.assertEqual(same_commitment["components"]["commitment_compatibility"], 1.0)
            self.assertEqual(same_commitment["components"]["opportunity_window_compatibility"], 1.0)

            different_commitment = engine.preview_action_plan({"action_id": "different", "type": "ACTION_PLAN", "plan_id": "different", "accept_dilution": True, "steps": [{"action_id": "a", "type": "SHORT_ACTION", "target": "a"}, {"action_id": "b", "type": "SHORT_ACTION", "target": "b"}]})
            self.assertEqual(different_commitment["components"]["commitment_compatibility"], 0.35)
            self.assertEqual(different_commitment["components"]["opportunity_window_compatibility"], 1.0)

            different_windows = engine.preview_action_plan({"action_id": "windows", "type": "ACTION_PLAN", "plan_id": "windows", "accept_dilution": True, "steps": [{"action_id": "a", "type": "SHORT_ACTION", "target": "a"}, {"action_id": "c", "type": "SHORT_ACTION", "target": "c"}]})
            self.assertEqual(different_windows["components"]["commitment_compatibility"], 1.0)
            self.assertEqual(different_windows["components"]["opportunity_window_compatibility"], 1.0)

            llm_only_tags = engine.preview_action_plan({"action_id": "tags", "type": "ACTION_PLAN", "plan_id": "tags", "accept_dilution": True, "steps": [{"action_id": "d1", "type": "SHORT_ACTION", "target": "d", "tags": ["commitment:faction_A", "window:morning"]}, {"action_id": "d2", "type": "SHORT_ACTION", "target": "d", "tags": ["commitment:faction_B", "window:morning"]}]})
            self.assertEqual(llm_only_tags["components"]["commitment_compatibility"], 1.0)
            self.assertEqual(llm_only_tags["components"]["opportunity_window_compatibility"], 1.0)

    def test_encounter_instances_expire_and_resolve(self):
        target = {"id": "wolf-instance", "definition_id": "wolf", "status": "alive", "hp": 20, "location_id": "forest", "attributes": {"strength": 2, "constitution": 2, "agility": 2, "spirit": 2}}
        state = minimal_state(
            meta={"current_location": "forest", "current_encounter_id": "encounter-1", "active_encounters": [{"id": "encounter-1", "location_id": "forest", "target_ids": ["wolf-instance"], "participants": ["player", "wolf-instance"], "status": "active"}]},
            world={"name": "遭遇生命周期世界", "difficulty": "标准", "enemy_definitions": {"wolf": {"id": "wolf", "status": "definition"}}, "encounter_entities": {"wolf-instance": target}},
        )
        projected = apply_event(state, standard_event("resolve", "COMBAT_RESOLVED", "player", "wolf-instance", {"encounter_updates": [{"id": "encounter-1", "target_ids": [], "participants": ["player"], "status": "resolved"}], "time_cost": 0}, 1, "Day 1 清晨"))
        self.assertEqual(projected["meta"]["active_encounters"], [])
        self.assertEqual(projected["meta"]["current_encounter_id"], None)
        self.assertEqual(projected["meta"]["encounter_history"][0]["status"], "resolved")
        expiring = deepcopy(state)
        expiring["meta"]["active_encounters"][0]["expires_turn"] = 1
        expired = apply_event(expiring, standard_event("expire", "ACTION_RESOLVED", "player", None, {"time_cost": 0}, 1, "Day 1 清晨"))
        self.assertEqual(expired["meta"]["active_encounters"], [])
        self.assertEqual(expired["meta"]["encounter_history"][0]["status"], "expired")

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
        world = {"name": "地点世界", "difficulty": "标准", "encounter_entities": {"wolf": target}}
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(world=world)))
            with self.assertRaises(ValueError):
                engine.execute_host_action({"action_id": "wrong-place", "type": "COMBAT", "target": "wolf"})
            engine.state.meta["current_location"] = "forest"
            engine.state.meta["current_encounter_id"] = "encounter-1"
            engine.state.meta["active_encounters"] = [{"id": "encounter-1", "location_id": "forest", "target_ids": ["wolf"], "participants": ["player", "wolf"], "status": "active"}]
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


class OptionLegalityGateTests(unittest.TestCase):
    """选项编译硬门槛：preview.legal 必须为 True 才能展示。"""

    def _period_world(self):
        return {
            "name": "时段门槛世界",
            "difficulty": "标准",
            "starting_location": "camp_core",
            "locations": [
                {"id": "camp_core", "name": "基地", "safe": True, "travel_minutes_from_base": 0},
                {"id": "scrap_yard", "name": "废铁站场", "safe": False, "travel_minutes_from_base": 30, "travel_stamina_from_base": 5},
            ],
            "action_targets": {
                "camp_core": {"id": "camp_core", "location_id": "camp_core", "target_difficulty": 0, "effects": {}},
                "scrap_yard": {
                    "id": "scrap_yard",
                    "location_id": "scrap_yard",
                    "requirements": {"location": "scrap_yard"},
                    "constraints": {"availability": {"allowed_periods": ["白天", "黄昏"]}},
                    "target_difficulty": 5,
                    "effects": {
                        "success": {"resource_changes": {"scrap": 1}},
                        "partial_failure": {"knowledge_additions": ["scrap_layout"]},
                    },
                },
            },
        }

    def test_compile_options_filters_period_illegal_actions(self):
        """清晨时探索废铁站场（允许白天/黄昏）不应出现在选项中。"""
        world = self._period_world()
        world["action_targets"]["scrap_yard_obs"] = {
            "id": "scrap_yard_obs",
            "location_id": "scrap_yard",
            "target_difficulty": 5,
            "effects": {"success": {"knowledge_additions": ["scrap_layout"]}},
        }
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(
                world=world,
                meta={"current_location": "scrap_yard", "time_of_day": "清晨", "day_elapsed_minutes": 0},
            )))
            compiled = engine.compile_options([
                {"id": "A", "label": "探索废铁站场", "action": {"action_id": "explore-illegal", "type": "EXPLORATION", "target": "scrap_yard"}},
                {"id": "B", "label": "观察周围", "action": {"action_id": "observe", "type": "SHORT_ACTION", "target": "scrap_yard_obs", "goal": "观察威胁"}},
            ])
            self.assertNotIn("A", compiled["options"])
            self.assertIn("B", compiled["options"])

    def test_compile_options_passes_period_legal_actions(self):
        """白天时探索废铁站场应正常出现在选项中。"""
        world = self._period_world()
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(
                world=world,
                meta={"current_location": "scrap_yard", "time_of_day": "白天", "day_elapsed_minutes": 120},
            )))
            compiled = engine.compile_options([
                {"id": "A", "label": "探索废铁站场", "action": {"action_id": "explore-legal", "type": "EXPLORATION", "target": "scrap_yard"}},
            ])
            self.assertIn("A", compiled["options"])
            self.assertTrue(compiled["contracts"]["A"]["preview"]["legal"])

    def test_wait_action_advances_time(self):
        """WAIT 行动应推进时间并更新时段。"""
        world = self._period_world()
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(
                world=world,
                meta={"current_location": "camp_core", "time_of_day": "清晨", "day_elapsed_minutes": 0},
            )))
            preview = engine.preview_host_action({"action_id": "wait-test", "type": "WAIT", "parameters": {"wait_minutes": 120}})
            self.assertTrue(preview["legal"], preview)
            self.assertEqual(preview["resolution"]["wait_minutes"], 120.0)
            result = engine.execute_host_action({"action_id": "wait-test", "type": "WAIT", "parameters": {"wait_minutes": 120}})
            self.assertEqual(result["event"]["type"], "WAIT_COMPLETED")
            self.assertEqual(engine.state.meta["time_of_day"], "白天")
            self.assertEqual(engine.state.meta["day_elapsed_minutes"], 120)

    def test_plan_wait_then_explore_legal_when_period_advances(self):
        """WAIT 120min → EXPLORATION 在清晨提交应合法（等待后进入白天）。"""
        world = self._period_world()
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(
                world=world,
                meta={"current_location": "scrap_yard", "time_of_day": "清晨", "day_elapsed_minutes": 0},
            )))
            plan = {
                "action_id": "plan-wait-explore",
                "type": "ACTION_PLAN",
                "plan_id": "plan-wait-explore",
                "accept_dilution": True,
                "steps": [
                    {"action_id": "step-wait", "type": "WAIT", "parameters": {"wait_minutes": 120}, "goal": "等待天亮"},
                    {"action_id": "step-explore", "type": "EXPLORATION", "target": "scrap_yard", "goal": "探索废铁站场"},
                ],
            }
            preview = engine.preview_host_action(plan)
            self.assertTrue(preview["legal"], preview)

    def test_plan_wait_insufficient_still_illegal(self):
        """WAIT 60min → EXPLORATION 在清晨提交仍不合法（60min后仍是清晨）。"""
        world = self._period_world()
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(
                world=world,
                meta={"current_location": "scrap_yard", "time_of_day": "清晨", "day_elapsed_minutes": 0},
            )))
            plan = {
                "action_id": "plan-short-wait",
                "type": "ACTION_PLAN",
                "plan_id": "plan-short-wait",
                "accept_dilution": True,
                "steps": [
                    {"action_id": "step-wait", "type": "WAIT", "parameters": {"wait_minutes": 60}, "goal": "短暂等待"},
                    {"action_id": "step-explore", "type": "EXPLORATION", "target": "scrap_yard", "goal": "探索废铁站场"},
                ],
            }
            preview = engine.preview_host_action(plan)
            self.assertFalse(preview["legal"])
            self.assertTrue(any("时段" in err for err in preview["errors"]))

    def test_stale_options_rejected_after_state_change(self):
        """选项绑定 state_turn；状态变化后旧选项被拒绝。"""
        world = self._period_world()
        with tempfile.TemporaryDirectory() as temp:
            engine = GameEngine(GameState(Path(temp), minimal_state(
                world=world,
                meta={"current_location": "camp_core", "time_of_day": "白天", "day_elapsed_minutes": 120},
            )))
            compiled = engine.compile_options([
                {"id": "A", "label": "休息", "action": {"action_id": "rest-day", "type": "REST", "target": "camp_core"}},
            ])
            self.assertIn("A", compiled["options"])
            engine.execute_player_choice("A")
            self.assertNotIn("pending_options", engine.state.meta)
            review = engine.preview_player_choice("A")
            self.assertFalse(review["legal"])


if __name__ == "__main__":
    unittest.main()
