from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novel_authoring.config import Settings, load_settings
from novel_authoring.db.database import Database
from novel_authoring.edition import create_edition, get_edition
from novel_authoring.ingest.service import ingest_book
from novel_authoring.metrics.models import ObservationSourceKind
from novel_authoring.metrics.registry import load_registry
from novel_authoring.metrics.segments import list_segments, rebuild_segments
from novel_authoring.metrics.service import (
    MetricObservationService,
    MetricsAssembler,
    ObservationInput,
)
from novel_authoring.planning.aggregates import build_planning_aggregate
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now
from novel_authoring.workflows.handoffs import (
    HandoffStatus,
    HandoffType,
    claim_handoff,
    create_continuation_handoff,
    update_handoff_status,
)

DEMO_BOOK_ID = "demo-author-workbench"
DEMO_EDITION_ID = "demo-variant"


def _demo_text() -> str:
    return """序章 灯塔日志

这是一组仅用于 Author Workbench 验收的合成文本。

第1章 雨线

林岚在废弃灯塔里记录潮汐，发现无线电每天在同一秒短暂亮起。她没有打开舱门，而是先把电池分成两份。

第2章 低潮

雨水淹过旧仓库，远处的浮标发出三次短响。林岚用手写地图标出安全路线，也记下了一个尚未解释的符号。

第3章 回声

无线电终于传来一个孩子的声音：“不要相信北面的灯。”林岚必须决定是否回应，灯塔外的潮声却提前改变了节拍。

第4章 选择

她把最后一枚电池交给信号接收器，换来一段不完整的坐标。坐标指向灯塔地下，而门锁上留下了新鲜的盐痕。
"""


def _number_for_component(component: Any) -> int | float:
    if component.minimum is not None and component.maximum is not None:
        if component.maximum <= 1:
            return float(round((component.minimum + component.maximum) / 2, 2))
        return float(round((component.minimum + component.maximum) / 2, 2))
    return 0.5


def _chapter_observations(
    database: Database,
    book_id: str,
    chapter_id: str,
    content_hash: str,
    segment_id: str,
    quote: str,
    *,
    add_conflict: bool = True,
) -> list[str]:
    registry = load_registry()
    service = MetricObservationService(database, registry)
    ids: list[str] = []
    special_agency = {
        "value_balance": 0.7,
        "consequence_difference": 0.8,
        "information_adequacy": 0.6,
        "opportunity_cost": 0.75,
        "long_term_effect": 0.65,
    }
    for metric_id, definition in registry.metrics.items():
        if definition.scope.value != "CHAPTER":
            continue
        for component_id, component in definition.components.items():
            if metric_id == "pressure" and component_id == "social_conflict":
                # Keep one missing required input visible in the demo.
                continue
            source = (
                ObservationSourceKind.SEMANTIC_ESTIMATE
                if ObservationSourceKind.SEMANTIC_ESTIMATE.value
                in {item.value for item in component.allowed_source_kinds}
                else ObservationSourceKind.DETERMINISTIC
            )
            if component_id == "agency":
                value: Any = special_agency
            elif component.value_type == "number":
                value = _number_for_component(component)
            else:
                continue
            evidence_links: list[dict[str, Any]] = []
            if source == ObservationSourceKind.SEMANTIC_ESTIMATE:
                evidence_links = [
                    {
                        "segment_id": segment_id,
                        "contribution_kind": "SEMANTIC_SUPPORT",
                        "direction": "SUPPORTS",
                        "strength": 0.8,
                        "confidence": 0.75,
                        "evidence_quote": quote,
                        "rationale": "合成演示证据",
                    }
                ]
            ids.append(
                service.append(
                    ObservationInput(
                        book_id=book_id,
                        edition_id="base",
                        scope_type="CHAPTER",
                        scope_id=chapter_id,
                        metric_id=metric_id,
                        component_id=component_id,
                        value=value,
                        source_kind=source,
                        confidence=(
                            0.75
                            if source == ObservationSourceKind.SEMANTIC_ESTIMATE
                            else 1.0
                        ),
                        reason="合成 Author Workbench 演示输入",
                        chapter_id=chapter_id,
                        effective_content_sha256=content_hash,
                        evidence_links=evidence_links,
                    )
                )
            )
    if add_conflict:
        # An intentional same-priority disagreement for the Web dispute panel.
        for value in (35, 65):
            ids.append(
                service.append(
                    ObservationInput(
                        book_id=book_id,
                        edition_id="base",
                        scope_type="CHAPTER",
                        scope_id=chapter_id,
                        metric_id="pressure",
                        component_id="uncertainty",
                        value=value,
                        source_kind=ObservationSourceKind.SEMANTIC_ESTIMATE,
                        confidence=0.7,
                        reason="合成演示冲突观察",
                        chapter_id=chapter_id,
                        effective_content_sha256=content_hash,
                        evidence_links=[
                            {
                                "segment_id": segment_id,
                                "contribution_kind": "SEMANTIC_SUPPORT",
                                "direction": "CONTRADICTS",
                                "strength": 0.6,
                                "confidence": 0.7,
                                "evidence_quote": quote,
                                "rationale": "故意保留的冲突",
                            }
                        ],
                    )
                )
            )
    return ids


