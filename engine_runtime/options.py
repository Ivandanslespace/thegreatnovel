"""可选行动的编译与执行适配器。

实际规则仍由 :class:`GameEngine` 负责；该薄层让主持器和测试可以明确
区分"生成候选"与"读取已保存契约"。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


class StrategicCategory(Enum):
    """战略类别分类系统"""
    EXTERNAL_PROGRESS = "external_progress"  # 对外推进：探索新地点、战斗征服、资源获取
    LONG_TERM_DEVELOPMENT = "long_term_development"  # 长期发展：基地建设、科技研究、能力培养
    PLAYER_SOCIAL = "player_social"  # 玩家社交：NPC 互动、关系建立、任务委托
    SURVIVAL_MANAGEMENT = "survival_management"  # 生存管理：休息恢复、物资整理、设施维护


class ActionValueCategory(Enum):
    """选项价值评估维度"""
    STATE_IMPACT = "state_impact"  # 1. 状态影响 (30%)
    LONG_TERM_GROWTH = "long_term_growth"  # 2. 长期成长潜力 (20%)
    COMPARATIVE_MEANING = "comparative_meaning"  # 3. 相对意义 (15%)
    ROUTE_DIFFERENTIATION = "route_differentiation"  # 4. 路线分化 (10%)
    INFO_VALUE = "info_value"  # 5. 情报价值 (10%)
    SOCIAL_FEEDBACK = "social_feedback"  # 6. 社会反馈 (10%)
    REPEAT_PENALTY = "repeat_penalty"  # 重复惩罚 (-)
    MINOR_ACTION_PENALTY = "minor_action_penalty"  # 次要行动惩罚 (-)


@dataclass
class ValueScore:
    """单项价值评分"""
    category: ActionValueCategory
    raw_score: float  # 原始分数 [0-100]
    weighted_score: float  # 加权后分数
    explanation: str = ""  # 评分说明
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "raw_score": round(self.raw_score, 2),
            "weighted_score": round(self.weighted_score, 2),
            "explanation": self.explanation,
        }


@dataclass
class OptionEvaluation:
    """选项完整评估结果"""
    option_id: str
    total_value: float
    base_value: float  # 未应用惩罚前的值
    category_scores: Dict[ActionValueCategory, ValueScore]
    strategic_categories: List[StrategicCategory]
    is_recommended: bool = False
    recommendation_reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "total_value": round(self.total_value, 2),
            "base_value": round(self.base_value, 2),
            "category_scores": {k: v.to_dict() for k, v in self.category_scores.items()},
            "strategic_categories": [c.value for c in self.strategic_categories],
            "is_recommended": self.is_recommended,
            "recommendation_reason": self.recommendation_reason,
        }


class OptionValueCalculator:
    """选项价值计算核心引擎
    
    计算公式：
    value = 
      0.30 * state_impact +              # 状态影响权重
      0.20 * long_term_growth +           # 长期成长权重
      0.15 * comparative_meaning +        # 相对意义权重
      0.15 * route_differentiation +      # 路线分化权重
      0.10 * info_value +                 # 情报价值权重
      0.10 * social_feedback +            # 社会反馈权重
      - repeat_penalty -                  # 重复惩罚
      - minor_action_penalty              # 次要行动惩罚
    """
    
    # 权重配置
    WEIGHTS = {
        ActionValueCategory.STATE_IMPACT: 0.30,
        ActionValueCategory.LONG_TERM_GROWTH: 0.20,
        ActionValueCategory.COMPARATIVE_MEANING: 0.15,
        ActionValueCategory.ROUTE_DIFFERENTIATION: 0.15,
        ActionValueCategory.INFO_VALUE: 0.10,
        ActionValueCategory.SOCIAL_FEEDBACK: 0.10,
    }
    
    # 阈值配置
    THRESHOLDS = {
        "rest_fatigue": 30,          # 疲劳≥30 才推荐休息
        "rest_mental": 65,           # mental≤65 才推荐休息
        "rest_hp_percent": 85,       # HP≤85% 才推荐休息
        "minor_action_energy": 20,   # 消耗<20 精力视为次要动作
        "repeat_threshold": 3,       # 同一标签出现 3 次以上算重复
    }
    
    def __init__(self, game_state: Mapping[str, Any]):
        """初始化计算器
        
        Args:
            game_state: 完整游戏状态字典，包含 player/base/npcs/meta 等
        """
        self.state = game_state
        self.player = game_state.get("player", {})
        self.base = game_state.get("base", {})
        self.npcs = game_state.get("npcs", [])
        self.meta = game_state.get("meta", {})
        
        # NPC 对话新鲜度追踪：{npc_id: {topic: last_turn, cooldown_remaining}}
        self.npc_conversation_freshness: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._load_conversation_history()
    
    def _load_conversation_history(self):
        """从存档加载 NPC 对话历史"""
        conversation_log = self.meta.get("conversation_log", [])
        if not isinstance(conversation_log, list):
            return
            
        for record in conversation_log[-100:]:  # 只查看最近 100 条
            if record.get("type") != "CONVERSATION":
                continue
                
            npc_id = record.get("npc_id")
            topic = record.get("topic")
            turn = record.get("turn")
            
            if npc_id and topic and turn is not None:
                if npc_id not in self.npc_conversation_freshness:
                    self.npc_conversation_freshness[npc_id] = {}
                
                self.npc_conversation_freshness[npc_id][topic] = {
                    "last_turn": turn,
                    "cooldown": 20,  # 默认冷却 20 回合
                }
    
    def calculate_option_value(
        self, 
        option: Mapping[str, Any],
        all_options: List[Mapping[str, Any]],
        current_turn: int
    ) -> OptionEvaluation:
        """计算单个选项的综合价值分
        
        Args:
            option: 当前选项字典
            all_options: 所有候选选项列表（用于比较）
            current_turn: 当前回合数
        
        Returns:
            OptionEvaluation: 完整评估结果
        """
        option_id = option.get("id") or option.get("option_id")
        
        # 1. 计算各维度原始分数 [0-100]
        state_impact_score = self._calc_state_impact(option)
        long_term_growth_score = self._calc_long_term_growth(option)
        comparative_meaning_score = self._calc_comparative_meaning(option, all_options)
        route_diff_score = self._calc_route_differentiation(option, all_options)
        info_value_score = self._calc_info_value(option)
        social_feedback_score = self._calc_social_feedback(option)
        
        # 2. 计算惩罚项
        repeat_penalty = self._calc_repeat_penalty(option, all_options, current_turn)
        minor_action_penalty = self._calc_minor_action_penalty(option)
        
        # 3. 加权求和
        base_value = (
            self.WEIGHTS[ActionValueCategory.STATE_IMPACT] * state_impact_score +
            self.WEIGHTS[ActionValueCategory.LONG_TERM_GROWTH] * long_term_growth_score +
            self.WEIGHTS[ActionValueCategory.COMPARATIVE_MEANING] * comparative_meaning_score +
            self.WEIGHTS[ActionValueCategory.ROUTE_DIFFERENTIATION] * route_diff_score +
            self.WEIGHTS[ActionValueCategory.INFO_VALUE] * info_value_score +
            self.WEIGHTS[ActionValueCategory.SOCIAL_FEEDBACK] * social_feedback_score
        )
        
        total_value = max(0, base_value - repeat_penalty - minor_action_penalty)
        
        # 4. 构建评分详情
        category_scores = {
            ActionValueCategory.STATE_IMPACT: ValueScore(
                ActionValueCategory.STATE_IMPACT,
                state_impact_score,
                self.WEIGHTS[ActionValueCategory.STATE_IMPACT] * state_impact_score,
                self._explain_state_impact(state_impact_score, option),
            ),
            ActionValueCategory.LONG_TERM_GROWTH: ValueScore(
                ActionValueCategory.LONG_TERM_GROWTH,
                long_term_growth_score,
                self.WEIGHTS[ActionValueCategory.LONG_TERM_GROWTH] * long_term_growth_score,
                self._explain_long_term_growth(long_term_growth_score, option),
            ),
            ActionValueCategory.COMPARATIVE_MEANING: ValueScore(
                ActionValueCategory.COMPARATIVE_MEANING,
                comparative_meaning_score,
                self.WEIGHTS[ActionValueCategory.COMPARATIVE_MEANING] * comparative_meaning_score,
                self._explain_comparative_meaning(comparative_meaning_score),
            ),
            ActionValueCategory.ROUTE_DIFFERENTIATION: ValueScore(
                ActionValueCategory.ROUTE_DIFFERENTIATION,
                route_diff_score,
                self.WEIGHTS[ActionValueCategory.ROUTE_DIFFERENTIATION] * route_diff_score,
                self._explain_route_diff(route_diff_score),
            ),
            ActionValueCategory.INFO_VALUE: ValueScore(
                ActionValueCategory.INFO_VALUE,
                info_value_score,
                self.WEIGHTS[ActionValueCategory.INFO_VALUE] * info_value_score,
                self._explain_info_value(info_value_score, option),
            ),
            ActionValueCategory.SOCIAL_FEEDBACK: ValueScore(
                ActionValueCategory.SOCIAL_FEEDBACK,
                social_feedback_score,
                self.WEIGHTS[ActionValueCategory.SOCIAL_FEEDBACK] * social_feedback_score,
                self._explain_social_feedback(social_feedback_score, option),
            ),
        }
        
        # 5. 确定战略类别
        strategic_cats = self._determine_strategic_category(option)
        
        # 6. 判断是否推荐
        is_recommended = total_value >= 60  # 阈值可调整
        recommendation_reason = self._get_recommendation_reason(
            total_value, base_value, repeat_penalty, minor_action_penalty
        )
        
        return OptionEvaluation(
            option_id=option_id,
            total_value=total_value,
            base_value=base_value,
            category_scores=category_scores,
            strategic_categories=strategic_cats,
            is_recommended=is_recommended,
            recommendation_reason=recommendation_reason,
        )
    
    # ==========================================================================
    # 六大价值维度计算
    # ==========================================================================
    
    def _calc_state_impact(self, option: Mapping[str, Any]) -> float:
        """1. 状态影响分数 [0-100]
        
        计算该选项对玩家状态（HP/mental/fatigue/资源等）的改变幅度
        """
        preview = option.get("preview", {})
        resolution = preview.get("resolution", {}) if isinstance(preview.get("resolution"), dict) else {}
        
        # 提取预计的状态改变
        resource_changes = resolution.get("resource_changes", {})
        status_changes = resolution.get("status_changes", {})
        
        score = 0.0
        impact_count = 0
        
        # HP 变化
        if "hp" in resource_changes:
            hp_change = abs(resource_changes["hp"])
            score += min(hp_change * 2, 30)  # 最多 30 分
            impact_count += 1
        
        # Mental 变化
        if "mental" in resource_changes:
            mental_change = abs(resource_changes["mental"])
            score += min(mental_change * 1.5, 25)  # 最多 25 分
            impact_count += 1
        
        # Fatigue 变化
        if "fatigue" in resource_changes:
            fatigue_change = abs(resource_changes["fatigue"])
            score += min(fatigue_change, 20)  # 最多 20 分
            impact_count += 1
        
        # 资源获取
        resources = ["fuel", "materials", "food", "ammo", "experience"]
        for res in resources:
            if res in resource_changes and resource_changes[res] > 0:
                score += min(resource_changes[res] * 2, 15)
                impact_count += 1
        
        # 等级/属性提升
        if "level" in status_changes:
            score += 25
            impact_count += 1
        if "attributes" in status_changes:
            attr_changes = status_changes["attributes"]
            score += len(attr_changes) * 8
            impact_count += 1
        
        # 归一化到 [0-100]
        if impact_count == 0:
            return 0.0
        
        normalized = min(100, score * (5 / impact_count))  # 期望 5 个影响维度
        return normalized
    
    def _calc_long_term_growth(self, option: Mapping[str, Any]) -> float:
        """2. 长期成长潜力 [0-100]
        
        计算该选项对未来发展的长期收益（解锁新内容、能力培养、基地建设等）
        """
        action_type = option.get("action", {}).get("type")
        action_id = option.get("action", {}).get("action_id", "")
        goal = option.get("goal", "") or option.get("description", "")
        
        score = 0.0
        
        # 基地建设类
        if action_type in {"BUILD", "RESEARCH", "UPGRADE"}:
            score += 60  # 基础高分
            # 检查解锁的新模块
            modules_unlocked = option.get("modules_unlocked", [])
            score += min(len(modules_unlocked) * 15, 40)
        
        # 技能学习类
        elif action_type == "LEARN_SKILL":
            skill_rarity = option.get("skill_rarity", "C")
            rarity_scores = {"S": 70, "A": 60, "B": 50, "C": 40, "D": 30}
            score += rarity_scores.get(skill_rarity, 40)
        
        # 探索新地点
        elif action_type in {"EXPLORE", "ENTER_LOCATION", "TRAVEL"}:
            location_value = option.get("location_value", 50)
            discovery_potential = option.get("discovery_potential", False)
            score = location_value * 0.6 + (70 if discovery_potential else 40)
        
        # 完成重大任务
        elif action_type == "COMPLETE_QUEST":
            quest_reward = option.get("quest_reward", {})
            xp_gain = quest_reward.get("experience", 0)
            score = min(xp_gain / 5, 80)  # 每 5XP 加 1 分，最高 80
        
        # 关系深化
        elif action_type == "SOCIAL_INTERACTION":
            relationship_goal = option.get("relationship_goal")
            if relationship_goal and relationship_goal.get("target_level"):
                score = relationship_goal.get("target_level") * 2  # 目标好感度*2
        
        #  talent 解锁
        elif "talent" in action_id.lower() or "解锁天赋" in goal:
            score += 75
        
        return min(100, score)
    
    def _calc_comparative_meaning(self, option: Mapping[str, Any], all_options: List[Mapping[str, Any]]) -> float:
        """3. 相对意义 [0-100]
        
        计算该选项在玩家群体中的相对价值和稀缺性
        """
        if not all_options:
            return 50.0  # 默认中等分数
        
        action_type = option.get("action", {}).get("type")
        
        # 统计各类别选项数量
        type_counts: Dict[str, int] = {}
        for opt in all_options:
            t = opt.get("action", {}).get("type", "UNKNOWN")
            type_counts[t] = type_counts.get(t, 0) + 1
        
        # 稀缺类型加分
        type_count = type_counts.get(action_type, 1)
        if type_count <= 1:
            return 90.0  # 唯一选项
        elif type_count == 2:
            return 75.0  # 少数选项
        elif type_count <= 3:
            return 60.0  # 较少选项
        else:
            # 常见选项，根据预期收益调整
            resolution = option.get("preview", {}).get("resolution", {})
            xp_reward = resolution.get("total_experience", 0)
            return max(30, min(55, 50 + xp_reward / 20))
    
    def _calc_route_differentiation(self, option: Mapping[str, Any], all_options: List[Mapping[str, Any]]) -> float:
        """4. 路线分化度 [0-100]
        
        计算该选项与其他选项的本质差异度（不同玩法路线）
        """
        if len(all_options) < 2:
            return 50.0
        
        action_type = option.get("action", {}).get("type")
        target = option.get("action", {}).get("target", "")
        
        # 计算策略距离矩阵
        strategy_distances: Dict[str, float] = {}
        
        for other_opt in all_options:
            other_type = other_opt.get("action", {}).get("type", "")
            other_target = other_opt.get("action", {}).get("target", "")
            
            if other_type == action_type and other_target == target:
                distance = 0.0  # 完全相同
            elif other_type == action_type:
                distance = 30.0  # 同类但不同目标
            elif self._are_related_types(action_type, other_type):
                distance = 60.0  # 相关类型
            else:
                distance = 100.0  # 完全不同路线
            
            # 累加距离
            strategy_distances[id(other_opt)] = distance
        
        # 返回平均距离作为差异化度
        if not strategy_distances:
            return 50.0
        
        avg_distance = sum(strategy_distances.values()) / len(strategy_distances)
        return avg_distance
    
    def _are_related_types(self, type1: str, type2: str) -> bool:
        """判断两个动作类型是否相关"""
        related_groups = [
            {"EXPLORE", "ENTER_LOCATION", "TRAVEL"},  # 移动探索组
            {"COMBAT", "BATCH_ACTION"},  # 战斗清理组
            {"BUILD", "RESEARCH", "UPGRADE"},  # 发展建设组
            {"SOCIAL_INTERACTION"},  # 社交组
            {"REST", "BASE_MANAGEMENT", "SHORT_ACTION"},  # 后勤组
        ]
        
        set1 = {type1}
        set2 = {type2}
        
        for group in related_groups:
            if set1 & group and set2 & group:
                return True
        
        return False
    
    def _calc_info_value(self, option: Mapping[str, Any]) -> float:
        """5. 情报价值 [0-100]
        
        计算该选项提供的信息量和新知识
        """
        action_type = option.get("action", {}).get("type")
        preview = option.get("preview", {})
        
        score = 0.0
        
        # 发现新地点
        if action_type in {"EXPLORE", "ENTER_LOCATION"}:
            discovered_locations = preview.get("discovered_locations", [])
            unknown_location_ratio = preview.get("unknown_location_ratio", 0)
            score = min(len(discovered_locations) * 30 + unknown_location_ratio * 40, 95)
        
        # NPC 知识解锁
        elif action_type == "SOCIAL_INTERACTION":
            knowledge_additions = preview.get("knowledge_additions", [])
            npc_backstory_unlocked = preview.get("npc_backstory_unlocked", False)
            score = len(knowledge_additions) * 25 + (50 if npc_backstory_unlocked else 0)
        
        # 世界情报
        world_secrets = preview.get("world_secrets_revealed", [])
        lore_entries = preview.get("lore_entries", [])
        score += len(world_secrets) * 35 + len(lore_entries) * 20
        
        return min(100, score)
    
    def _calc_social_feedback(self, option: Mapping[str, Any]) -> float:
        """6. 社会反馈 [0-100]
        
        计算该选项的社交相关收益（NPC 评价、关系提升、群体认可）
        """
        action_type = option.get("action", {}).get("type")
        preview = option.get("preview", {})
        
        if action_type != "SOCIAL_INTERACTION":
            return 20.0  # 非社交动作低分
        
        relationship_bonus = preview.get("relationship_bonus", {})
        npc_approval = preview.get("npc_approval_gained", [])
        reputation_changes = preview.get("reputation_changes", {})
        
        score = 0.0
        
        # 关系提升
        for npc_id, change in relationship_bonus.items():
            score += min(change * 2, 40)  # 好感度变化*2
        
        # NPC 认可
        score += len(npc_approval) * 25
        
        #  faction 声望
        for faction, change in reputation_changes.items():
            score += abs(change) * 3
        
        return min(100, score)
    
    # ==========================================================================
    # 惩罚项计算
    # ==========================================================================
    
    def _calc_repeat_penalty(self, option: Mapping[str, Any], all_options: List[Mapping[str, Any]], current_turn: int) -> float:
        """重复惩罚 [-30~0]
        
        连续做同类选项多次时扣分
        """
        option_id = option.get("id") or option.get("option_id")
        action_type = option.get("action", {}).get("type")
        
        # 统计该选项之前在本局游戏中出现的次数
        recent_actions = self.meta.get("recent_actions", [])[:20]  # 最近 20 次
        repeat_count = sum(
            1 for action in recent_actions
            if action.get("type") == action_type and action.get("turn", 0) > current_turn - 10
        )
        
        if repeat_count < 2:
            return 0.0
        
        # 每多一次扣 10-15 分
        penalty = repeat_count * 12
        return min(penalty, 30.0)
    
    def _calc_minor_action_penalty(self, option: Mapping[str, Any]) -> float:
        """次要动作惩罚 [-10~0]
        
        对那些效果微弱、消耗极小的动作扣分
        """
        preview = option.get("preview", {})
        resolution = preview.get("resolution", {}) if isinstance(preview.get("resolution"), dict) else {}
        
        # 检查能量消耗
        resource_changes = resolution.get("resource_changes", {})
        fatigue_cost = resource_changes.get("fatigue", 0)
        
        # 检查收益规模
        total_xp = resolution.get("total_experience", 0)
        resources_gained = sum(v for k, v in resource_changes.items() if v > 0 and k not in {"fatigue", "mental", "hp"})
        
        # 如果消耗极少 (<10 fatigue) 且收益很小 (<20 XP)
        if fatigue_cost < 10 and total_xp < 20 and resources_gained < 15:
            return 8.0  # 小动作惩罚
        
        return 0.0
    
    # ==========================================================================
    # 解释器
    # ==========================================================================
    
    def _explain_state_impact(self, score: float, option: Mapping[str, Any]) -> str:
        if score < 30:
            return "状态影响较小，短期收益有限"
        elif score < 60:
            return "有一定的状态改变，适合当前急需"
        else:
            return "状态影响显著，能明显改善处境"
    
    def _explain_long_term_growth(self, score: float, option: Mapping[str, Any]) -> str:
        if score < 30:
            return "长期成长价值较低"
        elif score < 60:
            return "提供稳定的中期发展机会"
        else:
            return "重要的长期投资，开启新能力或内容"
    
    def _explain_comparative_meaning(self, score: float) -> str:
        if score < 40:
            return "同类选项中表现普通"
        elif score < 70:
            return "在同阶玩家中具有竞争力"
        else:
            return "稀缺选择，同批玩家中少有尝试"
    
    def _explain_route_diff(self, score: float) -> str:
        if score < 40:
            return "与其他选项路线重合度高"
        elif score < 70:
            return "有一定差异化但属于相似风格"
        else:
            return "独特路线，开辟全新的玩法方向"
    
    def _explain_info_value(self, score: float, option: Mapping[str, Any]) -> str:
        if score < 30:
            return "信息增量有限"
        elif score < 60:
            return "提供有价值的区域情报"
        else:
            return "关键情报来源，可能揭示重要秘密"
    
    def _explain_social_feedback(self, score: float, option: Mapping[str, Any]) -> str:
        if score < 30:
            return "社交收益微薄"
        else:
            return "重要的关系建立机会"
    
    def _get_recommendation_reason(
        self, 
        total_value: float, 
        base_value: float, 
        repeat_penalty: float,
        minor_penalty: float
    ) -> str:
        if total_value >= 80:
            return "强烈推荐：综合价值极高"
        elif total_value >= 60:
            if repeat_penalty > 10:
                return f"价值不错但因近期重复已扣 {repeat_penalty:.1f}分"
            return "值得考虑：符合当前需求"
        elif total_value >= 40:
            return "备选方案：仅在特殊情况下选择"
        else:
            if minor_penalty > 0:
                return f"不推荐：效果过于微弱，已扣 {minor_penalty:.1f}分"
            return "避免选择：价值过低"
    
    # ==========================================================================
    # 战略类别判定
    # ==========================================================================
    
    def _determine_strategic_category(self, option: Mapping[str, Any]) -> List[StrategicCategory]:
        """根据选项特征判定所属的战略类别"""
        categories = []
        action_type = option.get("action", {}).get("type")
        
        # External Progress: 对外推进型
        if action_type in {
            "EXPLORE", "ENTER_LOCATION", "TRAVEL", "EXTRACT",
            "COMBAT", "BATCH_ACTION", "HUNT"
        }:
            categories.append(StrategicCategory.EXTERNAL_PROGRESS)
        
        # Long-term Development: 长期发展型
        if action_type in {"BUILD", "RESEARCH", "UPGRADE", "LEARN_SKILL"}:
            categories.append(StrategicCategory.LONG_TERM_DEVELOPMENT)
        
        # Player Social: 社交互动型
        if action_type == "SOCIAL_INTERACTION":
            categories.append(StrategicCategory.PLAYER_SOCIAL)
        
        # Survival Management: 生存管理类
        if action_type in {"REST", "BASE_MANAGEMENT", "SHORT_ACTION", "WAIT"}:
            categories.append(StrategicCategory.SURVIVAL_MANAGEMENT)
        
        # 默认：如果没有匹配，根据目标和描述推断
        if not categories:
            goal = option.get("goal", "") or option.get("description", "")
            if any(kw in goal.lower() for kw in ["build", "upgrade", "research"]):
                categories.append(StrategicCategory.LONG_TERM_DEVELOPMENT)
            elif any(kw in goal.lower() for kw in ["explore", "travel", "combat"]):
                categories.append(StrategicCategory.EXTERNAL_PROGRESS)
        
        return categories if categories else [StrategicCategory.SURVIVAL_MANAGEMENT]


class OptionCompiler:
    """选项编译器的基础实现
    
    职责：
    - 将候选选项编译为可执行格式
    - 进行合法性验证
    - 生成选项标签和描述
    
    子类（如 OptionDirector）可以重写此方法增加额外的编排逻辑
    """
    
    def __init__(self, engine):
        """初始化编译器
        
        Args:
            engine: GameEngine 实例，提供编译所需的底层能力
        """
        self.engine = engine
    
    def compile(self, candidates: list[Mapping[str, Any]], *, persist: bool = True):
        """编译候选选项列表
        
        Args:
            candidates: 候选选项列表，每个元素为 Mapping 类型
            persist: 是否持久化到事件日志
        
        Returns:
            Dict[str, Any]: 编译结果，包含 options、contracts 等字段
        """
        return self.engine.compile_options(candidates, persist=persist)
    
    compile_candidates = compile
    
    def present(self, candidates: list[Mapping[str, Any]], *, persist: bool = True):
        """展示候选选项（用于测试接口）
        
        Args:
            candidates: 候选选项列表
            persist: 是否持久化
        
        Returns:
            List[Dict]: 格式化后的选项列表
        """
        result = self.compile(candidates, persist=persist)
        return result["options"]
    
    def preview(self, option_id: str):
        """预览选项的执行效果
        
        Args:
            option_id: 选项 ID
        
        Returns:
            Dict: 预览结果，包含预期状态改变等信息
        """
        return self.engine.preview_player_choice(option_id)
    
    def execute(self, option_id: str, *, persist: bool = True):
        """执行选定的选项
        
        Args:
            option_id: 选项 ID
            persist: 是否持久化
        
        Returns:
            Dict: 执行结果，包含实际发生的事件
        """
        return self.engine.execute_player_choice(option_id, persist=persist)


class OptionDirector(OptionCompiler):
    """高级选项导演系统
    
    职责：
    1. 为每个候选选项计算价值评分
    2. 过滤掉低价值选项
    3. 确保最终选项的战略多样性
    4. 实施 REST 等 gating 机制
    5. 追踪 NPC 对话新鲜度
    
    核心功能：
    - REST gating: fatigue>=30 OR mental<=65 OR HP<=85% OR night phase
    - NPC 话题新鲜度衰减追踪（默认冷却 20 回合）
    - 战略类别平衡：最终 3 个选项来自至少 3 个不同类别
    """
    
    def __init__(self, engine):
        super().__init__(engine)
        self.enabled = True  # 总开关
        self.min_value_threshold = 40  # 最低展示阈值
        self.min_categories_in_top3 = 3  # 前 3 个选项必须来自的最少类别数
    
    def compile(self, candidates: list[Mapping[str, Any]], *, persist: bool = True):
        """重写 compile 方法，加入价值评估和战略平衡"""
        if not self.enabled:
            # 直接委托给上层，不做额外处理
            return self.engine.compile_options(candidates, persist=persist)
        
        # 1. 先调用引擎的基础编译逻辑
        basic_result = self.engine.compile_options(candidates, persist=False)
        compiled_options = basic_result.get("contracts", {})
        
        if not compiled_options:
            return basic_result
        
        # CRITICAL SECURITY LAYER: Block reader-knowledge-dependent options BEFORE value scoring
        filtered_options = self.filter_invalid_perspective_options(compiled_options)
        if not filtered_options:
            # All options were filtered out due to perspective violations
            return basic_result
        
        # Update compiled_options to use the filtered set
        compiled_options = filtered_options
        
        # 2. 创建价值计算器
        calculator = OptionValueCalculator(self.engine.state.data)
        
        # 3. 为每个选项计算价值
        all_options_list = list(compiled_options.values())
        evaluations = []
        
        for option_id, option in compiled_options.items():
            evaluation = calculator.calculate_option_value(
                option,
                all_options_list,
                self.engine.state.current_turn
            )
            
            # 4. 应用 REST gating
            if option.get("action", {}).get("type") == "REST":
                if not self._should_allow_rest(evaluation, calculator):
                    evaluation.total_value = 0  # 强制过滤
                    evaluation.is_recommended = False
            
            evaluations.append((option_id, option, evaluation))
        
        # 5. 按总分排序
        evaluations.sort(key=lambda x: x[2].total_value, reverse=True)
        
        # 6. 战略类别平衡筛选
        filtered_evaluations = self._apply_strategic_balance(
            evaluations, 
            calculator
        )
        
        # 7. 应用最低阈值过滤
        final_options = {
            opt_id: opt for opt_id, opt, eval in filtered_evaluations
            if eval.total_value >= self.min_value_threshold
        }
        
        # 8. 重新编译最终选项
        final_compiled = {
            opt_id: compiled_options[opt_id] 
            for opt_id in final_options
        }
        
        # 9. 构建返回结果
        result = basic_result.copy()
        result["contracts"] = final_compiled
        result["evaluations"] = {
            opt_id: eval.to_dict() 
            for opt_id, _, eval in filtered_evaluations
        }
        result["selection_reasons"] = {
            opt_id: eval.recommendation_reason
            for opt_id, _, eval in filtered_evaluations
        }
        
        # 10. 持久化
        if persist:
            event = basic_result.get("event")
            if event:
                self.engine.state.apply_and_append(event, persist=True)
                self.engine.state.save()
        
        return result
    
    def filter_invalid_perspective_options(self, compiled_options: Dict[str, Any]) -> Dict[str, Any]:
        """过滤掉依赖读者独占知识的非法选项。
        
        这是防止玩家通过叙事插叙作弊的关键安全层。必须在选项值评分之前调用。
        
        检查逻辑：
        1. 从 meta.cutaway_contexts 获取所有当前活跃的插叙线程
        2. 收集每个活跃插叙中读者已知但主角未知的信息
        3. 过滤掉任何仅依赖这些"读者独占知识"的选项
        4. 保留所有不依赖知识要求或主角已知知识的选项
        
        Args:
            compiled_options: 已编译的选项合同字典
            
        Returns:
            过滤后的选项合同字典，移除了违反视角限制的选项
        """
        state = self.engine.state
        meta = state.data.get("meta", {})
        
        # 获取所有当前活跃的插叙线程中的读者独占知识
        cutaway_contexts = meta.get("cutaway_contexts", [])
        if not isinstance(cutaway_contexts, list):
            cutaway_contexts = []
        
        reader_known_items = set()
        for ctx in cutaway_contexts:
            if isinstance(ctx, dict) and ctx.get("status") == "active":
                # 添加插叙中读者知道的所有项目/事实
                reader_known_items.update(ctx.get("reader_knows", []))
                # 添加读者知道的 NPC 存在性和附近性信息
                reader_id = ctx.get("reader_id", "")
                if reader_id:
                    reader_known_items.add(f"{reader_id}_exists")
                    reader_known_items.add(f"{reader_id}_is_nearby")
        
        # 获取主角实际知晓的知识
        protagonist_knowledge = set(state.player.get("knowledge", []))
        if not isinstance(protagonist_knowledge, set):
            protagonist_knowledge = set(str(k) for k in protagonist_knowledge)
        
        # 过滤掉其requirements仅依赖读者知识的选项
        valid_options = {}
        
        for opt_id, contract in compiled_options.items():
            if not isinstance(contract, dict):
                continue
                
            action = contract.get("action", {})
            requirements = action.get("requirements", {})
            required_knowledge = requirements.get("knowledge", [])
            
            # 无知识要求的选项自动保留
            if not required_knowledge:
                valid_options[opt_id] = contract
                continue
            
            # 检查是否有知识要求不在主角知识集中
            req_list = [required_knowledge] if isinstance(required_knowledge, str) else required_knowledge
            has_violation = False
            
            for req_key in req_list:
                req_key_str = str(req_key)
                # 如果该知识是读者独占的（读者知道但主角不知道）
                if req_key_str in reader_known_items and req_key_str not in protagonist_knowledge:
                    has_violation = True
                    break
            
            # 仅在无违规时保留选项
            if not has_violation:
                valid_options[opt_id] = contract
        
        return valid_options
    
    def _should_allow_rest(self, evaluation: OptionEvaluation, calculator: OptionValueCalculator) -> bool:
        """判断是否应该允许展示 REST 选项
        
        Gating 条件：
        - fatigue ≥ 30 OR
        - mental ≤ 65 OR  
        - HP ≤ 85% OR
        - 夜晚阶段
        """
        player = calculator.player
        
        # 疲劳阈值
        if player.get("fatigue", 0) >= 30:
            return True
        
        # Mental 阈值
        if player.get("mental", 100) <= 65:
            return True
        
        # HP 百分比
        hp = player.get("hp", 100)
        max_hp = player.get("max_hp", 100)
        if max_hp > 0 and (hp / max_hp) <= 0.85:
            return True
        
        # 夜晚阶段
        time_of_day = self.engine.state.meta.get("time_of_day", "")
        if time_of_day in {"黄昏", "夜晚", "深夜"}:
            return True
        
        return False
    
    def _apply_strategic_balance(
        self,
        evaluations: List[tuple],
        calculator: OptionValueCalculator
    ) -> List[tuple]:
        """应用战略多样性筛选
        
        确保前 3 个选项来自至少 3 个不同的战略类别
        """
        if len(evaluations) <= self.min_categories_in_top3:
            return evaluations
        
        # 分组
        by_category: Dict[StrategicCategory, List[tuple]] = {}
        remaining = []
        
        for opt_id, opt, eval in evaluations:
            cats = eval.strategic_categories
            if cats:
                # 取第一个类别为主类别
                main_cat = cats[0]
                if main_cat not in by_category:
                    by_category[main_cat] = []
                by_category[main_cat].append((opt_id, opt, eval))
            else:
                remaining.append((opt_id, opt, eval))
        
        # 逐步填充，确保每个类别至少有一个
        result = []
        selected_categories = set()
        
        # 第一轮：每个类别选最高的
        for cat_opts in by_category.values():
            cat_opts.sort(key=lambda x: x[2].total_value, reverse=True)
            top_opt = cat_opts[0]
            result.append(top_opt)
            selected_categories.update(top_opt[2].strategic_categories)
        
        # 第二轮：剩余按分数排序加入
        others = []
        for cat_opts in by_category.values():
            others.extend(cat_opts[1:])
        others.extend(remaining)
        others.sort(key=lambda x: x[2].total_value, reverse=True)
        
        result.extend(others)
        
        # 验证前 3 个是否满足多样性要求
        if len(result) >= 3:
            top3_cats = set()
            for opt_id, opt, eval in result[:3]:
                top3_cats.update(eval.strategic_categories)
            
            if len(top3_cats) < self.min_categories_in_top3:
                # 需要替换：从其他类别中找更高的
                self._fix_strategic_violation(result, by_category, top3_cats)
        
        return result
    
    def _fix_strategic_violation(
        self,
        result: List[tuple],
        by_category: Dict[StrategicCategory, List[tuple]],
        top3_current_cats: set
    ):
        """修复前 3 个选项的战略性违规"""
        all_cats = set(by_category.keys())
        missing_cats = all_cats - top3_current_cats
        
        if not missing_cats:
            return
        
        # 从缺失的类别中替换进前 3
        for missing_cat in missing_cats:
            if len(result) < 3 or len(top3_current_cats) >= self.min_categories_in_top3:
                break
            
            # 找到这个类别中分数最高的且不在前 3 的选项
            for opt_id, opt, eval in by_category[missing_cat]:
                in_top3 = opt_id in [x[0] for x in result[:3]]
                if not in_top3:
                    # 替换第 3 个位置
                    result[2] = (opt_id, opt, eval)
                    top3_current_cats.add(missing_cat)
                    break
