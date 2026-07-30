#!/usr/bin/env python3
"""把一个已结算回合记录为可复制的小说稿和完整对话日志。"""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from engine_runtime.narrative_log import record_narrative_turn
from validate_save import assert_startable


def _value(inline: str | None, filename: str | None, label: str) -> str:
    if inline is not None and filename is not None:
        raise ValueError(f"{label}不能同时使用文本和文件参数")
    if filename is not None:
        return Path(filename).read_text(encoding="utf-8")
    if inline is not None:
        return inline
    raise ValueError(f"缺少{label}")


def main() -> int:
    parser = argparse.ArgumentParser(description="记录一回合小说正文和完整对话")
    parser.add_argument("save", help="存档目录")
    player = parser.add_mutually_exclusive_group(required=True)
    player.add_argument("--player-input", help="玩家原始输入")
    player.add_argument("--player-input-file", help="玩家原始输入文件")
    response = parser.add_mutually_exclusive_group(required=True)
    response.add_argument("--gm-response", help="GM完整回答")
    response.add_argument("--gm-response-file", help="GM完整回答文件")
    parser.add_argument("--intent-source", choices=("player_free_text", "player_choice", "llm_suggestion", "system"), default="system", help="开局或补录时的意图来源")
    args = parser.parse_args()

    try:
        save_dir = Path(args.save).resolve()
        if not save_dir.is_dir():
            raise ValueError(f"找不到存档目录：{save_dir}")
        assert_startable(str(save_dir))
        result = record_narrative_turn(
            save_dir,
            _value(args.player_input, args.player_input_file, "玩家原始输入"),
            _value(args.gm_response, args.gm_response_file, "GM完整回答"),
            intent_source=args.intent_source,
        )
        print(f"已记录第{result['turn']}回：{result['novel_path']}")
    except (OSError, ValueError) as exc:
        print(f"记录失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
