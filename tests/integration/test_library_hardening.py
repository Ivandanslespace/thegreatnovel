from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novel_authoring.atlas.offline import export_snapshot
from novel_authoring.atlas.service import REQUIRED_ARTIFACTS
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.storage import library as library_service
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.library import LibraryAddOptions, add_book
from novel_authoring.storage.manifest import verify_mirror
from novel_authoring.storage.migration import (
    MigrationOptions,
    cleanup_legacy,
    migrate_legacy,
    plan_legacy_cleanup,
)
from novel_authoring.storage.models import LayoutError
from novel_authoring.web.app import create_app
from novel_authoring.workflows.extraction import prepare_extraction_task


def _add(tmp_path: Path, book_id: str = "demo") -> tuple[Path, Path]:
    source = tmp_path / f"{book_id}.md"
    source.write_text(
        "第1章 开始\n\n潮声盖过了警报。\n\n第2章 余波\n\n灯塔重新亮起。\n",
        encoding="utf-8",
    )
    library = tmp_path / "library"
    add_book(
        LibraryAddOptions(
            book_id=book_id,
            title="演示书",
            source=source,
            library_root=library,
        )
    )
    return library, source


def test_library_add_is_authoritative_and_web_reads_first_chapter(tmp_path: Path) -> None:
    library, source = _add(tmp_path)
    paths = BookLayout(library).for_book("demo")
    assert paths.database.is_file()
    assert paths.source_manifest.is_file()
    assert verify_mirror(paths.root)["match"] is True
    assert not (paths.root / "agent_tasks").exists()
    assert not (paths.root / "agent_outputs").exists()

    app = create_app(Database(paths.database), book_id="demo", library_root=library)
    client = TestClient(app)
    new_source = tmp_path / "web.md"
    new_source.write_text("第1章 Web 新书\n\n第一章正文。\n", encoding="utf-8")
    response = client.post(
        "/api/library/import",
        headers={"X-CSRF-Token": app.state.csrf_token},
        json={"book_id": "web-book", "source_path": str(new_source)},
    )
    assert response.status_code == 200
    assert response.json()["readiness_status"] == "NEEDS_INITIALIZATION"
    chapters = client.get("/api/books/web-book/editions/base/chapters")
    assert chapters.status_code == 200
    assert chapters.json()[0]["ordinal"] == 1
    chapter_id = chapters.json()[0]["chapter_id"]
    detail = client.get(f"/api/books/web-book/editions/base/chapters/{chapter_id}")
    assert detail.status_code == 200
    assert detail.json()["chapter"]["ordinal"] == 1

    # A second add never replaces an existing target, even when the deprecated
    # caller asks for an existing-target override.
    before = hashlib.sha256(paths.book_yaml.read_bytes()).hexdigest()
    try:
        add_book(LibraryAddOptions(book_id="demo", source=source, library_root=library))
    except ValueError:
        pass
    else:
        raise AssertionError("existing target must be rejected")
    assert hashlib.sha256(paths.book_yaml.read_bytes()).hexdigest() == before


def test_canonical_tasks_use_operation_workspace(tmp_path: Path) -> None:
    library, _ = _add(tmp_path)
    paths = BookLayout(library).for_book("demo")
    task = prepare_extraction_task(Database(paths.database), "demo", chapter_start=1, chapter_end=1)
    input_path = Path(str(task["input"]))
    output_path = Path(str(task["expected_output"]))
    assert input_path.parent.name == "input"
    assert output_path.parent.name == "output"
    assert input_path.parents[1].parent.name == "operations"
    assert (input_path.parents[1] / "manifest.json").is_file()
    assert not (paths.root / "agent_tasks").exists()
    assert not (paths.root / "agent_outputs").exists()


