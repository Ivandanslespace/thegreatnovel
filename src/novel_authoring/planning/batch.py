from __future__ import annotations

import json
import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from novel_authoring.atlas.service import (
    AtlasError,
    atlas_usage,
    get_atlas_overview,
    latest_atlas,
    required_far_end_chapter,
)
from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.metrics.registry import load_registry
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.manifest import authority_path, manifest_hash
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now
from novel_authoring.validation.models import VALIDATOR_NAMES


class BatchStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    CHECKPOINT = "CHECKPOINT"
    BATCH_VALIDATED = "BATCH_VALIDATED"
    STALE = "STALE"
    CANCELLED = "CANCELLED"


class BatchChunkPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    chunk_order: int = Field(ge=1)
    start_chapter_ordinal: int = Field(ge=1)
    end_chapter_ordinal: int = Field(ge=1)
    chapter_ordinals: list[int]
    input_projection_hash: str
    required_inputs: list[str] = Field(default_factory=list)
    prompt_contract: str

    @model_validator(mode="after")
    def validate_chunk(self) -> BatchChunkPlan:
        expected = list(range(self.start_chapter_ordinal, self.end_chapter_ordinal + 1))
        if self.chapter_ordinals != expected:
            raise ValueError("Batch chunk 的章节必须连续且不跳号")
        if str(self.end_chapter_ordinal) not in self.prompt_contract:
            raise ValueError("chunk prompt_contract 必须绑定当前 chunk 终点")
        return self


class BatchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    book_id: str
    edition_id: str
    target_chapter_count: int = Field(gt=0)
    chunk_size: int = Field(gt=0)
    checkpoint_interval: int = Field(gt=0)
    current_chapter_ordinal: int = Field(ge=0)
    required_far_end_chapter: int = Field(ge=0)
    atlas_id: str
    atlas_version: int = Field(ge=1)
    atlas_hash: str
    horizon_hash: str
    source_manifest_sha256: str
    effective_content_sha256: str
    registry_hash: str
    config_hash: str
    author_directives_hash: str
    metric_bundle_hash: str
    chunks: list[BatchChunkPlan]

    @model_validator(mode="after")
    def validate_no_giant_prompt(self) -> BatchPlan:
        expected_count = (self.target_chapter_count + self.chunk_size - 1) // self.chunk_size
        if len(self.chunks) != expected_count:
            raise ValueError("Batch 必须拆成 chunk，不能用单个巨型 prompt")
        if any(len(item.chapter_ordinals) > self.chunk_size for item in self.chunks):
            raise ValueError("单个 chunk 超出 chunk_size")
        ordered = sorted(self.chunks, key=lambda item: item.chunk_order)
        expected_start = self.current_chapter_ordinal + 1
        for index, item in enumerate(ordered, start=1):
            if item.chunk_order != index or item.start_chapter_ordinal != expected_start:
                raise ValueError("Batch chunks 必须按章节连续覆盖且 chunk_order 连续")
            expected_start = item.end_chapter_ordinal + 1
        if expected_start != self.current_chapter_ordinal + self.target_chapter_count + 1:
            raise ValueError("Batch chunks 未完整覆盖 target_chapter_count")
        return self


class BatchProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    book_id: str
    edition_id: str
    current_chapter_ordinal: int
    projection_hash: str
    state: dict[str, Any] = Field(default_factory=dict)
    status: BatchStatus
    atlas_id: str | None = None
    atlas_version: int | None = None
    atlas_hash: str = ""
    horizon_hash: str = ""


