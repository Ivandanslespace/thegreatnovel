"""Phase 6 true-live InnovationControl benchmark.

This controller is intentionally boring about literature.  It freezes isolated
Books, creates the same READY_FOR_CODEX file handoffs, collects typed outputs,
closes the generation, and only then reads controller-owned hidden truth.  It
does not contain nine-dimensional answers, candidate prose, Chapter Contract
literary content, or novel prose.  Those artifacts must be written by the
Windows Codex Desktop operation that owns each handoff.

Commands::

    python scripts/phase6_innovation_control.py prepare
    python scripts/phase6_innovation_control.py status --run-label v1
    python scripts/phase6_innovation_control.py collect --run-label v1
    python scripts/phase6_innovation_control.py evaluate --run-label v1

The default run contains L1/L3/L5, MEDIUM+RELATIONSHIP, MEDIUM+WORLD, and the
planning-only Runtime ablation C.  ``--skip-c`` is available when the author
explicitly wants to defer that ablation; it does not remove the Phase 5.1 C
implementation.
"""

# The benchmark prompts contain operational prose.  The contracts and the
# handoff boundaries, not line wrapping, are the relevant lint surface.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any

try:
    import phase5_live_ab as p5
except ImportError:  # pragma: no cover - supports ``python -m scripts...``
    from scripts import phase5_live_ab as p5

from novel_authoring.config import load_settings
from novel_authoring.contracts.draft import DraftOutput
from novel_authoring.db.database import Database
from novel_authoring.distill.service import (
    create_distill_handoff,
    import_distill_result,
    prepare_book_sources,
)
from novel_authoring.drafting.service import import_draft_output, prepare_draft_task
from novel_authoring.planning.batch import BatchProvisionalState
from novel_authoring.planning.candidates import (
    import_candidate_output,
    prepare_candidate_task,
)
from novel_authoring.planning.contracts import build_chapter_contract
from novel_authoring.planning.innovation import (
    CandidateInnovationPreview,
    InnovationControl,
    InnovationFocus,
    InnovationLevel,
    NarrativePortfolioSnapshot,
    assess_innovation_alignment,
    build_experiment_context_fingerprint,
    classify_novelty,
    compare_experiment_contexts,
    estimate_integration_cost,
)
from novel_authoring.planning.models import CandidateOutput, ChapterContract
from novel_authoring.planning.rewards import (
    calculate_realized_innovation_reward,
    detect_semantic_policy_leak,
)
from novel_authoring.storage.library import LibraryAddOptions, add_book
from novel_authoring.storage.operations import ensure_operation
from novel_authoring.utils import json_dumps, sha256_file, stable_id, utc_now
from novel_authoring.validation.service import validate_draft
from novel_authoring.workflows.handoffs import HandoffStatus, get_handoff

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "book" / "测试小说.md"
BOUNDARY = 60
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
STATE_SCHEMA = "phase6-innovation-control-live-v1"
CONTEXT_SCHEMA = "phase6-innovation-context-v1"
RUN_DIR_NAME = "phase6_live"
HIDDEN_DIR_NAME = "phase6_live_hidden"
MARKER = "<!-- phase6-live-directive -->"
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


class Phase6Error(RuntimeError):
    pass


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase6Error(f"无法读取 JSON：{path}") from exc
    if not isinstance(value, dict):
        raise Phase6Error(f"JSON 必须是 object：{path}")
    return value


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")


