from __future__ import annotations

import sys
import os
from pathlib import Path


SRC = Path(__file__).resolve().parents[2] / "src"
engine_src = next(
    (Path(item) for item in os.environ.get("PYTHONPATH", "").split(os.pathsep) if item and (Path(item) / "tgn" / "blueprint.py").is_file()),
    None,
)
if engine_src is not None:
    sys.path.insert(0, str(engine_src))
elif str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
