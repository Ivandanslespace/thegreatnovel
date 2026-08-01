"""Read-only Campaign observables used by the Story consistency boundary."""

from __future__ import annotations

import copy
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..campaign import verify_campaign
from ..campaign.models import CampaignError, CampaignManifest
from .common import (
    is_actual_directory,
    is_actual_regular_file,
    lexical_absolute,
    list_actual_children,
    parse_json_bytes,
    read_regular_file,
    require_actual_directory,
    sha256_bytes,
)


CAMPAIGN_RELATIVE_FILES: tuple[str, ...] = (
    "campaign.json",
    "projection/player_projection.json",
    "projection/projection_draft.json",
    "projection/projection_manifest.json",
    "projection/projection_report.json",
    "session/campaign.sqlite3",
    "session/recorded_decisions.json",
    "session/session.json",
    "world/bundle.json",
    "world/compile_report.json",
    "world/compiled_worldpack.json",
    "world/initial_state.json",
    "world/world_draft.json",
    "world/world_request.json",
)

_CAMPAIGN_CHILDREN = {"campaign.json", "world", "projection", "session"}
_NESTED_CHILDREN = {
    "world": {
        "bundle.json",
        "compile_report.json",
        "compiled_worldpack.json",
        "initial_state.json",
        "world_draft.json",
        "world_request.json",
    },
    "projection": {
        "player_projection.json",
        "projection_draft.json",
        "projection_manifest.json",
        "projection_report.json",
    },
    "session": {"campaign.sqlite3", "recorded_decisions.json", "session.json"},
}

_SQLITE_COLUMNS: dict[str, tuple[str, ...]] = {
    "campaigns": (
        "campaign_id",
        "engine_version",
        "state_schema_version",
        "seed",
        "initial_state_json",
        "initial_state_hash",
        "created_at",
    ),
    "events": (
        "event_id",
        "campaign_id",
        "event_seq",
        "decision_seq",
        "game_minute",
        "event_type",
        "actor_id",
        "action_id",
        "causation_id",
        "correlation_id",
        "payload_json",
        "state_hash_before",
        "state_hash_after",
        "created_at",
    ),
    "snapshots": (
        "id",
        "campaign_id",
        "event_seq",
        "state_json",
        "state_hash",
        "created_at",
    ),
}

_SQLITE_ORDER = {
    "campaigns": "campaign_id",
    "events": "campaign_id, event_seq",
    "snapshots": "campaign_id, event_seq, id",
}


@dataclass(frozen=True)
class FileObservable:
    relative_path: str
    sha256: str
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class CampaignSnapshot:
    """An in-memory, disposable read-only Campaign capture."""

    campaign_files: tuple[FileObservable, ...]
    sqlite_authoritative_rows: tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...]
    session_json_canonical_bytes: bytes
    session_json_hash: str
    recorded_decisions_json_canonical_bytes: bytes
    recorded_decisions_json_hash: str
    campaign_manifest_hash: str
    # Captured bytes are an implementation detail used to reconstruct one
    # internally consistent view. They never leave memory or enter Story.
    _file_bytes: tuple[tuple[str, bytes], ...]

    def file_bytes(self, relative_path: str) -> bytes:
        for name, payload in self._file_bytes:
            if name == relative_path:
                return payload
        raise KeyError(relative_path)

    @property
    def campaign_row(self) -> tuple[Any, ...]:
        return dict(self.sqlite_authoritative_rows)["campaigns"][0]

    @property
    def event_rows(self) -> tuple[tuple[Any, ...], ...]:
        return dict(self.sqlite_authoritative_rows)["events"]

    @property
    def snapshot_rows(self) -> tuple[tuple[Any, ...], ...]:
        return dict(self.sqlite_authoritative_rows)["snapshots"]

    def comparable(self) -> tuple[Any, ...]:
        return (
            self.campaign_files,
            self.sqlite_authoritative_rows,
            self.session_json_canonical_bytes,
            self.session_json_hash,
            self.recorded_decisions_json_canonical_bytes,
            self.recorded_decisions_json_hash,
            self.campaign_manifest_hash,
        )


def _assert_exact_campaign_tree(root: Path) -> None:
    try:
        root_stat = os.lstat(root)
    except FileNotFoundError as exc:
        raise OSError("Campaign root does not exist") from exc
    if not is_actual_directory(root_stat):
        raise OSError("Campaign root is not an actual directory")
    if {entry.name for entry in list_actual_children(root)} != _CAMPAIGN_CHILDREN:
        raise OSError("Campaign exact tree is invalid")
    campaign_file = root / "campaign.json"
    file_stat = os.lstat(campaign_file)
    if not is_actual_regular_file(file_stat):
        raise OSError("campaign.json is not a regular file")
    for directory_name, expected in _NESTED_CHILDREN.items():
        directory = root / directory_name
        directory_stat = os.lstat(directory)
        if not is_actual_directory(directory_stat):
            raise OSError("Campaign nested directory is invalid")
        if {entry.name for entry in list_actual_children(directory)} != expected:
            raise OSError("Campaign nested exact tree is invalid")
        for name in expected:
            child_stat = os.lstat(directory / name)
            if not is_actual_regular_file(child_stat):
                raise OSError("Campaign nested artifact is not a regular file")


