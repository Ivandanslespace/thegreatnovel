from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.metrics.models import MetricComponentStatus, ObservationSourceKind


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
    expected_active_observation_id: str | None = None
    evidence_links: list[dict[str, Any]] = Field(default_factory=list)


class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_stage: str
    edition_id: str | None = None
    require_complete_metrics: bool = False


class RetractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: str = "CHAPTER"
    scope_id: str
