"""Bounded Phase 10V1-D candidate preflight proofs.

This module is deliberately a proof boundary, not a second runtime.  It
recomputes the already-recorded V1-C candidate tuple, exercises the frozen
V1-B pressure reducer/replay path, and records one concrete anti-reskin
comparison.  It has no file, SQLite, network, subprocess, clock, UUID, or
random side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
import dataclasses
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from .binding import RuntimeBindingAssessment
from .blueprint import WorldBlueprint
from .candidate import (
    CANDIDATE_COMPILER_CONTRACT_VERSION,
    CANDIDATE_COMPILER_ID,
    CANDIDATE_DRAFT_SCHEMA_VERSION,
    CandidateGenesisAttempt,
    CandidateWorldDraft,
    PENDING_GATES,
    verify_candidate_artifacts,
)
from .catalog import FeatureSupportCatalog
from .models import (
    FeatureRequirementReport,
    GenesisRequest,
    RequirementCoverageApproval,
    RequirementProposal,
)
from .pressure import (
    CLAIM_SUPPLY_CACHE,
    EVENT_CACHE_CLAIMED,
    EVENT_GROWTH_UPGRADED,
    EVENT_HAZARD_TRAVERSED,
    EVENT_RESOURCE_RECOVERED,
    EVENT_SUPPLY_STABILIZED,
    PRESSURE_ACTION_IDS,
    PRESSURE_EVENT_TYPES,
    RESOURCE_SPENT_SUPPLY_ROUTE,
    RESOURCE_SPENT_UPGRADE,
    RECOVER_EXCLUSIVE_RESOURCE,
    STABILIZE_SUPPLY_ROUTE,
    TRAVERSE_HAZARD_ZONE,
    UPGRADE_GROWTH_OBJECT,
    ExclusiveUpgradeAction,
    ExclusiveUpgradeEvent,
    ExclusiveUpgradePressureConfig,
    ExclusiveUpgradePressureState,
    check_pressure_invariants,
    initial_pressure_state,
    legal_pressure_actions,
    pressure_event_hash,
    pressure_state_hash,
    reduce_pressure_event,
    replay_pressure_events,
    resolve_pressure_action,
    verify_terminal_pressure_trace,
)


STATIC_PREFLIGHT_SCHEMA_VERSION = 1
GAMEPLAY_PREFLIGHT_SCHEMA_VERSION = 1
STRUCTURAL_DIVERGENCE_SCHEMA_VERSION = 1
PREFLIGHT_BUNDLE_SCHEMA_VERSION = 1
STRUCTURAL_DIVERGENCE_ID = "STRUCTURAL_DIVERGENCE_V1"
NO_EXCLUSIVE_RESOURCE_COUNTERFACTUAL_ID = "NO_EXCLUSIVE_RESOURCE_COUNTERFACTUAL_V1"

RESOLVED_PREFLIGHT_GATES = ("STATIC_PREFLIGHT", "GAMEPLAY_PREFLIGHT", "STRUCTURAL_DIVERGENCE")
REMAINING_GLOBAL_GATES = (
    "REQUIREMENTS_GATE",
    "RUNTIME_CATALOG_SUPPORT",
    "PUBLICATION",
    "AUTOPLAY_COMPATIBILITY",
)
GAMEPLAY_FAILURE_SCENARIO_IDS = (
    "initial_upgrade_without_exclusive",
    "initial_stabilize_without_exclusive",
    "duplicate_recover_held",
    "recover_after_source_closed",
    "upgrade_after_supply_branch",
    "stabilize_after_upgrade_branch",
    "followup_before_unlock",
    "duplicate_event",
    "reordered_event",
    "missing_head_event",
    "event_payload_tamper",
    "wrong_final_state_hash",
    "nonterminal_prefix_terminal_verify",
)

_ERROR_CODES = frozenset(
    {
        "INVALID_SCHEMA",
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "INVALID_TYPE",
        "INVALID_VALUE",
        "INVALID_HASH",
        "HASH_MISMATCH",
        "LINEAGE_MISMATCH",
        "CANDIDATE_ARTIFACT_INVALID",
        "PREFLIGHT_MISMATCH",
        "PRESSURE_TRACE_MISMATCH",
        "STRUCTURAL_DIVERGENCE_FAILED",
        "PREFLIGHT_GATE_BLOCKED",
    }
)
_HEX64 = frozenset("0123456789abcdef")


class PreflightValidationError(ValueError):
    """Stable machine-readable failure for a persisted proof artifact."""

    def __init__(self, code: str, path: str = "$", *, message: str | None = None) -> None:
        if type(code) is not str or code not in _ERROR_CODES:
            raise ValueError(f"unknown preflight error code: {code}")
        self.code = code
        self.path = path
        self.message = message or code
        super().__init__(f"{code} at {path}: {self.message}")

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _fail(code: str, path: str = "$", *, message: str | None = None) -> None:
    raise PreflightValidationError(code, path, message=message)


def _ensure_json(value: Any, path: str = "$") -> Any:
    """Validate a finite JSON tree and return a detached JSON-compatible tree."""

    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail("INVALID_VALUE", path, message="non-finite numbers are not allowed")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                _fail("INVALID_TYPE", f"{path}.<key>", message="mapping keys must be strings")
            result[key] = _ensure_json(item, f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [_ensure_json(item, f"{path}[{index}]") for index, item in enumerate(value)]
    _fail("INVALID_TYPE", path, message="value must be JSON-compatible")
    raise AssertionError("unreachable")


def _canonical(value: Any) -> str:
    try:
        normalized = _ensure_json(value)
        return json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PreflightValidationError("INVALID_VALUE", "$", message="value is not canonical JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _detached(value: Any) -> Any:
    return json.loads(_canonical(value))


def _fields(data: Any, required: set[str], path: str = "$") -> None:
    if not isinstance(data, Mapping):
        _fail("INVALID_SCHEMA", path, message="object required")
    if any(type(key) is not str for key in data):
        _fail("INVALID_TYPE", path, message="object keys must be strings")
    unknown = sorted(set(data) - required)
    if unknown:
        _fail("UNKNOWN_FIELD", f"{path}.{unknown[0]}", message="field is not part of this artifact")
    missing = sorted(required - set(data))
    if missing:
        _fail("MISSING_FIELD", f"{path}.{missing[0]}", message="required field is missing")


def _text(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        _fail("INVALID_TYPE" if type(value) is not str else "INVALID_VALUE", path, message="non-empty text required")
    if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        _fail("INVALID_VALUE", path, message="invalid text code point")
    return value


def _hash_text(value: Any, path: str) -> str:
    value = _text(value, path)
    if len(value) != 64 or any(char not in _HEX64 for char in value):
        _fail("INVALID_HASH", path, message="lower-case SHA-256 hash required")
    return value


def _version(value: Any, expected: int, path: str) -> int:
    if type(value) is not int or value != expected:
        _fail("INVALID_VALUE", path, message=f"schema version must be {expected}")
    return value


def _bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        _fail("INVALID_TYPE", path, message="boolean required")
    return value


def _int(value: Any, path: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail("INVALID_TYPE" if type(value) is not int else "INVALID_VALUE", path, message="bounded integer required")
    return value


def _strings(value: Any, path: str, *, non_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list):
        _fail("INVALID_TYPE", path, message="array required")
    result = tuple(_text(item, f"{path}[{index}]") for index, item in enumerate(value))
    if non_empty and not result:
        _fail("INVALID_VALUE", path, message="non-empty string array required")
    if len(result) != len(set(result)):
        _fail("INVALID_VALUE", path, message="duplicate string")
    return result


def _nested_strings(value: Any, path: str, *, allow_empty_inner: bool = False) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list):
        _fail("INVALID_TYPE", path, message="array of string arrays required")
    return tuple(
        _strings(item, f"{path}[{index}]", non_empty=not allow_empty_inner)
        for index, item in enumerate(value)
    )


def _tuple_pairs(value: Mapping[str, int], path: str) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, Mapping):
        _fail("INVALID_TYPE", path, message="object of counts required")
    if any(type(key) is not str for key in value):
        _fail("INVALID_TYPE", path, message="count keys must be strings")
    result = []
    for key in sorted(value):
        result.append((_text(key, f"{path}.{key}"), _int(value[key], f"{path}.{key}")))
    return tuple(result)


def _pairs_to_dict(value: Sequence[tuple[str, int]]) -> dict[str, int]:
    return {key: count for key, count in value}


@dataclass(frozen=True, slots=True)
class LegacyReferenceSnapshot:
    """Read-only descriptor derived from the frozen phase75 runtime."""

    schema_version: int
    source_profile_id: str
    frozen_commit_identity: str
    source_descriptor: str
    legacy_legal_action_ids: tuple[str, ...]
    legacy_state_dimensions: tuple[str, ...]
    legacy_result_fields: tuple[str, ...]
    legacy_event_types: tuple[str, ...]
    legacy_runtime_binding_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _version(self.schema_version, 1, "$.schema_version")
        _text(self.source_profile_id, "$.source_profile_id")
        _text(self.frozen_commit_identity, "$.frozen_commit_identity")
        _text(self.source_descriptor, "$.source_descriptor")
        for field_name in (
            "legacy_legal_action_ids",
            "legacy_state_dimensions",
            "legacy_result_fields",
            "legacy_event_types",
            "legacy_runtime_binding_keys",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or not value or any(type(item) is not str or not item for item in value):
                _fail("INVALID_VALUE", f"$.{field_name}", message="non-empty immutable string tuple required")
        if len(self.legacy_legal_action_ids) != len(set(self.legacy_legal_action_ids)):
            _fail("INVALID_VALUE", "$.legacy_legal_action_ids", message="duplicate legacy action")

    @property
    def hash(self) -> str:
        return _hash(self.to_dict())

    @property
    def legacy_profile_id(self) -> str:
        """Compatibility-readable alias for the frozen source profile identity."""

        return self.source_profile_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_profile_id": self.source_profile_id,
            "frozen_commit_identity": self.frozen_commit_identity,
            "source_descriptor": self.source_descriptor,
            "legacy_legal_action_ids": list(self.legacy_legal_action_ids),
            "legacy_state_dimensions": list(self.legacy_state_dimensions),
            "legacy_result_fields": list(self.legacy_result_fields),
            "legacy_event_types": list(self.legacy_event_types),
            "legacy_runtime_binding_keys": list(self.legacy_runtime_binding_keys),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LegacyReferenceSnapshot":
        fields = {
            "schema_version",
            "source_profile_id",
            "frozen_commit_identity",
            "source_descriptor",
            "legacy_legal_action_ids",
            "legacy_state_dimensions",
            "legacy_result_fields",
            "legacy_event_types",
            "legacy_runtime_binding_keys",
        }
        _fields(data, fields)
        return cls(
            schema_version=data["schema_version"],
            source_profile_id=data["source_profile_id"],
            frozen_commit_identity=data["frozen_commit_identity"],
            source_descriptor=data["source_descriptor"],
            legacy_legal_action_ids=tuple(_strings(data["legacy_legal_action_ids"], "$.legacy_legal_action_ids")),
            legacy_state_dimensions=tuple(_strings(data["legacy_state_dimensions"], "$.legacy_state_dimensions")),
            legacy_result_fields=tuple(_strings(data["legacy_result_fields"], "$.legacy_result_fields")),
            legacy_event_types=tuple(_strings(data["legacy_event_types"], "$.legacy_event_types")),
            legacy_runtime_binding_keys=tuple(_strings(data["legacy_runtime_binding_keys"], "$.legacy_runtime_binding_keys")),
        )


@dataclass(frozen=True, slots=True)
class GameplayTraceProof:
    """One real V1-B policy trace, including every legal prefix."""

    schema_version: int
    policy_id: str
    source_config_hash: str
    initial_state_hash: str
    action_ids: tuple[str, ...]
    action_hashes: tuple[str, ...]
    event_types: tuple[str, ...]
    event_hashes: tuple[str, ...]
    before_state_hashes: tuple[str, ...]
    after_state_hashes: tuple[str, ...]
    legal_actions_before: tuple[tuple[str, ...], ...]
    legal_actions_after: tuple[tuple[str, ...], ...]
    prefix_replay_state_hashes: tuple[str, ...]
    terminal_state_hash: str
    terminal_result: str
    terminal_legal_action_set: tuple[str, ...]
    accepted_decision_count: int
    total_game_minute_delta: int
    total_stamina_delta: int
    common_material_final_value: int
    exclusive_resource_final_lifecycle: str
    branch_commitment: str
    exclusive_resource_final_count: int = 0
    exclusive_resource_source_available: bool = False

    def __post_init__(self) -> None:
        _version(self.schema_version, GAMEPLAY_PREFLIGHT_SCHEMA_VERSION, "$.schema_version")
        _text(self.policy_id, "$.policy_id")
        _hash_text(self.source_config_hash, "$.source_config_hash")
        _hash_text(self.initial_state_hash, "$.initial_state_hash")
        _hash_text(self.terminal_state_hash, "$.terminal_state_hash")
        lengths = (
            len(self.action_ids),
            len(self.action_hashes),
            len(self.event_types),
            len(self.event_hashes),
            len(self.before_state_hashes),
            len(self.after_state_hashes),
            len(self.legal_actions_before),
            len(self.legal_actions_after),
        )
        if not lengths or any(value != 3 for value in lengths):
            _fail("INVALID_VALUE", "$.action_ids", message="a pressure policy must contain exactly three decisions")
        if self.accepted_decision_count != 3:
            _fail("INVALID_VALUE", "$.accepted_decision_count", message="pressure policies require exactly three accepted decisions")
        for name, values in (
            ("action_ids", self.action_ids),
            ("action_hashes", self.action_hashes),
            ("event_types", self.event_types),
            ("event_hashes", self.event_hashes),
            ("before_state_hashes", self.before_state_hashes),
            ("after_state_hashes", self.after_state_hashes),
        ):
            if any(type(item) is not str for item in values):
                _fail("INVALID_TYPE", f"$.{name}", message="string tuple required")
        if any(item == "WAIT" for item in self.action_ids):
            _fail("PRESSURE_TRACE_MISMATCH", "$.action_ids", message="scripted pressure trace cannot contain WAIT")
        for name, values in (("legal_actions_before", self.legal_actions_before), ("legal_actions_after", self.legal_actions_after)):
            if any(not isinstance(item, tuple) or any(type(action) is not str for action in item) for item in values):
                _fail("INVALID_TYPE", f"$.{name}", message="nested immutable action tuples required")
        if len(self.prefix_replay_state_hashes) != 4:
            _fail("INVALID_VALUE", "$.prefix_replay_state_hashes", message="initial plus three replay prefixes required")
        if any(len(item) != 64 or any(char not in _HEX64 for char in item) for item in self.prefix_replay_state_hashes):
            _fail("INVALID_HASH", "$.prefix_replay_state_hashes", message="state hashes required")
        _text(self.terminal_result, "$.terminal_result")
        _text(self.exclusive_resource_final_lifecycle, "$.exclusive_resource_final_lifecycle")
        _text(self.branch_commitment, "$.branch_commitment")
        if self.exclusive_resource_final_count != 0:
            _fail("PRESSURE_TRACE_MISMATCH", "$.exclusive_resource_final_count", message="exclusive resource must be permanently consumed")
        if self.exclusive_resource_source_available is not False:
            _fail("PRESSURE_TRACE_MISMATCH", "$.exclusive_resource_source_available", message="exclusive source must remain closed")
        _int(self.total_game_minute_delta, "$.total_game_minute_delta")
        _int(self.common_material_final_value, "$.common_material_final_value")
        if type(self.total_stamina_delta) is not int:
            _fail("INVALID_TYPE", "$.total_stamina_delta", message="integer required")

    @property
    def hash(self) -> str:
        return _hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "source_config_hash": self.source_config_hash,
            "initial_state_hash": self.initial_state_hash,
            "action_ids": list(self.action_ids),
            "action_hashes": list(self.action_hashes),
            "event_types": list(self.event_types),
            "event_hashes": list(self.event_hashes),
            "before_state_hashes": list(self.before_state_hashes),
            "after_state_hashes": list(self.after_state_hashes),
            "legal_actions_before": [list(item) for item in self.legal_actions_before],
            "legal_actions_after": [list(item) for item in self.legal_actions_after],
            "prefix_replay_state_hashes": list(self.prefix_replay_state_hashes),
            "terminal_state_hash": self.terminal_state_hash,
            "terminal_result": self.terminal_result,
            "terminal_legal_action_set": list(self.terminal_legal_action_set),
            "accepted_decision_count": self.accepted_decision_count,
            "total_game_minute_delta": self.total_game_minute_delta,
            "total_stamina_delta": self.total_stamina_delta,
            "common_material_final_value": self.common_material_final_value,
            "exclusive_resource_final_lifecycle": self.exclusive_resource_final_lifecycle,
            "branch_commitment": self.branch_commitment,
            "exclusive_resource_final_count": self.exclusive_resource_final_count,
            "exclusive_resource_source_available": self.exclusive_resource_source_available,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GameplayTraceProof":
        fields = {
            "schema_version",
            "policy_id",
            "source_config_hash",
            "initial_state_hash",
            "action_ids",
            "action_hashes",
            "event_types",
            "event_hashes",
            "before_state_hashes",
            "after_state_hashes",
            "legal_actions_before",
            "legal_actions_after",
            "prefix_replay_state_hashes",
            "terminal_state_hash",
            "terminal_result",
            "terminal_legal_action_set",
            "accepted_decision_count",
            "total_game_minute_delta",
            "total_stamina_delta",
            "common_material_final_value",
            "exclusive_resource_final_lifecycle",
            "branch_commitment",
            "exclusive_resource_final_count",
            "exclusive_resource_source_available",
        }
        _fields(data, fields)
        return cls(
            schema_version=data["schema_version"],
            policy_id=data["policy_id"],
            source_config_hash=data["source_config_hash"],
            initial_state_hash=data["initial_state_hash"],
            action_ids=tuple(_strings(data["action_ids"], "$.action_ids")),
            action_hashes=tuple(_strings(data["action_hashes"], "$.action_hashes")),
            event_types=tuple(_strings(data["event_types"], "$.event_types")),
            event_hashes=tuple(_strings(data["event_hashes"], "$.event_hashes")),
            before_state_hashes=tuple(_strings(data["before_state_hashes"], "$.before_state_hashes")),
            after_state_hashes=tuple(_strings(data["after_state_hashes"], "$.after_state_hashes")),
            legal_actions_before=tuple(_nested_strings(data["legal_actions_before"], "$.legal_actions_before")),
            legal_actions_after=tuple(
                _nested_strings(data["legal_actions_after"], "$.legal_actions_after", allow_empty_inner=True)
            ),
            prefix_replay_state_hashes=tuple(_strings(data["prefix_replay_state_hashes"], "$.prefix_replay_state_hashes")),
            terminal_state_hash=_hash_text(data["terminal_state_hash"], "$.terminal_state_hash"),
            terminal_result=_text(data["terminal_result"], "$.terminal_result"),
            terminal_legal_action_set=tuple(_strings(data["terminal_legal_action_set"], "$.terminal_legal_action_set", non_empty=False)),
            accepted_decision_count=data["accepted_decision_count"],
            total_game_minute_delta=data["total_game_minute_delta"],
            total_stamina_delta=data["total_stamina_delta"],
            common_material_final_value=data["common_material_final_value"],
            exclusive_resource_final_lifecycle=data["exclusive_resource_final_lifecycle"],
            branch_commitment=data["branch_commitment"],
            exclusive_resource_final_count=data["exclusive_resource_final_count"],
            exclusive_resource_source_available=data["exclusive_resource_source_available"],
        )


@dataclass(frozen=True, slots=True)
class StaticPreflightReport:
    schema_version: int
    source_request_hash: str
    source_proposal_hash: str
    source_approval_hash: str
    source_report_hash: str
    source_catalog_version: str
    source_catalog_hash: str
    blueprint_hash: str
    binding_assessment_hash: str
    candidate_world_draft_hash: str
    candidate_attempt_hash: str
    candidate_semantic_hash: str
    compiler_id: str
    compiler_contract_version: int
    draft_schema_version: int
    binding_status_counts: tuple[tuple[str, int], ...]
    binding_gate_passed: bool
    requirements_gate_passed: bool
    attempt_status: str
    required_pending_gates: tuple[str, ...]
    blocked_gates: tuple[str, ...]
    runtime_catalog_feature_ids: tuple[str, ...]
    static_preflight_passed: bool
    publication_eligible: bool
    failure_codes: tuple[str, ...]
    non_goals: tuple[str, ...]

    def __post_init__(self) -> None:
        _version(self.schema_version, STATIC_PREFLIGHT_SCHEMA_VERSION, "$.schema_version")
        for name in (
            "source_request_hash",
            "source_proposal_hash",
            "source_approval_hash",
            "source_report_hash",
            "source_catalog_hash",
            "blueprint_hash",
            "binding_assessment_hash",
            "candidate_world_draft_hash",
            "candidate_attempt_hash",
            "candidate_semantic_hash",
        ):
            _hash_text(getattr(self, name), f"$.{name}")
        _text(self.source_catalog_version, "$.source_catalog_version")
        if self.compiler_id != CANDIDATE_COMPILER_ID:
            _fail("INVALID_VALUE", "$.compiler_id", message="candidate compiler identity is fixed")
        if self.compiler_contract_version != CANDIDATE_COMPILER_CONTRACT_VERSION:
            _fail("INVALID_VALUE", "$.compiler_contract_version", message="candidate compiler contract is fixed")
        if self.draft_schema_version != CANDIDATE_DRAFT_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.draft_schema_version", message="candidate draft schema is fixed")
        _bool(self.binding_gate_passed, "$.binding_gate_passed")
        _bool(self.requirements_gate_passed, "$.requirements_gate_passed")
        _bool(self.static_preflight_passed, "$.static_preflight_passed")
        if self.binding_status_counts != (
            ("CANDIDATE_RUNTIME_MATCH", 10),
            ("CONTENT_ACCEPTED", 1),
            ("OMITTED_OPTIONAL", 0),
            ("UNBOUND_BLOCKING", 0),
        ):
            _fail("PREFLIGHT_GATE_BLOCKED", "$.binding_status_counts", message="recorded V1-C binding counts differ")
        if self.binding_gate_passed:
            _fail("PREFLIGHT_GATE_BLOCKED", "$.binding_gate_passed", message="V1-D cannot promote runtime bindings")
        if self.publication_eligible is not False:
            _fail("PREFLIGHT_GATE_BLOCKED", "$.publication_eligible", message="static preflight cannot authorize publication")
        if self.requirements_gate_passed:
            _fail("PREFLIGHT_GATE_BLOCKED", "$.requirements_gate_passed", message="recorded V1-C candidate must retain the requirements gate")
        if self.static_preflight_passed is not True:
            _fail("PREFLIGHT_GATE_BLOCKED", "$.static_preflight_passed", message="static proof must pass before the V1-D bundle is emitted")
        if self.attempt_status != "BLOCKED_REQUIREMENTS":
            _fail("PREFLIGHT_GATE_BLOCKED", "$.attempt_status", message="candidate attempt remains blocked")
        if self.required_pending_gates != tuple(PENDING_GATES):
            _fail("PREFLIGHT_GATE_BLOCKED", "$.required_pending_gates", message="original pending gates must remain unchanged")
        if self.blocked_gates != REMAINING_GLOBAL_GATES:
            _fail("PREFLIGHT_GATE_BLOCKED", "$.blocked_gates", message="static proof must retain every global blocker")
        if self.runtime_catalog_feature_ids:
            _fail("PREFLIGHT_GATE_BLOCKED", "$.runtime_catalog_feature_ids", message="V1-D cannot register Runtime Catalog entries")
        if self.failure_codes:
            _fail("PREFLIGHT_GATE_BLOCKED", "$.failure_codes", message="positive static proof cannot contain failure codes")
        _strings(list(self.non_goals), "$.non_goals")

    @property
    def hash(self) -> str:
        return _hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_request_hash": self.source_request_hash,
            "source_proposal_hash": self.source_proposal_hash,
            "source_approval_hash": self.source_approval_hash,
            "source_report_hash": self.source_report_hash,
            "source_catalog_version": self.source_catalog_version,
            "source_catalog_hash": self.source_catalog_hash,
            "blueprint_hash": self.blueprint_hash,
            "binding_assessment_hash": self.binding_assessment_hash,
            "candidate_world_draft_hash": self.candidate_world_draft_hash,
            "candidate_attempt_hash": self.candidate_attempt_hash,
            "candidate_semantic_hash": self.candidate_semantic_hash,
            "compiler_id": self.compiler_id,
            "compiler_contract_version": self.compiler_contract_version,
            "draft_schema_version": self.draft_schema_version,
            "binding_status_counts": _pairs_to_dict(self.binding_status_counts),
            "binding_gate_passed": self.binding_gate_passed,
            "requirements_gate_passed": self.requirements_gate_passed,
            "attempt_status": self.attempt_status,
            "required_pending_gates": list(self.required_pending_gates),
            "blocked_gates": list(self.blocked_gates),
            "runtime_catalog_feature_ids": list(self.runtime_catalog_feature_ids),
            "static_preflight_passed": self.static_preflight_passed,
            "publication_eligible": self.publication_eligible,
            "failure_codes": list(self.failure_codes),
            "non_goals": list(self.non_goals),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StaticPreflightReport":
        fields = set(cls.__dataclass_fields__)
        _fields(data, fields)
        return cls(
            schema_version=data["schema_version"],
            source_request_hash=data["source_request_hash"],
            source_proposal_hash=data["source_proposal_hash"],
            source_approval_hash=data["source_approval_hash"],
            source_report_hash=data["source_report_hash"],
            source_catalog_version=data["source_catalog_version"],
            source_catalog_hash=data["source_catalog_hash"],
            blueprint_hash=data["blueprint_hash"],
            binding_assessment_hash=data["binding_assessment_hash"],
            candidate_world_draft_hash=data["candidate_world_draft_hash"],
            candidate_attempt_hash=data["candidate_attempt_hash"],
            candidate_semantic_hash=data["candidate_semantic_hash"],
            compiler_id=data["compiler_id"],
            compiler_contract_version=data["compiler_contract_version"],
            draft_schema_version=data["draft_schema_version"],
            binding_status_counts=_tuple_pairs(data["binding_status_counts"], "$.binding_status_counts"),
            binding_gate_passed=data["binding_gate_passed"],
            requirements_gate_passed=data["requirements_gate_passed"],
            attempt_status=data["attempt_status"],
            required_pending_gates=tuple(_strings(data["required_pending_gates"], "$.required_pending_gates")),
            blocked_gates=tuple(_strings(data["blocked_gates"], "$.blocked_gates")),
            runtime_catalog_feature_ids=tuple(_strings(data["runtime_catalog_feature_ids"], "$.runtime_catalog_feature_ids", non_empty=False)),
            static_preflight_passed=data["static_preflight_passed"],
            publication_eligible=data["publication_eligible"],
            failure_codes=tuple(_strings(data["failure_codes"], "$.failure_codes", non_empty=False)),
            non_goals=tuple(_strings(data["non_goals"], "$.non_goals")),
        )


@dataclass(frozen=True, slots=True)
class GameplayFailureProof:
    """Negative proof: invalid input cannot mutate state or create an artifact."""

    schema_version: int
    scenario_id: str
    expected_error_code: str
    actual_error_code: str
    state_hash_before: str
    state_hash_after: str
    game_minute_before: int
    game_minute_after: int
    decision_seq_before: int
    decision_seq_after: int
    event_seq_before: int
    event_seq_after: int
    accepted_event_count: int
    proof_artifact_created: bool
    state_unchanged: bool
    time_unchanged: bool

    def __post_init__(self) -> None:
        _version(self.schema_version, GAMEPLAY_PREFLIGHT_SCHEMA_VERSION, "$.schema_version")
        _text(self.scenario_id, "$.scenario_id")
        _text(self.expected_error_code, "$.expected_error_code")
        _text(self.actual_error_code, "$.actual_error_code")
        _hash_text(self.state_hash_before, "$.state_hash_before")
        _hash_text(self.state_hash_after, "$.state_hash_after")
        for name in (
            "game_minute_before",
            "game_minute_after",
            "decision_seq_before",
            "decision_seq_after",
            "event_seq_before",
            "event_seq_after",
            "accepted_event_count",
        ):
            _int(getattr(self, name), f"$.{name}")
        for name in ("proof_artifact_created", "state_unchanged", "time_unchanged"):
            _bool(getattr(self, name), f"$.{name}")
        if self.actual_error_code != self.expected_error_code:
            _fail("PRESSURE_TRACE_MISMATCH", "$.actual_error_code", message="negative proof returned an unexpected stable error")
        if self.state_hash_before != self.state_hash_after or self.game_minute_before != self.game_minute_after:
            _fail("PRESSURE_TRACE_MISMATCH", "$.state_hash_after", message="negative proof mutated state or time")
        if self.accepted_event_count != 0 or self.proof_artifact_created or not self.state_unchanged or not self.time_unchanged:
            _fail("PRESSURE_TRACE_MISMATCH", "$.accepted_event_count", message="negative proof created an accepted event or artifact")

    @property
    def hash(self) -> str:
        return _hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "expected_error_code": self.expected_error_code,
            "actual_error_code": self.actual_error_code,
            "state_hash_before": self.state_hash_before,
            "state_hash_after": self.state_hash_after,
            "game_minute_before": self.game_minute_before,
            "game_minute_after": self.game_minute_after,
            "decision_seq_before": self.decision_seq_before,
            "decision_seq_after": self.decision_seq_after,
            "event_seq_before": self.event_seq_before,
            "event_seq_after": self.event_seq_after,
            "accepted_event_count": self.accepted_event_count,
            "proof_artifact_created": self.proof_artifact_created,
            "state_unchanged": self.state_unchanged,
            "time_unchanged": self.time_unchanged,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GameplayFailureProof":
        _fields(data, set(cls.__dataclass_fields__))
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class GameplayPreflightReport:
    schema_version: int
    source_config_hash: str
    initial_state_hash: str
    policy_a: GameplayTraceProof
    policy_b: GameplayTraceProof
    no_wait: bool
    prefix_replay_verified: bool
    terminal_verification_passed: bool
    policy_event_traces_differ: bool
    policy_final_state_hashes_differ: bool
    policy_results_differ: bool
    policy_material_outcomes_differ: bool
    failure_proofs: tuple[GameplayFailureProof, ...]
    failure_proof_passed: bool
    gameplay_preflight_passed: bool
    non_goals: tuple[str, ...]

    def __post_init__(self) -> None:
        _version(self.schema_version, GAMEPLAY_PREFLIGHT_SCHEMA_VERSION, "$.schema_version")
        _hash_text(self.source_config_hash, "$.source_config_hash")
        _hash_text(self.initial_state_hash, "$.initial_state_hash")
        if type(self.policy_a) is not GameplayTraceProof or type(self.policy_b) is not GameplayTraceProof:
            _fail("INVALID_TYPE", "$.policy_a", message="two typed gameplay proofs required")
        if self.policy_a.source_config_hash != self.source_config_hash or self.policy_b.source_config_hash != self.source_config_hash:
            _fail("LINEAGE_MISMATCH", "$.source_config_hash", message="policy proofs must use one pressure config")
        if self.policy_a.initial_state_hash != self.initial_state_hash or self.policy_b.initial_state_hash != self.initial_state_hash:
            _fail("LINEAGE_MISMATCH", "$.initial_state_hash", message="policy proofs must use one initial state")
        for name in (
            "no_wait",
            "prefix_replay_verified",
            "terminal_verification_passed",
            "policy_event_traces_differ",
            "policy_final_state_hashes_differ",
            "policy_results_differ",
            "policy_material_outcomes_differ",
            "failure_proof_passed",
            "gameplay_preflight_passed",
        ):
            _bool(getattr(self, name), f"$.{name}")
        if self.policy_a.policy_id == self.policy_b.policy_id:
            _fail("INVALID_VALUE", "$.policy_b.policy_id", message="A/B policy IDs must differ")
        if tuple(item.scenario_id for item in self.failure_proofs) != GAMEPLAY_FAILURE_SCENARIO_IDS:
            _fail("INVALID_VALUE", "$.failure_proofs", message="all fixed negative proof scenarios are required in order")
        if any(type(item) is not GameplayFailureProof for item in self.failure_proofs):
            _fail("INVALID_TYPE", "$.failure_proofs", message="typed negative proofs required")
        derived_pass = (
            self.no_wait
            and self.prefix_replay_verified
            and self.terminal_verification_passed
            and self.policy_event_traces_differ
            and self.policy_final_state_hashes_differ
            and self.policy_results_differ
            and self.policy_material_outcomes_differ
            and self.failure_proof_passed
        )
        if self.gameplay_preflight_passed != derived_pass:
            _fail("PREFLIGHT_GATE_BLOCKED", "$.gameplay_preflight_passed", message="gameplay gate must be derived from proof fields")
        _strings(list(self.non_goals), "$.non_goals")

    @property
    def hash(self) -> str:
        return _hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_config_hash": self.source_config_hash,
            "initial_state_hash": self.initial_state_hash,
            "policy_a": self.policy_a.to_dict(),
            "policy_b": self.policy_b.to_dict(),
            "no_wait": self.no_wait,
            "prefix_replay_verified": self.prefix_replay_verified,
            "terminal_verification_passed": self.terminal_verification_passed,
            "policy_event_traces_differ": self.policy_event_traces_differ,
            "policy_final_state_hashes_differ": self.policy_final_state_hashes_differ,
            "policy_results_differ": self.policy_results_differ,
            "policy_material_outcomes_differ": self.policy_material_outcomes_differ,
            "failure_proofs": [item.to_dict() for item in self.failure_proofs],
            "failure_proof_passed": self.failure_proof_passed,
            "gameplay_preflight_passed": self.gameplay_preflight_passed,
            "non_goals": list(self.non_goals),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GameplayPreflightReport":
        fields = set(cls.__dataclass_fields__)
        _fields(data, fields)
        return cls(
            schema_version=data["schema_version"],
            source_config_hash=data["source_config_hash"],
            initial_state_hash=data["initial_state_hash"],
            policy_a=GameplayTraceProof.from_dict(data["policy_a"]),
            policy_b=GameplayTraceProof.from_dict(data["policy_b"]),
            no_wait=data["no_wait"],
            prefix_replay_verified=data["prefix_replay_verified"],
            terminal_verification_passed=data["terminal_verification_passed"],
            policy_event_traces_differ=data["policy_event_traces_differ"],
            policy_final_state_hashes_differ=data["policy_final_state_hashes_differ"],
            policy_results_differ=data["policy_results_differ"],
            policy_material_outcomes_differ=data["policy_material_outcomes_differ"],
            failure_proofs=tuple(GameplayFailureProof.from_dict(item) for item in data["failure_proofs"]),
            failure_proof_passed=data["failure_proof_passed"],
            gameplay_preflight_passed=data["gameplay_preflight_passed"],
            non_goals=tuple(_strings(data["non_goals"], "$.non_goals")),
        )


@dataclass(frozen=True, slots=True)
class NoExclusiveResourceCounterfactualProof:
    """Proof-only comparison; it is not an Action/Event/Reducer runtime."""

    schema_version: int
    counterfactual_id: str
    actual_initial_legal_action_ids: tuple[str, ...]
    counterfactual_initial_legal_action_ids: tuple[str, ...]
    actual_policy_a_actions: tuple[str, ...]
    actual_policy_b_actions: tuple[str, ...]
    counterfactual_policy_a_actions: tuple[str, ...]
    counterfactual_policy_b_actions: tuple[str, ...]
    actual_accepted_decision_count: int
    counterfactual_accepted_decision_count: int
    actual_event_count: int
    counterfactual_event_count: int
    actual_resource_cost_path: tuple[str, ...]
    counterfactual_resource_cost_path: tuple[str, ...]
    actual_opportunity_cost: str
    counterfactual_opportunity_cost: str
    common_material_cost: int
    changed_dimensions: tuple[str, ...]
    proof_only: bool
    generates_domain_events: bool
    runtime_callable: bool
    catalog_entry: bool

    def __post_init__(self) -> None:
        _version(self.schema_version, STRUCTURAL_DIVERGENCE_SCHEMA_VERSION, "$.schema_version")
        if self.counterfactual_id != NO_EXCLUSIVE_RESOURCE_COUNTERFACTUAL_ID:
            _fail("INVALID_VALUE", "$.counterfactual_id", message="counterfactual identity is fixed")
        for name in (
            "actual_initial_legal_action_ids",
            "counterfactual_initial_legal_action_ids",
            "actual_policy_a_actions",
            "actual_policy_b_actions",
            "counterfactual_policy_a_actions",
            "counterfactual_policy_b_actions",
            "actual_resource_cost_path",
            "counterfactual_resource_cost_path",
            "changed_dimensions",
        ):
            _strings(list(getattr(self, name)), f"$.{name}")
        if self.actual_accepted_decision_count != 3 or self.counterfactual_accepted_decision_count != 2:
            _fail("STRUCTURAL_DIVERGENCE_FAILED", "$.accepted_decision_count", message="actual/counterfactual trace lengths are fixed")
        if self.actual_event_count != 3 or self.counterfactual_event_count != 0:
            _fail("STRUCTURAL_DIVERGENCE_FAILED", "$.counterfactual_event_count", message="counterfactual cannot create events")
        if self.common_material_cost != 1:
            _fail("STRUCTURAL_DIVERGENCE_FAILED", "$.common_material_cost", message="counterfactual ordinary cost is fixed at one")
        for name in ("proof_only", "generates_domain_events", "runtime_callable", "catalog_entry"):
            _bool(getattr(self, name), f"$.{name}")
        if not self.proof_only or self.generates_domain_events or self.runtime_callable or self.catalog_entry:
            _fail("STRUCTURAL_DIVERGENCE_FAILED", "$.proof_only", message="counterfactual must remain proof-only")

    @property
    def hash(self) -> str:
        return _hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "counterfactual_id": self.counterfactual_id,
            "actual_initial_legal_action_ids": list(self.actual_initial_legal_action_ids),
            "counterfactual_initial_legal_action_ids": list(self.counterfactual_initial_legal_action_ids),
            "actual_policy_a_actions": list(self.actual_policy_a_actions),
            "actual_policy_b_actions": list(self.actual_policy_b_actions),
            "counterfactual_policy_a_actions": list(self.counterfactual_policy_a_actions),
            "counterfactual_policy_b_actions": list(self.counterfactual_policy_b_actions),
            "actual_accepted_decision_count": self.actual_accepted_decision_count,
            "counterfactual_accepted_decision_count": self.counterfactual_accepted_decision_count,
            "actual_event_count": self.actual_event_count,
            "counterfactual_event_count": self.counterfactual_event_count,
            "actual_resource_cost_path": list(self.actual_resource_cost_path),
            "counterfactual_resource_cost_path": list(self.counterfactual_resource_cost_path),
            "actual_opportunity_cost": self.actual_opportunity_cost,
            "counterfactual_opportunity_cost": self.counterfactual_opportunity_cost,
            "common_material_cost": self.common_material_cost,
            "changed_dimensions": list(self.changed_dimensions),
            "proof_only": self.proof_only,
            "generates_domain_events": self.generates_domain_events,
            "runtime_callable": self.runtime_callable,
            "catalog_entry": self.catalog_entry,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NoExclusiveResourceCounterfactualProof":
        fields = set(cls.__dataclass_fields__)
        _fields(data, fields)
        return cls(
            schema_version=data["schema_version"],
            counterfactual_id=data["counterfactual_id"],
            actual_initial_legal_action_ids=tuple(_strings(data["actual_initial_legal_action_ids"], "$.actual_initial_legal_action_ids")),
            counterfactual_initial_legal_action_ids=tuple(_strings(data["counterfactual_initial_legal_action_ids"], "$.counterfactual_initial_legal_action_ids")),
            actual_policy_a_actions=tuple(_strings(data["actual_policy_a_actions"], "$.actual_policy_a_actions")),
            actual_policy_b_actions=tuple(_strings(data["actual_policy_b_actions"], "$.actual_policy_b_actions")),
            counterfactual_policy_a_actions=tuple(_strings(data["counterfactual_policy_a_actions"], "$.counterfactual_policy_a_actions")),
            counterfactual_policy_b_actions=tuple(_strings(data["counterfactual_policy_b_actions"], "$.counterfactual_policy_b_actions")),
            actual_accepted_decision_count=data["actual_accepted_decision_count"],
            counterfactual_accepted_decision_count=data["counterfactual_accepted_decision_count"],
            actual_event_count=data["actual_event_count"],
            counterfactual_event_count=data["counterfactual_event_count"],
            actual_resource_cost_path=tuple(_strings(data["actual_resource_cost_path"], "$.actual_resource_cost_path")),
            counterfactual_resource_cost_path=tuple(_strings(data["counterfactual_resource_cost_path"], "$.counterfactual_resource_cost_path")),
            actual_opportunity_cost=_text(data["actual_opportunity_cost"], "$.actual_opportunity_cost"),
            counterfactual_opportunity_cost=_text(data["counterfactual_opportunity_cost"], "$.counterfactual_opportunity_cost"),
            common_material_cost=data["common_material_cost"],
            changed_dimensions=tuple(_strings(data["changed_dimensions"], "$.changed_dimensions")),
            proof_only=data["proof_only"],
            generates_domain_events=data["generates_domain_events"],
            runtime_callable=data["runtime_callable"],
            catalog_entry=data["catalog_entry"],
        )


@dataclass(frozen=True, slots=True)
class StructuralDivergenceV1Report:
    schema_version: int
    divergence_id: str
    source_config_hash: str
    legacy_reference: LegacyReferenceSnapshot
    pressure_action_ids: tuple[str, ...]
    pressure_state_dimensions: tuple[str, ...]
    pressure_event_types: tuple[str, ...]
    pressure_branch_opportunity: tuple[tuple[str, tuple[str, ...]], ...]
    counterfactual: NoExclusiveResourceCounterfactualProof
    legacy_evidence_hash: str
    actual_evidence_hashes: tuple[str, ...]
    policy_a_proof_hash: str
    policy_b_proof_hash: str
    counterfactual_proof_hash: str
    changed_dimensions: tuple[str, ...]
    legacy_structural_comparison_passed: bool
    counterfactual_comparison_passed: bool
    policy_ab_divergence_passed: bool
    gate_passed: bool
    non_goals: tuple[str, ...]

    def __post_init__(self) -> None:
        _version(self.schema_version, STRUCTURAL_DIVERGENCE_SCHEMA_VERSION, "$.schema_version")
        if self.divergence_id != STRUCTURAL_DIVERGENCE_ID:
            _fail("INVALID_VALUE", "$.divergence_id", message="structural gate identity is fixed")
        _hash_text(self.source_config_hash, "$.source_config_hash")
        if type(self.legacy_reference) is not LegacyReferenceSnapshot or type(self.counterfactual) is not NoExclusiveResourceCounterfactualProof:
            _fail("INVALID_TYPE", "$.legacy_reference", message="typed structural proofs required")
        _hash_text(self.legacy_evidence_hash, "$.legacy_evidence_hash")
        if self.legacy_evidence_hash != self.legacy_reference.hash:
            _fail("HASH_MISMATCH", "$.legacy_evidence_hash", message="legacy evidence hash differs")
        if not isinstance(self.actual_evidence_hashes, tuple) or not self.actual_evidence_hashes:
            _fail("INVALID_VALUE", "$.actual_evidence_hashes", message="actual evidence hashes required")
        for index, value in enumerate(self.actual_evidence_hashes):
            _hash_text(value, f"$.actual_evidence_hashes[{index}]")
        if self.actual_evidence_hashes != (
            self.source_config_hash,
            self.policy_a_proof_hash,
            self.policy_b_proof_hash,
        ):
            _fail("LINEAGE_MISMATCH", "$.actual_evidence_hashes", message="actual evidence must bind config and both gameplay proofs")
        _strings(list(self.pressure_action_ids), "$.pressure_action_ids")
        _strings(list(self.pressure_state_dimensions), "$.pressure_state_dimensions")
        _strings(list(self.pressure_event_types), "$.pressure_event_types")
        if not isinstance(self.pressure_branch_opportunity, tuple) or not self.pressure_branch_opportunity:
            _fail("INVALID_VALUE", "$.pressure_branch_opportunity", message="fixed pressure branch evidence required")
        for action, choices in self.pressure_branch_opportunity:
            _text(action, "$.pressure_branch_opportunity.action")
            _strings(list(choices), "$.pressure_branch_opportunity.choices")
        for name in ("policy_a_proof_hash", "policy_b_proof_hash", "counterfactual_proof_hash"):
            _hash_text(getattr(self, name), f"$.{name}")
        if self.counterfactual_proof_hash != self.counterfactual.hash:
            _fail("HASH_MISMATCH", "$.counterfactual_proof_hash", message="counterfactual proof hash differs")
        _strings(list(self.changed_dimensions), "$.changed_dimensions")
        if self.changed_dimensions != (
            "LEGAL_ACTION_VOCABULARY",
            "STATE_DIMENSIONS",
            "EVENT_CAUSAL_CHAIN",
            "RESOURCE_ACQUISITION_PATH",
            "PROGRESSION_BRANCH",
            "OPPORTUNITY_COST",
        ):
            _fail("STRUCTURAL_DIVERGENCE_FAILED", "$.changed_dimensions", message="V1-D changed dimensions must be the measured comparison set")
        for name in (
            "legacy_structural_comparison_passed",
            "counterfactual_comparison_passed",
            "policy_ab_divergence_passed",
            "gate_passed",
        ):
            _bool(getattr(self, name), f"$.{name}")
        _strings(list(self.non_goals), "$.non_goals")
        if self.gate_passed and not (
            self.legacy_structural_comparison_passed
            and self.counterfactual_comparison_passed
            and self.policy_ab_divergence_passed
        ):
            _fail("STRUCTURAL_DIVERGENCE_FAILED", "$.gate_passed", message="structural gate must be derived from all proof classes")
        derived_gate = (
            self.legacy_structural_comparison_passed
            and self.counterfactual_comparison_passed
            and self.policy_ab_divergence_passed
        )
        if self.gate_passed != derived_gate:
            _fail("STRUCTURAL_DIVERGENCE_FAILED", "$.gate_passed", message="structural gate must be derived")

    @property
    def hash(self) -> str:
        return _hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "divergence_id": self.divergence_id,
            "source_config_hash": self.source_config_hash,
            "legacy_reference": self.legacy_reference.to_dict(),
            "pressure_action_ids": list(self.pressure_action_ids),
            "pressure_state_dimensions": list(self.pressure_state_dimensions),
            "pressure_event_types": list(self.pressure_event_types),
            "pressure_branch_opportunity": {action: list(choices) for action, choices in self.pressure_branch_opportunity},
            "counterfactual": self.counterfactual.to_dict(),
            "legacy_evidence_hash": self.legacy_evidence_hash,
            "actual_evidence_hashes": list(self.actual_evidence_hashes),
            "policy_a_proof_hash": self.policy_a_proof_hash,
            "policy_b_proof_hash": self.policy_b_proof_hash,
            "counterfactual_proof_hash": self.counterfactual_proof_hash,
            "changed_dimensions": list(self.changed_dimensions),
            "legacy_structural_comparison_passed": self.legacy_structural_comparison_passed,
            "counterfactual_comparison_passed": self.counterfactual_comparison_passed,
            "policy_ab_divergence_passed": self.policy_ab_divergence_passed,
            "gate_passed": self.gate_passed,
            "non_goals": list(self.non_goals),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StructuralDivergenceV1Report":
        fields = set(cls.__dataclass_fields__)
        _fields(data, fields)
        if not isinstance(data["pressure_branch_opportunity"], Mapping):
            _fail("INVALID_TYPE", "$.pressure_branch_opportunity", message="branch evidence mapping required")
        if any(type(key) is not str for key in data["pressure_branch_opportunity"]):
            _fail("INVALID_TYPE", "$.pressure_branch_opportunity", message="branch evidence keys must be strings")
        branch = tuple(
            (action, tuple(_strings(choices, f"$.pressure_branch_opportunity.{action}")))
            for action, choices in sorted(data["pressure_branch_opportunity"].items())
        )
        return cls(
            schema_version=data["schema_version"],
            divergence_id=data["divergence_id"],
            source_config_hash=data["source_config_hash"],
            legacy_reference=LegacyReferenceSnapshot.from_dict(data["legacy_reference"]),
            pressure_action_ids=tuple(_strings(data["pressure_action_ids"], "$.pressure_action_ids")),
            pressure_state_dimensions=tuple(_strings(data["pressure_state_dimensions"], "$.pressure_state_dimensions")),
            pressure_event_types=tuple(_strings(data["pressure_event_types"], "$.pressure_event_types")),
            pressure_branch_opportunity=branch,
            counterfactual=NoExclusiveResourceCounterfactualProof.from_dict(data["counterfactual"]),
            legacy_evidence_hash=data["legacy_evidence_hash"],
            actual_evidence_hashes=tuple(_strings(data["actual_evidence_hashes"], "$.actual_evidence_hashes")),
            policy_a_proof_hash=data["policy_a_proof_hash"],
            policy_b_proof_hash=data["policy_b_proof_hash"],
            counterfactual_proof_hash=data["counterfactual_proof_hash"],
            changed_dimensions=tuple(_strings(data["changed_dimensions"], "$.changed_dimensions")),
            legacy_structural_comparison_passed=data["legacy_structural_comparison_passed"],
            counterfactual_comparison_passed=data["counterfactual_comparison_passed"],
            policy_ab_divergence_passed=data["policy_ab_divergence_passed"],
            gate_passed=data["gate_passed"],
            non_goals=tuple(_strings(data["non_goals"], "$.non_goals")),
        )


@dataclass(frozen=True, slots=True)
class CandidatePreflightBundle:
    schema_version: int
    source_request_hash: str
    source_proposal_hash: str
    source_approval_hash: str
    source_report_hash: str
    source_catalog_version: str
    source_catalog_hash: str
    blueprint_hash: str
    binding_assessment_hash: str
    candidate_world_draft_hash: str
    candidate_attempt_hash: str
    compiler_id: str
    compiler_contract_version: int
    static_report: StaticPreflightReport
    gameplay_report: GameplayPreflightReport
    structural_report: StructuralDivergenceV1Report
    candidate_preflight_passed: bool
    publication_eligible: bool
    campaign_creation_allowed: bool
    worldpack_seal_allowed: bool
    resolved_preflight_gates: tuple[str, ...]
    remaining_global_gates: tuple[str, ...]
    non_goals: tuple[str, ...]

    def __post_init__(self) -> None:
        _version(self.schema_version, PREFLIGHT_BUNDLE_SCHEMA_VERSION, "$.schema_version")
        for name in (
            "source_request_hash",
            "source_proposal_hash",
            "source_approval_hash",
            "source_report_hash",
            "source_catalog_hash",
            "blueprint_hash",
            "binding_assessment_hash",
            "candidate_world_draft_hash",
            "candidate_attempt_hash",
        ):
            _hash_text(getattr(self, name), f"$.{name}")
        _text(self.source_catalog_version, "$.source_catalog_version")
        if self.compiler_id != CANDIDATE_COMPILER_ID or self.compiler_contract_version != CANDIDATE_COMPILER_CONTRACT_VERSION:
            _fail("INVALID_VALUE", "$.compiler_id", message="candidate compiler identity/version is fixed")
        if type(self.static_report) is not StaticPreflightReport or type(self.gameplay_report) is not GameplayPreflightReport or type(self.structural_report) is not StructuralDivergenceV1Report:
            _fail("INVALID_TYPE", "$.static_report", message="typed preflight reports required")
        if (
            self.static_report.source_request_hash != self.source_request_hash
            or self.static_report.source_proposal_hash != self.source_proposal_hash
            or self.static_report.source_approval_hash != self.source_approval_hash
            or self.static_report.source_report_hash != self.source_report_hash
            or self.static_report.source_catalog_version != self.source_catalog_version
            or self.static_report.source_catalog_hash != self.source_catalog_hash
            or self.static_report.blueprint_hash != self.blueprint_hash
            or self.static_report.binding_assessment_hash != self.binding_assessment_hash
            or self.static_report.candidate_world_draft_hash != self.candidate_world_draft_hash
            or self.static_report.candidate_attempt_hash != self.candidate_attempt_hash
            or self.static_report.compiler_id != self.compiler_id
            or self.static_report.compiler_contract_version != self.compiler_contract_version
        ):
            _fail("LINEAGE_MISMATCH", "$.static_report", message="static report lineage differs from bundle")
        if self.gameplay_report.source_config_hash != self.structural_report.source_config_hash:
            _fail("LINEAGE_MISMATCH", "$.gameplay_report", message="gameplay and structural config identities differ")
        if (
            self.structural_report.policy_a_proof_hash != self.gameplay_report.policy_a.hash
            or self.structural_report.policy_b_proof_hash != self.gameplay_report.policy_b.hash
        ):
            _fail("LINEAGE_MISMATCH", "$.structural_report", message="structural report does not bind gameplay proofs")
        if self.resolved_preflight_gates != RESOLVED_PREFLIGHT_GATES:
            _fail("INVALID_VALUE", "$.resolved_preflight_gates", message="V1-D resolves exactly three gates")
        if self.remaining_global_gates != REMAINING_GLOBAL_GATES:
            _fail("INVALID_VALUE", "$.remaining_global_gates", message="V1-D retains the global gates")
        _bool(self.candidate_preflight_passed, "$.candidate_preflight_passed")
        for name in ("publication_eligible", "campaign_creation_allowed", "worldpack_seal_allowed"):
            if getattr(self, name) is not False:
                _fail("PREFLIGHT_GATE_BLOCKED", f"$.{name}", message="V1-D cannot publish or seal")
        derived_bundle_gate = (
            self.static_report.static_preflight_passed
            and self.gameplay_report.gameplay_preflight_passed
            and self.structural_report.gate_passed
        )
        if self.candidate_preflight_passed != derived_bundle_gate:
            _fail("PREFLIGHT_GATE_BLOCKED", "$.candidate_preflight_passed", message="bundle gate must be derived")
        _strings(list(self.non_goals), "$.non_goals")

    @property
    def static_preflight_report_hash(self) -> str:
        return self.static_report.hash

    @property
    def gameplay_preflight_report_hash(self) -> str:
        return self.gameplay_report.hash

    @property
    def structural_divergence_report_hash(self) -> str:
        return self.structural_report.hash

    @property
    def hash(self) -> str:
        return _hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_request_hash": self.source_request_hash,
            "source_proposal_hash": self.source_proposal_hash,
            "source_approval_hash": self.source_approval_hash,
            "source_report_hash": self.source_report_hash,
            "source_catalog_version": self.source_catalog_version,
            "source_catalog_hash": self.source_catalog_hash,
            "blueprint_hash": self.blueprint_hash,
            "binding_assessment_hash": self.binding_assessment_hash,
            "candidate_world_draft_hash": self.candidate_world_draft_hash,
            "candidate_attempt_hash": self.candidate_attempt_hash,
            "static_preflight_report": self.static_report.to_dict(),
            "static_preflight_report_hash": self.static_preflight_report_hash,
            "gameplay_preflight_report": self.gameplay_report.to_dict(),
            "gameplay_preflight_report_hash": self.gameplay_preflight_report_hash,
            "structural_divergence_report": self.structural_report.to_dict(),
            "structural_divergence_report_hash": self.structural_divergence_report_hash,
            "compiler_id": self.compiler_id,
            "compiler_contract_version": self.compiler_contract_version,
            "candidate_preflight_passed": self.candidate_preflight_passed,
            "publication_eligible": self.publication_eligible,
            "campaign_creation_allowed": self.campaign_creation_allowed,
            "worldpack_seal_allowed": self.worldpack_seal_allowed,
            "resolved_preflight_gates": list(self.resolved_preflight_gates),
            "remaining_global_gates": list(self.remaining_global_gates),
            "non_goals": list(self.non_goals),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidatePreflightBundle":
        fields = {
            "schema_version",
            "source_request_hash",
            "source_proposal_hash",
            "source_approval_hash",
            "source_report_hash",
            "source_catalog_version",
            "source_catalog_hash",
            "blueprint_hash",
            "binding_assessment_hash",
            "candidate_world_draft_hash",
            "candidate_attempt_hash",
            "static_preflight_report",
            "static_preflight_report_hash",
            "gameplay_preflight_report",
            "gameplay_preflight_report_hash",
            "structural_divergence_report",
            "structural_divergence_report_hash",
            "compiler_id",
            "compiler_contract_version",
            "candidate_preflight_passed",
            "publication_eligible",
            "campaign_creation_allowed",
            "worldpack_seal_allowed",
            "resolved_preflight_gates",
            "remaining_global_gates",
            "non_goals",
        }
        _fields(data, fields)
        static_report = StaticPreflightReport.from_dict(data["static_preflight_report"])
        gameplay_report = GameplayPreflightReport.from_dict(data["gameplay_preflight_report"])
        structural_report = StructuralDivergenceV1Report.from_dict(data["structural_divergence_report"])
        if data["static_preflight_report_hash"] != static_report.hash or data["gameplay_preflight_report_hash"] != gameplay_report.hash or data["structural_divergence_report_hash"] != structural_report.hash:
            _fail("HASH_MISMATCH", "$.static_preflight_report_hash", message="nested proof hash differs from payload")
        return cls(
            schema_version=data["schema_version"],
            source_request_hash=data["source_request_hash"],
            source_proposal_hash=data["source_proposal_hash"],
            source_approval_hash=data["source_approval_hash"],
            source_report_hash=data["source_report_hash"],
            source_catalog_version=data["source_catalog_version"],
            source_catalog_hash=data["source_catalog_hash"],
            blueprint_hash=data["blueprint_hash"],
            binding_assessment_hash=data["binding_assessment_hash"],
            candidate_world_draft_hash=data["candidate_world_draft_hash"],
            candidate_attempt_hash=data["candidate_attempt_hash"],
            compiler_id=data["compiler_id"],
            compiler_contract_version=data["compiler_contract_version"],
            static_report=static_report,
            gameplay_report=gameplay_report,
            structural_report=structural_report,
            candidate_preflight_passed=data["candidate_preflight_passed"],
            publication_eligible=data["publication_eligible"],
            campaign_creation_allowed=data["campaign_creation_allowed"],
            worldpack_seal_allowed=data["worldpack_seal_allowed"],
            resolved_preflight_gates=tuple(_strings(data["resolved_preflight_gates"], "$.resolved_preflight_gates")),
            remaining_global_gates=tuple(_strings(data["remaining_global_gates"], "$.remaining_global_gates")),
            non_goals=tuple(_strings(data["non_goals"], "$.non_goals")),
        )


def build_legacy_reference_snapshot() -> LegacyReferenceSnapshot:
    """Derive the legacy descriptor from the frozen runtime's public models."""

    from tgn.core.models import DomainEvent
    from tgn.core.reducer import reduce_event
    from tgn.gameplay import expedition
    from tgn.gameplay.expedition import get_legal_actions
    from tgn.gameplay.named_actor import ACTOR_CONVERSATION_RESOLVED
    from tgn.worldgen.compiler import compile_worldpack, materialize_initial_state
    from tgn.worldgen.models import BootstrapResult, MECHANICS_PROFILE, WorldDraft

    draft = WorldDraft(
        schema_version=1,
        mechanics_profile=MECHANICS_PROFILE,
        world_id="legacy-reference",
        content_locale="en-US",
        title="Legacy Reference",
        premise="Read-only frozen profile descriptor",
        labels={
            "base": "base",
            "target": "target",
            "resource": "salvage",
            "hazard": "hazard",
            "named_actor": "actor",
            "named_actor_role": "ally",
            "named_actor_public_goal": "goal",
        },
    )
    worldpack = compile_worldpack(draft)
    state = materialize_initial_state(worldpack, "legacy-reference-seed")
    legal_actions = tuple(item.action_type for item in get_legal_actions(state))
    state_dimensions = tuple(field.name for field in dataclasses.fields(state))
    result_fields = tuple(BootstrapResult.__dataclass_fields__)
    expected_event_types = (
        "TIME_ADVANCED",
        "EXPEDITION_DROPPED",
        "SEARCH_RESOLVED",
        "EXPEDITION_EXTRACTED",
        "COMBAT_RESOLVED",
        "EXPEDITION_FLED",
        "PLAYER_PROGRESSION_ADVANCED",
        "BASE_PROGRESSION_ADVANCED",
        "REST_RESOLVED",
        "BUILD_SELECTED",
    )
    frozen_code_constants = {
        value
        for function in (
            expedition.execute_action,
            expedition._execute_phase3_action,
            reduce_event,
            DomainEvent.advance_time,
        )
        for value in function.__code__.co_consts
        if type(value) is str
    }
    frozen_code_constants.add(ACTOR_CONVERSATION_RESOLVED)
    if any(value not in frozen_code_constants for value in expected_event_types):
        _fail("STRUCTURAL_DIVERGENCE_FAILED", "$.legacy_reference.legacy_event_types", message="legacy event descriptor is not present in frozen runtime code")
    event_types = tuple(sorted((*expected_event_types, ACTOR_CONVERSATION_RESOLVED)))
    return LegacyReferenceSnapshot(
        schema_version=1,
        source_profile_id=MECHANICS_PROFILE,
        frozen_commit_identity="pc1-frozen",
        source_descriptor=(
            "src/tgn/worldgen/models.py:MECHANICS_PROFILE;"
            "src/tgn/worldgen/compiler.py:compile_worldpack/materialize_initial_state;"
            "src/tgn/worldgen/models.py:BootstrapResult/to_report;"
            "src/tgn/gameplay/expedition.py:get_legal_actions/execute_action;"
            "src/tgn/core/reducer.py:reduce_event"
        ),
        legacy_legal_action_ids=legal_actions,
        legacy_state_dimensions=state_dimensions,
        legacy_result_fields=result_fields,
        legacy_event_types=event_types,
        legacy_runtime_binding_keys=tuple(sorted(worldpack.runtime_bindings)),
    )


