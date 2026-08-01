from __future__ import annotations

import json
import sqlite3

import pytest

import tgn.session.service as session_service
from tgn.actions.models import ActionExecutionResult, ActionValidationResult
from tgn.core.hashing import canonical_json
from tgn.core.models import GameState
from tgn.session import SessionError, SessionService
from tgn.storage.event_store import EventStore

from tests.gameplay.phase75_helpers import execute, make_phase75_state

from .conftest import choice_for


def _action(session_dir, action_type: str):
    request = SessionService(session_dir).next()["request"]
    choice = choice_for(request, action_type)
    return SessionService(session_dir).choose(
        request_fingerprint=request["request_fingerprint"],
        choice_id=choice["choice_id"],
    )


def _tamper_json(path, mutate):
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(canonical_json(payload), encoding="utf-8")


def _tamper_event_column(session_dir, column: str, value) -> None:
    assert column in {
        "actor_id",
        "action_id",
        "causation_id",
        "correlation_id",
        "payload_json",
    }
    connection = sqlite3.connect(session_dir / "campaign.sqlite3")
    try:
        connection.execute(
            f"UPDATE events SET {column} = ? WHERE event_seq = 1", (value,)
        )
        connection.commit()
    finally:
        connection.close()


def test_start_rejects_invalid_initial_without_formal_session_directory(tmp_path):
    initial = tmp_path / "invalid.json"
    initial.write_text(canonical_json({"schema_version": 1}), encoding="utf-8")
    session_dir = tmp_path / "not-created"
    with pytest.raises(SessionError) as exc_info:
        SessionService.start(
            session_dir,
            session_id="session-001",
            actor_id="player",
            max_decisions=5,
            initial_state_path=initial,
        )
    assert exc_info.value.code == "INVALID_INITIAL_STATE"
    assert not session_dir.exists()

    with pytest.raises(SessionError) as missing:
        SessionService.start(
            tmp_path / "missing-initial-session",
            session_id="missing-initial-session",
            actor_id="player",
            max_decisions=5,
            initial_state_path=tmp_path / "does-not-exist.json",
        )
    assert missing.value.code == "INVALID_INITIAL_STATE"


@pytest.mark.parametrize(
    "payload",
    [
        '{"schema_version":1,"schema_version":1}',
        '{"schema_version":1,"event_seq":0,"decision_seq":0,"game_minute":0,"seed":"x","data":NaN}',
    ],
)
def test_start_rejects_duplicate_or_nonstandard_initial_json(tmp_path, payload):
    initial = tmp_path / "invalid-json.json"
    initial.write_text(payload, encoding="utf-8")
    with pytest.raises(SessionError) as exc_info:
        SessionService.start(
            tmp_path / "invalid-json-session",
            session_id="invalid-json-session",
            actor_id="player",
            max_decisions=5,
            initial_state_path=initial,
        )
    assert exc_info.value.code == "INVALID_INITIAL_STATE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_seq", True),
        ("seed", 1),
        ("data", []),
        ("game_minute", -1),
    ],
)
def test_start_rejects_strict_initial_state_fields(tmp_path, field, value):
    payload = make_phase75_state().__dict__
    payload[field] = value
    initial = tmp_path / f"invalid-{field}.json"
    initial.write_text(canonical_json(payload), encoding="utf-8")
    with pytest.raises(SessionError) as exc_info:
        SessionService.start(
            tmp_path / f"invalid-{field}-session",
            session_id=f"invalid-{field}-session",
            actor_id="player",
            max_decisions=5,
            initial_state_path=initial,
        )
    assert exc_info.value.code == "INVALID_INITIAL_STATE"


def test_start_rejects_valid_core_state_without_gameplay_observation(tmp_path):
    initial = tmp_path / "core-only.json"
    initial.write_text(canonical_json(GameState.initial().__dict__), encoding="utf-8")
    with pytest.raises(SessionError) as exc_info:
        SessionService.start(
            tmp_path / "core-only-session",
            session_id="core-only-session",
            actor_id="player",
            max_decisions=5,
            initial_state_path=initial,
        )
    assert exc_info.value.code == "INVALID_INITIAL_STATE"