def test_portable_bundle_contract_and_archive_retention(tmp_path: Path) -> None:
    library, _ = _add(tmp_path)
    database = Database(BookLayout(library).for_book("demo").database)
    latest: Path | None = None
    for _ in range(5):
        result = export_snapshot(database, "demo")
        latest = Path(str(result["output_root"]))
    assert latest is not None
    expected = {
        "index.html",
        "manifest.json",
        "README.txt",
        "assets/app.js",
        "assets/style.css",
        "data/book.js",
        "data/metrics/metrics.js",
        "data/atlas/atlas.js",
        "data/reports/reports.js",
    }
    files = {path.relative_to(latest).as_posix() for path in latest.rglob("*") if path.is_file()}
    assert expected <= files
    assert not any(path.lower().endswith(".svg") for path in files)
    index = (latest / "index.html").read_text(encoding="utf-8")
    assert len(index.encode("utf-8")) < 1_000_000
    assert "fetch" not in index.lower()
    assert "window.__NOVEL_SNAPSHOT__" not in index
    manifest = json.loads((latest / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["chapter_chunk_max_bytes"] == 512 * 1024
    for relative, expected_hash in manifest["file_hashes"].items():
        assert hashlib.sha256((latest / relative).read_bytes()).hexdigest() == expected_hash
    chunks = sorted(latest.glob("data/chapters/chunk-*.js"))
    assert chunks
    assert all("registerChapterChunk" in chunk.read_text(encoding="utf-8") for chunk in chunks)
    archive = latest.parent / "archive"
    assert len(list(archive.glob("portable-*"))) <= 3


def test_legacy_cleanup_schema_and_existing_target_safety(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "story.md").write_text("第1章 测试\n\n正文。\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="legacy",
        title="Legacy",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
    )
    library = tmp_path / "library"
    migrate_legacy(
        MigrationOptions(
            book_id="legacy",
            source_root=source,
            workspace_root=workspace / "legacy",
            library_root=library,
            apply=True,
        )
    )
    paths = BookLayout(library).for_book("legacy")
    metadata = json.loads(paths.legacy_locations.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "legacy-locations-v1"
    assert {item["kind"] for item in metadata["legacy_locations"]} == {"source", "workspace"}
    try:
        migrate_legacy(
            MigrationOptions(
                book_id="legacy",
                source_root=source,
                workspace_root=workspace / "legacy",
                library_root=library,
                apply=True,
                allow_existing=True,
            )
        )
    except ValueError:
        pass
    else:
        raise AssertionError("migration must reject an existing target")
    plan = plan_legacy_cleanup(library, "legacy")
    assert {item["kind"] for item in plan["candidates"]} == {"source", "workspace"}
    result = cleanup_legacy(
        library,
        "legacy",
        apply=True,
        confirmation=str(plan["confirmation"]),
    )
    assert len(result["moved"]) == 2


def test_atlas_visuals_are_explicit_optional_exports() -> None:
    assert all(not path.lower().endswith(".svg") for path in REQUIRED_ARTIFACTS)


@pytest.mark.parametrize(
    "failure_point",
    [
        "finalize_manifest",
        "mirror_generation",
        "mirror_verify",
        "book_yaml",
        "readme",
        "rename",
    ],
)
def test_library_add_failures_leave_no_final_target_or_source_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    source = tmp_path / "atomic-source.md"
    source.write_text("第1章 原子性\n\n正文不变。\n", encoding="utf-8")
    library = tmp_path / "library"
    target = library / "atomic-book"
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError(f"injected failure: {failure_point}")

    if failure_point == "finalize_manifest":
        monkeypatch.setattr(library_service, "_finalize_manifest", fail)
    elif failure_point == "mirror_generation":
        monkeypatch.setattr(library_service, "write_compatibility_mirror", fail)
    elif failure_point == "mirror_verify":
        monkeypatch.setattr(library_service, "verify_mirror", lambda _root: {"match": False})
    elif failure_point == "book_yaml":
        monkeypatch.setattr(library_service.BookRegistry, "write", fail)
    elif failure_point == "readme":
        monkeypatch.setattr(library_service.BookRegistry, "write_readme", fail)
    else:
        def fail_rename(_source: Path, _target: Path) -> Path:
            raise OSError("injected rename failure")

        monkeypatch.setattr(Path, "rename", fail_rename)

    with pytest.raises((LayoutError, OSError, RuntimeError)):
        add_book(
            LibraryAddOptions(
                book_id="atomic-book",
                title="原子性测试",
                source=source,
                library_root=library,
            )
        )

    assert not target.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
    assert list(library.glob(".add-*")) == []


def test_library_add_existing_target_is_byte_for_byte_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("第1章 新来源\n\n不应覆盖。\n", encoding="utf-8")
    library = tmp_path / "library"
    target = library / "existing-book"
    target.mkdir(parents=True)
    (target / "sentinel.txt").write_text("keep", encoding="utf-8")
    before = {
        path.relative_to(target).as_posix(): path.read_bytes()
        for path in target.rglob("*")
        if path.is_file()
    }

    with pytest.raises(LayoutError):
        add_book(
            LibraryAddOptions(
                book_id="existing-book",
                source=source,
                library_root=library,
            )
        )

    after = {
        path.relative_to(target).as_posix(): path.read_bytes()
        for path in target.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_library_add_success_reads_chapters_and_fts_after_publish(tmp_path: Path) -> None:
    library, _source = _add(tmp_path, "atomic-success")
    paths = BookLayout(library).for_book("atomic-success")
    with Database(paths.database).connect() as connection:
        chapter = connection.execute(
            "SELECT chapter_id, content FROM chapters WHERE book_id=? ORDER BY ordinal LIMIT 1",
            ("atomic-success",),
        ).fetchone()
        fts = connection.execute(
            "SELECT chapter_id FROM chapter_fts WHERE book_id=? LIMIT 1",
            ("atomic-success",),
        ).fetchone()
    assert chapter is not None and str(chapter[1])
    assert fts is not None


def test_agents_rejects_worktree_creation_instruction() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "不得创建额外 worktree" in text
    assert "使用独立 worktree" not in text
    assert "所有生产代码修改由主 Agent 在 `小说续写_codex` 当前工作树串行完成" in text
