from __future__ import annotations

import builtins
from dataclasses import replace
import socket
import sqlite3
import subprocess

import pytest

from tgn.genesis import (
    BindingValidationError,
    BLUEPRINT_DURABILITY_TIERS,
    BlueprintPressureSelection,
    BlueprintRequirementFact,
    BlueprintValidationError,
    CANDIDATE_DURABLE,
    CandidateGenesisAttempt,
    CandidateBindingItem,
    CandidatePressureComponent,
    CandidateWorldDraft,
    CandidateValidationError,
    DEFAULT_CATALOG,
    ExclusiveUpgradePressureConfig,
    FeatureRequirementReport,
    GenesisRequest,
    PENDING_GATES,
    PRESSURE_CONTRACT_VERSION,
    PRESSURE_FEATURE_ID,
    FOUNDATION_FEATURE_ID,
    FOUNDATION_REQUIREMENT_IDS,
    FoundationCandidateComponent,
    build_foundation_candidate,
    verify_foundation_candidate,
    Requirement,
    RequirementApproval,
    RequirementConstraint,
    RequirementCoverageApproval,
    RequirementProposal,
    WorldBlueprint,
    build_runtime_binding_assessment,
    compile_candidate_artifacts,
    compile_candidate_attempt,
    evaluate,
    require_materializable_candidate,
    verify_candidate_artifacts,
    verify_runtime_binding_assessment,
)


OCEAN_PROMPT = """全民投放海洋世界。
只有主角的初始载具是活体玄武；
其他投放者拥有不同类型的普通载具。
玄武升级不消耗木材、金属等普通建造材料，
只消耗会被永久扣除的专属资源“能量晶石”。"""


def _requirement(
    requirement_id: str,
    intent: str,
    policy: str,
    layer: str,
    candidates: list[str],
    *,
    source_reference: str,
    requirement_kind: str,
    typed_constraints: list[RequirementConstraint] | None = None,
) -> Requirement:
    return Requirement(
        requirement_id=requirement_id,
        source_reference=source_reference,
        normalized_intent=intent,
        requirement_kind=requirement_kind,
        acceptance_policy=policy,
        catalog_layer=layer,
        typed_constraints=typed_constraints or [RequirementConstraint("constraint.fixture", "EQUALS", True, True)],
        candidate_feature_ids=candidates,
    )


