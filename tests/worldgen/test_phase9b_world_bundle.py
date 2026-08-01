from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

import tgn.worldgen.bundle as bundle_module
from tgn.core.hashing import canonical_json, state_hash
from tgn.worldgen import WorldGenError, compile_bundle, verify_bundle

from .conftest import draft_payload, request_payload, write_json


def _rewrite_json(path: Path, mutate) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(canonical_json(payload), encoding="utf-8")


def _rewrite_manifest_hash(bundle_dir: Path, field: str, artifact: str) -> None:
    manifest_path = bundle_dir / "bundle.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_value = json.loads((bundle_dir / artifact).read_text(encoding="utf-8"))
    manifest[field] = state_hash(artifact_value)
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")


def test_compile_publishes_exact_verified_bundle_without_campaign_files(bundle_dir):
    assert {path.name for path in bundle_dir.iterdir()} == {
        "bundle.json",
        "world_request.json",
        "world_draft.json",
        "compiled_worldpack.json",
        "initial_state.json",
        "compile_report.json",
    }
    assert not (bundle_dir / "campaign.sqlite3").exists()
    assert verify_bundle(bundle_dir)["valid"] is True


@pytest.mark.parametrize(
    "filename,mutation",
    [
        ("world_request.json", lambda value: value.__setitem__("prompt", "changed")),
        ("world_draft.json", lambda value: value.__setitem__("title", "changed")),
        (
            "compiled_worldpack.json",
            lambda value: value["runtime_bindings"].__setitem__(
                "target_location_id", "forged-site"
            ),
        ),
        ("initial_state.json", lambda value: value.__setitem__("seed", "forged")),
        (
            "compile_report.json",
            lambda value: value["bootstrap"].__setitem__("accepted_decisions", 99),
        ),
        (
            "bundle.json",
            lambda value: value.__setitem__("worldpack_hash", "0" * 64),
        ),
    ],
)
def test_verify_rejects_representative_artifact_tampering(bundle_dir, filename, mutation):
    _rewrite_json(bundle_dir / filename, mutation)
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_verify_rejects_unsupported_and_missing_files(bundle_dir):
    (bundle_dir / "unsupported.json").write_text("{}", encoding="utf-8")
    with pytest.raises(WorldGenError) as extra:
        verify_bundle(bundle_dir)
    assert extra.value.code == "BUNDLE_INTEGRITY_MISMATCH"

    (bundle_dir / "unsupported.json").unlink()
    (bundle_dir / "bundle.json").unlink()
    with pytest.raises(WorldGenError) as missing:
        verify_bundle(bundle_dir)
    assert missing.value.code == "BUNDLE_INTEGRITY_MISMATCH"


@pytest.mark.parametrize(
    "filename,payload",
    [
        ("bundle.json", "not json"),
        ("world_request.json", '{"schema_version": 1, "prompt": "x"}'),
    ],
)
def test_verify_rejects_non_strict_or_noncanonical_artifacts(bundle_dir, filename, payload):
    path = bundle_dir / filename
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


@pytest.mark.parametrize(
    "payload",
    [
        '{"value":NaN}',
        '{"value":Infinity}',
        '{"value":-Infinity}',
        '{"value":1,"value":2}',
    ],
)
def test_verify_rejects_noncanonical_numeric_and_duplicate_artifacts(
    bundle_dir, payload
):
    (bundle_dir / "bundle.json").write_text(payload, encoding="utf-8")

    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)

    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"
    canonical_json(error.value.error_dict()).encode("utf-8")
    canonical_json(error.value.issues_dict()).encode("utf-8")


def test_verify_rejects_invalid_utf8_artifact_with_safe_error(bundle_dir):
    (bundle_dir / "bundle.json").write_bytes(b"\xff")

    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)

    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"
    canonical_json(error.value.error_dict()).encode("utf-8")
    canonical_json(error.value.issues_dict()).encode("utf-8")


