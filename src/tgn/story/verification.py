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
    validate_path_components,
)
from .models import (
    NarrationRequest,
    StoryError,
    StoryManifest,
    TurnNarrationArtifact,
)


_TURN_FILE_RE = re.compile(r"turn-([0-9]{6,})\.json\Z")
_STORY_CHILDREN = {"story.json", "requests", "turns"}


def _file_identity(file_stat: os.stat_result) -> tuple[object, ...]:
    device = getattr(file_stat, "st_dev", None)
    inode = getattr(file_stat, "st_ino", None)
    if device is not None and inode is not None and not (device == 0 and inode == 0):
        return ("posix", int(device), int(inode))
    return (
        "fallback",
        int(getattr(file_stat, "st_file_attributes", 0)),
        int(getattr(file_stat, "st_ctime_ns", 0)),
        int(file_stat.st_mode),
    )


@dataclass(frozen=True)
class StoryFileObservable:
    relative_path: str
    sha256: str
    size: int
    mtime_ns: int
    identity: tuple[object, ...] = ()


@dataclass(frozen=True)
class StoryDirectoryObservable:
    """Disposable identity/metadata captured for one Story directory."""

    relative_path: str
    mode: int
    device: int | None
    inode: int | None
    file_attributes: int
    ctime_ns: int
    mtime_ns: int

    @property
    def identity(self) -> tuple[object, ...]:
        if self.device is not None and self.inode is not None and not (self.device == 0 and self.inode == 0):
            return (self.mode, self.device, self.inode)
        return (self.mode, self.file_attributes, self.ctime_ns)


@dataclass(frozen=True)
class StoryView:
    root: Path
    manifest: StoryManifest
    requests: tuple[tuple[int, NarrationRequest, bytes], ...]
    turns: tuple[tuple[int, TurnNarrationArtifact, bytes], ...]
    files: tuple[StoryFileObservable, ...]
    directories: tuple[StoryDirectoryObservable, ...]

    @property
    def request_map(self) -> dict[int, NarrationRequest]:
        return {number: value for number, value, _ in self.requests}

    @property
    def turn_map(self) -> dict[int, TurnNarrationArtifact]:
        return {number: value for number, value, _ in self.turns}

    @property
    def root_directory(self) -> StoryDirectoryObservable:
        return self.directories[0]

    @property
    def requests_directory(self) -> StoryDirectoryObservable:
        return self.directories[1]

    @property
    def turns_directory(self) -> StoryDirectoryObservable:
        return self.directories[2]


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


def capture_story_directory(path: str | Path, *, relative_path: str) -> StoryDirectoryObservable:
    """Capture one actual Story directory without following a path component."""

    directory = lexical_absolute(path)
    validate_path_components(directory, allow_missing_final=False)
    directory_stat = os.lstat(directory)
    if not is_actual_directory(directory_stat):
        raise OSError("Story path is not an actual directory")
    return StoryDirectoryObservable(
        relative_path=relative_path,
        mode=directory_stat.st_mode,
        device=getattr(directory_stat, "st_dev", None),
        inode=getattr(directory_stat, "st_ino", None),
        file_attributes=int(getattr(directory_stat, "st_file_attributes", 0)),
        ctime_ns=int(getattr(directory_stat, "st_ctime_ns", 0)),
        mtime_ns=int(directory_stat.st_mtime_ns),
    )


def story_directory_identity_matches(path: str | Path, expected: StoryDirectoryObservable) -> bool:
    try:
        actual = capture_story_directory(path, relative_path=expected.relative_path)
    except Exception:
        return False
    return actual.identity == expected.identity


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
    try:
        validate_path_components(root, allow_missing_final=False)
    except FileNotFoundError as exc:
        raise StoryError("STORY_NOT_FOUND", "Story root does not exist") from exc
    except OSError as exc:
        raise StoryError("INVALID_STORY_INPUT", "Story path contains a symlink or reparse point") from exc
    _actual_story_root(root)
    try:
        directories = (
            capture_story_directory(root, relative_path="."),
            capture_story_directory(root / "requests", relative_path="requests"),
            capture_story_directory(root / "turns", relative_path="turns"),
        )
    except FileNotFoundError as exc:
        raise _story_integrity("Story artifact directory is missing") from exc
    except OSError as exc:
        raise _story_integrity("Story artifact directory is invalid") from exc
    try:
        children = {entry.name for entry in list_actual_children(root)}
    except OSError as exc:
        raise StoryError("STORY_INTEGRITY_MISMATCH", "Story root cannot be inspected") from exc
    if "novel.md" in children:
        raise StoryError("UNSUPPORTED_STORY_FORMAT", "novel.md belongs to a later Story format")
    if children != _STORY_CHILDREN:
        raise _story_integrity("Story root exact tree is invalid")
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
        StoryFileObservable(
            "story.json",
            sha256_bytes(manifest_payload),
            len(manifest_payload),
            manifest_stat.st_mtime_ns,
            _file_identity(manifest_stat),
        )
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
                    _file_identity(file_stat),
                )
            )
    request_values.sort(key=lambda item: item[0])
    turn_values.sort(key=lambda item: item[0])
    file_values.sort(key=lambda item: item.relative_path)
    try:
        final_directories = (
            capture_story_directory(root, relative_path="."),
            capture_story_directory(root / "requests", relative_path="requests"),
            capture_story_directory(root / "turns", relative_path="turns"),
        )
    except Exception as exc:
        raise _story_integrity("Story directories changed while reading") from exc
    if final_directories != directories:
        raise _story_integrity("Story directories changed while reading")
    return StoryView(
        root=root,
        manifest=manifest,
        requests=tuple(request_values),
        turns=tuple(turn_values),
        files=tuple(file_values),
        directories=directories,
    )


def story_files_unchanged(root: str | Path, before: tuple[StoryFileObservable, ...]) -> bool:
    try:
        after = load_story_view(root).files
    except Exception:
        return False
    return after == before


__all__ = [
    "StoryDirectoryObservable",
    "StoryFileObservable",
    "StoryView",
    "capture_story_directory",
    "load_story_view",
    "story_directory_identity_matches",
    "story_files_unchanged",
]
