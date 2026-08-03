from __future__ import annotations

from dataclasses import replace
import builtins
import socket
import sqlite3
import subprocess

import pytest

from tgn.genesis import (
    CLAIM_SUPPLY_CACHE,
    DEFAULT_CATALOG,
    EVENT_CACHE_CLAIMED,
    EVENT_GROWTH_UPGRADED,
    EVENT_HAZARD_TRAVERSED,
    EVENT_RESOURCE_RECOVERED,
    EVENT_SUPPLY_STABILIZED,
    ExclusiveUpgradeAction,
    ExclusiveUpgradeEvent,
    ExclusiveUpgradePressureConfig,
    ExclusiveUpgradePressureState,
    PressureValidationError,
    PRESSURE_FEATURE_ID,
    RECOVER_EXCLUSIVE_RESOURCE,
    RESOURCE_SPENT_SUPPLY_ROUTE,
    RESOURCE_SPENT_UPGRADE,
    STABILIZE_SUPPLY_ROUTE,
    TRAVERSE_HAZARD_ZONE,
    UPGRADE_GROWTH_OBJECT,
    check_pressure_invariants,
    initial_pressure_state,
    legal_pressure_actions,
    pressure_event_hash,
    pressure_state_hash,
    project_pressure_observation,
    reduce_pressure_event,
    replay_pressure_events,
    resolve_pressure_action,
    verify_terminal_pressure_trace,
)


def _action(state: ExclusiveUpgradePressureState, action_id: str, config: ExclusiveUpgradePressureConfig, actor_id: str | None = None) -> ExclusiveUpgradeAction:
    return ExclusiveUpgradeAction(action_id, actor_id or config.protagonist_id, state.decision_seq + 1)


def _apply(
    state: ExclusiveUpgradePressureState,
    action_id: str,
    config: ExclusiveUpgradePressureConfig,
) -> tuple[ExclusiveUpgradePressureState, ExclusiveUpgradeEvent]:
    action = _action(state, action_id, config)
    event = resolve_pressure_action(state, action, config)
    return reduce_pressure_event(state, event, config), event


def _recover(state: ExclusiveUpgradePressureState, config: ExclusiveUpgradePressureConfig):
    return _apply(state, RECOVER_EXCLUSIVE_RESOURCE, config)


def _policy_a(config: ExclusiveUpgradePressureConfig):
    state = initial_pressure_state(config)
    events = []
    for action_id in (RECOVER_EXCLUSIVE_RESOURCE, UPGRADE_GROWTH_OBJECT, TRAVERSE_HAZARD_ZONE):
        state, event = _apply(state, action_id, config)
        events.append(event)
    return state, tuple(events)


def _policy_b(config: ExclusiveUpgradePressureConfig):
    state = initial_pressure_state(config)
    events = []
    for action_id in (RECOVER_EXCLUSIVE_RESOURCE, STABILIZE_SUPPLY_ROUTE, CLAIM_SUPPLY_CACHE):
        state, event = _apply(state, action_id, config)
        events.append(event)
    return state, tuple(events)


def test_config_and_initial_state_are_strict_and_detached():
    config = ExclusiveUpgradePressureConfig()
    assert ExclusiveUpgradePressureConfig.from_dict(config.to_dict()) == config
    assert config.hash == ExclusiveUpgradePressureConfig.from_dict(config.to_dict()).hash

    exported_config = config.to_dict()
    exported_config["feature_id"] = "runtime.other"
    with pytest.raises(PressureValidationError):
        ExclusiveUpgradePressureConfig.from_dict(exported_config)

    unknown = config.to_dict()
    unknown["unknown_field"] = True
    with pytest.raises(PressureValidationError) as error:
        ExclusiveUpgradePressureConfig.from_dict(unknown)
    assert error.value.code == "INVALID_ACTION"

    state = initial_pressure_state(config)
    assert check_pressure_invariants(state, config) is True
    assert state.growth_level == 0
    assert state.common_material_count >= 10
    assert state.exclusive_resource_count == 0
    assert state.exclusive_resource_source_available is True
    assert state.game_minute == config.initial_game_minute
    assert pressure_state_hash(state) == pressure_state_hash(ExclusiveUpgradePressureState.from_dict(state.to_dict()))

    exported_state = state.to_dict()
    exported_state["common_material_count"] = 999
    assert state.common_material_count != exported_state["common_material_count"]

    wrong_config_state = replace(state, config_hash="0" * 64)
    with pytest.raises(PressureValidationError) as error:
        check_pressure_invariants(wrong_config_state, config)
    assert error.value.code == "CONFIG_HASH_MISMATCH"


