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
      "world_name": "废土列车",
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
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "check-surroundings-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 720.0,
        "available_stamina": 100.0,
        "available_mental": 100.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "observe",
              "talent",
              "search"
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
        "action_id": "check-surroundings-001",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 0.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 10.0,
        "resistance": 0.0,
        "K": 10.0,
        "probability": 0.731059,
        "random_roll": 0.443975,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
            "ability_match": 10.0,
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
            "critical": 0.073106,
            "normal": 0.475188,
            "costly": 0.731059,
            "partial_failure": 0.798294,
            "severe_failure": 0.973106
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
        "pressure": 0.0,
        "payoff_maturity": 20.5,
        "payoff_impact": 12.5,
        "payoff_score": 23.30625,
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
          "max": 0.0,
          "by_type": {
            "WORLD_CREATED": 0.0
          }
        },
        "agency": 0.005833,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.833333
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.041666666666666664,
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
            "time_remaining": 0.9583333333333334,
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
          "waiting_time": 5.0,
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
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "character_sheet",
    "data": {
      "action": {
        "action_id": "allocate-001",
        "type": "SHORT_ACTION",
        "target": "character_sheet",
        "primary_attribute": "spirit"
      },
      "action_ledger": {
        "available_time_minutes": 690.0,
        "available_stamina": 100.0,
        "available_mental": 96.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "character_sheet",
            "time_minutes": 0.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "meta",
              "allocation"
            ]
          }
        ]
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "allocate-001",
        "advantage_components": {
          "ability_match": 10.0,
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
          "fatigue": 0.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 15.0,
        "resistance": 0.0,
        "K": 10.0,
        "probability": 1.0,
        "random_roll": 0.0,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "自动成功",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 10.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
          }
        }
      },
      "player_delta": {
        "attributes": {
          "strength": 2,
          "spirit": 2
        },
        "free_points": -4
      },
      "fatigue_delta": 0,
      "mental_delta": 0,
      "time_cost": 0,
      "hunger_delta": 0,
      "resource_changes": {}
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
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "talk-atai-001",
        "type": "SHORT_ACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 690.0,
        "available_stamina": 98.0,
        "available_mental": 96.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "social",
              "dialogue"
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
        "action_id": "talk-atai-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 0.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 15.4,
        "K": 10.0,
        "probability": 0.465057,
        "random_roll": 0.31826,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.56,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 3.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.046506,
            "normal": 0.302287,
            "costly": 0.465057,
            "partial_failure": 0.598793,
            "severe_failure": 0.946506
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
        "pressure": 15.833333,
        "payoff_maturity": 26.5,
        "payoff_impact": 15.5,
        "payoff_score": 31.2625,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.012174,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.652174
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.043478260869565216,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
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
          "relationship_change": 0.0,
          "information_change": 0.0,
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 15.0,
          "cost_paid": 20.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 2.0,
          "story_damage": 0.0
        }
      }
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
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "inspect-train-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 660.0,
        "available_stamina": 96.0,
        "available_mental": 92.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "observe",
              "explore",
              "base"
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
        "action_id": "inspect-train-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 0.8,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 0.8,
        "K": 10.0,
        "probability": 0.789182,
        "random_roll": 0.829585,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "失败但获得部分信息",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.078918,
            "normal": 0.512968,
            "costly": 0.789182,
            "partial_failure": 0.841886,
            "severe_failure": 0.978918
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
        "pressure": 13.666667,
        "payoff_maturity": 23.5,
        "payoff_impact": 0.0,
        "payoff_score": 20.53125,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.006364,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.454545
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.045454545454545456,
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
          "goal_progress": 0.2,
          "new_playable_system": 0.0
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 20.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
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
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "ask-atai-wall-001",
        "type": "SHORT_ACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 630.0,
        "available_stamina": 94.0,
        "available_mental": 88.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "social",
              "dialogue",
              "lore"
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
        "action_id": "ask-atai-wall-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 1.2,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 16.2,
        "K": 10.0,
        "probability": 0.445221,
        "random_roll": 0.855049,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.044522,
            "normal": 0.289394,
            "costly": 0.445221,
            "partial_failure": 0.583916,
            "severe_failure": 0.944522
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
        "pressure": 14.5,
        "payoff_maturity": 24.5,
        "payoff_impact": 15.5,
        "payoff_score": 31.6125,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.013333,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.238095
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.047619047619047616,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
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
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
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
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 25.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 40.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 6.0,
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
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "prepare-exploration-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 600.0,
        "available_stamina": 92.0,
        "available_mental": 84.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "prepare",
              "equipment",
              "plan"
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
        "action_id": "prepare-exploration-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 1.6,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 1.6,
        "K": 10.0,
        "probability": 0.775564,
        "random_roll": 0.521811,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.077556,
            "normal": 0.504117,
            "costly": 0.775564,
            "partial_failure": 0.831673,
            "severe_failure": 0.977556
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
        "payoff_maturity": 29.5,
        "payoff_impact": 0.0,
        "payoff_score": 22.38125,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.007,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.05,
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
            "time_remaining": 0.95,
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
          "waiting_time": 30.0,
          "cost_paid": 20.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 8.0,
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
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "confirm-tactics-001",
        "type": "SHORT_ACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 570.0,
        "available_stamina": 90.0,
        "available_mental": 80.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "social",
              "dialogue",
              "tactics"
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
        "action_id": "confirm-tactics-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 2.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 17.0,
        "K": 10.0,
        "probability": 0.425557,
        "random_roll": 0.823964,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
      "proposed_events": [],
      "runtime_metrics": {
        "pressure": 16.166667,
        "payoff_maturity": 26.5,
        "payoff_impact": 15.5,
        "payoff_score": 31.7125,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.014737,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 94.736842
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.05263157894736842,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
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
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
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
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 35.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 40.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 10.0,
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
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "craft-armguard-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 540.0,
        "available_stamina": 88.0,
        "available_mental": 76.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "craft",
              "equipment",
              "defense"
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
        "action_id": "craft-armguard-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 2.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 2.4,
        "K": 10.0,
        "probability": 0.761333,
        "random_roll": 0.368501,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
        "pressure": 17.0,
        "payoff_maturity": 27.5,
        "payoff_impact": 12.5,
        "payoff_score": 23.85625,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.007778,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 94.444444
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.05555555555555555,
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
            "time_remaining": 0.9444444444444444,
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
          "waiting_time": 40.0,
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
          "fatigue": 12.0,
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
    "type": "TRAVEL_COMPLETED",
    "actor": "player",
    "target": "scrap_yard",
    "data": {
      "action": {
        "action_id": "enter-scrap-001",
        "type": "ENTER_LOCATION",
        "target": "scrap_yard"
      },
      "action_ledger": {
        "available_time_minutes": 510.0,
        "available_stamina": 86.0,
        "available_mental": 72.0,
        "actions": [
          {
            "type": "ENTER_LOCATION",
            "target": "scrap_yard",
            "time_minutes": 30.0,
            "stamina_cost": 5.0,
            "mental_cost": 0.0,
            "tags": [
              "cautious"
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
        "action_type": "ENTER_LOCATION",
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
        "mode": "ENTER_LOCATION"
      },
      "proposed_events": [
        {
          "type": "LOCATION_ENTERED",
          "target": "scrap_yard"
        }
      ],
      "runtime_metrics": {
        "pressure": 17.833333,
        "payoff_maturity": 28.5,
        "payoff_impact": 33.0,
        "payoff_score": 34.18,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.009882,
        "uncertainty": 0.32,
        "risk_credibility": 0.2592,
        "decision_value": 0.005271,
        "combinability": 94.117647
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.058823529411764705,
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
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 45.0,
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
          "fatigue": 14.0,
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
    "type": "EXPLORATION_RESOLVED",
    "actor": "player",
    "target": "scrap_yard",
    "data": {
      "action": {
        "action_id": "explore-scrap-001",
        "type": "EXPLORATION",
        "target": "scrap_yard"
      },
      "action_ledger": {
        "available_time_minutes": 480.0,
        "available_stamina": 81.0,
        "available_mental": 72.0,
        "actions": [
          {
            "type": "EXPLORATION",
            "target": "scrap_yard",
            "time_minutes": 120.0,
            "stamina_cost": 15.0,
            "mental_cost": 10.0,
            "tags": [
              "search",
              "cautious",
              "talent",
              "major_action",
              "requires_full_attention"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [
          "major_action",
          "requires_full_attention"
        ],
        "commitments": [
          [
            "route_commitment",
            "scrap_yard"
          ]
        ],
        "windows": [
          {
            "group": "field_exploration",
            "ids": [
              "白天"
            ],
            "capacity": 1
          }
        ],
        "allowed_periods": [
          "白天",
          "黄昏"
        ],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "explore-scrap-001",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 25.0,
          "environment_penalty": 5.0,
          "injury": 0.0,
          "fatigue": 3.8,
          "time_pressure": 3.0,
          "unknown_risk": 7.0
        },
        "advantage": 15.0,
        "resistance": 43.8,
        "K": 10.0,
        "probability": 0.053151,
        "random_roll": 0.805489,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.5184,
        "outcome": "严重失败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 5.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 4.666666666666667,
            "time_pressure": 3.0,
            "continuous_errors": 0.0,
            "preparation": 5.0,
            "ability_match": 10.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 0.9,
            "causal_chain": 0.9,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.8
          },
          "outcome_thresholds": {
            "critical": 0.005315,
            "normal": 0.034548,
            "costly": 0.053151,
            "partial_failure": 0.289863,
            "severe_failure": 0.905315
          }
        }
      },
      "fatigue_delta": 15.0,
      "mental_delta": -10.0,
      "time_cost": 120.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [],
      "runtime_metrics": {
        "pressure": 18.666667,
        "payoff_maturity": 29.5,
        "payoff_impact": 20.5,
        "payoff_score": 32.805,
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
        "progress": 0.475,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 30.0,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "ACTION_RESOLVED": 30.0,
            "TRAVEL_COMPLETED": 0.0
          }
        },
        "agency": 0.042,
        "uncertainty": 0.32,
        "risk_credibility": 0.2592,
        "decision_value": 0.0224,
        "combinability": 75.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.25,
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
            "time_remaining": 0.75,
            "resource_compatibility": 1.0,
            "location_proximity": 1.0,
            "goal_compatibility": 1.0,
            "npc_availability": 1.0
          },
          "permanent_growth": 0.0,
          "world_change": 0.8,
          "relationship_change": 0.0,
          "information_change": 0.8,
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 50.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 20.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 0.9,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 0.9,
          "new_playable_system": 60.0,
          "decision_change": 40.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 19.0,
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
    "target": "scrap_yard",
    "data": {
      "action": {
        "action_id": "observe-scavengers-001",
        "type": "SHORT_ACTION",
        "target": "scrap_yard"
      },
      "action_ledger": {
        "available_time_minutes": 360.0,
        "available_stamina": 66.0,
        "available_mental": 62.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "scrap_yard",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "observe",
              "talent",
              "intelligence"
            ]
          }
        ]
      },
      "system_constraints": {
        "tags": [
          "major_action",
          "requires_full_attention"
        ],
        "commitments": [
          [
            "route_commitment",
            "scrap_yard"
          ]
        ],
        "windows": [
          {
            "group": "field_exploration",
            "ids": [
              "白天"
            ],
            "capacity": 1
          }
        ],
        "allowed_periods": [
          "白天",
          "黄昏"
        ],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "observe-scavengers-001",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 25.0,
          "environment_penalty": 5.0,
          "injury": 0.0,
          "fatigue": 6.8,
          "time_pressure": 0.0,
          "unknown_risk": 12.0
        },
        "advantage": 10.0,
        "resistance": 48.8,
        "K": 10.0,
        "probability": 0.020233,
        "random_roll": 0.593264,
        "severity": 3.0,
        "severity_band": "成功区",
        "death_fairness": 0.5184,
        "outcome": "严重失败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 5.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 8.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
            "ability_match": 10.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 0.9,
            "causal_chain": 0.9,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.8
          },
          "outcome_thresholds": {
            "critical": 0.002023,
            "normal": 0.013151,
            "costly": 0.020233,
            "partial_failure": 0.265175,
            "severe_failure": 0.902023
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
        "pressure": 22.0,
        "payoff_maturity": 31.1,
        "payoff_impact": 20.5,
        "payoff_score": 31.8175,
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
            "ACTION_RESOLVED": 30.0,
            "TRAVEL_COMPLETED": 0.0,
            "EXPLORATION_RESOLVED": 0.0
          }
        },
        "agency": 0.014,
        "uncertainty": 0.32,
        "risk_credibility": 0.2592,
        "decision_value": 0.007467,
        "combinability": 91.666667
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.08333333333333333,
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
            "time_remaining": 0.9166666666666666,
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
          "waiting_time": 55.0,
          "cost_paid": 3.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 20.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 0.9,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 0.9,
          "new_playable_system": 60.0,
          "decision_change": 40.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 34.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 12,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 13 | Day 1 白天
```json
[
  {
    "event_id": "evt_0013_001",
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
        "available_time_minutes": 330.0,
        "available_stamina": 64.0,
        "available_mental": 58.0,
        "actions": [
          {
            "type": "RETURN_TO_BASE",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 5.0,
            "mental_cost": 0.0,
            "tags": [
              "retreat"
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
        "pressure": 22.833333,
        "payoff_maturity": 31.5,
        "payoff_impact": 12.5,
        "payoff_score": 22.45625,
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
          "max": 27.857143,
          "by_type": {
            "ACTION_RESOLVED": 27.857143,
            "TRAVEL_COMPLETED": 0.0,
            "EXPLORATION_RESOLVED": 0.0
          }
        },
        "agency": 0.012727,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 90.909091
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.09090909090909091,
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
            "time_remaining": 0.9090909090909091,
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
          "waiting_time": 60.0,
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
          "fatigue": 36.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 13,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 14 | Day 1 白天
```json
[
  {
    "event_id": "evt_0014_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "give-fuel-atai-001",
        "type": "SHORT_ACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 300.0,
        "available_stamina": 59.0,
        "available_mental": 58.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "social",
              "gift",
              "nonverbal"
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
        "action_id": "give-fuel-atai-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 8.2,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 23.2,
        "K": 10.0,
        "probability": 0.284958,
        "random_roll": 0.236436,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.56,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 3.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.028496,
            "normal": 0.185223,
            "costly": 0.284958,
            "partial_failure": 0.463718,
            "severe_failure": 0.928496
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
        "pressure": 23.666667,
        "payoff_maturity": 36.5,
        "payoff_impact": 15.5,
        "payoff_score": 29.8625,
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
          "max": 27.5,
          "by_type": {
            "ACTION_RESOLVED": 27.5,
            "TRAVEL_COMPLETED": 0.0,
            "EXPLORATION_RESOLVED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0
          }
        },
        "agency": 0.028,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 90.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.1,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
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
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9,
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
          "waiting_time": 65.0,
          "cost_paid": 20.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 41.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 14,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 15 | Day 1 白天
```json
[
  {
    "event_id": "evt_0015_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "rest-short-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 270.0,
        "available_stamina": 57.0,
        "available_mental": 54.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "rest",
              "sleep",
              "recovery"
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
        "action_id": "rest-short-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 8.6,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 8.6,
        "K": 10.0,
        "probability": 0.631812,
        "random_roll": 0.70517,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "失败但获得部分信息",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.063181,
            "normal": 0.410678,
            "costly": 0.631812,
            "partial_failure": 0.723859,
            "severe_failure": 0.963181
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
        "pressure": 24.5,
        "payoff_maturity": 33.5,
        "payoff_impact": 0.0,
        "payoff_score": 19.13125,
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
          "max": 27.5,
          "by_type": {
            "ACTION_RESOLVED": 27.5,
            "TRAVEL_COMPLETED": 0.0,
            "EXPLORATION_RESOLVED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0
          }
        },
        "agency": 0.015556,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 88.888889
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.1111111111111111,
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
            "time_remaining": 0.8888888888888888,
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
          "waiting_time": 70.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 43.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 15,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 16 | Day 1 黄昏
```json
[
  {
    "event_id": "evt_0016_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "rest-night-002",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 240.0,
        "available_stamina": 55.0,
        "available_mental": 50.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "rest",
              "sleep"
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
        "action_id": "rest-night-002",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 9.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 9.0,
        "K": 10.0,
        "probability": 0.622459,
        "random_roll": 0.289075,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.062246,
            "normal": 0.404598,
            "costly": 0.622459,
            "partial_failure": 0.716844,
            "severe_failure": 0.962246
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
        "pressure": 25.333333,
        "payoff_maturity": 34.5,
        "payoff_impact": 12.5,
        "payoff_score": 22.30625,
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
          "max": 27.5,
          "by_type": {
            "ACTION_RESOLVED": 27.5,
            "TRAVEL_COMPLETED": 0.0,
            "EXPLORATION_RESOLVED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0
          }
        },
        "agency": 0.0175,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 87.5
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.125,
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
            "time_remaining": 0.875,
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
          "waiting_time": 75.0,
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
          "fatigue": 45.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 16,
    "timestamp": "Day 1 黄昏"
  }
]
```
---
## Turn 17 | Day 1 黄昏
```json
[
  {
    "event_id": "evt_0017_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "observe-fire-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 210.0,
        "available_stamina": 53.0,
        "available_mental": 46.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "observe",
              "cautious"
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
        "action_id": "observe-fire-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 9.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 9.4,
        "K": 10.0,
        "probability": 0.613014,
        "random_roll": 0.586239,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.061301,
            "normal": 0.398459,
            "costly": 0.613014,
            "partial_failure": 0.709761,
            "severe_failure": 0.961301
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
        "pressure": 26.166667,
        "payoff_maturity": 39.5,
        "payoff_impact": 0.0,
        "payoff_score": 20.98125,
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
          "max": 27.5,
          "by_type": {
            "ACTION_RESOLVED": 27.5,
            "TRAVEL_COMPLETED": 0.0,
            "EXPLORATION_RESOLVED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0
          }
        },
        "agency": 0.02,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 85.714286
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.14285714285714285,
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
            "time_remaining": 0.8571428571428572,
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
          "waiting_time": 80.0,
          "cost_paid": 20.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 47.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 17,
    "timestamp": "Day 1 黄昏"
  }
]
```
---
## Turn 18 | Day 1 黄昏
```json
[
  {
    "event_id": "evt_0018_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "note-fires-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 180.0,
        "available_stamina": 51.0,
        "available_mental": 42.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "record",
              "intelligence"
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
        "action_id": "note-fires-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 9.8,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 9.8,
        "K": 10.0,
        "probability": 0.603483,
        "random_roll": 0.982419,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "战败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.060348,
            "normal": 0.392264,
            "costly": 0.603483,
            "partial_failure": 0.702612,
            "severe_failure": 0.960348
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
        "pressure": 27.0,
        "payoff_maturity": 36.5,
        "payoff_impact": 0.0,
        "payoff_score": 19.28125,
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
          "max": 27.5,
          "by_type": {
            "ACTION_RESOLVED": 27.5,
            "TRAVEL_COMPLETED": 0.0,
            "EXPLORATION_RESOLVED": 0.0,
            "RETURN_TO_BASE_COMPLETED": 0.0
          }
        },
        "agency": 0.023333,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 83.333333
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.16666666666666666,
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
            "time_remaining": 0.8333333333333334,
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
          "waiting_time": 85.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 49.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 18,
    "timestamp": "Day 1 黄昏"
  }
]
```
---
## Turn 19 | Day 1 黄昏
```json
[
  {
    "event_id": "evt_0019_001",
    "type": "BUILDING_BUILT",
    "actor": "player",
    "target": "fuel_still",
    "data": {
      "resolution": {
        "formula_version": "1.0",
        "success": true,
        "errors": [],
        "time_required": 60.0,
        "space_cost": 1.0,
        "maintenance": {
          "燃油": 1
        },
        "resource_changes": {
          "wood": -1.0,
          "燃油": -1.0
        },
        "missing_resources": {},
        "quality_multiplier": 1.0
      },
      "action": {
        "action_id": "fuel_still",
        "type": "BUILD",
        "target": "fuel_still"
      },
      "action_ledger": {
        "available_time_minutes": 120.0,
        "available_stamina": 49.0,
        "available_mental": 38.0,
        "actions": [
          {
            "type": "BUILD",
            "target": "fuel_still",
            "time_minutes": 60.0,
            "stamina_cost": 20.0,
            "mental_cost": 5.0,
            "tags": [
              "requires_full_attention"
            ]
          }
        ]
      },
      "resource_changes": {
        "wood": -1.0,
        "燃油": -1.0
      },
      "fatigue_delta": 20.0,
      "mental_delta": -5.0,
      "time_cost": 60.0,
      "base_space_delta": 1.0,
      "base_module": {
        "id": "fuel_still",
        "name": "燃油蒸馏器",
        "description": "提高废燃料的回收效率",
        "space_cost": 1,
        "build_time": 60,
        "build_cost": {
          "wood": 1,
          "燃油": 1
        },
        "maintenance": {
          "燃油": 1
        },
        "effects": {
          "base_defense": 1
        },
        "quality_multiplier": 1.0
      },
      "proposed_events": [
        {
          "type": "BASE_UPGRADED",
          "target": "fuel_still"
        }
      ]
    },
    "turn": 19,
    "timestamp": "Day 1 黄昏"
  }
]
```
---
## Turn 20 | Day 1 夜晚
```json
[
  {
    "event_id": "evt_0020_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "search-train-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 90.0,
        "available_stamina": 29.0,
        "available_mental": 33.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "search",
              "explore",
              "base"
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
        "action_id": "search-train-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 14.2,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 14.2,
        "K": 10.0,
        "probability": 0.495,
        "random_roll": 0.92596,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.0495,
            "normal": 0.32175,
            "costly": 0.495,
            "partial_failure": 0.62125,
            "severe_failure": 0.9495
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
        "pressure": 29.5,
        "payoff_maturity": 38.5,
        "payoff_impact": 0.0,
        "payoff_score": 19.58125,
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
            "TRAVEL_COMPLETED": 0.0,
            "EXPLORATION_RESOLVED": 0.0,
            "ACTION_RESOLVED": 30.0,
            "RETURN_TO_BASE_COMPLETED": 0.0,
            "BUILDING_BUILT": 0.0
          }
        },
        "agency": 0.046667,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 66.666667
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.3333333333333333,
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
            "time_remaining": 0.6666666666666667,
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
          "waiting_time": 95.0,
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
          "fatigue": 71.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 20,
    "timestamp": "Day 1 夜晚"
  }
]
```
---
## Turn 21 | Day 1 夜晚
```json
[
  {
    "event_id": "evt_0021_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "test-still-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 60.0,
        "available_stamina": 27.0,
        "available_mental": 29.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "craft",
              "test",
              "production"
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
        "action_id": "test-still-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 14.6,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 14.6,
        "K": 10.0,
        "probability": 0.485004,
        "random_roll": 0.5564,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "失败但获得部分信息",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.0485,
            "normal": 0.315253,
            "costly": 0.485004,
            "partial_failure": 0.613753,
            "severe_failure": 0.9485
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
        "pressure": 30.333333,
        "payoff_maturity": 39.5,
        "payoff_impact": 0.0,
        "payoff_score": 17.63125,
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
            "EXPLORATION_RESOLVED": 0.0,
            "ACTION_RESOLVED": 30.0,
            "RETURN_TO_BASE_COMPLETED": 0.0,
            "BUILDING_BUILT": 0.0
          }
        },
        "agency": 0.07,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 50.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.5,
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
            "time_remaining": 0.5,
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
          "waiting_time": 100.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 73.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 21,
    "timestamp": "Day 1 夜晚"
  }
]
```
---
## Turn 21 | Day 1 夜晚
```json
[
  {
    "event_id": "evt_0021_options_254cd2c4",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 21,
        "options": {
          "C": {
            "id": "C",
            "label": "前往废铁站场",
            "description": "",
            "action": {
              "action_id": "auto-travel-scrap_yard",
              "type": "TRAVEL",
              "target": "scrap_yard"
            },
            "preview": {
              "legal": true,
              "errors": [],
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
              "target_profile": {
                "id": "scrap_yard",
                "location_id": "scrap_yard",
                "target_difficulty": 25,
                "environment_penalty": 5,
                "unknown_risk": 12,
                "risk_warning": 0.9,
                "causal_chain": 0.9,
                "avoidable": 0.8,
                "rule_consistency": 1.0,
                "player_responsibility": 0.8,
                "effects": {
                  "success": {
                    "discover_locations": [
                      "scrap_yard"
                    ],
                    "resource_changes": {
                      "燃油": 2
                    },
                    "knowledge_additions": [
                      "wasteland_raider_lv1_behavior"
                    ]
                  },
                  "partial_failure": {
                    "knowledge_additions": [
                      "wasteland_raider_lv1_behavior"
                    ]
                  }
                },
                "encounter_target_ids": [
                  "wasteland_raider_lv1"
                ],
                "constraints": {
                  "system_tags": [
                    "major_action",
                    "requires_full_attention"
                  ],
                  "exclusive_group": "field_exploration",
                  "window_ids": [
                    "白天",
                    "黄昏"
                  ],
                  "window_capacity": 1,
                  "availability": {
                    "allowed_periods": [
                      "白天",
                      "黄昏"
                    ]
                  },
                  "reservation": {
                    "exclusive_group": "field_exploration",
                    "window_id": "current_period",
                    "capacity": 1
                  },
                  "commitment_axis": "route_commitment",
                  "commitment_value": "scrap_yard"
                },
                "primary_attribute": "agility",
                "requirements": {
                  "location": "scrap_yard"
                }
              },
              "system_constraints": {
                "tags": [],
                "commitments": [],
                "windows": [],
                "allowed_periods": [],
                "npc_unavailable": false
              },
              "action_ledger": {
                "available_time_minutes": 30.0,
                "available_stamina": 25.0,
                "available_mental": 25.0,
                "actions": [
                  {
                    "type": "TRAVEL",
                    "target": "scrap_yard",
                    "time_minutes": 30.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 21
          }
        }
      },
      "state_turn": 21
    },
    "turn": 21,
    "timestamp": "Day 1 夜晚"
  }
]
```
---
## Turn 22 | Day 1 夜晚
```json
[
  {
    "event_id": "evt_0022_001",
    "type": "WAIT_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "wait-dawn-001",
        "type": "WAIT",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 30.0,
        "available_stamina": 25.0,
        "available_mental": 25.0,
        "actions": [
          {
            "type": "WAIT",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep"
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
        "action_type": "WAIT",
        "outcome": "普通成功",
        "probability": 1.0,
        "risk_mode": "deterministic_wait",
        "time_cost": 30.0,
        "wait_minutes": 30.0
      },
      "fatigue_delta": 0.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [
        {
          "type": "TIME_ADVANCED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 31.166667,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 20.55625,
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
            "RETURN_TO_BASE_COMPLETED": 0.0,
            "ACTION_RESOLVED": 30.0,
            "BUILDING_BUILT": 0.0,
            "OPTIONS_PRESENTED": 0.0
          }
        },
        "agency": 0.14,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 0.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 1.0,
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
            "time_remaining": 0.0,
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
          "waiting_time": 100.0,
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
          "fatigue": 75.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 22,
    "timestamp": "Day 1 夜晚"
  }
]
```
---
## Turn 23 | Day 2 清晨
```json
[
  {
    "event_id": "evt_0023_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "ask-station-001",
        "type": "SHORT_ACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 720.0,
        "available_stamina": 25.0,
        "available_mental": 25.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "social",
              "dialogue",
              "lore"
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
        "action_id": "ask-station-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 15.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 30.0,
        "K": 10.0,
        "probability": 0.167982,
        "random_roll": 0.023602,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.016798,
            "normal": 0.109188,
            "costly": 0.167982,
            "partial_failure": 0.375987,
            "severe_failure": 0.916798
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
        "pressure": 12.0,
        "payoff_maturity": 39.5,
        "payoff_impact": 28.0,
        "payoff_score": 29.5875,
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
            "ACTION_RESOLVED": 30.0,
            "BUILDING_BUILT": 0.0,
            "OPTIONS_PRESENTED": 0.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.011667,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.833333
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.041666666666666664,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
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
          "relationship_change": 0.0,
          "information_change": 0.0,
          "goal_progress": 0.7,
          "new_playable_system": 0.6
        },
        "payoff": {
          "scarcity_pressure": 0.0,
          "setup_depth": 60.0,
          "waiting_time": 100.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 50.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 75.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 23,
    "timestamp": "Day 2 清晨"
  }
]
```
---
## Turn 24 | Day 2 清晨
```json
[
  {
    "event_id": "evt_0024_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "test-wood-still-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 690.0,
        "available_stamina": 23.0,
        "available_mental": 21.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "craft",
              "experiment",
              "production"
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
        "action_id": "test-wood-still-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 15.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 15.4,
        "K": 10.0,
        "probability": 0.465057,
        "random_roll": 0.675805,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.046506,
            "normal": 0.302287,
            "costly": 0.465057,
            "partial_failure": 0.598793,
            "severe_failure": 0.946506
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
        "payoff_maturity": 39.5,
        "payoff_impact": 0.0,
        "payoff_score": 19.23125,
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
          "max": 27.5,
          "by_type": {
            "ACTION_RESOLVED": 27.5,
            "BUILDING_BUILT": 0.0,
            "OPTIONS_PRESENTED": 0.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.006087,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.652174
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.043478260869565216,
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
            "time_remaining": 0.9565217391304348,
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
          "waiting_time": 100.0,
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
          "fatigue": 77.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 24,
    "timestamp": "Day 2 清晨"
  }
]
```
---
## Turn 25 | Day 2 清晨
```json
[
  {
    "event_id": "evt_0025_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "ask-rules-001",
        "type": "SHORT_ACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 660.0,
        "available_stamina": 21.0,
        "available_mental": 17.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "social",
              "dialogue",
              "lore"
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
        "action_id": "ask-rules-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 15.8,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 30.8,
        "K": 10.0,
        "probability": 0.157095,
        "random_roll": 0.836738,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.01571,
            "normal": 0.102112,
            "costly": 0.157095,
            "partial_failure": 0.367821,
            "severe_failure": 0.91571
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
        "pressure": 13.666667,
        "payoff_maturity": 39.5,
        "payoff_impact": 15.5,
        "payoff_score": 28.0625,
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
          "max": 27.5,
          "by_type": {
            "ACTION_RESOLVED": 27.5,
            "BUILDING_BUILT": 0.0,
            "OPTIONS_PRESENTED": 0.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.012727,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.454545
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.045454545454545456,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
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
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
            "information_incompleteness": 0.0,
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
          "waiting_time": 100.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 40.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 79.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 25,
    "timestamp": "Day 2 清晨"
  }
]
```
---
## Turn 26 | Day 2 清晨
```json
[
  {
    "event_id": "evt_0026_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "rest-before-station-001",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 630.0,
        "available_stamina": 19.0,
        "available_mental": 13.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "rest",
              "recovery"
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
        "action_id": "rest-before-station-001",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 16.2,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 16.2,
        "K": 10.0,
        "probability": 0.445221,
        "random_roll": 0.541443,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "失败但获得部分信息",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.044522,
            "normal": 0.289394,
            "costly": 0.445221,
            "partial_failure": 0.583916,
            "severe_failure": 0.944522
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
        "pressure": 14.5,
        "payoff_maturity": 39.5,
        "payoff_impact": 0.0,
        "payoff_score": 16.83125,
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
          "max": 27.5,
          "by_type": {
            "ACTION_RESOLVED": 27.5,
            "BUILDING_BUILT": 0.0,
            "OPTIONS_PRESENTED": 0.0,
            "WAIT_COMPLETED": 0.0
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
          "waiting_time": 100.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 81.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 26,
    "timestamp": "Day 2 清晨"
  }
]
```
---
## Turn 27 | Day 2 白天
```json
[
  {
    "event_id": "evt_0027_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "exchange_station_observation",
    "data": {
      "action": {
        "action_id": "observe_station_b",
        "type": "SHORT_ACTION",
        "target": "exchange_station_observation"
      },
      "action_ledger": {
        "available_time_minutes": 600.0,
        "available_stamina": 17.0,
        "available_mental": 9.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "exchange_station_observation",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "observation",
              "cautious",
              "debt_repayment"
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
        "action_id": "observe_station_b",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 10.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 16.6,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 26.6,
        "K": 10.0,
        "probability": 0.220974,
        "random_roll": 0.020163,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "大成功",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
          },
          "outcome_thresholds": {
            "critical": 0.022097,
            "normal": 0.143633,
            "costly": 0.220974,
            "partial_failure": 0.415731,
            "severe_failure": 0.922097
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
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 21.75625,
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
          "max": 27.5,
          "by_type": {
            "ACTION_RESOLVED": 27.5,
            "BUILDING_BUILT": 0.0,
            "OPTIONS_PRESENTED": 0.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.007,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.05,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.3,
          "route_divergence": 0.3,
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
            "time_remaining": 0.95,
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
          "waiting_time": 100.0,
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
          "decision_change": 40.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 83.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 27,
    "timestamp": "Day 2 白天"
  }
]
```
---
## Turn 28 | Day 2 白天
```json
[
  {
    "event_id": "evt_0028_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "intelligence_consolidation",
    "data": {
      "action": {
        "action_id": "document_intel",
        "type": "SHORT_ACTION",
        "target": "intelligence_consolidation"
      },
      "action_ledger": {
        "available_time_minutes": 570.0,
        "available_stamina": 15.0,
        "available_mental": 5.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "intelligence_consolidation",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "analysis",
              "documentation",
              "self_care"
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
        "action_id": "document_intel",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 10.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 17.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 27.0,
        "K": 10.0,
        "probability": 0.214165,
        "random_roll": 0.344512,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "失败但获得部分信息",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
          },
          "outcome_thresholds": {
            "critical": 0.021417,
            "normal": 0.139207,
            "costly": 0.214165,
            "partial_failure": 0.410624,
            "severe_failure": 0.921417
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
        "payoff_maturity": 39.5,
        "payoff_impact": 0.0,
        "payoff_score": 16.43125,
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
          "max": 27.5,
          "by_type": {
            "BUILDING_BUILT": 0.0,
            "ACTION_RESOLVED": 27.5,
            "OPTIONS_PRESENTED": 0.0,
            "WAIT_COMPLETED": 0.0
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
          "route_divergence": 0.3,
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
          "waiting_time": 100.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 85.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 28,
    "timestamp": "Day 2 白天"
  }
]
```
---
## Turn 29 | Day 2 白天
```json
[
  {
    "event_id": "evt_0029_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "force_sleep",
        "type": "REST",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 540.0,
        "available_stamina": 13.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "REST",
            "target": "camp_core",
            "time_minutes": 360.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "recovery",
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
        "action_id": "force_sleep",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 17.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 17.4,
        "K": 10.0,
        "probability": 0.415809,
        "random_roll": 0.405579,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.041581,
            "normal": 0.270276,
            "costly": 0.415809,
            "partial_failure": 0.561857,
            "severe_failure": 0.941581
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
        "pressure": 17.0,
        "payoff_maturity": 43.5,
        "payoff_impact": 0.0,
        "payoff_score": 17.98125,
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
          "max": 27.857143,
          "by_type": {
            "ACTION_RESOLVED": 27.857143,
            "OPTIONS_PRESENTED": 0.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.093333,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 33.333333
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.6666666666666666,
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
            "time_remaining": 0.33333333333333337,
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
          "waiting_time": 100.0,
          "cost_paid": 20.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 87.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 29,
    "timestamp": "Day 2 白天"
  }
]
```
---
## Turn 30 | Day 2 黄昏
```json
[
  {
    "event_id": "evt_0030_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "show_notes_atai",
        "type": "SHORT_ACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 180.0,
        "available_stamina": 48.0,
        "available_mental": 21.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "social",
              "trust_building",
              "information_exchange"
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
              "黄昏"
            ],
            "capacity": 1
          }
        ],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "show_notes_atai",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 10.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 25.4,
        "K": 10.0,
        "probability": 0.24232,
        "random_roll": 0.913456,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.024232,
            "normal": 0.157508,
            "costly": 0.24232,
            "partial_failure": 0.43174,
            "severe_failure": 0.924232
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
        "pressure": 27.0,
        "payoff_maturity": 39.5,
        "payoff_impact": 15.5,
        "payoff_score": 30.7625,
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
          "max": 27.857143,
          "by_type": {
            "ACTION_RESOLVED": 27.857143,
            "OPTIONS_PRESENTED": 0.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.046667,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 83.333333
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.16666666666666666,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
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
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.8333333333333334,
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
          "waiting_time": 100.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 40.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 52.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 30,
    "timestamp": "Day 2 黄昏"
  }
]
```
---
## Turn 31 | Day 2 黄昏
```json
[
  {
    "event_id": "evt_0031_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "leave_tag_silent",
        "type": "SHORT_ACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 150.0,
        "available_stamina": 46.0,
        "available_mental": 17.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "social",
              "reconciliation",
              "silent_gesture"
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
              "黄昏"
            ],
            "capacity": 1
          }
        ],
        "allowed_periods": [],
        "npc_unavailable": false
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "leave_tag_silent",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 10.8,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 25.8,
        "K": 10.0,
        "probability": 0.235052,
        "random_roll": 0.822382,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.023505,
            "normal": 0.152784,
            "costly": 0.235052,
            "partial_failure": 0.426289,
            "severe_failure": 0.923505
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
        "pressure": 27.833333,
        "payoff_maturity": 39.5,
        "payoff_impact": 15.5,
        "payoff_score": 30.5625,
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
            "OPTIONS_PRESENTED": 0.0,
            "WAIT_COMPLETED": 0.0,
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.056,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 80.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.2,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.7,
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
            "failure_clarity": 1.0,
            "enemy_effectiveness": 1.0,
            "information_incompleteness": 0.0,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.8,
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
          "waiting_time": 100.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 0.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 1.0,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 1.0,
          "new_playable_system": 60.0,
          "decision_change": 40.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 54.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 31,
    "timestamp": "Day 2 黄昏"
  }
]
```
---
## Turn 32 | Day 2 夜晚
```json
[
  {
    "event_id": "evt_0032_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "inspect_train_night",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 120.0,
        "available_stamina": 44.0,
        "available_mental": 13.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "inspection",
              "maintenance",
              "observation"
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
        "action_id": "inspect_train_night",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 11.2,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 11.2,
        "K": 10.0,
        "probability": 0.569546,
        "random_roll": 0.29977,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.056955,
            "normal": 0.370205,
            "costly": 0.569546,
            "partial_failure": 0.67716,
            "severe_failure": 0.956955
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
        "pressure": 28.666667,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 22.45625,
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
            "WAIT_COMPLETED": 0.0,
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.035,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 75.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.25,
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
            "time_remaining": 0.75,
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
          "waiting_time": 100.0,
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
          "fatigue": 56.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 32,
    "timestamp": "Day 2 夜晚"
  }
]
```
---
## Turn 33 | Day 2 夜晚
```json
[
  {
    "event_id": "evt_0033_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "short_sleep_night",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 90.0,
        "available_stamina": 42.0,
        "available_mental": 9.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "rest",
              "sleep",
              "recovery"
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
        "action_id": "short_sleep_night",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 11.6,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 11.6,
        "K": 10.0,
        "probability": 0.559714,
        "random_roll": 0.785992,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.055971,
            "normal": 0.363814,
            "costly": 0.559714,
            "partial_failure": 0.669786,
            "severe_failure": 0.955971
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
        "pressure": 29.5,
        "payoff_maturity": 39.5,
        "payoff_impact": 0.0,
        "payoff_score": 21.13125,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.046667,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 66.666667
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.3333333333333333,
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
            "time_remaining": 0.6666666666666667,
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
          "waiting_time": 100.0,
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
          "fatigue": 58.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 33,
    "timestamp": "Day 2 夜晚"
  }
]
```
---
## Turn 34 | Day 2 夜晚
```json
[
  {
    "event_id": "evt_0034_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "improvised_sleep",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 60.0,
        "available_stamina": 40.0,
        "available_mental": 5.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "rest",
              "sleep",
              "improvisation",
              "sensory_deprivation"
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
        "action_id": "improvised_sleep",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 12.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 12.0,
        "K": 10.0,
        "probability": 0.549834,
        "random_roll": 0.05652,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.054983,
            "normal": 0.357392,
            "costly": 0.549834,
            "partial_failure": 0.662376,
            "severe_failure": 0.954983
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
        "pressure": 30.333333,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 22.05625,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.07,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 50.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.5,
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
            "time_remaining": 0.5,
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
          "waiting_time": 100.0,
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
          "fatigue": 60.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 34,
    "timestamp": "Day 2 夜晚"
  }
]
```
---
## Turn 35 | Day 2 夜晚
```json
[
  {
    "event_id": "evt_0035_001",
    "type": "WAIT_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "wait_dawn",
        "type": "WAIT",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 30.0,
        "available_stamina": 38.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "WAIT",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "wait",
              "day_transition"
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
        "action_type": "WAIT",
        "outcome": "普通成功",
        "probability": 1.0,
        "risk_mode": "deterministic_wait",
        "time_cost": 30.0,
        "wait_minutes": 30.0
      },
      "fatigue_delta": 0.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [
        {
          "type": "TIME_ADVANCED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 31.166667,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 21.85625,
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
            "ACTION_RESOLVED": 30.0
          }
        },
        "agency": 0.14,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 0.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 1.0,
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
            "time_remaining": 0.0,
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
          "waiting_time": 100.0,
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
          "fatigue": 62.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 35,
    "timestamp": "Day 2 夜晚"
  }
]
```
---
## Turn 36 | Day 3 清晨
```json
[
  {
    "event_id": "evt_0036_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "full_rest_day3",
        "type": "REST",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 720.0,
        "available_stamina": 38.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "REST",
            "target": "camp_core",
            "time_minutes": 360.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "full_recovery",
              "sensory_deprivation",
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
        "action_id": "full_rest_day3",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 12.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 12.4,
        "K": 10.0,
        "probability": 0.539915,
        "random_roll": 0.399327,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.053992,
            "normal": 0.350945,
            "costly": 0.539915,
            "partial_failure": 0.654936,
            "severe_failure": 0.953991
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
        "pressure": 12.0,
        "payoff_maturity": 43.5,
        "payoff_impact": 0.0,
        "payoff_score": 20.48125,
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
            "ACTION_RESOLVED": 30.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.07,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 50.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.5,
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
            "time_remaining": 0.5,
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
          "waiting_time": 100.0,
          "cost_paid": 20.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 62.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 36,
    "timestamp": "Day 3 清晨"
  }
]
```
---
## Turn 37 | Day 3 白天
```json
[
  {
    "event_id": "evt_0037_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "search_food_train",
        "type": "SHORT_ACTION",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 360.0,
        "available_stamina": 73.0,
        "available_mental": 21.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "forage",
              "search",
              "food",
              "exploration"
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
        "action_id": "search_food_train",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 5.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 5.4,
        "K": 10.0,
        "probability": 0.702661,
        "random_roll": 0.05539,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "大成功",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.070266,
            "normal": 0.45673,
            "costly": 0.702661,
            "partial_failure": 0.776996,
            "severe_failure": 0.970266
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
        "pressure": 22.0,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 27.35625,
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
            "ACTION_RESOLVED": 30.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.011667,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 91.666667
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.08333333333333333,
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
            "time_remaining": 0.9166666666666666,
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
          "waiting_time": 100.0,
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
          "decision_change": 40.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 27.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 37,
    "timestamp": "Day 3 白天"
  }
]
```
---
## Turn 38 | Day 3 白天
```json
[
  {
    "event_id": "evt_0038_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "storage_carriage",
    "data": {
      "action": {
        "action_id": "take_ration",
        "type": "SHORT_ACTION",
        "target": "storage_carriage"
      },
      "action_ledger": {
        "available_time_minutes": 330.0,
        "available_stamina": 71.0,
        "available_mental": 17.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "storage_carriage",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "food",
              "survival",
              "resource_use"
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
        "action_id": "take_ration",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 10.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 5.8,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 15.8,
        "K": 10.0,
        "probability": 0.455121,
        "random_roll": 0.724811,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "严重失败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
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
        "pressure": 22.833333,
        "payoff_maturity": 39.5,
        "payoff_impact": 0.0,
        "payoff_score": 24.03125,
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
            "ACTION_RESOLVED": 30.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.012727,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 90.909091
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.09090909090909091,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.3,
          "route_divergence": 0.3,
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
            "time_remaining": 0.9090909090909091,
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
          "waiting_time": 100.0,
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
          "fatigue": 29.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 38,
    "timestamp": "Day 3 白天"
  }
]
```
---
## Turn 39 | Day 3 白天
```json
[
  {
    "event_id": "evt_0039_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "sealed_carriage_door",
    "data": {
      "action": {
        "action_id": "investigate_sealed_door",
        "type": "SHORT_ACTION",
        "target": "sealed_carriage_door"
      },
      "action_ledger": {
        "available_time_minutes": 300.0,
        "available_stamina": 69.0,
        "available_mental": 13.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "sealed_carriage_door",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "investigation",
              "observation",
              "mystery"
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
        "action_id": "investigate_sealed_door",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 10.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 6.2,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 16.2,
        "K": 10.0,
        "probability": 0.445221,
        "random_roll": 0.848594,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "严重失败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
          },
          "outcome_thresholds": {
            "critical": 0.044522,
            "normal": 0.289394,
            "costly": 0.445221,
            "partial_failure": 0.583916,
            "severe_failure": 0.944522
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
        "pressure": 23.666667,
        "payoff_maturity": 39.5,
        "payoff_impact": 0.0,
        "payoff_score": 23.83125,
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
            "ACTION_RESOLVED": 30.0,
            "WAIT_COMPLETED": 0.0
          }
        },
        "agency": 0.014,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 90.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.1,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.3,
          "route_divergence": 0.3,
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
            "time_remaining": 0.9,
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
          "waiting_time": 100.0,
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
          "fatigue": 31.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 39,
    "timestamp": "Day 3 白天"
  }
]
```
---
## Turn 39 | Day 3 白天
```json
[
  {
    "event_id": "evt_0039_options_e225e530",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 39,
        "options": {
          "A": {
            "id": "A",
            "label": "与阿苔交谈",
            "description": "与阿苔交谈",
            "action": {
              "action_id": "auto-npc_atai",
              "type": "SOCIAL_INTERACTION",
              "target": "npc_atai",
              "goal": "与阿苔交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-npc_atai",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 15.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 6.6,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 21.6,
                "K": 10.0,
                "probability": 0.318646,
                "random_roll": 0.961569,
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
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.031865,
                    "normal": 0.20712,
                    "costly": 0.318646,
                    "partial_failure": 0.488984,
                    "severe_failure": 0.931865
                  }
                }
              },
              "target_profile": {
                "id": "npc_atai",
                "location_id": "camp_core",
                "target_difficulty": 15,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.8,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "npc_atai": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "npc_atai_goal"
                    ]
                  }
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "npc_atai"
                },
                "primary_attribute": "spirit",
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "npc_atai"
                }
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
              "action_ledger": {
                "available_time_minutes": 270.0,
                "available_stamina": 67.0,
                "available_mental": 9.0,
                "actions": [
                  {
                    "type": "SOCIAL_INTERACTION",
                    "target": "npc_atai",
                    "time_minutes": 30.0,
                    "stamina_cost": 2.0,
                    "mental_cost": 4.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 39
          }
        }
      },
      "state_turn": 39
    },
    "turn": 39,
    "timestamp": "Day 3 白天"
  }
]
```
---
## Turn 40 | Day 3 白天
```json
[
  {
    "event_id": "evt_0040_001",
    "type": "SOCIAL_RESOLVED",
    "actor": "player",
    "target": "npc_atai",
    "data": {
      "action": {
        "action_id": "auto-npc_atai",
        "type": "SOCIAL_INTERACTION",
        "target": "npc_atai"
      },
      "action_ledger": {
        "available_time_minutes": 270.0,
        "available_stamina": 67.0,
        "available_mental": 9.0,
        "actions": [
          {
            "type": "SOCIAL_INTERACTION",
            "target": "npc_atai",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": []
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
        "action_id": "auto-npc_atai",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 15.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 6.6,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 21.6,
        "K": 10.0,
        "probability": 0.318646,
        "random_roll": 0.961569,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.031865,
            "normal": 0.20712,
            "costly": 0.318646,
            "partial_failure": 0.488984,
            "severe_failure": 0.931865
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
        "pressure": 24.5,
        "payoff_maturity": 39.5,
        "payoff_impact": 21.5,
        "payoff_score": 33.7625,
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
            "ACTION_RESOLVED": 30.0,
            "WAIT_COMPLETED": 0.0,
            "OPTIONS_PRESENTED": 0.0
          }
        },
        "agency": 0.062222,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 88.888889
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.1111111111111111,
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
            "time_remaining": 0.8888888888888888,
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
          "waiting_time": 100.0,
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
          "fatigue": 33.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 40,
    "timestamp": "Day 3 白天"
  }
]
```
---
## Turn 40 | Day 3 黄昏
```json
[
  {
    "event_id": "evt_0040_options_4e6e0491",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 40,
        "options": {
          "A": {
            "id": "A",
            "label": "与阿苔交谈",
            "description": "与阿苔交谈",
            "action": {
              "action_id": "auto-npc_atai",
              "type": "SOCIAL_INTERACTION",
              "target": "npc_atai",
              "goal": "与阿苔交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-npc_atai",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 15.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 7.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 22.0,
                "K": 10.0,
                "probability": 0.310026,
                "random_roll": 0.3629,
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
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.031003,
                    "normal": 0.201517,
                    "costly": 0.310026,
                    "partial_failure": 0.482519,
                    "severe_failure": 0.931003
                  }
                }
              },
              "target_profile": {
                "id": "npc_atai",
                "location_id": "camp_core",
                "target_difficulty": 15,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.8,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "npc_atai": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "npc_atai_goal"
                    ]
                  }
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "npc_atai"
                },
                "primary_attribute": "spirit",
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "npc_atai"
                }
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
                      "黄昏"
                    ],
                    "capacity": 1
                  }
                ],
                "allowed_periods": [],
                "npc_unavailable": false
              },
              "action_ledger": {
                "available_time_minutes": 240.0,
                "available_stamina": 65.0,
                "available_mental": 5.0,
                "actions": [
                  {
                    "type": "SOCIAL_INTERACTION",
                    "target": "npc_atai",
                    "time_minutes": 30.0,
                    "stamina_cost": 2.0,
                    "mental_cost": 4.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 40
          }
        }
      },
      "state_turn": 40
    },
    "turn": 40,
    "timestamp": "Day 3 黄昏"
  }
]
```
---
## Turn 41 | Day 3 黄昏
```json
[
  {
    "event_id": "evt_0041_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "storage_carriage",
    "data": {
      "action": {
        "action_id": "cautious_eat",
        "type": "SHORT_ACTION",
        "target": "storage_carriage"
      },
      "action_ledger": {
        "available_time_minutes": 240.0,
        "available_stamina": 65.0,
        "available_mental": 5.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "storage_carriage",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "food",
              "cautious",
              "recovery"
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
        "action_id": "cautious_eat",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 10.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 7.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 17.0,
        "K": 10.0,
        "probability": 0.425557,
        "random_roll": 0.07091,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "普通成功",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
            "ability_match": 14.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
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
      "proposed_events": [],
      "runtime_metrics": {
        "pressure": 25.333333,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 24.55625,
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
            "ACTION_RESOLVED": 30.0,
            "WAIT_COMPLETED": 0.0,
            "OPTIONS_PRESENTED": 30.0,
            "SOCIAL_RESOLVED": 0.0
          }
        },
        "agency": 0.0175,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 87.5
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.125,
          "irreversibility": 0.5,
          "information_uncertainty": 0.0,
          "value_impact": 0.3,
          "route_divergence": 0.3,
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
            "time_remaining": 0.875,
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
          "waiting_time": 100.0,
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
          "fatigue": 35.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 41,
    "timestamp": "Day 3 黄昏"
  }
]
```
---
## Turn 42 | Day 3 黄昏
```json
[
  {
    "event_id": "evt_0042_001",
    "type": "WAIT_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "sleep_silent_night",
        "type": "WAIT",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 210.0,
        "available_stamina": 63.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "WAIT",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "wait",
              "recovery"
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
        "action_type": "WAIT",
        "outcome": "普通成功",
        "probability": 1.0,
        "risk_mode": "deterministic_wait",
        "time_cost": 30.0,
        "wait_minutes": 30.0
      },
      "fatigue_delta": 0.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [
        {
          "type": "TIME_ADVANCED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 26.166667,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 24.35625,
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
            "ACTION_RESOLVED": 27.0,
            "WAIT_COMPLETED": 0.0,
            "OPTIONS_PRESENTED": 30.0,
            "SOCIAL_RESOLVED": 0.0
          }
        },
        "agency": 0.02,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 85.714286
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.14285714285714285,
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
            "time_remaining": 0.8571428571428572,
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
          "waiting_time": 100.0,
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
          "fatigue": 37.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 42,
    "timestamp": "Day 3 黄昏"
  }
]
```
---
## Turn 43 | Day 3 黄昏
```json
[
  {
    "event_id": "evt_0043_001",
    "type": "WAIT_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "sleep_through_night",
        "type": "WAIT",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 180.0,
        "available_stamina": 63.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "WAIT",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "wait",
              "night"
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
        "action_type": "WAIT",
        "outcome": "普通成功",
        "probability": 1.0,
        "risk_mode": "deterministic_wait",
        "time_cost": 30.0,
        "wait_minutes": 30.0
      },
      "fatigue_delta": 0.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [
        {
          "type": "TIME_ADVANCED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 27.0,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 24.35625,
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
            "WAIT_COMPLETED": 0.0,
            "ACTION_RESOLVED": 26.25,
            "OPTIONS_PRESENTED": 30.0,
            "SOCIAL_RESOLVED": 0.0
          }
        },
        "agency": 0.023333,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 83.333333
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.16666666666666666,
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
            "time_remaining": 0.8333333333333334,
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
          "waiting_time": 100.0,
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
          "fatigue": 37.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 43,
    "timestamp": "Day 3 黄昏"
  }
]
```
---
## Turn 44 | Day 3 黄昏
```json
[
  {
    "event_id": "evt_0044_001",
    "type": "WAIT_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "wait_night2",
        "type": "WAIT",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 150.0,
        "available_stamina": 63.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "WAIT",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "wait"
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
        "action_type": "WAIT",
        "outcome": "普通成功",
        "probability": 1.0,
        "risk_mode": "deterministic_wait",
        "time_cost": 30.0,
        "wait_minutes": 30.0
      },
      "fatigue_delta": 0.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [
        {
          "type": "TIME_ADVANCED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 27.833333,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 24.35625,
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
            "ACTION_RESOLVED": 26.25,
            "OPTIONS_PRESENTED": 30.0,
            "SOCIAL_RESOLVED": 0.0,
            "WAIT_COMPLETED": 30.0
          }
        },
        "agency": 0.028,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 80.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.2,
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
            "time_remaining": 0.8,
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
          "waiting_time": 100.0,
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
          "fatigue": 37.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 44,
    "timestamp": "Day 3 黄昏"
  }
]
```
---
## Turn 45 | Day 3 夜晚
```json
[
  {
    "event_id": "evt_0045_001",
    "type": "WAIT_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "wait_night3",
        "type": "WAIT",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 120.0,
        "available_stamina": 63.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "WAIT",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "wait"
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
        "action_type": "WAIT",
        "outcome": "普通成功",
        "probability": 1.0,
        "risk_mode": "deterministic_wait",
        "time_cost": 30.0,
        "wait_minutes": 30.0
      },
      "fatigue_delta": 0.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [
        {
          "type": "TIME_ADVANCED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 28.666667,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 24.35625,
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
            "ACTION_RESOLVED": 25.0,
            "OPTIONS_PRESENTED": 30.0,
            "SOCIAL_RESOLVED": 0.0,
            "WAIT_COMPLETED": 30.0
          }
        },
        "agency": 0.035,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 75.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.25,
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
            "time_remaining": 0.75,
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
          "waiting_time": 100.0,
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
          "fatigue": 37.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 45,
    "timestamp": "Day 3 夜晚"
  }
]
```
---
## Turn 46 | Day 3 夜晚
```json
[
  {
    "event_id": "evt_0046_001",
    "type": "WAIT_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "wait_night4",
        "type": "WAIT",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 90.0,
        "available_stamina": 63.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "WAIT",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "wait"
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
        "action_type": "WAIT",
        "outcome": "普通成功",
        "probability": 1.0,
        "risk_mode": "deterministic_wait",
        "time_cost": 30.0,
        "wait_minutes": 30.0
      },
      "fatigue_delta": 0.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [
        {
          "type": "TIME_ADVANCED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 29.5,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 24.35625,
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
            "ACTION_RESOLVED": 22.5,
            "OPTIONS_PRESENTED": 30.0,
            "SOCIAL_RESOLVED": 0.0,
            "WAIT_COMPLETED": 30.0
          }
        },
        "agency": 0.046667,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 66.666667
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.3333333333333333,
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
            "time_remaining": 0.6666666666666667,
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
          "waiting_time": 100.0,
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
          "fatigue": 37.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 46,
    "timestamp": "Day 3 夜晚"
  }
]
```
---
## Turn 47 | Day 3 夜晚
```json
[
  {
    "event_id": "evt_0047_001",
    "type": "WAIT_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "wait_night5",
        "type": "WAIT",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 60.0,
        "available_stamina": 63.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "WAIT",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "wait"
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
        "action_type": "WAIT",
        "outcome": "普通成功",
        "probability": 1.0,
        "risk_mode": "deterministic_wait",
        "time_cost": 30.0,
        "wait_minutes": 30.0
      },
      "fatigue_delta": 0.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [
        {
          "type": "TIME_ADVANCED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 30.333333,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 24.35625,
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
            "ACTION_RESOLVED": 15.0,
            "OPTIONS_PRESENTED": 30.0,
            "SOCIAL_RESOLVED": 0.0,
            "WAIT_COMPLETED": 30.0
          }
        },
        "agency": 0.07,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 50.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.5,
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
            "time_remaining": 0.5,
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
          "waiting_time": 100.0,
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
          "fatigue": 37.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 47,
    "timestamp": "Day 3 夜晚"
  }
]
```
---
## Turn 48 | Day 3 夜晚
```json
[
  {
    "event_id": "evt_0048_001",
    "type": "WAIT_COMPLETED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "wait_dawn4",
        "type": "WAIT",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 30.0,
        "available_stamina": 63.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "WAIT",
            "target": "camp_core",
            "time_minutes": 30.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "wait",
              "dawn"
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
        "action_type": "WAIT",
        "outcome": "普通成功",
        "probability": 1.0,
        "risk_mode": "deterministic_wait",
        "time_cost": 30.0,
        "wait_minutes": 30.0
      },
      "fatigue_delta": 0.0,
      "mental_delta": -0.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "proposed_events": [
        {
          "type": "TIME_ADVANCED",
          "target": "camp_core"
        }
      ],
      "runtime_metrics": {
        "pressure": 31.166667,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 24.35625,
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
            "OPTIONS_PRESENTED": 30.0,
            "SOCIAL_RESOLVED": 0.0,
            "ACTION_RESOLVED": 0.0,
            "WAIT_COMPLETED": 30.0
          }
        },
        "agency": 0.14,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 0.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 1.0,
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
            "time_remaining": 0.0,
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
          "waiting_time": 100.0,
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
          "fatigue": 37.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 48,
    "timestamp": "Day 3 夜晚"
  }
]
```
---
## Turn 49 | Day 4 清晨
```json
[
  {
    "event_id": "evt_0049_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "full_rest_day4",
        "type": "REST",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 720.0,
        "available_stamina": 63.0,
        "available_mental": 1.0,
        "actions": [
          {
            "type": "REST",
            "target": "camp_core",
            "time_minutes": 360.0,
            "stamina_cost": 0.0,
            "mental_cost": 0.0,
            "tags": [
              "sleep",
              "full_recovery",
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
        "action_id": "full_rest_day4",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 7.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 7.4,
        "K": 10.0,
        "probability": 0.65926,
        "random_roll": 0.941065,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.065926,
            "normal": 0.428519,
            "costly": 0.65926,
            "partial_failure": 0.744445,
            "severe_failure": 0.965926
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
        "pressure": 12.0,
        "payoff_maturity": 39.5,
        "payoff_impact": 0.0,
        "payoff_score": 23.23125,
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
            "SOCIAL_RESOLVED": 0.0,
            "OPTIONS_PRESENTED": 0.0,
            "ACTION_RESOLVED": 0.0,
            "WAIT_COMPLETED": 30.0
          }
        },
        "agency": 0.07,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 50.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.5,
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
            "time_remaining": 0.5,
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
          "waiting_time": 100.0,
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
          "fatigue": 37.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 49,
    "timestamp": "Day 4 清晨"
  }
]
```
---
## Turn 49 | Day 4 白天
```json
[
  {
    "event_id": "evt_0049_options_1bbd6cb3",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 49,
        "options": {
          "A": {
            "id": "A",
            "label": "与阿苔交谈",
            "description": "与阿苔交谈",
            "action": {
              "action_id": "auto-npc_atai",
              "type": "SOCIAL_INTERACTION",
              "target": "npc_atai",
              "goal": "与阿苔交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-npc_atai",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 15.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.4,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 15.4,
                "K": 10.0,
                "probability": 0.465057,
                "random_roll": 0.573241,
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
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.046506,
                    "normal": 0.302287,
                    "costly": 0.465057,
                    "partial_failure": 0.598793,
                    "severe_failure": 0.946506
                  }
                }
              },
              "target_profile": {
                "id": "npc_atai",
                "location_id": "camp_core",
                "target_difficulty": 15,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.8,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "npc_atai": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "npc_atai_goal"
                    ]
                  }
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "npc_atai"
                },
                "primary_attribute": "spirit",
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "npc_atai"
                }
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
              "action_ledger": {
                "available_time_minutes": 360.0,
                "available_stamina": 98.0,
                "available_mental": 21.0,
                "actions": [
                  {
                    "type": "SOCIAL_INTERACTION",
                    "target": "npc_atai",
                    "time_minutes": 30.0,
                    "stamina_cost": 2.0,
                    "mental_cost": 4.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 49
          },
          "B": {
            "id": "B",
            "label": "休息恢复",
            "description": "",
            "action": {
              "action_id": "auto-rest",
              "type": "REST",
              "target": "camp_core"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-rest",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 0.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.4,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 0.4,
                "K": 10.0,
                "probability": 0.79576,
                "random_roll": 0.684279,
                "severity": 0.0,
                "severity_band": "成功区",
                "death_fairness": 0.0,
                "outcome": "成功但付出代价",
                "death_allowed": false,
                "components": {
                  "severity": {
                    "difficulty": 0.0,
                    "injury": 0.0,
                    "resource_shortage": 0.0,
                    "information_missing": 0.0,
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.079576,
                    "normal": 0.517244,
                    "costly": 0.79576,
                    "partial_failure": 0.84682,
                    "severe_failure": 0.979576
                  }
                }
              },
              "target_profile": {
                "id": "camp_core",
                "target_difficulty": 0,
                "effects": {}
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
              "action_ledger": {
                "available_time_minutes": 360.0,
                "available_stamina": 98.0,
                "available_mental": 21.0,
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
              "skill": null
            },
            "state_turn": 49
          }
        }
      },
      "state_turn": 49
    },
    "turn": 49,
    "timestamp": "Day 4 白天"
  }
]
```
---
## Turn 50 | Day 4 白天
```json
[
  {
    "event_id": "evt_0050_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "auto-rest",
        "type": "REST",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 360.0,
        "available_stamina": 98.0,
        "available_mental": 21.0,
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
        "action_id": "auto-rest",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 0.4,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 0.4,
        "K": 10.0,
        "probability": 0.79576,
        "random_roll": 0.684279,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.079576,
            "normal": 0.517244,
            "costly": 0.79576,
            "partial_failure": 0.84682,
            "severe_failure": 0.979576
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
        "pressure": 22.0,
        "payoff_maturity": 43.5,
        "payoff_impact": 0.0,
        "payoff_score": 26.48125,
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
            "ACTION_RESOLVED": 0.0,
            "WAIT_COMPLETED": 30.0,
            "OPTIONS_PRESENTED": 0.0
          }
        },
        "agency": 0.14,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 0.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 1.0,
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
            "time_remaining": 0.0,
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
          "waiting_time": 100.0,
          "cost_paid": 20.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 2.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 50,
    "timestamp": "Day 4 白天"
  }
]
```
---
## Turn 50 | Day 5 清晨
```json
[
  {
    "event_id": "evt_0050_options_73028e2d",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 50,
        "options": {
          "A": {
            "id": "A",
            "label": "与阿苔交谈",
            "description": "与阿苔交谈",
            "action": {
              "action_id": "auto-npc_atai",
              "type": "SOCIAL_INTERACTION",
              "target": "npc_atai",
              "goal": "与阿苔交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-npc_atai",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 15.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 15.0,
                "K": 10.0,
                "probability": 0.475021,
                "random_roll": 0.867472,
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
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.047502,
                    "normal": 0.308764,
                    "costly": 0.475021,
                    "partial_failure": 0.606266,
                    "severe_failure": 0.947502
                  }
                }
              },
              "target_profile": {
                "id": "npc_atai",
                "location_id": "camp_core",
                "target_difficulty": 15,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.8,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "npc_atai": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "npc_atai_goal"
                    ]
                  }
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "npc_atai"
                },
                "primary_attribute": "spirit",
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "npc_atai"
                }
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
              "action_ledger": {
                "available_time_minutes": 720.0,
                "available_stamina": 100.0,
                "available_mental": 41.0,
                "actions": [
                  {
                    "type": "SOCIAL_INTERACTION",
                    "target": "npc_atai",
                    "time_minutes": 30.0,
                    "stamina_cost": 2.0,
                    "mental_cost": 4.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 50
          },
          "B": {
            "id": "B",
            "label": "休息恢复",
            "description": "",
            "action": {
              "action_id": "auto-rest",
              "type": "REST",
              "target": "camp_core"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-rest",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 0.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 0.0,
                "K": 10.0,
                "probability": 0.802184,
                "random_roll": 0.161613,
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
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.080218,
                    "normal": 0.52142,
                    "costly": 0.802184,
                    "partial_failure": 0.851638,
                    "severe_failure": 0.980218
                  }
                }
              },
              "target_profile": {
                "id": "camp_core",
                "target_difficulty": 0,
                "effects": {}
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
              "action_ledger": {
                "available_time_minutes": 720.0,
                "available_stamina": 100.0,
                "available_mental": 41.0,
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
              "skill": null
            },
            "state_turn": 50
          }
        }
      },
      "state_turn": 50
    },
    "turn": 50,
    "timestamp": "Day 5 清晨"
  }
]
```
---
## Turn 50 | Day 5 清晨
```json
[
  {
    "event_id": "evt_0050_options_7d043d57",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 50,
        "options": {
          "A": {
            "id": "A",
            "label": "与阿苔交谈",
            "description": "与阿苔交谈",
            "action": {
              "action_id": "auto-npc_atai",
              "type": "SOCIAL_INTERACTION",
              "target": "npc_atai",
              "goal": "与阿苔交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-npc_atai",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 15.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 15.0,
                "K": 10.0,
                "probability": 0.475021,
                "random_roll": 0.867472,
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
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.047502,
                    "normal": 0.308764,
                    "costly": 0.475021,
                    "partial_failure": 0.606266,
                    "severe_failure": 0.947502
                  }
                }
              },
              "target_profile": {
                "id": "npc_atai",
                "location_id": "camp_core",
                "target_difficulty": 15,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.8,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "npc_atai": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "npc_atai_goal"
                    ]
                  }
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "npc_atai"
                },
                "primary_attribute": "spirit",
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "npc_atai"
                }
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
              "action_ledger": {
                "available_time_minutes": 720.0,
                "available_stamina": 100.0,
                "available_mental": 41.0,
                "actions": [
                  {
                    "type": "SOCIAL_INTERACTION",
                    "target": "npc_atai",
                    "time_minutes": 30.0,
                    "stamina_cost": 2.0,
                    "mental_cost": 4.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 50
          },
          "B": {
            "id": "B",
            "label": "休息恢复",
            "description": "",
            "action": {
              "action_id": "auto-rest",
              "type": "REST",
              "target": "camp_core"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-rest",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 0.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 0.0,
                "K": 10.0,
                "probability": 0.802184,
                "random_roll": 0.161613,
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
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.080218,
                    "normal": 0.52142,
                    "costly": 0.802184,
                    "partial_failure": 0.851638,
                    "severe_failure": 0.980218
                  }
                }
              },
              "target_profile": {
                "id": "camp_core",
                "target_difficulty": 0,
                "effects": {}
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
              "action_ledger": {
                "available_time_minutes": 720.0,
                "available_stamina": 100.0,
                "available_mental": 41.0,
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
              "skill": null
            },
            "state_turn": 50
          }
        }
      },
      "state_turn": 50
    },
    "turn": 50,
    "timestamp": "Day 5 清晨"
  }
]
```
---
## Turn 51 | Day 5 清晨
```json
[
  {
    "event_id": "evt_0051_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "auto-rest",
        "type": "REST",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 720.0,
        "available_stamina": 100.0,
        "available_mental": 41.0,
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
        "action_id": "auto-rest",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 0.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 0.0,
        "K": 10.0,
        "probability": 0.802184,
        "random_roll": 0.161613,
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
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.080218,
            "normal": 0.52142,
            "costly": 0.802184,
            "partial_failure": 0.851638,
            "severe_failure": 0.980218
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
        "pressure": 12.0,
        "payoff_maturity": 39.5,
        "payoff_impact": 12.5,
        "payoff_score": 28.05625,
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
            "WAIT_COMPLETED": 30.0,
            "ACTION_RESOLVED": 30.0,
            "OPTIONS_PRESENTED": 30.0
          }
        },
        "agency": 0.07,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 50.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.5,
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
            "time_remaining": 0.5,
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
          "waiting_time": 100.0,
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
          "fatigue": 0.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 51,
    "timestamp": "Day 5 清晨"
  }
]
```
---
## Turn 51 | Day 5 白天
```json
[
  {
    "event_id": "evt_0051_options_7ce4e089",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 51,
        "options": {
          "A": {
            "id": "A",
            "label": "与阿苔交谈",
            "description": "与阿苔交谈",
            "action": {
              "action_id": "auto-npc_atai",
              "type": "SOCIAL_INTERACTION",
              "target": "npc_atai",
              "goal": "与阿苔交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-npc_atai",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 15.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 15.0,
                "K": 10.0,
                "probability": 0.475021,
                "random_roll": 0.178219,
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
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.047502,
                    "normal": 0.308764,
                    "costly": 0.475021,
                    "partial_failure": 0.606266,
                    "severe_failure": 0.947502
                  }
                }
              },
              "target_profile": {
                "id": "npc_atai",
                "location_id": "camp_core",
                "target_difficulty": 15,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.8,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "npc_atai": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "npc_atai_goal"
                    ]
                  }
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "npc_atai"
                },
                "primary_attribute": "spirit",
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "npc_atai"
                }
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
              "action_ledger": {
                "available_time_minutes": 360.0,
                "available_stamina": 100.0,
                "available_mental": 61.0,
                "actions": [
                  {
                    "type": "SOCIAL_INTERACTION",
                    "target": "npc_atai",
                    "time_minutes": 30.0,
                    "stamina_cost": 2.0,
                    "mental_cost": 4.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 51
          },
          "B": {
            "id": "B",
            "label": "休息恢复",
            "description": "",
            "action": {
              "action_id": "auto-rest",
              "type": "REST",
              "target": "camp_core"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-rest",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 0.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 0.0,
                "K": 10.0,
                "probability": 0.802184,
                "random_roll": 0.732956,
                "severity": 0.0,
                "severity_band": "成功区",
                "death_fairness": 0.0,
                "outcome": "成功但付出代价",
                "death_allowed": false,
                "components": {
                  "severity": {
                    "difficulty": 0.0,
                    "injury": 0.0,
                    "resource_shortage": 0.0,
                    "information_missing": 0.0,
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.080218,
                    "normal": 0.52142,
                    "costly": 0.802184,
                    "partial_failure": 0.851638,
                    "severe_failure": 0.980218
                  }
                }
              },
              "target_profile": {
                "id": "camp_core",
                "target_difficulty": 0,
                "effects": {}
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
              "action_ledger": {
                "available_time_minutes": 360.0,
                "available_stamina": 100.0,
                "available_mental": 61.0,
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
              "skill": null
            },
            "state_turn": 51
          }
        }
      },
      "state_turn": 51
    },
    "turn": 51,
    "timestamp": "Day 5 白天"
  }
]
```
---
## Turn 52 | Day 5 白天
```json
[
  {
    "event_id": "evt_0052_001",
    "type": "ACTION_RESOLVED",
    "actor": "player",
    "target": "camp_core",
    "data": {
      "action": {
        "action_id": "auto-rest",
        "type": "REST",
        "target": "camp_core"
      },
      "action_ledger": {
        "available_time_minutes": 360.0,
        "available_stamina": 100.0,
        "available_mental": 61.0,
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
        "action_id": "auto-rest",
        "advantage_components": {
          "ability_match": 14.0,
          "equipment_advantage": 0.0,
          "preparation": 0.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 0.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 0.0,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 14.0,
        "resistance": 0.0,
        "K": 10.0,
        "probability": 0.802184,
        "random_roll": 0.732956,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 0.0,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 0.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 0.0,
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
            "critical": 0.080218,
            "normal": 0.52142,
            "costly": 0.802184,
            "partial_failure": 0.851638,
            "severe_failure": 0.980218
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
        "pressure": 22.0,
        "payoff_maturity": 43.5,
        "payoff_impact": 0.0,
        "payoff_score": 26.68125,
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
            "WAIT_COMPLETED": 30.0,
            "ACTION_RESOLVED": 22.5,
            "OPTIONS_PRESENTED": 30.0
          }
        },
        "agency": 0.14,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 0.0
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 1.0,
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
            "time_remaining": 0.0,
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
          "waiting_time": 100.0,
          "cost_paid": 20.0,
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
          "decision_change": 0.0,
          "higher_resource_need": 0.0,
          "social_market_effect": 0.0,
          "fatigue": 0.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 52,
    "timestamp": "Day 5 白天"
  }
]
```
---
## Turn 52 | Day 6 清晨
```json
[
  {
    "event_id": "evt_0052_options_652d030a",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 52,
        "options": {
          "A": {
            "id": "A",
            "label": "与阿苔交谈",
            "description": "与阿苔交谈",
            "action": {
              "action_id": "auto-npc_atai",
              "type": "SOCIAL_INTERACTION",
              "target": "npc_atai",
              "goal": "与阿苔交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-npc_atai",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 15.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 15.0,
                "K": 10.0,
                "probability": 0.475021,
                "random_roll": 0.68185,
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
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.047502,
                    "normal": 0.308764,
                    "costly": 0.475021,
                    "partial_failure": 0.606266,
                    "severe_failure": 0.947502
                  }
                }
              },
              "target_profile": {
                "id": "npc_atai",
                "location_id": "camp_core",
                "target_difficulty": 15,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.8,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "npc_atai": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "npc_atai_goal"
                    ]
                  }
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "npc_atai"
                },
                "primary_attribute": "spirit",
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "npc_atai"
                }
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
              "action_ledger": {
                "available_time_minutes": 720.0,
                "available_stamina": 100.0,
                "available_mental": 81.0,
                "actions": [
                  {
                    "type": "SOCIAL_INTERACTION",
                    "target": "npc_atai",
                    "time_minutes": 30.0,
                    "stamina_cost": 2.0,
                    "mental_cost": 4.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 52
          },
          "B": {
            "id": "B",
            "label": "休息恢复",
            "description": "",
            "action": {
              "action_id": "auto-rest",
              "type": "REST",
              "target": "camp_core"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-rest",
                "advantage_components": {
                  "ability_match": 14.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 0.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 14.0,
                "resistance": 0.0,
                "K": 10.0,
                "probability": 0.802184,
                "random_roll": 0.579449,
                "severity": 0.0,
                "severity_band": "成功区",
                "death_fairness": 0.0,
                "outcome": "成功但付出代价",
                "death_allowed": false,
                "components": {
                  "severity": {
                    "difficulty": 0.0,
                    "injury": 0.0,
                    "resource_shortage": 0.0,
                    "information_missing": 0.0,
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
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
                    "critical": 0.080218,
                    "normal": 0.52142,
                    "costly": 0.802184,
                    "partial_failure": 0.851638,
                    "severe_failure": 0.980218
                  }
                }
              },
              "target_profile": {
                "id": "camp_core",
                "target_difficulty": 0,
                "effects": {}
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
              "action_ledger": {
                "available_time_minutes": 720.0,
                "available_stamina": 100.0,
                "available_mental": 81.0,
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
              "skill": null
            },
            "state_turn": 52
          }
        }
      },
      "state_turn": 52
    },
    "turn": 52,
    "timestamp": "Day 6 清晨"
  }
]
```
