# 事件日志

<!-- 由 tools/create_save.py 创建；后续事件使用标准事件格式。 -->

---
## Turn 1 | Day 1 清晨 | 世界创建
```json
[
  {
    "event_id": "evt_0001_001",
    "type": "WORLD_CREATED",
    "actor": "system",
    "target": null,
    "data": {
      "world_name": "废土列车·新游戏",
      "theme": "废土列车",
      "safe_base": "不断行驶的废土列车",
      "difficulty": "标准",
      "generation_profile": "废土列车",
      "registry_counts": {
        "locations": 3,
        "enemies": 1,
        "areas": 1,
        "build_catalog": 3,
        "action_targets": 4
      }
    },
    "turn": 1,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 2 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0002_001",
    "type": "SOCIAL_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "social-001",
        "type": "SOCIAL_INTERACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 720.0,
        "available_stamina": 100.0,
        "available_mental": 100.0,
        "actions": [
          {
            "type": "SOCIAL_INTERACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "short_action"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [
          "short_action"
        ],
        "commitments": [
          [
            "social_relationship",
            "npc_atai"
          ]
        ],
        "windows": [
          {
            "group": "npc:npc_atai",
            "ids": [
              "清晨"
            ],
            "capacity": 1
          }
        ],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "social-001",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 0.0,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 15.0,
        "resistance": 18.0,
        "K": 10.0,
        "probability": 0.425557,
        "random_roll": 0.090145,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.56,
        "outcome": "普通成功",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 3.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 3.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 10.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.7
          },
          "outcome_thresholds": {
            "critical": 0.042556,
            "normal": 0.276612,
            "costly": 0.425557,
            "partial_failure": 0.569168,
            "severe_failure": 0.942556
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "relationship_changes": {
        "npc_atai": {
          "trust": 3,
          "respect": 1
        }
      },
      "knowledge_additions": [
        "npc_atai_goal"
      ],
      "proposed_events": [
        {
          "type": "KNOWLEDGE_GAINED",
          "target": "npc_atai_goal"
        },
        {
          "type": "RELATIONSHIP_CHANGED",
          "target": "npc_atai"
        }
      ],
      "runtime_metrics": {
        "pressure": 0.0,
        "payoff_maturity": 20.5,
        "payoff_impact": 34.0,
        "payoff_score": 35.4375,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.315,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 0.0,
          "by_type": {
            "WORLD_CREATED": 0.0
          }
        },
        "agency": 0.023333,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.833333
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.041666666666666664,
          "irreversibility": 1.0,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 1.0,
          "long_term_impact": 1.0,
          "uncertainty": {
            "danger_unknown": 0.0,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.0
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9583333333333334,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.8,
          "information_change": 0.0,
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 5.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 50.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 40.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 40.0,
          "fatigue": 0.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 2,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 3 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0003_001",
    "type": "SOCIAL_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "social-002",
        "type": "SOCIAL_INTERACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 690.0,
        "available_stamina": 98.0,
        "available_mental": 96.0,
        "actions": [
          {
            "type": "SOCIAL_INTERACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "short_action"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [
          "short_action"
        ],
        "commitments": [
          [
            "social_relationship",
            "npc_atai"
          ]
        ],
        "windows": [
          {
            "group": "npc:npc_atai",
            "ids": [
              "清晨"
            ],
            "capacity": 1
          }
        ],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "social-002",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 0.4,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 15.0,
        "resistance": 18.4,
        "K": 10.0,
        "probability": 0.415809,
        "random_roll": 0.501756,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.56,
        "outcome": "失败但获得部分信息",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 3.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 3.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 10.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.7
          },
          "outcome_thresholds": {
            "critical": 0.041581,
            "normal": 0.270276,
            "costly": 0.415809,
            "partial_failure": 0.561857,
            "severe_failure": 0.941581
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [],
      "runtime_metrics": {
        "pressure": 12.833333,
        "payoff_maturity": 21.5,
        "payoff_impact": 21.5,
        "payoff_score": 32.3625,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.315,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 0.0,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "SOCIAL_RESOLVED": 0.0
          }
        },
        "agency": 0.024348,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.652174
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.043478260869565216,
          "irreversibility": 1.0,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 1.0,
          "long_term_impact": 1.0,
          "uncertainty": {
            "danger_unknown": 0.0,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.0
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9565217391304348,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.8,
          "information_change": 0.0,
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 10.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 40.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 40.0,
          "fatigue": 2.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 3,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 4 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0004_001",
    "type": "ATTRIBUTES_ALLOCATED",
    "actor": "player",
    "target": "player",
    "data": {
      "action": {
        "action_id": "attributes-002",
        "type": "ATTRIBUTE_ALLOCATION"
      },
      "action_ledger": {
        "available_time_minutes": 660.0,
        "available_stamina": 96.0,
        "available_mental": 92.0,
        "actions": [
          {
            "type": "ATTRIBUTE_ALLOCATION",
            "target": null,
            "time_minutes": 0.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "progression",
              "zero_time"
            ]
          }
        ]
      },
      "resolution": {
        "formula_version": "attribute_allocation_v1",
        "action_type": "ATTRIBUTE_ALLOCATION",
        "outcome": "属性点分配完成",
        "allocation_success": true,
        "allocations": {
          "strength": 2,
          "spirit": 2
        },
        "points_before": 4,
        "points_spent": 4,
        "points_after": 0
      },
      "attribute_allocations": {
        "strength": 2,
        "spirit": 2
      },
      "player_delta": {
        "attributes": {
          "strength": 2,
          "spirit": 2
        },
        "free_points": -4
      },
      "time_cost": 0.0,
      "proposed_events": [
        {
          "type": "ATTRIBUTES_ALLOCATED",
          "target": "player",
          "allocations": {
            "strength": 2,
            "spirit": 2
          }
        }
      ]
    },
    "turn": 4,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 5 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0005_001",
    "type": "TRAVEL_COMPLETED",
    "actor": "player",
    "target": "scrap_yard",
    "data": {
      "action": {
        "action_id": "travel-scrap-yard-001",
        "type": "TRAVEL",
        "target": "scrap_yard"
      },
      "action_ledger": {
        "available_time_minutes": 660.0,
        "available_stamina": 96.0,
        "available_mental": 92.0,
        "actions": [
          {
            "type": "TRAVEL",
            "target": "scrap_yard",
            "time_minutes": 30.0,
            "stamina_cost": 5.0,
            "mental_cost": 0.0,
            "tags": [
              "move"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [],
        "commitments": [],
        "windows": [],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_type": "TRAVEL",
        "outcome": "普通成功",
        "movement_success": true,
        "probability": 1.0,
        "risk_mode": "deterministic_route",
        "time_cost": 30.0,
        "stamina_cost": 5.0,
        "mental_cost": 0.0
      },
      "fatigue_delta": 5.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "current_location": "scrap_yard",
      "current_location_name": "废铁站场",
      "current_encounter_id": null,
      "movement": {
        "from": "camp_core",
        "to": "scrap_yard",
        "mode": "TRAVEL"
      },
      "proposed_events": [
        {
          "type": "LOCATION_ENTERED",
          "target": "scrap_yard"
        }
      ],
      "runtime_metrics": {
        "pressure": 13.666667,
        "payoff_maturity": 23.5,
        "payoff_impact": 33.0,
        "payoff_score": 33.93,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.195,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 30.0,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "SOCIAL_RESOLVED": 30.0,
            "ATTRIBUTES_ALLOCATED": 0.0
          }
        },
        "agency": 0.007636,
        "uncertainty": 0.32,
        "risk_credibility": 0.2592,
        "decision_value": 0.004073,
        "combinability": 95.454545
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.045454545454545456,
          "irreversibility": 0.5,
          "information_uncertainty": 0.4,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 0.6,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.4,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.4
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.9,
            "enemy_effectiveness": 0.9,
            "information_incompleteness": 0.4,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9545454545454546,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.0,
          "information_change": 0.0,
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 20.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 20.0,
          "restriction_removed": 50.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 0.9,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 0.9,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 4.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 5,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 6 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0006_001",
    "type": "RETURN_TO_BASE_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "return-base-001",
        "type": "RETURN_TO_BASE",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 630.0,
        "available_stamina": 91.0,
        "available_mental": 92.0,
        "actions": [
          {
            "type": "RETURN_TO_BASE",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 5.0,
            "mental_cost": 0.0,
            "tags": [
              "move"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [],
        "commitments": [],
        "windows": [],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_type": "RETURN_TO_BASE",
        "outcome": "普通成功",
        "movement_success": true,
        "probability": 1.0,
        "risk_mode": "deterministic_route",
        "time_cost": 30.0,
        "stamina_cost": 5.0,
        "mental_cost": 0.0
      },
      "fatigue_delta": 5.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "current_location": "camp_core",
      "current_location_name": "不断行驶的废土列车",
      "current_encounter_id": null,
      "movement": {
        "from": "scrap_yard",
        "to": "camp_core",
        "mode": "RETURN_TO_BASE"
      },
      "proposed_events": [
        {
          "type": "RETURNED_TO_BASE",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 14.5,
        "payoff_maturity": 24.5,
        "payoff_impact": 12.5,
        "payoff_score": 23.40625,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.03,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 30.0,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "SOCIAL_RESOLVED": 30.0,
            "ATTRIBUTES_ALLOCATED": 0.0,
            "TRAVEL_COMPLETED": 0.0
          }
        },
        "agency": 0.006667,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.238095
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.047619047619047616,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.3,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 1.0,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.0,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.0
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.5,
            "enemy_effectiveness": 0.5,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9523809523809523,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.0,
          "information_change": 0.0,
          "goal_progress": 0.2,
          "new_playable_system": 0.0
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 25.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 50.0,
          "behavior_change": 0.0,
          "long_term_value": 0.0,
          "social_feedback": 0.0,
          "causal_chain": 0.5,
          "rule_consistency": 0.5,
          "reward_foreshadowed": 0.5,
          "new_playable_system": 0.0,
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 9.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 6,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 7 | Day 1 白天
```json
[
  {
    "event_id": "evt_0007_001",
    "type": "SOCIAL_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "report-atai-001",
        "type": "SOCIAL_INTERACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 600.0,
        "available_stamina": 86.0,
        "available_mental": 92.0,
        "actions": [
          {
            "type": "SOCIAL_INTERACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "short_action"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [
          "short_action"
        ],
        "commitments": [
          [
            "social_relationship",
            "npc_atai"
          ]
        ],
        "windows": [
          {
            "group": "npc:npc_atai",
            "ids": [
              "白天"
            ],
            "capacity": 1
          }
        ],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "report-atai-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 2.8,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 19.0,
        "resistance": 20.8,
        "K": 10.0,
        "probability": 0.455121,
        "random_roll": 0.72702,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.56,
        "outcome": "严重失败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 3.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 3.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.7
          },
          "outcome_thresholds": {
            "critical": 0.045512,
            "normal": 0.295829,
            "costly": 0.455121,
            "partial_failure": 0.591341,
            "severe_failure": 0.945512
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [],
      "runtime_metrics": {
        "pressure": 15.333333,
        "payoff_maturity": 25.5,
        "payoff_impact": 21.5,
        "payoff_score": 34.1625,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.315,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 30.0,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "SOCIAL_RESOLVED": 30.0,
            "ATTRIBUTES_ALLOCATED": 0.0,
            "TRAVEL_COMPLETED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0
          }
        },
        "agency": 0.028,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.05,
          "irreversibility": 1.0,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 1.0,
          "long_term_impact": 1.0,
          "uncertainty": {
            "danger_unknown": 0.0,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.0
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.95,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.8,
          "information_change": 0.0,
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 30.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 40.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 40.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 40.0,
          "fatigue": 14.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 7,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 8 | Day 1 白天
```json
[
  {
    "event_id": "evt_0008_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "check-gear-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 570.0,
        "available_stamina": 84.0,
        "available_mental": 88.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "short_action"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [],
        "commitments": [],
        "windows": [],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "check-gear-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 3.2,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 19.0,
        "resistance": 6.2,
        "K": 10.0,
        "probability": 0.78245,
        "random_roll": 0.961011,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "严重失败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 3.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.0,
            "rule_consistency": 1.0,
            "player_responsibility": 0.0
          },
          "outcome_thresholds": {
            "critical": 0.078245,
            "normal": 0.508593,
            "costly": 0.78245,
            "partial_failure": 0.836838,
            "severe_failure": 0.978245
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [],
      "runtime_metrics": {
        "pressure": 16.166667,
        "payoff_maturity": 26.5,
        "payoff_impact": 0.0,
        "payoff_score": 22.08125,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.03,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 22.5,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "SOCIAL_RESOLVED": 22.5,
            "ATTRIBUTES_ALLOCATED": 0.0,
            "TRAVEL_COMPLETED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0
          }
        },
        "agency": 0.007368,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 94.736842
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.05263157894736842,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.3,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 1.0,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.0,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.0
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.5,
            "enemy_effectiveness": 0.5,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9473684210526316,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.0,
          "information_change": 0.0,
          "goal_progress": 0.2,
          "new_playable_system": 0.0
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 35.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 0.0,
          "long_term_value": 0.0,
          "social_feedback": 0.0,
          "causal_chain": 0.5,
          "rule_consistency": 0.5,
          "reward_foreshadowed": 0.5,
          "new_playable_system": 0.0,
          "decision_change": 40.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 16.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 8,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 9 | Day 1 白天
```json
[
  {
    "event_id": "evt_0009_001",
    "type": "SOCIAL_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "ask-weapon-atai-001",
        "type": "SOCIAL_INTERACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 540.0,
        "available_stamina": 82.0,
        "available_mental": 84.0,
        "actions": [
          {
            "type": "SOCIAL_INTERACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "short_action"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [
          "short_action"
        ],
        "commitments": [
          [
            "social_relationship",
            "npc_atai"
          ]
        ],
        "windows": [
          {
            "group": "npc:npc_atai",
            "ids": [
              "白天"
            ],
            "capacity": 1
          }
        ],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "ask-weapon-atai-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 3.6,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 19.0,
        "resistance": 21.6,
        "K": 10.0,
        "probability": 0.435364,
        "random_roll": 0.994814,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.56,
        "outcome": "战败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 3.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 3.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.7
          },
          "outcome_thresholds": {
            "critical": 0.043536,
            "normal": 0.282987,
            "costly": 0.435364,
            "partial_failure": 0.576523,
            "severe_failure": 0.943536
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [],
      "runtime_metrics": {
        "pressure": 17.0,
        "payoff_maturity": 27.5,
        "payoff_impact": 21.5,
        "payoff_score": 32.2625,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.315,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 22.5,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "SOCIAL_RESOLVED": 22.5,
            "ATTRIBUTES_ALLOCATED": 0.0,
            "TRAVEL_COMPLETED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0,
            "ACTION_RESOLVED": 0.0
          }
        },
        "agency": 0.031111,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 94.444444
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.05555555555555555,
          "irreversibility": 1.0,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 1.0,
          "long_term_impact": 1.0,
          "uncertainty": {
            "danger_unknown": 0.0,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.0
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9444444444444444,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.8,
          "information_change": 0.0,
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 40.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 40.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 40.0,
          "fatigue": 18.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 9,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 10 | Day 1 白天
```json
[
  {
    "event_id": "evt_0010_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "check-gear-002",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 510.0,
        "available_stamina": 80.0,
        "available_mental": 80.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "short_action"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [],
        "commitments": [],
        "windows": [],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "check-gear-002",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 4.0,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 19.0,
        "resistance": 7.0,
        "K": 10.0,
        "probability": 0.768525,
        "random_roll": 0.864264,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "严重失败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 3.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.0,
            "rule_consistency": 1.0,
            "player_responsibility": 0.0
          },
          "outcome_thresholds": {
            "critical": 0.076853,
            "normal": 0.499541,
            "costly": 0.768525,
            "partial_failure": 0.826394,
            "severe_failure": 0.976853
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [],
      "runtime_metrics": {
        "pressure": 17.833333,
        "payoff_maturity": 28.5,
        "payoff_impact": 0.0,
        "payoff_score": 22.18125,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.03,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 25.0,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "SOCIAL_RESOLVED": 25.0,
            "ATTRIBUTES_ALLOCATED": 0.0,
            "TRAVEL_COMPLETED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0,
            "ACTION_RESOLVED": 0.0
          }
        },
        "agency": 0.008235,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 94.117647
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.058823529411764705,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.3,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 1.0,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.0,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.0
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.5,
            "enemy_effectiveness": 0.5,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9411764705882353,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.0,
          "information_change": 0.0,
          "goal_progress": 0.2,
          "new_playable_system": 0.0
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 45.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 0.0,
          "long_term_value": 0.0,
          "social_feedback": 0.0,
          "causal_chain": 0.5,
          "rule_consistency": 0.5,
          "reward_foreshadowed": 0.5,
          "new_playable_system": 0.0,
          "decision_change": 40.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 20.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 10,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 11 | Day 1 白天
```json
[
  {
    "event_id": "evt_0011_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "observe-train-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 480.0,
        "available_stamina": 78.0,
        "available_mental": 76.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "short_action"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [],
        "commitments": [],
        "windows": [],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "observe-train-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 4.4,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 19.0,
        "resistance": 7.4,
        "K": 10.0,
        "probability": 0.761333,
        "random_roll": 0.940845,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "严重失败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 3.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.0,
            "rule_consistency": 1.0,
            "player_responsibility": 0.0
          },
          "outcome_thresholds": {
            "critical": 0.076133,
            "normal": 0.494866,
            "costly": 0.761333,
            "partial_failure": 0.821,
            "severe_failure": 0.976133
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [],
      "runtime_metrics": {
        "pressure": 18.666667,
        "payoff_maturity": 29.5,
        "payoff_impact": 0.0,
        "payoff_score": 22.23125,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.03,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 30.0,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "SOCIAL_RESOLVED": 25.0,
            "ATTRIBUTES_ALLOCATED": 0.0,
            "TRAVEL_COMPLETED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0,
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.00875,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 93.75
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.0625,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.3,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 1.0,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.0,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.0
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.5,
            "enemy_effectiveness": 0.5,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9375,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.0,
          "information_change": 0.0,
          "goal_progress": 0.2,
          "new_playable_system": 0.0
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 50.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 0.0,
          "long_term_value": 0.0,
          "social_feedback": 0.0,
          "causal_chain": 0.5,
          "rule_consistency": 0.5,
          "reward_foreshadowed": 0.5,
          "new_playable_system": 0.0,
          "decision_change": 40.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 22.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 11,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 12 | Day 1 白天
```json
[
  {
    "event_id": "evt_0012_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "rest-001",
        "type": "REST",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 450.0,
        "available_stamina": 76.0,
        "available_mental": 72.0,
        "actions": [
          {
            "type": "REST",
            "target": "camp_core",
            "time_minutes": 360.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "major_action"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [
          "major_action"
        ],
        "commitments": [],
        "windows": [],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "rest-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 4.8,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 19.0,
        "resistance": 7.8,
        "K": 10.0,
        "probability": 0.753989,
        "random_roll": 0.428848,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "普通成功",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 3.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 1.0,
            "causal_chain": 1.0,
            "avoidable": 0.0,
            "rule_consistency": 1.0,
            "player_responsibility": 0.0
          },
          "outcome_thresholds": {
            "critical": 0.075399,
            "normal": 0.490093,
            "costly": 0.753989,
            "partial_failure": 0.815492,
            "severe_failure": 0.975399
          }
        }
      },
      "fatigue_delta": -35.0,
      "mental_delta": 20.0,
      "time_cost": 360.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "hp_delta": 5.0,
      "proposed_events": [
        {
          "type": "REST_COMPLETED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 19.5,
        "payoff_maturity": 30.5,
        "payoff_impact": 12.5,
        "payoff_score": 23.40625,
        "narrative_debt": [
          {
            "id": "这个世界是谁创造的？",
            "score": 0.0
          },
          {
            "id": "全民穿越的真正目的是什么？",
            "score": 0.0
          },
          {
            "id": "之前有没有其他批次的人？",
            "score": 0.0
          }
        ],
        "progress": 0.03,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 30.0,
          "by_type": {
            "SOCIAL_RESOLVED": 25.0,
            "ATTRIBUTES_ALLOCATED": 0.0,
            "TRAVEL_COMPLETED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0,
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.112,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 20.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.8,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.3,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 1.0,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.0,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.0
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.5,
            "enemy_effectiveness": 0.5,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.19999999999999996,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.0,
          "relationship_change": 0.0,
          "information_change": 0.0,
          "goal_progress": 0.2,
          "new_playable_system": 0.0
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 55.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 50.0,
          "behavior_change": 0.0,
          "long_term_value": 0.0,
          "social_feedback": 0.0,
          "causal_chain": 0.5,
          "rule_consistency": 0.5,
          "reward_foreshadowed": 0.5,
          "new_playable_system": 0.0,
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 24.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 12,
    "timestamp": "Day 1 白天"
  }
]
```
