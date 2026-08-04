"""Auditable legacy-layout migration into the canonical book library."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.manifest import (
    authority_path,
    manifest_hash,
    write_compatibility_mirror,
)
from novel_authoring.storage.models import BookPaths, EditionPaths, LayoutError
from novel_authoring.storage.registry import BookRegistry
from novel_authoring.utils import json_dumps, sha256_bytes, sha256_file, utc_now

_PATH_COLUMN_TOKENS = (
    "path",
    "root",
    "file",
    "artifact",
    "export",
    "directory",
    "prompt",
    "result",
    "event",
    "schema",
    "waiting",
)
_COUNT_TABLES = (
    "chapters",
    "source_spans",
    "chapter_features",
    "metric_observations",
    "metric_evidence_links",
    "metric_runs",
    "metric_run_results",
    "story_atlases",
    "workflow_handoffs",
    "canon_commits",
)


@dataclass(frozen=True, slots=True)
class MigrationOptions:
    book_id: str
    source_root: Path
    workspace_root: Path
    library_root: Path | None = None
    apply: bool = False
    allow_existing: bool = False


@dataclass(slots=True)
class MigrationPlan:
    book_id: str
    source_root: str
    workspace_root: str
    library_root: str
    target_root: str
    target_exists: bool
    source_files: list[dict[str, Any]] = field(default_factory=list)
    workspace_files: int = 0
    path_rewrites: list[dict[str, str]] = field(default_factory=list)
    counts_before: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    status: str = "DRY_RUN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "source_root": self.source_root,
            "workspace_root": self.workspace_root,
            "library_root": self.library_root,
            "target_root": self.target_root,
            "target_exists": self.target_exists,
            "source_files": self.source_files,
            "workspace_files": self.workspace_files,
            "path_rewrites": self.path_rewrites,
            "counts_before": self.counts_before,
            "warnings": self.warnings,
            "status": self.status,
        }


@dataclass(slots=True)
class MigrationResult:
    plan: MigrationPlan
    report_path: Path | None = None
    report_markdown_path: Path | None = None
    counts_after: dict[str, int] = field(default_factory=dict)
    source_hashes_after: dict[str, str] = field(default_factory=dict)
    residual_legacy_paths: list[str] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = self.plan.to_dict()
        value.update(
            {
                "report_path": str(self.report_path) if self.report_path else None,
                "report_markdown_path": (
                    str(self.report_markdown_path) if self.report_markdown_path else None
                ),
                "counts_after": self.counts_after,
                "source_hashes_after": self.source_hashes_after,
                "residual_legacy_paths": self.residual_legacy_paths,
                "verification": self.verification,
            }
        )
        return value


def plan_legacy_cleanup(
    library_root: Path | str | BookLayout,
    book_id: str,
) -> dict[str, Any]:
    """Build a dry-run plan for recoverably archiving old migration locations."""

    layout = (
        library_root
        if isinstance(library_root, BookLayout)
        else BookLayout(Path(library_root))
    )
    paths = layout.for_book(book_id)
    locations_file = paths.legacy_locations
    warnings: list[str] = []
    candidates: list[dict[str, Any]] = []
    if not locations_file.is_file():
        warnings.append(f"未找到 legacy_locations.json: {locations_file}")
    else:
        try:
            raw = json.loads(locations_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise LayoutError(f"legacy_locations.json 无法读取: {locations_file}: {exc}") from exc
        values = raw.get("legacy_locations", []) if isinstance(raw, dict) else []
        if isinstance(raw, dict) and not values:
            # Compatibility with the original migration metadata.  The
            # upgraded report is emitted on the next successful migration or
            # cleanup apply, while this read remains non-mutating.
            for key, kind in (("source_root", "source"), ("workspace_root", "workspace")):
                if raw.get(key):
                    values.append({"path": raw[key], "kind": kind, "retained": True})
        if not isinstance(values, list):
            raise LayoutError("legacy_locations.json 的 legacy_locations 必须是列表")
        for value in values:
            if isinstance(value, str):
                location = {"path": value, "kind": "workspace", "retained": True}
            elif isinstance(value, dict):
                location = value
            else:
                continue
            raw_path = str(location.get("path") or "").strip()
            if not raw_path or not bool(location.get("retained", True)):
                continue
            kind = str(location.get("kind") or "workspace").casefold()
            candidate = Path(raw_path).expanduser().resolve(strict=False)
            item: dict[str, Any] = {
                "path": str(candidate),
                "kind": kind,
                "exists": candidate.exists(),
                "status": "READY",
                "block_reasons": [],
            }
            if kind == "audit":
                item["status"] = "SKIPPED"
                item["skip_reason"] = "audit_default_retained"
                candidates.append(item)
                continue
            if not candidate.exists():
                item["status"] = "MISSING"
                item["block_reasons"].append("legacy_path_missing")
            if candidate.is_symlink():
                item["status"] = "BLOCKED"
                item["block_reasons"].append("symlink_or_reparse_point")
            if layout.contains(candidate):
                item["status"] = "BLOCKED"
                item["block_reasons"].append("legacy_path_inside_library")
            if candidate.exists() and not candidate.is_symlink():
                item["file_count"] = len(_files(candidate)) if candidate.is_dir() else 1
            candidates.append(item)
    candidate_hash = sha256_bytes(json_dumps(candidates).encode("utf-8"))
    blocked = [item for item in candidates if item.get("block_reasons")]
    return {
        "report_type": "legacy_cleanup",
        "report_version": 1,
        "mode": "DRY_RUN",
        "status": "BLOCKED" if blocked else "DRY_RUN",
        "book_id": paths.book_id,
        "library_root": str(layout.library_root),
        "legacy_locations_file": str(locations_file),
        "candidate_hash": candidate_hash,
        "confirmation": f"CLEANUP-LEGACY {paths.book_id} {candidate_hash}",
        "candidates": candidates,
        "warnings": warnings,
    }


def cleanup_legacy(
    library_root: Path | str | BookLayout,
    book_id: str,
    *,
    apply: bool = False,
    confirmation: str | None = None,
) -> dict[str, Any]:
    """Recoverably archive legacy roots, never permanently delete them."""

    report = plan_legacy_cleanup(library_root, book_id)
    if not apply:
        return report
    expected = str(report.get("confirmation") or "")
    if confirmation != expected:
        raise LayoutError("cleanup-legacy 必须提供精确 confirmation 字符串")
    if report.get("status") == "BLOCKED":
        raise LayoutError("cleanup-legacy dry-run 存在阻塞项，拒绝 apply")
    layout = (
        library_root
        if isinstance(library_root, BookLayout)
        else BookLayout(Path(library_root))
    )
    archive_root = layout.library_root / ".archive" / book_id / (
        "legacy-" + utc_now().replace(":", "").replace("+", "-")
    )
    archive_root.mkdir(parents=True, exist_ok=False)
    moved: list[dict[str, str]] = []
    try:
        for index, item in enumerate(report.get("candidates", []), start=1):
            if item.get("status") != "READY":
                continue
            source = Path(str(item["path"])).resolve(strict=False)
            if not source.exists():
                continue
            destination = archive_root / f"{index:02d}-{source.name}"
            if destination.exists():
                raise LayoutError(f"legacy archive 目标已存在: {destination}")
            shutil.move(str(source), str(destination))
            moved.append({"source": str(source), "destination": str(destination)})
    except Exception:
        # The archive remains recoverable if an individual move fails.
        raise
    result = dict(report)
    result.update(
        {
            "mode": "APPLIED",
            "status": "APPLIED",
            "archive_root": str(archive_root),
            "moved": moved,
            "applied_at": utc_now(),
        }
    )
    locations_file = layout.for_book(book_id).legacy_locations
    if locations_file.is_file():
        try:
            metadata = json.loads(locations_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            metadata = {}
        if isinstance(metadata, dict):
            metadata.setdefault("schema_version", "legacy-locations-v1")
            values = metadata.get("legacy_locations", [])
            if isinstance(values, list):
                moved_sources = {item["source"] for item in moved}
                upgraded: list[dict[str, Any]] = []
                for value in values:
                    if isinstance(value, str):
                        value = {"path": value, "kind": "workspace", "retained": True}
                    if not isinstance(value, dict):
                        continue
                    entry = dict(value)
                    if str(entry.get("path")) in moved_sources:
                        entry["retained"] = False
                        entry["archived_to"] = next(
                            item["destination"]
                            for item in moved
                            if item["source"] == str(entry.get("path"))
                        )
                    upgraded.append(entry)
                metadata["legacy_locations"] = upgraded
            metadata["legacy_archives"] = [item["destination"] for item in moved]
            metadata.setdefault("migration_history", []).append(
                {"cleanup_applied_at": utc_now(), "moved": moved}
            )
            _write_json(locations_file, metadata)
    return result


def plan_legacy_migration(options: MigrationOptions) -> MigrationPlan:
    """Build a read-only migration plan without creating the target."""

    source = _resolve_existing(options.source_root, "source_root")
    workspace = _resolve_existing(options.workspace_root, "workspace_root")
    layout = (
        BookLayout.default()
        if options.library_root is None
        else BookLayout(options.library_root)
    )
    paths = layout.for_book(options.book_id)
    if paths.root == workspace or paths.root == source:
        raise LayoutError("目标书库目录不能与 legacy source/workspace 相同")
    source_files = _source_inventory(source)
    workspace_files = len(_files(workspace))
    mapping = _path_mapping(source, workspace, paths)
    plan = MigrationPlan(
        book_id=paths.book_id,
        source_root=str(source),
        workspace_root=str(workspace),
        library_root=str(layout.library_root),
        target_root=str(paths.root),
        target_exists=paths.root.exists(),
        source_files=source_files,
        workspace_files=workspace_files,
        path_rewrites=[{"from": str(old), "to": str(new)} for old, new in mapping],
        counts_before=_database_counts(workspace / "state.sqlite3"),
    )
    if not (workspace / "state.sqlite3").is_file():
        plan.warnings.append("workspace_root/state.sqlite3 不存在；将无法保留数据库投影")
    if paths.root.exists():
        plan.warnings.append("target_root 已存在；apply 永远拒绝覆盖，allow_existing 仅为兼容参数")
    if not source_files:
        plan.warnings.append("source_root 没有可复制文件")
    return plan


def migrate_legacy(options: MigrationOptions) -> MigrationResult:
    """Migrate a legacy book, or return a dry-run result.

    Apply copies into a staging directory and atomically renames it into the
    target.  The legacy source/workspace are never removed by this function.
    """

    plan = plan_legacy_migration(options)
    if not options.apply:
        return MigrationResult(plan=plan)
    if plan.target_exists:
        raise LayoutError(f"目标目录已存在，拒绝覆盖: {plan.target_root}")

    layout = BookLayout(Path(plan.library_root))
    paths = layout.for_book(plan.book_id)
    source = Path(plan.source_root)
    workspace = Path(plan.workspace_root)
    layout.library_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".migration-{paths.book_id}-", dir=layout.library_root))
    stage_paths = BookPaths(stage / paths.book_id, paths.book_id)
    result: MigrationResult | None = None
    try:
        _materialize_stage(source, workspace, stage_paths)
        _rewrite_source_manifest_anchor(stage_paths.database, stage_paths.source_manifest)
        _rewrite_database_paths(
            stage_paths.database,
            # Persist final paths, not staging paths.  The staging directory is
            # renamed atomically below and must never leak into SQLite.
            _path_mapping(source, workspace, paths),
        )
        _verify_database_copy(workspace / "state.sqlite3", stage_paths.database)
        _verify_source_copy(source, stage_paths.source)
        _write_metadata(stage_paths, plan, source)
        final_root = paths.root
        if final_root.exists():
            raise LayoutError(f"目标目录已存在，拒绝覆盖: {final_root}")
        stage_paths.root.rename(final_root)
        final_manifest = authority_path(final_root)
        _rewrite_source_manifest(final_manifest, paths.source)
        write_compatibility_mirror(paths)
        _rewrite_source_manifest_anchor(paths.database, final_manifest)
        # The staging parent is empty after the atomic switch.
        with suppress(OSError):
            stage.rmdir()
        counts_after = _database_counts(paths.database)
        hashes_after = _source_hashes(paths.source)
        residual = _find_legacy_paths(paths.database, [source, workspace])
        verification = _verify_runtime(paths.database, paths.book_id)
        plan.status = "APPLIED"
        report = paths.system / "migration_report.json"
        report_markdown = paths.system / "migration_report.md"
        result = MigrationResult(
            plan=plan,
            report_path=report,
            report_markdown_path=report_markdown,
            counts_after=counts_after,
            source_hashes_after=hashes_after,
            residual_legacy_paths=residual,
            verification=verification,
        )
        _write_json(report, result.to_dict())
        _write_migration_markdown(report_markdown, result.to_dict())
        _write_legacy_locations(paths, plan, source, workspace)
        return result
    except Exception:
        if stage.exists() and layout.contains(stage):
            _remove_exact(stage, layout.library_root)
        raise


def _resolve_existing(value: Path, label: str) -> Path:
    resolved = Path(value).expanduser().resolve()
    if not resolved.exists():
        raise LayoutError(f"{label} 不存在: {resolved}")
    return resolved


def _files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.as_posix().casefold(),
    )


def _source_inventory(source: Path) -> list[dict[str, Any]]:
    files = [source] if source.is_file() else _files(source)
    base = source.parent if source.is_file() else source
    return [
        {
            "relative_path": path.relative_to(base).as_posix(),
            "absolute_path": str(path),
            "byte_size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]


def _source_hashes(source_root: Path) -> dict[str, str]:
    return {
        path.relative_to(source_root).as_posix(): sha256_file(path)
        for path in _files(source_root)
    }


def _path_mapping(
    source: Path,
    workspace: Path,
    target: BookPaths,
) -> list[tuple[Path, Path]]:
    edition = target.edition("base")
    mappings: list[tuple[Path, Path]] = [(source, target.source)]
    old_editions = workspace / "editions"
    if old_editions.is_dir():
        for old_edition in old_editions.iterdir():
            if not old_edition.is_dir():
                continue
            target_edition = target.edition(old_edition.name)
            mappings.extend(
                [
                    (old_edition / "story_atlas", target_edition.story_atlas),
                    (old_edition / "initialization", target_edition.initialization),
                    (old_edition / "handoffs", target_edition.operations),
                ]
            )
    for path in workspace.iterdir():
        if path.name in {"state.sqlite3", "state.sqlite3-shm", "state.sqlite3-wal", "editions"}:
            continue
        if path.name == "exports":
            mappings.append((path, edition.archive_exports / "legacy-root-exports"))
        elif path.name == "snapshots":
            mappings.append((path, edition.writing / "snapshots"))
        elif path.is_dir():
            mappings.append((path, edition.writing / path.name))
        elif path.is_file():
            destination = (
                target.root / "source_manifest.json"
                if path.name == "source_manifest.json"
                else target.system / "legacy" / path.name
            )
            mappings.append((path, destination))
    # Existing services treat books.workspace_root as the book directory
    # itself (the historical value was workspace/<book_id>), while the SQLite
    # file now lives in _system.  Keep that public DB meaning compatible.
    mappings.append((workspace, target.root))
    return sorted(mappings, key=lambda item: len(item[0].parts), reverse=True)


def _map_path(value: str, mappings: list[tuple[Path, Path]]) -> str | None:
    candidate = Path(value).expanduser()
    raw = os.path.normcase(os.path.normpath(str(candidate)))
    for old, new in mappings:
        old_raw = os.path.normcase(os.path.normpath(str(old)))
        if raw == old_raw or raw.startswith(old_raw + os.sep):
            relative = candidate.relative_to(old)
            return str(new / relative)
    return None


def _rewrite_database_paths(database: Path, mappings: list[tuple[Path, Path]]) -> int:
    if not database.is_file():
        return 0
    changed = 0
    connection = sqlite3.connect(database)
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            columns = [
                str(row[1])
                for row in connection.execute(f'PRAGMA table_info("{_quote(table)}")')
            ]
            path_columns = [
                column
                for column in columns
                if any(token in column.casefold() for token in _PATH_COLUMN_TOKENS)
            ]
            for column in path_columns:
                rows = connection.execute(
                    f'SELECT DISTINCT "{_quote(column)}" FROM "{_quote(table)}" '
                    f'WHERE typeof("{_quote(column)}") = \'text\''
                ).fetchall()
                for row in rows:
                    value = row[0]
                    if not isinstance(value, str):
                        continue
                    replacement = _map_path(value, mappings)
                    if replacement is None or replacement == value:
                        continue
                    cursor = connection.execute(
                        f'UPDATE "{_quote(table)}" SET "{_quote(column)}"=? '
                        f'WHERE "{_quote(column)}"=?',
                        (replacement, value),
                    )
                    changed += cursor.rowcount
        connection.commit()
    finally:
        connection.close()
    return changed


def _quote(identifier: str) -> str:
    return identifier.replace('"', '""')


def _database_counts(database: Path) -> dict[str, int]:
    if not database.is_file():
        return {}
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        return {
            table: int(connection.execute(f'SELECT count(*) FROM "{_quote(table)}"').fetchone()[0])
            for table in _COUNT_TABLES
            if table in tables
        }
    finally:
        connection.close()


def _verify_runtime(database: Path, book_id: str) -> dict[str, Any]:
    """Run read-only integrity, event projection and local Web dependency checks."""

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = [
            tuple(row)
            for row in connection.execute("PRAGMA foreign_key_check").fetchall()
        ]
        from novel_authoring.canon.projection import projection_from_connection

        projection = projection_from_connection(connection, book_id, "base")
        projection_value = {
            "through_event_seq": projection.through_event_seq,
            "sha256": projection.sha256(),
        }
    finally:
        connection.close()
    web_doctor: dict[str, Any]
    try:
        import fastapi  # noqa: F401
        import jinja2  # noqa: F401
        import uvicorn  # noqa: F401

        web_doctor = {"ok": True, "executor": "local"}
    except ImportError as exc:
        web_doctor = {"ok": False, "error": str(exc)}
    return {
        "sqlite_integrity": integrity,
        "foreign_key_violations": foreign_keys,
        "projection_rebuild": projection_value,
        "web_doctor": web_doctor,
    }


def _verify_database_copy(source: Path, target: Path) -> None:
    before = _database_counts(source)
    after = _database_counts(target)
    if before != after:
        raise LayoutError(f"迁移数据库计数不一致: before={before}, after={after}")


def _verify_source_copy(source: Path, target: Path) -> None:
    expected = {item["relative_path"]: item["sha256"] for item in _source_inventory(source)}
    actual = _source_hashes(target)
    if expected != actual:
        raise LayoutError(f"来源副本哈希不一致: expected={expected}, actual={actual}")


def _materialize_stage(source: Path, workspace: Path, target: BookPaths) -> None:
    target.root.mkdir(parents=True, exist_ok=True)
    _copy_source(source, target.source)
    target.system.mkdir(parents=True, exist_ok=True)
    database = workspace / "state.sqlite3"
    if database.is_file():
        _sqlite_backup(database, target.database)
    edition = target.edition("base")
    for directory in edition.all_directories():
        directory.mkdir(parents=True, exist_ok=True)
    _copy_legacy_workspace(workspace, target)


def _copy_source(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        _copy_file(source, destination / source.name)
        return
    for path in _files(source):
        relative = path.relative_to(source)
        _copy_file(path, destination / relative)


def _copy_legacy_workspace(workspace: Path, target: BookPaths) -> None:
    edition = target.edition("base")
    for path in workspace.iterdir():
        if path.name in {"state.sqlite3", "state.sqlite3-shm", "state.sqlite3-wal"}:
            continue
        if path.name == "editions" and path.is_dir():
            _copy_legacy_editions(path, target)
        elif path.name == "exports" and path.is_dir():
            _archive_tree(path, edition.archive_exports / "legacy-root-exports.zip")
        elif path.name == "snapshots" and path.is_dir():
            _copy_tree_no_symlink(path, edition.writing / "snapshots")
        elif path.name in {"agent_tasks", "agent_outputs"} and path.is_dir():
            # These directories are imported into operation workspaces below;
            # never recreate them under a canonical book root.
            continue
        elif path.is_dir():
            _copy_tree_no_symlink(path, edition.writing / path.name)
        elif path.is_file():
            if path.name == "source_manifest.json":
                destination = target.root / "source_manifest.json"
                _copy_file(path, destination)
                _rewrite_source_manifest(destination, target.source)
                _copy_file(destination, target.source_manifest)
            else:
                destination = target.system / "legacy" / path.name
                _copy_file(path, destination)
    _import_legacy_agent_tasks(workspace, edition)


def _import_legacy_agent_tasks(workspace: Path, edition: EditionPaths) -> None:
    """Import old agent task/output pairs into auditable operations."""

    task_root = workspace / "agent_tasks"
    output_root = workspace / "agent_outputs"
    task_ids = {
        path.name
        for base in (task_root, output_root)
        if base.is_dir()
        for path in base.iterdir()
        if path.is_dir()
    }
    for task_id in sorted(task_ids):
        operation = edition.operation(task_id)
        for directory in operation.all_directories():
            directory.mkdir(parents=True, exist_ok=True)
        old_task = task_root / task_id
        old_output = output_root / task_id
        if old_task.is_dir():
            _copy_tree_no_symlink(old_task, operation.input)
        if old_output.is_dir():
            _copy_tree_no_symlink(old_output, operation.output)
        _write_json(
            operation.manifest,
            {
                "operation_id": task_id,
                "operation_kind": "LEGACY_IMPORTED_TASK",
                "legacy_imported": True,
                "legacy_task_root": str(old_task),
                "legacy_output_root": str(old_output),
                "imported_at": utc_now(),
            },
        )
        if not operation.status.is_file():
            _write_json(operation.status, {"status": "IMPORTED", "legacy_imported": True})
        if not operation.events.is_file():
            operation.events.write_text(
                json_dumps({"event": "LEGACY_IMPORTED", "operation_id": task_id}) + "\n",
                encoding="utf-8",
            )


def _copy_legacy_editions(old_editions: Path, target: BookPaths) -> None:
    for old_edition in old_editions.iterdir():
        if not old_edition.is_dir():
            continue
        edition = target.edition(old_edition.name)
        for path in old_edition.iterdir():
            if path.name == "story_atlas" and path.is_dir():
                _copy_tree_no_symlink(path, edition.story_atlas)
            elif path.name == "initialization" and path.is_dir():
                _copy_tree_no_symlink(path, edition.initialization)
            elif path.name == "handoffs" and path.is_dir():
                for handoff in path.iterdir():
                    if handoff.is_dir():
                        _import_handoff(handoff, edition)
            elif path.is_dir():
                _copy_tree_no_symlink(path, edition.writing / "legacy-edition" / path.name)
            elif path.is_file():
                _copy_file(path, edition.writing / "legacy-edition" / path.name)


def _import_handoff(old_root: Path, edition: EditionPaths) -> None:
    operation = edition.operation(old_root.name)
    for directory in operation.all_directories():
        directory.mkdir(parents=True, exist_ok=True)
    for path in old_root.iterdir():
        if path.name == "status.json":
            _copy_file(path, operation.status)
        elif path.name == "events.jsonl":
            _copy_file(path, operation.events)
        elif path.name == "result.json":
            _copy_file(path, operation.output / path.name)
        elif path.name in {
            "prompt.md",
            "task.json",
            "output_schema.json",
            "context_manifest.json",
            "metric_context.json",
        }:
            _copy_file(path, operation.input / path.name)
        elif path.is_dir():
            _copy_tree_no_symlink(path, operation.artifacts / path.name)
        else:
            _copy_file(path, operation.artifacts / path.name)
    if not operation.manifest.exists():
        _write_json(
            operation.manifest,
            {
                "operation_id": operation.operation_id,
                "legacy_imported": True,
                "legacy_root": str(old_root),
                "imported_at": utc_now(),
            },
        )
    if not operation.events.exists():
        operation.events.write_text(
            json_dumps(
                {
                    "event": "LEGACY_IMPORTED",
                    "operation_id": operation.operation_id,
                    "imported_at": utc_now(),
                }
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if not operation.status.exists():
        _write_json(operation.status, {"status": "IMPORTED", "legacy_imported": True})


def _sqlite_backup(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
        target_connection.commit()
    finally:
        target_connection.close()
        source_connection.close()


def _copy_tree_no_symlink(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise LayoutError(f"不允许依赖 symlink: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        target = destination / path.name
        if path.is_symlink():
            raise LayoutError(f"不允许依赖 symlink: {path}")
        if path.is_dir():
            _copy_tree_no_symlink(path, target)
        elif path.is_file():
            _copy_file(path, target)


def _copy_file(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise LayoutError(f"不允许依赖 symlink: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _rewrite_source_manifest(path: Path, source_root: Path) -> None:
    """Keep the compatibility manifest readable after a root relocation."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise LayoutError(f"source_manifest.json 无法解析: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LayoutError(f"source_manifest.json 必须是 object: {path}")
    value["source_root"] = str(source_root)
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _rewrite_source_manifest_anchor(database: Path, manifest: Path) -> None:
    """Update every persisted source-manifest anchor after relocation."""

    if not database.is_file() or not manifest.is_file():
        return
    digest = manifest_hash(manifest)
    connection = sqlite3.connect(database)
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            columns = {
                str(row[1])
                for row in connection.execute(f'PRAGMA table_info("{_quote(table)}")')
            }
            if "source_manifest_sha256" in columns:
                connection.execute(
                    f'UPDATE "{_quote(table)}" SET source_manifest_sha256=?',
                    (digest,),
                )
        connection.commit()
    finally:
        connection.close()


