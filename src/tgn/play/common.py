"""Small boundary helpers for the thin Playable Client layer."""

from __future__ import annotations

import json
import math
import os
import stat
from pathlib import Path
from typing import Any, Iterable

from ..core.hashing import canonical_json


SUPPORTED_LOCALES = frozenset({"zh-CN", "en", "ar"})
MAX_NARRATOR_STDOUT = 1024 * 1024
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)

PLAY_ERROR_CODES = frozenset(
    {
        "INVALID_PLAY_INPUT",
        "PLAY_WORKSPACE_INCOMPLETE",
        "PLAY_CLIENT_INTEGRITY_MISMATCH",
        "PLAY_NARRATOR_FAILED",
        "PLAY_NARRATION_PENDING",
        "PLAY_CAMPAIGN_FAILED",
        "PLAY_STORY_FAILED",
    }
)


def _safe_text(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").encode("utf-8", "replace").decode("utf-8")


class PlayError(ValueError):
    """Stable, safe error at the Playable Client boundary."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        cause_code: str | None = None,
        exit_code: int = 2,
    ) -> None:
        self.code = code if code in PLAY_ERROR_CODES else "PLAY_STORY_FAILED"
        self.message = _safe_text(message)
        self.cause_code = _safe_text(cause_code) if cause_code else None
        self.exit_code = 3 if self.code == "PLAY_NARRATION_PENDING" else exit_code
        super().__init__(f"{self.code}: {self.message}")

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.cause_code is not None:
            value["cause_code"] = self.cause_code
        return value


def canonical_document(value: Any) -> bytes:
    validate_json_value(value)
    return canonical_json(value).encode("utf-8")


def validate_json_value(value: Any, *, path: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if type(value) is int:
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise ValueError(f"{path} contains a Unicode surrogate")
        value.encode("utf-8")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string object key")
            validate_json_value(child, path=f"{path}/{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_json_value(child, path=f"{path}/{index}")
        return
    raise TypeError(f"{path} contains an unsupported JSON value")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON number: {value}")


def parse_json_document(payload: bytes, *, max_bytes: int | None = None) -> Any:
    if not isinstance(payload, bytes):
        raise TypeError("JSON payload must be bytes")
    if max_bytes is not None and len(payload) > max_bytes:
        raise ValueError("JSON payload is too large")
    text = payload.decode("utf-8")
    value = json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )
    validate_json_value(value)
    return value


def _is_reparse_point(value: os.stat_result) -> bool:
    return bool(getattr(value, "st_file_attributes", 0) & _REPARSE_POINT)


def _is_actual_directory(value: os.stat_result) -> bool:
    return stat.S_ISDIR(value.st_mode) and not stat.S_ISLNK(value.st_mode) and not _is_reparse_point(value)


def _is_actual_regular_file(value: os.stat_result) -> bool:
    return stat.S_ISREG(value.st_mode) and not stat.S_ISLNK(value.st_mode) and not _is_reparse_point(value)


def lexical_absolute(value: str | Path) -> Path:
    try:
        return Path(os.path.abspath(os.fspath(Path(value))))
    except (TypeError, ValueError, OSError) as exc:
        raise PlayError("INVALID_PLAY_INPUT", "workspace path is invalid") from exc


def _components(value: Path) -> Iterable[Path]:
    current = Path(value.anchor) if value.anchor else Path()
    for part in value.parts:
        if part == value.anchor:
            continue
        current = current / part
        yield current


def _reject_untrusted_components(value: Path, *, allow_missing: bool) -> None:
    for component in _components(value):
        try:
            current = os.lstat(component)
        except FileNotFoundError:
            if allow_missing:
                return
            raise
        if stat.S_ISLNK(current.st_mode) or _is_reparse_point(current):
            raise OSError("workspace path contains a symlink or reparse point")


def ensure_new_workspace(value: str | Path) -> Path:
    workspace = lexical_absolute(value)
    try:
        _reject_untrusted_components(workspace, allow_missing=True)
        try:
            current = os.lstat(workspace)
        except FileNotFoundError:
            workspace.mkdir(parents=True)
            return workspace
        if not _is_actual_directory(current):
            raise OSError("workspace is not an actual directory")
        with os.scandir(workspace) as entries:
            if next(entries, None) is not None:
                raise FileExistsError("workspace is not empty")
        return workspace
    except PlayError:
        raise
    except Exception as exc:
        raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace must be absent or empty") from exc


def require_workspace(value: str | Path) -> Path:
    workspace = lexical_absolute(value)
    try:
        _reject_untrusted_components(workspace, allow_missing=False)
        current = os.lstat(workspace)
        if not _is_actual_directory(current):
            raise OSError("workspace is not an actual directory")
        with os.scandir(workspace) as entries:
            for entry in entries:
                if entry.name not in {"campaign", "story"}:
                    raise OSError("workspace contains an unknown client artifact")
                entry_stat = os.lstat(entry.path)
                if stat.S_ISLNK(entry_stat.st_mode) or _is_reparse_point(entry_stat):
                    raise OSError("workspace child is a symlink or reparse point")
        return workspace
    except PlayError:
        raise
    except Exception as exc:
        raise PlayError("PLAY_WORKSPACE_INCOMPLETE", "workspace is incomplete") from exc


def workspace_children(workspace: Path) -> tuple[Path, Path]:
    return workspace / "campaign", workspace / "story"


def parse_positive_integer(value: Any, field: str) -> int:
    if not isinstance(value, str) or not value or any(character not in "0123456789" for character in value):
        raise PlayError("INVALID_PLAY_INPUT", f"{field} must be a canonical positive integer")
    if value[0] == "0":
        raise PlayError("INVALID_PLAY_INPUT", f"{field} must be a canonical positive integer")
    try:
        result = int(value)
    except ValueError as exc:
        raise PlayError("INVALID_PLAY_INPUT", f"{field} is invalid") from exc
    if result <= 0:
        raise PlayError("INVALID_PLAY_INPUT", f"{field} must be positive")
    return result


def parse_nonnegative_integer(value: Any, field: str) -> int:
    if not isinstance(value, str) or not value or any(character not in "0123456789" for character in value):
        raise PlayError("INVALID_PLAY_INPUT", f"{field} must be a canonical non-negative integer")
    if len(value) > 1 and value[0] == "0":
        raise PlayError("INVALID_PLAY_INPUT", f"{field} must be a canonical non-negative integer")
    try:
        return int(value)
    except ValueError as exc:
        raise PlayError("INVALID_PLAY_INPUT", f"{field} is invalid") from exc


def read_external_json(path: str | Path, *, max_bytes: int = MAX_NARRATOR_STDOUT) -> Any:
    if os.fspath(path) == "-":
        raise PlayError("INVALID_PLAY_INPUT", "response file '-' is only valid on the process stdin boundary")
    source = lexical_absolute(path)
    try:
        initial = os.lstat(source)
        if not _is_actual_regular_file(initial):
            raise OSError("response file is not regular")
        with open(source, "rb") as handle:
            payload = handle.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ValueError("response file is too large")
        return parse_json_document(payload, max_bytes=max_bytes)
    except PlayError:
        raise
    except Exception as exc:
        raise PlayError("PLAY_NARRATOR_FAILED", "narrator response file is invalid") from exc


__all__ = [
    "MAX_NARRATOR_STDOUT",
    "PLAY_ERROR_CODES",
    "PlayError",
    "SUPPORTED_LOCALES",
    "canonical_document",
    "ensure_new_workspace",
    "lexical_absolute",
    "parse_json_document",
    "parse_nonnegative_integer",
    "parse_positive_integer",
    "read_external_json",
    "require_workspace",
    "validate_json_value",
    "workspace_children",
]
