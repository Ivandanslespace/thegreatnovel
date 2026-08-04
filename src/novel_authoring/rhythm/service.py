from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from novel_authoring.config import Settings, load_settings
from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, edition_workspace, resolve_edition_id
from novel_authoring.rhythm.features import (
    compare_ending_similarity,
    compare_opening_similarity,
    compare_title_similarity,
    effective_content_sha256,
    extract_chapter_feature,
    iter_feature_rows,
    series_marker,
)
from novel_authoring.rhythm.models import (
    ChapterFeature,
    ChapterSemanticFeaturesOutput,
    EmotionalIntensityBand,
    EndingMode,
    FeatureExtractorKind,
    HookAction,
    OpeningMode,
    RhythmDiagnosticSnapshot,
)
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now


class RhythmWorkflowError(RuntimeError):
    pass


_DEFAULT_RHYTHM_CONFIG: dict[str, Any] = {
    "analyzer_version": "rhythm-deterministic-v1",
    "semantic_analyzer_version": "rhythm-semantic-v1",
    "title_repetition": {
        "exact_duplicate_window": 50,
        "keyword_window": 12,
        "keyword_warning_count": 3,
        "similarity_window": 20,
        "similarity_warning_threshold": 0.82,
    },
    "opening_ending": {
        "text_window_chars": 300,
        "lexical_threshold": 0.72,
        "lookback_chapters": 4,
        "repeated_match_warning_count": 2,
        "mode_streak_warning": 3,
        "mode_streak_strong_warning": 5,
    },
    "function_streak": {
        "setup": {"warning": 2, "strong": 3},
        "pressure_build": {"warning": 3, "strong": 5},
        "choice": {"warning": 2, "strong": 3},
        "discovery": {"warning": 3, "strong": 4},
        "progress": {"warning": 4, "strong": 6},
        "partial_payoff": {"warning": 2, "strong": 3},
        "major_payoff": {"warning": 2, "strong": 2},
        "reversal": {"warning": 2, "strong": 3},
        "aftershock": {"warning": 2, "strong": 4},
        "recovery": {"warning": 2, "strong": 3},
        "relationship_shift": {"warning": 3, "strong": 4},
        "world_expansion": {"warning": 2, "strong": 3},
    },
    "high_emotion_streak": {"warning": 3, "strong_warning": 5, "climax_bonus": 2},
    "promise": {
        "default_dormancy_target": 8,
        "default_target_min_age": 3,
        "default_target_max_age": 12,
    },
}


