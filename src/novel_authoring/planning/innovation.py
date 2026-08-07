"""Author-controlled creative-distance contracts.

Innovation is a planning preference, not a continuity exception.  This module
keeps the preference, the author-facing preview, and the post-generation trace
as separate contracts so a requested level can never be mistaken for what a
candidate or a draft actually realized.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.operations import book_root
from novel_authoring.storage.registry import BookRegistry
from novel_authoring.utils import json_dumps, sha256_bytes


class InnovationLevel(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BOLD = "bold"


class InnovationFocus(StrEnum):
    AUTO = "auto"
    PLOT = "plot"
    CHARACTER = "character"
    RELATIONSHIP = "relationship"
    WORLD = "world"
    MECHANISM = "mechanism"
    NARRATIVE_STRUCTURE = "narrative_structure"
    STYLE = "style"


class IntegrationCost(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NoveltyQuality(StrEnum):
    MEANINGFUL_NOVELTY = "MEANINGFUL_NOVELTY"
    COSMETIC_NOVELTY = "COSMETIC_NOVELTY"


class AlignmentJudgment(StrEnum):
    STRONG_ALIGNMENT = "STRONG_ALIGNMENT"
    PARTIAL_ALIGNMENT = "PARTIAL_ALIGNMENT"
    WEAK_ALIGNMENT = "WEAK_ALIGNMENT"
    NO_ALIGNMENT = "NO_ALIGNMENT"


class PatternDistance(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InnovationControl(BaseModel):
    """Creative distance allowed inside an already legal workflow.

    ``AUTO`` is a recommendation mode.  It is deliberately mutually
    exclusive with explicit directions so an operation cannot silently mix a
    user-selected direction with an automatic one.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    level: InnovationLevel = InnovationLevel.MEDIUM
    focus: list[InnovationFocus] = Field(
        default_factory=lambda: [InnovationFocus.AUTO], min_length=1
    )

    @model_validator(mode="after")
    def validate_focus(self) -> InnovationControl:
        if len(set(self.focus)) != len(self.focus):
            raise ValueError("InnovationFocus 不得重复")
        has_auto = InnovationFocus.AUTO in self.focus
        if has_auto and len(self.focus) != 1:
            raise ValueError("AUTO 与显式 InnovationFocus 互斥")
        return self

    @property
    def uses_auto_focus(self) -> bool:
        return self.focus == [InnovationFocus.AUTO]

    @property
    def creative_distance_guidance(self) -> str:
        return {
            InnovationLevel.MINIMAL: (
                "最大程度沿当前轨道继续；优先 active thread、已有关系、Earned Capability、"
                "当前资源和成熟 Setup/Payoff，但仍允许有因果来源的局部 Forward Novelty。"
            ),
            InnovationLevel.LOW: (
                "允许小型新事件、人物、信息、能力组合或关系变化；整体应明显依附现有剧情轨道。"
            ),
            InnovationLevel.MEDIUM: (
                "在 Fidelity 与 Creativity 之间平衡；三个 Lens 都应有真实发挥空间，"
                "新人物、关系、地点、威胁、交易、世界信息或规则表现必须由当前因果引入。"
            ),
            InnovationLevel.HIGH: (
                "主动扩大 Future Possibility Space，积极考虑新人物、群体、地点、规则表现、"
                "资源循环、目标、Plot Route 和关系冲突，但不得降低任何事实 hard gate。"
            ),
            InnovationLevel.BOLD: (
                "允许显著偏离最显然的下一步，探索 major thread、世界扩张、社会结构、"
                "关系变化、预期反转或新的 scene topology；不得 retroactive invention、"
                "凭空获得能力或 Deus Ex Machina；所有 hard gates 保持不变。"
            ),
        }[self.level]

    @property
    def lens_tendency_guidance(self) -> str:
        return {
            InnovationLevel.MINIMAL: (
                "CONTINUITY_ACTIVE_THREAD >>> EARNED_OPPORTUNITY > "
                "FORWARD_EXPANSION"
            ),
            InnovationLevel.LOW: (
                "CONTINUITY_ACTIVE_THREAD > EARNED_OPPORTUNITY > "
                "FORWARD_EXPANSION"
            ),
            InnovationLevel.MEDIUM: (
                "CONTINUITY_ACTIVE_THREAD ≈ EARNED_OPPORTUNITY ≈ "
                "FORWARD_EXPANSION"
            ),
            InnovationLevel.HIGH: (
                "EARNED_OPPORTUNITY ≈ FORWARD_EXPANSION > "
                "CONTINUITY_ACTIVE_THREAD"
            ),
            InnovationLevel.BOLD: (
                "允许 Forward/Wildcard 显著扩大 Future Space；三个 Lens 仍全部保留"
            ),
        }[self.level]


