from __future__ import annotations

import json
import secrets
import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_authoring.atlas.service import atlas_usage, latest_atlas, validate_atlas
from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.ingest.service import verify_sources
from novel_authoring.metrics.registry import load_registry
from novel_authoring.metrics.service import MetricsAssembler
from novel_authoring.planning.aggregates import build_planning_aggregate
from novel_authoring.planning.batch import get_batch_plan, get_batch_projection
from novel_authoring.utils import json_dumps, sha256_bytes, sha256_file, stable_id, utc_now


class HandoffStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_CODEX = "READY_FOR_CODEX"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STALE = "STALE"
    CANCELLED = "CANCELLED"


class HandoffType(StrEnum):
    CONTINUATION = "CONTINUATION"
    REVISION = "REVISION"
    METRIC_SEMANTIC_ANALYSIS = "METRIC_SEMANTIC_ANALYSIS"
    CHAPTER_FEATURE_ANALYSIS = "CHAPTER_FEATURE_ANALYSIS"
    STORY_ATLAS_BOOTSTRAP = "STORY_ATLAS_BOOTSTRAP"
    STORY_ATLAS_REFRESH = "STORY_ATLAS_REFRESH"
    WORLD_MODEL_REVIEW = "WORLD_MODEL_REVIEW"
    STORY_ATLAS_RENDER = "STORY_ATLAS_RENDER"
    BATCH_CONTINUATION = "BATCH_CONTINUATION"
    NOVEL_INITIALIZATION = "NOVEL_INITIALIZATION"


class HandoffWorkflowError(RuntimeError):
    status_code = 409


class WorkflowHandoffResult(BaseModel):
    """Strict result contract shared by Codex desktop, Web and CLI."""

    model_config = ConfigDict(extra="forbid")

    handoff_id: str
    handoff_type: str
    requested_stage: str
    completed_stage: str
    book_id: str
    edition_id: str
    status: str
    task_ids: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    contract_id: str | None = None
    draft_id: str | None = None
    campaign_id: str | None = None
    revision_unit_ids: list[str] = Field(default_factory=list)
    artifact_paths: list[str] = Field(default_factory=list)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    next_action: str = ""
    canon_committed: Literal[False] = False
    edition_activated: Literal[False] = False
    base_event_seq: int
    base_projection_hash: str
    metric_run_ids: list[str] = Field(default_factory=list)
    metric_bundle_hash: str | None = None
    atlas_id: str | None = None
    atlas_version: int | None = None
    atlas_manifest_hash: str | None = None
    horizon_hash: str | None = None
    readiness_status: str | None = None
    batch_id: str | None = None
    batch_plan_hash: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    review_queue_ids: list[str] = Field(default_factory=list)
    atlas_refresh_required: bool = False
    completed_at: str | None = None
    initialization_id: str | None = None
    completed_arc_ids: list[str] = Field(default_factory=list)
    failed_arc_ids: list[str] = Field(default_factory=list)
    chapter_coverage: float | None = None
    arc_coverage: float | None = None
    entity_count: int = 0
    relationship_count: int = 0
    faction_count: int = 0
    ability_count: int = 0
    resource_count: int = 0
    region_count: int = 0
    thread_count: int = 0
    metric_observation_count: int = 0
    generated_visuals: list[str] = Field(default_factory=list)
    readiness: str | None = None
    review_queue: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_stage_contract(self) -> WorkflowHandoffResult:
        requested = self.requested_stage.upper()
        completed = self.completed_stage.upper()
        if requested == "PLAN_ONLY" and not self.candidate_ids:
            raise ValueError("PLAN_ONLY 完成结果必须包含 candidate_ids")
        if requested == "DRAFT_AND_VALIDATE" and not self.draft_id:
            raise ValueError("DRAFT_AND_VALIDATE 完成结果必须包含 draft_id")
        if requested == "IMPACT_AND_PLAN":
            if not self.campaign_id:
                raise ValueError("IMPACT_AND_PLAN 完成结果必须包含 campaign_id")
            if not self.artifact_paths:
                raise ValueError("IMPACT_AND_PLAN 完成结果必须包含 artifact_paths")
        atlas_type = self.handoff_type.upper()
        if atlas_type in {
            HandoffType.STORY_ATLAS_BOOTSTRAP.value,
            HandoffType.STORY_ATLAS_REFRESH.value,
            HandoffType.STORY_ATLAS_RENDER.value,
        } and not self.artifact_paths:
            raise ValueError(f"{atlas_type} 完成结果必须包含 Atlas artifact_paths")
        if atlas_type == HandoffType.BATCH_CONTINUATION.value and not self.batch_id:
            raise ValueError("BATCH_CONTINUATION 完成结果必须包含 batch_id")
        if atlas_type == HandoffType.BATCH_CONTINUATION.value and not self.chunk_ids:
            raise ValueError("BATCH_CONTINUATION 完成结果必须包含 chunk_ids")
        if atlas_type == HandoffType.WORLD_MODEL_REVIEW.value and not self.review_queue_ids:
            raise ValueError("WORLD_MODEL_REVIEW 完成结果必须包含 review_queue_ids")
        if atlas_type == HandoffType.NOVEL_INITIALIZATION.value and not self.initialization_id:
            raise ValueError("NOVEL_INITIALIZATION 完成结果必须包含 initialization_id")
        compatible = {
            "PLAN_ONLY": {"PLAN_ONLY", "PLANNED", "CANDIDATES"},
            "DRAFT_AND_VALIDATE": {"DRAFT_AND_VALIDATE", "VALIDATED_DRAFT", "VALIDATED"},
            "IMPACT_AND_PLAN": {"IMPACT_AND_PLAN", "IMPACTED", "PLANNED", "VALIDATED_CAMPAIGN"},
            "DRAFT_SELECTED_UNITS": {"DRAFT_SELECTED_UNITS", "VALIDATED_CAMPAIGN", "VALIDATED"},
            "ATLAS_BOOTSTRAP": {"ATLAS_BOOTSTRAP", "STORY_ATLAS_READY", "VALIDATED_ATLAS"},
            "ATLAS_REFRESH": {"ATLAS_REFRESH", "STORY_ATLAS_READY", "VALIDATED_ATLAS"},
            "WORLD_MODEL_REVIEW": {"WORLD_MODEL_REVIEW", "REVIEWED", "VALIDATED_ATLAS"},
            "BATCH_CONTINUATION": {"BATCH_CONTINUATION", "BATCH_VALIDATED", "VALIDATED"},
            "NOVEL_INITIALIZATION": {
                "NOVEL_INITIALIZATION",
                "INITIALIZATION_READY",
                "WORLD_MODEL_READY",
                "WORLD_MODEL_READY_WITH_GAPS",
                "VALIDATED_INITIALIZATION",
            },
        }
        if requested in compatible and completed not in compatible[requested]:
            raise ValueError(f"requested_stage={requested} 与 completed_stage={completed} 不兼容")
        return self


class WaitingForUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    question: str
    reason: str
    options: list[Any] = Field(default_factory=list)
    related_artifacts: list[str] = Field(default_factory=list)
    required_author_decision: str


