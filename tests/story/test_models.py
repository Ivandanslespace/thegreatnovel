from __future__ import annotations

import json

import pytest

from tgn.story.models import NarrationResponse, StoryManifest

from .test_edges import _request_value, _turn_value


def test_manifest_and_response_are_exact() -> None:
    digest = "a" * 64
    value = {
        "schema_version": 1,
        "story_format_id": "phase9c-story-v1",
        "story_id": "story-001",
        "campaign_id": "campaign-001",
        "campaign_manifest_hash": digest,
        "worldpack_hash": digest,
        "source_initial_state_hash": digest,
        "player_projection_hash": digest,
        "session_id": "campaign-001",
        "initial_narration_locale": "en",
        "initial_voice_id": "cablecar_survival",
    }
    assert set(StoryManifest.from_dict(value).to_dict()) == set(value)
    with pytest.raises(ValueError):
        StoryManifest.from_dict({**value, "campaign_dir": "secret"})

    response = {
        "schema_version": 1,
        "narration_request_id": "story-001:turn-000001",
        "narration_request_hash": digest,
        "locale": "en",
        "claims": [],
        "prose": "ok",
    }
    assert NarrationResponse.from_dict(response).prose == "ok"


def test_strict_json_rejects_duplicates_and_noncanonical_text() -> None:
    from tgn.story.common import parse_json_bytes

    with pytest.raises(ValueError):
        parse_json_bytes(b'{"a":1,"a":2}')
    with pytest.raises(ValueError):
        parse_json_bytes(b'{"a": 1}')
    with pytest.raises(ValueError):
        parse_json_bytes(b'{"a":NaN}')


def test_response_rejects_bool_as_schema_integer_and_bad_prose() -> None:
    digest = "a" * 64
    response = {
        "schema_version": True,
        "narration_request_id": "story-001:turn-000001",
        "narration_request_hash": digest,
        "locale": "en",
        "claims": [],
        "prose": "ok",
    }
    with pytest.raises(ValueError):
        NarrationResponse.from_dict(response)


def test_request_public_brief_and_identity_validation() -> None:
    base = _request_value()
    public_cases = []
    public_cases.append({**base, "turn_id": 1})
    public_cases.append({**base, "turn_id": "turn-1"})
    public_cases.append({**base, "turn_id": "turn-0000010"})
    public_cases.append({**base, "request_format_id": "other"})
    public_cases.append({**base, "session_id": "other-001"})
    public_cases.append({**base, "accepted_decision_number": 2})
    public_cases.append({**base, "choice_id": ""})
    public_cases.append({**base, "action_type": ""})
    public_cases.append({**base, "action_id": ""})
    public_cases.append({**base, "params": []})
    public_cases.append({**base, "event_seq_end": 2})
    for value in public_cases:
        with pytest.raises(ValueError):
            NarrationResponse.from_dict(value) if set(value) == {"schema_version", "narration_request_id", "narration_request_hash", "locale", "claims", "prose"} else __import__("tgn.story.models", fromlist=["NarrationRequest"]).NarrationRequest.from_dict(value)

    request = _request_value()
    brief = request["public_brief"]
    invalid_briefs = [
        {**brief, "observation_before": []},
        {**brief, "action_result": {"bad": True}},
        {**brief, "action_result": {**brief["action_result"], "choice_id": 1}},
        {**brief, "action_result": {**brief["action_result"], "action_id": 1}},
        {**brief, "action_result": {**brief["action_result"], "event_types": []}},
        {**brief, "action_result": {**brief["action_result"], "event_seq_end": 2}},
        {**brief, "action_result": {**brief["action_result"], "public_event_facts": []}},
        {**brief, "action_result": {**brief["action_result"], "public_event_facts": [{"bad": True}]}},
        {**brief, "action_result": {**brief["action_result"], "public_event_facts": [{"event_seq": 1, "decision_seq": 1, "event_type": 1, "facts": []}]}},
    ]
    for invalid in invalid_briefs:
        value = dict(request)
        value["public_brief"] = invalid
        with pytest.raises(ValueError):
            __import__("tgn.story.models", fromlist=["NarrationRequest"]).NarrationRequest.from_dict(value)


def test_response_and_turn_field_validation() -> None:
    response = {
        "schema_version": 1,
        "narration_request_id": "story-001:turn-000001",
        "narration_request_hash": "a" * 64,
        "locale": "en",
        "claims": [],
        "prose": "ok",
    }
    for invalid in (
        {**response, "narration_request_id": ""},
        {**response, "claims": {}},
    ):
        with pytest.raises(ValueError):
            NarrationResponse.from_dict(invalid)

    turn = _turn_value()
    cases = [
        ("turn_artifact_hash", "bad"),
        ("narration_request_id", "other:turn-000001"),
        ("session_id", "other-001"),
        ("accepted_decision_number", 2),
        ("choice_id", 1),
        ("params", []),
        ("event_seq_end", 2),
        ("claims", {}),
    ]
    for field, replacement in cases:
        invalid = dict(turn)
        invalid[field] = replacement
        with pytest.raises(ValueError):
            __import__("tgn.story.models", fromlist=["TurnNarrationArtifact"]).TurnNarrationArtifact.from_dict(invalid)
    response["schema_version"] = 1
    response["prose"] = "  bad  "
    with pytest.raises(ValueError):
        NarrationResponse.from_dict(response)
