from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.planning.innovation import (
    InnovationControl,
    InnovationDirectionAlignment,
    InnovationTrace,
)

StateChangeKind = Literal[
    "fact",
    "timeline",
    "character_state",
    "knowledge",
    "relationship",
    "resource",
    "capability",
    "thread",
    "promise",
    "payoff",
    "repetition",
    "style",
]


class DraftStateChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: StateChangeKind
    record_id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    payload: dict[str, Any]
    evidence_quotes: list[str] = Field(min_length=1)


class KnowledgeClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str
    fact_id: str
    basis: Literal["already_known", "learned_in_draft"]


class DraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    contract_id: str
    chapter_title: str
    prose_markdown: str = Field(min_length=1)
    state_changes: list[DraftStateChange] = Field(min_length=1)
    contract_evidence: dict[str, list[str]]
    knowledge_claims: list[KnowledgeClaim] = Field(default_factory=list)
    character_fit_inputs: dict[str, float]
    style_fit_inputs: dict[str, float]
    character_bottom_line_violations: list[str] = Field(default_factory=list)
    style_boundary_violations: list[str] = Field(default_factory=list)
    promises_advanced: list[str] = Field(default_factory=list)
    promises_paid: list[str] = Field(default_factory=list)
    new_major_hooks: int = Field(default=0, ge=0)
    structure_tags: list[str] = Field(default_factory=list)
    innovation_control: InnovationControl | None = None
    innovation_trace: InnovationTrace | None = None
    direction_alignment: InnovationDirectionAlignment | None = None
    notes: list[str] = Field(default_factory=list)
