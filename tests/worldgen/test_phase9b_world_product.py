from __future__ import annotations

import copy

from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import build_observation
from tgn.llm_player import build_llm_decision_request
from tgn.worldgen import (
    compile_world,
    validate_documents,
    validate_draft,
    verify_bundle,
)
from tgn.worldgen.bundle import compile_bundle

from .conftest import draft_payload, request_payload, write_json


def test_failed_first_draft_can_be_locally_repaired_without_rewriting_everything(
    tmp_path, sample_request, sample_draft
):
    broken = copy.deepcopy(sample_draft)
    del broken["labels"]["target"]
    broken["world_id"] = "Bad ID"
    broken["mechanics_profile"] = "unsupported"
    broken["rules"] = {"reward": 99}
    _, _, issues = validate_documents(sample_request, broken)
    assert [(issue.code, issue.path) for issue in issues] == [
        ("MISSING_FIELD", "/draft/labels/target"),
        ("UNSUPPORTED_MECHANICS_PROFILE", "/draft/mechanics_profile"),
        ("UNKNOWN_FIELD", "/draft/rules"),
        ("INVALID_STABLE_ID", "/draft/world_id"),
    ]

    repaired = copy.deepcopy(broken)
    repaired["world_id"] = "repaired-world"
    repaired["mechanics_profile"] = "phase75_expedition_v1"
    repaired["labels"]["target"] = "repaired target"
    del repaired["rules"]
    request_path = write_json(tmp_path / "request.json", sample_request)
    draft_path = write_json(tmp_path / "draft.json", repaired)
    output = tmp_path / "compiled" / "repaired"
    result = compile_bundle(request_path, draft_path, "repair-seed", output)
    assert result["ok"] is True
    assert verify_bundle(output)["valid"] is True


def test_hidden_truth_and_runtime_schema_are_not_draft_inputs(sample_draft):
    for forbidden in (
        "hidden_fact",
        "private_knowledge",
        "secret_goal",
        "actual_relationship",
        "future_event",
        "reward",
        "state",
        "event",
        "runtime_ids",
    ):
        candidate = copy.deepcopy(sample_draft)
        candidate[forbidden] = {}
        _, draft_issues = validate_draft(candidate)
        assert any(issue.code == "UNKNOWN_FIELD" for issue in draft_issues), forbidden


def test_content_artifacts_differ_while_engine_projection_is_equal():
    first = compile_world(
        request_payload("朋克移动城市"),
        draft_payload(
            world_id="punk-world",
            title="朋克移动城市",
            premise="机械城市穿越荒原。",
        ),
        "shared-seed",
    )
    second = compile_world(
        request_payload("عالم جليدي"),
        draft_payload(
            world_id="arabic-world",
            locale="ar",
            title="مدينة الجليد",
            premise="قطار يعبر جليدا لا ينتهي.",
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
        "shared-seed",
    )
    assert state_hash(first.initial_state.__dict__) == state_hash(second.initial_state.__dict__)
    first_request = build_llm_decision_request(build_observation(first.initial_state), 1)
    second_request = build_llm_decision_request(build_observation(second.initial_state), 1)
    assert first_request.request_fingerprint == second_request.request_fingerprint
    assert first.worldpack_hash != second.worldpack_hash
    assert first.compiled_worldpack.public_content != second.compiled_worldpack.public_content
