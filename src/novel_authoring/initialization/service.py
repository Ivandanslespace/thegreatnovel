# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.manifest import authority_path, manifest_hash
from novel_authoring.storage.operations import ensure_operation
from novel_authoring.utils import json_dumps, sha256_file, stable_id, utc_now


class InitializationError(RuntimeError):
    """A deterministic initialization contract or state error."""


class InitializationState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SOURCE_MAPPED = "SOURCE_MAPPED"
    ARC_EXTRACTION_RUNNING = "ARC_EXTRACTION_RUNNING"
    ENTITY_RESOLUTION_RUNNING = "ENTITY_RESOLUTION_RUNNING"
    SYNTHESIS_RUNNING = "SYNTHESIS_RUNNING"
    ATLAS_VALIDATION_RUNNING = "ATLAS_VALIDATION_RUNNING"
    METRIC_BOOTSTRAP_RUNNING = "METRIC_BOOTSTRAP_RUNNING"
    VISUAL_RENDERING_RUNNING = "VISUAL_RENDERING_RUNNING"
    READY_WITH_GAPS = "READY_WITH_GAPS"
    READY = "READY"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


class InitializationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChapterCoverage(InitializationBase):
    ordinal: int = Field(ge=1)
    raw_heading: str
    logical_heading: str
    chapter_id: str
    source_span_ids: list[str] = Field(default_factory=list)
    content_sha256: str
    char_count: int = Field(ge=0)
    inferred_volume: str | None = None
    assigned_arc_id: str
    analysis_status: str = "PENDING"


class ArcRecord(InitializationBase):
    arc_id: str
    ordinal: int = Field(ge=1)
    start_chapter: int = Field(ge=1)
    end_chapter: int = Field(ge=1)
    chapter_ids: list[str]
    source_span_ids: list[str]
    char_count: int = Field(ge=0)
    inferred_volume: str | None = None
    boundary_reason: str
    status: str = "PENDING"


class ArcManifest(InitializationBase):
    schema_version: str = "arc-manifest-v1"
    initialization_id: str
    book_id: str
    edition_id: str
    arcs: list[ArcRecord]
    max_chapters_per_arc: int = 20
    char_limit: int = Field(default=80_000, ge=1)


class SourceCoverage(InitializationBase):
    schema_version: str = "source-coverage-v1"
    book_id: str
    edition_id: str
    source_manifest_sha256: str
    effective_chapter_count: int = Field(ge=0)
    covered_chapter_count: int = Field(ge=0)
    chapter_coverage: float = Field(ge=0, le=1)
    chapters: list[ChapterCoverage]
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def counts_match(self) -> SourceCoverage:
        if self.covered_chapter_count > self.effective_chapter_count:
            raise ValueError("covered_chapter_count 不能超过 effective_chapter_count")
        return self


class ArcExtractionOutput(InitializationBase):
    """Strict top-level Arc output; semantic payloads remain evidence-bearing dicts."""

    schema_version: str = "arc-extraction-v1"
    initialization_id: str
    arc_id: str
    source_evidence: list[dict[str, Any]] = Field(default_factory=list)
    characters: list[dict[str, Any]] = Field(default_factory=list)
    aliases: list[dict[str, Any]] = Field(default_factory=list)
    factions: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    abilities: list[dict[str, Any]] = Field(default_factory=list)
    ability_evolution: list[dict[str, Any]] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    resources: list[dict[str, Any]] = Field(default_factory=list)
    production_chains: list[dict[str, Any]] = Field(default_factory=list)
    regions: list[dict[str, Any]] = Field(default_factory=list)
    region_connections: list[dict[str, Any]] = Field(default_factory=list)
    world_rules: list[dict[str, Any]] = Field(default_factory=list)
    rule_exceptions: list[dict[str, Any]] = Field(default_factory=list)
    major_events: list[dict[str, Any]] = Field(default_factory=list)
    promises: list[dict[str, Any]] = Field(default_factory=list)
    hooks: list[dict[str, Any]] = Field(default_factory=list)
    main_threads: list[dict[str, Any]] = Field(default_factory=list)
    secondary_threads: list[dict[str, Any]] = Field(default_factory=list)
    protagonist_decisions: list[dict[str, Any]] = Field(default_factory=list)
    leverage_events: list[dict[str, Any]] = Field(default_factory=list)
    payoff_events: list[dict[str, Any]] = Field(default_factory=list)
    pressure_events: list[dict[str, Any]] = Field(default_factory=list)
    stage_transition_signals: list[dict[str, Any]] = Field(default_factory=list)
    chapter_semantic_features: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_questions: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_boundary(self) -> ArcExtractionOutput:
        collections = (
            "characters",
            "factions",
            "relationships",
            "abilities",
            "items",
            "resources",
            "regions",
            "world_rules",
            "major_events",
            "promises",
            "hooks",
            "main_threads",
            "secondary_threads",
            "protagonist_decisions",
            "leverage_events",
            "payoff_events",
            "pressure_events",
            "contradictions",
        )
        for collection in collections:
            for item in getattr(self, collection):
                status = str(item.get("information_status", "CANON")).upper()
                spans = item.get("source_span_ids") or item.get("source_evidence") or []
                if status == "CANON" and not spans:
                    raise ValueError(f"{collection} 的 CANON 记录必须有 source_span_ids")
                if status == "INFERENCE":
                    missing = [
                        key
                        for key in ("reasoning_summary", "confidence", "counter_evidence")
                        if key not in item
                    ]
                    if missing:
                        raise ValueError(f"{collection} 的 INFERENCE 记录缺少 {missing}")
        return self


