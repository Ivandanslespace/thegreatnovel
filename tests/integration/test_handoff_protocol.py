from __future__ import annotations

import json
from pathlib import Path

import pytest

from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.utils import utc_now
from novel_authoring.workflows.handoffs import (
    HandoffStatus,
    HandoffWorkflowError,
    claim_handoff,
    create_continuation_handoff,
    update_handoff_status,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def test_handoff_files_claim_and_result_boundary(tmp_path: Path) -> None:
    source = tmp_path / "book"
    source.mkdir()
    (source / FIXTURE.name).write_bytes(FIXTURE.read_bytes())
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="handoff-book",
        title="合成求生小说",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
    )
    database = Database(workspace / "handoff-book" / "state.sqlite3")
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO rhythm_diagnostic_snapshots(
                snapshot_id, book_id, edition_id, as_of_chapter, as_of_event_seq,
                projection_hash, config_hash, analyzer_versions_json, snapshot_json, created_at
            ) VALUES (
                'rhythm-test', 'handoff-book', 'base', 3, 0,
                'projection', 'config', '{}', '{}', ?
            )
            """,
            (utc_now(),),
        )
    handoff = create_continuation_handoff(
        database, "handoff-book", requested_stage="PLAN_ONLY"
    )
    task_directory = Path(handoff["task_directory"])
    assert (task_directory / "task.json").is_file()
    task = json.loads((task_directory / "task.json").read_text(encoding="utf-8"))
    assert task["forbidden_actions"]
    claimed = claim_handoff(database, handoff["handoff_id"], "codex-desktop")
    assert claimed["status"] == HandoffStatus.CLAIMED
    with pytest.raises(HandoffWorkflowError):
        claim_handoff(database, handoff["handoff_id"], "second-thread")
    update_handoff_status(
        database,
        handoff["handoff_id"],
        HandoffStatus.RUNNING,
        claim_token=claimed["claim_token"],
    )
    with pytest.raises(HandoffWorkflowError):
        update_handoff_status(
            database,
            handoff["handoff_id"],
            HandoffStatus.COMPLETED,
            claim_token=claimed["claim_token"],
            result={
                "status": "VALIDATED_DRAFT",
                "canon_committed": True,
                "edition_activated": False,
            },
        )
