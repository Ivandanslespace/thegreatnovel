from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.config import Settings, load_settings
from novel_authoring.db.database import Database
from novel_authoring.drafting.service import import_draft_output, prepare_draft_task
from novel_authoring.ingest.service import ingest_book
from novel_authoring.metrics.engine import MetricInputBundle, diagnose_bundle, persist_results
from novel_authoring.planning.boundary import PlanningError, build_boundary_packet
from novel_authoring.planning.candidates import (
    import_candidate_output,
    prepare_candidate_task,
)
from novel_authoring.planning.contracts import build_chapter_contract
from novel_authoring.planning.models import ChapterContract
from novel_authoring.utils import json_dumps, sha256_file, utc_now
from novel_authoring.validation.service import validate_draft
from novel_authoring.workflows.approval import approve_draft
from novel_authoring.workflows.directives import add_directive
from novel_authoring.workflows.exporting import export_book

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def setup_planning_book(tmp_path: Path) -> tuple[Database, Path, Settings]:
    source_root = tmp_path / "中文小说"
    source_root.mkdir()
    (source_root / FIXTURE.name).write_bytes(FIXTURE.read_bytes())
    workspace = tmp_path / "workspace"
    settings = load_settings()
    ingest_book(
        book_id="planning-book",
        title="合成求生小说",
        source_root=source_root,
        workspace_root=workspace,
        settings=settings,
    )
    database = Database(workspace / "planning-book" / "state.sqlite3")
    with database.connect() as connection:
        for index, (thread_id, goal, progress) in enumerate(
            [
                ("station-defense", "守住气象站", 0.7),
                ("radio-caller", "确认无线电呼叫者身份", 0.4),
                ("wind-rule", "理解午夜风向规则", 0.5),
            ],
            1,
        ):
            connection.execute(
                """
                INSERT INTO threads(
                    thread_id, book_id, goal, stakes, phase,
                    introduced_chapter, last_advanced_chapter,
                    importance, reader_visibility, progress,
                    dependencies_json, status, payload_json, created_at
                ) VALUES (?, 'planning-book', ?, ?, 'escalation', '1', ?, ?, 0.9, ?, '[]',
                          'CANON', ?, ?)
                """,
                (
                    thread_id,
                    goal,
                    f"线程 {index} 失败会改变后续选择",
                    str(index),
                    1 - index * 0.1,
                    progress,
                    json_dumps(
                        {
                            "deadline_urgency": 80 - index * 10,
                            "payoff_readiness": progress * 100,
                            "goal_blockage": (1 - progress) * 100,
                            "diversity_bonus": 40 + index * 10,
                        }
                    ),
                    utc_now(),
                ),
            )
    bundle = MetricInputBundle.model_validate(
        {
            "pressure": {
                "threat": 70,
                "scarcity": 60,
                "deadline": 80,
                "uncertainty": 50,
                "social_conflict": 20,
                "failure_accumulation": 30,
            },
            "narrative_debt": {
                "importance": 0.8,
                "reader_visibility": 0.9,
                "promise_progress": 0.4,
                "age_chapters": 3,
                "target_max_age": 5,
                "reminder_count": 1,
            },
            "progress": {
                "permanent_growth": 40,
                "world_state_change": 50,
                "relationship_change": 20,
                "knowledge_change": 70,
                "goal_advance": 60,
                "strategy_expansion": 30,
            },
            "payoff": {
                "maturity": 70,
                "impact": 60,
                "causality": 90,
                "after_value": 70,
                "repetition_fatigue": 10,
                "structural_fit": 80,
                "future_damage": 10,
            },
            "repetition_history": [{"distance": 5, "similarity": 0.2}],
            "risk_credibility": {
                "realized_cost_rate": 60,
                "consequence_clarity": 80,
                "opposition_effectiveness": 60,
                "protection_limit_visibility": 70,
                "information_limits": 80,
            },
        }
    )
    persist_results(
        database,
        "planning-book",
        diagnose_bundle(bundle, settings.metrics),
        settings.metrics,
    )
    return database, workspace, settings


