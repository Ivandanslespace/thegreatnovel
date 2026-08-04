"""scheduler.py —— 下一章建议生成器（只提建议，不锁定；宪章 1.2）。

输入：六指标结果 + history + hooks + 作者台账，输出「下一章建议」dict：
payoff 分档、压力曲线检查、冷却组、10 章预算余额、悬念债务、
资源解放硬触发（宪章 3.3 七条）、禁忌桥段清单。
输出措辞统一为「建议」。
"""

from __future__ import annotations

from . import metrics as M

# 六冷却组中文名（CONSTITUTION.md 3.1）
COOLDOWN_GROUP_NAMES = {
    "resource": "资源类",
    "combat": "战力类",
    "cognition": "认知类",
    "social": "社会类",
    "world": "世界类",
    "emotion": "情绪类",
}

# 悬念债务阈值：超过即标记必须推进/部分兑现（宪章 2.3 还债纪律的量化提醒）
DEBT_MUST_ADVANCE_THRESHOLD = 30.0
DEBT_PARTIAL_PAYOFF_THRESHOLD = 12.0

# 压力曲线阈值（宪章 2.1）
PRESSURE_HIGH = 80
PRESSURE_HIGH_MAX_STREAK = 3
PRESSURE_LOW = 35
PRESSURE_LOW_MAX_STREAK = 5


def build_suggestion(chapter_no: int, book_state: dict, hooks: list,
                     history: dict, metric_results: dict) -> dict:
    """汇总六指标与台账，生成下一章建议 dict（纯函数，不落盘）。

    metric_results 由 analyze 流程计算：
    {pressure_total, resource_pressures: {name: score},
     repetition: (fatigue, evidence), ...}
    """
    pressure_total = metric_results.get("pressure_total")
    resource_pressures = metric_results.get("resource_pressures") or {}
    repetition = metric_results.get("repetition") or (0.0, {})
    fatigue, fatigue_evidence = repetition

    suggestion = {
        "chapter": chapter_no,
        "payoff": _payoff_advice(metric_results),
        "pressure_curve": _pressure_curve_advice(history, pressure_total),
        "cooldowns": _cooldown_advice(book_state, chapter_no),
        "budget": _budget_advice(history, chapter_no),
        "narrative_debt": _debt_advice(hooks, chapter_no),
        "resource_triggers": _resource_liberation_check(
            book_state, resource_pressures, fatigue),
        "repetition": {
            "fatigue": fatigue,
            "evidence": fatigue_evidence,
        },
    }
    suggestion["forbidden_hooks"] = _forbidden_hooks(
        fatigue, fatigue_evidence, suggestion["cooldowns"])
    return suggestion


# ---------------------------------------------------------------------------


def _payoff_advice(metric_results: dict) -> dict:
    """payoff 净分与五档建议（宪章 2.2）。"""
    payoff = metric_results.get("payoff")
    score, evidence = (payoff if isinstance(payoff, tuple)
                       else (None, {"note": "台账未填写 M/I/C/A 等子项"}))
    return {
        "score": score,
        "tier": M.classify_payoff(score),
        "evidence": evidence,
        "advice": ("建议按分档控制本章爽点规模" if score is not None
                   else "payoff 子项待作者填写，暂无法给出分档建议"),
    }


def _pressure_curve_advice(history: dict, pressure_total) -> dict:
    """压力曲线检查（宪章 2.1 曲线纪律）。

    连续 >80 超 3 章→建议降压章；连续 <35 超 5 章→建议升压；
    兑现后建议保留 20–40 残余。
    """
    ph = history.get("pressure_history") or []
    advice = []
    totals = [p.get("total") for p in ph if isinstance(p.get("total"), (int, float))]
    # 当前压力优先取最近一章记录值，其次取台账静态值
    if totals:
        pressure_total = totals[-1]
    high_streak = _tail_streak(totals, lambda t: t > PRESSURE_HIGH)
    low_streak = _tail_streak(totals, lambda t: t < PRESSURE_LOW)
    if high_streak > PRESSURE_HIGH_MAX_STREAK:
        advice.append(f"已连续 {high_streak} 章压力 >80（宪章 2.1：不宜超过 3–5 章），"
                      "建议安排降压章")
    if low_streak > PRESSURE_LOW_MAX_STREAK:
        advice.append(f"已连续 {low_streak} 章压力 <35（宪章 2.1：不宜超过 5–8 章），"
                      "建议制造新风险升压")
    events = history.get("payoff_events") or []
    last_ch = max((e.get("chapter", 0) for e in events), default=0)
    if totals and last_ch > 0 and max((p.get("chapter", 0) for p in ph),
                                       default=0) - last_ch <= 2:
        advice.append("最近刚兑现大爽点：压力不宜立即归零，"
                      "建议保留 20–40 分的新问题残余（宪章 2.1）")
    return {"high_streak": high_streak, "low_streak": low_streak,
            "current": pressure_total, "advice": advice}


def _tail_streak(totals: list, predicate) -> int:
    streak = 0
    for t in reversed(totals):
        if predicate(t):
            streak += 1
        else:
            break
    return streak


