"""可审计的 storage retention 策略。

Retention 只生成 normal portable export 的超额候选；``exports/archive``
和 ``exports/latest`` 永远不会被自动加入候选。实际移动仍由 cleanup 的
精确 confirmation 和安全归档门负责。
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from novel_authoring.storage.cleanup import (
    CleanupCandidate,
    CleanupReport,
    ReferenceChecker,
    _is_reparse_point,
    _raw_path_chain_is_safe,
    apply_cleanup,
    plan_cleanup,
)
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.models import LayoutError


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Retention defaults for normal portable exports.

    ``archive_auto_delete`` is retained as an explicit, safe configuration
    flag.  It can never be enabled by this module: archive material is kept
    indefinitely and is not emitted as an automatic cleanup candidate.
    """

    normal_portable_exports: int = 3
    archive_auto_delete: bool = False

    def __post_init__(self) -> None:
        if self.normal_portable_exports < 0:
            raise ValueError("normal_portable_exports 不能小于 0")
        if self.archive_auto_delete:
            raise ValueError("archive 不允许自动删除")

    @classmethod
    def from_yaml(cls, path: Path | str) -> RetentionConfig:
        with Path(path).expanduser().open("r", encoding="utf-8") as handle:
            value = yaml.safe_load(handle) or {}
        if not isinstance(value, Mapping):
            raise ValueError("retention.yaml 顶层必须是 mapping")
        keep = value.get("normal_portable_exports", 3)
        archive_auto_delete = bool(value.get("archive_auto_delete", False))
        return cls(normal_portable_exports=int(keep), archive_auto_delete=archive_auto_delete)

    @property
    def normal_export_keep(self) -> int:
        """兼容外部调用方使用的简短别名。"""

        return self.normal_portable_exports

    def to_dict(self) -> dict[str, object]:
        return {
            "normal_portable_exports": self.normal_portable_exports,
            "archive_auto_delete": self.archive_auto_delete,
        }


class RetentionReport(CleanupReport):
    """JSON-compatible retention report returned by :func:`plan_retention`."""


def plan_retention(
    library_root: Path | str | BookLayout,
    *,
    config: RetentionConfig | None = None,
    book_id: str | None = None,
    reference_checker: ReferenceChecker | None = None,
    generated_at: str | None = None,
) -> RetentionReport:
    """Plan retention without changing the library.

    Direct children of each ``editions/*/exports`` directory are treated as
    normal portable bundles, except for ``latest`` and ``archive``.  The
    newest configured number is retained; older normal bundles become
    ``REGENERABLE`` cleanup candidates and remain blocked if referenced.
    """

    effective = config or RetentionConfig()
    root = _library_root(library_root)
    normalized_book_id = _normalize_book_id(book_id) if book_id is not None else None
    targets: list[CleanupCandidate] = []
    retained: list[str] = []
    archive_skipped: list[str] = []
    discovery_warnings: list[str] = []

    for book_root in _book_roots(root, normalized_book_id):
        for exports_root in _export_roots(book_root):
            entries, skipped = _normal_exports(exports_root)
            archive_skipped.extend(skipped)
            entries.sort(key=_export_sort_key, reverse=True)
            retained.extend(
                str(entry.path) for entry in entries[: effective.normal_portable_exports]
            )
            for entry in entries[effective.normal_portable_exports :]:
                targets.append(
                    CleanupCandidate(
                        path=entry.path,
                        category="REGENERABLE",
                        book_id=book_root.name,
                        reason=(
                            "normal portable export 超过 retention 保留数 "
                            f"{effective.normal_portable_exports}"
                        ),
                        kind="normal_portable_export",
                        metadata={
                            "created_at": entry.created_at,
                            "retention_limit": effective.normal_portable_exports,
                        },
                    )
                )
    if not root.is_dir():
        discovery_warnings.append(f"library_root 不存在或不是目录: {root}")

    report = plan_cleanup(
        root,
        candidates=targets,
        book_id=normalized_book_id,
        reference_checker=reference_checker,
        generated_at=generated_at,
    )
    result = RetentionReport(report)
    result["report_type"] = "storage_retention"
    result["retention"] = effective.to_dict()
    result["retained"] = sorted(set(retained), key=str.casefold)
    result["archive_skipped"] = sorted(set(archive_skipped), key=str.casefold)
    result["warnings"] = [*discovery_warnings, *list(report.get("warnings", []))]
    summary = dict(report.get("summary", {}))
    summary.update(
        {
            "retained_count": len(result["retained"]),
            "archive_skipped_count": len(result["archive_skipped"]),
        }
    )
    result["summary"] = summary
    return result