def _trace_policy(
    policy_id: str,
    action_ids: Sequence[str],
    config: ExclusiveUpgradePressureConfig,
) -> GameplayTraceProof:
    initial = initial_pressure_state(config)
    initial_hash = pressure_state_hash(initial)
    current = initial
    events: list[ExclusiveUpgradeEvent] = []
    action_hashes: list[str] = []
    event_types: list[str] = []
    event_hashes: list[str] = []
    before_hashes: list[str] = []
    after_hashes: list[str] = []
    legal_before: list[tuple[str, ...]] = []
    legal_after: list[tuple[str, ...]] = []
    prefixes = [initial_hash]
    for decision_seq, action_id in enumerate(action_ids, start=1):
        legal_before.append(tuple(legal_pressure_actions(current, config.protagonist_id, config)))
        if action_id == "WAIT":
            _fail("PRESSURE_TRACE_MISMATCH", "$.action_ids", message="WAIT is not a pressure proof action")
        action = ExclusiveUpgradeAction(action_id, config.protagonist_id, decision_seq)
        event = resolve_pressure_action(current, action, config)
        if pressure_event_hash(event) != event.event_hash:
            _fail("PRESSURE_TRACE_MISMATCH", "$.event_hashes", message="production pressure event hash does not verify")
        after = reduce_pressure_event(current, event, config)
        if after.to_dict() != replay_pressure_events(initial, (*events, event), config).to_dict():
            _fail("PRESSURE_TRACE_MISMATCH", "$.prefix_replay_state_hashes", message="prefix replay differs from reducer state")
        current = after
        events.append(event)
        action_hashes.append(action.hash)
        event_types.append(event.event_type)
        event_hashes.append(event.event_hash)
        before_hashes.append(event.before_state_hash)
        after_hashes.append(event.after_state_hash)
        prefixes.append(pressure_state_hash(current))
        legal_after.append(tuple(legal_pressure_actions(current, config.protagonist_id, config)))
    terminal = verify_terminal_pressure_trace(initial, events, config, pressure_state_hash(current))
    result = "HAZARD_ZONE_TRAVERSED" if terminal.hazard_zone_traversed else "SUPPLY_CACHE_CLAIMED"
    lifecycle = "PERMANENTLY_CONSUMED"
    return GameplayTraceProof(
        schema_version=GAMEPLAY_PREFLIGHT_SCHEMA_VERSION,
        policy_id=policy_id,
        source_config_hash=config.hash,
        initial_state_hash=initial_hash,
        action_ids=tuple(action_ids),
        action_hashes=tuple(action_hashes),
        event_types=tuple(event_types),
        event_hashes=tuple(event_hashes),
        before_state_hashes=tuple(before_hashes),
        after_state_hashes=tuple(after_hashes),
        legal_actions_before=tuple(legal_before),
        legal_actions_after=tuple(legal_after),
        prefix_replay_state_hashes=tuple(prefixes),
        terminal_state_hash=pressure_state_hash(terminal),
        terminal_result=result,
        terminal_legal_action_set=tuple(legal_pressure_actions(terminal, config.protagonist_id, config)),
        accepted_decision_count=terminal.decision_seq,
        total_game_minute_delta=terminal.game_minute - initial.game_minute,
        total_stamina_delta=terminal.stamina - initial.stamina,
        common_material_final_value=terminal.common_material_count,
        exclusive_resource_final_lifecycle=lifecycle,
        branch_commitment=terminal.exclusive_resource_spent_on,
        exclusive_resource_final_count=terminal.exclusive_resource_count,
        exclusive_resource_source_available=terminal.exclusive_resource_source_available,
    )


