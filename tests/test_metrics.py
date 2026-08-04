"""test_metrics.py —— 六指标黄金值测试（标准库 unittest）。

公式权威来源：CONSTITUTION.md（六指标）与设计对话原文（黄金值）。
所有断言均按宪章公式手算；与任务书黄金值表述的差异在测试注释与
验证报告中如实说明。
"""

import unittest

from novelwriter import metrics as M


class TestPayoffGolden(unittest.TestCase):
    """爽点净分 S = 0.25M+0.25I+0.15N+0.15C+0.20A−0.10F−0.10D（宪章 2.2）"""

    def test_golden_example_matches_constitution_formula(self):
        # 任务书示例：M=83 I=92 N=87 C=91 A=94 F=12 D=16
        score, evidence = M.payoff_score(83, 92, 87, 91, 94, 12, 16)
        # 按宪章公式手算：20.75+23.00+13.05+13.65+18.80−1.20−1.60 = 86.45
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score, 86.45, delta=0.06)
        # 注：任务书写作「S≈88」，但其所给公式与输入算出为 86.45，
        # 两者相差 1.55（>±1）。实现与 CONSTITUTION.md 2.2 公式一致，
        # 差异判定为任务书期望值笔误，详见验证报告。
        for k in ("M", "I", "N", "C", "A", "F", "D"):
            self.assertIn(k, evidence)

    def test_missing_input_returns_none(self):
        score, evidence = M.payoff_score(83, None, 87, 91, 94, 12, 16)
        self.assertIsNone(score)
        self.assertEqual(evidence["missing"], ["I"])

    def test_classify_tiers(self):
        self.assertEqual(M.classify_payoff(49), "不爆发，继续铺垫")
        self.assertEqual(M.classify_payoff(50), "适合小型奖励")
        self.assertEqual(M.classify_payoff(65), "适合中型爽点")
        self.assertEqual(M.classify_payoff(80), "适合阶段性大爆发")
        self.assertEqual(M.classify_payoff(91), "留给篇章高潮或世界性变化")

    def test_classify_gap_values_continuous(self):
        # M3：整数闭区间曾让 49.1–49.9 等缝隙值落入兜底最高档；
        # 连续阈值下各缝隙值应归入正确档位
        self.assertEqual(M.classify_payoff(49.4), "不爆发，继续铺垫")
        self.assertEqual(M.classify_payoff(64.5), "适合小型奖励")
        self.assertEqual(M.classify_payoff(79.5), "适合中型爽点")
        self.assertEqual(M.classify_payoff(90.5), "适合阶段性大爆发")
        self.assertEqual(M.classify_payoff(95), "留给篇章高潮或世界性变化")
        self.assertEqual(M.classify_payoff(None), "无法判定（输入缺失）")


class TestNoveltyFatigue(unittest.TestCase):
    """新奇度 N = 100 − 最近20章同类×15 − 最近50章相似×8（宪章 2.5）"""

    def test_no_history_full_novelty(self):
        self.assertEqual(M.novelty_score(0, 0), 100.0)

    def test_one_each_penalties(self):
        # 各 1 次 → 100 − 15 − 8 = 77
        self.assertEqual(M.novelty_score(1, 1), 77.0)

    def test_clamped_at_zero(self):
        self.assertEqual(M.novelty_score(10, 10), 0.0)

    def test_repetition_fatigue_empty_history(self):
        fatigue, ev = M.repetition_fatigue([])
        self.assertEqual(fatigue, 0.0)
        self.assertEqual(ev["novelty"], 100.0)

    def test_repetition_fatigue_counts_windows(self):
        events = [{"chapter": ch, "group": "resource", "subtype": "暴富"}
                  for ch in (95, 98)] + [{"chapter": 100, "group": "combat"}]
        fatigue, ev = M.repetition_fatigue(events, target_group="resource")
        # 最近20章同类 resource = 2；最近50章相似结构 = 3
        self.assertEqual(ev["same_type_20"], 2)
        self.assertEqual(ev["similar_50"], 3)
        self.assertEqual(ev["novelty"], 100 - 2 * 15 - 3 * 8)
        self.assertEqual(fatigue, 100 - ev["novelty"])


