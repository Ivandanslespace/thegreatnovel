"""引擎输入/输出模型。

输入继续接受 YAML 映射，以便兼容现有存档；输出使用 dataclass，避免把
尚未结算的中间值藏在叙述文本里。
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
