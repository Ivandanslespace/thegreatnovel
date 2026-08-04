from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InformationStatus(StrEnum):
    CANON = "CANON"
    AUTHOR_INTENT = "AUTHOR_INTENT"
    APPROVED_OUTLINE = "APPROVED_OUTLINE"
    INFERENCE = "INFERENCE"
    CANDIDATE = "CANDIDATE"
    PROSE_ONLY = "PROSE_ONLY"


class ConstraintLevel(StrEnum):
    HARD = "HARD"
    SOFT = "SOFT"
    SPECULATIVE = "SPECULATIVE"


class HorizonKind(StrEnum):
    CURRENT = "CURRENT"
    NEAR = "NEAR"
    MID = "MID"
    FAR = "FAR"


class StoryAtlasStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INVALIDATED = "INVALIDATED"
    RETIRED = "RETIRED"


class ReadinessStatus(StrEnum):
    READY = "READY"
    READY_WITH_GAPS = "READY_WITH_GAPS"
    BLOCKED = "BLOCKED"


class VisualStatus(StrEnum):
    GENERATED_WITH_DATA = "GENERATED_WITH_DATA"
    EMPTY_SOURCE_GRAPH = "EMPTY_SOURCE_GRAPH"
    FAILED = "FAILED"
    STALE = "STALE"


class AtlasBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AtlasEvidence(AtlasBaseModel):
    source_span_ids: list[str] = Field(default_factory=list)
    chapter_ids: list[str] = Field(default_factory=list)
    canon_fact_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    counter_evidence: list[str] = Field(default_factory=list)

    def has_source(self) -> bool:
        """Only a source span is a primary-source anchor for CANON.

        Chapter/fact/event IDs are useful navigation references, but they can
        point at derived or stale rows and therefore cannot satisfy the Canon
        evidence contract by themselves.
        """
        return bool(self.source_span_ids)


Confidence = float | Literal["UNKNOWN"]


class AtlasNode(AtlasBaseModel):
    node_id: str
    name: str
    node_type: str
    description: str = ""
    information_status: InformationStatus
    constraint_level: ConstraintLevel
    horizon: HorizonKind
    confidence: Confidence = "UNKNOWN"
    evidence: AtlasEvidence = Field(default_factory=AtlasEvidence)
    lifecycle_status: Literal["ACTIVE", "RETIRED", "CONTRADICTED", "UNKNOWN"] = "ACTIVE"
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_information_boundary(self) -> AtlasNode:
        if self.information_status is InformationStatus.CANON and not self.evidence.has_source():
            raise ValueError(f"CANON 节点 {self.node_id} 必须有 source evidence")
        if (
            self.information_status is InformationStatus.CANDIDATE
            and self.constraint_level is ConstraintLevel.HARD
        ):
            raise ValueError(f"CANDIDATE 节点 {self.node_id} 不能声明 HARD 约束")
        if self.confidence != "UNKNOWN" and not 0 <= self.confidence <= 1:
            raise ValueError(f"节点 {self.node_id} 的 confidence 必须在 0—1 之间")
        return self


class AtlasEdge(AtlasBaseModel):
    edge_id: str
    from_id: str
    to_id: str
    relation_type: str
    label: str = ""
    information_status: InformationStatus
    constraint_level: ConstraintLevel
    horizon: HorizonKind
    confidence: Confidence = "UNKNOWN"
    evidence: AtlasEvidence = Field(default_factory=AtlasEvidence)
    lifecycle_status: Literal["ACTIVE", "RETIRED", "CONTRADICTED", "UNKNOWN"] = "ACTIVE"
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_information_boundary(self) -> AtlasEdge:
        if self.information_status is InformationStatus.CANON and not self.evidence.has_source():
            raise ValueError(f"CANON 关系 {self.edge_id} 必须有 source evidence")
        if (
            self.information_status is InformationStatus.CANDIDATE
            and self.constraint_level is ConstraintLevel.HARD
        ):
            raise ValueError(f"CANDIDATE 关系 {self.edge_id} 不能声明 HARD 约束")
        if self.confidence != "UNKNOWN" and not 0 <= self.confidence <= 1:
            raise ValueError(f"关系 {self.edge_id} 的 confidence 必须在 0—1 之间")
        return self


