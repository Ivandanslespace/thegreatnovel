from __future__ import annotations

import json
from pathlib import Path

import pytest

from tgn.worldgen import (
    BUNDLE_FILES,
    compile_devour_overlay_bundle,
    verify_bundle,
)
from tgn.worldgen.models import WorldGenError


def test_overlay_has_six_files_and_preserves_base_artifact_bytes(bundle_pair):
    base, overlay, _projection, _tmp = bundle_pair
    assert {path.name for path in overlay.iterdir()} == set(BUNDLE_FILES)
    for name in ("world_request.json", "world_draft.json", "compiled_worldpack.json"):
        assert (overlay / name).read_bytes() == (base / name).read_bytes()

    base_manifest = json.loads((base / "bundle.json").read_text(encoding="utf-8"))
    overlay_manifest = json.loads((overlay / "bundle.json").read_text(encoding="utf-8"))
    assert overlay_manifest["compiler_id"] == "phase10a-devour-overlay-v1"
    assert overlay_manifest["worldpack_hash"] == base_manifest["worldpack_hash"]
    assert overlay_manifest["request_hash"] == base_manifest["request_hash"]
    assert overlay_manifest["draft_hash"] == base_manifest["draft_hash"]
    assert overlay_manifest["initial_state_hash"] != base_manifest["initial_state_hash"]
    assert verify_bundle(overlay)["compiler_id"] == "phase10a-devour-overlay-v1"

    report = json.loads((overlay / "compile_report.json").read_text(encoding="utf-8"))
    assert set(report) == {
        "schema_version",
        "valid",
        "compiler_id",
        "base_compiler_id",
        "overlay_id",
        "base_initial_state_hash",
        "worldpack_hash",
        "initial_state_hash",
        "errors",
        "bootstrap",
    }
    assert report["bootstrap"] == {
        "accepted_decisions": 5,
        "events": 5,
        "illegal_actions": 0,
        "essence": 1,
        "devour_yield_consumed": True,
        "replay_verified": True,
        "stamina_before_devour": 1,
        "stamina_after_devour": 0,
        "final_stamina_after_extract": 0,
        "final_state_hash": report["bootstrap"]["final_state_hash"],
    }


def test_overlay_compiler_rejects_overlay_as_base(bundle_pair, tmp_path: Path):
    _base, overlay, _projection, _tmp = bundle_pair
    with pytest.raises(WorldGenError) as exc_info:
        compile_devour_overlay_bundle(overlay, tmp_path / "second-overlay")
    assert exc_info.value.code == "BUNDLE_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("artifact", ["bundle.json", "initial_state.json", "compile_report.json"])
def test_overlay_tamper_fails_verification(bundle_pair, artifact: str):
    _base, overlay, _projection, _tmp = bundle_pair
    path = overlay / artifact
    value = json.loads(path.read_text(encoding="utf-8"))
    if artifact == "bundle.json":
        value["compiler_id"] = "phase9b-bounded-world-v1"
    elif artifact == "initial_state.json":
        value["data"]["devour_evolution"]["essence"] = 9
    else:
        value["bootstrap"]["events"] = 4
    from tgn.core.hashing import canonical_json

    path.write_text(canonical_json(value), encoding="utf-8")
    with pytest.raises(WorldGenError) as exc_info:
        verify_bundle(overlay)
    assert exc_info.value.code == "BUNDLE_INTEGRITY_MISMATCH"
