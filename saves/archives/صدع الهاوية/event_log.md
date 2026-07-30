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
      "world_name": "صدع الهاوية",
      "theme": "صدع الهاوية",
      "safe_base": "围绕主题建立的移动避难所",
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
    "target": "الصدع من الداخل",
    "data": {
      "action": {
        "action_id": "observe-rift-001",
        "type": "EXPLORATION",
        "target": "الصدع من الداخل",
        "primary_attribute": "spirit"
      },
      "action_ledger": {
        "available_time_minutes": 240.0,
        "available_stamina": 100.0,
        "available_mental": 100.0,
        "actions": [
          {
            "type": "EXPLORATION",
            "target": "الصدع من الداخل",
            "time_minutes": 120.0,
            "stamina_cost": 15.0,
            "mental_cost": 10.0,
            "tags": [
              "observation"
            ]
          }
        ]
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "observe-rift-001",
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
        "random_roll": 0.092241,
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
    "target": "الصدع من الداخل",
    "data": {
      "action": {
        "action_id": "observe-rift-002",
        "type": "EXPLORATION",
        "target": "الصدع من الداخل",
        "primary_attribute": "spirit"
      },
      "action_ledger": {
        "available_time_minutes": 120.0,
        "available_stamina": 85.0,
        "available_mental": 90.0,
        "actions": [
          {
            "type": "EXPLORATION",
            "target": "الصدع من الداخل",
            "time_minutes": 120.0,
            "stamina_cost": 15.0,
            "mental_cost": 10.0,
            "tags": [
              "observation"
            ]
          }
        ]
      },
      "resolution": {
        "formula_version": "1.0",
        "action_id": "observe-rift-002",
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
          "fatigue": 3.0,
          "time_pressure": 3.0,
          "unknown_risk": 0.0
        },
        "advantage": 15.0,
        "resistance": 31.0,
        "K": 10.0,
        "probability": 0.167982,
        "random_roll": 0.956331,
        "severity": 0.0,
        "severity_band": "成功区",
        "death_fairness": 0.0,
        "outcome": "严重失败",
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
    "turn": 3,
    "timestamp": "Day 1 清晨"
  }
]
```
