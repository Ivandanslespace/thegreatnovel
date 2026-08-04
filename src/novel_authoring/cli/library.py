"""Book Library CLI commands added after the legacy CLI freeze."""

from pathlib import Path

import typer

from novel_authoring.cli.legacy import LibraryRoot, _emit, library_app
from novel_authoring.storage.library import LibraryAddOptions, add_book


@library_app.command("add")
def library_add_command(
    source: Path = typer.Option(..., "--source", exists=True, file_okay=True, dir_okay=True),  # noqa: B008
    book_id: str = typer.Option(..., "--book-id"),
    title: str | None = typer.Option(None, "--title"),
    library_root: LibraryRoot = None,
    confirm_order: bool = typer.Option(False, "--confirm-order"),
    initialize_mode: str = typer.Option("deferred", "--initialize-mode"),
) -> None:
    """一步建立 canonical 书库、SQLite/FTS、章节和 Source Spans。"""

    try:
        result = add_book(
            LibraryAddOptions(
                book_id=book_id,
                title=title,
                source=source,
                library_root=library_root,
                confirm_order=confirm_order,
                initialize_mode=initialize_mode,
            )
        )
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    _emit(result.to_dict())


__all__ = ["library_add_command"]
