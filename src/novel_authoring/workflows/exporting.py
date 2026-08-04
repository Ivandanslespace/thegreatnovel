from __future__ import annotations

from pathlib import Path
from typing import Any

from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.canon.state import projection_counts
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import verify_sources
from novel_authoring.planning.boundary import _workspace
from novel_authoring.utils import json_dumps, stable_id, utc_now


class ExportWorkflowError(RuntimeError):
    pass


def _rows(connection: Any, sql: str, parameters: tuple[object, ...]) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, parameters).fetchall()]


def export_book(
    database: Database,
    book_id: str,
    output_root: Path | None = None,
) -> dict[str, object]:
    if not database.path.is_file():
        raise ExportWorkflowError(f"状态库不存在：{database.path}")
    projection = rebuild_projection(database, book_id, persist=False)
    workspace = _workspace(database, book_id)
    export_id = stable_id(
        "export", book_id, str(projection.through_event_seq), projection.sha256()
    )
    export_dir = (output_root or workspace / "exports") / export_id
    export_dir.mkdir(parents=True, exist_ok=True)
    with database.connect() as connection:
        chapters = _rows(
            connection,
            """
            SELECT c.chapter_id, c.ordinal, c.raw_heading, c.title,
                   c.content_sha256, d.relative_path, d.status AS document_status
            FROM chapters c JOIN source_documents d ON d.document_id=c.document_id
            WHERE c.book_id=? ORDER BY c.ordinal, c.created_at
            """,
            (book_id,),
        )
        directives = _rows(
            connection,
            """
            SELECT directive_id, directive_type, content, mode, status,
                   priority, source, created_at
            FROM author_directives WHERE book_id=? ORDER BY priority, created_at
            """,
            (book_id,),
        )
        candidates = _rows(
            connection,
            """
            SELECT candidate_id, task_id, rank, primary_thread_id,
                   primary_function, selection_status, status, score_json,
                   gate_report_json, created_at
            FROM candidate_plans WHERE book_id=? ORDER BY created_at, rank
            """,
            (book_id,),
        )
        contracts = _rows(
            connection,
            """
            SELECT contract_id, candidate_id, target_chapter_ordinal, mode,
                   contract_sha256, status, created_at
            FROM chapter_contracts WHERE book_id=? ORDER BY created_at
            """,
            (book_id,),
        )
        drafts = _rows(
            connection,
            """
            SELECT draft_id, contract_id, candidate_id, chapter_title,
                   content_sha256, status, revision, validation_run_id,
                   approved_at, committed_at, created_at
            FROM drafts WHERE book_id=? ORDER BY created_at
            """,
            (book_id,),
        )
        commits = _rows(
            connection,
            """
            SELECT commit_id, draft_id, event_start_seq, event_end_seq,
                   chapter_id, author_approval, committed_at
            FROM canon_commits WHERE book_id=? ORDER BY committed_at
            """,
            (book_id,),
        )
        approved_chapters = connection.execute(
            """
            SELECT c.content FROM chapters c
            JOIN source_documents d ON d.document_id=c.document_id
            WHERE c.book_id=? AND d.status='GENERATED_CANON'
            ORDER BY c.ordinal, c.created_at
            """,
            (book_id,),
        ).fetchall()
    source_report = verify_sources(book_id, workspace.parent)
    projection_path = export_dir / "canon_projection.json"
    audit_path = export_dir / "audit.json"
    approved_path = export_dir / "approved_canon.md"
    manifest_path = export_dir / "manifest.json"
    projection_path.write_text(
        json_dumps(projection.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    audit = {
        "book_id": book_id,
        "chapters": chapters,
        "author_directives": directives,
        "candidate_plans": candidates,
        "chapter_contracts": contracts,
        "drafts": drafts,
        "canon_commits": commits,
    }
    audit_path.write_text(json_dumps(audit, indent=2) + "\n", encoding="utf-8")
    approved_text = "\n\n".join(str(row["content"]).strip() for row in approved_chapters)
    approved_path.write_text(
        (approved_text + "\n") if approved_text else "",
        encoding="utf-8",
    )
    manifest = {
        "export_id": export_id,
        "book_id": book_id,
        "created_at": utc_now(),
        "through_event_seq": projection.through_event_seq,
        "projection_sha256": projection.sha256(),
        "projection_counts": projection_counts(projection),
        "source_verify": source_report,
        "files": {
            "canon_projection": projection_path.name,
            "audit": audit_path.name,
            "approved_canon": approved_path.name,
        },
    }
    manifest_path.write_text(json_dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        **manifest,
        "path": str(export_dir),
        "manifest": str(manifest_path),
    }
