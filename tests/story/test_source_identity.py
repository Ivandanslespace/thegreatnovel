from __future__ import annotations

import ctypes
import shutil
from pathlib import Path

import pytest

import tgn.story.publication as publication
import tgn.story.service as service_module
from tgn.story import StoryError, commit_story, init_story, prepare_story

from .conftest import response_for
from .test_service import _choose


def _remove_exact(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def test_prepare_rejects_replaced_temporary_source(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory(name="request-source-replacement")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    original = service_module._publish_request
    replacement: Path | None = None

    def publish_with_replacement(path: Path, payload: bytes, **kwargs):
        nonlocal replacement
        binding = kwargs["parent_binding"]

        def replace_source() -> None:
            nonlocal replacement
            source = binding.temp_path
            assert source is not None
            source.unlink()
            source.write_bytes(b"replacement-source")
            replacement = source

        kwargs["before_atomic"] = replace_source
        return original(path, payload, **kwargs)

    monkeypatch.setattr(service_module, "_publish_request", publish_with_replacement)
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert not (story / "requests" / "turn-000001.json").exists()
    assert not any((story / "turns").iterdir())
    assert replacement is not None and replacement.exists()
    assert replacement.read_bytes() == b"replacement-source"
    _remove_exact(replacement)


def test_commit_rejects_replaced_temporary_source_and_keeps_pending(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory(name="turn-source-replacement")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    campaign_before = service_module.capture_campaign_snapshot(campaign).comparable()
    original = service_module._published_turn
    replacement: Path | None = None

    def publish_with_replacement(path: Path, payload: bytes, **kwargs):
        nonlocal replacement
        binding = kwargs["parent_binding"]

        def replace_source() -> None:
            nonlocal replacement
            source = binding.temp_path
            assert source is not None
            source.unlink()
            source.write_bytes(b"replacement-turn")
            replacement = source

        kwargs["before_atomic"] = replace_source
        return original(path, payload, **kwargs)

    monkeypatch.setattr(service_module, "_published_turn", publish_with_replacement)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert (story / "requests" / "turn-000001.json").exists()
    assert not (story / "turns" / "turn-000001.json").exists()
    assert service_module.capture_campaign_snapshot(campaign).comparable() == campaign_before
    assert replacement is not None and replacement.exists()
    _remove_exact(replacement)


def test_init_rejects_replaced_temporary_story_root(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory(name="story-root-source-replacement")
    original = service_module._publish_directory
    detached: Path | None = None
    replacement: Path | None = None

    def publish_with_replacement(source: Path, target: Path, **kwargs):
        nonlocal detached, replacement
        binding = kwargs["parent_binding"]
        temporary = binding.temp_path
        assert temporary is not None
        detached = temporary.with_name(temporary.name + ".detached")
        temporary.rename(detached)
        temporary.mkdir()
        replacement = temporary
        return original(source, target, **kwargs)

    monkeypatch.setattr(service_module, "_publish_directory", publish_with_replacement)
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert not story.exists()
    assert detached is not None and detached.exists()
    assert replacement is not None and replacement.exists()
    _remove_exact(replacement)
    _remove_exact(detached)


def test_post_move_target_identity_mismatch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "target.json"
    binding = publication.BoundPublicationDirectory.bind(tmp_path)

    def publish_wrong_target(*_args):
        assert binding.temp_name is not None
        source_path = binding.path / binding.temp_name
        target_path = binding.path / target.name
        target_path.write_bytes(b"writer-target")
        source_path.unlink()
        target_path.unlink()
        target_path.write_bytes(b"wrong-target")

    if publication.sys.platform.startswith("win"):
        monkeypatch.setattr(publication, "_windows_no_replace", publish_wrong_target)
    elif publication.sys.platform == "darwin":
        monkeypatch.setattr(publication, "_macos_no_replace", publish_wrong_target)
    else:
        monkeypatch.setattr(publication, "_linux_no_replace", publish_wrong_target)
    try:
        with pytest.raises(publication.PublicationBoundaryChanged):
            publication.publish_bytes_no_replace(target, b"correct-target", parent_binding=binding)
    finally:
        binding.close_safely()
    assert target.read_bytes() == b"wrong-target"


def test_same_bytes_pending_request_replacement_is_not_idempotent(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory(name="same-bytes-request-replacement")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    request_path = story / "requests" / "turn-000001.json"
    original = service_module._published_turn
    replaced = False

    def publish_with_same_bytes_replacement(path: Path, payload: bytes, **kwargs):
        def replace_request() -> None:
            nonlocal replaced
            if replaced:
                return
            request_path.unlink()
            request_path.write_bytes(service_module.canonical_bytes(request))
            replaced = True

        kwargs["before_atomic"] = replace_request
        return original(path, payload, **kwargs)

    monkeypatch.setattr(service_module, "_published_turn", publish_with_same_bytes_replacement)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    assert replaced is True
    assert request_path.exists()
    assert not (story / "turns" / "turn-000001.json").exists()


def test_bound_request_read_identity_and_error_edges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    child = tmp_path / "request.json"
    child.write_bytes(b"payload")
    other = tmp_path / "other.json"
    other.write_bytes(b"other")
    directory = tmp_path / "directory"
    directory.mkdir()
    try:
        assert binding.read_child_bytes(child.name)[0] == b"payload"
        with pytest.raises(publication.PublicationRuntime):
            binding.read_child_bytes(directory.name)

        real_fstat = publication.os.fstat
        monkeypatch.setattr(publication.os, "fstat", lambda _fd: other.stat())
        with pytest.raises(publication.PublicationRuntime):
            binding.read_child_bytes(child.name)
        monkeypatch.setattr(publication.os, "fstat", real_fstat)

        calls = 0
        real_stat_at = binding._stat_at

        def return_other_on_final_read(name: str):
            nonlocal calls
            calls += 1
            return other.stat() if calls == 2 else real_stat_at(name)

        monkeypatch.setattr(binding, "_stat_at", return_other_on_final_read)
        with pytest.raises(publication.PublicationRuntime):
            binding.read_child_bytes(child.name)
        monkeypatch.setattr(binding, "_stat_at", real_stat_at)

        monkeypatch.setattr(publication.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("open")))
        with pytest.raises(publication.PublicationRuntime):
            binding.read_child_bytes(child.name)
    finally:
        binding.close_safely()


class _ChildFakeFunction:
    def __init__(self, result):
        self.result = result
        self.argtypes = None
        self.restype = None

    def __call__(self, *_args):
        return self.result


class _ChildFakeKernel:
    def __init__(self, create_result, info_result, close_result=1):
        self.CreateFileW = _ChildFakeFunction(create_result)
        self.GetFileInformationByHandle = _ChildFakeFunction(info_result)
        self.CloseHandle = _ChildFakeFunction(close_result)


def test_windows_child_handle_and_close_failure_edges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    source = tmp_path / "source"
    source.write_bytes(b"source")
    directory = tmp_path / "directory"
    directory.mkdir()
    try:
        with monkeypatch.context() as context:
            context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: _ChildFakeKernel(ctypes.c_void_p(-1), 1))
            with pytest.raises(publication.PublicationRuntime):
                binding.adopt_existing(source, directory=False)
        with monkeypatch.context() as context:
            context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: _ChildFakeKernel(ctypes.c_void_p(123), 1))
            with pytest.raises(publication.PublicationRuntime):
                binding.adopt_existing(directory, directory=True)
        with monkeypatch.context() as context:
            context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: _ChildFakeKernel(ctypes.c_void_p(123), 0))
            with pytest.raises(publication.PublicationRuntime):
                binding.adopt_existing(source, directory=False)
        with monkeypatch.context() as context:
            context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: _ChildFakeKernel(ctypes.c_void_p(123), 1, close_result=0))
            with pytest.raises(OSError):
                binding._windows_identity_at(source.name, "file")
        binding._temp_handle = 123
        with monkeypatch.context() as context:
            context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: _ChildFakeKernel(ctypes.c_void_p(123), 1, close_result=0))
            with pytest.raises(publication.PublicationRuntime):
                binding._close_temp_handle()
    finally:
        binding.close_safely()


