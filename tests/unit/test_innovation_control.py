from __future__ import annotations

import pytest

from novel_authoring.config import load_settings
from novel_authoring.metrics.gates import HardGateInput, evaluate_hard_gates
from novel_authoring.planning.innovation import (
    AlignmentJudgment,
    InnovationControl,
    InnovationFocus,
    InnovationLevel,
    IntegrationCost,
    NoveltyQuality,
    assess_innovation_alignment,
    build_experiment_context_fingerprint,
    classify_novelty,
    compare_experiment_contexts,
    estimate_integration_cost,
)


def test_default_is_medium_auto() -> None:
    control = InnovationControl()
    assert control.level is InnovationLevel.MEDIUM
    assert control.focus == [InnovationFocus.AUTO]


def test_auto_and_explicit_focus_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="AUTO"):
        InnovationControl(
            level=InnovationLevel.HIGH,
            focus=[InnovationFocus.AUTO, InnovationFocus.WORLD],
        )


def test_minimal_still_allows_a_forward_preview_contract() -> None:
    control = InnovationControl(level=InnovationLevel.MINIMAL)
    assert control.level is InnovationLevel.MINIMAL
    # The control changes search distance; it is not a no-novelty switch.
    assert control.focus == [InnovationFocus.AUTO]
    assert "Forward Novelty" in control.creative_distance_guidance
    assert "CONTINUITY_ACTIVE_THREAD" in control.lens_tendency_guidance


def test_level_guidance_changes_search_width_not_hard_gate_policy() -> None:
    minimal = InnovationControl(level=InnovationLevel.MINIMAL)
    bold = InnovationControl(level=InnovationLevel.BOLD)
    assert minimal.creative_distance_guidance != bold.creative_distance_guidance
    assert "hard gate" in bold.creative_distance_guidance


def test_hard_gates_are_identical_for_minimal_and_bold() -> None:
    settings = load_settings()
    gate_input = HardGateInput(
        character_fit_inputs={
            "motivation_alignment": 80,
            "knowledge_alignment": 80,
            "capability_alignment": 80,
            "relationship_alignment": 80,
            "emotional_continuity": 80,
        },
        style_fit_inputs={
            "pov_and_tense": 80,
            "diction_register": 80,
            "sentence_rhythm": 80,
            "dialogue_voice": 80,
            "exposition_density": 80,
            "emotional_distance": 80,
        },
    )
    minimal = evaluate_hard_gates(gate_input, settings.metrics)
    bold = evaluate_hard_gates(gate_input, settings.metrics)
    assert minimal == bold
    assert InnovationControl(level=InnovationLevel.BOLD).level is InnovationLevel.BOLD


def test_requested_and_realized_direction_are_separate() -> None:
    alignment = assess_innovation_alignment(
        [InnovationFocus.RELATIONSHIP, InnovationFocus.WORLD],
        [InnovationFocus.MECHANISM],
    )
    assert alignment.judgment is AlignmentJudgment.WEAK_ALIGNMENT
    assert classify_novelty(new_mechanisms=["组合已有能力"]) is NoveltyQuality.MEANINGFUL_NOVELTY
    assert classify_novelty() is NoveltyQuality.COSMETIC_NOVELTY
    assert estimate_integration_cost(new_world_elements=["新组织"]) is IntegrationCost.LOW
    assert (
        estimate_integration_cost(
            new_entities=["a", "b"],
            new_relationship_states=["trust"],
            new_world_elements=["place"],
        )
        is IntegrationCost.MEDIUM
    )


def test_context_fingerprint_ignores_identity_and_innovation_control() -> None:
    left = {
        "book_id": "a",
        "operation_id": "op-a",
        "variant": "L1",
        "innovation_control": {"level": "minimal"},
        "visible_source": {"chapter_id": "chapter-a", "text": "same"},
    }
    right = {
        "book_id": "b",
        "operation_id": "op-b",
        "variant": "L5",
        "innovation_control": {"level": "bold"},
        "visible_source": {"chapter_id": "chapter-b", "text": "same"},
    }
    assert compare_experiment_contexts(left, right) == []
    fingerprint = build_experiment_context_fingerprint(
        visible_source=left,
        distill_soft_context={"finding": "same"},
        runtime_state={"state": "same"},
        earned_surface={"surface": "same"},
        author_directives={"directive": "same"},
        recent_chapter_window={"window": "same"},
    )
    assert fingerprint.context_fingerprint


def test_context_fingerprint_detects_semantic_difference() -> None:
    assert compare_experiment_contexts(
        {"visible_source": {"text": "one"}},
        {"visible_source": {"text": "two"}},
    ) == ["visible_source.text"]