class TestNarrativeDebt(unittest.TestCase):
    """Debt = 重要度 × 等待章数 × 被提醒次数 × 读者可见度 ÷ 推进度（宪章 2.3）"""

    def test_golden_debt_about_198(self):
        # importance=0.9, age=22, reminders=3, visibility=1.0, progress=0.3
        # → 0.9×22×3×1.0÷0.3 = 198
        hook = {"id": "h001", "hook": "系统来源", "importance": 0.9,
                "born_chapter": 78, "reminder_count": 3,
                "visibility": 1.0, "progress": 0.3, "status": "open"}
        debts = M.narrative_debt([hook], current_chapter=100)
        self.assertEqual(len(debts), 1)
        self.assertAlmostEqual(debts[0]["debt"], 198.0, delta=0.05)
        self.assertEqual(debts[0]["age"], 22)

    def test_resolved_hooks_excluded(self):
        hook = {"id": "h002", "hook": "已解决", "importance": 0.9,
                "born_chapter": 1, "reminder_count": 5,
                "visibility": 1.0, "progress": 1.0, "status": "resolved"}
        self.assertEqual(M.narrative_debt([hook], current_chapter=100), [])

    def test_progress_floor_prevents_division_blowup(self):
        hook = {"id": "h003", "hook": "零推进", "importance": 1.0,
                "born_chapter": 90, "reminder_count": 1,
                "visibility": 1.0, "progress": 0.0, "status": "open"}
        debts = M.narrative_debt([hook], current_chapter=100)
        # progress 下限 0.05 → 1.0×10×1×1.0÷0.05 = 200
        self.assertAlmostEqual(debts[0]["debt"], 200.0, delta=0.05)

    def test_hook_balance_check(self):
        # 新增 ≤ 完全兑现 + 部分兑现×1.5：新增 2 > 0 + 1×1.5 = 1.5 → 失衡
        events = [{"chapter": 10, "action": "new"},
                  {"chapter": 11, "action": "new"},
                  {"chapter": 12, "action": "advance"}]
        balanced, ev = M.hook_balance_check(events)
        self.assertFalse(balanced)
        self.assertEqual(ev["new"], 2)
        self.assertEqual(ev["capacity"], 1.5)
        # 再补一次完全兑现 → 2 ≤ 1 + 1×1.5 = 2.5 → 平衡
        events.append({"chapter": 13, "action": "resolve"})
        balanced, ev = M.hook_balance_check(events)
        self.assertTrue(balanced)


class TestPressureAndResourcePressure(unittest.TestCase):
    """压力加权（宪章 2.1 / 3.3）"""

    def test_pressure_six_components_hand_computed(self):
        # 六分项 72/91/68/55/20/40
        # = 25%×72 + 20%×91 + 20%×68 + 15%×55 + 10%×20 + 10%×40
        # = 18 + 18.2 + 13.6 + 8.25 + 2 + 4 = 64.05
        comps = {"survival_threat": 72, "resource_scarcity": 91,
                 "time_pressure": 68, "uncertainty": 55,
                 "social_conflict": 20, "recent_failure": 40}
        score, evidence = M.pressure_score(comps)
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score, 64.05, delta=0.06)
        # 注：任务书写「→67.7」，但按宪章 2.1 权重（25/20/20/15/10/10）
        # 任何排列组合最大也只能得到 65.0，67.7 无法由读者压力公式得出；
        # 67.7 恰为资源压力公式（30/20/20/15/15）在输入
        # gap=72/消耗收入比=91/受阻=68/下一层需求=55/可感知=40 时的结果，
        # 见 test_resource_pressure_golden。实现与宪章一致。

    def test_resource_pressure_golden_67_7(self):
        # 资源压力 P = 30%×缺口 + 20%×消耗收入比 + 20%×受阻次数
        #            + 15%×下一阶段需求 + 15%×读者可感知程度
        # = 21.6 + 18.2 + 13.6 + 8.25 + 6.0 = 67.65 → 67.7（黄金值）
        comps = {"gap": 72, "consume_income_ratio": 91, "blocked_count": 68,
                 "next_tier_demand": 55, "perceptibility": 40}
        score, evidence = M.resource_pressure(comps)
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score, 67.65, delta=0.06)

    def test_pressure_missing_returns_none(self):
        score, evidence = M.pressure_score({"survival_threat": 50})
        self.assertIsNone(score)
        self.assertIn("missing", evidence)


class TestProgressStagnationRisk(unittest.TestCase):
    """progress / stagnation / risk_credibility 手算用例（宪章 2.4 / 2.6）"""

    def test_progress_hand_computed(self):
        # 20%×80 + 20%×60 + 15%×50 + 15%×40 + 15%×70 + 15%×30
        # = 16 + 12 + 7.5 + 6 + 10.5 + 4.5 = 56.5
        comps = {"permanent_growth": 80, "world_change": 60,
                 "relationship_change": 50, "intel_change": 40,
                 "goal_advance": 70, "new_gameplay": 30}
        score, evidence = M.progress_score(comps)
        self.assertAlmostEqual(score, 56.5, delta=0.06)

    def test_stagnation_hand_computed(self):
        # 最近 8 章仅 2 章有效变化 → 指数 6，停滞率 0.75（宪章 2.4 示例）
        index, evidence = M.stagnation_index(8, 2)
        self.assertEqual(index, 6)
        self.assertEqual(evidence["stagnation_rate"], 0.75)

    def test_risk_credibility_hand_computed(self):
        # 五因子连乘：0.8×0.9×0.7×0.6×0.5 = 0.1512 → 15.1
        factors = {"cost_realized_rate": 0.8, "failure_clarity": 0.9,
                   "enemy_effectiveness": 0.7, "info_incompleteness": 0.6,
                   "protection_limitedness": 0.5}
        score, evidence = M.risk_credibility(factors)
        self.assertAlmostEqual(score, 15.1, delta=0.06)

    def test_risk_missing_factor_returns_none(self):
        score, evidence = M.risk_credibility({"cost_realized_rate": 0.5})
        self.assertIsNone(score)
        self.assertIn("missing", evidence)


if __name__ == "__main__":
    unittest.main()