_ALLOWED_TRANSITIONS: dict[HandoffStatus, set[HandoffStatus]] = {
    HandoffStatus.READY_FOR_CODEX: {
        HandoffStatus.CLAIMED,
        HandoffStatus.CANCELLED,
        HandoffStatus.STALE,
    },
    HandoffStatus.CLAIMED: {HandoffStatus.RUNNING, HandoffStatus.FAILED, HandoffStatus.CANCELLED},
    HandoffStatus.RUNNING: {
        HandoffStatus.WAITING_FOR_USER,
        HandoffStatus.COMPLETED,
        HandoffStatus.FAILED,
        HandoffStatus.STALE,
    },
    HandoffStatus.WAITING_FOR_USER: {HandoffStatus.RUNNING, HandoffStatus.CANCELLED},
}


def _book_workspace(database: Database, book_id: str) -> Path:
    row = database.scalar("SELECT workspace_root FROM books WHERE book_id=?", (book_id,))
    if row is None:
        raise HandoffWorkflowError(f"未知 book_id：{book_id}")
    return Path(str(row))


def _manifest_hash(database: Database, book_id: str) -> str:
    root = _book_workspace(database, book_id)
    path = root / "source_manifest.json"
    return sha256_file(path) if path.is_file() else ""


_OPERATION_INPUT_FILES = {
    "task.json",
    "prompt.md",
    "metric_context.json",
    "context_manifest.json",
    "output_schema.json",
}


def _handoff_file(task_directory: Path, name: str) -> Path:
    """Resolve a handoff file across canonical and legacy operation layouts."""

    if (task_directory / "input").is_dir() and (task_directory / "output").is_dir():
        if name in _OPERATION_INPUT_FILES:
            return task_directory / "input" / name
        if name == "result.json":
            return task_directory / "output" / name
    return task_directory / name


def _author_directives_hash(
    connection: sqlite3.Connection, book_id: str, edition_id: str
) -> str:
    rows = connection.execute(
        "SELECT directive_id, directive_type, content, mode, status, priority "
        "FROM author_directives WHERE book_id=? AND edition_id=? "
        "ORDER BY priority DESC, created_at, directive_id",
        (book_id, edition_id),
    ).fetchall()
    return sha256_bytes(json_dumps([dict(row) for row in rows]).encode("utf-8"))


def _next_sequence(connection: sqlite3.Connection, handoff_id: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(sequence), 0) + 1 FROM workflow_handoff_events WHERE handoff_id=?",
        (handoff_id,),
    ).fetchone()
    return int(row[0])


def append_event(
    database: Database,
    handoff_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    claim_token: str | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM workflow_handoffs WHERE handoff_id=?", (handoff_id,)
        ).fetchone()
        if row is None:
            raise HandoffWorkflowError(f"handoff 不存在：{handoff_id}")
        if claim_token is not None and str(row["claim_token"] or "") != claim_token:
            raise HandoffWorkflowError("claim_token 无效")
        sequence = _next_sequence(connection, handoff_id)
        event = {
            "event_id": stable_id("handoff-event", handoff_id, str(sequence), event_type),
            "handoff_id": handoff_id,
            "sequence": sequence,
            "event_type": event_type,
            "payload": payload,
            "created_at": utc_now(),
        }
        connection.execute(
            "INSERT INTO workflow_handoff_events(event_id, handoff_id, sequence, "
            "event_type, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event["event_id"],
                handoff_id,
                sequence,
                event_type,
                json_dumps(payload),
                event["created_at"],
            ),
        )
        task_directory = Path(str(row["task_directory"]))
        task_directory.mkdir(parents=True, exist_ok=True)
        with (task_directory / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json_dumps(event) + "\n")
        return event


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8")


def _current_metric_anchor(
    database: Database, book_id: str, edition_id: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    assembler = MetricsAssembler(database)
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, edition_id)
        if not chapters:
            raise HandoffWorkflowError("没有可用章节，无法冻结 handoff")
        scope_id = str(chapters[-1]["chapter_id"])
        bundle = assembler.assemble(
            book_id, edition_id=edition_id, scope_type="CHAPTER", scope_id=scope_id
        )
    latest = assembler.latest(book_id, edition_id, "CHAPTER", scope_id)
    metric_context = bundle.model_dump(mode="json")
    metric_context["input_bundle_hash"] = bundle.input_bundle_hash
    return metric_context, latest


