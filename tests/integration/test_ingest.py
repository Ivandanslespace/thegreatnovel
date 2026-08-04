from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from novel_authoring.config import load_settings
from novel_authoring.ingest.service import SourceAmbiguityError, ingest_book, scan_sources
from novel_authoring.utils import sha256_file

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def test_ingest_is_idempotent_traceable_and_source_immutable(tmp_path: Path) -> None:
    source_root = tmp_path / "中文源文件"
    source_root.mkdir()
    source = source_root / "合成小说.md"
    source.write_bytes(FIXTURE.read_bytes())
    before = sha256_file(source)
    workspace = tmp_path / "工作空间"
    settings = load_settings()

    first = ingest_book(
        book_id="synthetic-book",
        title="合成求生小说",
        source_root=source_root,
        workspace_root=workspace,
        settings=settings,
    )
    second = ingest_book(
        book_id="synthetic-book",
        title="合成求生小说",
        source_root=source_root,
        workspace_root=workspace,
        settings=settings,
    )

    assert first.documents_imported == 1
    assert first.chapters_imported == 3
    assert second.documents_imported == 0
    assert second.documents_unchanged == 1
    assert sha256_file(source) == before

    database_path = workspace / "synthetic-book" / "state.sqlite3"
    with sqlite3.connect(database_path) as connection:
        chapter_count = connection.execute("SELECT COUNT(*) FROM chapters").fetchone()[0]
        span_count = connection.execute(
            "SELECT COUNT(*) FROM source_spans WHERE chapter_id IS NOT NULL"
        ).fetchone()[0]
        trace = connection.execute(
            """
            SELECT d.relative_path, c.start_line, c.end_line, s.start_char, s.end_char
            FROM chapters c
            JOIN source_documents d ON d.document_id = c.document_id
            JOIN source_spans s ON s.chapter_id = c.chapter_id
            ORDER BY c.ordinal LIMIT 1
            """
        ).fetchone()
        fts_count = connection.execute(
            "SELECT COUNT(*) FROM chapter_fts WHERE chapter_fts MATCH '无线电'"
        ).fetchone()[0]
    assert chapter_count == 3
    assert span_count == 3
    assert trace is not None
    assert trace[0] == "合成小说.md"
    assert trace[1] > 0 and trace[2] >= trace[1]
    assert trace[4] > trace[3]
    assert fts_count == 1

    manifest = json.loads(
        (workspace / "synthetic-book" / "source_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["files"][0]["sha256"] == before


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "gb18030"])
def test_ingest_windows_chinese_path_and_encodings(tmp_path: Path, encoding: str) -> None:
    source_root = tmp_path / f"来源-{encoding}"
    source_root.mkdir()
    source = source_root / "短篇.txt"
    text = "第1章 起点\r\n中文正文。\r\n第2章 选择\r\n选择会留下后果。\r\n"
    source.write_bytes(text.encode(encoding))
    before = sha256_file(source)

    result = ingest_book(
        book_id=f"encoding-{encoding.replace('-', '')}",
        title="编码测试",
        source_root=source_root,
        workspace_root=tmp_path / "workspace",
        settings=load_settings(),
    )

    assert result.chapters_imported == 2
    assert sha256_file(source) == before


def test_multiple_sources_generate_manifest_and_block_unconfirmed_order(tmp_path: Path) -> None:
    source_root = tmp_path / "book"
    source_root.mkdir()
    (source_root / "第一部分.md").write_text("第1章 一\n正文", encoding="utf-8")
    (source_root / "第二部分.md").write_text("第2章 二\n正文", encoding="utf-8")
    workspace = tmp_path / "workspace"

    with pytest.raises(SourceAmbiguityError):
        ingest_book(
            book_id="ambiguous-book",
            title="多文件",
            source_root=source_root,
            workspace_root=workspace,
            settings=load_settings(),
        )

    manifest = scan_sources("ambiguous-book", source_root, load_settings())
    assert manifest.status == "needs_confirmation"
    assert manifest.confirmed is False
    assert len(manifest.files) == 2
    assert (workspace / "ambiguous-book" / "source_manifest.json").exists()
