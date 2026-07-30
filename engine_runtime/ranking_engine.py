"""全民系统 CDF 排名计算引擎 - 极简版本

核心目标：用真实 peer pool 分布计算百分位，替代旧的 fake formula。
设计原则：Karpathy guidelines - 最少代码，无推测性功能。
"""

from typing import Dict, List, Any


# 五维权重配置
WEIGHTS = {
    "combat": 0.30,
    "resources": 0.25,
    "base": 0.20,
    "information": 0.15,
    "social": 0.10
}


def calculate_dimension_scores(action_result: Dict[str, Any]) -> Dict[str, float]:
    """将行动结果分解为五个绩效维度得分
    
    Args:
        action_result: 行动结算结果字典
        
    Returns:
        包含 combat/resources/base/information/social 的得分字典
    """
    scores = {k: 0.0 for k in WEIGHTS.keys()}
    
    # Combat 维度
    if action_result.get("action_type") == "COMBAT":
        scores["combat"] = action_result.get("damage_dealt", 0) * 0.1
    
    # Resources 维度
    resources = sum((action_result.get("resources_obtained", {}) or {}).values())
    if resources > 0:
        scores["resources"] = resources * 0.5
    
    # Base 维度
    if action_result.get("structures_built", 0) > 0:
        scores["base"] = 20.0
    
    # Information 维度
    if action_result.get("locations_discovered", 0) > 0:
        scores["information"] = 25.0
    
    # Social 维度
    if action_result.get("alliances_formed", 0) > 0:
        scores["social"] = 20.0
    
    return scores


def calculate_cdf_percentile(protag_scores: Dict[str, float], 
                            peer_scores_list: List[Dict[str, float]]) -> float:
    """使用 CDF 计算主角相对于 peer pool 的百分位
    
    算法：对每个维度，计算有多少 peers 的分数严格低于主角，加权平均。
    
    Args:
        protag_scores: 主角的五维得分
        peer_scores_list: peer pool 的得分列表
        
    Returns:
        百分位值 (0-100)
    """
    if not peer_scores_list:
        return 50.0  # 无对比数据，返回中性位置
    
    weighted_sum = 0.0
    n_peers = len(peer_scores_list)
    
    for dim, weight in WEIGHTS.items():
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
    "WEIGHTS",
    "calculate_dimension_scores",
    "calculate_cdf_percentile",
    "convert_percentile_to_rank",
    "simulate_peer_actions",
]
