from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest

import tgn.campaign.verification as verification
from tgn.campaign import CampaignError
from tgn.campaign.common import read_canonical_json, write_canonical_json
from tgn.campaign.models import CampaignManifest
from tgn.session import SessionError
from tgn.worldgen.models import WorldGenError


def expect_error(callable_obj, *args, **kwargs) -> CampaignError:
    with pytest.raises(CampaignError) as error:
        callable_obj(*args, **kwargs)
    return error.value


def manifest_for(target: Path) -> CampaignManifest:
    return CampaignManifest.from_dict(read_canonical_json(target / "campaign.json"))


def test_exact_tree_rejects_missing_invalid_and_extra_artifacts(monkeypatch, campaign_factory, tmp_path: Path) -> None:
    with pytest.raises(CampaignError) as missing:
        verification._assert_exact_tree(tmp_path / "absent", missing_is_not_found=False)
    assert missing.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    target, _ = campaign_factory(name="extra")
    (target / "extra.txt").write_text("extra", encoding="utf-8")
    assert expect_error(verification._assert_exact_tree, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    target, _ = campaign_factory(name="not-directory")
    import shutil

    shutil.rmtree(target / "world")
    (target / "world").write_text("not a directory", encoding="utf-8")
    assert expect_error(verification._assert_exact_tree, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    target, _ = campaign_factory(name="campaign-file")
    (target / "campaign.json").unlink()
    (target / "campaign.json").mkdir()
    assert expect_error(verification._assert_exact_tree, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    target, _ = campaign_factory(name="nested-extra")
    (target / "world" / "extra.txt").write_text("extra", encoding="utf-8")
    assert expect_error(verification._assert_exact_tree, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    target, _ = campaign_factory(name="nested-directory")
    path = target / "world" / "world_request.json"
    path.unlink()
    path.mkdir()
    assert expect_error(verification._assert_exact_tree, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    target, _ = campaign_factory(name="inspect-error")
    monkeypatch.setattr(verification.Path, "iterdir", lambda _self: (_ for _ in ()).throw(OSError("raw")))
    assert expect_error(verification._assert_exact_tree, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_snapshot_and_read_only_open_fail_closed(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="snapshot-error")
    monkeypatch.setattr(verification.Path, "stat", lambda _self: (_ for _ in ()).throw(OSError("raw")))
    assert expect_error(verification.snapshot_files, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    def fail_connect(*_args, **_kwargs):
        raise sqlite3.OperationalError("raw")

    monkeypatch.setattr(verification.sqlite3, "connect", fail_connect)
    assert expect_error(verification._open_read_only, target / "session" / "campaign.sqlite3").code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_sqlite_schema_and_rows_reject_bad_integrity_and_zero_rows(campaign_factory) -> None:
    class BadIntegrity:
        def execute(self, _sql):
            return type("Result", (), {"fetchone": lambda self: ("bad",)})()

    assert expect_error(verification._check_schema, BadIntegrity()).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    class Broken:
        def execute(self, _sql):
            raise sqlite3.OperationalError("raw")

    assert expect_error(verification._check_schema, Broken()).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    target, _ = campaign_factory(name="zero-rows")
    connection = sqlite3.connect(target / "session" / "campaign.sqlite3")
    connection.execute("DELETE FROM campaigns")
    connection.commit()
    with pytest.raises(CampaignError) as raised:
        verification._authoritative_rows(connection)
    connection.close()
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_named_index_definition_and_authoritative_campaign_binding_are_exact(campaign_factory) -> None:
    target, _ = campaign_factory(name="index-definition")
    connection = sqlite3.connect(target / "session" / "campaign.sqlite3")
    connection.execute("DROP INDEX idx_events_campaign_seq")
    connection.execute("CREATE INDEX idx_events_campaign_seq ON events(event_type)")
    connection.commit()
    connection.close()
    assert expect_error(verification.verify_published_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    target, _ = campaign_factory(name="authoritative-binding")
    manifest = manifest_for(target)
    preflight = verification.preflight_sqlite(target, manifest)
    rows = list(preflight.sqlite.rows)
    event_rows = list(rows[1][1])
    event_rows.append(("other-event", "other", 1, 1, 0, "TEST", None, None, None, None, "{}", "a" * 64, "b" * 64, "now"))
    rows[1] = ("events", tuple(event_rows))
    changed = verification.SQLiteObservable(tuple(rows), preflight.sqlite.campaign_row)
    original = verification._authoritative_rows
    try:
        verification._authoritative_rows = lambda _connection: changed
        assert expect_error(verification.preflight_sqlite, target, manifest).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    finally:
        verification._authoritative_rows = original


@pytest.mark.parametrize("field", ["campaign_id", "engine_version", "schema_version", "seed", "state_json", "state_hash", "created_at"])
def test_campaign_row_scalar_validation(field: str, campaign_factory) -> None:
    target, _ = campaign_factory(name=f"row-{field}")
    manifest = manifest_for(target)
    connection = sqlite3.connect(target / "session" / "campaign.sqlite3")
    row = tuple(connection.execute("SELECT campaign_id, engine_version, state_schema_version, seed, initial_state_json, initial_state_hash, created_at FROM campaigns").fetchone())
    connection.close()
    values = list(row)
    replacements = {
        "campaign_id": "other",
        "engine_version": None,
        "schema_version": True,
        "seed": None,
        "state_json": "not-json",
        "state_hash": "BAD",
        "created_at": None,
    }
    values[list(("campaign_id", "engine_version", "schema_version", "seed", "state_json", "state_hash", "created_at")).index(field)] = replacements[field]
    assert expect_error(verification._validate_campaign_row, tuple(values), manifest).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_sqlite_payload_parser_rejects_duplicate_constant_and_noncanonical() -> None:
    for payload in ('{"x":1,"x":2}', '{"x":NaN}', '{ "x": 1 }'):
        with pytest.raises(ValueError):
            verification.read_canonical_json_payload(payload)


def test_preflight_and_observable_comparison_wrap_sqlite_failures(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="preflight-error")
    manifest = manifest_for(target)
    original_check = verification._check_schema
    monkeypatch.setattr(verification, "_check_schema", lambda _connection: (_ for _ in ()).throw(sqlite3.OperationalError("raw")))
    assert expect_error(verification.preflight_sqlite, target, manifest).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification, "_check_schema", original_check)
    preflight = verification.preflight_sqlite(target, manifest)

    monkeypatch.setattr(verification, "_authoritative_rows", lambda _connection: (_ for _ in ()).throw(sqlite3.OperationalError("raw")))
    assert expect_error(verification.assert_observables_unchanged, target, preflight).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(verification, "_authoritative_rows", lambda _connection: (_ for _ in ()).throw(CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "already bounded")))
    assert expect_error(verification.assert_observables_unchanged, target, preflight).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    class CloseFailure:
        def close(self):
            raise sqlite3.OperationalError("raw")

    monkeypatch.setattr(verification, "_open_read_only", lambda _path: CloseFailure())
    monkeypatch.setattr(verification, "_check_schema", lambda _connection: None)
    monkeypatch.setattr(verification, "_authoritative_rows", lambda _connection: preflight.sqlite)
    monkeypatch.setattr(verification, "_validate_campaign_row", lambda *_args: None)
    assert expect_error(verification.preflight_sqlite, target, manifest).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(verification, "_authoritative_rows", lambda _connection: preflight.sqlite)
    class CloseError:
        def close(self):
            raise sqlite3.OperationalError("raw")

    monkeypatch.setattr(verification, "_open_read_only", lambda _path: CloseError())
    assert expect_error(verification.assert_observables_unchanged, target, preflight).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_observable_row_change_is_detected(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="row-change")
    manifest = manifest_for(target)
    preflight = verification.preflight_sqlite(target, manifest)
    changed = verification.SQLiteObservable(preflight.sqlite.rows, ("other",) + preflight.sqlite.campaign_row[1:])
    monkeypatch.setattr(verification, "_authoritative_rows", lambda _connection: changed)
    assert expect_error(verification.assert_observables_unchanged, target, preflight).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_state_hash_binding_mismatch_is_rejected(campaign_factory) -> None:
    target, _ = campaign_factory(name="state-hash-binding")
    manifest = manifest_for(target)
    connection = sqlite3.connect(target / "session" / "campaign.sqlite3")
    row = tuple(connection.execute("SELECT campaign_id, engine_version, state_schema_version, seed, initial_state_json, initial_state_hash, created_at FROM campaigns").fetchone())
    connection.close()
    values = list(row)
    values[5] = "b" * 64
    assert expect_error(verification._validate_campaign_row, tuple(values), manifest).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_campaign_row_frozen_metadata_values_are_exact(campaign_factory) -> None:
    target, _ = campaign_factory(name="row-metadata-values")
    manifest = manifest_for(target)
    connection = sqlite3.connect(target / "session" / "campaign.sqlite3")
    row = tuple(connection.execute("SELECT campaign_id, engine_version, state_schema_version, seed, initial_state_json, initial_state_hash, created_at FROM campaigns").fetchone())
    connection.close()
    engine = list(row)
    engine[1] = "2.0.0"
    assert expect_error(verification._validate_campaign_row, tuple(engine), manifest).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    schema = list(row)
    schema[2] = 2
    assert expect_error(verification._validate_campaign_row, tuple(schema), manifest).code == "CAMPAIGN_INTEGRITY_MISMATCH"
