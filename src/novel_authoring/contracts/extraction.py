from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    local_id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    information_state: Literal["INFERENCE", "PROSE_ONLY"] = "INFERENCE"
    confidence: float = Field(ge=0, le=1)
    source_span_ids: list[str] = Field(min_length=1)
    evidence_quote: str = Field(min_length=1, max_length=240)


class EntityExtraction(ExtractionBase):
    kind: Literal["entity"]
    entity_type: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class FactExtraction(ExtractionBase):
    kind: Literal["fact"]
    statement: str
    subject_ref: str | None = None
    predicate: str
    object_value: Any


class EventExtraction(ExtractionBase):
    kind: Literal["event"]
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)


class TimelineExtraction(ExtractionBase):
    kind: Literal["timeline"]
    label: str
    story_time_start: str | None = None
    story_time_end: str | None = None
    order_key: float | None = None


class CharacterStateExtraction(ExtractionBase):
    kind: Literal["character_state"]
    character_ref: str
    goals: list[str] = Field(default_factory=list)
    knowledge: list[str] = Field(default_factory=list)
    resources: dict[str, Any] = Field(default_factory=dict)
    relationships: dict[str, Any] = Field(default_factory=dict)
    emotion: dict[str, Any] = Field(default_factory=dict)
    plans: list[str] = Field(default_factory=list)


class KnowledgeExtraction(ExtractionBase):
    kind: Literal["knowledge"]
    character_ref: str
    fact_ref: str
    knowledge_state: str


class RelationshipExtraction(ExtractionBase):
    kind: Literal["relationship"]
    from_entity_ref: str
    to_entity_ref: str
    values: dict[str, float | str | bool | None] = Field(default_factory=dict)


class ResourceExtraction(ExtractionBase):
    kind: Literal["resource"]
    owner_ref: str
    name: str
    quantity: float | None = None
    unit: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CapabilityExtraction(ExtractionBase):
    kind: Literal["capability"]
    owner_ref: str
    name: str
    absolute_capacity: float | None = None
    effective_capacity: float | None = None
    relative_standing: float | None = None
    limits: dict[str, Any] = Field(default_factory=dict)


class ThreadExtraction(ExtractionBase):
    kind: Literal["thread"]
    goal: str
    stakes: str
    phase: str
    importance: float = Field(ge=0, le=1)
    reader_visibility: float = Field(ge=0, le=1)
    progress: float = Field(ge=0, le=1)
    dependencies: list[str] = Field(default_factory=list)


class PromiseExtraction(ExtractionBase):
    kind: Literal["promise"]
    statement: str
    thread_ref: str | None = None
    importance: float = Field(ge=0, le=1)
    reader_visibility: float = Field(ge=0, le=1)
    progress: float = Field(ge=0, le=1)
    target_max_age: int = Field(gt=0)


class StyleExtraction(ExtractionBase):
    kind: Literal["style"]
    pov: str | None = None
    tense: str | None = None
    dialogue_ratio: float | None = Field(default=None, ge=0, le=1)
    exposition_density: str | None = None
    emotional_distance: str | None = None
    sample: str


class RepetitionExtraction(ExtractionBase):
    kind: Literal["repetition"]
    event_source: str
    solution_method: str
    payoff_type: str
    scene_topology: str
    emotional_outcome: str
    ending_type: str | None = None


ExtractionRecord = Annotated[
    EntityExtraction
    | FactExtraction
    | EventExtraction
    | TimelineExtraction
    | CharacterStateExtraction
    | KnowledgeExtraction
    | RelationshipExtraction
    | ResourceExtraction
    | CapabilityExtraction
    | ThreadExtraction
    | PromiseExtraction
    | StyleExtraction
    | RepetitionExtraction,
    Field(discriminator="kind"),
]


class ExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    records: list[ExtractionRecord]
    notes: list[str] = Field(default_factory=list)