def _fixture() -> tuple[GenesisRequest, RequirementProposal, RequirementCoverageApproval, FeatureRequirementReport, WorldBlueprint, ExclusiveUpgradePressureConfig]:
    request = GenesisRequest(
        1,
        "request-ocean-771305",
        OCEAN_PROMPT,
        771305,
        "zh-CN",
        ["recorded-fixture"],
        "policy.genesis.v1",
    )
    requirements = [
        _requirement("req.ocean", "全民投放海洋世界的公开题材与审美前提", "STRICT", "CONTENT", ["content.world_premise.v1"], source_reference="prompt:line-1", requirement_kind="CONTENT_EXPRESSION", typed_constraints=[RequirementConstraint("constraint.ocean", "EQUALS", "海洋世界", True)]),
        _requirement("req.mass_drop", "全民投放的公开系统机制", "STRICT", "RUNTIME", ["runtime.mass_drop"], source_reference="prompt:line-1", requirement_kind="PUBLIC_SYSTEM", typed_constraints=[
            RequirementConstraint("constraint.launch_system", "EQUALS", "system.public_mass_drop", True),
            RequirementConstraint("constraint.initial_cohort", "EQUALS", "cohort.initial", True),
            RequirementConstraint("constraint.cohort_scope", "EQUALS", "bounded_initial_cohort", True),
        ]),
        _requirement("req.peers", "其他投放者作为可区分的同场实体", "STRICT", "RUNTIME", ["runtime.peers"], source_reference="prompt:line-3", requirement_kind="ENTITY_MODEL", typed_constraints=[
            RequirementConstraint("constraint.cohort", "EQUALS", "cohort.initial", True),
            RequirementConstraint("constraint.actor_ids", "EQUALS", ("actor.protagonist", "actor.peer.1", "actor.peer.2"), True),
            RequirementConstraint("constraint.role_map", "EQUALS", ("actor.protagonist=PROTAGONIST", "actor.peer.1=PEER", "actor.peer.2=PEER"), True),
        ]),
        _requirement("req.vehicle", "投放者拥有载具实体", "STRICT", "RUNTIME", ["runtime.vehicle"], source_reference="prompt:line-2,line-3", requirement_kind="ENTITY_MODEL", typed_constraints=[
            RequirementConstraint("constraint.cohort", "EQUALS", "cohort.initial", True),
            RequirementConstraint("constraint.vehicle_ids", "EQUALS", ("vehicle.protagonist", "vehicle.peer.1", "vehicle.peer.2"), True),
        ]),
        _requirement("req.ownership", "载具所有权绑定到对应投放者", "STRICT", "RUNTIME", ["runtime.ownership"], source_reference="prompt:line-2,line-3", requirement_kind="EXCLUSIVITY", typed_constraints=[
            RequirementConstraint("constraint.actor_vehicle_pairs", "OWNERSHIP", ("actor.protagonist->vehicle.protagonist", "actor.peer.1->vehicle.peer.1", "actor.peer.2->vehicle.peer.2"), True),
            RequirementConstraint("constraint.bijective", "EQUALS", True, True),
        ]),
        _requirement("req.creature", "主角独有活体玄武作为初始载具", "STRICT", "RUNTIME", ["runtime.living_xuanwu"], source_reference="prompt:line-2", requirement_kind="PROTAGONIST_CONSTRAINT", typed_constraints=[
            RequirementConstraint("constraint.owner", "EQUALS", "actor.protagonist", True),
            RequirementConstraint("constraint.vehicle", "EQUALS", "vehicle.protagonist", True),
            RequirementConstraint("constraint.vehicle_kind", "EQUALS", "vehicle.kind.living_xuanwu", True),
            RequirementConstraint("constraint.living", "EQUALS", True, True),
            RequirementConstraint("constraint.growth_object", "EQUALS", True, True),
            RequirementConstraint("constraint.unique_in_cohort", "EQUALS", True, True),
        ]),
        _requirement("req.progression", "玄武作为可升级的成长对象", "STRICT", "RUNTIME", ["runtime.progression_object"], source_reference="prompt:line-4", requirement_kind="PROGRESSION_RULE"),
        _requirement("req.exclusion", "玄武升级排除木材和金属普通材料", "STRICT", "RUNTIME", ["runtime.material_exclusion"], source_reference="prompt:line-4", requirement_kind="PROGRESSION_RULE", typed_constraints=[RequirementConstraint("constraint.excludes", "EXCLUDES", ["木材", "金属"], True)]),
        _requirement("req.resource", "升级消耗专属资源能量晶石", "STRICT", "RUNTIME", ["runtime.energy_crystal"], source_reference="prompt:line-5", requirement_kind="RESOURCE_ECONOMY", typed_constraints=[RequirementConstraint("constraint.resource", "RESOURCE_COST", "能量晶石", True)]),
        _requirement("req.deduction", "能量晶石在升级时被永久扣除", "STRICT", "RUNTIME", ["runtime.permanent_deduction"], source_reference="prompt:line-5", requirement_kind="RESOURCE_ECONOMY", typed_constraints=[RequirementConstraint("constraint.deduction", "LIMIT", "永久扣除", True)]),
        _requirement("req.other_vehicles", "其他投放者拥有普通载具", "STRICT", "RUNTIME", ["runtime.other_vehicles"], source_reference="prompt:line-3", requirement_kind="EXCLUSIVITY", typed_constraints=[
            RequirementConstraint("constraint.vehicle_ids", "EQUALS", ("vehicle.peer.1", "vehicle.peer.2"), True),
            RequirementConstraint("constraint.owner_ids", "EQUALS", ("actor.peer.1", "actor.peer.2"), True),
            RequirementConstraint("constraint.vehicle_kinds", "EQUALS", ("vehicle.kind.peer_skiff", "vehicle.kind.peer_submersible"), True),
            RequirementConstraint("constraint.living", "EQUALS", False, True),
            RequirementConstraint("constraint.growth_object", "EQUALS", False, True),
            RequirementConstraint("constraint.distinct_ordinary_kinds", "EQUALS", True, True),
        ]),
    ]
    proposal = RequirementProposal(1, "proposal-ocean-771305", request.request_id, request.hash, requirements)
    approval = RequirementCoverageApproval(
        1,
        "approval-ocean-771305",
        "CONFIRMED",
        request.request_id,
        request.hash,
        proposal.proposal_id,
        proposal.hash,
        [RequirementApproval(item.requirement_id, item.acceptance_policy) for item in requirements],
    )
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    selection = BlueprintPressureSelection(
        "actor.protagonist",
        "vehicle.protagonist",
        "actor.protagonist",
        "resource.energy_crystal",
        ["resource.wood", "resource.metal"],
        PRESSURE_FEATURE_ID,
        PRESSURE_CONTRACT_VERSION,
        ["req.progression", "req.exclusion", "req.resource", "req.deduction"],
    )
    fact_kinds = [
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
    ]
    foundation_identity = {
        "req.mass_drop": (("system.public_mass_drop",), ("cohort.initial",)),
        "req.peers": (("cohort.initial",), ("actor.protagonist", "actor.peer.1", "actor.peer.2")),
        "req.vehicle": (("cohort.initial",), ("vehicle.protagonist", "vehicle.peer.1", "vehicle.peer.2")),
        "req.ownership": (("actor.protagonist", "actor.peer.1", "actor.peer.2"), ("vehicle.protagonist", "vehicle.peer.1", "vehicle.peer.2")),
        "req.creature": (("actor.protagonist",), ("vehicle.protagonist",)),
        "req.other_vehicles": (("actor.peer.1", "actor.peer.2"), ("vehicle.peer.1", "vehicle.peer.2")),
    }
    facts = []
    for index, item in enumerate(requirements):
        subjects, objects = foundation_identity.get(item.requirement_id, ((), ()))
        facts.append(
            BlueprintRequirementFact(
                item.requirement_id,
                item.source_reference,
                item.normalized_intent,
                fact_kinds[index],
                subject_ids=subjects,
                object_ids=objects,
                typed_constraints=item.typed_constraints,
            )
        )
    blueprint = WorldBlueprint(
        1,
        "blueprint-ocean-771305",
        request.request_id,
        request.hash,
        proposal.proposal_id,
        proposal.hash,
        approval.hash,
        report.hash,
        DEFAULT_CATALOG.version,
        DEFAULT_CATALOG.hash,
        request.genesis_seed,
        request.content_locale,
        facts,
        selection,
        request.generation_policy_reference,
    )
    pressure_config = ExclusiveUpgradePressureConfig(
        protagonist_id="actor.protagonist",
        growth_object_id="vehicle.protagonist",
        growth_object_owner_id="actor.protagonist",
        exclusive_resource_id="resource.energy_crystal",
    )
    return request, proposal, approval, report, blueprint, pressure_config


