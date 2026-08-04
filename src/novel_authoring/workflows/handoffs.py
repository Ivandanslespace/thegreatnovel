from __future__ import annotations

import json
import secrets
import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any

from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.ingest.service import verify_sources
from novel_authoring.metrics.service import MetricsAssembler
from novel_authoring.utils import json_dumps, sha256_file, stable_id, utc_now


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


class HandoffWorkflowError(RuntimeError):
    status_code = 409


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
) -> dict[str, Any]:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    workspace_root = _book_workspace(database, book_id)
    verification = verify_sources(book_id, workspace_root.parent)
    if not bool(verification.get("ok")):
        raise HandoffWorkflowError("source verify 失败，不能创建 handoff")
    with database.connect() as connection:
        projection = projection_from_connection(connection, book_id, selected)
    metric_context, latest = _current_metric_anchor(database, book_id, selected)
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
    if rhythm_snapshot_id is None:
        raise HandoffWorkflowError("当前 edition 没有 Rhythm Snapshot，不能冻结 handoff")
    handoff_id = stable_id(
        "handoff", book_id, selected, handoff_type.value, requested_stage, utc_now()
    )
    task_directory = workspace_root / "editions" / selected / "handoffs" / handoff_id
    artifacts = task_directory / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=False)
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
        "rhythm_snapshot_id": rhythm_snapshot_id,
        "registry_hash": metric_context.get("registry_hash", ""),
        "config_hash": metric_context.get("config_hash", ""),
        "allowed_paths": [str(artifacts.resolve()), str(task_directory.resolve())],
        "forbidden_actions": [
            "不得修改book",
            "不得批准正史",
            "不得批准改写Campaign",
            "不得启用Edition",
            "不得删除历史草稿",
            "不得绕过Validator",
        ],
        "expected_outputs": ["events.jsonl", "result.json", "status.json"],
        "task_schema_version": "handoff-v1",
    }
    skill_name = "continue-novel" if handoff_type == HandoffType.CONTINUATION else "revise-novel"
    prompt = (
        f"请使用仓库内的 ${skill_name} "
        "Skill，\n"
        f"领取并执行 task_id={handoff_id} 的待处理任务。\n\n"
        "严格读取任务目录中的 task.json、prompt.md、metric_context.json、"
        "context_manifest.json 和 output_schema.json。\n"
        f"按 requested_stage={requested_stage} 执行。不得修改 book，不得批准写入正史，"
        "不得启用 Edition。\n"
        "结束时写回 events.jsonl、result.json 和 status.json。"
    )
    context_manifest = {
        "book_id": book_id,
        "edition_id": selected,
        "base_projection_hash": projection.sha256(),
        "source_manifest_sha256": manifest_hash,
        "frozen_at": task["created_at"],
        "paths": ["task.json", "prompt.md", "metric_context.json", "output_schema.json"],
    }
    output_schema = {
        "type": "object",
        "required": ["status", "canon_committed", "edition_activated"],
        "properties": {
            "status": {"type": "string"},
            "canon_committed": {"const": False},
            "edition_activated": {"const": False},
        },
    }
    status_json = {
        "handoff_id": handoff_id,
        "status": HandoffStatus.READY_FOR_CODEX.value,
        "updated_at": task["created_at"],
    }
    for name, value in (
        ("task.json", task),
        ("prompt.md", prompt),
        ("metric_context.json", metric_context),
        ("context_manifest.json", context_manifest),
        ("output_schema.json", output_schema),
        ("status.json", status_json),
        ("result.json", {}),
    ):
        if isinstance(value, str):
            (task_directory / name).write_text(value, encoding="utf-8")
        else:
            _write_json(task_directory / name, value)
    context_manifest["file_hashes"] = {
        name: sha256_file(task_directory / name)
        for name in ("task.json", "prompt.md", "metric_context.json", "output_schema.json")
    }
    _write_json(task_directory / "context_manifest.json", context_manifest)
    (task_directory / "events.jsonl").write_text("", encoding="utf-8")
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO workflow_handoffs(
                handoff_id, book_id, edition_id, handoff_type, requested_stage, status,
                task_directory, prompt_path, task_manifest_path, output_schema_path,
                result_path, event_log_path, base_event_seq, base_projection_hash,
                source_manifest_sha256, metric_run_id, metric_bundle_hash, rhythm_snapshot_id,
                registry_hash, config_hash, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                handoff_id,
                book_id,
                selected,
                handoff_type.value,
                requested_stage,
                HandoffStatus.READY_FOR_CODEX.value,
                str(task_directory),
                str(task_directory / "prompt.md"),
                str(task_directory / "task.json"),
                str(task_directory / "output_schema.json"),
                str(task_directory / "result.json"),
                str(task_directory / "events.jsonl"),
                projection.through_event_seq,
                projection.sha256(),
                manifest_hash,
                metric_run_id,
                task["metric_bundle_hash"],
                task["rhythm_snapshot_id"],
                task["registry_hash"],
                task["config_hash"],
                task["created_at"],
            ),
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


