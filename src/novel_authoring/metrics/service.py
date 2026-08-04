from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.metrics.formulas import (
    agency,
    legibility,
    narrative_debt,
    outcome_uncertainty,
    payoff_score,
    pressure,
    progress,
    repetition_fatigue,
    resource_pressure,
    risk_credibility,
)
from novel_authoring.metrics.models import (
    ContributionKind,
    EvidenceDirection,
    EvidenceSummary,
    MetricComponentStatus,
    MetricComponentValue,
    MetricInputBundleV2,
    MetricResultV2,
    MetricRunStatus,
    MetricSemanticObservationsOutput,
    ObservationResolution,
    ObservationSourceKind,
)
from novel_authoring.metrics.registry import (
    MetricSourceKind,
    MetricsRegistry,
    load_registry,
)
from novel_authoring.metrics.segments import segment_contains_quote
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now


class MetricConflictError(RuntimeError):
    status_code = 409


class MetricValidationError(ValueError):
    pass


class ObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    book_id: str
    edition_id: str
    scope_type: str
    scope_id: str
    metric_id: str
    component_id: str
    value: Any | None = None
    status: MetricComponentStatus = MetricComponentStatus.AVAILABLE
    source_kind: ObservationSourceKind
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = ""
    chapter_id: str | None = None
    effective_content_sha256: str | None = None
    projection_hash: str | None = None
    registry_hash: str | None = None
    config_hash: str | None = None
    expected_active_observation_id: str | None = None
    source_task_id: str | None = None
    analyzer_version: str | None = None
    evidence_links: list[dict[str, Any]] = Field(default_factory=list)


def _numeric(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _json_value(value: Any) -> str:
    return json_dumps(value)


_SEMANTIC_SOURCE_PRIORITY: dict[ObservationSourceKind, int] = {
    ObservationSourceKind.AUTHOR_OVERRIDE: 500,
    ObservationSourceKind.AUTHOR_INPUT: 400,
    ObservationSourceKind.SEMANTIC_ESTIMATE: 300,
    ObservationSourceKind.DERIVED: 200,
    ObservationSourceKind.UNKNOWN: 0,
}
_DETERMINISTIC_SOURCE_PRIORITY: dict[ObservationSourceKind, int] = {
    ObservationSourceKind.DETERMINISTIC: 1000,
    ObservationSourceKind.DERIVED: 800,
}


class ObservationResolver:
    """Resolve one component from append-only observations.

    ``active`` is only a write-side optimization retained for compatibility;
    validity is determined from the complete non-retracted history here.  That
    makes explicit retraction recover the previous observation without
    manufacturing a new historical row.
    """

    def __init__(self, database: Database, registry: MetricsRegistry | None = None) -> None:
        self.database = database
        self.registry = registry or load_registry()
        self.config_hash = sha256_bytes(json_dumps(load_settings().metrics).encode("utf-8"))

    def _stale_reason(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        book_id: str,
        edition_id: str,
    ) -> str:
        reasons: list[str] = []
        stored_config = str(row["config_hash"] or "")
        if stored_config and stored_config != self.config_hash:
            reasons.append("config_hash changed")
        stored_registry = str(row["registry_hash"] or "")
        if stored_registry and stored_registry != self.registry.registry_hash:
            reasons.append("registry_hash changed")
        stored_projection = str(row["projection_hash"] or "")
        if stored_projection:
            projection_hash = projection_from_connection(connection, book_id, edition_id).sha256()
            if stored_projection != projection_hash:
                reasons.append("projection_hash changed")
        content_hash = row["effective_content_sha256"]
        chapter_id = row["chapter_id"]
        if content_hash and chapter_id:
            chapter = next(
                (
                    item
                    for item in edition_chapters(connection, book_id, edition_id)
                    if str(item["chapter_id"]) == str(chapter_id)
                ),
                None,
            )
            if chapter is None:
                reasons.append("effective chapter missing")
            elif str(chapter.get("content_sha256") or "") != str(content_hash):
                reasons.append("effective chapter content changed")
        stored_status = str(row["freshness_status"] or "FRESH")
        if stored_status == "STALE":
            reasons.append(str(row["stale_reason"] or "marked stale"))
        return "; ".join(dict.fromkeys(reasons))

    def _priority(self, metric_id: str, component_id: str, source: ObservationSourceKind) -> int:
        definition = self.registry.component(metric_id, component_id)
        if ObservationSourceKind.DETERMINISTIC in {
            ObservationSourceKind(item.value) for item in definition.allowed_source_kinds
        }:
            return _DETERMINISTIC_SOURCE_PRIORITY.get(
                source, _SEMANTIC_SOURCE_PRIORITY.get(source, 0)
            )
        return _SEMANTIC_SOURCE_PRIORITY.get(source, 0)

    def resolve(
        self,
        book_id: str,
        edition_id: str,
        scope_type: str,
        scope_id: str,
        metric_id: str,
        component_id: str,
    ) -> ObservationResolution:
        self.database.initialize()
        self.registry.component(metric_id, component_id)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM metric_observations WHERE book_id=? AND edition_id=? "
                "AND scope_type=? AND scope_id=? AND metric_id=? AND component_id=? "
                "AND retracted_at IS NULL ORDER BY created_at, observation_id",
                (book_id, edition_id, scope_type, scope_id, metric_id, component_id),
            ).fetchall()
            if not rows:
                return ObservationResolution(status=MetricComponentStatus.MISSING)
            fresh: list[tuple[sqlite3.Row, int]] = []
            stale: list[dict[str, Any]] = []
            for row in rows:
                stale_reason = self._stale_reason(connection, row, book_id, edition_id)
                if stale_reason:
                    stale.append(
                        {
                            "observation_id": str(row["observation_id"]),
                            "reason": stale_reason,
                            "source_kind": str(row["source_kind"]),
                        }
                    )
                    continue
                source = ObservationSourceKind(str(row["source_kind"]))
                fresh.append((row, self._priority(metric_id, component_id, source)))
            if not fresh:
                return ObservationResolution(
                    status=MetricComponentStatus.STALE,
                    ignored_observations=stale,
                    stale_reason="; ".join(item["reason"] for item in stale),
                )
            highest = max(priority for _, priority in fresh)
            winners = [(row, priority) for row, priority in fresh if priority == highest]
            values = [json.loads(str(row["value_json"])) for row, _ in winners]
            unique_values: list[Any] = []
            for value in values:
                if not any(value == existing for existing in unique_values):
                    unique_values.append(value)
            ignored = [
                {
                    "observation_id": str(row["observation_id"]),
                    "source_kind": str(row["source_kind"]),
                    "priority": priority,
                    "value": json.loads(str(row["value_json"])),
                }
                for row, priority in fresh
                if priority < highest
            ] + stale
            if len(unique_values) > 1:
                return ObservationResolution(
                    status=MetricComponentStatus.DISPUTED,
                    ignored_observations=ignored,
                    conflicts=[
                        {
                            "observation_id": str(row["observation_id"]),
                            "value": json.loads(str(row["value_json"])),
                            "source_kind": str(row["source_kind"]),
                            "priority": priority,
                        }
                        for row, priority in winners
                    ],
                )
            row, _ = sorted(
                winners,
                key=lambda pair: (str(pair[0]["created_at"]), str(pair[0]["observation_id"])),
            )[-1]
            source_kind = ObservationSourceKind(str(row["source_kind"]))
            selected_reason = (
                f"选择 {source_kind.value}（priority={highest}）；"
                f"候选历史 {len(rows)} 条，当前有效 {len(fresh)} 条"
            )
            return ObservationResolution(
                status=MetricComponentStatus(str(row["status"])),
                effective_observation_id=str(row["observation_id"]),
                value=json.loads(str(row["value_json"])),
                source_kind=source_kind,
                confidence=None if row["confidence"] is None else float(row["confidence"]),
                selected_reason=selected_reason,
                ignored_observations=ignored,
            )

    def resolve_scope(
        self, book_id: str, edition_id: str, scope_type: str, scope_id: str
    ) -> dict[tuple[str, str], ObservationResolution]:
        self.database.initialize()
        with self.database.connect() as connection:
            keys = connection.execute(
                "SELECT DISTINCT metric_id, component_id FROM metric_observations "
                "WHERE book_id=? AND edition_id=? AND scope_type=? AND scope_id=?",
                (book_id, edition_id, scope_type, scope_id),
            ).fetchall()
        return {
            (str(row["metric_id"]), str(row["component_id"])): self.resolve(
                book_id,
                edition_id,
                scope_type,
                scope_id,
                str(row["metric_id"]),
                str(row["component_id"]),
            )
            for row in keys
        }


