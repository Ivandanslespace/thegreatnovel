from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from novel_authoring.context.router import (
    ContextPurpose,
    RuntimeContextRequest,
    route_runtime_context,
)
from novel_authoring.contracts.draft import DraftOutput
from novel_authoring.db.database import Database
from novel_authoring.domain.models import DraftStatus
from novel_authoring.edition import edition_workspace, resolve_edition_id
from novel_authoring.planning.boundary import _workspace
from novel_authoring.planning.models import ChapterContract
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.operations import book_root, ensure_operation, find_operation
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now


class DraftWorkflowError(RuntimeError):
    pass


def prepare_draft_task(
    database: Database,
    book_id: str,
    contract_id: str,
    *,
    edition_id: str | None = None,
    include_runtime_state: bool = True,
) -> dict[str, object]:
    database.initialize()
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM chapter_contracts WHERE book_id=? AND contract_id=? AND edition_id=?",
            (book_id, contract_id, selected_edition),
        ).fetchone()
        if row is None:
            raise DraftWorkflowError(f"章节合同不存在：{contract_id}")
        if row["status"] != "READY":
            raise DraftWorkflowError(f"章节合同状态不可写作：{row['status']}")
        revision = (
            int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM drafts
                    WHERE book_id=? AND contract_id=? AND edition_id=?
                    """,
                    (book_id, contract_id, selected_edition),
                ).fetchone()[0]
            )
            + 1
        )
    if revision > 3:
        raise DraftWorkflowError("同一章节合同最多允许初稿加两轮修订")
    contract = ChapterContract.model_validate_json(str(row["contract_json"]))
    workspace = edition_workspace(database, book_id, selected_edition)
    root = book_root(database, book_id)
    boundary_dir = (
        BookLayout(root.parent).for_book(book_id).edition(selected_edition).boundaries
        if (root / "book.yaml").is_file()
        else workspace / "boundaries"
    )
    boundary_path = boundary_dir / f"{contract.boundary_packet_id}.md"
    if not boundary_path.exists():
        raise DraftWorkflowError("Boundary Packet 不存在，禁止准备正文任务")
    boundary_json_path = boundary_path.with_suffix(".json")
    boundary_payload = (
        json.loads(boundary_json_path.read_text(encoding="utf-8"))
        if boundary_json_path.is_file()
        else {}
    )
    runtime_context = route_runtime_context(
        database,
        book_id,
        edition_id=selected_edition,
        purpose=ContextPurpose.DRAFT,
        request=RuntimeContextRequest(
            purpose=ContextPurpose.DRAFT,
            include_runtime_state=include_runtime_state,
        ),
        boundary=boundary_payload,
    )
    schema_json = json_dumps(DraftOutput.model_json_schema(), indent=2)
    task_id = stable_id("draft-task", contract_id, str(revision), str(row["contract_sha256"]))
    operation = ensure_operation(
        database,
        book_id,
        selected_edition,
        task_id,
        "DRAFT",
        {"contract_id": contract_id, "revision": revision},
    )
    task_dir = (
        operation.input
        if operation is not None
        else workspace / "agent_tasks" / task_id
    )
    output_dir = (
        operation.output
        if operation is not None
        else workspace / "agent_outputs" / task_id
    )
    task_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_text = "\n".join(
        [
            f"# 章节正文任务 `{task_id}`",
            "",
            f"revision: {revision}",
            "",
            "严格依据下面的 Boundary Packet 与 Chapter Contract 写正文。",
            "正文不得声明新事实已自动进入正史；state_changes 必须逐项给出正文短证据。",
            "按 Chapter Contract 中冻结的 InnovationControl 执行；它只改变创作距离，"
            "不改变 Canon、Timeline、Knowledge、Capability、Resource、Approval 或 "
            "Edition hard gates。",
            f"Creative-distance guidance：{contract.innovation_control.creative_distance_guidance}",
            "Lens tendency："
            f"{contract.innovation_control.lens_tendency_guidance}；不得把它写成 Score Bonus。",
            "只写 output.json，不要修改 book；系统会把合法正文导入 drafts。",
            "",
            "## Continuation Boundary Packet",
            "",
            boundary_path.read_text(encoding="utf-8"),
            "",
            "## Chapter Contract",
            "",
            "```json",
            str(row["contract_json"]),
            "```",
            "",
            "## Runtime Context Router（hard boundary + earned surface + soft controls）",
            "",
            "```json",
            json_dumps(runtime_context.model_dump(mode="json"), indent=2),
            "```",
            "",
            (
                "本次是 Planning-only Runtime 消融：Draft 阶段不得读取 raw Runtime Baseline、"
                "Earned Surface 或 Effective Runtime 表；只使用 Contract、最近正文和 "
                "style/dialogue/narrative controls。"
                if not include_runtime_state
                else "本次是 Full Runtime Draft：Runtime 只能影响角色行动和规划兑现，"
                "不得把工程字段写进小说正文。"
            ),
        ]
    )
    metadata = {
        "task_id": task_id,
        "task_type": "draft",
        "book_id": book_id,
        "edition_id": selected_edition,
        "contract_id": contract_id,
        "revision": revision,
        "boundary_packet_id": contract.boundary_packet_id,
        "base_event_seq": contract.continuation_boundary["base_event_seq"],
        "base_projection_hash": contract.continuation_boundary["base_projection_hash"],
        "schema_sha256": sha256_bytes(schema_json.encode()),
        "created_at": utc_now(),
        "runtime_context": runtime_context.model_dump(mode="json"),
        "include_runtime_state": include_runtime_state,
        "runtime_ablation": "FULL_RUNTIME" if include_runtime_state else "PLANNING_ONLY",
        "raw_runtime_tables_loaded": include_runtime_state,
        "innovation_control": contract.innovation_control.model_dump(mode="json"),
    }
    (task_dir / "input.md").write_text(input_text, encoding="utf-8")
    (task_dir / "schema.json").write_text(schema_json + "\n", encoding="utf-8")
    (task_dir / "task.json").write_text(json_dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "task_id": task_id,
        "contract_id": contract_id,
        "revision": revision,
        "input": str(task_dir / "input.md"),
        "schema": str(task_dir / "schema.json"),
        "expected_output": str(output_dir / "output.json"),
    }


def import_draft_output(
    database: Database,
    book_id: str,
    task_id: str,
    output_path: Path | None = None,
    *,
    edition_id: str | None = None,
) -> dict[str, object]:
    database.initialize()
    workspace = _workspace(database, book_id)
    if edition_id is not None:
        workspace = edition_workspace(database, book_id, edition_id)
    operation = find_operation(database, book_id, edition_id or "base", task_id)
    task_path = (
        operation.input / "task.json"
        if operation is not None
        else workspace / "agent_tasks" / task_id / "task.json"
    )
    if not task_path.exists() and edition_id is None:
        candidates = list((workspace / "editions").glob(f"*/agent_tasks/{task_id}/task.json"))
        if candidates:
            task_path = candidates[0]
            workspace = task_path.parents[2]
    if not task_path.exists():
        raise DraftWorkflowError(f"正文任务不存在：{task_id}")
    metadata = json.loads(task_path.read_text(encoding="utf-8"))
    selected_edition = str(metadata.get("edition_id", "base"))
    workspace = edition_workspace(database, book_id, selected_edition)
    operation = find_operation(database, book_id, selected_edition, task_id)
    task_path = (
        operation.input / "task.json"
        if operation is not None
        else workspace / "agent_tasks" / task_id / "task.json"
    )
    metadata = json.loads(task_path.read_text(encoding="utf-8"))
    path = output_path or (
        operation.output / "output.json"
        if operation is not None
        else workspace / "agent_outputs" / task_id / "output.json"
    )
    try:
        output = DraftOutput.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise DraftWorkflowError(f"Draft output 不符合合同：{exc}") from exc
    if output.task_id != task_id or output.contract_id != metadata["contract_id"]:
        raise DraftWorkflowError("Draft output 的 task_id/contract_id 不匹配")
    contract_row = None
    with database.connect() as connection:
        contract_row = connection.execute(
            "SELECT contract_json FROM chapter_contracts WHERE contract_id=? AND book_id=?",
            (output.contract_id, book_id),
        ).fetchone()
    if contract_row is not None:
        contract = ChapterContract.model_validate_json(str(contract_row["contract_json"]))
        expected = contract.innovation_control
        if output.innovation_control is not None and output.innovation_control != expected:
            raise DraftWorkflowError(
                "Draft output 的 innovation_control 与 Chapter Contract 不一致"
            )
    content = output.prose_markdown.strip() + "\n"
    content_hash = sha256_bytes(content.encode())
    draft_id = stable_id("draft", output.contract_id, str(metadata["revision"]), content_hash)
    drafts_dir = workspace / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    draft_path = drafts_dir / f"{draft_id}.md"
    draft_path.write_bytes(content.encode("utf-8"))
    with database.connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO drafts(
                draft_id, book_id, contract_id, candidate_id, file_path,
                content_sha256, status, revision, created_at, task_id, edition_id,
                chapter_title, output_json, base_event_seq, base_projection_hash
            )
            SELECT ?, ?, ?, candidate_id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            FROM chapter_contracts WHERE contract_id=? AND book_id=? AND edition_id=?
            """,
            (
                draft_id,
                book_id,
                output.contract_id,
                str(draft_path),
                content_hash,
                DraftStatus.DRAFT.value,
                int(metadata["revision"]),
                utc_now(),
                task_id,
                selected_edition,
                output.chapter_title,
                json_dumps(output.model_dump(mode="json")),
                int(metadata["base_event_seq"]),
                str(metadata["base_projection_hash"]),
                output.contract_id,
                book_id,
                selected_edition,
            ),
        )
        exists = connection.execute("SELECT 1 FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
    if exists is None:
        raise DraftWorkflowError("无法关联章节合同，草稿未导入")
    return {
        "draft_id": draft_id,
        "path": str(draft_path),
        "status": DraftStatus.DRAFT.value,
        "revision": int(metadata["revision"]),
        "content_sha256": content_hash,
    }


def show_draft(
    database: Database,
    book_id: str,
    draft_id: str,
    *,
    edition_id: str | None = None,
) -> dict[str, object]:
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM drafts WHERE book_id=? AND draft_id=? AND edition_id=?",
            (book_id, draft_id, selected_edition),
        ).fetchone()
        reports = connection.execute(
            """
            SELECT validator, severity, passed, report_json
            FROM validation_reports WHERE book_id=? AND draft_id=? ORDER BY validator
            """,
            (book_id, draft_id),
        ).fetchall()
    if row is None:
        raise DraftWorkflowError(f"草稿不存在：{draft_id}")
    return {
        "draft_id": draft_id,
        "status": row["status"],
        "revision": row["revision"],
        "path": row["file_path"],
        "content_sha256": row["content_sha256"],
        "content": Path(str(row["file_path"])).read_text(encoding="utf-8"),
        "validation": [
            {
                "validator": report["validator"],
                "severity": report["severity"],
                "passed": bool(report["passed"]),
                "report": json.loads(str(report["report_json"])),
            }
            for report in reports
        ],
    }


def discard_draft(
    database: Database,
    book_id: str,
    draft_id: str,
    *,
    edition_id: str | None = None,
) -> dict[str, object]:
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        row = connection.execute(
            "SELECT status FROM drafts WHERE book_id=? AND draft_id=? AND edition_id=?",
            (book_id, draft_id, selected_edition),
        ).fetchone()
        if row is None:
            raise DraftWorkflowError(f"草稿不存在：{draft_id}")
        if row["status"] in {
            DraftStatus.AUTHOR_APPROVED.value,
            DraftStatus.CANON_COMMITTED.value,
        }:
            raise DraftWorkflowError("已批准或已提交草稿不可丢弃")
        connection.execute(
            "UPDATE drafts SET status=? WHERE draft_id=?",
            (DraftStatus.REJECTED.value, draft_id),
        )
    return {"draft_id": draft_id, "status": DraftStatus.REJECTED.value}
