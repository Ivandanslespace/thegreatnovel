from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tgn.campaign import CampaignError, verify_campaign
from tgn.campaign import verification
from tgn.campaign.common import write_canonical_json

from .conftest import file_snapshot


def expect_error(callable_obj, *args, **kwargs) -> CampaignError:
    with pytest.raises(CampaignError) as error:
        callable_obj(*args, **kwargs)
    return error.value


def rewrite_json(path: Path, update) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    update(value)
    write_canonical_json(path, value)
    return value


@pytest.mark.parametrize(
    "relative,update",
    [
        ("world/compiled_worldpack.json", lambda value: value["public_content"].update({"title": "篡改"})),
        ("projection/player_projection.json", lambda value: value["world"].update({"title": "篡改"})),
        ("campaign.json", lambda value: value.update({"initial_request_fingerprint": "b" * 64})),
        ("campaign.json", lambda value: value.update({"initial_presentation_hash": "b" * 64})),
    ],
)
def test_copied_artifact_or_manifest_tamper_fails_closed(campaign_factory, relative, update) -> None:
    target, _ = campaign_factory()
    rewrite_json(target / relative, update)
    error = expect_error(verify_campaign, target)
    assert error.code in {"CAMPAIGN_INTEGRITY_MISMATCH", "UNSUPPORTED_CAMPAIGN_FORMAT"}


def test_unsupported_campaign_format_is_distinguished(campaign_factory) -> None:
    target, _ = campaign_factory()
    rewrite_json(target / "campaign.json", lambda value: value.update({"schema_version": 99}))
    assert expect_error(verify_campaign, target).code == "UNSUPPORTED_CAMPAIGN_FORMAT"


def test_request_reconstruction_uses_frozen_fingerprint_builder(campaign_factory) -> None:
    target, created = campaign_factory()
    request = created["canonical_request"]
    rebuilt = verification.reconstruct_request(request)
    assert rebuilt.to_dict() == request

    changed_choice = json.loads(json.dumps(request))
    changed_choice["choices"][0]["params"]["unexpected"] = True
    error = expect_error(verification.reconstruct_request, changed_choice)
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    changed_fingerprint = json.loads(json.dumps(request))
    changed_fingerprint["request_fingerprint"] = "a" * 64
    assert expect_error(verification.reconstruct_request, changed_fingerprint).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert target.exists()


def test_projection_map_loader_is_strict_and_detached(campaign_factory) -> None:
    target, _ = campaign_factory()
    projection, serialized = verification.load_projection_map(target / "projection")
    serialized["world"]["title"] = "changed outside"
    assert projection.to_dict()["world"]["title"] != "changed outside"

    rewrite_json(
        target / "projection/player_projection.json",
        lambda value: value.update({"schema_version": True}),
    )
    assert expect_error(verification.load_projection_map, target / "projection").code == "CAMPAIGN_INTEGRITY_MISMATCH"

    rewrite_json(
        target / "projection/player_projection.json",
        lambda value: value.update({"schema_version": 1, "source_worldpack_hash": "BAD"}),
    )
    assert expect_error(verification.load_projection_map, target / "projection").code == "CAMPAIGN_INTEGRITY_MISMATCH"


def _mutate_db(root: Path, statement: str) -> None:
    connection = sqlite3.connect(root / "session" / "campaign.sqlite3")
    try:
        connection.execute(statement)
        connection.commit()
    finally:
        connection.close()


def _rebuild_same_named_table(
    root: Path,
    table: str,
    create_sql: str,
    columns: str,
    index_sql: str | None = None,
) -> None:
    connection = sqlite3.connect(root / "session" / "campaign.sqlite3")
    replacement = f"{table}_replacement"
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(create_sql.format(table=replacement))
        connection.execute(
            f"INSERT INTO {replacement} ({columns}) SELECT {columns} FROM {table}"
        )
        connection.execute(f"DROP TABLE {table}")
        connection.execute(f"ALTER TABLE {replacement} RENAME TO {table}")
        if index_sql is not None:
            connection.execute(index_sql)
        connection.commit()
    finally:
        connection.close()