def _sections(path: Path, *, minimum: int = BOUNDARY + 2) -> list[str]:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^##\s+.+$", text))
    if len(matches) < minimum:
        raise Phase6Error(
            f"测试源至少需要 {minimum} 章，实际只有 {len(matches)} 章"
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
    return {
        "controller_root": controller,
        "run_root": controller / "runs" / run_label,
        "state": controller / "runs" / run_label / "run_state.json",
        "queue": controller / "runs" / run_label / "WORK_QUEUE.md",
        "queue_pointer": controller / "WORK_QUEUE.md",
        "hidden_root": (hidden_root or root / "benchmark" / HIDDEN_DIR_NAME / run_label).resolve(),
        "library_root": (library_root or root / "library").resolve(),
    }


def _db(book: dict[str, Any]) -> Database:
    return Database(Path(str(book["database"])))


def _ordered_books(state: dict[str, Any]) -> list[dict[str, Any]]:
    order = {str(item["key"]): index for index, item in enumerate(state["variant_specs"])}
    return sorted(state["books"], key=lambda item: order[str(item["variant"])])


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
        raise Phase6Error(f"Phase 6 run 不存在：{paths['state']}")
    state = _read_json(paths["state"])
    if state.get("schema_version") != STATE_SCHEMA:
        raise Phase6Error("Phase 6 run schema 不匹配")
    state["state_path"] = str(paths["state"])
    return state


def _load_task(task: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    input_path = Path(str(task["input"]))
    task_path = input_path.parent / "task.json"
    return task_path, _read_json(task_path)


def _append_directive(path: Path, directive: str) -> None:
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    if MARKER not in current:
        _write_text(path, current + "\n\n" + MARKER + "\n" + directive)


def _augment_task(
    task: dict[str, Any],
    *,
    state: dict[str, Any],
    book: dict[str, Any],
    chapter: int,
    stage: str,
    include_runtime_state: bool,
    directive: str,
    previous_provisional: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task_path, metadata = _load_task(task)
    metadata.update(
        {
            "benchmark_protocol": {
                "schema_version": "phase6-live-protocol-v1",
                "run_label": state["run_label"],
                "variant": book["variant"],
                "benchmark_variant": book["variant"],
                "boundary": BOUNDARY,
                "target_chapter": chapter,
                "stage": stage,
                "visible_source_max_ordinal": BOUNDARY,
                "hidden_truth_provided": False,
                "include_runtime_state": include_runtime_state,
                "draft_include_runtime_state": bool(book["draft_runtime"]),
                "previous_provisional_state_present": previous_provisional is not None,
                "python_literal_candidate_fixture": False,
                "python_literal_prose_fixture": False,
            },
            "benchmark_variant": book["variant"],
            "include_runtime_state": include_runtime_state,
            "hidden_truth_provided": False,
            "innovation_control": book["innovation_control"],
            "innovation_source": "phase6_frozen_experiment_protocol",
        }
    )
    if previous_provisional is not None:
        metadata["previous_provisional_state"] = previous_provisional
    _write_json(task_path, metadata)
    _append_directive(Path(str(task["input"])), directive)
    return metadata


def _distill_augment(
    task_directory: Path,
    *,
    state: dict[str, Any],
    book: dict[str, Any],
) -> dict[str, Any]:
    task_path = task_directory / "input" / "task.json"
    if not task_path.is_file():
        task_path = task_directory / "task.json"
    task = _read_json(task_path)
    task["benchmark_protocol"] = {
        "schema_version": "phase6-live-protocol-v1",
        "run_label": state["run_label"],
        "variant": book["variant"],
        "boundary": BOUNDARY,
        "visible_source_max_ordinal": BOUNDARY,
        "hidden_truth_provided": False,
        "include_runtime_state": False,
        "semantic_output_must_be_codex_desktop": True,
        "python_literal_semantic_fixtures_forbidden": True,
        "innovation_control": book["innovation_control"],
    }
    task["innovation_control"] = book["innovation_control"]
    task["distill"]["live_benchmark_instruction"] = (
        "这是 Phase 6 True Live Distill handoff。请只读取冻结 artifacts/distill_input，"
        "由 Windows Codex Desktop 实际生成九维 Distillation Package；Python 不提供语义答案，"
        "hidden truth 不在任务输入中。Distill Scope 必须保持 SELF_BOOK。"
    )
    _write_json(task_path, task)
    _append_directive(
        task_path.parent / "prompt.md",
        "完成后保持 DISTILLED；不要写入 Canon、Edition 或 active runtime state。",
    )
    context_path = task_path.parent / "context_manifest.json"
    if context_path.is_file():
        context = _read_json(context_path)
        file_hashes = context.get("file_hashes", {})
        if isinstance(file_hashes, dict):
            file_hashes["task.json"] = sha256_file(task_path)
            file_hashes["prompt.md"] = sha256_file(task_path.parent / "prompt.md")
            context["file_hashes"] = file_hashes
        context["phase6"] = {
            "variant": book["variant"],
            "visible_source_max_ordinal": BOUNDARY,
            "hidden_truth_provided": False,
            "innovation_control": book["innovation_control"],
        }
        _write_json(context_path, context)
    return task


def _package_semantics(runtime: dict[str, Any]) -> dict[str, Any]:
    reference = runtime.get("distill_reference")
    if not isinstance(reference, dict):
        return {}
    manifest_path = Path(str(reference.get("machine_manifest") or ""))
    if not manifest_path.is_file():
        return {"scope": reference.get("scope"), "dimensions": reference.get("dimensions", [])}
    try:
        manifest = _read_json(manifest_path)
    except Phase6Error:
        manifest = {}
    return {
        "scope": reference.get("scope"),
        "dimensions": reference.get("dimensions", []),
        "depth": reference.get("depth"),
        "package_version": manifest.get("package_version"),
        "artifacts": manifest.get("artifacts", {}),
        "finding_counts": manifest.get("finding_counts", {}),
    }


def _semantic_context(
    state: dict[str, Any],
    book: dict[str, Any],
    metadata: dict[str, Any],
    *,
    include_runtime_state: bool,
) -> dict[str, Any]:
    runtime = metadata.get("runtime_context", {})
    if not isinstance(runtime, dict):
        runtime = {}
    runtime_state = runtime.get("effective_runtime_state") if include_runtime_state else {}
    earned_surface = runtime.get("earned_surface") if include_runtime_state else {}
    source_text = Path(str(book["visible_source"])).read_text(encoding="utf-8")
    sections = _sections(Path(str(book["visible_source"])), minimum=BOUNDARY)
    return {
        "visible_source": {
            "max_visible_ordinal": BOUNDARY,
            "content": source_text,
        },
        "distill_soft_context": _package_semantics(runtime),
        "runtime_state": runtime_state or {},
        "earned_surface": earned_surface or {},
        "author_directives": {
            "directive": "保持可验证事实、因果推进、作者控制与连续性 hard gates；只改变 creative distance。",
            "all_lenses_required": True,
        },
        "recent_chapter_window": {
            "chapters": sections[max(0, BOUNDARY - 10) : BOUNDARY],
        },
    }


def _write_context_manifest(
    state: dict[str, Any],
    book: dict[str, Any],
    task: dict[str, Any],
    *,
    chapter: int,
    stage: str,
    include_runtime_state: bool,
    previous_provisional: dict[str, Any] | None = None,
) -> str:
    _task_path, metadata = _load_task(task)
    runtime = metadata.get("runtime_context", {})
    if not isinstance(runtime, dict):
        runtime = {}
    if include_runtime_state:
        if runtime.get("effective_runtime_state") is None or runtime.get("earned_surface") is None:
            raise Phase6Error("Full Runtime handoff 缺少 Effective Runtime/Earned Surface")
    else:
        if any(runtime.get(key) for key in ("effective_runtime_state", "earned_surface", "baseline_recall_candidates", "hard_constraints")):
            raise Phase6Error("Planning-only Draft 仍携带 Raw Runtime tables")
    context = {
        "schema_version": CONTEXT_SCHEMA,
        "run_label": state["run_label"],
        "book_id": book["book_id"],
        "variant": book["variant"],
        "boundary": BOUNDARY,
        "target_chapter": chapter,
        "stage": stage,
        "truth_revealed": False,
        "visible_source": {
            "max_visible_ordinal": BOUNDARY,
            "visible_chapters": list(range(1, BOUNDARY + 1)),
            "hidden_chapters_loaded": [],
        },
        "innovation_control": book["innovation_control"],
        "runtime_layers": {
            "include_runtime_state": bool(include_runtime_state),
            "effective_runtime_state_id": (runtime.get("effective_runtime_state") or {}).get("state_id"),
            "earned_surface_id": (runtime.get("earned_surface") or {}).get("surface_id"),
            "baseline_recall_candidate_count": len(runtime.get("baseline_recall_candidates", [])),
            "hard_constraints_loaded": bool(runtime.get("hard_constraints")),
            "ablation": "FULL_RUNTIME" if include_runtime_state else "PLANNING_ONLY",
        },
        "operation": {
            "operation_id": metadata.get("task_id"),
            "task_id": metadata.get("task_id"),
            "input": str(task["input"]),
            "expected_output": str(task["expected_output"]),
            "task_created_at": metadata.get("created_at"),
        },
        "previous_provisional_state": previous_provisional,
        "canon_write": False,
        "edition_activation": False,
        "semantic_inputs": _semantic_context(
            state, book, metadata, include_runtime_state=include_runtime_state
        ),
    }
    path = (
        Path(str(book["benchmark_root"]))
        / "context_manifests"
        / f"chapter_{chapter:03d}_{stage}.json"
    )
    _write_json(path, context)
    return str(path)


def _make_book(
    *,
    state: dict[str, Any],
    sections: list[str],
    spec: dict[str, Any],
    paths: dict[str, Path],
) -> dict[str, Any]:
    key = str(spec["key"])
    book_id = f"phase6-live-{key.lower()}-060"
    source_root = paths["library_root"] / f".{state['run_label']}-{key.lower()}-060-input"
    if source_root.exists():
        raise Phase6Error(f"prepare 输入目录已存在：{source_root}")
    source_root.mkdir(parents=True)
    visible_path = source_root / "visible_060.md"
    _write_text(visible_path, "\n\n".join(sections[:BOUNDARY]))
    added = add_book(
        LibraryAddOptions(
            book_id=book_id,
            title=f"Phase 6 live {key} boundary 060",
            source=visible_path,
            library_root=paths["library_root"],
            confirm_order=True,
        )
    )
    database = Database(added.database)
    root = Path(str(added.root)).resolve()
    benchmark_root = root / "benchmark" / "phase6_live"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    prepared = prepare_book_sources(database, book_id, edition_id="base")
    p5._baseline_input(
        book={"book_id": book_id, "boundary": BOUNDARY, "database": str(added.database)},
        prepared=prepared,
        benchmark_root=benchmark_root,
    )
    p5._seed_neutral_planning_inputs(database, book_id, BOUNDARY)
    safety_before = p5._safety_state(database, book_id)
    distill_handoff = create_distill_handoff(
        database,
        book_id,
        preparation_id=str(prepared["preparation_id"]),
        dimensions=",".join(DIMENSIONS),
        depth="standard",
        edition_id="base",
    )
    _distill_augment(
        Path(str(distill_handoff["task_directory"])), state=state, book={
            "book_id": book_id,
            "variant": key,
            "innovation_control": spec["control"].model_dump(mode="json"),
        }
    )
    book = {
        "book_id": book_id,
        "variant": key,
        "edition_id": "base",
        "innovation_control": spec["control"].model_dump(mode="json"),
        "innovation_source": "phase6_frozen_experiment_protocol",
        "candidate_runtime": bool(spec["candidate_runtime"]),
        "draft_runtime": bool(spec["draft_runtime"]),
        "root": str(root),
        "database": str(added.database),
        "benchmark_root": str(benchmark_root),
        "visible_source": str(visible_path),
        "visible_chapter_count": BOUNDARY,
        "recent_median_characters": int(statistics.median(len(item) for item in sections[BOUNDARY - 10 : BOUNDARY])),
        "safety_before": safety_before,
        "distill": {
            "handoff_id": distill_handoff["handoff_id"],
            "task_directory": distill_handoff["task_directory"],
            "status": HandoffStatus.READY_FOR_CODEX.value,
            "imported": False,
            "result": None,
        },
        "chapters": {str(BOUNDARY + 1): {}, str(BOUNDARY + 2): {}},
        "generation_closed": False,
        "truth_revealed": False,
        "hidden_controller_key": book_id,
        "source_snapshot": {
            "size": visible_path.stat().st_size,
            "mtime_ns": visible_path.stat().st_mtime_ns,
        },
    }
    _write_json(
        benchmark_root / "benchmark_manifest.json",
        {
            "schema_version": STATE_SCHEMA,
            "benchmark_type": "TRUE_LIVE_CODEX_HANDOFF_INNOVATION_CONTROL",
            "run_label": state["run_label"],
            "book_id": book_id,
            "variant": key,
            "boundary": BOUNDARY,
            "edition_id": "base",
            "visible_source": "book/测试小说.md",
            "visible_chapter_count": BOUNDARY,
            "selected_dimensions": list(DIMENSIONS),
            "innovation_control": book["innovation_control"],
            "candidate_runtime": book["candidate_runtime"],
            "draft_runtime": book["draft_runtime"],
            "hidden_truth_provided": False,
            "canon_committed": False,
            "edition_activated": False,
            "python_literal_semantic_fixture": False,
            "python_literal_candidate_fixture": False,
            "python_literal_prose_fixture": False,
        },
    )
    _write_json(
        benchmark_root / "context_manifests" / "distill.json",
        {
            "schema_version": CONTEXT_SCHEMA,
            "run_label": state["run_label"],
            "book_id": book_id,
            "variant": key,
            "boundary": BOUNDARY,
            "stage": "distill",
            "truth_revealed": False,
            "visible_source": {"max_visible_ordinal": BOUNDARY, "hidden_chapters_loaded": []},
            "innovation_control": book["innovation_control"],
            "operation": {
                "handoff_id": distill_handoff["handoff_id"],
                "task_directory": str(distill_handoff["task_directory"]),
            },
        },
    )
    hidden_dir = paths["hidden_root"] / book_id
    hidden_dir.mkdir(parents=True, exist_ok=False)
    _write_text(hidden_dir / "chapter_061.md", sections[BOUNDARY])
    _write_text(hidden_dir / "chapter_062.md", sections[BOUNDARY + 1])
    return book


def _prepare_run(
    *,
    run_label: str,
    source: Path = SOURCE,
    root: Path = ROOT,
    controller_root: Path | None = None,
    hidden_root: Path | None = None,
    library_root: Path | None = None,
    include_c: bool = True,
    only_variant: str | None = None,
) -> dict[str, Any]:
    source = source.resolve()
    if not source.is_file():
        raise Phase6Error(f"测试源不存在：{source}")
    paths = _paths(
        root=root,
        run_label=run_label,
        controller_root=controller_root,
        hidden_root=hidden_root,
        library_root=library_root,
    )
    if paths["state"].exists():
        raise Phase6Error(f"run 已存在，拒绝覆盖：{paths['state']}")
    if paths["hidden_root"].resolve() == paths["library_root"].resolve() or paths["hidden_root"].is_relative_to(paths["library_root"]):
        raise Phase6Error("hidden truth 必须位于独立 controller 目录，不能位于 library")
    sections = _sections(source)
    controls = [
        ("L1", InnovationControl(level=InnovationLevel.MINIMAL), True, True),
        ("L3", InnovationControl(level=InnovationLevel.MEDIUM), True, True),
        ("L5", InnovationControl(level=InnovationLevel.BOLD), True, True),
        ("RELATIONSHIP", InnovationControl(level=InnovationLevel.MEDIUM, focus=[InnovationFocus.RELATIONSHIP]), True, True),
        ("WORLD", InnovationControl(level=InnovationLevel.MEDIUM, focus=[InnovationFocus.WORLD]), True, True),
    ]
    if include_c:
        controls.append(("C", InnovationControl(level=InnovationLevel.MEDIUM), True, False))
    if only_variant is not None:
        normalized_variant = only_variant.strip().upper()
        controls = [item for item in controls if item[0] == normalized_variant]
        if not controls:
            raise Phase6Error(f"未知 Phase 6 variant：{only_variant}")
    specs = [
        {
            "key": key,
            "control": control,
            "candidate_runtime": candidate_runtime,
            "draft_runtime": draft_runtime,
        }
        for key, control, candidate_runtime, draft_runtime in controls
    ]
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
        "boundaries": [BOUNDARY],
        "variant_specs": [
            {
                "key": spec["key"],
                "innovation_control": spec["control"].model_dump(mode="json"),
                "candidate_runtime": spec["candidate_runtime"],
                "draft_runtime": spec["draft_runtime"],
            }
            for spec in specs
        ],
        "include_c": include_c,
        "truth_revealed": False,
        "generation_closed": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "books": [],
    }
    for spec in specs:
        state["books"].append(_make_book(state=state, sections=sections, spec=spec, paths=paths))
    _write_queue(state)
    _save_state(state)
    return _status_summary(state)


def _visible_audit(state: dict[str, Any], book: dict[str, Any]) -> None:
    hidden_root = str(Path(str(state["hidden_root"])).resolve()).casefold()
    hidden_token = HIDDEN_DIR_NAME.casefold()
    root = Path(str(book["root"])).resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "operations" not in path.parts and "context_manifests" not in path.parts and path.name not in {"benchmark_manifest.json", "generation_snapshot.json"}:
            continue
        try:
            content = path.read_text(encoding="utf-8").casefold()
        except (UnicodeDecodeError, OSError):
            continue
        if hidden_root in content or hidden_token in content:
            raise Phase6Error(f"发现 hidden truth 路径泄漏：{path}")
    for path in (Path(str(book["benchmark_root"])) / "context_manifests").glob("*.json"):
        context = _read_json(path)
        visible = context.get("visible_source", {})
        if visible.get("max_visible_ordinal") != BOUNDARY or visible.get("hidden_chapters_loaded"):
            raise Phase6Error(f"visible/hidden 边界不合规：{path}")
    for path in root.rglob("task.json"):
        metadata = _read_json(path)
        protocol = metadata.get("benchmark_protocol", {})
        if isinstance(protocol, dict) and (protocol.get("visible_source_max_ordinal") != BOUNDARY or protocol.get("hidden_truth_provided")):
            raise Phase6Error(f"task visible/hidden 审计失败：{path}")


def _source_unchanged(state: dict[str, Any]) -> bool:
    source = Path(str(state["source"]))
    snapshot = state.get("source_snapshot", {})
    return source.is_file() and source.stat().st_size == int(snapshot.get("size", -1)) and source.stat().st_mtime_ns == int(snapshot.get("mtime_ns", -1))


def _candidate_directive(book: dict[str, Any], chapter: int) -> str:
    control = json_dumps(book["innovation_control"])
    control_model = InnovationControl.model_validate(book["innovation_control"])
    return "\n".join(
        [
            "这是 Phase 6 True Live InnovationControl 候选 handoff。",
            f"目标第 {chapter} 章；可见正文最高为第 {BOUNDARY} 章；冻结 InnovationControl={control}。",
            f"creative-distance guidance：{control_model.creative_distance_guidance}",
            f"soft lens tendency：{control_model.lens_tendency_guidance}。",
            "请由当前 Windows Codex Desktop 实际提出恰好三个具体小说事件候选。三个 Candidate Lens（CONTINUITY_ACTIVE_THREAD、EARNED_OPPORTUNITY、FORWARD_EXPANSION）必须全部保留；InnovationControl 只改变搜索宽度和未来分支表面，不放松任何 hard gate。",
            "每个候选必须填写作者可读 innovation_preview：creative distance、主要方向、打开的 future branches、meaningful/cosmetic、integration cost、earned asset 使用。不得使用占位符，不得把请求 level 冒充 realized level。",
            "每个候选还必须尽量填写 expected_innovation_elements、element synergies、SHORT/MID/LONG horizon roles、payoffs、new debts 与 before/after NarrativeDelta；只有存在共同因果链时才填写 synergy。",
            "Python 会在 Hard Gates 通过后独立计算 InnovationRewardBreakdown；不要把预估 reward 当成事实，也不能用它覆盖 Canon、Timeline、Knowledge、Capability、Resource 或 Approval。",
            "如果一个 PAYOFF_READY 或 overdue debt 被继续延后，必须在候选中说明代价与替代推进；不要只叠加新问题。",
            "不得写正文、不得把 hidden truth 当作已知事实、不得修改 book/、Canon、Edition 或 Approval。",
        ]
    )


def _draft_directive(book: dict[str, Any], chapter: int) -> str:
    median = int(book["recent_median_characters"])
    control_model = InnovationControl.model_validate(book["innovation_control"])
    return "\n".join(
        [
            "这是 Phase 6 True Live 正文 handoff。",
            f"请写完整的第 {chapter} 章小说正文；最近十章字符数中位数约 {median}，soft target 为其 65%–135%，不是 hard fail。",
            f"本次冻结 InnovationControl={json_dumps(book['innovation_control'])}；它只控制 creative distance，不放松 Canon、Timeline、Knowledge、Capability、Resource、Author Directive、Approval 或 Edition hard gates。",
            f"creative-distance guidance：{control_model.creative_distance_guidance}",
            f"soft lens tendency：{control_model.lens_tendency_guidance}；它不是候选配额或分数奖励。",
            "系统内核、Chapter Contract 和 Validator 已处理硬约束；正文只写人物如何感知、选择、行动及后果，不解释治理规则。",
            "本章至少让一个重要状态发生可读改变；未知可以保留，但若核心谜团继续悬置，必须推进或兑现另一条 SHORT/MID 线程。",
            "避免连续使用谨慎试探—暂不下结论—保留退路—撤回的审计型叙事，除非 Narrative Portfolio 明确需要。",
            "正文必须是自然场景化小说，不得出现 Runtime、Baseline、Earned Surface、Canon、Projection、Validator、Distill、thread_status、resource_cost、character_boundary、融合层等工程术语，也不得写测试说明、合同复述或字段清单。",
            "请在 output.json 中提供真实 InnovationTrace 与 DirectionAlignment；requested 与 realized 必须分开填写，不能根据 requested level 伪造 realized 结果。",
            "不得修改 book/、Canon、Edition 或 Approval。",
        ]
    )


def _prepare_candidate(
    state: dict[str, Any], book: dict[str, Any], *, chapter: int, second: bool = False
) -> dict[str, Any]:
    database = _db(book)
    control = InnovationControl.model_validate(book["innovation_control"])
    include_runtime = bool(book["candidate_runtime"])
    previous_provisional = None
    if not second:
        task = prepare_candidate_task(
            database,
            str(book["book_id"]),
            load_settings(),
            edition_id="base",
            include_runtime_state=include_runtime,
            innovation_control=control,
            innovation_source="phase6_frozen_experiment_protocol",
        )
    else:
        previous = book["chapters"][str(BOUNDARY + 1)]
        base = previous["candidate_task"]
        previous_provisional = previous["provisional_state"]
        operation_id = stable_id(
            "phase6-live-candidate",
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
            {"benchmark_stage": "N_PLUS_2_CANDIDATE", "previous_chapter": BOUNDARY + 1},
        )
        if operation is None:
            raise Phase6Error("Canonical Book 未能创建 N+2 candidate operation")
        previous_prose = Path(str(previous["draft_import"]["path"])).read_text(encoding="utf-8")
        _write_text(
            operation.input / "input.md",
            Path(str(base["input"])).read_text(encoding="utf-8")
            + "\n\n## Previous VALIDATED_DRAFT provisional chapter\n\n"
            + previous_prose
            + "\n\n## Previous provisional state\n\n"
            + json_dumps(previous_provisional, indent=2),
        )
        _write_text(operation.input / "schema.json", Path(str(base["schema"])).read_text(encoding="utf-8"))
        base_path, metadata = _load_task(base)
        metadata.update(
            {
                "task_id": operation_id,
                "created_at": utc_now(),
                "target_chapter": chapter,
                "innovation_control": book["innovation_control"],
                "include_runtime_state": include_runtime,
                "previous_provisional_state": previous_provisional,
            }
        )
        _write_json(operation.input / "task.json", metadata)
        task = {
            "task_id": operation_id,
            "boundary_packet_id": base.get("boundary_packet_id"),
            "input": str(operation.input / "input.md"),
            "schema": str(operation.input / "schema.json"),
            "expected_output": str(operation.output / "output.json"),
            "top_threads": base.get("top_threads", []),
            "aggregate_id": base.get("aggregate_id"),
            "bundle_hash": base.get("bundle_hash"),
        }
    metadata = _augment_task(
        task,
        state=state,
        book=book,
        chapter=chapter,
        stage="N_PLUS_2_CANDIDATE" if second else "N_PLUS_1_CANDIDATE",
        include_runtime_state=include_runtime,
        directive=_candidate_directive(book, chapter),
        previous_provisional=previous_provisional,
    )
    context_path = _write_context_manifest(
        state,
        book,
        task,
        chapter=chapter,
        stage="candidate",
        include_runtime_state=include_runtime,
        previous_provisional=previous_provisional,
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
        "context_manifest": context_path,
    }


def _prepare_draft(
    state: dict[str, Any],
    book: dict[str, Any],
    *,
    chapter: int,
    contract_id: str,
    second: bool = False,
) -> dict[str, Any]:
    include_runtime = bool(book["draft_runtime"])
    task = prepare_draft_task(
        _db(book),
        str(book["book_id"]),
        contract_id,
        edition_id="base",
        include_runtime_state=include_runtime,
    )
    previous_provisional = None
    if second:
        previous = book["chapters"][str(BOUNDARY + 1)]
        previous_provisional = previous["provisional_state"]
        previous_prose = Path(str(previous["draft_import"]["path"])).read_text(encoding="utf-8")
        _append_directive(
            Path(str(task["input"])),
            "上一章 VALIDATED_DRAFT provisional 正文如下；必须真正承接它，不得从第60章独立重置。\n\n"
            + previous_prose,
        )
    metadata = _augment_task(
        task,
        state=state,
        book=book,
        chapter=chapter,
        stage="N_PLUS_2_DRAFT" if second else "N_PLUS_1_DRAFT",
        include_runtime_state=include_runtime,
        directive=_draft_directive(book, chapter),
        previous_provisional=previous_provisional,
    )
    context_path = _write_context_manifest(
        state,
        book,
        task,
        chapter=chapter,
        stage="draft",
        include_runtime_state=include_runtime,
        previous_provisional=previous_provisional,
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
        "context_manifest": context_path,
    }


def _selected_candidate(task: dict[str, Any], selected_id: str) -> dict[str, Any]:
    output = CandidateOutput.model_validate_json(
        Path(str(task["expected_output"])).read_text(encoding="utf-8")
    )
    for candidate in output.candidates:
        if stable_id("candidate", str(task["task_id"]), candidate.local_id) == selected_id:
            return candidate.model_dump(mode="json")
    raise Phase6Error(f"候选输出找不到 selected_candidate_id：{selected_id}")


def _provisional_contract(
    base_contract: ChapterContract,
    selected: dict[str, Any],
    selected_id: str,
    chapter: int,
    control: InnovationControl,
) -> ChapterContract:
    values = base_contract.model_dump(mode="python")
    preview = CandidateInnovationPreview.model_validate(selected["innovation_preview"])
    values["innovation_commitments"] = {
        "expected_innovation_elements": [
            item.model_dump(mode="json") for item in preview.expected_innovation_elements
        ],
        "expected_element_synergies": [
            item.model_dump(mode="json") for item in preview.expected_element_synergies
        ],
        "expected_horizon_roles": {
            key: [item.value for item in horizon_roles]
            for key, horizon_roles in preview.expected_horizon_roles.items()
        },
        "expected_cross_horizon_synergies": [
            item.model_dump(mode="json")
            for item in preview.expected_cross_horizon_synergies
        ],
        "expected_payoffs": [item.model_dump(mode="json") for item in preview.expected_payoffs],
        "expected_new_debts": [item.model_dump(mode="json") for item in preview.expected_new_debts],
        "expected_future_options_opened": preview.future_options_opened,
        "minimum_meaningful_delta": (
            preview.expected_narrative_delta.model_dump(mode="json")
            if preview.expected_narrative_delta is not None
            else None
        ),
        "soft_contract": True,
        "hard_gate_exception": False,
    }
    values.update(
        {
            "contract_id": stable_id("phase6-live-contract", str(base_contract.contract_id), selected_id, str(chapter)),
            "chapter": chapter,
            "candidate_id": selected_id,
            "primary_thread": selected["primary_thread_id"],
            "primary_function": selected["primary_function"],
            "secondary_functions": selected.get("secondary_functions", []),
            "reader_question": selected["reader_question"],
            "pressure": {"before": selected["pressure_before"], "target_after": selected["pressure_target_after"]},
            "payoff_plan": {"causal_sources": selected["causal_sources"], "state_changes": selected["state_changes"], "must_change_behavior": selected["commit_updates"]},
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
            "innovation_control": control,
            "innovation_preview": selected.get("innovation_preview"),
        }
    )
    return ChapterContract.model_validate(values)


def _insert_provisional_contract(database: Database, book_id: str, contract: ChapterContract) -> None:
    p5._insert_provisional_contract(database, book_id, contract)


def _provisional_state(
    state: dict[str, Any],
    book: dict[str, Any],
    *,
    chapter: int,
    contract: ChapterContract,
    draft: DraftOutput,
) -> dict[str, Any]:
    metadata = _load_task(book["chapters"][str(BOUNDARY + 1)]["draft_task"])[1]
    provisional = BatchProvisionalState(
        current_chapter_ordinal=chapter,
        canon_projection_hash=str(metadata.get("base_projection_hash", "")),
        source_manifest_sha256=str(metadata.get("source_manifest_sha256", "")),
        effective_content_sha256=str(metadata.get("effective_content_sha256", "")),
        registry_hash=str(metadata.get("registry_hash", "")),
        config_hash=str(metadata.get("config_hash", "")),
        author_directives_hash=str(metadata.get("author_directives_hash", "")),
        metric_bundle_hash=str(metadata.get("metric_bundle_hash", "")),
        innovation_control=InnovationControl.model_validate(book["innovation_control"]),
        innovation_source="phase6_frozen_experiment_protocol",
        provisional_events=[{"chapter": chapter, "contract_id": contract.contract_id, "draft_id": draft.task_id, "status": "PROVISIONAL"}],
        provisional_threads=[
            {"thread_id": change.record_id, "status": "PROVISIONAL", "evidence": change.evidence_quotes[0]}
            for change in draft.state_changes
            if change.kind == "thread"
        ],
        unresolved_questions=[contract.reader_question],
    )
    path = Path(str(book["benchmark_root"])) / "provisional" / f"chapter_{chapter:03d}.json"
    _write_json(path, provisional.model_dump(mode="json"))
    return provisional.model_dump(mode="json")


def _require_outputs(state: dict[str, Any], field: str, label: str) -> None:
    missing = []
    for book in _ordered_books(state):
        for chapter in book["chapters"].values():
            task = chapter.get(field)
            if task and not Path(str(task["expected_output"])).is_file():
                missing.append(f"{book['book_id']}:{task['task_id']}")
    if missing:
        raise Phase6Error(f"collect 拒绝推进 {label}：尚未出现 output.json：{', '.join(missing)}")


def _record(path: Path, prepared_at: object) -> dict[str, Any]:
    return {
        "generation_timestamp": p5._now_from_mtime(path),
        "generation_timestamp_source": "output_file_mtime",
        "output_observed_at": utc_now(),
        "task_created_at": prepared_at,
    }


def _collect_distill(state: dict[str, Any]) -> None:
    pending = []
    for book in _ordered_books(state):
        if book["distill"]["imported"]:
            continue
        handoff = get_handoff(_db(book), str(book["distill"]["handoff_id"]))
        book["distill"]["status"] = handoff["status"]
        if handoff["status"] != HandoffStatus.COMPLETED.value:
            pending.append(f"{book['book_id']}:{handoff['status']}")
    if pending:
        raise Phase6Error("所有 Distill handoff 必须先由 Codex Desktop 完成：" + ", ".join(pending))
    for book in _ordered_books(state):
        if book["distill"]["imported"]:
            continue
        _visible_audit(state, book)
        result = import_distill_result(_db(book), str(book["book_id"]), str(book["distill"]["handoff_id"]))
        handoff = get_handoff(_db(book), str(book["distill"]["handoff_id"]))
        book["distill"].update(
            {
                "imported": True,
                "status": HandoffStatus.COMPLETED.value,
                "result": result,
                "output_artifact": str(Path(str(book["distill"]["task_directory"])) / "artifacts" / "distill_skill"),
                "input_context_manifest": str(Path(str(book["distill"]["task_directory"])) / "input" / "context_manifest.json"),
                "completed_at": (handoff.get("result") or {}).get("completed_at"),
            }
        )
        chapter = BOUNDARY + 1
        book["chapters"][str(chapter)]["candidate_task"] = _prepare_candidate(state, book, chapter=chapter)


def _collect_candidate(state: dict[str, Any], *, chapter_offset: int) -> None:
    ordinal = BOUNDARY + chapter_offset
    _require_outputs(state, "candidate_task", f"N+{chapter_offset} candidate")
    for book in _ordered_books(state):
        chapter = book["chapters"][str(ordinal)]
        if chapter.get("candidate_import"):
            continue
        task = chapter["candidate_task"]
        output_path = Path(str(task["expected_output"]))
        output = CandidateOutput.model_validate_json(output_path.read_text(encoding="utf-8"))
        if any(candidate.innovation_preview is None for candidate in output.candidates):
            raise Phase6Error(f"{book['book_id']} 第 {ordinal} 章候选缺少 innovation_preview")
        expected_control = InnovationControl.model_validate(book["innovation_control"])
        if output.innovation_control is not None and output.innovation_control != expected_control:
            raise Phase6Error(f"{book['book_id']} CandidateOutput 的 InnovationControl 与冻结值不一致")
        imported = import_candidate_output(
            _db(book), str(book["book_id"]), str(task["task_id"]), load_settings(), output_path,
            edition_id="base", include_runtime_state=bool(book["candidate_runtime"]),
        )
        contract_result = build_chapter_contract(_db(book), str(book["book_id"]), str(imported["selected_candidate_id"]), edition_id="base")
        contract = ChapterContract.model_validate_json(Path(str(contract_result["path"])).read_text(encoding="utf-8"))
        chapter["candidate_import"] = {**imported, **_record(output_path, task.get("prepared_at")), "input_context_manifest": task["context_manifest"]}
        chapter["candidate_preview"] = [item.innovation_preview.model_dump(mode="json") for item in output.candidates if item.innovation_preview]
        chapter["contract"] = {**contract_result, "input_context_manifest": task["context_manifest"], "source": "live Codex CandidateOutput selected by deterministic contract builder"}
        chapter["candidate_selected"] = _selected_candidate(task, str(imported["selected_candidate_id"]))
        chapter["draft_task"] = _prepare_draft(state, book, chapter=ordinal, contract_id=str(contract.contract_id))


def _audit_realized_innovation(
    book: dict[str, Any],
    chapter: dict[str, Any],
    draft_output: DraftOutput,
) -> dict[str, Any]:
    if draft_output.innovation_trace is None:
        raise Phase6Error("Draft 缺少 InnovationTrace，无法计算 realized reward")
    candidate_import = chapter.get("candidate_import", {})
    selected_id = str(candidate_import.get("selected_candidate_id", ""))
    selected = next(
        (
            item
            for item in candidate_import.get("candidates", [])
            if str(item.get("candidate_id", "")) == selected_id
        ),
        {},
    )
    portfolio_raw = candidate_import.get("narrative_portfolio_snapshot", {})
    portfolio = NarrativePortfolioSnapshot.model_validate(portfolio_raw)
    control = InnovationControl.model_validate(book["innovation_control"])
    base_score = float(selected.get("base_score", selected.get("score", 0)))
    realized_reward = calculate_realized_innovation_reward(
        draft_output.innovation_trace,
        control,
        base_candidate_score=base_score,
        portfolio=portfolio,
    )
    expected_breakdown = selected.get("innovation_reward_breakdown", {})
    expected_capped = float(expected_breakdown.get("capped_innovation_reward", 0))
    realized_capped = realized_reward.capped_innovation_reward
    return {
        "expected_innovation_reward": expected_breakdown,
        "realized_innovation_reward": realized_reward.model_dump(mode="json"),
        "innovation_underdelivery": {
            "status": (
                "INNOVATION_UNDERDELIVERY"
                if realized_capped + 0.5 < expected_capped
                else "CLEAR"
            ),
            "expected_capped_reward": expected_capped,
            "realized_capped_reward": realized_capped,
            "warning_only": True,
        },
        "semantic_policy_leak": detect_semantic_policy_leak(
            draft_output.prose_markdown
        ).model_dump(mode="json"),
    }


def _collect_draft(state: dict[str, Any], *, chapter_offset: int) -> None:
    ordinal = BOUNDARY + chapter_offset
    _require_outputs(state, "draft_task", f"N+{chapter_offset} draft")
    for book in _ordered_books(state):
        chapter = book["chapters"][str(ordinal)]
        if chapter.get("draft_import") and chapter.get("validation", {}).get("passed"):
            continue
        task = chapter["draft_task"]
        output_path = Path(str(task["expected_output"]))
        draft_output = DraftOutput.model_validate_json(output_path.read_text(encoding="utf-8"))
        expected_control = InnovationControl.model_validate(book["innovation_control"])
        if draft_output.innovation_trace is None or draft_output.direction_alignment is None:
            raise Phase6Error(f"{book['book_id']} 第 {ordinal} 章必须提供 InnovationTrace 与 DirectionAlignment")
        if draft_output.innovation_trace.requested_level is not expected_control.level or draft_output.innovation_trace.requested_focus != expected_control.focus:
            raise Phase6Error(f"{book['book_id']} 第 {ordinal} 章 requested InnovationTrace 与冻结控制不一致")
        if draft_output.innovation_control is not None and draft_output.innovation_control != expected_control:
            raise Phase6Error(f"{book['book_id']} 第 {ordinal} 章 DraftOutput 的 InnovationControl 与冻结值不一致")
        imported = import_draft_output(_db(book), str(book["book_id"]), str(task["task_id"]), output_path, edition_id="base")
        validation = validate_draft(_db(book), str(book["book_id"]), str(imported["draft_id"]), load_settings(), edition_id="base", include_runtime_state=bool(book["draft_runtime"]))
        validation_path = Path(str(book["benchmark_root"])) / "validation" / f"chapter_{ordinal:03d}.json"
        _write_json(validation_path, validation.model_dump(mode="json"))
        innovation_audit = _audit_realized_innovation(book, chapter, draft_output)
        chapter["draft_import"] = {**imported, **_record(output_path, task.get("prepared_at")), "output_path": str(output_path), "input_context_manifest": task["context_manifest"], "prose_markdown": draft_output.prose_markdown, "innovation_trace": draft_output.innovation_trace.model_dump(mode="json"), "direction_alignment": draft_output.direction_alignment.model_dump(mode="json"), **innovation_audit}
        chapter["validation"] = {"path": str(validation_path), "passed": validation.passed, "validator_count": len(validation.reports), "payload": validation.model_dump(mode="json")}
        if not validation.passed:
            raise Phase6Error(f"{book['book_id']} 第 {ordinal} 章 Validator 未通过；generation 不能关闭")
        if chapter_offset == 1:
            chapter["provisional_state"] = _provisional_state(
                state, book, chapter=ordinal,
                contract=ChapterContract.model_validate_json(Path(str(chapter["contract"]["path"])).read_text(encoding="utf-8")),
                draft=draft_output,
            )
    if chapter_offset == 1:
        for book in _ordered_books(state):
            key = str(BOUNDARY + 2)
            if not book["chapters"][key].get("candidate_task"):
                book["chapters"][key]["candidate_task"] = _prepare_candidate(state, book, chapter=BOUNDARY + 2, second=True)


def _collect_candidate_two(state: dict[str, Any]) -> None:
    _require_outputs(state, "candidate_task", "N+2 candidate")
    for book in _ordered_books(state):
        ordinal = BOUNDARY + 2
        chapter = book["chapters"][str(ordinal)]
        if chapter.get("candidate_import"):
            continue
        task = chapter["candidate_task"]
        output_path = Path(str(task["expected_output"]))
        output = CandidateOutput.model_validate_json(output_path.read_text(encoding="utf-8"))
        if any(candidate.innovation_preview is None for candidate in output.candidates):
            raise Phase6Error(f"{book['book_id']} 第 {ordinal} 章候选缺少 innovation_preview")
        imported = import_candidate_output(_db(book), str(book["book_id"]), str(task["task_id"]), load_settings(), output_path, edition_id="base", include_runtime_state=bool(book["candidate_runtime"]))
        selected = _selected_candidate(task, str(imported["selected_candidate_id"]))
        base_contract = ChapterContract.model_validate_json(Path(str(book["chapters"][str(BOUNDARY + 1)]["contract"]["path"])).read_text(encoding="utf-8"))
        provisional_contract = _provisional_contract(base_contract, selected, str(imported["selected_candidate_id"]), ordinal, InnovationControl.model_validate(book["innovation_control"]))
        _insert_provisional_contract(_db(book), str(book["book_id"]), provisional_contract)
        chapter["candidate_import"] = {**imported, **_record(output_path, task.get("prepared_at")), "input_context_manifest": task["context_manifest"]}
        contract_path = Path(str(book["benchmark_root"])) / "contracts" / f"chapter_{ordinal:03d}.json"
        _write_json(contract_path, provisional_contract.model_dump(mode="json"))
        chapter["contract"] = {"contract_id": provisional_contract.contract_id, "candidate_id": provisional_contract.candidate_id, "chapter": ordinal, "path": str(contract_path), "input_context_manifest": task["context_manifest"], "source": "live Codex CandidateOutput selected by deterministic provisional contract builder"}
        chapter["candidate_selected"] = selected
        chapter["draft_task"] = _prepare_draft(state, book, chapter=ordinal, contract_id=provisional_contract.contract_id, second=True)


def _close_generation(state: dict[str, Any]) -> None:
    for book in _ordered_books(state):
        first = book["chapters"][str(BOUNDARY + 1)]
        second = book["chapters"][str(BOUNDARY + 2)]
        if not first.get("validation", {}).get("passed") or not second.get("validation", {}).get("passed"):
            raise Phase6Error("两章都通过十项 Validator 后才能 generation_closed")
        _write_json(Path(str(book["benchmark_root"])) / "generation_snapshot.json", {"schema_version": "phase6-generation-snapshot-v1", "generation_closed": True, "truth_revealed": False, "visible_boundary": BOUNDARY, "generated_chapters": [BOUNDARY + 1, BOUNDARY + 2], "hidden_truth_loaded": False, "canon_committed": False, "edition_activated": False})
        book["generation_closed"] = True
    state["generation_closed"] = True


def _stage(state: dict[str, Any]) -> str:
    if not all(book["distill"]["imported"] for book in _ordered_books(state)):
        return "DISTILL"
    if any(not book["chapters"][str(BOUNDARY + 1)].get("candidate_task") for book in _ordered_books(state)):
        return "N_PLUS_1_CANDIDATE_PREPARED"
    if any(not book["chapters"][str(BOUNDARY + 1)].get("candidate_import") for book in _ordered_books(state)):
        return "N_PLUS_1_CANDIDATE"
    if any(not book["chapters"][str(BOUNDARY + 1)].get("draft_task") for book in _ordered_books(state)):
        return "N_PLUS_1_DRAFT_PREPARED"
    if any(not book["chapters"][str(BOUNDARY + 1)].get("draft_import") for book in _ordered_books(state)):
        return "N_PLUS_1_DRAFT"
    if any(not book["chapters"][str(BOUNDARY + 2)].get("candidate_task") for book in _ordered_books(state)):
        return "N_PLUS_2_CANDIDATE_PREPARED"
    if any(not book["chapters"][str(BOUNDARY + 2)].get("candidate_import") for book in _ordered_books(state)):
        return "N_PLUS_2_CANDIDATE"
    if any(not book["chapters"][str(BOUNDARY + 2)].get("draft_task") for book in _ordered_books(state)):
        return "N_PLUS_2_DRAFT_PREPARED"
    if any(not book["chapters"][str(BOUNDARY + 2)].get("draft_import") for book in _ordered_books(state)):
        return "N_PLUS_2_DRAFT"
    return "GENERATION_CLOSED" if state.get("generation_closed") else "READY_TO_CLOSE"


def _collect(state: dict[str, Any]) -> dict[str, Any]:
    stage = _stage(state)
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
        raise Phase6Error(f"collect 状态不一致：{stage}")
    for book in _ordered_books(state):
        _visible_audit(state, book)
    _write_queue(state)
    _save_state(state)
    return _status_summary(state)


def _task_line(number: int, label: str, task: dict[str, Any] | None) -> str:
    if task is None:
        return f"### {number}. {label}\n\n- 等待上一阶段 collect 准备。"
    return "\n".join(
        [
            f"### {number}. {label}",
            "",
            f"- handoff_id: `{task.get('handoff_id') or 'N/A — canonical Operation handoff'}`",
            f"- task_id / operation_id: `{task['task_id']}`",
            f"- input: `{task['input']}`",
            f"- expected output: `{task['expected_output']}`",
            "- Windows Codex Desktop：读取 input/task.json/schema，写真实结构化结果；不得修改 book/、Canon、Edition 或 Approval。",
        ]
    )


def _write_queue(state: dict[str, Any]) -> None:
    lines = [
        "# Phase 6 True Live InnovationControl Work Queue",
        "",
        f"Run label: `{state['run_label']}`；boundary: `{BOUNDARY} → {BOUNDARY + 1}/{BOUNDARY + 2}`",
        "",
        "本队列不包含 hidden truth 路径。Distill、候选与正文必须由对应 READY_FOR_CODEX/Operation 在 Windows Codex Desktop 实际生成；Python 只 prepare、collect、validate、close、evaluate。",
        "",
        "固定顺序：所有 Distill → N+1 Candidate → N+1 Draft → N+2 Candidate → N+2 Draft。N+2 必须读取同一 variant 自己的 N+1 VALIDATED_DRAFT provisional context。",
        "",
        "## Distill",
        "",
    ]
    number = 1
    for book in _ordered_books(state):
        task_dir = Path(str(book["distill"]["task_directory"]))
        lines.append(_task_line(number, f"{book['variant']} Distill ({book['innovation_control']['level']} + {','.join(book['innovation_control']['focus'])})", {"task_id": book["distill"]["handoff_id"], "input": str(task_dir / "input" / "prompt.md"), "expected_output": str(task_dir / "result.json"), "handoff_id": book["distill"]["handoff_id"]}))
        number += 1
    for offset, label in ((1, "Candidate"), (1, "Draft"), (2, "Candidate"), (2, "Draft")):
        lines.extend(["", f"## N+{offset} {label}", ""])
        for book in _ordered_books(state):
            task = book["chapters"][str(BOUNDARY + offset)].get("candidate_task" if label == "Candidate" else "draft_task")
            lines.append(_task_line(number, f"{book['variant']} 第 {BOUNDARY + offset} 章 {label}", task))
            number += 1
    lines.extend(
        [
            "",
            "## Operator commands",
            "",
            "1. Distill：使用 `$process-novel-handoff` 和 `$distill-novels`，完成后保持 DISTILLED。",
            "2. Candidate/Draft：按 output_schema.json 写真实结果；不调用 API、codex exec 或 subprocess。",
            f"3. 当前阶段完成后运行：`python scripts/phase6_innovation_control.py collect --run-label {state['run_label']}`。",
            "4. generation_closed=true 后才允许 evaluate；evaluate 才会读取 controller-owned hidden truth。",
            "5. 最终 draft 由外部审计策略 force-add 到 Git；只提交 library 中的正式 draft artifact，不提交 hidden truth、数据库缓存或原始 book。",
        ]
    )
    queue = "\n".join(lines) + "\n"
    _write_text(Path(str(state["run_root"])) / "WORK_QUEUE.md", queue)
    _write_text(Path(str(state["controller_root"])) / "WORK_QUEUE.md", queue)
    if HIDDEN_DIR_NAME.casefold() in queue.casefold() or str(Path(str(state["hidden_root"])).resolve()).casefold() in queue.casefold():
        raise Phase6Error("WORK_QUEUE 泄漏 hidden truth 路径")


def _status_summary(state: dict[str, Any]) -> dict[str, Any]:
    books = []
    for book in _ordered_books(state):
        handoff = get_handoff(_db(book), str(book["distill"]["handoff_id"]))
        chapters = {}
        for ordinal, chapter in book["chapters"].items():
            chapters[ordinal] = {
                "candidate_task": None if not chapter.get("candidate_task") else chapter["candidate_task"]["task_id"],
                "candidate_output": bool(chapter.get("candidate_task") and Path(str(chapter["candidate_task"]["expected_output"])).is_file()),
                "candidate_imported": bool(chapter.get("candidate_import")),
                "draft_task": None if not chapter.get("draft_task") else chapter["draft_task"]["task_id"],
                "draft_output": bool(chapter.get("draft_task") and Path(str(chapter["draft_task"]["expected_output"])).is_file()),
                "draft_imported": bool(chapter.get("draft_import")),
                "validated": bool(chapter.get("validation", {}).get("passed")),
            }
        books.append({"book_id": book["book_id"], "variant": book["variant"], "boundary": BOUNDARY, "innovation_control": book["innovation_control"], "candidate_runtime": book["candidate_runtime"], "draft_runtime": book["draft_runtime"], "distill_handoff_id": book["distill"]["handoff_id"], "distill_status": handoff["status"], "chapters": chapters, "generation_closed": book["generation_closed"], "truth_revealed": book["truth_revealed"]})
    return {"schema_version": STATE_SCHEMA, "run_label": state["run_label"], "phase": _stage(state), "generation_closed": state.get("generation_closed", False), "truth_revealed": state.get("truth_revealed", False), "work_queue": str(Path(str(state["controller_root"])) / "WORK_QUEUE.md"), "books": books}


def _system_language_leaks(book: dict[str, Any]) -> list[dict[str, Any]]:
    leaks = []
    for ordinal, chapter in book["chapters"].items():
        draft = chapter.get("draft_import")
        if not draft:
            continue
        prose = str(draft.get("prose_markdown", ""))
        found = [term for term in SYSTEM_LANGUAGE_TERMS if term.casefold() in prose.casefold()]
        if found:
            leaks.append({"chapter": int(ordinal), "terms": sorted(set(found)), "output": draft.get("output_path")})
    return leaks


def _safety(book: dict[str, Any]) -> dict[str, Any]:
    after = p5._safety_state(_db(book), str(book["book_id"]))
    return {
        "state_invariants": p5._safety_compare(book["safety_before"], after),
        "source_unchanged": True,
        "canon_write": False,
        "edition_activation": False,
        "approved_drafts": False,
    }


def _context_gate(state: dict[str, Any]) -> dict[str, Any]:
    by_variant = {str(book["variant"]): book for book in _ordered_books(state)}
    groups = {
        "level": ["L1", "L3", "L5"],
        "direction": ["L3", "RELATIONSHIP", "WORLD"],
    }
    results: dict[str, Any] = {}
    for name, variants in groups.items():
        baseline = by_variant["L3"]
        comparisons: list[dict[str, Any]] = []
        for chapter in (BOUNDARY + 1, BOUNDARY + 2):
            for stage in ("candidate", "draft"):
                reference_path = (
                    Path(str(baseline["benchmark_root"]))
                    / "context_manifests"
                    / f"chapter_{chapter:03d}_{stage}.json"
                )
                if not reference_path.is_file():
                    continue
                reference = _read_json(reference_path).get("semantic_inputs", {})
                for variant in variants:
                    if variant == "L3":
                        continue
                    candidate_path = (
                        Path(str(by_variant[variant]["benchmark_root"]))
                        / "context_manifests"
                        / f"chapter_{chapter:03d}_{stage}.json"
                    )
                    if not candidate_path.is_file():
                        continue
                    candidate = _read_json(candidate_path).get("semantic_inputs", {})
                    differences = compare_experiment_contexts(reference, candidate)
                    reference_fingerprint = build_experiment_context_fingerprint(
                        visible_source=reference.get("visible_source", {}),
                        distill_soft_context=reference.get("distill_soft_context", {}),
                        runtime_state=reference.get("runtime_state", {}),
                        earned_surface=reference.get("earned_surface", {}),
                        author_directives=reference.get("author_directives", {}),
                        recent_chapter_window=reference.get("recent_chapter_window", {}),
                    )
                    candidate_fingerprint = build_experiment_context_fingerprint(
                        visible_source=candidate.get("visible_source", {}),
                        distill_soft_context=candidate.get("distill_soft_context", {}),
                        runtime_state=candidate.get("runtime_state", {}),
                        earned_surface=candidate.get("earned_surface", {}),
                        author_directives=candidate.get("author_directives", {}),
                        recent_chapter_window=candidate.get("recent_chapter_window", {}),
                    )
                    comparisons.append(
                        {
                            "chapter": chapter,
                            "stage": stage,
                            "baseline": "L3",
                            "variant": variant,
                            "differences": differences,
                            "baseline_fingerprint": reference_fingerprint.model_dump(mode="json"),
                            "variant_fingerprint": candidate_fingerprint.model_dump(mode="json"),
                        }
                    )
        results[name] = {"status": "PASS" if all(not item["differences"] for item in comparisons) else "EXPERIMENT_CONFOUNDED", "comparisons": comparisons}
    return results


def _innovation_results(book: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    control = InnovationControl.model_validate(book["innovation_control"])
    for ordinal, chapter in sorted(book["chapters"].items(), key=lambda item: int(item[0])):
        draft = chapter.get("draft_import", {})
        trace = draft.get("innovation_trace")
        if not isinstance(trace, dict):
            continue
        realized = [InnovationFocus(item) for item in trace.get("realized_directions", [])]
        alignment = assess_innovation_alignment(control.focus, realized)
        meaningful = classify_novelty(
            meaningful_state_changes=trace.get("meaningful_state_changes", []),
            future_options_opened=trace.get("future_options_opened", []),
            new_relationship_states=trace.get("new_relationship_states", []),
            new_world_elements=trace.get("new_world_elements", []),
            new_mechanisms=trace.get("new_mechanisms", []),
        )
        estimated_cost = estimate_integration_cost(
            new_entities=trace.get("new_entities", []),
            new_relationship_states=trace.get("new_relationship_states", []),
            new_world_elements=trace.get("new_world_elements", []),
            new_mechanisms=trace.get("new_mechanisms", []),
            future_options_opened=trace.get("future_options_opened", []),
        )
        results.append({"chapter": int(ordinal), "requested_level": trace.get("requested_level"), "requested_focus": trace.get("requested_focus"), "realized_level": trace.get("realized_level"), "realized_directions": trace.get("realized_directions", []), "alignment": alignment.model_dump(mode="json"), "forward_novelties": trace.get("forward_novelties", []), "earned_recombinations": trace.get("earned_recombinations", []), "new_entities": trace.get("new_entities", []), "new_relationship_states": trace.get("new_relationship_states", []), "new_world_elements": trace.get("new_world_elements", []), "new_mechanisms": trace.get("new_mechanisms", []), "meaningful_state_changes": trace.get("meaningful_state_changes", []), "future_options_opened": trace.get("future_options_opened", []), "future_options_closed": trace.get("future_options_closed", []), "realized_elements": trace.get("realized_elements", []), "realized_synergies": trace.get("realized_synergies", []), "realized_horizon_effects": trace.get("realized_horizon_effects", {}), "realized_payoffs": trace.get("realized_payoffs", []), "realized_new_debt": trace.get("realized_new_debt", []), "narrative_delta": trace.get("realized_narrative_delta"), "novelty_quality": meaningful.value, "integration_cost_reported": trace.get("integration_cost"), "integration_cost_estimated": estimated_cost.value, "recent_pattern_distance": trace.get("recent_pattern_distance"), "candidate_preview": chapter.get("candidate_preview", []), "expected_innovation_reward": chapter.get("draft_import", {}).get("expected_innovation_reward", {}), "realized_innovation_reward": chapter.get("draft_import", {}).get("realized_innovation_reward", {}), "innovation_underdelivery": chapter.get("draft_import", {}).get("innovation_underdelivery", {}), "semantic_policy_leak": chapter.get("draft_import", {}).get("semantic_policy_leak", {})})
    return results


def _evaluate_book(state: dict[str, Any], book: dict[str, Any]) -> dict[str, Any]:
    hidden_dir = Path(str(state["hidden_root"])) / str(book["hidden_controller_key"])
    hidden_texts = [(hidden_dir / "chapter_061.md").read_text(encoding="utf-8"), (hidden_dir / "chapter_062.md").read_text(encoding="utf-8")]
    truth_overlap = {}
    for index, text in enumerate(hidden_texts, start=1):
        prose = str(book["chapters"][str(BOUNDARY + index)]["draft_import"]["prose_markdown"])
        truth_overlap[str(BOUNDARY + index)] = p5._token_overlap(prose, text)
    return {
        "book_id": book["book_id"],
        "variant": book["variant"],
        "boundary": BOUNDARY,
        "requested": book["innovation_control"],
        "runtime_ablation": "FULL_RUNTIME" if book["draft_runtime"] else "PLANNING_ONLY",
        "generation": {"closed": book["generation_closed"], "validated": all(bool(item.get("validation", {}).get("passed")) for item in book["chapters"].values()), "validator_counts": [item.get("validation", {}).get("validator_count") for item in book["chapters"].values()]},
        "innovation": _innovation_results(book),
        "system_language_leak": {"status": "SYSTEM_LANGUAGE_LEAK" if _system_language_leaks(book) else "CLEAR", "findings": _system_language_leaks(book)},
        "semantic_policy_leak": {
            "status": "SEMANTIC_POLICY_LEAK"
            if any(
                item.get("semantic_policy_leak", {}).get("status")
                == "SEMANTIC_POLICY_LEAK"
                for item in _innovation_results(book)
            )
            else "CLEAR",
            "findings": [
                {
                    "chapter": item["chapter"],
                    **item.get("semantic_policy_leak", {}),
                }
                for item in _innovation_results(book)
                if item.get("semantic_policy_leak", {}).get("status")
                == "SEMANTIC_POLICY_LEAK"
            ],
        },
        "safety": _safety(book),
        "truth_reference": {"revealed_after_generation_closed": True, "token_overlap_auxiliary_only": truth_overlap},
        "pattern_distance": [item.get("recent_pattern_distance") for item in _innovation_results(book)],
        "style_fidelity": "REVIEW_REQUIRED_FROM_LIVE_TEXT",
        "literary_review": {"status": "REVIEW_REQUIRED", "dimensions": list(DIMENSIONS) + ["specificity", "scene_vividness", "character_agency", "surprise", "causal_novelty", "payoff_strength", "hook_strength"]},
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
                    "generation_timestamps": {"candidate": chapter.get("candidate_import", {}).get("generation_timestamp"), "draft": chapter.get("draft_import", {}).get("generation_timestamp")},
                }
                for ordinal, chapter in book["chapters"].items()
            },
        },
    }