def _variant_fixture(
    requirement_id: str,
    *,
    warnings: list[str] | None = None,
    candidate_feature_ids: list[str] | None = None,
    typed_constraints: list[RequirementConstraint] | None = None,
    requirement_kind: str | None = None,
) -> tuple[GenesisRequest, RequirementProposal, RequirementCoverageApproval, FeatureRequirementReport, WorldBlueprint, ExclusiveUpgradePressureConfig]:
    """Rebuild the recorded fixture through V1-A so the Report remains valid."""

    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    proposal_data = proposal.to_dict()
    target = next(item for item in proposal_data["requirements"] if item["requirement_id"] == requirement_id)
    if warnings is not None:
        target["warnings"] = warnings
    if candidate_feature_ids is not None:
        target["candidate_feature_ids"] = candidate_feature_ids
    if typed_constraints is not None:
        target["typed_constraints"] = [constraint.to_dict() for constraint in typed_constraints]
    if requirement_kind is not None:
        target["requirement_kind"] = requirement_kind
    proposal = RequirementProposal.from_dict(proposal_data)
    approval = RequirementCoverageApproval(
        1,
        f"approval-{requirement_id}-variant",
        "CONFIRMED",
        request.request_id,
        request.hash,
        proposal.proposal_id,
        proposal.hash,
        [RequirementApproval(item.requirement_id, item.acceptance_policy) for item in proposal.requirements],
    )
    report = evaluate(request, proposal, approval, DEFAULT_CATALOG)
    blueprint_data = blueprint.to_dict()
    blueprint_data["source_proposal_hash"] = proposal.hash
    blueprint_data["source_approval_hash"] = approval.hash
    blueprint_data["source_report_hash"] = report.hash
    if typed_constraints is not None:
        blueprint_target = next(item for item in blueprint_data["facts"] if item["requirement_id"] == requirement_id)
        blueprint_target["typed_constraints"] = [constraint.to_dict() for constraint in typed_constraints]
    blueprint = WorldBlueprint.from_dict(blueprint_data)
    return request, proposal, approval, report, blueprint, pressure_config