class BatchProvisionalState(BaseModel):
    """Typed temporary state; it cannot carry a Canon commit."""

    model_config = ConfigDict(extra="forbid")

    current_chapter_ordinal: int = Field(ge=0)
    canon_projection_hash: str = ""
    atlas_id: str = ""
    atlas_version: int | None = None
    atlas_hash: str = ""
    horizon_hash: str = ""
    source_manifest_sha256: str = ""
    effective_content_sha256: str = ""
    registry_hash: str = ""
    config_hash: str = ""
    author_directives_hash: str = ""
    metric_bundle_hash: str = ""
    last_checkpoint_ordinal: int = Field(default=0, ge=0)
    provisional_events: list[dict[str, Any]] = Field(default_factory=list)
    provisional_facts: list[dict[str, Any]] = Field(default_factory=list)
    provisional_threads: list[dict[str, Any]] = Field(default_factory=list)
    atlas_candidate_changes: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    canon_committed: Literal[False] = False
    canon_commit_id: None = None

    @model_validator(mode="after")
    def reject_canon_materialization(self) -> BatchProvisionalState:
        if self.canon_committed or self.canon_commit_id is not None:
            raise ValueError("Batch provisional state 不得包含 Canon commit")
        for collection in (
            self.provisional_events,
            self.provisional_facts,
            self.provisional_threads,
            self.atlas_candidate_changes,
        ):
            for item in collection:
                lowered = {str(key).lower() for key in item}
                if {"canon_event_id", "canon_commit_id", "canon_committed"} & lowered:
                    raise ValueError("Batch provisional state 不得包含 Canon 事件或批准标记")
                if any(str(value).upper() == "CANON" for value in item.values()):
                    raise ValueError("Batch provisional state 不得把临时记录标记为 CANON")
        return self


class BatchChapterValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_ordinal: int = Field(ge=1)
    boundary_hash: str
    contract_id: str
    validation_report_ids: list[str] = Field(min_length=10, max_length=10)
    validator_names: list[str] = Field(min_length=10, max_length=10)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_ten_validators(self) -> BatchChapterValidation:
        if tuple(self.validator_names) != VALIDATOR_NAMES:
            raise ValueError("每章必须按既有顺序提供十项 Validator 报告")
        if len(set(self.validation_report_ids)) != 10:
            raise ValueError("每章十项 Validator report_id 必须唯一")
        return self


class BatchValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapters: list[BatchChapterValidation] = Field(min_length=1)
    passed: Literal[True] = True

    def validate_range(self, expected_ordinals: list[int]) -> BatchValidationSummary:
        actual = [item.chapter_ordinal for item in self.chapters]
        if actual != expected_ordinals:
            raise ValueError("Batch chunk 的 validation summary 必须逐章连续覆盖")
        return self


class BatchError(RuntimeError):
    status_code = 409


def _workspace(database: Database, book_id: str) -> Path:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    if row is None:
        raise BatchError(f"未知 book_id：{book_id}")
    return Path(str(row["workspace_root"]))


def _batch_root(database: Database, book_id: str, edition_id: str, batch_id: str) -> Path:
    root = _workspace(database, book_id)
    if (root / "book.yaml").is_file():
        return BookLayout(root.parent).for_book(book_id).edition(edition_id).batches / batch_id
    return root / "editions" / edition_id / "batches" / batch_id


def _anchor(database: Database, book_id: str, edition_id: str) -> tuple[int, str, int, str]:
    with database.connect() as connection:
        projection = projection_from_connection(connection, book_id, edition_id)
        chapters = edition_chapters(connection, book_id, edition_id)
    current = int(chapters[-1]["ordinal"]) if chapters else 0
    effective_content = str(chapters[-1].get("content_sha256") or "") if chapters else ""
    return projection.through_event_seq, projection.sha256(), current, effective_content


def _state_hash(state: dict[str, Any]) -> str:
    return sha256_bytes(json_dumps(state).encode("utf-8"))


def _author_directives_hash(database: Database, book_id: str, edition_id: str) -> str:
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT directive_id, directive_type, content, mode, status, priority "
            "FROM author_directives WHERE book_id=? AND edition_id=? "
            "ORDER BY priority DESC, created_at, directive_id",
            (book_id, edition_id),
        ).fetchall()
    return sha256_bytes(json_dumps([dict(row) for row in rows]).encode("utf-8"))


def _metric_bundle_hash(database: Database, book_id: str, edition_id: str) -> str:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT input_bundle_hash FROM metric_runs "
            "WHERE book_id=? AND edition_id=? AND invalidated_at IS NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (book_id, edition_id),
        ).fetchone()
    return "" if row is None else str(row["input_bundle_hash"] or "")


def _config_hash() -> str:
    return sha256_bytes(json_dumps(load_settings().metrics).encode("utf-8"))


