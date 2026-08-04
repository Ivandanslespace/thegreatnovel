from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.metrics.registry import load_registry
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now


class PlanningMetricBundle(BaseModel):
    """Frozen references used by plan-next; it is not a new literary score."""

    model_config = ConfigDict(extra="forbid")

    book_id: str
    edition_id: str
    edition_state_run_id: str | None = None
    recent_chapter_run_ids: list[str] = Field(default_factory=list)
    window_run_ids: list[str] = Field(default_factory=list)
    promise_run_ids: list[str] = Field(default_factory=list)
    thread_run_ids: list[str] = Field(default_factory=list)
    metric_run_ids: list[str] = Field(default_factory=list)
    author_policy: dict[str, Any] = Field(default_factory=dict)
    registry_hash: str
    config_hash: str
    projection_hash: str
    rhythm_snapshot_id: str | None = None
    rhythm_snapshot_hash: str | None = None

    @property
    def bundle_hash(self) -> str:
        payload = {
            "book_id": self.book_id,
            "edition_id": self.edition_id,
            "edition_state_run_id": self.edition_state_run_id,
            "recent_chapter_run_ids": self.recent_chapter_run_ids,
            "window_run_ids": self.window_run_ids,
            "promise_run_ids": self.promise_run_ids,
            "thread_run_ids": self.thread_run_ids,
            "metric_run_ids": self.metric_run_ids,
            "author_policy": self.author_policy,
            "registry_hash": self.registry_hash,
            "config_hash": self.config_hash,
            "projection_hash": self.projection_hash,
            "rhythm_snapshot_id": self.rhythm_snapshot_id,
            "rhythm_snapshot_hash": self.rhythm_snapshot_hash,
        }
        return sha256_bytes(json_dumps(payload).encode("utf-8"))


class PlanningAggregate(PlanningMetricBundle):
    aggregate_id: str
    status: str = "ACTIVE"
    stale_reason: str | None = None
    created_at: str
    invalidated_at: str | None = None


def _latest_run_ids(
    connection: sqlite3.Connection,
    book_id: str,
    edition_id: str,
    scope_type: str,
    *,
    limit: int | None = None,
) -> list[str]:
    sql = (
        "SELECT run_id FROM metric_runs WHERE book_id=? AND edition_id=? "
        "AND scope_type=? AND invalidated_at IS NULL ORDER BY created_at DESC, run_id DESC"
    )
    params: list[object] = [book_id, edition_id, scope_type]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return [str(row["run_id"]) for row in connection.execute(sql, tuple(params)).fetchall()]


def _validate_run_references(
    connection: sqlite3.Connection,
    book_id: str,
    edition_id: str,
    references: dict[str, list[str]],
) -> None:
    expected_scopes = {
        "edition_state_run_id": "EDITION_STATE",
        "recent_chapter_run_ids": "CHAPTER",
        "window_run_ids": "WINDOW",
        "promise_run_ids": "PROMISE",
        "thread_run_ids": "THREAD",
    }
    for field, scope in expected_scopes.items():
        run_ids = references.get(field, [])
        if isinstance(run_ids, str):
            run_ids = [run_ids]
        for run_id in run_ids:
            row = connection.execute(
                "SELECT book_id, edition_id, scope_type FROM metric_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Planning Aggregate 引用了不存在的 Metric Run：{run_id}")
            if (
                str(row["book_id"]) != book_id
                or str(row["edition_id"]) != edition_id
                or str(row["scope_type"]) != scope
            ):
                raise ValueError(
                    f"Metric Run {run_id} 与 Planning Aggregate 的 {scope} scope 不匹配"
                )


