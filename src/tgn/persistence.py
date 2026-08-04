"""Atomic JSON campaign storage with event-chain and state-digest verification."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .models import Campaign
from .engine import _event_hash, _state_summary, _set_digest


class StorageError(Exception):
    pass

class CampaignStore:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.campaigns_dir = self.root / "campaigns"
        self.campaigns_dir.mkdir(parents=True, exist_ok=True)
        self.active_path = self.root / "active_campaign"

    def _path(self, campaign_id: str) -> Path:
        if not campaign_id or Path(campaign_id).name != campaign_id:
            raise StorageError("invalid campaign id")
        return self.campaigns_dir / f"{campaign_id}.json"

    def save(self, campaign: Campaign) -> Path:
        _set_digest(campaign)
        payload = campaign.to_dict()
        path = self._path(campaign.campaign_id)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{campaign.campaign_id}.", suffix=".tmp", dir=str(self.campaigns_dir))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        self.set_active(campaign.campaign_id)
        return path

    def load(self, campaign_id: str | None = None) -> Campaign:
        cid = campaign_id or self.get_active()
        if not cid:
            raise StorageError("no active campaign")
        path = self._path(cid)
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"cannot read campaign {cid}: {exc}") from exc
        campaign = Campaign.from_dict(data)
        self._verify_campaign(campaign)
        return campaign

    def verify(self, campaign_id: str | None = None) -> bool:
        self.load(campaign_id)
        return True

    def list_campaigns(self) -> list[str]:
        return sorted(path.stem for path in self.campaigns_dir.glob("*.json"))

    def set_active(self, campaign_id: str) -> None:
        self._path(campaign_id)
        fd, tmp_name = tempfile.mkstemp(prefix=".active.", dir=str(self.root))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(campaign_id); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp_name, self.active_path)
        finally:
            if os.path.exists(tmp_name): os.unlink(tmp_name)

    def get_active(self) -> str | None:
        try:
            cid = self.active_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return cid or None

    @staticmethod
    def _verify_campaign(campaign: Campaign) -> None:
        if campaign.schema_version != "1.0":
            raise StorageError(f"unsupported schema_version: {campaign.schema_version}")
        prev = "0" * 64
        for event in campaign.events:
            event_data = {"turn": event.turn, "kind": event.kind, "action_id": event.action_id,
                          "public_facts": event.public_facts, "hidden_facts": event.hidden_facts}
            if event.prev_hash != prev:
                raise StorageError("event chain prev_hash mismatch")
            expected = _event_hash(prev, event_data)
            if event.event_hash != expected:
                raise StorageError("event chain event_hash mismatch")
            prev = event.event_hash
        expected_digest = hashlib.sha256(json.dumps(_state_summary(campaign), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if not campaign.status_digest or campaign.status_digest != expected_digest:
            raise StorageError("campaign status digest mismatch")