def test_config_requires_both_complete_pressure_paths():
    base = ExclusiveUpgradePressureConfig()
    maximum_required = max(base.required_growth_stamina, base.required_supply_stamina)
    exact = replace(base, initial_stamina=maximum_required)
    assert exact.initial_stamina == maximum_required
    assert exact.required_growth_stamina == base.required_growth_stamina
    assert exact.required_supply_stamina == base.required_supply_stamina

    under = base.to_dict()
    under["initial_stamina"] = maximum_required - 1
    with pytest.raises(PressureValidationError) as error:
        ExclusiveUpgradePressureConfig.from_dict(under)
    assert error.value.code == "INVARIANT_VIOLATION"

    recovery_only = base.to_dict()
    recovery_only.update(
        {
            "initial_stamina": 5,
            "recover_stamina_cost": 5,
            "upgrade_stamina_cost": 3,
            "traverse_stamina_cost": 3,
        }
    )
    with pytest.raises(PressureValidationError) as error:
        ExclusiveUpgradePressureConfig.from_dict(recovery_only)
    assert error.value.code == "INVARIANT_VIOLATION"


def test_all_schema_decoders_reject_non_string_keys_stably():
    config = ExclusiveUpgradePressureConfig()
    initial = initial_pressure_state(config)
    _, event = _recover(initial, config)
    decoders_and_payloads = (
        (ExclusiveUpgradePressureConfig.from_dict, config.to_dict()),
        (ExclusiveUpgradePressureState.from_dict, initial.to_dict()),
        (ExclusiveUpgradeAction.from_dict, _action(initial, RECOVER_EXCLUSIVE_RESOURCE, config).to_dict()),
        (ExclusiveUpgradeEvent.from_dict, event.to_dict()),
    )
    for decoder, payload in decoders_and_payloads:
        malformed = dict(payload)
        malformed[("tuple-key",)] = "invalid"
        with pytest.raises(PressureValidationError) as error:
            decoder(malformed)
        assert error.value.code == "INVALID_ACTION"


def test_action_strict_schema_and_initial_legality():
    config = ExclusiveUpgradePressureConfig()
    state = initial_pressure_state(config)
    assert legal_pressure_actions(state, config.protagonist_id, config) == (RECOVER_EXCLUSIVE_RESOURCE,)
    assert legal_pressure_actions(state, "actor.other", config) == ()

    malformed = _action(state, RECOVER_EXCLUSIVE_RESOURCE, config).to_dict()
    malformed["params"] = {}
    with pytest.raises(PressureValidationError) as error:
        ExclusiveUpgradeAction.from_dict(malformed)
    assert error.value.code == "INVALID_ACTION"

    mixed_key_schema = _action(state, RECOVER_EXCLUSIVE_RESOURCE, config).to_dict()
    mixed_key_schema[1] = "invalid-key"
    with pytest.raises(PressureValidationError) as error:
        ExclusiveUpgradeAction.from_dict(mixed_key_schema)
    assert error.value.code == "INVALID_ACTION"

    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(
            state,
            _action(state, UPGRADE_GROWTH_OBJECT, config),
            config,
        )
    assert error.value.code == "ORDINARY_RESOURCE_FALLBACK_FORBIDDEN"

    outsider_upgrade = _action(state, UPGRADE_GROWTH_OBJECT, config, "actor.other")
    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(state, outsider_upgrade, config)
    assert error.value.code == "NOT_GROWTH_OBJECT_OWNER"

    wrong_sequence = ExclusiveUpgradeAction(RECOVER_EXCLUSIVE_RESOURCE, config.protagonist_id, 2)
    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(state, wrong_sequence, config)
    assert error.value.code == "DECISION_SEQUENCE_MISMATCH"

    low_stamina = replace(state, stamina=1)
    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(low_stamina, _action(low_stamina, RECOVER_EXCLUSIVE_RESOURCE, config), config)
    assert error.value.code == "INVARIANT_VIOLATION"


