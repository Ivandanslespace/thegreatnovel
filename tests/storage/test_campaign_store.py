from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tgn.contracts import EngineResolution, EventDraft
from tgn.story import fallback_response
from tgn.storage.campaign import CampaignStore, CampaignStoreError, CommandConflict, IntegrityError


def _initial() -> dict:
    return {"campaign": {"campaign_id": "demo", "turn": 0, "time_minute": 0, "current_tier": 0}, "player": {"gold": 1}, "actors": {}, "world": {"minute": 0}, "opportunities": {}, "unlocks": [], "metrics": {}}


def _resolution(store: CampaignStore, *, gold: int = 3) -> EngineResolution:
    state = store.get_state()
    return EngineResolution(
        action_id="observe",
        expected_turn=state["campaign"]["turn"],
        expected_state_hash=store._current()[1],
        new_state={**state, "campaign": {**state["campaign"], "turn": state["campaign"]["turn"] + 1, "time_minute": 10}, "player": {"gold": gold}, "world": {"minute": 10}},
        events=(EventDraft("player.observed", "player", ({"op": "set", "path": "player.gold", "value": gold},), ({"text": "手中有金币", "visibility": "public", "kind": "state", "source": "engine"},), {"turn_after": 1, "time_after": 10, "tier_after": 0}),),
        player_observation={"visible": True},
    )


def test_create_no_replace_and_open_verify(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    store.close()
    with pytest.raises(FileExistsError):
        CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    reopened = CampaignStore.open(tmp_path, "demo")
    assert reopened.verify()["ok"] is True
    reopened.close()


def test_path_traversal_and_symlink_are_rejected(tmp_path) -> None:
    with pytest.raises(CampaignStoreError):
        CampaignStore.create(tmp_path, "../escape", {}, _initial())
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "link").symlink_to(outside, target_is_directory=True)
    assert CampaignStore.list_campaigns(tmp_path) == []


def test_commit_cas_idempotency_and_pending_gate(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    try:
        resolution = _resolution(store)
        first = store.commit_resolution("req-1", resolution)
        second = store.commit_resolution("req-1", resolution)
        assert first == second
        assert len(store.get_events()) == 1
        with pytest.raises(CampaignStoreError):
            store.commit_resolution("req-2", resolution)
        store.commit_narration(fallback_response(store.pending_narration()))
        assert store.pending_narration() is None
    finally:
        store.close()


def test_opening_is_a_grounded_turn_zero_event_and_draft_prologue(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"title": "潮汐卷"}, _initial())
    facts = (
        {"text": "潮水正在吞没低层码头。", "visibility": "public", "kind": "premise", "source": "blueprint"},
        {"text": "你仍没有调度权。", "visibility": "player", "kind": "control_deficit", "source": "blueprint"},
    )
    try:
        opened = store.begin_opening("open-1", facts, {"state": "visible"})
        assert opened == store.begin_opening("open-1", facts, {"state": "visible"})
        assert store.get_state()["campaign"]["turn"] == 0
        assert store.get_events()[0]["event_type"] == "campaign.started"
        with pytest.raises(CommandConflict):
            store.begin_opening("open-1", facts[:1], {"state": "visible"})
        response = fallback_response(store.pending_narration())
        store.commit_narration(response)
        draft = (store.exports_dir / "novel_draft.md").read_text(encoding="utf-8")
        assert "## 序章" in draft and "第 0 回合" not in draft
        store.commit_resolution("req-1", _resolution(store))
        store.commit_narration(fallback_response(store.pending_narration()))
        assert store.verify()["event_count"] == 2
    finally:
        store.close()


