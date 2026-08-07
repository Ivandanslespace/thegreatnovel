from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.context.router import (
    ContextPurpose,
    RuntimeContextRequest,
    route_runtime_context,
)
from novel_authoring.db.database import Database
from novel_authoring.distill.models import EvidenceMappingStatus
from novel_authoring.distill.service import (
    create_distill_handoff,
    import_distill_result,
    prepare_book_sources,
)
from novel_authoring.edition import edition_chapters
from novel_authoring.runtime_baseline import (
    BaselineCategory,
    BaselineStatus,
    RuntimeBaselineEntry,
    build_runtime_baseline,
    load_earned_surface,
    load_runtime_baseline,
)
from novel_authoring.storage.library import LibraryAddOptions, add_book
from novel_authoring.utils import json_dumps
from novel_authoring.workflows.handoffs import (
    HandoffStatus,
    claim_handoff,
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


def _publish_distill(
    database: Database,
    book_id: str,
    prepared: dict[str, object],
    dimensions: str,
    *,
    external: Path | None = None,
) -> dict[str, object]:
    handoff = create_distill_handoff(
        database,
        book_id,
        preparation_id=str(prepared["preparation_id"])
        if external is None
        else None,
        sources=[external] if external is not None else None,
        dimensions=dimensions,
        depth="compact",
    )
    handoff_id = str(handoff["handoff_id"])
    task_directory = Path(str(handoff["task_directory"]))
    task = json.loads(_task_path(task_directory).read_text(encoding="utf-8"))
    claim = claim_handoff(database, handoff_id, "phase3-pytest")
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.RUNNING,
        claim_token=str(claim["claim_token"]),
    )
    root = task_directory / "artifacts" / "distill_skill"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text("# Distill Skill\n", encoding="utf-8")
    (root / "distillation-report.md").write_text("# Report\n", encoding="utf-8")
    source_id = str(task["distill"]["source_ids"][0])
    for dimension in [item.strip() for item in dimensions.split(",")]:
        if external is not None:
            content = (
                f"# {dimension}\n\n## Control\n\n"
                "- Craft Control: keep external material abstract and transferable.\n"
            )
        else:
            content = (
                f"# {dimension}\n\n## Finding\n\n"
                f"- Sources: `{source_id} · segment-0001 · 行 1-2`\n"
                f"- Subject IDs: subject-phase3\n"
                f"- Chapter Range: 1-2\n"
                f"- Observation: {dimension} observation for phase3.\n"
            )
        (root / f"{dimension}.md").write_text(content, encoding="utf-8")
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.COMPLETED,
        claim_token=str(claim["claim_token"]),
        result=_result(task, handoff_id),
    )
    return import_distill_result(database, book_id, handoff_id)


def _setup_book(tmp_path: Path, book_id: str = "phase3-book") -> tuple[Database, dict[str, object]]:
    added = add_book(
        LibraryAddOptions(
            book_id=book_id,
            title="Phase 3 测试书",
            source=FIXTURE,
            library_root=tmp_path / "library",
            confirm_order=True,
        )
    )
    database = Database(added.database)
    return database, prepare_book_sources(database, book_id)


def _source_evidence(
    database: Database, book_id: str, prepared: dict[str, object]
) -> dict[str, object]:
    root = Path(str(prepared["root"]))
    index = json.loads((root / "chapter_index.json").read_text(encoding="utf-8"))
    segment = index["sources"][0]["segments"][0]
    with database.connect() as connection:
        chapter = edition_chapters(connection, book_id, "base")[0]
        span = connection.execute(
            "SELECT start_line, end_line FROM source_spans WHERE span_id=?",
            (chapter["source_span_id"],),
        ).fetchone()
    assert span is not None
    return {
        "source_id": str(prepared["source_ids"][0]),
        "segment_id": str(segment["segment_id"]),
        "start_line": int(span["start_line"]),
        "end_line": int(span["end_line"]),
        "chapter_id": str(chapter["chapter_id"]),
        "source_span_ids": [str(chapter["source_span_id"])],
        "mapping_status": EvidenceMappingStatus.EXACT.value,
        "direct_text_confirmed": True,
    }