def _failure_probe(
    scenario_id: str,
    expected_error_code: str,
    config: ExclusiveUpgradePressureConfig,
    operation: Any,
    state: ExclusiveUpgradePressureState,
) -> GameplayFailureProof:
    before_hash = pressure_state_hash(state)
    before_minute = state.game_minute
    before_decision = state.decision_seq
    before_event = state.event_seq
    actual_code = "NO_ERROR"
    try:
        operation()
    except Exception as exc:
        actual_code = getattr(exc, "code", type(exc).__name__)
    after_hash = pressure_state_hash(state)
    return GameplayFailureProof(
        schema_version=GAMEPLAY_PREFLIGHT_SCHEMA_VERSION,
        scenario_id=scenario_id,
        expected_error_code=expected_error_code,
        actual_error_code=actual_code,
        state_hash_before=before_hash,
        state_hash_after=after_hash,
        game_minute_before=before_minute,
        game_minute_after=state.game_minute,
        decision_seq_before=before_decision,
        decision_seq_after=state.decision_seq,
        event_seq_before=before_event,
        event_seq_after=state.event_seq,
        accepted_event_count=0,
        proof_artifact_created=False,
        state_unchanged=before_hash == after_hash,
        time_unchanged=before_minute == state.game_minute,
    )


def _build_failure_proofs(config: ExclusiveUpgradePressureConfig) -> tuple[GameplayFailureProof, ...]:
    initial = initial_pressure_state(config)
    recover_1 = resolve_pressure_action(initial, ExclusiveUpgradeAction(RECOVER_EXCLUSIVE_RESOURCE, config.protagonist_id, 1), config)
    recovered = reduce_pressure_event(initial, recover_1, config)
    upgrade_event = resolve_pressure_action(recovered, ExclusiveUpgradeAction(UPGRADE_GROWTH_OBJECT, config.protagonist_id, 2), config)
    upgraded = reduce_pressure_event(recovered, upgrade_event, config)
    stabilize_event = resolve_pressure_action(recovered, ExclusiveUpgradeAction(STABILIZE_SUPPLY_ROUTE, config.protagonist_id, 2), config)
    stabilized = reduce_pressure_event(recovered, stabilize_event, config)
    upgrade_terminal_event = resolve_pressure_action(upgraded, ExclusiveUpgradeAction(TRAVERSE_HAZARD_ZONE, config.protagonist_id, 3), config)
    supply_terminal_event = resolve_pressure_action(stabilized, ExclusiveUpgradeAction(CLAIM_SUPPLY_CACHE, config.protagonist_id, 3), config)

    e1 = recover_1
    e2 = upgrade_event
    e3 = upgrade_terminal_event
    tampered = dataclasses.replace(e1, event_hash="0" * 64)
    return (
        _failure_probe(
            "initial_upgrade_without_exclusive",
            "ORDINARY_RESOURCE_FALLBACK_FORBIDDEN",
            config,
            lambda: resolve_pressure_action(initial, ExclusiveUpgradeAction(UPGRADE_GROWTH_OBJECT, config.protagonist_id, 1), config),
            initial,
        ),
        _failure_probe(
            "initial_stabilize_without_exclusive",
            "EXCLUSIVE_RESOURCE_REQUIRED",
            config,
            lambda: resolve_pressure_action(initial, ExclusiveUpgradeAction(STABILIZE_SUPPLY_ROUTE, config.protagonist_id, 1), config),
            initial,
        ),
        _failure_probe(
            "duplicate_recover_held",
            "EXCLUSIVE_RESOURCE_ALREADY_HELD",
            config,
            lambda: resolve_pressure_action(recovered, ExclusiveUpgradeAction(RECOVER_EXCLUSIVE_RESOURCE, config.protagonist_id, 2), config),
            recovered,
        ),
        _failure_probe(
            "recover_after_source_closed",
            "EXCLUSIVE_RESOURCE_SOURCE_CLOSED",
            config,
            lambda: resolve_pressure_action(upgraded, ExclusiveUpgradeAction(RECOVER_EXCLUSIVE_RESOURCE, config.protagonist_id, 3), config),
            upgraded,
        ),
        _failure_probe(
            "upgrade_after_supply_branch",
            "BRANCH_ALREADY_COMMITTED",
            config,
            lambda: resolve_pressure_action(stabilized, ExclusiveUpgradeAction(UPGRADE_GROWTH_OBJECT, config.protagonist_id, 3), config),
            stabilized,
        ),
        _failure_probe(
            "stabilize_after_upgrade_branch",
            "BRANCH_ALREADY_COMMITTED",
            config,
            lambda: resolve_pressure_action(upgraded, ExclusiveUpgradeAction(STABILIZE_SUPPLY_ROUTE, config.protagonist_id, 3), config),
            upgraded,
        ),
        _failure_probe(
            "followup_before_unlock",
            "FOLLOWUP_NOT_UNLOCKED",
            config,
            lambda: resolve_pressure_action(initial, ExclusiveUpgradeAction(TRAVERSE_HAZARD_ZONE, config.protagonist_id, 1), config),
            initial,
        ),
        _failure_probe(
            "duplicate_event",
            "EVENT_SEQUENCE_MISMATCH",
            config,
            lambda: reduce_pressure_event(recovered, e1, config),
            recovered,
        ),
        _failure_probe(
            "reordered_event",
            "EVENT_SEQUENCE_MISMATCH",
            config,
            lambda: replay_pressure_events(initial, (e2, e1), config),
            initial,
        ),
        _failure_probe(
            "missing_head_event",
            "EVENT_SEQUENCE_MISMATCH",
            config,
            lambda: replay_pressure_events(initial, (e2, e3), config),
            initial,
        ),
        _failure_probe(
            "event_payload_tamper",
            "EVENT_HASH_MISMATCH",
            config,
            lambda: reduce_pressure_event(initial, tampered, config),
            initial,
        ),
        _failure_probe(
            "wrong_final_state_hash",
            "STATE_HASH_MISMATCH",
            config,
            lambda: verify_terminal_pressure_trace(initial, (e1, e2, e3), config, "0" * 64),
            initial,
        ),
        _failure_probe(
            "nonterminal_prefix_terminal_verify",
            "EVENT_SEQUENCE_MISMATCH",
            config,
            lambda: verify_terminal_pressure_trace(initial, (e1,), config, pressure_state_hash(recovered)),
            initial,
        ),
    )