def test_recovery_is_single_use_and_does_not_mutate_input():
    config = ExclusiveUpgradePressureConfig()
    state = initial_pressure_state(config)
    next_state, event = _recover(state, config)
    assert event.event_type == EVENT_RESOURCE_RECOVERED
    assert next_state.exclusive_resource_count == 1
    assert next_state.exclusive_resource_source_available is False
    assert next_state.exclusive_resource_spent_on == "NONE"
    assert next_state.game_minute == state.game_minute + config.recover_duration
    assert state.exclusive_resource_count == 0
    assert state.event_seq == 0

    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(next_state, _action(next_state, RECOVER_EXCLUSIVE_RESOURCE, config), config)
    assert error.value.code == "EXCLUSIVE_RESOURCE_ALREADY_HELD"

    spent_state, _ = _apply(next_state, STABILIZE_SUPPLY_ROUTE, config)
    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(spent_state, _action(spent_state, RECOVER_EXCLUSIVE_RESOURCE, config), config)
    assert error.value.code == "EXCLUSIVE_RESOURCE_SOURCE_CLOSED"


def test_each_legal_action_has_typed_event_and_reducer_proof():
    config = ExclusiveUpgradePressureConfig()
    state = initial_pressure_state(config)
    action = _action(state, RECOVER_EXCLUSIVE_RESOURCE, config)
    event = resolve_pressure_action(state, action, config)
    assert event.event_seq == 1
    assert event.decision_seq == 1
    assert event.actor_id == action.actor_id
    assert event.action_id == action.action_id
    assert event.before_state_hash == pressure_state_hash(state)
    assert event.event_hash == pressure_event_hash(event)
    after = reduce_pressure_event(state, event, config)
    assert event.after_state_hash == pressure_state_hash(after)
    assert after.event_seq == state.event_seq + 1
    assert after.decision_seq == state.decision_seq + 1

    assert event.to_dict()["event_type"] == EVENT_RESOURCE_RECOVERED
    assert event.to_dict()["resource_delta"] == 1
    assert event.to_dict()["stamina_delta"] == -config.recover_stamina_cost
    assert event.to_dict()["game_minute_delta"] == config.recover_duration


def test_event_tampering_and_sequence_gaps_are_rejected():
    config = ExclusiveUpgradePressureConfig()
    state, event = _recover(initial_pressure_state(config), config)

    tampered_payload = replace(event, resource_delta=0)
    with pytest.raises(PressureValidationError) as error:
        reduce_pressure_event(initial_pressure_state(config), tampered_payload, config)
    assert error.value.code == "EVENT_HASH_MISMATCH"

    tampered_payload = replace(event, resource_delta=0)
    tampered_payload = replace(tampered_payload, event_hash=pressure_event_hash(tampered_payload))
    with pytest.raises(PressureValidationError) as error:
        reduce_pressure_event(initial_pressure_state(config), tampered_payload, config)
    assert error.value.code == "INVALID_EVENT_PAYLOAD"

    wrong_config = replace(event, config_hash="0" * 64)
    with pytest.raises(PressureValidationError) as error:
        reduce_pressure_event(initial_pressure_state(config), wrong_config, config)
    assert error.value.code == "CONFIG_HASH_MISMATCH"

    wrong_before = replace(event, before_state_hash="0" * 64)
    with pytest.raises(PressureValidationError) as error:
        reduce_pressure_event(initial_pressure_state(config), wrong_before, config)
    assert error.value.code == "STATE_HASH_MISMATCH"

    wrong_after = replace(event, after_state_hash="0" * 64)
    wrong_after = replace(wrong_after, event_hash=pressure_event_hash(wrong_after))
    with pytest.raises(PressureValidationError) as error:
        reduce_pressure_event(initial_pressure_state(config), wrong_after, config)
    assert error.value.code == "STATE_HASH_MISMATCH"

    wrong_seq = replace(event, event_seq=3)
    with pytest.raises(PressureValidationError) as error:
        reduce_pressure_event(initial_pressure_state(config), wrong_seq, config)
    assert error.value.code == "EVENT_SEQUENCE_MISMATCH"

    assert state.event_seq == 1
    assert state.exclusive_resource_count == 1


