"""Story-owned atomic no-replace publication primitives."""

from __future__ import annotations

import ctypes
import errno
import os
import stat
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from .common import is_actual_directory, is_actual_regular_file, read_regular_file, write_fd_all


class PublicationConflict(RuntimeError):
    pass


class PublicationUnavailable(RuntimeError):
    pass


class PublicationRuntime(RuntimeError):
    pass


class PublicationBoundaryChanged(PublicationRuntime):
    """A caller-owned publication guard observed its bound directory/state change."""

    pass


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _ensure_source(source: Path, *, directory: bool) -> None:
    try:
        source_stat = os.lstat(source)
    except OSError as exc:
        raise PublicationRuntime("publication source cannot be inspected") from exc
    valid = is_actual_directory(source_stat) if directory else is_actual_regular_file(source_stat)
    if not valid:
        raise PublicationRuntime("publication source has an invalid file type")


def _windows_no_replace(source: Path, target: Path) -> None:
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file = kernel32.MoveFileExW
        move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move_file.restype = ctypes.c_int
    except Exception as exc:
        raise PublicationUnavailable("Windows no-replace capability is unavailable") from exc
    if move_file(os.fspath(source), os.fspath(target), 0):
        return
    error_number = ctypes.get_last_error()
    if error_number == 183:
        raise PublicationConflict("publication target already exists")
    if error_number in {1, 50, 120}:
        raise PublicationUnavailable("Windows no-replace capability is unavailable")
    raise PublicationRuntime("Windows atomic publication failed")


def _linux_no_replace(source: Path, target: Path) -> None:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2")
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
    except Exception as exc:
        raise PublicationUnavailable("Linux renameat2 is unavailable") from exc
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(target),
        1,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise PublicationConflict("publication target already exists")
    if error_number in {errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EINVAL}:
        raise PublicationUnavailable("Linux renameat2 no-replace capability is unavailable")
    raise PublicationRuntime("Linux atomic publication failed")


def _macos_no_replace(source: Path, target: Path) -> None:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameatx_np = getattr(libc, "renameatx_np")
        renameatx_np.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameatx_np.restype = ctypes.c_int
    except Exception as exc:
        raise PublicationUnavailable("macOS renameatx_np is unavailable") from exc
    result = renameatx_np(
        -2,
        os.fsencode(source),
        -2,
        os.fsencode(target),
        0x00000004,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise PublicationConflict("publication target already exists")
    if error_number in {errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EINVAL}:
        raise PublicationUnavailable("macOS renameatx_np no-replace capability is unavailable")
    raise PublicationRuntime("macOS atomic publication failed")


def atomic_no_replace_move(source: str | Path, target: str | Path, *, directory: bool) -> None:
    source_path = Path(source)
    target_path = Path(target)
    _ensure_source(source_path, directory=directory)
    if _lexists(target_path):
        raise PublicationConflict("publication target already exists")
    try:
        target_parent = os.lstat(target_path.parent)
    except OSError as exc:
        raise PublicationRuntime("publication target parent cannot be inspected") from exc
    if not is_actual_directory(target_parent):
        raise PublicationRuntime("publication target parent is not a directory")
    try:
        if sys.platform.startswith("win"):
            _windows_no_replace(source_path, target_path)
        elif sys.platform == "darwin":
            _macos_no_replace(source_path, target_path)
        elif sys.platform.startswith("linux"):
            _linux_no_replace(source_path, target_path)
        else:
            raise PublicationUnavailable("platform has no supported atomic no-replace primitive")
    except (PublicationConflict, PublicationUnavailable, PublicationRuntime):
        raise
    except OSError as exc:
        raise PublicationRuntime("atomic no-replace publication failed") from exc


def _cleanup_owned(path: Path | None) -> None:
    if path is None:
        return
    try:
        if os.path.lexists(path):
            source_stat = os.lstat(path)
            if stat.S_ISDIR(source_stat.st_mode) and not stat.S_ISLNK(source_stat.st_mode):
                # Story temp roots are private and are only removed by the owner.
                import shutil

                shutil.rmtree(path)
            elif is_actual_regular_file(source_stat):
                path.unlink()
            else:
                raise OSError("owned temporary has an invalid type")
    except FileNotFoundError:
        return
    except Exception as exc:
        raise PublicationRuntime("publication cleanup failed") from exc


def publish_bytes_no_replace(
    target: str | Path,
    payload: bytes,
    *,
    boundary_check: Callable[[], None] | None = None,
) -> None:
    """Publish one regular UTF-8 artifact; success consumes the temp source."""

    target_path = Path(target)
    if not isinstance(payload, bytes):
        raise PublicationRuntime("publication payload is not bytes")
    if boundary_check is not None:
        boundary_check()
    if _lexists(target_path):
        raise PublicationConflict("publication target already exists")
    temporary: Path | None = None
    fd: int | None = None
    try:
        fd, raw_name = tempfile.mkstemp(
            prefix=f".{target_path.name}.",
            suffix=".tmp",
            dir=os.fspath(target_path.parent),
        )
        temporary = Path(raw_name)
        if boundary_check is not None:
            boundary_check()
        write_fd_all(fd, payload)
        os.fsync(fd)
        os.close(fd)
        fd = None
        read_regular_file(temporary)
        if boundary_check is not None:
            boundary_check()
        atomic_no_replace_move(temporary, target_path, directory=False)
        temporary = None
    except (PublicationConflict, PublicationUnavailable, PublicationRuntime):
        raise
    except Exception as exc:
        raise PublicationRuntime("regular artifact publication failed") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if temporary is not None:
            _cleanup_owned(temporary)


__all__ = [
    "PublicationBoundaryChanged",
    "PublicationConflict",
    "PublicationRuntime",
    "PublicationUnavailable",
    "atomic_no_replace_move",
    "publish_bytes_no_replace",
]