def test_recorded_fixture_builds_only_candidate_and_blocked_artifacts():
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    attempt = compile_candidate_attempt(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)
    draft, bundled_attempt = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)

    assert len(blueprint.facts) == 11
    assert [fact.requirement_id for fact in blueprint.facts] == [item.requirement_id for item in proposal.requirements]
    assert {fact.durability_tier for fact in blueprint.facts} == BLUEPRINT_DURABILITY_TIERS
    assert assessment.status_counts == {
        "CANDIDATE_RUNTIME_MATCH": 10,
        "CONTENT_ACCEPTED": 1,
        "OMITTED_OPTIONAL": 0,
        "UNBOUND_BLOCKING": 0,
    }
    assert assessment.binding_gate_passed is False
    assert report.requirements_gate_passed is False
    assert attempt.attempt_status == "BLOCKED_REQUIREMENTS"
    assert draft.world_semantic_candidate_hash
    assert bundled_attempt.candidate_world_draft_hash == draft.hash
    assert attempt.required_pending_gates == PENDING_GATES
    assert all(field not in attempt.to_dict() for field in {"seal_allowed", "campaign_id", "publication", "passed_preflight", "freeze_identity"})
    with pytest.raises(CandidateValidationError) as error:
        require_materializable_candidate(attempt)
    assert error.value.code == "REQUIREMENTS_GATE_BLOCKED"


def test_candidate_artifacts_are_canonical_strict_and_detached():
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    draft, attempt = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)
    assert CandidateGenesisAttempt.from_dict(attempt.to_dict()).hash == attempt.hash
    exported = blueprint.to_dict()
    exported["facts"][0]["labels"].append("mutated")
    exported["pressure_selection"]["requirement_ids"].reverse()
    assert "mutated" not in blueprint.facts[0].labels
    assert blueprint.pressure_selection.requirement_ids == ("req.progression", "req.exclusion", "req.resource", "req.deduction")

    forged = blueprint.to_dict()
    forged["facts"][0]["durability_tier"] = "AUTHORITATIVE_DURABLE"
    with pytest.raises(BlueprintValidationError) as error:
        WorldBlueprint.from_dict(forged)
    assert error.value.code == "INVALID_FACT_TIER"

    forged = attempt.to_dict()
    forged["candidate_world_draft_hash"] = "0" * 64
    parsed_forgery = CandidateGenesisAttempt.from_dict(forged)
    assert parsed_forgery.candidate_world_draft_hash == "0" * 64
    assert parsed_forgery.hash != attempt.hash
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request,
            proposal,
            approval,
            report,
            DEFAULT_CATALOG,
            blueprint,
            pressure_config,
            assessment,
            draft,
            parsed_forgery,
        )
    assert error.value.code == "CANDIDATE_HASH_MISMATCH"


def test_lineage_pressure_and_binding_honesty_fail_stably():
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    bad_blueprint = blueprint.to_dict()
    bad_blueprint["source_report_hash"] = "0" * 64
    bad_blueprint = WorldBlueprint.from_dict(bad_blueprint)
    with pytest.raises(CandidateValidationError) as error:
        compile_candidate_attempt(request, proposal, approval, report, DEFAULT_CATALOG, bad_blueprint, pressure_config)
    assert error.value.code == "LINEAGE_MISMATCH"

    bad_config = ExclusiveUpgradePressureConfig(
        protagonist_id="actor.protagonist",
        growth_object_id="growth.object",
        growth_object_owner_id="actor.protagonist",
        exclusive_resource_id="resource.energy_crystal",
    )
    with pytest.raises(CandidateValidationError) as error:
        compile_candidate_attempt(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, bad_config)
    assert error.value.code == "PRESSURE_SELECTION_MISMATCH"

    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    forged = assessment.to_dict()
    forged["binding_gate_passed"] = True
    with pytest.raises(BindingValidationError) as error:
        assessment.__class__.from_dict(forged)
    assert error.value.code == "BINDING_HASH_MISMATCH"