def build_planning_aggregate(
    database: Database,
    book_id: str,
    *,
    edition_id: str = "base",
    edition_state_run_id: str | None = None,
    recent_chapter_run_ids: list[str] | None = None,
    window_run_ids: list[str] | None = None,
    promise_run_ids: list[str] | None = None,
    thread_run_ids: list[str] | None = None,
    author_policy: dict[str, Any] | None = None,
    rhythm_snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Persist a stable, reference-only planning aggregate."""
    database.initialize()
    registry_hash = load_registry().registry_hash
    config_hash = sha256_bytes(json_dumps(load_settings().metrics).encode("utf-8"))
    with database.connect() as connection:
        projection = projection_from_connection(connection, book_id, edition_id)
        if edition_state_run_id is None:
            state = _latest_run_ids(connection, book_id, edition_id, "EDITION_STATE", limit=1)
            edition_state_run_id = state[0] if state else None
        chapters = (
            recent_chapter_run_ids
            if recent_chapter_run_ids is not None
            else _latest_run_ids(connection, book_id, edition_id, "CHAPTER", limit=5)
        )
        windows = (
            window_run_ids
            if window_run_ids is not None
            else _latest_run_ids(connection, book_id, edition_id, "WINDOW", limit=3)
        )
        promises = (
            promise_run_ids
            if promise_run_ids is not None
            else _latest_run_ids(connection, book_id, edition_id, "PROMISE")
        )
        threads = (
            thread_run_ids
            if thread_run_ids is not None
            else _latest_run_ids(connection, book_id, edition_id, "THREAD")
        )
        _validate_run_references(
            connection,
            book_id,
            edition_id,
            {
                "edition_state_run_id": (
                    [] if edition_state_run_id is None else [edition_state_run_id]
                ),
                "recent_chapter_run_ids": list(chapters),
                "window_run_ids": list(windows),
                "promise_run_ids": list(promises),
                "thread_run_ids": list(threads),
            },
        )
        snapshot_hash: str | None = None
        if rhythm_snapshot_id is None:
            snapshot = connection.execute(
                "SELECT snapshot_id, snapshot_json FROM rhythm_diagnostic_snapshots "
                "WHERE book_id=? AND edition_id=? ORDER BY as_of_chapter DESC, "
                "created_at DESC LIMIT 1",
                (book_id, edition_id),
            ).fetchone()
            if snapshot is not None:
                rhythm_snapshot_id = str(snapshot["snapshot_id"])
                snapshot_hash = sha256_bytes(str(snapshot["snapshot_json"]).encode("utf-8"))
        elif rhythm_snapshot_id:
            snapshot = connection.execute(
                "SELECT snapshot_json FROM rhythm_diagnostic_snapshots WHERE snapshot_id=? "
                "AND book_id=? AND edition_id=?",
                (rhythm_snapshot_id, book_id, edition_id),
            ).fetchone()
            if snapshot is not None:
                snapshot_hash = sha256_bytes(str(snapshot["snapshot_json"]).encode("utf-8"))

    all_run_ids: list[str] = []
    for run_id in (
        [edition_state_run_id] if edition_state_run_id else [],
        list(chapters),
        list(windows),
        list(promises),
        list(threads),
    ):
        for item in run_id:
            if item not in all_run_ids:
                all_run_ids.append(item)
    bundle = PlanningMetricBundle(
        book_id=book_id,
        edition_id=edition_id,
        edition_state_run_id=edition_state_run_id,
        recent_chapter_run_ids=list(chapters),
        window_run_ids=list(windows),
        promise_run_ids=list(promises),
        thread_run_ids=list(threads),
        metric_run_ids=all_run_ids,
        author_policy=dict(author_policy or {}),
        registry_hash=registry_hash,
        config_hash=config_hash,
        projection_hash=projection.sha256(),
        rhythm_snapshot_id=rhythm_snapshot_id,
        rhythm_snapshot_hash=snapshot_hash,
    )
    aggregate_id = stable_id("planning-aggregate", book_id, edition_id, bundle.bundle_hash)
    created_at = utc_now()
    aggregate = PlanningAggregate(
        aggregate_id=aggregate_id,
        **bundle.model_dump(mode="python"),
        created_at=created_at,
    )
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO planning_aggregates(
                aggregate_id, book_id, edition_id, edition_state_run_id,
                recent_chapter_run_ids_json, window_run_ids_json, promise_run_ids_json,
                thread_run_ids_json, metric_run_ids_json, author_policy_json,
                registry_hash, config_hash, projection_hash, rhythm_snapshot_id,
                rhythm_snapshot_hash, bundle_hash, status, stale_reason, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(aggregate_id) DO UPDATE SET status='ACTIVE', invalidated_at=NULL
            """,
            (
                aggregate.aggregate_id,
                aggregate.book_id,
                aggregate.edition_id,
                aggregate.edition_state_run_id,
                json_dumps(aggregate.recent_chapter_run_ids),
                json_dumps(aggregate.window_run_ids),
                json_dumps(aggregate.promise_run_ids),
                json_dumps(aggregate.thread_run_ids),
                json_dumps(aggregate.metric_run_ids),
                json_dumps(aggregate.author_policy),
                aggregate.registry_hash,
                aggregate.config_hash,
                aggregate.projection_hash,
                aggregate.rhythm_snapshot_id,
                aggregate.rhythm_snapshot_hash,
                aggregate.bundle_hash,
                aggregate.status,
                aggregate.stale_reason,
                aggregate.created_at,
            ),
        )
    return aggregate.model_dump(mode="json") | {"bundle_hash": aggregate.bundle_hash}


def invalidate_planning_aggregates(database: Database, book_id: str, edition_id: str) -> None:
    with database.connect() as connection:
        connection.execute(
            "UPDATE planning_aggregates SET status='STALE', stale_reason=?, invalidated_at=? "
            "WHERE book_id=? AND edition_id=? AND status='ACTIVE'",
            (
                "metric observation or projection changed; re-plan required",
                utc_now(),
                book_id,
                edition_id,
            ),
        )
