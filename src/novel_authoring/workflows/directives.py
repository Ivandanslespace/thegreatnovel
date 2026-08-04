from __future__ import annotations

from novel_authoring.canon.events import EventStatus, EventStore
from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.db.database import Database
from novel_authoring.domain.models import InformationStatus
from novel_authoring.edition import resolve_edition_id
from novel_authoring.utils import stable_id, utc_now


class DirectiveWorkflowError(RuntimeError):
    pass


VALID_SCOPES = {"next_chapter", "persistent"}


def add_directive(
    database: Database,
    book_id: str,
    *,
    directive_type: str,
    content: str,
    scope: str = "next_chapter",
    priority: int = 100,
    source: str = "AUTHOR_CLI",
    edition_id: str | None = None,
) -> dict[str, object]:
    normalized_type = directive_type.strip().lower().replace(" ", "_")
    normalized_content = content.strip()
    if not normalized_type:
        raise DirectiveWorkflowError("directive_type 不得为空")
    if not normalized_content:
        raise DirectiveWorkflowError("content 不得为空")
    if scope not in VALID_SCOPES:
        raise DirectiveWorkflowError(f"scope 必须是 {sorted(VALID_SCOPES)}")
    if not 0 <= priority <= 1000:
        raise DirectiveWorkflowError("priority 必须在 0—1000")
    database.initialize()
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    directive_id = stable_id(
        "directive",
        book_id,
        selected_edition,
        normalized_type,
        normalized_content,
        scope,
        str(priority),
    )
    now = utc_now()
    with database.connect() as connection:
        book = connection.execute(
            "SELECT 1 FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
        if book is None:
            raise DirectiveWorkflowError(f"未知 book_id：{book_id}")
        connection.execute(
            """
            INSERT INTO author_directives(
                directive_id, book_id, edition_id, directive_type, content, mode,
                status, priority, source, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, directive_id) DO UPDATE SET
                status='ACTIVE', priority=excluded.priority,
                source=excluded.source, version=author_directives.version+1
            """,
            (
                directive_id,
                book_id,
                selected_edition,
                normalized_type,
                normalized_content,
                scope,
                priority,
                source,
                now,
            ),
        )
        event = EventStore(database).append_in_transaction(
            connection,
            book_id=book_id,
            edition_id=selected_edition,
            event_type="AUTHOR_DIRECTIVE_ADDED",
            aggregate_type="author_directive",
            aggregate_id=directive_id,
            payload={
                "directive_id": directive_id,
                "edition_id": selected_edition,
                "directive_type": normalized_type,
                "content": normalized_content,
                "scope": scope,
                "priority": priority,
            },
            source_kind=source,
            source_id=directive_id,
            status=EventStatus.COMMITTED,
            information_state=InformationStatus.AUTHOR_INTENT,
        )
    projection = rebuild_projection(database, book_id, edition_id=selected_edition, persist=True)
    return {
        "directive_id": directive_id,
        "book_id": book_id,
        "edition_id": selected_edition,
        "directive_type": normalized_type,
        "content": normalized_content,
        "scope": scope,
        "priority": priority,
        "status": "ACTIVE",
        "event_id": event.event_id,
        "through_event_seq": projection.through_event_seq,
    }
