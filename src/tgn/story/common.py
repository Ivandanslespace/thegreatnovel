"""Strict, local helpers for the Phase 9C1 Story boundary."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from pathlib import Path
from typing import Any, Iterable

from ..core.hashing import canonical_json


_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
_MISSING = object()


def contains_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def validate_json_value(value: Any, *, path: str = "$") -> None:
    """Validate the subset of JSON accepted by Story artifacts."""

    if value is None or isinstance(value, bool):
        return
    if type(value) is int:
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return
    if isinstance(value, str):
        if contains_surrogate(value):
            raise ValueError(f"{path} contains a Unicode surrogate")
        value.encode("utf-8")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string object key")
            if contains_surrogate(key):
                raise ValueError(f"{path} contains a surrogate object key")
            validate_json_value(child, path=f"{path}/{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_json_value(child, path=f"{path}/{index}")
        return
    raise TypeError(f"{path} contains unsupported JSON value")


def canonical_bytes(value: Any) -> bytes:
    validate_json_value(value)
    payload = canonical_json(value)
    return payload.encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON number: {value}")


def parse_json_bytes(payload: bytes, *, require_canonical: bool = True) -> Any:
    if not isinstance(payload, bytes):
        raise TypeError("JSON payload must be bytes")
    text = payload.decode("utf-8")
    parsed = json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )
    validate_json_value(parsed)
    if require_canonical and canonical_bytes(parsed) != payload:
        raise ValueError("JSON is not canonical")
    return parsed


def safe_text(value: Any) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text.encode("utf-8", "replace").decode("utf-8")


def _is_reparse(stat_result: os.stat_result) -> bool:
    return bool(getattr(stat_result, "st_file_attributes", 0) & _REPARSE_POINT)


def is_actual_directory(stat_result: os.stat_result) -> bool:
    return stat.S_ISDIR(stat_result.st_mode) and not stat.S_ISLNK(stat_result.st_mode) and not _is_reparse(stat_result)


def is_actual_regular_file(stat_result: os.stat_result) -> bool:
    return stat.S_ISREG(stat_result.st_mode) and not stat.S_ISLNK(stat_result.st_mode) and not _is_reparse(stat_result)


def _identity(stat_result: os.stat_result) -> tuple[int, int] | None:
    device = getattr(stat_result, "st_dev", None)
    inode = getattr(stat_result, "st_ino", None)
    if device is None or inode is None or (device == 0 and inode == 0):
        return None
    return device, inode


def _close_descriptor(fd: int | None) -> None:
    if fd is not None:
        os.close(fd)


def read_regular_file(path: str | Path) -> tuple[bytes, os.stat_result]:
    """Read one regular artifact with lstat/open/fstat identity checks."""

    source = Path(path)
    initial = os.lstat(source)
    if not is_actual_regular_file(initial):
        raise OSError("artifact is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd: int | None = None
    try:
        fd = os.open(os.fspath(source), flags)
        opened = os.fstat(fd)
        if not is_actual_regular_file(opened):
            raise OSError("opened artifact is not a regular file")
        first_identity = _identity(initial)
        opened_identity = _identity(opened)
        if first_identity is not None and opened_identity is not None and first_identity != opened_identity:
            raise OSError("artifact changed while opening")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        final = os.lstat(source)
        if not is_actual_regular_file(final):
            raise OSError("artifact changed while reading")
        final_identity = _identity(final)
        if opened_identity is not None and final_identity is not None and opened_identity != final_identity:
            raise OSError("artifact changed while reading")
        return b"".join(chunks), opened
    finally:
        _close_descriptor(fd)


def read_canonical_json_file(path: str | Path) -> tuple[Any, bytes, os.stat_result]:
    payload, file_stat = read_regular_file(path)
    return parse_json_bytes(payload, require_canonical=True), payload, file_stat


def write_fd_all(fd: int, payload: bytes) -> None:
    pending = payload
    while pending:
        written = os.write(fd, pending)
        if written <= 0:
            raise OSError("write made no progress")
        pending = pending[written:]


def lexical_absolute(path: str | Path) -> Path:
    """Normalize a path lexically without resolving symlinks."""

    return Path(os.path.abspath(os.fspath(Path(path))))


def _path_components(path: Path) -> Iterable[Path]:
    current = Path(path.anchor) if path.anchor else Path()
    for part in path.parts:
        if part == path.anchor:
            continue
        current = current / part
        yield current


def validate_path_components(path: Path, *, allow_missing_final: bool) -> None:
    """Reject symlink/reparse components before trusting a caller path."""

    components = tuple(_path_components(path))
    for index, component in enumerate(components):
        try:
            item_stat = os.lstat(component)
        except FileNotFoundError:
            # Once a path component is absent, no descendant can be an
            # existing filesystem entry.  Do not call Path.exists() here:
            # that would follow an untrusted suffix and defeat this gate.
            if allow_missing_final:
                return
            raise
        if stat.S_ISLNK(item_stat.st_mode) or _is_reparse(item_stat):
            raise OSError("path contains a symlink or reparse point")


def require_actual_directory(path: str | Path, *, allow_missing: bool = False) -> Path:
    value = lexical_absolute(path)
    validate_path_components(value, allow_missing_final=allow_missing)
    try:
        item_stat = os.lstat(value)
    except FileNotFoundError:
        if allow_missing:
            return value
        raise
    if not is_actual_directory(item_stat):
        raise OSError("path is not an actual directory")
    return value


def list_actual_children(path: Path) -> tuple[os.DirEntry[str], ...]:
    children: list[os.DirEntry[str]] = []
    with os.scandir(path) as iterator:
        for entry in iterator:
            children.append(entry)
    return tuple(children)


def path_overlaps(left: Path, right: Path) -> bool:
    left_text = os.path.normcase(os.fspath(left)).rstrip("\\/")
    right_text = os.path.normcase(os.fspath(right)).rstrip("\\/")
    return left_text == right_text or left_text.startswith(right_text + os.sep) or right_text.startswith(left_text + os.sep)


def validate_story_campaign_separation(story_dir: str | Path, campaign_dir: str | Path, *, story_may_be_missing: bool) -> tuple[Path, Path]:
    story = require_actual_directory(story_dir, allow_missing=story_may_be_missing)
    campaign = require_actual_directory(campaign_dir, allow_missing=False)
    if path_overlaps(story, campaign):
        raise ValueError("Story and Campaign directories overlap")
    parent = story.parent
    require_actual_directory(parent, allow_missing=False)
    return story, campaign


def validate_stable_id(value: Any, field: str) -> str:
    import re

    if not isinstance(value, str) or re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value) is None:
        raise ValueError(f"{field} is not a stable ID")
    return value


def validate_hash(value: Any, field: str) -> str:
    import re

    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{field} is not a lowercase SHA-256")
    return value


def strict_int(value: Any, field: str, *, positive: bool = False, nonnegative: bool = False) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be an integer")
    if positive and value <= 0:
        raise ValueError(f"{field} must be positive")
    if nonnegative and value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def validate_prose(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("prose must be a string")
    if not value or len(value) > 20_000:
        raise ValueError("prose length is outside the bounded range")
    if value != value.strip() or "\x00" in value or "\r" in value or contains_surrogate(value):
        raise ValueError("prose contains invalid text")
    value.encode("utf-8")
    return value


__all__ = [
    "canonical_bytes",
    "contains_surrogate",
    "is_actual_directory",
    "is_actual_regular_file",
    "lexical_absolute",
    "list_actual_children",
    "parse_json_bytes",
    "path_overlaps",
    "read_canonical_json_file",
    "read_regular_file",
    "require_actual_directory",
    "safe_text",
    "sha256_bytes",
    "sha256_json",
    "strict_int",
    "validate_json_value",
    "validate_prose",
    "validate_hash",
    "validate_stable_id",
    "validate_story_campaign_separation",
    "write_fd_all",
]
