from __future__ import annotations

import math

import pytest

from novel_authoring.config import load_settings
from novel_authoring.metrics.formulas import (
    agency,
    can_trigger_resource_liberation,
    candidate_score,
    character_fit,
    global_pressure,
    legibility,
    narrative_debt,
    outcome_uncertainty,
    payoff_component,
    payoff_cooldown_allowed,
    payoff_score,
    pressure,
    progress,
    repetition_fatigue,
    resource_pressure,
    stagnation_rate,
    structural_similarity,
    style_fit,
    thread_need,
    waiting_readiness,
)

CONFIG = load_settings().metrics


def test_pressure_constitution_vectors() -> None:
    keys = CONFIG["pressure"]["weights"]
    assert pressure(dict.fromkeys(keys, 0), CONFIG["pressure"]).score == 0
    assert pressure(dict.fromkeys(keys, 100), CONFIG["pressure"]).score == 100
    values = {
        "threat": 100,
        "scarcity": 50,
        "deadline": 0,
        "uncertainty": 100,
        "social_conflict": 50,
        "failure_accumulation": 0,
    }
    assert pressure(values, CONFIG["pressure"]).score == 55
    assert global_pressure([(1, 0), (3, 100)]) == 75
    assert global_pressure([]) is None


def test_narrative_debt_constitution_vectors() -> None:
    config = CONFIG["narrative_debt"]
    zero = narrative_debt(
        importance=0,
        reader_visibility=1,
        promise_progress=0,
        age_chapters=10,
        target_max_age=10,
        reminder_count=0,
        config=config,
    )
    capped = narrative_debt(
        importance=1,
        reader_visibility=1,
        promise_progress=0,
        age_chapters=20,
        target_max_age=10,
        reminder_count=5,
        config=config,
    )
    middle = narrative_debt(
        importance=0.8,
        reader_visibility=0.5,
        promise_progress=0.5,
        age_chapters=5,
        target_max_age=10,
        reminder_count=2,
        config=config,
    )
    assert zero.score == 0
    assert capped.score == 150
    assert middle.score == pytest.approx(10.794827, rel=1e-6)
    with pytest.raises(ValueError):
        narrative_debt(
            importance=1,
            reader_visibility=1,
            promise_progress=0,
            age_chapters=1,
            target_max_age=0,
            reminder_count=0,
            config=config,
        )


def test_progress_and_stagnation_boundaries() -> None:
    values = {
        "permanent_growth": 100,
        "world_state_change": 50,
        "relationship_change": 0,
        "knowledge_change": 100,
        "goal_advance": 50,
        "strategy_expansion": 0,
    }
    assert progress(values, CONFIG["progress"]).score == 52.5
    assert stagnation_rate([0] * 7, CONFIG["progress"]) is None
    assert stagnation_rate([0] * 8, CONFIG["progress"]) == 100
    assert stagnation_rate([10] * 8, CONFIG["progress"]) == 0
    assert stagnation_rate([0] * 5 + [10] * 3, CONFIG["progress"]) == 62.5


def test_payoff_subformulas_and_net_score() -> None:
    config = CONFIG["payoff"]
    assert waiting_readiness(5, 10) == 50
    assert waiting_readiness(15, 10) == 100
    assert payoff_component(
        {
            "target_pressure": 80,
            "setup_depth": 60,
            "waiting_readiness": 50,
            "cost_paid": 20,
            "arc_phase_fit": 40,
        },
        config["maturity_weights"],
    ) == 52
    assert payoff_component(
        {
            "relative_scale": 80,
            "constraint_removal": 60,
            "behavior_change": 40,
            "future_capacity": 20,
            "social_or_visual_proof": 0,
        },
        config["impact_weights"],
    ) == 46
    payoff = payoff_score(
        maturity=80,
        impact=70,
        causality=90,
        after_value=75,
        repetition_fatigue_score=20,
        structural_fit=80,
        future_damage=10,
        config=config,
    )
    assert payoff.inputs["novelty"] == 80
    assert payoff.score == pytest.approx(75.1)
    assert payoff_score(
        maturity=50,
        impact=50,
        causality=50,
        after_value=50,
        repetition_fatigue_score=50,
        structural_fit=50,
        future_damage=50,
        config=config,
    ).score == pytest.approx(39)


