"""Read-only verification and detached request reconstruction for Campaigns."""

from __future__ import annotations

import copy
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.hashing import canonical_json
from ..core.models import GameState
from ..gameplay.expedition import build_observation
from ..llm_player import (
    LLMActionChoice,
    LLMDecisionRequest,
    build_llm_decision_request,
)
from ..projection import (
    PROJECTION_FILES,
    PlayerProjectionMap,
    build_player_presentation,
    presentation_hash,
    projection_hash,
    verify_projection_bundle,
)
from ..session import SessionError, next_session, verify_session
from ..worldgen import BUNDLE_FILES, verify_bundle
from ..worldgen.models import WorldGenError
from .common import read_canonical_json, sha256_bytes, sha256_json
from .models import CampaignError, CampaignManifest


CAMPAIGN_FILE = "campaign.json"
SESSION_FILES = frozenset({"campaign.sqlite3", "session.json", "recorded_decisions.json"})
CAMPAIGN_RELATIVE_FILES = frozenset(
    {CAMPAIGN_FILE}
    | {f"world/{name}" for name in BUNDLE_FILES}
    | {f"projection/{name}" for name in PROJECTION_FILES}
    | {f"session/{name}" for name in SESSION_FILES}
)
_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
_EXPECTED_COLUMNS = {
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
_EXPECTED_COLUMN_TYPES = {
    "campaigns": ("TEXT", "TEXT", "INTEGER", "TEXT", "TEXT", "TEXT", "TEXT"),
    "events": (
        "TEXT",
        "TEXT",
        "INTEGER",
        "INTEGER",
        "INTEGER",
        "TEXT",
        "TEXT",
        "TEXT",
        "TEXT",
        "TEXT",
        "TEXT",
        "TEXT",
        "TEXT",
        "TEXT",
    ),
    "snapshots": ("INTEGER", "TEXT", "INTEGER", "TEXT", "TEXT", "TEXT"),
}
_EXPECTED_INDEX_COLUMNS = {
    "idx_events_campaign_seq": ("campaign_id", "event_seq"),
    "idx_snapshots_campaign_seq": ("campaign_id", "event_seq"),
}


@dataclass(frozen=True)
class FileObservable:
    digest: str
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class SQLiteObservable:
    rows: tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...]
    campaign_row: tuple[Any, ...]


@dataclass(frozen=True)
class SQLitePreflight:
    files: tuple[tuple[str, FileObservable], ...]
    sqlite: SQLiteObservable


@dataclass(frozen=True)
class VerifiedCampaign:
    manifest: CampaignManifest
    session_summary: dict[str, Any]
    verification: dict[str, Any]
    projection: PlayerProjectionMap
    current_request: LLMDecisionRequest | None
    current_presentation: Any | None


@dataclass(frozen=True)
class _DetachedLegalAction:
    action_type: str
    params: dict[str, Any]
    duration_minutes: int | None
    stamina_cost: int


def _integrity(message: str) -> CampaignError:
    return CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", message)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> None:
    raise ValueError("non-standard JSON number")


def _assert_exact_tree(root: Path, *, missing_is_not_found: bool = True) -> None:
    if not root.exists() or not root.is_dir():
        if missing_is_not_found:
            raise CampaignError("CAMPAIGN_NOT_FOUND", "published Campaign does not exist")
        raise _integrity("temporary Campaign directory does not exist")
    expected_children = {CAMPAIGN_FILE, "world", "projection", "session"}
    try:
        if {item.name for item in root.iterdir()} != expected_children:
            raise _integrity("Campaign tree is not exact")
        for directory in (root / "world", root / "projection", root / "session"):
            if not directory.is_dir():
                raise _integrity("Campaign tree has an invalid directory")
        if not (root / CAMPAIGN_FILE).is_file():
            raise _integrity("campaign.json is missing")
        expected_nested = {
            "world": set(BUNDLE_FILES),
            "projection": set(PROJECTION_FILES),
            "session": set(SESSION_FILES),
        }
        for directory_name, names in expected_nested.items():
            directory = root / directory_name
            if {item.name for item in directory.iterdir()} != names:
                raise _integrity("Campaign tree contains an unsupported or missing file")
            if any(not (directory / name).is_file() for name in names):
                raise _integrity("Campaign tree contains a non-file artifact")
    except CampaignError:
        raise
    except OSError as exc:
        raise _integrity("Campaign tree cannot be inspected") from exc


