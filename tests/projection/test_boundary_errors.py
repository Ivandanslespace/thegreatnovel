from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

import tgn.projection.bundle as bundle_module
import tgn.projection.compiler as compiler_module
from tgn.core.hashing import canonical_json
from tgn.llm_player.models import LLMActionChoice, LLMDecisionRequest
from tgn.projection import build_player_presentation, compile_projection, compile_projection_bundle, preview_projection
from tgn.projection.common import (
    _StrictJSONError,
    parse_strict_json,
    read_json,
    safe_issue_value,
    write_json,
)
from tgn.projection.__main__ import main
from tgn.worldgen.models import WorldGenError


def _copy_source(source_bundle: Path, tmp_path: Path) -> Path:
    destination = tmp_path / "source-copy"
    shutil.copytree(source_bundle, destination)
    return destination


def _rewrite(path: Path, value):
    path.write_text(canonical_json(value), encoding="utf-8")


def test_strict_json_rejects_duplicates_constants_and_non_text():
    with pytest.raises(_StrictJSONError) as duplicate:
        parse_strict_json('{"a":1,"a":2}')
    assert duplicate.value.code == "INVALID_JSON"
    with pytest.raises(_StrictJSONError) as constant:
        parse_strict_json('{"a":NaN}')
    assert constant.value.code == "NON_CANONICAL_JSON_VALUE"
    with pytest.raises(_StrictJSONError):
        parse_strict_json(123)


def test_safe_issue_values_cover_nested_non_utf8_values():
    value = {"\ud800": ["\udfff", float("inf"), (1, 2), object()]}
    safe = safe_issue_value(value)
    assert safe["contains invalid Unicode surrogate U+D800"]
    assert safe["contains invalid Unicode surrogate U+D800"][0]["invalid_code_points"] == ["U+DFFF"]
    assert safe["contains invalid Unicode surrogate U+D800"][1]["invalid_number"]
    assert safe["contains invalid Unicode surrogate U+D800"][2] == [1, 2]


def test_read_and_write_json_fail_closed_for_io_and_noncanonical_values(tmp_path):
    with pytest.raises(WorldGenError) as missing:
        read_json(tmp_path / "missing.json")
    assert missing.value.code == "INVALID_JSON"
    noncanonical = tmp_path / "noncanonical.json"
    noncanonical.write_text('{ "a": 1 }', encoding="utf-8")
    with pytest.raises(WorldGenError):
        read_json(noncanonical, require_canonical=True)
    with pytest.raises(WorldGenError):
        write_json(tmp_path / "surrogate.json", {"value": "\ud800"})


def test_compile_rejects_bad_draft_and_missing_source(source_bundle, valid_projection_draft, tmp_path):
    bad = copy.deepcopy(valid_projection_draft)
    bad["labels"] = dict(bad["labels"])
    bad["labels"]["phase_day"] = 10
    with pytest.raises(WorldGenError) as draft_error:
        compile_projection(source_bundle, bad)
    assert draft_error.value.code == "INVALID_PROJECTION_DRAFT"
    with pytest.raises(WorldGenError) as source_error:
        compile_projection(tmp_path / "missing-source", valid_projection_draft)
    assert source_error.value.code == "SOURCE_BUNDLE_INVALID"


def test_compile_wraps_public_source_verification_errors(monkeypatch, source_bundle, valid_projection_draft):
    def fail_verify(_):
        raise ValueError("source failed")

    monkeypatch.setattr(compiler_module, "verify_bundle", fail_verify)
    with pytest.raises(WorldGenError) as raised:
        compile_projection(source_bundle, valid_projection_draft)
    assert raised.value.code == "SOURCE_BUNDLE_INVALID"


def test_public_projection_operations_verify_source_before_draft_or_projection(monkeypatch, source_bundle, valid_projection_draft, tmp_path):
    calls = []
    original_verify = compiler_module.verify_bundle
    original_draft = compiler_module._coerce_draft
    original_bundle_draft = bundle_module._coerce_draft_input
    original_read = bundle_module._read_projection_artifacts

    def verify(source):
        calls.append("source")
        return original_verify(source)

    def coerce(value):
        calls.append("draft")
        return original_draft(value)

    def bundle_draft(value):
        calls.append("draft")
        return original_bundle_draft(value)

    def read(projection):
        calls.append("projection")
        return original_read(projection)

    monkeypatch.setattr(compiler_module, "verify_bundle", verify)
    monkeypatch.setattr(compiler_module, "_coerce_draft", coerce)
    monkeypatch.setattr(bundle_module, "_coerce_draft_input", bundle_draft)
    monkeypatch.setattr(bundle_module, "_read_projection_artifacts", read)

    compile_projection(source_bundle, valid_projection_draft)
    assert calls[0] == "source"

    calls.clear()
    output = tmp_path / "projection"
    compile_projection_bundle(source_bundle, valid_projection_draft, output)
    assert calls[0] == "source"

    calls.clear()
    bundle_module.verify_projection_bundle(source_bundle, output)
    assert calls[0] == "source"
    assert "projection" in calls[1:]

    calls.clear()
    preview_projection(source_bundle, output)
    assert calls[0] == "source"
    assert "projection" in calls[1:]


