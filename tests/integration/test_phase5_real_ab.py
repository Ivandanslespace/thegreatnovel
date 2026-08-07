from __future__ import annotations

import json
from pathlib import Path

from novel_authoring.benchmark.real_ab import anti_leak_audit, template_diagnostics
from novel_authoring.context.router import (
    ContextPurpose,
    RuntimeContextRequest,
    route_runtime_context,
)
from novel_authoring.db.database import Database
from novel_authoring.distill.models import EvidenceMappingStatus
from novel_authoring.distill.service import prepare_book_sources
from novel_authoring.runtime_baseline import build_runtime_baseline
from novel_authoring.storage.library import LibraryAddOptions, add_book

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def test_router_explicitly_separates_distill_only_from_fused_runtime(tmp_path: Path) -> None:
    added = add_book(
        LibraryAddOptions(
            book_id="phase5-router-book",
            title="Phase 5 router",
            source=FIXTURE,
            library_root=tmp_path / "library",
            confirm_order=True,
        )
    )
    database = Database(added.database)
    prepared = prepare_book_sources(database, added.book_id)
    index = json.loads(
        (Path(str(prepared["root"])) / "chapter_index.json").read_text(encoding="utf-8")
    )
    segment = index["sources"][0]["segments"][0]
    input_path = tmp_path / "baseline.json"
    input_path.write_text(
        json.dumps(
            {
                "book_id": added.book_id,
                "edition_id": "base",
                "boundary_chapter": 3,
                "scope": "SELF_BOOK",
                "entries": [
                    {
                        "entry_id": "capability-1",
                        "category": "capability",
                        "name": "可验证能力",
                        "statement": "source-derived capability",
                        "status": "SOURCE_VERIFIED",
                        "source_kind": "SOURCE_TEXT",
                        "evidence": [
                            {
                                "source_id": prepared["source_ids"][0],
                                "segment_id": segment["segment_id"],
                                "start_line": int(segment["start_line"]) + 1,
                                "end_line": int(segment["start_line"]) + 3,
                                "chapter_id": segment["chapter_id"],
                                "source_span_ids": [segment["source_span_id"]],
                                "mapping_status": EvidenceMappingStatus.EXACT.value,
                                "direct_text_confirmed": True,
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    build_runtime_baseline(database, added.book_id, input_path=input_path, boundary_chapter=3)

    distill_only = route_runtime_context(
        database,
        added.book_id,
        purpose=ContextPurpose.DRAFT,
        request=RuntimeContextRequest(
            purpose=ContextPurpose.DRAFT,
            include_runtime_state=False,
        ),
    )
    fused = route_runtime_context(
        database,
        added.book_id,
        purpose=ContextPurpose.DRAFT,
    )
    assert not distill_only.runtime_state_enabled
    assert distill_only.effective_runtime_state is None
    assert distill_only.earned_surface is None
    assert distill_only.baseline_recall_candidates == []
    assert distill_only.hard_constraints == {}
    assert fused.runtime_state_enabled
    assert fused.effective_runtime_state is not None
    assert fused.earned_surface is not None


def test_phase5_template_diagnostics_is_not_a_literary_score() -> None:
    collapsed = template_diagnostics(
        [
            {"chapter": 36, "prose": "他先确认资源。\n\n他做出选择，代价随之出现。"},
            {"chapter": 37, "prose": "他先确认资源。\n\n他做出选择，代价随之出现。"},
        ]
    )
    divergent = template_diagnostics(
        [
            {"chapter": 36, "prose": "雨幕里有人敲了三下玻璃。\n\n他没有立刻回应。"},
            {"chapter": 37, "prose": "交易完成后，远处的灯光突然熄灭。\n\n他改走另一条路。"},
        ]
    )
    assert collapsed["status"] == "PROSE_TEMPLATE_COLLAPSE"
    assert divergent["status"] == "DIVERGENT"
    assert "score" not in collapsed
    assert "score" not in divergent


def test_phase5_anti_leak_audit_checks_hidden_truth_only_after_reveal(tmp_path: Path) -> None:
    generation = tmp_path / "generation"
    generation.mkdir()
    (generation / "context.json").write_text(
        json.dumps({"truth_revealed": False, "runtime_state_enabled": False}),
        encoding="utf-8",
    )
    hidden = tmp_path / "hidden_ground_truth"
    hidden.mkdir()
    result = anti_leak_audit(
        variant="A",
        generation_files=[generation],
        hidden_root=hidden,
        hidden_texts=["不可在生成阶段读取的独特句子"],
    )
    assert result["passed"]
