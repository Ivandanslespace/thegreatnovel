from __future__ import annotations

import copy
import builtins
import json
import socket
import sqlite3
import subprocess

import pytest

from tgn.genesis import (
    DEFAULT_CATALOG,
    CatalogFeature,
    FeatureRequirementReport,
    FeatureSupportCatalog,
    GenesisRequest,
    GenesisValidationError,
    Requirement,
    RequirementApproval,
    RequirementConstraint,
    RequirementCoverageApproval,
    RequirementProposal,
    RequirementReportItem,
    evaluate,
    verify_report,
)


def _request(constraints: list[str] | None = None) -> GenesisRequest:
    return GenesisRequest(
        schema_version=1,
        request_id="request-ocean-771305",
        raw_prompt="An ocean genesis prompt with a living creature and a dedicated resource.",
        genesis_seed=771305,
        content_locale="en-US",
        explicit_constraints=constraints or ["recorded-fixture"],
        generation_policy_reference="policy.genesis.v1",
    )


def _requirement(
    requirement_id: str,
    intent: str,
    policy: str,
    layer: str,
    candidates: list[str],
    *,
    warnings: list[str] | None = None,
) -> Requirement:
    kind = "CONTENT_EXPRESSION" if layer == "CONTENT" else "RUNTIME_SEMANTIC"
    normalized_intent = "world_premise" if layer == "CONTENT" else intent
    return Requirement(
        requirement_id=requirement_id,
        source_reference=f"prompt:{requirement_id}",
        normalized_intent=normalized_intent,
        requirement_kind=kind,
        acceptance_policy=policy,
        catalog_layer=layer,
        typed_constraints=[RequirementConstraint("constraint.fixture", "BOOLEAN", True, True)],
        candidate_feature_ids=candidates,
        warnings=warnings or [],
    )


def _artifacts(requirements: list[Requirement] | None = None, *, decision: str = "CONFIRMED"):
    request = _request()
    requirements = requirements or [
        _requirement("req.ocean", "ocean setting", "STRICT", "CONTENT", ["content.world_premise.v1"]),
        _requirement("req.xuanwu", "living creature runtime", "STRICT", "RUNTIME", ["runtime.xuanwu"]),
        _requirement("req.optional", "optional peers", "OPTIONAL", "RUNTIME", ["runtime.peers"]),
    ]
    proposal = RequirementProposal(
        proposal_schema_version=1,
        proposal_id="proposal-ocean-771305",
        source_request_id=request.request_id,
        source_request_hash=request.hash,
        requirements=requirements,
    )
    approval = RequirementCoverageApproval(
        approval_schema_version=1,
        approval_id="approval-ocean-771305",
        decision=decision,
        source_request_id=request.request_id,
        source_request_hash=request.hash,
        source_proposal_id=proposal.proposal_id,
        source_proposal_hash=proposal.hash,
        requirement_approvals=[RequirementApproval(item.requirement_id, item.acceptance_policy) for item in requirements],
    )
    return request, proposal, approval


def test_request_and_nested_values_are_canonical_and_detached():
    constraints = ["a", "b"]
    request = _request(constraints)
    constraints.append("mutated")
    assert request.explicit_constraints == ("a", "b")
    exported = request.to_dict()
    exported["explicit_constraints"].append("changed")
    assert request.explicit_constraints == ("a", "b")

    typed = ["one", "two"]
    requirement = Requirement(
        "req.one",
        "prompt:1",
        "world_premise",
        "CONTENT_EXPRESSION",
        "STRICT",
        "CONTENT",
        [RequirementConstraint("constraint.labels", "STRING_LIST", typed, True)],
        ["content.world_premise.v1"],
    )
    typed.append("mutated")
    assert requirement.typed_constraints[0].value == ("one", "two")
    assert requirement == Requirement.from_dict(requirement.to_dict())


