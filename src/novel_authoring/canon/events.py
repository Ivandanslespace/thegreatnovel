from __future__ import annotations

import hashlib
import json
import sqlite3
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from novel_authoring.db.database import Database
from novel_authoring.domain.models import InformationStatus
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now


class EventStatus(StrEnum):
    PENDING = "PENDING"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"


class EventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_seq: int
    event_id: str
    book_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    source_kind: str
    source_id: str | None
    status: EventStatus
    information_state: InformationStatus
    payload_sha256: str
    prev_event_hash: str
    event_hash: str
    canon_commit_id: str | None
    created_at: str
    version: int


def _event_header(
    *,
    event_seq: int,
    event_id: str,
    book_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    source_kind: str,
    source_id: str | None,
    status: str,
    information_state: str,
    canon_commit_id: str | None,
    created_at: str,
    version: int,
) -> dict[str, Any]:
    return {
        "event_seq": event_seq,
        "event_id": event_id,
        "book_id": book_id,
        "event_type": event_type,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "source_kind": source_kind,
        "source_id": source_id,
        "status": status,
        "information_state": information_state,
        "canon_commit_id": canon_commit_id,
        "created_at": created_at,
        "version": version,
    }


def calculate_event_hash(
    prev_event_hash: str, header: dict[str, Any], payload_json: str
) -> str:
    material = prev_event_hash + json_dumps(header) + payload_json
    return hashlib.sha256(material.encode()).hexdigest()


class EventStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def append(
        self,
        *,
        book_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        source_kind: str,
        source_id: str | None = None,
        status: EventStatus = EventStatus.PENDING,
        information_state: InformationStatus = InformationStatus.INFERENCE,
        canon_commit_id: str | None = None,
    ) -> EventRecord:
        with self.database.connect() as connection:
            return self.append_in_transaction(
                connection,
                book_id=book_id,
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
                source_kind=source_kind,
                source_id=source_id,
                status=status,
                information_state=information_state,
                canon_commit_id=canon_commit_id,
            )

    def append_in_transaction(
        self,
        connection: sqlite3.Connection,
        *,
        book_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        source_kind: str,
        source_id: str | None = None,
        status: EventStatus = EventStatus.PENDING,
        information_state: InformationStatus = InformationStatus.INFERENCE,
        canon_commit_id: str | None = None,
    ) -> EventRecord:
        previous = connection.execute(
            """
            SELECT event_seq, event_hash FROM events
            WHERE book_id=? ORDER BY event_seq DESC LIMIT 1
            """,
            (book_id,),
        ).fetchone()
        previous_hash = "" if previous is None else str(previous["event_hash"])
        next_sequence = 1 if previous is None else int(previous["event_seq"]) + 1
        payload_json = json_dumps(payload)
        payload_hash = sha256_bytes(payload_json.encode())
        created_at = utc_now()
        event_id = stable_id(
            "event", book_id, str(next_sequence), event_type, aggregate_id, payload_hash
        )
        header = _event_header(
            event_seq=next_sequence,
            event_id=event_id,
            book_id=book_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            source_kind=source_kind,
            source_id=source_id,
            status=status.value,
            information_state=information_state.value,
            canon_commit_id=canon_commit_id,
            created_at=created_at,
            version=1,
        )
        event_hash = calculate_event_hash(previous_hash, header, payload_json)
        cursor = connection.execute(
            """
            INSERT INTO events(
                event_id, book_id, event_type, aggregate_type, aggregate_id,
                payload_json, source_kind, source_id, status, created_at, version,
                information_state, payload_sha256, prev_event_hash, event_hash,
                canon_commit_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                book_id,
                event_type,
                aggregate_type,
                aggregate_id,
                payload_json,
                source_kind,
                source_id,
                status.value,
                created_at,
                information_state.value,
                payload_hash,
                previous_hash,
                event_hash,
                canon_commit_id,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite 未返回事件序列")
        actual_sequence = int(cursor.lastrowid)
        if actual_sequence != next_sequence:
            raise RuntimeError(
                f"事件序列不连续：预期 {next_sequence}，实际 {actual_sequence}"
            )
        return EventRecord(
            event_seq=actual_sequence,
            event_id=event_id,
            book_id=book_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            source_kind=source_kind,
            source_id=source_id,
            status=status,
            information_state=information_state,
            payload_sha256=payload_hash,
            prev_event_hash=previous_hash,
            event_hash=event_hash,
            canon_commit_id=canon_commit_id,
            created_at=created_at,
            version=1,
        )


def row_to_event(row: sqlite3.Row) -> EventRecord:
    return EventRecord(
        event_seq=int(row["event_seq"]),
        event_id=str(row["event_id"]),
        book_id=str(row["book_id"]),
        event_type=str(row["event_type"]),
        aggregate_type=str(row["aggregate_type"]),
        aggregate_id=str(row["aggregate_id"]),
        payload=json.loads(str(row["payload_json"])),
        source_kind=str(row["source_kind"]),
        source_id=None if row["source_id"] is None else str(row["source_id"]),
        status=EventStatus(str(row["status"])),
        information_state=InformationStatus(str(row["information_state"])),
        payload_sha256=str(row["payload_sha256"]),
        prev_event_hash=str(row["prev_event_hash"]),
        event_hash=str(row["event_hash"]),
        canon_commit_id=(
            None if row["canon_commit_id"] is None else str(row["canon_commit_id"])
        ),
        created_at=str(row["created_at"]),
        version=int(row["version"]),
    )


def event_header(record: EventRecord) -> dict[str, Any]:
    return _event_header(
        event_seq=record.event_seq,
        event_id=record.event_id,
        book_id=record.book_id,
        event_type=record.event_type,
        aggregate_type=record.aggregate_type,
        aggregate_id=record.aggregate_id,
        source_kind=record.source_kind,
        source_id=record.source_id,
        status=record.status.value,
        information_state=record.information_state.value,
        canon_commit_id=record.canon_commit_id,
        created_at=record.created_at,
        version=record.version,
    )
