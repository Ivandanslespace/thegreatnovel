from __future__ import annotations

import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from novel_authoring.db.database import Database
from novel_authoring.utils import json_dumps, sha256_bytes, sha256_file, utc_now

BASE_EDITION_ID = "base"
ACTIVATE_PHRASE = "启用改写版本"


class EditionStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class Edition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: str
    book_id: str
    parent_edition_id: str | None = None
    display_name: str
    status: EditionStatus
    base_event_seq: int
    base_projection_hash: str
    parent_base_event_seq: int = 0
    parent_base_projection_hash: str = ""
    source_manifest_sha256: str
    created_at: str
    activated_at: str | None = None
    archived_at: str | None = None
    version: int = 1


class EditionWorkflowError(RuntimeError):
    pass


def _source_manifest_hash(connection: sqlite3.Connection, book_id: str) -> str:
    row = connection.execute(
        "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
    ).fetchone()
    if row is None:
        raise EditionWorkflowError(f"未知 book_id：{book_id}")
    manifest_path = Path(str(row["workspace_root"])) / "source_manifest.json"
    if manifest_path.is_file():
        return sha256_file(manifest_path)
    rows = connection.execute(
        """
        SELECT relative_path, sha256, order_index FROM source_documents
        WHERE book_id=? AND status!='GENERATED_CANON'
        ORDER BY order_index, relative_path
        """,
        (book_id,),
    ).fetchall()
    return sha256_bytes(json_dumps([dict(item) for item in rows]).encode("utf-8"))


def _projection_hash(connection: sqlite3.Connection, book_id: str) -> tuple[int, str]:
    from novel_authoring.canon.projection import projection_from_connection

    projection = projection_from_connection(connection, book_id, edition_id=BASE_EDITION_ID)
    return projection.through_event_seq, projection.sha256()


def _row_to_edition(row: sqlite3.Row) -> Edition:
    return Edition(
        edition_id=str(row["edition_id"]),
        book_id=str(row["book_id"]),
        parent_edition_id=(
            None if row["parent_edition_id"] is None else str(row["parent_edition_id"])
        ),
        display_name=str(row["display_name"]),
        status=EditionStatus(str(row["status"])),
        base_event_seq=int(row["base_event_seq"]),
        base_projection_hash=str(row["base_projection_hash"]),
        parent_base_event_seq=int(row["parent_base_event_seq"] or row["base_event_seq"]),
        parent_base_projection_hash=str(
            row["parent_base_projection_hash"] or row["base_projection_hash"]
        ),
        source_manifest_sha256=str(row["source_manifest_sha256"]),
        created_at=str(row["created_at"]),
        activated_at=None if row["activated_at"] is None else str(row["activated_at"]),
        archived_at=None if row["archived_at"] is None else str(row["archived_at"]),
        version=int(row["version"]),
    )


