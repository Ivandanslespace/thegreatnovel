from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CHAPTER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:chapter\s+(?:\d+|[ivxlcdm]+)|"
    r"第[零〇一二三四五六七八九十百千万两\d]+[章节回卷部篇]|序章|楔子|尾声|终章)"
    r"(?:\b|\s*)[^\n]*$",
    re.IGNORECASE,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    lines = args.source.read_text(encoding="utf-8").splitlines()
    headings = [
        (index + 1, line.strip())
        for index, line in enumerate(lines)
        if CHAPTER_RE.match(line)
    ]

    segments = []
    for index, (start_line, heading) in enumerate(headings):
        end_line = headings[index + 1][0] - 1 if index + 1 < len(headings) else len(lines)
        nonempty = sum(1 for line in lines[start_line - 1 : end_line] if line.strip())
        characters = sum(len(line) for line in lines[start_line - 1 : end_line])
        segments.append(
            {
                "segment_id": f"segment-{index + 1:04d}",
                "heading": heading,
                "line_start": start_line,
                "line_end": end_line,
                "nonempty_lines": nonempty,
                "characters": characters,
            }
        )

    payload = {
        "source": str(args.source),
        "total_lines": len(lines),
        "detected_segments": len(segments),
        "segments": segments,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "chapter_index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    markdown = [
        "# 章节索引",
        "",
        f"- 来源：`{args.source}`",
        f"- 总行数：{len(lines)}",
        f"- 检测片段：{len(segments)}",
        "",
        "| 片段 | 行号 | 字符数 | 标题 |",
        "|---|---:|---:|---|",
    ]
    markdown.extend(
        f"| `{item['segment_id']}` | {item['line_start']}-{item['line_end']} | "
        f"{item['characters']} | {item['heading'].replace('|', '\\|')} |"
        for item in segments
    )
    (args.output / "chapter_index.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )

    print(json.dumps({"total_lines": len(lines), "segments": len(segments)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
