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
    edition_id: str = "base"
    through_event_seq: int = 0
    facts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    timeline: dict[str, dict[str, Any]] = Field(default_factory=dict)
    entities: dict[str, dict[str, Any]] = Field(default_factory=dict)
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
    "ENTITY_CONFIRMED": ("entities", "entity_id"),
    "ENTITY_OVERLAY_SET": ("entities", "entity_id"),
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
    """Validate the book-wide append-only chain, including legacy v1 rows."""
    previous_hash = ""
    previous_sequence = 0
    for event in events:
        if event.event_seq != previous_sequence + 1:
            raise EventIntegrityError(f"事件序列断裂：{previous_sequence} → {event.event_seq}")
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
    value["_edition_id"] = event.edition_id
    collection[identifier] = value


def _selected_events(
    connection: sqlite3.Connection,
    all_events: list[EventRecord],
    book_id: str,
    edition_id: str,
    through_event_seq: int | None,
) -> list[EventRecord]:
    """Return parent snapshot plus the target edition overlay."""
    if edition_id == "base":
        return [
            event
            for event in all_events
            if event.edition_id == "base"
            and (through_event_seq is None or event.event_seq <= through_event_seq)
        ]
    row = connection.execute(
        """
        SELECT parent_edition_id, base_event_seq
        FROM editions WHERE book_id=? AND edition_id=?
        """,
        (book_id, edition_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"未知 edition_id：{edition_id}")
    base_seq = int(row["base_event_seq"])
    limit = through_event_seq
    parent_id = str(row["parent_edition_id"])
    parent_events = _selected_events(
        connection, all_events, book_id, parent_id, min(base_seq, limit) if limit else base_seq
    )
    overlay = [
        event
        for event in all_events
        if event.edition_id == edition_id
        and event.event_seq > base_seq
        and (limit is None or event.event_seq <= limit)
    ]
    return sorted([*parent_events, *overlay], key=lambda event: event.event_seq)


def _all_events(connection: sqlite3.Connection, book_id: str) -> list[EventRecord]:
    rows = connection.execute(
        "SELECT * FROM events WHERE book_id=? ORDER BY event_seq", (book_id,)
    ).fetchall()
    events = [row_to_event(row) for row in rows]
    _validate_event_chain(events)
    return events


def rebuild_projection(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    persist: bool = True,
    through_event_seq: int | None = None,
) -> CanonProjection:
    database.initialize()
    from novel_authoring.edition import ensure_base_edition, resolve_edition_id

    ensure_base_edition(database, book_id)
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        projection = projection_from_connection(
            connection,
            book_id,
            edition_id=selected_edition,
            through_event_seq=through_event_seq,
        )
        if persist:
            persist_projection_in_transaction(connection, projection)
    return projection


def projection_from_connection(
    connection: sqlite3.Connection,
    book_id: str,
    edition_id: str = "base",
    through_event_seq: int | None = None,
) -> CanonProjection:
    events = _all_events(connection, book_id)
    selected = _selected_events(connection, events, book_id, edition_id, through_event_seq)
    projection = CanonProjection(book_id=book_id, edition_id=edition_id)
    for event in selected:
        apply_event(projection, event)
    return projection


def persist_projection_in_transaction(
    connection: sqlite3.Connection, projection: CanonProjection
) -> None:
    state_json = projection.canonical_json()
    if projection.edition_id == "base":
        connection.execute(
            """
            INSERT INTO projection_metadata(
                book_id, edition_id, through_event_seq, state_sha256, updated_at, state_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(book_id, edition_id) DO UPDATE SET
                through_event_seq=excluded.through_event_seq,
                state_sha256=excluded.state_sha256, updated_at=excluded.updated_at,
                state_json=excluded.state_json
            """,
            (
                projection.book_id,
                projection.edition_id,
                projection.through_event_seq,
                projection.sha256(),
                utc_now(),
                state_json,
            ),
        )
        return
    connection.execute(
        """
        INSERT INTO edition_projection_metadata(
            book_id, edition_id, through_event_seq, state_sha256, updated_at, state_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(book_id, edition_id) DO UPDATE SET
            through_event_seq=excluded.through_event_seq,
            state_sha256=excluded.state_sha256,
            updated_at=excluded.updated_at,
            state_json=excluded.state_json
        """,
        (
            projection.book_id,
            projection.edition_id,
            projection.through_event_seq,
            projection.sha256(),
            utc_now(),
            state_json,
        ),
    )


def load_projection(
    database: Database, book_id: str, edition_id: str | None = None
) -> CanonProjection:
    database.initialize()
    from novel_authoring.edition import ensure_base_edition, resolve_edition_id

    ensure_base_edition(database, book_id)
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        if selected_edition == "base":
            row = connection.execute(
                "SELECT state_json FROM projection_metadata WHERE book_id=?",
                (book_id,),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT state_json FROM edition_projection_metadata
                WHERE book_id=? AND edition_id=?
                """,
                (book_id, selected_edition),
            ).fetchone()
    if row is None:
        return rebuild_projection(database, book_id, edition_id=selected_edition, persist=True)
    projection = CanonProjection.model_validate_json(str(row["state_json"]))
    if projection.edition_id != selected_edition:
        projection.edition_id = selected_edition
    return projection


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