@pytest.mark.parametrize("max_decisions", [0, -1, True])
def test_start_rejects_nonpositive_or_bool_decision_limit(
    tmp_path, phase75_initial_state_file, max_decisions
):
    with pytest.raises(SessionError) as exc_info:
        SessionService.start(
            tmp_path / f"bad-limit-{str(max_decisions).lower()}",
            session_id=f"bad-limit-{str(max_decisions).lower()}",
            actor_id="player",
            max_decisions=max_decisions,
            initial_state_path=phase75_initial_state_file,
        )
    assert exc_info.value.code == "INVALID_SESSION_MANIFEST"


def test_existing_session_is_not_overwritten(session_factory, phase75_initial_state_file):
    session_dir, _ = session_factory()
    with pytest.raises(SessionError) as exc_info:
        SessionService.start(
            session_dir,
            session_id="session-001",
            actor_id="player",
            max_decisions=5,
            initial_state_path=phase75_initial_state_file,
        )
    assert exc_info.value.code == "SESSION_ALREADY_EXISTS"


def test_missing_session_and_missing_required_files_fail_closed(
    tmp_path, session_factory
):
    with pytest.raises(SessionError) as missing:
        SessionService(tmp_path / "missing").status()
    assert missing.value.code == "SESSION_NOT_FOUND"
    session_dir, _ = session_factory()
    (session_dir / "recorded_decisions.json").unlink()
    with pytest.raises(SessionError) as incomplete:
        SessionService(session_dir).verify()
    assert incomplete.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_unsupported_files_and_noncanonical_or_invalid_edge_json_fail_closed(
    session_factory
):
    session_dir, _ = session_factory(name="edge-files")
    (session_dir / "worldpack.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SessionError) as extra:
        SessionService(session_dir).status()
    assert extra.value.code == "SESSION_INTEGRITY_MISMATCH"

    (session_dir / "worldpack.json").unlink()
    (session_dir / "session.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SessionError) as manifest:
        SessionService(session_dir).status()
    assert manifest.value.code == "INVALID_SESSION_MANIFEST"

    session_dir, _ = session_factory(name="noncanonical")
    manifest_payload = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
    (session_dir / "session.json").write_text(
        json.dumps(manifest_payload), encoding="utf-8"
    )
    with pytest.raises(SessionError) as noncanonical:
        SessionService(session_dir).status()
    assert noncanonical.value.code == "INVALID_SESSION_MANIFEST"

    session_dir, _ = session_factory(name="bad-records")
    (session_dir / "recorded_decisions.json").write_text("{", encoding="utf-8")
    with pytest.raises(SessionError) as bad_records:
        SessionService(session_dir).status()
    assert bad_records.value.code == "SESSION_INTEGRITY_MISMATCH"

    session_dir, _ = session_factory(name="pretty-records")
    (session_dir / "recorded_decisions.json").write_text(
        '{"schema_version": 1, "decisions": []}', encoding="utf-8"
    )
    with pytest.raises(SessionError) as pretty_records:
        SessionService(session_dir).status()
    assert pretty_records.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_no_legal_actions_are_terminal_without_a_fake_wait_or_stop(tmp_path):
    state = make_phase75_state()
    state.data["player"]["hp"] = 0
    initial = tmp_path / "dead.json"
    initial.write_text(canonical_json(state.__dict__), encoding="utf-8")
    session_dir = tmp_path / "dead-session"
    started = SessionService.start(
        session_dir,
        session_id="dead-session",
        actor_id="player",
        max_decisions=5,
        initial_state_path=initial,
    )
    assert started["session"]["status"] == "NO_LEGAL_ACTIONS"
    assert SessionService(session_dir).next()["request"]["choices"] == []
    assert SessionService(session_dir).verify()["session"]["stop_reason"] == "NO_LEGAL_ACTIONS"
    _tamper_json(
        session_dir / "session.json",
        lambda p: p.__setitem__("current_request_fingerprint", "1" * 64),
    )
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).verify()
    assert exc_info.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_accepted_action_can_transition_to_no_legal_actions(tmp_path):
    state = execute(make_phase75_state(), "DROP", "initial-drop")
    state.data["expedition"]["encounter"] = {
        "active": True,
        "enemy_id": "fatal-signal",
        "enemy_hp": 10,
        "enemy_max_hp": 10,
        "enemy_attack": 100,
    }
    initial = tmp_path / "fatal-encounter.json"
    initial.write_text(canonical_json(state.__dict__), encoding="utf-8")
    session_dir = tmp_path / "fatal-encounter"
    SessionService.start(
        session_dir,
        session_id="fatal-encounter",
        actor_id="player",
        max_decisions=5,
        initial_state_path=initial,
    )
    request = SessionService(session_dir).next()["request"]
    fight = next(choice for choice in request["choices"] if choice["action_type"] == "FIGHT")
    result = SessionService(session_dir).choose(
        request_fingerprint=request["request_fingerprint"],
        choice_id=fight["choice_id"],
    )
    assert result["session"]["status"] == "NO_LEGAL_ACTIONS"
    assert result["request"]["choices"] == []


def test_atomic_edge_writes_and_strict_file_reader_fail_closed(tmp_path, monkeypatch):
    target = tmp_path / "edge.json"
    original_replace = session_service.os.replace
    monkeypatch.setattr(
        session_service.os,
        "replace",
        lambda source, destination: (_ for _ in ()).throw(OSError("replace failed")),
    )
    with pytest.raises(SessionError) as write_error:
        session_service._atomic_write_text(target, "{}")
    assert write_error.value.code == "SESSION_INTEGRITY_MISMATCH"
    monkeypatch.setattr(session_service.os, "replace", original_replace)
    with pytest.raises(SessionError) as json_error:
        session_service._atomic_write_json(target, {"unsupported": {1, 2}})
    assert json_error.value.code == "SESSION_INTEGRITY_MISMATCH"
    with pytest.raises(SessionError) as read_error:
        session_service._read_json_file(
            tmp_path / "missing.json",
            code="INVALID_SESSION_MANIFEST",
            require_canonical=True,
        )
    assert read_error.value.code == "INVALID_SESSION_MANIFEST"


def test_invalid_record_bundle_and_corrupt_sqlite_are_reported(
    session_factory
):
    session_dir, _ = session_factory(name="invalid-record-bundle")
    (session_dir / "recorded_decisions.json").write_text(
        canonical_json({"schema_version": 1, "decisions": [{}]}), encoding="utf-8"
    )
    with pytest.raises(SessionError) as records:
        SessionService(session_dir).status()
    assert records.value.code == "SESSION_INTEGRITY_MISMATCH"

    session_dir, _ = session_factory(name="corrupt-sqlite")
    (session_dir / "campaign.sqlite3").write_bytes(b"not a sqlite database")
    with pytest.raises(SessionError) as database:
        SessionService(session_dir).verify()
    assert database.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_recorded_replay_and_event_replay_fail_closed_when_independent_checks_fail(
    session_factory, monkeypatch
):
    session_dir, _ = session_factory(name="replay-failures")
    _action(session_dir, "DROP")
    original_replay = session_service.replay_events
    monkeypatch.setattr(
        session_service,
        "replay_events",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("replay failed")),
    )
    with pytest.raises(SessionError) as event_replay:
        SessionService(session_dir).verify()
    assert event_replay.value.code == "SESSION_INTEGRITY_MISMATCH"
    monkeypatch.setattr(session_service, "replay_events", original_replay)

    original_execute = session_service.execute_action
    monkeypatch.setattr(
        session_service,
        "execute_action",
        lambda *args, **kwargs: ActionExecutionResult(
            accepted=False,
            validation=ActionValidationResult(valid=False, action=None),
            events=tuple(),
            final_state=None,
        ),
    )
    with pytest.raises(SessionError) as recorded_replay:
        SessionService(session_dir).next()
    assert recorded_replay.value.code == "SESSION_INTEGRITY_MISMATCH"
    monkeypatch.setattr(session_service, "execute_action", original_execute)


