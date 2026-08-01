from __future__ import annotations

import copy
import json
from pathlib import Path

from tgn.actions.models import ActionIntent
from tgn.core.hashing import canonical_json, state_hash
from tgn.core.models import GameState
from tgn.gameplay.expedition import build_observation, execute_action
from tgn.llm_player import build_llm_decision_request
from tgn.projection import build_player_presentation, compile_projection
from tgn.worldgen import compile_bundle

from .conftest import draft_payload, projection_draft, request_payload, write_json


def _action(state: GameState, action_type: str, params: dict | None = None) -> GameState:
    result = execute_action(
        state,
        ActionIntent(
            action_id=f"product-{state.event_seq + 1}",
            actor_id="player",
            action_type=action_type,
            params=params or {},
        ),
    )
    assert result.accepted, result.validation.errors
    assert result.final_state is not None
    return result.final_state


def test_projection_presents_all_first_world_lifecycle_stages(source_bundle, valid_projection_draft):
    source_value = json.loads((source_bundle / "initial_state.json").read_text(encoding="utf-8"))
    initial = GameState(**source_value)
    projection = compile_projection(source_bundle, valid_projection_draft).projection

    initial_request = build_llm_decision_request(build_observation(initial), 1)
    assert initial_request.choices
    initial_view = build_player_presentation(initial_request, projection).to_dict()["observation"]
    assert initial_view["world_phase"] == {"id": "DAY", "label": "白昼"}
    assert initial_view["progression"]["tracks"]["player"]["next_cost_display"]

    dropped = _action(initial, "DROP")
    dropped_request = build_llm_decision_request(build_observation(dropped), 2)
    dropped_view = build_player_presentation(dropped_request, projection).to_dict()
    assert dropped_view["observation"]["location_id"] == "site-1"
    assert "site-1-condition" not in dropped_view["observation"]["actor"]["facts"]
    assert "world_facts" not in dropped_view["observation"]

    searched = _action(dropped, "SEARCH")
    searched_view = build_player_presentation(
        build_llm_decision_request(build_observation(searched), 3), projection
    ).to_dict()["observation"]
    assert searched_view["carried_loot"]
    assert [item["resource_id"] for item in searched_view["carried_loot"]] == ["parts", "salvage"]

    extracted = _action(searched, "EXTRACT")
    extracted_view = build_player_presentation(
        build_llm_decision_request(build_observation(extracted), 4), projection
    ).to_dict()["observation"]
    assert extracted_view["inventory"]
    assert extracted_view["actor"]["has_something_to_report"] is True
    assert "site-1-condition" not in extracted_view["actor"]["facts"]

    talked = _action(extracted, "TALK_TO_ACTOR", {"actor_id": "mara"})
    talked_view = build_player_presentation(
        build_llm_decision_request(build_observation(talked), 5), projection
    ).to_dict()["observation"]
    assert talked_view["actor"]["facts"]["site-1-condition"]["value"] == "unstable"

    staged = copy.deepcopy(initial)
    staged.data["progression"]["tracks"]["player"] = 1
    staged.data["progression"]["tracks"]["base"] = 1
    staged.data["inventory"] = {"parts": 1, "salvage": 2}
    build_request = build_llm_decision_request(build_observation(staged), 1)
    build_view = build_player_presentation(build_request, projection).to_dict()["observation"]
    assert build_view["build"]["choice_available"] is True
    assert len(build_view["build"]["choices"]) == 3
    assert build_view["progression"]["tracks"]["player"]["next_cost"] is None

    selected = _action(staged, "CHOOSE_BUILD", {"build_id": "quick_rest"})
    selected_view = build_player_presentation(
        build_llm_decision_request(build_observation(selected), 2), projection
    ).to_dict()["observation"]
    assert selected_view["build"]["selected"] == "quick_rest"
    assert selected_view["build"]["selected_display_name"]

    night = copy.deepcopy(initial)
    night.game_minute = 90
    night_request = build_llm_decision_request(build_observation(night), 1)
    night_view = build_player_presentation(night_request, projection).to_dict()["observation"]
    assert night_view["world_phase"]["id"] == "NIGHT"
    assert night_view["world_phase_label"]


def test_theme_and_language_matrix_changes_only_sidecar_text(tmp_path):
    themes = [
        draft_payload(world_id="punk-world", title="朋克移动城市", premise="机械城市穿越荒原。"),
        draft_payload(world_id="ice-train", locale="fr", title="Train de glace", premise="Un train traverse un glacier."),
        draft_payload(
            world_id="beast-camp",
            locale="ar",
            title="مخيم الوحش",
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
    ]
    compiled = []
    for index, world_draft in enumerate(themes):
        request_path = write_json(tmp_path / f"request-{index}.json", request_payload(world_draft["title"]))
        draft_path = write_json(tmp_path / f"world-{index}.json", world_draft)
        source = tmp_path / f"source-{index}"
        compile_bundle(request_path, draft_path, "matrix-seed", source)
        worldpack_hash = json.loads((source / "bundle.json").read_text(encoding="utf-8"))["worldpack_hash"]
        labels = projection_draft(worldpack_hash, suffix=f"-{index}")
        compiled.append((source, compile_projection(source, labels)))

    first_source, first = compiled[0]
    first_state_hash = json.loads((first_source / "bundle.json").read_text(encoding="utf-8"))["initial_state_hash"]
    for source, result in compiled[1:]:
        manifest = json.loads((source / "bundle.json").read_text(encoding="utf-8"))
        assert manifest["initial_state_hash"] == first_state_hash
        assert result.initial_request.to_dict() == first.initial_request.to_dict()
        assert result.initial_request.request_fingerprint == first.initial_request.request_fingerprint
        assert result.projection_hash != first.projection_hash
        assert result.presentation_hash != first.presentation_hash
        assert canonical_json(result.initial_presentation.to_dict()).encode("utf-8")
