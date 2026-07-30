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
      "world_name": "巨兽的背脊",
      "theme": "巨兽的背脊",
      "safe_base": "巨兽背部的移动营地",
      "difficulty": "标准"
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
    "target": "巨兽背部的鳞沟",
    "data": {
      "action": {
        "action_id": "scout-001",
        "type": "EXPLORATION",
        "target": "巨兽背部的鳞沟",
        "primary_attribute": "agility"
      },
      "action_ledger": {
        "available_time_minutes": 240.0,
        "available_stamina": 100.0,
        "available_mental": 100.0,
        "actions": [
          {
            "type": "EXPLORATION",
            "target": "巨兽背部的鳞沟",
            "time_minutes": 120.0,
            "stamina_cost": 15.0,
            "mental_cost": 10.0,
            "tags": [
              "search"
            ]
          }
        ]
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "scout-001",
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
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 0.0,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 15.0,
        "resistance": 28.0,
        "K": 10.0,
        "probability": 0.214165,
        "random_roll": 0.703059,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "失败但获得部分信息",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 5.0,
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
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
          }
        }
      },
      "fatigue_delta": 15.0,
      "mental_delta": -10.0,
      "time_cost": 120.0,
      "hunger_delta": 0.0,
      "resource_changes": {}
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
    "target": "营地固定点",
    "data": {
      "action": {
        "action_id": "secure-001",
        "type": "SHORT_ACTION",
        "target": "营地固定点",
        "primary_attribute": "strength"
      },
      "action_ledger": {
        "available_time_minutes": 120.0,
        "available_stamina": 85.0,
        "available_mental": 90.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "营地固定点",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "defense"
            ]
          }
        ]
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "secure-001",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 10.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 3.0,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 15.0,
        "resistance": 16.0,
        "K": 10.0,
        "probability": 0.475021,
        "random_roll": 0.436461,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.0,
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
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
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
    "target": "巨兽脊骨震动",
    "data": {
      "action": {
        "action_id": "read-vibration-001",
        "type": "SHORT_ACTION",
        "target": "巨兽脊骨震动",
        "primary_attribute": "spirit"
      },
      "action_ledger": {
        "available_time_minutes": 90.0,
        "available_stamina": 83.0,
        "available_mental": 86.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "巨兽脊骨震动",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "observe",
              "talent"
            ]
          }
        ]
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "read-vibration-001",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 10.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 3.4,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 15.0,
        "resistance": 16.4,
        "K": 10.0,
        "probability": 0.465057,
        "random_roll": 0.259501,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.0,
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
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {}
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
    "target": "营地外侧连接点",
    "data": {
      "action": {
        "action_id": "secure-outer-001",
        "type": "SHORT_ACTION",
        "target": "营地外侧连接点",
        "primary_attribute": "strength"
      },
      "action_ledger": {
        "available_time_minutes": 60.0,
        "available_stamina": 81.0,
        "available_mental": 82.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "营地外侧连接点",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "defense",
              "repair"
            ]
          }
        ]
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "secure-outer-001",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 10.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 3.8,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 15.0,
        "resistance": 16.8,
        "K": 10.0,
        "probability": 0.455121,
        "random_roll": 0.006063,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.0,
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
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {}
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
    "target": "寄生兽经过的鳞沟",
    "data": {
      "action": {
        "action_id": "search-traces-001",
        "type": "SHORT_ACTION",
        "target": "寄生兽经过的鳞沟",
        "primary_attribute": "agility"
      },
      "action_ledger": {
        "available_time_minutes": 30.0,
        "available_stamina": 79.0,
        "available_mental": 78.0,
        "actions": [
          {
            "type": "SHORT_ACTION",
            "target": "寄生兽经过的鳞沟",
            "time_minutes": 30.0,
            "stamina_cost": 2.0,
            "mental_cost": 4.0,
            "tags": [
              "search",
              "scavenge"
            ]
          }
        ]
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "search-traces-001",
        "advantage_components": {
          "ability_match": 10.0,
          "equipment_advantage": 0.0,
          "preparation": 5.0,
          "intelligence": 0.0,
          "teammate_assistance": 0.0,
          "environment_advantage": 0.0
        },
        "resistance_components": {
          "target_difficulty": 10.0,
          "environment_penalty": 0.0,
          "injury": 0.0,
          "fatigue": 4.2,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 15.0,
        "resistance": 17.2,
        "K": 10.0,
        "probability": 0.445221,
        "random_roll": 0.376369,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "成功但付出代价",
        "death_allowed": false,
        "components": {
          "severity": {
            "difficulty": 2.0,
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
            "risk_warning": 0.0,
            "causal_chain": 0.0,
            "avoidable": 0.0,
            "rule_consistency": 0.0,
            "player_responsibility": 0.0
          }
        }
      },
      "fatigue_delta": 2.0,
      "mental_delta": -4.0,
      "time_cost": 30.0,
      "hunger_delta": 0.0,
      "resource_changes": {}
    },
    "turn": 6,
    "timestamp": "Day 1 清晨"
  }
]
```
