from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from novel_authoring.atlas.models import (
    AtlasAction,
    AtlasArtifactManifest,
    AtlasGraph,
    AtlasValidationResult,
    FuturePossibilitySpace,
    InformationStatus,
    ReadinessStatus,
    RollingHorizon,
    StoryAtlasStatus,
    WorldModelReadiness,
)
from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.utils import json_dumps, sha256_bytes, sha256_file, stable_id, utc_now

GRAPH_FILE_TYPES = {
    "characters.json": "characters",
    "factions.json": "factions",
    "abilities.json": "abilities",
    "resources_and_items.json": "resources_and_items",
    "regions.json": "regions",
    "plot_threads.json": "plot_threads",
    "stage_transitions.json": "stage_transitions",
}
REQUIRED_ARTIFACTS = (
    "narrative_dna.md",
    "current_world_model.md",
    "world_rules.yaml",
    "unresolved_assumptions.yaml",
    "expansion_grammar.yaml",
    "graphs/characters.json",
    "graphs/factions.json",
    "graphs/abilities.json",
    "graphs/resources_and_items.json",
    "graphs/regions.json",
    "graphs/plot_threads.json",
    "graphs/stage_transitions.json",
    "visuals/character_graph.svg",
    "visuals/faction_graph.svg",
    "visuals/ability_graph.svg",
    "visuals/resource_chain.svg",
    "visuals/region_topology.svg",
    "visuals/plot_thread_graph.svg",
    "visuals/stage_ladder.svg",
    "future/active_spine.yaml",
    "future/alternative_spines.yaml",
    "future/wildcard_possibilities.yaml",
    "future/open_design_spaces.yaml",
    "future/rolling_horizon.yaml",
    "reports/coverage_report.md",
    "reports/source_coverage_report.md",
    "reports/entity_resolution_report.md",
    "reports/contradiction_report.md",
    "reports/world_model_report.md",
    "reports/readiness_report.md",
)


class AtlasError(RuntimeError):
    status_code = 409


def _book_workspace(database: Database, book_id: str) -> Path:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    if row is None:
        raise AtlasError(f"未知 book_id：{book_id}")
    return Path(str(row["workspace_root"]))


def _source_manifest_hash(database: Database, book_id: str) -> str:
    root = _book_workspace(database, book_id)
    path = root / "source_manifest.json"
    return sha256_file(path) if path.is_file() else ""


def atlas_root(database: Database, book_id: str, edition_id: str | None = None) -> Path:
    """Return the edition-scoped soft-artifact directory without creating it."""
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    book_root = _book_workspace(database, book_id).resolve()
    edition_root = (book_root / "editions" / selected).resolve()
    if book_root not in edition_root.parents:
        raise AtlasError("edition workspace 越界")
    return edition_root / "story_atlas"


def _safe_artifact_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise AtlasError(f"Atlas artifact 路径越界：{relative_path}")
    if Path(relative_path).is_absolute():
        raise AtlasError(f"Atlas artifact 必须是相对路径：{relative_path}")
    return candidate


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _atlas_content_hash(manifest: AtlasArtifactManifest) -> str:
    """Hash the immutable soft artifacts, excluding the manifest itself."""
    payload = {
        path: manifest.artifact_hashes[path]
        for path in sorted(manifest.artifact_hashes)
        if path not in {"atlas_manifest.json", "future/rolling_horizon.yaml"}
    }
    return sha256_bytes(json_dumps(payload).encode("utf-8"))


def _source_span_ids(
    database: Database,
    book_id: str,
    edition_id: str,
    requested: set[str],
) -> set[str]:
    if not requested:
        return set()
    placeholders = ",".join("?" for _ in requested)
    parameters: tuple[object, ...] = (book_id, edition_id, *sorted(requested))
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT span_id FROM source_spans "
            "WHERE book_id=? AND (edition_id=? OR edition_id='base') "
            f"AND span_id IN ({placeholders})",
            parameters,
        ).fetchall()
    return {str(row["span_id"]) for row in rows}


