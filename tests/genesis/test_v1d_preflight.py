from __future__ import annotations

from dataclasses import replace

import pytest

from test_v1c_candidate_contract import _fixture

from tgn.genesis import (
    DEFAULT_CATALOG,
    CandidatePreflightBundle,
    CandidateValidationError,
    PreflightValidationError,
    RESOLVED_PREFLIGHT_GATES,
    REMAINING_GLOBAL_GATES,
    build_legacy_reference_snapshot,
    build_runtime_binding_assessment,
    compile_candidate_artifacts,
    run_candidate_preflight,
    run_gameplay_preflight,
    run_structural_divergence_preflight,
    verify_candidate_preflight,
)


def _candidate_tuple():
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    assessment = build_runtime_binding_assessment(
        request, proposal, approval, report, DEFAULT_CATALOG, blueprint
    )
    draft, attempt = compile_candidate_artifacts(
        request,
        proposal,
        approval,
        report,
        DEFAULT_CATALOG,
        blueprint,
        pressure_config,
    )
    return (
        request,
        proposal,
        approval,
        report,
        blueprint,
        pressure_config,
        assessment,
        draft,
        attempt,
    )


def test_static_preflight_recomputes_candidate_tuple_and_keeps_global_gates():
    values = _candidate_tuple()
    request, proposal, approval, report, blueprint, config, assessment, draft, attempt = values
    bundle = run_candidate_preflight(
        request,
        proposal,
        approval,
        report,
        DEFAULT_CATALOG,
        blueprint,
        config,
        assessment,
        draft,
        attempt,
    )

    static = bundle.static_report
    assert static.static_preflight_passed is True
    assert static.publication_eligible is False
    assert static.binding_gate_passed is False
    assert static.requirements_gate_passed is False
    assert static.binding_status_counts == (
        ("CANDIDATE_RUNTIME_MATCH", 10),
        ("CONTENT_ACCEPTED", 1),
        ("OMITTED_OPTIONAL", 0),
        ("UNBOUND_BLOCKING", 0),
    )
    assert static.runtime_catalog_feature_ids == ()
    assert static.blocked_gates == (
        "REQUIREMENTS_GATE",
        "RUNTIME_CATALOG_SUPPORT",
        "PUBLICATION",
        "AUTOPLAY_COMPATIBILITY",
    )
    assert static.required_pending_gates == (
        "REQUIREMENTS_GATE",
        "RUNTIME_CATALOG_SUPPORT",
        "STATIC_PREFLIGHT",
        "GAMEPLAY_PREFLIGHT",
        "STRUCTURAL_DIVERGENCE",
        "PUBLICATION",
        "AUTOPLAY_COMPATIBILITY",
    )
    assert bundle.resolved_preflight_gates == RESOLVED_PREFLIGHT_GATES
    assert bundle.remaining_global_gates == REMAINING_GLOBAL_GATES
    assert bundle.candidate_preflight_passed is True
    assert bundle.publication_eligible is False
    assert bundle.campaign_creation_allowed is False
    assert bundle.worldpack_seal_allowed is False


