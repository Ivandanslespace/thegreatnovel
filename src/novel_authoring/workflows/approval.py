from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from novel_authoring.canon.events import EventStatus, EventStore
from novel_authoring.canon.materialize import MaterializationError, materialize_change
from novel_authoring.canon.projection import (
    persist_projection_in_transaction,
    projection_from_connection,
)
from novel_authoring.contracts.draft import DraftOutput, DraftStateChange
from novel_authoring.db.database import Database
from novel_authoring.domain.models import (
    DraftStatus,
    InformationStatus,
    NarrativeFunction,
)
from novel_authoring.edition import edition_workspace, resolve_edition_id
from novel_authoring.ingest.service import verify_sources
from novel_authoring.planning.models import ChapterContract
from novel_authoring.utils import json_dumps, sha256_bytes, sha256_file, stable_id, utc_now
from novel_authoring.validation.service import ValidationWorkflowError, validate_draft

APPROVAL_PHRASE = "批准写入正史"


class ApprovalWorkflowError(RuntimeError):
    pass


STATE_EVENT_TYPES: dict[str, tuple[str, str, str]] = {
    "fact": ("FACT_ASSERTED", "fact", "fact_id"),
    "timeline": ("TIMELINE_ENTRY_SET", "timeline", "timeline_id"),
    "character_state": ("CHARACTER_STATE_SET", "character_state", "state_id"),
    "knowledge": ("KNOWLEDGE_EDGE_SET", "knowledge", "edge_id"),
    "relationship": ("RELATIONSHIP_SET", "relationship", "relationship_id"),
    "resource": ("RESOURCE_SET", "resource", "resource_id"),
    "capability": ("CAPABILITY_SET", "capability", "capability_id"),
    "thread": ("THREAD_SET", "thread", "thread_id"),
    "promise": ("PROMISE_SET", "promise", "promise_id"),
    "payoff": ("PAYOFF_RECORDED", "payoff", "payoff_id"),
    "repetition": ("REPETITION_TAGGED", "repetition", "tag_id"),
    "style": ("STYLE_PROFILE_SET", "style", "profile_id"),
}


