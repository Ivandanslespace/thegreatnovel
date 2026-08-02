from __future__ import annotations

import ctypes
import dataclasses
import json
import os
from pathlib import Path

import pytest
import tgn.story.publication as publication_module
import tgn.story.service as service_module

from tgn.campaign import choose_campaign, next_campaign, stop_campaign
from tgn.story import (
    StoryError,
    commit_story,
    export_story,
    init_story,
    prepare_story,
    status_story,
    verify_story,
)
from tgn.story.campaign_snapshot import capture_campaign_snapshot
from tgn.story.common import canonical_bytes
from tgn.story.novel import build_novel, parse_novel_header
from tgn.story.publication import (
    BoundPublicationDirectory,
    PublicationBoundaryChanged,
    PublicationConflict,
    PublicationRuntime,
    PublicationUnavailable,
    replace_bytes_atomic,
)
from tgn.story.reconstruction import reconstruct_campaign
from tgn.story.verification import load_story_view
import tgn.story.verification as verification_module
from tgn.story.verification import StoryDirectoryObservable

from .conftest import response_for
from .test_service import _choose
from .test_publication import _fake_posix_dirfd_runtime


def _choose_first(campaign: Path) -> dict:
    current = next_campaign(campaign)
    choice = next(
        item
        for item in current["canonical_request"]["choices"]
        if item["action_type"] != "WAIT"
    )
    return choose_campaign(
        campaign,
        request_fingerprint=current["canonical_request"]["request_fingerprint"],
        choice_id=choice["choice_id"],
    )


def test_locale_switch_preserves_engine_observables_and_commits(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    _choose(campaign, "DROP")
    first = prepare_story(story, campaign_dir=campaign, narration_locale="ar")["request"]
    view = load_story_view(story)
    snapshot = capture_campaign_snapshot(campaign)
    english = reconstruct_campaign(view.manifest, snapshot, {1: "en"}).action_turns[0].request
    arabic = reconstruct_campaign(view.manifest, snapshot, {1: "ar"}).action_turns[0].request
    assert english.narration_request_id == arabic.narration_request_id == first["narration_request_id"]
    assert english.source_request_hash == arabic.source_request_hash
    assert english.public_brief == arabic.public_brief
    assert english.claim_requirements == arabic.claim_requirements
    assert english.narration_request_hash != arabic.narration_request_hash

    commit_story(story, campaign_dir=campaign, response=response_for(first))
    _choose(campaign, "EXTRACT")
    second = prepare_story(story, campaign_dir=campaign, narration_locale="ar")["request"]
    assert second["narration_locale"] == "ar"
    assert second["narration_request_id"] == "story-001:turn-000002"
    committed = commit_story(story, campaign_dir=campaign, response=response_for(second))
    assert committed["result"] == "committed"

    _choose_first(campaign)
    third = prepare_story(story, campaign_dir=campaign)["request"]
    assert third["narration_locale"] == "ar"
    assert status_story(story, campaign_dir=campaign)["committed_prefix"] == 2


def test_snapshot_export_is_deterministic_and_historical(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="zh-CN",
        initial_voice_id="cablecar_survival",
    )
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    commit_story(story, campaign_dir=campaign, response=response_for(request))

    exported = export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=1)
    first_bytes = (story / "novel.md").read_bytes()
    assert exported["novel_status"] == "CURRENT_SNAPSHOT"
    assert exported["novel_sha256"]
    assert first_bytes.endswith(b"\n") and b"\r" not in first_bytes
    assert status_story(story, campaign_dir=campaign)["novel_status"] == "CURRENT_SNAPSHOT"
    assert verify_story(story, campaign_dir=campaign)["verification"]["novel_status"] == "CURRENT_SNAPSHOT"

    repeated = export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=1)
    assert repeated["novel_sha256"] == exported["novel_sha256"]
    assert (story / "novel.md").read_bytes() == first_bytes

    _choose(campaign, "EXTRACT")
    assert status_story(story, campaign_dir=campaign)["novel_status"] == "HISTORICAL_SNAPSHOT"
    assert verify_story(story, campaign_dir=campaign)["valid"] is True

    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=2)
    assert error.value.code == "STORY_INCOMPLETE"

    (story / "novel.md").unlink()
    rebuilt = export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=1)
    assert rebuilt["novel_sha256"] == exported["novel_sha256"]
    assert (story / "novel.md").read_bytes() == first_bytes


