"""Application service joining pure simulation, durable history, and narration.

This is the only host layer used by the local CLI.  It never narrates an
uncommitted result and never exposes the authoritative state directly to the
player; every outward state view comes through ``project_player_view``.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .blueprint import compile_blueprint
from .contracts import EventDraft
from .engine import initial_state, legal_actions, preview_action, resolve_action
from .projection import project_player_view
from .storage import CampaignStore, CampaignStoreError
from .story import NarrationResponse, fallback_response
from .worlds import (
    choose_world_for_prompt,
    list_worlds,
    load_world,
    require_experience_ready,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAVES_ROOT = PROJECT_ROOT / "saves"
_ID_PARTS = re.compile(r"[^A-Za-z0-9_-]+")


def _campaign_id(world_id: str, prompt: str) -> str:
    slug = _ID_PARTS.sub("-", world_id).strip("-")[:24] or "world"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{stamp}-{digest}"[:64]


def _seed_for(campaign_id: str, prompt: str, blueprint_hash: str) -> int:
    material = f"{campaign_id}\n{prompt}\n{blueprint_hash}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def _opening_facts(world: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    player = state.get("player", {})
    role = player.get("role", "尚未被世界承认的人") if isinstance(player, Mapping) else "尚未被世界承认的人"
    location = player.get("location", "未知之地") if isinstance(player, Mapping) else "未知之地"
    source = f"blueprint:{world['id']}"
    return (
        {"text": str(world["premise"]), "visibility": "public", "kind": "premise", "source": source},
        {
            "text": f"你以“{role}”的身份从“{location}”开始。",
            "visibility": "player",
            "kind": "starting_position",
            "source": source,
        },
        {"text": str(world["control_deficit"]), "visibility": "player", "kind": "control_deficit", "source": source},
        {
            "text": f"你拥有“{world['lever']['name']}”：{world['lever']['summary']}",
            "visibility": "player",
            "kind": "asymmetric_leverage",
            "source": source,
        },
    )


def _opening_observation(
    world: Mapping[str, Any],
    state: Mapping[str, Any],
    facts: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    draft = EventDraft(
        event_type="campaign.started",
        actor_id="world",
        patches=(),
        facts=facts,
        details={"turn_after": 0, "time_after": 0, "opening": True},
    )
    return project_player_view(world, state, (draft,))


def _compact_player_view(view: Mapping[str, Any]) -> dict[str, Any]:
    """Keep one player-facing copy of state/facts/actions instead of three."""

    return {
        "state_hash": view.get("state_hash"),
        "panel": dict(view.get("panel", {})),
        "observation": dict(view.get("player_observation", {})),
    }


def _public_narration_request(request: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if request is None:
        return None
    context = dict(request.get("context", {}))
    # The canonical observation is durably hashed and validated, but callers
    # already receive a compact player view beside this request.
    context.pop("player_observation", None)
    return {
        "schema_version": request.get("schema_version"),
        "request_id": request.get("request_id"),
        "request_hash": request.get("request_hash"),
        "campaign_id": request.get("campaign_id"),
        "turn": request.get("turn"),
        "event_ids": list(request.get("event_ids", ())),
        "required_claims": [dict(claim) for claim in request.get("required_claims", ())],
        "context": context,
    }


class GameService:
    def __init__(self, saves_root: str | Path = DEFAULT_SAVES_ROOT):
        self.saves_root = Path(saves_root).expanduser().resolve()
        self.saves_root.mkdir(parents=True, exist_ok=True)

    def available_worlds(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for world_id in list_worlds():
            world = load_world(world_id)
            result.append({
                "id": world["id"],
                "title": world["title"],
                "premise": world["premise"],
                "core_question": world["core_question"],
                "causal_model": world["causal_model"],
            })
        return result

    def compile_world_file(self, path: str | Path) -> dict[str, Any]:
        selection = choose_world_for_prompt(None, blueprint_file=path)
        compiled = compile_blueprint(selection["blueprint"])
        gate = require_experience_ready(compiled)
        return {
            "world_id": compiled["id"],
            "title": compiled["title"],
            "blueprint_hash": compiled["blueprint_hash"],
            "experience_gate": gate,
            "selection_reasons": selection["selection_reasons"],
            "fit_warning": selection["fit_warning"],
        }

    def start(
        self,
        prompt: str,
        *,
        campaign_id: str | None = None,
        world_id: str | None = None,
        blueprint_file: str | Path | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        text = str(prompt).strip()
        if world_id and blueprint_file:
            raise ValueError("world_id and blueprint_file are mutually exclusive")
        if world_id:
            raw = load_world(world_id)
            selection = {
                "blueprint": raw,
                "world_id": world_id,
                "selection_reasons": ["player or host selected a reviewed built-in world"],
                "fit_warning": None,
            }
        else:
            selection = choose_world_for_prompt(text, blueprint_file=blueprint_file)
        compiled = compile_blueprint(selection["blueprint"])
        gate = require_experience_ready(compiled)
        cid = campaign_id or _campaign_id(str(compiled["id"]), text)
        actual_seed = seed if seed is not None else _seed_for(cid, text, compiled["blueprint_hash"])
        state = initial_state(compiled, cid, actual_seed)
        state["campaign"]["world_prompt"] = text
        store = CampaignStore.create(self.saves_root, cid, compiled, state)
        try:
            facts = _opening_facts(compiled, state)
            observation = _opening_observation(compiled, state, facts)
            opening = store.begin_opening(
                f"start-{cid}",
                facts,
                observation,
            )
            return {
                "campaign_id": cid,
                "status": store.manifest()["status"],
                "world": self._world_card(compiled),
                "selection_reasons": selection["selection_reasons"],
                "fit_warning": selection.get("fit_warning"),
                "experience_gate": gate,
                "player_view": _compact_player_view(observation),
                "pending_narration": _public_narration_request(opening["narration_request"]),
                "novel_draft": str((store.exports_dir / "novel_draft.md").resolve()),
            }
        finally:
            store.close()

    @staticmethod
    def _world_card(world: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": world["id"],
            "title": world["title"],
            "premise": world["premise"],
            "core_question": world["core_question"],
            "control_deficit": world["control_deficit"],
            "lever": {
                key: world["lever"][key]
                for key in ("name", "summary", "cost", "limits", "ordinary_baseline")
            },
        }

    def list_campaigns(self) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for manifest in CampaignStore.list_campaigns(self.saves_root):
            cid = manifest["campaign_id"]
            store = CampaignStore.open(self.saves_root, cid)
            try:
                world = store.get_compiled_world()
                state = store.get_state()
                values.append({
                    "campaign_id": cid,
                    "status": manifest["status"],
                    "world_id": world.get("id"),
                    "title": world.get("title"),
                    "turn": state.get("campaign", {}).get("turn", 0),
                    "time_minute": state.get("campaign", {}).get("time_minute", 0),
                    "current_tier": state.get("campaign", {}).get("current_tier", 0),
                    "has_pending_narration": store.pending_narration() is not None,
                    "novel_draft": str((store.exports_dir / "novel_draft.md").resolve()),
                })
            finally:
                store.close()
        return sorted(values, key=lambda value: value["campaign_id"], reverse=True)

    def resume(self, campaign_id: str | None = None) -> dict[str, Any]:
        cid = campaign_id or self._latest_resumable_id()
        if cid is None:
            raise FileNotFoundError("no resumable campaign")
        store = CampaignStore.open(self.saves_root, cid)
        try:
            world = store.get_compiled_world()
            state = store.get_state()
            pending = store.pending_narration()
            if not store.get_events() and store.manifest().get("status") == "ACTIVE":
                facts = _opening_facts(world, state)
                opening = store.begin_opening(
                    f"start-{cid}",
                    facts,
                    _opening_observation(world, state, facts),
                )
                pending = opening["narration_request"]
            return self._campaign_view(store, world, state, pending=pending)
        finally:
            store.close()

    def _latest_resumable_id(self) -> str | None:
        campaigns = [item for item in self.list_campaigns() if item["status"] in {"ACTIVE", "STOPPING"}]
        return campaigns[0]["campaign_id"] if campaigns else None

    def state(self, campaign_id: str) -> dict[str, Any]:
        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            return self._campaign_view(
                store,
                store.get_compiled_world(),
                store.get_state(),
                pending=store.pending_narration(),
            )
        finally:
            store.close()

    def _campaign_view(
        self,
        store: CampaignStore,
        world: Mapping[str, Any],
        state: Mapping[str, Any],
        *,
        pending: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "campaign_id": store.campaign_dir.name,
            "status": store.manifest()["status"],
            "world": self._world_card(world),
            "player_view": _compact_player_view(project_player_view(world, state)),
            "pending_narration": _public_narration_request(pending),
            "novel_draft": str((store.exports_dir / "novel_draft.md").resolve()),
            "final_novel": str((store.exports_dir / "novel.md").resolve()) if (store.exports_dir / "novel.md").is_file() else None,
        }

    def actions(self, campaign_id: str) -> dict[str, Any]:
        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            self._require_no_pending(store)
            world = store.get_compiled_world()
            state = store.get_state()
            return {
                "campaign_id": campaign_id,
                "turn": state["campaign"]["turn"],
                "actions": legal_actions(world, state),
            }
        finally:
            store.close()

    def preview(self, campaign_id: str, action_id: str, *, use_lever: bool = True) -> dict[str, Any]:
        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            self._require_no_pending(store)
            if store.manifest()["status"] != "ACTIVE":
                raise CampaignStoreError("campaign is not active")
            preview = preview_action(store.get_compiled_world(), store.get_state(), action_id, use_lever)
            return {"campaign_id": campaign_id, **preview.to_dict()}
        finally:
            store.close()

    def act(self, campaign_id: str, preview_token: str, request_id: str) -> dict[str, Any]:
        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            self._require_no_pending(store)
            if store.manifest()["status"] != "ACTIVE":
                raise CampaignStoreError("campaign is not active")
            world = store.get_compiled_world()
            state = store.get_state()
            resolution = resolve_action(world, state, preview_token, request_id)
            committed = store.commit_resolution(request_id, resolution)
            return {
                **committed,
                "status": store.manifest()["status"],
                "player_view": _compact_player_view(resolution.player_observation),
                "narration_request": _public_narration_request(committed["narration_request"]),
                "novel_draft": str((store.exports_dir / "novel_draft.md").resolve()),
            }
        finally:
            store.close()

    def act_by_id(
        self,
        campaign_id: str,
        action_id: str,
        request_id: str,
        *,
        use_lever: bool = True,
        expected_turn: int | None = None,
    ) -> dict[str, Any]:
        """Re-preview and atomically accept one explicitly identified action."""

        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            self._require_no_pending(store)
            if store.manifest()["status"] != "ACTIVE":
                raise CampaignStoreError("campaign is not active")
            world = store.get_compiled_world()
            state = store.get_state()
            current_turn = int(state["campaign"]["turn"])
            if expected_turn is not None and expected_turn != current_turn:
                raise CampaignStoreError("expected turn is stale")
            preview = preview_action(world, state, action_id, use_lever)
            if not preview.legal:
                raise ValueError(preview.reason_code or "illegal_action")
            resolution = resolve_action(world, state, preview.preview_token, request_id)
            committed = store.commit_resolution(request_id, resolution)
            return {
                **committed,
                "status": store.manifest()["status"],
                "player_view": _compact_player_view(resolution.player_observation),
                "narration_request": _public_narration_request(committed["narration_request"]),
                "novel_draft": str((store.exports_dir / "novel_draft.md").resolve()),
            }
        finally:
            store.close()

    def pending(self, campaign_id: str) -> dict[str, Any]:
        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            world = store.get_compiled_world()
            state = store.get_state()
            return {
                "campaign_id": campaign_id,
                "status": store.manifest()["status"],
                "player_view": _compact_player_view(project_player_view(world, state)),
                "pending_narration": _public_narration_request(store.pending_narration()),
            }
        finally:
            store.close()

    def narrate(self, campaign_id: str, prose: str | None = None, *, fallback: bool = False) -> dict[str, Any]:
        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            request = store.pending_narration()
            if request is None:
                raise CampaignStoreError("no pending narration")
            if fallback:
                response: NarrationResponse = fallback_response(request)
            else:
                if prose is None or not prose.strip():
                    raise ValueError("prose is required unless fallback is selected")
                response = NarrationResponse(
                    schema_version=str(request["schema_version"]),
                    request_id=str(request["request_id"]),
                    request_hash=str(request["request_hash"]),
                    locale=str(request.get("context", {}).get("locale", "zh-CN")),
                    claims=tuple(dict(claim) for claim in request.get("required_claims", ())),
                    prose=prose,
                )
            committed = store.commit_narration(response)
            status = store.manifest()["status"]
            result = {
                "campaign_id": campaign_id,
                "status": status,
                "narration": committed,
                "novel_draft": str((store.exports_dir / "novel_draft.md").resolve()),
            }
            if status == "STOPPED":
                result["final_novel"] = str((store.exports_dir / "novel.md").resolve())
                result["history"] = str((store.exports_dir / "history.json").resolve())
                result["export_manifest"] = str((store.exports_dir / "manifest.json").resolve())
            return result
        finally:
            store.close()

    def end(self, campaign_id: str, request_id: str, reason: str) -> dict[str, Any]:
        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            result = store.begin_end(request_id, reason)
            return {
                **result,
                "campaign_id": campaign_id,
                "status": store.manifest()["status"],
                "narration_request": _public_narration_request(result["narration_request"]),
                "novel_draft": str((store.exports_dir / "novel_draft.md").resolve()),
            }
        finally:
            store.close()

    def verify(self, campaign_id: str) -> dict[str, Any]:
        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            return {"campaign_id": campaign_id, **store.verify()}
        finally:
            store.close()

    def export_final(self, campaign_id: str) -> dict[str, Any]:
        store = CampaignStore.open(self.saves_root, campaign_id)
        try:
            manifest = store.export_final()
            return {
                "campaign_id": campaign_id,
                "status": store.manifest()["status"],
                "manifest": manifest,
                "final_novel": str((store.exports_dir / "novel.md").resolve()),
            }
        finally:
            store.close()

    @staticmethod
    def _require_no_pending(store: CampaignStore) -> None:
        if store.pending_narration() is not None:
            raise CampaignStoreError("pending narration must be committed before the next decision")


__all__ = ["DEFAULT_SAVES_ROOT", "GameService"]
