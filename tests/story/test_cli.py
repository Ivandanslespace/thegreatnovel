from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pytest

import tgn.story.__main__ as cli
from tgn.story import StoryError, init_story, prepare_story
from tgn.story.common import canonical_bytes

from .conftest import response_for
from .test_service import _choose


def test_cli_prepare_commit_stdin_and_error_envelope(story_factory, capsys, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    campaign, story, config = story_factory()
    assert cli.main(["init", "--story-dir", str(story), "--campaign-dir", str(campaign), "--story-id", config["story_id"], "--locale", "en", "--voice-id", "cablecar_survival"]) == 0
    capsys.readouterr()
    _choose(campaign, "DROP")
    assert cli.main(["prepare", "--story-dir", str(story), "--campaign-dir", str(campaign), "--locale", "en"]) == 0
    request = json.loads(capsys.readouterr().out)["request"]
    response = canonical_bytes(response_for(request))

    class FakeStdin:
        buffer = io.BytesIO(response)

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())
    assert cli.main(["commit", "--story-dir", str(story), "--campaign-dir", str(campaign), "--response-file", "-"]) == 0
    assert json.loads(capsys.readouterr().out)["result"] == "committed"

    assert cli.main(["commit", "--story-dir", str(story), "--campaign-dir", str(campaign), "--response-file", str(tmp_path / "missing.json")]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "NARRATION_RESPONSE_INVALID"
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{ "not": "canonical" }', encoding="utf-8")
    assert cli.main(["commit", "--story-dir", str(story), "--campaign-dir", str(campaign), "--response-file", str(invalid)]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "NARRATION_RESPONSE_INVALID"

    assert cli.main(["status", "--story-dir", str(story)]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_STORY_INPUT"


def test_cli_dispatch_and_unexpected_error_mapping(story_factory, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    arguments = argparse.Namespace(command="status", story_dir=str(story), campaign_dir=str(campaign))
    assert cli.dispatch(arguments)["ok"] is True
    with pytest.raises(StoryError):
        cli.dispatch(argparse.Namespace(command="unknown"))
    monkeypatch.setattr(cli, "dispatch", lambda *_args: (_ for _ in ()).throw(RuntimeError("secret traceback")))
    assert cli.main(["status", "--story-dir", str(story), "--campaign-dir", str(campaign)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output == {"error": {"code": "STORY_INTEGRITY_MISMATCH", "message": "Story operation failed"}, "ok": False}


@pytest.mark.parametrize("raw", ["+1", "-1", "01", " 1", "1 ", "1.0", "true", "False", ""])
def test_cli_export_rejects_noncanonical_accepted_decisions_before_mutation(
    story_factory,
    raw: str,
    capsys,
) -> None:
    campaign, story, config = story_factory(name=f"cli-invalid-count-{len(raw)}")
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    assert cli.main(
        [
            "export",
            "--story-dir",
            str(story),
            "--campaign-dir",
            str(campaign),
            "--mode",
            "snapshot",
            "--accepted-decisions",
            raw,
        ]
    ) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["error"]["code"] == "INVALID_STORY_INPUT"
    assert not (story / "novel.md").exists()
