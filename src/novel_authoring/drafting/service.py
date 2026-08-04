from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from novel_authoring.contracts.draft import DraftOutput
from novel_authoring.db.database import Database
from novel_authoring.domain.models import DraftStatus
from novel_authoring.edition import edition_workspace, resolve_edition_id
from novel_authoring.planning.boundary import _workspace
from novel_authoring.planning.models import ChapterContract
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now


class DraftWorkflowError(RuntimeError):
    pass


def prepare_draft_task(
    database: Database,
    book_id: str,
    contract_id: str,
    *,
    edition_id: str | None = None,
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
    boundary_path = workspace / "boundaries" / f"{contract.boundary_packet_id}.md"
    if not boundary_path.exists():
        raise DraftWorkflowError("Boundary Packet 不存在，禁止准备正文任务")
    schema_json = json_dumps(DraftOutput.model_json_schema(), indent=2)
    task_id = stable_id("draft-task", contract_id, str(revision), str(row["contract_sha256"]))
    task_dir = workspace / "agent_tasks" / task_id
    output_dir = workspace / "agent_outputs" / task_id
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
    task_path = workspace / "agent_tasks" / task_id / "task.json"
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
    task_path = workspace / "agent_tasks" / task_id / "task.json"
    metadata = json.loads(task_path.read_text(encoding="utf-8"))
    path = output_path or workspace / "agent_outputs" / task_id / "output.json"
    try:
        output = DraftOutput.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise DraftWorkflowError(f"Draft output 不符合合同：{exc}") from exc
    if output.task_id != task_id or output.contract_id != metadata["contract_id"]:
        raise DraftWorkflowError("Draft output 的 task_id/contract_id 不匹配")
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
