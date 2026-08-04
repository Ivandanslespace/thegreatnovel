from __future__ import annotations

import json
from pathlib import Path

from novel_authoring.canon.events import EventStatus, EventStore
from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.canon.state import create_snapshot
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.domain.models import InformationStatus
from novel_authoring.ingest.service import ingest_book

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def test_snapshot_and_rebuild_are_deterministic(tmp_path: Path) -> None:
    source_root = tmp_path / "中文小说"
    source_root.mkdir()
    (source_root / FIXTURE.name).write_bytes(FIXTURE.read_bytes())
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="snapshot-book",
        title="合成求生小说",
        source_root=source_root,
        workspace_root=workspace,
        settings=load_settings(),
    )
    database = Database(workspace / "snapshot-book" / "state.sqlite3")
    store = EventStore(database)
    store.append(
        book_id="snapshot-book",
        event_type="CHARACTER_STATE_SET",
        aggregate_type="character",
        aggregate_id="lin-lan-current",
        payload={
            "state_id": "lin-lan-current",
            "character_id": "lin-lan",
            "goal": "守住气象站",
            "reason": "第一章明确目标",
        },
        source_kind="SOURCE_SPAN",
        source_id="chapter-1",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
        canon_commit_id="SOURCE_IMPORT",
    )
    store.append(
        book_id="snapshot-book",
        event_type="RESOURCE_SET",
        aggregate_type="resource",
        aggregate_id="battery",
        payload={
            "resource_id": "battery",
            "owner_id": "lin-lan",
            "quantity": 0,
            "reason": "第三章把电量用于无线电",
        },
        source_kind="SOURCE_SPAN",
        source_id="chapter-3",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
        canon_commit_id="SOURCE_IMPORT",
    )

    before = rebuild_projection(database, "snapshot-book")
    snapshot = create_snapshot(database, "snapshot-book")
    after = rebuild_projection(database, "snapshot-book")

    assert before.model_dump() == after.model_dump()
    assert before.sha256() == after.sha256() == snapshot["state_sha256"]
    artifact = json.loads(Path(str(snapshot["path"])).read_text(encoding="utf-8"))
    assert artifact["state_sha256"] == before.sha256()
    assert artifact["state"]["resources"]["battery"]["quantity"] == 0
    assert artifact["state"]["character_states"]["lin-lan-current"]["reason"]


def test_schema_migration_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "state.sqlite3")
    database.initialize()
    database.initialize()

    with database.connect() as connection:
        versions = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        event_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(events)").fetchall()
        }

    assert versions == [1, 2, 3, 4]
    assert {"information_state", "payload_sha256", "event_hash"} <= event_columns
