from __future__ import annotations

import copy
import dataclasses
from pathlib import Path
from types import SimpleNamespace

import pytest

from tgn.campaign import choose_campaign, next_campaign
from tgn.llm_player import RecordedDecision, export_recorded_decisions
from tgn.story import StoryError, init_story
from tgn.story.campaign_snapshot import capture_campaign_snapshot, parse_snapshot_json
from tgn.story.common import canonical_bytes
from tgn.story.models import StoryManifest
from tgn.story.reconstruction import reconstruct_campaign, request_for_turn
from tgn.story.verification import load_story_view

import tgn.story.reconstruction as reconstruction


def _choose(campaign: Path, action_type: str = "DROP") -> None:
    current = next_campaign(campaign)
    choice = next(item for item in current["canonical_request"]["choices"] if item["action_type"] == action_type)
    choose_campaign(campaign, request_fingerprint=current["canonical_request"]["request_fingerprint"], choice_id=choice["choice_id"])


def _base(story_factory, *, action_type: str = "DROP"):
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, action_type)
    snapshot = capture_campaign_snapshot(campaign)
    manifest = StoryManifest.from_dict(load_story_view(story).manifest.to_dict())
    return campaign, story, manifest, snapshot


def _replace_table(snapshot, table: str, rows) -> object:
    tables = dict(snapshot.sqlite_authoritative_rows)
    tables[table] = tuple(rows)
    return dataclasses.replace(
        snapshot,
        sqlite_authoritative_rows=tuple((name, tables[name]) for name, _rows in snapshot.sqlite_authoritative_rows),
    )


def _replace_file(snapshot, relative_path: str, payload: bytes):
    files = [(name, value) for name, value in snapshot._file_bytes]
    for index, (name, _value) in enumerate(files):
        if name == relative_path:
            files[index] = (name, payload)
            break
    else:
        raise AssertionError(relative_path)
    return dataclasses.replace(snapshot, _file_bytes=tuple(files))


def _recorded_bundle(snapshot) -> dict:
    return parse_snapshot_json(snapshot, "session/recorded_decisions.json")


def _with_bundle(snapshot, bundle: dict):
    payload = canonical_bytes(bundle)
    return dataclasses.replace(
        _replace_file(snapshot, "session/recorded_decisions.json", payload),
        recorded_decisions_json_canonical_bytes=payload,
        recorded_decisions_json_hash=__import__("hashlib").sha256(payload).hexdigest(),
    )


def _with_session(snapshot, session: dict):
    payload = canonical_bytes(session)
    return dataclasses.replace(
        _replace_file(snapshot, "session/session.json", payload),
        session_json_canonical_bytes=payload,
        session_json_hash=__import__("hashlib").sha256(payload).hexdigest(),
    )


def test_reconstruction_valid_history_and_request_lookup(story_factory) -> None:
    _campaign, story, manifest, snapshot = _base(story_factory)
    history = reconstruct_campaign(manifest, snapshot)
    assert history.accepted_decisions == 1
    assert history.recorded_decision_count == 1
    assert history.stop_reason is None
    assert request_for_turn(history, "turn-000001") is not None
    assert request_for_turn(history, "turn-999999") is None
    assert history.action_turns[0].request.event_seq_start == history.action_turns[0].request.event_seq_end


