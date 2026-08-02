"""Bounded subprocess edge for a local external narrator."""

from __future__ import annotations

import ctypes
import math
import os
import signal
import subprocess
import tempfile
import threading
import time
from typing import Any, Sequence

from .common import MAX_NARRATOR_STDOUT, PlayError, canonical_document, parse_json_document


DEFAULT_NARRATOR_TIMEOUT = 120.0
MIN_NARRATOR_TIMEOUT = 1.0
MAX_NARRATOR_TIMEOUT = 600.0
NARRATOR_CLEANUP_BUDGET = 5.0
_READER_CHUNK_SIZE = 64 * 1024


def _windows_last_error() -> int:
    """Read Win32 last-error without assuming a Windows ctypes runtime.

    The Job Object branch is exercised with a small fake kernel32 on POSIX in
    deterministic tests.  ``ctypes.get_last_error`` is only present on
    Windows, so a missing getter must become a bounded zero error rather than
    an unrelated AttributeError.
    """

    getter = getattr(ctypes, "get_last_error", None)
    if not callable(getter):
        return 0
    try:
        return int(getter())
    except (TypeError, ValueError, OSError):
        return 0


def validate_timeout(value: Any) -> float:
    if isinstance(value, bool):
        raise PlayError("INVALID_PLAY_INPUT", "narrator timeout is invalid")
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise PlayError("INVALID_PLAY_INPUT", "narrator timeout is invalid") from exc
    if not math.isfinite(timeout) or timeout < MIN_NARRATOR_TIMEOUT or timeout > MAX_NARRATOR_TIMEOUT:
        raise PlayError("INVALID_PLAY_INPUT", "narrator timeout is outside the allowed range")
    return timeout


def _validate_argv(argv: Sequence[str]) -> list[str]:
    if not isinstance(argv, (list, tuple)) or not argv:
        raise PlayError("INVALID_PLAY_INPUT", "narrator argv is invalid")
    if not all(isinstance(item, str) and item and "\x00" not in item for item in argv):
        raise PlayError("INVALID_PLAY_INPUT", "narrator argv is invalid")
    return list(argv)


