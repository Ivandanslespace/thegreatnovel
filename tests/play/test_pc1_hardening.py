from __future__ import annotations

import copy
import io
import json
import os
import shlex
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import tgn.play.common as common
import tgn.play.narrator_process as narrator_module
import tgn.play.service as service_module
from tgn.campaign import choose_campaign, next_campaign, stop_campaign
from tgn.play import PlayError, PlayService
from tgn.play.__main__ import main
from tgn.story import NarrationRequest, NarrationResponse, StoryError, init_story, prepare_story
from tgn.story.common import canonical_bytes

from .conftest import create_campaign_for_context


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _parse_powershell_argv(command: str) -> list[str]:
    assert command.startswith("& ")
    value = command[2:]
    result: list[str] = []
    index = 0
    while index < len(value):
        assert value[index] == "'"
        index += 1
        chars: list[str] = []
        while index < len(value):
            if value[index] != "'":
                chars.append(value[index])
                index += 1
                continue
            if index + 1 < len(value) and value[index + 1] == "'":
                chars.append("'")
                index += 2
                continue
            index += 1
            break
        result.append("".join(chars))
        if index < len(value):
            assert value[index] == " "
            index += 1
    return result


def _assert_dead(pid: int) -> None:
    # The production boundary waits for the owned group/job before returning;
    # assert the postcondition directly instead of polling with sleep.
    assert not _pid_alive(pid)


def _write_descendant_narrator(path: Path, pid_file: Path, *, writes_forever: bool) -> Path:
    child_source = (
        "import sys\n"
        "while True:\n"
        "    sys.stdout.buffer.write(b'x' * 65536)\n"
        "    sys.stdout.flush()\n"
    ) if writes_forever else "import time\ntime.sleep(30)\n"
    path.write_text(
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child_source!r}], stdout=sys.stdout, stderr=sys.stderr)\n"
        f"Path({str(pid_file)!r}).write_text(str(child.pid), encoding='ascii')\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("writes_forever", [False, True])
def test_real_descendant_process_is_contained_and_reader_is_bounded(tmp_path: Path, writes_forever: bool) -> None:
    script = _write_descendant_narrator(
        tmp_path / ("descendant-writer.py" if writes_forever else "descendant-holder.py"),
        tmp_path / "child.pid",
        writes_forever=writes_forever,
    )
    started = time.monotonic()
    with pytest.raises(PlayError) as error:
        service_module.run_narrator([sys.executable, str(script)], {"request": 1}, timeout=1)
    elapsed = time.monotonic() - started
    assert error.value.code == "PLAY_NARRATOR_FAILED"
    assert elapsed < 7.0
    child_pid = int((tmp_path / "child.pid").read_text(encoding="ascii"))
    _assert_dead(child_pid)
    assert not any(thread.name == "tgn-play-narrator-reader" for thread in threading.enumerate())