def test_candidate_lineage_and_gate_identity_are_not_mutable_shortcuts():
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    forged = blueprint.to_dict()
    forged["facts"][7]["typed_constraints"][0]["value"] = ["木材"]
    with pytest.raises(CandidateValidationError) as error:
        compile_candidate_attempt(
            request,
            proposal,
            approval,
            report,
            DEFAULT_CATALOG,
            WorldBlueprint.from_dict(forged),
            pressure_config,
        )
    assert error.value.code == "LINEAGE_MISMATCH"

    with pytest.raises(CandidateValidationError) as error:
        CandidateGenesisAttempt(
            1,
            "attempt-test",
            request.hash,
            proposal.hash,
            approval.hash,
            report.hash,
            DEFAULT_CATALOG.version,
            DEFAULT_CATALOG.hash,
            blueprint.hash,
            "0" * 64,
            "1" * 64,
            "other.compiler",
            1,
            PENDING_GATES,
            "BLOCKED_REQUIREMENTS",
        )
    assert error.value.code == "INVALID_VALUE"

    with pytest.raises(CandidateValidationError) as error:
        CandidateGenesisAttempt(
            1,
            "attempt-test",
            request.hash,
            proposal.hash,
            approval.hash,
            report.hash,
            DEFAULT_CATALOG.version,
            DEFAULT_CATALOG.hash,
            blueprint.hash,
            "0" * 64,
            "1" * 64,
            "genesis.v1c_candidate_compiler",
            2,
            (),
            "READY_FOR_FUTURE_PREFLIGHT",
        )
    assert error.value.code == "REQUIREMENTS_GATE_BLOCKED"


def test_strict_unknown_fields_and_side_effect_boundary(monkeypatch):
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    malformed = blueprint.to_dict()
    malformed["unexpected"] = True
    with pytest.raises(BlueprintValidationError) as error:
        WorldBlueprint.from_dict(malformed)
    assert error.value.code == "UNKNOWN_FIELD"

    def forbidden(*args, **kwargs):
        raise AssertionError("candidate compiler attempted an external side effect")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    attempt = compile_candidate_attempt(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)
    assert attempt.attempt_status == "BLOCKED_REQUIREMENTS"
    assert not any(feature.layer == "RUNTIME" for feature in DEFAULT_CATALOG.entries)


@pytest.mark.parametrize(
    ("field", "value"),
    (("genesis_seed", 771306), ("content_locale", "en-US"), ("generation_policy_reference", "policy.other")),
)
def test_blueprint_lineage_binds_request_seed_locale_and_policy(field, value):
    request, proposal, approval, report, blueprint, _pressure_config = _fixture()
    forged = blueprint.to_dict()
    forged[field] = value
    with pytest.raises(BlueprintValidationError) as error:
        from tgn.genesis import validate_blueprint_lineage

        validate_blueprint_lineage(
            WorldBlueprint.from_dict(forged), request, proposal, approval, report, DEFAULT_CATALOG
        )
    assert error.value.code == "LINEAGE_MISMATCH"


def test_blueprint_lineage_rejects_all_request_generation_fields_together_without_hash_change():
    request, proposal, approval, report, blueprint, _pressure_config = _fixture()
    forged = blueprint.to_dict()
    forged["genesis_seed"] = 771306
    forged["content_locale"] = "en-US"
    forged["generation_policy_reference"] = "policy.other"
    assert forged["source_request_hash"] == request.hash
    with pytest.raises(BlueprintValidationError) as error:
        from tgn.genesis import validate_blueprint_lineage

        validate_blueprint_lineage(
            WorldBlueprint.from_dict(forged), request, proposal, approval, report, DEFAULT_CATALOG
        )
    assert error.value.code == "LINEAGE_MISMATCH"


def test_persisted_assessment_is_recomputed_not_trusted_from_its_hash():
    request, proposal, approval, report, blueprint, _pressure_config = _fixture()
    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    assert verify_runtime_binding_assessment(
        request, proposal, approval, report, DEFAULT_CATALOG, blueprint, assessment
    ).to_dict() == assessment.to_dict()

    def assert_forged(data):
        forged = assessment.__class__.from_dict(data)
        with pytest.raises(BindingValidationError) as error:
            verify_runtime_binding_assessment(
                request, proposal, approval, report, DEFAULT_CATALOG, blueprint, forged
            )
        assert error.value.code == "BINDING_HASH_MISMATCH"

    changed_item = assessment.to_dict()
    changed_item["items"][0]["status"] = "UNBOUND_BLOCKING"
    changed_item["items"][0]["candidate_feature_id"] = None
    changed_item["items"][0]["reason_code"] = "NO_MATCHING_RUNTIME_CONTRACT"
    assert_forged(changed_item)

    reordered = assessment.to_dict()
    reordered["items"] = list(reversed(reordered["items"]))
    assert_forged(reordered)

    omitted = assessment.to_dict()
    omitted["items"] = omitted["items"][:-1]
    assert_forged(omitted)

    added = assessment.to_dict()
    added["items"].append(
        CandidateBindingItem("req.extra", "UNBOUND_BLOCKING", None, "NO_MATCHING_RUNTIME_CONTRACT").to_dict()
    )
    assert_forged(added)

    gate_tampered = assessment
    object.__setattr__(gate_tampered, "binding_gate_passed", True)
    with pytest.raises(BindingValidationError) as error:
        verify_runtime_binding_assessment(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint, gate_tampered
        )
    assert error.value.code == "BINDING_HASH_MISMATCH"
    object.__setattr__(gate_tampered, "binding_gate_passed", False)

    lineage_tampered = assessment.to_dict()
    lineage_tampered["source_request_hash"] = "0" * 64
    assert_forged(lineage_tampered)