def _write_report(state: dict[str, Any], evaluations: list[dict[str, Any]], context_gate: dict[str, Any]) -> Path:
    lines = [
        "# Phase 6 — Author-Controlled Innovation & Calibration",
        "",
        f"Run label: `{state['run_label']}`；boundary: `{BOUNDARY} → {BOUNDARY + 1}/{BOUNDARY + 2}`",
        "",
        "本报告只接受由对应 READY_FOR_CODEX/Operation 生成并经十项 Validator 的真实结果。请求 level 与 realized innovation 分开记录；Truth 仅在 generation_closed 后读取，且不是唯一创新目标。",
        "",
        "## Context Equality Gate",
        "",
        f"- Level group (L1/L3/L5): `{context_gate['level']['status']}`",
        f"- Direction group (L3/RELATIONSHIP/WORLD): `{context_gate['direction']['status']}`",
        "- 若 status 为 EXPERIMENT_CONFOUNDED，不得把 level/focus 差异解释为文学结论。",
        "",
        "## Level Comparison",
        "",
        "| variant | requested | realized direction / level | meaningful vs cosmetic | future options | integration cost | safety | leak |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in evaluations:
        innovation = item["innovation"]
        realized = "; ".join(
            f"ch{entry['chapter']}: {','.join(entry['realized_directions']) or 'REVIEW_REQUIRED'} / {entry['realized_level'] or 'REVIEW_REQUIRED'}"
            for entry in innovation
        )
        novelty = "; ".join(f"ch{entry['chapter']}: {entry['novelty_quality']}" for entry in innovation)
        future = "; ".join(f"ch{entry['chapter']}: {len(entry['future_options_opened'])} opened" for entry in innovation)
        costs = "; ".join(f"ch{entry['chapter']}: {entry['integration_cost_estimated']}" for entry in innovation)
        lines.append(f"| `{item['variant']}` | `{json_dumps(item['requested'])}` | {realized} | {novelty} | {future} | {costs} | `{item['safety']['state_invariants']}` | `{item['system_language_leak']['status']}` |")
    lines.extend(
        [
            "",
            "## Direction Comparison",
            "",
            "固定 MEDIUM 后比较 AUTO、RELATIONSHIP、WORLD。DirectionAlignment 以 requested_focus 与真实 realized_directions 计算；不会因为方向设置不同而改变 hard gate。",
            "",
            "## Requested vs Realized / Future Option Delta",
            "",
            "每个版本的 InnovationTrace、候选 Preview、forward_novelties、earned_recombinations、new relationship/world/mechanism、meaningful state changes、future_options_opened/closed 和 integration cost 均保存在各 Book 的 evaluation.json。若字段没有由 Desktop output 提供，状态保持 REVIEW_REQUIRED，不由 Python 猜测。",
            "",
            "## Full Runtime Draft vs Planning-only Runtime",
            "",
            "C 只在 Candidate Planning 使用 Runtime；Draft 仅加载 Chapter Contract、最近正文和 style/dialogue/narrative controls。请重点审阅 Full Runtime 是否出现说明书化或审计型叙事惯性。",
            "",
            "## Safety / State",
            "",
            "所有版本必须保持 book/ 原文不变、Canon events/projection/approved drafts 不变、Edition active state 不变；任何失败都不能被 InnovationControl 覆盖。",
            "",
            "## Handoff provenance",
            "",
            "下表记录每一个候选和正文由哪个 handoff/operation、哪个 input context manifest、哪个 output artifact 和什么时间生成。Candidate/Draft 是 canonical Operation handoff，因此 handoff_id 显示为 N/A，operation_id 使用 task_id。",
            "",
            "| variant | chapter | artifact | handoff_id | task/operation_id | context | output | generated_at |",
            "|---|---:|---|---|---|---|---|---|",
        ]
    )
    for item in evaluations:
        artifacts = item["artifacts"]
        lines.append(f"| `{item['variant']}` | Distill | distill | `{artifacts['distill_handoff_id']}` | `{artifacts['distill_handoff_id']}` | `{artifacts['distill_input_context_manifest']}` | `{artifacts['distill_output_artifact']}` | `{artifacts['distill_generation_timestamp']}` |")
        for ordinal, artifact in artifacts["chapters"].items():
            lines.append(f"| `{item['variant']}` | {ordinal} | candidate | `{artifact['candidate_handoff_id'] or 'N/A'}` | `{artifact['candidate_task_id']}` | `{artifact['candidate_context_manifest']}` | `{artifact['candidate_output']}` | `{artifact['generation_timestamps']['candidate']}` |")
            lines.append(f"| `{item['variant']}` | {ordinal} | draft | `{artifact['draft_handoff_id'] or 'N/A'}` | `{artifact['draft_task_id']}` | `{artifact['draft_context_manifest']}` | `{artifact['draft_file']}` | `{artifact['generation_timestamps']['draft']}` |")
    report = "\n".join(lines) + "\n"
    run_report = Path(str(state["run_root"])) / "phase6_innovation_control.md"
    _write_text(run_report, report)
    root_report = ROOT / "benchmark" / "phase6_innovation_control.md"
    _write_text(root_report, report)
    return root_report


def _evaluate(state: dict[str, Any]) -> dict[str, Any]:
    if not all(bool(book.get("generation_closed")) for book in _ordered_books(state)):
        raise Phase6Error("evaluate 拒绝执行：所有 variant 必须先 generation_closed=true")
    if state.get("truth_revealed"):
        raise Phase6Error("该 run 已揭示 hidden truth，拒绝重复 evaluate")
    if not _source_unchanged(state):
        raise Phase6Error("evaluate 拒绝执行：source 在 benchmark 期间发生变化")
    for book in _ordered_books(state):
        _visible_audit(state, book)
        hidden_dir = Path(str(state["hidden_root"])) / str(book["hidden_controller_key"])
        if not hidden_dir.is_dir():
            raise Phase6Error(f"hidden truth 不完整：{book['book_id']}")
    # This is the first point at which the controller reads hidden truth.
    context_gate = _context_gate(state)
    evaluations = [_evaluate_book(state, book) for book in _ordered_books(state)]
    for book in _ordered_books(state):
        snapshot_path = Path(str(book["benchmark_root"])) / "generation_snapshot.json"
        snapshot = _read_json(snapshot_path)
        snapshot.update({"truth_revealed": True, "hidden_truth_loaded": True, "reveal_stage": "AFTER_GENERATION_CLOSED"})
        _write_json(snapshot_path, snapshot)
        book["truth_revealed"] = True
    report = _write_report(state, evaluations, context_gate)
    payload = {"schema_version": "phase6-live-evaluation-v1", "run_label": state["run_label"], "truth_revealed": True, "context_equality_gate": context_gate, "report": str(report), "books": evaluations}
    _write_json(Path(str(state["run_root"])) / "evaluation.json", payload)
    _write_queue(state)
    state["truth_revealed"] = True
    _save_state(state)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 6 true-live InnovationControl benchmark")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--run-label", default="v1")
    prepare.add_argument("--source", type=Path, default=SOURCE)
    prepare.add_argument("--skip-c", action="store_true")
    prepare.add_argument("--variant", default=None, help="只准备一个变体；用于单变体真实 draft acceptance")
    prepare.add_argument("--controller-root", type=Path, default=None)
    prepare.add_argument("--hidden-root", type=Path, default=None)
    prepare.add_argument("--library-root", type=Path, default=None)
    for command in ("status", "collect", "evaluate"):
        item = sub.add_parser(command)
        item.add_argument("--run-label", default="v1")
        item.add_argument("--controller-root", type=Path, default=None)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "prepare":
            result = _prepare_run(run_label=str(args.run_label), source=Path(args.source), controller_root=args.controller_root, hidden_root=args.hidden_root, library_root=args.library_root, include_c=not bool(args.skip_c), only_variant=args.variant)
        else:
            state = _load_state(str(args.run_label), controller_root=args.controller_root)
            if args.command == "status":
                result = _status_summary(state)
            elif args.command == "collect":
                result = _collect(state)
            else:
                result = _evaluate(state)
    except (Phase6Error, OSError, ValueError, RuntimeError) as exc:
        print(str(exc), flush=True)
        raise SystemExit(2) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
