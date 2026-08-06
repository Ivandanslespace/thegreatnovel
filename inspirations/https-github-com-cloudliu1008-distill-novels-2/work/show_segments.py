from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("index", type=Path)
    parser.add_argument("segments", nargs="+")
    parser.add_argument("--max-lines", type=int, default=80)
    args = parser.parse_args()

    lines = args.source.read_text(encoding="utf-8").splitlines()
    payload = json.loads(args.index.read_text(encoding="utf-8"))
    by_id = {item["segment_id"]: item for item in payload["segments"]}

    for segment_id in args.segments:
        item = by_id[segment_id]
        print(f"\n## {segment_id}: {item['heading']} ({item['line_start']}-{item['line_end']})")
        selected = lines[item["line_start"] - 1 : item["line_end"]]
        if len(selected) > args.max_lines:
            head = args.max_lines // 2
            tail = args.max_lines - head
            ranges = [
                (item["line_start"], selected[:head]),
                (item["line_end"] - tail + 1, selected[-tail:]),
            ]
        else:
            ranges = [(item["line_start"], selected)]
        for start, chunk in ranges:
            for offset, line in enumerate(chunk):
                print(f"{start + offset}: {line}")
            if len(selected) > args.max_lines and start == item["line_start"]:
                print("...")


if __name__ == "__main__":
    main()
