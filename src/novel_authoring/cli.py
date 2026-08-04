from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

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
from novel_authoring.edition import (
    ACTIVATE_PHRASE,
    EditionWorkflowError,
    activate_edition,
    archive_edition,
    create_edition,
    get_edition,
    list_editions,
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
from novel_authoring.revision import (
    REVISION_APPROVAL_PHRASE,
    RevisionWorkflowError,
    approve_revision_campaign,
    build_revision_impact,
    build_revision_plan,
    complete_revision_impact_audit,
    create_revision_campaign,
    discard_revision_draft,
    import_revision_draft,
    prepare_revision_draft_task,
    revision_preview,
    validate_revision_campaign,
)
from novel_authoring.rhythm.service import (
    RhythmWorkflowError,
    diagnose_hooks,
    diagnose_rhythm,
    import_semantic_features,
    prepare_semantic_features,
    rebuild_features,
    show_features,
    show_latest_rhythm,
)
from novel_authoring.utils import json_dumps, safe_book_id
from novel_authoring.validation.service import ValidationWorkflowError, validate_draft
from novel_authoring.workflows.approval import (
    APPROVAL_PHRASE,
    ApprovalWorkflowError,
    approval_preview,
    approve_draft,
)
from novel_authoring.workflows.directives import DirectiveWorkflowError, add_directive
from novel_authoring.workflows.edition_export import EditionExportError, export_edition
from novel_authoring.workflows.exporting import ExportWorkflowError, export_book
from novel_authoring.workflows.extraction import (
    AgentContractError,
    build_reconcile_report,
    import_extraction_output,
    prepare_extraction_task,
    reconcile_fact,
    reconcile_record,
)

# Typer 0.9 (the project's test runtime) requires explicit Option defaults for
# required parameters; keep the compatibility annotations out of lint noise.
# ruff: noqa: B008, UP045

app = typer.Typer(help="小说作者辅助与续写系统 V1")
source_app = typer.Typer(help="不可变源文件命令")
extract_app = typer.Typer(help="Codex 结构化抽取文件合同")
boundary_app = typer.Typer(help="Continuation Boundary Packet")
contract_app = typer.Typer(help="Chapter Contract")
draft_app = typer.Typer(help="草稿文件合同与十项校验")
directive_app = typer.Typer(help="持久化作者要求、偏好与禁忌")
edition_app = typer.Typer(help="版本化 edition 生命周期")
revision_app = typer.Typer(help="显式批准、可回滚的版本化改写工作流")
revision_draft_app = typer.Typer(help="Revision Unit 的 REVISION_DRAFT 文件合同")
revision_contract_app = typer.Typer(help="Revision Plan/Unit 合同")
features_app = typer.Typer(help="章节确定性与语义特征文件合同")
rhythm_app = typer.Typer(help="edition-aware 长跨度节奏诊断")
hooks_app = typer.Typer(help="伏笔 Age/Dormancy/Readiness 动作诊断")
app.add_typer(source_app, name="source")
app.add_typer(extract_app, name="extract")
app.add_typer(boundary_app, name="boundary")
app.add_typer(contract_app, name="contract")
app.add_typer(draft_app, name="draft")
app.add_typer(directive_app, name="directive")
app.add_typer(edition_app, name="edition")
app.add_typer(revision_app, name="revision")
revision_app.add_typer(revision_draft_app, name="draft")
revision_app.add_typer(revision_contract_app, name="contract")
app.add_typer(features_app, name="features")
app.add_typer(rhythm_app, name="rhythm")
app.add_typer(hooks_app, name="hooks")

# Keep the required book ID as a plain type.  Commands provide an explicit
# ``typer.Option`` default so the project remains compatible with Typer 0.9;
# combining an ``Annotated[..., Option(...)]`` alias with another Option
# default raises ``MixedAnnotatedAndDefaultStyleError`` there.
BookId = str
Workspace = Annotated[Path, typer.Option("--workspace", help="workspace 根目录")]
ConfigPath = Annotated[Optional[Path], typer.Option("--config", help="可选 YAML 覆盖配置")]
EditionId = Annotated[
    Optional[str], typer.Option("--edition-id", help="edition ID；默认当前 ACTIVE，否则 base")
]


def _emit(value: object) -> None:
    typer.echo(json_dumps(value, indent=2))


@app.command("init")
def init_command(
    book_id: BookId = typer.Option(...),
    title: str = typer.Option(..., "--title"),
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
    book_id: BookId = typer.Option(...),
    title: str = typer.Option(..., "--title"),
    source_dir: Annotated[Path, typer.Option("--source-dir")] = Path("book"),
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
    manifest: Annotated[Optional[Path], typer.Option("--manifest")] = None,
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
def status_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """显示当前只读状态摘要。"""
    normalized = safe_book_id(book_id)
    database = Database(workspace.resolve() / normalized / "state.sqlite3")
    if not database.path.exists():
        typer.echo(f"状态库不存在：{database.path}", err=True)
        raise typer.Exit(code=2)
    from novel_authoring.edition import edition_chapters, resolve_edition_id

    selected_edition = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        mutable_tables = ("facts", "events", "drafts", "canon_commits", "author_directives")
        counts = {
            "source_documents": connection.execute(
                "SELECT COUNT(*) FROM source_documents WHERE book_id=?", (normalized,)
            ).fetchone()[0],
            "chapters": len(edition_chapters(connection, normalized, selected_edition)),
        }
        for table in mutable_tables:
            if selected_edition == "base":
                row = connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE book_id=? AND edition_id='base'",
                    (normalized,),
                ).fetchone()
            else:
                row = connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE book_id=? AND edition_id=?",
                    (normalized, selected_edition),
                ).fetchone()
            counts[table] = row[0]
        chapters = edition_chapters(connection, normalized, selected_edition)
        last_chapter = None if not chapters else {
            "ordinal": chapters[-1]["ordinal"],
            "raw_heading": chapters[-1].get("raw_heading", chapters[-1].get("title", "")),
        }
        latest_draft = connection.execute(
            """
            SELECT draft_id, contract_id, status, revision, chapter_title,
                   created_at, approved_at, committed_at
            FROM drafts WHERE book_id=? AND edition_id=? ORDER BY created_at DESC LIMIT 1
            """,
            (normalized, selected_edition),
        ).fetchone()
        projection = projection_from_connection(connection, normalized, edition_id=selected_edition)
        hard_conflicts = 0
        grouped: dict[tuple[object, object], set[str]] = {}
        for fact in projection.facts.values():
            key = (fact.get("subject_id"), fact.get("predicate"))
            grouped.setdefault(key, set()).add(json_dumps(fact.get("object")))
        hard_conflicts = sum(len(values) > 1 for values in grouped.values())
        pending_review = connection.execute(
            """
            SELECT COUNT(*) FROM facts
            WHERE book_id=? AND edition_id=? AND active=1 AND status!='CANON'
            """,
            (normalized, selected_edition),
        ).fetchone()[0]
    _emit(
        {
            "book_id": normalized,
            "edition_id": selected_edition,
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
def source_verify_command(
    book_id: BookId = typer.Option(...), workspace: Workspace = Path("workspace")
) -> None:
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
def snapshot_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """为当前已提交事件历史建立不可变快照。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    if not database.path.exists():
        typer.echo(f"状态库不存在：{database.path}", err=True)
        raise typer.Exit(code=2)
    _emit(create_snapshot(database, book_id, edition_id=edition_id))


@app.command("rebuild")
def rebuild_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """从 append-only 事件历史确定性重建 Canon Projection。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    if not database.path.exists():
        typer.echo(f"状态库不存在：{database.path}", err=True)
        raise typer.Exit(code=2)
    projection = rebuild_projection(database, book_id, edition_id=edition_id, persist=True)
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
    book_id: BookId = typer.Option(...),
    chapter_start: int = typer.Option(..., "--chapter-start"),
    chapter_end: int = typer.Option(..., "--chapter-end"),
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
    book_id: BookId = typer.Option(...),
    task_id: str = typer.Option(..., "--task-id"),
    workspace: Workspace = Path("workspace"),
    output: Annotated[Optional[Path], typer.Option("--output")] = None,
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
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    fact_id: Annotated[Optional[str], typer.Option("--fact-id")] = None,
    record_type: Annotated[Optional[str], typer.Option("--record-type")] = None,
    record_id: Annotated[Optional[str], typer.Option("--record-id")] = None,
    decision: Annotated[Optional[str], typer.Option("--decision")] = None,
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
    book_id: str = typer.Option(..., "--book-id", help="ASCII 稳定小说 ID"),
    directive_type: str = typer.Option(..., "--type"),
    content: str = typer.Option(..., "--content"),
    workspace: Workspace = Path("workspace"),
    scope: Annotated[str, typer.Option("--scope")] = "next_chapter",
    priority: Annotated[int, typer.Option("--priority")] = 100,
    edition_id: EditionId = None,
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
            edition_id=edition_id,
        )
    except (DirectiveWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@app.command("diagnose")
def diagnose_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
    input_path: Annotated[Optional[Path], typer.Option("--input")] = None,
    edition_id: EditionId = None,
) -> None:
    """按宪法公式计算六项 V1 指标并保存输入证据。"""
    workspace_book = workspace.resolve() / safe_book_id(book_id)
    path = input_path or workspace_book / "metric_inputs.json"
    try:
        settings = load_settings(config)
        bundle = load_metric_bundle(path)
        results = diagnose_bundle(bundle, settings.metrics)
        database = Database(workspace_book / "state.sqlite3")
        from novel_authoring.edition import resolve_edition_id

        result_ids = persist_results(
            database,
            book_id,
            results,
            settings.metrics,
            edition_id=resolve_edition_id(database, book_id, edition_id),
        )
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
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
    edition_id: EditionId = None,
) -> None:
    """在任何正文步骤之前建立并保存续写边界包。"""
    settings = load_settings(config)
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = build_boundary_packet(
            database,
            book_id,
            recent_full_chapters=settings.recent_full_chapters,
            edition_id=edition_id,
        )
    except (PlanningError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@app.command("plan-next")
def plan_next_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
    task_id: Annotated[Optional[str], typer.Option("--task-id")] = None,
    output: Annotated[Optional[Path], typer.Option("--output")] = None,
    edition_id: EditionId = None,
) -> None:
    """准备三个候选任务，或验证、评分并导入候选 output.json。"""
    settings = load_settings(config)
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        if task_id is None:
            if output is not None:
                raise PlanningError("提供 --output 时必须同时提供 --task-id")
            result = prepare_candidate_task(database, book_id, settings, edition_id=edition_id)
        else:
            result = import_candidate_output(
                database,
                book_id,
                task_id,
                settings,
                output,
                edition_id=edition_id,
            )
    except (PlanningError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@contract_app.command("build")
def contract_build_command(
    book_id: BookId = typer.Option(...),
    candidate_id: str = typer.Option(..., "--candidate-id"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """从通过硬门的候选生成可审查章节合同。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = build_chapter_contract(database, book_id, candidate_id, edition_id=edition_id)
    except (PlanningError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@draft_app.command("prepare")
def draft_prepare_command(
    book_id: BookId = typer.Option(...),
    contract_id: str = typer.Option(..., "--contract-id"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """生成只允许写 output.json 的正文任务包，不触碰正史。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = prepare_draft_task(database, book_id, contract_id, edition_id=edition_id)
    except (DraftWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@draft_app.command("import")
def draft_import_command(
    book_id: BookId = typer.Option(...),
    task_id: str = typer.Option(..., "--task-id"),
    workspace: Workspace = Path("workspace"),
    output: Annotated[Optional[Path], typer.Option("--output")] = None,
    edition_id: EditionId = None,
) -> None:
    """验证并导入 Codex 正文 output.json；状态只能进入 DRAFT。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = import_draft_output(database, book_id, task_id, output, edition_id=edition_id)
    except (DraftWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@draft_app.command("validate")
def draft_validate_command(
    book_id: BookId = typer.Option(...),
    draft_id: str = typer.Option(..., "--draft-id"),
    workspace: Workspace = Path("workspace"),
    config: ConfigPath = None,
    edition_id: EditionId = None,
) -> None:
    """运行宪法规定的十项校验；任一硬错误都阻止 VALIDATED。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = validate_draft(
            database,
            book_id,
            draft_id,
            load_settings(config),
            edition_id=edition_id,
        )
    except (ValidationWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc
    _emit(result.model_dump(mode="json"))
    if not result.passed:
        raise typer.Exit(code=5)


@draft_app.command("show")
def draft_show_command(
    book_id: BookId = typer.Option(...),
    draft_id: str = typer.Option(..., "--draft-id"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """显示草稿、状态和校验报告，不改变正史。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = show_draft(database, book_id, draft_id, edition_id=edition_id)
    except (DraftWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@draft_app.command("discard")
def draft_discard_command(
    book_id: BookId = typer.Option(...),
    draft_id: str = typer.Option(..., "--draft-id"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """拒绝未批准草稿并保留审计记录；不会污染正史。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = discard_draft(database, book_id, draft_id, edition_id=edition_id)
    except (DraftWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@app.command("approve")
def approve_command(
    book_id: str = typer.Option(..., "--book-id", help="ASCII 稳定小说 ID"),
    draft_id: str = typer.Option(..., "--draft-id"),
    workspace: Workspace = Path("workspace"),
    confirmation: str = typer.Option(
        "", "--confirm", help=f"必须逐字输入：{APPROVAL_PHRASE}"
    ),
    edition_id: EditionId = None,
) -> None:
    """显式批准 VALIDATED 草稿并以单事务提交事件、投影和快照。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        preview = approval_preview(database, book_id, draft_id, edition_id=edition_id)
        _emit({"approval_preview": preview})
        result = approve_draft(
            database,
            book_id,
            draft_id,
            confirmation=confirmation,
            edition_id=edition_id,
        )
    except (ApprovalWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=6) from exc
    _emit(result)


@app.command("export")
def export_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    output_dir: Annotated[Optional[Path], typer.Option("--output-dir")] = None,
    edition_id: EditionId = None,
) -> None:
    """导出投影、审计记录与已批准续写；不复制或修改原始 book。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        from novel_authoring.edition import BASE_EDITION_ID, resolve_edition_id

        selected_edition = resolve_edition_id(database, book_id, edition_id)
        if selected_edition == BASE_EDITION_ID:
            result = export_book(database, book_id, output_dir)
        else:
            result = export_edition(database, book_id, selected_edition, output_dir)
    except (ExportWorkflowError, EditionExportError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@edition_app.command("list")
def edition_list_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
) -> None:
    """列出 base 与所有派生 edition。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit([item.model_dump(mode="json") for item in list_editions(database, book_id)])
    except (EditionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@edition_app.command("create")
def edition_create_command(
    book_id: BookId = typer.Option(...),
    edition_id: str = typer.Option(..., "--edition-id"),
    display_name: str = typer.Option(..., "--display-name", "--name"),
    workspace: Workspace = Path("workspace"),
    parent_edition_id: Annotated[
        Optional[str], typer.Option("--parent-edition-id", "--parent")
    ] = None,
) -> None:
    """从当前或指定父 edition 冻结锚点并建立 DRAFT。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = create_edition(
            database,
            book_id,
            edition_id,
            display_name,
            parent_edition_id=parent_edition_id,
        )
        _emit(result.model_dump(mode="json"))
    except (EditionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@edition_app.command("activate")
def edition_activate_command(
    book_id: BookId = typer.Option(...),
    edition_id: str = typer.Option(..., "--edition-id"),
    workspace: Workspace = Path("workspace"),
    confirmation: Annotated[
        str, typer.Option("--confirm", help=f"必须逐字输入：{ACTIVATE_PHRASE}")
    ] = "",
) -> None:
    """显式启用已 VALIDATED 的 edition；不会修改 base。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = activate_edition(database, book_id, edition_id, confirmation=confirmation)
        _emit(result.model_dump(mode="json"))
    except (EditionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=6) from exc


@edition_app.command("archive")
def edition_archive_command(
    book_id: BookId = typer.Option(...),
    edition_id: str = typer.Option(..., "--edition-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """归档派生 edition；base 永不删除。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(archive_edition(database, book_id, edition_id).model_dump(mode="json"))
    except (EditionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@edition_app.command("show")
def edition_show_command(
    book_id: BookId = typer.Option(...),
    edition_id: str = typer.Option(..., "--edition-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """显示一个 edition 的冻结锚点与生命周期状态。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(get_edition(database, book_id, edition_id).model_dump(mode="json"))
    except (EditionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@edition_app.command("export")
def edition_export_command(
    book_id: BookId = typer.Option(...),
    edition_id: str = typer.Option(..., "--edition-id"),
    workspace: Workspace = Path("workspace"),
    output_dir: Annotated[Optional[Path], typer.Option("--output-dir")] = None,
) -> None:
    """导出指定 edition 的完整替换版与改写审计。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(export_edition(database, book_id, edition_id, output_dir))
    except (EditionExportError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_app.command("create")
def revision_create_command(
    book_id: BookId = typer.Option(...),
    spec: Path = typer.Option(..., "--spec"),
    edition_id: str = typer.Option(..., "--edition-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """校验并持久化 RevisionSpec。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(create_revision_campaign(database, book_id, spec, edition_id=edition_id))
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_app.command("impact")
def revision_impact_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """执行 deterministic FTS/source scan 并生成 Codex 语义审计任务。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(build_revision_impact(database, book_id, campaign_id))
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_app.command("impact-complete")
def revision_impact_complete_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
    decisions: Annotated[Optional[Path], typer.Option("--decisions")] = None,
) -> None:
    """导入语义审计处置 JSON；未处置项不会被默认视为已完成。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        value: list[dict[str, object]] | None = None
        if decisions is not None:
            value = json.loads(decisions.read_text(encoding="utf-8"))
        _emit(complete_revision_impact_audit(database, book_id, campaign_id, value))
    except (RevisionWorkflowError, OSError, ValueError, json.JSONDecodeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_app.command("plan")
def revision_plan_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """把影响包编译为有依赖顺序的 Revision Plan/Units。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(build_revision_plan(database, book_id, campaign_id))
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_contract_app.command("build")
def revision_contract_build_nested_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """为 campaign 构建 Revision Plan/Unit 合同（revision plan 的兼容别名）。"""
    revision_plan_command(book_id, campaign_id, workspace)


@revision_app.command("draft-task")
def revision_draft_task_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    unit_id: str = typer.Option(..., "--unit-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """为一个 Revision Unit 生成 REVISION_DRAFT 任务与 schema。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(prepare_revision_draft_task(database, book_id, campaign_id, unit_id))
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_app.command("import")
def revision_import_command(
    book_id: BookId = typer.Option(...),
    output: Path = typer.Option(..., "--output"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """验证并导入 REVISION_DRAFT；只进入 revision_drafts。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(import_revision_draft(database, book_id, output))
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_app.command("validate")
def revision_validate_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """运行十项改写校验及既有十项校验审计面。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        result = validate_revision_campaign(database, book_id, campaign_id)
        _emit(result)
        if not bool(result["passed"]):
            raise typer.Exit(code=5)
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc


@revision_app.command("preview")
def revision_preview_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """显示改写差异、variants、事件与未解决影响项。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(revision_preview(database, book_id, campaign_id))
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_app.command("status")
def revision_status_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """显示 campaign、impact、unit、variant 和未解决项状态。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(revision_preview(database, book_id, campaign_id))
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_app.command("approve")
def revision_approve_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
    confirmation: str = typer.Option(
        "", "--confirm", help=f"必须逐字输入：{REVISION_APPROVAL_PHRASE}"
    ),
) -> None:
    """批准改写 campaign；只写入目标 edition，且不自动激活。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        preview = revision_preview(database, book_id, campaign_id)
        _emit({"approval_preview": preview})
        _emit(
            approve_revision_campaign(
                database, book_id, campaign_id, confirmation=confirmation
            )
        )
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=6) from exc


@revision_app.command("discard")
def revision_discard_command(
    book_id: BookId = typer.Option(...),
    draft_id: str = typer.Option(..., "--draft-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """丢弃改写草稿；不会生成 chapter variant。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(discard_revision_draft(database, book_id, draft_id))
    except (RevisionWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@revision_draft_app.command("prepare")
def revision_draft_prepare_nested_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    unit_id: str = typer.Option(..., "--unit-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """Nested alias for revision draft prepare."""
    revision_draft_task_command(book_id, campaign_id, unit_id, workspace)


@revision_draft_app.command("import")
def revision_draft_import_nested_command(
    book_id: BookId = typer.Option(...),
    output: Path = typer.Option(..., "--output"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """Nested alias for revision draft import."""
    revision_import_command(book_id, output, workspace)


@revision_draft_app.command("validate")
def revision_draft_validate_nested_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """Nested alias for final campaign validation."""
    revision_validate_command(book_id, campaign_id, workspace)


@revision_draft_app.command("show")
def revision_draft_show_nested_command(
    book_id: BookId = typer.Option(...),
    campaign_id: str = typer.Option(..., "--campaign-id"),
    workspace: Workspace = Path("workspace"),
) -> None:
    """Nested alias for revision preview/show."""
    revision_preview_command(book_id, campaign_id, workspace)


@features_app.command("prepare")
def features_prepare_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    chapter_id: Annotated[Optional[str], typer.Option("--chapter-id")] = None,
) -> None:
    """为章节生成严格的 ChapterSemanticFeaturesOutput 任务。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(
            prepare_semantic_features(
                database, book_id, edition_id=edition_id, chapter_id=chapter_id
            )
        )
    except (RhythmWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@features_app.command("import")
def features_import_command(
    book_id: BookId = typer.Option(...),
    task_id: str = typer.Option(..., "--task-id"),
    workspace: Workspace = Path("workspace"),
    output: Annotated[Optional[Path], typer.Option("--output")] = None,
) -> None:
    """验证并导入 ChapterSemanticFeaturesOutput；不修改章节正文。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(import_semantic_features(database, book_id, task_id, output))
    except (RhythmWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@features_app.command("rebuild")
def features_rebuild_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """按当前 edition 章节正文确定性重建有效特征。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(rebuild_features(database, book_id, edition_id=edition_id))
    except (RhythmWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@features_app.command("show")
def features_show_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    chapter_id: Annotated[Optional[str], typer.Option("--chapter-id")] = None,
) -> None:
    """显示当前 content hash 对应的有效特征行与证据来源。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(show_features(database, book_id, edition_id=edition_id, chapter_id=chapter_id))
    except (RhythmWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@rhythm_app.command("diagnose")
def rhythm_diagnose_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    as_of_chapter: Annotated[Optional[int], typer.Option("--as-of-chapter")] = None,
) -> None:
    """输出章节功能、标题、首尾、情绪连续诊断及伏笔队列。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(
            diagnose_rhythm(
                database,
                book_id,
                edition_id=edition_id,
                as_of_chapter=as_of_chapter,
            )
        )
    except (RhythmWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@rhythm_app.command("show")
def rhythm_show_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """读取指定 edition 最近一次节奏诊断快照。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(show_latest_rhythm(database, book_id, edition_id=edition_id))
    except (RhythmWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@hooks_app.command("diagnose")
def hooks_diagnose_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """输出 HOLD/ADVANCE/RESOLVE/OVERDUE 伏笔动作队列。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(diagnose_hooks(database, book_id, edition_id=edition_id))
    except (RhythmWorkflowError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@hooks_app.command("show")
def hooks_show_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """show 是 diagnose 的只读别名，保持动作队列结构不变。"""
    hooks_diagnose_command(book_id, workspace, edition_id)


if __name__ == "__main__":
    app()
