"""Stable loading and conservative selection of built-in world blueprints.

The registry is deliberately a small host-side boundary.  It never claims that
an arbitrary prompt has been compiled into a unique mechanic; it only chooses
between reviewed blueprints and reports why the choice was made.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


_ROOT = Path(__file__).resolve().parents[3]
BUILTIN_WORLD_DIR = _ROOT / "worlds"
_BUILTIN_IDS = ("frost_harbor", "gray_court")

_FROST_TERMS = {
    "supply", "logistics", "maintenance", "infrastructure", "harbor", "tide",
    "schedule", "repair", "node", "供给", "物流", "维护", "基础设施", "港", "潮", "调度",
}
_GRAY_TERMS = {
    "evidence", "proof", "contract", "deadline", "arbitration", "court", "faction",
    "alliance", "promise", "clause", "证据", "证明", "契约", "期限", "仲裁", "法庭", "派系", "联盟",
}


def _read_blueprint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"world blueprint not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("world blueprint must be a JSON object")
    return value


def list_worlds() -> list[str]:
    """Return built-in IDs in stable lexical order."""

    return sorted(world_id for world_id in _BUILTIN_IDS if (BUILTIN_WORLD_DIR / f"{world_id}.json").is_file())


def load_world(world_id: str, *, blueprint_file: str | Path | None = None) -> dict[str, Any]:
    """Load a built-in or explicitly supplied host blueprint."""

    if not isinstance(world_id, str) or not world_id:
        raise ValueError("world_id must be a non-empty string")
    path = Path(blueprint_file) if blueprint_file is not None else BUILTIN_WORLD_DIR / f"{world_id}.json"
    value = _read_blueprint(path)
    if value.get("id") != world_id:
        raise ValueError("world blueprint id does not match requested id")
    return value


def _score(prompt: str, terms: set[str]) -> int:
    lowered = prompt.casefold()
    return sum((2 if len(term) > 2 else 1) for term in terms if term.casefold() in lowered)


def choose_world_for_prompt(
    prompt: str | None,
    *,
    blueprint_file: str | Path | None = None,
) -> dict[str, Any]:
    """Choose one reviewed world and return it with transparent fit metadata.

    ``blueprint_file`` is an explicit host escape hatch for a separately
    reviewed candidate; it is never inferred from prompt text.
    """

    if prompt is not None and not isinstance(prompt, str):
        raise TypeError("prompt must be text or None")
    text = (prompt or "").strip()
    if blueprint_file is not None:
        world = _read_blueprint(Path(blueprint_file))
        if not isinstance(world.get("id"), str) or not world["id"]:
            raise ValueError("custom world blueprint must declare a stable id")
        return {
            "world": world,
            "blueprint": world,
            "world_id": world["id"],
            "selection_reasons": ["host supplied an explicit blueprint file"],
            "fit_warning": "custom blueprint requires the normal compile and anti-reskin gates",
        }
    if not text:
        world_id = "frost_harbor"
        reasons = ["no prompt was supplied; the conservative default is frost_harbor"]
        warning = "default selection is a bounded reviewed world, not a unique interpretation of a prompt"
    else:
        frost = _score(text, _FROST_TERMS)
        gray = _score(text, _GRAY_TERMS)
        if gray > frost:
            world_id = "gray_court"
            reasons = [f"matched {gray} evidence/contract structure keyword points"]
        else:
            world_id = "frost_harbor"
            reasons = [f"matched {frost} supply/maintenance structure keyword points"]
        if frost == gray:
            reasons.append("scores tied; stable frost_harbor tie-break applies")
        warning = "keyword selection is only a fit hint; it does not claim arbitrary prompt uniqueness"
    world = load_world(world_id)
    return {
        "world": world,
        "blueprint": world,
        "world_id": world_id,
        "selection_reasons": reasons,
        "fit_warning": warning,
    }
