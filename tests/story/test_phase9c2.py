from __future__ import annotations

import ctypes
import dataclasses
import json
import os
import sqlite3
from pathlib import Path

import pytest
import tgn.story.publication as publication_module
import tgn.story.service as service_module

from tgn.campaign import choose_campaign, next_campaign, stop_campaign
from tgn.campaign import verify_campaign
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
    ERROR_UNABLE_TO_MOVE_REPLACEMENT,
    ERROR_UNABLE_TO_MOVE_REPLACEMENT_2,
    ERROR_UNABLE_TO_REMOVE_REPLACED,
    ExpectedPublicationFile,
    PublicationBoundaryChanged,
    PublicationConflict,
    PublicationRuntime,
    PublicationUnavailable,
    WindowsReplaceFailure,
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
    with pytest.raises(PublicationRuntime):
        replace_bytes_atomic(target, b"new")
    binding = BoundPublicationDirectory.bind(tmp_path)
    expected = binding.capture_file_observable("novel.md")
    binding.close_safely()
    replace_bytes_atomic(target, b"new", expected_target=expected)
    assert target.read_bytes() == b"new"

    with pytest.raises(PublicationRuntime):
        replace_bytes_atomic(tmp_path / "missing.md", b"new")
    assert not list(tmp_path.glob("*.tmp"))

    directory_target = tmp_path / "directory.md"
    directory_target.mkdir()
    with pytest.raises(PublicationRuntime):
        replace_bytes_atomic(directory_target, b"new", expected_target=expected)

    binding = BoundPublicationDirectory.bind(tmp_path)
    try:
        with pytest.raises(PublicationRuntime):
            binding.publish_replace("novel.md", b"competitor")
    finally:
        binding.close_safely()


def test_expected_publication_file_rejects_inconsistent_observables() -> None:
    payload = b"payload"
    valid = ExpectedPublicationFile(
        identity=("test", 1),
        sha256=publication_module.sha256_bytes(payload),
        size=len(payload),
        mtime_ns=1,
        payload=payload,
    )
    assert valid.payload == payload
    invalid_values = (
        {"identity": (), "sha256": valid.sha256, "size": valid.size, "mtime_ns": valid.mtime_ns, "payload": payload},
        {"identity": valid.identity, "sha256": valid.sha256, "size": -1, "mtime_ns": valid.mtime_ns, "payload": payload},
        {"identity": valid.identity, "sha256": valid.sha256, "size": valid.size, "mtime_ns": -1, "payload": payload},
        {"identity": valid.identity, "sha256": "bad", "size": valid.size, "mtime_ns": valid.mtime_ns, "payload": payload},
        {"identity": valid.identity, "sha256": valid.sha256, "size": valid.size, "mtime_ns": valid.mtime_ns, "payload": "payload"},
        {"identity": valid.identity, "sha256": valid.sha256, "size": valid.size + 1, "mtime_ns": valid.mtime_ns, "payload": payload},
    )
    for fields in invalid_values:
        with pytest.raises(PublicationRuntime):
            ExpectedPublicationFile(**fields)


def test_derived_replace_uses_posix_dirfd_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)

    def exchange_names(source_name, target_name, source_dir_fd=None, target_dir_fd=None):
        source_path = fd_paths[source_dir_fd] / source_name
        target_path = fd_paths[target_dir_fd] / target_name
        displaced = source_path.with_name(f".exchange-{source_path.name}")
        binding._close_temp_fd()
        os.replace(source_path, displaced)
        os.replace(target_path, source_path)
        os.replace(displaced, target_path)

    monkeypatch.setattr(publication_module, "_linux_exchange", exchange_names)
    try:
        expected = binding.capture_file_observable("novel.md")
        replace_bytes_atomic(target, b"new", parent_binding=binding, expected_target=expected)
        assert target.read_bytes() == b"new"
    finally:
        binding.close_safely()


def test_derived_replace_rejects_same_bytes_new_target_identity(tmp_path: Path) -> None:
    target = tmp_path / "novel.md"
    target.write_bytes(b"same bytes")
    binding = BoundPublicationDirectory.bind(tmp_path)
    try:
        expected = binding.capture_file_observable("novel.md")
        replacement = tmp_path / "replacement.md"
        replacement.write_bytes(b"same bytes")
        os.replace(replacement, target)

        with pytest.raises(PublicationBoundaryChanged):
            binding.publish_replace(
                "novel.md",
                b"new export",
                expected_target=expected,
            )
        assert target.read_bytes() == b"same bytes"
        assert not list(tmp_path.glob(".novel.md.*.tmp"))
    finally:
        binding.close_safely()


