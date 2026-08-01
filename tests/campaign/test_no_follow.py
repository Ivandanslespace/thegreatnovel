from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tgn.campaign import CampaignError, create_campaign, verify_campaign
import tgn.campaign.common as common
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


def test_copy_path_does_not_use_shutil_copyfile(bundle_pair, tmp_path: Path, monkeypatch) -> None:
    def fail_copyfile(*_args, **_kwargs):
        raise AssertionError("shutil.copyfile must not be used")

    monkeypatch.setattr(common.shutil, "copyfile", fail_copyfile)
    result = create_campaign(
        tmp_path / "descriptor-copy",
        world_bundle_dir=bundle_pair[0],
        projection_bundle_dir=bundle_pair[1],
        campaign_id="campaign-001",
        actor_id="player",
        max_decisions=10,
    )
    assert result["ok"] is True


def test_source_replaced_by_symlink_between_check_and_open_fails_closed(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / "artifact.json"
    replacement = tmp_path / "replacement.json"
    source.write_bytes(b"source")
    replacement.write_bytes(b"replacement")
    destination_root = tmp_path / "destination"
    original_open = common.os.open
    replaced = False

    def replace_before_open(path, flags, *args):
        nonlocal replaced
        if Path(path) == source and not replaced:
            replaced = True
            source.rename(tmp_path / "original.json")
            source.symlink_to(replacement)
        return original_open(path, flags, *args)

    monkeypatch.setattr(common.os, "open", replace_before_open)
    with pytest.raises(CampaignError) as raised:
        common.copy_files(source_root, destination_root, ["artifact.json"])
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert "raw" not in raised.value.message


def test_source_replaced_by_regular_file_between_check_and_open_fails_closed(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / "artifact.json"
    replacement = tmp_path / "replacement.json"
    source.write_bytes(b"source")
    replacement.write_bytes(b"replacement")
    destination_root = tmp_path / "destination"
    original_open = common.os.open
    replaced = False

    def replace_before_open(path, flags, *args):
        nonlocal replaced
        if Path(path) == source and not replaced:
            replaced = True
            os.replace(replacement, source)
        return original_open(path, flags, *args)

    monkeypatch.setattr(common.os, "open", replace_before_open)
    with pytest.raises(CampaignError) as raised:
        common.copy_files(source_root, destination_root, ["artifact.json"])
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_source_replaced_after_open_before_final_identity_check_fails_closed(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / "artifact.json"
    replacement = tmp_path / "replacement.json"
    source.write_bytes(b"source")
    replacement.write_bytes(b"replacement")
    destination_root = tmp_path / "destination"
    original_fstat = common.os.fstat
    replaced = False

    def replace_after_open(fd):
        nonlocal replaced
        result = original_fstat(fd)
        if not replaced:
            replaced = True
            os.replace(replacement, source)
        return result

    monkeypatch.setattr(common.os, "fstat", replace_after_open)
    with pytest.raises(CampaignError) as raised:
        common.copy_files(source_root, destination_root, ["artifact.json"])
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_copy_identity_fallback_handles_platform_without_identity() -> None:
    class NoIdentity:
        pass

    assert common._file_identity(NoIdentity()) is None


def test_copy_rejects_identity_change_after_open(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "artifact.json").write_bytes(b"source")
    identities = iter([(1, 1), (1, 1), (2, 2)])
    monkeypatch.setattr(common, "_file_identity", lambda _stat_result: next(identities))
    with pytest.raises(CampaignError) as raised:
        common.copy_files(source_root, tmp_path / "destination", ["artifact.json"])
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_descriptor_copy_rejects_zero_progress_write(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "artifact.json").write_bytes(b"source")
    monkeypatch.setattr(common.os, "write", lambda *_args, **_kwargs: 0)
    with pytest.raises(CampaignError) as raised:
        common.copy_files(source_root, tmp_path / "destination", ["artifact.json"])
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_descriptor_copy_destination_directory_failure_is_bounded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(common.Path, "mkdir", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("raw mkdir")))
    with pytest.raises(CampaignError) as raised:
        common.copy_files(tmp_path, tmp_path / "destination", ["artifact.json"])
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert "raw" not in raised.value.message


def test_existing_destination_is_not_overwritten(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    source_root.mkdir()
    destination_root.mkdir()
    (source_root / "artifact.json").write_bytes(b"new")
    destination = destination_root / "artifact.json"
    destination.write_bytes(b"old")
    with pytest.raises(CampaignError) as raised:
        common.copy_files(source_root, destination_root, ["artifact.json"])
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert destination.read_bytes() == b"old"


def test_copy_fifo_source_is_rejected_on_posix(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("POSIX FIFO creation is unavailable on this platform")
    source_root = tmp_path / "source"
    source_root.mkdir()
    try:
        os.mkfifo(source_root / "artifact.json")
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"POSIX FIFO creation is unavailable on this platform: {type(exc).__name__}")
    with pytest.raises(CampaignError) as raised:
        common.copy_files(source_root, tmp_path / "destination", ["artifact.json"])
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("operation", ["open", "read", "write", "close"])
def test_descriptor_copy_io_failures_are_bounded(tmp_path: Path, monkeypatch, operation: str) -> None:
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    source_root.mkdir()
    (source_root / "artifact.json").write_bytes(b"source")
    original = getattr(common.os, operation)

    if operation == "open":
        def fail(*_args, **_kwargs):
            raise RuntimeError("raw open")
        monkeypatch.setattr(common.os, "open", fail)
    elif operation == "read":
        def fail(*_args, **_kwargs):
            raise RuntimeError("raw read")
        monkeypatch.setattr(common.os, "read", fail)
    elif operation == "write":
        def fail(*_args, **_kwargs):
            raise RuntimeError("raw write")
        monkeypatch.setattr(common.os, "write", fail)
    else:
        def close_then_fail(fd):
            original(fd)
            raise RuntimeError("raw close")
        monkeypatch.setattr(common.os, "close", close_then_fail)

    with pytest.raises(CampaignError) as raised:
        common.copy_files(source_root, destination_root, ["artifact.json"])
    assert raised.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert "raw" not in raised.value.message


def _make_directory_junction(link: Path, target: Path) -> None:
    try:
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Windows junction creation is unavailable: {type(exc).__name__}")
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "junction creation failed").strip()
        pytest.skip(f"Windows junction creation is unavailable: {detail[:120]}")


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junctions are unavailable on this platform")
@pytest.mark.parametrize("relative", [".", "world", "session"])
def test_windows_directory_junctions_are_rejected(
    campaign_factory,
    tmp_path: Path,
    relative: str,
) -> None:
    target, _ = campaign_factory(name=f"junction-{relative.replace('.', 'root')}")
    linked = target if relative == "." else target / relative
    outside = tmp_path / f"outside-{relative.replace('.', 'root')}"
    linked.rename(outside)
    _make_directory_junction(linked, outside)
    _expect_integrity(verify_campaign, target)
