from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.canon.events import (
    EventRecord,
    EventStatus,
    calculate_event_hash,
    event_header,
    row_to_event,
)
from novel_authoring.db.database import Database
from novel_authoring.domain.models import InformationStatus
from novel_authoring.utils import json_dumps, sha256_bytes, utc_now


class EventIntegrityError(RuntimeError):
    pass


class CanonProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    book_id: str
    through_event_seq: int = 0
    facts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    timeline: dict[str, dict[str, Any]] = Field(default_factory=dict)
    character_states: dict[str, dict[str, Any]] = Field(default_factory=dict)
    knowledge: dict[str, dict[str, Any]] = Field(default_factory=dict)
    relationships: dict[str, dict[str, Any]] = Field(default_factory=dict)
    resources: dict[str, dict[str, Any]] = Field(default_factory=dict)
    capabilities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    threads: dict[str, dict[str, Any]] = Field(default_factory=dict)
    promises: dict[str, dict[str, Any]] = Field(default_factory=dict)
    payoffs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    repetition: dict[str, dict[str, Any]] = Field(default_factory=dict)
    style_profiles: dict[str, dict[str, Any]] = Field(default_factory=dict)
    committed_chapters: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def canonical_json(self) -> str:
        return json_dumps(self.model_dump(mode="json"))

    def sha256(self) -> str:
        return sha256_bytes(self.canonical_json().encode())


EVENT_TARGETS: dict[str, tuple[str, str]] = {
    "FACT_ASSERTED": ("facts", "fact_id"),
    "TIMELINE_ENTRY_SET": ("timeline", "timeline_id"),
    "CHARACTER_STATE_SET": ("character_states", "state_id"),
    "KNOWLEDGE_EDGE_SET": ("knowledge", "edge_id"),
    "RELATIONSHIP_SET": ("relationships", "relationship_id"),
    "RESOURCE_SET": ("resources", "resource_id"),
    "CAPABILITY_SET": ("capabilities", "capability_id"),
    "THREAD_SET": ("threads", "thread_id"),
    "PROMISE_SET": ("promises", "promise_id"),
    "PAYOFF_RECORDED": ("payoffs", "payoff_id"),
    "REPETITION_TAGGED": ("repetition", "tag_id"),
    "STYLE_PROFILE_SET": ("style_profiles", "profile_id"),
    "CANON_CHAPTER_COMMITTED": ("committed_chapters", "chapter_id"),
}


def _validate_event_chain(events: list[EventRecord]) -> None:
    previous_hash = ""
    previous_sequence = 0
    for event in events:
        if event.event_seq != previous_sequence + 1:
            raise EventIntegrityError(
                f"事件序列断裂：{previous_sequence} → {event.event_seq}"
            )
        payload_json = json_dumps(event.payload)
        payload_hash = sha256_bytes(payload_json.encode())
        if payload_hash != event.payload_sha256:
            raise EventIntegrityError(f"事件 payload 哈希不一致：{event.event_id}")
        if event.prev_event_hash != previous_hash:
            raise EventIntegrityError(f"事件前序哈希不一致：{event.event_id}")
        expected_hash = calculate_event_hash(previous_hash, event_header(event), payload_json)
        if expected_hash != event.event_hash:
            raise EventIntegrityError(f"事件哈希不一致：{event.event_id}")
        previous_hash = event.event_hash
        previous_sequence = event.event_seq


def apply_event(projection: CanonProjection, event: EventRecord) -> None:
    projection.through_event_seq = event.event_seq
    if event.status is not EventStatus.COMMITTED:
        return
    if event.information_state is not InformationStatus.CANON:
        return
    target = EVENT_TARGETS.get(event.event_type)
    if target is None:
        return
    if event.event_type == "FACT_ASSERTED" and event.payload.get("supersedes_fact_id"):
        projection.facts.pop(str(event.payload["supersedes_fact_id"]), None)
    collection_name, identifier_key = target
    identifier = str(event.payload.get(identifier_key) or event.aggregate_id)
    collection = getattr(projection, collection_name)
    value = dict(event.payload)
    value["_event_id"] = event.event_id
    value["_event_seq"] = event.event_seq
    value["_source_kind"] = event.source_kind
    value["_source_id"] = event.source_id
    collection[identifier] = value


def rebuild_projection(
    database: Database, book_id: str, *, persist: bool = True
) -> CanonProjection:
    database.initialize()
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM events WHERE book_id=? ORDER BY event_seq", (book_id,)
        ).fetchall()
    events = [row_to_event(row) for row in rows]
    _validate_event_chain(events)
    projection = CanonProjection(book_id=book_id)
    for event in events:
        apply_event(projection, event)
    if persist:
        state_json = projection.canonical_json()
        with database.connect() as connection:
            connection.execute(
                """
                INSERT INTO projection_metadata(
                    book_id, through_event_seq, state_sha256, updated_at, state_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    through_event_seq=excluded.through_event_seq,
                    state_sha256=excluded.state_sha256,
                    updated_at=excluded.updated_at,
                    state_json=excluded.state_json
                """,
                (
                    book_id,
                    projection.through_event_seq,
                    projection.sha256(),
                    utc_now(),
                    state_json,
                ),
            )
    return projection


def projection_from_connection(
    connection: sqlite3.Connection, book_id: str
) -> CanonProjection:
    rows = connection.execute(
        "SELECT * FROM events WHERE book_id=? ORDER BY event_seq", (book_id,)
    ).fetchall()
    events = [row_to_event(row) for row in rows]
    _validate_event_chain(events)
    projection = CanonProjection(book_id=book_id)
    for event in events:
        apply_event(projection, event)
    return projection


def persist_projection_in_transaction(
    connection: sqlite3.Connection, projection: CanonProjection
) -> None:
    connection.execute(
        """
        INSERT INTO projection_metadata(
            book_id, through_event_seq, state_sha256, updated_at, state_json
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(book_id) DO UPDATE SET
            through_event_seq=excluded.through_event_seq,
            state_sha256=excluded.state_sha256,
            updated_at=excluded.updated_at,
            state_json=excluded.state_json
        """,
        (
            projection.book_id,
            projection.through_event_seq,
            projection.sha256(),
            utc_now(),
            projection.canonical_json(),
        ),
    )


def load_projection(database: Database, book_id: str) -> CanonProjection:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT state_json FROM projection_metadata WHERE book_id=?", (book_id,)
        ).fetchone()
    if row is None:
        return rebuild_projection(database, book_id)
    return CanonProjection.model_validate_json(str(row["state_json"]))


def validate_information_transition(
    old: InformationStatus,
    new: InformationStatus,
    *,
    explicit_author_approval: bool = False,
    explicit_source_fact: bool = False,
) -> None:
    quarantined = {
        InformationStatus.INFERENCE,
        InformationStatus.CANDIDATE,
        InformationStatus.PROSE_ONLY,
    }
    if (
        old in quarantined
        and new is InformationStatus.CANON
        and not (explicit_author_approval or explicit_source_fact)
    ):
        raise ValueError(f"禁止静默升级 {old.value} → CANON")
