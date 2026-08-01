"""The first WorldPack's minimal named-actor vertical slice.

This module intentionally contains the concrete Mara slice rather than a
general actor, relationship, or knowledge framework.  The reducer is the only
caller allowed to apply the autonomous consequence or conversation result.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from ..core.models import DomainEvent, GameState


# Explicit first-slice content.  These names stay out of tgn.core.
MARA_ACTOR_ID = "mara"
MARA_NAME = "Mara"
MARA_INITIAL_LOCATION_ID = "base-1"
MARA_INITIAL_GOAL = "inspect_signal"
MARA_REPORT_GOAL = "report_finding"
MARA_REPORTED_GOAL = "reported"
MARA_AUTONOMOUS_ACTION = "INSPECT_SIGNAL"
MARA_FACT_ID = "site-1-condition"
MARA_FACT_VALUES = frozenset({"unstable", "safe"})
TALK_TO_ACTOR = "TALK_TO_ACTOR"
ACTOR_CONVERSATION_RESOLVED = "ACTOR_CONVERSATION_RESOLVED"
TALK_TO_ACTOR_TIME = 5

_FEATURE_KEYS = ("named_actor", "world_facts", "player_knowledge")
_KNOWN_GOALS = frozenset({MARA_INITIAL_GOAL, MARA_REPORT_GOAL, MARA_REPORTED_GOAL})


@dataclass(frozen=True)
class NamedActorDecisionView:
    """The complete input permitted to the local actor decision function."""

    location_id: str
    goal: str
    knowledge: dict[str, Any]
    player_present: bool
    game_minute: int


def named_actor_feature_enabled(state: GameState) -> bool:
    """Return whether all three local Phase 7.5 state sections are present."""

    return all(key in state.data for key in _FEATURE_KEYS)


def validate_named_actor_state(state: GameState) -> None:
    """Validate the explicit first-slice state, or accept a legacy state."""

    present = [key in state.data for key in _FEATURE_KEYS]
    if not any(present):
        return
    if not all(present):
        raise ValueError(
            "named actor feature requires named_actor, world_facts, and player_knowledge"
        )

    data = state.data
    named_actor = _require_dict(data["named_actor"], "named_actor")
    world_facts = _require_dict(data["world_facts"], "world_facts")
    player_knowledge = _require_dict(data["player_knowledge"], "player_knowledge")

    if set(world_facts) != {MARA_FACT_ID}:
        raise ValueError("world_facts must contain only the local condition fact")
    fact_value = world_facts[MARA_FACT_ID]
    if fact_value not in MARA_FACT_VALUES:
        raise ValueError("world_facts local condition must be 'unstable' or 'safe'")

    if named_actor.get("actor_id") != MARA_ACTOR_ID:
        raise ValueError("named_actor.actor_id must be 'mara'")
    if named_actor.get("name") != MARA_NAME:
        raise ValueError("named_actor.name must be 'Mara'")
    _require_string(named_actor.get("location_id"), "named_actor.location_id")

    goal = named_actor.get("goal")
    if goal not in _KNOWN_GOALS:
        raise ValueError(f"named_actor.goal must be one of {sorted(_KNOWN_GOALS)}")

    relationship = _require_dict(named_actor.get("relationship"), "named_actor.relationship")
    trust = relationship.get("trust")
    if isinstance(trust, bool) or not isinstance(trust, int):
        raise ValueError("named_actor.relationship.trust must be int, not bool")
    if trust not in (0, 1):
        raise ValueError("named_actor.relationship.trust must be 0 or 1")

    knowledge = _require_dict(named_actor.get("knowledge"), "named_actor.knowledge")
    _validate_fact_mapping(knowledge, world_facts, "named_actor.knowledge")

    last_action = named_actor.get("last_autonomous_action")
    if last_action not in (None, MARA_AUTONOMOUS_ACTION):
        raise ValueError(
            "named_actor.last_autonomous_action must be None or INSPECT_SIGNAL"
        )

    player = _require_dict(data.get("player"), "player")
    _require_string(player.get("location_id"), "player.location_id")
    exp = _require_dict(data.get("expedition"), "expedition")
    if not isinstance(exp.get("active"), bool):
        raise ValueError("expedition.active must be bool")
    encounter = exp.get("encounter")
    if encounter is not None and not isinstance(encounter, dict):
        raise ValueError("expedition.encounter must be dict or absent")

    facts = _require_dict(player_knowledge.get("facts"), "player_knowledge.facts")
    _validate_fact_mapping(facts, world_facts, "player_knowledge.facts")
    actors = _require_dict(player_knowledge.get("actors"), "player_knowledge.actors")
    mara_knowledge = _require_dict(actors.get(MARA_ACTOR_ID), "player_knowledge.actors.mara")
    if mara_knowledge.get("name") != MARA_NAME:
        raise ValueError("player_knowledge.actors.mara.name must be 'Mara'")
    _require_string(
        mara_knowledge.get("last_known_location_id"),
        "player_knowledge.actors.mara.last_known_location_id",
    )
    known_goal = mara_knowledge.get("known_goal")
    if known_goal not in (MARA_INITIAL_GOAL, MARA_REPORTED_GOAL):
        raise ValueError(
            "player_knowledge.actors.mara.known_goal must be inspect_signal or reported"
        )

    if goal == MARA_INITIAL_GOAL:
        _validate_initial_state(trust, knowledge, facts, known_goal, last_action)
    elif goal == MARA_REPORT_GOAL:
        _validate_report_ready_state(
            trust, knowledge, facts, known_goal, last_action, fact_value
        )
    else:
        _validate_reported_state(
            trust, knowledge, facts, known_goal, last_action, fact_value
        )


def build_actor_decision_view(state: GameState) -> NamedActorDecisionView:
    """Build a decision input without passing world truth to the actor policy."""

    actor = state.data["named_actor"]
    player = state.data["player"]
    return NamedActorDecisionView(
        location_id=actor["location_id"],
        goal=actor["goal"],
        knowledge=copy.deepcopy(actor["knowledge"]),
        player_present=player["location_id"] == actor["location_id"],
        game_minute=state.game_minute,
    )


def decide_named_actor_action(view: NamedActorDecisionView) -> str | None:
    """Choose from actor-local state only; hidden world truth is not an input."""

    if view.player_present:
        return None
    if view.goal == MARA_INITIAL_GOAL and MARA_FACT_ID not in view.knowledge:
        return MARA_AUTONOMOUS_ACTION
    return None


def apply_named_actor_autonomous_consequence(state: GameState) -> bool:
    """Apply one local autonomous step after an accepted time-advancing event.

    Phase 7.5 treats the autonomous actor step as a deterministic consequence
    of the triggering time-advancing event. Separate actor events and atomic
    multi-event decisions remain deferred.
    """

    if not named_actor_feature_enabled(state):
        return False

    view = build_actor_decision_view(state)
    decision = decide_named_actor_action(view)
    if decision != MARA_AUTONOMOUS_ACTION:
        return False

    fact_value = state.data["world_facts"].get(MARA_FACT_ID)
    if fact_value is None:
        return False

    actor = state.data["named_actor"]
    actor["knowledge"][MARA_FACT_ID] = fact_value
    actor["goal"] = MARA_REPORT_GOAL
    actor["last_autonomous_action"] = MARA_AUTONOMOUS_ACTION
    return True


def can_talk_to_actor(state: GameState, actor_id: str) -> bool:
    """Return whether the one local report interaction is currently legal."""

    if not named_actor_feature_enabled(state) or actor_id != MARA_ACTOR_ID:
        return False
    player = state.data.get("player", {})
    if player.get("hp", 1) <= 0:
        return False
    actor = state.data["named_actor"]
    if player.get("location_id") != actor.get("location_id"):
        return False
    exp = state.data.get("expedition", {})
    encounter = exp.get("encounter")
    if encounter and encounter.get("active"):
        return False
    if actor.get("goal") != MARA_REPORT_GOAL:
        return False
    if MARA_FACT_ID not in actor.get("knowledge", {}):
        return False
    if MARA_FACT_ID in state.data["player_knowledge"].get("facts", {}):
        return False
    return True


def apply_actor_conversation_resolved(state: GameState, event: DomainEvent) -> None:
    """Validate and apply the authoritative report conversation event."""

    payload = event.payload
    actor_id = payload.get("actor_id")
    if not can_talk_to_actor(state, actor_id):
        raise ValueError("conversation is not legal for the current actor/state")
    if payload.get("time") != TALK_TO_ACTOR_TIME:
        raise ValueError("conversation time cost must be 5")
    if event.game_minute != state.game_minute + TALK_TO_ACTOR_TIME:
        raise ValueError("conversation game_minute does not match authoritative cost")

    actor = state.data["named_actor"]
    trust_before = actor["relationship"]["trust"]
    if payload.get("trust_before") != trust_before:
        raise ValueError("forged trust_before")
    if payload.get("trust_after") != trust_before + 1:
        raise ValueError("forged trust_after")
    if payload.get("shared_fact_ids") != [MARA_FACT_ID]:
        raise ValueError("forged shared_fact_ids")

    fact_value = actor["knowledge"].get(MARA_FACT_ID)
    if fact_value is None:
        raise ValueError("Mara cannot share a fact she does not know")

    actor["relationship"]["trust"] = trust_before + 1
    actor["goal"] = MARA_REPORTED_GOAL
    state.data["player_knowledge"]["facts"][MARA_FACT_ID] = fact_value
    state.data["player_knowledge"]["actors"][MARA_ACTOR_ID]["known_goal"] = MARA_REPORTED_GOAL
    state.game_minute += TALK_TO_ACTOR_TIME


def build_actor_observation(state: GameState) -> dict[str, Any]:
    """Return only the player's projection of the local named actor."""

    actor = state.data["named_actor"]
    player = state.data["player"]
    player_knowledge = state.data["player_knowledge"]
    known_actor = player_knowledge["actors"][MARA_ACTOR_ID]
    visible = player["location_id"] == actor["location_id"]
    has_report = (
        visible
        and actor["goal"] == MARA_REPORT_GOAL
        and MARA_FACT_ID in actor["knowledge"]
        and MARA_FACT_ID not in player_knowledge["facts"]
    )
    return {
        "actor_id": MARA_ACTOR_ID,
        "name": known_actor["name"],
        "last_known_location_id": known_actor["last_known_location_id"],
        "known_goal": known_actor["known_goal"],
        "trust": actor["relationship"]["trust"],
        "visible": visible,
        "has_something_to_report": has_report,
        "facts": copy.deepcopy(player_knowledge["facts"]),
    }


