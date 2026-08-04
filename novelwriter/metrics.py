"""metrics.py —— 六指标纯函数与权重常量表。

公式与阈值的唯一事实来源是 CONSTITUTION.md，各函数 docstring 标注节号。
所有无法从文本自动推断的维度一律来自作者台账输入；本模块不猜事实。
输入缺失（值为 None）时返回 score=None 并在 evidence 中列出缺失项，
由报告标注「待作者填写」，而不是按 0 算出误导分数（宪章 1.2：公式只提醒）。

所有指标统一 0-100 尺度（宪章 2 总述），函数均为纯函数，便于测试。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 权重常量表
# ---------------------------------------------------------------------------

# CONSTITUTION.md 2.1：读者压力六分项权重
PRESSURE_WEIGHTS = {
    "survival_threat": 0.25,     # 生存威胁
    "resource_scarcity": 0.20,   # 资源匮乏
    "time_pressure": 0.20,       # 时间压力
    "uncertainty": 0.15,         # 信息不确定性
    "social_conflict": 0.10,     # 人际冲突
    "recent_failure": 0.10,      # 失败累积
}
PRESSURE_LABELS = {
    "survival_threat": "生存威胁",
    "resource_scarcity": "资源匮乏",
    "time_pressure": "时间压力",
    "uncertainty": "信息不确定性",
    "social_conflict": "人际冲突",
    "recent_failure": "失败累积",
}

# CONSTITUTION.md 2.2：爽点净分总权重
PAYOFF_WEIGHTS = {"M": 0.25, "I": 0.25, "N": 0.15, "C": 0.15, "A": 0.20,
                  "F": -0.10, "D": -0.10}

# CONSTITUTION.md 2.2：爽点五档阈值（连续判断：score < 阈值 落入该档）
PAYOFF_TIERS = [
    (50, "不爆发，继续铺垫"),
    (65, "适合小型奖励"),
    (80, "适合中型爽点"),
    (91, "适合阶段性大爆发"),
    (float("inf"), "留给篇章高潮或世界性变化"),
]

# CONSTITUTION.md 2.4：进展值六维权重
PROGRESS_WEIGHTS = {
    "permanent_growth": 0.20,   # 主角永久成长
    "world_change": 0.20,       # 世界状态变化
    "relationship_change": 0.15,  # 关系变化
    "intel_change": 0.15,       # 情报变化
    "goal_advance": 0.15,       # 目标推进
    "new_gameplay": 0.15,       # 新玩法解锁
}
PROGRESS_LABELS = {
    "permanent_growth": "主角永久成长",
    "world_change": "世界状态变化",
    "relationship_change": "关系变化",
    "intel_change": "情报变化",
    "goal_advance": "目标推进",
    "new_gameplay": "新玩法解锁",
}

# CONSTITUTION.md 3.3：资源压力五子项权重
RESOURCE_PRESSURE_WEIGHTS = {
    "gap": 0.30,                 # 当前缺口
    "consume_income_ratio": 0.20,  # 消耗收入比
    "blocked_count": 0.20,       # 最近受阻次数
    "next_tier_demand": 0.15,    # 下一阶段需求
    "perceptibility": 0.15,      # 读者可感知程度
}

# CONSTITUTION.md 3.2：每 10 章爽点预算（指导性，非刚性扣减）
BUDGET_WINDOW_CHAPTERS = 10
BUDGET_TOTAL_POINTS = 100

# CONSTITUTION.md 2.6：风险可信度五因子（各 0-1，连乘）
RISK_FACTOR_KEYS = [
    "cost_realized_rate",        # 实际代价兑现率
    "failure_clarity",           # 失败后果清晰度
    "enemy_effectiveness",       # 敌人有效性
    "info_incompleteness",       # 主角信息不完整度
    "protection_limitedness",    # 保护机制有限度
]

# CONSTITUTION.md 2.5 / 3.1：疲劳与冷却窗口
NOVELTY_SAME_WINDOW = 20
NOVELTY_SIMILAR_WINDOW = 50
NOVELTY_SAME_PENALTY = 15
NOVELTY_SIMILAR_PENALTY = 8


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _missing(components: dict, keys) -> list:
    return [k for k in keys if components.get(k) is None]


# ---------------------------------------------------------------------------
# 指标 1：Pressure（宪章 2.1）
# ---------------------------------------------------------------------------


def pressure_score(components: dict) -> tuple:
    """读者总压力 = 六分项加权（CONSTITUTION.md 2.1）。

    Pressure = 25%×生存威胁 + 20%×资源匮乏 + 20%×时间压力
             + 15%×信息不确定性 + 10%×人际冲突 + 10%×失败累积

    输入：六分项 dict（0-100）。缺失项不按 0 算：返回 (None, evidence)。
    """
    missing = _missing(components, PRESSURE_WEIGHTS)
    if missing:
        return None, {"missing": missing}
    total = sum(float(components[k]) * w for k, w in PRESSURE_WEIGHTS.items())
    return round(_clamp(total), 1), {k: components[k] for k in PRESSURE_WEIGHTS}


# ---------------------------------------------------------------------------
# 指标 2：Payoff（宪章 2.2 / 2.5 / 3.3）
# ---------------------------------------------------------------------------


def maturity_score(components: dict) -> float:
    """爽点成熟度 M（CONSTITUTION.md 2.2）。

    M = 25%×稀缺压力 + 20%×铺垫深度 + 20%×读者等待时间
      + 20%×主角已支付成本 + 15%×篇章节奏适配度
    输入键：scarcity_pressure, setup_depth, wait_time, paid_cost, arc_fit。
    """
    weights = {"scarcity_pressure": 0.25, "setup_depth": 0.20,
               "wait_time": 0.20, "paid_cost": 0.20, "arc_fit": 0.15}
    missing = _missing(components, weights)
    if missing:
        return None
    return round(_clamp(sum(float(components[k]) * w
                            for k, w in weights.items())), 1)


def impact_score(components: dict) -> float:
    """奖励冲击力 I（CONSTITUTION.md 2.2）。冲击力看相对倍数，不看绝对数字。

    I = 25%×相对收益规模 + 25%×解除限制程度 + 20%×行为方式改变
      + 15%×对未来成长的帮助 + 15%×社会反馈或视觉表现
    输入键：relative_gain, restriction_lifted, behavior_change,
    future_growth, social_feedback。
    """
    weights = {"relative_gain": 0.25, "restriction_lifted": 0.25,
               "behavior_change": 0.20, "future_growth": 0.15,
               "social_feedback": 0.15}
    missing = _missing(components, weights)
    if missing:
        return None
    return round(_clamp(sum(float(components[k]) * w
                            for k, w in weights.items())), 1)


def plausibility_score(components: dict) -> float:
    """合理性 C（CONSTITUTION.md 2.2）。

    C = 30%×因果链完整度 + 25%×世界规则一致性
      + 25%×主角支付代价 + 20%×奖励来源提前出现
    输入键：causal_chain, rule_consistency, price_paid, source_foreshadowed。
    """
    weights = {"causal_chain": 0.30, "rule_consistency": 0.25,
               "price_paid": 0.25, "source_foreshadowed": 0.20}
    missing = _missing(components, weights)
    if missing:
        return None
    return round(_clamp(sum(float(components[k]) * w
                            for k, w in weights.items())), 1)


def aftermath_value_score(components: dict) -> float:
    """后续价值 A（CONSTITUTION.md 2.2）。只有改变后续选择的奖励才有后续价值。

    A = 30%×解锁新玩法 + 25%×改变主角决策
      + 25%×开启更高层资源需求 + 20%×影响队伍、市场或组织
    输入键：new_gameplay, decision_change, higher_tier_demand, group_impact。
    """
    weights = {"new_gameplay": 0.30, "decision_change": 0.25,
               "higher_tier_demand": 0.25, "group_impact": 0.20}
    missing = _missing(components, weights)
    if missing:
        return None
    return round(_clamp(sum(float(components[k]) * w
                            for k, w in weights.items())), 1)


def novelty_score(same_type_in_20: int, similar_structure_in_50: int) -> float:
    """新奇度 N（CONSTITUTION.md 2.5）。

    N = 100 − 最近20章同类爽点次数×15 − 最近50章相似结构次数×8
    """
    n = (100 - same_type_in_20 * NOVELTY_SAME_PENALTY
         - similar_structure_in_50 * NOVELTY_SIMILAR_PENALTY)
    return round(_clamp(n), 1)


def payoff_score(M, I, N, C, A, F, D) -> tuple:
    """爽点净分（CONSTITUTION.md 2.2）。

    S = 0.25M + 0.25I + 0.15N + 0.15C + 0.20A − 0.10F − 0.10D
    M 成熟度 / I 冲击力 / N 新奇度 / C 合理性 / A 后续价值为正向项；
    F 同类疲劳 / D 剧情破坏为扣分项。任一输入为 None 时返回 (None, evidence)。
    分档见 classify_payoff（五档阈值，宪章 2.2）。
    """
    parts = {"M": M, "I": I, "N": N, "C": C, "A": A, "F": F, "D": D}
    missing = [k for k, v in parts.items() if v is None]
    if missing:
        return None, {"missing": missing}
    total = sum(float(parts[k]) * PAYOFF_WEIGHTS[k] for k in parts)
    return round(_clamp(total), 1), {k: float(parts[k]) for k in parts}


def classify_payoff(score: float) -> str:
    """爽点五档阈值（CONSTITUTION.md 2.2），连续阈值判断：

    <50 不爆发，继续铺垫；<65 小型奖励；<80 中型爽点；
    <91 阶段性大爆发；其余留给篇章高潮或世界性变化。
    用连续阈值（而非整数闭区间）避免 49.1–49.9 等缝隙值落入兜底最高档。
    """
    if score is None:
        return "无法判定（输入缺失）"
    for threshold, label in PAYOFF_TIERS:
        if score < threshold:
            return label
    return PAYOFF_TIERS[-1][1]


def resource_pressure(components: dict) -> tuple:
    """单一资源压力 P（CONSTITUTION.md 3.3）。

    P = 30%×当前缺口 + 20%×消耗收入比 + 20%×最近受阻次数
      + 15%×下一阶段需求 + 15%×读者可感知程度
    各子项 0-100，由台账提供（metrics 不猜事实）。缺失时返回 (None, evidence)。
    """
    missing = _missing(components, RESOURCE_PRESSURE_WEIGHTS)
    if missing:
        return None, {"missing": missing}
    total = sum(float(components[k]) * w
                for k, w in RESOURCE_PRESSURE_WEIGHTS.items())
    return round(_clamp(total), 1), {k: components[k]
                                     for k in RESOURCE_PRESSURE_WEIGHTS}


# ---------------------------------------------------------------------------
# 指标 3：Narrative Debt（宪章 2.3）
# ---------------------------------------------------------------------------


def narrative_debt(hooks: list, current_chapter: int) -> list:
    """悬念债务排序清单（CONSTITUTION.md 2.3）。

    Debt = 重要度 × 等待章数 × 被提醒次数 × 读者可见度 ÷ 当前推进度
    （progress 以 0.05 为下限，防止除零；数值用于排序，不追求绝对精确。）
    仅统计 status != resolved 的悬念。输入 hook 字段：
    importance(0-1), born_chapter, reminder_count, visibility(0-1), progress(0-1)。
    """
    debts = []
    for h in hooks:
        if isinstance(h, dict) and h.get("_comment"):
            continue
        if not isinstance(h, dict) or h.get("status") == "resolved":
            continue
        importance = float(h.get("importance") or 0)
        age = max(0, int(current_chapter) - int(h.get("born_chapter") or
                                                current_chapter))
        reminders = max(1, int(h.get("reminder_count") or 1))
        visibility = float(h.get("visibility") or 0)
        progress = max(float(h.get("progress") or 0), 0.05)
        debt = importance * age * reminders * visibility / progress
        debts.append({"id": h.get("id", ""), "hook": h.get("hook", ""),
                      "debt": round(debt, 1), "age": age,
                      "importance": importance, "progress": progress,
                      "status": h.get("status", "open")})
    debts.sort(key=lambda d: d["debt"], reverse=True)
    return debts


def hook_balance_check(events: list, window: int = 10) -> tuple:
    """每 10 章悬念平衡检查（CONSTITUTION.md 2.3）。

    新增悬念 ≤ 完全兑现 + 部分兑现×1.5。
    输入 events：[{chapter, action}]，action ∈ new/advance/resolve。
    返回 (balanced: bool, evidence)。
    """
    lo = max((e.get("chapter", 0) for e in events), default=0) - window + 1
    recent = [e for e in events if e.get("chapter", 0) >= lo]
    new = sum(1 for e in recent if e.get("action") == "new")
    resolved = sum(1 for e in recent if e.get("action") == "resolve")
    advanced = sum(1 for e in recent if e.get("action") == "advance")
    capacity = resolved + advanced * 1.5
    return new <= capacity, {"window": window, "new": new,
                             "resolved": resolved, "advanced": advanced,
                             "capacity": round(capacity, 1)}


# ---------------------------------------------------------------------------
# 指标 4：Progress（宪章 2.4）
# ---------------------------------------------------------------------------


def progress_score(components: dict) -> tuple:
    """进展值（CONSTITUTION.md 2.4）。

    Progress = 20%×主角永久成长 + 20%×世界状态变化 + 15%×关系变化
             + 15%×情报变化 + 15%×目标推进 + 15%×新玩法解锁
    缺失项返回 (None, evidence)。
    """
    missing = _missing(components, PROGRESS_WEIGHTS)
    if missing:
        return None, {"missing": missing}
    total = sum(float(components[k]) * w for k, w in PROGRESS_WEIGHTS.items())
    return round(_clamp(total), 1), {k: components[k] for k in PROGRESS_WEIGHTS}


def stagnation_index(recent_chapters: int, effective_chapters: int) -> tuple:
    """停滞指数与停滞率（CONSTITUTION.md 2.4）。

    停滞指数 = 最近章节数 − 发生有效不可逆变化的章节数。
    停滞率过高（例如最近 8 章只有 2 章真正改变状态）即代表正在灌水。
    """
    recent_chapters = max(0, int(recent_chapters))
    effective_chapters = max(0, min(int(effective_chapters), recent_chapters))
    index = recent_chapters - effective_chapters
    rate = round(index / recent_chapters, 2) if recent_chapters else 0.0
    return index, {"recent_chapters": recent_chapters,
                   "effective_chapters": effective_chapters,
                   "stagnation_rate": rate}


# ---------------------------------------------------------------------------
# 指标 5：Repetition Fatigue（宪章 2.5）
# ---------------------------------------------------------------------------


def repetition_fatigue(events: list, target_group: str | None = None) -> tuple:
    """重复疲劳（CONSTITUTION.md 2.5，同新奇度公式的疲劳视角）。

    N = 100 − 最近20章同类爽点次数×15 − 最近50章相似结构次数×8
    fatigue = 100 − N。
    输入 events：[{chapter, group, subtype}]，顺序不限。
    target_group 缺省时以章号最大事件的组为目标；无事件时疲劳为 0。
    """
    if not events:
        return 0.0, {"same_type_20": 0, "similar_50": 0, "novelty": 100.0,
                     "target_group": target_group}
    latest = max(events, key=lambda e: e.get("chapter", 0))
    last_ch = int(latest.get("chapter", 0))
    group = target_group or latest.get("group", "")
    recent_20 = [e for e in events if e.get("chapter", 0) > last_ch - 20]
    recent_50 = [e for e in events if e.get("chapter", 0) > last_ch - 50]
    same = sum(1 for e in recent_20 if e.get("group") == group)
    similar = sum(1 for e in recent_50)
    novelty = novelty_score(same, similar)
    fatigue = round(_clamp(100 - novelty), 1)
    return fatigue, {"target_group": group, "same_type_20": same,
                     "similar_50": similar, "novelty": novelty}


# ---------------------------------------------------------------------------
# 指标 6：Risk Credibility（宪章 2.6）
# ---------------------------------------------------------------------------


def risk_credibility(factors: dict) -> tuple:
    """风险可信度（CONSTITUTION.md 2.6），五项 0-1 连乘后映射 0-100。

    RiskCredibility = 实际代价兑现率 × 失败后果清晰度 × 敌人有效性
                    × 主角信息不完整度 × 保护机制有限度
    铁律：危险必须在故事中偶尔真实兑现，不能只存在于说明里。
    缺失因子返回 (None, evidence)。
    """
    missing = _missing(factors, RISK_FACTOR_KEYS)
    if missing:
        return None, {"missing": missing}
    product = 1.0
    for k in RISK_FACTOR_KEYS:
        product *= _clamp(float(factors[k]), 0.0, 1.0)
    return round(product * 100, 1), {k: factors[k] for k in RISK_FACTOR_KEYS}