def test_process_containment_platform_error_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    class Function:
        def __init__(self, result):
            self.result = result
            self.argtypes = None
            self.restype = None

        def __call__(self, *_args):
            return self.result

    class Kernel:
        def __init__(self, *, create=100, set_info=1, assign=1, close=1):
            self.CreateJobObjectW = Function(create)
            self.SetInformationJobObject = Function(set_info)
            self.AssignProcessToJobObject = Function(assign)
            self.CloseHandle = Function(close)

    process = type("Process", (), {"pid": 123, "_handle": 456})()
    monkeypatch.setattr(narrator_module.os, "name", "posix")
    monkeypatch.setattr(narrator_module.signal, "SIGKILL", 9, raising=False)
    assert narrator_module._WindowsJob.for_process(process) is None
    killed: list[int] = []
    monkeypatch.setattr(narrator_module.os, "killpg", lambda group, _signal: killed.append(group), raising=False)
    narrator_module._ProcessContainment(process).stop_tree()
    assert killed == [123]
    monkeypatch.setattr(narrator_module.os, "killpg", lambda *_args: (_ for _ in ()).throw(ProcessLookupError()))
    narrator_module._ProcessContainment(process).stop_tree()
    fallback = type("Fallback", (), {"kill": lambda self: None})()
    narrator_module._ProcessContainment(fallback).stop_tree()
    failing_fallback = type("FailingFallback", (), {"kill": lambda self: (_ for _ in ()).throw(OSError())})()
    narrator_module._ProcessContainment(failing_fallback).stop_tree()

    monkeypatch.setattr(narrator_module.os, "name", "nt")
    monkeypatch.setattr(narrator_module.ctypes, "WinDLL", lambda *_args, **_kwargs: Kernel(), raising=False)
    with pytest.raises(OSError):
        narrator_module._WindowsJob.for_process(type("NoHandle", (), {"pid": 123, "_handle": 0})())
    job = narrator_module._WindowsJob.for_process(process)
    assert job is not None
    job.close()
    job.close()
    for kernel in (Kernel(create=0), Kernel(set_info=0), Kernel(assign=0)):
        monkeypatch.setattr(narrator_module.ctypes, "WinDLL", lambda *_args, kernel=kernel, **_kwargs: kernel, raising=False)
        with pytest.raises(OSError):
            narrator_module._WindowsJob.for_process(process)
    close_failure = Kernel(close=0)
    monkeypatch.setattr(narrator_module.ctypes, "WinDLL", lambda *_args, **_kwargs: close_failure, raising=False)
    close_job = narrator_module._WindowsJob.for_process(process)
    assert close_job is not None
    with pytest.raises(OSError):
        close_job.close()

    assert not narrator_module._bounded_close(type("CloseFail", (), {"close": lambda self: (_ for _ in ()).throw(OSError())})(), time.monotonic() + 1)


def test_run_narrator_posix_session_flag_and_containment_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class Process:
        def __init__(self):
            self.stdout = io.BytesIO(b'{"ok":true}')
            self.returncode = 0
            self.pid = 123

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            return None

    seen: dict[str, object] = {}
    process = Process()
    monkeypatch.setattr(narrator_module.os, "name", "posix")
    monkeypatch.setattr(narrator_module.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(narrator_module.subprocess, "Popen", lambda *args, **kwargs: (seen.update(kwargs) or process))
    assert narrator_module.run_narrator(["python"], {"ok": True}) == {"ok": True}
    assert seen["start_new_session"] is True

    monkeypatch.setattr(narrator_module.os, "name", "nt")
    monkeypatch.setattr(narrator_module, "_ProcessContainment", lambda _process: (_ for _ in ()).throw(OSError("containment")))
    with pytest.raises(PlayError):
        narrator_module.run_narrator(["python"], {"ok": True})


def test_cli_rejects_malformed_narrator_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["resume", "--workspace", "unused", "--narrator-exec", "python", "--narrator-arg", ""]) != 0
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_PLAY_INPUT"


def test_response_fifo_replacement_is_nonblocking_on_posix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    response = tmp_path / "response.json"
    response.write_bytes(b'{"ok":true}')
    if not hasattr(os, "mkfifo"):
        # Windows exercises the regular-file/reparse branch in the companion
        # tests; this assertion keeps the test non-skipped on the host.
        assert not hasattr(os, "O_NONBLOCK") or isinstance(getattr(os, "O_NONBLOCK"), int)
        return
    real_open = common.os.open
    replaced = False

    def replace_before_open(path, flags, *args, **kwargs):
        nonlocal replaced
        if Path(path) == response and not replaced:
            replaced = True
            response.unlink()
            os.mkfifo(response)
            assert flags & getattr(os, "O_NONBLOCK", 0)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(common.os, "open", replace_before_open)
    started = time.monotonic()
    with pytest.raises(PlayError) as error:
        common.read_external_json(response)
    assert time.monotonic() - started < 1.0
    assert error.value.code == "PLAY_NARRATOR_FAILED"


