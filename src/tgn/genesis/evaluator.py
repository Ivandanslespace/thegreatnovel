"""Pure deterministic Feature Requirement evaluator for Genesis V1-A."""

from __future__ import annotations

from .catalog import CATALOG_VERSION, DEFAULT_CATALOG, FeatureSupportCatalog
from .models import (
    FeatureRequirementReport,
    GenesisRequest,
    Requirement,
    RequirementCoverageApproval,
    RequirementProposal,
    RequirementReportItem,
    _fail,
)


def _check_artifact_types(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    catalog: FeatureSupportCatalog,
) -> None:
    if type(request) is not GenesisRequest:
        _fail("INVALID_TYPE", "$.request", expected="GenesisRequest", actual=request)
    if type(proposal) is not RequirementProposal:
        _fail("INVALID_TYPE", "$.proposal", expected="RequirementProposal", actual=proposal)
    if type(coverage_approval) is not RequirementCoverageApproval:
        _fail("INVALID_TYPE", "$.coverage_approval", expected="RequirementCoverageApproval", actual=coverage_approval)
    if type(catalog) is not FeatureSupportCatalog:
        _fail("INVALID_TYPE", "$.catalog", expected="FeatureSupportCatalog", actual=catalog)


def _validate_approval_hash(approval: RequirementCoverageApproval) -> None:
    # The approval stores the hash captured at construction.  Recomputing its
    # canonical payload detects object-level tampering without I/O or a store.
    expected = approval._payload_dict()  # noqa: SLF001 - boundary integrity check
    from .models import _hash_payload

    if approval.hash != _hash_payload(expected):
        _fail("APPROVAL_HASH_MISMATCH", "$.coverage_approval.approval_hash", message="approval canonical hash does not match payload")


def _validate_catalog_identity(catalog: FeatureSupportCatalog) -> None:
    if catalog.version != CATALOG_VERSION or catalog.hash != DEFAULT_CATALOG.hash:
        _fail(
            "CATALOG_IDENTITY_MISMATCH",
            "$.catalog",
            message="V1-A accepts only the canonical versioned Feature Support Catalog",
        )


def _validate_cross_artifacts(
    request: GenesisRequest,
    proposal: RequirementProposal,
    approval: RequirementCoverageApproval,
) -> None:
    if proposal.source_request_id != request.request_id:
        _fail("SOURCE_ID_MISMATCH", "$.proposal.source_request_id", message="proposal is bound to a different request")
    if proposal.source_request_hash != request.hash:
        _fail("REQUEST_HASH_MISMATCH", "$.proposal.source_request_hash", message="proposal request hash does not match request")
    if approval.source_request_id != request.request_id or approval.source_proposal_id != proposal.proposal_id:
        _fail("SOURCE_ID_MISMATCH", "$.coverage_approval", message="approval source identity does not match inputs")
    if approval.source_request_hash != request.hash:
        _fail("REQUEST_HASH_MISMATCH", "$.coverage_approval.source_request_hash", message="approval request hash does not match request")
    if approval.source_proposal_hash != proposal.hash:
        _fail("PROPOSAL_HASH_MISMATCH", "$.coverage_approval.source_proposal_hash", message="approval proposal hash does not match proposal")

    proposal_ids = tuple(item.requirement_id for item in proposal.requirements)
    approval_ids = tuple(item.requirement_id for item in approval.requirement_approvals)
    if proposal_ids != approval_ids:
        _fail(
            "REQUIREMENT_SET_MISMATCH",
            "$.coverage_approval.requirement_approvals",
            message="approval requirement IDs/order do not match proposal",
        )
    proposal_policies = tuple(item.acceptance_policy for item in proposal.requirements)
    approval_policies = tuple(item.acceptance_policy for item in approval.requirement_approvals)
    if proposal_policies != approval_policies:
        _fail(
            "ACCEPTANCE_POLICY_MISMATCH",
            "$.coverage_approval.requirement_approvals",
            message="approval acceptance policies do not match proposal",
        )


def _resolve_requirement(requirement: Requirement, catalog: FeatureSupportCatalog) -> tuple[str, str, tuple[str, ...], str]:
    """Return ``status, reason, bound_ids, effect`` for one requirement."""

    candidate_ids = requirement.candidate_feature_ids
    if not candidate_ids:
        return (
            "UNSUPPORTED",
            "NO_MATCHING_RUNTIME_CONTRACT" if requirement.catalog_layer == "RUNTIME" else "UNKNOWN_FEATURE_ID",
            (),
            "No catalog binding is available for this requirement.",
        )

    known = [catalog.get(feature_id) for feature_id in candidate_ids]
    known = [feature for feature in known if feature is not None]
    if not known:
        # An unimplemented Runtime mechanism is intentionally a stable,
        # non-throwing no-match result.  For a Content candidate, an unknown
        # ID is a structural rejection instead of a placeholder binding.
        if requirement.catalog_layer == "RUNTIME":
            return (
                "UNSUPPORTED",
                "NO_MATCHING_RUNTIME_CONTRACT",
                (),
                "No implemented Runtime contract matches this requirement.",
            )
        return (
            "REJECTED",
            "UNKNOWN_FEATURE_ID",
            (),
            "Candidate Feature ID is not present in the finite catalog.",
        )

    layer_matches = [feature for feature in known if feature.layer == requirement.catalog_layer and feature.player_bindable]
    if not layer_matches:
        return (
            "REJECTED",
            "CATALOG_LAYER_MISMATCH",
            (),
            "Candidate Feature ID is bound to a different catalog layer.",
        )
    supported_matches = [feature for feature in layer_matches if feature.supported]
    if not supported_matches:
        return (
            "UNSUPPORTED",
            "NO_MATCHING_RUNTIME_CONTRACT" if requirement.catalog_layer == "RUNTIME" else "UNKNOWN_FEATURE_ID",
            (),
            "The catalog entry is not supported by this contract version.",
        )
    selected = sorted(supported_matches, key=lambda feature: feature.feature_id)[0]
    return (
        "SUPPORTED",
        "SUPPORTED",
        (selected.feature_id,),
        f"Bound to catalog feature {selected.feature_id}.",
    )