def test_book_profil_self_export_stale_cleanup_and_external_isolation(tmp_path: Path) -> None:
    database, prepared = _setup_book(tmp_path)
    first = _publish_distill(database, "phase3-book", prepared, "worldbuilding,plot")
    profile = Path(str(tmp_path / "library" / "phase3-book" / "book_profil"))
    manifest = json.loads((profile / "profile_manifest.json").read_text(encoding="utf-8"))
    assert manifest["scope"] == "SELF_BOOK"
    assert (profile / "worldbuilding.md").is_file()
    assert (profile / "plot.md").is_file()
    registry_root = (
        tmp_path
        / "library"
        / "phase3-book"
        / "editions"
        / "base"
        / "analysis"
        / "distill"
    )
    self_pointer = json.loads(
        (registry_root / "latest_self_book.json").read_text(encoding="utf-8")
    )
    assert self_pointer["distill_id"] == first["distill_id"]

    external = tmp_path / "external.md"
    external.write_text("## 第一章\n外部参考。\n", encoding="utf-8")
    external_result = _publish_distill(
        database, "phase3-book", prepared, "style", external=external
    )
    after_external = json.loads((profile / "profile_manifest.json").read_text(encoding="utf-8"))
    assert after_external["distill_id"] == first["distill_id"]
    references = json.loads((registry_root / "references.json").read_text(encoding="utf-8"))
    assert any(
        item["distill_id"] == external_result["distill_id"]
        for item in references["references"]
    )

    _publish_distill(database, "phase3-book", prepared, "worldbuilding")
    assert (profile / "worldbuilding.md").is_file()
    assert not (profile / "plot.md").exists()


