"""Bounded Phase 9B2A compiler for a detached player projection map."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..core.hashing import state_hash
from ..core.invariants import check_invariants
from ..core.models import GameState
from ..gameplay.expedition import build_observation
from ..llm_player import build_llm_decision_request
from ..worldgen import (
    DEVOUR_OVERLAY_COMPILER_ID,
    MECHANICS_PROFILE,
    verify_bundle,
)
from ..worldgen.models import ValidationIssue, WorldGenError
from .common import (
    SHA256_HEX,
    assert_canonical_utf8,
    contains_surrogate,
    error,
    has_invalid_text_controls,
    issue,
    read_json,
    safe_issue_text,
    sort_issues,
    write_json,
)
from .models import (
    PROJECTION_COMPILER_ID,
    PROJECTION_DRAFT_LABEL_FIELDS,
    PROJECTION_SCHEMA_VERSION,
    PlayerPresentation,
    PlayerProjectionMap,
    ProjectionCompilationResult,
    ProjectionDraft,
)


_SOURCE_RUNTIME_BINDINGS = {
    "base_location_id": "base-1",
    "target_location_id": "site-1",
    "resource_id": "salvage",
    "named_actor_id": "mara",
    "named_actor_fact_id": "site-1-condition",
}
_SOURCE_LABEL_FIELDS = {
    "base",
    "target",
    "resource",
    "hazard",
    "named_actor",
    "named_actor_role",
    "named_actor_public_goal",
}
_SOURCE_BUNDLE_FIELDS = {
    "schema_version",
    "compiler_id",
    "seed",
    "request_hash",
    "draft_hash",
    "worldpack_hash",
    "initial_state_hash",
    "compile_report_hash",
}
_SOURCE_WORLDPACK_FIELDS = {
    "schema_version",
    "compiler_id",
    "mechanics_profile",
    "world_id",
    "content_locale",
    "public_content",
    "runtime_bindings",
}
_SOURCE_STATE_FIELDS = {
    "schema_version",
    "event_seq",
    "decision_seq",
    "game_minute",
    "seed",
    "data",
}


@dataclass(frozen=True)
class _VerifiedSource:
    source_dir: Path
    source_bundle_compiler_id: str
    worldpack_hash: str
    initial_state_hash: str
    compiled_worldpack: dict[str, Any]
    initial_state_value: dict[str, Any]
    initial_state: GameState


def _projection_issue(
    code: str,
    path: str,
    message: str,
    expected: Any = None,
    actual: Any = None,
    allowed_values: Any = None,
) -> ValidationIssue:
    return issue(code, path, message, expected, actual, allowed_values)


def _draft_error(issues: list[ValidationIssue] | tuple[ValidationIssue, ...]) -> WorldGenError:
    return error(
        "INVALID_PROJECTION_DRAFT",
        "projection draft does not satisfy its strict supplemental contract",
        issues=sort_issues(issues),
    )


def _validate_exact_fields(
    value: Any,
    expected: set[str],
    *,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(value, dict):
        issues.append(
            _projection_issue("INVALID_TYPE", path, "value must be an object", "object", type(value).__name__)
        )
        return
    for field in sorted(set(value) - expected, key=str):
        field_path = f"{path}/{field}" if path != "/" else f"/{field}"
        issues.append(_projection_issue("UNKNOWN_FIELD", field_path, "field is not allowed", "absent", field))
    for field in sorted(expected - set(value), key=str):
        field_path = f"{path}/{field}" if path != "/" else f"/{field}"
        issues.append(_projection_issue("MISSING_FIELD", field_path, "required field is missing", "present", None))


def validate_projection_draft(
    value: Any,
) -> tuple[ProjectionDraft | None, tuple[ValidationIssue, ...]]:
    """Validate and normalize the only user-authored Phase 9B2A artifact."""

    issues: list[ValidationIssue] = []
    _validate_exact_fields(
        value,
        {"schema_version", "source_worldpack_hash", "labels"},
        path="/",
        issues=issues,
    )
    if not isinstance(value, dict):
        return None, sort_issues(issues)

    schema_version = value.get("schema_version")
    if type(schema_version) is not int or schema_version != PROJECTION_SCHEMA_VERSION:
        issues.append(
            _projection_issue(
                "UNSUPPORTED_SCHEMA_VERSION",
                "/schema_version",
                "projection schema_version must be 1",
                PROJECTION_SCHEMA_VERSION,
                schema_version,
            )
        )

    source_hash = value.get("source_worldpack_hash")
    if not isinstance(source_hash, str) or SHA256_HEX.fullmatch(source_hash) is None:
        issues.append(
            _projection_issue(
                "INVALID_WORLD_PACK_HASH",
                "/source_worldpack_hash",
                "source_worldpack_hash must be lowercase SHA-256 hex",
                "64 lowercase hexadecimal characters",
                source_hash,
            )
        )

    labels = value.get("labels")
    if not isinstance(labels, dict):
        issues.append(
            _projection_issue("INVALID_TYPE", "/labels", "labels must be an object", "object", type(labels).__name__)
        )
        labels = {}
    else:
        for field in sorted(set(labels) - PROJECTION_DRAFT_LABEL_FIELDS, key=str):
            issues.append(
                _projection_issue(
                    "UNKNOWN_FIELD",
                    f"/labels/{field}",
                    "projection draft may contain labels only from the fixed local set",
                    "absent",
                    field,
                )
            )
        for field in sorted(PROJECTION_DRAFT_LABEL_FIELDS - set(labels)):
            issues.append(
                _projection_issue(
                    "MISSING_FIELD",
                    f"/labels/{field}",
                    "required display label is missing",
                    "present",
                    None,
                )
            )

    normalized_labels: dict[str, str] = {}
    for field in sorted(PROJECTION_DRAFT_LABEL_FIELDS):
        raw = labels.get(field)
        if not isinstance(raw, str):
            issues.append(
                _projection_issue("INVALID_TYPE", f"/labels/{field}", "label must be a string", "string", type(raw).__name__)
            )
            continue
        normalized = raw.strip()
        if (
            not normalized
            or len(normalized) > 200
            or contains_surrogate(normalized)
            or has_invalid_text_controls(normalized)
        ):
            issues.append(
                _projection_issue(
                    "INVALID_TEXT",
                    f"/labels/{field}",
                    "label must be trimmed, bounded, and free of NUL, controls, and surrogate code points",
                    "trimmed Unicode string length 1..200",
                    raw,
                )
            )
        else:
            normalized_labels[field] = normalized

    ordered_issues = sort_issues(issues)
    if ordered_issues:
        return None, ordered_issues
    assert isinstance(source_hash, str)
    draft = ProjectionDraft(
        schema_version=PROJECTION_SCHEMA_VERSION,
        source_worldpack_hash=source_hash,
        labels=normalized_labels,
    )
    assert_canonical_utf8(draft.to_dict())
    return draft, ()


def load_projection_draft(path: str | Path) -> ProjectionDraft:
    """Read a draft without requiring escaped input to already be canonical."""

    try:
        value = read_json(path)
    except WorldGenError as exc:
        raise error(
            "INVALID_PROJECTION_DRAFT",
            "projection draft JSON could not be parsed",
            issues=(
                _projection_issue(
                    "INVALID_JSON",
                    "/",
                    "projection draft is not valid strict JSON",
                    "strict JSON object",
                    None,
                ),
            ),
        ) from exc
    draft, issues = validate_projection_draft(value)
    if issues or draft is None:
        raise _draft_error(issues)
    return draft


def _source_error(message: str, *, path: str = "/source_bundle", actual: Any = None) -> WorldGenError:
    return error(
        "SOURCE_BUNDLE_INVALID",
        message,
        issues=(
            _projection_issue(
                "SOURCE_BUNDLE_INVALID",
                path,
                message,
                "verified Phase 9B1 bundle",
                actual,
            ),
        ),
    )


def _read_source_artifact(root: Path, name: str) -> Any:
    path = root / name
    try:
        value = read_json(path, require_canonical=True)
        assert_canonical_utf8(value)
        return value
    except Exception as exc:
        if isinstance(exc, WorldGenError) and exc.code == "SOURCE_BUNDLE_INVALID":
            raise
        raise _source_error(
            f"source artifact {name} is not canonical UTF-8 JSON",
            path=f"/source_bundle/{name}",
            actual=name,
        ) from exc


def _verified_source(source_bundle_dir: str | Path) -> _VerifiedSource:
    """Verify the public Phase 9B1 bundle before reading any projection input."""

    root = Path(source_bundle_dir)
    try:
        verification = verify_bundle(root)
    except WorldGenError as exc:
        raise _source_error("source Phase 9B1 bundle verification failed", actual=exc.code) from exc
    except Exception as exc:
        raise _source_error("source Phase 9B1 bundle verification failed") from exc

    try:
        manifest = _read_source_artifact(root, "bundle.json")
        compiled_worldpack = _read_source_artifact(root, "compiled_worldpack.json")
        initial_state_value = _read_source_artifact(root, "initial_state.json")
    except WorldGenError:
        raise

    if not isinstance(manifest, dict) or set(manifest) != _SOURCE_BUNDLE_FIELDS:
        raise _source_error("source bundle manifest has an invalid field set", path="/source_bundle/bundle.json")
    if not isinstance(compiled_worldpack, dict) or set(compiled_worldpack) != _SOURCE_WORLDPACK_FIELDS:
        raise _source_error("compiled worldpack has an invalid field set", path="/source_bundle/compiled_worldpack.json")
    if not isinstance(initial_state_value, dict) or set(initial_state_value) != _SOURCE_STATE_FIELDS:
        raise _source_error("initial state has an invalid field set", path="/source_bundle/initial_state.json")

    worldpack_hash = manifest.get("worldpack_hash")
    initial_state_hash = manifest.get("initial_state_hash")
    if worldpack_hash != verification.get("worldpack_hash") or not isinstance(worldpack_hash, str):
        raise _source_error("source worldpack hash binding is invalid", path="/source_bundle/bundle.json", actual=worldpack_hash)
    if initial_state_hash != verification.get("initial_state_hash") or not isinstance(initial_state_hash, str):
        raise _source_error("source initial state hash binding is invalid", path="/source_bundle/bundle.json", actual=initial_state_hash)
    source_bundle_compiler_id = manifest.get("compiler_id")
    if source_bundle_compiler_id != verification.get("compiler_id"):
        raise _source_error("source bundle compiler identity is invalid", path="/source_bundle/bundle.json/compiler_id")

    if compiled_worldpack.get("mechanics_profile") != MECHANICS_PROFILE:
        raise error(
            "UNSUPPORTED_MECHANICS_PROFILE",
            "Phase 9B2A supports only the explicit phase75_expedition_v1 profile",
            path="/source_bundle/compiled_worldpack/mechanics_profile",
            expected=MECHANICS_PROFILE,
            actual=compiled_worldpack.get("mechanics_profile"),
        )
    if compiled_worldpack.get("runtime_bindings") != _SOURCE_RUNTIME_BINDINGS:
        raise _source_error(
            "source runtime bindings do not match the bounded Phase 9B2A profile",
            path="/source_bundle/compiled_worldpack/runtime_bindings",
            actual=compiled_worldpack.get("runtime_bindings"),
        )

    public_content = compiled_worldpack.get("public_content")
    if not isinstance(public_content, dict) or set(public_content) != {"labels", "premise", "title"}:
        raise _source_error("source public content has an invalid field set", path="/source_bundle/compiled_worldpack/public_content")
    labels = public_content.get("labels")
    if not isinstance(labels, dict) or set(labels) != _SOURCE_LABEL_FIELDS:
        raise _source_error("source public labels do not match the bounded profile", path="/source_bundle/compiled_worldpack/public_content/labels")
    if not all(isinstance(value, str) for value in labels.values()):
        raise _source_error("source public labels must be text", path="/source_bundle/compiled_worldpack/public_content/labels")

    try:
        initial_state = GameState(**copy.deepcopy(initial_state_value))
        check_invariants(initial_state)
    except Exception as exc:
        raise _source_error("source initial state violates engine invariants", path="/source_bundle/initial_state.json") from exc

    try:
        if state_hash(initial_state_value) != initial_state_hash:
            raise ValueError("initial state hash mismatch")
        if state_hash(compiled_worldpack) != worldpack_hash:
            raise ValueError("compiled worldpack hash mismatch")
        assert_canonical_utf8(compiled_worldpack)
        assert_canonical_utf8(initial_state_value)
    except Exception as exc:
        raise _source_error("source hashes or canonical artifacts are invalid") from exc

    return _VerifiedSource(
        source_dir=root,
        source_bundle_compiler_id=source_bundle_compiler_id,
        worldpack_hash=worldpack_hash,
        initial_state_hash=initial_state_hash,
        compiled_worldpack=copy.deepcopy(compiled_worldpack),
        initial_state_value=copy.deepcopy(initial_state_value),
        initial_state=initial_state,
    )


def _coerce_draft(value: ProjectionDraft | Mapping[str, Any] | str | Path) -> ProjectionDraft:
    if isinstance(value, (str, Path)):
        return load_projection_draft(value)
    payload = value.to_dict() if isinstance(value, ProjectionDraft) else value
    draft, issues = validate_projection_draft(payload)
    if issues or draft is None:
        raise _draft_error(issues)
    return draft


def _build_projection(source: _VerifiedSource, draft: ProjectionDraft) -> PlayerProjectionMap:
    worldpack = source.compiled_worldpack
    public_content = worldpack["public_content"]
    source_labels = public_content["labels"]
    labels = draft.labels

    identities = {
        "locations": {
            "base-1": source_labels["base"],
            "site-1": source_labels["target"],
        },
        "resources": {
            "parts": labels["secondary_resource"],
            "salvage": source_labels["resource"],
        },
        "actors": {
            "mara": {
                "name": source_labels["named_actor"],
                "role": source_labels["named_actor_role"],
            }
        },
        "actor_goals": {
            "inspect_signal": source_labels["named_actor_public_goal"],
            "report_finding": labels["actor_report_goal"],
            "reported": labels["actor_reported_goal"],
        },
        "facts": {
            "site-1-condition": {
                "subject": labels["site_condition_subject"],
                "values": {
                    "safe": labels["site_condition_safe"],
                    "unstable": labels["site_condition_unstable"],
                },
            }
        },
        "progression_tracks": {
            "base": labels["base_track"],
            "player": labels["player_track"],
        },
        "builds": {
            "field_rest": labels["build_field_rest"],
            "quick_rest": labels["build_quick_rest"],
            "window_runner": labels["build_window_runner"],
        },
        "world_phases": {
            "DAY": labels["phase_day"],
            "NIGHT": labels["phase_night"],
        },
    }
    if source.source_bundle_compiler_id == DEVOUR_OVERLAY_COMPILER_ID:
        identities["capabilities"] = {"devour_evolution": "Devour Evolution"}

    projection = PlayerProjectionMap(
        schema_version=PROJECTION_SCHEMA_VERSION,
        projection_compiler_id=PROJECTION_COMPILER_ID,
        mechanics_profile=MECHANICS_PROFILE,
        source_worldpack_hash=source.worldpack_hash,
        source_initial_state_hash=source.initial_state_hash,
        content_locale=worldpack["content_locale"],
        world={
            "world_id": worldpack["world_id"],
            "title": public_content["title"],
            "premise": public_content["premise"],
            "hazard": source_labels["hazard"],
        },
        identities=identities,
    )
    assert_canonical_utf8(projection.to_dict())
    return projection


def _mapped_identity_count(projection: PlayerProjectionMap) -> int:
    identities = projection.identities
    return (
        len(identities["locations"])
        + len(identities["resources"])
        + len(identities["actors"])
        + len(identities["actor_goals"])
        + len(identities["facts"])
        + sum(len(fact["values"]) for fact in identities["facts"].values())
        + len(identities["progression_tracks"])
        + len(identities["builds"])
        + len(identities["world_phases"])
        + len(identities.get("capabilities", {}))
    )


def projection_hash(projection: PlayerProjectionMap | Mapping[str, Any]) -> str:
    value = projection.to_dict() if isinstance(projection, PlayerProjectionMap) else copy.deepcopy(projection)
    from .common import sha256_json

    return sha256_json(value)


def presentation_hash(presentation: PlayerPresentation | Mapping[str, Any]) -> str:
    value = presentation.to_dict() if isinstance(presentation, PlayerPresentation) else copy.deepcopy(presentation)
    from .common import sha256_json

    return sha256_json(value)


def build_initial_request(state: GameState):
    """Materialize only the public initial Observation into the Phase 8 request."""

    return build_llm_decision_request(build_observation(state), 1)


def _compile_projection_from_verified_source(
    source: _VerifiedSource,
    normalized_draft: ProjectionDraft,
) -> ProjectionCompilationResult:
    if normalized_draft.source_worldpack_hash != source.worldpack_hash:
        raise error(
            "SOURCE_HASH_MISMATCH",
            "projection draft source_worldpack_hash does not match the verified source bundle",
            path="/source_worldpack_hash",
            expected=source.worldpack_hash,
            actual=normalized_draft.source_worldpack_hash,
        )

    projection = _build_projection(source, normalized_draft)
    projection_digest = projection_hash(projection)
    request = build_initial_request(source.initial_state)
    from .presenter import build_player_presentation

    presentation = build_player_presentation(request, projection)
    presentation_digest = presentation_hash(presentation)
    report = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "valid": True,
        "projection_compiler_id": PROJECTION_COMPILER_ID,
        "source_worldpack_hash": source.worldpack_hash,
        "source_initial_state_hash": source.initial_state_hash,
        "mapped_identity_count": _mapped_identity_count(projection),
        "unmapped_identity_count": 0,
        "initial_request_fingerprint": request.request_fingerprint,
        "initial_presentation_hash": presentation_digest,
    }
    if source.source_bundle_compiler_id == DEVOUR_OVERLAY_COMPILER_ID:
        report["source_bundle_compiler_id"] = DEVOUR_OVERLAY_COMPILER_ID
    assert_canonical_utf8(report)
    result = ProjectionCompilationResult(
        draft=normalized_draft,
        projection=projection,
        projection_hash=projection_digest,
        initial_request=request,
        initial_presentation=presentation,
        presentation_hash=presentation_digest,
        report=report,
    )
    assert_canonical_utf8(result.to_dict())
    return result


def compile_projection(
    source_bundle_dir: str | Path,
    draft: ProjectionDraft | Mapping[str, Any] | str | Path,
) -> ProjectionCompilationResult:
    """Verify source, compile one local projection, and never write files."""

    source = _verified_source(source_bundle_dir)
    normalized_draft = _coerce_draft(draft)
    return _compile_projection_from_verified_source(source, normalized_draft)


__all__ = [
    "PROJECTION_COMPILER_ID",
    "PROJECTION_DRAFT_LABEL_FIELDS",
    "PROJECTION_SCHEMA_VERSION",
    "build_initial_request",
    "compile_projection",
    "load_projection_draft",
    "presentation_hash",
    "projection_hash",
    "validate_projection_draft",
]
