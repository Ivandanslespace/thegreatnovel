from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

import phase5_live_ab as live  # noqa: E402


def _source(path: Path, chapter_count: int = 5) -> Path:
    path.write_text(
        "\n\n".join(
            f"## 第{ordinal}章 可见章节\n\n人物在第 {ordinal} 章面对一个仍待验证的问题。"
            for ordinal in range(1, chapter_count + 1)
        ),
        encoding="utf-8",
    )
    return path


def _prepared_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    monkeypatch.setattr(live, "BOUNDARIES", (2, 3))
    source = _source(tmp_path / "source.md")
    controller = tmp_path / "controller"
    return live._prepare_run(
        run_label="test-live",
        source=source,
        root=tmp_path,
        controller_root=controller,
        hidden_root=tmp_path / "hidden",
        library_root=tmp_path / "library",
    )


def test_prepare_creates_isolated_ready_handoffs_without_literary_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(live, "BOUNDARIES", (2, 3))
    source = _source(tmp_path / "source.md")
    summary = live._prepare_run(
        run_label="prepare-only",
        source=source,
        root=tmp_path,
        controller_root=tmp_path / "controller",
        hidden_root=tmp_path / "hidden",
        library_root=tmp_path / "library",
    )
    assert summary["phase"] == "DISTILL"
    assert len(summary["books"]) == 4
    state = live._load_state("prepare-only", controller_root=tmp_path / "controller")
    assert live._source_unchanged(state)
    for book in state["books"]:
        assert book["distill"]["status"] == "READY_FOR_CODEX"
        assert not book["distill"]["imported"]
        assert book["chapters"][str(int(book["boundary"]) + 1)] == {}
        assert Path(str(book["root"])).is_relative_to(tmp_path / "library")
        live._visible_and_hidden_audit(state, book)
        task_directory = Path(str(book["distill"]["task_directory"]))
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in task_directory.rglob("*")
            if path.is_file()
        )
        assert "phase5_live_hidden" not in content
        assert "hidden_truth_provided\": true" not in content
        assert not list(Path(str(book["root"])).rglob("generated/*.md"))


def test_collect_rejects_unfinished_distill_and_evaluate_rejects_open_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared_run(tmp_path, monkeypatch)
    state = live._load_state("test-live", controller_root=tmp_path / "controller")
    with pytest.raises(live.LiveBenchmarkError, match="READY_FOR_CODEX"):
        live._collect_run(state)
    with pytest.raises(live.LiveBenchmarkError, match="generation_closed"):
        live._evaluate_run(state)


def test_n_plus_2_candidate_input_contains_real_previous_provisional_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared_run(tmp_path, monkeypatch)
    state = live._load_state("test-live", controller_root=tmp_path / "controller")
    book = next(item for item in state["books"] if item["variant"] == "A" and item["boundary"] == 2)
    first_chapter = book["chapters"]["3"]
    first_chapter["candidate_task"] = live._prepare_candidate(state, book, chapter=3)
    previous_path = Path(str(book["benchmark_root"])) / "previous_chapter.md"
    previous_path.write_text("真实 N+1 临时正文：人物在现场改变了退路。", encoding="utf-8")
    first_chapter["draft_import"] = {
        "draft_id": "draft-live-3",
        "path": str(previous_path),
    }
    first_chapter["provisional_state"] = {
        "current_chapter_ordinal": 3,
        "canon_committed": False,
        "provisional_events": [{"chapter": 3, "status": "PROVISIONAL"}],
    }
    task = live._prepare_candidate(state, book, chapter=4, second=True)
    input_text = Path(str(task["input"])).read_text(encoding="utf-8")
    metadata = live._task_metadata(task)
    assert "真实 N+1 临时正文" in input_text
    assert "current_chapter_ordinal" in input_text
    assert metadata["benchmark_protocol"]["previous_provisional_state_present"] is True
    assert metadata["include_runtime_state"] is False
    assert "phase5_live_hidden" not in input_text


def test_a_b_runtime_isolation_and_prepare_preserves_canon_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepared_run(tmp_path, monkeypatch)
    state = live._load_state("test-live", controller_root=tmp_path / "controller")
    books = {
        str(book["variant"]): book
        for book in state["books"]
        if book["boundary"] == 2 and book["variant"] in {"A", "B"}
    }
    for variant, expected in (("A", False), ("B", True)):
        task = live._prepare_candidate(state, books[variant], chapter=3)
        metadata = live._task_metadata(task)
        assert metadata["benchmark_variant"] == variant
        assert metadata["include_runtime_state"] is expected
        assert task["context"]["runtime_layers"]["include_runtime_state"] is expected
        assert live._safety_state(
            live._database(books[variant]), str(books[variant]["book_id"])
        ) == books[variant]["safety_before"]


def test_system_language_leak_is_deterministically_reported(tmp_path: Path) -> None:
    output = tmp_path / "draft-output.json"
    output.write_text(
        json.dumps({"prose_markdown": "人物没有提到融合层，只写了 Runtime。"}),
        encoding="utf-8",
    )
    book = {
        "chapters": {
            "51": {"draft_import": {"output_path": str(output)}},
        }
    }
    findings = live._system_language_leaks(book)
    assert findings[0]["chapter"] == 51
    assert "runtime" in findings[0]["terms"]
    assert "融合层" in findings[0]["terms"]
