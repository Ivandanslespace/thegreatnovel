from __future__ import annotations

import json
from pathlib import Path

import pytest

from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.db.database import Database
from novel_authoring.distill.service import (
    DistillError,
    create_distill_handoff,
    import_distill_result,
    prepare_book_sources,
)
from novel_authoring.storage.library import LibraryAddOptions, add_book
from novel_authoring.workflows.handoffs import (
    HandoffStatus,
    claim_handoff,
    create_initialization_handoff,
    update_handoff_status,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def _task_path(task_directory: Path) -> Path:
    return task_directory / "input" / "task.json"


def _result(task: dict[str, object], handoff_id: str) -> dict[str, object]:
    distill = task["distill"]
    assert isinstance(distill, dict)
    return {
        "handoff_id": handoff_id,
        "handoff_type": "NOVEL_DISTILLATION",
        "requested_stage": "DISTILL",
        "completed_stage": "DISTILLED",
        "book_id": task["book_id"],
        "edition_id": task["edition_id"],
        "status": "DISTILLED",
        "task_ids": [],
        "candidate_ids": [],
        "selected_candidate_id": None,
        "contract_id": None,
        "draft_id": None,
        "campaign_id": None,
        "revision_unit_ids": [],
        "artifact_paths": [
            "artifacts/distill_skill/SKILL.md",
            "artifacts/distill_skill/distillation-report.md",
        ],
        "validation_summary": {"provenance": "PASS", "leakage": "PASS"},
        "warnings": [],
        "next_action": "novel distill import",
        "canon_committed": False,
        "edition_activated": False,
        "base_event_seq": task["base_event_seq"],
        "base_projection_hash": task["base_projection_hash"],
        "metric_run_ids": [],
        "metric_bundle_hash": None,
        "completed_at": "2026-01-01T00:00:00+00:00",
        "distill_id": distill["distill_id"],
        "distill_source_ids": distill["source_ids"],
        "distill_dimensions": distill["dimensions"],
        "distill_mode": distill["mode"],
        "distill_depth": distill["depth"],
        "distill_scope": distill["scope"],
        "distill_skill_root": "artifacts/distill_skill",
    }


def _canon_state(database: Database, book_id: str) -> dict[str, object]:
    with database.connect() as connection:
        editions = tuple(
            (str(row["edition_id"]), str(row["status"]), row["activated_at"])
            for row in connection.execute(
                "SELECT edition_id, status, activated_at FROM editions "
                "WHERE book_id=? ORDER BY edition_id",
                (book_id,),
            ).fetchall()
        )
        commits = tuple(
            (str(row["commit_id"]), str(row["chapter_id"]), str(row["edition_id"]))
            for row in connection.execute(
                "SELECT commit_id, chapter_id, edition_id FROM canon_commits "
                "WHERE book_id=? ORDER BY commit_id",
                (book_id,),
            ).fetchall()
        )
        return {
            "active_edition_id": connection.execute(
                "SELECT active_edition_id FROM books WHERE book_id=?", (book_id,)
            ).fetchone()[0],
            "projection": projection_from_connection(connection, book_id).canonical_json(),
            "editions": editions,
            "canon_commits": commits,
        }


def test_distill_handoff_freezes_and_publishes_reference_skill(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    added = add_book(
        LibraryAddOptions(
            book_id="distill-test-book",
            title="distill 测试书",
            source=FIXTURE,
            library_root=library_root,
            confirm_order=True,
        )
    )
    database = Database(added.database)
    prepared = prepare_book_sources(database, "distill-test-book")
    assert prepared["source_count"] == 1
    assert prepared["segment_count"] >= 1

    handoff = create_distill_handoff(
        database,
        "distill-test-book",
        preparation_id=str(prepared["preparation_id"]),
        dimensions="worldbuilding,plot",
        mode="create",
        depth="compact",
    )
    handoff_id = str(handoff["handoff_id"])
    task_directory = Path(str(handoff["task_directory"]))
    task = json.loads(_task_path(task_directory).read_text(encoding="utf-8"))
    frozen_root = Path(str(task["distill"]["prepared_root"]))
    assert frozen_root.is_dir()
    assert (frozen_root / "manifest.json").is_file()

    claim = claim_handoff(database, handoff_id, "pytest-codex")
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.RUNNING,
        claim_token=str(claim["claim_token"]),
    )
    skill_root = task_directory / "artifacts" / "distill_skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: test-reference\n---\n\n# Reference only\n",
        encoding="utf-8",
    )
    (skill_root / "distillation-report.md").write_text(
        "# Report\n\nprovenance: PASS\n",
        encoding="utf-8",
    )
    source_id = str(task["distill"]["source_ids"][0])
    for dimension in ("worldbuilding", "plot"):
        (skill_root / f"{dimension}.md").write_text(
            f"# {dimension}\n\n"
            "## Finding\n\n"
            f"- Sources: `{source_id} · segment-0001 · 行 1-2`\n"
            f"- Observation: {dimension} observation for strict package validation.\n"
            "- Confidence: high\n",
            encoding="utf-8",
        )
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.COMPLETED,
        claim_token=str(claim["claim_token"]),
        result=_result(task, handoff_id),
    )

    before_canon = _canon_state(database, "distill-test-book")
    published = import_distill_result(database, "distill-test-book", handoff_id)
    assert _canon_state(database, "distill-test-book") == before_canon
    published_root = Path(str(published["skill_root"]))
    assert published["canon_committed"] is False
    assert (published_root / "SKILL.md").is_file()
    assert (published_root / "distill_manifest.json").is_file()
    assert (published_root / "machine" / "package.json").is_file()
    assert (published_root / "machine" / "observations.jsonl").is_file()
    assert (published_root.parent.parent / "latest.json").is_file()
    assert published["scope"] == "SELF_BOOK"
    assert published["package_root"].endswith("machine")

    initialization = create_initialization_handoff(
        database,
        "distill-test-book",
        requested_stage="NOVEL_INITIALIZATION",
    )
    init_task = json.loads(
        (_task_path(Path(str(initialization["task_directory"])))).read_text(encoding="utf-8")
    )
    assert init_task["distill_reference"]["usage"] == "REFERENCE_ONLY"
    assert init_task["distill_reference"]["scope"] == "SELF_BOOK"


