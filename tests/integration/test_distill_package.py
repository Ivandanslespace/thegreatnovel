from __future__ import annotations

import json
from pathlib import Path

import pytest

from novel_authoring.db.database import Database
from novel_authoring.distill.mapping import map_evidence
from novel_authoring.distill.models import (
    DistilledEvidence,
    DistillScope,
    EvidenceMappingStatus,
)
from novel_authoring.distill.package import (
    DistillationPackageError,
    build_distillation_package,
    validate_distillation_package,
)
from novel_authoring.distill.service import create_distill_handoff, prepare_book_sources
from novel_authoring.edition import create_edition
from novel_authoring.revision import (
    approve_revision_campaign,
    build_revision_impact,
    build_revision_plan,
    complete_revision_impact_audit,
    create_revision_campaign,
    import_revision_draft,
    prepare_revision_draft_task,
    validate_revision_campaign,
)
from novel_authoring.storage.library import LibraryAddOptions, add_book

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def _setup_book(
    tmp_path: Path, book_id: str = "distill-package-book"
) -> tuple[Database, dict[str, object]]:
    added = add_book(
        LibraryAddOptions(
            book_id=book_id,
            title="Distill package 测试",
            source=FIXTURE,
            library_root=tmp_path / "library",
            confirm_order=True,
        )
    )
    database = Database(added.database)
    return database, prepare_book_sources(database, book_id)


def _skill_root(tmp_path: Path, source_id: str, *, missing: str | None = None) -> Path:
    root = tmp_path / "skill"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (root / "distillation-report.md").write_text("# Report\n", encoding="utf-8")
    for dimension in ("worldbuilding", "plot"):
        if dimension == missing:
            continue
        (root / f"{dimension}.md").write_text(
            f"# {dimension}\n\n## Finding\n\n"
            f"- Sources: `{source_id} · segment-0001 · 行 1-2`\n"
            f"- Observation: {dimension} finding\n"
            "- Confidence: high\n",
            encoding="utf-8",
        )
    return root


def test_exact_and_unmapped_evidence_mapping(tmp_path: Path) -> None:
    database, prepared = _setup_book(tmp_path)
    prep_root = Path(str(prepared["root"]))
    source_id = str(prepared["source_ids"][0])
    index = json.loads((prep_root / "chapter_index.json").read_text(encoding="utf-8"))
    segment = index["sources"][0]["segments"][0]
    exact = map_evidence(
        database,
        "distill-package-book",
        "base",
        prep_root / "manifest.json",
        DistilledEvidence(
            source_id=source_id,
            segment_id=str(segment["segment_id"]),
            start_line=int(segment["start_line"]),
            end_line=int(segment["end_line"]),
        ),
    )
    assert exact.mapping_status is EvidenceMappingStatus.EXACT
    assert exact.reason == "EXACT_EXPLICIT_CHAPTER"
    assert exact.chapter_id
    assert exact.source_span_ids

    unmapped = map_evidence(
        database,
        "distill-package-book",
        "base",
        prep_root / "manifest.json",
        DistilledEvidence(
            source_id=source_id,
            segment_id="segment-does-not-exist",
            start_line=1,
            end_line=2,
        ),
    )
    assert unmapped.mapping_status is EvidenceMappingStatus.UNMAPPED
    assert unmapped.reason == "UNMAPPED_SEGMENT_NOT_FOUND"
    assert unmapped.source_span_ids == []