class EntityResolutionResult(InitializationBase):
    schema_version: str = "entity-resolution-v1"
    initialization_id: str
    entity_resolution_map: list[dict[str, Any]] = Field(default_factory=list)
    alias_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_identity_candidates: list[dict[str, Any]] = Field(default_factory=list)
    identified_major_entities: int = Field(default=0, ge=0)
    resolved_major_entities: int = Field(default=0, ge=0)


class InitializationReadiness(InitializationBase):
    status: str
    chapter_coverage: float = Field(ge=0, le=1)
    arc_coverage: float = Field(ge=0, le=1)
    source_mapping_coverage: float = Field(default=0.0, ge=0, le=1)
    arc_output_coverage: float = Field(default=0.0, ge=0, le=1)
    chapter_semantic_feature_coverage: float = Field(default=0.0, ge=0, le=1)
    metric_observation_coverage: float = Field(default=0.0, ge=0, le=1)
    recent_detailed_metric_coverage: float = Field(default=0.0, ge=0, le=1)
    current_chapter_metric_coverage: float = Field(default=0.0, ge=0, le=1)
    metric_bootstrap_status: str = "NOT_READY"
    metric_bootstrap: dict[str, Any] = Field(default_factory=dict)
    canon_evidence_coverage: float = Field(ge=0, le=1)
    entity_resolution_coverage: float = Field(ge=0, le=1)
    core_graphs_complete: bool = False
    protagonist_confirmed: bool = False
    current_thread_confirmed: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    review_queue: list[str] = Field(default_factory=list)


class InitializationManifest(InitializationBase):
    schema_version: str = "novel-initialization-v1"
    initialization_id: str
    book_id: str
    edition_id: str
    source_manifest_sha256: str
    effective_content_sha256: str
    created_at: str
    pipeline: list[str]
    state: InitializationState
    source_coverage_path: str
    arc_manifest_path: str
    contract_hashes: dict[str, str]
    chapter_count: int = Field(ge=0)
    arc_count: int = Field(ge=0)
    current_core_requirements: list[str]
    future_can_remain_incomplete: bool = True


_HEADING_WORDS = re.compile(r"(?:地图|区域|基地|城市|避难所|阶段|副本|领地|世界|联盟|大区|车队)")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _book_workspace(database: Database, book_id: str) -> Path:
    row = database.scalar("SELECT workspace_root FROM books WHERE book_id=?", (book_id,))
    if row is None:
        raise InitializationError(f"未知 book_id：{book_id}")
    return Path(str(row)).resolve()


def initialization_root(
    database: Database,
    book_id: str,
    edition_id: str | None = None,
    initialization_id: str | None = None,
) -> Path:
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    book_root = _book_workspace(database, book_id)
    if (book_root / "book.yaml").is_file():
        root = BookLayout(book_root.parent).for_book(book_id).edition(selected).initialization
    else:
        root = book_root / "editions" / selected / "initialization"
    if initialization_id:
        root = root / initialization_id
    return root


def _source_manifest_hash(database: Database, book_id: str) -> str:
    root = _book_workspace(database, book_id)
    path = authority_path(root)
    return manifest_hash(path) if path.is_file() else ""


def _infer_volume(row: dict[str, Any]) -> str | None:
    value = row.get("volume_title")
    if value:
        return str(value)
    heading = str(row.get("raw_heading") or row.get("title") or "")
    return heading if _HEADING_WORDS.search(heading) else None


def _chapter_rows(database: Database, book_id: str, edition_id: str) -> list[dict[str, Any]]:
    with database.connect() as connection:
        return [dict(row) for row in edition_chapters(connection, book_id, edition_id)]