def candidate_payload(
    local_id: str,
    thread_id: str,
    *,
    score: float,
    variant: int,
) -> dict[str, Any]:
    structures = [
        (
            "午夜风暴迫近",
            "修复气象站机械门",
            "主角用时间换取防御控制",
            "断电与门体损坏",
            "放弃监听一次无线电",
            "紧张后的有限掌控",
            "远方呼叫者改变联络频率",
            "狭窄维修层与屋顶",
            "气象站可守但无线电线索延后",
        ),
        (
            "无线电主动发来坐标",
            "交叉验证地图与呼叫内容",
            "主角设置错误信息测试对方",
            "暴露位置与信任风险",
            "消耗最后一段电量",
            "怀疑转为审慎合作",
            "呼叫者交付可验证情报",
            "控制室与远端声音双场景",
            "获得路线但确认对方仍隐瞒身份",
        ),
        (
            "同伴在门外留下求援记号",
            "谈判换取共同值守",
            "主角以钥匙权限设置合作条件",
            "关系背叛与物资分配风险",
            "让出一半安全空间",
            "孤立转为带条件的互信",
            "新同伴承担第一次守夜",
            "门内门外的对峙空间",
            "关系改变但地下秘密仍未解决",
        ),
    ]
    structure = structures[variant]
    character_keys = load_settings().metrics["character_fit"]["weights"]
    style_keys = load_settings().metrics["style_fit"]["weights"]
    return {
        "local_id": local_id,
        "title": f"候选 {variant + 1}",
        "summary": "产生一个可追溯的下一章状态变化",
        "primary_thread_id": thread_id,
        "primary_function": ["progress", "discovery", "relationship_shift"][variant],
        "secondary_functions": ["choice"],
        "reader_question": "主角会如何用有限资源换取下一步控制？",
        "event_source": structure[0],
        "solution_method": structure[1],
        "protagonist_strategy": structure[2],
        "risk_form": structure[3],
        "opportunity_cost": structure[4],
        "emotional_outcome": structure[5],
        "social_feedback": structure[6],
        "scene_topology": structure[7],
        "ending_state": structure[8],
        "state_changes": [structure[8]],
        "causal_sources": ["前三章已建立的风向、钥匙与无线电"],
        "promises_to_advance": [thread_id],
        "promises_to_pay": [],
        "required_irreversible_change": structure[8],
        "required_cost": structure[4],
        "must_not_resolve": ["无线电呼叫者的最终身份"],
        "canon_constraints": ["钥匙仍是生锈钥匙", "电量已经用于无线电"],
        "knowledge_constraints": ["林岚不知道呼叫者身份"],
        "forbidden_repetitions": ["再次只靠查看面板推进"],
        "commit_updates": ["thread_status", "resource_stock", "character_state"],
        "pressure_before": 70,
        "pressure_target_after": 55,
        "score_inputs": {
            "thread_need_fit": score,
            "pressure_curve_fit": score,
            "debt_utility": score,
            "progress_gain": score,
            "payoff_or_setup_utility": score,
            "agency_gain": score,
            "risk_fit": score,
            "structural_diversity": 0,
            "style_fit": 90,
            "repetition_fatigue": 10,
            "future_damage": 5,
        },
        "score_evidence": {
            key: [f"{key} 的合成证据：{thread_id}"]
            for key in (
                "thread_need_fit",
                "pressure_curve_fit",
                "debt_utility",
                "progress_gain",
                "payoff_or_setup_utility",
                "agency_gain",
                "risk_fit",
                "style_fit",
                "repetition_fatigue",
                "future_damage",
            )
        },
        "gate_input": {
            "character_fit_inputs": dict.fromkeys(character_keys, 90),
            "style_fit_inputs": dict.fromkeys(style_keys, 90),
        },
    }