def _future_space_from_files(atlas_dir: Path) -> FuturePossibilitySpace | None:
    combined = atlas_dir / "future" / "possibility_space.yaml"
    if combined.is_file():
        return FuturePossibilitySpace.model_validate(_load_yaml(combined))

    active_path = atlas_dir / "future" / "active_spine.yaml"
    alternatives_path = atlas_dir / "future" / "alternative_spines.yaml"
    wildcards_path = atlas_dir / "future" / "wildcard_possibilities.yaml"
    open_spaces_path = atlas_dir / "future" / "open_design_spaces.yaml"
    if not active_path.is_file():
        return None
    alternatives = _load_yaml(alternatives_path) if alternatives_path.is_file() else []
    wildcards = _load_yaml(wildcards_path) if wildcards_path.is_file() else []
    open_spaces = _load_yaml(open_spaces_path) if open_spaces_path.is_file() else []
    if isinstance(alternatives, dict):
        alternatives = alternatives.get("alternative_spines", [])
    if isinstance(wildcards, dict):
        wildcards = wildcards.get("wildcard_possibilities", [])
    if isinstance(open_spaces, dict):
        open_spaces = open_spaces.get("open_design_spaces", [])
    return FuturePossibilitySpace.model_validate(
        {
            "active_spine": _load_yaml(active_path),
            "alternative_spines": alternatives,
            "wildcard_possibilities": wildcards,
            "open_design_spaces": open_spaces,
        }
    )


def _manifest_path(root: Path) -> Path:
    return root / "atlas_manifest.json"


def _current_anchor(
    database: Database, book_id: str, edition_id: str
) -> tuple[int, str, int]:
    with database.connect() as connection:
        projection = projection_from_connection(connection, book_id, edition_id)
        chapter_rows = edition_chapters(connection, book_id, edition_id)
    current_ordinal = int(chapter_rows[-1]["ordinal"]) if chapter_rows else 0
    return projection.through_event_seq, projection.sha256(), current_ordinal


def _declared_readiness(
    manifest: AtlasArtifactManifest, *, errors: list[str], warnings: list[str]
) -> WorldModelReadiness:
    declared = manifest.readiness
    if errors:
        return WorldModelReadiness(
            status=ReadinessStatus.BLOCKED,
            current_boundary_confirmed=declared.current_boundary_confirmed,
            core_rules_covered=declared.core_rules_covered,
            protagonist_state_confirmed=declared.protagonist_state_confirmed,
            main_threads_connected=declared.main_threads_connected,
            source_coverage=declared.source_coverage,
            graph_coverage=declared.graph_coverage,
            blocking_reasons=sorted(set([*declared.blocking_reasons, *errors])),
            gaps=declared.gaps,
            review_queue=declared.review_queue,
        )
    if warnings and declared.status is ReadinessStatus.READY:
        return WorldModelReadiness(
            status=ReadinessStatus.READY_WITH_GAPS,
            current_boundary_confirmed=declared.current_boundary_confirmed,
            core_rules_covered=declared.core_rules_covered,
            protagonist_state_confirmed=declared.protagonist_state_confirmed,
            main_threads_connected=declared.main_threads_connected,
            source_coverage=declared.source_coverage,
            graph_coverage=declared.graph_coverage,
            blocking_reasons=declared.blocking_reasons,
            gaps=sorted(set([*declared.gaps, *warnings])),
            review_queue=declared.review_queue,
        )
    return declared