def test_verify_converts_canonical_serialization_failure(
    bundle_dir, monkeypatch
):
    def fail_serialization(_value):
        raise TypeError("forced canonical serialization failure")

    monkeypatch.setattr(bundle_module, "_canonical_utf8_json", fail_serialization)

    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)

    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"
    canonical_json(error.value.error_dict()).encode("utf-8")
    canonical_json(error.value.issues_dict()).encode("utf-8")


@pytest.mark.parametrize(
    "filename",
    [
        "world_request.json",
        "world_draft.json",
        "bundle.json",
        "initial_state.json",
        "compiled_worldpack.json",
        "compile_report.json",
    ],
)
def test_verify_rejects_escaped_surrogate_artifacts_with_safe_errors(
    bundle_dir, filename
):
    (bundle_dir / filename).write_text(
        '{"schema_version":1,"prompt":"\\ud800"}',
        encoding="utf-8",
    )

    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)

    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"
    canonical_json(error.value.error_dict()).encode("utf-8")
    canonical_json(error.value.issues_dict()).encode("utf-8")


def test_verify_reports_unreadable_bundle_directory(bundle_dir, monkeypatch):
    def fail_iterdir(_path):
        raise OSError("forced directory read failure")

    monkeypatch.setattr(Path, "iterdir", fail_iterdir)
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("data"),
        lambda value: value.__setitem__("event_seq", True),
        lambda value: value.__setitem__("seed", ""),
        lambda value: value.__setitem__("data", []),
        lambda value: value.__setitem__("game_minute", -1),
    ],
)
def test_verify_rejects_invalid_initial_state_shape_and_invariants(
    bundle_dir, mutation
):
    _rewrite_json(bundle_dir / "initial_state.json", mutation)
    _rewrite_manifest_hash(bundle_dir, "initial_state_hash", "initial_state.json")
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("seed"),
        lambda value: value.__setitem__("schema_version", 2),
        lambda value: value.__setitem__("compiler_id", "other-compiler"),
        lambda value: value.__setitem__("seed", ""),
        lambda value: value.__setitem__("request_hash", "short"),
    ],
)
def test_verify_rejects_invalid_bundle_manifest(bundle_dir, mutation):
    _rewrite_json(bundle_dir / "bundle.json", mutation)
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("filename", ["world_request.json", "world_draft.json"])
def test_verify_rejects_saved_input_that_no_longer_matches_contract(bundle_dir, filename):
    _rewrite_json(bundle_dir / filename, lambda value: value.__setitem__("extra", True))
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


@pytest.mark.parametrize(
    "filename,mutation",
    [
        ("world_request.json", lambda value: value.__setitem__("prompt", "  padded  ")),
        ("world_draft.json", lambda value: value.__setitem__("title", "  padded  ")),
    ],
)
def test_verify_rejects_non_normalized_saved_inputs(bundle_dir, filename, mutation):
    _rewrite_json(bundle_dir / filename, mutation)
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_verify_rejects_recompilation_failure(bundle_dir, monkeypatch):
    def fail_compile(*args, **kwargs):
        raise WorldGenError("BOOTSTRAP_FAILED", "forced recompilation failure")

    monkeypatch.setattr(bundle_module, "compile_world", fail_compile)
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_verify_rejects_recomputed_artifact_difference_after_hash_check(bundle_dir):
    _rewrite_json(
        bundle_dir / "compile_report.json",
        lambda value: value["bootstrap"].__setitem__("events", 99),
    )
    _rewrite_manifest_hash(bundle_dir, "compile_report_hash", "compile_report.json")
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_verify_rejects_recomputed_manifest_difference(bundle_dir, monkeypatch):
    original_payloads = bundle_module._artifact_payloads

    def forged_payloads(*args, **kwargs):
        payloads = original_payloads(*args, **kwargs)
        payloads["bundle.json"]["seed"] = "forged-seed"
        return payloads

    monkeypatch.setattr(bundle_module, "_artifact_payloads", forged_payloads)
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_verify_rejects_state_reader_mismatch(bundle_dir, monkeypatch):
    original_reader = bundle_module._read_initial_state

    def altered_reader(value):
        state = original_reader(value)
        state.game_minute += 1
        return state

    monkeypatch.setattr(bundle_module, "_read_initial_state", altered_reader)
    with pytest.raises(WorldGenError) as error:
        verify_bundle(bundle_dir)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_existing_output_directory_is_never_overwritten(tmp_path, input_files):
    request_path, draft_path = input_files
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, draft_path, "seed", output)
    assert error.value.code == "BUNDLE_ALREADY_EXISTS"
    assert marker.read_text(encoding="utf-8") == "keep"