def test_reconstruction_projection_manifest_and_initial_state_errors(story_factory) -> None:
    _campaign, _story, manifest, snapshot = _base(story_factory)
    with pytest.raises(StoryError):
        reconstruct_campaign(manifest, _replace_file(snapshot, "projection/player_projection.json", canonical_bytes({"bad": True})))
    projection = parse_snapshot_json(snapshot, "projection/player_projection.json")
    projection["source_worldpack_hash"] = "b" * 64
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, _replace_file(snapshot, "projection/player_projection.json", canonical_bytes(projection)))
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    invalid_projection = copy.deepcopy(projection)
    invalid_projection["source_worldpack_hash"] = manifest.worldpack_hash
    invalid_projection["source_initial_state_hash"] = manifest.source_initial_state_hash
    invalid_projection["world"] = []
    with pytest.raises(StoryError):
        reconstruct_campaign(manifest, _replace_file(snapshot, "projection/player_projection.json", canonical_bytes(invalid_projection)))

    invalid_initial = _replace_file(snapshot, "world/initial_state.json", canonical_bytes({"not": "GameState"}))
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, invalid_initial)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    invalid_manifest = _replace_file(snapshot, "campaign.json", canonical_bytes({"bad": True}))
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, invalid_manifest)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_reconstruction_event_rows_and_sqlite_history_validation(story_factory) -> None:
    _campaign, _story, manifest, snapshot = _base(story_factory)
    event = snapshot.event_rows[0]
    snapshot_row = snapshot.snapshot_rows[0]
    mutations = [
        _replace_table(snapshot, "events", [event[:-1]]),
        _replace_table(snapshot, "events", [tuple([*event[:11], 1, *event[12:]])]),
        _replace_table(snapshot, "events", [tuple([*event[:1], "other", *event[2:]])]),
        _replace_table(snapshot, "events", [tuple([*event[:2], 99, *event[3:]])]),
        _replace_table(snapshot, "events", [tuple([*event[:3], 99, *event[4:]])]),
        _replace_table(snapshot, "snapshots", []),
        _replace_table(snapshot, "snapshots", [snapshot_row[:-1]]),
        _replace_table(snapshot, "snapshots", [tuple([*snapshot_row[:1], "other", *snapshot_row[2:]])]),
        _replace_table(snapshot, "snapshots", [tuple([*snapshot_row[:2], 99, *snapshot_row[3:]])]),
        _replace_table(snapshot, "snapshots", [tuple([*snapshot_row[:4], "b" * 64, *snapshot_row[5:]])]),
    ]
    campaign_row = snapshot.campaign_row
    mutations.extend(
        [
            _replace_table(snapshot, "campaigns", [campaign_row[:-1]]),
            _replace_table(snapshot, "campaigns", [tuple(["other", *campaign_row[1:]])]),
            _replace_table(snapshot, "campaigns", [tuple([*campaign_row[:5], "b" * 64, campaign_row[6]])]),
        ]
    )
    for mutated in mutations:
        with pytest.raises(StoryError) as error:
            reconstruct_campaign(manifest, mutated)
        assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_reconstruction_event_payload_and_recorded_decision_errors(story_factory) -> None:
    _campaign, _story, manifest, snapshot = _base(story_factory)
    event = snapshot.event_rows[0]
    for payload in (123, "not-json", "[]"):
        mutated_event = tuple([*event[:10], payload, *event[11:]])
        mutated = _replace_table(snapshot, "events", [mutated_event])
        with pytest.raises(StoryError) as error:
            reconstruct_campaign(manifest, mutated)
        assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    original_bundle = _recorded_bundle(snapshot)
    for mutation in (
        {"decision_number": 2},
        {"request_fingerprint": "b" * 64},
        {"choice_id": "not-legal"},
        {"action_type": "SEARCH"},
    ):
        bundle = copy.deepcopy(original_bundle)
        bundle["decisions"][0].update(mutation)
        with pytest.raises(StoryError) as error:
            reconstruct_campaign(manifest, _with_bundle(snapshot, bundle))
        assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    bad_event = tuple([*event[:7], "wrong-action", *event[8:]])
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, _replace_table(snapshot, "events", [bad_event]))
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    bad_hash = tuple([*event[:11], "b" * 64, event[12]])
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, _replace_table(snapshot, "events", [bad_hash]))
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_reconstruction_missing_event_and_session_edge_cases(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    _campaign, _story, manifest, snapshot = _base(story_factory)
    no_events = _replace_table(_replace_table(snapshot, "events", []), "snapshots", [])
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, no_events)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    session = parse_snapshot_json(snapshot, "session/session.json")
    with pytest.raises(StoryError):
        reconstruct_campaign(manifest, _with_session(snapshot, []))
    for changed in (
        {**session, "campaign_id": "other"},
        {**session, "accepted_decisions": 99},
        {**session, "recorded_decision_count": 99},
    ):
        with pytest.raises(StoryError) as error:
            reconstruct_campaign(manifest, _with_session(snapshot, changed))
        assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(reconstruction, "replay_events", lambda *_args, **_kwargs: SimpleNamespace(success=False, history=[]))
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, snapshot)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(reconstruction, "replay_events", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("replay")))
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, snapshot)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(reconstruction, "replay_events", lambda *_args, **_kwargs: SimpleNamespace(success=True, history=[]))
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, snapshot)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(reconstruction, "_reconstruct_request", lambda *_args: (_ for _ in ()).throw(RuntimeError("request")))
    with pytest.raises(StoryError) as error:
        reconstruct_campaign(manifest, snapshot)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
