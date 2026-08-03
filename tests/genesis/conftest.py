"""Ensure Genesis tests exercise this checkout's ``src`` tree."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
