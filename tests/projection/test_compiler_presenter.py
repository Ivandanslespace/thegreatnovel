from __future__ import annotations

import copy
import json

import pytest

from tgn.core.hashing import state_hash
from tgn.llm_player import build_llm_decision_request
from tgn.llm_player.models import LLMActionChoice, LLMDecisionRequest
from tgn.projection import (
    PlayerProjectionMap,
    build_player_presentation,
    compile_projection,
    presentation_hash,
    projection_hash,
)
from tgn.worldgen.models import WorldGenError


def _request(result, observation, choices=None):
    return LLMDecisionRequest(
        decision_number=1,
        observation=observation,
        choices=tuple(choices or result.initial_request.choices),
        request_fingerprint="test-fingerprint",
    )


def test_projection_covers_bounded_runtime_identity_set(compiled_projection):
    result, _ = compiled_projection
    identities = result.projection.identities
    assert set(identities["locations"]) == {"base-1", "site-1"}
    assert set(identities["resources"]) == {"salvage", "parts"}
    assert set(identities["actors"]) == {"mara"}
    assert set(identities["actor_goals"]) == {"inspect_signal", "report_finding", "reported"}
    assert set(identities["facts"]) == {"site-1-condition"}
    assert set(identities["progression_tracks"]) == {"player", "base"}
    assert set(identities["builds"]) == {"window_runner", "field_rest", "quick_rest"}
    assert set(identities["world_phases"]) == {"DAY", "NIGHT"}
    assert result.report["unmapped_identity_count"] == 0
    expected_counts = {
        "locations": 2,
        "resources": 2,
        "actors": 1,
        "actor_goals": 3,
        "fact_ids": 1,
        "fact_values": 2,
        "progression_tracks": 2,
        "builds": 3,
        "world_phases": 2,
    }
    assert expected_counts["locations"] == len(identities["locations"])
    assert expected_counts["resources"] == len(identities["resources"])
    assert expected_counts["actors"] == len(identities["actors"])
    assert expected_counts["actor_goals"] == len(identities["actor_goals"])
    assert expected_counts["fact_ids"] == len(identities["facts"])
    assert expected_counts["fact_values"] == sum(
        len(fact["values"]) for fact in identities["facts"].values()
    )
    assert expected_counts["progression_tracks"] == len(identities["progression_tracks"])
    assert expected_counts["builds"] == len(identities["builds"])
    assert expected_counts["world_phases"] == len(identities["world_phases"])
    assert result.report["mapped_identity_count"] == sum(expected_counts.values()) == 18


def test_presentation_preserves_canonical_request_and_adds_display_labels(compiled_projection):
    result, _ = compiled_projection
    presentation = result.initial_presentation.to_dict()
    assert presentation["request_fingerprint"] == result.initial_request.request_fingerprint
    assert presentation["observation"]["location_id"] == "base-1"
    assert presentation["observation"]["location_label"]
    assert presentation["observation"]["actor"]["actor_id"] == "mara"
    assert presentation["observation"]["actor"]["display_name"]
    assert presentation["observation"]["build"]["choices"][0]["build_id"] == "window_runner"
    assert presentation["observation"]["build"]["choices"][0]["display_name"]
    assert presentation["choices"][0]["choice_id"] == "choice-000"
    assert presentation["choices"][0]["duration_minutes"] is None


