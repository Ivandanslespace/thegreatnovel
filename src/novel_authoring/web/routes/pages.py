from __future__ import annotations

import json
from typing import Any

from novel_authoring.edition import edition_chapters, list_editions, resolve_edition_id
from novel_authoring.initialization.metrics import metric_bootstrap_status
from novel_authoring.initialization.service import latest_initialization
from novel_authoring.metrics.registry import load_registry
from novel_authoring.metrics.segments import list_segments, rebuild_segments
from novel_authoring.metrics.service import MetricsAssembler, ObservationResolver
from novel_authoring.planning.innovation import load_book_innovation_control
from novel_authoring.web.routes.jobs import list_handoffs


def _book_row(connection: Any, book_id: str) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM books WHERE book_id=?", (book_id,)).fetchone()
    if row is None:
        raise ValueError("book 不存在")
    return dict(row)


def home_context(database: Any, book_id: str) -> dict[str, Any]:
    database.initialize()
    edition_id = resolve_edition_id(database, book_id)
    with database.connect() as connection:
        book = _book_row(connection, book_id)
        chapters = edition_chapters(connection, book_id, edition_id)
        books = [
            dict(row)
            for row in connection.execute("SELECT * FROM books ORDER BY title, book_id")
        ]
    editions = [edition.model_dump(mode="json") for edition in list_editions(database, book_id)]
    return {
        "book": book,
        "books": books,
        "book_id": book_id,
        "edition_id": edition_id,
        "editions": editions,
        "chapters": chapters,
    }


def _metric_card_metadata(
    database: Any,
    book_id: str,
    edition_id: str,
    chapter: dict[str, Any],
    metrics: list[dict[str, Any]],
    observation_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    content_hash = str(chapter.get("content_sha256") or "")
    current_rows = [
        row
        for row in observation_rows
        if row.get("current")
        and not row.get("stale")
        and row.get("retracted_at") is None
        and str(row.get("effective_content_sha256") or "") == content_hash
    ]
    by_metric: dict[str, list[dict[str, Any]]] = {}
    for row in current_rows:
        by_metric.setdefault(str(row["metric_id"]), []).append(row)
    unknown_statuses = {
        "UNKNOWN",
        "UNKNOWN_AFTER_ANALYSIS",
        "MISSING",
        "NOT_ANALYZED",
        "MISSING_OPTIONAL_AUTHOR_INPUT",
    }
    for metric in metrics:
        metric_id = str(metric["metric_id"])
        rows = by_metric.get(metric_id, [])
        statuses = {str(row.get("status")) for row in rows}
        if not rows:
            analysis_state = "NOT_ANALYZED"
        elif str(metric.get("status")) == "NOT_APPLICABLE" or statuses == {"NOT_APPLICABLE"}:
            analysis_state = "NOT_APPLICABLE"
        elif statuses & unknown_statuses:
            analysis_state = "UNKNOWN"
        else:
            analysis_state = "ANALYZED"
        metric["analysis_state"] = analysis_state
        metric["observation_count"] = len(rows)
        metric["semantic_estimate_count"] = sum(
            1 for row in rows if str(row.get("source_kind")) == "SEMANTIC_ESTIMATE"
        )
        metric["last_analyzer_version"] = next(
            (str(row["analyzer_version"]) for row in rows if row.get("analyzer_version")),
            "—",
        )
        metric["import_tasks"] = sorted(
            {str(row["source_task_id"]) for row in rows if row.get("source_task_id")}
        )
        metric["evidence_count"] = sum(len(row.get("evidence_links", [])) for row in rows)
        metric["unknown_reasons"] = sorted(
            {
                str(row.get("reason"))
                for row in rows
                if str(row.get("status")) in unknown_statuses and row.get("reason")
            }
        )
        metric["observation_history"] = rows
    bootstrap: dict[str, Any] = {
        "status": "NOT_READY",
        "coverage": {
            "source_mapping_coverage": 0.0,
            "arc_output_coverage": 0.0,
            "chapter_semantic_feature_coverage": 0.0,
            "metric_observation_coverage": 0.0,
            "recent_detailed_metric_coverage": 0.0,
            "current_chapter_metric_coverage": 0.0,
        },
        "initialization_id": None,
    }
    initialization = latest_initialization(database, book_id, edition_id)
    if initialization:
        initialization_manifest = initialization.get("manifest") or {}
        initialization_id = initialization_manifest.get("initialization_id")
        if initialization_id:
            try:
                bootstrap = metric_bootstrap_status(
                    database,
                    book_id,
                    edition_id=edition_id,
                    initialization_id=str(initialization_id),
                )
            except (OSError, ValueError):
                bootstrap["initialization_id"] = initialization_id
    metadata = {
        "observation_count": len(current_rows),
        "semantic_estimate_count": sum(
            1 for row in current_rows if str(row.get("source_kind")) == "SEMANTIC_ESTIMATE"
        ),
        "evidence_count": sum(len(row.get("evidence_links", [])) for row in current_rows),
        "analyzer_versions": sorted(
            {str(row["analyzer_version"]) for row in current_rows if row.get("analyzer_version")}
        ),
        "import_tasks": sorted(
            {str(row["source_task_id"]) for row in current_rows if row.get("source_task_id")}
        ),
        "current_content_hash": content_hash,
        "bootstrap": bootstrap,
    }
    return metrics, metadata


def chapter_context(
    database: Any, book_id: str, edition_id: str, chapter_id: str
) -> dict[str, Any]:
    database.initialize()
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, edition_id)
        chapter_index = next(
            (index for index, item in enumerate(chapters) if str(item["chapter_id"]) == chapter_id),
            None,
        )
        if chapter_index is None:
            raise ValueError("章节不存在")
        chapter = chapters[chapter_index]
        book = _book_row(connection, book_id)
    segments = list_segments(database, book_id, edition_id=edition_id, chapter_id=chapter_id)
    if not segments:
        rebuild_segments(database, book_id, edition_id=edition_id)
        segments = list_segments(database, book_id, edition_id=edition_id, chapter_id=chapter_id)
    assembler = MetricsAssembler(database)
    run = assembler.rebuild(
        book_id, edition_id=edition_id, scope_type="CHAPTER", scope_id=chapter_id
    )
    latest = assembler.latest(book_id, edition_id, "CHAPTER", chapter_id)
    metrics = run["results"]
    missing_count = sum(len(item.get("missing_components", [])) for item in metrics)
    history = metric_history(database, book_id, edition_id, "CHAPTER", chapter_id)
    observation_rows = observation_history(database, book_id, edition_id, "CHAPTER", chapter_id)
    metrics, metric_metadata = _metric_card_metadata(
        database,
        book_id,
        edition_id,
        dict(chapter),
        metrics,
        observation_rows,
    )
    return {
        "book": book,
        "book_id": book_id,
        "edition_id": edition_id,
        "chapter": chapter,
        "chapters": chapters,
        "segments": segments,
        "bundle": run["bundle"],
        "run": run,
        "latest": latest,
        "metrics": metrics,
        "history": history,
        "observation_history": observation_rows,
        "metric_metadata": metric_metadata,
        "metric_bootstrap": metric_metadata["bootstrap"],
        "missing_count": missing_count,
        "previous_chapter": None
        if chapter_index == 0
        else chapters[chapter_index - 1],
        "next_chapter": None
        if chapter_index == len(chapters) - 1
        else chapters[chapter_index + 1],
        "source_info": {
            "relative_path": chapter.get("relative_path", ""),
            "source_span_id": chapter.get("source_span_id"),
            "content_sha256": chapter.get("content_sha256", ""),
            "document_status": chapter.get("document_status", ""),
        },
    }