def _insert_demo_variant(database: Database, book_id: str, edition_id: str) -> None:
    with database.connect() as connection:
        chapter = connection.execute(
            "SELECT * FROM chapters WHERE book_id=? AND edition_id='base' "
            "ORDER BY ordinal LIMIT 1",
            (book_id,),
        ).fetchone()
        if chapter is None:
            raise ValueError("demo 缺少 base 章节")
        source_span = connection.execute(
            "SELECT span_id FROM source_spans WHERE chapter_id=? AND kind='chapter' "
            "ORDER BY span_id LIMIT 1",
            (str(chapter["chapter_id"]),),
        ).fetchone()
        if source_span is None:
            raise ValueError("demo 缺少 base source span")
        campaign_id = stable_id("demo-campaign", book_id, edition_id)
        unit_id = stable_id("demo-unit", book_id, edition_id, str(chapter["chapter_id"]))
        variant_id = stable_id("demo-variant", book_id, edition_id, str(chapter["chapter_id"]))
        now = utc_now()
        edition = get_edition(database, book_id, edition_id)
        connection.execute(
            """
            INSERT OR IGNORE INTO revision_campaigns(
                campaign_id, book_id, edition_id, campaign_name, revision_kind,
                author_intent, target_scope_json, canon_changes_json, entity_changes_json,
                invariants_json, must_change_json, forbidden_changes_json,
                propagation_rules_json, style_policy_json, completion_policy_json,
                base_event_seq, base_projection_hash, source_manifest_sha256, status, created_at
            ) VALUES (?, ?, ?, ?, 'DEMO', ?, '{}', '[]', '[]', '[]', '[]', '[]',
                      '[]', '{}', '{}', ?, ?, ?, 'VALIDATED', ?)
            """,
            (
                campaign_id,
                book_id,
                edition_id,
                "合成变体演示 Campaign",
                "只替换一段合成正文，用于验证 derived edition 隔离。",
                edition.base_event_seq,
                edition.base_projection_hash,
                edition.source_manifest_sha256,
                now,
            ),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO revision_units(
                unit_id, campaign_id, book_id, edition_id, unit_order, base_chapter_id,
                base_source_span_id, base_content_sha256, original_heading, original_content,
                status, created_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, 'PLANNED', ?)
            """,
            (
                unit_id,
                campaign_id,
                book_id,
                edition_id,
                str(chapter["chapter_id"]),
                str(source_span["span_id"]),
                str(chapter["content_sha256"]),
                str(chapter["raw_heading"]),
                str(chapter["content"]),
                now,
            ),
        )
        replacement = "变体版的雨线在灯塔玻璃上折成两道，林岚先检查电池，再把新坐标写进地图。"
        connection.execute(
            """
            INSERT OR IGNORE INTO chapter_variants(
                variant_id, book_id, edition_id, campaign_id, unit_id, base_chapter_id,
                base_source_span_id, base_content_sha256, title, replacement_content,
                replacement_content_sha256, status, active, created_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'VALIDATED', 1, ?, ?)
            """,
            (
                variant_id,
                book_id,
                edition_id,
                campaign_id,
                unit_id,
                str(chapter["chapter_id"]),
                str(source_span["span_id"]),
                str(chapter["content_sha256"]),
                "雨线·变体",
                replacement,
                sha256_bytes(replacement.encode("utf-8")),
                now,
                now,
            ),
        )


def _insert_demo_state(database: Database, book_id: str) -> str:
    with database.connect() as connection:
        chapters = connection.execute(
            "SELECT chapter_id, content_sha256 FROM chapters WHERE book_id=? "
            "ORDER BY ordinal DESC",
            (book_id,),
        ).fetchall()
        if not chapters:
            raise ValueError("demo 缺少章节")
        chapter_id = str(chapters[0]["chapter_id"])
        connection.execute(
            """
            INSERT OR IGNORE INTO threads(
                thread_id, book_id, edition_id, goal, stakes, phase, introduced_chapter,
                last_advanced_chapter, importance, reader_visibility, progress,
                dependencies_json, status, payload_json, created_at, version
            ) VALUES ('demo-signal', ?, 'base', '确认无线电来源', '错误回应会暴露灯塔',
                      'escalation', '1', '3', 0.9, 0.85, 0.35, '[]', 'CANON',
                      '{"deadline_urgency":78}', ?, 1)
            """,
            (book_id, utc_now()),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO promises(
                promise_id, book_id, edition_id, thread_id, statement, importance,
                reader_visibility, progress, introduced_ordinal, last_reminded_ordinal,
                reminder_count, target_min_age, target_max_age, status, source_span_id,
                payload_json, created_at, version, last_advanced_ordinal, dormancy_target,
                resolution_readiness, dependencies_ready, promise_horizon, author_deferred_until
            ) VALUES ('demo-overdue', ?, 'base', 'demo-signal', '北面灯塔的真实用途',
                      0.9, 0.9, 0.1, 1, 2, 2, 2, 1, 'CANON', NULL, '{}', ?, 1,
                      1, 2, 0.1, 1, 'short', NULL)
            """,
            (book_id, utc_now()),
        )
    return chapter_id


