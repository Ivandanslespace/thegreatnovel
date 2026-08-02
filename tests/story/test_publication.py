from __future__ import annotations

import ctypes
import errno
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import tgn.story.publication as publication
from tgn.story.publication import (
    ExpectedPublicationFile,
    PublicationBoundaryChanged,
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
    (-1, errno.ENOSYS, PublicationUnavailable),
    (-1, errno.EIO, PublicationRuntime),
])
def test_linux_exchange_primitive_mapping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, result: int, error_number: int, expected) -> None:
    fake = _FakeLib("renameat2", result)
    monkeypatch.setattr(publication.ctypes, "CDLL", lambda *_args, **_kwargs: fake)
    monkeypatch.setattr(publication.ctypes, "get_errno", lambda: error_number)
    if expected is None:
        publication._linux_exchange(tmp_path / "source", tmp_path / "target")
    else:
        with pytest.raises(expected):
            publication._linux_exchange(tmp_path / "source", tmp_path / "target")


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


@pytest.mark.parametrize("result,error_number,expected", [
    (0, 0, None),
    (-1, errno.EOPNOTSUPP, PublicationUnavailable),
    (-1, errno.EIO, PublicationRuntime),
])
def test_macos_exchange_primitive_mapping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, result: int, error_number: int, expected) -> None:
    fake = _FakeLib("renameatx_np", result)
    monkeypatch.setattr(publication.ctypes, "CDLL", lambda *_args, **_kwargs: fake)
    monkeypatch.setattr(publication.ctypes, "get_errno", lambda: error_number)
    if expected is None:
        publication._macos_exchange(tmp_path / "source", tmp_path / "target")
    else:
        with pytest.raises(expected):
            publication._macos_exchange(tmp_path / "source", tmp_path / "target")


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
    monkeypatch.setattr(publication, "_windows_no_replace", lambda *_args: (_ for _ in ()).throw(PublicationRuntime("bad")))
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
        publication._linux_exchange(source, target)
    with pytest.raises(PublicationUnavailable):
        publication._macos_no_replace(source, target)
    with pytest.raises(PublicationUnavailable):
        publication._macos_exchange(source, target)

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
    monkeypatch.setattr(publication, "_linux_no_replace", lambda *_args: os.replace(source, target))
    monkeypatch.setattr(publication.sys, "platform", "linux")
    publication.atomic_no_replace_move(source, target, directory=False)

    source2 = tmp_path / "source2"
    target2 = tmp_path / "target2"
    source2.write_bytes(b"payload")
    monkeypatch.setattr(publication, "_macos_no_replace", lambda *_args: os.replace(source2, target2))
    monkeypatch.setattr(publication.sys, "platform", "darwin")
    publication.atomic_no_replace_move(source2, target2, directory=False)

    missing = tmp_path / "missing-owned"
    original_lstat = publication.os.lstat
    monkeypatch.setattr(publication.os, "lstat", lambda *_args: (_ for _ in ()).throw(FileNotFoundError()))
    publication._cleanup_owned(missing)
    monkeypatch.setattr(publication.os, "lstat", original_lstat)


def _fake_posix_dirfd_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[int, Path]:
    """Exercise the POSIX dirfd path on the Windows test host with real files."""

    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    real_stat = os.stat
    real_mkdir = os.mkdir
    real_unlink = os.unlink
    real_rmdir = os.rmdir
    real_scandir = os.scandir
    fd_paths: dict[int, Path] = {17: tmp_path}

    class PosixOSProxy:
        name = "posix"
        O_DIRECTORY = 0x10000000
        O_NOFOLLOW = 0x20000000

        def __getattr__(self, name):
            return getattr(os, name)

    proxy = PosixOSProxy()
    monkeypatch.setattr(publication, "os", proxy)

    class LinuxSysProxy:
        platform = "linux"

        def __getattr__(self, name):
            return getattr(__import__("sys"), name)

    monkeypatch.setattr(publication, "sys", LinuxSysProxy())

    def actual_path(value, dir_fd):
        if dir_fd is None:
            return Path(value)
        return fd_paths[dir_fd] / os.fspath(value)

    def fake_open(value, flags, mode=0o777, *, dir_fd=None, **kwargs):
        if dir_fd is None and Path(value) == tmp_path and not (flags & os.O_WRONLY):
            return 17
        path = actual_path(value, dir_fd)
        if path.is_dir() and flags & PosixOSProxy.O_DIRECTORY:
            synthetic = max(fd_paths, default=17) + 1
            fd_paths[synthetic] = path
            return synthetic
        portable_flags = flags & ~(PosixOSProxy.O_DIRECTORY | PosixOSProxy.O_NOFOLLOW)
        fd = real_open(path, portable_flags, mode, **kwargs)
        if path.is_dir():
            fd_paths[fd] = path
        return fd

    def fake_close(fd):
        if fd == 17 or fd in fd_paths:
            fd_paths.pop(fd, None) if fd != 17 else None
            return
        return real_close(fd)

    def fake_fstat(fd):
        if fd in fd_paths:
            return real_stat(fd_paths[fd])
        return real_fstat(fd)

    def fake_stat(value, *args, dir_fd=None, follow_symlinks=True, **kwargs):
        return real_stat(actual_path(value, dir_fd), *args, follow_symlinks=follow_symlinks, **kwargs)

    def fake_mkdir(value, mode=0o777, *, dir_fd=None):
        return real_mkdir(actual_path(value, dir_fd), mode)

    def fake_unlink(value, *, dir_fd=None):
        return real_unlink(actual_path(value, dir_fd))

    def fake_rmdir(value, *, dir_fd=None):
        return real_rmdir(actual_path(value, dir_fd))

    def fake_scandir(value):
        if isinstance(value, int):
            value = fd_paths[value]
        return real_scandir(value)

    monkeypatch.setattr(publication.os, "open", fake_open)
    monkeypatch.setattr(publication.os, "close", fake_close)
    monkeypatch.setattr(publication.os, "fstat", fake_fstat)
    monkeypatch.setattr(publication.os, "stat", fake_stat)
    monkeypatch.setattr(publication.os, "mkdir", fake_mkdir)
    monkeypatch.setattr(publication.os, "unlink", fake_unlink)
    monkeypatch.setattr(publication.os, "rmdir", fake_rmdir)
    monkeypatch.setattr(publication.os, "scandir", fake_scandir)
    return fd_paths