def test_strict_schema_and_bounds_reject_unknown_or_invalid_values():
    data = _request().to_dict()
    data["unexpected"] = True
    with pytest.raises(GenesisValidationError) as error:
        GenesisRequest.from_dict(data)
    assert error.value.code == "UNKNOWN_FIELD"

    data = _request().to_dict()
    data["genesis_seed"] = True
    with pytest.raises(GenesisValidationError) as error:
        GenesisRequest.from_dict(data)
    assert error.value.code == "INVALID_TYPE"

    with pytest.raises(GenesisValidationError) as error:
        GenesisRequest(1, "request-a", "bad\x00prompt", 1, "en-US", [], "policy")
    assert error.value.code == "INVALID_VALUE"

    with pytest.raises(GenesisValidationError):
        RequirementConstraint("constraint.bad", "STRING", {"nested": True}, True)
    with pytest.raises(GenesisValidationError):
        RequirementConstraint("constraint.bad", "INTEGER", 1.5, True)

    malformed = _requirement("req.schema", "schema", "STRICT", "RUNTIME", []).to_dict()
    malformed["typed_constraints"] = {}
    with pytest.raises(GenesisValidationError) as error:
        Requirement.from_dict(malformed)
    assert error.value.code == "INVALID_TYPE"


def test_hash_is_stable_for_mapping_order_and_changes_for_identity_content():
    request_a = GenesisRequest(1, "request-a", "prompt", 1, "en-US", ["a"], "policy")
    request_b = GenesisRequest.from_dict(
        {
            "generation_policy_reference": "policy",
            "explicit_constraints": ["a"],
            "content_locale": "en-US",
            "genesis_seed": 1,
            "raw_prompt": "prompt",
            "request_id": "request-a",
            "schema_version": 1,
        }
    )
    assert request_a.hash == request_b.hash
    assert request_a.hash != GenesisRequest(1, "request-b", "prompt", 1, "en-US", ["a"], "policy").hash


def test_coverage_approval_is_a_report_input_and_cannot_be_cancelled():
    request, proposal, approval = _artifacts()
    assert approval.hash == RequirementCoverageApproval.from_dict(approval.to_dict()).hash
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    assert report.source_approval_hash == approval.hash

    request, proposal, cancelled = _artifacts(decision="CANCELLED")
    with pytest.raises(GenesisValidationError) as error:
        evaluate(request, proposal, cancelled, DEFAULT_CATALOG)
    assert error.value.code == "APPROVAL_NOT_CONFIRMED"


def test_cross_artifact_hash_and_requirement_policy_mismatch_are_stable_errors():
    request, proposal, approval = _artifacts()
    bad_proposal = RequirementProposal(
        1,
        proposal.proposal_id,
        proposal.source_request_id,
        "0" * 64,
        list(proposal.requirements),
    )
    with pytest.raises(GenesisValidationError) as error:
        evaluate(request, bad_proposal, approval, DEFAULT_CATALOG)
    assert error.value.code == "REQUEST_HASH_MISMATCH"

    changed = [
        _requirement("req.ocean", "ocean setting", "OPTIONAL", "CONTENT", ["content.world_premise.v1"]),
        _requirement("req.xuanwu", "living creature runtime", "STRICT", "RUNTIME", ["runtime.xuanwu"]),
        _requirement("req.optional", "optional peers", "OPTIONAL", "RUNTIME", ["runtime.peers"]),
    ]
    changed_proposal = RequirementProposal(1, proposal.proposal_id, request.request_id, request.hash, changed)
    changed_approval = RequirementCoverageApproval(
        1,
        approval.approval_id,
        "CONFIRMED",
        request.request_id,
        request.hash,
        changed_proposal.proposal_id,
        changed_proposal.hash,
        [RequirementApproval(item.requirement_id, "STRICT") for item in changed],
    )
    with pytest.raises(GenesisValidationError) as error:
        evaluate(request, changed_proposal, changed_approval, DEFAULT_CATALOG)
    assert error.value.code == "ACCEPTANCE_POLICY_MISMATCH"

    missing_approval = RequirementCoverageApproval(
        1,
        approval.approval_id,
        "CONFIRMED",
        request.request_id,
        request.hash,
        proposal.proposal_id,
        proposal.hash,
        [RequirementApproval(proposal.requirements[0].requirement_id, proposal.requirements[0].acceptance_policy)],
    )
    with pytest.raises(GenesisValidationError) as error:
        evaluate(request, proposal, missing_approval, DEFAULT_CATALOG)
    assert error.value.code == "REQUIREMENT_SET_MISMATCH"


