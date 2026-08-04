from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.domain.models import ContinuationMode, NarrativeFunction
from novel_authoring.metrics.gates import HardGateInput


class BoundaryChapter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str
    ordinal: int
    heading: str
    content: str
    source_span_id: str


class EarlierSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str
    ordinal: int
    heading: str
    summary: str


class ContinuationBoundaryPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_id: str
    book_id: str
    edition_id: str = "base"
    base_event_seq: int
    base_projection_hash: str
    current_position: dict[str, Any]
    recent_full_chapters: list[BoundaryChapter]
    earlier_summaries: list[EarlierSummary]
    relevant_source_spans: list[dict[str, Any]] = Field(default_factory=list)
    canon_facts: dict[str, dict[str, Any]]
    character_states: dict[str, dict[str, Any]]
    knowledge_boundaries: dict[str, dict[str, Any]]
    active_threads: list[dict[str, Any]]
    promises: dict[str, dict[str, Any]]
    resources: dict[str, dict[str, Any]]
    capabilities: dict[str, dict[str, Any]]
    relationships: dict[str, dict[str, Any]]
    recent_payoffs: dict[str, dict[str, Any]]
    recent_structures: list[dict[str, Any]]
    style_profiles: list[dict[str, Any]]
    author_directives: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)


class CandidateScoreInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_need_fit: float = Field(ge=0, le=100)
    pressure_curve_fit: float = Field(ge=0, le=100)
    debt_utility: float = Field(ge=0, le=100)
    progress_gain: float = Field(ge=0, le=100)
    payoff_or_setup_utility: float = Field(ge=0, le=100)
    agency_gain: float = Field(ge=0, le=100)
    risk_fit: float = Field(ge=0, le=100)
    structural_diversity: float = Field(ge=0, le=100)
    style_fit: float = Field(ge=0, le=100)
    repetition_fatigue: float = Field(ge=0, le=100)
    future_damage: float = Field(ge=0, le=100)


class CandidateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    title: str
    summary: str
    primary_thread_id: str
    primary_function: NarrativeFunction
    secondary_functions: list[NarrativeFunction] = Field(default_factory=list, max_length=2)
    reader_question: str
    event_source: str
    solution_method: str
    protagonist_strategy: str
    risk_form: str
    opportunity_cost: str
    emotional_outcome: str
    social_feedback: str
    scene_topology: str
    ending_state: str
    state_changes: list[str] = Field(min_length=1)
    causal_sources: list[str] = Field(min_length=1)
    promises_to_advance: list[str] = Field(default_factory=list)
    promises_to_pay: list[str] = Field(default_factory=list)
    required_irreversible_change: str
    required_cost: str
    must_not_resolve: list[str] = Field(default_factory=list)
    canon_constraints: list[str] = Field(default_factory=list)
    knowledge_constraints: list[str] = Field(default_factory=list)
    forbidden_repetitions: list[str] = Field(default_factory=list)
    style_constraints: dict[str, str] = Field(default_factory=dict)
    commit_updates: list[str] = Field(min_length=1)
    pressure_before: float = Field(ge=0, le=100)
    pressure_target_after: float = Field(ge=0, le=100)
    score_inputs: CandidateScoreInputs
    score_evidence: dict[str, list[str]]
    gate_input: HardGateInput


class CandidateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    candidates: list[CandidateProposal] = Field(min_length=3, max_length=3)
    notes: list[str] = Field(default_factory=list)


class ThreadPriority(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str
    goal: str
    score: float
    inputs: dict[str, float]
    evidence: list[str]


class ChapterContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: str
    chapter: int
    mode: ContinuationMode
    boundary_packet_id: str
    continuation_boundary: dict[str, Any]
    candidate_id: str
    primary_thread: str
    primary_function: NarrativeFunction
    secondary_functions: list[NarrativeFunction] = Field(max_length=2)
    reader_question: str
    pressure: dict[str, float]
    payoff_plan: dict[str, Any]
    narrative_debt: dict[str, list[str] | int]
    progress: dict[str, str | float]
    required_irreversible_change: str
    required_cost: str
    canon_constraints: list[str]
    knowledge_constraints: list[str]
    must_not_resolve: list[str]
    forbidden_repetitions: list[str]
    style_constraints: dict[str, str]
    ending_state: str
    commit_updates: list[str] = Field(min_length=1)
