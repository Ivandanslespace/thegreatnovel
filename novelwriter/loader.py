"""loader.py —— 素材读取与切章（只读模块，绝不写入 inspirations/）。

职责：
- ``read_text``：编码探测（utf-8-sig 严格优先，失败回退 gb18030）。
- ``parse_frontmatter``：手写 YAML frontmatter 解析（不引 YAML 库），
  提取 chapter_count / title / book_id。
- ``build_chapter_index``：按文件类型切章，产出索引条目
  ``{no, title, offset, length}``（字符偏移）。
- ``read_chapter_text``：按索引条目读取指定章正文。

公式与阈值不在本模块，见 CONSTITUTION.md。
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# 编码探测
# ---------------------------------------------------------------------------


def read_text(path) -> tuple[str, str]:
    """读取文本文件，返回 (text, encoding)。

    先以 utf-8-sig 严格解码（容忍 BOM），失败回退 gb18030（兼容 gb2312/gbk）。
    两者均失败时抛出 ValueError。
    """
    p = Path(path)
    raw = p.read_bytes()
    try:
        return raw.decode("utf-8-sig", errors="strict"), "utf-8-sig"
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("gb18030", errors="strict"), "gb18030"
    except UnicodeDecodeError as exc:
        raise ValueError(f"无法识别文件编码: {p}") from exc


# ---------------------------------------------------------------------------
# 中文数字
# ---------------------------------------------------------------------------

_CN_DIGITS = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def chinese_numeral_to_int(s: str) -> int:
    """中文数字转阿拉伯数字（三百三十六 → 336）。

    支持零/两、十/百/千位、省略前导一的写法（十五 → 15）。
    解析失败抛 ValueError。
    """
    s = s.strip()
    if not s:
        raise ValueError("空字符串")
    if s.isdigit():
        return int(s)
    total, current = 0, 0
    for ch in s:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            total += (current if current else 1) * unit
            current = 0
        else:
            raise ValueError(f"无法解析中文数字: {s!r}")
    return total + current


# ---------------------------------------------------------------------------
# frontmatter
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> tuple[dict, int]:
    """解析文件开头的 YAML frontmatter，返回 (meta, body 起始偏移)。

    手写解析（不引 YAML 库）：仅支持扁平 ``key: value``，容忍空行；
    value 去除首尾引号；chapter_count / book_id 尽量转为 int。
    无 frontmatter 时返回 ({}, 0)。
    """
    if not text.startswith("---"):
        return {}, 0
    meta: dict = {}
    pos = 0
    first = True
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if first:
            first = False
            if stripped != "---":
                return {}, 0
        else:
            if stripped == "---":
                pos += len(line)
                return meta, pos
            if stripped and not stripped.startswith("#") and ":" in stripped:
                key, _, value = stripped.partition(":")
                value = value.strip().strip("\"'").strip()
                if key.strip() in ("chapter_count", "book_id"):
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        pass
                meta[key.strip()] = value
        pos += len(line)
    # 未闭合的 frontmatter 视为无效
    return {}, 0


# ---------------------------------------------------------------------------
# 切章
# ---------------------------------------------------------------------------

# md 章节头：## 第 N 章 标题（兼容中文数字与全角空格）；
# 容忍无「第」前缀的章头（如玄武第 86 章「## 八十六章 誰才是窮逼」）。
# 因要求「## + 数字 + 章」三者齐备，正文行不会误匹配。
_MD_HEADING_RE = re.compile(
    r"^##[ \t\u3000]*(?:第[ \t\u3000]*)?"
    r"([0-9一二三四五六七八九十百千零两]+)[ \t\u3000]*章(.*)$",
    re.M,
)
# txt 章节头：允许行首缩进（含全角空格），章/回/节；
# 允许同一行内先出现卷头再跟章节头（如“第五卷 星斗森林 第二十九章 xxx”）。
# 注意：txt 正则保留「第」为必需前缀——正文行可能出现无「第」的
# 「N章」字样，放宽会引入误匹配（斗罗大陆行为不得回归）。
_TXT_CHAPTER_RE = re.compile(
    r"(?:^|[ \t\u3000])第([0-9一二三四五六七八九十百千零两]+)[章回节](.*)$",
    re.M,
)

FALLBACK_WINDOW_CHARS = 3000


def build_chapter_index(path, text: str | None = None) -> dict:
    """切章并生成索引。

    返回 ``{entries, warning, frontmatter}``：
    - md：按 ``^## 第N章`` 切分；切出章数与 frontmatter chapter_count
      不一致时记入 warning（不阻断）。
    - txt：按 ``第X章/回/节`` 切分；章数 < 10 退化为约 3000 字定长窗口
      切块并给出警告标记。
    """
    path = Path(path)
    if text is None:
        text, _enc = read_text(path)
    suffix = path.suffix.lower()
    if suffix == ".md":
        return _split_markdown(text)
    if suffix == ".txt":
        return _split_text(text)
    raise ValueError(f"不支持的素材文件类型: {suffix}")


def _split_markdown(text: str) -> dict:
    meta, body_start = parse_frontmatter(text)
    matches = list(_MD_HEADING_RE.finditer(text, body_start))
    warning = None
    entries = []
    for i, m in enumerate(matches):
        try:
            no = chinese_numeral_to_int(m.group(1))
        except ValueError:
            no = i + 1
        title = m.group(2).strip()
        offset = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entries.append({"no": no, "title": title, "offset": offset,
                        "length": end - offset})
    expected = meta.get("chapter_count")
    if isinstance(expected, int) and expected > 0 and len(entries) != expected:
        warning = (f"切出 {len(entries)} 章，与 frontmatter "
                   f"chapter_count={expected} 不一致")
    return {"entries": entries, "warning": warning, "frontmatter": meta}


def _split_text(text: str) -> dict:
    matches = list(_TXT_CHAPTER_RE.finditer(text))
    parsed = []
    for m in matches:
        try:
            no = chinese_numeral_to_int(m.group(1))
        except ValueError:
            continue
        parsed.append((no, m))
    filtered = parsed
    # 汇总：同一章号被拆成（一）（二）…小节时并入前一章
    merged: list[tuple[int, str, int]] = []  # (no, title, start)
    for no, m in filtered:
        title = m.group(2).strip()
        if merged and no == merged[-1][0]:
            prev_no, prev_title, prev_start = merged[-1]
            if title:
                merged[-1] = (prev_no, f"{prev_title}（{title}）", prev_start)
        else:
            merged.append((no, title, m.start()))
    entries = []
    for i, (no, title, offset) in enumerate(merged):
        end = merged[i + 1][2] if i + 1 < len(merged) else len(text)
        entries.append({"no": no, "title": title, "offset": offset,
                        "length": end - offset})
    if len(entries) < 10:
        n_chapters = len(entries)
        entries = _fallback_windows(text)
        warning = (f"按章切分仅得 {n_chapters} 章，"
                   f"已退化为约 {FALLBACK_WINDOW_CHARS} 字定长窗口，"
                   f"共切出 {len(entries)} 块")
        return {"entries": entries, "warning": warning, "frontmatter": {}}
    return {"entries": entries, "warning": None, "frontmatter": {}}


def _fallback_windows(text: str, size: int = FALLBACK_WINDOW_CHARS) -> list[dict]:
    """定长窗口切块（优先在换行处断开），用于无章节头的长文本。"""
    entries = []
    pos, no = 0, 1
    n = len(text)
    while pos < n:
        end = min(pos + size, n)
        if end < n:
            nl = text.rfind("\n", pos, end)
            if nl > pos + size // 2:
                end = nl + 1
        entries.append({"no": no, "title": f"块{no:04d}",
                        "offset": pos, "length": end - pos})
        pos = end
        no += 1
    return entries


def read_chapter_text(path, entry: dict, text: str | None = None) -> str:
    """按索引条目读取指定章正文（按需读取，不常驻整文件）。"""
    if text is None:
        text, _enc = read_text(path)
    return text[entry["offset"]: entry["offset"] + entry["length"]]
