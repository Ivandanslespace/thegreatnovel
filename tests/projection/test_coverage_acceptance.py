from __future__ import annotations

import copy
import errno
import json
import os
import shutil
from pathlib import Path

import pytest

import tgn.projection.bundle as bundle_module
import tgn.projection.common as common_module
import tgn.projection.compiler as compiler_module
import tgn.projection.models as models_module
from tgn.core.hashing import canonical_json
from tgn.llm_player.models import LLMDecisionRequest
from tgn.projection import (
    ProjectionDraft,
    ProjectionCompilationResult,
    build_player_presentation,
)
from tgn.projection.__main__ import main
from tgn.worldgen.models import WorldGenError


def _raise(exc):
    def raiser(*_args, **_kwargs):
        raise exc

    return raiser


class _FakeFunction:
    def __init__(self, result: int, calls: list[tuple[object, ...]]) -> None:
        self.result = result
        self.calls = calls

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class _FakeLibrary:
    def __init__(self, name: str, function: _FakeFunction) -> None:
        setattr(self, name, function)


def test_windows_no_replace_primitive_covers_success_conflict_and_unavailable(monkeypatch, tmp_path):
    source = tmp_path / "temporary"
    target = tmp_path / "target"
    calls: list[tuple[object, ...]] = []
    move = _FakeFunction(1, calls)

    monkeypatch.setattr(bundle_module.os, "name", "nt")
    monkeypatch.setattr(
        bundle_module.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: _FakeLibrary("MoveFileExW", move),
        raising=False,
    )
    bundle_module._publish_directory_no_replace(source, target)
    assert calls == [(str(source), str(target), 0x00000008)]

    move.result = 0
    monkeypatch.setattr(bundle_module.ctypes, "get_last_error", lambda: 183, raising=False)
    with pytest.raises(FileExistsError):
        bundle_module._publish_directory_no_replace(source, target)

    monkeypatch.setattr(bundle_module.ctypes, "get_last_error", lambda: 5, raising=False)
    with pytest.raises(bundle_module._NoReplaceUnavailable):
        bundle_module._publish_directory_no_replace(source, target)

    monkeypatch.setattr(bundle_module.ctypes, "WinDLL", lambda *_args, **_kwargs: object(), raising=False)
    with pytest.raises(bundle_module._NoReplaceUnavailable):
        bundle_module._publish_directory_no_replace(source, target)


def test_linux_no_replace_primitive_covers_success_conflict_and_unavailable(monkeypatch, tmp_path):
    source = tmp_path / "temporary"
    target = tmp_path / "target"
    calls: list[tuple[object, ...]] = []
    rename = _FakeFunction(0, calls)

    monkeypatch.setattr(bundle_module.os, "name", "posix")
    monkeypatch.setattr(bundle_module.sys, "platform", "linux")
    monkeypatch.setattr(
        bundle_module.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: _FakeLibrary("renameat2", rename),
    )
    bundle_module._publish_directory_no_replace(source, target)
    assert calls[-1] == (-100, os.fsencode(source), -100, os.fsencode(target), 1)

    rename.result = -1
    monkeypatch.setattr(bundle_module.ctypes, "get_errno", lambda: errno.EEXIST)
    with pytest.raises(FileExistsError):
        bundle_module._publish_directory_no_replace(source, target)

    monkeypatch.setattr(bundle_module.ctypes, "get_errno", lambda: errno.EIO)
    with pytest.raises(bundle_module._NoReplaceUnavailable):
        bundle_module._publish_directory_no_replace(source, target)

    monkeypatch.setattr(bundle_module.ctypes, "CDLL", lambda *_args, **_kwargs: object())
    with pytest.raises(bundle_module._NoReplaceUnavailable):
        bundle_module._publish_directory_no_replace(source, target)


def test_macos_no_replace_primitive_covers_success_conflict_and_unavailable(monkeypatch, tmp_path):
    source = tmp_path / "temporary"
    target = tmp_path / "target"
    calls: list[tuple[object, ...]] = []
    rename = _FakeFunction(0, calls)

    monkeypatch.setattr(bundle_module.os, "name", "posix")
    monkeypatch.setattr(bundle_module.sys, "platform", "darwin")
    monkeypatch.setattr(
        bundle_module.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: _FakeLibrary("renameatx_np", rename),
    )
    bundle_module._publish_directory_no_replace(source, target)
    assert calls[-1] == (-2, os.fsencode(source), -2, os.fsencode(target), 0x00000004)

    rename.result = -1
    monkeypatch.setattr(bundle_module.ctypes, "get_errno", lambda: errno.ENOTEMPTY)
    with pytest.raises(FileExistsError):
        bundle_module._publish_directory_no_replace(source, target)

    monkeypatch.setattr(bundle_module.ctypes, "get_errno", lambda: errno.EIO)
    with pytest.raises(bundle_module._NoReplaceUnavailable):
        bundle_module._publish_directory_no_replace(source, target)

    monkeypatch.setattr(bundle_module.ctypes, "CDLL", lambda *_args, **_kwargs: object())
    with pytest.raises(bundle_module._NoReplaceUnavailable):
        bundle_module._publish_directory_no_replace(source, target)


