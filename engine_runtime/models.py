"""引擎输入/输出模型。

输入继续接受 YAML 映射，以便兼容现有存档；输出使用 dataclass，避免把
尚未结算的中间值藏在叙述文本里。

第十九轮对话新增：支持全民系统投放类型的数据模型
- PeerPopulationResolution: 同批玩家群体状态
- ComparativeResolution: 主角与同类玩家的比较结果  
- PublicSystemFeedback: 公共系统（排行、公告、频道）反馈
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class ActionContext:
    action_id: str = "action"
    primary_attribute: str = "spirit"
    target_difficulty: float = 20.0
    preparation: float = 0.0
    intelligence: float = 0.0
    teammate_assistance: float = 0.0
    environment_advantage: float = 0.0
    environment_penalty: float = 0.0
    time_pressure: float = 0.0
    unknown_risk: float = 0.0
    resource_shortage: float = 0.0
    continuous_errors: float = 0.0
    survival_assets: float = 0.0
    skill_bonus: float = 0.0
    equipment_bonus: Optional[float] = None
    ability_match: Optional[float] = None
    strength: float = 5.0
    constitution: float = 5.0
    agility: float = 5.0
    spirit: float = 5.0
    risk_warning: float = 0.0
    causal_chain: float = 0.0
    avoidable: float = 0.0
    rule_consistency: float = 0.0
    player_responsibility: float = 0.0
    difficulty_mode: str = "标准"
    seed: str = ""


# ============================================================================
# 全民系统流专用数据模型（第十九轮对话核心改进）
# ============================================================================

@dataclass
class PeerPopulationResolution:
    """同批玩家群体的推进结果
    
    用来模拟一批普通玩家在同一回合的发展情况，作为主角的参照系
    """
    region_id: str
    population_before: int  # 本轮开始时存活人数
    population_after: int  # 本轮结束后存活人数
    deaths: int  # 死亡人数
    advancement_distribution: Dict[str, float]  # 进展分布 percentiles: {10, 25, 50, 75, 90}
    notable_players: List[Dict[str, Any]]  # 本轮回有特殊表现的玩家列表
    achievements_unlocked: int  # 解锁成就数
    first_achievements: List[Dict[str, str]]  # 首杀/首建等记录
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "region_id": self.region_id,
            "population_before": self.population_before,
            "population_after": self.population_after,
            "deaths": self.deaths,
            "advancement_distribution": self.advancement_distribution,
            "notable_players": self.notable_players,
            "achievements_unlocked": self.achievements_unlocked,
            "first_achievements": self.first_achievements,
        }


@dataclass
class ComparativeResolution:
    """主角与同类玩家的比较结果
    
    计算主角在相同阶段、相似资源条件下的相对位置
    """
    protagonist_action_id: str
    matched_peer_count: int  # 匹配的同阶玩家数量
    peer_median_performance: float  # 普通玩家中位表现分
    protagonist_performance: float  # 主角表现分
    percentile: float  # 主角百分位 (0-100)
    power_percentile: Optional[float] = None  # 战斗力分位
    resource_percentile: Optional[float] = None  # 资源积累分位
    base_percentile: Optional[float] = None  # 基地建设分位
    information_percentile: Optional[float] = None  # 情报获取分位
    comparative_result: str = "near_peer_median"  # above/below/near_peer_median
    main_causes: List[str] = field(default_factory=list)  # 领先/落后的主要原因
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "protagonist_action_id": self.protagonist_action_id,
            "matched_peer_count": self.matched_peer_count,
            "peer_median_performance": self.peer_median_performance,
            "protagonist_performance": self.protagonist_performance,
            "percentile": self.percentile,
            "power_percentile": self.power_percentile,
            "resource_percentile": self.resource_percentile,
            "base_percentile": self.base_percentile,
            "information_percentile": self.information_percentile,
            "comparative_result": self.comparative_result,
            "main_causes": self.main_causes,
        }


@dataclass
class PublicSystemFeedback:
    """公共系统反馈信息
    
    包含排行榜变化、系统公告、频道消息、交易记录等
    """
    announcements: List[Dict[str, Any]] = field(default_factory=list)  # 系统公告
    ranking_changes: List[Dict[str, Any]] = field(default_factory=list)  # 排行榜变动
    channel_messages: List[Dict[str, Any]] = field(default_factory=list)  # 频道消息摘要
    market_changes: List[Dict[str, Any]] = field(default_factory=list)  # 市场价格波动
    achievements: List[Dict[str, str]] = field(default_factory=list)  # 新解锁成就
    regional_statistics: Dict[str, Any] = field(default_factory=dict)  # 区域统计数据
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "announcements": self.announcements,
            "ranking_changes": self.ranking_changes,
            "channel_messages": self.channel_messages,
            "market_changes": self.market_changes,
            "achievements": self.achievements,
            "regional_statistics": self.regional_statistics,
        }


# ============================================================================
# 原有数据模型保持向下兼容
# ============================================================================


@dataclass(frozen=True)
class ActionContext:
    action_id: str = "action"
    primary_attribute: str = "spirit"
    target_difficulty: float = 20.0
    preparation: float = 0.0
    intelligence: float = 0.0
    teammate_assistance: float = 0.0
    environment_advantage: float = 0.0
    environment_penalty: float = 0.0
    time_pressure: float = 0.0
    unknown_risk: float = 0.0
    resource_shortage: float = 0.0
    continuous_errors: float = 0.0
    survival_assets: float = 0.0
    skill_bonus: float = 0.0
    equipment_bonus: Optional[float] = None
    ability_match: Optional[float] = None
    strength: float = 5.0
    constitution: float = 5.0
    agility: float = 5.0
    spirit: float = 5.0
    risk_warning: float = 0.0
    causal_chain: float = 0.0
    avoidable: float = 0.0
    rule_consistency: float = 0.0
    player_responsibility: float = 0.0
    difficulty_mode: str = "标准"
    seed: str = ""


@dataclass
class ActionResolution:
    formula_version: str
    action_id: str
    advantage_components: Dict[str, float]
    resistance_components: Dict[str, float]
    advantage: float
    resistance: float
    k: float
    probability: float
    random_roll: float
    severity: float
    severity_band: str
    death_fairness: float
    outcome: str
    death_allowed: bool
    components: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "formula_version": self.formula_version,
            "action_id": self.action_id,
            "advantage_components": self.advantage_components,
            "resistance_components": self.resistance_components,
            "advantage": self.advantage,
            "resistance": self.resistance,
            "K": self.k,
            "probability": self.probability,
            "random_roll": self.random_roll,
            "severity": self.severity,
            "severity_band": self.severity_band,
            "death_fairness": self.death_fairness,
            "outcome": self.outcome,
            "death_allowed": self.death_allowed,
            "components": self.components,
        }


@dataclass
class CombatResolution:
    formula_version: str
    attacker_attack: float
    defender_defense: float
    attacker_accuracy: float
    defender_evasion: float
    hit_probability: float
    random_roll: float
    hit: bool
    ammo_sufficient: bool
    outcome: str
    damage: float
    retreat_probability: float
    ammo_consumed: int
    weapon_durability_after: Optional[float]
    status_effects: List[Dict[str, Any]]
    death_risk: float
    components: Dict[str, Any] = field(default_factory=dict)
    incoming_damage: float = 0.0
    counterattack_hit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "formula_version": self.formula_version,
            "attacker_attack": self.attacker_attack,
            "defender_defense": self.defender_defense,
            "attacker_accuracy": self.attacker_accuracy,
            "defender_evasion": self.defender_evasion,
            "hit_probability": self.hit_probability,
            "random_roll": self.random_roll,
            "hit": self.hit,
            "ammo_sufficient": self.ammo_sufficient,
            "outcome": self.outcome,
            "damage": self.damage,
            "retreat_probability": self.retreat_probability,
            "ammo_consumed": self.ammo_consumed,
            "weapon_durability_after": self.weapon_durability_after,
            "status_effects": self.status_effects,
            "death_risk": self.death_risk,
            "incoming_damage": self.incoming_damage,
            "counterattack_hit": self.counterattack_hit,
            "components": self.components,
        }


@dataclass
class BatchResolution:
    formula_version: str
    farmability: float
    mode: str
    encounter_count: float
    kills_by_level: Dict[str, float]
    total_kills: float
    total_experience: float
    outcome: str
    recovered_resources: Dict[str, float]
    ammo_consumed: float
    durability_cost: float
    risk: float
    interruption_reasons: List[str]
    components: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "formula_version": self.formula_version,
            "farmability": self.farmability,
            "mode": self.mode,
            "encounter_count": self.encounter_count,
            "kills_by_level": self.kills_by_level,
            "total_kills": self.total_kills,
            "total_experience": self.total_experience,
            "outcome": self.outcome,
            "recovered_resources": self.recovered_resources,
            "ammo_consumed": self.ammo_consumed,
            "durability_cost": self.durability_cost,
            "risk": self.risk,
            "interruption_reasons": self.interruption_reasons,
            "components": self.components,
        }


@dataclass
class Observation:
    """Generic observation/assessment model.

    Represents: A character forms an assessment of another through world-consistent
    methods, and the assessment changes their cognition and behavior.

    This is NOT a specific detector system — it is an abstract capability that can
    manifest as:

    - Scanner device (sci-fi world)
    - Qi reading (cultivation world)
    - Professional judgment (mercenary veteran)
    - Animal reaction (beast taming world)
    - System feedback (game-like world)
    - etc.
    """

    observer_id: str
    target_id: str
    subject: str  # What is being observed: combat_capability, identity, danger_level, etc.

    prior_belief: Dict[str, Any] = field(
        default_factory=dict
    )  # {estimate: str, confidence: float}
    evidence: Dict[str, Any] = field(
        default_factory=dict
    )  # {source: str, reliability: float, precision: str}
    revealed_result: Dict[str, Any] = field(
        default_factory=dict
    )  # {relative_gap: str, exact_value_visible: bool}
    belief_change: Dict[str, Any] = field(
        default_factory=dict
    )  # {new_estimate: str, confidence: float}
    behavioral_consequences: List[str] = field(
        default_factory=list
    )  # What observer will do differently

    assessment_style: str = "qualitative_band"
    # Allowed values: exact_numeric, range_estimate, qualitative_band,
    #                 unmeasurable, environmental_reaction, professional_reaction

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observer_id": self.observer_id,
            "target_id": self.target_id,
            "subject": self.subject,
            "prior_belief": self.prior_belief,
            "evidence": self.evidence,
            "revealed_result": self.revealed_result,
            "belief_change": self.belief_change,
            "behavioral_consequences": self.behavioral_consequences,
            "assessment_style": self.assessment_style,
        }


@dataclass
class InformationChannel:
    """Defines what information methods are allowed in a world.

    Each world can have different information acquisition channels.
    The LLM invents specific manifestations based on world type.
    """

    domain: str  # combat_capability, identity, danger, etc.
    possible_methods: List[str] = field(
        default_factory=list
    )  # system_feedback, professional_judgment, supernatural_perception, etc.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "possible_methods": self.possible_methods,
        }