def test_dual_invalid_source_wins_before_draft_or_projection_errors(source_bundle, valid_projection_draft, tmp_path):
    invalid_source = _copy_source(source_bundle, tmp_path)
    worldpack = json.loads((invalid_source / "compiled_worldpack.json").read_text(encoding="utf-8"))
    worldpack["public_content"]["title"] = "tampered source"
    _rewrite(invalid_source / "compiled_worldpack.json", worldpack)
    invalid_draft = dict(valid_projection_draft)
    invalid_draft["labels"] = dict(invalid_draft["labels"])
    invalid_draft["labels"]["phase_day"] = 10

    with pytest.raises(WorldGenError) as compile_error:
        compile_projection(invalid_source, invalid_draft)
    assert compile_error.value.code == "SOURCE_BUNDLE_INVALID"

    with pytest.raises(WorldGenError) as publish_error:
        compile_projection_bundle(invalid_source, invalid_draft, tmp_path / "new-output")
    assert publish_error.value.code == "SOURCE_BUNDLE_INVALID"

    with pytest.raises(WorldGenError) as verify_error:
        bundle_module.verify_projection_bundle(invalid_source, tmp_path / "missing-projection")
    assert verify_error.value.code == "SOURCE_BUNDLE_INVALID"

    with pytest.raises(WorldGenError) as preview_error:
        preview_projection(invalid_source, tmp_path / "missing-projection")
    assert preview_error.value.code == "SOURCE_BUNDLE_INVALID"


@pytest.mark.parametrize("mutation", ["title", "premise", "public_label", "content_locale", "world_id"])
def test_source_verification_return_race_rebinds_consumed_worldpack_hash(
    monkeypatch, source_bundle, valid_projection_draft, mutation
):
    original_verify = compiler_module.verify_bundle
    mutated = False

    def verify(source):
        nonlocal mutated
        verification = original_verify(source)
        if not mutated:
            worldpack_path = Path(source) / "compiled_worldpack.json"
            worldpack = json.loads(worldpack_path.read_text(encoding="utf-8"))
            if mutation == "title":
                worldpack["public_content"]["title"] = "race-mutated-title"
            elif mutation == "premise":
                worldpack["public_content"]["premise"] = "race-mutated-premise"
            elif mutation == "public_label":
                worldpack["public_content"]["labels"]["base"] = "race-mutated-label"
            elif mutation == "world_id":
                worldpack["world_id"] = "race-mutated-world-id"
            else:
                worldpack["content_locale"] = "fr"
            _rewrite(worldpack_path, worldpack)
            mutated = True
        return verification

    monkeypatch.setattr(compiler_module, "verify_bundle", verify)
    with pytest.raises(WorldGenError) as raised:
        compile_projection(source_bundle, valid_projection_draft)
    assert raised.value.code == "SOURCE_BUNDLE_INVALID"


@pytest.mark.parametrize("mutation", ["manifest", "profile", "runtime", "public", "labels", "label_type", "state", "hash"])
def test_source_artifact_integrity_and_profile_checks(monkeypatch, source_bundle, valid_projection_draft, tmp_path, mutation):
    source = _copy_source(source_bundle, tmp_path)
    manifest = json.loads((source / "bundle.json").read_text(encoding="utf-8"))
    worldpack = json.loads((source / "compiled_worldpack.json").read_text(encoding="utf-8"))
    state = json.loads((source / "initial_state.json").read_text(encoding="utf-8"))
    if mutation == "manifest":
        manifest["extra"] = True
        _rewrite(source / "bundle.json", manifest)
    elif mutation == "profile":
        worldpack["mechanics_profile"] = "unsupported"
        _rewrite(source / "compiled_worldpack.json", worldpack)
    elif mutation == "runtime":
        worldpack["runtime_bindings"]["resource_id"] = "other"
        _rewrite(source / "compiled_worldpack.json", worldpack)
    elif mutation == "public":
        del worldpack["public_content"]["premise"]
        _rewrite(source / "compiled_worldpack.json", worldpack)
    elif mutation == "labels":
        del worldpack["public_content"]["labels"]["base"]
        _rewrite(source / "compiled_worldpack.json", worldpack)
    elif mutation == "label_type":
        worldpack["public_content"]["labels"]["base"] = 1
        _rewrite(source / "compiled_worldpack.json", worldpack)
    elif mutation == "state":
        state["data"] = {}
        _rewrite(source / "initial_state.json", state)
    elif mutation == "hash":
        manifest["worldpack_hash"] = "0" * 64
        _rewrite(source / "bundle.json", manifest)

    monkeypatch.setattr(
        compiler_module,
        "verify_bundle",
        lambda _: {"worldpack_hash": manifest["worldpack_hash"], "initial_state_hash": manifest["initial_state_hash"]},
    )
    with pytest.raises(WorldGenError) as raised:
        compile_projection(source, valid_projection_draft)
    assert raised.value.code in {"SOURCE_BUNDLE_INVALID", "UNSUPPORTED_MECHANICS_PROFILE", "SOURCE_HASH_MISMATCH"}


