"""全民系统 CDF 排名计算引擎 - 极简版本

核心目标：用真实 peer pool 分布计算百分位，替代旧的 fake formula。
设计原则：Karpathy guidelines - 最少代码，无推测性功能。
"""

from collections import defaultdict
from typing import Dict, List, Any, Optional, Mapping


# 五维权重配置 (默认值，可由世界覆盖)
DEFAULT_RANKING_WEIGHTS = {
    "combat": 0.30,
    "resources": 0.25,
    "base": 0.20,
    "information": 0.15,
    "social": 0.10
}

# 维度尺度配置 (默认乘数/bonuses)
DEFAULT_RANKING_SCALES = {
    "combat_multiplier": 0.1,
    "resource_multiplier": 0.5,
    "base_bonus": 20.0,
    "information_bonus": 25.0,
    "social_bonus": 20.0
}


def _merge_weights(custom_scales: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Merge custom scales over default weights/scales.
    
    Args:
        custom_scales: Optional custom scales dict from world config
                       Can be either:
                       - Raw ranking config dict (with enabled_dimensions/dimension_weights/dimension_scales)
                       - Already-merged validated config dict (with weights + _scales key)
        
    Returns:
        Merged weight/scale configuration
    """
    if custom_scales is None:
        return DEFAULT_RANKING_WEIGHTS.copy()
    
    # Check if this is already a merged config (has _scales or all dimension keys)
    has_scaled_keys = isinstance(custom_scales.get("_scales"), Mapping)
    has_dimension_keys = all(dim in custom_scales for dim in DEFAULT_RANKING_WEIGHTS.keys())
    
    if has_scaled_keys or has_dimension_keys:
        # This is an already-merged config from validation
        merged = defaultdict(float, DEFAULT_RANKING_WEIGHTS.copy())
        
        # Override with custom weights for enabled dimensions
        for dim in list(DEFAULT_RANKING_WEIGHTS.keys()):
            if dim in custom_scales and "_scales" not in str(type(custom_scales)):
                val = custom_scales[dim]
                if isinstance(val, (int, float)) and not str(val).startswith("_"):
                    merged[dim] = float(val)
        
        # Override scales
        base_scales = DEFAULT_RANKING_SCALES.copy()
        custom_dim_scales = dict(custom_scales["_scales"]) if isinstance(custom_scales.get("_scales"), Mapping) else {}
        base_scales.update(custom_dim_scales)
        
        # Merge scales into weights dict (with special key prefix)
        for key, value in base_scales.items():
            if isinstance(value, (int, float)):
                merged[key] = float(value)
        
        return dict(merged)
    
    # This looks like it might be just weights without scales structure
    # Try to detect if it's actually a simple weight dict
    appears_to_be_weights_only = all(
        isinstance(v, (int, float)) 
        for k, v in custom_scales.items() 
        if k in DEFAULT_RANKING_WEIGHTS.keys()
    ) and len([k for k in custom_scales if k in DEFAULT_RANKING_WEIGHTS.keys()]) > 0
    
    if appears_to_be_weights_only:
        # Treat as raw weights only (backward compatibility test case)
        merged = DEFAULT_RANKING_WEIGHTS.copy()
        for dim in DEFAULT_RANKING_WEIGHTS:
            if dim in custom_scales and isinstance(custom_scales[dim], (int, float)):
                merged[dim] = float(custom_scales[dim])
        return merged
    
    # Default to no override
    return DEFAULT_RANKING_WEIGHTS.copy()


def calculate_dimension_scores(action_result: Dict[str, Any], 
                                custom_config: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """将行动结果分解为五个绩效维度得分
    
    Args:
        action_result: 行动结算结果字典
        custom_config: 可选的世界自定义排名配置 (来自 generation_bundle.ranking_config)
        
    Returns:
        包含 combat/resources/base/information/social 的得分字典
    """
    # Merge custom config with defaults
    scales = _merge_weights(custom_config)
    
    scores = {k: 0.0 for k in DEFAULT_RANKING_WEIGHTS.keys()}
    
    # Get scaling factors from merged config
    combat_multiplier = scales.get("combat_multiplier", 0.1)
    resource_multiplier = scales.get("resource_multiplier", 0.5)
    base_bonus = scales.get("base_bonus", 20.0)
    information_bonus = scales.get("information_bonus", 25.0)
    social_bonus = scales.get("social_bonus", 20.0)
    
    # Combat 维度
    if action_result.get("action_type") == "COMBAT":
        scores["combat"] = action_result.get("damage_dealt", 0) * combat_multiplier
    
    # Resources 维度
    resources = sum((action_result.get("resources_obtained", {}) or {}).values())
    if resources > 0:
        scores["resources"] = resources * resource_multiplier
    
    # Base 维度
    if action_result.get("structures_built", 0) > 0:
        scores["base"] = base_bonus
    
    # Information 维度
    if action_result.get("locations_discovered", 0) > 0:
        scores["information"] = information_bonus
    
    # Social 维度
    if action_result.get("alliances_formed", 0) > 0:
        scores["social"] = social_bonus
    
    return scores


def calculate_cdf_percentile(protag_scores: Dict[str, float], 
                            peer_scores_list: List[Dict[str, float]],
                            custom_weights: Optional[Dict[str, float]] = None) -> float:
    """使用 CDF 计算主角相对于 peer pool 的百分位
    
    算法：对每个维度，计算有多少 peers 的分数严格低于主角，加权平均。
    
    Args:
        protag_scores: 主角的五维得分
        peer_scores_list: peer pool 的得分列表
        custom_weights: 可选的世界自定义权重 (来自 _merge_weights result)
        
    Returns:
        百分位值 (0-100)
    """
    if not peer_scores_list:
        return 50.0  # 无对比数据，返回中性位置
    
    # Use custom weights if provided, otherwise default
    weights = dict(custom_weights) if custom_weights else DEFAULT_RANKING_WEIGHTS.copy()
    
    weighted_sum = 0.0
    n_peers = len(peer_scores_list)
    
    for dim, weight in weights.items():
        protag_val = protag_scores.get(dim, 0.0)
        below = sum(1 for p in peer_scores_list if p.get(dim, 0.0) < protag_val - 1e-9)
        dim_pct = below / n_peers
        weighted_sum += weight * dim_pct
    
    return round(weighted_sum * 100, 2)


def convert_percentile_to_rank(percentile: float, region_size: int) -> int:
    """将百分位转换为排名数字"""
    rank = region_size - int(region_size * percentile / 100) + 1
    return max(1, min(rank, region_size))


def simulate_peer_actions(peer_pool: List[Any]) -> List[Dict[str, Any]]:
    """模拟 peer 行动 - 当前为占位符，返回空列表
    
    后续阶段可扩展为真实的 peer 行动模拟。
    """
    return []


# 导出公开 API
__all__ = [
    "DEFAULT_RANKING_WEIGHTS",
    "DEFAULT_RANKING_SCALES",
    "_merge_weights",
    "calculate_dimension_scores",
    "calculate_cdf_percentile",
    "convert_percentile_to_rank",
    "simulate_peer_actions",
]
