from __future__ import annotations

import copy
import json
import os
import stat
from types import SimpleNamespace
from pathlib import Path

import pytest

import tgn.story.common as common_module
from tgn.story.common import (
    canonical_bytes,
    parse_json_bytes,
    read_regular_file,
    require_actual_directory,
    safe_text,
    sha256_json,
    strict_int,
    validate_hash,
    validate_json_value,
    validate_path_components,
    validate_prose,
    validate_stable_id,
    write_fd_all,
)
from tgn.story.models import (
    NarrationRequest,
    NarrationResponse,
    StoryError,
    StoryManifest,
    TurnNarrationArtifact,
    request_hash,
    turn_artifact_hash,
)


DIGEST = "a" * 64


def _brief() -> dict:
    observation = {
        "location_id": "base-1",
        "stamina": 3,
        "max_stamina": 5,
        "inventory": [],
        "carried_loot": [],
        "actor": {"actor_id": "mara", "trust": 0, "facts": {}},
        "game_minute": 0,
    }
    return {
        "observation_before": copy.deepcopy(observation),
        "observation_after": copy.deepcopy(observation),
        "action_result": {
            "choice_id": "choice-001",
            "action_type": "DROP",
            "action_id": "player-external-campaign-001-1",
            "accepted_decision_number": 1,
            "event_types": ["EXPEDITION_DROPPED"],
            "event_seq_start": 1,
            "event_seq_end": 1,
            "public_event_facts": [
                {
                    "event_seq": 1,
                    "decision_seq": 1,
                    "event_type": "EXPEDITION_DROPPED",
                    "facts": {},
                }
            ],
        },
    }


def _request_value() -> dict:
    value = {
        "schema_version": 1,
        "request_format_id": "phase9c-narration-request-v1",
        "narration_request_id": "story-001:turn-000001",
        "narration_request_hash": DIGEST,
        "story_id": "story-001",
        "turn_id": "turn-000001",
        "campaign_id": "campaign-001",
        "session_id": "campaign-001",
        "accepted_decision_number": 1,
        "recorded_decision_index": 1,
        "request_fingerprint_before": DIGEST,
        "source_request_hash": DIGEST,
        "choice_id": "choice-001",
        "action_type": "DROP",
        "action_id": "player-external-campaign-001-1",
        "params": {},
        "duration_minutes": 10,
        "stamina_cost": 1,
        "event_seq_start": 1,
        "event_seq_end": 1,
        "state_hash_before": DIGEST,
        "state_hash_after": DIGEST,
        "narration_locale": "en",
        "voice_id": "cablecar_survival",
        "public_brief": _brief(),
        "claim_requirements": [
            {"kind": "action_performed", "value": {"choice_id": "choice-001", "action_type": "DROP"}}
        ],
    }
    return value


def _turn_value() -> dict:
    request = _request_value()
    value = {
        "schema_version": 1,
        "artifact_format_id": "phase9c-turn-narration-v1",
        "turn_artifact_hash": DIGEST,
        "story_id": request["story_id"],
        "turn_id": request["turn_id"],
        "narration_request_id": request["narration_request_id"],
        "narration_request_hash": request["narration_request_hash"],
        "source_request_hash": request["source_request_hash"],
        "campaign_id": request["campaign_id"],
        "session_id": request["session_id"],
        "accepted_decision_number": request["accepted_decision_number"],
        "recorded_decision_index": request["recorded_decision_index"],
        "request_fingerprint_before": request["request_fingerprint_before"],
        "choice_id": request["choice_id"],
        "action_type": request["action_type"],
        "action_id": request["action_id"],
        "params": {},
        "duration_minutes": request["duration_minutes"],
        "stamina_cost": request["stamina_cost"],
        "event_seq_start": 1,
        "event_seq_end": 1,
        "state_hash_before": DIGEST,
        "state_hash_after": DIGEST,
        "narration_locale": "en",
        "voice_id": "cablecar_survival",
        "claims": request["claim_requirements"],
        "prose": "A consequence became visible.",
    }
    return value


def test_common_json_text_and_scalar_boundaries(tmp_path: Path) -> None:
    assert canonical_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
    assert sha256_json({"value": 1})
    assert safe_text("a\r\nb") == "a  b"
    with pytest.raises(TypeError):
        validate_json_value({1: "bad"})
    with pytest.raises(ValueError):
        validate_json_value("\ud800")
    with pytest.raises(TypeError):
        validate_json_value(object())
    with pytest.raises(ValueError):
        validate_json_value(float("inf"))
    with pytest.raises(ValueError):
        validate_json_value({"\ud800": 1})
    assert common_module._identity(SimpleNamespace(st_dev=None, st_ino=None)) is None
    with pytest.raises(TypeError):
        parse_json_bytes("{}")
    with pytest.raises(UnicodeDecodeError):
        parse_json_bytes(b"\xff")
    with pytest.raises(ValueError):
        parse_json_bytes(b"{\"a\":Infinity}", require_canonical=False)
    with pytest.raises(ValueError):
        parse_json_bytes(b'{ "a": 1 }', require_canonical=True)
    with pytest.raises(ValueError):
        validate_prose("")
    with pytest.raises(ValueError):
        validate_prose("x\x00y")
    with pytest.raises(ValueError):
        validate_prose("x\ry")
    with pytest.raises(ValueError):
        validate_prose("x" * 20_001)
    with pytest.raises(ValueError):
        validate_stable_id("Bad", "id")
    with pytest.raises(ValueError):
        validate_hash("not-a-hash", "hash")
    with pytest.raises(ValueError):
        strict_int(True, "number")
    with pytest.raises(ValueError):
        strict_int(0, "number", positive=True)
    with pytest.raises(ValueError):
        strict_int(-1, "number", nonnegative=True)


