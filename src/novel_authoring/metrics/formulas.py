from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from novel_authoring.domain.models import MetricResult


def clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def _validate_number(name: str, value: float, low: float, high: float) -> None:
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} 必须在 {low}—{high}，实际为 {value}")


def _validate_scores(values: Mapping[str, float], *, high: float = 100) -> None:
    for name, value in values.items():
        _validate_number(name, value, 0, high)


def _weighted(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    missing = set(weights) - set(values)
    extra = set(values) - set(weights)
    if missing or extra:
        raise ValueError(f"指标字段不匹配；缺少={sorted(missing)}，多余={sorted(extra)}")
    return sum(values[name] * weight for name, weight in weights.items())


def pressure(values: Mapping[str, float], config: Mapping[str, Any]) -> MetricResult:
    _validate_scores(values)
    score = _weighted(values, config["weights"])
    if score <= 30:
        interpretation, action = "低压", "允许恢复、关系或探索，但检查长期进展"
    elif score <= 55:
        interpretation, action = "正常推进", "保持当前压力曲线"
    elif score <= 75:
        interpretation, action = "明显紧张", "安排决定、代价或局部兑现"
    elif score <= 90:
        interpretation, action = "高潮准备区", "检查成熟爽点或关键反转"
    else:
        interpretation, action = "极端压力", "不得长期维持，准备局部控制或兑现"
    return MetricResult(
        metric="Pressure",
        score=score,
        inputs=dict(values),
        threshold_interpretation=interpretation,
        recommended_action=action,
    )


def global_pressure(weighted_pressures: Sequence[tuple[float, float]]) -> float | None:
    for salience, score in weighted_pressures:
        if salience < 0:
            raise ValueError("Salience 不得为负")
        _validate_number("thread_pressure", score, 0, 100)
    denominator = sum(salience for salience, _ in weighted_pressures)
    if denominator == 0:
        return None
    return sum(salience * score for salience, score in weighted_pressures) / denominator


def narrative_debt(
    *,
    importance: float,
    reader_visibility: float,
    promise_progress: float,
    age_chapters: int,
    target_max_age: int,
    reminder_count: int,
    config: Mapping[str, Any],
) -> MetricResult:
    for name, value in (
        ("importance", importance),
        ("reader_visibility", reader_visibility),
        ("promise_progress", promise_progress),
    ):
        _validate_number(name, value, 0, 1)
    if age_chapters < 0 or reminder_count < 0 or target_max_age <= 0:
        raise ValueError("Age、ReminderCount 必须非负，TargetMaxAge 必须大于 0")
    age_ratio = clamp(0, float(config["age_ratio_cap"]), age_chapters / target_max_age)
    reminder_factor = 1 + float(config["reminder_step"]) * min(
        reminder_count, int(config["reminder_cap"])
    )
    raw = (
        100
        * importance
        * reader_visibility
        * (1 - promise_progress) ** float(config["progress_exponent"])
        * age_ratio
        * reminder_factor
    )
    score = clamp(0, float(config["debt_cap"]), raw)
    if score < 40:
        interpretation, action = "健康", "无需优先处理"
    elif score < 80:
        interpretation, action = "应在近期推进", "安排一次实质推进"
    elif score < 110:
        interpretation, action = "高债务", "三章内至少明显推进"
    elif score < 130:
        interpretation, action = "严重债务", "暂停堆叠同等级新承诺"
    else:
        interpretation, action = "债务过载", "兑现、明确重构或经作者批准延后"
    return MetricResult(
        metric="Narrative Debt",
        score=score,
        inputs={
            "importance": importance,
            "reader_visibility": reader_visibility,
            "promise_progress": promise_progress,
            "age_chapters": age_chapters,
            "target_max_age": target_max_age,
            "reminder_count": reminder_count,
            "age_ratio": age_ratio,
            "reminder_factor": reminder_factor,
        },
        threshold_interpretation=interpretation,
        recommended_action=action,
    )


def hook_load_allowed(
    new_hook_load: float,
    full_payoff_count: int,
    partial_advance_count: int,
    genre_allowance: float,
) -> bool:
    if min(new_hook_load, full_payoff_count, partial_advance_count, genre_allowance) < 0:
        raise ValueError("Hook load 输入不得为负")
    return new_hook_load <= full_payoff_count + 0.6 * partial_advance_count + genre_allowance


def progress(values: Mapping[str, float], config: Mapping[str, Any]) -> MetricResult:
    _validate_scores(values)
    score = _weighted(values, config["weights"])
    if score < 10:
        interpretation, action = "低进展", "必须说明恢复、塑造或准备功能"
    elif score < 25:
        interpretation, action = "局部进展", "检查近期是否已有不可逆变化"
    else:
        interpretation, action = "有效不可逆进展", "记录状态变化及来源"
    return MetricResult(
        metric="Progress",
        score=score,
        inputs=dict(values),
        threshold_interpretation=interpretation,
        recommended_action=action,
    )


def stagnation_rate(scores: Sequence[float], config: Mapping[str, Any]) -> float | None:
    window = int(config["stagnation_window"])
    if len(scores) < window:
        return None
    recent = list(scores[-window:])
    _validate_scores({str(index): value for index, value in enumerate(recent)})
    low = sum(value < float(config["low_progress_cutoff"]) for value in recent)
    return low / window * 100


def waiting_readiness(age: int, target_min_age: int) -> float:
    if age < 0 or target_min_age <= 0:
        raise ValueError("Age 必须非负，TargetMinAge 必须大于 0")
    return min(100, 100 * age / target_min_age)


def payoff_component(
    values: Mapping[str, float], weights: Mapping[str, float]
) -> float:
    _validate_scores(values)
    return _weighted(values, weights)


def payoff_score(
    *,
    maturity: float,
    impact: float,
    causality: float,
    after_value: float,
    repetition_fatigue_score: float,
    structural_fit: float,
    future_damage: float,
    config: Mapping[str, Any],
) -> MetricResult:
    values = {
        "maturity": maturity,
        "impact": impact,
        "novelty": 100 - repetition_fatigue_score,
        "causality": causality,
        "after_value": after_value,
        "structural_fit": structural_fit,
        "repetition_fatigue": repetition_fatigue_score,
        "future_damage": future_damage,
    }
    _validate_scores(values)
    score = clamp(0, 100, _weighted(values, config["score_weights"]))
    if score < 50:
        interpretation, action = "尚不适合大兑现", "继续铺垫或修改方案"
    elif score < 65:
        interpretation, action = "小型兑现窗口", "局部回答或小奖励"
    elif score < 80:
        interpretation, action = "中型爽点窗口", "检查来源、代价和行为变化"
    elif score <= 90:
        interpretation, action = "阶段性大爆发窗口", "通过硬门后可进入候选"
    else:
        interpretation, action = "篇章高潮级", "仅用于重大反转或世界性质变化"
    return MetricResult(
        metric="Payoff",
        score=score,
        inputs=values,
        threshold_interpretation=interpretation,
        recommended_action=action,
    )


def resource_pressure(values: Mapping[str, float], config: Mapping[str, Any]) -> float:
    _validate_scores(values)
    return _weighted(values, config["weights"])


def resource_scale(
    reward_amount: float,
    average_chapter_cost: float,
    recent_normal_income: float,
    epsilon: float,
) -> tuple[float, float]:
    if reward_amount < 0 or average_chapter_cost < 0 or recent_normal_income < 0:
        raise ValueError("资源尺度输入不得为负")
    if epsilon <= 0:
        raise ValueError("epsilon 必须大于 0")
    return (
        reward_amount / max(average_chapter_cost, epsilon),
        reward_amount / max(recent_normal_income, epsilon),
    )


def can_trigger_resource_liberation(
    *,
    resource_pressure_score: float,
    setup_chapters: int,
    blocked_decisions: int,
    same_type_fatigue: float,
    has_causal_source: bool,
    has_paid_cost_or_risk: bool,
    has_post_payoff_behavior_change: bool,
    next_resource_tier_ready: bool,
) -> bool:
    _validate_number("resource_pressure", resource_pressure_score, 0, 100)
    _validate_number("same_type_fatigue", same_type_fatigue, 0, 100)
    if setup_chapters < 0 or blocked_decisions < 0:
        raise ValueError("章节数与受阻决策数不得为负")
    return (
        resource_pressure_score >= 70
        and setup_chapters >= 8
        and blocked_decisions >= 2
        and same_type_fatigue <= 35
        and has_causal_source
        and has_paid_cost_or_risk
        and has_post_payoff_behavior_change
        and next_resource_tier_ready
    )


def payoff_cooldown_allowed(
    *,
    group: str,
    chapters_since_last: int | None,
    occurrence_count: int,
    config: Mapping[str, Any],
) -> bool:
    """Apply Constitution section 19 cooldown references as a deterministic gate."""
    if occurrence_count < 0:
        raise ValueError("occurrence_count 不得为负")
    if chapters_since_last is not None and chapters_since_last < 0:
        raise ValueError("chapters_since_last 不得为负")
    groups = config.get("groups")
    if not isinstance(groups, Mapping) or group not in groups:
        raise ValueError(f"未知爽点冷却组：{group}")
    group_config = groups[group]
    if not isinstance(group_config, Mapping):
        raise ValueError(f"爽点冷却组配置无效：{group}")
    if bool(group_config.get("one_time")):
        return occurrence_count == 0
    minimum = int(group_config.get("minimum_chapters", 0))
    if minimum < 0:
        raise ValueError("minimum_chapters 不得为负")
    return chapters_since_last is None or chapters_since_last >= minimum


def structural_similarity(
    values: Mapping[str, float], config: Mapping[str, Any]
) -> float:
    _validate_scores(values, high=1)
    return _weighted(values, config["similarity_weights"])


def repetition_fatigue(
    history: Sequence[tuple[float, float]], config: Mapping[str, Any]
) -> MetricResult:
    tau = float(config["tau"])
    if tau <= 0:
        raise ValueError("tau 必须大于 0")
    if not history:
        return MetricResult(
            metric="Repetition Fatigue",
            score=0,
            inputs={"history": [], "tau": tau, "policy": config["no_history_policy"]},
            evidence=["no_history"],
            threshold_interpretation="无历史，可视为新鲜",
            recommended_action="仍需记录本次结构标签",
        )
    numerator = 0.0
    denominator = 0.0
    normalized: list[dict[str, float]] = []
    for distance, similarity in history:
        if distance < 0:
            raise ValueError("Distance 不得为负")
        _validate_number("Similarity", similarity, 0, 1)
        decay = math.exp(-distance / tau)
        numerator += decay * similarity
        denominator += decay
        normalized.append(
            {"distance": distance, "similarity": similarity, "decay": decay}
        )
    score = 100 * numerator / denominator
    if score < 35:
        interpretation, action = "新鲜", "可用"
    elif score < 60:
        interpretation, action = "轻中度疲劳", "至少改变一个结构维度"
    elif score < 75:
        interpretation, action = "高疲劳", "至少改变来源、解决方式或结果中的两个"
    else:
        interpretation, action = "默认拒绝", "仅升级、反讽或闭环可申请例外"
    return MetricResult(
        metric="Repetition Fatigue",
        score=score,
        inputs={"history": normalized, "tau": tau},
        threshold_interpretation=interpretation,
        recommended_action=action,
    )


def risk_credibility(values: Mapping[str, float], config: Mapping[str, Any]) -> MetricResult:
    _validate_scores(values)
    score = _weighted(values, config["weights"])
    if score < 40:
        interpretation, action = "风险可信度偏低", "让已强调风险兑现真实代价"
    elif score > 85:
        interpretation, action = "风险可信度极高", "若总压力已过 80，允许局部控制或回报"
    else:
        interpretation, action = "风险可信", "保持来源、边界和后果清晰"
    return MetricResult(
        metric="Risk Credibility",
        score=score,
        inputs=dict(values),
        threshold_interpretation=interpretation,
        recommended_action=action,
    )


def agency(values: Mapping[str, float]) -> MetricResult:
    expected = {
        "value_balance",
        "consequence_difference",
        "information_adequacy",
        "opportunity_cost",
        "long_term_effect",
    }
    if set(values) != expected:
        raise ValueError(
            f"指标字段不匹配；缺少={sorted(expected - set(values))}，"
            f"多余={sorted(set(values) - expected)}"
        )
    _validate_scores(values, high=1)
    product = math.prod(values.values())
    score = 100 * product ** (1 / 5)
    if score < 35:
        interpretation, action = "伪选择", "增加真实后果差异或机会成本"
    elif score < 60:
        interpretation, action = "局部差异", "让选择改变后续条件"
    elif score < 80:
        interpretation, action = "有效选择", "保留选择造成的状态变化"
    else:
        interpretation, action = "路线级选择", "记录长期后果和不可逆成本"
    return MetricResult(
        metric="Agency",
        score=score,
        inputs=dict(values),
        threshold_interpretation=interpretation,
        recommended_action=action,
    )


def legibility(values: Mapping[str, float], config: Mapping[str, Any]) -> MetricResult:
    _validate_scores(values)
    score = _weighted(values, config["weights"])
    healthy = float(config["healthy_minimum"])
    if score < 60:
        interpretation, action = "可理解性过低", "优先调查、规则验证或局部回答"
    elif score < healthy:
        interpretation, action = "接近健康下限", "补足目标、规则或信息来源"
    else:
        interpretation, action = "目标与规则可理解", "可保留适度结果未知"
    return MetricResult(
        metric="Legibility",
        score=score,
        inputs=dict(values),
        threshold_interpretation=interpretation,
        recommended_action=action,
    )


def outcome_uncertainty(
    values: Mapping[str, float], config: Mapping[str, Any]
) -> MetricResult:
    _validate_scores(values)
    score = _weighted(values, config["weights"])
    low = float(config["healthy_minimum"])
    high = float(config["healthy_maximum"])
    if score < low:
        interpretation, action = "结果过于可预测", "引入真实选择、对手行动或代价"
    elif score <= high:
        interpretation, action = "健康未知度", "保持规则稳定并让结果继续开放"
    else:
        interpretation, action = "结果未知度过高", "给出局部答案并明确失败条件"
    return MetricResult(
        metric="Outcome Uncertainty",
        score=score,
        inputs=dict(values),
        threshold_interpretation=interpretation,
        recommended_action=action,
    )


def character_fit(values: Mapping[str, float], config: Mapping[str, Any]) -> float:
    _validate_scores(values)
    return _weighted(values, config["weights"])


def style_fit(values: Mapping[str, float], config: Mapping[str, Any]) -> float:
    _validate_scores(values)
    return _weighted(values, config["weights"])


def thread_need(values: Mapping[str, float], config: Mapping[str, Any]) -> float:
    for name, value in values.items():
        high = 150 if name == "narrative_debt" else 100
        _validate_number(name, value, 0, high)
    return _weighted(values, config["weights"])


def candidate_score(values: Mapping[str, float], config: Mapping[str, Any]) -> float:
    _validate_scores(values)
    return clamp(0, 100, _weighted(values, config["weights"]))
