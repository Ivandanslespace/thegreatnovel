"""The bounded Phase 10A ``devour_evolution`` gameplay slice.

This module deliberately owns the feature-local state contract.  Core and the
expedition action system call the small public helpers below; they do not grow
a generic capability registry or effect dispatcher.
"""

from __future__ import annotations

from typing import Any

from ..core.models import DomainEvent, GameState


DEVOUR_EVOLUTION_CAPABILITY_ID = "devour_evolution"
DEVOUR_EVOLUTION_LABEL = "Devour Evolution"
DEVOUR_EVOLUTION_GRANT_ID = "player_devour_evolution_genesis"
DEVOUR_EVOLUTION_HOLDER_ID = "player"
DEVOUR_EVOLUTION_SOURCE_KIND = "world_genesis"
DEVOUR_EVOLUTION_SOURCE_ID = "protagonist_core_gift"

DEVOUR_REMAINS = "DEVOUR_REMAINS"
DEVOUR_RESOLVED = "DEVOUR_RESOLVED"

DEVOUR_TIME = 20
DEVOUR_STAMINA_COST = 1
DEVOUR_ESSENCE_GAIN = 1

_GRANT_FIELDS = {
    "holder_id",
    "capability_id",
    "source_kind",
    "source_id",
    "acquired_event_seq",
}
_YIELD_FIELDS = {"capability_id", "essence", "consumed"}
_EVENT_FIELDS = {
    "capability_id",
    "grant_id",
    "enemy_id",
    "essence_before",
    "essence_gained",
    "essence_after",
    "time",
    "stamina_cost",
}


def _feature_present(state: GameState) -> bool:
    data = state.data if isinstance(state, GameState) else {}
    expedition = data.get("expedition")
    encounter = expedition.get("encounter") if isinstance(expedition, dict) else None
    return (
        any(key in data for key in ("capability_grants", "devour_evolution"))
        or (isinstance(encounter, dict) and "devour_yield" in encounter)
    )


def _strict_int(value: Any) -> bool:
    return type(value) is int


def validate_devour_evolution_state(state: GameState) -> None:
    """Validate the exact local Phase 10A state, or accept a legacy state.

    A legacy state has none of the three feature sections.  Once one section
    appears, all sections must be complete and mutually consistent.
    """

    if not isinstance(state, GameState):
        raise ValueError("state must be GameState")
    if not _feature_present(state):
        return

    data = state.data
    grants = data.get("capability_grants")
    if not isinstance(grants, dict) or set(grants) != {DEVOUR_EVOLUTION_GRANT_ID}:
        raise ValueError("capability_grants must contain the exact genesis grant")
    grant = grants.get(DEVOUR_EVOLUTION_GRANT_ID)
    if not isinstance(grant, dict) or set(grant) != _GRANT_FIELDS:
        raise ValueError("genesis grant has an invalid field set")
    expected_grant = {
        "holder_id": DEVOUR_EVOLUTION_HOLDER_ID,
        "capability_id": DEVOUR_EVOLUTION_CAPABILITY_ID,
        "source_kind": DEVOUR_EVOLUTION_SOURCE_KIND,
        "source_id": DEVOUR_EVOLUTION_SOURCE_ID,
        "acquired_event_seq": 0,
    }
    if grant != expected_grant or not _strict_int(grant["acquired_event_seq"]):
        raise ValueError("genesis grant does not match the Phase 10A contract")

    local = data.get("devour_evolution")
    if not isinstance(local, dict) or set(local) != {"essence"}:
        raise ValueError("devour_evolution has an invalid field set")
    essence = local.get("essence")
    if not _strict_int(essence) or essence < 0:
        raise ValueError("devour_evolution.essence must be a non-negative integer")

    expedition = data.get("expedition")
    encounter = expedition.get("encounter") if isinstance(expedition, dict) else None
    if not isinstance(encounter, dict):
        raise ValueError("Phase 10A requires an expedition encounter")
    devour_yield = encounter.get("devour_yield")
    if not isinstance(devour_yield, dict) or set(devour_yield) != _YIELD_FIELDS:
        raise ValueError("devour_yield has an invalid field set")
    if devour_yield.get("capability_id") != DEVOUR_EVOLUTION_CAPABILITY_ID:
        raise ValueError("devour_yield capability_id is unsupported")
    if not _strict_int(devour_yield.get("essence")) or devour_yield.get("essence") != 1:
        raise ValueError("devour_yield essence must be exactly 1")
    if type(devour_yield.get("consumed")) is not bool:
        raise ValueError("devour_yield.consumed must be bool")


def devour_evolution_enabled(state: GameState) -> bool:
    """Return whether any Phase 10A state is present."""

    return _feature_present(state)


def player_owns_devour_evolution(state: GameState) -> bool:
    """Return ownership without turning ordinary legality checks into errors."""

    try:
        validate_devour_evolution_state(state)
    except Exception:
        return False
    grants = state.data.get("capability_grants", {})
    grant = grants.get(DEVOUR_EVOLUTION_GRANT_ID)
    return isinstance(grant, dict) and grant.get("holder_id") == DEVOUR_EVOLUTION_HOLDER_ID