def test_anchored_posix_adopted_file_and_bound_child_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    source = tmp_path / "adopted-source"
    source.write_bytes(b"payload")
    try:
        assert binding.read_child_bytes(source.name)[0] == b"payload"
        with pytest.raises(FileNotFoundError):
            binding.read_child_bytes("missing-child")
        directory = tmp_path / "not-file"
        directory.mkdir()
        with pytest.raises(PublicationRuntime):
            binding.read_child_bytes(directory.name)

        real_open = publication.os.open
        monkeypatch.setattr(publication.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("open")))
        with pytest.raises(PublicationRuntime):
            binding.read_child_bytes(source.name)
        monkeypatch.setattr(publication.os, "open", real_open)

        def move_file(source_name, target_name, source_fd, target_fd):
            binding._close_temp_fd()
            os.replace(fd_paths[source_fd] / source_name, fd_paths[target_fd] / target_name)

        monkeypatch.setattr(publication, "_linux_no_replace", move_file)
        binding.adopt_existing(source, directory=False, owned=True)
        binding.publish_adopted("adopted-target")
        assert (tmp_path / "adopted-target").read_bytes() == b"payload"
    finally:
        binding.close_safely()


def test_anchored_posix_file_publication_and_detached_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    def move_file(source, target, source_fd, target_fd):
        binding._close_temp_fd()
        os.replace(fd_paths[source_fd] / source, fd_paths[target_fd] / target)

    monkeypatch.setattr(publication, "_linux_no_replace", move_file)
    binding.publish_bytes("target.json", b"payload")
    assert (tmp_path / "target.json").read_bytes() == b"payload"
    binding.close()

    detached = tmp_path.with_name(f"{tmp_path.name}-detached")
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    binding.create_temp_file("later.json")
    binding._close_temp_fd()
    tmp_path.rename(detached)
    tmp_path.mkdir()
    fd_paths[17] = detached
    binding.cleanup_temp()
    assert not list(detached.glob("*.tmp"))
    binding.close()


def test_conditional_publication_observable_and_cleanup_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    child = tmp_path / "child.json"
    child.write_bytes(b"child")
    expected = binding.capture_file_observable(child.name)
    directory = tmp_path / "directory"
    directory.mkdir()
    try:
        with pytest.raises(PublicationRuntime):
            binding.child_identity("child.json", "invalid")
        with pytest.raises(PublicationRuntime):
            binding.child_identity("directory", "file")
        with pytest.raises(FileNotFoundError):
            binding.child_identity("missing", "file")

        with pytest.raises(PublicationRuntime):
            binding.read_child_bytes(directory.name)
        with pytest.raises(FileNotFoundError):
            binding.capture_file_observable("missing")
        with monkeypatch.context() as context:
            context.setattr(binding, "_capture_file_observable_anchored", lambda *_args: (_ for _ in ()).throw(OSError("capture")))
            with pytest.raises(PublicationRuntime):
                binding.capture_file_observable(child.name)
        with monkeypatch.context() as context:
            context.setattr(binding, "_stat_at", lambda *_args: (_ for _ in ()).throw(OSError("stat")))
            with pytest.raises(PublicationRuntime):
                binding.child_identity(child.name, "file")

        invalid_expected = ExpectedPublicationFile(
            identity=expected.identity,
            sha256=publication.sha256_bytes(b"other"),
            size=5,
            mtime_ns=expected.mtime_ns,
            payload=b"other",
        )
        with pytest.raises(PublicationBoundaryChanged):
            binding._remove_expected_file_anchored(child.name, invalid_expected)
        with monkeypatch.context() as context:
            context.setattr(publication.os, "unlink", lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()))
            with pytest.raises(PublicationBoundaryChanged):
                binding._remove_expected_file_anchored(child.name, expected)
        with monkeypatch.context() as context:
            context.setattr(publication.os, "unlink", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("unlink")))
            with pytest.raises(PublicationRuntime):
                binding._remove_expected_file_anchored(child.name, expected)

        no_fd = publication.BoundPublicationDirectory(tmp_path)
        with pytest.raises(PublicationUnavailable):
            no_fd._exchange_names("source", "target")
        monkeypatch.setattr(publication.sys, "platform", "darwin")
        monkeypatch.setattr(publication, "_macos_exchange", lambda *_args: None)
        binding._exchange_names("source", "target")
        monkeypatch.setattr(publication.sys, "platform", "linux")

        with monkeypatch.context() as context:
            context.setattr(publication.os, "name", "posix")
            binding._open_windows_temp_handle()
        temp = binding.create_temp_file("edge.json")
        with monkeypatch.context() as context:
            context.setattr(publication.os, "fstat", lambda *_args: os.stat(tmp_path))
            with pytest.raises(PublicationRuntime):
                binding._verify_temp()
        binding.cleanup_temp()

        writer = ExpectedPublicationFile(
            identity=("writer", 1),
            sha256=publication.sha256_bytes(b"writer"),
            size=6,
            mtime_ns=1,
            payload=b"writer",
        )
        displaced = ExpectedPublicationFile(
            identity=("old", 1),
            sha256=publication.sha256_bytes(b"old"),
            size=3,
            mtime_ns=1,
            payload=b"old",
        )
        values = {"target": writer, "backup": displaced, "cleanup": writer}
        removed: list[str] = []
        with monkeypatch.context() as context:
            context.setattr(publication.os, "name", "nt")
            context.setattr(binding, "_writer_target_matches", lambda *_args: True)
            context.setattr(binding, "_next_displaced_name", lambda *_args: "cleanup")
            context.setattr(binding, "_capture_file_observable_anchored", lambda name: values[name])
            context.setattr(binding, "_remove_expected_file_anchored", lambda name, _value: removed.append(name))
            def fake_windows_replace(*_args):
                values["target"] = displaced
                values["cleanup"] = writer
            context.setattr(publication, "_windows_replace_file", fake_windows_replace)
            binding._restore_displaced_after_exchange("target", "backup", displaced, writer)
        assert removed == ["cleanup"]
    finally:
        binding.close_safely()


