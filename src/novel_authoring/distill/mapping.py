"""Deterministic mapping from Distill locators to edition evidence.

The mapper only uses frozen preparation metadata, selected-edition chapter
views and existing source spans.  It never chooses between conflicting
chapters by similarity and it never writes to the Canon database.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novel_authoring.db.database import Database
from novel_authoring.distill.models import (
    DistilledEvidence,
    DistillScope,
    EvidenceMappingStatus,
)
from novel_authoring.edition import edition_chapters


class DistillMappingError(ValueError):
    """Raised when frozen preparation data cannot be read."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DistillMappingError(f"无法读取 mapping 输入：{path}") from exc
    if not isinstance(value, dict):
        raise DistillMappingError(f"mapping 输入必须是 object：{path}")
    return value


def _preparation_data(preparation_manifest: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = Path(preparation_manifest).expanduser().resolve()
    manifest = _read_object(manifest_path)
    index_path = manifest_path.parent / "chapter_index.json"
    if not index_path.is_file():
        raise DistillMappingError(f"chapter_index.json 不存在：{index_path}")
    return manifest, _read_object(index_path)


def _source_rows(
    manifest: dict[str, Any], chapter_index: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in manifest.get("sources", []):
        if isinstance(item, dict) and item.get("source_id"):
            result[str(item["source_id"])] = dict(item)
    for item in chapter_index.get("sources", []):
        if not isinstance(item, dict) or not item.get("source_id"):
            continue
        current = result.setdefault(str(item["source_id"]), {})
        current.update(item)
    return result


def _is_self_source(database: Database, book_id: str, source: dict[str, Any]) -> bool:
    declared = str(source.get("source_origin") or "").upper()
    if declared:
        return declared == DistillScope.SELF_BOOK.value
    input_path = str(source.get("input_path") or "").strip()
    if not input_path:
        return False
    with database.connect() as connection:
        row = connection.execute(
            "SELECT source_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    if row is None:
        return False
    try:
        Path(input_path).expanduser().resolve().relative_to(
            Path(str(row["source_root"])).expanduser().resolve()
        )
    except ValueError:
        return False
    return True


def _chapter_span_id(database: Database, chapter: dict[str, Any]) -> str | None:
    if chapter.get("source_span_id"):
        return str(chapter["source_span_id"])
    chapter_id = str(chapter.get("chapter_id") or "")
    if not chapter_id:
        return None
    with database.connect() as connection:
        row = connection.execute(
            "SELECT span_id FROM source_spans WHERE chapter_id=? "
            "ORDER BY CASE WHEN kind='chapter' THEN 0 ELSE 1 END, span_id LIMIT 1",
            (chapter_id,),
        ).fetchone()
    return None if row is None else str(row["span_id"])


def _candidate_chapters(
    database: Database,
    book_id: str,
    edition_id: str,
    source: dict[str, Any],
    segment: dict[str, Any],
    chapters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not _is_self_source(database, book_id, source):
        return []
    explicit_chapter = str(segment.get("chapter_id") or "").strip()
    if explicit_chapter:
        return [
            chapter
            for chapter in chapters
            if str(chapter.get("chapter_id")) == explicit_chapter
        ]
    ordinal = segment.get("ordinal")
    if ordinal is None:
        return []
    try:
        target_ordinal = int(ordinal)
    except (TypeError, ValueError):
        return []

    document_id = str(source.get("document_id") or "").strip()
    if document_id:
        matches = [
            chapter
            for chapter in chapters
            if str(chapter.get("document_id")) == document_id
            and int(chapter.get("ordinal", -1)) == target_ordinal
        ]
        if matches:
            return matches

    input_path = str(source.get("input_path") or "").strip()
    with database.connect() as connection:
        book = connection.execute(
            "SELECT source_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
        documents = connection.execute(
            "SELECT document_id, relative_path FROM source_documents "
            "WHERE book_id=? AND status!='GENERATED_CANON' ORDER BY order_index, relative_path",
            (book_id,),
        ).fetchall()
    document_ids: set[str] = set()
    if input_path and book is not None:
        try:
            relative = Path(input_path).expanduser().resolve().relative_to(
                Path(str(book["source_root"])).expanduser().resolve()
            )
        except ValueError:
            relative = None
        if relative is not None:
            document_ids.update(
                str(row["document_id"])
                for row in documents
                if str(row["relative_path"]) == relative.as_posix()
            )
    if not document_ids and len(documents) == 1:
        document_ids.add(str(documents[0]["document_id"]))
    return [
        chapter
        for chapter in chapters
        if str(chapter.get("document_id")) in document_ids
        and int(chapter.get("ordinal", -1)) == target_ordinal
    ]


def map_evidence(
    database: Database,
    book_id: str,
    edition_id: str,
    preparation_manifest: Path,
    evidence: DistilledEvidence,
) -> DistilledEvidence:
    """Map one frozen Distill locator to the selected edition.

    External and comparative sources remain unmapped unless their frozen
    source record explicitly identifies a self-book effective chapter.  This
    preserves the external-reference boundary even when two files happen to
    contain similar prose.
    """

    manifest, chapter_index = _preparation_data(preparation_manifest)
    sources = _source_rows(manifest, chapter_index)
    source = sources.get(evidence.source_id)
    if source is None:
        return evidence.model_copy(
            update={
                "mapping_status": EvidenceMappingStatus.UNMAPPED,
                "chapter_id": None,
                "source_span_ids": [],
            }
        )
    segment_matches = [
        item
        for item in source.get("segments", [])
        if isinstance(item, dict) and str(item.get("segment_id")) == evidence.segment_id
    ]
    if len(
        {
            str(item.get("chapter_id"))
            for item in segment_matches
            if item.get("chapter_id")
        }
    ) > 1:
        return evidence.model_copy(
            update={
                "mapping_status": EvidenceMappingStatus.CONFLICTING,
                "chapter_id": None,
                "source_span_ids": [],
            }
        )
    segment = segment_matches[0] if segment_matches else None
    if segment is None:
        return evidence.model_copy(
            update={
                "mapping_status": EvidenceMappingStatus.UNMAPPED,
                "chapter_id": None,
                "source_span_ids": [],
            }
        )
    database.initialize()
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, edition_id)
    candidates = _candidate_chapters(
        database, book_id, edition_id, source, segment, chapters
    )
    distinct_ids = {str(item.get("chapter_id")) for item in candidates}
    if len(distinct_ids) > 1:
        return evidence.model_copy(
            update={
                "mapping_status": EvidenceMappingStatus.CONFLICTING,
                "chapter_id": None,
                "source_span_ids": [],
            }
        )
    if not candidates:
        return evidence.model_copy(
            update={
                "mapping_status": EvidenceMappingStatus.UNMAPPED,
                "chapter_id": None,
                "source_span_ids": [],
            }
        )
    chapter = candidates[0]
    span_id = _chapter_span_id(database, chapter)
    if span_id is None:
        return evidence.model_copy(
            update={
                "mapping_status": EvidenceMappingStatus.PARTIAL,
                "chapter_id": str(chapter["chapter_id"]),
                "source_span_ids": [],
            }
        )

    segment_start = int(segment.get("start_line", evidence.start_line))
    segment_end = int(segment.get("end_line", evidence.end_line))
    requested_start = evidence.start_line
    requested_end = evidence.end_line
    explicit_chapter = bool(str(segment.get("chapter_id") or "").strip())
    frozen_range_ok = segment_start <= requested_start and requested_end <= segment_end
    chapter_start = int(chapter.get("start_line", segment_start))
    chapter_end = int(chapter.get("end_line", segment_end))
    overlaps_chapter = requested_start <= chapter_end and requested_end >= chapter_start
    exact = explicit_chapter and frozen_range_ok
    if not exact and frozen_range_ok and (
        chapter_start <= requested_start and requested_end <= chapter_end
    ):
        exact = True
    if exact:
        return evidence.model_copy(
            update={
                "mapping_status": EvidenceMappingStatus.EXACT,
                "chapter_id": str(chapter["chapter_id"]),
                "source_span_ids": [span_id],
            }
        )
    if overlaps_chapter:
        return evidence.model_copy(
            update={
                "mapping_status": EvidenceMappingStatus.PARTIAL,
                "chapter_id": str(chapter["chapter_id"]),
                "source_span_ids": [span_id],
            }
        )
    return evidence.model_copy(
        update={
            "mapping_status": EvidenceMappingStatus.UNMAPPED,
            "chapter_id": None,
            "source_span_ids": [],
        }
    )


def map_evidence_batch(
    database: Database,
    book_id: str,
    edition_id: str,
    preparation_manifest: Path,
    evidence: list[DistilledEvidence],
) -> list[DistilledEvidence]:
    return [
        map_evidence(database, book_id, edition_id, preparation_manifest, item)
        for item in evidence
    ]


def mapping_summary(evidence: list[DistilledEvidence]) -> dict[str, int]:
    return {
        status.value: sum(1 for item in evidence if item.mapping_status is status)
        for status in EvidenceMappingStatus
    }


__all__ = [
    "DistillMappingError",
    "map_evidence",
    "map_evidence_batch",
    "mapping_summary",
]