def test_transition_boundary_maps_engine_and_sqlite_failures_without_writing(
    session_factory, monkeypatch
):
    session_dir, _ = session_factory(name="transition-failures")
    original_execute = session_service.execute_action
    monkeypatch.setattr(
        session_service,
        "execute_action",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("engine failure")),
    )
    request = SessionService(session_dir).next()["request"]
    drop = next(choice for choice in request["choices"] if choice["action_type"] == "DROP")
    with pytest.raises(SessionError) as engine_error:
        SessionService(session_dir).choose(
            request_fingerprint=request["request_fingerprint"], choice_id=drop["choice_id"]
        )
    assert engine_error.value.code == "ENGINE_REJECTED_LEGAL_CHOICE"
    monkeypatch.setattr(session_service, "execute_action", original_execute)

    original_append = EventStore.append_transition
    monkeypatch.setattr(
        EventStore,
        "append_transition",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("append failure")),
    )
    request = SessionService(session_dir).next()["request"]
    with pytest.raises(SessionError) as append_error:
        SessionService(session_dir).choose(
            request_fingerprint=request["request_fingerprint"], choice_id=drop["choice_id"]
        )
    assert append_error.value.code == "SESSION_INTEGRITY_MISMATCH"
    monkeypatch.setattr(EventStore, "append_transition", original_append)
    assert SessionService(session_dir).status()["session"]["accepted_decisions"] == 0


