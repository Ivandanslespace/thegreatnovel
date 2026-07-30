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
    profession = {
        "id": "tide_singer",
        "name": "潮歌译员",
        "description": "将潮汐留下的节律译为可航行的短句。",
        "attribute_focus": "spirit",
        "exclusive_actions": [{"action_type": "TRANSLATE_TIDE", "name": "翻译潮歌", "location_id": "camp_core"}],
    }
    return {
        "world": {
            "name": "ProfessionsTestWorld",
            "theme": "会唱歌的海面吞没旧大陆",
            "difficulty": "标准",
            "narrative_length": 7,
            "language": "中文",
            "setting": {
                "safe_base": "漂在鲸油灯群里的潮汐邮亭",
                "external_dangers": ["倒灌的回声潮", "盗走声音的盐鸥"],
                "exploration_method": "听潮歌辨认短暂浮出的石阶，并在副歌结束前折返",
                "disaster_cycle": "每5天一次失声巨潮",
                "disaster_type": "失声巨潮",
            },
            "resources": {"primary": ["潮墨", "浮木音叉", "盐雾玻璃"]},
            "professions": {"tide_singer": profession},
            "motifs": ["潮歌", "被淹没的地址"],
            "taboo_domains": ["替亡者唱名"],
            "world_blueprint": {
                "opening_area": {"id": "refrain_steps", "name": "副歌石阶", "description": "海面仅在副歌时露出的台阶。", "danger_hint": "最后一个音被拖长时，台阶会翻向海底。"},
                "opening_enemy": {"id": "salt_gull", "name": "盐鸥", "description": "会啄走人声的白鸟。", "knowledge_hint": "它们不攻击沉默的人。"},
                "base_modules": [{"id": "tide_bell", "name": "潮铃架", "description": "记录潮歌的节拍。"}],
                "starter_kit": {"main_weapon": {"id": "tuning_hook", "name": "调音钩", "attack_type": "melee"}, "items": []},
                "starter_recipe": {"id": "salt_seal", "name": "盐蜡封", "description": "将一段声音封进玻璃。"},
                "starting_npc": {"id": "npc_mora", "name": "莫拉", "goal": "找回被潮水带走的名字。", "profession": "tide_singer"},
            },
        },
        "player_talent": {
            "name": "回声借名",
            "description": "可借用一段遗失声音的余响。",
            "type": "信息类",
            "trigger": "在潮水退去后聆听残留回声时",
            "effect": "得到一条不完整的过去线索。",
            "limitations": "每次借名都会使自己的声音变轻，不能用来直接判定真相。",
        },
    }


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