def backfill_base_editions(connection: sqlite3.Connection) -> None:
    """为旧数据库补齐 base；可重复执行，且不改变既有事件。"""
    books = connection.execute(
        "SELECT book_id, title, active_edition_id FROM books ORDER BY book_id"
    ).fetchall()
    for book in books:
        book_id = str(book["book_id"])
        existing = connection.execute(
            "SELECT 1 FROM editions WHERE book_id=? AND edition_id=?",
            (book_id, BASE_EDITION_ID),
        ).fetchone()
        if existing is None:
            event_seq, projection_hash = _projection_hash(connection, book_id)
            now = utc_now()
            connection.execute(
                """
                INSERT INTO editions(
                    edition_id, book_id, parent_edition_id, display_name, status,
                    base_event_seq, base_projection_hash, source_manifest_sha256,
                    parent_base_event_seq, parent_base_projection_hash,
                    created_at, activated_at, version
                ) VALUES (?, ?, NULL, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    BASE_EDITION_ID,
                    book_id,
                    str(book["title"]),
                    event_seq,
                    projection_hash,
                    _source_manifest_hash(connection, book_id),
                    event_seq,
                    projection_hash,
                    now,
                    now,
                ),
            )
        if book["active_edition_id"] is None:
            connection.execute(
                "UPDATE books SET active_edition_id=? WHERE book_id=?",
                (BASE_EDITION_ID, book_id),
            )


def ensure_base_edition(database: Database, book_id: str) -> Edition:
    database.initialize()
    with database.connect() as connection:
        backfill_base_editions(connection)
        row = connection.execute(
            "SELECT * FROM editions WHERE book_id=? AND edition_id=?",
            (book_id, BASE_EDITION_ID),
        ).fetchone()
        if row is None:
            raise EditionWorkflowError(f"未知 book_id 或无法创建 base edition：{book_id}")
        return _row_to_edition(row)


def resolve_edition_id(database: Database, book_id: str, edition_id: str | None = None) -> str:
    ensure_base_edition(database, book_id)
    with database.connect() as connection:
        if edition_id is not None:
            row = connection.execute(
                "SELECT status FROM editions WHERE book_id=? AND edition_id=?",
                (book_id, edition_id),
            ).fetchone()
            if row is None:
                raise EditionWorkflowError(f"edition 不存在：{edition_id}")
            return edition_id
        active_id = connection.execute(
            "SELECT active_edition_id FROM books WHERE book_id=?", (book_id,)
        ).fetchone()[0]
        if active_id:
            active = connection.execute(
                """
                SELECT edition_id FROM editions
                WHERE book_id=? AND edition_id=? AND status='ACTIVE'
                """,
                (book_id, str(active_id)),
            ).fetchone()
            if active is not None:
                return str(active["edition_id"])
        row = connection.execute(
            """
            SELECT edition_id FROM editions
            WHERE book_id=? AND status='ACTIVE'
            ORDER BY CASE WHEN edition_id='base' THEN 1 ELSE 0 END, created_at DESC
            LIMIT 1
            """,
            (book_id,),
        ).fetchone()
        return BASE_EDITION_ID if row is None else str(row["edition_id"])


def get_edition(database: Database, book_id: str, edition_id: str) -> Edition:
    ensure_base_edition(database, book_id)
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM editions WHERE book_id=? AND edition_id=?",
            (book_id, edition_id),
        ).fetchone()
    if row is None:
        raise EditionWorkflowError(f"edition 不存在：{edition_id}")
    return _row_to_edition(row)


def list_editions(database: Database, book_id: str) -> list[Edition]:
    ensure_base_edition(database, book_id)
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM editions WHERE book_id=? ORDER BY created_at, edition_id",
            (book_id,),
        ).fetchall()
    return [_row_to_edition(row) for row in rows]


def create_edition(
    database: Database,
    book_id: str,
    edition_id: str,
    display_name: str,
    *,
    parent_edition_id: str | None = None,
) -> Edition:
    ensure_base_edition(database, book_id)
    parent_id = parent_edition_id or resolve_edition_id(database, book_id)
    if not edition_id or edition_id == BASE_EDITION_ID:
        raise EditionWorkflowError("derived edition_id 必须是非空且不能为 base")
    parent = get_edition(database, book_id, parent_id)
    if parent.status is EditionStatus.ARCHIVED:
        raise EditionWorkflowError("不能从 ARCHIVED edition 创建派生版本")
    with database.connect() as connection:
        if (
            connection.execute(
                "SELECT 1 FROM editions WHERE edition_id=?", (edition_id,)
            ).fetchone()
            is not None
        ):
            raise EditionWorkflowError(f"edition 已存在：{edition_id}")
        from novel_authoring.canon.projection import projection_from_connection

        projection = projection_from_connection(connection, book_id, edition_id=parent_id)
        now = utc_now()
        connection.execute(
            """
            INSERT INTO editions(
                edition_id, book_id, parent_edition_id, display_name, status,
                base_event_seq, base_projection_hash, source_manifest_sha256,
                parent_base_event_seq, parent_base_projection_hash,
                created_at, version
            ) VALUES (?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                edition_id,
                book_id,
                parent_id,
                display_name,
                projection.through_event_seq,
                projection.sha256(),
                _source_manifest_hash(connection, book_id),
                projection.through_event_seq,
                projection.sha256(),
                now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM editions WHERE edition_id=?", (edition_id,)
        ).fetchone()
    assert row is not None
    return _row_to_edition(row)


def activate_edition(
    database: Database,
    book_id: str,
    edition_id: str,
    *,
    confirmation: str,
) -> Edition:
    if confirmation != ACTIVATE_PHRASE:
        raise EditionWorkflowError(f"拒绝激活：必须逐字提供确认语“{ACTIVATE_PHRASE}”")
    ensure_base_edition(database, book_id)
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM editions WHERE book_id=? AND edition_id=?",
            (book_id, edition_id),
        ).fetchone()
        if row is None:
            raise EditionWorkflowError(f"edition 不存在：{edition_id}")
        if edition_id == BASE_EDITION_ID:
            target_status = EditionStatus.ACTIVE.value
        elif str(row["status"]) != EditionStatus.VALIDATED.value:
            raise EditionWorkflowError(f"edition 状态不可激活：{row['status']}")
        else:
            parent_id = row["parent_edition_id"]
            if parent_id is not None:
                from novel_authoring.canon.projection import projection_from_connection

                frozen_parent = projection_from_connection(
                    connection,
                    book_id,
                    edition_id=str(parent_id),
                    through_event_seq=int(
                        row["parent_base_event_seq"] or row["base_event_seq"]
                    ),
                )
                if frozen_parent.sha256() != str(
                    row["parent_base_projection_hash"] or row["base_projection_hash"]
                ):
                    raise EditionWorkflowError("edition 父版本锚点已漂移，禁止激活")
            if _source_manifest_hash(connection, book_id) != str(row["source_manifest_sha256"]):
                raise EditionWorkflowError("不可变源 manifest 已漂移，禁止激活")
            target_status = EditionStatus.ACTIVE.value
        now = utc_now()
        connection.execute(
            """
            UPDATE editions SET status='ARCHIVED', archived_at=?, version=version+1
            WHERE book_id=? AND status='ACTIVE' AND edition_id<>?
            """,
            (now, book_id, edition_id),
        )
        connection.execute(
            """
            UPDATE editions SET status=?, activated_at=?, archived_at=NULL,
                version=version+1 WHERE book_id=? AND edition_id=?
            """,
            (target_status, now, book_id, edition_id),
        )
        connection.execute(
            "UPDATE books SET active_edition_id=?, updated_at=?, version=version+1 WHERE book_id=?",
            (edition_id, now, book_id),
        )
        updated = connection.execute(
            "SELECT * FROM editions WHERE book_id=? AND edition_id=?",
            (book_id, edition_id),
        ).fetchone()
    assert updated is not None
    return _row_to_edition(updated)


