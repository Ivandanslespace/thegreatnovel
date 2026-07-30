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
## Turn 1 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0001_options_28641fbe",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 1,
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
                  "target_difficulty": 6.0,
                  "environment_penalty": 0.0,
                  "injury": 0.0,
                  "fatigue": 0.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 6.0,
                "K": 10.0,
                "probability": 0.598688,
                "random_roll": 0.433667,
                "severity": 0.0,
                "severity_band": "成功区",
                "death_fairness": 0.63,
                "outcome": "普通成功",
                "death_allowed": false,
                "components": {
                  "severity": {
                    "difficulty": 1.2,
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
                    "avoidable": 0.9,
                    "rule_consistency": 1.0,
                    "player_responsibility": 0.7
                  },
                  "outcome_thresholds": {
                    "critical": 0.047895,
                    "normal": 0.466977,
                    "costly": 0.598688,
                    "partial_failure": 0.839475,
                    "severe_failure": 0.979934
                  }
                }
              },
              "target_profile": {
                "id": "npc_atai",
                "location_id": "camp_core",
                "target_difficulty": 6,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.9,
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
                      "npc_atai_goal",
                      "npc_atai_routine"
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
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 1
          },
          "B": {
            "id": "B",
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
                "target_difficulty": 14,
                "environment_penalty": 3,
                "unknown_risk": 5,
                "risk_warning": 0.7,
                "causal_chain": 0.85,
                "avoidable": 0.8,
                "rule_consistency": 1.0,
                "player_responsibility": 0.8,
                "effects": {
                  "success": {
                    "discover_locations": [
                      "scrap_yard"
                    ],
                    "resource_changes": {
                      "燃油": 3
                    },
                    "knowledge_additions": [
                      "wasteland_raider_lv1_behavior"
                    ]
                  },
                  "partial_failure": {
                    "resource_changes": {
                      "燃油": 1
                    },
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
                "action_type": "EXPLORATION",
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
                "available_time_minutes": 720.0,
                "available_stamina": 100.0,
                "available_mental": 100.0,
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
            "state_turn": 1
          },
          "C": {
            "id": "C",
            "label": "建造燃油蒸馏器",
            "description": "",
            "action": {
              "action_id": "auto-build-fuel_still",
              "type": "BUILD",
              "target": "fuel_still"
            },
            "preview": {
              "legal": true,
              "errors": [],
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
              "action_ledger": {
                "available_time_minutes": 120.0,
                "actions": [
                  {
                    "type": "BUILD",
                    "target": "fuel_still",
                    "time_minutes": 60.0,
                    "stamina_cost": 20.0,
                    "mental_cost": 5.0,
                    "tags": [
                      "major_action",
                      "requires_full_attention"
                    ]
                  }
                ]
              }
            },
            "state_turn": 1
          }
        }
      },
      "state_turn": 1
    },
    "turn": 1,
    "timestamp": "Day 1 清晨"
  }
]
```