def create_handoff(
    database: Database,
    book_id: str,
    *,
    handoff_type: HandoffType,
    requested_stage: str,
    edition_id: str | None = None,
    metric_run_id: str | None = None,
    require_complete_metrics: bool = False,
    atlas_id: str | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    workspace_root = _book_workspace(database, book_id)
    verification = verify_sources(book_id, workspace_root.parent)
    if not bool(verification.get("ok")):
        raise HandoffWorkflowError("source verify 失败，不能创建 handoff")
    with database.connect() as connection:
        projection = projection_from_connection(connection, book_id, selected)
        edition_row = connection.execute(
            "SELECT status FROM editions WHERE book_id=? AND edition_id=?",
            (book_id, selected),
        ).fetchone()
        directives_hash = _author_directives_hash(connection, book_id, selected)
    edition_status = None if edition_row is None else str(edition_row["status"])
    initialization_handoff = handoff_type is HandoffType.NOVEL_INITIALIZATION
    if initialization_handoff:
        # Existing-novel initialization is the upstream producer of the Atlas.
        # It must not require a planning aggregate or a completed metric run.
        metric_context = {
            "scope_type": "INITIALIZATION",
            "scope_id": selected,
            "input_bundle_hash": "",
            "semantic_metrics_deferred": True,
        }
        latest = None
        planning_aggregate = {"aggregate_id": None, "bundle_hash": None}
    else:
        metric_context, latest = _current_metric_anchor(database, book_id, selected)
        planning_aggregate = build_planning_aggregate(
            database,
            book_id,
            edition_id=selected,
            author_policy={"source": "handoff-freeze", "policy_version": "v1"},
        )
    if metric_run_id is None and latest is not None:
        metric_run_id = str(latest["run"]["run_id"])
    if metric_run_id is None:
        if require_complete_metrics:
            raise HandoffWorkflowError("没有可用 Metric Run")
    elif latest is not None and str(latest["run"]["run_id"]) == metric_run_id:
        if require_complete_metrics and str(latest["run"]["status"]) != "COMPLETE":
            raise HandoffWorkflowError("当前 Metric Run 尚未 COMPLETE")
        if require_complete_metrics and any(
            item["missing_components_json"] != "[]" for item in latest["results"]
        ):
            raise HandoffWorkflowError("当前 Metric Run 仍有缺失 component")
    manifest_hash = _manifest_hash(database, book_id)
    with database.connect() as connection:
        rhythm_row = connection.execute(
            "SELECT snapshot_id FROM rhythm_diagnostic_snapshots WHERE book_id=? AND edition_id=? "
            "ORDER BY as_of_chapter DESC, created_at DESC LIMIT 1",
            (book_id, selected),
        ).fetchone()
    rhythm_snapshot_id = None if rhythm_row is None else str(rhythm_row["snapshot_id"])
    rhythm_required = handoff_type in {
        HandoffType.CONTINUATION,
        HandoffType.REVISION,
        HandoffType.BATCH_CONTINUATION,
    }
    if rhythm_snapshot_id is None and rhythm_required:
        raise HandoffWorkflowError("当前 edition 没有 Rhythm Snapshot，不能冻结 handoff")
    current_atlas = latest_atlas(database, book_id, selected)
    if atlas_id is not None:
        with database.connect() as connection:
            current_atlas = connection.execute(
                "SELECT * FROM story_atlases WHERE atlas_id=? AND book_id=? "
                "AND edition_id=?",
                (atlas_id, book_id, selected),
            ).fetchone()
        current_atlas = None if current_atlas is None else dict(current_atlas)
    if handoff_type is HandoffType.BATCH_CONTINUATION:
        if not batch_id:
            raise HandoffWorkflowError("BATCH_CONTINUATION handoff 必须绑定 batch_id")
        try:
            batch_projection = get_batch_projection(database, batch_id)
            batch_plan = get_batch_plan(database, batch_id)
        except (OSError, ValueError, RuntimeError) as exc:
            raise HandoffWorkflowError(f"Batch handoff 无法读取 batch_id：{exc}") from exc
        if batch_projection.book_id != book_id or batch_projection.edition_id != selected:
            raise HandoffWorkflowError("batch_id 不属于当前 book/edition")
        if current_atlas is None or str(current_atlas["atlas_id"]) != str(
            batch_projection.atlas_id
        ):
            raise HandoffWorkflowError("Batch handoff 的 Atlas 必须与 Batch 冻结锚点一致")
        batch_plan_path = (
            workspace_root
            / "editions"
            / selected
            / "batches"
            / batch_id
            / "batch_plan.json"
        )
        if not batch_plan_path.is_file():
            raise HandoffWorkflowError("Batch plan 文件不存在")
        batch_plan_hash = sha256_file(batch_plan_path)
    else:
        batch_projection = None
        batch_plan = None
        batch_plan_hash = None
    atlas_version = None if current_atlas is None else int(current_atlas["atlas_version"])
    atlas_manifest_hash = (
        None
        if current_atlas is None
        else str(current_atlas["artifact_manifest_sha256"] or "")
    )
    horizon_hash = None if current_atlas is None else str(current_atlas["horizon_hash"] or "")
    readiness_status = None if current_atlas is None else str(current_atlas["readiness_status"])
    handoff_id = stable_id(
        "handoff", book_id, selected, handoff_type.value, requested_stage, utc_now()
    )
    canonical_layout = (workspace_root / "book.yaml").is_file()
    if canonical_layout:
        task_directory = workspace_root / "editions" / selected / "operations" / handoff_id
        input_directory = task_directory / "input"
        output_directory = task_directory / "output"
        artifacts = task_directory / "artifacts"
        logs_directory = task_directory / "logs"
        for directory in (
            task_directory,
            input_directory,
            output_directory,
            artifacts,
            logs_directory,
        ):
            directory.mkdir(parents=True, exist_ok=False)
    else:
        task_directory = workspace_root / "editions" / selected / "handoffs" / handoff_id
        input_directory = task_directory
        output_directory = task_directory
        artifacts = task_directory / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=False)
    artifacts = task_directory / "artifacts"
    atlas_output_directory = artifacts / "story_atlas"
    task = {
        "handoff_id": handoff_id,
        "task_type": handoff_type.value,
        "requested_stage": requested_stage,
        "book_id": book_id,
        "edition_id": selected,
        "created_at": utc_now(),
        "base_event_seq": projection.through_event_seq,
        "base_projection_hash": projection.sha256(),
        "source_manifest_sha256": manifest_hash,
        "metric_run_id": metric_run_id,
        "metric_bundle_hash": metric_context.get("input_bundle_hash"),
        "planning_aggregate_id": planning_aggregate["aggregate_id"],
        "planning_aggregate_hash": planning_aggregate["bundle_hash"],
        "effective_content_sha256": metric_context.get("effective_content_sha256"),
        "rhythm_snapshot_id": rhythm_snapshot_id,
        "registry_hash": metric_context.get("registry_hash", ""),
        "config_hash": metric_context.get("config_hash", ""),
        "author_directives_hash": directives_hash,
        "current_atlas_id": None if current_atlas is None else current_atlas["atlas_id"],
        "current_atlas_version": atlas_version,
        "current_atlas_manifest_hash": atlas_manifest_hash,
        "current_horizon_hash": horizon_hash,
        "readiness_status": readiness_status,
        "batch_id": batch_id,
        "batch_plan_hash": batch_plan_hash,
        "atlas_output_directory": str(atlas_output_directory),
        "atlas_required_artifacts": [
            "atlas_manifest.json",
            "narrative_dna.md",
            "current_world_model.md",
            "world_rules.yaml",
            "unresolved_assumptions.yaml",
            "expansion_grammar.yaml",
            "graphs/*.json",
            "future/*.yaml",
            "reports/*.md",
        ],
        "allowed_paths": [str(artifacts.resolve()), str(task_directory.resolve())],
        "forbidden_actions": [
            "不得修改book",
            "不得批准正史",
            "不得批准改写Campaign",
            "不得启用Edition",
            "不得删除历史草稿",
            "不得绕过Validator",
            "不得把 Story Atlas 的 INFERENCE/CANDIDATE/SPECULATIVE 内容写入 Canon",
            "不得把 FAR Horizon 写成逐章固定大纲",
        ],
        "expected_outputs": ["events.jsonl", "result.json", "status.json"],
        "task_schema_version": "handoff-v1",
    }
    if initialization_handoff:
        task.update(
            {
                "initialization_contract": {
                    "root": str(
                        workspace_root
                        / "editions"
                        / selected
                        / ("analysis" if canonical_layout else "")
                        / "initialization"
                    ),
                    "required_files": [
                        "initialization_manifest.json",
                        "source_coverage.json",
                        "arc_manifest.json",
                        "status.json",
                        "events.jsonl",
                        "arc_tasks/",
                        "arc_outputs/",
                        "entity_resolution/",
                        "synthesis/",
                        "metrics/",
                        "visuals/",
                        "reports/",
                    ],
                    "pipeline": [
                        "Source Coverage",
                        "Arc Segmentation",
                        "Arc Extraction",
                        "Entity Resolution",
                        "Cross-Arc Synthesis",
                        "Contradiction Audit",
                        "Narrative DNA",
                        "Current Story Atlas",
                        "Future Possibility Space",
                        "Semantic Metric Bootstrap",
                        "Visual Asset Rendering",
                    ],
                },
                "planning_aggregate_required": False,
            }
        )
    if batch_projection is not None and batch_plan is not None:
        task["batch_target_chapter_count"] = batch_plan.target_chapter_count
        task["batch_current_chapter_ordinal"] = batch_projection.current_chapter_ordinal
        task["batch_status"] = batch_projection.status.value
    skill_name = {
        HandoffType.CONTINUATION: "continue-novel",
        HandoffType.REVISION: "revise-novel",
        HandoffType.METRIC_SEMANTIC_ANALYSIS: "review-novel-metrics",
        HandoffType.CHAPTER_FEATURE_ANALYSIS: "analyze-novel-rhythm",
        HandoffType.STORY_ATLAS_BOOTSTRAP: "bootstrap-story-atlas",
        HandoffType.STORY_ATLAS_REFRESH: "refresh-story-atlas",
        HandoffType.WORLD_MODEL_REVIEW: "review-story-atlas",
        HandoffType.STORY_ATLAS_RENDER: "render-story-atlas-assets",
        HandoffType.BATCH_CONTINUATION: "continue-novel-batch",
        HandoffType.NOVEL_INITIALIZATION: "initialize-existing-novel",
    }.get(handoff_type, "continue-novel")
    atlas_instruction = ""
    if handoff_type in {
        HandoffType.STORY_ATLAS_BOOTSTRAP,
        HandoffType.STORY_ATLAS_REFRESH,
        HandoffType.WORLD_MODEL_REVIEW,
        HandoffType.STORY_ATLAS_RENDER,
    }:
        atlas_instruction = (
            "Atlas 输出必须先写入 task artifacts/story_atlas，再由 Python 校验并登记；"
            "不得直接修改 Canon。"
        )
    elif handoff_type is HandoffType.BATCH_CONTINUATION:
        atlas_instruction = (
            "Batch 必须按 chunk_size=5 滚动执行、每章更新 Batch Provisional Projection；"
            "每10章进入 checkpoint，最终停在 BATCH_VALIDATED，不得自动批准正史。"
        )
    elif handoff_type is HandoffType.NOVEL_INITIALIZATION:
        atlas_instruction = (
            "初始化必须先完成 Source Coverage 和 Arc task 文件合同，再由 Codex 桌面端执行 "
            "Arc Extraction、Entity Resolution、Cross-Arc Synthesis、Contradiction Audit、"
            "Narrative DNA、Atlas、语义指标和 SVG 渲染；"
            "不得依赖 Planning Aggregate，不得写入 Canon。"
        )
    prompt = (
        "$process-novel-handoff\n\n"
        "请先使用仓库内的 $process-novel-handoff Skill，领取并验证 "
        f"handoff_id={handoff_id}。\n\n"
        f"领取成功后，根据 task.json 调用 ${skill_name}，严格执行 "
        f"requested_stage={requested_stage}。\n\n"
        f"{atlas_instruction}\n\n"
        "严格读取任务目录中的 task.json、prompt.md、metric_context.json、"
        "context_manifest.json 和 output_schema.json。\n"
        "不得修改 book；不得批准写入正史；不得批准改写 Campaign；不得启用 Edition。\n"
        "结束时必须严格按 output_schema.json 写回 result.json 和 status.json；"
        "需要作者决定时写 waiting_for_user.json 并进入 WAITING_FOR_USER。"
    )
    context_manifest = {
        "book_id": book_id,
        "edition_id": selected,
        "base_projection_hash": projection.sha256(),
        "source_manifest_sha256": manifest_hash,
        "metric_bundle_hash": task["metric_bundle_hash"],
        "planning_aggregate_id": task["planning_aggregate_id"],
        "planning_aggregate_hash": task["planning_aggregate_hash"],
        "registry_hash": task["registry_hash"],
        "config_hash": task["config_hash"],
        "author_directives_hash": task["author_directives_hash"],
        "current_atlas_id": task["current_atlas_id"],
        "current_atlas_version": task["current_atlas_version"],
        "current_atlas_manifest_hash": task["current_atlas_manifest_hash"],
        "current_horizon_hash": task["current_horizon_hash"],
        "readiness_status": task["readiness_status"],
        "batch_id": task["batch_id"],
        "batch_plan_hash": task["batch_plan_hash"],
        "atlas_required_artifacts": task["atlas_required_artifacts"],
        "effective_content_sha256": task["effective_content_sha256"],
        "edition_status": edition_status,
        "frozen_at": task["created_at"],
        "paths": ["task.json", "prompt.md", "metric_context.json", "output_schema.json"],
    }
    output_schema = WorkflowHandoffResult.model_json_schema()
    output_schema["additionalProperties"] = False
    output_schema["required"] = [
        "handoff_id",
        "handoff_type",
        "requested_stage",
        "completed_stage",
        "book_id",
        "edition_id",
        "status",
        "task_ids",
        "candidate_ids",
        "selected_candidate_id",
        "contract_id",
        "draft_id",
        "campaign_id",
        "revision_unit_ids",
        "artifact_paths",
        "validation_summary",
        "warnings",
        "next_action",
        "canon_committed",
        "edition_activated",
        "base_event_seq",
        "base_projection_hash",
        "metric_run_ids",
        "metric_bundle_hash",
        "completed_at",
    ]
    output_schema["x-stage-rules"] = {
        "PLAN_ONLY": {"required_non_empty": ["candidate_ids"]},
        "DRAFT_AND_VALIDATE": {"required_non_empty": ["draft_id"]},
        "IMPACT_AND_PLAN": {
            "required_non_empty": ["campaign_id", "artifact_paths"]
        },
        "ATLAS_BOOTSTRAP": {"required_non_empty": ["artifact_paths"]},
        "ATLAS_REFRESH": {"required_non_empty": ["artifact_paths"]},
        "WORLD_MODEL_REVIEW": {"required_non_empty": ["review_queue_ids"]},
        "BATCH_CONTINUATION": {"required_non_empty": ["batch_id", "chunk_ids"]},
        "NOVEL_INITIALIZATION": {
            "required_non_empty": ["initialization_id", "completed_arc_ids", "readiness"]
        },
    }
    if initialization_handoff:
        output_schema["required"].extend(
            [
                "initialization_id",
                "completed_arc_ids",
                "failed_arc_ids",
                "chapter_coverage",
                "arc_coverage",
                "entity_count",
                "relationship_count",
                "faction_count",
                "ability_count",
                "resource_count",
                "region_count",
                "thread_count",
                "metric_observation_count",
                "generated_visuals",
                "readiness",
                "review_queue",
            ]
        )
        output_schema["x-initialization-result-fields"] = [
            "initialization_id",
            "completed_arc_ids",
            "failed_arc_ids",
            "chapter_coverage",
            "arc_coverage",
            "entity_count",
            "relationship_count",
            "faction_count",
            "ability_count",
            "resource_count",
            "region_count",
            "thread_count",
            "metric_observation_count",
            "generated_visuals",
            "atlas_id",
            "atlas_version",
            "readiness",
            "warnings",
            "review_queue",
            "canon_committed",
            "edition_activated",
        ]
    status_json = {
        "handoff_id": handoff_id,
        "status": HandoffStatus.READY_FOR_CODEX.value,
        "updated_at": task["created_at"],
    }
    input_files = {
        name: input_directory / name
        for name in (
            "task.json",
            "prompt.md",
            "metric_context.json",
            "context_manifest.json",
            "output_schema.json",
        )
    }
    status_path = task_directory / "status.json"
    result_path = output_directory / "result.json"
    event_log_path = task_directory / "events.jsonl"
    for name, value in (
        ("task.json", task),
        ("prompt.md", prompt),
        ("metric_context.json", metric_context),
        ("context_manifest.json", context_manifest),
        ("output_schema.json", output_schema),
    ):
        if isinstance(value, str):
            input_files[name].write_text(value, encoding="utf-8")
        else:
            _write_json(input_files[name], value)
    _write_json(status_path, status_json)
    _write_json(result_path, {})
    context_manifest["file_hashes"] = {
        name: sha256_file(input_files[name])
        for name in ("task.json", "prompt.md", "metric_context.json", "output_schema.json")
    }
    _write_json(input_files["context_manifest.json"], context_manifest)
    event_log_path.write_text("", encoding="utf-8")
    if canonical_layout:
        _write_json(
            task_directory / "manifest.json",
            {
                "operation_id": handoff_id,
                "operation_kind": "WORKFLOW_HANDOFF",
                "legacy_imported": False,
                "book_id": book_id,
                "edition_id": selected,
                "input": {name: str(path) for name, path in input_files.items()},
                "output": {"result": str(result_path)},
                "created_at": task["created_at"],
            },
        )
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO workflow_handoffs(
                handoff_id, book_id, edition_id, handoff_type, requested_stage, status,
                task_directory, prompt_path, task_manifest_path, output_schema_path,
                result_path, event_log_path, base_event_seq, base_projection_hash,
                source_manifest_sha256, metric_run_id, metric_bundle_hash, rhythm_snapshot_id,
                registry_hash, config_hash, effective_content_sha256, edition_status,
                planning_aggregate_id, planning_aggregate_hash,
                author_directives_hash, atlas_id, atlas_version, atlas_manifest_hash,
                horizon_hash, batch_id, batch_plan_hash, readiness_status,
                created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                handoff_id,
                book_id,
                selected,
                handoff_type.value,
                requested_stage,
                HandoffStatus.READY_FOR_CODEX.value,
                str(task_directory),
                str(input_files["prompt.md"]),
                str(input_files["task.json"]),
                str(input_files["output_schema.json"]),
                str(result_path),
                str(event_log_path),
                projection.through_event_seq,
                projection.sha256(),
                manifest_hash,
                metric_run_id,
                task["metric_bundle_hash"],
                task["rhythm_snapshot_id"],
                task["registry_hash"],
                task["config_hash"],
                task["effective_content_sha256"],
                edition_status,
                task["planning_aggregate_id"],
                task["planning_aggregate_hash"],
                task["author_directives_hash"],
                task["current_atlas_id"],
                task["current_atlas_version"],
                task["current_atlas_manifest_hash"],
                task["current_horizon_hash"],
                task["batch_id"],
                task["batch_plan_hash"],
                task["readiness_status"],
                task["created_at"],
            ),
        )
    if task["current_atlas_id"]:
        atlas_usage(
            database,
            atlas_id=str(task["current_atlas_id"]),
            book_id=book_id,
            edition_id=selected,
            usage_kind="HANDOFF_CREATED",
            batch_id=batch_id,
            handoff_id=handoff_id,
        )
    append_event(database, handoff_id, "READY_FOR_CODEX", {"requested_stage": requested_stage})
    return {
        "handoff_id": handoff_id,
        "task_directory": str(task_directory),
        "prompt": prompt,
        "status": status_json,
    }


