#!/usr/bin/env python3
"""从 SQLite 事件源重放一个存档的当前投影。"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from engine_runtime.persistence import SQLiteEventStore
from engine_runtime.events import apply_event


def main() -> int:
    parser = argparse.ArgumentParser(description="从 SQLite 事件源重放 TheGreatNovel 存档")
    parser.add_argument("campaign", help="存档目录或 campaign.sqlite3 路径")
    args = parser.parse_args()
    path = Path(args.campaign).resolve()
    db_path = path if path.suffix == ".sqlite3" else path / "campaign.sqlite3"
    store = SQLiteEventStore(db_path)
    replayed = store.replay(apply_event)
    if replayed is None:
        print("找不到可重放的 campaign", file=sys.stderr)
        return 1
    print(json.dumps(replayed, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
