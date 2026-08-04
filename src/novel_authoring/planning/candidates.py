from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from novel_authoring.config import Settings
from novel_authoring.db.database import Database
from novel_authoring.metrics.formulas import candidate_score, narrative_debt, thread_need
from novel_authoring.metrics.gates import evaluate_hard_gates
from novel_authoring.planning.boundary import PlanningError, _workspace, build_boundary_packet
from novel_authoring.planning.models import CandidateOutput, CandidateProposal, ThreadPriority
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now

STRUCTURE_FIELDS = (
    "event_source",
    "solution_method",
    "protagonist_strategy",
    "risk_form",
    "opportunity_cost",
    "emotional_outcome",
    "social_feedback",
    "scene_topology",
    "ending_state",
)


def _current_ordinal(connection: Any, book_id: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(ordinal), 0) FROM chapters WHERE book_id=?", (book_id,)
    ).fetchone()
    return int(row[0])


def rank_threads(
    database: Database, book_id: str, settings: Settings
) -> list[ThreadPriority]:
    with database.connect() as connection:
        current_ordinal = _current_ordinal(connection, book_id)
        rows = connection.execute(
            """
            SELECT * FROM threads
            WHERE book_id=? AND status IN ('CANON','AUTHOR_INTENT','APPROVED_OUTLINE')
              AND phase NOT IN ('resolved','closed')
            ORDER BY importance DESC, thread_id
            """,
            (book_id,),
        ).fetchall()
        priorities: list[ThreadPriority] = []
        for row in rows:
            payload = json.loads(str(row["payload_json"]))
            promise_rows = connection.execute(
                "SELECT * FROM promises WHERE book_id=? AND thread_id=? AND status='CANON'",
                (book_id, row["thread_id"]),
            ).fetchall()
            debts = []
            for promise in promise_rows:
                debt = narrative_debt(
                    importance=float(promise["importance"]),
                    reader_visibility=float(promise["reader_visibility"]),
                    promise_progress=float(promise["progress"]),
                    age_chapters=max(0, current_ordinal - int(promise["introduced_ordinal"])),
                    target_max_age=int(promise["target_max_age"]),
                    reminder_count=int(promise["reminder_count"]),
                    config=settings.metrics["narrative_debt"],
                ).score
                debts.append(debt)
            last_advanced = int(row["last_advanced_chapter"] or row["introduced_chapter"] or 0)
            gap = max(0, current_ordinal - last_advanced)
            values = {
                "narrative_debt": max(debts, default=0),
                "deadline_urgency": float(payload.get("deadline_urgency", 0)),
                "payoff_readiness": float(
                    payload.get("payoff_readiness", float(row["progress"]) * 100)
                ),
                "recency_neglect": float(payload.get("recency_neglect", min(100, gap / 12 * 100))),
                "goal_blockage": float(
                    payload.get("goal_blockage", (1 - float(row["progress"])) * 100)
                ),
                "protagonist_relevance": float(
                    payload.get("protagonist_relevance", float(row["importance"]) * 100)
                ),
                "diversity_bonus": float(payload.get("diversity_bonus", 50)),
            }
            score = thread_need(values, settings.metrics["thread_need"])
            priorities.append(
                ThreadPriority(
                    thread_id=str(row["thread_id"]),
                    goal=str(row["goal"]),
                    score=score,
                    inputs=values,
                    evidence=[
                        f"active promises={len(promise_rows)}",
                        f"chapters since advance={gap}",
                        f"importance={row['importance']}",
                    ],
                )
            )
    return sorted(priorities, key=lambda item: (-item.score, item.thread_id))[:3]


