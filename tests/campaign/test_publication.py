from __future__ import annotations

import errno
import os

import pytest

import tgn.campaign.publication as publication
import tgn.campaign.service as service
from tgn.campaign import CampaignError, create_campaign


class FakeFunction:
    def __init__(self, result: int, calls: list[tuple[object, ...]]) -> None:
        self.result = result
        self.calls = calls

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class FakeLibrary:
    def __init__(self, name: str, function: FakeFunction) -> None:
        setattr(self, name, function)


class RaisingFunction:
    def __call__(self, *_args):
        raise OSError("raw runtime failure")


def test_windows_no_replace_success_conflict_and_unavailable(monkeypatch, tmp_path) -> None:
    calls: list[tuple[object, ...]] = []
    move = FakeFunction(1, calls)
    monkeypatch.setattr(publication.os, "name", "nt")
    monkeypatch.setattr(
        publication.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: FakeLibrary("MoveFileExW", move),
        raising=False,
    )
    publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    assert calls[-1][2] == 0x00000008
    move.result = 0
    monkeypatch.setattr(publication.ctypes, "get_last_error", lambda: 183, raising=False)
    with pytest.raises(FileExistsError):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    monkeypatch.setattr(publication.ctypes, "get_last_error", lambda: 5, raising=False)
    with pytest.raises(publication._PublicationRuntimeError):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    monkeypatch.setattr(
        publication.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: FakeLibrary("MoveFileExW", RaisingFunction()),
        raising=False,
    )
    with pytest.raises(publication._PublicationRuntimeError):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")


def test_linux_no_replace_success_conflict_and_unavailable(monkeypatch, tmp_path) -> None:
    calls: list[tuple[object, ...]] = []
    rename = FakeFunction(0, calls)
    monkeypatch.setattr(publication.os, "name", "posix")
    monkeypatch.setattr(publication.sys, "platform", "linux")
    monkeypatch.setattr(
        publication.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: FakeLibrary("renameat2", rename),
    )
    publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    assert calls[-1][-1] == 1
    rename.result = -1
    monkeypatch.setattr(publication.ctypes, "get_errno", lambda: errno.EEXIST)
    with pytest.raises(FileExistsError):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    monkeypatch.setattr(publication.ctypes, "get_errno", lambda: errno.EIO)
    with pytest.raises(publication._PublicationRuntimeError):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    monkeypatch.setattr(
        publication.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: FakeLibrary("renameat2", RaisingFunction()),
    )
    with pytest.raises(publication._PublicationRuntimeError):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")


def test_macos_and_unsupported_platforms(monkeypatch, tmp_path) -> None:
    calls: list[tuple[object, ...]] = []
    rename = FakeFunction(0, calls)
    monkeypatch.setattr(publication.os, "name", "posix")
    monkeypatch.setattr(publication.sys, "platform", "darwin")
    monkeypatch.setattr(
        publication.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: FakeLibrary("renameatx_np", rename),
    )
    publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    assert calls[-1][-1] == 0x00000004
    rename.result = -1
    monkeypatch.setattr(publication.ctypes, "get_errno", lambda: errno.ENOTEMPTY)
    with pytest.raises(FileExistsError):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    monkeypatch.setattr(publication.ctypes, "get_errno", lambda: errno.EIO)
    with pytest.raises(publication._PublicationRuntimeError):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    monkeypatch.setattr(
        publication.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: FakeLibrary("renameatx_np", RaisingFunction()),
    )
    with pytest.raises(publication._PublicationRuntimeError):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    monkeypatch.setattr(publication.sys, "platform", "freebsd")
    with pytest.raises(publication._NoReplaceUnavailable):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")