def _read_sqlite_rows(root: Path) -> tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...]:
    database = root / "session" / "campaign.sqlite3"
    database_stat = os.lstat(database)
    if not is_actual_regular_file(database_stat):
        raise OSError("Campaign SQLite artifact is not a regular file")
    payload_uri = lexical_absolute(database).as_uri() + "?mode=ro"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(payload_uri, uri=True)
        tables: list[tuple[str, tuple[tuple[Any, ...], ...]]] = []
        for table, columns in _SQLITE_COLUMNS.items():
            query = f"SELECT {', '.join(columns)} FROM {table} ORDER BY {_SQLITE_ORDER[table]}"
            rows = connection.execute(query).fetchall()
            tables.append((table, tuple(tuple(row) for row in rows)))
        final_stat = os.lstat(database)
        if not is_actual_regular_file(final_stat):
            raise OSError("Campaign SQLite artifact changed during capture")
        initial_identity = (database_stat.st_dev, database_stat.st_ino)
        final_identity = (final_stat.st_dev, final_stat.st_ino)
        if initial_identity != final_identity:
            raise OSError("Campaign SQLite artifact changed during capture")
        return tuple(tables)
    except sqlite3.Error as exc:
        raise OSError("Campaign SQLite read-only capture failed") from exc
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                raise OSError("Campaign SQLite close failed") from exc


def capture_campaign_snapshot(campaign_dir: str | Path) -> CampaignSnapshot:
    """Capture the exact frozen Campaign observables without opening EventStore."""

    root = require_actual_directory(campaign_dir, allow_missing=False)
    _assert_exact_campaign_tree(root)
    values: list[FileObservable] = []
    payloads: list[tuple[str, bytes]] = []
    for relative_path in CAMPAIGN_RELATIVE_FILES:
        payload, file_stat = read_regular_file(root / relative_path)
        values.append(
            FileObservable(
                relative_path=relative_path,
                sha256=sha256_bytes(payload),
                size=len(payload),
                mtime_ns=file_stat.st_mtime_ns,
            )
        )
        payloads.append((relative_path, payload))

    campaign_payload = dict(payloads)["campaign.json"]
    session_payload = dict(payloads)["session/session.json"]
    decisions_payload = dict(payloads)["session/recorded_decisions.json"]
    parse_json_bytes(campaign_payload, require_canonical=True)
    parse_json_bytes(session_payload, require_canonical=True)
    parse_json_bytes(decisions_payload, require_canonical=True)
    rows = _read_sqlite_rows(root)
    campaign_manifest_hash = sha256_bytes(campaign_payload)
    return CampaignSnapshot(
        campaign_files=tuple(values),
        sqlite_authoritative_rows=rows,
        session_json_canonical_bytes=session_payload,
        session_json_hash=sha256_bytes(session_payload),
        recorded_decisions_json_canonical_bytes=decisions_payload,
        recorded_decisions_json_hash=sha256_bytes(decisions_payload),
        campaign_manifest_hash=campaign_manifest_hash,
        _file_bytes=tuple((name, bytes(payload)) for name, payload in payloads),
    )


def manifest_from_snapshot(snapshot: CampaignSnapshot) -> CampaignManifest:
    value = parse_json_bytes(snapshot.file_bytes("campaign.json"), require_canonical=True)
    return CampaignManifest.from_dict(value)


def parse_snapshot_json(snapshot: CampaignSnapshot, relative_path: str) -> Any:
    return parse_json_bytes(snapshot.file_bytes(relative_path), require_canonical=True)


def verify_and_capture_campaign(campaign_dir: str | Path) -> tuple[CampaignManifest, CampaignSnapshot]:
    """Run the frozen public verifier, then capture its exact observables."""

    try:
        verify_campaign(campaign_dir)
        snapshot = capture_campaign_snapshot(campaign_dir)
        manifest = manifest_from_snapshot(snapshot)
        return manifest, snapshot
    except CampaignError:
        raise
    except Exception as exc:
        raise OSError("Campaign candidate cannot be captured") from exc


def compare_request_prefix(
    before: CampaignSnapshot,
    after: CampaignSnapshot,
    *,
    event_seq: int,
    recorded_decision_index: int,
) -> bool:
    """Compare only the historical prefix needed by a pending Story turn."""

    before_files = {item.relative_path: item for item in before.campaign_files}
    after_files = {item.relative_path: item for item in after.campaign_files}
    immutable_files = {
        "campaign.json",
        "world/bundle.json",
        "world/compile_report.json",
        "world/compiled_worldpack.json",
        "world/initial_state.json",
        "world/world_draft.json",
        "world/world_request.json",
        "projection/player_projection.json",
        "projection/projection_draft.json",
        "projection/projection_manifest.json",
        "projection/projection_report.json",
    }
    if any(before_files[name] != after_files[name] for name in immutable_files):
        return False
    before_tables = dict(before.sqlite_authoritative_rows)
    after_tables = dict(after.sqlite_authoritative_rows)
    if before_tables["campaigns"] != after_tables["campaigns"]:
        return False
    for table, key_index in (("events", 2), ("snapshots", 2)):
        before_prefix = tuple(row for row in before_tables[table] if row[key_index] <= event_seq)
        after_prefix = tuple(row for row in after_tables[table] if row[key_index] <= event_seq)
        if before_prefix != after_prefix:
            return False

    try:
        from ..llm_player import import_recorded_decisions

        before_records = import_recorded_decisions(before.recorded_decisions_json_canonical_bytes.decode("utf-8"))
        after_records = import_recorded_decisions(after.recorded_decisions_json_canonical_bytes.decode("utf-8"))
    except Exception:
        return False
    if before_records[:recorded_decision_index] != after_records[:recorded_decision_index]:
        return False
    return True


__all__ = [
    "CAMPAIGN_RELATIVE_FILES",
    "CampaignSnapshot",
    "FileObservable",
    "capture_campaign_snapshot",
    "compare_request_prefix",
    "manifest_from_snapshot",
    "parse_snapshot_json",
    "verify_and_capture_campaign",
]
