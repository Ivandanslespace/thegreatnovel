"""Small strict helpers local to the Phase 9B2B Campaign boundary."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any, Iterable

from ..core.hashing import canonical_json
from .models import CampaignError


_COPY_CHUNK_SIZE = 1024 * 1024
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("non-standard JSON number")


def read_canonical_json(path: str | Path, *, code: str = "CAMPAIGN_INTEGRITY_MISMATCH") -> Any:
    source = Path(path)
    try:
        payload = source.read_bytes().decode("utf-8")
        parsed = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
        if canonical_json(parsed) != payload:
            raise ValueError("non-canonical JSON")
        return parsed
    except CampaignError:
        raise
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CampaignError(code, "canonical JSON artifact cannot be read") from exc


def write_canonical_json(path: str | Path, value: Any) -> None:
    try:
        Path(path).write_text(canonical_json(value), encoding="utf-8")
    except (OSError, TypeError, ValueError, UnicodeError) as exc:
        raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "canonical JSON artifact cannot be written") from exc


def _actual_regular_file(stat_result: os.stat_result) -> bool:
    return (
        stat.S_ISREG(stat_result.st_mode)
        and not stat.S_ISLNK(stat_result.st_mode)
        and not bool(getattr(stat_result, "st_file_attributes", 0) & _REPARSE_POINT)
    )


def _file_identity(stat_result: os.stat_result) -> tuple[int, int] | None:
    device = getattr(stat_result, "st_dev", None)
    inode = getattr(stat_result, "st_ino", None)
    if device is None or inode is None or (device == 0 and inode == 0):
        return None
    return device, inode


def _validate_copy_stat(stat_result: os.stat_result) -> None:
    if not _actual_regular_file(stat_result):
        raise OSError("source is not a regular file")


def _copy_one_file(source: Path, destination: Path) -> None:
    source_fd: int | None = None
    destination_fd: int | None = None
    failure: Exception | None = None
    close_failures: list[Exception] = []
    try:
        initial_stat = os.lstat(source)
        _validate_copy_stat(initial_stat)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        source_fd = os.open(str(source), flags)
        opened_stat = os.fstat(source_fd)
        _validate_copy_stat(opened_stat)
        final_stat = os.lstat(source)
        _validate_copy_stat(final_stat)
        identities = (_file_identity(initial_stat), _file_identity(opened_stat), _file_identity(final_stat))
        if identities[0] is not None and identities[1] is not None and identities[0] != identities[1]:
            raise OSError("source changed while opening")
        if identities[1] is not None and identities[2] is not None and identities[1] != identities[2]:
            raise OSError("source changed while opening")

        destination_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            destination_flags |= os.O_BINARY
        destination_fd = os.open(str(destination), destination_flags, 0o600)
        while True:
            chunk = os.read(source_fd, _COPY_CHUNK_SIZE)
            if not chunk:
                break
            pending = chunk
            while pending:
                written = os.write(destination_fd, pending)
                if written <= 0:
                    raise OSError("destination write made no progress")
                pending = pending[written:]
    except Exception as exc:
        failure = exc
    finally:
        if destination_fd is not None:
            try:
                os.close(destination_fd)
            except Exception as exc:
                close_failures.append(exc)
        if source_fd is not None:
            try:
                os.close(source_fd)
            except Exception as exc:
                close_failures.append(exc)

    if failure is not None or close_failures:
        cause = close_failures[0] if close_failures else failure
        raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "artifact copy failed") from cause


def copy_files(source_root: Path, destination_root: Path, names: Iterable[str]) -> None:
    try:
        destination_root.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "artifact copy failed") from exc
    for name in names:
        _copy_one_file(source_root / name, destination_root / name)


def safe_json_error(error: CampaignError) -> dict[str, Any]:
    return {"ok": False, "error": error.to_dict()}


__all__ = [
    "copy_files",
    "read_canonical_json",
    "safe_json_error",
    "sha256_bytes",
    "sha256_json",
    "write_canonical_json",
]