def snapshot_files(root: Path) -> tuple[tuple[str, FileObservable], ...]:
    values: list[tuple[str, FileObservable]] = []
    for relative in sorted(CAMPAIGN_RELATIVE_FILES):
        path = root / relative
        try:
            stat = path.stat()
            payload = path.read_bytes()
        except OSError as exc:
            raise _integrity("Campaign file snapshot failed") from exc
        values.append((relative, FileObservable(sha256_bytes(payload), len(payload), stat.st_mtime_ns)))
    return tuple(values)


def _sqlite_uri(path: Path) -> str:
    return path.resolve().as_uri() + "?mode=ro"


def _open_read_only(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(_sqlite_uri(path), uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as exc:
        raise _integrity("campaign SQLite cannot be opened read-only") from exc


def _row_tuple(row: sqlite3.Row, columns: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row[column] for column in columns)


def _authoritative_rows(connection: sqlite3.Connection) -> SQLiteObservable:
    table_rows: list[tuple[str, tuple[tuple[Any, ...], ...]]] = []
    order_by = {
        "campaigns": "campaign_id",
        "events": "campaign_id, event_seq",
        "snapshots": "campaign_id, event_seq, id",
    }
    for table, columns in _EXPECTED_COLUMNS.items():
        rows = connection.execute(
            f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order_by[table]}"
        ).fetchall()
        table_rows.append((table, tuple(_row_tuple(row, columns) for row in rows)))
    campaign_rows = dict(table_rows)["campaigns"]
    if len(campaign_rows) != 1:
        raise _integrity("Campaign SQLite must contain exactly one Campaign row")
    return SQLiteObservable(tuple(table_rows), campaign_rows[0])


def _check_schema(connection: sqlite3.Connection) -> None:
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise _integrity("SQLite integrity check failed")
        objects = {
            (row[0], row[1])
            for row in connection.execute(
                "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        }
        expected_objects = {
            ("table", table) for table in _EXPECTED_COLUMNS
        } | {("index", index) for index in _EXPECTED_INDEX_COLUMNS}
        if objects != expected_objects:
            raise _integrity("SQLite schema contains an unexpected user object")
        for table, expected_columns in _EXPECTED_COLUMNS.items():
            actual_definitions = tuple(
                (row[1], row[2].upper())
                for row in connection.execute(f"PRAGMA table_info({table})")
            )
            expected_definitions = tuple(
                zip(expected_columns, _EXPECTED_COLUMN_TYPES[table])
            )
            if actual_definitions != expected_definitions:
                raise _integrity("SQLite table columns do not match the frozen schema")
        named_indexes: dict[str, tuple[str, ...]] = {}
        for table in _EXPECTED_COLUMNS:
            for row in connection.execute(f"PRAGMA index_list({table})"):
                name = row[1]
                if name.startswith("sqlite_autoindex_"):
                    continue
                columns = tuple(
                    item[2]
                    for item in connection.execute(f"PRAGMA index_info({name})")
                )
                named_indexes[name] = columns
        if named_indexes != _EXPECTED_INDEX_COLUMNS:
            raise _integrity("SQLite named indexes do not match the frozen schema")
    except CampaignError:
        raise
    except sqlite3.Error as exc:
        raise _integrity("SQLite schema inspection failed") from exc


def _validate_campaign_row(row: tuple[Any, ...], manifest: CampaignManifest) -> None:
    campaign_id, engine_version, schema_version, seed, state_json, state_hash, created_at = row
    if campaign_id != manifest.campaign_id:
        raise _integrity("SQLite Campaign row does not match campaign_id")
    if engine_version != "1.0.0" or type(schema_version) is not int or schema_version != 1:
        raise _integrity("SQLite Campaign row has invalid metadata")
    if not isinstance(seed, str) or not isinstance(state_json, str) or not isinstance(created_at, str):
        raise _integrity("SQLite Campaign row has invalid values")
    if not isinstance(state_hash, str) or _HASH_RE.fullmatch(state_hash) is None:
        raise _integrity("SQLite initial state hash is invalid")
    try:
        parsed = read_canonical_json_payload(state_json)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise _integrity("SQLite initial state JSON is invalid") from exc
    if (
        sha256_json(parsed) != state_hash
        or state_hash != manifest.initial_session_state_hash
        or state_hash != manifest.source_initial_state_hash
    ):
        raise _integrity("SQLite initial state binding is invalid")


def read_canonical_json_payload(payload: str) -> Any:
    """Parse one SQLite JSON value with the same canonical rules as artifacts."""

    parsed = json.loads(
        payload,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_json_constant,
    )
    if canonical_json(parsed) != payload:
        raise ValueError("JSON is not canonical")
    return parsed


def preflight_sqlite(root: Path, manifest: CampaignManifest) -> SQLitePreflight:
    """Inspect the frozen EventStore schema without allowing it to initialize."""

    _assert_exact_tree(root, missing_is_not_found=False)
    before_files = snapshot_files(root)
    connection = _open_read_only(root / "session" / "campaign.sqlite3")
    try:
        _check_schema(connection)
        sqlite_snapshot = _authoritative_rows(connection)
        _validate_campaign_row(sqlite_snapshot.campaign_row, manifest)
        if any(row[1] != manifest.campaign_id for row in sqlite_snapshot.rows[1][1] + sqlite_snapshot.rows[2][1]):
            raise _integrity("SQLite authoritative rows contain another Campaign")
    except CampaignError:
        raise
    except sqlite3.Error as exc:
        raise _integrity("SQLite read-only preflight failed") from exc
    finally:
        try:
            connection.close()
        except sqlite3.Error as exc:
            raise _integrity("SQLite read-only connection could not close") from exc
    return SQLitePreflight(before_files, sqlite_snapshot)


def assert_observables_unchanged(root: Path, preflight: SQLitePreflight) -> None:
    try:
        _assert_exact_tree(root, missing_is_not_found=False)
        after_files = snapshot_files(root)
    except CampaignError as exc:
        raise _integrity("Campaign files changed during verification") from exc
    if after_files != preflight.files:
        raise _integrity("Campaign file observables changed during verification")
    connection = _open_read_only(root / "session" / "campaign.sqlite3")
    try:
        after_rows = _authoritative_rows(connection)
    except CampaignError:
        raise
    except sqlite3.Error as exc:
        raise _integrity("SQLite rows cannot be compared after verification") from exc
    finally:
        try:
            connection.close()
        except sqlite3.Error as exc:
            raise _integrity("SQLite comparison connection could not close") from exc
    if after_rows != preflight.sqlite:
        raise _integrity("SQLite authoritative rows changed during verification")


def load_projection_map(root: Path) -> tuple[PlayerProjectionMap, dict[str, Any]]:
    value = read_canonical_json(root / "player_projection.json")
    expected_fields = {
        "schema_version",
        "projection_compiler_id",
        "mechanics_profile",
        "source_worldpack_hash",
        "source_initial_state_hash",
        "content_locale",
        "world",
        "identities",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise _integrity("PlayerProjectionMap has an invalid field set")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["projection_compiler_id"] != "phase9b2a-player-projection-v1"
        or value["mechanics_profile"] != "phase75_expedition_v1"
        or not isinstance(value["mechanics_profile"], str)
        or not isinstance(value["content_locale"], str)
        or not isinstance(value["world"], dict)
        or not isinstance(value["identities"], dict)
        or any(
            not isinstance(value[field], str) or _HASH_RE.fullmatch(value[field]) is None
            for field in ("source_worldpack_hash", "source_initial_state_hash")
        )
    ):
        raise _integrity("PlayerProjectionMap has invalid scalar fields")
    try:
        projection = PlayerProjectionMap(
            schema_version=value["schema_version"],
            projection_compiler_id=value["projection_compiler_id"],
            mechanics_profile=value["mechanics_profile"],
            source_worldpack_hash=value["source_worldpack_hash"],
            source_initial_state_hash=value["source_initial_state_hash"],
            content_locale=value["content_locale"],
            world=copy.deepcopy(value["world"]),
            identities=copy.deepcopy(value["identities"]),
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise _integrity("PlayerProjectionMap is invalid") from exc
    return projection, value


def load_projection_manifest(root: Path) -> dict[str, Any]:
    value = read_canonical_json(root / "projection_manifest.json")
    fields = {
        "schema_version",
        "projection_compiler_id",
        "source_worldpack_hash",
        "source_initial_state_hash",
        "projection_draft_hash",
        "player_projection_hash",
        "projection_report_hash",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise _integrity("projection manifest has an invalid field set")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["projection_compiler_id"] != "phase9b2a-player-projection-v1"
        or any(
            not isinstance(value[field], str) or _HASH_RE.fullmatch(value[field]) is None
            for field in fields - {"schema_version", "projection_compiler_id"}
        )
    ):
        raise _integrity("projection manifest has invalid scalar fields")
    return value


def _source_summary(source_root: Path) -> dict[str, Any]:
    try:
        return verify_bundle(source_root)
    except WorldGenError as exc:
        raise CampaignError("SOURCE_BUNDLE_INVALID", "WorldPack verification failed") from exc
    except Exception as exc:
        raise CampaignError("SOURCE_BUNDLE_INVALID", "WorldPack verification failed") from exc


def verify_external_pair(world_root: Path, projection_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source = _source_summary(world_root)
    try:
        projection_manifest = load_projection_manifest(projection_root)
    except CampaignError as exc:
        raise CampaignError("PROJECTION_BUNDLE_INVALID", "Projection verification failed") from exc
    if (
        projection_manifest.get("source_worldpack_hash") != source.get("worldpack_hash")
        or projection_manifest.get("source_initial_state_hash") != source.get("initial_state_hash")
    ):
        raise CampaignError("PROJECTION_SOURCE_MISMATCH", "Projection source binding does not match WorldPack")
    try:
        projection = verify_projection_bundle(world_root, projection_root)
    except WorldGenError as exc:
        raise CampaignError("PROJECTION_BUNDLE_INVALID", "Projection verification failed") from exc
    except Exception as exc:
        raise CampaignError("PROJECTION_BUNDLE_INVALID", "Projection verification failed") from exc
    return source, projection


def reconstruct_request(value: Any) -> LLMDecisionRequest:
    """Rebuild one serialized Phase 9A request through the frozen builder."""

    fields = {"decision_number", "observation", "choices", "request_fingerprint"}
    if not isinstance(value, dict) or set(value) != fields:
        raise _integrity("serialized request has an invalid field set")
    observation = value["observation"]
    choices = value["choices"]
    if not isinstance(observation, dict) or "legal_actions" in observation or not isinstance(choices, list):
        raise _integrity("serialized request has invalid observation or choices")
    legal_actions: list[_DetachedLegalAction] = []
    for choice in choices:
        if not isinstance(choice, dict) or set(choice) != {
            "choice_id",
            "action_type",
            "params",
            "duration_minutes",
            "stamina_cost",
        }:
            raise _integrity("serialized choice has an invalid field set")
        try:
            normalized = LLMActionChoice(
                choice["choice_id"],
                choice["action_type"],
                copy.deepcopy(choice["params"]),
                choice["duration_minutes"],
                choice["stamina_cost"],
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise _integrity("serialized choice has invalid values") from exc
        legal_actions.append(
            _DetachedLegalAction(
                action_type=normalized.action_type,
                params=normalized.params,
                duration_minutes=normalized.duration_minutes,
                stamina_cost=normalized.stamina_cost,
            )
        )
    rebuilt_observation = copy.deepcopy(observation)
    rebuilt_observation["legal_actions"] = legal_actions
    try:
        rebuilt = build_llm_decision_request(rebuilt_observation, value["decision_number"])
    except (TypeError, ValueError, KeyError) as exc:
        raise _integrity("serialized request cannot be rebuilt") from exc
    if rebuilt.to_dict() != value:
        raise _integrity("serialized request does not match frozen request reconstruction")
    return rebuilt


def _build_initial_request(root: Path) -> LLMDecisionRequest:
    value = read_canonical_json(root / "world" / "initial_state.json")
    try:
        state = GameState(**copy.deepcopy(value))
        return build_llm_decision_request(build_observation(state), 1)
    except (TypeError, ValueError, KeyError) as exc:
        raise _integrity("initial canonical request cannot be rebuilt") from exc


def _artifact_hashes(root: Path) -> dict[str, str]:
    names = {
        "worldpack_hash": "world/compiled_worldpack.json",
        "source_initial_state_hash": "world/initial_state.json",
        "world_bundle_manifest_hash": "world/bundle.json",
        "player_projection_hash": "projection/player_projection.json",
        "projection_bundle_manifest_hash": "projection/projection_manifest.json",
    }
    result: dict[str, str] = {}
    for field, relative in names.items():
        try:
            result[field] = sha256_bytes((root / relative).read_bytes())
        except OSError as exc:
            raise _integrity("Campaign artifact hash cannot be read") from exc
    return result


def _map_session_error(error: SessionError, *, bootstrap: bool) -> CampaignError:
    if error.code in {"STALE_REQUEST", "UNKNOWN_CHOICE", "SESSION_TERMINAL"} and not bootstrap:
        messages = {
            "STALE_REQUEST": "request fingerprint is stale",
            "UNKNOWN_CHOICE": "choice_id is not currently legal",
            "SESSION_TERMINAL": "session is not accepting decisions",
        }
        return CampaignError(error.code, messages[error.code])
    if bootstrap:
        return CampaignError("SESSION_BOOTSTRAP_FAILED", "Phase 9A Session bootstrap failed")
    if error.code == "SESSION_NOT_FOUND":
        return CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "published Campaign Session is missing")
    return CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "published Campaign Session is invalid")


def verify_published_campaign(root: Path, *, bootstrap: bool = False) -> VerifiedCampaign:
    """Verify one Campaign while proving all observables remain read-only."""

    _assert_exact_tree(root, missing_is_not_found=not bootstrap)
    manifest_value = read_canonical_json(root / CAMPAIGN_FILE)
    manifest = CampaignManifest.from_dict(manifest_value)
    preflight = preflight_sqlite(root, manifest)
    try:
        world_manifest = read_canonical_json(root / "world" / "bundle.json")
        worldpack = read_canonical_json(root / "world" / "compiled_worldpack.json")
        initial_state = read_canonical_json(root / "world" / "initial_state.json")
        try:
            source_verification = verify_bundle(root / "world")
        except WorldGenError as exc:
            raise _integrity("copied WorldPack verification failed") from exc
        except Exception as exc:
            raise _integrity("copied WorldPack verification failed") from exc
        projection_manifest = load_projection_manifest(root / "projection")
        projection, projection_value = load_projection_map(root / "projection")
        artifact_hashes = _artifact_hashes(root)
        if any(getattr(manifest, field) != value for field, value in artifact_hashes.items()):
            raise _integrity("Campaign artifact hash binding is invalid")
        if world_manifest.get("worldpack_hash") != manifest.worldpack_hash or world_manifest.get("initial_state_hash") != manifest.source_initial_state_hash:
            raise _integrity("WorldPack manifest binding is invalid")
        if projection_manifest.get("source_worldpack_hash") != manifest.worldpack_hash or projection_manifest.get("source_initial_state_hash") != manifest.source_initial_state_hash:
            raise _integrity("Projection source binding does not match copied WorldPack")
        if projection_manifest.get("player_projection_hash") != manifest.player_projection_hash:
            raise _integrity("Projection map hash binding is invalid")
        if (
            projection.source_worldpack_hash != manifest.worldpack_hash
            or projection.source_initial_state_hash != manifest.source_initial_state_hash
        ):
            raise _integrity("PlayerProjectionMap source binding is invalid")
        if projection_hash(projection) != manifest.player_projection_hash or sha256_json(projection_value) != manifest.player_projection_hash:
            raise _integrity("PlayerProjectionMap hash is invalid")
        if sha256_json(worldpack) != manifest.worldpack_hash or sha256_json(initial_state) != manifest.source_initial_state_hash:
            raise _integrity("WorldPack artifact hash is invalid")
        try:
            projection_verification = verify_projection_bundle(root / "world", root / "projection")
        except WorldGenError as exc:
            raise _integrity("copied Projection verification failed") from exc
        except Exception as exc:
            raise _integrity("copied Projection verification failed") from exc
        if source_verification.get("worldpack_hash") != manifest.worldpack_hash or source_verification.get("initial_state_hash") != manifest.source_initial_state_hash:
            raise _integrity("copied WorldPack verification binding is invalid")
        if projection_verification.get("projection_hash") != manifest.player_projection_hash:
            raise _integrity("copied Projection verification binding is invalid")
        initial_request = _build_initial_request(root)
        initial_presentation = build_player_presentation(initial_request, projection)
        if initial_request.request_fingerprint != manifest.initial_request_fingerprint:
            raise _integrity("initial request fingerprint binding is invalid")
        if presentation_hash(initial_presentation) != manifest.initial_presentation_hash:
            raise _integrity("initial presentation hash binding is invalid")
        try:
            session_verification = verify_session(root / "session")
            session_summary = session_verification["session"]
            current_serialized = next_session(root / "session")["request"]
        except SessionError as exc:
            raise _map_session_error(exc, bootstrap=bootstrap) from exc
        if session_summary.get("campaign_id") != manifest.campaign_id or session_summary.get("actor_id") != manifest.actor_id or session_summary.get("max_decisions") != manifest.max_decisions:
            raise _integrity("Session manifest does not match Campaign manifest")
        session_verification_data = session_verification["verification"]
        if session_verification_data.get("recorded_decision_replay_completion_calls") != 0:
            raise _integrity("RecordedDecision replay performed completion calls")
        if not all(
            session_verification_data.get(field) is True
            for field in (
                "event_replay",
                "recorded_decision_replay",
                "sqlite_persistence_integrity",
                "sqlite_close_reopen",
            )
        ):
            raise _integrity("Phase 9A Session verification is incomplete")
        if session_summary.get("status") == "AWAITING_DECISION":
            current_request = reconstruct_request(current_serialized)
            current_presentation = build_player_presentation(current_request, projection)
            if session_summary.get("current_request_fingerprint") != current_request.request_fingerprint:
                raise _integrity("current request fingerprint binding is invalid")
        else:
            current_request = None
            current_presentation = None
        verification = {
            "valid": True,
            "worldpack_hash": manifest.worldpack_hash,
            "source_initial_state_hash": manifest.source_initial_state_hash,
            "projection_hash": manifest.player_projection_hash,
            "initial_request_fingerprint": manifest.initial_request_fingerprint,
            "initial_presentation_hash": manifest.initial_presentation_hash,
            "event_replay": bool(session_verification["verification"]["event_replay"]),
            "recorded_decision_replay": bool(session_verification["verification"]["recorded_decision_replay"]),
            "recorded_decision_replay_completion_calls": session_verification_data["recorded_decision_replay_completion_calls"],
            "sqlite_persistence_integrity": bool(session_verification["verification"]["sqlite_persistence_integrity"]),
            "sqlite_close_reopen": bool(session_verification["verification"]["sqlite_close_reopen"]),
        }
        result = VerifiedCampaign(
            manifest=manifest,
            session_summary=copy.deepcopy(session_summary),
            verification=verification,
            projection=projection,
            current_request=current_request,
            current_presentation=current_presentation,
        )
    except CampaignError:
        assert_observables_unchanged(root, preflight)
        raise
    except (TypeError, ValueError, KeyError, WorldGenError) as exc:
        assert_observables_unchanged(root, preflight)
        raise _integrity("Campaign verification failed") from exc
    assert_observables_unchanged(root, preflight)
    return result


__all__ = [
    "CAMPAIGN_RELATIVE_FILES",
    "CAMPAIGN_FILE",
    "FileObservable",
    "SQLitePreflight",
    "VerifiedCampaign",
    "assert_observables_unchanged",
    "load_projection_manifest",
    "load_projection_map",
    "preflight_sqlite",
    "reconstruct_request",
    "snapshot_files",
    "verify_external_pair",
    "verify_published_campaign",
]
