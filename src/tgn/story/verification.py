"""Read-only Story tree loading and artifact observables."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import (
    is_actual_directory,
    is_actual_regular_file,
    lexical_absolute,
    list_actual_children,
    read_canonical_json_file,
    read_regular_file,
    sha256_bytes,
)
from .models import (
    NarrationRequest,
    StoryError,
    StoryManifest,
    TurnNarrationArtifact,
)


_TURN_FILE_RE = re.compile(r"turn-([0-9]{6,})\.json\Z")
_STORY_CHILDREN = {"story.json", "requests", "turns"}


@dataclass(frozen=True)
class StoryFileObservable:
    relative_path: str
    sha256: str
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class StoryView:
    root: Path
    manifest: StoryManifest
    requests: tuple[tuple[int, NarrationRequest, bytes], ...]
    turns: tuple[tuple[int, TurnNarrationArtifact, bytes], ...]
    files: tuple[StoryFileObservable, ...]

    @property
    def request_map(self) -> dict[int, NarrationRequest]:
        return {number: value for number, value, _ in self.requests}

    @property
    def turn_map(self) -> dict[int, TurnNarrationArtifact]:
        return {number: value for number, value, _ in self.turns}


def _story_integrity(message: str) -> StoryError:
    return StoryError("STORY_INTEGRITY_MISMATCH", message)


def _actual_story_root(root: Path) -> None:
    try:
        root_stat = os.lstat(root)
    except FileNotFoundError as exc:
        raise StoryError("STORY_NOT_FOUND", "Story root does not exist") from exc
    except OSError as exc:
        raise StoryError("INVALID_STORY_INPUT", "Story directory cannot be inspected") from exc
    if not is_actual_directory(root_stat):
        raise StoryError("INVALID_STORY_INPUT", "Story root is not an actual directory")


def _read_turn_file(directory: Path, entry_name: str) -> tuple[int, bytes, Any]:
    match = _TURN_FILE_RE.fullmatch(entry_name)
    if match is None:
        raise _story_integrity("Story turn directory contains an invalid filename")
    number = int(match.group(1))
    if number <= 0 or entry_name != f"turn-{number:06d}.json":
        raise _story_integrity("Story turn filename is not canonical")
    path = directory / entry_name
    try:
        payload, file_stat = read_regular_file(path)
        return number, payload, file_stat
    except StoryError:
        raise
    except Exception as exc:
        raise _story_integrity("Story artifact cannot be read safely") from exc


def load_story_view(story_dir: str | Path) -> StoryView:
    """Read the exact Phase 9C1 tree without creating or repairing anything."""

    root = lexical_absolute(story_dir)
    _actual_story_root(root)
    try:
        children = {entry.name for entry in list_actual_children(root)}
    except OSError as exc:
        raise StoryError("STORY_INTEGRITY_MISMATCH", "Story root cannot be inspected") from exc
    if "novel.md" in children:
        raise StoryError("UNSUPPORTED_STORY_FORMAT", "novel.md belongs to a later Story format")
    if children != _STORY_CHILDREN:
        raise _story_integrity("Story root exact tree is invalid")
    for directory_name in ("requests", "turns"):
        try:
            directory_stat = os.lstat(root / directory_name)
        except OSError as exc:
            raise _story_integrity("Story artifact directory is missing") from exc
        if not is_actual_directory(directory_stat):
            raise _story_integrity("Story artifact directory is invalid")
    try:
        manifest_value, manifest_payload, manifest_stat = read_canonical_json_file(root / "story.json")
        manifest = StoryManifest.from_dict(manifest_value)
    except StoryError:
        raise
    except Exception as exc:
        raise _story_integrity("story.json is invalid") from exc

    request_values: list[tuple[int, NarrationRequest, bytes]] = []
    turn_values: list[tuple[int, TurnNarrationArtifact, bytes]] = []
    file_values: list[StoryFileObservable] = [
        StoryFileObservable("story.json", sha256_bytes(manifest_payload), len(manifest_payload), manifest_stat.st_mtime_ns)
    ]
    seen_request: set[int] = set()
    seen_turn: set[int] = set()
    for directory_name, target, seen, rel_prefix in (
        ("requests", request_values, seen_request, "requests"),
        ("turns", turn_values, seen_turn, "turns"),
    ):
        directory = root / directory_name
        try:
            entries = sorted(list_actual_children(directory), key=lambda item: item.name)
        except OSError as exc:
            raise _story_integrity("Story artifact directory cannot be inspected") from exc
        for entry in entries:
            try:
                number, payload, file_stat = _read_turn_file(directory, entry.name)
                from .common import parse_json_bytes

                parsed = parse_json_bytes(payload, require_canonical=True)
            except StoryError:
                raise
            except Exception as exc:
                raise _story_integrity("Story JSON artifact is invalid") from exc
            if number in seen:
                raise _story_integrity("Story contains a duplicate turn identity")
            seen.add(number)
            try:
                value = NarrationRequest.from_dict(parsed) if directory_name == "requests" else TurnNarrationArtifact.from_dict(parsed)
            except Exception as exc:
                raise _story_integrity("Story artifact schema is invalid") from exc
            if value.turn_id != f"turn-{number:06d}":
                raise _story_integrity("Story filename and turn identity differ")
            target.append((number, value, payload))
            file_values.append(
                StoryFileObservable(
                    f"{rel_prefix}/{entry.name}",
                    sha256_bytes(payload),
                    len(payload),
                    file_stat.st_mtime_ns,
                )
            )
    request_values.sort(key=lambda item: item[0])
    turn_values.sort(key=lambda item: item[0])
    file_values.sort(key=lambda item: item.relative_path)
    return StoryView(
        root=root,
        manifest=manifest,
        requests=tuple(request_values),
        turns=tuple(turn_values),
        files=tuple(file_values),
    )


def story_files_unchanged(root: str | Path, before: tuple[StoryFileObservable, ...]) -> bool:
    try:
        after = load_story_view(root).files
    except Exception:
        return False
    return after == before


__all__ = [
    "StoryFileObservable",
    "StoryView",
    "load_story_view",
    "story_files_unchanged",
]
