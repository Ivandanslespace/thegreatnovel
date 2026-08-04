from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.config import load_settings
from novel_authoring.contracts.extraction import ExtractionOutput
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.workflows.extraction import (
    AgentContractError,
    build_reconcile_report,
    import_extraction_output,
    prepare_extraction_task,
    reconcile_fact,
    reconcile_record,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def prepared_book(tmp_path: Path) -> tuple[Database, Path, dict[str, object]]:
    source_root = tmp_path / "中文小说"
    source_root.mkdir()
    (source_root / FIXTURE.name).write_bytes(FIXTURE.read_bytes())
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="extract-book",
        title="合成求生小说",
        source_root=source_root,
        workspace_root=workspace,
        settings=load_settings(),
    )
    database = Database(workspace / "extract-book" / "state.sqlite3")
    task = prepare_extraction_task(
        database,
        "extract-book",
        chapter_start=1,
        chapter_end=2,
    )
    return database, workspace, task


def write_output(
    workspace: Path,
    task: dict[str, object],
    *,
    evidence_quote: str = "只有一瓶水和一枚生锈钥匙",
) -> Path:
    task_id = str(task["task_id"])
    metadata = json.loads(
        (workspace / "extract-book" / "agent_tasks" / task_id / "task.json").read_text(
            encoding="utf-8"
        )
    )
    span_one = metadata["source_spans"][0]["source_span_id"]
    payload = {
        "task_id": task_id,
        "records": [
            {
                "kind": "entity",
                "local_id": "lin-lan",
                "information_state": "INFERENCE",
                "confidence": 1.0,
                "source_span_ids": [span_one],
                "evidence_quote": "林岚",
                "entity_type": "character",
                "name": "林岚",
                "aliases": [],
            },
            {
                "kind": "fact",
                "local_id": "lin-lan-inventory",
                "information_state": "INFERENCE",
                "confidence": 1.0,
                "source_span_ids": [span_one],
                "evidence_quote": evidence_quote,
                "statement": "林岚醒来时只有一瓶水和一枚生锈钥匙",
                "subject_ref": "lin-lan",
                "predicate": "inventory_at_waking",
                "object_value": ["一瓶水", "一枚生锈钥匙"],
            },
            {
                "kind": "timeline",
                "local_id": "waking-time",
                "information_state": "INFERENCE",
                "confidence": 0.9,
                "source_span_ids": [span_one],
                "evidence_quote": "林岚",
                "label": "林岚醒来",
                "story_time_start": "雨夜",
                "story_time_end": "雨夜",
                "order_key": 1,
            },
        ],
        "notes": [],
    }
    output_path = workspace / "extract-book" / "agent_outputs" / task_id / "output.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return output_path


def test_prepare_task_is_bounded_and_emits_schema(tmp_path: Path) -> None:
    _, _, task = prepared_book(tmp_path)

    input_text = Path(str(task["input"])).read_text(encoding="utf-8")
    schema = json.loads(Path(str(task["schema"])).read_text(encoding="utf-8"))

    assert task["chapters"] == 2
    assert "雨夜醒来" in input_text
    assert "旧门之后" in input_text
    assert "风向的价格" not in input_text
    assert schema["additionalProperties"] is False
    assert "records" in schema["properties"]


def test_import_stays_in_inference_until_explicit_reconcile(tmp_path: Path) -> None:
    database, workspace, task = prepared_book(tmp_path)
    output_path = write_output(workspace, task)

    imported = import_extraction_output(
        database,
        "extract-book",
        str(task["task_id"]),
        output_path,
    )
    fact_id = str(imported["record_ids"]["lin-lan-inventory"])

    with sqlite3.connect(database.path) as connection:
        row = connection.execute(
            "SELECT status, source_span_id FROM facts WHERE fact_id=?", (fact_id,)
        ).fetchone()
        event_statuses = connection.execute(
            "SELECT DISTINCT status, information_state FROM events"
        ).fetchall()
    assert row is not None and row[0] == "INFERENCE" and row[1]
    assert event_statuses == [("PENDING", "INFERENCE")]
    assert rebuild_projection(database, "extract-book").facts == {}

    reconciled = reconcile_fact(
        database,
        "extract-book",
        fact_id,
        decision="accept-source",
        reason="原文直接列出背包内容",
    )
    projection = rebuild_projection(database, "extract-book")

    assert reconciled["status"] == "CANON"
    assert fact_id in projection.facts
    assert projection.facts[fact_id]["source_span_id"]