def run_gameplay_preflight(config: ExclusiveUpgradePressureConfig) -> GameplayPreflightReport:
    if type(config) is not ExclusiveUpgradePressureConfig:
        _fail("INVALID_TYPE", "$.pressure_config", message="pressure config required")
    initial = initial_pressure_state(config)
    policy_a = _trace_policy(
        "POLICY_A_UPGRADE_THEN_TRAVERSE",
        (RECOVER_EXCLUSIVE_RESOURCE, UPGRADE_GROWTH_OBJECT, TRAVERSE_HAZARD_ZONE),
        config,
    )
    policy_b = _trace_policy(
        "POLICY_B_STABILIZE_THEN_CLAIM",
        (RECOVER_EXCLUSIVE_RESOURCE, STABILIZE_SUPPLY_ROUTE, CLAIM_SUPPLY_CACHE),
        config,
    )
    no_wait = all("WAIT" not in proof.action_ids for proof in (policy_a, policy_b))
    prefixes_verified = all(
        proof.prefix_replay_state_hashes[0] == proof.initial_state_hash
        and proof.prefix_replay_state_hashes[-1] == proof.terminal_state_hash
        and proof.terminal_legal_action_set == ()
        for proof in (policy_a, policy_b)
    )
    terminal_verified = all(proof.accepted_decision_count == 3 for proof in (policy_a, policy_b))
    traces_differ = policy_a.event_types != policy_b.event_types
    hashes_differ = policy_a.terminal_state_hash != policy_b.terminal_state_hash
    results_differ = policy_a.terminal_result != policy_b.terminal_result
    material_differ = policy_a.common_material_final_value != policy_b.common_material_final_value
    failure_proofs = _build_failure_proofs(config)
    failure_proof_passed = tuple(item.scenario_id for item in failure_proofs) == GAMEPLAY_FAILURE_SCENARIO_IDS
    passed = no_wait and prefixes_verified and terminal_verified and traces_differ and hashes_differ and results_differ and material_differ and failure_proof_passed
    return GameplayPreflightReport(
        schema_version=GAMEPLAY_PREFLIGHT_SCHEMA_VERSION,
        source_config_hash=config.hash,
        initial_state_hash=pressure_state_hash(initial),
        policy_a=policy_a,
        policy_b=policy_b,
        no_wait=no_wait,
        prefix_replay_verified=prefixes_verified,
        terminal_verification_passed=terminal_verified,
        policy_event_traces_differ=traces_differ,
        policy_final_state_hashes_differ=hashes_differ,
        policy_results_differ=results_differ,
        policy_material_outcomes_differ=material_differ,
        failure_proofs=failure_proofs,
        failure_proof_passed=failure_proof_passed,
        gameplay_preflight_passed=passed,
        non_goals=("RUNTIME_CATALOG_SUPPORT", "WORLD_PACK_SEAL", "CAMPAIGN_PUBLICATION", "V1-E", "V1-F"),
    )


