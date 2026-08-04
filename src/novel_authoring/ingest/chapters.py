from __future__ import annotations

import re
from dataclasses import dataclass

from novel_authoring.domain.models import ChapterSlice


@dataclass(frozen=True)
class SplitResult:
    chapters: list[ChapterSlice]
    preamble: str
    preamble_end_line: int
    warnings: list[str]


def split_chapters(
    text: str,
    chapter_patterns: list[str],
    volume_patterns: list[str] | None = None,
) -> SplitResult:
    chapter_regexes = [re.compile(pattern) for pattern in chapter_patterns]
    volume_regexes = [re.compile(pattern) for pattern in (volume_patterns or [])]
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)

    headings: list[tuple[int, re.Match[str], str | None]] = []
    current_volume: str | None = None
    for index, line in enumerate(lines):
        candidate = line.rstrip("\r\n")
        volume_match = next(
            (match for regex in volume_regexes if (match := regex.match(candidate)) is not None),
            None,
        )
        if volume_match is not None:
            current_volume = (volume_match.groupdict().get("title") or candidate).strip()
        chapter_match = next(
            (match for regex in chapter_regexes if (match := regex.match(candidate)) is not None),
            None,
        )
        if chapter_match is not None:
            headings.append((index, chapter_match, current_volume))

    warnings: list[str] = []
    if not headings:
        warnings.append("未识别章节标题；整个文件作为单章导入")
        chapter = ChapterSlice(
            ordinal=1,
            raw_heading="",
            title="全文",
            start_line=1,
            end_line=max(1, len(lines)),
            start_char=0,
            end_char=len(text),
            text=text,
        )
        return SplitResult(chapters=[chapter], preamble="", preamble_end_line=0, warnings=warnings)

    preamble_end = offsets[headings[0][0]]
    preamble = text[:preamble_end]
    chapters: list[ChapterSlice] = []
    seen_labels: dict[str, int] = {}
    previous_number: int | None = None
    for ordinal, (line_index, match, volume_title) in enumerate(headings, start=1):
        next_line_index = headings[ordinal][0] if ordinal < len(headings) else len(lines)
        start_char = offsets[line_index]
        end_char = offsets[next_line_index] if next_line_index < len(offsets) else len(text)
        groups = match.groupdict()
        number = (groups.get("number") or "").strip() or None
        title = (groups.get("title") or "").strip()
        raw_heading = lines[line_index].rstrip("\r\n")
        if not title:
            title = raw_heading.lstrip("# ").strip()
        if number is not None:
            seen_labels[number] = seen_labels.get(number, 0) + 1
            if number.isascii() and number.isdigit():
                parsed = int(number)
                if previous_number is not None and parsed < previous_number:
                    warnings.append(f"第 {ordinal} 个章块编号从 {previous_number} 回退到 {parsed}")
                previous_number = parsed
        chapters.append(
            ChapterSlice(
                ordinal=ordinal,
                raw_heading=raw_heading,
                chapter_number_text=number,
                title=title,
                volume_title=volume_title,
                start_line=line_index + 1,
                end_line=max(line_index + 1, next_line_index),
                start_char=start_char,
                end_char=end_char,
                text=text[start_char:end_char],
            )
        )
    duplicates = sorted(label for label, count in seen_labels.items() if count > 1)
    if duplicates:
        warnings.append("检测到重复章号：" + ", ".join(duplicates))
    return SplitResult(
        chapters=chapters,
        preamble=preamble,
        preamble_end_line=headings[0][0],
        warnings=warnings,
    )
