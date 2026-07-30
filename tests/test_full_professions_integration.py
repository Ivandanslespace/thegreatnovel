#!/usr/bin/env python3
"""职业系统端到端测试：创建存档后，职业必须进入世界与初始 NPC。"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import yaml


PROJECT_DIR = Path(__file__).parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def creative_answers() -> dict:
    """复用完整 LLM 世界包，再替换为本测试专属职业。"""
    from test_engine_runtime import creative_world_package

    package = creative_world_package("ProfessionsTestWorld")
    world = package["world"]
    profession = {
        "id": "tide_singer",
        "name": "潮歌译员",
        "description": "将潮汐留下的节律译为可航行的短句。",
        "attribute_focus": "spirit",
        "exclusive_actions": [{"action_type": "TRANSLATE_TIDE", "name": "翻译潮歌", "location_id": "camp_core"}],
    }
    world["professions"] = {"tide_singer": profession}
    world["starting_profession"] = "tide_singer"
    world["world_blueprint"]["npcs"][0]["profession"] = "tide_singer"
    world["world_blueprint"]["action_targets"][-1] = {
        "id": "profession:tide_singer:TRANSLATE_TIDE",
        "name": "翻译潮歌",
        "action_type": "PROFESSION_ACTION",
        "location_id": "camp_core",
        "primary_attribute": "spirit",
        "target_difficulty": 15,
        "time_minutes": 29,
        "stamina_cost": 1,
        "mental_cost": 3,
        "effects": {"success": {"knowledge_additions": ["profession:tide_singer:TRANSLATE_TIDE:completed"]}},
        "requirements": {"profession": "tide_singer", "location": "camp_core", "knowledge_absent": ["profession:tide_singer:TRANSLATE_TIDE:completed"]},
        "constraints": {"system_tags": ["short_action"]},
    }
    return package

    # 以下是迁移前的独立样例，保留在历史 diff 中不会执行；完整包由上方统一提供。

def test_professions_in_npc() -> bool:
    """创建隔离存档，检查职业注册和 NPC 分配两个投影出口。"""
    from tools.create_save import create_save

    with tempfile.TemporaryDirectory(prefix="great_novel_professions_") as temp_dir:
        temp_root = Path(temp_dir)
        answers_yaml = temp_root / "answers.yaml"
        answers = creative_answers()
        answers_yaml.write_text(yaml.safe_dump(answers, allow_unicode=True, sort_keys=False), encoding="utf-8")
        result_path = create_save(argparse.Namespace(
            answers=str(answers_yaml),
            interactive=False,
            world_name=None,
            save_root=str(temp_root / "saves"),
        ))

        world_data = yaml.safe_load((result_path / "world.yaml").read_text(encoding="utf-8")) or {}
        professions = world_data.get("world", {}).get("professions", {})
        if "tide_singer" not in professions:
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
        if npcs[0]["profession"] != "tide_singer":
            print("初始 NPC 职业没有遵循世界蓝图")
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