def test_derived_replace_boundary_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")

    binding = BoundPublicationDirectory.bind(tmp_path)
    try:
        expected = binding.capture_file_observable("novel.md")
        with pytest.raises(PublicationBoundaryChanged):
            binding.publish_replace("missing.md", b"missing", expected_target=expected)

        monkeypatch.setattr(publication_module.sys, "platform", "freebsd")
        with pytest.raises(PublicationUnavailable):
            binding.publish_replace("novel.md", b"unsupported", expected_target=expected)
        monkeypatch.setattr(publication_module.sys, "platform", "linux")

        monkeypatch.setattr(
            publication_module,
            "_linux_exchange",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("rename")),
        )
        with pytest.raises(PublicationRuntime):
            binding.publish_replace("novel.md", b"rename failure", expected_target=expected)
    finally:
        binding.close_safely()

    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)
    expected = binding.capture_file_observable("novel.md")
    monkeypatch.setattr(
        publication_module,
        "_linux_exchange",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("rename")),
    )
    try:
        with pytest.raises(PublicationRuntime):
            binding.publish_replace("novel.md", b"invalid post target", expected_target=expected)
    finally:
        binding.close_safely()


def test_derived_replace_post_read_and_close_failures_are_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)
    expected = binding.capture_file_observable("novel.md")

    def exchange_names(source_name, target_name, source_dir_fd=None, target_dir_fd=None):
        source_path = fd_paths[source_dir_fd] / source_name
        target_path = fd_paths[target_dir_fd] / target_name
        displaced = source_path.with_name(f".exchange-{source_path.name}")
        binding._close_temp_fd()
        os.replace(source_path, displaced)
        os.replace(target_path, source_path)
        os.replace(displaced, target_path)

    monkeypatch.setattr(publication_module, "_linux_exchange", exchange_names)
    try:
        with pytest.raises(PublicationRuntime):
            monkeypatch.setattr(
                binding,
                "_writer_target_matches",
                lambda *_args: (_ for _ in ()).throw(PublicationRuntime("post-read")),
            )
            binding.publish_replace("novel.md", b"post-read failure", expected_target=expected)
    finally:
        binding.close_safely()
    assert target.read_bytes() == b"post-read failure"
    assert {child.name for child in tmp_path.iterdir()} == {"novel.md"}


def test_derived_replace_close_failures_are_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)
    expected = binding.capture_file_observable("novel.md")

    def close_fd_then_fail():
        raise PublicationRuntime("close fd")

    def close_handle_then_fail():
        raise PublicationRuntime("close handle")

    def exchange_names(source_name, target_name, source_dir_fd=None, target_dir_fd=None):
        source_path = fd_paths[source_dir_fd] / source_name
        target_path = fd_paths[target_dir_fd] / target_name
        displaced = source_path.with_name(f".exchange-{source_path.name}")
        if binding._temp_fd is not None:
            os.close(binding._temp_fd)
            binding._temp_fd = None
        os.replace(source_path, displaced)
        os.replace(target_path, source_path)
        os.replace(displaced, target_path)

    monkeypatch.setattr(publication_module, "_linux_exchange", exchange_names)
    monkeypatch.setattr(binding, "_close_temp_fd", close_fd_then_fail)
    monkeypatch.setattr(binding, "_close_temp_handle", close_handle_then_fail)
    try:
        binding.publish_replace("novel.md", b"close failure", expected_target=expected)
        assert target.read_bytes() == b"close failure"
    finally:
        binding.close_safely()


@pytest.mark.parametrize("competitor_payload", [b"old", b"competitor"])
def test_conditional_replace_preserves_competitor_after_final_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    competitor_payload: bytes,
) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)
    expected = binding.capture_file_observable("novel.md")
    armed = True

    def exchange_names(source_name, target_name, source_dir_fd=None, target_dir_fd=None):
        nonlocal armed
        source_path = fd_paths[source_dir_fd] / source_name
        target_path = fd_paths[target_dir_fd] / target_name
        if armed:
            competitor = target_path.with_name("competitor.md")
            competitor.write_bytes(competitor_payload)
            os.replace(competitor, target_path)
            armed = False
        binding._close_temp_fd()
        displaced = source_path.with_name(f".exchange-{source_path.name}")
        os.replace(source_path, displaced)
        os.replace(target_path, source_path)
        os.replace(displaced, target_path)

    monkeypatch.setattr(publication_module, "_linux_exchange", exchange_names)
    try:
        with pytest.raises(PublicationBoundaryChanged):
            replace_bytes_atomic(
                target,
                b"writer payload",
                parent_binding=binding,
                expected_target=expected,
            )
        competitor_identity = binding.child_identity("novel.md", "file")
        assert target.read_bytes() == competitor_payload
        assert competitor_identity != expected.identity
        assert not list(tmp_path.glob(".novel.md.*.tmp"))
    finally:
        binding.close_safely()


@pytest.mark.parametrize("competitor_payload", [b"same-byte competitor", b"different-byte competitor"])
def test_conditional_replace_post_primitive_interference_preserves_unknown_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    competitor_payload: bytes,
) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)
    expected = binding.capture_file_observable("novel.md")
    interfered = False

    def exchange_names(source_name, target_name, source_dir_fd=None, target_dir_fd=None):
        nonlocal interfered
        source_path = fd_paths[source_dir_fd] / source_name
        target_path = fd_paths[target_dir_fd] / target_name
        binding._close_temp_fd()
        displaced = source_path.with_name(f".exchange-{source_path.name}")
        os.replace(source_path, displaced)
        os.replace(target_path, source_path)
        os.replace(displaced, target_path)
        if not interfered:
            competitor = target_path.with_name("unknown-competitor.md")
            competitor.write_bytes(competitor_payload)
            os.replace(competitor, target_path)
            interfered = True

    monkeypatch.setattr(publication_module, "_linux_exchange", exchange_names)
    try:
        with pytest.raises(PublicationBoundaryChanged):
            replace_bytes_atomic(
                target,
                b"writer payload",
                parent_binding=binding,
                expected_target=expected,
            )
        assert target.read_bytes() == competitor_payload
        assert not target.read_bytes() == b"writer payload"
        assert {child.name for child in tmp_path.iterdir()} == {"novel.md"}
    finally:
        binding.close_safely()


