from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

import phase6_innovation_control as live  # noqa: E402


def _source(path: Path, chapter_count: int = 62) -> Path:
    path.write_text(
        "\n\n".join(
            f"## 第{ordinal}章 可见章节\n\n人物在第 {ordinal} 章面对一个仍待验证的问题。"
            for ordinal in range(1, chapter_count + 1)
        ),
        encoding="utf-8",
    )
    return path


def _prepared(tmp_path: Path, *, include_c: bool = True) -> dict[str, object]:
    source = _source(tmp_path / "source.md")
    return live._prepare_run(
        run_label="phase6-test",
        source=source,
        root=tmp_path,
        controller_root=tmp_path / "controller",
        hidden_root=tmp_path / "hidden",
        library_root=tmp_path / "library",
        include_c=include_c,
    )


def test_prepare_freezes_level_focus_runtime_and_blind_boundary(tmp_path: Path) -> None:
    summary = _prepared(tmp_path)
    assert summary["phase"] == "DISTILL"
    assert len(summary["books"]) == 6
    state = live._load_state("phase6-test", controller_root=tmp_path / "controller")
    assert live._source_unchanged(state)
    variants = {str(book["variant"]): book for book in state["books"]}
    assert variants["L1"]["innovation_control"] == {"level": "minimal", "focus": ["auto"]}
    assert variants["L3"]["innovation_control"] == {"level": "medium", "focus": ["auto"]}
    assert variants["L5"]["innovation_control"] == {"level": "bold", "focus": ["auto"]}
    assert variants["RELATIONSHIP"]["innovation_control"]["focus"] == ["relationship"]
    assert variants["WORLD"]["innovation_control"]["focus"] == ["world"]
    assert variants["C"]["candidate_runtime"] is True
    assert variants["C"]["draft_runtime"] is False
    for book in variants.values():
        assert book["distill"]["status"] == "READY_FOR_CODEX"
        assert book["chapters"]["61"] == {}
        live._visible_audit(state, book)
        task_root = Path(str(book["distill"]["task_directory"]))
        content = "\n".join(
            item.read_text(encoding="utf-8")
            for item in task_root.rglob("*")
            if item.is_file()
        )
        assert "phase6_live_hidden" not in content
        assert '"hidden_truth_provided": true' not in content


def test_collect_and_evaluate_refuse_open_live_run(tmp_path: Path) -> None:
    _prepared(tmp_path)
    state = live._load_state("phase6-test", controller_root=tmp_path / "controller")
    with pytest.raises(live.Phase6Error, match="Distill handoff"):
        live._collect(state)
    with pytest.raises(live.Phase6Error, match="generation_closed"):
        live._evaluate(state)


def test_runtime_isolation_and_n_plus_2_provisional_context(tmp_path: Path) -> None:
    _prepared(tmp_path, include_c=False)
    state = live._load_state("phase6-test", controller_root=tmp_path / "controller")
    books = {str(book["variant"]): book for book in state["books"]}
    before = {
        variant: live.p5._safety_state(live._db(book), str(book["book_id"]))
        for variant, book in books.items()
    }
    for variant in ("L1", "L3", "L5"):
        task = live._prepare_candidate(state, books[variant], chapter=61)
        metadata = live._load_task(task)[1]
        assert metadata["include_runtime_state"] is True
        assert metadata["innovation_control"] == books[variant]["innovation_control"]
        assert live._load_task(task)[1]["benchmark_protocol"]["hidden_truth_provided"] is False
    first = books["L3"]["chapters"]["61"]
    first["candidate_task"] = live._prepare_candidate(state, books["L3"], chapter=61)
    previous = Path(str(books["L3"]["benchmark_root"])) / "previous.md"
    previous.write_text("真实 N+1 provisional 正文。", encoding="utf-8")
    first["draft_import"] = {"draft_id": "draft-61", "path": str(previous)}
    first["provisional_state"] = {"current_chapter_ordinal": 61, "canon_committed": False}
    second = live._prepare_candidate(state, books["L3"], chapter=62, second=True)
    assert "真实 N+1 provisional 正文" in Path(str(second["input"])).read_text(encoding="utf-8")
    assert (
        live._load_task(second)[1]["benchmark_protocol"]["previous_provisional_state_present"]
        is True
    )
    assert all(
        live.p5._safety_state(live._db(book), str(book["book_id"])) == before[str(book["variant"])]
        for book in books.values()
    )


def test_planning_only_c_draft_metadata_has_no_raw_runtime(tmp_path: Path) -> None:
    _prepared(tmp_path, include_c=True)
    state = live._load_state("phase6-test", controller_root=tmp_path / "controller")
    book = next(item for item in state["books"] if item["variant"] == "C")
    task = live._prepare_candidate(state, book, chapter=61)
    assert live._load_task(task)[1]["include_runtime_state"] is True
    # Draft ablation is enforced in the control contract even before a real
    # Candidate/Contract arrives from Codex Desktop.
    assert book["draft_runtime"] is False
