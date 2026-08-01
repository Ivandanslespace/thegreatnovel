"""Strict Campaign edge models and boundary errors for Phase 9B2B."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


CAMPAIGN_SCHEMA_VERSION = 1
CAMPAIGN_FORMAT_ID = "phase9b2b-campaign-v1"
CAMPAIGN_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "campaign_format_id",
        "campaign_id",
        "worldpack_hash",
        "source_initial_state_hash",
        "world_bundle_manifest_hash",
        "player_projection_hash",
        "projection_bundle_manifest_hash",
        "initial_request_fingerprint",
        "initial_presentation_hash",
        "session_id",
        "actor_id",
        "max_decisions",
        "initial_session_state_hash",
    }
)
CAMPAIGN_ERROR_CODES = frozenset(
    {
        "INVALID_CAMPAIGN_INPUT",
        "CAMPAIGN_ALREADY_EXISTS",
        "CAMPAIGN_NOT_FOUND",
        "CAMPAIGN_INTEGRITY_MISMATCH",
        "SOURCE_BUNDLE_INVALID",
        "PROJECTION_BUNDLE_INVALID",
        "PROJECTION_SOURCE_MISMATCH",
        "SESSION_BOOTSTRAP_FAILED",
        "UNSUPPORTED_CAMPAIGN_FORMAT",
        "CAMPAIGN_PUBLICATION_UNAVAILABLE",
        "STALE_REQUEST",
        "UNKNOWN_CHOICE",
        "SESSION_TERMINAL",
    }
)
_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")


def _safe_message(value: Any) -> str:
    """Keep boundary messages deterministic and UTF-8 safe."""

    text = str(value).replace("\r", " ").replace("\n", " ")
    return text.encode("utf-8", "replace").decode("utf-8")


class CampaignError(ValueError):
    """Stable, presentation-safe error at the Campaign boundary."""

    def __init__(self, code: str, message: str) -> None:
        safe_code = code if code in CAMPAIGN_ERROR_CODES else "CAMPAIGN_INTEGRITY_MISMATCH"
        self.code = safe_code
        self.message = _safe_message(message)
        super().__init__(f"{self.code}: {self.message}")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


def _validate_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", f"{field} is not a valid stable ID")
    return value


def _validate_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", f"{field} is not a lowercase SHA-256")
    return value


@dataclass(frozen=True)
class CampaignManifest:
    """Immutable scalar manifest for one published Campaign."""

    schema_version: int
    campaign_format_id: str
    campaign_id: str
    worldpack_hash: str
    source_initial_state_hash: str
    world_bundle_manifest_hash: str
    player_projection_hash: str
    projection_bundle_manifest_hash: str
    initial_request_fingerprint: str
    initial_presentation_hash: str
    session_id: str
    actor_id: str
    max_decisions: int
    initial_session_state_hash: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != CAMPAIGN_SCHEMA_VERSION:
            raise CampaignError("UNSUPPORTED_CAMPAIGN_FORMAT", "unsupported Campaign schema_version")
        if self.campaign_format_id != CAMPAIGN_FORMAT_ID:
            raise CampaignError("UNSUPPORTED_CAMPAIGN_FORMAT", "unsupported Campaign format")
        _validate_id(self.campaign_id, "campaign_id")
        _validate_id(self.session_id, "session_id")
        _validate_id(self.actor_id, "actor_id")
        if self.session_id != self.campaign_id:
            raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "session_id must equal campaign_id")
        if type(self.max_decisions) is not int or self.max_decisions <= 0:
            raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "max_decisions must be positive")
        for field in (
            "worldpack_hash",
            "source_initial_state_hash",
            "world_bundle_manifest_hash",
            "player_projection_hash",
            "projection_bundle_manifest_hash",
            "initial_request_fingerprint",
            "initial_presentation_hash",
            "initial_session_state_hash",
        ):
            _validate_hash(getattr(self, field), field)

    @classmethod
    def from_dict(cls, value: Any) -> "CampaignManifest":
        if not isinstance(value, dict) or set(value) != CAMPAIGN_MANIFEST_FIELDS:
            raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "campaign.json has an invalid field set")
        try:
            return cls(**value)
        except CampaignError:
            raise
        except (TypeError, ValueError) as exc:
            raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "campaign.json has invalid values") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "campaign_format_id": self.campaign_format_id,
            "campaign_id": self.campaign_id,
            "worldpack_hash": self.worldpack_hash,
            "source_initial_state_hash": self.source_initial_state_hash,
            "world_bundle_manifest_hash": self.world_bundle_manifest_hash,
            "player_projection_hash": self.player_projection_hash,
            "projection_bundle_manifest_hash": self.projection_bundle_manifest_hash,
            "initial_request_fingerprint": self.initial_request_fingerprint,
            "initial_presentation_hash": self.initial_presentation_hash,
            "session_id": self.session_id,
            "actor_id": self.actor_id,
            "max_decisions": self.max_decisions,
            "initial_session_state_hash": self.initial_session_state_hash,
        }


__all__ = [
    "CAMPAIGN_ERROR_CODES",
    "CAMPAIGN_FORMAT_ID",
    "CAMPAIGN_MANIFEST_FIELDS",
    "CAMPAIGN_SCHEMA_VERSION",
    "CampaignError",
    "CampaignManifest",
]
