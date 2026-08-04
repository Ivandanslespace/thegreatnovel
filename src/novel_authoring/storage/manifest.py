"""Canonical source-manifest resolution and compatibility-mirror helpers.

The ``_system`` copy is authoritative for a canonical Book Library book.  A
root-level ``source_manifest.json`` may exist only as a generated compatibility
mirror for older commands; it is never selected by new runtime code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novel_authoring.storage.models import BookPaths, LayoutError
from novel_authoring.utils import json_dumps, sha256_bytes, sha256_file

COMPATIBILITY_MIRROR_MARKER = "GENERATED_COMPATIBILITY_MIRROR"
COMPATIBILITY_MIRROR_FIELD = "mirror_of"
COMPATIBILITY_MIRROR_TARGET = "_system/source_manifest.json"


def authority_path(book_root: Path) -> Path:
    """Return the authoritative manifest path for a book root."""

    root = Path(book_root).expanduser().resolve()
    if (root / "book.yaml").is_file():
        return root / "_system" / "source_manifest.json"
    # Legacy books predate BookLayout and retain their old root manifest.
    return root / "source_manifest.json"


def authority_path_from_paths(paths: BookPaths) -> Path:
    return paths.source_manifest


def authority_path_from_database(database: Any, book_id: str) -> Path:
    """Resolve a manifest from the database without introducing a DB import."""

    row = database.scalar("SELECT workspace_root FROM books WHERE book_id=?", (book_id,))
    if row is None:
        raise LayoutError(f"未知 book_id：{book_id}")
    return authority_path(Path(str(row)))


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LayoutError(f"source manifest 无法读取: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LayoutError(f"source manifest 必须是 object: {path}")
    return value


def normalized_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Remove compatibility-only fields for mirror equality checks."""

    return {
        key: item
        for key, item in value.items()
        if key not in {"compatibility_marker", COMPATIBILITY_MIRROR_FIELD}
    }


def normalized_hash(value: dict[str, Any]) -> str:
    payload = json_dumps(normalized_payload(value), indent=2).encode("utf-8")
    return sha256_bytes(payload)


def manifest_hash(path: Path) -> str:
    """Hash a manifest using canonical or legacy compatibility semantics.

    Canonical ``_system/source_manifest.json`` files are normalized so a root
    compatibility mirror can carry marker fields without changing the anchor.
    Legacy root manifests retain their historical file-byte hash.
    """

    resolved = Path(path).expanduser().resolve()
    if resolved.parent.name != "_system":
        return sha256_file(resolved)
    return normalized_hash(_read_object(resolved))


def verify_mirror(book_root: Path) -> dict[str, Any]:
    """Verify the canonical manifest and optional generated root mirror."""

    root = Path(book_root).expanduser().resolve()
    authority = authority_path(root)
    authority_value = _read_object(authority)
    result: dict[str, Any] = {
        "authority": str(authority),
        "authority_sha256": normalized_hash(authority_value),
        "mirror": None,
        "mirror_sha256": None,
        "match": True,
    }
    if (root / "book.yaml").is_file():
        mirror = root / "source_manifest.json"
        result["mirror"] = str(mirror)
        if not mirror.is_file():
            result["match"] = False
            return result
        mirror_value = _read_object(mirror)
        result["mirror_sha256"] = normalized_hash(mirror_value)
        result["mirror_marker"] = mirror_value.get("compatibility_marker")
        result["mirror_of"] = mirror_value.get(COMPATIBILITY_MIRROR_FIELD)
        result["match"] = (
            mirror_value.get("compatibility_marker") == COMPATIBILITY_MIRROR_MARKER
            and mirror_value.get(COMPATIBILITY_MIRROR_FIELD)
            == COMPATIBILITY_MIRROR_TARGET
            and result["authority_sha256"] == result["mirror_sha256"]
        )
    return result


def write_compatibility_mirror(paths: BookPaths) -> Path:
    """Generate the deprecated root mirror from the authority file."""

    authority = _read_object(paths.source_manifest)
    mirror = dict(authority)
    mirror["compatibility_marker"] = COMPATIBILITY_MIRROR_MARKER
    mirror[COMPATIBILITY_MIRROR_FIELD] = COMPATIBILITY_MIRROR_TARGET
    path = paths.root / "source_manifest.json"
    path.write_text(json_dumps(mirror, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


__all__ = [
    "COMPATIBILITY_MIRROR_MARKER",
    "COMPATIBILITY_MIRROR_TARGET",
    "authority_path",
    "authority_path_from_database",
    "authority_path_from_paths",
    "manifest_hash",
    "normalized_hash",
    "verify_mirror",
    "write_compatibility_mirror",
]
