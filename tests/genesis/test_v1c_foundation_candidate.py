from __future__ import annotations

import builtins
from dataclasses import replace
import socket
import sqlite3
import subprocess

import pytest

from tgn.genesis import (
    BindingValidationError,
    CandidateValidationError,
    DEFAULT_CATALOG,
    FOUNDATION_CONTRACT_VERSION,
    FOUNDATION_FEATURE_ID,
    FOUNDATION_INITIAL_COHORT_ID,
    FOUNDATION_LAUNCH_SYSTEM_ID,
    FOUNDATION_LIVING_XUANWU_KIND,
    FOUNDATION_ORDINARY_VEHICLE_KINDS,
    FOUNDATION_PEER_ACTOR_IDS,
    FOUNDATION_PEER_VEHICLE_IDS,
    FOUNDATION_PROTAGONIST_ACTOR_ID,
    FOUNDATION_PROTAGONIST_VEHICLE_ID,
    FOUNDATION_REQUIREMENT_IDS,
    FOUNDATION_SCHEMA_VERSION,
    FoundationCandidateComponent,
    FoundationValidationError,
    FoundationVehicleCandidate,
    build_foundation_candidate,
    build_runtime_binding_assessment,
    compile_candidate_artifacts,
    verify_foundation_candidate,
)

from test_v1c_candidate_contract import _fixture, _variant_fixture


def _foundation_fixture():
    request, proposal, approval, report, blueprint, pressure_config = _fixture()
    component = build_foundation_candidate(blueprint, pressure_config)
    return request, proposal, approval, report, blueprint, pressure_config, component


def test_recorded_foundation_has_exact_cohort_vehicle_and_ownership_semantics():
    _request, _proposal, _approval, _report, _blueprint, _pressure, component = _foundation_fixture()
    assert component.feature_id == FOUNDATION_FEATURE_ID
    assert component.contract_version == FOUNDATION_CONTRACT_VERSION
    assert component.launch_system_id == FOUNDATION_LAUNCH_SYSTEM_ID
    assert component.initial_cohort_id == FOUNDATION_INITIAL_COHORT_ID
    assert component.source_requirement_ids == FOUNDATION_REQUIREMENT_IDS
    assert [actor.actor_id for actor in component.actors] == [
        FOUNDATION_PROTAGONIST_ACTOR_ID,
        *FOUNDATION_PEER_ACTOR_IDS,
    ]
    assert [vehicle.vehicle_id for vehicle in component.vehicles] == [
        FOUNDATION_PROTAGONIST_VEHICLE_ID,
        *FOUNDATION_PEER_VEHICLE_IDS,
    ]
    assert sum(actor.role == "PROTAGONIST" for actor in component.actors) == 1
    assert sum(actor.role == "PEER" for actor in component.actors) == 2
    assert sum(vehicle.living for vehicle in component.vehicles) == 1
    assert sum(vehicle.growth_object for vehicle in component.vehicles) == 1

    protagonist = component.vehicles[0]
    peers = component.vehicles[1:]
    assert protagonist.owner_id == FOUNDATION_PROTAGONIST_ACTOR_ID
    assert protagonist.vehicle_kind == FOUNDATION_LIVING_XUANWU_KIND
    assert protagonist.living is True
    assert protagonist.growth_object is True
    assert all(vehicle.owner_id == actor_id for vehicle, actor_id in zip(peers, FOUNDATION_PEER_ACTOR_IDS))
    assert all(vehicle.living is False and vehicle.growth_object is False for vehicle in peers)
    assert len({vehicle.vehicle_kind for vehicle in peers}) == 2


def test_foundation_pressure_identity_is_closed_and_mismatch_is_stable():
    _request, _proposal, _approval, _report, blueprint, pressure_config, component = _foundation_fixture()
    assert component.pressure_feature_id == pressure_config.feature_id
    assert component.pressure_contract_version == pressure_config.contract_version
    assert component.pressure_protagonist_id == pressure_config.protagonist_id == FOUNDATION_PROTAGONIST_ACTOR_ID
    assert component.pressure_growth_object_id == pressure_config.growth_object_id == FOUNDATION_PROTAGONIST_VEHICLE_ID
    assert component.pressure_growth_object_owner_id == pressure_config.growth_object_owner_id == FOUNDATION_PROTAGONIST_ACTOR_ID
    assert component.pressure_exclusive_resource_id == pressure_config.exclusive_resource_id == "resource.energy_crystal"
    assert verify_foundation_candidate(blueprint, pressure_config, component).to_dict() == component.to_dict()

    with pytest.raises(FoundationValidationError) as error:
        build_foundation_candidate(blueprint, replace(pressure_config, growth_object_id="vehicle.peer.1"))
    assert error.value.code == "FOUNDATION_CONFIG_MISMATCH"

    forged_blueprint = blueprint.to_dict()
    forged_fact = next(item for item in forged_blueprint["facts"] if item["requirement_id"] == "req.vehicle")
    forged_fact["object_ids"] = ["vehicle.protagonist", "vehicle.peer.1"]
    with pytest.raises(FoundationValidationError) as error:
        build_foundation_candidate(blueprint.__class__.from_dict(forged_blueprint), pressure_config)
    assert error.value.code == "FOUNDATION_REQUIREMENT_MISMATCH"