def validate_atlas(
    database: Database,
    book_id: str,
    edition_id: str,
    *,
    root: Path | None = None,
) -> AtlasValidationResult:
    """Validate soft Atlas files against deterministic edition/source anchors.

    This function never writes Canon events or projection rows.  The manifest's
    semantic readiness is a declaration from the LLM/editor; Python only
    verifies its shape, evidence rules, hashes, edition anchor and file safety.
    """
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    if root is None:
        with database.connect() as connection:
            active_row = connection.execute(
                "SELECT artifact_root FROM story_atlases WHERE book_id=? AND edition_id=? "
                "AND status='ACTIVE' ORDER BY atlas_version DESC LIMIT 1",
                (book_id, selected),
            ).fetchone()
        selected_root = (
            Path(str(active_row["artifact_root"]))
            if active_row is not None
            else atlas_root(database, book_id, selected)
        )
    else:
        selected_root = root
    atlas_dir = selected_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest_file = _manifest_path(atlas_dir)
    if not manifest_file.is_file():
        raise AtlasError(f"Atlas manifest 不存在：{manifest_file}")
    try:
        manifest = AtlasArtifactManifest.model_validate(_load_json(manifest_file))
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise AtlasError(f"Atlas manifest 无法验证：{exc}") from exc

    if manifest.book_id != book_id or manifest.edition_id != selected:
        errors.append("Atlas manifest 的 book_id/edition_id 与请求不一致")
    event_seq, projection_hash, current_ordinal = _current_anchor(database, book_id, selected)
    source_hash = _source_manifest_hash(database, book_id)
    if manifest.base_event_seq != event_seq:
        errors.append("Atlas base_event_seq 已漂移")
    if manifest.base_projection_hash != projection_hash:
        errors.append("Atlas base_projection_hash 已漂移")
    if manifest.source_manifest_sha256 != source_hash:
        errors.append("Atlas source_manifest_sha256 已漂移")
    if manifest.atlas_content_hash and manifest.atlas_content_hash != _atlas_content_hash(manifest):
        errors.append("Atlas atlas_content_hash 与 artifact hashes 不一致")
    if manifest.current_chapter_ordinal != current_ordinal:
        warnings.append("Atlas current_chapter_ordinal 需要 refresh")
    if manifest.status is StoryAtlasStatus.INVALIDATED:
        warnings.append("Atlas 已标记 INVALIDATED")
    required_far = required_far_end_chapter(
        current_ordinal,
        manifest.batch_target_chapters,
    )
    if manifest.far_horizon_end_chapter < required_far:
        errors.append("Atlas FAR horizon 未覆盖当前故事和 Batch 目标的两倍")

    graphs: dict[str, AtlasGraph] = {}
    for relative_path in manifest.artifact_paths:
        try:
            path = _safe_artifact_path(atlas_dir, relative_path)
        except AtlasError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"Atlas artifact 不存在：{relative_path}")
            continue
        if relative_path != "atlas_manifest.json":
            expected_hash = manifest.artifact_hashes.get(relative_path)
            if expected_hash is None:
                errors.append(f"Atlas artifact 缺少 hash：{relative_path}")
            elif sha256_file(path) != expected_hash:
                errors.append(f"Atlas artifact hash 不匹配：{relative_path}")
        if relative_path.startswith("graphs/") and path.suffix == ".json":
            try:
                data = _load_json(path)
                graph = AtlasGraph.model_validate(data)
                expected_type = GRAPH_FILE_TYPES.get(path.name)
                if expected_type is not None and graph.graph_type != expected_type:
                    errors.append(f"{relative_path} graph_type 不匹配")
                if graph.atlas_version != manifest.atlas_version:
                    errors.append(f"{relative_path} atlas_version 不匹配")
                graphs[graph.graph_type] = graph
            except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
                errors.append(f"图谱 {relative_path} 无法验证：{exc}")

    declared_paths = set(manifest.artifact_paths)
    for required in REQUIRED_ARTIFACTS:
        if required not in declared_paths:
            if manifest.source_coverage:
                errors.append(f"Atlas 缺少初始化必需 artifact：{required}")
            else:
                warnings.append(f"Atlas 缺少推荐 artifact：{required}")

    future_space: FuturePossibilitySpace | None = None
    try:
        future_space = _future_space_from_files(atlas_dir)
    except (OSError, ValidationError, ValueError, TypeError) as exc:
        errors.append(f"Future Possibility Space 无法验证：{exc}")
    rolling_horizon: RollingHorizon | None = None
    horizon_path = atlas_dir / "future" / "rolling_horizon.yaml"
    if horizon_path.is_file():
        try:
            rolling_horizon = RollingHorizon.model_validate(_load_yaml(horizon_path))
            if rolling_horizon.horizon_id != manifest.horizon_id:
                errors.append("Rolling Horizon horizon_id 与 Atlas manifest 不匹配")
            if rolling_horizon.horizon_hash != manifest.horizon_hash:
                errors.append("Rolling Horizon horizon_hash 与 Atlas manifest 不匹配")
            if rolling_horizon.atlas_id != manifest.atlas_id:
                errors.append("Rolling Horizon 未锚定当前 Atlas")
            if rolling_horizon.atlas_version != manifest.atlas_version:
                errors.append("Rolling Horizon atlas_version 与 Atlas manifest 不匹配")
            if rolling_horizon.atlas_content_hash != manifest.atlas_content_hash:
                errors.append("Rolling Horizon atlas_content_hash 与 Atlas manifest 不匹配")
            if rolling_horizon.base_projection_hash != manifest.base_projection_hash:
                errors.append("Rolling Horizon base_projection_hash 已漂移")
            if rolling_horizon.current_chapter_ordinal != current_ordinal:
                warnings.append("Rolling Horizon current_chapter_ordinal 需要 refresh")
            if rolling_horizon.required_far_end_chapter < required_far:
                errors.append("Rolling Horizon FAR 未覆盖当前故事和 Batch 目标的两倍")
        except (OSError, ValidationError, ValueError) as exc:
            errors.append(f"Rolling Horizon 无法验证：{exc}")

    evidence_ids: set[str] = set()
    for graph in graphs.values():
        for node in graph.nodes:
            evidence_ids.update(node.evidence.source_span_ids)
        for edge in graph.edges:
            evidence_ids.update(edge.evidence.source_span_ids)
    if future_space is not None:
        for spine in (
            future_space.active_spine,
            *future_space.alternative_spines,
            *future_space.wildcard_possibilities,
        ):
            evidence_ids.update(spine.evidence.source_span_ids)
    found_evidence = _source_span_ids(database, book_id, selected, evidence_ids)
    missing_evidence = sorted(evidence_ids - found_evidence)
    if missing_evidence:
        errors.append(f"Atlas 引用了不存在或不属于当前 source 的 source_span：{missing_evidence}")

    readiness = _declared_readiness(manifest, errors=errors, warnings=warnings)
    return AtlasValidationResult(
        manifest=manifest,
        readiness=readiness,
        graph_views=graphs,
        future_space=future_space,
        rolling_horizon=rolling_horizon,
        files_checked=sorted(declared_paths),
        errors=sorted(set(errors)),
        warnings=sorted(set(warnings)),
    )


