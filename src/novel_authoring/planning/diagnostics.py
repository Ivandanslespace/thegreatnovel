"""Portfolio diagnostics for candidate reasoning diversity and earned usage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.planning.innovation import (
    NarrativeDebt,
    NarrativeDebtStatus,
    NarrativeHorizon,
    NarrativePortfolioSnapshot,
    NarrativeThreadLifecycle,
    NarrativeThreadState,
)
from novel_authoring.planning.models import (
    CandidateLens,
    CandidateProposal,
    NoveltyProvenance,
)
from novel_authoring.runtime_baseline.models import EarnedEntry, EarnedSurface


class CandidatePortfolioDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_count: int = Field(ge=0)
    lens_counts: dict[str, int] = Field(default_factory=dict)
    continuity_count: int = Field(ge=0)
    payoff_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    world_count: int = Field(ge=0)
    social_count: int = Field(ge=0)
    forward_novelty_count: int = Field(ge=0)
    wildcard_count: int = Field(ge=0)
    earned_usage_count: int = Field(ge=0)
    earned_surface_usage_coverage: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


def _all_earned_entries(surface: EarnedSurface | None) -> list[EarnedEntry]:
    if surface is None:
        return []
    return [
        *surface.earned_capabilities,
        *surface.available_items,
        *surface.available_resources,
        *surface.actionable_knowledge,
        *surface.relationship_leverage,
    ]


def _candidate_uses_earned(
    candidate: CandidateProposal, earned: list[EarnedEntry]
) -> bool:
    if any(
        item.provenance is NoveltyProvenance.SOURCE_EARNED
        for item in candidate.novelty_provenance
    ):
        return True
    sources = {item.casefold() for item in candidate.causal_sources}
    return any(
        entry.entry_id.casefold() in sources or entry.name.casefold() in sources
        for entry in earned
    )


def diagnose_candidate_portfolio(
    candidates: list[CandidateProposal],
    *,
    earned_surface: EarnedSurface | None = None,
) -> CandidatePortfolioDiagnostics:
    """Count what a portfolio covers; diagnostics never reject by fixed quota."""

    lens_counts: dict[str, int] = {}
    counts = {
        "continuity": 0,
        "payoff": 0,
        "relationship": 0,
        "world": 0,
        "social": 0,
        "forward": 0,
        "wildcard": 0,
        "earned": 0,
    }
    earned = _all_earned_entries(earned_surface)
    for candidate in candidates:
        lens = candidate.lens.value
        lens_counts[lens] = lens_counts.get(lens, 0) + 1
        functions = {candidate.primary_function.value} | {
            item.value for item in candidate.secondary_functions
        }
        if (
            candidate.lens is CandidateLens.CONTINUITY_ACTIVE_THREAD
            or candidate.promises_to_advance
        ):
            counts["continuity"] += 1
        if candidate.promises_to_pay or {"partial_payoff", "major_payoff"}.intersection(functions):
            counts["payoff"] += 1
        if "relationship_shift" in functions:
            counts["relationship"] += 1
        if "world_expansion" in functions:
            counts["world"] += 1
        if "relationship_shift" in functions or "social" in candidate.social_feedback.casefold():
            counts["social"] += 1
        if candidate.lens is CandidateLens.FORWARD_EXPANSION or any(
            item.provenance is NoveltyProvenance.FORWARD_NOVELTY
            for item in candidate.novelty_provenance
        ):
            counts["forward"] += 1
        if candidate.wildcard:
            counts["wildcard"] += 1
        if _candidate_uses_earned(candidate, earned):
            counts["earned"] += 1

    warnings: list[str] = []
    if len(lens_counts) < min(len(candidates), 3):
        warnings.append("候选 lens 覆盖不足；这是诊断提示，不是固定配额门槛")
    if len({candidate.solution_method.casefold() for candidate in candidates}) < len(candidates):
        warnings.append("候选 solution_method 存在重复；请人工复核结构性差异")
    coverage = counts["earned"] / len(candidates) if candidates else 0.0
    return CandidatePortfolioDiagnostics(
        candidate_count=len(candidates),
        lens_counts=lens_counts,
        continuity_count=counts["continuity"],
        payoff_count=counts["payoff"],
        relationship_count=counts["relationship"],
        world_count=counts["world"],
        social_count=counts["social"],
        forward_novelty_count=counts["forward"],
        wildcard_count=counts["wildcard"],
        earned_usage_count=counts["earned"],
        earned_surface_usage_coverage=coverage,
        warnings=warnings,
    )


def _horizon(value: object, *, target_max_age: object = None) -> NarrativeHorizon:
    selected = str(value or "").upper()
    if selected in {item.value for item in NarrativeHorizon}:
        return NarrativeHorizon(selected)
    try:
        age = int(str(target_max_age)) if target_max_age is not None else 8
    except (TypeError, ValueError):
        age = 8
    if age <= 3:
        return NarrativeHorizon.SHORT
    if age <= 15:
        return NarrativeHorizon.MID
    return NarrativeHorizon.LONG


def _lifecycle(item: Mapping[str, object]) -> NarrativeThreadLifecycle:
    raw = str(item.get("lifecycle", item.get("phase", item.get("status", "")))).upper()
    if raw in {"RESOLVED", "CLOSED"}:
        return NarrativeThreadLifecycle.RESOLVED
    if raw in {"DORMANT", "HOLD"}:
        return NarrativeThreadLifecycle.DORMANT
    if raw in {"PAYOFF_READY", "READY", "RESOLVE_DUE"} or bool(item.get("payoff_ready")):
        return NarrativeThreadLifecycle.PAYOFF_READY
    if raw in {"SETUP", "OPEN"}:
        return NarrativeThreadLifecycle.SETUP
    if raw in {"PARTIALLY_PAID", "PARTIAL_PAYOFF"}:
        return NarrativeThreadLifecycle.PARTIALLY_PAID
    return NarrativeThreadLifecycle.DEVELOPING


def _int_value(item: Mapping[str, object], *keys: str) -> int:
    for key in keys:
        value = item.get(key)
        if value is not None:
            try:
                return max(0, int(str(value)))
            except (TypeError, ValueError):
                continue
    return 0


def build_narrative_portfolio_snapshot(
    *,
    active_threads: Sequence[Mapping[str, object]],
    promises: Mapping[str, Mapping[str, object]] | None,
    current_chapter: int,
    snapshot_id: str,
    consecutive_deferrals: int = 0,
) -> NarrativePortfolioSnapshot:
    """Freeze the current soft portfolio before an agent plans candidates."""

    thread_values: dict[str, dict[str, object]] = {}
    for item in active_threads:
        thread_id = str(item.get("thread_id", item.get("id", ""))).strip()
        if not thread_id:
            continue
        progress_value = item.get("progress")
        maturity: float | None
        try:
            maturity = (
                min(1.0, max(0.0, float(str(progress_value))))
                if progress_value is not None
                else None
            )
        except (TypeError, ValueError):
            maturity = None
        thread_values[thread_id] = {
            "thread_id": thread_id,
            "name": str(item.get("goal", item.get("name", ""))),
            "horizon": _horizon(item.get("horizon"), target_max_age=item.get("target_max_age")),
            "lifecycle": _lifecycle(item),
            "maturity": maturity,
            "maturity_note": str(item.get("maturity_note", "")),
            "opened_chapter": _int_value(
                item, "opened_chapter", "introduced_chapter", "introduced_ordinal"
            ),
            "last_advanced": _int_value(item, "last_advanced", "last_advanced_chapter"),
            "debt_ids": [],
        }

    debts: list[NarrativeDebt] = []
    payoff_ready_thread_ids: set[str] = set()
    overdue_debt_ids: list[str] = []
    for promise_id, item in (promises or {}).items():
        debt_id = str(item.get("promise_id", promise_id))
        thread_id = str(item.get("thread_id", ""))
        horizon = _horizon(item.get("horizon"), target_max_age=item.get("target_max_age"))
        opened = _int_value(item, "opened_chapter", "introduced_ordinal", "introduced_chapter")
        last_advanced = _int_value(item, "last_advanced", "last_advanced_chapter")
        progress = item.get("progress", 0)
        try:
            progress_float = float(str(progress))
        except (TypeError, ValueError):
            progress_float = 0.0
        raw_status = str(item.get("status", "OPEN")).upper()
        if raw_status in {"RESOLVED", "CLOSED", "PAID"}:
            status = NarrativeDebtStatus.RESOLVED
        elif bool(item.get("payoff_ready")) or progress_float >= 0.8:
            status = NarrativeDebtStatus.PAYOFF_READY
        elif last_advanced > opened:
            status = NarrativeDebtStatus.ADVANCED
        else:
            status = NarrativeDebtStatus.OPEN
        try:
            target_age = int(str(item.get("target_max_age", 8)))
        except (TypeError, ValueError):
            target_age = 8
        overdue = (
            opened > 0
            and
            status not in {
                NarrativeDebtStatus.RESOLVED,
                NarrativeDebtStatus.PAYOFF_READY,
            }
            and current_chapter - opened > target_age
        )
        if overdue:
            status = NarrativeDebtStatus.OVERDUE
            overdue_debt_ids.append(debt_id)
        if status is NarrativeDebtStatus.PAYOFF_READY and thread_id:
            payoff_ready_thread_ids.add(thread_id)
        if thread_id and thread_id not in thread_values:
            thread_values[thread_id] = {
                "thread_id": thread_id,
                "name": str(item.get("goal", item.get("name", ""))),
                "horizon": horizon,
                "lifecycle": (
                    NarrativeThreadLifecycle.PAYOFF_READY
                    if status is NarrativeDebtStatus.PAYOFF_READY
                    else NarrativeThreadLifecycle.DEVELOPING
                ),
                "maturity": min(1.0, max(0.0, progress_float)),
                "maturity_note": "由 active promise 生成的线程视图",
                "opened_chapter": opened,
                "last_advanced": last_advanced,
                "debt_ids": [],
            }
        if thread_id:
            debt_ids = thread_values[thread_id].get("debt_ids", [])
            existing_debt_ids = debt_ids if isinstance(debt_ids, list) else []
            thread_values[thread_id]["debt_ids"] = [
                *[str(value) for value in existing_debt_ids],
                debt_id,
            ]
        debts.append(
            NarrativeDebt(
                debt_id=debt_id,
                question_or_promise=str(
                    item.get(
                        "question_or_promise",
                        item.get("description", item.get("goal", "")),
                    )
                ),
                horizon=horizon,
                opened_chapter=opened,
                source_event=str(item.get("source_event", item.get("introduction_event", ""))),
                expected_payoff_window=str(
                    item.get("expected_payoff_window", f"within {target_age} chapters")
                ),
                maturity=(
                    "payoff_ready" if status is NarrativeDebtStatus.PAYOFF_READY
                    else "advanced" if status is NarrativeDebtStatus.ADVANCED
                    else "overdue" if status is NarrativeDebtStatus.OVERDUE
                    else "developing"
                ),
                status=status,
                last_advanced=last_advanced,
            )
        )

    threads = [NarrativeThreadState.model_validate(value) for value in thread_values.values()]
    for thread in threads:
        if thread.lifecycle is NarrativeThreadLifecycle.PAYOFF_READY:
            payoff_ready_thread_ids.add(thread.thread_id)
    return NarrativePortfolioSnapshot(
        snapshot_id=snapshot_id,
        current_chapter=max(0, current_chapter),
        short_threads=[item for item in threads if item.horizon is NarrativeHorizon.SHORT],
        mid_threads=[item for item in threads if item.horizon is NarrativeHorizon.MID],
        long_threads=[item for item in threads if item.horizon is NarrativeHorizon.LONG],
        narrative_debts=debts,
        payoff_ready_thread_ids=sorted(payoff_ready_thread_ids),
        overdue_debt_ids=sorted(set(overdue_debt_ids)),
        consecutive_deferrals=max(0, consecutive_deferrals),
        warnings=(
            [f"存在 {len(overdue_debt_ids)} 个超过软窗口的 Narrative Debt"]
            if overdue_debt_ids
            else []
        ),
    )


__all__ = [
    "CandidatePortfolioDiagnostics",
    "build_narrative_portfolio_snapshot",
    "diagnose_candidate_portfolio",
]
