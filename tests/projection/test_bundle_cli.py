from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import tgn.projection.bundle as bundle_module
from tgn.core.hashing import canonical_json
from tgn.projection import (
    PROJECTION_FILES,
    compile_projection_bundle,
    publication_lock_path,
    verify_projection_bundle,
)
from tgn.projection.__main__ import main
from tgn.worldgen.models import WorldGenError


def test_projection_bundle_has_exact_four_files_and_verifies(compiled_projection):
    _, output = compiled_projection
    assert {item.name for item in output.iterdir()} == PROJECTION_FILES
    verification = verify_projection_bundle(output.parent / "source-bundle", output)
    assert verification["valid"] is True


def test_projection_bundle_tamper_and_extra_file_fail_closed(compiled_projection):
    _, output = compiled_projection
    projection_path = output / "player_projection.json"
    value = json.loads(projection_path.read_text(encoding="utf-8"))
    value["world"]["title"] = "tampered"
    projection_path.write_text(canonical_json(value), encoding="utf-8")
    with pytest.raises(WorldGenError) as raised:
        verify_projection_bundle(output.parent / "source-bundle", output)
    assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"

    projection_path.write_text(canonical_json(value), encoding="utf-8")
    (output / "extra.json").write_text("{}", encoding="utf-8")
    with pytest.raises(WorldGenError):
        verify_projection_bundle(output.parent / "source-bundle", output)


def test_existing_target_and_existing_lock_are_preserved(source_bundle, valid_projection_draft, tmp_path):
    target = tmp_path / "projection"
    target.mkdir()
    marker = target / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(WorldGenError) as target_error:
        compile_projection_bundle(source_bundle, valid_projection_draft, target)
    assert target_error.value.code == "PROJECTION_ALREADY_EXISTS"
    assert marker.read_text(encoding="utf-8") == "keep"

    locked_target = tmp_path / "locked"
    lock = publication_lock_path(locked_target)
    lock.write_text("pre-existing", encoding="utf-8")
    with pytest.raises(WorldGenError) as lock_error:
        compile_projection_bundle(source_bundle, valid_projection_draft, locked_target)
    assert lock_error.value.code == "PROJECTION_ALREADY_EXISTS"
    assert lock.read_text(encoding="utf-8") == "pre-existing"
    assert not locked_target.exists()


def test_competing_target_is_preserved_and_rename_is_not_called(monkeypatch, source_bundle, valid_projection_draft, tmp_path):
    target = tmp_path / "race"
    original_verify = bundle_module.verify_projection_bundle
    rename_calls = []

    def create_competing_target(source, temporary):
        result = original_verify(source, temporary)
        target.mkdir()
        (target / "marker.txt").write_text("competing", encoding="utf-8")
        return result

    monkeypatch.setattr(bundle_module, "verify_projection_bundle", create_competing_target)
    monkeypatch.setattr(bundle_module.os, "rename", lambda *args: rename_calls.append(args))
    with pytest.raises(WorldGenError) as raised:
        compile_projection_bundle(source_bundle, valid_projection_draft, target)
    assert raised.value.code == "PROJECTION_ALREADY_EXISTS"
    assert (target / "marker.txt").read_text(encoding="utf-8") == "competing"
    assert rename_calls == []
    assert not publication_lock_path(target).exists()
    assert not list(tmp_path.glob(".race.*"))


def test_two_cooperating_writers_have_one_success_and_no_debris(source_bundle, valid_projection_draft, tmp_path):
    target = tmp_path / "concurrent"

    def writer():
        try:
            return compile_projection_bundle(source_bundle, valid_projection_draft, target)
        except WorldGenError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: writer(), range(2)))
    successes = [item for item in results if isinstance(item, dict) and item.get("ok")]
    failures = [item for item in results if isinstance(item, WorldGenError)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert verify_projection_bundle(source_bundle, target)["valid"] is True
    assert not publication_lock_path(target).exists()
    assert not list(tmp_path.glob(".concurrent.*"))


def test_compile_verifies_temporary_bundle_once_without_post_publish_call(monkeypatch, source_bundle, valid_projection_draft, tmp_path):
    target = tmp_path / "counted"
    original_verify = bundle_module.verify_projection_bundle
    calls = []

    def count_verify(source, projection):
        calls.append(Path(projection))
        return original_verify(source, projection)

    monkeypatch.setattr(bundle_module, "verify_projection_bundle", count_verify)
    result = compile_projection_bundle(source_bundle, valid_projection_draft, target)
    assert result["ok"] is True
    assert len(calls) == 1
    assert calls[0] != target


def test_cli_validate_compile_verify_preview_do_not_traceback(capsys, source_bundle, valid_projection_draft, tmp_path):
    draft_path = tmp_path / "projection_draft.json"
    draft_path.write_text(canonical_json(valid_projection_draft), encoding="utf-8")
    output = tmp_path / "cli-projection"

    assert main(["validate", "--source-bundle-dir", str(source_bundle), "--draft", str(draft_path)]) == 0
    assert not output.exists()
    assert json.loads(capsys.readouterr().out)["valid"] is True

    assert main(["compile", "--source-bundle-dir", str(source_bundle), "--draft", str(draft_path), "--output-dir", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["verify", "--source-bundle-dir", str(source_bundle), "--projection-dir", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["preview", "--source-bundle-dir", str(source_bundle), "--projection-dir", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["presentation_hash"]


def test_cli_invalid_json_is_machine_readable(capsys, source_bundle, tmp_path):
    draft_path = tmp_path / "invalid.json"
    draft_path.write_text("{not-json", encoding="utf-8")
    assert main(["validate", "--source-bundle-dir", str(source_bundle), "--draft", str(draft_path)]) == 2
    output = capsys.readouterr().out
    assert "Traceback" not in output
    assert json.loads(output)["error"]["code"] == "INVALID_PROJECTION_DRAFT"
