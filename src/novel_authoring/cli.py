from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

from novel_authoring.atlas.models import AtlasAction
from novel_authoring.atlas.offline import export_snapshot
from novel_authoring.atlas.service import (
    AtlasError,
    atlas_root,
    get_atlas_overview,
    list_atlas_history,
    record_atlas_action,
    register_atlas,
    validate_atlas,
)
from novel_authoring.atlas.visuals import render_atlas_visuals
from novel_authoring.canon.projection import projection_from_connection, rebuild_projection
from novel_authoring.canon.state import create_snapshot, projection_counts
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.demo import seed_author_workbench
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
from novel_authoring.initialization.metrics import (
    import_metric_bootstrap,
    metric_bootstrap_status,
    prepare_metric_bootstrap,
    rebuild_initialization_metric_runs,
)
from novel_authoring.initialization.service import (
    InitializationError,
    create_initialization,
    latest_initialization,
    refresh_initialization,
)
from novel_authoring.metrics.engine import diagnose_bundle, load_metric_bundle, persist_results
from novel_authoring.metrics.models import MetricSemanticObservationsOutput
from novel_authoring.metrics.registry import load_registry
from novel_authoring.metrics.segments import list_segments, rebuild_segments
from novel_authoring.metrics.service import (
    AuthorMetricInputService,
    MetricConflictError,
    MetricsAssembler,
    ObservationResolver,
    import_semantic_output,
)
from novel_authoring.planning.aggregates import build_planning_aggregate
from novel_authoring.planning.batch import (
    complete_chunk,
    create_batch,
    create_checkpoint,
    get_batch_plan,
    get_batch_projection,
    get_chunk_context,
)
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
from novel_authoring.storage.cleanup import (
    CleanupCandidate,
    CleanupCategory,
    apply_cleanup,
    plan_cleanup,
)
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.migration import (
    MigrationOptions,
    cleanup_legacy,
    migrate_legacy,
)
from novel_authoring.storage.registry import BookRegistry
from novel_authoring.storage.retention import (
    RetentionConfig,
    apply_retention,
    plan_retention,
    retention_candidates,
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
from novel_authoring.workflows.handoffs import (
    HandoffStatus,
    HandoffType,
    HandoffWorkflowError,
    cancel_handoff,
    claim_handoff,
    create_batch_continuation_handoff,
    create_continuation_handoff,
    create_initialization_handoff,
    create_revision_handoff,
    create_story_atlas_handoff,
    get_handoff,
    mark_stale,
    update_handoff_status,
    validate_result_file,
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
metrics_app = typer.Typer(help="provenance-aware 指标观测与运行")
metrics_semantic_app = typer.Typer(help="语义指标观察文件合同")
observation_app = typer.Typer(help="append-only Metric Observation 解析与撤回")
atlas_app = typer.Typer(help="Versioned Soft Story Atlas")
initialize_app = typer.Typer(help="已有长篇 Atlas-first 深度初始化")
initialize_metrics_app = typer.Typer(help="批量 Semantic Metric Bootstrap")
batch_app = typer.Typer(help="滚动 Batch Continuation 与 Provisional Projection")
demo_app = typer.Typer(help="合成演示数据")
segments_app = typer.Typer(help="effective edition 段落与证据")
workflow_app = typer.Typer(help="Local File Handoff Protocol")
web_app = typer.Typer(help="本地 Author Workbench（不启动 Codex 进程）")
library_app = typer.Typer(help="Canonical Book Library 与 legacy 迁移")
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
app.add_typer(metrics_app, name="metrics")
metrics_app.add_typer(metrics_semantic_app, name="semantic")
app.add_typer(observation_app, name="observation")
app.add_typer(atlas_app, name="atlas")
app.add_typer(initialize_app, name="initialize")
initialize_app.add_typer(initialize_metrics_app, name="metrics")
app.add_typer(batch_app, name="batch")
app.add_typer(demo_app, name="demo")
app.add_typer(segments_app, name="segments")
app.add_typer(workflow_app, name="workflow")
app.add_typer(workflow_app, name="handoff")
app.add_typer(web_app, name="web")
app.add_typer(library_app, name="library")

# Keep the required book ID as a plain type.  Commands provide an explicit
# ``typer.Option`` default so the project remains compatible with Typer 0.9;
# combining an ``Annotated[..., Option(...)]`` alias with another Option
# default raises ``MixedAnnotatedAndDefaultStyleError`` there.
BookId = str
Workspace = Annotated[Path, typer.Option("--workspace", help="workspace 根目录")]
ConfigPath = Annotated[Optional[Path], typer.Option("--config", help="可选 YAML 覆盖配置")]
LibraryRoot = Annotated[
    Optional[Path], typer.Option("--library-root", help="书库根目录；默认项目根目录/library")
]
EditionId = Annotated[
    Optional[str], typer.Option("--edition-id", help="edition ID；默认当前 ACTIVE，否则 base")
]


def _book_library(library_root: Path | None) -> tuple[BookLayout, BookRegistry]:
    layout = BookLayout.default() if library_root is None else BookLayout(library_root)
    return layout, BookRegistry(layout)


def _cleanup_candidates(layout: BookLayout, book_id: str) -> list[CleanupCandidate]:
    candidates = retention_candidates(layout, book_id=book_id)
    paths = layout.for_book(book_id)
    for edition_root in sorted(paths.editions.glob("*"), key=lambda item: item.name.casefold()):
        if not edition_root.is_dir() or edition_root.is_symlink():
            continue
        for svg in sorted(edition_root.rglob("*.svg"), key=lambda item: item.as_posix().casefold()):
            if svg.is_file() and not svg.is_symlink():
                candidates.append(
                    CleanupCandidate(
                        path=svg,
                        category=CleanupCategory.REGENERABLE,
                        book_id=book_id,
                        reason="SVG 是显式可重建导出，不是 Atlas required artifact",
                        kind="svg_export",
                    )
                )
    return candidates


@library_app.command("list")
def library_list_command(library_root: LibraryRoot = None) -> None:
    """列出书库中已有 book.yaml 的书。"""

    _layout, registry = _book_library(library_root)
    _emit(
        [
            {
                "book_id": record.book_id,
                "title": record.title,
                "root": str(record.root),
                "source_files": list(record.source_files),
                "active_edition_id": record.active_edition_id,
                "readiness_status": record.readiness_status,
                "legacy_locations": list(record.legacy_locations),
            }
            for record in registry.list()
        ]
    )


@library_app.command("init")
def library_init_command(
    book_id: BookId = typer.Option(..., "--book-id"),
    title: Optional[str] = typer.Option(None, "--title"),
    library_root: LibraryRoot = None,
) -> None:
    """建立一本书的 canonical 目录和 book.yaml，不复制正文。"""

    _layout, registry = _book_library(library_root)
    record = registry.ensure(book_id, title=title)
    _emit(
        {
            "book_id": record.book_id,
            "root": str(record.root),
            "book_yaml": str(record.root / "book.yaml"),
            "readme": str(record.root / "README.md"),
        }
    )


@library_app.command("import")
def library_import_command(
    source: Path = typer.Option(..., "--source", exists=True, file_okay=True, dir_okay=False),
    book_id: BookId = typer.Option(..., "--book-id"),
    title: Optional[str] = typer.Option(None, "--title"),
    library_root: LibraryRoot = None,
) -> None:
    """导入一个新的只读来源文件到 canonical library。"""

    source_path = source.expanduser().resolve()
    _layout, registry = _book_library(library_root)
    paths = _layout.ensure_book(book_id)
    destination = paths.source / source_path.name
    if destination.exists():
        if destination.read_bytes() != source_path.read_bytes():
            raise typer.BadParameter(f"目标来源已存在且内容不同: {destination}")
    else:
        shutil.copy2(source_path, destination)
    record = registry.ensure(book_id, title=title, source_path=destination)
    _emit(
        {
            "book_id": record.book_id,
            "source": str(destination),
            "source_read_only": True,
            "sha256": record.source_files and registry.read(record.book_id).get("source", {}).get("sha256"),
            "root": str(record.root),
        }
    )


@library_app.command("paths")
def library_paths_command(
    book_id: BookId = typer.Option(..., "--book-id"),
    edition_id: str = typer.Option("base", "--edition-id"),
    operation_id: Optional[str] = typer.Option(None, "--operation-id"),
    library_root: LibraryRoot = None,
) -> None:
    """输出一本书的 canonical path map，便于 Web/脚本复核。"""

    layout, _registry = _book_library(library_root)
    paths = layout.for_book(book_id)
    edition = paths.edition(edition_id)
    value: dict[str, object] = {
        "layout_version": layout.layout_version,
        "book_id": paths.book_id,
        "root": str(paths.root),
        "book_yaml": str(paths.book_yaml),
        "readme": str(paths.readme),
        "source": str(paths.source),
        "system": str(paths.system),
        "database": str(paths.database),
        "source_manifest": str(paths.source_manifest),
        "system_snapshots": str(paths.snapshots),
        "system_logs": str(paths.logs),
        "system_cache": str(paths.cache),
        "system_temp": str(paths.temp),
        "editions": str(paths.editions),
        "edition": {
            "edition_id": edition.edition_id,
            "root": str(edition.root),
            "analysis": str(edition.analysis),
            "initialization": str(edition.initialization),
            "atlas": str(edition.atlas),
            "metrics": str(edition.metrics),
            "rhythm": str(edition.rhythm),
            "writing": str(edition.writing),
            "drafts": str(edition.drafts),
            "continuation": str(edition.continuation),
            "revisions": str(edition.revisions),
            "validation": str(edition.validation),
            "boundaries": str(edition.boundaries),
            "candidates": str(edition.candidates),
            "contracts": str(edition.contracts),
            "operations": str(edition.operations),
            "batches": str(edition.batches),
            "canon": str(edition.canon),
            "exports": str(edition.exports),
            "latest_export": str(edition.latest_export),
            "archive_exports": str(edition.archive_exports),
        },
    }
    if operation_id is not None:
        operation = edition.operation(operation_id)
        value["operation"] = {
            "operation_id": operation.operation_id,
            "root": str(operation.root),
            "manifest": str(operation.manifest),
            "status": str(operation.status),
            "events": str(operation.events),
            "input": str(operation.input),
            "output": str(operation.output),
            "artifacts": str(operation.artifacts),
            "logs": str(operation.logs),
        }
    _emit(value)


@library_app.command("migrate-legacy")
def library_migrate_legacy_command(
    book_id: BookId = typer.Option(..., "--book-id"),
    source_root: Path = typer.Option(..., "--source-root"),
    workspace_root: Path = typer.Option(..., "--workspace-root"),
    library_root: LibraryRoot = None,
    dry_run: bool = typer.Option(True, "--dry-run/--apply"),
) -> None:
    """迁移旧书库到 canonical library；默认只生成 dry-run 计划。"""

    result = migrate_legacy(
        MigrationOptions(
            book_id=book_id,
            source_root=source_root,
            workspace_root=workspace_root,
            library_root=library_root,
            apply=not dry_run,
        )
    )
    _emit(result.to_dict())


@library_app.command("cleanup-legacy")
def library_cleanup_legacy_command(
    book_id: BookId = typer.Option(..., "--book-id"),
    library_root: LibraryRoot = None,
    dry_run: bool = typer.Option(True, "--dry-run/--apply"),
    confirmation: Optional[str] = typer.Option(None, "--confirmation", "--confirm"),
) -> None:
    """按 legacy_locations.json 生成报告，apply 时只移动到可恢复 archive。"""

    try:
        _emit(
            cleanup_legacy(
                BookLayout.default() if library_root is None else BookLayout(library_root),
                book_id,
                apply=not dry_run,
                confirmation=confirmation,
            )
        )
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@library_app.command("retention")
def library_retention_command(
    library_root: LibraryRoot = None,
    book_id: Optional[str] = typer.Option(None, "--book-id"),
    keep: int = typer.Option(3, "--keep", min=0),
    dry_run: bool = typer.Option(True, "--dry-run/--apply"),
    confirmation: Optional[str] = typer.Option(None, "--confirmation", "--confirm"),
) -> None:
    """规划或安全归档超出保留数的 normal Portable Snapshot。"""

    try:
        report = plan_retention(
            BookLayout.default() if library_root is None else BookLayout(library_root),
            config=RetentionConfig(normal_portable_exports=keep),
            book_id=book_id,
        )
        _emit(
            report
            if dry_run
            else apply_retention(report, confirmation or "")
        )
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@library_app.command("cleanup")
def library_cleanup_command(
    book_id: BookId = typer.Option(..., "--book-id"),
    library_root: LibraryRoot = None,
    dry_run: bool = typer.Option(True, "--dry-run/--apply"),
    confirmation: Optional[str] = typer.Option(None, "--confirmation", "--confirm"),
) -> None:
    """只规划或安全归档可重建导出；source/DB/Canon 永远不在候选中。"""

    try:
        layout = BookLayout.default() if library_root is None else BookLayout(library_root)
        report = plan_cleanup(
            layout,
            candidates=_cleanup_candidates(layout, book_id),
            book_id=book_id,
        )
        _emit(report if dry_run else apply_cleanup(report, confirmation or ""))
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


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
    batch_id: Annotated[Optional[str], typer.Option("--batch-id")] = None,
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
            batch_id=batch_id,
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


@metrics_app.command("rebuild")
def metrics_rebuild_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    scope_type: str = typer.Option("CHAPTER", "--scope-type"),
    scope_id: Annotated[Optional[str], typer.Option("--scope-id")] = None,
) -> None:
    """从有效 edition、状态和 append-only observations 重建 Metric Run。"""
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(MetricsAssembler(database).rebuild(
            book_id, edition_id=edition_id, scope_type=scope_type, scope_id=scope_id
        ))
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


def _run_metric_scope(
    book_id: BookId,
    workspace: Path,
    edition_id: EditionId,
    scope_type: str,
    scope_id: str | None,
    requested_metric_ids: list[str] | None = None,
) -> None:
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(
            MetricsAssembler(database).rebuild(
                book_id,
                edition_id=edition_id,
                scope_type=scope_type,
                scope_id=scope_id,
                requested_metric_ids=requested_metric_ids,
            )
        )
    except (MetricConflictError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@metrics_app.command("run-chapter")
def metrics_run_chapter_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    chapter_id: Annotated[Optional[str], typer.Option("--chapter-id")] = None,
) -> None:
    """只运行 Registry 中 scope=CHAPTER 的指标。"""
    _run_metric_scope(book_id, workspace, edition_id, "CHAPTER", chapter_id)


@metrics_app.command("run-window")
def metrics_run_window_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    window_id: str = typer.Option("current", "--window-id"),
) -> None:
    """运行当前章节窗口的 Window 指标。"""
    _run_metric_scope(book_id, workspace, edition_id, "WINDOW", window_id)