def test_anchored_posix_directory_cleanup_and_final_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    temporary = binding.create_temp_directory("story")
    (temporary / "nested").mkdir()
    (temporary / "nested" / "value").write_bytes(b"x")
    detached = tmp_path.with_name(f"{tmp_path.name}-directory-detached")
    tmp_path.rename(detached)
    tmp_path.mkdir()
    fd_paths[17] = detached
    binding.cleanup_temp()
    assert not any(detached.iterdir())
    assert tmp_path.exists()
    binding.close()


def test_anchored_posix_post_move_parent_change_removes_only_published_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    detached = tmp_path.with_name(f"{tmp_path.name}-post-move-detached")

    def move_and_replace_parent(source, target, source_fd, target_fd):
        binding._close_temp_fd()
        os.replace(fd_paths[source_fd] / source, fd_paths[target_fd] / target)
        tmp_path.rename(detached)
        tmp_path.mkdir()
        fd_paths[17] = detached

    monkeypatch.setattr(publication, "_linux_no_replace", move_and_replace_parent)
    try:
        with pytest.raises(PublicationBoundaryChanged):
            binding.publish_bytes("post-move.json", b"payload")
        assert not (detached / "post-move.json").exists()
        assert not (tmp_path / "post-move.json").exists()
    finally:
        binding.close_safely()
        if detached.exists():
            shutil.rmtree(detached)

    fd_paths[17] = tmp_path
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    detached_final = tmp_path.with_name(f"{tmp_path.name}-final-detached")

    def replace_parent_after_guard():
        binding._close_temp_fd()
        tmp_path.rename(detached_final)
        tmp_path.mkdir()
        fd_paths[17] = detached_final

    with pytest.raises(PublicationBoundaryChanged):
        binding.publish_bytes("window.json", b"x", before_atomic=replace_parent_after_guard)
    assert not (detached_final / "window.json").exists()
    assert not list(detached_final.glob("*.tmp"))
    binding.close()


def test_posix_parent_binding_rejects_open_and_identity_races(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    other = tmp_path.with_name(f"{tmp_path.name}-other")
    other.mkdir()
    real_fstat = publication.os.fstat
    with monkeypatch.context() as context:
        context.setattr(publication.os, "fstat", lambda fd: os.stat(other) if fd == 17 else real_fstat(fd))
        with pytest.raises(PublicationRuntime):
            publication.BoundPublicationDirectory.bind(tmp_path)
    with monkeypatch.context() as context:
        context.setattr(publication.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("open")))
        with pytest.raises(PublicationRuntime):
            publication.BoundPublicationDirectory.bind(tmp_path)


def test_publication_handle_and_temporary_error_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Kernel:
        def __init__(self, create_result, info_result):
            self.CreateFileW = _FakeFunction(create_result)
            self.GetFileInformationByHandle = _FakeFunction(info_result)
            self.CloseHandle = _FakeFunction(1)

    with monkeypatch.context() as context:
        context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: Kernel(ctypes.c_void_p(-1), 1))
        with pytest.raises(PublicationRuntime):
            publication.BoundPublicationDirectory.bind(tmp_path)
    with monkeypatch.context() as context:
        context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: Kernel(ctypes.c_void_p(123), 1))
        with pytest.raises(PublicationRuntime):
            publication.BoundPublicationDirectory.bind(tmp_path)
    with monkeypatch.context() as context:
        context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: Kernel(ctypes.c_void_p(123), 0))
        binding = publication.BoundPublicationDirectory(tmp_path)
        binding.directory_handle = 123
        with pytest.raises(PublicationRuntime):
            binding._windows_info()
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    with monkeypatch.context() as context:
        context.setattr(binding, "_windows_info", lambda: (binding._FILE_ATTRIBUTE_REPARSE_POINT, binding._handle_identity))
        with pytest.raises(PublicationBoundaryChanged):
            binding.check()
    binding.close()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    assert binding.temp_path is None
    assert binding._exists_at("missing") is False
    with monkeypatch.context() as context:
        context.setattr(publication.os, "lstat", lambda *_args: (_ for _ in ()).throw(PermissionError("read")))
        with pytest.raises(PublicationRuntime):
            binding._stat_at("child")
    with monkeypatch.context() as context:
        context.setattr(binding, "_stat_at", lambda *_args: (_ for _ in ()).throw(PublicationRuntime("bad")))
        with pytest.raises(PublicationRuntime):
            binding._exists_at("child")
    binding.close()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    with pytest.raises(PublicationRuntime):
        binding._register_temp("missing", kind="file", fd=None)
    invalid = tmp_path / "invalid-source"
    invalid.write_bytes(b"x")
    with pytest.raises(PublicationRuntime):
        binding._register_temp(invalid.name, kind="directory", fd=None)
    binding._temp_name = None
    binding._temp_kind = None
    binding._temp_identity = None
    with monkeypatch.context() as context:
        context.setattr(publication.tempfile, "mkstemp", lambda **_kwargs: (_ for _ in ()).throw(PermissionError("create")))
        with pytest.raises(PublicationRuntime):
            binding.create_temp_file("target")
    with monkeypatch.context() as context:
        context.setattr(publication.tempfile, "mkdtemp", lambda **_kwargs: (_ for _ in ()).throw(PermissionError("create")))
        with pytest.raises(PublicationRuntime):
            binding.create_temp_directory("target")
    binding.close()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    with pytest.raises(PublicationRuntime):
        binding.write_temp_bytes(b"payload")
    binding.create_temp_file("target")
    binding._close_temp_fd()
    binding.write_temp_bytes(b"payload")
    binding.cleanup_temp()
    binding.create_temp_file("mismatch")
    with monkeypatch.context() as context:
        context.setattr(publication, "read_regular_file", lambda *_args: (b"different", None))
        with pytest.raises(PublicationRuntime):
            binding.write_temp_bytes(b"payload")
    binding.cleanup_temp()
    binding.create_temp_file("identity")
    binding._close_temp_fd()
    binding._temp_identity = ("different",)
    with pytest.raises(PublicationRuntime):
        binding._verify_temp()
    binding._temp_name = None
    binding._temp_kind = None
    binding._temp_identity = None
    binding.close()


