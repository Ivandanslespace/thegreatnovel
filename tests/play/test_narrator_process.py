from __future__ import annotations

import subprocess
import sys
import io
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

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.BytesIO(b'{"ok":true}')
            self.returncode = 0

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            self.returncode = -9

    def fake_popen(*args, **kwargs):
        seen["args"] = args
        seen.update(kwargs)
        seen["stdin_bytes"] = kwargs["stdin"].read()
        kwargs["stdin"].seek(0)
        return FakeProcess()

    monkeypatch.setattr(narrator_module.subprocess, "Popen", fake_popen)
    result = run_narrator(["python", "script.py", "argument;literal"], {"request": 1})
    assert result == {"ok": True}
    assert seen["args"] == (["python", "script.py", "argument;literal"],)
    assert seen["shell"] is False
    assert seen["stderr"] is subprocess.DEVNULL
    assert seen["stdout"] is subprocess.PIPE
    assert seen["stdin_bytes"] == canonical_document({"request": 1})


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


def test_run_narrator_accepts_exact_one_megabyte_and_discards_stderr(tmp_path: Path) -> None:
    script = tmp_path / "exact.py"
    script.write_text(
        "import sys\n"
        "payload = b'{\"x\":\"' + b'a' * (1024 * 1024 - 8) + b'\"}'\n"
        "sys.stderr.buffer.write(b'diagnostic' * 1000000)\n"
        "sys.stdout.buffer.write(payload)\n",
        encoding="utf-8",
    )
    result = run_narrator([sys.executable, str(script)], {"request": 1})
    assert len(result["x"]) == 1024 * 1024 - 8


def test_run_narrator_kills_unbounded_stdout(tmp_path: Path) -> None:
    script = tmp_path / "unbounded.py"
    script.write_text(
        "import sys\n"
        "while True:\n"
        "    sys.stdout.buffer.write(b'x' * 65536)\n"
        "    sys.stdout.flush()\n",
        encoding="utf-8",
    )
    with pytest.raises(PlayError) as error:
        run_narrator([sys.executable, str(script)], {"request": 1})
    assert error.value.code == "PLAY_NARRATOR_FAILED"


def test_run_narrator_reader_failure_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenStream:
        def read(self, _size):
            raise OSError("reader failure")

        def close(self):
            return None

    class FakeProcess:
        def __init__(self):
            self.stdout = BrokenStream()
            self.returncode = 0
            self.killed = False

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            self.killed = True

    process = FakeProcess()
    monkeypatch.setattr(narrator_module.subprocess, "Popen", lambda *_args, **_kwargs: process)
    with pytest.raises(PlayError) as error:
        run_narrator(["python"], {"request": 1})
    assert error.value.code == "PLAY_NARRATOR_FAILED"


@pytest.mark.parametrize("value", [None, True, "0", "601", "nan", "inf"])
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