@metrics_app.command("run-promise")
def metrics_run_promise_command(
    book_id: BookId = typer.Option(...),
    promise_id: str = typer.Option(..., "--promise-id"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """只运行指定 Promise 的 Narrative Debt。"""
    _run_metric_scope(book_id, workspace, edition_id, "PROMISE", promise_id)


@metrics_app.command("build-planning-aggregate")
def metrics_build_planning_aggregate_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    """冻结多个 scope Run 的引用与 hash，供 plan-next 使用。"""
    try:
        _emit(
            build_planning_aggregate(
                Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3"),
                book_id,
                edition_id=edition_id or "base",
            )
        )
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@metrics_app.command("disputes")
def metrics_disputes_command(
    book_id: BookId = typer.Option(...),
    scope_id: str = typer.Option(..., "--scope-id"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    scope_type: str = typer.Option("CHAPTER", "--scope-type"),
) -> None:
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    selected = edition_id or "base"
    database.initialize()
    with database.connect() as connection:
        keys = connection.execute(
            "SELECT DISTINCT metric_id, component_id FROM metric_observations "
            "WHERE book_id=? AND edition_id=? AND scope_type=? AND scope_id=?",
            (book_id, selected, scope_type.upper(), scope_id),
        ).fetchall()
    resolver = ObservationResolver(database)
    _emit(
        [
            {
                "metric_id": str(row["metric_id"]),
                "component_id": str(row["component_id"]),
                "resolution": resolver.resolve(
                    book_id,
                    selected,
                    scope_type.upper(),
                    scope_id,
                    str(row["metric_id"]),
                    str(row["component_id"]),
                ).model_dump(mode="json"),
            }
            for row in keys
            if resolver.resolve(
                book_id,
                selected,
                scope_type.upper(),
                scope_id,
                str(row["metric_id"]),
                str(row["component_id"]),
            ).status.value
            == "DISPUTED"
        ]
    )


@metrics_app.command("diagnose")
def metrics_diagnose_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    scope_type: str = typer.Option("CHAPTER", "--scope-type"),
    scope_id: Annotated[Optional[str], typer.Option("--scope-id")] = None,
) -> None:
    """显示一次新的 provenance-aware 指标诊断。"""
    metrics_rebuild_command(book_id, workspace, edition_id, scope_type, scope_id)


@metrics_app.command("show")
def metrics_show_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    scope_type: str = typer.Option("CHAPTER", "--scope-type"),
    scope_id: str = typer.Option(..., "--scope-id"),
) -> None:
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        selected = edition_id or "base"
        assembler = MetricsAssembler(database)
        _emit(assembler.latest(book_id, selected, scope_type, scope_id) or {"status": "NO_RUN"})
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@metrics_app.command("missing")
def metrics_missing_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    scope_id: Annotated[Optional[str], typer.Option("--scope-id")] = None,
) -> None:
    result = MetricsAssembler(Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")).rebuild(
        book_id, edition_id=edition_id, scope_type="CHAPTER", scope_id=scope_id
    )
    _emit({"run_id": result["run_id"], "missing": {
        item["metric_id"]: item["missing_components"] for item in result["results"] if item["missing_components"]
    }})


