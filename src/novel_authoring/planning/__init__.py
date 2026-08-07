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
    "ExperimentContextFingerprint": (
        "novel_authoring.planning.innovation",
        "ExperimentContextFingerprint",
    ),
    "classify_novelty": ("novel_authoring.planning.innovation", "classify_novelty"),
    "InnovationControl": ("novel_authoring.planning.innovation", "InnovationControl"),
    "InnovationDiagnostics": (
        "novel_authoring.planning.innovation",
        "InnovationDiagnostics",
    ),
    "InnovationDirectionAlignment": (
        "novel_authoring.planning.innovation",
        "InnovationDirectionAlignment",
    ),
    "InnovationFocus": ("novel_authoring.planning.innovation", "InnovationFocus"),
    "InnovationLevel": ("novel_authoring.planning.innovation", "InnovationLevel"),
    "InnovationRecommendation": (
        "novel_authoring.planning.innovation",
        "InnovationRecommendation",
    ),
    "InnovationTrace": ("novel_authoring.planning.innovation", "InnovationTrace"),
    "IntegrationCost": ("novel_authoring.planning.innovation", "IntegrationCost"),
    "NoveltyQuality": ("novel_authoring.planning.innovation", "NoveltyQuality"),
    "PatternDistance": ("novel_authoring.planning.innovation", "PatternDistance"),
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