def test_response_ancestor_symlink_or_reparse_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "response.json").write_bytes(b'{"ok":true}')
    link = tmp_path / "outside-link"
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert completed.returncode == 0, completed.stderr or completed.stdout
        else:
            link.symlink_to(outside, target_is_directory=True)
        with pytest.raises(PlayError) as error:
            common.read_external_json(link / "response.json")
        assert error.value.code == "PLAY_NARRATOR_FAILED"
    finally:
        if link.exists() or link.is_symlink():
            if os.name == "nt":
                link.rmdir()
            else:
                link.unlink()


def test_terminal_safe_json_round_trips_controls_and_unicode() -> None:
    value = {"text": "ESC\x1b DEL\x7f C1\x80\x9b 中文 العربية\n"}
    rendered = common.terminal_safe_json(value)
    assert json.loads(rendered) == value
    assert all(not (ord(char) < 0x20 or ord(char) == 0x7F or 0x80 <= ord(char) <= 0x9F) for char in rendered)
    assert "\\u001b" in rendered and "\\u007f" in rendered and "\\u0080" in rendered


def test_manual_pending_prints_exact_argv_and_platform_quoting(tmp_path: Path) -> None:
    workspace_name = "space & 中文" if os.name == "nt" else "space & 'quote' \"double\" 中文"
    workspace = tmp_path / workspace_name
    workspace.mkdir()
    output: list[str] = []
    service_module.PlayService._manual_pending({"request": "中文"}, workspace, output.append)
    argv_line = next(item for item in output if item.startswith("Command argv JSON: "))
    argv = json.loads(argv_line.split(": ", 1)[1])
    assert argv[0] == sys.executable
    assert "--response-file <response.json>" not in "\n".join(output)
    response_path = Path(argv[-1])
    assert response_path.parent == workspace.parent
    assert response_path.parent != workspace
    label = "PowerShell command: " if os.name == "nt" else "POSIX shell command: "
    command_line = next(item for item in output if item.startswith(label)).split(": ", 1)[1]
    if os.name == "nt":
        assert _parse_powershell_argv(command_line) == argv
        synthetic = [sys.executable, "foo&bar", "foo^bar", "%TEMP%", "!value!", "(a)", "single'quote", "中文"]
        quoted = service_module._quote_argv(synthetic, platform_name="nt")
        assert _parse_powershell_argv(quoted) == synthetic
    else:
        assert shlex.split(command_line) == argv
        synthetic = [sys.executable, "a & b", "single'\"double", "中文"]
        assert shlex.split(service_module._quote_argv(synthetic, platform_name="posix")) == synthetic


