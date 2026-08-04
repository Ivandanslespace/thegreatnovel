from __future__ import annotations

from pathlib import Path

import pytest

from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.metrics.models import ObservationSourceKind
from novel_authoring.metrics.registry import load_registry
from novel_authoring.metrics.segments import SegmentKind, classify_segment, split_segments
from novel_authoring.metrics.service import (
    MetricObservationService,
    MetricsAssembler,
    MetricValidationError,
    ObservationInput,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def _database(tmp_path: Path) -> Database:
    source = tmp_path / "book"
    source.mkdir()
    (source / FIXTURE.name).write_bytes(FIXTURE.read_bytes())
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="metric-book",
        title="合成求生小说",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
    )
    return Database(workspace / "metric-book" / "state.sqlite3")


def test_registry_is_strict_and_segments_preserve_blocks() -> None:
    registry = load_registry()
    assert registry.registry_hash
    with pytest.raises(ValueError):
        registry.metric("not-registered")
    blocks = split_segments("第一段。\n\n【系统：警告】\n\n“选择。”")
    assert [
        classify_segment(text) for _, _, text in blocks
    ] == [SegmentKind.PROSE, SegmentKind.SYSTEM_PANEL, SegmentKind.DIALOGUE]


def test_missing_score_is_null_and_author_input_is_append_only(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database.connect() as connection:
        chapter = connection.execute(
            "SELECT chapter_id, content_sha256 FROM chapters ORDER BY ordinal DESC LIMIT 1"
        ).fetchone()
    chapter_id = str(chapter["chapter_id"])
    result = MetricsAssembler(database).rebuild("metric-book", scope_id=chapter_id)
    pressure_result = next(item for item in result["results"] if item["metric_id"] == "pressure")
    assert pressure_result["score"] is None
    assert pressure_result["missing_components"]

    service = MetricObservationService(database)
    with pytest.raises(MetricValidationError):
        service.append(
            ObservationInput(
                book_id="metric-book",
                edition_id="base",
                scope_type="CHAPTER",
                scope_id=chapter_id,
                metric_id="pressure",
                component_id="threat",
                value=101,
                source_kind=ObservationSourceKind.AUTHOR_INPUT,
                reason="out of range",
            )
        )