def _active_observation_row(
    connection: sqlite3.Connection,
    book_id: str,
    edition_id: str,
    scope_type: str,
    scope_id: str,
    metric_id: str,
    component_id: str,
) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        connection.execute(
            """
        SELECT * FROM metric_observations
        WHERE book_id=? AND edition_id=? AND scope_type=? AND scope_id=?
          AND metric_id=? AND component_id=? AND active=1
        ORDER BY created_at DESC, observation_id DESC LIMIT 1
        """,
            (book_id, edition_id, scope_type, scope_id, metric_id, component_id),
        ).fetchone(),
    )


class MetricObservationService:
    def __init__(self, database: Database, registry: MetricsRegistry | None = None) -> None:
        self.database = database
        self.registry = registry or load_registry()

    def append(self, observation: ObservationInput) -> str:
        self.database.initialize()
        self.registry.metric(observation.metric_id)
        self.registry.component(observation.metric_id, observation.component_id)
        self.registry.validate_source(
            observation.metric_id,
            observation.component_id,
            MetricSourceKind(observation.source_kind.value),
        )
        if (
            observation.source_kind
            in (
                ObservationSourceKind.AUTHOR_OVERRIDE,
                ObservationSourceKind.AUTHOR_INPUT,
            )
            and not observation.reason.strip()
        ):
            raise MetricValidationError("AUTHOR_INPUT/AUTHOR_OVERRIDE 必须提供 reason")
        if (
            observation.source_kind == ObservationSourceKind.AUTHOR_OVERRIDE
            and not observation.reason.strip()
        ):
            raise MetricValidationError("AUTHOR_OVERRIDE 必须提供 reason")
        numeric = _numeric(observation.value)
        component_definition = self.registry.component(
            observation.metric_id, observation.component_id
        )
        if numeric is not None:
            if component_definition.minimum is not None and numeric < component_definition.minimum:
                raise MetricValidationError("component 数值低于注册表下限")
            if component_definition.maximum is not None and numeric > component_definition.maximum:
                raise MetricValidationError("component 数值超过注册表上限")
        with self.database.connect() as connection:
            projection = projection_from_connection(
                connection, observation.book_id, observation.edition_id
            )
            if observation.projection_hash and observation.projection_hash != projection.sha256():
                raise MetricConflictError("projection 已变化，请刷新后重试")
            current_config_hash = sha256_bytes(
                json_dumps(load_settings().metrics).encode("utf-8")
            )
            if (
                observation.registry_hash
                and observation.registry_hash != self.registry.registry_hash
            ):
                raise MetricConflictError("registry 已变化，请刷新后重试")
            if observation.config_hash and observation.config_hash != current_config_hash:
                raise MetricConflictError("config 已变化，请刷新后重试")
            resolver = ObservationResolver(self.database, self.registry)
            resolved = resolver.resolve(
                observation.book_id,
                observation.edition_id,
                observation.scope_type,
                observation.scope_id,
                observation.metric_id,
                observation.component_id,
            )
            if observation.expected_active_observation_id is not None:
                actual = resolved.effective_observation_id
                if actual != observation.expected_active_observation_id:
                    raise MetricConflictError("active observation 已变化，请刷新后重试")
            if observation.chapter_id and observation.effective_content_sha256:
                chapter = next(
                    (
                        item
                        for item in edition_chapters(
                            connection, observation.book_id, observation.edition_id
                        )
                        if str(item["chapter_id"]) == observation.chapter_id
                    ),
                    None,
                )
                if (
                    chapter is not None
                    and str(chapter["content_sha256"]) != observation.effective_content_sha256
                ):
                    raise MetricConflictError("章节内容 hash 已变化，请刷新后重试")
            current_id = resolved.effective_observation_id
            status = observation.status.value
            # Superseding is not retraction: old rows remain eligible for
            # resolver fallback until the author explicitly retracts them.
            if current_id is not None and resolved.status != MetricComponentStatus.DISPUTED:
                connection.execute(
                    "UPDATE metric_observations SET active=0 WHERE observation_id=?",
                    (current_id,),
                )
            observation_id = stable_id(
                "observation",
                observation.book_id,
                observation.edition_id,
                observation.scope_type,
                observation.scope_id,
                observation.metric_id,
                observation.component_id,
                utc_now(),
            )
            value_numeric = numeric
            config_hash = current_config_hash
            connection.execute(
                """
                INSERT INTO metric_observations(
                    observation_id, book_id, edition_id, scope_type, scope_id, chapter_id,
                    effective_content_sha256, metric_id, component_id, value_json, value_numeric,
                    status, source_kind, confidence, analyzer_version, config_hash,
                    projection_hash, registry_hash, freshness_status, stale_reason,
                    reason, source_task_id, supersedes_observation_id, active, created_at, version
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 1
                )
                """,
                (
                    observation_id,
                    observation.book_id,
                    observation.edition_id,
                    observation.scope_type,
                    observation.scope_id,
                    observation.chapter_id,
                    observation.effective_content_sha256,
                    observation.metric_id,
                    observation.component_id,
                    _json_value(observation.value),
                    value_numeric,
                    status,
                    observation.source_kind.value,
                    observation.confidence,
                    observation.analyzer_version,
                    config_hash,
                    projection.sha256(),
                    self.registry.registry_hash,
                    "FRESH",
                    None,
                    observation.reason,
                    observation.source_task_id,
                    current_id,
                    utc_now(),
                ),
            )
            self._insert_evidence(connection, observation, observation_id)
            return observation_id

    def _insert_evidence(
        self, connection: sqlite3.Connection, observation: ObservationInput, observation_id: str
    ) -> None:
        for ordinal, raw_link in enumerate(observation.evidence_links):
            contribution = ContributionKind(
                str(raw_link.get("contribution_kind", "AUTHOR_EVIDENCE"))
            )
            exact_delta = raw_link.get("exact_delta")
            if contribution == ContributionKind.EXACT_DELTA and observation.source_kind not in (
                ObservationSourceKind.DETERMINISTIC,
                ObservationSourceKind.DERIVED,
            ):
                raise MetricValidationError("EXACT_DELTA 只能来自 DETERMINISTIC/DERIVED")
            if contribution != ContributionKind.EXACT_DELTA and exact_delta is not None:
                raise MetricValidationError("SEMANTIC_SUPPORT/AUTHOR_EVIDENCE 不得填写 exact_delta")
            segment_id = raw_link.get("segment_id")
            quote = str(raw_link.get("evidence_quote", ""))
            if segment_id is not None:
                segment = connection.execute(
                    "SELECT book_id, edition_id FROM chapter_segments "
                    "WHERE segment_id=? AND invalidated_at IS NULL",
                    (str(segment_id),),
                ).fetchone()
                if (
                    segment is None
                    or str(segment["book_id"]) != observation.book_id
                    or str(segment["edition_id"]) != observation.edition_id
                ):
                    raise MetricValidationError("segment 不属于当前 book/edition")
                if not segment_contains_quote(connection, str(segment_id), quote):
                    raise MetricValidationError("evidence_quote 不存在于指定 segment")
            if raw_link.get("source_span_id") is not None:
                source_span = connection.execute(
                    "SELECT book_id, edition_id, excerpt FROM source_spans WHERE span_id=?",
                    (str(raw_link["source_span_id"]),),
                ).fetchone()
                if (
                    source_span is None
                    or str(source_span["book_id"]) != observation.book_id
                    or str(source_span["edition_id"]) != observation.edition_id
                    or (quote and quote not in str(source_span["excerpt"]))
                ):
                    raise MetricValidationError("evidence_quote 不存在于指定 source span")
            if not quote and contribution != ContributionKind.STATE_EVIDENCE:
                raise MetricValidationError("段落证据必须提供 evidence_quote")
            link_id = stable_id("metric-link", observation_id, str(ordinal), quote)
            connection.execute(
                """
                INSERT INTO metric_evidence_links(
                    link_id, observation_id, segment_id, source_span_id, event_id,
                    contribution_kind, direction, strength, exact_delta, confidence,
                    evidence_quote, rationale, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    link_id,
                    observation_id,
                    segment_id,
                    raw_link.get("source_span_id"),
                    raw_link.get("event_id"),
                    contribution.value,
                    str(raw_link.get("direction", "SUPPORTS")),
                    raw_link.get("strength"),
                    exact_delta,
                    raw_link.get("confidence"),
                    quote,
                    str(raw_link.get("rationale", "")),
                    utc_now(),
                ),
            )

    def retract(
        self, observation_id: str, *, reason: str = "", retracted_by: str | None = None
    ) -> None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT observation_id, retracted_at FROM metric_observations "
                "WHERE observation_id=?",
                (observation_id,),
            ).fetchone()
            if row is None or row["retracted_at"] is not None:
                raise MetricValidationError("可撤回 observation 不存在")
            connection.execute(
                "UPDATE metric_observations SET active=0, retracted_at=?, "
                "retracted_by=?, retraction_reason=? "
                "WHERE observation_id=?",
                (utc_now(), retracted_by, reason or "retracted", observation_id),
            )

    def active(
        self, book_id: str, edition_id: str, scope_type: str, scope_id: str
    ) -> list[dict[str, Any]]:
        self.database.initialize()
        with self.database.connect() as connection:
            keys = connection.execute(
                "SELECT DISTINCT metric_id, component_id FROM metric_observations "
                "WHERE book_id=? AND edition_id=? AND scope_type=? AND scope_id=?",
                (book_id, edition_id, scope_type, scope_id),
            ).fetchall()
            result: list[dict[str, Any]] = []
            resolver = ObservationResolver(self.database, self.registry)
            for key in keys:
                resolved = resolver.resolve(
                    book_id,
                    edition_id,
                    scope_type,
                    scope_id,
                    str(key["metric_id"]),
                    str(key["component_id"]),
                )
                if resolved.effective_observation_id is not None:
                    row = connection.execute(
                        "SELECT * FROM metric_observations WHERE observation_id=?",
                        (resolved.effective_observation_id,),
                    ).fetchone()
                    if row is not None:
                        result.append(dict(row))
            return result


def _row_component(row: sqlite3.Row) -> MetricComponentValue:
    value = json.loads(str(row["value_json"]))
    return MetricComponentValue(
        metric_id=str(row["metric_id"]),
        component_id=str(row["component_id"]),
        value=value,
        status=MetricComponentStatus(str(row["status"])),
        source_kind=ObservationSourceKind(str(row["source_kind"])),
        confidence=None if row["confidence"] is None else float(row["confidence"]),
        reason=str(row["reason"] or ""),
        observation_id=str(row["observation_id"]),
    )


class MetricsAssembler:
    """Assemble frozen, provenance-aware inputs and persist a replayable run."""

    def __init__(
        self,
        database: Database,
        registry: MetricsRegistry | None = None,
        config_path: Path | None = None,
    ) -> None:
        self.database = database
        self.registry = registry or load_registry()
        self.settings = load_settings(config_path)

    def _anchor(
        self,
        connection: sqlite3.Connection,
        book_id: str,
        edition_id: str,
        scope_type: str,
        scope_id: str,
    ) -> tuple[int, str, str | None, int | None]:
        projection = projection_from_connection(connection, book_id, edition_id)
        content_hash: str | None = None
        ordinal: int | None = None
        chapters = edition_chapters(connection, book_id, edition_id)
        current_ordinal = max((int(chapter["ordinal"]) for chapter in chapters), default=0)
        if scope_type == "CHAPTER":
            for chapter in chapters:
                if str(chapter["chapter_id"]) == scope_id:
                    content_hash = str(chapter.get("content_sha256") or "")
                    ordinal = int(chapter["ordinal"])
                    break
            if ordinal is None:
                raise MetricValidationError(f"有效 edition 中不存在章节：{scope_id}")
        else:
            # Non-chapter scopes are anchored to the current effective edition
            # horizon, never to the scope identifier (for example promise_id).
            ordinal = current_ordinal
        return projection.through_event_seq, projection.sha256(), content_hash, ordinal

    def assemble(
        self,
        book_id: str,
        *,
        edition_id: str | None = None,
        scope_type: str = "CHAPTER",
        scope_id: str | None = None,
        requested_metric_ids: list[str] | None = None,
    ) -> MetricInputBundleV2:
        self.database.initialize()
        normalized_scope = str(scope_type).upper()
        matching_metric_ids = self.registry.metric_ids_for_scope(normalized_scope)
        requested = None if requested_metric_ids is None else list(requested_metric_ids)
        if requested is not None:
            for metric_id in requested:
                self.registry.validate_metric_scope(metric_id, normalized_scope)
        selected = resolve_edition_id(self.database, book_id, edition_id)
        with self.database.connect() as connection:
            chapters = edition_chapters(connection, book_id, selected)
            if scope_id is None:
                if normalized_scope != "CHAPTER" or not chapters:
                    raise MetricValidationError(f"{normalized_scope} Run 必须提供 scope_id")
                scope_id = str(chapters[-1]["chapter_id"])
            event_seq, projection_hash, content_hash, as_of_chapter = self._anchor(
                connection, book_id, selected, normalized_scope, scope_id
            )
            components: dict[str, dict[str, MetricComponentValue]] = {}
            evidence: dict[str, list[EvidenceSummary]] = {}
            resolver = ObservationResolver(self.database, self.registry)
            rows = connection.execute(
                "SELECT DISTINCT metric_id, component_id FROM metric_observations "
                "WHERE book_id=? AND edition_id=? AND scope_type=? AND scope_id=?",
                (book_id, selected, normalized_scope, scope_id),
            ).fetchall()
            allowed = set(requested if requested is not None else matching_metric_ids)
            for key in rows:
                metric_id = str(key["metric_id"])
                component_id = str(key["component_id"])
                if metric_id not in allowed:
                    continue
                resolved = resolver.resolve(
                    book_id,
                    selected,
                    normalized_scope,
                    scope_id,
                    metric_id,
                    component_id,
                )
                source = resolved.source_kind or ObservationSourceKind.UNKNOWN
                component_value = MetricComponentValue(
                    metric_id=metric_id,
                    component_id=component_id,
                    value=resolved.value
                    if resolved.status
                    not in (MetricComponentStatus.DISPUTED, MetricComponentStatus.STALE)
                    else None,
                    status=resolved.status,
                    source_kind=source,
                    confidence=resolved.confidence,
                    reason=resolved.selected_reason,
                    observation_id=resolved.effective_observation_id,
                    selected_reason=resolved.selected_reason,
                    freshness="STALE"
                    if resolved.status == MetricComponentStatus.STALE
                    else "FRESH",
                    stale_reason=resolved.stale_reason,
                )
                components.setdefault(metric_id, {})[component_id] = component_value
                if resolved.effective_observation_id:
                    links = connection.execute(
                        "SELECT * FROM metric_evidence_links WHERE observation_id=? "
                        "ORDER BY created_at, link_id",
                        (resolved.effective_observation_id,),
                    ).fetchall()
                    evidence.setdefault(metric_id, []).extend(
                        EvidenceSummary(
                            link_id=str(link["link_id"]),
                            component_id=component_id,
                            observation_id=resolved.effective_observation_id,
                            source_kind=source,
                            segment_id=None
                            if link["segment_id"] is None
                            else str(link["segment_id"]),
                            source_span_id=None
                            if link["source_span_id"] is None
                            else str(link["source_span_id"]),
                            event_id=None
                            if link["event_id"] is None
                            else str(link["event_id"]),
                            contribution_kind=ContributionKind(str(link["contribution_kind"])),
                            direction=EvidenceDirection(str(link["direction"])),
                            strength=None
                            if link["strength"] is None
                            else float(link["strength"]),
                            exact_delta=None
                            if link["exact_delta"] is None
                            else float(link["exact_delta"]),
                            confidence=None
                            if link["confidence"] is None
                            else float(link["confidence"]),
                            evidence_quote=str(link["evidence_quote"]),
                            rationale=str(link["rationale"] or ""),
                        )
                        for link in links
                    )
            # Derived evidence is read from the current edition, never guessed
            # by the semantic executor.  A rhythm snapshot is a diagnostic
            # object rather than a new literary score.
            rhythm = connection.execute(
                "SELECT snapshot_id, snapshot_json FROM rhythm_diagnostic_snapshots "
                "WHERE book_id=? AND edition_id=? ORDER BY as_of_chapter DESC, "
                "created_at DESC LIMIT 1",
                (book_id, selected),
            ).fetchone()
            if normalized_scope == "WINDOW" and rhythm is not None:
                components.setdefault("rhythm_diagnostics", {})["snapshot"] = MetricComponentValue(
                    metric_id="rhythm_diagnostics",
                    component_id="snapshot",
                    value={
                        "snapshot_id": str(rhythm["snapshot_id"]),
                        **json.loads(str(rhythm["snapshot_json"])),
                    },
                    status=MetricComponentStatus.AVAILABLE,
                    source_kind=ObservationSourceKind.DETERMINISTIC,
                    confidence=1.0,
                    reason="rhythm_diagnostic_snapshots",
                )
            if normalized_scope == "PROMISE":
                promise = connection.execute(
                    "SELECT * FROM promises "
                    "WHERE book_id=? AND edition_id=? AND promise_id=?",
                    (book_id, selected, scope_id),
                ).fetchone()
                if promise is not None:
                    current_ordinal = max(
                        (int(chapter["ordinal"]) for chapter in chapters), default=0
                    )
                    introduced = int(promise["introduced_ordinal"])
                    last_advanced = int(promise["last_advanced_ordinal"] or introduced)
                    last_reminded = int(promise["last_reminded_ordinal"] or introduced)
                    age = max(0, current_ordinal - introduced)
                    dormancy = max(0, current_ordinal - last_advanced)
                    promise_defaults = self.settings.rhythm.get("promise", {})
                    target_min_age = int(
                        promise["target_min_age"]
                        or promise_defaults.get("default_target_min_age", 3)
                    )
                    target_max_age = int(
                        promise["target_max_age"]
                        or promise_defaults.get("default_target_max_age", 12)
                    )
                    dormancy_target = int(
                        promise["dormancy_target"]
                        or promise_defaults.get("default_dormancy_target", 8)
                    )
                    readiness = float(promise["resolution_readiness"] or 0)
                    dependencies_ready = bool(promise["dependencies_ready"])
                    deferred = promise["author_deferred_until"]
                    if (
                        deferred is not None and int(deferred) > current_ordinal
                    ) or (not dependencies_ready and age / max(target_max_age, 1) < 1):
                        decision = "HOLD"
                    elif age > target_max_age:
                        decision = "OVERDUE"
                    elif age >= target_min_age and readiness >= 0.7:
                        decision = "RESOLVE"
                    elif dormancy / max(dormancy_target, 1) >= 1:
                        decision = "ADVANCE"
                    else:
                        decision = "HOLD"
                    derived = {
                        "importance": promise["importance"],
                        "reader_visibility": promise["reader_visibility"],
                        "promise_progress": promise["progress"],
                        "age": age,
                        "dormancy": dormancy,
                        "age_ratio": age / max(target_max_age, 1),
                        "dormancy_ratio": dormancy / max(dormancy_target, 1),
                        "introduced_ordinal": introduced,
                        "current_ordinal": current_ordinal,
                        "last_advanced_ordinal": last_advanced,
                        "last_reminded_ordinal": last_reminded,
                        "target_min_age": target_min_age,
                        "target_max_age": target_max_age,
                        "dormancy_target": dormancy_target,
                        "reminder_count": promise["reminder_count"],
                        "readiness": readiness,
                        "resolution_readiness": readiness,
                        "dependencies_ready": dependencies_ready,
                        "dependency_state": "READY" if dependencies_ready else "BLOCKED",
                        "author_deferred_until": deferred,
                        "decision": decision,
                        "evidence": [
                            f"Age={age} (current={current_ordinal}, introduced={introduced})",
                            f"Dormancy={dormancy} (last_advanced={last_advanced})",
                            f"TargetMaxAge={target_max_age}; action={decision}",
                        ],
                    }
                    for component_id, value in derived.items():
                        components.setdefault("narrative_debt", {})[component_id] = (
                            MetricComponentValue(
                                metric_id="narrative_debt",
                                component_id=component_id,
                                value=value,
                                status=MetricComponentStatus.AVAILABLE,
                                source_kind=ObservationSourceKind.DETERMINISTIC,
                                confidence=1.0,
                                reason="promises projection",
                            )
                        )
        return MetricInputBundleV2(
            book_id=book_id,
            edition_id=selected,
            scope_type=normalized_scope,
            scope_id=scope_id,
            as_of_chapter=as_of_chapter,
            as_of_event_seq=event_seq,
            projection_hash=projection_hash,
            effective_content_sha256=content_hash,
            registry_hash=self.registry.registry_hash,
            config_hash=sha256_bytes(json_dumps(self.settings.metrics).encode("utf-8")),
            requested_metric_ids=requested,
            components=components,
            evidence=evidence,
        )

    def _result(self, metric_id: str, bundle: MetricInputBundleV2) -> MetricResultV2:
        definition = self.registry.metric(metric_id)
        values = bundle.components.get(metric_id, {})
        missing: list[str] = []
        disputed_components: list[str] = []
        stale_components: list[str] = []
        disputed = False
        for component_id in definition.required_components:
            value = values.get(component_id)
            if value is None or value.status in (
                MetricComponentStatus.MISSING,
                MetricComponentStatus.STALE,
                MetricComponentStatus.INVALID,
                MetricComponentStatus.UNKNOWN,
            ):
                missing.append(component_id)
            if value is not None and value.status == MetricComponentStatus.STALE:
                stale_components.append(component_id)
            if value is not None and value.status == MetricComponentStatus.DISPUTED:
                disputed = True
                disputed_components.append(component_id)
        for component_id, value in values.items():
            if value.status == MetricComponentStatus.STALE and component_id not in stale_components:
                stale_components.append(component_id)
        available = [
            value for value in values.values() if value.status == MetricComponentStatus.AVAILABLE
        ]
        completeness = (
            (len(definition.required_components) - len(missing))
            / len(definition.required_components)
            if definition.required_components
            else 1.0
        )
        confidence = (
            sum(value.confidence or 0 for value in available) / len(available) if available else 0.0
        )
        semantic_values = [
            value
            for value in available
            if value.source_kind
            in (ObservationSourceKind.SEMANTIC_ESTIMATE, ObservationSourceKind.AUTHOR_INPUT,
                ObservationSourceKind.AUTHOR_OVERRIDE)
        ]
        semantic_confidence = (
            sum(value.confidence or 0 for value in semantic_values) / len(semantic_values)
            if semantic_values
            else 0.0
        )
        status: MetricRunStatus | MetricComponentStatus
        if disputed:
            status = MetricComponentStatus.DISPUTED
        elif missing:
            status = MetricRunStatus.INCOMPLETE
        else:
            status = MetricRunStatus.COMPLETE
        score: float | None = None
        interpretation = ""
        formula_contribution: dict[str, float | None] = {}
        action = "补齐缺失输入后重算" if missing else ""
        try:
            if not missing and not disputed:
                numeric: dict[str, float] = {}
                for key, item in values.items():
                    number = _numeric(item.value)
                    if number is not None:
                        numeric[key] = number
                config = self.settings.metrics
                if metric_id == "pressure":
                    computed = pressure(numeric, config["pressure"])
                elif metric_id == "progress":
                    computed = progress(numeric, config["progress"])
                elif metric_id == "payoff":
                    computed = payoff_score(
                        maturity=numeric["maturity"],
                        impact=numeric["impact"],
                        causality=numeric["causality"],
                        after_value=numeric["after_value"],
                        repetition_fatigue_score=numeric["repetition_fatigue"],
                        structural_fit=numeric["structural_fit"],
                        future_damage=numeric["future_damage"],
                        config=config["payoff"],
                    )
                elif metric_id == "risk_credibility":
                    computed = risk_credibility(numeric, config["risk_credibility"])
                elif metric_id == "legibility":
                    computed = legibility(numeric, config["legibility"])
                elif metric_id == "outcome_uncertainty":
                    computed = outcome_uncertainty(numeric, config["outcome_uncertainty"])
                elif metric_id == "agency":
                    agency_value = values["agency"].value
                    computed = agency(agency_value if isinstance(agency_value, dict) else numeric)
                elif metric_id == "resource_pressure":
                    score = resource_pressure(numeric, config["resource_pressure"])
                    computed = None
                elif metric_id == "repetition_fatigue":
                    history = values["history"].value
                    if not isinstance(history, list):
                        raise ValueError("history 必须是数组")
                    pairs = [
                        (float(item["distance"]), float(item["similarity"]))
                        for item in history
                        if isinstance(item, dict)
                    ]
                    computed = repetition_fatigue(pairs, config["repetition"])
                elif metric_id == "narrative_debt":
                    target_max_age = int(numeric["target_max_age"])
                    computed = narrative_debt(
                        importance=numeric["importance"],
                        reader_visibility=numeric["reader_visibility"],
                        promise_progress=numeric["promise_progress"],
                        age_chapters=int(numeric["age"]),
                        target_max_age=target_max_age,
                        reminder_count=int(numeric["reminder_count"]),
                        config=config["narrative_debt"],
                    )
                else:
                    computed = None
                if computed is not None:
                    score = computed.score
                    interpretation = computed.threshold_interpretation
                    action = computed.recommended_action
                    raw_inputs = getattr(computed, "inputs", {})
                    if isinstance(raw_inputs, dict):
                        formula_contribution = {
                            str(key): _numeric(value) for key, value in raw_inputs.items()
                        }
        except (KeyError, TypeError, ValueError):
            status = MetricComponentStatus.INVALID
            action = "输入无法通过公式校验"
        return MetricResultV2(
            metric_id=metric_id,
            status=status,
            score=score,
            completeness=completeness,
            confidence=confidence,
            missing_components=missing,
            disputed_components=disputed_components,
            stale_components=stale_components,
            components=values,
            formula_id=definition.formula_id,
            config_hash=bundle.config_hash,
            evidence_summary=bundle.evidence.get(metric_id, []),
            threshold_interpretation=interpretation,
            recommended_action=action,
            semantic_confidence=semantic_confidence,
            data_freshness="STALE" if stale_components else "FRESH",
            dispute_status="DISPUTED" if disputed_components else "NONE",
            formula_contribution=formula_contribution,
            created_at=utc_now(),
        )

    def run(
        self,
        bundle: MetricInputBundleV2 | str | None = None,
        scope_id: str | None = None,
        requested_metric_ids: list[str] | None = None,
        *,
        book_id: str | None = None,
        edition_id: str | None = None,
        scope_type: str | None = None,
    ) -> dict[str, Any]:
        """Run only registry metrics matching the requested scope.

        The bundle form remains the compatibility entry point.  The explicit
        scope form is useful to CLI/Web callers and guarantees that the same
        assembly path is used by both surfaces.
        """
        self.database.initialize()
        if not isinstance(bundle, MetricInputBundleV2):
            selected_scope = scope_type or (str(bundle) if bundle is not None else None)
            if selected_scope is None or book_id is None or scope_id is None:
                raise MetricValidationError(
                    "run 需要 MetricInputBundleV2，或同时提供 book_id/scope_type/scope_id"
                )
            bundle = self.assemble(
                book_id,
                edition_id=edition_id,
                scope_type=selected_scope,
                scope_id=scope_id,
                requested_metric_ids=requested_metric_ids,
            )
        elif requested_metric_ids is not None:
            for metric_id in requested_metric_ids:
                self.registry.validate_metric_scope(metric_id, bundle.scope_type)
            bundle = bundle.model_copy(update={"requested_metric_ids": requested_metric_ids})
        metric_ids = bundle.requested_metric_ids
        if metric_ids is None:
            metric_ids = self.registry.metric_ids_for_scope(bundle.scope_type)
        else:
            for metric_id in metric_ids:
                self.registry.validate_metric_scope(metric_id, bundle.scope_type)
        results = [self._result(metric_id, bundle) for metric_id in metric_ids]
        complete_ratio = (
            sum(result.completeness for result in results) / len(results) if results else 1.0
        )
        overall_status = (
            MetricRunStatus.COMPLETE
            if all(result.status == MetricRunStatus.COMPLETE for result in results)
            else MetricRunStatus.INCOMPLETE
        )
        run_id = stable_id(
            "metric-run", bundle.book_id, bundle.edition_id, bundle.input_bundle_hash, utc_now()
        )
        disputed_components = sorted(
            f"{result.metric_id}.{component}"
            for result in results
            for component in result.disputed_components
        )
        stale_components = sorted(
            f"{result.metric_id}.{component}"
            for result in results
            for component in result.stale_components
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO metric_runs(
                    run_id, book_id, edition_id, scope_type, scope_id, as_of_chapter,
                    as_of_event_seq, projection_hash, effective_content_sha256, registry_hash,
                    config_hash, status, completeness, confidence, input_bundle_hash,
                    created_at, version, requested_metric_ids_json,
                    disputed_components_json, stale_components_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    run_id,
                    bundle.book_id,
                    bundle.edition_id,
                    bundle.scope_type,
                    bundle.scope_id,
                    bundle.as_of_chapter,
                    bundle.as_of_event_seq,
                    bundle.projection_hash,
                    bundle.effective_content_sha256,
                    bundle.registry_hash,
                    bundle.config_hash,
                    overall_status.value,
                    complete_ratio,
                    sum(result.confidence for result in results) / len(results) if results else 0,
                    bundle.input_bundle_hash,
                    utc_now(),
                    json_dumps(metric_ids),
                    json_dumps(disputed_components),
                    json_dumps(stale_components),
                ),
            )
            for result in results:
                connection.execute(
                    """
                    INSERT INTO metric_run_results(
                        run_id, metric_id, status, score, lower_bound, upper_bound, band,
                        completeness, confidence, components_json, missing_components_json,
                        evidence_summary_json, threshold_interpretation, recommended_action,
                        formula_id, version, disputed_components_json, stale_components_json,
                        semantic_confidence, data_freshness, dispute_status,
                        formula_contribution_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        result.metric_id,
                        str(result.status),
                        result.score,
                        result.lower_bound,
                        result.upper_bound,
                        result.band,
                        result.completeness,
                        result.confidence,
                        json_dumps(
                            {
                                key: value.model_dump(mode="json")
                                for key, value in result.components.items()
                            }
                        ),
                        json_dumps(result.missing_components),
                        json_dumps(
                            [item.model_dump(mode="json") for item in result.evidence_summary]
                        ),
                        result.threshold_interpretation,
                        result.recommended_action,
                        result.formula_id,
                        json_dumps(result.disputed_components),
                        json_dumps(result.stale_components),
                        result.semantic_confidence,
                        result.data_freshness,
                        result.dispute_status,
                        json_dumps(result.formula_contribution),
                    ),
                )
        return {
            "run_id": run_id,
            "status": overall_status.value,
            "completeness": complete_ratio,
            "scope_type": bundle.scope_type,
            "scope_id": bundle.scope_id,
            "requested_metric_ids": metric_ids,
            "results": [result.model_dump(mode="json") for result in results],
            "bundle": bundle.model_dump(mode="json"),
        }

    def rebuild(
        self,
        book_id: str,
        *,
        edition_id: str | None = None,
        scope_type: str = "CHAPTER",
        scope_id: str | None = None,
        requested_metric_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.run(
            self.assemble(
                book_id,
                edition_id=edition_id,
                scope_type=scope_type,
                scope_id=scope_id,
                requested_metric_ids=requested_metric_ids,
            )
        )

    def latest(
        self, book_id: str, edition_id: str, scope_type: str, scope_id: str
    ) -> dict[str, Any] | None:
        self.database.initialize()
        with self.database.connect() as connection:
            run = connection.execute(
                "SELECT * FROM metric_runs WHERE book_id=? AND edition_id=? "
                "AND scope_type=? AND scope_id=? "
                "AND invalidated_at IS NULL ORDER BY created_at DESC LIMIT 1",
                (book_id, edition_id, scope_type, scope_id),
            ).fetchone()
            if run is None:
                return None
            results = connection.execute(
                "SELECT * FROM metric_run_results WHERE run_id=? ORDER BY metric_id",
                (str(run["run_id"]),),
            ).fetchall()
            return {"run": dict(run), "results": [dict(item) for item in results]}

    def invalidate_scope(
        self, book_id: str, edition_id: str, scope_type: str, scope_id: str
    ) -> None:
        self.database.initialize()
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE metric_runs SET status=?, invalidated_at=? WHERE book_id=? "
                "AND edition_id=? "
                "AND scope_type=? AND scope_id=? AND invalidated_at IS NULL",
                (
                    MetricRunStatus.INVALIDATED.value,
                    utc_now(),
                    book_id,
                    edition_id,
                    scope_type,
                    scope_id,
                ),
            )


