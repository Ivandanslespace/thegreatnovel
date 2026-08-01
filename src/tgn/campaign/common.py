"""Small strict helpers local to the Phase 9B2B Campaign boundary."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from ..core.hashing import canonical_json
from .models import CampaignError


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


def copy_files(source_root: Path, destination_root: Path, names: Iterable[str]) -> None:
    destination_root.mkdir(parents=True, exist_ok=True)
    for name in names:
        source = source_root / name
        destination = destination_root / name
        try:
            if not source.is_file():
                raise OSError("source file missing")
            shutil.copyfile(source, destination)
        except (OSError, shutil.Error) as exc:
            raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "artifact copy failed") from exc


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
