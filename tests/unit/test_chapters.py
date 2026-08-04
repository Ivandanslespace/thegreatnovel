from __future__ import annotations

from novel_authoring.config import load_settings
from novel_authoring.ingest.chapters import split_chapters


def test_split_configured_chinese_headings_and_offsets() -> None:
    text = "书名\r\n## 第1章 开始\r\n甲。\r\n第 二 章 转折\r\n乙。\r\n"
    settings = load_settings()
    result = split_chapters(
        text,
        settings.ingest.chapter_patterns,
        settings.ingest.volume_patterns,
    )

    assert result.preamble == "书名\r\n"
    assert [chapter.chapter_number_text for chapter in result.chapters] == ["1", "二"]
    assert [chapter.ordinal for chapter in result.chapters] == [1, 2]
    assert result.chapters[0].start_line == 2
    assert text[result.chapters[0].start_char : result.chapters[0].end_char].startswith(
        "## 第1章"
    )


def test_duplicate_numbers_preserve_source_order_and_warn() -> None:
    text = "第1章 一\n正文\n第1章 二\n正文\n"
    settings = load_settings()
    result = split_chapters(text, settings.ingest.chapter_patterns)

    assert len(result.chapters) == 2
    assert [chapter.title for chapter in result.chapters] == ["一", "二"]
    assert any("重复章号" in warning for warning in result.warnings)

