from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import tgn.play.narrator_process as narrator_module
from tgn.play.common import (
    PlayError,
    canonical_document,
    ensure_new_workspace,
    parse_json_document,
    parse_nonnegative_integer,
    parse_positive_integer,
    read_external_json,
    require_workspace,
)
from tgn.play.narrator_process import run_narrator, validate_timeout

from .conftest import narrator_argv, write_narrator


def test_run_narrator_uses_explicit_argv_and_shell_false(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        seen["args"] = args
        seen.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=b'{"ok":true}', stderr=b"secret diagnostic")

    monkeypatch.setattr(narrator_module.subprocess, "run", fake_run)
    result = run_narrator(["python", "script.py", "argument;literal"], {"request": 1})
    assert result == {"ok": True}
    assert seen["args"] == (["python", "script.py", "argument;literal"],)
    assert seen["shell"] is False
    assert seen["check"] is False
    assert seen["stderr"] is subprocess.PIPE
    assert seen["input"] == canonical_document({"request": 1})


def test_run_narrator_real_success_and_nonzero(tmp_path: Path) -> None:
    success = write_narrator(tmp_path / "success.py")
    request = {
        "narration_request_id": "story-001:turn-000001",
        "narration_request_hash": "a" * 64,
        "narration_locale": "en",
        "claim_requirements": [],
    }
    result = run_narrator(narrator_argv(success), request)
    assert result["narration_request_id"] == request["narration_request_id"]

    failing = write_narrator(tmp_path / "failure.py", fail_first=True)
    with pytest.raises(PlayError) as error:
        run_narrator(narrator_argv(failing), request)
    assert error.value.code == "PLAY_NARRATOR_FAILED"


@pytest.mark.parametrize(
    "source, expected",
    [
        ("import sys; sys.stdout.write('{\\\"a\\\":1,\\\"a\\\":2}')", "invalid JSON"),
        ("import sys; sys.stdout.buffer.write(b'\\xff')", "invalid JSON"),
        ("import sys; sys.stdout.buffer.write(b'x' * (1024 * 1024 + 1))", "too large"),
    ],
)
def test_run_narrator_rejects_invalid_or_oversized_stdout(tmp_path: Path, source: str, expected: str) -> None:
    script = tmp_path / "bad.py"
    script.write_text(source, encoding="utf-8")
    with pytest.raises(PlayError) as error:
        run_narrator([sys.executable, str(script)], {"request": 1})
    assert error.value.code == "PLAY_NARRATOR_FAILED"
    assert expected in error.value.message


def test_run_narrator_timeout_is_bounded(tmp_path: Path) -> None:
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(2)", encoding="utf-8")
    with pytest.raises(PlayError) as error:
        run_narrator([sys.executable, str(script)], {"request": 1}, timeout=1)
    assert error.value.code == "PLAY_NARRATOR_FAILED"
    assert "timed out" in error.value.message


@pytest.mark.parametrize("value", [None, "0", "601", "nan", "inf"])
def test_timeout_validation(value) -> None:
    with pytest.raises(PlayError) as error:
        validate_timeout(value)
    assert error.value.code == "INVALID_PLAY_INPUT"


def test_strict_json_and_integer_helpers(tmp_path: Path) -> None:
    assert parse_json_document(b'{"b":2,"a":1}') == {"a": 1, "b": 2}
    with pytest.raises(ValueError):
        parse_json_document(b'{"a":1,"a":2}')
    with pytest.raises(ValueError):
        parse_json_document(b'{"a":NaN}')
    assert parse_positive_integer("1", "max_decisions") == 1
    assert parse_nonnegative_integer("0", "accepted_decisions") == 0
    for parser, value in ((parse_positive_integer, "01"), (parse_nonnegative_integer, "+1")):
        with pytest.raises(PlayError):
            parser(value, "number")

    response = tmp_path / "response.json"
    response.write_bytes(b'{"ok":true}')
    assert read_external_json(response) == {"ok": True}
    with pytest.raises(PlayError):
        read_external_json(tmp_path / "missing.json")


def test_workspace_creation_and_unknown_child_rejection(tmp_path: Path) -> None:
    workspace = ensure_new_workspace(tmp_path / "workspace")
    assert workspace.is_dir()
    assert require_workspace(workspace) == workspace
    (workspace / "unknown").mkdir()
    with pytest.raises(PlayError) as error:
        require_workspace(workspace)
    assert error.value.code == "PLAY_WORKSPACE_INCOMPLETE"
    with pytest.raises(PlayError):
        ensure_new_workspace(workspace)
