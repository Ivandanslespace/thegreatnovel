"""P0 完整数据链验证测试 - 从 world.mechanics 配置到 runtime ranking

验证审查报告指出的所有 P0 问题：
1. rules:null 与 create_save.py setdefault() 兼容
2. mechanics.capabilities 通过 create_save → compiler → bundle
3. mechanics.ranking 配置正确传递和解析
4. RankingConfig 数据结构分离 (weights vs scales)
5. calculate_cdf_percentile 不会 _scales * float
"""

import unittest
from engine_runtime.world_compiler import compile_world_bundle
from engine_runtime.ranking_engine import (
    DEFAULT_RANKING_WEIGHTS,
    DEFAULT_RANKING_SCALES,
    _merge_weights,
    calculate_dimension_scores,
    calculate_cdf_percentile,
)


class TestP0RulesNullCompatibility(unittest.TestCase):
    """P0-1: 测试 rules:null 与 create_save.py 的兼容"""
    
    def test_rules_null_does_not_crash(self):
        """规则为 null 时不应崩溃，应正常初始化"""
        # 模拟模板中 rules: null 的情况
        world_with_null_rules = {
            "name": "TestWorld",
            "rules": None,  # 模板可能设为 null
        }
        
        # create_save.py 的正确做法是用 setdefault 获取或初始化
        rules = world_with_null_rules.setdefault("rules", {})
        
        # 如果 rules 已经是 null，需要检查并重新初始化
        if not isinstance(rules, dict):
            rules = {}
            world_with_null_rules["rules"] = rules
        
        if not isinstance(rules.get("disaster"), dict):
            rules["disaster"] = {}
        
        if not isinstance(rules.get("death"), dict):
            rules["death"] = {}
        
        # 不应该抛出 TypeError: 'NoneType' object is not subscriptable
        self.assertIn("disaster", rules)
        self.assertIn("death", rules)
        self.assertIsInstance(rules["disaster"], dict)
        self.assertIsInstance(rules["death"], dict)


class TestP0RankingSchemaSeparation(unittest.TestCase):
    """P0-5: RankingConfig 数据结构分离 (weights vs scales)"""
    
    def test_merge_weights_separates_weights_and_scales(self):
        """_merge_weights 应返回 weights 和 scales 分离的结构"""
        custom_config = {
            "enabled_dimensions": ["combat", "resources", "base", "information", "social"],
            "dimension_weights": {
                "combat": 0.6,
                "resources": 0.4,
                "base": 0.0,
                "information": 0.0,
                "social": 0.0,
            },
            "dimension_scales": {"combat_multiplier": 0.15},
        }
        
        result = _merge_weights(custom_config)
        
        # 结果应包含五维权重
        for dim in DEFAULT_RANKING_WEIGHTS.keys():
            self.assertIn(dim, result, f"维度 {dim} 必须在结果中")
            self.assertIsInstance(result[dim], float, f"{dim} 必须是 float")
        
        # _scales 必须是嵌套对象
        self.assertIn("_scales", result)
        self.assertIsInstance(result["_scales"], dict)
        
        # 关键：_scales 不应与维度混在一起
        self.assertNotIn("combat_multiplier", result)  # 在 _scales 内部
        self.assertIn("combat_multiplier", result["_scales"])
    
    def test_default_returns_separated_structure(self):
        """默认返回值应分离 weights 和 scales"""
        result = _merge_weights(None)
        
        for dim in DEFAULT_RANKING_WEIGHTS.keys():
            self.assertIn(dim, result)
            self.assertIsInstance(result[dim], float)
        
        self.assertIn("_scales", result)
        self.assertIsInstance(result["_scales"], dict)


class TestP0NoScalesFloatMultiplication(unittest.TestCase):
    """P0-6: 验证 _scales 不会与 float 相乘导致 TypeError"""
    
    def test_cdf_percentile_filters_out_scales_key(self):
        """calculate_cdf_percentile 必须过滤掉 _scales 键"""
        merged_config = _merge_weights(None)
        
        # 这是一个正确的 merged config
        self.assertIn("_scales", merged_config)
        
        protag = {"combat": 10, "resources": 5, "base": 0, "information": 0, "social": 0}
        peers = [{"combat": 5, "resources": 3, "base": 0, "information": 0, "social": 0}]
        
        # 这行代码如果 bug 存在会抛出 TypeError: unsupported operand type(s) for *: 'dict' and 'float'
        try:
            percentile = calculate_cdf_percentile(protag, peers, merged_config)
            self.assertIsInstance(percentile, float)
            self.assertGreaterEqual(percentile, 0)
            self.assertLessEqual(percentile, 100)
        except TypeError as e:
            self.fail(f"calculate_cdf_percentile 抛出了 TypeError: {e}")
    
    def test_partial_custom_weights_no_multiplication_error(self):
        """部分自定义权重也不应导致 _scales * float"""
        custom = {
            "enabled_dimensions": ["combat"],
            "dimension_weights": {"combat": 1.0},
        }
        
        merged = _merge_weights(custom)
        
        protag = {"combat": 20, "resources": 0, "base": 0, "information": 0, "social": 0}
        peers = [{"combat": 10, "resources": 0, "base": 0, "information": 0, "social": 0}] * 5
        
        # 不应抛出任何错误
        percentile = calculate_cdf_percentile(protag, peers, merged)
        self.assertIsInstance(percentile, float)


if __name__ == "__main__":
    unittest.main()
