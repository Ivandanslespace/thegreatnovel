from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.db.database import Database
from novel_authoring.edition import (
    BASE_EDITION_ID,
    edition_chapters,
    edition_workspace,
    resolve_edition_id,
)
from novel_authoring.ingest.service import verify_sources
from novel_authoring.utils import json_dumps, stable_id, utc_now


class EditionExportError(RuntimeError):
    pass


def _rows(connection: Any, sql: str, params: tuple[object, ...]) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, params).fetchall()]


def export_edition(
    database: Database,
    book_id: str,
    edition_id: str | None = None,
    output_root: Path | None = None,
) -> dict[str, object]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    if selected == BASE_EDITION_ID:
        raise EditionExportError("base edition 请使用既有 export_book，以保持字节级兼容")
    projection = rebuild_projection(database, book_id, edition_id=selected, persist=False)
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, selected)
        variants = _rows(
            connection,
            """
            SELECT variant_id, campaign_id, unit_id, base_chapter_id,
                   base_source_span_id, base_content_sha256, title,
                   replacement_content_sha256, status, active, supersedes_variant_id,
                   revision_commit_id, created_at, approved_at
            FROM chapter_variants WHERE book_id=? AND edition_id=?
            ORDER BY base_chapter_id, created_at
            """,
            (book_id, selected),
        )
        campaigns = _rows(
            connection,
            "SELECT * FROM revision_campaigns WHERE book_id=? AND edition_id=? ORDER BY created_at",
            (book_id, selected),
        )
        units = _rows(
            connection,
            "SELECT * FROM revision_units WHERE book_id=? AND edition_id=? ORDER BY unit_order",
            (book_id, selected),
        )
        drafts = _rows(
            connection,
            """
            SELECT draft_id, campaign_id, unit_id, task_id, status,
                   replacement_sha256, base_content_sha256, validation_run_id,
                   approved_at, committed_at
            FROM revision_drafts
            WHERE book_id=? AND edition_id=? ORDER BY created_at
            """,
            (book_id, selected),
        )
        commits = _rows(
            connection,
            "SELECT * FROM revision_commits WHERE book_id=? AND edition_id=? ORDER BY committed_at",
            (book_id, selected),
        )
        edition_row = connection.execute(
            """
            SELECT parent_edition_id, source_manifest_sha256
            FROM editions WHERE book_id=? AND edition_id=?
            """,
            (book_id, selected),
        ).fetchone()
        snapshot_row = connection.execute(
            """
            SELECT snapshot_id, through_event_seq, state_sha256, file_path, created_at
            FROM snapshots WHERE book_id=? AND edition_id=?
            ORDER BY created_at DESC LIMIT 1
            """,
            (book_id, selected),
        ).fetchone()
        impact = _rows(
            connection,
            """
            SELECT * FROM revision_impact_items
            WHERE book_id=? AND edition_id=? ORDER BY impact_id
            """,
            (book_id, selected),
        )
        events = _rows(
            connection,
            """
            SELECT event_seq, event_id, event_type, aggregate_id, status,
                   information_state, event_hash
            FROM events WHERE book_id=? AND edition_id=? ORDER BY event_seq
            """,
            (book_id, selected),
        )
        base_chapters = {
            str(row["chapter_id"]): row
            for row in connection.execute(
                """
                SELECT chapter_id, content, content_sha256, raw_heading, title
                FROM chapters WHERE book_id=? AND edition_id='base'
                """,
                (book_id,),
            ).fetchall()
        }
    workspace = edition_workspace(database, book_id, selected)
    export_id = stable_id(
        "edition-export", book_id, selected, str(projection.through_event_seq), projection.sha256()
    )
    export_dir = (output_root or workspace / "exports") / export_id
    export_dir.mkdir(parents=True, exist_ok=True)
    ordinals = [int(row["ordinal"]) for row in chapters]
    if len(ordinals) != len(set(ordinals)):
        raise EditionExportError("edition 导出发现重复 ordinal；拒绝生成含歧义的完整正文")
    complete_text = "\n\n".join(
        str(row["content"]).strip() for row in chapters if row.get("content")
    )
    if complete_text:
        complete_text += "\n"
    (export_dir / "complete_edition.md").write_text(complete_text, encoding="utf-8")
    diff_lines: list[str] = [f"# Revision Diff `{selected}`", ""]
    for variant in variants:
        base = base_chapters.get(str(variant["base_chapter_id"]))
        if base is None:
            continue
        current = next(
            (
                item
                for item in chapters
                if str(item["chapter_id"]) == str(variant["base_chapter_id"])
            ),
            None,
        )
        if current is None:
            continue
        diff_lines.extend(
            difflib.unified_diff(
                str(base["content"]).splitlines(),
                str(current["content"]).splitlines(),
                fromfile=f"base/{variant['base_chapter_id']}",
                tofile=f"{selected}/{variant['variant_id']}",
                lineterm="",
            )
        )
        diff_lines.append("")
    (export_dir / "revision_diff.md").write_text("\n".join(diff_lines) + "\n", encoding="utf-8")
    unresolved = [
        item
        for item in impact
        if item["classification"] in {"MUST_REVIEW", "MUST_REWRITE"}
        and item["status"] not in {"HANDLED", "WAIVED"}
    ]
    files = {
        "complete_edition": "complete_edition.md",
        "edition_manifest": "edition_manifest.json",
        "edition_projection": "edition_projection.json",
        "revision_audit": "revision_audit.json",
        "chapter_variant_index": "chapter_variant_index.json",
        "revision_diff": "revision_diff.md",
        "unresolved_items": "unresolved_items.json",
    }
    (export_dir / "edition_projection.json").write_text(
        json_dumps(projection.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    (export_dir / "revision_audit.json").write_text(
        json_dumps(
            {
                "campaigns": campaigns,
                "units": units,
                "drafts": drafts,
                "commits": commits,
                "impact_items": impact,
                "events": events,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (export_dir / "chapter_variant_index.json").write_text(
        json_dumps({"edition_id": selected, "variants": variants}, indent=2) + "\n",
        encoding="utf-8",
    )
    (export_dir / "unresolved_items.json").write_text(
        json_dumps({"edition_id": selected, "items": unresolved}, indent=2) + "\n", encoding="utf-8"
    )
    source_root = workspace.parent if selected == BASE_EDITION_ID else workspace.parents[2]
    source_report = verify_sources(book_id, source_root)
    manifest = {
        "export_id": export_id,
        "book_id": book_id,
        "edition_id": selected,
        "base_edition": BASE_EDITION_ID,
        "parent_edition_id": None if edition_row is None else edition_row["parent_edition_id"],
        "source_manifest_sha256": None
        if edition_row is None
        else edition_row["source_manifest_sha256"],
        "created_at": utc_now(),
        "through_event_seq": projection.through_event_seq,
        "projection_sha256": projection.sha256(),
        "revision_commits": commits,
        "active_variants": [item for item in variants if item["active"]],
        "snapshot": None if snapshot_row is None else dict(snapshot_row),
        "source_verify": source_report,
        "chapter_count": len(chapters),
        "variant_count": len([item for item in variants if item["active"]]),
        "unresolved_count": len(unresolved),
        "files": files,
    }
    (export_dir / "edition_manifest.json").write_text(
        json_dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {
        **manifest,
        "path": str(export_dir),
        "manifest": str(export_dir / "edition_manifest.json"),
    }
