"""Immutable edge models for the Phase 9B2A projection slice."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True)
class ProjectionDraft:
    """Strict supplemental labels; it contains no runtime authority."""

    schema_version: int
    source_worldpack_hash: str
    labels: dict[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "labels", copy.deepcopy(self.labels))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_worldpack_hash": self.source_worldpack_hash,
            "labels": copy.deepcopy(self.labels),
        }


@dataclass(frozen=True)
class PlayerProjectionMap:
    """Detached deterministic mapping from canonical IDs to display labels."""

    schema_version: int
    projection_compiler_id: str
    mechanics_profile: str
    source_worldpack_hash: str
    source_initial_state_hash: str
    content_locale: str
    world: dict[str, Any]
    identities: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "world", copy.deepcopy(self.world))
        object.__setattr__(self, "identities", copy.deepcopy(self.identities))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "projection_compiler_id": self.projection_compiler_id,
            "mechanics_profile": self.mechanics_profile,
            "source_worldpack_hash": self.source_worldpack_hash,
            "source_initial_state_hash": self.source_initial_state_hash,
            "content_locale": self.content_locale,
            "world": copy.deepcopy(self.world),
            "identities": copy.deepcopy(self.identities),
        }


@dataclass(frozen=True)
class PlayerPresentation:
    """Detached player-facing rendering of one canonical decision request."""

    schema_version: int
    source_worldpack_hash: str
    request_fingerprint: str
    content_locale: str
    world: dict[str, Any]
    observation: dict[str, Any]
    choices: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "world", copy.deepcopy(self.world))
        object.__setattr__(self, "observation", copy.deepcopy(self.observation))
        object.__setattr__(self, "choices", tuple(copy.deepcopy(self.choices)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_worldpack_hash": self.source_worldpack_hash,
            "request_fingerprint": self.request_fingerprint,
            "content_locale": self.content_locale,
            "world": copy.deepcopy(self.world),
            "observation": copy.deepcopy(self.observation),
            "choices": copy.deepcopy(list(self.choices)),
        }


@dataclass(frozen=True)
class ProjectionCompilationResult:
    """Projection artifacts plus the initial canonical request and presentation."""

    draft: ProjectionDraft
    projection: PlayerProjectionMap
    projection_hash: str
    initial_request: LLMDecisionRequest
    initial_presentation: PlayerPresentation
    presentation_hash: str
    report: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "report", copy.deepcopy(self.report))

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft": self.draft.to_dict(),
            "projection": self.projection.to_dict(),
            "projection_hash": self.projection_hash,
            "initial_request": self.initial_request.to_dict(),
            "initial_presentation": self.initial_presentation.to_dict(),
            "presentation_hash": self.presentation_hash,
            "report": copy.deepcopy(self.report),
        }
