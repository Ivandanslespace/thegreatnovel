from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from novel_authoring.canon.projection import projection_from_connection, rebuild_projection
from novel_authoring.canon.state import create_snapshot, projection_counts
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.drafting.service import (
    DraftWorkflowError,
    discard_draft,
    import_draft_output,
    prepare_draft_task,
    show_draft,
)
from novel_authoring.ingest.service import (
    ImmutableSourceError,
    SourceAmbiguityError,
    ingest_book,
    scan_sources,
    verify_sources,
    write_manifest,
)
from novel_authoring.metrics.engine import diagnose_bundle, load_metric_bundle, persist_results
from novel_authoring.planning.boundary import PlanningError, build_boundary_packet
from novel_authoring.planning.candidates import import_candidate_output, prepare_candidate_task
from novel_authoring.planning.contracts import build_chapter_contract
from novel_authoring.utils import json_dumps, safe_book_id
from novel_authoring.validation.service import ValidationWorkflowError, validate_draft
from novel_authoring.workflows.approval import (
    APPROVAL_PHRASE,
    ApprovalWorkflowError,
    approval_preview,
    approve_draft,
)
from novel_authoring.workflows.directives import DirectiveWorkflowError, add_directive
from novel_authoring.workflows.exporting import ExportWorkflowError, export_book
from novel_authoring.workflows.extraction import (
    AgentContractError,
    build_reconcile_report,
    import_extraction_output,
    prepare_extraction_task,
    reconcile_fact,
    reconcile_record,
)

app = typer.Typer(help="小说作者辅助与续写系统 V1")
source_app = typer.Typer(help="不可变源文件命令")
extract_app = typer.Typer(help="Codex 结构化抽取文件合同")
boundary_app = typer.Typer(help="Continuation Boundary Packet")
contract_app = typer.Typer(help="Chapter Contract")
draft_app = typer.Typer(help="草稿文件合同与十项校验")
directive_app = typer.Typer(help="持久化作者要求、偏好与禁忌")
app.add_typer(source_app, name="source")
app.add_typer(extract_app, name="extract")
app.add_typer(boundary_app, name="boundary")
app.add_typer(contract_app, name="contract")
app.add_typer(draft_app, name="draft")
app.add_typer(directive_app, name="directive")

BookId = Annotated[str, typer.Option("--book-id", help="ASCII 稳定小说 ID")]
Workspace = Annotated[Path, typer.Option("--workspace", help="workspace 根目录")]
ConfigPath = Annotated[Path | None, typer.Option("--config", help="可选 YAML 覆盖配置")]


def _emit(value: object) -> None:
    typer.echo(json_dumps(value, indent=2))


@app.command("init")
def init_command(
    book_id: BookId,
    title: Annotated[str, typer.Option("--title")],
    source_dir: Annotated[Path, typer.Option("--source-dir")] = Path("book"),
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
) -> None:
    """建立 workspace、数据库和 source manifest，不导入正文。"""
    normalized = safe_book_id(book_id)
    settings = load_settings(config)
    workspace_book = workspace.resolve() / normalized
    database = Database(workspace_book / "state.sqlite3")
    database.initialize()
    manifest = scan_sources(normalized, source_dir, settings)
    manifest_path = write_manifest(manifest, workspace_book)
    with database.connect() as connection:
        from novel_authoring.utils import utc_now

        now = utc_now()
        connection.execute(
            """
            INSERT INTO books(
                book_id, title, mode, source_root, workspace_root, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(book_id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at
            """,
            (
                normalized,
                title,
                settings.default_mode,
                str(source_dir.resolve()),
                str(workspace_book),
                now,
                now,
            ),
        )
    _emit(
        {
            "book_id": normalized,
            "database": str(database.path),
            "manifest": str(manifest_path),
            "manifest_status": manifest.status,
        }
    )