def can_devour_remains(state: GameState) -> bool:
    """Return whether the one explicit Phase 10A action is currently legal."""

    try:
        validate_devour_evolution_state(state)
        if not player_owns_devour_evolution(state):
            return False
        data = state.data
        player = data.get("player")
        expedition = data.get("expedition")
        if not isinstance(player, dict) or not isinstance(expedition, dict):
            return False
        if player.get("hp", 1) <= 0 or not expedition.get("active"):
            return False
        if player.get("location_id") != expedition.get("target_location_id"):
            return False
        encounter = expedition.get("encounter")
        if not isinstance(encounter, dict):
            return False
        if encounter.get("enemy_hp") != 0 or encounter.get("active") is not False:
            return False
        devour_yield = encounter.get("devour_yield")
        if not isinstance(devour_yield, dict):
            return False
        if devour_yield.get("capability_id") != DEVOUR_EVOLUTION_CAPABILITY_ID:
            return False
        if devour_yield.get("essence") != DEVOUR_ESSENCE_GAIN:
            return False
        if devour_yield.get("consumed") is not False:
            return False
        stamina = player.get("stamina")
        return _strict_int(stamina) and stamina >= DEVOUR_STAMINA_COST
    except Exception:
        return False


def build_devour_capability_observation(state: GameState) -> list[dict[str, str]]:
    """Return only the public identity of the owned genesis Capability."""

    if not player_owns_devour_evolution(state):
        return []
    return [
        {
            "capability_id": DEVOUR_EVOLUTION_CAPABILITY_ID,
            "label": DEVOUR_EVOLUTION_LABEL,
            "source_kind": DEVOUR_EVOLUTION_SOURCE_KIND,
        }
    ]


def build_devour_event_payload(state: GameState) -> dict[str, Any]:
    """Build the authoritative payload from the current state."""

    if not can_devour_remains(state):
        raise ValueError("DEVOUR_REMAINS is not legal in the current state")
    encounter = state.data["expedition"]["encounter"]
    essence_before = state.data["devour_evolution"]["essence"]
    return {
        "capability_id": DEVOUR_EVOLUTION_CAPABILITY_ID,
        "grant_id": DEVOUR_EVOLUTION_GRANT_ID,
        "enemy_id": encounter["enemy_id"],
        "essence_before": essence_before,
        "essence_gained": DEVOUR_ESSENCE_GAIN,
        "essence_after": essence_before + DEVOUR_ESSENCE_GAIN,
        "time": DEVOUR_TIME,
        "stamina_cost": DEVOUR_STAMINA_COST,
    }


def apply_devour_resolved(state: GameState, event: DomainEvent) -> None:
    """Validate and apply exactly one ``DEVOUR_RESOLVED`` event."""

    validate_devour_evolution_state(state)
    if event.event_type != DEVOUR_RESOLVED:
        raise ValueError("event type is not DEVOUR_RESOLVED")
    payload = event.payload
    if not isinstance(payload, dict) or set(payload) != _EVENT_FIELDS:
        raise ValueError("DEVOUR_RESOLVED payload has an invalid field set")
    if not can_devour_remains(state):
        raise ValueError("DEVOUR_REMAINS is not legal in the current state")

    encounter = state.data["expedition"]["encounter"]
    player = state.data["player"]
    essence_before = state.data["devour_evolution"]["essence"]
    expected = build_devour_event_payload(state)
    if payload != expected:
        raise ValueError("DEVOUR_RESOLVED payload does not match authoritative state")
    if type(event.game_minute) is not int or event.game_minute != state.game_minute + DEVOUR_TIME:
        raise ValueError("DEVOUR_RESOLVED game_minute does not match the fixed cost")
    if type(payload["essence_before"]) is not int or type(payload["essence_after"]) is not int:
        raise ValueError("essence payload values must be strict integers")
    if type(payload["essence_gained"]) is not int or type(payload["time"]) is not int:
        raise ValueError("DEVOUR_RESOLVED numeric payload values must be integers")
    if type(payload["stamina_cost"]) is not int:
        raise ValueError("stamina_cost must be a strict integer")

    player["stamina"] -= DEVOUR_STAMINA_COST
    state.game_minute += DEVOUR_TIME
    state.data["devour_evolution"]["essence"] = essence_before + DEVOUR_ESSENCE_GAIN
    encounter["devour_yield"]["consumed"] = True


__all__ = [
    "DEVOUR_EVOLUTION_CAPABILITY_ID",
    "DEVOUR_EVOLUTION_GRANT_ID",
    "DEVOUR_EVOLUTION_HOLDER_ID",
    "DEVOUR_EVOLUTION_LABEL",
    "DEVOUR_EVOLUTION_SOURCE_ID",
    "DEVOUR_EVOLUTION_SOURCE_KIND",
    "DEVOUR_ESSENCE_GAIN",
    "DEVOUR_REMAINS",
    "DEVOUR_RESOLVED",
    "DEVOUR_STAMINA_COST",
    "DEVOUR_TIME",
    "apply_devour_resolved",
    "build_devour_capability_observation",
    "build_devour_event_payload",
    "can_devour_remains",
    "devour_evolution_enabled",
    "player_owns_devour_evolution",
    "validate_devour_evolution_state",
]
