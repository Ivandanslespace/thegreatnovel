"""Innovation reward and multi-horizon portfolio calculations.

The calculator is intentionally deterministic and soft.  Hard continuity
gates are evaluated by ``metrics.gates`` first; this module is only allowed to
order candidates that already passed those gates.  It also never promotes a
preview or a realized trace into Canon.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence

from novel_authoring.planning.innovation import (
    CandidateInnovationPreview,
    CrossHorizonSynergy,
    EarnedRecombination,
    ExpectedNarrativeDebt,
    InnovationControl,
    InnovationElement,
    InnovationFocus,
    InnovationLevel,
    InnovationMagnitude,
    InnovationRewardBreakdown,
    InnovationRewardLine,
    InnovationSynergy,
    InnovationTrace,
    NarrativeDelta,
    NarrativeHorizon,
    NarrativePatternDiagnostic,
    NarrativePayoff,
    NarrativePortfolioSnapshot,
    NoveltyQuality,
    PayoffExtent,
    QuestionBalance,
    SemanticPolicyLeakDiagnostic,
)
from novel_authoring.planning.models import CandidateProposal

LEVEL_MULTIPLIERS: dict[InnovationLevel, float] = {
    InnovationLevel.MINIMAL: 0.35,
    InnovationLevel.LOW: 0.65,
    InnovationLevel.MEDIUM: 1.0,
    InnovationLevel.HIGH: 1.35,
    InnovationLevel.BOLD: 1.70,
}

LEVEL_REWARD_CAPS: dict[InnovationLevel, float] = {
    InnovationLevel.MINIMAL: 6,
    InnovationLevel.LOW: 12,
    InnovationLevel.MEDIUM: 24,
    InnovationLevel.HIGH: 36,
    InnovationLevel.BOLD: 50,
}

MAGNITUDE_REWARDS: dict[InnovationMagnitude, float] = {
    InnovationMagnitude.LOCAL: 4,
    InnovationMagnitude.SUBSTANTIAL: 7,
    InnovationMagnitude.MAJOR: 11,
}

EARNED_RECOMBINATION_REWARDS: dict[InnovationMagnitude, float] = {
    InnovationMagnitude.LOCAL: 3,
    InnovationMagnitude.SUBSTANTIAL: 6,
    InnovationMagnitude.MAJOR: 9,
}

PAYOFF_REWARDS: dict[NarrativeHorizon, float] = {
    NarrativeHorizon.SHORT: 4,
    NarrativeHorizon.MID: 7,
    NarrativeHorizon.LONG: 10,
}

_DIMINISHING_RETURNS = (1.0, 0.6, 0.3, 0.0)


def question_balance(delta: NarrativeDelta | None) -> QuestionBalance:
    """Count answered, advanced and opened questions without judging prose."""

    if delta is None:
        return QuestionBalance()
    answered = len(delta.questions_answered)
    partial = len(delta.questions_partially_paid)
    advanced = len(delta.questions_materially_advanced)
    opened = len(delta.new_questions_opened)
    over_deferred = answered == 0 and partial == 0 and advanced == 0 and opened >= 2
    return QuestionBalance(
        answered=answered,
        partially_paid=partial,
        materially_advanced=advanced,
        newly_opened=opened,
        over_deferred=over_deferred,
        penalty=4 if over_deferred else 0,
    )


def detect_semantic_policy_leak(prose: str) -> SemanticPolicyLeakDiagnostic:
    """Detect repeated governance-shaped reasoning as a soft prose signal.

    The patterns are semantic combinations rather than a fixed blacklist of
    exact sentences.  A single cautious line is normal fiction; repetition of
    policy-shaped deferral is what receives a warning.
    """

    rules = {
        "deferred_confirmation": re.compile(
            r"(?:暂不|先不|不急于|保留|等待)[^。！？\n]{0,24}(?:确认|验证|结论|答案|行动)"
        ),
        "evidence_governance": re.compile(
            r"(?:必须|只能|不得|允许)[^。！？\n]{0,24}(?:确认|进入|行动|记录|验证|结论)"
        ),
        "unknown_as_policy": re.compile(
            r"(?:未知|不确定|尚未确认|无法判断)[^。！？\n]{0,24}(?:因此|所以|只能|暂不|先不|不得)"
        ),
    }
    matches: list[tuple[str, str]] = []
    for category, pattern in rules.items():
        matches.extend((category, match.group(0)) for match in pattern.finditer(prose))
    categories = sorted({category for category, _match in matches})
    repeated_count = len(matches)
    leaked = repeated_count >= 2 and len(categories) >= 1
    return SemanticPolicyLeakDiagnostic(
        status="SEMANTIC_POLICY_LEAK" if leaked else "CLEAR",
        categories=categories,
        evidence=[match for _category, match in matches[:6]],
        repeated_count=repeated_count,
        penalty=min(8, repeated_count * 2) if leaked else 0,
    )


def detect_pattern_repetition(
    candidate_metadata: Mapping[str, object],
    recent_structures: Sequence[Mapping[str, object]] = (),
) -> NarrativePatternDiagnostic:
    """Compare chapter function/topology/questions, not just surface names."""

    primary_function = str(candidate_metadata.get("primary_function", ""))
    scene_topology = str(candidate_metadata.get("scene_topology", ""))
    ending_mode = str(
        candidate_metadata.get("ending_mode", candidate_metadata.get("ending_state", ""))
    )
    question_payoff = "|".join(
        (
            str(candidate_metadata.get("reader_question", "")),
            str(candidate_metadata.get("promises_to_advance", "")),
            str(candidate_metadata.get("promises_to_pay", "")),
        )
    )
    risk_resolution = "|".join(
        (
            str(candidate_metadata.get("risk_form", "")),
            str(candidate_metadata.get("solution_method", "")),
        )
    )
    exact_matches: list[str] = []
    partial_matches: list[str] = []
    for item in recent_structures:
        same_function = (
            primary_function
            and str(item.get("primary_function", "")) == primary_function
        )
        same_topology = (
            scene_topology
            and str(item.get("scene_topology", "")) == scene_topology
        )
        same_ending = (
            ending_mode
            and str(item.get("ending_mode", item.get("ending_state", "")))
            == ending_mode
        )
        if same_function and same_topology and same_ending:
            exact_matches.append("primary_function + scene_topology + ending_mode")
        elif sum(bool(value) for value in (same_function, same_topology, same_ending)) >= 2:
            partial_matches.append("two of primary_function/scene_topology/ending_mode")
    repeated = bool(exact_matches or len(partial_matches) >= 2)
    penalty = 4 if exact_matches else 2 if len(partial_matches) >= 2 else 0
    return NarrativePatternDiagnostic(
        repeated=repeated,
        primary_function=primary_function,
        scene_topology=scene_topology,
        ending_mode=ending_mode,
        question_payoff_pattern=question_payoff,
        risk_resolution_pattern=risk_resolution,
        evidence=[*exact_matches[:2], *partial_matches[:2]],
        penalty=penalty,
    )


def _synergy_reward(size: int) -> float:
    if size >= 4:
        return 16
    if size == 3:
        return 10
    if size == 2:
        return 5
    return 0


def _meaningful_elements(elements: Sequence[InnovationElement]) -> list[InnovationElement]:
    return [
        element
        for element in elements
        if element.novelty_type is NoveltyQuality.MEANINGFUL_NOVELTY
    ]


def _valid_synergy(
    synergy: InnovationSynergy,
    element_ids: set[str],
) -> bool:
    return (
        len(synergy.element_ids) >= 2
        and set(synergy.element_ids).issubset(element_ids)
        and bool(synergy.causal_link.strip())
        and bool(synergy.joint_state_change.strip())
        and bool(synergy.future_option_effect.strip())
    )


def _valid_cross_horizon_synergy(
    synergy: CrossHorizonSynergy,
    element_ids: set[str],
) -> bool:
    return (
        len(synergy.horizons) >= 2
        and set(synergy.element_ids).issubset(element_ids)
        and bool(synergy.causal_link.strip())
        and bool(synergy.joint_state_change.strip())
        and bool(synergy.future_option_effect.strip())
    )


def _new_debt_cost(debt: ExpectedNarrativeDebt) -> float:
    if debt.horizon is NarrativeHorizon.SHORT:
        return 1 if debt.magnitude is InnovationMagnitude.LOCAL else 2
    if debt.horizon is NarrativeHorizon.MID:
        return 1 if debt.magnitude is InnovationMagnitude.LOCAL else 2
    return 0 if debt.magnitude is InnovationMagnitude.LOCAL else 1


def _payoff_reward(payoff: NarrativePayoff) -> float:
    value = PAYOFF_REWARDS[payoff.horizon]
    return value if payoff.extent is PayoffExtent.FULL else value / 2


def _answer_and_expand_reward(
    payoffs: Sequence[NarrativePayoff],
    elements: Sequence[InnovationElement],
    delta: NarrativeDelta | None,
) -> float:
    resolved = {
        payoff.horizon for payoff in payoffs if payoff.extent is PayoffExtent.FULL
    }
    advanced = {
        payoff.horizon for payoff in payoffs if payoff.extent is PayoffExtent.PARTIAL
    }
    if delta is not None:
        if delta.questions_answered:
            resolved.add(NarrativeHorizon.SHORT)
        if delta.questions_partially_paid:
            advanced.add(NarrativeHorizon.SHORT)
        if delta.questions_materially_advanced:
            advanced.add(NarrativeHorizon.MID)
    horizon_roles = {
        horizon
        for element in elements
        for horizon in element.horizon_roles
    }
    if (
        NarrativeHorizon.LONG in horizon_roles
        and NarrativeHorizon.LONG in resolved.union(advanced)
        and NarrativeHorizon.SHORT in resolved
        and NarrativeHorizon.MID in resolved.union(advanced)
    ):
        return 12
    if NarrativeHorizon.MID in resolved and NarrativeHorizon.LONG in horizon_roles:
        return 8
    if (
        NarrativeHorizon.SHORT in resolved
        and NarrativeHorizon.MID in advanced.union(horizon_roles)
    ):
        return 5
    return 0


def calculate_innovation_reward(
    preview: CandidateInnovationPreview | None,
    control: InnovationControl,
    *,
    base_candidate_score: float,
    portfolio: NarrativePortfolioSnapshot | None = None,
    recent_structures: Sequence[Mapping[str, object]] = (),
    candidate_metadata: Mapping[str, object] | None = None,
    eligible: bool = True,
    ineligibility_reasons: Sequence[str] = (),
) -> InnovationRewardBreakdown:
    """Calculate expected or realized reward for one already-gated plan."""

    preview = preview or CandidateInnovationPreview(
        creative_distance=control.level,
        primary_directions=[InnovationFocus.AUTO],
        main_innovations=["未提供结构化创新元素"],
    )
    elements = list(preview.expected_innovation_elements)
    meaningful = _meaningful_elements(elements)
    meaningful_ids = {element.element_id for element in meaningful}
    per_focus_count: defaultdict[InnovationFocus, int] = defaultdict(int)
    element_rewards: list[InnovationRewardLine] = []
    raw_element_reward = 0.0
    orphan_penalty = 0.0
    cosmetic_penalty = 0.0
    for element in elements:
        if element.novelty_type is NoveltyQuality.COSMETIC_NOVELTY:
            cosmetic_penalty += 0.5
            continue
        rank = per_focus_count[element.focus]
        per_focus_count[element.focus] += 1
        factor = _DIMINISHING_RETURNS[min(rank, len(_DIMINISHING_RETURNS) - 1)]
        reward = MAGNITUDE_REWARDS[element.magnitude] * factor
        if reward:
            element_rewards.append(
                InnovationRewardLine(
                    item_id=element.element_id,
                    reward=reward,
                    reason=(
                        f"{element.focus.value} {element.magnitude.value}，"
                        f"同方向第 {rank + 1} 项递减系数 {factor:g}"
                    ),
                )
            )
        raw_element_reward += reward
        if (
            not element.causal_source.strip()
            or not element.evidence_or_forward_introduction.strip()
        ):
            orphan_penalty += 2

    element_synergies: list[InnovationSynergy] = []
    element_synergy_reward = 0.0
    for element_synergy in preview.expected_element_synergies:
        reward = (
            _synergy_reward(len(element_synergy.element_ids))
            if _valid_synergy(element_synergy, meaningful_ids)
            else 0
        )
        if reward:
            element_synergy_reward += reward
            element_synergies.append(
                element_synergy.model_copy(update={"reward": reward})
            )
        else:
            element_synergies.append(element_synergy.model_copy(update={"reward": 0}))

    cross_horizon_synergies: list[CrossHorizonSynergy] = []
    cross_horizon_reward = 0.0
    for cross_synergy in preview.expected_cross_horizon_synergies:
        reward = (
            _synergy_reward(len(cross_synergy.horizons))
            if _valid_cross_horizon_synergy(cross_synergy, meaningful_ids)
            else 0
        )
        cross_horizon_reward += reward
        cross_horizon_synergies.append(
            cross_synergy.model_copy(update={"reward": reward})
        )

    earned_recombinations: list[EarnedRecombination] = []
    earned_recombination_reward = 0.0
    for recombination in preview.expected_earned_recombinations:
        valid = bool(
            recombination.earned_asset_ids
            and recombination.new_strategy.strip()
            and recombination.causal_source.strip()
        )
        reward = EARNED_RECOMBINATION_REWARDS[recombination.magnitude] if valid else 0
        earned_recombination_reward += reward
        earned_recombinations.append(recombination.model_copy(update={"reward": reward}))

    payoffs = list(preview.expected_payoffs)
    payoff_reward = sum(_payoff_reward(payoff) for payoff in payoffs)
    delta = preview.expected_narrative_delta
    answer_and_expand_reward = _answer_and_expand_reward(payoffs, meaningful, delta)

    focus_alignment_reward = 0.0
    if not control.uses_auto_focus:
        realized_focuses = {element.focus for element in meaningful}
        focus_alignment_reward = min(
            6,
            3 * len(realized_focuses.intersection(set(control.focus))),
        )

    new_narrative_debt_cost = sum(_new_debt_cost(debt) for debt in preview.expected_new_debts)
    overdue_debt_penalty = 0.0
    if portfolio is not None and portfolio.overdue_debt_ids:
        paid_ids = {payoff.debt_id for payoff in payoffs if payoff.debt_id}
        overdue_debt_penalty = float(
            2 * len(set(portfolio.overdue_debt_ids).difference(paid_ids))
        )
    if portfolio is not None and portfolio.payoff_ready_thread_ids and not payoffs:
        overdue_debt_penalty += float(3 * len(portfolio.payoff_ready_thread_ids))

    integration_cost_penalty = {
        "low": 0.0,
        "medium": 1.0,
        "high": 3.0,
    }[preview.integration_cost.value]
    pattern = detect_pattern_repetition(candidate_metadata or {}, recent_structures)
    balance = question_balance(delta)
    over_deferral_penalty = balance.penalty
    if portfolio is not None and portfolio.consecutive_deferrals >= 2:
        if balance.answered == balance.partially_paid == balance.materially_advanced == 0:
            over_deferral_penalty = max(over_deferral_penalty, 8)
    elif (
        portfolio is not None
        and portfolio.consecutive_deferrals >= 1
        and balance.answered == balance.partially_paid == balance.materially_advanced == 0
    ):
        over_deferral_penalty = max(over_deferral_penalty, 4)

    raw_innovation_reward = (
        raw_element_reward
        + element_synergy_reward
        + cross_horizon_reward
        + earned_recombination_reward
        + payoff_reward
        + answer_and_expand_reward
        + focus_alignment_reward
    )
    multiplier = LEVEL_MULTIPLIERS[control.level]
    reward_cap = LEVEL_REWARD_CAPS[control.level]
    scaled = raw_innovation_reward * multiplier
    capped = min(reward_cap, scaled)
    penalties = (
        new_narrative_debt_cost
        + overdue_debt_penalty
        + integration_cost_penalty
        + cosmetic_penalty
        + orphan_penalty
        + pattern.penalty
        + over_deferral_penalty
    )
    final = base_candidate_score + capped - penalties if eligible else 0.0
    return InnovationRewardBreakdown(
        requested_level=control.level,
        level_multiplier=multiplier,
        reward_cap=reward_cap,
        innovation_elements=elements,
        element_rewards=element_rewards,
        element_synergies=element_synergies,
        element_synergy_reward=element_synergy_reward,
        cross_horizon_synergies=cross_horizon_synergies,
        cross_horizon_reward=cross_horizon_reward,
        earned_recombinations=earned_recombinations,
        earned_recombination_reward=earned_recombination_reward,
        payoffs=payoffs,
        payoff_reward=payoff_reward,
        answer_and_expand_reward=answer_and_expand_reward,
        focus_alignment_reward=focus_alignment_reward,
        new_narrative_debt_cost=new_narrative_debt_cost,
        overdue_debt_penalty=overdue_debt_penalty,
        integration_cost_penalty=integration_cost_penalty,
        cosmetic_penalty=cosmetic_penalty,
        orphan_penalty=orphan_penalty,
        repetition_penalty=pattern.penalty,
        over_deferral_penalty=over_deferral_penalty,
        raw_innovation_reward=raw_innovation_reward,
        scaled_innovation_reward=scaled,
        capped_innovation_reward=capped if eligible else 0,
        base_candidate_score=base_candidate_score,
        final_selection_score=final,
        question_balance=balance,
        narrative_delta=delta,
        eligible=eligible,
        ineligibility_reasons=list(ineligibility_reasons),
    )


def calculate_candidate_innovation_reward(
    candidate: CandidateProposal,
    control: InnovationControl,
    *,
    base_candidate_score: float,
    portfolio: NarrativePortfolioSnapshot | None = None,
    recent_structures: Sequence[Mapping[str, object]] = (),
    eligible: bool = True,
    ineligibility_reasons: Sequence[str] = (),
) -> InnovationRewardBreakdown:
    return calculate_innovation_reward(
        candidate.innovation_preview,
        control,
        base_candidate_score=base_candidate_score,
        portfolio=portfolio,
        recent_structures=recent_structures,
        candidate_metadata=candidate.model_dump(mode="json"),
        eligible=eligible,
        ineligibility_reasons=ineligibility_reasons,
    )


def calculate_realized_innovation_reward(
    trace: InnovationTrace,
    control: InnovationControl,
    *,
    base_candidate_score: float = 0,
    portfolio: NarrativePortfolioSnapshot | None = None,
    recent_structures: Sequence[Mapping[str, object]] = (),
) -> InnovationRewardBreakdown:
    """Apply the same calculator to a post-draft realized trace."""

    meaningful = any(
        item.novelty_type is NoveltyQuality.MEANINGFUL_NOVELTY
        for item in trace.realized_elements
    )
    preview = CandidateInnovationPreview(
        creative_distance=trace.realized_level or trace.requested_level,
        primary_directions=trace.realized_directions or [InnovationFocus.AUTO],
        main_innovations=trace.meaningful_state_changes or ["未记录 realized state change"],
        future_options_opened=trace.future_options_opened,
        integration_cost=trace.integration_cost,
        novelty_quality=(
            NoveltyQuality.MEANINGFUL_NOVELTY
            if meaningful
            else NoveltyQuality.COSMETIC_NOVELTY
        ),
        expected_innovation_elements=trace.realized_elements,
        expected_element_synergies=trace.realized_synergies,
        expected_payoffs=trace.realized_payoffs,
        expected_narrative_delta=trace.realized_narrative_delta,
        expected_new_debts=[
            ExpectedNarrativeDebt(
                debt_id=debt.debt_id,
                question_or_promise=debt.question_or_promise,
                horizon=debt.horizon,
                source_event=debt.source_event,
                expected_payoff_window=debt.expected_payoff_window,
            )
            for debt in trace.realized_new_debt
        ],
    )
    return calculate_innovation_reward(
        preview,
        control,
        base_candidate_score=base_candidate_score,
        portfolio=portfolio,
        recent_structures=recent_structures,
        candidate_metadata={
            "primary_function": "",
            "scene_topology": "",
            "ending_state": "",
        },
    )


__all__ = [
    "EARNED_RECOMBINATION_REWARDS",
    "LEVEL_MULTIPLIERS",
    "LEVEL_REWARD_CAPS",
    "MAGNITUDE_REWARDS",
    "PAYOFF_REWARDS",
    "calculate_candidate_innovation_reward",
    "calculate_innovation_reward",
    "calculate_realized_innovation_reward",
    "detect_pattern_repetition",
    "detect_semantic_policy_leak",
    "question_balance",
]
