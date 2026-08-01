"""Deterministic, bounded compiler for the Phase 9B1 world slice."""

from __future__ import annotations

import copy
import json
import math
import re
import unicodedata
from typing import Any, Iterable, Mapping

from ..actions.models import ActionIntent
from ..autoplay.models import AutoplayConfig
from ..autoplay.runner import run_autoplay
from ..core.hashing import canonical_json, state_hash
from ..core.invariants import check_invariants
from ..core.models import GameState
from ..gameplay.expedition import build_observation, get_legal_actions
from ..gameplay.named_actor import (
    MARA_ACTOR_ID,
    MARA_AUTONOMOUS_ACTION,
    MARA_FACT_ID,
    MARA_INITIAL_GOAL,
    MARA_INITIAL_LOCATION_ID,
    MARA_NAME,
    TALK_TO_ACTOR,
    count_knowledge_boundary_violations,
)
from .models import (
    BootstrapResult,
    COMPILER_ID,
    DRAFT_FIELDS,
    LABEL_FIELDS,
    MECHANICS_PROFILE,
    REQUEST_FIELDS,
    CompiledWorldPack,
    CompilationResult,
    ValidationIssue,
    WorldDraft,
    WorldGenError,
    WorldGenesisRequest,
)


_STABLE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_LOCALE_TAG = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")
_TARGET_LOCATION_ID = "site-1"
_RESOURCE_ID = "salvage"
_PHASE_CYCLE = {
    "cycle_minutes": 120,
    "boundary_minute": 60,
    "phase_before": "DAY",
    "phase_after": "NIGHT",
    "blocked_actions_by_phase": {"NIGHT": ["DROP"]},
}
_BUILD_CANDIDATES = ["window_runner", "field_rest", "quick_rest"]


