from __future__ import annotations

import copy
import hashlib
import io
import os
import stat
from pathlib import Path

import pytest

import tgn.play.common as common
import tgn.play.narrator_process as narrator
import tgn.play.service as service
from tgn.play.common import PlayError, canonical_document


def _fails(function, *args, **kwargs) -> None:
    with pytest.raises(PlayError):
        function(*args, **kwargs)


def _session(*, status: str = "AWAITING_DECISION") -> dict[str, object]:
    return {
        "schema_version": 1,
        "session_id": "campaign-001",
        "campaign_id": "campaign-001",
        "actor_id": "player",
        "max_decisions": 20,
        "accepted_decisions": 0,
        "recorded_decision_count": 0,
        "status": status,
        "stop_reason": None if status == "AWAITING_DECISION" else ("EXPLICIT_STOP" if status == "STOPPED" else status),
        "current_event_seq": 0,
        "current_state_decision_seq": 0,
        "current_state_hash": "1" * 64,
        "current_request_fingerprint": "2" * 64 if status == "AWAITING_DECISION" else None,
    }


def _campaign_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "campaign_format_id": "phase9b2b-campaign-v1",
        "campaign_id": "campaign-001",
        "worldpack_hash": "a" * 64,
        "source_initial_state_hash": "b" * 64,
        "world_bundle_manifest_hash": "c" * 64,
        "player_projection_hash": "d" * 64,
        "projection_bundle_manifest_hash": "e" * 64,
        "initial_request_fingerprint": "f" * 64,
        "initial_presentation_hash": "0" * 64,
        "session_id": "campaign-001",
        "actor_id": "player",
        "max_decisions": 20,
        "initial_session_state_hash": "1" * 64,
    }


def _story_manifest() -> dict[str, object]:
    campaign = _campaign_manifest()
    return {
        "schema_version": 1,
        "story_format_id": "phase9c-story-v1",
        "story_id": "story-001",
        "campaign_id": "campaign-001",
        "campaign_manifest_hash": hashlib.sha256(canonical_document(campaign)).hexdigest(),
        "worldpack_hash": campaign["worldpack_hash"],
        "source_initial_state_hash": campaign["source_initial_state_hash"],
        "player_projection_hash": campaign["player_projection_hash"],
        "session_id": "campaign-001",
        "initial_narration_locale": "en",
        "initial_voice_id": "cablecar_survival",
    }


def _story_status() -> dict[str, object]:
    session = _session()
    return {
        "ok": True,
        "story": _story_manifest(),
        "campaign_session": copy.deepcopy(session),
        "session": copy.deepcopy(session),
        "accepted_decisions": 0,
        "recorded_decision_count": 0,
        "request_count": 0,
        "committed_turn_count": 0,
        "committed_prefix": 0,
        "pending_turn_id": None,
        "missing_request_turn_ids": [],
        "next_preparable_turn_id": None,
        "novel_status": "ABSENT",
        "export_readiness": {
            "snapshot_exportable_through": 0,
            "current_snapshot_ready": True,
            "final_ready": False,
        },
        "phase_9c2_export_ready": True,
        "missing_narration_work": False,
    }


def _valid_pair() -> dict[str, object]:
    choice = {
        "choice_id": "choice-1",
        "action_type": "WAIT",
        "params": {},
        "duration_minutes": None,
        "stamina_cost": 0,
    }
    return {
        "session": _session(),
        "canonical_request": {"request_fingerprint": "2" * 64, "choices": [choice]},
        "player_presentation": {"request_fingerprint": "2" * 64, "choices": [copy.deepcopy(choice)]},
    }