def test_unsupported_platform_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(bundle_module.os, "name", "posix")
    monkeypatch.setattr(bundle_module.sys, "platform", "freebsd")
    with pytest.raises(bundle_module._NoReplaceUnavailable):
        bundle_module._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")


def test_projection_artifact_read_errors_are_wrapped(monkeypatch, compiled_projection):
    _, output = compiled_projection

    with monkeypatch.context() as patch:
        patch.setattr(bundle_module.Path, "iterdir", _raise(OSError("directory unavailable")))
        with pytest.raises(WorldGenError) as raised:
            bundle_module._read_projection_artifacts(output)
        assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"

    invalid = output / "projection_draft.json"
    original = invalid.read_text(encoding="utf-8")
    invalid.write_text("{not-json", encoding="utf-8")
    try:
        with pytest.raises(WorldGenError) as raised:
            bundle_module._read_projection_artifacts(output)
        assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"
    finally:
        invalid.write_text(original, encoding="utf-8")

    with monkeypatch.context() as patch:
        patch.setattr(bundle_module, "read_json", _raise(RuntimeError("reader failed")))
        with pytest.raises(WorldGenError) as raised:
            bundle_module._read_projection_artifacts(output)
        assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("mutation", ["fields", "schema", "compiler", "hash"])
def test_projection_manifest_schema_errors_are_directly_rejected(monkeypatch, compiled_projection, mutation):
    _, output = compiled_projection
    manifest_path = output / "projection_manifest.json"
    original = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate = copy.deepcopy(original)
    if mutation == "fields":
        candidate["extra"] = True
    elif mutation == "schema":
        candidate["schema_version"] = 2
    elif mutation == "compiler":
        candidate["projection_compiler_id"] = "unsupported"
    else:
        candidate["projection_draft_hash"] = "not-a-sha256"
    manifest_path.write_text(canonical_json(candidate), encoding="utf-8")
    try:
        with pytest.raises(WorldGenError) as raised:
            bundle_module.verify_projection_bundle(output.parent / "source-bundle", output)
        assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"
    finally:
        manifest_path.write_text(canonical_json(original), encoding="utf-8")


def test_bundle_draft_coercion_and_recompile_errors_are_wrapped(
    monkeypatch, source_bundle, valid_projection_draft, compiled_projection
):
    bad = copy.deepcopy(valid_projection_draft)
    bad["labels"] = dict(bad["labels"])
    bad["labels"]["phase_day"] = 1
    with pytest.raises(WorldGenError) as draft_error:
        bundle_module._coerce_draft_input(bad)
    assert draft_error.value.code == "INVALID_PROJECTION_DRAFT"

    _, output = compiled_projection
    with monkeypatch.context() as patch:
        patch.setattr(
            bundle_module,
            "_compile_projection_from_verified_source",
            _raise(WorldGenError("OTHER_COMPILE_ERROR", "compile failed")),
        )
        with pytest.raises(WorldGenError) as raised:
            bundle_module.verify_projection_bundle(source_bundle, output)
        assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"

    with monkeypatch.context() as patch:
        patch.setattr(
            bundle_module,
            "_compile_projection_from_verified_source",
            _raise(RuntimeError("compile failed")),
        )
        with pytest.raises(WorldGenError) as raised:
            bundle_module.verify_projection_bundle(source_bundle, output)
        assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("field", ["source_worldpack_hash", "source_initial_state_hash"])
def test_projection_source_hash_binding_checks_run_after_artifact_recomputation(
    monkeypatch, source_bundle, compiled_projection, field
):
    _, output = compiled_projection
    source = compiler_module._verified_source(source_bundle)
    artifacts = bundle_module._read_projection_artifacts(output)
    mutated = copy.deepcopy(artifacts)
    mutated["projection_manifest.json"][field] = "f" * 64
    monkeypatch.setattr(bundle_module, "_read_projection_artifacts", lambda _root: mutated)
    monkeypatch.setattr(bundle_module, "_artifact_payloads", lambda _result: copy.deepcopy(mutated))

    with pytest.raises(WorldGenError) as raised:
        bundle_module._verify_projection_bundle_with_source(source, output)
    assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"


