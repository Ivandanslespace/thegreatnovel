"""Canonical compiled-bundle publication and verification for Phase 9B1."""

from __future__ import annotations

import copy
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..core.hashing import canonical_json, state_hash
from ..core.invariants import check_invariants
from ..core.models import GameState
from .compiler import (
    COMPILER_ID,
    compile_world,
    load_draft,
    load_request,
    parse_strict_json,
    prefix_validation_issues,
    sort_validation_issues,
    validate_draft,
    validate_request,
)
from .models import CompilationResult, ValidationIssue, WorldGenError


BUNDLE_FILES = frozenset(
    {
        "bundle.json",
        "world_request.json",
        "world_draft.json",
        "compiled_worldpack.json",
        "initial_state.json",
        "compile_report.json",
    }
)
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _integrity_issue(message: str, actual: Any = None) -> ValidationIssue:
    return ValidationIssue(
        code="BUNDLE_INTEGRITY_MISMATCH",
        path="/",
        message=message,
        expected="verified canonical compiled bundle",
        actual=actual,
        allowed_values=None,
    )


def _bundle_error(message: str, *, actual: Any = None) -> WorldGenError:
    return WorldGenError(
        "BUNDLE_INTEGRITY_MISMATCH",
        message,
        issues=(_integrity_issue(message, actual),),
    )


def _canonical_utf8_json(value: Any) -> str:
    payload = canonical_json(value)
    payload.encode("utf-8")
    return payload


def _publication_lock_path(target: Path) -> Path:
    return target.parent / f".{target.name}.publish.lock"


def _already_exists_error(message: str, actual: Any) -> WorldGenError:
    return WorldGenError(
        "BUNDLE_ALREADY_EXISTS",
        message,
        issues=(
            ValidationIssue(
                code="BUNDLE_ALREADY_EXISTS",
                path="/output-dir",
                message=message,
                expected="absent output and publication lock",
                actual=actual,
                allowed_values=None,
            ),
        ),
    )


def _read_canonical_json(path: Path) -> Any:
    try:
        payload = path.read_text(encoding="utf-8")
        parsed = parse_strict_json(payload)
    except Exception as exc:
        raise _bundle_error(f"cannot read strict JSON artifact {path.name}") from exc
    if _canonical_utf8_json(parsed) != payload:
        raise _bundle_error(f"artifact {path.name} is not canonical JSON")
    return parsed


def _write_json(path: Path, value: Any) -> None:
    path.write_text(_canonical_utf8_json(value), encoding="utf-8")


def _artifact_payloads(compilation: CompilationResult, seed: str) -> dict[str, Any]:
    request = compilation.request.to_dict()
    draft = compilation.draft.to_dict()
    worldpack = compilation.compiled_worldpack.to_dict()
    initial_state = copy.deepcopy(compilation.initial_state.__dict__)
    report = copy.deepcopy(compilation.report)
    report_hash = state_hash(report)
    bundle = {
        "schema_version": 1,
        "compiler_id": COMPILER_ID,
        "seed": seed,
        "request_hash": state_hash(request),
        "draft_hash": state_hash(draft),
        "worldpack_hash": state_hash(worldpack),
        "initial_state_hash": state_hash(initial_state),
        "compile_report_hash": report_hash,
    }
    return {
        "bundle.json": bundle,
        "world_request.json": request,
        "world_draft.json": draft,
        "compiled_worldpack.json": worldpack,
        "initial_state.json": initial_state,
        "compile_report.json": report,
    }