def test_bundle_publication_error_issue_is_canonicalizable():
    error = bundle_module._already_exists_error(
        f"invalid-{chr(0xD800)}",
        chr(0xDFFF),
    )

    canonical_json(error.error_dict()).encode("utf-8")
    canonical_json(error.issues_dict()).encode("utf-8")


def test_compile_bundle_returns_both_prefixed_parse_issues(tmp_path, input_files):
    request_path, draft_path = input_files
    request_path.write_text("{not json", encoding="utf-8")
    draft_path.write_text("[not json", encoding="utf-8")
    output = tmp_path / "compiled" / "invalid-inputs"

    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, draft_path, "seed", output)

    assert error.value.code == "INVALID_JSON"
    assert [(issue.code, issue.path) for issue in error.value.issues] == [
        ("INVALID_JSON", "/draft"),
        ("INVALID_JSON", "/request"),
    ]
    assert not output.parent.exists()


def test_compile_bundle_returns_both_prefixed_schema_issues(tmp_path, input_files):
    request_path, draft_path = input_files
    request_path.write_text(
        canonical_json({"schema_version": 2, "prompt": "prompt"}),
        encoding="utf-8",
    )
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    del draft["labels"]["target"]
    draft_path.write_text(canonical_json(draft), encoding="utf-8")
    output = tmp_path / "compiled" / "schema-errors"

    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, draft_path, "seed", output)

    assert error.value.code == "INVALID_SCHEMA"
    assert [(issue.code, issue.path) for issue in error.value.issues] == [
        ("MISSING_FIELD", "/draft/labels/target"),
        ("UNSUPPORTED_SCHEMA_VERSION", "/request/schema_version"),
    ]
    assert not output.parent.exists()


def test_competing_target_is_preserved_before_locked_recheck(
    tmp_path, input_files, monkeypatch
):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "race-target"
    original_verify = bundle_module.verify_bundle
    rename_called = False

    def create_competing_target(path):
        result = original_verify(path)
        if Path(path).name.startswith(f".{output.name}.") and not output.exists():
            output.mkdir(parents=True)
            (output / "marker.txt").write_text("keep", encoding="utf-8")
        return result

    def forbidden_rename(*args, **kwargs):
        nonlocal rename_called
        rename_called = True
        raise AssertionError("rename must not run after the locked target recheck")

    monkeypatch.setattr(bundle_module, "verify_bundle", create_competing_target)
    monkeypatch.setattr(bundle_module.os, "rename", forbidden_rename)

    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, draft_path, "seed", output)

    assert error.value.code == "BUNDLE_ALREADY_EXISTS"
    assert rename_called is False
    assert (output / "marker.txt").read_text(encoding="utf-8") == "keep"
    assert not (output.parent / ".race-target.publish.lock").exists()
    assert not list(output.parent.glob(".race-target.*"))


def test_existing_publication_lock_is_preserved_and_fails_closed(
    tmp_path, input_files
):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "locked"
    output.parent.mkdir(parents=True)
    lock_path = output.parent / ".locked.publish.lock"
    lock_path.write_text("owned by another writer", encoding="utf-8")

    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, draft_path, "seed", output)

    assert error.value.code == "BUNDLE_ALREADY_EXISTS"
    assert lock_path.read_text(encoding="utf-8") == "owned by another writer"
    assert not output.exists()
    assert [path.name for path in output.parent.glob(".locked.*")] == [lock_path.name]