def _rhythm_config(settings: Settings | None) -> dict[str, Any]:
    configured = {} if settings is None else dict(settings.rhythm)
    # A shallow copy plus recursive merge keeps a partial user override useful
    # while preserving deterministic defaults for newly introduced thresholds.
    def merge(left: dict[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(left)
        for key, value in right.items():
            if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
                result[key] = merge(dict(result[key]), value)
            else:
                result[key] = value
        return result

    return merge(_DEFAULT_RHYTHM_CONFIG, configured)


def _config_hash(config: Mapping[str, Any]) -> str:
    return sha256_bytes(json_dumps(dict(config)).encode("utf-8"))


def _feature_from_row(row: Mapping[str, Any]) -> ChapterFeature:
    row = dict(row)
    return ChapterFeature(
        feature_id=str(row["feature_id"]),
        book_id=str(row["book_id"]),
        edition_id=str(row["edition_id"]),
        chapter_id=str(row["chapter_id"]),
        ordinal=int(row.get("ordinal", 0)),
        effective_content_sha256=str(row["effective_content_sha256"]),
        analyzer_version=str(row["analyzer_version"]),
        planned_primary_function=row.get("planned_primary_function"),
        realized_primary_function=row.get("realized_primary_function"),
        function_confidence=(
            None if row.get("function_confidence") is None else float(row["function_confidence"])
        ),
        emotional_intensity_band=EmotionalIntensityBand(
            str(row.get("emotional_intensity_band") or EmotionalIntensityBand.UNKNOWN.value)
        ),
        emotional_confidence=(
            None if row.get("emotional_confidence") is None else float(row["emotional_confidence"])
        ),
        title_raw=str(row.get("title_raw") or ""),
        normalized_title=str(row["normalized_title"]),
        title_fingerprint=str(row["title_fingerprint"]),
        opening_excerpt_raw=str(row["opening_excerpt_raw"]),
        opening_excerpt_prose=str(row["opening_excerpt_prose"]),
        opening_fingerprint_raw=str(row["opening_fingerprint_raw"]),
        opening_fingerprint_prose=str(row["opening_fingerprint_prose"]),
        opening_mode=OpeningMode(str(row.get("opening_mode") or "unknown")),
        ending_excerpt_raw=str(row["ending_excerpt_raw"]),
        ending_excerpt_prose=str(row["ending_excerpt_prose"]),
        ending_fingerprint_raw=str(row["ending_fingerprint_raw"]),
        ending_fingerprint_prose=str(row["ending_fingerprint_prose"]),
        ending_mode=EndingMode(str(row.get("ending_mode") or "unknown")),
        extractor_kind=FeatureExtractorKind(str(row["extractor_kind"])),
        evidence=json.loads(str(row["evidence_json"])),
        config_hash=str(row["config_hash"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        invalidated_at=(None if row.get("invalidated_at") is None else str(row["invalidated_at"])),
    )


def _insert_feature(connection: Any, feature: ChapterFeature) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO chapter_features(
            feature_id, book_id, edition_id, chapter_id, effective_content_sha256,
            analyzer_version, planned_primary_function, realized_primary_function,
            function_confidence, emotional_intensity_band, emotional_confidence,
            title_raw, normalized_title, title_fingerprint, opening_excerpt_raw,
            opening_excerpt_prose,
            opening_fingerprint_raw, opening_fingerprint_prose, opening_mode,
            ending_excerpt_raw, ending_excerpt_prose, ending_fingerprint_raw,
            ending_fingerprint_prose, ending_mode, extractor_kind, evidence_json,
            config_hash, status, created_at, invalidated_at, version
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1
        )
        """,
        (
            feature.feature_id,
            feature.book_id,
            feature.edition_id,
            feature.chapter_id,
            feature.effective_content_sha256,
            feature.analyzer_version,
            None
            if feature.planned_primary_function is None
            else str(feature.planned_primary_function),
            None
            if feature.realized_primary_function is None
            else str(feature.realized_primary_function),
            feature.function_confidence,
            str(feature.emotional_intensity_band),
            feature.emotional_confidence,
            feature.title_raw,
            feature.normalized_title,
            feature.title_fingerprint,
            feature.opening_excerpt_raw,
            feature.opening_excerpt_prose,
            feature.opening_fingerprint_raw,
            feature.opening_fingerprint_prose,
            str(feature.opening_mode),
            feature.ending_excerpt_raw,
            feature.ending_excerpt_prose,
            feature.ending_fingerprint_raw,
            feature.ending_fingerprint_prose,
            str(feature.ending_mode),
            str(feature.extractor_kind),
            json_dumps(feature.evidence),
            feature.config_hash,
            feature.status,
            feature.created_at,
            feature.invalidated_at,
        ),
    )


def _invalidate_content_changes(
    connection: Any, book_id: str, edition_id: str, current_hashes: Mapping[str, str]
) -> None:
    now = utc_now()
    rows = connection.execute(
        """
        SELECT feature_id, chapter_id, effective_content_sha256
        FROM chapter_features
        WHERE book_id=? AND edition_id=?
          AND status IN ('ACTIVE', 'INSUFFICIENT_EVIDENCE')
        """,
        (book_id, edition_id),
    ).fetchall()
    for row in rows:
        chapter_id = str(row["chapter_id"])
        if (
            chapter_id in current_hashes
            and str(row["effective_content_sha256"]) != current_hashes[chapter_id]
        ):
            connection.execute(
                "UPDATE chapter_features SET status='INVALIDATED', invalidated_at=? "
                "WHERE feature_id=?",
                (now, str(row["feature_id"])),
            )


def _current_features(
    connection: Any, book_id: str, edition_id: str, chapters: list[dict[str, Any]]
) -> list[ChapterFeature]:
    result: list[ChapterFeature] = []
    preference = {
        FeatureExtractorKind.UNKNOWN.value: 0,
        FeatureExtractorKind.DETERMINISTIC.value: 1,
        FeatureExtractorKind.AUTHOR_POLICY.value: 2,
        FeatureExtractorKind.SEMANTIC_ESTIMATE.value: 3,
    }
    for chapter in chapters:
        chapter_id = str(chapter["chapter_id"])
        content_hash = effective_content_sha256(chapter)
        rows = connection.execute(
            """
            SELECT cf.*, c.ordinal
            FROM chapter_features cf JOIN chapters c ON c.chapter_id=cf.chapter_id
            WHERE cf.book_id=? AND cf.edition_id=? AND cf.chapter_id=?
              AND cf.effective_content_sha256=?
              AND cf.status IN ('ACTIVE', 'INSUFFICIENT_EVIDENCE')
            ORDER BY cf.created_at DESC
            """,
            (book_id, edition_id, chapter_id, content_hash),
        ).fetchall()
        if rows:
            selected = max(rows, key=lambda row: preference.get(str(row["extractor_kind"]), 0))
            result.append(_feature_from_row(selected))
    return iter_feature_rows(result)


def rebuild_features(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    rhythm = _rhythm_config(settings or load_settings())
    config_hash = _config_hash(rhythm)
    analyzer_version = str(rhythm["analyzer_version"])
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, selected)
        hashes = {str(row["chapter_id"]): effective_content_sha256(row) for row in chapters}
        _invalidate_content_changes(connection, book_id, selected, hashes)
        for row in chapters:
            feature = extract_chapter_feature(
                row,
                book_id=book_id,
                edition_id=selected,
                config_hash=config_hash,
                analyzer_version=analyzer_version,
                text_window_chars=int(rhythm["opening_ending"]["text_window_chars"]),
            )
            _insert_feature(connection, feature)
        current = _current_features(connection, book_id, selected, chapters)
    return {
        "book_id": book_id,
        "edition_id": selected,
        "config_hash": config_hash,
        "analyzer_version": analyzer_version,
        "feature_count": len(current),
        "chapter_ids": [item.chapter_id for item in current],
    }


def prepare_semantic_features(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    chapter_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    rhythm = _rhythm_config(settings or load_settings())
    rebuild_features(database, book_id, edition_id=selected, settings=settings)
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, selected)
        if chapter_id is not None:
            chapters = [row for row in chapters if str(row["chapter_id"]) == chapter_id]
        if not chapters:
            raise RhythmWorkflowError("没有可生成语义特征任务的章节")
    workspace = edition_workspace(database, book_id, selected)
    schema_json = json_dumps(ChapterSemanticFeaturesOutput.model_json_schema(), indent=2)
    tasks: list[dict[str, Any]] = []
    for chapter in chapters:
        content_hash = effective_content_sha256(chapter)
        task_id = stable_id(
            "chapter-semantic-features",
            book_id,
            selected,
            str(chapter["chapter_id"]),
            content_hash,
            sha256_bytes(schema_json.encode()),
        )
        task_dir = workspace / "agent_tasks" / task_id
        output_dir = workspace / "agent_outputs" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "task_id": task_id,
            "task_type": "CHAPTER_SEMANTIC_FEATURES",
            "book_id": book_id,
            "edition_id": selected,
            "chapter_id": str(chapter["chapter_id"]),
            "content_sha256": content_hash,
            "schema_sha256": sha256_bytes(schema_json.encode()),
            "analyzer_version": str(rhythm["semantic_analyzer_version"]),
            "created_at": utc_now(),
        }
        input_text = "\n".join(
            [
                f"# ChapterSemanticFeatures `{task_id}`",
                "",
                "仅根据给定正文提交结构化语义特征；每个判断都必须引用正文短证据。",
                "不确定时使用 UNKNOWN，并填写 unknown_reasons；不得凭空输出分数。",
                "",
                f"chapter_id: `{chapter['chapter_id']}`",
                f"content_sha256: `{content_hash}`",
                "",
                str(chapter.get("content", "")),
            ]
        )
        (task_dir / "input.md").write_text(input_text + "\n", encoding="utf-8")
        (task_dir / "schema.json").write_text(schema_json + "\n", encoding="utf-8")
        (task_dir / "task.json").write_text(json_dumps(metadata, indent=2) + "\n", encoding="utf-8")
        tasks.append(
            {
                "task_id": task_id,
                "chapter_id": str(chapter["chapter_id"]),
                "input": str(task_dir / "input.md"),
                "schema": str(task_dir / "schema.json"),
                "expected_output": str(output_dir / "output.json"),
            }
        )
    return {"book_id": book_id, "edition_id": selected, "tasks": tasks}


def import_semantic_features(
    database: Database,
    book_id: str,
    task_id: str,
    output_path: Path | None = None,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    database.initialize()
    with database.connect() as connection:
        book = connection.execute(
            "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    if book is None:
        raise RhythmWorkflowError(f"未知 book_id：{book_id}")
    root = Path(str(book["workspace_root"]))
    candidates = [root / "agent_tasks" / task_id / "task.json"]
    candidates.extend(root.glob(f"editions/*/agent_tasks/{task_id}/task.json"))
    task_path = next((path for path in candidates if path.is_file()), None)
    if task_path is None:
        raise RhythmWorkflowError(f"语义特征任务不存在：{task_id}")
    metadata = json.loads(task_path.read_text(encoding="utf-8"))
    selected = str(metadata.get("edition_id", "base"))
    workspace = edition_workspace(database, book_id, selected)
    path = output_path or workspace / "agent_outputs" / task_id / "output.json"
    try:
        output = ChapterSemanticFeaturesOutput.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise RhythmWorkflowError(f"语义特征 output.json 不符合合同：{exc}") from exc
    if output.task_id != task_id or output.book_id != book_id:
        raise RhythmWorkflowError("语义特征 task/book 不匹配")
    if output.edition_id != selected or output.chapter_id != str(metadata["chapter_id"]):
        raise RhythmWorkflowError("语义特征 edition/chapter 不匹配")
    if output.content_sha256 != str(metadata["content_sha256"]):
        raise RhythmWorkflowError("语义特征 content_sha256 与任务 preimage 不匹配")
    with database.connect() as connection:
        chapter = connection.execute(
            "SELECT * FROM chapters WHERE book_id=? AND chapter_id=?",
            (book_id, output.chapter_id),
        ).fetchone()
        if chapter is None:
            raise RhythmWorkflowError("语义特征章节不存在")
        content = str(chapter["content"])
        if effective_content_sha256(dict(chapter)) != output.content_sha256:
            # A variant is resolved through the edition chapter view, not the
            # immutable base row.
            view = [
                row
                for row in edition_chapters(connection, book_id, selected)
                if str(row["chapter_id"]) == output.chapter_id
            ]
            content = "" if not view else str(view[0].get("content", ""))
        if output.evidence_quotes and any(quote not in content for quote in output.evidence_quotes):
            raise RhythmWorkflowError("语义证据短句不存在于该 edition 正文")
        if not output.evidence_quotes and output.confidence > 0:
            raise RhythmWorkflowError("confidence 大于 0 时必须提供正文证据")
        view = [
            row
            for row in edition_chapters(connection, book_id, selected)
            if str(row["chapter_id"]) == output.chapter_id
        ]
        if not view:
            raise RhythmWorkflowError("当前 edition 中不存在该章节")
        rhythm = _rhythm_config(settings or load_settings())
        config_hash = _config_hash(rhythm)
        base = extract_chapter_feature(
            view[0],
            book_id=book_id,
            edition_id=selected,
            config_hash=config_hash,
            analyzer_version=output.analyzer_version,
            text_window_chars=int(rhythm["opening_ending"]["text_window_chars"]),
        )
        feature = base.model_copy(
            update={
                "feature_id": stable_id(
                    "chapter-feature-semantic",
                    book_id,
                    selected,
                    output.chapter_id,
                    output.content_sha256,
                    output.analyzer_version,
                ),
                "realized_primary_function": output.realized_primary_function,
                "function_confidence": output.confidence,
                "emotional_intensity_band": output.emotional_intensity_band,
                "emotional_confidence": output.confidence,
                "opening_mode": output.opening_mode,
                "ending_mode": output.ending_mode,
                "extractor_kind": FeatureExtractorKind.SEMANTIC_ESTIMATE,
                "status": (
                    "INSUFFICIENT_EVIDENCE"
                    if output.confidence == 0 and not output.evidence_quotes
                    else "ACTIVE"
                ),
                "evidence": {
                    "evidence_quotes": output.evidence_quotes,
                    "unknown_reasons": output.unknown_reasons,
                    "task_id": output.task_id,
                },
            }
        )
        _insert_feature(connection, feature)
    return {
        "task_id": task_id,
        "feature_id": feature.feature_id,
        "book_id": book_id,
        "edition_id": selected,
        "chapter_id": output.chapter_id,
        "extractor_kind": feature.extractor_kind,
    }


def _severity(count: int, warning: int, strong: int) -> str:
    if count >= strong:
        return "STRONG_WARNING"
    if count >= warning:
        return "WARNING"
    return "NONE"


def _tail_streak(values: list[str | None]) -> tuple[str | None, int]:
    if not values or values[-1] is None:
        return None, 0
    target = values[-1]
    count = 0
    for value in reversed(values):
        if value != target:
            break
        count += 1
    return target, count


def _promise_action(
    row: Mapping[str, Any], current_ordinal: int, config: Mapping[str, Any]
) -> tuple[HookAction, dict[str, Any]]:
    introduced = int(row.get("introduced_ordinal") or 0)
    last_advanced = int(row.get("last_advanced_ordinal") or introduced)
    age = max(0, current_ordinal - introduced)
    dormancy = max(0, current_ordinal - last_advanced)
    target_min = int(row.get("target_min_age") or config["default_target_min_age"])
    target_max = int(row.get("target_max_age") or config["default_target_max_age"])
    dormancy_target = int(row.get("dormancy_target") or config["default_dormancy_target"])
    readiness = float(row.get("resolution_readiness") or 0)
    dependencies_ready = bool(row.get("dependencies_ready"))
    deferred = row.get("author_deferred_until")
    if (
        (deferred is not None and int(deferred) > current_ordinal)
        or (not dependencies_ready and age / max(target_max, 1) < 1)
    ):
        action = HookAction.HOLD
    elif age > target_max:
        action = HookAction.OVERDUE
    elif age >= target_min and readiness >= 0.7:
        action = HookAction.RESOLVE
    elif dormancy / max(dormancy_target, 1) >= 1:
        action = HookAction.ADVANCE
    else:
        action = HookAction.HOLD
    return action, {
        "promise_id": str(row.get("promise_id", "")),
        "thread_id": row.get("thread_id"),
        "statement": row.get("statement", ""),
        "introduced_ordinal": introduced,
        "current_ordinal": current_ordinal,
        "age": age,
        "last_advanced_ordinal": last_advanced,
        "dormancy": dormancy,
        "age_ratio": age / max(target_max, 1),
        "dormancy_ratio": dormancy / max(dormancy_target, 1),
        "resolution_readiness": readiness,
        "dependencies_ready": dependencies_ready,
        "evidence": [
            f"Age={age} (current={current_ordinal}, introduced={introduced})",
            f"Dormancy={dormancy} (last_advanced={last_advanced})",
        ],
        "action": action.value,
    }


def diagnose_hooks(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    rhythm = _rhythm_config(settings or load_settings())["promise"]
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, selected)
        current = max((int(item["ordinal"]) for item in chapters), default=0)
        projection = None
        if selected != "base":
            from novel_authoring.canon.projection import rebuild_projection

            projection = rebuild_projection(database, book_id, edition_id=selected, persist=False)
        rows: list[Mapping[str, Any]]
        if projection is None:
            rows = [
                dict(row)
                for row in connection.execute(
                "SELECT * FROM promises WHERE book_id=? AND edition_id=? AND status='CANON'",
                (book_id, selected),
                ).fetchall()
            ]
        else:
            rows = []
            for promise_id, promise_value in projection.promises.items():
                item = dict(promise_value)
                item.setdefault("promise_id", promise_id)
                rows.append(item)
    queues: dict[str, list[dict[str, Any]]] = {action.value: [] for action in HookAction}
    for row in rows:
        action, payload = _promise_action(row, current, rhythm)
        queues[action.value].append(payload)
    for value in queues.values():
        value.sort(key=lambda item: (int(item["age"]), str(item["promise_id"])), reverse=True)
    return {
        "book_id": book_id,
        "edition_id": selected,
        "as_of_chapter": current,
        "advance_due": queues[HookAction.ADVANCE.value],
        "resolve_due": queues[HookAction.RESOLVE.value],
        "overdue": queues[HookAction.OVERDUE.value],
        "hold": queues[HookAction.HOLD.value],
        "queues": queues,
    }


def _latest_features(
    database: Database, book_id: str, edition_id: str, *, settings: Settings | None = None
) -> list[ChapterFeature]:
    rhythm = _rhythm_config(settings or load_settings())
    analyzer = str(rhythm["analyzer_version"])
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, edition_id)
        # Rebuild is intentionally explicit; it also invalidates stale hashes.
        current_hashes = {str(row["chapter_id"]): effective_content_sha256(row) for row in chapters}
        _invalidate_content_changes(connection, book_id, edition_id, current_hashes)
        rows = connection.execute(
            """
            SELECT cf.*, c.ordinal
            FROM chapter_features cf JOIN chapters c ON c.chapter_id=cf.chapter_id
            WHERE cf.book_id=? AND cf.edition_id=?
              AND cf.status IN ('ACTIVE', 'INSUFFICIENT_EVIDENCE')
              AND cf.analyzer_version IN (?, ?)
            ORDER BY c.ordinal, cf.created_at DESC
            """,
            (book_id, edition_id, analyzer, str(rhythm["semantic_analyzer_version"])),
        ).fetchall()
        by_chapter: dict[str, list[Any]] = {}
        for row in rows:
            chapter_id = str(row["chapter_id"])
            if current_hashes.get(chapter_id) != str(row["effective_content_sha256"]):
                continue
            by_chapter.setdefault(chapter_id, []).append(row)
        preference = {
            FeatureExtractorKind.UNKNOWN.value: 0,
            FeatureExtractorKind.DETERMINISTIC.value: 1,
            FeatureExtractorKind.AUTHOR_POLICY.value: 2,
            FeatureExtractorKind.SEMANTIC_ESTIMATE.value: 3,
        }
        selected_rows = [
            max(
                values,
                key=lambda row: (
                    preference.get(str(row["extractor_kind"]), 0),
                    str(row["created_at"]),
                ),
            )
            for values in by_chapter.values()
        ]
        return iter_feature_rows([_feature_from_row(row) for row in selected_rows])


def diagnose_rhythm(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    settings: Settings | None = None,
    as_of_chapter: int | None = None,
) -> dict[str, Any]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    settings_value = settings or load_settings()
    rhythm = _rhythm_config(settings_value)
    # Deterministic features are always rebuilt; semantic estimates remain
    # separate rows and are selected when their evidence matches the hash.
    rebuild_features(database, book_id, edition_id=selected, settings=settings_value)
    features = _latest_features(database, book_id, selected, settings=settings_value)
    if as_of_chapter is not None:
        features = [item for item in features if item.ordinal <= as_of_chapter]
    current = max((item.ordinal for item in features), default=0)
    function_values = [
        str(item.realized_primary_function or item.planned_primary_function)
        if (item.realized_primary_function or item.planned_primary_function) is not None
        else None
        for item in features
    ]
    function, function_count = _tail_streak(function_values)
    function_threshold = rhythm["function_streak"].get(
        function or "", {"warning": 99, "strong": 100}
    )
    same_function = {
        "function": function,
        "count": function_count,
        "severity": _severity(
            function_count,
            int(function_threshold.get("warning", 99)),
            int(function_threshold.get("strong", 100)),
        ),
        "source": "realized_primary_function"
        if any(item.realized_primary_function is not None for item in features[-function_count:])
        else "planned_primary_function",
    }
    emotions = [
        item.emotional_intensity_band.value
        if item.emotional_intensity_band
        in {EmotionalIntensityBand.HIGH, EmotionalIntensityBand.EXTREME}
        else None
        for item in features
    ]
    emotion_count = 0
    for value in reversed(emotions):
        if value is None:
            break
        emotion_count += 1
    emotion_config = rhythm["high_emotion_streak"]
    high_emotion = {
        "count": emotion_count,
        "severity": _severity(
            emotion_count,
            int(emotion_config["warning"]),
            int(emotion_config["strong_warning"]),
        ),
        "bands": [item.emotional_intensity_band.value for item in features[-emotion_count:]]
        if emotion_count
        else [],
        "climax_bonus": int(emotion_config["climax_bonus"]),
    }
    title_config = rhythm["title_repetition"]
    title_window = features[-int(title_config["similarity_window"]) :]
    max_title = 0.0
    title_matches: list[int] = []
    for index, item in enumerate(title_window):
        for prior in title_window[:index]:
            score = compare_title_similarity(item, prior)
            if score > max_title:
                max_title = score
            if score >= float(title_config["similarity_warning_threshold"]):
                title_matches.append(prior.ordinal)
    exact_window = features[-int(title_config["exact_duplicate_window"]) :]
    exact_titles: dict[str, list[int]] = {}
    for item in exact_window:
        exact_titles.setdefault(item.normalized_title, []).append(item.ordinal)
    exact_duplicates = [values for values in exact_titles.values() if len(values) > 1 and values[0]]
    title_severity = "WARNING" if exact_duplicates or title_matches else "NONE"
    # A series marker is deliberate continuity, so downgrade a sole match.
    if title_severity == "WARNING" and title_window and all(
        series_marker(item.normalized_title) for item in title_window
    ):
        title_severity = "NONE"
    title_repetition = {
        "max_similarity_last_20": max_title,
        "exact_duplicates": exact_duplicates,
        "matching_chapters": sorted(set(title_matches)),
        "severity": title_severity,
        "series_markers": [series_marker(item.normalized_title) for item in title_window],
    }
    open_config = rhythm["opening_ending"]
    lookback = int(open_config["lookback_chapters"])
    recent = features[-lookback:]
    opening_matches: list[dict[str, Any]] = []
    ending_matches: list[dict[str, Any]] = []
    for index, item in enumerate(recent):
        for prior in recent[:index]:
            opening = compare_opening_similarity(item, prior)
            ending = compare_ending_similarity(item, prior)
            if opening["prose"] >= float(open_config["lexical_threshold"]):
                opening_matches.append(
                    {"chapter": item.ordinal, "matching_chapter": prior.ordinal, **opening}
                )
            if ending["prose"] >= float(open_config["lexical_threshold"]):
                ending_matches.append(
                    {"chapter": item.ordinal, "matching_chapter": prior.ordinal, **ending}
                )
    opening_similarity = {
        "max_similarity_last_4": max((item["prose"] for item in opening_matches), default=0.0),
        "matching_chapters": opening_matches,
        "severity": "WARNING"
        if len(opening_matches) >= int(open_config["repeated_match_warning_count"])
        else "NONE",
    }
    ending_similarity = {
        "max_similarity_last_4": max((item["prose"] for item in ending_matches), default=0.0),
        "matching_chapters": ending_matches,
        "severity": "WARNING"
        if len(ending_matches) >= int(open_config["repeated_match_warning_count"])
        else "NONE",
    }
    ending_mode, ending_count = _tail_streak([str(item.ending_mode) for item in features])
    ending_mode_streak = {
        "mode": ending_mode,
        "count": ending_count,
        "severity": _severity(
            ending_count,
            int(open_config["mode_streak_warning"]),
            int(open_config["mode_streak_strong_warning"]),
        ),
    }
    hooks = diagnose_hooks(database, book_id, edition_id=selected, settings=settings_value)
    with database.connect() as connection:
        from novel_authoring.canon.projection import projection_from_connection

        projection = projection_from_connection(connection, book_id, edition_id=selected)
    config_hash = _config_hash(rhythm)
    analyzer_versions = {
        "deterministic": str(rhythm["analyzer_version"]),
        "semantic": str(rhythm["semantic_analyzer_version"]),
    }
    snapshot_payload = {
        "edition_id": selected,
        "as_of_chapter": current,
        "same_function_streak": same_function,
        "high_emotion_streak": high_emotion,
        "title_repetition": title_repetition,
        "opening_similarity": opening_similarity,
        "ending_similarity": ending_similarity,
        "ending_mode_streak": ending_mode_streak,
        "hooks": {
            "advance_due": hooks["advance_due"],
            "resolve_due": hooks["resolve_due"],
            "overdue": hooks["overdue"],
        },
        "evidence": [
            {
                "chapter_id": item.chapter_id,
                "ordinal": item.ordinal,
                "extractor_kind": item.extractor_kind,
            }
            for item in features[-lookback:]
        ],
    }
    snapshot_id = stable_id(
        "rhythm-snapshot",
        book_id,
        selected,
        str(current),
        str(projection.through_event_seq),
        config_hash,
    )
    snapshot = RhythmDiagnosticSnapshot(
        snapshot_id=snapshot_id,
        book_id=book_id,
        edition_id=selected,
        as_of_chapter=current,
        as_of_event_seq=projection.through_event_seq,
        projection_hash=projection.sha256(),
        config_hash=config_hash,
        analyzer_versions=analyzer_versions,
        same_function_streak=same_function,
        high_emotion_streak=high_emotion,
        title_repetition=title_repetition,
        opening_similarity=opening_similarity,
        ending_similarity=ending_similarity,
        ending_mode_streak=ending_mode_streak,
        hooks={
            "advance_due": hooks["advance_due"],
            "resolve_due": hooks["resolve_due"],
            "overdue": hooks["overdue"],
        },
        evidence=cast(list[dict[str, Any]], snapshot_payload["evidence"]),
        created_at=utc_now(),
    )
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO rhythm_diagnostic_snapshots(
                snapshot_id, book_id, edition_id, as_of_chapter, as_of_event_seq,
                projection_hash, config_hash, analyzer_versions_json, snapshot_json,
                created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, as_of_chapter, as_of_event_seq, config_hash)
            DO UPDATE SET snapshot_id=excluded.snapshot_id,
                projection_hash=excluded.projection_hash,
                analyzer_versions_json=excluded.analyzer_versions_json,
                snapshot_json=excluded.snapshot_json,
                created_at=excluded.created_at
            """,
            (
                snapshot.snapshot_id,
                book_id,
                selected,
                current,
                snapshot.as_of_event_seq,
                snapshot.projection_hash,
                config_hash,
                json_dumps(analyzer_versions),
                json_dumps(snapshot.model_dump(mode="json")),
                snapshot.created_at,
            ),
        )
    return snapshot.model_dump(mode="json")


def show_latest_rhythm(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
) -> dict[str, Any]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM rhythm_diagnostic_snapshots
            WHERE book_id=? AND edition_id=?
            ORDER BY as_of_chapter DESC, created_at DESC LIMIT 1
            """,
            (book_id, selected),
        ).fetchone()
    if row is None:
        raise RhythmWorkflowError("尚无节奏诊断快照；请先运行 rhythm diagnose")
    return cast(dict[str, Any], json.loads(str(row["snapshot_json"])))


def show_features(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    chapter_id: str | None = None,
) -> list[dict[str, Any]]:
    """Read current effective feature rows without mutating the book."""
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, selected)
        current = _current_features(connection, book_id, selected, chapters)
    if chapter_id is not None:
        current = [item for item in current if item.chapter_id == chapter_id]
    return [item.model_dump(mode="json") for item in current]