def test_branch_legality_and_exclusive_commitment():
    config = ExclusiveUpgradePressureConfig()
    recovered, _ = _recover(initial_pressure_state(config), config)
    assert set(legal_pressure_actions(recovered, config.protagonist_id, config)) == {
        UPGRADE_GROWTH_OBJECT,
        STABILIZE_SUPPLY_ROUTE,
    }
    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(recovered, _action(recovered, TRAVERSE_HAZARD_ZONE, config), config)
    assert error.value.code == "FOLLOWUP_NOT_UNLOCKED"

    upgraded, upgrade_event = _apply(recovered, UPGRADE_GROWTH_OBJECT, config)
    assert upgrade_event.event_type == EVENT_GROWTH_UPGRADED
    assert upgraded.exclusive_resource_spent_on == RESOURCE_SPENT_UPGRADE
    assert upgraded.exclusive_resource_count == 0
    assert upgraded.growth_level == 1
    assert upgraded.hazard_traversal_unlocked is True
    assert STABILIZE_SUPPLY_ROUTE not in legal_pressure_actions(upgraded, config.protagonist_id, config)
    assert TRAVERSE_HAZARD_ZONE in legal_pressure_actions(upgraded, config.protagonist_id, config)

    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(upgraded, _action(upgraded, STABILIZE_SUPPLY_ROUTE, config), config)
    assert error.value.code == "BRANCH_ALREADY_COMMITTED"
    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(upgraded, _action(upgraded, UPGRADE_GROWTH_OBJECT, config), config)
    assert error.value.code == "EXCLUSIVE_RESOURCE_ALREADY_COMMITTED"

    stabilized, stabilize_event = _apply(recovered, STABILIZE_SUPPLY_ROUTE, config)
    assert stabilize_event.event_type == EVENT_SUPPLY_STABILIZED
    assert stabilized.exclusive_resource_spent_on == RESOURCE_SPENT_SUPPLY_ROUTE
    assert stabilized.supply_route_stabilized is True
    assert stabilized.growth_level == 0
    assert CLAIM_SUPPLY_CACHE in legal_pressure_actions(stabilized, config.protagonist_id, config)
    assert UPGRADE_GROWTH_OBJECT not in legal_pressure_actions(stabilized, config.protagonist_id, config)


def test_policy_a_and_b_are_real_mutually_exclusive_strategy_traces():
    config = ExclusiveUpgradePressureConfig()
    final_a, events_a = _policy_a(config)
    final_b, events_b = _policy_b(config)

    assert [event.action_id for event in events_a] == [
        RECOVER_EXCLUSIVE_RESOURCE,
        UPGRADE_GROWTH_OBJECT,
        TRAVERSE_HAZARD_ZONE,
    ]
    assert [event.action_id for event in events_b] == [
        RECOVER_EXCLUSIVE_RESOURCE,
        STABILIZE_SUPPLY_ROUTE,
        CLAIM_SUPPLY_CACHE,
    ]
    assert all(event.event_type in {EVENT_RESOURCE_RECOVERED, EVENT_GROWTH_UPGRADED, EVENT_HAZARD_TRAVERSED} for event in events_a)
    assert all(event.event_type in {EVENT_RESOURCE_RECOVERED, EVENT_SUPPLY_STABILIZED, EVENT_CACHE_CLAIMED} for event in events_b)
    assert final_a.exclusive_resource_count == 0
    assert final_b.exclusive_resource_count == 0
    assert final_a.exclusive_resource_spent_on == RESOURCE_SPENT_UPGRADE
    assert final_b.exclusive_resource_spent_on == RESOURCE_SPENT_SUPPLY_ROUTE
    assert final_a.hazard_zone_traversed is True
    assert final_b.supply_cache_claimed is True
    assert final_a.common_material_count == config.initial_common_material_count
    assert final_b.common_material_count == config.initial_common_material_count + config.supply_cache_material_reward
    assert pressure_state_hash(final_a) != pressure_state_hash(final_b)
    assert tuple(event.event_hash for event in events_a) != tuple(event.event_hash for event in events_b)
    assert legal_pressure_actions(final_a, config.protagonist_id, config) == ()
    assert legal_pressure_actions(final_b, config.protagonist_id, config) == ()

    ordinary_material_rich = initial_pressure_state(config)
    assert ordinary_material_rich.common_material_count >= 10
    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(ordinary_material_rich, _action(ordinary_material_rich, UPGRADE_GROWTH_OBJECT, config), config)
    assert error.value.code == "ORDINARY_RESOURCE_FALLBACK_FORBIDDEN"


