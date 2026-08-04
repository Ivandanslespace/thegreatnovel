from __future__ import annotations

import re
import sqlite3
from enum import StrEnum
from typing import Any

from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.utils import sha256_bytes, stable_id, utc_now


class SegmentKind(StrEnum):
    HEADING = "HEADING"
    PROSE = "PROSE"
    DIALOGUE = "DIALOGUE"
    SYSTEM_PANEL = "SYSTEM_PANEL"
    LIST = "LIST"
    TABLE = "TABLE"
    SEPARATOR = "SEPARATOR"
    OTHER = "OTHER"


class SegmentWorkflowError(RuntimeError):
    pass


def classify_segment(text: str) -> SegmentKind:
    stripped = text.strip()
    if not stripped:
        return SegmentKind.OTHER
    if re.match(
        r"^(?:#{1,6}\s*)?第\s*[0-9０-９一二三四五六七八九十百千两兩零〇]+\s*[章节卷]", stripped
    ):
        return SegmentKind.HEADING
    if re.match(r"^(?:\[|【).*(?:系统|面板|提示|任务|状态|属性|技能).*(?:\]|】)$", stripped, re.S):
        return SegmentKind.SYSTEM_PANEL
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if lines and all(line.startswith(("- ", "* ", "• ", "1. ", "一、")) for line in lines):
        return SegmentKind.LIST
    if "|" in stripped or "\t" in stripped and len(lines) > 1:
        return SegmentKind.TABLE
    if re.fullmatch(r"[\-—_*=~·。．.]{2,}", stripped):
        return SegmentKind.SEPARATOR
    if stripped.startswith(('"', "“", "『", "「", "‘", "‘")) or any(
        marker in stripped for marker in ("：“", '："', "‘", "’", "『", "」")
    ):
        return SegmentKind.DIALOGUE
    return SegmentKind.PROSE


def split_segments(text: str) -> list[tuple[int, int, str]]:
    """Split only on blank-line boundaries and preserve source offsets/text."""
    if not text:
        return []
    result: list[tuple[int, int, str]] = []
    cursor = 0
    # Ingested files may retain Windows CRLF line endings. Treat CRLF and LF
    # identically so a heading and following prose become separate evidence
    # segments on Windows as well.
    for match in re.finditer(r"\r?\n[ \t]*(?:\r?\n)+", text):
        if match.start() > cursor:
            result.append((cursor, match.start(), text[cursor : match.start()]))
        cursor = match.end()
    if cursor < len(text):
        result.append((cursor, len(text), text[cursor:]))
    return result


def _insert_segments(
    connection: sqlite3.Connection, book_id: str, edition_id: str, chapter: dict[str, Any]
) -> int:
    content = str(chapter.get("content") or "")
    content_hash = str(chapter.get("content_sha256") or sha256_bytes(content.encode("utf-8")))
    chapter_id = str(chapter["chapter_id"])
    now = utc_now()
    connection.execute(
        "UPDATE chapter_segments SET invalidated_at=? WHERE book_id=? AND edition_id=? "
        "AND chapter_id=? AND effective_content_sha256<>? AND invalidated_at IS NULL",
        (now, book_id, edition_id, chapter_id, content_hash),
    )
    count = 0
    for ordinal, (start, end, raw) in enumerate(split_segments(content)):
        text_hash = sha256_bytes(raw.encode("utf-8"))
        segment_id = stable_id(
            "segment", book_id, edition_id, chapter_id, content_hash, str(ordinal), text_hash
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO chapter_segments(
                segment_id, book_id, edition_id, chapter_id, effective_content_sha256,
                segment_ordinal, segment_kind, start_char, end_char, text, text_sha256,
                created_at, invalidated_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 1)
            """,
            (
                segment_id,
                book_id,
                edition_id,
                chapter_id,
                content_hash,
                ordinal,
                classify_segment(raw).value,
                start,
                end,
                raw,
                text_hash,
                now,
            ),
        )
        count += 1
    return count


def rebuild_segments(
    database: Database, book_id: str, *, edition_id: str | None = None
) -> dict[str, Any]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, selected)
        count = sum(
            _insert_segments(connection, book_id, selected, chapter) for chapter in chapters
        )
    return {
        "book_id": book_id,
        "edition_id": selected,
        "chapters": len(chapters),
        "segments": count,
    }


def list_segments(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    chapter_id: str | None = None,
) -> list[dict[str, Any]]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        sql = (
            "SELECT * FROM chapter_segments WHERE book_id=? AND edition_id=? "
            "AND invalidated_at IS NULL"
        )
        params: list[object] = [book_id, selected]
        if chapter_id is not None:
            sql += " AND chapter_id=?"
            params.append(chapter_id)
        sql += " ORDER BY chapter_id, segment_ordinal"
        return [dict(row) for row in connection.execute(sql, tuple(params)).fetchall()]


def segment_contains_quote(connection: sqlite3.Connection, segment_id: str, quote: str) -> bool:
    row = connection.execute(
        "SELECT text FROM chapter_segments WHERE segment_id=? AND invalidated_at IS NULL",
        (segment_id,),
    ).fetchone()
    return row is not None and bool(quote) and quote in str(row["text"])