def test_export_rejects_story_root_replacement_after_final_guard(
    story_factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, story, config = story_factory(name="phase9c2-root-publication-race")
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
    export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=1)
    original_novel = (story / "novel.md").read_bytes()
    _choose(campaign, "SEARCH")
    next_request = prepare_story(story, campaign_dir=campaign)["request"]
    commit_story(story, campaign_dir=campaign, response=response_for(next_request))

    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    detached = tmp_path / "phase9c2-root-detached"
    moved = False
    current_binding = None
    original_exchange_method = publication_module.BoundPublicationDirectory._exchange_names

    def capture_binding(self, source_name, target_name):
        nonlocal current_binding
        current_binding = self
        return original_exchange_method(self, source_name, target_name)

    def exchange_names(source_name, target_name, source_dir_fd=None, target_dir_fd=None):
        nonlocal moved
        assert current_binding is not None
        if not moved:
            current_binding._close_temp_fd()
            story.rename(detached)
            story.mkdir()
            for child_name in ("story.json", "requests", "turns"):
                (detached / child_name).rename(story / child_name)
            fd_paths[source_dir_fd] = detached
            moved = True
        source_path = fd_paths[source_dir_fd] / source_name
        target_path = fd_paths[target_dir_fd] / target_name
        displaced = source_path.with_name(f".exchange-{source_path.name}")
        os.replace(source_path, displaced)
        os.replace(target_path, source_path)
        os.replace(displaced, target_path)

    monkeypatch.setattr(publication_module.BoundPublicationDirectory, "_exchange_names", capture_binding)
    monkeypatch.setattr(publication_module, "_linux_exchange", exchange_names)
    try:
        with pytest.raises(StoryError) as error:
            export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=2)
        assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
        assert moved is True
        assert not (story / "novel.md").exists()
        assert (detached / "novel.md").read_bytes() == original_novel
    finally:
        if story.exists():
            for child_name in ("story.json", "requests", "turns"):
                child = story / child_name
                if child.exists():
                    child.rename(detached / child_name)
            story.rmdir()
        if detached.exists():
            detached.rename(story)


