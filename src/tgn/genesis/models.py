"""Immutable, deterministic V1-A Genesis request artifacts.

This module deliberately contains only boundary models and validation helpers.
It does not know about the game runtime, persistence, providers, or prompt
parsing.  Nested JSON values are stored as canonical snapshots so callers
cannot mutate an artifact after it has been constructed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


MAX_PROMPT_LENGTH = 16_384
MAX_SEED_LENGTH = 256
MAX_LOCALE_LENGTH = 64
MAX_STRING_LENGTH = 8_192
MAX_REQUIREMENTS = 128
MAX_CANDIDATE_FEATURES = 64
MAX_WARNINGS = 64
MAX_CONSTRAINTS = 128
MAX_JSON_DEPTH = 32
MAX_JSON_OBJECT_KEYS = 128
MAX_JSON_ARRAY_LENGTH = 128

REQUEST_SCHEMA_VERSION = 1
PROPOSAL_SCHEMA_VERSION = 1
APPROVAL_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1

ACCEPTANCE_POLICIES = frozenset({"STRICT", "DEGRADABLE", "OPTIONAL"})
CATALOG_LAYERS = frozenset({"CONTENT", "RUNTIME", "KERNEL", "LEGACY"})
REQUIREMENT_KINDS = frozenset(
    {
        "CONTENT_EXPRESSION",
        "WORLD_RULE",
        "RUNTIME_MECHANIC",
        "PROTAGONIST_CONSTRAINT",
        "PROGRESSION_RULE",
        "RESOURCE_ECONOMY",
        "PUBLIC_SYSTEM",
        "EXCLUSIVITY",
        "ENTITY_MODEL",
    }
)
CONSTRAINT_KINDS = frozenset(
    {"EQUALS", "ONE_OF", "EXCLUDES", "REQUIRES", "OWNERSHIP", "RESOURCE_COST", "LIMIT"}
)
REPORT_REASON_CODES = frozenset(
    {
        "SUPPORTED",
        "NO_MATCHING_RUNTIME_CONTRACT",
        "UNKNOWN_FEATURE_ID",
        "CATALOG_LAYER_MISMATCH",
        "UNRESOLVED_WARNING",
    }
)
SUPPORT_STATUSES = frozenset({"SUPPORTED", "UNSUPPORTED", "REJECTED"})
DISPOSITIONS = frozenset({"BIND", "OMIT", "BLOCK"})
APPROVAL_DECISIONS = frozenset({"CONFIRMED", "CANCELLED"})

ERROR_CODES = frozenset(
    {
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "INVALID_TYPE",
        "INVALID_VALUE",
        "INVALID_ID",
        "DUPLICATE_ID",
        "REQUEST_HASH_MISMATCH",
        "PROPOSAL_HASH_MISMATCH",
        "APPROVAL_HASH_MISMATCH",
        "SOURCE_ID_MISMATCH",
        "REQUIREMENT_SET_MISMATCH",
        "ACCEPTANCE_POLICY_MISMATCH",
        "APPROVAL_NOT_CONFIRMED",
        "CATALOG_LAYER_MISMATCH",
        "CATALOG_IDENTITY_MISMATCH",
        "UNKNOWN_FEATURE_ID",
        "NO_MATCHING_RUNTIME_CONTRACT",
        "UNRESOLVED_WARNING",
        "REPORT_MISMATCH",
    }
)

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class GenesisValidationError(ValueError):
    """Stable, machine-readable validation failure for Genesis artifacts."""

    def __init__(
        self,
        code: str,
        path: str = "$",
        *,
        expected: str | None = None,
        actual: str | None = None,
        message: str | None = None,
    ) -> None:
        if type(code) is not str or code not in ERROR_CODES:
            raise ValueError(f"Unknown Genesis validation error code: {code}")
        self.code = code
        self.path = path
        self.expected = expected
        self.actual = actual
        self.message = message or code
        super().__init__(self.__str__())

    def __str__(self) -> str:
        detail = f"{self.code} at {self.path}: {self.message}"
        if self.expected is not None:
            detail += f" (expected {self.expected}"
            if self.actual is not None:
                detail += f", got {self.actual}"
            detail += ")"
        return detail

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"code": self.code, "path": self.path, "message": self.message}
        if self.expected is not None:
            result["expected"] = self.expected
        if self.actual is not None:
            result["actual"] = self.actual
        return result


def _actual(value: Any) -> str:
    """Return a safe type/value summary without echoing user prompt data."""

    if value is None:
        return "null"
    if isinstance(value, str):
        return f"string(length={len(value)})"
    if isinstance(value, (list, tuple)):
        return f"array(length={len(value)})"
    if isinstance(value, Mapping):
        return f"object(keys={len(value)})"
    return type(value).__name__


def _fail(
    code: str,
    path: str,
    *,
    expected: str | None = None,
    actual: Any = None,
    message: str | None = None,
) -> None:
    raise GenesisValidationError(
        code,
        path,
        expected=expected,
        actual=_actual(actual) if actual is not None else None,
        message=message,
    )


def _check_type(value: Any, expected: type | tuple[type, ...], path: str) -> None:
    if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
        _fail("INVALID_TYPE", path, expected=getattr(expected, "__name__", "value"), actual=value)


def _check_int(value: Any, path: str) -> int:
    if type(value) is not int:
        _fail("INVALID_TYPE", path, expected="int", actual=value)
    return value


def _validate_text(
    value: Any,
    path: str,
    *,
    max_length: int = MAX_STRING_LENGTH,
    allow_empty: bool = False,
) -> str:
    if type(value) is not str:
        _fail("INVALID_TYPE", path, expected="string", actual=value)
    if not allow_empty and not value:
        _fail("INVALID_VALUE", path, expected="non-empty string", actual=value)
    if len(value) > max_length:
        _fail("INVALID_VALUE", path, expected=f"length <= {max_length}", actual=value)
    if "\x00" in value:
        _fail("INVALID_VALUE", path, message="NUL is not allowed")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        _fail("INVALID_VALUE", path, message="surrogate code points are not allowed")
    return value


def _validate_id(value: Any, path: str) -> str:
    value = _validate_text(value, path, max_length=128)
    if _ID_RE.fullmatch(value) is None:
        _fail("INVALID_ID", path, expected="lower-case stable identifier", actual=value)
    return value


def _validate_intent_summary(value: Any, path: str) -> str:
    """Keep normalized intent as an auditable summary, not a machine ID."""

    value = _validate_text(value, path)
    if _ID_RE.fullmatch(value) is not None:
        _fail("INVALID_VALUE", path, expected="human-readable semantic summary", actual=value)
    return value


def _validate_hash(value: Any, path: str, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    value = _validate_text(value, path, max_length=64)
    if _HEX64_RE.fullmatch(value) is None:
        _fail("INVALID_VALUE", path, expected="lower-case SHA-256 hex", actual=value)
    return value


def _check_exact_fields(
    data: Mapping[str, Any],
    allowed: set[str],
    required: set[str],
    path: str,
) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        _fail("UNKNOWN_FIELD", f"{path}.{unknown[0]}", message="field is not part of this artifact")
    missing = sorted(required - set(data))
    if missing:
        _fail("MISSING_FIELD", f"{path}.{missing[0]}", message="required field is missing")


def _json_value(value: Any, path: str = "$", *, _depth: int = 0, _seen: set[int] | None = None) -> Any:
    """Validate a finite, UTF-8-safe JSON value and return it unchanged."""

    if _depth > MAX_JSON_DEPTH:
        _fail("INVALID_VALUE", path, expected=f"JSON depth <= {MAX_JSON_DEPTH}", actual=value)
    if _seen is None:
        _seen = set()
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str):
            _validate_text(value, path, allow_empty=True)
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("INVALID_VALUE", path, message="non-finite numbers are not allowed")
        return value
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in _seen:
            _fail("INVALID_VALUE", path, message="cyclic JSON value is not allowed")
        _seen.add(identity)
        if len(value) > MAX_JSON_OBJECT_KEYS:
            _seen.remove(identity)
            _fail("INVALID_VALUE", path, expected=f"object keys <= {MAX_JSON_OBJECT_KEYS}", actual=value)
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if type(key) is not str:
                _seen.remove(identity)
                _fail("INVALID_TYPE", f"{path}.<key>", expected="string", actual=key)
            _validate_text(key, f"{path}.<key>", allow_empty=True)
            normalized[key] = _json_value(child, f"{path}.{key}", _depth=_depth + 1, _seen=_seen)
        _seen.remove(identity)
        return normalized
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in _seen:
            _fail("INVALID_VALUE", path, message="cyclic JSON value is not allowed")
        _seen.add(identity)
        if len(value) > MAX_JSON_ARRAY_LENGTH:
            _seen.remove(identity)
            _fail("INVALID_VALUE", path, expected=f"array length <= {MAX_JSON_ARRAY_LENGTH}", actual=value)
        normalized = [
            _json_value(child, f"{path}[{index}]", _depth=_depth + 1, _seen=_seen)
            for index, child in enumerate(value)
        ]
        _seen.remove(identity)
        return normalized
    _fail("INVALID_TYPE", path, expected="JSON value", actual=value)
    return None


def _canonical_json(value: Any) -> str:
    normalized = _json_value(value)
    try:
        encoded = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise GenesisValidationError("INVALID_VALUE", "$", message="value is not canonical JSON") from exc
    return encoded.decode("utf-8")


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _load_snapshot(snapshot: str) -> Any:
    return json.loads(snapshot)


def _normalize_string_array(
    value: Any,
    path: str,
    *,
    max_length: int,
    allow_empty_items: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        _fail("INVALID_TYPE", path, expected="array", actual=value)
    if len(value) > max_length:
        _fail("INVALID_VALUE", path, expected=f"array length <= {max_length}", actual=value)
    result = []
    for index, item in enumerate(value):
        result.append(_validate_text(item, f"{path}[{index}]", allow_empty=allow_empty_items))
    return tuple(result)


def _normalize_unique_ids(value: Any, path: str, *, max_length: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        _fail("INVALID_TYPE", path, expected="array", actual=value)
    if len(value) > max_length:
        _fail("INVALID_VALUE", path, expected=f"array length <= {max_length}", actual=value)
    result = tuple(_validate_id(item, f"{path}[{index}]") for index, item in enumerate(value))
    if len(result) != len(set(result)):
        _fail("DUPLICATE_ID", path, message="duplicate identifier")
    return result


@dataclass(frozen=True, slots=True, init=False)
class GenesisRequest:
    schema_version: int
    request_id: str
    raw_prompt: str
    genesis_seed: int | str
    content_locale: str
    _explicit_constraints_json: str = field(repr=False, compare=True)
    generation_policy_reference: str

    def __init__(
        self,
        schema_version: int,
        request_id: str,
        raw_prompt: str,
        genesis_seed: int | str,
        content_locale: str,
        explicit_constraints: Sequence[str],
        generation_policy_reference: str,
    ) -> None:
        if type(schema_version) is not int or schema_version != REQUEST_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.schema_version", expected=str(REQUEST_SCHEMA_VERSION), actual=schema_version)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "request_id", _validate_id(request_id, "$.request_id"))
        object.__setattr__(self, "raw_prompt", _validate_text(raw_prompt, "$.raw_prompt", max_length=MAX_PROMPT_LENGTH))
        if type(genesis_seed) is int and not isinstance(genesis_seed, bool):
            if not 0 <= genesis_seed <= 2**63 - 1:
                _fail("INVALID_VALUE", "$.genesis_seed", expected="integer in [0, 2^63-1]", actual=genesis_seed)
            seed: int | str = genesis_seed
        elif type(genesis_seed) is str:
            seed = _validate_text(genesis_seed, "$.genesis_seed", max_length=MAX_SEED_LENGTH)
        else:
            _fail("INVALID_TYPE", "$.genesis_seed", expected="int or string", actual=genesis_seed)
            seed = 0
        object.__setattr__(self, "genesis_seed", seed)
        object.__setattr__(self, "content_locale", _validate_text(content_locale, "$.content_locale", max_length=MAX_LOCALE_LENGTH))
        constraints = _normalize_string_array(
            explicit_constraints,
            "$.explicit_constraints",
            max_length=MAX_CONSTRAINTS,
            allow_empty_items=False,
        )
        object.__setattr__(self, "_explicit_constraints_json", _canonical_json(list(constraints)))
        object.__setattr__(
            self,
            "generation_policy_reference",
            _validate_text(generation_policy_reference, "$.generation_policy_reference", max_length=MAX_STRING_LENGTH),
        )

    @property
    def explicit_constraints(self) -> tuple[str, ...]:
        return tuple(_load_snapshot(self._explicit_constraints_json))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "raw_prompt": self.raw_prompt,
            "genesis_seed": self.genesis_seed,
            "content_locale": self.content_locale,
            "explicit_constraints": list(self.explicit_constraints),
            "generation_policy_reference": self.generation_policy_reference,
        }

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GenesisRequest":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data)
        allowed = {
            "schema_version",
            "request_id",
            "raw_prompt",
            "genesis_seed",
            "content_locale",
            "explicit_constraints",
            "generation_policy_reference",
        }
        _check_exact_fields(data, allowed, allowed, "$")
        return cls(**dict(data))


def _normalize_constraint_value(value: Any, path: str) -> str | int | bool | tuple[str | int | bool, ...]:
    """Validate a scalar or one-level scalar array for a semantic constraint."""

    def normalize_scalar(item: Any, item_path: str) -> str | int | bool:
        if type(item) is str:
            return _validate_text(item, item_path, allow_empty=True)
        if type(item) is int or type(item) is bool:
            return item
        _fail("INVALID_TYPE", item_path, expected="string|integer|boolean", actual=item)
        raise AssertionError("unreachable")

    if type(value) in {str, int, bool}:
        return normalize_scalar(value, path)
    if isinstance(value, (list, tuple)):
        if len(value) > 8:
            _fail("INVALID_VALUE", path, expected="array length <= 8", actual=value)
        return tuple(normalize_scalar(item, f"{path}[{index}]") for index, item in enumerate(value))
    _fail("INVALID_TYPE", path, expected="string|integer|boolean|scalar array", actual=value)
    raise AssertionError("unreachable")


@dataclass(frozen=True, slots=True)
class RequirementConstraint:
    constraint_id: str
    constraint_kind: str
    value: str | int | bool | tuple[str | int | bool, ...]
    required: bool

    def __post_init__(self) -> None:
        _validate_id(self.constraint_id, "$.constraint_id")
        if type(self.constraint_kind) is not str or self.constraint_kind not in CONSTRAINT_KINDS:
            _fail("INVALID_VALUE", "$.constraint_kind", expected="known semantic constraint kind", actual=self.constraint_kind)
        if type(self.required) is not bool:
            _fail("INVALID_TYPE", "$.required", expected="boolean", actual=self.required)
        normalized = _normalize_constraint_value(self.value, "$.value")
        object.__setattr__(self, "value", normalized)

    def to_dict(self) -> dict[str, Any]:
        value: Any = list(self.value) if isinstance(self.value, tuple) else self.value
        return {
            "constraint_id": self.constraint_id,
            "constraint_kind": self.constraint_kind,
            "value": value,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RequirementConstraint":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data)
        allowed = {"constraint_id", "constraint_kind", "value", "required"}
        _check_exact_fields(data, allowed, allowed, "$")
        return cls(**dict(data))


@dataclass(frozen=True, slots=True, init=False)
class Requirement:
    requirement_id: str
    source_reference: str
    normalized_intent: str
    requirement_kind: str
    acceptance_policy: str
    catalog_layer: str
    _typed_constraints_json: str = field(repr=False, compare=True)
    candidate_feature_ids: tuple[str, ...]
    notes: str
    _warnings_json: str = field(repr=False, compare=True)

    def __init__(
        self,
        requirement_id: str,
        source_reference: str,
        normalized_intent: str,
        requirement_kind: str,
        acceptance_policy: str,
        catalog_layer: str,
        typed_constraints: Sequence[RequirementConstraint],
        candidate_feature_ids: Sequence[str],
        notes: str = "",
        warnings: Sequence[str] = (),
    ) -> None:
        object.__setattr__(self, "requirement_id", _validate_id(requirement_id, "$.requirement_id"))
        object.__setattr__(self, "source_reference", _validate_text(source_reference, "$.source_reference"))
        object.__setattr__(self, "normalized_intent", _validate_intent_summary(normalized_intent, "$.normalized_intent"))
        if type(requirement_kind) is not str or requirement_kind not in REQUIREMENT_KINDS:
            _fail(
                "INVALID_VALUE",
                "$.requirement_kind",
                expected="a finite requirement kind",
                actual=requirement_kind,
            )
        object.__setattr__(self, "requirement_kind", requirement_kind)
        if type(acceptance_policy) is not str or acceptance_policy not in ACCEPTANCE_POLICIES:
            _fail("INVALID_VALUE", "$.acceptance_policy", expected="STRICT|DEGRADABLE|OPTIONAL", actual=acceptance_policy)
        object.__setattr__(self, "acceptance_policy", acceptance_policy)
        if type(catalog_layer) is not str or catalog_layer not in {"CONTENT", "RUNTIME"}:
            _fail("INVALID_VALUE", "$.catalog_layer", expected="CONTENT|RUNTIME", actual=catalog_layer)
        if catalog_layer == "CONTENT" and requirement_kind != "CONTENT_EXPRESSION":
            _fail(
                "INVALID_VALUE",
                "$.requirement_kind",
                expected="CONTENT_EXPRESSION for CONTENT",
                actual=requirement_kind,
            )
        if catalog_layer == "RUNTIME" and requirement_kind == "CONTENT_EXPRESSION":
            _fail(
                "INVALID_VALUE",
                "$.requirement_kind",
                expected="a runtime requirement kind for RUNTIME",
                actual=requirement_kind,
            )
        object.__setattr__(self, "catalog_layer", catalog_layer)
        if not isinstance(typed_constraints, (list, tuple)):
            _fail("INVALID_TYPE", "$.typed_constraints", expected="array of RequirementConstraint", actual=typed_constraints)
        if len(typed_constraints) > 32:
            _fail("INVALID_VALUE", "$.typed_constraints", expected="array length <= 32", actual=typed_constraints)
        if any(type(item) is not RequirementConstraint for item in typed_constraints):
            _fail("INVALID_TYPE", "$.typed_constraints", expected="RequirementConstraint objects", actual=typed_constraints)
        if catalog_layer == "CONTENT" and any(
            item.constraint_kind not in {"EQUALS", "ONE_OF"} for item in typed_constraints
        ):
            _fail(
                "INVALID_VALUE",
                "$.typed_constraints",
                expected="EQUALS|ONE_OF for non-causal Content expression",
                actual=typed_constraints,
            )
        constraint_ids = tuple(item.constraint_id for item in typed_constraints)
        if len(constraint_ids) != len(set(constraint_ids)):
            _fail("DUPLICATE_ID", "$.typed_constraints", message="duplicate constraint identifier")
        object.__setattr__(self, "_typed_constraints_json", _canonical_json([item.to_dict() for item in typed_constraints]))
        normalized_candidates = _normalize_unique_ids(
            candidate_feature_ids,
            "$.candidate_feature_ids",
            max_length=MAX_CANDIDATE_FEATURES,
        )
        if len(normalized_candidates) > 1:
            _fail("INVALID_VALUE", "$.candidate_feature_ids", expected="at most one candidate Feature ID", actual=normalized_candidates)
        object.__setattr__(
            self,
            "candidate_feature_ids",
            normalized_candidates,
        )
        object.__setattr__(self, "notes", _validate_text(notes, "$.notes", allow_empty=True))
        normalized_warnings = _normalize_string_array(
            warnings,
            "$.warnings",
            max_length=MAX_WARNINGS,
            allow_empty_items=False,
        )
        object.__setattr__(self, "_warnings_json", _canonical_json(list(normalized_warnings)))

    @property
    def typed_constraints(self) -> tuple[RequirementConstraint, ...]:
        return tuple(RequirementConstraint.from_dict(item) for item in _load_snapshot(self._typed_constraints_json))

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(_load_snapshot(self._warnings_json))

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "source_reference": self.source_reference,
            "normalized_intent": self.normalized_intent,
            "requirement_kind": self.requirement_kind,
            "acceptance_policy": self.acceptance_policy,
            "catalog_layer": self.catalog_layer,
            "typed_constraints": [item.to_dict() for item in self.typed_constraints],
            "candidate_feature_ids": list(self.candidate_feature_ids),
            "notes": self.notes,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Requirement":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data)
        allowed = {
            "requirement_id",
            "source_reference",
            "normalized_intent",
            "requirement_kind",
            "acceptance_policy",
            "catalog_layer",
            "typed_constraints",
            "candidate_feature_ids",
            "notes",
            "warnings",
        }
        required = allowed - {"notes", "warnings"}
        _check_exact_fields(data, allowed, required, "$")
        if not isinstance(data["typed_constraints"], list):
            _fail("INVALID_TYPE", "$.typed_constraints", expected="array", actual=data["typed_constraints"])
        return cls(
            requirement_id=data["requirement_id"],
            source_reference=data["source_reference"],
            normalized_intent=data["normalized_intent"],
            requirement_kind=data["requirement_kind"],
            acceptance_policy=data["acceptance_policy"],
            catalog_layer=data["catalog_layer"],
            typed_constraints=[RequirementConstraint.from_dict(item) for item in data["typed_constraints"]],
            candidate_feature_ids=data["candidate_feature_ids"],
            notes=data.get("notes", ""),
            warnings=data.get("warnings", ()),
        )


@dataclass(frozen=True, slots=True, init=False)
class RequirementProposal:
    proposal_schema_version: int
    proposal_id: str
    source_request_id: str
    source_request_hash: str
    _requirements_json: str = field(repr=False, compare=True)
    generation_metadata_hash: str | None

    def __init__(
        self,
        proposal_schema_version: int,
        proposal_id: str,
        source_request_id: str,
        source_request_hash: str,
        requirements: Sequence[Requirement],
        generation_metadata_hash: str | None = None,
    ) -> None:
        if type(proposal_schema_version) is not int or proposal_schema_version != PROPOSAL_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.proposal_schema_version", expected=str(PROPOSAL_SCHEMA_VERSION), actual=proposal_schema_version)
        object.__setattr__(self, "proposal_schema_version", proposal_schema_version)
        object.__setattr__(self, "proposal_id", _validate_id(proposal_id, "$.proposal_id"))
        object.__setattr__(self, "source_request_id", _validate_id(source_request_id, "$.source_request_id"))
        object.__setattr__(self, "source_request_hash", _validate_hash(source_request_hash, "$.source_request_hash"))
        if not isinstance(requirements, (list, tuple)):
            _fail("INVALID_TYPE", "$.requirements", expected="array", actual=requirements)
        if not requirements:
            _fail("INVALID_VALUE", "$.requirements", expected="non-empty array", actual=requirements)
        if len(requirements) > MAX_REQUIREMENTS:
            _fail("INVALID_VALUE", "$.requirements", expected=f"array length <= {MAX_REQUIREMENTS}", actual=requirements)
        if any(type(item) is not Requirement for item in requirements):
            _fail("INVALID_TYPE", "$.requirements", expected="Requirement objects", actual=requirements)
        ids = tuple(item.requirement_id for item in requirements)
        if len(ids) != len(set(ids)):
            _fail("DUPLICATE_ID", "$.requirements", message="duplicate requirement identifier")
        object.__setattr__(self, "_requirements_json", _canonical_json([item.to_dict() for item in requirements]))
        if generation_metadata_hash is not None:
            generation_metadata_hash = _validate_hash(generation_metadata_hash, "$.generation_metadata_hash", required=False)
        object.__setattr__(self, "generation_metadata_hash", generation_metadata_hash)

    @property
    def requirements(self) -> tuple[Requirement, ...]:
        return tuple(Requirement.from_dict(item) for item in _load_snapshot(self._requirements_json))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "proposal_schema_version": self.proposal_schema_version,
            "proposal_id": self.proposal_id,
            "source_request_id": self.source_request_id,
            "source_request_hash": self.source_request_hash,
            "requirements": [item.to_dict() for item in self.requirements],
        }
        if self.generation_metadata_hash is not None:
            result["generation_metadata_hash"] = self.generation_metadata_hash
        return result

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RequirementProposal":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data)
        allowed = {
            "proposal_schema_version",
            "proposal_id",
            "source_request_id",
            "source_request_hash",
            "requirements",
            "generation_metadata_hash",
        }
        required = allowed - {"generation_metadata_hash"}
        _check_exact_fields(data, allowed, required, "$")
        requirements = data["requirements"]
        if not isinstance(requirements, list):
            _fail("INVALID_TYPE", "$.requirements", expected="array", actual=requirements)
        return cls(
            proposal_schema_version=data["proposal_schema_version"],
            proposal_id=data["proposal_id"],
            source_request_id=data["source_request_id"],
            source_request_hash=data["source_request_hash"],
            requirements=[Requirement.from_dict(item) for item in requirements],
            generation_metadata_hash=data.get("generation_metadata_hash"),
        )


@dataclass(frozen=True, slots=True)
class RequirementApproval:
    requirement_id: str
    acceptance_policy: str

    def __post_init__(self) -> None:
        _validate_id(self.requirement_id, "$.requirement_id")
        if type(self.acceptance_policy) is not str or self.acceptance_policy not in ACCEPTANCE_POLICIES:
            _fail("INVALID_VALUE", "$.acceptance_policy", expected="STRICT|DEGRADABLE|OPTIONAL", actual=self.acceptance_policy)

    def to_dict(self) -> dict[str, str]:
        return {"requirement_id": self.requirement_id, "acceptance_policy": self.acceptance_policy}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RequirementApproval":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data)
        allowed = {"requirement_id", "acceptance_policy"}
        _check_exact_fields(data, allowed, allowed, "$")
        return cls(**dict(data))


@dataclass(frozen=True, slots=True, init=False)
class RequirementCoverageApproval:
    approval_schema_version: int
    approval_id: str
    decision: str
    source_request_id: str
    source_request_hash: str
    source_proposal_id: str
    source_proposal_hash: str
    _requirement_approvals_json: str = field(repr=False, compare=True)
    _approval_hash: str = field(repr=False, compare=True)

    def __init__(
        self,
        approval_schema_version: int,
        approval_id: str,
        decision: str,
        source_request_id: str,
        source_request_hash: str,
        source_proposal_id: str,
        source_proposal_hash: str,
        requirement_approvals: Sequence[RequirementApproval],
        approval_hash: str | None = None,
    ) -> None:
        if type(approval_schema_version) is not int or approval_schema_version != APPROVAL_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.approval_schema_version", expected=str(APPROVAL_SCHEMA_VERSION), actual=approval_schema_version)
        object.__setattr__(self, "approval_schema_version", approval_schema_version)
        object.__setattr__(self, "approval_id", _validate_id(approval_id, "$.approval_id"))
        if type(decision) is not str or decision not in APPROVAL_DECISIONS:
            _fail("INVALID_VALUE", "$.decision", expected="CONFIRMED|CANCELLED", actual=decision)
        object.__setattr__(self, "decision", decision)
        object.__setattr__(self, "source_request_id", _validate_id(source_request_id, "$.source_request_id"))
        object.__setattr__(self, "source_request_hash", _validate_hash(source_request_hash, "$.source_request_hash"))
        object.__setattr__(self, "source_proposal_id", _validate_id(source_proposal_id, "$.source_proposal_id"))
        object.__setattr__(self, "source_proposal_hash", _validate_hash(source_proposal_hash, "$.source_proposal_hash"))
        if not isinstance(requirement_approvals, (list, tuple)):
            _fail("INVALID_TYPE", "$.requirement_approvals", expected="array", actual=requirement_approvals)
        if not requirement_approvals:
            _fail("INVALID_VALUE", "$.requirement_approvals", expected="non-empty array", actual=requirement_approvals)
        if len(requirement_approvals) > MAX_REQUIREMENTS:
            _fail("INVALID_VALUE", "$.requirement_approvals", expected=f"array length <= {MAX_REQUIREMENTS}", actual=requirement_approvals)
        if any(type(item) is not RequirementApproval for item in requirement_approvals):
            _fail("INVALID_TYPE", "$.requirement_approvals", expected="RequirementApproval objects", actual=requirement_approvals)
        ids = tuple(item.requirement_id for item in requirement_approvals)
        if len(ids) != len(set(ids)):
            _fail("DUPLICATE_ID", "$.requirement_approvals", message="duplicate requirement identifier")
        object.__setattr__(self, "_requirement_approvals_json", _canonical_json([item.to_dict() for item in requirement_approvals]))
        computed_hash = _hash_payload(self._payload_dict())
        if approval_hash is not None:
            approval_hash = _validate_hash(approval_hash, "$.approval_hash")
            if approval_hash != computed_hash:
                _fail("APPROVAL_HASH_MISMATCH", "$.approval_hash", message="approval canonical hash does not match payload")
        object.__setattr__(self, "_approval_hash", computed_hash)

    @property
    def requirement_approvals(self) -> tuple[RequirementApproval, ...]:
        return tuple(RequirementApproval.from_dict(item) for item in _load_snapshot(self._requirement_approvals_json))

    def _payload_dict(self) -> dict[str, Any]:
        return {
            "approval_schema_version": self.approval_schema_version,
            "approval_id": self.approval_id,
            "decision": self.decision,
            "source_request_id": self.source_request_id,
            "source_request_hash": self.source_request_hash,
            "source_proposal_id": self.source_proposal_id,
            "source_proposal_hash": self.source_proposal_hash,
            "requirement_approvals": [item.to_dict() for item in self.requirement_approvals],
        }

    @property
    def hash(self) -> str:
        return self._approval_hash

    def to_dict(self) -> dict[str, Any]:
        result = self._payload_dict()
        result["approval_hash"] = self.hash
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RequirementCoverageApproval":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data)
        allowed = {
            "approval_schema_version",
            "approval_id",
            "decision",
            "source_request_id",
            "source_request_hash",
            "source_proposal_id",
            "source_proposal_hash",
            "requirement_approvals",
            "approval_hash",
        }
        _check_exact_fields(data, allowed, allowed, "$")
        approvals = data["requirement_approvals"]
        if not isinstance(approvals, list):
            _fail("INVALID_TYPE", "$.requirement_approvals", expected="array", actual=approvals)
        instance = cls(
            approval_schema_version=data["approval_schema_version"],
            approval_id=data["approval_id"],
            decision=data["decision"],
            source_request_id=data["source_request_id"],
            source_request_hash=data["source_request_hash"],
            source_proposal_id=data["source_proposal_id"],
            source_proposal_hash=data["source_proposal_hash"],
            requirement_approvals=[RequirementApproval.from_dict(item) for item in approvals],
            approval_hash=data["approval_hash"],
        )
        return instance


@dataclass(frozen=True, slots=True, init=False)
class RequirementReportItem:
    requirement_id: str
    catalog_layer: str
    support_status: str
    _warnings_json: str = field(repr=False, compare=True)
    reason_code: str
    bound_feature_ids: tuple[str, ...]
    _accepted_scope_json: str = field(repr=False, compare=True)
    _lost_capabilities_json: str = field(repr=False, compare=True)
    player_visible_effect: str
    acknowledgement_required: bool
    disposition: str

    def __init__(
        self,
        requirement_id: str,
        catalog_layer: str,
        support_status: str,
        warnings: Sequence[str],
        reason_code: str,
        bound_feature_ids: Sequence[str],
        accepted_scope: Any,
        lost_capabilities: Sequence[str],
        player_visible_effect: str,
        acknowledgement_required: bool,
        disposition: str,
    ) -> None:
        object.__setattr__(self, "requirement_id", _validate_id(requirement_id, "$.requirement_id"))
        if type(catalog_layer) is not str or catalog_layer not in {"CONTENT", "RUNTIME"}:
            _fail("INVALID_VALUE", "$.catalog_layer", expected="CONTENT|RUNTIME", actual=catalog_layer)
        object.__setattr__(self, "catalog_layer", catalog_layer)
        if type(support_status) is not str or support_status not in SUPPORT_STATUSES:
            _fail("INVALID_VALUE", "$.support_status", expected="SUPPORTED|UNSUPPORTED|REJECTED", actual=support_status)
        object.__setattr__(self, "support_status", support_status)
        normalized_warnings = _normalize_string_array(warnings, "$.warnings", max_length=MAX_WARNINGS)
        object.__setattr__(self, "_warnings_json", _canonical_json(list(normalized_warnings)))
        if type(reason_code) is not str or reason_code not in REPORT_REASON_CODES:
            _fail("INVALID_VALUE", "$.reason_code", expected="a finite report reason code", actual=reason_code)
        object.__setattr__(self, "reason_code", reason_code)
        normalized_bound_ids = _normalize_unique_ids(
            bound_feature_ids,
            "$.bound_feature_ids",
            max_length=MAX_CANDIDATE_FEATURES,
        )
        object.__setattr__(self, "bound_feature_ids", normalized_bound_ids)
        object.__setattr__(self, "_accepted_scope_json", _canonical_json(accepted_scope))
        lost = _normalize_string_array(lost_capabilities, "$.lost_capabilities", max_length=MAX_CANDIDATE_FEATURES, allow_empty_items=False)
        object.__setattr__(self, "_lost_capabilities_json", _canonical_json(list(lost)))
        object.__setattr__(self, "player_visible_effect", _validate_text(player_visible_effect, "$.player_visible_effect", allow_empty=True))
        if type(acknowledgement_required) is not bool:
            _fail("INVALID_TYPE", "$.acknowledgement_required", expected="boolean", actual=acknowledgement_required)
        if acknowledgement_required:
            _fail("INVALID_VALUE", "$.acknowledgement_required", expected="false in V1-A", actual=acknowledgement_required)
        object.__setattr__(self, "acknowledgement_required", False)
        if type(disposition) is not str or disposition not in DISPOSITIONS:
            _fail("INVALID_VALUE", "$.disposition", expected="BIND|OMIT|BLOCK", actual=disposition)
        if support_status == "SUPPORTED" and disposition != "BIND":
            _fail("INVALID_VALUE", "$.disposition", message="SUPPORTED items must use BIND")
        if support_status == "REJECTED" and disposition != "BLOCK":
            _fail("INVALID_VALUE", "$.disposition", message="REJECTED items must use BLOCK")
        if support_status == "UNSUPPORTED" and disposition not in {"OMIT", "BLOCK"}:
            _fail("INVALID_VALUE", "$.disposition", message="UNSUPPORTED items must use OMIT or BLOCK")
        if support_status == "SUPPORTED" and not normalized_bound_ids:
            _fail("INVALID_VALUE", "$.bound_feature_ids", message="SUPPORTED items require a binding")
        if support_status != "SUPPORTED" and normalized_bound_ids:
            _fail("INVALID_VALUE", "$.bound_feature_ids", message="unsupported or rejected items cannot bind features")
        object.__setattr__(self, "disposition", disposition)

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(_load_snapshot(self._warnings_json))

    @property
    def accepted_scope(self) -> Any:
        return json.loads(self._accepted_scope_json)

    @property
    def lost_capabilities(self) -> tuple[str, ...]:
        return tuple(_load_snapshot(self._lost_capabilities_json))

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "catalog_layer": self.catalog_layer,
            "support_status": self.support_status,
            "warnings": list(self.warnings),
            "reason_code": self.reason_code,
            "bound_feature_ids": list(self.bound_feature_ids),
            "accepted_scope": self.accepted_scope,
            "lost_capabilities": list(self.lost_capabilities),
            "player_visible_effect": self.player_visible_effect,
            "acknowledgement_required": False,
            "disposition": self.disposition,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RequirementReportItem":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data)
        allowed = {
            "requirement_id",
            "catalog_layer",
            "support_status",
            "warnings",
            "reason_code",
            "bound_feature_ids",
            "accepted_scope",
            "lost_capabilities",
            "player_visible_effect",
            "acknowledgement_required",
            "disposition",
        }
        _check_exact_fields(data, allowed, allowed, "$")
        return cls(**dict(data))


@dataclass(frozen=True, slots=True, init=False)
class FeatureRequirementReport:
    report_schema_version: int
    source_request_hash: str
    source_proposal_hash: str
    source_approval_hash: str
    catalog_version: str
    source_catalog_hash: str
    _items_json: str = field(repr=False, compare=True)
    requirements_gate_passed: bool

    def __init__(
        self,
        report_schema_version: int,
        source_request_hash: str,
        source_proposal_hash: str,
        source_approval_hash: str,
        catalog_version: str,
        source_catalog_hash: str,
        items: Sequence[RequirementReportItem],
        requirements_gate_passed: bool,
    ) -> None:
        if type(report_schema_version) is not int or report_schema_version != REPORT_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.report_schema_version", expected=str(REPORT_SCHEMA_VERSION), actual=report_schema_version)
        object.__setattr__(self, "report_schema_version", report_schema_version)
        object.__setattr__(self, "source_request_hash", _validate_hash(source_request_hash, "$.source_request_hash"))
        object.__setattr__(self, "source_proposal_hash", _validate_hash(source_proposal_hash, "$.source_proposal_hash"))
        object.__setattr__(self, "source_approval_hash", _validate_hash(source_approval_hash, "$.source_approval_hash"))
        object.__setattr__(self, "catalog_version", _validate_text(catalog_version, "$.catalog_version", max_length=128))
        object.__setattr__(self, "source_catalog_hash", _validate_hash(source_catalog_hash, "$.source_catalog_hash"))
        if not isinstance(items, (list, tuple)):
            _fail("INVALID_TYPE", "$.items", expected="array", actual=items)
        if not items:
            _fail("INVALID_VALUE", "$.items", expected="non-empty array", actual=items)
        if any(type(item) is not RequirementReportItem for item in items):
            _fail("INVALID_TYPE", "$.items", expected="RequirementReportItem objects", actual=items)
        ids = [item.requirement_id for item in items]
        if len(ids) != len(set(ids)):
            _fail("DUPLICATE_ID", "$.items", message="duplicate requirement identifier")
        object.__setattr__(self, "_items_json", _canonical_json([item.to_dict() for item in items]))
        if type(requirements_gate_passed) is not bool:
            _fail("INVALID_TYPE", "$.requirements_gate_passed", expected="boolean", actual=requirements_gate_passed)
        if requirements_gate_passed:
            if any(item.disposition == "BLOCK" for item in items):
                _fail("INVALID_VALUE", "$.requirements_gate_passed", message="a blocked item cannot pass the requirements gate")
            if any(item.support_status == "REJECTED" for item in items):
                _fail("INVALID_VALUE", "$.requirements_gate_passed", message="a rejected item cannot pass the requirements gate")
            if any(item.warnings for item in items):
                _fail("INVALID_VALUE", "$.requirements_gate_passed", message="an unresolved warning cannot pass the requirements gate")
            if any(item.disposition == "BIND" and item.support_status != "SUPPORTED" for item in items):
                _fail("INVALID_VALUE", "$.requirements_gate_passed", message="only supported items can be bound")
            if any(item.disposition == "OMIT" and item.support_status != "UNSUPPORTED" for item in items):
                _fail("INVALID_VALUE", "$.requirements_gate_passed", message="only unsupported optional items can be omitted")
        object.__setattr__(self, "requirements_gate_passed", requirements_gate_passed)

    @property
    def items(self) -> tuple[RequirementReportItem, ...]:
        return tuple(RequirementReportItem.from_dict(item) for item in _load_snapshot(self._items_json))

    @property
    def report_version(self) -> int:
        """Compatibility alias; the canonical serialized field is schema version."""

        return self.report_schema_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_schema_version": self.report_schema_version,
            "source_request_hash": self.source_request_hash,
            "source_proposal_hash": self.source_proposal_hash,
            "source_approval_hash": self.source_approval_hash,
            "catalog_version": self.catalog_version,
            "source_catalog_hash": self.source_catalog_hash,
            "items": [item.to_dict() for item in self.items],
            "requirements_gate_passed": self.requirements_gate_passed,
        }

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FeatureRequirementReport":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data)
        allowed = {
            "report_schema_version",
            "source_request_hash",
            "source_proposal_hash",
            "source_approval_hash",
            "catalog_version",
            "source_catalog_hash",
            "items",
            "requirements_gate_passed",
        }
        _check_exact_fields(data, allowed, allowed, "$")
        if not isinstance(data["items"], list):
            _fail("INVALID_TYPE", "$.items", expected="array", actual=data["items"])
        return cls(
            report_schema_version=data["report_schema_version"],
            source_request_hash=data["source_request_hash"],
            source_proposal_hash=data["source_proposal_hash"],
            source_approval_hash=data["source_approval_hash"],
            catalog_version=data["catalog_version"],
            source_catalog_hash=data["source_catalog_hash"],
            items=[RequirementReportItem.from_dict(item) for item in data["items"]],
            requirements_gate_passed=data["requirements_gate_passed"],
        )


__all__ = [
    "ACCEPTANCE_POLICIES",
    "APPROVAL_DECISIONS",
    "CATALOG_LAYERS",
    "CONSTRAINT_KINDS",
    "DISPOSITIONS",
    "ERROR_CODES",
    "FeatureRequirementReport",
    "GenesisRequest",
    "GenesisValidationError",
    "Requirement",
    "RequirementApproval",
    "RequirementConstraint",
    "RequirementCoverageApproval",
    "RequirementProposal",
    "RequirementReportItem",
    "REPORT_SCHEMA_VERSION",
    "REPORT_REASON_CODES",
    "REQUIREMENT_KINDS",
    "SUPPORT_STATUSES",
]
