from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.storage.library import LibraryAddOptions, add_book
from novel_authoring.web.app import create_app, web_doctor


def _book(tmp_path: Path, book_id: str = "workbench-book") -> Database:
    source = tmp_path / "source"
    source.mkdir()
    (source / "novel.md").write_text(
        "第1章 灯塔\n\n海风把旧门吹开。\n\n"
        "第2章 潮声\n\n潮声里藏着一段坐标。\n\n"
        "第3章 返航\n\n主角把坐标收进怀里。\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id=book_id,
        title="Workbench 测试书",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
    )
    database = Database(workspace / book_id / "state.sqlite3")
    database.initialize()
    profile_root = workspace / book_id / "book_profil"
    profile_root.mkdir()
    (profile_root / "worldbuilding.md").write_text(
        "# 世界观\n\n潮汐会遮蔽灯塔坐标。\n", encoding="utf-8"
    )
    (profile_root / "profile_manifest.json").write_text(
        json.dumps(
            {"scope": "SELF_BOOK", "profile_version": "test-profile-v1"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return database


def _chapter_ids(database: Database) -> list[str]:
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT chapter_id FROM chapters ORDER BY ordinal"
        ).fetchall()
    return [str(row["chapter_id"]) for row in rows]


def _read_only_snapshot(database: Database) -> dict[str, object]:
    with database.connect() as connection:
        events = connection.execute(
            "SELECT event_id, event_seq, event_type FROM events ORDER BY event_seq"
        ).fetchall()
        commits = connection.execute(
            "SELECT commit_id, draft_id, event_end_seq FROM canon_commits ORDER BY commit_id"
        ).fetchall()
        projection = connection.execute(
            "SELECT book_id, through_event_seq, state_sha256, state_json "
            "FROM projection_metadata ORDER BY book_id"
        ).fetchall()
        editions = connection.execute(
            "SELECT edition_id, status, version FROM editions ORDER BY edition_id"
        ).fetchall()
        books = connection.execute(
            "SELECT book_id, active_edition_id, mode FROM books ORDER BY book_id"
        ).fetchall()
    return {
        "events": [tuple(row) for row in events],
        "commits": [tuple(row) for row in commits],
        "projection": [tuple(row) for row in projection],
        "editions": [tuple(row) for row in editions],
        "books": [tuple(row) for row in books],
    }


def test_workbench_renders_real_profile_and_highlights_selected_node(tmp_path: Path) -> None:
    database = _book(tmp_path)
    app = create_app(database, book_id="workbench-book")
    client = TestClient(app)

    response = client.get(
        "/books/workbench-book/editions/base/workbench?node=worldbuilding"
    )

    assert response.status_code == 200
    assert "Novel Authoring Workbench" in response.text
    assert "潮汐会遮蔽灯塔坐标" in response.text
    assert "SOFT INTERPRETATION" in response.text
    assert 'data-workbench-shell' in response.text
    assert "is-selected" in response.text
    assert "当前 Book 没有" not in response.text


def test_chapter_navigation_is_query_only_and_exposes_source_gap(tmp_path: Path) -> None:
    database = _book(tmp_path, "historical-workbench-book")
    app = create_app(database, book_id="historical-workbench-book")
    client = TestClient(app)
    chapter_ids = _chapter_ids(database)
    before = _read_only_snapshot(database)

    for chapter_id in (chapter_ids[0], chapter_ids[2], chapter_ids[1], chapter_ids[0]):
        response = client.get(
            "/api/books/historical-workbench-book/editions/base/"
            f"chapters/{chapter_id}/context"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["chapter_id"] == chapter_id
        assert body["read_only_navigation"] is True
        assert body["before_state"]["availability"] == "SOURCE_CHAPTER_STATE_PROJECTION_MISSING"
        assert body["after_state"]["availability"] == "SOURCE_CHAPTER_STATE_PROJECTION_MISSING"
        assert body["chapter_delta"]["status"] == "SOURCE_CHAPTER_STATE_PROJECTION_MISSING"

    selected = client.get(
        f"/books/historical-workbench-book/editions/base/workbench?chapter_id={chapter_ids[1]}&node=chapter"
    )
    assert selected.status_code == 200
    assert "第2章" in selected.text
    assert "selected_chapter_anchor · 2" in selected.text
    assert "SOURCE_CHAPTER_STATE_PROJECTION_MISSING" in selected.text
    assert "潮声里藏着一段坐标" in selected.text
    assert _read_only_snapshot(database) == before


def test_draft_is_provisional_and_explicit_save_does_not_touch_canon(tmp_path: Path) -> None:
    database = _book(tmp_path, "draft-workbench-book")
    root = tmp_path / "workspace" / "draft-workbench-book"
    draft_path = root / "drafts" / "draft-61.md"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text("旧稿\n", encoding="utf-8")
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO chapter_contracts(
                contract_id, book_id, candidate_id, target_chapter_ordinal,
                mode, contract_json, contract_sha256, status, created_at,
                version, edition_id
            ) VALUES (?, ?, NULL, ?, 'faithful_continuation', ?, 'contract',
                      'READY', 'now', 1, 'base')
            """,
            (
                "contract-61",
                "draft-workbench-book",
                4,
                json.dumps({"lens": "CONTINUITY_ACTIVE_THREAD"}),
            ),
        )
        connection.execute(
            """
            INSERT INTO drafts(
                draft_id, book_id, contract_id, candidate_id, file_path,
                content_sha256, status, revision, created_at, task_id,
                edition_id, chapter_title, output_json, base_event_seq,
                base_projection_hash, validation_run_id
            ) VALUES (?, ?, ?, NULL, ?, 'old-content', 'VALIDATED', 1, 'now',
                      'task-61', 'base', '第4章 接续', ?, 0, 'empty', 'run-1')
            """,
            (
                "draft-61",
                "draft-workbench-book",
                "contract-61",
                str(draft_path),
                json.dumps(
                    {
                        "prose_markdown": "旧稿",
                        "state_changes": [{"kind": "ADDED", "description": "新线索"}],
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        connection.execute(
            """
            INSERT INTO validation_reports(
                report_id, book_id, draft_id, validator, severity, passed,
                report_json, created_at, version
            ) VALUES ('report-61', ?, 'draft-61', 'test', 'INFO', 1, '{}', 'now', 1)
            """,
            ("draft-workbench-book",),
        )

    app = create_app(database, book_id="draft-workbench-book")
    client = TestClient(app)
    page = client.get(
        "/books/draft-workbench-book/editions/base/workbench?draft_id=draft-61&node=chapter"
    )
    assert page.status_code == 200
    assert "PROVISIONAL" in page.text
    assert "PROVISIONAL_DRAFT_DELTA" in page.text
    assert "旧稿" in page.text

    before = _read_only_snapshot(database)
    saved = client.post(
        "/api/books/draft-workbench-book/editions/base/drafts/draft-61/content",
        headers={"X-CSRF-Token": app.state.csrf_token},
        json={"content": "新稿\n"},
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "DRAFT"
    assert draft_path.read_text(encoding="utf-8") == "新稿\n"
    with database.connect() as connection:
        draft = connection.execute(
            "SELECT status, validation_run_id, output_json FROM drafts WHERE draft_id='draft-61'"
        ).fetchone()
        reports = connection.execute(
            "SELECT COUNT(*) FROM validation_reports WHERE draft_id='draft-61'"
        ).fetchone()[0]
    assert draft is not None
    assert draft["status"] == "DRAFT"
    assert draft["validation_run_id"] is None
    assert json.loads(str(draft["output_json"]))["prose_markdown"] == "新稿"
    assert reports == 0
    assert _read_only_snapshot(database) == before


def test_web_doctor_checks_native_workbench_surface() -> None:
    result = web_doctor()

    assert result["ok"] is True
    assert result["checks"]["frontend"]["mode"] == "native-javascript-css"
    assert result["checks"]["routes"]["missing"] == []
    assert result["checks"]["api_health"]["ok"] is True


def test_library_mode_auto_discovers_canonical_sessions_and_opens_each_workbench(
    tmp_path: Path,
) -> None:
    library_root = tmp_path / "library"
    for book_id in ("session-a", "session-b"):
        source = tmp_path / f"{book_id}.md"
        source.write_text(f"第1章 {book_id}\n\n正文。\n", encoding="utf-8")
        add_book(
            LibraryAddOptions(
                book_id=book_id,
                title=f"标题 {book_id}",
                source=source,
                library_root=library_root,
            )
        )
    (library_root / ".raw-input").mkdir(parents=True)
    (library_root / ".raw-input" / "notes.md").write_text("输入素材", encoding="utf-8")

    app = create_app(Database(tmp_path / "boot.sqlite3"), library_root=library_root)
    client = TestClient(app)

    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/library"

    library = client.get("/api/library")
    assert library.status_code == 200
    assert [item["book_id"] for item in library.json()["books"]] == [
        "session-a",
        "session-b",
    ]
    page = client.get("/library")
    assert page.status_code == 200
    assert "标题 session-a" in page.text
    assert "标题 session-b" in page.text
    assert ".raw-input" not in page.text
    assert page.text.count("打开 Workbench") == 2

    workbench = client.get("/books/session-b/editions/base/workbench")
    assert workbench.status_code == 200
    assert "标题 session-b" in workbench.text
    assert "标题 session-a" in workbench.text