def test_publication_cleanup_and_close_failure_mappings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    source = tmp_path / "source"
    source.write_bytes(b"x")
    with pytest.raises(PublicationRuntime):
        binding._remove_owned_name(source.name, ("different",), directory=False)
    binding.close()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    binding.create_temp_file("close")
    with monkeypatch.context() as context:
        context.setattr(binding, "_close_temp_fd", lambda: (_ for _ in ()).throw(PublicationRuntime("close")))
        with pytest.raises(PublicationRuntime):
            binding.close()
    binding.close_safely()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    with monkeypatch.context() as context:
        context.setattr(binding, "cleanup_temp", lambda: (_ for _ in ()).throw(PublicationRuntime("cleanup")))
        with pytest.raises(PublicationRuntime):
            binding.publish_bytes("target", b"x", boundary_check=lambda: (_ for _ in ()).throw(PublicationRuntime("guard")))
    binding.close_safely()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    source = tmp_path / "adopted"
    source.write_bytes(b"x")
    binding.adopt_existing(source, directory=False, owned=True)
    with monkeypatch.context() as context:
        context.setattr(binding, "cleanup_temp", lambda: (_ for _ in ()).throw(PublicationRuntime("cleanup")))
        with pytest.raises(PublicationRuntime):
            binding.publish_adopted("target", before_atomic=lambda: (_ for _ in ()).throw(PublicationRuntime("guard")))
    binding.close_safely()
def test_publication_binding_validation_and_handle_failure_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(PublicationRuntime):
        publication.BoundPublicationDirectory.bind(tmp_path / "missing")
    file_path = tmp_path / "file"
    file_path.write_bytes(b"x")
    with pytest.raises(PublicationRuntime):
        publication.BoundPublicationDirectory.bind(file_path)
    with pytest.raises(PublicationRuntime):
        publication._ensure_name("nested/name")
    with pytest.raises(PublicationRuntime):
        publication._ensure_source(file_path, directory=True)
    with pytest.raises(PublicationRuntime):
        publication._ensure_source(tmp_path / "missing", directory=False)

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    monkeypatch.setattr(binding, "_windows_info", lambda: (binding._FILE_ATTRIBUTE_DIRECTORY, ("windows", 1, 2, 3)))
    with pytest.raises(PublicationBoundaryChanged):
        binding.check()
    binding.close()

    real_windll = publication.ctypes.WinDLL

    class FailingKernel:
        def __init__(self):
            self.CreateFileW = _FakeFunction(ctypes.c_void_p(-1))

    monkeypatch.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: FailingKernel())
    with pytest.raises(PublicationRuntime):
        publication.BoundPublicationDirectory.bind(tmp_path)
    monkeypatch.setattr(publication.ctypes, "WinDLL", real_windll)

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    binding._temp_name = "missing.tmp"
    binding._temp_kind = "file"
    binding._temp_identity = None
    with pytest.raises(PublicationRuntime):
        binding.cleanup_temp()
    binding.close()


def test_publication_remaining_error_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert publication._stat_identity(SimpleNamespace(st_dev=0, st_ino=0, st_mode=0)) == (
        "fallback",
        0,
        0,
        0,
    )

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    assert binding._next_temp_name("target").startswith(".target.")
    with pytest.raises(PublicationRuntime):
        binding._next_temp_name("nested/name")
    with pytest.raises(PublicationRuntime):
        publication.BoundPublicationDirectory(tmp_path)._windows_info()
    binding.close()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    monkeypatch.setattr(binding, "_windows_info", lambda: (binding._FILE_ATTRIBUTE_REPARSE_POINT, binding._handle_identity))
    with pytest.raises(PublicationBoundaryChanged):
        binding.check()
    binding.close()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    with pytest.raises(PublicationRuntime):
        binding.write_temp_bytes(b"payload")
    with pytest.raises(PublicationRuntime):
        binding._verify_temp()
    with pytest.raises(PublicationRuntime):
        binding.adopt_existing(tmp_path / "other" / "source", directory=False)
    binding.close()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    with monkeypatch.context() as context:
        context.setattr(publication.tempfile, "mkstemp", lambda **_kwargs: (_ for _ in ()).throw(FileExistsError()))
        with pytest.raises(PublicationRuntime):
            binding.create_temp_file("target")
    binding.close()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    temporary = binding.create_temp_file("target")
    binding._close_temp_fd()
    with pytest.raises(PublicationRuntime):
        binding.write_temp_bytes("not-bytes")
    monkeypatch.setattr(binding, "_stat_at", lambda *_args: (_ for _ in ()).throw(PermissionError("denied")))
    with pytest.raises(PublicationRuntime):
        binding._verify_temp()
    binding.close_safely()
    if temporary.exists():
        publication._cleanup_owned(temporary)

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    source = tmp_path / "source"
    source.write_bytes(b"x")
    with pytest.raises(PublicationRuntime):
        binding.publish_bytes("target", b"x", before_atomic=lambda: (_ for _ in ()).throw(PublicationRuntime("hook")))
    binding.close()


