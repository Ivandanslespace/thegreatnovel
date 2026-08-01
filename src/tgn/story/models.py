"""Strict immutable edge models for Phase 9C1 Story artifacts."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from .common import (
    canonical_bytes,
    strict_int,
    validate_hash,
    validate_json_value,
    validate_prose,
    validate_stable_id,
)


STORY_SCHEMA_VERSION = 1
STORY_FORMAT_ID = "phase9c-story-v1"
NARRATION_REQUEST_FORMAT_ID = "phase9c-narration-request-v1"
TURN_ARTIFACT_FORMAT_ID = "phase9c-turn-narration-v1"
SUPPORTED_LOCALES = frozenset({"zh-CN", "en", "ar"})

STORY_FIELDS = frozenset(
    {
        "schema_version",
        "story_format_id",
        "story_id",
        "campaign_id",
        "campaign_manifest_hash",
        "worldpack_hash",
        "source_initial_state_hash",
        "player_projection_hash",
        "session_id",
        "initial_narration_locale",
        "initial_voice_id",
    }
)

REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "request_format_id",
        "narration_request_id",
        "narration_request_hash",
        "story_id",
        "turn_id",
        "campaign_id",
        "session_id",
        "accepted_decision_number",
        "recorded_decision_index",
        "request_fingerprint_before",
        "source_request_hash",
        "choice_id",
        "action_type",
        "action_id",
        "params",
        "duration_minutes",
        "stamina_cost",
        "event_seq_start",
        "event_seq_end",
        "state_hash_before",
        "state_hash_after",
        "narration_locale",
        "voice_id",
        "public_brief",
        "claim_requirements",
    }
)

RESPONSE_FIELDS = frozenset(
    {
        "schema_version",
        "narration_request_id",
        "narration_request_hash",
        "locale",
        "claims",
        "prose",
    }
)

TURN_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_format_id",
        "turn_artifact_hash",
        "story_id",
        "turn_id",
        "narration_request_id",
        "narration_request_hash",
        "source_request_hash",
        "campaign_id",
        "session_id",
        "accepted_decision_number",
        "recorded_decision_index",
        "request_fingerprint_before",
        "choice_id",
        "action_type",
        "action_id",
        "params",
        "duration_minutes",
        "stamina_cost",
        "event_seq_start",
        "event_seq_end",
        "state_hash_before",
        "state_hash_after",
        "narration_locale",
        "voice_id",
        "claims",
        "prose",
    }
)

_TURN_RE = re.compile(r"turn-(?P<number>[0-9]{6,})\Z")

STORY_ERROR_CODES = frozenset(
    {
        "INVALID_STORY_INPUT",
        "STORY_ALREADY_EXISTS",
        "STORY_NOT_FOUND",
        "STORY_INTEGRITY_MISMATCH",
        "CAMPAIGN_BINDING_MISMATCH",
        "CAMPAIGN_INTEGRITY_MISMATCH",
        "CAMPAIGN_SNAPSHOT_CHANGED",
        "NARRATION_REQUEST_NOT_FOUND",
        "NARRATION_REQUEST_PENDING",
        "NARRATION_RESPONSE_INVALID",
        "TURN_ALREADY_COMMITTED",
        "TURN_CONFLICT",
        "STORY_INCOMPLETE",
        "UNSUPPORTED_STORY_FORMAT",
        "STORY_PUBLICATION_UNAVAILABLE",
    }
)


class StoryError(ValueError):
    """Stable, safe boundary error for Story operations."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code if code in STORY_ERROR_CODES else "STORY_INTEGRITY_MISMATCH"
        self.message = str(message).replace("\r", " ").replace("\n", " ")
        self.message = self.message.encode("utf-8", "replace").decode("utf-8")
        super().__init__(f"{self.code}: {self.message}")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


def _require_exact(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} has an invalid field set")
    validate_json_value(value, path=label)
    return value


def _hash_field(value: Any, field: str) -> str:
    return validate_hash(value, field)


def _validate_locale(value: Any, field: str) -> str:
    if not isinstance(value, str) or value not in SUPPORTED_LOCALES:
        raise ValueError(f"{field} is unsupported")
    return value


def _validate_turn_id(value: Any) -> int:
    if not isinstance(value, str):
        raise ValueError("turn_id must be a string")
    match = _TURN_RE.fullmatch(value)
    if match is None:
        raise ValueError("turn_id is invalid")
    number = int(match.group("number"))
    if number <= 0 or value != f"turn-{number:06d}":
        raise ValueError("turn_id is not canonical")
    return number


