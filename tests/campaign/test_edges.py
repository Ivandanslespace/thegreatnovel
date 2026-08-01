from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import tgn.campaign.common as common
import tgn.campaign.publication as publication
import tgn.campaign.service as service
from tgn.campaign import CampaignError, CampaignService
from tgn.session import SessionError


def expect_campaign_error(callable_obj, *args, **kwargs) -> CampaignError:
    with pytest.raises(CampaignError) as error:
        callable_obj(*args, **kwargs)
    return error.value


def test_common_json_reader_rejects_duplicate_constant_and_noncanonical(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"x":1,"x":2}', encoding="utf-8")
    assert expect_campaign_error(common.read_canonical_json, duplicate).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    constant = tmp_path / "constant.json"
    constant.write_text('{"x":NaN}', encoding="utf-8")
    assert expect_campaign_error(common.read_canonical_json, constant).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    noncanonical = tmp_path / "noncanonical.json"
    noncanonical.write_text('{ "x": 1 }', encoding="utf-8")
    assert expect_campaign_error(common.read_canonical_json, noncanonical).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_common_json_reader_preserves_boundary_error(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "value.json"
    path.write_text("{}", encoding="utf-8")

    def fail(_):
        raise CampaignError("SOURCE_BUNDLE_INVALID", "safe")

    monkeypatch.setattr(common, "canonical_json", fail)
    assert expect_campaign_error(common.read_canonical_json, path).code == "SOURCE_BUNDLE_INVALID"


def test_common_write_and_copy_fail_closed(monkeypatch, tmp_path: Path) -> None:
    assert expect_campaign_error(common.write_canonical_json, tmp_path / "bad.json", object()).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    source = tmp_path / "source.json"
    source.write_text("{}", encoding="utf-8")
    destination = tmp_path / "destination"
    assert expect_campaign_error(common.copy_files, tmp_path / "missing", destination, ["missing.json"]).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    def fail_copy(*_args, **_kwargs):
        raise common.shutil.Error("copy failed")

    monkeypatch.setattr(common.shutil, "copyfile", fail_copy)
    common.copy_files(tmp_path, destination, ["source.json"])
    assert (destination / "source.json").read_bytes() == source.read_bytes()

    def fail_write(*_args, **_kwargs):
        raise OSError("write failed")

    monkeypatch.setattr(common.Path, "write_text", fail_write)
    assert expect_campaign_error(common.write_canonical_json, tmp_path / "write.json", {}).code == "CAMPAIGN_INTEGRITY_MISMATCH"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"campaign_id": "Bad ID"},
        {"actor_id": "Bad ID"},
        {"max_decisions": True},
    ],
)
def test_create_input_and_operation_argument_validation(kwargs, bundle_pair, tmp_path: Path) -> None:
    values = {
        "campaign_id": "campaign-001",
        "actor_id": "player",
        "max_decisions": 10,
    }
    values.update(kwargs)
    assert expect_campaign_error(
        service.create_campaign,
        tmp_path / "campaign",
        world_bundle_dir=bundle_pair[0],
        projection_bundle_dir=bundle_pair[1],
        **values,
    ).code == "INVALID_CAMPAIGN_INPUT"
    assert expect_campaign_error(CampaignService, object()).code == "INVALID_CAMPAIGN_INPUT"

    instance = CampaignService(tmp_path / "missing")
    assert expect_campaign_error(instance.choose, request_fingerprint=object(), choice_id="choice-000").code == "INVALID_CAMPAIGN_INPUT"
    assert expect_campaign_error(instance.stop, request_fingerprint=object()).code == "INVALID_CAMPAIGN_INPUT"


def test_session_error_mapping_and_sqlite_bootstrap_edges(tmp_path: Path) -> None:
    assert service._map_session_error(SessionError("SESSION_NOT_FOUND", "raw"), bootstrap=False).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert service._map_session_error(SessionError("INVALID_INITIAL_STATE", "raw"), bootstrap=True).code == "SESSION_BOOTSTRAP_FAILED"

    missing = expect_campaign_error(service._sqlite_initial_hash, tmp_path / "missing", "campaign")
    assert missing.code == "SESSION_BOOTSTRAP_FAILED"
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    connection = sqlite3.connect(session_dir / "campaign.sqlite3")
    connection.execute("CREATE TABLE campaigns (campaign_id TEXT, initial_state_hash TEXT)")
    connection.commit()
    connection.close()
    assert expect_campaign_error(service._sqlite_initial_hash, session_dir, "campaign").code == "SESSION_BOOTSTRAP_FAILED"


def test_publication_capability_platform_dispatch_and_loader_failures(monkeypatch) -> None:
    original_linux = publication._linux_rename_function
    original_macos = publication._macos_rename_function
    monkeypatch.setattr(publication.os, "name", "posix")
    monkeypatch.setattr(publication.sys, "platform", "linux")
    monkeypatch.setattr(publication, "_linux_rename_function", lambda: object())
    publication.assert_publication_capability()
    monkeypatch.setattr(publication.sys, "platform", "darwin")
    monkeypatch.setattr(publication, "_macos_rename_function", lambda: object())
    publication.assert_publication_capability()
    monkeypatch.setattr(publication.sys, "platform", "sunos")
    with pytest.raises(publication._NoReplaceUnavailable):
        publication.assert_publication_capability()

    monkeypatch.setattr(publication.ctypes, "WinDLL", lambda *_args, **_kwargs: object(), raising=False)
    monkeypatch.setattr(publication.os, "name", "nt")
    with pytest.raises(publication._NoReplaceUnavailable):
        publication._windows_move_function()
    monkeypatch.setattr(publication.ctypes, "CDLL", lambda *_args, **_kwargs: object())
    with pytest.raises(publication._NoReplaceUnavailable):
        original_linux()
    monkeypatch.setattr(publication.ctypes, "CDLL", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")))
    with pytest.raises(publication._NoReplaceUnavailable):
        original_macos()