def calculate_source_coverage(
    database: Database, book_id: str, edition_id: str | None = None
) -> dict[str, Any]:
    """Calculate source/span coverage from database intervals, not declarations."""
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    chapters = _chapter_rows(database, book_id, selected)
    anomalies: list[str] = []
    ordinals = [int(item["ordinal"]) for item in chapters]
    if ordinals != list(range(1, len(ordinals) + 1)):
        anomalies.append("章节 source ordinal 不连续或重复")
    missing_spans: list[str] = []
    duplicate_spans: list[str] = []
    with database.connect() as connection:
        spans = connection.execute(
            "SELECT span_id, chapter_id, document_id, start_char, end_char, text_sha256 "
            "FROM source_spans WHERE book_id=? ORDER BY document_id, start_char, span_id",
            (book_id,),
        ).fetchall()
    span_rows = [dict(row) for row in spans]
    for item in chapters:
        chapter_id = str(item["chapter_id"])
        related = [row for row in span_rows if str(row.get("chapter_id")) == chapter_id]
        if not related:
            missing_spans.append(chapter_id)
        if len(related) > 1:
            duplicate_spans.append(chapter_id)
        if related and str(related[0].get("text_sha256")) != str(item.get("content_sha256")):
            anomalies.append(f"chapter {chapter_id} content hash 与 source span 不一致")
    by_document: dict[str, list[tuple[int, int]]] = {}
    for row in span_rows:
        by_document.setdefault(str(row["document_id"]), []).append(
            (int(row["start_char"]), int(row["end_char"]))
        )
    document_diagnostics: list[dict[str, Any]] = []
    whole_source_ok = True
    for document_id, intervals in by_document.items():
        intervals = sorted(intervals)
        overlap = any(
            end > next_start
            for (_, end), (next_start, _) in zip(intervals, intervals[1:], strict=False)
        )
        start = intervals[0][0] if intervals else 0
        end = max((item[1] for item in intervals), default=0)
        union = 0
        cursor = start
        for left, right in intervals:
            if left > cursor:
                whole_source_ok = False
            cursor = max(cursor, right)
            union = cursor - start
        if overlap:
            anomalies.append(f"document {document_id} source span 存在重叠")
            whole_source_ok = False
        document_diagnostics.append(
            {
                "document_id": document_id,
                "start_char": start,
                "end_char": end,
                "covered_char_count": union,
                "interval_count": len(intervals),
                "coverage": 1.0 if end == start else union / max(1, end - start),
                "overlap": overlap,
            }
        )
    return {
        "book_id": book_id,
        "edition_id": selected,
        "source_manifest_sha256": _source_manifest_hash(database, book_id),
        "effective_chapter_count": len(chapters),
        "covered_chapter_count": len(chapters) - len(missing_spans),
        "chapter_coverage": (
            (len(chapters) - len(missing_spans)) / len(chapters) if chapters else 0.0
        ),
        "whole_source_coverage": 1.0 if whole_source_ok and not missing_spans else 0.0,
        "missing_source_spans": missing_spans,
        "duplicate_source_spans": duplicate_spans,
        "anomalies": sorted(set(anomalies)),
        "documents": document_diagnostics,
        "status": (
            "BLOCKED"
            if missing_spans or duplicate_spans or not whole_source_ok
            else ("FULL_WITH_ANOMALIES" if anomalies else "FULL")
        ),
    }


def _propose_arcs(
    book_id: str,
    edition_id: str,
    initialization_id: str,
    chapters: list[dict[str, Any]],
    *,
    char_limit: int,
    max_chapters: int = 20,
) -> list[ArcRecord]:
    if not chapters:
        return []
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    current_volume: str | None = None
    for row in chapters:
        volume = _infer_volume(row)
        chars = len(str(row.get("content") or ""))
        force_volume = bool(current and volume and current_volume and volume != current_volume)
        force_size = bool(current and (len(current) >= max_chapters or current_chars + chars > char_limit))
        if force_volume or force_size:
            groups.append(current)
            current = []
            current_chars = 0
            current_volume = volume
        if not current:
            current_volume = volume
        current.append(row)
        current_chars += chars
    if current:
        groups.append(current)
    arcs: list[ArcRecord] = []
    for index, group in enumerate(groups, start=1):
        first, last = group[0], group[-1]
        source_spans = [
            str(item.get("source_span_id"))
            for item in group
            if item.get("source_span_id")
        ]
        arc_id = stable_id(
            "init-arc",
            book_id,
            edition_id,
            initialization_id,
            str(first["ordinal"]),
            str(last["ordinal"]),
        )
        reason = "volume boundary" if len({str(_infer_volume(item)) for item in group}) > 1 else "chapter window"
        arcs.append(
            ArcRecord(
                arc_id=arc_id,
                ordinal=index,
                start_chapter=int(first["ordinal"]),
                end_chapter=int(last["ordinal"]),
                chapter_ids=[str(item["chapter_id"]) for item in group],
                source_span_ids=source_spans,
                char_count=sum(len(str(item.get("content") or "")) for item in group),
                inferred_volume=_infer_volume(first),
                boundary_reason=reason,
            )
        )
    return arcs


def _event(root: Path, event_type: str, payload: dict[str, Any]) -> None:
    path = root / "events.jsonl"
    event = {"event_type": event_type, "created_at": utc_now(), **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json_dumps(event) + "\n")


def _arc_schema() -> dict[str, Any]:
    schema = ArcExtractionOutput.model_json_schema()
    schema["additionalProperties"] = False
    return schema


