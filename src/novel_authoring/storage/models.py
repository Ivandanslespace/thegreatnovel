"""Typed path objects for the canonical library layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class LayoutError(ValueError):
    """Raised when a book, edition, operation, or path is unsafe."""


@dataclass(frozen=True, slots=True)
class OperationPaths:
    """One auditable operation workspace under an edition."""

    root: Path
    operation_id: str

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def status(self) -> Path:
        return self.root / "status.json"

    @property
    def events(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def input(self) -> Path:
        return self.root / "input"

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    def all_directories(self) -> tuple[Path, ...]:
        return (self.root, self.input, self.output, self.artifacts, self.logs)


@dataclass(frozen=True, slots=True)
class EditionPaths:
    """All canonical paths belonging to one edition."""

    root: Path
    edition_id: str

    @property
    def analysis(self) -> Path:
        return self.root / "analysis"

    @property
    def writing(self) -> Path:
        return self.root / "writing"

    @property
    def operations(self) -> Path:
        return self.root / "operations"

    @property
    def batches(self) -> Path:
        return self.root / "batches"

    @property
    def canon(self) -> Path:
        return self.root / "canon"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def latest_export(self) -> Path:
        return self.exports / "latest"

    @property
    def archive_exports(self) -> Path:
        return self.exports / "archive"

    @property
    def story_atlas(self) -> Path:
        return self.analysis / "story_atlas"

    @property
    def atlas(self) -> Path:
        """Canonical public alias; implementation keeps the versioned Atlas name."""

        return self.story_atlas

    @property
    def metrics(self) -> Path:
        return self.analysis / "metrics"

    @property
    def rhythm(self) -> Path:
        return self.analysis / "rhythm"

    @property
    def initialization(self) -> Path:
        return self.analysis / "initialization"

    @property
    def drafts(self) -> Path:
        return self.writing / "drafts"

    @property
    def continuation(self) -> Path:
        return self.writing / "continuation"

    @property
    def revisions(self) -> Path:
        return self.writing / "revisions"

    @property
    def validation(self) -> Path:
        return self.writing / "validation"

    @property
    def boundaries(self) -> Path:
        return self.writing / "boundaries"

    @property
    def candidates(self) -> Path:
        return self.writing / "candidates"

    @property
    def contracts(self) -> Path:
        return self.writing / "contracts"

    def operation(self, operation_id: str) -> OperationPaths:
        _validate_component(operation_id, "operation_id")
        return OperationPaths(self.operations / operation_id, operation_id)

    def all_directories(self) -> tuple[Path, ...]:
        return (
            self.root,
            self.analysis,
            self.initialization,
            self.story_atlas,
            self.metrics,
            self.rhythm,
            self.writing,
            self.drafts,
            self.continuation,
            self.revisions,
            self.validation,
            self.boundaries,
            self.candidates,
            self.contracts,
            self.operations,
            self.batches,
            self.canon,
            self.exports,
            self.archive_exports,
        )


@dataclass(frozen=True, slots=True)
class BookPaths:
    """The single canonical path map for a book.

    No service should construct a ``workspace/<book_id>`` or ``editions`` path
    itself.  It should receive this object from :class:`BookLayout`.
    """

    root: Path
    book_id: str

    @property
    def book_yaml(self) -> Path:
        return self.root / "book.yaml"

    @property
    def readme(self) -> Path:
        return self.root / "README.md"

    @property
    def source(self) -> Path:
        return self.root / "source"

    @property
    def system(self) -> Path:
        return self.root / "_system"

    @property
    def database(self) -> Path:
        return self.system / "state.sqlite3"

    @property
    def database_shm(self) -> Path:
        return self.system / "state.sqlite3-shm"

    @property
    def database_wal(self) -> Path:
        return self.system / "state.sqlite3-wal"

    @property
    def source_manifest(self) -> Path:
        return self.system / "source_manifest.json"

    @property
    def snapshots(self) -> Path:
        return self.system / "snapshots"

    @property
    def logs(self) -> Path:
        return self.system / "logs"

    @property
    def cache(self) -> Path:
        return self.system / "cache"

    @property
    def temp(self) -> Path:
        return self.system / "temp"

    @property
    def legacy_locations(self) -> Path:
        return self.system / "legacy_locations.json"

    @property
    def editions(self) -> Path:
        return self.root / "editions"

    def edition(self, edition_id: str) -> EditionPaths:
        _validate_component(edition_id, "edition_id")
        return EditionPaths(self.editions / edition_id, edition_id)

    def all_directories(self) -> tuple[Path, ...]:
        return (
            self.root,
            self.source,
            self.system,
            self.snapshots,
            self.logs,
            self.cache,
            self.temp,
            self.editions,
        )


def _validate_component(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized or normalized in {".", ".."}:
        raise LayoutError(f"{label} 不能为空或路径保留字")
    if any(char in normalized for char in ("/", "\\", ":")):
        raise LayoutError(f"{label} 不能包含路径分隔符: {value!r}")
    if any(ord(char) < 32 for char in normalized):
        raise LayoutError(f"{label} 不能包含控制字符")
    return normalized


__all__ = [
    "BookPaths",
    "EditionPaths",
    "LayoutError",
    "OperationPaths",
]
