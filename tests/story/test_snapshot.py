from __future__ import annotations

import dataclasses
import os
import sqlite3
import stat
from types import SimpleNamespace
from pathlib import Path

import pytest

from tgn.campaign import next_campaign
from tgn.story.campaign_snapshot import (
    CAMPAIGN_RELATIVE_FILES,
    _read_sqlite_rows,
    capture_campaign_snapshot,
    compare_request_prefix,
    manifest_from_snapshot,
    parse_snapshot_json,
    verify_and_capture_campaign,
)
import tgn.story.campaign_snapshot as snapshot_module
from tgn.story.models import StoryManifest


def _choose_drop(campaign: Path, *, action_type: str = "DROP") -> None:
    from tgn.campaign import choose_campaign

    current = next_campaign(campaign)
    choice = next(item for item in current["canonical_request"]["choices"] if item["action_type"] == action_type)
    choose_campaign(campaign, request_fingerprint=current["canonical_request"]["request_fingerprint"], choice_id=choice["choice_id"])


def test_snapshot_captures_exact_files_rows_and_no_sqlite_sidecars(story_factory) -> None:
    campaign, _story, _config = story_factory()
    session_dir = campaign / "session"
    before_children = sorted(item.name for item in session_dir.iterdir())
    manifest, snapshot = verify_and_capture_campaign(campaign)
    after_children = sorted(item.name for item in session_dir.iterdir())
    assert before_children == after_children
    assert [item.relative_path for item in snapshot.campaign_files] == sorted(CAMPAIGN_RELATIVE_FILES)
    assert set(dict(snapshot.sqlite_authoritative_rows)) == {"campaigns", "events", "snapshots"}
    assert len(snapshot.campaign_row) == 7
    assert snapshot.event_rows == ()
    assert snapshot.snapshot_rows == ()
    assert snapshot.file_bytes("campaign.json")
    with pytest.raises(KeyError):
        snapshot.file_bytes("not-an-artifact")
    assert manifest.campaign_id == dict(snapshot.sqlite_authoritative_rows)["campaigns"][0][0]
    assert manifest_from_snapshot(snapshot).campaign_id == manifest.campaign_id
    assert parse_snapshot_json(snapshot, "session/session.json")["campaign_id"] == manifest.campaign_id


def test_snapshot_prefix_allows_later_append_but_rejects_identity_changes(story_factory) -> None:
    campaign, _story, _config = story_factory()
    _choose_drop(campaign)
    before = capture_campaign_snapshot(campaign)
    _choose_drop(campaign, action_type="SEARCH")
    after = capture_campaign_snapshot(campaign)
    assert compare_request_prefix(before, after, event_seq=1, recorded_decision_index=1) is True
    assert compare_request_prefix(before, after, event_seq=0, recorded_decision_index=0) is True
    changed_files = list(after.campaign_files)
    changed_files[0] = dataclasses.replace(changed_files[0], sha256="b" * 64)
    changed = dataclasses.replace(after, campaign_files=tuple(changed_files))
    assert compare_request_prefix(before, changed, event_seq=1, recorded_decision_index=1) is False
    assert compare_request_prefix(before, after, event_seq=1, recorded_decision_index=2) is False


def test_snapshot_sqlite_errors_are_bounded(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, _story, _config = story_factory()

    class BrokenConnection:
        def execute(self, _query):
            raise sqlite3.OperationalError("hidden sqlite detail")

        def close(self):
            return None

    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: BrokenConnection())
    with pytest.raises(OSError):
        _read_sqlite_rows(campaign)

    class CloseBrokenConnection:
        def execute(self, _query):
            return []

        def close(self):
            raise RuntimeError("close detail")

    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: CloseBrokenConnection())
    with pytest.raises(OSError):
        _read_sqlite_rows(campaign)


def test_snapshot_rejects_extra_campaign_tree_entry(story_factory) -> None:
    campaign, _story, _config = story_factory()
    extra = campaign / "extra"
    extra.write_text("not allowed", encoding="utf-8")
    with pytest.raises(OSError):
        capture_campaign_snapshot(campaign)


def test_snapshot_tree_and_capture_failure_boundaries(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(OSError):
        capture_campaign_snapshot(missing)
    file_root = tmp_path / "file-root"
    file_root.write_text("not a directory", encoding="utf-8")
    with pytest.raises(OSError):
        capture_campaign_snapshot(file_root)

    campaign, _story, _config = story_factory()
    campaign_json = campaign / "campaign.json"
    campaign_json.unlink()
    with pytest.raises(OSError):
        capture_campaign_snapshot(campaign)

    campaign, _story, _config = story_factory(name="nested")
    world = campaign / "world"
    extra = world / "extra"
    extra.write_text("extra", encoding="utf-8")
    with pytest.raises(OSError):
        capture_campaign_snapshot(campaign)
    extra.unlink()
    (world / "bundle.json").unlink()
    with pytest.raises(OSError):
        capture_campaign_snapshot(campaign)

    campaign, _story, _config = story_factory(name="sqlite-race")
    database = campaign / "session" / "campaign.sqlite3"
    original_lstat = snapshot_module.os.lstat
    calls = {"database": 0}

    def changing_lstat(path):
        if Path(path) == database:
            calls["database"] += 1
            if calls["database"] > 1:
                return SimpleNamespace(st_mode=stat.S_IFREG, st_dev=999, st_ino=999)
        return original_lstat(path)

    monkeypatch.setattr(snapshot_module.os, "lstat", changing_lstat)
    with pytest.raises(OSError):
        snapshot_module._read_sqlite_rows(campaign)


def test_snapshot_prefix_and_verify_wrapper_failure(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, _story, _config = story_factory()
    before = capture_campaign_snapshot(campaign)
    changed_tables = dict(before.sqlite_authoritative_rows)
    changed_tables["campaigns"] = (tuple(["other", *changed_tables["campaigns"][0][1:]]),)
    changed = dataclasses.replace(before, sqlite_authoritative_rows=tuple(changed_tables.items()))
    assert compare_request_prefix(before, changed, event_seq=0, recorded_decision_index=0) is False
    bad_events = dict(before.sqlite_authoritative_rows)
    bad_events["events"] = (tuple([None, None, 1] + [None] * 11),)
    bad = dataclasses.replace(before, sqlite_authoritative_rows=tuple(bad_events.items()))
    assert compare_request_prefix(before, bad, event_seq=1, recorded_decision_index=0) is False
    bad_records = dataclasses.replace(
        before,
        recorded_decisions_json_canonical_bytes=b"not-json",
    )
    assert compare_request_prefix(before, bad_records, event_seq=0, recorded_decision_index=0) is False

    monkeypatch.setattr(snapshot_module, "verify_campaign", lambda *_args: (_ for _ in ()).throw(RuntimeError("candidate")))
    with pytest.raises(OSError):
        verify_and_capture_campaign(campaign)
