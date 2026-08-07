from __future__ import annotations

import pytest

from novel_authoring.planning.diagnostics import build_narrative_portfolio_snapshot
from novel_authoring.planning.innovation import (
    CandidateInnovationPreview,
    CrossHorizonSynergy,
    ExpectedNarrativeDebt,
    InnovationControl,
    InnovationElement,
    InnovationFocus,
    InnovationLevel,
    InnovationMagnitude,
    InnovationSynergy,
    NarrativeDebtStatus,
    NarrativeDelta,
    NarrativeHorizon,
    NarrativePayoff,
    NarrativePortfolioSnapshot,
    NarrativeThreadLifecycle,
    PayoffExtent,
)
from novel_authoring.planning.rewards import (
    calculate_innovation_reward,
    detect_semantic_policy_leak,
)


def _element(
    element_id: str,
    focus: InnovationFocus,
    *,
    magnitude: InnovationMagnitude = InnovationMagnitude.LOCAL,
    horizons: list[NarrativeHorizon] | None = None,
) -> InnovationElement:
    return InnovationElement(
        element_id=element_id,
        focus=focus,
        description=f"meaningful {element_id}",
        magnitude=magnitude,
        causal_source="当前章节已发生的选择",
        state_before="旧状态",
        state_after_if_realized="新状态",
        future_options_opened=[f"future-{element_id}"],
        horizon_roles=horizons or [NarrativeHorizon.SHORT],
        evidence_or_forward_introduction="本章前向引入",
    )


def _preview(
    elements: list[InnovationElement],
    *,
    synergies: list[InnovationSynergy] | None = None,
    cross: list[CrossHorizonSynergy] | None = None,
    payoffs: list[NarrativePayoff] | None = None,
    delta: NarrativeDelta | None = None,
    debts: list[ExpectedNarrativeDebt] | None = None,
) -> CandidateInnovationPreview:
    return CandidateInnovationPreview(
        creative_distance=InnovationLevel.MEDIUM,
        primary_directions=[InnovationFocus.PLOT],
        main_innovations=[element.description for element in elements] or ["没有创新"],
        expected_innovation_elements=elements,
        expected_element_synergies=synergies or [],
        expected_cross_horizon_synergies=cross or [],
        expected_payoffs=payoffs or [],
        expected_new_debts=debts or [],
        expected_narrative_delta=delta,
    )


def _reward(
    preview: CandidateInnovationPreview,
    *,
    level: InnovationLevel = InnovationLevel.MEDIUM,
    base: float = 50,
    portfolio: NarrativePortfolioSnapshot | None = None,
):
    return calculate_innovation_reward(
        preview,
        InnovationControl(level=level),
        base_candidate_score=base,
        portfolio=portfolio,
    )


def test_same_focus_elements_have_diminishing_main_reward() -> None:
    preview = _preview(
        [
            _element("e1", InnovationFocus.PLOT),
            _element("e2", InnovationFocus.PLOT),
            _element("e3", InnovationFocus.PLOT),
            _element("e4", InnovationFocus.PLOT),
        ]
    )
    result = _reward(preview)

    assert [line.reward for line in result.element_rewards] == [4, 2.4, 1.2]
    assert result.raw_innovation_reward == pytest.approx(7.6)


def test_level_multiplier_and_cap_increase_without_relaxing_gates() -> None:
    preview = _preview(
        [
            _element("plot", InnovationFocus.PLOT, magnitude=InnovationMagnitude.MAJOR),
            _element("world", InnovationFocus.WORLD, magnitude=InnovationMagnitude.MAJOR),
        ]
    )
    values = [
        _reward(preview, level=level).capped_innovation_reward
        for level in (
            InnovationLevel.MINIMAL,
            InnovationLevel.LOW,
            InnovationLevel.MEDIUM,
            InnovationLevel.HIGH,
            InnovationLevel.BOLD,
        )
    ]

    assert values == sorted(values)
    assert values[0] < values[-1]


def test_related_elements_get_synergy_but_unrelated_ids_get_zero() -> None:
    elements = [_element("plot", InnovationFocus.PLOT), _element("world", InnovationFocus.WORLD)]
    related = InnovationSynergy(
        synergy_id="s-related",
        element_ids=["plot", "world"],
        focuses=[InnovationFocus.PLOT, InnovationFocus.WORLD],
        causal_link="同一个选择暴露了新地点",
        joint_state_change="行动路线被迫改变",
        future_option_effect="交易或冲突都成为可能",
    )
    unrelated = InnovationSynergy(
        synergy_id="s-unrelated",
        element_ids=["missing-a", "missing-b"],
        focuses=[InnovationFocus.PLOT, InnovationFocus.WORLD],
        causal_link="没有共同原因",
        joint_state_change="没有共同状态变化",
        future_option_effect="没有共同后果",
    )
    result = _reward(_preview(elements, synergies=[related, unrelated]))

    assert result.element_synergy_reward == 5
    assert [item.reward for item in result.element_synergies] == [5, 0]


