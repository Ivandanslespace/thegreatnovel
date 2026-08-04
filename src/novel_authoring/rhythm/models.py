from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.domain.models import NarrativeFunction


class FeatureExtractorKind(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    SEMANTIC_ESTIMATE = "SEMANTIC_ESTIMATE"
    AUTHOR_POLICY = "AUTHOR_POLICY"
    UNKNOWN = "UNKNOWN"


class EmotionalIntensityBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"
    UNKNOWN = "UNKNOWN"


class OpeningMode(StrEnum):
    ACTION = "action"
    DIALOGUE = "dialogue"
    ENVIRONMENT = "environment"
    SYSTEM_NOTICE = "system_notice"
    RETROSPECTION = "retrospection"
    INTERNAL_MONOLOGUE = "internal_monologue"
    AFTERMATH = "aftermath"
    NEW_INFORMATION = "new_information"
    OTHER = "other"
    UNKNOWN = "unknown"


class EndingMode(StrEnum):
    NEW_THREAT = "new_threat"
    REWARD_REVEAL = "reward_reveal"
    DECISION = "decision"
    QUESTION = "question"
    CLIFFHANGER = "cliffhanger"
    ARRIVAL = "arrival"
    SYSTEM_NOTICE = "system_notice"
    RELATIONSHIP_BEAT = "relationship_beat"
    SCENE_CUT = "scene_cut"
    RESOLUTION = "resolution"
    OTHER = "other"
    UNKNOWN = "unknown"


class HookAction(StrEnum):
    HOLD = "HOLD"
    ADVANCE = "ADVANCE"
    RESOLVE = "RESOLVE"
    OVERDUE = "OVERDUE"


class ChapterSemanticFeaturesOutput(BaseModel):
    """Strict Codex file contract for semantic chapter annotations."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    book_id: str
    edition_id: str = "base"
    chapter_id: str
    content_sha256: str
    realized_primary_function: NarrativeFunction | None = None
    emotional_intensity_band: EmotionalIntensityBand = EmotionalIntensityBand.UNKNOWN
    opening_mode: OpeningMode = OpeningMode.UNKNOWN
    ending_mode: EndingMode = EndingMode.UNKNOWN
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    unknown_reasons: list[str] = Field(default_factory=list)
    analyzer_version: str


class ChapterFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str
    book_id: str
    edition_id: str
    chapter_id: str
    ordinal: int
    effective_content_sha256: str
    analyzer_version: str
    planned_primary_function: NarrativeFunction | None = None
    realized_primary_function: NarrativeFunction | None = None
    function_confidence: float | None = Field(default=None, ge=0, le=1)
    emotional_intensity_band: EmotionalIntensityBand = EmotionalIntensityBand.UNKNOWN
    emotional_confidence: float | None = Field(default=None, ge=0, le=1)
    title_raw: str
    normalized_title: str
    title_fingerprint: str
    opening_excerpt_raw: str
    opening_excerpt_prose: str
    opening_fingerprint_raw: str
    opening_fingerprint_prose: str
    opening_mode: OpeningMode = OpeningMode.UNKNOWN
    ending_excerpt_raw: str
    ending_excerpt_prose: str
    ending_fingerprint_raw: str
    ending_fingerprint_prose: str
    ending_mode: EndingMode = EndingMode.UNKNOWN
    extractor_kind: FeatureExtractorKind
    evidence: dict[str, Any] = Field(default_factory=dict)
    config_hash: str
    status: str = "ACTIVE"
    created_at: str
    invalidated_at: str | None = None


class RhythmDiagnosticSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    book_id: str
    edition_id: str
    as_of_chapter: int
    as_of_event_seq: int
    projection_hash: str
    config_hash: str
    analyzer_versions: dict[str, str]
    same_function_streak: dict[str, Any]
    high_emotion_streak: dict[str, Any]
    title_repetition: dict[str, Any]
    opening_similarity: dict[str, Any]
    ending_similarity: dict[str, Any]
    ending_mode_streak: dict[str, Any]
    hooks: dict[str, list[dict[str, Any]]]
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
