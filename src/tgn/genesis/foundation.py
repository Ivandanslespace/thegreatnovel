"""Bounded recorded-fixture foundation cohort candidate semantics.

This module is a candidate durable artifact only.  It describes one finite
recorded cohort and its vehicles; it is not a runtime registry, WorldPack,
GameState, Campaign, or population simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping, Sequence

from .blueprint import (
    ArtifactValidationError,
    BlueprintValidationError,
    CANDIDATE_DURABLE,
    FOUNDATION_REQUIREMENT_IDS,
    WorldBlueprint,
    _canonical_payload,
    _check_exact_fields,
    _fail,
    _hash_payload,
    _validate_hash,
    _validate_id,
    _validate_text,
)
from .pressure import (
    PRESSURE_CONTRACT_VERSION,
    PRESSURE_FEATURE_ID,
    ExclusiveUpgradePressureConfig,
)


FOUNDATION_SCHEMA_VERSION = 1
FOUNDATION_FEATURE_ID = "runtime.foundation_cohort_vehicle.v1"
FOUNDATION_CONTRACT_VERSION = "1"
FOUNDATION_LAUNCH_SYSTEM_ID = "system.public_mass_drop"
FOUNDATION_INITIAL_COHORT_ID = "cohort.initial"
FOUNDATION_PROTAGONIST_ACTOR_ID = "actor.protagonist"
FOUNDATION_PEER_ACTOR_IDS = ("actor.peer.1", "actor.peer.2")
FOUNDATION_PROTAGONIST_VEHICLE_ID = "vehicle.protagonist"
FOUNDATION_PEER_VEHICLE_IDS = ("vehicle.peer.1", "vehicle.peer.2")
FOUNDATION_LIVING_XUANWU_KIND = "vehicle.kind.living_xuanwu"
FOUNDATION_ORDINARY_VEHICLE_KINDS = (
    "vehicle.kind.peer_skiff",
    "vehicle.kind.peer_submersible",
)


class FoundationValidationError(ArtifactValidationError):
    """Stable validation error for the bounded foundation candidate."""


def _foundation_fail(code: str, path: str, *, message: str | None = None, actual: Any = None) -> None:
    _fail(code, path, message=message, actual=actual, error_cls=FoundationValidationError)


def _check_bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        _foundation_fail("INVALID_TYPE", path, message="boolean required", actual=value)
    return value


def _check_foundation_facts(blueprint: WorldBlueprint) -> None:
    if type(blueprint) is not WorldBlueprint:
        _foundation_fail("INVALID_TYPE", "$.blueprint", message="WorldBlueprint required", actual=blueprint)
    facts = {fact.requirement_id: fact for fact in blueprint.facts}
    expected = {
        "req.mass_drop": ("PUBLIC_SYSTEM", (FOUNDATION_LAUNCH_SYSTEM_ID,), (FOUNDATION_INITIAL_COHORT_ID,)),
        "req.peers": (
            "ACTOR_ENTITY",
            (FOUNDATION_INITIAL_COHORT_ID,),
            (FOUNDATION_PROTAGONIST_ACTOR_ID, *FOUNDATION_PEER_ACTOR_IDS),
        ),
        "req.vehicle": (
            "VEHICLE_ENTITY",
            (FOUNDATION_INITIAL_COHORT_ID,),
            (FOUNDATION_PROTAGONIST_VEHICLE_ID, *FOUNDATION_PEER_VEHICLE_IDS),
        ),
        "req.ownership": (
            "OWNERSHIP",
            (FOUNDATION_PROTAGONIST_ACTOR_ID, *FOUNDATION_PEER_ACTOR_IDS),
            (FOUNDATION_PROTAGONIST_VEHICLE_ID, *FOUNDATION_PEER_VEHICLE_IDS),
        ),
        "req.creature": (
            "PROTAGONIST_IDENTITY",
            (FOUNDATION_PROTAGONIST_ACTOR_ID,),
            (FOUNDATION_PROTAGONIST_VEHICLE_ID,),
        ),
        "req.other_vehicles": (
            "PEER_VEHICLE_CLASS",
            FOUNDATION_PEER_ACTOR_IDS,
            FOUNDATION_PEER_VEHICLE_IDS,
        ),
    }
    for requirement_id in FOUNDATION_REQUIREMENT_IDS:
        fact = facts.get(requirement_id)
        if fact is None:
            _foundation_fail(
                "FOUNDATION_REQUIREMENT_MISMATCH",
                f"$.blueprint.facts.{requirement_id}",
                message="required foundation fact is missing",
            )
        fact_kind, subject_ids, object_ids = expected[requirement_id]
        if (
            fact.fact_kind != fact_kind
            or fact.durability_tier != CANDIDATE_DURABLE
            or fact.visibility != "PUBLIC_WORLD"
            or fact.subject_ids != subject_ids
            or fact.object_ids != object_ids
        ):
            _foundation_fail(
                "FOUNDATION_REQUIREMENT_MISMATCH",
                f"$.blueprint.facts.{requirement_id}",
                message="foundation fact kind and stable subject/object identity differ from the recorded contract",
            )


@dataclass(frozen=True, slots=True, init=False)
class FoundationActorCandidate:
    actor_id: str
    role: str
    cohort_id: str
    vehicle_id: str

    def __init__(self, actor_id: str, role: str, cohort_id: str, vehicle_id: str) -> None:
        object.__setattr__(self, "actor_id", _validate_id(actor_id, "$.actor_id", error_cls=FoundationValidationError))
        if type(role) is not str or role not in {"PROTAGONIST", "PEER"}:
            _foundation_fail("INVALID_VALUE", "$.role", message="role must be PROTAGONIST or PEER", actual=role)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "cohort_id", _validate_id(cohort_id, "$.cohort_id", error_cls=FoundationValidationError))
        object.__setattr__(self, "vehicle_id", _validate_id(vehicle_id, "$.vehicle_id", error_cls=FoundationValidationError))

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "role": self.role,
            "cohort_id": self.cohort_id,
            "vehicle_id": self.vehicle_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FoundationActorCandidate":
        if not isinstance(data, Mapping):
            _foundation_fail("INVALID_TYPE", "$", message="object required", actual=data)
        allowed = {"actor_id", "role", "cohort_id", "vehicle_id"}
        _check_exact_fields(data, allowed, "$", error_cls=FoundationValidationError)
        return cls(**dict(data))


@dataclass(frozen=True, slots=True, init=False)
class FoundationVehicleCandidate:
    vehicle_id: str
    owner_id: str
    cohort_id: str
    vehicle_kind: str
    living: bool
    growth_object: bool

    def __init__(
        self,
        vehicle_id: str,
        owner_id: str,
        cohort_id: str,
        vehicle_kind: str,
        living: bool,
        growth_object: bool,
    ) -> None:
        object.__setattr__(self, "vehicle_id", _validate_id(vehicle_id, "$.vehicle_id", error_cls=FoundationValidationError))
        object.__setattr__(self, "owner_id", _validate_id(owner_id, "$.owner_id", error_cls=FoundationValidationError))
        object.__setattr__(self, "cohort_id", _validate_id(cohort_id, "$.cohort_id", error_cls=FoundationValidationError))
        object.__setattr__(self, "vehicle_kind", _validate_id(vehicle_kind, "$.vehicle_kind", error_cls=FoundationValidationError))
        object.__setattr__(self, "living", _check_bool(living, "$.living"))
        object.__setattr__(self, "growth_object", _check_bool(growth_object, "$.growth_object"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "owner_id": self.owner_id,
            "cohort_id": self.cohort_id,
            "vehicle_kind": self.vehicle_kind,
            "living": self.living,
            "growth_object": self.growth_object,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FoundationVehicleCandidate":
        if not isinstance(data, Mapping):
            _foundation_fail("INVALID_TYPE", "$", message="object required", actual=data)
        allowed = {"vehicle_id", "owner_id", "cohort_id", "vehicle_kind", "living", "growth_object"}
        _check_exact_fields(data, allowed, "$", error_cls=FoundationValidationError)
        return cls(**dict(data))


@dataclass(frozen=True, slots=True, init=False)
class FoundationCandidateComponent:
    schema_version: int
    feature_id: str
    contract_version: str
    launch_system_id: str
    initial_cohort_id: str
    protagonist_actor_id: str
    protagonist_vehicle_id: str
    _actors_json: str = field(repr=False, compare=True)
    _vehicles_json: str = field(repr=False, compare=True)
    source_requirement_ids: tuple[str, ...]
    source_blueprint_hash: str
    pressure_feature_id: str
    pressure_contract_version: str
    pressure_protagonist_id: str
    pressure_growth_object_id: str
    pressure_growth_object_owner_id: str
    pressure_exclusive_resource_id: str

    def __init__(
        self,
        schema_version: int,
        feature_id: str,
        contract_version: str,
        launch_system_id: str,
        initial_cohort_id: str,
        protagonist_actor_id: str,
        protagonist_vehicle_id: str,
        actors: Sequence[FoundationActorCandidate],
        vehicles: Sequence[FoundationVehicleCandidate],
        source_requirement_ids: Sequence[str],
        source_blueprint_hash: str,
        pressure_feature_id: str,
        pressure_contract_version: str,
        pressure_protagonist_id: str,
        pressure_growth_object_id: str,
        pressure_growth_object_owner_id: str,
        pressure_exclusive_resource_id: str,
    ) -> None:
        if type(schema_version) is not int or schema_version != FOUNDATION_SCHEMA_VERSION:
            _foundation_fail("INVALID_VALUE", "$.schema_version", message="foundation schema version is fixed", actual=schema_version)
        object.__setattr__(self, "schema_version", schema_version)
        if feature_id != FOUNDATION_FEATURE_ID or contract_version != FOUNDATION_CONTRACT_VERSION:
            _foundation_fail("FOUNDATION_CONFIG_MISMATCH", "$.feature_id", message="foundation feature identity is fixed")
        object.__setattr__(self, "feature_id", _validate_id(feature_id, "$.feature_id", error_cls=FoundationValidationError))
        object.__setattr__(self, "contract_version", _validate_text(contract_version, "$.contract_version", error_cls=FoundationValidationError, max_length=32))
        for name, value, expected in (
            ("launch_system_id", launch_system_id, FOUNDATION_LAUNCH_SYSTEM_ID),
            ("initial_cohort_id", initial_cohort_id, FOUNDATION_INITIAL_COHORT_ID),
            ("protagonist_actor_id", protagonist_actor_id, FOUNDATION_PROTAGONIST_ACTOR_ID),
            ("protagonist_vehicle_id", protagonist_vehicle_id, FOUNDATION_PROTAGONIST_VEHICLE_ID),
        ):
            if value != expected:
                _foundation_fail("FOUNDATION_CONFIG_MISMATCH", f"$.{name}", message="recorded foundation identity is fixed", actual=value)
            object.__setattr__(self, name, _validate_id(value, f"$.{name}", error_cls=FoundationValidationError))
        if not isinstance(actors, (list, tuple)) or not isinstance(vehicles, (list, tuple)):
            _foundation_fail("INVALID_TYPE", "$.actors", message="typed actor and vehicle arrays required")
        if len(actors) != 3 or len(vehicles) != 3:
            _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.actors", message="recorded foundation requires exactly three actors and vehicles")
        if any(type(item) is not FoundationActorCandidate for item in actors):
            _foundation_fail("INVALID_TYPE", "$.actors", message="FoundationActorCandidate objects required")
        if any(type(item) is not FoundationVehicleCandidate for item in vehicles):
            _foundation_fail("INVALID_TYPE", "$.vehicles", message="FoundationVehicleCandidate objects required")
        actor_by_id = {item.actor_id: item for item in actors}
        vehicle_by_id = {item.vehicle_id: item for item in vehicles}
        if set(actor_by_id) != {FOUNDATION_PROTAGONIST_ACTOR_ID, *FOUNDATION_PEER_ACTOR_IDS}:
            _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.actors", message="actor identities are not the recorded cohort")
        if set(vehicle_by_id) != {FOUNDATION_PROTAGONIST_VEHICLE_ID, *FOUNDATION_PEER_VEHICLE_IDS}:
            _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.vehicles", message="vehicle identities are not the recorded cohort")
        protagonist = actor_by_id[FOUNDATION_PROTAGONIST_ACTOR_ID]
        if protagonist.role != "PROTAGONIST" or protagonist.cohort_id != self.initial_cohort_id or protagonist.vehicle_id != self.protagonist_vehicle_id:
            _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.actors", message="protagonist identity/vehicle mapping is invalid")
        for actor_id in FOUNDATION_PEER_ACTOR_IDS:
            actor = actor_by_id[actor_id]
            if actor.role != "PEER" or actor.cohort_id != self.initial_cohort_id:
                _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.actors", message="peer identity/cohort mapping is invalid")
        expected_vehicle_owners = {
            FOUNDATION_PROTAGONIST_VEHICLE_ID: FOUNDATION_PROTAGONIST_ACTOR_ID,
            FOUNDATION_PEER_VEHICLE_IDS[0]: FOUNDATION_PEER_ACTOR_IDS[0],
            FOUNDATION_PEER_VEHICLE_IDS[1]: FOUNDATION_PEER_ACTOR_IDS[1],
        }
        for vehicle_id, owner_id in expected_vehicle_owners.items():
            vehicle = vehicle_by_id[vehicle_id]
            actor = actor_by_id[owner_id]
            if vehicle.owner_id != owner_id or vehicle.cohort_id != self.initial_cohort_id or actor.vehicle_id != vehicle_id:
                _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.vehicles", message="actor/vehicle ownership must be bijective")
        protagonist_vehicle = vehicle_by_id[FOUNDATION_PROTAGONIST_VEHICLE_ID]
        if (
            protagonist_vehicle.vehicle_kind != FOUNDATION_LIVING_XUANWU_KIND
            or protagonist_vehicle.living is not True
            or protagonist_vehicle.growth_object is not True
        ):
            _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.vehicles", message="protagonist vehicle must be the unique living xuanwu growth object")
        peer_vehicles = [vehicle_by_id[vehicle_id] for vehicle_id in FOUNDATION_PEER_VEHICLE_IDS]
        if any(vehicle.living or vehicle.growth_object for vehicle in peer_vehicles):
            _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.vehicles", message="peer vehicles must be ordinary non-living vehicles")
        peer_kinds = tuple(vehicle.vehicle_kind for vehicle in peer_vehicles)
        if (
            len(set(peer_kinds)) != 2
            or any(kind == FOUNDATION_LIVING_XUANWU_KIND or not kind.startswith("vehicle.kind.") for kind in peer_kinds)
        ):
            _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.vehicles", message="peer vehicle kinds must be distinct ordinary stable kinds")
        if sum(vehicle.living for vehicle in vehicles) != 1 or sum(vehicle.growth_object for vehicle in vehicles) != 1:
            _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.vehicles", message="exactly one living and growth vehicle is required")
        if not isinstance(source_requirement_ids, (list, tuple)) or any(type(item) is not str for item in source_requirement_ids):
            _foundation_fail("INVALID_TYPE", "$.source_requirement_ids", message="string requirement ID array required", actual=source_requirement_ids)
        if tuple(source_requirement_ids) != FOUNDATION_REQUIREMENT_IDS:
            _foundation_fail("FOUNDATION_REQUIREMENT_MISMATCH", "$.source_requirement_ids", message="foundation requirement identity/order is fixed")
        object.__setattr__(self, "_actors_json", _canonical_payload([item.to_dict() for item in actors], error_cls=FoundationValidationError))
        object.__setattr__(self, "_vehicles_json", _canonical_payload([item.to_dict() for item in vehicles], error_cls=FoundationValidationError))
        object.__setattr__(self, "source_requirement_ids", tuple(source_requirement_ids))
        object.__setattr__(self, "source_blueprint_hash", _validate_hash(source_blueprint_hash, "$.source_blueprint_hash", error_cls=FoundationValidationError))
        for name, value, expected in (
            ("pressure_feature_id", pressure_feature_id, PRESSURE_FEATURE_ID),
            ("pressure_contract_version", pressure_contract_version, PRESSURE_CONTRACT_VERSION),
            ("pressure_protagonist_id", pressure_protagonist_id, FOUNDATION_PROTAGONIST_ACTOR_ID),
            ("pressure_growth_object_id", pressure_growth_object_id, FOUNDATION_PROTAGONIST_VEHICLE_ID),
            ("pressure_growth_object_owner_id", pressure_growth_object_owner_id, FOUNDATION_PROTAGONIST_ACTOR_ID),
            ("pressure_exclusive_resource_id", pressure_exclusive_resource_id, "resource.energy_crystal"),
        ):
            if value != expected:
                _foundation_fail("FOUNDATION_CONFIG_MISMATCH", f"$.{name}", message="Foundation/Pressure identity differs from the recorded contract", actual=value)
            object.__setattr__(self, name, value)

    @property
    def actors(self) -> tuple[FoundationActorCandidate, ...]:
        try:
            return tuple(FoundationActorCandidate.from_dict(item) for item in json.loads(self._actors_json))
        except (FoundationValidationError, TypeError, ValueError) as exc:
            raise FoundationValidationError("FOUNDATION_HASH_MISMATCH", "$.actors", message="stored actor candidates are invalid") from exc

    @property
    def vehicles(self) -> tuple[FoundationVehicleCandidate, ...]:
        try:
            return tuple(FoundationVehicleCandidate.from_dict(item) for item in json.loads(self._vehicles_json))
        except (FoundationValidationError, TypeError, ValueError) as exc:
            raise FoundationValidationError("FOUNDATION_HASH_MISMATCH", "$.vehicles", message="stored vehicle candidates are invalid") from exc

    def semantic_payload(self) -> dict[str, Any]:
        """Return candidate semantics, excluding Blueprint provenance."""

        return {
            "schema_version": self.schema_version,
            "feature_id": self.feature_id,
            "contract_version": self.contract_version,
            "launch_system_id": self.launch_system_id,
            "initial_cohort_id": self.initial_cohort_id,
            "protagonist_actor_id": self.protagonist_actor_id,
            "protagonist_vehicle_id": self.protagonist_vehicle_id,
            "actors": [item.to_dict() for item in self.actors],
            "vehicles": [item.to_dict() for item in self.vehicles],
            "pressure_feature_id": self.pressure_feature_id,
            "pressure_contract_version": self.pressure_contract_version,
            "pressure_protagonist_id": self.pressure_protagonist_id,
            "pressure_growth_object_id": self.pressure_growth_object_id,
            "pressure_growth_object_owner_id": self.pressure_growth_object_owner_id,
            "pressure_exclusive_resource_id": self.pressure_exclusive_resource_id,
        }

    @property
    def hash(self) -> str:
        return _hash_payload(self.to_dict(), error_cls=FoundationValidationError)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "feature_id": self.feature_id,
            "contract_version": self.contract_version,
            "launch_system_id": self.launch_system_id,
            "initial_cohort_id": self.initial_cohort_id,
            "protagonist_actor_id": self.protagonist_actor_id,
            "protagonist_vehicle_id": self.protagonist_vehicle_id,
            "actors": [item.to_dict() for item in self.actors],
            "vehicles": [item.to_dict() for item in self.vehicles],
            "source_requirement_ids": list(self.source_requirement_ids),
            "source_blueprint_hash": self.source_blueprint_hash,
            "pressure_feature_id": self.pressure_feature_id,
            "pressure_contract_version": self.pressure_contract_version,
            "pressure_protagonist_id": self.pressure_protagonist_id,
            "pressure_growth_object_id": self.pressure_growth_object_id,
            "pressure_growth_object_owner_id": self.pressure_growth_object_owner_id,
            "pressure_exclusive_resource_id": self.pressure_exclusive_resource_id,
            "durability_tier": CANDIDATE_DURABLE,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FoundationCandidateComponent":
        if not isinstance(data, Mapping):
            _foundation_fail("INVALID_TYPE", "$", message="object required", actual=data)
        allowed = {
            "schema_version", "feature_id", "contract_version", "launch_system_id", "initial_cohort_id",
            "protagonist_actor_id", "protagonist_vehicle_id", "actors", "vehicles", "source_requirement_ids",
            "source_blueprint_hash", "pressure_feature_id", "pressure_contract_version", "pressure_protagonist_id",
            "pressure_growth_object_id", "pressure_growth_object_owner_id", "pressure_exclusive_resource_id", "durability_tier",
        }
        _check_exact_fields(data, allowed, "$", error_cls=FoundationValidationError)
        if data["durability_tier"] != CANDIDATE_DURABLE:
            _foundation_fail("INVALID_VALUE", "$.durability_tier", message="candidate foundation must remain durable candidate")
        if not isinstance(data["actors"], list) or not isinstance(data["vehicles"], list):
            _foundation_fail("INVALID_TYPE", "$.actors", message="actor and vehicle arrays required")
        actors = [FoundationActorCandidate.from_dict(item) for item in data["actors"]]
        vehicles = [FoundationVehicleCandidate.from_dict(item) for item in data["vehicles"]]
        return cls(
            schema_version=data["schema_version"], feature_id=data["feature_id"], contract_version=data["contract_version"],
            launch_system_id=data["launch_system_id"], initial_cohort_id=data["initial_cohort_id"],
            protagonist_actor_id=data["protagonist_actor_id"], protagonist_vehicle_id=data["protagonist_vehicle_id"],
            actors=actors, vehicles=vehicles, source_requirement_ids=data["source_requirement_ids"],
            source_blueprint_hash=data["source_blueprint_hash"], pressure_feature_id=data["pressure_feature_id"],
            pressure_contract_version=data["pressure_contract_version"], pressure_protagonist_id=data["pressure_protagonist_id"],
            pressure_growth_object_id=data["pressure_growth_object_id"], pressure_growth_object_owner_id=data["pressure_growth_object_owner_id"],
            pressure_exclusive_resource_id=data["pressure_exclusive_resource_id"],
        )


def build_foundation_candidate(
    blueprint: WorldBlueprint,
    pressure_config: ExclusiveUpgradePressureConfig,
) -> FoundationCandidateComponent:
    """Build the one recorded cohort/vehicle candidate from typed Blueprint facts."""

    if type(blueprint) is not WorldBlueprint:
        _foundation_fail("INVALID_TYPE", "$.blueprint", message="WorldBlueprint required", actual=blueprint)
    if type(pressure_config) is not ExclusiveUpgradePressureConfig:
        _foundation_fail("INVALID_TYPE", "$.pressure_config", message="ExclusiveUpgradePressureConfig required", actual=pressure_config)
    _check_foundation_facts(blueprint)
    actors = (
        FoundationActorCandidate(FOUNDATION_PROTAGONIST_ACTOR_ID, "PROTAGONIST", FOUNDATION_INITIAL_COHORT_ID, FOUNDATION_PROTAGONIST_VEHICLE_ID),
        FoundationActorCandidate(FOUNDATION_PEER_ACTOR_IDS[0], "PEER", FOUNDATION_INITIAL_COHORT_ID, FOUNDATION_PEER_VEHICLE_IDS[0]),
        FoundationActorCandidate(FOUNDATION_PEER_ACTOR_IDS[1], "PEER", FOUNDATION_INITIAL_COHORT_ID, FOUNDATION_PEER_VEHICLE_IDS[1]),
    )
    vehicles = (
        FoundationVehicleCandidate(FOUNDATION_PROTAGONIST_VEHICLE_ID, FOUNDATION_PROTAGONIST_ACTOR_ID, FOUNDATION_INITIAL_COHORT_ID, FOUNDATION_LIVING_XUANWU_KIND, True, True),
        FoundationVehicleCandidate(FOUNDATION_PEER_VEHICLE_IDS[0], FOUNDATION_PEER_ACTOR_IDS[0], FOUNDATION_INITIAL_COHORT_ID, FOUNDATION_ORDINARY_VEHICLE_KINDS[0], False, False),
        FoundationVehicleCandidate(FOUNDATION_PEER_VEHICLE_IDS[1], FOUNDATION_PEER_ACTOR_IDS[1], FOUNDATION_INITIAL_COHORT_ID, FOUNDATION_ORDINARY_VEHICLE_KINDS[1], False, False),
    )
    return FoundationCandidateComponent(
        schema_version=FOUNDATION_SCHEMA_VERSION,
        feature_id=FOUNDATION_FEATURE_ID,
        contract_version=FOUNDATION_CONTRACT_VERSION,
        launch_system_id=FOUNDATION_LAUNCH_SYSTEM_ID,
        initial_cohort_id=FOUNDATION_INITIAL_COHORT_ID,
        protagonist_actor_id=FOUNDATION_PROTAGONIST_ACTOR_ID,
        protagonist_vehicle_id=FOUNDATION_PROTAGONIST_VEHICLE_ID,
        actors=actors,
        vehicles=vehicles,
        source_requirement_ids=FOUNDATION_REQUIREMENT_IDS,
        source_blueprint_hash=blueprint.hash,
        pressure_feature_id=pressure_config.feature_id,
        pressure_contract_version=pressure_config.contract_version,
        pressure_protagonist_id=pressure_config.protagonist_id,
        pressure_growth_object_id=pressure_config.growth_object_id,
        pressure_growth_object_owner_id=pressure_config.growth_object_owner_id,
        pressure_exclusive_resource_id=pressure_config.exclusive_resource_id,
    )


def validate_foundation_blueprint_facts(blueprint: WorldBlueprint) -> None:
    """Validate the six typed Blueprint facts without producing a component."""

    _check_foundation_facts(blueprint)


def verify_foundation_candidate(
    blueprint: WorldBlueprint,
    pressure_config: ExclusiveUpgradePressureConfig,
    component: FoundationCandidateComponent,
) -> FoundationCandidateComponent:
    if type(component) is not FoundationCandidateComponent:
        _foundation_fail("INVALID_TYPE", "$.component", message="FoundationCandidateComponent required", actual=component)
    expected = build_foundation_candidate(blueprint, pressure_config)
    if component.to_dict() != expected.to_dict() or component.hash != expected.hash:
        _foundation_fail("FOUNDATION_HASH_MISMATCH", "$.component", message="persisted foundation component differs from deterministic recompilation")
    return expected


__all__ = [
    "FOUNDATION_CONTRACT_VERSION",
    "FOUNDATION_FEATURE_ID",
    "FOUNDATION_INITIAL_COHORT_ID",
    "FOUNDATION_LAUNCH_SYSTEM_ID",
    "FOUNDATION_LIVING_XUANWU_KIND",
    "FOUNDATION_ORDINARY_VEHICLE_KINDS",
    "FOUNDATION_PEER_ACTOR_IDS",
    "FOUNDATION_PEER_VEHICLE_IDS",
    "FOUNDATION_PROTAGONIST_ACTOR_ID",
    "FOUNDATION_PROTAGONIST_VEHICLE_ID",
    "FOUNDATION_REQUIREMENT_IDS",
    "FOUNDATION_SCHEMA_VERSION",
    "FoundationActorCandidate",
    "FoundationCandidateComponent",
    "FoundationValidationError",
    "FoundationVehicleCandidate",
    "build_foundation_candidate",
    "validate_foundation_blueprint_facts",
    "verify_foundation_candidate",
]