def test_common_regular_file_and_path_safety(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = tmp_path / "payload.json"
    payload.write_bytes(b"{}")
    assert read_regular_file(payload)[0] == b"{}"
    with pytest.raises(OSError):
        read_regular_file(tmp_path)

    link = tmp_path / "link"
    try:
        os.symlink(payload, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on this platform")
    with pytest.raises(OSError):
        read_regular_file(link)
    with pytest.raises(OSError):
        require_actual_directory(link)
    with pytest.raises(OSError):
        require_actual_directory(payload)
    with pytest.raises(OSError):
        validate_path_components(link, allow_missing_final=False)

    with pytest.raises(ValueError):
        validate_prose(1)

    missing = tmp_path / "missing" / "nested"
    validate_path_components(missing, allow_missing_final=True)
    assert require_actual_directory(missing, allow_missing=True) == missing

    destination = tmp_path / "write.bin"
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        write_fd_all(fd, b"ok")
    finally:
        os.close(fd)
    assert destination.read_bytes() == b"ok"

    original_write = os.write
    monkeypatch.setattr(os, "write", lambda *_args: 0)
    fd = os.open(destination, os.O_WRONLY | os.O_TRUNC)
    try:
        with pytest.raises(OSError):
            write_fd_all(fd, b"x")
    finally:
        os.close(fd)
    monkeypatch.setattr(os, "write", original_write)


def test_story_error_and_model_hash_boundaries() -> None:
    error = StoryError("unknown-code", "line\nsecret")
    assert error.code == "STORY_INTEGRITY_MISMATCH"
    assert "\n" not in error.message
    manifest = {
        "schema_version": 1,
        "story_format_id": "phase9c-story-v1",
        "story_id": "story-001",
        "campaign_id": "campaign-001",
        "campaign_manifest_hash": DIGEST,
        "worldpack_hash": DIGEST,
        "source_initial_state_hash": DIGEST,
        "player_projection_hash": DIGEST,
        "session_id": "campaign-001",
        "initial_narration_locale": "en",
        "initial_voice_id": "cablecar_survival",
    }
    assert StoryManifest.from_dict(manifest).story_id == "story-001"
    for field, replacement in (
        ("schema_version", True),
        ("story_format_id", "other"),
        ("session_id", "other-001"),
        ("initial_narration_locale", "fr"),
        ("initial_voice_id", "Bad Voice"),
    ):
        invalid = dict(manifest)
        invalid[field] = replacement
        with pytest.raises(ValueError):
            StoryManifest.from_dict(invalid)

    request = _request_value()
    assert request_hash(request) == request_hash({**request, "narration_request_hash": "f" * 64})
    parsed_request = NarrationRequest.from_dict(request)
    response = NarrationResponse.from_dict(
        {
            "schema_version": 1,
            "narration_request_id": parsed_request.narration_request_id,
            "narration_request_hash": DIGEST,
            "locale": "en",
            "claims": request["claim_requirements"],
            "prose": "ok",
        }
    )
    assert response.prose == "ok"
    turn = _turn_value()
    assert turn_artifact_hash(turn) == turn_artifact_hash({**turn, "turn_artifact_hash": "f" * 64})
    assert TurnNarrationArtifact.from_dict(turn).turn_id == "turn-000001"


def test_model_rejects_request_brief_and_turn_mismatches() -> None:
    base = _request_value()
    invalid_values = [
        {**base, "narration_request_id": "story-001:turn-000002"},
        {**base, "turn_id": "turn-000002"},
        {**base, "event_seq_end": 2},
        {**base, "duration_minutes": True},
        {**base, "public_brief": {"observation_before": {}, "observation_after": {}}},
        {**base, "claim_requirements": "not-a-list"},
    ]
    for value in invalid_values:
        with pytest.raises(ValueError):
            NarrationRequest.from_dict(value)

    response = {
        "schema_version": 1,
        "narration_request_id": "story-001:turn-000001",
        "narration_request_hash": DIGEST,
        "locale": "en",
        "claims": [],
        "prose": "ok",
    }
    for field, replacement in (("locale", "fr"), ("claims", {"bad": True}), ("prose", "\ud800")):
        invalid = dict(response)
        invalid[field] = replacement
        with pytest.raises((ValueError, UnicodeEncodeError)):
            NarrationResponse.from_dict(invalid)

    turn = _turn_value()
    for field, replacement in (
        ("artifact_format_id", "other"),
        ("turn_id", "turn-000002"),
        ("event_seq_end", 2),
        ("prose", ""),
        ("claims", "bad"),
    ):
        invalid = dict(turn)
        invalid[field] = replacement
        with pytest.raises(ValueError):
            TurnNarrationArtifact.from_dict(invalid)