def test_publication_cleanup_closes_pending_lock_and_tolerates_missing_lock(
    monkeypatch, source_bundle, valid_projection_draft, tmp_path
):
    target = tmp_path / "close-failure"
    original_close = os.close
    calls: list[int] = []

    def close_once_fails(fd):
        if not calls:
            calls.append(fd)
            raise OSError("close failed")
        return original_close(fd)

    monkeypatch.setattr(bundle_module.os, "close", close_once_fails)
    with pytest.raises(WorldGenError) as raised:
        bundle_module.compile_projection_bundle(source_bundle, valid_projection_draft, target)
    assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"
    assert not bundle_module.publication_lock_path(target).exists()
    assert not target.exists()

    monkeypatch.undo()
    target = tmp_path / "lock-removed"

    def remove_lock_then_fail(_temporary, destination):
        bundle_module.publication_lock_path(destination).unlink()
        raise RuntimeError("publication failed")

    monkeypatch.setattr(bundle_module, "_publish_directory_no_replace", remove_lock_then_fail)
    with pytest.raises(WorldGenError) as raised:
        bundle_module.compile_projection_bundle(source_bundle, valid_projection_draft, target)
    assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"
    assert not bundle_module.publication_lock_path(target).exists()


def test_publication_unavailable_is_a_boundary_error(monkeypatch, source_bundle, valid_projection_draft, tmp_path):
    monkeypatch.setattr(
        bundle_module,
        "_publish_directory_no_replace",
        _raise(bundle_module._NoReplaceUnavailable("unsupported")),
    )
    with pytest.raises(WorldGenError) as raised:
        bundle_module.compile_projection_bundle(source_bundle, valid_projection_draft, tmp_path / "unavailable")
    assert raised.value.code == "PROJECTION_INTEGRITY_MISMATCH"


def test_compiler_draft_and_source_artifact_exception_branches(monkeypatch, source_bundle, valid_projection_draft):
    draft, issues = compiler_module.validate_projection_draft({"schema_version": 1})
    assert draft is None
    assert {item.code for item in issues} >= {"MISSING_FIELD"}

    source = compiler_module._verified_source(source_bundle)
    bad_draft = ProjectionDraft(1, "0" * 64, valid_projection_draft["labels"])
    with pytest.raises(WorldGenError) as raised:
        compiler_module._compile_projection_from_verified_source(source, bad_draft)
    assert raised.value.code == "SOURCE_HASH_MISMATCH"

    with monkeypatch.context() as patch:
        patch.setattr(compiler_module, "read_json", _raise(ValueError("bad artifact")))
        with pytest.raises(WorldGenError) as raised:
            compiler_module._read_source_artifact(source.source_dir, "bundle.json")
        assert raised.value.code == "SOURCE_BUNDLE_INVALID"

    with monkeypatch.context() as patch:
        patch.setattr(
            compiler_module,
            "read_json",
            _raise(WorldGenError("SOURCE_BUNDLE_INVALID", "already wrapped")),
        )
        with pytest.raises(WorldGenError) as raised:
            compiler_module._read_source_artifact(source.source_dir, "bundle.json")
        assert raised.value.code == "SOURCE_BUNDLE_INVALID"

    with monkeypatch.context() as patch:
        patch.setattr(compiler_module, "_read_source_artifact", _raise(WorldGenError("SOURCE_BUNDLE_INVALID", "read")))
        with pytest.raises(WorldGenError) as raised:
            compiler_module._verified_source(source_bundle)
        assert raised.value.code == "SOURCE_BUNDLE_INVALID"


@pytest.mark.parametrize("mutation", ["worldpack_fields", "state_fields", "worldpack_hash", "state_hash"])
def test_source_shape_and_hash_bindings_fail_closed_directly(
    monkeypatch, source_bundle, valid_projection_draft, tmp_path, mutation
):
    source = tmp_path / mutation
    shutil.copytree(source_bundle, source)
    manifest_path = source / "bundle.json"
    worldpack_path = source / "compiled_worldpack.json"
    state_path = source / "initial_state.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    worldpack = json.loads(worldpack_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    verified_hashes = {
        "worldpack_hash": manifest["worldpack_hash"],
        "initial_state_hash": manifest["initial_state_hash"],
    }
    if mutation == "worldpack_fields":
        worldpack["unexpected"] = True
        worldpack_path.write_text(canonical_json(worldpack), encoding="utf-8")
    elif mutation == "state_fields":
        state["unexpected"] = True
        state_path.write_text(canonical_json(state), encoding="utf-8")
    elif mutation == "worldpack_hash":
        manifest["worldpack_hash"] = "f" * 64
        manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
    else:
        manifest["initial_state_hash"] = "e" * 64
        manifest_path.write_text(canonical_json(manifest), encoding="utf-8")

    monkeypatch.setattr(compiler_module, "verify_bundle", lambda _root: verified_hashes)
    with pytest.raises(WorldGenError) as raised:
        compiler_module.compile_projection(source, valid_projection_draft)
    assert raised.value.code == "SOURCE_BUNDLE_INVALID"


