from __future__ import annotations

from typing import Any

from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.metrics.segments import list_segments
from novel_authoring.metrics.service import MetricsAssembler


def home_context(database: Any, book_id: str) -> dict[str, Any]:
    database.initialize()
    edition_id = resolve_edition_id(database, book_id)
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, edition_id)
    return {"book_id": book_id, "edition_id": edition_id, "chapters": chapters}


def chapter_context(
    database: Any, book_id: str, edition_id: str, chapter_id: str
) -> dict[str, Any]:
    database.initialize()
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, edition_id)
        chapter = next((item for item in chapters if str(item["chapter_id"]) == chapter_id), None)
    if chapter is None:
        raise ValueError("章节不存在")
    segments = list_segments(database, book_id, edition_id=edition_id, chapter_id=chapter_id)
    assembler = MetricsAssembler(database)
    bundle = assembler.assemble(
        book_id, edition_id=edition_id, scope_type="CHAPTER", scope_id=chapter_id
    )
    latest = assembler.latest(book_id, edition_id, "CHAPTER", chapter_id)
    return {
        "book_id": book_id,
        "edition_id": edition_id,
        "chapter": chapter,
        "segments": segments,
        "bundle": bundle.model_dump(mode="json"),
        "latest": latest,
    }
