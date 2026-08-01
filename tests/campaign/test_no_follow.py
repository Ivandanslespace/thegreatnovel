from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from tgn.campaign import CampaignError, create_campaign, verify_campaign
from tgn.campaign.publication import publication_lock_path


def _expect_integrity(callable_obj, *args) -> None:
    with pytest.raises(CampaignError) as raised:
        callable_obj(*args)
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def _replace_with_symlink(path: Path, target: Path, *, target_is_directory: bool) -> None:
    if os.path.lexists(str(path)):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    try:
        path.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation is unavailable on this platform: {type(exc).__name__}")


def test_campaign_root_symlink_is_rejected(campaign_factory, tmp_path: Path) -> None:
    target, _ = campaign_factory(name="root-link")
    outside = tmp_path / "outside-root"
    target.rename(outside)
    _replace_with_symlink(target, outside, target_is_directory=True)
    _expect_integrity(verify_campaign, target)


@pytest.mark.parametrize(
    ("relative", "target_name"),
    [
        ("campaign.json", "outside-campaign.json"),
        ("projection/player_projection.json", "outside-projection.json"),
        ("session/campaign.sqlite3", "outside-session.sqlite3"),
    ],
)
def test_campaign_file_symlinks_are_rejected(
    campaign_factory,
    tmp_path: Path,
    relative: str,
    target_name: str,
) -> None:
    target, _ = campaign_factory(name=f"file-link-{target_name}")
    linked = target / relative
    outside = tmp_path / target_name
    outside.write_bytes(linked.read_bytes())
    _replace_with_symlink(linked, outside, target_is_directory=False)
    _expect_integrity(verify_campaign, target)


@pytest.mark.parametrize("directory_name", ["world", "session"])
def test_campaign_directory_symlinks_are_rejected(campaign_factory, tmp_path: Path, directory_name: str) -> None:
    target, _ = campaign_factory(name=f"directory-link-{directory_name}")
    linked = target / directory_name
    outside = tmp_path / f"outside-{directory_name}"
    shutil.copytree(linked, outside)
    _replace_with_symlink(linked, outside, target_is_directory=True)
    _expect_integrity(verify_campaign, target)


def test_campaign_fifo_is_rejected_on_posix(campaign_factory) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("POSIX FIFO creation is unavailable on this platform")
    target, _ = campaign_factory(name="fifo-artifact")
    artifact = target / "world" / "world_request.json"
    artifact.unlink()
    try:
        os.mkfifo(artifact)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"POSIX FIFO creation is unavailable on this platform: {type(exc).__name__}")
    _expect_integrity(verify_campaign, target)


def test_external_symlinked_source_artifact_is_not_copied(bundle_pair, tmp_path: Path) -> None:
    world, projection = bundle_pair
    source = world / "world_request.json"
    outside = tmp_path / "outside-world-request.json"
    outside.write_bytes(source.read_bytes())
    _replace_with_symlink(source, outside, target_is_directory=False)
    target = tmp_path / "campaign"
    with pytest.raises(CampaignError) as raised:
        create_campaign(
            target,
            world_bundle_dir=world,
            projection_bundle_dir=projection,
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert not target.exists()
    assert not publication_lock_path(target).exists()
    assert not list(tmp_path.glob(".campaign.*"))