def test_publication_anchor_identity_and_owned_type_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    binding.directory_handle = None
    with pytest.raises(PublicationRuntime):
        binding._windows_info()
    binding.close_safely()


def test_publication_additional_identity_and_cleanup_error_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    real_lstat = publication.os.lstat
    with monkeypatch.context() as context:
        context.setattr(publication.os, "lstat", lambda *_args: (_ for _ in ()).throw(OSError("path")))
        with pytest.raises(PublicationBoundaryChanged):
            binding._capture_path_identity()
    with monkeypatch.context() as context:
        context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: (_ for _ in ()).throw(PublicationRuntime("info")))
        with pytest.raises(PublicationRuntime):
            binding._windows_info_for_handle(123)
    binding._temp_name = "temporary"
    binding._temp_kind = None
    with pytest.raises(PublicationRuntime):
        binding._open_windows_temp_handle()
    binding._temp_name = None
    binding._temp_kind = None
    binding.close_safely()
    monkeypatch.setattr(publication.os, "lstat", real_lstat)

    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    posix_binding = publication.BoundPublicationDirectory.bind(tmp_path)
    other = tmp_path.with_name(f"{tmp_path.name}-other-for-matrix")
    other.mkdir()
    with monkeypatch.context() as context:
        context.setattr(publication.os, "fstat", lambda fd: os.stat(other) if fd == 17 else os.fstat(fd))
        with pytest.raises(PublicationBoundaryChanged):
            posix_binding._check_handle()

    with monkeypatch.context() as context:
        context.setattr(publication.os, "mkdir", lambda *_args, **_kwargs: (_ for _ in ()).throw(FileExistsError()))
        with pytest.raises(PublicationRuntime):
            posix_binding.create_temp_directory("collision")

    source = tmp_path / "matrix-source"
    source.write_bytes(b"x")
    with monkeypatch.context() as context:
        context.setattr(publication.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("anchor")))
        with pytest.raises(PublicationRuntime):
            posix_binding.adopt_existing(source, directory=False)
    with monkeypatch.context() as context:
        context.setattr(posix_binding, "_stat_at", lambda *_args: (_ for _ in ()).throw(PublicationRuntime("inspect")))
        with pytest.raises(PublicationRuntime):
            posix_binding.adopt_existing(source, directory=False)

    source_directory = tmp_path / "matrix-directory"
    source_directory.mkdir()
    posix_binding.adopt_existing(source_directory, directory=True, owned=True)
    posix_binding.cleanup_temp()
    posix_binding.create_temp_file("verify")
    posix_binding._close_temp_fd()
    with pytest.raises(PublicationRuntime):
        posix_binding._verify_temp()
    posix_binding.cleanup_temp()
    posix_binding.close_safely()
    fd_paths[17] = tmp_path
    shutil.rmtree(other)


def test_publication_target_observation_and_parent_cleanup_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    target = tmp_path / "target-observation.json"
    original_identity = binding._identity_at
    for exception in (PublicationRuntime("inspect"), OSError("inspect")):
        with monkeypatch.context() as context:
            context.setattr(binding, "_identity_at", lambda *_args, _exception=exception: (_ for _ in ()).throw(_exception))
            with pytest.raises(PublicationRuntime):
                publication.publish_bytes_no_replace(target, b"payload", parent_binding=binding)
        if target.exists():
            target.unlink()
    monkeypatch.setattr(binding, "_identity_at", original_identity)
    binding.close_safely()

    dummy = publication.BoundPublicationDirectory(tmp_path)
    dummy.directory_handle = 123
    with monkeypatch.context() as context:
        context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: _ChildFakeKernel(ctypes.c_void_p(123), 1, close_result=0))
        with pytest.raises(PublicationRuntime):
            dummy.close()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    real_lstat = os.lstat
    file_path = tmp_path / "not-a-directory"
    file_path.write_bytes(b"x")

    def fake_lstat(value):
        return real_lstat(file_path) if Path(value) == tmp_path else real_lstat(value)

    monkeypatch.setattr(publication.os, "lstat", fake_lstat)
    with pytest.raises(PublicationBoundaryChanged):
        binding._capture_path_identity()
    monkeypatch.setattr(publication.os, "lstat", real_lstat)

    with monkeypatch.context() as context:
        context.setattr(binding, "_stat_at", lambda *_args: (_ for _ in ()).throw(OSError("inspect")))
        with pytest.raises(PublicationRuntime):
            binding._exists_at("child")
    with pytest.raises(PublicationRuntime):
        binding._move_temp("target")

    file_stat = os.lstat(file_path)
    with pytest.raises(PublicationRuntime):
        binding._remove_owned_name(file_path.name, publication._stat_identity(file_stat), directory=True)
    directory = tmp_path / "directory"
    directory.mkdir()
    directory_stat = os.lstat(directory)
    with pytest.raises(PublicationRuntime):
        binding._remove_owned_name(directory.name, publication._stat_identity(directory_stat), directory=False)
    binding.close_safely()


