"""Build and load source-derived runtime knowledge snapshots."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from novel_authoring.canon.projection import CanonProjection, rebuild_projection
from novel_authoring.db.database import Database
from novel_authoring.distill.models import DistillScope, EvidenceMappingStatus
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.runtime_baseline.models import (
    AvailablePayoff,
    BaselineCategory,
    BaselineEvidence,
    BaselineStatus,
    EarnedEntry,
    EarnedSurface,
    EffectiveRuntimeState,
    RuntimeBaseline,
    RuntimeBaselineEntry,
    RuntimeBaselineInput,
    RuntimeBaselineManifest,
    RuntimeStateRecord,
)
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.operations import book_root
from novel_authoring.utils import json_dumps, stable_id, utc_now


class RuntimeBaselineError(RuntimeError):
    """Raised when a source-derived baseline cannot be validated."""


def _baseline_root(database: Database, book_id: str, edition_id: str) -> Path:
    root = book_root(database, book_id)
    if not (root / "book.yaml").is_file():
        raise RuntimeBaselineError("Runtime Baseline 只支持 Canonical Book Library")
    return (
        BookLayout(root.parent).for_book(book_id).edition(edition_id).analysis
        / "runtime_baseline"
    )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeBaselineError(f"无法读取 Runtime Baseline 文件：{path}") from exc


def _entry_files() -> dict[BaselineCategory, str]:
    return {
        BaselineCategory.CHARACTER: "characters.json",
        BaselineCategory.CAPABILITY: "capabilities.json",
        BaselineCategory.ITEM: "items.json",
        BaselineCategory.EQUIPMENT: "equipment.json",
        BaselineCategory.RESOURCE: "resources.json",
        BaselineCategory.KNOWLEDGE: "knowledge.json",
        BaselineCategory.RULE: "rules.json",
        BaselineCategory.EXCEPTION: "exceptions.json",
        BaselineCategory.PROMISE: "promises.json",
    }


def _validate_source_evidence(
    database: Database,
    book_id: str,
    edition_id: str,
    entry: RuntimeBaselineEntry,
    chapters: list[dict[str, Any]],
    boundary_chapter: int,
) -> RuntimeBaselineEntry:
    chapter_map = {str(item["chapter_id"]): item for item in chapters}
    validated: list[BaselineEvidence] = []
    with database.connect() as connection:
        for evidence in entry.evidence:
            if evidence.mapping_status not in {
                EvidenceMappingStatus.EXACT,
                EvidenceMappingStatus.PARTIAL,
            }:
                if entry.status is BaselineStatus.SOURCE_VERIFIED:
                    raise RuntimeBaselineError(
                        f"SOURCE_VERIFIED entry {entry.entry_id} 含非可靠 evidence"
                    )
                validated.append(evidence)
                continue
            if not evidence.chapter_id or evidence.chapter_id not in chapter_map:
                raise RuntimeBaselineError(
                    f"Baseline evidence 未映射到 selected Edition chapter：{entry.entry_id}"
                )
            chapter = chapter_map[evidence.chapter_id]
            if int(chapter.get("ordinal", 0)) > boundary_chapter:
                raise RuntimeBaselineError(
                    f"Baseline evidence 超过 boundary chapter {boundary_chapter}：{entry.entry_id}"
                )
            span_rows = connection.execute(
                "SELECT span_id, start_line, end_line, excerpt FROM source_spans "
                "WHERE chapter_id=?",
                (evidence.chapter_id,),
            ).fetchall()
            valid_span_ids = {str(row["span_id"]) for row in span_rows}
            if not set(evidence.source_span_ids).issubset(valid_span_ids):
                raise RuntimeBaselineError(
                    f"Baseline evidence 使用了不属于 chapter 的 source span：{entry.entry_id}"
                )
            selected_spans = [
                row for row in span_rows if str(row["span_id"]) in evidence.source_span_ids
            ]
            if not selected_spans or not any(
                str(row["excerpt"] or "").strip()
                and int(row["start_line"]) <= evidence.start_line
                and evidence.end_line <= int(row["end_line"])
                for row in selected_spans
            ):
                raise RuntimeBaselineError(
                    f"Baseline evidence line range 不在 source span 内：{entry.entry_id}"
                )
            if (
                evidence.mapping_status is EvidenceMappingStatus.EXACT
                and not evidence.direct_text_confirmed
            ):
                raise RuntimeBaselineError(
                    f"EXACT evidence 必须声明 direct_text_confirmed：{entry.entry_id}"
                )
            validated.append(evidence)
    if entry.status is BaselineStatus.SOURCE_VERIFIED and any(
        item.mapping_status is not EvidenceMappingStatus.EXACT for item in validated
    ):
        raise RuntimeBaselineError(
            f"SOURCE_VERIFIED entry {entry.entry_id} 必须全部使用 EXACT mapping"
        )
    if entry.status is BaselineStatus.SOURCE_PARTIAL and not any(
        item.mapping_status
        in {EvidenceMappingStatus.EXACT, EvidenceMappingStatus.PARTIAL}
        for item in validated
    ):
        raise RuntimeBaselineError(
            f"SOURCE_PARTIAL entry {entry.entry_id} 没有可用的 PARTIAL/EXACT mapping"
        )
    return entry.model_copy(update={"evidence": validated})


def _load_input(path: Path, book_id: str, edition_id: str) -> RuntimeBaselineInput:
    try:
        payload = RuntimeBaselineInput.model_validate(_read_json(path))
    except Exception as exc:
        raise RuntimeBaselineError(f"Runtime Baseline input 不符合严格模型：{exc}") from exc
    if payload.book_id != book_id or payload.edition_id != edition_id:
        raise RuntimeBaselineError("Runtime Baseline input 的 book_id/edition_id 不一致")
    if payload.scope is not DistillScope.SELF_BOOK:
        raise RuntimeBaselineError("Runtime Baseline 只能消费 SELF_BOOK source-derived input")
    return payload


def _atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _string_attributes(value: dict[str, Any]) -> dict[str, str]:
    """Keep only compact scalar metadata in the runtime knowledge surface."""

    result: dict[str, str] = {}
    for key, item in value.items():
        if str(key).startswith("_") or item is None or isinstance(item, (dict, list)):
            continue
        result[str(key)] = str(item)
    return result


def _split_attribute(value: str) -> list[str]:
    return [
        item.strip()
        for item in value.replace("；", "|").replace(",", "|").split("|")
        if item.strip()
    ]


def _entry_runtime_metadata(
    attributes: dict[str, str], status: BaselineStatus
) -> tuple[str, list[str], list[str], int | None]:
    availability = attributes.get(
        "availability", "AVAILABLE" if status is BaselineStatus.SOURCE_VERIFIED else "CONDITIONAL"
    )
    costs = _split_attribute(attributes.get("costs", ""))
    constraints = _split_attribute(
        attributes.get("constraints", "")
        or attributes.get("activation_gate", "")
        or attributes.get("missing_materials", "")
    )
    raw_last = attributes.get("last_confirmed") or attributes.get("last_advanced")
    last_confirmed = int(raw_last) if raw_last and raw_last.isdigit() else None
    return availability, costs, constraints, last_confirmed


def _earned_from_baseline(entry: RuntimeBaselineEntry) -> EarnedEntry:
    availability, costs, constraints, last_confirmed = _entry_runtime_metadata(
        entry.attributes, entry.status
    )
    return EarnedEntry(
        entry_id=f"baseline:{entry.entry_id}",
        category=entry.category.value,
        name=entry.name,
        statement=entry.statement,
        status=entry.status,
        source="SOURCE_DERIVED_RUNTIME_BASELINE",
        source_entry_id=entry.entry_id,
        evidence=entry.evidence,
        attributes=dict(entry.attributes),
        availability=availability,
        costs=costs,
        constraints=constraints,
        last_confirmed=last_confirmed,
    )


def _projection_earned(
    *,
    entry_id: str,
    category: str,
    name: str,
    statement: str,
    record_id: str,
    value: dict[str, Any],
) -> EarnedEntry:
    attributes = _string_attributes(value)
    availability, costs, constraints, last_confirmed = _entry_runtime_metadata(
        attributes, BaselineStatus.SOURCE_VERIFIED
    )
    return EarnedEntry(
        entry_id=entry_id,
        category=category,
        name=name,
        statement=statement,
        status=BaselineStatus.SOURCE_VERIFIED,
        source="CANON_PROJECTION",
        projection_record_id=record_id,
        attributes=attributes,
        availability="CANON_AVAILABLE" if availability == "AVAILABLE" else availability,
        costs=costs,
        constraints=constraints,
        last_confirmed=(
            int(value["_event_seq"])
            if str(value.get("_event_seq", "")).isdigit()
            else last_confirmed
        ),
    )


def _projection_scalar(value: Any, *keys: str, fallback: str) -> str:
    for key in keys:
        candidate = value.get(key) if isinstance(value, dict) else None
        if candidate is not None and str(candidate).strip():
            return str(candidate)
    return fallback


def build_effective_runtime_state(
    baseline: RuntimeBaseline,
    projection: CanonProjection,
    *,
    created_at: str | None = None,
) -> EffectiveRuntimeState:
    """Compose baseline facts with the latest Canon projection without mutation.

    Projection records are a delta: a matching category/name or declared record
    identifier replaces the earlier baseline record in the returned view.  The
    source baseline files are never edited and the projection is never persisted.
    """

    records: dict[str, list[RuntimeStateRecord]] = {}

    def add(record: RuntimeStateRecord, *, replace_ids: set[str] | None = None) -> None:
        category = records.setdefault(record.category, [])
        replace_ids = replace_ids or set()
        category[:] = [
            existing
            for existing in category
            if existing.record_id not in replace_ids
            and existing.baseline_entry_id not in replace_ids
            and existing.name.casefold() != record.name.casefold()
            and (
                not replace_ids
                or not set(existing.attributes.values()).intersection(replace_ids)
            )
        ]
        category.append(record)

    for entry in baseline.entries:
        if entry.status is BaselineStatus.UNKNOWN:
            continue
        add(
            RuntimeStateRecord(
                record_id=f"baseline:{entry.entry_id}",
                category=entry.category.value,
                name=entry.name,
                statement=entry.statement,
                status=entry.status.value,
                source="SOURCE_DERIVED_RUNTIME_BASELINE",
                baseline_entry_id=entry.entry_id,
                attributes=dict(entry.attributes),
                evidence=entry.evidence,
                last_confirmed=_entry_runtime_metadata(entry.attributes, entry.status)[3],
            )
        )

    collections: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        ("facts", "fact", ("fact_id", "name", "fact")),
        ("timeline", "timeline", ("timeline_id", "name", "event")),
        ("entities", "entity", ("entity_id", "name", "entity")),
        ("character_states", "character_state", ("state_id", "character_id", "name")),
        ("knowledge", "knowledge", ("edge_id", "name", "knowledge")),
        ("relationships", "relationship", ("relationship_id", "name", "relationship")),
        ("resources", "resource", ("resource_id", "name", "resource")),
        ("capabilities", "capability", ("capability_id", "name", "capability")),
        ("threads", "thread", ("thread_id", "name", "thread")),
        ("promises", "promise", ("promise_id", "promise_id", "statement")),
        ("payoffs", "payoff", ("payoff_id", "payoff_id", "statement")),
        ("style_profiles", "style_profile", ("profile_id", "name", "profile")),
        ("committed_chapters", "committed_chapter", ("chapter_id", "title", "chapter_id")),
    )
    for collection_name, category, identifiers in collections:
        collection = getattr(projection, collection_name)
        for record_id, raw_value in collection.items():
            value = dict(raw_value)
            identity = _projection_scalar(value, *identifiers, fallback=str(record_id))
            statement = _projection_scalar(
                value, "statement", "description", "content", "status", fallback=identity
            )
            attributes = _string_attributes(value)
            add(
                RuntimeStateRecord(
                    record_id=f"projection:{category}:{record_id}",
                    category=category,
                    name=identity,
                    statement=statement,
                    status=str(value.get("status") or "CANON"),
                    source="CANON_PROJECTION",
                    projection_record_id=str(record_id),
                    attributes=attributes,
                    last_confirmed=(
                        int(value["_event_seq"])
                        if str(value.get("_event_seq", "")).isdigit()
                        else None
                    ),
                ),
                replace_ids={str(record_id), identity},
            )

    state_id = stable_id(
        "effective-runtime-state",
        baseline.manifest.baseline_id,
        str(projection.through_event_seq),
        projection.sha256(),
    )
    return EffectiveRuntimeState(
        state_id=state_id,
        book_id=baseline.manifest.book_id,
        edition_id=baseline.manifest.edition_id,
        baseline_id=baseline.manifest.baseline_id,
        projection_event_seq=projection.through_event_seq,
        projection_hash=projection.sha256(),
        created_at=created_at or utc_now(),
        records=records,
        hard_unknowns=[
            f"{entry.category.value}:{entry.name}: {entry.statement}"
            for entry in baseline.entries
            if entry.status is BaselineStatus.UNKNOWN
        ],
    )


def build_earned_surface(
    baseline: RuntimeBaseline,
    projection: CanonProjection,
    *,
    created_at: str | None = None,
) -> EarnedSurface:
    """Derive available runtime surface from Baseline plus hard projection only."""

    surface_id = stable_id(
        "earned-surface",
        baseline.manifest.baseline_id,
        str(projection.through_event_seq),
        projection.sha256(),
    )
    result = EarnedSurface(
        surface_id=surface_id,
        book_id=baseline.manifest.book_id,
        edition_id=baseline.manifest.edition_id,
        baseline_id=baseline.manifest.baseline_id,
        projection_event_seq=projection.through_event_seq,
        projection_hash=projection.sha256(),
        created_at=created_at or utc_now(),
    )
    for entry in baseline.entries:
        if entry.status is BaselineStatus.UNKNOWN:
            result.hard_unknowns.append(f"{entry.category.value}:{entry.name}: {entry.statement}")
            continue
        earned = _earned_from_baseline(entry)
        if entry.category is BaselineCategory.CAPABILITY:
            result.earned_capabilities.append(earned)
        elif entry.category in {BaselineCategory.ITEM, BaselineCategory.EQUIPMENT}:
            result.available_items.append(earned)
        elif entry.category is BaselineCategory.RESOURCE:
            result.available_resources.append(earned)
        elif entry.category is BaselineCategory.RULE:
            result.known_rules.append(earned)
        elif entry.category is BaselineCategory.EXCEPTION:
            result.known_exceptions.append(earned)
        elif entry.category is BaselineCategory.KNOWLEDGE:
            result.open_setups.append(earned)
            result.actionable_knowledge.append(earned)
        elif entry.category is BaselineCategory.PROMISE:
            result.open_setups.append(earned)
            forms = [item for item in entry.attributes.get("payoff_forms", "").split("|") if item]
            result.available_payoffs.append(
                AvailablePayoff(
                    payoff_id=f"payoff:{entry.entry_id}",
                    setup=entry.statement,
                    maturity_evidence=entry.evidence,
                    last_advanced=(
                        int(entry.attributes["last_advanced"])
                        if entry.attributes.get("last_advanced", "").isdigit()
                        else None
                    ),
                    possible_payoff_forms=forms,
                    payoff_cost=entry.attributes.get("payoff_cost", ""),
                    post_payoff_pressure=entry.attributes.get("post_payoff_pressure", ""),
                    source_entry_id=entry.entry_id,
                    status=entry.status,
                )
            )
        elif entry.category is BaselineCategory.CHARACTER:
            if entry.attributes.get("institutional_authority"):
                result.institutional_authority.append(earned)
            if entry.attributes.get("relationship_leverage"):
                result.relationship_leverage.append(earned)

    for record_id, value in projection.capabilities.items():
        result.earned_capabilities.append(
            _projection_earned(
                entry_id=f"projection:capability:{record_id}",
                category=BaselineCategory.CAPABILITY.value,
                name=str(value.get("name") or record_id),
                statement=str(value.get("statement") or value.get("name") or record_id),
                record_id=str(record_id),
                value=value,
            )
        )
    for record_id, value in projection.resources.items():
        result.available_resources.append(
            _projection_earned(
                entry_id=f"projection:resource:{record_id}",
                category=BaselineCategory.RESOURCE.value,
                name=str(value.get("name") or record_id),
                statement=str(value.get("name") or record_id),
                record_id=str(record_id),
                value=value,
            )
        )
    for record_id, value in projection.promises.items():
        status = str(value.get("status") or "CANON").upper()
        if status in {"RESOLVED", "CLOSED", "PAID"}:
            continue
        setup = str(value.get("statement") or value.get("promise_id") or record_id)
        earned = _projection_earned(
            entry_id=f"projection:promise:{record_id}",
            category=BaselineCategory.PROMISE.value,
            name=str(value.get("promise_id") or record_id),
            statement=setup,
            record_id=str(record_id),
            value=value,
        )
        result.open_setups.append(earned)
        result.available_payoffs.append(
            AvailablePayoff(
                payoff_id=f"payoff:projection:{record_id}",
                setup=setup,
                last_advanced=(
                    int(value["last_reminded_ordinal"])
                    if str(value.get("last_reminded_ordinal", "")).isdigit()
                    else None
                ),
                possible_payoff_forms=[],
                payoff_cost=str(value.get("payload_json") or ""),
                post_payoff_pressure="",
                source_entry_id=None,
                status=BaselineStatus.SOURCE_VERIFIED,
            )
        )
    for record_id, value in projection.relationships.items():
        result.relationship_leverage.append(
            _projection_earned(
                entry_id=f"projection:relationship:{record_id}",
                category="relationship",
                name=str(record_id),
                statement=str(value.get("status") or record_id),
                record_id=str(record_id),
                value=value,
            )
        )
    for record_id, value in projection.knowledge.items():
        result.actionable_knowledge.append(
            _projection_earned(
                entry_id=f"projection:knowledge:{record_id}",
                category=BaselineCategory.KNOWLEDGE.value,
                name=str(value.get("name") or record_id),
                statement=str(value.get("statement") or value.get("description") or record_id),
                record_id=str(record_id),
                value=value,
            )
        )
    return result


def build_runtime_baseline(
    database: Database,
    book_id: str,
    *,
    input_path: Path | None = None,
    edition_id: str | None = None,
    boundary_chapter: int | None = None,
) -> dict[str, object]:
    """Validate a source-derived input and atomically publish its snapshot."""

    database.initialize()
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, selected_edition)
    max_chapter = max((int(item.get("ordinal", 0)) for item in chapters), default=0)
    if boundary_chapter is None:
        boundary_chapter = max_chapter
    if boundary_chapter < 0 or boundary_chapter > max_chapter:
        raise RuntimeBaselineError("boundary_chapter 超出 selected Edition 有效章节范围")
    entries: list[RuntimeBaselineEntry] = []
    warnings: list[str] = []
    if input_path is not None:
        payload = _load_input(Path(input_path).expanduser().resolve(), book_id, selected_edition)
        if payload.boundary_chapter != boundary_chapter:
            raise RuntimeBaselineError("input boundary_chapter 与命令参数不一致")
        for entry in payload.entries:
            if entry.status is BaselineStatus.UNKNOWN:
                if entry.evidence:
                    raise RuntimeBaselineError(
                        f"UNKNOWN entry 不应携带未经验证的 evidence：{entry.entry_id}"
                    )
                entries.append(entry)
            else:
                entries.append(
                    _validate_source_evidence(
                        database,
                        book_id,
                        selected_edition,
                        entry,
                        chapters,
                        boundary_chapter,
                    )
                )
    else:
        warnings.append("没有提供 Codex/source review input；所有未列出的运行事实保持 UNKNOWN")
    if not entries:
        warnings.append("当前 Baseline 没有已验证条目；不得用默认值补齐 Runtime State")
    baseline_id = stable_id("runtime-baseline", book_id, selected_edition, utc_now())
    manifest = RuntimeBaselineManifest(
        baseline_id=baseline_id,
        book_id=book_id,
        edition_id=selected_edition,
        boundary_chapter=boundary_chapter,
        created_at=utc_now(),
        entry_counts={
            category.value: sum(1 for item in entries if item.category is category)
            for category in BaselineCategory
        },
        warnings=warnings,
        files={
            "manifest": "manifest.json",
            **{category.value: filename for category, filename in _entry_files().items()},
            "earned_surface": "earned_surface.json",
        },
    )
    baseline = RuntimeBaseline(manifest=manifest, entries=entries)
    projection = rebuild_projection(
        database, book_id, edition_id=selected_edition, persist=False
    )
    earned = build_earned_surface(baseline, projection, created_at=manifest.created_at)
    root = _baseline_root(database, book_id, selected_edition)
    versions = root / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    staging = versions / f".baseline-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        (staging / "manifest.json").write_text(
            json_dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        for category, filename in _entry_files().items():
            (staging / filename).write_text(
                json_dumps(
                    [
                        item.model_dump(mode="json")
                        for item in entries
                        if item.category is category
                    ],
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        (staging / "earned_surface.json").write_text(
            json_dumps(earned.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        destination = versions / baseline_id
        if destination.exists():
            raise RuntimeBaselineError(f"Runtime Baseline 已存在，拒绝覆盖：{destination}")
        staging.replace(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    latest = root / "latest.json"
    _atomic_write_json(
        latest,
        {
            "baseline_id": baseline_id,
            "book_id": book_id,
            "edition_id": selected_edition,
            "root": str(destination),
            "manifest": str(destination / "manifest.json"),
            "earned_surface": str(destination / "earned_surface.json"),
        },
    )
    return {
        "baseline_id": baseline_id,
        "book_id": book_id,
        "edition_id": selected_edition,
        "boundary_chapter": boundary_chapter,
        "root": str(destination),
        "manifest": str(destination / "manifest.json"),
        "earned_surface": str(destination / "earned_surface.json"),
        "entry_counts": manifest.entry_counts,
        "earned_counts": {
            "capabilities": len(earned.earned_capabilities),
            "items": len(earned.available_items),
            "resources": len(earned.available_resources),
            "payoffs": len(earned.available_payoffs),
            "hard_unknowns": len(earned.hard_unknowns),
        },
        "warnings": warnings,
    }


def latest_runtime_baseline(
    database: Database, book_id: str, *, edition_id: str | None = None
) -> RuntimeBaseline | None:
    database.initialize()
    if not (book_root(database, book_id) / "book.yaml").is_file():
        return None
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    root = _baseline_root(database, book_id, selected_edition)
    pointer = root / "latest.json"
    if not pointer.is_file():
        return None
    payload = _read_json(pointer)
    if not isinstance(payload, dict):
        return None
    manifest_path = Path(str(payload.get("manifest", ""))).expanduser().resolve()
    if not manifest_path.is_file():
        return None
    manifest = RuntimeBaselineManifest.model_validate(_read_json(manifest_path))
    entries: list[RuntimeBaselineEntry] = []
    version_root = manifest_path.parent
    for filename in _entry_files().values():
        path = version_root / filename
        if not path.is_file():
            continue
        values = _read_json(path)
        if not isinstance(values, list):
            raise RuntimeBaselineError(f"Baseline artifact 必须是数组：{path}")
        entries.extend(RuntimeBaselineEntry.model_validate(item) for item in values)
    return RuntimeBaseline(manifest=manifest, entries=entries)


def load_runtime_baseline(
    database: Database, book_id: str, *, edition_id: str | None = None
) -> RuntimeBaseline | None:
    return latest_runtime_baseline(database, book_id, edition_id=edition_id)


def load_earned_surface(
    database: Database, book_id: str, *, edition_id: str | None = None
) -> EarnedSurface | None:
    baseline = latest_runtime_baseline(database, book_id, edition_id=edition_id)
    if baseline is None:
        return None
    latest = _read_json(
        _baseline_root(database, book_id, baseline.manifest.edition_id) / "latest.json"
    )
    if not isinstance(latest, dict):
        return None
    root = Path(str(latest.get("earned_surface", ""))).expanduser().resolve()
    if not root.is_file():
        return None
    try:
        return EarnedSurface.model_validate(_read_json(root))
    except Exception as exc:
        raise RuntimeBaselineError(f"Earned Surface 不符合严格模型：{root}") from exc


def load_effective_runtime_state(
    database: Database, book_id: str, *, edition_id: str | None = None
) -> EffectiveRuntimeState | None:
    """Return a fresh baseline + non-persisting Canon projection composition."""

    baseline = latest_runtime_baseline(database, book_id, edition_id=edition_id)
    if baseline is None:
        return None
    projection = rebuild_projection(
        database,
        book_id,
        edition_id=baseline.manifest.edition_id,
        persist=False,
    )
    return build_effective_runtime_state(baseline, projection)


__all__ = [
    "RuntimeBaselineError",
    "build_earned_surface",
    "build_effective_runtime_state",
    "build_runtime_baseline",
    "latest_runtime_baseline",
    "load_earned_surface",
    "load_effective_runtime_state",
    "load_runtime_baseline",
]
