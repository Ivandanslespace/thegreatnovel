from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.migration import MigrationOptions, migrate_legacy
from novel_authoring.web.app import create_app
from novel_authoring.workflows.handoffs import (
    create_initialization_handoff,
    get_handoff,
    write_waiting_for_user,
)


def _legacy_book(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "story.md").write_text(
        "第1章 测试\n\n潮声盖过了警报。\n\n第2章 余波\n\n灯塔重新亮起。\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="canonical-book",
        title="Canonical Book",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
    )
    return source, workspace / "canonical-book"


def test_migration_rewrites_manifest_and_new_handoff_uses_operation_layout(
    tmp_path: Path,
) -> None:
    source, workspace = _legacy_book(tmp_path)
    library = tmp_path / "library"
    result = migrate_legacy(
        MigrationOptions(
            book_id="canonical-book",
            source_root=source,
            workspace_root=workspace,
            library_root=library,
            apply=True,
        )
    )
    assert result.plan.status == "APPLIED"
    paths = BookLayout(library).for_book("canonical-book")
    database = Database(paths.database)
    manifest = json.loads((paths.root / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_root"] == str(paths.source)

    handoff = create_initialization_handoff(
        database,
        "canonical-book",
        requested_stage="NOVEL_INITIALIZATION",
    )
    operation = Path(str(handoff["task_directory"]))
    assert (operation / "manifest.json").is_file()
    assert (operation / "input" / "task.json").is_file()
    assert (operation / "output" / "result.json").is_file()
    assert (operation / "events.jsonl").is_file()

    write_waiting_for_user(
        database,
        str(handoff["handoff_id"]),
        {
            "question_id": "route",
            "question": "选择哪条路线？",
            "reason": "需要作者决定",
            "options": ["A", "B"],
            "related_artifacts": [],
            "required_author_decision": "true",
        },
    )
    loaded = get_handoff(database, str(handoff["handoff_id"]))
    assert loaded["waiting_for_user"]["question_id"] == "route"


def test_library_web_lists_paths_and_imports_without_overwriting(tmp_path: Path) -> None:
    source, workspace = _legacy_book(tmp_path)
    library = tmp_path / "library"
    migrate_legacy(
        MigrationOptions(
            book_id="canonical-book",
            source_root=source,
            workspace_root=workspace,
            library_root=library,
            apply=True,
        )
    )
    database = Database(BookLayout(library).for_book("canonical-book").database)
    app = create_app(database, book_id="canonical-book", library_root=library)
    client = TestClient(app)

    assert client.get("/library").status_code == 200
    assert "canonical-book" in client.get("/api/library").text
    assert client.get("/library/canonical-book/paths").status_code == 200
    assert client.get("/library/canonical-book/export/latest/").status_code == 404

    new_source = tmp_path / "new.md"
    new_source.write_text("第1章 新书\n\n正文。\n", encoding="utf-8")
    assert client.post(
        "/api/library/import",
        json={"book_id": "new-book", "source_path": str(new_source)},
    ).status_code == 403
    imported = client.post(
        "/api/library/import",
        headers={"X-CSRF-Token": app.state.csrf_token},
        json={"book_id": "new-book", "title": "新书", "source_path": str(new_source)},
    )
    assert imported.status_code == 200
    imported_text = (library / "new-book" / "source" / "new.md").read_text(encoding="utf-8")
    assert imported_text == new_source.read_text(encoding="utf-8")