def test_bundle_missing_invalid_manifest_and_invalid_saved_draft(compiled_projection, valid_projection_draft, tmp_path):
    _, output = compiled_projection
    with pytest.raises(WorldGenError) as missing:
        bundle_module.verify_projection_bundle(output.parent / "source-bundle", output.parent / "does-not-exist")
    assert missing.value.code == "PROJECTION_NOT_FOUND"

    bad_manifest = json.loads((output / "projection_manifest.json").read_text(encoding="utf-8"))
    bad_manifest["projection_draft_hash"] = "bad"
    _rewrite(output / "projection_manifest.json", bad_manifest)
    with pytest.raises(WorldGenError):
        bundle_module.verify_projection_bundle(output.parent / "source-bundle", output)

    # Recreate a clean output and then make the saved draft structurally invalid.
    clean = tmp_path / "clean"
    compile_projection_bundle(output.parent / "source-bundle", valid_projection_draft, clean)
    saved = json.loads((clean / "projection_draft.json").read_text(encoding="utf-8"))
    del saved["labels"]["phase_day"]
    _rewrite(clean / "projection_draft.json", saved)
    with pytest.raises(WorldGenError):
        bundle_module.verify_projection_bundle(output.parent / "source-bundle", clean)


def test_bundle_publication_lock_and_rename_fail_closed(monkeypatch, source_bundle, valid_projection_draft, tmp_path):
    target = tmp_path / "lock-race"

    def fail_open(*_args):
        raise FileExistsError("lock exists")

    monkeypatch.setattr(bundle_module.os, "open", fail_open)
    with pytest.raises(WorldGenError) as lock_error:
        compile_projection_bundle(source_bundle, valid_projection_draft, target)
    assert lock_error.value.code == "PROJECTION_ALREADY_EXISTS"
    assert not target.exists()
    assert not list(tmp_path.glob(".lock-race.*"))

    monkeypatch.undo()
    target2 = tmp_path / "rename-race"
    monkeypatch.setattr(
        bundle_module,
        "_publish_directory_no_replace",
        lambda *_args: (_ for _ in ()).throw(FileExistsError("target")),
    )
    with pytest.raises(WorldGenError) as rename_error:
        compile_projection_bundle(source_bundle, valid_projection_draft, target2)
    assert rename_error.value.code == "PROJECTION_ALREADY_EXISTS"
    assert not target2.exists()
    assert not bundle_module.publication_lock_path(target2).exists()
    assert not list(tmp_path.glob(".rename-race.*"))


def test_bundle_publication_unexpected_error_is_wrapped(monkeypatch, source_bundle, valid_projection_draft, tmp_path):
    target = tmp_path / "io-failure"
    monkeypatch.setattr(bundle_module, "write_json", lambda *_args: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(WorldGenError) as raised:
        compile_projection_bundle(source_bundle, valid_projection_draft, target)
    assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"
    assert not target.exists()


def test_verify_recompile_failure_and_preview_saved_draft_branch(monkeypatch, compiled_projection):
    result, output = compiled_projection
    source = output.parent / "source-bundle"

    def fail_compile(*_args):
        raise WorldGenError("SOURCE_HASH_MISMATCH", "mismatch")

    monkeypatch.setattr(bundle_module, "_compile_projection_from_verified_source", fail_compile)
    with pytest.raises(WorldGenError) as raised:
        bundle_module.verify_projection_bundle(source, output)
    assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"

    monkeypatch.undo()
    monkeypatch.setattr(bundle_module, "verify_projection_bundle", lambda *_args: {"valid": True})
    draft = json.loads((output / "projection_draft.json").read_text(encoding="utf-8"))
    del draft["labels"]["phase_day"]
    _rewrite(output / "projection_draft.json", draft)
    with pytest.raises(WorldGenError):
        preview_projection(source, output)


def test_cli_generic_boundary_failure_is_safe(monkeypatch, capsys, source_bundle, valid_projection_draft, tmp_path):
    import tgn.projection.__main__ as cli

    monkeypatch.setattr(cli, "compile_projection", lambda *_args: (_ for _ in ()).throw(RuntimeError("boom")))
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(canonical_json(valid_projection_draft), encoding="utf-8")
    assert main(["validate", "--source-bundle-dir", str(source_bundle), "--draft", str(draft_path)]) == 2
    output = capsys.readouterr().out
    assert json.loads(output)["error"]["code"] == "PROJECTION_INTEGRITY_MISMATCH"
