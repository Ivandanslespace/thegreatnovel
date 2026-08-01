"""Campaign-local atomic no-replace publication primitives."""

from __future__ import annotations

import ctypes
import errno
import os
import sys
from pathlib import Path


class _NoReplaceUnavailable(RuntimeError):
    """The host cannot provide the required atomic no-replace operation."""


class _PublicationRuntimeError(RuntimeError):
    """The host primitive failed after capability had been established."""


def publication_lock_path(target: str | Path) -> Path:
    destination = Path(target)
    return destination.parent / f".{destination.name}.publish.lock"


def _windows_move_function():
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file = kernel32.MoveFileExW
        move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move_file.restype = ctypes.c_int
        return move_file
    except (AttributeError, OSError) as exc:
        raise _NoReplaceUnavailable("Windows atomic publication is unavailable") from exc


def _linux_rename_function():
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2")
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        return renameat2
    except (AttributeError, OSError) as exc:
        raise _NoReplaceUnavailable("Linux atomic publication is unavailable") from exc


def _macos_rename_function():
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameatx_np = getattr(libc, "renameatx_np")
        renameatx_np.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameatx_np.restype = ctypes.c_int
        return renameatx_np
    except (AttributeError, OSError) as exc:
        raise _NoReplaceUnavailable("macOS atomic publication is unavailable") from exc


def assert_publication_capability() -> None:
    """Perform a read-only capability preflight without touching the filesystem."""

    if os.name == "nt":
        _windows_move_function()
        return
    if sys.platform.startswith("linux"):
        _linux_rename_function()
        return
    if sys.platform == "darwin":
        _macos_rename_function()
        return
    raise _NoReplaceUnavailable("host has no supported atomic publication primitive")


_UNIX_CAPABILITY_ERRNOS = {
    errno.ENOSYS,
    errno.EINVAL,
    getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
    getattr(errno, "ENOTSUP", errno.EOPNOTSUPP),
}
_WINDOWS_CAPABILITY_ERRORS = {1, 50, 120}


def _is_capability_errno(error_number: int | None) -> bool:
    return error_number in _UNIX_CAPABILITY_ERRNOS


def _is_capability_windows_error(error_number: int | None) -> bool:
    return error_number in _WINDOWS_CAPABILITY_ERRORS


def _publish_directory_no_replace(source: Path, target: Path) -> None:
    """Atomically move a sibling directory without replacing ``target``."""

    if os.name == "nt":
        move_file = _windows_move_function()
        try:
            result = move_file(str(source), str(target), 0x00000008)
        except OSError as exc:
            if _is_capability_windows_error(getattr(exc, "winerror", None) or getattr(exc, "errno", None)):
                raise _NoReplaceUnavailable("Windows atomic publication is unavailable") from exc
            raise _PublicationRuntimeError("Windows atomic directory publication failed") from exc
        if result == 0:
            error_number = ctypes.get_last_error()
            if error_number in {80, 183}:
                raise FileExistsError(error_number, "target already exists")
            if _is_capability_windows_error(error_number):
                raise _NoReplaceUnavailable("Windows atomic publication is unavailable")
            raise _PublicationRuntimeError("Windows atomic directory publication failed")
        return
    if sys.platform.startswith("linux"):
        renameat2 = _linux_rename_function()
        try:
            result = renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1)
        except OSError as exc:
            if _is_capability_errno(exc.errno):
                raise _NoReplaceUnavailable("Linux atomic publication is unavailable") from exc
            raise _PublicationRuntimeError("Linux atomic directory publication failed") from exc
        if result != 0:
            error_number = ctypes.get_errno()
            if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
                raise FileExistsError(error_number, "target already exists")
            if _is_capability_errno(error_number):
                raise _NoReplaceUnavailable("Linux atomic publication is unavailable")
            raise _PublicationRuntimeError("Linux atomic directory publication failed")
        return
    if sys.platform == "darwin":
        renameatx_np = _macos_rename_function()
        try:
            result = renameatx_np(-2, os.fsencode(source), -2, os.fsencode(target), 0x00000004)
        except OSError as exc:
            if _is_capability_errno(exc.errno):
                raise _NoReplaceUnavailable("macOS atomic publication is unavailable") from exc
            raise _PublicationRuntimeError("macOS atomic directory publication failed") from exc
        if result != 0:
            error_number = ctypes.get_errno()
            if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
                raise FileExistsError(error_number, "target already exists")
            if _is_capability_errno(error_number):
                raise _NoReplaceUnavailable("macOS atomic publication is unavailable")
            raise _PublicationRuntimeError("macOS atomic directory publication failed")
        return
    raise _NoReplaceUnavailable("host has no supported atomic publication primitive")


__all__ = [
    "_NoReplaceUnavailable",
    "_PublicationRuntimeError",
    "_publish_directory_no_replace",
    "assert_publication_capability",
    "publication_lock_path",
]