class _WindowsJob:
    """The smallest operation-owned Job Object used by the narrator boundary."""

    def __init__(self, handle: Any, close_handle: Any) -> None:
        self._handle = handle
        self._close_handle = close_handle
        self._closed = False

    @classmethod
    def for_process(cls, process: Any) -> "_WindowsJob | None":
        if os.name != "nt":
            return None
        # Test doubles do not expose a native process handle.  Real Popen
        # instances do; a real process without one is not safe to contain.
        if not isinstance(getattr(process, "pid", None), int):
            return None
        process_handle = getattr(process, "_handle", None)
        if process_handle in (None, 0, -1):
            raise OSError("narrator process has no native handle")
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise OSError(_windows_last_error(), "CreateJobObjectW failed")

        class _BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class _ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        info = _ExtendedLimitInformation()
        # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
        info.BasicLimitInformation.LimitFlags = 0x2000
        if not kernel32.SetInformationJobObject(
            job,
            9,  # JobObjectExtendedLimitInformation
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            error = _windows_last_error()
            kernel32.CloseHandle(job)
            raise OSError(error, "SetInformationJobObject failed")
        if not kernel32.AssignProcessToJobObject(job, wintypes.HANDLE(process_handle)):
            error = _windows_last_error()
            kernel32.CloseHandle(job)
            raise OSError(error, "AssignProcessToJobObject failed")
        return cls(job, kernel32.CloseHandle)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if not self._close_handle(self._handle):
                raise OSError("CloseHandle failed")


class _ProcessContainment:
    def __init__(self, process: Any) -> None:
        self.process = process
        self.group_id = None if os.name == "nt" else getattr(process, "pid", None)
        self.job = _WindowsJob.for_process(process)

    def stop_tree(self) -> None:
        if self.job is not None:
            # Closing a kill-on-close Job Object is the Windows tree-kill
            # primitive.  Keep it operation-owned and close it exactly once.
            self.job.close()
            return
        if self.group_id is not None and hasattr(os, "killpg"):
            try:
                os.killpg(self.group_id, signal.SIGKILL)
                return
            except ProcessLookupError:
                return
        try:
            self.process.kill()
        except Exception:
            pass


def _kill_and_wait(process: Any, containment: _ProcessContainment | None = None, *, deadline: float | None = None) -> bool:
    """Best-effort bounded tree cleanup used on every failed outcome."""

    cleanup_ok = True
    try:
        if containment is not None:
            containment.stop_tree()
        elif process.poll() is None:
            process.kill()
    except Exception:
        cleanup_ok = False
        try:
            process.kill()
        except Exception:
            cleanup_ok = False
    wait_budget = 2.0 if deadline is None else max(0.0, deadline - time.monotonic())
    try:
        process.wait(timeout=wait_budget)
    except Exception:
        cleanup_ok = False
        try:
            process.kill()
        except Exception:
            cleanup_ok = False
        retry_budget = 2.0 if deadline is None else max(0.0, deadline - time.monotonic())
        if retry_budget > 0:
            try:
                process.wait(timeout=retry_budget)
            except Exception:
                cleanup_ok = False
    return cleanup_ok


def _bounded_close(stream: Any, deadline: float) -> bool:
    if stream is None:
        return True
    error: list[BaseException] = []

    def close_stream() -> None:
        try:
            stream.close()
        except BaseException as exc:
            error.append(exc)

    closer = threading.Thread(target=close_stream, name="tgn-play-narrator-close", daemon=True)
    closer.start()
    closer.join(max(0.0, deadline - time.monotonic()))
    return not closer.is_alive() and not error


def _close_stream(stream: Any) -> None:
    """Compatibility helper with a bounded close used by legacy edge tests."""

    _bounded_close(stream, time.monotonic() + NARRATOR_CLEANUP_BUDGET)


def run_narrator(
    argv: Sequence[str],
    request: dict[str, Any],
    *,
    timeout: float = DEFAULT_NARRATOR_TIMEOUT,
) -> dict[str, Any]:
    command = _validate_argv(argv)
    timeout_value = validate_timeout(timeout)
    try:
        request_bytes = canonical_document(request)
    except Exception as exc:
        raise PlayError("PLAY_NARRATOR_FAILED", "narration request cannot be encoded") from exc

    process: Any = None
    containment: _ProcessContainment | None = None
    stdout_stream: Any = None
    request_file: Any = None
    reader_done = threading.Event()
    reader_error: list[BaseException] = []
    captured = bytearray()
    overflow = threading.Event()
    started_at = time.monotonic()

    def read_stdout() -> None:
        try:
            while True:
                chunk = stdout_stream.read(_READER_CHUNK_SIZE)
                if not chunk:
                    break
                remaining = MAX_NARRATOR_STDOUT + 1 - len(captured)
                captured.extend(chunk[:remaining])
                if len(captured) > MAX_NARRATOR_STDOUT:
                    overflow.set()
                    break
        except BaseException as exc:  # reader failures are mapped at the boundary
            reader_error.append(exc)
        finally:
            reader_done.set()

    failure: PlayError | None = None
    reader: threading.Thread | None = None
    try:
        request_file = tempfile.TemporaryFile(mode="w+b")
        request_file.write(request_bytes)
        request_file.flush()
        request_file.seek(0)
        popen_kwargs: dict[str, Any] = {
            "stdin": request_file,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.DEVNULL,
            "shell": False,
        }
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **popen_kwargs)
        try:
            containment = _ProcessContainment(process)
        except Exception as exc:
            failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator process containment is unavailable")
            raise exc
        stdout_stream = process.stdout
        if stdout_stream is None:
            raise OSError("narrator stdout pipe was not created")
        reader = threading.Thread(target=read_stdout, name="tgn-play-narrator-reader", daemon=True)
        reader.start()
        deadline = started_at + timeout_value
        while not reader_done.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator timed out")
                break
            reader_done.wait(min(0.05, remaining))
        if failure is None and overflow.is_set():
            failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator output is too large")
        if failure is None and reader_error:
            failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator output could not be read")
        if failure is None:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator timed out")
        if failure is None and process.returncode != 0:
            failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator returned a non-zero exit code")
    except KeyboardInterrupt as exc:
        failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator was interrupted")
    except Exception as exc:
        if failure is None:
            failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator could not be started")
    finally:
        cleanup_deadline = min(started_at + timeout_value + NARRATOR_CLEANUP_BUDGET, time.monotonic() + NARRATOR_CLEANUP_BUDGET)
        tree_ok = True
        if process is not None and (failure is not None or containment is not None):
            tree_ok = _kill_and_wait(process, containment, deadline=cleanup_deadline)
        close_ok = _bounded_close(stdout_stream, cleanup_deadline)
        if reader is not None:
            reader.join(max(0.0, cleanup_deadline - time.monotonic()))
            # Process-group/Job-Object cleanup is operational containment,
            # not a security boundary. A live operation-owned reader is also
            # a failed cleanup postcondition; never return success beside it.
            if reader.is_alive():
                close_ok = False
        if request_file is not None:
            close_ok = _bounded_close(request_file, cleanup_deadline) and close_ok
        if (not tree_ok or not close_ok) and failure is None:
            failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator cleanup failed")

    if failure is not None:
        raise failure
    try:
        value = parse_json_document(bytes(captured), max_bytes=MAX_NARRATOR_STDOUT)
    except Exception as exc:
        raise PlayError("PLAY_NARRATOR_FAILED", "external narrator returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise PlayError("PLAY_NARRATOR_FAILED", "external narrator response must be a JSON object")
    return value


__all__ = [
    "DEFAULT_NARRATOR_TIMEOUT",
    "MAX_NARRATOR_TIMEOUT",
    "MIN_NARRATOR_TIMEOUT",
    "NARRATOR_CLEANUP_BUDGET",
    "run_narrator",
    "validate_timeout",
]