def count_knowledge_boundary_violations(
    state: GameState, observation: dict[str, Any]
) -> int:
    """Check the explicit Mara projection against Player Knowledge."""

    if not named_actor_feature_enabled(state):
        return 0

    allowed_fields = {
        "actor_id",
        "name",
        "last_known_location_id",
        "known_goal",
        "trust",
        "visible",
        "has_something_to_report",
        "facts",
    }
    violations = 0
    actor_observation = observation.get("actor")
    if not isinstance(actor_observation, dict):
        violations += 1
        actor_observation = {}
    else:
        violations += len(set(actor_observation) - allowed_fields)
        expected_actor = build_actor_observation(state)
        for field in allowed_fields:
            if actor_observation.get(field) != expected_actor.get(field):
                violations += 1

    for forbidden in (
        "world_facts",
        "private_knowledge",
        "last_autonomous_action",
        "private_goal",
    ):
        if forbidden in observation or forbidden in actor_observation:
            violations += 1
    return violations


def named_actor_metric_delta(before: GameState, after: GameState) -> dict[str, int]:
    """Return the four scripted-autoplay metrics for this local feature."""

    before_actor = before.data.get("named_actor", {})
    after_actor = after.data.get("named_actor", {})
    before_pk = before.data.get("player_knowledge", {})
    after_pk = after.data.get("player_knowledge", {})
    before_facts = before_pk.get("facts", {})
    after_facts = after_pk.get("facts", {})
    before_trust = before_actor.get("relationship", {}).get("trust")
    after_trust = after_actor.get("relationship", {}).get("trust")
    return {
        "actor_autonomous_actions": int(
            before_actor.get("last_autonomous_action") is None
            and after_actor.get("last_autonomous_action") == MARA_AUTONOMOUS_ACTION
        ),
        "knowledge_transfers": int(
            MARA_FACT_ID not in before_facts and MARA_FACT_ID in after_facts
        ),
        "relationship_changes": int(before_trust == 0 and after_trust == 1),
    }


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be dict, got {type(value).__name__}")
    return value


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be non-empty string")
    return value