def test_gameplay_uses_real_pressure_prefix_replay_and_terminal_verifier():
    _, _, _, _, _, config, *_ = _candidate_tuple()
    gameplay = run_gameplay_preflight(config)
    assert gameplay.gameplay_preflight_passed is True
    assert gameplay.no_wait is True
    assert gameplay.prefix_replay_verified is True
    assert gameplay.terminal_verification_passed is True
    assert gameplay.policy_event_traces_differ is True
    assert gameplay.policy_final_state_hashes_differ is True
    assert gameplay.policy_results_differ is True
    assert gameplay.policy_material_outcomes_differ is True

    assert gameplay.policy_a.action_ids == (
        "RECOVER_EXCLUSIVE_RESOURCE",
        "UPGRADE_GROWTH_OBJECT",
        "TRAVERSE_HAZARD_ZONE",
    )
    assert gameplay.policy_b.action_ids == (
        "RECOVER_EXCLUSIVE_RESOURCE",
        "STABILIZE_SUPPLY_ROUTE",
        "CLAIM_SUPPLY_CACHE",
    )
    assert gameplay.policy_a.legal_actions_before == (
        ("RECOVER_EXCLUSIVE_RESOURCE",),
        ("UPGRADE_GROWTH_OBJECT", "STABILIZE_SUPPLY_ROUTE"),
        ("TRAVERSE_HAZARD_ZONE",),
    )
    assert gameplay.policy_b.legal_actions_before == (
        ("RECOVER_EXCLUSIVE_RESOURCE",),
        ("UPGRADE_GROWTH_OBJECT", "STABILIZE_SUPPLY_ROUTE"),
        ("CLAIM_SUPPLY_CACHE",),
    )
    assert gameplay.policy_a.legal_actions_after[-1] == ()
    assert gameplay.policy_b.legal_actions_after[-1] == ()
    assert len(gameplay.policy_a.prefix_replay_state_hashes) == 4
    assert len(gameplay.policy_b.prefix_replay_state_hashes) == 4
    assert gameplay.policy_a.terminal_result == "HAZARD_ZONE_TRAVERSED"
    assert gameplay.policy_b.terminal_result == "SUPPLY_CACHE_CLAIMED"
    assert gameplay.policy_a.branch_commitment == "UPGRADE"
    assert gameplay.policy_b.branch_commitment == "SUPPLY_ROUTE"
    assert gameplay.policy_a.exclusive_resource_final_lifecycle == "PERMANENTLY_CONSUMED"
    assert gameplay.policy_b.exclusive_resource_final_lifecycle == "PERMANENTLY_CONSUMED"
    assert len(gameplay.failure_proofs) == 13
    assert gameplay.failure_proof_passed is True
    assert all(item.accepted_event_count == 0 for item in gameplay.failure_proofs)
    assert all(item.state_unchanged and item.time_unchanged for item in gameplay.failure_proofs)


def test_structural_divergence_contains_legacy_reference_and_fixed_counterfactual():
    _, _, _, _, _, config, *_ = _candidate_tuple()
    gameplay = run_gameplay_preflight(config)
    structural = run_structural_divergence_preflight(config, gameplay)
    assert structural.gate_passed is True
    assert structural.divergence_id == "STRUCTURAL_DIVERGENCE_V1"
    assert structural.legacy_reference.source_profile_id == "phase75_expedition_v1"
    assert structural.legacy_reference.frozen_commit_identity == "pc1-frozen"
    assert structural.legacy_reference.legacy_legal_action_ids
    assert structural.legacy_reference.legacy_state_dimensions
    assert structural.legacy_reference.legacy_result_fields
    assert structural.legacy_reference.legacy_event_types
    assert structural.pressure_action_ids == (
        "CLAIM_SUPPLY_CACHE",
        "RECOVER_EXCLUSIVE_RESOURCE",
        "STABILIZE_SUPPLY_ROUTE",
        "TRAVERSE_HAZARD_ZONE",
        "UPGRADE_GROWTH_OBJECT",
    )
    assert structural.legacy_structural_comparison_passed is True
    assert structural.counterfactual_comparison_passed is True
    assert structural.policy_ab_divergence_passed is True
    assert structural.actual_evidence_hashes == (
        structural.source_config_hash,
        structural.policy_a_proof_hash,
        structural.policy_b_proof_hash,
    )
    assert {
        "LEGAL_ACTION_VOCABULARY",
        "STATE_DIMENSIONS",
        "EVENT_CAUSAL_CHAIN",
        "RESOURCE_ACQUISITION_PATH",
        "PROGRESSION_BRANCH",
        "OPPORTUNITY_COST",
    }.issubset(structural.changed_dimensions)

    counterfactual = structural.counterfactual
    assert counterfactual.counterfactual_id == "NO_EXCLUSIVE_RESOURCE_COUNTERFACTUAL_V1"
    assert counterfactual.actual_initial_legal_action_ids == ("RECOVER_EXCLUSIVE_RESOURCE",)
    assert counterfactual.counterfactual_initial_legal_action_ids == (
        "UPGRADE_GROWTH_OBJECT",
        "STABILIZE_SUPPLY_ROUTE",
    )
    assert counterfactual.actual_accepted_decision_count == 3
    assert counterfactual.counterfactual_accepted_decision_count == 2
    assert counterfactual.actual_event_count == 3
    assert counterfactual.counterfactual_event_count == 0
    assert counterfactual.proof_only is True
    assert counterfactual.generates_domain_events is False
    assert counterfactual.runtime_callable is False
    assert counterfactual.catalog_entry is False


