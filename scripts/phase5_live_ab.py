"""Prepare, collect and evaluate the Phase 5.1 live Codex handoff benchmark.

This module is deliberately an orchestration boundary.  It may create isolated
Book Libraries, freeze visible input, create Runtime Baseline data, prepare
file handoffs and validate/record returned artifacts.  It must never invent
Distill findings, candidate proposals, Chapter Contract prose or novel prose.

The only component allowed to create those literary artifacts is the Windows
Codex Desktop operator working on the READY_FOR_CODEX file handoffs.  The
benchmark therefore has four explicit commands::

    python scripts/phase5_live_ab.py prepare
    python scripts/phase5_live_ab.py status --run-label <label>
    python scripts/phase5_live_ab.py collect --run-label <label>
    python scripts/phase5_live_ab.py evaluate --run-label <label>

``collect`` is intentionally staged and strict.  It refuses to advance while
the current stage has unfinished handoffs, and it never reads hidden truth.
``evaluate`` is the first command allowed to read the controller-owned hidden
truth directory.
"""

# Work queues and benchmark prompts contain long Chinese operational prose.
# The production contracts, not line wrapping, are the relevant check here.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.config import load_settings
from novel_authoring.contracts.draft import DraftOutput
from novel_authoring.db.database import Database
from novel_authoring.distill.models import DistillScope, EvidenceMappingStatus
from novel_authoring.distill.service import (
    create_distill_handoff,
    import_distill_result,
    prepare_book_sources,
)
from novel_authoring.drafting.service import import_draft_output, prepare_draft_task
from novel_authoring.metrics.engine import MetricInputBundle, diagnose_bundle, persist_results
from novel_authoring.planning.batch import BatchProvisionalState
from novel_authoring.planning.candidates import (
    import_candidate_output,
    prepare_candidate_task,
)
from novel_authoring.planning.contracts import build_chapter_contract
from novel_authoring.planning.models import CandidateOutput, ChapterContract
from novel_authoring.rhythm.service import diagnose_rhythm, rebuild_features
from novel_authoring.runtime_baseline import build_runtime_baseline
from novel_authoring.runtime_baseline.models import (
    BaselineCategory,
    BaselineEvidence,
    BaselineStatus,
    RuntimeBaselineEntry,
    RuntimeBaselineInput,
)
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.library import LibraryAddOptions, add_book
from novel_authoring.storage.operations import ensure_operation
from novel_authoring.utils import json_dumps, sha256_file, stable_id, utc_now
from novel_authoring.validation.service import validate_draft
from novel_authoring.workflows.handoffs import (
    HandoffStatus,
    get_handoff,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "book" / "测试小说.md"
BOUNDARIES = (50, 75)
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
BASE_VARIANTS = ("A", "B")
SYSTEM_LANGUAGE_TERMS = (
    "runtime",
    "baseline",
    "earned surface",
    "canon",
    "projection",
    "validator",
    "thread_status",
    "resource_cost",
    "character_boundary",
    "distill",
    "融合层",
    "运行时基线",
    "正史投影",
)
HIDDEN_DIR_NAME = "phase5_live_hidden"
RUN_DIR_NAME = "live_phase5"
STATE_SCHEMA = "phase5-live-generation-ab-v1"
CONTEXT_SCHEMA = "phase5-live-context-manifest-v1"
DIRECTIVE_MARKER = "<!-- phase5.1-live-directive -->"


class LiveBenchmarkError(RuntimeError):
    """Raised when a live benchmark boundary is not safe to advance."""


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LiveBenchmarkError(f"无法读取 JSON：{path}") from exc
    if not isinstance(value, dict):
        raise LiveBenchmarkError(f"JSON 必须是 object：{path}")
    return value


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")


def _now_from_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def _chapter_sections(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^##\s+.+$", text))
    required = max(BOUNDARIES) + 2
    if len(matches) < required:
        raise LiveBenchmarkError(
            f"测试小说需要至少 {required} 个章节，实际只有 {len(matches)}"
        )
    return [
        text[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(text)].strip()
        for index, match in enumerate(matches)
    ]


def _paths(
    *,
    root: Path,
    run_label: str,
    controller_root: Path | None = None,
    hidden_root: Path | None = None,
    library_root: Path | None = None,
) -> dict[str, Path]:
    controller = (controller_root or root / "benchmark" / RUN_DIR_NAME).resolve()
    run_root = controller / "runs" / run_label
    hidden = (hidden_root or root / "benchmark" / HIDDEN_DIR_NAME / run_label).resolve()
    library = (library_root or root / "library").resolve()
    return {
        "controller_root": controller,
        "run_root": run_root,
        "state": run_root / "run_state.json",
        "queue": run_root / "WORK_QUEUE.md",
        "queue_pointer": controller / "WORK_QUEUE.md",
        "hidden_root": hidden,
        "library_root": library,
    }


def _ordered_books(state: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        state["books"],
        key=lambda item: (int(item["boundary"]), BASE_VARIANTS.index(str(item["variant"]))
        if str(item["variant"]) in BASE_VARIANTS
        else 2),
    )


def _save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    _write_json(Path(str(state["state_path"])), state)


def _load_state(
    run_label: str,
    *,
    root: Path = ROOT,
    controller_root: Path | None = None,
) -> dict[str, Any]:
    paths = _paths(root=root, run_label=run_label, controller_root=controller_root)
    if not paths["state"].is_file():
        raise LiveBenchmarkError(f"Live benchmark run 不存在：{paths['state']}")
    state = _read_json(paths["state"])
    if state.get("schema_version") != STATE_SCHEMA:
        raise LiveBenchmarkError("Live benchmark run schema 不匹配")
    state["state_path"] = str(paths["state"])
    return state


def _database(book: dict[str, Any]) -> Database:
    return Database(Path(str(book["database"])))


def _source_segments(prepared: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    index = _read_json(Path(str(prepared["root"])) / "chapter_index.json")
    sources = index.get("sources")
    if not isinstance(sources, list) or not sources:
        raise LiveBenchmarkError("冻结 preparation 缺少 source segments")
    source = sources[0]
    if not isinstance(source, dict) or not isinstance(source.get("segments"), list):
        raise LiveBenchmarkError("冻结 preparation 的 source segments 无效")
    return str(source["source_id"]), list(source["segments"])


def _segment(segments: list[dict[str, Any]], ordinal: int) -> dict[str, Any]:
    for segment in segments:
        if int(segment.get("ordinal", 0)) == ordinal:
            return segment
    raise LiveBenchmarkError(f"冻结 source 缺少第 {ordinal} 个 segment")


def _baseline_input(
    *,
    book: dict[str, Any],
    prepared: dict[str, Any],
    benchmark_root: Path,
) -> dict[str, Any]:
    """Create a compact source-derived Runtime Baseline, not literary output.

    The entries intentionally carry source anchors and neutral labels.  The
    live Codex must decide whether the visible prose supports a capability,
    resource or knowledge use; this controller does not prewrite that choice.
    """

    source_id, segments = _source_segments(prepared)
    boundary = int(book["boundary"])

    def evidence(ordinal: int) -> BaselineEvidence:
        segment = _segment(segments, ordinal)
        start = min(int(segment["end_line"]), int(segment["start_line"]) + 1)
        return BaselineEvidence(
            source_id=source_id,
            segment_id=str(segment["segment_id"]),
            start_line=start,
            end_line=min(int(segment["end_line"]), start + 2),
            chapter_id=str(segment["chapter_id"]),
            source_span_ids=[str(segment["source_span_id"])],
            mapping_status=EvidenceMappingStatus.EXACT,
            direct_text_confirmed=True,
        )

    rows = (
        (BaselineCategory.CAPABILITY, "capability", max(1, boundary - 2)),
        (BaselineCategory.RESOURCE, "resource", max(1, boundary - 1)),
        (BaselineCategory.KNOWLEDGE, "actionable knowledge", boundary),
    )
    entries: list[RuntimeBaselineEntry] = []
    for category, label, ordinal in rows:
        entry_id = f"visible-{category.value}-{boundary}-{ordinal}"
        entries.append(
            RuntimeBaselineEntry(
                entry_id=entry_id,
                category=category,
                name=f"source-confirmed {label} at chapter {ordinal}",
                statement=(
                    f"A source-derived {label} observation anchored to visible chapter "
                    f"{ordinal}; live Codex must verify its narrative use from the frozen source."
                ),
                status=BaselineStatus.SOURCE_VERIFIED,
                source_scope=DistillScope.SELF_BOOK,
                source_kind="SOURCE_TEXT",
                evidence=[evidence(ordinal)],
                attributes={
                    "availability": "SOURCE_VERIFIED",
                    "costs": "must verify before use",
                    "constraints": "visible source only",
                    "last_confirmed": str(ordinal),
                },
                runtime_uses=["candidate_planning", "draft_controls", "soft_validation"],
            )
        )
    payload = RuntimeBaselineInput(
        book_id=str(book["book_id"]),
        edition_id="base",
        boundary_chapter=boundary,
        scope=DistillScope.SELF_BOOK,
        entries=entries,
    )
    path = benchmark_root / "runtime_baseline_input.json"
    _write_json(path, payload.model_dump(mode="json"))
    result = build_runtime_baseline(
        _database(book),
        str(book["book_id"]),
        input_path=path,
        boundary_chapter=boundary,
    )
    if not isinstance(result, dict):
        raise LiveBenchmarkError("Runtime Baseline 构建结果无效")
    return result


def _seed_neutral_planning_inputs(database: Database, book_id: str, boundary: int) -> None:
    """Provide non-literary AUTHOR_INTENT/metric scaffolding for existing tasks."""

    goals = (
        ("visible-boundary", "从可见正文确定下一步问题"),
        ("source-continuity", "保持可见事实与未知边界分离"),
        ("author-choice", "让作者选择保留可验证的前进空间"),
    )
    with database.connect() as connection:
        for index, (_name, goal) in enumerate(goals, 1):
            connection.execute(
                """
                INSERT OR REPLACE INTO threads(
                    thread_id, book_id, goal, stakes, phase,
                    introduced_chapter, last_advanced_chapter,
                    importance, reader_visibility, progress,
                    dependencies_json, status, payload_json, created_at, edition_id
                ) VALUES (?, ?, ?, ?, 'escalation', ?, ?, 0.5, 0.5, 0.5, '[]',
                          'AUTHOR_INTENT', ?, ?, 'base')
                """,
                (
                    f"live-thread-{boundary}-{index}",
                    book_id,
                    goal,
                    "Neutral benchmark scaffold; Codex must derive the event from visible input.",
                    max(1, boundary - index),
                    max(1, boundary - index),
                    json_dumps({"deadline_urgency": 50, "payoff_readiness": 50, "goal_blockage": 50}),
                    utc_now(),
                ),
            )
    neutral = 50
    bundle = MetricInputBundle.model_validate(
        {
            "pressure": {
                "threat": neutral,
                "scarcity": neutral,
                "deadline": neutral,
                "uncertainty": neutral,
                "social_conflict": neutral,
                "failure_accumulation": neutral,
            },
            "narrative_debt": {
                "importance": 0.5,
                "reader_visibility": 0.5,
                "promise_progress": 0.5,
                "age_chapters": 1,
                "target_max_age": 8,
                "reminder_count": 0,
            },
            "progress": {
                "permanent_growth": neutral,
                "world_state_change": neutral,
                "relationship_change": neutral,
                "knowledge_change": neutral,
                "goal_advance": neutral,
                "strategy_expansion": neutral,
            },
            "payoff": {
                "maturity": neutral,
                "impact": neutral,
                "causality": neutral,
                "after_value": neutral,
                "repetition_fatigue": neutral,
                "structural_fit": neutral,
                "future_damage": neutral,
            },
            "repetition_history": [],
            "risk_credibility": {
                "realized_cost_rate": neutral,
                "consequence_clarity": neutral,
                "opposition_effectiveness": neutral,
                "protection_limit_visibility": neutral,
                "information_limits": neutral,
            },
        }
    )
    settings = load_settings()
    persist_results(database, book_id, diagnose_bundle(bundle, settings.metrics), settings.metrics)
    rebuild_features(database, book_id)
    diagnose_rhythm(database, book_id)


def _safety_state(database: Database, book_id: str) -> dict[str, Any]:
    projection = rebuild_projection(database, book_id, edition_id="base", persist=False)
    with database.connect() as connection:
        counts = {
            "events": int(
                connection.execute("SELECT COUNT(*) FROM events WHERE book_id=?", (book_id,)).fetchone()[0]
            ),
            "canon_commits": int(
                connection.execute(
                    "SELECT COUNT(*) FROM canon_commits WHERE book_id=?", (book_id,)
                ).fetchone()[0]
            ),
            "approved_drafts": int(
                connection.execute(
                    "SELECT COUNT(*) FROM drafts WHERE book_id=? "
                    "AND status IN ('AUTHOR_APPROVED','CANON_COMMITTED')",
                    (book_id,),
                ).fetchone()[0]
            ),
            "editions": [
                dict(row)
                for row in connection.execute(
                    "SELECT edition_id, status, activated_at FROM editions "
                    "WHERE book_id=? ORDER BY edition_id",
                    (book_id,),
                ).fetchall()
            ],
        }
        active = connection.execute(
            "SELECT active_edition_id FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    return {
        "counts": counts,
        "active_edition_id": None if active is None else active["active_edition_id"],
        "projection": {
            "through_event_seq": projection.through_event_seq,
            "facts": projection.facts,
            "threads": projection.threads,
            "capabilities": projection.capabilities,
            "resources": projection.resources,
            "knowledge": projection.knowledge,
        },
    }


def _safety_compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, bool]:
    return {
        "canon_events_unchanged": before["counts"]["events"] == after["counts"]["events"],
        "canon_commits_unchanged": before["counts"]["canon_commits"]
        == after["counts"]["canon_commits"],
        "approved_drafts_unchanged": before["counts"]["approved_drafts"]
        == after["counts"]["approved_drafts"],
        "edition_state_unchanged": before["counts"]["editions"] == after["counts"]["editions"],
        "active_edition_unchanged": before["active_edition_id"] == after["active_edition_id"],
        "projection_unchanged": before["projection"] == after["projection"],
    }


def _source_unchanged(state: dict[str, Any]) -> bool:
    source = Path(str(state["source"]))
    snapshot = state.get("source_snapshot", {})
    if not source.is_file() or not isinstance(snapshot, dict):
        return False
    return (
        source.stat().st_size == int(snapshot.get("size", -1))
        and source.stat().st_mtime_ns == int(snapshot.get("mtime_ns", -1))
    )


def _handoff_task_path(task_directory: Path) -> Path:
    candidate = task_directory / "input" / "task.json"
    return candidate if candidate.is_file() else task_directory / "task.json"


def _augment_distill_handoff(
    task_directory: Path,
    *,
    run_label: str,
    book: dict[str, Any],
) -> dict[str, Any]:
    """Add only protocol metadata before claim, then refresh frozen file hash."""

    task_path = _handoff_task_path(task_directory)
    task = _read_json(task_path)
    task["benchmark_protocol"] = {
        "schema_version": "phase5.1-live-protocol-v1",
        "run_label": run_label,
        "benchmark_variant": book["variant"],
        "boundary": book["boundary"],
        "visible_source_max_ordinal": book["boundary"],
        "hidden_truth_provided": False,
        "include_runtime_state": False,
        "semantic_output_must_be_codex_desktop": True,
        "python_literal_semantic_fixtures_forbidden": True,
    }
    task["distill"]["live_benchmark_instruction"] = (
        "这是 True Live Codex handoff。请只读取冻结的 artifacts/distill_input；"
        "九维语义必须由当前 Windows Codex Desktop 通过 $process-novel-handoff 与 "
        "$distill-novels 实际完成。Python 不提供九维答案，hidden truth 不在任务输入中。"
    )
    _write_json(task_path, task)
    context_path = task_directory / "input" / "context_manifest.json"
    context = _read_json(context_path)
    file_hashes = context.get("file_hashes", {})
    if not isinstance(file_hashes, dict):
        raise LiveBenchmarkError("Distill handoff context_manifest.file_hashes 无效")
    file_hashes["task.json"] = sha256_file(task_path)
    context["file_hashes"] = file_hashes
    _write_json(context_path, context)
    return task


def _task_metadata(task: dict[str, object]) -> dict[str, Any]:
    path = Path(str(task["input"]))
    return _read_json(path.parent / "task.json")


def _append_directive(path: Path, directive: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if DIRECTIVE_MARKER not in existing:
        _write_text(path, existing + "\n\n" + DIRECTIVE_MARKER + "\n" + directive)


def _operation_protocol(
    *,
    state: dict[str, Any],
    book: dict[str, Any],
    chapter: int,
    stage: str,
    include_runtime_state: bool,
    previous_provisional: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "phase5.1-live-protocol-v1",
        "run_label": state["run_label"],
        "benchmark_variant": book["variant"],
        "boundary": book["boundary"],
        "target_chapter": chapter,
        "stage": stage,
        "visible_source_max_ordinal": book["boundary"],
        "hidden_truth_provided": False,
        "include_runtime_state": include_runtime_state,
        "draft_include_runtime_state": book["variant"] == "B",
        "previous_provisional_state_present": previous_provisional is not None,
        "python_literal_candidate_fixture": False,
        "python_literal_prose_fixture": False,
    }


def _augment_operation_task(
    task: dict[str, object],
    *,
    protocol: dict[str, Any],
    directive: str,
) -> dict[str, Any]:
    input_path = Path(str(task["input"]))
    metadata = _task_metadata(task)
    metadata["benchmark_protocol"] = protocol
    metadata["benchmark_variant"] = protocol["benchmark_variant"]
    metadata["include_runtime_state"] = protocol["include_runtime_state"]
    metadata["hidden_truth_provided"] = False
    _write_json(input_path.parent / "task.json", metadata)
    _append_directive(input_path, directive)
    return metadata


def _runtime_expectation(metadata: dict[str, Any], expected: bool) -> None:
    if bool(metadata.get("include_runtime_state")) is not expected:
        raise LiveBenchmarkError(
            f"Runtime isolation 失败：task={metadata.get('task_id')} "
            f"include_runtime_state={metadata.get('include_runtime_state')} expected={expected}"
        )
    runtime = metadata.get("runtime_context", {})
    if not isinstance(runtime, dict):
        raise LiveBenchmarkError("task runtime_context 不是 object")
    if expected:
        if runtime.get("effective_runtime_state") is None or runtime.get("earned_surface") is None:
            raise LiveBenchmarkError("B/C planning task 缺少 Effective Runtime/Earned Surface")
    else:
        if runtime.get("effective_runtime_state") is not None:
            raise LiveBenchmarkError("A/C draft 仍加载 Effective Runtime")
        if runtime.get("earned_surface") is not None:
            raise LiveBenchmarkError("A/C draft 仍加载 Earned Surface")
        if runtime.get("baseline_recall_candidates"):
            raise LiveBenchmarkError("A/C draft 仍加载 baseline recall")
        if runtime.get("hard_constraints"):
            raise LiveBenchmarkError("A/C draft 仍加载 hard-state constraints")


def _context_manifest(
    state: dict[str, Any],
    book: dict[str, Any],
    *,
    task: dict[str, object],
    chapter: int,
    stage: str,
    expected_runtime: bool,
    previous_provisional: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = _task_metadata(task)
    _runtime_expectation(metadata, expected_runtime)
    runtime = metadata.get("runtime_context", {})
    if not isinstance(runtime, dict):
        runtime = {}
    reference = runtime.get("distill_reference")
    if not isinstance(reference, dict):
        reference = {}
    context = {
        "schema_version": CONTEXT_SCHEMA,
        "run_label": state["run_label"],
        "book_id": book["book_id"],
        "variant": book["variant"],
        "boundary": book["boundary"],
        "benchmark_variant": book["variant"],
        "target_chapter": chapter,
        "stage": stage,
        "truth_revealed": False,
        "visible_source": {
            "source": "isolated canonical Book frozen from book/测试小说.md",
            "max_visible_ordinal": book["boundary"],
            "visible_chapters": list(range(1, int(book["boundary"]) + 1)),
            "hidden_chapters_loaded": [],
        },
        "distill": {
            "scope": reference.get("scope", DistillScope.SELF_BOOK.value),
            "distill_id": reference.get("distill_id"),
            "dimensions": list(DIMENSIONS),
            "machine_manifest": reference.get("machine_manifest"),
        },
        "runtime_layers": {
            "include_runtime_state": bool(metadata.get("include_runtime_state")),
            "effective_runtime_state_id": (
                runtime.get("effective_runtime_state", {}) or {}
            ).get("state_id"),
            "earned_surface_id": (runtime.get("earned_surface", {}) or {}).get("surface_id"),
            "baseline_recall_candidate_count": len(runtime.get("baseline_recall_candidates", [])),
            "hard_constraints_loaded": bool(runtime.get("hard_constraints")),
        },
        "operation": {
            "handoff_id": None,
            "task_id": metadata.get("task_id"),
            "input": str(task["input"]),
            "schema": str(task["schema"]),
            "expected_output": str(task["expected_output"]),
            "task_created_at": metadata.get("created_at"),
        },
        "previous_provisional_state": previous_provisional,
        "canon_write": False,
        "edition_activation": False,
    }
    path = (
        Path(str(book["benchmark_root"]))
        / "context_manifests"
        / f"chapter_{chapter:03d}_{stage}.json"
    )
    _write_json(path, context)
    return context


def _distill_context_manifest(
    state: dict[str, Any], book: dict[str, Any], handoff: dict[str, Any]
) -> None:
    task_directory = Path(str(handoff["task_directory"]))
    task = _read_json(_handoff_task_path(task_directory))
    _write_json(
        Path(str(book["benchmark_root"])) / "context_manifests" / "distill.json",
        {
            "schema_version": CONTEXT_SCHEMA,
            "run_label": state["run_label"],
            "book_id": book["book_id"],
            "variant": book["variant"],
            "boundary": book["boundary"],
            "benchmark_variant": book["variant"],
            "stage": "distill",
            "truth_revealed": False,
            "visible_source": {
                "max_visible_ordinal": book["boundary"],
                "hidden_chapters_loaded": [],
            },
            "operation": {
                "handoff_id": handoff["handoff_id"],
                "task_id": handoff["handoff_id"],
                "task_directory": str(task_directory),
                "task_created_at": task.get("created_at"),
            },
            "include_runtime_state": False,
        },
    )


def _make_book_state(
    *,
    state: dict[str, Any],
    sections: list[str],
    boundary: int,
    variant: str,
    library_root: Path,
    hidden_root: Path,
) -> dict[str, Any]:
    label = f"{state['run_label']}-{variant.lower()}-{boundary:03d}"
    book_id = f"phase5-live-{variant.lower()}-{boundary:03d}"
    source_root = library_root / f".{label}-input"
    if source_root.exists():
        raise LiveBenchmarkError(f"prepare 输入目录已存在，拒绝覆盖：{source_root}")
    source_root.mkdir(parents=True)
    visible_path = source_root / f"visible_{boundary:03d}.md"
    _write_text(visible_path, "\n\n".join(sections[:boundary]))
    added = add_book(
        LibraryAddOptions(
            book_id=book_id,
            title=f"Phase 5.1 live {variant} boundary {boundary}",
            source=visible_path,
            library_root=library_root,
            confirm_order=True,
        )
    )
    database = Database(added.database)
    book_root = Path(str(added.root)).resolve()
    benchmark_root = book_root / "benchmark" / "phase5_live"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    prepared = prepare_book_sources(database, book_id, edition_id="base")
    baseline = _baseline_input(
        book={
            "book_id": book_id,
            "boundary": boundary,
            "database": str(added.database),
        },
        prepared=prepared,
        benchmark_root=benchmark_root,
    )
    _seed_neutral_planning_inputs(database, book_id, boundary)
    safety_before = _safety_state(database, book_id)
    handoff = create_distill_handoff(
        database,
        book_id,
        preparation_id=str(prepared["preparation_id"]),
        dimensions=",".join(DIMENSIONS),
        depth="standard",
        edition_id="base",
    )
    handoff_task_directory = Path(str(handoff["task_directory"]))
    _augment_distill_handoff(
        handoff_task_directory,
        run_label=str(state["run_label"]),
        book={"book_id": book_id, "variant": variant, "boundary": boundary},
    )
    book_state = {
        "book_id": book_id,
        "variant": variant,
        "boundary": boundary,
        "edition_id": "base",
        "root": str(book_root),
        "database": str(added.database),
        "benchmark_root": str(benchmark_root),
        "visible_source": str(visible_path),
        "visible_chapter_count": boundary,
        "recent_median_characters": int(
            statistics.median(len(section) for section in sections[max(0, boundary - 10) : boundary])
        ),
        "runtime_baseline": baseline,
        "safety_before": safety_before,
        "distill": {
            "handoff_id": handoff["handoff_id"],
            "task_directory": handoff["task_directory"],
            "status": HandoffStatus.READY_FOR_CODEX.value,
            "imported": False,
            "result": None,
        },
        "chapters": {
            str(boundary + 1): {},
            str(boundary + 2): {},
        },
        "generation_closed": False,
        "truth_revealed": False,
    }
    _distill_context_manifest(state, book_state, handoff)
    _write_json(
        benchmark_root / "benchmark_manifest.json",
        {
            "schema_version": STATE_SCHEMA,
            "benchmark_type": "TRUE_LIVE_CODEX_HANDOFF_AB",
            "run_label": state["run_label"],
            "book_id": book_id,
            "variant": variant,
            "boundary": boundary,
            "edition_id": "base",
            "visible_source": "book/测试小说.md",
            "visible_chapter_count": boundary,
            "selected_dimensions": list(DIMENSIONS),
            "distill_handoff_id": handoff["handoff_id"],
            "runtime_state_enabled_for_candidate": variant in {"B", "C"},
            "runtime_state_enabled_for_draft": variant == "B",
            "hidden_truth_provided": False,
            "canon_committed": False,
            "edition_activated": False,
            "approved_chapters": [],
            "semantic_executor": "Windows Codex desktop",
            "python_literal_semantic_fixture": False,
        },
    )
    # The controller owns hidden truth.  It is deliberately not inside this
    # Book Library and is not referenced by any task or context manifest.
    hidden_book_root = hidden_root / book_id
    hidden_book_root.mkdir(parents=True, exist_ok=False)
    _write_text(hidden_book_root / f"chapter_{boundary + 1:03d}.md", sections[boundary])
    _write_text(hidden_book_root / f"chapter_{boundary + 2:03d}.md", sections[boundary + 1])
    book_state["hidden_controller_key"] = book_id
    return book_state


def _prepare_run(
    *,
    run_label: str,
    source: Path = SOURCE,
    root: Path = ROOT,
    controller_root: Path | None = None,
    hidden_root: Path | None = None,
    library_root: Path | None = None,
    include_c: bool = False,
) -> dict[str, Any]:
    source = source.resolve()
    if not source.is_file():
        raise LiveBenchmarkError(f"测试源不存在：{source}")
    paths = _paths(
        root=root,
        run_label=run_label,
        controller_root=controller_root,
        hidden_root=hidden_root,
        library_root=library_root,
    )
    if paths["state"].exists():
        raise LiveBenchmarkError(f"run 已存在，拒绝覆盖：{paths['state']}")
    if paths["hidden_root"].resolve() == paths["library_root"].resolve() or paths["hidden_root"].is_relative_to(paths["library_root"]):
        raise LiveBenchmarkError("hidden truth 必须位于独立 controller 目录，不能位于 library")
    sections = _chapter_sections(source)
    paths["run_root"].mkdir(parents=True, exist_ok=False)
    paths["hidden_root"].mkdir(parents=True, exist_ok=False)
    state: dict[str, Any] = {
        "schema_version": STATE_SCHEMA,
        "run_label": run_label,
        "state_path": str(paths["state"]),
        "controller_root": str(paths["controller_root"]),
        "run_root": str(paths["run_root"]),
        "hidden_root": str(paths["hidden_root"]),
        "library_root": str(paths["library_root"]),
        "source": str(source),
        "source_snapshot": {"size": source.stat().st_size, "mtime_ns": source.stat().st_mtime_ns},
        "boundaries": list(BOUNDARIES),
        "variants": ["A", "B", "C"] if include_c else list(BASE_VARIANTS),
        "include_c": include_c,
        "truth_revealed": False,
        "generation_closed": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "books": [],
    }
    variants = list(BASE_VARIANTS) + (["C"] if include_c else [])
    for boundary in BOUNDARIES:
        for variant in variants:
            if variant == "C" and boundary != 50:
                continue
            book = _make_book_state(
                state=state,
                sections=sections,
                boundary=boundary,
                variant=variant,
                library_root=paths["library_root"],
                hidden_root=paths["hidden_root"],
            )
            state["books"].append(book)
    _write_queue(state)
    _save_state(state)
    return _status_summary(state)


def _visible_and_hidden_audit(state: dict[str, Any], book: dict[str, Any]) -> None:
    """Audit task inputs without reading controller-owned hidden content."""

    hidden_root = str(Path(str(state["hidden_root"])).resolve()).casefold()
    hidden_token = HIDDEN_DIR_NAME.casefold()
    book_root = Path(str(book["root"])).resolve()
    candidates = [
        path
        for path in book_root.rglob("*")
        if path.is_file()
        and (
            "operations" in path.parts
            or "context_manifests" in path.parts
            or path.name in {"benchmark_manifest.json", "generation_snapshot.json"}
        )
    ]
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lowered = content.casefold()
        if hidden_root in lowered or hidden_token in lowered:
            raise LiveBenchmarkError(f"发现 hidden truth 路径泄漏：{path}")
    benchmark_root = Path(str(book["benchmark_root"]))
    for path in benchmark_root.glob("context_manifests/*.json"):
        context = _read_json(path)
        visible = context.get("visible_source", {})
        if visible.get("max_visible_ordinal") != book["boundary"]:
            raise LiveBenchmarkError(f"visible ordinal 漂移：{path}")
        if visible.get("hidden_chapters_loaded"):
            raise LiveBenchmarkError(f"context manifest 已加载 hidden chapter：{path}")
    for path in benchmark_root.glob("**/task.json"):
        metadata = _read_json(path)
        protocol = metadata.get("benchmark_protocol", {})
        if protocol and protocol.get("visible_source_max_ordinal") != book["boundary"]:
            raise LiveBenchmarkError(f"task visible ordinal 漂移：{path}")
        if protocol and protocol.get("hidden_truth_provided"):
            raise LiveBenchmarkError(f"task 声明已提供 hidden truth：{path}")


def _candidate_directive(book: dict[str, Any], chapter: int) -> str:
    return "\n".join(
        [
            "本次是 Phase 5.1 True Live Codex Benchmark 的真实候选任务。",
            f"目标是第 {chapter} 章；可见正文最高只到第 {book['boundary']} 章。",
            "请你依据 task input 中的可见正文、Distill 和允许的 Runtime context，实际提出恰好三个具体小说事件候选。",
            "每个候选必须写清：谁、在哪里、做什么、为什么、付出什么不可撤回代价、引入什么新东西、章末改变什么。",
            "不得使用 method-50-a、change-50-c、某个有代价的选择等占位符；不得把未来真值写成已知事实。",
            "candidate output 必须是完整 CandidateOutput 合同，不要写正文；Python 只会校验你的 output，不会替你补充文学内容。",
        ]
    )


def _draft_directive(book: dict[str, Any], chapter: int) -> str:
    median = int(book["recent_median_characters"])
    low = int(median * 0.65)
    high = int(median * 1.35)
    return "\n".join(
        [
            "本次是 Phase 5.1 True Live Codex Benchmark 的真实正文任务。",
            f"请写完整的第 {chapter} 章小说正文；可见正文最高只到第 {book['boundary']} 章。",
            f"最近可见章节字符数中位数约为 {median}；{low}–{high} 只是 soft target，偏离不得自行判定失败。",
            "正文必须是场景化小说，不得写测试说明、合同复述、字段清单或工程解释。",
            "正文不得出现 Runtime、Baseline、Earned Surface、Canon、Projection、Validator、Distill、thread_status、resource_cost、character_boundary、融合层等工程术语。",
            "Runtime 信息只能通过人物行动、限制、代价、关系或现场反馈体现，不能直接把 Runtime 字段写进正文。",
            "必须按 output schema 给每个 state_change 提供正文逐字短证据；不得修改 book、Canon 或 Edition。",
        ]
    )


def _prepare_candidate(
    state: dict[str, Any], book: dict[str, Any], *, chapter: int, second: bool = False
) -> dict[str, Any]:
    database = _database(book)
    include_runtime = book["variant"] in {"B", "C"}
    if second:
        previous = book["chapters"][str(book["boundary"] + 1)]
        base = previous["candidate_task"]
        provisional = previous["provisional_state"]
        operation_id = stable_id(
            "phase5-live-candidate",
            str(base["task_id"]),
            str(chapter),
            str(previous["draft_import"]["draft_id"]),
        )
        operation = ensure_operation(
            database,
            str(book["book_id"]),
            "base",
            operation_id,
            "PLAN_NEXT",
            {"benchmark_stage": "N_PLUS_2_CANDIDATE", "previous_chapter": book["boundary"] + 1},
        )
        if operation is None:
            raise LiveBenchmarkError("canonical Book 未能创建 N+2 candidate operation")
        base_input = Path(str(base["input"])).read_text(encoding="utf-8")
        previous_prose = Path(str(previous["draft_import"]["path"])).read_text(encoding="utf-8")
        input_path = operation.input / "input.md"
        _write_text(
            input_path,
            base_input
            + "\n\n## Previous VALIDATED_DRAFT provisional chapter\n\n"
            + previous_prose
            + "\n\n## Previous provisional state\n\n"
            + json_dumps(provisional, indent=2),
        )
        _write_text(operation.input / "schema.json", Path(str(base["schema"])).read_text(encoding="utf-8"))
        metadata = _task_metadata(base)
        metadata.update(
            {
                "task_id": operation_id,
                "created_at": utc_now(),
                "target_chapter": chapter,
                "benchmark_protocol": _operation_protocol(
                    state=state,
                    book=book,
                    chapter=chapter,
                    stage="N_PLUS_2_CANDIDATE",
                    include_runtime_state=include_runtime,
                    previous_provisional=provisional,
                ),
                "previous_provisional_state": provisional,
            }
        )
        _write_json(operation.input / "task.json", metadata)
        task = {
            "task_id": operation_id,
            "boundary_packet_id": base.get("boundary_packet_id"),
            "input": str(input_path),
            "schema": str(operation.input / "schema.json"),
            "expected_output": str(operation.output / "output.json"),
            "top_threads": base.get("top_threads", []),
            "aggregate_id": base.get("aggregate_id"),
            "bundle_hash": base.get("bundle_hash"),
        }
        _append_directive(input_path, _candidate_directive(book, chapter))
    else:
        task = prepare_candidate_task(
            database,
            str(book["book_id"]),
            load_settings(),
            edition_id="base",
            include_runtime_state=include_runtime,
        )
        metadata = _augment_operation_task(
            task,
            protocol=_operation_protocol(
                state=state,
                book=book,
                chapter=chapter,
                stage="N_PLUS_1_CANDIDATE",
                include_runtime_state=include_runtime,
            ),
            directive=_candidate_directive(book, chapter),
        )
    context = _context_manifest(
        state,
        book,
        task=task,
        chapter=chapter,
        stage="candidate",
        expected_runtime=include_runtime,
        previous_provisional=(
            book["chapters"][str(book["boundary"] + 1)].get("provisional_state")
            if second
            else None
        ),
    )
    return {
        "task_id": str(task["task_id"]),
        "operation_id": str(task["task_id"]),
        "handoff_id": None,
        "input": str(task["input"]),
        "schema": str(task["schema"]),
        "expected_output": str(task["expected_output"]),
        "prepared_at": metadata.get("created_at"),
        "include_runtime_state": include_runtime,
        "context_manifest": str(
            Path(str(book["benchmark_root"]))
            / "context_manifests"
            / f"chapter_{chapter:03d}_candidate.json"
        ),
        "context": context,
    }


def _prepare_draft(
    state: dict[str, Any],
    book: dict[str, Any],
    *,
    chapter: int,
    contract_id: str,
    second: bool = False,
) -> dict[str, Any]:
    include_runtime = book["variant"] == "B"
    task = prepare_draft_task(
        _database(book),
        str(book["book_id"]),
        contract_id,
        edition_id="base",
        include_runtime_state=include_runtime,
    )
    metadata = _augment_operation_task(
        task,
        protocol=_operation_protocol(
            state=state,
            book=book,
            chapter=chapter,
            stage="N_PLUS_2_DRAFT" if second else "N_PLUS_1_DRAFT",
            include_runtime_state=include_runtime,
            previous_provisional=(
                book["chapters"][str(book["boundary"] + 1)].get("provisional_state")
                if second
                else None
            ),
        ),
        directive=_draft_directive(book, chapter),
    )
    if second:
        previous = book["chapters"][str(book["boundary"] + 1)]
        previous_prose = Path(str(previous["draft_import"]["path"])).read_text(encoding="utf-8")
        _append_directive(
            Path(str(task["input"])),
            "上一章 VALIDATED_DRAFT provisional 正文如下；必须真正承接它，不得从 boundary 独立重置。\n\n"
            + previous_prose,
        )
    context = _context_manifest(
        state,
        book,
        task=task,
        chapter=chapter,
        stage="draft",
        expected_runtime=include_runtime,
        previous_provisional=(
            book["chapters"][str(book["boundary"] + 1)].get("provisional_state")
            if second
            else None
        ),
    )
    return {
        "task_id": str(task["task_id"]),
        "operation_id": str(task["task_id"]),
        "handoff_id": None,
        "contract_id": contract_id,
        "input": str(task["input"]),
        "schema": str(task["schema"]),
        "expected_output": str(task["expected_output"]),
        "prepared_at": metadata.get("created_at"),
        "include_runtime_state": include_runtime,
        "context_manifest": str(
            Path(str(book["benchmark_root"]))
            / "context_manifests"
            / f"chapter_{chapter:03d}_draft.json"
        ),
        "context": context,
    }


def _selected_candidate(task: dict[str, Any], selected_id: str) -> dict[str, Any]:
    output = CandidateOutput.model_validate_json(
        Path(str(task["expected_output"])).read_text(encoding="utf-8")
    )
    for candidate in output.candidates:
        if stable_id("candidate", str(task["task_id"]), candidate.local_id) == selected_id:
            return candidate.model_dump(mode="json")
    raise LiveBenchmarkError(f"候选输出找不到 selected_candidate_id：{selected_id}")


def _provisional_contract(
    *,
    base_contract: ChapterContract,
    selected: dict[str, Any],
    selected_id: str,
    chapter: int,
) -> ChapterContract:
    values = base_contract.model_dump(mode="python")
    values.update(
        {
            "contract_id": stable_id(
                "phase5-live-contract",
                str(base_contract.contract_id),
                selected_id,
                str(chapter),
            ),
            "chapter": chapter,
            "candidate_id": selected_id,
            "primary_thread": selected["primary_thread_id"],
            "primary_function": selected["primary_function"],
            "secondary_functions": selected.get("secondary_functions", []),
            "reader_question": selected["reader_question"],
            "pressure": {
                "before": selected["pressure_before"],
                "target_after": selected["pressure_target_after"],
            },
            "payoff_plan": {
                "causal_sources": selected["causal_sources"],
                "state_changes": selected["state_changes"],
                "must_change_behavior": selected["commit_updates"],
            },
            "required_irreversible_change": selected["required_irreversible_change"],
            "required_cost": selected["required_cost"],
            "canon_constraints": selected.get("canon_constraints", []),
            "knowledge_constraints": selected.get("knowledge_constraints", []),
            "must_not_resolve": selected.get("must_not_resolve", []),
            "forbidden_repetitions": selected.get("forbidden_repetitions", []),
            "style_constraints": selected.get("style_constraints", {}),
            "ending_state": selected["ending_state"],
            "commit_updates": selected["commit_updates"],
            "lens": selected["lens"],
            "novelty_provenance": selected.get("novelty_provenance", []),
        }
    )
    return ChapterContract.model_validate(values)


def _insert_provisional_contract(database: Database, book_id: str, contract: ChapterContract) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO chapter_contracts(
                contract_id, book_id, candidate_id, target_chapter_ordinal,
                mode, contract_json, contract_sha256, status, created_at, version,
                edition_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'READY', ?, 1, 'base')
            """,
            (
                contract.contract_id,
                book_id,
                contract.candidate_id,
                contract.chapter,
                contract.mode.value,
                json_dumps(contract.model_dump(mode="json")),
                "phase5.1-live-provisional-contract",
                utc_now(),
            ),
        )


def _provisional_state(
    book: dict[str, Any],
    *,
    chapter: int,
    contract: ChapterContract,
    draft: DraftOutput,
) -> dict[str, Any]:
    metadata = _task_metadata(book["chapters"][str(book["boundary"] + 1)]["draft_task"])
    provisional = BatchProvisionalState(
        current_chapter_ordinal=chapter,
        canon_projection_hash=str(metadata.get("base_projection_hash", "")),
        source_manifest_sha256=str(metadata.get("source_manifest_sha256", "")),
        effective_content_sha256=str(metadata.get("effective_content_sha256", "")),
        registry_hash=str(metadata.get("registry_hash", "")),
        config_hash=str(metadata.get("config_hash", "")),
        author_directives_hash=str(metadata.get("author_directives_hash", "")),
        metric_bundle_hash=str(metadata.get("metric_bundle_hash", "")),
        provisional_events=[
            {
                "chapter": chapter,
                "contract_id": contract.contract_id,
                "draft_id": draft.task_id,
                "status": "PROVISIONAL",
            }
        ],
        provisional_threads=[
            {
                "thread_id": change.record_id,
                "status": "PROVISIONAL",
                "evidence": change.evidence_quotes[0],
            }
            for change in draft.state_changes
            if change.kind == "thread"
        ],
        unresolved_questions=[contract.reader_question],
    )
    path = Path(str(book["benchmark_root"])) / "provisional" / f"chapter_{chapter:03d}.json"
    _write_json(path, provisional.model_dump(mode="json"))
    return provisional.model_dump(mode="json")


def _require_outputs(state: dict[str, Any], field: str, stage: str) -> None:
    missing = []
    for book in _ordered_books(state):
        for chapter in book["chapters"].values():
            task = chapter.get(field)
            if task and not Path(str(task["expected_output"])).is_file():
                missing.append(f"{book['book_id']}:{task['task_id']}")
    if missing:
        raise LiveBenchmarkError(
            f"collect 拒绝推进 {stage}：以下 Codex Desktop operation 尚未完成 output.json："
            + ", ".join(missing)
        )


def _record_output_timestamp(path: Path, prepared_at: object) -> dict[str, Any]:
    return {
        "generation_timestamp": _now_from_mtime(path),
        "generation_timestamp_source": "output_file_mtime",
        "output_observed_at": utc_now(),
        "task_created_at": prepared_at,
    }


def _collect_distill(state: dict[str, Any]) -> None:
    pending: list[str] = []
    for book in _ordered_books(state):
        if book["distill"]["imported"]:
            continue
        database = _database(book)
        handoff = get_handoff(database, str(book["distill"]["handoff_id"]))
        book["distill"]["status"] = handoff["status"]
        if handoff["status"] != HandoffStatus.COMPLETED.value:
            pending.append(f"{book['book_id']}:{handoff['status']}")
    if pending:
        raise LiveBenchmarkError(
            "collect 拒绝推进 Distill：所有 READY_FOR_CODEX handoff 必须先由 Codex Desktop 完成；"
            + ", ".join(pending)
        )
    for book in _ordered_books(state):
        if book["distill"]["imported"]:
            continue
        _visible_and_hidden_audit(state, book)
        database = _database(book)
        result = import_distill_result(
            database, str(book["book_id"]), str(book["distill"]["handoff_id"])
        )
        handoff = get_handoff(database, str(book["distill"]["handoff_id"]))
        book["distill"].update(
            {
                "imported": True,
                "status": HandoffStatus.COMPLETED.value,
                "result": result,
                "output_artifact": str(
                    Path(str(book["distill"]["task_directory"])) / "artifacts" / "distill_skill"
                ),
                "input_context_manifest": str(
                    Path(str(book["distill"]["task_directory"])) / "input" / "context_manifest.json"
                ),
                "completed_at": (handoff.get("result") or {}).get("completed_at"),
            }
        )
        _distill_context_manifest(state, book, {"handoff_id": book["distill"]["handoff_id"], "task_directory": book["distill"]["task_directory"]})
    for book in _ordered_books(state):
        first = str(int(book["boundary"]) + 1)
        if not book["chapters"][first].get("candidate_task"):
            book["chapters"][first]["candidate_task"] = _prepare_candidate(
                state, book, chapter=int(book["boundary"]) + 1
            )


def _collect_candidate(state: dict[str, Any], *, chapter_offset: int) -> None:
    chapter_number = chapter_offset
    field = "candidate_task"
    for book in _ordered_books(state):
        chapter = book["chapters"][str(int(book["boundary"]) + chapter_number)]
        if not chapter.get(field):
            raise LiveBenchmarkError("候选 task 尚未由 collect prepare")
    _require_outputs(state, field, f"N+{chapter_number} candidate")
    for book in _ordered_books(state):
        ordinal = int(book["boundary"]) + chapter_number
        chapter = book["chapters"][str(ordinal)]
        if chapter.get("candidate_import"):
            continue
        _visible_and_hidden_audit(state, book)
        task = chapter[field]
        output_path = Path(str(task["expected_output"]))
        imported = import_candidate_output(
            _database(book),
            str(book["book_id"]),
            str(task["task_id"]),
            load_settings(),
            output_path,
            edition_id="base",
            include_runtime_state=book["variant"] in {"B", "C"},
        )
        contract_result = build_chapter_contract(
            _database(book),
            str(book["book_id"]),
            str(imported["selected_candidate_id"]),
            edition_id="base",
        )
        contract = ChapterContract.model_validate_json(
            Path(str(contract_result["path"])).read_text(encoding="utf-8")
        )
        chapter["candidate_import"] = {
            **imported,
            **_record_output_timestamp(output_path, task.get("prepared_at")),
            "input_context_manifest": task["context_manifest"],
        }
        chapter["contract"] = {
            **contract_result,
            "input_context_manifest": task["context_manifest"],
            "source": "live Codex CandidateOutput selected by Python deterministic contract builder",
        }
        chapter["candidate_selected"] = _selected_candidate(
            task, str(imported["selected_candidate_id"])
        )
        chapter["draft_task"] = _prepare_draft(
            state,
            book,
            chapter=ordinal,
            contract_id=str(contract.contract_id),
        )


def _collect_draft(state: dict[str, Any], *, chapter_offset: int) -> None:
    field = "draft_task"
    for book in _ordered_books(state):
        ordinal = int(book["boundary"]) + chapter_offset
        chapter = book["chapters"][str(ordinal)]
        if not chapter.get(field):
            raise LiveBenchmarkError("正文 task 尚未由 collect prepare")
    _require_outputs(state, field, f"N+{chapter_offset} draft")
    for book in _ordered_books(state):
        ordinal = int(book["boundary"]) + chapter_offset
        chapter = book["chapters"][str(ordinal)]
        if chapter.get("draft_import") and chapter.get("validation", {}).get("passed"):
            continue
        _visible_and_hidden_audit(state, book)
        task = chapter[field]
        output_path = Path(str(task["expected_output"]))
        draft_output = DraftOutput.model_validate_json(output_path.read_text(encoding="utf-8"))
        imported = import_draft_output(
            _database(book),
            str(book["book_id"]),
            str(task["task_id"]),
            output_path,
            edition_id="base",
        )
        validation = validate_draft(
            _database(book),
            str(book["book_id"]),
            str(imported["draft_id"]),
            load_settings(),
            edition_id="base",
            include_runtime_state=book["variant"] == "B",
        )
        validation_payload = validation.model_dump(mode="json")
        validation_path = (
            Path(str(book["benchmark_root"]))
            / "validation"
            / f"chapter_{ordinal:03d}.json"
        )
        _write_json(validation_path, validation_payload)
        chapter["draft_import"] = {
            **imported,
            **_record_output_timestamp(output_path, task.get("prepared_at")),
            "output_path": str(output_path),
            "input_context_manifest": task["context_manifest"],
            "prose_markdown": draft_output.prose_markdown,
        }
        chapter["validation"] = {
            "path": str(validation_path),
            "passed": validation.passed,
            "validator_count": len(validation.reports),
            "payload": validation_payload,
        }
        if not validation.passed:
            raise LiveBenchmarkError(
                f"{book['book_id']} 第 {ordinal} 章 Validator 未通过；已保留 output/draft/validation，不能关闭 generation"
            )
        if chapter_offset == 1:
            provisional = _provisional_state(
                book,
                chapter=ordinal,
                contract=ChapterContract.model_validate_json(
                    Path(str(chapter["contract"]["path"])).read_text(encoding="utf-8")
                ),
                draft=draft_output,
            )
            chapter["provisional_state"] = provisional
    if chapter_offset == 1:
        for book in _ordered_books(state):
            second = str(int(book["boundary"]) + 2)
            if not book["chapters"][second].get("candidate_task"):
                book["chapters"][second]["candidate_task"] = _prepare_candidate(
                    state, book, chapter=int(book["boundary"]) + 2, second=True
                )


def _collect_candidate_two(state: dict[str, Any]) -> None:
    for book in _ordered_books(state):
        ordinal = int(book["boundary"]) + 2
        if not book["chapters"][str(ordinal)].get("candidate_task"):
            raise LiveBenchmarkError("N+2 candidate task 尚未由 collect prepare")
    _require_outputs(state, "candidate_task", "N+2 candidate")
    for book in _ordered_books(state):
        ordinal = int(book["boundary"]) + 2
        chapter = book["chapters"][str(ordinal)]
        if chapter.get("candidate_import"):
            continue
        _visible_and_hidden_audit(state, book)
        task = chapter["candidate_task"]
        output_path = Path(str(task["expected_output"]))
        imported = import_candidate_output(
            _database(book),
            str(book["book_id"]),
            str(task["task_id"]),
            load_settings(),
            output_path,
            edition_id="base",
            include_runtime_state=book["variant"] in {"B", "C"},
        )
        selected = _selected_candidate(task, str(imported["selected_candidate_id"]))
        base_contract = ChapterContract.model_validate_json(
            Path(
                str(book["chapters"][str(int(book["boundary"]) + 1)]["contract"]["path"])
            ).read_text(encoding="utf-8")
        )
        provisional_contract = _provisional_contract(
            base_contract=base_contract,
            selected=selected,
            selected_id=str(imported["selected_candidate_id"]),
            chapter=ordinal,
        )
        _insert_provisional_contract(_database(book), str(book["book_id"]), provisional_contract)
        chapter["candidate_import"] = {
            **imported,
            **_record_output_timestamp(output_path, task.get("prepared_at")),
            "input_context_manifest": task["context_manifest"],
        }
        contract_path = Path(str(book["benchmark_root"])) / "contracts" / f"chapter_{ordinal:03d}.json"
        _write_json(contract_path, provisional_contract.model_dump(mode="json"))
        chapter["contract"] = {
            "contract_id": provisional_contract.contract_id,
            "candidate_id": provisional_contract.candidate_id,
            "chapter": ordinal,
            "path": str(contract_path),
            "database_contract_path": str(
                BookLayout(Path(str(book["root"])).parent).for_book(str(book["book_id"])).edition("base").contracts
                / f"{provisional_contract.contract_id}.json"
            ),
            "source": "live Codex CandidateOutput selected by Python deterministic provisional contract builder",
        }
        chapter["candidate_selected"] = selected
        chapter["draft_task"] = _prepare_draft(
            state,
            book,
            chapter=ordinal,
            contract_id=provisional_contract.contract_id,
            second=True,
        )


def _close_generation(state: dict[str, Any]) -> None:
    for book in _ordered_books(state):
        first = book["chapters"][str(int(book["boundary"]) + 1)]
        second = book["chapters"][str(int(book["boundary"]) + 2)]
        if not first.get("validation", {}).get("passed") or not second.get("validation", {}).get("passed"):
            raise LiveBenchmarkError("不能在两章都通过 Validator 前关闭 generation")
        snapshot = {
            "schema_version": "phase5.1-generation-snapshot-v1",
            "generation_closed": True,
            "truth_revealed": False,
            "visible_boundary": book["boundary"],
            "generated_chapters": [book["boundary"] + 1, book["boundary"] + 2],
            "hidden_truth_loaded": False,
            "canon_committed": False,
            "edition_activated": False,
        }
        _write_json(Path(str(book["benchmark_root"])) / "generation_snapshot.json", snapshot)
        book["generation_closed"] = True
    state["generation_closed"] = True


def _current_stage(state: dict[str, Any]) -> str:
    if not all(book["distill"]["imported"] for book in _ordered_books(state)):
        return "DISTILL"
    if any(not book["chapters"][str(int(book["boundary"]) + 1)].get("candidate_task") for book in _ordered_books(state)):
        return "N_PLUS_1_CANDIDATE_PREPARED_BY_COLLECT"
    if any(not book["chapters"][str(int(book["boundary"]) + 1)].get("candidate_import") for book in _ordered_books(state)):
        return "N_PLUS_1_CANDIDATE"
    if any(not book["chapters"][str(int(book["boundary"]) + 1)].get("draft_task") for book in _ordered_books(state)):
        return "N_PLUS_1_DRAFT_PREPARED_BY_COLLECT"
    if any(not book["chapters"][str(int(book["boundary"]) + 1)].get("draft_import") for book in _ordered_books(state)):
        return "N_PLUS_1_DRAFT"
    if any(not book["chapters"][str(int(book["boundary"]) + 2)].get("candidate_task") for book in _ordered_books(state)):
        return "N_PLUS_2_CANDIDATE_PREPARED_BY_COLLECT"
    if any(not book["chapters"][str(int(book["boundary"]) + 2)].get("candidate_import") for book in _ordered_books(state)):
        return "N_PLUS_2_CANDIDATE"
    if any(not book["chapters"][str(int(book["boundary"]) + 2)].get("draft_task") for book in _ordered_books(state)):
        return "N_PLUS_2_DRAFT_PREPARED_BY_COLLECT"
    if any(not book["chapters"][str(int(book["boundary"]) + 2)].get("draft_import") for book in _ordered_books(state)):
        return "N_PLUS_2_DRAFT"
    return "GENERATION_CLOSED" if state.get("generation_closed") else "READY_TO_CLOSE"


def _collect_run(state: dict[str, Any]) -> dict[str, Any]:
    stage = _current_stage(state)
    if stage == "DISTILL":
        _collect_distill(state)
    elif stage == "N_PLUS_1_CANDIDATE":
        _collect_candidate(state, chapter_offset=1)
    elif stage == "N_PLUS_1_DRAFT":
        _collect_draft(state, chapter_offset=1)
    elif stage == "N_PLUS_2_CANDIDATE":
        _collect_candidate_two(state)
    elif stage == "N_PLUS_2_DRAFT":
        _collect_draft(state, chapter_offset=2)
    elif stage == "READY_TO_CLOSE":
        _close_generation(state)
    elif stage == "GENERATION_CLOSED":
        return _status_summary(state)
    else:
        raise LiveBenchmarkError(f"collect 状态不一致：{stage}")
    _visible_all_tasks_audit(state)
    _write_queue(state)
    _save_state(state)
    return _status_summary(state)


def _visible_all_tasks_audit(state: dict[str, Any]) -> None:
    for book in _ordered_books(state):
        _visible_and_hidden_audit(state, book)


def _task_line(
    number: int,
    label: str,
    task_id: str,
    input_path: str,
    output_path: str,
    handoff_id: str | None,
) -> str:
    return "\n".join(
        [
            f"### {number}. {label}",
            "",
            f"- handoff_id: `{handoff_id or 'N/A — canonical Operation handoff'}`",
            f"- task_id / operation_id: `{task_id}`",
            f"- input: `{input_path}`",
            f"- expected output: `{output_path}`",
            "- Codex Desktop：读取 input/task.json/schema，写 expected output；不要修改 book/、Canon 或 Edition。",
        ]
    )


def _write_queue(state: dict[str, Any]) -> None:
    lines = [
        "# Phase 5.1 True Live Codex Handoff Work Queue",
        "",
        f"Run label: `{state['run_label']}`",
        "",
        "本队列不包含 hidden truth 路径。所有文学语义、候选和正文必须由 Windows Codex Desktop 在对应文件 handoff 中生成；Python 只负责 prepare/collect/evaluate。",
        "",
        "固定顺序：先完成四个 Distill handoff，再按 N+1 Candidate → N+1 Draft → N+2 Candidate → N+2 Draft 滚动推进。每次完成当前阶段后运行 collect；未完成时 collect 会拒绝推进。",
        "",
        "## Distill",
        "",
    ]
    number = 1
    for book in _ordered_books(state):
        distill = book["distill"]
        lines.append(
            _task_line(
                number,
                f"{book['variant']}{book['boundary']} Distill",
                str(distill["handoff_id"]),
                str(Path(str(distill["task_directory"])) / "input" / "prompt.md"),
                str(Path(str(distill["task_directory"])) / "result.json"),
                str(distill["handoff_id"]),
            )
        )
        number += 1
    for chapter_offset, stage_label in ((1, "Candidate"), (1, "Draft"), (2, "Candidate"), (2, "Draft")):
        lines.extend(["", f"## N+{chapter_offset} {stage_label}", ""])
        for book in _ordered_books(state):
            ordinal = int(book["boundary"]) + chapter_offset
            chapter = book["chapters"][str(ordinal)]
            key = "candidate_task" if stage_label == "Candidate" else "draft_task"
            task = chapter.get(key)
            if task is None:
                lines.append(f"- {book['variant']}{book['boundary']} 第 {ordinal} 章：等待前一阶段 collect 准备。")
            else:
                lines.append(
                    _task_line(
                        number,
                        f"{book['variant']}{book['boundary']} 第 {ordinal} {stage_label}",
                        str(task["task_id"]),
                        str(task["input"]),
                        str(task["expected_output"]),
                        task.get("handoff_id"),
                    )
                )
                number += 1
    lines.extend(
        [
            "",
            "## Operator commands",
            "",
            "1. Distill：使用 `$process-novel-handoff` 领取对应 handoff，再调用 `$distill-novels`；完成后保持 `DISTILLED`，由 collect/import 发布。",
            "2. Candidate/Draft：使用对应 task input/schema，在 expected output 写真实结构化结果；不要调用 API、codex exec 或 subprocess。",
            f"3. 当前阶段完成后：`python scripts/phase5_live_ab.py collect --run-label {state['run_label']}`。",
            f"4. 两章全部完成且 Validator 通过后才会写 generation_closed=true；随后才可运行 `python scripts/phase5_live_ab.py evaluate --run-label {state['run_label']}`。",
        ]
    )
    queue = "\n".join(lines) + "\n"
    queue_path = Path(str(state["run_root"])) / "WORK_QUEUE.md"
    pointer_path = Path(str(state["controller_root"])) / "WORK_QUEUE.md"
    _write_text(queue_path, queue)
    _write_text(pointer_path, queue)
    if HIDDEN_DIR_NAME.casefold() in queue.casefold() or str(Path(str(state["hidden_root"])).resolve()).casefold() in queue.casefold():
        raise LiveBenchmarkError("WORK_QUEUE 泄漏 hidden truth 路径")


def _status_summary(state: dict[str, Any]) -> dict[str, Any]:
    books = []
    for book in _ordered_books(state):
        database = _database(book)
        handoff = get_handoff(database, str(book["distill"]["handoff_id"]))
        chapters = {}
        for ordinal, chapter in book["chapters"].items():
            chapters[ordinal] = {
                "candidate_task": None if not chapter.get("candidate_task") else chapter["candidate_task"]["task_id"],
                "candidate_output": bool(
                    chapter.get("candidate_task")
                    and Path(str(chapter["candidate_task"]["expected_output"])).is_file()
                ),
                "candidate_imported": bool(chapter.get("candidate_import")),
                "draft_task": None if not chapter.get("draft_task") else chapter["draft_task"]["task_id"],
                "draft_output": bool(
                    chapter.get("draft_task")
                    and Path(str(chapter["draft_task"]["expected_output"])).is_file()
                ),
                "draft_imported": bool(chapter.get("draft_import")),
                "validated": bool(chapter.get("validation", {}).get("passed")),
            }
        books.append(
            {
                "book_id": book["book_id"],
                "variant": book["variant"],
                "boundary": book["boundary"],
                "distill_handoff_id": book["distill"]["handoff_id"],
                "distill_status": handoff["status"],
                "chapters": chapters,
                "generation_closed": book["generation_closed"],
                "truth_revealed": book["truth_revealed"],
            }
        )
    return {
        "schema_version": STATE_SCHEMA,
        "run_label": state["run_label"],
        "phase": _current_stage(state),
        "generation_closed": state.get("generation_closed", False),
        "truth_revealed": state.get("truth_revealed", False),
        "work_queue": str(Path(str(state["controller_root"])) / "WORK_QUEUE.md"),
        "books": books,
    }


def _token_overlap(left: str, right: str) -> float:
    def tokens(value: str) -> set[str]:
        return set(re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", value))

    first, second = tokens(left), tokens(right)
    return round(len(first & second) / max(len(first | second), 1), 4)


def _system_language_leaks(book: dict[str, Any]) -> list[dict[str, Any]]:
    leaks: list[dict[str, Any]] = []
    for ordinal, chapter in book["chapters"].items():
        draft_import = chapter.get("draft_import")
        if not draft_import:
            continue
        output_path = Path(str(draft_import["output_path"]))
        payload = _read_json(output_path)
        prose = str(payload.get("prose_markdown", ""))
        lowered = prose.casefold()
        found = [term for term in SYSTEM_LANGUAGE_TERMS if term.casefold() in lowered]
        if found:
            leaks.append({"chapter": int(ordinal), "terms": sorted(set(found)), "output": str(output_path)})
    return leaks


def _runtime_usage(book: dict[str, Any]) -> dict[str, Any]:
    names: list[str] = []
    baseline_path = Path(str(book["benchmark_root"])) / "runtime_baseline_input.json"
    if baseline_path.is_file():
        payload = _read_json(baseline_path)
        names = [str(item.get("name")) for item in payload.get("entries", []) if isinstance(item, dict)]
    selected_sources: list[str] = []
    prose_mentions = {name: 0 for name in names}
    for chapter in book["chapters"].values():
        selected = chapter.get("candidate_selected", {})
        selected_sources.extend(str(item) for item in selected.get("causal_sources", []))
        prose = str(chapter.get("draft_import", {}).get("prose_markdown", ""))
        for name in names:
            prose_mentions[name] += prose.casefold().count(name.casefold())
    return {
        "selected_candidate_runtime_sources": [item for item in selected_sources if item.startswith("baseline:")],
        "prose_mentions": prose_mentions,
        "capability_reuse": [item for item in selected_sources if "capability" in item.casefold()],
        "resource_reuse": [item for item in selected_sources if "resource" in item.casefold()],
        "actionable_knowledge": [item for item in selected_sources if "knowledge" in item.casefold()],
        "relationship_leverage": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "setup_payoff_use": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
    }


def _safety_review(book: dict[str, Any]) -> dict[str, Any]:
    selected = []
    for chapter in book["chapters"].values():
        candidate = chapter.get("candidate_selected", {})
        selected.extend(candidate.get("novelty_provenance", []))
    retroactive = [
        item
        for item in selected
        if item.get("retroactive_claim")
        or str(item.get("novelty_boundary")) == "RETROACTIVE_UNSUPPORTED_INVENTION"
    ]
    after = _safety_state(_database(book), str(book["book_id"]))
    return {
        "retroactive_unsupported_invention": retroactive,
        "unsupported_capability": "REVIEW_REQUIRED_FROM_SOURCE_AND_VALIDATION",
        "unsupported_resource": "REVIEW_REQUIRED_FROM_SOURCE_AND_VALIDATION",
        "knowledge_violation": "REVIEW_REQUIRED_FROM_KNOWLEDGE_VALIDATOR",
        "timeline_conflict": "REVIEW_REQUIRED_FROM_TIMELINE_VALIDATOR",
        "rule_conflict": "REVIEW_REQUIRED_FROM_ECONOMY_POWER_VALIDATOR",
        "state_invariants": _safety_compare(book["safety_before"], after),
    }


def _forward_novelty_review(book: dict[str, Any]) -> dict[str, Any]:
    declarations: list[dict[str, Any]] = []
    for ordinal, chapter in book["chapters"].items():
        selected = chapter.get("candidate_selected", {})
        for declaration in selected.get("novelty_provenance", []):
            declarations.append({"chapter": int(ordinal), **declaration})
    return {
        "new_person": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "new_threat": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "new_location": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "new_item": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "new_discovery": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "new_transaction": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "new_relationship": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "new_social_structure": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "new_rule_manifestation": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "candidate_declarations": declarations,
        "causal": all(bool(item.get("causal_source")) for item in declarations),
        "non_retroactive": not any(
            bool(item.get("retroactive_claim"))
            or str(item.get("novelty_boundary")) == "RETROACTIVE_UNSUPPORTED_INVENTION"
            for item in declarations
        ),
        "meaningful": all(
            bool(chapter.get("candidate_selected", {}).get("required_irreversible_change"))
            and bool(chapter.get("candidate_selected", {}).get("required_cost"))
            for chapter in book["chapters"].values()
        ),
        "changes_future_choices": all(
            bool(chapter.get("candidate_selected", {}).get("ending_state"))
            for chapter in book["chapters"].values()
        ),
    }


def _literary_review_template(state: dict[str, Any]) -> dict[str, Any]:
    dimensions = list(DIMENSIONS) + [
        "specificity",
        "scene_vividness",
        "character_agency",
        "surprise",
        "causal_novelty",
        "payoff_strength",
        "hook_strength",
    ]
    return {
        "review_state": "REVIEW_REQUIRED",
        "aggregate_score": None,
        "instruction": "逐章人工/独立 Codex review；不要压成唯一文学总分。",
        "dimensions": [
            {"dimension": dimension, "A": "REVIEW_REQUIRED", "B": "REVIEW_REQUIRED", "truth": "REFERENCE_ONLY"}
            for dimension in dimensions
        ],
        "questions": [
            "A 是否比 B 更敢创造新东西？",
            "A 的自由是否带来更多 retroactive hallucination？",
            "B 是否真正利用已有能力/资源，而不仅仅写得更保守？",
            "B 是否出现说明书化？",
            "哪个版本人物行动更自然？",
            "哪个版本世界扩张更自然？",
            "哪个版本章末 hook 更强？",
            "哪个版本更像原书而不是系统文本？",
            "Fused 的哪部分最有价值？",
            "哪些 Runtime 信息可不送给 Draft？",
        ],
    }


def _evaluate_book(state: dict[str, Any], book: dict[str, Any], hidden_book: Path) -> dict[str, Any]:
    hidden_paths = [
        hidden_book / f"chapter_{int(book['boundary']) + 1:03d}.md",
        hidden_book / f"chapter_{int(book['boundary']) + 2:03d}.md",
    ]
    hidden_texts = [path.read_text(encoding="utf-8") for path in hidden_paths]
    leaks = _system_language_leaks(book)
    truth_overlap = {
        str(int(book["boundary"]) + index + 1): _token_overlap(
            str(book["chapters"][str(int(book["boundary"]) + index + 1)]["draft_import"]["prose_markdown"]),
            hidden_text,
        )
        for index, hidden_text in enumerate(hidden_texts)
    }
    result = {
        "schema_version": "phase5.1-live-evaluation-v1",
        "book_id": book["book_id"],
        "variant": book["variant"],
        "boundary": book["boundary"],
        "truth": {
            "revealed_after_generation_closed": True,
            "titles": [
                line.split("##", 1)[1].strip()
                for text in hidden_texts
                for line in text.splitlines()
                if line.startswith("## ")
            ],
            "token_overlap_auxiliary_only": truth_overlap,
        },
        "system_language_leak": {
            "status": "SYSTEM_LANGUAGE_LEAK" if leaks else "CLEAR",
            "findings": leaks,
        },
        "source_safety": {
            "path": state["source"],
            "source_unchanged": _source_unchanged(state),
        },
        "safety": _safety_review(book),
        "earned_asset_usage": _runtime_usage(book),
        "forward_novelty": _forward_novelty_review(book),
        "generation": {
            "chapters": [book["boundary"] + 1, book["boundary"] + 2],
            "candidate_count_per_chapter": 3,
            "validators": [
                chapter.get("validation", {}).get("validator_count")
                for chapter in book["chapters"].values()
            ],
            "all_validated": all(
                bool(chapter.get("validation", {}).get("passed"))
                for chapter in book["chapters"].values()
            ),
            "generation_closed": book["generation_closed"],
        },
        "literary_review": _literary_review_template(state),
        "artifacts": {
            "distill_handoff_id": book["distill"]["handoff_id"],
            "distill_input_context_manifest": book["distill"].get("input_context_manifest"),
            "distill_output_artifact": book["distill"].get("output_artifact"),
            "distill_generation_timestamp": book["distill"].get("completed_at"),
            "chapters": {
                ordinal: {
                    "candidate_handoff_id": chapter.get("candidate_task", {}).get("handoff_id"),
                    "candidate_task_id": chapter.get("candidate_task", {}).get("task_id"),
                    "candidate_context_manifest": chapter.get("candidate_task", {}).get("context_manifest"),
                    "candidate_output": chapter.get("candidate_task", {}).get("expected_output"),
                    "draft_handoff_id": chapter.get("draft_task", {}).get("handoff_id"),
                    "draft_task_id": chapter.get("draft_task", {}).get("task_id"),
                    "draft_context_manifest": chapter.get("draft_task", {}).get("context_manifest"),
                    "draft_output": chapter.get("draft_task", {}).get("expected_output"),
                    "draft_file": chapter.get("draft_import", {}).get("path"),
                    "generation_timestamps": {
                        "candidate": chapter.get("candidate_import", {}).get("generation_timestamp"),
                        "draft": chapter.get("draft_import", {}).get("generation_timestamp"),
                    },
                }
                for ordinal, chapter in book["chapters"].items()
            },
        },
    }
    _write_json(Path(str(book["benchmark_root"])) / "evaluation.json", result)
    snapshot_path = Path(str(book["benchmark_root"])) / "generation_snapshot.json"
    snapshot = _read_json(snapshot_path)
    snapshot["truth_revealed"] = True
    snapshot["hidden_truth_loaded"] = True
    snapshot["reveal_stage"] = "AFTER_GENERATION_CLOSED"
    _write_json(snapshot_path, snapshot)
    book["truth_revealed"] = True
    return result


def _write_evaluation_report(state: dict[str, Any], evaluations: list[dict[str, Any]]) -> Path:
    report_path = Path(str(state["run_root"])) / "phase5_1_live_generation_ab.md"
    lines = [
        "# Phase 5.1 True Live Codex Handoff Benchmark",
        "",
        f"Run label: `{state['run_label']}`",
        "",
        "本报告只收录在 READY_FOR_CODEX handoff/operation 中由 Windows Codex Desktop 实际写入并经 collect 导入的结果。Python 没有生成 Distill finding、候选剧情、Chapter Contract 文学内容或小说正文。",
        "",
        "## Experimental integrity",
        "",
        f"- boundaries: `{state['boundaries']}`；variants: `{state['variants']}`。",
        "- hidden truth 只在 generation_closed=true 后由 evaluate 读取；Truth 不是唯一正确答案。",
        "- A 禁用 Runtime state；B 为 Candidate + Draft fused；C（若启用）只在 Candidate 使用 Runtime。",
        "- 原始 book/ 只读；未批准 Canon、Edition 或正式续章。",
        "",
        "## Handoff / operation provenance",
        "",
        "| book | chapter | variant | handoff_id | task_id / operation_id | input context manifest | output artifact | generation timestamp |",
        "|---|---:|:---:|---|---|---|---|---|",
    ]
    for evaluation in evaluations:
        artifacts = evaluation["artifacts"]
        lines.append(
            f"| `{evaluation['book_id']}` | Distill | {evaluation['variant']} | `{artifacts['distill_handoff_id']}` | `{artifacts['distill_handoff_id']}` | `{artifacts['distill_input_context_manifest']}` | `{artifacts['distill_output_artifact']}` | `{artifacts['distill_generation_timestamp']}` |"
        )
        for ordinal, item in artifacts["chapters"].items():
            lines.append(
                f"| `{evaluation['book_id']}` | {ordinal} | {evaluation['variant']} | `{item['candidate_handoff_id'] or 'N/A'}` | `{item['candidate_task_id']}` | `{item['candidate_context_manifest']}` | `{item['candidate_output']}` | `{item['generation_timestamps']['candidate']}` |"
            )
            lines.append(
                f"| `{evaluation['book_id']}` | {ordinal} | {evaluation['variant']} | `{item['draft_handoff_id'] or 'N/A'}` | `{item['draft_task_id']}` | `{item['draft_context_manifest']}` | `{item['draft_file']}` | `{item['generation_timestamps']['draft']}` |"
            )
    lines.extend(
        [
            "",
            "## Safety / engineering leakage",
            "",
        ]
    )
    for evaluation in evaluations:
        lines.append(
            f"- `{evaluation['book_id']}`: SYSTEM_LANGUAGE_LEAK=`{evaluation['system_language_leak']['status']}`; source_unchanged=`{evaluation['source_safety']['source_unchanged']}`; safety=`{evaluation['safety']['state_invariants']}`."
        )
    lines.extend(
        [
            "",
            "## Nine dimensions and extended literary review",
            "",
            "九维（worldbuilding、characters、plot、style、narrative、dialogue、pacing、themes、continuity）以及 specificity、scene vividness、character agency、surprise、causal novelty、payoff strength、hook strength 均保留逐章 A/B/Truth review，不压成唯一总分。若 literary_review.json 未经人工填写，状态保持 REVIEW_REQUIRED。",
            "",
            "## Runtime ablation questions",
            "",
            "请依据每个 evaluation.json 的 earned_asset_usage、forward_novelty、system_language_leak 和正文逐章审阅回答：A 是否更敢创造、A 是否更容易 retroactive hallucination、B 是否真实使用 Runtime、B 是否说明书化、哪个版本人物行动/世界扩张/hook 更自然、哪些 Runtime 信息可从 Draft 移除。",
            "",
            "## State boundary",
            "",
            "所有结果停在 VALIDATED_DRAFT/benchmark artifact；evaluate 不会批准 Canon。",
        ]
    )
    _write_text(report_path, "\n".join(lines))
    return report_path


def _evaluate_run(state: dict[str, Any]) -> dict[str, Any]:
    if not all(bool(book.get("generation_closed")) for book in _ordered_books(state)):
        raise LiveBenchmarkError("evaluate 拒绝执行：所有 Book 必须先 generation_closed=true")
    if state.get("truth_revealed"):
        raise LiveBenchmarkError("该 run 已揭示 hidden truth，拒绝重复 evaluate")
    if not _source_unchanged(state):
        raise LiveBenchmarkError("evaluate 拒绝执行：原始 source 在 benchmark 期间发生变化")
    _visible_all_tasks_audit(state)
    hidden_root = Path(str(state["hidden_root"])).resolve()
    if not hidden_root.is_dir():
        raise LiveBenchmarkError("controller hidden truth 目录不存在")
    evaluations: list[dict[str, Any]] = []
    for book in _ordered_books(state):
        hidden_book = hidden_root / str(book["hidden_controller_key"])
        if not hidden_book.is_dir():
            raise LiveBenchmarkError(f"hidden truth 不完整：{book['book_id']}")
        evaluation = _evaluate_book(state, book, hidden_book)
        evaluations.append(evaluation)
    state["truth_revealed"] = True
    report = _write_evaluation_report(state, evaluations)
    _write_json(
        Path(str(state["run_root"])) / "evaluation.json",
        {
            "schema_version": "phase5.1-live-evaluation-v1",
            "run_label": state["run_label"],
            "truth_revealed": True,
            "report": str(report),
            "books": evaluations,
        },
    )
    _write_queue(state)
    _save_state(state)
    return {"report": str(report), "truth_revealed": True, "books": evaluations}


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 5.1 True Live Codex Handoff Benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--run-label", default="v1")
    prepare.add_argument("--source", type=Path, default=SOURCE)
    prepare.add_argument("--include-c", action="store_true")
    prepare.add_argument("--controller-root", type=Path, default=None)
    prepare.add_argument("--hidden-root", type=Path, default=None)
    prepare.add_argument("--library-root", type=Path, default=None)
    for command in ("status", "collect", "evaluate"):
        item = subparsers.add_parser(command)
        item.add_argument("--run-label", default="v1")
        item.add_argument("--controller-root", type=Path, default=None)
    return parser


def main() -> None:
    args = _argument_parser().parse_args()
    try:
        if args.command == "prepare":
            result = _prepare_run(
                run_label=str(args.run_label),
                source=Path(args.source),
                controller_root=args.controller_root,
                hidden_root=args.hidden_root,
                library_root=args.library_root,
                include_c=bool(args.include_c),
            )
        else:
            state = _load_state(str(args.run_label), controller_root=args.controller_root)
            if args.command == "status":
                result = _status_summary(state)
            elif args.command == "collect":
                result = _collect_run(state)
            else:
                result = _evaluate_run(state)
    except (LiveBenchmarkError, OSError, ValueError, RuntimeError) as exc:
        print(str(exc), flush=True)
        raise SystemExit(2) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