def _item_for_requirement(requirement: Requirement, catalog: FeatureSupportCatalog) -> RequirementReportItem:
    status, reason, bound_ids, effect = _resolve_requirement(requirement, catalog)
    if requirement.warnings:
        reason = "UNRESOLVED_WARNING"
    if status == "SUPPORTED":
        disposition = "BIND"
        accepted_scope = {"feature_ids": list(bound_ids), "intent": requirement.normalized_intent}
        lost_capabilities: tuple[str, ...] = ()
        if requirement.catalog_layer == "CONTENT":
            effect = "expression only; no runtime mechanic"
    elif status == "REJECTED":
        disposition = "BLOCK"
        accepted_scope = {}
        lost_capabilities = (requirement.normalized_intent,)
    elif requirement.acceptance_policy == "OPTIONAL":
        disposition = "OMIT"
        accepted_scope = {}
        lost_capabilities = (requirement.normalized_intent,)
    else:
        disposition = "BLOCK"
        accepted_scope = {}
        lost_capabilities = (requirement.normalized_intent,)
    return RequirementReportItem(
        requirement_id=requirement.requirement_id,
        catalog_layer=requirement.catalog_layer,
        support_status=status,
        warnings=requirement.warnings,
        reason_code=reason,
        bound_feature_ids=bound_ids,
        accepted_scope=accepted_scope,
        lost_capabilities=lost_capabilities,
        player_visible_effect=effect,
        acknowledgement_required=False,
        disposition=disposition,
    )


def _gate_passes(items: tuple[RequirementReportItem, ...], catalog: FeatureSupportCatalog) -> bool:
    if any(item.disposition == "BLOCK" for item in items):
        return False
    if any(item.support_status == "REJECTED" for item in items):
        return False
    if any(item.warnings for item in items):
        return False
    if any(item.disposition == "BIND" and item.support_status != "SUPPORTED" for item in items):
        return False
    for item in items:
        for feature_id in item.bound_feature_ids:
            feature = catalog.get(feature_id)
            if feature is None or feature.layer != item.catalog_layer or not feature.player_bindable:
                return False
    return True


def evaluate(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    catalog: FeatureSupportCatalog,
) -> FeatureRequirementReport:
    """Evaluate a confirmed proposal against a finite catalog.

    This is intentionally a pure function: all inputs are immutable boundary
    artifacts, and the function performs no file, database, network, runtime,
    Campaign, GameState, Event, or provider operations.
    """

    _check_artifact_types(request, proposal, coverage_approval, catalog)
    _validate_approval_hash(coverage_approval)
    if coverage_approval.decision != "CONFIRMED":
        _fail(
            "APPROVAL_NOT_CONFIRMED",
            "$.coverage_approval.decision",
            expected="CONFIRMED",
            actual=coverage_approval.decision,
            message="Coverage Approval must be CONFIRMED before a Report is produced",
        )
    _validate_cross_artifacts(request, proposal, coverage_approval)
    _validate_catalog_identity(catalog)

    # Preserve Proposal canonical order.  No status counters or UI groupings
    # are stored; those remain deterministic projections from items[].
    items = tuple(_item_for_requirement(requirement, catalog) for requirement in proposal.requirements)
    return FeatureRequirementReport(
        report_schema_version=1,
        source_request_hash=request.hash,
        source_proposal_hash=proposal.hash,
        source_approval_hash=coverage_approval.hash,
        catalog_version=catalog.version,
        source_catalog_hash=catalog.hash,
        items=items,
        requirements_gate_passed=_gate_passes(items, catalog),
    )


def verify_report(
    request: GenesisRequest,
    proposal: RequirementProposal,
    coverage_approval: RequirementCoverageApproval,
    catalog: FeatureSupportCatalog,
    report: FeatureRequirementReport,
) -> FeatureRequirementReport:
    """Recompute and verify a persisted Report before any later phase uses it."""

    if type(report) is not FeatureRequirementReport:
        _fail("INVALID_TYPE", "$.report", expected="FeatureRequirementReport", actual=report)
    expected = evaluate(request, proposal, coverage_approval, catalog)
    if report.hash != expected.hash or report.to_dict() != expected.to_dict():
        _fail(
            "REPORT_MISMATCH",
            "$.report",
            message="persisted Report differs from deterministic evaluation of its source artifacts",
        )
    return report


__all__ = ["evaluate", "verify_report"]
