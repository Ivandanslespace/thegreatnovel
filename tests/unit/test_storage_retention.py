from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from novel_authoring.storage.cleanup import (
    CleanupBlockedError,
    CleanupCandidate,
    CleanupCategory,
    CleanupConfirmationError,
    apply_cleanup,
    plan_cleanup,
)
from novel_authoring.storage.retention import RetentionConfig, plan_retention


def _write_export(root: Path, name: str, created_at: str) -> Path:
    export = root / name
    export.mkdir(parents=True)
    (export / "manifest.json").write_text(
        json.dumps({"export_id": name, "created_at": created_at}), encoding="utf-8"
    )
    (export / "index.html").write_text(name, encoding="utf-8")
    return export


def _exports_root(tmp_path: Path) -> Path:
    return tmp_path / "library" / "book-a" / "editions" / "base" / "exports"


def test_retention_is_dry_run_json_serializable_and_archives_old_normal_export(
    tmp_path: Path,
) -> None:
    exports = _exports_root(tmp_path)
    for index in range(4):
        _write_export(exports, f"export-{index}", f"2026-08-04T00:0{index}:00+00:00")
    (exports / "latest").mkdir()
    (exports / "archive" / "old-export").mkdir(parents=True)

    report = plan_retention(tmp_path / "library")

    assert report["mode"] == "DRY_RUN"
    assert report["retention"] == {
        "normal_portable_exports": 3,
        "archive_auto_delete": False,
    }
    assert report["summary"]["eligible_count"] == 1
    assert report["summary"]["retained_count"] == 3
    assert all("archive" not in str(item["path"]) for item in report["candidates"])
    assert json.loads(json.dumps(report))["candidate_hash"] == report.candidate_hash
    assert (exports / "export-0").is_dir()

    with pytest.raises(CleanupConfirmationError):
        apply_cleanup(report, "CLEANUP book-a wrong-hash")

    applied = apply_cleanup(report, report.confirmation or "")
    assert applied["status"] == "APPLIED"
    assert not (exports / "export-0").exists()
    archive_root = Path(str(applied["archive_root"]))
    assert (archive_root / "editions" / "base" / "exports" / "export-0").is_dir()
    assert (exports / "latest").is_dir()
    assert (exports / "archive" / "old-export").is_dir()


def test_cleanup_blocks_protected_categories_references_and_outside_paths(tmp_path: Path) -> None:
    library = tmp_path / "library"
    source_file = library / "book-a" / "source" / "novel.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("immutable", encoding="utf-8")
    generated = library / "book-a" / "editions" / "base" / "writing" / "generated.bin"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"generated")
    referenced = library / "book-a" / "editions" / "base" / "writing" / "referenced.bin"
    referenced.write_bytes(b"referenced")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")

    report = plan_cleanup(
        library,
        candidates=[
            CleanupCandidate(source_file, CleanupCategory.REGENERABLE),
            CleanupCandidate(generated, CleanupCategory.USER_DATA),
            CleanupCandidate(referenced, CleanupCategory.REGENERABLE),
            CleanupCandidate(outside, CleanupCategory.ARCHIVE),
        ],
        book_id="book-a",
        reference_checker=lambda path: ["state.sqlite3:path"]
        if path == referenced.resolve()
        else [],
    )

    assert report["summary"]["eligible_count"] == 0
    reasons = [reason for item in report["candidates"] for reason in item["block_reasons"]]
    assert "canon_source_database_or_atlas_is_immutable" in reasons
    assert any(reason.startswith("category_not_allowed") for reason in reasons)
    assert "path_referenced" in reasons
    assert "path_outside_library_root" in reasons
    with pytest.raises(CleanupBlockedError):
        apply_cleanup(report, report.confirmation or "")


def test_default_reference_checker_blocks_sqlite_path_reference(tmp_path: Path) -> None:
    library = tmp_path / "library"
    candidate = library / "book-a" / "editions" / "base" / "writing" / "referenced.bin"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"referenced")
    database = library / "book-a" / "_system" / "state.sqlite3"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE references_(path TEXT)")
        connection.execute("INSERT INTO references_(path) VALUES (?)", (str(candidate),))
        connection.commit()

    report = plan_cleanup(
        library,
        candidates=[CleanupCandidate(candidate, CleanupCategory.REGENERABLE)],
        book_id="book-a",
    )

    assert report["summary"]["eligible_count"] == 0
    assert report["summary"]["referenced_count"] == 1
    assert "path_referenced" in report["candidates"][0]["block_reasons"]


def test_cleanup_rejects_symlink_target_when_platform_allows_symlinks(tmp_path: Path) -> None:
    library = tmp_path / "library"
    book_root = library / "book-a" / "editions" / "base" / "writing"
    book_root.mkdir(parents=True)
    real = tmp_path / "real.bin"
    real.write_bytes(b"real")
    link = book_root / "link.bin"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("当前 Windows 环境不允许创建 symlink")

    report = plan_cleanup(
        library,
        candidates=[CleanupCandidate(link, CleanupCategory.REGENERABLE)],
        book_id="book-a",
    )
    assert report["summary"]["eligible_count"] == 0
    assert any(
        reason == "symlink_or_reparse_point"
        for reason in report["candidates"][0]["block_reasons"]
    )


def test_retention_config_never_enables_archive_auto_delete() -> None:
    with pytest.raises(ValueError):
        RetentionConfig(archive_auto_delete=True)
