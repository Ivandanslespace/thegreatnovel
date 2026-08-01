from __future__ import annotations

import json

import pytest

from tgn.core.models import GameState
from tgn.session.models import SessionError, SessionManifest, validate_stable_id


@pytest.mark.parametrize("value", ["", "../x", "A", "session.x", "session/x", "session\\x", "session:1"])
def test_stable_machine_ids_reject_path_and_display_values(value):
    with pytest.raises(SessionError) as exc_info:
        validate_stable_id(value, "session_id")
    assert exc_info.value.code == "INVALID_SESSION_ID"


def test_stable_machine_ids_accept_bounded_ascii_identity():
    assert validate_stable_id("session-001_a", "session_id") == "session-001_a"


def test_manifest_has_exact_edge_fields_and_strict_status_contract():
    manifest = SessionManifest.create(
        session_id="session-001",
        actor_id="player",
        max_decisions=3,
        accepted_decisions=0,
        recorded_decision_count=0,
        status="AWAITING_DECISION",
        stop_reason=None,
        current_event_seq=0,
        current_state_decision_seq=0,
        current_state_hash="a" * 64,
        current_request_fingerprint="b" * 64,
    )
    assert set(manifest.to_dict()) == {
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
    assert "data" not in manifest.to_dict()
    assert manifest.public_summary() == manifest.to_dict()


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_decisions", True),
        ("accepted_decisions", False),
        ("current_event_seq", True),
        ("current_state_hash", "not-a-hash"),
    ],
)
def test_manifest_rejects_bool_and_noncanonical_values(field, value):
    payload = {
        "schema_version": 1,
        "session_id": "session-001",
        "campaign_id": "session-001",
        "actor_id": "player",
        "max_decisions": 3,
        "accepted_decisions": 0,
        "recorded_decision_count": 0,
        "status": "AWAITING_DECISION",
        "stop_reason": None,
        "current_event_seq": 0,
        "current_state_decision_seq": 0,
        "current_state_hash": "a" * 64,
        "current_request_fingerprint": "b" * 64,
    }
    payload[field] = value
    with pytest.raises(SessionError) as exc_info:
        SessionManifest.from_dict(payload)
    assert exc_info.value.code == "INVALID_SESSION_MANIFEST"


def test_manifest_rejects_invalid_stop_reason_and_unknown_fields():
    payload = SessionManifest.create(
        session_id="session-001",
        actor_id="player",
        max_decisions=3,
        accepted_decisions=0,
        recorded_decision_count=0,
        status="AWAITING_DECISION",
        stop_reason=None,
        current_event_seq=0,
        current_state_decision_seq=0,
        current_state_hash="a" * 64,
        current_request_fingerprint="b" * 64,
    ).to_dict()
    payload["stop_reason"] = "EXPLICIT_STOP"
    with pytest.raises(SessionError):
        SessionManifest.from_dict(payload)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.__setitem__("schema_version", 2),
        lambda p: p.__setitem__("campaign_id", "other-campaign"),
        lambda p: p.__setitem__("status", "UNKNOWN"),
        lambda p: p.__setitem__("stop_reason", 1),
        lambda p: p.__setitem__("accepted_decisions", 4),
        lambda p: (p.__setitem__("accepted_decisions", 1), p.__setitem__("recorded_decision_count", 0)),
        lambda p: p.__setitem__("max_decisions", 0),
        lambda p: p.__setitem__("accepted_decisions", -1),
        lambda p: p.__setitem__("current_request_fingerprint", "bad"),
    ],
)
def test_manifest_rejects_each_strict_boundary(mutate):
    payload = SessionManifest.create(
        session_id="session-001",
        actor_id="player",
        max_decisions=3,
        accepted_decisions=0,
        recorded_decision_count=0,
        status="AWAITING_DECISION",
        stop_reason=None,
        current_event_seq=0,
        current_state_decision_seq=0,
        current_state_hash="a" * 64,
        current_request_fingerprint="b" * 64,
    ).to_dict()
    mutate(payload)
    with pytest.raises(SessionError) as exc_info:
        SessionManifest.from_dict(payload)
    assert exc_info.value.code == "INVALID_SESSION_MANIFEST"
    payload["stop_reason"] = None
    payload["unexpected"] = 1
    with pytest.raises(SessionError):
        SessionManifest.from_dict(payload)


def test_game_state_shape_is_not_a_session_manifest():
    state = GameState.initial()
    assert set(state.__dict__) != set(SessionManifest.__dataclass_fields__)
    assert json.loads(json.dumps(state.__dict__)) ["data"] == {}