def _arc_operation_id(initialization_id: str, arc_id: str) -> str:
    return f"{initialization_id}-arc-{arc_id}"


def arc_output_path(
    root: Path,
    initialization_id: str,
    book_id: str,
    edition_id: str,
    arc_id: str,
) -> Path:
    """Resolve an Arc result in the canonical operation workspace."""

    book_root = next(
        (candidate for candidate in (root, *root.parents) if (candidate / "book.yaml").is_file()),
        None,
    )
    if book_root is None:
        return root / "arc_outputs" / arc_id / "output.json"
    edition = BookLayout(book_root.parent).for_book(book_id).edition(edition_id)
    return edition.operation(_arc_operation_id(initialization_id, arc_id)).output / "output.json"


def create_initialization(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    char_limit: int = 80_000,
    max_chapters_per_arc: int = 20,
) -> dict[str, Any]:
    """Create a frozen, source-complete initialization task package.

    This function only maps and packages source material. It deliberately does
    not claim semantic completion and does not create Canon events.
    """
    if char_limit < 1 or max_chapters_per_arc < 1 or max_chapters_per_arc > 20:
        raise InitializationError("Arc 限制无效：章节数必须 1—20，字符上限必须为正数")
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    chapters = _chapter_rows(database, book_id, selected)
    if not chapters:
        raise InitializationError("当前 edition 没有有效章节，无法初始化")
    source_diagnostic = calculate_source_coverage(database, book_id, selected)
    if source_diagnostic["status"] == "BLOCKED":
        raise InitializationError(
            "Source Coverage 阻断：" + "; ".join(source_diagnostic["anomalies"])
        )
    source_hash = _source_manifest_hash(database, book_id)
    effective_hash = hashlib.sha256(
        "".join(str(item.get("content_sha256") or "") for item in chapters).encode("utf-8")
    ).hexdigest()
    initialization_id = stable_id("novel-initialization", book_id, selected, source_hash, effective_hash, utc_now())
    root = initialization_root(database, book_id, selected, initialization_id)
    root.mkdir(parents=True, exist_ok=False)
    for name in (
        "entity_resolution",
        "synthesis",
        "metrics",
        "visuals",
        "reports",
    ):
        (root / name).mkdir()
    arcs = _propose_arcs(
        book_id,
        selected,
        initialization_id,
        chapters,
        char_limit=char_limit,
        max_chapters=max_chapters_per_arc,
    )
    arc_by_chapter = {
        chapter_id: arc
        for arc in arcs
        for chapter_id in arc.chapter_ids
    }
    coverage_items: list[ChapterCoverage] = []
    for row in chapters:
        arc = arc_by_chapter[str(row["chapter_id"])]
        coverage_items.append(
            ChapterCoverage(
                ordinal=int(row["ordinal"]),
                raw_heading=str(row.get("raw_heading") or ""),
                logical_heading=str(row.get("title") or row.get("raw_heading") or ""),
                chapter_id=str(row["chapter_id"]),
                source_span_ids=(
                    [str(row["source_span_id"])] if row.get("source_span_id") else []
                ),
                content_sha256=str(row.get("content_sha256") or ""),
                char_count=len(str(row.get("content") or "")),
                inferred_volume=_infer_volume(row),
                assigned_arc_id=arc.arc_id,
            )
        )
    coverage = SourceCoverage(
        book_id=book_id,
        edition_id=selected,
        source_manifest_sha256=source_hash,
        effective_chapter_count=len(chapters),
        covered_chapter_count=len(coverage_items),
        chapter_coverage=1.0,
        chapters=coverage_items,
        diagnostics=source_diagnostic,
    )
    manifest = InitializationManifest(
        initialization_id=initialization_id,
        book_id=book_id,
        edition_id=selected,
        source_manifest_sha256=source_hash,
        effective_content_sha256=effective_hash,
        created_at=utc_now(),
        pipeline=[
            "Source Coverage",
            "Arc Segmentation",
            "Arc Extraction",
            "Entity Resolution",
            "Cross-Arc Synthesis",
            "Contradiction Audit",
            "Narrative DNA",
            "Current Story Atlas",
            "Future Possibility Space",
            "Semantic Metric Bootstrap",
            "Visual Asset Rendering",
        ],
        state=InitializationState.SOURCE_MAPPED,
        source_coverage_path="source_coverage.json",
        arc_manifest_path="arc_manifest.json",
        contract_hashes={},
        chapter_count=len(chapters),
        arc_count=len(arcs),
        current_core_requirements=[
            "protagonist state",
            "current world rules",
            "current ability boundaries",
            "active main thread",
            "continuation boundary",
        ],
    )
    _write_json(root / "source_coverage.json", coverage.model_dump(mode="json"))
    arc_manifest = ArcManifest(
        initialization_id=initialization_id,
        book_id=book_id,
        edition_id=selected,
        arcs=arcs,
        max_chapters_per_arc=max_chapters_per_arc,
        char_limit=char_limit,
    )
    _write_json(root / "arc_manifest.json", arc_manifest.model_dump(mode="json"))
    schema_path = root / "arc_schema.json"
    _write_json(schema_path, _arc_schema())
    manifest.contract_hashes = {
        "arc_schema.json": sha256_file(schema_path),
        "source_coverage.json": sha256_file(root / "source_coverage.json"),
        "arc_manifest.json": sha256_file(root / "arc_manifest.json"),
    }
    _write_json(root / "initialization_manifest.json", manifest.model_dump(mode="json"))
    _write_json(
        root / "status.json",
        {
            "initialization_id": initialization_id,
            "state": InitializationState.SOURCE_MAPPED.value,
            "readiness": "BLOCKED",
            "source_coverage": coverage.chapter_coverage,
            "chapter_coverage": 0.0,
            "updated_at": utc_now(),
            "completed_arc_ids": [],
            "failed_arc_ids": [],
            "warnings": ["语义 Arc 输出尚未由 Codex 桌面端完成"],
        },
    )
    (root / "events.jsonl").write_text("", encoding="utf-8")
    for arc in arcs:
        operation = ensure_operation(
            database,
            book_id,
            selected,
            _arc_operation_id(initialization_id, arc.arc_id),
            "INITIALIZATION_ARC",
            {"initialization_id": initialization_id, "arc_id": arc.arc_id},
        )
        arc_task = (
            operation.input
            if operation is not None
            else root / "arc_tasks" / arc.arc_id
        )
        (arc_task / "chapters").mkdir(parents=True)
        arc_chapters = [
            row for row in chapters if str(row["chapter_id"]) in set(arc.chapter_ids)
        ]
        chapter_lines: list[str] = []
        for row in arc_chapters:
            # Keep filenames short: Windows workspaces can already be deeply
            # nested, and the stable chapter id is preserved in the manifest.
            chapter_path = arc_task / "chapters" / f"chapter-{int(row['ordinal']):04d}.md"
            chapter_text = f"# {row.get('raw_heading') or row.get('title') or row['ordinal']}\n\n{row.get('content') or ''}\n"
            chapter_path.write_text(chapter_text, encoding="utf-8")
            chapter_lines.append(f"- 第 {row['ordinal']} 章 · `{row['chapter_id']}` · `{chapter_path.name}`")
        _write_json(
            arc_task / "source_manifest.json",
            {
                "initialization_id": initialization_id,
                "arc_id": arc.arc_id,
                "chapter_ids": arc.chapter_ids,
                "source_span_ids": arc.source_span_ids,
                "content_hashes": [
                    str(row.get("content_sha256") or "") for row in arc_chapters
                ],
            },
        )
        _write_json(arc_task / "output_schema.json", _arc_schema())
        _write_json(
            arc_task / "status.json",
            {
                "initialization_id": initialization_id,
                "arc_id": arc.arc_id,
                "state": "PENDING",
                "updated_at": utc_now(),
                "source_frozen": True,
            },
        )
        input_text = (
            "$initialize-existing-novel\n\n"
            f"初始化 {initialization_id} 的 Arc {arc.arc_id}。\n"
            "请只读取本目录 chapters/ 和 source_manifest.json，按 output_schema.json 输出 output.json。\n"
            "CANON 必须有真实 source_span_ids；INFERENCE 必须有 reasoning_summary、confidence、counter_evidence 和 unknown_boundary。\n"
            "不得修改 book、Canon、正史或远端；未知保持 unknown，不要为了完整而猜测。\n\n"
            "本 Arc 章节：\n" + "\n".join(chapter_lines) + "\n"
        )
        (arc_task / "input.md").write_text(input_text, encoding="utf-8")
    _event(root, "SOURCE_MAPPED", {"chapter_count": len(chapters), "arc_count": len(arcs)})
    return {
        "initialization_id": initialization_id,
        "book_id": book_id,
        "edition_id": selected,
        "root": str(root),
        "state": InitializationState.SOURCE_MAPPED.value,
        "chapter_count": len(chapters),
        "arc_count": len(arcs),
        "chapter_coverage": 1.0,
        "source_coverage": 1.0,
        "arc_ids": [arc.arc_id for arc in arcs],
        "source_manifest_sha256": source_hash,
    }