def test_removing_exclusive_resource_semantics_changes_legal_actions_and_cost():
    config = ExclusiveUpgradePressureConfig()
    state = initial_pressure_state(config)
    enabled_actions = set(legal_pressure_actions(state, config.protagonist_id, config))

    # Counterfactual A/B baseline: if the exclusive-resource requirement were
    # removed, the already-owned ordinary material would make the upgrade
    # directly legal and consume one ordinary material. This is a test oracle,
    # not a second runtime path: the production slice must keep that action
    # unavailable until the dedicated recovery action has closed its source.
    removed_resource_baseline = {
        "legal_action_ids": (UPGRADE_GROWTH_OBJECT,),
        "reachable_growth_level": 1,
        "common_material_count_after": state.common_material_count - 1,
        "ordinary_material_cost": 1,
    }
    assert set(removed_resource_baseline["legal_action_ids"]) != enabled_actions
    assert UPGRADE_GROWTH_OBJECT not in enabled_actions
    assert UPGRADE_GROWTH_OBJECT in removed_resource_baseline["legal_action_ids"]
    assert removed_resource_baseline["reachable_growth_level"] > state.growth_level
    assert removed_resource_baseline["common_material_count_after"] < state.common_material_count
    assert removed_resource_baseline["ordinary_material_cost"] > 0
    with pytest.raises(PressureValidationError) as error:
        resolve_pressure_action(state, _action(state, UPGRADE_GROWTH_OBJECT, config), config)
    assert error.value.code == "ORDINARY_RESOURCE_FALLBACK_FORBIDDEN"


def test_replay_accepts_prefixes_and_terminal_verify_rejects_incomplete_or_corrupt_traces():
    config = ExclusiveUpgradePressureConfig()
    final_a, events_a = _policy_a(config)
    initial = initial_pressure_state(config)
    replayed_initial = replay_pressure_events(initial, (), config)
    assert replayed_initial.to_dict() == initial.to_dict()

    recovered = replay_pressure_events(initial, events_a[:1], config)
    assert recovered.exclusive_resource_count == 1
    assert recovered.exclusive_resource_source_available is False
    assert recovered.event_seq == 1
    assert recovered.event_seq == events_a[0].event_seq

    upgraded = replay_pressure_events(initial, events_a[:2], config)
    assert upgraded.exclusive_resource_spent_on == RESOURCE_SPENT_UPGRADE
    assert upgraded.growth_level == 1
    assert upgraded.hazard_traversal_unlocked is True
    assert upgraded.hazard_zone_traversed is False
    assert upgraded.event_seq == 2

    replayed = replay_pressure_events(initial, events_a, config)
    assert pressure_state_hash(replayed) == pressure_state_hash(final_a)
    assert replayed.to_dict() == final_a.to_dict()
    verified = verify_terminal_pressure_trace(initial, events_a, config, pressure_state_hash(final_a))
    assert verified.to_dict() == final_a.to_dict()

    final_b, events_b = _policy_b(config)
    supply_committed = replay_pressure_events(initial, events_b[:2], config)
    assert supply_committed.exclusive_resource_spent_on == RESOURCE_SPENT_SUPPLY_ROUTE
    assert supply_committed.supply_route_stabilized is True
    assert supply_committed.supply_cache_claimed is False
    assert verify_terminal_pressure_trace(initial, events_b, config, pressure_state_hash(final_b)).to_dict() == final_b.to_dict()

    corrupted_initial = replace(initial, exclusive_resource_source_available=False)
    with pytest.raises(PressureValidationError) as error:
        replay_pressure_events(corrupted_initial, (), config)
    assert error.value.code == "INVARIANT_VIOLATION"

    final_again, events_again = _policy_a(config)
    assert final_again.to_dict() == final_a.to_dict()
    assert [event.to_dict() for event in events_again] == [event.to_dict() for event in events_a]

    with pytest.raises(PressureValidationError) as error:
        replay_pressure_events(initial, events_a[1:], config)
    assert error.value.code == "EVENT_SEQUENCE_MISMATCH"

    tail_prefix = replay_pressure_events(initial, events_a[:-1], config)
    assert tail_prefix.exclusive_resource_spent_on == RESOURCE_SPENT_UPGRADE
    with pytest.raises(PressureValidationError) as error:
        verify_terminal_pressure_trace(initial, events_a[:-1], config, pressure_state_hash(final_a))
    assert error.value.code == "EVENT_SEQUENCE_MISMATCH"

    with pytest.raises(PressureValidationError) as error:
        verify_terminal_pressure_trace(initial, (), config, pressure_state_hash(final_a))
    assert error.value.code == "EVENT_SEQUENCE_MISMATCH"
    with pytest.raises(PressureValidationError) as error:
        verify_terminal_pressure_trace(initial, events_a[:1], config, pressure_state_hash(final_a))
    assert error.value.code == "EVENT_SEQUENCE_MISMATCH"
    with pytest.raises(PressureValidationError) as error:
        verify_terminal_pressure_trace(initial, events_a[:2], config, pressure_state_hash(final_a))
    assert error.value.code == "EVENT_SEQUENCE_MISMATCH"

    with pytest.raises(PressureValidationError) as error:
        verify_terminal_pressure_trace(initial, events_a, config, "0" * 64)
    assert error.value.code == "STATE_HASH_MISMATCH"

    duplicate = events_a + (events_a[-1],)
    with pytest.raises(PressureValidationError) as error:
        replay_pressure_events(initial, duplicate, config)
    assert error.value.code in {"EVENT_SEQUENCE_MISMATCH", "DECISION_SEQUENCE_MISMATCH"}

    reordered = (events_a[1], events_a[0], events_a[2])
    with pytest.raises(PressureValidationError) as error:
        replay_pressure_events(initial, reordered, config)
    assert error.value.code in {"EVENT_SEQUENCE_MISMATCH", "STATE_HASH_MISMATCH", "EVENT_HASH_MISMATCH"}