def register_atlas(
    database: Database,
    book_id: str,
    edition_id: str,
    *,
    root: Path | None = None,
    allow_gaps: bool = True,
) -> dict[str, Any]:
    """Register a validated soft Atlas index; never materialize its content as Canon."""
    selected = resolve_edition_id(database, book_id, edition_id)
    result = validate_atlas(database, book_id, edition_id, root=root)
    if result.errors:
        raise AtlasError("Atlas 不能登记：" + "；".join(result.errors))
    if not allow_gaps and result.readiness.status is not ReadinessStatus.READY:
        raise AtlasError(f"Atlas readiness 不满足要求：{result.readiness.status.value}")
    source_root = (root or atlas_root(database, book_id, selected)).resolve()
    manifest_path = _manifest_path(source_root)
    manifest = result.manifest
    artifact_manifest_hash = sha256_file(manifest_path)
    atlas_content_hash = manifest.atlas_content_hash or _atlas_content_hash(manifest)
    now = utc_now()
    with database.connect() as connection:
        existing = connection.execute(
            "SELECT * FROM story_atlases WHERE atlas_id=?",
            (manifest.atlas_id,),
        ).fetchone()
        if existing is not None:
            same_content = (
                str(existing["book_id"]) == book_id
                and str(existing["edition_id"]) == selected
                and int(existing["atlas_version"]) == manifest.atlas_version
                and str(existing["artifact_manifest_sha256"]) == artifact_manifest_hash
                and str(existing["atlas_content_hash"] or "") == atlas_content_hash
            )
            if not same_content:
                raise AtlasError("Atlas ID 已存在但内容或作用域不同；版本化 Atlas 不可覆盖")
            return get_atlas_overview(
                database,
                book_id,
                selected,
                atlas_id=manifest.atlas_id,
            )
        version_row = connection.execute(
            "SELECT atlas_id FROM story_atlases WHERE book_id=? AND edition_id=? "
            "AND atlas_version=?",
            (book_id, selected, manifest.atlas_version),
        ).fetchone()
        if version_row is not None:
            raise AtlasError("Atlas version 已存在；请使用新的 atlas_id 和版本")
        if manifest.parent_atlas_id is not None:
            parent = connection.execute(
                "SELECT atlas_version FROM story_atlases WHERE atlas_id=? "
                "AND book_id=? AND edition_id=?",
                (manifest.parent_atlas_id, book_id, selected),
            ).fetchone()
            if parent is None or int(parent["atlas_version"]) >= manifest.atlas_version:
                raise AtlasError("Atlas parent 必须是同一 edition 中更早的已登记版本")

    # Copy a staging Atlas into a version-addressed directory only after every
    # collision/parent check has passed.  The database row then points at this
    # immutable copy, so later edits to the staging directory cannot rewrite a
    # registered version.
    canonical_root = (
        atlas_root(database, book_id, selected) / "versions" / manifest.atlas_id
    ).resolve()
    if source_root != canonical_root:
        if canonical_root.exists():
            raise AtlasError("Atlas immutable artifact 目录已存在但尚未登记，拒绝覆盖")
        canonical_root.mkdir(parents=True, exist_ok=False)
        for relative_path in [*manifest.artifact_paths, "atlas_manifest.json"]:
            source_path = _safe_artifact_path(source_root, relative_path)
            target_path = _safe_artifact_path(canonical_root, relative_path)
            if not source_path.is_file():
                raise AtlasError(f"Atlas artifact 在 immutable copy 前消失：{relative_path}")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
        manifest_path = canonical_root / "atlas_manifest.json"

    with database.connect() as connection:
        connection.execute(
            "UPDATE story_atlases SET status='INVALIDATED', invalidated_at=? "
            "WHERE book_id=? AND edition_id=? AND status='ACTIVE' AND atlas_version<?",
            (now, book_id, selected, manifest.atlas_version),
        )
        connection.execute(
            """
            INSERT INTO story_atlases(
                atlas_id, book_id, edition_id, atlas_version, base_event_seq,
                parent_atlas_id, base_projection_hash, source_manifest_sha256,
                effective_content_sha256, registry_hash, config_hash,
                analyzer_versions_hash, horizon_id, horizon_hash,
                artifact_root, manifest_path,
                artifact_manifest_sha256, atlas_content_hash, status,
                readiness_status, readiness_json, author_accepted, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)
            """,
            (
                manifest.atlas_id,
                book_id,
                selected,
                manifest.atlas_version,
                manifest.base_event_seq,
                manifest.parent_atlas_id,
                manifest.base_projection_hash,
                manifest.source_manifest_sha256,
                manifest.effective_content_sha256,
                manifest.registry_hash,
                manifest.config_hash,
                manifest.analyzer_versions_hash,
                manifest.horizon_id,
                manifest.horizon_hash,
                str(manifest_path.parent),
                str(manifest_path),
                artifact_manifest_hash,
                atlas_content_hash,
                StoryAtlasStatus.ACTIVE.value,
                result.readiness.status.value,
                json_dumps(result.readiness.model_dump(mode="json")),
                now,
            ),
        )
    return get_atlas_overview(database, book_id, selected, atlas_id=manifest.atlas_id)