def _latest_directory(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir() and (path / "initialization_manifest.json").is_file()]
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0] if candidates else None


def latest_initialization(
    database: Database,
    book_id: str,
    edition_id: str | None = None,
    initialization_id: str | None = None,
) -> dict[str, Any] | None:
    root = initialization_root(database, book_id, edition_id)
    selected = (
        initialization_root(database, book_id, edition_id, initialization_id)
        if initialization_id
        else _latest_directory(root)
    )
    if selected is None:
        return None
    try:
        manifest = _read_json(selected / "initialization_manifest.json")
        status = _read_json(selected / "status.json")
    except (OSError, json.JSONDecodeError) as exc:
        raise InitializationError(f"初始化状态文件无法读取：{selected}") from exc
    return {"root": str(selected), "manifest": manifest, "status": status}


def _arc_outputs(root: Path, arc_manifest: ArcManifest) -> tuple[list[ArcExtractionOutput], list[str], list[str]]:
    completed: list[ArcExtractionOutput] = []
    failed: list[str] = []
    pending: list[str] = []
    for arc in arc_manifest.arcs:
        path = arc_output_path(
            root,
            arc_manifest.initialization_id,
            arc_manifest.book_id,
            arc_manifest.edition_id,
            arc.arc_id,
        )
        if not path.is_file():
            pending.append(arc.arc_id)
            continue
        try:
            value = ArcExtractionOutput.model_validate(_read_json(path))
            if value.initialization_id != arc_manifest.initialization_id or value.arc_id != arc.arc_id:
                raise ValueError("initialization_id/arc_id 不匹配")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            failed.append(arc.arc_id)
            _write_json(
                path.parent / "validation_error.json",
                {"arc_id": arc.arc_id, "error": str(exc), "updated_at": utc_now()},
            )
            continue
        completed.append(value)
    return completed, pending, failed