def test_legacy_snapshot_is_static_and_does_not_touch_event_metadata(monkeypatch):
    import tgn.core.models as core_models

    monkeypatch.setattr(
        core_models.uuid,
        "uuid4",
        lambda: (_ for _ in ()).throw(AssertionError("UUID must not be generated")),
    )

    class BombDateTime:
        @classmethod
        def now(cls):
            raise AssertionError("wall clock must not be read")

    monkeypatch.setattr(core_models, "datetime", BombDateTime)
    snapshot = build_legacy_reference_snapshot()
    assert snapshot.frozen_commit_identity == "pc1-frozen"
    assert snapshot.source_profile_id == "phase75_expedition_v1"


def test_bundle_round_trip_and_full_recomputation_verification():
    values = _candidate_tuple()
    request, proposal, approval, report, blueprint, config, assessment, draft, attempt = values
    bundle = run_candidate_preflight(
        request,
        proposal,
        approval,
        report,
        DEFAULT_CATALOG,
        blueprint,
        config,
        assessment,
        draft,
        attempt,
    )
    parsed = CandidatePreflightBundle.from_dict(bundle.to_dict())
    assert parsed.hash == bundle.hash
    verified = verify_candidate_preflight(
        request,
        proposal,
        approval,
        report,
        DEFAULT_CATALOG,
        blueprint,
        config,
        assessment,
        draft,
        attempt,
        parsed.static_report,
        parsed.gameplay_report,
        parsed.structural_report,
        parsed,
    )
    assert verified.to_dict() == bundle.to_dict()


def test_unknown_fields_mixed_keys_and_nested_hashes_are_rejected():
    values = _candidate_tuple()
    request, proposal, approval, report, blueprint, config, assessment, draft, attempt = values
    bundle = run_candidate_preflight(
        request,
        proposal,
        approval,
        report,
        DEFAULT_CATALOG,
        blueprint,
        config,
        assessment,
        draft,
        attempt,
    )

    unknown = bundle.static_report.to_dict()
    unknown["unexpected"] = True
    with pytest.raises(PreflightValidationError) as error:
        bundle.static_report.from_dict(unknown)
    assert error.value.code == "UNKNOWN_FIELD"

    mixed = bundle.to_dict()
    mixed["static_preflight_report"][1] = "non-string-key"
    with pytest.raises(PreflightValidationError) as error:
        CandidatePreflightBundle.from_dict(mixed)
    assert error.value.code in {"INVALID_TYPE", "INVALID_SCHEMA"}

    forged = bundle.to_dict()
    forged["static_preflight_report_hash"] = "0" * 64
    with pytest.raises(PreflightValidationError) as error:
        CandidatePreflightBundle.from_dict(forged)
    assert error.value.code == "HASH_MISMATCH"


def test_persisted_candidate_tamper_and_original_attempt_are_not_accepted():
    values = _candidate_tuple()
    request, proposal, approval, report, blueprint, config, assessment, draft, attempt = values
    bundle = run_candidate_preflight(
        request,
        proposal,
        approval,
        report,
        DEFAULT_CATALOG,
        blueprint,
        config,
        assessment,
        draft,
        attempt,
    )
    forged_attempt = attempt.to_dict()
    forged_attempt["candidate_world_draft_hash"] = "0" * 64
    from tgn.genesis import CandidateGenesisAttempt

    parsed_attempt = CandidateGenesisAttempt.from_dict(forged_attempt)
    with pytest.raises(PreflightValidationError) as error:
        verify_candidate_preflight(
            request,
            proposal,
            approval,
            report,
            DEFAULT_CATALOG,
            blueprint,
            config,
            assessment,
            draft,
            parsed_attempt,
            bundle.static_report,
            bundle.gameplay_report,
            bundle.structural_report,
            bundle,
        )
    assert error.value.code == "CANDIDATE_ARTIFACT_INVALID"
    assert attempt.attempt_status == "BLOCKED_REQUIREMENTS"
    assert "PUBLICATION" in attempt.required_pending_gates


def test_structural_gate_cannot_be_forged_without_all_three_proofs():
    _, _, _, _, _, config, *_ = _candidate_tuple()
    gameplay = run_gameplay_preflight(config)
    structural = run_structural_divergence_preflight(config, gameplay)
    forged = structural.to_dict()
    forged["policy_ab_divergence_passed"] = False
    forged["gate_passed"] = True
    from tgn.genesis import StructuralDivergenceV1Report

    with pytest.raises(PreflightValidationError) as error:
        StructuralDivergenceV1Report.from_dict(forged)
    assert error.value.code == "STRUCTURAL_DIVERGENCE_FAILED"
