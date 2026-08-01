from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tgn.core.hashing import canonical_json, state_hash
from tgn.core.invariants import check_invariants
from tgn.gameplay.expedition import build_observation, get_legal_actions
from tgn.llm_player import build_llm_decision_request
import tgn.worldgen.compiler as compiler_module
from tgn.worldgen import (
    BootstrapResult,
    MECHANICS_PROFILE,
    WorldGenError,
    bootstrap_smoke,
    compile_world,
    compile_worldpack,
    materialize_initial_state,
)
from tgn.worldgen.compiler import load_draft, load_request
from tgn.worldgen.models import WorldDraft

from .conftest import draft_payload, request_payload


def test_compile_binds_only_reviewed_runtime_ids_and_keeps_content_out_of_state(
    sample_request, sample_draft
):
    result = compile_world(sample_request, sample_draft, "compiler-seed")
    pack = result.compiled_worldpack.to_dict()
    assert set(pack) == {
        "schema_version",
        "compiler_id",
        "mechanics_profile",
        "world_id",
        "content_locale",
        "public_content",
        "runtime_bindings",
    }
    assert pack["mechanics_profile"] == MECHANICS_PROFILE
    assert pack["runtime_bindings"] == {
        "base_location_id": "base-1",
        "target_location_id": "site-1",
        "resource_id": "salvage",
        "named_actor_id": "mara",
        "named_actor_fact_id": "site-1-condition",
    }
    state_text = canonical_json(result.initial_state.__dict__)
    assert sample_draft["title"] not in state_text
    assert sample_draft["premise"] not in state_text
    assert sample_draft["labels"]["base"] not in state_text
    assert result.initial_state.seed == "compiler-seed"
    check_invariants(result.initial_state)


def test_materializer_is_deterministic_and_initial_choices_are_nonempty(
    sample_request, sample_draft
):
    first = compile_world(sample_request, sample_draft, "same-seed")
    second = compile_world(sample_request, sample_draft, "same-seed")
    assert first.initial_state.__dict__ == second.initial_state.__dict__
    assert first.initial_state_hash == second.initial_state_hash
    observation = build_observation(first.initial_state)
    assert get_legal_actions(first.initial_state)
    assert observation["legal_actions"]
    first_request = build_llm_decision_request(observation, 1)
    second_request = build_llm_decision_request(build_observation(second.initial_state), 1)
    assert first_request.request_fingerprint == second_request.request_fingerprint


def test_smoke_reuses_existing_autoplay_and_replay_contract(compilation):
    smoke = bootstrap_smoke(compilation.initial_state)
    assert smoke.passed is True
    assert smoke.accepted_decisions == 4
    assert smoke.events == 4
    assert smoke.illegal_actions == 0
    assert smoke.knowledge_boundary_violations == 0
    assert smoke.event_replay is True
    assert smoke.final_state.data["named_actor"]["relationship"]["trust"] == 1
    assert smoke.final_state.data["player_knowledge"]["facts"] == {
        "site-1-condition": "unstable"
    }
    assert smoke.final_state.data["named_actor"]["last_autonomous_action"] == "INSPECT_SIGNAL"


def test_content_and_language_change_pack_but_not_engine_artifacts():
    request = request_payload()
    drafts = [
        draft_payload(
            world_id="punk-mobile-city",
            title="朋克移动城市",
            premise="一座机械城市穿越荒原。",
        ),
        draft_payload(
            world_id="eternal-ice-train",
            title="永夜冰川列车",
            premise="列车在永夜冰川上寻找燃料。",
            locale="en",
        ),
        draft_payload(
            world_id="giant-beast-camp",
            title="巨兽背部营地",
            premise="营地建在一头迁徙巨兽的背上。",
            locale="fr",
        ),
        draft_payload(
            world_id="arabic-ice-world",
            title="مدينة الجليد",
            premise="قطار يعبر جليدا لا ينتهي.",
            locale="ar",
            labels={
                "base": "قطار النجاة",
                "target": "محطة جليدية",
                "resource": "نواة الطاقة",
                "hazard": "عاصفة بيضاء",
                "named_actor": "ميرا",
                "named_actor_role": "حارسة الصيانة",
                "named_actor_public_goal": "تحقيق في الإشارة الغامضة",
            },
        ),
    ]
    results = [compile_world(request, draft, "shared-seed") for draft in drafts]
    assert len({result.worldpack_hash for result in results}) == 4
    assert len({result.initial_state_hash for result in results}) == 1
    fingerprints = {
        build_llm_decision_request(build_observation(result.initial_state), 1).request_fingerprint
        for result in results
    }
    assert len(fingerprints) == 1
    assert all(result.report["bootstrap"]["event_replay"] for result in results)


def test_different_seed_changes_state_but_not_presentation_pack(sample_draft):
    first = compile_world(request_payload(), sample_draft, "seed-a")
    second = compile_world(request_payload(), sample_draft, "seed-b")
    assert first.worldpack_hash == second.worldpack_hash
    assert first.initial_state_hash != second.initial_state_hash


def test_profile_branch_is_explicit_and_rejects_unknown_profile(sample_request, sample_draft):
    invalid = copy.deepcopy(sample_draft)
    invalid["mechanics_profile"] = "future-profile"
    with pytest.raises(WorldGenError) as error:
        compile_world(sample_request, invalid, "seed")
    assert error.value.code == "INVALID_SCHEMA"
    assert error.value.issues[0].code == "UNSUPPORTED_MECHANICS_PROFILE"


