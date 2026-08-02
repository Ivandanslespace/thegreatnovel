from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tgn.core.hashing import canonical_json
from tgn.projection import compile_projection_bundle
from tgn.worldgen import compile_bundle, compile_devour_overlay_bundle


def _write_json(path: Path, value: Any) -> Path:
    path.write_text(canonical_json(value), encoding="utf-8")
    return path


def world_draft() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mechanics_profile": "phase75_expedition_v1",
        "world_id": "phase10-world",
        "content_locale": "zh-CN",
        "title": "Phase 10 World",
        "premise": "A bounded deterministic test world.",
        "labels": {
            "base": "Base",
            "target": "Site",
            "resource": "Salvage",
            "hazard": "Hazard",
            "named_actor": "Mara",
            "named_actor_role": "Scout",
            "named_actor_public_goal": "Inspect the signal",
        },
    }


def projection_draft(worldpack_hash: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_worldpack_hash": worldpack_hash,
        "labels": {
            "secondary_resource": "Parts",
            "phase_day": "Day",
            "phase_night": "Night",
            "player_track": "Player",
            "base_track": "Base",
            "site_condition_subject": "Site condition",
            "site_condition_unstable": "Unstable",
            "site_condition_safe": "Safe",
            "actor_report_goal": "Report finding",
            "actor_reported_goal": "Reported",
            "build_window_runner": "Window Runner",
            "build_field_rest": "Field Rest",
            "build_quick_rest": "Quick Rest",
        },
    }


@pytest.fixture
def bundle_pair(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    request_path = _write_json(
        tmp_path / "request.json",
        {"schema_version": 1, "prompt": "bounded phase10 fixture"},
    )
    draft_path = _write_json(tmp_path / "draft.json", world_draft())
    base = tmp_path / "base-bundle"
    overlay = tmp_path / "overlay-bundle"
    compile_bundle(request_path, draft_path, "phase10-seed", base)
    compile_devour_overlay_bundle(base, overlay)
    worldpack_hash = json.loads(
        (overlay / "bundle.json").read_text(encoding="utf-8")
    )["worldpack_hash"]
    projection = tmp_path / "projection-bundle"
    compile_projection_bundle(overlay, projection_draft(worldpack_hash), projection)
    return base, overlay, projection, tmp_path
