from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from novel_authoring.atlas.models import (
    AtlasAction,
    AtlasArtifactManifest,
    AtlasEvidence,
    AtlasGraph,
    AtlasNode,
    ConstraintLevel,
    FuturePossibilitySpace,
    HorizonBand,
    HorizonItem,
    HorizonKind,
    InformationStatus,
    ReadinessStatus,
    RollingHorizon,
    Spine,
    StoryAtlasStatus,
    WorldModelReadiness,
)
from novel_authoring.atlas.service import (
    AtlasError,
    get_atlas_overview,
    record_atlas_action,
    register_atlas,
    validate_stable_entity_ids,
)
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.ingest.service import ingest_book
from novel_authoring.planning.batch import (
    BatchError,
    BatchProvisionalState,
    BatchValidationSummary,
    complete_chunk,
    create_batch,
    get_batch_projection,
)
from novel_authoring.utils import json_dumps, sha256_bytes, sha256_file, utc_now
from novel_authoring.validation.models import VALIDATOR_NAMES
from novel_authoring.web.app import create_app
from novel_authoring.web.routes.atlas import public_atlas_overview
from novel_authoring.workflows.handoffs import (
    HandoffType,
    create_story_atlas_handoff,
)


def _setup_book(tmp_path: Path) -> tuple[Database, str, int, str, str]:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "novel.md").write_text(
        "# 第1章 灯塔\n主角看见一盏灯。\n\n"
        "# 第2章 电池\n主角把最后一枚电池保存下来。\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    ingest_book(
        book_id="atlas-book",
        title="Atlas 合成书",
        source_root=source_root,
        workspace_root=workspace,
        settings=load_settings(),
        confirm_order=True,
    )
    database = Database(workspace / "atlas-book" / "state.sqlite3")
    database.initialize()
    with database.connect() as connection:
        span = connection.execute(
            "SELECT span_id FROM source_spans WHERE book_id=? ORDER BY span_id LIMIT 1",
            ("atlas-book",),
        ).fetchone()
        chapter = connection.execute(
            "SELECT MAX(ordinal) AS ordinal FROM chapters WHERE book_id=?",
            ("atlas-book",),
        ).fetchone()
        content = connection.execute(
            "SELECT content_sha256 FROM chapters WHERE book_id=? ORDER BY ordinal DESC LIMIT 1",
            ("atlas-book",),
        ).fetchone()
    assert span is not None and chapter is not None and content is not None
    return (
        database,
        "atlas-book",
        int(chapter["ordinal"]),
        str(span["span_id"]),
        str(content["content_sha256"]),
    )


