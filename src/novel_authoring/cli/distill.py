"""CLI commands for the distill-novels handoff workflow."""

# Typer options are intentionally declared in function defaults, matching the
# frozen legacy CLI and the project's Typer compatibility policy.
# ruff: noqa: B008

from __future__ import annotations

from pathlib import Path

import typer

from novel_authoring.cli.legacy import LibraryRoot, _book_database, _emit, app
from novel_authoring.distill.preparation import DistillPreparationError, prepare_sources
from novel_authoring.distill.service import (
    DistillError,
    create_distill_handoff,
    import_distill_result,
    latest_distill_reference,
    latest_preparation,
    prepare_book_sources,
)

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


__all__ = ["distill_app"]
