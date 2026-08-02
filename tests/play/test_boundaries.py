from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import tgn.play.__main__ as cli
import tgn.play.service as service_module
from tgn.campaign import CampaignError
from tgn.story import StoryError
from tgn.play import PlayError, PlayService
from tgn.play.common import (
    MAX_NARRATOR_STDOUT,
    canonical_document,
    ensure_new_workspace,
    lexical_absolute,
    parse_json_document,
    parse_nonnegative_integer,
    parse_positive_integer,
    read_external_json,
    require_workspace,
    validate_json_value,
)

from .conftest import create_campaign_for_context


def test_common_boundary_helpers_cover_strict_values_and_safe_errors(tmp_path: Path) -> None:
    error = PlayError("not-a-play-code", "line\r\nmessage", cause_code="cause\ncode")
    assert error.code == "PLAY_STORY_FAILED"
    assert error.to_dict() == {
        "code": "PLAY_STORY_FAILED",
        "message": "line  message",
        "cause_code": "cause code",
    }
    assert PlayError("PLAY_NARRATION_PENDING", "pending").exit_code == 3
    assert canonical_document((1, True, "中文")) == '[1,true,"中文"]'.encode("utf-8")
    validate_json_value(1.5)
    for value in (float("nan"), float("inf"), "\ud800", {1: "bad"}, {"x": object()}):
        with pytest.raises((ValueError, TypeError)):
            validate_json_value(value)
    with pytest.raises(TypeError):
        parse_json_document("not bytes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parse_json_document(b"{}", max_bytes=1)
    with pytest.raises(ValueError):
        parse_json_document(b"{\"a\":Infinity}")
    with pytest.raises(PlayError):
        lexical_absolute(object())  # type: ignore[arg-type]
    for parser, value in (
        (parse_positive_integer, "0"),
        (parse_positive_integer, "a" * 5000),
        (parse_nonnegative_integer, "0" * 2),
        (parse_nonnegative_integer, "9" * 5000),
    ):
        with pytest.raises(PlayError):
            parser(value, "number")
    with pytest.raises(PlayError) as dash_error:
        read_external_json("-")
    assert dash_error.value.code == "INVALID_PLAY_INPUT"
    response_dir = tmp_path / "response-dir"
    response_dir.mkdir()
    with pytest.raises(PlayError):
        read_external_json(response_dir)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * (MAX_NARRATOR_STDOUT + 1))
    with pytest.raises(PlayError):
        read_external_json(oversized)


def test_workspace_boundaries_cover_missing_file_and_nonempty_cases(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(PlayError):
        require_workspace(missing)
    regular = tmp_path / "regular"
    regular.write_text("not a workspace", encoding="utf-8")
    with pytest.raises(PlayError):
        ensure_new_workspace(regular)
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "unexpected").write_text("x", encoding="utf-8")
    with pytest.raises(PlayError):
        ensure_new_workspace(nonempty)


def test_narrator_process_failure_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    from tgn.play import narrator_process

    for argv in ([], [""], [1]):
        with pytest.raises(PlayError) as error:
            narrator_process.run_narrator(argv, {})  # type: ignore[arg-type]
        assert error.value.code == "INVALID_PLAY_INPUT"
    with pytest.raises(PlayError):
        narrator_process.validate_timeout("not-a-number")

    def raise_os_error(*_args, **_kwargs):
        raise OSError("not exposed")

    monkeypatch.setattr(narrator_process.subprocess, "run", raise_os_error)
    with pytest.raises(PlayError) as error:
        narrator_process.run_narrator(["python"], {})
    assert error.value.code == "PLAY_NARRATOR_FAILED"
    assert "could not be started" in error.value.message

    def raise_value_error(*_args, **_kwargs):
        raise ValueError("not exposed")

    monkeypatch.setattr(narrator_process.subprocess, "run", raise_value_error)
    with pytest.raises(PlayError):
        narrator_process.run_narrator(["python"], {})

    monkeypatch.setattr(
        narrator_process.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=b"[]", stderr=b""),
    )
    with pytest.raises(PlayError) as error:
        narrator_process.run_narrator(["python"], {})
    assert "JSON object" in error.value.message


