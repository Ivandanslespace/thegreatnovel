from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tgn import (  # noqa: E402
    CampaignStore,
    InvalidActionError,
    available_actions,
    create_campaign,
    settle_action,
    status_packet,
)
from tgn.cli import runtime_path  # noqa: E402
from tgn.exporter import render_markdown  # noqa: E402
from tgn.locales import normalize_locale  # noqa: E402
from tgn.narrative import narration_brief, project_chapters  # noqa: E402
from tgn.persistence import StorageError  # noqa: E402


class V1Tests(unittest.TestCase):
    maxDiff = None

    def cli(
        self,
        runtime: str | os.PathLike[str],
        *args: str,
        expect: int = 0,
        cwd: str | os.PathLike[str] | None = None,
    ) -> tuple[dict, subprocess.CompletedProcess[str]]:
        process = subprocess.run(
            [sys.executable, str(ROOT / "game.py"), "--runtime", str(runtime), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        self.assertEqual(process.returncode, expect, process.stderr or process.stdout)
        self.assertTrue(process.stdout.strip(), "CLI must emit one JSON object")
        payload = json.loads(process.stdout)
        self.assertEqual(len([line for line in process.stdout.splitlines() if line.strip()]), 1)
        return payload, process

    @staticmethod
    def save_path(runtime: Path, campaign_id: str) -> Path:
        return runtime / "saves" / "campaigns" / f"{campaign_id}.json"

    @staticmethod
    def authoritative_state(campaign) -> dict:
        data = campaign.to_dict()
        data.pop("chapters", None)
        data.pop("status_digest", None)
        return data

    def test_locales_aliases_unicode_and_public_knowledge_gate(self):
        aliases = {"zh": "zh-CN", "fr": "fr-FR", "en-US": "en", "ar-sa": "ar"}
        for alias, expected in aliases.items():
            self.assertEqual(normalize_locale(alias), expected)

        premises = {
            "zh-CN": "一座靠出售记忆维持照明的沉没城市",
            "fr-FR": "Une cité engloutie éclaire ses rues avec des souvenirs",
            "en": "A drowned city lights its streets with traded memories",
            "ar": "مدينة غارقة تضيء شوارعها بالذكريات المتداولة",
        }
        for locale, premise in premises.items():
            campaign, packet = create_campaign(premise, locale, seed=11, campaign_id=f"gate-{locale}")
            self.assertIsNone(packet["world"]["core_rule"])
            self.assertFalse(packet["world"]["leverage"]["discovered"])
            self.assertNotIn("hidden", json.dumps(packet, ensure_ascii=False))
            campaign, packet = settle_action(campaign, "observe_rule")
            self.assertTrue(packet["world"]["core_rule"])
            self.assertIn("formula", packet["world"]["leverage"])
            self.assertNotIn("\ufffd", json.dumps(packet, ensure_ascii=False))

    def test_deterministic_sequence_and_invalid_action_has_no_side_effect(self):
        left, _ = create_campaign("memory archive", "en", seed=42, campaign_id="det")
        right, _ = create_campaign("memory archive", "en", seed=42, campaign_id="det")
        for action_id in ("observe_rule", "convert_leverage"):
            self.assertIn(action_id, {a["action_id"] for a in available_actions(left)})
            left, _ = settle_action(left, action_id)
            right, _ = settle_action(right, action_id)
        self.assertEqual(left.to_dict(), right.to_dict())

        before = copy.deepcopy(left.to_dict())
        with self.assertRaises(InvalidActionError):
            settle_action(left, "observe_and_trade_and_fight")
        self.assertEqual(before, left.to_dict())

    def test_failure_cost_world_tick_and_opportunity_bonus_are_public(self):
        failing = None
        before = None
        packet = None
        for seed in range(100):
            campaign, _ = create_campaign("memory archive", "en", seed=seed, campaign_id=f"fail-{seed}")
            campaign, _ = settle_action(campaign, "observe_rule")
            prior = copy.deepcopy(campaign)
            campaign, result = settle_action(campaign, "convert_leverage")
            if result["latest_event"]["success"] is False:
                failing, before, packet = campaign, prior, result
                break
        self.assertIsNotNone(failing, "at least one deterministic seed must exercise failure")
        facts = packet["latest_event"]
        self.assertEqual(facts["opportunity_bonus"], 2)
        self.assertEqual(facts["cost"]["energy"], 1)
        self.assertEqual(facts["cost"]["insight"], 1)
        self.assertEqual(facts["cost"]["core"], 1)
        self.assertEqual(facts["cost"]["risk_exposure"], 1)
        self.assertLess(failing.player["resources"]["vitality"], before.player["resources"]["vitality"])
        self.assertGreater(failing.player["resources"]["risk_exposure"], before.player["resources"]["risk_exposure"])
        self.assertTrue(facts["world_response"]["rival"])
        self.assertGreater(failing.clock, before.clock)

    def test_real_growth_path_unlocks_and_preserves_tier_two_progress(self):
        campaign, _ = create_campaign("grain production beneath a moving sky", "en", seed=0, campaign_id="route")
        seen: set[str] = set()
        before_growth = None
        before_counts = None
        for _ in range(120):
            actions = {item["action_id"] for item in available_actions(campaign)}
            seen |= actions
            if "ascend" in actions:
                before_counts = (len(campaign.factions), len(campaign.world["regions"]), len(campaign.opportunities))
                before_growth = (
                    campaign.player["lifetime_control"],
                    copy.deepcopy(campaign.player["abilities"]),
                    set(campaign.player["assets"]),
                )
                campaign, _ = settle_action(campaign, "ascend")
                if campaign.tier == 2:
                    break
                continue
            if "core_rule" not in campaign.knowledge:
                choice = "observe_rule"
            elif "recover" in actions and (
                campaign.player["resources"]["energy"] < 2
                or campaign.player["resources"]["vitality"] <= 1
            ):
                choice = "recover"
            elif "convert_leverage" in actions:
                choice = "convert_leverage"
            elif campaign.player["resources"]["insight"] < 1:
                choice = "observe_rule"
            else:
                choice = "gather_resource"
            campaign, _ = settle_action(campaign, choice)

        self.assertEqual(campaign.tier, 2)
        self.assertTrue({"negotiate", "organize", "exploit_rule", "ascend"} <= seen)
        self.assertGreater(len(campaign.factions), before_counts[0])
        self.assertGreater(len(campaign.world["regions"]), before_counts[1])
        self.assertGreater(len(campaign.opportunities), before_counts[2])
        self.assertGreaterEqual(campaign.player["lifetime_control"], before_growth[0])
        self.assertTrue(before_growth[2] <= set(campaign.player["assets"]))
        for name, value in before_growth[1].items():
            self.assertGreaterEqual(campaign.player["abilities"][name], value)
        self.assertNotIn("ascend", {item["action_id"] for item in available_actions(campaign)})

    def test_world_control_axes_and_same_axis_worlds_are_materially_distinct(self):
        premises = {
            "resource_production": "粮食生产城",
            "knowledge_memory": "记忆档案城",
            "relationship_trust": "信任盟约城",
            "law_identity": "法律身份城",
            "space_environment": "空间路线城",
            "causal_resonance": "因果共振城",
        }
        effects = set()
        for expected_axis, premise in premises.items():
            campaign, _ = create_campaign(premise, "zh-CN", seed=1, campaign_id=expected_axis)
            self.assertEqual(campaign.world["control_axis"], expected_axis)
            effects.add(campaign.world["leverage"]["effect"])
        self.assertEqual(len(effects), 6)

        first, _ = create_campaign("记忆档案甲", "zh-CN", seed=1, campaign_id="variant-a")
        second, _ = create_campaign("记忆档案乙", "zh-CN", seed=2, campaign_id="variant-b")
        self.assertNotEqual([f["name"] for f in first.factions], [f["name"] for f in second.factions])
        self.assertFalse(any(f["name"][-1:].isdigit() for f in first.factions + second.factions))

    def test_store_atomic_roundtrip_and_two_kinds_of_tampering_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = CampaignStore(root)
            campaign, _ = create_campaign("memory city", "en", seed=4, campaign_id="secure")
            path = store.save(campaign)
            self.assertTrue(store.verify("secure"))
            self.assertFalse(list(path.parent.glob("*.tmp")))

            data = json.loads(path.read_text(encoding="utf-8"))
            data["events"][0]["event_hash"] = "0" * 64
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(StorageError):
                store.load("secure")

            campaign, _ = create_campaign("memory city", "en", seed=5, campaign_id="finished-tamper")
            path = store.save(campaign)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["finished"] = True
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(StorageError):
                store.load("finished-tamper")

    def test_default_campaign_ids_and_seeds_do_not_overwrite(self):
        first, _ = create_campaign("same premise", "zh-CN")
        second, _ = create_campaign("same premise", "zh-CN")
        self.assertNotEqual(first.campaign_id, second.campaign_id)
        self.assertNotEqual(first.seed, second.seed)

    def test_cli_four_language_flow_auto_saves_manuscript_and_final_export(self):
        premises = {
            "zh-CN": "记忆城市",
            "fr-FR": "cité de mémoire",
            "en": "memory city",
            "ar": "مدينة الذاكرة",
        }
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            ids = set()
            for locale, premise in premises.items():
                runtime = base / locale
                inbox = runtime / "inbox"
                inbox.mkdir(parents=True)
                premise_path = inbox / "premise.txt"
                premise_path.write_text(premise, encoding="utf-8")
                created, _ = self.cli(runtime, "new", "--locale", locale, "--premise-file", str(premise_path), "--seed", "9")
                campaign_id = created["campaign_id"]
                ids.add(campaign_id)
                self.assertIn("brief", created)
                self.assertIsNone(created["packet"]["world"]["core_rule"])
                save = self.save_path(runtime, campaign_id)
                manuscript = Path(created["manuscript"])
                self.assertTrue(save.is_file() and manuscript.is_file())

                acted, _ = self.cli(runtime, "act", "--campaign", campaign_id, "--action", "observe_rule")
                self.assertTrue(acted["packet"]["world"]["core_rule"])
                self.assertGreaterEqual(manuscript.read_text(encoding="utf-8").count("## "), 2)

                finished, _ = self.cli(runtime, "finish", "--campaign", campaign_id)
                self.assertIn("brief", finished)
                self.assertTrue(Path(finished["manuscript"]).is_file())
                final_path = Path(finished["export"])
                self.assertTrue(final_path.is_file())
                if locale == "ar":
                    final_text = final_path.read_text(encoding="utf-8")
                    self.assertIn('dir="rtl"', final_text)
                    self.assertNotIn('<div dir="rtl"><bdi><div dir="rtl">', final_text)
            self.assertEqual(len(ids), 4)

    def test_narration_changes_only_projection_and_updates_draft_and_final(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            created, _ = self.cli(runtime, "new", "--locale", "en", "--premise", "memory city", "--seed", "12")
            campaign_id = created["campaign_id"]
            self.cli(runtime, "act", "--campaign", campaign_id, "--action", "observe_rule")

            store = CampaignStore(runtime / "saves")
            before = store.load(campaign_id)
            authority = self.authoritative_state(before)
            draft_dir = runtime / "drafts" / campaign_id
            draft_dir.mkdir(parents=True)
            draft = draft_dir / "turn-1.md"
            draft.write_text("A close third-person chapter grounded in the settled facts.", encoding="utf-8")
            narrated, _ = self.cli(runtime, "narrate", "--campaign", campaign_id, "--turn", "1", "--file", str(draft))
            after = store.load(campaign_id)
            self.assertEqual(authority, self.authoritative_state(after))
            self.assertIn("A close third-person", Path(narrated["manuscript"]).read_text(encoding="utf-8"))

            finished, _ = self.cli(runtime, "finish", "--campaign", campaign_id)
            final_turn = finished["brief"]["turn"]
            final_draft = draft_dir / f"turn-{final_turn}.md"
            final_draft.write_text("The final chapter preserves every earned consequence.", encoding="utf-8")
            final_narrated, _ = self.cli(runtime, "narrate", "--campaign", campaign_id, "--turn", str(final_turn), "--file", str(final_draft))
            self.assertIn("export", final_narrated)
            for key in ("manuscript", "export"):
                self.assertIn("The final chapter", Path(final_narrated[key]).read_text(encoding="utf-8"))

    def test_invalid_cli_action_is_structured_and_save_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            created, _ = self.cli(runtime, "new", "--premise", "memory city", "--seed", "7")
            campaign_id = created["campaign_id"]
            save = self.save_path(runtime, campaign_id)
            before = save.read_bytes()
            failed, process = self.cli(runtime, "act", "--campaign", campaign_id, "--action", "not_real", expect=2)
            self.assertFalse(failed["ok"])
            self.assertEqual(failed["error"]["type"], "domain_error")
            self.assertEqual(process.stderr, "")
            self.assertEqual(before, save.read_bytes())

    def test_cli_rejects_out_of_runtime_files_and_parser_errors_are_json(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            runtime = Path(temp)
            foreign = Path(outside) / "premise.txt"
            foreign.write_text("do not read this", encoding="utf-8")
            failed, _ = self.cli(runtime, "new", "--premise-file", str(foreign), expect=2)
            self.assertFalse(failed["ok"])
            self.assertIn("runtime", failed["error"]["message"].lower())

            parsed, process = self.cli(runtime, "act", expect=2)
            self.assertFalse(parsed["ok"])
            self.assertEqual(process.stderr, "")

    def test_default_runtime_is_project_anchored_and_env_override_wins(self):
        original_cwd = Path.cwd()
        original_env = os.environ.get("TGN_RUNTIME_DIR")
        with tempfile.TemporaryDirectory() as temp:
            try:
                os.environ.pop("TGN_RUNTIME_DIR", None)
                os.chdir(temp)
                self.assertEqual(runtime_path(), (ROOT / "runtime").resolve())
                override = Path(temp) / "override"
                os.environ["TGN_RUNTIME_DIR"] = str(override)
                self.assertEqual(runtime_path(), override.resolve())
            finally:
                os.chdir(original_cwd)
                if original_env is None:
                    os.environ.pop("TGN_RUNTIME_DIR", None)
                else:
                    os.environ["TGN_RUNTIME_DIR"] = original_env

    def test_novel_projection_never_serializes_hidden_state(self):
        campaign, _ = create_campaign("memory city", "en", seed=3, campaign_id="novel")
        campaign.hidden["contradiction"] = "SECRET_NEVER_EXPORT"
        project_chapters(campaign)
        text = render_markdown(campaign)
        self.assertNotIn("SECRET_NEVER_EXPORT", text)
        self.assertIn('campaign_id: "novel"', text)

    def test_agents_protocol_contains_executable_chat_contract(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        required = (
            "开始游戏",
            "commencer le jeu",
            "ابدأ اللعبة",
            "简体中文（默认）",
            "packet.available_actions",
            "success:false",
            "CLI 返回非零",
            "premise-file",
            "narrate",
            "finish",
            "verify",
            "1200–2200",
            "不得读取其他项目",
            "karpathy-guidelines",
        )
        for token in required:
            self.assertIn(token, agents)


if __name__ == "__main__":
    unittest.main()
