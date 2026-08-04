from __future__ import annotations

from pathlib import Path
from typing import Any

from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import verify_sources
from novel_authoring.planning.models import (
    BoundaryChapter,
    ContinuationBoundaryPacket,
    EarlierSummary,
)
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


def _fact_conflicts(database: Database, book_id: str) -> list[dict[str, Any]]:
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT subject_id, predicate, object_json, fact_id
            FROM facts WHERE book_id=? AND active=1 AND status='CANON'
            ORDER BY subject_id, predicate, fact_id
            """,
            (book_id,),
        ).fetchall()
    groups: dict[tuple[str | None, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (
            None if row["subject_id"] is None else str(row["subject_id"]),
            str(row["predicate"]),
        )
        groups.setdefault(key, []).append(
            {"fact_id": str(row["fact_id"]), "object_json": str(row["object_json"])}
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
) -> dict[str, object]:
    database.initialize()
    workspace = _workspace(database, book_id)
    verification = verify_sources(book_id, workspace.parent)
    if not verification["ok"]:
        raise PlanningError("源文件 SHA-256 校验失败，禁止建立续写边界")
    conflicts = _fact_conflicts(database, book_id)
    if conflicts:
        raise PlanningError("存在未解决的 CANON 冲突，禁止建立续写边界")
    projection = rebuild_projection(database, book_id)
    with database.connect() as connection:
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
        thread_rows = connection.execute(
            """
            SELECT * FROM threads
            WHERE book_id=? AND status IN ('CANON','AUTHOR_INTENT','APPROVED_OUTLINE')
            ORDER BY importance DESC, thread_id
            """,
            (book_id,),
        ).fetchall()
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
        structure_rows = connection.execute(
            """
            SELECT * FROM repetition_tags WHERE book_id=?
            ORDER BY ordinal DESC LIMIT 20
            """,
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
        directive_rows = connection.execute(
            """
            SELECT * FROM author_directives
            WHERE book_id=? AND status='ACTIVE'
            ORDER BY priority DESC, created_at
            """,
            (book_id,),
        ).fetchall()
        total = int(
            connection.execute(
                "SELECT COUNT(*) FROM chapters WHERE book_id=?", (book_id,)
            ).fetchone()[0]
        )
    warnings: list[str] = []
    if first_recent > 1 and not summary_rows:
        warnings.append("更早章节尚无结构化摘要；当前仅依赖 Canon Projection 与最近原文")
    packet_seed = json_dumps(
        {
            "book_id": book_id,
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
            },
        }
    )
    packet_id = stable_id("boundary", packet_seed)
    packet = ContinuationBoundaryPacket(
        packet_id=packet_id,
        book_id=book_id,
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
        warnings=warnings,
    )
    packet_json = json_dumps(packet.model_dump(mode="json"), indent=2)
    packet_hash = sha256_bytes(packet_json.encode())
    boundaries = workspace / "boundaries"
    boundaries.mkdir(parents=True, exist_ok=True)
    json_path = boundaries / f"{packet_id}.json"
    markdown_path = boundaries / f"{packet_id}.md"
    json_path.write_text(packet_json + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(packet), encoding="utf-8")
    with database.connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO boundary_packets(
                packet_id, book_id, base_event_seq, base_projection_hash,
                file_path, packet_json, packet_sha256, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'READY', ?)
            """,
            (
                packet_id,
                book_id,
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
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "packet_sha256": packet_hash,
        "warnings": warnings,
    }
