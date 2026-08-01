"""Pure mapping from a detached Phase 8 request to player-facing labels."""

from __future__ import annotations

import copy
from typing import Any

from ..llm_player.models import LLMDecisionRequest
from ..worldgen.models import WorldGenError
from .common import assert_canonical_utf8, error, issue
from .models import PlayerPresentation, PlayerProjectionMap


def _unmapped(path: str, identity: Any) -> WorldGenError:
    return error(
        "UNMAPPED_PLAYER_IDENTITY",
        "player-visible canonical identity is not present in the projection map",
        issues=(
            issue(
                "UNMAPPED_PLAYER_IDENTITY",
                path,
                "canonical identity has no approved display mapping",
                "mapped identity",
                identity,
            ),
        ),
    )


def _identity(mapping: dict[str, Any], value: Any, path: str) -> Any:
    if not isinstance(value, str) or value not in mapping:
        raise _unmapped(path, value)
    return mapping[value]


def _resource_entries(values: Any, identities: dict[str, Any], path: str) -> list[dict[str, Any]]:
    if values is None:
        return []
    if not isinstance(values, dict):
        raise _unmapped(path, type(values).__name__)
    entries: list[dict[str, Any]] = []
    for resource_id in sorted(values):
        label = _identity(identities, resource_id, f"{path}/{resource_id}")
        entries.append(
            {
                "resource_id": resource_id,
                "label": label,
                "quantity": copy.deepcopy(values[resource_id]),
            }
        )
    return entries


def _map_fact(
    fact_id: Any,
    value: Any,
    facts: dict[str, Any],
    path: str,
) -> dict[str, Any]:
    fact = facts.get(fact_id) if isinstance(fact_id, str) else None
    if not isinstance(fact_id, str) or not isinstance(fact, dict):
        raise _unmapped(path, fact_id)
    values = fact.get("values")
    if not isinstance(values, dict) or not isinstance(value, str) or value not in values:
        raise _unmapped(f"{path}/value", value)
    return {
        "fact_id": fact_id,
        "subject": fact.get("subject"),
        "value": value,
        "value_label": values[value],
    }


def _map_actor(actor: Any, identities: dict[str, Any], path: str) -> dict[str, Any]:
    if not isinstance(actor, dict):
        raise _unmapped(path, type(actor).__name__)
    actor_id = actor.get("actor_id")
    actor_map = _identity(identities.get("actors", {}), actor_id, f"{path}/actor_id")
    if not isinstance(actor_map, dict):
        raise _unmapped(f"{path}/actor_id", actor_id)
    result: dict[str, Any] = {
        "actor_id": actor_id,
        "canonical_name": copy.deepcopy(actor.get("name")),
        "name": copy.deepcopy(actor_map.get("name")),
        "display_name": copy.deepcopy(actor_map.get("name")),
        "role": copy.deepcopy(actor_map.get("role")),
        "last_known_location_id": actor.get("last_known_location_id"),
        "last_known_location_label": _identity(
            identities.get("locations", {}),
            actor.get("last_known_location_id"),
            f"{path}/last_known_location_id",
        ),
        "last_known_location": {
            "id": actor.get("last_known_location_id"),
            "label": _identity(
                identities.get("locations", {}),
                actor.get("last_known_location_id"),
                f"{path}/last_known_location_id",
            ),
        },
        "known_goal": actor.get("known_goal"),
        "known_goal_label": _identity(
            identities.get("actor_goals", {}),
            actor.get("known_goal"),
            f"{path}/known_goal",
        ),
        "known_goal_display": {
            "id": actor.get("known_goal"),
            "label": _identity(
                identities.get("actor_goals", {}),
                actor.get("known_goal"),
                f"{path}/known_goal",
            ),
        },
        "trust": copy.deepcopy(actor.get("trust")),
        "visible": copy.deepcopy(actor.get("visible")),
        "has_something_to_report": copy.deepcopy(actor.get("has_something_to_report")),
    }
    public_facts = actor.get("facts", {})
    if not isinstance(public_facts, dict):
        raise _unmapped(f"{path}/facts", type(public_facts).__name__)
    mapped_facts: dict[str, Any] = {}
    for fact_id in sorted(public_facts):
        mapped_facts[fact_id] = _map_fact(
            fact_id,
            public_facts[fact_id],
            identities.get("facts", {}),
            f"{path}/facts/{fact_id}",
        )
    result["facts"] = mapped_facts
    return result


