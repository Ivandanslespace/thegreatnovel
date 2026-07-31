"""Peer Agent 实体系统 - 精简版

只保留排行榜和对比系统必需的最小字段集。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PeerAgent:
    """最小化 Peer Agent - 仅包含排名和追踪必需字段"""
    id: str
    name: str
    profession: str = "survivor"
    level: int = 1
    location_id: str = "starting_area"
    hp: float = 100.0
    attributes: Dict[str, float] = field(default_factory=lambda: {
        "strength": 14.0, "agility": 14.0, "spirit": 14.0, "constitution": 13.0
    })
    action_history: List[dict] = field(default_factory=list)
    score_components: Dict[str, float] = field(default_factory=lambda: {
        "combat": 0.0, "resources": 0.0, "base": 0.0, "information": 0.0, "social": 0.0
    })
    ranking_percentile: float = 50.0
    
    # Extended personality traits (6 dimensions)
    personality_traits: Dict[str, float] = field(default_factory=lambda: {
        "caution": 50.0,      # Risk aversion (0-100, higher = more cautious)
        "ambition": 50.0,     # Goal-driven behavior (0-100)
        "empathy": 50.0,      # Social cooperation tendency (0-100)
        "honesty": 50.0,      # Trustworthiness and fairness (0-100)
        "openness": 50.0,     # Willingness to try new things/experiences (0-100)
        "collectivism": 50.0  # Group vs individual preference (0-100, higher = more group-focused)
    })
    
    # Strategic goals
    primary_goal: Optional[str] = None  # e.g., "maximize_resources", "survival", "combat_expert", "social_builder"
    secondary_goal: Optional[str] = None
    goal_progress: Dict[str, float] = field(default_factory=dict)
    
    # Social network
    relationships: Dict[str, str] = field(default_factory=dict)  # peer_id -> "neutral"/"friendly"/"hostile" or numeric -10 to +10
    faction_id: Optional[str] = None
    faction_status: str = "independent"
    
    # Resources/equipment for decision making
    inventory_resources: Dict[str, int] = field(default_factory=dict)
    equipment: Dict[str, str] = field(default_factory=dict)  # weapon, armor, tool names

    def record_action(self, turn: int, action_type: str, target: str, outcome: str,
                      scores: Dict[str, float] | None = None):
        self.action_history.append({
            "turn": turn,
            "action_type": action_type,
            "target": target,
            "outcome": outcome,
            "scores": scores or {},
        })
        # P1-06: Bound action_history to last 100 entries to prevent entity bloat
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> PeerAgent:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
