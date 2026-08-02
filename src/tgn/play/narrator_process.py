"""Bounded subprocess edge for a local external narrator."""

from __future__ import annotations

import math
import subprocess
import tempfile
import threading
import time
from typing import Any, Sequence

from .common import MAX_NARRATOR_STDOUT, PlayError, canonical_document, parse_json_document


DEFAULT_NARRATOR_TIMEOUT = 120.0
MIN_NARRATOR_TIMEOUT = 1.0
MAX_NARRATOR_TIMEOUT = 600.0
_READER_CHUNK_SIZE = 64 * 1024


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


def _kill_and_wait(process: Any) -> None:
    """Best-effort bounded child cleanup used on every failed outcome."""

    try:
        if process.poll() is None:
            process.kill()
    except Exception:
        pass
    try:
        process.wait(timeout=2.0)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=2.0)
        except Exception:
            pass


def _close_stream(stream: Any) -> None:
    if stream is None:
        return
    try:
        stream.close()
    except Exception:
        pass


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
    stdout_stream: Any = None
    request_file: Any = None
    reader_done = threading.Event()
    reader_error: list[BaseException] = []
    captured = bytearray()
    overflow = threading.Event()

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
        process = subprocess.Popen(
            command,
            stdin=request_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
        stdout_stream = process.stdout
        if stdout_stream is None:
            raise OSError("narrator stdout pipe was not created")
        reader = threading.Thread(target=read_stdout, name="tgn-play-narrator-reader")
        reader.start()
        deadline = time.monotonic() + timeout_value
        while not reader_done.is_set():
            if overflow.is_set():
                failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator output is too large")
                break
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
        failure = PlayError("PLAY_NARRATOR_FAILED", "external narrator could not be started")
    finally:
        if process is not None and failure is not None:
            _kill_and_wait(process)
        _close_stream(stdout_stream)
        if reader is not None:
            reader.join()
        if request_file is not None:
            try:
                request_file.close()
            except Exception:
                if failure is None:
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
    "run_narrator",
    "validate_timeout",
]
