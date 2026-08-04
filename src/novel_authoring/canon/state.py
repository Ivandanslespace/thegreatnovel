from __future__ import annotations

from pathlib import Path

from novel_authoring.canon.projection import CanonProjection, rebuild_projection
from novel_authoring.db.database import Database
from novel_authoring.utils import json_dumps, stable_id, utc_now


def _workspace_for_book(database: Database, book_id: str) -> Path:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"未知 book_id：{book_id}")
    return Path(str(row["workspace_root"]))


def create_snapshot(
    database: Database, book_id: str, *, edition_id: str | None = None
) -> dict[str, object]:
    from novel_authoring.edition import edition_workspace, resolve_edition_id

    selected_edition = resolve_edition_id(database, book_id, edition_id)
    projection = rebuild_projection(database, book_id, edition_id=selected_edition, persist=True)
    state_json = projection.canonical_json()
    state_hash = projection.sha256()
    snapshot_id = stable_id(
        "snapshot",
        book_id,
        selected_edition,
        str(projection.through_event_seq),
        state_hash,
    )
    workspace = edition_workspace(database, book_id, selected_edition)
    book_root = _workspace_for_book(database, book_id)
    if (book_root / "book.yaml").is_file():
        from novel_authoring.storage.layout import BookLayout

        snapshots_dir = BookLayout(book_root.parent).for_book(book_id).snapshots
    else:
        snapshots_dir = workspace / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshots_dir / f"{snapshot_id}.json"
    artifact = {
        "snapshot_id": snapshot_id,
        "book_id": book_id,
        "edition_id": selected_edition,
        "through_event_seq": projection.through_event_seq,
        "state_sha256": state_hash,
        "state": projection.model_dump(mode="json"),
    }
    temporary = snapshot_path.with_suffix(".json.tmp")
    temporary.write_text(json_dumps(artifact, indent=2) + "\n", encoding="utf-8")
    temporary.replace(snapshot_path)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO snapshots(
                snapshot_id, book_id, edition_id, through_event_seq, state_sha256,
                state_json, file_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                book_id,
                selected_edition,
                projection.through_event_seq,
                state_hash,
                state_json,
                str(snapshot_path),
                utc_now(),
            ),
        )
    return {
        "snapshot_id": snapshot_id,
        "path": str(snapshot_path),
        "edition_id": selected_edition,
        "through_event_seq": projection.through_event_seq,
        "state_sha256": state_hash,
    }


def projection_counts(projection: CanonProjection) -> dict[str, int]:
    return {
        field: len(getattr(projection, field))
        for field in (
            "facts",
            "timeline",
            "entities",
            "character_states",
            "knowledge",
            "relationships",
            "resources",
            "capabilities",
            "threads",
            "promises",
            "payoffs",
            "repetition",
            "style_profiles",
            "committed_chapters",
        )
    }