class InnovationRecommendation(BaseModel):
    """Evidence-backed suggestion for ``AUTO``; never an implicit override."""

    model_config = ConfigDict(extra="forbid")

    recommended_focus: list[InnovationFocus] = Field(min_length=1)
    reason: list[str] = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    pattern_distance: PatternDistance = PatternDistance.MEDIUM

    @model_validator(mode="after")
    def validate_recommendation(self) -> InnovationRecommendation:
        if InnovationFocus.AUTO in self.recommended_focus:
            raise ValueError("recommendation 必须是显式方向，不得返回 AUTO")
        if len(set(self.recommended_focus)) != len(self.recommended_focus):
            raise ValueError("recommended_focus 不得重复")
        return self


class CandidateInnovationPreview(BaseModel):
    """作者可读的候选创新预览，不是评分，也不是实际结果。"""

    model_config = ConfigDict(extra="forbid")

    creative_distance: InnovationLevel
    primary_directions: list[InnovationFocus] = Field(min_length=1)
    new_future_branches: list[str] = Field(default_factory=list)
    major_branch_count: int = Field(default=0, ge=0)
    local_branch_count: int = Field(default=0, ge=0)
    main_innovations: list[str] = Field(min_length=1)
    future_options_opened: list[str] = Field(default_factory=list)
    integration_cost: IntegrationCost = IntegrationCost.LOW
    novelty_quality: NoveltyQuality = NoveltyQuality.MEANINGFUL_NOVELTY
    uses_earned_assets: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_directions(self) -> CandidateInnovationPreview:
        if InnovationFocus.AUTO in self.primary_directions and len(self.primary_directions) > 1:
            raise ValueError("Candidate Preview 的显式方向不得与 AUTO 混用")
        if len(set(self.primary_directions)) != len(self.primary_directions):
            raise ValueError("Candidate Preview 方向不得重复")
        return self


class InnovationTrace(BaseModel):
    """What the candidate/draft actually realized after generation."""

    model_config = ConfigDict(extra="forbid")

    requested_level: InnovationLevel
    requested_focus: list[InnovationFocus] = Field(min_length=1)
    realized_directions: list[InnovationFocus] = Field(default_factory=list)
    realized_level: InnovationLevel | None = None
    forward_novelties: list[str] = Field(default_factory=list)
    earned_recombinations: list[str] = Field(default_factory=list)
    new_entities: list[str] = Field(default_factory=list)
    new_relationship_states: list[str] = Field(default_factory=list)
    new_world_elements: list[str] = Field(default_factory=list)
    new_mechanisms: list[str] = Field(default_factory=list)
    meaningful_state_changes: list[str] = Field(default_factory=list)
    future_options_opened: list[str] = Field(default_factory=list)
    future_options_closed: list[str] = Field(default_factory=list)
    novelty_quality: list[NoveltyQuality] = Field(default_factory=list)
    integration_cost: IntegrationCost = IntegrationCost.LOW
    recent_pattern_distance: PatternDistance = PatternDistance.MEDIUM

    @model_validator(mode="after")
    def validate_trace_focus(self) -> InnovationTrace:
        if InnovationFocus.AUTO in self.requested_focus and len(self.requested_focus) > 1:
            raise ValueError("InnovationTrace requested_focus 不得混用 AUTO")
        if len(set(self.requested_focus)) != len(self.requested_focus):
            raise ValueError("InnovationTrace requested_focus 不得重复")
        return self


class InnovationDirectionAlignment(BaseModel):
    """Judgement of requested direction versus realized direction."""

    model_config = ConfigDict(extra="forbid")

    requested_focus: list[InnovationFocus] = Field(min_length=1)
    realized_directions: list[InnovationFocus] = Field(default_factory=list)
    judgment: AlignmentJudgment
    reason: list[str] = Field(min_length=1)


class InnovationDiagnostics(BaseModel):
    """Soft rolling-window signals; never a Validator gate."""

    model_config = ConfigDict(extra="forbid")

    window_chapters: list[int] = Field(default_factory=list)
    recent_pattern_distance: PatternDistance = PatternDistance.MEDIUM
    repeated_patterns: list[str] = Field(default_factory=list)
    open_novelty_debt: list[str] = Field(default_factory=list)
    recommendation: InnovationRecommendation | None = None