@metrics_app.command("history")
def metrics_history_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    limit: int = typer.Option(20, "--limit"),
) -> None:
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    database.initialize()
    selected = edition_id or "base"
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM metric_runs WHERE book_id=? AND edition_id=? ORDER BY created_at DESC LIMIT ?",
            (book_id, selected, limit),
        ).fetchall()
    _emit([dict(row) for row in rows])


@metrics_app.command("semantic-prepare")
def metrics_semantic_prepare_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    chapter_id: str = typer.Option(..., "--chapter-id"),
) -> None:
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    database.initialize()
    selected = edition_id or "base"
    with database.connect() as connection:
        row = connection.execute(
            "SELECT content_sha256 FROM chapters WHERE book_id=? AND chapter_id=?",
            (book_id, chapter_id),
        ).fetchone()
    if row is None:
        raise typer.BadParameter("chapter_id 不存在")
    registry = load_registry()
    _emit({
        "task_id": f"metric-semantic-{book_id}-{chapter_id}", "book_id": book_id,
        "edition_id": selected, "chapter_id": chapter_id,
        "content_sha256": str(row["content_sha256"]), "registry_hash": registry.registry_hash,
        "required_components": {
            metric_id: definition.required_components
            for metric_id, definition in registry.metrics.items()
            if any(kind.value == "SEMANTIC_ESTIMATE" for component in definition.components.values() for kind in component.allowed_source_kinds)
        },
    })