@pytest.mark.parametrize("source_mode", ["same", "different"])
def test_target_identity_mismatch_never_deletes_competing_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_mode: str,
) -> None:
    target = tmp_path / f"target-{source_mode}.json"
    binding = publication.BoundPublicationDirectory.bind(tmp_path)

    def publish_wrong_target(*_args) -> None:
        assert binding.temp_name is not None
        source = binding.path / binding.temp_name
        if source_mode == "different":
            source.unlink()
            source.write_bytes(b"replacement-source")
        (binding.path / target.name).write_bytes(b"wrong-target")

    if publication.sys.platform.startswith("win"):
        monkeypatch.setattr(publication, "_windows_no_replace", publish_wrong_target)
    elif publication.sys.platform == "darwin":
        monkeypatch.setattr(publication, "_macos_no_replace", publish_wrong_target)
    else:
        monkeypatch.setattr(publication, "_linux_no_replace", publish_wrong_target)
    try:
        with pytest.raises(publication.PublicationRuntime if source_mode == "different" else publication.PublicationBoundaryChanged):
            publication.publish_bytes_no_replace(target, b"correct-target", parent_binding=binding)
        assert target.exists()
    finally:
        binding.close_safely()
        _remove_exact(target)
        for item in tmp_path.iterdir():
            if item.name.startswith(".target-"):
                _remove_exact(item)


def test_publication_post_move_parent_and_source_error_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    target = tmp_path / "target.json"

    def primitive_failure(*_args):
        raise OSError("primitive failure")

    if publication.sys.platform.startswith("win"):
        monkeypatch.setattr(publication, "_windows_no_replace", primitive_failure)
    elif publication.sys.platform == "darwin":
        monkeypatch.setattr(publication, "_macos_no_replace", primitive_failure)
    else:
        monkeypatch.setattr(publication, "_linux_no_replace", primitive_failure)
    try:
        with pytest.raises(publication.PublicationRuntime):
            publication.publish_bytes_no_replace(target, b"payload", parent_binding=binding)
    finally:
        binding.close_safely()


def test_post_commit_handle_close_failure_does_not_reverse_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    monkeypatch.setattr(binding, "_close_temp_handle", lambda: (_ for _ in ()).throw(publication.PublicationRuntime("close")))
    binding.publish_bytes("handle-close.json", b"payload")
    assert (tmp_path / "handle-close.json").read_bytes() == b"payload"
    assert binding.temp_name is None
    binding.close_safely()