def _cooldown_advice(book_state: dict, chapter_no: int) -> dict:
    """冷却组判断（宪章 3.1）：组内距 last_major_chapter 不足
    recommended_cooldown → 该组禁用；列出可用组。"""
    cooldowns = book_state.get("payoff_cooldowns") or []
    disabled, available = [], []
    for c in cooldowns:
        group = c.get("group", "")
        last = int(c.get("last_major_chapter") or 0)
        rec = int(c.get("recommended_cooldown") or 0)
        name = COOLDOWN_GROUP_NAMES.get(group, group)
        if last > 0 and chapter_no - last < rec:
            disabled.append({"group": group, "name": name,
                             "wait_chapters": rec - (chapter_no - last)})
        else:
            available.append(group)
    return {"available_groups": available, "disabled_groups": disabled}


def _budget_advice(history: dict, chapter_no: int) -> dict:
    """10 章爽点预算余额（宪章 3.2：每 10 章约 100 点，指导性）。"""
    events = history.get("payoff_events") or []
    window = [e for e in events
              if e.get("chapter", 0) > chapter_no - M.BUDGET_WINDOW_CHAPTERS]
    used = sum(int(e.get("score") or 0) for e in window)
    remaining = M.BUDGET_TOTAL_POINTS - used
    advice = []
    if remaining <= 0:
        advice.append("最近 10 章预算已用完，建议本章以铺垫与余韵为主")
    if any(int(e.get("score") or 0) >= 40 for e in window):
        advice.append("窗口内已有 40+ 点大爽点，前后应留铺垫与余韵，"
                      "不得连续堆叠（宪章 3.2）")
    return {"window_chapters": M.BUDGET_WINDOW_CHAPTERS,
            "budget": M.BUDGET_TOTAL_POINTS, "used": used,
            "remaining": remaining, "events": window, "advice": advice}


def _debt_advice(hooks: list, chapter_no: int) -> dict:
    """悬念债务 top1/top2 超阈值 → 标记必须推进/部分兑现（宪章 2.3）。"""
    debts = M.narrative_debt(hooks, chapter_no)
    advice = []
    must = []
    for i, d in enumerate(debts[:2], start=1):
        if d["debt"] >= DEBT_MUST_ADVANCE_THRESHOLD:
            must.append({"rank": i, **d, "action": "建议必须推进（可部分兑现）"})
        elif d["debt"] >= DEBT_PARTIAL_PAYOFF_THRESHOLD:
            must.append({"rank": i, **d, "action": "建议推进或部分兑现"})
    if not debts:
        advice.append("台账中暂无未解决悬念；可新增，但注意每 10 章平衡检查"
                      "（新增 ≤ 完全兑现 + 部分兑现×1.5，宪章 2.3）")
    return {"top_debts": debts[:5], "must_act": must, "advice": advice}


def _resource_liberation_check(book_state: dict, resource_pressures: dict,
                               fatigue) -> dict:
    """资源解放硬触发（宪章 3.3）：七条必须同时满足，逐条给出 pass/fail。"""
    results = []
    for res in book_state.get("resources") or []:
        name = res.get("name", "")
        rp = resource_pressures.get(name)
        checks = [
            _check("资源压力 ≥ 70（资源真的短缺）",
                   rp is not None and rp >= 70,
                   f"当前 {rp}" if rp is not None else "资源压力待计算"),
            _check("铺垫 ≥ 8 章", int(res.get("setup_chapters") or 0) >= 8,
                   f"setup_chapters={res.get('setup_chapters')}"),
            _check("受阻决策 ≥ 2", int(res.get("blocked_count") or 0) >= 2,
                   f"blocked_count={res.get('blocked_count')}"),
            _check("同类疲劳 ≤ 35", fatigue is not None and fatigue <= 35,
                   f"fatigue={fatigue}"),
            _check("有因果来源（战斗/闭环/投资，非作者发钱）",
                   bool(res.get("causal_source")),
                   "台账 causal_source " + ("已填" if res.get("causal_source")
                                            else "未填")),
            _check("有后续玩法（得到后会改变玩法）",
                   bool(res.get("post_gameplay")),
                   "台账 post_gameplay " + ("已填" if res.get("post_gameplay")
                                            else "未填")),
            _check("下一层资源目标就绪", bool(res.get("next_tier_goal")),
                   "台账 next_tier_goal " + ("已填" if res.get("next_tier_goal")
                                              else "未填")),
        ]
        results.append({"resource": name, "checks": checks,
                        "all_pass": all(c["pass"] for c in checks)})
    return {"results": results,
            "summary": ("建议：存在满足七条硬触发的资源，可考虑阶段性资源解放"
                        if any(r["all_pass"] for r in results)
                        else "无资源满足全部七条硬触发，不建议资源解放大爽点")}


def _check(rule: str, passed: bool, detail: str) -> dict:
    return {"rule": rule, "pass": bool(passed), "detail": detail}


def _forbidden_hooks(fatigue, fatigue_evidence: dict, cooldowns: dict) -> list:
    """基于疲劳度与冷却组生成禁止桥段清单（宪章 2.5 / 3.1 / 3.5）。"""
    forbidden = []
    group = fatigue_evidence.get("target_group")
    if group and fatigue is not None and fatigue > 65:
        name = COOLDOWN_GROUP_NAMES.get(group, group)
        forbidden.append(f"禁止再次使用「{name}」同类爽点结构"
                         f"（疲劳度 {fatigue}，宪章 2.5）")
    for d in cooldowns.get("disabled_groups", []):
        forbidden.append(f"禁用「{d['name']}」组爽点：距上次大爽点不足冷却间隔，"
                         f"还需约 {d['wait_chapters']} 章（宪章 3.1）")
    forbidden.append("禁止无铺垫发大数字、暴富后立刻清空、一次解除所有资源限制"
                     "（宪章 3.5 四种禁止写法）")
    return forbidden