def _load_approval_rows(
    database: Database, book_id: str, draft_id: str, edition_id: str = "base"
) -> tuple[Any, DraftOutput, ChapterContract]:
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT d.*, c.contract_json, c.target_chapter_ordinal
            FROM drafts d JOIN chapter_contracts c ON c.contract_id=d.contract_id
            WHERE d.book_id=? AND d.draft_id=? AND d.edition_id=?
            """,
            (book_id, draft_id, edition_id),
        ).fetchone()
    if row is None:
        raise ApprovalWorkflowError(f"草稿不存在：{draft_id}")
    try:
        draft = DraftOutput.model_validate_json(str(row["output_json"]))
        contract = ChapterContract.model_validate_json(str(row["contract_json"]))
    except ValidationError as exc:
        raise ApprovalWorkflowError(f"草稿或合同记录无效：{exc}") from exc
    return row, draft, contract


def approval_preview(
    database: Database,
    book_id: str,
    draft_id: str,
    *,
    edition_id: str | None = None,
) -> dict[str, object]:
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    row, draft, contract = _load_approval_rows(database, book_id, draft_id, selected_edition)
    major = contract.primary_function is NarrativeFunction.MAJOR_PAYOFF or any(
        bool(change.payload.get("major_event"))
        for change in draft.state_changes
        if change.kind == "payoff"
    )
    return {
        "draft_id": draft_id,
        "edition_id": selected_edition,
        "current_status": str(row["status"]),
        "target_status": DraftStatus.CANON_COMMITTED.value,
        "chapter": contract.chapter,
        "chapter_title": draft.chapter_title,
        "contract_id": contract.contract_id,
        "state_changes": [
            {"kind": change.kind, "record_id": change.record_id} for change in draft.state_changes
        ],
        "will_create_aftershock_obligations": 4 if major else 0,
        "will_create_snapshot": True,
        "required_confirmation": APPROVAL_PHRASE,
    }


def _aftershock_changes(
    *,
    book_id: str,
    draft_id: str,
    thread_id: str,
    ordinal: int,
) -> list[DraftStateChange]:
    obligations = (
        ("awareness", "核心人物明确意识到重大变化", 0, 1),
        ("behavior", "行为方式因重大变化而改变", 1, 3),
        ("external_feedback", "关系、组织、市场或敌人作出反馈", 2, 5),
        ("higher_bottleneck", "新的高阶瓶颈或责任显现", 3, 8),
    )
    changes: list[DraftStateChange] = []
    for obligation_type, statement, due_min, due_max in obligations:
        promise_id = stable_id("aftershock", book_id, draft_id, obligation_type, str(ordinal))
        changes.append(
            DraftStateChange(
                kind="promise",
                record_id=promise_id,
                payload={
                    "promise_id": promise_id,
                    "thread_id": thread_id,
                    "statement": statement,
                    "importance": 1.0,
                    "reader_visibility": 0.9,
                    "progress": 0.0,
                    "introduced_ordinal": ordinal,
                    "target_min_age": due_min,
                    "target_max_age": due_max,
                    "obligation_type": obligation_type,
                    "aftershock": True,
                    "source_draft_id": draft_id,
                },
                evidence_quotes=[statement],
            )
        )
    return changes


def _append_change(
    store: EventStore,
    connection: Any,
    *,
    book_id: str,
    draft_id: str,
    commit_id: str,
    change: DraftStateChange,
    source_span_id: str,
    chapter_id: str,
    ordinal: int,
    edition_id: str = "base",
) -> int:
    event_type, aggregate_type, identifier_key = STATE_EVENT_TYPES[change.kind]
    payload = dict(change.payload)
    payload.setdefault(identifier_key, change.record_id)
    payload.setdefault("source_span_id", source_span_id)
    payload.setdefault("source_draft_id", draft_id)
    committed_change = change.model_copy(update={"payload": payload})
    event = store.append_in_transaction(
        connection,
        book_id=book_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=change.record_id,
        payload=payload,
        source_kind="AUTHOR_APPROVED_DRAFT",
        source_id=draft_id,
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
        canon_commit_id=commit_id,
        edition_id=edition_id,
    )
    materialize_change(
        connection,
        book_id=book_id,
        change=committed_change,
        source_span_id=source_span_id,
        event_id=event.event_id,
        event_seq=event.event_seq,
        chapter_id=chapter_id,
        ordinal=ordinal,
        edition_id=edition_id,
    )
    return event.event_seq


def approve_draft(
    database: Database,
    book_id: str,
    draft_id: str,
    *,
    confirmation: str,
    edition_id: str | None = None,
) -> dict[str, object]:
    if confirmation != APPROVAL_PHRASE:
        raise ApprovalWorkflowError(f"拒绝提交：必须逐字提供确认语“{APPROVAL_PHRASE}”")
    database.initialize()
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    try:
        validation = validate_draft(database, book_id, draft_id, edition_id=selected_edition)
    except ValidationWorkflowError as exc:
        raise ApprovalWorkflowError(str(exc)) from exc
    if not validation.passed:
        failed = [report.validator for report in validation.reports if not report.passed]
        raise ApprovalWorkflowError(f"十项校验未全部通过：{failed}")
    row, draft, contract = _load_approval_rows(database, book_id, draft_id, selected_edition)
    if row["status"] != DraftStatus.VALIDATED.value:
        raise ApprovalWorkflowError(f"草稿尚未处于 VALIDATED：{row['status']}")
    workspace = edition_workspace(database, book_id, selected_edition)
    source_root = workspace.parent if selected_edition == "base" else workspace.parents[2]
    source_report = verify_sources(book_id, source_root)
    if not bool(source_report["ok"]):
        raise ApprovalWorkflowError("不可变源文件校验失败，拒绝写入正史")
    draft_path = Path(str(row["file_path"]))
    if sha256_file(draft_path) != str(row["content_sha256"]):
        raise ApprovalWorkflowError("草稿文件哈希已变化，拒绝写入正史")

    now = utc_now()
    commit_id = stable_id(
        "canon-commit",
        book_id,
        selected_edition,
        draft_id,
        str(row["content_sha256"]),
        str(row["base_projection_hash"]),
    )
    chapter_id = stable_id("canon-chapter", book_id, commit_id)
    document_id = stable_id("canon-document", book_id, commit_id)
    span_id = stable_id("canon-span", book_id, commit_id)
    ordinal = contract.chapter
    heading = f"## 第{ordinal}章 {draft.chapter_title}".rstrip()
    canon_content = f"{heading}\n\n{draft.prose_markdown.strip()}\n"
    canon_dir = workspace / "canon"
    canon_dir.mkdir(parents=True, exist_ok=True)
    canon_path = canon_dir / f"chapter-{ordinal:06d}-{commit_id}.md"
    content_hash = sha256_bytes(canon_content.encode())
    line_count = len(canon_content.splitlines())
    snapshot_path: Path | None = None
    canon_written = False
    snapshot_written = False
    try:
        with database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute(
                "SELECT commit_id FROM canon_commits WHERE draft_id=? AND edition_id=?",
                (draft_id, selected_edition),
            ).fetchone()
            if duplicate is not None:
                raise ApprovalWorkflowError(f"草稿已经提交：{duplicate['commit_id']}")
            current = projection_from_connection(connection, book_id, edition_id=selected_edition)
            if current.through_event_seq != int(row["base_event_seq"]) or current.sha256() != str(
                row["base_projection_hash"]
            ):
                raise ApprovalWorkflowError(
                    "Continuation Boundary 已漂移；必须重建边界、合同和草稿"
                )
            canon_path.write_bytes(canon_content.encode("utf-8"))
            canon_written = True
            order_index = int(
                connection.execute(
                    """
                    SELECT COALESCE(MAX(order_index), -1) + 1
                    FROM source_documents WHERE book_id=?
                    """,
                    (book_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO source_documents(
                    document_id, book_id, relative_path, sha256, encoding,
                    byte_size, line_count, order_index, order_confidence,
                    status, imported_at, version, edition_id
                ) VALUES (?, ?, ?, ?, 'utf-8', ?, ?, ?, 1.0,
                          'GENERATED_CANON', ?, 1, ?)
                """,
                (
                    document_id,
                    book_id,
                    str(canon_path.relative_to(workspace)),
                    content_hash,
                    len(canon_content.encode()),
                    line_count,
                    order_index,
                    now,
                    selected_edition,
                ),
            )
            connection.execute(
                """
                INSERT INTO chapters(
                    chapter_id, book_id, document_id, ordinal, raw_heading,
                    chapter_number_text, title, start_line, end_line,
                    start_char, end_char, content, content_sha256,
                    summary, created_at, version, edition_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 0, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    chapter_id,
                    book_id,
                    document_id,
                    ordinal,
                    heading,
                    str(ordinal),
                    draft.chapter_title,
                    line_count,
                    len(canon_content),
                    canon_content,
                    content_hash,
                    draft.notes[0] if draft.notes else None,
                    now,
                    selected_edition,
                ),
            )
            connection.execute(
                """
                INSERT INTO source_spans(
                    span_id, book_id, document_id, chapter_id, kind,
                    start_line, end_line, start_char, end_char, text_sha256,
                    excerpt, created_at, version, edition_id
                ) VALUES (?, ?, ?, ?, 'AUTHOR_APPROVED_CHAPTER', 1, ?, 0, ?, ?, ?, ?, 1, ?)
                """,
                (
                    span_id,
                    book_id,
                    document_id,
                    chapter_id,
                    line_count,
                    len(canon_content),
                    content_hash,
                    canon_content,
                    now,
                    selected_edition,
                ),
            )
            connection.execute(
                """
                INSERT INTO chapter_fts(chapter_id, book_id, heading, content)
                VALUES (?, ?, ?, ?)
                """,
                (chapter_id, book_id, heading, canon_content),
            )
            connection.execute(
                """
                UPDATE drafts SET status=?, approved_at=?, version=version+1
                WHERE draft_id=? AND edition_id=?
                """,
                (DraftStatus.AUTHOR_APPROVED.value, now, draft_id, selected_edition),
            )
            store = EventStore(database)
            approval_event = store.append_in_transaction(
                connection,
                book_id=book_id,
                event_type="AUTHOR_APPROVED",
                aggregate_type="draft",
                aggregate_id=draft_id,
                payload={
                    "draft_id": draft_id,
                    "contract_id": contract.contract_id,
                    "approval": confirmation,
                    "approved_at": now,
                },
                source_kind="AUTHOR_CONFIRMATION",
                source_id=draft_id,
                status=EventStatus.COMMITTED,
                information_state=InformationStatus.CANON,
                canon_commit_id=commit_id,
                edition_id=selected_edition,
            )
            last_event_seq = approval_event.event_seq
            for change in draft.state_changes:
                last_event_seq = _append_change(
                    store,
                    connection,
                    book_id=book_id,
                    draft_id=draft_id,
                    commit_id=commit_id,
                    change=change,
                    source_span_id=span_id,
                    chapter_id=chapter_id,
                    ordinal=ordinal,
                    edition_id=selected_edition,
                )
            if draft.structure_tags and not any(
                change.kind == "repetition" for change in draft.state_changes
            ):
                tag_id = stable_id("repetition", book_id, draft_id)
                repetition = DraftStateChange(
                    kind="repetition",
                    record_id=tag_id,
                    payload={
                        "tag_id": tag_id,
                        "candidate_id": row["candidate_id"],
                        "signature": "|".join(sorted(draft.structure_tags)),
                        "structure_tags": draft.structure_tags,
                    },
                    evidence_quotes=[draft.structure_tags[0]],
                )
                last_event_seq = _append_change(
                    store,
                    connection,
                    book_id=book_id,
                    draft_id=draft_id,
                    commit_id=commit_id,
                    change=repetition,
                    source_span_id=span_id,
                    chapter_id=chapter_id,
                    ordinal=ordinal,
                    edition_id=selected_edition,
                )
            major = contract.primary_function is NarrativeFunction.MAJOR_PAYOFF or any(
                bool(change.payload.get("major_event"))
                for change in draft.state_changes
                if change.kind == "payoff"
            )
            aftershock_ids: list[str] = []
            if major:
                for change in _aftershock_changes(
                    book_id=book_id,
                    draft_id=draft_id,
                    thread_id=contract.primary_thread,
                    ordinal=ordinal,
                ):
                    aftershock_ids.append(change.record_id)
                    last_event_seq = _append_change(
                        store,
                        connection,
                        book_id=book_id,
                        draft_id=draft_id,
                        commit_id=commit_id,
                        change=change,
                        source_span_id=span_id,
                        chapter_id=chapter_id,
                        ordinal=ordinal,
                        edition_id=selected_edition,
                    )
            directive_rows = connection.execute(
                """
                SELECT directive_id FROM author_directives
                WHERE book_id=? AND edition_id=? AND status='ACTIVE' AND mode='next_chapter'
                ORDER BY priority, created_at
                """,
                (book_id, selected_edition),
            ).fetchall()
            consumed_directive_ids = [str(item["directive_id"]) for item in directive_rows]
            if consumed_directive_ids:
                connection.executemany(
                    """
                    UPDATE author_directives
                    SET status='CONSUMED', version=version+1
                    WHERE directive_id=? AND edition_id=?
                    """,
                    [(directive_id, selected_edition) for directive_id in consumed_directive_ids],
                )
                directive_event = store.append_in_transaction(
                    connection,
                    book_id=book_id,
                    event_type="AUTHOR_DIRECTIVES_CONSUMED",
                    aggregate_type="chapter",
                    aggregate_id=chapter_id,
                    payload={
                        "chapter_id": chapter_id,
                        "directive_ids": consumed_directive_ids,
                    },
                    source_kind="CANON_COMMIT",
                    source_id=draft_id,
                    status=EventStatus.COMMITTED,
                    information_state=InformationStatus.AUTHOR_INTENT,
                    canon_commit_id=commit_id,
                    edition_id=selected_edition,
                )
                last_event_seq = directive_event.event_seq
            chapter_event = store.append_in_transaction(
                connection,
                book_id=book_id,
                event_type="CANON_CHAPTER_COMMITTED",
                aggregate_type="chapter",
                aggregate_id=chapter_id,
                payload={
                    "chapter_id": chapter_id,
                    "document_id": document_id,
                    "source_span_id": span_id,
                    "draft_id": draft_id,
                    "contract_id": contract.contract_id,
                    "ordinal": ordinal,
                    "title": draft.chapter_title,
                    "content_sha256": content_hash,
                    "aftershock_obligation_ids": aftershock_ids,
                },
                source_kind="AUTHOR_APPROVED_DRAFT",
                source_id=draft_id,
                status=EventStatus.COMMITTED,
                information_state=InformationStatus.CANON,
                canon_commit_id=commit_id,
                edition_id=selected_edition,
            )
            last_event_seq = chapter_event.event_seq
            connection.execute(
                """
                INSERT INTO canon_commits(
                    commit_id, book_id, draft_id, event_start_seq, event_end_seq,
                    chapter_id, author_approval, committed_at, version, edition_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    commit_id,
                    book_id,
                    draft_id,
                    approval_event.event_seq,
                    last_event_seq,
                    chapter_id,
                    confirmation,
                    now,
                    selected_edition,
                ),
            )
            projection = projection_from_connection(
                connection, book_id, edition_id=selected_edition
            )
            persist_projection_in_transaction(connection, projection)
            state_json = projection.canonical_json()
            state_hash = projection.sha256()
            snapshot_id = stable_id(
                "snapshot",
                book_id,
                selected_edition,
                str(projection.through_event_seq),
                state_hash,
            )
            snapshots_dir = workspace / "snapshots"
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = snapshots_dir / f"{snapshot_id}.json"
            snapshot_path.write_text(
                json_dumps(
                    {
                        "snapshot_id": snapshot_id,
                        "book_id": book_id,
                        "edition_id": selected_edition,
                        "through_event_seq": projection.through_event_seq,
                        "state_sha256": state_hash,
                        "state": projection.model_dump(mode="json"),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            snapshot_written = True
            connection.execute(
                """
                INSERT INTO snapshots(
                    snapshot_id, book_id, edition_id, through_event_seq,
                    state_sha256, state_json, file_path, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    snapshot_id,
                    book_id,
                    selected_edition,
                    projection.through_event_seq,
                    state_hash,
                    state_json,
                    str(snapshot_path),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE drafts SET status=?, committed_at=?, version=version+1
                WHERE draft_id=? AND edition_id=?
                """,
                (DraftStatus.CANON_COMMITTED.value, now, draft_id, selected_edition),
            )
            connection.execute(
                "UPDATE books SET updated_at=?, version=version+1 WHERE book_id=?",
                (now, book_id),
            )
    except ApprovalWorkflowError:
        if canon_written:
            canon_path.unlink(missing_ok=True)
        if snapshot_written and snapshot_path is not None:
            snapshot_path.unlink(missing_ok=True)
        raise
    except (MaterializationError, KeyError, OSError, sqlite3.DatabaseError, ValueError) as exc:
        if canon_written:
            canon_path.unlink(missing_ok=True)
        if snapshot_written and snapshot_path is not None:
            snapshot_path.unlink(missing_ok=True)
        raise ApprovalWorkflowError(f"正史物化失败：{exc}") from exc
    return {
        "book_id": book_id,
        "draft_id": draft_id,
        "status": DraftStatus.CANON_COMMITTED.value,
        "commit_id": commit_id,
        "chapter_id": chapter_id,
        "chapter": ordinal,
        "canon_path": str(canon_path),
        "content_sha256": content_hash,
        "event_start_seq": approval_event.event_seq,
        "event_end_seq": last_event_seq,
        "snapshot_path": str(snapshot_path),
        "source_verify": source_report,
    }
