from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_authoring.canon.projection import CanonProjection
from novel_authoring.context.router import (
    ContextPurpose,
    DistillationSoftContext,
    RuntimeContextBundle,
    RuntimeContextRequest,
    _artifact_matches,
)
from novel_authoring.distill.models import (
    DistilledEvidence,
    DistillScope,
    EvidenceMappingStatus,
    LiteraryArc,
    RuntimeRecallCandidate,
)
from novel_authoring.metrics.gates import HardGateInput
from novel_authoring.planning.diagnostics import diagnose_candidate_portfolio
from novel_authoring.planning.models import (
    CandidateLens,
    CandidateProposal,
    CandidateScoreInputs,
    NoveltyBoundary,
    NoveltyDeclaration,
    NoveltyProvenance,
)
from novel_authoring.runtime_baseline import (
    BaselineCategory,
    BaselineEvidence,
    BaselineStatus,
    EffectiveRuntimeState,
    RuntimeBaseline,
    RuntimeBaselineEntry,
    RuntimeBaselineManifest,
    build_earned_surface,
    build_effective_runtime_state,
    build_runtime_baseline,
    hydrate_runtime_baseline,
    load_runtime_baseline,
)
from novel_authoring.storage.library import LibraryAddOptions, add_book

FIXTURE = Path(__file__).parents[1] / "fixtures" / "合成求生小说.md"


def _evidence() -> BaselineEvidence:
    return BaselineEvidence(
        source_id="source-1",
        segment_id="segment-0001",
        start_line=1,
        end_line=2,
        mapping_status=EvidenceMappingStatus.PARTIAL,
    )


def _baseline_entry(
    *,
    category: BaselineCategory,
    name: str,
    statement: str,
    attributes: dict[str, str] | None = None,
) -> RuntimeBaselineEntry:
    return RuntimeBaselineEntry(
        entry_id=f"entry-{name}",
        category=category,
        name=name,
        statement=statement,
        status=BaselineStatus.SOURCE_PARTIAL,
        source_kind="SOURCE_TEXT",
        evidence=[_evidence()],
        attributes=attributes or {},
    )


def _baseline(entries: list[RuntimeBaselineEntry]) -> RuntimeBaseline:
    manifest = RuntimeBaselineManifest(
        baseline_id="baseline-1",
        book_id="book-1",
        edition_id="base",
        boundary_chapter=10,
        created_at="2026-01-01T00:00:00+00:00",
    )
    return RuntimeBaseline(manifest=manifest, entries=entries)


def _proposal(
    local_id: str,
    lens: CandidateLens,
    *,
    novelty: list[NoveltyDeclaration] | None = None,
    wildcard: bool = False,
) -> CandidateProposal:
    score = CandidateScoreInputs(**{name: 60 for name in CandidateScoreInputs.model_fields})
    gate = HardGateInput(
        character_fit_inputs={"agency": 80, "consistency": 80},
        style_fit_inputs={"sentence": 80, "diction": 80},
    )
    return CandidateProposal(
        local_id=local_id,
        title=f"候选 {local_id}",
        summary="A structurally distinct candidate.",
        primary_thread_id="thread-1",
        primary_function="setup",
        reader_question="what changes next",
        event_source=f"source-{local_id}",
        solution_method=f"method-{local_id}",
        protagonist_strategy=f"strategy-{local_id}",
        risk_form=f"risk-{local_id}",
        opportunity_cost=f"cost-{local_id}",
        emotional_outcome=f"emotion-{local_id}",
        social_feedback=f"social-{local_id}",
        scene_topology=f"topology-{local_id}",
        ending_state=f"ending-{local_id}",
        state_changes=[f"state-{local_id}"],
        causal_sources=["baseline:entry-capability-1"],
        required_irreversible_change=f"change-{local_id}",
        required_cost=f"required-cost-{local_id}",
        commit_updates=[f"update-{local_id}"],
        pressure_before=40,
        pressure_target_after=55,
        score_inputs=score,
        score_evidence={name: ["evidence"] for name in CandidateScoreInputs.model_fields},
        gate_input=gate,
        lens=lens,
        novelty_provenance=novelty or [],
        wildcard=wildcard,
    )