def test_compile_verifies_temporary_bundle_exactly_once(
    tmp_path, input_files, monkeypatch
):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "once"
    original_verify = bundle_module.verify_bundle
    calls = []

    def count_verify(path):
        calls.append(Path(path))
        return original_verify(path)

    monkeypatch.setattr(bundle_module, "verify_bundle", count_verify)
    result = compile_bundle(request_path, draft_path, "seed", output)

    assert result["ok"] is True
    assert len(calls) == 1
    assert calls[0].name.startswith(".once.")
    assert output.is_dir()


def test_two_cooperating_compilers_have_one_winner(tmp_path, input_files):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "two-writers"

    def compile_once():
        try:
            compile_bundle(request_path, draft_path, "seed", output)
            return "success"
        except WorldGenError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: compile_once(), (1, 2)))

    assert results.count("success") == 1
    assert results.count("BUNDLE_ALREADY_EXISTS") == 1
    assert verify_bundle(output)["valid"] is True
    assert not list(output.parent.glob(".two-writers.*"))


def test_invalid_input_does_not_create_output_or_sqlite(tmp_path, input_files):
    request_path, _ = input_files
    invalid_draft = write_json(tmp_path / "invalid-draft.json", {"schema_version": 1})
    output = tmp_path / "compiled" / "invalid"
    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, invalid_draft, "seed", output)
    assert error.value.code == "INVALID_SCHEMA"
    assert not output.exists()
    assert not (tmp_path / "compiled").exists()
    assert not list(tmp_path.glob("**/campaign.sqlite3"))


def test_bootstrap_failure_cleans_temporary_publication(tmp_path, input_files, monkeypatch):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "bootstrap-failure"

    def fail(*args, **kwargs):
        raise WorldGenError("BOOTSTRAP_FAILED", "forced smoke failure")

    monkeypatch.setattr(bundle_module, "compile_world", fail)
    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, draft_path, "seed", output)
    assert error.value.code == "BOOTSTRAP_FAILED"
    assert not output.exists()
    assert not (tmp_path / "compiled").exists()


def test_bundle_write_failure_cleans_temporary_sibling(tmp_path, input_files, monkeypatch):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "write-failure"
    parent = output.parent

    def fail_write(*args, **kwargs):
        raise OSError("forced write failure")

    monkeypatch.setattr(bundle_module, "_write_json", fail_write)
    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, draft_path, "seed", output)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"
    assert not output.exists()
    assert not list(parent.glob(".write-failure.*"))


def test_temporary_verification_failure_cleans_publication(tmp_path, input_files, monkeypatch):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "verification-failure"

    def fail_verify(*args, **kwargs):
        raise WorldGenError("BUNDLE_INTEGRITY_MISMATCH", "forced verification failure")

    monkeypatch.setattr(bundle_module, "verify_bundle", fail_verify)
    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, draft_path, "seed", output)
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"
    assert not output.exists()


def test_publish_race_does_not_replace_target(tmp_path, input_files, monkeypatch):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "race"
    original_rename = bundle_module.os.rename

    def race(*args, **kwargs):
        raise FileExistsError("target appeared")

    monkeypatch.setattr(bundle_module.os, "rename", race)
    with pytest.raises(WorldGenError) as error:
        compile_bundle(request_path, draft_path, "seed", output)
    assert error.value.code == "BUNDLE_ALREADY_EXISTS"
    assert not output.exists()
    monkeypatch.setattr(bundle_module.os, "rename", original_rename)


def test_missing_bundle_directory_is_machine_readable(tmp_path):
    with pytest.raises(WorldGenError) as error:
        verify_bundle(tmp_path / "missing")
    assert error.value.code == "BUNDLE_NOT_FOUND"


def test_bundle_path_diagnostic_with_surrogate_is_canonicalizable(tmp_path):
    missing = tmp_path / f"missing-{chr(0xD800)}"

    with pytest.raises(WorldGenError) as error:
        verify_bundle(missing)

    assert error.value.code == "BUNDLE_NOT_FOUND"
    canonical_json(error.value.error_dict()).encode("utf-8")
    canonical_json(error.value.issues_dict()).encode("utf-8")
