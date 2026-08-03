"""Feature-local V1-B exclusive-resource pressure slice.

This module is intentionally concrete rather than a runtime framework.  It
owns one bounded causal chain and keeps all authority in immutable state,
typed actions, explicit events, and a deterministic reducer/replay path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import re
from typing import Any, Mapping, Sequence

from tgn.core.hashing import canonical_json, state_hash


PRESSURE_FEATURE_ID = "runtime.exclusive_upgrade_pressure.v1"
PRESSURE_CONTRACT_VERSION = "1"

RECOVER_EXCLUSIVE_RESOURCE = "RECOVER_EXCLUSIVE_RESOURCE"
UPGRADE_GROWTH_OBJECT = "UPGRADE_GROWTH_OBJECT"
STABILIZE_SUPPLY_ROUTE = "STABILIZE_SUPPLY_ROUTE"
TRAVERSE_HAZARD_ZONE = "TRAVERSE_HAZARD_ZONE"
CLAIM_SUPPLY_CACHE = "CLAIM_SUPPLY_CACHE"
PRESSURE_ACTION_IDS = frozenset(
    {
        RECOVER_EXCLUSIVE_RESOURCE,
        UPGRADE_GROWTH_OBJECT,
        STABILIZE_SUPPLY_ROUTE,
        TRAVERSE_HAZARD_ZONE,
        CLAIM_SUPPLY_CACHE,
    }
)

RESOURCE_SPENT_NONE = "NONE"
RESOURCE_SPENT_UPGRADE = "UPGRADE"
RESOURCE_SPENT_SUPPLY_ROUTE = "SUPPLY_ROUTE"
PRESSURE_BRANCHES = frozenset(
    {RESOURCE_SPENT_NONE, RESOURCE_SPENT_UPGRADE, RESOURCE_SPENT_SUPPLY_ROUTE}
)

EVENT_RESOURCE_RECOVERED = "EXCLUSIVE_RESOURCE_RECOVERED"
EVENT_GROWTH_UPGRADED = "GROWTH_OBJECT_UPGRADED"
EVENT_SUPPLY_STABILIZED = "SUPPLY_ROUTE_STABILIZED"
EVENT_HAZARD_TRAVERSED = "HAZARD_ZONE_TRAVERSED"
EVENT_CACHE_CLAIMED = "SUPPLY_CACHE_CLAIMED"
PRESSURE_EVENT_TYPES = frozenset(
    {
        EVENT_RESOURCE_RECOVERED,
        EVENT_GROWTH_UPGRADED,
        EVENT_SUPPLY_STABILIZED,
        EVENT_HAZARD_TRAVERSED,
        EVENT_CACHE_CLAIMED,
    }
)
PRESSURE_RESULTS = frozenset({"NONE", "HAZARD_ZONE_TRAVERSED", "SUPPLY_CACHE_CLAIMED"})

PRESSURE_ERROR_CODES = frozenset(
    {
        "INVALID_ACTION",
        "ACTION_NOT_LEGAL",
        "NOT_GROWTH_OBJECT_OWNER",
        "INSUFFICIENT_STAMINA",
        "EXCLUSIVE_RESOURCE_REQUIRED",
        "EXCLUSIVE_RESOURCE_SOURCE_CLOSED",
        "EXCLUSIVE_RESOURCE_ALREADY_HELD",
        "EXCLUSIVE_RESOURCE_ALREADY_COMMITTED",
        "ORDINARY_RESOURCE_FALLBACK_FORBIDDEN",
        "BRANCH_ALREADY_COMMITTED",
        "FOLLOWUP_NOT_UNLOCKED",
        "CONFIG_HASH_MISMATCH",
        "STATE_HASH_MISMATCH",
        "EVENT_HASH_MISMATCH",
        "EVENT_SEQUENCE_MISMATCH",
        "DECISION_SEQUENCE_MISMATCH",
        "INVALID_EVENT_PAYLOAD",
        "INVARIANT_VIOLATION",
    }
)

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class PressureValidationError(ValueError):
    """Stable failure raised by the feature-local pressure contract."""

    def __init__(self, code: str, path: str = "$", *, message: str | None = None) -> None:
        if type(code) is not str or code not in PRESSURE_ERROR_CODES:
            raise ValueError(f"Unknown pressure validation error code: {code}")
        self.code = code
        self.path = path
        self.message = message or code
        super().__init__(f"{code} at {path}: {self.message}")

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _fail(code: str, path: str, *, message: str | None = None) -> None:
    raise PressureValidationError(code, path, message=message)


def _validate_id(value: Any, path: str) -> str:
    if type(value) is not str or _ID_RE.fullmatch(value) is None:
        _fail("INVARIANT_VIOLATION", path, message="stable lower-case ID required")
    return value


def _validate_hash(value: Any, path: str) -> str:
    if type(value) is not str or _HEX64_RE.fullmatch(value) is None:
        _fail("INVARIANT_VIOLATION", path, message="SHA-256 hex required")
    return value


def _validate_int(value: Any, path: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail("INVARIANT_VIOLATION", path, message=f"integer >= {minimum} required")
    return value


def _validate_bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        _fail("INVARIANT_VIOLATION", path, message="boolean required")
    return value


def _strict_fields(data: Mapping[str, Any], allowed: set[str], path: str = "$") -> None:
    if not isinstance(data, Mapping):
        _fail("INVALID_ACTION", path, message="object required")
    unknown = [key for key in data if key not in allowed]
    if unknown:
        unknown_key = min(unknown, key=lambda key: repr(key))
        key_label = unknown_key if type(unknown_key) is str else repr(unknown_key)
        _fail("INVALID_ACTION", f"{path}.{key_label}", message="unknown field")
    missing = sorted(allowed - set(data))
    if missing:
        _fail("INVALID_ACTION", f"{path}.{missing[0]}", message="required field missing")


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(dict(payload)).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ExclusiveUpgradePressureConfig:
    """The finite, fixed contract parameters for this one pressure slice."""

    schema_version: int = 1
    feature_id: str = PRESSURE_FEATURE_ID
    contract_version: str = PRESSURE_CONTRACT_VERSION
    protagonist_id: str = "actor.protagonist"
    growth_object_id: str = "growth.object"
    growth_object_owner_id: str = "actor.protagonist"
    exclusive_resource_id: str = "resource.exclusive"
    initial_common_material_count: int = 100
    initial_stamina: int = 10
    initial_game_minute: int = 0
    recover_duration: int = 5
    recover_stamina_cost: int = 2
    upgrade_duration: int = 1
    upgrade_stamina_cost: int = 1
    stabilize_duration: int = 1
    stabilize_stamina_cost: int = 1
    traverse_duration: int = 3
    traverse_stamina_cost: int = 1
    claim_duration: int = 1
    claim_stamina_cost: int = 1
    supply_cache_material_reward: int = 5

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            _fail("INVARIANT_VIOLATION", "$.schema_version", message="schema version must be 1")
        if type(self.feature_id) is not str or self.feature_id != PRESSURE_FEATURE_ID:
            _fail("INVARIANT_VIOLATION", "$.feature_id", message="feature identity is fixed")
        if type(self.contract_version) is not str or self.contract_version != PRESSURE_CONTRACT_VERSION:
            _fail("INVARIANT_VIOLATION", "$.contract_version", message="contract version is fixed")
        for name in (
            "protagonist_id",
            "growth_object_id",
            "growth_object_owner_id",
            "exclusive_resource_id",
        ):
            _validate_id(getattr(self, name), f"$.{name}")
        if self.growth_object_owner_id != self.protagonist_id:
            _fail("INVARIANT_VIOLATION", "$.growth_object_owner_id", message="growth object owner must be protagonist")
        for name in (
            "initial_common_material_count",
            "initial_stamina",
            "initial_game_minute",
            "recover_duration",
            "recover_stamina_cost",
            "upgrade_duration",
            "upgrade_stamina_cost",
            "stabilize_duration",
            "stabilize_stamina_cost",
            "traverse_duration",
            "traverse_stamina_cost",
            "claim_duration",
            "claim_stamina_cost",
            "supply_cache_material_reward",
        ):
            _validate_int(getattr(self, name), f"$.{name}")
        if self.initial_common_material_count < 10:
            _fail("INVARIANT_VIOLATION", "$.initial_common_material_count", message="fixture must contain ample ordinary material")
        required_growth_stamina = self.recover_stamina_cost + self.upgrade_stamina_cost + self.traverse_stamina_cost
        required_supply_stamina = self.recover_stamina_cost + self.stabilize_stamina_cost + self.claim_stamina_cost
        if self.initial_stamina < max(required_growth_stamina, required_supply_stamina):
            _fail(
                "INVARIANT_VIOLATION",
                "$.initial_stamina",
                message="initial stamina must cover both complete pressure paths",
            )
        for name in (
            "recover_duration",
            "recover_stamina_cost",
            "upgrade_duration",
            "upgrade_stamina_cost",
            "stabilize_duration",
            "stabilize_stamina_cost",
            "traverse_duration",
            "traverse_stamina_cost",
            "claim_duration",
            "claim_stamina_cost",
            "supply_cache_material_reward",
        ):
            if getattr(self, name) <= 0:
                _fail("INVARIANT_VIOLATION", f"$.{name}", message="positive contract value required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "feature_id": self.feature_id,
            "contract_version": self.contract_version,
            "protagonist_id": self.protagonist_id,
            "growth_object_id": self.growth_object_id,
            "growth_object_owner_id": self.growth_object_owner_id,
            "exclusive_resource_id": self.exclusive_resource_id,
            "initial_common_material_count": self.initial_common_material_count,
            "initial_stamina": self.initial_stamina,
            "initial_game_minute": self.initial_game_minute,
            "recover_duration": self.recover_duration,
            "recover_stamina_cost": self.recover_stamina_cost,
            "upgrade_duration": self.upgrade_duration,
            "upgrade_stamina_cost": self.upgrade_stamina_cost,
            "stabilize_duration": self.stabilize_duration,
            "stabilize_stamina_cost": self.stabilize_stamina_cost,
            "traverse_duration": self.traverse_duration,
            "traverse_stamina_cost": self.traverse_stamina_cost,
            "claim_duration": self.claim_duration,
            "claim_stamina_cost": self.claim_stamina_cost,
            "supply_cache_material_reward": self.supply_cache_material_reward,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExclusiveUpgradePressureConfig":
        allowed = set(cls.__dataclass_fields__)
        _strict_fields(data, allowed)
        return cls(**dict(data))

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict())

    @property
    def required_growth_stamina(self) -> int:
        return self.recover_stamina_cost + self.upgrade_stamina_cost + self.traverse_stamina_cost

    @property
    def required_supply_stamina(self) -> int:
        return self.recover_stamina_cost + self.stabilize_stamina_cost + self.claim_stamina_cost


@dataclass(frozen=True, slots=True)
class ExclusiveUpgradePressureState:
    protagonist_id: str
    growth_object_id: str
    growth_object_owner_id: str
    growth_level: int
    common_material_count: int
    exclusive_resource_count: int
    exclusive_resource_source_available: bool
    exclusive_resource_spent_on: str
    supply_route_stabilized: bool
    hazard_traversal_unlocked: bool
    supply_cache_claimed: bool
    hazard_zone_traversed: bool
    stamina: int
    game_minute: int
    decision_seq: int
    event_seq: int
    config_hash: str

    def __post_init__(self) -> None:
        for name in ("protagonist_id", "growth_object_id", "growth_object_owner_id"):
            _validate_id(getattr(self, name), f"$.{name}")
        for name in (
            "growth_level",
            "common_material_count",
            "exclusive_resource_count",
            "stamina",
            "game_minute",
            "decision_seq",
            "event_seq",
        ):
            _validate_int(getattr(self, name), f"$.{name}")
        if self.growth_level not in {0, 1}:
            _fail("INVARIANT_VIOLATION", "$.growth_level", message="growth level must be 0 or 1")
        if self.exclusive_resource_count not in {0, 1}:
            _fail("INVARIANT_VIOLATION", "$.exclusive_resource_count", message="exclusive resource count must be 0 or 1")
        _validate_bool(self.exclusive_resource_source_available, "$.exclusive_resource_source_available")
        _validate_bool(self.supply_route_stabilized, "$.supply_route_stabilized")
        _validate_bool(self.hazard_traversal_unlocked, "$.hazard_traversal_unlocked")
        _validate_bool(self.supply_cache_claimed, "$.supply_cache_claimed")
        _validate_bool(self.hazard_zone_traversed, "$.hazard_zone_traversed")
        if type(self.exclusive_resource_spent_on) is not str or self.exclusive_resource_spent_on not in PRESSURE_BRANCHES:
            _fail("INVARIANT_VIOLATION", "$.exclusive_resource_spent_on", message="unknown branch")
        _validate_hash(self.config_hash, "$.config_hash")

    def to_dict(self) -> dict[str, Any]:
        return {
            "protagonist_id": self.protagonist_id,
            "growth_object_id": self.growth_object_id,
            "growth_object_owner_id": self.growth_object_owner_id,
            "growth_level": self.growth_level,
            "common_material_count": self.common_material_count,
            "exclusive_resource_count": self.exclusive_resource_count,
            "exclusive_resource_source_available": self.exclusive_resource_source_available,
            "exclusive_resource_spent_on": self.exclusive_resource_spent_on,
            "supply_route_stabilized": self.supply_route_stabilized,
            "hazard_traversal_unlocked": self.hazard_traversal_unlocked,
            "supply_cache_claimed": self.supply_cache_claimed,
            "hazard_zone_traversed": self.hazard_zone_traversed,
            "stamina": self.stamina,
            "game_minute": self.game_minute,
            "decision_seq": self.decision_seq,
            "event_seq": self.event_seq,
            "config_hash": self.config_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExclusiveUpgradePressureState":
        allowed = set(cls.__dataclass_fields__)
        _strict_fields(data, allowed)
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class ExclusiveUpgradeAction:
    action_id: str
    actor_id: str
    decision_seq: int

    def __post_init__(self) -> None:
        if type(self.action_id) is not str or self.action_id not in PRESSURE_ACTION_IDS:
            _fail("INVALID_ACTION", "$.action_id", message="unknown pressure action")
        _validate_id(self.actor_id, "$.actor_id")
        if type(self.decision_seq) is not int or self.decision_seq < 1:
            _fail("INVALID_ACTION", "$.decision_seq", message="positive decision sequence required")

    def to_dict(self) -> dict[str, Any]:
        return {"action_id": self.action_id, "actor_id": self.actor_id, "decision_seq": self.decision_seq}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExclusiveUpgradeAction":
        _strict_fields(data, set(cls.__dataclass_fields__))
        return cls(**dict(data))

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict())


@dataclass(frozen=True, slots=True)
class ExclusiveUpgradeEvent:
    event_type: str
    event_seq: int
    decision_seq: int
    actor_id: str
    action_id: str
    action_hash: str
    config_hash: str
    before_state_hash: str
    after_state_hash: str
    resource_delta: int
    common_material_delta: int
    growth_level_delta: int
    branch_commitment: str
    result: str
    game_minute_delta: int
    stamina_delta: int
    event_hash: str

    def __post_init__(self) -> None:
        if type(self.event_type) is not str or self.event_type not in PRESSURE_EVENT_TYPES:
            _fail("INVALID_EVENT_PAYLOAD", "$.event_type", message="unknown pressure event")
        for name in ("event_seq", "decision_seq", "resource_delta", "common_material_delta", "growth_level_delta", "game_minute_delta"):
            value = getattr(self, name)
            if type(value) is not int:
                _fail("INVALID_EVENT_PAYLOAD", f"$.{name}", message="integer required")
        if self.event_seq < 1 or self.decision_seq < 1 or self.game_minute_delta <= 0:
            _fail("INVALID_EVENT_PAYLOAD", "$", message="event sequences and time delta must be positive")
        if self.resource_delta not in {-1, 0, 1} or self.common_material_delta < 0 or self.growth_level_delta not in {0, 1}:
            _fail("INVALID_EVENT_PAYLOAD", "$", message="event deltas outside fixed pressure domain")
        if type(self.stamina_delta) is not int or self.stamina_delta >= 0:
            _fail("INVALID_EVENT_PAYLOAD", "$.stamina_delta", message="stamina must decrease")
        _validate_id(self.actor_id, "$.actor_id")
        if type(self.action_id) is not str or self.action_id not in PRESSURE_ACTION_IDS:
            _fail("INVALID_EVENT_PAYLOAD", "$.action_id", message="unknown action")
        _validate_hash(self.action_hash, "$.action_hash")
        _validate_hash(self.config_hash, "$.config_hash")
        _validate_hash(self.before_state_hash, "$.before_state_hash")
        _validate_hash(self.after_state_hash, "$.after_state_hash")
        if type(self.branch_commitment) is not str or self.branch_commitment not in PRESSURE_BRANCHES:
            _fail("INVALID_EVENT_PAYLOAD", "$.branch_commitment", message="unknown branch")
        if type(self.result) is not str or self.result not in PRESSURE_RESULTS:
            _fail("INVALID_EVENT_PAYLOAD", "$.result", message="unknown result")
        _validate_hash(self.event_hash, "$.event_hash")

    def _payload_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_seq": self.event_seq,
            "decision_seq": self.decision_seq,
            "actor_id": self.actor_id,
            "action_id": self.action_id,
            "action_hash": self.action_hash,
            "config_hash": self.config_hash,
            "before_state_hash": self.before_state_hash,
            "after_state_hash": self.after_state_hash,
            "resource_delta": self.resource_delta,
            "common_material_delta": self.common_material_delta,
            "growth_level_delta": self.growth_level_delta,
            "branch_commitment": self.branch_commitment,
            "result": self.result,
            "game_minute_delta": self.game_minute_delta,
            "stamina_delta": self.stamina_delta,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload_dict()
        payload["event_hash"] = self.event_hash
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExclusiveUpgradeEvent":
        _strict_fields(data, set(cls.__dataclass_fields__))
        return cls(**dict(data))

    @property
    def event_id(self) -> str:
        return self.event_hash


@dataclass(frozen=True, slots=True)
class ExclusiveUpgradeObservation:
    growth_level: int
    has_exclusive_resource: bool
    exclusive_resource_source_available: bool
    branch_committed: str
    stamina: int
    game_minute: int
    legal_action_ids: tuple[str, ...]
    completed_results: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "growth_level": self.growth_level,
            "has_exclusive_resource": self.has_exclusive_resource,
            "exclusive_resource_source_available": self.exclusive_resource_source_available,
            "branch_committed": self.branch_committed,
            "stamina": self.stamina,
            "game_minute": self.game_minute,
            "legal_action_ids": list(self.legal_action_ids),
            "completed_results": list(self.completed_results),
        }


def initial_pressure_state(config: ExclusiveUpgradePressureConfig) -> ExclusiveUpgradePressureState:
    if type(config) is not ExclusiveUpgradePressureConfig:
        _fail("CONFIG_HASH_MISMATCH", "$.config", message="pressure config required")
    state = ExclusiveUpgradePressureState(
        protagonist_id=config.protagonist_id,
        growth_object_id=config.growth_object_id,
        growth_object_owner_id=config.growth_object_owner_id,
        growth_level=0,
        common_material_count=config.initial_common_material_count,
        exclusive_resource_count=0,
        exclusive_resource_source_available=True,
        exclusive_resource_spent_on=RESOURCE_SPENT_NONE,
        supply_route_stabilized=False,
        hazard_traversal_unlocked=False,
        supply_cache_claimed=False,
        hazard_zone_traversed=False,
        stamina=config.initial_stamina,
        game_minute=config.initial_game_minute,
        decision_seq=0,
        event_seq=0,
        config_hash=config.hash,
    )
    check_pressure_invariants(state, config)
    return state


def pressure_state_hash(state: ExclusiveUpgradePressureState) -> str:
    if type(state) is not ExclusiveUpgradePressureState:
        _fail("STATE_HASH_MISMATCH", "$.state", message="pressure state required")
    return state_hash(state.to_dict())


def pressure_event_hash(event: ExclusiveUpgradeEvent) -> str:
    if type(event) is not ExclusiveUpgradeEvent:
        _fail("EVENT_HASH_MISMATCH", "$.event", message="pressure event required")
    return _hash_payload(event._payload_dict())


def _check_state_config(state: ExclusiveUpgradePressureState, config: ExclusiveUpgradePressureConfig) -> None:
    if type(state) is not ExclusiveUpgradePressureState:
        _fail("INVARIANT_VIOLATION", "$.state", message="pressure state required")
    if type(config) is not ExclusiveUpgradePressureConfig:
        _fail("CONFIG_HASH_MISMATCH", "$.config", message="pressure config required")
    if state.config_hash != config.hash:
        _fail("CONFIG_HASH_MISMATCH", "$.state.config_hash", message="state belongs to a different pressure config")
    if state.protagonist_id != config.protagonist_id or state.growth_object_id != config.growth_object_id:
        _fail("INVARIANT_VIOLATION", "$.state", message="state identity differs from config")
    if state.growth_object_owner_id != config.growth_object_owner_id:
        _fail("INVARIANT_VIOLATION", "$.state.growth_object_owner_id", message="owner differs from config")


def _expected_pressure_stage_dicts(config: ExclusiveUpgradePressureConfig) -> tuple[tuple[str, dict[str, Any]], ...]:
    """Return the six exact reachable signatures for this concrete slice."""

    base = {
        "protagonist_id": config.protagonist_id,
        "growth_object_id": config.growth_object_id,
        "growth_object_owner_id": config.growth_object_owner_id,
        "growth_level": 0,
        "common_material_count": config.initial_common_material_count,
        "exclusive_resource_count": 0,
        "exclusive_resource_source_available": True,
        "exclusive_resource_spent_on": RESOURCE_SPENT_NONE,
        "supply_route_stabilized": False,
        "hazard_traversal_unlocked": False,
        "supply_cache_claimed": False,
        "hazard_zone_traversed": False,
        "stamina": config.initial_stamina,
        "game_minute": config.initial_game_minute,
        "decision_seq": 0,
        "event_seq": 0,
        "config_hash": config.hash,
    }

    def stage(name: str, **changes: Any) -> tuple[str, dict[str, Any]]:
        values = dict(base)
        values.update(changes)
        return name, values

    recovered_stamina = config.initial_stamina - config.recover_stamina_cost
    recovered_minute = config.initial_game_minute + config.recover_duration
    upgrade_stamina = recovered_stamina - config.upgrade_stamina_cost
    upgrade_minute = recovered_minute + config.upgrade_duration
    supply_stamina = recovered_stamina - config.stabilize_stamina_cost
    supply_minute = recovered_minute + config.stabilize_duration
    return (
        stage("INITIAL"),
        stage(
            "RESOURCE_RECOVERED",
            exclusive_resource_count=1,
            exclusive_resource_source_available=False,
            stamina=recovered_stamina,
            game_minute=recovered_minute,
            decision_seq=1,
            event_seq=1,
        ),
        stage(
            "UPGRADE_COMMITTED",
            exclusive_resource_count=0,
            exclusive_resource_source_available=False,
            exclusive_resource_spent_on=RESOURCE_SPENT_UPGRADE,
            growth_level=1,
            hazard_traversal_unlocked=True,
            stamina=upgrade_stamina,
            game_minute=upgrade_minute,
            decision_seq=2,
            event_seq=2,
        ),
        stage(
            "UPGRADE_TERMINAL",
            exclusive_resource_count=0,
            exclusive_resource_source_available=False,
            exclusive_resource_spent_on=RESOURCE_SPENT_UPGRADE,
            growth_level=1,
            hazard_traversal_unlocked=True,
            hazard_zone_traversed=True,
            stamina=upgrade_stamina - config.traverse_stamina_cost,
            game_minute=upgrade_minute + config.traverse_duration,
            decision_seq=3,
            event_seq=3,
        ),
        stage(
            "SUPPLY_COMMITTED",
            exclusive_resource_count=0,
            exclusive_resource_source_available=False,
            exclusive_resource_spent_on=RESOURCE_SPENT_SUPPLY_ROUTE,
            supply_route_stabilized=True,
            stamina=supply_stamina,
            game_minute=supply_minute,
            decision_seq=2,
            event_seq=2,
        ),
        stage(
            "SUPPLY_TERMINAL",
            exclusive_resource_count=0,
            exclusive_resource_source_available=False,
            exclusive_resource_spent_on=RESOURCE_SPENT_SUPPLY_ROUTE,
            supply_route_stabilized=True,
            supply_cache_claimed=True,
            common_material_count=config.initial_common_material_count + config.supply_cache_material_reward,
            stamina=supply_stamina - config.claim_stamina_cost,
            game_minute=supply_minute + config.claim_duration,
            decision_seq=3,
            event_seq=3,
        ),
    )


def _pressure_stage_name(state: ExclusiveUpgradePressureState, config: ExclusiveUpgradePressureConfig) -> str:
    actual = state.to_dict()
    for name, expected in _expected_pressure_stage_dicts(config):
        if actual == expected:
            return name
    _fail(
        "INVARIANT_VIOLATION",
        "$.state",
        message="state is not one of the six exact reachable pressure stages",
    )
    raise AssertionError("unreachable")


def check_pressure_invariants(state: ExclusiveUpgradePressureState, config: ExclusiveUpgradePressureConfig) -> bool:
    _check_state_config(state, config)
    _pressure_stage_name(state, config)
    return True


def legal_pressure_actions(
    state: ExclusiveUpgradePressureState,
    actor_id: str,
    config: ExclusiveUpgradePressureConfig,
) -> tuple[str, ...]:
    check_pressure_invariants(state, config)
    _validate_id(actor_id, "$.actor_id")
    if actor_id != config.protagonist_id:
        return ()
    actions: list[str] = []
    if state.exclusive_resource_source_available and state.exclusive_resource_count == 0 and state.stamina >= config.recover_stamina_cost:
        actions.append(RECOVER_EXCLUSIVE_RESOURCE)
    if state.exclusive_resource_count == 1 and state.exclusive_resource_spent_on == RESOURCE_SPENT_NONE:
        if state.stamina >= config.upgrade_stamina_cost:
            actions.append(UPGRADE_GROWTH_OBJECT)
        if state.stamina >= config.stabilize_stamina_cost:
            actions.append(STABILIZE_SUPPLY_ROUTE)
    if state.hazard_traversal_unlocked and not state.hazard_zone_traversed and state.stamina >= config.traverse_stamina_cost:
        actions.append(TRAVERSE_HAZARD_ZONE)
    if state.supply_route_stabilized and not state.supply_cache_claimed and state.stamina >= config.claim_stamina_cost:
        actions.append(CLAIM_SUPPLY_CACHE)
    return tuple(actions)


def _check_action_legal(
    state: ExclusiveUpgradePressureState,
    action: ExclusiveUpgradeAction,
    config: ExclusiveUpgradePressureConfig,
) -> None:
    if type(action) is not ExclusiveUpgradeAction:
        _fail("INVALID_ACTION", "$.action", message="typed pressure action required")
    _check_state_config(state, config)
    check_pressure_invariants(state, config)
    if action.decision_seq != state.decision_seq + 1:
        _fail("DECISION_SEQUENCE_MISMATCH", "$.action.decision_seq", message="action must be next decision")
    if action.actor_id != config.protagonist_id:
        if action.action_id == UPGRADE_GROWTH_OBJECT:
            _fail("NOT_GROWTH_OBJECT_OWNER", "$.action.actor_id", message="only the growth object owner may upgrade")
        _fail("ACTION_NOT_LEGAL", "$.action.actor_id", message="only the protagonist may execute this slice")
    if action.action_id == RECOVER_EXCLUSIVE_RESOURCE:
        if state.exclusive_resource_count:
            _fail("EXCLUSIVE_RESOURCE_ALREADY_HELD", "$.state", message="exclusive resource is already held")
        if not state.exclusive_resource_source_available:
            _fail("EXCLUSIVE_RESOURCE_SOURCE_CLOSED", "$.state", message="exclusive resource source is permanently closed")
        if state.stamina < config.recover_stamina_cost:
            _fail("INSUFFICIENT_STAMINA", "$.state.stamina", message="recovery requires more stamina")
        return
    if action.action_id in {UPGRADE_GROWTH_OBJECT, STABILIZE_SUPPLY_ROUTE}:
        if state.exclusive_resource_spent_on != RESOURCE_SPENT_NONE:
            committed_branch = (
                RESOURCE_SPENT_UPGRADE
                if action.action_id == UPGRADE_GROWTH_OBJECT
                else RESOURCE_SPENT_SUPPLY_ROUTE
            )
            if state.exclusive_resource_spent_on == committed_branch:
                _fail(
                    "EXCLUSIVE_RESOURCE_ALREADY_COMMITTED",
                    "$.state.exclusive_resource_spent_on",
                    message="the exclusive resource has already been spent on this branch",
                )
            _fail("BRANCH_ALREADY_COMMITTED", "$.state.exclusive_resource_spent_on", message="the other exclusive branch is closed")
        if state.exclusive_resource_count == 0:
            if action.action_id == UPGRADE_GROWTH_OBJECT and state.common_material_count > 0:
                _fail("ORDINARY_RESOURCE_FALLBACK_FORBIDDEN", "$.state.common_material_count", message="ordinary materials cannot substitute for exclusive resource")
            _fail("EXCLUSIVE_RESOURCE_REQUIRED", "$.state.exclusive_resource_count", message="one exclusive resource is required")
        cost = config.upgrade_stamina_cost if action.action_id == UPGRADE_GROWTH_OBJECT else config.stabilize_stamina_cost
        if state.stamina < cost:
            _fail("INSUFFICIENT_STAMINA", "$.state.stamina", message="branch action requires more stamina")
        return
    if action.action_id == TRAVERSE_HAZARD_ZONE:
        if state.exclusive_resource_spent_on != RESOURCE_SPENT_UPGRADE or not state.hazard_traversal_unlocked or state.hazard_zone_traversed:
            _fail("FOLLOWUP_NOT_UNLOCKED", "$.state", message="hazard traversal is not currently unlocked")
        if state.stamina < config.traverse_stamina_cost:
            _fail("INSUFFICIENT_STAMINA", "$.state.stamina", message="hazard traversal requires more stamina")
        return
    if action.action_id == CLAIM_SUPPLY_CACHE:
        if state.exclusive_resource_spent_on != RESOURCE_SPENT_SUPPLY_ROUTE or not state.supply_route_stabilized or state.supply_cache_claimed:
            _fail("FOLLOWUP_NOT_UNLOCKED", "$.state", message="supply cache is not currently unlocked")
        if state.stamina < config.claim_stamina_cost:
            _fail("INSUFFICIENT_STAMINA", "$.state.stamina", message="cache claim requires more stamina")
        return
    _fail("INVALID_ACTION", "$.action.action_id", message="unreachable action")


def _transition(
    state: ExclusiveUpgradePressureState,
    action: ExclusiveUpgradeAction,
    config: ExclusiveUpgradePressureConfig,
) -> tuple[ExclusiveUpgradePressureState, dict[str, Any]]:
    if action.action_id == RECOVER_EXCLUSIVE_RESOURCE:
        after = replace(
            state,
            exclusive_resource_count=1,
            exclusive_resource_source_available=False,
            stamina=state.stamina - config.recover_stamina_cost,
            game_minute=state.game_minute + config.recover_duration,
            decision_seq=state.decision_seq + 1,
            event_seq=state.event_seq + 1,
        )
        payload = dict(
            event_type=EVENT_RESOURCE_RECOVERED,
            resource_delta=1,
            common_material_delta=0,
            growth_level_delta=0,
            branch_commitment=RESOURCE_SPENT_NONE,
            result="NONE",
            game_minute_delta=config.recover_duration,
            stamina_delta=-config.recover_stamina_cost,
        )
    elif action.action_id == UPGRADE_GROWTH_OBJECT:
        after = replace(
            state,
            growth_level=1,
            exclusive_resource_count=0,
            exclusive_resource_spent_on=RESOURCE_SPENT_UPGRADE,
            hazard_traversal_unlocked=True,
            stamina=state.stamina - config.upgrade_stamina_cost,
            game_minute=state.game_minute + config.upgrade_duration,
            decision_seq=state.decision_seq + 1,
            event_seq=state.event_seq + 1,
        )
        payload = dict(
            event_type=EVENT_GROWTH_UPGRADED,
            resource_delta=-1,
            common_material_delta=0,
            growth_level_delta=1,
            branch_commitment=RESOURCE_SPENT_UPGRADE,
            result="NONE",
            game_minute_delta=config.upgrade_duration,
            stamina_delta=-config.upgrade_stamina_cost,
        )
    elif action.action_id == STABILIZE_SUPPLY_ROUTE:
        after = replace(
            state,
            exclusive_resource_count=0,
            exclusive_resource_spent_on=RESOURCE_SPENT_SUPPLY_ROUTE,
            supply_route_stabilized=True,
            stamina=state.stamina - config.stabilize_stamina_cost,
            game_minute=state.game_minute + config.stabilize_duration,
            decision_seq=state.decision_seq + 1,
            event_seq=state.event_seq + 1,
        )
        payload = dict(
            event_type=EVENT_SUPPLY_STABILIZED,
            resource_delta=-1,
            common_material_delta=0,
            growth_level_delta=0,
            branch_commitment=RESOURCE_SPENT_SUPPLY_ROUTE,
            result="NONE",
            game_minute_delta=config.stabilize_duration,
            stamina_delta=-config.stabilize_stamina_cost,
        )
    elif action.action_id == TRAVERSE_HAZARD_ZONE:
        after = replace(
            state,
            hazard_zone_traversed=True,
            stamina=state.stamina - config.traverse_stamina_cost,
            game_minute=state.game_minute + config.traverse_duration,
            decision_seq=state.decision_seq + 1,
            event_seq=state.event_seq + 1,
        )
        payload = dict(
            event_type=EVENT_HAZARD_TRAVERSED,
            resource_delta=0,
            common_material_delta=0,
            growth_level_delta=0,
            branch_commitment=RESOURCE_SPENT_UPGRADE,
            result="HAZARD_ZONE_TRAVERSED",
            game_minute_delta=config.traverse_duration,
            stamina_delta=-config.traverse_stamina_cost,
        )
    elif action.action_id == CLAIM_SUPPLY_CACHE:
        after = replace(
            state,
            supply_cache_claimed=True,
            common_material_count=state.common_material_count + config.supply_cache_material_reward,
            stamina=state.stamina - config.claim_stamina_cost,
            game_minute=state.game_minute + config.claim_duration,
            decision_seq=state.decision_seq + 1,
            event_seq=state.event_seq + 1,
        )
        payload = dict(
            event_type=EVENT_CACHE_CLAIMED,
            resource_delta=0,
            common_material_delta=config.supply_cache_material_reward,
            growth_level_delta=0,
            branch_commitment=RESOURCE_SPENT_SUPPLY_ROUTE,
            result="SUPPLY_CACHE_CLAIMED",
            game_minute_delta=config.claim_duration,
            stamina_delta=-config.claim_stamina_cost,
        )
    else:
        _fail("INVALID_ACTION", "$.action.action_id", message="unknown pressure action")
    check_pressure_invariants(after, config)
    return after, payload


def _make_event(
    state: ExclusiveUpgradePressureState,
    action: ExclusiveUpgradeAction,
    after: ExclusiveUpgradePressureState,
    payload: Mapping[str, Any],
    config: ExclusiveUpgradePressureConfig,
) -> ExclusiveUpgradeEvent:
    event_payload = dict(
        event_type=payload["event_type"],
        event_seq=after.event_seq,
        decision_seq=action.decision_seq,
        actor_id=action.actor_id,
        action_id=action.action_id,
        action_hash=action.hash,
        config_hash=config.hash,
        before_state_hash=pressure_state_hash(state),
        after_state_hash=pressure_state_hash(after),
        resource_delta=payload["resource_delta"],
        common_material_delta=payload["common_material_delta"],
        growth_level_delta=payload["growth_level_delta"],
        branch_commitment=payload["branch_commitment"],
        result=payload["result"],
        game_minute_delta=payload["game_minute_delta"],
        stamina_delta=payload["stamina_delta"],
    )
    return ExclusiveUpgradeEvent(**event_payload, event_hash=_hash_payload(event_payload))


def resolve_pressure_action(
    state: ExclusiveUpgradePressureState,
    action: ExclusiveUpgradeAction,
    config: ExclusiveUpgradePressureConfig,
) -> ExclusiveUpgradeEvent:
    _check_action_legal(state, action, config)
    after, payload = _transition(state, action, config)
    return _make_event(state, action, after, payload, config)


def reduce_pressure_event(
    state: ExclusiveUpgradePressureState,
    event: ExclusiveUpgradeEvent,
    config: ExclusiveUpgradePressureConfig,
) -> ExclusiveUpgradePressureState:
    if type(event) is not ExclusiveUpgradeEvent:
        _fail("INVALID_EVENT_PAYLOAD", "$.event", message="typed pressure event required")
    _check_state_config(state, config)
    check_pressure_invariants(state, config)
    if event.config_hash != config.hash:
        _fail("CONFIG_HASH_MISMATCH", "$.event.config_hash", message="event belongs to a different pressure config")
    if event.event_seq != state.event_seq + 1:
        _fail("EVENT_SEQUENCE_MISMATCH", "$.event.event_seq", message="event must be next in sequence")
    if event.decision_seq != state.decision_seq + 1:
        _fail("DECISION_SEQUENCE_MISMATCH", "$.event.decision_seq", message="event must be next decision")
    if event.before_state_hash != pressure_state_hash(state):
        _fail("STATE_HASH_MISMATCH", "$.event.before_state_hash", message="event does not start from supplied state")
    try:
        action = ExclusiveUpgradeAction(event.action_id, event.actor_id, event.decision_seq)
    except PressureValidationError:
        _fail("INVALID_EVENT_PAYLOAD", "$.event.action_id", message="event action identity is invalid")
    if event.action_hash != action.hash:
        _fail("EVENT_HASH_MISMATCH", "$.event.action_hash", message="event action hash is invalid")
    if event.event_hash != pressure_event_hash(event):
        _fail("EVENT_HASH_MISMATCH", "$.event.event_hash", message="event canonical hash is invalid")
    _check_action_legal(state, action, config)
    after, payload = _transition(state, action, config)
    expected = _make_event(state, action, after, payload, config)
    if event.after_state_hash != expected.after_state_hash:
        _fail("STATE_HASH_MISMATCH", "$.event.after_state_hash", message="event does not commit expected state")
    if event.to_dict() != expected.to_dict():
        _fail("INVALID_EVENT_PAYLOAD", "$.event", message="event payload differs from deterministic transition")
    return after


def replay_pressure_events(
    initial_state: ExclusiveUpgradePressureState,
    events: Sequence[ExclusiveUpgradeEvent],
    config: ExclusiveUpgradePressureConfig,
) -> ExclusiveUpgradePressureState:
    """Replay any valid prefix of this feature-local pressure trace.

    The sequence counters here belong only to this isolated pressure slice;
    they are not a future Campaign/EventStore global sequencing rule.
    """

    if not isinstance(events, (list, tuple)):
        _fail("INVALID_EVENT_PAYLOAD", "$.events", message="event sequence required")
    if type(initial_state) is not ExclusiveUpgradePressureState:
        _fail("INVARIANT_VIOLATION", "$.initial_state", message="pressure state required")
    _check_state_config(initial_state, config)
    check_pressure_invariants(initial_state, config)
    current = initial_state
    for index, event in enumerate(events):
        if type(event) is not ExclusiveUpgradeEvent:
            _fail("INVALID_EVENT_PAYLOAD", f"$.events[{index}]", message="typed pressure event required")
        current = reduce_pressure_event(current, event, config)
    return current


def verify_terminal_pressure_trace(
    initial_state: ExclusiveUpgradePressureState,
    events: Sequence[ExclusiveUpgradeEvent],
    config: ExclusiveUpgradePressureConfig,
    expected_final_state_hash: str,
) -> ExclusiveUpgradePressureState:
    """Verify a complete A/B pressure trace and its expected terminal hash."""

    if type(expected_final_state_hash) is not str or _HEX64_RE.fullmatch(expected_final_state_hash) is None:
        _fail(
            "STATE_HASH_MISMATCH",
            "$.expected_final_state_hash",
            message="expected terminal state hash must be SHA-256 hex",
        )
    final_state = replay_pressure_events(initial_state, events, config)
    terminal_results = int(final_state.hazard_zone_traversed) + int(final_state.supply_cache_claimed)
    if terminal_results != 1:
        _fail(
            "EVENT_SEQUENCE_MISMATCH",
            "$.events",
            message="pressure trace is a legal prefix, not a terminal trace",
        )
    if legal_pressure_actions(final_state, config.protagonist_id, config):
        _fail(
            "INVARIANT_VIOLATION",
            "$.events",
            message="terminal pressure state still exposes legal actions",
        )
    if pressure_state_hash(final_state) != expected_final_state_hash:
        _fail(
            "STATE_HASH_MISMATCH",
            "$.expected_final_state_hash",
            message="terminal state hash does not match expected hash",
        )
    return final_state


def project_pressure_observation(
    state: ExclusiveUpgradePressureState,
    actor_id: str,
    config: ExclusiveUpgradePressureConfig,
) -> ExclusiveUpgradeObservation:
    check_pressure_invariants(state, config)
    legal_ids = legal_pressure_actions(state, actor_id, config)
    results: list[str] = []
    if state.hazard_zone_traversed:
        results.append("HAZARD_ZONE_TRAVERSED")
    if state.supply_cache_claimed:
        results.append("SUPPLY_CACHE_CLAIMED")
    return ExclusiveUpgradeObservation(
        growth_level=state.growth_level,
        has_exclusive_resource=state.exclusive_resource_count == 1,
        exclusive_resource_source_available=state.exclusive_resource_source_available,
        branch_committed=state.exclusive_resource_spent_on,
        stamina=state.stamina,
        game_minute=state.game_minute,
        legal_action_ids=legal_ids,
        completed_results=tuple(results),
    )


__all__ = [
    "CLAIM_SUPPLY_CACHE",
    "EVENT_CACHE_CLAIMED",
    "EVENT_GROWTH_UPGRADED",
    "EVENT_HAZARD_TRAVERSED",
    "EVENT_RESOURCE_RECOVERED",
    "EVENT_SUPPLY_STABILIZED",
    "ExclusiveUpgradeAction",
    "ExclusiveUpgradeEvent",
    "ExclusiveUpgradeObservation",
    "ExclusiveUpgradePressureConfig",
    "ExclusiveUpgradePressureState",
    "PRESSURE_ACTION_IDS",
    "PRESSURE_CONTRACT_VERSION",
    "PRESSURE_ERROR_CODES",
    "PRESSURE_FEATURE_ID",
    "PressureValidationError",
    "RECOVER_EXCLUSIVE_RESOURCE",
    "RESOURCE_SPENT_NONE",
    "RESOURCE_SPENT_SUPPLY_ROUTE",
    "RESOURCE_SPENT_UPGRADE",
    "STABILIZE_SUPPLY_ROUTE",
    "TRAVERSE_HAZARD_ZONE",
    "UPGRADE_GROWTH_OBJECT",
    "check_pressure_invariants",
    "initial_pressure_state",
    "legal_pressure_actions",
    "pressure_event_hash",
    "pressure_state_hash",
    "project_pressure_observation",
    "reduce_pressure_event",
    "replay_pressure_events",
    "resolve_pressure_action",
    "verify_terminal_pressure_trace",
]
