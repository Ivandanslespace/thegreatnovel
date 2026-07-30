#!/usr/bin/env python3
"""使用 Python 规则引擎预览或执行一次玩家行动。

示例：
    python tools/run_action.py saves/新世界 --action-json '{"action_id":"scout","type":"EXPLORATION","target":"冰原边缘","primary_attribute":"agility","risk_preference":"谨慎"}' --player-input '我去侦察。' --gm-response-file response.md
"""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from engine_runtime.audit import append_audit_record, build_rejected_audit
from engine_runtime.presentation import player_facing_result
from engine_runtime.runtime import GameEngine
from engine_runtime.narrative_log import record_narrative_turn
from engine_runtime.state import load_game_state
from validate_save import assert_startable


def snapshot_files(save_dir: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(save_dir): path.read_bytes()
        for path in save_dir.rglob("*")
        if path.is_file()
    }


def restore_files(save_dir: Path, snapshot: dict[Path, bytes]) -> None:
    current_files = [path for path in save_dir.rglob("*") if path.is_file()]
    for path in current_files:
        relative = path.relative_to(save_dir)
        if relative not in snapshot:
            path.unlink()
    for relative, content in snapshot.items():
        target = save_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="执行一次 TheGreatNovel Python 引擎行动")
    parser.add_argument("save", help="存档目录")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--action-json", help="行动 JSON")
    source.add_argument("--action-file", help="行动 JSON 文件")
    source.add_argument("--player-choice-option", help="直接执行已保存的玩家选项，例如 A")
    parser.add_argument("--dry-run", action="store_true", help="只计算，不写入事件和 YAML")
    player = parser.add_mutually_exclusive_group()
    player.add_argument("--player-input", help="玩家本轮原始输入（执行时必填）")
    player.add_argument("--player-input-file", help="玩家本轮原始输入文件（执行时必填）")
    response = parser.add_mutually_exclusive_group()
    response.add_argument("--gm-response", help="GM本轮完整回答（执行时必填）")
    response.add_argument("--gm-response-file", help="GM本轮完整回答文件（执行时必填）")
    parser.add_argument("--intent-source", choices=("player_free_text", "player_choice", "llm_suggestion", "system"), default="player_free_text", help="意图来源，用于审计归属")
    args = parser.parse_args()

    save_dir = None
    snapshot = None
    action = None
    player_input_text = ""
    preflight_ok = False
    try:
        if args.action_json:
            action = json.loads(args.action_json)
        elif args.action_file:
            action = json.loads(Path(args.action_file).read_text(encoding="utf-8"))
        if args.player_choice_option and args.dry_run and any((args.player_input, args.player_input_file, args.gm_response, args.gm_response_file)):
            raise ValueError("--dry-run 不记录小说；请不要同时提交玩家输入和GM回答")
        if action is not None and not isinstance(action, dict):
            raise ValueError("行动 JSON 顶层必须是对象")
        save_dir = Path(args.save).resolve()
        if not save_dir.is_dir():
            raise ValueError(f"找不到存档目录：{save_dir}")
        assert_startable(str(save_dir))
        preflight_ok = True
        engine = GameEngine(load_game_state(save_dir))
        if args.player_choice_option:
            choice_review = engine.preview_player_choice(args.player_choice_option)
            if not choice_review["legal"]:
                raise ValueError("选项不可执行：" + "、".join(choice_review["errors"]))
            action = choice_review["action"]
        if args.dry_run:
            if any((args.player_input, args.player_input_file, args.gm_response, args.gm_response_file)):
                raise ValueError("--dry-run 不记录小说；开发预览不能同时提交玩家输入和GM回答")
            result = engine.preview_player_choice(args.player_choice_option) if args.player_choice_option else engine.preview_host_action(action)
        else:
            if not (args.player_input or args.player_input_file):
                raise ValueError("执行时必须提供 --player-input 或 --player-input-file")
            if not (args.gm_response or args.gm_response_file):
                raise ValueError("执行时必须提供 --gm-response 或 --gm-response-file")
            snapshot = snapshot_files(save_dir)
            before_state = deepcopy(engine.state.data)
            result = engine.execute_player_choice(args.player_choice_option) if args.player_choice_option else engine.execute_host_action(action)
            player_input = Path(args.player_input_file).read_text(encoding="utf-8") if args.player_input_file else args.player_input
            gm_response = Path(args.gm_response_file).read_text(encoding="utf-8") if args.gm_response_file else args.gm_response
            player_input_text = player_input or ""
            record_narrative_turn(save_dir, player_input, gm_response, action=action, before_state=before_state, result=result, intent_source=args.intent_source)
            try:
                assert_startable(str(save_dir))
            except ValueError:
                restore_files(save_dir, snapshot)
                raise ValueError("执行后存档校验未通过，已恢复执行前状态")
        print(json.dumps(player_facing_result(result), ensure_ascii=False, indent=2, default=str))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if snapshot is not None and save_dir is not None:
            restore_files(save_dir, snapshot)
        elif preflight_ok and save_dir is not None and isinstance(action, dict):
            try:
                current_turn = load_game_state(save_dir).current_turn
                append_audit_record(
                    save_dir,
                    build_rejected_audit(
                        turn=current_turn,
                        player_input=player_input_text or (args.player_input or ""),
                        action=action,
                        error=str(exc),
                        stage="run_action",
                    ),
                )
            except (OSError, ValueError):
                pass
        print(f"行动失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