def _archive_tree(source: Path, destination: Path) -> None:
    """Archive a potentially very deep legacy tree without recreating it.

    Windows legacy snapshots can exceed MAX_PATH when nested below the new
    library root.  A zip archive preserves every relative file and hash while
    keeping the canonical path short and making the old export explicitly
    archival rather than a live Web artifact.
    """

    if source.is_symlink():
        raise LayoutError(f"不允许依赖 symlink: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        manifest: list[dict[str, Any]] = []
        for path in _files(source):
            if path.is_symlink():
                raise LayoutError(f"不允许依赖 symlink: {path}")
            relative = path.relative_to(source).as_posix()
            archive.write(path, arcname=relative)
            manifest.append(
                {
                    "relative_path": relative,
                    "byte_size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        archive.writestr(
            "LEGACY_ARCHIVE_MANIFEST.json",
            json_dumps(
                {
                    "source_root": str(source),
                    "created_at": utc_now(),
                    "files": manifest,
                },
                indent=2,
            )
            + "\n",
        )


def _write_metadata(target: BookPaths, plan: MigrationPlan, source: Path) -> None:
    registry = BookRegistry(BookLayout(target.root.parent.parent))
    source_files = [item["relative_path"] for item in plan.source_files]
    latest_chapter: int | None = None
    current_atlas_id: str | None = None
    if target.database.is_file():
        connection = sqlite3.connect(target.database)
        try:
            chapter_row = connection.execute(
                "SELECT MAX(ordinal) FROM chapters WHERE book_id=?", (target.book_id,)
            ).fetchone()
            latest_chapter = (
                None
                if chapter_row is None or chapter_row[0] is None
                else int(chapter_row[0])
            )
            atlas_row = connection.execute(
                "SELECT atlas_id FROM story_atlases WHERE book_id=? "
                "ORDER BY atlas_version DESC, created_at DESC LIMIT 1",
                (target.book_id,),
            ).fetchone()
            current_atlas_id = None if atlas_row is None else str(atlas_row[0])
        finally:
            connection.close()
    current_initialization_id = _latest_initialization_id(target.edition("base").initialization)
    values: dict[str, Any] = {
        "schema_version": "book-v1",
        "layout_version": "library-v1",
        "book_id": target.book_id,
        "title": target.book_id,
        "active_edition_id": "base",
        "database_path": "_system/state.sqlite3",
        "slug": target.book_id,
        "source_storage_mode": "COPY_READ_ONLY",
        "source_files": list(source_files),
        "created_at": utc_now(),
        "latest_chapter": latest_chapter,
        "current_atlas_id": current_atlas_id,
        "current_initialization_id": current_initialization_id,
        "latest_export": "editions/base/exports/latest",
        "source": {
            "root": "source",
            "files": list(source_files),
            "sha256": plan.source_files[0]["sha256"] if len(plan.source_files) == 1 else None,
            "byte_size": plan.source_files[0]["byte_size"] if len(plan.source_files) == 1 else None,
        },
        "legacy_locations": [
            _legacy_location_entry(Path(plan.source_root), "source"),
            _legacy_location_entry(Path(plan.workspace_root), "workspace"),
        ],
        "readiness_status": "MIGRATED",
        "migrated_at": utc_now(),
    }
    registry.write(target, values)
    registry.write_readme(target, values)


def _legacy_location_entry(path: Path, kind: str, *, retained: bool = True) -> dict[str, Any]:
    return {
        "path": str(path.expanduser().resolve(strict=False)),
        "kind": kind,
        "retained": retained,
        "sha256_manifest": _legacy_location_hash(path),
        "migrated_at": utc_now(),
    }


def _legacy_location_hash(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        inventory = _source_inventory(path)
    except (OSError, ValueError):
        inventory = []
    return sha256_bytes(json_dumps(inventory).encode("utf-8"))


def _write_legacy_locations(
    paths: BookPaths,
    plan: MigrationPlan,
    source: Path,
    workspace: Path,
) -> None:
    """Persist the v1 legacy-location schema and an immutable history record."""

    migrated_at = utc_now()
    entries = [
        {**_legacy_location_entry(source, "source"), "migrated_at": migrated_at},
        {**_legacy_location_entry(workspace, "workspace"), "migrated_at": migrated_at},
    ]
    history = {
        "migrated_at": migrated_at,
        "source_root": str(source),
        "workspace_root": str(workspace),
        "target_root": str(paths.root),
        "path_rewrites": plan.path_rewrites,
    }
    _write_json(
        paths.legacy_locations,
        {
            "schema_version": "legacy-locations-v1",
            "book_id": paths.book_id,
            "legacy_locations": entries,
            "migration_history": [history],
        },
    )
    # Keep the full pre-consolidation record in an append-only history file;
    # cleanup updates only the retained flags and archive references above.
    _write_json(paths.system / "migration_history.json", [history])


def _latest_initialization_id(root: Path) -> str | None:
    manifests = sorted(
        root.glob("*/initialization_manifest.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for path in manifests:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        if isinstance(value, dict) and value.get("initialization_id"):
            return str(value["initialization_id"])
    return None


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _write_migration_markdown(path: Path, value: dict[str, Any]) -> None:
    summary = value.get("counts_after", {})
    lines = [
        "# Legacy Migration Report",
        "",
        f"- book_id: `{value.get('book_id', '')}`",
        f"- status: `{value.get('status', '')}`",
        f"- target: `{value.get('target_root', '')}`",
        f"- source: `{value.get('source_root', '')}`",
        f"- workspace: `{value.get('workspace_root', '')}`",
        "",
        "## Counts after migration",
        "",
    ]
    lines.extend(f"- {key}: {item}" for key, item in sorted(summary.items()))
    lines.extend(
        [
            "",
            "## Verification",
            "",
            "```json",
            json_dumps(value.get("verification", {}), indent=2),
            "```",
            "",
            "旧 source/workspace 默认保留；详见 `legacy_locations.json`。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _find_legacy_paths(database: Path, roots: list[Path]) -> list[str]:
    if not database.is_file():
        return []
    normalized = [os.path.normcase(os.path.normpath(str(root))) for root in roots]
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    residual: list[str] = []
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            columns = [
                str(row[1])
                for row in connection.execute(f'PRAGMA table_info("{_quote(table)}")')
            ]
            path_columns = [
                column
                for column in columns
                if any(token in column.casefold() for token in _PATH_COLUMN_TOKENS)
            ]
            for column in path_columns:
                for row in connection.execute(
                    f'SELECT "{_quote(column)}" FROM "{_quote(table)}" '
                    f'WHERE typeof("{_quote(column)}") = \'text\''
                ):
                    value = row[0]
                    if isinstance(value, str):
                        raw = os.path.normcase(os.path.normpath(value))
                        if any(raw == root or raw.startswith(root + os.sep) for root in normalized):
                            residual.append(f"{table}.{column}: {value}")
    finally:
        connection.close()
    return residual


def _remove_exact(target: Path, allowed_root: Path) -> None:
    resolved = target.resolve(strict=False)
    root = allowed_root.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise LayoutError(f"拒绝删除 library_root 外路径: {resolved}") from exc
    if resolved == root:
        raise LayoutError("拒绝删除 library_root 本身")
    if resolved.is_dir():
        shutil.rmtree(resolved)
    elif resolved.exists():
        resolved.unlink()


__all__ = [
    "cleanup_legacy",
    "MigrationOptions",
    "MigrationPlan",
    "MigrationResult",
    "migrate_legacy",
    "plan_legacy_cleanup",
    "plan_legacy_migration",
]
