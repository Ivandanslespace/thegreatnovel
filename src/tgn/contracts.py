"""Small JSON-shaped contracts between engine, persistence, story, and host layers.

The shared layer intentionally contains no world-specific resources, combat model,
relationship score, or growth interface. Concrete worlds earn those concepts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class EventDraft:
    """An uncommitted deterministic consequence produced by the engine."""

    event_type: str
    actor_id: str
    patches: tuple[JsonObject, ...]
    facts: tuple[JsonObject, ...]
    details: JsonObject = field(default_factory=dict)

    def to_dict(self) -> JsonObject:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ActionPreview:
    """Pure preflight result. Creating it must not alter durable state."""

    action_id: str
    expected_turn: int
    expected_state_hash: str
    legal: bool
    reason_code: str | None
    time_cost: int
    costs: tuple[JsonObject, ...]
    known_risks: tuple[str, ...]
    unknowns: tuple[str, ...]
    opportunity_costs: tuple[str, ...]
    preview_token: str

    def to_dict(self) -> JsonObject:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EngineResolution:
    """Complete in-memory result of one accepted decision before persistence."""

    action_id: str
    expected_turn: int
    expected_state_hash: str
    new_state: JsonObject
    events: tuple[EventDraft, ...]
    player_observation: JsonObject
    expansion_request: JsonObject | None = None


@dataclass(frozen=True, slots=True)
class NarrationRequest:
    """Grounding contract for prose generated after authoritative commit."""

    schema_version: str
    request_id: str
    campaign_id: str
    turn: int
    event_ids: tuple[str, ...]
    required_claims: tuple[JsonObject, ...]
    context: JsonObject
    request_hash: str

    def to_dict(self) -> JsonObject:
        return asdict(self)


def require_json_object(value: Mapping[str, Any] | JsonObject, *, name: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a JSON object")
    return dict(value)


def require_json_sequence(value: Sequence[Any], *, name: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a JSON array")
    return tuple(value)