def test_foundation_schema_round_trip_is_strict_and_detached():
    _request, _proposal, _approval, _report, _blueprint, _pressure, component = _foundation_fixture()
    assert component.schema_version == FOUNDATION_SCHEMA_VERSION
    parsed = FoundationCandidateComponent.from_dict(component.to_dict())
    assert parsed.to_dict() == component.to_dict()
    assert parsed.hash == component.hash

    exported = component.to_dict()
    exported["actors"][0]["actor_id"] = "actor.attacker"
    assert component.actors[0].actor_id == FOUNDATION_PROTAGONIST_ACTOR_ID

    unknown = component.to_dict()
    unknown["placeholder"] = True
    with pytest.raises(FoundationValidationError) as error:
        FoundationCandidateComponent.from_dict(unknown)
    assert error.value.code == "UNKNOWN_FIELD"

    mixed = component.to_dict()
    mixed[1] = "invalid"
    with pytest.raises(FoundationValidationError) as error:
        FoundationCandidateComponent.from_dict(mixed)
    assert error.value.code == "INVALID_TYPE"

    wrong_nested = component.to_dict()
    wrong_nested["vehicles"][0][("tuple-key",)] = "invalid"
    with pytest.raises(FoundationValidationError) as error:
        FoundationCandidateComponent.from_dict(wrong_nested)
    assert error.value.code == "INVALID_TYPE"

    with pytest.raises(FoundationValidationError) as error:
        verify_foundation_candidate(_blueprint, _pressure, object())
    assert error.value.code == "INVALID_TYPE"


def test_foundation_hashes_are_deterministic_and_semantic_provenance_is_separate():
    request, proposal, approval, report, blueprint, pressure_config, component = _foundation_fixture()
    draft_a, _attempt_a = compile_candidate_artifacts(
        request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config
    )
    other_blueprint_data = blueprint.to_dict()
    other_blueprint_data["blueprint_id"] = "blueprint-ocean-foundation-provenance"
    other_blueprint = blueprint.__class__.from_dict(other_blueprint_data)
    draft_b, _attempt_b = compile_candidate_artifacts(
        request, proposal, approval, report, DEFAULT_CATALOG, other_blueprint, pressure_config
    )
    assert build_foundation_candidate(blueprint, pressure_config).to_dict() == component.to_dict()
    assert component.hash == build_foundation_candidate(blueprint, pressure_config).hash
    assert draft_a.hash != draft_b.hash
    assert draft_a.world_semantic_candidate_hash == draft_b.world_semantic_candidate_hash

    changed_kind = list(component.vehicles)
    changed_kind[1] = replace(changed_kind[1], vehicle_kind="vehicle.kind.peer_canoe")
    changed_component = FoundationCandidateComponent(
        schema_version=component.schema_version,
        feature_id=component.feature_id,
        contract_version=component.contract_version,
        launch_system_id=component.launch_system_id,
        initial_cohort_id=component.initial_cohort_id,
        protagonist_actor_id=component.protagonist_actor_id,
        protagonist_vehicle_id=component.protagonist_vehicle_id,
        actors=component.actors,
        vehicles=changed_kind,
        source_requirement_ids=component.source_requirement_ids,
        source_blueprint_hash=component.source_blueprint_hash,
        pressure_feature_id=component.pressure_feature_id,
        pressure_contract_version=component.pressure_contract_version,
        pressure_protagonist_id=component.pressure_protagonist_id,
        pressure_growth_object_id=component.pressure_growth_object_id,
        pressure_growth_object_owner_id=component.pressure_growth_object_owner_id,
        pressure_exclusive_resource_id=component.pressure_exclusive_resource_id,
    )
    changed_draft = draft_a.__class__(
        draft_schema_version=draft_a.draft_schema_version,
        draft_id=draft_a.draft_id,
        blueprint_hash=draft_a.blueprint_hash,
        binding_assessment_hash=draft_a.binding_assessment_hash,
        candidate_facts=draft_a.candidate_facts,
        pressure_component=draft_a.pressure_component,
        candidate_initial_component=draft_a.candidate_initial_component,
        foundation_component=changed_component,
    )
    assert changed_draft.world_semantic_candidate_hash != draft_a.world_semantic_candidate_hash
    assert changed_draft.hash != draft_a.hash


