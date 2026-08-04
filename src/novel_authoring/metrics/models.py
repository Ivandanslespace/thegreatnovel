from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MetricRunStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    PROVISIONAL = "PROVISIONAL"
    INVALIDATED = "INVALIDATED"
    FAILED = "FAILED"


class MetricComponentStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PROVISIONAL = "PROVISIONAL"
    MISSING = "MISSING"
    STALE = "STALE"
    DISPUTED = "DISPUTED"
    INVALID = "INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    UNKNOWN_AFTER_ANALYSIS = "UNKNOWN_AFTER_ANALYSIS"
    NOT_ANALYZED = "NOT_ANALYZED"
    MISSING_OPTIONAL_AUTHOR_INPUT = "MISSING_OPTIONAL_AUTHOR_INPUT"


class ObservationSourceKind(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    DERIVED = "DERIVED"
    SEMANTIC_ESTIMATE = "SEMANTIC_ESTIMATE"
    AUTHOR_INPUT = "AUTHOR_INPUT"
    AUTHOR_OVERRIDE = "AUTHOR_OVERRIDE"
    UNKNOWN = "UNKNOWN"


class ContributionKind(StrEnum):
    EXACT_DELTA = "EXACT_DELTA"
    SEMANTIC_SUPPORT = "SEMANTIC_SUPPORT"
    AUTHOR_EVIDENCE = "AUTHOR_EVIDENCE"
    STATE_EVIDENCE = "STATE_EVIDENCE"


class EvidenceDirection(StrEnum):
    RAISES = "RAISES"
    LOWERS = "LOWERS"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"


class MetricComponentValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    component_id: str
    value: Any | None = None
    status: MetricComponentStatus = MetricComponentStatus.AVAILABLE
    source_kind: ObservationSourceKind
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = ""
    observation_id: str | None = None
    selected_reason: str = ""
    freshness: str = "FRESH"
    stale_reason: str = ""


class EvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: str | None = None
    component_id: str | None = None
    observation_id: str | None = None
    source_kind: ObservationSourceKind | None = None
    segment_id: str | None = None
    source_span_id: str | None = None
    event_id: str | None = None
    contribution_kind: ContributionKind
    direction: EvidenceDirection
    strength: float | None = Field(default=None, ge=0, le=1)
    exact_delta: float | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_quote: str
    rationale: str = ""


class MetricResultV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    status: MetricComponentStatus | MetricRunStatus
    score: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    band: str | None = None
    completeness: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    missing_components: list[str] = Field(default_factory=list)
    disputed_components: list[str] = Field(default_factory=list)
    stale_components: list[str] = Field(default_factory=list)
    components: dict[str, MetricComponentValue] = Field(default_factory=dict)
    formula_id: str
    config_hash: str
    evidence_summary: list[EvidenceSummary] = Field(default_factory=list)
    threshold_interpretation: str = ""
    recommended_action: str = ""
    semantic_confidence: float = Field(default=0.0, ge=0, le=1)
    data_freshness: str = "FRESH"
    dispute_status: str = "NONE"
    formula_contribution: dict[str, float | None] = Field(default_factory=dict)
    created_at: str


class MetricRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    book_id: str
    edition_id: str
    scope_type: str
    scope_id: str
    as_of_chapter: int | None = None
    as_of_event_seq: int
    projection_hash: str
    effective_content_sha256: str | None = None
    registry_hash: str
    config_hash: str
    status: MetricRunStatus
    completeness: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    input_bundle_hash: str
    requested_metric_ids: list[str] = Field(default_factory=list)
    created_at: str
    invalidated_at: str | None = None


class MetricRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    metric_id: str
    status: MetricRunStatus | MetricComponentStatus
    score: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    band: str | None = None
    completeness: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    components: dict[str, MetricComponentValue] = Field(default_factory=dict)
    missing_components: list[str] = Field(default_factory=list)
    disputed_components: list[str] = Field(default_factory=list)
    stale_components: list[str] = Field(default_factory=list)
    evidence_summary: list[EvidenceSummary] = Field(default_factory=list)
    threshold_interpretation: str = ""
    recommended_action: str = ""
    semantic_confidence: float = Field(default=0.0, ge=0, le=1)
    data_freshness: str = "FRESH"
    dispute_status: str = "NONE"
    formula_contribution: dict[str, float | None] = Field(default_factory=dict)
    formula_id: str


class MetricInputBundleV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    book_id: str
    edition_id: str
    scope_type: str
    scope_id: str
    as_of_chapter: int | None = None
    as_of_event_seq: int
    projection_hash: str
    effective_content_sha256: str | None = None
    registry_hash: str
    config_hash: str
    requested_metric_ids: list[str] | None = None
    components: dict[str, dict[str, MetricComponentValue]] = Field(default_factory=dict)
    evidence: dict[str, list[EvidenceSummary]] = Field(default_factory=dict)

    @property
    def input_bundle_hash(self) -> str:
        from novel_authoring.utils import json_dumps, sha256_bytes

        return sha256_bytes(json_dumps(self.model_dump(mode="json")).encode("utf-8"))


class ObservationResolution(BaseModel):
    """Auditable result of resolving one component's append-only history."""

    model_config = ConfigDict(extra="forbid")

    status: MetricComponentStatus
    effective_observation_id: str | None = None
    value: Any | None = None
    source_kind: ObservationSourceKind | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    selected_reason: str = ""
    ignored_observations: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    stale_reason: str = ""


class SemanticEvidenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str | None = None
    source_span_id: str | None = None
    event_id: str | None = None
    contribution_kind: ContributionKind = ContributionKind.SEMANTIC_SUPPORT
    direction: EvidenceDirection
    strength: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str
    rationale: str = ""
    exact_delta: float | None = None

    @model_validator(mode="after")
    def validate_exactness(self) -> SemanticEvidenceLink:
        if self.contribution_kind == ContributionKind.EXACT_DELTA and self.exact_delta is None:
            raise ValueError("EXACT_DELTA 必须提供 exact_delta")
        if self.contribution_kind != ContributionKind.EXACT_DELTA and self.exact_delta is not None:
            raise ValueError("语义证据不得冒充 exact_delta")
        if self.segment_id is None and self.source_span_id is None and self.event_id is None:
            raise ValueError("证据必须关联 segment、source span 或 event")
        return self


class SemanticObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    component_id: str
    value: Any | None = None
    status: MetricComponentStatus = MetricComponentStatus.AVAILABLE
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = ""
    unknown_reason: str | None = None
    evidence_links: list[SemanticEvidenceLink] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unknown(self) -> SemanticObservation:
        if (
            self.status
            in (
                MetricComponentStatus.MISSING,
                MetricComponentStatus.UNKNOWN,
                MetricComponentStatus.UNKNOWN_AFTER_ANALYSIS,
                MetricComponentStatus.NOT_ANALYZED,
            )
            and not self.unknown_reason
        ):
            raise ValueError("MISSING/UNKNOWN observation 必须填写 unknown_reason")
        return self


class MetricSemanticObservationsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    book_id: str
    edition_id: str
    chapter_id: str
    content_sha256: str
    registry_hash: str
    analyzer_version: str
    observations: list[SemanticObservation]
    notes: list[str] = Field(default_factory=list)