def _validate_public_brief(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "observation_before",
        "observation_after",
        "action_result",
    }:
        raise ValueError("public_brief has an invalid field set")
    if not isinstance(value["observation_before"], dict) or not isinstance(value["observation_after"], dict):
        raise ValueError("public observations must be objects")
    action_result = value["action_result"]
    action_fields = {
        "choice_id",
        "action_type",
        "action_id",
        "accepted_decision_number",
        "event_types",
        "event_seq_start",
        "event_seq_end",
        "public_event_facts",
    }
    if not isinstance(action_result, dict) or set(action_result) != action_fields:
        raise ValueError("public action_result has an invalid field set")
    if not isinstance(action_result["choice_id"], str) or not isinstance(action_result["action_type"], str):
        raise ValueError("public action_result identity is invalid")
    if not isinstance(action_result["action_id"], str):
        raise ValueError("public action_result action_id is invalid")
    strict_int(action_result["accepted_decision_number"], "accepted_decision_number", positive=True)
    event_types = action_result["event_types"]
    if not isinstance(event_types, list) or len(event_types) != 1 or not isinstance(event_types[0], str):
        raise ValueError("public action_result must contain one event type")
    event_start = strict_int(action_result["event_seq_start"], "event_seq_start", nonnegative=True)
    event_end = strict_int(action_result["event_seq_end"], "event_seq_end", nonnegative=True)
    if event_start != event_end:
        raise ValueError("public event range must contain one event")
    public_facts = action_result["public_event_facts"]
    if not isinstance(public_facts, list) or len(public_facts) != 1:
        raise ValueError("public action_result must contain one public event fact")
    fact = public_facts[0]
    if not isinstance(fact, dict) or set(fact) != {"event_seq", "decision_seq", "event_type", "facts"}:
        raise ValueError("public event fact has an invalid field set")
    strict_int(fact["event_seq"], "public_event_facts.event_seq", nonnegative=True)
    strict_int(fact["decision_seq"], "public_event_facts.decision_seq", nonnegative=True)
    if not isinstance(fact["event_type"], str) or not isinstance(fact["facts"], dict):
        raise ValueError("public event fact is invalid")


@dataclass(frozen=True)
class StoryManifest:
    schema_version: int
    story_format_id: str
    story_id: str
    campaign_id: str
    campaign_manifest_hash: str
    worldpack_hash: str
    source_initial_state_hash: str
    player_projection_hash: str
    session_id: str
    initial_narration_locale: str
    initial_voice_id: str

    @classmethod
    def from_dict(cls, value: Any) -> "StoryManifest":
        value = _require_exact(value, STORY_FIELDS, "story.json")
        strict_int(value["schema_version"], "schema_version")
        if value["schema_version"] != STORY_SCHEMA_VERSION or value["story_format_id"] != STORY_FORMAT_ID:
            raise ValueError("unsupported Story format")
        story_id = validate_stable_id(value["story_id"], "story_id")
        campaign_id = validate_stable_id(value["campaign_id"], "campaign_id")
        session_id = validate_stable_id(value["session_id"], "session_id")
        if session_id != campaign_id:
            raise ValueError("session_id does not match campaign_id")
        for field in (
            "campaign_manifest_hash",
            "worldpack_hash",
            "source_initial_state_hash",
            "player_projection_hash",
        ):
            _hash_field(value[field], field)
        locale = _validate_locale(value["initial_narration_locale"], "initial_narration_locale")
        voice_id = validate_stable_id(value["initial_voice_id"], "initial_voice_id")
        return cls(
            schema_version=value["schema_version"],
            story_format_id=value["story_format_id"],
            story_id=story_id,
            campaign_id=campaign_id,
            campaign_manifest_hash=value["campaign_manifest_hash"],
            worldpack_hash=value["worldpack_hash"],
            source_initial_state_hash=value["source_initial_state_hash"],
            player_projection_hash=value["player_projection_hash"],
            session_id=session_id,
            initial_narration_locale=locale,
            initial_voice_id=voice_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "story_format_id": self.story_format_id,
            "story_id": self.story_id,
            "campaign_id": self.campaign_id,
            "campaign_manifest_hash": self.campaign_manifest_hash,
            "worldpack_hash": self.worldpack_hash,
            "source_initial_state_hash": self.source_initial_state_hash,
            "player_projection_hash": self.player_projection_hash,
            "session_id": self.session_id,
            "initial_narration_locale": self.initial_narration_locale,
            "initial_voice_id": self.initial_voice_id,
        }