def _batch_drift_reasons(
    database: Database, row: sqlite3.Row | dict[str, Any]
) -> list[str]:
    """Return deterministic inputs that changed after a Batch was frozen."""
    status = str(row["status"])
    if status not in {
        BatchStatus.PLANNED.value,
        BatchStatus.RUNNING.value,
        BatchStatus.CHECKPOINT.value,
    }:
        return []

    book_id = str(row["book_id"])
    edition_id = str(row["edition_id"])
    reasons: list[str] = []
    try:
        base_event_seq, base_projection_hash, _current, effective_hash = _anchor(
            database, book_id, edition_id
        )
        if int(row["base_event_seq"]) != base_event_seq:
            reasons.append("Canon event sequence")
        if str(row["base_projection_hash"]) != base_projection_hash:
            reasons.append("Canon projection hash")
        if str(row["input_effective_content_sha256"] or "") != effective_hash:
            reasons.append("effective edition content hash")
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        reasons.append(f"current edition anchor unavailable: {exc}")

    workspace = _workspace(database, book_id)
    source_manifest = authority_path(workspace)
    current_source_hash = manifest_hash(source_manifest) if source_manifest.is_file() else ""
    if str(row["source_manifest_sha256"] or "") != current_source_hash:
        reasons.append("source manifest hash")

    try:
        if str(row["registry_hash"] or "") != load_registry().registry_hash:
            reasons.append("metric registry hash")
    except (OSError, ValueError, KeyError) as exc:
        reasons.append(f"metric registry unavailable: {exc}")
    try:
        if str(row["config_hash"] or "") != _config_hash():
            reasons.append("config hash")
    except (OSError, ValueError, TypeError) as exc:
        reasons.append(f"config unavailable: {exc}")
    if str(row["author_directives_hash"] or "") != _author_directives_hash(
        database, book_id, edition_id
    ):
        reasons.append("author directives hash")
    if str(row["metric_bundle_hash"] or "") != _metric_bundle_hash(
        database, book_id, edition_id
    ):
        reasons.append("metric bundle hash")

    atlas_row = latest_atlas(database, book_id, edition_id)
    if atlas_row is None:
        reasons.append("ACTIVE Story Atlas missing")
    else:
        if str(row["atlas_id"] or "") != str(atlas_row["atlas_id"]):
            reasons.append("Story Atlas id")
        if int(row["atlas_version"] or 0) != int(atlas_row["atlas_version"]):
            reasons.append("Story Atlas version")
        if str(row["atlas_hash"] or "") != str(atlas_row["atlas_content_hash"] or ""):
            reasons.append("Story Atlas content hash")
        if str(row["horizon_hash"] or "") != str(atlas_row["horizon_hash"] or ""):
            reasons.append("Rolling Horizon hash")
        try:
            overview = get_atlas_overview(
                database, book_id, edition_id, atlas_id=str(atlas_row["atlas_id"])
            )
            if overview.get("errors"):
                reasons.append("Story Atlas validation")
            if not isinstance(overview.get("rolling_horizon"), dict):
                reasons.append("Rolling Horizon missing")
        except (AtlasError, OSError, ValueError) as exc:
            reasons.append(f"Story Atlas unavailable: {exc}")
    return sorted(set(reasons))


def _mark_batch_stale_if_needed(
    database: Database, batch_id: str, row: sqlite3.Row
) -> sqlite3.Row | dict[str, Any]:
    reasons = _batch_drift_reasons(database, row)
    if not reasons:
        return row
    state = json.loads(str(row["state_json"] or "{}"))
    state["stale_reasons"] = reasons
    now = utc_now()
    reason_text = "Batch 输入 hash 漂移：" + ", ".join(reasons)
    with database.connect() as connection:
        connection.execute(
            "UPDATE batch_working_projections SET status=?, state_json=?, "
            "updated_at=?, version=version+1 WHERE batch_id=? AND status IN (?, ?, ?)",
            (
                BatchStatus.STALE.value,
                json_dumps(state),
                now,
                batch_id,
                BatchStatus.PLANNED.value,
                BatchStatus.RUNNING.value,
                BatchStatus.CHECKPOINT.value,
            ),
        )
        connection.execute(
            "UPDATE batch_chunk_states SET failure_reason=? "
            "WHERE batch_id=? AND status='PLANNED'",
            (reason_text, batch_id),
        )
    updated = dict(row)
    updated["status"] = BatchStatus.STALE.value
    updated["state_json"] = json_dumps(state)
    return updated


def _ensure_batch_continuable(projection: BatchProjection) -> None:
    if projection.status is BatchStatus.STALE:
        reasons = projection.state.get("stale_reasons", [])
        raise BatchError(
            "Batch 已因输入 hash 漂移标记为 STALE，必须重新建立 Batch："
            + ", ".join(str(item) for item in reasons)
        )
    if projection.status is BatchStatus.CANCELLED:
        raise BatchError("Batch 已取消，不能继续")