class _StrictJSONError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _StrictJSONError("INVALID_JSON", f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise _StrictJSONError(
        "NON_CANONICAL_JSON_VALUE",
        f"non-standard JSON number: {value}",
    )


def _find_nonfinite(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_find_nonfinite(item) for item in value.values())
    if isinstance(value, list):
        return any(_find_nonfinite(item) for item in value)
    return False


def _contains_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _surrogate_code_points(value: str) -> list[str]:
    return sorted({f"U+{ord(character):04X}" for character in value if 0xD800 <= ord(character) <= 0xDFFF})


def _safe_issue_text(value: str) -> str:
    if _contains_surrogate(value):
        return "contains invalid Unicode surrogate " + ", ".join(_surrogate_code_points(value))
    return value


def _safe_issue_value(value: Any) -> Any:
    if isinstance(value, str):
        if _contains_surrogate(value):
            return {"invalid_code_points": _surrogate_code_points(value)}
        return value
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return {"invalid_number": repr(value)}
    if isinstance(value, Mapping):
        safe_mapping: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = _safe_issue_text(key if isinstance(key, str) else str(key))
            safe_mapping[safe_key] = _safe_issue_value(item)
        return safe_mapping
    if isinstance(value, (list, tuple)):
        return [_safe_issue_value(item) for item in value]
    return {"invalid_value_type": type(value).__name__}


def _assert_canonical_utf8(value: Any) -> None:
    canonical_json(value).encode("utf-8")


def parse_strict_json(payload: str) -> Any:
    """Parse JSON while rejecting duplicate keys and non-finite numbers."""

    if not isinstance(payload, str):
        raise _StrictJSONError("INVALID_JSON", "JSON payload must be text")
    try:
        parsed = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except _StrictJSONError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _StrictJSONError("INVALID_JSON", "payload is not valid JSON") from exc
    if _find_nonfinite(parsed):
        raise _StrictJSONError(
            "NON_CANONICAL_JSON_VALUE",
            "JSON contains a non-finite number",
        )
    return parsed


def _issue(
    code: str,
    path: str,
    message: str,
    expected: Any = None,
    actual: Any = None,
    allowed_values: Any = None,
) -> ValidationIssue:
    issue = ValidationIssue(
        code=_safe_issue_text(code),
        path=_safe_issue_text(path),
        message=_safe_issue_text(message),
        expected=_safe_issue_value(expected),
        actual=_safe_issue_value(actual),
        allowed_values=_safe_issue_value(allowed_values),
    )
    _assert_canonical_utf8(issue.to_dict())
    return issue


def _sort_issues(issues: list[ValidationIssue]) -> tuple[ValidationIssue, ...]:
    return tuple(sorted(issues, key=lambda issue: (issue.path, issue.code)))


def sort_validation_issues(
    issues: Iterable[ValidationIssue],
) -> tuple[ValidationIssue, ...]:
    return _sort_issues(list(issues))


def prefix_validation_issues(
    issues: Iterable[ValidationIssue], prefix: str
) -> tuple[ValidationIssue, ...]:
    prefixed: list[ValidationIssue] = []
    for issue in issues:
        path = issue.path
        if path in ("", "/"):
            combined_path = prefix
        elif path.startswith("/"):
            combined_path = f"{prefix}{path}"
        else:
            combined_path = f"{prefix}/{path}"
        prefixed.append(
            _issue(
                issue.code,
                combined_path,
                issue.message,
                issue.expected,
                issue.actual,
                issue.allowed_values,
            )
        )
    return sort_validation_issues(prefixed)


def _normalise_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _has_invalid_control(value: str, *, allow_newline: bool = True) -> bool:
    for character in value:
        if allow_newline and character == "\n":
            continue
        if unicodedata.category(character) == "Cc":
            return True
    return False


def _validate_text(
    value: Any,
    *,
    path: str,
    maximum: int,
    allow_newline: bool = True,
    reject_controls: bool = True,
) -> tuple[str | None, list[ValidationIssue]]:
    if not isinstance(value, str):
        return None, [
            _issue(
                "INVALID_TYPE",
                path,
                "value must be a string",
                "string",
                type(value).__name__,
            )
        ]
    normalized = _normalise_text(value)
    issues: list[ValidationIssue] = []
    if _contains_surrogate(normalized) or not normalized or len(normalized) > maximum or (
        reject_controls and _has_invalid_control(normalized, allow_newline=allow_newline)
    ):
        issues.append(
            _issue(
                "INVALID_TEXT",
                path,
                "text must be non-empty, bounded, and free of disallowed control characters",
                f"trimmed string length 1..{maximum}",
                value,
            )
        )
    return normalized, issues


def _validate_exact_fields(
    value: Any,
    fields: frozenset[str],
    *,
    path: str = "",
) -> list[ValidationIssue]:
    if not isinstance(value, dict):
        return [
            _issue(
                "INVALID_SCHEMA",
                path or "/",
                "document must be a JSON object",
                "object",
                type(value).__name__,
            )
        ]
    issues: list[ValidationIssue] = []
    for key in sorted(set(value) - fields):
        issues.append(
            _issue(
                "UNKNOWN_FIELD",
                f"{path}/{key}" if path else f"/{key}",
                "field is not supported by this contract",
                "no extra fields",
                value[key],
            )
        )
    for key in sorted(fields - set(value)):
        issues.append(
            _issue(
                "MISSING_FIELD",
                f"{path}/{key}" if path else f"/{key}",
                "required field is missing",
                "required field",
                None,
            )
        )
    return issues


def validate_request(
    value: Mapping[str, Any] | WorldGenesisRequest,
) -> tuple[WorldGenesisRequest | None, tuple[ValidationIssue, ...]]:
    mapping = value.to_dict() if isinstance(value, WorldGenesisRequest) else value
    issues = _validate_exact_fields(mapping, REQUEST_FIELDS)
    if not isinstance(mapping, dict):
        return None, _sort_issues(issues)

    schema_version = mapping.get("schema_version")
    if "schema_version" in mapping:
        if type(schema_version) is not int:
            issues.append(
                _issue(
                    "INVALID_TYPE",
                    "/schema_version",
                    "schema_version must be a strict integer",
                    "integer 1, not bool or float",
                    type(schema_version).__name__,
                )
            )
        elif schema_version != 1:
            issues.append(
                _issue(
                    "UNSUPPORTED_SCHEMA_VERSION",
                    "/schema_version",
                    "only schema_version 1 is supported",
                    1,
                    schema_version,
                    [1],
                )
            )

    prompt: str | None = None
    if "prompt" in mapping:
        prompt, prompt_issues = _validate_text(
            mapping["prompt"],
            path="/prompt",
            maximum=4000,
            reject_controls=False,
        )
        if isinstance(mapping["prompt"], str) and "\x00" in mapping["prompt"]:
            prompt_issues.append(
                _issue(
                    "INVALID_TEXT",
                    "/prompt",
                    "prompt must not contain NUL",
                    "UTF-8 string without NUL",
                    mapping["prompt"],
                )
            )
        issues.extend(prompt_issues)

    ordered = _sort_issues(issues)
    if ordered:
        return None, ordered
    assert prompt is not None
    normalized = WorldGenesisRequest(schema_version=1, prompt=prompt)
    _assert_canonical_utf8(normalized.to_dict())
    return normalized, ()


def _validate_stable_id(value: Any, path: str) -> tuple[str | None, list[ValidationIssue]]:
    if not isinstance(value, str):
        return None, [
            _issue(
                "INVALID_TYPE",
                path,
                "stable ID must be a string",
                "[a-z0-9][a-z0-9_-]{0,63}",
                type(value).__name__,
            )
        ]
    if _contains_surrogate(value):
        return None, [
            _issue(
                "INVALID_TEXT",
                path,
                "stable ID contains an invalid Unicode surrogate",
                "ASCII stable ID without surrogate code points",
                value,
            )
        ]
    if _STABLE_ID.fullmatch(value) is None:
        return None, [
            _issue(
                "INVALID_STABLE_ID",
                path,
                "stable ID does not match the supported format",
                "[a-z0-9][a-z0-9_-]{0,63}",
                value,
            )
        ]
    return value, []


def _validate_locale(value: Any) -> tuple[str | None, list[ValidationIssue]]:
    path = "/content_locale"
    if not isinstance(value, str):
        return None, [
            _issue(
                "INVALID_TYPE",
                path,
                "content_locale must be a string",
                "ASCII language tag",
                type(value).__name__,
            )
        ]
    if _contains_surrogate(value):
        return None, [
            _issue(
                "INVALID_TEXT",
                path,
                "content_locale contains an invalid Unicode surrogate",
                "ASCII language tag without surrogate code points",
                value,
            )
        ]
    if len(value) > 35 or _LOCALE_TAG.fullmatch(value) is None:
        return None, [
            _issue(
                "INVALID_LOCALE_TAG",
                path,
                "content_locale must be a simple ASCII language tag",
                "letters, digits, and hyphens; maximum length 35",
                value,
            )
        ]
    return value, []


def validate_draft(
    value: Mapping[str, Any] | WorldDraft,
) -> tuple[WorldDraft | None, tuple[ValidationIssue, ...]]:
    mapping = value.to_dict() if isinstance(value, WorldDraft) else value
    issues = _validate_exact_fields(mapping, DRAFT_FIELDS)
    if not isinstance(mapping, dict):
        return None, _sort_issues(issues)

    schema_version = mapping.get("schema_version")
    if "schema_version" in mapping:
        if type(schema_version) is not int:
            issues.append(
                _issue(
                    "INVALID_TYPE",
                    "/schema_version",
                    "schema_version must be a strict integer",
                    "integer 1, not bool or float",
                    type(schema_version).__name__,
                )
            )
        elif schema_version != 1:
            issues.append(
                _issue(
                    "UNSUPPORTED_SCHEMA_VERSION",
                    "/schema_version",
                    "only schema_version 1 is supported",
                    1,
                    schema_version,
                    [1],
                )
            )

    profile = mapping.get("mechanics_profile")
    if "mechanics_profile" in mapping:
        if not isinstance(profile, str):
            issues.append(
                _issue(
                    "INVALID_TYPE",
                    "/mechanics_profile",
                    "mechanics_profile must be a string",
                    MECHANICS_PROFILE,
                    type(profile).__name__,
                )
            )
        elif profile != MECHANICS_PROFILE:
            issues.append(
                _issue(
                    "UNSUPPORTED_MECHANICS_PROFILE",
                    "/mechanics_profile",
                    "mechanics profile is not supported by this compiler",
                    MECHANICS_PROFILE,
                    profile,
                    [MECHANICS_PROFILE],
                )
            )

    world_id = None
    if "world_id" in mapping:
        world_id, id_issues = _validate_stable_id(mapping["world_id"], "/world_id")
        issues.extend(id_issues)

    locale = None
    if "content_locale" in mapping:
        locale, locale_issues = _validate_locale(mapping["content_locale"])
        issues.extend(locale_issues)

    title = premise = None
    if "title" in mapping:
        title, title_issues = _validate_text(
            mapping["title"], path="/title", maximum=200, allow_newline=False
        )
        issues.extend(title_issues)
    if "premise" in mapping:
        premise, premise_issues = _validate_text(
            mapping["premise"], path="/premise", maximum=2000
        )
        issues.extend(premise_issues)

    labels = mapping.get("labels")
    normalized_labels: dict[str, str] | None = None
    if "labels" in mapping:
        label_issues = _validate_exact_fields(labels, LABEL_FIELDS, path="/labels")
        issues.extend(label_issues)
        if isinstance(labels, dict):
            normalized_labels = {}
            for key in sorted(LABEL_FIELDS):
                if key not in labels:
                    continue
                label, text_issues = _validate_text(
                    labels[key],
                    path=f"/labels/{key}",
                    maximum=200,
                    allow_newline=False,
                )
                issues.extend(text_issues)
                if label is not None:
                    normalized_labels[key] = label

    ordered = _sort_issues(issues)
    if ordered:
        return None, ordered
    assert (
        world_id is not None
        and locale is not None
        and title is not None
        and premise is not None
        and normalized_labels is not None
    )
    normalized = WorldDraft(
            schema_version=1,
            mechanics_profile=MECHANICS_PROFILE,
            world_id=world_id,
            content_locale=locale,
            title=title,
            premise=premise,
            labels={key: normalized_labels[key] for key in sorted(LABEL_FIELDS)},
        )
    _assert_canonical_utf8(normalized.to_dict())
    return normalized, ()


def validate_documents(
    request: Mapping[str, Any] | WorldGenesisRequest,
    draft: Mapping[str, Any] | WorldDraft,
) -> tuple[
    WorldGenesisRequest | None,
    WorldDraft | None,
    tuple[ValidationIssue, ...],
]:
    normalized_request, request_issues = validate_request(request)
    normalized_draft, draft_issues = validate_draft(draft)
    issues = sort_validation_issues(
        list(prefix_validation_issues(request_issues, "/request"))
        + list(prefix_validation_issues(draft_issues, "/draft"))
    )
    if issues:
        return None, None, issues
    return normalized_request, normalized_draft, ()


def load_and_validate_documents(
    request_path: str,
    draft_path: str,
) -> tuple[WorldGenesisRequest, WorldDraft]:
    """Load and validate both documents with combined source provenance."""

    values: dict[str, Any] = {}
    loaded: dict[str, bool] = {}
    issues: list[ValidationIssue] = []
    for source, path in (("request", request_path), ("draft", draft_path)):
        try:
            values[source] = load_document(path)
            loaded[source] = True
        except WorldGenError as exc:
            values[source] = None
            loaded[source] = False
            issues.extend(prefix_validation_issues(exc.issues, f"/{source}"))

    normalized_request: WorldGenesisRequest | None = None
    normalized_draft: WorldDraft | None = None
    if loaded.get("request"):
        normalized_request, request_issues = validate_request(values["request"])
        issues.extend(prefix_validation_issues(request_issues, "/request"))
    if loaded.get("draft"):
        normalized_draft, draft_issues = validate_draft(values["draft"])
        issues.extend(prefix_validation_issues(draft_issues, "/draft"))

    ordered = sort_validation_issues(issues)
    if ordered:
        parse_codes = {"INVALID_JSON", "NON_CANONICAL_JSON_VALUE"}
        code = ordered[0].code if all(issue.code in parse_codes for issue in ordered) else "INVALID_SCHEMA"
        raise WorldGenError(
            code,
            "input validation failed",
            issues=ordered,
        )
    assert normalized_request is not None and normalized_draft is not None
    return normalized_request, normalized_draft


def load_document(path: str) -> Any:
    """Read one strict UTF-8 JSON document at the worldgen boundary."""

    from pathlib import Path

    try:
        payload = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise WorldGenError(
            "INVALID_JSON",
            f"cannot read JSON input: {Path(path).name}",
            issues=(
                _issue(
                    "INVALID_JSON",
                    "/",
                    "input must be readable UTF-8 JSON",
                    "UTF-8 JSON file",
                    str(exc),
                ),
            ),
        ) from exc
    try:
        return parse_strict_json(payload)
    except _StrictJSONError as exc:
        message = _safe_issue_text(str(exc))
        raise WorldGenError(
            exc.code,
            message,
            issues=(_issue(exc.code, "/", message, "strict JSON", None),),
        ) from exc


def load_request(path: str) -> WorldGenesisRequest:
    value = load_document(path)
    request, issues = validate_request(value)
    if issues or request is None:
        raise WorldGenError("INVALID_SCHEMA", "World Genesis Request is invalid", issues=issues)
    return request


def load_draft(path: str) -> WorldDraft:
    value = load_document(path)
    draft, issues = validate_draft(value)
    if issues or draft is None:
        raise WorldGenError("INVALID_SCHEMA", "World Draft is invalid", issues=issues)
    return draft


def _validate_seed(seed: Any) -> str:
    if not isinstance(seed, str) or not seed or "\x00" in seed or _contains_surrogate(seed):
        raise WorldGenError(
            "INVALID_TEXT",
            "seed must be a non-empty string without NUL",
            issues=(
                _issue(
                    "INVALID_TEXT",
                    "/seed",
                    "seed must be a non-empty string without NUL",
                    "non-empty string",
                    seed,
                ),
            ),
        )
    return seed


def _coerce_request(value: Mapping[str, Any] | WorldGenesisRequest) -> WorldGenesisRequest:
    request, issues = validate_request(value)
    if issues or request is None:
        raise WorldGenError("INVALID_SCHEMA", "World Genesis Request is invalid", issues=issues)
    return request


def _coerce_draft(value: Mapping[str, Any] | WorldDraft) -> WorldDraft:
    draft, issues = validate_draft(value)
    if issues or draft is None:
        raise WorldGenError("INVALID_SCHEMA", "World Draft is invalid", issues=issues)
    return draft


def compile_worldpack(draft: WorldDraft) -> CompiledWorldPack:
    """Bind the one explicit profile to current reviewed runtime contracts."""

    if draft.mechanics_profile != MECHANICS_PROFILE:
        raise WorldGenError(
            "UNSUPPORTED_MECHANICS_PROFILE",
            "mechanics profile is not supported by this compiler",
        )
    return CompiledWorldPack(
        schema_version=1,
        compiler_id=COMPILER_ID,
        mechanics_profile=MECHANICS_PROFILE,
        world_id=draft.world_id,
        content_locale=draft.content_locale,
        public_content={
            "title": draft.title,
            "premise": draft.premise,
            "labels": copy.deepcopy(draft.labels),
        },
        runtime_bindings={
            "base_location_id": MARA_INITIAL_LOCATION_ID,
            "target_location_id": _TARGET_LOCATION_ID,
            "resource_id": _RESOURCE_ID,
            "named_actor_id": MARA_ACTOR_ID,
            "named_actor_fact_id": MARA_FACT_ID,
        },
    )


def materialize_initial_state(
    compiled_worldpack: CompiledWorldPack | Mapping[str, Any], seed: str
) -> GameState:
    """Materialize the fixed Phase 7.5-compatible state, without display content."""

    seed = _validate_seed(seed)
    pack = (
        compiled_worldpack.to_dict()
        if isinstance(compiled_worldpack, CompiledWorldPack)
        else compiled_worldpack
    )
    if not isinstance(pack, dict) or pack.get("mechanics_profile") != MECHANICS_PROFILE:
        raise WorldGenError(
            "UNSUPPORTED_MECHANICS_PROFILE",
            "only phase75_expedition_v1 can be materialized",
        )
    bindings = pack.get("runtime_bindings")
    expected_bindings = {
        "base_location_id": MARA_INITIAL_LOCATION_ID,
        "target_location_id": _TARGET_LOCATION_ID,
        "resource_id": _RESOURCE_ID,
        "named_actor_id": MARA_ACTOR_ID,
        "named_actor_fact_id": MARA_FACT_ID,
    }
    if bindings != expected_bindings:
        raise WorldGenError(
            "BUNDLE_INTEGRITY_MISMATCH",
            "compiled runtime bindings do not match the reviewed profile",
        )

    state = GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed=seed,
        data={
            "player": {
                "location_id": MARA_INITIAL_LOCATION_ID,
                "stamina": 3,
                "max_stamina": 3,
                "hp": 10,
                "max_hp": 10,
                "attack": 2,
            },
            "inventory": {},
            "expedition": {
                "active": False,
                "base_location_id": MARA_INITIAL_LOCATION_ID,
                "target_location_id": _TARGET_LOCATION_ID,
                "target_searched": False,
                "target_loot": {"salvage": 2, "parts": 1},
                "carried_loot": {},
            },
            "phase_cycle": copy.deepcopy(_PHASE_CYCLE),
            "progression": {"tracks": {"player": 0, "base": 0}},
            "progression_gates": {
                "player": {
                    "from_stage": 0,
                    "to_stage": 1,
                    "cost": {"salvage": 2, "parts": 1},
                },
                "base": {
                    "from_stage": 0,
                    "to_stage": 1,
                    "cost": {"salvage": 2, "parts": 1},
                },
            },
            "build_choice": {
                "required_track": "player",
                "required_stage": 1,
                "candidates": list(_BUILD_CANDIDATES),
            },
            "build": {"selected": None},
            "named_actor": {
                "actor_id": MARA_ACTOR_ID,
                "name": MARA_NAME,
                "location_id": MARA_INITIAL_LOCATION_ID,
                "goal": MARA_INITIAL_GOAL,
                "relationship": {"trust": 0},
                "knowledge": {},
                "last_autonomous_action": None,
            },
            "world_facts": {MARA_FACT_ID: "unstable"},
            "player_knowledge": {
                "facts": {},
                "actors": {
                    MARA_ACTOR_ID: {
                        "name": MARA_NAME,
                        "last_known_location_id": MARA_INITIAL_LOCATION_ID,
                        "known_goal": MARA_INITIAL_GOAL,
                    }
                },
            },
        },
    )
    try:
        check_invariants(state)
    except Exception as exc:
        raise WorldGenError(
            "BOOTSTRAP_FAILED",
            "materialized initial GameState violates engine invariants",
        ) from exc
    return state