def create_continuation_handoff(database: Database, book_id: str, **kwargs: Any) -> dict[str, Any]:
    return create_handoff(database, book_id, handoff_type=HandoffType.CONTINUATION, **kwargs)


def create_revision_handoff(database: Database, book_id: str, **kwargs: Any) -> dict[str, Any]:
    return create_handoff(database, book_id, handoff_type=HandoffType.REVISION, **kwargs)


def create_story_atlas_handoff(
    database: Database,
    book_id: str,
    *,
    handoff_type: HandoffType = HandoffType.STORY_ATLAS_BOOTSTRAP,
    **kwargs: Any,
) -> dict[str, Any]:
    if handoff_type not in {
        HandoffType.STORY_ATLAS_BOOTSTRAP,
        HandoffType.STORY_ATLAS_REFRESH,
        HandoffType.WORLD_MODEL_REVIEW,
    }:
        raise HandoffWorkflowError("create_story_atlas_handoff 的类型必须是 Story Atlas handoff")
    return create_handoff(database, book_id, handoff_type=handoff_type, **kwargs)


def create_batch_continuation_handoff(
    database: Database,
    book_id: str,
    *,
    batch_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    return create_handoff(
        database,
        book_id,
        handoff_type=HandoffType.BATCH_CONTINUATION,
        batch_id=batch_id,
        **kwargs,
    )


def create_initialization_handoff(
    database: Database, book_id: str, **kwargs: Any
) -> dict[str, Any]:
    return create_handoff(
        database,
        book_id,
        handoff_type=HandoffType.NOVEL_INITIALIZATION,
        **kwargs,
    )


def _drift_reasons(
    database: Database, connection: sqlite3.Connection, row: sqlite3.Row
) -> list[str]:
    book_id = str(row["book_id"])
    edition_id = str(row["edition_id"])
    reasons: list[str] = []
    if _manifest_hash(database, book_id) != str(row["source_manifest_sha256"] or ""):
        reasons.append("source manifest hash changed")
    projection = projection_from_connection(connection, book_id, edition_id)
    if projection.sha256() != str(row["base_projection_hash"] or ""):
        reasons.append("projection hash changed")
    edition = connection.execute(
        "SELECT status FROM editions WHERE book_id=? AND edition_id=?",
        (book_id, edition_id),
    ).fetchone()
    if edition is None or str(edition["status"]) != str(row["edition_status"] or ""):
        reasons.append("edition status changed")
    chapters = edition_chapters(connection, book_id, edition_id)
    if row["effective_content_sha256"]:
        current_content = str(chapters[-1].get("content_sha256") or "") if chapters else ""
        if current_content != str(row["effective_content_sha256"]):
            reasons.append("effective chapter hash changed")
    if row["metric_run_id"]:
        metric_run = connection.execute(
            "SELECT input_bundle_hash, registry_hash, config_hash, invalidated_at "
            "FROM metric_runs WHERE run_id=?",
            (str(row["metric_run_id"]),),
        ).fetchone()
        if metric_run is None or metric_run["invalidated_at"] is not None:
            reasons.append("metric run missing or invalidated")
        else:
            if str(metric_run["input_bundle_hash"] or "") != str(row["metric_bundle_hash"] or ""):
                reasons.append("metric bundle hash changed")
            if str(metric_run["registry_hash"] or "") != str(row["registry_hash"] or ""):
                reasons.append("registry hash changed")
            if str(metric_run["config_hash"] or "") != str(row["config_hash"] or ""):
                reasons.append("config hash changed")
    if row["planning_aggregate_id"]:
        aggregate = connection.execute(
            "SELECT status, bundle_hash FROM planning_aggregates "
            "WHERE aggregate_id=? AND book_id=? AND edition_id=?",
            (str(row["planning_aggregate_id"]), book_id, edition_id),
        ).fetchone()
        if aggregate is None or str(aggregate["status"]) != "ACTIVE":
            reasons.append("planning aggregate missing or stale")
        elif str(aggregate["bundle_hash"] or "") != str(row["planning_aggregate_hash"] or ""):
            reasons.append("planning aggregate hash changed")
    if row["author_directives_hash"]:
        current_directives_hash = _author_directives_hash(connection, book_id, edition_id)
        if current_directives_hash != str(row["author_directives_hash"]):
            reasons.append("author directives hash changed")
    current_registry = load_registry().registry_hash
    current_metrics_hash = sha256_bytes(json_dumps(load_settings().metrics).encode("utf-8"))
    if current_registry != str(row["registry_hash"] or ""):
        reasons.append("current registry hash changed")
    if current_metrics_hash != str(row["config_hash"] or ""):
        reasons.append("current config hash changed")
    if row["rhythm_snapshot_id"]:
        rhythm = connection.execute(
            "SELECT 1 FROM rhythm_diagnostic_snapshots WHERE snapshot_id=? "
            "AND book_id=? AND edition_id=?",
            (str(row["rhythm_snapshot_id"]), book_id, edition_id),
        ).fetchone()
        if rhythm is None:
            reasons.append("rhythm snapshot missing")
    if row["atlas_id"]:
        atlas = connection.execute(
            "SELECT * FROM story_atlases WHERE atlas_id=? AND book_id=? AND edition_id=?",
            (str(row["atlas_id"]), book_id, edition_id),
        ).fetchone()
        if atlas is None or str(atlas["status"]) != "ACTIVE":
            reasons.append("Atlas missing or inactive")
        else:
            if row["atlas_version"] is not None and int(atlas["atlas_version"]) != int(
                row["atlas_version"]
            ):
                reasons.append("Atlas version changed")
            if row["atlas_manifest_hash"] and str(atlas["artifact_manifest_sha256"]) != str(
                row["atlas_manifest_hash"]
            ):
                reasons.append("Atlas manifest hash changed")
            if row["horizon_hash"] and str(atlas["horizon_hash"] or "") != str(
                row["horizon_hash"]
            ):
                reasons.append("Rolling Horizon hash changed")
            try:
                validation = validate_atlas(
                    database,
                    book_id,
                    edition_id,
                    root=Path(str(atlas["artifact_root"])),
                )
                if validation.errors:
                    reasons.append("Atlas validation failed")
            except (OSError, RuntimeError, ValueError):
                reasons.append("Atlas validation unavailable")
    if row["batch_id"]:
        batch = connection.execute(
            "SELECT * FROM batch_working_projections WHERE batch_id=? AND book_id=? "
            "AND edition_id=?",
            (str(row["batch_id"]), book_id, edition_id),
        ).fetchone()
        if batch is None:
            reasons.append("Batch missing")
        else:
            if row["batch_plan_hash"]:
                plan_path = (
                    _book_workspace(database, book_id)
                    / "editions"
                    / edition_id
                    / "batches"
                    / str(row["batch_id"])
                    / "batch_plan.json"
                )
                if not plan_path.is_file() or sha256_file(plan_path) != str(
                    row["batch_plan_hash"]
                ):
                    reasons.append("Batch plan hash changed")
            if row["atlas_id"] and str(batch["atlas_id"] or "") != str(row["atlas_id"]):
                reasons.append("Batch Atlas anchor changed")
            if row["horizon_hash"] and str(batch["horizon_hash"] or "") != str(
                row["horizon_hash"]
            ):
                reasons.append("Batch Horizon anchor changed")
    return list(dict.fromkeys(reasons))


def claim_handoff(database: Database, handoff_id: str, claimed_by: str) -> dict[str, Any]:
    database.initialize()
    stale_reason: str | None = None
    token: str | None = None
    with database.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM workflow_handoffs WHERE handoff_id=?", (handoff_id,)
        ).fetchone()
        if row is None:
            raise HandoffWorkflowError(f"handoff 不存在：{handoff_id}")
        if str(row["status"]) != HandoffStatus.READY_FOR_CODEX.value:
            raise HandoffWorkflowError(f"handoff 当前状态不可领取：{row['status']}")
        task_directory = Path(str(row["task_directory"]))
        manifest_path = _handoff_file(task_directory, "context_manifest.json")
        file_drift_reason: str | None = None
        if not manifest_path.is_file():
            file_drift_reason = "context_manifest.json 缺失"
        else:
            try:
                loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(loaded_manifest, dict):
                    raise ValueError("context_manifest.json 必须是 object")
                file_hashes = loaded_manifest.get("file_hashes", {})
                if not isinstance(file_hashes, dict):
                    raise ValueError("context_manifest.json 的 file_hashes 必须是 object")
                for relative_name, expected_hash in file_hashes.items():
                    candidate = _handoff_file(task_directory, str(relative_name)).resolve()
                    if task_directory.resolve() not in candidate.parents:
                        file_drift_reason = f"handoff 文件路径漂移：{relative_name}"
                        break
                    if not candidate.is_file() or sha256_file(candidate) != str(expected_hash):
                        file_drift_reason = f"handoff 文件 hash 漂移：{relative_name}"
                        break
            except (OSError, ValueError, TypeError) as exc:
                file_drift_reason = f"context_manifest.json 无效：{exc}"
        verification = (
            verify_sources(row["book_id"], _book_workspace(database, str(row["book_id"])).parent)
            if file_drift_reason is None
            else {"ok": False}
        )
        drift_reasons = _drift_reasons(database, connection, row)
        if file_drift_reason is not None:
            drift_reasons.append(file_drift_reason)
        if not bool(verification.get("ok")):
            drift_reasons.append("source verify failed")
        if drift_reasons:
            reason = "; ".join(dict.fromkeys(drift_reasons))
            connection.execute(
                "UPDATE workflow_handoffs SET status=?, stale_at=?, stale_reason=?, "
                "error_message=? "
                "WHERE handoff_id=?",
                (HandoffStatus.STALE.value, utc_now(), reason, reason, handoff_id),
            )
            stale_reason = reason
        else:
            token = secrets.token_urlsafe(24)
            now = utc_now()
            updated = connection.execute(
                "UPDATE workflow_handoffs SET status=?, claimed_by=?, claim_token=?, claimed_at=? "
                "WHERE handoff_id=? AND status=?",
                (
                    HandoffStatus.CLAIMED.value,
                    claimed_by,
                    token,
                    now,
                    handoff_id,
                    HandoffStatus.READY_FOR_CODEX.value,
                ),
            )
            if updated.rowcount != 1:
                raise HandoffWorkflowError("handoff 已被其他 Codex 客户端领取")
    if stale_reason is not None:
        append_event(database, handoff_id, "STALE", {"reason": stale_reason})
        raise HandoffWorkflowError(f"handoff 上下文已漂移，已标记 STALE：{stale_reason}")
    assert token is not None
    append_event(database, handoff_id, "CLAIMED", {"claimed_by": claimed_by}, claim_token=token)
    return {"handoff_id": handoff_id, "claim_token": token, "status": HandoffStatus.CLAIMED.value}