def test_pressure_sequence_counters_are_local_to_this_trace():
    # These counters describe only this feature-local pressure trace. They do
    # not establish a future Campaign/EventStore global decision sequencing rule.
    _, events = _policy_a(ExclusiveUpgradePressureConfig())
    assert [event.decision_seq for event in events] == [1, 2, 3]
    assert [event.event_seq for event in events] == [1, 2, 3]


def test_invariants_cover_negative_and_cross_branch_state_corruption():
    config = ExclusiveUpgradePressureConfig()
    initial = initial_pressure_state(config)
    with pytest.raises(PressureValidationError):
        ExclusiveUpgradePressureState.from_dict({**initial.to_dict(), "common_material_count": -1})

    bad_branch = replace(initial, growth_level=1)
    with pytest.raises(PressureValidationError) as error:
        check_pressure_invariants(bad_branch, config)
    assert error.value.code == "INVARIANT_VIOLATION"

    recovered, _ = _recover(initial, config)
    bad_both = replace(
        recovered,
        exclusive_resource_spent_on=RESOURCE_SPENT_UPGRADE,
        exclusive_resource_count=0,
        growth_level=1,
        hazard_traversal_unlocked=True,
        supply_route_stabilized=True,
    )
    with pytest.raises(PressureValidationError):
        check_pressure_invariants(bad_both, config)

    wrong_owner = replace(initial, growth_object_owner_id="actor.other")
    with pytest.raises(PressureValidationError):
        check_pressure_invariants(wrong_owner, config)

    impossible_closed_source = replace(initial, exclusive_resource_source_available=False)
    with pytest.raises(PressureValidationError):
        check_pressure_invariants(impossible_closed_source, config)

    with pytest.raises(PressureValidationError):
        backward_time = replace(initial, game_minute=-1)
        ExclusiveUpgradePressureState.from_dict(backward_time.to_dict())