@metrics_app.command("semantic-import")
def metrics_semantic_import_command(
    book_id: BookId = typer.Option(...),
    input_path: Path = typer.Option(..., "--input"),
    workspace: Workspace = Path("workspace"),
) -> None:
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        output = MetricSemanticObservationsOutput.model_validate_json(input_path.read_text(encoding="utf-8"))
        _emit(import_semantic_output(database, output))
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@metrics_semantic_app.command("prepare")
def metrics_semantic_prepare_nested_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    chapter_id: str = typer.Option(..., "--chapter-id"),
) -> None:
    metrics_semantic_prepare_command(book_id, workspace, edition_id, chapter_id)


@metrics_semantic_app.command("import")
def metrics_semantic_import_nested_command(
    book_id: BookId = typer.Option(...),
    input_path: Path = typer.Option(..., "--input"),
    workspace: Workspace = Path("workspace"),
) -> None:
    metrics_semantic_import_command(book_id, input_path, workspace)


@observation_app.command("resolve")
def observation_resolve_command(
    book_id: BookId = typer.Option(...),
    metric_id: str = typer.Option(..., "--metric-id"),
    component_id: str = typer.Option(..., "--component-id"),
    scope_id: str = typer.Option(..., "--scope-id"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    scope_type: str = typer.Option("CHAPTER", "--scope-type"),
) -> None:
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(
            ObservationResolver(database)
            .resolve(
                book_id,
                edition_id or "base",
                scope_type.upper(),
                scope_id,
                metric_id,
                component_id,
            )
            .model_dump(mode="json")
        )
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@observation_app.command("retract")
def observation_retract_command(
    book_id: BookId = typer.Option(...),
    observation_id: str = typer.Option(..., "--observation-id"),
    scope_id: str = typer.Option(..., "--scope-id"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    scope_type: str = typer.Option("CHAPTER", "--scope-type"),
    reason: str = typer.Option("作者撤回", "--reason"),
    expected_active_observation_id: Annotated[
        Optional[str], typer.Option("--expected-active-observation-id")
    ] = None,
) -> None:
    database = Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")
    try:
        _emit(
            AuthorMetricInputService(database).retract(
                observation_id,
                book_id=book_id,
                edition_id=edition_id or "base",
                scope_type=scope_type.upper(),
                scope_id=scope_id,
                reason=reason,
                expected_active_observation_id=expected_active_observation_id,
            )
        )
    except (MetricConflictError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@segments_app.command("rebuild")
def segments_rebuild_command(
    book_id: BookId = typer.Option(...), workspace: Workspace = Path("workspace"), edition_id: EditionId = None
) -> None:
    try:
        _emit(rebuild_segments(Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3"), book_id, edition_id=edition_id))
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@segments_app.command("show")
def segments_show_command(
    book_id: BookId = typer.Option(...), workspace: Workspace = Path("workspace"), edition_id: EditionId = None,
    chapter_id: Annotated[Optional[str], typer.Option("--chapter-id")] = None,
) -> None:
    _emit(list_segments(Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3"), book_id, edition_id=edition_id, chapter_id=chapter_id))


def _book_database(
    workspace: Path,
    book_id: str,
    library_root: Path | None = None,
) -> Database:
    if library_root is not None:
        return Database(BookLayout(library_root).for_book(book_id).database)
    return Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3")


@atlas_app.command("show")
def atlas_show_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    try:
        database = _book_database(workspace, book_id, library_root)
        selected = edition_id or "base"
        _emit(get_atlas_overview(database, book_id, selected))
    except (AtlasError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@atlas_app.command("register")
def atlas_register_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    artifact_root: Annotated[Optional[Path], typer.Option("--artifact-root")] = None,
    allow_gaps: bool = typer.Option(True, "--allow-gaps/--require-ready"),
    library_root: LibraryRoot = None,
) -> None:
    """验证并登记一个不可变 Story Atlas 版本；不会写入 Canon。"""
    try:
        _emit(
            register_atlas(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id or "base",
                root=artifact_root,
                allow_gaps=allow_gaps,
            )
        )
    except (AtlasError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@atlas_app.command("validate")
def atlas_validate_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    try:
        result = validate_atlas(
            _book_database(workspace, book_id, library_root), book_id, edition_id or "base"
        )
        _emit(result.model_dump(mode="json"))
        if not result.ok:
            raise typer.Exit(code=3)
    except (AtlasError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@atlas_app.command("render")
def atlas_render_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    artifact_root: Annotated[Optional[Path], typer.Option("--artifact-root")] = None,
    library_root: LibraryRoot = None,
) -> None:
    """离线渲染七张 SVG Atlas 图；不使用网络或图片 API。"""
    try:
        database = _book_database(workspace, book_id, library_root)
        root = (artifact_root or atlas_root(database, book_id, edition_id or "base")).resolve()
        _emit({"artifact_root": str(root), "visuals": render_atlas_visuals(root)})
    except (AtlasError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@atlas_app.command("visuals")
def atlas_visuals_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    artifact_root: Annotated[Optional[Path], typer.Option("--artifact-root")] = None,
    library_root: LibraryRoot = None,
) -> None:
    """render 的明确别名。"""
    atlas_render_command(book_id, workspace, edition_id, artifact_root, library_root)


@atlas_app.command("export-snapshot")
def atlas_export_snapshot_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    output_root: Annotated[Optional[Path], typer.Option("--output-root")] = None,
    library_root: LibraryRoot = None,
) -> None:
    """导出无需服务器、可直接打开的本地 HTML 作者工作台。"""
    try:
        _emit(
            export_snapshot(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id=edition_id,
                output_root=output_root,
            )
        )
    except (AtlasError, ValueError, OSError, InitializationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@initialize_app.command("create")
def initialize_create_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
    char_limit: int = typer.Option(80_000, "--char-limit"),
    max_chapters_per_arc: int = typer.Option(20, "--max-chapters-per-arc"),
) -> None:
    try:
        _emit(
            create_initialization(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id=edition_id,
                char_limit=char_limit,
                max_chapters_per_arc=max_chapters_per_arc,
            )
        )
    except (InitializationError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@initialize_app.command("status")
def initialize_status_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
    initialization_id: Annotated[Optional[str], typer.Option("--initialization-id")] = None,
) -> None:
    try:
        _emit(
            latest_initialization(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id,
                initialization_id,
            )
        )
    except (InitializationError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@initialize_app.command("refresh")
def initialize_refresh_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
    initialization_id: Annotated[Optional[str], typer.Option("--initialization-id")] = None,
) -> None:
    try:
        _emit(
            refresh_initialization(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id=edition_id,
                initialization_id=initialization_id,
            )
        )
    except (InitializationError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@initialize_metrics_app.command("prepare")
def initialize_metrics_prepare_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
    initialization_id: str = typer.Option(..., "--initialization-id"),
    recent_detailed_window: int = typer.Option(50, "--recent-detailed-window"),
) -> None:
    """生成冻结 hash、逐章 JSONL 和严格 Metric Bootstrap Manifest。"""
    try:
        _emit(
            prepare_metric_bootstrap(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id=edition_id,
                initialization_id=initialization_id,
                recent_detailed_window=recent_detailed_window,
            )
        )
    except (InitializationError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@initialize_metrics_app.command("import")
def initialize_metrics_import_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
    initialization_id: str = typer.Option(..., "--initialization-id"),
    input_path: Annotated[Optional[Path], typer.Option("--input")] = None,
) -> None:
    """校验并幂等导入逐章 Semantic Metric Observation JSONL。"""
    try:
        _emit(
            import_metric_bootstrap(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id=edition_id,
                initialization_id=initialization_id,
                input_path=input_path,
            )
        )
    except (InitializationError, ValueError, OSError, MetricConflictError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@initialize_metrics_app.command("status")
def initialize_metrics_status_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
    initialization_id: str = typer.Option(..., "--initialization-id"),
) -> None:
    """审计 Manifest、Import Report、Observation、Evidence 和最新 Metric Run。"""
    try:
        _emit(
            metric_bootstrap_status(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id=edition_id,
                initialization_id=initialization_id,
            )
        )
    except (InitializationError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@initialize_metrics_app.command("rebuild")
def initialize_metrics_rebuild_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
    initialization_id: str = typer.Option(..., "--initialization-id"),
) -> None:
    """从当前初始化 Observation Ledger 重建章节 Metric Run。"""
    try:
        _emit(
            rebuild_initialization_metric_runs(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id=edition_id,
                initialization_id=initialization_id,
            )
        )
    except (InitializationError, ValueError, OSError, MetricConflictError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@atlas_app.command("history")
def atlas_history_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    _emit(
        list_atlas_history(
            _book_database(workspace, book_id, library_root), book_id, edition_id or "base"
        )
    )


@atlas_app.command("action")
def atlas_action_command(
    book_id: BookId = typer.Option(...),
    action_type: str = typer.Option(..., "--action-type"),
    target_id: Optional[str] = typer.Option(None, "--target-id"),
    payload_json: str = typer.Option("{}", "--payload-json"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    try:
        payload = json.loads(payload_json)
        action = AtlasAction.model_validate(
            {"action_type": action_type, "target_id": target_id, "payload": payload}
        )
        _emit(
            record_atlas_action(
                _book_database(workspace, book_id, library_root),
                book_id,
                edition_id or "base",
                action,
            )
        )
    except (AtlasError, ValueError, OSError, json.JSONDecodeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@batch_app.command("create")
def batch_create_command(
    book_id: BookId = typer.Option(...),
    target_chapter_count: int = typer.Option(..., "--target-chapters"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    atlas_id: Optional[str] = typer.Option(None, "--atlas-id"),
    chunk_size: int = typer.Option(5, "--chunk-size"),
    checkpoint_interval: int = typer.Option(10, "--checkpoint-interval"),
) -> None:
    try:
        _emit(
            create_batch(
                _book_database(workspace, book_id),
                book_id,
                target_chapter_count=target_chapter_count,
                edition_id=edition_id,
                atlas_id=atlas_id,
                chunk_size=chunk_size,
                checkpoint_interval=checkpoint_interval,
            )
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@batch_app.command("show")
def batch_show_command(
    batch_id: str = typer.Option(..., "--batch-id"),
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    library_root: LibraryRoot = None,
) -> None:
    database = _book_database(workspace, book_id, library_root)
    _emit({"projection": get_batch_projection(database, batch_id).model_dump(mode="json"), "plan": get_batch_plan(database, batch_id).model_dump(mode="json")})


@batch_app.command("chunk-context")
def batch_chunk_context_command(
    batch_id: str = typer.Option(..., "--batch-id"),
    chunk_order: int = typer.Option(..., "--chunk-order"),
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    library_root: LibraryRoot = None,
) -> None:
    _emit(
        get_chunk_context(
            _book_database(workspace, book_id, library_root), batch_id, chunk_order
        )
    )


@batch_app.command("complete-chunk")
def batch_complete_chunk_command(
    batch_id: str = typer.Option(..., "--batch-id"),
    chunk_order: int = typer.Option(..., "--chunk-order"),
    provisional_state_file: Path = typer.Option(..., "--provisional-state-file"),
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    library_root: LibraryRoot = None,
    validator_summary_file: Optional[Path] = typer.Option(None, "--validator-summary-file"),
    atlas_refresh_required: bool = typer.Option(False, "--atlas-refresh-required"),
) -> None:
    try:
        state = json.loads(provisional_state_file.read_text(encoding="utf-8"))
        summary = (
            {}
            if validator_summary_file is None
            else json.loads(validator_summary_file.read_text(encoding="utf-8"))
        )
        _emit(
            complete_chunk(
                _book_database(workspace, book_id, library_root),
                batch_id,
                chunk_order,
                provisional_state=state,
                validator_summary=summary,
                atlas_refresh_required=atlas_refresh_required,
            )
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@batch_app.command("checkpoint")
def batch_checkpoint_command(
    batch_id: str = typer.Option(..., "--batch-id"),
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    library_root: LibraryRoot = None,
) -> None:
    _emit(create_checkpoint(_book_database(workspace, book_id, library_root), batch_id))


@workflow_app.command("continuation")
def workflow_continuation_command(
    book_id: BookId = typer.Option(...), requested_stage: str = typer.Option("DRAFT_AND_VALIDATE", "--stage"),
    workspace: Workspace = Path("workspace"), edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    try:
        _emit(create_continuation_handoff(_book_database(workspace, book_id, library_root), book_id, edition_id=edition_id, requested_stage=requested_stage))
    except (HandoffWorkflowError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True); raise typer.Exit(code=3) from exc


@workflow_app.command("revision")
def workflow_revision_command(
    book_id: BookId = typer.Option(...), requested_stage: str = typer.Option("DRAFT_SELECTED_UNITS", "--stage"),
    workspace: Workspace = Path("workspace"), edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    try:
        _emit(create_revision_handoff(_book_database(workspace, book_id, library_root), book_id, edition_id=edition_id, requested_stage=requested_stage))
    except (HandoffWorkflowError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True); raise typer.Exit(code=3) from exc


@workflow_app.command("atlas-bootstrap")
def workflow_atlas_bootstrap_command(
    book_id: BookId = typer.Option(...),
    requested_stage: str = typer.Option("ATLAS_BOOTSTRAP", "--stage"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
) -> None:
    try:
        _emit(
            create_story_atlas_handoff(
                Database(workspace.resolve() / safe_book_id(book_id) / "state.sqlite3"),
                book_id,
                requested_stage=requested_stage,
                edition_id=edition_id,
            )
        )
    except (HandoffWorkflowError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@workflow_app.command("initialize")
def workflow_initialize_command(
    book_id: BookId = typer.Option(...),
    requested_stage: str = typer.Option("NOVEL_INITIALIZATION", "--stage"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    """创建已有长篇 Atlas-first 初始化 handoff，不预先创建 Planning Aggregate。"""
    try:
        _emit(
            create_initialization_handoff(
                _book_database(workspace, book_id, library_root),
                book_id,
                requested_stage=requested_stage,
                edition_id=edition_id,
            )
        )
    except (HandoffWorkflowError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@workflow_app.command("atlas-refresh")
def workflow_atlas_refresh_command(
    book_id: BookId = typer.Option(...),
    requested_stage: str = typer.Option("ATLAS_REFRESH", "--stage"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    try:
        _emit(
            create_story_atlas_handoff(
                _book_database(workspace, book_id, library_root),
                book_id,
                handoff_type=HandoffType.STORY_ATLAS_REFRESH,
                requested_stage=requested_stage,
                edition_id=edition_id,
            )
        )
    except (HandoffWorkflowError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@workflow_app.command("world-model-review")
def workflow_world_model_review_command(
    book_id: BookId = typer.Option(...),
    requested_stage: str = typer.Option("WORLD_MODEL_REVIEW", "--stage"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    try:
        _emit(
            create_story_atlas_handoff(
                _book_database(workspace, book_id, library_root),
                book_id,
                handoff_type=HandoffType.WORLD_MODEL_REVIEW,
                requested_stage=requested_stage,
                edition_id=edition_id,
            )
        )
    except (HandoffWorkflowError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@workflow_app.command("batch")
def workflow_batch_command(
    book_id: BookId = typer.Option(...),
    batch_id: str = typer.Option(..., "--batch-id"),
    requested_stage: str = typer.Option("BATCH_CONTINUATION", "--stage"),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    try:
        _emit(
            create_batch_continuation_handoff(
                _book_database(workspace, book_id, library_root),
                book_id,
                batch_id=batch_id,
                requested_stage=requested_stage,
                edition_id=edition_id,
            )
        )
    except (HandoffWorkflowError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@workflow_app.command("show")
def workflow_show_command(
    handoff_id: str = typer.Option(..., "--handoff-id"),
    workspace: Workspace = Path("workspace"),
    book_id: BookId = typer.Option(...),
    library_root: LibraryRoot = None,
) -> None:
    _emit(get_handoff(_book_database(workspace, book_id, library_root), handoff_id))


@workflow_app.command("jobs")
def workflow_handoffs_command(
    book_id: BookId = typer.Option(...), workspace: Workspace = Path("workspace"), edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    database = _book_database(workspace, book_id, library_root)
    database.initialize()
    with database.connect() as connection:
        sql = "SELECT * FROM workflow_handoffs WHERE book_id=?"
        params: list[object] = [book_id]
        if edition_id:
            sql += " AND edition_id=?"; params.append(edition_id)
        sql += " ORDER BY created_at DESC"
        _emit([dict(row) for row in connection.execute(sql, tuple(params)).fetchall()])


@workflow_app.command("list")
def workflow_list_command(
    book_id: BookId = typer.Option(...),
    workspace: Workspace = Path("workspace"),
    edition_id: EditionId = None,
    library_root: LibraryRoot = None,
) -> None:
    """jobs 的明确命名别名。"""
    workflow_handoffs_command(book_id, workspace, edition_id, library_root)


@workflow_app.command("claim")
def workflow_claim_command(
    handoff_id: str = typer.Option(..., "--handoff-id"),
    claimed_by: str = typer.Option(..., "--claimed-by"),
    workspace: Workspace = Path("workspace"),
    book_id: BookId = typer.Option(...),
    library_root: LibraryRoot = None,
) -> None:
    _emit(claim_handoff(_book_database(workspace, book_id, library_root), handoff_id, claimed_by))


@workflow_app.command("cancel")
def workflow_cancel_command(
    handoff_id: str = typer.Option(..., "--handoff-id"),
    workspace: Workspace = Path("workspace"),
    book_id: BookId = typer.Option(...),
    library_root: LibraryRoot = None,
) -> None:
    _emit(cancel_handoff(_book_database(workspace, book_id, library_root), handoff_id))


@workflow_app.command("stale")
def workflow_stale_command(
    handoff_id: str = typer.Option(..., "--handoff-id"),
    workspace: Workspace = Path("workspace"),
    book_id: BookId = typer.Option(...),
    library_root: LibraryRoot = None,
) -> None:
    _emit(mark_stale(_book_database(workspace, book_id, library_root), handoff_id))


@workflow_app.command("mark-stale")
def workflow_mark_stale_command(
    handoff_id: str = typer.Option(..., "--handoff-id"),
    workspace: Workspace = Path("workspace"),
    book_id: BookId = typer.Option(...),
    library_root: LibraryRoot = None,
) -> None:
    workflow_stale_command(handoff_id, workspace, book_id, library_root)


@workflow_app.command("validate-result")
def workflow_validate_result_command(
    handoff_id: str = typer.Option(..., "--handoff-id"),
    workspace: Workspace = Path("workspace"),
    book_id: BookId = typer.Option(...),
    library_root: LibraryRoot = None,
) -> None:
    try:
        _emit(
            validate_result_file(
                _book_database(workspace, book_id, library_root),
                handoff_id,
            )
        )
    except (HandoffWorkflowError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@workflow_app.command("update")
def workflow_update_command(
    handoff_id: str = typer.Option(..., "--handoff-id"),
    status: HandoffStatus = typer.Option(..., "--status"),
    claim_token: str = typer.Option(..., "--claim-token"),
    workspace: Workspace = Path("workspace"),
    book_id: BookId = typer.Option(...),
    library_root: LibraryRoot = None,
) -> None:
    _emit(
        update_handoff_status(
            _book_database(workspace, book_id, library_root),
            handoff_id,
            status,
            claim_token=claim_token,
        )
    )


@web_app.command("doctor")
def web_doctor_command() -> None:
    try:
        import fastapi  # noqa: F401
        import jinja2  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError as exc:
        _emit({"ok": False, "error": str(exc), "install": "pip install -e '.[web]'"})
        raise typer.Exit(code=3) from exc
    _emit({"ok": True, "executor": "Windows Codex desktop client", "bind_default": "127.0.0.1"})


@demo_app.command("seed-author-workbench")
def demo_seed_author_workbench_command(
    workspace: Workspace = Path("workspace"),
) -> None:
    """生成完全合成的 Author Workbench 端到端演示项目。"""
    try:
        _emit(seed_author_workbench(workspace.resolve()))
    except (ValueError, OSError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc


@web_app.command("serve")
def web_serve_command(
    book_id: BookId = typer.Option(...), workspace: Workspace = Path("workspace"),
    host: str = typer.Option("127.0.0.1", "--host"), port: int = typer.Option(8765, "--port"),
    allow_remote: bool = typer.Option(False, "--allow-remote"),
    library_root: LibraryRoot = None,
) -> None:
    try:
        from novel_authoring.web.app import serve

        serve(
            _book_database(workspace, book_id, library_root),
            host=host,
            port=port,
            allow_remote=allow_remote,
            book_id=book_id,
            library_root=library_root,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        typer.echo(str(exc), err=True); raise typer.Exit(code=3) from exc


if __name__ == "__main__":
    app()