def _allowed_artifact_path(task_directory: Path, task: dict[str, Any], raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = task_directory / candidate
    resolved = candidate.resolve()
    allowed = [Path(str(item)).resolve() for item in task.get("allowed_paths", [])]
    if not any(resolved == root or root in resolved.parents for root in allowed):
        raise HandoffWorkflowError(f"artifact 路径不在 allowed_paths 内：{raw_path}")
    return resolved


def validate_handoff_result(
    database: Database,
    handoff_id: str,
    result: dict[str, Any],
    *,
    require_completed_status: bool = False,
) -> WorkflowHandoffResult:
    """Validate result.json against the frozen task and filesystem contract."""
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM workflow_handoffs WHERE handoff_id=?", (handoff_id,)
        ).fetchone()
        if row is None:
            raise HandoffWorkflowError("handoff 不存在")
        task_directory = Path(str(row["task_directory"])).resolve()
        task_path = _handoff_file(task_directory, "task.json")
        if not task_path.is_file():
            raise HandoffWorkflowError("task.json 缺失")
        task = json.loads(task_path.read_text(encoding="utf-8"))
        required_fields = {
            "handoff_id",
            "handoff_type",
            "requested_stage",
            "completed_stage",
            "book_id",
            "edition_id",
            "status",
            "task_ids",
            "candidate_ids",
            "selected_candidate_id",
            "contract_id",
            "draft_id",
            "campaign_id",
            "revision_unit_ids",
            "artifact_paths",
            "validation_summary",
            "warnings",
            "next_action",
            "canon_committed",
            "edition_activated",
            "base_event_seq",
            "base_projection_hash",
            "metric_run_ids",
            "metric_bundle_hash",
            "completed_at",
        }
        missing_fields = sorted(required_fields - set(result))
        if str(row["handoff_type"]) == HandoffType.NOVEL_INITIALIZATION.value:
            required_fields.update(
                {
                    "initialization_id",
                    "completed_arc_ids",
                    "failed_arc_ids",
                    "chapter_coverage",
                    "arc_coverage",
                    "entity_count",
                    "relationship_count",
                    "faction_count",
                    "ability_count",
                    "resource_count",
                    "region_count",
                    "thread_count",
                    "metric_observation_count",
                    "generated_visuals",
                    "readiness",
                    "review_queue",
                }
            )
            missing_fields = sorted(required_fields - set(result))
        if missing_fields:
            raise HandoffWorkflowError(
                f"result.json 缺少必填字段：{', '.join(missing_fields)}"
            )
        try:
            parsed = WorkflowHandoffResult.model_validate(result)
        except Exception as exc:
            raise HandoffWorkflowError(f"result.json 不符合 WorkflowHandoffResult：{exc}") from exc
        if parsed.handoff_id != handoff_id:
            raise HandoffWorkflowError("result handoff_id 不一致")
        for field, expected in (
            ("handoff_type", str(row["handoff_type"])),
            ("book_id", str(row["book_id"])),
            ("edition_id", str(row["edition_id"])),
            ("base_event_seq", int(row["base_event_seq"])),
            ("base_projection_hash", str(row["base_projection_hash"])),
        ):
            if getattr(parsed, field) != expected:
                raise HandoffWorkflowError(f"result {field} 与冻结 handoff 不一致")
        if row["metric_bundle_hash"] and parsed.metric_bundle_hash != str(
            row["metric_bundle_hash"]
        ):
            raise HandoffWorkflowError("result metric_bundle_hash 与冻结 handoff 不一致")
        if require_completed_status:
            status_path = task_directory / "status.json"
            if not status_path.is_file():
                raise HandoffWorkflowError("status.json 缺失")
            status_payload = json.loads(status_path.read_text(encoding="utf-8"))
            if str(status_payload.get("handoff_id")) != handoff_id:
                raise HandoffWorkflowError("status.json handoff_id 不一致")
            if str(status_payload.get("status")) != HandoffStatus.COMPLETED.value:
                raise HandoffWorkflowError("status.json 与 result.json 状态不一致")
        for raw_path in parsed.artifact_paths:
            artifact = _allowed_artifact_path(task_directory, task, raw_path)
            if not artifact.is_file():
                raise HandoffWorkflowError(f"required artifact 不存在：{raw_path}")
        if parsed.requested_stage.upper() != str(row["requested_stage"]).upper():
            raise HandoffWorkflowError("result requested_stage 不一致")
        return parsed


