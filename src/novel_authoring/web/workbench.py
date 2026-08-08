"""Read-only query layer for the author-facing Novel Workbench.

The Workbench is a projection of the existing Book Library and Edition data.
It deliberately keeps chapter navigation on the query side: loading a
chapter never rebuilds, persists, approves, activates, or rolls back any
authoritative state.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.edition import edition_chapters
from novel_authoring.storage.layout import BookLayout

PROFILE_DIMENSIONS: tuple[tuple[str, str, str], ...] = (
    ("worldbuilding", "世界观", "worldbuilding.md"),
    ("characters", "人物", "characters.md"),
    ("plot", "剧情", "plot.md"),
    ("style", "Style", "style.md"),
    ("narrative", "Narrative", "narrative.md"),
    ("dialogue", "Dialogue", "dialogue.md"),
    ("pacing", "Pacing", "pacing.md"),
    ("themes", "Themes", "themes.md"),
    ("continuity", "Continuity", "continuity.md"),
)

_PROJECTION_COLLECTIONS = (
    "facts",
    "timeline",
    "entities",
    "character_states",
    "knowledge",
    "relationships",
    "resources",
    "capabilities",
    "threads",
    "promises",
    "payoffs",
    "repetition",
    "style_profiles",
    "committed_chapters",
)


def _book_row(connection: sqlite3.Connection, book_id: str) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM books WHERE book_id=?", (book_id,)).fetchone()
    if row is None:
        raise ValueError("book 不存在")
    return dict(row)


def _edition_row(
    connection: sqlite3.Connection, book_id: str, edition_id: str
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM editions WHERE book_id=? AND edition_id=?",
        (book_id, edition_id),
    ).fetchone()
    if row is None:
        raise ValueError("edition 不存在")
    return dict(row)


def _base_chapters_without_edition(
    connection: sqlite3.Connection, book_id: str
) -> list[dict[str, Any]]:
    """Read imported base chapters from a deferred library add without mutating it."""

    rows = connection.execute(
        """
        SELECT c.*, d.status AS document_status, d.relative_path
        FROM chapters c JOIN source_documents d ON d.document_id=c.document_id
        WHERE c.book_id=? AND c.edition_id='base' AND d.status!='GENERATED_CANON'
        ORDER BY c.ordinal, c.created_at, c.chapter_id
        """,
        (book_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _read_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return {"raw": str(value)}
    return parsed if isinstance(parsed, dict) else {"raw": parsed}


def _profile_root(book: dict[str, Any], book_id: str) -> Path:
    root = Path(str(book["workspace_root"])).expanduser().resolve()
    if (root / "book.yaml").is_file():
        return BookLayout(root.parent).for_book(book_id).book_profil
    return root / "book_profil"


def _profile_data(book: dict[str, Any], book_id: str, selected_node: str) -> tuple[
    list[dict[str, Any]], dict[str, Any], dict[str, Any]
]:
    root = _profile_root(book, book_id)
    manifest = _read_json(
        root.joinpath("profile_manifest.json").read_text(encoding="utf-8")
        if root.joinpath("profile_manifest.json").is_file()
        else {}
    )
    items: list[dict[str, Any]] = []
    selected: dict[str, Any] = {
        "id": selected_node,
        "label": "作者画像",
        "available": False,
        "content": "",
        "relative_path": "",
    }
    for dimension, label, filename in PROFILE_DIMENSIONS:
        path = root / filename
        available = path.is_file()
        item = {
            "id": dimension,
            "label": label,
            "filename": filename,
            "available": available,
            "relative_path": f"book_profil/{filename}",
        }
        items.append(item)
        if dimension == selected_node:
            selected = {
                **item,
                "content": path.read_text(encoding="utf-8")[:500_000] if available else "",
            }
    return items, selected, manifest


def _draft_rows(
    connection: sqlite3.Connection, book_id: str, edition_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT d.*, c.target_chapter_ordinal, c.contract_json
        FROM drafts d
        LEFT JOIN chapter_contracts c
          ON c.book_id=d.book_id AND c.edition_id=d.edition_id
         AND c.contract_id=d.contract_id
        WHERE d.book_id=? AND d.edition_id=?
        ORDER BY COALESCE(c.target_chapter_ordinal, 0), d.created_at DESC, d.draft_id DESC
        """,
        (book_id, edition_id),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        target = item.get("target_chapter_ordinal")
        item["target_chapter_ordinal"] = None if target is None else int(target)
        item["display_status"] = (
            "VALIDATED_DRAFT" if str(item.get("status")) == "VALIDATED" else str(item.get("status"))
        )
        item["contract_payload"] = _read_json(item.get("contract_json"))
        item["output"] = _read_json(item.get("output_json"))
        path = Path(str(item.get("file_path") or ""))
        try:
            item["content"] = path.read_text(encoding="utf-8")[:500_000] if path.is_file() else ""
        except OSError:
            item["content"] = ""
        report_rows = connection.execute(
            "SELECT validator, severity, passed, report_json, run_id "
            "FROM validation_reports WHERE draft_id=? ORDER BY validator, run_id",
            (str(item["draft_id"]),),
        ).fetchall()
        item["validation_reports"] = [
            {
                **dict(report),
                "passed": bool(report["passed"]),
                "report": _read_json(report["report_json"]),
            }
            for report in report_rows
        ]
        item["validation_warning_count"] = sum(
            1 for report in item["validation_reports"] if not report["passed"]
        )
        result.append(item)
    return result


