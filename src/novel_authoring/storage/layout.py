"""Canonical, symlink-free book library layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from novel_authoring.storage.models import BookPaths, EditionPaths, LayoutError
from novel_authoring.utils import safe_book_id

LAYOUT_VERSION = "library-v1"


def default_library_root(anchor: Path | None = None) -> Path:
    """Return the repository-local default library root.

    Commands are expected to run from the repository root.  Tests and callers
    can pass an explicit anchor, which keeps the default deterministic without
    hard-coding a user-specific Windows path.
    """

    return (anchor or Path.cwd()).resolve() / "library"


@dataclass(frozen=True, slots=True)
class BookLayout:
    """Resolve every canonical book path from one library root."""

    library_root: Path
    layout_version: str = LAYOUT_VERSION

    def __post_init__(self) -> None:
        root = Path(self.library_root).expanduser().resolve()
        if root.name in {".", ".."}:
            raise LayoutError("library_root 无效")
        object.__setattr__(self, "library_root", root)

    @classmethod
    def default(cls, anchor: Path | None = None) -> BookLayout:
        return cls(default_library_root(anchor))

    def for_book(self, book_id: str) -> BookPaths:
        normalized = safe_book_id(book_id)
        return BookPaths(self.library_root / normalized, normalized)

    # Friendly aliases used by services and external integrations.
    paths = for_book
    book_paths = for_book

    def for_edition(self, book_id: str, edition_id: str) -> EditionPaths:
        return self.for_book(book_id).edition(edition_id)

    def ensure_book(self, book_id: str) -> BookPaths:
        paths = self.for_book(book_id)
        for directory in paths.all_directories():
            directory.mkdir(parents=True, exist_ok=True)
        return paths

    def list_books(self) -> list[BookPaths]:
        if not self.library_root.is_dir():
            return []
        result: list[BookPaths] = []
        for child in sorted(self.library_root.iterdir(), key=lambda item: item.name.casefold()):
            if child.is_dir() and (child / "book.yaml").is_file():
                result.append(self.for_book(child.name))
        return result

    def contains(self, path: Path, *, allow_root: bool = True) -> bool:
        """Return whether ``path`` is contained by the library root."""

        candidate = Path(path).expanduser().resolve(strict=False)
        root = self.library_root.resolve(strict=False)
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            return False
        return allow_root or relative != Path(".")

    def require_contained(self, path: Path, *, label: str = "path") -> Path:
        resolved = Path(path).expanduser().resolve(strict=False)
        if not self.contains(resolved):
            raise LayoutError(f"{label} 必须位于 library_root 内: {resolved}")
        return resolved

    def relative_path(self, path: Path) -> str:
        resolved = self.require_contained(path)
        return resolved.relative_to(self.library_root).as_posix()


__all__ = ["BookLayout", "LAYOUT_VERSION", "default_library_root"]