def _batch_plan(
    batch_id: str,
    book_id: str,
    edition_id: str,
    current: int,
    target: int,
    chunk_size: int,
    checkpoint_interval: int,
    projection_hash: str,
    atlas_id: str,
    atlas_version: int,
    atlas_hash: str,
    horizon_hash: str,
    source_manifest_sha256: str,
    effective_content_sha256: str,
    registry_hash: str,
    config_hash: str,
    author_directives_hash: str,
    metric_bundle_hash: str,
) -> BatchPlan:
    chunks: list[BatchChunkPlan] = []
    remaining = target
    start = current + 1
    order = 1
    while remaining > 0:
        count = min(chunk_size, remaining)
        end = start + count - 1
        chunks.append(
            BatchChunkPlan(
                chunk_id=stable_id("batch-chunk", batch_id, str(order)),
                chunk_order=order,
                start_chapter_ordinal=start,
                end_chapter_ordinal=end,
                chapter_ordinals=list(range(start, end + 1)),
                input_projection_hash=projection_hash,
                required_inputs=[
                    "Deterministic Canon projection",
                    "Batch Provisional Projection from the previous chunk",
                    "Versioned Story Atlas",
                    "NEAR Rolling Horizon",
                    "relevant Metric Run",
                ],
                prompt_contract=(
                    f"只处理 batch={batch_id} chunk={order}，章节范围 {start}-{end}；"
                    "每章完成后更新 provisional state，禁止直接写入 Canon。"
                ),
            )
        )
        remaining -= count
        start = end + 1
        order += 1
    return BatchPlan(
        batch_id=batch_id,
        book_id=book_id,
        edition_id=edition_id,
        target_chapter_count=target,
        chunk_size=chunk_size,
        checkpoint_interval=checkpoint_interval,
        current_chapter_ordinal=current,
        required_far_end_chapter=required_far_end_chapter(current, target),
        atlas_id=atlas_id,
        atlas_version=atlas_version,
        atlas_hash=atlas_hash,
        horizon_hash=horizon_hash,
        source_manifest_sha256=source_manifest_sha256,
        effective_content_sha256=effective_content_sha256,
        registry_hash=registry_hash,
        config_hash=config_hash,
        author_directives_hash=author_directives_hash,
        metric_bundle_hash=metric_bundle_hash,
        chunks=chunks,
    )


