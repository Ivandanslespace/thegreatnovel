"""Public Typer application entry point."""

# Importing the module registers the new Book Library command on the frozen
# Typer group without adding more commands to the legacy facade.
from novel_authoring.cli import distill as _distill  # noqa: F401,E402
from novel_authoring.cli import library as _library  # noqa: F401,E402
from novel_authoring.cli import runtime_baseline as _runtime_baseline  # noqa: F401,E402
from novel_authoring.cli.legacy import app

__all__ = ["app"]