def test_phase9c2_complete_campaign_story_locale_resume_and_final_rebuild_proof(
    story_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, story, config = story_factory(name="phase9c2-complete-proof", max_decisions=10)
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="zh-CN",
        initial_voice_id="cablecar_survival",
    )

    def no_completion(*_args, **_kwargs):
        raise AssertionError("Phase 9C2 deterministic proof must not invoke a provider")

    from tgn.llm_player import policy

    monkeypatch.setattr(policy.LLMPlayerPolicy, "__init__", no_completion)

    _choose(campaign, "DROP")
    before_prepare = verify_campaign(campaign)
    assert before_prepare["verification"]["event_replay"] is True
    drop_request = prepare_story(story, campaign_dir=campaign)["request"]
    assert drop_request["narration_locale"] == "zh-CN"
    commit_story(
        story,
        campaign_dir=campaign,
        response=response_for(drop_request, prose="中文后果已经出现。"),
    )
    drop_turn_bytes = (story / "turns" / "turn-000001.json").read_bytes()

    _choose(campaign, "SEARCH")
    search_request = prepare_story(story, campaign_dir=campaign)["request"]
    search_history = verify_campaign(campaign)
    assert search_history["verification"]["event_replay"] is True
    assert status_story(story, campaign_dir=campaign)["pending_turn_id"] == "turn-000002"
    reopened_request = prepare_story(story, campaign_dir=campaign)["request"]
    assert reopened_request == search_request
    commit_story(
        story,
        campaign_dir=campaign,
        response=response_for(search_request, prose="搜索结果仍在公开边界内。"),
    )

    _choose(campaign, "EXTRACT")
    arabic_request = prepare_story(story, campaign_dir=campaign, narration_locale="ar")["request"]
    assert arabic_request["narration_locale"] == "ar"
    commit_story(
        story,
        campaign_dir=campaign,
        response=response_for(arabic_request, prose="ظهرت نتيجة واضحة."),
    )

    _choose(campaign, "TALK_TO_ACTOR")
    talk_request = prepare_story(story, campaign_dir=campaign)["request"]
    assert talk_request["narration_locale"] == "ar"
    forbidden_keys = {"knowledge", "goal", "private_goal", "world_truth", "private_world_truth"}

    def walk_keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from walk_keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk_keys(child)

    assert not forbidden_keys.intersection(walk_keys(talk_request))
    commit_story(
        story,
        campaign_dir=campaign,
        response=response_for(talk_request, prose="بقيت المعرفة الخاصة خارج السرد."),
    )
    talk_artifact = json.loads((story / "turns" / "turn-000004.json").read_text(encoding="utf-8"))
    assert not forbidden_keys.intersection(walk_keys(talk_artifact))
    assert (story / "turns" / "turn-000001.json").read_bytes() == drop_turn_bytes
    assert any(
        "بقيت" in (story / "turns" / "turn-000004.json").read_text(encoding="utf-8")
        for _ in [0]
    )

    current = next_campaign(campaign)
    stop_result = stop_campaign(
        campaign,
        request_fingerprint=current["canonical_request"]["request_fingerprint"],
    )
    assert stop_result["session"]["status"] == "STOPPED"
    assert prepare_story(story, campaign_dir=campaign)["request"] is None
    assert not (story / "requests" / "turn-000005.json").exists()
    assert not (story / "turns" / "turn-000005.json").exists()
    campaign_result = verify_campaign(campaign)
    assert campaign_result["verification"]["event_replay"] is True
    assert campaign_result["verification"]["recorded_decision_replay"] is True
    connection = sqlite3.connect(campaign / "session" / "campaign.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 4
    finally:
        connection.close()
    records = json.loads(
        (campaign / "session" / "recorded_decisions.json").read_text(encoding="utf-8")
    )["decisions"]
    assert [record["outcome"] for record in records] == ["ACTION"] * 4 + ["STOP"]

    exported = export_story(story, campaign_dir=campaign, mode="final")
    assert exported["novel_status"] == "CURRENT_FINAL"
    assert verify_story(story, campaign_dir=campaign)["verification"]["novel_status"] == "CURRENT_FINAL"
    final_bytes = (story / "novel.md").read_bytes()
    assert "中文后果".encode("utf-8") in final_bytes
    assert "ظهرت".encode("utf-8") in final_bytes
    assert "بقيت".encode("utf-8") in final_bytes
    (story / "novel.md").unlink()
    rebuilt = export_story(story, campaign_dir=campaign, mode="final")
    assert rebuilt["novel_status"] == "CURRENT_FINAL"
    assert (story / "novel.md").read_bytes() == final_bytes
    assert verify_story(story, campaign_dir=campaign)["valid"] is True


def test_phase9c2_existing_novel_replace_campaign_integration_proof(
    story_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, story, config = story_factory(name="phase9c2-existing-novel-replace", max_decisions=10)
    init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )
    windows_replace_calls: list[tuple[object, ...]] = []
    if os.name == "nt":
        original_windows_replace = publication_module._windows_replace_file

        def spy_windows_replace(*args, **kwargs):
            windows_replace_calls.append(args)
            return original_windows_replace(*args, **kwargs)

        monkeypatch.setattr(publication_module, "_windows_replace_file", spy_windows_replace)

    _choose(campaign, "DROP")
    drop_request = prepare_story(story, campaign_dir=campaign)["request"]
    commit_story(
        story,
        campaign_dir=campaign,
        response=response_for(drop_request, prose="The first consequence is now visible."),
    )
    first_export = export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=1)
    assert first_export["novel_status"] == "CURRENT_SNAPSHOT"
    first_bytes = (story / "novel.md").read_bytes()
    assert {child.name for child in story.iterdir()} == {"story.json", "requests", "turns", "novel.md"}

    _choose(campaign, "SEARCH")
    search_request = prepare_story(story, campaign_dir=campaign)["request"]
    commit_story(
        story,
        campaign_dir=campaign,
        response=response_for(search_request, prose="The second consequence changes the snapshot."),
    )
    second_export = export_story(story, campaign_dir=campaign, mode="snapshot", accepted_decisions=2)
    assert second_export["novel_status"] == "CURRENT_SNAPSHOT"
    second_bytes = (story / "novel.md").read_bytes()
    assert second_bytes != first_bytes
    assert {child.name for child in story.iterdir()} == {"story.json", "requests", "turns", "novel.md"}

    current = next_campaign(campaign)
    stop_campaign(
        campaign,
        request_fingerprint=current["canonical_request"]["request_fingerprint"],
    )
    final_export = export_story(story, campaign_dir=campaign, mode="final")
    assert final_export["novel_status"] == "CURRENT_FINAL"
    assert verify_story(story, campaign_dir=campaign)["verification"]["novel_status"] == "CURRENT_FINAL"
    assert {child.name for child in story.iterdir()} == {"story.json", "requests", "turns", "novel.md"}
    assert (story / "novel.md").read_bytes() != second_bytes
    assert verify_campaign(campaign)["verification"]["event_replay"] is True
    if os.name == "nt":
        assert len(windows_replace_calls) >= 2


