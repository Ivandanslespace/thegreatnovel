"""Book registry and generated per-book metadata."""

from __future__ import annotations

from builtins import list as builtin_list
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from novel_authoring.storage.layout import LAYOUT_VERSION, BookLayout
from novel_authoring.storage.models import BookPaths
from novel_authoring.utils import sha256_file, utc_now


@dataclass(frozen=True, slots=True)
class BookRecord:
    book_id: str
    title: str
    root: Path
    source_root: Path
    source_files: tuple[str, ...]
    active_edition_id: str
    layout_version: str
    readiness_status: str | None = None
    legacy_locations: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, paths: BookPaths, mapping: dict[str, Any]) -> BookRecord:
        source = mapping.get("source") or {}
        edition = mapping.get("active_edition_id") or mapping.get("active_edition") or "base"
        files_value = (
            (source.get("files") or mapping.get("source_files", []))
            if isinstance(source, dict)
            else mapping.get("source_files", [])
        )
        files = files_value if isinstance(files_value, list) else []
        legacy_value = mapping.get("legacy_locations")
        legacy = legacy_value if isinstance(legacy_value, list) else []
        return cls(
            book_id=str(mapping.get("book_id") or paths.book_id),
            title=str(mapping.get("title") or paths.book_id),
            root=paths.root,
            source_root=paths.source,
            source_files=tuple(str(item) for item in files if isinstance(item, str)),
            active_edition_id=str(edition),
            layout_version=str(mapping.get("layout_version") or LAYOUT_VERSION),
            readiness_status=(
                str(mapping["readiness_status"]) if mapping.get("readiness_status") else None
            ),
            legacy_locations=tuple(str(item) for item in legacy if isinstance(item, str)),
        )