def prepare_candidate_task(
    database: Database, book_id: str, settings: Settings
) -> dict[str, object]:
    boundary = build_boundary_packet(
        database, book_id, recent_full_chapters=settings.recent_full_chapters
    )
    threads = rank_threads(database, book_id, settings)
    if not threads:
        raise PlanningError("没有可规划的活跃线程；请先完成抽取与 reconcile")
    with database.connect() as connection:
        metric_rows = connection.execute(
            """
            SELECT * FROM metric_results WHERE book_id=?
            AND as_of_event_seq=(SELECT MAX(as_of_event_seq) FROM metric_results WHERE book_id=?)
            ORDER BY metric_name
            """,
            (book_id, book_id),
        ).fetchall()
    if len(metric_rows) < 6:
        raise PlanningError("缺少六项最新指标；请先运行 novel diagnose")
    schema = CandidateOutput.model_json_schema()
    schema_json = json_dumps(schema, indent=2)
    seed = json_dumps(
        {
            "book_id": book_id,
            "boundary": boundary["packet_id"],
            "threads": [item.model_dump(mode="json") for item in threads],
            "metrics": [dict(row) for row in metric_rows],
        }
    )
    task_id = stable_id("plan", seed, sha256_bytes(schema_json.encode()))
    workspace = _workspace(database, book_id)
    task_dir = workspace / "agent_tasks" / task_id
    output_dir = workspace / "agent_outputs" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_text = "\n".join(
        [
            f"# 下一章候选任务 `{task_id}`",
            "",
            f"Boundary Packet: `{boundary['markdown_path']}`",
            "",
            "必须提交恰好三个结构真正不同的候选；不得只换怪物、资源、地点或社会反馈名词。",
            "每个候选先填写硬门证据，再填写评分输入与来源；Python 将重新计算门禁、结构差异和总分。",
            "候选只处于 CANDIDATE，不得写正文或升级为 CANON。",
            "",
            "## 三条优先线程",
            "",
            "```json",
            json_dumps([item.model_dump(mode="json") for item in threads], indent=2),
            "```",
            "",
            "## 最新指标",
            "",
            "```json",
            json_dumps([dict(row) for row in metric_rows], indent=2),
            "```",
        ]
    )
    metadata = {
        "task_id": task_id,
        "task_type": "plan-next",
        "book_id": book_id,
        "boundary_packet_id": boundary["packet_id"],
        "boundary_path": boundary["json_path"],
        "thread_priorities": [item.model_dump(mode="json") for item in threads],
        "schema_sha256": sha256_bytes(schema_json.encode()),
        "created_at": utc_now(),
    }
    (task_dir / "input.md").write_text(input_text, encoding="utf-8")
    (task_dir / "schema.json").write_text(schema_json + "\n", encoding="utf-8")
    (task_dir / "task.json").write_text(
        json_dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "task_id": task_id,
        "boundary_packet_id": boundary["packet_id"],
        "input": str(task_dir / "input.md"),
        "schema": str(task_dir / "schema.json"),
        "expected_output": str(output_dir / "output.json"),
        "top_threads": [item.model_dump(mode="json") for item in threads],
    }


def _difference_count(left: CandidateProposal, right: CandidateProposal) -> int:
    return sum(
        str(getattr(left, field)).strip().casefold()
        != str(getattr(right, field)).strip().casefold()
        for field in STRUCTURE_FIELDS
    )


