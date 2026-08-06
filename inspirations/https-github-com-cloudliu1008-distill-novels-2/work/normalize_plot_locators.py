from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


LOCATOR_RE = re.compile(
    r"\[book-01-bcc78727 / (segment-\d{4}) / L(\d+)(?:-L?(\d+))?\]"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("index", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    segments = json.loads(args.index.read_text(encoding="utf-8"))["segments"]
    by_id = {segment["segment_id"]: segment for segment in segments}
    corrected = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal corrected
        segment_id = match.group(1)
        start = int(match.group(2))
        end = int(match.group(3) or match.group(2))
        named = by_id[segment_id]
        if named["line_start"] <= start <= end <= named["line_end"]:
            return match.group(0)

        intersecting = [
            segment
            for segment in segments
            if segment["line_start"] <= end and segment["line_end"] >= start
        ]
        if not intersecting:
            return match.group(0)

        corrected += 1
        locators = []
        for segment in intersecting:
            clipped_start = max(start, segment["line_start"])
            clipped_end = min(end, segment["line_end"])
            locators.append(
                f"[book-01-bcc78727 / {segment['segment_id']} / "
                f"L{clipped_start}-L{clipped_end}]"
            )
        return " ".join(locators)

    normalized = LOCATOR_RE.sub(replace, args.report.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(normalized, encoding="utf-8")
    print(json.dumps({"corrected_locator_ranges": corrected}, ensure_ascii=False))


if __name__ == "__main__":
    main()