def test_tampered_approval_hash_is_rejected_before_report():
    request, proposal, approval = _artifacts()
    tampered = approval.to_dict()
    tampered["approval_hash"] = "0" * 64
    with pytest.raises(GenesisValidationError) as error:
        RequirementCoverageApproval.from_dict(tampered)
    assert error.value.code == "APPROVAL_HASH_MISMATCH"


def test_evaluator_distinguishes_content_support_from_runtime_no_match():
    request, proposal, approval = _artifacts()
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    assert [item.requirement_id for item in report.items] == ["req.ocean", "req.xuanwu", "req.optional"]
    assert report.items[0].support_status == "SUPPORTED"
    assert report.items[0].disposition == "BIND"
    assert report.items[1].support_status == "UNSUPPORTED"
    assert report.items[1].reason_code == "NO_MATCHING_RUNTIME_CONTRACT"
    assert report.items[1].disposition == "BLOCK"
    assert report.items[2].disposition == "OMIT"
    assert report.requirements_gate_passed is False
    assert "DEGRADED" not in json.dumps(report.to_dict())
    assert "seal_allowed" not in report.to_dict()
    assert "status_counts" not in report.to_dict()


def test_report_requires_cross_artifact_verification_before_reuse():
    request, proposal, approval = _artifacts()
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    assert verify_report(request, proposal, approval, DEFAULT_CATALOG, report) == report

    forged = FeatureRequirementReport(
        1,
        report.source_request_hash,
        report.source_proposal_hash,
        report.source_approval_hash,
        report.catalog_version,
        [report.items[0]],
        True,
    )
    with pytest.raises(GenesisValidationError) as error:
        verify_report(request, proposal, approval, DEFAULT_CATALOG, forged)
    assert error.value.code == "REPORT_MISMATCH"

    fake_binding_item = RequirementReportItem(
        report.items[0].requirement_id,
        "CONTENT",
        "SUPPORTED",
        [],
        "SUPPORTED",
        ["content.not_in_catalog"],
        {},
        [],
        "fake binding",
        False,
        "BIND",
    )
    fake_binding_report = FeatureRequirementReport(
        1,
        report.source_request_hash,
        report.source_proposal_hash,
        report.source_approval_hash,
        report.catalog_version,
        [fake_binding_item, *report.items[1:]],
        False,
    )
    with pytest.raises(GenesisValidationError) as error:
        verify_report(request, proposal, approval, DEFAULT_CATALOG, fake_binding_report)
    assert error.value.code == "REPORT_MISMATCH"


def test_content_and_runtime_requirement_kinds_cannot_be_crossed():
    constraint = [RequirementConstraint("constraint.kind", "STRING", "value", True)]
    with pytest.raises(GenesisValidationError):
        Requirement(
            "req.mechanism",
            "prompt:1",
            "permanent deduction",
            "RUNTIME_SEMANTIC",
            "STRICT",
            "CONTENT",
            constraint,
            ["content.world_premise.v1"],
        )
    with pytest.raises(GenesisValidationError):
        Requirement(
            "req.runtime_content_id",
            "prompt:1",
            "world_premise",
            "RUNTIME_SEMANTIC",
            "OPTIONAL",
            "RUNTIME",
            constraint,
            [],
        )
    with pytest.raises(GenesisValidationError):
        Requirement(
            "req.alternatives",
            "prompt:1",
            "premise",
            "CONTENT_EXPRESSION",
            "STRICT",
            "CONTENT",
            constraint,
            ["content.world_premise.v1", "content.other"],
        )
    with pytest.raises(GenesisValidationError):
        Requirement(
            "req.misclassified",
            "prompt:1",
            "permanent_deduction",
            "CONTENT_EXPRESSION",
            "STRICT",
            "CONTENT",
            constraint,
            ["content.world_premise.v1"],
        )