def _read_initial_state(value: Any) -> GameState:
    expected_fields = {
        "schema_version",
        "event_seq",
        "decision_seq",
        "game_minute",
        "seed",
        "data",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise _bundle_error("initial_state.json has an invalid GameState field set")
    for field in ("schema_version", "event_seq", "decision_seq", "game_minute"):
        if type(value[field]) is not int:
            raise _bundle_error(f"initial_state.json field {field} is not a strict integer")
    if not isinstance(value["seed"], str) or not value["seed"] or "\x00" in value["seed"]:
        raise _bundle_error("initial_state.json seed is invalid")
    if not isinstance(value["data"], dict):
        raise _bundle_error("initial_state.json data is not an object")
    try:
        state = GameState(**copy.deepcopy(value))
        check_invariants(state)
    except Exception as exc:
        raise _bundle_error("initial_state.json violates engine invariants") from exc
    return state


def _read_bundle_artifacts(bundle_dir: Path) -> dict[str, Any]:
    if not bundle_dir.is_dir():
        raise WorldGenError(
            "BUNDLE_NOT_FOUND",
            "compiled bundle directory does not exist",
            issues=(
                ValidationIssue(
                    code="BUNDLE_NOT_FOUND",
                    path="/bundle",
                    message="compiled bundle directory does not exist",
                    expected="directory",
                    actual=str(bundle_dir),
                    allowed_values=None,
                ),
            ),
        )
    try:
        actual_files = {path.name for path in bundle_dir.iterdir()}
    except OSError as exc:
        raise _bundle_error("cannot inspect compiled bundle directory") from exc
    if actual_files != BUNDLE_FILES:
        raise _bundle_error(
            "compiled bundle has an unsupported or missing file",
            actual=sorted(actual_files ^ BUNDLE_FILES),
        )
    return {
        name: _read_canonical_json(bundle_dir / name)
        for name in sorted(BUNDLE_FILES)
    }


def _validate_bundle_manifest(manifest: Any) -> None:
    fields = {
        "schema_version",
        "compiler_id",
        "seed",
        "request_hash",
        "draft_hash",
        "worldpack_hash",
        "initial_state_hash",
        "compile_report_hash",
    }
    if not isinstance(manifest, dict) or set(manifest) != fields:
        raise _bundle_error("bundle.json has an invalid field set")
    if manifest["schema_version"] != 1 or type(manifest["schema_version"]) is not int:
        raise _bundle_error("bundle.json schema_version is unsupported")
    if manifest["compiler_id"] != COMPILER_ID:
        raise _bundle_error("bundle.json compiler_id is unsupported")
    if not isinstance(manifest["seed"], str) or not manifest["seed"] or "\x00" in manifest["seed"]:
        raise _bundle_error("bundle.json seed is invalid")
    for field in (
        "request_hash",
        "draft_hash",
        "worldpack_hash",
        "initial_state_hash",
        "compile_report_hash",
    ):
        value = manifest[field]
        if not isinstance(value, str) or _SHA256_HEX.fullmatch(value) is None:
            raise _bundle_error(f"bundle.json {field} is not a SHA-256 hex string")


def verify_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    """Fail closed after re-reading and rebuilding every deterministic artifact."""

    root = Path(bundle_dir)
    artifacts = _read_bundle_artifacts(root)
    manifest = artifacts["bundle.json"]
    _validate_bundle_manifest(manifest)

    request, request_issues = validate_request(artifacts["world_request.json"])
    draft, draft_issues = validate_draft(artifacts["world_draft.json"])
    if request_issues or draft_issues or request is None or draft is None:
        issues = sort_validation_issues(
            list(prefix_validation_issues(request_issues, "/request"))
            + list(prefix_validation_issues(draft_issues, "/draft"))
        )
        raise WorldGenError(
            "BUNDLE_INTEGRITY_MISMATCH",
            "saved request or draft no longer satisfies its contract",
            issues=issues or (_integrity_issue("saved request or draft is invalid"),),
        )
    if request.to_dict() != artifacts["world_request.json"]:
        raise _bundle_error("world_request.json is not normalized to its saved artifact")
    if draft.to_dict() != artifacts["world_draft.json"]:
        raise _bundle_error("world_draft.json is not normalized to its saved artifact")

    if manifest["request_hash"] != state_hash(artifacts["world_request.json"]):
        raise _bundle_error("request_hash mismatch")
    if manifest["draft_hash"] != state_hash(artifacts["world_draft.json"]):
        raise _bundle_error("draft_hash mismatch")
    if manifest["worldpack_hash"] != state_hash(artifacts["compiled_worldpack.json"]):
        raise _bundle_error("worldpack_hash mismatch")
    if manifest["initial_state_hash"] != state_hash(artifacts["initial_state.json"]):
        raise _bundle_error("initial_state_hash mismatch")
    if manifest["compile_report_hash"] != state_hash(artifacts["compile_report.json"]):
        raise _bundle_error("compile_report_hash mismatch")

    initial_state = _read_initial_state(artifacts["initial_state.json"])
    try:
        compilation = compile_world(request, draft, manifest["seed"])
    except WorldGenError as exc:
        raise _bundle_error("recompilation failed during bundle verification") from exc
    expected = _artifact_payloads(compilation, manifest["seed"])
    for name in BUNDLE_FILES - {"bundle.json"}:
        if artifacts[name] != expected[name]:
            raise _bundle_error(f"recomputed artifact differs: {name}")
    if artifacts["bundle.json"] != expected["bundle.json"]:
        raise _bundle_error("bundle.json bindings differ from recomputed artifacts")
    if initial_state.__dict__ != compilation.initial_state.__dict__:
        raise _bundle_error("initial_state.json differs from rematerialized state")

    return {
        "valid": True,
        "compiler_id": COMPILER_ID,
        "world_id": draft.world_id,
        "worldpack_hash": manifest["worldpack_hash"],
        "initial_state_hash": manifest["initial_state_hash"],
    }


def compile_bundle(
    request_path: str | Path,
    draft_path: str | Path,
    seed: str,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Compile and atomically publish one verified bundle."""

    target = Path(output_dir)
    if target.exists():
        raise _already_exists_error(
            "output directory already exists",
            str(target),
        )

    request = load_request(str(request_path))
    draft = load_draft(str(draft_path))
    compilation = compile_world(request, draft, seed)
    artifacts = _artifact_payloads(compilation, seed)

    temporary_dir: Path | None = None
    temporary_verification: dict[str, Any] | None = None
    lock_path = _publication_lock_path(target)
    lock_created = False
    lock_fd: int | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_dir = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent)
        )
        for name, value in artifacts.items():
            _write_json(temporary_dir / name, value)
        temporary_verification = verify_bundle(temporary_dir)
        try:
            lock_fd = os.open(
                str(lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            lock_created = True
            os.close(lock_fd)
            lock_fd = None
        except FileExistsError as exc:
            raise _already_exists_error(
                "publication lock already exists; another cooperating compiler may be publishing",
                str(lock_path),
            ) from exc
        if target.exists():
            raise _already_exists_error(
                "output directory appeared before locked publication; target was preserved",
                str(target),
            )
        try:
            os.rename(temporary_dir, target)
        except FileExistsError as exc:
            raise _already_exists_error(
                "output directory appeared during atomic publication",
                str(target),
            ) from exc
        temporary_dir = None
    except WorldGenError:
        raise
    except Exception as exc:
        raise _bundle_error("compiled bundle publication failed") from exc
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        if lock_created:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
        if temporary_dir is not None:
            shutil.rmtree(temporary_dir, ignore_errors=True)

    assert temporary_verification is not None
    return {
        "ok": True,
        "valid": True,
        "bundle_dir": str(target),
        "preview": {
            "compiler_id": temporary_verification["compiler_id"],
            "world_id": temporary_verification["world_id"],
            "worldpack_hash": temporary_verification["worldpack_hash"],
            "initial_state_hash": temporary_verification["initial_state_hash"],
        },
    }