def test_runtime_baseline_validates_source_and_unknown_without_canon_change(tmp_path: Path) -> None:
    database, prepared = _setup_book(tmp_path, "baseline-book")
    evidence = _source_evidence(database, "baseline-book", prepared)
    input_path = tmp_path / "baseline.json"
    input_path.write_text(
        json_dumps(
            {
                "book_id": "baseline-book",
                "edition_id": "base",
                "boundary_chapter": 1,
                "scope": "SELF_BOOK",
                "entries": [
                    {
                        "entry_id": "cap-source",
                        "category": "capability",
                        "name": "source capability",
                        "statement": "A capability explicitly established in source text.",
                        "status": "SOURCE_VERIFIED",
                        "source_kind": "SOURCE_TEXT",
                        "evidence": [evidence],
                    },
                    {
                        "entry_id": "cap-unknown",
                        "category": "capability",
                        "name": "unknown capability",
                        "statement": "The source has not established this capability.",
                        "status": "UNKNOWN",
                        "source_kind": "DISTILL_RECALL",
                    },
                    {
                        "entry_id": "setup",
                        "category": "promise",
                        "name": "open setup",
                        "statement": "An open setup remains available for payoff.",
                        "status": "SOURCE_PARTIAL",
                        "source_kind": "SOURCE_TEXT",
                        "attributes": {
                            "payoff_forms": "partial_reveal|costly_use",
                            "payoff_cost": "must spend an existing resource",
                            "post_payoff_pressure": "a larger unresolved constraint",
                        },
                        "evidence": [evidence],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    before_projection = rebuild_projection(
        database, "baseline-book", edition_id="base", persist=False
    )
    with database.connect() as connection:
        before_active = connection.execute(
            "SELECT active_edition_id FROM books WHERE book_id=?", ("baseline-book",)
        ).fetchone()[0]
        before_events = connection.execute(
            "SELECT COUNT(*) FROM events WHERE book_id=?", ("baseline-book",)
        ).fetchone()[0]
    result = build_runtime_baseline(
        database, "baseline-book", input_path=input_path, boundary_chapter=1
    )
    baseline = load_runtime_baseline(database, "baseline-book")
    earned = load_earned_surface(database, "baseline-book")
    assert baseline is not None and earned is not None
    assert result["boundary_chapter"] == 1
    assert any(item.status is BaselineStatus.SOURCE_VERIFIED for item in baseline.entries)
    assert len(earned.earned_capabilities) == 1
    assert len(earned.available_payoffs) == 1
    assert any("unknown capability" in item for item in earned.hard_unknowns)
    with database.connect() as connection:
        after_active = connection.execute(
            "SELECT active_edition_id FROM books WHERE book_id=?", ("baseline-book",)
        ).fetchone()[0]
        after_events = connection.execute(
            "SELECT COUNT(*) FROM events WHERE book_id=?", ("baseline-book",)
        ).fetchone()[0]
    after_projection = rebuild_projection(
        database, "baseline-book", edition_id="base", persist=False
    )
    assert before_projection.canonical_json() == after_projection.canonical_json()
    assert before_active == after_active == "base"
    assert before_events == after_events == 0


def test_distill_recall_cannot_directly_become_capability() -> None:
    with pytest.raises(ValidationError):
        RuntimeBaselineEntry(
            entry_id="bad",
            category=BaselineCategory.CAPABILITY,
            name="bad",
            statement="Only a Distill interpretation.",
            status=BaselineStatus.SOURCE_VERIFIED,
            source_kind="DISTILL_RECALL",
            evidence=[],
        )


def test_context_router_filters_metadata_and_keeps_external_soft(tmp_path: Path) -> None:
    database, prepared = _setup_book(tmp_path, "router-book")
    _publish_distill(database, "router-book", prepared, "worldbuilding,plot")
    request = RuntimeContextRequest(
        purpose=ContextPurpose.CANDIDATE_PLANNING,
        dimensions=["worldbuilding"],
        subject_ids=["subject-phase3"],
        runtime_uses=["candidate_planning"],
    )
    bundle = route_runtime_context(
        database,
        "router-book",
        purpose=ContextPurpose.CANDIDATE_PLANNING,
        request=request,
    )
    assert len(bundle.observations) == 1
    assert bundle.observations[0].subject_ids == ["subject-phase3"]
    assert bundle.hard_boundary

    external = tmp_path / "external-router.md"
    external.write_text("## 第一章\n外部参考。\n", encoding="utf-8")
    _publish_distill(database, "router-book", prepared, "style", external=external)
    external_bundle = route_runtime_context(
        database,
        "router-book",
        purpose=ContextPurpose.CANDIDATE_PLANNING,
    )
    assert all(
        item.information_class.value in {"INTERPRETATION", "CRAFT_CONTROL"}
        or item.kind in {"synthesis", "transferable_principle", "craft_control"}
        for item in external_bundle.observations
    )
    assert external_bundle.literary_arcs == []
    assert external_bundle.continuity_candidates == []
    assert external_bundle.character_voice_profiles == []
    assert external_bundle.theme_questions == []
    assert external_bundle.craft_controls


def test_blind_benchmark_generation_artifacts_do_not_leak_future_inputs() -> None:
    root = Path("library/cable-survival-blind-50/benchmark/run_phase3_fused_20260807")
    if not root.is_dir():
        pytest.skip("真实盲测工件只存在于本地 acceptance workspace")
    manifest = json.loads((root / "benchmark_manifest.json").read_text(encoding="utf-8"))
    snapshot = json.loads((root / "generation_snapshot.json").read_text(encoding="utf-8"))
    assert manifest["visible_chapter_boundary"] == 50
    assert manifest["baseline_boundary"] == 50
    assert manifest["ground_truth_available_during_generation"] is False
    assert snapshot["truth_revealed"] is False
    generated_files = [
        *sorted((root / "generated").glob("*.md")),
        *sorted((root / "candidate_sets").glob("*.json")),
        *sorted((root / "contracts").glob("*.json")),
    ]
    assert generated_files
    forbidden = ("hidden_ground_truth", "cable-survival-test", "真实第51章", "真实第52章")
    for path in generated_files:
        text = path.read_text(encoding="utf-8")
        assert not any(item in text for item in forbidden), path
