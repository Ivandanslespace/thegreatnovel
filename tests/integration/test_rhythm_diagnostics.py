from __future__ import annotations

import json
from pathlib import Path

import pytest

from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.rhythm.models import EmotionalIntensityBand
from novel_authoring.rhythm.service import (
    RhythmWorkflowError,
    diagnose_hooks,
    diagnose_rhythm,
    import_semantic_features,
    prepare_semantic_features,
    rebuild_features,
    show_features,
)


def _workspace(tmp_path: Path) -> tuple[Path, Database]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "book.md").write_text(
        "## 第一章 起点\n\n第一段。\n\n第二段。\n\n结尾。\n\n"
        "## 第二章 压力\n\n新的压力。\n\n角色决定留下。\n\n新的威胁。\n\n"
        "## 第三章 余波\n\n余波开始。\n\n选择完成。\n\n新的威胁。\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="rhythm-book",
        title="节奏测试",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
    )
    return workspace, Database(workspace / "rhythm-book" / "state.sqlite3")


def test_rebuild_features_is_edition_aware_and_deterministic(tmp_path: Path) -> None:
    workspace, database = _workspace(tmp_path)
    base = rebuild_features(database, "rhythm-book")
    derived = rebuild_features(database, "rhythm-book", edition_id="base")
    assert base["edition_id"] == "base"
    assert base["chapter_ids"] == derived["chapter_ids"]
    rows = show_features(database, "rhythm-book")
    assert len(rows) == 3
    assert all(row["edition_id"] == "base" for row in rows)
    assert workspace.exists()


def test_rhythm_snapshot_contains_diagnostics_without_total_score(tmp_path: Path) -> None:
    _, database = _workspace(tmp_path)
    snapshot = diagnose_rhythm(database, "rhythm-book")
    assert snapshot["as_of_chapter"] == 3
    assert "same_function_streak" in snapshot
    assert "high_emotion_streak" in snapshot
    assert "title_repetition" in snapshot
    assert "opening_similarity" in snapshot
    assert "ending_similarity" in snapshot
    assert "hooks" in snapshot
    assert "rhythm_score" not in snapshot


def test_hook_actions_follow_hold_advance_resolve_overdue_and_deferred(tmp_path: Path) -> None:
    _, database = _workspace(tmp_path)
    with database.connect() as connection:
        rows = [
            ("hold", 1, 2, 12, 0, 0, None),
            ("advance", 1, 1, 12, 0, 8, None),
            ("resolve", 1, 1, 12, 0.8, 0, None),
            ("overdue", 1, 1, 1, 0, 0, None),
            ("deferred", 1, 1, 2, 1, 0, 99),
        ]
        for promise_id, introduced, target_min, target_max, readiness, dormant, deferred in rows:
            connection.execute(
                """
                INSERT INTO promises(
                    promise_id, book_id, edition_id, thread_id, statement, importance,
                    reader_visibility, progress, introduced_ordinal, last_reminded_ordinal,
                    reminder_count, target_min_age, target_max_age, status, source_span_id,
                    payload_json, created_at, version, last_advanced_ordinal,
                    dormancy_target, resolution_readiness, dependencies_ready,
                    promise_horizon, author_deferred_until
                ) VALUES (?, 'rhythm-book', 'base', NULL, ?, 0.5, 0.5, 0,
                    ?, NULL, 0, ?, ?, 'CANON', NULL, '{}', 'now', 1, ?, 8, ?, 1,
                    'medium', ?)
                """,
                (
                    promise_id,
                    promise_id,
                    introduced,
                    target_min,
                    target_max,
                    3 - dormant,
                    readiness,
                    deferred,
                ),
            )
    result = diagnose_hooks(database, "rhythm-book")
    assert result["hold"]
    assert any(item["promise_id"] == "advance" for item in result["advance_due"])
    assert any(item["promise_id"] == "resolve" for item in result["resolve_due"])
    assert any(item["promise_id"] == "overdue" for item in result["overdue"])
    assert any(item["promise_id"] == "deferred" for item in result["hold"])


def test_semantic_features_require_real_evidence_and_allow_unknown(tmp_path: Path) -> None:
    _, database = _workspace(tmp_path)
    prepared = prepare_semantic_features(database, "rhythm-book", chapter_id=None)
    task = prepared["tasks"][0]
    metadata = json.loads(Path(task["input"].replace("input.md", "task.json")).read_text())
    bad = Path(task["expected_output"])
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text(
        json.dumps(
            {
                "task_id": task["task_id"],
                "book_id": "rhythm-book",
                "edition_id": "base",
                "chapter_id": metadata["chapter_id"],
                "content_sha256": metadata["content_sha256"],
                "realized_primary_function": None,
                "emotional_intensity_band": EmotionalIntensityBand.UNKNOWN,
                "opening_mode": "unknown",
                "ending_mode": "unknown",
                "evidence_quotes": ["不存在的证据"],
                "confidence": 0,
                "unknown_reasons": ["语义不足"],
                "analyzer_version": metadata["analyzer_version"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(RhythmWorkflowError, match="证据短句"):
        import_semantic_features(database, "rhythm-book", task["task_id"])
