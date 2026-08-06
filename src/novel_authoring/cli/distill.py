"""CLI commands for the distill-novels handoff workflow."""

# Typer options are intentionally declared in function defaults, matching the
# frozen legacy CLI and the project's Typer compatibility policy.
# ruff: noqa: B008

from __future__ import annotations

import json
from pathlib import Path

import typer

from novel_authoring.cli.legacy import LibraryRoot, _book_database, _emit, app
from novel_authoring.distill.package import (
    DistillationPackageError,
    build_distillation_package,
    validate_distillation_package,
)
from novel_authoring.distill.preparation import DistillPreparationError, prepare_sources
from novel_authoring.distill.service import (
    DistillError,
    _book_edition,
    create_distill_handoff,
    import_distill_result,
    latest_distill_reference,
    latest_preparation,
    prepare_book_sources,
)
from novel_authoring.utils import json_dumps

distill_app = typer.Typer(help="distill-novels 知识库准备、Codex handoff 与发布")
app.add_typer(distill_app, name="distill")


@distill_app.command("prepare")
def distill_prepare_command(
    source: list[Path] = typer.Option(
        [],
        "--source",
        exists=True,
        file_okay=True,
        dir_okay=True,
        help="TXT/Markdown/HTML/EPUB/DOCX/RTF 文件或目录，可重复指定",
    ),
    output: Path | None = typer.Option(None, "--output", help="脱离 Book Library 时的准备目录"),
    book_id: str | None = typer.Option(None, "--book-id"),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    library_root: LibraryRoot = None,
) -> None:
    """建立确定性 normalized source、章节索引和 manifest。"""

    try:
        if book_id is not None:
            if output is not None:
                raise DistillError("指定 --book-id 时由 BookLayout 管理输出，不要同时指定 --output")
            database = _book_database(Path("workspace"), book_id, library_root)
            result = prepare_book_sources(
                database,
                book_id,
                sources=source or None,
                edition_id=edition_id,
            )
        else:
            if output is None or not source:
                raise DistillError("脱离书库运行时必须同时指定 --source 和 --output")
            result = prepare_sources(source, output)
    except (DistillError, DistillPreparationError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    _emit(result)


@distill_app.command("create")
def distill_create_command(
    book_id: str = typer.Option(..., "--book-id"),
    mode: str = typer.Option("create", "--mode"),
    dimensions: str = typer.Option("all", "--dimensions"),
    depth: str = typer.Option("standard", "--depth"),
    requested_stage: str = typer.Option("DISTILL", "--stage"),
    source: list[Path] = typer.Option(
        [],
        "--source",
        exists=True,
        file_okay=True,
        dir_okay=True,
        help="直接准备参考来源；省略时使用最近一次 preparation",
    ),
    preparation_id: str | None = typer.Option(None, "--preparation-id"),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    library_root: LibraryRoot = None,
) -> None:
    """冻结 distill 输入并创建 READY_FOR_CODEX handoff。"""

    try:
        result = create_distill_handoff(
            _book_database(workspace, book_id, library_root),
            book_id,
            sources=source or None,
            preparation_id=preparation_id,
            mode=mode.strip().lower(),
            dimensions=dimensions,
            depth=depth.strip().lower(),
            requested_stage=requested_stage,
            edition_id=edition_id,
        )
    except (DistillError, DistillPreparationError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@distill_app.command("import")
def distill_import_command(
    handoff_id: str = typer.Option(..., "--handoff-id"),
    book_id: str = typer.Option(..., "--book-id"),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    library_root: LibraryRoot = None,
) -> None:
    """校验已完成 handoff，并把 skill 发布到 edition.analysis/distill。"""

    try:
        result = import_distill_result(
            _book_database(workspace, book_id, library_root), book_id, handoff_id
        )
    except (DistillError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@distill_app.command("status")
def distill_status_command(
    book_id: str = typer.Option(..., "--book-id"),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    library_root: LibraryRoot = None,
) -> None:
    """查看最近一次 preparation 与已发布的 reference skill。"""

    database = _book_database(workspace, book_id, library_root)
    try:
        preparation = latest_preparation(database, book_id, edition_id=edition_id)
    except DistillError:
        preparation = None
    from novel_authoring.distill.service import _book_edition

    edition = _book_edition(database, book_id, edition_id)
    _emit(
        {
            "book_id": book_id,
            "edition_id": edition.edition_id,
            "preparation": preparation,
            "published": latest_distill_reference(edition),
        }
    )


@distill_app.command("validate")
def distill_validate_command(
    book_id: str = typer.Option(..., "--book-id"),
    handoff_id: str | None = typer.Option(None, "--handoff-id"),
    distill_id: str | None = typer.Option(None, "--distill-id"),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    library_root: LibraryRoot = None,
) -> None:
    """严格检查 selected dimensions、package、provenance 和 mapping。"""

    database = _book_database(workspace, book_id, library_root)
    try:
        edition = _book_edition(database, book_id, edition_id)
        if handoff_id:
            from novel_authoring.workflows.handoffs import validate_result_file

            result = validate_result_file(database, handoff_id)
            with database.connect() as connection:
                row = connection.execute(
                    "SELECT task_directory FROM workflow_handoffs WHERE handoff_id=?",
                    (handoff_id,),
                ).fetchone()
            if row is None:
                raise DistillError(f"distill handoff 不存在：{handoff_id}")
            task_directory = Path(str(row["task_directory"])).resolve()
            task_path = task_directory / "input" / "task.json"
            if not task_path.is_file():
                task_path = task_directory / "task.json"
            task = json.loads(task_path.read_text(encoding="utf-8"))
            request = task["distill"]
            root = Path(str(result["distill_skill_root"]))
            if not root.is_absolute():
                root = (task_directory / root).resolve()
            build_distillation_package(database, book_id, edition.edition_id, request, root)
            summary = validate_distillation_package(
                root,
                expected_book_id=book_id,
                expected_edition_id=edition.edition_id,
                expected_scope=str(request.get("scope")),
                expected_dimensions=[str(item) for item in request["dimensions"]],
            )
            summary.update({"handoff_id": handoff_id, "package_root": str(root / "machine")})
        else:
            reference = latest_distill_reference(edition)
            if reference is None:
                raise DistillError("当前 edition 没有已发布 Distillation Package")
            if distill_id and str(reference["distill_id"]) != distill_id:
                root = edition.distill / "skills" / distill_id
                manifest_path = root / "distill_manifest.json"
                if not manifest_path.is_file():
                    raise DistillError(f"distill 不存在：{distill_id}")
                selected_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(selected_manifest, dict):
                    raise DistillError(f"distill manifest 无效：{distill_id}")
                expected_scope = str(
                    selected_manifest.get("scope") or reference["scope"]
                )
                expected_dimensions = [
                    str(item)
                    for item in selected_manifest.get("dimensions", reference["dimensions"])
                ]
                expected_edition_id = str(
                    selected_manifest.get("edition_id") or edition.edition_id
                )
            else:
                root = Path(str(reference["skill_root"]))
                manifest_path = root / "distill_manifest.json"
                expected_scope = str(reference["scope"])
                expected_dimensions = [
                    str(item) for item in reference["dimensions"]
                ]
                expected_edition_id = edition.edition_id
            summary = validate_distillation_package(
                root,
                expected_book_id=book_id,
                expected_edition_id=expected_edition_id,
                expected_scope=expected_scope,
                expected_dimensions=expected_dimensions,
            )
            summary["distill_id"] = distill_id or reference["distill_id"]
            summary["package_root"] = str(root / "machine")
    except (DistillError, DistillationPackageError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(summary)


@distill_app.command("map-evidence")
def distill_map_evidence_command(
    book_id: str = typer.Option(..., "--book-id"),
    distill_id: str | None = typer.Option(None, "--distill-id"),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    library_root: LibraryRoot = None,
) -> None:
    """使用冻结 preparation 重新执行 Evidence Mapping，不调用 Codex。"""

    database = _book_database(workspace, book_id, library_root)
    try:
        edition = _book_edition(database, book_id, edition_id)
        reference = latest_distill_reference(edition)
        if reference is None:
            raise DistillError("当前 edition 没有已发布 Distillation Package")
        selected_id = distill_id or str(reference["distill_id"])
        root = edition.distill / "skills" / selected_id
        manifest_path = root / "distill_manifest.json"
        if not manifest_path.is_file():
            raise DistillError(f"distill 不存在：{selected_id}")
        published = json.loads(manifest_path.read_text(encoding="utf-8"))
        request = published.get("request")
        if not isinstance(request, dict):
            raise DistillError("published distill manifest 缺少 request")
        if not request.get("scope"):
            request["scope"] = published.get("scope") or "EXTERNAL_REFERENCE"
        build_distillation_package(database, book_id, edition.edition_id, request, root)
        summary = validate_distillation_package(
            root,
            expected_book_id=book_id,
            expected_edition_id=edition.edition_id,
            expected_scope=str(request["scope"]),
            expected_dimensions=[str(item) for item in request.get("dimensions", [])],
        )
        published["mapping_summary"] = summary["mapping_summary"]
        published["package_summary"] = summary
        manifest_path.write_text(json_dumps(published, indent=2) + "\n", encoding="utf-8")
        latest_path = edition.distill / "latest.json"
        if latest_path.is_file():
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            if isinstance(latest, dict) and str(latest.get("distill_id")) == selected_id:
                latest["mapping_summary"] = summary["mapping_summary"]
                latest_path.write_text(
                    json_dumps(latest, indent=2) + "\n", encoding="utf-8"
                )
        summary.update({"distill_id": selected_id, "package_root": str(root / "machine")})
    except (DistillError, DistillationPackageError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(summary)


@distill_app.command("inspect")
def distill_inspect_command(
    book_id: str = typer.Option(..., "--book-id"),
    distill_id: str | None = typer.Option(None, "--distill-id"),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    library_root: LibraryRoot = None,
) -> None:
    """打印 Distillation Package 的作者可读摘要。"""

    database = _book_database(workspace, book_id, library_root)
    try:
        edition = _book_edition(database, book_id, edition_id)
        reference = latest_distill_reference(edition)
        if reference is None:
            raise DistillError("当前 edition 没有已发布 Distillation Package")
        selected_id = distill_id or str(reference["distill_id"])
        root = edition.distill / "skills" / selected_id
        manifest_path = root / "distill_manifest.json"
        if not manifest_path.is_file():
            raise DistillError(f"distill 不存在：{selected_id}")
        selected_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(selected_manifest, dict):
            raise DistillError(f"distill manifest 无效：{selected_id}")
        summary = validate_distillation_package(
            root,
            expected_book_id=book_id,
            expected_edition_id=str(
                selected_manifest.get("edition_id") or edition.edition_id
            ),
            expected_scope=str(
                selected_manifest.get("scope") or reference["scope"]
            ),
            expected_dimensions=[
                str(item)
                for item in selected_manifest.get("dimensions", reference["dimensions"])
            ],
        )
    except (DistillError, DistillationPackageError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    mapping = summary["mapping_summary"]
    typer.echo(
        "\n".join(
            [
                f"Distill Scope: {summary['scope']}",
                f"Dimensions: {', '.join(summary['selected_dimensions'])}",
                f"Literary Arcs: {summary['literary_arc_count']}",
                f"Continuity Warnings: {summary['continuity_candidate_count']}",
                f"Unmapped Evidence: {summary['unmapped_count']}",
                f"Conflicting Evidence: {summary['conflicting_count']}",
                f"Available Craft Controls: {summary['craft_control_count']}",
                f"Mapping: {mapping}",
            ]
        )
    )


__all__ = ["distill_app"]