def create_batch(
    database: Database,
    book_id: str,
    *,
    target_chapter_count: int,
    edition_id: str | None = None,
    atlas_id: str | None = None,
    chunk_size: int = 5,
    checkpoint_interval: int = 10,
) -> dict[str, Any]:
    if target_chapter_count <= 0:
        raise BatchError("Batch 目标章节数必须大于 0")
    if chunk_size <= 0 or checkpoint_interval <= 0:
        raise BatchError("chunk_size/checkpoint_interval 必须大于 0")
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    base_event_seq, base_hash, current, effective_content_hash = _anchor(
        database, book_id, selected
    )
    atlas_row = latest_atlas(database, book_id, selected)
    if atlas_id is not None:
        with database.connect() as connection:
            atlas_row = connection.execute(
                "SELECT * FROM story_atlases WHERE atlas_id=? AND book_id=? "
                "AND edition_id=? AND status='ACTIVE'",
                (atlas_id, book_id, selected),
            ).fetchone()
        atlas_row = None if atlas_row is None else dict(atlas_row)
    if atlas_row is None:
        raise BatchError("Batch 必须绑定当前 edition 的 ACTIVE Story Atlas")
    selected_atlas = str(atlas_row["atlas_id"])
    try:
        overview = get_atlas_overview(
            database,
            book_id,
            selected,
            atlas_id=selected_atlas,
        )
    except AtlasError as exc:
        raise BatchError(f"无法验证 Batch 使用的 Atlas：{exc}") from exc
    if overview.get("errors"):
        raise BatchError("Batch 不能使用校验失败的 Atlas")
    if str(overview.get("readiness", {}).get("status")) == "BLOCKED":
        raise BatchError("BLOCKED Atlas 不能启动 Batch")
    far_end = int(overview.get("manifest", {}).get("far_horizon_end_chapter", 0))
    if far_end < required_far_end_chapter(current, target_chapter_count):
        raise BatchError("Atlas FAR horizon 未覆盖当前 Batch 目标，请先 refresh Atlas")
    horizon = overview.get("rolling_horizon")
    if not isinstance(horizon, dict) or not horizon.get("horizon_id"):
        raise BatchError("Batch 必须冻结带 horizon_id/hash 的 Rolling Horizon")
    atlas_hash = str(atlas_row.get("atlas_content_hash") or "")
    if not atlas_hash:
        atlas_hash = str(atlas_row.get("artifact_manifest_sha256") or "")
    horizon_hash = str(atlas_row.get("horizon_hash") or horizon.get("horizon_hash") or "")
    if not horizon_hash:
        raise BatchError("Rolling Horizon 缺少 horizon_hash")
    source_manifest_path = authority_path(_workspace(database, book_id))
    source_manifest_hash = (
        manifest_hash(source_manifest_path) if source_manifest_path.is_file() else ""
    )
    registry_hash = load_registry().registry_hash
    config_hash = _config_hash()
    directives_hash = _author_directives_hash(database, book_id, selected)
    metric_bundle_hash = _metric_bundle_hash(database, book_id, selected)
    batch_id = stable_id("batch", book_id, selected, str(target_chapter_count), utc_now())
    state = {
        "current_chapter_ordinal": current,
        "canon_projection_hash": base_hash,
        "atlas_id": selected_atlas,
        "atlas_version": int(atlas_row["atlas_version"]),
        "atlas_hash": atlas_hash,
        "horizon_hash": horizon_hash,
        "source_manifest_sha256": source_manifest_hash,
        "effective_content_sha256": effective_content_hash,
        "registry_hash": registry_hash,
        "config_hash": config_hash,
        "author_directives_hash": directives_hash,
        "metric_bundle_hash": metric_bundle_hash,
        "provisional_events": [],
        "provisional_facts": [],
        "provisional_threads": [],
        "atlas_candidate_changes": [],
        "unresolved_questions": [],
        "canon_committed": False,
        "canon_commit_id": None,
        "last_checkpoint_ordinal": current,
    }
    current_hash = _state_hash(state)
    plan = _batch_plan(
        batch_id,
        book_id,
        selected,
        current,
        target_chapter_count,
        chunk_size,
        checkpoint_interval,
        current_hash,
        selected_atlas,
        int(atlas_row["atlas_version"]),
        atlas_hash,
        horizon_hash,
        source_manifest_hash,
        effective_content_hash,
        registry_hash,
        config_hash,
        directives_hash,
        metric_bundle_hash,
    )
    root = _batch_root(database, book_id, selected, batch_id)
    root.mkdir(parents=True, exist_ok=False)
    (root / "batch_plan.json").write_text(
        json_dumps(plan.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO batch_working_projections(
                batch_id, book_id, edition_id, atlas_id, base_event_seq,
                atlas_version, atlas_hash, horizon_hash, base_projection_hash,
                source_manifest_sha256, input_effective_content_sha256,
                registry_hash, config_hash, author_directives_hash, metric_bundle_hash,
                current_projection_hash, current_chapter_ordinal,
                target_chapter_count, chunk_size, checkpoint_interval, status,
                state_json, created_at, updated_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                batch_id,
                book_id,
                selected,
                selected_atlas,
                base_event_seq,
                int(atlas_row["atlas_version"]),
                atlas_hash,
                horizon_hash,
                base_hash,
                source_manifest_hash,
                effective_content_hash,
                registry_hash,
                config_hash,
                directives_hash,
                metric_bundle_hash,
                current_hash,
                current,
                target_chapter_count,
                chunk_size,
                checkpoint_interval,
                BatchStatus.PLANNED.value,
                json_dumps(state),
                utc_now(),
                utc_now(),
            ),
        )
        for item in plan.chunks:
            connection.execute(
                """
                INSERT INTO batch_chunk_states(
                    chunk_id, batch_id, chunk_order, start_chapter_ordinal,
                    end_chapter_ordinal, input_projection_hash, output_projection_hash,
                    input_state_json, output_state_json, status, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, '', '{}', '{}', 'PLANNED', ?, 1)
                """,
                (
                    item.chunk_id,
                    batch_id,
                    item.chunk_order,
                    item.start_chapter_ordinal,
                    item.end_chapter_ordinal,
                    current_hash,
                    utc_now(),
                ),
            )
    if selected_atlas:
        atlas_usage(
            database,
            atlas_id=selected_atlas,
            book_id=book_id,
            edition_id=selected,
            usage_kind="BATCH_CREATED",
            batch_id=batch_id,
        )
    return {
        "batch_id": batch_id,
        "plan": plan.model_dump(mode="json"),
        "projection": BatchProjection(
            batch_id=batch_id,
            book_id=book_id,
            edition_id=selected,
            current_chapter_ordinal=current,
            projection_hash=current_hash,
            state=state,
            status=BatchStatus.PLANNED,
            atlas_id=selected_atlas,
            ).model_dump(mode="json"),
        "plan_path": str(root / "batch_plan.json"),
    }


def _row_projection(row: sqlite3.Row | dict[str, Any]) -> BatchProjection:
    return BatchProjection(
        batch_id=str(row["batch_id"]),
        book_id=str(row["book_id"]),
        edition_id=str(row["edition_id"]),
        current_chapter_ordinal=int(row["current_chapter_ordinal"]),
        projection_hash=str(row["current_projection_hash"]),
        state=json.loads(str(row["state_json"])),
        status=BatchStatus(str(row["status"])),
        atlas_id=None if row["atlas_id"] is None else str(row["atlas_id"]),
        atlas_version=None if row["atlas_version"] is None else int(row["atlas_version"]),
        atlas_hash=str(row["atlas_hash"] or ""),
        horizon_hash=str(row["horizon_hash"] or ""),
    )


def get_batch_projection(database: Database, batch_id: str) -> BatchProjection:
    database.initialize()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM batch_working_projections WHERE batch_id=?", (batch_id,)
        ).fetchone()
    if row is None:
        raise BatchError(f"未知 batch_id：{batch_id}")
    return _row_projection(_mark_batch_stale_if_needed(database, batch_id, row))


