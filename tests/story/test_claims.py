from __future__ import annotations

import pytest

from tgn.story.claims import derive_claim_requirements, validate_claims


def test_claim_scopes_and_exact_set() -> None:
    before = {
        "location_id": "base-1",
        "stamina": 3,
        "inventory": [{"resource_id": "salvage", "label": "x", "quantity": 1}],
        "carried_loot": [{"resource_id": "salvage", "label": "x", "quantity": 0}],
        "actor": {"actor_id": "mara", "trust": 0, "facts": {}},
    }
    after = {
        "location_id": "site-1",
        "stamina": 2,
        "inventory": [{"resource_id": "salvage", "label": "x", "quantity": 2}],
        "carried_loot": [{"resource_id": "salvage", "label": "x", "quantity": 1}],
        "actor": {"actor_id": "mara", "trust": 1, "facts": {"site-1-condition": {"value": "safe"}}},
    }
    claims = derive_claim_requirements(before, after, choice_id="choice-001", action_type="DROP")
    assert {item["value"].get("scope") for item in claims if item["kind"] == "resource_delta"} == {"inventory", "carried"}
    assert any(item["kind"] == "relationship_public_change" and item["value"]["relationship_id"] == "trust" for item in claims)
    assert validate_claims(claims, claims) == claims
    with pytest.raises(ValueError):
        validate_claims(claims[:-1], claims)


def test_claim_derivation_only_emits_public_changes() -> None:
    before = {
        "location_id": "base-1",
        "stamina": 3,
        "inventory": {"salvage": 1},
        "carried_loot": {"salvage": 0},
        "actor": {"actor_id": "mara", "trust": 0, "facts": {}},
    }
    unchanged = {
        **before,
        "private": {"hidden_goal": "escape", "knowledge": ["secret"]},
        "actor": {"actor_id": "mara", "trust": 0, "facts": {}},
    }
    action_only = derive_claim_requirements(
        before, unchanged, choice_id="choice-001", action_type="DROP"
    )
    assert action_only == [
        {"kind": "action_performed", "value": {"choice_id": "choice-001", "action_type": "DROP"}}
    ]

    after = {
        "location_id": "site-1",
        "stamina": 2,
        "inventory": {"salvage": 2, "metal": 1},
        "carried_loot": {"salvage": 1},
        "actor": {
            "actor_id": "mara",
            "trust": 2,
            "facts": {"site-1-condition": {"value": "safe"}},
        },
    }
    claims = derive_claim_requirements(
        before,
        after,
        choice_id="choice-001",
        action_type="DROP",
        terminal_reason="MAX_DECISIONS",
    )
    kinds = [item["kind"] for item in claims]
    assert kinds == sorted(kinds)
    assert {item["value"]["resource_id"] for item in claims if item["kind"] == "resource_delta"} == {"salvage", "metal"}
    assert any(item["kind"] == "location_changed" for item in claims)
    assert any(item["kind"] == "stamina_changed" and item["value"]["delta"] == -1 for item in claims)
    assert any(item["kind"] == "public_fact_revealed" for item in claims)
    assert any(item["kind"] == "terminal_reason" for item in claims)

    no_legal = derive_claim_requirements(
        before,
        after,
        choice_id="choice-001",
        action_type="DROP",
        terminal_reason="NO_LEGAL_ACTIONS",
    )
    assert {item["value"].get("reason") for item in no_legal if item["kind"] == "terminal_reason"} == {"NO_LEGAL_ACTIONS"}


def test_claim_validation_rejects_shape_scope_values_and_duplicates() -> None:
    requirement = [
        {"kind": "action_performed", "value": {"choice_id": "choice-001", "action_type": "DROP"}}
    ]
    invalid_claims = [
        [{"kind": "unknown", "value": {}}],
        [{"kind": "action_performed", "value": {"choice_id": "choice-001"}}],
        [{"kind": "resource_delta", "value": {"scope": "hidden", "resource_id": "salvage", "delta": 1}}],
        [{"kind": "resource_delta", "value": {"scope": "inventory", "resource_id": "salvage", "delta": 0}}],
        [{"kind": "stamina_changed", "value": {"before": 3, "after": 2, "delta": 3}}],
        [{"kind": "location_changed", "value": {"from_location_id": "Bad", "to_location_id": "site-1"}}],
        [{"kind": "public_fact_revealed", "value": {"fact_id": "fact-1", "value": {"private": True}}}],
        [{"kind": "relationship_public_change", "value": {"actor_id": "mara", "relationship_id": "fear", "before": 0, "after": 1}}],
        [{"kind": "terminal_reason", "value": {"reason": "EXPLICIT_STOP"}}],
    ]
    for claims in invalid_claims:
        with pytest.raises(ValueError):
            validate_claims(claims, requirement)

    duplicate = requirement + requirement
    with pytest.raises(ValueError):
        validate_claims(duplicate, duplicate)
    with pytest.raises(ValueError):
        validate_claims([], requirement)
    with pytest.raises(ValueError):
        validate_claims(requirement + [{"kind": "action_performed", "value": {"choice_id": "choice-002", "action_type": "DROP"}}], requirement)


def test_claim_derivation_rejects_bad_public_observations() -> None:
    base = {"location_id": "base-1", "stamina": 3, "inventory": {}, "carried_loot": {}}
    with pytest.raises(ValueError):
        derive_claim_requirements([], base, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "inventory": {"salvage": True}}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "actor": {"facts": {"secret": {"value": {"x": 1}}}}}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "location_id": 3}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "stamina": "2"}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, base, choice_id="choice-001", action_type="DROP", terminal_reason="TERMINAL_STATE")


def test_claim_observation_and_bound_limits() -> None:
    base = {"location_id": "base-1", "stamina": 3, "inventory": {}, "carried_loot": {}}
    assert derive_claim_requirements(base, {**base, "inventory": None}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "inventory": ["bad"]}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "inventory": [{"resource_id": "x", "quantity": 1}]}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "inventory": [{"resource_id": "x", "label": "x", "quantity": 1}, {"resource_id": "x", "label": "x", "quantity": 2}]}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "inventory": 5}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "actor": {"facts": []}}, choice_id="choice-001", action_type="DROP")
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "actor": {"facts": {1: "bad"}}}, choice_id="choice-001", action_type="DROP")
    scalar_claims = derive_claim_requirements(
        base,
        {**base, "actor": {"facts": {"fact-1": "scalar"}}},
        choice_id="choice-001",
        action_type="DROP",
    )
    assert any(item["kind"] == "public_fact_revealed" for item in scalar_claims)
    with pytest.raises(ValueError):
        derive_claim_requirements(
            {**base, "actor": {"trust": 0}},
            {**base, "actor": {"trust": 1}},
            choice_id="choice-001",
            action_type="DROP",
        )
    with pytest.raises(ValueError):
        derive_claim_requirements(base, base, choice_id=1, action_type="DROP")

    many = {"resource-%02d" % number: 1 for number in range(33)}
    with pytest.raises(ValueError):
        derive_claim_requirements(base, {**base, "inventory": many}, choice_id="choice-001", action_type="DROP")

    requirement = [{"kind": "action_performed", "value": {"choice_id": "choice-001", "action_type": "DROP"}}]
    with pytest.raises(ValueError):
        validate_claims([{"kind": "action_performed"}], requirement)
    with pytest.raises(ValueError):
        validate_claims([requirement[0]] * 33, requirement)
    with pytest.raises(ValueError):
        validate_claims(requirement, requirement * 33)
