"""Route hard runtime state and soft Distill knowledge by explicit purpose."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.db.database import Database
from novel_authoring.distill.models import (
    CharacterVoiceProfile,
    ContinuityCandidate,
    CraftControl,
    DistilledInformationClass,
    DistilledObservation,
    LiteraryArc,
    RuntimeRecallCandidate,
    ThemeQuestion,
)
from novel_authoring.distill.service import latest_distill_reference
from novel_authoring.edition import resolve_edition_id
from novel_authoring.runtime_baseline import (
    EarnedSurface,
    EffectiveRuntimeState,
    discover_runtime_recall_candidates,
    load_earned_surface,
    load_effective_runtime_state,
)
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.operations import book_root


class ContextPurpose(StrEnum):
    CANDIDATE_PLANNING = "candidate_planning"
    DRAFT = "draft"
    VALIDATION = "validation"


class RuntimeContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: ContextPurpose
    dimensions: list[str] = Field(default_factory=list)
    subject_ids: list[str] = Field(default_factory=list)
    related_entity_ids: list[str] = Field(default_factory=list)
    chapter_range: list[int] | None = None
    runtime_uses: list[str] = Field(default_factory=list)
    reference_scope: str | None = None


class RuntimeContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: RuntimeContextRequest
    book_id: str
    edition_id: str
    hard_boundary: dict[str, object]
    hard_constraints: dict[str, object] = Field(default_factory=dict)
    effective_runtime_state: EffectiveRuntimeState | None = None
    earned_surface: EarnedSurface | None = None
    observations: list[DistilledObservation] = Field(default_factory=list)
    literary_arcs: list[LiteraryArc] = Field(default_factory=list)
    continuity_candidates: list[ContinuityCandidate] = Field(default_factory=list)
    craft_controls: list[CraftControl] = Field(default_factory=list)
    character_voice_profiles: list[CharacterVoiceProfile] = Field(default_factory=list)
    theme_questions: list[ThemeQuestion] = Field(default_factory=list)
    distillation_soft_context: DistillationSoftContext | None = None
    distill_reference: dict[str, object] | None = None
    baseline_recall_candidates: list[RuntimeRecallCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DistillationSoftContext(BaseModel):
    """Purpose-filtered Distill artifacts; never a hard runtime ledger."""

    model_config = ConfigDict(extra="forbid")

    scope: str
    distill_id: str
    observations: list[DistilledObservation] = Field(default_factory=list)
    literary_arcs: list[LiteraryArc] = Field(default_factory=list)
    continuity_candidates: list[ContinuityCandidate] = Field(default_factory=list)
    craft_controls: list[CraftControl] = Field(default_factory=list)
    character_voice_profiles: list[CharacterVoiceProfile] = Field(default_factory=list)
    theme_questions: list[ThemeQuestion] = Field(default_factory=list)
    mapping_summary: dict[str, int] = Field(default_factory=dict)


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Context Router 无法读取：{path}") from exc


def _read_json_array(path: Path, model: type[BaseModel]) -> list[Any]:
    if not path.is_file():
        return []
    value = _read_json(path)
    if not isinstance(value, list):
        raise ValueError(f"Context Router artifact 必须是数组：{path}")
    return [model.model_validate(item) for item in value]


def _read_jsonl(path: Path, model: type[BaseModel]) -> list[Any]:
    if not path.is_file():
        return []
    values: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            values.append(model.model_validate(json.loads(line)))
    return values


def _default_request(purpose: ContextPurpose) -> RuntimeContextRequest:
    dimensions = {
        ContextPurpose.CANDIDATE_PLANNING: ["plot", "pacing", "themes", "continuity"],
        ContextPurpose.DRAFT: ["characters", "style", "narrative", "dialogue"],
        ContextPurpose.VALIDATION: ["continuity", "style", "narrative", "dialogue"],
    }[purpose]
    uses = {
        ContextPurpose.CANDIDATE_PLANNING: ["candidate_planning"],
        ContextPurpose.DRAFT: ["draft_controls"],
        ContextPurpose.VALIDATION: ["soft_validation"],
    }[purpose]
    return RuntimeContextRequest(purpose=purpose, dimensions=dimensions, runtime_uses=uses)


def _matches(observation: DistilledObservation, request: RuntimeContextRequest) -> bool:
    if request.dimensions and observation.dimension not in request.dimensions:
        return False
    if request.runtime_uses and not set(request.runtime_uses).intersection(
        observation.runtime_uses
    ):
        return False
    if request.subject_ids:
        known_subjects = set(observation.subject_ids) | set(observation.related_entity_ids)
        if not known_subjects or not known_subjects.intersection(request.subject_ids):
            return False
    if request.related_entity_ids:
        known_entities = set(observation.related_entity_ids) | set(observation.subject_ids)
        if not known_entities or not known_entities.intersection(request.related_entity_ids):
            return False
    if request.chapter_range and observation.chapter_range:
        start, end = request.chapter_range
        obs_start, obs_end = observation.chapter_range
        if obs_end < start or obs_start > end:
            return False
    return True


def _chapter_number(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", str(value))
    return None if match is None else int(match.group(0))


def _artifact_range(item: Any) -> tuple[int | None, int | None]:
    chapter_range = getattr(item, "chapter_range", None)
    if isinstance(chapter_range, list) and len(chapter_range) == 2:
        return int(chapter_range[0]), int(chapter_range[1])
    return _chapter_number(getattr(item, "start_chapter", None)), _chapter_number(
        getattr(item, "end_chapter", None)
    )


def _artifact_matches(item: Any, request: RuntimeContextRequest) -> bool:
    """Apply the same explicit metadata and overlap rules to every artifact."""

    if request.chapter_range:
        req_start, req_end = request.chapter_range
        item_start, item_end = _artifact_range(item)
        # An unknown range is soft-included.  A known range must overlap,
        # including touching endpoints.
        if (
            item_start is not None
            and item_end is not None
            and (item_end < req_start or item_start > req_end)
        ):
            return False
    subjects = set(getattr(item, "subject_ids", []))
    subjects.update(getattr(item, "related_entity_ids", []))
    subjects.update(getattr(item, "key_characters", []))
    character_id = getattr(item, "character_id", None)
    if character_id:
        subjects.add(str(character_id))
    if request.subject_ids and subjects and not subjects.intersection(request.subject_ids):
        return False
    if request.subject_ids and not subjects:
        return False
    if request.related_entity_ids and subjects and not subjects.intersection(
        request.related_entity_ids
    ):
        return False
    if request.related_entity_ids and not subjects:
        return False
    runtime_uses = set(getattr(item, "runtime_uses", []))
    if (
        request.runtime_uses
        and runtime_uses
        and not isinstance(item, CraftControl)
        and not runtime_uses.intersection(request.runtime_uses)
    ):
        return False
    if request.dimensions:
        category = str(getattr(item, "category", "")).casefold()
        applies_to = {str(value).casefold() for value in getattr(item, "applies_to", [])}
        tags = {str(value).casefold() for value in getattr(item, "tags", [])}
        known = {category, *applies_to, *tags} - {""}
        # Empty metadata is retained for compatibility with older packages.
        if (
            known
            and not isinstance(item, CraftControl)
            and not known.intersection(request.dimensions)
            and (
                not isinstance(item, LiteraryArc)
                or not known.intersection({"plot", "narrative", "themes", "continuity"})
                .intersection(request.dimensions)
            )
        ):
            return False
    return True


def _purpose_artifacts(
    purpose: ContextPurpose,
    request: RuntimeContextRequest,
    *,
    arcs: list[LiteraryArc],
    continuity: list[ContinuityCandidate],
    controls: list[CraftControl],
    voices: list[CharacterVoiceProfile],
    themes: list[ThemeQuestion],
) -> tuple[
    list[LiteraryArc],
    list[ContinuityCandidate],
    list[CraftControl],
    list[CharacterVoiceProfile],
    list[ThemeQuestion],
]:
    """Keep artifact routing purpose-specific without hiding explicit requests."""

    if purpose is ContextPurpose.CANDIDATE_PLANNING:
        return arcs, continuity, controls, voices, themes
    if purpose is ContextPurpose.DRAFT:
        return (
            arcs,
            continuity,
            controls,
            voices if request.subject_ids or "dialogue" in request.dimensions else [],
            themes if "themes" in request.dimensions else [],
        )
    return (
        arcs if "plot" in request.dimensions or "narrative" in request.dimensions else [],
        continuity,
        controls,
        voices if "dialogue" in request.dimensions or request.subject_ids else [],
        themes if "themes" in request.dimensions else [],
    )


def route_runtime_context(
    database: Database,
    book_id: str,
    *,
    purpose: ContextPurpose | str,
    edition_id: str | None = None,
    request: RuntimeContextRequest | None = None,
    boundary: dict[str, object] | None = None,
) -> RuntimeContextBundle:
    """Build a deterministic, purpose-specific context bundle.

    The projection is always the hard boundary.  Distill artifacts are soft
    additions and are filtered by dimension, metadata and runtime use; no
    vector search or semantic merge is performed here.
    """

    database.initialize()
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    selected_purpose = ContextPurpose(str(purpose))
    selected_request = request or _default_request(selected_purpose)
    if selected_request.purpose is not selected_purpose:
        raise ValueError("RuntimeContextRequest purpose 与 router purpose 不一致")
    projection = rebuild_projection(
        database, book_id, edition_id=selected_edition, persist=False
    )
    hard_boundary = dict(boundary or projection.model_dump(mode="json"))
    earned = load_earned_surface(database, book_id, edition_id=selected_edition)
    effective = load_effective_runtime_state(
        database, book_id, edition_id=selected_edition
    )
    bundle = RuntimeContextBundle(
        request=selected_request,
        book_id=book_id,
        edition_id=selected_edition,
        hard_boundary=hard_boundary,
        hard_constraints=dict(hard_boundary),
        effective_runtime_state=effective,
        earned_surface=earned,
    )
    root = book_root(database, book_id)
    edition = BookLayout(root.parent).for_book(book_id).edition(selected_edition)
    reference = latest_distill_reference(
        edition,
        scope=selected_request.reference_scope,
    )
    if reference is None:
        bundle.warnings.append(
            "当前 Edition 没有 Distill Package；仅提供 hard boundary/earned surface"
        )
        return bundle
    bundle.distill_reference = {
        key: value
        for key, value in reference.items()
        if key
        in {
            "distill_id",
            "scope",
            "book_id",
            "edition_id",
            "dimensions",
            "depth",
            "skill_root",
            "package_root",
            "machine_manifest",
            "usage",
            "mapping_summary",
        }
    }
    bundle.baseline_recall_candidates = discover_runtime_recall_candidates(
        database,
        book_id,
        edition_id=selected_edition,
        reference=reference,
    )
    package_root = Path(str(reference.get("package_root", ""))).expanduser().resolve()
    if not package_root.is_dir():
        bundle.warnings.append("Distill Package machine root 不存在")
        return bundle
    observations_path = package_root / "observations.jsonl"
    if observations_path.is_file():
        for line in observations_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                observation = DistilledObservation.model_validate(json.loads(line))
                if _matches(observation, selected_request):
                    bundle.observations.append(observation)
    arcs = [
        item
        for item in _read_json_array(package_root / "literary_arcs.json", LiteraryArc)
        if _artifact_matches(item, selected_request)
    ]
    continuity = [
        item
        for item in _read_jsonl(
            package_root / "continuity_candidates.jsonl", ContinuityCandidate
        )
        if item.verification_status.value != "RESOLVED"
        and _artifact_matches(item, selected_request)
    ]
    controls = [
        item
        for item in _read_json_array(package_root / "craft_controls.json", CraftControl)
        if _artifact_matches(item, selected_request)
    ]
    voices = [
        item
        for item in _read_json_array(
            package_root / "character_voice_profiles.json", CharacterVoiceProfile
        )
        if _artifact_matches(item, selected_request)
    ]
    themes = [
        item
        for item in _read_json_array(package_root / "theme_questions.json", ThemeQuestion)
        if _artifact_matches(item, selected_request)
    ]
    (
        bundle.literary_arcs,
        bundle.continuity_candidates,
        bundle.craft_controls,
        bundle.character_voice_profiles,
        bundle.theme_questions,
    ) = _purpose_artifacts(
        selected_purpose,
        selected_request,
        arcs=arcs,
        continuity=continuity,
        controls=controls,
        voices=voices,
        themes=themes,
    )
    mapping = reference.get("mapping_summary", {})
    mapping_summary = {
        str(key): int(value)
        for key, value in mapping.items()
        if isinstance(value, int)
    } if isinstance(mapping, dict) else {}
    if mapping_summary.get("unmapped", 0):
        bundle.warnings.append("Distill 存在 UNMAPPED evidence；不得作为 Runtime hard evidence")
    if mapping_summary.get("conflicting", 0):
        bundle.warnings.append("Distill 存在 CONFLICTING evidence；必须进入 review")
    bundle.distillation_soft_context = DistillationSoftContext(
        scope=str(reference.get("scope") or ""),
        distill_id=str(reference.get("distill_id") or ""),
        observations=list(bundle.observations),
        literary_arcs=list(bundle.literary_arcs),
        continuity_candidates=list(bundle.continuity_candidates),
        craft_controls=list(bundle.craft_controls),
        character_voice_profiles=list(bundle.character_voice_profiles),
        theme_questions=list(bundle.theme_questions),
        mapping_summary=mapping_summary,
    )
    if str(reference.get("scope")) != "SELF_BOOK":
        bundle.warnings.append(
            "当前 Distill scope 不是 SELF_BOOK；只允许消费抽象 craft/synthesis，不作为来源事实"
        )
        bundle.observations = [
            item
            for item in bundle.observations
            if item.information_class
            in {
                DistilledInformationClass.INTERPRETATION,
                DistilledInformationClass.CRAFT_CONTROL,
            }
            or item.kind.strip().casefold()
            in {"synthesis", "transferable_principle", "craft_control"}
        ]
        # Literary arcs, continuity candidates, character voice profiles and
        # theme questions retain source-book identity.  They are not safe
        # cross-book payloads; external/comparative consumption is limited to
        # explicitly transferable observations and craft controls.
        bundle.literary_arcs = []
        bundle.continuity_candidates = []
        bundle.character_voice_profiles = []
        bundle.theme_questions = []
        if bundle.distillation_soft_context is not None:
            bundle.distillation_soft_context.observations = list(bundle.observations)
            bundle.distillation_soft_context.literary_arcs = []
            bundle.distillation_soft_context.continuity_candidates = []
            bundle.distillation_soft_context.character_voice_profiles = []
            bundle.distillation_soft_context.theme_questions = []
    return bundle


__all__ = [
    "ContextPurpose",
    "DistillationSoftContext",
    "RuntimeContextBundle",
    "RuntimeContextRequest",
    "route_runtime_context",
]
