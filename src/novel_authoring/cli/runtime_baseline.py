"""CLI for the source-derived Runtime Baseline and Earned Surface."""

# Typer options follow the project's CLI compatibility policy.
# ruff: noqa: B008

from __future__ import annotations

from pathlib import Path

import typer

from novel_authoring.cli.legacy import LibraryRoot, _book_database, _emit, app
from novel_authoring.runtime_baseline import (
    RuntimeBaselineError,
    RuntimeHydrationError,
    build_runtime_baseline,
    discover_runtime_recall_candidates,
    hydrate_runtime_baseline,
    latest_runtime_baseline,
    load_earned_surface,
)

runtime_baseline_app = typer.Typer(help="Source-Derived Runtime Baseline 与 Earned Surface")
app.add_typer(runtime_baseline_app, name="runtime-baseline")


@runtime_baseline_app.command("build")
def runtime_baseline_build_command(
    book_id: str = typer.Option(..., "--book-id"),
    input_path: Path | None = typer.Option(None, "--input", exists=True, file_okay=True),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    boundary_chapter: int | None = typer.Option(None, "--boundary-chapter", min=0),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    library_root: LibraryRoot = None,
) -> None:
    """验证 Codex/source review input 并发布独立 Baseline 版本。"""

    try:
        result = build_runtime_baseline(
            _book_database(workspace, book_id, library_root),
            book_id,
            input_path=input_path,
            edition_id=edition_id,
            boundary_chapter=boundary_chapter,
        )
    except (RuntimeBaselineError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


@runtime_baseline_app.command("status")
def runtime_baseline_status_command(
    book_id: str = typer.Option(..., "--book-id"),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    library_root: LibraryRoot = None,
) -> None:
    """查看当前 Baseline 与 Earned Surface 摘要。"""

    try:
        database = _book_database(workspace, book_id, library_root)
        baseline = latest_runtime_baseline(database, book_id, edition_id=edition_id)
        earned = load_earned_surface(database, book_id, edition_id=edition_id)
    except (RuntimeBaselineError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(
        {
            "book_id": book_id,
            "edition_id": None if baseline is None else baseline.manifest.edition_id,
            "baseline_id": None if baseline is None else baseline.manifest.baseline_id,
            "boundary_chapter": None
            if baseline is None
            else baseline.manifest.boundary_chapter,
            "entry_counts": None if baseline is None else baseline.manifest.entry_counts,
            "earned_surface": None
            if earned is None
            else {
                "surface_id": earned.surface_id,
                "capabilities": len(earned.earned_capabilities),
                "items": len(earned.available_items),
                "resources": len(earned.available_resources),
                "payoffs": len(earned.available_payoffs),
                "hard_unknowns": len(earned.hard_unknowns),
            },
        }
    )


@runtime_baseline_app.command("inspect")
def runtime_baseline_inspect_command(
    book_id: str = typer.Option(..., "--book-id"),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    library_root: LibraryRoot = None,
) -> None:
    """打印 Baseline、Earned Surface 和 Hard Unknowns 的可读摘要。"""

    database = _book_database(workspace, book_id, library_root)
    try:
        baseline = latest_runtime_baseline(database, book_id, edition_id=edition_id)
        earned = load_earned_surface(database, book_id, edition_id=edition_id)
    except (RuntimeBaselineError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    if baseline is None or earned is None:
        typer.echo("Runtime Baseline: NONE")
        return
    typer.echo(
        "\n".join(
            [
                f"Baseline: {baseline.manifest.baseline_id}",
                f"Edition: {baseline.manifest.edition_id}",
                f"Boundary chapter: {baseline.manifest.boundary_chapter}",
                f"Earned capabilities: {len(earned.earned_capabilities)}",
                f"Available items: {len(earned.available_items)}",
                f"Available resources: {len(earned.available_resources)}",
                f"Available payoffs: {len(earned.available_payoffs)}",
                f"Hard unknowns: {len(earned.hard_unknowns)}",
            ]
        )
    )


@runtime_baseline_app.command("recall")
def runtime_baseline_recall_command(
    book_id: str = typer.Option(..., "--book-id"),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    limit: int = typer.Option(24, "--limit", min=1),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    library_root: LibraryRoot = None,
) -> None:
    """列出 Distill 发现但尚未进入 Runtime Baseline 的 recall-only 线索。"""

    try:
        database = _book_database(workspace, book_id, library_root)
        candidates = discover_runtime_recall_candidates(
            database,
            book_id,
            edition_id=edition_id,
            limit=limit,
        )
    except (RuntimeBaselineError, RuntimeHydrationError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit({"book_id": book_id, "edition_id": edition_id, "recall_candidates": [
        item.model_dump(mode="json") for item in candidates
    ]})


@runtime_baseline_app.command("hydrate")
def runtime_baseline_hydrate_command(
    book_id: str = typer.Option(..., "--book-id"),
    input_path: Path = typer.Option(..., "--input", exists=True, file_okay=True),
    edition_id: str | None = typer.Option(None, "--edition-id"),
    boundary_chapter: int | None = typer.Option(None, "--boundary-chapter", min=0),
    workspace: Path = typer.Option(Path("workspace"), "--workspace"),
    library_root: LibraryRoot = None,
) -> None:
    """消费经过 Source/作者复核的 input，发布新的 Baseline version。"""

    try:
        result = hydrate_runtime_baseline(
            _book_database(workspace, book_id, library_root),
            book_id,
            input_path,
            edition_id=edition_id,
            boundary_chapter=boundary_chapter,
        )
    except (RuntimeBaselineError, RuntimeHydrationError, OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    _emit(result)


__all__ = ["runtime_baseline_app"]