def test_final_export_requires_terminal_and_records_stop_reason(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="final")
    assert error.value.code == "STORY_INCOMPLETE"

    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    commit_story(story, campaign_dir=campaign, response=response_for(request))
    current = next_campaign(campaign)["canonical_request"]
    stop_campaign(campaign, request_fingerprint=current["request_fingerprint"])

    exported = export_story(story, campaign_dir=campaign, mode="final")
    assert exported["novel_status"] == "CURRENT_FINAL"
    content = (story / "novel.md").read_text(encoding="utf-8")
    assert "## terminal\nstop_reason: EXPLICIT_STOP\n" in content
    status = status_story(story, campaign_dir=campaign)
    assert status["novel_status"] == "CURRENT_FINAL"
    assert status["export_readiness"]["final_ready"] is True
    assert verify_story(story, campaign_dir=campaign)["valid"] is True


def test_novel_tamper_and_special_format_fail_closed(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=0)
    novel = story / "novel.md"
    original = novel.read_bytes()
    novel.write_bytes(original + b"tampered")
    with pytest.raises(StoryError) as error:
        status_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    assert novel.read_bytes() == original + b"tampered"

    novel.write_text("future", encoding="utf-8")
    with pytest.raises(StoryError) as error:
        verify_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    assert novel.exists()


