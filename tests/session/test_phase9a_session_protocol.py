from __future__ import annotations

import copy

import pytest

from tgn.core.hashing import state_hash
from tgn.gameplay.named_actor import MARA_FACT_ID
from tgn.session import (
    SessionError,
    SessionService,
    choose_session,
    next_session,
    start_session,
    status_session,
    stop_session,
    verify_session,
)
from tgn.storage.event_store import EventStore
from tgn.storage.replay import verify_persistence_integrity

from .conftest import choice_for


def _choose(session_dir, action_type: str):
    current = SessionService(session_dir).next()
    choice = choice_for(current["request"], action_type)
    return SessionService(session_dir).choose(
        request_fingerprint=current["request"]["request_fingerprint"],
        choice_id=choice["choice_id"],
    )


def _latest_state(session_dir):
    store = EventStore(session_dir / "campaign.sqlite3")
    try:
        record = store.latest_snapshot_record("session-001")
        assert record is not None
        return record.state
    finally:
        store.close()


def test_start_next_is_detached_and_repeated_next_is_read_only(session_factory):
    session_dir, started = session_factory()
    assert started["session"]["status"] == "AWAITING_DECISION"
    first = SessionService(session_dir).next()
    second = SessionService(session_dir).next()
    assert first == second
    mutated = copy.deepcopy(first)
    mutated["request"]["choices"][0]["params"]["tampered"] = True
    mutated["session"]["accepted_decisions"] = 99
    assert SessionService(session_dir).next() == first


def test_external_client_phase75_path_reopens_between_every_command(session_factory):
    session_dir, _ = session_factory()
    assert _choose(session_dir, "DROP")["result"]["action_type"] == "DROP"
    site_request = SessionService(session_dir).next()["request"]
    assert "site-1-condition" not in site_request["observation"]
    assert site_request["observation"]["actor"]["visible"] is False
    assert site_request["observation"]["actor"]["known_goal"] == "inspect_signal"
    assert "knowledge" not in site_request["observation"]["actor"]

    assert _choose(session_dir, "SEARCH")["result"]["action_type"] == "SEARCH"
    assert _choose(session_dir, "EXTRACT")["result"]["action_type"] == "EXTRACT"
    base_request = SessionService(session_dir).next()["request"]
    assert base_request["observation"]["actor"]["visible"] is True
    assert base_request["observation"]["actor"]["has_something_to_report"] is True
    assert "site-1-condition" not in base_request["observation"]["actor"]["facts"]

    talk = _choose(session_dir, "TALK_TO_ACTOR")
    assert talk["result"]["action_type"] == "TALK_TO_ACTOR"
    assert talk["result"]["event_type"] == "ACTOR_CONVERSATION_RESOLVED"
    state = _latest_state(session_dir)
    assert state["data"]["named_actor"]["relationship"]["trust"] == 1
    assert state["data"]["player_knowledge"]["facts"] == {
        MARA_FACT_ID: "unstable"
    }

    next_result = SessionService(session_dir).next()
    stopped = SessionService(session_dir).stop(
        request_fingerprint=next_result["request"]["request_fingerprint"]
    )
    assert stopped["session"]["accepted_decisions"] == 4
    assert stopped["session"]["recorded_decision_count"] == 5
    assert stopped["session"]["status"] == "STOPPED"
    assert stopped["session"]["stop_reason"] == "EXPLICIT_STOP"
    verification = SessionService(session_dir).verify()
    assert verification["verification"]["event_replay"] is True
    assert verification["verification"]["recorded_decision_replay"] is True
    assert verification["verification"]["sqlite_close_reopen"] is True
    assert verification["verification"]["event_count"] == 4


def test_stale_and_unknown_choices_do_not_change_authoritative_state(session_factory):
    session_dir, _ = session_factory()
    request = SessionService(session_dir).next()["request"]
    before = SessionService(session_dir).status()
    with pytest.raises(SessionError) as stale:
        SessionService(session_dir).choose(
            request_fingerprint="0" * 64, choice_id="choice-000"
        )
    assert stale.value.code == "STALE_REQUEST"
    with pytest.raises(SessionError) as unknown:
        SessionService(session_dir).choose(
            request_fingerprint=request["request_fingerprint"], choice_id="choice-999"
        )
    assert unknown.value.code == "UNKNOWN_CHOICE"
    after = SessionService(session_dir).status()
    assert after == before
    assert verify_persistence_integrity("session-001", session_dir / "campaign.sqlite3").success


def test_stop_records_only_a_stop_and_is_terminal(session_factory):
    session_dir, _ = session_factory()
    request = SessionService(session_dir).next()["request"]
    result = SessionService(session_dir).stop(
        request_fingerprint=request["request_fingerprint"]
    )
    assert result["session"]["accepted_decisions"] == 0
    assert result["session"]["recorded_decision_count"] == 1
    assert result["request"] is None
    with pytest.raises(SessionError) as exc_info:
        SessionService(session_dir).choose(
            request_fingerprint=request["request_fingerprint"], choice_id="choice-000"
        )
    assert exc_info.value.code == "SESSION_TERMINAL"
    with pytest.raises(SessionError) as stop_again:
        SessionService(session_dir).stop(
            request_fingerprint=request["request_fingerprint"]
        )
    assert stop_again.value.code == "SESSION_TERMINAL"
    store = EventStore(session_dir / "campaign.sqlite3")
    try:
        assert store.all_event_records("session-001") == []
    finally:
        store.close()


def test_phase75_resume_has_stable_state_hash_and_replay_result(session_factory):
    session_dir, _ = session_factory()
    action_results = [_choose(session_dir, action) for action in ("DROP", "SEARCH", "EXTRACT", "TALK_TO_ACTOR")]
    assert [result["result"]["action_type"] for result in action_results] == [
        "DROP", "SEARCH", "EXTRACT", "TALK_TO_ACTOR"
    ]
    final_status = SessionService(session_dir).status()
    persistence = verify_persistence_integrity("session-001", session_dir / "campaign.sqlite3")
    assert persistence.success
    assert persistence.actual_hash == final_status["session"]["current_state_hash"]
    assert state_hash(persistence.final_state) == final_status["session"]["current_state_hash"]


def test_module_level_session_facade_preserves_one_shot_contract(
    tmp_path, phase75_initial_state_file
):
    session_dir = tmp_path / "facade"
    started = start_session(
        session_dir,
        session_id="facade",
        actor_id="player",
        max_decisions=3,
        initial_state_path=phase75_initial_state_file,
    )
    assert started["ok"] is True
    request = next_session(session_dir)["request"]
    choice = choice_for(request, "DROP")
    chosen = choose_session(
        session_dir,
        request_fingerprint=request["request_fingerprint"],
        choice_id=choice["choice_id"],
    )
    assert chosen["result"]["action_type"] == "DROP"
    next_request = next_session(session_dir)["request"]
    stopped = stop_session(
        session_dir, request_fingerprint=next_request["request_fingerprint"]
    )
    assert stopped["session"]["status"] == "STOPPED"
    assert status_session(session_dir)["session"]["status"] == "STOPPED"
    assert verify_session(session_dir)["verification"]["event_count"] == 1