def _write_atlas(
    database: Database,
    book_id: str,
    current_chapter: int,
    source_span_id: str,
    effective_content_hash: str,
    *,
    atlas_id: str = "atlas-v1",
    atlas_version: int = 1,
    batch_target_chapters: int = 10,
) -> Path:
    with database.connect() as connection:
        book = connection.execute(
            "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
        from novel_authoring.canon.projection import projection_from_connection

        projection = projection_from_connection(connection, book_id, "base")
    assert book is not None
    root = (
        Path(str(book["workspace_root"]))
        / "editions"
        / "base"
        / "story_atlas"
    )
    (root / "graphs").mkdir(parents=True)
    (root / "future").mkdir(parents=True)

    character = AtlasNode(
        node_id="character-protagonist",
        name="主角",
        node_type="character",
        information_status=InformationStatus.CANON,
        constraint_level=ConstraintLevel.HARD,
        horizon=HorizonKind.CURRENT,
        evidence=AtlasEvidence(source_span_ids=[source_span_id]),
    )
    graph = AtlasGraph(
        graph_type="characters",
        atlas_version=atlas_version,
        nodes=[character],
    )
    graph_path = root / "graphs" / "characters.json"
    graph_path.write_text(
        json_dumps(graph.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )

    active = Spine(
        spine_id="spine-active",
        title="主动查证",
        kind="ACTIVE",
        structure_signature="active-a",
        summary="先验证灯塔规则，再扩大选择空间。",
        information_status=InformationStatus.INFERENCE,
        constraint_level=ConstraintLevel.SOFT,
        horizon=HorizonKind.NEAR,
    )
    alternative_a = Spine(
        spine_id="spine-alt-a",
        title="结盟路线",
        kind="ALTERNATIVE",
        structure_signature="alternative-a",
        summary="用关系换取短期资源。",
        information_status=InformationStatus.CANDIDATE,
        constraint_level=ConstraintLevel.SPECULATIVE,
        horizon=HorizonKind.FAR,
    )
    alternative_b = Spine(
        spine_id="spine-alt-b",
        title="独行路线",
        kind="ALTERNATIVE",
        structure_signature="alternative-b",
        summary="保留秘密但承受更高维护成本。",
        information_status=InformationStatus.CANDIDATE,
        constraint_level=ConstraintLevel.SPECULATIVE,
        horizon=HorizonKind.FAR,
    )
    future = FuturePossibilitySpace(
        active_spine=active,
        alternative_spines=[alternative_a, alternative_b],
        wildcard_possibilities=[],
        open_design_spaces=["灯塔信号的来源仍未知"],
    )
    (root / "future" / "active_spine.yaml").write_text(
        yaml.safe_dump(active.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (root / "future" / "alternative_spines.yaml").write_text(
        yaml.safe_dump(
            {
                "alternative_spines": [
                    item.model_dump(mode="json") for item in future.alternative_spines
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "future" / "wildcard_possibilities.yaml").write_text(
        "wildcard_possibilities: []\n", encoding="utf-8"
    )
    (root / "future" / "open_design_spaces.yaml").write_text(
        yaml.safe_dump(
            {"open_design_spaces": future.open_design_spaces},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    far_end = max(current_chapter * 2, batch_target_chapters * 2)
    horizon = RollingHorizon(
        horizon_id="horizon-v1",
        horizon_hash="horizon-hash-v1",
        atlas_id=atlas_id,
        atlas_version=atlas_version,
        atlas_content_hash="pending",
        base_projection_hash=projection.sha256(),
        current_chapter_ordinal=current_chapter,
        current=HorizonBand(
            horizon=HorizonKind.CURRENT,
            start_chapter=current_chapter,
            end_chapter=current_chapter,
        ),
        near=HorizonBand(
            horizon=HorizonKind.NEAR,
            start_chapter=current_chapter + 1,
            end_chapter=current_chapter + 5,
        ),
        mid=HorizonBand(
            horizon=HorizonKind.MID,
            start_chapter=current_chapter + 6,
            end_chapter=current_chapter + 10,
        ),
        far=HorizonBand(horizon=HorizonKind.FAR, end_chapter=far_end),
        required_far_end_chapter=far_end,
    )
    non_horizon_paths = [
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file()
    ]
    non_horizon_hashes = {
        path: sha256_file(root / path) for path in non_horizon_paths
    }
    atlas_content_hash = sha256_bytes(
        json_dumps(
            {path: non_horizon_hashes[path] for path in sorted(non_horizon_hashes)}
        ).encode()
    )
    horizon = horizon.model_copy(update={"atlas_content_hash": atlas_content_hash})
    (root / "future" / "rolling_horizon.yaml").write_text(
        yaml.safe_dump(horizon.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    artifact_paths = [
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file()
    ]
    artifact_hashes = {path: sha256_file(root / path) for path in artifact_paths}
    source_manifest = Path(str(book["workspace_root"])) / "source_manifest.json"
    manifest = AtlasArtifactManifest(
        atlas_id=atlas_id,
        atlas_version=atlas_version,
        book_id=book_id,
        edition_id="base",
        base_event_seq=projection.through_event_seq,
        base_projection_hash=projection.sha256(),
        source_manifest_sha256=sha256_file(source_manifest),
        effective_content_sha256=effective_content_hash,
        atlas_content_hash=atlas_content_hash,
        horizon_id=horizon.horizon_id,
        horizon_hash=horizon.horizon_hash,
        created_at=utc_now(),
        status=StoryAtlasStatus.ACTIVE,
        readiness=WorldModelReadiness(
            status=ReadinessStatus.READY,
            current_boundary_confirmed=True,
            core_rules_covered=True,
            protagonist_state_confirmed=True,
            main_threads_connected=True,
            source_coverage=1.0,
            graph_coverage=1.0,
        ),
        current_chapter_ordinal=current_chapter,
        batch_target_chapters=batch_target_chapters,
        far_horizon_end_chapter=far_end,
        artifact_paths=artifact_paths,
        artifact_hashes=artifact_hashes,
    )
    (root / "atlas_manifest.json").write_text(
        json_dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def _validator_summary(start: int, end: int) -> dict[str, object]:
    return {
        "chapters": [
            {
                "chapter_ordinal": ordinal,
                "boundary_hash": f"boundary-{ordinal}",
                "contract_id": f"contract-{ordinal}",
                "validation_report_ids": [
                    f"report-{ordinal}-{index}" for index in range(10)
                ],
                "validator_names": list(VALIDATOR_NAMES),
                "passed": True,
            }
            for ordinal in range(start, end + 1)
        ],
        "passed": True,
    }


def test_story_atlas_contracts_source_evidence_and_immutable_registration(
    tmp_path: Path,
) -> None:
    database, book_id, current, span_id, content_hash = _setup_book(tmp_path)
    root = _write_atlas(database, book_id, current, span_id, content_hash)

    with pytest.raises(ValueError, match="source evidence"):
        AtlasNode(
            node_id="bad",
            name="bad",
            node_type="character",
            information_status=InformationStatus.CANON,
            constraint_level=ConstraintLevel.HARD,
            horizon=HorizonKind.CURRENT,
            evidence=AtlasEvidence(chapter_ids=["chapter-1"]),
        )
    with pytest.raises(ValueError, match="FAR"):
        HorizonItem(
            item_id="far-chapter",
            title="bad",
            summary="bad",
            horizon=HorizonKind.FAR,
            information_status=InformationStatus.CANDIDATE,
            constraint_level=ConstraintLevel.SPECULATIVE,
            chapter_ordinal=3,
        )
    with pytest.raises(ValueError, match="结构差异"):
        FuturePossibilitySpace(
            active_spine=Spine(
                spine_id="active",
                title="active",
                kind="ACTIVE",
                structure_signature="same",
                summary="x",
                information_status=InformationStatus.INFERENCE,
                constraint_level=ConstraintLevel.SOFT,
                horizon=HorizonKind.NEAR,
            ),
            alternative_spines=[
                Spine(
                    spine_id="a",
                    title="a",
                    kind="ALTERNATIVE",
                    structure_signature="same",
                    summary="x",
                    information_status=InformationStatus.CANDIDATE,
                    constraint_level=ConstraintLevel.SPECULATIVE,
                    horizon=HorizonKind.FAR,
                ),
                Spine(
                    spine_id="b",
                    title="b",
                    kind="ALTERNATIVE",
                    structure_signature="same",
                    summary="x",
                    information_status=InformationStatus.CANDIDATE,
                    constraint_level=ConstraintLevel.SPECULATIVE,
                    horizon=HorizonKind.FAR,
                ),
            ],
        )
    with pytest.raises(ValueError, match="creative grammar"):
        AtlasGraph(
            graph_type="abilities",
            atlas_version=1,
            nodes=[
                AtlasNode(
                    node_id="ability-candidate",
                    name="新能力",
                    node_type="ability",
                    information_status=InformationStatus.CANDIDATE,
                    constraint_level=ConstraintLevel.SPECULATIVE,
                    horizon=HorizonKind.NEAR,
                )
            ],
        )
    with pytest.raises(ValueError, match="坐标"):
        AtlasGraph(
            graph_type="regions",
            atlas_version=1,
            nodes=[
                AtlasNode(
                    node_id="region",
                    name="北岸",
                    node_type="region",
                    information_status=InformationStatus.INFERENCE,
                    constraint_level=ConstraintLevel.SOFT,
                    horizon=HorizonKind.NEAR,
                    payload={"lat": 48.8},
                )
            ],
        )

    registered = register_atlas(database, book_id, "base", root=root)
    assert registered["index"]["atlas_version"] == 1
    assert registered["readiness"]["status"] == "READY_WITH_GAPS"
    assert get_atlas_overview(database, book_id, "base")["errors"] == []
    with database.connect() as connection:
        stored_root = Path(
            str(
                connection.execute(
                    "SELECT artifact_root FROM story_atlases WHERE atlas_id=?",
                    ("atlas-v1",),
                ).fetchone()[0]
            )
        )
    assert stored_root != root.resolve()
    assert stored_root.is_dir()

    with database.connect() as connection:
        event_count = connection.execute(
            "SELECT COUNT(*) FROM events WHERE book_id=?", (book_id,)
        ).fetchone()[0]
    assert event_count == 0
    record_atlas_action(
        database,
        book_id,
        "base",
        AtlasAction(action_type="ACCEPT_ATLAS"),
        expected_atlas_version=1,
        expected_manifest_hash=registered["index"]["artifact_manifest_sha256"],
    )
    with database.connect() as connection:
        assert connection.execute(
            "SELECT author_accepted FROM story_atlases WHERE atlas_id=?", ("atlas-v1",)
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE book_id=?", (book_id,)
        ).fetchone()[0] == 0

    manifest_path = root / "atlas_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["notes"] = ["attempted overwrite"]
    manifest_path.write_text(json_dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(AtlasError, match="不可覆盖"):
        register_atlas(database, book_id, "base", root=root)

    old = AtlasGraph(
        graph_type="characters",
        atlas_version=1,
        nodes=[
            AtlasNode(
                node_id="stable-character",
                name="主角",
                node_type="character",
                information_status=InformationStatus.CANON,
                constraint_level=ConstraintLevel.HARD,
                horizon=HorizonKind.CURRENT,
                evidence=AtlasEvidence(source_span_ids=[span_id]),
            )
        ],
    )
    new = old.model_copy(
        update={
            "nodes": [
                old.nodes[0].model_copy(update={"node_id": "changed-id"})
            ]
        }
    )
    assert validate_stable_entity_ids(old, new)


def test_batch_marks_input_drift_stale_and_blocks_continuation(tmp_path: Path) -> None:
    database, book_id, current, span_id, content_hash = _setup_book(tmp_path)
    root = _write_atlas(
        database,
        book_id,
        current,
        span_id,
        content_hash,
        batch_target_chapters=10,
    )
    register_atlas(database, book_id, "base", root=root)
    created = create_batch(
        database,
        book_id,
        target_chapter_count=10,
        edition_id="base",
    )

    with database.connect() as connection:
        workspace_root = Path(
            str(
                connection.execute(
                    "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
                ).fetchone()[0]
            )
        )
    source_manifest = workspace_root / "source_manifest.json"
    source_manifest.write_text(
        source_manifest.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    projection = get_batch_projection(database, created["batch_id"])
    assert projection.status.value == "STALE"
    assert projection.state["stale_reasons"]
    with pytest.raises(BatchError, match="STALE"):
        complete_chunk(
            database,
            created["batch_id"],
            1,
            provisional_state=projection.state,
            validator_summary={},
        )


def test_batch_is_chunked_typed_provisional_checkpointed_and_never_canon(
    tmp_path: Path,
) -> None:
    database, book_id, current, span_id, content_hash = _setup_book(tmp_path)
    root = _write_atlas(
        database,
        book_id,
        current,
        span_id,
        content_hash,
        batch_target_chapters=10,
    )
    register_atlas(database, book_id, "base", root=root)
    created = create_batch(
        database,
        book_id,
        target_chapter_count=10,
        edition_id="base",
    )
    plan = created["plan"]
    assert len(plan["chunks"]) == 2
    assert plan["chunks"][0]["end_chapter_ordinal"] + 1 == plan["chunks"][1][
        "start_chapter_ordinal"
    ]
    assert plan["atlas_id"] == "atlas-v1"
    assert plan["required_far_end_chapter"] == 20

    with pytest.raises(BatchError, match="合同无效"):
        complete_chunk(
            database,
            created["batch_id"],
            1,
            provisional_state={"canon_committed": True},
            validator_summary={},
        )

    projection = get_batch_projection(database, created["batch_id"])
    state = BatchProvisionalState.model_validate(projection.state).model_dump(mode="json")
    first = complete_chunk(
        database,
        created["batch_id"],
        1,
        provisional_state=state,
        validator_summary=_validator_summary(current + 1, current + 5),
    )
    assert first["batch_projection"]["status"] == "RUNNING"
    projection = get_batch_projection(database, created["batch_id"])
    assert projection.status.value == "RUNNING"
    second_state = BatchProvisionalState.model_validate(projection.state).model_dump(mode="json")
    complete_chunk(
        database,
        created["batch_id"],
        2,
        provisional_state=second_state,
        validator_summary=_validator_summary(current + 6, current + 10),
    )
    final_projection = get_batch_projection(database, created["batch_id"])
    assert final_projection.status.value == "BATCH_VALIDATED"
    with database.connect() as connection:
        checkpoint_count = connection.execute(
            "SELECT COUNT(*) FROM batch_checkpoints WHERE batch_id=?",
            (created["batch_id"],),
        ).fetchone()[0]
        event_count = connection.execute(
            "SELECT COUNT(*) FROM events WHERE book_id=?", (book_id,)
        ).fetchone()[0]
        chunk = connection.execute(
            "SELECT provisional_state_hash, boundary_hash, contract_ids_json, "
            "validation_report_ids_json FROM batch_chunk_states "
            "WHERE batch_id=? AND chunk_order=2",
            (created["batch_id"],),
        ).fetchone()
    assert checkpoint_count == 1
    assert event_count == 0
    assert chunk is not None and chunk["provisional_state_hash"]
    assert json.loads(str(chunk["contract_ids_json"]))
    assert len(json.loads(str(chunk["validation_report_ids_json"]))) == 50
    assert BatchValidationSummary.model_validate(_validator_summary(current + 1, current + 5))


def test_atlas_web_scope_and_atlas_handoff_anchor(tmp_path: Path) -> None:
    database, book_id, current, span_id, content_hash = _setup_book(tmp_path)
    root = _write_atlas(database, book_id, current, span_id, content_hash)
    registered = register_atlas(database, book_id, "base", root=root)
    public = public_atlas_overview(database, book_id, "base")
    assert "artifact_root" not in public["index"]
    assert public["index"]["atlas_id"] == "atlas-v1"

    handoff = create_story_atlas_handoff(
        database,
        book_id,
        handoff_type=HandoffType.STORY_ATLAS_BOOTSTRAP,
        requested_stage="ATLAS_BOOTSTRAP",
        edition_id="base",
    )
    with database.connect() as connection:
        row = connection.execute(
            "SELECT atlas_id, atlas_version, atlas_manifest_hash, horizon_hash "
            "FROM workflow_handoffs WHERE handoff_id=?",
            (handoff["handoff_id"],),
        ).fetchone()
    assert row is not None
    assert row["atlas_id"] == registered["index"]["atlas_id"]
    assert row["atlas_version"] == 1
    assert row["atlas_manifest_hash"] == registered["index"]["artifact_manifest_sha256"]
    assert row["horizon_hash"] == "horizon-hash-v1"

    app = create_app(database, book_id=book_id)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get(f"/api/books/{book_id}/editions/base/atlas")
    assert response.status_code == 200
    assert response.json()["index"]["atlas_id"] == "atlas-v1"
    csrf = app.state.csrf_token
    action_response = client.post(
        f"/api/books/{book_id}/editions/base/atlas/actions",
        headers={"X-CSRF-Token": csrf},
        json={
            "action_type": "ADD_REVIEW_QUEUE",
            "target_id": "character-protagonist",
            "expected_atlas_id": "atlas-v1",
            "expected_atlas_version": 1,
            "expected_manifest_hash": registered["index"]["artifact_manifest_sha256"],
            "payload": {"reason": "合成测试"},
        },
    )
    assert action_response.status_code == 200
    assert client.post(
        f"/api/books/{book_id}/editions/base/atlas/actions",
        json={"action_type": "ADD_REVIEW_QUEUE", "target_id": "x"},
    ).status_code == 403
