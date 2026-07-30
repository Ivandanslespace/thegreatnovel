#!/usr/bin/env python3
"""读取决策审计 JSONL，生成可读的流程审计报告。"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_records(save_dir: Path) -> List[Dict[str, Any]]:
    path = save_dir / "decision_audit.jsonl"
    if not path.exists():
        raise ValueError(f"找不到审计日志：{path}")
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"审计日志第{line_number}行无法解析：{exc.msg}") from exc
        if isinstance(value, dict):
            records.append(value)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="查看TheGreatNovel逐回合决策审计")
    parser.add_argument("save", help="存档目录")
    parser.add_argument("--turn", type=int, help="只看指定回合")
    parser.add_argument("--status", choices=("EXECUTED", "REJECTED"), help="只看执行或拒绝记录")
    parser.add_argument("--field", help="只看影响指定数据库字段的记录，例如 player.fatigue")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出筛选后的JSON")
    args = parser.parse_args()

    try:
        records = load_records(Path(args.save).resolve())
        if args.turn is not None:
            records = [record for record in records if int(record.get("turn", -1)) == args.turn]
        if args.status:
            records = [record for record in records if record.get("status") == args.status]
        if args.field:
            records = [record for record in records if args.field in record.get("player_database_impact", {}).get("state_diff", {})]
        if args.as_json:
            print(json.dumps(records, ensure_ascii=False, indent=2))
            return 0

        executed = sum(1 for record in records if record.get("status") == "EXECUTED")
        rejected = sum(1 for record in records if record.get("status") == "REJECTED")
        print(f"审计记录：{len(records)}条（执行 {executed} / 拒绝 {rejected}）")
        for record in records:
            python = record.get("python", {})
            llm = record.get("llm", {})
            impact = record.get("player_database_impact", {}).get("state_diff", {})
            resolution = python.get("resolution", {}) if isinstance(python.get("resolution"), dict) else {}
            changed = ", ".join(list(impact)[:8]) or "无数据库变化"
            print(
                f"\nTurn {record.get('turn')} [{record.get('status')}] {record.get('event_id', '')}"
                f"\n玩家：{record.get('player', {}).get('raw_input', '')}"
                f"\nLLM意图：{json.dumps(llm.get('intent'), ensure_ascii=False)}"
                f"\nPython结果：{resolution.get('outcome', python.get('validation', {}).get('error', ''))}"
                f"\n数据库变化：{changed}"
            )
    except (OSError, ValueError) as exc:
        print(f"审计读取失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
