"""Candidate Runtime Binding assessment for bounded Genesis V1-C.2.

This module records what a concrete candidate pressure contract *could* bind
without claiming that the Runtime Catalog supports it.  In particular,
``CANDIDATE_RUNTIME_MATCH`` is never a Catalog ``SUPPORTED`` result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping, Sequence

from .blueprint import (
    ArtifactValidationError,
    BlueprintValidationError,
    PRESSURE_REQUIREMENT_IDS,
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
    FOUNDATION_FEATURE_ID,
    FOUNDATION_REQUIREMENT_IDS,
    validate_foundation_blueprint_facts,
)
from .models import (
    FeatureRequirementReport,
    GenesisRequest,
    GenesisValidationError,
    RequirementCoverageApproval,
    RequirementProposal,
)


BINDING_SCHEMA_VERSION = 1
BINDING_STATUSES = frozenset(
    {
        "CONTENT_ACCEPTED",
        "CANDIDATE_RUNTIME_MATCH",
        "UNBOUND_BLOCKING",
        "OMITTED_OPTIONAL",
    }
)
BINDING_REASON_CODES = frozenset(
    {
        "CONTENT_REPORT_SUPPORTED",
        "REPORT_SUPPORT_PENDING",
        "NO_MATCHING_RUNTIME_CONTRACT",
        "REPORT_ITEM_REJECTED",
        "REPORT_ITEM_WARNING",
        "OPTIONAL_REQUIREMENT_OMITTED",
        "LINEAGE_MISMATCH",
    }
)


class BindingValidationError(ArtifactValidationError):
    """Stable validation error for candidate binding assessments."""


@dataclass(frozen=True, slots=True, init=False)
class CandidateBindingItem:
    requirement_id: str
    status: str
    candidate_feature_id: str | None
    reason_code: str

    def __init__(
        self,
        requirement_id: str,
        status: str,
        candidate_feature_id: str | None,
        reason_code: str,
    ) -> None:
        object.__setattr__(self, "requirement_id", _validate_id(requirement_id, "$.requirement_id", error_cls=BindingValidationError))
        if type(status) is not str or status not in BINDING_STATUSES:
            _fail("INVALID_VALUE", "$.status", expected="finite candidate binding status", actual=status, error_cls=BindingValidationError)
        object.__setattr__(self, "status", status)
        if candidate_feature_id is not None:
            candidate_feature_id = _validate_id(candidate_feature_id, "$.candidate_feature_id", error_cls=BindingValidationError)
        object.__setattr__(self, "candidate_feature_id", candidate_feature_id)
        if type(reason_code) is not str or reason_code not in BINDING_REASON_CODES:
            _fail("INVALID_VALUE", "$.reason_code", expected="finite candidate binding reason code", actual=reason_code, error_cls=BindingValidationError)
        object.__setattr__(self, "reason_code", reason_code)
        if status in {"UNBOUND_BLOCKING", "OMITTED_OPTIONAL"} and candidate_feature_id is not None:
            _fail("INVALID_VALUE", "$.candidate_feature_id", message="blocking or omitted items cannot carry a candidate binding", error_cls=BindingValidationError)
        if status == "CONTENT_ACCEPTED" and candidate_feature_id is None:
            _fail("INVALID_VALUE", "$.candidate_feature_id", message="accepted content requires its concrete content feature", error_cls=BindingValidationError)
        if status == "CANDIDATE_RUNTIME_MATCH" and candidate_feature_id is None:
            _fail("INVALID_VALUE", "$.candidate_feature_id", message="candidate runtime match requires a candidate feature ID", error_cls=BindingValidationError)
        expected_reasons = {
            "CONTENT_ACCEPTED": {"CONTENT_REPORT_SUPPORTED"},
            "CANDIDATE_RUNTIME_MATCH": {"REPORT_SUPPORT_PENDING"},
            "UNBOUND_BLOCKING": {"NO_MATCHING_RUNTIME_CONTRACT", "REPORT_ITEM_REJECTED", "REPORT_ITEM_WARNING", "LINEAGE_MISMATCH"},
            "OMITTED_OPTIONAL": {"OPTIONAL_REQUIREMENT_OMITTED"},
        }
        if reason_code not in expected_reasons[status]:
            _fail("INVALID_VALUE", "$.reason_code", message="binding status and reason code are inconsistent", error_cls=BindingValidationError)

    @property
    def feature_id(self) -> str | None:
        """Compatibility alias for callers that use the catalog terminology."""

        return self.candidate_feature_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "status": self.status,
            "candidate_feature_id": self.candidate_feature_id,
            "reason_code": self.reason_code,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidateBindingItem":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data, error_cls=BindingValidationError)
        allowed = {"requirement_id", "status", "candidate_feature_id", "reason_code"}
        _check_exact_fields(data, allowed, "$", error_cls=BindingValidationError)
        return cls(**dict(data))


@dataclass(frozen=True, slots=True, init=False)
class RuntimeBindingAssessment:
    assessment_schema_version: int
    source_request_hash: str
    source_proposal_hash: str
    source_approval_hash: str
    source_report_hash: str
    source_catalog_version: str
    source_catalog_hash: str
    blueprint_hash: str
    _items_json: str = field(repr=False, compare=True)
    binding_gate_passed: bool

    def __init__(
        self,
        assessment_schema_version: int,
        source_request_hash: str,
        source_proposal_hash: str,
        source_approval_hash: str,
        source_report_hash: str,
        source_catalog_version: str,
        source_catalog_hash: str,
        blueprint_hash: str,
        items: Sequence[CandidateBindingItem],
        binding_gate_passed: bool | None = None,
    ) -> None:
        if type(assessment_schema_version) is not int or assessment_schema_version != BINDING_SCHEMA_VERSION:
            _fail("INVALID_VALUE", "$.assessment_schema_version", expected=str(BINDING_SCHEMA_VERSION), actual=assessment_schema_version, error_cls=BindingValidationError)
        object.__setattr__(self, "assessment_schema_version", assessment_schema_version)
        for name, value in (
            ("source_request_hash", source_request_hash),
            ("source_proposal_hash", source_proposal_hash),
            ("source_approval_hash", source_approval_hash),
            ("source_report_hash", source_report_hash),
            ("source_catalog_hash", source_catalog_hash),
            ("blueprint_hash", blueprint_hash),
        ):
            object.__setattr__(self, name, _validate_hash(value, f"$.{name}", error_cls=BindingValidationError))
        object.__setattr__(self, "source_catalog_version", _validate_text(source_catalog_version, "$.source_catalog_version", error_cls=BindingValidationError, max_length=128))
        if not isinstance(items, (list, tuple)):
            _fail("INVALID_TYPE", "$.items", expected="array of CandidateBindingItem", actual=items, error_cls=BindingValidationError)
        if not items:
            _fail("INVALID_VALUE", "$.items", expected="non-empty array", actual=items, error_cls=BindingValidationError)
        if any(type(item) is not CandidateBindingItem for item in items):
            _fail("INVALID_TYPE", "$.items", expected="CandidateBindingItem objects", actual=items, error_cls=BindingValidationError)
        ids = [item.requirement_id for item in items]
        if len(ids) != len(set(ids)):
            _fail("DUPLICATE_ID", "$.items", message="duplicate requirement identifier", error_cls=BindingValidationError)
        derived_gate = all(item.status in {"CONTENT_ACCEPTED", "OMITTED_OPTIONAL"} for item in items)
        if binding_gate_passed is None:
            binding_gate_passed = derived_gate
        if type(binding_gate_passed) is not bool:
            _fail("INVALID_TYPE", "$.binding_gate_passed", expected="boolean", actual=binding_gate_passed, error_cls=BindingValidationError)
        if binding_gate_passed != derived_gate:
            _fail("BINDING_HASH_MISMATCH", "$.binding_gate_passed", message="binding gate must be derived from assessment items", error_cls=BindingValidationError)
        object.__setattr__(self, "_items_json", _canonical_payload([item.to_dict() for item in items], error_cls=BindingValidationError))
        object.__setattr__(self, "binding_gate_passed", binding_gate_passed)

    @property
    def items(self) -> tuple[CandidateBindingItem, ...]:
        try:
            return tuple(CandidateBindingItem.from_dict(item) for item in json.loads(self._items_json))
        except (BindingValidationError, TypeError, ValueError) as exc:
            raise BindingValidationError("INVALID_VALUE", "$.items", message="stored binding items are invalid") from exc

    @property
    def status_counts(self) -> dict[str, int]:
        """Deterministic projection; counts are not persisted as artifact fields."""

        return {status: sum(item.status == status for item in self.items) for status in sorted(BINDING_STATUSES)}

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict(), error_cls=BindingValidationError)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_schema_version": self.assessment_schema_version,
            "source_request_hash": self.source_request_hash,
            "source_proposal_hash": self.source_proposal_hash,
            "source_approval_hash": self.source_approval_hash,
            "source_report_hash": self.source_report_hash,
            "source_catalog_version": self.source_catalog_version,
            "source_catalog_hash": self.source_catalog_hash,
            "blueprint_hash": self.blueprint_hash,
            "items": [item.to_dict() for item in self.items],
            "binding_gate_passed": self.binding_gate_passed,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RuntimeBindingAssessment":
        if not isinstance(data, Mapping):
            _fail("INVALID_TYPE", "$", expected="object", actual=data, error_cls=BindingValidationError)
        allowed = {
            "assessment_schema_version",
            "source_request_hash",
            "source_proposal_hash",
            "source_approval_hash",
            "source_report_hash",
            "source_catalog_version",
            "source_catalog_hash",
            "blueprint_hash",
            "items",
            "binding_gate_passed",
        }
        _check_exact_fields(data, allowed, "$", error_cls=BindingValidationError)
        if not isinstance(data["items"], list):
            _fail("INVALID_TYPE", "$.items", expected="array", actual=data["items"], error_cls=BindingValidationError)
        return cls(
            assessment_schema_version=data["assessment_schema_version"],
            source_request_hash=data["source_request_hash"],
            source_proposal_hash=data["source_proposal_hash"],
            source_approval_hash=data["source_approval_hash"],
            source_report_hash=data["source_report_hash"],
            source_catalog_version=data["source_catalog_version"],
            source_catalog_hash=data["source_catalog_hash"],
            blueprint_hash=data["blueprint_hash"],
            items=[CandidateBindingItem.from_dict(item) for item in data["items"]],
            binding_gate_passed=data["binding_gate_passed"],
        )


def _verify_v1a_lineage(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    blueprint: WorldBlueprint,
) -> None:
    try:
        verify_report(request, proposal, coverage_approval, catalog, report)
    except (GenesisValidationError, ValueError) as exc:
        _fail("REPORT_NOT_VERIFIED", "$.report", message="V1-A Report failed deterministic re-verification", error_cls=BindingValidationError)
    try:
        validate_blueprint_lineage(
            blueprint,
            request,
            proposal,
            coverage_approval,
            report,
            catalog,
            error_cls=BindingValidationError,
        )
    except ArtifactValidationError as exc:
        _fail(exc.code, exc.path, message=str(exc), error_cls=BindingValidationError)


def build_runtime_binding_assessment(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    blueprint: WorldBlueprint,
) -> RuntimeBindingAssessment:
    """Build a deterministic candidate assessment without accepting a binding."""

    for name, value, expected in (
        ("request", request, GenesisRequest),
        ("proposal", proposal, RequirementProposal),
        ("coverage_approval", coverage_approval, RequirementCoverageApproval),
        ("report", report, FeatureRequirementReport),
        ("catalog", catalog, FeatureSupportCatalog),
        ("blueprint", blueprint, WorldBlueprint),
    ):
        if type(value) is not expected:
            _fail("INVALID_TYPE", f"$.{name}", expected=expected.__name__, actual=value, error_cls=BindingValidationError)
    _verify_v1a_lineage(request, proposal, coverage_approval, report, catalog, blueprint)
    try:
        validate_foundation_blueprint_facts(proposal, blueprint)
    except ArtifactValidationError as exc:
        _fail(exc.code, exc.path, message=str(exc), error_cls=BindingValidationError)
    item_by_id = {item.requirement_id: item for item in report.items}
    requirement_by_id = {item.requirement_id: item for item in proposal.requirements}
    if set(item_by_id) != set(requirement_by_id):
        _fail("REQUIREMENT_SET_MISMATCH", "$.report.items", message="Report items do not cover Proposal requirements", error_cls=BindingValidationError)
    selection = blueprint.pressure_selection
    result: list[CandidateBindingItem] = []
    for requirement in proposal.requirements:
        item = item_by_id[requirement.requirement_id]
        # Report warnings and rejections are always handled first.  Neither
        # can be laundered into a candidate binding by a plausible feature ID.
        if item.warnings:
            result.append(CandidateBindingItem(requirement.requirement_id, "UNBOUND_BLOCKING", None, "REPORT_ITEM_WARNING"))
            continue
        if item.support_status == "REJECTED":
            result.append(CandidateBindingItem(requirement.requirement_id, "UNBOUND_BLOCKING", None, "REPORT_ITEM_REJECTED"))
            continue
        if requirement.catalog_layer == "CONTENT":
            feature = catalog.get(item.bound_feature_ids[0]) if len(item.bound_feature_ids) == 1 else None
            if (
                item.support_status == "SUPPORTED"
                and item.catalog_layer == "CONTENT"
                and item.disposition == "BIND"
                and item.reason_code == "SUPPORTED"
                and len(item.bound_feature_ids) == 1
                and feature is not None
                and feature.layer == "CONTENT"
                and feature.player_bindable
                and feature.supported
            ):
                result.append(CandidateBindingItem(requirement.requirement_id, "CONTENT_ACCEPTED", feature.feature_id, "CONTENT_REPORT_SUPPORTED"))
            else:
                result.append(CandidateBindingItem(requirement.requirement_id, "UNBOUND_BLOCKING", None, "LINEAGE_MISMATCH"))
            continue
        if requirement.requirement_id in PRESSURE_REQUIREMENT_IDS:
            if (
                requirement.catalog_layer != "RUNTIME"
                or item.catalog_layer != "RUNTIME"
                or item.support_status != "UNSUPPORTED"
                or item.disposition != "BLOCK"
                or item.reason_code != "NO_MATCHING_RUNTIME_CONTRACT"
                or item.bound_feature_ids
            ):
                _fail("PRESSURE_SELECTION_MISMATCH", f"$.items.{requirement.requirement_id}", message="selected pressure requirement is not an honest unsupported candidate match", error_cls=BindingValidationError)
            result.append(CandidateBindingItem(requirement.requirement_id, "CANDIDATE_RUNTIME_MATCH", selection.feature_id, "REPORT_SUPPORT_PENDING"))
            continue
        if requirement.requirement_id in FOUNDATION_REQUIREMENT_IDS:
            if (
                requirement.catalog_layer != "RUNTIME"
                or item.catalog_layer != "RUNTIME"
                or item.support_status != "UNSUPPORTED"
                or item.disposition != "BLOCK"
                or item.reason_code != "NO_MATCHING_RUNTIME_CONTRACT"
                or item.bound_feature_ids
            ):
                _fail(
                    "FOUNDATION_SELECTION_MISMATCH",
                    f"$.items.{requirement.requirement_id}",
                    message="selected foundation requirement is not an honest unsupported candidate match",
                    error_cls=BindingValidationError,
                )
            result.append(CandidateBindingItem(requirement.requirement_id, "CANDIDATE_RUNTIME_MATCH", FOUNDATION_FEATURE_ID, "REPORT_SUPPORT_PENDING"))
            continue
        if requirement.acceptance_policy == "OPTIONAL" and item.support_status == "UNSUPPORTED" and item.disposition == "OMIT":
            result.append(CandidateBindingItem(requirement.requirement_id, "OMITTED_OPTIONAL", None, "OPTIONAL_REQUIREMENT_OMITTED"))
            continue
        result.append(CandidateBindingItem(requirement.requirement_id, "UNBOUND_BLOCKING", None, "NO_MATCHING_RUNTIME_CONTRACT"))
    return RuntimeBindingAssessment(
        assessment_schema_version=BINDING_SCHEMA_VERSION,
        source_request_hash=request.hash,
        source_proposal_hash=proposal.hash,
        source_approval_hash=coverage_approval.hash,
        source_report_hash=report.hash,
        source_catalog_version=catalog.version,
        source_catalog_hash=catalog.hash,
        blueprint_hash=blueprint.hash,
        items=result,
    )


def verify_runtime_binding_assessment(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    report: FeatureRequirementReport,
    catalog: FeatureSupportCatalog,
    blueprint: WorldBlueprint,
    assessment: RuntimeBindingAssessment,
) -> RuntimeBindingAssessment:
    """Recompute and verify a persisted bounded V1-C.2 binding assessment.

    Parsing an assessment is intentionally not an integrity proof.  This
    boundary re-verifies the Approval-bound Report, Blueprint lineage, and
    every derived item before returning the deterministic assessment.
    """

    for name, value, expected in (
        ("request", request, GenesisRequest),
        ("proposal", proposal, RequirementProposal),
        ("coverage_approval", coverage_approval, RequirementCoverageApproval),
        ("report", report, FeatureRequirementReport),
        ("catalog", catalog, FeatureSupportCatalog),
        ("blueprint", blueprint, WorldBlueprint),
        ("assessment", assessment, RuntimeBindingAssessment),
    ):
        if type(value) is not expected:
            _fail("INVALID_TYPE", f"$.{name}", expected=expected.__name__, actual=value, error_cls=BindingValidationError)
    try:
        verify_report(request, proposal, coverage_approval, catalog, report)
    except (GenesisValidationError, ValueError) as exc:
        _fail("REPORT_NOT_VERIFIED", "$.report", message="V1-A Report failed deterministic re-verification", error_cls=BindingValidationError)
    try:
        validate_blueprint_lineage(
            blueprint,
            request,
            proposal,
            coverage_approval,
            report,
            catalog,
            error_cls=BindingValidationError,
        )
    except ArtifactValidationError:
        raise
    expected = build_runtime_binding_assessment(request, proposal, coverage_approval, report, catalog, blueprint)
    try:
        assessment_matches = assessment.hash == expected.hash and assessment.to_dict() == expected.to_dict()
    except (ArtifactValidationError, TypeError, ValueError):
        assessment_matches = False
    if not assessment_matches:
        _fail(
            "BINDING_HASH_MISMATCH",
            "$.assessment",
            message="persisted RuntimeBindingAssessment differs from deterministic recomputation",
            error_cls=BindingValidationError,
        )
    return expected


# Explicit aliases keep the seam discoverable without creating a registry.
build_binding_assessment = build_runtime_binding_assessment
assess_runtime_bindings = build_runtime_binding_assessment


__all__ = [
    "BINDING_REASON_CODES",
    "BINDING_SCHEMA_VERSION",
    "BINDING_STATUSES",
    "BindingValidationError",
    "CandidateBindingItem",
    "RuntimeBindingAssessment",
    "assess_runtime_bindings",
    "build_binding_assessment",
    "build_runtime_binding_assessment",
    "verify_runtime_binding_assessment",
]