def test_only_the_canonical_catalog_identity_is_accepted():
    custom_catalog = FeatureSupportCatalog.from_features(
        DEFAULT_CATALOG.version,
        DEFAULT_CATALOG.entries[:-1],
    )
    request, proposal, approval = _artifacts()
    with pytest.raises(GenesisValidationError) as error:
        evaluate(request, proposal, approval, custom_catalog)
    assert error.value.code == "CATALOG_IDENTITY_MISMATCH"


def test_degradable_unsupported_is_blocked_and_warning_blocks_gate():
    requirements = [
        _requirement("req.degradable", "dedicated resource runtime", "DEGRADABLE", "RUNTIME", ["runtime.resource"]),
    ]
    request, proposal, approval = _artifacts(requirements)
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    assert report.items[0].support_status == "UNSUPPORTED"
    assert report.items[0].disposition == "BLOCK"
    assert report.requirements_gate_passed is False

    requirements = [
        _requirement("req.content", "ocean setting", "STRICT", "CONTENT", ["content.world_premise.v1"], warnings=["manual confirmation pending"]),
    ]
    request, proposal, approval = _artifacts(requirements)
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    assert report.items[0].support_status == "SUPPORTED"
    assert report.items[0].warnings == ("manual confirmation pending",)
    assert report.items[0].reason_code == "UNRESOLVED_WARNING"
    assert report.requirements_gate_passed is False


def test_layer_and_unknown_feature_results_never_create_placeholder_support():
    layer_mismatch = [_requirement("req.kernel", "hash primitive", "STRICT", "RUNTIME", ["kernel.canonical_identity"])]
    request, proposal, approval = _artifacts(layer_mismatch)
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    assert report.items[0].support_status == "REJECTED"
    assert report.items[0].reason_code == "CATALOG_LAYER_MISMATCH"

    unknown_content = [_requirement("req.future", "future content", "OPTIONAL", "CONTENT", ["content.future_placeholder"])]
    request, proposal, approval = _artifacts(unknown_content)
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    assert report.items[0].support_status == "REJECTED"
    assert report.items[0].reason_code == "UNKNOWN_FEATURE_ID"


def test_fixture_covers_ocean_prompt_without_runtime_artifacts():
    names = [
        ("req.ocean", "ocean content", "STRICT", "CONTENT", ["content.world_premise.v1"]),
        ("req.mass_drop", "mass drop", "STRICT", "RUNTIME", ["runtime.mass_drop"]),
        ("req.peers", "peers", "OPTIONAL", "RUNTIME", ["runtime.peers"]),
        ("req.vehicle", "vehicle entity", "STRICT", "RUNTIME", ["runtime.vehicle"]),
        ("req.ownership", "vehicle ownership", "STRICT", "RUNTIME", ["runtime.ownership"]),
        ("req.creature", "unique living creature", "STRICT", "RUNTIME", ["runtime.creature"]),
        ("req.progression", "progression object", "STRICT", "RUNTIME", ["runtime.progression_object"]),
        ("req.exclusion", "normal-material exclusion", "STRICT", "RUNTIME", ["runtime.material_exclusion"]),
        ("req.resource", "exclusive resource", "STRICT", "RUNTIME", ["runtime.resource"]),
        ("req.deduction", "permanent deduction", "STRICT", "RUNTIME", ["runtime.deduction"]),
        ("req.other_vehicles", "other ordinary vehicles", "OPTIONAL", "RUNTIME", ["runtime.other_vehicles"]),
    ]
    requirements = [_requirement(*item) for item in names]
    request, proposal, approval = _artifacts(requirements)
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    supported = {item.requirement_id for item in report.items if item.support_status == "SUPPORTED"}
    assert supported == {"req.ocean"}
    assert all(item.catalog_layer != "RUNTIME" or not item.bound_feature_ids for item in report.items)
    assert report.requirements_gate_passed is False


