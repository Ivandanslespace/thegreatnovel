"""Lazy, source-gated recall and hydration for the Runtime Baseline.

Distill can point to a likely missing asset, but this module deliberately has
two separate operations: discovery returns recall-only leads, while hydration
accepts a normal ``RuntimeBaselineInput`` reviewed against selected Edition
source spans.  There is no Distill-to-Runtime promotion path.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from novel_authoring.db.database import Database
from novel_authoring.distill.models import (
    DistilledInformationClass,
    DistilledObservation,
    DistillScope,
    RuntimeRecallCandidate,
)
from novel_authoring.distill.service import latest_distill_reference
from novel_authoring.edition import resolve_edition_id
from novel_authoring.runtime_baseline.models import (
    BaselineCategory,
    RuntimeBaselineInput,
)
from novel_authoring.runtime_baseline.service import (
    build_runtime_baseline,
    latest_runtime_baseline,
)
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.operations import book_root
from novel_authoring.utils import json_dumps


class RuntimeHydrationError(RuntimeError):
    """Raised when an explicit source review cannot hydrate a baseline."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    values: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                values.append(value)
    return values


def _category_for_observation(observation: DistilledObservation) -> BaselineCategory:
    declared = (observation.subject_type or "").strip().casefold()
    aliases = {item.value: item for item in BaselineCategory}
    if declared in aliases:
        return aliases[declared]
    by_dimension = {
        "worldbuilding": BaselineCategory.RULE,
        "characters": BaselineCategory.CHARACTER,
        "plot": BaselineCategory.PROMISE,
        "continuity": BaselineCategory.PROMISE,
    }
    return by_dimension.get(observation.dimension, BaselineCategory.KNOWLEDGE)


def discover_runtime_recall_candidates(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    reference: dict[str, Any] | None = None,
    limit: int = 24,
) -> list[RuntimeRecallCandidate]:
    """Return a bounded list of leads that need source verification.

    The check is intentionally shallow: it compares names/statements against
    the current baseline and never writes a version or changes Canon.
    """

    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    edition = BookLayout(book_root(database, book_id).parent).for_book(book_id).edition(
        selected
    )
    selected_reference = reference or latest_distill_reference(
        edition, scope=DistillScope.SELF_BOOK
    )
    if selected_reference is None or str(
        selected_reference.get("scope")
    ) != DistillScope.SELF_BOOK.value:
        return []
    package_root = Path(str(selected_reference.get("package_root", ""))).expanduser().resolve()
    observations: list[DistilledObservation] = []
    for payload in _read_jsonl(package_root / "observations.jsonl"):
        observation = DistilledObservation.model_validate(payload)
        if observation.information_class is DistilledInformationClass.CRAFT_CONTROL:
            continue
        if any(item.mapping_status.value in {"EXACT", "PARTIAL"} for item in observation.evidence):
            observations.append(observation)
    baseline = latest_runtime_baseline(database, book_id, edition_id=selected)
    known_statements: set[str] = set()
    if baseline is not None:
        known_statements = {entry.statement.casefold() for entry in baseline.entries}
    result: list[RuntimeRecallCandidate] = []
    for observation in observations:
        if observation.statement.casefold() in known_statements:
            continue
        category = _category_for_observation(observation)
        result.append(
            RuntimeRecallCandidate(
                candidate_id=f"recall:{observation.observation_id}",
                category=category.value,
                name=f"distill:{observation.observation_id}",
                statement=observation.statement,
                dimension=observation.dimension,
                observation_id=observation.observation_id,
                source_scope=DistillScope.SELF_BOOK,
                evidence=list(observation.evidence),
                subject_ids=list(observation.subject_ids),
                rationale=(
                    "Distill 提供了 selected Edition 的线索；需要 Source/作者复核后"
                    "才能进入 Baseline"
                ),
            )
        )
        if len(result) >= limit:
            break
    return result


def hydrate_runtime_baseline(
    database: Database,
    book_id: str,
    input_path: Path,
    *,
    edition_id: str | None = None,
    boundary_chapter: int | None = None,
) -> dict[str, object]:
    """Publish a new Baseline only from an explicit source-review input file."""

    selected = resolve_edition_id(database, book_id, edition_id)
    try:
        payload = RuntimeBaselineInput.model_validate_json(
            Path(input_path).expanduser().resolve().read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise RuntimeHydrationError(f"hydration input 不符合 RuntimeBaselineInput：{exc}") from exc
    if payload.book_id != book_id or payload.edition_id != selected:
        raise RuntimeHydrationError(
            "hydration input 的 book_id/edition_id 与 selected Edition 不一致"
        )
    if any(entry.source_kind == "DISTILL_RECALL" for entry in payload.entries):
        raise RuntimeHydrationError("Distill recall 只能引导 source review，不能直接 hydration")
    existing = latest_runtime_baseline(database, book_id, edition_id=selected)
    merged_entries = {
        entry.entry_id: entry for entry in ([] if existing is None else existing.entries)
    }
    merged_entries.update({entry.entry_id: entry for entry in payload.entries})
    effective_boundary = boundary_chapter
    if effective_boundary is None:
        effective_boundary = max(
            payload.boundary_chapter,
            0 if existing is None else existing.manifest.boundary_chapter,
        )
    merged = payload.model_copy(
        update={
            "boundary_chapter": effective_boundary,
            "entries": list(merged_entries.values()),
        }
    )
    with tempfile.TemporaryDirectory(prefix="runtime-hydration-") as temporary:
        merged_path = Path(temporary) / "merged-input.json"
        merged_path.write_text(
            json_dumps(merged.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        return build_runtime_baseline(
            database,
            book_id,
            input_path=merged_path,
            edition_id=selected,
            boundary_chapter=effective_boundary,
        )


__all__ = [
    "RuntimeHydrationError",
    "discover_runtime_recall_candidates",
    "hydrate_runtime_baseline",
]