def latest_atlas(database: Database, book_id: str, edition_id: str) -> dict[str, Any] | None:
    database.initialize()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM story_atlases WHERE book_id=? AND edition_id=? "
            "AND status='ACTIVE' ORDER BY atlas_version DESC, created_at DESC LIMIT 1",
            (book_id, edition_id),
        ).fetchone()
    return None if row is None else dict(row)


def list_atlas_history(database: Database, book_id: str, edition_id: str) -> list[dict[str, Any]]:
    database.initialize()
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM story_atlases WHERE book_id=? AND edition_id=? "
            "ORDER BY atlas_version DESC, created_at DESC",
            (book_id, edition_id),
        ).fetchall()
    return [dict(row) for row in rows]


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def get_atlas_overview(
    database: Database,
    book_id: str,
    edition_id: str,
    *,
    atlas_id: str | None = None,
) -> dict[str, Any]:
    row = None
    with database.connect() as connection:
        if atlas_id is None:
            row = connection.execute(
                "SELECT * FROM story_atlases WHERE book_id=? AND edition_id=? "
                "AND status='ACTIVE' ORDER BY atlas_version DESC LIMIT 1",
                (book_id, edition_id),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM story_atlases WHERE atlas_id=? AND book_id=? AND edition_id=?",
                (atlas_id, book_id, edition_id),
            ).fetchone()
    if row is None:
        return {
            "available": False,
            "book_id": book_id,
            "edition_id": edition_id,
            "history": list_atlas_history(database, book_id, edition_id),
        }
    root = Path(str(row["artifact_root"]))
    validation = validate_atlas(database, book_id, edition_id, root=root)
    actions = []
    review_queue = []
    with database.connect() as connection:
        actions = [
            dict(item)
            for item in connection.execute(
                "SELECT * FROM story_atlas_actions WHERE atlas_id=? ORDER BY created_at DESC",
                (str(row["atlas_id"]),),
            ).fetchall()
        ]
        review_queue = [
            dict(item)
            for item in connection.execute(
                "SELECT * FROM story_atlas_review_queue WHERE atlas_id=? "
                "ORDER BY created_at DESC",
                (str(row["atlas_id"]),),
            ).fetchall()
        ]
    return {
        "available": True,
        "index": dict(row),
        "manifest": validation.manifest.model_dump(mode="json"),
        "readiness": validation.readiness.model_dump(mode="json"),
        "errors": validation.errors,
        "warnings": validation.warnings,
        "graphs": {
            name: graph.model_dump(mode="json") for name, graph in validation.graph_views.items()
        },
        "future_space": _json_value(validation.future_space),
        "rolling_horizon": _json_value(validation.rolling_horizon),
        "actions": actions,
        "review_queue": review_queue,
        "history": list_atlas_history(database, book_id, edition_id),
    }