def test_repeated_evaluation_is_deterministic_and_report_has_only_derived_items():
    request, proposal, approval = _artifacts()
    first = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    second = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    assert first.to_dict() == second.to_dict()
    assert first.hash == second.hash
    exported = copy.deepcopy(first.to_dict())
    exported["items"].reverse()
    assert [item.requirement_id for item in first.items] == ["req.ocean", "req.xuanwu", "req.optional"]
    assert FeatureRequirementReport.from_dict(first.to_dict()).hash == first.hash


def test_report_item_and_gate_invariants_reject_forged_success():
    with pytest.raises(GenesisValidationError):
        RequirementReportItem(
            "req.forged",
            "RUNTIME",
            "UNSUPPORTED",
            [],
            "NO_MATCHING_RUNTIME_CONTRACT",
            ["runtime.fake"],
            {},
            [],
            "not supported",
            False,
            "BIND",
        )

    supported_item = RequirementReportItem(
        "req.forged",
        "CONTENT",
        "SUPPORTED",
        [],
        "SUPPORTED",
        ["content.world_premise.v1"],
        {},
        [],
        "supported",
        False,
        "BIND",
    )
    blocked_item = RequirementReportItem(
        "req.blocked",
        "RUNTIME",
        "UNSUPPORTED",
        [],
        "NO_MATCHING_RUNTIME_CONTRACT",
        [],
        {},
        ["runtime mechanism"],
        "blocked",
        False,
        "BLOCK",
    )
    with pytest.raises(GenesisValidationError):
        FeatureRequirementReport(1, "0" * 64, "1" * 64, "2" * 64, "v1", [blocked_item], True)
    report = FeatureRequirementReport(1, "0" * 64, "1" * 64, "2" * 64, "v1", [supported_item], True)
    assert report.requirements_gate_passed is True


def test_evaluator_has_no_file_database_network_or_process_side_effects(monkeypatch):
    request, proposal, approval = _artifacts()

    def forbidden(*args, **kwargs):
        raise AssertionError("V1-A evaluator attempted a side effect")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    before = proposal.to_dict()
    result = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    assert result.source_approval_hash == approval.hash
    assert proposal.to_dict() == before


def test_json_snapshots_reject_depth_and_cycles_with_stable_errors():
    deep: dict[str, object] = {}
    cursor = deep
    for _ in range(40):
        child: dict[str, object] = {}
        cursor["child"] = child
        cursor = child
    with pytest.raises(GenesisValidationError) as error:
        RequirementReportItem(
            "req.deep",
            "CONTENT",
            "SUPPORTED",
            [],
            "SUPPORTED",
            ["content.world_premise.v1"],
            deep,
            [],
            "deep",
            False,
            "BIND",
        )
    assert error.value.code == "INVALID_VALUE"

    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(GenesisValidationError) as error:
        RequirementReportItem(
            "req.cycle",
            "CONTENT",
            "SUPPORTED",
            [],
            "SUPPORTED",
            ["content.world_premise.v1"],
            cyclic,
            [],
            "cycle",
            False,
            "BIND",
        )
    assert error.value.code == "INVALID_VALUE"


def test_catalog_rejects_unregistered_runtime_and_supports_only_finite_members():
    with pytest.raises(GenesisValidationError):
        CatalogFeature("runtime.xuanwu", "RUNTIME", evidence=("fake",))
    with pytest.raises(GenesisValidationError):
        CatalogFeature("runtime.fake", "RUNTIME", evidence=("free text is not a contract",))
    assert {item.layer for item in DEFAULT_CATALOG.entries} == {"CONTENT", "KERNEL", "LEGACY"}
    assert all(item.player_bindable for item in DEFAULT_CATALOG.entries if item.layer == "CONTENT")