@dataclass(frozen=True)
class NarrationRequest:
    schema_version: int
    request_format_id: str
    narration_request_id: str
    narration_request_hash: str
    story_id: str
    turn_id: str
    campaign_id: str
    session_id: str
    accepted_decision_number: int
    recorded_decision_index: int
    request_fingerprint_before: str
    source_request_hash: str
    choice_id: str
    action_type: str
    action_id: str
    params: dict[str, Any]
    duration_minutes: int | None
    stamina_cost: int
    event_seq_start: int
    event_seq_end: int
    state_hash_before: str
    state_hash_after: str
    narration_locale: str
    voice_id: str
    public_brief: dict[str, Any]
    claim_requirements: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, value: Any) -> "NarrationRequest":
        value = _require_exact(value, REQUEST_FIELDS, "Narration Request")
        if type(value["schema_version"]) is not int or value["schema_version"] != STORY_SCHEMA_VERSION:
            raise ValueError("unsupported request schema")
        if value["request_format_id"] != NARRATION_REQUEST_FORMAT_ID:
            raise ValueError("unsupported request format")
        story_id = validate_stable_id(value["story_id"], "story_id")
        turn_number = _validate_turn_id(value["turn_id"])
        turn_id = value["turn_id"]
        campaign_id = validate_stable_id(value["campaign_id"], "campaign_id")
        session_id = validate_stable_id(value["session_id"], "session_id")
        if session_id != campaign_id:
            raise ValueError("request session binding is invalid")
        if value["narration_request_id"] != f"{story_id}:{turn_id}":
            raise ValueError("narration_request_id is invalid")
        for field in (
            "narration_request_hash",
            "request_fingerprint_before",
            "source_request_hash",
            "state_hash_before",
            "state_hash_after",
        ):
            _hash_field(value[field], field)
        accepted = strict_int(value["accepted_decision_number"], "accepted_decision_number", positive=True)
        recorded = strict_int(value["recorded_decision_index"], "recorded_decision_index", positive=True)
        if accepted != turn_number or accepted != int(turn_id[5:]):
            raise ValueError("request turn number does not match accepted decision")
        if not isinstance(value["choice_id"], str) or not value["choice_id"]:
            raise ValueError("choice_id is invalid")
        if not isinstance(value["action_type"], str) or not value["action_type"]:
            raise ValueError("action_type is invalid")
        if not isinstance(value["action_id"], str) or not value["action_id"]:
            raise ValueError("action_id is invalid")
        if not isinstance(value["params"], dict):
            raise ValueError("params must be an object")
        duration = value["duration_minutes"]
        if duration is not None:
            strict_int(duration, "duration_minutes")
        stamina = strict_int(value["stamina_cost"], "stamina_cost")
        event_start = strict_int(value["event_seq_start"], "event_seq_start", nonnegative=True)
        event_end = strict_int(value["event_seq_end"], "event_seq_end", nonnegative=True)
        if event_start != event_end:
            raise ValueError("Phase 9C1 requires a single event range")
        locale = _validate_locale(value["narration_locale"], "narration_locale")
        voice_id = validate_stable_id(value["voice_id"], "voice_id")
        _validate_public_brief(value["public_brief"])
        if not isinstance(value["claim_requirements"], list):
            raise ValueError("claim_requirements must be a list")
        return cls(
            schema_version=value["schema_version"],
            request_format_id=value["request_format_id"],
            narration_request_id=value["narration_request_id"],
            narration_request_hash=value["narration_request_hash"],
            story_id=story_id,
            turn_id=turn_id,
            campaign_id=campaign_id,
            session_id=session_id,
            accepted_decision_number=accepted,
            recorded_decision_index=recorded,
            request_fingerprint_before=value["request_fingerprint_before"],
            source_request_hash=value["source_request_hash"],
            choice_id=value["choice_id"],
            action_type=value["action_type"],
            action_id=value["action_id"],
            params=copy.deepcopy(value["params"]),
            duration_minutes=duration,
            stamina_cost=stamina,
            event_seq_start=event_start,
            event_seq_end=event_end,
            state_hash_before=value["state_hash_before"],
            state_hash_after=value["state_hash_after"],
            narration_locale=locale,
            voice_id=voice_id,
            public_brief=copy.deepcopy(value["public_brief"]),
            claim_requirements=copy.deepcopy(value["claim_requirements"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_format_id": self.request_format_id,
            "narration_request_id": self.narration_request_id,
            "narration_request_hash": self.narration_request_hash,
            "story_id": self.story_id,
            "turn_id": self.turn_id,
            "campaign_id": self.campaign_id,
            "session_id": self.session_id,
            "accepted_decision_number": self.accepted_decision_number,
            "recorded_decision_index": self.recorded_decision_index,
            "request_fingerprint_before": self.request_fingerprint_before,
            "source_request_hash": self.source_request_hash,
            "choice_id": self.choice_id,
            "action_type": self.action_type,
            "action_id": self.action_id,
            "params": copy.deepcopy(self.params),
            "duration_minutes": self.duration_minutes,
            "stamina_cost": self.stamina_cost,
            "event_seq_start": self.event_seq_start,
            "event_seq_end": self.event_seq_end,
            "state_hash_before": self.state_hash_before,
            "state_hash_after": self.state_hash_after,
            "narration_locale": self.narration_locale,
            "voice_id": self.voice_id,
            "public_brief": copy.deepcopy(self.public_brief),
            "claim_requirements": copy.deepcopy(self.claim_requirements),
        }


@dataclass(frozen=True)
class NarrationResponse:
    schema_version: int
    narration_request_id: str
    narration_request_hash: str
    locale: str
    claims: list[dict[str, Any]]
    prose: str

    @classmethod
    def from_dict(cls, value: Any) -> "NarrationResponse":
        value = _require_exact(value, RESPONSE_FIELDS, "Narration Response")
        if type(value["schema_version"]) is not int or value["schema_version"] != STORY_SCHEMA_VERSION:
            raise ValueError("unsupported response schema")
        if not isinstance(value["narration_request_id"], str) or not value["narration_request_id"]:
            raise ValueError("narration_request_id is invalid")
        _hash_field(value["narration_request_hash"], "narration_request_hash")
        locale = _validate_locale(value["locale"], "locale")
        if not isinstance(value["claims"], list):
            raise ValueError("claims must be a list")
        prose = validate_prose(value["prose"])
        return cls(
            schema_version=value["schema_version"],
            narration_request_id=value["narration_request_id"],
            narration_request_hash=value["narration_request_hash"],
            locale=locale,
            claims=copy.deepcopy(value["claims"]),
            prose=prose,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "narration_request_id": self.narration_request_id,
            "narration_request_hash": self.narration_request_hash,
            "locale": self.locale,
            "claims": copy.deepcopy(self.claims),
            "prose": self.prose,
        }


@dataclass(frozen=True)
class TurnNarrationArtifact:
    schema_version: int
    artifact_format_id: str
    turn_artifact_hash: str
    story_id: str
    turn_id: str
    narration_request_id: str
    narration_request_hash: str
    source_request_hash: str
    campaign_id: str
    session_id: str
    accepted_decision_number: int
    recorded_decision_index: int
    request_fingerprint_before: str
    choice_id: str
    action_type: str
    action_id: str
    params: dict[str, Any]
    duration_minutes: int | None
    stamina_cost: int
    event_seq_start: int
    event_seq_end: int
    state_hash_before: str
    state_hash_after: str
    narration_locale: str
    voice_id: str
    claims: list[dict[str, Any]]
    prose: str

    @classmethod
    def from_dict(cls, value: Any) -> "TurnNarrationArtifact":
        value = _require_exact(value, TURN_FIELDS, "Turn artifact")
        if type(value["schema_version"]) is not int or value["schema_version"] != STORY_SCHEMA_VERSION:
            raise ValueError("unsupported turn schema")
        if value["artifact_format_id"] != TURN_ARTIFACT_FORMAT_ID:
            raise ValueError("unsupported turn format")
        story_id = validate_stable_id(value["story_id"], "story_id")
        turn_number = _validate_turn_id(value["turn_id"])
        turn_id = value["turn_id"]
        if value["narration_request_id"] != f"{story_id}:{turn_id}":
            raise ValueError("turn request identity is invalid")
        for field in (
            "turn_artifact_hash",
            "narration_request_hash",
            "source_request_hash",
            "request_fingerprint_before",
            "state_hash_before",
            "state_hash_after",
        ):
            _hash_field(value[field], field)
        campaign_id = validate_stable_id(value["campaign_id"], "campaign_id")
        session_id = validate_stable_id(value["session_id"], "session_id")
        if campaign_id != session_id:
            raise ValueError("turn session binding is invalid")
        accepted = strict_int(value["accepted_decision_number"], "accepted_decision_number", positive=True)
        if accepted != turn_number or accepted != int(turn_id[5:]):
            raise ValueError("turn number is invalid")
        strict_int(value["recorded_decision_index"], "recorded_decision_index", positive=True)
        if not isinstance(value["choice_id"], str) or not isinstance(value["action_type"], str) or not isinstance(value["action_id"], str):
            raise ValueError("turn action identity is invalid")
        if not isinstance(value["params"], dict):
            raise ValueError("turn params must be object")
        if value["duration_minutes"] is not None:
            strict_int(value["duration_minutes"], "duration_minutes")
        strict_int(value["stamina_cost"], "stamina_cost")
        event_start = strict_int(value["event_seq_start"], "event_seq_start", nonnegative=True)
        event_end = strict_int(value["event_seq_end"], "event_seq_end", nonnegative=True)
        if event_start != event_end:
            raise ValueError("turn event range must contain one event")
        locale = _validate_locale(value["narration_locale"], "narration_locale")
        voice_id = validate_stable_id(value["voice_id"], "voice_id")
        if not isinstance(value["claims"], list):
            raise ValueError("turn claims must be a list")
        prose = validate_prose(value["prose"])
        return cls(
            schema_version=value["schema_version"],
            artifact_format_id=value["artifact_format_id"],
            turn_artifact_hash=value["turn_artifact_hash"],
            story_id=story_id,
            turn_id=turn_id,
            narration_request_id=value["narration_request_id"],
            narration_request_hash=value["narration_request_hash"],
            source_request_hash=value["source_request_hash"],
            campaign_id=campaign_id,
            session_id=session_id,
            accepted_decision_number=accepted,
            recorded_decision_index=value["recorded_decision_index"],
            request_fingerprint_before=value["request_fingerprint_before"],
            choice_id=value["choice_id"],
            action_type=value["action_type"],
            action_id=value["action_id"],
            params=copy.deepcopy(value["params"]),
            duration_minutes=value["duration_minutes"],
            stamina_cost=value["stamina_cost"],
            event_seq_start=event_start,
            event_seq_end=event_end,
            state_hash_before=value["state_hash_before"],
            state_hash_after=value["state_hash_after"],
            narration_locale=locale,
            voice_id=voice_id,
            claims=copy.deepcopy(value["claims"]),
            prose=prose,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_format_id": self.artifact_format_id,
            "turn_artifact_hash": self.turn_artifact_hash,
            "story_id": self.story_id,
            "turn_id": self.turn_id,
            "narration_request_id": self.narration_request_id,
            "narration_request_hash": self.narration_request_hash,
            "source_request_hash": self.source_request_hash,
            "campaign_id": self.campaign_id,
            "session_id": self.session_id,
            "accepted_decision_number": self.accepted_decision_number,
            "recorded_decision_index": self.recorded_decision_index,
            "request_fingerprint_before": self.request_fingerprint_before,
            "choice_id": self.choice_id,
            "action_type": self.action_type,
            "action_id": self.action_id,
            "params": copy.deepcopy(self.params),
            "duration_minutes": self.duration_minutes,
            "stamina_cost": self.stamina_cost,
            "event_seq_start": self.event_seq_start,
            "event_seq_end": self.event_seq_end,
            "state_hash_before": self.state_hash_before,
            "state_hash_after": self.state_hash_after,
            "narration_locale": self.narration_locale,
            "voice_id": self.voice_id,
            "claims": copy.deepcopy(self.claims),
            "prose": self.prose,
        }


def request_hash(value: dict[str, Any]) -> str:
    payload = copy.deepcopy(value)
    payload.pop("narration_request_hash", None)
    return __import__("hashlib").sha256(canonical_bytes(payload)).hexdigest()


def turn_artifact_hash(value: dict[str, Any]) -> str:
    payload = copy.deepcopy(value)
    payload.pop("turn_artifact_hash", None)
    return __import__("hashlib").sha256(canonical_bytes(payload)).hexdigest()


__all__ = [
    "NARRATION_REQUEST_FORMAT_ID",
    "REQUEST_FIELDS",
    "RESPONSE_FIELDS",
    "STORY_ERROR_CODES",
    "STORY_FIELDS",
    "STORY_FORMAT_ID",
    "STORY_SCHEMA_VERSION",
    "SUPPORTED_LOCALES",
    "TURN_ARTIFACT_FORMAT_ID",
    "TURN_FIELDS",
    "NarrationRequest",
    "NarrationResponse",
    "StoryError",
    "StoryManifest",
    "TurnNarrationArtifact",
    "request_hash",
    "turn_artifact_hash",
]
