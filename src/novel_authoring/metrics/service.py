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
    expected_active_observation_id: str | None = None
    source_task_id: str | None = None
    analyzer_version: str | None = None
    evidence_links: list[dict[str, Any]] = Field(default_factory=list)


def _numeric(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _json_value(value: Any) -> str:
    return json_dumps(value)


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
            current = _active_observation_row(
                connection,
                observation.book_id,
                observation.edition_id,
                observation.scope_type,
                observation.scope_id,
                observation.metric_id,
                observation.component_id,
            )
            if observation.expected_active_observation_id is not None:
                actual = None if current is None else str(current["observation_id"])
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
            same_priority_conflict = False
            if current is not None and str(current["source_kind"]) == observation.source_kind.value:
                # Same-priority active values are intentionally retained as a
                # conflict instead of silently choosing one.
                existing_value = json.loads(str(current["value_json"]))
                if existing_value != observation.value and observation.source_kind in (
                    ObservationSourceKind.AUTHOR_INPUT,
                    ObservationSourceKind.AUTHOR_OVERRIDE,
                    ObservationSourceKind.SEMANTIC_ESTIMATE,
                ):
                    status = MetricComponentStatus.DISPUTED.value
                    same_priority_conflict = True
                else:
                    status = observation.status.value
            else:
                status = observation.status.value
            if current is not None and not same_priority_conflict:
                connection.execute(
                    "UPDATE metric_observations SET active=0, retracted_at=? "
                    "WHERE observation_id=? AND active=1",
                    (utc_now(), str(current["observation_id"])),
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
            config_hash = sha256_bytes(json_dumps(load_settings().metrics).encode("utf-8"))
            connection.execute(
                """
                INSERT INTO metric_observations(
                    observation_id, book_id, edition_id, scope_type, scope_id, chapter_id,
                    effective_content_sha256, metric_id, component_id, value_json, value_numeric,
                    status, source_kind, confidence, analyzer_version, config_hash, reason,
                    source_task_id, supersedes_observation_id, active, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 1)
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
                    observation.reason,
                    observation.source_task_id,
                    None
                    if current is None or same_priority_conflict
                    else str(current["observation_id"]),
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

    def retract(self, observation_id: str, *, reason: str = "") -> None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT observation_id FROM metric_observations "
                "WHERE observation_id=? AND active=1",
                (observation_id,),
            ).fetchone()
            if row is None:
                raise MetricValidationError("active observation 不存在")
            connection.execute(
                "UPDATE metric_observations SET active=0, retracted_at=?, reason=? "
                "WHERE observation_id=?",
                (utc_now(), reason or "retracted", observation_id),
            )

    def active(
        self, book_id: str, edition_id: str, scope_type: str, scope_id: str
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM metric_observations
                WHERE book_id=? AND edition_id=? AND scope_type=? AND scope_id=? AND active=1
                ORDER BY metric_id, component_id, created_at
                """,
                (book_id, edition_id, scope_type, scope_id),
            ).fetchall()
            return [dict(row) for row in rows]


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
        self, connection: sqlite3.Connection, book_id: str, edition_id: str, scope_id: str
    ) -> tuple[int, str, str | None, int | None]:
        projection = projection_from_connection(connection, book_id, edition_id)
        content_hash: str | None = None
        ordinal: int | None = None
        for chapter in edition_chapters(connection, book_id, edition_id):
            if str(chapter["chapter_id"]) == scope_id:
                content_hash = str(chapter.get("content_sha256") or "")
                ordinal = int(chapter["ordinal"])
                break
        return projection.through_event_seq, projection.sha256(), content_hash, ordinal

    def assemble(
        self,
        book_id: str,
        *,
        edition_id: str | None = None,
        scope_type: str = "CHAPTER",
        scope_id: str | None = None,
    ) -> MetricInputBundleV2:
        self.database.initialize()
        selected = resolve_edition_id(self.database, book_id, edition_id)
        with self.database.connect() as connection:
            chapters = edition_chapters(connection, book_id, selected)
            if scope_id is None:
                if not chapters:
                    raise MetricValidationError("没有可用章节，无法组装指标")
                scope_id = str(chapters[-1]["chapter_id"])
            event_seq, projection_hash, content_hash, as_of_chapter = self._anchor(
                connection, book_id, selected, scope_id
            )
            rows = connection.execute(
                """
                SELECT * FROM metric_observations
                WHERE book_id=? AND edition_id=? AND scope_type=? AND scope_id=? AND active=1
                ORDER BY metric_id, component_id, created_at
                """,
                (book_id, selected, scope_type, scope_id),
            ).fetchall()
            components: dict[str, dict[str, MetricComponentValue]] = {}
            evidence: dict[str, list[EvidenceSummary]] = {}
            for row in rows:
                value = _row_component(row)
                components.setdefault(value.metric_id, {})[value.component_id] = value
                links = connection.execute(
                    "SELECT * FROM metric_evidence_links WHERE observation_id=? "
                    "ORDER BY created_at, link_id",
                    (str(row["observation_id"]),),
                ).fetchall()
                evidence.setdefault(value.metric_id, []).extend(
                    EvidenceSummary(
                        link_id=str(link["link_id"]),
                        segment_id=None if link["segment_id"] is None else str(link["segment_id"]),
                        source_span_id=None
                        if link["source_span_id"] is None
                        else str(link["source_span_id"]),
                        event_id=None if link["event_id"] is None else str(link["event_id"]),
                        contribution_kind=ContributionKind(str(link["contribution_kind"])),
                        direction=EvidenceDirection(str(link["direction"])),
                        strength=None if link["strength"] is None else float(link["strength"]),
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
            if rhythm is not None:
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
            if scope_type == "PROMISE":
                promise = connection.execute(
                    "SELECT importance, reader_visibility, progress, introduced_ordinal, "
                    "last_reminded_ordinal, reminder_count, target_max_age, dormancy_target, "
                    "resolution_readiness, dependencies_ready FROM promises "
                    "WHERE book_id=? AND edition_id=? AND promise_id=?",
                    (book_id, selected, scope_id),
                ).fetchone()
                if promise is not None:
                    current_ordinal = as_of_chapter or int(promise["introduced_ordinal"])
                    age = max(0, current_ordinal - int(promise["introduced_ordinal"]))
                    derived = {
                        "importance": promise["importance"],
                        "reader_visibility": promise["reader_visibility"],
                        "promise_progress": promise["progress"],
                        "age": age,
                        "dormancy": age
                        - int(promise["last_reminded_ordinal"] or promise["introduced_ordinal"]),
                        "reminder_count": promise["reminder_count"],
                        "readiness": promise["resolution_readiness"],
                        "dependency_state": "READY" if promise["dependencies_ready"] else "BLOCKED",
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
            scope_type=scope_type,
            scope_id=scope_id,
            as_of_chapter=as_of_chapter,
            as_of_event_seq=event_seq,
            projection_hash=projection_hash,
            effective_content_sha256=content_hash,
            registry_hash=self.registry.registry_hash,
            config_hash=sha256_bytes(json_dumps(self.settings.metrics).encode("utf-8")),
            components=components,
            evidence=evidence,
        )

    def _result(self, metric_id: str, bundle: MetricInputBundleV2) -> MetricResultV2:
        definition = self.registry.metric(metric_id)
        values = bundle.components.get(metric_id, {})
        missing: list[str] = []
        disputed = False
        for component_id in definition.required_components:
            value = values.get(component_id)
            if value is None or value.status in (
                MetricComponentStatus.MISSING,
                MetricComponentStatus.STALE,
                MetricComponentStatus.INVALID,
            ):
                missing.append(component_id)
            if value is not None and value.status == MetricComponentStatus.DISPUTED:
                disputed = True
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
        status: MetricRunStatus | MetricComponentStatus
        if disputed:
            status = MetricComponentStatus.DISPUTED
        elif missing:
            status = MetricRunStatus.INCOMPLETE
        else:
            status = MetricRunStatus.COMPLETE
        score: float | None = None
        interpretation = ""
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
                    computed = narrative_debt(
                        importance=numeric["importance"],
                        reader_visibility=numeric["reader_visibility"],
                        promise_progress=numeric["promise_progress"],
                        age_chapters=int(numeric["age"]),
                        target_max_age=max(1, int(numeric["age"])),
                        reminder_count=int(numeric["reminder_count"]),
                        config=config["narrative_debt"],
                    )
                else:
                    computed = None
                if computed is not None:
                    score = computed.score
                    interpretation = computed.threshold_interpretation
                    action = computed.recommended_action
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
            components=values,
            formula_id=definition.formula_id,
            config_hash=bundle.config_hash,
            evidence_summary=bundle.evidence.get(metric_id, []),
            threshold_interpretation=interpretation,
            recommended_action=action,
            created_at=utc_now(),
        )

    def run(self, bundle: MetricInputBundleV2) -> dict[str, Any]:
        results = [self._result(metric_id, bundle) for metric_id in self.registry.metrics]
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
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO metric_runs(
                    run_id, book_id, edition_id, scope_type, scope_id, as_of_chapter,
                    as_of_event_seq, projection_hash, effective_content_sha256, registry_hash,
                    config_hash, status, completeness, confidence, input_bundle_hash,
                    created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
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
                ),
            )
            for result in results:
                connection.execute(
                    """
                    INSERT INTO metric_run_results(
                        run_id, metric_id, status, score, lower_bound, upper_bound, band,
                        completeness, confidence, components_json, missing_components_json,
                        evidence_summary_json, threshold_interpretation, recommended_action,
                        formula_id, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
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
                    ),
                )
        return {
            "run_id": run_id,
            "status": overall_status.value,
            "completeness": complete_ratio,
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
    ) -> dict[str, Any]:
        return self.run(
            self.assemble(book_id, edition_id=edition_id, scope_type=scope_type, scope_id=scope_id)
        )

    def latest(
        self, book_id: str, edition_id: str, scope_type: str, scope_id: str
    ) -> dict[str, Any] | None:
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

    def retract(
        self,
        observation_id: str,
        *,
        book_id: str,
        edition_id: str,
        scope_type: str,
        scope_id: str,
    ) -> dict[str, Any]:
        MetricObservationService(self.database, self.registry).retract(observation_id)
        assembler = MetricsAssembler(self.database, self.registry)
        assembler.invalidate_scope(book_id, edition_id, scope_type, scope_id)
        self._stale_planning(book_id, edition_id)
        return assembler.rebuild(
            book_id,
            edition_id=edition_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )


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