def test_novel_header_and_cli_export(story_factory, capsys) -> None:
    from tgn.story.__main__ import main

    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="ar",
        initial_voice_id="cablecar_survival",
    )
    assert main(
        [
            "export",
            "--story-dir",
            str(story),
            "--campaign-dir",
            str(campaign),
            "--mode",
            "snapshot",
            "--accepted-decisions",
            "0",
        ]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["novel_status"] == "CURRENT_SNAPSHOT"
    header = parse_novel_header((story / "novel.md").read_bytes())
    assert header.accepted_decisions == 0
    assert header.recorded_decision_count == 0

    with pytest.raises(ValueError):
        parse_novel_header(canonical_bytes({"not": "markdown"}))
    with pytest.raises(ValueError):
        build_novel(
            story_id="story-001",
            campaign_id="campaign-001",
            session_id="campaign-001",
            mode="snapshot",
            accepted_decisions=1,
            recorded_decision_count=1,
            turns=(),
        )


@pytest.mark.parametrize(
    "payload",
    [
        b"not markdown",
        b"# TheGreatNovel\n\n",
        b"# TheGreatNovel\r\n",
        b"# TheGreatNovel\n\nstory_id: s\ncampaign_id: c\nsession_id: c\nexport_mode: bad\naccepted_decisions: 0\nrecorded_decision_count: 0\n\n",
        b"# TheGreatNovel\n\nstory_id: s\ncampaign_id: c\nsession_id: c\nexport_mode: snapshot\naccepted_decisions: 01\nrecorded_decision_count: 0\n\n",
    ],
)
def test_novel_header_rejects_noncanonical_forms(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_novel_header(payload)


def test_novel_builder_rejects_invalid_boundaries() -> None:
    with pytest.raises(ValueError):
        parse_novel_header("not bytes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parse_novel_header(
            b"# TheGreatNovel\n\nstory_id: \ncampaign_id: c\nsession_id: c\nexport_mode: snapshot\naccepted_decisions: 0\nrecorded_decision_count: 0\n\n"
        )
    with pytest.raises(ValueError):
        parse_novel_header(
            b"# TheGreatNovel\n\nstory_id: s\ncampaign_id: c\nsession_id: c\nexport_mode: snapshot\naccepted_decisions: nope\nrecorded_decision_count: 0\n\n"
        )
    with pytest.raises(ValueError):
        build_novel(
            story_id="s",
            campaign_id="c",
            session_id="c",
            mode="invalid",
            accepted_decisions=0,
            recorded_decision_count=0,
            turns=(),
        )
    with pytest.raises(ValueError):
        build_novel(
            story_id="s",
            campaign_id="c",
            session_id="c",
            mode="snapshot",
            accepted_decisions=0,
            recorded_decision_count=0,
            turns=(),
            stop_reason="EXPLICIT_STOP",
        )
    with pytest.raises(ValueError):
        build_novel(
            story_id="s",
            campaign_id="c",
            session_id="c",
            mode="final",
            accepted_decisions=0,
            recorded_decision_count=0,
            turns=(),
        )
    with pytest.raises(ValueError):
        build_novel(
            story_id="s",
            campaign_id="c",
            session_id="c",
            mode="snapshot",
            accepted_decisions=1,
            recorded_decision_count=0,
            turns=(),
        )


def test_derived_replace_uses_anchored_parent_and_cleans_failures(tmp_path: Path) -> None:
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")
    replace_bytes_atomic(target, b"new")
    assert target.read_bytes() == b"new"

    with pytest.raises(PublicationConflict):
        replace_bytes_atomic(tmp_path / "missing.md", b"new")
    assert not list(tmp_path.glob("*.tmp"))

    directory_target = tmp_path / "directory.md"
    directory_target.mkdir()
    with pytest.raises(PublicationRuntime):
        replace_bytes_atomic(directory_target, b"new")

    binding = BoundPublicationDirectory.bind(tmp_path)
    try:
        original_identity = binding._identity_at
        binding._identity_at = lambda *_args: ("different",)  # type: ignore[method-assign]
        with pytest.raises(PublicationBoundaryChanged):
            binding.publish_replace("novel.md", b"competitor")
        binding._identity_at = original_identity  # type: ignore[method-assign]
    finally:
        binding.close_safely()


def test_derived_replace_uses_posix_dirfd_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)

    def replace_file(source_name, target_name, *, src_dir_fd=None, dst_dir_fd=None):
        binding._close_temp_fd()
        os.replace(
            fd_paths[src_dir_fd] / source_name,
            fd_paths[dst_dir_fd] / target_name,
        )

    monkeypatch.setattr(publication_module.os, "replace", replace_file)
    try:
        replace_bytes_atomic(target, b"new", parent_binding=binding)
        assert target.read_bytes() == b"new"
    finally:
        binding.close_safely()


def test_derived_replace_rejects_same_bytes_new_target_identity(tmp_path: Path) -> None:
    target = tmp_path / "novel.md"
    target.write_bytes(b"same bytes")
    binding = BoundPublicationDirectory.bind(tmp_path)
    try:
        expected_identity = binding.child_identity("novel.md", "file")
        replacement = tmp_path / "replacement.md"
        replacement.write_bytes(b"same bytes")
        os.replace(replacement, target)

        with pytest.raises(PublicationBoundaryChanged):
            binding.publish_replace(
                "novel.md",
                b"new export",
                expected_target_identity=expected_identity,
            )
        assert target.read_bytes() == b"same bytes"
        assert not list(tmp_path.glob(".novel.md.*.tmp"))
    finally:
        binding.close_safely()


def test_derived_replace_boundary_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")

    def replace_file(source_name, target_name, *, src_dir_fd=None, dst_dir_fd=None):
        # The temporary descriptor is intentionally released only after its
        # identity has been checked, mirroring the platform primitive.
        binding._close_temp_fd()
        os.replace(fd_paths[src_dir_fd] / source_name, fd_paths[dst_dir_fd] / target_name)

    monkeypatch.setattr(publication_module.os, "replace", replace_file)
    binding = BoundPublicationDirectory.bind(tmp_path)
    try:
        with pytest.raises(PublicationConflict):
            binding.publish_replace("missing.md", b"missing")

        monkeypatch.setattr(publication_module.sys, "platform", "freebsd")
        with pytest.raises(PublicationUnavailable):
            binding.publish_replace("novel.md", b"unsupported")
        monkeypatch.setattr(publication_module.sys, "platform", "linux")

        monkeypatch.setattr(
            publication_module.os,
            "replace",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("rename")),
        )
        with pytest.raises(PublicationRuntime):
            binding.publish_replace("novel.md", b"rename failure")
    finally:
        binding.close_safely()

    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)
    directory = tmp_path / "not-regular"
    directory.mkdir()
    def replace_file_post(source_name, target_name, *, src_dir_fd=None, dst_dir_fd=None):
        binding._close_temp_fd()
        os.replace(fd_paths[src_dir_fd] / source_name, fd_paths[dst_dir_fd] / target_name)

    monkeypatch.setattr(publication_module.os, "replace", replace_file_post)
    original_stat = binding._stat_at
    target_reads = 0

    def invalid_post_stat(name):
        nonlocal target_reads
        if name == "novel.md":
            target_reads += 1
            if target_reads == 2:
                return os.stat(directory)
        return original_stat(name)

    monkeypatch.setattr(binding, "_stat_at", invalid_post_stat)
    try:
        with pytest.raises(PublicationRuntime):
            binding.publish_replace("novel.md", b"invalid post target")
    finally:
        binding.close_safely()