def _insert_demo_rhythm(database: Database, book_id: str) -> None:
    with database.connect() as connection:
        existing = connection.execute(
            "SELECT 1 FROM rhythm_diagnostic_snapshots WHERE book_id=? AND edition_id='base'",
            (book_id,),
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO rhythm_diagnostic_snapshots(
                    snapshot_id, book_id, edition_id, as_of_chapter, as_of_event_seq,
                    projection_hash, config_hash, analyzer_versions_json, snapshot_json, created_at
                ) VALUES ('demo-rhythm', ?, 'base', 4, 0, 'demo-projection', 'demo-config',
                          '{"deterministic":"demo"}',
                          '{"warnings":["same ending mode streak"],
                            "overdue_promises":["demo-overdue"]}', ?)
                """,
                (book_id, utc_now()),
            )


def _insert_demo_draft(database: Database, book_id: str, workspace: Path) -> None:
    draft_path = workspace / book_id / "drafts" / "demo-validated.md"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_text = "合成草稿：林岚没有打开北门，而是把坐标拆成两段交给潮汐。"
    draft_path.write_text(draft_text + "\n", encoding="utf-8")
    draft_id = "demo-validated-draft"
    contract_id = "demo-contract"
    candidate_id = "demo-candidate"
    now = utc_now()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO candidate_plans(
                candidate_id, book_id, edition_id, task_id, rank, primary_thread_id,
                primary_function, plan_json, score_json, gate_report_json,
                selection_status, status, created_at, version
            ) VALUES (?, ?, 'base', 'demo-plan-task', 1, 'demo-signal', 'DECISION',
                      '{}', '{"score":82}', '{"passed":true}', 'SELECTED', 'CANDIDATE', ?, 1)
            """,
            (candidate_id, book_id, now),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO chapter_contracts(
                contract_id, book_id, edition_id, candidate_id, target_chapter_ordinal,
                mode, contract_json, contract_sha256, status, created_at, version
            ) VALUES (?, ?, 'base', ?, 5, 'faithful_continuation', '{}', ?, 'READY', ?, 1)
            """,
            (contract_id, book_id, candidate_id, sha256_bytes(b"demo-contract"), now),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO drafts(
                draft_id, book_id, edition_id, contract_id, candidate_id, file_path,
                content_sha256, status, revision, created_at, task_id, chapter_title,
                output_json, base_event_seq, base_projection_hash, validation_run_id
            ) VALUES (?, ?, 'base', ?, ?, ?, ?, 'VALIDATED', 1, ?, 'demo-task',
                      '第五章·拆分坐标', ?, 0, 'demo', 'demo-validation')
            """,
            (
                draft_id,
                book_id,
                contract_id,
                candidate_id,
                str(draft_path),
                sha256_bytes(draft_text.encode("utf-8")),
                json_dumps(
                    {
                        "workflow_stage": "VALIDATED_DRAFT",
                        "metric_changes": [],
                        "state_changes": [],
                        "approval_preview": "尚未进入正史；需作者明确批准。",
                    }
                ),
                now,
            ),
        )
        for validator in ("schema", "canon_boundary", "metrics", "rhythm"):
            connection.execute(
                """
                INSERT OR IGNORE INTO validation_reports(
                    report_id, book_id, edition_id, draft_id, validator, severity,
                    passed, report_json, created_at, version, run_id
                ) VALUES (?, ?, 'base', ?, ?, 'INFO', 1, ?, ?, 1, 'demo-validation')
                """,
                (
                    stable_id("demo-validation", draft_id, validator),
                    book_id,
                    draft_id,
                    validator,
                    json_dumps({"status": "PASS", "message": "合成演示通过"}),
                    now,
                ),
            )