def test_publication_posix_descriptor_and_recursive_cleanup_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    binding.directory_fd = None
    with pytest.raises(PublicationBoundaryChanged):
        binding._check_handle()
    binding.close_safely()

    fd_paths[17] = tmp_path
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    with monkeypatch.context() as context:
        context.setattr(publication.os, "fstat", lambda *_args: (_ for _ in ()).throw(OSError("fstat")))
        with pytest.raises(PublicationBoundaryChanged):
            binding._check_handle()
    binding.close_safely()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    temporary = binding.create_temp_directory("tree")
    with pytest.raises(OSError):
        binding._remove_tree_at(binding.directory_fd, temporary.name, ("wrong",))
    binding.cleanup_temp()
    binding.close_safely()


def test_publication_temp_verification_and_atomic_target_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    monkeypatch.setattr(publication, "_windows_no_replace", lambda *_args: None)
    with pytest.raises(PublicationRuntime):
        binding.publish_bytes("not-published.json", b"payload")
    assert not (tmp_path / "not-published.json").exists()
    assert not list(tmp_path.glob("*.tmp"))
    binding.close_safely()

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    with pytest.raises(PublicationRuntime):
        binding.adopt_existing(tmp_path / "missing-source", directory=False)
    source = tmp_path / "source-dir"
    source.mkdir()
    with pytest.raises(PublicationRuntime):
        binding.adopt_existing(source, directory=False)
    binding.close_safely()

    source_file = tmp_path / "source-file"
    source_file.write_bytes(b"x")
    monkeypatch.setattr(publication.BoundPublicationDirectory, "publish_adopted", lambda self, *_args, **_kwargs: (_ for _ in ()).throw(PublicationRuntime("publish")))
    with pytest.raises(PublicationRuntime):
        publication.atomic_no_replace_move(source_file, tmp_path / "target-file", directory=False)
    assert source_file.exists()


def test_publication_compatibility_cleanup_and_payload_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owned = tmp_path / "owned"
    owned.write_bytes(b"x")
    monkeypatch.setattr(publication.BoundPublicationDirectory, "bind", classmethod(lambda cls, *_args: (_ for _ in ()).throw(ValueError("bind"))))
    with pytest.raises(PublicationRuntime):
        publication._cleanup_owned(owned)

    monkeypatch.undo()
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(PublicationRuntime):
        publication.publish_bytes_no_replace(outside / "target.json", b"x", parent_binding=binding)
    binding.close_safely()


def test_post_commit_descriptor_close_failure_does_not_reverse_publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    monkeypatch.setattr(binding, "_close_temp_fd", lambda: (_ for _ in ()).throw(PublicationRuntime("close")))
    binding.publish_bytes("committed.json", b"payload")
    assert (tmp_path / "committed.json").read_bytes() == b"payload"
    assert binding.temp_name is None
    binding.close_safely()


def test_publication_remaining_observable_error_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    child = tmp_path / "child.json"
    child.write_bytes(b"child")

    with monkeypatch.context() as context:
        context.setattr(binding, "_read_child_bytes_anchored", lambda *_args: (_ for _ in ()).throw(OSError("read")))
        with pytest.raises(PublicationRuntime, match="cannot be read"):
            binding.read_child_bytes(child.name)
    with monkeypatch.context() as context:
        context.setattr(binding, "_capture_file_observable_anchored", lambda *_args: (_ for _ in ()).throw(OSError("capture")))
        with pytest.raises(PublicationRuntime, match="cannot be captured"):
            binding.capture_file_observable(child.name)

    binding.create_temp_file("write.json")
    with monkeypatch.context() as context:
        context.setattr(binding, "_verify_temp", lambda: (_ for _ in ()).throw(PublicationRuntime("verify")))
        with pytest.raises(PublicationRuntime, match="verify"):
            binding.write_temp_bytes(b"payload")
    binding.cleanup_temp()

    with monkeypatch.context() as context:
        context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("close")))
        binding._temp_handle = 123
        with pytest.raises(PublicationRuntime, match="HANDLE"):
            binding._close_temp_handle()
    binding._temp_handle = None

    inactive = publication.BoundPublicationDirectory(tmp_path)
    inactive._verify_temp = lambda: None  # type: ignore[method-assign]
    inactive._exists_at = lambda *_args: False  # type: ignore[method-assign]
    with pytest.raises(PublicationRuntime, match="not active"):
        inactive._move_temp("target.json")
    with monkeypatch.context() as context:
        context.setattr(inactive, "_exists_at", lambda *_args: True)
        with pytest.raises(PublicationRuntime, match="backup name"):
            inactive._next_displaced_name("target.json")

    payload = b"old"
    expected = ExpectedPublicationFile(
        identity=("expected", 1),
        sha256=publication.sha256_bytes(payload),
        size=len(payload),
        mtime_ns=1,
        payload=payload,
    )
    wrong = ExpectedPublicationFile(
        identity=("wrong", 1),
        sha256=publication.sha256_bytes(b"wrong"),
        size=5,
        mtime_ns=1,
        payload=b"wrong",
    )
    with pytest.raises(PublicationRuntime, match="not the expected"):
        inactive._remove_displaced_if_expected("child.json", wrong, expected)
    assert inactive._windows_retained_writer_matches(expected) is False
    with pytest.raises(PublicationRuntime, match="name is unavailable"):
        inactive._discard_windows_writer_replacement(expected)
    inactive._temp_name = "wrong.tmp"
    inactive._close_temp_resources = lambda: None  # type: ignore[method-assign]
    inactive._capture_file_observable_anchored = lambda *_args: wrong  # type: ignore[method-assign]
    with pytest.raises(PublicationRuntime, match="identity changed"):
        inactive._discard_windows_writer_replacement(expected)
    with pytest.raises(PublicationRuntime, match="backup identity"):
        inactive._discard_windows_expected_backup("child.json", expected)
    inactive._capture_file_observable_anchored = lambda *_args: (_ for _ in ()).throw(OSError("capture"))  # type: ignore[method-assign]
    assert inactive._writer_target_matches("child.json", expected) is False
    binding.close_safely()