def test_cli_dispatches_all_pc1_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeService:
        def __init__(self, workspace: str) -> None:
            calls.append(("init", {"workspace": workspace}))

        def new(self, **kwargs):
            calls.append(("new", kwargs))
            return {"ok": True, "command": "new"}

        def resume(self, **kwargs):
            calls.append(("resume", kwargs))
            return {"ok": True, "command": "resume"}

        def narrate(self, **kwargs):
            calls.append(("narrate", kwargs))
            return {"ok": True, "command": "narrate"}

        def status(self):
            calls.append(("status", {}))
            return {"ok": True, "command": "status"}

        def verify(self):
            calls.append(("verify", {}))
            return {"ok": True, "command": "verify"}

        def export(self, **kwargs):
            calls.append(("export", kwargs))
            return {"ok": True, "command": "export"}

    monkeypatch.setattr(cli, "PlayService", FakeService)
    parser = cli.build_parser()
    commands = [
        [
            "new",
            "--workspace",
            str(tmp_path),
            "--world-bundle-dir",
            "world",
            "--projection-bundle-dir",
            "projection",
            "--campaign-id",
            "campaign",
            "--story-id",
            "story",
            "--actor-id",
            "player",
            "--max-decisions",
            "3",
            "--locale",
            "en",
            "--voice-id",
            "voice",
            "--narrator-exec",
            "python",
            "--narrator-arg",
            "script.py",
            "--narrator-timeout",
            "5",
        ],
        ["resume", "--workspace", str(tmp_path), "--locale", "ar"],
        ["narrate", "--workspace", str(tmp_path), "--response-file", "response.json"],
        ["status", "--workspace", str(tmp_path)],
        ["verify", "--workspace", str(tmp_path)],
        ["export", "--workspace", str(tmp_path), "--mode", "snapshot", "--accepted-decisions", "0"],
    ]
    for argv in commands:
        result = cli.dispatch(parser.parse_args(argv), input_fn=lambda: "", output_fn=lambda _value: None)
        assert result["ok"] is True
    assert {name for name, _kwargs in calls} == {"init", "new", "resume", "narrate", "status", "verify", "export"}
    new_call = next(kwargs for name, kwargs in calls if name == "new")
    assert new_call["narrator_argv"] == ["python", "script.py"]
    assert new_call["max_decisions"] == 3


