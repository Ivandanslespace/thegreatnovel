from __future__ import annotations

import errno
from pathlib import Path

import pytest

import tgn.story.publication as publication
from tgn.story.publication import (
    PublicationConflict,
    PublicationRuntime,
    PublicationUnavailable,
    atomic_no_replace_move,
    publish_bytes_no_replace,
)


def test_publication_success_conflict_and_invalid_targets(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.write_bytes(b"payload")
    atomic_no_replace_move(source, target, directory=False)
    assert target.read_bytes() == b"payload"
    with pytest.raises(PublicationConflict):
        publish_bytes_no_replace(target, b"different")
    source_conflict = tmp_path / "source-conflict"
    source_conflict.write_bytes(b"payload")
    with pytest.raises(PublicationConflict):
        atomic_no_replace_move(source_conflict, target, directory=False)

    directory_source = tmp_path / "directory-source"
    directory_target = tmp_path / "directory-target"
    directory_source.mkdir()
    (directory_source / "value").write_text("ok", encoding="utf-8")
    atomic_no_replace_move(directory_source, directory_target, directory=True)
    assert (directory_target / "value").read_text(encoding="utf-8") == "ok"

    with pytest.raises(PublicationRuntime):
        atomic_no_replace_move(tmp_path / "missing", tmp_path / "missing-target", directory=False)
    with pytest.raises(PublicationRuntime):
        atomic_no_replace_move(directory_target, tmp_path / "bad-file-target", directory=False)
    bad_parent = tmp_path / "parent-file"
    bad_parent.write_text("not a directory", encoding="utf-8")
    with pytest.raises(PublicationRuntime):
        atomic_no_replace_move(target, bad_parent / "child", directory=False)


def test_publication_capability_and_runtime_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"payload")
    target = tmp_path / "target"

    monkeypatch.setattr(publication.sys, "platform", "freebsd")
    with pytest.raises(PublicationUnavailable):
        atomic_no_replace_move(source, target, directory=False)

    monkeypatch.setattr(publication.sys, "platform", "win32")
    monkeypatch.setattr(publication, "_windows_no_replace", lambda *_args: (_ for _ in ()).throw(PublicationUnavailable("no")))
    with pytest.raises(PublicationUnavailable):
        atomic_no_replace_move(source, target, directory=False)
    monkeypatch.setattr(publication, "_windows_no_replace", lambda *_args: (_ for _ in ()).throw(PublicationRuntime("bad")))
    with pytest.raises(PublicationRuntime):
        atomic_no_replace_move(source, target, directory=False)


class _FakeFunction:
    def __init__(self, result: int):
        self.result = result
        self.argtypes = None
        self.restype = None

    def __call__(self, *_args):
        return self.result


class _FakeKernel:
    def __init__(self, result: int):
        self.MoveFileExW = _FakeFunction(result)


class _FakeLib:
    def __init__(self, name: str, result: int):
        setattr(self, name, _FakeFunction(result))


@pytest.mark.parametrize("error_number", [183, 1, 50, 120, 5])
def test_windows_primitive_maps_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_number: int) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.write_bytes(b"payload")
    monkeypatch.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: _FakeKernel(0))
    monkeypatch.setattr(publication.ctypes, "get_last_error", lambda: error_number)
    expected = PublicationConflict if error_number == 183 else PublicationUnavailable if error_number in {1, 50, 120} else PublicationRuntime
    with pytest.raises(expected):
        publication._windows_no_replace(source, target)


@pytest.mark.parametrize("result,error_number,expected", [
    (0, 0, None),
    (-1, errno.EEXIST, PublicationConflict),
    (-1, errno.ENOSYS, PublicationUnavailable),
    (-1, errno.EIO, PublicationRuntime),
])
def test_linux_primitive_mapping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, result: int, error_number: int, expected) -> None:
    fake = _FakeLib("renameat2", result)
    monkeypatch.setattr(publication.ctypes, "CDLL", lambda *_args, **_kwargs: fake)
    monkeypatch.setattr(publication.ctypes, "get_errno", lambda: error_number)
    if expected is None:
        publication._linux_no_replace(tmp_path / "source", tmp_path / "target")
    else:
        with pytest.raises(expected):
            publication._linux_no_replace(tmp_path / "source", tmp_path / "target")