def test_effective_runtime_state_projection_delta_overrides_baseline() -> None:
    baseline_entry = _baseline_entry(
        category=BaselineCategory.CAPABILITY,
        name="capability-1",
        statement="baseline state",
        attributes={"record_id": "capability-1"},
    )
    baseline = _baseline([baseline_entry])
    projection = CanonProjection(
        book_id="book-1",
        capabilities={
            "capability-1": {
                "capability_id": "capability-1",
                "name": "capability-1",
                "statement": "canon delta state",
                "status": "CANON",
                "_event_seq": 4,
            }
        },
        through_event_seq=4,
    )
    state = build_effective_runtime_state(baseline, projection)
    assert isinstance(state, EffectiveRuntimeState)
    assert state.records["capability"][0].statement == "canon delta state"
    assert state.records["capability"][0].source == "CANON_PROJECTION"
    assert baseline.entries[0].statement == "baseline state"


def test_effective_runtime_state_keeps_unknown_out_of_records() -> None:
    unknown = RuntimeBaselineEntry(
        entry_id="unknown",
        category=BaselineCategory.ITEM,
        name="not-confirmed",
        statement="not source verified",
        status=BaselineStatus.UNKNOWN,
        source_kind="DISTILL_RECALL",
    )
    state = build_effective_runtime_state(_baseline([unknown]), CanonProjection(book_id="book-1"))
    assert state.records == {}
    assert any("not-confirmed" in item for item in state.hard_unknowns)


def test_earned_surface_preserves_actionable_metadata() -> None:
    entry = _baseline_entry(
        category=BaselineCategory.KNOWLEDGE,
        name="field-method",
        statement="A source-established method can be used under a condition.",
        attributes={
            "availability": "CONDITIONAL",
            "costs": "time|material",
            "constraints": "requires daylight",
            "last_confirmed": "8",
        },
    )
    surface = build_earned_surface(_baseline([entry]), CanonProjection(book_id="book-1"))
    assert surface.actionable_knowledge[0].availability == "CONDITIONAL"
    assert surface.actionable_knowledge[0].costs == ["time", "material"]
    assert surface.actionable_knowledge[0].constraints == ["requires daylight"]
    assert surface.actionable_knowledge[0].last_confirmed == 8


def test_literary_arc_overlap_includes_touching_known_range() -> None:
    arc = LiteraryArc(
        arc_id="arc-1",
        name="arc",
        start_segment="segment-1",
        end_segment="segment-5",
        start_chapter="chapter-10",
        end_chapter="chapter-20",
        causal_summary="cause",
    )
    request = RuntimeContextRequest(
        purpose=ContextPurpose.CANDIDATE_PLANNING,
        chapter_range=[20, 25],
    )
    assert _artifact_matches(arc, request)


def test_literary_arc_non_overlapping_known_range_is_excluded() -> None:
    arc = LiteraryArc(
        arc_id="arc-1",
        name="arc",
        start_segment="segment-1",
        end_segment="segment-5",
        start_chapter="chapter-10",
        end_chapter="chapter-20",
        causal_summary="cause",
    )
    request = RuntimeContextRequest(
        purpose=ContextPurpose.CANDIDATE_PLANNING,
        chapter_range=[21, 25],
    )
    assert not _artifact_matches(arc, request)


def test_literary_arc_unknown_range_is_soft_included() -> None:
    arc = LiteraryArc(
        arc_id="arc-unknown",
        name="arc",
        start_segment="segment-1",
        end_segment="segment-5",
        causal_summary="cause",
    )
    request = RuntimeContextRequest(
        purpose=ContextPurpose.DRAFT,
        chapter_range=[21, 25],
    )
    assert _artifact_matches(arc, request)