def _draft_tree_items(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the newest visible draft for each target chapter."""

    latest: dict[int, dict[str, Any]] = {}
    for draft in drafts:
        ordinal = draft.get("target_chapter_ordinal")
        if ordinal is None or ordinal in latest:
            continue
        latest[int(ordinal)] = {
            "chapter_id": None,
            "draft_id": str(draft["draft_id"]),
            "ordinal": int(ordinal),
            "title": str(draft.get("chapter_title") or f"第{ordinal}章"),
            "status": str(draft["display_status"]),
            "warning_count": int(draft.get("validation_warning_count", 0)),
            "is_draft": True,
        }
    return [latest[key] for key in sorted(latest)]


def _chapter_tree_items(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for chapter in chapters:
        document_status = str(chapter.get("document_status") or "SOURCE")
        status = "CANON" if document_status == "GENERATED_CANON" else "SOURCE"
        result.append(
            {
                "chapter_id": str(chapter["chapter_id"]),
                "draft_id": None,
                "ordinal": int(chapter["ordinal"]),
                "title": str(chapter["title"]),
                "status": status,
                "warning_count": 0,
                "is_draft": False,
            }
        )
    return result


def _selected_records(
    chapters: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    *,
    chapter_id: str | None,
    draft_id: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    selected_draft = next(
        (draft for draft in drafts if draft_id and str(draft["draft_id"]) == draft_id), None
    )
    selected_chapter = next(
        (
            chapter
            for chapter in chapters
            if chapter_id and str(chapter["chapter_id"]) == chapter_id
        ),
        None,
    )
    if selected_chapter is None and selected_draft is not None:
        target = selected_draft.get("target_chapter_ordinal")
        selected_chapter = next(
            (
                chapter
                for chapter in chapters
                if target is not None and int(chapter["ordinal"]) == int(target)
            ),
            None,
        )
    if selected_chapter is None and selected_draft is None and chapters:
        selected_chapter = chapters[-1]
    return selected_chapter, selected_draft


def _commit_anchors(
    connection: sqlite3.Connection,
    book_id: str,
    edition_id: str,
    chapters: list[dict[str, Any]],
) -> dict[int, int]:
    anchors: dict[int, int] = {}
    for chapter in chapters:
        if str(chapter.get("document_status")) != "GENERATED_CANON":
            continue
        row = connection.execute(
            "SELECT MAX(event_end_seq) AS event_end_seq FROM canon_commits "
            "WHERE book_id=? AND edition_id=? AND chapter_id=?",
            (book_id, edition_id, str(chapter["chapter_id"])),
        ).fetchone()
        if row is not None and row["event_end_seq"] is not None:
            anchors[int(chapter["ordinal"])] = int(row["event_end_seq"])
    return anchors


def _projection_view(
    connection: sqlite3.Connection,
    book_id: str,
    edition_id: str,
    *,
    ordinal: int,
    event_seq: int | None,
    label: str,
) -> dict[str, Any]:
    if event_seq is None:
        return {
            "availability": "SOURCE_CHAPTER_STATE_PROJECTION_MISSING",
            "label": label,
            "anchor_chapter_ordinal": ordinal,
            "through_event_seq": None,
            "reason": (
                "当前章节只有不可变 Source 章节；尚未建立逐章 Source-Derived Runtime "
                "State Projection，不能把最新状态冒充历史截面。"
            ),
        }
    projection = projection_from_connection(
        connection,
        book_id,
        edition_id=edition_id,
        through_event_seq=event_seq,
    )
    return {
        "availability": "CANON_EVENT_PROJECTION",
        "label": label,
        "anchor_chapter_ordinal": ordinal,
        "through_event_seq": event_seq,
        "projection_hash": projection.sha256(),
        "state": projection.model_dump(mode="json"),
    }


def _projection_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_state = before.get("state")
    after_state = after.get("state")
    if not isinstance(before_state, dict) or not isinstance(after_state, dict):
        return {
            "status": "SOURCE_CHAPTER_STATE_PROJECTION_MISSING",
            "changes": [],
            "reason": after.get("reason") or before.get("reason"),
        }
    changes: list[dict[str, Any]] = []
    for collection in _PROJECTION_COLLECTIONS:
        old = before_state.get(collection) or {}
        new = after_state.get(collection) or {}
        if not isinstance(old, dict) or not isinstance(new, dict):
            continue
        for record_id in sorted(set(old) | set(new)):
            if record_id not in old:
                changes.append(
                    {
                        "collection": collection,
                        "record_id": record_id,
                        "kind": "ADDED",
                        "after": new[record_id],
                    }
                )
            elif record_id not in new:
                changes.append(
                    {
                        "collection": collection,
                        "record_id": record_id,
                        "kind": "REMOVED",
                        "before": old[record_id],
                    }
                )
            elif old[record_id] != new[record_id]:
                changes.append(
                    {
                        "collection": collection,
                        "record_id": record_id,
                        "kind": "CHANGED",
                        "before": old[record_id],
                        "after": new[record_id],
                    }
                )
    return {"status": "CANON_EVENT_DELTA", "changes": changes, "change_count": len(changes)}


def _validation_context(
    selected_draft: dict[str, Any] | None,
) -> dict[str, Any]:
    if selected_draft is None:
        return {
            "status": "SOURCE_READ_ONLY",
            "hard_gate": "NOT_RUN",
            "reports": [],
        }
    reports = selected_draft.get("validation_reports", [])
    return {
        "status": selected_draft.get("display_status", selected_draft.get("status")),
        "hard_gate": (
            "PASS"
            if reports and all(item["passed"] for item in reports)
            else "NOT_RUN_OR_WARNING"
        ),
        "reports": reports,
    }


def _chapter_context(
    connection: sqlite3.Connection,
    book_id: str,
    edition_id: str,
    chapters: list[dict[str, Any]],
    selected_chapter: dict[str, Any] | None,
    selected_draft: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if selected_chapter is None and selected_draft is None:
        return None
    if selected_chapter is not None:
        ordinal_value = selected_chapter.get("ordinal")
    elif selected_draft is not None:
        ordinal_value = selected_draft.get("target_chapter_ordinal")
    else:
        return None
    if ordinal_value is None:
        return None
    ordinal = int(ordinal_value)
    anchors = _commit_anchors(connection, book_id, edition_id, chapters)
    before_seq = max(
        (seq for chapter_ordinal, seq in anchors.items() if chapter_ordinal < ordinal),
        default=None,
    )
    after_seq = max(
        (seq for chapter_ordinal, seq in anchors.items() if chapter_ordinal <= ordinal),
        default=None,
    )
    before = _projection_view(
        connection,
        book_id,
        edition_id,
        ordinal=ordinal,
        event_seq=before_seq,
        label="BEFORE_CHAPTER",
    )
    after = _projection_view(
        connection,
        book_id,
        edition_id,
        ordinal=ordinal,
        event_seq=after_seq,
        label="AFTER_CHAPTER",
    )
    delta = _projection_delta(before, after)
    provisional = selected_draft is not None
    if selected_draft is not None:
        output = _read_json(selected_draft.get("output_json"))
        state_changes = output.get("state_changes", [])
        if not isinstance(state_changes, list):
            state_changes = []
        if state_changes:
            delta = {
                "status": "PROVISIONAL_DRAFT_DELTA",
                "changes": state_changes,
                "change_count": len(state_changes),
                "note": "这是 Draft 自带的 provisional state_changes，不是 Canon Event。",
            }
            after = {
                "availability": "PROVISIONAL_DRAFT_ONLY",
                "label": "PROVISIONAL_AFTER_CHAPTER",
                "anchor_chapter_ordinal": ordinal,
                "based_on": after,
                "state_changes": state_changes,
            }
        elif after.get("availability") != "CANON_EVENT_PROJECTION":
            after = {
                **after,
                "availability": "PROVISIONAL_DRAFT_ONLY",
                "label": "PROVISIONAL_AFTER_CHAPTER",
                "note": "Draft 正文存在，但没有可审计的 provisional state_changes。",
            }
    source_content = "" if selected_chapter is None else str(selected_chapter.get("content") or "")
    draft_content = "" if selected_draft is None else str(selected_draft.get("content") or "")
    if selected_draft is not None:
        status = str(selected_draft.get("display_status"))
    elif selected_chapter is not None:
        status = (
            "CANON"
            if str(selected_chapter.get("document_status")) == "GENERATED_CANON"
            else "SOURCE"
        )
    else:
        return None
    source_boundary = max(
        (
            int(chapter["ordinal"])
            for chapter in chapters
            if str(chapter.get("document_status")) != "GENERATED_CANON"
        ),
        default=0,
    )
    canon_boundary = max(anchors, default=0)
    narrative_context: dict[str, Any] = {"status": "NOT_AVAILABLE"}
    if selected_draft is not None:
        contract = selected_draft.get("contract_payload") or {}
        narrative_context = {
            "status": "PROVISIONAL_DRAFT_CONTEXT",
            "lens": contract.get("lens"),
            "narrative_portfolio": contract.get("narrative_portfolio", {}),
            "narrative_debt": contract.get("narrative_debt", {}),
            "innovation_control": selected_draft.get("output", {}).get("innovation_control")
            if isinstance(selected_draft.get("output"), dict)
            else None,
        }
    return {
        "book_id": book_id,
        "edition_id": edition_id,
        "chapter_id": None if selected_chapter is None else str(selected_chapter["chapter_id"]),
        "chapter_ordinal": ordinal,
        "chapter_status": status,
        "selected_chapter_anchor": ordinal,
        "read_only_navigation": True,
        "before_state": before,
        "chapter_delta": delta,
        "after_state": after,
        "source_content": source_content,
        "draft_content": draft_content,
        "validation": _validation_context(selected_draft),
        "narrative_context": narrative_context,
        "canonical_boundary": {
            "chapter_ordinal": canon_boundary,
            "event_seq": max(anchors.values(), default=0),
            "status": "CANON" if canon_boundary else "NO_CANON_EVENT_ANCHOR",
        },
        "source_boundary": {
            "chapter_ordinal": source_boundary,
            "status": "SOURCE_ONLY" if source_boundary else "EMPTY",
        },
        "provisional": provisional,
    }


def _public_chapter_context(context: dict[str, Any] | None) -> dict[str, Any] | None:
    if context is None:
        return None
    return context


def build_workbench_context(
    database: Any,
    book_id: str,
    edition_id: str | None,
    *,
    chapter_id: str | None = None,
    draft_id: str | None = None,
    node: str = "overview",
) -> dict[str, Any]:
    """Build one Workbench read model without initializing or mutating the DB."""

    with database.connect() as connection:
        book = _book_row(connection, book_id)
        selected_edition_id = edition_id or str(book.get("active_edition_id") or "base")
        edition_rows = connection.execute(
            "SELECT edition_id, display_name, status, parent_edition_id "
            "FROM editions WHERE book_id=? ORDER BY created_at, edition_id",
            (book_id,),
        ).fetchall()
        editions = [dict(row) for row in edition_rows]
        if not editions and selected_edition_id == "base":
            edition = {
                "edition_id": "base",
                "display_name": str(book.get("title") or book_id),
                "status": "ACTIVE",
                "parent_edition_id": None,
            }
            editions = [dict(edition)]
        else:
            edition = _edition_row(connection, book_id, selected_edition_id)
        raw_chapters = (
            _base_chapters_without_edition(connection, book_id)
            if not edition_rows and selected_edition_id == "base"
            else edition_chapters(connection, book_id, selected_edition_id)
        )
        drafts = _draft_rows(connection, book_id, selected_edition_id)
        selected_chapter, selected_draft = _selected_records(
            raw_chapters,
            drafts,
            chapter_id=chapter_id,
            draft_id=draft_id,
        )
        selected_anchor = None
        if selected_chapter is not None:
            selected_anchor = int(selected_chapter["ordinal"])
        elif selected_draft is not None:
            selected_anchor = selected_draft.get("target_chapter_ordinal")
        selected_node = node
        valid_profile_nodes = {item[0] for item in PROFILE_DIMENSIONS}
        if (
            selected_node not in valid_profile_nodes
            and selected_node not in {"overview", "chapter"}
        ):
            selected_node = "overview"
        if (selected_chapter is not None or selected_draft is not None) and node == "chapter":
            selected_node = "chapter"
        if selected_node == "chapter" and selected_chapter is None and selected_draft is None:
            selected_node = "overview"
        chapter_context = _chapter_context(
            connection,
            book_id,
            selected_edition_id,
            raw_chapters,
            selected_chapter,
            selected_draft,
        )
    profile_items, selected_profile, profile_manifest = _profile_data(
        book, book_id, selected_node
    )
    chapter_items = _chapter_tree_items(raw_chapters)
    draft_items = _draft_tree_items(drafts)
    latest_chapter = chapter_items[-1] if chapter_items else None
    if selected_anchor is None and latest_chapter is not None:
        selected_anchor = int(latest_chapter["ordinal"])
    return {
        "book": book,
        "book_id": book_id,
        "edition_id": selected_edition_id,
        "edition": edition,
        "editions": editions,
        "chapter_items": chapter_items,
        "draft_items": draft_items,
        "profile_items": profile_items,
        "profile_manifest": profile_manifest,
        "selected_profile": selected_profile,
        "selected_node": selected_node,
        "selected_chapter": selected_chapter,
        "selected_draft": selected_draft,
        "chapter_context": _public_chapter_context(chapter_context),
        "selected_chapter_anchor": selected_anchor,
        "latest_chapter": latest_chapter,
        "book_status": str(book.get("readiness_status") or "UNKNOWN"),
        "data_ownership": {
            "source": "Book Library source/ and immutable chapters",
            "distill": "book_profil/ author-facing derived view",
            "runtime": "existing Runtime Baseline + Canon Projection; query only",
            "draft": "existing Edition writing/drafts and drafts table",
            "canon": "existing append-only events and Canon Projection",
        },
    }


__all__ = ["PROFILE_DIMENSIONS", "build_workbench_context"]
