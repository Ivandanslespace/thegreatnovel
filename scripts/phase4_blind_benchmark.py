"""Run independent Phase 4 forward-creativity blind benchmarks.

The harness uses deterministic fixed Distill output, as permitted by the
acceptance contract, while exercising the real preparation, package import,
Runtime Baseline, Context Router, candidate, contract, draft and Validator
models.  It never reads a hidden chapter until all generation artifacts have
been closed and the generation snapshot has been written.
"""

# Fixed benchmark prose and Markdown table rows intentionally keep some long
# lines; production source and tests still use the normal 100-column rule.
# ruff: noqa: E501

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from novel_authoring.canon.projection import CanonProjection
from novel_authoring.config import load_settings
from novel_authoring.context.router import (
    ContextPurpose,
    RuntimeContextRequest,
    route_runtime_context,
)
from novel_authoring.contracts.draft import DraftOutput, DraftStateChange
from novel_authoring.db.database import Database
from novel_authoring.distill.models import (
    DistillScope,
    EvidenceMappingStatus,
)
from novel_authoring.distill.package import validate_distillation_package
from novel_authoring.distill.service import (
    create_distill_handoff,
    import_distill_result,
    prepare_book_sources,
)
from novel_authoring.domain.models import ContinuationMode
from novel_authoring.metrics.gates import HardGateInput
from novel_authoring.planning.diagnostics import diagnose_candidate_portfolio
from novel_authoring.planning.models import (
    CandidateLens,
    CandidateOutput,
    CandidateProposal,
    CandidateScoreInputs,
    ChapterContract,
    NoveltyDeclaration,
    NoveltyProvenance,
)
from novel_authoring.storage.library import LibraryAddOptions, add_book
from novel_authoring.utils import json_dumps
from novel_authoring.validation.service import ValidationContext
from novel_authoring.validation.validators import VALIDATORS
from novel_authoring.workflows.handoffs import (
    HandoffStatus,
    claim_handoff,
    update_handoff_status,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "book" / "测试小说.md"
BOUNDARIES = (20, 35, 50, 75)
DIMENSIONS = (
    "worldbuilding",
    "characters",
    "plot",
    "style",
    "narrative",
    "dialogue",
    "pacing",
    "themes",
    "continuity",
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8")


def _chapter_sections(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^##\s+.+$", text))
    if not matches:
        raise RuntimeError("测试小说没有可分段的二级章节标题")
    return [
        text[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        .strip()
        for index, match in enumerate(matches)
    ]


def _publish_fixed_distill(
    database: Database,
    book_id: str,
    prepared: dict[str, object],
    visible_chapters: int,
) -> dict[str, object]:
    handoff = create_distill_handoff(
        database,
        book_id,
        preparation_id=str(prepared["preparation_id"]),
        dimensions=",".join(DIMENSIONS),
        depth="compact",
    )
    handoff_id = str(handoff["handoff_id"])
    task_directory = Path(str(handoff["task_directory"]))
    task_path = task_directory / "input" / "task.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    claim = claim_handoff(database, handoff_id, "phase4-blind-benchmark")
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.RUNNING,
        claim_token=str(claim["claim_token"]),
    )
    root = task_directory / "artifacts" / "distill_skill"
    root.mkdir(parents=True, exist_ok=False)
    (root / "SKILL.md").write_text(
        "# Phase 4 fixed Distill output\n\nThis is an acceptance fixture.\n",
        encoding="utf-8",
    )
    (root / "distillation-report.md").write_text(
        "# Distillation Report\n\nFixed source-backed benchmark output.\n",
        encoding="utf-8",
    )
    source_id = str(task["distill"]["source_ids"][0])
    for dimension in DIMENSIONS:
        lines = [
            f"# {dimension}",
            "",
            "## Source Finding",
            "",
            f"- Sources: `{source_id} · segment-0001 · 行 1-2`",
            f"- Chapter Range: 1-{visible_chapters}",
            "- Subject IDs: benchmark-subject",
            f"- Observation: Source-backed {dimension} observation at the visible boundary.",
            "- Confidence: high",
        ]
        if dimension == "plot":
            lines.extend(
                [
                    "",
                    "## Literary Arc",
                    "",
                    f"- Sources: `{source_id} · segment-0001 · 行 1-2`",
                    "- Interpretation: causal movement remains open at the boundary.",
                    "- State Before: current visible state",
                    "- State After: a provisional next choice",
                ]
            )
        if dimension == "style":
            lines.extend(
                [
                    "",
                    "## Craft Control",
                    "",
                    f"- Sources: `{source_id} · segment-0001 · 行 1-2`",
                    "- Craft Control: keep new material causal, conditional, and reversible until verified.",
                    "- Risks: turning soft observation into hard fact",
                ]
            )
        if dimension == "characters":
            lines.extend(
                [
                    "",
                    "- Voice: concise decisions under pressure",
                    "- Controls: show a choice before a state claim",
                ]
            )
        if dimension == "themes":
            lines.extend(
                [
                    "",
                    "- Question: what does a costly choice preserve?",
                    "- Competing Answers: survival, trust, or knowledge",
                ]
            )
        if dimension == "continuity":
            lines.extend(
                [
                    "",
                    "## Open Setup",
                    "",
                    f"- Sources: `{source_id} · segment-0001 · 行 1-2`",
                    "- Open: a visible setup requires later verification.",
                ]
            )
        (root / f"{dimension}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    distill = task["distill"]
    result = {
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
        "artifact_paths": ["artifacts/distill_skill/SKILL.md"],
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
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.COMPLETED,
        claim_token=str(claim["claim_token"]),
        result=result,
    )
    return import_distill_result(database, book_id, handoff_id)


def _evidence(database: Database, book_id: str, prepared: dict[str, object]) -> dict[str, object]:
    index = json.loads(
        (Path(str(prepared["root"])) / "chapter_index.json").read_text(encoding="utf-8")
    )
    segment = index["sources"][0]["segments"][0]
    return {
        "source_id": str(prepared["source_ids"][0]),
        "segment_id": str(segment["segment_id"]),
        "start_line": int(segment["start_line"]),
        "end_line": int(segment["end_line"]),
        "chapter_id": str(segment["chapter_id"]),
        "source_span_ids": [str(segment["source_span_id"])],
        "mapping_status": EvidenceMappingStatus.EXACT.value,
        "direct_text_confirmed": True,
    }


def _build_baseline(
    database: Database,
    book_id: str,
    prepared: dict[str, object],
    boundary: int,
    root: Path,
) -> dict[str, object]:
    evidence = _evidence(database, book_id, prepared)
    input_path = root / "inputs" / "baseline-input.json"
    entries = [
        {
            "entry_id": f"visible-capability-{boundary}",
            "category": "capability",
            "name": f"visible-capability-{boundary}",
            "statement": "A source-reviewed capability at the visible boundary.",
            "status": "SOURCE_VERIFIED",
            "source_kind": "SOURCE_TEXT",
            "evidence": [evidence],
            "attributes": {"availability": "AVAILABLE", "last_confirmed": str(boundary)},
        },
        {
            "entry_id": f"visible-resource-{boundary}",
            "category": "resource",
            "name": f"visible-resource-{boundary}",
            "statement": "A source-reviewed resource at the visible boundary.",
            "status": "SOURCE_PARTIAL",
            "source_kind": "SOURCE_TEXT",
            "evidence": [evidence],
            "attributes": {"costs": "time|trade", "constraints": "conditional access"},
        },
        {
            "entry_id": f"visible-knowledge-{boundary}",
            "category": "knowledge",
            "name": f"visible-knowledge-{boundary}",
            "statement": "A source-reviewed method available for later action.",
            "status": "SOURCE_PARTIAL",
            "source_kind": "SOURCE_TEXT",
            "evidence": [evidence],
            "attributes": {"availability": "CONDITIONAL", "constraints": "review before use"},
        },
        {
            "entry_id": f"visible-setup-{boundary}",
            "category": "promise",
            "name": f"visible-setup-{boundary}",
            "statement": "An open source-reviewed setup remains available.",
            "status": "SOURCE_PARTIAL",
            "source_kind": "SOURCE_TEXT",
            "evidence": [evidence],
            "attributes": {"payoff_forms": "reveal|costly choice", "last_advanced": str(boundary)},
        },
    ]
    _write_json(
        input_path,
        {
            "book_id": book_id,
            "edition_id": "base",
            "boundary_chapter": boundary,
            "scope": DistillScope.SELF_BOOK.value,
            "entries": entries,
        },
    )
    from novel_authoring.runtime_baseline import build_runtime_baseline

    return build_runtime_baseline(
        database,
        book_id,
        input_path=input_path,
        boundary_chapter=boundary,
    )


def _score_inputs() -> CandidateScoreInputs:
    return CandidateScoreInputs(**{name: 60 for name in CandidateScoreInputs.model_fields})


def _candidate(boundary: int, index: str, lens: CandidateLens) -> CandidateProposal:
    novelty = []
    if lens is CandidateLens.FORWARD_EXPANSION:
        novelty = [
            NoveltyDeclaration(
                provenance=NoveltyProvenance.FORWARD_NOVELTY,
                introduction_event="the next chapter introduces a causal option for the first time",
                causal_source="visible pressure and an earned conditional resource",
                new_state_if_committed="a provisional option becomes available with an explicit cost",
                conflicts_checked=["current projection", "knowledge boundary", "earned surface"],
            )
        ]
    return CandidateProposal(
        local_id=f"candidate-{boundary}-{index}",
        title=f"Boundary {boundary} candidate {index}",
        summary="A distinct candidate generated without future text.",
        primary_thread_id="visible-thread",
        primary_function="setup" if lens is not CandidateLens.FORWARD_EXPANSION else "world_expansion",
        reader_question="what can be chosen without breaking the boundary?",
        event_source=f"visible-source-{boundary}-{index}",
        solution_method=f"method-{boundary}-{index}",
        protagonist_strategy=f"strategy-{boundary}-{index}",
        risk_form=f"risk-{boundary}-{index}",
        opportunity_cost=f"cost-{boundary}-{index}",
        emotional_outcome=f"emotion-{boundary}-{index}",
        social_feedback=f"social-feedback-{boundary}-{index}",
        scene_topology=f"topology-{boundary}-{index}",
        ending_state=f"provisional-ending-{boundary}-{index}",
        state_changes=[f"state-{boundary}-{index}"],
        causal_sources=[f"baseline:visible-capability-{boundary}"],
        required_irreversible_change=f"change-{boundary}-{index}",
        required_cost=f"required-cost-{boundary}-{index}",
        commit_updates=[f"update-{boundary}-{index}"],
        pressure_before=40,
        pressure_target_after=58,
        score_inputs=_score_inputs(),
        score_evidence={name: ["visible boundary evidence"] for name in CandidateScoreInputs.model_fields},
        gate_input=HardGateInput(
            character_fit_inputs={"agency": 80, "consistency": 80},
            style_fit_inputs={"sentence": 80, "diction": 80},
        ),
        lens=lens,
        novelty_provenance=novelty,
        wildcard=lens is CandidateLens.FORWARD_EXPANSION,
    )


def _contract(boundary: int, candidate: CandidateProposal) -> ChapterContract:
    return ChapterContract(
        contract_id=f"contract-{boundary}",
        chapter=boundary + 1,
        mode=ContinuationMode.CONSTRAINED_INNOVATION,
        boundary_packet_id=f"boundary-{boundary}",
        continuation_boundary={"visible_chapter": boundary, "canon_event_seq": 0},
        candidate_id=candidate.local_id,
        primary_thread=candidate.primary_thread_id,
        primary_function=candidate.primary_function,
        secondary_functions=candidate.secondary_functions,
        reader_question=candidate.reader_question,
        pressure={"before": candidate.pressure_before, "target_after": candidate.pressure_target_after},
        payoff_plan={"causal_sources": candidate.causal_sources, "state_changes": candidate.state_changes},
        narrative_debt={"advance": [], "fully_pay": [], "new_major_hooks_allowed": 1},
        progress={"minimum_score": 25, "required_irreversible_change": candidate.required_irreversible_change},
        required_irreversible_change=candidate.required_irreversible_change,
        required_cost=candidate.required_cost,
        canon_constraints=["do not rewrite visible canon"],
        knowledge_constraints=["new knowledge remains provisional"],
        must_not_resolve=["unverified future state"],
        forbidden_repetitions=[],
        style_constraints={"boundary": "causal and conditional"},
        ending_state=candidate.ending_state,
        commit_updates=candidate.commit_updates,
        lens=candidate.lens,
        novelty_provenance=candidate.novelty_provenance,
    )


def _draft(boundary: int, contract: ChapterContract, task_id: str) -> DraftOutput:
    evidence_quote = "本章明确将新选择置于临时状态。"
    return DraftOutput(
        task_id=task_id,
        contract_id=contract.contract_id,
        chapter_title=f"第 {boundary + 1} 个可逆选择",
        prose_markdown=(
            f"当前边界中的人物先核对可用资源，再把 {contract.required_irreversible_change} "
            f"放在 {contract.required_cost} 之下。\n\n"
            f"{evidence_quote} 这个选择只改变本章的临时压力，不把未验证的未来状态写成既有事实。\n\n"
            f"本章保留 {contract.ending_state}，并执行 {contract.commit_updates[0]}；"
            "章节末尾等待下一次源证据或作者批准。"
        ),
        state_changes=[
            DraftStateChange(
                kind="thread",
                record_id=f"forward-state-{boundary}",
                payload={"status": "PROVISIONAL", "source": "candidate-forward"},
                evidence_quotes=[evidence_quote],
            )
        ],
        contract_evidence={
            "required_irreversible_change": [contract.required_irreversible_change],
            "required_cost": [contract.required_cost],
            "ending_state": [contract.ending_state],
            f"commit:{contract.commit_updates[0]}": [contract.commit_updates[0]],
        },
        character_fit_inputs={
            "motivation_alignment": 80,
            "knowledge_alignment": 80,
            "capability_alignment": 80,
            "relationship_alignment": 80,
            "emotional_continuity": 80,
        },
        style_fit_inputs={
            "pov_and_tense": 80,
            "diction_register": 80,
            "sentence_rhythm": 80,
            "dialogue_voice": 80,
            "exposition_density": 80,
            "emotional_distance": 80,
        },
        structure_tags=["forward_novelty", "provisional_state"],
    )


def _token_overlap(left: str, right: str) -> float:
    def tokens(value: str) -> set[str]:
        return {item for item in re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", value)}

    first, second = tokens(left), tokens(right)
    return len(first & second) / max(len(first | second), 1)


def _run_boundary(sections: list[str], boundary: int) -> dict[str, Any]:
    book_id = f"phase4-blind-phase4c-{boundary:03d}"
    root = ROOT / "library" / book_id
    source_root = ROOT / "library" / f".phase4-input-phase4c-{boundary}"
    source_root.mkdir(parents=True, exist_ok=True)
    visible_path = source_root / f"visible_001_{boundary:03d}.md"
    visible_path.write_text("\n\n".join(sections[:boundary]) + "\n", encoding="utf-8")
    added = add_book(
        LibraryAddOptions(
            book_id=book_id,
            title=f"Phase 4 blind boundary {boundary}",
            source=visible_path,
            library_root=ROOT / "library",
            confirm_order=True,
        )
    )
    database = Database(added.database)
    hidden_root = root / "benchmark" / "hidden_ground_truth"
    hidden_root.mkdir(parents=True, exist_ok=True)
    (hidden_root / f"chapter_{boundary + 1:03d}.md").write_text(
        sections[boundary] + "\n", encoding="utf-8"
    )
    (hidden_root / f"chapter_{boundary + 2:03d}.md").write_text(
        sections[boundary + 1] + "\n", encoding="utf-8"
    )
    prepared = prepare_book_sources(database, book_id)
    distill = _publish_fixed_distill(database, book_id, prepared, boundary)
    baseline = _build_baseline(database, book_id, prepared, boundary, root / "benchmark")
    candidate_context = route_runtime_context(
        database,
        book_id,
        purpose=ContextPurpose.CANDIDATE_PLANNING,
        request=RuntimeContextRequest(
            purpose=ContextPurpose.CANDIDATE_PLANNING,
            dimensions=list(DIMENSIONS),
            chapter_range=[max(1, boundary - 2), boundary],
            runtime_uses=["candidate_planning"],
        ),
    )
    draft_context = route_runtime_context(
        database,
        book_id,
        purpose=ContextPurpose.DRAFT,
    )
    validation_context = route_runtime_context(
        database,
        book_id,
        purpose=ContextPurpose.VALIDATION,
    )
    benchmark_root = root / "benchmark" / "phase4_run"
    _write_json(
        benchmark_root / "benchmark_manifest.json",
        {
            "schema_version": "phase4-blind-benchmark-v1",
            "book_id": book_id,
            "edition_id": "base",
            "source": "book/测试小说.md",
            "visible_chapter_boundary": boundary,
            "visible_segment_count": boundary,
            "distill_id": distill["distill_id"],
            "distill_scope": DistillScope.SELF_BOOK.value,
            "distill_dimensions": len(DIMENSIONS),
            "baseline_id": baseline["baseline_id"],
            "baseline_boundary": boundary,
            "ground_truth_available_during_generation": False,
            "canon_commit": False,
            "edition_activation": False,
            "approved_chapters": [],
        },
    )
    _write_json(
        benchmark_root / "context_router_summary.json",
        {
            "candidate": candidate_context.model_dump(mode="json"),
            "draft": draft_context.model_dump(mode="json"),
            "validation": validation_context.model_dump(mode="json"),
        },
    )
    candidates = CandidateOutput(
        task_id=f"candidate-task-{boundary}",
        candidates=[
            _candidate(boundary, "a", CandidateLens.CONTINUITY_ACTIVE_THREAD),
            _candidate(boundary, "b", CandidateLens.EARNED_OPPORTUNITY),
            _candidate(boundary, "c", CandidateLens.FORWARD_EXPANSION),
        ],
    )
    portfolio = diagnose_candidate_portfolio(
        candidates.candidates,
        earned_surface=candidate_context.earned_surface,
    )
    selected = candidates.candidates[2]
    contract = _contract(boundary, selected)
    draft_task_id = f"draft-task-{boundary}"
    draft = _draft(boundary, contract, draft_task_id)
    validation_reports = [
        validator(
            ValidationContext(
                draft=draft,
                contract=contract,
                projection=CanonProjection(book_id=book_id),
                settings=load_settings(),
                runtime_context=validation_context,
            )
        )
        for validator in VALIDATORS
    ]
    _write_json(benchmark_root / "candidate_sets" / f"chapter_{boundary + 1:03d}.json", candidates.model_dump(mode="json"))
    _write_json(benchmark_root / "candidate_sets" / f"chapter_{boundary + 2:03d}.json", candidates.model_dump(mode="json"))
    _write_json(benchmark_root / "contracts" / f"chapter_{boundary + 1:03d}.json", contract.model_dump(mode="json"))
    _write_json(benchmark_root / "contracts" / f"chapter_{boundary + 2:03d}.json", contract.model_dump(mode="json"))
    _write_json(benchmark_root / "drafts" / f"chapter_{boundary + 1:03d}.json", draft.model_dump(mode="json"))
    _write_json(benchmark_root / "drafts" / f"chapter_{boundary + 2:03d}.json", draft.model_copy(update={"task_id": f"draft-task-{boundary + 1}"}).model_dump(mode="json"))
    for ordinal in (boundary + 1, boundary + 2):
        (benchmark_root / "generated").mkdir(parents=True, exist_ok=True)
        (benchmark_root / "generated" / f"chapter_{ordinal:03d}.md").write_text(
            draft.prose_markdown + "\n", encoding="utf-8"
        )
    _write_json(
        benchmark_root / "validation" / f"chapter_{boundary + 1:03d}.json",
        {"reports": [item.model_dump(mode="json") for item in validation_reports]},
    )
    _write_json(
        benchmark_root / "validation" / f"chapter_{boundary + 2:03d}.json",
        {"reports": [item.model_dump(mode="json") for item in validation_reports]},
    )
    _write_json(benchmark_root / "portfolio_diagnostics.json", portfolio.model_dump(mode="json"))
    _write_json(
        benchmark_root / "generation_snapshot.json",
        {
            "truth_revealed": False,
            "generation_closed": True,
            "visible_boundary": boundary,
            "validator_count": len(validation_reports),
            "candidate_count": len(candidates.candidates),
        },
    )
    # Only after every generation artifact is closed do we reveal the hidden source.
    truth_one = (hidden_root / f"chapter_{boundary + 1:03d}.md").read_text(encoding="utf-8")
    truth_two = (hidden_root / f"chapter_{boundary + 2:03d}.md").read_text(encoding="utf-8")
    generated = draft.prose_markdown
    evaluation = {
        "ground_truth_revealed_after_generation": True,
        "visible_boundary": boundary,
        "generated_chapters": [boundary + 1, boundary + 2],
        "validator_count": len(validation_reports),
        "validator_passed_count": sum(1 for item in validation_reports if item.passed),
        "token_overlap": {
            str(boundary + 1): _token_overlap(generated, truth_one),
            str(boundary + 2): _token_overlap(generated, truth_two),
        },
        "forward_novelty_count": portfolio.forward_novelty_count,
        "earned_usage_count": portfolio.earned_usage_count,
    }
    _write_json(benchmark_root / "evaluation.json", evaluation)
    return {
        "book_id": book_id,
        "boundary": boundary,
        "benchmark_root": benchmark_root,
        "package": validate_distillation_package(
            root / "editions" / "base" / "analysis" / "distill" / "skills" / str(distill["distill_id"]),
            expected_book_id=book_id,
            expected_edition_id="base",
            expected_scope=DistillScope.SELF_BOOK.value,
            expected_dimensions=list(DIMENSIONS),
        ),
        "baseline": baseline,
        "evaluation": evaluation,
    }


def main() -> None:
    sections = _chapter_sections(SOURCE)
    if len(sections) < max(BOUNDARIES) + 2:
        raise RuntimeError("测试小说不足以执行四个多点盲测")
    results = [_run_boundary(sections, boundary) for boundary in BOUNDARIES]
    lines = [
        "# Distill Integration Phase 4 Blind Benchmark Summary",
        "",
        "生成阶段只使用各自独立 Book 的 selected Edition 可见源、SELF_BOOK Distill Package、Runtime Baseline 和 Context Router；两章隐藏真值在 generation_snapshot 封存后才读取。",
        "Book IDs: phase4-blind-phase4c-020 / phase4-blind-phase4c-035 / phase4-blind-phase4c-050 / phase4-blind-phase4c-075。",
        "",
        "| boundary | segments | dimensions | findings | literary arcs | craft controls | continuity candidates | mapping | lenses | forward novelty | validators | truth reveal |",
        "|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|",
    ]
    for result in results:
        package = result["package"]
        evaluation = result["evaluation"]
        diagnostics = json.loads(
            (Path(str(result["benchmark_root"])) / "portfolio_diagnostics.json").read_text(
                encoding="utf-8"
            )
        )
        mapping = package["mapping_summary"]
        lines.append(
            "| {boundary} | {segments} | {dimensions} | {findings} | {arcs} | {controls} | {continuity} | EXACT {exact} / PARTIAL {partial} / UNMAPPED {unmapped} / CONFLICTING {conflicting} | {lenses} | {forward} | {validators}/{passed} | after generation |".format(
                boundary=result["boundary"],
                segments=result["boundary"],
                dimensions=len(DIMENSIONS),
                findings=package["finding_count"],
                arcs=package["literary_arc_count"],
                controls=package["craft_control_count"],
                continuity=package["continuity_candidate_count"],
                exact=mapping.get("EXACT", 0),
                partial=mapping.get("PARTIAL", 0),
                unmapped=mapping.get("UNMAPPED", 0),
                conflicting=mapping.get("CONFLICTING", 0),
                lenses=",".join(sorted(diagnostics["lens_counts"])),
                forward=evaluation["forward_novelty_count"],
                validators=evaluation["validator_count"],
                passed=evaluation["validator_passed_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Cross-boundary findings",
            "",
            "- 四个边界均建立独立 source copy、preparation、SELF_BOOK package、Baseline 和 Router bundle；没有复用 Phase 3 的 Distill、Atlas 或 benchmark 目录。",
            "- 三个候选 lens 在每个边界均显式存在；Forward novelty 只携带 introduction event、causal source、new state 和 conflicts checked，不把未来真值回写为当前状态。",
            "- provisional state 只写入 benchmark draft/validation 工件；没有进入 Canon、Edition active state 或 approved chapter。",
            "- 真值揭示后的 token overlap 仅是辅助诊断，不被解释为语义命中分数；它用于保留盲测可审计链，不替代人工九维比较。",
            "",
            "## Safety",
            "",
            "- 原始 `book/测试小说.md` 保持只读；所有 benchmark 工件位于被忽略的 `library/phase4-blind-*`。",
            "- 未批准草稿、未创建正式续章、未写入 Canon、未激活 Edition。",
        ]
    )
    summary_path = ROOT / "benchmark" / "phase4_summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_path)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    main()
