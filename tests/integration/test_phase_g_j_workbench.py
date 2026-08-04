from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.metrics.models import ObservationSourceKind
from novel_authoring.metrics.service import (
    MetricObservationService,
    MetricsAssembler,
    ObservationInput,
    ObservationResolver,
)
from novel_authoring.planning.aggregates import build_planning_aggregate
from novel_authoring.web.app import create_app, serve
from novel_authoring.workflows.handoffs import (
    WorkflowHandoffResult,
    create_continuation_handoff,
    read_waiting_for_user,
    record_user_response,
    write_waiting_for_user,
)


def _book(tmp_path: Path, book_id: str = "phase-g-book") -> tuple[Database, str, str]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "synthetic.md").write_text(
        "第1章 测试\n\n<script>alert(1)</script>\n\n第二段证据。\n\n"
        "第2章 后续\n\n灯塔把坐标藏进潮声。\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id=book_id,
        title="合成工作台",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
    )
    database = Database(workspace / book_id / "state.sqlite3")
    with database.connect() as connection:
        chapter = connection.execute(
            "SELECT chapter_id, content_sha256 FROM chapters ORDER BY ordinal DESC LIMIT 1"
        ).fetchone()
    assert chapter is not None
    return database, str(chapter["chapter_id"]), str(chapter["content_sha256"])


def test_scope_resolver_retraction_and_planning_aggregate(tmp_path: Path) -> None:
    database, chapter_id, content_hash = _book(tmp_path)
    service = MetricObservationService(database)
    semantic = service.append(
        ObservationInput(
            book_id="phase-g-book",
            edition_id="base",
            scope_type="CHAPTER",
            scope_id=chapter_id,
            metric_id="pressure",
            component_id="threat",
            value=70,
            source_kind=ObservationSourceKind.SEMANTIC_ESTIMATE,
            reason="semantic",
            chapter_id=chapter_id,
            effective_content_sha256=content_hash,
        )
    )
    author = service.append(
        ObservationInput(
            book_id="phase-g-book",
            edition_id="base",
            scope_type="CHAPTER",
            scope_id=chapter_id,
            metric_id="pressure",
            component_id="threat",
            value=85,
            source_kind=ObservationSourceKind.AUTHOR_INPUT,
            reason="作者修正",
            chapter_id=chapter_id,
            effective_content_sha256=content_hash,
        )
    )
    resolver = ObservationResolver(database)
    selected = resolver.resolve(
        "phase-g-book", "base", "CHAPTER", chapter_id, "pressure", "threat"
    )
    assert selected.effective_observation_id == author
    assert selected.selected_reason
    MetricObservationService(database).retract(author, reason="撤回作者修正")
    restored = resolver.resolve(
        "phase-g-book", "base", "CHAPTER", chapter_id, "pressure", "threat"
    )
    assert restored.effective_observation_id == semantic
    with database.connect() as connection:
        old = connection.execute(
            "SELECT value_json, retracted_at FROM metric_observations WHERE observation_id=?",
            (author,),
        ).fetchone()
    assert old is not None and json.loads(str(old["value_json"])) == 85
    assert old["retracted_at"] is not None

    chapter_run = MetricsAssembler(database).rebuild(
        "phase-g-book", scope_type="CHAPTER", scope_id=chapter_id
    )
    assert chapter_run["requested_metric_ids"]
    assert all(item["metric_id"] != "candidate_score" for item in chapter_run["results"])
    with pytest.raises(ValueError, match="不能在 CHAPTER"):
        MetricsAssembler(database).rebuild(
            "phase-g-book",
            scope_type="CHAPTER",
            scope_id=chapter_id,
            requested_metric_ids=["candidate_score"],
        )
    window_run = MetricsAssembler(database).rebuild(
        "phase-g-book", scope_type="WINDOW", scope_id="window-1"
    )
    assert window_run["requested_metric_ids"] == ["repetition_fatigue", "rhythm_diagnostics"]
    aggregate = build_planning_aggregate(database, "phase-g-book")
    assert chapter_run["run_id"] in aggregate["metric_run_ids"]
    assert window_run["run_id"] in aggregate["metric_run_ids"]
    rebuilt = build_planning_aggregate(database, "phase-g-book")
    assert aggregate["bundle_hash"] == rebuilt["bundle_hash"]


def test_workbench_escapes_xss_and_requires_csrf(tmp_path: Path) -> None:
    database, _, _ = _book(tmp_path, "web-book")
    with database.connect() as connection:
        row = connection.execute(
            "SELECT chapter_id FROM chapters ORDER BY ordinal LIMIT 1"
        ).fetchone()
    assert row is not None
    chapter_id = str(row["chapter_id"])
    app = create_app(database, book_id="web-book")
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(f"/books/web-book/editions/base/chapters/{chapter_id}")
    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text
    assert "&lt;/script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text
    assert "innerHTML" not in response.text
    assert "API Key" not in response.text
    assert "model_id" not in response.text
    assert client.post(
        "/api/books/web-book/editions/base/metrics/recompute",
        json={"scope_type": "CHAPTER", "scope_id": chapter_id},
    ).status_code == 403
    missing = client.get("/books/web-book/editions/base/chapters/not-found")
    assert missing.status_code == 404
    with pytest.raises(ValueError):
        serve(database, host="0.0.0.0")


def test_handoff_waiting_contract_and_user_response(tmp_path: Path) -> None:
    database, _, _ = _book(tmp_path, "handoff-g-book")
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO rhythm_diagnostic_snapshots(
                snapshot_id, book_id, edition_id, as_of_chapter, as_of_event_seq,
                projection_hash, config_hash, analyzer_versions_json, snapshot_json, created_at
            ) VALUES ('handoff-g-rhythm', 'handoff-g-book', 'base', 2, 0,
                      'projection', 'config', '{}', '{}', 'now')
            """
        )
    handoff = create_continuation_handoff(
        database, "handoff-g-book", requested_stage="PLAN_ONLY"
    )
    assert handoff["prompt"].startswith("$process-novel-handoff")
    handoff_id = str(handoff["handoff_id"])
    waiting = write_waiting_for_user(
        database,
        handoff_id,
        {
            "question_id": "choose-route",
            "question": "是否回应无线电？",
            "reason": "两个候选都能通过硬门",
            "options": ["回应", "保持沉默"],
            "related_artifacts": [],
            "required_author_decision": "选择路线",
        },
    )
    assert waiting["question_id"] == "choose-route"
    assert read_waiting_for_user(database, handoff_id) == waiting
    response = record_user_response(database, handoff_id, {"choice": "回应"})
    assert response["response"]["choice"] == "回应"
    task_before = Path(str(handoff["task_directory"])) / "task.json"
    task_text = task_before.read_text(encoding="utf-8")
    assert task_before.read_text(encoding="utf-8") == task_text
    with pytest.raises(ValueError):
        WorkflowHandoffResult.model_validate(
            {
                "handoff_id": handoff_id,
                "handoff_type": "CONTINUATION",
                "requested_stage": "DRAFT_AND_VALIDATE",
                "completed_stage": "VALIDATED_DRAFT",
                "book_id": "handoff-g-book",
                "edition_id": "base",
                "status": "VALIDATED_DRAFT",
                "draft_id": None,
                "canon_committed": False,
                "edition_activated": False,
                "base_event_seq": 0,
                "base_projection_hash": "x",
            }
        )