def _create_completed_demo_handoff(database: Database, book_id: str) -> str:
    handoff = create_continuation_handoff(
        database,
        book_id,
        requested_stage="DRAFT_AND_VALIDATE",
        require_complete_metrics=False,
    )
    handoff_id = str(handoff["handoff_id"])
    claimed = claim_handoff(database, handoff_id, "demo-fake-codex")
    token = str(claimed["claim_token"])
    update_handoff_status(database, handoff_id, HandoffStatus.RUNNING, claim_token=token)
    task = json.loads(
        (Path(str(handoff["task_directory"])) / "task.json").read_text(encoding="utf-8")
    )
    result = {
        "handoff_id": handoff_id,
        "handoff_type": HandoffType.CONTINUATION.value,
        "requested_stage": "DRAFT_AND_VALIDATE",
        "completed_stage": "VALIDATED_DRAFT",
        "book_id": book_id,
        "edition_id": str(task["edition_id"]),
        "status": "VALIDATED_DRAFT",
        "task_ids": ["demo-fake-worker"],
        "candidate_ids": ["demo-candidate"],
        "selected_candidate_id": "demo-candidate",
        "contract_id": "demo-contract",
        "draft_id": "demo-validated-draft",
        "campaign_id": None,
        "revision_unit_ids": [],
        "artifact_paths": [],
        "validation_summary": {"status": "PASS", "demo": True},
        "warnings": ["合成演示结果，尚未进入正史"],
        "next_action": "作者审查候选",
        "canon_committed": False,
        "edition_activated": False,
        "base_event_seq": task["base_event_seq"],
        "base_projection_hash": task["base_projection_hash"],
        "metric_run_ids": [str(task["metric_run_id"])] if task.get("metric_run_id") else [],
        "metric_bundle_hash": task.get("metric_bundle_hash"),
        "completed_at": utc_now(),
    }
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.COMPLETED,
        claim_token=token,
        result=result,
    )
    return handoff_id