def _map_progression(value: Any, identities: dict[str, Any], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _unmapped(path, type(value).__name__)
    tracks = value.get("tracks", {})
    if not isinstance(tracks, dict):
        raise _unmapped(f"{path}/tracks", type(tracks).__name__)
    result_tracks: dict[str, Any] = {}
    resources = identities.get("resources", {})
    for track_id in sorted(tracks):
        track = tracks[track_id]
        if not isinstance(track, dict):
            raise _unmapped(f"{path}/tracks/{track_id}", type(track).__name__)
        result_tracks[track_id] = {
            "track_id": track_id,
            "label": _identity(identities.get("progression_tracks", {}), track_id, f"{path}/tracks/{track_id}"),
            "stage": copy.deepcopy(track.get("stage")),
            "next_cost": copy.deepcopy(track.get("next_cost", {})),
            "next_cost_display": _resource_entries(
                track.get("next_cost", {}), resources, f"{path}/tracks/{track_id}/next_cost"
            ),
        }
    return {"tracks": result_tracks}


def _map_build(value: Any, identities: dict[str, Any], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _unmapped(path, type(value).__name__)
    result: dict[str, Any] = {
        "selected": copy.deepcopy(value.get("selected")),
        "choice_available": copy.deepcopy(value.get("choice_available")),
        "selection_rule": copy.deepcopy(value.get("selection_rule")),
    }
    selected = value.get("selected")
    if selected is not None:
        result["selected_display_name"] = _identity(
            identities.get("builds", {}), selected, f"{path}/selected"
        )
    choices = value.get("choices", [])
    if not isinstance(choices, list):
        raise _unmapped(f"{path}/choices", type(choices).__name__)
    mapped_choices: list[dict[str, Any]] = []
    for index, choice in enumerate(choices):
        if not isinstance(choice, dict):
            raise _unmapped(f"{path}/choices/{index}", type(choice).__name__)
        build_id = choice.get("build_id")
        mapped = copy.deepcopy(choice)
        mapped["display_name"] = _identity(
            identities.get("builds", {}), build_id, f"{path}/choices/{index}/build_id"
        )
        mapped_choices.append(mapped)
    result["choices"] = mapped_choices
    return result


def _display_params(params: dict[str, Any], identities: dict[str, Any], path: str) -> dict[str, Any]:
    display: dict[str, Any] = {}
    for key, value in params.items():
        if key == "location_id":
            display[key] = {
                "id": value,
                "label": _identity(identities.get("locations", {}), value, f"{path}/params/{key}"),
            }
            display["location"] = copy.deepcopy(display[key])
        elif key == "resource_id":
            display[key] = {
                "id": value,
                "label": _identity(identities.get("resources", {}), value, f"{path}/params/{key}"),
            }
            display["resource"] = copy.deepcopy(display[key])
        elif key == "actor_id":
            actor = _identity(identities.get("actors", {}), value, f"{path}/params/{key}")
            display[key] = {"id": value, "label": actor.get("name") if isinstance(actor, dict) else actor}
            display["actor"] = copy.deepcopy(display[key])
        elif key == "build_id":
            display[key] = {
                "id": value,
                "label": _identity(identities.get("builds", {}), value, f"{path}/params/{key}"),
            }
            display["build"] = copy.deepcopy(display[key])
        elif key == "track_id":
            display[key] = {
                "id": value,
                "label": _identity(identities.get("progression_tracks", {}), value, f"{path}/params/{key}"),
            }
            display["track"] = copy.deepcopy(display[key])
        elif key == "phase":
            display[key] = {
                "id": value,
                "label": _identity(identities.get("world_phases", {}), value, f"{path}/params/{key}"),
            }
            display["world_phase"] = copy.deepcopy(display[key])
        else:
            display[key] = copy.deepcopy(value)
    return display


def _map_choice(choice: Any, projection: PlayerProjectionMap, index: int) -> dict[str, Any]:
    if not isinstance(choice, dict):
        raise _unmapped(f"/choices/{index}", type(choice).__name__)
    result = copy.deepcopy(choice)
    params = choice.get("params", {})
    if not isinstance(params, dict):
        raise _unmapped(f"/choices/{index}/params", type(params).__name__)
    result["display_params"] = _display_params(params, projection.identities, f"/choices/{index}")
    return result


def _map_observation(observation: dict[str, Any], projection: PlayerProjectionMap) -> dict[str, Any]:
    identities = projection.identities
    result: dict[str, Any] = {}
    for field in (
        "game_minute",
        "stamina",
        "max_stamina",
        "hp",
        "max_hp",
        "expedition_active",
        "target_searched",
        "minutes_until_phase_change",
    ):
        if field in observation:
            result[field] = copy.deepcopy(observation[field])

    if "location_id" in observation:
        location_id = observation["location_id"]
        result["location_id"] = location_id
        location_label = _identity(identities.get("locations", {}), location_id, "/observation/location_id")
        result["location_label"] = location_label
        result["location"] = {"id": location_id, "label": location_label}

    if "inventory" in observation:
        result["inventory"] = _resource_entries(
            observation["inventory"], identities.get("resources", {}), "/observation/inventory"
        )
    if "carried_loot" in observation:
        result["carried_loot"] = _resource_entries(
            observation["carried_loot"], identities.get("resources", {}), "/observation/carried_loot"
        )

    if "world_phase" in observation:
        phase = observation["world_phase"]
        phase_label = _identity(identities.get("world_phases", {}), phase, "/observation/world_phase")
        result["world_phase_id"] = phase
        result["world_phase"] = {"id": phase, "label": phase_label}
        result["world_phase_label"] = phase_label

    if "progression" in observation:
        result["progression"] = _map_progression(observation["progression"], identities, "/observation/progression")
    if "actor" in observation:
        result["actor"] = _map_actor(observation["actor"], identities, "/observation/actor")
    if "build" in observation:
        result["build"] = _map_build(observation["build"], identities, "/observation/build")
    if "enemy" in observation:
        enemy = observation["enemy"]
        if not isinstance(enemy, dict):
            raise _unmapped("/observation/enemy", type(enemy).__name__)
        # The explicit Phase 9B2A map has no enemy identity binding. Failing
        # closed is safer than silently displaying an unmapped canonical ID.
        if "enemy_id" in enemy:
            raise _unmapped("/observation/enemy/enemy_id", enemy["enemy_id"])
        result["enemy"] = {
            key: copy.deepcopy(enemy[key])
            for key in ("enemy_hp", "enemy_max_hp", "enemy_attack")
            if key in enemy
        }
    return result


def build_player_presentation(
    request: LLMDecisionRequest,
    projection: PlayerProjectionMap,
) -> PlayerPresentation:
    """Map public canonical identities without reading state or changing choices."""

    if not isinstance(request, LLMDecisionRequest):
        raise TypeError("request must be LLMDecisionRequest")
    if not isinstance(projection, PlayerProjectionMap):
        raise TypeError("projection must be PlayerProjectionMap")
    choices = tuple(
        _map_choice(choice.to_dict(), projection, index)
        for index, choice in enumerate(request.choices)
    )
    presentation = PlayerPresentation(
        schema_version=projection.schema_version,
        source_worldpack_hash=projection.source_worldpack_hash,
        request_fingerprint=request.request_fingerprint,
        content_locale=projection.content_locale,
        world=copy.deepcopy(projection.world),
        observation=_map_observation(request.observation, projection),
        choices=choices,
    )
    assert_canonical_utf8(presentation.to_dict())
    return presentation


__all__ = ["build_player_presentation"]