class AtlasGraph(AtlasBaseModel):
    graph_type: str
    atlas_version: int
    nodes: list[AtlasNode] = Field(default_factory=list)
    edges: list[AtlasEdge] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> AtlasGraph:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError(f"{self.graph_type} graph 存在重复 node_id")
        edge_ids = [edge.edge_id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError(f"{self.graph_type} graph 存在重复 edge_id")
        known = set(node_ids)
        missing = sorted(
            {
                item
                for edge in self.edges
                for item in (edge.from_id, edge.to_id)
                if item not in known
            }
        )
        if missing:
            raise ValueError(f"{self.graph_type} graph 的 edge 引用了不存在节点：{missing}")
        creative_requirements = {
            "characters": {"role", "desire", "constraint", "source_of_introduction", "why_now"},
            "factions": {
                "goal",
                "resource_base",
                "internal_tension",
                "source_of_introduction",
                "why_now",
            },
            "abilities": {
                "new_problem_addressed",
                "cost_and_boundary",
                "possible_counterplay",
                "source_of_introduction",
                "why_now",
            },
        }
        required = creative_requirements.get(self.graph_type, set())
        if required:
            for node in self.nodes:
                if node.information_status is InformationStatus.CANON:
                    continue
                missing_fields = sorted(required - set(node.payload))
                if missing_fields:
                    raise ValueError(
                        f"{self.graph_type} creative grammar 缺少字段："
                        f"{node.node_id} -> {missing_fields}"
                    )
        if self.graph_type == "regions":
            forbidden_coordinate_keys = {
                "lat",
                "lon",
                "latitude",
                "longitude",
                "x",
                "y",
            }
            for node in self.nodes:
                if forbidden_coordinate_keys & set(node.payload):
                    raise ValueError("Region graph 只能使用拓扑关系，不得伪造坐标")
        return self


class HorizonItem(AtlasBaseModel):
    item_id: str
    title: str
    summary: str
    horizon: HorizonKind
    information_status: InformationStatus
    constraint_level: ConstraintLevel
    confidence: Confidence = "UNKNOWN"
    chapter_ordinal: int | None = None
    stage_anchor: str | None = None
    must_preserve: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    evidence: AtlasEvidence = Field(default_factory=AtlasEvidence)

    @model_validator(mode="after")
    def far_is_not_chapter_outline(self) -> HorizonItem:
        if self.horizon is HorizonKind.FAR and self.chapter_ordinal is not None:
            raise ValueError(f"FAR item {self.item_id} 不得包含逐章 ordinal")
        if self.information_status is InformationStatus.CANON and not self.evidence.has_source():
            raise ValueError(f"CANON horizon item {self.item_id} 必须有 evidence")
        return self


class HorizonBand(AtlasBaseModel):
    horizon: HorizonKind
    start_chapter: int | None = None
    end_chapter: int | None = None
    items: list[HorizonItem] = Field(default_factory=list)
    stage_anchors: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_band(self) -> HorizonBand:
        if (
            self.start_chapter is not None
            and self.end_chapter is not None
            and self.end_chapter < self.start_chapter
        ):
            raise ValueError(f"{self.horizon} horizon 结束章节不能早于开始章节")
        if any(item.horizon is not self.horizon for item in self.items):
            raise ValueError(f"{self.horizon} horizon 的 item horizon 必须一致")
        if self.horizon is HorizonKind.FAR and any(
            item.chapter_ordinal is not None for item in self.items
        ):
            raise ValueError("FAR horizon 不得包含逐章大纲")
        return self


class Spine(AtlasBaseModel):
    spine_id: str
    title: str
    kind: Literal["ACTIVE", "ALTERNATIVE", "WILDCARD"]
    status: Literal["ACTIVE", "PAUSED", "RETIRED", "CONTRADICTED"] = "ACTIVE"
    structure_signature: str
    summary: str
    information_status: InformationStatus
    constraint_level: ConstraintLevel
    horizon: HorizonKind
    confidence: Confidence = "UNKNOWN"
    anchor_ids: list[str] = Field(default_factory=list)
    open_design_spaces: list[str] = Field(default_factory=list)
    evidence: AtlasEvidence = Field(default_factory=AtlasEvidence)

    @model_validator(mode="after")
    def validate_canon_evidence(self) -> Spine:
        if self.information_status is InformationStatus.CANON and not self.evidence.has_source():
            raise ValueError(f"CANON spine {self.spine_id} 必须有 source evidence")
        if (
            self.information_status is InformationStatus.CANDIDATE
            and self.constraint_level is ConstraintLevel.HARD
        ):
            raise ValueError(f"CANDIDATE spine {self.spine_id} 不能声明 HARD 约束")
        return self


class FuturePossibilitySpace(AtlasBaseModel):
    active_spine: Spine
    alternative_spines: list[Spine] = Field(default_factory=list)
    wildcard_possibilities: list[Spine] = Field(default_factory=list)
    open_design_spaces: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_spine_roles(self) -> FuturePossibilitySpace:
        if self.active_spine.kind != "ACTIVE":
            raise ValueError("active_spine.kind 必须为 ACTIVE")
        if len({item.spine_id for item in self.alternative_spines}) != len(self.alternative_spines):
            raise ValueError("Alternative Spine 的 spine_id 必须稳定且唯一")
        if len({item.structure_signature for item in self.alternative_spines}) != len(
            self.alternative_spines
        ):
            raise ValueError("Alternative Spines 必须保留结构差异，不能全部是同一路线")
        if any(item.kind != "ALTERNATIVE" for item in self.alternative_spines):
            raise ValueError("alternative_spines 内的 kind 必须为 ALTERNATIVE")
        if any(item.kind != "WILDCARD" for item in self.wildcard_possibilities):
            raise ValueError("wildcard_possibilities 内的 kind 必须为 WILDCARD")
        return self


class RollingHorizon(AtlasBaseModel):
    horizon_id: str
    horizon_hash: str
    atlas_id: str
    atlas_version: int = Field(ge=1)
    atlas_content_hash: str
    base_projection_hash: str
    current_chapter_ordinal: int = Field(ge=0)
    current: HorizonBand
    near: HorizonBand
    mid: HorizonBand
    far: HorizonBand
    required_far_end_chapter: int

    @model_validator(mode="after")
    def validate_band_roles(self) -> RollingHorizon:
        if self.current.horizon is not HorizonKind.CURRENT:
            raise ValueError("current horizon 标签错误")
        if self.near.horizon is not HorizonKind.NEAR:
            raise ValueError("near horizon 标签错误")
        if self.mid.horizon is not HorizonKind.MID:
            raise ValueError("mid horizon 标签错误")
        if self.far.horizon is not HorizonKind.FAR:
            raise ValueError("far horizon 标签错误")
        if (
            self.far.end_chapter is not None
            and self.far.end_chapter < self.required_far_end_chapter
        ):
            raise ValueError("FAR horizon 未达到要求的覆盖终点")
        if self.far.end_chapter is not None and self.far.end_chapter < self.current_chapter_ordinal:
            raise ValueError("FAR horizon 不能早于当前章节")
        return self


class CreativeLineage(AtlasBaseModel):
    derived_from_existing_rules: list[str] = Field(default_factory=list)
    new_problem_addressed: str
    novelty_dimension: str
    cost_and_boundary: str
    relationship_to_current_atlas: str
    strategy_space_change: str
    future_value: str
    possible_counterplay: str
    source_of_introduction: str
    why_now: str
    canon_status: InformationStatus


class WorldModelReadiness(AtlasBaseModel):
    status: ReadinessStatus
    current_boundary_confirmed: bool
    core_rules_covered: bool
    protagonist_state_confirmed: bool
    main_threads_connected: bool
    source_coverage: float
    graph_coverage: float
    blocking_reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    review_queue: list[str] = Field(default_factory=list)


class AtlasArtifactManifest(AtlasBaseModel):
    schema_version: Literal["story-atlas-v1"] = "story-atlas-v1"
    atlas_id: str
    atlas_version: int = Field(ge=1)
    book_id: str
    edition_id: str
    parent_atlas_id: str | None = None
    base_event_seq: int = Field(ge=0)
    base_projection_hash: str
    source_manifest_sha256: str
    effective_content_sha256: str = ""
    registry_hash: str = ""
    config_hash: str = ""
    analyzer_versions_hash: str = ""
    atlas_content_hash: str = ""
    horizon_id: str | None = None
    horizon_hash: str = ""
    created_at: str
    status: StoryAtlasStatus = StoryAtlasStatus.ACTIVE
    readiness: WorldModelReadiness
    current_chapter_ordinal: int = Field(ge=0)
    batch_target_chapters: int = Field(default=0, ge=0)
    far_horizon_end_chapter: int = Field(ge=0)
    artifact_paths: list[str] = Field(default_factory=list)
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    graph_counts: dict[str, int] = Field(default_factory=dict)
    source_coverage: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_manifest(self) -> AtlasArtifactManifest:
        required_far_end = max(
            self.current_chapter_ordinal * 2,
            self.batch_target_chapters * 2,
        )
        if self.far_horizon_end_chapter < required_far_end:
            raise ValueError("far_horizon_end_chapter 不能早于 current_chapter_ordinal")
        if set(self.artifact_paths) != set(self.artifact_hashes):
            raise ValueError("artifact_paths 与 artifact_hashes 必须一一对应")
        if self.readiness.status is ReadinessStatus.BLOCKED and not self.readiness.blocking_reasons:
            raise ValueError("BLOCKED Atlas 必须记录 blocking_reasons")
        return self


class AtlasValidationResult(AtlasBaseModel):
    manifest: AtlasArtifactManifest
    readiness: WorldModelReadiness
    graph_views: dict[str, AtlasGraph] = Field(default_factory=dict)
    future_space: FuturePossibilitySpace | None = None
    rolling_horizon: RollingHorizon | None = None
    files_checked: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class AtlasAction(AtlasBaseModel):
    action_type: Literal[
        "ACCEPT_SOFT_ANCHOR",
        "REJECT_FUTURE_CANDIDATE",
        "RETIRE_ROUTE",
        "SET_ACTIVE_SPINE",
        "ADD_AUTHOR_INTENT",
        "ADD_REVIEW_QUEUE",
        "ACCEPT_ATLAS",
    ]
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = "AUTHOR"
