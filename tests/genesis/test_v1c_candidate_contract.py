from __future__ import annotations

import builtins
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
    CandidatePressureComponent,
    CandidateValidationError,
    DEFAULT_CATALOG,
    ExclusiveUpgradePressureConfig,
    FeatureRequirementReport,
    GenesisRequest,
    PENDING_GATES,
    PRESSURE_CONTRACT_VERSION,
    PRESSURE_FEATURE_ID,
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
        _requirement("req.mass_drop", "全民投放的公开系统机制", "STRICT", "RUNTIME", ["runtime.mass_drop"], source_reference="prompt:line-1", requirement_kind="PUBLIC_SYSTEM"),
        _requirement("req.peers", "其他投放者作为可区分的同场实体", "STRICT", "RUNTIME", ["runtime.peers"], source_reference="prompt:line-3", requirement_kind="ENTITY_MODEL"),
        _requirement("req.vehicle", "投放者拥有载具实体", "STRICT", "RUNTIME", ["runtime.vehicle"], source_reference="prompt:line-2,line-3", requirement_kind="ENTITY_MODEL"),
        _requirement("req.ownership", "载具所有权绑定到对应投放者", "STRICT", "RUNTIME", ["runtime.ownership"], source_reference="prompt:line-2,line-3", requirement_kind="EXCLUSIVITY", typed_constraints=[RequirementConstraint("constraint.owner", "OWNERSHIP", "对应投放者", True)]),
        _requirement("req.creature", "主角独有活体玄武作为初始载具", "STRICT", "RUNTIME", ["runtime.living_xuanwu"], source_reference="prompt:line-2", requirement_kind="PROTAGONIST_CONSTRAINT"),
        _requirement("req.progression", "玄武作为可升级的成长对象", "STRICT", "RUNTIME", ["runtime.progression_object"], source_reference="prompt:line-4", requirement_kind="PROGRESSION_RULE"),
        _requirement("req.exclusion", "玄武升级排除木材和金属普通材料", "STRICT", "RUNTIME", ["runtime.material_exclusion"], source_reference="prompt:line-4", requirement_kind="PROGRESSION_RULE", typed_constraints=[RequirementConstraint("constraint.excludes", "EXCLUDES", ["木材", "金属"], True)]),
        _requirement("req.resource", "升级消耗专属资源能量晶石", "STRICT", "RUNTIME", ["runtime.energy_crystal"], source_reference="prompt:line-5", requirement_kind="RESOURCE_ECONOMY", typed_constraints=[RequirementConstraint("constraint.resource", "RESOURCE_COST", "能量晶石", True)]),
        _requirement("req.deduction", "能量晶石在升级时被永久扣除", "STRICT", "RUNTIME", ["runtime.permanent_deduction"], source_reference="prompt:line-5", requirement_kind="RESOURCE_ECONOMY", typed_constraints=[RequirementConstraint("constraint.deduction", "LIMIT", "永久扣除", True)]),
        _requirement("req.other_vehicles", "其他投放者拥有普通载具", "STRICT", "RUNTIME", ["runtime.other_vehicles"], source_reference="prompt:line-3", requirement_kind="EXCLUSIVITY"),
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
    facts = [
        BlueprintRequirementFact(
            item.requirement_id,
            item.source_reference,
            item.normalized_intent,
            fact_kinds[index],
            typed_constraints=item.typed_constraints,
        )
        for index, item in enumerate(requirements)
    ]
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


def test_recorded_fixture_builds_only_candidate_and_blocked_artifacts():
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    attempt = compile_candidate_attempt(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)
    draft, bundled_attempt = compile_candidate_artifacts(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)

    assert len(blueprint.facts) == 11
    assert [fact.requirement_id for fact in blueprint.facts] == [item.requirement_id for item in proposal.requirements]
    assert {fact.durability_tier for fact in blueprint.facts} == BLUEPRINT_DURABILITY_TIERS
    assert assessment.status_counts == {
        "CANDIDATE_RUNTIME_MATCH": 4,
        "CONTENT_ACCEPTED": 1,
        "OMITTED_OPTIONAL": 0,
        "UNBOUND_BLOCKING": 6,
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
    attempt = compile_candidate_attempt(request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config)
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
    assert CandidateGenesisAttempt.from_dict(forged).candidate_world_draft_hash == "0" * 64
    assert CandidateGenesisAttempt.from_dict(forged).hash != attempt.hash


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
            1,
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