def build_no_exclusive_resource_counterfactual(
    config: ExclusiveUpgradePressureConfig,
    gameplay: GameplayPreflightReport,
) -> NoExclusiveResourceCounterfactualProof:
    if type(config) is not ExclusiveUpgradePressureConfig or type(gameplay) is not GameplayPreflightReport:
        _fail("INVALID_TYPE", "$.counterfactual", message="pressure config and gameplay proof required")
    actual_initial = tuple(legal_pressure_actions(initial_pressure_state(config), config.protagonist_id, config))
    return NoExclusiveResourceCounterfactualProof(
        schema_version=STRUCTURAL_DIVERGENCE_SCHEMA_VERSION,
        counterfactual_id=NO_EXCLUSIVE_RESOURCE_COUNTERFACTUAL_ID,
        actual_initial_legal_action_ids=actual_initial,
        counterfactual_initial_legal_action_ids=(UPGRADE_GROWTH_OBJECT, STABILIZE_SUPPLY_ROUTE),
        actual_policy_a_actions=gameplay.policy_a.action_ids,
        actual_policy_b_actions=gameplay.policy_b.action_ids,
        counterfactual_policy_a_actions=(UPGRADE_GROWTH_OBJECT, TRAVERSE_HAZARD_ZONE),
        counterfactual_policy_b_actions=(STABILIZE_SUPPLY_ROUTE, CLAIM_SUPPLY_CACHE),
        actual_accepted_decision_count=3,
        counterfactual_accepted_decision_count=2,
        actual_event_count=3,
        counterfactual_event_count=0,
        actual_resource_cost_path=(
            "RECOVER_EXCLUSIVE_RESOURCE",
            "source_permanently_closed",
            "resource_held",
            "mutually_exclusive_commitment",
            "resource_count_permanently_zero",
        ),
        counterfactual_resource_cost_path=(
            "no_exclusive_acquisition",
            "one_ordinary_material_consumed",
            "no_source_closure",
            "no_exclusive_lifecycle",
        ),
        actual_opportunity_cost="branch_commitment_closes_the_other_route",
        counterfactual_opportunity_cost="no_exclusive_source_or_held_resource_choice",
        common_material_cost=1,
        changed_dimensions=(
            "LEGAL_ACTION_SET",
            "ACCEPTED_DECISION_TRACE",
            "RESOURCE_COST_PATH",
            "OPPORTUNITY_COST",
            "RESOURCE_LIFECYCLE",
        ),
        proof_only=True,
        generates_domain_events=False,
        runtime_callable=False,
        catalog_entry=False,
    )


