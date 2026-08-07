from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.metrics.models import MetricComponentStatus, ObservationSourceKind
from novel_authoring.planning.innovation import InnovationFocus, InnovationLevel


class AuthorInputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: str = "CHAPTER"
    scope_id: str
    metric_id: str
    component_id: str
    value: Any | None = None
    status: MetricComponentStatus = MetricComponentStatus.AVAILABLE
    source_kind: ObservationSourceKind = ObservationSourceKind.AUTHOR_INPUT
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str
    chapter_id: str | None = None
    effective_content_sha256: str | None = None
    projection_hash: str | None = None
    registry_hash: str | None = None
    config_hash: str | None = None
    expected_active_observation_id: str | None = None
    evidence_links: list[dict[str, Any]] = Field(default_factory=list)


class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_stage: str
    edition_id: str | None = None
    require_complete_metrics: bool = False
    innovation_level: InnovationLevel | None = None
    innovation_focus: list[InnovationFocus] | None = None
    save_as_book_default: bool = False


class RetractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: str = "CHAPTER"
    scope_id: str
    reason: str = "作者撤回"
    expected_active_observation_id: str | None = None


class RecomputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: str = "CHAPTER"
    scope_id: str
    requested_metric_ids: list[str] | None = None
    effective_content_sha256: str | None = None
    projection_hash: str | None = None
    registry_hash: str | None = None
    config_hash: str | None = None
    expected_effective_observation_ids: dict[str, str] = Field(default_factory=dict)


class UserResponseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: dict[str, Any]


class AtlasActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_atlas_id: str | None = None
    expected_atlas_version: int | None = Field(default=None, ge=1)
    expected_manifest_hash: str | None = None
