"""Portfolio diagnostics for candidate reasoning diversity and earned usage."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

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


__all__ = ["CandidatePortfolioDiagnostics", "diagnose_candidate_portfolio"]