def test_cli_main_success_play_error_and_unexpected_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    original_dispatch = cli.dispatch
    monkeypatch.setattr(cli, "dispatch", lambda _arguments: {"ok": True, "result": "done"})
    assert cli.main(["status", "--workspace", "unused"]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "result": "done"}

    def raise_play_error(_arguments):
        raise PlayError("INVALID_PLAY_INPUT", "bad\ninput")

    monkeypatch.setattr(cli, "dispatch", raise_play_error)
    assert cli.main(["status", "--workspace", "unused"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_PLAY_INPUT"

    monkeypatch.setattr(cli, "dispatch", lambda _arguments: (_ for _ in ()).throw(RuntimeError("secret")))
    assert cli.main(["status", "--workspace", "unused"]) == 2
    value = json.loads(capsys.readouterr().out)
    assert value == {"ok": False, "error": {"code": "PLAY_STORY_FAILED", "message": "Playable Client boundary failed"}}
    monkeypatch.setattr(cli, "dispatch", original_dispatch)
    with pytest.raises(PlayError):
        cli.dispatch(SimpleNamespace(workspace="unused", command="unknown"))


def test_cli_parser_and_narrator_argument_edges(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["status"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_PLAY_INPUT"
    arguments = SimpleNamespace(narrator_timeout="1", narrator_exec="", narrator_arg=[])
    with pytest.raises(PlayError):
        cli._narrator_argv(arguments)

    def reject_timeout(_value):
        raise PlayError("INVALID_PLAY_INPUT", "invalid timeout")

    monkeypatch.setattr(cli, "validate_timeout", reject_timeout)
    with pytest.raises(PlayError):
        cli._narrator_argv(SimpleNamespace(narrator_timeout="1", narrator_exec=None, narrator_arg=[]))


def _valid_pair() -> dict[str, object]:
    choice = {
        "choice_id": "choice-1",
        "action_type": "WAIT",
        "params": {},
        "duration_minutes": None,
        "stamina_cost": 0,
    }
    return {
        "canonical_request": {"request_fingerprint": "fp", "choices": [choice]},
        "player_presentation": {"request_fingerprint": "fp", "choices": [dict(choice)]},
    }


def test_service_boundary_helpers_and_error_mapping(tmp_path: Path) -> None:
    assert service_module._map_boundary_error(PlayError("INVALID_PLAY_INPUT", "x"), operation="x").code == "INVALID_PLAY_INPUT"
    campaign_error = service_module._map_boundary_error(CampaignError("UNKNOWN_CHOICE", "bad"), operation="choice")
    assert campaign_error.code == "PLAY_CAMPAIGN_FAILED" and campaign_error.cause_code == "UNKNOWN_CHOICE"
    story_error = service_module._map_boundary_error(StoryError("STORY_INCOMPLETE", "bad"), operation="status")
    assert story_error.code == "PLAY_STORY_FAILED" and story_error.cause_code == "STORY_INCOMPLETE"
    assert service_module._map_boundary_error(RuntimeError("secret"), operation="status").code == "PLAY_STORY_FAILED"
    assert service_module._present_directory(tmp_path) is True
    assert service_module._present_directory(tmp_path / "missing") is False
    regular = tmp_path / "regular"
    regular.write_text("x", encoding="utf-8")
    assert service_module._present_directory(regular) is False
    assert service_module._validate_request_pair({}) == (None, None)
    assert service_module._validate_request_pair(_valid_pair())[0]["request_fingerprint"] == "fp"  # type: ignore[index]
    invalid_values = [
        {"canonical_request": {}},
        {"canonical_request": "bad", "player_presentation": {}},
        {"canonical_request": {"request_fingerprint": "a", "choices": []}, "player_presentation": {"request_fingerprint": "b", "choices": []}},
        {"canonical_request": {"request_fingerprint": "a", "choices": {}}, "player_presentation": {"request_fingerprint": "a", "choices": {}}},
        {"canonical_request": {"request_fingerprint": "a", "choices": [1]}, "player_presentation": {"request_fingerprint": "a", "choices": [1]}},
        {"canonical_request": {"request_fingerprint": "a", "choices": [{"choice_id": "a"}]}, "player_presentation": {"request_fingerprint": "a", "choices": [{"choice_id": "b"}]}},
    ]
    for value in invalid_values:
        with pytest.raises(PlayError):
            service_module._validate_request_pair(value)  # type: ignore[arg-type]
    rendered: list[str] = []
    service_module._render_presentation({"choices": [{"action_type": "WAIT", "display_params": {"x": 1}}]}, rendered.append)
    assert any("WAIT" in line for line in rendered)
    with pytest.raises(PlayError):
        PlayService(object())  # type: ignore[arg-type]


def test_service_call_and_status_guards(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def bad_result(*_args, **_kwargs):
        return None

    with pytest.raises(PlayError):
        PlayService._call_campaign(bad_result, operation="bad")
    with pytest.raises(PlayError):
        PlayService._call_story(bad_result, operation="bad")

    def raises_campaign(*_args, **_kwargs):
        raise CampaignError("UNKNOWN_CHOICE", "bad")

    def raises_story(*_args, **_kwargs):
        raise StoryError("STORY_INCOMPLETE", "bad")

    with pytest.raises(PlayError):
        PlayService._call_campaign(raises_campaign, operation="bad")
    with pytest.raises(PlayError):
        PlayService._call_story(raises_story, operation="bad")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = PlayService(workspace)
    with pytest.raises(PlayError) as error:
        service.status()
    assert error.value.code == "PLAY_WORKSPACE_INCOMPLETE"
    with pytest.raises(PlayError):
        service.export(mode="final")
    with pytest.raises(PlayError):
        service._verify_pair(workspace / "campaign", workspace / "story")
    with pytest.raises(PlayError):
        service._compose_status({}, {})
    with pytest.raises(PlayError):
        service._compose_status({"session": {}}, {"export_readiness": []})


def test_service_input_and_resume_guards(play_context) -> None:
    context = play_context
    service = PlayService(context["workspace"])
    with pytest.raises(PlayError):
        service.new(
            world_bundle_dir=context["world"], projection_bundle_dir=context["projection"], campaign_id="c",
            story_id="s", actor_id="p", max_decisions=1, locale="xx", voice_id="v",
        )
    with pytest.raises(PlayError):
        service.new(
            world_bundle_dir=context["world"], projection_bundle_dir=context["projection"], campaign_id="c",
            story_id="s", actor_id="p", max_decisions=True, locale="en", voice_id="v",
        )
    with pytest.raises(PlayError):
        service.resume(locale="xx")
    with pytest.raises(PlayError):
        service.resume()
    context["workspace"].mkdir(parents=True, exist_ok=True)
    with pytest.raises(PlayError) as no_campaign:
        service.resume()
    assert no_campaign.value.code == "PLAY_WORKSPACE_INCOMPLETE"
    campaign = create_campaign_for_context(context)
    with pytest.raises(PlayError) as no_story_identity:
        service.resume()
    assert no_story_identity.value.code == "PLAY_WORKSPACE_INCOMPLETE"
    assert campaign.is_dir()


def test_service_revalidation_and_loop_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with pytest.raises(PlayError):
        service_module._validate_request_pair(
            {"canonical_request": {"request_fingerprint": "fp", "choices": []}, "player_presentation": {"request_fingerprint": "fp", "choices": [1]}}
        )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "campaign").mkdir()
    (workspace / "story").mkdir()
    service = PlayService(workspace)
    monkeypatch.setattr(service, "_verify_pair", lambda *_args: ({}, {}))

    def pending_call(function, *_args, operation, **_kwargs):
        if operation == "pending status":
            return {"ok": True, "pending_turn_id": "turn-000001"}
        return {"ok": True, "request": None}

    monkeypatch.setattr(service, "_call_story", pending_call)
    response_path = tmp_path / "response.json"
    response_path.write_bytes(b"[]")
    with pytest.raises(PlayError) as pending_error:
        service.narrate(response_file=response_path, output_fn=lambda _value: None)
    assert pending_error.value.code == "PLAY_NARRATION_PENDING"

    monkeypatch.setattr(service, "_call_story", lambda function, *_args, operation, **_kwargs: {"ok": True, "pending_turn_id": "turn-000001", "request": {}} if operation == "pending status" else {"ok": True, "request": None})
    with pytest.raises(PlayError):
        service.narrate(response_file=response_path, output_fn=lambda _value: None)

    monkeypatch.setattr(service_module, "commit_story", lambda *_args, **_kwargs: {"ok": True, "turn": {}})
    with pytest.raises(PlayError) as malformed_turn:
        service._commit_response(workspace / "campaign", workspace / "story", {}, output_fn=lambda _value: None)
    assert malformed_turn.value.code == "PLAY_CLIENT_INTEGRITY_MISMATCH"

    monkeypatch.setattr(service, "_complete_pending", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(service, "_call_campaign", lambda function, *_args, operation, **_kwargs: {"ok": True, "canonical_request": None, "player_presentation": None, "session": {}})
    monkeypatch.setattr(service, "_call_story", lambda *_args, **_kwargs: {"ok": True, "export_readiness": {"final_ready": False}})
    terminal = service._loop(workspace / "campaign", workspace / "story", locale=None, narrator_argv=None, narrator_timeout=1, input_fn=input, output_fn=lambda _value: None)
    assert terminal["terminal"] is True

    pair = _valid_pair()
    monkeypatch.setattr(service, "_call_campaign", lambda function, *_args, operation, **_kwargs: {"ok": True, **pair})
    with pytest.raises(PlayError) as type_error:
        service._loop(workspace / "campaign", workspace / "story", locale=None, narrator_argv=None, narrator_timeout=1, input_fn=lambda: 1, output_fn=lambda _value: None)
    assert type_error.value.code == "INVALID_PLAY_INPUT"

    values = iter(["99"])

    def bad_option():
        try:
            return next(values)
        except StopIteration as exc:
            raise EOFError from exc

    with pytest.raises(PlayError) as option_error:
        service._loop(workspace / "campaign", workspace / "story", locale=None, narrator_argv=None, narrator_timeout=1, input_fn=bad_option, output_fn=lambda _value: None)
    assert option_error.value.code == "INVALID_PLAY_INPUT"

    invalid_choice = _valid_pair()
    invalid_choice["canonical_request"]["choices"] = [{"action_type": "WAIT", "params": {}, "duration_minutes": None, "stamina_cost": 0}]  # type: ignore[index]
    invalid_choice["player_presentation"]["choices"] = [{"action_type": "WAIT", "params": {}, "duration_minutes": None, "stamina_cost": 0}]  # type: ignore[index]
    monkeypatch.setattr(service, "_call_campaign", lambda function, *_args, operation, **_kwargs: {"ok": True, **invalid_choice})
    with pytest.raises(PlayError) as choice_error:
        service._loop(workspace / "campaign", workspace / "story", locale=None, narrator_argv=None, narrator_timeout=1, input_fn=lambda: "1", output_fn=lambda _value: None)
    assert choice_error.value.code == "PLAY_CLIENT_INTEGRITY_MISMATCH"


def test_new_preserves_campaign_when_story_initialization_fails(monkeypatch: pytest.MonkeyPatch, play_context) -> None:
    context = play_context
    monkeypatch.setattr(service_module, "create_campaign", lambda *_args, **_kwargs: {"ok": True})

    def fail_story(*_args, **_kwargs):
        raise StoryError("STORY_PUBLICATION_UNAVAILABLE", "failed")

    monkeypatch.setattr(service_module, "init_story", fail_story)
    with pytest.raises(PlayError) as error:
        PlayService(context["workspace"]).new(
            world_bundle_dir=context["world"], projection_bundle_dir=context["projection"], campaign_id="c",
            story_id="s", actor_id="p", max_decisions=1, locale="en", voice_id="v",
        )
    assert error.value.code == "PLAY_STORY_FAILED"