def test_runtime_bundle_has_explicit_layers() -> None:
    request = RuntimeContextRequest(purpose=ContextPurpose.DRAFT)
    soft = DistillationSoftContext(scope="SELF_BOOK", distill_id="distill-1")
    bundle = RuntimeContextBundle(
        request=request,
        book_id="book-1",
        edition_id="base",
        hard_boundary={"facts": {}},
        hard_constraints={"facts": {}},
        distillation_soft_context=soft,
    )
    assert bundle.hard_constraints == bundle.hard_boundary
    assert bundle.distillation_soft_context is soft


def test_scope_recall_candidate_is_not_a_runtime_entry() -> None:
    candidate = RuntimeRecallCandidate(
        candidate_id="recall:obs-1",
        category="knowledge",
        name="distill:obs-1",
        statement="A lead that requires review.",
        dimension="plot",
        observation_id="obs-1",
        source_scope=DistillScope.SELF_BOOK,
        evidence=[
            DistilledEvidence(
                source_id="source-1",
                segment_id="segment-0001",
                start_line=1,
                end_line=2,
            )
        ],
        rationale="requires source review",
    )
    assert candidate.status == "RECALL_ONLY"


def test_distill_recall_cannot_be_source_verified() -> None:
    with pytest.raises(ValidationError):
        RuntimeBaselineEntry(
            entry_id="recall",
            category=BaselineCategory.KNOWLEDGE,
            name="recall",
            statement="Distill only",
            status=BaselineStatus.SOURCE_VERIFIED,
            source_kind="DISTILL_RECALL",
            evidence=[_evidence()],
        )


def test_forward_novelty_requires_complete_provenance() -> None:
    with pytest.raises(ValidationError):
        NoveltyDeclaration(provenance=NoveltyProvenance.FORWARD_NOVELTY)


def test_forward_novelty_accepts_causal_introduction() -> None:
    declaration = NoveltyDeclaration(
        provenance=NoveltyProvenance.FORWARD_NOVELTY,
        introduction_event="本章首次通过选择引入",
        causal_source="当前边界中的资源压力",
        new_state_if_committed="角色获得一个需付成本的新选择",
        conflicts_checked=["projection", "knowledge boundary"],
    )
    assert declaration.novelty_boundary is NoveltyBoundary.FORWARD_CANON_COMPATIBLE


def test_retroactive_invention_is_rejected_from_candidate() -> None:
    with pytest.raises(ValidationError):
        _proposal(
            "retro",
            CandidateLens.FORWARD_EXPANSION,
            novelty=[
                NoveltyDeclaration(
                    provenance=NoveltyProvenance.AUTHOR_DIRECTED,
                    novelty_boundary=NoveltyBoundary.RETROACTIVE_UNSUPPORTED_INVENTION,
                )
            ],
        )


def test_candidate_portfolio_reports_three_lenses_without_quota() -> None:
    forward = NoveltyDeclaration(
        provenance=NoveltyProvenance.FORWARD_NOVELTY,
        introduction_event="first introduction",
        causal_source="current pressure",
        new_state_if_committed="new conditional state",
        conflicts_checked=["canon"],
    )
    candidates = [
        _proposal("a", CandidateLens.CONTINUITY_ACTIVE_THREAD),
        _proposal("b", CandidateLens.EARNED_OPPORTUNITY),
        _proposal("c", CandidateLens.FORWARD_EXPANSION, novelty=[forward], wildcard=True),
    ]
    diagnostics = diagnose_candidate_portfolio(candidates)
    assert diagnostics.lens_counts == {
        "CONTINUITY_ACTIVE_THREAD": 1,
        "EARNED_OPPORTUNITY": 1,
        "FORWARD_EXPANSION": 1,
    }
    assert diagnostics.forward_novelty_count == 1
    assert diagnostics.wildcard_count == 1
    assert not diagnostics.warnings


def test_candidate_portfolio_counts_earned_usage() -> None:
    entry = _baseline_entry(
        category=BaselineCategory.CAPABILITY,
        name="capability-1",
        statement="earned capability",
    )
    surface = build_earned_surface(_baseline([entry]), CanonProjection(book_id="book-1"))
    candidate = _proposal("earned", CandidateLens.EARNED_OPPORTUNITY)
    diagnostics = diagnose_candidate_portfolio([candidate], earned_surface=surface)
    assert diagnostics.earned_usage_count == 1
    assert diagnostics.earned_surface_usage_coverage == 1