@app.command("ingest")
def ingest_command(
    book_id: BookId,
    title: Annotated[str, typer.Option("--title")],
    source_dir: Annotated[Path, typer.Option("--source-dir")] = Path("book"),
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
    manifest: Annotated[Path | None, typer.Option("--manifest")] = None,
    confirm_order: Annotated[bool, typer.Option("--confirm-order")] = False,
) -> None:
    """导入不可变原文；多文件顺序未经确认时阻断。"""
    try:
        result = ingest_book(
            book_id=safe_book_id(book_id),
            title=title,
            source_root=source_dir,
            workspace_root=workspace,
            settings=load_settings(config),
            confirm_order=confirm_order,
            manifest_path=manifest,
        )
    except (SourceAmbiguityError, ImmutableSourceError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    _emit(
        {
            "book_id": result.book_id,
            "documents_imported": result.documents_imported,
            "documents_unchanged": result.documents_unchanged,
            "chapters_imported": result.chapters_imported,
            "warnings": result.warnings,
            "manifest": str(result.manifest_path),
        }
    )


@app.command("status")
def status_command(book_id: BookId, workspace: Workspace = Path("workspace")) -> None:
    """显示当前只读状态摘要。"""
    normalized = safe_book_id(book_id)
    database = Database(workspace.resolve() / normalized / "state.sqlite3")
    if not database.path.exists():
        typer.echo(f"状态库不存在：{database.path}", err=True)
        raise typer.Exit(code=2)
    with database.connect() as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "source_documents",
                "chapters",
                "facts",
                "events",
                "drafts",
                "canon_commits",
                "author_directives",
            )
        }
        last_chapter = connection.execute(
            """
            SELECT ordinal, raw_heading FROM chapters
            WHERE book_id=? ORDER BY ordinal DESC LIMIT 1
            """,
            (normalized,),
        ).fetchone()
        hard_conflicts = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT subject_id, predicate
                FROM facts
                WHERE book_id=? AND active=1 AND status='CANON'
                GROUP BY subject_id, predicate
                HAVING COUNT(DISTINCT object_json) > 1
            )
            """,
            (normalized,),
        ).fetchone()[0]
        pending_review = connection.execute(
            """
            SELECT COUNT(*) FROM facts
            WHERE book_id=? AND active=1 AND status!='CANON'
            """,
            (normalized,),
        ).fetchone()[0]
        latest_draft = connection.execute(
            """
            SELECT draft_id, contract_id, status, revision, chapter_title,
                   created_at, approved_at, committed_at
            FROM drafts WHERE book_id=? ORDER BY created_at DESC LIMIT 1
            """,
            (normalized,),
        ).fetchone()
        projection = projection_from_connection(connection, normalized)
    _emit(
        {
            "book_id": normalized,
            "database": str(database.path),
            "counts": counts,
            "last_chapter": dict(last_chapter) if last_chapter is not None else None,
            "projection": {
                "through_event_seq": projection.through_event_seq,
                "state_sha256": projection.sha256(),
            },
            "unresolved_hard_conflicts": int(hard_conflicts),
            "pending_fact_review": int(pending_review),
            "latest_draft": dict(latest_draft) if latest_draft is not None else None,
        }
    )


@source_app.command("verify")
def source_verify_command(book_id: BookId, workspace: Workspace = Path("workspace")) -> None:
    """复核所有源文件 SHA-256；不修改源文件。"""
    try:
        report = verify_sources(safe_book_id(book_id), workspace)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    _emit(report)
    if not report["ok"]:
        raise typer.Exit(code=3)


@app.command("snapshot")
def snapshot_command(book_id: BookId, workspace: Workspace = Path("workspace")) -> None:
    """为当前已提交事件历史建立不可变快照。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    if not database.path.exists():
        typer.echo(f"状态库不存在：{database.path}", err=True)
        raise typer.Exit(code=2)
    _emit(create_snapshot(database, book_id))