def test_derived_replace_post_read_and_close_failures_are_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)

    def replace_file(source_name, target_name, *, src_dir_fd=None, dst_dir_fd=None):
        binding._close_temp_fd()
        os.replace(fd_paths[src_dir_fd] / source_name, fd_paths[dst_dir_fd] / target_name)

    monkeypatch.setattr(publication_module.os, "replace", replace_file)
    original_stat = binding._stat_at
    target_reads = 0

    def failing_post_stat(name):
        nonlocal target_reads
        if name == "novel.md":
            target_reads += 1
            if target_reads == 2:
                raise OSError("post-read")
        return original_stat(name)

    monkeypatch.setattr(binding, "_stat_at", failing_post_stat)
    try:
        with pytest.raises(PublicationRuntime):
            binding.publish_replace("novel.md", b"post-read failure")
    finally:
        binding.close_safely()

    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)

    def close_fd_then_fail():
        raise PublicationRuntime("close fd")

    def close_handle_then_fail():
        raise PublicationRuntime("close handle")

    def replace_file_again(source_name, target_name, *, src_dir_fd=None, dst_dir_fd=None):
        if binding._temp_fd is not None:
            os.close(binding._temp_fd)
            binding._temp_fd = None
        os.replace(fd_paths[src_dir_fd] / source_name, fd_paths[dst_dir_fd] / target_name)

    monkeypatch.setattr(publication_module.os, "replace", replace_file_again)
    monkeypatch.setattr(binding, "_close_temp_fd", close_fd_then_fail)
    monkeypatch.setattr(binding, "_close_temp_handle", close_handle_then_fail)
    try:
        binding.publish_replace("novel.md", b"close failure")
        assert target.read_bytes() == b"close failure"
    finally:
        binding.close_safely()


@pytest.mark.parametrize("result,error_number,expected", [(1, 0, None), (0, 1, PublicationUnavailable), (0, 5, PublicationRuntime)])
def test_windows_replace_primitive_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: int, error_number: int, expected) -> None:
    class Function:
        def __init__(self, value: int):
            self.value = value
            self.argtypes = None
            self.restype = None

        def __call__(self, *_args):
            return self.value

    class Kernel:
        MoveFileExW = Function(result)

    monkeypatch.setattr(publication_module.ctypes, "WinDLL", lambda *_args, **_kwargs: Kernel())
    monkeypatch.setattr(publication_module.ctypes, "get_last_error", lambda: error_number)
    if expected is None:
        publication_module._windows_replace(tmp_path / "source", tmp_path / "target")
    else:
        with pytest.raises(expected):
            publication_module._windows_replace(tmp_path / "source", tmp_path / "target")

    monkeypatch.setattr(
        publication_module.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")),
    )
    with pytest.raises(PublicationUnavailable):
        publication_module._windows_replace(tmp_path / "source", tmp_path / "target")


