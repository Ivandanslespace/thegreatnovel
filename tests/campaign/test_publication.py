from __future__ import annotations

import errno
import os

import pytest

import tgn.campaign.publication as publication
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
    with pytest.raises(publication._NoReplaceUnavailable):
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
    with pytest.raises(publication._NoReplaceUnavailable):
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
    with pytest.raises(publication._NoReplaceUnavailable):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")
    monkeypatch.setattr(publication.sys, "platform", "freebsd")
    with pytest.raises(publication._NoReplaceUnavailable):
        publication._publish_directory_no_replace(tmp_path / "temporary", tmp_path / "target")


def test_capability_preflight_unavailable_has_no_side_effect(monkeypatch, bundle_pair, tmp_path) -> None:
    def unavailable():
        raise publication._NoReplaceUnavailable("unsupported")

    monkeypatch.setattr(publication, "assert_publication_capability", unavailable)
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