@pytest.mark.parametrize(
    "result,error_number,expected",
    [
        (1, 0, None),
        (0, ERROR_UNABLE_TO_REMOVE_REPLACED, WindowsReplaceFailure),
        (0, ERROR_UNABLE_TO_MOVE_REPLACEMENT, WindowsReplaceFailure),
        (0, ERROR_UNABLE_TO_MOVE_REPLACEMENT_2, WindowsReplaceFailure),
        (0, 5, WindowsReplaceFailure),
    ],
)
def test_windows_replace_primitive_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result: int,
    error_number: int,
    expected,
) -> None:
    class Function:
        def __init__(self, value: int):
            self.value = value
            self.argtypes = None
            self.restype = None

        def __call__(self, *_args):
            return self.value

    class Kernel:
        ReplaceFileW = Function(result)

    monkeypatch.setattr(publication_module.ctypes, "WinDLL", lambda *_args, **_kwargs: Kernel())
    monkeypatch.setattr(publication_module.ctypes, "get_last_error", lambda: error_number)
    if expected is None:
        publication_module._windows_replace_file(
            tmp_path / "source", tmp_path / "target", tmp_path / "backup"
        )
    else:
        with pytest.raises(expected) as error:
            publication_module._windows_replace_file(
                tmp_path / "source", tmp_path / "target", tmp_path / "backup"
            )
        assert error.value.error_number == error_number
        assert error.value.outcome == publication_module.WindowsReplaceFailure._OUTCOMES.get(
            error_number,
            "OTHER",
        )

    monkeypatch.setattr(
        publication_module.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")),
    )
    with pytest.raises(PublicationUnavailable):
        publication_module._windows_replace_file(
            tmp_path / "source", tmp_path / "target", tmp_path / "backup"
        )


def _windows_recovery_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    target: ExpectedPublicationFile | None,
    replacement: ExpectedPublicationFile,
    backup: ExpectedPublicationFile | None,
):
    """Build a bounded Win32 layout model with real sibling names."""

    class WindowsOSProxy:
        name = "nt"

        def __getattr__(self, name):
            return getattr(os, name)

    monkeypatch.setattr(publication_module, "os", WindowsOSProxy())
    binding = BoundPublicationDirectory(tmp_path)
    binding.directory_handle = 99
    binding._handle_identity = ("parent", 1)
    binding._path_identity = ("parent", 1)
    binding._temp_name = ".novel.md.writer.tmp"
    binding._temp_path = tmp_path / binding._temp_name
    binding._temp_kind = "file"
    binding._temp_handle = 123
    binding._temp_identity = replacement.identity

    values: dict[str, ExpectedPublicationFile] = {
        "novel.md": target,
        binding._temp_name: replacement,
        ".novel.md.writer.backup": backup,
    }
    values = {name: value for name, value in values.items() if value is not None}
    for name, value in values.items():
        (tmp_path / name).write_bytes(value.payload)

    monkeypatch.setattr(binding, "_windows_info", lambda: (binding._FILE_ATTRIBUTE_DIRECTORY, ("parent", 1)))
    monkeypatch.setattr(binding, "_windows_info_for_handle", lambda _handle: (0, replacement.identity))
    monkeypatch.setattr(binding, "_close_temp_resources", lambda: None)
    monkeypatch.setattr(binding, "_close_temp_fd", lambda: None)
    monkeypatch.setattr(binding, "_close_temp_handle", lambda: None)
    monkeypatch.setattr(
        binding,
        "_capture_file_observable_anchored",
        lambda name: values[name] if name in values else (_ for _ in ()).throw(FileNotFoundError(name)),
    )

    def remove(name: str, expected: ExpectedPublicationFile, **_kwargs) -> None:
        if values.get(name) != expected:
            raise PublicationBoundaryChanged("unexpected Windows test object")
        values.pop(name)
        path = tmp_path / name
        if path.exists():
            path.unlink()

    monkeypatch.setattr(binding, "_remove_expected_file_anchored", remove)
    return binding, values


def _windows_observable(identity: tuple[str, int], payload: bytes) -> ExpectedPublicationFile:
    return ExpectedPublicationFile(
        identity=identity,
        sha256=publication_module.sha256_bytes(payload),
        size=len(payload),
        mtime_ns=1,
        payload=payload,
    )


@pytest.mark.parametrize(
    "error_number",
    [ERROR_UNABLE_TO_REMOVE_REPLACED, ERROR_UNABLE_TO_MOVE_REPLACEMENT],
)
def test_windows_replace_failure_1175_1176_cleans_only_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_number: int,
) -> None:
    expected = _windows_observable(("old", error_number), b"old")
    writer = _windows_observable(("writer", error_number), b"new")
    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=None,
    )
    with pytest.raises(PublicationRuntime, match=f"{error_number}"):
        binding._recover_windows_replace_failure(
            "novel.md",
            ".novel.md.writer.backup",
            expected,
            writer,
            WindowsReplaceFailure(error_number),
        )
    assert values == {"novel.md": expected}
    assert (tmp_path / "novel.md").read_bytes() == b"old"
    assert {child.name for child in tmp_path.iterdir()} == {"novel.md"}


def test_windows_replace_failure_1177_recovers_expected_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _windows_observable(("old", 1177), b"old")
    writer = _windows_observable(("writer", 1177), b"new")
    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=None,
        replacement=writer,
        backup=expected,
    )

    def restore(source, target, _parent_handle):
        source_name = Path(source).name
        target_name = Path(target).name
        assert target_name not in values
        values[target_name] = values.pop(source_name)
        (tmp_path / source_name).unlink()
        (tmp_path / target_name).write_bytes(values[target_name].payload)

    monkeypatch.setattr(publication_module, "_windows_no_replace", restore)
    with pytest.raises(PublicationRuntime, match="1177"):
        binding._recover_windows_replace_failure(
            "novel.md",
            ".novel.md.writer.backup",
            expected,
            writer,
            WindowsReplaceFailure(ERROR_UNABLE_TO_MOVE_REPLACEMENT_2),
        )
    assert values == {"novel.md": expected}
    assert {child.name for child in tmp_path.iterdir()} == {"novel.md"}