def _validate_fact_mapping(
    mapping: dict[str, Any], world_facts: dict[str, Any], path: str
) -> None:
    if not set(mapping).issubset({MARA_FACT_ID}):
        raise ValueError(f"{path} contains an unsupported fact")
    for fact_id, value in mapping.items():
        if value != world_facts.get(fact_id):
            raise ValueError(f"{path}.{fact_id} does not match world truth")


def _validate_initial_state(
    trust: int,
    knowledge: dict[str, Any],
    facts: dict[str, Any],
    known_goal: str,
    last_action: str | None,
) -> None:
    """Validate the one exact pre-inspection state of this local slice."""

    if trust != 0 or knowledge or facts or last_action is not None:
        raise ValueError(
            "initial inspect_signal requires trust=0, empty knowledge, empty facts, "
            "and no autonomous action"
        )
    if known_goal != MARA_INITIAL_GOAL:
        raise ValueError("initial inspect_signal requires known_goal=inspect_signal")


def _validate_report_ready_state(
    trust: int,
    knowledge: dict[str, Any],
    facts: dict[str, Any],
    known_goal: str,
    last_action: str | None,
    fact_value: Any,
) -> None:
    """Validate the one exact post-inspection, pre-report state."""

    expected_knowledge = {MARA_FACT_ID: fact_value}
    if trust != 0 or knowledge != expected_knowledge or facts:
        raise ValueError(
            "report_finding requires trust=0, the current inspected fact, and no "
            "player fact"
        )
    if known_goal != MARA_INITIAL_GOAL:
        raise ValueError("report_finding requires known_goal=inspect_signal")
    if last_action != MARA_AUTONOMOUS_ACTION:
        raise ValueError("report_finding requires the autonomous inspection result")


def _validate_reported_state(
    trust: int,
    knowledge: dict[str, Any],
    facts: dict[str, Any],
    known_goal: str,
    last_action: str | None,
    fact_value: Any,
) -> None:
    """Validate the one exact post-report state of this local slice."""

    expected_facts = {MARA_FACT_ID: fact_value}
    if trust != 1 or knowledge != expected_facts or facts != expected_facts:
        raise ValueError(
            "reported requires trust=1 and the current fact in both knowledge maps"
        )
    if known_goal != MARA_REPORTED_GOAL:
        raise ValueError("reported requires known_goal=reported")
    if last_action != MARA_AUTONOMOUS_ACTION:
        raise ValueError("reported requires the autonomous inspection result")
