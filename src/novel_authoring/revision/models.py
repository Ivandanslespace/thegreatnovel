from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.contracts.draft import DraftStateChange


class RevisionTargetScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_ids: list[str] = Field(default_factory=list)
    chapter_ranges: list[tuple[int, int]] = Field(default_factory=list)
    source_span_ids: list[str] = Field(default_factory=list)
    semantic_queries: list[str] = Field(default_factory=list)
    include_downstream_dependencies: bool = True


class CanonChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    predicate: str
    old_value: Any | None = None
    new_value: Any
    change_type: Literal[
        "ADD",
        "SUPERSEDE",
        "REMOVE",
        "REFRAME",
        "add_or_supersede",
    ] = "REFRAME"
    reason: str
    author_authority: bool | str = True


class EntityChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    old_name: str | None = None
    new_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    change_type: Literal["RENAME", "ALIAS", "RECLASSIFY", "CONFIRM"] = "RENAME"
    reason: str


class RevisionSpec(BaseModel):
    """可审计的改写意图；额外字段一律拒绝，避免 prompt 漂移。"""

    model_config = ConfigDict(extra="forbid")

    campaign_name: str = Field(min_length=1)
    revision_kind: Literal[
        "correction",
        "canon_retcon",
        "character_reframe",
        "relationship_transformation",
        "arc_rewrite",
        "style_rewrite",
    ]
    intent: str = Field(min_length=1)
    target_scope: RevisionTargetScope
    canon_changes: list[CanonChange] = Field(default_factory=list)
    entity_changes: list[EntityChange] = Field(default_factory=list)
    must_preserve: list[str] = Field(default_factory=list)
    must_change: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    propagation_rules: list[str] = Field(default_factory=list)
    style_policy: dict[str, Any] = Field(default_factory=dict)
    completion_policy: dict[str, Any] = Field(default_factory=dict)


class ChangeMapItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_span_id: str
    old_quote: str
    new_quote: str
    change_class: Literal[
        "REQUIRED",
        "PRESERVED",
        "CONTEXT",
        "SUPERSEDED",
        "CANON_CHANGE",
        "RELATIONSHIP_CHANGE",
        "ENTITY_CHANGE",
    ]
    reason: str


class ImpactItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impact_id: str
    chapter_id: str | None = None
    source_span_id: str | None = None
    classification: Literal["MUST_REWRITE", "MUST_REVIEW", "INFORMATIONAL", "EXPLICITLY_WAIVED"]
    severity: Literal["BLOCKING", "HIGH", "MEDIUM", "LOW"]
    matched_terms: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    status: Literal["OPEN", "HANDLED", "WAIVED"] = "OPEN"
    waiver_reason: str | None = None


class ImpactPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_id: str
    campaign_id: str
    book_id: str
    edition_id: str
    base_event_seq: int
    base_projection_hash: str
    source_manifest_sha256: str
    deterministic_scan_completed: bool
    codex_semantic_audit_completed: bool
    complete: bool
    items: list[ImpactItem]
    unresolved_items: list[str] = Field(default_factory=list)
    scan_query: str | None = None
    created_at: str


class ImpactAuditDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impact_id: str
    classification: Literal[
        "MUST_REWRITE",
        "MUST_REVIEW",
        "INFORMATIONAL",
        "EXPLICITLY_WAIVED",
    ]
    status: Literal["OPEN", "HANDLED", "WAIVED"]
    evidence_quotes: list[str] = Field(default_factory=list)
    waiver_reason: str | None = None
    notes: list[str] = Field(default_factory=list)


class ImpactAuditOutput(BaseModel):
    """Codex 语义影响审计文件合同；不能由数据库缺省值代替。"""

    model_config = ConfigDict(extra="forbid")

    task_type: Literal["REVISION_IMPACT_AUDIT"] = "REVISION_IMPACT_AUDIT"
    task_id: str
    campaign_id: str
    edition_id: str
    packet_id: str
    packet_sha256: str
    schema_sha256: str
    source_manifest_sha256: str
    base_event_seq: int
    base_projection_hash: str
    analyzer_versions: dict[str, str] = Field(default_factory=dict)
    decisions: list[ImpactAuditDecision] = Field(min_length=1)
    new_items: list[ImpactItem] = Field(default_factory=list)


class RevisionUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str
    campaign_id: str
    book_id: str
    edition_id: str
    unit_order: int
    base_chapter_ordinal: int
    base_chapter_id: str
    base_source_span_id: str
    base_content_sha256: str
    original_heading: str
    original_content: str
    direct_change_requirements: list[str] = Field(default_factory=list)
    downstream_requirements: list[str] = Field(default_factory=list)
    facts_to_add: list[dict[str, Any]] = Field(default_factory=list)
    facts_to_supersede: list[dict[str, Any]] = Field(default_factory=list)
    relationships_to_update: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_edges_to_update: list[dict[str, Any]] = Field(default_factory=list)
    must_preserve: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    style_constraints: dict[str, Any] = Field(default_factory=dict)
    adult_consent_constraints: dict[str, Any] = Field(default_factory=dict)
    expected_after_state: dict[str, Any] = Field(default_factory=dict)
    dependent_units: list[str] = Field(default_factory=list)
    status: Literal["PLANNED", "DRAFTED", "VALIDATED", "COMMITTED", "REJECTED"] = "PLANNED"


class RevisionDraftOutput(BaseModel):
    """改写草稿的唯一允许输出合同；不等同于普通续写 DraftOutput。"""

    model_config = ConfigDict(extra="forbid")

    task_type: Literal["REVISION_DRAFT"] = "REVISION_DRAFT"
    task_id: str
    campaign_id: str
    unit_id: str
    edition_id: str
    base_chapter_id: str
    base_content_sha256: str
    parent_draft_id: str | None = None
    revision_number: int = Field(default=1, ge=1, le=3)
    packet_sha256: str = ""
    plan_sha256: str = ""
    schema_sha256: str = ""
    replacement_title: str
    replacement_markdown: str = Field(min_length=1)
    change_map: list[ChangeMapItem] = Field(min_length=1)
    state_changes: list[DraftStateChange] = Field(default_factory=list)
    facts_superseded: list[dict[str, Any]] = Field(default_factory=list)
    facts_added: list[dict[str, Any]] = Field(default_factory=list)
    relationships_updated: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_updates: list[dict[str, Any]] = Field(default_factory=list)
    invariant_evidence: dict[str, list[str]] = Field(default_factory=dict)
    required_change_evidence: dict[str, list[str]] = Field(default_factory=dict)
    stale_reference_checks: list[dict[str, Any]] = Field(default_factory=list)
    character_fit_inputs: dict[str, float] = Field(default_factory=dict)
    style_fit_inputs: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    adult_consent: "AdultConsentDeclaration | None" = None  # noqa: UP037


class AdultConsentDeclaration(BaseModel):
    """亲密/成人情节的结构化当前状态声明。"""

    model_config = ConfigDict(extra="forbid")

    characters: list[str] = Field(min_length=1)
    adult_status: dict[str, Literal["ADULT", "MINOR", "UNKNOWN"]]
    consciousness: Literal["CLEAR", "IMPAIRED", "UNCONSCIOUS", "UNKNOWN"]
    coercion_state: Literal["NONE", "PRESENT", "UNKNOWN"]
    ability_or_bloodline_influence: Literal["NONE", "PRESENT", "UNKNOWN"]
    proposal: Literal["PRESENT", "ABSENT", "UNKNOWN"]
    acceptance: Literal["EXPLICIT", "ABSENT", "REFUSED", "UNKNOWN"]
    refusal_possible: bool
    withdrawal_possible: bool
    evidence_quotes: list[str] = Field(min_length=1)


class RevisionValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validator: str
    severity: Literal["BLOCKING", "WARNING", "INFO"]
    passed: bool
    evidence: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


RevisionDraftOutput.model_rebuild()