class ExperimentContextFingerprint(BaseModel):
    """Normalized semantic input comparison for a level experiment."""

    model_config = ConfigDict(extra="forbid")

    visible_source: str
    distill_soft_context: str
    runtime_state: str
    earned_surface: str
    author_directives: str
    recent_chapter_window: str
    context_fingerprint: str
    excluded_fields: list[str] = Field(default_factory=list)
    normalized_diff: list[str] = Field(default_factory=list)


def default_innovation_control() -> InnovationControl:
    return InnovationControl()


def _book_yaml(database: Any, book_id: str) -> tuple[Path, dict[str, Any]] | None:
    root = book_root(database, book_id)
    if not (root / "book.yaml").is_file():
        return None
    layout = BookLayout(root.parent)
    registry = BookRegistry(layout)
    return root / "book.yaml", registry.read(book_id)


def load_book_innovation_control(database: Any, book_id: str) -> InnovationControl:
    """Read the per-book default; legacy workspaces use MEDIUM+AUTO."""

    loaded = _book_yaml(database, book_id)
    if loaded is None:
        return default_innovation_control()
    _path, values = loaded
    raw = values.get("innovation") or {}
    if not isinstance(raw, Mapping):
        raise ValueError("book.yaml 的 innovation 必须是 mapping")
    try:
        return InnovationControl.model_validate(dict(raw))
    except ValueError as exc:
        raise ValueError("book.yaml 的 innovation 默认值无效") from exc


def save_book_innovation_control(
    database: Any, book_id: str, control: InnovationControl
) -> Path | None:
    loaded = _book_yaml(database, book_id)
    if loaded is None:
        return None
    path, values = loaded
    values = dict(values)
    values["innovation"] = control.model_dump(mode="json")
    registry = BookRegistry(BookLayout(path.parent.parent))
    registry.write(BookLayout(path.parent.parent).for_book(book_id), values)
    registry.write_readme(BookLayout(path.parent.parent).for_book(book_id), values)
    return path


def resolve_innovation_control(
    database: Any,
    book_id: str,
    *,
    level: InnovationLevel | str | None = None,
    focus: Sequence[InnovationFocus | str] | None = None,
    save_as_book_default: bool = False,
) -> tuple[InnovationControl, str]:
    """Resolve book default plus one-operation overrides.

    The returned source is ``book_default`` or ``operation_override`` and is
    persisted in task metadata for audit.  An override never mutates the book
    unless ``save_as_book_default`` is explicitly true.
    """

    book_default = load_book_innovation_control(database, book_id)
    has_override = level is not None or focus is not None
    selected_level = book_default.level if level is None else InnovationLevel(str(level))
    selected_focus = (
        book_default.focus
        if focus is None
        else [
            item if isinstance(item, InnovationFocus) else InnovationFocus(str(item))
            for item in focus
        ]
    )
    control = InnovationControl(level=selected_level, focus=selected_focus)
    if save_as_book_default:
        if not has_override:
            raise ValueError("只有显式 operation override 才能保存为本书默认")
        if save_book_innovation_control(database, book_id, control) is None:
            raise ValueError("legacy workspace 没有 book.yaml，不能保存本书默认")
    return control, "operation_override" if has_override else "book_default"


def parse_focus_option(value: str | None) -> list[InnovationFocus] | None:
    if value is None:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    if not items:
        raise ValueError("--innovation-focus 不能为空")
    return [InnovationFocus(item) for item in items]


def _pattern_distance(recent_structures: Sequence[Mapping[str, object]]) -> PatternDistance:
    if not recent_structures:
        return PatternDistance.MEDIUM
    signatures = {
        json_dumps(
            {
                key: item.get(key)
                for key in ("primary_function", "scene_topology", "ending_mode", "structure_tag")
                if item.get(key) is not None
            }
        )
        for item in recent_structures
    }
    ratio = len(signatures) / max(len(recent_structures), 1)
    if ratio < 0.4:
        return PatternDistance.LOW
    if ratio < 0.75:
        return PatternDistance.MEDIUM
    return PatternDistance.HIGH