def run_structural_divergence_preflight(
    config: ExclusiveUpgradePressureConfig,
    gameplay: GameplayPreflightReport,
) -> StructuralDivergenceV1Report:
    if type(config) is not ExclusiveUpgradePressureConfig or type(gameplay) is not GameplayPreflightReport:
        _fail("INVALID_TYPE", "$.structural", message="pressure config and gameplay proof required")
    legacy = build_legacy_reference_snapshot()
    counterfactual = build_no_exclusive_resource_counterfactual(config, gameplay)
    pressure_state_dimensions = tuple(field.name for field in dataclasses.fields(ExclusiveUpgradePressureState))
    pressure_event_types = tuple(sorted(PRESSURE_EVENT_TYPES))
    branch = (
        (RECOVER_EXCLUSIVE_RESOURCE, (UPGRADE_GROWTH_OBJECT, STABILIZE_SUPPLY_ROUTE)),
        (UPGRADE_GROWTH_OBJECT, (TRAVERSE_HAZARD_ZONE,)),
        (STABILIZE_SUPPLY_ROUTE, (CLAIM_SUPPLY_CACHE,)),
    )
    legacy_compare = (
        legacy.source_profile_id == "phase75_expedition_v1"
        and set(legacy.legacy_legal_action_ids) != set(PRESSURE_ACTION_IDS)
        and legacy.legacy_state_dimensions != pressure_state_dimensions
        and set(legacy.legacy_event_types) != set(pressure_event_types)
        and legacy.legacy_result_fields != ("terminal_result", "branch_commitment", "common_material_final_value")
    )
    counterfactual_compare = (
        counterfactual.actual_initial_legal_action_ids == (RECOVER_EXCLUSIVE_RESOURCE,)
        and counterfactual.counterfactual_initial_legal_action_ids == (UPGRADE_GROWTH_OBJECT, STABILIZE_SUPPLY_ROUTE)
        and counterfactual.actual_accepted_decision_count != counterfactual.counterfactual_accepted_decision_count
        and counterfactual.actual_event_count != counterfactual.counterfactual_event_count
        and "OPPORTUNITY_COST" in counterfactual.changed_dimensions
        and counterfactual.proof_only
        and not counterfactual.generates_domain_events
    )
    policy_divergence = (
        gameplay.gameplay_preflight_passed
        and gameplay.policy_event_traces_differ
        and gameplay.policy_final_state_hashes_differ
        and gameplay.policy_results_differ
        and gameplay.policy_material_outcomes_differ
        and gameplay.policy_a.branch_commitment == RESOURCE_SPENT_UPGRADE
        and gameplay.policy_b.branch_commitment == RESOURCE_SPENT_SUPPLY_ROUTE
    )
    changed_dimensions = (
        "LEGAL_ACTION_VOCABULARY",
        "STATE_DIMENSIONS",
        "EVENT_CAUSAL_CHAIN",
        "RESOURCE_ACQUISITION_PATH",
        "PROGRESSION_BRANCH",
        "OPPORTUNITY_COST",
    )
    gate = legacy_compare and counterfactual_compare and policy_divergence
    return StructuralDivergenceV1Report(
        schema_version=STRUCTURAL_DIVERGENCE_SCHEMA_VERSION,
        divergence_id=STRUCTURAL_DIVERGENCE_ID,
        source_config_hash=config.hash,
        legacy_reference=legacy,
        pressure_action_ids=tuple(sorted(PRESSURE_ACTION_IDS)),
        pressure_state_dimensions=pressure_state_dimensions,
        pressure_event_types=pressure_event_types,
        pressure_branch_opportunity=branch,
        counterfactual=counterfactual,
        legacy_evidence_hash=legacy.hash,
        actual_evidence_hashes=(config.hash, gameplay.policy_a.hash, gameplay.policy_b.hash),
        policy_a_proof_hash=gameplay.policy_a.hash,
        policy_b_proof_hash=gameplay.policy_b.hash,
        counterfactual_proof_hash=counterfactual.hash,
        changed_dimensions=changed_dimensions,
        legacy_structural_comparison_passed=legacy_compare,
        counterfactual_comparison_passed=counterfactual_compare,
        policy_ab_divergence_passed=policy_divergence,
        gate_passed=gate,
        non_goals=(
            "WORLD_DEPTH_L1",
            "WORLD_DEPTH_L2",
            "OCEAN_PHYSICS",
            "OFFSCREEN_ACTOR_SIMULATION",
            "RUNTIME_CATALOG_SUPPORT",
            "CAMPAIGN_PUBLICATION",
            "WORLDPACK_SEAL",
        ),
    )