def test_candidate_artifact_verifier_rejects_cross_artifact_and_recomputed_forgery():
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    draft, attempt = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)
    verified_assessment, verified_draft, verified_attempt = verify_candidate_artifacts(
        request,
        proposal,
        approval,
        report,
        DEFAULT_CATALOG,
        blueprint,
        pressure_config,
        assessment,
        draft,
        attempt,
    )
    assert verified_assessment.to_dict() == assessment.to_dict()
    assert verified_draft.to_dict() == draft.to_dict()
    assert verified_attempt.to_dict() == attempt.to_dict()

    forged_draft_data = draft.to_dict()
    forged_draft_data["binding_assessment_hash"] = "0" * 64
    with pytest.raises(CandidateValidationError) as error:
        CandidateWorldDraft.from_dict(forged_draft_data)
    assert error.value.code in {"BINDING_HASH_MISMATCH", "CANDIDATE_HASH_MISMATCH"}

    forged_attempt_data = attempt.to_dict()
    forged_attempt_data["candidate_world_draft_hash"] = "0" * 64
    forged_attempt = CandidateGenesisAttempt.from_dict(forged_attempt_data)
    assert forged_attempt.hash
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request,
            proposal,
            approval,
            report,
            DEFAULT_CATALOG,
            blueprint,
            pressure_config,
            assessment,
            draft,
            forged_attempt,
        )
    assert error.value.code == "CANDIDATE_HASH_MISMATCH"

    blueprint_b_data = blueprint.to_dict()
    blueprint_b_data["blueprint_id"] = "blueprint-ocean-cross"
    blueprint_b = WorldBlueprint.from_dict(blueprint_b_data)
    assessment_b = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint_b)
    draft_b, attempt_b = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, blueprint_b, pressure_config)
    with pytest.raises(BindingValidationError) as error:
        verify_candidate_artifacts(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint_b, pressure_config,
            assessment, draft_b, attempt_b,
        )
    assert error.value.code == "BINDING_HASH_MISMATCH"
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint_b, pressure_config,
            assessment_b, draft, attempt,
        )
    assert error.value.code == "FOUNDATION_HASH_MISMATCH"

    changed_config = replace(pressure_config, upgrade_stamina_cost=pressure_config.upgrade_stamina_cost + 1)
    draft_config_b, attempt_config_b = compile_candidate_artifacts(
        request, proposal, approval, report, DEFAULT_CATALOG, blueprint, changed_config
    )
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config,
            assessment, draft_config_b, attempt_config_b,
        )
    assert error.value.code == "CANDIDATE_HASH_MISMATCH"

    altered_pressure = CandidatePressureComponent(
        feature_id=draft.pressure_component.feature_id,
        contract_version=draft.pressure_component.contract_version,
        pressure_config=draft.pressure_component.pressure_config,
        initial_state=draft.pressure_component.initial_state,
        source_pressure_selection_hash="0" * 64,
        candidate_binding_assessment_hash=assessment.hash,
    )
    altered_draft = CandidateWorldDraft(
        draft_schema_version=draft.draft_schema_version,
        draft_id=draft.draft_id,
        blueprint_hash=draft.blueprint_hash,
        binding_assessment_hash=draft.binding_assessment_hash,
        candidate_facts=draft.candidate_facts,
        pressure_component=altered_pressure,
        candidate_initial_component=draft.candidate_initial_component,
        foundation_component=draft.foundation_component,
    )
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config,
            assessment, altered_draft, attempt,
        )
    assert error.value.code == "CANDIDATE_HASH_MISMATCH"

    altered_assessment_pressure = CandidatePressureComponent(
        feature_id=draft.pressure_component.feature_id,
        contract_version=draft.pressure_component.contract_version,
        pressure_config=draft.pressure_component.pressure_config,
        initial_state=draft.pressure_component.initial_state,
        source_pressure_selection_hash=draft.pressure_component.source_pressure_selection_hash,
        candidate_binding_assessment_hash="0" * 64,
    )
    altered_assessment_draft = CandidateWorldDraft(
        draft_schema_version=draft.draft_schema_version,
        draft_id=draft.draft_id,
        blueprint_hash=draft.blueprint_hash,
        binding_assessment_hash="0" * 64,
        candidate_facts=draft.candidate_facts,
        pressure_component=altered_assessment_pressure,
        candidate_initial_component=draft.candidate_initial_component,
        foundation_component=draft.foundation_component,
    )
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config,
            assessment, altered_assessment_draft, attempt,
        )
    assert error.value.code == "CANDIDATE_HASH_MISMATCH"

    reordered_facts = list(draft.candidate_facts)
    reordered_facts.reverse()
    reordered_draft = CandidateWorldDraft(
        draft_schema_version=draft.draft_schema_version,
        draft_id=draft.draft_id,
        blueprint_hash=draft.blueprint_hash,
        binding_assessment_hash=draft.binding_assessment_hash,
        candidate_facts=reordered_facts,
        pressure_component=draft.pressure_component,
        candidate_initial_component=draft.candidate_initial_component,
        foundation_component=draft.foundation_component,
    )
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config,
            assessment, reordered_draft, attempt,
        )
    assert error.value.code == "CANDIDATE_HASH_MISMATCH"

    deleted_draft = CandidateWorldDraft(
        draft_schema_version=draft.draft_schema_version,
        draft_id=draft.draft_id,
        blueprint_hash=draft.blueprint_hash,
        binding_assessment_hash=draft.binding_assessment_hash,
        candidate_facts=list(draft.candidate_facts)[:-1],
        pressure_component=draft.pressure_component,
        candidate_initial_component=draft.candidate_initial_component,
        foundation_component=draft.foundation_component,
    )
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config,
            assessment, deleted_draft, attempt,
        )
    assert error.value.code == "CANDIDATE_HASH_MISMATCH"

    replaced_fact_data = draft.candidate_facts[0].to_dict()
    replaced_fact_data["labels"] = ["attacker-replaced-fact"]
    replaced_draft = CandidateWorldDraft(
        draft_schema_version=draft.draft_schema_version,
        draft_id=draft.draft_id,
        blueprint_hash=draft.blueprint_hash,
        binding_assessment_hash=draft.binding_assessment_hash,
        candidate_facts=[BlueprintRequirementFact.from_dict(replaced_fact_data), *draft.candidate_facts[1:]],
        pressure_component=draft.pressure_component,
        candidate_initial_component=draft.candidate_initial_component,
        foundation_component=draft.foundation_component,
    )
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config,
            assessment, replaced_draft, attempt,
        )
    assert error.value.code == "CANDIDATE_HASH_MISMATCH"

    ready_data = attempt.to_dict()
    ready_data["attempt_status"] = "READY_FOR_FUTURE_PREFLIGHT"
    ready_attempt = CandidateGenesisAttempt.from_dict(ready_data)
    with pytest.raises(CandidateValidationError) as error:
        verify_candidate_artifacts(
            request,
            proposal,
            approval,
            report,
            DEFAULT_CATALOG,
            blueprint,
            pressure_config,
            assessment,
            draft,
            ready_attempt,
        )
    assert error.value.code == "CANDIDATE_HASH_MISMATCH"


