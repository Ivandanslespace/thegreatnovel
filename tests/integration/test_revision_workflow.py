from __future__ import annotations

import json
from pathlib import Path

import pytest

from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.edition import activate_edition, create_edition
from novel_authoring.ingest.service import ingest_book
from novel_authoring.revision import (
    RevisionSpec,
    approve_revision_campaign,
    build_revision_impact,
    build_revision_plan,
    complete_revision_impact_audit,
    create_revision_campaign,
    import_revision_draft,
    prepare_revision_draft_task,
    validate_revision_campaign,
)
from novel_authoring.revision.service import RevisionWorkflowError
from novel_authoring.workflows.edition_export import export_edition


def _setup(tmp_path: Path) -> tuple[Database, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "book.md").write_text(
        "## 第一章 缺口\n主角缺少晶体。\n\n## 第二章 夜袭\n夜袭逼近。\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="revision-book",
        title="改写测试",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
    )
    database = Database(workspace / "revision-book" / "state.sqlite3")
    create_edition(database, "revision-book", "edition-r1", "改写候选")
    return database, workspace


def _spec() -> dict[str, object]:
    return {
        "campaign_name": "修正晶体缺口",
        "revision_kind": "correction",
        "intent": "把第一章错误的资源事实改为已获得晶体",
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


def _prepare_campaign(database: Database) -> tuple[str, str, dict[str, object]]:
    campaign = create_revision_campaign(database, "revision-book", _spec(), edition_id="edition-r1")
    impact = build_revision_impact(database, "revision-book", str(campaign["campaign_id"]))
    complete_revision_impact_audit(
        database,
        "revision-book",
        str(campaign["campaign_id"]),
        [{"impact_id": item["impact_id"], "status": "HANDLED"} for item in impact["items"]],
    )
    plan = build_revision_plan(database, "revision-book", str(campaign["campaign_id"]))
    unit_id = str(plan["units"][0]["unit_id"])
    task = prepare_revision_draft_task(
        database, "revision-book", str(campaign["campaign_id"]), unit_id
    )
    return str(campaign["campaign_id"]), unit_id, task


def _write_output(
    database: Database, tmp_path: Path, campaign_id: str, unit_id: str, task: dict[str, object]
) -> Path:
    with database.connect() as connection:
        unit = connection.execute(
            "SELECT base_chapter_id, base_content_sha256 FROM revision_units WHERE unit_id=?",
            (unit_id,),
        ).fetchone()
    output = {
        "task_type": "REVISION_DRAFT",
        "task_id": task["task_id"],
        "campaign_id": campaign_id,
        "unit_id": unit_id,
        "edition_id": "edition-r1",
        "base_chapter_id": unit["base_chapter_id"],
        "base_content_sha256": unit["base_content_sha256"],
        "replacement_title": "缺口",
        "replacement_markdown": "主角已经拥有晶体。",
        "change_map": [
            {
                "source_span_id": "source-span",
                "old_quote": "缺少晶体",
                "new_quote": "拥有晶体",
                "change_class": "REQUIRED",
                "reason": "修正明确错误",
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
        "notes": ["保留原章节叙事视角"],
    }
    path = tmp_path / "revision-output.json"
    path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    return path


def test_revision_spec_rejects_unknown_fields() -> None:
    value = _spec()
    value["unknown"] = True
    with pytest.raises(ValueError):
        RevisionSpec.model_validate(value)


def test_revision_workflow_approval_then_separate_activation(tmp_path: Path) -> None:
    database, workspace = _setup(tmp_path)
    campaign_id, unit_id, task = _prepare_campaign(database)
    output_path = _write_output(database, tmp_path, campaign_id, unit_id, task)
    import_revision_draft(database, "revision-book", output_path)
    assert validate_revision_campaign(database, "revision-book", campaign_id)["passed"]
    committed = approve_revision_campaign(
        database,
        "revision-book",
        campaign_id,
        confirmation="批准改写版本",
    )
    assert committed["activation_required"] is True
    with database.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM chapter_variants WHERE campaign_id=? AND active=1",
                (campaign_id,),
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT status FROM editions WHERE edition_id='edition-r1'"
            ).fetchone()[0]
            == "VALIDATED"
        )
    with pytest.raises(RevisionWorkflowError):
        approve_revision_campaign(
            database, "revision-book", campaign_id, confirmation="批准改写版本"
        )
    activated = activate_edition(
        database,
        "revision-book",
        "edition-r1",
        confirmation="启用改写版本",
    )
    assert activated.status.value == "ACTIVE"
    exported = export_edition(database, "revision-book", "edition-r1")
    export_dir = Path(str(exported["path"]))
    assert {item for item in exported["files"].values()} <= {
        path.name for path in export_dir.iterdir()
    }
    assert "主角已经拥有晶体" in (export_dir / "complete_edition.md").read_text(encoding="utf-8")
    assert (workspace / "revision-book" / "editions" / "edition-r1").exists()


def test_revision_approval_requires_exact_phrase(tmp_path: Path) -> None:
    database, _ = _setup(tmp_path)
    campaign_id, unit_id, task = _prepare_campaign(database)
    import_revision_draft(
        database, "revision-book", _write_output(database, tmp_path, campaign_id, unit_id, task)
    )
    validate_revision_campaign(database, "revision-book", campaign_id)
    with pytest.raises(RevisionWorkflowError, match="批准改写版本"):
        approve_revision_campaign(
            database, "revision-book", campaign_id, confirmation="批准写入正史"
        )


def test_revision_event_projection_isolated_from_base(tmp_path: Path) -> None:
    database, _ = _setup(tmp_path)
    from novel_authoring.canon.events import EventStatus, EventStore
    from novel_authoring.canon.projection import rebuild_projection
    from novel_authoring.domain.models import InformationStatus

    EventStore(database).append(
        book_id="revision-book",
        edition_id="edition-r1",
        event_type="FACT_ASSERTED",
        aggregate_type="fact",
        aggregate_id="derived-fact",
        payload={"fact_id": "derived-fact", "predicate": "state", "object": "new"},
        source_kind="TEST",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
    )
    assert (
        "derived-fact"
        not in rebuild_projection(database, "revision-book", edition_id="base", persist=False).facts
    )
    assert (
        "derived-fact"
        in rebuild_projection(
            database, "revision-book", edition_id="edition-r1", persist=False
        ).facts
    )