def record_atlas_action(
    database: Database,
    book_id: str,
    edition_id: str,
    action: AtlasAction,
    *,
    atlas_id: str | None = None,
    expected_atlas_version: int | None = None,
    expected_manifest_hash: str | None = None,
) -> dict[str, Any]:
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    selected = atlas_id or (
        latest_atlas(database, book_id, selected_edition) or {}
    ).get("atlas_id")
    if not selected:
        raise AtlasError("没有可操作的 Story Atlas")
    with database.connect() as connection:
        atlas = connection.execute(
            "SELECT * FROM story_atlases WHERE atlas_id=? AND book_id=? AND edition_id=?",
            (selected, book_id, selected_edition),
        ).fetchone()
        if atlas is None:
            raise AtlasError("Atlas 不属于当前 book/edition")
        if str(atlas["status"]) != StoryAtlasStatus.ACTIVE.value:
            raise AtlasError("只有 ACTIVE Atlas 可以接受作者操作")
        if (
            expected_atlas_version is not None
            and int(atlas["atlas_version"]) != expected_atlas_version
        ):
            raise AtlasError("Atlas 版本已变化，请刷新后重试")
        if (
            expected_manifest_hash is not None
            and str(atlas["artifact_manifest_sha256"]) != expected_manifest_hash
        ):
            raise AtlasError("Atlas manifest hash 已变化，请刷新后重试")
    validation = validate_atlas(
        database,
        book_id,
        selected_edition,
        root=Path(str(atlas["artifact_root"])),
    )
    if validation.errors:
        raise AtlasError("Atlas 当前校验失败，拒绝作者操作：" + "；".join(validation.errors))
    if validation.manifest.atlas_id != str(selected):
        raise AtlasError("Atlas manifest 与登记索引不一致，拒绝作者操作")
    if (
        action.action_type == "ACCEPT_ATLAS"
        and validation.readiness.status is ReadinessStatus.BLOCKED
    ):
        raise AtlasError("BLOCKED Atlas 不能被作者接受")
    with database.connect() as connection:
        action_id = stable_id(
            "atlas-action",
            str(selected),
            action.action_type,
            str(action.target_id or ""),
            utc_now(),
        )
        now = utc_now()
        connection.execute(
            """
            INSERT INTO story_atlas_actions(
                action_id, atlas_id, book_id, edition_id, action_type,
                target_id, payload_json, actor, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                action_id,
                selected,
                book_id,
                selected_edition,
                action.action_type,
                action.target_id,
                json_dumps(action.payload),
                action.actor,
                now,
            ),
        )
        if action.action_type == "ACCEPT_ATLAS":
            connection.execute(
                "UPDATE story_atlases SET author_accepted=1, version=version+1 WHERE atlas_id=?",
                (selected,),
            )
        if action.action_type == "ADD_REVIEW_QUEUE" and action.target_id:
            review_id = stable_id("atlas-review", str(selected), action.target_id, now)
            connection.execute(
                """
                INSERT INTO story_atlas_review_queue(
                    review_id, atlas_id, book_id, edition_id, target_type,
                    target_id, reason, status, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, 1)
                """,
                (
                    review_id,
                    selected,
                    book_id,
                    selected_edition,
                    str(action.payload.get("target_type", "ATLAS_ENTRY")),
                    action.target_id,
                    str(action.payload.get("reason", "作者要求复核")),
                    now,
                ),
            )
    return {
        "action_id": action_id,
        "atlas_id": selected,
        "action_type": action.action_type,
        "target_id": action.target_id,
    }


def accept_atlas(
    database: Database, book_id: str, edition_id: str, *, atlas_id: str | None = None
) -> dict[str, Any]:
    return record_atlas_action(
        database,
        book_id,
        edition_id,
        AtlasAction(action_type="ACCEPT_ATLAS"),
        atlas_id=atlas_id,
    )


def required_far_end_chapter(current_chapter_ordinal: int, batch_target_chapters: int) -> int:
    return max(current_chapter_ordinal * 2, batch_target_chapters * 2)


def validate_far_horizon_coverage(
    current_chapter_ordinal: int,
    batch_target_chapters: int,
    far_end_chapter: int,
) -> bool:
    return far_end_chapter >= required_far_end_chapter(
        current_chapter_ordinal, batch_target_chapters
    )


def validate_stable_entity_ids(previous: Any, current: Any) -> list[str]:
    """Return deterministic identity violations between two graph versions."""
    previous_nodes = {node.node_id: node for node in previous.nodes}
    current_nodes = {node.node_id: node for node in current.nodes}
    violations: list[str] = []
    previous_canon_names = {
        (node.node_type, node.name): node.node_id
        for node in previous.nodes
        if node.information_status is InformationStatus.CANON
    }
    for node in current.nodes:
        key = (node.node_type, node.name)
        old_id = previous_canon_names.get(key)
        if old_id is not None and old_id != node.node_id:
            violations.append(f"{key} 的稳定 Entity ID 从 {old_id} 变为 {node.node_id}")
    for node_id in previous_nodes:
        if node_id in current_nodes:
            continue
        if previous_nodes[node_id].information_status is InformationStatus.CANON:
            violations.append(f"CANON Entity {node_id} 在新 Atlas 中消失")
    return violations


def atlas_usage(
    database: Database,
    *,
    atlas_id: str,
    book_id: str,
    edition_id: str,
    usage_kind: str,
    batch_id: str | None = None,
    handoff_id: str | None = None,
) -> str:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT atlas_version, atlas_content_hash FROM story_atlases "
            "WHERE atlas_id=? AND book_id=? AND edition_id=?",
            (atlas_id, book_id, edition_id),
        ).fetchone()
    if row is None:
        raise AtlasError("Atlas usage 引用了不存在或跨 edition 的 Atlas")
    usage_id = stable_id(
        "atlas-usage", atlas_id, usage_kind, batch_id or "", handoff_id or "", utc_now()
    )
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO story_atlas_usage(
                usage_id, atlas_id, book_id, edition_id, atlas_version,
                atlas_hash, batch_id, handoff_id, usage_kind, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                usage_id,
                atlas_id,
                book_id,
                edition_id,
                int(row["atlas_version"]),
                str(row["atlas_content_hash"] or ""),
                batch_id,
                handoff_id,
                usage_kind,
                utc_now(),
            ),
        )
    return usage_id
