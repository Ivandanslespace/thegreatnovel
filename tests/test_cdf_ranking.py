"""Phase 2 CDF 排名引擎单元测试 - 极简版本"""

import unittest
from engine_runtime.ranking_engine import (
    WEIGHTS,
    calculate_cdf_percentile,
    calculate_dimension_scores,
    convert_percentile_to_rank,
)


class TestWeights(unittest.TestCase):
    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0)

    def test_all_five_dimensions_present(self):
        self.assertEqual(set(WEIGHTS.keys()), {"combat", "resources", "base", "information", "social"})


class TestCalculateDimensionScores(unittest.TestCase):
    def test_empty_action_returns_all_zeros(self):
        scores = calculate_dimension_scores({})
        self.assertEqual(scores, {k: 0.0 for k in WEIGHTS})

    def test_combat_action(self):
        scores = calculate_dimension_scores({"action_type": "COMBAT", "damage_dealt": 100})
        self.assertEqual(scores["combat"], 10.0)

    def test_exploration_gives_information(self):
        scores = calculate_dimension_scores({"action_type": "EXPLORATION", "locations_discovered": 1})
        self.assertEqual(scores["information"], 25.0)

    def test_resources_score(self):
        scores = calculate_dimension_scores({"resources_obtained": {"wood": 10, "stone": 5}})
        self.assertEqual(scores["resources"], 7.5)  # 15 * 0.5

    def test_build_gives_base_score(self):
        scores = calculate_dimension_scores({"structures_built": 1})
        self.assertEqual(scores["base"], 20.0)

    def test_alliance_gives_social_score(self):
        scores = calculate_dimension_scores({"alliances_formed": 1})
        self.assertEqual(scores["social"], 20.0)


class TestCDFPercentile(unittest.TestCase):
    def test_empty_pool_returns_50(self):
        self.assertEqual(calculate_cdf_percentile({"combat": 10}, []), 50.0)

    def test_beating_all_peers(self):
        protag = {"combat": 100, "resources": 0, "base": 0, "information": 0, "social": 0}
        peers = [{"combat": 10, "resources": 0, "base": 0, "information": 0, "social": 0}] * 5
        pct = calculate_cdf_percentile(protag, peers)
        self.assertEqual(pct, 30.0)  # 0.30 * 1.0 * 100

    def test_losing_to_all_peers(self):
        protag = {"combat": 0, "resources": 0, "base": 0, "information": 0, "social": 0}
        peers = [{"combat": 10, "resources": 10, "base": 10, "information": 10, "social": 10}] * 5
        pct = calculate_cdf_percentile(protag, peers)
        self.assertEqual(pct, 0.0)

    def test_tied_scores_give_zero_below(self):
        """关键测试：完全相同的分数应该给出 0% below（严格小于）"""
        protag = {"combat": 10, "resources": 0, "base": 0, "information": 0, "social": 0}
        peers = [{"combat": 10, "resources": 0, "base": 0, "information": 0, "social": 0}] * 10
        pct = calculate_cdf_percentile(protag, peers)
        self.assertEqual(pct, 0.0)  # 没有人严格低于主角

    def test_mixed_scores(self):
        protag = {"combat": 50, "resources": 30, "base": 20, "information": 10, "social": 5}
        peers = [
            {"combat": 40, "resources": 20, "base": 10, "information": 5, "social": 0},
            {"combat": 60, "resources": 40, "base": 30, "information": 20, "social": 10},
        ]
        # combat: below=1/2, resources: below=1/2, base: below=1/2, info: below=1/2, social: below=1/2
        # weighted = (0.30+0.25+0.20+0.15+0.10) * 0.5 * 100 = 50.0
        pct = calculate_cdf_percentile(protag, peers)
        self.assertEqual(pct, 50.0)


class TestConvertPercentileToRank(unittest.TestCase):
    def test_50_percentile(self):
        self.assertEqual(convert_percentile_to_rank(50.0, 1000), 501)

    def test_100_percentile(self):
        self.assertEqual(convert_percentile_to_rank(100.0, 1000), 1)

    def test_bounds(self):
        self.assertEqual(convert_percentile_to_rank(0.0, 100), 100)
        self.assertEqual(convert_percentile_to_rank(100.0, 100), 1)


class TestKeyBehavior(unittest.TestCase):
    """验证核心行为：一次普通行动不会跳到 top 排名"""

    def test_first_normal_action_stays_moderate(self):
        """首次普通行动，如果 peers 也都有类似分数，应该保持中等排名"""
        protag = calculate_dimension_scores({"action_type": "EXPLORATION", "locations_discovered": 1})
        # 20 个 peers，其中 10 个也有 information=25，10 个更高
        peers = (
            [{"information": 25.0, "combat": 0.0, "resources": 0.0, "base": 0.0, "social": 0.0}] * 10 +
            [{"information": 50.0, "combat": 10.0, "resources": 5.0, "base": 0.0, "social": 0.0}] * 10
        )
        pct = calculate_cdf_percentile(protag, peers)
        # 主角 information=25：below=0 (10个平局不算below), combat/resources/base/social=0：below=0
        # 所以 percentile 应该不高
        self.assertLessEqual(pct, 50.0)


if __name__ == "__main__":
    unittest.main()