def write_candidates(
    workspace: Path,
    task_id: str,
    candidates: list[dict[str, Any]],
) -> Path:
    path = workspace / "planning-book" / "agent_outputs" / task_id / "output.json"
    path.write_text(
        json.dumps(
            {"task_id": task_id, "candidates": candidates, "notes": []},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_boundary_candidate_ranking_and_contract(tmp_path: Path) -> None:
    database, workspace, settings = setup_planning_book(tmp_path)
    boundary = build_boundary_packet(database, "planning-book", recent_full_chapters=2)
    task = prepare_candidate_task(database, "planning-book", settings)
    task_id = str(task["task_id"])
    thread_ids = [item["thread_id"] for item in task["top_threads"]]
    candidates = [
        candidate_payload("candidate-a", thread_ids[0], score=90, variant=0),
        candidate_payload("candidate-b", thread_ids[1], score=85, variant=1),
        candidate_payload("candidate-c", thread_ids[2], score=65, variant=2),
    ]
    output_path = write_candidates(workspace, task_id, candidates)

    planned = import_candidate_output(
        database, "planning-book", task_id, settings, output_path
    )
    contract = build_chapter_contract(
        database, "planning-book", str(planned["selected_candidate_id"])
    )

    assert Path(str(boundary["markdown_path"])).exists()
    packet = json.loads(Path(str(boundary["json_path"])).read_text(encoding="utf-8"))
    assert len(packet["recent_full_chapters"]) == 2
    assert packet["relevant_source_spans"]
    assert packet["relevant_source_spans"][0]["ordinal"] == 1
    assert set(
        [
            "canon_facts",
            "character_states",
            "knowledge_boundaries",
            "active_threads",
            "promises",
            "resources",
            "capabilities",
            "relationships",
            "recent_payoffs",
            "recent_structures",
            "style_profiles",
            "author_directives",
            "narrative_portfolio",
        ]
    ) <= packet.keys()
    assert packet["narrative_portfolio"]["snapshot_id"]
    assert packet["innovation_diagnostics"]["portfolio_snapshot"] == packet[
        "narrative_portfolio"
    ]
    assert len(planned["candidates"]) == 3
    assert len(planned["same_choice_band"]) == 2
    assert sum(item["selection_status"] == "SELECTED" for item in planned["candidates"]) == 1
    assert all(min(item["structural_difference_counts"]) >= 3 for item in planned["candidates"])

    contract_data = json.loads(Path(str(contract["path"])).read_text(encoding="utf-8"))
    assert contract_data["chapter"] == 4
    assert len(contract_data["secondary_functions"]) <= 2
    assert contract_data["required_irreversible_change"]
    assert contract_data["required_cost"]
    assert contract_data["boundary_packet_id"] == task["boundary_packet_id"]

    with sqlite3.connect(database.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM candidate_plans").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM chapter_contracts").fetchone()[0] == 1


def test_candidate_output_rejects_renamed_same_structure(tmp_path: Path) -> None:
    database, workspace, settings = setup_planning_book(tmp_path)
    task = prepare_candidate_task(database, "planning-book", settings)
    task_id = str(task["task_id"])
    base = candidate_payload("one", "station-defense", score=80, variant=0)
    renamed = deepcopy(base)
    renamed["local_id"] = "two"
    renamed["title"] = "换了标题"
    third = candidate_payload("three", "radio-caller", score=70, variant=1)
    output = write_candidates(workspace, task_id, [base, renamed, third])

    with pytest.raises(PlanningError, match="结构维度不同"):
        import_candidate_output(database, "planning-book", task_id, settings, output)


def test_hard_gate_rejected_candidate_is_preserved_with_reason(tmp_path: Path) -> None:
    database, workspace, settings = setup_planning_book(tmp_path)
    task = prepare_candidate_task(database, "planning-book", settings)
    task_id = str(task["task_id"])
    candidates = [
        candidate_payload("one", "station-defense", score=80, variant=0),
        candidate_payload("two", "radio-caller", score=70, variant=1),
        candidate_payload("three", "wind-rule", score=90, variant=2),
    ]
    candidates[2]["gate_input"]["knowledge_violations"] = ["主角提前知道呼叫者身份"]
    output = write_candidates(workspace, task_id, candidates)

    result = import_candidate_output(database, "planning-book", task_id, settings, output)

    rejected = next(item for item in result["candidates"] if not item["passed"])
    assert rejected["selection_status"] == "REJECTED"
    assert rejected["score"] == 0
    assert rejected["hard_failures"] == ["主角提前知道呼叫者身份"]


def test_full_synthetic_e2e_from_ingest_to_approval(tmp_path: Path) -> None:
    database, workspace, settings = setup_planning_book(tmp_path)
    source_path = tmp_path / "中文小说" / FIXTURE.name
    source_hash = sha256_file(source_path)
    directive = add_directive(
        database,
        "planning-book",
        directive_type="requirement",
        content="主角必须主动选择",
    )
    build_boundary_packet(database, "planning-book", recent_full_chapters=3)
    task = prepare_candidate_task(database, "planning-book", settings)
    task_id = str(task["task_id"])
    threads = [item["thread_id"] for item in task["top_threads"]]
    candidate_path = write_candidates(
        workspace,
        task_id,
        [
            candidate_payload("e2e-a", threads[0], score=90, variant=0),
            candidate_payload("e2e-b", threads[1], score=75, variant=1),
            candidate_payload("e2e-c", threads[2], score=65, variant=2),
        ],
    )
    planned = import_candidate_output(
        database, "planning-book", task_id, settings, candidate_path
    )
    contract_result = build_chapter_contract(
        database, "planning-book", str(planned["selected_candidate_id"])
    )
    contract = ChapterContract.model_validate_json(
        Path(str(contract_result["path"])).read_text(encoding="utf-8")
    )
    draft_task = prepare_draft_task(database, "planning-book", contract.contract_id)
    draft_task_id = str(draft_task["task_id"])
    prose = "\n".join(
        [
            contract.required_irreversible_change,
            contract.required_cost,
            contract.ending_state,
            "线程状态完成更新，主角目标随之改变。",
            "资源库存完成更新，三份维修材料被正式登记。",
            "人物状态完成更新，他决定先加固机械门。",
        ]
    )
    draft_output = {
        "task_id": draft_task_id,
        "contract_id": contract.contract_id,
        "chapter_title": "合成端到端章节",
        "prose_markdown": prose,
        "state_changes": [
            {
                "kind": "thread",
                "record_id": contract.primary_thread,
                "payload": {
                    "goal": "守住气象站",
                    "stakes": "失守将失去安全据点",
                    "phase": "advanced",
                    "importance": 0.9,
                    "reader_visibility": 0.9,
                    "progress": 0.85,
                },
                "evidence_quotes": ["线程状态完成更新"],
            },
            {
                "kind": "resource",
                "record_id": "resource_repair_material",
                "payload": {
                    "owner_id": "hero",
                    "name": "维修材料",
                    "before_quantity": 0,
                    "delta": 3,
                    "after_quantity": 3,
                    "unit": "份",
                    "source": "气象站储物柜",
                },
                "evidence_quotes": ["三份维修材料被正式登记"],
            },
            {
                "kind": "character_state",
                "record_id": "state_hero_e2e",
                "payload": {
                    "character_id": "hero",
                    "goals": ["加固机械门"],
                    "plans": ["先修门再监听无线电"],
                },
                "evidence_quotes": ["他决定先加固机械门"],
            },
        ],
        "contract_evidence": {
            "required_irreversible_change": [contract.required_irreversible_change],
            "required_cost": [contract.required_cost],
            "ending_state": [contract.ending_state],
            "commit:thread_status": ["线程状态完成更新"],
            "commit:resource_stock": ["资源库存完成更新"],
            "commit:character_state": ["人物状态完成更新"],
        },
        "knowledge_claims": [],
        "character_fit_inputs": dict.fromkeys(
            settings.metrics["character_fit"]["weights"], 90
        ),
        "style_fit_inputs": dict.fromkeys(
            settings.metrics["style_fit"]["weights"], 90
        ),
        "character_bottom_line_violations": [],
        "style_boundary_violations": [],
        "promises_advanced": [contract.primary_thread],
        "promises_paid": [],
        "new_major_hooks": 0,
        "structure_tags": ["station-defense-repair"],
        "notes": ["固定合成 agent output，不调用远程模型"],
    }
    output_path = Path(str(draft_task["expected_output"]))
    output_path.write_text(json_dumps(draft_output, indent=2), encoding="utf-8")
    imported = import_draft_output(database, "planning-book", draft_task_id)
    draft_id = str(imported["draft_id"])
    assert validate_draft(database, "planning-book", draft_id, settings).passed
    committed = approve_draft(
        database,
        "planning-book",
        draft_id,
        confirmation="批准写入正史",
    )
    projection = rebuild_projection(database, "planning-book", persist=False)
    exported = export_book(database, "planning-book")
    next_boundary = build_boundary_packet(
        database, "planning-book", recent_full_chapters=3
    )
    next_packet = json.loads(
        Path(str(next_boundary["json_path"])).read_text(encoding="utf-8")
    )
    with database.connect() as connection:
        directive_status = connection.execute(
            "SELECT status FROM author_directives WHERE directive_id=?",
            (directive["directive_id"],),
        ).fetchone()[0]

    assert committed["status"] == "CANON_COMMITTED"
    assert directive_status == "CONSUMED"
    assert next_packet["author_directives"] == []
    assert "合成端到端章节" in next_packet["recent_full_chapters"][-1]["heading"]
    assert projection.committed_chapters
    assert contract.primary_thread in projection.threads
    assert Path(str(exported["manifest"])).is_file()
    assert sha256_file(source_path) == source_hash