def validate_result_file(database: Database, handoff_id: str) -> dict[str, Any]:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT result_path FROM workflow_handoffs WHERE handoff_id=?", (handoff_id,)
        ).fetchone()
    if row is None:
        raise HandoffWorkflowError("handoff 不存在")
    result_path = Path(str(row["result_path"]))
    if not result_path.is_file():
        raise HandoffWorkflowError("result.json 缺失")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    parsed = validate_handoff_result(
        database, handoff_id, result, require_completed_status=True
    )
    return parsed.model_dump(mode="json")


def update_handoff_status(
    database: Database,
    handoff_id: str,
    status: HandoffStatus,
    *,
    claim_token: str,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    validated_result: WorkflowHandoffResult | None = None
    drift_reason: str | None = None
    invalid_result_reason: str | None = None
    if status == HandoffStatus.COMPLETED:
        if result is None:
            raise HandoffWorkflowError("COMPLETED 必须同时提供 result.json 内容")
        try:
            validated_result = validate_handoff_result(database, handoff_id, result)
            result = validated_result.model_dump(mode="json")
        except HandoffWorkflowError as exc:
            invalid_result_reason = str(exc)
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM workflow_handoffs WHERE handoff_id=?", (handoff_id,)
        ).fetchone()
        if row is None or str(row["claim_token"] or "") != claim_token:
            raise HandoffWorkflowError("claim_token 无效")
        current = HandoffStatus(str(row["status"]))
        if invalid_result_reason is not None:
            if HandoffStatus.FAILED not in _ALLOWED_TRANSITIONS.get(current, set()):
                raise HandoffWorkflowError(invalid_result_reason)
            now = utc_now()
            connection.execute(
                "UPDATE workflow_handoffs SET status=?, error_message=?, "
                "result_validation_json=? WHERE handoff_id=?",
                (
                    HandoffStatus.FAILED.value,
                    invalid_result_reason,
                    json_dumps({"valid": False, "error": invalid_result_reason}),
                    handoff_id,
                ),
            )
            task_directory = Path(str(row["task_directory"]))
            _write_json(
                task_directory / "status.json",
                {
                    "handoff_id": handoff_id,
                    "status": HandoffStatus.FAILED.value,
                    "updated_at": now,
                    "reason": invalid_result_reason,
                },
            )
            _write_json(
                task_directory / "error.json",
                {"error": invalid_result_reason, "created_at": now},
            )
            invalid_result_reason = f"INVALID_RESULT: {invalid_result_reason}"
        elif status not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise HandoffWorkflowError(f"非法 handoff 状态转换：{current.value} -> {status.value}")
        if status == HandoffStatus.COMPLETED and current == HandoffStatus.RUNNING:
            drift_reasons = _drift_reasons(database, connection, row)
            if drift_reasons:
                reason = "; ".join(drift_reasons)
                connection.execute(
                    "UPDATE workflow_handoffs SET status='STALE', stale_at=?, "
                    "stale_reason=?, drift_detected_at=?, error_message=? WHERE handoff_id=?",
                    (utc_now(), reason, utc_now(), reason, handoff_id),
                )
                task_directory = Path(str(row["task_directory"]))
                _write_json(
                    task_directory / "status.json",
                    {
                        "handoff_id": handoff_id,
                        "status": "STALE_RESULT",
                        "updated_at": utc_now(),
                        "reason": reason,
                    },
                )
                drift_reason = reason
        if invalid_result_reason is None and drift_reason is None:
            now = utc_now()
            completed = now if status == HandoffStatus.COMPLETED else None
            connection.execute(
                "UPDATE workflow_handoffs SET status=?, started_at=COALESCE(started_at, ?), "
                "completed_at=COALESCE(?, completed_at), "
                "error_message=?, result_json=?, result_validation_json=? WHERE handoff_id=?",
                (
                    status.value,
                    now
                    if status in (HandoffStatus.RUNNING, HandoffStatus.WAITING_FOR_USER)
                    else None,
                    completed,
                    error_message,
                    None if result is None else json_dumps(result),
                    None
                    if status != HandoffStatus.COMPLETED
                    else json_dumps({"valid": True}),
                    handoff_id,
                ),
            )
            task_directory = Path(str(row["task_directory"]))
            _write_json(
                task_directory / "status.json",
                {"handoff_id": handoff_id, "status": status.value, "updated_at": now},
            )
            if result is not None:
                if validated_result is None and (
                    result.get("canon_committed") is not False
                    or result.get("edition_activated") is not False
                ):
                    raise HandoffWorkflowError(
                        "handoff result 必须明确 canon_committed=false 且 edition_activated=false"
                    )
                _write_json(_handoff_file(task_directory, "result.json"), result)
            if error_message:
                _write_json(
                    task_directory / "error.json",
                    {"error": error_message, "created_at": now},
                )
    if invalid_result_reason is not None:
        append_event(
            database,
            handoff_id,
            HandoffStatus.FAILED.value,
            {"error": invalid_result_reason},
            claim_token=claim_token,
        )
        raise HandoffWorkflowError(invalid_result_reason)
    if drift_reason is not None:
        append_event(
            database,
            handoff_id,
            "DRIFT_DETECTED",
            {"reason": drift_reason},
            claim_token=claim_token,
        )
        raise HandoffWorkflowError(f"运行中的 handoff 发生漂移：{drift_reason}")
    append_event(
        database,
        handoff_id,
        status.value,
        {"error_message": error_message or ""},
        claim_token=claim_token,
    )
    return {"handoff_id": handoff_id, "status": status.value, "result": result}


