"""Operation Workspace resolver for canonical books.

All newly prepared extraction, metric, feature, initialization and writing
tasks for a Book Library book live below
``library/<book_id>/editions/<edition_id>/operations/<operation_id>``.  Legacy
workspace callers remain readable through their existing paths, but this
module never creates a legacy ``agent_tasks`` or ``agent_outputs`` directory
for a canonical book.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.models import OperationPaths
from novel_authoring.utils import json_dumps, utc_now


def book_root(database: Any, book_id: str) -> Path:
    row = database.scalar("SELECT workspace_root FROM books WHERE book_id=?", (book_id,))
    if row is None:
        raise ValueError(f"未知 book_id：{book_id}")
    return Path(str(row)).expanduser().resolve()


def canonical_book(database: Any, book_id: str) -> bool:
    return (book_root(database, book_id) / "book.yaml").is_file()


def operation_paths(
    database: Any,
    book_id: str,
    edition_id: str,
    operation_id: str,
) -> OperationPaths | None:
    """Return canonical paths, or ``None`` for a legacy book."""

    root = book_root(database, book_id)
    if not (root / "book.yaml").is_file():
        return None
    return BookLayout(root.parent).for_book(book_id).edition(edition_id).operation(operation_id)


def ensure_operation(
    database: Any,
    book_id: str,
    edition_id: str,
    operation_id: str,
    operation_kind: str,
    metadata: dict[str, Any] | None = None,
) -> OperationPaths | None:
    """Create an auditable canonical operation directory if applicable."""

    paths = operation_paths(database, book_id, edition_id, operation_id)
    if paths is None:
        return None
    for directory in paths.all_directories():
        directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "operation_id": operation_id,
        "operation_kind": operation_kind,
        "legacy_imported": False,
        "book_id": book_id,
        "edition_id": edition_id,
        "created_at": utc_now(),
    }
    if metadata:
        payload["metadata"] = metadata
    paths.manifest.write_text(json_dumps(payload, indent=2) + "\n", encoding="utf-8")
    paths.status.write_text(
        json_dumps(
            {"operation_id": operation_id, "status": "READY", "updated_at": utc_now()},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    paths.events.write_text("", encoding="utf-8")
    return paths


def find_operation(
    database: Any,
    book_id: str,
    edition_id: str,
    operation_id: str,
) -> OperationPaths | None:
    paths = operation_paths(database, book_id, edition_id, operation_id)
    if paths is None or not paths.root.is_dir():
        return None
    return paths


def read_operation_metadata(paths: OperationPaths) -> dict[str, Any]:
    try:
        value = json.loads(paths.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"operation manifest 无法读取: {paths.manifest}") from exc
    return value if isinstance(value, dict) else {}


__all__ = [
    "book_root",
    "canonical_book",
    "ensure_operation",
    "find_operation",
    "operation_paths",
    "read_operation_metadata",
]