_CAMPAIGN_COLUMNS = "campaign_id, engine_version, state_schema_version, seed, initial_state_json, initial_state_hash, created_at"
_EVENT_COLUMNS = "event_id, campaign_id, event_seq, decision_seq, game_minute, event_type, actor_id, action_id, causation_id, correlation_id, payload_json, state_hash_before, state_hash_after, created_at"
_SNAPSHOT_COLUMNS = "id, campaign_id, event_seq, state_json, state_hash, created_at"


@pytest.mark.parametrize(
    ("case", "table", "create_sql", "columns", "index_sql"),
    [
        (
            "primary-key",
            "campaigns",
            """
            CREATE TABLE {table} (
                campaign_id TEXT,
                engine_version TEXT NOT NULL DEFAULT '1.0.0',
                state_schema_version INTEGER NOT NULL DEFAULT 1,
                seed TEXT NOT NULL DEFAULT '',
                initial_state_json TEXT NOT NULL,
                initial_state_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            _CAMPAIGN_COLUMNS,
            None,
        ),
        (
            "not-null",
            "campaigns",
            """
            CREATE TABLE {table} (
                campaign_id TEXT PRIMARY KEY,
                engine_version TEXT DEFAULT '1.0.0',
                state_schema_version INTEGER NOT NULL DEFAULT 1,
                seed TEXT NOT NULL DEFAULT '',
                initial_state_json TEXT NOT NULL,
                initial_state_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            _CAMPAIGN_COLUMNS,
            None,
        ),
        (
            "default",
            "campaigns",
            """
            CREATE TABLE {table} (
                campaign_id TEXT PRIMARY KEY,
                engine_version TEXT NOT NULL,
                state_schema_version INTEGER NOT NULL DEFAULT 1,
                seed TEXT NOT NULL DEFAULT '',
                initial_state_json TEXT NOT NULL,
                initial_state_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            _CAMPAIGN_COLUMNS,
            None,
        ),
        (
            "foreign-key",
            "events",
            """
            CREATE TABLE {table} (
                event_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                event_seq INTEGER NOT NULL,
                decision_seq INTEGER NOT NULL,
                game_minute INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                actor_id TEXT,
                action_id TEXT,
                causation_id TEXT,
                correlation_id TEXT,
                payload_json TEXT NOT NULL,
                state_hash_before TEXT NOT NULL,
                state_hash_after TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(campaign_id, event_seq)
            )
            """,
            _EVENT_COLUMNS,
            "CREATE INDEX idx_events_campaign_seq ON events(campaign_id, event_seq)",
        ),
        (
            "unique",
            "events",
            """
            CREATE TABLE {table} (
                event_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                event_seq INTEGER NOT NULL,
                decision_seq INTEGER NOT NULL,
                game_minute INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                actor_id TEXT,
                action_id TEXT,
                causation_id TEXT,
                correlation_id TEXT,
                payload_json TEXT NOT NULL,
                state_hash_before TEXT NOT NULL,
                state_hash_after TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
            )
            """,
            _EVENT_COLUMNS,
            "CREATE INDEX idx_events_campaign_seq ON events(campaign_id, event_seq)",
        ),
        (
            "autoincrement",
            "snapshots",
            """
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                event_seq INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id),
                UNIQUE(campaign_id, event_seq)
            )
            """,
            _SNAPSHOT_COLUMNS,
            "CREATE INDEX idx_snapshots_campaign_seq ON snapshots(campaign_id, event_seq)",
        ),
    ],
)
def test_rebuilt_same_named_tables_missing_frozen_constraints_are_rejected(
    campaign_factory,
    case: str,
    table: str,
    create_sql: str,
    columns: str,
    index_sql: str | None,
) -> None:
    target, _ = campaign_factory(name=f"schema-{case}")
    _rebuild_same_named_table(target, table, create_sql, columns, index_sql)
    error = expect_error(verify_campaign, target)
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"


@pytest.mark.parametrize(
    "statement",
    [
        "DROP TABLE snapshots",
        "DROP INDEX idx_events_campaign_seq",
        "ALTER TABLE campaigns RENAME COLUMN seed TO seed_renamed",
        "CREATE TABLE extra_user_table (value TEXT)",
        "CREATE VIEW extra_user_view AS SELECT campaign_id FROM campaigns",
        "CREATE TRIGGER extra_user_trigger AFTER INSERT ON events BEGIN SELECT 1; END",
        "CREATE INDEX extra_user_index ON events(event_type)",
    ],
)
def test_read_only_sqlite_preflight_rejects_schema_changes(campaign_factory, statement) -> None:
    target, _ = campaign_factory()
    _mutate_db(target, statement)
    error = expect_error(verify_campaign, target)
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("sidecar", ["campaign.sqlite3-journal", "campaign.sqlite3-wal", "campaign.sqlite3-shm"])
def test_sqlite_sidecars_are_rejected(campaign_factory, sidecar: str) -> None:
    target, _ = campaign_factory()
    (target / "session" / sidecar).write_bytes(b"sidecar")
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_verify_uses_read_only_sqlite_uri(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory()
    original_connect = verification.sqlite3.connect
    uris: list[str] = []

    def connect(database, *args, **kwargs):
        if isinstance(database, str):
            uris.append(database)
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(verification.sqlite3, "connect", connect)
    verify_campaign(target)
    assert any("mode=ro" in uri for uri in uris)


def test_frozen_verifier_file_mutation_is_detected(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory()
    original = verification.verify_session

    def mutate_after_verify(session_dir):
        result = original(session_dir)
        path = Path(session_dir) / "session.json"
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        return result

    monkeypatch.setattr(verification, "verify_session", mutate_after_verify)
    error = expect_error(verify_campaign, target)
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_new_file_appearing_during_verify_is_detected(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory()
    original = verification.verify_session

    def add_file(session_dir):
        result = original(session_dir)
        (Path(session_dir) / "late.log").write_text("late", encoding="utf-8")
        return result

    monkeypatch.setattr(verification, "verify_session", add_file)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_session_error_mapping_fails_closed(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory()

    def missing(_):
        from tgn.session import SessionError

        raise SessionError("SESSION_NOT_FOUND", "raw database detail")

    monkeypatch.setattr(verification, "verify_session", missing)
    error = expect_error(verify_campaign, target)
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert "raw database" not in error.message


@pytest.mark.parametrize(
    ("symbol", "exception"),
    [
        ("verify_session", RuntimeError("raw verify_session")),
        ("next_session", RuntimeError("raw next_session")),
        ("presentation_hash", RuntimeError("raw presentation_hash")),
        ("projection_hash", OSError("raw projection_hash")),
    ],
)
def test_unexpected_verification_exceptions_are_bounded(
    monkeypatch,
    campaign_factory,
    symbol: str,
    exception: Exception,
) -> None:
    target, _ = campaign_factory(name=f"unexpected-{symbol}")
    before = file_snapshot(target)

    def raise_unexpected(*_args, **_kwargs):
        raise exception

    monkeypatch.setattr(verification, symbol, raise_unexpected)
    error = expect_error(verify_campaign, target)
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert error.message == "Campaign verification failed"
    assert "raw" not in error.message
    assert file_snapshot(target) == before


def test_unexpected_observable_comparison_exception_is_bounded(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="unexpected-observable-comparison")

    def raise_unexpected(*_args, **_kwargs):
        raise RuntimeError("raw observable comparison")

    monkeypatch.setattr(verification, "assert_observables_unchanged", raise_unexpected)
    error = expect_error(verify_campaign, target)
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert error.message == "Campaign verification failed"
    assert "raw" not in error.message


def test_missing_campaign_is_distinct(tmp_path: Path) -> None:
    error = expect_error(verify_campaign, tmp_path / "missing")
    assert error.code == "CAMPAIGN_NOT_FOUND"


def test_verify_does_not_rewrite_files(campaign_factory) -> None:
    target, _ = campaign_factory()
    before = file_snapshot(target)
    verify_campaign(target)
    assert file_snapshot(target) == before
