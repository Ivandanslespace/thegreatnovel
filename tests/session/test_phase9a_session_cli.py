from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import tgn.session.__main__ as session_cli
from tgn.session.__main__ import main

from .conftest import choice_for

ROOT = Path(__file__).resolve().parents[2]


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tgn.session", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _json_output(result: subprocess.CompletedProcess[str]) -> dict:
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
    assert result.stdout.strip()
    return json.loads(result.stdout)


def test_cli_start_next_stop_status_verify_are_json_and_reopenable(
    tmp_path: Path, phase75_initial_state_file: Path
):
    session_dir = tmp_path / "cli-session"
    started = _run_cli(
        "start",
        "--session-dir",
        str(session_dir),
        "--session-id",
        "cli-session",
        "--actor-id",
        "player",
        "--max-decisions",
        "5",
        "--initial-state",
        str(phase75_initial_state_file),
    )
    assert started.returncode == 0
    assert _json_output(started)["session"]["status"] == "AWAITING_DECISION"

    next_result = _run_cli("next", "--session-dir", str(session_dir))
    next_payload = _json_output(next_result)
    assert next_result.returncode == 0
    fingerprint = next_payload["request"]["request_fingerprint"]

    stopped = _run_cli(
        "stop",
        "--session-dir",
        str(session_dir),
        "--request-fingerprint",
        fingerprint,
    )
    assert stopped.returncode == 0
    assert _json_output(stopped)["session"]["status"] == "STOPPED"

    status = _run_cli("status", "--session-dir", str(session_dir))
    assert status.returncode == 0
    assert _json_output(status)["session"]["recorded_decision_count"] == 1
    verified = _run_cli("verify", "--session-dir", str(session_dir))
    assert verified.returncode == 0
    assert _json_output(verified)["verification"]["sqlite_persistence_integrity"] is True


def test_cli_rejects_stale_request_and_unknown_command_without_traceback(
    tmp_path: Path, phase75_initial_state_file: Path
):
    session_dir = tmp_path / "cli-session"
    start = _run_cli(
        "start",
        "--session-dir",
        str(session_dir),
        "--session-id",
        "cli-session",
        "--actor-id",
        "player",
        "--max-decisions",
        "2",
        "--initial-state",
        str(phase75_initial_state_file),
    )
    assert start.returncode == 0
    stale = _run_cli(
        "choose",
        "--session-dir",
        str(session_dir),
        "--request-fingerprint",
        "0" * 64,
        "--choice-id",
        "choice-000",
    )
    assert stale.returncode != 0
    assert _json_output(stale)["error"]["code"] == "STALE_REQUEST"
    help_result = _run_cli("--help")
    assert help_result.returncode == 0
    assert "Traceback" not in help_result.stderr


def test_cli_in_process_dispatch_covers_external_command_boundary(
    tmp_path: Path, phase75_initial_state_file: Path, capsys
):
    session_dir = tmp_path / "direct-cli"
    assert (
        main(
            [
                "start",
                "--session-dir",
                str(session_dir),
                "--session-id",
                "direct-cli",
                "--actor-id",
                "player",
                "--max-decisions",
                "5",
                "--initial-state",
                str(phase75_initial_state_file),
            ]
        )
        == 0
    )
    start_output = json.loads(capsys.readouterr().out)
    assert start_output["ok"] is True

    assert main(["next", "--session-dir", str(session_dir)]) == 0
    request = json.loads(capsys.readouterr().out)["request"]
    drop = choice_for(request, "DROP")
    assert (
        main(
            [
                "choose",
                "--session-dir",
                str(session_dir),
                "--request-fingerprint",
                request["request_fingerprint"],
                "--choice-id",
                drop["choice_id"],
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["result"]["action_type"] == "DROP"

    assert main(["next", "--session-dir", str(session_dir)]) == 0
    request = json.loads(capsys.readouterr().out)["request"]
    assert main(
        [
            "stop",
            "--session-dir",
            str(session_dir),
            "--request-fingerprint",
            request["request_fingerprint"],
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["session"]["status"] == "STOPPED"
    assert main(["status", "--session-dir", str(session_dir)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert main(["verify", "--session-dir", str(session_dir)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    assert main(["unknown"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_ARGUMENTS"
    assert main(["next", "--session-dir", str(session_dir), "--bad"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_ARGUMENTS"
    with pytest.raises(Exception):
        session_cli._dispatch(type("Arguments", (), {"command": "unknown", "session_dir": str(session_dir)})())


def test_cli_converts_unexpected_boundary_failure_to_stable_json(
    tmp_path: Path, capsys, monkeypatch
):
    monkeypatch.setattr(session_cli, "_dispatch", lambda arguments: (_ for _ in ()).throw(RuntimeError("boom")))
    assert main(["status", "--session-dir", str(tmp_path / "never")]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["error"]["code"] == "SESSION_INTEGRITY_MISMATCH"
