"""Small Phase 9A session metadata contract.

Session metadata is an edge artifact.  It is deliberately separate from
GameState, DomainEvent, and the SQLite EventStore schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SESSION_SCHEMA_VERSION = 1
SESSION_STATUSES = frozenset(
    {"AWAITING_DECISION", "STOPPED", "MAX_DECISIONS", "NO_LEGAL_ACTIONS"}
)
SESSION_FIELDS = frozenset(
    {
        "schema_version",
        "session_id",
        "campaign_id",
        "actor_id",
        "max_decisions",
        "accepted_decisions",
        "recorded_decision_count",
        "status",
        "stop_reason",
        "current_event_seq",
        "current_state_decision_seq",
        "current_state_hash",
        "current_request_fingerprint",
    }
)
_STABLE_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")


class SessionError(ValueError):
    """Stable, presentation-safe error from the Phase 9A session boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def validate_stable_id(value: Any, field: str) -> str:
    """Validate a machine identity without treating it as a display title."""

    if not isinstance(value, str) or _STABLE_ID_RE.fullmatch(value) is None:
        raise SessionError(
            "INVALID_SESSION_ID",
            f"{field} must match [a-z0-9][a-z0-9_-]{{0,63}}",
        )
    return value


def _strict_int(value: Any, field: str, *, positive: bool = False) -> int:
    if type(value) is not int:
        raise SessionError("INVALID_SESSION_MANIFEST", f"{field} must be an integer")
    if positive and value <= 0:
        raise SessionError("INVALID_SESSION_MANIFEST", f"{field} must be positive")
    if not positive and value < 0:
        raise SessionError("INVALID_SESSION_MANIFEST", f"{field} must be non-negative")
    return value


def _strict_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise SessionError("INVALID_SESSION_MANIFEST", f"{field} must be a SHA-256 hex string")
    return value


@dataclass(frozen=True)
class SessionManifest:
    """Strict edge metadata persisted beside the authoritative campaign DB."""

    schema_version: int
    session_id: str
    campaign_id: str
    actor_id: str
    max_decisions: int
    accepted_decisions: int
    recorded_decision_count: int
    status: str
    stop_reason: str | None
    current_event_seq: int
    current_state_decision_seq: int
    current_state_hash: str
    current_request_fingerprint: str | None

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        actor_id: str,
        max_decisions: int,
        accepted_decisions: int,
        recorded_decision_count: int,
        status: str,
        stop_reason: str | None,
        current_event_seq: int,
        current_state_decision_seq: int,
        current_state_hash: str,
        current_request_fingerprint: str | None,
    ) -> "SessionManifest":
        return cls.from_dict(
            {
                "schema_version": SESSION_SCHEMA_VERSION,
                "session_id": session_id,
                "campaign_id": session_id,
                "actor_id": actor_id,
                "max_decisions": max_decisions,
                "accepted_decisions": accepted_decisions,
                "recorded_decision_count": recorded_decision_count,
                "status": status,
                "stop_reason": stop_reason,
                "current_event_seq": current_event_seq,
                "current_state_decision_seq": current_state_decision_seq,
                "current_state_hash": current_state_hash,
                "current_request_fingerprint": current_request_fingerprint,
            }
        )

    @classmethod
    def from_dict(cls, value: Any) -> "SessionManifest":
        if not isinstance(value, dict) or set(value) != SESSION_FIELDS:
            raise SessionError(
                "INVALID_SESSION_MANIFEST",
                "session.json must contain exactly the session manifest fields",
            )

        if type(value["schema_version"]) is not int or value["schema_version"] != SESSION_SCHEMA_VERSION:
            raise SessionError(
                "INVALID_SESSION_MANIFEST", "unsupported session schema_version"
            )

        session_id = validate_stable_id(value["session_id"], "session_id")
        campaign_id = validate_stable_id(value["campaign_id"], "campaign_id")
        actor_id = validate_stable_id(value["actor_id"], "actor_id")
        if campaign_id != session_id:
            raise SessionError(
                "INVALID_SESSION_MANIFEST", "campaign_id must equal session_id in Phase 9A"
            )

        max_decisions = _strict_int(value["max_decisions"], "max_decisions", positive=True)
        accepted_decisions = _strict_int(value["accepted_decisions"], "accepted_decisions")
        recorded_decision_count = _strict_int(
            value["recorded_decision_count"], "recorded_decision_count"
        )
        current_event_seq = _strict_int(value["current_event_seq"], "current_event_seq")
        current_state_decision_seq = _strict_int(
            value["current_state_decision_seq"], "current_state_decision_seq"
        )
        status = value["status"]
        if not isinstance(status, str) or status not in SESSION_STATUSES:
            raise SessionError("INVALID_SESSION_MANIFEST", "unknown session status")

        stop_reason = value["stop_reason"]
        if stop_reason is not None and not isinstance(stop_reason, str):
            raise SessionError("INVALID_SESSION_MANIFEST", "stop_reason must be string or null")
        expected_stop_reason = {
            "AWAITING_DECISION": None,
            "STOPPED": "EXPLICIT_STOP",
            "MAX_DECISIONS": "MAX_DECISIONS",
            "NO_LEGAL_ACTIONS": "NO_LEGAL_ACTIONS",
        }[status]
        if stop_reason != expected_stop_reason:
            raise SessionError(
                "INVALID_SESSION_MANIFEST",
                "status and stop_reason do not form a valid Phase 9A pair",
            )

        current_state_hash = _strict_hash(value["current_state_hash"], "current_state_hash")
        current_request_fingerprint = value["current_request_fingerprint"]
        if current_request_fingerprint is not None:
            current_request_fingerprint = _strict_hash(
                current_request_fingerprint, "current_request_fingerprint"
            )

        if accepted_decisions > max_decisions:
            raise SessionError(
                "INVALID_SESSION_MANIFEST", "accepted_decisions exceeds max_decisions"
            )
        if recorded_decision_count < accepted_decisions:
            raise SessionError(
                "INVALID_SESSION_MANIFEST",
                "recorded_decision_count cannot be below accepted_decisions",
            )

        return cls(
            schema_version=value["schema_version"],
            session_id=session_id,
            campaign_id=campaign_id,
            actor_id=actor_id,
            max_decisions=max_decisions,
            accepted_decisions=accepted_decisions,
            recorded_decision_count=recorded_decision_count,
            status=status,
            stop_reason=stop_reason,
            current_event_seq=current_event_seq,
            current_state_decision_seq=current_state_decision_seq,
            current_state_hash=current_state_hash,
            current_request_fingerprint=current_request_fingerprint,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "campaign_id": self.campaign_id,
            "actor_id": self.actor_id,
            "max_decisions": self.max_decisions,
            "accepted_decisions": self.accepted_decisions,
            "recorded_decision_count": self.recorded_decision_count,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "current_event_seq": self.current_event_seq,
            "current_state_decision_seq": self.current_state_decision_seq,
            "current_state_hash": self.current_state_hash,
            "current_request_fingerprint": self.current_request_fingerprint,
        }

    def public_summary(self) -> dict[str, Any]:
        """Return session metadata only; never include GameState or SQLite rows."""

        return self.to_dict()