def metric_history(
    database: Any, book_id: str, edition_id: str, scope_type: str, scope_id: str
) -> list[dict[str, Any]]:
    database.initialize()
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM metric_runs WHERE book_id=? AND edition_id=? "
            "AND scope_type=? AND scope_id=? ORDER BY created_at DESC",
            (book_id, edition_id, scope_type, scope_id),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["requested_metric_ids"] = json.loads(
                str(item.get("requested_metric_ids_json") or "[]")
            )
            item["disputed_components"] = json.loads(
                str(item.get("disputed_components_json") or "[]")
            )
            item["stale_components"] = json.loads(
                str(item.get("stale_components_json") or "[]")
            )
            result.append(item)
        return result


def observation_history(
    database: Any, book_id: str, edition_id: str, scope_type: str, scope_id: str
) -> list[dict[str, Any]]:
    """Return the append-only observation ledger, including retracted rows."""
    database.initialize()
    resolver = ObservationResolver(database, load_registry())
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM metric_observations WHERE book_id=? AND edition_id=? "
            "AND scope_type=? AND scope_id=? ORDER BY created_at DESC, observation_id DESC",
            (book_id, edition_id, scope_type, scope_id),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["value"] = json.loads(str(item.get("value_json") or "null"))
            except json.JSONDecodeError:
                item["value"] = item.get("value_json")
            links = connection.execute(
                "SELECT * FROM metric_evidence_links WHERE observation_id=? "
                "ORDER BY created_at, link_id",
                (str(row["observation_id"]),),
            ).fetchall()
            item["evidence_links"] = [dict(link) for link in links]
            resolved = resolver.resolve(
                book_id,
                edition_id,
                scope_type,
                scope_id,
                str(row["metric_id"]),
                str(row["component_id"]),
            )
            item["current"] = resolved.effective_observation_id == str(row["observation_id"])
            item["resolution_status"] = resolved.status.value
            item["effective_observation_id"] = resolved.effective_observation_id
            item["stale"] = bool(
                str(row["freshness_status"] or "FRESH") != "FRESH"
                or row["stale_reason"]
                or resolved.stale_reason
            )
            item["stale_reason"] = row["stale_reason"] or resolved.stale_reason
            result.append(item)
        return result


