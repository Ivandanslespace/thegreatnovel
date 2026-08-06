"""Route hard runtime state and soft Distill knowledge by explicit purpose."""

from __future__ import annotations

import json
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
    ThemeQuestion,
)
from novel_authoring.distill.service import latest_distill_reference
from novel_authoring.edition import resolve_edition_id
from novel_authoring.runtime_baseline import EarnedSurface, load_earned_surface
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


class RuntimeContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: RuntimeContextRequest
    book_id: str
    edition_id: str
    hard_boundary: dict[str, object]
    earned_surface: EarnedSurface | None = None
    observations: list[DistilledObservation] = Field(default_factory=list)
    literary_arcs: list[LiteraryArc] = Field(default_factory=list)
    continuity_candidates: list[ContinuityCandidate] = Field(default_factory=list)
    craft_controls: list[CraftControl] = Field(default_factory=list)
    character_voice_profiles: list[CharacterVoiceProfile] = Field(default_factory=list)
    theme_questions: list[ThemeQuestion] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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
    bundle = RuntimeContextBundle(
        request=selected_request,
        book_id=book_id,
        edition_id=selected_edition,
        hard_boundary=hard_boundary,
        earned_surface=earned,
    )
    root = book_root(database, book_id)
    edition = BookLayout(root.parent).for_book(book_id).edition(selected_edition)
    reference = latest_distill_reference(edition)
    if reference is None:
        bundle.warnings.append(
            "当前 Edition 没有 Distill Package；仅提供 hard boundary/earned surface"
        )
        return bundle
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
    bundle.literary_arcs = [
        item
        for item in _read_json_array(package_root / "literary_arcs.json", LiteraryArc)
        if not selected_request.chapter_range
        or not item.start_chapter
        or not item.end_chapter
    ]
    bundle.continuity_candidates = [
        item
        for item in _read_jsonl(
            package_root / "continuity_candidates.jsonl", ContinuityCandidate
        )
        if item.verification_status.value != "RESOLVED"
    ]
    bundle.craft_controls = _read_json_array(package_root / "craft_controls.json", CraftControl)
    bundle.character_voice_profiles = _read_json_array(
        package_root / "character_voice_profiles.json", CharacterVoiceProfile
    )
    bundle.theme_questions = _read_json_array(
        package_root / "theme_questions.json", ThemeQuestion
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
    return bundle


__all__ = [
    "ContextPurpose",
    "RuntimeContextBundle",
    "RuntimeContextRequest",
    "route_runtime_context",
]