def recommend_innovation_focus(
    *,
    active_threads: Sequence[Mapping[str, object]] = (),
    relationships: Mapping[str, object] | None = None,
    capabilities: Mapping[str, object] | None = None,
    recent_structures: Sequence[Mapping[str, object]] = (),
    open_setups: Sequence[object] = (),
    available_payoffs: Sequence[object] = (),
) -> InnovationRecommendation:
    """Produce a transparent AUTO recommendation from current soft inputs."""

    pattern = _pattern_distance(recent_structures)
    scores: dict[InnovationFocus, int] = {
        InnovationFocus.PLOT: len(active_threads) + len(open_setups) + len(available_payoffs),
        InnovationFocus.RELATIONSHIP: 2 if relationships else 1,
        InnovationFocus.WORLD: 2 if not relationships else 1,
        InnovationFocus.MECHANISM: 2 if capabilities else 1,
        InnovationFocus.CHARACTER: max(len(active_threads), 1),
        InnovationFocus.NARRATIVE_STRUCTURE: 3 if pattern is PatternDistance.LOW else 1,
        InnovationFocus.STYLE: 0,
    }
    ranked = sorted(scores, key=lambda item: (-scores[item], item.value))
    selected = [item for item in ranked if scores[item] > 0][:2]
    if not selected:
        selected = [InnovationFocus.PLOT]
    reasons = [
        f"最近窗口结构差异为 {pattern.value}，仅作为软规划信号",
        f"当前存在 {len(active_threads)} 个活跃线程、{len(open_setups)} 个开放设置",
    ]
    evidence = [
        "active_threads",
        "recent_structures",
        "earned_surface.available_payoffs",
    ]
    return InnovationRecommendation(
        recommended_focus=selected,
        reason=reasons,
        evidence=evidence,
        pattern_distance=pattern,
    )


def _without_experiment_identity(value: object, path: str = "") -> object:
    if isinstance(value, Mapping):
        ignored = {
            "book_id",
            "operation_id",
            "handoff_id",
            "task_id",
            "run_id",
            "run_label",
            "variant",
            "benchmark_variant",
            "stage",
            "target_chapter",
            "schema_version",
            "schema",
            "input",
            "expected_output",
            "task_directory",
            "task_created_at",
            "created_at",
            "frozen_at",
            "timestamp",
            "innovation_control",
            "distill_id",
            "baseline_id",
            "state_id",
            "surface_id",
            "packet_id",
            "contract_id",
            "candidate_id",
            "entry_id",
            "chapter_id",
            "segment_id",
            "source_span_ids",
        }
        return {
            str(key): _without_experiment_identity(item, f"{path}.{key}")
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in ignored
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_without_experiment_identity(item, path) for item in value]
    return value


def build_experiment_context_fingerprint(
    *,
    visible_source: object,
    distill_soft_context: object,
    runtime_state: object,
    earned_surface: object,
    author_directives: object,
    recent_chapter_window: object,
) -> ExperimentContextFingerprint:
    parts = {
        "visible_source": _without_experiment_identity(visible_source),
        "distill_soft_context": _without_experiment_identity(distill_soft_context),
        "runtime_state": _without_experiment_identity(runtime_state),
        "earned_surface": _without_experiment_identity(earned_surface),
        "author_directives": _without_experiment_identity(author_directives),
        "recent_chapter_window": _without_experiment_identity(recent_chapter_window),
    }
    digests = {
        key: sha256_bytes(json_dumps(value).encode("utf-8")) for key, value in parts.items()
    }
    combined = sha256_bytes(json_dumps(parts).encode("utf-8"))
    return ExperimentContextFingerprint(
        visible_source=digests["visible_source"],
        distill_soft_context=digests["distill_soft_context"],
        runtime_state=digests["runtime_state"],
        earned_surface=digests["earned_surface"],
        author_directives=digests["author_directives"],
        recent_chapter_window=digests["recent_chapter_window"],
        context_fingerprint=combined,
        excluded_fields=[
            "book_id",
            "operation_id",
            "handoff_id",
            "task_id",
            "run_id",
            "run_label",
            "variant",
            "benchmark_variant",
            "stage",
            "target_chapter",
            "schema_version",
            "schema",
            "input",
            "expected_output",
            "task_directory",
            "task_created_at",
            "created_at",
            "innovation_control",
            "distill_id",
            "baseline_id",
            "state_id",
            "surface_id",
            "packet_id",
            "contract_id",
            "candidate_id",
            "entry_id",
            "chapter_id",
            "segment_id",
            "source_span_ids",
        ],
    )