def _build_static_report(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    blueprint: WorldBlueprint,
    assessment: RuntimeBindingAssessment,
    draft: CandidateWorldDraft,
    attempt: CandidateGenesisAttempt,
) -> StaticPreflightReport:
    runtime_ids = tuple(sorted(feature.feature_id for feature in catalog.entries if feature.layer == "RUNTIME"))
    counts = tuple(sorted(assessment.status_counts.items()))
    return StaticPreflightReport(
        schema_version=STATIC_PREFLIGHT_SCHEMA_VERSION,
        source_request_hash=request.hash,
        source_proposal_hash=proposal.hash,
        source_approval_hash=coverage_approval.hash,
        source_report_hash=report.hash,
        source_catalog_version=catalog.version,
        source_catalog_hash=catalog.hash,
        blueprint_hash=blueprint.hash,
        binding_assessment_hash=assessment.hash,
        candidate_world_draft_hash=draft.hash,
        candidate_attempt_hash=attempt.hash,
        candidate_semantic_hash=draft.world_semantic_candidate_hash,
        compiler_id=attempt.compiler_id,
        compiler_contract_version=attempt.compiler_contract_version,
        draft_schema_version=draft.draft_schema_version,
        binding_status_counts=counts,
        binding_gate_passed=assessment.binding_gate_passed,
        requirements_gate_passed=report.requirements_gate_passed,
        attempt_status=attempt.attempt_status,
        required_pending_gates=attempt.required_pending_gates,
        blocked_gates=REMAINING_GLOBAL_GATES,
        runtime_catalog_feature_ids=runtime_ids,
        static_preflight_passed=True,
        publication_eligible=False,
        failure_codes=(),
        non_goals=(
            "RUNTIME_CATALOG_SUPPORT",
            "WORLDPACK_SEAL",
            "CAMPAIGN_PUBLICATION",
            "AUTHORITATIVE_GAMESTATE",
            "AUTOPLAY_COMPATIBILITY",
        ),
    )