def test_cli_real_control_character_response_preserves_story_and_export(tmp_path: Path, play_context, capsys: pytest.CaptureFixture[str]) -> None:
    context = play_context
    workspace = context["workspace"]
    campaign = create_campaign_for_context(context)
    story = workspace / "story"
    init_story(
        story,
        campaign_dir=campaign,
        story_id="story-001",
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    current = next_campaign(campaign)
    choice = current["canonical_request"]["choices"][1]
    choose_campaign(campaign, request_fingerprint=current["canonical_request"]["request_fingerprint"], choice_id=choice["choice_id"])
    request = prepare_story(story, campaign_dir=campaign)["request"]
    prose = "ESC\x1b DEL\x7f C1\x80\x9b 中文\n العربية"
    response_path = context["root"] / "control-response.json"
    response_path.write_bytes(
        canonical_bytes(
            {
                "schema_version": 1,
                "narration_request_id": request["narration_request_id"],
                "narration_request_hash": request["narration_request_hash"],
                "locale": request["narration_locale"],
                "claims": request["claim_requirements"],
                "prose": prose,
            }
        )
    )
    assert main(["narrate", "--workspace", str(workspace), "--response-file", str(response_path)]) == 0
    cli_output = capsys.readouterr().out
    assert "\x1b" not in cli_output and "\x7f" not in cli_output
    assert all(not (0x80 <= ord(char) <= 0x9F) for char in cli_output)
    final_value = json.loads(cli_output.splitlines()[-1])
    assert final_value["turn"]["prose"] == prose
    stored = json.loads((story / "turns" / "turn-000001.json").read_bytes())
    assert stored["prose"] == prose
    next_request = next_campaign(campaign)
    stop_campaign(campaign, request_fingerprint=next_request["canonical_request"]["request_fingerprint"])
    exported = PlayService(workspace).export(mode="final")
    assert exported["novel_status"] == "CURRENT_FINAL"
    novel = story / "novel.md"
    first = novel.read_bytes()
    assert prose.encode("utf-8") in first
    novel.unlink()
    PlayService(workspace).export(mode="final")
    assert novel.read_bytes() == first


def test_story_progress_iff_and_oldest_request_contract() -> None:
    from tests.play.test_validation_edges import _story_status

    valid = _story_status()
    valid["accepted_decisions"] = 1
    valid["session"]["accepted_decisions"] = 1
    valid["session"]["recorded_decision_count"] = 1
    valid["campaign_session"]["accepted_decisions"] = 1
    valid["campaign_session"]["recorded_decision_count"] = 1
    valid["recorded_decision_count"] = 1
    valid["missing_request_turn_ids"] = ["turn-000001"]
    valid["next_preparable_turn_id"] = "turn-000001"
    valid["missing_narration_work"] = True
    valid["export_readiness"]["current_snapshot_ready"] = False
    valid["phase_9c2_export_ready"] = False
    service_module._validate_story_status(valid)

    contradictory = dict(valid)
    contradictory["next_preparable_turn_id"] = None
    with pytest.raises(PlayError):
        service_module._validate_story_status(contradictory)


def test_public_request_and_turn_models_are_required_on_real_commit(play_context) -> None:
    context = play_context
    with pytest.raises(PlayError):
        PlayService(context["workspace"]).new(
            world_bundle_dir=context["world"],
            projection_bundle_dir=context["projection"],
            campaign_id="campaign-001",
            story_id="story-001",
            actor_id="player",
            max_decisions=1,
            locale="en",
            voice_id="cablecar_survival",
            input_fn=iter(["2"]).__next__,
            output_fn=lambda _value: None,
        )
    story = context["workspace"] / "story"
    campaign = context["workspace"] / "campaign"
    request = prepare_story(story, campaign_dir=campaign)["request"]
    assert request["turn_id"] == "turn-000001"


def test_response_file_observable_edges_and_unknown_identity_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    response = tmp_path / "response.json"
    response.write_bytes(b'{"ok":true}')
    for value in (True, 0, -1, 1.0):
        with pytest.raises(PlayError):
            common.read_external_json(response, max_bytes=value)  # type: ignore[arg-type]

    real_identity = common._file_identity
    monkeypatch.setattr(common, "_file_identity", lambda _stat: (0, 0))
    with pytest.raises(PlayError):
        common.read_external_json(response)
    monkeypatch.setattr(common, "_file_identity", real_identity)

    calls = {"count": 0}
    real_components = common._safe_component_snapshot

    def changed_components(path):
        calls["count"] += 1
        value = real_components(path)
        return value if calls["count"] == 1 else value + ((999, 999, stat.S_IFREG, 0),)

    monkeypatch.setattr(common, "_safe_component_snapshot", changed_components)
    with pytest.raises(PlayError):
        common.read_external_json(response)

    monkeypatch.setattr(common, "_safe_component_snapshot", real_components)
    real_same = common._same_file_observable
    checks = {"count": 0}

    def changed_final(left, right):
        checks["count"] += 1
        return checks["count"] < 3 and real_same(left, right)

    monkeypatch.setattr(common, "_same_file_observable", changed_final)
    with pytest.raises(PlayError):
        common.read_external_json(response)

    monkeypatch.setattr(common, "_same_file_observable", real_same)
    monkeypatch.setattr(common, "parse_json_document", lambda *_args, **_kwargs: (_ for _ in ()).throw(PlayError("PLAY_NARRATOR_FAILED", "parse")))
    with pytest.raises(PlayError):
        common.read_external_json(response)

    monkeypatch.setattr(common, "parse_json_document", common.parse_json_document)
    monkeypatch.setattr(common.os, "open", lambda *_args, **_kwargs: 123)
    monkeypatch.setattr(common.os, "fstat", lambda _fd: (_ for _ in ()).throw(OSError("fstat")))
    monkeypatch.setattr(common.os, "close", lambda _fd: (_ for _ in ()).throw(OSError("close")))
    with pytest.raises(PlayError):
        common.read_external_json(response)


def test_workspace_existing_and_child_reparse_boundaries(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert common.ensure_new_workspace(empty) == empty
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    child = workspace / "campaign"
    child.mkdir()
    story = workspace / "story"
    story.mkdir()
    link = workspace / "link"
    target = tmp_path / "target"
    target.mkdir()
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr or result.stdout
    else:
        link.symlink_to(target, target_is_directory=True)
    try:
        with pytest.raises(PlayError):
            common.require_workspace(workspace)
    finally:
        if link.exists() or link.is_symlink():
            link.rmdir() if os.name == "nt" else link.unlink()
    regular = tmp_path / "regular"
    regular.write_text("not a directory", encoding="utf-8")
    with pytest.raises(PlayError):
        common.require_workspace(regular)
    named_link_workspace = tmp_path / "named-link-workspace"
    named_link_workspace.mkdir()
    named_link_story = named_link_workspace / "story"
    named_link_story.mkdir()
    named_link_campaign = named_link_workspace / "campaign"
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(named_link_campaign), str(target)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr or result.stdout
    else:
        named_link_campaign.symlink_to(target, target_is_directory=True)
    try:
        with pytest.raises(PlayError):
            common.require_workspace(named_link_workspace)
    finally:
        if named_link_campaign.exists() or named_link_campaign.is_symlink():
            named_link_campaign.rmdir() if os.name == "nt" else named_link_campaign.unlink()


def test_public_composition_helpers_reject_malformed_request_response_and_turn(play_context) -> None:
    context = play_context
    workspace = context["workspace"]
    campaign = create_campaign_for_context(context)
    story = workspace / "story"
    init_story(story, campaign_dir=campaign, story_id="story-001", initial_narration_locale="en", initial_voice_id="cablecar_survival")
    current = next_campaign(campaign)
    choice = current["canonical_request"]["choices"][1]
    choose_campaign(campaign, request_fingerprint=current["canonical_request"]["request_fingerprint"], choice_id=choice["choice_id"])
    request = prepare_story(story, campaign_dir=campaign)["request"]
    request_model = NarrationRequest.from_dict(request)
    with pytest.raises(PlayError):
        service_module._request_model({})
    response_value = {
        "schema_version": 1,
        "narration_request_id": request["narration_request_id"],
        "narration_request_hash": request["narration_request_hash"],
        "locale": request["narration_locale"],
        "claims": request["claim_requirements"],
        "prose": "public",
    }
    response_model = service_module._response_model(response_value, request_model)
    for field, replacement in (
        ("narration_request_id", "other:turn-000001"),
        ("narration_request_hash", "f" * 64),
        ("locale", "ar"),
    ):
        invalid = copy.deepcopy(response_value)
        invalid[field] = replacement
        with pytest.raises(PlayError):
            service_module._response_model(invalid, request_model)

    response_path = context["root"] / "response.json"
    response_path.write_bytes(canonical_bytes(response_value))
    PlayService(workspace).narrate(response_file=response_path, output_fn=lambda _value: None)
    turn_path = story / "turns" / "turn-000001.json"
    turn = json.loads(turn_path.read_bytes())
    service_module._assert_turn_matches_request(turn, request_model, response_model)
    invalid_turn = copy.deepcopy(turn)
    invalid_turn["choice_id"] = "other"
    with pytest.raises(PlayError):
        service_module._assert_turn_matches_request(invalid_turn, request_model, response_model)
    invalid_output = copy.deepcopy(turn)
    invalid_output["claims"] = []
    with pytest.raises(PlayError):
        service_module._assert_turn_matches_request(invalid_output, request_model, response_model)
    with pytest.raises(PlayError):
        service_module._assert_turn_matches_request({}, request_model, response_model)


def test_commit_response_maps_all_public_boundary_failures(play_context, monkeypatch: pytest.MonkeyPatch) -> None:
    context = play_context
    workspace = context["workspace"]
    campaign = create_campaign_for_context(context)
    story = workspace / "story"
    init_story(story, campaign_dir=campaign, story_id="story-001", initial_narration_locale="en", initial_voice_id="cablecar_survival")
    current = next_campaign(campaign)
    choice = current["canonical_request"]["choices"][1]
    choose_campaign(campaign, request_fingerprint=current["canonical_request"]["request_fingerprint"], choice_id=choice["choice_id"])
    request = prepare_story(story, campaign_dir=campaign)["request"]
    response = {
        "schema_version": 1,
        "narration_request_id": request["narration_request_id"],
        "narration_request_hash": request["narration_request_hash"],
        "locale": request["narration_locale"],
        "claims": request["claim_requirements"],
        "prose": "public",
    }
    for replacement in (
        StoryError("NARRATION_RESPONSE_INVALID", "invalid"),
        RuntimeError("private"),
        {"ok": False},
        {"ok": True, "turn": None},
        {"ok": True, "turn": {}},
    ):
        if isinstance(replacement, BaseException):
            def failing(*_args, error=replacement, **_kwargs):
                raise error
            monkeypatch.setattr(service_module, "commit_story", failing)
        else:
            monkeypatch.setattr(service_module, "commit_story", lambda *_args, result=replacement, **_kwargs: result)
        with pytest.raises(PlayError):
            PlayService(workspace)._commit_response(campaign, story, response, output_fn=lambda _value: None)


def test_progress_and_composition_failures_are_rejected_before_engine_calls() -> None:
    from tests.play.test_validation_edges import _campaign_manifest, _session, _story_status

    session = _session()
    for mutation in (
        {**session, "status": "BROKEN"},
        {**session, "stop_reason": "wrong"},
        {**session, "accepted_decisions": 21},
    ):
        with pytest.raises(PlayError):
            service_module._validate_session_summary(mutation)
    with pytest.raises(PlayError):
        service_module._strict_turn_id("turn-" + "1" * 1001)
    assert service_module._strict_turn_id("turn-000001") == "turn-000001"
    with pytest.raises(PlayError):
        service_module._validate_request_pair(None)  # type: ignore[arg-type]
    with pytest.raises(PlayError):
        service_module._validate_path("bad\x00path", "path")

    campaign = _campaign_manifest()
    story = _story_status()
    campaign_value = {"ok": True, "campaign": campaign, "session": _session(), "canonical_request": None, "player_presentation": None}
    actor_mismatch = copy.deepcopy(campaign_value)
    actor_mismatch["campaign"]["actor_id"] = "other"
    with pytest.raises(PlayError):
        service_module._cross_check(actor_mismatch, story)
    max_mismatch = copy.deepcopy(campaign_value)
    max_mismatch["campaign"]["max_decisions"] = 21
    with pytest.raises(PlayError):
        service_module._cross_check(max_mismatch, story)
    shared_mismatch = copy.deepcopy(story)
    shared_mismatch["campaign_session"]["actor_id"] = "other"
    shared_mismatch["session"]["actor_id"] = "other"
    with pytest.raises(PlayError):
        service_module._cross_check(campaign_value, shared_mismatch)

    backlog = _story_status()
    backlog["accepted_decisions"] = 1
    backlog["session"]["accepted_decisions"] = 1
    backlog["session"]["recorded_decision_count"] = 1
    backlog["campaign_session"]["accepted_decisions"] = 1
    backlog["campaign_session"]["recorded_decision_count"] = 1
    backlog["recorded_decision_count"] = 1
    backlog["request_count"] = 1
    backlog["committed_turn_count"] = 0
    backlog["committed_prefix"] = 0
    backlog["missing_request_turn_ids"] = []
    backlog["missing_narration_work"] = False
    backlog["next_preparable_turn_id"] = None
    backlog["export_readiness"]["current_snapshot_ready"] = False
    backlog["phase_9c2_export_ready"] = False
    with pytest.raises(PlayError):
        service_module._validate_story_status(backlog)

    pending_bad = copy.deepcopy(backlog)
    pending_bad["request_count"] = 2
    pending_bad["pending_turn_id"] = "turn-000002"
    pending_bad["missing_request_turn_ids"] = []
    with pytest.raises(PlayError):
        service_module._validate_story_status(pending_bad)

    final_bad = _story_status()
    final_bad["novel_status"] = "CURRENT_FINAL"
    with pytest.raises(PlayError):
        service_module._validate_story_status(final_bad)
    snapshot_bad = _story_status()
    snapshot_bad["accepted_decisions"] = 1
    snapshot_bad["session"]["accepted_decisions"] = 1
    snapshot_bad["session"]["recorded_decision_count"] = 1
    snapshot_bad["campaign_session"]["accepted_decisions"] = 1
    snapshot_bad["campaign_session"]["recorded_decision_count"] = 1
    snapshot_bad["recorded_decision_count"] = 1
    snapshot_bad["missing_request_turn_ids"] = ["turn-000001"]
    snapshot_bad["next_preparable_turn_id"] = "turn-000001"
    snapshot_bad["missing_narration_work"] = True
    snapshot_bad["export_readiness"]["current_snapshot_ready"] = False
    snapshot_bad["phase_9c2_export_ready"] = False
    snapshot_bad["novel_status"] = "CURRENT_SNAPSHOT"
    with pytest.raises(PlayError):
        service_module._validate_story_status(snapshot_bad)


def test_status_and_verify_never_accept_incomplete_composition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.play.test_validation_edges import _campaign_manifest, _session, _story_status

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    campaign_dir = workspace / "campaign"
    story_dir = workspace / "story"
    campaign_dir.mkdir()
    story_dir.mkdir()
    facade = PlayService(workspace)
    monkeypatch.setattr(facade, "_layout", lambda **_kwargs: (campaign_dir, story_dir))
    with pytest.raises(PlayError):
        facade.status()
    with pytest.raises(PlayError):
        facade.verify()

    campaign_result = {
        "ok": True,
        "campaign": _campaign_manifest(),
        "session": _session(),
        "canonical_request": None,
        "player_presentation": None,
        "verification": {"valid": True},
    }
    story_result = _story_status()
    story_result["valid"] = False
    story_result["verification"] = {"valid": True, "read_only": True}
    monkeypatch.setattr(facade, "_call_campaign", lambda *_args, **_kwargs: campaign_result)
    monkeypatch.setattr(facade, "_call_story", lambda *_args, **_kwargs: story_result)
    with pytest.raises(PlayError):
        facade._verify_pair(campaign_dir, story_dir)
    story_result["valid"] = True
    story_result["verification"] = {"valid": True, "read_only": False}
    with pytest.raises(PlayError):
        facade._verify_pair(campaign_dir, story_dir)

    story_result["verification"] = {"valid": True, "read_only": True}
    status_value = copy.deepcopy(campaign_result)
    current_value = copy.deepcopy(campaign_result)
    status_value["campaign"]["actor_id"] = "other"
    def campaign_call(_function, *_args, operation, **_kwargs):
        return status_value if operation == "status" else current_value
    monkeypatch.setattr(facade, "_call_campaign", campaign_call)
    with pytest.raises(PlayError):
        facade._read_status_pair(campaign_dir, story_dir)
    status_value = copy.deepcopy(campaign_result)
    status_value["session"]["actor_id"] = "other"
    with pytest.raises(PlayError):
        facade._read_status_pair(campaign_dir, story_dir)
