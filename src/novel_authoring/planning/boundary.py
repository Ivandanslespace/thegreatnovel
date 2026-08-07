from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from novel_authoring.atlas.service import latest_atlas
from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.db.database import Database
from novel_authoring.edition import (
    edition_chapters,
    edition_lineage_ids,
    edition_workspace,
    resolve_edition_id,
)
from novel_authoring.ingest.service import verify_sources
from novel_authoring.planning.innovation import (
    InnovationControl,
    InnovationDiagnostics,
    recommend_innovation_focus,
    resolve_innovation_control,
)
from novel_authoring.planning.models import (
    BoundaryChapter,
    ContinuationBoundaryPacket,
    EarlierSummary,
)
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.operations import book_root
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now


class PlanningError(RuntimeError):
    pass


def _workspace(database: Database, book_id: str) -> Path:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    if row is None:
        raise PlanningError(f"未知 book_id：{book_id}")
    return Path(str(row["workspace_root"]))


def _fact_conflicts(projection: Any) -> list[dict[str, Any]]:
    """Detect conflicts from the selected edition projection, not global rows."""
    groups: dict[tuple[str | None, str], list[dict[str, str]]] = {}
    for fact_id, fact in projection.facts.items():
        key = (
            None if fact.get("subject_id") is None else str(fact.get("subject_id")),
            str(fact.get("predicate", "")),
        )
        groups.setdefault(key, []).append(
            {"fact_id": str(fact_id), "object_json": json_dumps(fact.get("object"))}
        )
    return [
        {"subject_id": key[0], "predicate": key[1], "facts": facts}
        for key, facts in groups.items()
        if len({fact["object_json"] for fact in facts}) > 1
    ]


def _markdown(packet: ContinuationBoundaryPacket) -> str:
    lines = [
        f"# Continuation Boundary Packet `{packet.packet_id}`",
        "",
        f"- book_id: `{packet.book_id}`",
        f"- base_event_seq: {packet.base_event_seq}",
        f"- projection_sha256: `{packet.base_projection_hash}`",
        f"- current_position: {json_dumps(packet.current_position)}",
        "",
        "## 最近完整章节",
        "",
    ]
    for chapter in packet.recent_full_chapters:
        lines.extend(
            [
                f"### {chapter.heading}",
                "",
                f"source_span_id: `{chapter.source_span_id}`",
                "",
                chapter.content,
                "",
            ]
        )
    sections = {
        "更早章节摘要": [item.model_dump(mode="json") for item in packet.earlier_summaries],
        "FTS5 相关原文片段": packet.relevant_source_spans,
        "当前正史": packet.canon_facts,
        "人物状态": packet.character_states,
        "人物知识边界": packet.knowledge_boundaries,
        "活跃线程": packet.active_threads,
        "承诺与悬念": packet.promises,
        "资源": packet.resources,
        "能力": packet.capabilities,
        "关系": packet.relationships,
        "最近爽点": packet.recent_payoffs,
        "最近结构": packet.recent_structures,
        "文风样本": packet.style_profiles,
        "作者指令与禁忌": packet.author_directives,
        "章节节奏特征": packet.rhythm_features,
        "长跨度节奏诊断": packet.rhythm_diagnostics,
        "伏笔动作队列": packet.hook_diagnostics,
        "Story Atlas anchor": packet.story_atlas_anchor,
        "Batch anchor": packet.batch_anchor,
        "Innovation Control": packet.innovation_control.model_dump(mode="json"),
        "Innovation diagnostics": (
            None
            if packet.innovation_diagnostics is None
            else packet.innovation_diagnostics.model_dump(mode="json")
        ),
        "警告": packet.warnings,
    }
    for title, value in sections.items():
        lines.extend([f"## {title}", "", "```json", json_dumps(value, indent=2), "```", ""])
    return "\n".join(lines)