def archive_edition(database: Database, book_id: str, edition_id: str) -> Edition:
    ensure_base_edition(database, book_id)
    if edition_id == BASE_EDITION_ID:
        raise EditionWorkflowError("base edition 永远存在且不能停用")
    now = utc_now()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM editions WHERE book_id=? AND edition_id=?",
            (book_id, edition_id),
        ).fetchone()
        if row is None:
            raise EditionWorkflowError(f"edition 不存在：{edition_id}")
        connection.execute(
            """
            UPDATE editions SET status='ARCHIVED', archived_at=?, version=version+1
            WHERE edition_id=?
            """,
            (now, edition_id),
        )
        from novel_authoring.canon.events import EventStatus, EventStore
        from novel_authoring.domain.models import InformationStatus

        EventStore(database).append_in_transaction(
            connection,
            book_id=book_id,
            edition_id=edition_id,
            event_type="EDITION_ARCHIVED",
            aggregate_type="edition",
            aggregate_id=edition_id,
            payload={"edition_id": edition_id, "archived_at": now},
            source_kind="AUTHOR_CONFIRMATION",
            status=EventStatus.COMMITTED,
            information_state=InformationStatus.AUTHOR_INTENT,
        )
        if str(row["status"]) == EditionStatus.ACTIVE.value:
            connection.execute(
                """
                UPDATE editions SET status='ACTIVE',
                    activated_at=COALESCE(activated_at, ?), archived_at=NULL
                WHERE book_id=? AND edition_id='base'
                """,
                (now, book_id),
            )
            connection.execute(
                "UPDATE books SET active_edition_id=?, updated_at=? WHERE book_id=?",
                (BASE_EDITION_ID, now, book_id),
            )
        updated = connection.execute(
            "SELECT * FROM editions WHERE book_id=? AND edition_id=?",
            (book_id, edition_id),
        ).fetchone()
    assert updated is not None
    return _row_to_edition(updated)


def edition_lineage_ids(connection: sqlite3.Connection, edition_id: str) -> list[str]:
    lineage: list[str] = []
    current: str | None = edition_id
    while current is not None:
        if current in lineage:
            raise EditionWorkflowError("edition parent 形成循环")
        lineage.append(current)
        row = connection.execute(
            "SELECT parent_edition_id FROM editions WHERE edition_id=?", (current,)
        ).fetchone()
        if row is None:
            raise EditionWorkflowError(f"edition 不存在：{current}")
        current = None if row["parent_edition_id"] is None else str(row["parent_edition_id"])
    return list(reversed(lineage))


def _edition_event_limits(
    connection: sqlite3.Connection, edition_id: str
) -> dict[str, int | None]:
    """Return the event horizon at which each lineage edition was frozen."""
    lineage = edition_lineage_ids(connection, edition_id)
    limits: dict[str, int | None] = {item: None for item in lineage}
    for index, lineage_edition in enumerate(lineage[:-1]):
        child = lineage[index + 1]
        row = connection.execute(
            "SELECT parent_base_event_seq, base_event_seq FROM editions WHERE edition_id=?",
            (child,),
        ).fetchone()
        if row is not None:
            limits[lineage_edition] = int(
                row["parent_base_event_seq"] or row["base_event_seq"] or 0
            )
    return limits