def test_common_uncovered_error_and_identity_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with pytest.raises(PlayError):
        common.lexical_absolute("bad\x00path")
    target = tmp_path / "blocked" / "child"

    real_lstat = common.os.lstat

    def symlink_lstat(path):
        if Path(path) == tmp_path / "blocked":
            return type("Stat", (), {"st_mode": stat.S_IFLNK, "st_file_attributes": 0})()
        return real_lstat(path)

    monkeypatch.setattr(common.os, "lstat", symlink_lstat)
    with pytest.raises(OSError):
        common._reject_untrusted_components(target, allow_missing=True)

    monkeypatch.setattr(common, "_reject_untrusted_components", lambda *_args, **_kwargs: (_ for _ in ()).throw(PlayError("INVALID_PLAY_INPUT", "x")))
    _fails(common.ensure_new_workspace, tmp_path / "new")
    _fails(common.require_workspace, tmp_path / "new")

    regular = tmp_path / "regular"
    regular.write_text("x", encoding="utf-8")
    _fails(common.require_workspace, regular)
    _fails(common.parse_positive_integer, "9" * 1001, "number")
    with pytest.raises(TypeError):
        common.terminal_safe_text(None)  # type: ignore[arg-type]


def test_common_response_file_identity_and_cleanup_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    response = tmp_path / "response.json"
    response.write_bytes(b'{"ok":true}')
    real_fstat = common.os.fstat
    calls = {"count": 0}

    def changed_fstat(fd):
        calls["count"] += 1
        value = real_fstat(fd)
        if calls["count"] == 1:
            return type("Stat", (), {"st_mode": value.st_mode, "st_dev": value.st_dev + 1, "st_ino": value.st_ino, "st_size": value.st_size, "st_mtime_ns": value.st_mtime_ns, "st_file_attributes": 0})()
        return value

    monkeypatch.setattr(common.os, "fstat", changed_fstat)
    _fails(common.read_external_json, response)

    monkeypatch.undo()
    calls = {"count": 0}

    def changed_after(fd):
        calls["count"] += 1
        value = real_fstat(fd)
        if calls["count"] == 2:
            return type("Stat", (), {"st_mode": value.st_mode, "st_dev": value.st_dev, "st_ino": value.st_ino + 1, "st_size": value.st_size, "st_mtime_ns": value.st_mtime_ns, "st_file_attributes": 0})()
        return value

    monkeypatch.setattr(common.os, "fstat", changed_after)
    _fails(common.read_external_json, response)

    monkeypatch.undo()
    original_open = common.os.open
    monkeypatch.setattr(common.os, "open", lambda *args, **kwargs: original_open(*args, **kwargs))
    monkeypatch.setattr(common.os, "close", lambda _fd: (_ for _ in ()).throw(OSError("close")))
    _fails(common.read_external_json, tmp_path / "missing.json")


def test_narrator_cleanup_and_process_outcome_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    class Process:
        def __init__(self, *, poll_value=None, wait_fail=False, stdout=None):
            self.returncode = 0
            self.stdout = stdout if stdout is not None else io.BytesIO(b'{"ok":true}')
            self.poll_value = poll_value
            self.wait_fail = wait_fail
            self.kills = 0
            self.waits = 0

        def poll(self):
            return self.poll_value

        def kill(self):
            self.kills += 1

        def wait(self, timeout=None):
            self.waits += 1
            if self.wait_fail:
                raise OSError("wait")
            return self.returncode

    class CloseFail:
        def close(self):
            raise OSError("close")

    narrator._kill_and_wait(Process(poll_value=None))
    narrator._kill_and_wait(Process(poll_value=None, wait_fail=True))

    class PollFailure:
        def poll(self):
            raise OSError("poll")

        def wait(self, timeout=None):
            return None

    class KillFailure:
        def poll(self):
            return None

        def kill(self):
            raise OSError("kill")

        def wait(self, timeout=None):
            raise OSError("wait")

    narrator._kill_and_wait(PollFailure())
    narrator._kill_and_wait(KillFailure())
    narrator._close_stream(None)
    narrator._close_stream(CloseFail())
    _fails(narrator.run_narrator, ["python"], {"bad": object()})

    process = Process()
    process.stdout = None
    monkeypatch.setattr(narrator.subprocess, "Popen", lambda *_args, **_kwargs: process)
    _fails(narrator.run_narrator, ["python"], {"ok": True})

    nonzero = Process()
    nonzero.returncode = 7
    monkeypatch.setattr(narrator.subprocess, "Popen", lambda *_args, **_kwargs: nonzero)
    _fails(narrator.run_narrator, ["python"], {"ok": True})

    timeout_process = Process()

    def timeout_wait(*_args, **_kwargs):
        raise narrator.subprocess.TimeoutExpired(["python"], 1)

    timeout_process.wait = timeout_wait
    monkeypatch.setattr(narrator.subprocess, "Popen", lambda *_args, **_kwargs: timeout_process)
    _fails(narrator.run_narrator, ["python"], {"ok": True})

    class ExtraStream:
        def __init__(self):
            self.parts = [b"x" * (narrator.MAX_NARRATOR_STDOUT + 1), b"x"]

        def read(self, _size):
            return self.parts.pop(0) if self.parts else b""

        def close(self):
            return None

    overflow_process = Process(stdout=ExtraStream())
    monkeypatch.setattr(narrator.subprocess, "Popen", lambda *_args, **_kwargs: overflow_process)
    _fails(narrator.run_narrator, ["python"], {"ok": True})


