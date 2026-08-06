from __future__ import annotations

import json
from pathlib import Path

from novel_authoring.db.database import Database
from novel_authoring.distill.service import (
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
        "distill_skill_root": "artifacts/distill_skill",
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
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.COMPLETED,
        claim_token=str(claim["claim_token"]),
        result=_result(task, handoff_id),
    )

    published = import_distill_result(database, "distill-test-book", handoff_id)
    published_root = Path(str(published["skill_root"]))
    assert published["canon_committed"] is False
    assert (published_root / "SKILL.md").is_file()
    assert (published_root / "distill_manifest.json").is_file()
    assert (published_root.parent.parent / "latest.json").is_file()

    initialization = create_initialization_handoff(
        database,
        "distill-test-book",
        requested_stage="NOVEL_INITIALIZATION",
    )
    init_task = json.loads(
        (_task_path(Path(str(initialization["task_directory"])))).read_text(encoding="utf-8")
    )
    assert init_task["distill_reference"]["usage"] == "REFERENCE_ONLY"
