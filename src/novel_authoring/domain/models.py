from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InformationStatus(StrEnum):
    CANON = "CANON"
    AUTHOR_INTENT = "AUTHOR_INTENT"
    APPROVED_OUTLINE = "APPROVED_OUTLINE"
    INFERENCE = "INFERENCE"
    CANDIDATE = "CANDIDATE"
    PROSE_ONLY = "PROSE_ONLY"


class ContinuationMode(StrEnum):
    FAITHFUL = "faithful_continuation"
    CONSTRAINED_INNOVATION = "constrained_innovation"
    EXPLICIT_REVISION = "explicit_revision"


class DraftStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    AUTHOR_APPROVED = "AUTHOR_APPROVED"
    CANON_COMMITTED = "CANON_COMMITTED"
    REJECTED = "REJECTED"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class NarrativeFunction(StrEnum):
    SETUP = "setup"
    PRESSURE_BUILD = "pressure_build"
    CHOICE = "choice"
    DISCOVERY = "discovery"
    PROGRESS = "progress"
    PARTIAL_PAYOFF = "partial_payoff"
    MAJOR_PAYOFF = "major_payoff"
    REVERSAL = "reversal"
    AFTERSHOCK = "aftershock"
    RECOVERY = "recovery"
    RELATIONSHIP_SHIFT = "relationship_shift"
    WORLD_EXPANSION = "world_expansion"


class SourceFileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str
    sha256: str
    byte_size: int
    detected_encoding: str
    order_index: int
    order_confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: int = 1
    book_id: str
    source_root: str
    status: Literal["ready", "needs_confirmation"]
    confirmed: bool
    files: list[SourceFileEntry]
    conflicts: list[str] = Field(default_factory=list)
    created_at: str


class ChapterSlice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    raw_heading: str
    chapter_number_text: str | None = None
    title: str
    volume_title: str | None = None
    start_line: int
    end_line: int
    start_char: int
    end_char: int
    text: str


class MetricResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    score: float
    inputs: dict[str, Any]
    evidence: list[dict[str, Any] | str] = Field(default_factory=list)
    threshold_interpretation: str
    recommended_action: str