def test_transition_reject_and_prestate_mutation_are_fail_closed(
    session_factory, monkeypatch
):
    session_dir, _ = session_factory(name="transition-validation")
    original_execute = session_service.execute_action
    monkeypatch.setattr(
        session_service,
        "execute_action",
        lambda *args, **kwargs: ActionExecutionResult(
            accepted=False,
            validation=ActionValidationResult(valid=False, action=None),
            events=tuple(),
            final_state=None,
        ),
    )
    request = SessionService(session_dir).next()["request"]
    drop = next(choice for choice in request["choices"] if choice["action_type"] == "DROP")
    with pytest.raises(SessionError) as rejected:
        SessionService(session_dir).choose(
            request_fingerprint=request["request_fingerprint"], choice_id=drop["choice_id"]
        )
    assert rejected.value.code == "ENGINE_REJECTED_LEGAL_CHOICE"
    monkeypatch.setattr(session_service, "execute_action", original_execute)

    def mutate_before_execution(state, intent):
        state.game_minute += 1
        return original_execute(state, intent)

    monkeypatch.setattr(session_service, "execute_action", mutate_before_execution)
    request = SessionService(session_dir).next()["request"]
    with pytest.raises(SessionError) as mutated:
        SessionService(session_dir).choose(
            request_fingerprint=request["request_fingerprint"], choice_id=drop["choice_id"]
        )
    assert mutated.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_atomic_start_cleans_temp_directory_on_initialize_and_publish_failures(
    tmp_path, phase75_initial_state_file, monkeypatch
):
    original_initialize = EventStore.initialize
    monkeypatch.setattr(
        EventStore,
        "initialize",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("initialize failure")),
    )
    target = tmp_path / "initialize-failure"
    with pytest.raises(SessionError) as initialize_error:
        SessionService.start(
            target,
            session_id="initialize-failure",
            actor_id="player",
            max_decisions=5,
            initial_state_path=phase75_initial_state_file,
        )
    assert initialize_error.value.code == "SESSION_INTEGRITY_MISMATCH"
    assert not target.exists()
    monkeypatch.setattr(EventStore, "initialize", original_initialize)

    original_atomic = session_service._atomic_write_text
    monkeypatch.setattr(
        session_service,
        "_atomic_write_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("edge write failure")),
    )
    target = tmp_path / "edge-write-failure"
    with pytest.raises(SessionError) as write_error:
        SessionService.start(
            target,
            session_id="edge-write-failure",
            actor_id="player",
            max_decisions=5,
            initial_state_path=phase75_initial_state_file,
        )
    assert write_error.value.code == "SESSION_INTEGRITY_MISMATCH"
    assert not target.exists()
    monkeypatch.setattr(session_service, "_atomic_write_text", original_atomic)


