from __future__ import annotations

from novel_authoring.rhythm.features import (
    dice_similarity,
    excerpt_windows,
    normalize_title,
    prose_only,
    series_marker,
)


def test_title_normalization_and_series_marker() -> None:
    assert normalize_title("## 第１２章： 大战（一） ") == "大战(一)"
    assert series_marker("大战（一）") == "(一)"
    assert dice_similarity("暗门开启", "暗门开启") == 1
    assert dice_similarity("完全不同", "毫无关系") < 0.5


def test_excerpt_windows_use_three_paragraphs_and_prose_filter() -> None:
    text = (
        "系统提示：面板\n\n"
        "第一段。\n\n第二段。\n\n第三段。\n\n第四段。\n\n"
        "| 属性 | 数值 |\n| --- | --- |\n\n第五段。"
    )
    opening_raw, opening_prose, ending_raw, ending_prose = excerpt_windows(text, limit=300)
    assert opening_raw.startswith("系统提示")
    assert "第一段" in opening_prose and "第三段" in opening_prose
    assert "第四段" in ending_raw and "第五段" in ending_raw
    assert "系统提示" not in prose_only(text)
    assert "属性" not in ending_prose


def test_excerpt_limit_is_hard() -> None:
    text = "\n\n".join(["甲" * 200, "乙" * 200, "丙" * 200, "丁" * 200])
    windows = excerpt_windows(text, limit=300)
    assert all(len(value) <= 300 for value in windows)