def test_resource_pressure_and_liberation_gate() -> None:
    values = {
        "current_shortfall": 80,
        "cost_income_imbalance": 60,
        "recently_blocked_actions": 40,
        "near_future_demand": 20,
        "reader_salience": 0,
    }
    assert resource_pressure(values, CONFIG["resource_pressure"]) == 47
    valid = dict(
        resource_pressure_score=70,
        setup_chapters=8,
        blocked_decisions=2,
        same_type_fatigue=35,
        has_causal_source=True,
        has_paid_cost_or_risk=True,
        has_post_payoff_behavior_change=True,
        next_resource_tier_ready=True,
    )
    assert can_trigger_resource_liberation(**valid)
    assert not can_trigger_resource_liberation(
        **{**valid, "resource_pressure_score": 69}
    )


def test_payoff_cooldown_groups() -> None:
    config = CONFIG["payoff_cooldown"]
    assert not payoff_cooldown_allowed(
        group="small_same_type",
        chapters_since_last=4,
        occurrence_count=2,
        config=config,
    )
    assert payoff_cooldown_allowed(
        group="small_same_type",
        chapters_since_last=5,
        occurrence_count=2,
        config=config,
    )
    assert payoff_cooldown_allowed(
        group="low_tier_resource_liberation",
        chapters_since_last=None,
        occurrence_count=0,
        config=config,
    )
    assert not payoff_cooldown_allowed(
        group="low_tier_resource_liberation",
        chapters_since_last=100,
        occurrence_count=1,
        config=config,
    )
    with pytest.raises(ValueError, match="未知爽点冷却组"):
        payoff_cooldown_allowed(
            group="unknown",
            chapters_since_last=None,
            occurrence_count=0,
            config=config,
        )


def test_repetition_similarity_and_decay_vectors() -> None:
    values = {
        "event_source_similarity": 1,
        "solution_method_similarity": 0,
        "payoff_type_similarity": 1,
        "scene_topology_similarity": 0,
        "emotional_outcome_similarity": 1,
    }
    assert structural_similarity(values, CONFIG["repetition"]) == pytest.approx(0.6)
    score = repetition_fatigue([(0, 1), (12, 0)], CONFIG["repetition"]).score
    assert score == pytest.approx(100 / (1 + math.exp(-1)), rel=1e-6)
    no_history = repetition_fatigue([], CONFIG["repetition"])
    assert no_history.score == 0
    assert "no_history" in no_history.evidence
    with pytest.raises(ValueError):
        repetition_fatigue([(0, 50)], CONFIG["repetition"])


def test_fit_thread_and_candidate_vectors() -> None:
    char_values = dict.fromkeys(CONFIG["character_fit"]["weights"], 0)
    char_values["motivation_alignment"] = 100
    style_values = dict.fromkeys(CONFIG["style_fit"]["weights"], 0)
    style_values["pov_and_tense"] = 100
    assert character_fit(char_values, CONFIG["character_fit"]) == 25
    assert style_fit(style_values, CONFIG["style_fit"]) == 20

    all_thread = dict.fromkeys(CONFIG["thread_need"]["weights"], 100)
    assert thread_need(all_thread, CONFIG["thread_need"]) == 100
    all_thread["narrative_debt"] = 150
    assert thread_need(all_thread, CONFIG["thread_need"]) == 112

    all_candidate = dict.fromkeys(CONFIG["candidate_score"]["weights"], 50)
    assert candidate_score(all_candidate, CONFIG["candidate_score"]) == 40


def test_agency_legibility_and_uncertainty_diagnostics() -> None:
    agency_result = agency(
        {
            "value_balance": 1,
            "consequence_difference": 1,
            "information_adequacy": 1,
            "opportunity_cost": 1,
            "long_term_effect": 1,
        }
    )
    assert agency_result.score == 100
    assert agency({**agency_result.inputs, "long_term_effect": 0}).score == 0
    legibility_result = legibility(
        dict.fromkeys(CONFIG["legibility"]["weights"], 100),
        CONFIG["legibility"],
    )
    uncertainty_result = outcome_uncertainty(
        dict.fromkeys(CONFIG["outcome_uncertainty"]["weights"], 50),
        CONFIG["outcome_uncertainty"],
    )
    assert legibility_result.score == 100
    assert uncertainty_result.score == 50
    assert uncertainty_result.threshold_interpretation == "健康未知度"
