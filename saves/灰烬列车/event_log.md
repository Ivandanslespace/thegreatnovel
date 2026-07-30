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
      "world_name": "灰烬列车",
      "theme": "废土列车",
      "safe_base": "废土列车·铁蛇号",
      "difficulty": "标准",
      "generation_source": "llm_world_blueprint",
      "genre_contract_id": "mass_system_survival",
      "public_system_enabled": true,
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
    "event_id": "evt_0001_options_d2044429",
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
            "label": "与老金交谈",
            "description": "与老金交谈",
            "action": {
              "action_id": "auto-old_jin",
              "type": "SOCIAL_INTERACTION",
              "target": "old_jin",
              "goal": "与老金交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-old_jin",
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
                "random_roll": 0.453723,
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
                "id": "old_jin",
                "location_id": "camp_core",
                "action_type": "SOCIAL_INTERACTION",
                "is_npc": true,
                "primary_attribute": "spirit",
                "target_difficulty": 6,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.9,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "old_jin": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "old_jin_goal",
                      "old_jin_routine"
                    ]
                  }
                },
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "old_jin"
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "old_jin"
                }
              },
              "system_constraints": {
                "tags": [
                  "short_action"
                ],
                "commitments": [
                  [
                    "social_relationship",
                    "old_jin"
                  ]
                ],
                "windows": [
                  {
                    "group": "npc:old_jin",
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
                    "target": "old_jin",
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
            "label": "前往锈蚀车站",
            "description": "",
            "action": {
              "action_id": "auto-travel-rust_station",
              "type": "TRAVEL",
              "target": "rust_station"
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
                "id": "rust_station",
                "location_id": "rust_station",
                "action_type": "EXPLORATION",
                "primary_attribute": "agility",
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
                      "rust_station"
                    ],
                    "resource_changes": {
                      "净水": 3
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  },
                  "partial_failure": {
                    "resource_changes": {
                      "净水": 1
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  }
                },
                "encounter_target_ids": [
                  "rad_scorpion"
                ],
                "requirements": {
                  "location": "rust_station"
                },
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
                  "commitment_axis": "route_commitment",
                  "commitment_value": "rust_station",
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
                  }
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
                    "target": "rust_station",
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
            "label": "建造净水过滤器",
            "description": "",
            "action": {
              "action_id": "auto-build-water_filter",
              "type": "BUILD",
              "target": "water_filter"
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
                  "净水": 1
                },
                "resource_changes": {
                  "净水": -1.0,
                  "废铁": -1.0
                },
                "missing_resources": {},
                "quality_multiplier": 1.0
              },
              "action_ledger": {
                "available_time_minutes": 120.0,
                "actions": [
                  {
                    "type": "BUILD",
                    "target": "water_filter",
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
---
## Turn 2 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0002_001",
    "type": "TRAVEL_COMPLETED",
    "actor": "player",
    "target": "rust_station",
    "data": {
      "action": {
        "action_id": "auto-travel-rust_station",
        "type": "TRAVEL",
        "target": "rust_station"
      },
      "action_ledger": {
        "available_time_minutes": 720.0,
        "available_stamina": 100.0,
        "available_mental": 100.0,
        "actions": [
          {
            "type": "TRAVEL",
            "target": "rust_station",
            "time_minutes": 30.0,
            "stamina_cost": 5.0,
            "mental_cost": 0.0,
            "tags": []
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
      "current_location": "rust_station",
      "current_location_name": "锈蚀车站",
      "current_encounter_id": null,
      "movement": {
        "from": "camp_core",
        "to": "rust_station",
        "mode": "TRAVEL"
      },
      "discover_locations": [
        "rust_station"
      ],
      "proposed_events": [
        {
          "type": "LOCATION_ENTERED",
          "target": "rust_station"
        }
      ],
      "runtime_metrics": {
        "pressure": 0.0,
        "payoff_maturity": 28.5,
        "payoff_impact": 23.5,
        "payoff_score": 33.19675,
        "narrative_debt": [
          {
            "id": "信号塔废墟的共鸣波从何而来？是自然现象还是人为操控？",
            "score": 0.0
          },
          {
            "id": "末日方舟系统的真正目的是什么？为什么选择第七扇区？",
            "score": 0.0
          },
          {
            "id": "共鸣晶体为何在靠近信号塔时会自动发热？",
            "score": 0.0
          },
          {
            "id": "老金似乎知道一些关于系统的事，他为什么不愿说？",
            "score": 0.0
          },
          {
            "id": "排行榜上偶尔出现又消失的玩家'影'是谁？",
            "score": 0.0
          }
        ],
        "progress": 0.165,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 0.0,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "OPTIONS_PRESENTED": 0.0
          }
        },
        "agency": 0.009722,
        "uncertainty": 0.226667,
        "risk_credibility": 0.079333,
        "decision_value": 0.001556,
        "combinability": 95.833333
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.041666666666666664,
          "irreversibility": 0.5,
          "information_uncertainty": 0.16666666666666666,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 0.8333333333333334,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.16666666666666666,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.16666666666666666
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.85,
            "enemy_effectiveness": 0.7,
            "information_incompleteness": 0.16666666666666666,
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
          "setup_depth": 100.0,
          "waiting_time": 5.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 40.0,
          "restriction_removed": 50.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 0.85,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 0.7,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
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
## Turn 2 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0002_public",
    "type": "PUBLIC_SYSTEM_ADVANCED",
    "actor": "system",
    "target": null,
    "data": {
      "projection_state": {
        "population_state": {
          "enabled": true,
          "region_name": "第七扇区·铁锈荒原",
          "region_size": 1000,
          "alive_count": 1000,
          "deaths_total": 0,
          "visible_peers": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            },
            {
              "id": "peer_chen",
              "name": "教授·陈",
              "opening_strategy": "研究信号塔废墟，试图理解共鸣波的规律以获取技术优势",
              "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
            },
            {
              "id": "peer_viper",
              "name": "毒蛇·卡里姆",
              "opening_strategy": "武装列车，拦截其他投放者的物资运输线",
              "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
            }
          ],
          "turn_history": [
            {
              "turn": 2,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            }
          ]
        },
        "public_system_state": {
          "enabled": true,
          "system_name": "末日方舟系统",
          "opening_announcement": "【末日方舟系统公告】第七扇区已激活。1,000名投放者已就位。\n你们拥有一列初始列车和七天缓冲期。第七天日落时，第一轮辐射风暴降临。\n存活者进入下一阶段。系统将持续记录你们的生存数据。祝你们好运。",
          "opening_rules": [
            "每7天一次辐射风暴，不在列车内或庇护所中的人将受到致命伤害",
            "排行榜每小时更新，综合评分=存活天数×资源储备×探索深度",
            "区域频道公开可用，但发言会暴露你的位置和策略",
            "掠夺者NPC每3天巡逻一次，独行且无武装者优先被袭击",
            "信号塔废墟有稀有物资，但共鸣波会造成精神损伤",
            "系统不干预PVP，但击杀投放者会被标记并降低交易信誉"
          ],
          "channel_feed": [
            {
              "sender": "铁拳·马库斯",
              "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
              "turn": 1
            },
            {
              "sender": "幽灵·蕾娜",
              "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
              "turn": 1
            },
            {
              "sender": "教授·陈",
              "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
              "turn": 1
            },
            {
              "sender": "新人0742",
              "message": "天啊这是真的吗？我连水都不够喝三天……",
              "turn": 1
            }
          ],
          "system_announcements": [],
          "regional_chat_enabled": true,
          "announcements_enabled": true
        },
        "market_state": {
          "market_enabled": true,
          "available_vendors": [],
          "market_prices": {},
          "player_inventory_listings": [],
          "recent_transactions": [],
          "market_trends": {}
        },
        "ranking_state": {
          "rankings_enabled": true,
          "player_rank_global": null,
          "player_rank_regional": 201,
          "leaderboards": {
            "regional": [
              {
                "rank": 1,
                "player_id": "peer_marcus",
                "name": "铁拳·马库斯",
                "status": "alive",
                "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
              },
              {
                "rank": 2,
                "player_id": "peer_lena",
                "name": "幽灵·蕾娜",
                "status": "alive",
                "visible_edge": "拥有隐身模块原型，探索时不易被发现"
              },
              {
                "rank": 3,
                "player_id": "peer_chen",
                "name": "教授·陈",
                "status": "alive",
                "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
              },
              {
                "rank": 4,
                "player_id": "peer_viper",
                "name": "毒蛇·卡里姆",
                "status": "alive",
                "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
              },
              {
                "rank": 201,
                "player_id": "player",
                "name": "你",
                "status": "alive"
              }
            ]
          },
          "rank_season_current": 1,
          "rank_season_end_turn": 100,
          "prestige_points": 0
        },
        "comparative_state": {
          "player_comparison_baseline": {
            "percentile": 80,
            "summary": "本回合表现已计入区域排名"
          },
          "performance_metrics_history": [
            {
              "turn": 2,
              "action_score": 15,
              "cumulative_score": 15,
              "percentile": 80,
              "regional_rank": 201
            }
          ],
          "best_performance_by_category": {},
          "comparison_partners": [
            "peer_marcus",
            "peer_lena",
            "peer_chen",
            "peer_viper"
          ],
          "comparison_last_updated": 2
        },
        "rival_state": {
          "active_rivals": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            }
          ],
          "rival_relationships": {
            "peer_marcus": "unknown",
            "peer_lena": "unknown"
          },
          "rival_competitions_active": [],
          "rival_score_current": 15,
          "rival_score_target": 0,
          "rivalry_win_rate": 0.0,
          "last_rival_encounter": {
            "turn": 2,
            "rival_id": "peer_marcus",
            "relative_percentile": 80
          }
        }
      },
      "public_feedback": {
        "regional_statistics": {
          "region_name": "第七扇区·铁锈荒原",
          "alive_count": 1000,
          "deaths_this_turn": 0
        },
        "peer_comparison": {
          "turn": 2,
          "action_score": 15,
          "cumulative_score": 15,
          "percentile": 80,
          "regional_rank": 201
        },
        "ranking_changes": [
          {
            "player": "你",
            "regional_rank": 201,
            "percentile": 80
          }
        ],
        "channel_feed": [
          {
            "sender": "铁拳·马库斯",
            "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
            "turn": 1
          },
          {
            "sender": "幽灵·蕾娜",
            "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
            "turn": 1
          },
          {
            "sender": "教授·陈",
            "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
            "turn": 1
          },
          {
            "sender": "新人0742",
            "message": "天啊这是真的吗？我连水都不够喝三天……",
            "turn": 1
          }
        ],
        "system_announcements": []
      }
    },
    "turn": 2,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 2 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0002_options_b703ab16",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 2,
        "options": {
          "A": {
            "id": "A",
            "label": "等待至白天并rust_station",
            "description": "",
            "action": {
              "action_id": "auto-wait-rust_station",
              "type": "ACTION_PLAN",
              "plan_id": "auto-wait-rust_station",
              "accept_dilution": true,
              "steps": [
                {
                  "action_id": "wait-step",
                  "type": "WAIT",
                  "parameters": {
                    "wait_minutes": 90
                  },
                  "goal": "等待进入白天"
                },
                {
                  "action_id": "action-step",
                  "type": "EXPLORATION",
                  "target": "rust_station",
                  "goal": "rust_station"
                }
              ]
            },
            "preview": {
              "legal": true,
              "errors": [],
              "plan_id": "auto-wait-rust_station",
              "combinability": 50.0,
              "components": {
                "time_compatibility": 1.0,
                "buffer_ratio": 0.6956521739130435,
                "resource_compatibility": 1.0,
                "location_proximity": 1.0,
                "goal_compatibility": 1.0,
                "npc_availability": 1.0,
                "attention_compatibility": 1.0,
                "action_slot_compatibility": 0.5,
                "commitment_compatibility": 1.0,
                "opportunity_window_compatibility": 1.0,
                "movement_compatibility": 1.0
              },
              "dilution_multiplier": 0.75,
              "partial": false,
              "deferred_steps": [],
              "action_ledger": {
                "available_time_minutes": 690.0,
                "available_stamina": 95.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "WAIT",
                    "target": null,
                    "time_minutes": 90.0,
                    "stamina_cost": 0.0,
                    "mental_cost": 0.0,
                    "tags": []
                  },
                  {
                    "type": "EXPLORATION",
                    "target": "rust_station",
                    "time_minutes": 120.0,
                    "stamina_cost": 15.0,
                    "mental_cost": 10.0,
                    "tags": [
                      "major_action",
                      "requires_full_attention"
                    ]
                  }
                ]
              },
              "steps": [
                {
                  "action": {
                    "action_id": "wait-step",
                    "type": "WAIT",
                    "parameters": {
                      "wait_minutes": 90
                    },
                    "goal": "等待进入白天"
                  },
                  "preview": {
                    "legal": true,
                    "errors": [],
                    "resolution": {
                      "formula_version": "1.0",
                      "action_type": "WAIT",
                      "outcome": "普通成功",
                      "probability": 1.0,
                      "risk_mode": "deterministic_wait",
                      "time_cost": 90.0,
                      "wait_minutes": 90.0
                    },
                    "target_profile": {},
                    "system_constraints": {
                      "tags": [],
                      "commitments": [],
                      "windows": [],
                      "allowed_periods": [],
                      "npc_unavailable": false
                    },
                    "action_ledger": {
                      "available_time_minutes": 690.0,
                      "available_stamina": 95.0,
                      "available_mental": 100.0,
                      "actions": [
                        {
                          "type": "WAIT",
                          "target": null,
                          "time_minutes": 90.0,
                          "stamina_cost": 0.0,
                          "mental_cost": 0.0,
                          "tags": []
                        }
                      ]
                    },
                    "skill": null
                  },
                  "source_action_id": "wait-step",
                  "start_period": "清晨",
                  "start_location": "rust_station",
                  "auto_generated": false
                },
                {
                  "action": {
                    "action_id": "action-step",
                    "type": "EXPLORATION",
                    "target": "rust_station",
                    "goal": "rust_station"
                  },
                  "preview": {
                    "legal": true,
                    "errors": [],
                    "resolution": {
                      "formula_version": "1.0",
                      "action_id": "action-step",
                      "advantage_components": {
                        "ability_match": 7.5,
                        "equipment_advantage": 0.0,
                        "preparation": 2.25,
                        "intelligence": 0.0,
                        "teammate_assistance": 0.0,
                        "environment_advantage": 0.0
                      },
                      "resistance_components": {
                        "target_difficulty": 14.0,
                        "environment_penalty": 3.0,
                        "injury": 0.0,
                        "fatigue": 1.0,
                        "time_pressure": 0.0,
                        "unknown_risk": 3.0
                      },
                      "advantage": 9.75,
                      "resistance": 21.0,
                      "K": 10.0,
                      "probability": 0.245085,
                      "random_roll": 0.967154,
                      "severity": 0.0,
                      "severity_band": "成功区",
                      "death_fairness": 0.3808,
                      "outcome": "战败",
                      "death_allowed": false,
                      "components": {
                        "severity": {
                          "difficulty": 2.8,
                          "injury": 0.0,
                          "resource_shortage": 0.0,
                          "information_missing": 2.0,
                          "time_pressure": 0.0,
                          "continuous_errors": 0.0,
                          "preparation": 3.0,
                          "ability_match": 10.0,
                          "teammate_support": 0.0,
                          "survival_assets": 0.0
                        },
                        "death_fairness_inputs": {
                          "risk_warning": 0.7,
                          "causal_chain": 0.85,
                          "avoidable": 0.8,
                          "rule_consistency": 1.0,
                          "player_responsibility": 0.8
                        },
                        "outcome_thresholds": {
                          "critical": 0.024509,
                          "normal": 0.159305,
                          "costly": 0.245085,
                          "partial_failure": 0.433814,
                          "severe_failure": 0.924509
                        },
                        "dilution_multiplier": 0.75
                      }
                    },
                    "target_profile": {
                      "id": "rust_station",
                      "location_id": "rust_station",
                      "action_type": "EXPLORATION",
                      "primary_attribute": "agility",
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
                            "rust_station"
                          ],
                          "resource_changes": {
                            "净水": 3
                          },
                          "knowledge_additions": [
                            "rad_scorpion_behavior"
                          ]
                        },
                        "partial_failure": {
                          "resource_changes": {
                            "净水": 1
                          },
                          "knowledge_additions": [
                            "rad_scorpion_behavior"
                          ]
                        }
                      },
                      "encounter_target_ids": [
                        "rad_scorpion"
                      ],
                      "requirements": {
                        "location": "rust_station"
                      },
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
                        "commitment_axis": "route_commitment",
                        "commitment_value": "rust_station",
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
                        }
                      }
                    },
                    "system_constraints": {
                      "tags": [
                        "major_action",
                        "requires_full_attention"
                      ],
                      "commitments": [
                        [
                          "route_commitment",
                          "rust_station"
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
                    "action_ledger": {
                      "available_time_minutes": 600.0,
                      "available_stamina": 95.0,
                      "available_mental": 100.0,
                      "actions": [
                        {
                          "type": "EXPLORATION",
                          "target": "rust_station",
                          "time_minutes": 120.0,
                          "stamina_cost": 15.0,
                          "mental_cost": 10.0,
                          "tags": [
                            "major_action",
                            "requires_full_attention"
                          ]
                        }
                      ]
                    },
                    "skill": null
                  },
                  "source_action_id": "action-step",
                  "start_period": "白天",
                  "start_location": "rust_station",
                  "auto_generated": false
                }
              ]
            },
            "state_turn": 2
          },
          "B": {
            "id": "B",
            "label": "返回基地",
            "description": "",
            "action": {
              "action_id": "auto-return",
              "type": "RETURN_TO_BASE"
            },
            "preview": {
              "legal": true,
              "errors": [],
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
              "target_profile": {},
              "system_constraints": {
                "tags": [],
                "commitments": [],
                "windows": [],
                "allowed_periods": [],
                "npc_unavailable": false
              },
              "action_ledger": {
                "available_time_minutes": 690.0,
                "available_stamina": 95.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "RETURN_TO_BASE",
                    "target": null,
                    "time_minutes": 30.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 2
          },
          "C": {
            "id": "C",
            "label": "前往信号塔废墟",
            "description": "",
            "action": {
              "action_id": "auto-travel-signal_tower_ruins",
              "type": "TRAVEL",
              "target": "signal_tower_ruins"
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
                "time_cost": 45.0,
                "stamina_cost": 8.0,
                "mental_cost": 0.0
              },
              "target_profile": {
                "id": "signal_tower_ruins",
                "location_id": "signal_tower_ruins",
                "action_type": "RESEARCH",
                "primary_attribute": "spirit",
                "target_difficulty": 20,
                "environment_penalty": 5,
                "unknown_risk": 10,
                "risk_warning": 0.8,
                "causal_chain": 0.85,
                "avoidable": 0.7,
                "rule_consistency": 1.0,
                "player_responsibility": 0.8,
                "effects": {
                  "success": {
                    "knowledge_additions": [
                      "signal_tower_ruins_principle"
                    ],
                    "resource_changes": {
                      "燃料棒": 2
                    }
                  }
                },
                "requirements": {
                  "location": "signal_tower_ruins"
                },
                "constraints": {
                  "system_tags": [
                    "major_action",
                    "requires_full_attention"
                  ],
                  "exclusive_group": "research_window",
                  "window_ids": [
                    "白天",
                    "黄昏"
                  ],
                  "window_capacity": 1,
                  "commitment_axis": "research_focus",
                  "commitment_value": "signal_tower_ruins"
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
                "available_time_minutes": 690.0,
                "available_stamina": 95.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "TRAVEL",
                    "target": "signal_tower_ruins",
                    "time_minutes": 45.0,
                    "stamina_cost": 8.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 2
          }
        }
      },
      "state_turn": 2
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
    "type": "TRAVEL_COMPLETED",
    "actor": "player",
    "target": "signal_tower_ruins",
    "data": {
      "action": {
        "action_id": "auto-travel-signal_tower_ruins",
        "type": "TRAVEL",
        "target": "signal_tower_ruins"
      },
      "action_ledger": {
        "available_time_minutes": 690.0,
        "available_stamina": 95.0,
        "available_mental": 100.0,
        "actions": [
          {
            "type": "TRAVEL",
            "target": "signal_tower_ruins",
            "time_minutes": 45.0,
            "stamina_cost": 8.0,
            "mental_cost": 0.0,
            "tags": []
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
        "time_cost": 45.0,
        "stamina_cost": 8.0,
        "mental_cost": 0.0
      },
      "fatigue_delta": 8.0,
      "mental_delta": -0.0,
      "time_cost": 45.0,
      "hunger_delta": 0.0,
      "resource_changes": {},
      "current_location": "signal_tower_ruins",
      "current_location_name": "信号塔废墟",
      "current_encounter_id": null,
      "movement": {
        "from": "rust_station",
        "to": "signal_tower_ruins",
        "mode": "TRAVEL"
      },
      "discover_locations": [
        "signal_tower_ruins"
      ],
      "proposed_events": [
        {
          "type": "LOCATION_ENTERED",
          "target": "signal_tower_ruins"
        }
      ],
      "runtime_metrics": {
        "pressure": 15.625,
        "payoff_maturity": 29.5,
        "payoff_impact": 23.5,
        "payoff_score": 32.94975,
        "narrative_debt": [
          {
            "id": "信号塔废墟的共鸣波从何而来？是自然现象还是人为操控？",
            "score": 0.0
          },
          {
            "id": "末日方舟系统的真正目的是什么？为什么选择第七扇区？",
            "score": 0.0
          },
          {
            "id": "共鸣晶体为何在靠近信号塔时会自动发热？",
            "score": 0.0
          },
          {
            "id": "老金似乎知道一些关于系统的事，他为什么不愿说？",
            "score": 0.0
          },
          {
            "id": "排行榜上偶尔出现又消失的玩家'影'是谁？",
            "score": 0.0
          }
        ],
        "progress": 0.165,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 30.0,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "OPTIONS_PRESENTED": 30.0,
            "TRAVEL_COMPLETED": 0.0,
            "PUBLIC_SYSTEM_ADVANCED": 0.0
          }
        },
        "agency": 0.012174,
        "uncertainty": 0.293333,
        "risk_credibility": 0.181333,
        "decision_value": 0.00487,
        "combinability": 93.478261
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.06521739130434782,
          "irreversibility": 0.5,
          "information_uncertainty": 0.3333333333333333,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 0.6666666666666667,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.3333333333333333,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.3333333333333333
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.85,
            "enemy_effectiveness": 0.8,
            "information_incompleteness": 0.3333333333333333,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9347826086956522,
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
          "setup_depth": 100.0,
          "waiting_time": 10.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 20.0,
          "restriction_removed": 50.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 0.85,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 0.8,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 5.0,
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
## Turn 3 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0003_public",
    "type": "PUBLIC_SYSTEM_ADVANCED",
    "actor": "system",
    "target": null,
    "data": {
      "projection_state": {
        "population_state": {
          "enabled": true,
          "region_name": "第七扇区·铁锈荒原",
          "region_size": 1000,
          "alive_count": 1000,
          "deaths_total": 0,
          "visible_peers": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            },
            {
              "id": "peer_chen",
              "name": "教授·陈",
              "opening_strategy": "研究信号塔废墟，试图理解共鸣波的规律以获取技术优势",
              "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
            },
            {
              "id": "peer_viper",
              "name": "毒蛇·卡里姆",
              "opening_strategy": "武装列车，拦截其他投放者的物资运输线",
              "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
            }
          ],
          "turn_history": [
            {
              "turn": 2,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 3,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            }
          ]
        },
        "public_system_state": {
          "enabled": true,
          "system_name": "末日方舟系统",
          "opening_announcement": "【末日方舟系统公告】第七扇区已激活。1,000名投放者已就位。\n你们拥有一列初始列车和七天缓冲期。第七天日落时，第一轮辐射风暴降临。\n存活者进入下一阶段。系统将持续记录你们的生存数据。祝你们好运。",
          "opening_rules": [
            "每7天一次辐射风暴，不在列车内或庇护所中的人将受到致命伤害",
            "排行榜每小时更新，综合评分=存活天数×资源储备×探索深度",
            "区域频道公开可用，但发言会暴露你的位置和策略",
            "掠夺者NPC每3天巡逻一次，独行且无武装者优先被袭击",
            "信号塔废墟有稀有物资，但共鸣波会造成精神损伤",
            "系统不干预PVP，但击杀投放者会被标记并降低交易信誉"
          ],
          "channel_feed": [
            {
              "sender": "铁拳·马库斯",
              "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
              "turn": 1
            },
            {
              "sender": "幽灵·蕾娜",
              "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
              "turn": 1
            },
            {
              "sender": "教授·陈",
              "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
              "turn": 1
            },
            {
              "sender": "新人0742",
              "message": "天啊这是真的吗？我连水都不够喝三天……",
              "turn": 1
            }
          ],
          "system_announcements": [],
          "regional_chat_enabled": true,
          "announcements_enabled": true
        },
        "market_state": {
          "market_enabled": true,
          "available_vendors": [],
          "market_prices": {},
          "player_inventory_listings": [],
          "recent_transactions": [],
          "market_trends": {}
        },
        "ranking_state": {
          "rankings_enabled": true,
          "player_rank_global": null,
          "player_rank_regional": 11,
          "leaderboards": {
            "regional": [
              {
                "rank": 1,
                "player_id": "peer_marcus",
                "name": "铁拳·马库斯",
                "status": "alive",
                "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
              },
              {
                "rank": 2,
                "player_id": "peer_lena",
                "name": "幽灵·蕾娜",
                "status": "alive",
                "visible_edge": "拥有隐身模块原型，探索时不易被发现"
              },
              {
                "rank": 3,
                "player_id": "peer_chen",
                "name": "教授·陈",
                "status": "alive",
                "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
              },
              {
                "rank": 4,
                "player_id": "peer_viper",
                "name": "毒蛇·卡里姆",
                "status": "alive",
                "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
              },
              {
                "rank": 11,
                "player_id": "player",
                "name": "你",
                "status": "alive"
              }
            ]
          },
          "rank_season_current": 1,
          "rank_season_end_turn": 100,
          "prestige_points": 0
        },
        "comparative_state": {
          "player_comparison_baseline": {
            "percentile": 99,
            "summary": "本回合表现已计入区域排名"
          },
          "performance_metrics_history": [
            {
              "turn": 2,
              "action_score": 15,
              "cumulative_score": 15,
              "percentile": 80,
              "regional_rank": 201
            },
            {
              "turn": 3,
              "action_score": 15,
              "cumulative_score": 30,
              "percentile": 99,
              "regional_rank": 11
            }
          ],
          "best_performance_by_category": {},
          "comparison_partners": [
            "peer_marcus",
            "peer_lena",
            "peer_chen",
            "peer_viper"
          ],
          "comparison_last_updated": 3
        },
        "rival_state": {
          "active_rivals": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            }
          ],
          "rival_relationships": {
            "peer_marcus": "unknown",
            "peer_lena": "unknown"
          },
          "rival_competitions_active": [],
          "rival_score_current": 30,
          "rival_score_target": 0,
          "rivalry_win_rate": 0.0,
          "last_rival_encounter": {
            "turn": 3,
            "rival_id": "peer_marcus",
            "relative_percentile": 99
          }
        }
      },
      "public_feedback": {
        "regional_statistics": {
          "region_name": "第七扇区·铁锈荒原",
          "alive_count": 1000,
          "deaths_this_turn": 0
        },
        "peer_comparison": {
          "turn": 3,
          "action_score": 15,
          "cumulative_score": 30,
          "percentile": 99,
          "regional_rank": 11
        },
        "ranking_changes": [
          {
            "player": "你",
            "regional_rank": 11,
            "percentile": 99
          }
        ],
        "channel_feed": [
          {
            "sender": "铁拳·马库斯",
            "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
            "turn": 1
          },
          {
            "sender": "幽灵·蕾娜",
            "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
            "turn": 1
          },
          {
            "sender": "教授·陈",
            "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
            "turn": 1
          },
          {
            "sender": "新人0742",
            "message": "天啊这是真的吗？我连水都不够喝三天……",
            "turn": 1
          }
        ],
        "system_announcements": []
      }
    },
    "turn": 3,
    "timestamp": "Day 1 清晨"
  }
]
```
---
## Turn 3 | Day 1 清晨
```json
[
  {
    "event_id": "evt_0003_options_eaa1281f",
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
            "label": "signal_tower_ruins",
            "description": "signal_tower_ruins",
            "action": {
              "action_id": "auto-signal_tower_ruins",
              "type": "RESEARCH",
              "target": "signal_tower_ruins",
              "goal": "signal_tower_ruins"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-signal_tower_ruins",
                "advantage_components": {
                  "ability_match": 10.0,
                  "equipment_advantage": 0.0,
                  "preparation": 0.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 20.0,
                  "environment_penalty": 5.0,
                  "injury": 0.0,
                  "fatigue": 2.6,
                  "time_pressure": 0.0,
                  "unknown_risk": 10.0
                },
                "advantage": 10.0,
                "resistance": 37.6,
                "K": 10.0,
                "probability": 0.059524,
                "random_roll": 0.023274,
                "severity": 0.666667,
                "severity_band": "成功区",
                "death_fairness": 0.3808,
                "outcome": "普通成功",
                "death_allowed": false,
                "components": {
                  "severity": {
                    "difficulty": 4.0,
                    "injury": 0.0,
                    "resource_shortage": 0.0,
                    "information_missing": 6.666666666666667,
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 0.0,
                    "ability_match": 10.0,
                    "teammate_support": 0.0,
                    "survival_assets": 0.0
                  },
                  "death_fairness_inputs": {
                    "risk_warning": 0.8,
                    "causal_chain": 0.85,
                    "avoidable": 0.7,
                    "rule_consistency": 1.0,
                    "player_responsibility": 0.8
                  },
                  "outcome_thresholds": {
                    "critical": 0.004762,
                    "normal": 0.046429,
                    "costly": 0.059524,
                    "partial_failure": 0.62381,
                    "severe_failure": 0.952976
                  }
                }
              },
              "target_profile": {
                "id": "signal_tower_ruins",
                "location_id": "signal_tower_ruins",
                "action_type": "RESEARCH",
                "primary_attribute": "spirit",
                "target_difficulty": 20,
                "environment_penalty": 5,
                "unknown_risk": 10,
                "risk_warning": 0.8,
                "causal_chain": 0.85,
                "avoidable": 0.7,
                "rule_consistency": 1.0,
                "player_responsibility": 0.8,
                "effects": {
                  "success": {
                    "knowledge_additions": [
                      "signal_tower_ruins_principle"
                    ],
                    "resource_changes": {
                      "燃料棒": 2
                    }
                  }
                },
                "requirements": {
                  "location": "signal_tower_ruins"
                },
                "constraints": {
                  "system_tags": [
                    "major_action",
                    "requires_full_attention"
                  ],
                  "exclusive_group": "research_window",
                  "window_ids": [
                    "白天",
                    "黄昏"
                  ],
                  "window_capacity": 1,
                  "commitment_axis": "research_focus",
                  "commitment_value": "signal_tower_ruins"
                }
              },
              "system_constraints": {
                "tags": [
                  "major_action",
                  "requires_full_attention"
                ],
                "commitments": [
                  [
                    "research_focus",
                    "signal_tower_ruins"
                  ]
                ],
                "windows": [
                  {
                    "group": "research_window",
                    "ids": [
                      "白天",
                      "黄昏"
                    ],
                    "capacity": 1
                  }
                ],
                "allowed_periods": [],
                "npc_unavailable": false
              },
              "action_ledger": {
                "available_time_minutes": 645.0,
                "available_stamina": 87.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "RESEARCH",
                    "target": "signal_tower_ruins",
                    "time_minutes": 120.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 20.0,
                    "tags": [
                      "major_action",
                      "requires_full_attention"
                    ]
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 3
          },
          "B": {
            "id": "B",
            "label": "返回基地",
            "description": "",
            "action": {
              "action_id": "auto-return",
              "type": "RETURN_TO_BASE"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_type": "RETURN_TO_BASE",
                "outcome": "普通成功",
                "movement_success": true,
                "probability": 1.0,
                "risk_mode": "deterministic_route",
                "time_cost": 45.0,
                "stamina_cost": 8.0,
                "mental_cost": 0.0
              },
              "target_profile": {},
              "system_constraints": {
                "tags": [],
                "commitments": [],
                "windows": [],
                "allowed_periods": [],
                "npc_unavailable": false
              },
              "action_ledger": {
                "available_time_minutes": 645.0,
                "available_stamina": 87.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "RETURN_TO_BASE",
                    "target": null,
                    "time_minutes": 45.0,
                    "stamina_cost": 8.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 3
          },
          "C": {
            "id": "C",
            "label": "前往锈蚀车站",
            "description": "",
            "action": {
              "action_id": "auto-travel-rust_station",
              "type": "TRAVEL",
              "target": "rust_station"
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
                "id": "rust_station",
                "location_id": "rust_station",
                "action_type": "EXPLORATION",
                "primary_attribute": "agility",
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
                      "rust_station"
                    ],
                    "resource_changes": {
                      "净水": 3
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  },
                  "partial_failure": {
                    "resource_changes": {
                      "净水": 1
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  }
                },
                "encounter_target_ids": [
                  "rad_scorpion"
                ],
                "requirements": {
                  "location": "rust_station"
                },
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
                  "commitment_axis": "route_commitment",
                  "commitment_value": "rust_station",
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
                  }
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
                "available_time_minutes": 645.0,
                "available_stamina": 87.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "TRAVEL",
                    "target": "rust_station",
                    "time_minutes": 30.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 0.0,
                    "tags": []
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
    "type": "TRAVEL_COMPLETED",
    "actor": "player",
    "target": "rust_station",
    "data": {
      "action": {
        "action_id": "auto-travel-rust_station",
        "type": "TRAVEL",
        "target": "rust_station"
      },
      "action_ledger": {
        "available_time_minutes": 645.0,
        "available_stamina": 87.0,
        "available_mental": 100.0,
        "actions": [
          {
            "type": "TRAVEL",
            "target": "rust_station",
            "time_minutes": 30.0,
            "stamina_cost": 5.0,
            "mental_cost": 0.0,
            "tags": []
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
      "current_location": "rust_station",
      "current_location_name": "锈蚀车站",
      "current_encounter_id": null,
      "movement": {
        "from": "signal_tower_ruins",
        "to": "rust_station",
        "mode": "TRAVEL"
      },
      "discover_locations": [
        "rust_station"
      ],
      "proposed_events": [
        {
          "type": "LOCATION_ENTERED",
          "target": "rust_station"
        }
      ],
      "runtime_metrics": {
        "pressure": 16.5625,
        "payoff_maturity": 30.5,
        "payoff_impact": 23.5,
        "payoff_score": 32.39675,
        "narrative_debt": [
          {
            "id": "信号塔废墟的共鸣波从何而来？是自然现象还是人为操控？",
            "score": 0.0
          },
          {
            "id": "末日方舟系统的真正目的是什么？为什么选择第七扇区？",
            "score": 0.0
          },
          {
            "id": "共鸣晶体为何在靠近信号塔时会自动发热？",
            "score": 0.0
          },
          {
            "id": "老金似乎知道一些关于系统的事，他为什么不愿说？",
            "score": 0.0
          },
          {
            "id": "排行榜上偶尔出现又消失的玩家'影'是谁？",
            "score": 0.0
          }
        ],
        "progress": 0.165,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 22.5,
          "by_type": {
            "WORLD_CREATED": 0.0,
            "OPTIONS_PRESENTED": 22.5,
            "TRAVEL_COMPLETED": 15.0,
            "PUBLIC_SYSTEM_ADVANCED": 15.0
          }
        },
        "agency": 0.010853,
        "uncertainty": 0.226667,
        "risk_credibility": 0.079333,
        "decision_value": 0.001736,
        "combinability": 95.348837
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.046511627906976744,
          "irreversibility": 0.5,
          "information_uncertainty": 0.16666666666666666,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 0.8333333333333334,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.16666666666666666,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.16666666666666666
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.85,
            "enemy_effectiveness": 0.7,
            "information_incompleteness": 0.16666666666666666,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9534883720930233,
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
          "setup_depth": 100.0,
          "waiting_time": 15.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 40.0,
          "restriction_removed": 50.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 0.85,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 0.7,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 13.0,
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
    "event_id": "evt_0004_public",
    "type": "PUBLIC_SYSTEM_ADVANCED",
    "actor": "system",
    "target": null,
    "data": {
      "projection_state": {
        "population_state": {
          "enabled": true,
          "region_name": "第七扇区·铁锈荒原",
          "region_size": 1000,
          "alive_count": 1000,
          "deaths_total": 0,
          "visible_peers": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            },
            {
              "id": "peer_chen",
              "name": "教授·陈",
              "opening_strategy": "研究信号塔废墟，试图理解共鸣波的规律以获取技术优势",
              "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
            },
            {
              "id": "peer_viper",
              "name": "毒蛇·卡里姆",
              "opening_strategy": "武装列车，拦截其他投放者的物资运输线",
              "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
            }
          ],
          "turn_history": [
            {
              "turn": 2,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 3,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 4,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            }
          ]
        },
        "public_system_state": {
          "enabled": true,
          "system_name": "末日方舟系统",
          "opening_announcement": "【末日方舟系统公告】第七扇区已激活。1,000名投放者已就位。\n你们拥有一列初始列车和七天缓冲期。第七天日落时，第一轮辐射风暴降临。\n存活者进入下一阶段。系统将持续记录你们的生存数据。祝你们好运。",
          "opening_rules": [
            "每7天一次辐射风暴，不在列车内或庇护所中的人将受到致命伤害",
            "排行榜每小时更新，综合评分=存活天数×资源储备×探索深度",
            "区域频道公开可用，但发言会暴露你的位置和策略",
            "掠夺者NPC每3天巡逻一次，独行且无武装者优先被袭击",
            "信号塔废墟有稀有物资，但共鸣波会造成精神损伤",
            "系统不干预PVP，但击杀投放者会被标记并降低交易信誉"
          ],
          "channel_feed": [
            {
              "sender": "铁拳·马库斯",
              "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
              "turn": 1
            },
            {
              "sender": "幽灵·蕾娜",
              "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
              "turn": 1
            },
            {
              "sender": "教授·陈",
              "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
              "turn": 1
            },
            {
              "sender": "新人0742",
              "message": "天啊这是真的吗？我连水都不够喝三天……",
              "turn": 1
            }
          ],
          "system_announcements": [],
          "regional_chat_enabled": true,
          "announcements_enabled": true
        },
        "market_state": {
          "market_enabled": true,
          "available_vendors": [],
          "market_prices": {},
          "player_inventory_listings": [],
          "recent_transactions": [],
          "market_trends": {}
        },
        "ranking_state": {
          "rankings_enabled": true,
          "player_rank_global": null,
          "player_rank_regional": 11,
          "leaderboards": {
            "regional": [
              {
                "rank": 1,
                "player_id": "peer_marcus",
                "name": "铁拳·马库斯",
                "status": "alive",
                "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
              },
              {
                "rank": 2,
                "player_id": "peer_lena",
                "name": "幽灵·蕾娜",
                "status": "alive",
                "visible_edge": "拥有隐身模块原型，探索时不易被发现"
              },
              {
                "rank": 3,
                "player_id": "peer_chen",
                "name": "教授·陈",
                "status": "alive",
                "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
              },
              {
                "rank": 4,
                "player_id": "peer_viper",
                "name": "毒蛇·卡里姆",
                "status": "alive",
                "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
              },
              {
                "rank": 11,
                "player_id": "player",
                "name": "你",
                "status": "alive"
              }
            ]
          },
          "rank_season_current": 1,
          "rank_season_end_turn": 100,
          "prestige_points": 0
        },
        "comparative_state": {
          "player_comparison_baseline": {
            "percentile": 99,
            "summary": "本回合表现已计入区域排名"
          },
          "performance_metrics_history": [
            {
              "turn": 2,
              "action_score": 15,
              "cumulative_score": 15,
              "percentile": 80,
              "regional_rank": 201
            },
            {
              "turn": 3,
              "action_score": 15,
              "cumulative_score": 30,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 4,
              "action_score": 15,
              "cumulative_score": 45,
              "percentile": 99,
              "regional_rank": 11
            }
          ],
          "best_performance_by_category": {},
          "comparison_partners": [
            "peer_marcus",
            "peer_lena",
            "peer_chen",
            "peer_viper"
          ],
          "comparison_last_updated": 4
        },
        "rival_state": {
          "active_rivals": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            }
          ],
          "rival_relationships": {
            "peer_marcus": "unknown",
            "peer_lena": "unknown"
          },
          "rival_competitions_active": [],
          "rival_score_current": 45,
          "rival_score_target": 0,
          "rivalry_win_rate": 0.0,
          "last_rival_encounter": {
            "turn": 4,
            "rival_id": "peer_marcus",
            "relative_percentile": 99
          }
        }
      },
      "public_feedback": {
        "regional_statistics": {
          "region_name": "第七扇区·铁锈荒原",
          "alive_count": 1000,
          "deaths_this_turn": 0
        },
        "peer_comparison": {
          "turn": 4,
          "action_score": 15,
          "cumulative_score": 45,
          "percentile": 99,
          "regional_rank": 11
        },
        "ranking_changes": [
          {
            "player": "你",
            "regional_rank": 11,
            "percentile": 99
          }
        ],
        "channel_feed": [
          {
            "sender": "铁拳·马库斯",
            "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
            "turn": 1
          },
          {
            "sender": "幽灵·蕾娜",
            "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
            "turn": 1
          },
          {
            "sender": "教授·陈",
            "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
            "turn": 1
          },
          {
            "sender": "新人0742",
            "message": "天啊这是真的吗？我连水都不够喝三天……",
            "turn": 1
          }
        ],
        "system_announcements": []
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
    "event_id": "evt_0004_options_7de9d9a4",
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
            "label": "等待至白天并rust_station",
            "description": "",
            "action": {
              "action_id": "auto-wait-rust_station",
              "type": "ACTION_PLAN",
              "plan_id": "auto-wait-rust_station",
              "accept_dilution": true,
              "steps": [
                {
                  "action_id": "wait-step",
                  "type": "WAIT",
                  "parameters": {
                    "wait_minutes": 15
                  },
                  "goal": "等待进入白天"
                },
                {
                  "action_id": "action-step",
                  "type": "EXPLORATION",
                  "target": "rust_station",
                  "goal": "rust_station"
                }
              ]
            },
            "preview": {
              "legal": true,
              "errors": [],
              "plan_id": "auto-wait-rust_station",
              "combinability": 100.0,
              "components": {
                "time_compatibility": 1.0,
                "buffer_ratio": 0.7804878048780488,
                "resource_compatibility": 1.0,
                "location_proximity": 1.0,
                "goal_compatibility": 1.0,
                "npc_availability": 1.0,
                "attention_compatibility": 1.0,
                "action_slot_compatibility": 1.0,
                "commitment_compatibility": 1.0,
                "opportunity_window_compatibility": 1.0,
                "movement_compatibility": 1.0
              },
              "dilution_multiplier": 1.0,
              "partial": false,
              "deferred_steps": [],
              "action_ledger": {
                "available_time_minutes": 615.0,
                "available_stamina": 82.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "WAIT",
                    "target": null,
                    "time_minutes": 15.0,
                    "stamina_cost": 0.0,
                    "mental_cost": 0.0,
                    "tags": []
                  },
                  {
                    "type": "EXPLORATION",
                    "target": "rust_station",
                    "time_minutes": 120.0,
                    "stamina_cost": 15.0,
                    "mental_cost": 10.0,
                    "tags": [
                      "major_action",
                      "requires_full_attention"
                    ]
                  }
                ]
              },
              "steps": [
                {
                  "action": {
                    "action_id": "wait-step",
                    "type": "WAIT",
                    "parameters": {
                      "wait_minutes": 15
                    },
                    "goal": "等待进入白天"
                  },
                  "preview": {
                    "legal": true,
                    "errors": [],
                    "resolution": {
                      "formula_version": "1.0",
                      "action_type": "WAIT",
                      "outcome": "普通成功",
                      "probability": 1.0,
                      "risk_mode": "deterministic_wait",
                      "time_cost": 15.0,
                      "wait_minutes": 15.0
                    },
                    "target_profile": {},
                    "system_constraints": {
                      "tags": [],
                      "commitments": [],
                      "windows": [],
                      "allowed_periods": [],
                      "npc_unavailable": false
                    },
                    "action_ledger": {
                      "available_time_minutes": 615.0,
                      "available_stamina": 82.0,
                      "available_mental": 100.0,
                      "actions": [
                        {
                          "type": "WAIT",
                          "target": null,
                          "time_minutes": 15.0,
                          "stamina_cost": 0.0,
                          "mental_cost": 0.0,
                          "tags": []
                        }
                      ]
                    },
                    "skill": null
                  },
                  "source_action_id": "wait-step",
                  "start_period": "清晨",
                  "start_location": "rust_station",
                  "auto_generated": false
                },
                {
                  "action": {
                    "action_id": "action-step",
                    "type": "EXPLORATION",
                    "target": "rust_station",
                    "goal": "rust_station"
                  },
                  "preview": {
                    "legal": true,
                    "errors": [],
                    "resolution": {
                      "formula_version": "1.0",
                      "action_id": "action-step",
                      "advantage_components": {
                        "ability_match": 10.0,
                        "equipment_advantage": 0.0,
                        "preparation": 3.0,
                        "intelligence": 0.0,
                        "teammate_assistance": 0.0,
                        "environment_advantage": 0.0
                      },
                      "resistance_components": {
                        "target_difficulty": 14.0,
                        "environment_penalty": 3.0,
                        "injury": 0.0,
                        "fatigue": 3.6,
                        "time_pressure": 0.0,
                        "unknown_risk": 3.0
                      },
                      "advantage": 13.0,
                      "resistance": 23.6,
                      "K": 10.0,
                      "probability": 0.257309,
                      "random_roll": 0.159562,
                      "severity": 0.0,
                      "severity_band": "成功区",
                      "death_fairness": 0.3808,
                      "outcome": "普通成功",
                      "death_allowed": false,
                      "components": {
                        "severity": {
                          "difficulty": 2.8,
                          "injury": 0.0,
                          "resource_shortage": 0.0,
                          "information_missing": 2.0,
                          "time_pressure": 0.0,
                          "continuous_errors": 0.0,
                          "preparation": 3.0,
                          "ability_match": 10.0,
                          "teammate_support": 0.0,
                          "survival_assets": 0.0
                        },
                        "death_fairness_inputs": {
                          "risk_warning": 0.7,
                          "causal_chain": 0.85,
                          "avoidable": 0.8,
                          "rule_consistency": 1.0,
                          "player_responsibility": 0.8
                        },
                        "outcome_thresholds": {
                          "critical": 0.020585,
                          "normal": 0.200701,
                          "costly": 0.257309,
                          "partial_failure": 0.702924,
                          "severe_failure": 0.962865
                        }
                      }
                    },
                    "target_profile": {
                      "id": "rust_station",
                      "location_id": "rust_station",
                      "action_type": "EXPLORATION",
                      "primary_attribute": "agility",
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
                            "rust_station"
                          ],
                          "resource_changes": {
                            "净水": 3
                          },
                          "knowledge_additions": [
                            "rad_scorpion_behavior"
                          ]
                        },
                        "partial_failure": {
                          "resource_changes": {
                            "净水": 1
                          },
                          "knowledge_additions": [
                            "rad_scorpion_behavior"
                          ]
                        }
                      },
                      "encounter_target_ids": [
                        "rad_scorpion"
                      ],
                      "requirements": {
                        "location": "rust_station"
                      },
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
                        "commitment_axis": "route_commitment",
                        "commitment_value": "rust_station",
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
                        }
                      }
                    },
                    "system_constraints": {
                      "tags": [
                        "major_action",
                        "requires_full_attention"
                      ],
                      "commitments": [
                        [
                          "route_commitment",
                          "rust_station"
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
                    "action_ledger": {
                      "available_time_minutes": 600.0,
                      "available_stamina": 82.0,
                      "available_mental": 100.0,
                      "actions": [
                        {
                          "type": "EXPLORATION",
                          "target": "rust_station",
                          "time_minutes": 120.0,
                          "stamina_cost": 15.0,
                          "mental_cost": 10.0,
                          "tags": [
                            "major_action",
                            "requires_full_attention"
                          ]
                        }
                      ]
                    },
                    "skill": null
                  },
                  "source_action_id": "action-step",
                  "start_period": "白天",
                  "start_location": "rust_station",
                  "auto_generated": false
                }
              ]
            },
            "state_turn": 4
          },
          "B": {
            "id": "B",
            "label": "返回基地",
            "description": "",
            "action": {
              "action_id": "auto-return",
              "type": "RETURN_TO_BASE"
            },
            "preview": {
              "legal": true,
              "errors": [],
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
              "target_profile": {},
              "system_constraints": {
                "tags": [],
                "commitments": [],
                "windows": [],
                "allowed_periods": [],
                "npc_unavailable": false
              },
              "action_ledger": {
                "available_time_minutes": 615.0,
                "available_stamina": 82.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "RETURN_TO_BASE",
                    "target": null,
                    "time_minutes": 30.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 4
          },
          "C": {
            "id": "C",
            "label": "前往信号塔废墟",
            "description": "",
            "action": {
              "action_id": "auto-travel-signal_tower_ruins",
              "type": "TRAVEL",
              "target": "signal_tower_ruins"
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
                "time_cost": 45.0,
                "stamina_cost": 8.0,
                "mental_cost": 0.0
              },
              "target_profile": {
                "id": "signal_tower_ruins",
                "location_id": "signal_tower_ruins",
                "action_type": "RESEARCH",
                "primary_attribute": "spirit",
                "target_difficulty": 20,
                "environment_penalty": 5,
                "unknown_risk": 10,
                "risk_warning": 0.8,
                "causal_chain": 0.85,
                "avoidable": 0.7,
                "rule_consistency": 1.0,
                "player_responsibility": 0.8,
                "effects": {
                  "success": {
                    "knowledge_additions": [
                      "signal_tower_ruins_principle"
                    ],
                    "resource_changes": {
                      "燃料棒": 2
                    }
                  }
                },
                "requirements": {
                  "location": "signal_tower_ruins"
                },
                "constraints": {
                  "system_tags": [
                    "major_action",
                    "requires_full_attention"
                  ],
                  "exclusive_group": "research_window",
                  "window_ids": [
                    "白天",
                    "黄昏"
                  ],
                  "window_capacity": 1,
                  "commitment_axis": "research_focus",
                  "commitment_value": "signal_tower_ruins"
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
                "available_time_minutes": 615.0,
                "available_stamina": 82.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "TRAVEL",
                    "target": "signal_tower_ruins",
                    "time_minutes": 45.0,
                    "stamina_cost": 8.0,
                    "mental_cost": 0.0,
                    "tags": []
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
    "type": "RETURN_TO_BASE_COMPLETED",
    "actor": "player",
    "target": null,
    "data": {
      "action": {
        "action_id": "auto-return",
        "type": "RETURN_TO_BASE"
      },
      "action_ledger": {
        "available_time_minutes": 615.0,
        "available_stamina": 82.0,
        "available_mental": 100.0,
        "actions": [
          {
            "type": "RETURN_TO_BASE",
            "target": null,
            "time_minutes": 30.0,
            "stamina_cost": 5.0,
            "mental_cost": 0.0,
            "tags": []
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
      "current_location_name": "废土列车·铁蛇号",
      "current_encounter_id": null,
      "movement": {
        "from": "rust_station",
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
        "pressure": 17.1875,
        "payoff_maturity": 31.5,
        "payoff_impact": 10.0,
        "payoff_score": 23.63125,
        "narrative_debt": [
          {
            "id": "信号塔废墟的共鸣波从何而来？是自然现象还是人为操控？",
            "score": 0.0
          },
          {
            "id": "末日方舟系统的真正目的是什么？为什么选择第七扇区？",
            "score": 0.0
          },
          {
            "id": "共鸣晶体为何在靠近信号塔时会自动发热？",
            "score": 0.0
          },
          {
            "id": "老金似乎知道一些关于系统的事，他为什么不愿说？",
            "score": 0.0
          },
          {
            "id": "排行榜上偶尔出现又消失的玩家'影'是谁？",
            "score": 0.0
          }
        ],
        "progress": 0.03,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 20.0,
          "by_type": {
            "OPTIONS_PRESENTED": 20.0,
            "TRAVEL_COMPLETED": 15.0,
            "PUBLIC_SYSTEM_ADVANCED": 15.0
          }
        },
        "agency": 0.006829,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 95.121951
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.4,
          "opportunity_cost": 0.04878048780487805,
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
            "time_remaining": 0.9512195121951219,
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
          "setup_depth": 100.0,
          "waiting_time": 20.0,
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
          "fatigue": 18.0,
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
## Turn 5 | Day 1 白天
```json
[
  {
    "event_id": "evt_0005_public",
    "type": "PUBLIC_SYSTEM_ADVANCED",
    "actor": "system",
    "target": null,
    "data": {
      "projection_state": {
        "population_state": {
          "enabled": true,
          "region_name": "第七扇区·铁锈荒原",
          "region_size": 1000,
          "alive_count": 1000,
          "deaths_total": 0,
          "visible_peers": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            },
            {
              "id": "peer_chen",
              "name": "教授·陈",
              "opening_strategy": "研究信号塔废墟，试图理解共鸣波的规律以获取技术优势",
              "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
            },
            {
              "id": "peer_viper",
              "name": "毒蛇·卡里姆",
              "opening_strategy": "武装列车，拦截其他投放者的物资运输线",
              "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
            }
          ],
          "turn_history": [
            {
              "turn": 2,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 3,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 4,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 5,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            }
          ]
        },
        "public_system_state": {
          "enabled": true,
          "system_name": "末日方舟系统",
          "opening_announcement": "【末日方舟系统公告】第七扇区已激活。1,000名投放者已就位。\n你们拥有一列初始列车和七天缓冲期。第七天日落时，第一轮辐射风暴降临。\n存活者进入下一阶段。系统将持续记录你们的生存数据。祝你们好运。",
          "opening_rules": [
            "每7天一次辐射风暴，不在列车内或庇护所中的人将受到致命伤害",
            "排行榜每小时更新，综合评分=存活天数×资源储备×探索深度",
            "区域频道公开可用，但发言会暴露你的位置和策略",
            "掠夺者NPC每3天巡逻一次，独行且无武装者优先被袭击",
            "信号塔废墟有稀有物资，但共鸣波会造成精神损伤",
            "系统不干预PVP，但击杀投放者会被标记并降低交易信誉"
          ],
          "channel_feed": [
            {
              "sender": "铁拳·马库斯",
              "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
              "turn": 1
            },
            {
              "sender": "幽灵·蕾娜",
              "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
              "turn": 1
            },
            {
              "sender": "教授·陈",
              "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
              "turn": 1
            },
            {
              "sender": "新人0742",
              "message": "天啊这是真的吗？我连水都不够喝三天……",
              "turn": 1
            }
          ],
          "system_announcements": [],
          "regional_chat_enabled": true,
          "announcements_enabled": true
        },
        "market_state": {
          "market_enabled": true,
          "available_vendors": [],
          "market_prices": {},
          "player_inventory_listings": [],
          "recent_transactions": [],
          "market_trends": {}
        },
        "ranking_state": {
          "rankings_enabled": true,
          "player_rank_global": null,
          "player_rank_regional": 11,
          "leaderboards": {
            "regional": [
              {
                "rank": 1,
                "player_id": "peer_marcus",
                "name": "铁拳·马库斯",
                "status": "alive",
                "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
              },
              {
                "rank": 2,
                "player_id": "peer_lena",
                "name": "幽灵·蕾娜",
                "status": "alive",
                "visible_edge": "拥有隐身模块原型，探索时不易被发现"
              },
              {
                "rank": 3,
                "player_id": "peer_chen",
                "name": "教授·陈",
                "status": "alive",
                "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
              },
              {
                "rank": 4,
                "player_id": "peer_viper",
                "name": "毒蛇·卡里姆",
                "status": "alive",
                "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
              },
              {
                "rank": 11,
                "player_id": "player",
                "name": "你",
                "status": "alive"
              }
            ]
          },
          "rank_season_current": 1,
          "rank_season_end_turn": 100,
          "prestige_points": 0
        },
        "comparative_state": {
          "player_comparison_baseline": {
            "percentile": 99,
            "summary": "本回合表现已计入区域排名"
          },
          "performance_metrics_history": [
            {
              "turn": 2,
              "action_score": 15,
              "cumulative_score": 15,
              "percentile": 80,
              "regional_rank": 201
            },
            {
              "turn": 3,
              "action_score": 15,
              "cumulative_score": 30,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 4,
              "action_score": 15,
              "cumulative_score": 45,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 5,
              "action_score": 12,
              "cumulative_score": 57,
              "percentile": 99,
              "regional_rank": 11
            }
          ],
          "best_performance_by_category": {},
          "comparison_partners": [
            "peer_marcus",
            "peer_lena",
            "peer_chen",
            "peer_viper"
          ],
          "comparison_last_updated": 5
        },
        "rival_state": {
          "active_rivals": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            }
          ],
          "rival_relationships": {
            "peer_marcus": "unknown",
            "peer_lena": "unknown"
          },
          "rival_competitions_active": [],
          "rival_score_current": 57,
          "rival_score_target": 0,
          "rivalry_win_rate": 0.0,
          "last_rival_encounter": {
            "turn": 5,
            "rival_id": "peer_marcus",
            "relative_percentile": 99
          }
        }
      },
      "public_feedback": {
        "regional_statistics": {
          "region_name": "第七扇区·铁锈荒原",
          "alive_count": 1000,
          "deaths_this_turn": 0
        },
        "peer_comparison": {
          "turn": 5,
          "action_score": 12,
          "cumulative_score": 57,
          "percentile": 99,
          "regional_rank": 11
        },
        "ranking_changes": [
          {
            "player": "你",
            "regional_rank": 11,
            "percentile": 99
          }
        ],
        "channel_feed": [
          {
            "sender": "铁拳·马库斯",
            "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
            "turn": 1
          },
          {
            "sender": "幽灵·蕾娜",
            "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
            "turn": 1
          },
          {
            "sender": "教授·陈",
            "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
            "turn": 1
          },
          {
            "sender": "新人0742",
            "message": "天啊这是真的吗？我连水都不够喝三天……",
            "turn": 1
          }
        ],
        "system_announcements": []
      }
    },
    "turn": 5,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 5 | Day 1 白天
```json
[
  {
    "event_id": "evt_0005_options_86b15960",
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
            "label": "与老金交谈",
            "description": "与老金交谈",
            "action": {
              "action_id": "auto-old_jin",
              "type": "SOCIAL_INTERACTION",
              "target": "old_jin",
              "goal": "与老金交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-old_jin",
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
                  "fatigue": 4.6,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 10.6,
                "K": 10.0,
                "probability": 0.485004,
                "random_roll": 0.739913,
                "severity": 0.0,
                "severity_band": "成功区",
                "death_fairness": 0.63,
                "outcome": "失败但获得部分信息",
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
                    "critical": 0.0388,
                    "normal": 0.378303,
                    "costly": 0.485004,
                    "partial_failure": 0.794002,
                    "severe_failure": 0.97425
                  }
                }
              },
              "target_profile": {
                "id": "old_jin",
                "location_id": "camp_core",
                "action_type": "SOCIAL_INTERACTION",
                "is_npc": true,
                "primary_attribute": "spirit",
                "target_difficulty": 6,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.9,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "old_jin": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "old_jin_goal",
                      "old_jin_routine"
                    ]
                  }
                },
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "old_jin"
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "old_jin"
                }
              },
              "system_constraints": {
                "tags": [
                  "short_action"
                ],
                "commitments": [
                  [
                    "social_relationship",
                    "old_jin"
                  ]
                ],
                "windows": [
                  {
                    "group": "npc:old_jin",
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
                "available_time_minutes": 585.0,
                "available_stamina": 77.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "SOCIAL_INTERACTION",
                    "target": "old_jin",
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
                  "fatigue": 4.6,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 4.6,
                "K": 10.0,
                "probability": 0.631812,
                "random_roll": 0.950049,
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
                    "critical": 0.050545,
                    "normal": 0.492813,
                    "costly": 0.631812,
                    "partial_failure": 0.852725,
                    "severe_failure": 0.981591
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
                "available_time_minutes": 585.0,
                "available_stamina": 77.0,
                "available_mental": 100.0,
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
          },
          "C": {
            "id": "C",
            "label": "前往锈蚀车站",
            "description": "",
            "action": {
              "action_id": "auto-travel-rust_station",
              "type": "TRAVEL",
              "target": "rust_station"
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
                "id": "rust_station",
                "location_id": "rust_station",
                "action_type": "EXPLORATION",
                "primary_attribute": "agility",
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
                      "rust_station"
                    ],
                    "resource_changes": {
                      "净水": 3
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  },
                  "partial_failure": {
                    "resource_changes": {
                      "净水": 1
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  }
                },
                "encounter_target_ids": [
                  "rad_scorpion"
                ],
                "requirements": {
                  "location": "rust_station"
                },
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
                  "commitment_axis": "route_commitment",
                  "commitment_value": "rust_station",
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
                  }
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
                "available_time_minutes": 585.0,
                "available_stamina": 77.0,
                "available_mental": 100.0,
                "actions": [
                  {
                    "type": "TRAVEL",
                    "target": "rust_station",
                    "time_minutes": 30.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 0.0,
                    "tags": []
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
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 6 | Day 1 白天
```json
[
  {
    "event_id": "evt_0006_001",
    "type": "SOCIAL_RESOLVED",
    "actor": "player",
    "target": "old_jin",
    "data": {
      "action": {
        "action_id": "auto-old_jin",
        "type": "SOCIAL_INTERACTION",
        "target": "old_jin"
      },
      "action_ledger": {
        "available_time_minutes": 585.0,
        "available_stamina": 77.0,
        "available_mental": 100.0,
        "actions": [
          {
            "type": "SOCIAL_INTERACTION",
            "target": "old_jin",
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
            "old_jin"
          ]
        ],
        "windows": [
          {
            "group": "npc:old_jin",
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
        "action_id": "auto-old_jin",
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
          "fatigue": 4.6,
          "time_pressure": 0.0,
          "unknown_risk": 0.0
        },
        "advantage": 10.0,
        "resistance": 10.6,
        "K": 10.0,
        "probability": 0.485004,
        "random_roll": 0.739913,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.63,
        "outcome": "失败但获得部分信息",
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
            "critical": 0.0388,
            "normal": 0.378303,
            "costly": 0.485004,
            "partial_failure": 0.794002,
            "severe_failure": 0.97425
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
        "pressure": 17.8125,
        "payoff_maturity": 32.5,
        "payoff_impact": 13.5,
        "payoff_score": 31.0125,
        "narrative_debt": [
          {
            "id": "信号塔废墟的共鸣波从何而来？是自然现象还是人为操控？",
            "score": 0.0
          },
          {
            "id": "末日方舟系统的真正目的是什么？为什么选择第七扇区？",
            "score": 0.0
          },
          {
            "id": "共鸣晶体为何在靠近信号塔时会自动发热？",
            "score": 0.0
          },
          {
            "id": "老金似乎知道一些关于系统的事，他为什么不愿说？",
            "score": 0.0
          },
          {
            "id": "排行榜上偶尔出现又消失的玩家'影'是谁？",
            "score": 0.0
          }
        ],
        "progress": 0.245,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 15.0,
          "by_type": {
            "PUBLIC_SYSTEM_ADVANCED": 15.0,
            "TRAVEL_COMPLETED": 15.0,
            "OPTIONS_PRESENTED": 15.0,
            "RETURN_TO_BASE_COMPLETED": 0.0
          }
        },
        "agency": 0.028718,
        "uncertainty": 0.16,
        "risk_credibility": 0.0,
        "decision_value": 0.0,
        "combinability": 94.871795
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.05128205128205128,
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
            "time_remaining": 0.9487179487179487,
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
          "setup_depth": 100.0,
          "waiting_time": 25.0,
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
          "fatigue": 23.0,
          "story_damage": 0.0
        }
      }
    },
    "turn": 6,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 6 | Day 1 白天
```json
[
  {
    "event_id": "evt_0006_public",
    "type": "PUBLIC_SYSTEM_ADVANCED",
    "actor": "system",
    "target": null,
    "data": {
      "projection_state": {
        "population_state": {
          "enabled": true,
          "region_name": "第七扇区·铁锈荒原",
          "region_size": 1000,
          "alive_count": 1000,
          "deaths_total": 0,
          "visible_peers": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            },
            {
              "id": "peer_chen",
              "name": "教授·陈",
              "opening_strategy": "研究信号塔废墟，试图理解共鸣波的规律以获取技术优势",
              "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
            },
            {
              "id": "peer_viper",
              "name": "毒蛇·卡里姆",
              "opening_strategy": "武装列车，拦截其他投放者的物资运输线",
              "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
            }
          ],
          "turn_history": [
            {
              "turn": 2,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 3,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 4,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 5,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 6,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            }
          ]
        },
        "public_system_state": {
          "enabled": true,
          "system_name": "末日方舟系统",
          "opening_announcement": "【末日方舟系统公告】第七扇区已激活。1,000名投放者已就位。\n你们拥有一列初始列车和七天缓冲期。第七天日落时，第一轮辐射风暴降临。\n存活者进入下一阶段。系统将持续记录你们的生存数据。祝你们好运。",
          "opening_rules": [
            "每7天一次辐射风暴，不在列车内或庇护所中的人将受到致命伤害",
            "排行榜每小时更新，综合评分=存活天数×资源储备×探索深度",
            "区域频道公开可用，但发言会暴露你的位置和策略",
            "掠夺者NPC每3天巡逻一次，独行且无武装者优先被袭击",
            "信号塔废墟有稀有物资，但共鸣波会造成精神损伤",
            "系统不干预PVP，但击杀投放者会被标记并降低交易信誉"
          ],
          "channel_feed": [
            {
              "sender": "铁拳·马库斯",
              "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
              "turn": 1
            },
            {
              "sender": "幽灵·蕾娜",
              "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
              "turn": 1
            },
            {
              "sender": "教授·陈",
              "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
              "turn": 1
            },
            {
              "sender": "新人0742",
              "message": "天啊这是真的吗？我连水都不够喝三天……",
              "turn": 1
            }
          ],
          "system_announcements": [],
          "regional_chat_enabled": true,
          "announcements_enabled": true
        },
        "market_state": {
          "market_enabled": true,
          "available_vendors": [],
          "market_prices": {},
          "player_inventory_listings": [],
          "recent_transactions": [],
          "market_trends": {}
        },
        "ranking_state": {
          "rankings_enabled": true,
          "player_rank_global": null,
          "player_rank_regional": 11,
          "leaderboards": {
            "regional": [
              {
                "rank": 1,
                "player_id": "peer_marcus",
                "name": "铁拳·马库斯",
                "status": "alive",
                "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
              },
              {
                "rank": 2,
                "player_id": "peer_lena",
                "name": "幽灵·蕾娜",
                "status": "alive",
                "visible_edge": "拥有隐身模块原型，探索时不易被发现"
              },
              {
                "rank": 3,
                "player_id": "peer_chen",
                "name": "教授·陈",
                "status": "alive",
                "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
              },
              {
                "rank": 4,
                "player_id": "peer_viper",
                "name": "毒蛇·卡里姆",
                "status": "alive",
                "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
              },
              {
                "rank": 11,
                "player_id": "player",
                "name": "你",
                "status": "alive"
              }
            ]
          },
          "rank_season_current": 1,
          "rank_season_end_turn": 100,
          "prestige_points": 0
        },
        "comparative_state": {
          "player_comparison_baseline": {
            "percentile": 99,
            "summary": "本回合表现已计入区域排名"
          },
          "performance_metrics_history": [
            {
              "turn": 2,
              "action_score": 15,
              "cumulative_score": 15,
              "percentile": 80,
              "regional_rank": 201
            },
            {
              "turn": 3,
              "action_score": 15,
              "cumulative_score": 30,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 4,
              "action_score": 15,
              "cumulative_score": 45,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 5,
              "action_score": 12,
              "cumulative_score": 57,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 6,
              "action_score": 3,
              "cumulative_score": 60,
              "percentile": 99,
              "regional_rank": 11
            }
          ],
          "best_performance_by_category": {},
          "comparison_partners": [
            "peer_marcus",
            "peer_lena",
            "peer_chen",
            "peer_viper"
          ],
          "comparison_last_updated": 6
        },
        "rival_state": {
          "active_rivals": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            }
          ],
          "rival_relationships": {
            "peer_marcus": "unknown",
            "peer_lena": "unknown"
          },
          "rival_competitions_active": [],
          "rival_score_current": 60,
          "rival_score_target": 0,
          "rivalry_win_rate": 0.0,
          "last_rival_encounter": {
            "turn": 6,
            "rival_id": "peer_marcus",
            "relative_percentile": 99
          }
        }
      },
      "public_feedback": {
        "regional_statistics": {
          "region_name": "第七扇区·铁锈荒原",
          "alive_count": 1000,
          "deaths_this_turn": 0
        },
        "peer_comparison": {
          "turn": 6,
          "action_score": 3,
          "cumulative_score": 60,
          "percentile": 99,
          "regional_rank": 11
        },
        "ranking_changes": [
          {
            "player": "你",
            "regional_rank": 11,
            "percentile": 99
          }
        ],
        "channel_feed": [
          {
            "sender": "铁拳·马库斯",
            "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
            "turn": 1
          },
          {
            "sender": "幽灵·蕾娜",
            "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
            "turn": 1
          },
          {
            "sender": "教授·陈",
            "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
            "turn": 1
          },
          {
            "sender": "新人0742",
            "message": "天啊这是真的吗？我连水都不够喝三天……",
            "turn": 1
          }
        ],
        "system_announcements": []
      }
    },
    "turn": 6,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 6 | Day 1 白天
```json
[
  {
    "event_id": "evt_0006_options_63910524",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 6,
        "options": {
          "A": {
            "id": "A",
            "label": "与老金交谈",
            "description": "与老金交谈",
            "action": {
              "action_id": "auto-old_jin",
              "type": "SOCIAL_INTERACTION",
              "target": "old_jin",
              "goal": "与老金交谈"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-old_jin",
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
                  "fatigue": 5.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 11.0,
                "K": 10.0,
                "probability": 0.475021,
                "random_roll": 0.201925,
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
                    "critical": 0.038002,
                    "normal": 0.370516,
                    "costly": 0.475021,
                    "partial_failure": 0.790008,
                    "severe_failure": 0.973751
                  }
                }
              },
              "target_profile": {
                "id": "old_jin",
                "location_id": "camp_core",
                "action_type": "SOCIAL_INTERACTION",
                "is_npc": true,
                "primary_attribute": "spirit",
                "target_difficulty": 6,
                "risk_warning": 1.0,
                "causal_chain": 1.0,
                "avoidable": 0.9,
                "rule_consistency": 1.0,
                "player_responsibility": 0.7,
                "effects": {
                  "success": {
                    "relationship_changes": {
                      "old_jin": {
                        "trust": 3,
                        "respect": 1
                      }
                    },
                    "knowledge_additions": [
                      "old_jin_goal",
                      "old_jin_routine"
                    ]
                  }
                },
                "requirements": {
                  "location": "camp_core",
                  "npc_available": "old_jin"
                },
                "constraints": {
                  "system_tags": [
                    "short_action"
                  ],
                  "commitment_axis": "social_relationship",
                  "commitment_value": "old_jin"
                }
              },
              "system_constraints": {
                "tags": [
                  "short_action"
                ],
                "commitments": [
                  [
                    "social_relationship",
                    "old_jin"
                  ]
                ],
                "windows": [
                  {
                    "group": "npc:old_jin",
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
                "available_time_minutes": 555.0,
                "available_stamina": 75.0,
                "available_mental": 96.0,
                "actions": [
                  {
                    "type": "SOCIAL_INTERACTION",
                    "target": "old_jin",
                    "time_minutes": 30.0,
                    "stamina_cost": 2.0,
                    "mental_cost": 4.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 6
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
                  "fatigue": 5.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 0.0
                },
                "advantage": 10.0,
                "resistance": 5.0,
                "K": 10.0,
                "probability": 0.622459,
                "random_roll": 0.488923,
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
                    "critical": 0.049797,
                    "normal": 0.485518,
                    "costly": 0.622459,
                    "partial_failure": 0.848984,
                    "severe_failure": 0.981123
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
                "available_time_minutes": 555.0,
                "available_stamina": 75.0,
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
            "state_turn": 6
          },
          "C": {
            "id": "C",
            "label": "前往锈蚀车站",
            "description": "",
            "action": {
              "action_id": "auto-travel-rust_station",
              "type": "TRAVEL",
              "target": "rust_station"
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
                "id": "rust_station",
                "location_id": "rust_station",
                "action_type": "EXPLORATION",
                "primary_attribute": "agility",
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
                      "rust_station"
                    ],
                    "resource_changes": {
                      "净水": 3
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  },
                  "partial_failure": {
                    "resource_changes": {
                      "净水": 1
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  }
                },
                "encounter_target_ids": [
                  "rad_scorpion"
                ],
                "requirements": {
                  "location": "rust_station"
                },
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
                  "commitment_axis": "route_commitment",
                  "commitment_value": "rust_station",
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
                  }
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
                "available_time_minutes": 555.0,
                "available_stamina": 75.0,
                "available_mental": 96.0,
                "actions": [
                  {
                    "type": "TRAVEL",
                    "target": "rust_station",
                    "time_minutes": 30.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 6
          }
        }
      },
      "state_turn": 6
    },
    "turn": 6,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 7 | Day 1 白天
```json
[
  {
    "event_id": "evt_0007_001",
    "type": "TRAVEL_COMPLETED",
    "actor": "player",
    "target": "rust_station",
    "data": {
      "action": {
        "action_id": "auto-travel-rust_station",
        "type": "TRAVEL",
        "target": "rust_station"
      },
      "action_ledger": {
        "available_time_minutes": 555.0,
        "available_stamina": 75.0,
        "available_mental": 96.0,
        "actions": [
          {
            "type": "TRAVEL",
            "target": "rust_station",
            "time_minutes": 30.0,
            "stamina_cost": 5.0,
            "mental_cost": 0.0,
            "tags": []
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
      "current_location": "rust_station",
      "current_location_name": "锈蚀车站",
      "current_encounter_id": null,
      "movement": {
        "from": "camp_core",
        "to": "rust_station",
        "mode": "TRAVEL"
      },
      "discover_locations": [
        "rust_station"
      ],
      "proposed_events": [
        {
          "type": "LOCATION_ENTERED",
          "target": "rust_station"
        }
      ],
      "runtime_metrics": {
        "pressure": 18.4375,
        "payoff_maturity": 33.5,
        "payoff_impact": 23.5,
        "payoff_score": 31.94675,
        "narrative_debt": [
          {
            "id": "信号塔废墟的共鸣波从何而来？是自然现象还是人为操控？",
            "score": 0.0
          },
          {
            "id": "末日方舟系统的真正目的是什么？为什么选择第七扇区？",
            "score": 0.0
          },
          {
            "id": "共鸣晶体为何在靠近信号塔时会自动发热？",
            "score": 0.0
          },
          {
            "id": "老金似乎知道一些关于系统的事，他为什么不愿说？",
            "score": 0.0
          },
          {
            "id": "排行榜上偶尔出现又消失的玩家'影'是谁？",
            "score": 0.0
          }
        ],
        "progress": 0.165,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 15.0,
          "by_type": {
            "PUBLIC_SYSTEM_ADVANCED": 15.0,
            "TRAVEL_COMPLETED": 0.0,
            "OPTIONS_PRESENTED": 15.0,
            "RETURN_TO_BASE_COMPLETED": 0.0,
            "SOCIAL_RESOLVED": 0.0
          }
        },
        "agency": 0.012613,
        "uncertainty": 0.226667,
        "risk_credibility": 0.079333,
        "decision_value": 0.002018,
        "combinability": 94.594595
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.05405405405405406,
          "irreversibility": 0.5,
          "information_uncertainty": 0.16666666666666666,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 0.8333333333333334,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.16666666666666666,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.16666666666666666
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.85,
            "enemy_effectiveness": 0.7,
            "information_incompleteness": 0.16666666666666666,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.9459459459459459,
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
          "setup_depth": 100.0,
          "waiting_time": 30.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 40.0,
          "restriction_removed": 50.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 0.85,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 0.7,
          "new_playable_system": 60.0,
          "decision_change": 0.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 25.0,
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
## Turn 7 | Day 1 白天
```json
[
  {
    "event_id": "evt_0007_public",
    "type": "PUBLIC_SYSTEM_ADVANCED",
    "actor": "system",
    "target": null,
    "data": {
      "projection_state": {
        "population_state": {
          "enabled": true,
          "region_name": "第七扇区·铁锈荒原",
          "region_size": 1000,
          "alive_count": 1000,
          "deaths_total": 0,
          "visible_peers": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            },
            {
              "id": "peer_chen",
              "name": "教授·陈",
              "opening_strategy": "研究信号塔废墟，试图理解共鸣波的规律以获取技术优势",
              "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
            },
            {
              "id": "peer_viper",
              "name": "毒蛇·卡里姆",
              "opening_strategy": "武装列车，拦截其他投放者的物资运输线",
              "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
            }
          ],
          "turn_history": [
            {
              "turn": 2,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 3,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 4,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 5,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 6,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 7,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            }
          ]
        },
        "public_system_state": {
          "enabled": true,
          "system_name": "末日方舟系统",
          "opening_announcement": "【末日方舟系统公告】第七扇区已激活。1,000名投放者已就位。\n你们拥有一列初始列车和七天缓冲期。第七天日落时，第一轮辐射风暴降临。\n存活者进入下一阶段。系统将持续记录你们的生存数据。祝你们好运。",
          "opening_rules": [
            "每7天一次辐射风暴，不在列车内或庇护所中的人将受到致命伤害",
            "排行榜每小时更新，综合评分=存活天数×资源储备×探索深度",
            "区域频道公开可用，但发言会暴露你的位置和策略",
            "掠夺者NPC每3天巡逻一次，独行且无武装者优先被袭击",
            "信号塔废墟有稀有物资，但共鸣波会造成精神损伤",
            "系统不干预PVP，但击杀投放者会被标记并降低交易信誉"
          ],
          "channel_feed": [
            {
              "sender": "铁拳·马库斯",
              "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
              "turn": 1
            },
            {
              "sender": "幽灵·蕾娜",
              "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
              "turn": 1
            },
            {
              "sender": "教授·陈",
              "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
              "turn": 1
            },
            {
              "sender": "新人0742",
              "message": "天啊这是真的吗？我连水都不够喝三天……",
              "turn": 1
            }
          ],
          "system_announcements": [],
          "regional_chat_enabled": true,
          "announcements_enabled": true
        },
        "market_state": {
          "market_enabled": true,
          "available_vendors": [],
          "market_prices": {},
          "player_inventory_listings": [],
          "recent_transactions": [],
          "market_trends": {}
        },
        "ranking_state": {
          "rankings_enabled": true,
          "player_rank_global": null,
          "player_rank_regional": 11,
          "leaderboards": {
            "regional": [
              {
                "rank": 1,
                "player_id": "peer_marcus",
                "name": "铁拳·马库斯",
                "status": "alive",
                "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
              },
              {
                "rank": 2,
                "player_id": "peer_lena",
                "name": "幽灵·蕾娜",
                "status": "alive",
                "visible_edge": "拥有隐身模块原型，探索时不易被发现"
              },
              {
                "rank": 3,
                "player_id": "peer_chen",
                "name": "教授·陈",
                "status": "alive",
                "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
              },
              {
                "rank": 4,
                "player_id": "peer_viper",
                "name": "毒蛇·卡里姆",
                "status": "alive",
                "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
              },
              {
                "rank": 11,
                "player_id": "player",
                "name": "你",
                "status": "alive"
              }
            ]
          },
          "rank_season_current": 1,
          "rank_season_end_turn": 100,
          "prestige_points": 0
        },
        "comparative_state": {
          "player_comparison_baseline": {
            "percentile": 99,
            "summary": "本回合表现已计入区域排名"
          },
          "performance_metrics_history": [
            {
              "turn": 2,
              "action_score": 15,
              "cumulative_score": 15,
              "percentile": 80,
              "regional_rank": 201
            },
            {
              "turn": 3,
              "action_score": 15,
              "cumulative_score": 30,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 4,
              "action_score": 15,
              "cumulative_score": 45,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 5,
              "action_score": 12,
              "cumulative_score": 57,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 6,
              "action_score": 3,
              "cumulative_score": 60,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 7,
              "action_score": 15,
              "cumulative_score": 75,
              "percentile": 99,
              "regional_rank": 11
            }
          ],
          "best_performance_by_category": {},
          "comparison_partners": [
            "peer_marcus",
            "peer_lena",
            "peer_chen",
            "peer_viper"
          ],
          "comparison_last_updated": 7
        },
        "rival_state": {
          "active_rivals": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            }
          ],
          "rival_relationships": {
            "peer_marcus": "unknown",
            "peer_lena": "unknown"
          },
          "rival_competitions_active": [],
          "rival_score_current": 75,
          "rival_score_target": 0,
          "rivalry_win_rate": 0.0,
          "last_rival_encounter": {
            "turn": 7,
            "rival_id": "peer_marcus",
            "relative_percentile": 99
          }
        }
      },
      "public_feedback": {
        "regional_statistics": {
          "region_name": "第七扇区·铁锈荒原",
          "alive_count": 1000,
          "deaths_this_turn": 0
        },
        "peer_comparison": {
          "turn": 7,
          "action_score": 15,
          "cumulative_score": 75,
          "percentile": 99,
          "regional_rank": 11
        },
        "ranking_changes": [
          {
            "player": "你",
            "regional_rank": 11,
            "percentile": 99
          }
        ],
        "channel_feed": [
          {
            "sender": "铁拳·马库斯",
            "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
            "turn": 1
          },
          {
            "sender": "幽灵·蕾娜",
            "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
            "turn": 1
          },
          {
            "sender": "教授·陈",
            "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
            "turn": 1
          },
          {
            "sender": "新人0742",
            "message": "天啊这是真的吗？我连水都不够喝三天……",
            "turn": 1
          }
        ],
        "system_announcements": []
      }
    },
    "turn": 7,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 7 | Day 1 白天
```json
[
  {
    "event_id": "evt_0007_options_44cf7a00",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 7,
        "options": {
          "A": {
            "id": "A",
            "label": "rust_station",
            "description": "rust_station",
            "action": {
              "action_id": "auto-rust_station",
              "type": "EXPLORATION",
              "target": "rust_station",
              "goal": "rust_station"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-rust_station",
                "advantage_components": {
                  "ability_match": 10.0,
                  "equipment_advantage": 0.0,
                  "preparation": 3.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 14.0,
                  "environment_penalty": 3.0,
                  "injury": 0.0,
                  "fatigue": 6.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 3.0
                },
                "advantage": 13.0,
                "resistance": 26.0,
                "K": 10.0,
                "probability": 0.214165,
                "random_roll": 0.912733,
                "severity": 0.0,
                "severity_band": "成功区",
                "death_fairness": 0.3808,
                "outcome": "严重失败",
                "death_allowed": false,
                "components": {
                  "severity": {
                    "difficulty": 2.8,
                    "injury": 0.0,
                    "resource_shortage": 0.0,
                    "information_missing": 2.0,
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 3.0,
                    "ability_match": 10.0,
                    "teammate_support": 0.0,
                    "survival_assets": 0.0
                  },
                  "death_fairness_inputs": {
                    "risk_warning": 0.7,
                    "causal_chain": 0.85,
                    "avoidable": 0.8,
                    "rule_consistency": 1.0,
                    "player_responsibility": 0.8
                  },
                  "outcome_thresholds": {
                    "critical": 0.017133,
                    "normal": 0.167049,
                    "costly": 0.214165,
                    "partial_failure": 0.685666,
                    "severe_failure": 0.960708
                  }
                }
              },
              "target_profile": {
                "id": "rust_station",
                "location_id": "rust_station",
                "action_type": "EXPLORATION",
                "primary_attribute": "agility",
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
                      "rust_station"
                    ],
                    "resource_changes": {
                      "净水": 3
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  },
                  "partial_failure": {
                    "resource_changes": {
                      "净水": 1
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  }
                },
                "encounter_target_ids": [
                  "rad_scorpion"
                ],
                "requirements": {
                  "location": "rust_station"
                },
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
                  "commitment_axis": "route_commitment",
                  "commitment_value": "rust_station",
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
                  }
                }
              },
              "system_constraints": {
                "tags": [
                  "major_action",
                  "requires_full_attention"
                ],
                "commitments": [
                  [
                    "route_commitment",
                    "rust_station"
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
              "action_ledger": {
                "available_time_minutes": 525.0,
                "available_stamina": 70.0,
                "available_mental": 96.0,
                "actions": [
                  {
                    "type": "EXPLORATION",
                    "target": "rust_station",
                    "time_minutes": 120.0,
                    "stamina_cost": 15.0,
                    "mental_cost": 10.0,
                    "tags": [
                      "major_action",
                      "requires_full_attention"
                    ]
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 7
          },
          "B": {
            "id": "B",
            "label": "返回基地",
            "description": "",
            "action": {
              "action_id": "auto-return",
              "type": "RETURN_TO_BASE"
            },
            "preview": {
              "legal": true,
              "errors": [],
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
              "target_profile": {},
              "system_constraints": {
                "tags": [],
                "commitments": [],
                "windows": [],
                "allowed_periods": [],
                "npc_unavailable": false
              },
              "action_ledger": {
                "available_time_minutes": 525.0,
                "available_stamina": 70.0,
                "available_mental": 96.0,
                "actions": [
                  {
                    "type": "RETURN_TO_BASE",
                    "target": null,
                    "time_minutes": 30.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 7
          },
          "C": {
            "id": "C",
            "label": "前往信号塔废墟",
            "description": "",
            "action": {
              "action_id": "auto-travel-signal_tower_ruins",
              "type": "TRAVEL",
              "target": "signal_tower_ruins"
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
                "time_cost": 45.0,
                "stamina_cost": 8.0,
                "mental_cost": 0.0
              },
              "target_profile": {
                "id": "signal_tower_ruins",
                "location_id": "signal_tower_ruins",
                "action_type": "RESEARCH",
                "primary_attribute": "spirit",
                "target_difficulty": 20,
                "environment_penalty": 5,
                "unknown_risk": 10,
                "risk_warning": 0.8,
                "causal_chain": 0.85,
                "avoidable": 0.7,
                "rule_consistency": 1.0,
                "player_responsibility": 0.8,
                "effects": {
                  "success": {
                    "knowledge_additions": [
                      "signal_tower_ruins_principle"
                    ],
                    "resource_changes": {
                      "燃料棒": 2
                    }
                  }
                },
                "requirements": {
                  "location": "signal_tower_ruins"
                },
                "constraints": {
                  "system_tags": [
                    "major_action",
                    "requires_full_attention"
                  ],
                  "exclusive_group": "research_window",
                  "window_ids": [
                    "白天",
                    "黄昏"
                  ],
                  "window_capacity": 1,
                  "commitment_axis": "research_focus",
                  "commitment_value": "signal_tower_ruins"
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
                "available_time_minutes": 525.0,
                "available_stamina": 70.0,
                "available_mental": 96.0,
                "actions": [
                  {
                    "type": "TRAVEL",
                    "target": "signal_tower_ruins",
                    "time_minutes": 45.0,
                    "stamina_cost": 8.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 7
          }
        }
      },
      "state_turn": 7
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
    "type": "EXPLORATION_RESOLVED",
    "actor": "player",
    "target": "rust_station",
    "data": {
      "action": {
        "action_id": "auto-rust_station",
        "type": "EXPLORATION",
        "target": "rust_station"
      },
      "action_ledger": {
        "available_time_minutes": 525.0,
        "available_stamina": 70.0,
        "available_mental": 96.0,
        "actions": [
          {
            "type": "EXPLORATION",
            "target": "rust_station",
            "time_minutes": 120.0,
            "stamina_cost": 15.0,
            "mental_cost": 10.0,
            "tags": [
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
            "rust_station"
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
        "action_id": "auto-rust_station",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 3.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 14.0,
          "environment_penalty": 3.0,
          "injury": 0.0,
          "fatigue": 6.0,
          "time_pressure": 0.0,
          "unknown_risk": 3.0
        },
        "advantage": 13.0,
        "resistance": 26.0,
        "K": 10.0,
        "probability": 0.214165,
        "random_roll": 0.912733,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.3808,
        "outcome": "严重失败",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.8,
            "injury": 0.0,
            "resource_shortage": 0.0,
            "information_missing": 2.0,
            "time_pressure": 0.0,
            "continuous_errors": 0.0,
            "preparation": 3.0,
            "ability_match": 10.0,
            "teammate_support": 0.0,
            "survival_assets": 0.0
          },
          "death_fairness_inputs": {
            "risk_warning": 0.7,
            "causal_chain": 0.85,
            "avoidable": 0.8,
            "rule_consistency": 1.0,
            "player_responsibility": 0.8
          },
          "outcome_thresholds": {
            "critical": 0.017133,
            "normal": 0.167049,
            "costly": 0.214165,
            "partial_failure": 0.685666,
            "severe_failure": 0.960708
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
        "pressure": 19.0625,
        "payoff_maturity": 34.5,
        "payoff_impact": 13.5,
        "payoff_score": 31.19675,
        "narrative_debt": [
          {
            "id": "信号塔废墟的共鸣波从何而来？是自然现象还是人为操控？",
            "score": 0.0
          },
          {
            "id": "末日方舟系统的真正目的是什么？为什么选择第七扇区？",
            "score": 0.0
          },
          {
            "id": "共鸣晶体为何在靠近信号塔时会自动发热？",
            "score": 0.0
          },
          {
            "id": "老金似乎知道一些关于系统的事，他为什么不愿说？",
            "score": 0.0
          },
          {
            "id": "排行榜上偶尔出现又消失的玩家'影'是谁？",
            "score": 0.0
          }
        ],
        "progress": 0.245,
        "stagnation_rate": 1.0,
        "repetition_fatigue": {
          "max": 15.0,
          "by_type": {
            "PUBLIC_SYSTEM_ADVANCED": 15.0,
            "RETURN_TO_BASE_COMPLETED": 0.0,
            "OPTIONS_PRESENTED": 15.0,
            "SOCIAL_RESOLVED": 0.0,
            "TRAVEL_COMPLETED": 0.0
          }
        },
        "agency": 0.053333,
        "uncertainty": 0.226667,
        "risk_credibility": 0.079333,
        "decision_value": 0.008533,
        "combinability": 77.142857
      },
      "narrative_inputs": {
        "decision": {
          "consequence_difference": 0.8,
          "opportunity_cost": 0.22857142857142856,
          "irreversibility": 0.5,
          "information_uncertainty": 0.16666666666666666,
          "value_impact": 0.7,
          "route_divergence": 0.8,
          "option_balance": 0.7,
          "information_sufficiency": 0.8333333333333334,
          "long_term_impact": 0.5,
          "uncertainty": {
            "danger_unknown": 0.16666666666666666,
            "rule_unknown": 0.1,
            "motive_unknown": 0.3,
            "world_unknown": 0.5,
            "reward_unknown": 0.16666666666666666
          },
          "risk_credibility": {
            "cost_fulfillment": 1.0,
            "failure_clarity": 0.85,
            "enemy_effectiveness": 0.7,
            "information_incompleteness": 0.16666666666666666,
            "limited_protection": 0.8
          },
          "combinability": {
            "time_remaining": 0.7714285714285715,
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
          "setup_depth": 100.0,
          "waiting_time": 35.0,
          "cost_paid": 0.0,
          "chapter_rhythm": 50.0,
          "relative_gain": 40.0,
          "restriction_removed": 0.0,
          "behavior_change": 40.0,
          "long_term_value": 50.0,
          "social_feedback": 0.0,
          "causal_chain": 0.85,
          "rule_consistency": 1.0,
          "reward_foreshadowed": 0.7,
          "new_playable_system": 60.0,
          "decision_change": 40.0,
          "higher_resource_need": 30.0,
          "social_market_effect": 0.0,
          "fatigue": 30.0,
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
## Turn 8 | Day 1 白天
```json
[
  {
    "event_id": "evt_0008_public",
    "type": "PUBLIC_SYSTEM_ADVANCED",
    "actor": "system",
    "target": null,
    "data": {
      "projection_state": {
        "population_state": {
          "enabled": true,
          "region_name": "第七扇区·铁锈荒原",
          "region_size": 1000,
          "alive_count": 1000,
          "deaths_total": 0,
          "visible_peers": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            },
            {
              "id": "peer_chen",
              "name": "教授·陈",
              "opening_strategy": "研究信号塔废墟，试图理解共鸣波的规律以获取技术优势",
              "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
            },
            {
              "id": "peer_viper",
              "name": "毒蛇·卡里姆",
              "opening_strategy": "武装列车，拦截其他投放者的物资运输线",
              "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
            }
          ],
          "turn_history": [
            {
              "turn": 2,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 3,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 4,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 5,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 6,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 7,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            },
            {
              "turn": 8,
              "alive_before": 1000,
              "alive_after": 1000,
              "deaths": 0
            }
          ]
        },
        "public_system_state": {
          "enabled": true,
          "system_name": "末日方舟系统",
          "opening_announcement": "【末日方舟系统公告】第七扇区已激活。1,000名投放者已就位。\n你们拥有一列初始列车和七天缓冲期。第七天日落时，第一轮辐射风暴降临。\n存活者进入下一阶段。系统将持续记录你们的生存数据。祝你们好运。",
          "opening_rules": [
            "每7天一次辐射风暴，不在列车内或庇护所中的人将受到致命伤害",
            "排行榜每小时更新，综合评分=存活天数×资源储备×探索深度",
            "区域频道公开可用，但发言会暴露你的位置和策略",
            "掠夺者NPC每3天巡逻一次，独行且无武装者优先被袭击",
            "信号塔废墟有稀有物资，但共鸣波会造成精神损伤",
            "系统不干预PVP，但击杀投放者会被标记并降低交易信誉"
          ],
          "channel_feed": [
            {
              "sender": "铁拳·马库斯",
              "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
              "turn": 1
            },
            {
              "sender": "幽灵·蕾娜",
              "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
              "turn": 1
            },
            {
              "sender": "教授·陈",
              "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
              "turn": 1
            },
            {
              "sender": "新人0742",
              "message": "天啊这是真的吗？我连水都不够喝三天……",
              "turn": 1
            }
          ],
          "system_announcements": [],
          "regional_chat_enabled": true,
          "announcements_enabled": true
        },
        "market_state": {
          "market_enabled": true,
          "available_vendors": [],
          "market_prices": {},
          "player_inventory_listings": [],
          "recent_transactions": [],
          "market_trends": {}
        },
        "ranking_state": {
          "rankings_enabled": true,
          "player_rank_global": null,
          "player_rank_regional": 11,
          "leaderboards": {
            "regional": [
              {
                "rank": 1,
                "player_id": "peer_marcus",
                "name": "铁拳·马库斯",
                "status": "alive",
                "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
              },
              {
                "rank": 2,
                "player_id": "peer_lena",
                "name": "幽灵·蕾娜",
                "status": "alive",
                "visible_edge": "拥有隐身模块原型，探索时不易被发现"
              },
              {
                "rank": 3,
                "player_id": "peer_chen",
                "name": "教授·陈",
                "status": "alive",
                "visible_edge": "前科研人员，拥有信号分析仪的蓝图"
              },
              {
                "rank": 4,
                "player_id": "peer_viper",
                "name": "毒蛇·卡里姆",
                "status": "alive",
                "visible_edge": "初始装备有突击步枪和弹药，战斗经验丰富"
              },
              {
                "rank": 11,
                "player_id": "player",
                "name": "你",
                "status": "alive"
              }
            ]
          },
          "rank_season_current": 1,
          "rank_season_end_turn": 100,
          "prestige_points": 0
        },
        "comparative_state": {
          "player_comparison_baseline": {
            "percentile": 99,
            "summary": "本回合表现已计入区域排名"
          },
          "performance_metrics_history": [
            {
              "turn": 2,
              "action_score": 15,
              "cumulative_score": 15,
              "percentile": 80,
              "regional_rank": 201
            },
            {
              "turn": 3,
              "action_score": 15,
              "cumulative_score": 30,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 4,
              "action_score": 15,
              "cumulative_score": 45,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 5,
              "action_score": 12,
              "cumulative_score": 57,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 6,
              "action_score": 3,
              "cumulative_score": 60,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 7,
              "action_score": 15,
              "cumulative_score": 75,
              "percentile": 99,
              "regional_rank": 11
            },
            {
              "turn": 8,
              "action_score": -6,
              "cumulative_score": 69,
              "percentile": 99,
              "regional_rank": 11
            }
          ],
          "best_performance_by_category": {},
          "comparison_partners": [
            "peer_marcus",
            "peer_lena",
            "peer_chen",
            "peer_viper"
          ],
          "comparison_last_updated": 8
        },
        "rival_state": {
          "active_rivals": [
            {
              "id": "peer_marcus",
              "name": "铁拳·马库斯",
              "opening_strategy": "快速加固列车装甲并招募盟友，建立小型车队",
              "visible_edge": "重型改装列车，装甲防御是普通列车的两倍"
            },
            {
              "id": "peer_lena",
              "name": "幽灵·蕾娜",
              "opening_strategy": "隐蔽行动，独自探索高价值废墟后迅速撤离",
              "visible_edge": "拥有隐身模块原型，探索时不易被发现"
            }
          ],
          "rival_relationships": {
            "peer_marcus": "unknown",
            "peer_lena": "unknown"
          },
          "rival_competitions_active": [],
          "rival_score_current": 69,
          "rival_score_target": 0,
          "rivalry_win_rate": 0.0,
          "last_rival_encounter": {
            "turn": 8,
            "rival_id": "peer_marcus",
            "relative_percentile": 99
          }
        }
      },
      "public_feedback": {
        "regional_statistics": {
          "region_name": "第七扇区·铁锈荒原",
          "alive_count": 1000,
          "deaths_this_turn": 0
        },
        "peer_comparison": {
          "turn": 8,
          "action_score": -6,
          "cumulative_score": 69,
          "percentile": 99,
          "regional_rank": 11
        },
        "ranking_changes": [
          {
            "player": "你",
            "regional_rank": 11,
            "percentile": 99
          }
        ],
        "channel_feed": [
          {
            "sender": "铁拳·马库斯",
            "message": "我的列车已经加固了装甲板，谁想结盟？资源共享。",
            "turn": 1
          },
          {
            "sender": "幽灵·蕾娜",
            "message": "别在频道里暴露位置。我已经找到第一个物资点了。",
            "turn": 1
          },
          {
            "sender": "教授·陈",
            "message": "有人注意到信号塔废墟的能量读数吗？那不是普通的辐射。",
            "turn": 1
          },
          {
            "sender": "新人0742",
            "message": "天啊这是真的吗？我连水都不够喝三天……",
            "turn": 1
          }
        ],
        "system_announcements": []
      }
    },
    "turn": 8,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 8 | Day 1 白天
```json
[
  {
    "event_id": "evt_0008_options_cde32d29",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 8,
        "options": {
          "A": {
            "id": "A",
            "label": "rust_station",
            "description": "rust_station",
            "action": {
              "action_id": "auto-rust_station",
              "type": "EXPLORATION",
              "target": "rust_station",
              "goal": "rust_station"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-rust_station",
                "advantage_components": {
                  "ability_match": 10.0,
                  "equipment_advantage": 0.0,
                  "preparation": 3.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 14.0,
                  "environment_penalty": 3.0,
                  "injury": 0.0,
                  "fatigue": 9.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 3.0
                },
                "advantage": 13.0,
                "resistance": 29.0,
                "K": 10.0,
                "probability": 0.167982,
                "random_roll": 0.378626,
                "severity": 0.0,
                "severity_band": "成功区",
                "death_fairness": 0.3808,
                "outcome": "失败但获得部分信息",
                "death_allowed": false,
                "components": {
                  "severity": {
                    "difficulty": 2.8,
                    "injury": 0.0,
                    "resource_shortage": 0.0,
                    "information_missing": 2.0,
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 3.0,
                    "ability_match": 10.0,
                    "teammate_support": 0.0,
                    "survival_assets": 0.0
                  },
                  "death_fairness_inputs": {
                    "risk_warning": 0.7,
                    "causal_chain": 0.85,
                    "avoidable": 0.8,
                    "rule_consistency": 1.0,
                    "player_responsibility": 0.8
                  },
                  "outcome_thresholds": {
                    "critical": 0.013439,
                    "normal": 0.131026,
                    "costly": 0.167982,
                    "partial_failure": 0.667193,
                    "severe_failure": 0.958399
                  }
                }
              },
              "target_profile": {
                "id": "rust_station",
                "location_id": "rust_station",
                "action_type": "EXPLORATION",
                "primary_attribute": "agility",
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
                      "rust_station"
                    ],
                    "resource_changes": {
                      "净水": 3
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  },
                  "partial_failure": {
                    "resource_changes": {
                      "净水": 1
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  }
                },
                "encounter_target_ids": [
                  "rad_scorpion"
                ],
                "requirements": {
                  "location": "rust_station"
                },
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
                  "commitment_axis": "route_commitment",
                  "commitment_value": "rust_station",
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
                  }
                }
              },
              "system_constraints": {
                "tags": [
                  "major_action",
                  "requires_full_attention"
                ],
                "commitments": [
                  [
                    "route_commitment",
                    "rust_station"
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
              "action_ledger": {
                "available_time_minutes": 405.0,
                "available_stamina": 55.0,
                "available_mental": 86.0,
                "actions": [
                  {
                    "type": "EXPLORATION",
                    "target": "rust_station",
                    "time_minutes": 120.0,
                    "stamina_cost": 15.0,
                    "mental_cost": 10.0,
                    "tags": [
                      "major_action",
                      "requires_full_attention"
                    ]
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 8
          },
          "B": {
            "id": "B",
            "label": "返回基地",
            "description": "",
            "action": {
              "action_id": "auto-return",
              "type": "RETURN_TO_BASE"
            },
            "preview": {
              "legal": true,
              "errors": [],
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
              "target_profile": {},
              "system_constraints": {
                "tags": [],
                "commitments": [],
                "windows": [],
                "allowed_periods": [],
                "npc_unavailable": false
              },
              "action_ledger": {
                "available_time_minutes": 405.0,
                "available_stamina": 55.0,
                "available_mental": 86.0,
                "actions": [
                  {
                    "type": "RETURN_TO_BASE",
                    "target": null,
                    "time_minutes": 30.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 8
          },
          "C": {
            "id": "C",
            "label": "前往信号塔废墟",
            "description": "",
            "action": {
              "action_id": "auto-travel-signal_tower_ruins",
              "type": "TRAVEL",
              "target": "signal_tower_ruins"
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
                "time_cost": 45.0,
                "stamina_cost": 8.0,
                "mental_cost": 0.0
              },
              "target_profile": {
                "id": "signal_tower_ruins",
                "location_id": "signal_tower_ruins",
                "action_type": "RESEARCH",
                "primary_attribute": "spirit",
                "target_difficulty": 20,
                "environment_penalty": 5,
                "unknown_risk": 10,
                "risk_warning": 0.8,
                "causal_chain": 0.85,
                "avoidable": 0.7,
                "rule_consistency": 1.0,
                "player_responsibility": 0.8,
                "effects": {
                  "success": {
                    "knowledge_additions": [
                      "signal_tower_ruins_principle"
                    ],
                    "resource_changes": {
                      "燃料棒": 2
                    }
                  }
                },
                "requirements": {
                  "location": "signal_tower_ruins"
                },
                "constraints": {
                  "system_tags": [
                    "major_action",
                    "requires_full_attention"
                  ],
                  "exclusive_group": "research_window",
                  "window_ids": [
                    "白天",
                    "黄昏"
                  ],
                  "window_capacity": 1,
                  "commitment_axis": "research_focus",
                  "commitment_value": "signal_tower_ruins"
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
                "available_time_minutes": 405.0,
                "available_stamina": 55.0,
                "available_mental": 86.0,
                "actions": [
                  {
                    "type": "TRAVEL",
                    "target": "signal_tower_ruins",
                    "time_minutes": 45.0,
                    "stamina_cost": 8.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 8
          }
        }
      },
      "state_turn": 8
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
    "type": "ATTRIBUTES_ALLOCATED",
    "actor": "player",
    "target": "player",
    "data": {
      "action": {
        "action_id": "attr_day1_spirit4",
        "type": "ATTRIBUTE_ALLOCATION"
      },
      "action_ledger": {
        "available_time_minutes": 405.0,
        "available_stamina": 55.0,
        "available_mental": 86.0,
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
          "spirit": 4
        },
        "points_before": 4,
        "points_spent": 4,
        "points_after": 0
      },
      "attribute_allocations": {
        "spirit": 4
      },
      "player_delta": {
        "attributes": {
          "spirit": 4
        },
        "free_points": -4
      },
      "time_cost": 0.0,
      "proposed_events": [
        {
          "type": "ATTRIBUTES_ALLOCATED",
          "target": "player",
          "allocations": {
            "spirit": 4
          }
        }
      ]
    },
    "turn": 9,
    "timestamp": "Day 1 白天"
  }
]
```
---
## Turn 9 | Day 1 白天
```json
[
  {
    "event_id": "evt_0009_options_32d3b87e",
    "type": "OPTIONS_PRESENTED",
    "actor": "system",
    "target": null,
    "data": {
      "pending_options": {
        "version": 1,
        "state_turn": 9,
        "options": {
          "A": {
            "id": "A",
            "label": "rust_station",
            "description": "rust_station",
            "action": {
              "action_id": "auto-rust_station",
              "type": "EXPLORATION",
              "target": "rust_station",
              "goal": "rust_station"
            },
            "preview": {
              "legal": true,
              "errors": [],
              "resolution": {
                "formula_version": "1.0",
                "action_id": "auto-rust_station",
                "advantage_components": {
                  "ability_match": 10.0,
                  "equipment_advantage": 0.0,
                  "preparation": 3.0,
                  "intelligence": 0.0,
                  "teammate_assistance": 0.0,
                  "environment_advantage": 0.0
                },
                "resistance_components": {
                  "target_difficulty": 14.0,
                  "environment_penalty": 3.0,
                  "injury": 0.0,
                  "fatigue": 9.0,
                  "time_pressure": 0.0,
                  "unknown_risk": 3.0
                },
                "advantage": 13.0,
                "resistance": 29.0,
                "K": 10.0,
                "probability": 0.167982,
                "random_roll": 0.400398,
                "severity": 0.0,
                "severity_band": "成功区",
                "death_fairness": 0.3808,
                "outcome": "失败但获得部分信息",
                "death_allowed": false,
                "components": {
                  "severity": {
                    "difficulty": 2.8,
                    "injury": 0.0,
                    "resource_shortage": 0.0,
                    "information_missing": 2.0,
                    "time_pressure": 0.0,
                    "continuous_errors": 0.0,
                    "preparation": 3.0,
                    "ability_match": 10.0,
                    "teammate_support": 0.0,
                    "survival_assets": 0.0
                  },
                  "death_fairness_inputs": {
                    "risk_warning": 0.7,
                    "causal_chain": 0.85,
                    "avoidable": 0.8,
                    "rule_consistency": 1.0,
                    "player_responsibility": 0.8
                  },
                  "outcome_thresholds": {
                    "critical": 0.013439,
                    "normal": 0.131026,
                    "costly": 0.167982,
                    "partial_failure": 0.667193,
                    "severe_failure": 0.958399
                  }
                }
              },
              "target_profile": {
                "id": "rust_station",
                "location_id": "rust_station",
                "action_type": "EXPLORATION",
                "primary_attribute": "agility",
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
                      "rust_station"
                    ],
                    "resource_changes": {
                      "净水": 3
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  },
                  "partial_failure": {
                    "resource_changes": {
                      "净水": 1
                    },
                    "knowledge_additions": [
                      "rad_scorpion_behavior"
                    ]
                  }
                },
                "encounter_target_ids": [
                  "rad_scorpion"
                ],
                "requirements": {
                  "location": "rust_station"
                },
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
                  "commitment_axis": "route_commitment",
                  "commitment_value": "rust_station",
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
                  }
                }
              },
              "system_constraints": {
                "tags": [
                  "major_action",
                  "requires_full_attention"
                ],
                "commitments": [
                  [
                    "route_commitment",
                    "rust_station"
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
              "action_ledger": {
                "available_time_minutes": 405.0,
                "available_stamina": 55.0,
                "available_mental": 86.0,
                "actions": [
                  {
                    "type": "EXPLORATION",
                    "target": "rust_station",
                    "time_minutes": 120.0,
                    "stamina_cost": 15.0,
                    "mental_cost": 10.0,
                    "tags": [
                      "major_action",
                      "requires_full_attention"
                    ]
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 9
          },
          "B": {
            "id": "B",
            "label": "返回基地",
            "description": "",
            "action": {
              "action_id": "auto-return",
              "type": "RETURN_TO_BASE"
            },
            "preview": {
              "legal": true,
              "errors": [],
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
              "target_profile": {},
              "system_constraints": {
                "tags": [],
                "commitments": [],
                "windows": [],
                "allowed_periods": [],
                "npc_unavailable": false
              },
              "action_ledger": {
                "available_time_minutes": 405.0,
                "available_stamina": 55.0,
                "available_mental": 86.0,
                "actions": [
                  {
                    "type": "RETURN_TO_BASE",
                    "target": null,
                    "time_minutes": 30.0,
                    "stamina_cost": 5.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 9
          },
          "C": {
            "id": "C",
            "label": "前往信号塔废墟",
            "description": "",
            "action": {
              "action_id": "auto-travel-signal_tower_ruins",
              "type": "TRAVEL",
              "target": "signal_tower_ruins"
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
                "time_cost": 45.0,
                "stamina_cost": 8.0,
                "mental_cost": 0.0
              },
              "target_profile": {
                "id": "signal_tower_ruins",
                "location_id": "signal_tower_ruins",
                "action_type": "RESEARCH",
                "primary_attribute": "spirit",
                "target_difficulty": 20,
                "environment_penalty": 5,
                "unknown_risk": 10,
                "risk_warning": 0.8,
                "causal_chain": 0.85,
                "avoidable": 0.7,
                "rule_consistency": 1.0,
                "player_responsibility": 0.8,
                "effects": {
                  "success": {
                    "knowledge_additions": [
                      "signal_tower_ruins_principle"
                    ],
                    "resource_changes": {
                      "燃料棒": 2
                    }
                  }
                },
                "requirements": {
                  "location": "signal_tower_ruins"
                },
                "constraints": {
                  "system_tags": [
                    "major_action",
                    "requires_full_attention"
                  ],
                  "exclusive_group": "research_window",
                  "window_ids": [
                    "白天",
                    "黄昏"
                  ],
                  "window_capacity": 1,
                  "commitment_axis": "research_focus",
                  "commitment_value": "signal_tower_ruins"
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
                "available_time_minutes": 405.0,
                "available_stamina": 55.0,
                "available_mental": 86.0,
                "actions": [
                  {
                    "type": "TRAVEL",
                    "target": "signal_tower_ruins",
                    "time_minutes": 45.0,
                    "stamina_cost": 8.0,
                    "mental_cost": 0.0,
                    "tags": []
                  }
                ]
              },
              "skill": null
            },
            "state_turn": 9
          }
        }
      },
      "state_turn": 9
    },
    "turn": 9,
    "timestamp": "Day 1 白天"
  }
]
```