def test_publication_wrapper_and_adopted_error_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.json"
    with pytest.raises(PublicationRuntime, match="payload"):
        publication.publish_bytes_no_replace(target, "not-bytes")
    with pytest.raises(PublicationRuntime, match="payload"):
        publication.replace_bytes_atomic(target, "not-bytes", expected_target=None)
    with pytest.raises(PublicationRuntime, match="expected target"):
        publication.replace_bytes_atomic(target, b"payload")

    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    target.write_bytes(b"old")
    expected = binding.capture_file_observable(target.name)
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(PublicationRuntime, match="outside bound parent"):
        publication.publish_bytes_no_replace(outside / "child.json", b"payload", parent_binding=binding)
    with pytest.raises(PublicationRuntime, match="outside bound parent"):
        publication.replace_bytes_atomic(outside / "child.json", b"payload", parent_binding=binding, expected_target=expected)

    source = tmp_path / "adopted.json"
    source.write_bytes(b"adopted")
    binding.adopt_existing(source, directory=False, owned=True)
    monkeypatch.setattr(binding, "_move_temp", lambda *_args: None)
    binding.publish_adopted("adopted-target", boundary_check=lambda: None, before_atomic=lambda: None)
    binding.cleanup_temp()

    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    target.write_bytes(b"old")
    posix = publication.BoundPublicationDirectory.bind(tmp_path)
    expected = posix.capture_file_observable(target.name)
    def exchange(source_name, target_name, source_dir_fd=None, target_dir_fd=None):
        posix._close_temp_fd()
        os.replace(fd_paths[source_dir_fd] / source_name, fd_paths[source_dir_fd] / ".exchange")
        os.replace(fd_paths[target_dir_fd] / target_name, fd_paths[target_dir_fd] / source_name)
        os.replace(fd_paths[source_dir_fd] / ".exchange", fd_paths[target_dir_fd] / target_name)

    monkeypatch.setattr(publication, "_linux_exchange", exchange)
    posix.publish_replace(target.name, b"new", before_atomic=lambda: None, expected_target=expected)
    assert target.read_bytes() == b"new"
    posix.close_safely()

    with monkeypatch.context() as context:
        context.setattr(publication, "_lexists", lambda *_args: True)
        real_lstat = publication.os.lstat
        context.setattr(
            publication.os,
            "lstat",
            lambda value: (_ for _ in ()).throw(FileNotFoundError())
            if Path(value) == tmp_path / "missing-owned"
            else real_lstat(value),
        )
        publication._cleanup_owned(tmp_path / "missing-owned")
    invalid = tmp_path / "invalid-owned"
    invalid.write_bytes(b"invalid")
    with monkeypatch.context() as context:
        context.setattr(publication, "is_actual_regular_file", lambda _stat: False)
        with pytest.raises(PublicationRuntime, match="invalid type"):
            publication._cleanup_owned(invalid)


def test_publication_windows_child_and_move_error_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = publication.BoundPublicationDirectory(tmp_path)
    binding._temp_name = "temporary.tmp"
    binding._temp_kind = "file"
    binding._temp_identity = ("temp", 1)
    with monkeypatch.context() as context:
        context.setattr(
            binding,
            "_open_windows_child_handle",
            lambda *_args: (_ for _ in ()).throw(PublicationRuntime("child")),
        )
        with pytest.raises(PublicationRuntime, match="child"):
            binding._open_windows_temp_handle()

    class InvalidChildKernel:
        CreateFileW = _FakeFunction(ctypes.c_void_p(-1))

    monkeypatch.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: InvalidChildKernel())
    with pytest.raises(PublicationRuntime, match="HANDLE"):
        binding._open_windows_child_handle("temporary.tmp", "file")

    class InvalidTypeKernel:
        CreateFileW = _FakeFunction(ctypes.c_void_p(123))
        CloseHandle = _FakeFunction(1)

    monkeypatch.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: InvalidTypeKernel())
    monkeypatch.setattr(
        binding,
        "_windows_info_for_handle",
        lambda _handle: (binding._FILE_ATTRIBUTE_DIRECTORY, ("directory", 1)),
    )
    with pytest.raises(PublicationRuntime, match="HANDLE"):
        binding._open_windows_child_handle("temporary.tmp", "file")

    with monkeypatch.context() as context:
        context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("close")))
        binding._temp_handle = 123
        with pytest.raises(PublicationRuntime, match="HANDLE"):
            binding._close_temp_handle()
    binding._temp_handle = None

    with pytest.raises(PublicationBoundaryChanged, match="identity"):
        binding._handle_target_identity_mismatch("target", ("other",), "source", "file")