class AuthorMetricInputService:
    def __init__(self, database: Database, registry: MetricsRegistry | None = None) -> None:
        self.database = database
        self.registry = registry or load_registry()

    def save(self, observation: ObservationInput) -> dict[str, Any]:
        if observation.source_kind not in (
            ObservationSourceKind.AUTHOR_INPUT,
            ObservationSourceKind.AUTHOR_OVERRIDE,
        ):
            raise MetricValidationError("作者输入只能使用 AUTHOR_INPUT 或 AUTHOR_OVERRIDE")
        assembler = MetricsAssembler(self.database, self.registry)
        selected = resolve_edition_id(self.database, observation.book_id, observation.edition_id)
        if selected != observation.edition_id:
            raise MetricConflictError("edition 已变化，请刷新后重试")
        observation_id = MetricObservationService(self.database, self.registry).append(observation)
        assembler.invalidate_scope(
            observation.book_id,
            observation.edition_id,
            observation.scope_type,
            observation.scope_id,
        )
        self._stale_planning(observation.book_id, observation.edition_id)
        result = assembler.rebuild(
            observation.book_id,
            edition_id=observation.edition_id,
            scope_type=observation.scope_type,
            scope_id=observation.scope_id,
        )
        result["observation_id"] = observation_id
        result["missing"] = {
            item["metric_id"]: item["missing_components"]
            for item in result["results"]
            if item["missing_components"]
        }
        return result

    def _stale_planning(self, book_id: str, edition_id: str) -> None:
        with self.database.connect() as connection:
            for table in ("candidate_plans", "chapter_contracts"):
                connection.execute(
                    f"UPDATE {table} SET status='STALE', stale_reason=? WHERE book_id=? "
                    "AND edition_id=? "
                    "AND status NOT IN ('STALE', 'ARCHIVED')",
                    ("metric observation changed; re-plan required", book_id, edition_id),
                )
            connection.execute(
                "UPDATE workflow_handoffs SET status='STALE', stale_at=?, "
                "error_message=? WHERE book_id=? AND edition_id=? "
                "AND status IN ('DRAFT', 'READY_FOR_CODEX')",
                (utc_now(), "metric observation changed; recreate handoff", book_id, edition_id),
            )
        from novel_authoring.planning.aggregates import invalidate_planning_aggregates

        invalidate_planning_aggregates(self.database, book_id, edition_id)

    def retract(
        self,
        observation_id: str,
        *,
        book_id: str,
        edition_id: str,
        scope_type: str,
        scope_id: str,
        reason: str = "作者撤回",
        expected_active_observation_id: str | None = None,
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            anchor = connection.execute(
                "SELECT book_id, edition_id, scope_type, scope_id FROM metric_observations "
                "WHERE observation_id=?",
                (observation_id,),
            ).fetchone()
        if anchor is None or any(
            str(anchor[field]) != expected
            for field, expected in (
                ("book_id", book_id),
                ("edition_id", edition_id),
                ("scope_type", scope_type),
                ("scope_id", scope_id),
            )
        ):
            raise MetricValidationError("observation 不属于当前 book/edition/scope")
        if expected_active_observation_id is not None:
            metric_id = self._observation_metric_id(observation_id)
            component_id = self._observation_component_id(observation_id)
            effective = ObservationResolver(self.database, self.registry).resolve(
                book_id,
                edition_id,
                scope_type,
                scope_id,
                metric_id,
                component_id,
            ).effective_observation_id
            if effective != expected_active_observation_id:
                raise MetricConflictError("active observation 已变化，请刷新后重试")
        MetricObservationService(self.database, self.registry).retract(
            observation_id, reason=reason, retracted_by="author"
        )
        assembler = MetricsAssembler(self.database, self.registry)
        assembler.invalidate_scope(book_id, edition_id, scope_type, scope_id)
        self._stale_planning(book_id, edition_id)
        return assembler.rebuild(
            book_id,
            edition_id=edition_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def _observation_metric_id(self, observation_id: str) -> str:
        value = self.database.scalar(
            "SELECT metric_id FROM metric_observations WHERE observation_id=?",
            (observation_id,),
        )
        if value is None:
            raise MetricValidationError("可撤回 observation 不存在")
        return str(value)

    def _observation_component_id(self, observation_id: str) -> str:
        value = self.database.scalar(
            "SELECT component_id FROM metric_observations WHERE observation_id=?",
            (observation_id,),
        )
        if value is None:
            raise MetricValidationError("可撤回 observation 不存在")
        return str(value)


def import_semantic_output(
    database: Database,
    output: MetricSemanticObservationsOutput,
    registry: MetricsRegistry | None = None,
) -> dict[str, Any]:
    selected_registry = registry or load_registry()
    if output.registry_hash != selected_registry.registry_hash:
        raise MetricValidationError("registry_hash 不匹配，拒绝导入")
    service = MetricObservationService(database, selected_registry)
    ids: list[str] = []
    for item in output.observations:
        links = [link.model_dump(mode="json") for link in item.evidence_links]
        observation = ObservationInput(
            book_id=output.book_id,
            edition_id=output.edition_id,
            scope_type="CHAPTER",
            scope_id=output.chapter_id,
            metric_id=item.metric_id,
            component_id=item.component_id,
            value=item.value,
            status=item.status,
            source_kind=ObservationSourceKind.SEMANTIC_ESTIMATE,
            confidence=item.confidence,
            reason=item.reason or item.unknown_reason or "",
            chapter_id=output.chapter_id,
            effective_content_sha256=output.content_sha256,
            source_task_id=output.task_id,
            analyzer_version=output.analyzer_version,
            evidence_links=links,
        )
        ids.append(service.append(observation))
    return {"task_id": output.task_id, "observation_ids": ids, "count": len(ids)}