def get_batch_plan(database: Database, batch_id: str) -> BatchPlan:
    projection = get_batch_projection(database, batch_id)
    path = (
        _batch_root(database, projection.book_id, projection.edition_id, batch_id)
        / "batch_plan.json"
    )
    if not path.is_file():
        raise BatchError("Batch plan 文件不存在")
    return BatchPlan.model_validate(json.loads(path.read_text(encoding="utf-8")))


def get_chunk_context(database: Database, batch_id: str, chunk_order: int) -> dict[str, Any]:
    projection = get_batch_projection(database, batch_id)
    _ensure_batch_continuable(projection)
    plan = get_batch_plan(database, batch_id)
    chunk = next((item for item in plan.chunks if item.chunk_order == chunk_order), None)
    if chunk is None:
        raise BatchError(f"不存在 chunk_order={chunk_order}")
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM batch_chunk_states WHERE batch_id=? AND chunk_order=?",
            (batch_id, chunk_order),
        ).fetchone()
    if row is None:
        raise BatchError("Batch chunk state 不存在")
    if (
        str(row["status"]) == "PLANNED"
        and str(row["input_projection_hash"]) != projection.projection_hash
    ):
        raise BatchError("chunk 的输入 projection 已漂移")
    return {
        "batch_id": batch_id,
        "chunk": chunk.model_dump(mode="json"),
        "batch_projection": projection.model_dump(mode="json"),
        "chunk_state": dict(row),
        "must_read_previous_provisional": chunk_order > 1,
    }