def test_presentation_removes_legacy_actor_and_build_display_leakage(compiled_projection):
    result, _ = compiled_projection
    presentation = result.initial_presentation.to_dict()
    actor = presentation["observation"]["actor"]
    actor_map = result.projection.identities["actors"]["mara"]
    assert "canonical_name" not in actor
    assert actor["name"] == actor_map["name"]
    assert actor["display_name"] == actor_map["name"]
    assert actor["name"] != result.initial_request.observation["actor"]["name"]

    canonical_build = result.initial_request.observation["build"]["choices"][0]
    visible_build = presentation["observation"]["build"]["choices"][0]
    assert "title" not in visible_build
    assert visible_build["build_id"] == canonical_build["build_id"]
    assert visible_build["display_name"] == result.projection.identities["builds"][canonical_build["build_id"]]
    for field in (
        "effect_summary",
        "relevant_condition_or_limitation",
        "permanence",
        "opportunity_cost",
    ):
        assert visible_build[field] == canonical_build[field]
    assert presentation["observation"]["build"]["selection_rule"] == result.initial_request.observation["build"]["selection_rule"]


def test_presentation_maps_sorted_inventory_and_public_fact_without_private_leak(compiled_projection):
    result, _ = compiled_projection
    observation = result.initial_request.observation
    observation.update(
        {
            "location_id": "site-1",
            "inventory": {"salvage": 2, "parts": 1},
            "carried_loot": {"parts": 3},
            "world_facts": {"site-1-condition": "unstable"},
            "target_loot": {"salvage": 999},
            "private_knowledge": {"secret": True},
        }
    )
    observation["actor"] = {
        "actor_id": "mara",
        "name": "Mara",
        "last_known_location_id": "base-1",
        "known_goal": "inspect_signal",
        "trust": 0,
        "visible": False,
        "has_something_to_report": False,
        "facts": {"site-1-condition": "unstable"},
        "last_autonomous_action": "INSPECT_SIGNAL",
        "private_goal": "report_finding",
    }
    request = LLMDecisionRequest(
        decision_number=1,
        observation=observation,
        choices=result.initial_request.choices,
        request_fingerprint="public-fingerprint",
    )
    presentation = build_player_presentation(request, result.projection).to_dict()
    mapped = presentation["observation"]
    assert [item["resource_id"] for item in mapped["inventory"]] == ["parts", "salvage"]
    assert mapped["carried_loot"][0]["resource_id"] == "parts"
    assert mapped["actor"]["facts"]["site-1-condition"]["value_label"]
    assert "world_facts" not in mapped
    assert "target_loot" not in mapped
    assert "private_knowledge" not in mapped
    assert "last_autonomous_action" not in mapped["actor"]
    assert "private_goal" not in mapped["actor"]


@pytest.mark.parametrize(
    ("field", "value", "path"),
    [
        ("location_id", "unknown-location", "/observation/location_id"),
        ("inventory", {"unknown-resource": 1}, "/observation/inventory/unknown-resource"),
    ],
)
def test_unknown_observation_identity_fails_closed(compiled_projection, field, value, path):
    result, _ = compiled_projection
    observation = result.initial_request.observation
    observation[field] = value
    request = LLMDecisionRequest(
        decision_number=1,
        observation=observation,
        choices=result.initial_request.choices,
        request_fingerprint="fingerprint",
    )
    with pytest.raises(WorldGenError) as raised:
        build_player_presentation(request, result.projection)
    assert raised.value.code == "UNMAPPED_PLAYER_IDENTITY"
    assert raised.value.issues[0].path == path


def test_unknown_choice_identity_fails_closed(compiled_projection):
    result, _ = compiled_projection
    choice = LLMActionChoice("choice-001", "CHOOSE_BUILD", {"build_id": "unknown-build"}, 1, 0)
    request = LLMDecisionRequest(1, result.initial_request.observation, (choice,), "fingerprint")
    with pytest.raises(WorldGenError) as raised:
        build_player_presentation(request, result.projection)
    assert raised.value.code == "UNMAPPED_PLAYER_IDENTITY"
    assert raised.value.issues[0].path == "/choices/0/params/build_id"


