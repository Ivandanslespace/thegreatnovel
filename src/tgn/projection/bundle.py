"""Atomic four-file publication and verification for the projection sidecar."""

from __future__ import annotations

import copy
import ctypes
import errno
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ..worldgen.models import WorldGenError
from .common import (
    SHA256_HEX,
    assert_canonical_utf8,
    canonical_payload,
    error,
    issue,
    read_json,
    sha256_json,
    write_json,
)
from .compiler import (
    _compile_projection_from_verified_source,
    _verified_source,
    load_projection_draft,
    presentation_hash,
    projection_hash,
    validate_projection_draft,
)
from .models import PlayerProjectionMap, ProjectionCompilationResult, ProjectionDraft


PROJECTION_FILES = frozenset(
    {
        "projection_manifest.json",
        "projection_draft.json",
        "player_projection.json",
        "projection_report.json",
    }
)


def _publication_lock_path(target: Path) -> Path:
    return target.parent / f".{target.name}.publish.lock"


def publication_lock_path(target: str | Path) -> Path:
    """Return the deterministic cooperative-writer lock path."""

    return _publication_lock_path(Path(target))


def _bundle_issue(message: str, path: str = "/projection", actual: Any = None):
    return issue(
        "PROJECTION_INTEGRITY_MISMATCH",
        path,
        message,
        "verified canonical projection bundle",
        actual,
    )


def _bundle_error(message: str, *, path: str = "/projection", actual: Any = None) -> WorldGenError:
    return error(
        "PROJECTION_INTEGRITY_MISMATCH",
        message,
        issues=(_bundle_issue(message, path, actual),),
    )


def _not_found_error(path: Path) -> WorldGenError:
    return error(
        "PROJECTION_NOT_FOUND",
        "projection bundle directory does not exist",
        path="/projection",
        expected="directory",
        actual=str(path),
    )


def _already_exists_error(message: str, actual: Any) -> WorldGenError:
    return error(
        "PROJECTION_ALREADY_EXISTS",
        message,
        path="/output-dir",
        expected="absent target and publication lock",
        actual=actual,
    )


class _NoReplaceUnavailable(RuntimeError):
    """The host does not expose a safe atomic directory no-replace primitive."""


def _publish_directory_no_replace(source: Path, target: Path) -> None:
    """Atomically move a sibling directory without replacing an existing target."""

    if os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            move_file = kernel32.MoveFileExW
            move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
            move_file.restype = ctypes.c_int
            # Omitting MOVEFILE_REPLACE_EXISTING is the Windows no-replace mode.
            if move_file(str(source), str(target), 0x00000008) == 0:
                error_number = ctypes.get_last_error()
                if error_number in {80, 183}:
                    raise FileExistsError(error_number, "target already exists", str(target))
                raise OSError(error_number, "atomic directory publication failed", str(target))
            return
        except FileExistsError:
            raise
        except (AttributeError, OSError) as exc:
            raise _NoReplaceUnavailable("Windows atomic no-replace publication is unavailable") from exc

    if sys.platform.startswith("linux"):
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2")
            renameat2.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameat2.restype = ctypes.c_int
            result = renameat2(
                -100,
                os.fsencode(source),
                -100,
                os.fsencode(target),
                1,
            )
            if result == 0:
                return
            error_number = ctypes.get_errno()
            if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
                raise FileExistsError(error_number, "target already exists", str(target))
            raise OSError(error_number, "atomic directory publication failed", str(target))
        except FileExistsError:
            raise
        except (AttributeError, OSError) as exc:
            raise _NoReplaceUnavailable("Linux renameat2(RENAME_NOREPLACE) is unavailable") from exc

    if sys.platform == "darwin":
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            renameatx_np = getattr(libc, "renameatx_np")
            renameatx_np.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameatx_np.restype = ctypes.c_int
            result = renameatx_np(
                -2,
                os.fsencode(source),
                -2,
                os.fsencode(target),
                0x00000004,
            )
            if result == 0:
                return
            error_number = ctypes.get_errno()
            if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
                raise FileExistsError(error_number, "target already exists", str(target))
            raise OSError(error_number, "atomic directory publication failed", str(target))
        except FileExistsError:
            raise
        except (AttributeError, OSError) as exc:
            raise _NoReplaceUnavailable("macOS renameatx_np(RENAME_EXCL) is unavailable") from exc

    raise _NoReplaceUnavailable("host platform has no supported atomic no-replace directory primitive")