def compare_experiment_contexts(
    left: Mapping[str, object], right: Mapping[str, object]
) -> list[str]:
    """Return normalized input paths that differ, excluding identity fields."""

    normalized_left = _without_experiment_identity(left)
    normalized_right = _without_experiment_identity(right)
    differences: list[str] = []

    def walk(first: object, second: object, path: str) -> None:
        if type(first) is not type(second):
            differences.append(path or "$")
            return
        if isinstance(first, Mapping) and isinstance(second, Mapping):
            keys = sorted(set(first) | set(second), key=str)
            for key in keys:
                if key not in first or key not in second:
                    differences.append(f"{path}.{key}" if path else str(key))
                else:
                    walk(first[key], second[key], f"{path}.{key}" if path else str(key))
            return
        if isinstance(first, list) and isinstance(second, list):
            if len(first) != len(second):
                differences.append(path or "$")
                return
            for index, (left_item, right_item) in enumerate(zip(first, second, strict=True)):
                walk(left_item, right_item, f"{path}[{index}]")
            return
        if first != second:
            differences.append(path or "$")

    walk(normalized_left, normalized_right, "")
    return differences


def assess_innovation_alignment(
    requested_focus: Sequence[InnovationFocus],
    realized_directions: Sequence[InnovationFocus],
) -> InnovationDirectionAlignment:
    requested = list(requested_focus)
    realized = list(realized_directions)
    if not realized:
        judgment = AlignmentJudgment.NO_ALIGNMENT
        reason = ["没有记录到 realized innovation direction"]
    elif InnovationFocus.AUTO in requested:
        judgment = AlignmentJudgment.STRONG_ALIGNMENT
        reason = ["AUTO 允许根据当前书本证据选择实际方向；已记录 realized direction"]
    else:
        overlap = set(requested).intersection(realized)
        if overlap == set(requested):
            judgment = AlignmentJudgment.STRONG_ALIGNMENT
            reason = ["所有请求方向都在 realized direction 中出现"]
        elif overlap:
            judgment = AlignmentJudgment.PARTIAL_ALIGNMENT
            reason = [f"部分请求方向实现：{', '.join(sorted(item.value for item in overlap))}"]
        else:
            judgment = AlignmentJudgment.WEAK_ALIGNMENT
            reason = [
                "创新发生了，但主要方向不在作者请求范围内："
                + ", ".join(sorted(item.value for item in realized))
            ]
    return InnovationDirectionAlignment(
        requested_focus=requested,
        realized_directions=realized,
        judgment=judgment,
        reason=reason,
    )


def classify_novelty(
    *,
    meaningful_state_changes: Sequence[str] = (),
    future_options_opened: Sequence[str] = (),
    new_relationship_states: Sequence[str] = (),
    new_world_elements: Sequence[str] = (),
    new_mechanisms: Sequence[str] = (),
) -> NoveltyQuality:
    """Separate state-changing novelty from cosmetic renaming."""

    if any(
        (
            meaningful_state_changes,
            future_options_opened,
            new_relationship_states,
            new_world_elements,
            new_mechanisms,
        )
    ):
        return NoveltyQuality.MEANINGFUL_NOVELTY
    return NoveltyQuality.COSMETIC_NOVELTY


def estimate_integration_cost(
    *,
    new_entities: Sequence[str] = (),
    new_relationship_states: Sequence[str] = (),
    new_world_elements: Sequence[str] = (),
    new_mechanisms: Sequence[str] = (),
    future_options_opened: Sequence[str] = (),
) -> IntegrationCost:
    obligations = sum(
        len(items)
        for items in (
            new_entities,
            new_relationship_states,
            new_world_elements,
            new_mechanisms,
            future_options_opened,
        )
    )
    if obligations >= 5:
        return IntegrationCost.HIGH
    if obligations >= 2:
        return IntegrationCost.MEDIUM
    return IntegrationCost.LOW


__all__ = [
    "AlignmentJudgment",
    "CandidateInnovationPreview",
    "ExperimentContextFingerprint",
    "InnovationControl",
    "InnovationDiagnostics",
    "InnovationDirectionAlignment",
    "InnovationFocus",
    "InnovationLevel",
    "InnovationRecommendation",
    "InnovationTrace",
    "IntegrationCost",
    "NoveltyQuality",
    "PatternDistance",
    "build_experiment_context_fingerprint",
    "assess_innovation_alignment",
    "classify_novelty",
    "compare_experiment_contexts",
    "default_innovation_control",
    "estimate_integration_cost",
    "load_book_innovation_control",
    "parse_focus_option",
    "recommend_innovation_focus",
    "resolve_innovation_control",
    "save_book_innovation_control",
]
