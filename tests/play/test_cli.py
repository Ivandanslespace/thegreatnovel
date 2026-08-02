from __future__ import annotations

import json
from pathlib import Path

import pytest

from tgn.play.__main__ import dispatch, main
from tgn.play.common import PlayError


@pytest.mark.parametrize("raw", ["+1", "-1", "01", " 1", "1 ", "1.0", "true", "False", ""])
def test_cli_rejects_noncanonical_accepted_decisions_before_workspace_mutation(
    raw: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "export",
            "--workspace",
            str(tmp_path / "not-created"),
            "--mode",
            "snapshot",
            "--accepted-decisions",
            raw,
        ]
    )
    assert exit_code != 0
    value = json.loads(capsys.readouterr().out)
    assert value["error"]["code"] == "INVALID_PLAY_INPUT"
    assert not (tmp_path / "not-created").exists()


def test_cli_help_contains_only_pc1_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "new" in output and "resume" in output and "narrate" in output
    assert "status" in output and "verify" in output and "export" in output


def test_cli_status_maps_incomplete_workspace_safely(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status", "--workspace", str(tmp_path / "missing")]) != 0
    value = json.loads(capsys.readouterr().out)
    assert value == {"error": {"code": "PLAY_WORKSPACE_INCOMPLETE", "message": "workspace is incomplete"}, "ok": False}


def test_dispatch_rejects_narrator_args_without_executable(tmp_path: Path) -> None:
    with pytest.raises(PlayError) as error:
        dispatch(
            type(
                "Arguments",
                (),
                {
                    "workspace": str(tmp_path),
                    "command": "resume",
                    "locale": None,
                    "story_id": None,
                    "voice_id": "cablecar_survival",
                    "narrator_exec": None,
                    "narrator_arg": ["unexpected"],
                    "narrator_timeout": "120",
                },
            )()
        )
    assert error.value.code == "INVALID_PLAY_INPUT"
