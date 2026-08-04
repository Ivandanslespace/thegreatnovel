from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

from novel_authoring.domain.models import NarrativeFunction
from novel_authoring.rhythm.models import (
    ChapterFeature,
    FeatureExtractorKind,
)
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now

_CHAPTER_PREFIX = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:第\s*[0-9０-９一二三四五六七八九十百千两兩零〇]+\s*章)"
    r"(?:\s*[:：、.．\-———]?\s*)?",
    re.IGNORECASE,
)
_SERIES_MARKER = re.compile(
    r"(?:[（(]\s*[一二三四五六七八九十0-9]+\s*[）)]|"
    r"[（(]\s*[ivx]+\s*[）)])$"
)
_SYSTEM_LINE = re.compile(
    r"^\s*(?:\[?系统(?:提示|公告|面板)?\]?|系统面板|属性面板|公告|等级|力量|敏捷|体质)\s*[:：]",
    re.IGNORECASE,
)
_TABLE_LINE = re.compile(r"^\s*(?:\|.*\||[-+_=]{4,}|\d+(?:\.\d+)?\s+){2,}.*$")


def _compact(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKC", value) if not ch.isspace())


def normalize_title(title: str) -> str:
    """Return a stable, human-readable title without chapter decoration."""
    value = _CHAPTER_PREFIX.sub("", title.strip())
    value = re.sub(r"[\u3000\t\r\n]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^[\s:：、.．\-—]+|[\s:：、.．\-—]+$", "", value)
    return unicodedata.normalize("NFKC", value).strip().casefold()


def series_marker(title: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", title).strip()
    match = _SERIES_MARKER.search(normalized)
    return None if match is None else match.group(0)


def _ngrams(value: str, size: int) -> set[str]:
    compact = _compact(value)
    if not compact:
        return set()
    if len(compact) <= size:
        return {compact}
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def dice_similarity(left: str, right: str, *, sizes: tuple[int, ...] = (2, 3)) -> float:
    """Explainable character n-gram Dice similarity in [0, 1]."""
    if not left.strip() or not right.strip():
        return 0.0
    values: list[float] = []
    for size in sizes:
        a, b = _ngrams(left, size), _ngrams(right, size)
        if not a or not b:
            values.append(0.0)
        else:
            values.append(2 * len(a & b) / (len(a) + len(b)))
    return sum(values) / len(values) if values else 0.0


def _nonempty_paragraphs(content: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n+", content) if part.strip()]


def prose_only(text: str) -> str:
    """Remove headings/panels/tables before comparing prose windows."""
    kept: list[str] = []
    in_fence = False
    for paragraph in _nonempty_paragraphs(text):
        stripped = paragraph.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        table_block = stripped.startswith("|") and stripped.count("|") >= 2
        if in_fence or _SYSTEM_LINE.match(stripped) or _TABLE_LINE.match(stripped) or table_block:
            continue
        if stripped.startswith(("#", ">>>", "---")) and len(stripped) < 80:
            continue
        kept.append(stripped)
    return "\n\n".join(kept)


def excerpt_windows(content: str, *, limit: int = 300) -> tuple[str, str, str, str]:
    paragraphs = _nonempty_paragraphs(content)
    raw_opening = "\n\n".join(paragraphs[:3])[:limit]
    raw_ending = "\n\n".join(paragraphs[-3:])[:limit]
    prose = prose_only(content)
    prose_paragraphs = _nonempty_paragraphs(prose)
    prose_opening = "\n\n".join(prose_paragraphs[:3])[:limit]
    prose_ending = "\n\n".join(prose_paragraphs[-3:])[-limit:]
    return raw_opening, prose_opening, raw_ending, prose_ending


def _title_fingerprint(title: str) -> str:
    return sha256_bytes(json_dumps(sorted(_ngrams(title, 2) | _ngrams(title, 3))).encode())


def _fingerprint(value: str) -> str:
    return hashlib.sha256(_compact(value).encode("utf-8")).hexdigest()


def extract_chapter_feature(
    row: Mapping[str, Any],
    *,
    book_id: str,
    edition_id: str,
    config_hash: str,
    analyzer_version: str,
    text_window_chars: int = 300,
    planned_primary_function: str | None = None,
) -> ChapterFeature:
    content = str(row.get("content", ""))
    title = str(row.get("raw_heading", row.get("title", "")))
    effective_hash = str(row.get("content_sha256") or sha256_bytes(content.encode("utf-8")))
    normalized = normalize_title(title)
    opening_raw, opening_prose, ending_raw, ending_prose = excerpt_windows(
        content, limit=text_window_chars
    )
    chapter_id = str(row["chapter_id"])
    feature_id = stable_id(
        "chapter-feature", book_id, edition_id, chapter_id, effective_hash, analyzer_version
    )
    return ChapterFeature(
        feature_id=feature_id,
        book_id=book_id,
        edition_id=edition_id,
        chapter_id=chapter_id,
        ordinal=int(row.get("ordinal", 0)),
        effective_content_sha256=effective_hash,
        analyzer_version=analyzer_version,
        planned_primary_function=(
            None
            if planned_primary_function is None
            else NarrativeFunction(planned_primary_function)
        ),
        title_raw=title,
        normalized_title=normalized,
        title_fingerprint=_title_fingerprint(normalized),
        opening_excerpt_raw=opening_raw,
        opening_excerpt_prose=opening_prose,
        opening_fingerprint_raw=_fingerprint(opening_raw),
        opening_fingerprint_prose=_fingerprint(opening_prose),
        ending_excerpt_raw=ending_raw,
        ending_excerpt_prose=ending_prose,
        ending_fingerprint_raw=_fingerprint(ending_raw),
        ending_fingerprint_prose=_fingerprint(ending_prose),
        extractor_kind=FeatureExtractorKind.DETERMINISTIC,
        evidence={
            "title_series_marker": series_marker(normalized),
            "opening_paragraph_count": len(_nonempty_paragraphs(content)[:3]),
            "ending_paragraph_count": len(_nonempty_paragraphs(content)[-3:]),
        },
        config_hash=config_hash,
        created_at=utc_now(),
    )


def effective_content_sha256(row: Mapping[str, Any]) -> str:
    content = str(row.get("content", ""))
    return str(row.get("content_sha256") or sha256_bytes(content.encode("utf-8")))


def compare_title_similarity(left: ChapterFeature, right: ChapterFeature) -> float:
    return dice_similarity(left.normalized_title, right.normalized_title)


def compare_opening_similarity(left: ChapterFeature, right: ChapterFeature) -> dict[str, float]:
    return {
        "raw": dice_similarity(left.opening_excerpt_raw, right.opening_excerpt_raw),
        "prose": dice_similarity(left.opening_excerpt_prose, right.opening_excerpt_prose),
    }


def compare_ending_similarity(left: ChapterFeature, right: ChapterFeature) -> dict[str, float]:
    return {
        "raw": dice_similarity(left.ending_excerpt_raw, right.ending_excerpt_raw),
        "prose": dice_similarity(left.ending_excerpt_prose, right.ending_excerpt_prose),
    }


def iter_feature_rows(features: Iterable[ChapterFeature]) -> list[ChapterFeature]:
    return sorted(features, key=lambda item: (item.ordinal, item.chapter_id, item.feature_id))