def _write_reports(root: Path, coverage: SourceCoverage, arc_manifest: ArcManifest, outputs: list[ArcExtractionOutput], readiness: InitializationReadiness) -> None:
    (root / "reports" / "source_coverage_report.md").write_text(
        "# Source Coverage Report\n\n"
        f"- Effective chapters: {coverage.effective_chapter_count}\n"
        f"- Source-mapped chapters: {coverage.covered_chapter_count}\n"
        f"- Source mapping coverage: {coverage.chapter_coverage:.1%}\n"
        f"- Arcs: {len(arc_manifest.arcs)}\n"
        "\nEvery effective chapter has exactly one assigned Arc and a source span when the ingest layer provides one.\n",
        encoding="utf-8",
    )
    (root / "reports" / "entity_resolution_report.md").write_text(
        "# Entity Resolution Report\n\n"
        "Entity resolution is conservative: aliases do not auto-merge by string similarity; unresolved candidates remain reviewable.\n",
        encoding="utf-8",
    )
    (root / "reports" / "contradiction_report.md").write_text(
        "# Contradiction Report\n\n"
        f"Arc outputs reviewed: {len(outputs)} / {len(arc_manifest.arcs)}.\n"
        "Cross-Arc contradiction audit is pending until entity resolution and synthesis artifacts exist.\n",
        encoding="utf-8",
    )
    (root / "reports" / "world_model_report.md").write_text(
        "# World Model Report\n\n"
        "This report is evidence-led. It never promotes an inference into Canon and keeps future possibility space separate from current facts.\n",
        encoding="utf-8",
    )
    (root / "reports" / "readiness_report.md").write_text(
        "# Readiness Report\n\n"
        f"- Status: {readiness.status}\n"
        f"- Chapter coverage: {readiness.chapter_coverage:.1%}\n"
        f"- Arc coverage: {readiness.arc_coverage:.1%}\n"
        f"- Source Mapping Coverage: {readiness.source_mapping_coverage:.1%}\n"
        f"- Arc Output Coverage: {readiness.arc_output_coverage:.1%}\n"
        f"- Chapter Semantic Feature Coverage: {readiness.chapter_semantic_feature_coverage:.1%}\n"
        f"- Metric Observation Coverage: {readiness.metric_observation_coverage:.1%}\n"
        f"- Recent Detailed Metric Coverage: {readiness.recent_detailed_metric_coverage:.1%}\n"
        f"- Current Chapter Metric Coverage: {readiness.current_chapter_metric_coverage:.1%}\n"
        f"- Metric Bootstrap Status: {readiness.metric_bootstrap_status}\n"
        f"- Canon evidence coverage: {readiness.canon_evidence_coverage:.1%}\n"
        f"- Entity resolution coverage: {readiness.entity_resolution_coverage:.1%}\n\n"
        "## Blocking reasons\n"
        + "\n".join(f"- {item}" for item in readiness.blocking_reasons)
        + "\n\n## Gaps\n"
        + "\n".join(f"- {item}" for item in readiness.gaps)
        + "\n",
        encoding="utf-8",
    )


