"""Planning public API with lazy imports.

Lazy exports keep the strict Innovation models usable from contracts and
drafts without importing the validation service while the planning package is
still initializing.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "build_boundary_packet": ("novel_authoring.planning.boundary", "build_boundary_packet"),
    "BatchChunkPlan": ("novel_authoring.planning.batch", "BatchChunkPlan"),
    "BatchChapterValidation": ("novel_authoring.planning.batch", "BatchChapterValidation"),
    "BatchError": ("novel_authoring.planning.batch", "BatchError"),
    "BatchPlan": ("novel_authoring.planning.batch", "BatchPlan"),
    "BatchProjection": ("novel_authoring.planning.batch", "BatchProjection"),
    "BatchProvisionalState": ("novel_authoring.planning.batch", "BatchProvisionalState"),
    "BatchStatus": ("novel_authoring.planning.batch", "BatchStatus"),
    "BatchValidationSummary": ("novel_authoring.planning.batch", "BatchValidationSummary"),
    "complete_chunk": ("novel_authoring.planning.batch", "complete_chunk"),
    "create_batch": ("novel_authoring.planning.batch", "create_batch"),
    "create_checkpoint": ("novel_authoring.planning.batch", "create_checkpoint"),
    "get_batch_plan": ("novel_authoring.planning.batch", "get_batch_plan"),
    "get_batch_projection": ("novel_authoring.planning.batch", "get_batch_projection"),
    "get_chunk_context": ("novel_authoring.planning.batch", "get_chunk_context"),
    "build_chapter_contract": ("novel_authoring.planning.contracts", "build_chapter_contract"),
    "import_candidate_output": ("novel_authoring.planning.candidates", "import_candidate_output"),
    "prepare_candidate_task": ("novel_authoring.planning.candidates", "prepare_candidate_task"),
    "PlanningAggregate": ("novel_authoring.planning.aggregates", "PlanningAggregate"),
    "PlanningMetricBundle": ("novel_authoring.planning.aggregates", "PlanningMetricBundle"),
    "build_planning_aggregate": ("novel_authoring.planning.aggregates", "build_planning_aggregate"),
    "invalidate_planning_aggregates": (
        "novel_authoring.planning.aggregates",
        "invalidate_planning_aggregates",
    ),
    "AlignmentJudgment": ("novel_authoring.planning.innovation", "AlignmentJudgment"),
    "assess_innovation_alignment": (
        "novel_authoring.planning.innovation",
        "assess_innovation_alignment",
    ),
    "CandidateInnovationPreview": (
        "novel_authoring.planning.innovation",
        "CandidateInnovationPreview",
    ),
    "CrossHorizonSynergy": (
        "novel_authoring.planning.innovation",
        "CrossHorizonSynergy",
    ),
    "EarnedRecombination": (
        "novel_authoring.planning.innovation",
        "EarnedRecombination",
    ),
    "ExpectedNarrativeDebt": (
        "novel_authoring.planning.innovation",
        "ExpectedNarrativeDebt",
    ),
    "ExperimentContextFingerprint": (
        "novel_authoring.planning.innovation",
        "ExperimentContextFingerprint",
    ),
    "classify_novelty": ("novel_authoring.planning.innovation", "classify_novelty"),
    "InnovationControl": ("novel_authoring.planning.innovation", "InnovationControl"),
    "InnovationCommitments": (
        "novel_authoring.planning.innovation",
        "InnovationCommitments",
    ),
    "InnovationDiagnostics": (
        "novel_authoring.planning.innovation",
        "InnovationDiagnostics",
    ),
    "InnovationDirectionAlignment": (
        "novel_authoring.planning.innovation",
        "InnovationDirectionAlignment",
    ),
    "InnovationElement": ("novel_authoring.planning.innovation", "InnovationElement"),
    "InnovationFocus": ("novel_authoring.planning.innovation", "InnovationFocus"),
    "InnovationLevel": ("novel_authoring.planning.innovation", "InnovationLevel"),
    "InnovationMagnitude": (
        "novel_authoring.planning.innovation",
        "InnovationMagnitude",
    ),
    "InnovationRecommendation": (
        "novel_authoring.planning.innovation",
        "InnovationRecommendation",
    ),
    "InnovationRewardBreakdown": (
        "novel_authoring.planning.innovation",
        "InnovationRewardBreakdown",
    ),
    "InnovationRewardLine": (
        "novel_authoring.planning.innovation",
        "InnovationRewardLine",
    ),
    "InnovationTrace": ("novel_authoring.planning.innovation", "InnovationTrace"),
    "IntegrationCost": ("novel_authoring.planning.innovation", "IntegrationCost"),
    "NarrativeDebt": ("novel_authoring.planning.innovation", "NarrativeDebt"),
    "NarrativeDebtStatus": (
        "novel_authoring.planning.innovation",
        "NarrativeDebtStatus",
    ),
    "NarrativeDelta": ("novel_authoring.planning.innovation", "NarrativeDelta"),
    "NarrativeHorizon": ("novel_authoring.planning.innovation", "NarrativeHorizon"),
    "NarrativePatternDiagnostic": (
        "novel_authoring.planning.innovation",
        "NarrativePatternDiagnostic",
    ),
    "NarrativePortfolioSnapshot": (
        "novel_authoring.planning.innovation",
        "NarrativePortfolioSnapshot",
    ),
    "NarrativePayoff": ("novel_authoring.planning.innovation", "NarrativePayoff"),
    "NarrativeThreadLifecycle": (
        "novel_authoring.planning.innovation",
        "NarrativeThreadLifecycle",
    ),
    "NarrativeThreadState": (
        "novel_authoring.planning.innovation",
        "NarrativeThreadState",
    ),
    "NoveltyQuality": ("novel_authoring.planning.innovation", "NoveltyQuality"),
    "PayoffExtent": ("novel_authoring.planning.innovation", "PayoffExtent"),
    "PatternDistance": ("novel_authoring.planning.innovation", "PatternDistance"),
    "QuestionBalance": ("novel_authoring.planning.innovation", "QuestionBalance"),
    "SemanticPolicyLeakDiagnostic": (
        "novel_authoring.planning.innovation",
        "SemanticPolicyLeakDiagnostic",
    ),
    "build_narrative_portfolio_snapshot": (
        "novel_authoring.planning.diagnostics",
        "build_narrative_portfolio_snapshot",
    ),
    "calculate_candidate_innovation_reward": (
        "novel_authoring.planning.rewards",
        "calculate_candidate_innovation_reward",
    ),
    "calculate_innovation_reward": (
        "novel_authoring.planning.rewards",
        "calculate_innovation_reward",
    ),
    "calculate_realized_innovation_reward": (
        "novel_authoring.planning.rewards",
        "calculate_realized_innovation_reward",
    ),
    "detect_semantic_policy_leak": (
        "novel_authoring.planning.rewards",
        "detect_semantic_policy_leak",
    ),
    "detect_pattern_repetition": (
        "novel_authoring.planning.rewards",
        "detect_pattern_repetition",
    ),
    "estimate_integration_cost": (
        "novel_authoring.planning.innovation",
        "estimate_integration_cost",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module = import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value