def test_windows_restore_failure_1177_recovers_displaced_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    displaced = _windows_observable(("displaced", 1177), b"displaced")
    writer = _windows_observable(("writer", 1177), b"writer")
    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=None,
        replacement=writer,
        backup=writer,
    )
    source_name = ".novel.md.displaced.backup"
    old_temp_name = binding._temp_name
    assert old_temp_name is not None
    values.pop(old_temp_name)
    (tmp_path / old_temp_name).unlink()
    values[source_name] = displaced
    (tmp_path / source_name).write_bytes(displaced.payload)

    def restore(source, target, _parent_handle):
        source_name_from_call = Path(source).name
        target_name = Path(target).name
        assert target_name not in values
        values[target_name] = values.pop(source_name_from_call)
        (tmp_path / source_name_from_call).unlink()
        (tmp_path / target_name).write_bytes(values[target_name].payload)

    monkeypatch.setattr(publication_module, "_windows_no_replace", restore)
    with pytest.raises(PublicationRuntime, match="1177"):
        binding._recover_windows_displaced_restore_failure(
            "novel.md",
            source_name,
            ".novel.md.writer.backup",
            displaced,
            writer,
            WindowsReplaceFailure(ERROR_UNABLE_TO_MOVE_REPLACEMENT_2),
        )
    assert values == {"novel.md": displaced}
    assert {child.name for child in tmp_path.iterdir()} == {"novel.md"}


def test_windows_restore_failure_preserves_competitor_and_unknown_displaced_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    displaced = _windows_observable(("displaced", 1175), b"displaced")
    writer = _windows_observable(("writer", 1175), b"writer")
    competitor = _windows_observable(("competitor", 1175), b"competitor")
    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=competitor,
        replacement=writer,
        backup=writer,
    )
    source_name = ".novel.md.displaced.backup"
    old_temp_name = binding._temp_name
    assert old_temp_name is not None
    values.pop(old_temp_name)
    (tmp_path / old_temp_name).unlink()
    values[source_name] = displaced
    (tmp_path / source_name).write_bytes(displaced.payload)

    with pytest.raises(PublicationRuntime, match="1175"):
        binding._recover_windows_displaced_restore_failure(
            "novel.md",
            source_name,
            ".novel.md.writer.backup",
            displaced,
            writer,
            WindowsReplaceFailure(ERROR_UNABLE_TO_REMOVE_REPLACED),
        )
    assert values == {"novel.md": competitor, source_name: displaced}
    assert {child.name for child in tmp_path.iterdir()} == {"novel.md", source_name}


def test_windows_replace_failure_1177_preserves_competitor_and_cleans_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _windows_observable(("old", 1), b"old")
    writer = _windows_observable(("writer", 1), b"new")
    competitor = _windows_observable(("competitor", 1), b"competitor")
    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=competitor,
        replacement=writer,
        backup=expected,
    )
    with pytest.raises(PublicationRuntime, match="1177"):
        binding._recover_windows_replace_failure(
            "novel.md",
            ".novel.md.writer.backup",
            expected,
            writer,
            WindowsReplaceFailure(ERROR_UNABLE_TO_MOVE_REPLACEMENT_2),
        )
    assert values == {"novel.md": competitor}
    assert (tmp_path / "novel.md").read_bytes() == b"competitor"
    assert {child.name for child in tmp_path.iterdir()} == {"novel.md"}


def test_windows_replace_failure_1177_preserves_unproven_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _windows_observable(("old", 2), b"old")
    writer = _windows_observable(("writer", 2), b"new")
    unknown_backup = _windows_observable(("unknown", 2), b"unknown")
    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=None,
        replacement=writer,
        backup=unknown_backup,
    )
    with pytest.raises(PublicationRuntime, match="1177"):
        binding._recover_windows_replace_failure(
            "novel.md",
            ".novel.md.writer.backup",
            expected,
            writer,
            WindowsReplaceFailure(ERROR_UNABLE_TO_MOVE_REPLACEMENT_2),
        )
    assert values == {".novel.md.writer.backup": unknown_backup}
    assert not (tmp_path / ".novel.md.writer.tmp").exists()
    assert {child.name for child in tmp_path.iterdir()} == {".novel.md.writer.backup"}