def claim_handoff(database: Database, handoff_id: str, claimed_by: str) -> dict[str, Any]:
    database.initialize()
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
        manifest_path = task_directory / "context_manifest.json"
        if not manifest_path.is_file():
            raise HandoffWorkflowError("context_manifest.json 缺失")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative_name, expected_hash in dict(manifest.get("file_hashes", {})).items():
            candidate = task_directory / str(relative_name)
            if not candidate.is_file() or sha256_file(candidate) != str(expected_hash):
                raise HandoffWorkflowError(f"handoff 文件 hash 漂移：{relative_name}")
        verification = verify_sources(
            row["book_id"], _book_workspace(database, str(row["book_id"])).parent
        )
        projection = projection_from_connection(
            connection, str(row["book_id"]), str(row["edition_id"])
        )
        metric_drift = False
        if row["metric_run_id"]:
            metric_run = connection.execute(
                "SELECT input_bundle_hash, registry_hash, config_hash, invalidated_at "
                "FROM metric_runs WHERE run_id=?",
                (str(row["metric_run_id"]),),
            ).fetchone()
            metric_drift = (
                metric_run is None
                or metric_run["invalidated_at"] is not None
                or str(metric_run["input_bundle_hash"] or "")
                != str(row["metric_bundle_hash"] or "")
                or str(metric_run["registry_hash"] or "") != str(row["registry_hash"] or "")
                or str(metric_run["config_hash"] or "") != str(row["config_hash"] or "")
            )
        rhythm_drift = False
        if row["rhythm_snapshot_id"]:
            rhythm_drift = (
                connection.execute(
                    "SELECT 1 FROM rhythm_diagnostic_snapshots WHERE snapshot_id=? "
                    "AND book_id=? AND edition_id=?",
                    (str(row["rhythm_snapshot_id"]), str(row["book_id"]), str(row["edition_id"])),
                ).fetchone()
                is None
            )
        if (
            not bool(verification.get("ok"))
            or projection.sha256() != str(row["base_projection_hash"])
            or metric_drift
            or rhythm_drift
        ):
            connection.execute(
                "UPDATE workflow_handoffs SET status=?, stale_at=?, error_message=? "
                "WHERE handoff_id=?",
                (HandoffStatus.STALE.value, utc_now(), "冻结上下文已漂移", handoff_id),
            )
            raise HandoffWorkflowError("handoff 上下文已漂移，已标记 STALE")
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
    append_event(database, handoff_id, "CLAIMED", {"claimed_by": claimed_by}, claim_token=token)
    return {"handoff_id": handoff_id, "claim_token": token, "status": HandoffStatus.CLAIMED.value}


def update_handoff_status(
    database: Database,
    handoff_id: str,
    status: HandoffStatus,
    *,
    claim_token: str,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM workflow_handoffs WHERE handoff_id=?", (handoff_id,)
        ).fetchone()
        if row is None or str(row["claim_token"] or "") != claim_token:
            raise HandoffWorkflowError("claim_token 无效")
        current = HandoffStatus(str(row["status"]))
        if status not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise HandoffWorkflowError(f"非法 handoff 状态转换：{current.value} -> {status.value}")
        now = utc_now()
        completed = now if status == HandoffStatus.COMPLETED else None
        connection.execute(
            "UPDATE workflow_handoffs SET status=?, started_at=COALESCE(started_at, ?), "
            "completed_at=COALESCE(?, completed_at), "
            "error_message=?, result_json=? WHERE handoff_id=?",
            (
                status.value,
                now if status in (HandoffStatus.RUNNING, HandoffStatus.WAITING_FOR_USER) else None,
                completed,
                error_message,
                None if result is None else json_dumps(result),
                handoff_id,
            ),
        )
        task_directory = Path(str(row["task_directory"]))
        _write_json(
            task_directory / "status.json",
            {"handoff_id": handoff_id, "status": status.value, "updated_at": now},
        )
        if result is not None:
            if (
                result.get("canon_committed") is not False
                or result.get("edition_activated") is not False
            ):
                raise HandoffWorkflowError(
                    "handoff result 必须明确 canon_committed=false 且 edition_activated=false"
                )
            _write_json(task_directory / "result.json", result)
        if error_message:
            _write_json(task_directory / "error.json", {"error": error_message, "created_at": now})
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
            "UPDATE workflow_handoffs SET status=?, stale_at=?, error_message=? WHERE handoff_id=?",
            (HandoffStatus.STALE.value, utc_now(), reason, handoff_id),
        )
    append_event(database, handoff_id, "STALE", {"reason": reason})
    return {"handoff_id": handoff_id, "status": HandoffStatus.STALE.value, "reason": reason}


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
        result = dict(row)
        result["events"] = [dict(item) for item in events]
        if result.get("result_json"):
            result["result"] = json.loads(str(result["result_json"]))
        return result


def copy_instruction(database: Database, handoff_id: str) -> str:
    row = get_handoff(database, handoff_id)
    return Path(str(row["prompt_path"])).read_text(encoding="utf-8")