def test_atomic_publish_rejects_racing_target_and_stop_checks_stale_request(
    session_factory, monkeypatch
):
    session_dir, _ = session_factory(name="publish-race")
    request = SessionService(session_dir).next()["request"]
    with pytest.raises(SessionError) as stale:
        SessionService(session_dir).stop(request_fingerprint="0" * 64)
    assert stale.value.code == "STALE_REQUEST"

    import os

    original_rename = os.rename
    monkeypatch.setattr(
        session_service.os,
        "rename",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileExistsError("racing target")),
    )
    target = session_dir.parent / "publish-race-target"
    with pytest.raises(SessionError) as race:
        SessionService.start(
            target,
            session_id="publish-race-target",
            actor_id="player",
            max_decisions=5,
            initial_state_path=session_dir.parent / "initial-state.json",
        )
    assert race.value.code == "SESSION_ALREADY_EXISTS"
    monkeypatch.setattr(session_service.os, "rename", original_rename)


@pytest.mark.parametrize("field", ["current_state_hash", "accepted_decisions", "current_request_fingerprint"])
def test_manifest_tampering_fails_closed(session_factory, field):
    session_dir, _ = session_factory()
    if field == "current_state_hash":
        _tamper_json(session_dir / "session.json", lambda p: p.__setitem__(field, "0" * 64))
    elif field == "accepted_decisions":
        _tamper_json(
            session_dir / "session.json",
            lambda p: (p.__setitem__(field, 1), p.__setitem__("recorded_decision_count", 1)),
        )
    else:
        _tamper_json(session_dir / "session.json", lambda p: p.__setitem__(field, "1" * 64))
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).verify()
    assert exc_info.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_recorded_choice_tampering_fails_recorded_replay(session_factory):
    session_dir, _ = session_factory()
    _action(session_dir, "DROP")
    _tamper_json(
        session_dir / "recorded_decisions.json",
        lambda p: p["decisions"][0].__setitem__("choice_id", "choice-999"),
    )
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).next()
    assert exc_info.value.code == "SESSION_INTEGRITY_MISMATCH"


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("actor_id", "forged-actor"),
        ("action_id", "forged-action"),
        ("causation_id", "forged-causation"),
        ("correlation_id", "forged-correlation"),
    ],
)
def test_persisted_event_provenance_tampering_fails_transition_trace(
    session_factory, column, value
):
    session_dir, _ = session_factory(name=f"tampered-{column}")
    _action(session_dir, "DROP")
    _tamper_event_column(session_dir, column, value)
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).verify()
    assert exc_info.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_persisted_event_payload_extra_field_fails_transition_trace(session_factory):
    session_dir, _ = session_factory(name="tampered-payload")
    _action(session_dir, "DROP")
    connection = sqlite3.connect(session_dir / "campaign.sqlite3")
    try:
        payload_json = connection.execute(
            "SELECT payload_json FROM events WHERE event_seq = 1"
        ).fetchone()[0]
        payload = json.loads(payload_json)
        payload["forged_reward"] = 99
        connection.execute(
            "UPDATE events SET payload_json = ? WHERE event_seq = 1",
            (json.dumps(payload, ensure_ascii=False),),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).verify()
    assert exc_info.value.code == "SESSION_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("outcome", ["ACTION", "STOP"])
def test_phase9a_raw_response_must_be_exact_canonical_edge_response(
    session_factory, outcome
):
    session_dir, _ = session_factory(name=f"tampered-raw-{outcome.lower()}")
    request = SessionService(session_dir).next()["request"]
    if outcome == "ACTION":
        choice = choice_for(request, "DROP")
        SessionService(session_dir).choose(
            request_fingerprint=request["request_fingerprint"],
            choice_id=choice["choice_id"],
        )
        tampered_response = '{ "choice_id": "choice-000" }'
    else:
        SessionService(session_dir).stop(
            request_fingerprint=request["request_fingerprint"]
        )
        tampered_response = '{"stop":true,"ignored":false}'
    _tamper_json(
        session_dir / "recorded_decisions.json",
        lambda p: p["decisions"][0].__setitem__("raw_response", tampered_response),
    )
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).verify()
    assert exc_info.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_sqlite_snapshot_tampering_fails_persistence_integrity(session_factory):
    session_dir, _ = session_factory()
    _action(session_dir, "DROP")
    connection = sqlite3.connect(session_dir / "campaign.sqlite3")
    try:
        connection.execute(
            "UPDATE snapshots SET state_json = ? WHERE event_seq = 1", ("{}",)
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).verify()
    assert exc_info.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_max_decisions_is_action_only_and_does_not_invent_stop(session_factory):
    session_dir, _ = session_factory(name="limited", max_decisions=2)
    _action(session_dir, "DROP")
    _action(session_dir, "SEARCH")
    status = SessionService(session_dir).status()["session"]
    assert status["status"] == "MAX_DECISIONS"
    assert status["accepted_decisions"] == 2
    assert status["recorded_decision_count"] == 2
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).choose(request_fingerprint="", choice_id="choice-000")
    assert exc_info.value.code == "SESSION_TERMINAL"
    assert SessionService(session_dir).verify()["verification"]["event_count"] == 2