def test_windows_replace_failure_1177_preserves_replacement_with_wrong_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _windows_observable(("old", 3), b"old")
    retained_writer = _windows_observable(("writer", 3), b"new")
    replacement_competitor = _windows_observable(("replacement", 3), b"other")
    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=None,
        replacement=replacement_competitor,
        backup=expected,
    )
    binding._temp_identity = retained_writer.identity
    monkeypatch.setattr(binding, "_windows_info_for_handle", lambda _handle: (0, retained_writer.identity))
    with pytest.raises(PublicationRuntime, match="1177"):
        binding._recover_windows_replace_failure(
            "novel.md",
            ".novel.md.writer.backup",
            expected,
            retained_writer,
            WindowsReplaceFailure(ERROR_UNABLE_TO_MOVE_REPLACEMENT_2),
        )
    assert values == {
        ".novel.md.writer.tmp": replacement_competitor,
        ".novel.md.writer.backup": expected,
    }
    assert {child.name for child in tmp_path.iterdir()} == {
        ".novel.md.writer.tmp",
        ".novel.md.writer.backup",
    }


def test_windows_replace_failure_cleanup_failure_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _windows_observable(("old", 4), b"old")
    writer = _windows_observable(("writer", 4), b"new")
    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=None,
    )
    monkeypatch.setattr(
        binding,
        "_remove_expected_file_anchored",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PublicationRuntime("cleanup")),
    )
    with pytest.raises(PublicationRuntime, match="cleanup"):
        binding._recover_windows_replace_failure(
            "novel.md",
            ".novel.md.writer.backup",
            expected,
            writer,
            WindowsReplaceFailure(ERROR_UNABLE_TO_REMOVE_REPLACED),
        )
    assert values == {"novel.md": expected, ".novel.md.writer.tmp": writer}
    assert {child.name for child in tmp_path.iterdir()} == {"novel.md", ".novel.md.writer.tmp"}


def test_windows_expected_backup_restore_observes_competitors_and_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _windows_observable(("old", 10), b"old")
    writer = _windows_observable(("writer", 10), b"new")
    competitor = _windows_observable(("competitor", 10), b"competitor")

    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=competitor,
        replacement=writer,
        backup=expected,
    )
    binding._restore_windows_expected_backup("novel.md", ".novel.md.writer.backup", expected)
    assert values == {"novel.md": competitor, ".novel.md.writer.tmp": writer}

    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=expected,
    )
    binding._restore_windows_expected_backup("novel.md", ".novel.md.writer.backup", expected)
    assert values == {"novel.md": expected, ".novel.md.writer.tmp": writer}

    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=None,
        replacement=writer,
        backup=expected,
    )

    def conflict_with_competitor(source, _target, _parent_handle):
        source_name = Path(source).name
        values["novel.md"] = competitor
        (tmp_path / "novel.md").write_bytes(competitor.payload)
        raise PublicationConflict("competitor appeared")

    monkeypatch.setattr(publication_module, "_windows_no_replace", conflict_with_competitor)
    binding._restore_windows_expected_backup("novel.md", ".novel.md.writer.backup", expected)
    assert values == {"novel.md": competitor, ".novel.md.writer.tmp": writer}

    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=None,
        replacement=writer,
        backup=expected,
    )
    monkeypatch.setattr(
        publication_module,
        "_windows_no_replace",
        lambda *_args: (_ for _ in ()).throw(PublicationConflict("no target")),
    )
    with pytest.raises(PublicationRuntime, match="could not be restored"):
        binding._restore_windows_expected_backup("novel.md", ".novel.md.writer.backup", expected)
    assert values == {".novel.md.writer.tmp": writer, ".novel.md.writer.backup": expected}


def test_windows_expected_backup_restore_rejects_changed_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _windows_observable(("old", 11), b"old")
    writer = _windows_observable(("writer", 11), b"new")
    wrong = _windows_observable(("wrong", 11), b"wrong")

    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=None,
        replacement=writer,
        backup=expected,
    )

    def restore_wrong(source, target, _parent_handle):
        source_name = Path(source).name
        target_name = Path(target).name
        values.pop(source_name)
        values[target_name] = wrong
        (tmp_path / source_name).unlink()
        (tmp_path / target_name).write_bytes(wrong.payload)

    monkeypatch.setattr(publication_module, "_windows_no_replace", restore_wrong)
    with pytest.raises(PublicationRuntime, match="restored target observable"):
        binding._restore_windows_expected_backup("novel.md", ".novel.md.writer.backup", expected)
    assert values == {"novel.md": wrong, ".novel.md.writer.tmp": writer}

    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=None,
        replacement=writer,
        backup=expected,
    )

    def restore_but_leave_backup(source, target, _parent_handle):
        source_name = Path(source).name
        target_name = Path(target).name
        values[target_name] = values[source_name]
        (tmp_path / target_name).write_bytes(values[target_name].payload)

    monkeypatch.setattr(publication_module, "_windows_no_replace", restore_but_leave_backup)
    with pytest.raises(PublicationRuntime, match="backup was not consumed"):
        binding._restore_windows_expected_backup("novel.md", ".novel.md.writer.backup", expected)
    assert values == {
        "novel.md": expected,
        ".novel.md.writer.tmp": writer,
        ".novel.md.writer.backup": expected,
    }


