from __future__ import annotations

import copy
import json
import shutil

import pytest

from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import build_observation, execute_action
from tgn.llm_player import build_llm_decision_request
from tgn.llm_player.models import LLMDecisionRequest
from tgn.projection import compile_projection
from tgn.projection import compiler as compiler_module
from tgn.projection.presenter import build_player_presentation
from tgn.core.models import GameState
from tgn.worldgen.models import WorldGenError


def _overlay_result(bundle_pair):
    _base, overlay, projection, _tmp = bundle_pair
    draft = json.loads((projection / "projection_draft.json").read_text(encoding="utf-8"))
    return overlay, compile_projection(overlay, draft)


def test_base_projection_has_no_capability_identity(bundle_pair):
    base, _overlay, _projection, _tmp = bundle_pair
    overlay_draft = json.loads((bundle_pair[2] / "projection_draft.json").read_text(encoding="utf-8"))
    result = compile_projection(base, overlay_draft)
    assert "capabilities" not in result.projection.identities
    assert "capabilities" not in result.initial_presentation.observation


def test_overlay_projection_maps_capability_and_choice(bundle_pair):
    overlay, result = _overlay_result(bundle_pair)
    assert result.projection.identities["capabilities"] == {
        "devour_evolution": "Devour Evolution"
    }

    state = GameState(**json.loads((overlay / "initial_state.json").read_text(encoding="utf-8")))
    for index, action in enumerate(("DROP", "SEARCH", "FIGHT"), start=1):
        execution = execute_action(state, ActionIntent(f"proj-{index}", "player", action, {}))
        assert execution.accepted
        state = execution.final_state
    request = build_llm_decision_request(build_observation(state), 4)
    presentation = build_player_presentation(request, result.projection)
    choice = next(choice for choice in presentation.choices if choice["action_type"] == "DEVOUR_REMAINS")
    assert choice["params"] == {}
    assert choice["duration_minutes"] == 20
    assert choice["stamina_cost"] == 1
    assert choice["display_params"] == {
        "capability": {"id": "devour_evolution", "label": "Devour Evolution"}
    }
    assert presentation.observation["capabilities"] == [
        {
            "capability_id": "devour_evolution",
            "label": "Devour Evolution",
            "source_kind": "world_genesis",
        }
    ]


def test_capability_label_and_schema_are_projection_authoritative(bundle_pair):
    overlay, result = _overlay_result(bundle_pair)
    state = result.initial_request.observation
    state = copy.deepcopy(state)
    state["capabilities"][0]["label"] = "forged"
    request = LLMDecisionRequest(
        decision_number=result.initial_request.decision_number,
        observation=state,
        choices=result.initial_request.choices,
        request_fingerprint=result.initial_request.request_fingerprint,
    )
    with pytest.raises(WorldGenError):
        build_player_presentation(request, result.projection)


@pytest.mark.parametrize("mutation", ["not-list", "extra-field", "source-kind"])
def test_capability_observation_schema_fails_closed(bundle_pair, mutation):
    _overlay, result = _overlay_result(bundle_pair)
    observation = copy.deepcopy(result.initial_request.observation)
    if mutation == "not-list":
        observation["capabilities"] = "forged"
    elif mutation == "extra-field":
        observation["capabilities"][0]["extra"] = True
    else:
        observation["capabilities"][0]["source_kind"] = "private"
    request = LLMDecisionRequest(
        decision_number=result.initial_request.decision_number,
        observation=observation,
        choices=result.initial_request.choices,
        request_fingerprint=result.initial_request.request_fingerprint,
    )
    with pytest.raises(WorldGenError):
        build_player_presentation(request, result.projection)


@pytest.mark.parametrize("mutation", ["profile", "runtime", "public", "labels", "label-type"])
def test_overlay_source_profile_validation_fails_closed(bundle_pair, tmp_path, monkeypatch, mutation):
    base, _overlay, projection, _root = bundle_pair
    source = tmp_path / mutation
    shutil.copytree(base, source)
    worldpack_path = source / "compiled_worldpack.json"
    worldpack = json.loads(worldpack_path.read_text(encoding="utf-8"))
    if mutation == "profile":
        worldpack["mechanics_profile"] = "unsupported"
    elif mutation == "runtime":
        worldpack["runtime_bindings"]["resource_id"] = "other"
    elif mutation == "public":
        del worldpack["public_content"]["premise"]
    elif mutation == "labels":
        del worldpack["public_content"]["labels"]["base"]
    else:
        worldpack["public_content"]["labels"]["base"] = 1
    worldpack_path.write_text(json.dumps(worldpack, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    manifest = json.loads((source / "bundle.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(
        compiler_module,
        "verify_bundle",
        lambda _root: {
            "compiler_id": manifest["compiler_id"],
            "worldpack_hash": manifest["worldpack_hash"],
            "initial_state_hash": manifest["initial_state_hash"],
        },
    )
    draft = json.loads((projection / "projection_draft.json").read_text(encoding="utf-8"))
    with pytest.raises(WorldGenError):
        compile_projection(source, draft)


def test_overlay_source_initial_state_hash_validation_fails_closed(bundle_pair, monkeypatch):
    base, _overlay, projection, _root = bundle_pair
    manifest = json.loads((base / "bundle.json").read_text(encoding="utf-8"))
    original_hash = compiler_module.state_hash

    def wrong_initial_hash(value):
        if isinstance(value, dict) and {"schema_version", "event_seq", "decision_seq", "game_minute", "seed", "data"}.issubset(value):
            return "0" * 64
        return original_hash(value)

    monkeypatch.setattr(compiler_module, "state_hash", wrong_initial_hash)
    draft = json.loads((projection / "projection_draft.json").read_text(encoding="utf-8"))
    with pytest.raises(WorldGenError):
        compile_projection(base, draft)