def test_six_exact_reachable_stages_reject_unreachable_signatures():
    config = ExclusiveUpgradePressureConfig()
    initial = initial_pressure_state(config)
    recovered, _ = _recover(initial, config)
    upgraded, _ = _apply(recovered, UPGRADE_GROWTH_OBJECT, config)
    final_a, _ = _policy_a(config)
    stabilized, _ = _apply(recovered, STABILIZE_SUPPLY_ROUTE, config)
    final_b, _ = _policy_b(config)

    for stage in (initial, recovered, upgraded, final_a, stabilized, final_b):
        assert check_pressure_invariants(stage, config) is True

    assert recovered.game_minute == config.initial_game_minute + config.recover_duration
    assert upgraded.game_minute == recovered.game_minute + config.upgrade_duration
    assert final_a.game_minute == upgraded.game_minute + config.traverse_duration
    assert stabilized.game_minute == recovered.game_minute + config.stabilize_duration
    assert final_b.game_minute == stabilized.game_minute + config.claim_duration
    assert final_b.common_material_count == config.initial_common_material_count + config.supply_cache_material_reward

    impossible_states = (
        replace(initial, decision_seq=5, event_seq=5),
        replace(recovered, game_minute=recovered.game_minute + 1),
        replace(recovered, common_material_count=recovered.common_material_count + 1),
        replace(upgraded, common_material_count=upgraded.common_material_count + 1),
        replace(final_b, common_material_count=final_b.common_material_count - 1),
        replace(final_b, common_material_count=final_b.common_material_count + config.supply_cache_material_reward),
        replace(final_a, hazard_zone_traversed=False),
        replace(recovered, event_seq=2, decision_seq=2),
    )
    for impossible in impossible_states:
        with pytest.raises(PressureValidationError) as error:
            check_pressure_invariants(impossible, config)
        assert error.value.code == "INVARIANT_VIOLATION"


def test_public_pressure_functions_reject_wrong_object_types_stably():
    config = ExclusiveUpgradePressureConfig()
    initial = initial_pressure_state(config)
    _, event = _recover(initial, config)
    final_a, events_a = _policy_a(config)
    calls = (
        lambda: initial_pressure_state(object()),
        lambda: pressure_state_hash(object()),
        lambda: pressure_event_hash(object()),
        lambda: check_pressure_invariants(object(), config),
        lambda: legal_pressure_actions(object(), config.protagonist_id, config),
        lambda: resolve_pressure_action(initial, object(), config),
        lambda: resolve_pressure_action(object(), _action(initial, RECOVER_EXCLUSIVE_RESOURCE, config), config),
        lambda: reduce_pressure_event(initial, object(), config),
        lambda: reduce_pressure_event(object(), event, config),
        lambda: replay_pressure_events(object(), (), config),
        lambda: replay_pressure_events(initial, object(), config),
        lambda: verify_terminal_pressure_trace(initial, events_a, config, object()),
        lambda: verify_terminal_pressure_trace(object(), events_a, config, pressure_state_hash(final_a)),
        lambda: project_pressure_observation(object(), config.protagonist_id, config),
        lambda: project_pressure_observation(initial, object(), config),
    )
    for call in calls:
        with pytest.raises(PressureValidationError):
            call()


def test_observation_is_public_and_action_projection_is_exact():
    config = ExclusiveUpgradePressureConfig()
    state = initial_pressure_state(config)
    observation = project_pressure_observation(state, config.protagonist_id, config)
    assert observation.to_dict() == {
        "growth_level": 0,
        "has_exclusive_resource": False,
        "exclusive_resource_source_available": True,
        "branch_committed": "NONE",
        "stamina": config.initial_stamina,
        "game_minute": config.initial_game_minute,
        "legal_action_ids": [RECOVER_EXCLUSIVE_RESOURCE],
        "completed_results": [],
    }
    assert "config_hash" not in observation.to_dict()
    assert "exclusive_resource_count" not in observation.to_dict()

    recovered, _ = _recover(state, config)
    recovered_observation = project_pressure_observation(recovered, config.protagonist_id, config)
    assert set(recovered_observation.legal_action_ids) == {UPGRADE_GROWTH_OBJECT, STABILIZE_SUPPLY_ROUTE}
    exported = recovered_observation.to_dict()
    exported["legal_action_ids"].clear()
    assert recovered_observation.legal_action_ids


def test_pressure_slice_has_no_runtime_catalog_registration_or_side_effects(monkeypatch):
    assert PRESSURE_FEATURE_ID not in {feature.feature_id for feature in DEFAULT_CATALOG.entries}
    assert not any(feature.layer == "RUNTIME" for feature in DEFAULT_CATALOG.entries)

    def forbidden(*args, **kwargs):
        raise AssertionError("pressure slice attempted an external side effect")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    final_state, events = _policy_a(ExclusiveUpgradePressureConfig())
    assert final_state.hazard_zone_traversed is True
    assert len(events) == 3
