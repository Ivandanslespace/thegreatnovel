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
