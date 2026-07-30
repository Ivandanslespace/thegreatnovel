"""统一回合入口：一次调用完成执行、选项生成和叙事包输出。

用法：
    # 玩家选择了已展示的选项
    python tools/game_turn.py saves/世界名 --player-choice A \
      --player-input '我选A。' --gm-response-file response.md

    # 玩家自由输入（LLM已解析为行动JSON）
    python tools/game_turn.py saves/世界名 \
      --action-json '{"action_id":"scout","type":"EXPLORATION","target":"scrap_yard"}' \
      --player-input '我去探索废铁站场。' --gm-response-file response.md

    # 仅生成下一回合选项（不执行行动，用于开局或选项过期后）
    python tools/game_turn.py saves/世界名 --generate-options-only

输出：JSON NarrativePackage，包含 resolved_events、status_panel、
visible_options、scene_context。LLM 只需把这个包写成小说。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine_runtime.narrative_log import record_narrative_turn
from engine_runtime.presentation import player_facing_result
from engine_runtime.runtime import GameEngine
from engine_runtime.state import load_game_state
from tools.validate_save import assert_startable


def build_status_panel(engine: GameEngine) -> dict:
    """生成玩家可见的状态面板数据。"""
    player = engine.state.player
    meta = engine.state.meta
    attributes = player.get("attributes", {})
    return {
        "level": player.get("level", 1),
        "exp": player.get("exp", 0),
        "exp_to_next": player.get("exp_to_next", 100),
        "attributes": {
            "strength": attributes.get("strength", 0),
            "constitution": attributes.get("constitution", 0),
            "agility": attributes.get("agility", 0),
            "spirit": attributes.get("spirit", 0),
        },
        "hp": player.get("hp", 0),
        "max_hp": player.get("max_hp", 0),
        "fatigue": player.get("fatigue", 0),
        "mental": player.get("mental", 100),
        "status": player.get("status", "normal"),
        "game_day": meta.get("game_day", 1),
        "time_of_day": meta.get("time_of_day", "清晨"),
        "current_location": meta.get("current_location", ""),
        "available_time_minutes": meta.get("available_time_minutes", 720),
        "free_points": player.get("free_points", 0),
    }


def build_scene_context(engine: GameEngine) -> dict:
    """生成当前场景上下文，帮助LLM写叙述。"""
    meta = engine.state.meta
    world = engine.state.data.get("world", {})
    current_location = meta.get("current_location", "")
    locations = world.get("locations", []) if isinstance(world.get("locations", []), list) else []
    location_info = next((loc for loc in locations if isinstance(loc, dict) and loc.get("id") == current_location), {})
    npcs_here = [
        {"id": npc.get("id"), "name": npc.get("name"), "status": npc.get("status", "alive")}
        for npc in engine.state.data.get("npcs", [])
        if isinstance(npc, dict) and npc.get("location") == current_location and npc.get("status", "alive") == "alive"
    ]
    return {
        "location_id": current_location,
        "location_name": location_info.get("name", current_location),
        "location_safe": location_info.get("safe", False),
        "time_of_day": meta.get("time_of_day", "清晨"),
        "game_day": meta.get("game_day", 1),
        "npcs_present": npcs_here,
        "current_encounter_id": meta.get("current_encounter_id"),
        "pending_reaction": meta.get("pending_reaction"),
    }


def build_narrative_package(engine: GameEngine, execution_result: dict | None = None) -> dict:
    """组装完整的叙事包：LLM只需要把这个写成小说。"""
    package: dict = {
        "turn": engine.state.current_turn,
        "status_panel": build_status_panel(engine),
        "scene_context": build_scene_context(engine),
        "visible_options": {},
        "option_labels": {},
    }
    if execution_result:
        package["resolved"] = player_facing_result(execution_result)
    pending = engine.state.meta.get("pending_options", {})
    if isinstance(pending, dict) and pending.get("options"):
        for key, option in pending["options"].items():
            if isinstance(option, dict):
                package["visible_options"][key] = {
                    "label": option.get("label", ""),
                    "description": option.get("description", ""),
                }
                package["option_labels"][key] = option.get("label", "")
    return package


def main():
    parser = argparse.ArgumentParser(description="统一回合入口")
    parser.add_argument("save_dir", type=str, help="存档目录路径")
    parser.add_argument("--player-choice", type=str, help="玩家选择的选项字母（A/B/C）")
    parser.add_argument("--action-json", type=str, help="LLM解析的行动JSON（自由输入时使用）")
    parser.add_argument("--player-input", type=str, default="", help="玩家原始输入文本")
    parser.add_argument("--gm-response-file", type=str, help="GM回答文件路径（用于审计）")
    parser.add_argument("--generate-options-only", action="store_true", help="仅生成下一回合选项，不执行行动")
    parser.add_argument("--skip-narrative-log", action="store_true", help="跳过叙事日志记录")
    args = parser.parse_args()

    save_dir = Path(args.save_dir)
    if not save_dir.is_dir():
        print(json.dumps({"error": f"存档目录不存在：{save_dir}"}, ensure_ascii=False))
        sys.exit(1)

    assert_startable(save_dir)
    state = load_game_state(save_dir)
    engine = GameEngine(state)

    execution_result = None

    if args.generate_options_only:
        pass
    elif args.player_choice:
        execution_result = engine.execute_player_choice(args.player_choice.strip())
    elif args.action_json:
        action = json.loads(args.action_json)
        execution_result = engine.execute_host_action(action)
    else:
        print(json.dumps({"error": "必须提供 --player-choice、--action-json 或 --generate-options-only"}, ensure_ascii=False))
        sys.exit(1)

    if not args.skip_narrative_log and execution_result and args.player_input:
        gm_response = ""
        if args.gm_response_file:
            gm_path = Path(args.gm_response_file)
            if gm_path.is_file():
                gm_response = gm_path.read_text(encoding="utf-8")
        if gm_response:
            try:
                record_narrative_turn(
                    save_dir,
                    args.player_input,
                    gm_response,
                    action=execution_result.get("event", {}).get("data", {}).get("action"),
                    before_state=None,
                    result=execution_result,
                )
            except Exception:
                pass

    candidates = engine.generate_candidates()
    if candidates:
        try:
            engine.compile_options(candidates, persist=True)
        except ValueError:
            pass

    package = build_narrative_package(engine, execution_result)
    print(json.dumps(package, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