def _bootstrap_policy(
    _observation: dict[str, Any], decision_number: int, actor_id: str
) -> ActionIntent | None:
    sequence = ("DROP", "SEARCH", "EXTRACT", TALK_TO_ACTOR)
    if decision_number > len(sequence):
        return None
    action_type = sequence[decision_number - 1]
    params = {"actor_id": MARA_ACTOR_ID} if action_type == TALK_TO_ACTOR else {}
    return ActionIntent(
        action_id=f"{actor_id}-bootstrap-{decision_number}",
        actor_id=actor_id,
        action_type=action_type,
        params=params,
    )


def bootstrap_smoke(initial_state: GameState) -> BootstrapResult:
    """Run the existing scripted autoplay/replay path without persistence."""

    try:
        build_observation(initial_state)
        if not get_legal_actions(initial_state):
            raise ValueError("initial legal choices are empty")
        result = run_autoplay(
            copy.deepcopy(initial_state),
            _bootstrap_policy,
            AutoplayConfig(max_decisions=5, actor_id="phase9b-bootstrap"),
        )
        passed = (
            result.completed
            and result.decisions == 4
            and result.events == 4
            and result.illegal_actions == 0
            and result.knowledge_boundary_violations == 0
            and result.actor_autonomous_actions == 1
            and result.knowledge_transfers == 1
            and result.relationship_changes == 1
            and result.replay_verified
            and result.final_state.data["named_actor"]["relationship"]["trust"] == 1
            and result.final_state.data["player_knowledge"]["facts"]
            == {MARA_FACT_ID: "unstable"}
            and result.final_state.data["named_actor"]["last_autonomous_action"]
            == MARA_AUTONOMOUS_ACTION
        )
        return BootstrapResult(
            passed=passed,
            accepted_decisions=result.decisions,
            events=result.events,
            illegal_actions=result.illegal_actions,
            knowledge_boundary_violations=result.knowledge_boundary_violations,
            event_replay=result.replay_verified,
            final_state_hash=result.final_state_hash,
            final_state=result.final_state,
            error=None if passed else "bootstrap metrics did not match the contract",
        )
    except Exception as exc:
        boundary_violations = 0
        final_hash = ""
        if isinstance(initial_state, GameState):
            try:
                boundary_violations = count_knowledge_boundary_violations(
                    initial_state, build_observation(initial_state)
                )
            except Exception:
                boundary_violations = 0
            final_hash = state_hash(initial_state.__dict__)
        return BootstrapResult(
            passed=False,
            accepted_decisions=0,
            events=0,
            illegal_actions=0,
            knowledge_boundary_violations=boundary_violations,
            event_replay=False,
            final_state_hash=final_hash,
            final_state=initial_state,
            error=str(exc),
        )