def cancel_handoff(database: Database, handoff_id: str) -> dict[str, Any]:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT status FROM workflow_handoffs WHERE handoff_id=?", (handoff_id,)
        ).fetchone()
        if row is None:
            raise HandoffWorkflowError("handoff 不存在")
        if str(row["status"]) != HandoffStatus.READY_FOR_CODEX.value:
            raise HandoffWorkflowError("只能取消尚未领取的 handoff")
        connection.execute(
            "UPDATE workflow_handoffs SET status=? WHERE handoff_id=?",
            (HandoffStatus.CANCELLED.value, handoff_id),
        )
    append_event(database, handoff_id, "CANCELLED")
    return {"handoff_id": handoff_id, "status": HandoffStatus.CANCELLED.value}


def mark_stale(database: Database, handoff_id: str, reason: str = "manual stale") -> dict[str, Any]:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT status FROM workflow_handoffs WHERE handoff_id=?", (handoff_id,)
        ).fetchone()
        if row is None:
            raise HandoffWorkflowError("handoff 不存在")
        if str(row["status"]) in (HandoffStatus.COMPLETED.value, HandoffStatus.CANCELLED.value):
            raise HandoffWorkflowError("已结束 handoff 不可标记过期")
        connection.execute(
            "UPDATE workflow_handoffs SET status=?, stale_at=?, stale_reason=?, "
            "error_message=? WHERE handoff_id=?",
            (HandoffStatus.STALE.value, utc_now(), reason, reason, handoff_id),
        )
    append_event(database, handoff_id, "STALE", {"reason": reason})
    return {"handoff_id": handoff_id, "status": HandoffStatus.STALE.value, "reason": reason}


