"""Deprecated CLI compatibility facade.

The executable entry point is now :mod:`novel_authoring.cli.app`.  The
historical command implementation remains frozen in ``cli/legacy.py`` for
one compatibility release; new commands belong in the split CLI modules.
"""

from novel_authoring.cli.app import app

__all__ = ["app"]


if __name__ == "__main__":  # pragma: no cover - compatibility invocation
    app()
