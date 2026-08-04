from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from novel_authoring.canon.events import EventStatus, EventStore
from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.config import load_settings
from novel_authoring.db.database import Database
from novel_authoring.domain.models import InformationStatus
from novel_authoring.drafting.service import (
    discard_draft,
    import_draft_output,
    prepare_draft_task,
)
from novel_authoring.ingest.service import ingest_book
from novel_authoring.planning.models import ChapterContract
from novel_authoring.utils import json_dumps, sha256_file, stable_id, utc_now
from novel_authoring.validation.models import VALIDATOR_NAMES
from novel_authoring.validation.service import validate_draft
from novel_authoring.workflows.approval import ApprovalWorkflowError, approve_draft

BOOK_ID = "synthetic-draft"


def _setup_contract(tmp_path: Path) -> tuple[Database, Path, ChapterContract]:
    source_dir = tmp_path / "中文来源"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "合成小说.md"
    source_path.write_text(
        "## 第一章 缺口\n主角缺少低级晶体。\n\n## 第二章 夜袭\n夜袭逼近。\n",
        encoding="utf-8",
    )
    workspace_root = tmp_path / "中文工作区"
    ingest_book(
        book_id=BOOK_ID,
        title="合成校验小说",
        source_root=source_dir,
        workspace_root=workspace_root,
        settings=load_settings(),
    )
    database = Database(workspace_root / BOOK_ID / "state.sqlite3")
    store = EventStore(database)
    store.append(
        book_id=BOOK_ID,
        event_type="TIMELINE_ENTRY_SET",
        aggregate_type="timeline",
        aggregate_id="timeline_existing",
        payload={
            "timeline_id": "timeline_existing",
            "label": "夜袭开始",
            "order_key": 1,
        },
        source_kind="TEST",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
        canon_commit_id="synthetic-seed",
    )
    projection = rebuild_projection(database, BOOK_ID)
    packet_id = "packet_synthetic"
    boundary_dir = workspace_root / BOOK_ID / "boundaries"
    boundary_dir.mkdir(parents=True, exist_ok=True)
    (boundary_dir / f"{packet_id}.md").write_text("# 合成边界\n", encoding="utf-8")
    contract = ChapterContract(
        contract_id="contract_synthetic",
        chapter=3,
        mode="faithful_continuation",
        boundary_packet_id=packet_id,
        continuation_boundary={
            "last_canon_chapter": 2,
            "base_event_seq": projection.through_event_seq,
            "base_projection_hash": projection.sha256(),
        },
        candidate_id="candidate_synthetic",
        primary_thread="thread_resource",
        primary_function="major_payoff",
        secondary_functions=["aftershock"],
        reader_question="低级晶体能否形成正循环？",
        pressure={"before": 82.0, "target_after": 38.0},
        payoff_plan={"causal_sources": ["夜袭"], "state_changes": ["资源自由"]},
        narrative_debt={
            "advance": [],
            "fully_pay": [],
            "new_major_hooks_allowed": 1,
        },
        progress={"minimum_score": 25, "required_irreversible_change": "资源自由"},
        required_irreversible_change="普通诡晶不再是核心焦虑",
        required_cost="备用箭矢耗尽",
        canon_constraints=["不得凭空增加资源"],
        knowledge_constraints=["主角只能知道已观察事实"],
        must_not_resolve=["高级诡晶短缺"],
        forbidden_repetitions=["普通宝箱暴富"],
        style_constraints={"pov": "第三人称限知"},
        ending_state="高级诡晶仍是下一层瓶颈",
        commit_updates=[
            "resource_stock",
            "payoff_history",
            "aftershock_obligations",
        ],
    )
    contract_json = json_dumps(contract.model_dump(mode="json"))
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO candidate_plans(
                candidate_id, book_id, task_id, rank, primary_thread_id,
                primary_function, plan_json, score_json, gate_report_json,
                selection_status, status, created_at
            ) VALUES (?, ?, 'task', 1, ?, 'major_payoff', '{}', '{}', '{}',
                      'SELECTED', 'CANDIDATE', ?)
            """,
            ("candidate_synthetic", BOOK_ID, "thread_resource", utc_now()),
        )
        connection.execute(
            """
            INSERT INTO chapter_contracts(
                contract_id, book_id, candidate_id, target_chapter_ordinal,
                mode, contract_json, contract_sha256, status, created_at
            ) VALUES (?, ?, ?, 3, ?, ?, ?, 'READY', ?)
            """,
            (
                contract.contract_id,
                BOOK_ID,
                contract.candidate_id,
                contract.mode.value,
                contract_json,
                stable_id("hash", contract_json),
                utc_now(),
            ),
        )
    return database, source_path, contract


def _valid_output(task_id: str, contract: ChapterContract) -> dict[str, Any]:
    prose = "\n".join(
        [
            "他从夜袭残骸中收起十枚诡晶。",
            "备用箭矢已经耗尽，这是此前选择留下的代价。",
            "系统记录让他确认普通诡晶不再是核心焦虑。",
            "他重新开启自动攻击，资源库存完成更新。",
            "这场兑现被记录进历史，四项余波义务随之锁定。",
            "时间推进到夜袭结束，第三人称限知视角没有越界。",
            "高级诡晶仍是下一层瓶颈。",
        ]
    )
    return {
        "task_id": task_id,
        "contract_id": contract.contract_id,
        "chapter_title": "夜袭闭环",
        "prose_markdown": prose,
        "state_changes": [
            {
                "kind": "fact",
                "record_id": "fact_resource_free",
                "payload": {
                    "subject_id": "hero",
                    "predicate": "resource_pressure",
                    "object": "low",
                    "statement": "普通诡晶不再是核心焦虑",
                },
                "evidence_quotes": ["普通诡晶不再是核心焦虑"],
            },
            {
                "kind": "knowledge",
                "record_id": "knowledge_hero_resource",
                "payload": {
                    "character_id": "hero",
                    "fact_id": "fact_resource_free",
                    "knowledge_state": "KNOWN",
                },
                "evidence_quotes": ["系统记录让他确认"],
            },
            {
                "kind": "timeline",
                "record_id": "timeline_night_raid_end",
                "payload": {
                    "label": "夜袭结束",
                    "story_time_start": 1,
                    "story_time_end": 2,
                    "order_key": 2,
                },
                "evidence_quotes": ["时间推进到夜袭结束"],
            },
            {
                "kind": "resource",
                "record_id": "resource_crystal",
                "payload": {
                    "owner_id": "hero",
                    "name": "诡晶",
                    "before_quantity": 0,
                    "delta": 10,
                    "after_quantity": 10,
                    "unit": "枚",
                    "causal_source": "夜袭残骸",
                },
                "evidence_quotes": ["收起十枚诡晶"],
            },
            {
                "kind": "payoff",
                "record_id": "payoff_night_raid",
                "payload": {
                    "thread_id": "thread_resource",
                    "payoff_type": "resource_liberation",
                    "causal_source": "夜袭掉落",
                    "cost": "备用箭矢耗尽",
                    "behavior_change": "重新开启自动攻击",
                    "major_event": True,
                    "cooldown_group": "major_same_subtype",
                    "chapters_since_same_subtype": 35,
                    "same_subtype_occurrence_count": 1,
                    "aftershock_obligations": [
                        "意识变化",
                        "行为变化",
                        "外部反馈",
                        "高阶瓶颈",
                    ],
                },
                "evidence_quotes": ["他重新开启自动攻击"],
            },
        ],
        "contract_evidence": {
            "required_irreversible_change": ["普通诡晶不再是核心焦虑"],
            "required_cost": ["备用箭矢已经耗尽"],
            "ending_state": ["高级诡晶仍是下一层瓶颈"],
            "commit:resource_stock": ["资源库存完成更新"],
            "commit:payoff_history": ["兑现被记录进历史"],
            "commit:aftershock_obligations": ["四项余波义务随之锁定"],
        },
        "knowledge_claims": [
            {
                "character_id": "hero",
                "fact_id": "fact_resource_free",
                "basis": "learned_in_draft",
            }
        ],
        "character_fit_inputs": {
            "motivation_alignment": 90,
            "knowledge_alignment": 90,
            "capability_alignment": 90,
            "relationship_alignment": 90,
            "emotional_continuity": 90,
        },
        "style_fit_inputs": {
            "pov_and_tense": 90,
            "diction_register": 90,
            "sentence_rhythm": 90,
            "dialogue_voice": 90,
            "exposition_density": 90,
            "emotional_distance": 90,
        },
        "character_bottom_line_violations": [],
        "style_boundary_violations": [],
        "promises_advanced": [],
        "promises_paid": [],
        "new_major_hooks": 1,
        "structure_tags": ["night-raid-closure"],
        "notes": ["合成测试章节"],
    }


def _import_output(
    database: Database,
    contract: ChapterContract,
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    task = prepare_draft_task(database, BOOK_ID, contract.contract_id)
    task_id = str(task["task_id"])
    output = _valid_output(task_id, contract)
    if mutate is not None:
        mutate(output)
    output_path = Path(str(task["expected_output"]))
    output_path.write_text(json_dumps(output, indent=2) + "\n", encoding="utf-8")
    result = import_draft_output(database, BOOK_ID, task_id)
    return str(result["draft_id"])


def test_ten_validators_approval_snapshot_and_rebuild(tmp_path: Path) -> None:
    database, source_path, contract = _setup_contract(tmp_path)
    source_hash = sha256_file(source_path)
    before = rebuild_projection(database, BOOK_ID)
    draft_id = _import_output(database, contract)

    after_import = rebuild_projection(database, BOOK_ID)
    assert after_import.sha256() == before.sha256()
    assert "fact_resource_free" not in after_import.facts

    validation = validate_draft(database, BOOK_ID, draft_id)
    assert validation.passed
    assert tuple(report.validator for report in validation.reports) == VALIDATOR_NAMES
    assert all(report.passed for report in validation.reports)

    with pytest.raises(ApprovalWorkflowError, match="批准写入正史"):
        approve_draft(database, BOOK_ID, draft_id, confirmation="同意")
    assert rebuild_projection(database, BOOK_ID).sha256() == before.sha256()

    result = approve_draft(database, BOOK_ID, draft_id, confirmation="批准写入正史")
    rebuilt = rebuild_projection(database, BOOK_ID, persist=False)
    with database.connect() as connection:
        draft_status = connection.execute(
            "SELECT status FROM drafts WHERE draft_id=?", (draft_id,)
        ).fetchone()[0]
        aftershocks = connection.execute(
            "SELECT COUNT(*) FROM promises WHERE payload_json LIKE '%\"aftershock\": true%'"
        ).fetchone()[0]
        snapshot = connection.execute(
            "SELECT state_sha256 FROM snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        fact_span = connection.execute(
            "SELECT source_span_id FROM facts WHERE fact_id='fact_resource_free'"
        ).fetchone()[0]
    assert result["status"] == "CANON_COMMITTED"
    assert draft_status == "CANON_COMMITTED"
    assert aftershocks == 4
    assert snapshot == rebuilt.sha256()
    assert fact_span is not None
    assert rebuilt.facts["fact_resource_free"]["predicate"] == "resource_pressure"
    assert rebuilt.committed_chapters[str(result["chapter_id"])]["ordinal"] == 3
    assert sha256_file(source_path) == source_hash


def test_canon_conflict_timeline_conflict_and_knowledge_leak_fail(
    tmp_path: Path,
) -> None:
    def mutate(output: dict[str, Any]) -> None:
        changes = output["state_changes"]
        assert isinstance(changes, list)
        fact = changes[0]
        timeline = changes[2]
        assert isinstance(fact, dict) and isinstance(timeline, dict)
        fact["record_id"] = "fact_existing"
        timeline_payload = timeline["payload"]
        assert isinstance(timeline_payload, dict)
        timeline_payload["order_key"] = 0
        claims = output["knowledge_claims"]
        assert isinstance(claims, list)
        claims[0] = {
            "character_id": "hero",
            "fact_id": "secret_not_known",
            "basis": "already_known",
        }

    database, _, contract = _setup_contract(tmp_path)
    EventStore(database).append(
        book_id=BOOK_ID,
        event_type="FACT_ASSERTED",
        aggregate_type="fact",
        aggregate_id="fact_existing",
        payload={
            "fact_id": "fact_existing",
            "subject_id": "hero",
            "predicate": "resource_pressure",
            "object": "high",
        },
        source_kind="TEST",
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
        canon_commit_id="synthetic-seed-2",
    )
    current = rebuild_projection(database, BOOK_ID)
    contract.continuation_boundary["base_event_seq"] = current.through_event_seq
    contract.continuation_boundary["base_projection_hash"] = current.sha256()
    contract_json = json_dumps(contract.model_dump(mode="json"))
    with database.connect() as connection:
        connection.execute(
            """
            UPDATE chapter_contracts SET contract_json=?, contract_sha256=?
            WHERE contract_id=?
            """,
            (contract_json, stable_id("hash", contract_json), contract.contract_id),
        )
    draft_id = _import_output(database, contract, mutate)
    validation = validate_draft(database, BOOK_ID, draft_id)
    failed = {report.validator for report in validation.reports if not report.passed}
    assert "Canon Validator" in failed
    assert "Timeline Validator" in failed
    assert "Knowledge Validator" in failed
    with pytest.raises(ApprovalWorkflowError, match="十项校验未全部通过"):
        approve_draft(database, BOOK_ID, draft_id, confirmation="批准写入正史")
    assert not rebuild_projection(database, BOOK_ID).committed_chapters


def test_discard_unapproved_draft_does_not_change_projection(tmp_path: Path) -> None:
    database, _, contract = _setup_contract(tmp_path)
    before = rebuild_projection(database, BOOK_ID)
    draft_id = _import_output(database, contract)
    result = discard_draft(database, BOOK_ID, draft_id)
    after = rebuild_projection(database, BOOK_ID)
    assert result["status"] == "REJECTED"
    assert after.sha256() == before.sha256()