def test_distill_import_rejects_missing_selected_dimension(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    added = add_book(
        LibraryAddOptions(
            book_id="distill-missing-dimension",
            title="strict dimension test",
            source=FIXTURE,
            library_root=library_root,
            confirm_order=True,
        )
    )
    database = Database(added.database)
    prepared = prepare_book_sources(database, "distill-missing-dimension")
    handoff = create_distill_handoff(
        database,
        "distill-missing-dimension",
        preparation_id=str(prepared["preparation_id"]),
        dimensions="worldbuilding,plot",
    )
    handoff_id = str(handoff["handoff_id"])
    task_directory = Path(str(handoff["task_directory"]))
    task = json.loads(_task_path(task_directory).read_text(encoding="utf-8"))
    claim = claim_handoff(database, handoff_id, "pytest-codex")
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.RUNNING,
        claim_token=str(claim["claim_token"]),
    )
    skill_root = task_directory / "artifacts" / "distill_skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (skill_root / "distillation-report.md").write_text("# Report\n", encoding="utf-8")
    source_id = str(task["distill"]["source_ids"][0])
    (skill_root / "worldbuilding.md").write_text(
        f"# worldbuilding\n\n- Sources: `{source_id} · segment-0001 · 行 1-2`\n"
        "- Observation: only one selected dimension\n",
        encoding="utf-8",
    )
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.COMPLETED,
        claim_token=str(claim["claim_token"]),
        result=_result(task, handoff_id),
    )
    with pytest.raises(DistillError, match="plot"):
        import_distill_result(database, "distill-missing-dimension", handoff_id)
