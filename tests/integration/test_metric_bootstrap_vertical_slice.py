from __future__ import annotations

import json
from pathlib import Path

import pytest

from novel_authoring.atlas.offline import export_snapshot
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.initialization.metrics import (
    import_metric_bootstrap,
    metric_bootstrap_status,
    prepare_metric_bootstrap,
)
from novel_authoring.initialization.service import (
    ArcExtractionOutput,
    InitializationError,
    create_initialization,
    refresh_initialization,
)
from novel_authoring.web.routes.pages import chapter_context


def _book(tmp_path: Path, count: int = 24) -> tuple[Database, str]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "novel.md").write_text(
        "".join(
            f"# 第{ordinal}章 章节{ordinal}\n主角继续观察与选择。\n\n"
            for ordinal in range(1, count + 1)
        ),
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="init-book",
        title="初始化测试书",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
        confirm_order=True,
    )
    return Database(workspace / "init-book" / "state.sqlite3"), "init-book"


def _write_empty_arc_outputs(root: Path, initialization_id: str) -> None:
    arc_manifest = json.loads((root / "arc_manifest.json").read_text(encoding="utf-8"))
    for arc in arc_manifest["arcs"]:
        output = ArcExtractionOutput(
            initialization_id=initialization_id,
            arc_id=str(arc["arc_id"]),
            chapter_semantic_features=[],
        )
        output_path = root / "arc_outputs" / str(arc["arc_id"]) / "output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def test_empty_semantic_features_are_not_counted_as_chapter_coverage(tmp_path: Path) -> None:
    database, book_id = _book(tmp_path, count=4)
    initialization = create_initialization(database, book_id, edition_id="base")
    root = Path(initialization["root"])
    _write_empty_arc_outputs(root, initialization["initialization_id"])
    (root / "metrics").mkdir(parents=True, exist_ok=True)
    (root / "metrics" / "initialization_metric_bootstrap.json").write_text(
        json.dumps({"legacy": True}), encoding="utf-8"
    )

    refreshed = refresh_initialization(
        database,
        book_id,
        edition_id="base",
        initialization_id=initialization["initialization_id"],
    )

    assert refreshed["readiness"]["source_mapping_coverage"] == 1.0
    assert refreshed["readiness"]["arc_output_coverage"] == 1.0
    assert refreshed["readiness"]["chapter_semantic_feature_coverage"] == 0.0
    assert refreshed["readiness"]["metric_bootstrap_status"] == "NOT_READY"
    assert refreshed["readiness"]["status"] == "BLOCKED"


def test_metric_bootstrap_import_is_evidence_bearing_and_idempotent(tmp_path: Path) -> None:
    database, book_id = _book(tmp_path, count=4)
    initialization = create_initialization(database, book_id, edition_id="base")
    root = Path(initialization["root"])
    _write_empty_arc_outputs(root, initialization["initialization_id"])

    prepared = prepare_metric_bootstrap(
        database,
        book_id,
        edition_id="base",
        initialization_id=initialization["initialization_id"],
        recent_detailed_window=4,
    )
    manifest_path = root / "metrics" / "metric_bootstrap_manifest.json"
    records_path = root / "metrics" / "chapter_metric_observations.jsonl"
    assert manifest_path.is_file()
    assert records_path.is_file()
    assert prepared["record_count"] == 4
    assert prepared["observation_count"] > 0

    before = metric_bootstrap_status(
        database,
        book_id,
        edition_id="base",
        initialization_id=initialization["initialization_id"],
    )
    assert before["status"] == "NOT_READY"
    assert before["metric_observation_count"] == 0

    imported = import_metric_bootstrap(
        database,
        book_id,
        edition_id="base",
        initialization_id=initialization["initialization_id"],
        input_path=records_path,
    )
    observation_count = int(database.scalar("SELECT COUNT(*) FROM metric_observations") or 0)
    evidence_count = int(database.scalar("SELECT COUNT(*) FROM metric_evidence_links") or 0)
    assert imported["observations_added"] == observation_count > 0
    assert evidence_count > 0
    assert database.scalar(
        "SELECT COUNT(*) FROM metric_observations WHERE source_kind='SEMANTIC_ESTIMATE'"
    ) == observation_count

    latest_chapter = database.scalar(
        "SELECT chapter_id FROM chapters WHERE book_id=? ORDER BY ordinal DESC LIMIT 1",
        (book_id,),
    )
    with database.connect() as run:
        row = run.execute(
            "SELECT status, completeness FROM metric_runs WHERE book_id=? AND edition_id='base' "
            "AND scope_type='CHAPTER' AND scope_id=? AND invalidated_at IS NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (book_id, latest_chapter),
        ).fetchone()
    assert row is not None
    assert row["status"] == "PROVISIONAL"
    assert float(row["completeness"]) > 0

    context = chapter_context(database, book_id, "base", str(latest_chapter))
    assert context["metric_metadata"]["observation_count"] > 0
    assert context["metric_metadata"]["semantic_estimate_count"] > 0
    assert context["metric_metadata"]["evidence_count"] > 0
    assert all(item["analysis_state"] != "NOT_ANALYZED" for item in context["metrics"])

    after = metric_bootstrap_status(
        database,
        book_id,
        edition_id="base",
        initialization_id=initialization["initialization_id"],
    )
    assert after["status"] == "COMPLETE"
    assert after["coverage"]["recent_detailed_metric_coverage"] == 1.0
    assert after["coverage"]["current_chapter_metric_coverage"] == 1.0

    repeated = import_metric_bootstrap(
        database,
        book_id,
        edition_id="base",
        initialization_id=initialization["initialization_id"],
        input_path=records_path,
    )
    assert repeated["observations_added"] == 0
    assert repeated["records_skipped_idempotent"] > 0
    assert (
        int(database.scalar("SELECT COUNT(*) FROM metric_observations") or 0)
        == observation_count
    )

    snapshot = export_snapshot(
        database,
        book_id,
        edition_id="base",
        output_root=tmp_path / "snapshot",
    )
    snapshot_root = Path(snapshot["output_root"])
    assert (snapshot_root / "metrics" / "metric_runs.json").is_file()
    assert (snapshot_root / "metrics" / "metric_run_results.json").is_file()
    assert (snapshot_root / "metrics" / "metric_observations.json").is_file()
    assert (snapshot_root / "metrics" / "metric_evidence_links.json").is_file()
    html = (snapshot_root / "index.html").read_text(encoding="utf-8")
    assert "Observation history" in html
    assert "Evidence" in html
    assert "fetch(" not in html


def test_metric_bootstrap_rejects_record_hash_drift(tmp_path: Path) -> None:
    database, book_id = _book(tmp_path, count=2)
    initialization = create_initialization(database, book_id, edition_id="base")
    root = Path(initialization["root"])
    _write_empty_arc_outputs(root, initialization["initialization_id"])
    prepare_metric_bootstrap(
        database,
        book_id,
        edition_id="base",
        initialization_id=initialization["initialization_id"],
        recent_detailed_window=2,
    )
    records_path = root / "metrics" / "chapter_metric_observations.jsonl"
    lines = records_path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    payload["content_sha256"] = "0" * 64
    records_path.write_text(
        "\n".join([json.dumps(payload, ensure_ascii=False), *lines[1:]]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(InitializationError, match="JSONL|hash"):
        import_metric_bootstrap(
            database,
            book_id,
            edition_id="base",
            initialization_id=initialization["initialization_id"],
            input_path=records_path,
        )