def test_narrator_interrupted_and_cleanup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class File:
        def write(self, _value):
            raise KeyboardInterrupt

        def flush(self):
            return None

        def seek(self, _value):
            return None

        def close(self):
            return None

    monkeypatch.setattr(narrator.tempfile, "TemporaryFile", lambda **_kwargs: File())
    _fails(narrator.run_narrator, ["python"], {"ok": True})

    class Process:
        stdout = io.BytesIO(b'{"ok":true}')
        returncode = 0

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            return None

    class ClosingFile:
        def write(self, value):
            return len(value)

        def flush(self):
            return None

        def seek(self, _value):
            return None

        def close(self):
            raise OSError("cleanup")

    monkeypatch.setattr(narrator.tempfile, "TemporaryFile", lambda **_kwargs: ClosingFile())
    monkeypatch.setattr(narrator.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    _fails(narrator.run_narrator, ["python"], {"ok": True})


def test_service_strict_scalar_manifest_and_choice_edges() -> None:
    assert service._map_boundary_error(RuntimeError("x"), operation="x", boundary="campaign").code == "PLAY_CAMPAIGN_FAILED"
    assert service._map_boundary_error(RuntimeError("x"), operation="x", boundary="narrator").code == "PLAY_NARRATOR_FAILED"
    for value in (None, 1, "x"):
        _fails(service._strict_bool, value, "field")
    for value in (True, "1", 1.0):
        _fails(service._strict_int, value, "field")
    _fails(service._strict_int, -1, "field", nonnegative=True)
    _fails(service._strict_int, 0, "field", positive=True)
    for value in (None, "A" * 64, "g" * 64):
        _fails(service._strict_sha, value, "field")
    for value in (None, "A", "bad id", "x" * 65):
        _fails(service._strict_id, value, "field")
    for value in (None, "turn-1", "turn-000001x", "turn-000000"):
        _fails(service._strict_turn_id, value)
    assert service._canonical_equal({"x": 1}, {"x": 1})
    assert not service._canonical_equal({"x": 1}, {"x": True})
    assert not service._canonical_equal(object(), object())

    manifest = _campaign_manifest()
    service._validate_manifest(manifest, label="campaign")
    story = _story_manifest()
    service._validate_manifest(story, label="story")
    for label, base in (("campaign", manifest), ("story", story)):
        for mutation in (None, {}, {"bad": 1}):
            _fails(service._validate_manifest, mutation, label=label)
        for field in ("schema_version", "campaign_format_id" if label == "campaign" else "story_format_id"):
            value = copy.deepcopy(base)
            value[field] = 2
            _fails(service._validate_manifest, value, label=label)
    value = copy.deepcopy(manifest)
    value["campaign_id"] = "other"
    _fails(service._validate_manifest, value, label="campaign")
    value = copy.deepcopy(story)
    value["initial_narration_locale"] = "fr"
    _fails(service._validate_manifest, value, label="story")

    valid_choice = _valid_pair()["canonical_request"]["choices"][0]
    for choice in (None, {}, {"choice_id": "x"}):
        _fails(service._validate_choice, choice, label="choice")
    for field, replacement in (("choice_id", 1), ("action_type", 1), ("params", []), ("duration_minutes", True), ("stamina_cost", -1)):
        choice = copy.deepcopy(valid_choice)
        choice[field] = replacement
        _fails(service._validate_choice, choice, label="choice")
    nested_invalid = copy.deepcopy(valid_choice)
    nested_invalid["params"] = {"opaque": object()}
    _fails(service._validate_choice, nested_invalid, label="choice")


def test_service_session_request_story_and_cross_checks() -> None:
    valid = _session()
    service._validate_session_summary(valid)
    for mutation in (None, {}, {"x": 1}):
        _fails(service._validate_session_summary, mutation)
    mutations = [
        ("schema_version", True),
        ("session_id", "bad id"),
        ("campaign_id", "bad id"),
        ("actor_id", "bad id"),
        ("max_decisions", 0),
        ("accepted_decisions", -1),
        ("recorded_decision_count", -1),
        ("current_event_seq", -1),
        ("current_state_decision_seq", -1),
        ("current_state_hash", "bad"),
        ("status", "UNKNOWN"),
        ("stop_reason", "wrong"),
        ("current_request_fingerprint", "bad"),
    ]
    for field, replacement in mutations:
        value = copy.deepcopy(valid)
        value[field] = replacement
        _fails(service._validate_session_summary, value)
    value = copy.deepcopy(valid)
    value["accepted_decisions"] = 21
    _fails(service._validate_session_summary, value)
    value = copy.deepcopy(valid)
    value["recorded_decision_count"] = -1
    _fails(service._validate_session_summary, value)
    value = copy.deepcopy(valid)
    value["current_request_fingerprint"] = None
    _fails(service._validate_session_summary, value)
    terminal = _session(status="STOPPED")
    terminal["current_request_fingerprint"] = "2" * 64
    _fails(service._validate_session_summary, terminal)

    pair = _valid_pair()
    service._validate_request_pair(pair)
    _fails(service._validate_request_pair, {"session": _session(), "canonical_request": None, "player_presentation": None})
    empty_presented = copy.deepcopy(pair)
    empty_presented["player_presentation"]["choices"] = []
    _fails(service._validate_request_pair, empty_presented)
    different_counts = copy.deepcopy(pair)
    different_counts["player_presentation"]["choices"].append(copy.deepcopy(different_counts["player_presentation"]["choices"][0]))
    _fails(service._validate_request_pair, different_counts)
    different_ids = copy.deepcopy(pair)
    different_ids["player_presentation"]["choices"][0]["choice_id"] = "choice-2"
    _fails(service._validate_request_pair, different_ids)
    mutations = [{"canonical_request": None, "player_presentation": {}}]
    stopped_pair = copy.deepcopy(pair)
    stopped_pair["session"] = _session(status="STOPPED")
    mutations.append(stopped_pair)
    for value in mutations:
        _fails(service._validate_request_pair, value)
    value = copy.deepcopy(pair)
    value["session"]["current_request_fingerprint"] = "3" * 64
    _fails(service._validate_request_pair, value)
    value = copy.deepcopy(pair)
    value["player_presentation"]["request_fingerprint"] = "3" * 64
    _fails(service._validate_request_pair, value)
    value = copy.deepcopy(pair)
    value["player_presentation"]["choices"][0]["choice_id"] = "other"
    _fails(service._validate_request_pair, value)

    campaign = {"ok": True, "campaign": _campaign_manifest(), "session": _session(), **_valid_pair()}
    service._validate_campaign_result(campaign)
    _fails(service._validate_campaign_result, {"ok": False})
    _fails(service._validate_campaign_result, campaign, require_verification=True)
    verified = copy.deepcopy(campaign)
    verified["verification"] = {"valid": True}
    service._validate_campaign_result(verified, require_verification=True)

    story = _story_status()
    service._validate_story_status(story)
    missing_required = copy.deepcopy(story)
    del missing_required["missing_narration_work"]
    _fails(service._validate_story_status, missing_required)
    for field, replacement in (("ok", False), ("missing_request_turn_ids", None), ("novel_status", "bad"), ("phase_9c2_export_ready", "yes")):
        value = copy.deepcopy(story)
        value[field] = replacement
        _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["session"]["actor_id"] = "other"
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["accepted_decisions"] = 1
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["request_count"] = 1
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["pending_turn_id"] = "turn-000001"
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["missing_request_turn_ids"] = ["turn-000001"]
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["next_preparable_turn_id"] = "turn-000001"
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["export_readiness"]["snapshot_exportable_through"] = 1
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["export_readiness"]["extra"] = False
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["export_readiness"]["current_snapshot_ready"] = False
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["missing_narration_work"] = True
    _fails(service._validate_story_status, value)
    value = copy.deepcopy(story)
    value["phase_9c2_export_ready"] = False
    _fails(service._validate_story_status, value)

    good_campaign = {"campaign": _campaign_manifest(), "session": _session()}
    good_full = {"ok": True, **good_campaign, "canonical_request": None, "player_presentation": None}
    # Cross checking uses a terminal-shaped Campaign when no request is needed.
    good_story = copy.deepcopy(story)
    service._cross_check(good_full, good_story)
    bad_story = copy.deepcopy(good_story)
    bad_story["story"]["worldpack_hash"] = "9" * 64
    _fails(service._cross_check, good_full, bad_story)
    bad_story = copy.deepcopy(good_story)
    bad_story["campaign_session"]["actor_id"] = "other"
    _fails(service._cross_check, good_full, bad_story)


def test_service_preflight_and_method_error_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for value in ([], "-", ["python", "bad\x00arg"], [""]):
        _fails(service._validate_narrator_argv, value)
    _fails(service._validate_callable, None, "callback")
    _fails(service._validate_id_input, "bad id", "id")
    _fails(service._validate_path, "bad\x00path", "path")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _fails(service._validate_response_path, "-", workspace)
    _fails(service._validate_response_path, workspace / "inside.json", workspace)
    assert service._validate_response_path(tmp_path / "outside.json", workspace) == tmp_path / "outside.json"
    monkeypatch.setattr(service.os.path, "commonpath", lambda _paths: (_ for _ in ()).throw(ValueError("different drives")))
    _fails(service._validate_response_path, tmp_path / "outside.json", workspace)

    facade = service.PlayService(workspace)
    _fails(facade._preflight_new, world_bundle_dir=tmp_path, projection_bundle_dir=tmp_path, campaign_id="bad id", story_id="s", actor_id="p", max_decisions=1, locale="en", voice_id="v", narrator_argv=None, narrator_timeout=1, input_fn=lambda: "", output_fn=lambda _: None)
    _fails(facade._preflight_resume, locale="fr", story_id="s", voice_id="v", narrator_argv=None, narrator_timeout=1, input_fn=lambda: "", output_fn=lambda _: None)
    _fails(facade._compose_status, {}, {})
    _fails(facade.export, mode="bad")
    _fails(facade.export, mode="final", accepted_decisions=0)
    _fails(facade.export, mode="snapshot", accepted_decisions=-1)

    campaign = workspace / "campaign"
    story = workspace / "story"
    campaign.mkdir()
    story.mkdir()
    monkeypatch.setattr(facade, "_layout", lambda **_kwargs: (campaign, story))
    monkeypatch.setattr(facade, "_read_status_pair", lambda *_args, **_kwargs: {"story_status": {"committed_prefix": 0, "novel_status": "ABSENT"}})
    monkeypatch.setattr(facade, "_call_story", lambda *_args, **_kwargs: {"ok": True})
    assert facade.export(mode="snapshot")["ok"] is True
    final_statuses = iter(
        [
            {"story_status": {"committed_prefix": 0, "novel_status": "ABSENT"}},
            {"story_status": {"novel_status": "ABSENT"}},
        ]
    )
    monkeypatch.setattr(facade, "_read_status_pair", lambda *_args, **_kwargs: next(final_statuses))
    _fails(facade.export, mode="final")


def test_service_rejects_out_of_range_option_before_engine_transition(play_context) -> None:
    context = play_context
    result = service.PlayService(context["workspace"]).new(
        world_bundle_dir=context["world"],
        projection_bundle_dir=context["projection"],
        campaign_id="campaign-001",
        story_id="story-001",
        actor_id="player",
        max_decisions=1,
        locale="en",
        voice_id="cablecar_survival",
        input_fn=iter(["999", "STOP"]).__next__,
        output_fn=lambda _value: None,
    )
    assert result["terminal"] is True
