"""Serializable state contracts for TheGreatNovel."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List
import copy


@dataclass
class Event:
    turn: int
    kind: str
    action_id: str | None
    public_facts: Dict[str, Any]
    prev_hash: str
    event_hash: str
    hidden_facts: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "Event":
        return cls(
            turn=int(value.get("turn", 0)), kind=str(value.get("kind", "")),
            action_id=value.get("action_id"), public_facts=dict(value.get("public_facts", {})),
            prev_hash=str(value.get("prev_hash", "")), event_hash=str(value.get("event_hash", "")),
            hidden_facts=dict(value.get("hidden_facts", {})),
        )


@dataclass
class Campaign:
    schema_version: str
    campaign_id: str
    seed: str
    locale: str
    premise: str
    status: str
    tier: int
    turn: int
    clock: int
    world: Dict[str, Any]
    player: Dict[str, Any]
    factions: List[Dict[str, Any]]
    rival: Dict[str, Any]
    opportunities: List[Dict[str, Any]]
    hidden: Dict[str, Any]
    events: List[Event] = field(default_factory=list)
    chapters: List[Dict[str, Any]] = field(default_factory=list)
    knowledge: List[str] = field(default_factory=list)
    status_digest: str = ""
    finished: bool = False

    def to_dict(self) -> dict:
        value = asdict(self)
        value["events"] = [event.to_dict() if isinstance(event, Event) else event for event in self.events]
        return value

    @classmethod
    def from_dict(cls, value: dict) -> "Campaign":
        data = copy.deepcopy(value)
        data["events"] = [Event.from_dict(item) for item in data.get("events", [])]
        data.setdefault("chapters", [])
        data.setdefault("knowledge", [])
        data.setdefault("status_digest", "")
        data.setdefault("finished", False)
        return cls(**data)

    def clone(self) -> "Campaign":
        return Campaign.from_dict(self.to_dict())