def test_label_change_changes_only_projection_presentation_hash(source_bundle, source_worldpack_hash, valid_projection_draft):
    from tgn.projection import compile_projection

    first = compile_projection(source_bundle, valid_projection_draft)
    changed = copy.deepcopy(valid_projection_draft)
    changed["labels"] = dict(changed["labels"])
    changed["labels"]["phase_day"] = "DAY-ALT"
    second = compile_projection(source_bundle, changed)
    assert first.initial_request.request_fingerprint == second.initial_request.request_fingerprint
    assert first.initial_request.to_dict() == second.initial_request.to_dict()
    assert first.projection_hash != second.projection_hash
    assert first.presentation_hash != second.presentation_hash
    assert state_hash(first.initial_request.observation) == state_hash(second.initial_request.observation)


def test_hash_helpers_are_separate_from_embedded_projection_map(compiled_projection):
    result, _ = compiled_projection
    assert "projection_hash" not in result.projection.to_dict()
    assert projection_hash(result.projection) == result.projection_hash
    assert presentation_hash(result.initial_presentation) == result.presentation_hash


def test_presenter_maps_supported_choice_parameter_identities_and_selected_build(compiled_projection):
    result, _ = compiled_projection
    observation = result.initial_request.observation
    observation["inventory"] = None
    observation["carried_loot"] = {"salvage": 1}
    observation["build"] = copy.deepcopy(observation["build"])
    observation["build"]["selected"] = "quick_rest"
    choices = [
        LLMActionChoice(
            "choice-build",
            "CHOOSE_BUILD",
            {"build_id": "quick_rest"},
            1,
            0,
        ),
        LLMActionChoice(
            "choice-actor",
            "TALK_TO_ACTOR",
            {"actor_id": "mara"},
            5,
            0,
        ),
    ]
    presentation = build_player_presentation(_request(result, observation, choices), result.projection).to_dict()
    assert presentation["observation"]["build"]["selected_display_name"]
    build_display = presentation["choices"][0]["display_params"]
    assert build_display["build_id"]["label"]
    assert build_display["build"]["label"] == build_display["build_id"]["label"]
    actor_display = presentation["choices"][1]["display_params"]
    assert actor_display["actor_id"]["label"]
    assert actor_display["actor"]["label"] == actor_display["actor_id"]["label"]


@pytest.mark.parametrize(
    ("action_type", "params", "path"),
    [
        ("UNKNOWN_ACTION", {}, "/choices/0/action_type"),
        ("WAIT", {"enemy_id": "enemy-1"}, "/choices/0/params/enemy_id"),
        ("CHOOSE_BUILD", {}, "/choices/0/params/build_id"),
        ("TALK_TO_ACTOR", {"actor_id": "mara", "fact_id": "hidden-fact"}, "/choices/0/params/fact_id"),
    ],
)
def test_presenter_fails_closed_on_unsupported_choice_schemas(compiled_projection, action_type, params, path):
    result, _ = compiled_projection
    choice = LLMActionChoice("choice-schema", action_type, params, 1, 0)
    request = LLMDecisionRequest(1, result.initial_request.observation, (choice,), "fingerprint")
    with pytest.raises(WorldGenError) as raised:
        build_player_presentation(request, result.projection)
    assert raised.value.code == "UNSUPPORTED_PRESENTATION_ACTION_SCHEMA"
    assert raised.value.issues[0].path == path


@pytest.mark.parametrize(
    ("action_type", "params"),
    [("CHOOSE_BUILD", {"build_id": "unknown-build"}), ("TALK_TO_ACTOR", {"actor_id": "secret-actor"})],
)
def test_presenter_fails_closed_on_unmapped_supported_choice_identities(compiled_projection, action_type, params):
    result, _ = compiled_projection
    choice = LLMActionChoice("choice-identity", action_type, params, 1, 0)
    request = LLMDecisionRequest(1, result.initial_request.observation, (choice,), "fingerprint")
    with pytest.raises(WorldGenError) as raised:
        build_player_presentation(request, result.projection)
    assert raised.value.code == "UNMAPPED_PLAYER_IDENTITY"


