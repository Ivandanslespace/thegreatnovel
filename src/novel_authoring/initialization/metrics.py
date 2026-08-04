# ruff: noqa: E501

"""Strict, local Semantic Metric Bootstrap for an existing novel.

The bootstrap is deliberately file-first: a prepared JSONL package is frozen
against the current edition, then validated before any observation is appended
to SQLite.  The local analyzer is a provisional lexical baseline.  It is
evidence-bearing and replaceable by a Codex semantic pass; it is never Canon.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.initialization.service import (
    InitializationError,
    SourceCoverage,
    arc_output_path,
    initialization_root,
)
from novel_authoring.metrics.models import (
    ContributionKind,
    EvidenceDirection,
    MetricComponentStatus,
    ObservationSourceKind,
    SemanticEvidenceLink,
    SemanticObservation,
)
from novel_authoring.metrics.registry import MetricSourceKind, MetricsRegistry, load_registry
from novel_authoring.metrics.segments import list_segments, rebuild_segments
from novel_authoring.metrics.service import (
    MetricObservationService,
    MetricsAssembler,
    ObservationInput,
)
from novel_authoring.rhythm.service import rebuild_features
from novel_authoring.storage.manifest import authority_path, manifest_hash
from novel_authoring.utils import json_dumps, sha256_file, utc_now

CHAPTER_METRIC_IDS = (
    "pressure",
    "progress",
    "payoff",
    "risk_credibility",
    "agency",
    "legibility",
    "outcome_uncertainty",
    "resource_pressure",
)
BOOTSTRAP_ANALYZER_VERSION = "metric-bootstrap-lexical-v1"


class ChapterMetricBootstrapRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initialization_id: str
    arc_id: str
    task_id: str
    book_id: str
    edition_id: str
    chapter_id: str
    chapter_ordinal: int = Field(ge=1)
    content_sha256: str
    analyzer_version: str
    analysis_status: str
    realized_primary_function: str | None = None
    emotional_intensity_band: str = "UNKNOWN"
    primary_thread: str | None = None
    irreversible_change: bool | None = None
    promise_opened: bool | None = None
    promise_advanced: bool | None = None
    promise_resolved: bool | None = None
    payoff_type: str | None = None
    payoff_presence: str | None = None
    cost_or_risk: str | None = None
    structural_signature: dict[str, Any] = Field(default_factory=dict)
    chapter_summary: str = ""
    chapter_role_in_arc: str = ""
    observations: list[SemanticObservation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class InitializationMetricBootstrapManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "initialization-metric-bootstrap-v1"
    initialization_id: str
    book_id: str
    edition_id: str
    source_manifest_sha256: str
    effective_content_sha256: str
    registry_hash: str
    analyzer_version: str
    total_chapters: int = Field(ge=0)
    expected_chapter_ids: list[str]
    completed_chapter_ids: list[str] = Field(default_factory=list)
    failed_chapter_ids: list[str] = Field(default_factory=list)
    detailed_window_start: int = Field(ge=1)
    detailed_window_end: int = Field(ge=1)
    record_path: str
    record_sha256: str
    created_at: str


class MetricBootstrapImportReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "metric-bootstrap-import-report-v1"
    initialization_id: str
    book_id: str
    edition_id: str
    status: str
    record_path: str
    record_sha256: str
    records_total: int = 0
    records_imported: int = 0
    records_skipped_idempotent: int = 0
    observations_added: int = 0
    evidence_links_added: int = 0
    rebuilt_run_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: str


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _root_for(
    database: Database, book_id: str, edition_id: str, initialization_id: str
) -> Path:
    root = initialization_root(database, book_id, edition_id, initialization_id)
    if not (root / "initialization_manifest.json").is_file():
        raise InitializationError(f"初始化目录不存在：{root}")
    return root


def _init_payload(root: Path) -> dict[str, Any]:
    try:
        value = json.loads((root / "initialization_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InitializationError(f"初始化 manifest 不可读取：{root}") from exc
    if not isinstance(value, dict):
        raise InitializationError("初始化 manifest 必须是 object")
    return value


def _current_chapters(database: Database, book_id: str, edition_id: str) -> list[dict[str, Any]]:
    with database.connect() as connection:
        return [dict(row) for row in edition_chapters(connection, book_id, edition_id)]


def _effective_hash(chapters: Iterable[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        "".join(str(item.get("content_sha256") or "") for item in chapters).encode("utf-8")
    ).hexdigest()


def _check_anchor(
    database: Database,
    book_id: str,
    edition_id: str,
    root: Path,
    chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    init_manifest = _init_payload(root)
    current_effective = _effective_hash(chapters)
    source_manifest = authority_path(
        Path(str(database.scalar("SELECT workspace_root FROM books WHERE book_id=?", (book_id,))))
    )
    current_source = manifest_hash(source_manifest) if source_manifest.is_file() else ""
    if str(init_manifest.get("source_manifest_sha256", "")) != current_source:
        raise InitializationError("Source manifest hash 已变化，拒绝生成/导入 Metric Bootstrap")
    if str(init_manifest.get("effective_content_sha256", "")) != current_effective:
        raise InitializationError("effective content hash 已变化，拒绝生成/导入 Metric Bootstrap")
    return {
        "source_manifest_sha256": current_source,
        "effective_content_sha256": current_effective,
        "initialization_id": str(init_manifest.get("initialization_id", "")),
    }


def _count_hits(text: str, terms: Iterable[str]) -> int:
    return sum(len(re.findall(re.escape(term), text, flags=re.IGNORECASE)) for term in terms)


def _score(text: str, terms: Iterable[str], *, base: float = 8.0, step: float = 18.0) -> float:
    return max(0.0, min(100.0, base + step * min(5, _count_hits(text, terms))))


def _contains(text: str, terms: Iterable[str]) -> bool:
    return any(term.lower() in text.lower() for term in terms)


def _function(text: str) -> str:
    signals = [
        ("major_payoff", ("奖励", "收获", "突破", "升级", "获得", "解锁", "胜利")),
        ("choice", ("选择", "三选一", "选项", "决定", "方案")),
        ("pressure_build", ("危险", "袭击", "怪物", "战斗", "追杀", "危机", "死亡")),
        ("discovery", ("发现", "探索", "线索", "秘密", "真相", "地图")),
        ("relationship_shift", ("信任", "背叛", "合作", "队友", "联盟", "交易")),
        ("world_expansion", ("区域", "城市", "基地", "避难所", "世界", "营地")),
        ("recovery", ("休息", "恢复", "修炼", "疗伤", "准备")),
    ]
    for name, terms in signals:
        if _contains(text, terms):
            return name
    return "setup"


def _emotion(text: str) -> str:
    high = _count_hits(text, ("死亡", "爆炸", "恐怖", "震惊", "愤怒", "绝望", "狂喜", "大战"))
    medium = _count_hits(text, ("危险", "紧张", "担心", "惊讶", "战斗", "选择"))
    if high >= 4:
        return "EXTREME"
    if high >= 1 or medium >= 4:
        return "HIGH"
    if medium >= 1:
        return "MEDIUM"
    return "LOW"


def _quote_for(text: str, terms: Iterable[str]) -> str:
    clean = text.strip()
    for term in terms:
        match = re.search(re.escape(term), clean, flags=re.IGNORECASE)
        if match:
            start = max(0, match.start() - 42)
            return clean[start : min(len(clean), start + 180)]
    return clean[:180]


def _evidence(
    *,
    text: str,
    source_span_id: str | None,
    segment: Mapping[str, Any] | None,
    terms: Iterable[str],
    confidence: float,
    rationale: str,
) -> SemanticEvidenceLink:
    quote = _quote_for(text, terms)
    if segment is not None:
        return SemanticEvidenceLink(
            segment_id=str(segment["segment_id"]),
            contribution_kind=ContributionKind.SEMANTIC_SUPPORT,
            direction=EvidenceDirection.SUPPORTS,
            strength=0.55,
            confidence=confidence,
            evidence_quote=_quote_for(str(segment.get("text") or text), terms),
            rationale=rationale,
        )
    return SemanticEvidenceLink(
        source_span_id=source_span_id,
        contribution_kind=ContributionKind.SEMANTIC_SUPPORT,
        direction=EvidenceDirection.SUPPORTS,
        strength=0.55,
        confidence=confidence,
        evidence_quote=quote,
        rationale=rationale,
    )


def _observation(
    metric_id: str,
    component_id: str,
    value: Any,
    *,
    text: str,
    source_span_id: str | None,
    segment: Mapping[str, Any] | None,
    terms: Iterable[str],
    confidence: float,
    detailed: bool,
) -> SemanticObservation:
    layer = "最近窗口详细 provisional" if detailed else "全书基础 provisional"
    return SemanticObservation(
        metric_id=metric_id,
        component_id=component_id,
        value=value,
        status=MetricComponentStatus.PROVISIONAL,
        confidence=confidence,
        reason=f"{layer}：本地词面与章节证据基线，待 Codex 语义复核。",
        evidence_links=[
            _evidence(
                text=text,
                source_span_id=source_span_id,
                segment=segment,
                terms=terms,
                confidence=confidence,
                rationale="证据只支持本地 provisional 语义估计，不升级为 Canon。",
            )
        ],
    )


def _feature_values(
    chapter: Mapping[str, Any],
    *,
    detailed: bool,
    source_span_id: str | None,
    segment: Mapping[str, Any] | None,
    primary_thread: str | None,
) -> ChapterMetricBootstrapRecord:
    text = f"{chapter.get('raw_heading') or chapter.get('title') or ''}\n{chapter.get('content') or ''}"
    evidence_text = str(chapter.get("source_excerpt") or text)
    function = _function(text)
    emotion = _emotion(text)
    confidence = 0.72 if detailed else 0.56
    threat_terms = ("危险", "袭击", "怪物", "战斗", "追杀", "危机", "死亡", "受伤")
    scarcity_terms = ("缺少", "短缺", "资源", "食物", "水", "燃油", "材料", "铁锭", "燃料", "消耗")
    deadline_terms = ("倒计时", "必须", "尽快", "限时", "截止", "马上", "天后", "小时")
    uncertainty_terms = ("未知", "随机", "概率", "不知道", "不确定", "谜", "秘密", "线索")
    social_terms = ("频道", "交易", "合作", "争夺", "冲突", "敌对", "联盟", "队伍")
    failure_terms = ("失败", "死亡", "损失", "代价", "受伤", "被迫", "无法", "失去")
    progress_terms = ("升级", "突破", "提升", "获得", "解锁", "建造", "制作", "强化", "新技能")
    world_terms = ("区域", "地图", "基地", "城市", "镇", "营地", "探索", "发现", "世界")
    relation_terms = ("朋友", "队友", "关系", "信任", "背叛", "合作", "交易")
    knowledge_terms = ("情报", "信息", "发现", "知道", "线索", "秘密", "真相", "规则")
    goal_terms = ("目标", "必须", "计划", "决定", "选择", "前往", "寻找", "完成")
    strategy_terms = ("方案", "策略", "利用", "安排", "组合", "布局", "比较", "选项", "三选一")
    payoff_terms = ("奖励", "收获", "突破", "升级", "获得", "解锁", "击杀", "胜利", "完成", "选择")
    risk_terms = failure_terms + threat_terms
    agency_terms = choice_terms = ("选择", "三选一", "选项", "决定", "计划", "主动", "利用")
    metric_values: dict[str, dict[str, Any]] = {
        "pressure": {
            "threat": _score(text, threat_terms),
            "scarcity": _score(text, scarcity_terms),
            "deadline": _score(text, deadline_terms, base=4, step=22),
            "uncertainty": _score(text, uncertainty_terms),
            "social_conflict": _score(text, social_terms, base=3, step=20),
            "failure_accumulation": _score(text, failure_terms, base=2, step=18),
        },
        "progress": {
            "permanent_growth": _score(text, progress_terms, base=5, step=18),
            "world_state_change": _score(text, world_terms, base=5, step=18),
            "relationship_change": _score(text, relation_terms, base=3, step=18),
            "knowledge_change": _score(text, knowledge_terms, base=5, step=18),
            "goal_advance": _score(text, goal_terms, base=4, step=20),
            "strategy_expansion": _score(text, strategy_terms, base=3, step=20),
        },
        "payoff": {
            "maturity": _score(text, payoff_terms, base=3, step=19),
            "impact": _score(text, ("击杀", "胜利", "突破", "升级", "获得", "摧毁"), base=3, step=20),
            "novelty": max(0.0, 100.0 - _score(text, ("重复", "再次", "又一次"), base=2, step=18)),
            "causality": _score(text, ("因为", "所以", "因此", "计划", "利用", "准备"), base=12, step=15),
            "after_value": _score(text, ("之后", "未来", "新的", "解锁", "升级", "下一步"), base=5, step=18),
            "structural_fit": _score(text, (function, "铺垫", "兑现", "转折"), base=20, step=14),
            "repetition_fatigue": _score(text, ("重复", "再次", "又一次"), base=4, step=18),
            "future_damage": _score(text, ("代价", "损失", "消耗", "失去", "后果"), base=5, step=18),
        },
        "risk_credibility": {
            "realized_cost_rate": _score(text, risk_terms, base=3, step=20),
            "consequence_clarity": _score(text, ("后果", "代价", "失败", "死亡", "损失"), base=8, step=18),
            "opposition_effectiveness": _score(text, ("敌人", "对手", "怪物", "袭击", "无法"), base=5, step=18),
            "protection_limit_visibility": _score(text, ("限制", "边界", "不能", "消耗", "保护"), base=6, step=17),
            "information_limits": _score(text, uncertainty_terms, base=8, step=17),
        },
        "agency": {
            "agency": {
                "value_balance": min(1.0, 0.35 + 0.15 * _count_hits(text, choice_terms)),
                "consequence_difference": min(1.0, 0.30 + 0.14 * _count_hits(text, ("后果", "代价", "结果"))),
                "information_adequacy": min(1.0, 0.35 + 0.12 * _count_hits(text, ("信息", "情报", "知道", "比较"))),
                "opportunity_cost": min(1.0, 0.25 + 0.15 * _count_hits(text, ("消耗", "机会", "失去", "代价"))),
                "long_term_effect": min(1.0, 0.30 + 0.13 * _count_hits(text, ("之后", "未来", "长期", "下一步"))),
            }
        },
        "legibility": {
            "goal_clarity": _score(text, goal_terms, base=20, step=14),
            "rule_clarity": _score(text, ("规则", "系统", "属性", "条件", "只能", "需要"), base=20, step=14),
            "consequence_clarity": _score(text, ("后果", "代价", "失败", "死亡", "奖励"), base=18, step=15),
            "information_provenance": _score(text, ("看到", "听到", "消息", "情报", "提示", "系统"), base=25, step=13),
        },
        "outcome_uncertainty": {
            "danger_unknown": _score(text, ("未知", "危险", "怪物", "随机", "概率"), base=10, step=17),
            "opponent_plan_unknown": _score(text, ("敌人", "对手", "计划", "阴谋", "不知道"), base=8, step=18),
            "motivation_unknown": _score(text, ("为什么", "动机", "目的", "秘密", "不明"), base=6, step=18),
            "reward_or_result_unknown": _score(text, ("结果", "奖励", "选择", "概率", "未知"), base=8, step=17),
            "world_truth_unknown": _score(text, ("真相", "秘密", "世界", "规则", "未知", "线索"), base=8, step=17),
        },
        "resource_pressure": {
            "current_shortfall": _score(text, scarcity_terms, base=5, step=19),
            "cost_income_imbalance": _score(text, ("成本", "消耗", "收入", "交易", "价格", "资源"), base=5, step=18),
            "recently_blocked_actions": _score(text, ("无法", "缺少", "不够", "受阻", "失败"), base=4, step=19),
            "near_future_demand": _score(text, ("需要", "准备", "未来", "下一步", "升级", "制作"), base=8, step=16),
            "reader_salience": _score(text, ("资源", "食物", "水", "燃油", "材料", "铁锭", "玻璃", "诡晶"), base=12, step=15),
        },
    }
    observations: list[SemanticObservation] = []
    terms_by_component: dict[str, dict[str, tuple[str, ...]]] = {
        "pressure": {
            "threat": threat_terms, "scarcity": scarcity_terms, "deadline": deadline_terms,
            "uncertainty": uncertainty_terms, "social_conflict": social_terms, "failure_accumulation": failure_terms,
        },
        "progress": {
            "permanent_growth": progress_terms, "world_state_change": world_terms, "relationship_change": relation_terms,
            "knowledge_change": knowledge_terms, "goal_advance": goal_terms, "strategy_expansion": strategy_terms,
        },
        "payoff": {key: payoff_terms for key in metric_values["payoff"]},
        "risk_credibility": {key: risk_terms for key in metric_values["risk_credibility"]},
        "agency": {"agency": agency_terms},
        "legibility": {key: goal_terms for key in metric_values["legibility"]},
        "outcome_uncertainty": {key: uncertainty_terms for key in metric_values["outcome_uncertainty"]},
        "resource_pressure": {key: scarcity_terms for key in metric_values["resource_pressure"]},
    }
    for metric_id, values in metric_values.items():
        for component_id, value in values.items():
            observations.append(
                _observation(
                    metric_id,
                    component_id,
                    value,
                    text=evidence_text,
                    source_span_id=source_span_id,
                    segment=segment,
                    terms=terms_by_component[metric_id][component_id],
                    confidence=confidence,
                    detailed=detailed,
                )
            )
    signals = sorted(
        signal
        for signal, terms in {
            "threat": threat_terms,
            "scarcity": scarcity_terms,
            "choice": choice_terms,
            "payoff": payoff_terms,
            "knowledge": knowledge_terms,
            "resource": scarcity_terms,
        }.items()
        if _contains(text, terms)
    )
    ordinal = int(chapter["ordinal"])
    status = "DETAILED_PROVISIONAL" if detailed else "BASIC_PROVISIONAL"
    return ChapterMetricBootstrapRecord(
        initialization_id="",
        arc_id="",
        task_id="",
        book_id="",
        edition_id="",
        chapter_id=str(chapter["chapter_id"]),
        chapter_ordinal=ordinal,
        content_sha256=str(chapter.get("content_sha256") or ""),
        analyzer_version=BOOTSTRAP_ANALYZER_VERSION,
        analysis_status=status,
        realized_primary_function=_function(text),
        emotional_intensity_band=emotion,
        primary_thread=primary_thread,
        irreversible_change=_contains(text, progress_terms + ("死亡", "离开", "进入", "摧毁")),
        promise_opened=_contains(text, ("线索", "谜", "秘密", "未知", "将会", "以后")),
        promise_advanced=_contains(text, ("线索", "发现", "推进", "信息", "真相")),
        promise_resolved=_contains(text, ("真相", "完成", "解决", "揭开", "兑现")),
        payoff_type=("PROVISIONAL_REWARD_OR_PROGRESS" if _contains(text, payoff_terms) else "NONE_DETECTED"),
        payoff_presence=("PRESENT_PROVISIONAL" if _contains(text, payoff_terms) else "NOT_DETECTED"),
        cost_or_risk=("COST_OR_RISK_PRESENT" if _contains(text, risk_terms) else "NOT_DETECTED"),
        structural_signature={"function": function, "emotion": emotion, "signals": signals, "length": len(text)},
        chapter_summary=f"本地 provisional 基线：{function}；证据信号：{', '.join(signals) or 'none'}。",
        chapter_role_in_arc=f"Arc 内第 {ordinal} 章；由正文词面信号暂定为 {function}。",
        observations=observations,
        notes=["本记录是本地可复核 provisional baseline，不替代 Codex 三轮语义复核。"],
    )


def _records_for_prepare(
    database: Database,
    book_id: str,
    edition_id: str,
    root: Path,
    chapters: list[dict[str, Any]],
    *,
    recent_detailed_window: int,
) -> list[ChapterMetricBootstrapRecord]:
    arc_manifest = json.loads((root / "arc_manifest.json").read_text(encoding="utf-8"))
    arc_by_chapter: dict[str, str] = {}
    for arc in arc_manifest.get("arcs", []):
        for chapter_id in arc.get("chapter_ids", []):
            arc_by_chapter[str(chapter_id)] = str(arc["arc_id"])
    output_by_arc: dict[str, dict[str, Any]] = {}
    for output_arc_id in set(arc_by_chapter.values()):
        path = arc_output_path(
            root,
            str(arc_manifest.get("initialization_id", "")),
            book_id,
            edition_id,
            output_arc_id,
        )
        if path.is_file():
            try:
                output_by_arc[output_arc_id] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                output_by_arc[output_arc_id] = {}
    rebuild_segments(database, book_id, edition_id=edition_id)
    segments_by_chapter: dict[str, dict[str, Any]] = {}
    for chapter in chapters:
        if int(chapter["ordinal"]) >= max(1, len(chapters) - recent_detailed_window + 1):
            segments = list_segments(database, book_id, edition_id=edition_id, chapter_id=str(chapter["chapter_id"]))
            prose = next(
                (item for item in segments if str(item.get("segment_kind")) != "HEADING"),
                None,
            ) or (segments[0] if segments else None)
            if prose is not None:
                segments_by_chapter[str(chapter["chapter_id"])] = prose
    records: list[ChapterMetricBootstrapRecord] = []
    source_span_ids = {
        str(chapter["source_span_id"])
        for chapter in chapters
        if chapter.get("source_span_id")
    }
    source_excerpts: dict[str, str] = {}
    if source_span_ids:
        placeholders = ",".join("?" for _ in source_span_ids)
        with database.connect() as connection:
            source_excerpts = {
                str(row["span_id"]): str(row["excerpt"] or "")
                for row in connection.execute(
                    f"SELECT span_id, excerpt FROM source_spans WHERE span_id IN ({placeholders})",
                    tuple(source_span_ids),
                ).fetchall()
            }
    detailed_start = max(1, len(chapters) - recent_detailed_window + 1)
    for chapter in chapters:
        chapter_id = str(chapter["chapter_id"])
        arc_id = arc_by_chapter.get(chapter_id)
        if arc_id is None:
            raise InitializationError(f"章节没有分配 Arc：{chapter_id}")
        output = output_by_arc.get(arc_id, {})
        thread: str | None = next(
            (
                str(item.get("thread_id"))
                for item in output.get("main_threads", [])
                if item.get("thread_id")
            ),
            None,
        )
        record = _feature_values(
            {
                **chapter,
                "source_excerpt": source_excerpts.get(str(chapter.get("source_span_id")), ""),
            },
            detailed=int(chapter["ordinal"]) >= detailed_start,
            source_span_id=(None if chapter.get("source_span_id") is None else str(chapter["source_span_id"])),
            segment=segments_by_chapter.get(chapter_id),
            primary_thread=thread,
        )
        task_id = (
            f"metric-bootstrap:{root.name}:{chapter_id}:"
            f"{BOOTSTRAP_ANALYZER_VERSION}:{str(chapter.get('content_sha256') or '')[:16]}"
        )
        records.append(
            record.model_copy(
                update={
                    "initialization_id": root.name,
                    "arc_id": arc_id,
                    "task_id": task_id,
                    "book_id": book_id,
                    "edition_id": edition_id,
                }
            )
        )
    return records


def prepare_metric_bootstrap(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    initialization_id: str,
    recent_detailed_window: int = 50,
    registry: MetricsRegistry | None = None,
) -> dict[str, Any]:
    if recent_detailed_window < 1:
        raise InitializationError("recent_detailed_window 必须为正数")
    selected = resolve_edition_id(database, book_id, edition_id)
    root = _root_for(database, book_id, selected, initialization_id)
    chapters = _current_chapters(database, book_id, selected)
    anchor = _check_anchor(database, book_id, selected, root, chapters)
    selected_registry = registry or load_registry()
    records = _records_for_prepare(
        database,
        book_id,
        selected,
        root,
        chapters,
        recent_detailed_window=min(recent_detailed_window, max(1, len(chapters))),
    )
    record_path = root / "metrics" / "chapter_metric_observations.jsonl"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        "".join(json_dumps(record.model_dump(mode="json")) + "\n" for record in records),
        encoding="utf-8",
    )
    detailed_start = max(1, len(chapters) - recent_detailed_window + 1)
    manifest = InitializationMetricBootstrapManifest(
        initialization_id=initialization_id,
        book_id=book_id,
        edition_id=selected,
        source_manifest_sha256=anchor["source_manifest_sha256"],
        effective_content_sha256=anchor["effective_content_sha256"],
        registry_hash=selected_registry.registry_hash,
        analyzer_version=BOOTSTRAP_ANALYZER_VERSION,
        total_chapters=len(chapters),
        expected_chapter_ids=[str(item["chapter_id"]) for item in chapters],
        completed_chapter_ids=[],
        failed_chapter_ids=[],
        detailed_window_start=detailed_start,
        detailed_window_end=len(chapters),
        record_path="metrics/chapter_metric_observations.jsonl",
        record_sha256=sha256_file(record_path),
        created_at=utc_now(),
    )
    _write_json(root / "metrics" / "metric_bootstrap_manifest.json", manifest.model_dump(mode="json"))
    return {
        "manifest": manifest.model_dump(mode="json"),
        "record_path": str(record_path),
        "record_count": len(records),
        "observation_count": sum(len(record.observations) for record in records),
        "source_manifest_sha256": anchor["source_manifest_sha256"],
        "effective_content_sha256": anchor["effective_content_sha256"],
    }


def _load_bootstrap_manifest(root: Path) -> InitializationMetricBootstrapManifest:
    path = root / "metrics" / "metric_bootstrap_manifest.json"
    if not path.is_file():
        raise InitializationError("严格 Metric Bootstrap Manifest 不存在")
    try:
        return InitializationMetricBootstrapManifest.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise InitializationError(f"Metric Bootstrap Manifest 不符合合同：{exc}") from exc


def _read_records(root: Path, manifest: InitializationMetricBootstrapManifest) -> list[ChapterMetricBootstrapRecord]:
    path = (root / manifest.record_path).resolve()
    if root.resolve() not in path.parents:
        raise InitializationError("record_path 必须位于初始化目录内")
    if not path.is_file():
        raise InitializationError(f"Metric Bootstrap JSONL 不存在：{path}")
    if sha256_file(path) != manifest.record_sha256:
        raise InitializationError("Metric Bootstrap JSONL hash 不匹配")
    records: list[ChapterMetricBootstrapRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(ChapterMetricBootstrapRecord.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise InitializationError(f"Metric Bootstrap JSONL 第 {line_number} 行无效：{exc}") from exc
    return records


def _chapter_observation_match(database: Database, input_value: ObservationInput) -> str | None:
    if input_value.source_task_id is None:
        return None
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM metric_observations WHERE book_id=? AND edition_id=? AND scope_type=? "
            "AND scope_id=? AND metric_id=? AND component_id=? AND source_task_id=? "
            "AND retracted_at IS NULL ORDER BY created_at DESC",
            (
                input_value.book_id,
                input_value.edition_id,
                input_value.scope_type,
                input_value.scope_id,
                input_value.metric_id,
                input_value.component_id,
                input_value.source_task_id,
            ),
        ).fetchall()
    for row in rows:
        if (
            str(row["status"]) == input_value.status.value
            and str(row["source_kind"]) == input_value.source_kind.value
            and str(row["effective_content_sha256"] or "") == str(input_value.effective_content_sha256 or "")
            and str(row["analyzer_version"] or "") == str(input_value.analyzer_version or "")
            and str(row["reason"] or "") == input_value.reason
            and (None if row["confidence"] is None else float(row["confidence"])) == input_value.confidence
            and json.loads(str(row["value_json"])) == input_value.value
        ):
            return str(row["observation_id"])
    return None


def _validate_records(
    database: Database,
    manifest: InitializationMetricBootstrapManifest,
    root: Path,
    records: list[ChapterMetricBootstrapRecord],
    chapters: list[dict[str, Any]],
    registry: MetricsRegistry,
) -> None:
    expected = set(manifest.expected_chapter_ids)
    chapter_map = {str(item["chapter_id"]): item for item in chapters}
    arc_manifest = json.loads((root / "arc_manifest.json").read_text(encoding="utf-8"))
    arc_map = {
        str(chapter_id): str(arc["arc_id"])
        for arc in arc_manifest.get("arcs", [])
        for chapter_id in arc.get("chapter_ids", [])
    }
    seen: set[str] = set()
    for record in records:
        if record.initialization_id != manifest.initialization_id:
            raise InitializationError("record initialization_id 不匹配")
        if record.book_id != manifest.book_id or record.edition_id != manifest.edition_id:
            raise InitializationError("record book/edition 不匹配")
        if record.chapter_id in seen:
            raise InitializationError(f"章节重复：{record.chapter_id}")
        seen.add(record.chapter_id)
        chapter = chapter_map.get(record.chapter_id)
        if chapter is None:
            raise InitializationError(f"章节不属于当前 edition：{record.chapter_id}")
        if str(chapter.get("content_sha256") or "") != record.content_sha256:
            raise InitializationError(f"章节 content hash 不匹配：{record.chapter_id}")
        if record.arc_id != arc_map.get(record.chapter_id):
            raise InitializationError(f"章节 Arc 不匹配：{record.chapter_id}")
        for observation in record.observations:
            registry.validate_metric_scope(observation.metric_id, "CHAPTER")
            registry.component(observation.metric_id, observation.component_id)
            registry.validate_source(
                observation.metric_id,
                observation.component_id,
                MetricSourceKind.SEMANTIC_ESTIMATE,
            )
    if seen != expected:
        missing = sorted(expected - seen)
        extra = sorted(seen - expected)
        raise InitializationError(f"JSONL 章节集合不匹配：missing={missing[:5]} extra={extra[:5]}")


def rebuild_metric_runs(
    database: Database,
    book_id: str,
    edition_id: str,
    chapter_ids: Iterable[str],
) -> list[str]:
    assembler = MetricsAssembler(database)
    run_ids: list[str] = []
    for chapter_id in chapter_ids:
        assembler.invalidate_scope(book_id, edition_id, "CHAPTER", chapter_id)
        run = assembler.rebuild(
            book_id,
            edition_id=edition_id,
            scope_type="CHAPTER",
            scope_id=chapter_id,
        )
        run_ids.append(str(run["run_id"]))
    return run_ids


def import_metric_bootstrap(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    initialization_id: str,
    input_path: Path | None = None,
    registry: MetricsRegistry | None = None,
) -> dict[str, Any]:
    selected = resolve_edition_id(database, book_id, edition_id)
    root = _root_for(database, book_id, selected, initialization_id)
    chapters = _current_chapters(database, book_id, selected)
    _check_anchor(database, book_id, selected, root, chapters)
    selected_registry = registry or load_registry()
    manifest = _load_bootstrap_manifest(root)
    if manifest.book_id != book_id or manifest.edition_id != selected:
        raise InitializationError("Metric Bootstrap Manifest book/edition 不匹配")
    if manifest.registry_hash != selected_registry.registry_hash:
        raise InitializationError("Metric Bootstrap Manifest registry_hash 不匹配")
    if input_path is not None:
        resolved_input = input_path.resolve()
        expected_path = (root / manifest.record_path).resolve()
        if resolved_input != expected_path:
            raise InitializationError("当前实现只允许导入 Manifest 锚定的 JSONL 路径")
    records = _read_records(root, manifest)
    _validate_records(database, manifest, root, records, chapters, selected_registry)
    service = MetricObservationService(database, selected_registry)
    projection_hash = None
    with database.connect() as connection:
        projection_hash = projection_from_connection(connection, book_id, selected).sha256()
    config_hash = MetricsAssembler(database, selected_registry).settings.metrics
    from novel_authoring.utils import sha256_bytes

    config_digest = sha256_bytes(json_dumps(config_hash).encode("utf-8"))
    task_ids = sorted({record.task_id for record in records})
    existing_rows: dict[tuple[str, str, str, str], list[Any]] = {}
    if task_ids:
        placeholders = ",".join("?" for _ in task_ids)
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM metric_observations WHERE book_id=? AND edition_id=? "
                f"AND source_task_id IN ({placeholders})",
                (book_id, selected, *task_ids),
            ).fetchall()
        for row in rows:
            key = (
                str(row["scope_id"]),
                str(row["metric_id"]),
                str(row["component_id"]),
                str(row["source_task_id"] or ""),
                str(row["observation_id"]),
            )
            existing_rows.setdefault(key[:-1], []).append(row)
    pending: list[ObservationInput] = []
    pending_chapter_ids: set[str] = set()
    skipped = 0
    for record in records:
        for semantic in record.observations:
            links = [link.model_dump(mode="json") for link in semantic.evidence_links]
            observation = ObservationInput(
                book_id=book_id,
                edition_id=selected,
                scope_type="CHAPTER",
                scope_id=record.chapter_id,
                metric_id=semantic.metric_id,
                component_id=semantic.component_id,
                value=semantic.value,
                status=semantic.status,
                source_kind=ObservationSourceKind.SEMANTIC_ESTIMATE,
                confidence=semantic.confidence,
                reason=semantic.reason or semantic.unknown_reason or "",
                chapter_id=record.chapter_id,
                effective_content_sha256=record.content_sha256,
                projection_hash=projection_hash,
                registry_hash=manifest.registry_hash,
                config_hash=config_digest,
                source_task_id=record.task_id,
                analyzer_version=record.analyzer_version,
                evidence_links=links,
            )
            existing_key = (
                record.chapter_id,
                semantic.metric_id,
                semantic.component_id,
                record.task_id,
            )
            matches = existing_rows.get(existing_key, [])
            if any(
                str(row["status"]) == observation.status.value
                and str(row["source_kind"]) == observation.source_kind.value
                and str(row["effective_content_sha256"] or "")
                == str(observation.effective_content_sha256 or "")
                and str(row["analyzer_version"] or "")
                == str(observation.analyzer_version or "")
                and str(row["reason"] or "") == observation.reason
                and (None if row["confidence"] is None else float(row["confidence"]))
                == observation.confidence
                and json.loads(str(row["value_json"])) == observation.value
                for row in matches
            ):
                skipped += 1
                continue
            pending.append(observation)
            pending_chapter_ids.add(record.chapter_id)
    added_ids = service.append_many(pending)
    added = len(added_ids)
    evidence_added = sum(len(observation.evidence_links) for observation in pending)
    if added:
        rebuild_features(database, book_id, edition_id=selected)
        from novel_authoring.planning.aggregates import invalidate_planning_aggregates

        invalidate_planning_aggregates(database, book_id, selected)
        run_ids = rebuild_metric_runs(database, book_id, selected, [record.chapter_id for record in records])
    else:
        run_ids = []
        with database.connect() as connection:
            current_ids = [
                str(row["scope_id"])
                for row in connection.execute(
                    "SELECT DISTINCT scope_id FROM metric_runs WHERE book_id=? AND edition_id=? "
                    "AND scope_type='CHAPTER' AND invalidated_at IS NULL",
                    (book_id, selected),
                )
            ]
        if not current_ids:
            run_ids = rebuild_metric_runs(database, book_id, selected, [record.chapter_id for record in records])
    report = MetricBootstrapImportReport(
        initialization_id=initialization_id,
        book_id=book_id,
        edition_id=selected,
        status="SUCCESS",
        record_path=manifest.record_path,
        record_sha256=manifest.record_sha256,
        records_total=len(records),
        records_imported=len(pending_chapter_ids),
        records_skipped_idempotent=skipped,
        observations_added=added,
        evidence_links_added=evidence_added,
        rebuilt_run_ids=run_ids,
        created_at=utc_now(),
    )
    _write_json(root / "metrics" / "import_report.json", report.model_dump(mode="json"))
    updated_manifest = manifest.model_copy(
        update={
            "completed_chapter_ids": [record.chapter_id for record in records],
            "failed_chapter_ids": [],
        }
    )
    _write_json(root / "metrics" / "metric_bootstrap_manifest.json", updated_manifest.model_dump(mode="json"))
    from novel_authoring.initialization.service import refresh_initialization

    refresh_initialization(database, book_id, edition_id=selected, initialization_id=initialization_id)
    return report.model_dump(mode="json")


def metric_bootstrap_status(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    initialization_id: str,
    registry: MetricsRegistry | None = None,
) -> dict[str, Any]:
    selected = resolve_edition_id(database, book_id, edition_id)
    root = _root_for(database, book_id, selected, initialization_id)
    chapters = _current_chapters(database, book_id, selected)
    expected_ids = {str(item["chapter_id"]) for item in chapters}
    chapter_hashes = {
        str(item["chapter_id"]): str(item.get("content_sha256") or "") for item in chapters
    }
    manifest_path = root / "metrics" / "metric_bootstrap_manifest.json"
    report_path = root / "metrics" / "import_report.json"
    manifest: InitializationMetricBootstrapManifest | None = None
    errors: list[str] = []
    records: list[ChapterMetricBootstrapRecord] = []
    if manifest_path.is_file():
        try:
            manifest = _load_bootstrap_manifest(root)
            records = _read_records(root, manifest)
        except InitializationError as exc:
            errors.append(str(exc))
    else:
        errors.append("严格 Metric Bootstrap Manifest 不存在")
    report: MetricBootstrapImportReport | None = None
    if report_path.is_file():
        try:
            report = MetricBootstrapImportReport.model_validate(
                json.loads(report_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"Import Report 无效：{exc}")
    selected_registry = registry or load_registry()
    record_validation_ok = True
    anchor: dict[str, Any] = {}
    try:
        anchor = _check_anchor(database, book_id, selected, root, chapters)
    except InitializationError as exc:
        record_validation_ok = False
        errors.append(str(exc))
    if manifest is not None:
        if manifest.book_id != book_id or manifest.edition_id != selected:
            record_validation_ok = False
            errors.append("Metric Bootstrap Manifest book/edition 不匹配")
        if manifest.registry_hash != selected_registry.registry_hash:
            record_validation_ok = False
            errors.append("Metric Bootstrap Manifest registry_hash 不匹配")
        if anchor and (
            manifest.source_manifest_sha256 != anchor["source_manifest_sha256"]
            or manifest.effective_content_sha256 != anchor["effective_content_sha256"]
        ):
            record_validation_ok = False
            errors.append("Metric Bootstrap Manifest source/effective hash 不匹配")
        if manifest.expected_chapter_ids != [str(item["chapter_id"]) for item in chapters]:
            record_validation_ok = False
            errors.append("Metric Bootstrap Manifest expected_chapter_ids 不匹配")
        try:
            _validate_records(database, manifest, root, records, chapters, selected_registry)
        except (InitializationError, ValueError) as exc:
            record_validation_ok = False
            errors.append(str(exc))
    prefix = f"metric-bootstrap:{initialization_id}:%"
    with database.connect() as connection:
        observation_rows = connection.execute(
            "SELECT * FROM metric_observations WHERE book_id=? AND edition_id=? AND source_task_id LIKE ?",
            (book_id, selected, prefix),
        ).fetchall()
        evidence_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM metric_evidence_links WHERE observation_id IN "
                "(SELECT observation_id FROM metric_observations WHERE book_id=? AND edition_id=? AND source_task_id LIKE ?)",
                (book_id, selected, prefix),
            ).fetchone()[0]
        )
        latest_chapter = chapters[-1] if chapters else None
        latest_run = None
        if latest_chapter is not None:
            latest_run = connection.execute(
                "SELECT * FROM metric_runs WHERE book_id=? AND edition_id=? AND scope_type='CHAPTER' "
                "AND scope_id=? AND invalidated_at IS NULL ORDER BY created_at DESC LIMIT 1",
                (book_id, selected, str(latest_chapter["chapter_id"])),
            ).fetchone()
    observed_chapters = {
        str(row["chapter_id"])
        for row in observation_rows
        if row["chapter_id"] is not None
        and int(row["active"] or 0) == 1
        and row["retracted_at"] is None
        and str(row["freshness_status"] or "FRESH") == "FRESH"
        and str(row["effective_content_sha256"] or "") == chapter_hashes.get(str(row["chapter_id"]), "")
    }
    semantic_count = sum(1 for row in observation_rows if str(row["source_kind"]) == "SEMANTIC_ESTIMATE")
    current_id = str(chapters[-1]["chapter_id"]) if chapters else ""
    current_hash = chapter_hashes.get(current_id, "")
    current_rows = [
        row
        for row in observation_rows
        if str(row["chapter_id"] or "") == current_id
        and int(row["active"] or 0) == 1
        and row["retracted_at"] is None
        and str(row["freshness_status"] or "FRESH") == "FRESH"
        and str(row["effective_content_sha256"] or "") == current_hash
    ]
    expected_component_keys = {
        (metric_id, component_id)
        for metric_id in CHAPTER_METRIC_IDS
        for component_id in selected_registry.metric(metric_id).required_components
    }
    current_component_keys = {
        (str(row["metric_id"]), str(row["component_id"]))
        for row in current_rows
        if str(row["status"]) in {
            MetricComponentStatus.AVAILABLE.value,
            MetricComponentStatus.PROVISIONAL.value,
        }
    }
    current_coverage = len(current_component_keys & expected_component_keys) / max(
        1, len(expected_component_keys)
    )
    source_mapping = 0.0
    try:
        source_coverage = SourceCoverage.model_validate(_read_json(root / "source_coverage.json"))
        source_mapping = source_coverage.chapter_coverage
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"Source Coverage 无效：{exc}")

    arc_output_count = 0
    feature_chapter_ids: set[str] = set()
    arc_payload: Any = {}
    try:
        arc_payload = _read_json(root / "arc_manifest.json")
        arc_items = arc_payload.get("arcs", []) if isinstance(arc_payload, dict) else []
        for arc in arc_items:
            arc_id = str(arc.get("arc_id", ""))
            output_path = arc_output_path(
                root,
                str(arc_payload.get("initialization_id", "")),
                book_id,
                selected,
                arc_id,
            )
            if not output_path.is_file():
                continue
            arc_output_count += 1
            output_payload = _read_json(output_path)
            for feature in output_payload.get("chapter_semantic_features", []):
                if (
                    isinstance(feature, dict)
                    and feature.get("chapter_id")
                    and str(feature.get("analysis_status", "PENDING")).upper()
                    not in {"PENDING", "UNKNOWN", "NOT_ANALYZED"}
                ):
                    feature_chapter_ids.add(str(feature["chapter_id"]))
    except (OSError, json.JSONDecodeError, AttributeError, TypeError) as exc:
        errors.append(f"Arc Output/Chapter Semantic Feature 无法审计：{exc}")
    arc_output_coverage = arc_output_count / max(1, len(arc_payload.get("arcs", []))) if isinstance(arc_payload, dict) else 0.0
    feature_coverage = len(feature_chapter_ids & expected_ids) / max(1, len(expected_ids))
    observation_coverage = len(observed_chapters) / max(1, len(expected_ids))
    recent_expected = (
        {
            str(item["chapter_id"])
            for item in chapters
            if manifest is not None
            and manifest.detailed_window_start <= int(item["ordinal"]) <= manifest.detailed_window_end
        }
        if manifest is not None
        else set()
    )
    recent_coverage = len(recent_expected & observed_chapters) / max(1, len(recent_expected))
    report_success = report is not None and report.status == "SUCCESS"
    report_matches = bool(
        report is not None
        and report.initialization_id == initialization_id
        and report.book_id == book_id
        and report.edition_id == selected
        and report.record_sha256 == (manifest.record_sha256 if manifest is not None else "")
        and report.records_total == len(records)
    )
    latest_run_ready = bool(
        latest_run is not None
        and str(latest_run["effective_content_sha256"] or "") == current_hash
        and str(latest_run["status"]) in {"COMPLETE", "PROVISIONAL"}
    )
    ready = bool(
        manifest is not None
        and record_validation_ok
        and len(records) == len(expected_ids)
        and report_success
        and report_matches
        and set(manifest.completed_chapter_ids) == expected_ids
        and expected_ids <= observed_chapters
        and recent_coverage >= 0.70
        and current_coverage >= 0.70
        and latest_run_ready
    )
    if not ready:
        if not expected_ids <= observed_chapters:
            errors.append("仍有章节没有 Metric Observation")
        if recent_coverage < 0.70:
            errors.append("最近详细窗口 Metric Observation Coverage 低于 70%")
        if current_coverage < 0.70:
            errors.append("最新章节相关 Metric Coverage 低于 70%")
        if not latest_run_ready:
            errors.append("最新章节 Metric Run 尚未按当前 hash 重建为 COMPLETE/PROVISIONAL")
    return {
        "status": "COMPLETE" if ready else "NOT_READY",
        "initialization_id": initialization_id,
        "book_id": book_id,
        "edition_id": selected,
        "manifest": None if manifest is None else manifest.model_dump(mode="json"),
        "import_report": None if report is None else report.model_dump(mode="json"),
        "record_count": len(records),
        "metric_observation_count": len(observation_rows),
        "semantic_estimate_count": semantic_count,
        "evidence_link_count": evidence_count,
        "latest_chapter_id": current_id,
        "latest_run_id": None if latest_run is None else str(latest_run["run_id"]),
        "coverage": {
            "source_mapping_coverage": source_mapping,
            "arc_output_coverage": arc_output_coverage,
            "chapter_semantic_feature_coverage": feature_coverage,
            "metric_observation_coverage": observation_coverage,
            "recent_detailed_metric_coverage": recent_coverage,
            "current_chapter_metric_coverage": current_coverage,
        },
        "errors": sorted(set(errors)),
    }


def rebuild_initialization_metric_runs(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    initialization_id: str,
) -> dict[str, Any]:
    selected = resolve_edition_id(database, book_id, edition_id)
    root = _root_for(database, book_id, selected, initialization_id)
    manifest = _load_bootstrap_manifest(root)
    prefix = f"metric-bootstrap:{initialization_id}:%"
    with database.connect() as connection:
        ids = [
            str(row["chapter_id"])
            for row in connection.execute(
                "SELECT DISTINCT chapter_id FROM metric_observations WHERE book_id=? AND edition_id=? "
                "AND source_task_id LIKE ? AND chapter_id IS NOT NULL ORDER BY chapter_id",
                (book_id, selected, prefix),
            )
        ]
    run_ids = rebuild_metric_runs(database, book_id, selected, ids)
    _write_json(
        root / "metrics" / "run_rebuild_report.json",
        {"initialization_id": initialization_id, "chapter_count": len(ids), "run_ids": run_ids, "created_at": utc_now()},
    )
    return {"initialization_id": initialization_id, "chapter_count": len(ids), "run_ids": run_ids, "manifest": manifest.model_dump(mode="json")}


__all__ = [
    "CHAPTER_METRIC_IDS",
    "ChapterMetricBootstrapRecord",
    "InitializationMetricBootstrapManifest",
    "MetricBootstrapImportReport",
    "prepare_metric_bootstrap",
    "import_metric_bootstrap",
    "metric_bootstrap_status",
    "rebuild_initialization_metric_runs",
]