def test_windows_identity_and_cleanup_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    binding = BoundPublicationDirectory(tmp_path)

    # The Windows temporary path must be checked against both the retained
    # handle identity and the current name identity.
    monkeypatch.setattr(publication_module.os, "name", "nt")
    binding._temp_name = "temporary.tmp"
    binding._temp_kind = "file"
    binding._temp_identity = ("windows", 1, 2, 3)
    binding._close_temp_handle_safely = lambda: None  # type: ignore[method-assign]
    binding._open_windows_child_handle = lambda *_args: (123, 0, ("windows", 9, 9, 9))  # type: ignore[method-assign]
    with pytest.raises(PublicationRuntime):
        binding._open_windows_temp_handle()

    binding._temp_handle = None
    binding._open_windows_child_handle = lambda *_args: (123, 0, ("windows", 1, 2, 3))  # type: ignore[method-assign]
    binding._windows_identity_at = lambda *_args: (0, ("windows", 4, 5, 6))  # type: ignore[method-assign]
    with pytest.raises(PublicationRuntime):
        binding._open_windows_temp_handle()

    binding._temp_handle = None
    with pytest.raises(PublicationRuntime):
        binding._verify_temp()
    binding._temp_handle = 123
    binding._windows_info_for_handle = lambda *_args: (binding._FILE_ATTRIBUTE_REPARSE_POINT, binding._temp_identity)  # type: ignore[method-assign]
    with pytest.raises(PublicationRuntime):
        binding._verify_temp()

    class Function:
        def __init__(self, value):
            self.value = value
            self.argtypes = None
            self.restype = None

        def __call__(self, *_args):
            return self.value

    class Kernel:
        CreateFileW = Function(ctypes.c_void_p(123))
        GetFileInformationByHandle = Function(0)
        CloseHandle = Function(0)

    monkeypatch.setattr(publication_module.ctypes, "WinDLL", lambda *_args, **_kwargs: Kernel())
    del binding._open_windows_child_handle
    with pytest.raises(PublicationRuntime):
        binding._open_windows_child_handle("temporary.tmp", "file")
    binding._windows_info = lambda: (_ for _ in ()).throw(PublicationRuntime("info"))  # type: ignore[method-assign]
    with pytest.raises(PublicationRuntime):
        binding._open_windows_handle()

    monkeypatch.setattr(publication_module.os, "name", "posix")
    binding = BoundPublicationDirectory.bind(tmp_path)
    binding.create_temp_file("close.tmp")
    temp_fd = binding._temp_fd
    assert temp_fd is not None
    with monkeypatch.context() as context:
        context.setattr(publication_module.os, "close", lambda _fd: (_ for _ in ()).throw(OSError("close")))
        with pytest.raises(PublicationRuntime):
            binding._close_temp_fd()
    binding._temp_fd = None
    binding._close_temp_handle = lambda: (_ for _ in ()).throw(PublicationRuntime("handle"))  # type: ignore[method-assign]
    binding._temp_handle = 123
    with pytest.raises(PublicationRuntime):
        binding._close_temp_handle()
    binding._close_temp_handle_safely()
    binding.close_safely()


def test_export_input_and_publication_errors_are_bounded(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="invalid", accepted_decisions=0)
    assert error.value.code == "INVALID_STORY_INPUT"
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="snapshot")
    assert error.value.code == "INVALID_STORY_INPUT"
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="final", accepted_decisions=0)
    assert error.value.code == "INVALID_STORY_INPUT"
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=-1)
    assert error.value.code == "INVALID_STORY_INPUT"
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=1)
    assert error.value.code == "INVALID_STORY_INPUT"

    monkeypatch.setattr(
        service_module,
        "publish_bytes_no_replace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PublicationRuntime("unavailable")),
    )
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=0)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"


