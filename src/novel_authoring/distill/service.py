"""Book Library integration for the upstream ``distill-novels`` skill."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from novel_authoring.db.database import Database
from novel_authoring.distill.models import DistillScope
from novel_authoring.distill.package import (
    DistillationPackageError,
    build_distillation_package,
    validate_distillation_package,
)
from novel_authoring.distill.preparation import discover_sources, prepare_sources
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.ingest.service import load_manifest
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.models import EditionPaths
from novel_authoring.storage.operations import book_root
from novel_authoring.utils import json_dumps, safe_book_id, stable_id, utc_now

DIMENSIONS = (
    "worldbuilding",
    "characters",
    "plot",
    "style",
    "narrative",
    "dialogue",
    "pacing",
    "themes",
    "continuity",
)
MODES = {"analyze-only", "create", "compare", "update"}
DEPTHS = {"compact", "standard", "deep"}


class DistillError(RuntimeError):
    """Raised when a distill preparation, handoff or publication is invalid."""


def parse_dimensions(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return list(DIMENSIONS)
    values = [value] if isinstance(value, str) else list(value)
    selected: list[str] = []
    for item in values:
        selected.extend(part.strip().lower() for part in item.split(","))
    if not selected or "all" in selected:
        return list(DIMENSIONS)
    unknown = sorted(set(selected) - set(DIMENSIONS))
    if unknown:
        raise DistillError(f"未知 distill dimension：{', '.join(unknown)}")
    return list(dict.fromkeys(selected))


def _validate_request(mode: str, depth: str, dimensions: list[str], source_count: int) -> None:
    if mode not in MODES:
        raise DistillError(f"mode 必须是：{', '.join(sorted(MODES))}")
    if depth not in DEPTHS:
        raise DistillError(f"depth 必须是：{', '.join(sorted(DEPTHS))}")
    if not dimensions:
        raise DistillError("至少选择一个 distill dimension")
    if mode == "compare" and source_count < 2:
        raise DistillError("compare 模式至少需要两个来源")


def _book_edition(database: Database, book_id: str, edition_id: str | None) -> EditionPaths:
    root = book_root(database, book_id)
    if not (root / "book.yaml").is_file():
        raise DistillError("distill 新流程要求 Canonical Book Library；请先运行 novel library add")
    selected = resolve_edition_id(database, book_id, edition_id)
    return BookLayout(root.parent).for_book(book_id).edition(selected)


def _canonical_sources(database: Database, book_id: str) -> list[Path]:
    root = book_root(database, book_id)
    manifest = load_manifest(root / "_system" / "source_manifest.json")
    source_root = Path(manifest.source_root)
    return [source_root / entry.relative_path for entry in manifest.files]


def _materialize_effective_edition_source(
    database: Database, book_id: str, edition: EditionPaths, preparation_id: str
) -> Path:
    """Freeze a derived edition's current effective chapters for Distill.

    ``edition_chapters`` is the existing source of truth for variant
    inheritance.  The generated snapshot is preparation data below the
    selected edition; it is not a replacement for the immutable ``book/`` or
    canonical source copy.
    """

    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, edition.edition_id)
    if not chapters:
        raise DistillError("selected edition 没有可供 distill 的有效章节")
    parts: list[str] = []
    for chapter in chapters:
        chapter_content = str(chapter.get("content") or "").strip("\n")
        if not chapter_content:
            continue
        title = str(chapter.get("title") or chapter.get("raw_heading") or "").strip()
        parts.append(f"## {title}\n{chapter_content}" if title else chapter_content)
    content = "\n\n".join(parts).strip("\n")
    if not content:
        raise DistillError("selected edition 的有效章节正文为空")
    root = edition.distill / "effective_sources"
    root.mkdir(parents=True, exist_ok=True)
    snapshot = root / f"{preparation_id}.md"
    snapshot.write_text(content + "\n", encoding="utf-8", newline="\n")
    return snapshot


def _source_document_id(database: Database, book_id: str, path: Path) -> str | None:
    resolved = path.expanduser().resolve()
    with database.connect() as connection:
        book = connection.execute(
            "SELECT source_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
        if book is None:
            return None
        try:
            relative = resolved.relative_to(Path(str(book["source_root"])).resolve())
        except ValueError:
            return None
        row = connection.execute(
            "SELECT document_id FROM source_documents WHERE book_id=? AND relative_path=?",
            (book_id, relative.as_posix()),
        ).fetchone()
    return None if row is None else str(row["document_id"])


def _annotate_frozen_chapters(
    database: Database,
    book_id: str,
    edition: EditionPaths,
    preparation_root: Path,
    *,
    self_book: bool,
) -> None:
    """Attach deterministic selected-edition chapter IDs to preparation segments."""

    if not self_book:
        return
    manifest_path = preparation_root / "manifest.json"
    chapter_index_path = preparation_root / "chapter_index.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chapter_index = json.loads(chapter_index_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(chapter_index, dict):
        raise DistillError("distill preparation index 必须是 object")
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, edition.edition_id)
    source_items = [item for item in manifest.get("sources", []) if isinstance(item, dict)]
    index_items = [item for item in chapter_index.get("sources", []) if isinstance(item, dict)]
    if len(source_items) != len(index_items):
        raise DistillError("distill preparation manifest 与 chapter_index source 不一致")
    for source_summary, source_index in zip(source_items, index_items, strict=True):
        source_path = Path(str(source_index.get("input_path") or ""))
        document_id = _source_document_id(database, book_id, source_path)
        source_summary["source_origin"] = DistillScope.SELF_BOOK.value
        source_index["source_origin"] = DistillScope.SELF_BOOK.value
        if document_id:
            source_summary["document_id"] = document_id
            source_index["document_id"] = document_id
        candidates = [
            chapter
            for chapter in chapters
            if not document_id or str(chapter.get("document_id")) == document_id
        ]
        if len(index_items) == 1 and not document_id:
            candidates = chapters
        candidates.sort(key=lambda item: int(item.get("ordinal", 0)))
        segments = [item for item in source_index.get("segments", []) if isinstance(item, dict)]
        for segment in segments:
            ordinal = int(segment.get("ordinal", 0))
            if ordinal < 1 or ordinal > len(candidates):
                continue
            chapter = candidates[ordinal - 1]
            segment.update(
                {
                    "chapter_id": str(chapter["chapter_id"]),
                    "source_span_id": chapter.get("source_span_id"),
                    "chapter_ordinal": int(chapter["ordinal"]),
                    "edition_id": edition.edition_id,
                    "document_id": chapter.get("document_id"),
                }
            )
    manifest["sources"] = source_items
    manifest["scope"] = DistillScope.SELF_BOOK.value
    manifest["source_scope"] = (
        "BOOK_CANONICAL_SOURCE"
        if edition.edition_id == "base"
        else "BOOK_EFFECTIVE_EDITION"
    )
    manifest["effective_content"] = {
        "selected_edition": edition.edition_id,
        "materialization": "edition_chapters",
        "chapter_count": len(chapters),
    }
    chapter_index["sources"] = index_items
    chapter_index["edition_id"] = edition.edition_id
    chapter_index["scope"] = DistillScope.SELF_BOOK.value
    manifest_path.write_text(json_dumps(manifest, indent=2) + "\n", encoding="utf-8")
    chapter_index_path.write_text(
        json_dumps(chapter_index, indent=2) + "\n", encoding="utf-8"
    )


def prepare_book_sources(
    database: Database,
    book_id: str,
    *,
    sources: Iterable[Path] | None = None,
    edition_id: str | None = None,
) -> dict[str, Any]:
    """Prepare source files under the selected edition's analysis area."""

    database.initialize()
    edition = _book_edition(database, book_id, edition_id)
    preparation_id = stable_id("distill-prep", book_id, edition.edition_id, utc_now())
    self_book = sources is None
    if sources is None and edition.edition_id == "base":
        input_paths = _canonical_sources(database, book_id)
    elif sources is None:
        input_paths = [
            _materialize_effective_edition_source(
                database, book_id, edition, preparation_id
            )
        ]
    else:
        input_paths = list(sources)
        if edition.edition_id == "base":
            canonical = {path.resolve() for path in _canonical_sources(database, book_id)}
            self_book = {path.resolve() for path in discover_sources(input_paths)} == canonical
        else:
            effective_root = edition.distill / "effective_sources"
            self_book = True
            for path in discover_sources(input_paths):
                try:
                    path.resolve().relative_to(effective_root.resolve())
                except ValueError:
                    self_book = False
                    break
    resolved = discover_sources(input_paths)
    output_root = edition.distill / "preparations" / preparation_id
    result = prepare_sources(resolved, output_root, preparation_id=preparation_id)
    manifest_path = Path(result["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scope = DistillScope.SELF_BOOK if self_book else DistillScope.EXTERNAL_REFERENCE
    source_scope = (
        "BOOK_CANONICAL_SOURCE"
        if self_book and edition.edition_id == "base"
        else "BOOK_EFFECTIVE_EDITION"
        if self_book
        else "REFERENCE_INPUT"
    )
    source_items = manifest.get("sources", [])
    if isinstance(source_items, list):
        for source_item in source_items:
            if isinstance(source_item, dict):
                source_item["source_origin"] = scope.value
    manifest.update(
        {
            "book_id": book_id,
            "edition_id": edition.edition_id,
            "scope": scope.value,
            "source_scope": source_scope,
            "effective_content": self_book,
            "source_manifest_path": str(
                book_root(database, book_id) / "_system" / "source_manifest.json"
            ),
        }
    )
    if isinstance(source_items, list):
        manifest["sources"] = source_items
    manifest_path.write_text(json_dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _annotate_frozen_chapters(
        database,
        book_id,
        edition,
        output_root,
        self_book=self_book,
    )
    result["book_id"] = book_id
    result["edition_id"] = edition.edition_id
    result["source_scope"] = manifest["source_scope"]
    result["scope"] = scope.value
    result["effective_content"] = self_book
    return result


def _read_preparation(root: Path) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise DistillError(f"distill preparation manifest 不存在：{manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DistillError(f"distill preparation manifest 无法读取：{manifest_path}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "distill-preparation-v1":
        raise DistillError("distill preparation manifest schema 不正确")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise DistillError("distill preparation 没有 source")
    return manifest


def _check_preparation_scope(manifest: dict[str, Any], book_id: str, edition_id: str) -> None:
    declared_book = manifest.get("book_id")
    declared_edition = manifest.get("edition_id")
    if declared_book is not None and str(declared_book) != book_id:
        raise DistillError("distill preparation 不属于当前 book")
    if declared_edition is not None and str(declared_edition) != edition_id:
        raise DistillError("distill preparation 不属于当前 edition")


def _request_scope(mode: str, prepared: dict[str, Any]) -> DistillScope:
    if mode == "compare":
        return DistillScope.COMPARATIVE_REFERENCE
    declared = str(prepared.get("scope") or "").upper()
    if declared in {item.value for item in DistillScope}:
        return DistillScope(declared)
    source_scope = str(prepared.get("source_scope") or "").upper()
    if source_scope in {"BOOK_CANONICAL_SOURCE", "BOOK_EFFECTIVE_EDITION"}:
        return DistillScope.SELF_BOOK
    return DistillScope.EXTERNAL_REFERENCE


def latest_preparation(
    database: Database, book_id: str, *, edition_id: str | None = None
) -> dict[str, Any]:
    database.initialize()
    edition = _book_edition(database, book_id, edition_id)
    candidates: list[tuple[str, Path, dict[str, Any]]] = []
    root = edition.distill / "preparations"
    if root.is_dir():
        for candidate in root.iterdir():
            if not candidate.is_dir():
                continue
            try:
                manifest = _read_preparation(candidate)
                _check_preparation_scope(manifest, book_id, edition.edition_id)
            except DistillError:
                continue
            candidates.append((str(manifest.get("created_at", "")), candidate, manifest))
    if not candidates:
        raise DistillError("当前 edition 没有可用 distill preparation；请先运行 distill prepare")
    _, candidate, manifest = max(candidates, key=lambda item: item[0])
    return {
        "preparation_id": str(manifest["preparation_id"]),
        "root": str(candidate),
        "manifest": str(candidate / "manifest.json"),
        "source_ids": [str(item["source_id"]) for item in manifest["sources"]],
        "source_count": len(manifest["sources"]),
        "warnings": list(manifest.get("warnings", [])),
        "scope": str(
            manifest.get("scope")
            or (
                DistillScope.SELF_BOOK.value
                if str(manifest.get("source_scope", "")).startswith("BOOK_")
                else DistillScope.EXTERNAL_REFERENCE.value
            )
        ),
        "effective_content": manifest.get("effective_content", False),
        "book_id": book_id,
        "edition_id": edition.edition_id,
    }


def create_distill_handoff(
    database: Database,
    book_id: str,
    *,
    sources: Iterable[Path] | None = None,
    preparation_id: str | None = None,
    mode: str = "create",
    dimensions: str | Iterable[str] | None = None,
    depth: str = "standard",
    requested_stage: str = "DISTILL",
    edition_id: str | None = None,
) -> dict[str, Any]:
    """Freeze a distill input package and create a desktop Codex handoff."""

    database.initialize()
    edition = _book_edition(database, book_id, edition_id)
    selected_dimensions = parse_dimensions(dimensions)
    if sources is not None:
        prepared = prepare_book_sources(
            database, book_id, sources=sources, edition_id=edition.edition_id
        )
    elif preparation_id:
        root = edition.distill / "preparations" / preparation_id
        manifest = _read_preparation(root)
        _check_preparation_scope(manifest, book_id, edition.edition_id)
        prepared = {
            "preparation_id": preparation_id,
            "root": str(root),
            "manifest": str(root / "manifest.json"),
            "source_ids": [str(item["source_id"]) for item in manifest["sources"]],
            "source_count": len(manifest["sources"]),
            "warnings": list(manifest.get("warnings", [])),
            "scope": str(
                manifest.get("scope")
                or (
                    DistillScope.SELF_BOOK.value
                    if str(manifest.get("source_scope", "")).startswith("BOOK_")
                    else DistillScope.EXTERNAL_REFERENCE.value
                )
            ),
            "effective_content": manifest.get("effective_content", False),
            "book_id": book_id,
            "edition_id": edition.edition_id,
        }
    else:
        prepared = latest_preparation(database, book_id, edition_id=edition.edition_id)
    _validate_request(mode, depth, list(selected_dimensions), int(prepared["source_count"]))
    scope = _request_scope(mode, prepared)
    base_reference = None
    if mode == "update":
        base_reference = latest_distill_reference(edition)
        if base_reference is None:
            raise DistillError("update 模式需要当前 edition 已发布的 distill skill")
    distill_id = stable_id(
        "distill",
        book_id,
        edition.edition_id,
        str(prepared["preparation_id"]),
        mode,
        ",".join(selected_dimensions),
        depth,
    )
    request = {
        "schema_version": "distill-request-v1",
        "distill_id": distill_id,
        "preparation_id": prepared["preparation_id"],
        "prepared_root": prepared["root"],
        "preparation_manifest": prepared["manifest"],
        "source_ids": prepared["source_ids"],
        "source_count": prepared["source_count"],
        "mode": mode,
        "dimensions": selected_dimensions,
        "depth": depth,
        "scope": scope.value,
        "scope_id": book_id,
        "published_root": str(edition.distill / "skills" / distill_id),
        "warnings": prepared["warnings"],
    }
    if base_reference is not None:
        request["base_skill_root"] = base_reference["skill_root"]
    from novel_authoring.workflows.handoffs import HandoffType, create_handoff

    return create_handoff(
        database,
        book_id,
        handoff_type=HandoffType.NOVEL_DISTILLATION,
        requested_stage=requested_stage,
        edition_id=edition.edition_id,
        distill_request=request,
    )


def _task_path(task_directory: Path) -> Path:
    candidate = task_directory / "input" / "task.json"
    return candidate if candidate.is_file() else task_directory / "task.json"


def _contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def import_distill_result(database: Database, book_id: str, handoff_id: str) -> dict[str, Any]:
    """Publish a validated skill into ``edition.analysis/distill``."""

    from novel_authoring.workflows.handoffs import (
        HandoffType,
        HandoffWorkflowError,
        append_event,
        validate_result_file,
    )

    database.initialize()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM workflow_handoffs WHERE handoff_id=? AND book_id=?",
            (handoff_id, book_id),
        ).fetchone()
    if row is None:
        raise DistillError(f"distill handoff 不存在：{handoff_id}")
    if str(row["handoff_type"]) != HandoffType.NOVEL_DISTILLATION.value:
        raise DistillError("指定 handoff 不是 NOVEL_DISTILLATION")
    try:
        result = validate_result_file(database, handoff_id)
    except HandoffWorkflowError as exc:
        raise DistillError(str(exc)) from exc
    task_directory = Path(str(row["task_directory"])).resolve()
    task = json.loads(_task_path(task_directory).read_text(encoding="utf-8"))
    request = task.get("distill")
    if not isinstance(request, dict):
        raise DistillError("handoff task 缺少 distill request")
    request = dict(request)
    if not str(request.get("scope") or "").strip():
        preparation_manifest = Path(str(request.get("preparation_manifest") or ""))
        try:
            prepared_manifest = _read_preparation(preparation_manifest.parent)
        except DistillError as exc:
            raise DistillError("无法为旧 distill request 推断 scope") from exc
        request["scope"] = _request_scope(
            str(request.get("mode") or "create"), prepared_manifest
        ).value
    request.setdefault("scope_id", book_id)
    distill_id = str(result.get("distill_id") or "")
    if not distill_id or safe_book_id(distill_id) != distill_id:
        raise DistillError("result distill_id 不是安全路径组件")
    if distill_id != str(request.get("distill_id")):
        raise DistillError("result distill_id 与 task 不一致")
    raw_root = str(result.get("distill_skill_root") or "")
    skill_root = Path(raw_root)
    if not skill_root.is_absolute():
        skill_root = task_directory / skill_root
    skill_root = skill_root.resolve()
    if not _contained(task_directory, skill_root) or not skill_root.is_dir():
        raise DistillError("distill_skill_root 必须位于 handoff task 目录内")
    if not (skill_root / "SKILL.md").is_file():
        raise DistillError("distill skill 缺少 SKILL.md")
    try:
        package_result = build_distillation_package(
            database,
            book_id,
            str(row["edition_id"]),
            request,
            skill_root,
        )
        package_summary = validate_distillation_package(
            skill_root,
            expected_book_id=book_id,
            expected_edition_id=str(row["edition_id"]),
            expected_scope=str(request.get("scope") or ""),
            expected_dimensions=[str(item) for item in request.get("dimensions", [])],
        )
    except DistillationPackageError as exc:
        raise DistillError(f"严格 Distillation Package 校验失败：{exc}") from exc
    edition = _book_edition(database, book_id, str(row["edition_id"]))
    destination = edition.distill / "skills" / distill_id
    if destination.exists():
        raise DistillError(f"distill skill 已存在，拒绝覆盖：{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_root, destination)
    published_at = utc_now()
    manifest = {
        "schema_version": "distill-published-v1",
        "distill_id": distill_id,
        "handoff_id": handoff_id,
        "book_id": book_id,
        "edition_id": str(row["edition_id"]),
        "published_at": published_at,
        "scope": request.get("scope"),
        "scope_id": request.get("scope_id", book_id),
        "package_version": package_result["manifest"].package_version,
        "package_root": str(destination / "machine"),
        "machine_manifest": str(destination / "machine" / "package.json"),
        "mapping_summary": package_summary.get("mapping_summary", {}),
        "mapping_reason_summary": package_summary.get("mapping_reason_summary", {}),
        "package_summary": package_summary,
        "request": request,
        "result": result,
        "skill_root": str(destination),
    }
    (destination / "distill_manifest.json").write_text(
        json_dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    latest_path = edition.distill / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(
        json_dumps(
            {
                "schema_version": "distill-latest-v1",
                "distill_id": distill_id,
                "skill_root": str(destination),
                "published_at": published_at,
                "scope": request.get("scope"),
                "book_id": book_id,
                "edition_id": str(row["edition_id"]),
                "dimensions": request.get("dimensions", []),
                "depth": request.get("depth"),
                "package_root": str(destination / "machine"),
                "machine_manifest": str(destination / "machine" / "package.json"),
                "usage": "REFERENCE_ONLY",
                "mapping_summary": package_summary.get("mapping_summary", {}),
                "mapping_reason_summary": package_summary.get(
                    "mapping_reason_summary", {}
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    profile_result: dict[str, object] | None = None
    if str(request.get("scope")) == DistillScope.SELF_BOOK.value:
        from novel_authoring.distill.profile import export_book_profile

        profile_result = export_book_profile(
            database, book_id, edition_id=str(row["edition_id"])
        )
    append_event(
        database,
        handoff_id,
        "DISTILL_PUBLISHED",
        {
            "distill_id": distill_id,
            "skill_root": str(destination),
            "scope": request.get("scope"),
            "package_root": str(destination / "machine"),
            "machine_manifest": str(destination / "machine" / "package.json"),
            "mapping_summary": package_summary.get("mapping_summary", {}),
            "mapping_reason_summary": package_summary.get("mapping_reason_summary", {}),
        },
    )
    return {
        "distill_id": distill_id,
        "handoff_id": handoff_id,
        "skill_root": str(destination),
        "latest": str(latest_path),
        "source_ids": request.get("source_ids", []),
        "dimensions": request.get("dimensions", []),
        "mode": request.get("mode"),
        "depth": request.get("depth"),
        "scope": request.get("scope"),
        "package_root": str(destination / "machine"),
        "machine_manifest": str(destination / "machine" / "package.json"),
        "mapping_summary": package_summary.get("mapping_summary", {}),
        "profile": profile_result,
        "canon_committed": False,
    }


def latest_distill_reference(edition: EditionPaths) -> dict[str, Any] | None:
    latest_path = edition.distill / "latest.json"
    if not latest_path.is_file():
        return None
    try:
        value = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    root = Path(str(value.get("skill_root", ""))).expanduser().resolve()
    if not _contained(edition.distill.resolve(), root) or not (root / "SKILL.md").is_file():
        return None
    published: dict[str, Any] = {}
    published_path = root / "distill_manifest.json"
    if published_path.is_file():
        try:
            loaded = json.loads(published_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                published = loaded
        except (OSError, UnicodeError, json.JSONDecodeError):
            published = {}
    request_value = published.get("request")
    request: dict[str, Any] = request_value if isinstance(request_value, dict) else {}
    package_root = root / "machine"
    machine_manifest = package_root / "package.json"
    mapping = value.get("mapping_summary") or published.get("mapping_summary") or {}
    if not isinstance(mapping, dict):
        mapping = {}
    mapping_reasons = (
        value.get("mapping_reason_summary")
        or published.get("mapping_reason_summary")
        or {}
    )
    if not isinstance(mapping_reasons, dict):
        mapping_reasons = {}
    scope = (
        value.get("scope")
        or published.get("scope")
        or request.get("scope")
        or DistillScope.EXTERNAL_REFERENCE.value
    )
    return {
        "distill_id": str(value.get("distill_id", "")),
        "scope": str(scope),
        "book_id": str(value.get("book_id") or published.get("book_id") or ""),
        "edition_id": str(
            value.get("edition_id") or published.get("edition_id") or edition.edition_id
        ),
        "dimensions": list(value.get("dimensions") or request.get("dimensions") or []),
        "depth": str(value.get("depth") or request.get("depth") or ""),
        "skill_root": str(root),
        "package_root": str(package_root) if package_root.is_dir() else None,
        "machine_manifest": str(machine_manifest) if machine_manifest.is_file() else None,
        "latest_path": str(latest_path),
        "usage": str(value.get("usage") or "REFERENCE_ONLY"),
        "mapping_summary": mapping,
        "mapping_reason_summary": mapping_reasons,
        "profile_root": str(edition.root.parents[1] / "book_profil"),
    }


__all__ = [
    "DIMENSIONS",
    "DEPTHS",
    "MODES",
    "DistillError",
    "create_distill_handoff",
    "import_distill_result",
    "latest_distill_reference",
    "latest_preparation",
    "parse_dimensions",
    "prepare_book_sources",
]
