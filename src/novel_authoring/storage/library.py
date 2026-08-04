"""Book Library first import service."""

from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import IngestResult, ingest_book
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.manifest import verify_mirror, write_compatibility_mirror
from novel_authoring.storage.migration import _rewrite_database_paths
from novel_authoring.storage.models import BookPaths, LayoutError
from novel_authoring.storage.registry import BookRegistry
from novel_authoring.utils import json_dumps, safe_book_id, sha256_file, utc_now


@dataclass(frozen=True, slots=True)
class LibraryAddOptions:
    book_id: str
    source: Path
    title: str | None = None
    library_root: Path | None = None
    confirm_order: bool = False
    initialize_mode: str = "deferred"


@dataclass(slots=True)
class LibraryAddResult:
    book_id: str
    title: str
    root: Path
    source: Path
    database: Path
    source_manifest: Path
    readiness_status: str
    source_hashes_before: dict[str, str] = field(default_factory=dict)
    source_hashes_after: dict[str, str] = field(default_factory=dict)
    ingest: IngestResult | None = None
    fts_rows: int = 0
    initialize_mode: str = "deferred"

    def to_dict(self) -> dict[str, Any]:
        ingest = self.ingest
        return {
            "book_id": self.book_id,
            "title": self.title,
            "root": str(self.root),
            "source": str(self.source),
            "database": str(self.database),
            "source_manifest": str(self.source_manifest),
            "readiness_status": self.readiness_status,
            "source_hashes_before": self.source_hashes_before,
            "source_hashes_after": self.source_hashes_after,
            "documents_imported": 0 if ingest is None else ingest.documents_imported,
            "documents_unchanged": 0 if ingest is None else ingest.documents_unchanged,
            "chapters_imported": 0 if ingest is None else ingest.chapters_imported,
            "fts_rows": self.fts_rows,
            "initialize_mode": self.initialize_mode,
            "web": f"/library/{self.book_id}",
            "paths": f"/library/{self.book_id}/paths",
            "atlas": f"/books/{self.book_id}/editions/base/atlas",
            "metrics": f"/books/{self.book_id}/editions/base/metrics",
            "latest_export": f"/library/{self.book_id}/export/latest/",
        }


def add_book(options: LibraryAddOptions) -> LibraryAddResult:
    """Create a new canonical book atomically and ingest its source."""

    book_id = safe_book_id(options.book_id)
    initialize_mode = options.initialize_mode.strip().lower()
    if initialize_mode not in {"deferred", "prepare"}:
        raise LayoutError("initialize-mode 只能是 deferred 或 prepare")
    source = Path(options.source).expanduser().resolve()
    if not source.exists() or (not source.is_file() and not source.is_dir()):
        raise LayoutError(f"导入来源必须是文件或目录: {source}")
    if source.is_symlink():
        raise LayoutError(f"导入来源不能是 symlink/reparse point: {source}")

    layout = (
        BookLayout.default()
        if options.library_root is None
        else BookLayout(options.library_root)
    )
    paths = layout.for_book(book_id)
    if paths.root.exists():
        raise LayoutError(f"目标书籍已存在，library add 拒绝覆盖: {paths.root}")
    if source == paths.root or paths.root in source.parents:
        raise LayoutError("导入来源不能位于目标书籍目录内")

    source_before = _source_hashes(source)
    layout.library_root.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(tempfile.mkdtemp(prefix=f".add-{book_id}-", dir=layout.library_root))
    stage_paths = BookPaths(staging_parent / book_id, book_id)
    try:
        _copy_source(source, stage_paths.source)
        source_after = _source_hashes(stage_paths.source)
        if source_before != source_after:
            raise LayoutError("来源复制前后 SHA-256 不一致，拒绝继续导入")
        ingest = ingest_book(
            book_id=book_id,
            title=options.title or book_id,
            source_root=stage_paths.source,
            workspace_root=staging_parent,
            settings=load_settings(),
            confirm_order=options.confirm_order,
            canonical_paths=stage_paths,
        )
        _rewrite_database_paths(
            stage_paths.database,
            sorted(
                [(stage_paths.source, paths.source), (stage_paths.root, paths.root)],
                key=lambda item: len(item[0].parts),
                reverse=True,
            ),
        )
        stage_paths.root.rename(paths.root)
        _finalize_manifest(paths)
        mirror_check = verify_mirror(paths.root)
        if not mirror_check.get("match", False):
            raise LayoutError("canonical source manifest 与兼容镜像不一致")
        _finalize_registry(paths, options.title or book_id, source_before, initialize_mode)
        return LibraryAddResult(
            book_id=book_id,
            title=options.title or book_id,
            root=paths.root,
            source=paths.source,
            database=paths.database,
            source_manifest=paths.source_manifest,
            readiness_status="NEEDS_INITIALIZATION",
            source_hashes_before=source_before,
            source_hashes_after=_source_hashes(paths.source),
            ingest=ingest,
            fts_rows=_fts_rows(paths.database, book_id),
            initialize_mode=initialize_mode,
        )
    except Exception:
        if stage_paths.root.exists() and layout.contains(stage_paths.root):
            shutil.rmtree(stage_paths.root)
        raise
    finally:
        with suppress(OSError):
            staging_parent.rmdir()