def test_publication_move_identity_type_and_parent_error_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)

    def make_binding(name: str):
        binding = publication.BoundPublicationDirectory.bind(tmp_path)
        binding.create_temp_file(name)
        binding.write_temp_bytes(b"payload")
        return binding

    binding = make_binding("oserror.json")
    monkeypatch.setattr(
        publication,
        "_linux_no_replace",
        lambda *_args: (_ for _ in ()).throw(OSError("move")),
    )
    with pytest.raises(PublicationRuntime, match="atomic no-replace"):
        binding._move_temp("oserror-target.json")
    binding.cleanup_temp()

    binding = make_binding("identity.json")

    def move(source, target, source_dir_fd, target_dir_fd):
        binding._close_temp_fd()
        os.replace(fd_paths[source_dir_fd] / source, fd_paths[target_dir_fd] / target)

    monkeypatch.setattr(publication, "_linux_no_replace", move)
    monkeypatch.setattr(binding, "_identity_at", lambda *_args: ("wrong",))
    with pytest.raises(PublicationBoundaryChanged, match="identity"):
        binding._move_temp("identity-target.json")
    binding.cleanup_temp()

    binding = make_binding("type.json")
    original_regular = publication.is_actual_regular_file
    regular_calls = 0

    def regular_then_invalid(item_stat):
        nonlocal regular_calls
        regular_calls += 1
        return original_regular(item_stat) if regular_calls <= 2 else False

    with monkeypatch.context() as context:
        context.setattr(publication, "is_actual_regular_file", regular_then_invalid)
        with pytest.raises(PublicationRuntime, match="invalid type"):
            binding._move_temp("type-target.json")
    binding.cleanup_temp()

    binding = make_binding("parent-runtime.json")
    monkeypatch.setattr(binding, "_capture_path_identity", lambda: (_ for _ in ()).throw(PublicationRuntime("parent")))
    with pytest.raises(PublicationRuntime, match="parent"):
        binding._move_temp("parent-runtime-target.json")
    binding.cleanup_temp()

    binding = make_binding("parent-oserror.json")
    monkeypatch.setattr(binding, "_capture_path_identity", lambda: (_ for _ in ()).throw(OSError("parent")))
    with pytest.raises(PublicationRuntime, match="parent changed"):
        binding._move_temp("parent-oserror-target.json")
    binding.cleanup_temp()


def test_publication_close_and_wrapper_cleanup_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = publication.BoundPublicationDirectory(tmp_path)
    binding._temp_handle = 123

    class FailingCloseKernel:
        CloseHandle = _FakeFunction(0)

    with monkeypatch.context() as context:
        context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: FailingCloseKernel())
        context.setattr(publication.ctypes, "get_last_error", lambda: 5)
        with pytest.raises(PublicationRuntime, match="HANDLE"):
            binding._close_temp_handle()
    binding._temp_handle = None

    fd_paths = _fake_posix_dirfd_runtime(tmp_path, monkeypatch)
    binding = publication.BoundPublicationDirectory.bind(tmp_path)
    binding.create_temp_file("close-handle.json")
    binding.write_temp_bytes(b"payload")

    def move(source, target, source_dir_fd, target_dir_fd):
        binding._close_temp_fd()
        os.replace(fd_paths[source_dir_fd] / source, fd_paths[target_dir_fd] / target)

    monkeypatch.setattr(publication, "_linux_no_replace", move)
    monkeypatch.setattr(binding, "_close_temp_handle", lambda: (_ for _ in ()).throw(PublicationRuntime("handle close")))
    binding._move_temp("close-handle-target.json")
    assert (tmp_path / "close-handle-target.json").read_bytes() == b"payload"
    binding.close_safely()

    directory_binding = publication.BoundPublicationDirectory(tmp_path)
    directory_binding.directory_handle = 123
    with monkeypatch.context() as context:
        context.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: FailingCloseKernel())
        with pytest.raises(PublicationRuntime, match="descriptor cleanup"):
            directory_binding.close()

    fd_binding = publication.BoundPublicationDirectory(tmp_path)
    fd_binding.directory_fd = 123456
    with pytest.raises(PublicationRuntime, match="descriptor cleanup"):
        fd_binding.close()

    cleanup_binding = publication.BoundPublicationDirectory.bind(tmp_path)
    target = tmp_path / "cleanup-target.json"
    target.write_bytes(b"old")
    expected = cleanup_binding.capture_file_observable(target.name)
    monkeypatch.setattr(
        cleanup_binding,
        "cleanup_temp",
        lambda: (_ for _ in ()).throw(PublicationRuntime("cleanup")),
    )
    with pytest.raises(PublicationRuntime, match="cleanup"):
        cleanup_binding.publish_replace(
            target.name,
            b"new",
            before_atomic=lambda: (_ for _ in ()).throw(PublicationRuntime("guard")),
            expected_target=expected,
        )
    cleanup_binding.close_safely()

    source = tmp_path / "atomic-source.json"
    source.write_bytes(b"source")
    with monkeypatch.context() as context:
        context.setattr(
            publication.BoundPublicationDirectory,
            "bind",
            classmethod(lambda cls, *_args: (_ for _ in ()).throw(ValueError("unexpected bind"))),
        )
        with pytest.raises(PublicationRuntime, match="atomic no-replace"):
            publication.atomic_no_replace_move(source, tmp_path / "atomic-target.json", directory=False)

    class FakeWrapperBinding:
        path = tmp_path
        temp_name = "owned.tmp"

        def publish_bytes(self, *_args, **_kwargs):
            raise PublicationRuntime("publish")

        def publish_replace(self, *_args, **_kwargs):
            raise PublicationRuntime("replace")

        def cleanup_temp(self):
            raise PublicationRuntime("cleanup")

        def close_safely(self):
            return None

    with monkeypatch.context() as context:
        context.setattr(
            publication.BoundPublicationDirectory,
            "bind",
            classmethod(lambda cls, *_args: FakeWrapperBinding()),
        )
        with pytest.raises(PublicationRuntime, match="cleanup"):
            publication.publish_bytes_no_replace(tmp_path / "wrapper.json", b"payload")
        with pytest.raises(PublicationRuntime, match="cleanup"):
            publication.replace_bytes_atomic(
                tmp_path / "wrapper.json",
                b"payload",
                expected_target=ExpectedPublicationFile(
                    identity=("wrapper", 1),
                    sha256=publication.sha256_bytes(b"old"),
                    size=3,
                    mtime_ns=1,
                    payload=b"old",
                ),
            )