def test_compiled_pack_cannot_materialize_forged_runtime_bindings(compilation):
    forged = compilation.compiled_worldpack.to_dict()
    forged["runtime_bindings"]["target_location_id"] = "other-site"
    with pytest.raises(WorldGenError) as error:
        materialize_initial_state(forged, "seed")
    assert error.value.code == "BUNDLE_INTEGRITY_MISMATCH"


def test_compile_report_contains_only_deterministic_smoke_fields(compilation):
    report = compilation.report
    assert set(report) == {
        "schema_version",
        "valid",
        "compiler_id",
        "errors",
        "worldpack_hash",
        "initial_state_hash",
        "bootstrap",
    }
    assert set(report["bootstrap"]) == {
        "accepted_decisions",
        "events",
        "illegal_actions",
        "knowledge_boundary_violations",
        "event_replay",
        "final_state_hash",
    }
    assert "event_id" not in canonical_json(report)
    assert "created_at" not in canonical_json(report)


def test_loaders_fail_closed_for_missing_encoding_json_and_schema(tmp_path: Path):
    with pytest.raises(WorldGenError) as missing:
        load_request(str(tmp_path / "missing.json"))
    assert missing.value.code == "INVALID_JSON"

    invalid_utf8 = tmp_path / "invalid-utf8.json"
    invalid_utf8.write_bytes(b"\xff")
    with pytest.raises(WorldGenError) as encoding:
        load_request(str(invalid_utf8))
    assert encoding.value.code == "INVALID_JSON"

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json}", encoding="utf-8")
    with pytest.raises(WorldGenError) as malformed_error:
        load_draft(str(malformed))
    assert malformed_error.value.code == "INVALID_JSON"

    invalid_schema = tmp_path / "invalid-schema.json"
    invalid_schema.write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(WorldGenError) as schema:
        load_draft(str(invalid_schema))
    assert schema.value.code == "INVALID_SCHEMA"

    with pytest.raises(WorldGenError) as request_schema:
        load_request(str(invalid_schema))
    assert request_schema.value.code == "INVALID_SCHEMA"


@pytest.mark.parametrize("seed", [None, "", "bad\x00seed"])
def test_compile_rejects_invalid_seed_before_materialization(sample_request, sample_draft, seed):
    with pytest.raises(WorldGenError) as error:
        compile_world(sample_request, sample_draft, seed)
    assert error.value.code == "INVALID_TEXT"
    assert error.value.issues[0].path == "/seed"


def test_compile_rejects_invalid_edge_models_before_runtime_binding(sample_draft):
    with pytest.raises(WorldGenError) as request_error:
        compile_world([], sample_draft, "seed")
    assert request_error.value.code == "INVALID_SCHEMA"

    with pytest.raises(WorldGenError) as draft_error:
        compile_world({"schema_version": 1, "prompt": "prompt"}, [], "seed")
    assert draft_error.value.code == "INVALID_SCHEMA"


def test_direct_profile_and_materializer_guards_do_not_accept_unknown_runtime_profiles(
    sample_draft,
):
    draft = WorldDraft(
        schema_version=1,
        mechanics_profile="future-profile",
        world_id=sample_draft["world_id"],
        content_locale=sample_draft["content_locale"],
        title=sample_draft["title"],
        premise=sample_draft["premise"],
        labels=sample_draft["labels"],
    )
    with pytest.raises(WorldGenError) as profile_error:
        compile_worldpack(draft)
    assert profile_error.value.code == "UNSUPPORTED_MECHANICS_PROFILE"

    with pytest.raises(WorldGenError) as materialize_error:
        materialize_initial_state({}, "seed")
    assert materialize_error.value.code == "UNSUPPORTED_MECHANICS_PROFILE"


def test_materializer_converts_invariant_failures_to_bootstrap_errors(compilation, monkeypatch):
    def fail_invariants(_state):
        raise ValueError("forced invariant failure")

    monkeypatch.setattr(compiler_module, "check_invariants", fail_invariants)
    with pytest.raises(WorldGenError) as error:
        materialize_initial_state(compilation.compiled_worldpack, "seed")
    assert error.value.code == "BOOTSTRAP_FAILED"


def test_bootstrap_smoke_reports_empty_initial_legal_choices(monkeypatch, compilation):
    monkeypatch.setattr(compiler_module, "get_legal_actions", lambda _state: ())
    result = bootstrap_smoke(compilation.initial_state)

    assert result.passed is False
    assert result.error == "initial legal choices are empty"
    assert result.final_state_hash == state_hash(compilation.initial_state.__dict__)


def test_bootstrap_smoke_reports_unexpected_boundary_failure(monkeypatch, compilation):
    def fail_observation(_state):
        raise RuntimeError("forced observation failure")

    monkeypatch.setattr(compiler_module, "build_observation", fail_observation)
    result = bootstrap_smoke(compilation.initial_state)

    assert result.passed is False
    assert result.events == 0
    assert result.event_replay is False
    assert result.final_state_hash == state_hash(compilation.initial_state.__dict__)


def test_compile_raises_stable_error_when_bootstrap_contract_fails(
    monkeypatch, sample_request, sample_draft
):
    failure = BootstrapResult(
        passed=False,
        accepted_decisions=0,
        events=0,
        illegal_actions=1,
        knowledge_boundary_violations=0,
        event_replay=False,
        final_state_hash="",
        final_state=None,
        error="forced bootstrap mismatch",
    )
    monkeypatch.setattr(compiler_module, "bootstrap_smoke", lambda _state: failure)

    with pytest.raises(WorldGenError) as error:
        compile_world(sample_request, sample_draft, "seed")
    assert error.value.code == "BOOTSTRAP_FAILED"
    assert error.value.issues[0].actual["illegal_actions"] == 1
