"""Blocked candidate artifacts and pure compiler seam for bounded Genesis V1-C.2."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping, Sequence

from .binding import (
    BINDING_SCHEMA_VERSION,
    BindingValidationError,
    RuntimeBindingAssessment,
    build_runtime_binding_assessment,
    verify_runtime_binding_assessment,
)
from .blueprint import (
    ArtifactValidationError,
    BlueprintValidationError,
    CANDIDATE_DURABLE,
    WorldBlueprint,
    _canonical_payload,
    _check_exact_fields,
    _fail,
    _hash_payload,
    _validate_hash,
    _validate_id,
    _validate_text,
    validate_blueprint_lineage,
)
from .catalog import FeatureSupportCatalog
from .evaluator import verify_report
from .foundation import (
    FoundationCandidateComponent,
    build_foundation_candidate,
    verify_foundation_candidate,
)
from .models import (
    FeatureRequirementReport,
    GenesisRequest,
    GenesisValidationError,
    RequirementCoverageApproval,
    RequirementProposal,
)
from .pressure import (
    ExclusiveUpgradePressureConfig,
    ExclusiveUpgradePressureState,
    PRESSURE_CONTRACT_VERSION,
    PRESSURE_FEATURE_ID,
    check_pressure_invariants,
    initial_pressure_state,
    pressure_state_hash,
)


CANDIDATE_PRESSURE_SCHEMA_VERSION = 1
CANDIDATE_DRAFT_SCHEMA_VERSION = 2
CANDIDATE_SEMANTIC_SCHEMA_VERSION = 2
CANDIDATE_ATTEMPT_SCHEMA_VERSION = 1
CANDIDATE_COMPILER_ID = "genesis.v1c_candidate_compiler"
CANDIDATE_COMPILER_CONTRACT_VERSION = 2
CANDIDATE_ATTEMPT_STATUSES = frozenset({"BLOCKED_REQUIREMENTS", "READY_FOR_FUTURE_PREFLIGHT"})
PENDING_GATES = (
    "REQUIREMENTS_GATE",
    "RUNTIME_CATALOG_SUPPORT",
    "STATIC_PREFLIGHT",
    "GAMEPLAY_PREFLIGHT",
    "STRUCTURAL_DIVERGENCE",
    "PUBLICATION",
    "AUTOPLAY_COMPATIBILITY",
)


class CandidateValidationError(ArtifactValidationError):
    """Stable validation error for candidate component and attempt artifacts."""


def _candidate_type(value: Any, expected: type, path: str) -> None:
    if type(value) is not expected:
        _fail("INVALID_TYPE", path, expected=expected.__name__, actual=value, error_cls=CandidateValidationError)


@dataclass(frozen=True, slots=True, init=False)
class CandidatePressureComponent:
    pressure_schema_version: int
    feature_id: str
    contract_version: str
    _pressure_config_json: str = field(repr=False, compare=True)
    pressure_config_hash: str
    _initial_state_json: str = field(repr=False, compare=True)
    initial_state_hash: str
    source_pressure_selection_hash: str
    candidate_binding_assessment_hash: str

    def __init__(
        self,
        feature_id: str,
        contract_version: str,
        pressure_config: ExclusiveUpgradePressureConfig,
        initial_state: ExclusiveUpgradePressureState,
        source_pressure_selection_hash: str,
        candidate_binding_assessment_hash: str,
        pressure_config_hash: str | None = None,
        initial_state_hash: str | None = None,
        pressure_schema_version: int = CANDIDATE_PRESSURE_SCHEMA_VERSION,
    ) -> None:
        if type(pressure_schema_version) is not int or pressure_schema_version != CANDIDATE_PRESSURE_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.pressure_schema_version", expected=str(CANDIDATE_PRESSURE_SCHEMA_VERSION), actual=pressure_schema_version, error_cls=CandidateValidationError)
        object.__setattr__(self, "pressure_schema_version", pressure_schema_version)
        if type(feature_id) is not str or feature_id != PRESSURE_FEATURE_ID:
            _fail("PRESSURE_CONFIG_MISMATCH", "$.feature_id", message="pressure component feature identity is fixed", error_cls=CandidateValidationError)
        if type(contract_version) is not str or contract_version != PRESSURE_CONTRACT_VERSION:
            _fail("PRESSURE_CONFIG_MISMATCH", "$.contract_version", message="pressure component contract identity is fixed", error_cls=CandidateValidationError)
        _candidate_type(pressure_config, ExclusiveUpgradePressureConfig, "$.pressure_config")
        _candidate_type(initial_state, ExclusiveUpgradePressureState, "$.initial_state")
        try:
            check_pressure_invariants(initial_state, pressure_config)
            computed_config_hash = pressure_config.hash
            computed_state_hash = pressure_state_hash(initial_state)
            expected_initial = initial_pressure_state(pressure_config)
            if initial_state.to_dict() != expected_initial.to_dict():
                _fail("PRESSURE_CONFIG_MISMATCH", "$.initial_state", message="candidate initial state must be derived from the supplied pressure config", error_cls=CandidateValidationError)
        except CandidateValidationError:
            raise
        except ValueError as exc:
            _fail("PRESSURE_CONFIG_MISMATCH", "$.pressure_config", message="pressure config/state failed its concrete contract", error_cls=CandidateValidationError)
        if pressure_config_hash is not None and pressure_config_hash != computed_config_hash:
            _fail("CANDIDATE_HASH_MISMATCH", "$.pressure_config_hash", message="pressure config hash does not match canonical payload", error_cls=CandidateValidationError)
        if initial_state_hash is not None and initial_state_hash != computed_state_hash:
            _fail("CANDIDATE_HASH_MISMATCH", "$.initial_state_hash", message="initial state hash does not match canonical payload", error_cls=CandidateValidationError)
        object.__setattr__(self, "feature_id", feature_id)
        object.__setattr__(self, "contract_version", contract_version)
        object.__setattr__(self, "_pressure_config_json", _canonical_payload(pressure_config.to_dict(), error_cls=CandidateValidationError))
        object.__setattr__(self, "pressure_config_hash", computed_config_hash)
        object.__setattr__(self, "_initial_state_json", _canonical_payload(initial_state.to_dict(), error_cls=CandidateValidationError))
        object.__setattr__(self, "initial_state_hash", computed_state_hash)
        object.__setattr__(self, "source_pressure_selection_hash", _validate_hash(source_pressure_selection_hash, "$.source_pressure_selection_hash", error_cls=CandidateValidationError))
        object.__setattr__(self, "candidate_binding_assessment_hash", _validate_hash(candidate_binding_assessment_hash, "$.candidate_binding_assessment_hash", error_cls=CandidateValidationError))

    @property
    def pressure_config(self) -> ExclusiveUpgradePressureConfig:
        try:
            return ExclusiveUpgradePressureConfig.from_dict(json.loads(self._pressure_config_json))
        except ValueError as exc:
            raise CandidateValidationError("PRESSURE_CONFIG_MISMATCH", "$.pressure_config", message="stored pressure config is invalid") from exc

    @property
    def initial_state(self) -> ExclusiveUpgradePressureState:
        try:
            return ExclusiveUpgradePressureState.from_dict(json.loads(self._initial_state_json))
        except ValueError as exc:
            raise CandidateValidationError("PRESSURE_CONFIG_MISMATCH", "$.initial_state", message="stored initial state is invalid") from exc

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict(), error_cls=CandidateValidationError)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pressure_schema_version": self.pressure_schema_version,
            "feature_id": self.feature_id,
            "contract_version": self.contract_version,
            "pressure_config": self.pressure_config.to_dict(),
            "pressure_config_hash": self.pressure_config_hash,
            "initial_state": self.initial_state.to_dict(),
            "initial_state_hash": self.initial_state_hash,
            "source_pressure_selection_hash": self.source_pressure_selection_hash,
            "candidate_binding_assessment_hash": self.candidate_binding_assessment_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidatePressureComponent":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data, error_cls=CandidateValidationError)
        allowed = {
            "pressure_schema_version",
            "feature_id",
            "contract_version",
            "pressure_config",
            "pressure_config_hash",
            "initial_state",
            "initial_state_hash",
            "source_pressure_selection_hash",
            "candidate_binding_assessment_hash",
        }
        _check_exact_fields(data, allowed, "$", error_cls=CandidateValidationError)
        if not isinstance(data["pressure_config"], Mapping) or not isinstance(data["initial_state"], Mapping):
            _fail("INVALID_TYPE", "$.pressure_config", expected="object payloads", actual=data, error_cls=CandidateValidationError)
        for nested_name in ("pressure_config", "initial_state"):
            if any(type(key) is not str for key in data[nested_name]):
                _fail("INVALID_TYPE", f"$.{nested_name}", expected="string keys", actual=data[nested_name], error_cls=CandidateValidationError)
        try:
            config = ExclusiveUpgradePressureConfig.from_dict(data["pressure_config"])
            state = ExclusiveUpgradePressureState.from_dict(data["initial_state"])
        except ValueError as exc:
            _fail("PRESSURE_CONFIG_MISMATCH", "$.pressure_config", message="invalid pressure component payload", error_cls=CandidateValidationError)
        return cls(
            feature_id=data["feature_id"],
            contract_version=data["contract_version"],
            pressure_config=config,
            initial_state=state,
            source_pressure_selection_hash=data["source_pressure_selection_hash"],
            candidate_binding_assessment_hash=data["candidate_binding_assessment_hash"],
            pressure_config_hash=data["pressure_config_hash"],
            initial_state_hash=data["initial_state_hash"],
            pressure_schema_version=data["pressure_schema_version"],
        )


@dataclass(frozen=True, slots=True, init=False)
class CandidateInitialComponent:
    feature_id: str
    contract_version: str
    _state_json: str = field(repr=False, compare=True)
    state_hash: str

    def __init__(self, feature_id: str, contract_version: str, initial_state: ExclusiveUpgradePressureState, state_hash: str | None = None) -> None:
        if type(feature_id) is not str or feature_id != PRESSURE_FEATURE_ID:
            _fail("PRESSURE_CONFIG_MISMATCH", "$.feature_id", message="candidate initial component feature identity is fixed", error_cls=CandidateValidationError)
        if type(contract_version) is not str or contract_version != PRESSURE_CONTRACT_VERSION:
            _fail("PRESSURE_CONFIG_MISMATCH", "$.contract_version", message="candidate initial component contract identity is fixed", error_cls=CandidateValidationError)
        _candidate_type(initial_state, ExclusiveUpgradePressureState, "$.initial_state")
        computed = pressure_state_hash(initial_state)
        if state_hash is not None and state_hash != computed:
            _fail("CANDIDATE_HASH_MISMATCH", "$.state_hash", message="candidate initial state hash does not match payload", error_cls=CandidateValidationError)
        object.__setattr__(self, "feature_id", feature_id)
        object.__setattr__(self, "contract_version", contract_version)
        object.__setattr__(self, "_state_json", _canonical_payload(initial_state.to_dict(), error_cls=CandidateValidationError))
        object.__setattr__(self, "state_hash", computed)

    @property
    def initial_state(self) -> ExclusiveUpgradePressureState:
        try:
            return ExclusiveUpgradePressureState.from_dict(json.loads(self._state_json))
        except ValueError as exc:
            raise CandidateValidationError("PRESSURE_CONFIG_MISMATCH", "$.initial_state", message="stored candidate state is invalid") from exc

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict(), error_cls=CandidateValidationError)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "contract_version": self.contract_version,
            "initial_state": self.initial_state.to_dict(),
            "state_hash": self.state_hash,
            "durability_tier": CANDIDATE_DURABLE,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidateInitialComponent":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data, error_cls=CandidateValidationError)
        allowed = {"feature_id", "contract_version", "initial_state", "state_hash", "durability_tier"}
        _check_exact_fields(data, allowed, "$", error_cls=CandidateValidationError)
        if data["durability_tier"] != CANDIDATE_DURABLE:
            _fail("INVALID_FACT_TIER", "$.durability_tier", expected=CANDIDATE_DURABLE, actual=data["durability_tier"], error_cls=CandidateValidationError)
        if not isinstance(data["initial_state"], Mapping):
            _fail("INVALID_TYPE", "$.initial_state", expected="object", actual=data["initial_state"], error_cls=CandidateValidationError)
        if any(type(key) is not str for key in data["initial_state"]):
            _fail("INVALID_TYPE", "$.initial_state", expected="string keys", actual=data["initial_state"], error_cls=CandidateValidationError)
        try:
            state = ExclusiveUpgradePressureState.from_dict(data["initial_state"])
        except ValueError as exc:
            _fail("PRESSURE_CONFIG_MISMATCH", "$.initial_state", message="invalid candidate state payload", error_cls=CandidateValidationError)
        return cls(data["feature_id"], data["contract_version"], state, data["state_hash"])


@dataclass(frozen=True, slots=True, init=False)
class CandidateWorldDraft:
    draft_schema_version: int
    draft_id: str
    blueprint_hash: str
    binding_assessment_hash: str
    _candidate_facts_json: str = field(repr=False, compare=True)
    _pressure_component_json: str = field(repr=False, compare=True)
    _initial_component_json: str = field(repr=False, compare=True)
    _foundation_component_json: str = field(repr=False, compare=True)
    world_semantic_candidate_hash: str

    def __init__(
        self,
        draft_schema_version: int,
        draft_id: str,
        blueprint_hash: str,
        binding_assessment_hash: str,
        candidate_facts: Sequence[Any],
        pressure_component: CandidatePressureComponent,
        candidate_initial_component: CandidateInitialComponent,
        foundation_component: FoundationCandidateComponent,
        world_semantic_candidate_hash: str | None = None,
    ) -> None:
        from .blueprint import BlueprintRequirementFact

        if type(draft_schema_version) is not int or draft_schema_version != CANDIDATE_DRAFT_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.draft_schema_version", expected=str(CANDIDATE_DRAFT_SCHEMA_VERSION), actual=draft_schema_version, error_cls=CandidateValidationError)
        object.__setattr__(self, "draft_schema_version", draft_schema_version)
        object.__setattr__(self, "draft_id", _validate_id(draft_id, "$.draft_id", error_cls=CandidateValidationError))
        object.__setattr__(self, "blueprint_hash", _validate_hash(blueprint_hash, "$.blueprint_hash", error_cls=CandidateValidationError))
        object.__setattr__(self, "binding_assessment_hash", _validate_hash(binding_assessment_hash, "$.binding_assessment_hash", error_cls=CandidateValidationError))
        if not isinstance(candidate_facts, (list, tuple)) or not candidate_facts:
            _fail("INVALID_VALUE", "$.candidate_facts", expected="non-empty array", actual=candidate_facts, error_cls=CandidateValidationError)
        if any(type(item) is not BlueprintRequirementFact for item in candidate_facts):
            _fail("INVALID_TYPE", "$.candidate_facts", expected="BlueprintRequirementFact objects", actual=candidate_facts, error_cls=CandidateValidationError)
        if any(item.durability_tier != CANDIDATE_DURABLE for item in candidate_facts):
            _fail("INVALID_FACT_TIER", "$.candidate_facts", expected=CANDIDATE_DURABLE, actual=candidate_facts, error_cls=CandidateValidationError)
        fact_ids = [item.requirement_id for item in candidate_facts]
        if len(fact_ids) != len(set(fact_ids)):
            _fail("DUPLICATE_ID", "$.candidate_facts", message="duplicate candidate fact identifier", error_cls=CandidateValidationError)
        if type(pressure_component) is not CandidatePressureComponent:
            _fail("INVALID_TYPE", "$.pressure_component", expected="CandidatePressureComponent", actual=pressure_component, error_cls=CandidateValidationError)
        if type(candidate_initial_component) is not CandidateInitialComponent:
            _fail("INVALID_TYPE", "$.candidate_initial_component", expected="CandidateInitialComponent", actual=candidate_initial_component, error_cls=CandidateValidationError)
        if type(foundation_component) is not FoundationCandidateComponent:
            _fail("INVALID_TYPE", "$.foundation_component", expected="FoundationCandidateComponent", actual=foundation_component, error_cls=CandidateValidationError)
        if pressure_component.feature_id != candidate_initial_component.feature_id or pressure_component.contract_version != candidate_initial_component.contract_version:
            _fail("PRESSURE_CONFIG_MISMATCH", "$.candidate_initial_component", message="candidate initial component must use the pressure component contract", error_cls=CandidateValidationError)
        if pressure_component.initial_state.to_dict() != candidate_initial_component.initial_state.to_dict():
            _fail("PRESSURE_CONFIG_MISMATCH", "$.candidate_initial_component.initial_state", message="candidate initial state must match the pressure component state", error_cls=CandidateValidationError)
        if pressure_component.initial_state_hash != candidate_initial_component.state_hash:
            _fail("CANDIDATE_HASH_MISMATCH", "$.candidate_initial_component.state_hash", message="pressure and candidate initial state hashes must agree", error_cls=CandidateValidationError)
        if (
            foundation_component.pressure_feature_id != pressure_component.feature_id
            or foundation_component.pressure_contract_version != pressure_component.contract_version
            or foundation_component.pressure_protagonist_id != pressure_component.pressure_config.protagonist_id
            or foundation_component.pressure_growth_object_id != pressure_component.pressure_config.growth_object_id
            or foundation_component.pressure_growth_object_owner_id != pressure_component.pressure_config.growth_object_owner_id
            or foundation_component.pressure_exclusive_resource_id != pressure_component.pressure_config.exclusive_resource_id
        ):
            _fail("FOUNDATION_CONFIG_MISMATCH", "$.foundation_component", message="foundation/pressure identity linkage differs", error_cls=CandidateValidationError)
        if pressure_component.candidate_binding_assessment_hash != binding_assessment_hash:
            _fail("BINDING_HASH_MISMATCH", "$.pressure_component.candidate_binding_assessment_hash", message="pressure component must bind the draft assessment", error_cls=CandidateValidationError)
        object.__setattr__(self, "_candidate_facts_json", _canonical_payload([item.to_dict() for item in candidate_facts], error_cls=CandidateValidationError))
        object.__setattr__(self, "_pressure_component_json", _canonical_payload(pressure_component.to_dict(), error_cls=CandidateValidationError))
        object.__setattr__(self, "_initial_component_json", _canonical_payload(candidate_initial_component.to_dict(), error_cls=CandidateValidationError))
        object.__setattr__(self, "_foundation_component_json", _canonical_payload(foundation_component.to_dict(), error_cls=CandidateValidationError))
        computed_semantic_hash = self._compute_semantic_hash()
        if world_semantic_candidate_hash is not None and world_semantic_candidate_hash != computed_semantic_hash:
            _fail("CANDIDATE_HASH_MISMATCH", "$.world_semantic_candidate_hash", message="candidate semantic hash does not match draft payload", error_cls=CandidateValidationError)
        object.__setattr__(self, "world_semantic_candidate_hash", computed_semantic_hash)

    def _semantic_candidate_payload(self) -> dict[str, Any]:
        """Return runtime semantics only; provenance is deliberately absent."""

        pressure_component = self.pressure_component
        initial_component = self.candidate_initial_component
        foundation_component = self.foundation_component
        candidate_fact_semantics = [
            {
                "fact_kind": fact.fact_kind,
                "visibility": fact.visibility,
                "subject_ids": list(fact.subject_ids),
                "object_ids": list(fact.object_ids),
                "labels": list(fact.labels),
                "typed_constraints": [constraint.to_dict() for constraint in fact.typed_constraints],
            }
            for fact in self.candidate_facts
        ]
        candidate_fact_semantics.sort(
            key=lambda value: _canonical_payload(value, error_cls=CandidateValidationError)
        )
        return {
            "candidate_semantic_schema_version": CANDIDATE_SEMANTIC_SCHEMA_VERSION,
            "candidate_facts": candidate_fact_semantics,
            "pressure_feature_id": pressure_component.feature_id,
            "pressure_contract_version": pressure_component.contract_version,
            "pressure_config": pressure_component.pressure_config.to_dict(),
            "initial_state": initial_component.initial_state.to_dict(),
            "foundation_component": foundation_component.semantic_payload(),
        }

    def _compute_semantic_hash(self) -> str:
        return _hash_payload(self._semantic_candidate_payload(), error_cls=CandidateValidationError)

    def _compute_artifact_hash(self) -> str:
        return _hash_payload(
            {
                "draft_schema_version": self.draft_schema_version,
                "draft_id": self.draft_id,
                "blueprint_hash": self.blueprint_hash,
                "binding_assessment_hash": self.binding_assessment_hash,
                "candidate_facts": json.loads(self._candidate_facts_json),
                "pressure_component": json.loads(self._pressure_component_json),
                "candidate_initial_component": json.loads(self._initial_component_json),
                "foundation_component": json.loads(self._foundation_component_json),
                "world_semantic_candidate_hash": self.world_semantic_candidate_hash,
            },
            error_cls=CandidateValidationError,
        )

    @property
    def candidate_facts(self) -> tuple[Any, ...]:
        from .blueprint import BlueprintRequirementFact

        try:
            return tuple(BlueprintRequirementFact.from_dict(item) for item in json.loads(self._candidate_facts_json))
        except ValueError as exc:
            raise CandidateValidationError("INVALID_VALUE", "$.candidate_facts", message="stored candidate facts are invalid") from exc

    @property
    def pressure_component(self) -> CandidatePressureComponent:
        return CandidatePressureComponent.from_dict(json.loads(self._pressure_component_json))

    @property
    def candidate_initial_component(self) -> CandidateInitialComponent:
        return CandidateInitialComponent.from_dict(json.loads(self._initial_component_json))

    @property
    def foundation_component(self) -> FoundationCandidateComponent:
        return FoundationCandidateComponent.from_dict(json.loads(self._foundation_component_json))

    @property
    def hash(self) -> str:
        return self._compute_artifact_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_schema_version": self.draft_schema_version,
            "draft_id": self.draft_id,
            "blueprint_hash": self.blueprint_hash,
            "binding_assessment_hash": self.binding_assessment_hash,
            "candidate_facts": [item.to_dict() for item in self.candidate_facts],
            "pressure_component": self.pressure_component.to_dict(),
            "candidate_initial_component": self.candidate_initial_component.to_dict(),
            "foundation_component": self.foundation_component.to_dict(),
            "world_semantic_candidate_hash": self.world_semantic_candidate_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidateWorldDraft":
        from .blueprint import BlueprintRequirementFact

        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data, error_cls=CandidateValidationError)
        allowed = {
            "draft_schema_version",
            "draft_id",
            "blueprint_hash",
            "binding_assessment_hash",
            "candidate_facts",
            "pressure_component",
            "candidate_initial_component",
            "foundation_component",
            "world_semantic_candidate_hash",
        }
        _check_exact_fields(data, allowed, "$", error_cls=CandidateValidationError)
        if (
            not isinstance(data["candidate_facts"], list)
            or not isinstance(data["pressure_component"], Mapping)
            or not isinstance(data["candidate_initial_component"], Mapping)
            or not isinstance(data["foundation_component"], Mapping)
        ):
            _fail("INVALID_TYPE", "$.candidate_facts", expected="typed candidate payloads", actual=data, error_cls=CandidateValidationError)
        return cls(
            draft_schema_version=data["draft_schema_version"],
            draft_id=data["draft_id"],
            blueprint_hash=data["blueprint_hash"],
            binding_assessment_hash=data["binding_assessment_hash"],
            candidate_facts=[BlueprintRequirementFact.from_dict(item) for item in data["candidate_facts"]],
            pressure_component=CandidatePressureComponent.from_dict(data["pressure_component"]),
            candidate_initial_component=CandidateInitialComponent.from_dict(data["candidate_initial_component"]),
            foundation_component=FoundationCandidateComponent.from_dict(data["foundation_component"]),
            world_semantic_candidate_hash=data["world_semantic_candidate_hash"],
        )


@dataclass(frozen=True, slots=True, init=False)
class CandidateGenesisAttempt:
    attempt_schema_version: int
    attempt_id: str
    source_request_hash: str
    source_proposal_hash: str
    source_approval_hash: str
    source_report_hash: str
    source_catalog_version: str
    source_catalog_hash: str
    blueprint_hash: str
    binding_assessment_hash: str
    candidate_world_draft_hash: str
    compiler_id: str
    compiler_contract_version: int
    required_pending_gates: tuple[str, ...]
    attempt_status: str

    def __init__(
        self,
        attempt_schema_version: int,
        attempt_id: str,
        source_request_hash: str,
        source_proposal_hash: str,
        source_approval_hash: str,
        source_report_hash: str,
        source_catalog_version: str,
        source_catalog_hash: str,
        blueprint_hash: str,
        binding_assessment_hash: str,
        candidate_world_draft_hash: str,
        compiler_id: str,
        compiler_contract_version: int,
        required_pending_gates: Sequence[str],
        attempt_status: str,
    ) -> None:
        if type(attempt_schema_version) is not int or attempt_schema_version != CANDIDATE_ATTEMPT_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.attempt_schema_version", expected=str(CANDIDATE_ATTEMPT_SCHEMA_VERSION), actual=attempt_schema_version, error_cls=CandidateValidationError)
        object.__setattr__(self, "attempt_schema_version", attempt_schema_version)
        object.__setattr__(self, "attempt_id", _validate_id(attempt_id, "$.attempt_id", error_cls=CandidateValidationError))
        for name, value in (
            ("source_request_hash", source_request_hash),
            ("source_proposal_hash", source_proposal_hash),
            ("source_approval_hash", source_approval_hash),
            ("source_report_hash", source_report_hash),
            ("source_catalog_hash", source_catalog_hash),
            ("blueprint_hash", blueprint_hash),
            ("binding_assessment_hash", binding_assessment_hash),
            ("candidate_world_draft_hash", candidate_world_draft_hash),
        ):
            object.__setattr__(self, name, _validate_hash(value, f"$.{name}", error_cls=CandidateValidationError))
        object.__setattr__(self, "source_catalog_version", _validate_text(source_catalog_version, "$.source_catalog_version", error_cls=CandidateValidationError, max_length=128))
        if type(compiler_id) is not str or compiler_id != CANDIDATE_COMPILER_ID:
            _fail("INVALID_VALUE", "$.compiler_id", expected=CANDIDATE_COMPILER_ID, actual=compiler_id, error_cls=CandidateValidationError)
        object.__setattr__(self, "compiler_id", compiler_id)
        if type(compiler_contract_version) is not int or compiler_contract_version != CANDIDATE_COMPILER_CONTRACT_VERSION:
            _fail("INVALID_VALUE", "$.compiler_contract_version", expected=str(CANDIDATE_COMPILER_CONTRACT_VERSION), actual=compiler_contract_version, error_cls=CandidateValidationError)
        object.__setattr__(self, "compiler_contract_version", compiler_contract_version)
        if type(attempt_status) is not str or attempt_status not in CANDIDATE_ATTEMPT_STATUSES:
            _fail("INVALID_VALUE", "$.attempt_status", expected="BLOCKED_REQUIREMENTS|READY_FOR_FUTURE_PREFLIGHT", actual=attempt_status, error_cls=CandidateValidationError)
        object.__setattr__(self, "attempt_status", attempt_status)
        if not isinstance(required_pending_gates, (list, tuple)):
            _fail("INVALID_TYPE", "$.required_pending_gates", expected="array", actual=required_pending_gates, error_cls=CandidateValidationError)
        gates = tuple(_validate_text(gate, f"$.required_pending_gates[{index}]", error_cls=CandidateValidationError, max_length=64) for index, gate in enumerate(required_pending_gates))
        if len(gates) != len(set(gates)):
            _fail("DUPLICATE_ID", "$.required_pending_gates", message="duplicate pending gate", error_cls=CandidateValidationError)
        if not gates:
            _fail("REQUIREMENTS_GATE_BLOCKED", "$.required_pending_gates", message="candidate attempts must retain at least one unresolved V1 gate", error_cls=CandidateValidationError)
        if attempt_status == "BLOCKED_REQUIREMENTS" and tuple(gates) != PENDING_GATES:
            _fail("REQUIREMENTS_GATE_BLOCKED", "$.required_pending_gates", message="blocked candidate must preserve the complete V1-C pending gate list", error_cls=CandidateValidationError)
        object.__setattr__(self, "required_pending_gates", gates)

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict(), error_cls=CandidateValidationError)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_schema_version": self.attempt_schema_version,
            "attempt_id": self.attempt_id,
            "source_request_hash": self.source_request_hash,
            "source_proposal_hash": self.source_proposal_hash,
            "source_approval_hash": self.source_approval_hash,
            "source_report_hash": self.source_report_hash,
            "source_catalog_version": self.source_catalog_version,
            "source_catalog_hash": self.source_catalog_hash,
            "blueprint_hash": self.blueprint_hash,
            "binding_assessment_hash": self.binding_assessment_hash,
            "candidate_world_draft_hash": self.candidate_world_draft_hash,
            "compiler_id": self.compiler_id,
            "compiler_contract_version": self.compiler_contract_version,
            "required_pending_gates": list(self.required_pending_gates),
            "attempt_status": self.attempt_status,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidateGenesisAttempt":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data, error_cls=CandidateValidationError)
        allowed = {
            "attempt_schema_version",
            "attempt_id",
            "source_request_hash",
            "source_proposal_hash",
            "source_approval_hash",
            "source_report_hash",
            "source_catalog_version",
            "source_catalog_hash",
            "blueprint_hash",
            "binding_assessment_hash",
            "candidate_world_draft_hash",
            "compiler_id",
            "compiler_contract_version",
            "required_pending_gates",
            "attempt_status",
        }
        _check_exact_fields(data, allowed, "$", error_cls=CandidateValidationError)
        return cls(**dict(data))


def _validate_pressure_selection_config(blueprint: WorldBlueprint, pressure_config: ExclusiveUpgradePressureConfig) -> None:
    selection = blueprint.pressure_selection
    pairs = (
        ("protagonist_id", selection.protagonist_id, pressure_config.protagonist_id),
        ("growth_object_id", selection.growth_object_id, pressure_config.growth_object_id),
        ("growth_object_owner_id", selection.growth_object_owner_id, pressure_config.growth_object_owner_id),
        ("exclusive_resource_id", selection.exclusive_resource_id, pressure_config.exclusive_resource_id),
    )
    if any(expected != actual for _, expected, actual in pairs):
        _fail("PRESSURE_SELECTION_MISMATCH", "$.pressure_config", message="pressure config identity differs from Blueprint pressure selection", error_cls=CandidateValidationError)
    if pressure_config.feature_id != selection.feature_id or pressure_config.contract_version != selection.contract_version:
        _fail("PRESSURE_CONFIG_MISMATCH", "$.pressure_config", message="pressure config contract differs from Blueprint selection", error_cls=CandidateValidationError)


def compile_candidate_artifacts(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    blueprint: WorldBlueprint,
    pressure_config: ExclusiveUpgradePressureConfig,
) -> tuple[CandidateWorldDraft, CandidateGenesisAttempt]:
    """Compile the detached V1-C draft and its blocked attempt together.

    The draft is returned so a caller can persist the candidate artifact and
    independently review its hash; neither result is an authoritative
    WorldPack, Campaign, or runtime binding.
    """

    for name, value, expected in (
        ("request", request, GenesisRequest),
        ("proposal", proposal, RequirementProposal),
        ("coverage_approval", coverage_approval, RequirementCoverageApproval),
        ("report", report, FeatureRequirementReport),
        ("catalog", catalog, FeatureSupportCatalog),
        ("blueprint", blueprint, WorldBlueprint),
        ("pressure_config", pressure_config, ExclusiveUpgradePressureConfig),
    ):
        if type(value) is not expected:
            _fail("INVALID_TYPE", f"$.{name}", expected=expected.__name__, actual=value, error_cls=CandidateValidationError)
    try:
        # The persisted V1-A Report is the first trust boundary.  No
        # Blueprint, Binding, or candidate artifact is accepted before its
        # Approval-bound deterministic re-verification succeeds.
        verify_report(request, proposal, coverage_approval, catalog, report)
    except ValueError as exc:
        _fail("REPORT_NOT_VERIFIED", "$.report", message="V1-A Report failed deterministic re-verification", error_cls=CandidateValidationError)
    try:
        validate_blueprint_lineage(blueprint, request, proposal, coverage_approval, report, catalog, error_cls=CandidateValidationError)
    except CandidateValidationError:
        raise
    except ValueError as exc:
        _fail("LINEAGE_MISMATCH", "$.blueprint", message="Blueprint lineage validation failed", error_cls=CandidateValidationError)
    try:
        assessment = build_runtime_binding_assessment(request, proposal, coverage_approval, report, catalog, blueprint)
    except BindingValidationError as exc:
        _fail(exc.code, exc.path, message=str(exc), error_cls=CandidateValidationError)
    _validate_pressure_selection_config(blueprint, pressure_config)
    try:
        foundation_component = build_foundation_candidate(proposal, blueprint, pressure_config)
    except ValueError as exc:
        _fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.foundation_component", message="foundation candidate cannot be built from the recorded Blueprint", error_cls=CandidateValidationError)
    try:
        initial_state = initial_pressure_state(pressure_config)
        check_pressure_invariants(initial_state, pressure_config)
    except ValueError as exc:
        _fail("PRESSURE_CONFIG_MISMATCH", "$.pressure_config", message="pressure config cannot materialize its candidate initial state", error_cls=CandidateValidationError)
    pressure_component = CandidatePressureComponent(
        feature_id=pressure_config.feature_id,
        contract_version=pressure_config.contract_version,
        pressure_config=pressure_config,
        initial_state=initial_state,
        source_pressure_selection_hash=blueprint.pressure_selection.hash,
        candidate_binding_assessment_hash=assessment.hash,
    )
    initial_component = CandidateInitialComponent(
        feature_id=pressure_config.feature_id,
        contract_version=pressure_config.contract_version,
        initial_state=initial_state,
    )
    draft = CandidateWorldDraft(
        draft_schema_version=CANDIDATE_DRAFT_SCHEMA_VERSION,
        draft_id=f"draft-{blueprint.blueprint_id}",
        blueprint_hash=blueprint.hash,
        binding_assessment_hash=assessment.hash,
        candidate_facts=blueprint.facts,
        pressure_component=pressure_component,
        candidate_initial_component=initial_component,
        foundation_component=foundation_component,
    )
    attempt = CandidateGenesisAttempt(
        attempt_schema_version=CANDIDATE_ATTEMPT_SCHEMA_VERSION,
        attempt_id=f"attempt-{draft.hash[:32]}",
        source_request_hash=request.hash,
        source_proposal_hash=proposal.hash,
        source_approval_hash=coverage_approval.hash,
        source_report_hash=report.hash,
        source_catalog_version=catalog.version,
        source_catalog_hash=catalog.hash,
        blueprint_hash=blueprint.hash,
        binding_assessment_hash=assessment.hash,
        candidate_world_draft_hash=draft.hash,
        compiler_id=CANDIDATE_COMPILER_ID,
        compiler_contract_version=CANDIDATE_COMPILER_CONTRACT_VERSION,
        required_pending_gates=PENDING_GATES,
        # V1-C.2 is a detached candidate seam.  The canonical compiler never
        # emits a materialization-ready status, even if a future fixture were
        # to report all current requirements as supported.
        attempt_status="BLOCKED_REQUIREMENTS",
    )
    return draft, attempt


def verify_candidate_artifacts(
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
) -> tuple[RuntimeBindingAssessment, CandidateWorldDraft, CandidateGenesisAttempt]:
    """Recompute and verify the complete persisted bounded V1-C.2 artifact tuple."""

    for name, value, expected in (
        ("request", request, GenesisRequest),
        ("proposal", proposal, RequirementProposal),
        ("coverage_approval", coverage_approval, RequirementCoverageApproval),
        ("report", report, FeatureRequirementReport),
        ("catalog", catalog, FeatureSupportCatalog),
        ("blueprint", blueprint, WorldBlueprint),
        ("pressure_config", pressure_config, ExclusiveUpgradePressureConfig),
        ("assessment", assessment, RuntimeBindingAssessment),
        ("draft", draft, CandidateWorldDraft),
        ("attempt", attempt, CandidateGenesisAttempt),
    ):
        if type(value) is not expected:
            _fail("INVALID_TYPE", f"$.{name}", expected=expected.__name__, actual=value, error_cls=CandidateValidationError)
    try:
        verify_report(request, proposal, coverage_approval, catalog, report)
    except (GenesisValidationError, ValueError) as exc:
        _fail("REPORT_NOT_VERIFIED", "$.report", message="V1-A Report failed deterministic re-verification", error_cls=CandidateValidationError)
    try:
        validate_blueprint_lineage(blueprint, request, proposal, coverage_approval, report, catalog, error_cls=CandidateValidationError)
    except CandidateValidationError:
        raise
    except ValueError as exc:
        _fail("LINEAGE_MISMATCH", "$.blueprint", message="Blueprint lineage validation failed", error_cls=CandidateValidationError)

    # This call independently recomputes every binding item and gate; a
    # parsed assessment or its local hash is never treated as sufficient.
    verified_assessment = verify_runtime_binding_assessment(
        request,
        proposal,
        coverage_approval,
        report,
        catalog,
        blueprint,
        assessment,
    )
    try:
        verify_foundation_candidate(proposal, blueprint, pressure_config, draft.foundation_component)
    except ValueError as exc:
        _fail("FOUNDATION_HASH_MISMATCH", "$.draft.foundation_component", message="persisted foundation candidate failed deterministic recomputation", error_cls=CandidateValidationError)
    expected_draft, expected_attempt = compile_candidate_artifacts(
        request,
        proposal,
        coverage_approval,
        report,
        catalog,
        blueprint,
        pressure_config,
    )
    try:
        draft_matches = draft.hash == expected_draft.hash and draft.to_dict() == expected_draft.to_dict()
    except (ArtifactValidationError, TypeError, ValueError):
        draft_matches = False
    if not draft_matches:
        _fail("CANDIDATE_HASH_MISMATCH", "$.draft", message="persisted CandidateWorldDraft differs from deterministic recompilation", error_cls=CandidateValidationError)
    try:
        attempt_matches = attempt.hash == expected_attempt.hash and attempt.to_dict() == expected_attempt.to_dict()
    except (ArtifactValidationError, TypeError, ValueError):
        attempt_matches = False
    if not attempt_matches:
        _fail("CANDIDATE_HASH_MISMATCH", "$.attempt", message="persisted CandidateGenesisAttempt differs from deterministic recompilation", error_cls=CandidateValidationError)
    return verified_assessment, expected_draft, expected_attempt


def compile_candidate_attempt(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    blueprint: WorldBlueprint,
    pressure_config: ExclusiveUpgradePressureConfig,
) -> CandidateGenesisAttempt:
    """Compile one deterministic, deliberately blocked V1-C candidate attempt."""

    _draft, attempt = compile_candidate_artifacts(
        request,
        proposal,
        coverage_approval,
        report,
        catalog,
        blueprint,
        pressure_config,
    )
    return attempt


def require_materializable_candidate(attempt: CandidateGenesisAttempt) -> CandidateGenesisAttempt:
    """Explicitly refuse promotion to a BoundRuntimeConfiguration or WorldPack."""

    if type(attempt) is not CandidateGenesisAttempt:
        _fail("INVALID_TYPE", "$.attempt", expected="CandidateGenesisAttempt", actual=attempt, error_cls=CandidateValidationError)
    if attempt.attempt_status != "READY_FOR_FUTURE_PREFLIGHT" or attempt.required_pending_gates:
        _fail("REQUIREMENTS_GATE_BLOCKED", "$.attempt", message="candidate attempt is not materializable before all later V1 gates", error_cls=CandidateValidationError)
    return attempt


assert_candidate_worldpack_materializable = require_materializable_candidate


__all__ = [
    "CANDIDATE_PRESSURE_SCHEMA_VERSION",
    "CANDIDATE_ATTEMPT_SCHEMA_VERSION",
    "CANDIDATE_ATTEMPT_STATUSES",
    "CANDIDATE_COMPILER_CONTRACT_VERSION",
    "CANDIDATE_COMPILER_ID",
    "CANDIDATE_DRAFT_SCHEMA_VERSION",
    "CANDIDATE_SEMANTIC_SCHEMA_VERSION",
    "CandidateGenesisAttempt",
    "CandidateInitialComponent",
    "CandidatePressureComponent",
    "CandidateValidationError",
    "CandidateWorldDraft",
    "PENDING_GATES",
    "assert_candidate_worldpack_materializable",
    "compile_candidate_artifacts",
    "compile_candidate_attempt",
    "require_materializable_candidate",
    "verify_candidate_artifacts",
]
