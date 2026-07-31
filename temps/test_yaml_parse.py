#!/usr/bin/env python3
"""快速测试 YAML 解析"""
import yaml
from pathlib import Path

path = Path("temps/punk_world.yaml")
with open(path, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

public_survival = data.get("world", {}).get("public_survival", {})
competition = public_survival.get("competition", {})
outcome_scores = competition.get("outcome_scores", {})

print(f"outcome_scores type: {type(outcome_scores)}")
print(f"outcome_scores value: {outcome_scores}")
print(f"Is dict: {isinstance(outcome_scores, dict)}")