def apply_retention(
    report: Mapping[str, Any],
    confirmation: str,
    *,
    reference_checker: ReferenceChecker | None = None,
) -> CleanupReport:
    """Apply a retention dry-run through cleanup's archive-only gate."""

    return apply_cleanup(report, confirmation, reference_checker=reference_checker)


retention = plan_retention
plan_export_retention = plan_retention


@dataclass(frozen=True, slots=True)
class _ExportEntry:
    path: Path
    created_at: str | None
    mtime_ns: int


def retention_candidates(
    library_root: Path | str | BookLayout,
    *,
    config: RetentionConfig | None = None,
    book_id: str | None = None,
) -> list[CleanupCandidate]:
    """Return only the normal-export candidates, without running cleanup."""

    effective = config or RetentionConfig()
    root = _library_root(library_root)
    normalized_book_id = _normalize_book_id(book_id) if book_id is not None else None
    result: list[CleanupCandidate] = []
    for book_root in _book_roots(root, normalized_book_id):
        for exports_root in _export_roots(book_root):
            entries, _ = _normal_exports(exports_root)
            entries.sort(key=_export_sort_key, reverse=True)
            result.extend(
                CleanupCandidate(
                    path=entry.path,
                    category="REGENERABLE",
                    book_id=book_root.name,
                    reason=(
                        "normal portable export 超过 retention 保留数 "
                        f"{effective.normal_portable_exports}"
                    ),
                    kind="normal_portable_export",
                    metadata={"created_at": entry.created_at},
                )
                for entry in entries[effective.normal_portable_exports :]
            )
    return result


def _library_root(value: Path | str | BookLayout) -> Path:
    raw = value.library_root if isinstance(value, BookLayout) else Path(value)
    lexical = Path(os.path.abspath(os.path.normpath(str(raw.expanduser()))))
    if not _raw_path_chain_is_safe(lexical):
        raise LayoutError(f"library_root 路径包含 symlink/reparse point: {raw}")
    root = lexical.resolve(strict=False)
    if root.name in {"", ".", ".."}:
        raise LayoutError("library_root 无效")
    return root


def _normalize_book_id(value: str) -> str:
    normalized = value.strip()
    if not normalized or normalized in {".", ".."}:
        raise LayoutError("book_id 不能为空或路径保留字")
    if any(char in normalized for char in ("/", "\\", ":")):
        raise LayoutError("book_id 不能包含路径分隔符")
    if any(ord(char) < 32 for char in normalized):
        raise LayoutError("book_id 不能包含控制字符")
    return normalized


def _book_roots(root: Path, book_id: str | None) -> list[Path]:
    if book_id is not None:
        candidate = root / book_id
        return [candidate] if candidate.is_dir() else []
    if not root.is_dir():
        return []
    return [
        child
        for child in sorted(root.iterdir(), key=lambda item: item.name.casefold())
        if child.is_dir()
        and not _is_reparse_point(child)
        and child.name.casefold() != ".archive"
    ]


def _export_roots(book_root: Path) -> list[Path]:
    editions = book_root / "editions"
    if not editions.is_dir() or editions.is_symlink():
        return []
    return [
        edition / "exports"
        for edition in sorted(editions.iterdir(), key=lambda item: item.name.casefold())
        if (
            edition.is_dir()
            and not _is_reparse_point(edition)
            and (edition / "exports").is_dir()
            and not _is_reparse_point(edition / "exports")
        )
    ]


def _normal_exports(exports_root: Path) -> tuple[list[_ExportEntry], list[str]]:
    entries: list[_ExportEntry] = []
    archive_skipped: list[str] = []
    try:
        children = sorted(exports_root.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return [], []
    for child in children:
        lowered = child.name.casefold()
        if lowered in {"latest", "archive"}:
            archive_skipped.append(str(child))
            continue
        if lowered.startswith(".") or lowered in {"manifest.json", "readme.md", ".gitkeep"}:
            continue
        if _is_reparse_point(child) or not (child.is_dir() or child.is_file()):
            continue
        try:
            info = child.stat()
        except OSError:
            continue
        entries.append(
            _ExportEntry(
                path=child,
                created_at=_manifest_created_at(child),
                mtime_ns=info.st_mtime_ns,
            )
        )
    return entries, archive_skipped


def _manifest_created_at(path: Path) -> str | None:
    manifest = path / "manifest.json" if path.is_dir() else None
    if manifest is None or not manifest.is_file():
        return None
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping):
        return None
    created_at = value.get("created_at")
    return str(created_at) if created_at else None


def _export_sort_key(entry: _ExportEntry) -> tuple[str, int, str]:
    return (entry.created_at or "", entry.mtime_ns, entry.path.name.casefold())


__all__ = [
    "RetentionConfig",
    "RetentionReport",
    "apply_retention",
    "plan_export_retention",
    "plan_retention",
    "retention",
    "retention_candidates",
]
