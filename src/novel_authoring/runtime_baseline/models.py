"""Strict contracts for the source-derived runtime baseline.

The baseline is a validated source snapshot, not a second Canon ledger.  It
is deliberately stored as files below an Edition analysis directory and never
written into the event store or the normalized runtime tables.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_authoring.distill.models import DistillScope, EvidenceMappingStatus


class BaselineStatus(StrEnum):
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    SOURCE_PARTIAL = "SOURCE_PARTIAL"
    UNKNOWN = "UNKNOWN"


class BaselineCategory(StrEnum):
    CHARACTER = "character"
    CAPABILITY = "capability"
    ITEM = "item"
    EQUIPMENT = "equipment"
    RESOURCE = "resource"
    KNOWLEDGE = "knowledge"
    RULE = "rule"
    EXCEPTION = "exception"
    PROMISE = "promise"


class BaselineEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    chapter_id: str | None = None
    source_span_ids: list[str] = Field(default_factory=list)
    mapping_status: EvidenceMappingStatus = EvidenceMappingStatus.UNMAPPED
    direct_text_confirmed: bool = False
    note: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> BaselineEvidence:
        if self.end_line < self.start_line:
            raise ValueError("baseline evidence end_line 不能小于 start_line")
        if self.mapping_status is EvidenceMappingStatus.EXACT and (
            not self.chapter_id or not self.source_span_ids
        ):
            raise ValueError("SOURCE_VERIFIED evidence 必须包含 chapter_id 和 source_span_ids")
        return self


class RuntimeBaselineEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(min_length=1)
    category: BaselineCategory
    subject_id: str | None = None
    name: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    status: BaselineStatus
    source_scope: DistillScope = DistillScope.SELF_BOOK
    source_kind: str = Field(min_length=1)
    evidence: list[BaselineEvidence] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    runtime_uses: list[str] = Field(default_factory=list)
    unknown_reason: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> RuntimeBaselineEntry:
        if self.status is BaselineStatus.UNKNOWN:
            if not self.unknown_reason:
                self.unknown_reason = "source evidence 尚未验证"
            return self
        if self.source_scope is not DistillScope.SELF_BOOK:
            raise ValueError("Runtime Baseline 只能由 SELF_BOOK source evidence 建立")
        if not self.evidence:
            raise ValueError("SOURCE_VERIFIED/SOURCE_PARTIAL entry 必须包含 source evidence")
        if self.source_kind not in {"SOURCE_TEXT", "AUTHOR_REVIEW"}:
            raise ValueError(
                "Runtime Baseline entry 必须来自 SOURCE_TEXT/AUTHOR_REVIEW；"
                "Distill observation 只能作为 recall"
            )
        return self


class RuntimeBaselineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    book_id: str = Field(min_length=1)
    edition_id: str = Field(min_length=1)
    boundary_chapter: int = Field(ge=0)
    scope: DistillScope = DistillScope.SELF_BOOK
    entries: list[RuntimeBaselineEntry] = Field(default_factory=list)


class RuntimeBaselineManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_id: str = Field(min_length=1)
    book_id: str = Field(min_length=1)
    edition_id: str = Field(min_length=1)
    boundary_chapter: int = Field(ge=0)
    source_type: str = "SOURCE_DERIVED_RUNTIME_BASELINE"
    scope: DistillScope = DistillScope.SELF_BOOK
    created_at: str = Field(min_length=1)
    package_version: str = "runtime-baseline-v1"
    entry_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)


class RuntimeBaseline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: RuntimeBaselineManifest
    entries: list[RuntimeBaselineEntry] = Field(default_factory=list)


class EarnedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    name: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    status: BaselineStatus
    source: str = Field(min_length=1)
    source_entry_id: str | None = None
    projection_record_id: str | None = None
    evidence: list[BaselineEvidence] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    availability: str = "AVAILABLE"
    costs: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    last_confirmed: int | None = Field(default=None, ge=0)


class AvailablePayoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payoff_id: str = Field(min_length=1)
    setup: str = Field(min_length=1)
    maturity_evidence: list[BaselineEvidence] = Field(default_factory=list)
    last_advanced: int | None = Field(default=None, ge=0)
    possible_payoff_forms: list[str] = Field(default_factory=list)
    payoff_cost: str = ""
    post_payoff_pressure: str = ""
    source_entry_id: str | None = None
    status: BaselineStatus


class EarnedSurface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surface_id: str = Field(min_length=1)
    book_id: str = Field(min_length=1)
    edition_id: str = Field(min_length=1)
    baseline_id: str = Field(min_length=1)
    projection_event_seq: int = Field(ge=0)
    projection_hash: str = ""
    created_at: str = Field(min_length=1)
    earned_capabilities: list[EarnedEntry] = Field(default_factory=list)
    available_items: list[EarnedEntry] = Field(default_factory=list)
    available_resources: list[EarnedEntry] = Field(default_factory=list)
    known_rules: list[EarnedEntry] = Field(default_factory=list)
    known_exceptions: list[EarnedEntry] = Field(default_factory=list)
    relationship_leverage: list[EarnedEntry] = Field(default_factory=list)
    institutional_authority: list[EarnedEntry] = Field(default_factory=list)
    open_setups: list[EarnedEntry] = Field(default_factory=list)
    actionable_knowledge: list[EarnedEntry] = Field(default_factory=list)
    available_payoffs: list[AvailablePayoff] = Field(default_factory=list)
    hard_unknowns: list[str] = Field(default_factory=list)


class RuntimeStateRecord(BaseModel):
    """A non-CANON runtime record after baseline and projection composition."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    name: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    status: str = Field(min_length=1)
    source: str = Field(min_length=1)
    baseline_entry_id: str | None = None
    projection_record_id: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    evidence: list[BaselineEvidence] = Field(default_factory=list)
    last_confirmed: int | None = Field(default=None, ge=0)


class EffectiveRuntimeState(BaseModel):
    """Read-only composition of a source baseline and the Canon projection delta."""

    model_config = ConfigDict(extra="forbid")

    state_id: str = Field(min_length=1)
    book_id: str = Field(min_length=1)
    edition_id: str = Field(min_length=1)
    baseline_id: str = Field(min_length=1)
    projection_event_seq: int = Field(ge=0)
    projection_hash: str = ""
    created_at: str = Field(min_length=1)
    records: dict[str, list[RuntimeStateRecord]] = Field(default_factory=dict)
    hard_unknowns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "AvailablePayoff",
    "BaselineCategory",
    "BaselineEvidence",
    "BaselineStatus",
    "EarnedEntry",
    "EarnedSurface",
    "EffectiveRuntimeState",
    "RuntimeBaseline",
    "RuntimeBaselineEntry",
    "RuntimeBaselineInput",
    "RuntimeBaselineManifest",
    "RuntimeStateRecord",
]