def test_windows_replace_temp_validation_and_failure_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _windows_observable(("old", 20), b"old")
    writer = _windows_observable(("writer", 20), b"new")

    binding, _values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=None,
    )
    binding._verify_temp = lambda: None  # type: ignore[method-assign]
    with pytest.raises(PublicationRuntime, match="expected target"):
        binding._replace_temp("novel.md", expected_target=None)

    binding._temp_kind = "directory"
    with pytest.raises(PublicationRuntime, match="owned temporary file"):
        binding._replace_temp("novel.md", expected_target=expected)

    binding, values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=None,
    )
    binding._verify_temp = lambda: None  # type: ignore[method-assign]
    wrong_writer = _windows_observable(("wrong", 20), b"wrong")
    values[binding._temp_name] = wrong_writer  # type: ignore[index]
    with pytest.raises(PublicationRuntime, match="identity changed"):
        binding._replace_temp("novel.md", expected_target=expected)

    binding, _values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=None,
    )
    binding._verify_temp = lambda: None  # type: ignore[method-assign]
    monkeypatch.setattr(
        binding,
        "_capture_file_observable_anchored",
        lambda *_args: (_ for _ in ()).throw(OSError("capture")),
    )
    with pytest.raises(PublicationRuntime, match="cannot be inspected"):
        binding._replace_temp("novel.md", expected_target=expected)

    competitor = _windows_observable(("competitor", 20), b"competitor")
    binding, _values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=competitor,
        replacement=writer,
        backup=None,
    )
    binding._verify_temp = lambda: None  # type: ignore[method-assign]
    with pytest.raises(PublicationBoundaryChanged, match="observable changed"):
        binding._replace_temp("novel.md", expected_target=expected)

    binding, _values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=None,
    )
    binding._verify_temp = lambda: None  # type: ignore[method-assign]
    monkeypatch.setattr(
        publication_module,
        "_windows_replace_file",
        lambda *_args: (_ for _ in ()).throw(WindowsReplaceFailure(ERROR_UNABLE_TO_MOVE_REPLACEMENT_2)),
    )
    monkeypatch.setattr(
        binding,
        "_recover_windows_replace_failure",
        lambda *_args: (_ for _ in ()).throw(PublicationRuntime("recovery dispatched")),
    )
    with pytest.raises(PublicationRuntime, match="recovery dispatched"):
        binding._replace_temp("novel.md", expected_target=expected)


@pytest.mark.parametrize("second_result", [False, "raise"])
def test_conditional_replace_second_guard_failure_cleans_displaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    second_result: bool | str,
) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target = tmp_path / "novel.md"
    target.write_bytes(b"old")
    binding = BoundPublicationDirectory.bind(tmp_path)
    expected = binding.capture_file_observable(target.name)

    def exchange(source_name, target_name, source_dir_fd=None, target_dir_fd=None):
        binding._close_temp_fd()
        source = fd_paths[source_dir_fd] / source_name
        target_path = fd_paths[target_dir_fd] / target_name
        displaced = source.with_name(f".exchange-{source.name}")
        os.replace(source, displaced)
        os.replace(target_path, source)
        os.replace(displaced, target_path)

    monkeypatch.setattr(publication_module, "_linux_exchange", exchange)
    calls = 0

    def writer_matches(*_args):
        nonlocal calls
        calls += 1
        if calls == 1:
            return True
        if second_result == "raise":
            raise PublicationRuntime("second guard")
        return False

    monkeypatch.setattr(binding, "_writer_target_matches", writer_matches)
    try:
        expected_error = PublicationRuntime if second_result == "raise" else PublicationBoundaryChanged
        with pytest.raises(expected_error):
            binding.publish_replace(target.name, b"new", expected_target=expected)
        assert target.read_bytes() == b"new"
        assert {child.name for child in tmp_path.iterdir()} == {"novel.md"}
    finally:
        binding.close_safely()


def test_windows_recovery_and_restore_layout_inspection_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _windows_observable(("old", 21), b"old")
    writer = _windows_observable(("writer", 21), b"new")

    binding, _values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=None,
    )
    with monkeypatch.context() as context:
        context.setattr(binding, "_windows_retained_writer_matches", lambda *_args: False)
        with pytest.raises(PublicationRuntime, match="failure layout"):
            binding._recover_windows_replace_failure(
                "novel.md",
                ".novel.md.writer.backup",
                expected,
                writer,
                WindowsReplaceFailure(ERROR_UNABLE_TO_REMOVE_REPLACED),
            )

    binding, _values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=None,
    )
    binding._temp_name = None
    with pytest.raises(PublicationRuntime, match="failure layout"):
        binding._recover_windows_replace_failure(
            "novel.md",
            ".novel.md.writer.backup",
            expected,
            writer,
            WindowsReplaceFailure(ERROR_UNABLE_TO_REMOVE_REPLACED),
        )

    binding, _values = _windows_recovery_fixture(
        tmp_path,
        monkeypatch,
        target=expected,
        replacement=writer,
        backup=None,
    )
    monkeypatch.setattr(
        binding,
        "_capture_optional_file_observable",
        lambda *_args: (_ for _ in ()).throw(OSError("layout")),
    )
    with pytest.raises(PublicationRuntime, match="failure layout"):
        binding._recover_windows_replace_failure(
            "novel.md",
            ".novel.md.writer.backup",
            expected,
            writer,
            WindowsReplaceFailure(ERROR_UNABLE_TO_REMOVE_REPLACED),
        )


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