def dashboard_context(database: Any, book_id: str) -> dict[str, Any]:
    context = home_context(database, book_id)
    edition_id = context["edition_id"]
    chapters = context["chapters"]
    latest_chapter = chapters[-1] if chapters else None
    latest_run = None
    missing = disputed = stale = complete = incomplete = 0
    if latest_chapter is not None:
        run = MetricsAssembler(database).rebuild(
            book_id,
            edition_id=edition_id,
            scope_type="CHAPTER",
            scope_id=str(latest_chapter["chapter_id"]),
        )
        latest_run = run
        for item in run["results"]:
            if item["status"] == "COMPLETE":
                complete += 1
            else:
                incomplete += 1
            missing += len(item.get("missing_components", []))
            disputed += len(item.get("disputed_components", []))
            stale += len(item.get("stale_components", []))
    with database.connect() as connection:
        handoff_rows = connection.execute(
            "SELECT status, COUNT(*) AS count FROM workflow_handoffs WHERE book_id=? "
            "GROUP BY status",
            (book_id,),
        ).fetchall()
        handoffs = {str(row["status"]): int(row["count"]) for row in handoff_rows}
        latest_draft = connection.execute(
            "SELECT * FROM drafts WHERE book_id=? AND edition_id=? "
            "AND status IN ('VALIDATED', 'VALIDATED_DRAFT') ORDER BY created_at DESC LIMIT 1",
            (book_id, edition_id),
        ).fetchone()
        latest_campaign = connection.execute(
            "SELECT * FROM revision_campaigns WHERE book_id=? AND edition_id=? "
            "ORDER BY created_at DESC LIMIT 1",
            (book_id, edition_id),
        ).fetchone()
        latest_aggregate = connection.execute(
            "SELECT * FROM planning_aggregates WHERE book_id=? AND edition_id=? "
            "ORDER BY created_at DESC LIMIT 1",
            (book_id, edition_id),
        ).fetchone()
        rhythm_row = connection.execute(
            "SELECT snapshot_json FROM rhythm_diagnostic_snapshots WHERE book_id=? "
            "AND edition_id=? ORDER BY as_of_chapter DESC, created_at DESC LIMIT 1",
            (book_id, edition_id),
        ).fetchone()
        latest_ordinal = max((int(item["ordinal"]) for item in chapters), default=0)
        overdue_promises = connection.execute(
            "SELECT promise_id, statement, target_max_age, last_advanced_ordinal, status "
            "FROM promises WHERE book_id=? AND edition_id=? "
            "AND status NOT IN ('RESOLVED', 'CLOSED', 'PAID')",
            (book_id, edition_id),
        ).fetchall()
        overdue = [
            dict(row)
            for row in overdue_promises
            if row["target_max_age"] is not None
            and latest_ordinal - int(row["last_advanced_ordinal"] or 0)
            > int(row["target_max_age"])
        ]
    rhythm: dict[str, Any] = {}
    if rhythm_row is not None:
        try:
            rhythm = json.loads(str(rhythm_row["snapshot_json"] or "{}"))
        except json.JSONDecodeError:
            rhythm = {"raw": str(rhythm_row["snapshot_json"])}
    return {
        **context,
        "latest_chapter": latest_chapter,
        "latest_run": latest_run,
        "counts": {
            "complete": complete,
            "incomplete": incomplete,
            "missing": missing,
            "disputed": disputed,
            "stale": stale,
        },
        "handoffs": handoffs,
        "latest_draft": (
            None
            if latest_draft is None
            else {
                **dict(latest_draft),
                "display_status": (
                    "VALIDATED_DRAFT"
                    if str(latest_draft["status"]) == "VALIDATED"
                    else str(latest_draft["status"])
                ),
            }
        ),
        "latest_campaign": None if latest_campaign is None else dict(latest_campaign),
        "latest_aggregate": None if latest_aggregate is None else dict(latest_aggregate),
        "rhythm": rhythm,
        "overdue_promises": overdue,
    }


def workflow_context(database: Any, book_id: str) -> dict[str, Any]:
    return {
        "book_id": book_id,
        "handoffs": list_handoffs(database, book_id),
        "innovation_default": load_book_innovation_control(database, book_id).model_dump(
            mode="json"
        ),
    }