def refresh_initialization(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    initialization_id: str | None = None,
) -> dict[str, Any]:
    """Recalculate initialization status from immutable coverage and output files."""
    selected = resolve_edition_id(database, book_id, edition_id)
    root = initialization_root(database, book_id, selected, initialization_id)
    if initialization_id is None:
        root = _latest_directory(root) or root
    if not (root / "initialization_manifest.json").is_file():
        raise InitializationError(f"初始化目录不存在：{root}")
    initialization_manifest = InitializationManifest.model_validate(
        _read_json(root / "initialization_manifest.json")
    )
    current_chapters = _chapter_rows(database, book_id, selected)
    current_effective_hash = hashlib.sha256(
        "".join(str(item.get("content_sha256") or "") for item in current_chapters).encode("utf-8")
    ).hexdigest()
    current_source_hash = _source_manifest_hash(database, book_id)
    if (
        initialization_manifest.source_manifest_sha256 != current_source_hash
        or initialization_manifest.effective_content_sha256 != current_effective_hash
    ):
        stale_status = {
            "initialization_id": initialization_manifest.initialization_id,
            "state": InitializationState.STALE.value,
            "readiness": "BLOCKED",
            "source_coverage": 0.0,
            "chapter_coverage": 0.0,
            "updated_at": utc_now(),
            "blocking_reasons": ["Source 或 effective Edition hash 已漂移，必须重新初始化"],
            "completed_arc_ids": [],
            "failed_arc_ids": [],
        }
        _write_json(root / "status.json", stale_status)
        _write_json(
            root / "initialization_manifest.json",
            initialization_manifest.model_copy(update={"state": InitializationState.STALE}).model_dump(
                mode="json"
            ),
        )
        _event(root, InitializationState.STALE.value, stale_status)
        return {"root": str(root), "status": stale_status, "readiness": stale_status}
    coverage = SourceCoverage.model_validate(_read_json(root / "source_coverage.json"))
    arc_manifest = ArcManifest.model_validate(_read_json(root / "arc_manifest.json"))
    outputs, pending, failed = _arc_outputs(root, arc_manifest)
    analyzed_chapter_ids: set[str] = set()
    evidence_total = 0
    evidence_valid = 0
    for output in outputs:
        feature_rows = output.chapter_semantic_features
        analyzed_chapter_ids.update(
            str(item["chapter_id"])
            for item in feature_rows
            if item.get("chapter_id")
            and str(item.get("analysis_status", "PENDING")).upper()
            not in {"PENDING", "UNKNOWN", "NOT_ANALYZED"}
        )
        for field_name in type(output).model_fields:
            value = getattr(output, field_name)
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    continue
                if str(item.get("information_status", "CANON")).upper() == "CANON":
                    evidence_total += 1
                    if item.get("source_span_ids") or item.get("source_evidence"):
                        evidence_valid += 1
    canon_evidence = evidence_valid / evidence_total if evidence_total else 0.0
    entity_file = root / "entity_resolution" / "entity_resolution_map.json"
    entity_result: EntityResolutionResult | None = None
    if entity_file.is_file():
        try:
            entity_result = EntityResolutionResult.model_validate(_read_json(entity_file))
        except (OSError, json.JSONDecodeError, ValueError):
            entity_result = None
    entity_cov = 0.0
    if entity_result and entity_result.identified_major_entities:
        entity_cov = min(1.0, entity_result.resolved_major_entities / entity_result.identified_major_entities)
    synthesis_file = root / "synthesis" / "current_world_model.md"
    graph_file = root / "synthesis" / "graphs.json"
    core_graphs = synthesis_file.is_file() and graph_file.is_file()
    graph_core = False
    protagonist_confirmed = False
    thread_confirmed = False
    if graph_file.is_file():
        try:
            graphs = _read_json(graph_file)
            if isinstance(graphs, dict):
                required = {"characters", "factions", "abilities", "resources", "regions", "plot_threads"}
                graph_core = required.issubset(set(graphs))
                text = json.dumps(graphs, ensure_ascii=False).lower()
                protagonist_confirmed = "主角" in text or "protagonist" in text
                thread_confirmed = "thread" in text or "线程" in text
                core_graphs = core_graphs and graph_core
        except (OSError, json.JSONDecodeError):
            core_graphs = False
    chapter_coverage = (
        len(analyzed_chapter_ids) / coverage.effective_chapter_count
        if coverage.effective_chapter_count
        else 0.0
    )
    arc_coverage = len(outputs) / len(arc_manifest.arcs) if arc_manifest.arcs else 0.0
    source_mapping_coverage = coverage.chapter_coverage
    arc_output_coverage = arc_coverage
    chapter_semantic_feature_coverage = chapter_coverage
    try:
        from novel_authoring.initialization.metrics import metric_bootstrap_status

        metric_audit = metric_bootstrap_status(
            database,
            book_id,
            edition_id=selected,
            initialization_id=initialization_manifest.initialization_id,
        )
    except (InitializationError, OSError, ValueError) as exc:
        metric_audit = {
            "status": "NOT_READY",
            "errors": [f"Metric Bootstrap 审计失败：{exc}"],
            "coverage": {
                "metric_observation_coverage": 0.0,
                "recent_detailed_metric_coverage": 0.0,
                "current_chapter_metric_coverage": 0.0,
            },
        }
    metric_coverage = metric_audit.get("coverage", {})
    metric_observation_coverage = float(metric_coverage.get("metric_observation_coverage", 0.0))
    recent_detailed_metric_coverage = float(
        metric_coverage.get("recent_detailed_metric_coverage", 0.0)
    )
    current_chapter_metric_coverage = float(
        metric_coverage.get("current_chapter_metric_coverage", 0.0)
    )
    blockers: list[str] = []
    gaps: list[str] = []
    if chapter_coverage < 0.95:
        blockers.append("章节覆盖率低于 95%")
    if arc_coverage < 1.0:
        blockers.append("仍有 Arc 未完成语义提取")
    if not core_graphs:
        blockers.append("当前核心 World Model/图谱尚未生成")
    if not protagonist_confirmed:
        blockers.append("主角当前状态尚未确认")
    if not thread_confirmed:
        blockers.append("当前主线程尚未确认")
    if canon_evidence < 0.95 and outputs:
        gaps.append("CANON 记录的 source-span 证据覆盖不足")
    if pending:
        gaps.append(f"待处理 Arc：{len(pending)}")
    if failed:
        blockers.append(f"校验失败 Arc：{len(failed)}")
    if not entity_file.is_file():
        gaps.append("实体解析尚未写回")
    if metric_audit.get("status") != "COMPLETE":
        errors = metric_audit.get("errors") or ["严格 Semantic Metric Bootstrap 尚未完成"]
        blockers.append(f"Semantic Metric Bootstrap 未完成：{errors[0]}")
    if (root / "synthesis" / "unresolved_assumptions.yaml").is_file():
        gaps.append("Future Possibility Space 仍保留未决假设")
    status = "BLOCKED" if blockers else ("READY_WITH_GAPS" if gaps or chapter_coverage < 1.0 else "READY")
    readiness = InitializationReadiness(
        status=status,
        chapter_coverage=chapter_coverage,
        arc_coverage=arc_coverage,
        source_mapping_coverage=source_mapping_coverage,
        arc_output_coverage=arc_output_coverage,
        chapter_semantic_feature_coverage=chapter_semantic_feature_coverage,
        metric_observation_coverage=metric_observation_coverage,
        recent_detailed_metric_coverage=recent_detailed_metric_coverage,
        current_chapter_metric_coverage=current_chapter_metric_coverage,
        metric_bootstrap_status=str(metric_audit.get("status", "NOT_READY")),
        metric_bootstrap=metric_audit,
        canon_evidence_coverage=canon_evidence,
        entity_resolution_coverage=entity_cov,
        core_graphs_complete=core_graphs,
        protagonist_confirmed=protagonist_confirmed,
        current_thread_confirmed=thread_confirmed,
        blocking_reasons=blockers,
        gaps=gaps,
        review_queue=sorted(set([*pending, *failed])),
    )
    metrics_ready = metric_audit.get("status") == "COMPLETE"
    if status == "READY":
        state = InitializationState.READY
    elif status == "READY_WITH_GAPS":
        state = InitializationState.READY_WITH_GAPS
    elif failed:
        state = InitializationState.BLOCKED
    elif not outputs:
        state = InitializationState.SOURCE_MAPPED
    elif pending:
        state = InitializationState.ARC_EXTRACTION_RUNNING
    elif not entity_file.is_file():
        state = InitializationState.ENTITY_RESOLUTION_RUNNING
    elif not core_graphs:
        state = InitializationState.SYNTHESIS_RUNNING
    elif not metrics_ready:
        state = InitializationState.METRIC_BOOTSTRAP_RUNNING
    else:
        state = InitializationState.ATLAS_VALIDATION_RUNNING
    status_payload = {
        "initialization_id": arc_manifest.initialization_id,
        "state": state.value,
        "readiness": readiness.model_dump(mode="json"),
        "source_coverage": coverage.chapter_coverage,
        "source_mapping_coverage": source_mapping_coverage,
        "arc_output_coverage": arc_output_coverage,
        "chapter_semantic_feature_coverage": chapter_semantic_feature_coverage,
        "metric_observation_coverage": metric_observation_coverage,
        "recent_detailed_metric_coverage": recent_detailed_metric_coverage,
        "current_chapter_metric_coverage": current_chapter_metric_coverage,
        "metric_bootstrap": metric_audit,
        "updated_at": utc_now(),
        "completed_arc_ids": [item.arc_id for item in outputs],
        "failed_arc_ids": failed,
        "pending_arc_ids": pending,
        "entity_count": (
            entity_result.resolved_major_entities
            if entity_result is not None
            else sum(len(item.characters) for item in outputs)
        ),
        "warnings": readiness.gaps,
    }
    _write_json(root / "status.json", status_payload)
    _write_json(
        root / "initialization_manifest.json",
        initialization_manifest.model_copy(update={"state": state}).model_dump(mode="json"),
    )
    _write_reports(root, coverage, arc_manifest, outputs, readiness)
    _event(root, state.value, {"readiness": readiness.model_dump(mode="json")})
    return {"root": str(root), "status": status_payload, "readiness": readiness.model_dump(mode="json")}
