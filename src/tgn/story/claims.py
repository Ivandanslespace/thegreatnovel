"""Bounded deterministic claim requirements for Story turns."""

from __future__ import annotations

import copy
from typing import Any

from .common import canonical_bytes, strict_int, validate_json_value, validate_stable_id


CLAIM_KINDS = frozenset(
    {
        "action_performed",
        "location_changed",
        "resource_delta",
        "stamina_changed",
        "public_fact_revealed",
        "relationship_public_change",
        "terminal_reason",
    }
)
CLAIM_VALUE_FIELDS = {
    "action_performed": {"choice_id", "action_type"},
    "location_changed": {"from_location_id", "to_location_id"},
    "resource_delta": {"scope", "resource_id", "delta"},
    "stamina_changed": {"before", "after", "delta"},
    "public_fact_revealed": {"fact_id", "value"},
    "relationship_public_change": {"actor_id", "relationship_id", "before", "after"},
    "terminal_reason": {"reason"},
}
MAX_CLAIMS = 32


def _claim(kind: str, value: dict[str, Any]) -> dict[str, Any]:
    return {"kind": kind, "value": copy.deepcopy(value)}


def _resource_map(value: Any) -> dict[str, int]:
    if value is None:
        return {}
    if isinstance(value, dict):
        result: dict[str, int] = {}
        for resource_id, quantity in value.items():
            if not isinstance(resource_id, str) or type(quantity) is not int:
                raise ValueError("resource observation is invalid")
            result[resource_id] = quantity
        return result
    if not isinstance(value, list):
        raise ValueError("resource observation is invalid")
    result = {}
    for item in value:
        if not isinstance(item, dict) or set(item) - {"resource_id", "label", "quantity"} != set() or set(item) != {"resource_id", "label", "quantity"}:
            raise ValueError("resource presentation entry is invalid")
        resource_id = item["resource_id"]
        quantity = item["quantity"]
        if not isinstance(resource_id, str) or type(quantity) is not int or resource_id in result:
            raise ValueError("resource presentation entry is invalid")
        result[resource_id] = quantity
    return result


def _actor_facts(observation: dict[str, Any]) -> dict[str, Any]:
    actor = observation.get("actor")
    if not isinstance(actor, dict):
        return {}
    facts = actor.get("facts", {})
    if not isinstance(facts, dict):
        raise ValueError("public actor facts are invalid")
    result: dict[str, Any] = {}
    for fact_id, item in facts.items():
        if not isinstance(fact_id, str):
            raise ValueError("public fact id is invalid")
        if isinstance(item, dict) and "value" in item:
            value = item["value"]
        else:
            value = item
        validate_json_value(value)
        if isinstance(value, (dict, list, tuple)):
            raise ValueError("public fact value must be scalar")
        result[fact_id] = copy.deepcopy(value)
    return result


def _sort_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (copy.deepcopy(item) for item in claims),
        key=lambda item: (item["kind"], canonical_bytes(item["value"])),
    )


def derive_claim_requirements(
    observation_before: dict[str, Any],
    observation_after: dict[str, Any],
    *,
    choice_id: str,
    action_type: str,
    terminal_reason: str | None = None,
) -> list[dict[str, Any]]:
    """Derive the complete bounded claim set from public before/after data."""

    if not isinstance(observation_before, dict) or not isinstance(observation_after, dict):
        raise ValueError("public observations must be objects")
    if not isinstance(choice_id, str) or not isinstance(action_type, str):
        raise ValueError("action identity is invalid")
    claims: list[dict[str, Any]] = [
        _claim("action_performed", {"choice_id": choice_id, "action_type": action_type})
    ]
    before_location = observation_before.get("location_id")
    after_location = observation_after.get("location_id")
    if before_location != after_location:
        if not isinstance(before_location, str) or not isinstance(after_location, str):
            raise ValueError("public location identity is invalid")
        claims.append(
            _claim(
                "location_changed",
                {"from_location_id": before_location, "to_location_id": after_location},
            )
        )

    before_stamina = observation_before.get("stamina")
    after_stamina = observation_after.get("stamina")
    if before_stamina != after_stamina:
        strict_int(before_stamina, "observation_before.stamina")
        strict_int(after_stamina, "observation_after.stamina")
        claims.append(
            _claim(
                "stamina_changed",
                {
                    "before": before_stamina,
                    "after": after_stamina,
                    "delta": after_stamina - before_stamina,
                },
            )
        )

    before_inventory = _resource_map(observation_before.get("inventory", {}))
    after_inventory = _resource_map(observation_after.get("inventory", {}))
    before_carried = _resource_map(observation_before.get("carried_loot", {}))
    after_carried = _resource_map(observation_after.get("carried_loot", {}))
    for scope, before_values, after_values in (
        ("inventory", before_inventory, after_inventory),
        ("carried", before_carried, after_carried),
    ):
        for resource_id in sorted(set(before_values) | set(after_values)):
            delta = after_values.get(resource_id, 0) - before_values.get(resource_id, 0)
            if delta:
                claims.append(
                    _claim(
                        "resource_delta",
                        {"scope": scope, "resource_id": resource_id, "delta": delta},
                    )
                )

    before_facts = _actor_facts(observation_before)
    after_facts = _actor_facts(observation_after)
    for fact_id in sorted(set(after_facts) - set(before_facts)):
        claims.append(
            _claim("public_fact_revealed", {"fact_id": fact_id, "value": after_facts[fact_id]})
        )

    before_actor = observation_before.get("actor")
    after_actor = observation_after.get("actor")
    before_trust = before_actor.get("trust") if isinstance(before_actor, dict) else None
    after_trust = after_actor.get("trust") if isinstance(after_actor, dict) else None
    if before_trust != after_trust and before_trust is not None and after_trust is not None:
        strict_int(before_trust, "observation_before.actor.trust")
        strict_int(after_trust, "observation_after.actor.trust")
        actor_id = after_actor.get("actor_id") if isinstance(after_actor, dict) else None
        if not isinstance(actor_id, str):
            raise ValueError("public relationship actor id is invalid")
        claims.append(
            _claim(
                "relationship_public_change",
                {
                    "actor_id": actor_id,
                    "relationship_id": "trust",
                    "before": before_trust,
                    "after": after_trust,
                },
            )
        )

    if terminal_reason is not None:
        if terminal_reason not in {"MAX_DECISIONS", "NO_LEGAL_ACTIONS"}:
            raise ValueError("unsupported terminal reason")
        claims.append(_claim("terminal_reason", {"reason": terminal_reason}))
    result = _sort_claims(claims)
    if len(result) > MAX_CLAIMS:
        raise ValueError("claim requirements exceed bounded limit")
    return result