@pytest.mark.parametrize(
    "publication_error, expected_code",
    [
        (PublicationBoundaryChanged("story-error:STORY_INTEGRITY_MISMATCH"), "STORY_INTEGRITY_MISMATCH"),
        (PublicationBoundaryChanged("story-error:CAMPAIGN_SNAPSHOT_CHANGED"), "CAMPAIGN_SNAPSHOT_CHANGED"),
        (PublicationBoundaryChanged("other boundary"), "STORY_PUBLICATION_UNAVAILABLE"),
        (PublicationConflict("target"), "STORY_PUBLICATION_UNAVAILABLE"),
    ],
)
def test_export_publication_boundary_error_mapping(story_factory, monkeypatch: pytest.MonkeyPatch, publication_error, expected_code) -> None:
    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    monkeypatch.setattr(
        service_module,
        "publish_bytes_no_replace",
        lambda *_args, _error=publication_error, **_kwargs: (_ for _ in ()).throw(_error),
    )
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=0)
    assert error.value.code == expected_code


def test_export_build_and_root_guard_fail_closed(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    monkeypatch.setattr(service_module, "build_novel", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("builder")))
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=0)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"

    monkeypatch.undo()
    monkeypatch.setattr(service_module, "story_directory_identity_matches", lambda *_args: False)
    with pytest.raises(StoryError) as error:
        export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=0)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"


def test_prepare_rejects_unsupported_locale_before_mutation(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign, narration_locale="fr")
    assert error.value.code == "INVALID_STORY_INPUT"


def test_story_view_input_and_read_only_observable_boundaries(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(StoryError) as error:
        verification_module._actual_story_root(tmp_path / "missing")
    assert error.value.code == "STORY_NOT_FOUND"
    file_root = tmp_path / "file-root"
    file_root.write_bytes(b"x")
    with pytest.raises(StoryError) as error:
        verification_module._actual_story_root(file_root)
    assert error.value.code == "INVALID_STORY_INPUT"
    real_lstat = verification_module.os.lstat
    monkeypatch.setattr(
        verification_module.os,
        "lstat",
        lambda *_args: (_ for _ in ()).throw(OSError("inspect")),
    )
    with pytest.raises(StoryError) as error:
        verification_module._actual_story_root(tmp_path / "blocked")
    assert error.value.code == "INVALID_STORY_INPUT"
    monkeypatch.setattr(verification_module.os, "lstat", real_lstat)

    expected_directory = StoryDirectoryObservable(".", 0, 1, 1, 0, 0, 0)
    assert verification_module.story_directory_identity_matches(tmp_path / "missing", expected_directory) is False

    campaign, story, config = story_factory()
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    original_children = verification_module.list_actual_children
    monkeypatch.setattr(
        verification_module,
        "list_actual_children",
        lambda path: (_ for _ in ()).throw(OSError("list")) if path == story else original_children(path),
    )
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification_module, "list_actual_children", original_children)

    export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=0)
    original_read = verification_module.read_regular_file
    monkeypatch.setattr(
        verification_module,
        "read_regular_file",
        lambda path: (_ for _ in ()).throw(OSError("novel read"))
        if Path(path).name == "novel.md"
        else original_read(path),
    )
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification_module, "read_regular_file", original_read)

    original_capture = verification_module.capture_story_directory
    calls = 0

    def changed_final(path, *, relative_path):
        nonlocal calls
        calls += 1
        observed = original_capture(path, relative_path=relative_path)
        if calls == 6 and relative_path == "turns":
            return dataclasses.replace(observed, mtime_ns=observed.mtime_ns + 1)
        return observed

    monkeypatch.setattr(verification_module, "capture_story_directory", changed_final)
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