def _fts_query(goals: list[str]) -> str | None:
    terms: list[str] = []
    for goal in goals:
        compact = "".join(character for character in goal if character.isalnum())
        if len(compact) < 3:
            continue
        for index in range(len(compact) - 2):
            term = compact[index : index + 3]
            if term not in terms:
                terms.append(term)
            if len(terms) >= 12:
                break
        if len(terms) >= 12:
            break
    if not terms:
        return None
    return " OR ".join(f'"{term}"' for term in terms)


def build_boundary_packet(
    database: Database,
    book_id: str,
    *,
    recent_full_chapters: int = 3,
    edition_id: str | None = None,
    batch_id: str | None = None,
    innovation_control: InnovationControl | None = None,
) -> dict[str, object]:
    database.initialize()
    workspace_root = _workspace(database, book_id)
    verification = verify_sources(book_id, workspace_root.parent)
    if not verification["ok"]:
        raise PlanningError("源文件 SHA-256 校验失败，禁止建立续写边界")
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    selected_innovation = innovation_control
    if selected_innovation is None:
        selected_innovation, _ = resolve_innovation_control(
            database, book_id
        )
    workspace = edition_workspace(database, book_id, selected_edition)
    projection = rebuild_projection(database, book_id, edition_id=selected_edition)
    conflicts = _fact_conflicts(projection)
    if conflicts:
        raise PlanningError("存在未解决的 CANON 冲突，禁止建立续写边界")
    atlas_row = latest_atlas(database, book_id, selected_edition)
    atlas_anchor = (
        {
            "atlas_id": str(atlas_row["atlas_id"]),
            "atlas_version": int(atlas_row["atlas_version"]),
            "atlas_manifest_hash": str(atlas_row["artifact_manifest_sha256"] or ""),
            "atlas_content_hash": str(atlas_row["atlas_content_hash"] or ""),
            "horizon_hash": str(atlas_row["horizon_hash"] or ""),
            "readiness_status": str(atlas_row["readiness_status"]),
        }
        if atlas_row is not None
        else {}
    )
    batch_anchor: dict[str, Any] = {}
    if batch_id is not None:
        from novel_authoring.planning.batch import get_batch_projection

        batch_projection = get_batch_projection(database, batch_id)
        if (
            batch_projection.book_id != book_id
            or batch_projection.edition_id != selected_edition
        ):
            raise PlanningError("batch_id 不属于当前 Boundary 的 book/edition")
        batch_anchor = batch_projection.model_dump(mode="json")
    with database.connect() as connection:
        if selected_edition == "base":
            recent_rows = connection.execute(
                """
                SELECT c.chapter_id, c.ordinal, c.raw_heading, c.content, s.span_id
                FROM chapters c JOIN source_spans s ON s.chapter_id=c.chapter_id
                WHERE c.book_id=?
                  AND s.kind IN ('chapter', 'AUTHOR_APPROVED_CHAPTER')
                ORDER BY c.ordinal DESC LIMIT ?
                """,
                (book_id, recent_full_chapters),
            ).fetchall()
        else:
            recent_rows = [
                {
                    "chapter_id": row["chapter_id"],
                    "ordinal": row["ordinal"],
                    "raw_heading": row.get("raw_heading", row.get("title", "")),
                    "content": row["content"],
                    "span_id": row.get("source_span_id", ""),
                }
                for row in edition_chapters(connection, book_id, selected_edition)[
                    -recent_full_chapters:
                ]
            ]
        recent_rows = list(reversed(recent_rows))
        first_recent = int(recent_rows[0]["ordinal"]) if recent_rows else 1
        summary_rows = connection.execute(
            """
            SELECT chapter_id, ordinal, raw_heading, summary FROM chapters
            WHERE book_id=? AND ordinal<? AND summary IS NOT NULL
            ORDER BY ordinal
            """,
            (book_id, first_recent),
        ).fetchall()
        if selected_edition != "base":
            replaced_ids = {
                str(item["chapter_id"])
                for item in edition_chapters(connection, book_id, selected_edition)
                if item.get("document_status") == "REVISION_VARIANT"
            }
            summary_rows = [
                item for item in summary_rows if str(item["chapter_id"]) not in replaced_ids
            ]
        else:
            replaced_ids = set()
        if selected_edition == "base":
            thread_rows = connection.execute(
                """
                SELECT * FROM threads
                WHERE book_id=? AND status IN ('CANON','AUTHOR_INTENT','APPROVED_OUTLINE')
                ORDER BY importance DESC, thread_id
                """,
                (book_id,),
            ).fetchall()
        else:
            # Derived editions inherit the frozen parent projection; querying
            # only rows physically stamped with the child edition would hide
            # unchanged threads and leak an incomplete continuation boundary.
            thread_rows = []
            for thread_id, value in projection.threads.items():
                item = dict(value)
                item.setdefault("thread_id", thread_id)
                item.setdefault("status", "CANON")
                item.setdefault("importance", 0.5)
                item.setdefault("goal", "")
                item.setdefault("phase", "active")
                item.setdefault("payload_json", json_dumps(item))
                thread_rows.append(item)
            thread_rows.sort(
                key=lambda row: (-float(row["importance"]), str(row["thread_id"]))
            )
        fts_query = _fts_query([str(row["goal"]) for row in thread_rows[:3]])
        relevant_source_rows: list[Any] = []
        if fts_query is not None:
            relevant_source_rows = connection.execute(
                """
                SELECT c.chapter_id, c.ordinal, c.raw_heading,
                       snippet(chapter_fts, 3, '', '', '…', 30) AS excerpt,
                       (
                           SELECT MIN(source_span.span_id)
                           FROM source_spans source_span
                           WHERE source_span.chapter_id=c.chapter_id
                             AND source_span.kind IN (
                                 'chapter', 'AUTHOR_APPROVED_CHAPTER'
                             )
                       ) AS source_span_id
                FROM chapter_fts
                JOIN chapters c ON c.chapter_id=chapter_fts.chapter_id
                WHERE chapter_fts MATCH ? AND chapter_fts.book_id=?
                      AND c.ordinal<?
                ORDER BY bm25(chapter_fts), c.ordinal DESC
                LIMIT 5
                """,
                (fts_query, book_id, first_recent),
            ).fetchall()
            if selected_edition != "base":
                try:
                    variant_rows = connection.execute(
                        """
                        SELECT chapter_id, heading,
                               snippet(edition_chapter_fts, 4, '', '', '…', 30) AS excerpt,
                               variant_id
                        FROM edition_chapter_fts
                        WHERE edition_id=? AND edition_chapter_fts MATCH ?
                        ORDER BY rank LIMIT 5
                        """,
                        (selected_edition, fts_query),
                    ).fetchall()
                    relevant_source_rows.extend(
                        {
                            **dict(item),
                            "edition_id": selected_edition,
                            "source_span_id": next(
                                (
                                    str(chapter.get("source_span_id"))
                                    for chapter in edition_chapters(
                                        connection, book_id, selected_edition
                                    )
                                    if str(chapter["chapter_id"]) == str(item["chapter_id"])
                                ),
                                "",
                            ),
                        }
                        for item in variant_rows
                    )
                except sqlite3.DatabaseError:
                    pass
        if selected_edition == "base":
            structure_rows = connection.execute(
                "SELECT * FROM repetition_tags WHERE book_id=? ORDER BY ordinal DESC LIMIT 20",
                (book_id,),
            ).fetchall()
            style_rows = connection.execute(
                """
                SELECT * FROM style_profiles
                WHERE book_id=? AND status IN ('CANON','AUTHOR_INTENT','APPROVED_OUTLINE')
                ORDER BY created_at DESC
                """,
                (book_id,),
            ).fetchall()
        else:
            structure_rows = []
            for tag_id, value in projection.repetition.items():
                item = dict(value)
                item.setdefault("tag_id", tag_id)
                structure_rows.append(item)
            structure_rows.sort(key=lambda row: int(row.get("ordinal", 0)), reverse=True)
            structure_rows = structure_rows[:20]
            style_rows = []
            for profile_id, value in projection.style_profiles.items():
                item = dict(value)
                item.setdefault("profile_id", profile_id)
                item.setdefault("status", "CANON")
                style_rows.append(item)
        directive_lineage = edition_lineage_ids(connection, selected_edition)
        directive_placeholders = ",".join("?" for _ in directive_lineage)
        directive_rows = connection.execute(
            f"""
            SELECT * FROM author_directives
            WHERE book_id=? AND status='ACTIVE'
              AND edition_id IN ({directive_placeholders})
            ORDER BY priority DESC, created_at
            """,
            (book_id, *directive_lineage),
        ).fetchall()
        total = (
            len(edition_chapters(connection, book_id, selected_edition))
            if selected_edition != "base"
            else int(
                connection.execute(
                    "SELECT COUNT(*) FROM chapters WHERE book_id=?", (book_id,)
                ).fetchone()[0]
            )
        )
    rhythm_features: list[dict[str, Any]] = []
    rhythm_diagnostics: dict[str, Any] = {}
    hook_diagnostics: dict[str, Any] = {}
    try:
        from novel_authoring.rhythm.service import diagnose_hooks, diagnose_rhythm

        rhythm_diagnostics = diagnose_rhythm(
            database, book_id, edition_id=selected_edition
        )
        hook_diagnostics = diagnose_hooks(database, book_id, edition_id=selected_edition)
        with database.connect() as rhythm_connection:
            rows = rhythm_connection.execute(
                """
                SELECT cf.*, c.ordinal
                FROM chapter_features cf JOIN chapters c ON c.chapter_id=cf.chapter_id
                WHERE cf.book_id=? AND cf.edition_id=? AND cf.status='ACTIVE'
                ORDER BY c.ordinal DESC LIMIT 20
                """,
                (book_id, selected_edition),
            ).fetchall()
            rhythm_features = [dict(row) for row in reversed(rows)]
    except Exception as exc:
        # Rhythm diagnostics are advisory.  A malformed optional semantic
        # artifact must be visible as a warning, never silently block the
        # constitution-mandated boundary build.
        warnings_message = f"节奏诊断暂不可用：{exc}"
    else:
        warnings_message = ""

    warnings: list[str] = []
    if warnings_message:
        warnings.append(warnings_message)
    if first_recent > 1 and not summary_rows:
        warnings.append("更早章节尚无结构化摘要；当前仅依赖 Canon Projection 与最近原文")
    if replaced_ids:
        warnings.append("改写章节的旧摘要已从本 edition 边界排除；请重新生成 edition 摘要")
    recommendation = recommend_innovation_focus(
        active_threads=[dict(row) for row in thread_rows],
        relationships=projection.relationships,
        capabilities=projection.capabilities,
        recent_structures=[dict(row) for row in structure_rows],
        open_setups=list(projection.promises.values()),
        available_payoffs=list(projection.payoffs.values()),
    )
    innovation_diagnostics = InnovationDiagnostics(
        window_chapters=[int(row["ordinal"]) for row in recent_rows],
        recent_pattern_distance=recommendation.pattern_distance,
        repeated_patterns=[
            str(item.get("pattern"))
            for item in [dict(row) for row in structure_rows[:5]]
            if item.get("pattern")
        ],
        open_novelty_debt=[],
        recommendation=recommendation,
    )
    packet_seed = json_dumps(
        {
            "book_id": book_id,
            "edition_id": selected_edition,
            "event_seq": projection.through_event_seq,
            "projection": projection.sha256(),
            "last_chapter": total,
            "recent_full_chapters": recent_full_chapters,
            "recent_chapter_ids": [str(row["chapter_id"]) for row in recent_rows],
            "directives": [dict(row) for row in directive_rows],
            "planning_context": {
                "summaries": [str(row["chapter_id"]) for row in summary_rows],
                "threads": [dict(row) for row in thread_rows],
                "relevant_sources": [dict(row) for row in relevant_source_rows],
                "structures": [dict(row) for row in structure_rows],
            "styles": [dict(row) for row in style_rows],
            "rhythm_features": rhythm_features,
            "rhythm_diagnostics": rhythm_diagnostics,
            "hook_diagnostics": hook_diagnostics,
            "story_atlas_anchor": atlas_anchor,
            "batch_anchor": batch_anchor,
            "innovation_control": selected_innovation.model_dump(mode="json"),
            "innovation_diagnostics": innovation_diagnostics.model_dump(mode="json"),
            },
        }
    )
    packet_id = stable_id("boundary", packet_seed)
    packet = ContinuationBoundaryPacket(
        packet_id=packet_id,
        book_id=book_id,
        edition_id=selected_edition,
        base_event_seq=projection.through_event_seq,
        base_projection_hash=projection.sha256(),
        current_position={"last_canon_chapter": total, "next_chapter": total + 1},
        recent_full_chapters=[
            BoundaryChapter(
                chapter_id=str(row["chapter_id"]),
                ordinal=int(row["ordinal"]),
                heading=str(row["raw_heading"]),
                content=str(row["content"]),
                source_span_id=str(row["span_id"]),
            )
            for row in recent_rows
        ],
        earlier_summaries=[
            EarlierSummary(
                chapter_id=str(row["chapter_id"]),
                ordinal=int(row["ordinal"]),
                heading=str(row["raw_heading"]),
                summary=str(row["summary"]),
            )
            for row in summary_rows
        ],
        relevant_source_spans=[dict(row) for row in relevant_source_rows],
        canon_facts=projection.facts,
        character_states=projection.character_states,
        knowledge_boundaries=projection.knowledge,
        active_threads=[dict(row) for row in thread_rows],
        promises=projection.promises,
        resources=projection.resources,
        capabilities=projection.capabilities,
        relationships=projection.relationships,
        recent_payoffs=projection.payoffs,
        recent_structures=[dict(row) for row in structure_rows],
        style_profiles=[dict(row) for row in style_rows],
        author_directives=[dict(row) for row in directive_rows],
        rhythm_features=rhythm_features,
        rhythm_diagnostics=rhythm_diagnostics,
        hook_diagnostics=hook_diagnostics,
        story_atlas_anchor=atlas_anchor,
        batch_anchor=batch_anchor,
        innovation_control=selected_innovation,
        innovation_diagnostics=innovation_diagnostics,
        warnings=warnings,
    )
    packet_json = json_dumps(packet.model_dump(mode="json"), indent=2)
    packet_hash = sha256_bytes(packet_json.encode())
    root = book_root(database, book_id)
    boundaries = (
        BookLayout(root.parent).for_book(book_id).edition(selected_edition).boundaries
        if (root / "book.yaml").is_file()
        else workspace / "boundaries"
    )
    boundaries.mkdir(parents=True, exist_ok=True)
    json_path = boundaries / f"{packet_id}.json"
    markdown_path = boundaries / f"{packet_id}.md"
    json_path.write_text(packet_json + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(packet), encoding="utf-8")
    with database.connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO boundary_packets(
                packet_id, book_id, edition_id, base_event_seq, base_projection_hash,
                file_path, packet_json, packet_sha256, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'READY', ?)
            """,
            (
                packet_id,
                book_id,
                selected_edition,
                packet.base_event_seq,
                packet.base_projection_hash,
                str(markdown_path),
                packet_json,
                packet_hash,
                utc_now(),
            ),
        )
    return {
        "packet_id": packet_id,
        "edition_id": selected_edition,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "packet_sha256": packet_hash,
        "warnings": warnings,
    }