def edition_workspace(database: Database, book_id: str, edition_id: str) -> Path:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    if row is None:
        raise EditionWorkflowError(f"未知 book_id：{book_id}")
    root = Path(str(row["workspace_root"]))
    if edition_id == BASE_EDITION_ID:
        return root
    path = root / "editions" / edition_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def edition_chapters(
    connection: sqlite3.Connection, book_id: str, edition_id: str
) -> list[dict[str, Any]]:
    """返回指定版本的章节视图；variant 替换原章，未改章节仍引用原文。"""
    lineage = edition_lineage_ids(connection, edition_id)
    event_limits = _edition_event_limits(connection, edition_id)
    rows = connection.execute(
        """
        SELECT c.*, d.status AS document_status, d.relative_path
        FROM chapters c JOIN source_documents d ON d.document_id=c.document_id
        WHERE c.book_id=? AND c.edition_id='base' AND d.status!='GENERATED_CANON'
        ORDER BY c.ordinal, c.created_at, c.chapter_id
        """,
        (book_id,),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        variant = None
        # A child edition inherits an active variant from its frozen parent;
        # the nearest variant wins if the child later replaces that chapter.
        for lineage_edition in reversed(lineage):
            variant = connection.execute(
                """
                SELECT variant_id, title, replacement_content,
                       replacement_content_sha256, base_source_span_id,
                       revision_commit_id, committed_event_seq
                FROM chapter_variants
                WHERE book_id=? AND edition_id=? AND base_chapter_id=? AND active=1
                  AND (
                      ? IS NULL OR committed_event_seq IS NULL
                      OR committed_event_seq <= ?
                  )
                """,
                (
                    book_id,
                    lineage_edition,
                    str(row["chapter_id"]),
                    event_limits[lineage_edition],
                    event_limits[lineage_edition],
                ),
            ).fetchone()
            if variant is not None:
                break
        if variant is not None:
            item["variant_id"] = str(variant["variant_id"])
            item["title"] = str(variant["title"])
            item["raw_heading"] = str(variant["title"])
            item["content"] = str(variant["replacement_content"])
            item["content_sha256"] = str(variant["replacement_content_sha256"])
            variant_span = connection.execute(
                """
                SELECT span_id FROM source_spans
                WHERE book_id=? AND chapter_id=? AND variant_id=?
                ORDER BY created_at DESC, span_id DESC LIMIT 1
                """,
                (book_id, str(row["chapter_id"]), str(variant["variant_id"])),
            ).fetchone()
            item["source_span_id"] = (
                str(variant_span["span_id"])
                if variant_span is not None
                else str(variant["base_source_span_id"])
            )
            item["document_status"] = "REVISION_VARIANT"
            item["revision_commit_id"] = str(variant["revision_commit_id"] or "")
        else:
            span = connection.execute(
                """
                SELECT span_id FROM source_spans
                WHERE chapter_id=? AND kind='chapter'
                ORDER BY span_id LIMIT 1
                """,
                (str(row["chapter_id"]),),
            ).fetchone()
            item["source_span_id"] = None if span is None else str(span["span_id"])
        item["edition_id"] = edition_id
        result.append(item)

    generated: list[sqlite3.Row] = []
    placeholders = ",".join("?" for _ in lineage)
    generated = connection.execute(
        f"""
        SELECT c.*, d.status AS document_status, d.relative_path,
               (SELECT span_id FROM source_spans s WHERE s.chapter_id=c.chapter_id
                ORDER BY s.span_id LIMIT 1) AS source_span_id
        FROM chapters c JOIN source_documents d ON d.document_id=c.document_id
        LEFT JOIN canon_commits cc
          ON cc.chapter_id=c.chapter_id AND cc.edition_id=c.edition_id
        WHERE c.book_id=? AND c.edition_id IN ({placeholders}) AND d.status='GENERATED_CANON'
          AND (
              cc.event_end_seq IS NULL
              OR cc.event_end_seq <= CASE c.edition_id
                  WHEN 'base' THEN COALESCE(?, cc.event_end_seq)
                  ELSE COALESCE((
                      SELECT parent_base_event_seq FROM editions child
                      WHERE child.parent_edition_id=c.edition_id
                        AND child.edition_id=?
                  ), cc.event_end_seq)
              END
          )
        ORDER BY c.ordinal, c.created_at, c.chapter_id
        """,
        (
            book_id,
            *lineage,
            event_limits.get("base"),
            edition_id,
        ),
    ).fetchall()
    result.extend({**dict(row), "edition_id": edition_id} for row in generated)
    result.sort(
        key=lambda item: (
            int(item["ordinal"]),
            str(item.get("created_at", "")),
            str(item["chapter_id"]),
        )
    )
    return result


def current_base_anchor(connection: sqlite3.Connection, book_id: str) -> tuple[int, str]:
    """读取当前 base 投影，供创建 campaign/edition 时冻结父版本锚点。"""
    from novel_authoring.canon.projection import projection_from_connection

    projection = projection_from_connection(connection, book_id, edition_id=BASE_EDITION_ID)
    return projection.through_event_seq, projection.sha256()