def test_conflicting_mapping_is_not_silently_selected(tmp_path: Path) -> None:
    database, prepared = _setup_book(tmp_path)
    original_root = Path(str(prepared["root"]))
    conflict_root = tmp_path / "conflicting-preparation"
    conflict_root.mkdir()
    manifest = json.loads((original_root / "manifest.json").read_text(encoding="utf-8"))
    chapter_index = json.loads((original_root / "chapter_index.json").read_text(encoding="utf-8"))
    source = chapter_index["sources"][0]
    source["segments"].append(
        {**source["segments"][0], "chapter_id": "different-chapter"}
    )
    (conflict_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    (conflict_root / "chapter_index.json").write_text(
        json.dumps(chapter_index, ensure_ascii=False), encoding="utf-8"
    )
    evidence = DistilledEvidence(
        source_id=str(prepared["source_ids"][0]),
        segment_id=str(source["segments"][0]["segment_id"]),
        start_line=int(source["segments"][0]["start_line"]),
        end_line=int(source["segments"][0]["end_line"]),
    )
    mapped = map_evidence(
        database,
        "distill-package-book",
        "base",
        conflict_root / "manifest.json",
        evidence,
    )
    assert mapped.mapping_status is EvidenceMappingStatus.CONFLICTING
    assert mapped.reason == "CONFLICTING_MULTIPLE_CHAPTERS"
    assert mapped.chapter_id is None


def test_package_strictly_requires_selected_dimension(tmp_path: Path) -> None:
    database, prepared = _setup_book(tmp_path)
    source_id = str(prepared["source_ids"][0])
    request = {
        "distill_id": "distill-test-package",
        "mode": "create",
        "depth": "compact",
        "scope": DistillScope.SELF_BOOK.value,
        "scope_id": "distill-package-book",
        "dimensions": ["worldbuilding", "plot"],
        "source_ids": [source_id],
        "preparation_manifest": str(Path(str(prepared["manifest"]))),
    }
    root = _skill_root(tmp_path, source_id)
    built = build_distillation_package(database, "distill-package-book", "base", request, root)
    summary = validate_distillation_package(
        root,
        expected_book_id="distill-package-book",
        expected_edition_id="base",
        expected_scope="SELF_BOOK",
        expected_dimensions=["worldbuilding", "plot"],
    )
    assert built["summary"]["finding_count"] == 2
    assert summary["finding_count"] == 2
    assert (root / "machine" / "package.json").is_file()

    missing_root = _skill_root(tmp_path / "missing", source_id, missing="plot")
    with pytest.raises(DistillationPackageError, match="plot"):
        build_distillation_package(database, "distill-package-book", "base", request, missing_root)


def test_scope_is_persisted_for_external_and_comparative_requests(tmp_path: Path) -> None:
    database, _prepared = _setup_book(tmp_path, book_id="scope-book")
    external_a = tmp_path / "external-a.md"
    external_b = tmp_path / "external-b.md"
    external_a.write_text("## 第一章\n外部参考 A。\n", encoding="utf-8")
    external_b.write_text("## 第一章\n外部参考 B。\n", encoding="utf-8")

    external = prepare_book_sources(database, "scope-book", sources=[external_a])
    assert external["scope"] == DistillScope.EXTERNAL_REFERENCE.value
    handoff = create_distill_handoff(
        database,
        "scope-book",
        preparation_id=str(external["preparation_id"]),
        dimensions="worldbuilding",
    )
    task = json.loads(
        (Path(str(handoff["task_directory"])) / "input" / "task.json").read_text(
            encoding="utf-8"
        )
    )
    assert task["distill"]["scope"] == DistillScope.EXTERNAL_REFERENCE.value

    comparative = create_distill_handoff(
        database,
        "scope-book",
        sources=[external_a, external_b],
        mode="compare",
        dimensions="worldbuilding",
    )
    compare_task = json.loads(
        (Path(str(comparative["task_directory"])) / "input" / "task.json").read_text(
            encoding="utf-8"
        )
    )
    assert compare_task["distill"]["scope"] == DistillScope.COMPARATIVE_REFERENCE.value


def test_derived_edition_distill_freezes_effective_content(tmp_path: Path) -> None:
    source = tmp_path / "derived-source.md"
    source.write_text(
        "## 第一章 缺口\n主角缺少晶体。\n\n## 第二章 夜袭\n夜袭逼近。\n",
        encoding="utf-8",
    )
    added = add_book(
        LibraryAddOptions(
            book_id="derived-distill-book",
            title="Derived Distill",
            source=source,
            library_root=tmp_path / "library",
            confirm_order=True,
        )
    )
    database = Database(added.database)
    create_edition(database, "derived-distill-book", "derived-r1", "派生稿")
    spec = {
        "campaign_name": "修改第一章",
        "revision_kind": "correction",
        "intent": "修正第一章资源事实",
        "target_scope": {"chapter_ranges": [[1, 1]], "semantic_queries": []},
        "canon_changes": [],
        "entity_changes": [],
        "must_preserve": ["夜袭"],
        "must_change": ["晶体"],
        "forbidden_changes": [],
        "propagation_rules": [],
        "style_policy": {},
        "completion_policy": {},
    }
    campaign = create_revision_campaign(
        database, "derived-distill-book", spec, edition_id="derived-r1"
    )
    campaign_id = str(campaign["campaign_id"])
    impact = build_revision_impact(database, "derived-distill-book", campaign_id)
    complete_revision_impact_audit(
        database,
        "derived-distill-book",
        campaign_id,
        [{"impact_id": item["impact_id"], "status": "HANDLED"} for item in impact["items"]],
    )
    plan = build_revision_plan(database, "derived-distill-book", campaign_id)
    unit_id = str(plan["units"][0]["unit_id"])
    task = prepare_revision_draft_task(database, "derived-distill-book", campaign_id, unit_id)
    with database.connect() as connection:
        unit = connection.execute(
            "SELECT base_chapter_id, base_content_sha256, base_source_span_id "
            "FROM revision_units WHERE unit_id=?",
            (unit_id,),
        ).fetchone()
    output = {
        "task_type": "REVISION_DRAFT",
        "task_id": task["task_id"],
        "campaign_id": campaign_id,
        "unit_id": unit_id,
        "edition_id": "derived-r1",
        "base_chapter_id": unit["base_chapter_id"],
        "base_content_sha256": unit["base_content_sha256"],
        "replacement_title": "第一章 缺口",
        "replacement_markdown": "主角已经拥有晶体。",
        "change_map": [
            {
                "source_span_id": unit["base_source_span_id"],
                "old_quote": "缺少晶体",
                "new_quote": "拥有晶体",
                "change_class": "REQUIRED",
                "reason": "测试派生 Edition 有效正文",
            }
        ],
        "state_changes": [],
        "facts_superseded": [],
        "facts_added": [],
        "relationships_updated": [],
        "knowledge_updates": [],
        "invariant_evidence": {"夜袭": ["夜袭逼近"]},
        "required_change_evidence": {"晶体": ["拥有晶体"]},
        "stale_reference_checks": [],
        "character_fit_inputs": {},
        "style_fit_inputs": {},
        "notes": [],
    }
    output_path = tmp_path / "derived-revision.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    import_revision_draft(database, "derived-distill-book", output_path)
    validation = validate_revision_campaign(database, "derived-distill-book", campaign_id)
    assert validation["passed"], validation
    approve_revision_campaign(
        database,
        "derived-distill-book",
        campaign_id,
        confirmation="批准改写版本",
    )
    prepared = prepare_book_sources(database, "derived-distill-book", edition_id="derived-r1")
    normalized = Path(str(prepared["root"])) / "normalized"
    normalized_text = next(normalized.glob("*.txt")).read_text(encoding="utf-8")
    assert "拥有晶体" in normalized_text
    assert "缺少晶体" not in normalized_text
    assert prepared["scope"] == DistillScope.SELF_BOOK.value
    assert prepared["edition_id"] == "derived-r1"
    with database.connect() as connection:
        assert connection.execute(
            "SELECT active_edition_id FROM books WHERE book_id=?",
            ("derived-distill-book",),
        ).fetchone()[0] == "base"