def complete_chunk(
    database: Database,
    batch_id: str,
    chunk_order: int,
    *,
    provisional_state: dict[str, Any],
    validator_summary: dict[str, Any] | None = None,
    atlas_refresh_required: bool = False,
) -> dict[str, Any]:
    projection = get_batch_projection(database, batch_id)
    _ensure_batch_continuable(projection)
    plan = get_batch_plan(database, batch_id)
    chunk = next((item for item in plan.chunks if item.chunk_order == chunk_order), None)
    if chunk is None:
        raise BatchError(f"不存在 chunk_order={chunk_order}")
    try:
        state_model = BatchProvisionalState.model_validate(provisional_state)
        summary_model = BatchValidationSummary.model_validate(validator_summary or {})
        summary_model.validate_range(chunk.chapter_ordinals)
    except ValidationError as exc:
        raise BatchError(f"Batch chunk 合同无效：{exc}") from exc
    if state_model.current_chapter_ordinal > chunk.end_chapter_ordinal:
        raise BatchError("provisional state 不能越过当前 chunk 的章节范围")
    state_payload = state_model.model_dump(mode="json")
    state_payload["current_chapter_ordinal"] = chunk.end_chapter_ordinal
    state_model = BatchProvisionalState.model_validate(state_payload)
    summary_payload = summary_model.model_dump(mode="json")
    boundary_hash = _state_hash(
        {str(item.chapter_ordinal): item.boundary_hash for item in summary_model.chapters}
    )
    contract_ids = [item.contract_id for item in summary_model.chapters]
    validation_report_ids = [
        report_id
        for item in summary_model.chapters
        for report_id in item.validation_report_ids
    ]
    output_state = state_model.model_dump(mode="json")
    output_hash = _state_hash(output_state)
    checkpoint_due = False
    previous_checkpoint_ordinal = plan.current_chapter_ordinal
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM batch_chunk_states WHERE batch_id=? AND chunk_order=?",
            (batch_id, chunk_order),
        ).fetchone()
        if row is None:
            raise BatchError("Batch chunk state 不存在")
        if str(row["status"]) != "PLANNED":
            raise BatchError("Batch chunk 只能完成一次，已完成或失败的 chunk 不可覆盖")
        if chunk_order > 1:
            previous = connection.execute(
                "SELECT status FROM batch_chunk_states WHERE batch_id=? AND chunk_order=?",
                (batch_id, chunk_order - 1),
            ).fetchone()
            if previous is None or str(previous["status"]) != "COMPLETED":
                raise BatchError("必须先完成前一个 chunk，才能读取并推进 provisional state")
        expected_input = projection.projection_hash
        if str(row["input_projection_hash"]) != expected_input:
            raise BatchError("chunk input projection hash 与当前 provisional state 不一致")
        now = utc_now()
        connection.execute(
            """
            UPDATE batch_chunk_states SET output_projection_hash=?, provisional_state_hash=?,
                boundary_hash=?, contract_ids_json=?, validation_report_ids_json=?,
                output_state_json=?, validator_summary_json=?, atlas_refresh_required=?,
                failure_reason=NULL, status='COMPLETED', completed_at=?, version=version+1
            WHERE batch_id=? AND chunk_order=?
            """,
            (
                output_hash,
                output_hash,
                boundary_hash,
                json_dumps(contract_ids),
                json_dumps(validation_report_ids),
                json_dumps(output_state),
                json_dumps(summary_payload),
                int(atlas_refresh_required),
                now,
                batch_id,
                chunk_order,
            ),
        )
        remaining = connection.execute(
            "SELECT COUNT(*) FROM batch_chunk_states WHERE batch_id=? AND status!='COMPLETED'",
            (batch_id,),
        ).fetchone()
        status = (
            BatchStatus.BATCH_VALIDATED.value
            if int(remaining[0]) == 0
            else BatchStatus.RUNNING.value
        )
        connection.execute(
            "UPDATE batch_working_projections SET current_projection_hash=?, "
            "current_chapter_ordinal=?, state_json=?, status=?, updated_at=?, version=version+1 "
            "WHERE batch_id=?",
            (
                output_hash,
                chunk.end_chapter_ordinal,
                json_dumps(output_state),
                status,
                now,
                batch_id,
            ),
        )
        connection.execute(
            "UPDATE batch_chunk_states SET input_projection_hash=?, input_state_json=? "
            "WHERE batch_id=? AND chunk_order=? AND status='PLANNED'",
            (output_hash, json_dumps(output_state), batch_id, chunk_order + 1),
        )
        last_checkpoint = connection.execute(
            "SELECT MAX(chapter_ordinal) FROM batch_checkpoints WHERE batch_id=?",
            (batch_id,),
        ).fetchone()
        if last_checkpoint is not None and last_checkpoint[0] is not None:
            previous_checkpoint_ordinal = int(last_checkpoint[0])
        completed_target = chunk.end_chapter_ordinal - plan.current_chapter_ordinal
        checkpoint_due = (
            completed_target >= plan.checkpoint_interval
            and chunk.end_chapter_ordinal // plan.checkpoint_interval
            > previous_checkpoint_ordinal // plan.checkpoint_interval
        )
    if checkpoint_due:
        create_checkpoint(
            database,
            batch_id,
            report={"reason": "automatic_interval", "chunk_order": chunk_order},
        )
    return get_chunk_context(database, batch_id, chunk_order)