def test_source_initial_state_invariant_failure_is_wrapped(monkeypatch, source_bundle, valid_projection_draft):
    monkeypatch.setattr(
        compiler_module,
        "check_invariants",
        _raise(ValueError("invariant failure")),
    )
    with pytest.raises(WorldGenError) as raised:
        compiler_module.compile_projection(source_bundle, valid_projection_draft)
    assert raised.value.code == "SOURCE_BUNDLE_INVALID"


def test_common_and_model_snapshot_rejection_branches(monkeypatch, tmp_path):
    with pytest.raises(common_module._StrictJSONError) as raised:
        common_module.parse_strict_json('{"value":1e999}')
    assert raised.value.code == "NON_CANONICAL_JSON_VALUE"
    assert common_module.safe_issue_value(1.25) == 1.25

    with monkeypatch.context() as patch:
        patch.setattr(common_module, "parse_strict_json", _raise(WorldGenError("PASSTHROUGH", "already a boundary error")))
        json_path = tmp_path / "already-failed.json"
        json_path.write_text("{}", encoding="utf-8")
        with pytest.raises(WorldGenError) as raised:
            common_module.read_json(json_path)
        assert raised.value.code == "PASSTHROUGH"

    with pytest.raises(ValueError):
        models_module.ProjectionDraft(1, "a" * 64, {"\ud800": "bad"})
    assert models_module.ProjectionDraft(1, "a" * 64, {"finite": 1.25}).labels["finite"] == 1.25
    with pytest.raises(ValueError):
        models_module.ProjectionDraft(1, "a" * 64, [])
    with pytest.raises(ValueError):
        models_module.PlayerProjectionMap(1, "compiler", "profile", "a" * 64, "b" * 64, "zh-CN", [], {})
    with pytest.raises(ValueError):
        models_module.PlayerProjectionMap(1, "compiler", "profile", "a" * 64, "b" * 64, "zh-CN", {}, [])
    with pytest.raises(ValueError):
        models_module.PlayerPresentation(1, "a" * 64, "fingerprint", "zh-CN", [], {}, ())
    with pytest.raises(ValueError):
        models_module.PlayerPresentation(1, "a" * 64, "fingerprint", "zh-CN", {}, [], ())
    with pytest.raises(ValueError):
        models_module.PlayerPresentation(1, "a" * 64, "fingerprint", "zh-CN", {}, {}, ["not-a-choice"])


def test_compilation_result_rejects_non_mapping_report(compiled_projection):
    result, _ = compiled_projection
    with pytest.raises(ValueError):
        ProjectionCompilationResult(
            result.draft,
            result.projection,
            result.projection_hash,
            result.initial_request,
            result.initial_presentation,
            result.presentation_hash,
            [],
        )


def test_presenter_schema_and_identity_edge_branches(compiled_projection):
    result, _ = compiled_projection
    from tgn.projection.presenter import _map_build, _map_choice, _map_observation

    with pytest.raises(WorldGenError):
        _map_observation({"inventory": []}, result.projection)

    observation = copy.deepcopy(result.initial_request.observation)
    observation["actor"]["facts"] = {"unknown-fact": "value"}
    request = LLMDecisionRequest(1, observation, result.initial_request.choices, "fingerprint")
    with pytest.raises(WorldGenError) as fact_error:
        build_player_presentation(request, result.projection)
    assert fact_error.value.code == "UNMAPPED_PLAYER_IDENTITY"

    malformed_build = {"choices": [{}]}
    with pytest.raises(WorldGenError):
        _map_build(malformed_build, result.projection.identities, "/observation/build")

    canonical_build = copy.deepcopy(result.initial_request.observation["build"])
    del canonical_build["choices"][0]["effect_summary"]
    with pytest.raises(WorldGenError) as build_error:
        _map_build(canonical_build, result.projection.identities, "/observation/build")
    assert build_error.value.code == "UNSUPPORTED_PRESENTATION_ACTION_SCHEMA"

    with pytest.raises(WorldGenError):
        _map_choice({"action_type": "WAIT", "params": []}, result.projection, 0)
    with pytest.raises(WorldGenError):
        _map_choice(
            {"choice_id": "id", "action_type": "WAIT", "params": {}, "duration_minutes": 1},
            result.projection,
            0,
        )


def test_cli_uses_safe_fallback_when_json_serializer_fails(monkeypatch, capsys, source_bundle, valid_projection_draft, tmp_path):
    import tgn.projection.__main__ as cli

    draft_path = tmp_path / "draft.json"
    draft_path.write_text(canonical_json(valid_projection_draft), encoding="utf-8")
    monkeypatch.setattr(cli, "canonical_json", _raise(ValueError("serializer failed")))
    assert main(["validate", "--source-bundle-dir", str(source_bundle), "--draft", str(draft_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "PROJECTION_INTEGRITY_MISMATCH"
