#!/usr/bin/env python3
"""职业系统端到端测试：创建存档后，职业必须进入世界与初始 NPC。"""

from __future__ import annotations

import argparse
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

import yaml


PROJECT_DIR = Path(__file__).parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def test_professions_in_npc() -> bool:
    """创建隔离存档，检查职业注册和 NPC 分配两个投影出口。"""
    from engine_runtime.world_compiler import PROFESSION_REGISTRY
    from tools.create_save import create_save

    with tempfile.TemporaryDirectory(prefix="great_novel_professions_") as temp_dir:
        temp_root = Path(temp_dir)
        answers_yaml = temp_root / "answers.yaml"
        answers = {
            "world": {
                "name": "ProfessionsTestWorld",
                "theme": "废土列车",
                "difficulty": "标准",
                "narrative_length": 7,
                "language": "中文",
                "professions": {"mechanic": deepcopy(PROFESSION_REGISTRY["mechanic"])},
            }
        }
        answers_yaml.write_text(yaml.safe_dump(answers, allow_unicode=True, sort_keys=False), encoding="utf-8")
        result_path = create_save(argparse.Namespace(
            answers=str(answers_yaml),
            interactive=False,
            world_name=None,
            save_root=str(temp_root / "saves"),
        ))

        world_data = yaml.safe_load((result_path / "world.yaml").read_text(encoding="utf-8")) or {}
        professions = world_data.get("world", {}).get("professions", {})
        if "mechanic" not in professions:
            print("职业未写入 world.yaml")
            return False

        npc_data = yaml.safe_load((result_path / "npcs.yaml").read_text(encoding="utf-8")) or {}
        npcs = npc_data.get("npcs", [])
        if not npcs or not npcs[0].get("profession"):
            print("初始 NPC 未获得职业")
            return False
        from engine_runtime.state import load_game_state
        state = load_game_state(result_path)
        auxiliary_keys = {
            "region_state", "population_state", "public_system_state", "market_state",
            "ranking_state", "comparative_state", "rival_state",
        }
        if not auxiliary_keys.issubset(state.data):
            print("公共系统状态没有进入运行时快照")
            return False
        state.save()
        snapshot = state.store.latest_snapshot() or {}
        if not auxiliary_keys.issubset(snapshot):
            print("公共系统状态没有进入 SQLite 快照")
            return False
        print(f"职业已注册；初始 NPC 职业：{npcs[0]['profession']}")
        return True


if __name__ == "__main__":
    try:
        if not test_professions_in_npc():
            sys.exit(1)
        print("完整职业集成测试通过。")
    except Exception as exc:
        print(f"职业集成测试失败：{exc}")
        raise
