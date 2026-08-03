"""Deterministic candidate World Blueprint contracts for Genesis V1-C.1.

The objects in this module are candidate durable artifacts.  They preserve
lineage and typed facts without turning a Blueprint into runtime authority.
The implementation is deliberately concrete for the recorded V1-C pressure
slice; it is not a generic world-schema or plugin framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .catalog import FeatureSupportCatalog
from .models import (
    GenesisRequest,
    GenesisValidationError,
    Requirement,
    RequirementConstraint,
    RequirementCoverageApproval,
    RequirementProposal,
    FeatureRequirementReport,
    _canonical_json as _models_canonical_json,
)
from .pressure import PRESSURE_CONTRACT_VERSION, PRESSURE_FEATURE_ID


BLUEPRINT_SCHEMA_VERSION = 1
PRESSURE_SELECTION_SCHEMA_VERSION = 1
CANDIDATE_DURABLE = "CANDIDATE_DURABLE"
BLUEPRINT_FACT_KINDS = frozenset(
    {
        "WORLD_PREMISE",
        "PUBLIC_SYSTEM",
        "ACTOR_ENTITY",
        "VEHICLE_ENTITY",
        "OWNERSHIP",
        "PROTAGONIST_IDENTITY",
        "GROWTH_OBJECT",
        "RESOURCE_EXCLUSION",
        "EXCLUSIVE_RESOURCE",
        "PERMANENT_CONSUMPTION",
        "PEER_VEHICLE_CLASS",
    }
)
BLUEPRINT_DURABILITY_TIERS = frozenset({CANDIDATE_DURABLE})
BLUEPRINT_VISIBILITIES = frozenset({"PUBLIC_WORLD", "WORLD_HIDDEN", "ACTOR_SCOPED"})
PRESSURE_REQUIREMENT_IDS = (
    "req.progression",
    "req.exclusion",
    "req.resource",
    "req.deduction",
)
RECORDED_REQUIREMENT_IDS = (
    "req.ocean",
    "req.mass_drop",
    "req.peers",
    "req.vehicle",
    "req.ownership",
    "req.creature",
    "req.progression",
    "req.exclusion",
    "req.resource",
    "req.deduction",
    "req.other_vehicles",
)
PRESSURE_SELECTION_IDS = frozenset(
    {
        "actor.protagonist",
        "vehicle.protagonist",
        "resource.energy_crystal",
        "resource.wood",
        "resource.metal",
        PRESSURE_FEATURE_ID,
    }
)
# The V1-C recorded fixture has one finite fact kind for each Proposal item.
# These are stable contract identifiers, not a theme parser or a future
# Feature registry.
RECORDED_FACT_KINDS = {
    "req.ocean": "WORLD_PREMISE",
    "req.mass_drop": "PUBLIC_SYSTEM",
    "req.peers": "ACTOR_ENTITY",
    "req.vehicle": "VEHICLE_ENTITY",
    "req.ownership": "OWNERSHIP",
    "req.creature": "PROTAGONIST_IDENTITY",
    "req.progression": "GROWTH_OBJECT",
    "req.exclusion": "RESOURCE_EXCLUSION",
    "req.resource": "EXCLUSIVE_RESOURCE",
    "req.deduction": "PERMANENT_CONSUMPTION",
    "req.other_vehicles": "PEER_VEHICLE_CLASS",
}

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_ERROR_CODES = frozenset(
    {
        "INVALID_TYPE",
        "INVALID_VALUE",
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "DUPLICATE_ID",
        "LINEAGE_MISMATCH",
        "REQUIREMENT_SET_MISMATCH",
        "BLUEPRINT_HASH_MISMATCH",
        "BINDING_HASH_MISMATCH",
        "PRESSURE_SELECTION_MISMATCH",
        "PRESSURE_CONFIG_MISMATCH",
        "REPORT_NOT_VERIFIED",
        "REQUIREMENTS_GATE_BLOCKED",
        "CANDIDATE_HASH_MISMATCH",
        "INVALID_FACT_TIER",
        "INVALID_VISIBILITY",
    }
)


class ArtifactValidationError(ValueError):
    """Finite, machine-readable error shared by the three V1-C artifacts."""

    def __init__(
        self,
        code: str,
        path: str = "$",
        *,
        expected: str | None = None,
        actual: Any = None,
        message: str | None = None,
    ) -> None:
        if type(code) is not str or code not in _ERROR_CODES:
            raise ValueError(f"Unknown candidate artifact validation error code: {code}")
        self.code = code
        self.path = path
        self.expected = expected
        self.actual = _actual(actual) if actual is not None else None
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


class BlueprintValidationError(ArtifactValidationError):
    """Stable validation error for Blueprint and selection artifacts."""


def _actual(value: Any) -> str:
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
    error_cls: type[ArtifactValidationError] = BlueprintValidationError,
) -> None:
    raise error_cls(code, path, expected=expected, actual=actual, message=message)


def _check_type(value: Any, expected: type | tuple[type, ...], path: str, *, error_cls: type[ArtifactValidationError]) -> None:
    if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
        _fail("INVALID_TYPE", path, expected=getattr(expected, "__name__", "value"), actual=value, error_cls=error_cls)


def _validate_text(value: Any, path: str, *, error_cls: type[ArtifactValidationError], allow_empty: bool = False, max_length: int = 8192) -> str:
    if type(value) is not str:
        _fail("INVALID_TYPE", path, expected="string", actual=value, error_cls=error_cls)
    if not allow_empty and not value:
        _fail("INVALID_VALUE", path, expected="non-empty string", actual=value, error_cls=error_cls)
    if len(value) > max_length or "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        _fail("INVALID_VALUE", path, message="invalid text value", error_cls=error_cls)
    return value


def _validate_id(value: Any, path: str, *, error_cls: type[ArtifactValidationError]) -> str:
    value = _validate_text(value, path, error_cls=error_cls, max_length=128)
    if _ID_RE.fullmatch(value) is None:
        _fail("INVALID_VALUE", path, expected="lower-case stable identifier", actual=value, error_cls=error_cls)
    return value


def _validate_hash(value: Any, path: str, *, error_cls: type[ArtifactValidationError]) -> str:
    value = _validate_text(value, path, error_cls=error_cls, max_length=64)
    if _HEX64_RE.fullmatch(value) is None:
        _fail("INVALID_VALUE", path, expected="lower-case SHA-256 hex", actual=value, error_cls=error_cls)
    return value


def _normalize_ids(value: Any, path: str, *, error_cls: type[ArtifactValidationError], allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        _fail("INVALID_TYPE", path, expected="array", actual=value, error_cls=error_cls)
    if not allow_empty and not value:
        _fail("INVALID_VALUE", path, expected="non-empty array", actual=value, error_cls=error_cls)
    result = tuple(_validate_id(item, f"{path}[{index}]", error_cls=error_cls) for index, item in enumerate(value))
    if len(result) != len(set(result)):
        _fail("DUPLICATE_ID", path, message="duplicate identifier", error_cls=error_cls)
    return result


def _normalize_texts(value: Any, path: str, *, error_cls: type[ArtifactValidationError]) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        _fail("INVALID_TYPE", path, expected="array", actual=value, error_cls=error_cls)
    return tuple(
        _validate_text(item, f"{path}[{index}]", error_cls=error_cls)
        for index, item in enumerate(value)
    )


def _check_exact_fields(data: Mapping[str, Any], allowed: set[str], path: str, *, error_cls: type[ArtifactValidationError]) -> None:
    if any(type(key) is not str for key in data):
        _fail("INVALID_TYPE", path, expected="string keys", actual=data, error_cls=error_cls)
    keys = set(data)
    unknown = sorted(keys - allowed)
    if unknown:
        _fail("UNKNOWN_FIELD", f"{path}.{unknown[0]}", message="field is not part of this artifact", error_cls=error_cls)
    missing = sorted(allowed - keys)
    if missing:
        _fail("MISSING_FIELD", f"{path}.{missing[0]}", message="required field is missing", error_cls=error_cls)


def _canonical_payload(value: Any, *, error_cls: type[ArtifactValidationError]) -> str:
    try:
        return _models_canonical_json(value)
    except (GenesisValidationError, TypeError, ValueError, UnicodeError) as exc:
        _fail("INVALID_VALUE", "$", message="value is not canonical JSON", error_cls=error_cls)
        raise AssertionError("unreachable") from exc


def _hash_payload(value: Any, *, error_cls: type[ArtifactValidationError]) -> str:
    return hashlib.sha256(_canonical_payload(value, error_cls=error_cls).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True, init=False)
class BlueprintRequirementFact:
    requirement_id: str
    source_reference: str
    normalized_intent: str
    fact_kind: str
    durability_tier: str
    visibility: str
    subject_ids: tuple[str, ...]
    object_ids: tuple[str, ...]
    labels: tuple[str, ...]
    _typed_constraints_json: str = field(repr=False, compare=True)

    def __init__(
        self,
        requirement_id: str,
        source_reference: str,
        normalized_intent: str,
        fact_kind: str,
        durability_tier: str = CANDIDATE_DURABLE,
        visibility: str = "PUBLIC_WORLD",
        subject_ids: Sequence[str] = (),
        object_ids: Sequence[str] = (),
        labels: Sequence[str] = (),
        typed_constraints: Sequence[RequirementConstraint] = (),
    ) -> None:
        object.__setattr__(self, "requirement_id", _validate_id(requirement_id, "$.requirement_id", error_cls=BlueprintValidationError))
        object.__setattr__(self, "source_reference", _validate_text(source_reference, "$.source_reference", error_cls=BlueprintValidationError))
        object.__setattr__(self, "normalized_intent", _validate_text(normalized_intent, "$.normalized_intent", error_cls=BlueprintValidationError))
        if type(fact_kind) is not str or fact_kind not in BLUEPRINT_FACT_KINDS:
            _fail("INVALID_VALUE", "$.fact_kind", expected="finite Blueprint fact kind", actual=fact_kind, error_cls=BlueprintValidationError)
        object.__setattr__(self, "fact_kind", fact_kind)
        if type(durability_tier) is not str or durability_tier not in BLUEPRINT_DURABILITY_TIERS:
            _fail("INVALID_FACT_TIER", "$.durability_tier", expected=CANDIDATE_DURABLE, actual=durability_tier, error_cls=BlueprintValidationError)
        object.__setattr__(self, "durability_tier", durability_tier)
        if type(visibility) is not str or visibility not in BLUEPRINT_VISIBILITIES:
            _fail("INVALID_VISIBILITY", "$.visibility", expected="PUBLIC_WORLD|WORLD_HIDDEN|ACTOR_SCOPED", actual=visibility, error_cls=BlueprintValidationError)
        object.__setattr__(self, "visibility", visibility)
        object.__setattr__(self, "subject_ids", _normalize_ids(subject_ids, "$.subject_ids", error_cls=BlueprintValidationError))
        object.__setattr__(self, "object_ids", _normalize_ids(object_ids, "$.object_ids", error_cls=BlueprintValidationError))
        object.__setattr__(self, "labels", _normalize_texts(labels, "$.labels", error_cls=BlueprintValidationError))
        if not isinstance(typed_constraints, (list, tuple)):
            _fail("INVALID_TYPE", "$.typed_constraints", expected="array of RequirementConstraint", actual=typed_constraints, error_cls=BlueprintValidationError)
        if any(type(item) is not RequirementConstraint for item in typed_constraints):
            _fail("INVALID_TYPE", "$.typed_constraints", expected="RequirementConstraint objects", actual=typed_constraints, error_cls=BlueprintValidationError)
        constraint_ids = [item.constraint_id for item in typed_constraints]
        if len(constraint_ids) != len(set(constraint_ids)):
            _fail("DUPLICATE_ID", "$.typed_constraints", message="duplicate constraint identifier", error_cls=BlueprintValidationError)
        object.__setattr__(self, "_typed_constraints_json", _canonical_payload([item.to_dict() for item in typed_constraints], error_cls=BlueprintValidationError))

    @property
    def typed_constraints(self) -> tuple[RequirementConstraint, ...]:
        try:
            values = json.loads(self._typed_constraints_json)
            return tuple(RequirementConstraint.from_dict(item) for item in values)
        except (GenesisValidationError, TypeError, ValueError) as exc:
            raise BlueprintValidationError("INVALID_VALUE", "$.typed_constraints", message="stored constraints are invalid") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "source_reference": self.source_reference,
            "normalized_intent": self.normalized_intent,
            "fact_kind": self.fact_kind,
            "durability_tier": self.durability_tier,
            "visibility": self.visibility,
            "subject_ids": list(self.subject_ids),
            "object_ids": list(self.object_ids),
            "labels": list(self.labels),
            "typed_constraints": [item.to_dict() for item in self.typed_constraints],
        }

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict(), error_cls=BlueprintValidationError)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BlueprintRequirementFact":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data, error_cls=BlueprintValidationError)
        allowed = {
            "requirement_id",
            "source_reference",
            "normalized_intent",
            "fact_kind",
            "durability_tier",
            "visibility",
            "subject_ids",
            "object_ids",
            "labels",
            "typed_constraints",
        }
        _check_exact_fields(data, allowed, "$", error_cls=BlueprintValidationError)
        if not isinstance(data["typed_constraints"], list):
            _fail("INVALID_TYPE", "$.typed_constraints", expected="array", actual=data["typed_constraints"], error_cls=BlueprintValidationError)
        for index, constraint in enumerate(data["typed_constraints"]):
            if isinstance(constraint, Mapping) and any(type(key) is not str for key in constraint):
                _fail("INVALID_TYPE", f"$.typed_constraints[{index}]", expected="string keys", actual=constraint, error_cls=BlueprintValidationError)
        try:
            constraints = [RequirementConstraint.from_dict(item) for item in data["typed_constraints"]]
        except GenesisValidationError as exc:
            _fail("INVALID_VALUE", "$.typed_constraints", message=str(exc), error_cls=BlueprintValidationError)
        return cls(**dict(data, typed_constraints=constraints))


@dataclass(frozen=True, slots=True, init=False)
class BlueprintPressureSelection:
    protagonist_id: str
    growth_object_id: str
    growth_object_owner_id: str
    exclusive_resource_id: str
    excluded_common_resource_ids: tuple[str, ...]
    feature_id: str
    contract_version: str
    requirement_ids: tuple[str, ...]

    def __init__(
        self,
        protagonist_id: str,
        growth_object_id: str,
        growth_object_owner_id: str,
        exclusive_resource_id: str,
        excluded_common_resource_ids: Sequence[str],
        feature_id: str,
        contract_version: str,
        requirement_ids: Sequence[str] | None = None,
        *,
        bound_requirement_ids: Sequence[str] | None = None,
    ) -> None:
        if requirement_ids is None:
            requirement_ids = bound_requirement_ids
        elif bound_requirement_ids is not None and tuple(requirement_ids) != tuple(bound_requirement_ids):
            _fail("PRESSURE_SELECTION_MISMATCH", "$.requirement_ids", message="duplicate requirement aliases disagree", error_cls=BlueprintValidationError)
        if requirement_ids is None:
            _fail("MISSING_FIELD", "$.requirement_ids", message="pressure requirement IDs are required", error_cls=BlueprintValidationError)
        object.__setattr__(self, "protagonist_id", _validate_id(protagonist_id, "$.protagonist_id", error_cls=BlueprintValidationError))
        object.__setattr__(self, "growth_object_id", _validate_id(growth_object_id, "$.growth_object_id", error_cls=BlueprintValidationError))
        object.__setattr__(self, "growth_object_owner_id", _validate_id(growth_object_owner_id, "$.growth_object_owner_id", error_cls=BlueprintValidationError))
        object.__setattr__(self, "exclusive_resource_id", _validate_id(exclusive_resource_id, "$.exclusive_resource_id", error_cls=BlueprintValidationError))
        excluded = _normalize_ids(excluded_common_resource_ids, "$.excluded_common_resource_ids", error_cls=BlueprintValidationError, allow_empty=False)
        object.__setattr__(self, "excluded_common_resource_ids", excluded)
        object.__setattr__(self, "feature_id", _validate_id(feature_id, "$.feature_id", error_cls=BlueprintValidationError))
        object.__setattr__(self, "contract_version", _validate_text(contract_version, "$.contract_version", error_cls=BlueprintValidationError, max_length=32))
        normalized_requirements = _normalize_ids(requirement_ids, "$.requirement_ids", error_cls=BlueprintValidationError, allow_empty=False)
        object.__setattr__(self, "requirement_ids", normalized_requirements)
        if self.protagonist_id != "actor.protagonist" or self.growth_object_id != "vehicle.protagonist" or self.growth_object_owner_id != "actor.protagonist" or self.exclusive_resource_id != "resource.energy_crystal":
            _fail("PRESSURE_SELECTION_MISMATCH", "$.pressure_selection", message="pressure selection identity is not the recorded candidate contract", error_cls=BlueprintValidationError)
        if self.excluded_common_resource_ids != ("resource.wood", "resource.metal"):
            _fail("PRESSURE_SELECTION_MISMATCH", "$.excluded_common_resource_ids", message="pressure selection ordinary-resource exclusions are fixed", error_cls=BlueprintValidationError)
        if self.feature_id != PRESSURE_FEATURE_ID or self.contract_version != PRESSURE_CONTRACT_VERSION:
            _fail("PRESSURE_SELECTION_MISMATCH", "$.pressure_selection", message="pressure feature contract identity is fixed", error_cls=BlueprintValidationError)
        if self.requirement_ids != PRESSURE_REQUIREMENT_IDS:
            _fail("PRESSURE_SELECTION_MISMATCH", "$.requirement_ids", message="pressure selection must bind exactly the four pressure requirements", error_cls=BlueprintValidationError)

    @property
    def bound_requirement_ids(self) -> tuple[str, ...]:
        return self.requirement_ids

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict(), error_cls=BlueprintValidationError)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protagonist_id": self.protagonist_id,
            "growth_object_id": self.growth_object_id,
            "growth_object_owner_id": self.growth_object_owner_id,
            "exclusive_resource_id": self.exclusive_resource_id,
            "excluded_common_resource_ids": list(self.excluded_common_resource_ids),
            "feature_id": self.feature_id,
            "contract_version": self.contract_version,
            "requirement_ids": list(self.requirement_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BlueprintPressureSelection":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data, error_cls=BlueprintValidationError)
        allowed = {
            "protagonist_id",
            "growth_object_id",
            "growth_object_owner_id",
            "exclusive_resource_id",
            "excluded_common_resource_ids",
            "feature_id",
            "contract_version",
            "requirement_ids",
        }
        _check_exact_fields(data, allowed, "$", error_cls=BlueprintValidationError)
        return cls(**dict(data))


@dataclass(frozen=True, slots=True, init=False)
class WorldBlueprint:
    blueprint_schema_version: int
    blueprint_id: str
    source_request_id: str
    source_request_hash: str
    source_proposal_id: str
    source_proposal_hash: str
    source_approval_hash: str
    source_report_hash: str
    source_catalog_version: str
    source_catalog_hash: str
    genesis_seed: int | str
    content_locale: str
    _facts_json: str = field(repr=False, compare=True)
    _pressure_selection_json: str = field(repr=False, compare=True)
    generation_policy_reference: str

    def __init__(
        self,
        blueprint_schema_version: int,
        blueprint_id: str,
        source_request_id: str,
        source_request_hash: str,
        source_proposal_id: str,
        source_proposal_hash: str,
        source_approval_hash: str,
        source_report_hash: str,
        source_catalog_version: str,
        source_catalog_hash: str,
        genesis_seed: int | str,
        content_locale: str,
        facts: Sequence[BlueprintRequirementFact],
        pressure_selection: BlueprintPressureSelection,
        generation_policy_reference: str,
    ) -> None:
        if type(blueprint_schema_version) is not int or blueprint_schema_version != BLUEPRINT_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.blueprint_schema_version", expected=str(BLUEPRINT_SCHEMA_VERSION), actual=blueprint_schema_version, error_cls=BlueprintValidationError)
        object.__setattr__(self, "blueprint_schema_version", blueprint_schema_version)
        object.__setattr__(self, "blueprint_id", _validate_id(blueprint_id, "$.blueprint_id", error_cls=BlueprintValidationError))
        for name, value in (
            ("source_request_id", source_request_id),
            ("source_proposal_id", source_proposal_id),
        ):
            object.__setattr__(self, name, _validate_id(value, f"$.{name}", error_cls=BlueprintValidationError))
        for name, value in (
            ("source_request_hash", source_request_hash),
            ("source_proposal_hash", source_proposal_hash),
            ("source_approval_hash", source_approval_hash),
            ("source_report_hash", source_report_hash),
            ("source_catalog_hash", source_catalog_hash),
        ):
            object.__setattr__(self, name, _validate_hash(value, f"$.{name}", error_cls=BlueprintValidationError))
        object.__setattr__(self, "source_catalog_version", _validate_text(source_catalog_version, "$.source_catalog_version", error_cls=BlueprintValidationError, max_length=128))
        if type(genesis_seed) is int and not isinstance(genesis_seed, bool):
            if genesis_seed < 0:
                _fail("INVALID_VALUE", "$.genesis_seed", expected="non-negative integer", actual=genesis_seed, error_cls=BlueprintValidationError)
        elif type(genesis_seed) is str:
            _validate_text(genesis_seed, "$.genesis_seed", error_cls=BlueprintValidationError, max_length=256)
        else:
            _fail("INVALID_TYPE", "$.genesis_seed", expected="int or string", actual=genesis_seed, error_cls=BlueprintValidationError)
        object.__setattr__(self, "genesis_seed", genesis_seed)
        object.__setattr__(self, "content_locale", _validate_text(content_locale, "$.content_locale", error_cls=BlueprintValidationError, max_length=64))
        object.__setattr__(self, "generation_policy_reference", _validate_text(generation_policy_reference, "$.generation_policy_reference", error_cls=BlueprintValidationError))
        if not isinstance(facts, (list, tuple)):
            _fail("INVALID_TYPE", "$.facts", expected="array of BlueprintRequirementFact", actual=facts, error_cls=BlueprintValidationError)
        if not facts:
            _fail("INVALID_VALUE", "$.facts", expected="non-empty array", actual=facts, error_cls=BlueprintValidationError)
        if any(type(item) is not BlueprintRequirementFact for item in facts):
            _fail("INVALID_TYPE", "$.facts", expected="BlueprintRequirementFact objects", actual=facts, error_cls=BlueprintValidationError)
        fact_ids = [item.requirement_id for item in facts]
        if len(fact_ids) != len(set(fact_ids)):
            _fail("DUPLICATE_ID", "$.facts", message="duplicate requirement fact identifier", error_cls=BlueprintValidationError)
        if type(pressure_selection) is not BlueprintPressureSelection:
            _fail("INVALID_TYPE", "$.pressure_selection", expected="BlueprintPressureSelection", actual=pressure_selection, error_cls=BlueprintValidationError)
        object.__setattr__(self, "_facts_json", _canonical_payload([item.to_dict() for item in facts], error_cls=BlueprintValidationError))
        object.__setattr__(self, "_pressure_selection_json", _canonical_payload(pressure_selection.to_dict(), error_cls=BlueprintValidationError))

    @property
    def facts(self) -> tuple[BlueprintRequirementFact, ...]:
        try:
            return tuple(BlueprintRequirementFact.from_dict(item) for item in json.loads(self._facts_json))
        except (BlueprintValidationError, TypeError, ValueError) as exc:
            raise BlueprintValidationError("INVALID_VALUE", "$.facts", message="stored facts are invalid") from exc

    @property
    def pressure_selection(self) -> BlueprintPressureSelection:
        try:
            return BlueprintPressureSelection.from_dict(json.loads(self._pressure_selection_json))
        except (BlueprintValidationError, TypeError, ValueError) as exc:
            raise BlueprintValidationError("INVALID_VALUE", "$.pressure_selection", message="stored pressure selection is invalid") from exc

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict(), error_cls=BlueprintValidationError)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint_schema_version": self.blueprint_schema_version,
            "blueprint_id": self.blueprint_id,
            "source_request_id": self.source_request_id,
            "source_request_hash": self.source_request_hash,
            "source_proposal_id": self.source_proposal_id,
            "source_proposal_hash": self.source_proposal_hash,
            "source_approval_hash": self.source_approval_hash,
            "source_report_hash": self.source_report_hash,
            "source_catalog_version": self.source_catalog_version,
            "source_catalog_hash": self.source_catalog_hash,
            "genesis_seed": self.genesis_seed,
            "content_locale": self.content_locale,
            "facts": [fact.to_dict() for fact in self.facts],
            "pressure_selection": self.pressure_selection.to_dict(),
            "generation_policy_reference": self.generation_policy_reference,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorldBlueprint":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data, error_cls=BlueprintValidationError)
        allowed = {
            "blueprint_schema_version",
            "blueprint_id",
            "source_request_id",
            "source_request_hash",
            "source_proposal_id",
            "source_proposal_hash",
            "source_approval_hash",
            "source_report_hash",
            "source_catalog_version",
            "source_catalog_hash",
            "genesis_seed",
            "content_locale",
            "facts",
            "pressure_selection",
            "generation_policy_reference",
        }
        _check_exact_fields(data, allowed, "$", error_cls=BlueprintValidationError)
        if not isinstance(data["facts"], list):
            _fail("INVALID_TYPE", "$.facts", expected="array", actual=data["facts"], error_cls=BlueprintValidationError)
        return cls(
            blueprint_schema_version=data["blueprint_schema_version"],
            blueprint_id=data["blueprint_id"],
            source_request_id=data["source_request_id"],
            source_request_hash=data["source_request_hash"],
            source_proposal_id=data["source_proposal_id"],
            source_proposal_hash=data["source_proposal_hash"],
            source_approval_hash=data["source_approval_hash"],
            source_report_hash=data["source_report_hash"],
            source_catalog_version=data["source_catalog_version"],
            source_catalog_hash=data["source_catalog_hash"],
            genesis_seed=data["genesis_seed"],
            content_locale=data["content_locale"],
            facts=[BlueprintRequirementFact.from_dict(item) for item in data["facts"]],
            pressure_selection=BlueprintPressureSelection.from_dict(data["pressure_selection"]),
            generation_policy_reference=data["generation_policy_reference"],
        )


def validate_blueprint_lineage(
    blueprint: WorldBlueprint,
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    *,
    error_cls: type[ArtifactValidationError] = BlueprintValidationError,
) -> None:
    """Validate that Blueprint facts are an exact candidate projection of V1-A."""

    if type(blueprint) is not WorldBlueprint:
        _fail("INVALID_TYPE", "$.blueprint", expected="WorldBlueprint", actual=blueprint, error_cls=error_cls)
    if type(request) is not GenesisRequest or type(proposal) is not RequirementProposal or type(coverage_approval) is not RequirementCoverageApproval or type(report) is not FeatureRequirementReport or type(catalog) is not FeatureSupportCatalog:
        _fail("INVALID_TYPE", "$.lineage", expected="V1-A artifacts", error_cls=error_cls)
    expected_ids = (request.request_id, request.hash, proposal.proposal_id, proposal.hash, coverage_approval.hash, report.hash, catalog.version, catalog.hash)
    actual_ids = (
        blueprint.source_request_id,
        blueprint.source_request_hash,
        blueprint.source_proposal_id,
        blueprint.source_proposal_hash,
        blueprint.source_approval_hash,
        blueprint.source_report_hash,
        blueprint.source_catalog_version,
        blueprint.source_catalog_hash,
    )
    if actual_ids != expected_ids:
        _fail("LINEAGE_MISMATCH", "$.blueprint", message="Blueprint lineage does not match supplied V1-A artifacts", error_cls=error_cls)
    if blueprint.genesis_seed != request.genesis_seed:
        _fail("LINEAGE_MISMATCH", "$.blueprint.genesis_seed", message="Blueprint genesis seed differs from Request", error_cls=error_cls)
    if blueprint.content_locale != request.content_locale:
        _fail("LINEAGE_MISMATCH", "$.blueprint.content_locale", message="Blueprint content locale differs from Request", error_cls=error_cls)
    if blueprint.generation_policy_reference != request.generation_policy_reference:
        _fail("LINEAGE_MISMATCH", "$.blueprint.generation_policy_reference", message="Blueprint generation policy differs from Request", error_cls=error_cls)
    requirements = proposal.requirements
    facts = blueprint.facts
    requirement_ids = tuple(item.requirement_id for item in requirements)
    if requirement_ids != RECORDED_REQUIREMENT_IDS:
        _fail("REQUIREMENT_SET_MISMATCH", "$.blueprint.facts", message="V1-C Blueprint must use the recorded eleven-item Proposal fixture in canonical order", error_cls=error_cls)
    if len(facts) != len(requirements) or tuple(fact.requirement_id for fact in facts) != requirement_ids:
        _fail("REQUIREMENT_SET_MISMATCH", "$.blueprint.facts", message="Blueprint facts must cover Proposal requirements in canonical order", error_cls=error_cls)
    for index, (fact, requirement) in enumerate(zip(facts, requirements)):
        if fact.source_reference != requirement.source_reference or fact.normalized_intent != requirement.normalized_intent:
            _fail("LINEAGE_MISMATCH", f"$.blueprint.facts[{index}]", message="fact source or normalized intent differs from Proposal", error_cls=error_cls)
        if fact.durability_tier != CANDIDATE_DURABLE:
            _fail("INVALID_FACT_TIER", f"$.blueprint.facts[{index}].durability_tier", expected=CANDIDATE_DURABLE, actual=fact.durability_tier, error_cls=error_cls)
        if fact.typed_constraints != requirement.typed_constraints:
            _fail("LINEAGE_MISMATCH", f"$.blueprint.facts[{index}].typed_constraints", message="fact typed constraints differ from Proposal", error_cls=error_cls)
        expected_fact_kind = RECORDED_FACT_KINDS.get(requirement.requirement_id)
        if expected_fact_kind is None or fact.fact_kind != expected_fact_kind:
            _fail("PRESSURE_SELECTION_MISMATCH", f"$.blueprint.facts[{index}].fact_kind", message="fact kind is not the recorded V1-C semantic projection", error_cls=error_cls)
    selection = blueprint.pressure_selection
    fact_by_id = {fact.requirement_id: fact for fact in facts}
    expected_kinds = {requirement_id: RECORDED_FACT_KINDS[requirement_id] for requirement_id in PRESSURE_REQUIREMENT_IDS}
    for requirement_id, fact_kind in expected_kinds.items():
        if requirement_id not in fact_by_id or fact_by_id[requirement_id].fact_kind != fact_kind:
            _fail("PRESSURE_SELECTION_MISMATCH", f"$.blueprint.facts[{requirement_id}]", message="pressure fact kind does not match selected concrete contract", error_cls=error_cls)
    return None


__all__ = [
    "ArtifactValidationError",
    "BLUEPRINT_DURABILITY_TIERS",
    "BLUEPRINT_FACT_KINDS",
    "BLUEPRINT_SCHEMA_VERSION",
    "BLUEPRINT_VISIBILITIES",
    "BlueprintPressureSelection",
    "BlueprintRequirementFact",
    "BlueprintValidationError",
    "CANDIDATE_DURABLE",
    "RECORDED_FACT_KINDS",
    "RECORDED_REQUIREMENT_IDS",
    "PRESSURE_REQUIREMENT_IDS",
    "WorldBlueprint",
    "validate_blueprint_lineage",
]