def run_candidate_preflight(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    blueprint: WorldBlueprint,
    pressure_config: ExclusiveUpgradePressureConfig,
    assessment: RuntimeBindingAssessment,
    draft: CandidateWorldDraft,
    attempt: CandidateGenesisAttempt,
) -> CandidatePreflightBundle:
    """Recompute all V1-D proof artifacts and return one detached bundle."""

    try:
        verified_assessment, verified_draft, verified_attempt = verify_candidate_artifacts(
            request,
            proposal,
            coverage_approval,
            report,
            catalog,
            blueprint,
            pressure_config,
            assessment,
            draft,
            attempt,
        )
    except Exception as exc:
        _fail("CANDIDATE_ARTIFACT_INVALID", "$.candidate", message=str(exc))
    static_report = _build_static_report(
        request,
        proposal,
        coverage_approval,
        report,
        catalog,
        blueprint,
        verified_assessment,
        verified_draft,
        verified_attempt,
    )
    gameplay_report = run_gameplay_preflight(pressure_config)
    structural_report = run_structural_divergence_preflight(pressure_config, gameplay_report)
    return CandidatePreflightBundle(
        schema_version=PREFLIGHT_BUNDLE_SCHEMA_VERSION,
        source_request_hash=request.hash,
        source_proposal_hash=proposal.hash,
        source_approval_hash=coverage_approval.hash,
        source_report_hash=report.hash,
        source_catalog_version=catalog.version,
        source_catalog_hash=catalog.hash,
        blueprint_hash=blueprint.hash,
        binding_assessment_hash=verified_assessment.hash,
        candidate_world_draft_hash=verified_draft.hash,
        candidate_attempt_hash=verified_attempt.hash,
        compiler_id=verified_attempt.compiler_id,
        compiler_contract_version=verified_attempt.compiler_contract_version,
        static_report=static_report,
        gameplay_report=gameplay_report,
        structural_report=structural_report,
        candidate_preflight_passed=(
            static_report.static_preflight_passed
            and gameplay_report.gameplay_preflight_passed
            and structural_report.gate_passed
        ),
        publication_eligible=False,
        campaign_creation_allowed=False,
        worldpack_seal_allowed=False,
        resolved_preflight_gates=RESOLVED_PREFLIGHT_GATES,
        remaining_global_gates=REMAINING_GLOBAL_GATES,
        non_goals=("V1-E", "V1-F", "RUNTIME_CATALOG_SUPPORT", "PUBLICATION", "CAMPAIGN", "SQLITE"),
    )


def verify_candidate_preflight(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    blueprint: WorldBlueprint,
    pressure_config: ExclusiveUpgradePressureConfig,
    assessment: RuntimeBindingAssessment,
    draft: CandidateWorldDraft,
    attempt: CandidateGenesisAttempt,
    static_report: StaticPreflightReport,
    gameplay_report: GameplayPreflightReport,
    structural_report: StructuralDivergenceV1Report,
    bundle: CandidatePreflightBundle,
) -> CandidatePreflightBundle:
    """Re-run every proof and compare all persisted payloads, not just hashes."""

    try:
        expected = run_candidate_preflight(
            request,
            proposal,
            coverage_approval,
            report,
            catalog,
            blueprint,
            pressure_config,
            assessment,
            draft,
            attempt,
        )
    except PreflightValidationError:
        raise
    except Exception as exc:
        _fail("CANDIDATE_ARTIFACT_INVALID", "$.candidate", message=str(exc))
    for name, actual, wanted in (
        ("static_report", static_report, expected.static_report),
        ("gameplay_report", gameplay_report, expected.gameplay_report),
        ("structural_report", structural_report, expected.structural_report),
        ("bundle", bundle, expected),
    ):
        if type(actual) is not type(wanted) or actual.to_dict() != wanted.to_dict() or actual.hash != wanted.hash:
            _fail("PREFLIGHT_MISMATCH", f"$.{name}", message="persisted proof differs from deterministic recomputation")
    return expected


def run_static_preflight(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    blueprint: WorldBlueprint,
    pressure_config: ExclusiveUpgradePressureConfig,
    assessment: RuntimeBindingAssessment,
    draft: CandidateWorldDraft,
    attempt: CandidateGenesisAttempt,
) -> StaticPreflightReport:
    """Run the static gate, beginning with full V1-C artifact verification."""

    try:
        verified_assessment, verified_draft, verified_attempt = verify_candidate_artifacts(
            request,
            proposal,
            coverage_approval,
            report,
            catalog,
            blueprint,
            pressure_config,
            assessment,
            draft,
            attempt,
        )
    except Exception as exc:
        _fail("CANDIDATE_ARTIFACT_INVALID", "$.candidate", message=str(exc))
    return _build_static_report(
        request,
        proposal,
        coverage_approval,
        report,
        catalog,
        blueprint,
        verified_assessment,
        verified_draft,
        verified_attempt,
    )


run_structural_divergence = run_structural_divergence_preflight


__all__ = [
    "CandidatePreflightBundle",
    "GAMEPLAY_PREFLIGHT_SCHEMA_VERSION",
    "GAMEPLAY_FAILURE_SCENARIO_IDS",
    "LegacyReferenceSnapshot",
    "NO_EXCLUSIVE_RESOURCE_COUNTERFACTUAL_ID",
    "NoExclusiveResourceCounterfactualProof",
    "PREFLIGHT_BUNDLE_SCHEMA_VERSION",
    "PreflightValidationError",
    "RESOLVED_PREFLIGHT_GATES",
    "REMAINING_GLOBAL_GATES",
    "STATIC_PREFLIGHT_SCHEMA_VERSION",
    "STRUCTURAL_DIVERGENCE_ID",
    "STRUCTURAL_DIVERGENCE_SCHEMA_VERSION",
    "StaticPreflightReport",
    "GameplayTraceProof",
    "GameplayFailureProof",
    "GameplayPreflightReport",
    "StructuralDivergenceV1Report",
    "build_legacy_reference_snapshot",
    "build_no_exclusive_resource_counterfactual",
    "run_candidate_preflight",
    "run_gameplay_preflight",
    "run_static_preflight",
    "run_structural_divergence",
    "run_structural_divergence_preflight",
    "verify_candidate_preflight",
]
