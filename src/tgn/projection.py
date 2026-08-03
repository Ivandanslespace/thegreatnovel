"""Deterministic player projection and knowledge redaction."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .contracts import EventDraft


def _visible_fact(fact: Mapping[str, Any]) -> bool:
    visibility = fact.get("visibility")
    return visibility in {"public", "player"}


def _redact(value: Any) -> Any:
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        if "visibility" in value and value.get("visibility") not in {"public", "player"}:
            return None
        return {key: redacted for key, item in value.items() if (redacted := _redact(item)) is not None}
    return deepcopy(value)


def _public_world(value: Any) -> Any:
    """Recursively remove private/actor-scoped facts from world projection."""
    if isinstance(value, list):
        return [item for raw in value if (item := _public_world(raw)) is not None]
    if isinstance(value, dict):
        visibility = value.get("visibility")
        if visibility not in (None, "public", "player"):
            return None
        result = {}
        for key, raw in value.items():
            if key in {"process_last_run", "active_actions", "active_processes", "materialized_expansions", "action_counts"} or str(key).startswith("_"):
                continue
            projected = _public_world(raw)
            if projected is not None:
                result[key] = projected
        return result
    return deepcopy(value)


def _player_state(state: Mapping[str, Any]) -> dict[str, Any]:
    campaign = state.get("campaign", {})
    actor_source = state.get("actors", {})
    actors = []
    actor_items = sorted(actor_source.items(), key=lambda item: str(item[0])) if isinstance(actor_source, Mapping) else ()
    for key, raw in actor_items:
        if not isinstance(raw, Mapping):
            continue
        actor = {field: deepcopy(raw[field]) for field in ("id", "name", "role", "location", "trust", "dependence", "fear", "debt") if field in raw}
        actor.setdefault("id", key)
        actors.append(actor)
    return {
        "campaign": {field: deepcopy(campaign[field]) for field in ("status", "turn", "time_minute", "current_tier") if field in campaign},
        "player": deepcopy(dict(state.get("player", {}))),
        "actors": actors,
        "world": _public_world(state.get("world", {})),
        "opportunities": _public_world(state.get("opportunities", {})),
        "unlocks": _public_world(state.get("unlocks", [])),
        "metrics": _public_world(state.get("metrics", {})),
    }


def _facts_from_events(events: Any) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for event_index, event in enumerate(events or ()):
        raw_facts = event.facts if isinstance(event, EventDraft) else event.get("facts", ())
        for fact_index, raw in enumerate(raw_facts):
            fact = deepcopy(dict(raw))
            fact.setdefault("fact_id", f"event:{event_index}:{fact_index}")
            if _visible_fact(fact):
                facts.append(fact)
    return facts


def project_player_view(compiled: Mapping[str, Any], state: Mapping[str, Any], events: Any = ()) -> dict[str, Any]:
    from .engine.core import legal_actions, state_hash

    player = deepcopy(dict(state.get("player", {})))
    panel = {
        "control_deficit": compiled.get("control_deficit"),
        "absolute_power": player.get("absolute_power", state.get("metrics", {}).get("absolute_power", 0)),
        "effective_capacity": player.get("effective_capacity", state.get("metrics", {}).get("effective_capacity", 0)),
        "relative_standing": player.get("relative_standing", state.get("metrics", {}).get("relative_standing", 0)),
        "current_tier": state.get("campaign", {}).get("current_tier", 0),
        "turn": state.get("campaign", {}).get("turn", 0),
        "time_minute": state.get("campaign", {}).get("time_minute", 0),
    }
    facts = _facts_from_events(events)
    # `truth` intentionally carries only an integrity digest and counts.  Raw
    # hidden facts belong to the engine, never to a player-facing projection.
    actor_knowledge = {
        "viewer": "player",
        "known_fact_ids": [fact["fact_id"] for fact in facts],
    }
    observation = {
        "state": _player_state(state),
        "facts": facts,
        "legal_actions": legal_actions(compiled, state),
    }
    return {
        "state_hash": state_hash(state),
        "truth": {"state_hash": state_hash(state), "fact_count": len(facts)},
        "actor_knowledge": actor_knowledge,
        "player_observation": observation,
        "panel": panel,
        "facts": facts,
        "legal_actions": observation["legal_actions"],
    }
