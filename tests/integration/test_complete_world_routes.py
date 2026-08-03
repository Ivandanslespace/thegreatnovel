from __future__ import annotations

from pathlib import Path

import pytest

from tgn.service import GameService
from tgn.storage import CampaignStore


ROUTES = (
    (
        "frost_harbor",
        2,
        (
            "accept_debt", "inspect_grid", "trace_fault", "log_cause",
            "automate_pump", "schedule_crew", "audit_manifest", "rest",
            "convene_council", "sign_quota", "rest", "map_ice_route",
        ),
        "become_dispatch_steward",
        "cross_tier_three",
        "outer_ice_shelf",
        "map_ice_route",
    ),
    (
        "gray_court",
        1,
        (
            "rest", "gather_deposition", "verify_chain", "file_motion",
            "publish_affidavit", "seek_witness", "bind_commitment",
            "call_alliance", "set_arbitration", "draft_settlement",
            "audit_registry", "expose_conflict", "audit_registry", "rest",
            "ratify_concord",
        ),
        "become_arbitration_setter",
        "enter_federal_circuit",
        "federal_concord",
        "ratify_concord",
    ),
)


@pytest.mark.parametrize(
    "world_id,seed,route,relationship_milestone,tier_milestone,expansion_id,expansion_action",
    ROUTES,
)
def test_complete_route_survives_storage_narration_reopen_and_final_export(
    tmp_path,
    world_id: str,
    seed: int,
    route: tuple[str, ...],
    relationship_milestone: str,
    tier_milestone: str,
    expansion_id: str,
    expansion_action: str,
) -> None:
    service = GameService(tmp_path)
    started = service.start("", campaign_id=world_id, world_id=world_id, seed=seed)
    service.narrate(world_id, fallback=True)
    draft = Path(started["novel_draft"])

    for turn, action_id in enumerate(route, 1):
        preview = service.preview(world_id, action_id)
        assert preview["legal"] is True, (world_id, turn, action_id, preview)
        service.act_by_id(
            world_id,
            action_id,
            f"turn-{turn}",
            expected_turn=turn - 1,
        )
        service.narrate(world_id, fallback=True)
        assert f"## 第 {turn} 章" in draft.read_text(encoding="utf-8")
        assert service.verify(world_id)["ok"] is True

    store = CampaignStore.open(tmp_path, world_id)
    try:
        state = store.get_state()
        events = store.get_events()
        assert relationship_milestone in state["world"]["completed_milestones"]
        assert tier_milestone in state["world"]["completed_milestones"]
        assert state["campaign"]["current_tier"] == 3
        assert expansion_id in state["world"]["materialized_expansions"]
        assert state["world"]["action_counts"][expansion_action] == 1
        process_events = [event for event in events if event["event_type"] == "PROCESS_TICK"]
        assert process_events and all(event["details"]["process_id"] for event in process_events)
        assert all(event["actor_id"] != "player" for event in process_events)
    finally:
        store.close()

    service.end(world_id, "end-route", "route_acceptance")
    final = service.narrate(world_id, fallback=True)
    assert final["status"] == "STOPPED"
    novel = Path(final["final_novel"])
    novel_text = novel.read_text(encoding="utf-8")
    assert "## 序章" in novel_text and "## 尾声" in novel_text
    assert service.verify(world_id)["ok"] is True