def _validate_claim_shape(claim: Any) -> dict[str, Any]:
    if not isinstance(claim, dict) or set(claim) != {"kind", "value"}:
        raise ValueError("claim has an invalid field set")
    kind = claim["kind"]
    if not isinstance(kind, str) or kind not in CLAIM_KINDS:
        raise ValueError("claim kind is unsupported")
    value = claim["value"]
    if not isinstance(value, dict) or set(value) != CLAIM_VALUE_FIELDS[kind]:
        raise ValueError("claim value has an invalid field set")
    validate_json_value(value)
    if kind == "resource_delta":
        if value["scope"] not in {"inventory", "carried"} or not isinstance(value["resource_id"], str):
            raise ValueError("resource claim scope or id is invalid")
        strict_int(value["delta"], "resource_delta.delta")
        if value["delta"] == 0:
            raise ValueError("resource claim delta must be non-zero")
    elif kind == "stamina_changed":
        for field in ("before", "after", "delta"):
            strict_int(value[field], f"stamina_changed.{field}")
        if value["delta"] != value["after"] - value["before"]:
            raise ValueError("stamina claim delta is invalid")
    elif kind == "location_changed":
        validate_stable_id(value["from_location_id"], "from_location_id")
        validate_stable_id(value["to_location_id"], "to_location_id")
    elif kind == "action_performed":
        if not isinstance(value["choice_id"], str) or not isinstance(value["action_type"], str):
            raise ValueError("action claim identity is invalid")
    elif kind == "public_fact_revealed":
        validate_stable_id(value["fact_id"], "fact_id")
        if isinstance(value["value"], (dict, list, tuple)):
            raise ValueError("fact claim value must be scalar")
    elif kind == "relationship_public_change":
        validate_stable_id(value["actor_id"], "actor_id")
        if value["relationship_id"] != "trust":
            raise ValueError("relationship claim kind is unsupported")
        strict_int(value["before"], "relationship_public_change.before")
        strict_int(value["after"], "relationship_public_change.after")
    elif kind == "terminal_reason":
        if value["reason"] not in {"MAX_DECISIONS", "NO_LEGAL_ACTIONS"}:
            raise ValueError("terminal reason is unsupported")
    return copy.deepcopy(claim)


def validate_claims(claims: Any, requirements: Any) -> list[dict[str, Any]]:
    """Require an exact, duplicate-free response claim set."""

    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise ValueError("claims exceed bounded schema")
    if not isinstance(requirements, list) or len(requirements) > MAX_CLAIMS:
        raise ValueError("claim requirements are invalid")
    normalized = [_validate_claim_shape(item) for item in claims]
    expected = [_validate_claim_shape(item) for item in requirements]
    normalized_sorted = _sort_claims(normalized)
    expected_sorted = _sort_claims(expected)
    if len({canonical_bytes(item) for item in normalized_sorted}) != len(normalized_sorted):
        raise ValueError("duplicate claim")
    if normalized_sorted != expected_sorted:
        raise ValueError("claims do not exactly satisfy requirements")
    return normalized_sorted


__all__ = [
    "CLAIM_KINDS",
    "MAX_CLAIMS",
    "derive_claim_requirements",
    "validate_claims",
]
