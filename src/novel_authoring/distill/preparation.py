"""Deterministic source preparation for the upstream ``distill-novels`` skill.

This module deliberately stops at normalized text, chapter boundaries and
auditable metadata. Semantic interpretation remains a Codex desktop handoff.
"""

from __future__ import annotations

import html
import re
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from novel_authoring.utils import json_dumps, stable_id, utc_now

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".adoc",
    ".html",
    ".htm",
    ".rtf",
    ".epub",
    ".docx",
}
CHAPTER_RE = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:chapter\s+(?:\d+|[ivxlcdm]+)|"
    r"第[零〇一二三四五六七八九十百千万两\d]+[章节回卷部篇]|序章|楔子|"
    r"尾声|终章)(?:\b|\s*)[^\n]*"
)


class DistillPreparationError(ValueError):
    """Raised when a source cannot be prepared deterministically."""


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "big5", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _strip_markup(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", "\n", value)
    return html.unescape(value)


def _extract_docx(path: Path) -> str:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        paragraphs.append(
            "".join(
                node.text or ""
                for node in paragraph.iter(f"{namespace}t")
            )
        )
    return "\n".join(paragraphs)


def _extract_epub(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            name
            for name in archive.namelist()
            if name.lower().endswith((".xhtml", ".html", ".htm"))
        )
        return "\n\n".join(
            _strip_markup(archive.read(name).decode("utf-8", errors="replace"))
            for name in names
        )


def extract_source(path: Path) -> str:
    """Extract one supported source into normalized UTF-8 text."""

    suffix = path.suffix.lower()
    if suffix == ".docx":
        value = _extract_docx(path)
    elif suffix == ".epub":
        value = _extract_epub(path)
    else:
        value = _read_text(path)
        if suffix in {".html", ".htm"}:
            value = _strip_markup(value)
        elif suffix == ".rtf":
            value = re.sub(r"\\'[0-9a-fA-F]{2}|\\[a-zA-Z]+-?\d* ?|[{}]", "", value)
    return value.replace("\r\n", "\n").replace("\r", "\n")


def discover_sources(inputs: Iterable[Path]) -> list[Path]:
    """Resolve files and directories without following symlinks."""

    found: set[Path] = set()
    for raw in inputs:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise DistillPreparationError(f"来源不存在：{path}")
        if path.is_symlink():
            raise DistillPreparationError(f"来源不能是 symlink/reparse point：{path}")
        if path.is_file():
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise DistillPreparationError(f"不支持的来源格式：{path.suffix or path.name}")
            found.add(path)
            continue
        if not path.is_dir():
            raise DistillPreparationError(f"来源不是文件或目录：{path}")
        for candidate in path.rglob("*"):
            if (
                candidate.is_file()
                and not candidate.is_symlink()
                and candidate.suffix.lower() in SUPPORTED_EXTENSIONS
            ):
                found.add(candidate.resolve())
    if not found:
        raise DistillPreparationError("没有发现可处理的 TXT/Markdown/HTML/EPUB/DOCX/RTF 来源")
    return sorted(found, key=lambda item: item.as_posix().casefold())


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _segments(text: str) -> list[dict[str, Any]]:
    matches = list(CHAPTER_RE.finditer(text))
    if not matches:
        if not text.strip():
            return []
        return [
            {
                "segment_id": "segment-0001",
                "ordinal": 1,
                "heading": "全文",
                "start_line": 1,
                "end_line": max(1, len(text.splitlines())),
                "start_char": 0,
                "end_char": len(text),
                "char_count": len(text),
            }
        ]
    total_lines = max(1, len(text.splitlines()))
    result: list[dict[str, Any]] = []
    for index, match in enumerate(matches, start=1):
        start = match.start()
        end = matches[index].start() if index < len(matches) else len(text)
        result.append(
            {
                "segment_id": f"segment-{index:04d}",
                "ordinal": index,
                "heading": match.group(0).strip(),
                "start_line": _line_number(text, start),
                "end_line": total_lines if index == len(matches) else _line_number(text, end) - 1,
                "start_char": start,
                "end_char": end,
                "char_count": end - start,
            }
        )
    return result


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def prepare_sources(
    inputs: Iterable[Path],
    output_root: Path,
    *,
    preparation_id: str | None = None,
) -> dict[str, Any]:
    """Create normalized source files and bounded segment indexes.

    The output is an input package for ``$distill-novels``. It is never a
    Canon artifact and does not contain semantic claims.
    """

    sources = discover_sources(inputs)
    root = Path(output_root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise DistillPreparationError(f"准备目录已有内容，拒绝覆盖：{root}")
    root.mkdir(parents=True, exist_ok=True)
    normalized_root = root / "normalized"
    index_root = root / "index"
    normalized_root.mkdir()
    index_root.mkdir()

    manifest_sources: list[dict[str, Any]] = []
    index_sources: list[dict[str, Any]] = []
    warnings: list[str] = []
    for position, source in enumerate(sources, start=1):
        text = extract_source(source)
        source_id = f"book-{position:02d}-{stable_id('distill-source', text)[-8:]}"
        segments = _segments(text)
        if len(segments) < 3:
            warnings.append(f"{source_id}: 可识别段落少于三个，章节级分析证据较弱")
        normalized_path = normalized_root / f"{source_id}.txt"
        normalized_path.write_text(text, encoding="utf-8", newline="\n")
        source_index = {
            "source_id": source_id,
            "filename": source.name,
            "format": source.suffix.lower(),
            "input_path": str(source),
            "normalized_path": str(normalized_path),
            "characters": len(text),
            "lines": len(text.splitlines()),
            "segment_count": len(segments),
            "chapter_detection_confidence": "high" if len(segments) >= 3 else "low",
            "segments": segments,
        }
        _write_json(index_root / f"{source_id}.json", source_index)
        manifest_sources.append(
            {
                key: source_index[key]
                for key in (
                    "source_id",
                    "filename",
                    "format",
                    "input_path",
                    "normalized_path",
                    "characters",
                    "lines",
                    "segment_count",
                    "chapter_detection_confidence",
                )
            }
        )
        index_sources.append(source_index)

    manifest = {
        "schema_version": "distill-preparation-v1",
        "preparation_id": preparation_id
        or stable_id("distill-prep", *(item["source_id"] for item in manifest_sources)),
        "created_at": utc_now(),
        "sources": manifest_sources,
        "warnings": warnings,
        "source_scope": "EXTERNAL_OR_REFERENCE_INPUT",
    }
    _write_json(root / "manifest.json", manifest)
    _write_json(
        root / "chapter_index.json",
        {
            "schema_version": "distill-chapter-index-v1",
            "preparation_id": manifest["preparation_id"],
            "sources": index_sources,
        },
    )
    _write_json(
        root / "statistics.json",
        {
            "source_count": len(manifest_sources),
            "segment_count": sum(item["segment_count"] for item in manifest_sources),
            "character_count": sum(item["characters"] for item in manifest_sources),
            "line_count": sum(item["lines"] for item in manifest_sources),
            "warnings": warnings,
        },
    )
    return {
        "preparation_id": manifest["preparation_id"],
        "root": str(root),
        "manifest": str(root / "manifest.json"),
        "chapter_index": str(root / "chapter_index.json"),
        "source_ids": [item["source_id"] for item in manifest_sources],
        "source_count": len(manifest_sources),
        "segment_count": sum(item["segment_count"] for item in manifest_sources),
        "warnings": warnings,
    }