def test_distill_scope_values_remain_distinct() -> None:
    assert {
        DistillScope.SELF_BOOK.value,
        DistillScope.EXTERNAL_REFERENCE.value,
        DistillScope.COMPARATIVE_REFERENCE.value,
    } == {"SELF_BOOK", "EXTERNAL_REFERENCE", "COMPARATIVE_REFERENCE"}


def test_source_evidence_mapping_status_is_not_canon_status() -> None:
    evidence = DistilledEvidence(
        source_id="source-1",
        segment_id="segment-0001",
        start_line=1,
        end_line=2,
        mapping_status=EvidenceMappingStatus.EXACT,
        chapter_id="chapter-1",
        source_span_ids=["span-1"],
    )
    assert evidence.mapping_status is EvidenceMappingStatus.EXACT
    assert not hasattr(evidence, "CANON")


def test_lazy_hydration_merges_reviewed_entries_without_distill_promotion(tmp_path: Path) -> None:
    added = add_book(
        LibraryAddOptions(
            book_id="phase4-hydration-book",
            title="Phase 4 hydration",
            source=FIXTURE,
            library_root=tmp_path / "library",
            confirm_order=True,
        )
    )
    from novel_authoring.db.database import Database
    from novel_authoring.distill.service import prepare_book_sources

    database = Database(added.database)
    prepared = prepare_book_sources(database, "phase4-hydration-book")
    index = json.loads(
        (Path(str(prepared["root"])) / "chapter_index.json").read_text(encoding="utf-8")
    )
    segment = index["sources"][0]["segments"][0]
    with database.connect() as connection:
        span = connection.execute(
            "SELECT start_line, end_line FROM source_spans WHERE span_id=?",
            (str(segment["source_span_id"]),),
        ).fetchone()
    assert span is not None
    evidence = {
        "source_id": str(prepared["source_ids"][0]),
        "segment_id": str(segment["segment_id"]),
        "start_line": int(span["start_line"]),
        "end_line": int(span["end_line"]),
        "chapter_id": str(segment["chapter_id"]),
        "source_span_ids": [str(segment["source_span_id"])],
        "mapping_status": "EXACT",
        "direct_text_confirmed": True,
    }
    initial = tmp_path / "initial.json"
    initial.write_text(
        json.dumps(
            {
                "book_id": "phase4-hydration-book",
                "edition_id": "base",
                "boundary_chapter": 1,
                "scope": "SELF_BOOK",
                "entries": [
                    {
                        "entry_id": "existing-entry",
                        "category": "capability",
                        "name": "existing-entry",
                        "statement": "source reviewed existing state",
                        "status": "SOURCE_VERIFIED",
                        "source_kind": "SOURCE_TEXT",
                        "evidence": [evidence],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    build_runtime_baseline(
        database,
        "phase4-hydration-book",
        input_path=initial,
        boundary_chapter=1,
    )
    supplement = tmp_path / "supplement.json"
    supplement.write_text(
        json.dumps(
            {
                "book_id": "phase4-hydration-book",
                "edition_id": "base",
                "boundary_chapter": 1,
                "scope": "SELF_BOOK",
                "entries": [
                    {
                        "entry_id": "new-reviewed-entry",
                        "category": "knowledge",
                        "name": "new-reviewed-entry",
                        "statement": "source reviewed new state",
                        "status": "SOURCE_PARTIAL",
                        "source_kind": "AUTHOR_REVIEW",
                        "evidence": [evidence],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    hydrate_runtime_baseline(
        database,
        "phase4-hydration-book",
        supplement,
        boundary_chapter=1,
    )
    baseline = load_runtime_baseline(database, "phase4-hydration-book")
    assert baseline is not None
    assert {item.entry_id for item in baseline.entries} == {
        "existing-entry",
        "new-reviewed-entry",
    }
