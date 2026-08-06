from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.db.database import Database
from novel_authoring.domain.models import MetricResult
from novel_authoring.metrics.formulas import (
    agency,
    legibility,
    narrative_debt,
    outcome_uncertainty,
    payoff_score,
    pressure,
    progress,
    repetition_fatigue,
    risk_credibility,
)
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now


class NarrativeDebtInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    importance: float
    reader_visibility: float
    promise_progress: float
    age_chapters: int
    target_max_age: int
    reminder_count: int


class PayoffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maturity: float
    impact: float
    causality: float
    after_value: float
    repetition_fatigue: float
    structural_fit: float
    future_damage: float


class RepetitionHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance: float = Field(ge=0)
    similarity: float = Field(ge=0, le=1)


class MetricInputBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pressure: dict[str, float]
    narrative_debt: NarrativeDebtInput
    progress: dict[str, float]
    payoff: PayoffInput
    repetition_history: list[RepetitionHistoryInput]
    risk_credibility: dict[str, float]
    agency: dict[str, float] | None = None
    legibility: dict[str, float] | None = None
    outcome_uncertainty: dict[str, float] | None = None
    evidence: dict[str, list[dict[str, Any] | str]] = Field(default_factory=dict)


def diagnose_bundle(
    bundle: MetricInputBundle, metrics_config: dict[str, Any]
) -> list[MetricResult]:
    debt = bundle.narrative_debt
    payoff = bundle.payoff
    results = [
        pressure(bundle.pressure, metrics_config["pressure"]),
        narrative_debt(
            importance=debt.importance,
            reader_visibility=debt.reader_visibility,
            promise_progress=debt.promise_progress,
            age_chapters=debt.age_chapters,
            target_max_age=debt.target_max_age,
            reminder_count=debt.reminder_count,
            config=metrics_config["narrative_debt"],
        ),
        progress(bundle.progress, metrics_config["progress"]),
        payoff_score(
            maturity=payoff.maturity,
            impact=payoff.impact,
            causality=payoff.causality,
            after_value=payoff.after_value,
            repetition_fatigue_score=payoff.repetition_fatigue,
            structural_fit=payoff.structural_fit,
            future_damage=payoff.future_damage,
            config=metrics_config["payoff"],
        ),
        repetition_fatigue(
            [(item.distance, item.similarity) for item in bundle.repetition_history],
            metrics_config["repetition"],
        ),
        risk_credibility(bundle.risk_credibility, metrics_config["risk_credibility"]),
    ]
    if bundle.agency is not None:
        results.append(agency(bundle.agency))
    if bundle.legibility is not None:
        results.append(legibility(bundle.legibility, metrics_config["legibility"]))
    if bundle.outcome_uncertainty is not None:
        results.append(
            outcome_uncertainty(
                bundle.outcome_uncertainty,
                metrics_config["outcome_uncertainty"],
            )
        )
    for result in results:
        result.evidence.extend(bundle.evidence.get(result.metric, []))
    return results


def persist_results(
    database: Database,
    book_id: str,
    results: list[MetricResult],
    metrics_config: dict[str, Any],
    *,
    edition_id: str = "base",
) -> list[str]:
    config_json = json_dumps(metrics_config)
    config_hash = sha256_bytes(config_json.encode())
    with database.connect() as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(event_seq), 0) FROM events WHERE book_id=? AND edition_id=?",
            (book_id, edition_id),
        ).fetchone()
        as_of_seq = int(row[0])
        result_ids: list[str] = []
        for result in results:
            result_id = stable_id(
                "metric", book_id, edition_id, str(as_of_seq), result.metric, config_hash
            )
            connection.execute(
                """
                INSERT INTO metric_results(
                    result_id, book_id, as_of_event_seq, metric_name, score,
                    inputs_json, evidence_json, threshold_interpretation,
                    recommended_action, config_hash, formula_id, created_at, edition_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, as_of_event_seq, metric_name, config_hash)
                DO UPDATE SET
                    score=excluded.score,
                    inputs_json=excluded.inputs_json,
                    evidence_json=excluded.evidence_json,
                    threshold_interpretation=excluded.threshold_interpretation,
                    recommended_action=excluded.recommended_action
                """,
                (
                    result_id,
                    book_id,
                    as_of_seq,
                    result.metric,
                    result.score,
                    json_dumps(result.inputs),
                    json_dumps(result.evidence),
                    result.threshold_interpretation,
                    result.recommended_action,
                    config_hash,
                    "constitution-v2",
                    utc_now(),
                    edition_id,
                ),
            )
            result_ids.append(result_id)
    return result_ids


def load_metric_bundle(path: Path) -> MetricInputBundle:
    return MetricInputBundle.model_validate_json(path.read_text(encoding="utf-8"))