def test_capability_preflight_unavailable_has_no_side_effect(monkeypatch, bundle_pair, tmp_path) -> None:
    calls = {"start_session": 0, "temporary": 0, "lock": 0}

    def unavailable():
        raise publication._NoReplaceUnavailable("unsupported")

    def start_session(*_args, **_kwargs):
        calls["start_session"] += 1

    def make_temporary(*_args, **_kwargs):
        calls["temporary"] += 1
        raise AssertionError("temporary directory must not be created")

    def open_lock(*_args, **_kwargs):
        calls["lock"] += 1
        raise AssertionError("publication lock must not be acquired")

    monkeypatch.setattr(publication, "assert_publication_capability", unavailable)
    monkeypatch.setattr(service.frozen_session, "start_session", start_session)
    monkeypatch.setattr(service.tempfile, "mkdtemp", make_temporary)
    monkeypatch.setattr(service.os, "open", open_lock)
    target = tmp_path / "campaign"
    with pytest.raises(CampaignError) as error:
        create_campaign(
            target,
            world_bundle_dir=bundle_pair[0],
            projection_bundle_dir=bundle_pair[1],
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
    assert error.value.code == "CAMPAIGN_PUBLICATION_UNAVAILABLE"
    assert not target.exists()
    assert not list(tmp_path.glob(".campaign.*"))
    assert not publication.publication_lock_path(target).exists()
    assert calls == {"start_session": 0, "temporary": 0, "lock": 0}


def test_publication_runtime_eio_is_integrity_error_and_cleaned(monkeypatch, bundle_pair, tmp_path) -> None:
    monkeypatch.setattr(
        publication,
        "_publish_directory_no_replace",
        lambda *_args: (_ for _ in ()).throw(publication._PublicationRuntimeError("raw EIO")),
    )
    target = tmp_path / "runtime-eio"
    with pytest.raises(CampaignError) as raised:
        create_campaign(
            target,
            world_bundle_dir=bundle_pair[0],
            projection_bundle_dir=bundle_pair[1],
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert raised.value.message == "Campaign publication failed"
    assert "raw" not in raised.value.message
    assert not target.exists()
    assert not publication.publication_lock_path(target).exists()
    assert not list(tmp_path.glob(".runtime-eio.*"))


def test_lock_cleanup_error_is_not_silently_swallowed(monkeypatch, bundle_pair, tmp_path) -> None:
    target = tmp_path / "lock-cleanup-error"
    lock = publication.publication_lock_path(target)
    original_unlink = service.Path.unlink

    monkeypatch.setattr(
        publication,
        "_publish_directory_no_replace",
        lambda *_args: (_ for _ in ()).throw(publication._PublicationRuntimeError("runtime")),
    )

    def fail_owned_lock_unlink(self, missing_ok=False):
        if self == lock:
            raise OSError("raw unlink")
        return original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(service.Path, "unlink", fail_owned_lock_unlink)
    with pytest.raises(CampaignError) as raised:
        create_campaign(
            target,
            world_bundle_dir=bundle_pair[0],
            projection_bundle_dir=bundle_pair[1],
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert raised.value.message == "Campaign publication cleanup failed"
    assert lock.exists()
    assert list(tmp_path.glob(".lock-cleanup-error.*")) == [lock]


def test_temporary_cleanup_error_is_not_silently_swallowed(monkeypatch, bundle_pair, tmp_path) -> None:
    target = tmp_path / "temporary-cleanup-error"

    monkeypatch.setattr(
        publication,
        "_publish_directory_no_replace",
        lambda *_args: (_ for _ in ()).throw(publication._PublicationRuntimeError("runtime")),
    )
    monkeypatch.setattr(service.shutil, "rmtree", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("raw rmtree")))
    with pytest.raises(CampaignError) as raised:
        create_campaign(
            target,
            world_bundle_dir=bundle_pair[0],
            projection_bundle_dir=bundle_pair[1],
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert raised.value.message == "Campaign publication cleanup failed"
    assert not target.exists()
    assert not publication.publication_lock_path(target).exists()
    assert list(tmp_path.glob(".temporary-cleanup-error.*"))


def test_late_target_is_preserved_and_owned_lock_is_removed(monkeypatch, bundle_pair, tmp_path) -> None:
    target = tmp_path / "campaign"
    original = publication._publish_directory_no_replace

    def appear_then_publish(source, destination):
        destination.mkdir()
        (destination / "marker.txt").write_text("preserve", encoding="utf-8")
        return original(source, destination)

    monkeypatch.setattr(publication, "_publish_directory_no_replace", appear_then_publish)
    with pytest.raises(CampaignError) as error:
        create_campaign(
            target,
            world_bundle_dir=bundle_pair[0],
            projection_bundle_dir=bundle_pair[1],
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
    assert error.value.code == "CAMPAIGN_ALREADY_EXISTS"
    assert (target / "marker.txt").read_text(encoding="utf-8") == "preserve"
    assert not publication.publication_lock_path(target).exists()
    assert not list(tmp_path.glob(".campaign.*"))


def test_cooperating_lock_race_is_preserved(monkeypatch, bundle_pair, tmp_path) -> None:
    target = tmp_path / "campaign"
    lock = publication.publication_lock_path(target)
    original_verify = __import__("tgn.campaign.service", fromlist=["verify_published_campaign"]).verify_published_campaign

    def verify_then_lock(root, *, bootstrap=False):
        result = original_verify(root, bootstrap=bootstrap)
        lock.write_bytes(b"other-writer")
        return result

    import tgn.campaign.service as service

    monkeypatch.setattr(service, "verify_published_campaign", verify_then_lock)
    with pytest.raises(CampaignError) as error:
        create_campaign(
            target,
            world_bundle_dir=bundle_pair[0],
            projection_bundle_dir=bundle_pair[1],
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
    assert error.value.code == "CAMPAIGN_ALREADY_EXISTS"
    assert lock.read_bytes() == b"other-writer"
    assert not target.exists()
    assert list(tmp_path.glob(".campaign.*")) == [lock]


def test_publication_lock_path_is_a_target_sibling(tmp_path) -> None:
    target = tmp_path / "campaign"
    assert publication.publication_lock_path(target) == tmp_path / ".campaign.publish.lock"
