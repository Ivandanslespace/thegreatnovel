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
      "world_name": "废土列车·双语",
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
## Turn 3 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0003_options_2c150013",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 3,
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
                  "ability_match": 10.0,
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
                "advantage": 10.0,
                "resistance": 15.4,
                "K": 10.0,
                "probability": 0.368188,
                "random_roll": 0.395428,
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
                    "critical": 0.036819,
                    "normal": 0.239322,
                    "costly": 0.368188,
                    "partial_failure": 0.526141,
                    "severe_failure": 0.936819
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
                "action_type": "SOCIAL_INTERACTION",
                "is_npc": true,
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
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 3
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
                  "fatigue": 0.4,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 0.4,
                "K": 10.0,
                "probability": 0.723122,
                "random_roll": 0.773451,
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
                    "critical": 0.072312,
                    "normal": 0.470029,
                    "costly": 0.723122,
                    "partial_failure": 0.792342,
                    "severe_failure": 0.972312
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
                "available_time_minutes": 690.0,
                "available_stamina": 98.0,
                "available_mental": 96.0,
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
            "state_turn": 3
          }
        }
      },
      "state_turn": 3
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
        "action_id": "auto-npc_atai",
        "advantage_components": {
          "ability_match": 10.0,
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
        "advantage": 10.0,
        "resistance": 15.4,
        "K": 10.0,
        "probability": 0.368188,
        "random_roll": 0.395428,
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
            "critical": 0.036819,
            "normal": 0.239322,
            "costly": 0.368188,
            "partial_failure": 0.526141,
            "severe_failure": 0.936819
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
        "pressure": 15.833333,
        "payoff_maturity": 22.5,
        "payoff_impact": 21.5,
        "payoff_score": 32.6125,
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
            "OPTIONS_PRESENTED": 0.0
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
          "waiting_time": 15.0,
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
    "turn": 4,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 4 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0004_options_bb6b3e30",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 4,
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
                  "ability_match": 10.0,
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
                  "fatigue": 0.8,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 15.8,
                "K": 10.0,
                "probability": 0.358933,
                "random_roll": 0.311923,
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
                    "critical": 0.035893,
                    "normal": 0.233306,
                    "costly": 0.358933,
                    "partial_failure": 0.5192,
                    "severe_failure": 0.935893
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
                "action_type": "SOCIAL_INTERACTION",
                "is_npc": true,
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
                "available_time_minutes": 660.0,
                "available_stamina": 96.0,
                "available_mental": 92.0,
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
            "state_turn": 4
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
                  "fatigue": 0.8,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 0.8,
                "K": 10.0,
                "probability": 0.715042,
                "random_roll": 0.098844,
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
                    "critical": 0.071504,
                    "normal": 0.464777,
                    "costly": 0.715042,
                    "partial_failure": 0.786281,
                    "severe_failure": 0.971504
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
                "available_time_minutes": 660.0,
                "available_stamina": 96.0,
                "available_mental": 92.0,
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
            "state_turn": 4
          }
        }
      },
      "state_turn": 4
    },
    "turn": 4,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 4 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0004_options_70434397",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 4,
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
                  "ability_match": 10.0,
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
                  "fatigue": 0.8,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 15.8,
                "K": 10.0,
                "probability": 0.358933,
                "random_roll": 0.311923,
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
                    "critical": 0.035893,
                    "normal": 0.233306,
                    "costly": 0.358933,
                    "partial_failure": 0.5192,
                    "severe_failure": 0.935893
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
                "action_type": "SOCIAL_INTERACTION",
                "is_npc": true,
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
                "available_time_minutes": 660.0,
                "available_stamina": 96.0,
                "available_mental": 92.0,
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
            "state_turn": 4
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
                  "fatigue": 0.8,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 0.8,
                "K": 10.0,
                "probability": 0.715042,
                "random_roll": 0.098844,
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
                    "critical": 0.071504,
                    "normal": 0.464777,
                    "costly": 0.715042,
                    "partial_failure": 0.786281,
                    "severe_failure": 0.971504
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
                "available_time_minutes": 660.0,
                "available_stamina": 96.0,
                "available_mental": 92.0,
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
            "state_turn": 4
          }
        }
      },
      "state_turn": 4
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
        "available_time_minutes": 660.0,
        "available_stamina": 96.0,
        "available_mental": 92.0,
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
        "action_id": "auto-npc_atai",
        "advantage_components": {
          "ability_match": 10.0,
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
          "fatigue": 0.8,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 10.0,
        "resistance": 15.8,
        "K": 10.0,
        "probability": 0.358933,
        "random_roll": 0.311923,
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
            "critical": 0.035893,
            "normal": 0.233306,
            "costly": 0.358933,
            "partial_failure": 0.5192,
            "severe_failure": 0.935893
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
        "pressure": 16.666667,
        "payoff_maturity": 27.5,
        "payoff_impact": 21.5,
        "payoff_score": 34.4125,
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
            "OPTIONS_PRESENTED": 30.0,
            "SOCIAL_RESOLVED": 0.0
          }
        },
        "agency": 0.025455,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.454545
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.045454545454545456,
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
            "time_remaining": 0.9545454545454546,
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
          "waiting_time": 20.0,
          "cost_paid": 20.0,
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
## Turn 5 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0005_options_7e896ac7",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 5,
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
                  "ability_match": 10.0,
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
                "advantage": 10.0,
                "resistance": 16.2,
                "K": 10.0,
                "probability": 0.349781,
                "random_roll": 0.885983,
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
                    "critical": 0.034978,
                    "normal": 0.227358,
                    "costly": 0.349781,
                    "partial_failure": 0.512336,
                    "severe_failure": 0.934978
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
                "action_type": "SOCIAL_INTERACTION",
                "is_npc": true,
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
                "available_time_minutes": 630.0,
                "available_stamina": 94.0,
                "available_mental": 88.0,
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
            "state_turn": 5
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
                  "fatigue": 1.2,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 1.2,
                "K": 10.0,
                "probability": 0.706822,
                "random_roll": 0.597253,
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
                    "critical": 0.070682,
                    "normal": 0.459434,
                    "costly": 0.706822,
                    "partial_failure": 0.780116,
                    "severe_failure": 0.970682
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
                "available_time_minutes": 630.0,
                "available_stamina": 94.0,
                "available_mental": 88.0,
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
            "state_turn": 5
          }
        }
      },
      "state_turn": 5
    },
    "turn": 5,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 5 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0005_options_ccf44234",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 5,
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
                  "ability_match": 10.0,
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
                "advantage": 10.0,
                "resistance": 16.2,
                "K": 10.0,
                "probability": 0.349781,
                "random_roll": 0.885983,
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
                    "critical": 0.034978,
                    "normal": 0.227358,
                    "costly": 0.349781,
                    "partial_failure": 0.512336,
                    "severe_failure": 0.934978
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
                "action_type": "SOCIAL_INTERACTION",
                "is_npc": true,
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
                "available_time_minutes": 630.0,
                "available_stamina": 94.0,
                "available_mental": 88.0,
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
            "state_turn": 5
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
                  "fatigue": 1.2,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 1.2,
                "K": 10.0,
                "probability": 0.706822,
                "random_roll": 0.597253,
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
                    "critical": 0.070682,
                    "normal": 0.459434,
                    "costly": 0.706822,
                    "partial_failure": 0.780116,
                    "severe_failure": 0.970682
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
                "available_time_minutes": 630.0,
                "available_stamina": 94.0,
                "available_mental": 88.0,
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
            "state_turn": 5
          }
        }
      },
      "state_turn": 5
    },
    "turn": 5,
    "timestamp": "Day 1 清晨"
  }
]
```
