from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tgn.service import GameService
from tgn.storage import CampaignStoreError


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts" / "tgn.py"


def test_service_full_lifecycle_autosaves_and_exports(tmp_path) -> None:
    service = GameService(tmp_path)
    started = service.start(
        "我想在潮汐与盐雾支配的港口重建供给网络",
        campaign_id="service-frost",
        world_id="frost_harbor",
        seed=2,
    )
    assert started["status"] == "ACTIVE"
    assert started["pending_narration"]["context"]["opening"] is True
    assert "seed" not in json.dumps(started["player_view"], ensure_ascii=False)
    with pytest.raises(CampaignStoreError):
        service.actions("service-frost")

    opening = service.narrate("service-frost", fallback=True)
    draft = Path(opening["novel_draft"])
    assert draft.is_file() and "## 序章" in draft.read_text(encoding="utf-8")

    preview = service.preview("service-frost", "inspect_grid")
    assert preview["legal"] is True and preview["expected_turn"] == 0
    committed = service.act_by_id(
        "service-frost", "inspect_grid", "turn-1", expected_turn=0
    )
    assert committed["turn"] == 1
    assert committed["narration_request"]["required_claims"]
    service.narrate("service-frost", fallback=True)
    draft.unlink()
    recovered = service.recover_exports("service-frost")
    assert recovered["verified"]["ok"] is True and draft.is_file()
    resumed = service.resume("service-frost")
    assert resumed["player_view"]["panel"]["turn"] == 1
    assert service.verify("service-frost")["ok"] is True

    ending = service.end("service-frost", "end-1", "player_requested")
    assert ending["status"] == "STOPPING"
    final = service.narrate("service-frost", fallback=True)
    assert final["status"] == "STOPPED"
    novel = Path(final["final_novel"])
    text = novel.read_text(encoding="utf-8")
    assert "## 序章" in text and "## 第 1 章" in text and "## 尾声" in text
    assert service.verify("service-frost")["ok"] is True
    with pytest.raises(CampaignStoreError):
        service.act_by_id("service-frost", "rest", "post-ending")


def _cli(tmp_path: Path, *args: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [sys.executable, str(LAUNCHER), "--saves-root", str(tmp_path), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_repository_launcher_is_json_only_and_recovers_pending_turn(tmp_path) -> None:
    code, hello = _cli(tmp_path, "hello")
    assert code == 0 and hello["protocol"] == "tgn.local.v1"
    code, started = _cli(
        tmp_path,
        "start",
        "--prompt",
        "霜港供给",
        "--world",
        "frost_harbor",
        "--campaign",
        "cli-frost",
        "--seed",
        "7",
    )
    assert code == 0 and started["data"]["pending_narration"]["turn"] == 0
    code, blocked = _cli(tmp_path, "actions", "--campaign", "cli-frost")
    assert code == 2 and blocked["error"]["code"] == "CAMPAIGN_CONFLICT"
    claims = started["data"]["pending_narration"]["required_claims"]
    prose = "盐雾压低了灯火。\n\n" + "\n\n".join(claim["text"] for claim in claims) + "\n\n真正的选择才刚刚开始。"
    prose_file = tmp_path / "opening.md"
    prose_file.write_text(prose, encoding="utf-8")
    code, narrated = _cli(
        tmp_path,
        "narrate",
        "--campaign",
        "cli-frost",
        "--prose-file",
        str(prose_file),
    )
    assert code == 0 and Path(narrated["data"]["novel_draft"]).is_file()
    assert narrated["data"]["narration"]["prose"] == prose
    code, resumed = _cli(tmp_path, "resume", "--campaign", "cli-frost")
    assert code == 0 and resumed["data"]["pending_narration"] is None


def test_cli_reports_custom_world_quality_failures_as_structured_json(tmp_path) -> None:
    source = json.loads((ROOT / "worlds" / "frost_harbor.json").read_text(encoding="utf-8"))
    source["actions"] = source["actions"][:2]
    # Keep compiler references internally valid so the experience gate, not
    # malformed JSON handling, owns the failure.
    source["lever"]["action_ids"] = [action["id"] for action in source["actions"] if action["lever"]["required"]]
    source["cycle"]["rule_legibility_actions"] = [source["actions"][0]["id"]]
    source["cycle"]["compounding_chains"] = [
        [source["actions"][0]["id"], source["milestones"][0]["id"]],
        [source["actions"][1]["id"], source["milestones"][1]["id"]],
    ]
    custom = tmp_path / "thin.json"
    custom.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    code, payload = _cli(tmp_path / "saves", "compile-world", "--file", str(custom))
    assert code == 2
    assert payload["error"]["code"] == "WORLD_REJECTED"
    assert any(issue["code"] == "insufficient_actions" for issue in payload["error"]["details"]["issues"])


def test_cli_route_audit_is_a_real_reachability_certificate(tmp_path) -> None:
    route = (
        "accept_debt,inspect_grid,trace_fault,log_cause,automate_pump,"
        "schedule_crew,audit_manifest,rest,convene_council,sign_quota,rest,map_ice_route"
    )
    code, payload = _cli(
        tmp_path,
        "audit-world",
        "--file",
        str(ROOT / "worlds" / "frost_harbor.json"),
        "--seed",
        "1",
        "--route",
        route,
    )
    assert code == 0 and payload["data"]["passed"] is True
    assert all(payload["data"]["checks"].values())

    code, failed = _cli(
        tmp_path,
        "audit-world",
        "--file",
        str(ROOT / "worlds" / "frost_harbor.json"),
        "--seed",
        "1",
        "--route",
        "map_ice_route",
    )
    assert code == 0 and failed["data"]["passed"] is False
    assert failed["data"]["reason_code"] in {"expansion_inactive", "not_visible"}
