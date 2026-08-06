from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
LOCATOR_BOUNDARY_RE = re.compile(
    r"(segment-\d{4})\s*(?:·|/)\s*(?:行|L|lines?)\s*(\d+)(?:-(?:L)?(\d+))?",
    re.I,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("index", type=Path)
    parser.add_argument("--source-id", required=True)
    args = parser.parse_args()

    errors: list[str] = []
    markdown_files = sorted(args.skill.rglob("*.md"))
    relative_files = {
        str(path.relative_to(args.skill)).replace("\\", "/")
        for path in markdown_files
    }
    required = {
        "SKILL.md",
        "sources.md",
        "synthesis.md",
        "craft-controls.md",
        "worldbuilding.md",
        "characters.md",
        "plot.md",
        "style.md",
        "narrative.md",
        "dialogue.md",
        "pacing.md",
        "themes.md",
        "continuity.md",
        f"books/{args.source_id}/overview.md",
    }
    missing = sorted(required - relative_files)
    if missing:
        errors.append("缺少文件: " + ", ".join(missing))

    chapter_files = list((args.skill / "books" / args.source_id / "chapters").glob("*.md"))
    if len(chapter_files) < 10:
        errors.append(f"代表性章节分析不足 10 个，当前 {len(chapter_files)} 个")

    source_text = args.source.read_text(encoding="utf-8")
    segments = json.loads(args.index.read_text(encoding="utf-8"))["segments"]
    segment_bounds = {
        segment["segment_id"]: (segment["line_start"], segment["line_end"])
        for segment in segments
    }
    source_specific = [
        args.skill / name
        for name in (
            "worldbuilding.md", "characters.md", "plot.md", "style.md",
            "narrative.md", "dialogue.md", "pacing.md", "themes.md", "continuity.md",
        )
        if (args.skill / name).exists()
    ]
    for path in source_specific:
        text = path.read_text(encoding="utf-8")
        locator_re = re.compile(
            re.escape(args.source_id) + r".*segment-\d{4}.*(?:行|lines?)\s*\d+", re.I
        )
        if not locator_re.search(text):
            errors.append(f"缺少 source_id + segment + 行号定位: {path.name}")

    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for match in LOCATOR_BOUNDARY_RE.finditer(text):
            segment_id = match.group(1)
            start = int(match.group(2))
            end = int(match.group(3) or match.group(2))
            segment_start, segment_end = segment_bounds[segment_id]
            if not segment_start <= start <= end <= segment_end:
                errors.append(
                    f"越界定位: {path.relative_to(args.skill)} -> "
                    f"{segment_id} 行 {start}-{end}，有效 {segment_start}-{segment_end}"
                )
        for link in LINK_RE.findall(text):
            if link.startswith(("http://", "https://", "#")):
                continue
            target = (path.parent / link.split("#", 1)[0]).resolve()
            if not target.exists():
                errors.append(f"断链: {path.relative_to(args.skill)} -> {link}")
        for line_number, line in enumerate(text.splitlines(), start=1):
            compact = re.sub(r"[`*_#>|\[\]()\s]", "", line)
            if len(compact) < 80:
                continue
            starts = {0, max(0, len(compact) // 2 - 30), max(0, len(compact) - 60)}
            if any(compact[start : start + 60] in source_text for start in starts):
                errors.append(f"疑似长段原文复用: {path.relative_to(args.skill)}:{line_number}")

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print(f"PASS: {len(markdown_files)} 个 Markdown，{len(chapter_files)} 个代表性章节分析")


if __name__ == "__main__":
    main()
