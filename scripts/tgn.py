"""Repository-local launcher; no package installation is required."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tgn.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