def test_foundation_persisted_tamper_and_invalid_semantics_are_rejected():
    request, proposal, approval, report, blueprint, pressure_config, component = _foundation_fixture()
    draft, attempt = compile_candidate_artifacts(
        request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config
    )

    forged = component.to_dict()
    forged["source_blueprint_hash"] = "0" * 64
    forged_component = FoundationCandidateComponent.from_dict(forged)
    with pytest.raises(FoundationValidationError) as error:
        verify_foundation_candidate(blueprint, pressure_config, forged_component)
    assert error.value.code == "FOUNDATION_HASH_MISMATCH"

    invalid_owner = component.to_dict()
    invalid_owner["vehicles"][1]["owner_id"] = FOUNDATION_PEER_ACTOR_IDS[1]
    with pytest.raises(FoundationValidationError) as error:
        FoundationCandidateComponent.from_dict(invalid_owner)
    assert error.value.code == "FOUNDATION_REQUIREMENT_MISMATCH"

    invalid_living = component.to_dict()
    invalid_living["vehicles"][1]["living"] = True
    with pytest.raises(FoundationValidationError) as error:
        FoundationCandidateComponent.from_dict(invalid_living)
    assert error.value.code == "FOUNDATION_REQUIREMENT_MISMATCH"

    invalid_protagonist = component.to_dict()
    invalid_protagonist["vehicles"][0]["vehicle_kind"] = "vehicle.kind.peer_skiff"
    with pytest.raises(FoundationValidationError) as error:
        FoundationCandidateComponent.from_dict(invalid_protagonist)
    assert error.value.code == "FOUNDATION_REQUIREMENT_MISMATCH"

    draft_payload = draft.to_dict()
    draft_payload["foundation_component"] = forged
    forged_draft = draft.__class__.from_dict(draft_payload)
    with pytest.raises(CandidateValidationError) as error:
        from tgn.genesis import verify_candidate_artifacts

        verify_candidate_artifacts(
            request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config,
            build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint),
            forged_draft, attempt,
        )
    assert error.value.code in {"FOUNDATION_HASH_MISMATCH", "CANDIDATE_HASH_MISMATCH"}


def test_foundation_binding_counts_and_gate_honesty():
    request, proposal, approval, report, blueprint, pressure_config, _component = _foundation_fixture()
    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    assert assessment.status_counts == {
        "CANDIDATE_RUNTIME_MATCH": 10,
        "CONTENT_ACCEPTED": 1,
        "OMITTED_OPTIONAL": 0,
        "UNBOUND_BLOCKING": 0,
    }
    foundation_items = [item for item in assessment.items if item.requirement_id in FOUNDATION_REQUIREMENT_IDS]
    assert len(foundation_items) == 6
    assert all(item.candidate_feature_id == FOUNDATION_FEATURE_ID for item in foundation_items)
    assert assessment.binding_gate_passed is False
    assert report.requirements_gate_passed is False
    assert not any(feature.feature_id == FOUNDATION_FEATURE_ID for feature in DEFAULT_CATALOG.entries)
    assert not any(feature.layer == "RUNTIME" for feature in DEFAULT_CATALOG.entries)
    draft, attempt = compile_candidate_artifacts(
        request, proposal, approval, report, DEFAULT_CATALOG, blueprint, pressure_config
    )
    assert draft.foundation_component.feature_id == FOUNDATION_FEATURE_ID
    assert attempt.attempt_status == "BLOCKED_REQUIREMENTS"


@pytest.mark.parametrize("requirement_id", FOUNDATION_REQUIREMENT_IDS[:2])
def test_foundation_warning_or_rejection_is_not_laundered(requirement_id):
    request, proposal, approval, report, blueprint, _pressure_config = _variant_fixture(
        requirement_id,
        warnings=["foundation ambiguity"],
    )
    assessment = build_runtime_binding_assessment(request, proposal, approval, report, DEFAULT_CATALOG, blueprint)
    item = next(item for item in assessment.items if item.requirement_id == requirement_id)
    assert item.status == "UNBOUND_BLOCKING"
    assert item.candidate_feature_id is None
    assert item.reason_code == "REPORT_ITEM_WARNING"
    assert assessment.binding_gate_passed is False


def test_foundation_candidate_has_no_io_runtime_registration_or_generic_registry(monkeypatch):
    _request, _proposal, _approval, _report, blueprint, pressure_config, _component = _foundation_fixture()

    def forbidden(*args, **kwargs):
        raise AssertionError("foundation candidate attempted an external side effect")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    first = build_foundation_candidate(blueprint, pressure_config)
    second = build_foundation_candidate(blueprint, pressure_config)
    assert first.to_dict() == second.to_dict()
    assert first.hash == second.hash
    assert not hasattr(first, "registry")
    assert not hasattr(first, "plugin_id")