def import_candidate_output(
    database: Database,
    book_id: str,
    task_id: str,
    settings: Settings,
    output_path: Path | None = None,
) -> dict[str, object]:
    workspace = _workspace(database, book_id)
    task_path = workspace / "agent_tasks" / task_id / "task.json"
    if not task_path.exists():
        raise PlanningError(f"候选任务不存在：{task_id}")
    metadata = json.loads(task_path.read_text(encoding="utf-8"))
    path = output_path or workspace / "agent_outputs" / task_id / "output.json"
    try:
        output = CandidateOutput.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise PlanningError(f"候选 output.json 不符合合同：{exc}") from exc
    if output.task_id != task_id:
        raise PlanningError("候选 output task_id 不匹配")
    differences: dict[str, list[int]] = {candidate.local_id: [] for candidate in output.candidates}
    for left, right in combinations(output.candidates, 2):
        count = _difference_count(left, right)
        differences[left.local_id].append(count)
        differences[right.local_id].append(count)
        if count < 3:
            raise PlanningError(
                f"候选 {left.local_id}/{right.local_id} 只有 {count} 个结构维度不同"
            )
    evaluated: list[dict[str, Any]] = []
    for candidate in output.candidates:
        gate = evaluate_hard_gates(candidate.gate_input, settings.metrics)
        diversity = sum(differences[candidate.local_id]) / (
            len(differences[candidate.local_id]) * len(STRUCTURE_FIELDS)
        ) * 100
        inputs = candidate.score_inputs.model_dump()
        inputs["structural_diversity"] = diversity
        required_evidence = set(inputs) - {"structural_diversity"}
        missing_evidence = sorted(
            key for key in required_evidence if not candidate.score_evidence.get(key)
        )
        if missing_evidence:
            raise PlanningError(
                f"候选 {candidate.local_id} 缺少评分证据：{missing_evidence}"
            )
        score_evidence = dict(candidate.score_evidence)
        score_evidence["structural_diversity"] = [
            f"与另外两案的结构差异维度数：{differences[candidate.local_id]}"
        ]
        score = candidate_score(inputs, settings.metrics["candidate_score"]) if gate.passed else 0
        evaluated.append(
            {
                "candidate": candidate,
                "candidate_id": stable_id("candidate", task_id, candidate.local_id),
                "gate": gate,
                "score": score,
                "inputs": inputs,
                "score_evidence": score_evidence,
                "diversity": diversity,
            }
        )
    passed = sorted(
        (item for item in evaluated if item["gate"].passed),
        key=lambda item: (-float(item["score"]), str(item["candidate_id"])),
    )
    if not passed:
        raise PlanningError("三个候选全部未通过硬门")
    selected_id = str(passed[0]["candidate_id"])
    best_score = float(passed[0]["score"])
    tie_delta = float(settings.metrics["candidate_score"]["tie_delta"])
    same_choice_band = [
        str(item["candidate_id"])
        for item in passed
        if best_score - float(item["score"]) < tie_delta
    ]
    ranking = {str(item["candidate_id"]): index for index, item in enumerate(passed, 1)}
    with database.connect() as connection:
        for item in evaluated:
            candidate = item["candidate"]
            assert isinstance(candidate, CandidateProposal)
            candidate_id = str(item["candidate_id"])
            gate = item["gate"]
            selection = (
                "REJECTED"
                if not gate.passed
                else "SELECTED"
                if candidate_id == selected_id
                else "NOT_SELECTED"
            )
            reason = (
                "; ".join(gate.hard_failures)
                if not gate.passed
                else (
                    "综合评分最高且通过硬门；同一可选区间仍由作者审美决定"
                    if len(same_choice_band) > 1
                    else "综合评分最高且通过硬门"
                )
                if candidate_id == selected_id
                else (
                    f"与最高分差小于 {tie_delta:g}，属于同一可选区间；"
                    "默认未选但保留给作者"
                    if candidate_id in same_choice_band
                    else f"通过硬门但排名 {ranking[candidate_id]}，保留为备选"
                )
            )
            score_json = {
                "score": item["score"],
                "inputs": item["inputs"],
                "evidence": item["score_evidence"],
                "structural_difference_counts": differences[candidate.local_id],
                "reason": reason,
            }
            connection.execute(
                """
                INSERT OR REPLACE INTO candidate_plans(
                    candidate_id, book_id, task_id, rank, primary_thread_id,
                    primary_function, secondary_functions_json, plan_json,
                    score_json, gate_report_json, selection_status, status,
                    created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CANDIDATE', ?, 1)
                """,
                (
                    candidate_id,
                    book_id,
                    task_id,
                    ranking.get(candidate_id),
                    candidate.primary_thread_id,
                    candidate.primary_function.value,
                    json_dumps([item.value for item in candidate.secondary_functions]),
                    json_dumps(candidate.model_dump(mode="json")),
                    json_dumps(score_json),
                    json_dumps(gate.model_dump(mode="json")),
                    selection,
                    utc_now(),
                ),
            )
    return {
        "task_id": task_id,
        "selected_candidate_id": selected_id,
        "same_choice_band": same_choice_band,
        "candidates": [
            {
                "candidate_id": item["candidate_id"],
                "title": item["candidate"].title,
                "score": item["score"],
                "passed": item["gate"].passed,
                "selection_status": "SELECTED"
                if item["candidate_id"] == selected_id
                else "REJECTED"
                if not item["gate"].passed
                else "NOT_SELECTED",
                "hard_failures": item["gate"].hard_failures,
                "structural_difference_counts": differences[item["candidate"].local_id],
            }
            for item in evaluated
        ],
        "boundary_packet_id": metadata["boundary_packet_id"],
    }