def write_waiting_for_user(
    database: Database,
    handoff_id: str,
    payload: dict[str, Any],
    *,
    claim_token: str | None = None,
) -> dict[str, Any]:
    waiting = WaitingForUser.model_validate(payload)
    current_status: str | None = None
    with database.connect() as connection:
        row = connection.execute(
            "SELECT task_directory, claim_token, status FROM workflow_handoffs WHERE handoff_id=?",
            (handoff_id,),
        ).fetchone()
        if row is None:
            raise HandoffWorkflowError("handoff 不存在")
        if claim_token is not None and str(row["claim_token"] or "") != claim_token:
            raise HandoffWorkflowError("claim_token 无效")
        current_status = str(row["status"])
        if claim_token is not None and current_status not in {
            HandoffStatus.RUNNING.value,
            HandoffStatus.WAITING_FOR_USER.value,
        }:
            raise HandoffWorkflowError("只有 RUNNING handoff 可以进入 WAITING_FOR_USER")
        task_directory = Path(str(row["task_directory"]))
        path = task_directory / "waiting_for_user.json"
        _write_json(path, waiting.model_dump(mode="json"))
        connection.execute(
            """
            INSERT INTO workflow_waiting_for_user(
                handoff_id, question_id, question, reason, options_json,
                related_artifacts_json, required_author_decision, response_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(handoff_id) DO UPDATE SET
                question_id=excluded.question_id, question=excluded.question,
                reason=excluded.reason, options_json=excluded.options_json,
                related_artifacts_json=excluded.related_artifacts_json,
                required_author_decision=excluded.required_author_decision,
                response_path=excluded.response_path, created_at=excluded.created_at,
                answered_at=NULL
            """,
            (
                handoff_id,
                waiting.question_id,
                waiting.question,
                waiting.reason,
                json_dumps(waiting.options),
                json_dumps(waiting.related_artifacts),
                waiting.required_author_decision,
                str(task_directory / "handoff_user_response.json"),
                utc_now(),
            ),
        )
    if claim_token is not None and current_status == HandoffStatus.RUNNING.value:
        update_handoff_status(
            database,
            handoff_id,
            HandoffStatus.WAITING_FOR_USER,
            claim_token=claim_token,
        )
    return waiting.model_dump(mode="json")


def read_waiting_for_user(database: Database, handoff_id: str) -> dict[str, Any] | None:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT task_directory FROM workflow_handoffs WHERE handoff_id=?",
            (handoff_id,),
        ).fetchone()
    if row is None:
        raise HandoffWorkflowError("handoff 不存在")
    path = Path(str(row["task_directory"])) / "waiting_for_user.json"
    if not path.is_file():
        return None
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def record_user_response(
    database: Database, handoff_id: str, response: dict[str, Any]
) -> dict[str, Any]:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT task_directory FROM workflow_handoffs WHERE handoff_id=?",
            (handoff_id,),
        ).fetchone()
        if row is None:
            raise HandoffWorkflowError("handoff 不存在")
        task_directory = Path(str(row["task_directory"]))
        path = task_directory / "handoff_user_response.json"
        payload = {"handoff_id": handoff_id, "response": response, "created_at": utc_now()}
        _write_json(path, payload)
        connection.execute(
            "UPDATE workflow_waiting_for_user SET answered_at=? WHERE handoff_id=?",
            (utc_now(), handoff_id),
        )
    append_event(database, handoff_id, "USER_RESPONSE", {"path": str(path)})
    return payload


def get_handoff(database: Database, handoff_id: str) -> dict[str, Any]:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM workflow_handoffs WHERE handoff_id=?", (handoff_id,)
        ).fetchone()
        if row is None:
            raise HandoffWorkflowError("handoff 不存在")
        events = connection.execute(
            "SELECT * FROM workflow_handoff_events WHERE handoff_id=? ORDER BY sequence",
            (handoff_id,),
        ).fetchall()
        waiting = connection.execute(
            "SELECT * FROM workflow_waiting_for_user WHERE handoff_id=?",
            (handoff_id,),
        ).fetchone()
        result = dict(row)
        result["events"] = [dict(item) for item in events]
        if waiting is not None:
            waiting_payload = dict(waiting)
            waiting_payload["options"] = json.loads(str(waiting["options_json"]))
            waiting_payload["related_artifacts"] = json.loads(
                str(waiting["related_artifacts_json"])
            )
            result["waiting_for_user"] = waiting_payload
        if result.get("result_json"):
            result["result"] = json.loads(str(result["result_json"]))
        return result


def copy_instruction(database: Database, handoff_id: str) -> str:
    row = get_handoff(database, handoff_id)
    return Path(str(row["prompt_path"])).read_text(encoding="utf-8")