def test_candidate_semantic_hash_excludes_provenance_but_tracks_runtime_semantics():
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    assessment_a = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    draft_a, _attempt_a = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)

    blueprint_data = blueprint.to_dict()
    blueprint_data["blueprint_id"] = "blueprint-ocean-other"
    blueprint_b = WorldBlueprint.from_dict(blueprint_data)
    assessment_b = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint_b)
    draft_b, _attempt_b = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, blueprint_b, pressure_config)

    assert blueprint.hash != blueprint_b.hash
    assert assessment_a.hash != assessment_b.hash
    assert draft_a.hash != draft_b.hash
    assert draft_a.candidate_facts == draft_b.candidate_facts
    assert draft_a.pressure_component.pressure_config.to_dict() == draft_b.pressure_component.pressure_config.to_dict()
    assert draft_a.world_semantic_candidate_hash == draft_b.world_semantic_candidate_hash

    changed_config = replace(pressure_config, upgrade_stamina_cost=pressure_config.upgrade_stamina_cost + 1)
    draft_c, _attempt_c = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, changed_config)
    assert draft_c.world_semantic_candidate_hash != draft_a.world_semantic_candidate_hash

    changed_fact_data = blueprint.to_dict()
    changed_fact_data["facts"][0]["visibility"] = "WORLD_HIDDEN"
    changed_blueprint = WorldBlueprint.from_dict(changed_fact_data)
    draft_d, _attempt_d = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, changed_blueprint, pressure_config)
    assert draft_d.world_semantic_candidate_hash != draft_a.world_semantic_candidate_hash


