from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(material).hexdigest()[:24]}"


def json_dumps(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=indent)


def safe_book_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    if not normalized:
        raise ValueError("book_id 必须至少包含一个 ASCII 字母或数字")
    return normalized

