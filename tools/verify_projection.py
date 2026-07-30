#!/usr/bin/env python3
"""验证 SQLite 事件重放结果与最新状态快照一致。"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from engine_runtime.events import apply_event
from engine_runtime.persistence import SQLiteEventStore


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 TheGreatNovel SQLite 投影")
    parser.add_argument("campaign", help="存档目录或 campaign.sqlite3 路径")
    args = parser.parse_args()
    path = Path(args.campaign).resolve()
    db_path = path if path.suffix == ".sqlite3" else path / "campaign.sqlite3"
    store = SQLiteEventStore(db_path)
    result = store.verify_projection(apply_event)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