class BookRegistry:
    """Read/write ``book.yaml`` and generated README files."""

    def __init__(self, layout: BookLayout) -> None:
        self.layout = layout

    def read(self, book_id: str) -> dict[str, Any]:
        paths = self.layout.for_book(book_id)
        with paths.book_yaml.open("r", encoding="utf-8") as handle:
            value = yaml.safe_load(handle) or {}
        if not isinstance(value, dict):
            raise ValueError(f"book.yaml 必须是 mapping: {paths.book_yaml}")
        return value

    def record(self, book_id: str) -> BookRecord:
        paths = self.layout.for_book(book_id)
        return BookRecord.from_mapping(paths, self.read(book_id))

    def list(self) -> builtin_list[BookRecord]:
        return [self.record(paths.book_id) for paths in self.layout.list_books()]

    def write(self, paths: BookPaths, values: dict[str, Any]) -> Path:
        paths.root.mkdir(parents=True, exist_ok=True)
        normalized = dict(values)
        normalized.setdefault("schema_version", "book-v1")
        normalized.setdefault("layout_version", LAYOUT_VERSION)
        normalized.setdefault("book_id", paths.book_id)
        normalized.setdefault("slug", paths.book_id)
        normalized.setdefault("database_path", "_system/state.sqlite3")
        normalized.setdefault("source_storage_mode", "COPY_READ_ONLY")
        normalized.setdefault("source_files", [])
        normalized.setdefault("created_at", utc_now())
        normalized.setdefault("latest_chapter", None)
        normalized.setdefault("current_atlas_id", None)
        normalized.setdefault("current_initialization_id", None)
        normalized.setdefault("latest_export", "editions/base/exports/latest")
        with paths.book_yaml.open("w", encoding="utf-8", newline="\n") as handle:
            yaml.safe_dump(normalized, handle, allow_unicode=True, sort_keys=False)
        return paths.book_yaml

    def ensure(
        self,
        book_id: str,
        *,
        title: str | None = None,
        source_path: Path | None = None,
        active_edition_id: str = "base",
        readiness_status: str | None = None,
        legacy_locations: builtin_list[str] | None = None,
    ) -> BookRecord:
        paths = self.layout.ensure_book(book_id)
        values: dict[str, Any] = self.read(paths.book_id) if paths.book_yaml.exists() else {}
        created_at = values.get("created_at") or utc_now()
        values.update(
            {
                "schema_version": "book-v1",
                "layout_version": LAYOUT_VERSION,
                "book_id": paths.book_id,
                "slug": str(values.get("slug") or paths.book_id),
                "title": title or values.get("title") or paths.book_id,
                "active_edition_id": active_edition_id,
                "database_path": "_system/state.sqlite3",
                "source_storage_mode": "COPY_READ_ONLY",
                "created_at": created_at,
                "latest_export": values.get(
                    "latest_export", "editions/base/exports/latest"
                ),
                "source": values.get("source") or {"root": "source", "files": []},
                "updated_at": utc_now(),
            }
        )
        source = values["source"]
        if source_path is not None and source_path.is_file():
            source = dict(source) if isinstance(source, dict) else {}
            source["root"] = "source"
            source["files"] = [source_path.name]
            source["sha256"] = sha256_file(source_path)
            source["byte_size"] = source_path.stat().st_size
            values["source"] = source
            values["source_files"] = list(source["files"])
        elif "source_files" not in values:
            values["source_files"] = list(
                source.get("files", []) if isinstance(source, dict) else []
            )
        if readiness_status is not None:
            values["readiness_status"] = readiness_status
        if legacy_locations:
            values["legacy_locations"] = sorted(set(legacy_locations))
        self.write(paths, values)
        self.write_readme(paths, values)
        return BookRecord.from_mapping(paths, values)

    def write_readme(self, paths: BookPaths, values: dict[str, Any] | None = None) -> Path:
        metadata = values if values is not None else self.read(paths.book_id)
        title = str(metadata.get("title") or paths.book_id)
        source = metadata.get("source") or {}
        files = source.get("files", []) if isinstance(source, dict) else []
        readiness = metadata.get("readiness_status") or "UNKNOWN"
        lines = [
            f"# {title}",
            "",
            "此目录由 Novel Authoring System 的 Book Library 管理。",
            "原始来源位于 `source/`，机器运行数据位于 `_system/`；请勿手工覆盖数据库或 Canon。",
            "",
            f"- book_id: `{paths.book_id}`",
            f"- layout: `{metadata.get('layout_version', LAYOUT_VERSION)}`",
            f"- active edition: `{metadata.get('active_edition_id', 'base')}`",
            f"- database: `{metadata.get('database_path', '_system/state.sqlite3')}`",
            f"- readiness: `{readiness}`",
            f"- source files: {len(files)}",
            f"- latest chapter: `{metadata.get('latest_chapter') or 'unknown'}`",
            f"- current Atlas: `{metadata.get('current_atlas_id') or 'unknown'}`",
            f"- current initialization: `{metadata.get('current_initialization_id') or 'unknown'}`",
            f"- latest export: `{metadata.get('latest_export', 'editions/base/exports/latest')}`",
            "",
            "## 入口",
            "",
            "- `book.yaml`: 书库注册元数据",
            "- `source/`: 只读来源副本",
            "- `editions/<edition_id>/`: edition-scoped analysis、writing、operations 和 exports",
            "- `editions/<edition_id>/exports/latest/`: 当前 Portable Snapshot Bundle（如已生成）",
            "",
            "## 常用命令",
            "",
            f"- `novel library paths --book-id {paths.book_id}`",
            f"- `novel atlas export-snapshot --book-id {paths.book_id}`",
            f"- `novel library cleanup --book-id {paths.book_id} --dry-run`",
            "",
            "## 下一步",
            "",
            "先核对当前 edition、Atlas readiness 和指标覆盖，再由作者决定是否创建下一次 handoff。",
        ]
        paths.readme.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return paths.readme


__all__ = ["BookRecord", "BookRegistry"]
