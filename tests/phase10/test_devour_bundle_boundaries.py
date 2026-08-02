from __future__ import annotations

import json
import shutil

import pytest

from tgn.core.hashing import canonical_json, state_hash
from tgn.worldgen import bundle as bundle_module
from tgn.worldgen.models import WorldGenError
from tgn.worldgen import compile_devour_overlay_bundle, verify_bundle


def _copy_overlay(overlay, tmp_path, name="mutated"):
    target = tmp_path / name
    shutil.copytree(overlay, target)
    return target


def _rewrite(path, value):
    path.write_text(canonical_json(value), encoding="utf-8")


def test_overlay_publication_rejects_existing_target_and_lock(bundle_pair, tmp_path):
    _base, overlay, _projection, _root = bundle_pair
    target = tmp_path / "existing"
    target.mkdir()
    with pytest.raises(WorldGenError) as existing:
        compile_devour_overlay_bundle(overlay.parent / "base-bundle", target)
    assert existing.value.code == "BUNDLE_ALREADY_EXISTS"

    locked = tmp_path / "locked"
    bundle_module._publication_lock_path(locked).write_text("lock", encoding="utf-8")
    with pytest.raises(WorldGenError) as lock_error:
        compile_devour_overlay_bundle(overlay.parent / "base-bundle", locked)
    assert lock_error.value.code == "BUNDLE_ALREADY_EXISTS"
    assert bundle_module._publication_lock_path(locked).exists()


def test_overlay_verification_rejects_invalid_saved_request(bundle_pair, tmp_path):
    _base, overlay, _projection, _root = bundle_pair
    mutated = _copy_overlay(overlay, tmp_path)
    _rewrite(mutated / "world_request.json", {"schema_version": 1})
    with pytest.raises(WorldGenError) as error:
        verify_bundle(mutated)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_overlay_verification_rebuilds_base_and_report_fail_closed(bundle_pair, tmp_path, monkeypatch):
    _base, overlay, _projection, _root = bundle_pair

    def fail_compile(*_args, **_kwargs):
        raise RuntimeError("forced base rebuild failure")

    monkeypatch.setattr(bundle_module, "compile_world", fail_compile)
    with pytest.raises(WorldGenError) as error:
        verify_bundle(overlay)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"

    monkeypatch.undo()
    monkeypatch.setattr(bundle_module, "apply_devour_overlay", fail_compile)
    with pytest.raises(WorldGenError) as overlay_error:
        verify_bundle(overlay)
    assert overlay_error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_overlay_verification_rejects_changed_base_artifact_and_report(bundle_pair, tmp_path):
    _base, overlay, _projection, _root = bundle_pair
    changed_base = _copy_overlay(overlay, tmp_path, "changed-base")
    worldpack_path = changed_base / "compiled_worldpack.json"
    worldpack = json.loads(worldpack_path.read_text(encoding="utf-8"))
    worldpack["public_content"]["title"] = "changed"
    _rewrite(worldpack_path, worldpack)
    manifest_path = changed_base / "bundle.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["worldpack_hash"] = state_hash(worldpack)
    _rewrite(manifest_path, manifest)
    with pytest.raises(WorldGenError) as base_error:
        verify_bundle(changed_base)
    assert base_error.value.code == "BUNDLE_INTEGRITY_MISMATCH"

    changed_report = _copy_overlay(overlay, tmp_path, "changed-report")
    report_path = changed_report / "compile_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["bootstrap"]["events"] = 4
    _rewrite(report_path, report)
    manifest_path = changed_report / "bundle.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compile_report_hash"] = state_hash(report)
    _rewrite(manifest_path, manifest)
    with pytest.raises(WorldGenError) as report_error:
        verify_bundle(changed_report)
    assert report_error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_overlay_publication_target_and_rename_races_cleanup(bundle_pair, tmp_path, monkeypatch):
    base, _overlay, _projection, _root = bundle_pair

    target_appears = tmp_path / "appears"
    original_verify = bundle_module.verify_bundle

    def verify_then_compete(root):
        result = original_verify(root)
        if root != base and not target_appears.exists():
            target_appears.mkdir()
        return result

    monkeypatch.setattr(bundle_module, "verify_bundle", verify_then_compete)
    with pytest.raises(WorldGenError) as appears_error:
        compile_devour_overlay_bundle(base, target_appears)
    assert appears_error.value.code == "BUNDLE_ALREADY_EXISTS"

    monkeypatch.undo()
    rename_target = tmp_path / "rename-race"

    def competing_rename(_source, destination):
        destination.mkdir()
        raise FileExistsError("competing target")

    monkeypatch.setattr(bundle_module.os, "rename", competing_rename)
    with pytest.raises(WorldGenError) as rename_error:
        compile_devour_overlay_bundle(base, rename_target)
    assert rename_error.value.code == "BUNDLE_ALREADY_EXISTS"
    assert rename_target.exists()