@pytest.mark.parametrize(
    ("requirement_id", "kwargs", "expected_reason"),
    (
        ("req.ocean", {"warnings": ["ambiguous content scope"]}, "REPORT_ITEM_WARNING"),
        ("req.progression", {"warnings": ["runtime warning"]}, "REPORT_ITEM_WARNING"),
        ("req.ocean", {"candidate_feature_ids": ["kernel.canonical_identity"]}, "REPORT_ITEM_REJECTED"),
        ("req.progression", {"candidate_feature_ids": ["content.world_premise.v1"]}, "REPORT_ITEM_REJECTED"),
    ),
)
def test_binding_assessment_does_not_launder_warning_rejected_or_wrong_layer(requirement_id, kwargs, expected_reason):
    request, proposal, approval, report, blueprint, _pressure_config = _variant_fixture(requirement_id, **kwargs)
    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    item = next(item for item in assessment.items if item.requirement_id == requirement_id)
    assert item.status == "UNBOUND_BLOCKING"
    assert item.reason_code == expected_reason
    assert assessment.binding_gate_passed is False


def test_pressure_report_wrong_reason_is_a_stable_selection_failure():
    request, proposal, approval, report, blueprint, _pressure_config = _fixture()
    report_data = report.to_dict()
    item = next(item for item in report_data["items"] if item["requirement_id"] == "req.progression")
    item["reason_code"] = "SUPPORTED"
    forged_report = FeatureRequirementReport.from_dict(report_data)
    with pytest.raises(BindingValidationError) as error:
        build_runtime_binding_assessment(request, proposal, approval, forged_report, DEFAULT_CATALOG, blueprint)
    assert error.value.code == "REPORT_NOT_VERIFIED"


@pytest.mark.parametrize(
    "artifact_key",
    ("blueprint", "assessment", "pressure", "draft", "attempt"),
)
@pytest.mark.parametrize("bad_key", (1, ("tuple-key",), object()))
def test_all_v1c_from_dict_boundaries_reject_non_string_keys(artifact_key, bad_key):
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    draft, attempt = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)
    payloads = {
        "blueprint": (WorldBlueprint, blueprint.to_dict(), BlueprintValidationError),
        "assessment": (assessment.__class__, assessment.to_dict(), BindingValidationError),
        "pressure": (CandidatePressureComponent, draft.pressure_component.to_dict(), CandidateValidationError),
        "draft": (CandidateWorldDraft, draft.to_dict(), CandidateValidationError),
        "attempt": (CandidateGenesisAttempt, attempt.to_dict(), CandidateValidationError),
    }
    cls, payload, error_cls = payloads[artifact_key]
    payload[bad_key] = "invalid key"
    with pytest.raises(error_cls) as error:
        cls.from_dict(payload)
    assert error.value.code == "INVALID_TYPE"


def test_pressure_nested_from_dict_boundaries_reject_non_string_keys():
    _request, _proposal, _approval, _report, _blueprint, pressure_config = _fixture()
    _draft, _attempt = compile_candidate_artifacts(
        _request,
        _proposal,
        _approval,
        _report,
        DEFAULT_CATALOG,
        _blueprint,
        pressure_config,
    )
    payload = _draft.pressure_component.to_dict()
    payload["pressure_config"][1] = "invalid key"
    with pytest.raises(CandidateValidationError) as error:
        CandidatePressureComponent.from_dict(payload)
    assert error.value.code == "INVALID_TYPE"