def _source_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and not path.is_symlink()),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )


def _source_hashes(root: Path) -> dict[str, str]:
    base = root.parent if root.is_file() else root
    return {path.relative_to(base).as_posix(): sha256_file(path) for path in _source_files(root)}


def _copy_source(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        shutil.copy2(source, destination / source.name)
        return
    for path in source.rglob("*"):
        if path.is_symlink():
            raise LayoutError(f"导入来源包含 symlink/reparse point: {path}")
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        else:
            raise LayoutError(f"导入来源包含不支持的路径: {path}")


def _finalize_manifest(paths: BookPaths) -> None:
    authority = paths.source_manifest
    payload = json.loads(authority.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LayoutError(f"source manifest 必须是 object: {authority}")
    payload["source_root"] = str(paths.source)
    payload.pop("compatibility_marker", None)
    payload.pop("mirror_of", None)
    authority.write_text(json_dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_compatibility_mirror(paths)


def _finalize_registry(
    paths: BookPaths,
    title: str,
    source_hashes: dict[str, str],
    initialize_mode: str,
) -> None:
    registry = BookRegistry(BookLayout(paths.root.parent.parent))
    values: dict[str, Any] = {
        "schema_version": "book-v1",
        "layout_version": "library-v1",
        "book_id": paths.book_id,
        "slug": paths.book_id,
        "title": title,
        "active_edition_id": "base",
        "database_path": "_system/state.sqlite3",
        "source_storage_mode": "COPY_READ_ONLY",
        "source_files": sorted(source_hashes),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "readiness_status": "NEEDS_INITIALIZATION",
        "initialize_mode": initialize_mode,
        "latest_chapter": _latest_chapter(paths.database, paths.book_id),
        "current_atlas_id": None,
        "current_initialization_id": None,
        "latest_export": "editions/base/exports/latest",
        "source": {
            "root": "source",
            "files": sorted(source_hashes),
            "sha256": next(iter(source_hashes.values())) if len(source_hashes) == 1 else None,
            "hashes": source_hashes,
        },
    }
    registry.write(paths, values)
    registry.write_readme(paths, values)


def _latest_chapter(database: Path, book_id: str) -> int | None:
    with Database(database).connect() as connection:
        row = connection.execute(
            "SELECT MAX(ordinal) FROM chapters WHERE book_id=?", (book_id,)
        ).fetchone()
    return None if row is None or row[0] is None else int(row[0])


def _fts_rows(database: Path, book_id: str) -> int:
    with Database(database).connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM chapter_fts WHERE book_id=?", (book_id,)
        ).fetchone()
    return 0 if row is None else int(row[0])


__all__ = ["LibraryAddOptions", "LibraryAddResult", "add_book"]
