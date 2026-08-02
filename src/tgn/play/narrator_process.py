"""Bounded subprocess edge for a local external narrator."""

from __future__ import annotations

import subprocess
import math
from typing import Any, Sequence

from ..core.hashing import canonical_json
from .common import MAX_NARRATOR_STDOUT, PlayError, parse_json_document


DEFAULT_NARRATOR_TIMEOUT = 120.0
MIN_NARRATOR_TIMEOUT = 1.0
MAX_NARRATOR_TIMEOUT = 600.0


def validate_timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise PlayError("INVALID_PLAY_INPUT", "narrator timeout is invalid") from exc
    if not math.isfinite(timeout) or timeout < MIN_NARRATOR_TIMEOUT or timeout > MAX_NARRATOR_TIMEOUT:
        raise PlayError("INVALID_PLAY_INPUT", "narrator timeout is outside the allowed range")
    return timeout


def run_narrator(
    argv: Sequence[str],
    request: dict[str, Any],
    *,
    timeout: float = DEFAULT_NARRATOR_TIMEOUT,
) -> dict[str, Any]:
    if not isinstance(argv, (list, tuple)) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise PlayError("INVALID_PLAY_INPUT", "narrator argv is invalid")
    timeout_value = validate_timeout(timeout)
    try:
        completed = subprocess.run(
            list(argv),
            input=canonical_json(request).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            check=False,
            timeout=timeout_value,
        )
    except subprocess.TimeoutExpired as exc:
        raise PlayError("PLAY_NARRATOR_FAILED", "external narrator timed out") from exc
    except (OSError, ValueError) as exc:
        raise PlayError("PLAY_NARRATOR_FAILED", "external narrator could not be started") from exc
    if completed.returncode != 0:
        raise PlayError("PLAY_NARRATOR_FAILED", "external narrator returned a non-zero exit code")
    if len(completed.stdout) > MAX_NARRATOR_STDOUT:
        raise PlayError("PLAY_NARRATOR_FAILED", "external narrator output is too large")
    try:
        value = parse_json_document(completed.stdout, max_bytes=MAX_NARRATOR_STDOUT)
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