def compile_world(
    request: Mapping[str, Any] | WorldGenesisRequest,
    draft: Mapping[str, Any] | WorldDraft,
    seed: str,
) -> CompilationResult:
    """Validate, compile, materialize, and smoke-test one bounded world."""

    normalized_request = _coerce_request(request)
    normalized_draft = _coerce_draft(draft)
    seed = _validate_seed(seed)
    compiled_worldpack = compile_worldpack(normalized_draft)
    initial_state = materialize_initial_state(compiled_worldpack, seed)
    smoke = bootstrap_smoke(initial_state)
    if not smoke.passed:
        raise WorldGenError(
            "BOOTSTRAP_FAILED",
            smoke.error or "bootstrap smoke test failed",
            issues=(
                _issue(
                    "BOOTSTRAP_FAILED",
                    "/bootstrap",
                    smoke.error or "bootstrap smoke test failed",
                    "contract metrics",
                    smoke.to_report(),
                ),
            ),
        )
    worldpack_dict = compiled_worldpack.to_dict()
    initial_state_hash = state_hash(initial_state.__dict__)
    worldpack_hash = state_hash(worldpack_dict)
    report = {
        "schema_version": 1,
        "valid": True,
        "compiler_id": COMPILER_ID,
        "errors": [],
        "worldpack_hash": worldpack_hash,
        "initial_state_hash": initial_state_hash,
        "bootstrap": smoke.to_report(),
    }
    return CompilationResult(
        request=normalized_request,
        draft=normalized_draft,
        compiled_worldpack=compiled_worldpack,
        initial_state=initial_state,
        report=report,
        worldpack_hash=worldpack_hash,
        initial_state_hash=initial_state_hash,
    )
