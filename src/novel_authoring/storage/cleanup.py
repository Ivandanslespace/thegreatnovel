"""安全、可恢复的 library 清理原语。

清理模块只负责把明确标记为可重建或可归档的产物移入受控 archive。
它不会永久删除文件，也不会改变 Canon、source、数据库或 Story Atlas。
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import stat
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeAlias

from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.models import LayoutError
from novel_authoring.utils import json_dumps, sha256_bytes, utc_now

ReferenceChecker: TypeAlias = Callable[[Path], object]


class CleanupCategory(StrEnum):
    """Storage classification accepted by the cleanup apply gate."""

    REGENERABLE = "REGENERABLE"
    ARCHIVE = "ARCHIVE"
    USER_DATA = "USER_DATA"
    KEEP_CORE = "KEEP_CORE"
    KEEP_HISTORY = "KEEP_HISTORY"
    UNKNOWN = "UNKNOWN"


class CleanupError(LayoutError):
    """Base error for an unsafe or invalid cleanup operation."""


class CleanupConfirmationError(CleanupError):
    """Raised when apply does not receive the exact confirmation string."""


class CleanupBlockedError(CleanupError):
    """Raised when a dry-run report contains any apply blocker."""


@dataclass(frozen=True, slots=True)
class CleanupCandidate:
    """Input descriptor for one explicitly classified cleanup target."""

    path: Path
    category: CleanupCategory | str
    book_id: str | None = None
    reason: str = ""
    kind: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    classification: CleanupCategory | str | None = None

    def __post_init__(self) -> None:
        if self.classification is None:
            return
        if _category_value(self.category) not in {
            CleanupCategory.UNKNOWN.value,
            _category_value(self.classification),
        }:
            raise CleanupError("category 与 classification 不一致")
        object.__setattr__(self, "category", self.classification)


# ``CleanupTarget`` is kept as a readable integration alias.
CleanupTarget = CleanupCandidate


class CleanupReport(dict[str, Any]):
    """JSON-compatible report with small convenience accessors.

    The report intentionally subclasses ``dict`` so callers can pass the
    return value directly to ``json.dumps``/``json_dumps``.
    """

    def to_dict(self) -> dict[str, Any]:
        return dict(self)

    @property
    def candidate_hash(self) -> str:
        return str(self.get("candidate_hash", ""))

    @property
    def confirmation(self) -> str | None:
        value = self.get("confirmation")
        return None if value is None else str(value)

    @property
    def candidates(self) -> list[dict[str, Any]]:
        value = self.get("candidates", [])
        return value if isinstance(value, list) else []


_ALLOWED_APPLY_CATEGORIES = {
    CleanupCategory.REGENERABLE.value,
    CleanupCategory.ARCHIVE.value,
}
_IMMUTABLE_DIRECTORY_NAMES = {
    "_system",
    "atlas",
    "canon",
    "database",
    "db",
    "source",
    "story_atlas",
}
_IMMUTABLE_FILE_NAMES = {
    "atlas_manifest.json",
    "book.yaml",
    "state.sqlite3",
    "state.sqlite3-shm",
    "state.sqlite3-wal",
}
_STRUCTURAL_DIRECTORY_NAMES = {
    "analysis",
    "batches",
    "editions",
    "exports",
    "operations",
    "writing",
}
_ARCHIVE_DIRECTORY_NAMES = {".archive", "archive", "latest"}
_TEXT_REFERENCE_SUFFIXES = {
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
}


def plan_cleanup(
    library_root: Path | str | BookLayout,
    *,
    candidates: Iterable[CleanupCandidate | Path | str | Mapping[str, object]] | None = None,
    targets: Iterable[CleanupCandidate | Path | str | Mapping[str, object]] | None = None,
    book_id: str | None = None,
    reference_checker: ReferenceChecker | None = None,
    generated_at: str | None = None,
) -> CleanupReport:
    """Build a read-only, JSON-compatible cleanup report.

    Targets must be supplied with an explicit classification.  A bare path
    is treated as ``UNKNOWN`` and therefore cannot pass the apply gate.  The
    default report is always dry-run; no directory is created or moved.
    """

    if candidates is not None and targets is not None:
        raise CleanupError("candidates 与 targets 只能提供一个")
    root = _library_root(library_root)
    normalized_book_id = _normalize_book_id(book_id) if book_id is not None else None
    supplied = candidates if candidates is not None else targets
    raw_candidates = list(supplied or ())
    records = [
        _inspect_candidate(
            _coerce_candidate(item),
            root,
            normalized_book_id,
            reference_checker,
        )
        for item in raw_candidates
    ]
    _add_overlap_blockers(records)

    derived_book_ids = {
        str(item["book_id"])
        for item in records
        if item.get("book_id") and not item.get("path_error")
    }
    report_book_id = normalized_book_id
    warnings: list[str] = []
    if report_book_id is None and len(derived_book_ids) == 1:
        report_book_id = next(iter(derived_book_ids))
    elif report_book_id is None and len(derived_book_ids) > 1:
        warnings.append("一次清理只能对应一个 book_id；多本书的候选永久阻塞")
        for item in records:
            item["blocked"] = True
            item["status"] = "BLOCKED"
            _append_reason(item, "multiple_book_ids")
    if not root.is_dir():
        warnings.append(f"library_root 不存在或不是目录: {root}")

    candidate_hash = _candidate_hash(records, root)
    eligible = [item for item in records if not item.get("blocked", True)]
    blocked = [item for item in records if item.get("blocked", True)]
    summary = {
        "candidate_count": len(records),
        "eligible_count": len(eligible),
        "blocked_count": len(blocked),
        "referenced_count": sum(bool(item.get("references")) for item in records),
    }
    confirmation = (
        f"CLEANUP {report_book_id} {candidate_hash}"
        if report_book_id is not None
        else None
    )
    status = "DRY_RUN" if eligible else ("BLOCKED" if blocked else "EMPTY")
    return CleanupReport(
        {
            "report_type": "storage_cleanup",
            "report_version": 1,
            "mode": "DRY_RUN",
            "status": status,
            "library_root": str(root),
            "book_id": report_book_id,
            "candidate_hash": candidate_hash,
            "confirmation": confirmation,
            "generated_at": generated_at or utc_now(),
            "summary": summary,
            "warnings": warnings,
            "candidates": records,
        }
    )


def apply_cleanup(
    report: Mapping[str, Any],
    confirmation: str,
    *,
    reference_checker: ReferenceChecker | None = None,
) -> CleanupReport:
    """Move an approved dry-run report into ``library/.archive``.

    The confirmation is intentionally exact, including spaces and casing.
    Every candidate is revalidated immediately before moving so a changed or
    newly referenced path cannot be applied from a stale report.
    """

    report_dict = dict(report)
    root = _library_root(Path(str(report_dict.get("library_root", ""))))
    report_book_id = report_dict.get("book_id")
    candidate_hash = str(report_dict.get("candidate_hash", ""))
    if not isinstance(report_book_id, str) or not report_book_id or not candidate_hash:
        raise CleanupConfirmationError("清理报告缺少 book_id 或 candidate_hash")
    expected = f"CLEANUP {report_book_id} {candidate_hash}"
    if confirmation != expected:
        raise CleanupConfirmationError(
            "confirmation 必须精确匹配 CLEANUP <book_id> <candidate_hash>"
        )
    if report_dict.get("mode") != "DRY_RUN":
        raise CleanupError("只能 apply DRY_RUN 报告")

    records_value = report_dict.get("candidates")
    if not isinstance(records_value, list):
        raise CleanupBlockedError("清理报告 candidates 必须是列表")
    records = [item for item in records_value if isinstance(item, Mapping)]
    if len(records) != len(records_value):
        raise CleanupBlockedError("清理报告包含不可解析的候选")
    if _candidate_hash(records, root) != candidate_hash:
        raise CleanupConfirmationError("候选内容已变化，candidate_hash 失效")
    if any(bool(item.get("blocked", True)) for item in records):
        raise CleanupBlockedError("dry-run 报告包含被阻塞候选，拒绝 apply")
    if not records:
        raise CleanupBlockedError("没有可 apply 的候选")

    root = _require_safe_root(root)
    timestamp = _archive_timestamp()
    archive_root = root / ".archive" / report_book_id / timestamp
    while os.path.lexists(str(archive_root)):
        timestamp = f"{timestamp}-1"
        archive_root = root / ".archive" / report_book_id / timestamp
    _require_safe_destination(root, archive_root)

    prepared: list[tuple[dict[str, Any], Path, Path]] = []
    seen_destinations: set[str] = set()
    for item in records:
        source, relative = _report_source(root, item, report_book_id)
        current = _inspect_current_source(source, root, relative, item, reference_checker)
        destination = archive_root / Path(*relative.parts[1:])
        _require_safe_destination(root, destination)
        destination_key = os.path.normcase(os.path.normpath(str(destination)))
        if destination_key in seen_destinations:
            raise CleanupBlockedError(f"归档目标冲突: {destination}")
        seen_destinations.add(destination_key)
        if os.path.lexists(str(destination)):
            raise CleanupBlockedError(f"归档目标已存在，拒绝覆盖: {destination}")
        prepared.append((current, source, destination))

    try:
        archive_root.mkdir(parents=True, exist_ok=False)
        moved: list[dict[str, str]] = []
        for item, source, destination in prepared:
            _inspect_current_source(
                source,
                root,
                Path(str(item["relative_path"])),
                item,
                reference_checker,
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            _require_safe_destination(root, destination.parent)
            if os.path.lexists(str(destination)):
                raise CleanupBlockedError(f"归档目标已存在，拒绝覆盖: {destination}")
            shutil.move(str(source), str(destination))
            moved.append(
                {
                    "source": str(source),
                    "destination": str(destination),
                    "relative_path": str(item["relative_path"]),
                }
            )
    except CleanupError:
        raise
    except (OSError, shutil.Error) as exc:
        raise CleanupError(
            f"归档移动未完整完成；已移动的目标仍位于 {archive_root}: {exc}"
        ) from exc

    result = CleanupReport(report_dict)
    result["mode"] = "APPLIED"
    result["status"] = "APPLIED"
    result["applied_at"] = utc_now()
    result["archive_root"] = str(archive_root)
    result["moved"] = moved
    result["candidates"] = [
        {
            **dict(item),
            "status": "MOVED",
            "archive_path": moved[index]["destination"],
        }
        for index, item in enumerate(records)
    ]
    return result


def cleanup(
    library_root: Path | str | BookLayout,
    *,
    candidates: Iterable[CleanupCandidate | Path | str | Mapping[str, object]] | None = None,
    targets: Iterable[CleanupCandidate | Path | str | Mapping[str, object]] | None = None,
    book_id: str | None = None,
    reference_checker: ReferenceChecker | None = None,
    apply: bool = False,
    dry_run: bool | None = None,
    confirmation: str | None = None,
) -> CleanupReport:
    """Plan cleanup by default, or apply only with explicit confirmation."""

    if dry_run is not None:
        apply = not dry_run
    report = plan_cleanup(
        library_root,
        candidates=candidates,
        targets=targets,
        book_id=book_id,
        reference_checker=reference_checker,
    )
    if not apply:
        return report
    if confirmation is None:
        raise CleanupConfirmationError("apply 必须提供精确 confirmation 字符串")
    return apply_cleanup(report, confirmation, reference_checker=reference_checker)


cleanup_library = cleanup


def default_reference_checker(path: Path, library_root: Path | None = None) -> list[str]:
    """Find conservative DB/text path references to ``path``.

    Callers with domain-specific references can supply ``reference_checker``;
    the built-in checker is intentionally conservative and reports scan errors
    as blockers rather than treating an incomplete scan as proof of safety.
    """

    candidate = Path(path).expanduser().resolve(strict=False)
    root = (library_root or _infer_library_root(candidate)).expanduser().resolve(strict=False)
    if not _is_contained(candidate, root):
        return [f"candidate 不在 library_root 内: {candidate}"]
    needles = _reference_needles(candidate, root)
    if not needles:
        return []
    references: list[str] = []
    try:
        for current, directories, files in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            directories[:] = [
                name
                for name in directories
                if not _is_reparse_point(current_path / name)
                and not _is_same_or_child(current_path / name, candidate)
            ]
            for name in files:
                file_path = current_path / name
                if _is_same_or_child(file_path, candidate) or _is_reparse_point(file_path):
                    continue
                suffix = file_path.suffix.casefold()
                if suffix not in _TEXT_REFERENCE_SUFFIXES and suffix not in {".db", ".sqlite3"}:
                    continue
                data = file_path.read_bytes()
                normalized_data = data.lower().replace(b"/", b"\\")
                if any(needle in normalized_data for needle in needles):
                    references.append(str(file_path))
    except (OSError, sqlite3.Error) as exc:
        return [f"reference scan failed: {exc}"]
    return sorted(set(references), key=str.casefold)


def _coerce_candidate(
    value: CleanupCandidate | Path | str | Mapping[str, object],
) -> CleanupCandidate:
    if isinstance(value, CleanupCandidate):
        return value
    if isinstance(value, Mapping):
        raw_path = value.get("path")
        if not isinstance(raw_path, (Path, str)):
            raise CleanupError("cleanup candidate 必须包含 path")
        category = value.get(
            "category", value.get("classification", CleanupCategory.UNKNOWN.value)
        )
        book_id = value.get("book_id")
        metadata = value.get("metadata", {})
        return CleanupCandidate(
            path=Path(raw_path),
            category=str(category),
            book_id=None if book_id is None else str(book_id),
            reason=str(value.get("reason", "")),
            kind=None if value.get("kind") is None else str(value["kind"]),
            metadata=metadata if isinstance(metadata, Mapping) else {},
        )
    if isinstance(value, (Path, str)):
        return CleanupCandidate(path=Path(value), category=CleanupCategory.UNKNOWN)
    raise CleanupError(f"无法解析 cleanup candidate: {value!r}")


def _inspect_candidate(
    candidate: CleanupCandidate,
    root: Path,
    requested_book_id: str | None,
    reference_checker: ReferenceChecker | None,
) -> dict[str, Any]:
    category = _category_value(candidate.category)
    raw_path = candidate.path.expanduser()
    lexical = raw_path if raw_path.is_absolute() else root / raw_path
    lexical = Path(os.path.abspath(os.path.normpath(str(lexical))))
    record: dict[str, Any] = {
        "path": str(lexical),
        "relative_path": None,
        "book_id": candidate.book_id,
        "category": category,
        "kind": candidate.kind,
        "reason": candidate.reason,
        "metadata": _json_safe(candidate.metadata),
        "status": "BLOCKED",
        "blocked": True,
        "block_reasons": [],
        "references": [],
        "fingerprint": None,
    }
    if category not in _ALLOWED_APPLY_CATEGORIES:
        _append_reason(record, f"category_not_allowed:{category}")

    if not _is_contained(lexical, root):
        _append_reason(record, "path_outside_library_root")
        record["path_error"] = True
        return record
    if not _ancestors_are_safe(root, lexical):
        _append_reason(record, "symlink_or_reparse_point")
        record["path_error"] = True
        return record
    try:
        resolved = lexical.resolve(strict=False)
        relative = resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        _append_reason(record, f"path_resolution_failed:{exc}")
        record["path_error"] = True
        return record
    record["path"] = str(resolved)
    record["relative_path"] = relative.as_posix()
    parts = tuple(part.casefold() for part in relative.parts)
    derived_book_id = relative.parts[0] if relative.parts else None
    if derived_book_id is not None:
        record["book_id"] = candidate.book_id or derived_book_id
    if requested_book_id is not None and record.get("book_id") != requested_book_id:
        _append_reason(record, "book_id_mismatch")
    if candidate.book_id is not None and candidate.book_id != derived_book_id:
        _append_reason(record, "candidate_book_id_mismatch")
    if len(parts) < 2:
        _append_reason(record, "book_root_or_library_root_is_immutable")
    protected_reason = _protected_path_reason(resolved, relative)
    if protected_reason is not None:
        _append_reason(record, protected_reason)
    if not os.path.lexists(str(resolved)):
        _append_reason(record, "path_does_not_exist")
        return record
    if not resolved.is_file() and not resolved.is_dir():
        _append_reason(record, "target_is_not_regular_file_or_directory")
    tree_issue = _tree_security_issue(resolved)
    if tree_issue is not None:
        _append_reason(record, tree_issue)
    try:
        record["fingerprint"] = _fingerprint(resolved)
    except OSError as exc:
        _append_reason(record, f"fingerprint_failed:{exc}")
    if not record["block_reasons"]:
        references = _run_reference_checker(resolved, root, reference_checker)
        record["references"] = references
        if references:
            _append_reason(record, "path_referenced")
    if not record["block_reasons"]:
        record["status"] = "ELIGIBLE"
        record["blocked"] = False
    return record


def _inspect_current_source(
    source: Path,
    root: Path,
    relative: Path,
    item: Mapping[str, Any],
    reference_checker: ReferenceChecker | None,
) -> dict[str, Any]:
    current = _inspect_candidate(
        CleanupCandidate(
            path=source,
            category=str(item.get("category", CleanupCategory.UNKNOWN.value)),
            book_id=str(item.get("book_id")),
            reason=str(item.get("reason", "")),
            kind=None if item.get("kind") is None else str(item["kind"]),
            metadata=item.get("metadata", {}) if isinstance(item.get("metadata"), Mapping) else {},
        ),
        root,
        str(item.get("book_id")),
        reference_checker,
    )
    if current.get("relative_path") != relative.as_posix():
        raise CleanupBlockedError("候选路径在 apply 前发生变化")
    if current.get("fingerprint") != item.get("fingerprint"):
        raise CleanupBlockedError(f"候选内容已变化，拒绝移动: {source}")
    if current.get("blocked"):
        raise CleanupBlockedError(
            f"候选在 apply 前被阻塞: {source} ({current.get('block_reasons', [])})"
        )
    return current


def _report_source(root: Path, item: Mapping[str, Any], report_book_id: str) -> tuple[Path, Path]:
    relative_raw = item.get("relative_path")
    if not isinstance(relative_raw, str) or not relative_raw:
        raise CleanupBlockedError("候选缺少 relative_path")
    relative = Path(relative_raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise CleanupBlockedError(f"候选 relative_path 不安全: {relative_raw}")
    if not relative.parts or relative.parts[0] != report_book_id:
        raise CleanupBlockedError("候选不属于 confirmation 中的 book_id")
    source = root.joinpath(*relative.parts)
    if not _is_contained(source, root):
        raise CleanupBlockedError(f"候选 source 越出 library_root: {source}")
    return source, relative


def _library_root(value: Path | str | BookLayout) -> Path:
    raw = value.library_root if isinstance(value, BookLayout) else Path(value)
    if not raw:
        raise CleanupError("library_root 不能为空")
    lexical = Path(os.path.abspath(os.path.normpath(str(raw.expanduser()))))
    if not _raw_path_chain_is_safe(lexical):
        raise CleanupError(f"library_root 路径包含 symlink/reparse point: {raw}")
    root = lexical.resolve(strict=False)
    if root.name in {"", ".", ".."}:
        raise CleanupError("library_root 无效")
    return root


def _require_safe_root(root: Path) -> Path:
    if _is_reparse_point(root):
        raise CleanupError(f"library_root 不允许是 symlink/reparse point: {root}")
    if not root.is_dir():
        raise CleanupError(f"library_root 不是目录: {root}")
    if not _ancestors_are_safe(root, root):
        raise CleanupError(f"library_root 路径包含 symlink/reparse point: {root}")
    return root


def _normalize_book_id(value: str) -> str:
    normalized = value.strip()
    if not normalized or normalized in {".", ".."}:
        raise CleanupError("book_id 不能为空或路径保留字")
    if any(char in normalized for char in ("/", "\\", ":")):
        raise CleanupError("book_id 不能包含路径分隔符")
    if any(ord(char) < 32 for char in normalized):
        raise CleanupError("book_id 不能包含控制字符")
    return normalized


def _category_value(value: CleanupCategory | str) -> str:
    return value.value if isinstance(value, CleanupCategory) else str(value).strip().upper()


def _append_reason(record: dict[str, Any], reason: str) -> None:
    reasons = record.setdefault("block_reasons", [])
    if reason not in reasons:
        reasons.append(reason)
    record["blocked"] = True
    record["status"] = "BLOCKED"


def _is_contained(path: Path, root: Path) -> bool:
    try:
        Path(path).relative_to(root)
    except ValueError:
        return False
    return True


def _is_same_or_child(path: Path, parent: Path) -> bool:
    try:
        Path(path).relative_to(parent)
    except ValueError:
        return False
    return True


def _ancestors_are_safe(root: Path, path: Path) -> bool:
    if _is_reparse_point(root):
        return False
    try:
        relative = Path(path).relative_to(root)
    except ValueError:
        return False
    current = root
    for part in relative.parts:
        current /= part
        if os.path.lexists(str(current)) and _is_reparse_point(current):
            return False
    return True


def _is_reparse_point(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = getattr(os.lstat(str(path)), "st_file_attributes", 0)
    except OSError:
        return False
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and attributes & flag)


def _tree_security_issue(path: Path) -> str | None:
    if _is_reparse_point(path):
        return "symlink_or_reparse_point"
    if not path.is_dir():
        return None
    for current, directories, files in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in [*directories, *files]:
            child = current_path / name
            if _is_reparse_point(child):
                return f"symlink_or_reparse_point:{child}"
        directories[:] = [
            name for name in directories if not _is_reparse_point(current_path / name)
        ]
    return None


def _protected_path_reason(path: Path, relative: Path) -> str | None:
    parts = tuple(part.casefold() for part in relative.parts)
    if not parts:
        return "library_root_is_immutable"
    if parts[0] == ".archive":
        return "cleanup_archive_is_immutable"
    if any(part in _IMMUTABLE_DIRECTORY_NAMES for part in parts):
        return "canon_source_database_or_atlas_is_immutable"
    if any(part in _ARCHIVE_DIRECTORY_NAMES for part in parts):
        return "latest_or_archive_is_not_auto_deleted"
    if path.name.casefold() in _IMMUTABLE_FILE_NAMES or path.suffix.casefold() in {
        ".sqlite3",
        ".db",
    }:
        return "database_or_registry_file_is_immutable"
    if len(parts) == 2 and parts[1] in {"source", "_system", "editions"}:
        return "book_structural_root_is_immutable"
    if len(parts) == 3 and parts[1] == "editions":
        return "edition_root_is_immutable"
    if (
        len(parts) == 4
        and parts[1] == "editions"
        and parts[3] in _STRUCTURAL_DIRECTORY_NAMES
    ):
        return "edition_structural_root_is_immutable"
    if path.is_dir() and _contains_protected_descendant(path):
        return "target_contains_immutable_descendant"
    return None


def _contains_protected_descendant(path: Path) -> bool:
    for current, directories, files in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in [*directories, *files]:
            lowered = name.casefold()
            child = current_path / name
            if lowered in _IMMUTABLE_DIRECTORY_NAMES | _ARCHIVE_DIRECTORY_NAMES:
                return True
            if lowered in _IMMUTABLE_FILE_NAMES or child.suffix.casefold() in {".sqlite3", ".db"}:
                return True
        directories[:] = [
            name for name in directories if not _is_reparse_point(current_path / name)
        ]
    return False


def _fingerprint(path: Path) -> dict[str, Any]:
    if path.is_file():
        info = path.stat()
        return {"kind": "file", "size": info.st_size, "mtime_ns": info.st_mtime_ns}
    if path.is_dir():
        entries: list[dict[str, Any]] = []
        for current, directories, files in os.walk(path, topdown=True, followlinks=False):
            current_path = Path(current)
            directories.sort(key=str.casefold)
            files.sort(key=str.casefold)
            for name in [*directories, *files]:
                child = current_path / name
                relative = child.relative_to(path).as_posix()
                if _is_reparse_point(child):
                    entries.append({"path": relative, "kind": "reparse"})
                    continue
                info = child.stat()
                entries.append(
                    {
                        "path": relative,
                        "kind": "dir" if child.is_dir() else "file",
                        "size": info.st_size,
                        "mtime_ns": info.st_mtime_ns,
                    }
                )
        return {"kind": "directory", "entries": entries}
    raise OSError(f"不是 regular file/directory: {path}")


def _run_reference_checker(
    path: Path,
    root: Path,
    checker: ReferenceChecker | None,
) -> list[str]:
    try:
        result = checker(path) if checker is not None else default_reference_checker(path, root)
    except Exception as exc:  # pragma: no cover - defensive boundary for plugin hooks
        return [f"reference_checker failed: {exc}"]
    if result is None or result is False:
        return []
    if result is True:
        return ["reference_checker reported a reference"]
    if isinstance(result, str):
        return [result] if result else []
    if isinstance(result, Mapping):
        referenced = result.get("references", result.get("referenced", False))
        if referenced is True:
            return [str(result.get("reason", "reference_checker reported a reference"))]
        if isinstance(referenced, str):
            return [referenced] if referenced else []
        if isinstance(referenced, Iterable):
            return [str(item) for item in referenced if str(item)]
        return []
    if isinstance(result, Iterable):
        return [str(item) for item in result if str(item)]
    return [f"reference_checker returned unsupported result: {result!r}"]


def _reference_needles(path: Path, root: Path) -> tuple[bytes, ...]:
    values = {
        str(path),
        path.as_posix(),
        str(path).replace("/", "\\"),
        root.joinpath(path.relative_to(root)).as_posix(),
        path.relative_to(root).as_posix(),
    }
    needles = {
        value.replace("/", "\\").casefold().encode("utf-8")
        for value in values
        if value
    }
    return tuple(sorted(needles, key=len, reverse=True))


def _infer_library_root(path: Path) -> Path:
    parts = path.parts
    for index, part in enumerate(parts):
        if part.casefold() == "library":
            return Path(*parts[: index + 1])
    return path.parent


def _require_safe_destination(root: Path, destination: Path) -> None:
    lexical = Path(os.path.abspath(os.path.normpath(str(destination))))
    if not _is_contained(lexical, root):
        raise CleanupBlockedError(f"归档目标越出 library_root: {destination}")
    if not _ancestors_are_safe(root, lexical):
        raise CleanupBlockedError(f"归档路径包含 symlink/reparse point: {destination}")


def _archive_timestamp() -> str:
    return utc_now().replace("-", "").replace(":", "").replace("+00:00", "Z")


def _candidate_hash(
    records: Iterable[Mapping[str, Any]], library_root: Path | None = None
) -> str:
    seed = [
        {
            "relative_path": item.get("relative_path"),
            "book_id": item.get("book_id"),
            "category": item.get("category"),
            "kind": item.get("kind"),
            "status": item.get("status"),
            "fingerprint": item.get("fingerprint"),
        }
        for item in records
    ]
    seed.sort(key=lambda item: str(item.get("relative_path")))
    payload: dict[str, Any] = {
        "library_root": None if library_root is None else str(library_root),
        "candidates": seed,
    }
    return sha256_bytes(json_dumps(payload).encode("utf-8"))


def _add_overlap_blockers(records: list[dict[str, Any]]) -> None:
    eligible = [
        item
        for item in records
        if not item.get("blocked") and isinstance(item.get("path"), str)
    ]
    for index, left in enumerate(eligible):
        left_path = Path(str(left["path"]))
        for right in eligible[index + 1 :]:
            right_path = Path(str(right["path"]))
            if _is_same_or_child(left_path, right_path) or _is_same_or_child(right_path, left_path):
                _append_reason(left, "overlapping_targets")
                _append_reason(right, "overlapping_targets")


def _json_safe(value: object) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _raw_path_chain_is_safe(path: Path) -> bool:
    current = path
    while True:
        if os.path.lexists(str(current)) and _is_reparse_point(current):
            return False
        parent = current.parent
        if parent == current:
            return True
        current = parent


__all__ = [
    "CleanupCandidate",
    "CleanupCategory",
    "CleanupConfirmationError",
    "CleanupError",
    "CleanupBlockedError",
    "CleanupReport",
    "CleanupTarget",
    "ReferenceChecker",
    "apply_cleanup",
    "cleanup",
    "cleanup_library",
    "default_reference_checker",
    "plan_cleanup",
]