def test_patch_tamper_and_event_tamper_are_detected(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    try:
        store.commit_resolution("req-1", _resolution(store))
        store.commit_narration(fallback_response(store.pending_narration()))
        with pytest.raises(IntegrityError):
            store._db.execute("UPDATE events SET patches_json=? WHERE seq=1", (json.dumps([]),))
            store._db.commit()
            store.verify()
    finally:
        store.close()


def test_ending_exports_are_complete_and_idempotent(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    try:
        store.commit_resolution("req-1", _resolution(store))
        store.commit_narration(fallback_response(store.pending_narration()))
        store.begin_end("end-1", "player_requested")
        result = store.commit_narration(fallback_response(store.pending_narration()))
        assert store.manifest()["status"] == "STOPPED"
        final = store.campaign_dir / "exports" / "novel.md"
        history = store.campaign_dir / "exports" / "history.json"
        manifest = store.campaign_dir / "exports" / "manifest.json"
        assert final.exists() and history.exists() and manifest.exists()
        assert "手中有金币" in final.read_text(encoding="utf-8")
        assert store.commit_narration(result) == result
        assert store.verify()["ok"]
    finally:
        store.close()


def test_metadata_replay_and_business_patch_boundary(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"title": "潮汐卷"}, _initial())
    try:
        state = store.get_state()
        resolution = EngineResolution(
            "meta", 0, store._current()[1], {**state, "campaign": {**state["campaign"], "turn": 1, "time_minute": 30}, "world": {"minute": 30}, "player": {"gold": 2}},
            (EventDraft("meta", "player", ({"op": "set", "path": "player.gold", "value": 2},), ({"text": "时间前进", "visibility": "public", "kind": "time", "source": "engine"},), {"turn_after": 1, "time_after": 30, "tier_after": 0}),), {},
        )
        store.commit_resolution("meta", resolution)
        assert store.get_state()["campaign"]["turn"] == 1
        assert store.get_state()["world"]["minute"] == 30
        store.commit_narration(fallback_response(store.pending_narration()))
        state = store.get_state()
        bad = EngineResolution("bad", 1, store._current()[1], state, (EventDraft("bad", "player", ({"op": "set", "path": "campaign.turn", "value": 99},), ({"text": "x", "visibility": "public", "kind": "x", "source": "x"},), {"turn_after": 2, "time_after": 30, "tier_after": 0}),), {})
        with pytest.raises(IntegrityError):
            store.commit_resolution("bad", bad)
    finally:
        store.close()


def test_ending_export_failure_is_retryable_and_stays_stopping(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"title": "潮汐卷"}, _initial())
    try:
        store.commit_resolution("req-1", _resolution(store))
        store.commit_narration(fallback_response(store.pending_narration()))
        store.begin_end("end-1", "pause")
        original = store._atomic_text
        calls = {"n": 0}
        def fail_second(path, content):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("simulated export failure")
            return original(path, content)
        with patch.object(CampaignStore, "_atomic_text", staticmethod(fail_second)), pytest.raises(OSError):
            store.commit_narration(fallback_response(store.pending_narration()))
        assert store.manifest()["status"] == "STOPPING"
        store.close()
        store = CampaignStore.open(tmp_path, "demo")
        store.export_final()
        assert store.manifest()["status"] == "STOPPED"
        assert "暂歇" in (store.campaign_dir / "exports" / "novel.md").read_text(encoding="utf-8")
    finally:
        store.close()


def test_ending_request_conflict(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"title": "x"}, _initial())
    try:
        store.begin_end("end", "one")
        with pytest.raises(CommandConflict):
            store.begin_end("end", "two")
    finally:
        store.close()


def test_stopped_rejects_new_resolution_and_second_end(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    try:
        store.begin_end("end", "one")
        store.commit_narration(fallback_response(store.pending_narration()))
        with pytest.raises(CampaignStoreError):
            store.commit_resolution("new", _resolution(store))
        with pytest.raises(CampaignStoreError):
            store.begin_end("other", "two")
    finally:
        store.close()


def test_multi_event_resolution_uses_final_replay_turn(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    try:
        state = store.get_state()
        events = (
            EventDraft("one", "player", ({"op": "set", "path": "player.a", "value": 1},), ({"text": "甲", "visibility": "public", "kind": "state", "source": "engine"},), {"turn_after": 1, "time_after": 1, "tier_after": 0}),
            EventDraft("two", "world", ({"op": "set", "path": "player.b", "value": 2},), ({"text": "乙", "visibility": "public", "kind": "state", "source": "engine"},), {"turn_after": 2, "time_after": 2, "tier_after": 0}),
        )
        new_state = {**state, "campaign": {**state["campaign"], "turn": 2, "time_minute": 2}, "player": {"gold": 1, "a": 1, "b": 2}, "world": {"minute": 2}}
        resolution = EngineResolution("multi", 0, store._current()[1], new_state, events, {"visible": True})
        result = store.commit_resolution("multi", resolution)
        assert result["turn"] == 2 and store.pending_narration()["turn"] == 2
        store.commit_narration(fallback_response(store.pending_narration()))
        assert store.verify()["ok"]
    finally:
        store.close()


def test_draft_failure_reopens_and_recovers(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    try:
        store.commit_resolution("req", _resolution(store))
        response = fallback_response(store.pending_narration())
        original = store._atomic_text
        with patch.object(CampaignStore, "_atomic_text", staticmethod(lambda path, content: (_ for _ in ()).throw(OSError("draft fault")))), pytest.raises(OSError):
            store.commit_narration(response)
        store.close()
        store = CampaignStore.open(tmp_path, "demo")
        store.recover_exports()
        assert store.verify()["ok"]
    finally:
        store.close()


def test_stale_final_manifest_is_rejected(tmp_path) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    try:
        store.begin_end("end", "one")
        store.commit_narration(fallback_response(store.pending_narration()))
        path = store.exports_dir / "manifest.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["source_event_count"] = 999
        path.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(IntegrityError):
            store.verify()
    finally:
        store.close()


def test_create_rejects_incomplete_business_state(tmp_path) -> None:
    bad = _initial()
    del bad["metrics"]
    with pytest.raises(IntegrityError):
        CampaignStore.create(tmp_path, "bad", {"world": "w"}, bad)


def test_observation_must_match_canonical_projection(tmp_path, monkeypatch) -> None:
    store = CampaignStore.create(tmp_path, "demo", {"world": "w"}, _initial())
    try:
        monkeypatch.setattr(store, "_canonical_player_observation", lambda state, events: {"canonical": True})
        with pytest.raises(IntegrityError):
            store.commit_resolution("leak", _resolution(store))
    finally:
        store.close()