def test_cross_horizon_and_answer_expand_reward_are_separate() -> None:
    elements = [
        _element("short", InnovationFocus.PLOT, horizons=[NarrativeHorizon.SHORT]),
        _element(
            "mid",
            InnovationFocus.RELATIONSHIP,
            horizons=[NarrativeHorizon.MID, NarrativeHorizon.LONG],
        ),
    ]
    cross = CrossHorizonSynergy(
        synergy_id="cross",
        element_ids=["short", "mid"],
        horizons=[NarrativeHorizon.SHORT, NarrativeHorizon.MID, NarrativeHorizon.LONG],
        causal_link="短期交易改变中期联盟，并留下长期路线",
        joint_state_change="主角失去旧的安全选择",
        future_option_effect="联盟、追索和远行同时打开",
    )
    delta = NarrativeDelta(
        state_before="无人回应",
        state_after="交易完成但路线改变",
        description="短问题得到回答，新的中期问题出现",
        meaningful=True,
        questions_answered=["谁会回应"],
        questions_materially_advanced=["联盟是否成立"],
        new_questions_opened=["谁在追踪交易"],
    )
    result = _reward(
        _preview(
            elements,
            cross=[cross],
            payoffs=[
                NarrativePayoff(
                    payoff_id="short-payoff",
                    description="回应出现",
                    horizon=NarrativeHorizon.SHORT,
                    extent=PayoffExtent.FULL,
                )
            ],
            delta=delta,
        )
    )

    assert result.cross_horizon_reward == 10
    assert result.payoff_reward == 4
    assert result.answer_and_expand_reward == 5


def test_new_debt_and_pure_deferral_are_penalized() -> None:
    delta = NarrativeDelta(
        state_before="旧问题未推进",
        state_after="又出现两个问题",
        description="只增加悬念",
        new_questions_opened=["q1", "q2"],
    )
    preview = _preview(
        [],
        delta=delta,
        debts=[
            ExpectedNarrativeDebt(
                debt_id="d1",
                question_or_promise="短期问题",
                horizon=NarrativeHorizon.SHORT,
                source_event="新发现",
                expected_payoff_window="1-3 chapters",
            )
        ],
    )
    result = _reward(preview, base=60)

    assert result.raw_innovation_reward == 0
    assert result.new_narrative_debt_cost == 1
    assert result.over_deferral_penalty == 4
    assert result.final_selection_score < 60


def test_payoff_ready_thread_cannot_be_deferred_for_free() -> None:
    portfolio = NarrativePortfolioSnapshot(
        snapshot_id="p",
        current_chapter=20,
        payoff_ready_thread_ids=["thread-ready"],
    )
    result = _reward(_preview([]), portfolio=portfolio, base=60)

    assert result.overdue_debt_penalty == 3
    assert result.final_selection_score == 57


def test_bold_without_meaningful_novelty_has_no_reward_bonus() -> None:
    result = _reward(_preview([]), level=InnovationLevel.BOLD, base=70)

    assert result.capped_innovation_reward == 0
    assert result.final_selection_score == 70


def test_high_innovation_can_beat_safe_high_base_only_after_gate() -> None:
    safe = _reward(_preview([]), base=90)
    elements = [
        _element("plot", InnovationFocus.PLOT, magnitude=InnovationMagnitude.SUBSTANTIAL),
        _element("world", InnovationFocus.WORLD, magnitude=InnovationMagnitude.SUBSTANTIAL),
        _element(
            "relation",
            InnovationFocus.RELATIONSHIP,
            magnitude=InnovationMagnitude.SUBSTANTIAL,
        ),
    ]
    synergy = InnovationSynergy(
        synergy_id="three-way",
        element_ids=["plot", "world", "relation"],
        focuses=[InnovationFocus.PLOT, InnovationFocus.WORLD, InnovationFocus.RELATIONSHIP],
        causal_link="一个选择同时改写三者关系",
        joint_state_change="未来路线被重新分叉",
        future_option_effect="打开联盟、冲突和探索三种后续",
    )
    innovative = _reward(
        _preview(elements, synergies=[synergy]),
        base=82,
    )

    assert innovative.final_selection_score > safe.final_selection_score
    ineligible = calculate_innovation_reward(
        _preview(elements, synergies=[synergy]),
        InnovationControl(level=InnovationLevel.BOLD),
        base_candidate_score=99,
        eligible=False,
        ineligibility_reasons=["timeline conflict"],
    )
    assert ineligible.final_selection_score == 0
    assert ineligible.capped_innovation_reward == 0


def test_portfolio_freezes_lifecycle_horizon_and_overdue_debt() -> None:
    snapshot = build_narrative_portfolio_snapshot(
        active_threads=[
            {
                "thread_id": "t-short",
                "goal": "找到回应",
                "phase": "payoff_ready",
                "introduced_chapter": 18,
                "last_advanced_chapter": 20,
                "target_max_age": 3,
            }
        ],
        promises={
            "p-overdue": {
                "thread_id": "t-short",
                "statement": "旧承诺",
                "introduced_ordinal": 1,
                "target_max_age": 3,
                "progress": 0.2,
            }
        },
        current_chapter=20,
        snapshot_id="portfolio-test",
    )

    assert snapshot.short_threads[0].lifecycle is NarrativeThreadLifecycle.PAYOFF_READY
    assert snapshot.narrative_debts[0].status is NarrativeDebtStatus.OVERDUE
    assert snapshot.overdue_debt_ids == ["p-overdue"]


def test_semantic_policy_leak_is_soft_and_requires_repetition() -> None:
    clear = detect_semantic_policy_leak("他停了一下，仍不知道门后是什么。")
    leaked = detect_semantic_policy_leak(
        "未知，所以暂不确认。线索不确定，因此先不行动。"
    )

    assert clear.status == "CLEAR"
    assert leaked.status == "SEMANTIC_POLICY_LEAK"
    assert leaked.penalty > 0