def _read_projection_artifacts(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise _not_found_error(root)
    try:
        actual_files = {item.name for item in root.iterdir()}
    except OSError as exc:
        raise _bundle_error("cannot inspect projection bundle directory") from exc
    if actual_files != PROJECTION_FILES:
        raise _bundle_error(
            "projection bundle must contain exactly four canonical files",
            actual=sorted(actual_files ^ PROJECTION_FILES),
        )
    artifacts: dict[str, Any] = {}
    for name in sorted(PROJECTION_FILES):
        try:
            artifacts[name] = read_json(root / name, require_canonical=True)
            assert_canonical_utf8(artifacts[name])
        except WorldGenError as exc:
            raise _bundle_error(
                f"projection artifact {name} is not canonical JSON",
                path=f"/projection/{name}",
            ) from exc
        except Exception as exc:
            raise _bundle_error(
                f"projection artifact {name} is not canonical JSON",
                path=f"/projection/{name}",
            ) from exc
    return artifacts


def _validate_manifest(manifest: Any) -> None:
    expected_fields = {
        "schema_version",
        "projection_compiler_id",
        "source_worldpack_hash",
        "source_initial_state_hash",
        "projection_draft_hash",
        "player_projection_hash",
        "projection_report_hash",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_fields:
        raise _bundle_error("projection_manifest.json has an invalid field set", path="/projection/projection_manifest.json")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise _bundle_error("projection manifest schema_version is unsupported", path="/projection/projection_manifest.json/schema_version")
    if manifest["projection_compiler_id"] != "phase9b2a-player-projection-v1":
        raise _bundle_error("projection compiler id is unsupported", path="/projection/projection_manifest.json/projection_compiler_id")
    for field in (
        "source_worldpack_hash",
        "source_initial_state_hash",
        "projection_draft_hash",
        "player_projection_hash",
        "projection_report_hash",
    ):
        value = manifest[field]
        if not isinstance(value, str) or SHA256_HEX.fullmatch(value) is None:
            raise _bundle_error(
                f"projection manifest {field} is not lowercase SHA-256 hex",
                path=f"/projection/projection_manifest.json/{field}",
                actual=value,
            )


def _artifact_payloads(result: ProjectionCompilationResult) -> dict[str, Any]:
    draft = result.draft.to_dict()
    projection = result.projection.to_dict()
    report = copy.deepcopy(result.report)
    manifest = {
        "schema_version": 1,
        "projection_compiler_id": "phase9b2a-player-projection-v1",
        "source_worldpack_hash": result.projection.source_worldpack_hash,
        "source_initial_state_hash": result.projection.source_initial_state_hash,
        "projection_draft_hash": sha256_json(draft),
        "player_projection_hash": result.projection_hash,
        "projection_report_hash": sha256_json(report),
    }
    return {
        "projection_manifest.json": manifest,
        "projection_draft.json": draft,
        "player_projection.json": projection,
        "projection_report.json": report,
    }


def _coerce_draft_input(value: ProjectionDraft | Mapping[str, Any] | str | Path) -> ProjectionDraft:
    if isinstance(value, (str, Path)):
        return load_projection_draft(value)
    payload = value.to_dict() if isinstance(value, ProjectionDraft) else value
    draft, issues = validate_projection_draft(payload)
    if issues or draft is None:
        raise error(
            "INVALID_PROJECTION_DRAFT",
            "projection draft does not satisfy its strict supplemental contract",
            issues=issues,
        )
    return draft


def _verify_projection_bundle_with_source(
    source: Any,
    projection_dir: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], ProjectionCompilationResult]:
    """Verify projection artifacts against one already verified source snapshot."""

    root = Path(projection_dir)
    artifacts = _read_projection_artifacts(root)
    manifest = artifacts["projection_manifest.json"]
    _validate_manifest(manifest)

    draft, draft_issues = validate_projection_draft(artifacts["projection_draft.json"])
    if draft_issues or draft is None:
        raise _bundle_error("saved projection draft is invalid", path="/projection/projection_draft.json")
    try:
        expected = _compile_projection_from_verified_source(source, draft)
    except WorldGenError as exc:
        if exc.code == "SOURCE_HASH_MISMATCH":
            raise _bundle_error("projection draft source hash does not match source bundle") from exc
        raise _bundle_error("projection cannot be deterministically recompiled") from exc
    except Exception as exc:
        raise _bundle_error("projection cannot be deterministically recompiled") from exc

    expected_artifacts = _artifact_payloads(expected)
    for name in sorted(PROJECTION_FILES):
        if artifacts[name] != expected_artifacts[name]:
            raise _bundle_error(
                f"recomputed projection artifact differs: {name}",
                path=f"/projection/{name}",
            )
    if manifest["source_worldpack_hash"] != expected.projection.source_worldpack_hash:
        raise _bundle_error("source_worldpack_hash does not match verified source")
    if manifest["source_initial_state_hash"] != expected.projection.source_initial_state_hash:
        raise _bundle_error("source_initial_state_hash does not match verified source")

    verification = {
        "valid": True,
        "projection_compiler_id": "phase9b2a-player-projection-v1",
        "source_worldpack_hash": expected.projection.source_worldpack_hash,
        "source_initial_state_hash": expected.projection.source_initial_state_hash,
        "projection_hash": expected.projection_hash,
        "initial_request_fingerprint": expected.initial_request.request_fingerprint,
        "initial_presentation_hash": expected.presentation_hash,
    }
    return verification, artifacts, expected


def verify_projection_bundle(
    source_bundle_dir: str | Path,
    projection_dir: str | Path,
) -> dict[str, Any]:
    """Re-verify source, projection draft, map, report, and all hashes."""

    source = _verified_source(source_bundle_dir)
    verification, _, _ = _verify_projection_bundle_with_source(source, projection_dir)
    return verification


def compile_projection_bundle(
    source_bundle_dir: str | Path,
    draft: ProjectionDraft | Mapping[str, Any] | str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Compile and publish exactly one verified projection sidecar."""

    source = _verified_source(source_bundle_dir)
    normalized_draft = _coerce_draft_input(draft)
    target = Path(output_dir)
    lock_path = _publication_lock_path(target)
    if target.exists():
        raise _already_exists_error("projection output directory already exists", str(target))
    if lock_path.exists():
        raise _already_exists_error("projection publication lock already exists", str(lock_path))

    result = _compile_projection_from_verified_source(source, normalized_draft)
    artifacts = _artifact_payloads(result)
    temporary_dir: Path | None = None
    lock_created = False
    lock_fd: int | None = None
    temporary_verification: dict[str, Any] | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_dir = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
        for name, value in artifacts.items():
            write_json(temporary_dir / name, value)

        # Verify exactly once before publication. A successful rename does not
        # change directory contents, so a second post-publication verification
        # would create a published-but-reported-failure state.
        temporary_verification, _, _ = _verify_projection_bundle_with_source(source, temporary_dir)

        try:
            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            lock_created = True
            os.close(lock_fd)
            lock_fd = None
        except FileExistsError as exc:
            raise _already_exists_error(
                "projection publication lock already exists; cooperating writer is active",
                str(lock_path),
            ) from exc

        if target.exists():
            raise _already_exists_error(
                "projection output appeared before locked publication; target was preserved",
                str(target),
            )
        try:
            _publish_directory_no_replace(temporary_dir, target)
        except FileExistsError as exc:
            raise _already_exists_error(
                "projection output appeared during atomic publication; target was preserved",
                str(target),
            ) from exc
        except _NoReplaceUnavailable as exc:
            raise _bundle_error(
                "atomic no-replace directory publication is unavailable on this platform"
            ) from exc
        temporary_dir = None
    except WorldGenError:
        raise
    except Exception as exc:
        raise _bundle_error("projection bundle publication failed") from exc
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
        "projection_dir": str(target),
        "verification": copy.deepcopy(temporary_verification),
    }


def preview_projection(
    source_bundle_dir: str | Path,
    projection_dir: str | Path,
) -> dict[str, Any]:
    """Verify an existing projection and return detached initial edge data."""

    source = _verified_source(source_bundle_dir)
    verification, _, result = _verify_projection_bundle_with_source(source, projection_dir)
    return {
        "verification": verification,
        "request": result.initial_request.to_dict(),
        "presentation": result.initial_presentation.to_dict(),
        "projection_hash": result.projection_hash,
        "presentation_hash": result.presentation_hash,
    }


__all__ = [
    "PROJECTION_FILES",
    "compile_projection_bundle",
    "preview_projection",
    "publication_lock_path",
    "verify_projection_bundle",
]
