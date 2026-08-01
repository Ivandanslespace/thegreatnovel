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
from pathlib import Path
from typing import Any

from .common import (
    is_actual_directory,
    is_actual_regular_file,
    lexical_absolute,
    read_regular_file,
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


class BoundPublicationDirectory:
    """One operation-local, caller-visible parent directory binding."""

    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_READ_ATTRIBUTES = 0x00000080
    _FILE_LIST_DIRECTORY = 0x00000001
    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
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
        self._temp_identity: tuple[Any, ...] | None = None
        self._temp_owned = False

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
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_info = kernel32.GetFileInformationByHandle
            get_info.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION)]
            get_info.restype = ctypes.wintypes.BOOL
            info = _BY_HANDLE_FILE_INFORMATION()
            if not get_info(ctypes.wintypes.HANDLE(self.directory_handle), ctypes.byref(info)):
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
            raise PublicationRuntime("publication parent HANDLE cannot be inspected") from exc

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
        self._temp_identity = _stat_identity(item_stat)
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
            item_stat = self._stat_at(self._temp_name) if os.name == "nt" else os.fstat(fd)
            if not is_actual_regular_file(item_stat) or _stat_identity(item_stat) != self._temp_identity:
                raise OSError("owned temporary identity changed")
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
        if os.name != "nt" and directory:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(name, flags, dir_fd=self.directory_fd)
            except OSError as exc:
                raise PublicationRuntime("publication source directory cannot be anchored") from exc
        self._temp_name = name
        self._temp_path = source_path
        self._temp_kind = "directory" if directory else "file"
        self._temp_fd = fd
        self._temp_identity = _stat_identity(item_stat)
        self._temp_owned = owned

    def _verify_temp(self) -> os.stat_result:
        if self._temp_name is None or self._temp_kind is None:
            raise PublicationRuntime("owned temporary is not active")
        try:
            item_stat = os.fstat(self._temp_fd) if self._temp_fd is not None and os.name != "nt" else self._stat_at(self._temp_name)
        except OSError as exc:
            raise PublicationRuntime("owned temporary cannot be inspected") from exc
        valid = is_actual_directory(item_stat) if self._temp_kind == "directory" else is_actual_regular_file(item_stat)
        if not valid or _stat_identity(item_stat) != self._temp_identity:
            raise PublicationRuntime("owned temporary identity changed")
        return item_stat

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
            if _stat_identity(current) != expected:
                raise OSError("owned target identity changed")
            if directory:
                if self.directory_fd is not None:
                    self._remove_tree_at(self.directory_fd, name, expected)
                else:
                    if not is_actual_directory(current):
                        raise OSError("owned target is not a directory")
                    shutil.rmtree(self.path / name)
            else:
                if not is_actual_regular_file(current):
                    raise OSError("owned target is not a regular file")
                if self.directory_fd is not None:
                    os.unlink(name, dir_fd=self.directory_fd)
                else:
                    os.unlink(self.path / name)
        except FileNotFoundError:
            return
        except PublicationRuntime:
            raise
        except Exception as exc:
            raise PublicationRuntime("publication cleanup failed") from exc

    def cleanup_temp(self) -> None:
        if self._temp_name is None or self._temp_kind is None:
            return
        name = self._temp_name
        expected = self._temp_identity
        directory = self._temp_kind == "directory"
        if expected is None:
            raise PublicationRuntime("owned temporary identity is missing")
        self._close_temp_fd()
        if self._temp_owned:
            self._remove_owned_name(name, expected, directory=directory)
        self._temp_name = None
        self._temp_path = None
        self._temp_kind = None
        self._temp_fd = None
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

    def _move_temp(self, target_name: str) -> None:
        target_name = _ensure_name(target_name)
        self._verify_temp()
        if self._exists_at(target_name):
            raise PublicationConflict("publication target already exists")
        source_name = self._temp_name
        source_path = self._temp_path
        source_kind = self._temp_kind
        owned_temp = self._temp_owned
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
            if (source_kind == "directory" and not is_actual_directory(target_stat)) or (
                source_kind == "file" and not is_actual_regular_file(target_stat)
            ):
                raise OSError("published target has an invalid type")
            target_identity = _stat_identity(target_stat)
        except FileNotFoundError:
            # Story-owned temporaries remain strict.  The compatibility
            # atomic_no_replace_move wrapper also supports tests that replace
            # a low-level primitive with a no-op, so an adopted source does
            # not require a second observable check here.
            if owned_temp:
                raise PublicationRuntime("published target cannot be verified")
        except PublicationRuntime:
            raise
        except Exception as exc:
            raise PublicationRuntime("published target cannot be verified") from exc
        # The no-replace move above is the publication commit point.  A
        # descriptor-close failure after that point must not turn an already
        # published Story artifact into a reported failure or trigger cleanup
        # against a competing target.  _close_temp_fd clears the owned fd
        # slot before attempting the close, so the later state reset remains
        # bounded even when the OS close itself fails.
        try:
            self._close_temp_fd()
        except PublicationRuntime:
            pass
        self._temp_name = None
        self._temp_path = None
        self._temp_kind = None
        self._temp_fd = None
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
        self.create_temp_file(target_name)
        try:
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

    def close_safely(self) -> None:
        try:
            self.close()
        except PublicationRuntime:
            pass

    def close(self) -> None:
        errors: list[BaseException] = []
        if self._temp_fd is not None:
            try:
                self._close_temp_fd()
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


__all__ = [
    "BoundPublicationDirectory",
    "PublicationBoundaryChanged",
    "PublicationConflict",
    "PublicationRuntime",
    "PublicationUnavailable",
    "atomic_no_replace_move",
    "publish_bytes_no_replace",
]
