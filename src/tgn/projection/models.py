"""Immutable edge models for the Phase 9B2A projection slice."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

from ..core.hashing import canonical_json
from ..llm_player.models import LLMDecisionRequest


PROJECTION_SCHEMA_VERSION = 1
PROJECTION_COMPILER_ID = "phase9b2a-player-projection-v1"
PROJECTION_DRAFT_LABEL_FIELDS = frozenset(
    {
        "secondary_resource",
        "phase_day",
        "phase_night",
        "player_track",
        "base_track",
        "site_condition_subject",
        "site_condition_unstable",
        "site_condition_safe",
        "actor_report_goal",
        "actor_reported_goal",
        "build_window_runner",
        "build_field_rest",
        "build_quick_rest",
    }
)


def _validate_snapshot_value(value: Any, path: str) -> None:
    """Reject values that cannot be represented by canonical UTF-8 JSON."""

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} contains a non-string JSON object key")
            if any(0xD800 <= ord(character) <= 0xDFFF for character in key):
                raise ValueError(f"{path} contains a surrogate JSON object key")
            _validate_snapshot_value(item, f"{path}/{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_snapshot_value(item, f"{path}/{index}")
        return
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise ValueError(f"{path} contains a Unicode surrogate")
        return
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return
    raise TypeError(f"{path} contains unsupported JSON value {type(value).__name__}")


def _snapshot_json(value: Any, path: str) -> str:
    """Store one detached, canonical UTF-8 JSON snapshot."""

    try:
        _validate_snapshot_value(value, path)
        payload = canonical_json(value)
        payload.encode("utf-8")
        return payload
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError(f"{path} must contain canonical UTF-8 JSON values") from exc


@dataclass(frozen=True, init=False)
class ProjectionDraft:
    """Strict supplemental labels; it contains no runtime authority."""

    schema_version: int
    source_worldpack_hash: str
    _labels_json: str = field(repr=False)

    def __init__(self, schema_version: int, source_worldpack_hash: str, labels: dict[str, str]) -> None:
        if not isinstance(labels, dict):
            raise ValueError("labels must be a dict")
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "source_worldpack_hash", source_worldpack_hash)
        object.__setattr__(self, "_labels_json", _snapshot_json(labels, "labels"))

    @property
    def labels(self) -> dict[str, str]:
        return json.loads(self._labels_json)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_worldpack_hash": self.source_worldpack_hash,
            "labels": self.labels,
        }


@dataclass(frozen=True, init=False)
class PlayerProjectionMap:
    """Detached deterministic mapping from canonical IDs to display labels."""

    schema_version: int
    projection_compiler_id: str
    mechanics_profile: str
    source_worldpack_hash: str
    source_initial_state_hash: str
    content_locale: str
    _world_json: str = field(repr=False)
    _identities_json: str = field(repr=False)

    def __init__(
        self,
        schema_version: int,
        projection_compiler_id: str,
        mechanics_profile: str,
        source_worldpack_hash: str,
        source_initial_state_hash: str,
        content_locale: str,
        world: dict[str, Any],
        identities: dict[str, Any],
    ) -> None:
        if not isinstance(world, dict) or not isinstance(identities, dict):
            raise ValueError("world and identities must be dicts")
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "projection_compiler_id", projection_compiler_id)
        object.__setattr__(self, "mechanics_profile", mechanics_profile)
        object.__setattr__(self, "source_worldpack_hash", source_worldpack_hash)
        object.__setattr__(self, "source_initial_state_hash", source_initial_state_hash)
        object.__setattr__(self, "content_locale", content_locale)
        object.__setattr__(self, "_world_json", _snapshot_json(world, "world"))
        object.__setattr__(self, "_identities_json", _snapshot_json(identities, "identities"))

    @property
    def world(self) -> dict[str, Any]:
        return json.loads(self._world_json)

    @property
    def identities(self) -> dict[str, Any]:
        return json.loads(self._identities_json)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "projection_compiler_id": self.projection_compiler_id,
            "mechanics_profile": self.mechanics_profile,
            "source_worldpack_hash": self.source_worldpack_hash,
            "source_initial_state_hash": self.source_initial_state_hash,
            "content_locale": self.content_locale,
            "world": self.world,
            "identities": self.identities,
        }


@dataclass(frozen=True, init=False)
class PlayerPresentation:
    """Detached player-facing rendering of one canonical decision request."""

    schema_version: int
    source_worldpack_hash: str
    request_fingerprint: str
    content_locale: str
    _world_json: str = field(repr=False)
    _observation_json: str = field(repr=False)
    _choices_json: str = field(repr=False)

    def __init__(
        self,
        schema_version: int,
        source_worldpack_hash: str,
        request_fingerprint: str,
        content_locale: str,
        world: dict[str, Any],
        observation: dict[str, Any],
        choices: tuple[dict[str, Any], ...],
    ) -> None:
        if not isinstance(world, dict) or not isinstance(observation, dict):
            raise ValueError("world and observation must be dicts")
        if not isinstance(choices, tuple):
            choices = tuple(choices)
        if not all(isinstance(choice, dict) for choice in choices):
            raise ValueError("choices must contain dicts")
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "source_worldpack_hash", source_worldpack_hash)
        object.__setattr__(self, "request_fingerprint", request_fingerprint)
        object.__setattr__(self, "content_locale", content_locale)
        object.__setattr__(self, "_world_json", _snapshot_json(world, "world"))
        object.__setattr__(self, "_observation_json", _snapshot_json(observation, "observation"))
        object.__setattr__(self, "_choices_json", _snapshot_json(list(choices), "choices"))

    @property
    def world(self) -> dict[str, Any]:
        return json.loads(self._world_json)

    @property
    def observation(self) -> dict[str, Any]:
        return json.loads(self._observation_json)

    @property
    def choices(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(self._choices_json))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_worldpack_hash": self.source_worldpack_hash,
            "request_fingerprint": self.request_fingerprint,
            "content_locale": self.content_locale,
            "world": self.world,
            "observation": self.observation,
            "choices": list(self.choices),
        }


@dataclass(frozen=True, init=False)
class ProjectionCompilationResult:
    """Projection artifacts plus the initial canonical request and presentation."""

    draft: ProjectionDraft
    projection: PlayerProjectionMap
    projection_hash: str
    initial_request: LLMDecisionRequest
    initial_presentation: PlayerPresentation
    presentation_hash: str
    _report_json: str = field(repr=False)

    def __init__(
        self,
        draft: ProjectionDraft,
        projection: PlayerProjectionMap,
        projection_hash: str,
        initial_request: LLMDecisionRequest,
        initial_presentation: PlayerPresentation,
        presentation_hash: str,
        report: dict[str, Any],
    ) -> None:
        if not isinstance(report, dict):
            raise ValueError("report must be a dict")
        object.__setattr__(self, "draft", draft)
        object.__setattr__(self, "projection", projection)
        object.__setattr__(self, "projection_hash", projection_hash)
        object.__setattr__(self, "initial_request", initial_request)
        object.__setattr__(self, "initial_presentation", initial_presentation)
        object.__setattr__(self, "presentation_hash", presentation_hash)
        object.__setattr__(self, "_report_json", _snapshot_json(report, "report"))

    @property
    def report(self) -> dict[str, Any]:
        return json.loads(self._report_json)

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft": self.draft.to_dict(),
            "projection": self.projection.to_dict(),
            "projection_hash": self.projection_hash,
            "initial_request": self.initial_request.to_dict(),
            "initial_presentation": self.initial_presentation.to_dict(),
            "presentation_hash": self.presentation_hash,
            "report": self.report,
        }