def test_output_schema_forbids_canon_from_agent() -> None:
    with pytest.raises(ValidationError):
        ExtractionOutput.model_validate(
            {
                "task_id": "task",
                "records": [
                    {
                        "kind": "fact",
                        "local_id": "f1",
                        "information_state": "CANON",
                        "confidence": 1,
                        "source_span_ids": ["span"],
                        "evidence_quote": "证据",
                        "statement": "事实",
                        "predicate": "is",
                        "object_value": True,
                    }
                ],
            }
        )


def test_non_fact_record_can_be_explicitly_reconciled(tmp_path: Path) -> None:
    database, workspace, task = prepared_book(tmp_path)
    imported = import_extraction_output(
        database,
        "extract-book",
        str(task["task_id"]),
        write_output(workspace, task),
    )
    timeline_id = str(imported["record_ids"]["waking-time"])
    entity_id = str(imported["record_ids"]["lin-lan"])

    timeline_result = reconcile_record(
        database,
        "extract-book",
        "timeline",
        timeline_id,
        decision="accept-source",
        reason="原文直接建立醒来顺序",
    )
    entity_result = reconcile_record(
        database,
        "extract-book",
        "entity",
        entity_id,
        decision="accept-source",
        reason="原文直接出现人物姓名",
    )
    projection = rebuild_projection(database, "extract-book", persist=False)
    report = build_reconcile_report(database, "extract-book")

    assert timeline_result["status"] == "CANON"
    assert entity_result["status"] == "CANON"
    assert timeline_id in projection.timeline
    assert report["pending_by_type"]["timeline"] == []
    assert report["pending_by_type"]["entity"] == []


def test_import_rejects_quote_outside_selected_source(tmp_path: Path) -> None:
    database, workspace, task = prepared_book(tmp_path)
    output_path = write_output(workspace, task, evidence_quote="原文中不存在的证据")

    with pytest.raises(AgentContractError, match="无法在来源中定位"):
        import_extraction_output(
            database,
            "extract-book",
            str(task["task_id"]),
            output_path,
        )


def test_reconcile_report_lists_conflicting_inferences(tmp_path: Path) -> None:
    database, workspace, task = prepared_book(tmp_path)
    output_path = write_output(workspace, task)
    imported = import_extraction_output(
        database, "extract-book", str(task["task_id"]), output_path
    )
    fact_id = str(imported["record_ids"]["lin-lan-inventory"])
    with database.connect() as connection:
        original = connection.execute(
            "SELECT * FROM facts WHERE fact_id=?", (fact_id,)
        ).fetchone()
        assert original is not None
        connection.execute(
            """
            INSERT INTO facts(
                fact_id, book_id, subject_id, predicate, object_json, statement,
                status, source_span_id, confidence, active, created_at
            ) VALUES ('conflict-fact', ?, ?, ?, ?, ?, 'INFERENCE', ?, 0.5, 1, ?)
            """,
            (
                "extract-book",
                original["subject_id"],
                original["predicate"],
                json.dumps(["两瓶水"], ensure_ascii=False),
                "背包里有两瓶水",
                original["source_span_id"],
                original["created_at"],
            ),
        )

    report = build_reconcile_report(database, "extract-book")

    assert len(report["pending_review"]) == 2
    assert len(report["conflicts"]) == 1
    assert Path(str(report["path"])).exists()