def test_stopped_at_max_decisions_is_an_impossible_lifecycle_state(session_factory):
    session_dir, _ = session_factory(name="stopped-at-max", max_decisions=1)
    _action(session_dir, "DROP")
    _tamper_json(
        session_dir / "recorded_decisions.json",
        lambda p: p["decisions"].append(
            {
                "decision_number": 2,
                "request_fingerprint": "0" * 64,
                "outcome": "STOP",
                "choice_id": None,
                "action_type": None,
                "params": {},
                "raw_response": canonical_json({"stop": True}),
            }
        ),
    )
    _tamper_json(
        session_dir / "session.json",
        lambda p: (
            p.__setitem__("status", "STOPPED"),
            p.__setitem__("stop_reason", "EXPLICIT_STOP"),
            p.__setitem__("recorded_decision_count", 2),
        ),
    )
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).verify()
    assert exc_info.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_no_legal_actions_at_max_decisions_is_an_impossible_lifecycle_state(tmp_path):
    state = execute(make_phase75_state(), "DROP", "drop-for-no-legal-max")
    state.data["expedition"]["encounter"] = {
        "active": True,
        "enemy_id": "fatal-signal",
        "enemy_hp": 10,
        "enemy_max_hp": 10,
        "enemy_attack": 100,
    }
    initial = tmp_path / "fatal-max-initial.json"
    initial.write_text(canonical_json(state.__dict__), encoding="utf-8")
    session_dir = tmp_path / "no-legal-at-max"
    SessionService.start(
        session_dir,
        session_id="no-legal-at-max",
        actor_id="player",
        max_decisions=1,
        initial_state_path=initial,
    )
    _action(session_dir, "FIGHT")
    assert SessionService(session_dir).status()["session"]["status"] == "MAX_DECISIONS"
    _tamper_json(
        session_dir / "session.json",
        lambda p: (
            p.__setitem__("status", "NO_LEGAL_ACTIONS"),
            p.__setitem__("stop_reason", "NO_LEGAL_ACTIONS"),
        ),
    )
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).verify()
    assert exc_info.value.code == "SESSION_INTEGRITY_MISMATCH"


def test_close_reopen_resume_matches_same_policy_path(session_factory):
    first_dir, _ = session_factory(name="first")
    second_dir, _ = session_factory(name="second")
    for action_type in ("DROP", "SEARCH", "EXTRACT", "TALK_TO_ACTOR"):
        _action(first_dir, action_type)
        _action(second_dir, action_type)
    first = SessionService(first_dir).status()["session"]
    second = SessionService(second_dir).status()["session"]
    assert first["current_state_hash"] == second["current_state_hash"]
    assert first["current_event_seq"] == second["current_event_seq"] == 4
    assert SessionService(first_dir).verify()["verification"]["event_replay"] is True
    assert SessionService(second_dir).verify()["verification"]["recorded_decision_replay"] is True


def test_sqlite_can_be_closed_and_reopened_without_live_service_state(session_factory):
    session_dir, _ = session_factory()
    _action(session_dir, "DROP")
    store = EventStore(session_dir / "campaign.sqlite3")
    try:
        first = store.latest_snapshot_record("session-001")
    finally:
        store.close()
    reopened = EventStore(session_dir / "campaign.sqlite3")
    try:
        second = reopened.latest_snapshot_record("session-001")
    finally:
        reopened.close()
    assert first is not None and second is not None
    assert first.state_hash == second.state_hash