@app.command("rebuild")
def rebuild_command(book_id: BookId, workspace: Workspace = Path("workspace")) -> None:
    """从 append-only 事件历史确定性重建 Canon Projection。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    if not database.path.exists():
        typer.echo(f"状态库不存在：{database.path}", err=True)
        raise typer.Exit(code=2)
    projection = rebuild_projection(database, book_id, persist=True)
    _emit(
        {
            "book_id": book_id,
            "through_event_seq": projection.through_event_seq,
            "state_sha256": projection.sha256(),
            "counts": projection_counts(projection),
        }
    )


@extract_app.command("prepare")
def extract_prepare_command(
    book_id: BookId,
    chapter_start: Annotated[int, typer.Option("--chapter-start")],
    chapter_end: Annotated[int, typer.Option("--chapter-end")],
    workspace: Workspace = Path("workspace"),
) -> None:
    """按章块生成 input.md、schema.json 和 task.json。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = prepare_extraction_task(
            database,
            book_id,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
        )
    except AgentContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    _emit(result)


@extract_app.command("import")
def extract_import_command(
    book_id: BookId,
    task_id: Annotated[str, typer.Option("--task-id")],
    workspace: Workspace = Path("workspace"),
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    """验证并导入 Codex output.json；默认只进入推断隔离区。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = import_extraction_output(database, book_id, task_id, output)
    except AgentContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    _emit(result)


@app.command("reconcile")
def reconcile_command(
    book_id: BookId,
    workspace: Workspace = Path("workspace"),
    fact_id: Annotated[str | None, typer.Option("--fact-id")] = None,
    record_type: Annotated[str | None, typer.Option("--record-type")] = None,
    record_id: Annotated[str | None, typer.Option("--record-id")] = None,
    decision: Annotated[str | None, typer.Option("--decision")] = None,
    reason: Annotated[str, typer.Option("--reason")] = "人工整理",
) -> None:
    """生成冲突报告，或显式接受/拒绝一条结构化抽取记录。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        if record_id is not None:
            if record_type is None or decision is None:
                raise AgentContractError(
                    "提供 --record-id 时必须同时提供 --record-type 和 --decision"
                )
            if fact_id is not None:
                raise AgentContractError("--fact-id 与 --record-id 不得同时使用")
            result = reconcile_record(
                database,
                book_id,
                record_type,
                record_id,
                decision=decision,
                reason=reason,
            )
        elif fact_id is None:
            result = build_reconcile_report(database, book_id)
        elif decision is None:
            raise AgentContractError("提供 --fact-id 时必须同时提供 --decision")
        else:
            result = reconcile_fact(
                database,
                book_id,
                fact_id,
                decision=decision,
                reason=reason,
            )
    except AgentContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    _emit(result)


@directive_app.command("add")
def directive_add_command(
    book_id: BookId,
    directive_type: Annotated[str, typer.Option("--type")],
    content: Annotated[str, typer.Option("--content")],
    workspace: Workspace = Path("workspace"),
    scope: Annotated[str, typer.Option("--scope")] = "next_chapter",
    priority: Annotated[int, typer.Option("--priority")] = 100,
) -> None:
    """先持久化用户对下一章的明确要求，再允许进入规划。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = add_directive(
            database,
            book_id,
            directive_type=directive_type,
            content=content,
            scope=scope,
            priority=priority,
        )
    except (DirectiveWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@app.command("diagnose")
def diagnose_command(
    book_id: BookId,
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
    input_path: Annotated[Path | None, typer.Option("--input")] = None,
) -> None:
    """按宪法公式计算六项 V1 指标并保存输入证据。"""
    workspace_book = workspace.resolve() / safe_book_id(book_id)
    path = input_path or workspace_book / "metric_inputs.json"
    try:
        settings = load_settings(config)
        bundle = load_metric_bundle(path)
        results = diagnose_bundle(bundle, settings.metrics)
        database = Database(workspace_book / "state.sqlite3")
        result_ids = persist_results(database, book_id, results, settings.metrics)
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    _emit(
        {
            "book_id": book_id,
            "results": [result.model_dump(mode="json") for result in results],
            "result_ids": result_ids,
        }
    )


@boundary_app.command("build")
def boundary_build_command(
    book_id: BookId,
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
) -> None:
    """在任何正文步骤之前建立并保存续写边界包。"""
    settings = load_settings(config)
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = build_boundary_packet(
            database,
            book_id,
            recent_full_chapters=settings.recent_full_chapters,
        )
    except (PlanningError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@app.command("plan-next")
def plan_next_command(
    book_id: BookId,
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
    task_id: Annotated[str | None, typer.Option("--task-id")] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    """准备三个候选任务，或验证、评分并导入候选 output.json。"""
    settings = load_settings(config)
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        if task_id is None:
            if output is not None:
                raise PlanningError("提供 --output 时必须同时提供 --task-id")
            result = prepare_candidate_task(database, book_id, settings)
        else:
            result = import_candidate_output(
                database,
                book_id,
                task_id,
                settings,
                output,
            )
    except (PlanningError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@contract_app.command("build")
def contract_build_command(
    book_id: BookId,
    candidate_id: Annotated[str, typer.Option("--candidate-id")],
    workspace: Workspace = Path("workspace"),
) -> None:
    """从通过硬门的候选生成可审查章节合同。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = build_chapter_contract(database, book_id, candidate_id)
    except (PlanningError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@draft_app.command("prepare")
def draft_prepare_command(
    book_id: BookId,
    contract_id: Annotated[str, typer.Option("--contract-id")],
    workspace: Workspace = Path("workspace"),
) -> None:
    """生成只允许写 output.json 的正文任务包，不触碰正史。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = prepare_draft_task(database, book_id, contract_id)
    except (DraftWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@draft_app.command("import")
def draft_import_command(
    book_id: BookId,
    task_id: Annotated[str, typer.Option("--task-id")],
    workspace: Workspace = Path("workspace"),
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    """验证并导入 Codex 正文 output.json；状态只能进入 DRAFT。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = import_draft_output(database, book_id, task_id, output)
    except (DraftWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@draft_app.command("validate")
def draft_validate_command(
    book_id: BookId,
    draft_id: Annotated[str, typer.Option("--draft-id")],
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
) -> None:
    """运行宪法规定的十项校验；任一硬错误都阻止 VALIDATED。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = validate_draft(database, book_id, draft_id, load_settings(config))
    except (ValidationWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc
    _emit(result.model_dump(mode="json"))
    if not result.passed:
        raise typer.Exit(code=5)


@draft_app.command("show")
def draft_show_command(
    book_id: BookId,
    draft_id: Annotated[str, typer.Option("--draft-id")],
    workspace: Workspace = Path("workspace"),
) -> None:
    """显示草稿、状态和校验报告，不改变正史。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = show_draft(database, book_id, draft_id)
    except (DraftWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@draft_app.command("discard")
def draft_discard_command(
    book_id: BookId,
    draft_id: Annotated[str, typer.Option("--draft-id")],
    workspace: Workspace = Path("workspace"),
) -> None:
    """拒绝未批准草稿并保留审计记录；不会污染正史。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = discard_draft(database, book_id, draft_id)
    except (DraftWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@app.command("approve")
def approve_command(
    book_id: BookId,
    draft_id: Annotated[str, typer.Option("--draft-id")],
    workspace: Workspace = Path("workspace"),
    confirmation: Annotated[
        str,
        typer.Option("--confirm", help=f"必须逐字输入：{APPROVAL_PHRASE}"),
    ] = "",
) -> None:
    """显式批准 VALIDATED 草稿并以单事务提交事件、投影和快照。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        preview = approval_preview(database, book_id, draft_id)
        _emit({"approval_preview": preview})
        result = approve_draft(
            database,
            book_id,
            draft_id,
            confirmation=confirmation,
        )
    except (ApprovalWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=6) from exc
    _emit(result)


@app.command("export")
def export_command(
    book_id: BookId,
    workspace: Workspace = Path("workspace"),
    output_dir: Annotated[Path | None, typer.Option("--output-dir")] = None,
) -> None:
    """导出投影、审计记录与已批准续写；不复制或修改原始 book。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = export_book(database, book_id, output_dir)
    except (ExportWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


if __name__ == "__main__":
    app()
