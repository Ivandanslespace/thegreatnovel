from __future__ import annotations

from pathlib import Path

import pytest

from novel_authoring.canon.events import EventStatus, EventStore
from novel_authoring.canon.projection import (
    EventIntegrityError,
    rebuild_projection,
    validate_information_transition,
)
from novel_authoring.db.database import Database
from novel_authoring.domain.models import InformationStatus
from novel_authoring.utils import utc_now


def make_database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "workspace" / "test-book" / "state.sqlite3")
    database.initialize()
    with database.connect() as connection:
        now = utc_now()
        connection.execute(
            """
            INSERT INTO books(
                book_id, title, mode, source_root, workspace_root, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "test-book",
                "测试小说",
                "faithful_continuation",
                str(tmp_path / "book"),
                str(tmp_path / "workspace" / "test-book"),
                now,
                now,
            ),
        )
    return database


def test_six_information_states_are_explicit() -> None:
    assert {state.value for state in InformationStatus} == {
        "CANON",
        "AUTHOR_INTENT",
        "APPROVED_OUTLINE",
        "INFERENCE",
        "CANDIDATE",
        "PROSE_ONLY",
    }


@pytest.mark.parametrize(
    "old",
    [
        InformationStatus.INFERENCE,
        InformationStatus.CANDIDATE,
        InformationStatus.PROSE_ONLY,
    ],
)
def test_quarantined_state_cannot_silently_become_canon(old: InformationStatus) -> None:
    with pytest.raises(ValueError, match="禁止静默升级"):
        validate_information_transition(old, InformationStatus.CANON)

    validate_information_transition(
        old,
        InformationStatus.CANON,
        explicit_author_approval=True,
    )


def test_only_committed_canon_events_enter_projection(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    store = EventStore(database)
    canon = store.append(
        book_id="test-book",
        event_type="FACT_ASSERTED",
        aggregate_type="fact",
        aggregate_id="fact-source",
        payload={"fact_id": "fact-source", "statement": "钥匙来自原文"},
        source_kind="SOURCE_SPAN",
        source_id="span-1",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
        canon_commit_id="SOURCE_IMPORT",
    )
    store.append(
        book_id="test-book",
        event_type="FACT_ASSERTED",
        aggregate_type="fact",
        aggregate_id="fact-inference",
        payload={"fact_id": "fact-inference", "statement": "人物也许在撒谎"},
        source_kind="AGENT_OUTPUT",
        source_id="task-1",
        status=EventStatus.PENDING,
        information_state=InformationStatus.INFERENCE,
    )
    store.append(
        book_id="test-book",
        event_type="FACT_ASSERTED",
        aggregate_type="fact",
        aggregate_id="fact-author-intent",
        payload={"fact_id": "fact-author-intent", "statement": "以后打开红门"},
        source_kind="AUTHOR_DIRECTIVE",
        source_id="directive-1",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.AUTHOR_INTENT,
    )

    projection = rebuild_projection(database, "test-book")

    assert list(projection.facts) == ["fact-source"]
    assert projection.facts["fact-source"]["_event_id"] == canon.event_id
    assert projection.facts["fact-source"]["_source_id"] == "span-1"
    assert projection.through_event_seq == 3


def test_event_hash_chain_detects_tampering(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    store = EventStore(database)
    event = store.append(
        book_id="test-book",
        event_type="RESOURCE_SET",
        aggregate_type="resource",
        aggregate_id="coal",
        payload={"resource_id": "coal", "quantity": 2},
        source_kind="SOURCE_SPAN",
        source_id="span-2",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
        canon_commit_id="SOURCE_IMPORT",
    )
    with database.connect() as connection:
        connection.execute(
            "UPDATE events SET payload_json='{}' WHERE event_id=?", (event.event_id,)
        )

    with pytest.raises(EventIntegrityError, match="payload 哈希"):
        rebuild_projection(database, "test-book")


def test_explicit_fact_supersession_replays_without_old_fact(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    store = EventStore(database)
    store.append(
        book_id="test-book",
        event_type="FACT_ASSERTED",
        aggregate_type="fact",
        aggregate_id="fact-old",
        payload={"fact_id": "fact-old", "predicate": "door", "object": "closed"},
        source_kind="SOURCE_SPAN",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
    )
    store.append(
        book_id="test-book",
        event_type="FACT_ASSERTED",
        aggregate_type="fact",
        aggregate_id="fact-new",
        payload={
            "fact_id": "fact-new",
            "predicate": "door",
            "object": "open",
            "supersedes_fact_id": "fact-old",
        },
        source_kind="AUTHOR_APPROVED_REVISION",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
    )

    projection = rebuild_projection(database, "test-book", persist=False)
    assert "fact-old" not in projection.facts
    assert projection.facts["fact-new"]["object"] == "open"