def create_checkpoint(
    database: Database,
    batch_id: str,
    *,
    report: dict[str, Any] | None = None,
    atlas_version: int | None = None,
    rhythm_snapshot_id: str | None = None,
) -> dict[str, Any]:
    projection = get_batch_projection(database, batch_id)
    _ensure_batch_continuable(projection)
    plan = get_batch_plan(database, batch_id)
    atlas_row = latest_atlas(database, projection.book_id, projection.edition_id)
    if atlas_row is None:
        raise BatchError("Checkpoint 不能在没有 ACTIVE Atlas 时创建")
    atlas_overview = get_atlas_overview(
        database,
        projection.book_id,
        projection.edition_id,
        atlas_id=str(atlas_row["atlas_id"]),
    )
    if atlas_overview.get("errors"):
        raise BatchError("Checkpoint 不能绑定校验失败的 Atlas")
    horizon = atlas_overview.get("rolling_horizon")
    if not isinstance(horizon, dict):
        raise BatchError("Checkpoint 缺少 Rolling Horizon")
    selected_atlas_version = int(atlas_row["atlas_version"])
    if atlas_version is not None and atlas_version != selected_atlas_version:
        raise BatchError("Checkpoint 请求的 Atlas version 已不是当前 ACTIVE 版本")
    atlas_hash = str(atlas_row.get("atlas_content_hash") or "")
    horizon_hash = str(atlas_row.get("horizon_hash") or horizon.get("horizon_hash") or "")
    checkpoint_state = dict(projection.state)
    checkpoint_state.update(
        {
            "atlas_id": str(atlas_row["atlas_id"]),
            "atlas_version": selected_atlas_version,
            "atlas_hash": atlas_hash,
            "horizon_hash": horizon_hash,
            "last_checkpoint_ordinal": projection.current_chapter_ordinal,
        }
    )
    checkpoint_status = (
        BatchStatus.BATCH_VALIDATED.value
        if projection.status is BatchStatus.BATCH_VALIDATED
        else BatchStatus.CHECKPOINT.value
    )
    checkpoint_report = dict(report or {})
    checkpoint_report.update(
        {
            "atlas_id": str(atlas_row["atlas_id"]),
            "atlas_version": selected_atlas_version,
            "atlas_hash": atlas_hash,
            "horizon_hash": horizon_hash,
        }
    )
    with database.connect() as connection:
        row = connection.execute(
            "SELECT checkpoint_interval FROM batch_working_projections WHERE batch_id=?",
            (batch_id,),
        ).fetchone()
        if row is None:
            raise BatchError(f"未知 batch_id：{batch_id}")
        interval = int(row["checkpoint_interval"])
        checkpoint_id = stable_id(
            "batch-checkpoint", batch_id, str(projection.current_chapter_ordinal)
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO batch_checkpoints(
                checkpoint_id, batch_id, chapter_ordinal, projection_hash,
                atlas_version, atlas_hash, horizon_hash, rhythm_snapshot_id,
                report_json, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                checkpoint_id,
                batch_id,
                projection.current_chapter_ordinal,
                projection.projection_hash,
                selected_atlas_version,
                atlas_hash,
                horizon_hash,
                rhythm_snapshot_id,
                json_dumps({"checkpoint_interval": interval, **checkpoint_report}),
                utc_now(),
            ),
        )
        connection.execute(
            "UPDATE batch_working_projections SET atlas_id=?, atlas_version=?, atlas_hash=?, "
            "horizon_hash=?, state_json=?, status=?, updated_at=?, version=version+1 "
            "WHERE batch_id=?",
            (
                str(atlas_row["atlas_id"]),
                selected_atlas_version,
                atlas_hash,
                horizon_hash,
                json_dumps(checkpoint_state),
                checkpoint_status,
                utc_now(),
                batch_id,
            ),
        )
    atlas_usage(
        database,
        atlas_id=str(atlas_row["atlas_id"]),
        book_id=projection.book_id,
        edition_id=projection.edition_id,
        usage_kind="BATCH_CHECKPOINT",
        batch_id=batch_id,
    )
    updated_projection = get_batch_projection(database, batch_id)
    return {
        "checkpoint_id": checkpoint_id,
        "batch_id": batch_id,
        "plan_checkpoint_interval": plan.checkpoint_interval,
        **updated_projection.model_dump(mode="json"),
    }
