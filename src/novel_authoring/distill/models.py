"""Strict machine contracts for the Distillation Knowledge Layer.

Distill artifacts are a soft, provenance-aware knowledge layer.  The models in
this module deliberately do not expose a ``CANON`` information state: a
distilled observation can be useful to runtime planning without becoming a
fact in the selected edition.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DistillScope(StrEnum):
    SELF_BOOK = "SELF_BOOK"
    EXTERNAL_REFERENCE = "EXTERNAL_REFERENCE"
    COMPARATIVE_REFERENCE = "COMPARATIVE_REFERENCE"


class EvidenceMappingStatus(StrEnum):
    EXACT = "EXACT"
    PARTIAL = "PARTIAL"
    UNMAPPED = "UNMAPPED"
    CONFLICTING = "CONFLICTING"


class DistilledInformationClass(StrEnum):
    TEXTUAL_OBSERVATION = "TEXTUAL_OBSERVATION"
    INTERPRETATION = "INTERPRETATION"
    CRAFT_CONTROL = "CRAFT_CONTROL"
    CONTINUITY_CANDIDATE = "CONTINUITY_CANDIDATE"
    EMERGENT_FINDING = "EMERGENT_FINDING"


class ContinuityVerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    CONFLICTING = "CONFLICTING"
    RESOLVED = "RESOLVED"


DISTILL_DIMENSIONS = (
    "worldbuilding",
    "characters",
    "plot",
    "style",
    "narrative",
    "dialogue",
    "pacing",
    "themes",
    "continuity",
)
OBSERVATION_DIMENSIONS = DISTILL_DIMENSIONS + ("synthesis",)


class DistilledEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    chapter_hint: str | None = None
    mapping_status: EvidenceMappingStatus = EvidenceMappingStatus.UNMAPPED
    chapter_id: str | None = None
    source_span_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_line_range(self) -> DistilledEvidence:
        if self.end_line < self.start_line:
            raise ValueError("evidence end_line 不能小于 start_line")
        if self.mapping_status is EvidenceMappingStatus.EXACT and (
            not self.chapter_id or not self.source_span_ids
        ):
            raise ValueError("EXACT evidence 必须包含 chapter_id 和 source_span_ids")
        return self


class DistilledObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(min_length=1)
    dimension: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    scope_type: DistillScope
    scope_id: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence: list[DistilledEvidence] = Field(default_factory=list)
    runtime_uses: list[str] = Field(default_factory=list)
    information_class: DistilledInformationClass

    @model_validator(mode="after")
    def validate_dimension(self) -> DistilledObservation:
        if self.dimension not in OBSERVATION_DIMENSIONS:
            raise ValueError(f"observation dimension 无效：{self.dimension}")
        return self


class LiteraryArc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arc_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    start_segment: str = Field(min_length=1)
    end_segment: str = Field(min_length=1)
    start_chapter: str | None = None
    end_chapter: str | None = None
    state_before: str = ""
    causal_summary: str = Field(min_length=1)
    state_after: str = ""
    key_characters: list[str] = Field(default_factory=list)
    theme_questions: list[str] = Field(default_factory=list)
    representative_segments: list[str] = Field(default_factory=list)
    evidence: list[DistilledEvidence] = Field(default_factory=list)


class CraftControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    control_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    applies_to: list[str] = Field(default_factory=list)
    recommended_behavior: str = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    evidence: list[DistilledEvidence] = Field(default_factory=list)


class ContinuityCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    evidence: list[DistilledEvidence] = Field(default_factory=list)
    verification_status: ContinuityVerificationStatus = (
        ContinuityVerificationStatus.UNVERIFIED
    )
    runtime_resolution: str = Field(min_length=1)


class CharacterVoiceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    character_id: str = Field(min_length=1)
    voice_markers: list[str] = Field(default_factory=list)
    dialogue_controls: list[str] = Field(default_factory=list)
    evidence: list[DistilledEvidence] = Field(default_factory=list)


class ThemeQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    competing_answers: list[str] = Field(default_factory=list)
    evidence: list[DistilledEvidence] = Field(default_factory=list)


class DistillationPackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distill_id: str = Field(min_length=1)
    book_id: str = Field(min_length=1)
    edition_id: str = Field(min_length=1)
    scope: DistillScope
    mode: str = Field(min_length=1)
    depth: str = Field(min_length=1)
    dimensions: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    source_count: int = Field(ge=1)
    created_at: str = Field(min_length=1)
    package_version: str = Field(min_length=1)
    artifacts: dict[str, str] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_count(self) -> DistillationPackageManifest:
        if self.source_count != len(self.source_ids):
            raise ValueError("source_count 必须等于 source_ids 长度")
        unknown = sorted(set(self.dimensions) - set(DISTILL_DIMENSIONS))
        if unknown:
            raise ValueError(f"package 包含未知 dimension：{', '.join(unknown)}")
        return self


__all__ = [
    "ContinuityCandidate",
    "ContinuityVerificationStatus",
    "CraftControl",
    "DISTILL_DIMENSIONS",
    "DistillScope",
    "DistilledEvidence",
    "DistilledInformationClass",
    "DistilledObservation",
    "DistillationPackageManifest",
    "EvidenceMappingStatus",
    "LiteraryArc",
    "OBSERVATION_DIMENSIONS",
    "CharacterVoiceProfile",
    "ThemeQuestion",
]
