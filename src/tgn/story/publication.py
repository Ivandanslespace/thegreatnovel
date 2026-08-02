"""Story-owned anchored atomic no-replace publication primitives.

The publication boundary in this module is deliberately local to Story.  A
writer binds the target parent once, keeps the POSIX directory descriptor or
Windows directory handle open, and owns exactly one temporary name.  The
public Story service uses that binding for every checkpoint and for cleanup;
it never searches for a temporary by pathname after the parent has changed.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import errno
import os
import secrets
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import (
    is_actual_directory,
    is_actual_regular_file,
    lexical_absolute,
    read_regular_file,
    sha256_bytes,
    validate_path_components,
    write_fd_all,
)


class PublicationConflict(RuntimeError):
    pass


class PublicationUnavailable(RuntimeError):
    pass


class PublicationRuntime(RuntimeError):
    pass


class PublicationBoundaryChanged(PublicationRuntime):
    """A caller-owned publication guard observed its bound state change."""


ERROR_UNABLE_TO_REMOVE_REPLACED = 1175
ERROR_UNABLE_TO_MOVE_REPLACEMENT = 1176
ERROR_UNABLE_TO_MOVE_REPLACEMENT_2 = 1177


class WindowsReplaceFailure(PublicationRuntime):
    """A ReplaceFileW failure with its documented exact outcome preserved."""

    _OUTCOMES = {
        ERROR_UNABLE_TO_REMOVE_REPLACED: "ERROR_UNABLE_TO_REMOVE_REPLACED",
        ERROR_UNABLE_TO_MOVE_REPLACEMENT: "ERROR_UNABLE_TO_MOVE_REPLACEMENT",
        ERROR_UNABLE_TO_MOVE_REPLACEMENT_2: "ERROR_UNABLE_TO_MOVE_REPLACEMENT_2",
    }

    def __init__(self, error_number: int) -> None:
        self.error_number = int(error_number)
        self.outcome = self._OUTCOMES.get(self.error_number, "OTHER")
        super().__init__(f"ReplaceFileW failed with {self.outcome} ({self.error_number})")


@dataclass(frozen=True)
class ExpectedPublicationFile:
    """The exact regular file that a conditional replacement may displace."""

    identity: tuple[Any, ...]
    sha256: str
    size: int
    mtime_ns: int
    payload: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.identity, tuple) or not self.identity:
            raise PublicationRuntime("expected publication identity is invalid")
        if type(self.size) is not int or self.size < 0:
            raise PublicationRuntime("expected publication size is invalid")
        if type(self.mtime_ns) is not int or self.mtime_ns < 0:
            raise PublicationRuntime("expected publication mtime is invalid")
        if not isinstance(self.sha256, str) or len(self.sha256) != 64:
            raise PublicationRuntime("expected publication hash is invalid")
        if not isinstance(self.payload, bytes):
            raise PublicationRuntime("expected publication payload is invalid")
        if len(self.payload) != self.size or sha256_bytes(self.payload) != self.sha256:
            raise PublicationRuntime("expected publication observable is inconsistent")


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _stat_identity(item_stat: os.stat_result) -> tuple[Any, ...]:
    device = getattr(item_stat, "st_dev", None)
    inode = getattr(item_stat, "st_ino", None)
    if device is not None and inode is not None and not (device == 0 and inode == 0):
        return ("posix", int(device), int(inode))
    return (
        "fallback",
        int(getattr(item_stat, "st_file_attributes", 0)),
        int(getattr(item_stat, "st_ctime_ns", 0)),
        int(item_stat.st_mode),
    )


def _ensure_name(name: str) -> str:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or Path(name).name != name
        or "/" in name
        or "\\" in name
    ):
        raise PublicationRuntime("publication name is invalid")
    return name


def _ensure_source(source: Path, *, directory: bool) -> None:
    try:
        source_stat = os.lstat(source)
    except OSError as exc:
        raise PublicationRuntime("publication source cannot be inspected") from exc
    valid = is_actual_directory(source_stat) if directory else is_actual_regular_file(source_stat)
    if not valid:
        raise PublicationRuntime("publication source has an invalid file type")


def _windows_no_replace(source: str | Path, target: str | Path, parent_handle: int | None = None) -> None:
    """Use MoveFileExW with no-replace semantics.

    On Windows the caller keeps ``parent_handle`` open with FILE_SHARE_DELETE
    absent.  MoveFileExW is therefore not able to redirect the operation by
    replacing the verified parent during this publication.  The handle is
    deliberately accepted here even though MoveFileExW itself takes paths:
    the handle is the parent binding/protection mechanism.
    """

    del parent_handle
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


def _windows_replace_file(
    source: str | Path,
    target: str | Path,
    backup: str | Path,
    parent_handle: int | None = None,
) -> None:
    """Replace a target while atomically preserving its displaced object."""

    del parent_handle
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        replace_file = kernel32.ReplaceFileW
        replace_file.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        replace_file.restype = ctypes.wintypes.BOOL
    except Exception as exc:
        raise PublicationUnavailable("Windows atomic replace capability is unavailable") from exc
    if replace_file(
        os.fspath(target),
        os.fspath(source),
        os.fspath(backup),
        0,
        None,
        None,
    ):
        return
    error_number = ctypes.get_last_error()
    raise WindowsReplaceFailure(error_number)


def _linux_no_replace(
    source: str | Path,
    target: str | Path,
    source_dir_fd: int | None = None,
    target_dir_fd: int | None = None,
) -> None:
    """Call Linux renameat2, optionally with anchored directory descriptors."""

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2")
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
    except Exception as exc:
        raise PublicationUnavailable("Linux renameat2 is unavailable") from exc
    source_fd = -100 if source_dir_fd is None else source_dir_fd
    target_fd = -100 if target_dir_fd is None else target_dir_fd
    result = renameat2(
        source_fd,
        os.fsencode(source),
        target_fd,
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


def _linux_exchange(
    source: str | Path,
    target: str | Path,
    source_dir_fd: int | None = None,
    target_dir_fd: int | None = None,
) -> None:
    """Atomically exchange two names while retaining the displaced object."""

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2")
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
    except Exception as exc:
        raise PublicationUnavailable("Linux renameat2 exchange is unavailable") from exc
    source_fd = -100 if source_dir_fd is None else source_dir_fd
    target_fd = -100 if target_dir_fd is None else target_dir_fd
    result = renameat2(
        source_fd,
        os.fsencode(source),
        target_fd,
        os.fsencode(target),
        2,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EINVAL}:
        raise PublicationUnavailable("Linux renameat2 exchange is unavailable")
    raise PublicationRuntime("Linux atomic exchange failed")


def _macos_no_replace(
    source: str | Path,
    target: str | Path,
    source_dir_fd: int | None = None,
    target_dir_fd: int | None = None,
) -> None:
    """Call macOS renameatx_np, optionally with anchored directory descriptors."""

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameatx_np = getattr(libc, "renameatx_np")
        renameatx_np.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameatx_np.restype = ctypes.c_int
    except Exception as exc:
        raise PublicationUnavailable("macOS renameatx_np is unavailable") from exc
    source_fd = -2 if source_dir_fd is None else source_dir_fd
    target_fd = -2 if target_dir_fd is None else target_dir_fd
    result = renameatx_np(
        source_fd,
        os.fsencode(source),
        target_fd,
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


def _macos_exchange(
    source: str | Path,
    target: str | Path,
    source_dir_fd: int | None = None,
    target_dir_fd: int | None = None,
) -> None:
    """Atomically exchange two names through macOS renameatx_np."""

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameatx_np = getattr(libc, "renameatx_np")
        renameatx_np.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameatx_np.restype = ctypes.c_int
    except Exception as exc:
        raise PublicationUnavailable("macOS renameatx_np exchange is unavailable") from exc
    source_fd = -2 if source_dir_fd is None else source_dir_fd
    target_fd = -2 if target_dir_fd is None else target_dir_fd
    result = renameatx_np(
        source_fd,
        os.fsencode(source),
        target_fd,
        os.fsencode(target),
        0x00000002,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EINVAL}:
        raise PublicationUnavailable("macOS renameatx_np exchange is unavailable")
    raise PublicationRuntime("macOS atomic exchange failed")


class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", ctypes.wintypes.DWORD),
        ("ftCreationTime", ctypes.wintypes.FILETIME),
        ("ftLastAccessTime", ctypes.wintypes.FILETIME),
        ("ftLastWriteTime", ctypes.wintypes.FILETIME),
        ("dwVolumeSerialNumber", ctypes.wintypes.DWORD),
        ("nFileSizeHigh", ctypes.wintypes.DWORD),
        ("nFileSizeLow", ctypes.wintypes.DWORD),
        ("nNumberOfLinks", ctypes.wintypes.DWORD),
        ("nFileIndexHigh", ctypes.wintypes.DWORD),
        ("nFileIndexLow", ctypes.wintypes.DWORD),
    ]


class _FILE_DISPOSITION_INFO(ctypes.Structure):
    _fields_ = [("DeleteFile", ctypes.wintypes.BOOL)]


class BoundPublicationDirectory:
    """One operation-local, caller-visible parent directory binding."""

    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_READ_ATTRIBUTES = 0x00000080
    _FILE_LIST_DIRECTORY = 0x00000001
    _GENERIC_READ = 0x80000000
    _DELETE = 0x00010000
    _FILE_DISPOSITION_INFO_CLASS = 4
    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
    _FILE_SHARE_DELETE = 0x00000004
    _OPEN_EXISTING = 3

    def __init__(self, path: Path) -> None:
        self.path = path
        self.directory_fd: int | None = None
        self.directory_handle: int | None = None
        self._path_identity: tuple[Any, ...] | None = None
        self._handle_identity: tuple[Any, ...] | None = None
        self._temp_name: str | None = None
        self._temp_path: Path | None = None
        self._temp_kind: str | None = None
        self._temp_fd: int | None = None
        self._temp_handle: int | None = None
        self._temp_identity: tuple[Any, ...] | None = None
        self._temp_owned = False
        self._quarantine_name: str | None = None
        self._quarantine_fd: int | None = None
        self._quarantine_identity: tuple[Any, ...] | None = None

    @classmethod
    def bind(cls, parent: str | Path) -> "BoundPublicationDirectory":
        path = lexical_absolute(parent)
        try:
            validate_path_components(path, allow_missing_final=False)
            initial = os.lstat(path)
        except OSError as exc:
            raise PublicationRuntime("publication parent cannot be inspected") from exc
        if not is_actual_directory(initial):
            raise PublicationRuntime("publication parent is not an actual directory")
        binding = cls(path)
        binding._path_identity = _stat_identity(initial)
        try:
            if os.name == "nt":
                binding._open_windows_handle()
            else:
                flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                binding.directory_fd = os.open(os.fspath(path), flags)
                opened = os.fstat(binding.directory_fd)
                if not is_actual_directory(opened) or _stat_identity(opened) != binding._path_identity:
                    raise OSError("publication parent changed while opening")
        except (PublicationUnavailable, PublicationRuntime):
            binding.close_safely()
            raise
        except OSError as exc:
            binding.close_safely()
            raise PublicationRuntime("publication parent cannot be anchored") from exc
        return binding

    def _open_windows_handle(self) -> None:
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.c_wchar_p,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.DWORD,
                ctypes.c_void_p,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.HANDLE,
            ]
            create_file.restype = ctypes.wintypes.HANDLE
            handle = create_file(
                os.fspath(self.path),
                self._FILE_READ_ATTRIBUTES | self._FILE_LIST_DIRECTORY,
                self._FILE_SHARE_READ | self._FILE_SHARE_WRITE,
                None,
                self._OPEN_EXISTING,
                self._FILE_FLAG_BACKUP_SEMANTICS | self._FILE_FLAG_OPEN_REPARSE_POINT,
                None,
            )
            value = ctypes.cast(handle, ctypes.c_void_p).value
            invalid_handle = ctypes.c_void_p(-1).value
            if value in {None, -1, invalid_handle}:
                raise OSError(ctypes.get_last_error(), "CreateFileW failed")
            self.directory_handle = int(value)
            info = self._windows_info()
            if not (info[0] & self._FILE_ATTRIBUTE_DIRECTORY) or info[0] & self._FILE_ATTRIBUTE_REPARSE_POINT:
                raise OSError("publication parent is not a real Windows directory")
            self._handle_identity = info[1]
        except PublicationRuntime:
            raise
        except Exception as exc:
            raise PublicationRuntime("publication parent HANDLE cannot be opened") from exc

    def _windows_info(self) -> tuple[int, tuple[Any, ...]]:
        if self.directory_handle is None:
            raise PublicationRuntime("publication parent HANDLE is closed")
        return self._windows_info_for_handle(self.directory_handle)

    def _windows_info_for_handle(self, handle: int) -> tuple[int, tuple[Any, ...]]:
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_info = kernel32.GetFileInformationByHandle
            get_info.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION)]
            get_info.restype = ctypes.wintypes.BOOL
            info = _BY_HANDLE_FILE_INFORMATION()
            if not get_info(ctypes.wintypes.HANDLE(handle), ctypes.byref(info)):
                raise OSError(ctypes.get_last_error(), "GetFileInformationByHandle failed")
            identity = (
                "windows",
                int(info.dwVolumeSerialNumber),
                int(info.nFileIndexHigh),
                int(info.nFileIndexLow),
            )
            return int(info.dwFileAttributes), identity
        except PublicationRuntime:
            raise
        except Exception as exc:
            raise PublicationRuntime("publication HANDLE cannot be inspected") from exc

    def _open_windows_temp_handle(self) -> None:
        if os.name != "nt":
            return
        if self._temp_name is None or self._temp_kind is None:
            raise PublicationRuntime("owned temporary is not active")
        try:
            handle, attributes, handle_identity = self._open_windows_child_handle(
                self._temp_name,
                self._temp_kind,
            )
            self._temp_handle = handle
            if self._temp_identity is None:
                self._temp_identity = handle_identity
            elif handle_identity != self._temp_identity:
                raise OSError("owned temporary identity changed while opening HANDLE")
            _attributes, name_identity = self._windows_identity_at(self._temp_name, self._temp_kind)
            if name_identity != self._temp_identity:
                raise OSError("owned temporary name identity changed while opening HANDLE")
        except PublicationRuntime:
            self._close_temp_handle_safely()
            raise
        except Exception as exc:
            self._close_temp_handle_safely()
            raise PublicationRuntime("owned temporary HANDLE cannot be opened") from exc

    def _open_windows_child_handle(
        self,
        name: str,
        kind: str,
        *,
        delete: bool = False,
        compatible_with_delete: bool = False,
    ) -> tuple[int, int, tuple[Any, ...]]:
        """Open one non-reparse child and return its stable Windows identity."""

        name = _ensure_name(name)
        handle_value: int | None = None
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.c_wchar_p,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.DWORD,
                ctypes.c_void_p,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.HANDLE,
            ]
            create_file.restype = ctypes.wintypes.HANDLE
            access = self._FILE_READ_ATTRIBUTES | (self._DELETE if delete else 0)
            if delete:
                access |= self._GENERIC_READ
            flags = self._FILE_FLAG_OPEN_REPARSE_POINT
            if kind == "directory":
                access |= self._FILE_LIST_DIRECTORY
                flags |= self._FILE_FLAG_BACKUP_SEMANTICS
            handle = create_file(
                os.fspath(self.path / name),
                access,
                self._FILE_SHARE_READ
                if delete or compatible_with_delete
                else self._FILE_SHARE_READ | self._FILE_SHARE_WRITE | self._FILE_SHARE_DELETE,
                None,
                self._OPEN_EXISTING,
                flags,
                None,
            )
            value = ctypes.cast(handle, ctypes.c_void_p).value
            invalid_handle = ctypes.c_void_p(-1).value
            if value in {None, -1, invalid_handle}:
                raise OSError(ctypes.get_last_error(), "CreateFileW child failed")
            handle_value = int(value)
            attributes, identity = self._windows_info_for_handle(handle_value)
            valid = bool(attributes & self._FILE_ATTRIBUTE_DIRECTORY) if kind == "directory" else not bool(attributes & self._FILE_ATTRIBUTE_DIRECTORY)
            if attributes & self._FILE_ATTRIBUTE_REPARSE_POINT or not valid:
                self._close_windows_handle_value(handle_value)
                handle_value = None
                raise OSError("Windows child has an invalid type")
            return handle_value, attributes, identity
        except Exception as exc:
            if handle_value is not None:
                try:
                    self._close_windows_handle_value(handle_value)
                except Exception:
                    pass
            if isinstance(exc, PublicationRuntime):
                raise
            raise PublicationRuntime("Windows child HANDLE cannot be opened") from exc

    def _close_windows_handle_value(self, handle: int) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.wintypes.HANDLE]
        close_handle.restype = ctypes.wintypes.BOOL
        if not close_handle(ctypes.wintypes.HANDLE(handle)):
            raise OSError(ctypes.get_last_error(), "CloseHandle child failed")

    def _windows_identity_at(
        self,
        name: str,
        kind: str,
        *,
        compatible_with_delete: bool = False,
    ) -> tuple[int, tuple[Any, ...]]:
        handle, attributes, identity = self._open_windows_child_handle(
            name,
            kind,
            compatible_with_delete=compatible_with_delete,
        )
        try:
            return attributes, identity
        finally:
            self._close_windows_handle_value(handle)

    def _windows_remove_file_by_handle(
        self,
        name: str,
        expected: ExpectedPublicationFile,
        *,
        retained_handle: int | None = None,
    ) -> None:
        """Delete one exact Windows file through a DELETE-capable HANDLE."""

        if os.name != "nt":
            raise PublicationUnavailable("Windows handle deletion is unavailable")
        if retained_handle is not None:
            attributes, identity = self._windows_info_for_handle(retained_handle)
            if (
                attributes & self._FILE_ATTRIBUTE_DIRECTORY
                or attributes & self._FILE_ATTRIBUTE_REPARSE_POINT
                or identity != expected.identity
            ):
                raise PublicationBoundaryChanged("Windows cleanup HANDLE identity changed")
        current = self._capture_file_observable_anchored(name)
        if current != expected:
            raise PublicationBoundaryChanged("Windows cleanup target observable changed")
        self._before_windows_delete_handle(name, expected)
        handle: int | None = None
        try:
            handle, attributes, identity = self._open_windows_child_handle(
                name,
                "file",
                delete=True,
            )
            if (
                attributes & self._FILE_ATTRIBUTE_DIRECTORY
                or attributes & self._FILE_ATTRIBUTE_REPARSE_POINT
                or identity != expected.identity
            ):
                raise PublicationBoundaryChanged("Windows cleanup target identity changed")
            self._after_windows_delete_handle_open(name, expected, handle)
            current_after_open = self._capture_file_observable_anchored(name, handle)
            if current_after_open.identity != identity or current_after_open != expected:
                raise PublicationBoundaryChanged("Windows cleanup target observable changed")
            try:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                set_information = kernel32.SetFileInformationByHandle
                set_information.argtypes = [
                    ctypes.wintypes.HANDLE,
                    ctypes.wintypes.DWORD,
                    ctypes.c_void_p,
                    ctypes.wintypes.DWORD,
                ]
                set_information.restype = ctypes.wintypes.BOOL
                disposition = _FILE_DISPOSITION_INFO(True)
                if not set_information(
                    ctypes.wintypes.HANDLE(handle),
                    self._FILE_DISPOSITION_INFO_CLASS,
                    ctypes.byref(disposition),
                    ctypes.sizeof(disposition),
                ):
                    error_number = ctypes.get_last_error()
                    if error_number in {1, 50, 120}:
                        raise PublicationUnavailable("Windows handle deletion is unavailable")
                    raise PublicationRuntime("Windows handle deletion failed")
            except (PublicationBoundaryChanged, PublicationUnavailable, PublicationRuntime):
                raise
            except Exception as exc:
                raise PublicationUnavailable("Windows handle deletion is unavailable") from exc
        finally:
            if handle is not None:
                self._close_windows_handle_value(handle)

    def _capture_path_identity(self) -> tuple[Any, ...]:
        try:
            validate_path_components(self.path, allow_missing_final=False)
            current = os.lstat(self.path)
        except OSError as exc:
            raise PublicationBoundaryChanged("publication parent path changed") from exc
        if not is_actual_directory(current):
            raise PublicationBoundaryChanged("publication parent path changed")
        return _stat_identity(current)

    def _check_handle(self) -> None:
        if os.name == "nt":
            attributes, identity = self._windows_info()
            if not (attributes & self._FILE_ATTRIBUTE_DIRECTORY) or attributes & self._FILE_ATTRIBUTE_REPARSE_POINT:
                raise PublicationBoundaryChanged("publication parent HANDLE changed")
            if identity != self._handle_identity:
                raise PublicationBoundaryChanged("publication parent HANDLE changed")
            return
        if self.directory_fd is None:
            raise PublicationBoundaryChanged("publication parent descriptor is closed")
        try:
            opened = os.fstat(self.directory_fd)
        except OSError as exc:
            raise PublicationBoundaryChanged("publication parent descriptor changed") from exc
        if not is_actual_directory(opened) or _stat_identity(opened) != self._path_identity:
            raise PublicationBoundaryChanged("publication parent descriptor changed")

    def check(self) -> None:
        """Verify both the retained handle/descriptor and its visible path."""

        self._check_handle()
        if self._capture_path_identity() != self._path_identity:
            raise PublicationBoundaryChanged("publication parent path changed")

    def checkpoint(self, boundary_check: Callable[[], None] | None = None) -> None:
        """Run one anchored checkpoint before and after the caller guard."""

        self.check()
        if boundary_check is not None:
            boundary_check()
        self.check()

    @property
    def temp_name(self) -> str | None:
        return self._temp_name

    @property
    def temp_path(self) -> Path | None:
        return self._temp_path

    def _next_temp_name(self, target_name: str) -> str:
        safe_target = _ensure_name(target_name)
        return f".{safe_target}.{secrets.token_hex(16)}.tmp"

    def _stat_at(self, name: str) -> os.stat_result:
        _ensure_name(name)
        if self.directory_fd is not None:
            return os.stat(name, dir_fd=self.directory_fd, follow_symlinks=False)
        try:
            return os.lstat(self.path / name)
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise PublicationRuntime("publication child cannot be inspected") from exc

    def read_child_bytes(self, name: str) -> tuple[bytes, os.stat_result]:
        """Read one regular child through this operation's bound parent."""

        name = _ensure_name(name)
        self.check()
        try:
            return self._read_child_bytes_anchored(name)
        except PublicationRuntime:
            raise
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise PublicationRuntime("publication child cannot be read") from exc
        finally:
            self.check()

    def _read_child_bytes_anchored(self, name: str) -> tuple[bytes, os.stat_result]:
        """Read one child relative to the retained parent without a path check."""

        name = _ensure_name(name)
        try:
            initial = self._stat_at(name)
            if not is_actual_regular_file(initial):
                raise PublicationRuntime("publication child is not a regular file")
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
            if self.directory_fd is not None:
                fd = os.open(name, flags, dir_fd=self.directory_fd)
            else:
                fd = os.open(os.fspath(self.path / name), flags)
            try:
                opened = os.fstat(fd)
                if not is_actual_regular_file(opened) or _stat_identity(opened) != _stat_identity(initial):
                    raise PublicationRuntime("publication child identity changed while opening")
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(fd, 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                final = self._stat_at(name)
                if not is_actual_regular_file(final) or _stat_identity(final) != _stat_identity(opened):
                    raise PublicationRuntime("publication child identity changed while reading")
                return b"".join(chunks), final
            finally:
                os.close(fd)
        except PublicationRuntime:
            raise
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise PublicationRuntime("publication child cannot be read") from exc

    def _read_windows_handle(self, handle: int) -> bytes:
        """Read one regular file through its already-open Windows HANDLE."""

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            read_file = kernel32.ReadFile
            read_file.argtypes = [
                ctypes.wintypes.HANDLE,
                ctypes.c_void_p,
                ctypes.wintypes.DWORD,
                ctypes.POINTER(ctypes.wintypes.DWORD),
                ctypes.c_void_p,
            ]
            read_file.restype = ctypes.wintypes.BOOL
            chunks: list[bytes] = []
            while True:
                buffer = ctypes.create_string_buffer(1024 * 1024)
                count = ctypes.wintypes.DWORD()
                if not read_file(
                    ctypes.wintypes.HANDLE(handle),
                    ctypes.byref(buffer),
                    ctypes.sizeof(buffer),
                    ctypes.byref(count),
                    None,
                ):
                    raise OSError(ctypes.get_last_error(), "ReadFile failed")
                if count.value == 0:
                    break
                chunks.append(buffer.raw[: count.value])
            return b"".join(chunks)
        except PublicationRuntime:
            raise
        except Exception as exc:
            raise PublicationRuntime("Windows cleanup observable cannot be captured") from exc

    def _capture_file_observable_from_windows_handle(
        self,
        name: str,
        handle: int,
    ) -> ExpectedPublicationFile:
        """Capture a child through a held DELETE-capable HANDLE and its name."""

        try:
            handle_attributes, handle_identity = self._windows_info_for_handle(handle)
            if (
                handle_attributes & self._FILE_ATTRIBUTE_DIRECTORY
                or handle_attributes & self._FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise PublicationBoundaryChanged("Windows cleanup target has an invalid type")
            path_attributes, path_identity = self._windows_identity_at(
                name,
                "file",
                compatible_with_delete=True,
            )
            if (
                path_attributes & self._FILE_ATTRIBUTE_DIRECTORY
                or path_attributes & self._FILE_ATTRIBUTE_REPARSE_POINT
                or path_identity != handle_identity
            ):
                raise PublicationBoundaryChanged("Windows cleanup target identity changed")
            initial = self._stat_at(name)
            if not is_actual_regular_file(initial):
                raise PublicationBoundaryChanged("Windows cleanup target has an invalid type")
            payload = self._read_windows_handle(handle)
            final_attributes, final_identity = self._windows_info_for_handle(handle)
            final_path_attributes, final_path_identity = self._windows_identity_at(
                name,
                "file",
                compatible_with_delete=True,
            )
            final = self._stat_at(name)
            if (
                final_attributes & self._FILE_ATTRIBUTE_DIRECTORY
                or final_attributes & self._FILE_ATTRIBUTE_REPARSE_POINT
                or final_path_attributes & self._FILE_ATTRIBUTE_DIRECTORY
                or final_path_attributes & self._FILE_ATTRIBUTE_REPARSE_POINT
                or final_identity != handle_identity
                or final_path_identity != handle_identity
                or not is_actual_regular_file(final)
                or _stat_identity(final) != _stat_identity(initial)
                or int(final.st_size) != len(payload)
            ):
                raise PublicationBoundaryChanged("Windows cleanup target observable changed")
            return ExpectedPublicationFile(
                identity=handle_identity,
                sha256=sha256_bytes(payload),
                size=len(payload),
                mtime_ns=int(final.st_mtime_ns),
                payload=payload,
            )
        except (PublicationBoundaryChanged, PublicationRuntime):
            raise
        except FileNotFoundError as exc:
            raise PublicationBoundaryChanged("Windows cleanup target disappeared") from exc
        except OSError as exc:
            raise PublicationRuntime("Windows cleanup observable cannot be captured") from exc

    def _capture_file_observable_anchored(
        self,
        name: str,
        windows_handle: int | None = None,
    ) -> ExpectedPublicationFile:
        """Capture exact file bytes and identity relative to the bound parent."""

        if windows_handle is not None:
            if os.name != "nt":
                raise PublicationRuntime("Windows cleanup HANDLE is unavailable")
            return self._capture_file_observable_from_windows_handle(name, windows_handle)

        payload, file_stat = self._read_child_bytes_anchored(name)
        identity = self._identity_at(name, "file") if os.name == "nt" else _stat_identity(file_stat)
        return ExpectedPublicationFile(
            identity=identity,
            sha256=sha256_bytes(payload),
            size=len(payload),
            mtime_ns=int(file_stat.st_mtime_ns),
            payload=payload,
        )

    def capture_file_observable(self, name: str) -> ExpectedPublicationFile:
        """Capture a regular child as an exact conditional-publication target."""

        name = _ensure_name(name)
        self.check()
        try:
            return self._capture_file_observable_anchored(name)
        except PublicationRuntime:
            raise
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise PublicationRuntime("publication child observable cannot be captured") from exc
        finally:
            self.check()

    def child_identity(self, name: str, kind: str) -> tuple[Any, ...]:
        """Capture one child identity through this operation's bound parent."""

        name = _ensure_name(name)
        if kind not in {"file", "directory"}:
            raise PublicationRuntime("publication child kind is invalid")
        self.check()
        try:
            item_stat = self._stat_at(name)
            valid = is_actual_regular_file(item_stat) if kind == "file" else is_actual_directory(item_stat)
            if not valid:
                raise PublicationRuntime("publication child has an invalid file type")
            return self._identity_at(name, kind)
        except PublicationRuntime:
            raise
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise PublicationRuntime("publication child identity cannot be inspected") from exc
        finally:
            self.check()

    def _exists_at(self, name: str) -> bool:
        try:
            self._stat_at(name)
            return True
        except FileNotFoundError:
            return False
        except PublicationRuntime:
            raise
        except OSError as exc:
            raise PublicationRuntime("publication target cannot be inspected") from exc

    def _identity_at(self, name: str, kind: str) -> tuple[Any, ...]:
        if os.name == "nt":
            _attributes, identity = self._windows_identity_at(name, kind)
            return identity
        return _stat_identity(self._stat_at(name))

    def _register_temp(self, name: str, *, kind: str, fd: int | None) -> Path:
        self._temp_name = _ensure_name(name)
        self._temp_path = self.path / self._temp_name
        self._temp_kind = kind
        self._temp_fd = fd
        self._temp_owned = True
        try:
            item_stat = os.fstat(fd) if fd is not None and os.name != "nt" else self._stat_at(name)
        except OSError as exc:
            raise PublicationRuntime("owned temporary cannot be inspected") from exc
        valid = is_actual_directory(item_stat) if kind == "directory" else is_actual_regular_file(item_stat)
        if not valid:
            raise PublicationRuntime("owned temporary has an invalid file type")
        self._temp_identity = None if os.name == "nt" else _stat_identity(item_stat)
        if os.name == "nt":
            self._open_windows_temp_handle()
        return self._temp_path

    def create_temp_file(self, target_name: str) -> Path:
        self.check()
        prefix = f".{_ensure_name(target_name)}."
        for _ in range(32):
            name = f"{prefix}{secrets.token_hex(16)}.tmp"
            try:
                if os.name == "nt":
                    fd, raw_name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=os.fspath(self.path))
                    name = Path(raw_name).name
                else:
                    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                    if hasattr(os, "O_BINARY"):
                        flags |= os.O_BINARY
                    fd = os.open(name, flags, 0o600, dir_fd=self.directory_fd)
                return self._register_temp(name, kind="file", fd=fd)
            except FileExistsError:
                continue
            except OSError as exc:
                raise PublicationRuntime("owned temporary file cannot be created") from exc
        raise PublicationRuntime("owned temporary name allocation failed")

    def create_temp_directory(self, target_name: str) -> Path:
        self.check()
        prefix = f".{_ensure_name(target_name)}."
        for _ in range(32):
            name = f"{prefix}{secrets.token_hex(16)}.tmp"
            try:
                if os.name == "nt":
                    raw_name = tempfile.mkdtemp(prefix=prefix, dir=os.fspath(self.path))
                    name = Path(raw_name).name
                    fd = None
                else:
                    os.mkdir(name, 0o700, dir_fd=self.directory_fd)
                    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                    fd = os.open(name, flags, dir_fd=self.directory_fd)
                return self._register_temp(name, kind="directory", fd=fd)
            except FileExistsError:
                continue
            except OSError as exc:
                raise PublicationRuntime("owned temporary directory cannot be created") from exc
        raise PublicationRuntime("owned temporary name allocation failed")

    def write_temp_bytes(self, payload: bytes) -> None:
        if self._temp_kind != "file" or self._temp_name is None or self._temp_path is None:
            raise PublicationRuntime("owned temporary file is not active")
        if not isinstance(payload, bytes):
            raise PublicationRuntime("publication payload is not bytes")
        fd = self._temp_fd
        try:
            if fd is None:
                flags = os.O_WRONLY | getattr(os, "O_BINARY", 0)
                fd = os.open(os.fspath(self._temp_path), flags)
                self._temp_fd = fd
            write_fd_all(fd, payload)
            os.fsync(fd)
            if os.name == "nt":
                os.close(fd)
                self._temp_fd = None
                actual, _ = read_regular_file(self._temp_path)
            else:
                os.lseek(fd, 0, os.SEEK_SET)
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(fd, 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                os.lseek(fd, 0, os.SEEK_END)
                actual = b"".join(chunks)
            if actual != payload:
                raise OSError("owned temporary verification differs from payload")
            self._verify_temp()
        except PublicationRuntime:
            raise
        except Exception as exc:
            raise PublicationRuntime("owned temporary file could not be written") from exc

    def adopt_existing(self, source: str | Path, *, directory: bool, owned: bool = False) -> None:
        source_path = lexical_absolute(source)
        if source_path.parent != self.path:
            raise PublicationRuntime("publication source is not in bound parent")
        name = _ensure_name(source_path.name)
        try:
            item_stat = self._stat_at(name)
        except PublicationRuntime:
            raise
        except OSError as exc:
            raise PublicationRuntime("publication source cannot be inspected") from exc
        valid = is_actual_directory(item_stat) if directory else is_actual_regular_file(item_stat)
        if not valid:
            raise PublicationRuntime("publication source has an invalid file type")
        fd: int | None = None
        if os.name != "nt":
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            if directory:
                flags |= getattr(os, "O_DIRECTORY", 0)
            try:
                fd = os.open(name, flags, dir_fd=self.directory_fd)
            except OSError as exc:
                raise PublicationRuntime("publication source cannot be anchored") from exc
        self._temp_name = name
        self._temp_path = source_path
        self._temp_kind = "directory" if directory else "file"
        self._temp_fd = fd
        self._temp_handle = None
        self._temp_identity = None if os.name == "nt" else _stat_identity(item_stat)
        self._temp_owned = owned
        if os.name == "nt":
            self._open_windows_temp_handle()
        self._verify_temp()

    def _verify_temp(self) -> os.stat_result:
        if self._temp_name is None or self._temp_kind is None or self._temp_identity is None:
            raise PublicationRuntime("owned temporary is not active")
        try:
            if os.name == "nt":
                if self._temp_handle is None:
                    raise PublicationRuntime("owned temporary HANDLE is not active")
                attributes, retained_identity = self._windows_info_for_handle(self._temp_handle)
                retained_valid = (
                    bool(attributes & self._FILE_ATTRIBUTE_DIRECTORY)
                    if self._temp_kind == "directory"
                    else not bool(attributes & self._FILE_ATTRIBUTE_DIRECTORY)
                )
                if attributes & self._FILE_ATTRIBUTE_REPARSE_POINT or not retained_valid:
                    raise PublicationRuntime("owned temporary HANDLE has an invalid type")
                _current_attributes, current_identity = self._windows_identity_at(self._temp_name, self._temp_kind)
                current = self._stat_at(self._temp_name)
            else:
                if self._temp_fd is None:
                    raise PublicationRuntime("owned temporary descriptor is not active")
                retained_stat = os.fstat(self._temp_fd)
                retained_identity = _stat_identity(retained_stat)
                retained_valid = is_actual_directory(retained_stat) if self._temp_kind == "directory" else is_actual_regular_file(retained_stat)
                if not retained_valid:
                    raise PublicationRuntime("owned temporary descriptor has an invalid type")
                current = self._stat_at(self._temp_name)
        except OSError as exc:
            raise PublicationRuntime("owned temporary cannot be inspected") from exc
        current_valid = is_actual_directory(current) if self._temp_kind == "directory" else is_actual_regular_file(current)
        if os.name != "nt":
            current_identity = _stat_identity(current)
        if not current_valid or retained_identity != self._temp_identity or current_identity != self._temp_identity:
            raise PublicationRuntime("owned temporary identity changed")
        return current

    def _capture_file_observable_at(
        self,
        parent_fd: int,
        name: str,
    ) -> ExpectedPublicationFile:
        """Capture one regular file relative to an already bound POSIX fd."""

        name = _ensure_name(name)
        try:
            initial = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if not is_actual_regular_file(initial):
                raise PublicationRuntime("quarantine child is not a regular file")
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
            fd = os.open(name, flags, dir_fd=parent_fd)
            try:
                opened = os.fstat(fd)
                if not is_actual_regular_file(opened) or _stat_identity(opened) != _stat_identity(initial):
                    raise PublicationRuntime("quarantine child identity changed while opening")
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(fd, 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                final = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if not is_actual_regular_file(final) or _stat_identity(final) != _stat_identity(opened):
                    raise PublicationRuntime("quarantine child identity changed while reading")
                payload = b"".join(chunks)
                return ExpectedPublicationFile(
                    identity=_stat_identity(final),
                    sha256=sha256_bytes(payload),
                    size=len(payload),
                    mtime_ns=int(final.st_mtime_ns),
                    payload=payload,
                )
            finally:
                os.close(fd)
        except PublicationRuntime:
            raise
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise PublicationRuntime("quarantine child cannot be captured") from exc

    def _move_no_replace_between(
        self,
        source_name: str,
        source_fd: int,
        target_name: str,
        target_fd: int,
    ) -> None:
        """Move one name between bound POSIX directories without replacement."""

        source_name = _ensure_name(source_name)
        target_name = _ensure_name(target_name)
        if sys.platform.startswith("linux"):
            _linux_no_replace(source_name, target_name, source_fd, target_fd)
        elif sys.platform == "darwin":
            _macos_no_replace(source_name, target_name, source_fd, target_fd)
        else:
            raise PublicationUnavailable("platform has no supported cleanup quarantine primitive")

    def _open_cleanup_quarantine(self) -> tuple[str, int]:
        """Create one operation-owned private POSIX cleanup directory."""

        if os.name == "nt" or self.directory_fd is None:
            raise PublicationUnavailable("cleanup quarantine is unavailable")
        self._check_handle()
        for _ in range(32):
            name = f".cleanup.{secrets.token_hex(16)}"
            try:
                os.mkdir(name, 0o700, dir_fd=self.directory_fd)
                flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(name, flags, dir_fd=self.directory_fd)
                item_stat = os.fstat(fd)
                if not is_actual_directory(item_stat):
                    os.close(fd)
                    raise OSError("cleanup quarantine is not a directory")
                self._quarantine_name = name
                self._quarantine_fd = fd
                self._quarantine_identity = _stat_identity(item_stat)
                return name, fd
            except FileExistsError:
                continue
            except OSError as exc:
                try:
                    os.rmdir(name, dir_fd=self.directory_fd)
                except Exception:
                    pass
                raise PublicationRuntime("cleanup quarantine cannot be created") from exc
        raise PublicationRuntime("cleanup quarantine name allocation failed")

    def _close_cleanup_quarantine(self) -> None:
        """Close and remove the empty operation-owned quarantine directory."""

        name = self._quarantine_name
        fd = self._quarantine_fd
        expected = self._quarantine_identity
        if name is None or fd is None or expected is None:
            return
        errors: list[BaseException] = []
        try:
            retained = os.fstat(fd)
            if not is_actual_directory(retained) or _stat_identity(retained) != expected:
                raise PublicationRuntime("cleanup quarantine identity changed")
            with os.scandir(fd) as iterator:
                if any(True for _ in iterator):
                    raise PublicationRuntime("cleanup quarantine is not empty")
            os.close(fd)
            self._quarantine_fd = None
            current = self._stat_at(name)
            if not is_actual_directory(current) or _stat_identity(current) != expected:
                raise PublicationRuntime("cleanup quarantine name identity changed")
            os.rmdir(name, dir_fd=self.directory_fd)
        except FileNotFoundError as exc:
            errors.append(PublicationBoundaryChanged("cleanup quarantine disappeared"))
            errors[-1].__cause__ = exc
        except (PublicationBoundaryChanged, PublicationRuntime) as exc:
            errors.append(exc)
        except OSError as exc:
            errors.append(PublicationRuntime("cleanup quarantine cannot be removed"))
            errors[-1].__cause__ = exc
        finally:
            if self._quarantine_fd is not None:
                try:
                    os.close(self._quarantine_fd)
                except OSError as exc:
                    errors.append(PublicationRuntime("cleanup quarantine descriptor cannot be closed"))
                    errors[-1].__cause__ = exc
            self._quarantine_name = None
            self._quarantine_fd = None
            self._quarantine_identity = None
        if errors:
            raise errors[0]

    def _before_cleanup_quarantine_move(
        self,
        name: str,
        expected: ExpectedPublicationFile,
    ) -> None:
        """Test seam for the check-to-quarantine linearization window."""

        del name, expected

    def _before_cleanup_delete(
        self,
        name: str,
        expected: ExpectedPublicationFile,
    ) -> None:
        """Test seam for the final quarantined-object deletion window."""

        del name, expected

    def _before_windows_delete_handle(
        self,
        name: str,
        expected: ExpectedPublicationFile,
    ) -> None:
        """Test seam for the check-to-HANDLE-delete linearization window."""

        del name, expected

    def _after_windows_delete_handle_open(
        self,
        name: str,
        expected: ExpectedPublicationFile,
        handle: int,
    ) -> None:
        """Test seam while the DELETE-capable HANDLE is held open."""

        del name, expected, handle

    def _restore_quarantined_file(
        self,
        original_name: str,
        quarantine_name: str,
        actual: ExpectedPublicationFile,
    ) -> bool:
        if self._quarantine_fd is None or self.directory_fd is None:
            raise PublicationRuntime("cleanup quarantine is not active")
        if self._exists_at(original_name):
            return False
        self._move_no_replace_between(
            quarantine_name,
            self._quarantine_fd,
            original_name,
            self.directory_fd,
        )
        restored = self._capture_file_observable_anchored(original_name)
        if restored != actual:
            raise PublicationRuntime("cleanup competitor could not be restored")
        return True

    def _quarantine_remove_expected_file(
        self,
        name: str,
        expected: ExpectedPublicationFile,
    ) -> None:
        """Move the candidate into private quarantine before deleting it."""

        if self.directory_fd is None:
            raise PublicationUnavailable("cleanup quarantine is unavailable")
        current = self._capture_file_observable_anchored(name)
        if current != expected:
            raise PublicationBoundaryChanged("publication cleanup candidate changed")
        self._before_cleanup_quarantine_move(name, expected)
        _quarantine_dir, quarantine_fd = self._open_cleanup_quarantine()
        quarantine_name = "candidate"
        primary: BaseException | None = None
        try:
            self._move_no_replace_between(name, self.directory_fd, quarantine_name, quarantine_fd)
            actual = self._capture_file_observable_at(quarantine_fd, quarantine_name)
            if actual != expected:
                if not self._restore_quarantined_file(name, quarantine_name, actual):
                    raise PublicationRuntime("cleanup competitor could not be safely restored")
                raise PublicationBoundaryChanged("publication cleanup candidate changed")
            self._before_cleanup_delete(quarantine_name, expected)
            after_hook = self._capture_file_observable_at(quarantine_fd, quarantine_name)
            if after_hook != expected:
                if not self._restore_quarantined_file(name, quarantine_name, after_hook):
                    raise PublicationRuntime("cleanup competitor could not be safely restored")
                raise PublicationBoundaryChanged("publication cleanup candidate changed")
            try:
                os.unlink(quarantine_name, dir_fd=quarantine_fd)
            except FileNotFoundError as exc:
                try:
                    restored = self._restore_quarantined_file(name, quarantine_name, expected)
                except BaseException as restore_exc:
                    raise PublicationRuntime("quarantined cleanup object disappeared") from restore_exc
                if restored:
                    raise PublicationRuntime("quarantined cleanup object disappeared") from exc
                raise PublicationRuntime("quarantined cleanup competitor cannot be preserved") from exc
            except OSError as exc:
                try:
                    restored = self._restore_quarantined_file(name, quarantine_name, expected)
                except BaseException as restore_exc:
                    raise PublicationRuntime("quarantined cleanup object cannot be removed") from restore_exc
                if restored:
                    raise PublicationRuntime("quarantined cleanup object cannot be removed") from exc
                raise PublicationRuntime("quarantined cleanup competitor cannot be preserved") from exc
        except BaseException as exc:
            primary = exc
            raise
        finally:
            try:
                self._close_cleanup_quarantine()
            except BaseException as cleanup_exc:
                if primary is None:
                    raise
                raise cleanup_exc from primary

    def _remove_tree_at(self, parent_fd: int, name: str, expected: tuple[Any, ...]) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        child_fd = os.open(name, flags, dir_fd=parent_fd)
        try:
            root_stat = os.fstat(child_fd)
            if not is_actual_directory(root_stat) or _stat_identity(root_stat) != expected:
                raise OSError("owned directory identity changed")
            with os.scandir(child_fd) as iterator:
                children = tuple(iterator)
            for entry in children:
                child_name = _ensure_name(entry.name)
                child_stat = os.stat(child_name, dir_fd=child_fd, follow_symlinks=False)
                if is_actual_directory(child_stat):
                    self._remove_tree_at(child_fd, child_name, _stat_identity(child_stat))
                elif is_actual_regular_file(child_stat):
                    os.unlink(child_name, dir_fd=child_fd)
                else:
                    raise OSError("owned directory contains an invalid child")
        finally:
            os.close(child_fd)
        os.rmdir(name, dir_fd=parent_fd)

    def _remove_owned_name(self, name: str, expected: tuple[Any, ...], *, directory: bool) -> None:
        _ensure_name(name)
        try:
            current = self._stat_at(name)
            if directory:
                if not is_actual_directory(current):
                    raise OSError("owned target is not a directory")
                current_identity = self._identity_at(name, "directory")
            else:
                if not is_actual_regular_file(current):
                    raise OSError("owned target is not a regular file")
                current_observable = self._capture_file_observable_anchored(name)
                current_identity = current_observable.identity
            if current_identity != expected:
                raise OSError("owned target identity changed")
            if directory:
                if self.directory_fd is not None:
                    self._remove_tree_at(self.directory_fd, name, expected)
                else:
                    shutil.rmtree(self.path / name)
            else:
                self._remove_expected_file_anchored(name, current_observable)
        except FileNotFoundError:
            return
        except PublicationUnavailable:
            raise
        except PublicationRuntime:
            raise
        except Exception as exc:
            raise PublicationRuntime("publication cleanup failed") from exc

    def _remove_expected_file_anchored(
        self,
        name: str,
        expected: ExpectedPublicationFile,
        *,
        retained_handle: int | None = None,
    ) -> None:
        """Remove only an exact, operation-observed regular file."""

        current = self._capture_file_observable_anchored(name)
        if current != expected:
            raise PublicationBoundaryChanged("publication displaced file changed")
        if os.name == "nt":
            self._windows_remove_file_by_handle(
                name,
                expected,
                retained_handle=retained_handle,
            )
        else:
            self._quarantine_remove_expected_file(name, expected)

    def _clear_temp_state(self) -> None:
        """Forget a consumed temporary without pathname cleanup."""

        try:
            self._close_temp_fd()
        except PublicationRuntime:
            pass
        try:
            self._close_temp_handle()
        except PublicationRuntime:
            pass
        self._temp_name = None
        self._temp_path = None
        self._temp_kind = None
        self._temp_fd = None
        self._temp_handle = None
        self._temp_identity = None
        self._temp_owned = False

    def cleanup_temp(self) -> None:
        if self._temp_name is None or self._temp_kind is None:
            return
        name = self._temp_name
        expected = self._temp_identity
        directory = self._temp_kind == "directory"
        if expected is None:
            raise PublicationRuntime("owned temporary identity is missing")
        self._close_temp_resources()
        if self._temp_owned:
            self._remove_owned_name(name, expected, directory=directory)
        self._temp_name = None
        self._temp_path = None
        self._temp_kind = None
        self._temp_fd = None
        self._temp_handle = None
        self._temp_identity = None
        self._temp_owned = False

    def _close_temp_fd(self) -> None:
        if self._temp_fd is None:
            return
        fd = self._temp_fd
        self._temp_fd = None
        try:
            os.close(fd)
        except OSError as exc:
            raise PublicationRuntime("owned temporary descriptor could not be closed") from exc

    def _close_temp_handle(self) -> None:
        if self._temp_handle is None:
            return
        handle = self._temp_handle
        self._temp_handle = None
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [ctypes.wintypes.HANDLE]
            close_handle.restype = ctypes.wintypes.BOOL
            if not close_handle(ctypes.wintypes.HANDLE(handle)):
                raise OSError(ctypes.get_last_error(), "CloseHandle temporary failed")
        except OSError as exc:
            raise PublicationRuntime("owned temporary HANDLE could not be closed") from exc
        except Exception as exc:
            raise PublicationRuntime("owned temporary HANDLE could not be closed") from exc

    def _close_temp_handle_safely(self) -> None:
        try:
            self._close_temp_handle()
        except PublicationRuntime:
            pass

    def _close_temp_resources(self) -> None:
        errors: list[BaseException] = []
        for close in (self._close_temp_fd, self._close_temp_handle):
            try:
                close()
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise PublicationRuntime("owned temporary descriptor cleanup failed") from errors[0]

    def _handle_target_identity_mismatch(
        self,
        target_name: str,
        target_identity: tuple[Any, ...],
        source_name: str,
        source_kind: str,
    ) -> None:
        """Fail closed without deleting a target that may be a competitor."""
        del target_name, target_identity, source_name, source_kind
        # A mismatched target is never owned by this writer.  The source name
        # may have disappeared because the primitive consumed it, but that is
        # not evidence that a different object now occupying the target name
        # belongs to this operation.  Leave both objects untouched.
        raise PublicationBoundaryChanged("published target identity changed")

    def _move_temp(self, target_name: str) -> None:
        target_name = _ensure_name(target_name)
        self._verify_temp()
        if self._exists_at(target_name):
            raise PublicationConflict("publication target already exists")
        source_name = self._temp_name
        source_path = self._temp_path
        source_kind = self._temp_kind
        if source_name is None or source_path is None or source_kind is None:
            raise PublicationRuntime("owned temporary is not active")
        try:
            if sys.platform.startswith("win"):
                _windows_no_replace(source_path, self.path / target_name, self.directory_handle)
            elif sys.platform == "darwin":
                _macos_no_replace(source_name, target_name, self.directory_fd, self.directory_fd)
            elif sys.platform.startswith("linux"):
                _linux_no_replace(source_name, target_name, self.directory_fd, self.directory_fd)
            else:
                raise PublicationUnavailable("platform has no supported atomic no-replace primitive")
        except (PublicationConflict, PublicationUnavailable, PublicationRuntime):
            raise
        except OSError as exc:
            raise PublicationRuntime("atomic no-replace publication failed") from exc
        target_identity: tuple[Any, ...] | None = None
        try:
            target_stat = self._stat_at(target_name)
            target_identity = self._identity_at(target_name, source_kind)
        except FileNotFoundError:
            raise PublicationRuntime("published target cannot be verified")
        except PublicationRuntime:
            raise
        except Exception as exc:
            raise PublicationRuntime("published target cannot be verified") from exc
        if target_identity != self._temp_identity:
            self._handle_target_identity_mismatch(target_name, target_identity, source_name, source_kind)
        if (source_kind == "directory" and not is_actual_directory(target_stat)) or (
            source_kind == "file" and not is_actual_regular_file(target_stat)
        ):
            raise PublicationRuntime("published target has an invalid type")
        # The no-replace move above is the publication commit point.  A
        # descriptor/handle-close failure after that point must not turn an
        # already published Story artifact into a reported failure or trigger
        # cleanup against a competing target.  Both close helpers clear their
        # slots before attempting the OS close.
        try:
            self._close_temp_fd()
        except PublicationRuntime:
            pass
        try:
            self._close_temp_handle()
        except PublicationRuntime:
            pass
        self._temp_name = None
        self._temp_path = None
        self._temp_kind = None
        self._temp_fd = None
        self._temp_handle = None
        self._temp_identity = None
        self._temp_owned = False
        try:
            # A POSIX directory can be renamed after the last guard and before
            # renameat2.  The dirfd still names the old directory; detect that
            # outcome and remove only the target just published by this writer.
            if self._capture_path_identity() != self._path_identity:
                self._remove_owned_name(target_name, target_identity, directory=source_kind == "directory")
                raise PublicationBoundaryChanged("publication parent path changed")
        except PublicationBoundaryChanged:
            raise
        except PublicationRuntime:
            raise
        except Exception as exc:
            raise PublicationRuntime("publication parent changed after atomic move") from exc

    def publish_bytes(
        self,
        target_name: str,
        payload: bytes,
        *,
        boundary_check: Callable[[], None] | None = None,
        before_atomic: Callable[[], None] | None = None,
    ) -> None:
        self.checkpoint(boundary_check)
        try:
            self.create_temp_file(target_name)
            self.checkpoint(boundary_check)
            self.write_temp_bytes(payload)
            self.checkpoint(boundary_check)
            if before_atomic is not None:
                before_atomic()
            # The hook represents the last-check-to-primitive scheduling
            # window.  Re-run the logical guard after it so a request-bound
            # Campaign or pending request mutation cannot pass into rename.
            if boundary_check is not None:
                self.checkpoint(boundary_check)
            else:
                self.check()
            self._move_temp(target_name)
        except BaseException as exc:
            try:
                self.cleanup_temp()
            except PublicationRuntime as cleanup_exc:
                raise cleanup_exc from exc
            raise

    def publish_adopted(
        self,
        target_name: str,
        *,
        boundary_check: Callable[[], None] | None = None,
        before_atomic: Callable[[], None] | None = None,
    ) -> None:
        try:
            self.checkpoint(boundary_check)
            if before_atomic is not None:
                before_atomic()
            if boundary_check is not None:
                self.checkpoint(boundary_check)
            else:
                self.check()
            self._move_temp(target_name)
        except BaseException as exc:
            try:
                self.cleanup_temp()
            except PublicationRuntime as cleanup_exc:
                raise cleanup_exc from exc
            raise

    def _next_displaced_name(self, target_name: str) -> str:
        target_name = _ensure_name(target_name)
        for _ in range(32):
            candidate = f".{target_name}.{secrets.token_hex(16)}.backup"
            if not self._exists_at(candidate):
                return candidate
        raise PublicationRuntime("publication backup name allocation failed")

    def _exchange_names(self, source_name: str, target_name: str) -> None:
        if self.directory_fd is None:
            raise PublicationUnavailable("anchored replace descriptor is unavailable")
        try:
            if sys.platform.startswith("linux"):
                _linux_exchange(source_name, target_name, self.directory_fd, self.directory_fd)
            elif sys.platform == "darwin":
                _macos_exchange(source_name, target_name, self.directory_fd, self.directory_fd)
            else:
                raise PublicationUnavailable("platform has no supported conditional replace primitive")
        except (PublicationUnavailable, PublicationRuntime):
            raise
        except OSError as exc:
            raise PublicationRuntime("atomic conditional exchange failed") from exc

    def _writer_target_matches(
        self,
        target_name: str,
        writer: ExpectedPublicationFile,
    ) -> bool:
        try:
            current = self._capture_file_observable_anchored(target_name)
        except Exception:
            return False
        return (
            current.identity == writer.identity
            and current.sha256 == writer.sha256
            and current.size == writer.size
            and current.payload == writer.payload
        )

    def _capture_optional_file_observable(
        self,
        name: str,
    ) -> ExpectedPublicationFile | None:
        try:
            return self._capture_file_observable_anchored(name)
        except FileNotFoundError:
            return None

    def _remove_displaced_if_expected(
        self,
        name: str,
        displaced: ExpectedPublicationFile,
        expected: ExpectedPublicationFile,
    ) -> None:
        """Remove a displaced object only when the original target is proven."""

        if displaced != expected:
            raise PublicationRuntime("publication displaced object is not the expected target")
        self._remove_expected_file_anchored(name, displaced)

    def _windows_retained_writer_matches(self, writer: ExpectedPublicationFile) -> bool:
        if os.name != "nt" or self._temp_handle is None or self._temp_identity is None:
            return False
        attributes, identity = self._windows_info_for_handle(self._temp_handle)
        return (
            not bool(attributes & self._FILE_ATTRIBUTE_DIRECTORY)
            and not bool(attributes & self._FILE_ATTRIBUTE_REPARSE_POINT)
            and identity == self._temp_identity == writer.identity
        )

    def _discard_windows_writer_replacement(self, writer: ExpectedPublicationFile) -> None:
        """Close and remove only the retained writer replacement."""

        name = self._temp_name
        if name is None:
            raise PublicationRuntime("Windows writer replacement name is unavailable")
        retained_handle = self._temp_handle
        current = self._capture_file_observable_anchored(name)
        if current != writer:
            raise PublicationRuntime("Windows writer replacement identity changed")
        self._remove_expected_file_anchored(
            name,
            writer,
            retained_handle=retained_handle,
        )
        self._close_temp_resources()
        self._clear_temp_state()

    def _discard_windows_expected_backup(
        self,
        name: str,
        expected: ExpectedPublicationFile,
    ) -> None:
        current = self._capture_file_observable_anchored(name)
        if current != expected:
            raise PublicationRuntime("Windows replacement backup identity changed")
        self._remove_expected_file_anchored(name, expected)

    def _restore_windows_expected_backup(
        self,
        target_name: str,
        backup_name: str,
        expected: ExpectedPublicationFile,
    ) -> None:
        """Restore an expected backup without replacing a competitor."""

        current_target = self._capture_optional_file_observable(target_name)
        if current_target is not None:
            # A target that is not the expected old target is a competitor and
            # must remain at the canonical name.  The backup is operation-
            # proven expected state and may be discarded safely.
            if current_target != expected:
                self._discard_windows_expected_backup(backup_name, expected)
                return
            self._discard_windows_expected_backup(backup_name, expected)
            return
        try:
            _windows_no_replace(
                self.path / backup_name,
                self.path / target_name,
                self.directory_handle,
            )
        except (PublicationConflict, PublicationUnavailable, PublicationRuntime) as exc:
            observed_target = self._capture_optional_file_observable(target_name)
            if observed_target is not None:
                if observed_target != expected:
                    self._discard_windows_expected_backup(backup_name, expected)
                    return
                self._discard_windows_expected_backup(backup_name, expected)
                return
            raise PublicationRuntime("Windows expected target could not be restored") from exc
        restored = self._capture_file_observable_anchored(target_name)
        if restored != expected:
            raise PublicationRuntime("Windows restored target observable changed")
        if self._capture_optional_file_observable(backup_name) is not None:
            raise PublicationRuntime("Windows replacement backup was not consumed")

    def _recover_windows_replace_failure(
        self,
        target_name: str,
        backup_name: str,
        expected: ExpectedPublicationFile,
        writer: ExpectedPublicationFile,
        failure: WindowsReplaceFailure,
    ) -> None:
        """Inspect and recover every documented ReplaceFileW failure layout."""

        outcome = f"{failure.outcome} ({failure.error_number})"
        try:
            self._check_handle()
            if not self._windows_retained_writer_matches(writer):
                raise PublicationRuntime("Windows retained writer HANDLE identity changed")
            replacement_name = self._temp_name
            if replacement_name is None:
                raise PublicationRuntime("Windows replacement temporary name is unavailable")
            target = self._capture_optional_file_observable(target_name)
            replacement = self._capture_optional_file_observable(replacement_name)
            backup = self._capture_optional_file_observable(backup_name)
        except PublicationRuntime:
            raise PublicationRuntime("Windows ReplaceFileW failure layout cannot be proven")
        except Exception as exc:
            raise PublicationRuntime("Windows ReplaceFileW failure layout cannot be inspected") from exc

        replacement_is_writer = replacement is not None and replacement == writer
        backup_is_expected = backup is not None and backup == expected
        target_is_expected = target is not None and target == expected

        # 1175/1176 normally leave the old target in place, the writer at its
        # temporary name, and no backup.  Do not infer this from the code: the
        # layout was captured above before cleanup.
        if target_is_expected and replacement_is_writer and backup is None:
            self._discard_windows_writer_replacement(writer)
            raise PublicationRuntime(f"Windows ReplaceFileW {outcome} failed before replacement")

        # 1177 can leave the old target in the backup name while the canonical
        # name is absent.  Restore it with no-replace semantics before deleting
        # the separately proven writer replacement.
        if target is None and backup_is_expected and replacement_is_writer:
            self._restore_windows_expected_backup(target_name, backup_name, expected)
            self._discard_windows_writer_replacement(writer)
            raise PublicationRuntime(f"Windows ReplaceFileW {outcome} partial replacement recovered")

        # A competitor may have occupied the canonical name before recovery.
        # Preserve it, discard only the proven expected backup, and then remove
        # only the retained writer object.
        if target is not None and not target_is_expected and backup_is_expected and replacement_is_writer:
            self._discard_windows_expected_backup(backup_name, expected)
            self._discard_windows_writer_replacement(writer)
            raise PublicationRuntime(f"Windows ReplaceFileW {outcome} competitor preserved")

        # Other documented errors may have changed attributes/streams or left
        # an unusual layout.  A writer object is still independently safe to
        # remove, but every other object remains untouched unless its exact
        # expected observable was proven above.
        if replacement_is_writer:
            self._discard_windows_writer_replacement(writer)
        raise PublicationRuntime(f"Windows ReplaceFileW {outcome} failure layout is not safely recoverable")

    def _recover_windows_displaced_restore_failure(
        self,
        target_name: str,
        displaced_name: str,
        backup_name: str,
        displaced: ExpectedPublicationFile,
        writer: ExpectedPublicationFile,
        failure: WindowsReplaceFailure,
    ) -> None:
        """Inspect a failed Windows restore without guessing ownership.

        The restore operation has a different source than the initial
        publication: ``displaced_name`` is the object being restored and the
        retained temporary HANDLE still identifies the writer currently at
        the target.  Keep those identities separate so a partial
        ReplaceFileW result cannot be mistaken for the initial layout.
        """

        outcome = f"{failure.outcome} ({failure.error_number})"
        try:
            self._check_handle()
            if not self._windows_retained_writer_matches(writer):
                raise PublicationRuntime("Windows retained writer HANDLE identity changed")
            current_target = self._capture_optional_file_observable(target_name)
            current_displaced = self._capture_optional_file_observable(displaced_name)
            current_backup = self._capture_optional_file_observable(backup_name)
        except PublicationRuntime:
            raise PublicationRuntime("Windows restore failure layout cannot be proven")
        except Exception as exc:
            raise PublicationRuntime("Windows restore failure layout cannot be inspected") from exc

        source_is_displaced = current_displaced is not None and current_displaced == displaced
        backup_is_writer = current_backup is not None and current_backup == writer

        # A documented partial move can leave the source at its temporary
        # name, the canonical name absent, and the old target at backup.  In
        # this restore operation the old target is the writer, so restore the
        # known displaced source with no-replace semantics and remove only
        # the exact writer backup.
        if current_target is None and source_is_displaced and backup_is_writer:
            _windows_no_replace(
                self.path / displaced_name,
                self.path / target_name,
                self.directory_handle,
            )
            restored = self._capture_file_observable_anchored(target_name)
            if restored != displaced:
                raise PublicationRuntime("Windows restore target observable changed")
            self._discard_windows_expected_backup(backup_name, writer)
            raise PublicationRuntime(f"Windows ReplaceFileW {outcome} restore recovered")

        # A competitor at the canonical name is never overwritten or
        # deleted.  A writer backup is independently proven and may be
        # removed; an unproven displaced object remains for bounded cleanup
        # reporting rather than being guessed away.
        if current_target is not None and current_target != writer and backup_is_writer:
            self._discard_windows_expected_backup(backup_name, writer)
            raise PublicationRuntime(f"Windows ReplaceFileW {outcome} restore competitor preserved")

        raise PublicationRuntime(f"Windows ReplaceFileW {outcome} restore layout is not safely recoverable")

    def _restore_displaced_after_exchange(
        self,
        target_name: str,
        displaced_name: str,
        displaced: ExpectedPublicationFile,
        writer: ExpectedPublicationFile,
    ) -> None:
        """Restore the displaced object and remove only the writer object."""

        if not self._writer_target_matches(target_name, writer):
            raise PublicationBoundaryChanged("publication target interference")
        if os.name == "nt":
            cleanup_name = self._next_displaced_name(target_name)
            try:
                _windows_replace_file(
                    self.path / displaced_name,
                    self.path / target_name,
                    self.path / cleanup_name,
                    self.directory_handle,
                )
            except WindowsReplaceFailure as failure:
                self._recover_windows_displaced_restore_failure(
                    target_name,
                    displaced_name,
                    cleanup_name,
                    displaced,
                    writer,
                    failure,
                )
            restored = self._capture_file_observable_anchored(target_name)
            if restored != displaced:
                raise PublicationBoundaryChanged("publication target interference")
            cleanup = self._capture_file_observable_anchored(cleanup_name)
            if cleanup.identity != writer.identity or cleanup.payload != writer.payload:
                raise PublicationBoundaryChanged("publication writer cleanup identity changed")
            self._remove_expected_file_anchored(cleanup_name, cleanup)
            return

        self._exchange_names(displaced_name, target_name)
        restored = self._capture_file_observable_anchored(target_name)
        if restored != displaced:
            raise PublicationBoundaryChanged("publication target interference")
        writer_at_source = self._capture_file_observable_anchored(displaced_name)
        if writer_at_source.identity != writer.identity or writer_at_source.payload != writer.payload:
            raise PublicationBoundaryChanged("publication writer cleanup identity changed")
        self._remove_expected_file_anchored(displaced_name, writer_at_source)

    def _replace_temp(
        self,
        target_name: str,
        *,
        expected_target: ExpectedPublicationFile,
    ) -> None:
        """Conditionally replace a regular target while retaining its old object."""

        target_name = _ensure_name(target_name)
        if not isinstance(expected_target, ExpectedPublicationFile):
            raise PublicationRuntime("expected target observable is required")
        self._verify_temp()
        source_name = self._temp_name
        source_path = self._temp_path
        source_kind = self._temp_kind
        if source_name is None or source_path is None or source_kind != "file":
            raise PublicationRuntime("owned temporary file is not active")

        try:
            writer = self._capture_file_observable_anchored(source_name)
            if writer.identity != self._temp_identity:
                raise PublicationRuntime("owned temporary identity changed")
            current_target = self._capture_file_observable_anchored(target_name)
        except FileNotFoundError as exc:
            raise PublicationBoundaryChanged("publication target observable changed") from exc
        except PublicationBoundaryChanged:
            raise
        except PublicationRuntime:
            raise
        except OSError as exc:
            raise PublicationRuntime("publication target observable cannot be inspected") from exc
        if current_target != expected_target:
            raise PublicationBoundaryChanged("publication target observable changed")

        exchanged = False
        displaced_name = target_name
        try:
            if os.name == "nt":
                displaced_name = self._next_displaced_name(target_name)
                try:
                    _windows_replace_file(
                        source_path,
                        self.path / target_name,
                        self.path / displaced_name,
                        self.directory_handle,
                    )
                except WindowsReplaceFailure as failure:
                    self._recover_windows_replace_failure(
                        target_name,
                        displaced_name,
                        expected_target,
                        writer,
                        failure,
                    )
            else:
                self._exchange_names(source_name, target_name)
                displaced_name = source_name
            exchanged = True

            displaced = self._capture_file_observable_anchored(displaced_name)
            try:
                writer_matches = self._writer_target_matches(target_name, writer)
            except BaseException:
                self._remove_displaced_if_expected(displaced_name, displaced, expected_target)
                self._clear_temp_state()
                raise
            if not writer_matches:
                self._remove_displaced_if_expected(displaced_name, displaced, expected_target)
                self._clear_temp_state()
                raise PublicationBoundaryChanged("publication target interference")

            if displaced != expected_target:
                self._restore_displaced_after_exchange(
                    target_name,
                    displaced_name,
                    displaced,
                    writer,
                )
                self._clear_temp_state()
                raise PublicationBoundaryChanged("publication target observable changed")

            try:
                self.check()
            except PublicationBoundaryChanged:
                self._restore_displaced_after_exchange(
                    target_name,
                    displaced_name,
                    displaced,
                    writer,
                )
                self._clear_temp_state()
                raise

            try:
                writer_matches = self._writer_target_matches(target_name, writer)
            except BaseException:
                self._remove_displaced_if_expected(displaced_name, displaced, expected_target)
                self._clear_temp_state()
                raise
            if not writer_matches:
                self._remove_displaced_if_expected(displaced_name, displaced, expected_target)
                self._clear_temp_state()
                raise PublicationBoundaryChanged("publication target interference")
            self.check()

            # The displaced object is exactly the observable captured at the
            # beginning.  Remove it only after all parent and target checks
            # have passed; the writer object remains at the canonical name.
            self._remove_expected_file_anchored(displaced_name, displaced)
            self._clear_temp_state()
        except BaseException:
            if exchanged:
                # Once names have exchanged, the source name no longer names
                # the writer temporary.  Never let generic temp cleanup
                # delete a displaced or competing object by identity guess.
                self._clear_temp_state()
            raise

    def publish_replace(
        self,
        target_name: str,
        payload: bytes,
        *,
        boundary_check: Callable[[], None] | None = None,
        before_atomic: Callable[[], None] | None = None,
        expected_target: ExpectedPublicationFile | None = None,
    ) -> None:
        """Write a sibling temporary and conditionally replace one target."""

        if not isinstance(expected_target, ExpectedPublicationFile):
            raise PublicationRuntime("expected target observable is required")
        self.checkpoint(boundary_check)
        try:
            try:
                current = self._capture_file_observable_anchored(_ensure_name(target_name))
            except FileNotFoundError as exc:
                raise PublicationBoundaryChanged("publication target observable changed") from exc
            if current != expected_target:
                raise PublicationBoundaryChanged("publication target observable changed")
            if expected_target.payload == payload:
                self.checkpoint(boundary_check)
                return
            self.create_temp_file(target_name)
            self.checkpoint(boundary_check)
            self.write_temp_bytes(payload)
            self.checkpoint(boundary_check)
            if before_atomic is not None:
                before_atomic()
            if boundary_check is not None:
                self.checkpoint(boundary_check)
            else:
                self.check()
            self._replace_temp(target_name, expected_target=expected_target)
        except BaseException as exc:
            try:
                self.cleanup_temp()
            except PublicationRuntime as cleanup_exc:
                raise cleanup_exc from exc
            raise

    def close_safely(self) -> None:
        try:
            self.close()
        except PublicationRuntime:
            pass

    def close(self) -> None:
        errors: list[BaseException] = []
        if self._temp_fd is not None or self._temp_handle is not None:
            try:
                self._close_temp_resources()
            except BaseException as exc:
                errors.append(exc)
        if self.directory_handle is not None:
            try:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                close_handle = kernel32.CloseHandle
                close_handle.argtypes = [ctypes.wintypes.HANDLE]
                close_handle.restype = ctypes.wintypes.BOOL
                if not close_handle(ctypes.wintypes.HANDLE(self.directory_handle)):
                    raise OSError(ctypes.get_last_error(), "CloseHandle failed")
            except BaseException as exc:
                errors.append(exc)
            self.directory_handle = None
        if self.directory_fd is not None:
            try:
                os.close(self.directory_fd)
            except BaseException as exc:
                errors.append(exc)
            self.directory_fd = None
        if errors:
            raise PublicationRuntime("publication descriptor cleanup failed") from errors[0]


def atomic_no_replace_move(source: str | Path, target: str | Path, *, directory: bool) -> None:
    """Compatibility wrapper that still uses an anchored parent binding."""

    source_path = lexical_absolute(source)
    target_path = lexical_absolute(target)
    binding: BoundPublicationDirectory | None = None
    try:
        binding = BoundPublicationDirectory.bind(target_path.parent)
        binding.adopt_existing(source_path, directory=directory)
        binding.publish_adopted(target_path.name)
    except (PublicationConflict, PublicationUnavailable, PublicationRuntime):
        raise
    except Exception as exc:
        raise PublicationRuntime("atomic no-replace publication failed") from exc
    finally:
        if binding is not None:
            try:
                if binding.temp_name is not None:
                    binding.cleanup_temp()
            finally:
                binding.close_safely()


def _cleanup_owned(path: Path | None) -> None:
    """Compatibility cleanup entry point, anchored to the temporary parent."""

    if path is None:
        return
    if not _lexists(path):
        return
    binding: BoundPublicationDirectory | None = None
    try:
        binding = BoundPublicationDirectory.bind(path.parent)
        item_stat = os.lstat(path)
        if is_actual_directory(item_stat):
            binding.adopt_existing(path, directory=True, owned=True)
        elif is_actual_regular_file(item_stat):
            binding.adopt_existing(path, directory=False, owned=True)
        else:
            raise PublicationRuntime("owned temporary has an invalid type")
        binding.cleanup_temp()
    except FileNotFoundError:
        return
    except (PublicationUnavailable, PublicationRuntime):
        raise
    except Exception as exc:
        raise PublicationRuntime("publication cleanup failed") from exc
    finally:
        if binding is not None:
            binding.close_safely()


def publish_bytes_no_replace(
    target: str | Path,
    payload: bytes,
    *,
    parent_binding: BoundPublicationDirectory | None = None,
    boundary_check: Callable[[], None] | None = None,
    before_atomic: Callable[[], None] | None = None,
) -> None:
    """Publish one regular artifact using an anchored parent binding."""

    if not isinstance(payload, bytes):
        raise PublicationRuntime("publication payload is not bytes")
    target_path = lexical_absolute(target)
    binding = parent_binding
    owns_binding = binding is None
    try:
        if binding is None:
            binding = BoundPublicationDirectory.bind(target_path.parent)
        elif binding.path != target_path.parent:
            raise PublicationRuntime("publication target is outside bound parent")
        binding.publish_bytes(
            target_path.name,
            payload,
            boundary_check=boundary_check,
            before_atomic=before_atomic,
        )
    finally:
        if owns_binding and binding is not None:
            try:
                if binding.temp_name is not None:
                    binding.cleanup_temp()
            finally:
                binding.close_safely()


def replace_bytes_atomic(
    target: str | Path,
    payload: bytes,
    *,
    parent_binding: BoundPublicationDirectory | None = None,
    boundary_check: Callable[[], None] | None = None,
    before_atomic: Callable[[], None] | None = None,
    expected_target: ExpectedPublicationFile | None = None,
) -> None:
    """Conditionally replace one existing derived file through an anchored boundary."""

    if not isinstance(payload, bytes):
        raise PublicationRuntime("publication payload is not bytes")
    if not isinstance(expected_target, ExpectedPublicationFile):
        raise PublicationRuntime("expected target observable is required")
    target_path = lexical_absolute(target)
    binding = parent_binding
    owns_binding = binding is None
    try:
        if binding is None:
            binding = BoundPublicationDirectory.bind(target_path.parent)
        elif binding.path != target_path.parent:
            raise PublicationRuntime("publication target is outside bound parent")
        binding.publish_replace(
            target_path.name,
            payload,
            boundary_check=boundary_check,
            before_atomic=before_atomic,
            expected_target=expected_target,
        )
    finally:
        if owns_binding and binding is not None:
            try:
                if binding.temp_name is not None:
                    binding.cleanup_temp()
            finally:
                binding.close_safely()


__all__ = [
    "BoundPublicationDirectory",
    "ERROR_UNABLE_TO_MOVE_REPLACEMENT",
    "ERROR_UNABLE_TO_MOVE_REPLACEMENT_2",
    "ERROR_UNABLE_TO_REMOVE_REPLACED",
    "ExpectedPublicationFile",
    "PublicationBoundaryChanged",
    "PublicationConflict",
    "PublicationRuntime",
    "PublicationUnavailable",
    "WindowsReplaceFailure",
    "atomic_no_replace_move",
    "publish_bytes_no_replace",
    "replace_bytes_atomic",
]