@pytest.mark.parametrize("result,error_number,expected", [
    (0, 0, None),
    (-1, errno.EEXIST, PublicationConflict),
    (-1, errno.EOPNOTSUPP, PublicationUnavailable),
    (-1, errno.EIO, PublicationRuntime),
])
def test_macos_primitive_mapping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, result: int, error_number: int, expected) -> None:
    fake = _FakeLib("renameatx_np", result)
    monkeypatch.setattr(publication.ctypes, "CDLL", lambda *_args, **_kwargs: fake)
    monkeypatch.setattr(publication.ctypes, "get_errno", lambda: error_number)
    if expected is None:
        publication._macos_no_replace(tmp_path / "source", tmp_path / "target")
    else:
        with pytest.raises(expected):
            publication._macos_no_replace(tmp_path / "source", tmp_path / "target")


def test_publication_cleanup_and_failure_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file_path = tmp_path / "owned.tmp"
    file_path.write_bytes(b"x")
    publication._cleanup_owned(file_path)
    assert not file_path.exists()
    directory = tmp_path / "owned-dir"
    directory.mkdir()
    (directory / "x").write_bytes(b"x")
    publication._cleanup_owned(directory)
    assert not directory.exists()
    publication._cleanup_owned(None)

    target = tmp_path / "target.json"
    monkeypatch.setattr(publication, "atomic_no_replace_move", lambda *_args, **_kwargs: (_ for _ in ()).throw(PublicationRuntime("bad")))
    with pytest.raises(PublicationRuntime):
        publish_bytes_no_replace(target, b"payload")
    assert not target.exists()


def test_publication_loader_and_cleanup_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"payload")
    target = tmp_path / "target"
    monkeypatch.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")))
    with pytest.raises(PublicationUnavailable):
        publication._windows_no_replace(source, target)
    monkeypatch.setattr(publication.ctypes, "CDLL", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")))
    with pytest.raises(PublicationUnavailable):
        publication._linux_no_replace(source, target)
    with pytest.raises(PublicationUnavailable):
        publication._macos_no_replace(source, target)

    monkeypatch.setattr(publication, "_windows_no_replace", lambda *_args: (_ for _ in ()).throw(OSError("runtime")))
    with pytest.raises(PublicationRuntime):
        publication.atomic_no_replace_move(source, target, directory=False)

    original_lstat = publication.os.lstat
    monkeypatch.setattr(publication.os, "lstat", lambda path: (_ for _ in ()).throw(OSError("parent")) if Path(path) == target.parent else original_lstat(path))
    with pytest.raises(PublicationRuntime):
        publication.atomic_no_replace_move(source, target, directory=False)

    with pytest.raises(PublicationRuntime):
        publish_bytes_no_replace(target, "not-bytes")
    monkeypatch.setattr(publication.tempfile, "mkstemp", lambda **_kwargs: (999_999, str(tmp_path / "never-created.tmp")))
    with pytest.raises(PublicationRuntime):
        publish_bytes_no_replace(target, b"payload")

    owned = tmp_path / "owned-dir"
    owned.mkdir()
    monkeypatch.setattr(publication.shutil if hasattr(publication, "shutil") else __import__("shutil"), "rmtree", lambda *_args: (_ for _ in ()).throw(OSError("cleanup")))
    with pytest.raises(PublicationRuntime):
        publication._cleanup_owned(owned)

    link_target = tmp_path / "link-target"
    link_target.write_bytes(b"x")
    link = tmp_path / "owned-link"
    try:
        link.symlink_to(link_target)
    except (OSError, NotImplementedError):
        return
    with pytest.raises(PublicationRuntime):
        publication._cleanup_owned(link)


def test_publication_platform_dispatch_and_missing_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.write_bytes(b"payload")
    monkeypatch.setattr(publication, "_linux_no_replace", lambda *_args: None)
    monkeypatch.setattr(publication.sys, "platform", "linux")
    publication.atomic_no_replace_move(source, target, directory=False)

    source2 = tmp_path / "source2"
    target2 = tmp_path / "target2"
    source2.write_bytes(b"payload")
    monkeypatch.setattr(publication, "_macos_no_replace", lambda *_args: None)
    monkeypatch.setattr(publication.sys, "platform", "darwin")
    publication.atomic_no_replace_move(source2, target2, directory=False)

    missing = tmp_path / "missing-owned"
    original_lstat = publication.os.lstat
    monkeypatch.setattr(publication.os, "lstat", lambda *_args: (_ for _ in ()).throw(FileNotFoundError()))
    publication._cleanup_owned(missing)
    monkeypatch.setattr(publication.os, "lstat", original_lstat)