def test_unknown_observation_fields_are_omitted_without_false_failure(compiled_projection):
    result, _ = compiled_projection
    observation = result.initial_request.observation
    observation["future_unreviewed_field"] = {"enemy_id": "enemy-1", "fact_id": "hidden-fact"}
    request = LLMDecisionRequest(1, observation, result.initial_request.choices, "fingerprint")
    presentation = build_player_presentation(request, result.projection).to_dict()
    assert "future_unreviewed_field" not in presentation["observation"]


@pytest.mark.parametrize(
    "mutation",
    ["bad_actor", "bad_facts", "bad_progression", "bad_tracks", "bad_track", "bad_build", "bad_choices", "bad_choice_item", "bad_enemy"],
)
def test_presenter_rejects_malformed_public_shapes(compiled_projection, mutation):
    result, _ = compiled_projection
    observation = result.initial_request.observation
    if mutation == "bad_actor":
        observation["actor"] = []
    elif mutation == "bad_facts":
        observation["actor"] = copy.deepcopy(observation["actor"])
        observation["actor"]["facts"] = []
    elif mutation == "bad_progression":
        observation["progression"] = []
    elif mutation == "bad_tracks":
        observation["progression"] = {"tracks": []}
    elif mutation == "bad_track":
        observation["progression"] = {"tracks": {"player": []}}
    elif mutation == "bad_build":
        observation["build"] = []
    elif mutation == "bad_choices":
        observation["build"] = copy.deepcopy(observation["build"])
        observation["build"]["choices"] = "not-a-list"
    elif mutation == "bad_choice_item":
        observation["build"] = copy.deepcopy(observation["build"])
        observation["build"]["choices"] = [[]]
    elif mutation == "bad_enemy":
        observation["enemy"] = []
    with pytest.raises(WorldGenError) as raised:
        build_player_presentation(_request(result, observation), result.projection)
    assert raised.value.code == "UNMAPPED_PLAYER_IDENTITY"


def test_presenter_rejects_unknown_fact_value_and_enemy_identity(compiled_projection):
    result, _ = compiled_projection
    observation = copy.deepcopy(result.initial_request.observation)
    observation["actor"]["facts"] = {"site-1-condition": "unknown"}
    with pytest.raises(WorldGenError) as fact_error:
        build_player_presentation(_request(result, observation), result.projection)
    assert fact_error.value.issues[0].path.endswith("/value")

    observation = copy.deepcopy(result.initial_request.observation)
    observation["enemy"] = {"enemy_id": "enemy-1", "enemy_hp": 1}
    with pytest.raises(WorldGenError) as enemy_error:
        build_player_presentation(_request(result, observation), result.projection)
    assert enemy_error.value.issues[0].path == "/observation/enemy/enemy_id"

    observation["enemy"] = {"enemy_hp": 1, "enemy_max_hp": 1, "enemy_attack": 1}
    assert build_player_presentation(_request(result, observation), result.projection).to_dict()["observation"]["enemy"]["enemy_hp"] == 1


def test_presenter_type_and_identity_shape_errors(compiled_projection):
    result, _ = compiled_projection
    with pytest.raises(TypeError):
        build_player_presentation({}, result.projection)
    with pytest.raises(TypeError):
        build_player_presentation(result.initial_request, {})

    malformed = copy.deepcopy(result.projection.to_dict())
    malformed["identities"]["actors"]["mara"] = "not-an-actor-map"
    bad_projection = PlayerProjectionMap(**malformed)
    with pytest.raises(WorldGenError):
        build_player_presentation(result.initial_request, bad_projection)


def test_presenter_direct_choice_shape_errors(compiled_projection):
    from tgn.projection.presenter import _map_choice

    result, _ = compiled_projection
    with pytest.raises(WorldGenError):
        _map_choice([], result.projection, 0)
    with pytest.raises(WorldGenError):
        _map_choice({"params": []}, result.projection, 0)