def seed_author_workbench(
    workspace: Path = Path("workspace"),
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Create a fully synthetic, local-only Workbench demonstration project."""
    selected_settings = settings or load_settings()
    workspace = workspace.resolve()
    book_root = workspace / DEMO_BOOK_ID
    source_root = workspace / "_demo_sources" / DEMO_BOOK_ID
    source_root.mkdir(parents=True, exist_ok=True)
    source_path = source_root / "synthetic_author_workbench.md"
    source_path.write_text(_demo_text(), encoding="utf-8")
    database_path = book_root / "state.sqlite3"
    if not database_path.exists():
        ingest_book(
            book_id=DEMO_BOOK_ID,
            title="合成灯塔：Author Workbench 演示",
            source_root=source_root,
            workspace_root=workspace,
            settings=selected_settings,
        )
    database = Database(database_path)
    database.initialize()
    with database.connect() as connection:
        derived = connection.execute(
            "SELECT 1 FROM editions WHERE book_id=? AND edition_id=?",
            (DEMO_BOOK_ID, DEMO_EDITION_ID),
        ).fetchone()
    if derived is None:
        create_edition(database, DEMO_BOOK_ID, DEMO_EDITION_ID, "合成变体")
        _insert_demo_variant(database, DEMO_BOOK_ID, DEMO_EDITION_ID)
    rebuild_segments(database, DEMO_BOOK_ID, edition_id="base")
    rebuild_segments(database, DEMO_BOOK_ID, edition_id=DEMO_EDITION_ID)
    chapter_id = _insert_demo_state(database, DEMO_BOOK_ID)
    segments = list_segments(database, DEMO_BOOK_ID, edition_id="base", chapter_id=chapter_id)
    if not segments:
        raise ValueError("demo 章节没有可用 segment")
    quote = str(segments[0]["text"])[:40]
    with database.connect() as connection:
        chapter = connection.execute(
            "SELECT content_sha256 FROM chapters WHERE chapter_id=?", (chapter_id,)
        ).fetchone()
    assert chapter is not None
    _chapter_observations(
        database,
        DEMO_BOOK_ID,
        chapter_id,
        str(chapter["content_sha256"]),
        str(segments[0]["segment_id"]),
        quote,
        add_conflict=False,
    )
    # Keep the latest chapter focused on one author-editable missing input. Put
    # the intentional dispute and stale observation on the first chapter so
    # both diagnostic states are visible without making the main demo chapter
    # impossible to complete from the Missing Input Editor.
    with database.connect() as connection:
        first_chapter = connection.execute(
            "SELECT chapter_id, content_sha256 FROM chapters WHERE book_id=? "
            "AND edition_id='base' ORDER BY ordinal LIMIT 1",
            (DEMO_BOOK_ID,),
        ).fetchone()
    if first_chapter is not None and str(first_chapter["chapter_id"]) != chapter_id:
        first_segments = list_segments(
            database,
            DEMO_BOOK_ID,
            edition_id="base",
            chapter_id=str(first_chapter["chapter_id"]),
        )
        if first_segments:
            _chapter_observations(
                database,
                DEMO_BOOK_ID,
                str(first_chapter["chapter_id"]),
                str(first_chapter["content_sha256"]),
                str(first_segments[0]["segment_id"]),
                str(first_segments[0]["text"])[:40],
            )
    # Preserve the stale row and let the resolver explain why it is ignored.
    with database.connect() as connection:
        stale_row = connection.execute(
            "SELECT observation_id FROM metric_observations WHERE metric_id='progress' "
            "AND component_id='goal_advance' AND scope_id<>? ORDER BY created_at LIMIT 1",
            (chapter_id,),
        ).fetchone()
        if stale_row is not None:
            connection.execute(
                "UPDATE metric_observations SET config_hash='stale-demo-config' "
                "WHERE observation_id=?",
                (str(stale_row["observation_id"]),),
            )
    _insert_demo_rhythm(database, DEMO_BOOK_ID)
    MetricsAssembler(database).rebuild(
        DEMO_BOOK_ID, edition_id="base", scope_type="CHAPTER", scope_id=chapter_id
    )
    MetricsAssembler(database).rebuild(
        DEMO_BOOK_ID, edition_id="base", scope_type="WINDOW", scope_id="demo-window"
    )
    with database.connect() as connection:
        promise = connection.execute(
            "SELECT promise_id FROM promises WHERE book_id=? AND edition_id='base' LIMIT 1",
            (DEMO_BOOK_ID,),
        ).fetchone()
    if promise is not None:
        MetricsAssembler(database).rebuild(
            DEMO_BOOK_ID,
            edition_id="base",
            scope_type="PROMISE",
            scope_id=str(promise["promise_id"]),
        )
    build_planning_aggregate(
        database,
        DEMO_BOOK_ID,
        edition_id="base",
        author_policy={"demo": True, "policy": "作者保留最终决定权"},
    )
    _insert_demo_draft(database, DEMO_BOOK_ID, workspace)
    ready = create_continuation_handoff(
        database, DEMO_BOOK_ID, requested_stage="PLAN_ONLY", require_complete_metrics=False
    )
    completed_id = _create_completed_demo_handoff(database, DEMO_BOOK_ID)
    return {
        "book_id": DEMO_BOOK_ID,
        "title": "合成灯塔：Author Workbench 演示",
        "workspace": str(book_root),
        "source_root": str(source_root),
        "base_edition_id": "base",
        "derived_edition_id": DEMO_EDITION_ID,
        "ready_handoff_id": ready["handoff_id"],
        "completed_handoff_id": completed_id,
        "serve": "novel web serve --book-id demo-author-workbench --host 127.0.0.1 --port 8765",
        "synthetic_only": True,
    }
