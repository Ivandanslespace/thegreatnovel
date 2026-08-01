from __future__ import annotations

import json
from pathlib import Path

import pytest

from tgn.campaign import CampaignError, create_campaign
from tgn.campaign import service as campaign_service
from tgn.campaign import verification
from tgn.session import SessionError

from .conftest import make_projection_bundle, make_world_bundle


EXPECTED_FILES = {
    "campaign.json",
    "world/bundle.json",
    "world/world_request.json",
    "world/world_draft.json",
    "world/compiled_worldpack.json",
    "world/initial_state.json",
    "world/compile_report.json",
    "projection/projection_manifest.json",
    "projection/projection_draft.json",
    "projection/player_projection.json",
    "projection/projection_report.json",
    "session/campaign.sqlite3",
    "session/session.json",
    "session/recorded_decisions.json",
}


def _error_code(callable_obj, *args, **kwargs) -> str:
    with pytest.raises(CampaignError) as error:
        callable_obj(*args, **kwargs)
    return error.value.code


def test_create_publishes_exact_fourteen_files_and_bindings(campaign_factory) -> None:
    target, result = campaign_factory()
    files = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }
    assert files == EXPECTED_FILES
    assert len(files) == 14
    assert result["ok"] is True
    assert result["campaign"]["session_id"] == result["campaign"]["campaign_id"]
    assert result["canonical_request"]["decision_number"] == 1
    assert result["player_presentation"]["request_fingerprint"] == result["campaign"]["initial_request_fingerprint"]

    campaign = json.loads((target / "campaign.json").read_text(encoding="utf-8"))
    world_manifest = json.loads((target / "world/bundle.json").read_text(encoding="utf-8"))
    projection_manifest = json.loads(
        (target / "projection/projection_manifest.json").read_text(encoding="utf-8")
    )
    assert campaign["worldpack_hash"] == world_manifest["worldpack_hash"]
    assert campaign["source_initial_state_hash"] == world_manifest["initial_state_hash"]
    assert campaign["source_initial_state_hash"] == campaign["initial_session_state_hash"]
    assert projection_manifest["source_worldpack_hash"] == campaign["worldpack_hash"]
    assert projection_manifest["source_initial_state_hash"] == campaign["source_initial_state_hash"]


def test_create_verifies_source_before_projection(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    world, projection = bundle_pair
    calls: list[str] = []
    original_source = verification.verify_bundle
    original_projection = verification.verify_projection_bundle

    def source(*args, **kwargs):
        calls.append("source")
        return original_source(*args, **kwargs)

    def projected(*args, **kwargs):
        calls.append("projection")
        return original_projection(*args, **kwargs)

    monkeypatch.setattr(verification, "verify_bundle", source)
    monkeypatch.setattr(verification, "verify_projection_bundle", projected)
    create_campaign(
        tmp_path / "campaign",
        world_bundle_dir=world,
        projection_bundle_dir=projection,
        campaign_id="campaign-001",
        actor_id="player",
        max_decisions=10,
    )
    assert calls[:2] == ["source", "projection"]


def test_cross_bound_projection_rejected_before_session_creation(bundle_pair, tmp_path: Path) -> None:
    world, projection = bundle_pair
    other_world = make_world_bundle(tmp_path, name="other-world", seed="other-seed")
    other_projection = make_projection_bundle(tmp_path, other_world, name="other-projection")
    target = tmp_path / "campaign"
    code = _error_code(
        create_campaign,
        target,
        world_bundle_dir=world,
        projection_bundle_dir=other_projection,
        campaign_id="campaign-001",
        actor_id="player",
        max_decisions=10,
    )
    assert code == "PROJECTION_SOURCE_MISMATCH"
    assert not target.exists()
    assert not (tmp_path / ".campaign.publish.lock").exists()
    assert not list(tmp_path.glob(".campaign.*"))
    assert projection.exists()


def test_external_change_after_verification_fails_closed_and_cleans_temporary(
    monkeypatch, bundle_pair, tmp_path: Path
) -> None:
    world, projection = bundle_pair
    original = campaign_service.verify_external_pair
    changed = False

    def verify_then_change(world_root, projection_root):
        nonlocal changed
        result = original(world_root, projection_root)
        if not changed and Path(world_root) == world:
            changed = True
            path = world / "initial_state.json"
            path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        return result

    monkeypatch.setattr(campaign_service, "verify_external_pair", verify_then_change)
    code = _error_code(
        create_campaign,
        tmp_path / "campaign",
        world_bundle_dir=world,
        projection_bundle_dir=projection,
        campaign_id="campaign-001",
        actor_id="player",
        max_decisions=10,
    )
    assert code in {"SOURCE_BUNDLE_INVALID", "CAMPAIGN_INTEGRITY_MISMATCH"}
    assert changed
    assert not (tmp_path / "campaign").exists()
    assert not list(tmp_path.glob(".campaign.*"))
    assert not (tmp_path / ".campaign.publish.lock").exists()


def test_session_bootstrap_failure_has_no_formal_target_or_debris(
    monkeypatch, bundle_pair, tmp_path: Path
) -> None:
    def fail(*args, **kwargs):
        raise SessionError("INVALID_INITIAL_STATE", "internal details are hidden")

    monkeypatch.setattr(campaign_service.frozen_session, "start_session", fail)
    code = _error_code(
        create_campaign,
        tmp_path / "campaign",
        world_bundle_dir=bundle_pair[0],
        projection_bundle_dir=bundle_pair[1],
        campaign_id="campaign-001",
        actor_id="player",
        max_decisions=10,
    )
    assert code == "SESSION_BOOTSTRAP_FAILED"
    assert not (tmp_path / "campaign").exists()
    assert not list(tmp_path.glob(".campaign.*"))
    assert not (tmp_path / ".campaign.publish.lock").exists()


def test_invalid_create_input_is_zero_side_effect(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    called = False

    def unavailable():
        nonlocal called
        called = True
        raise AssertionError("capability preflight must follow input validation")

    monkeypatch.setattr(campaign_service.publication, "assert_publication_capability", unavailable)
    target = tmp_path / "campaign"
    code = _error_code(
        create_campaign,
        target,
        world_bundle_dir=bundle_pair[0],
        projection_bundle_dir=bundle_pair[1],
        campaign_id="Bad ID",
        actor_id="player",
        max_decisions=True,
    )
    assert code == "INVALID_CAMPAIGN_INPUT"
    assert not called
    assert not target.exists()
    assert not (tmp_path / ".campaign.publish.lock").exists()
    assert not list(tmp_path.glob(".campaign.*"))


@pytest.mark.parametrize("kind", ["target", "empty-target", "lock"])
def test_existing_target_or_lock_is_preserved(kind: str, campaign_factory, tmp_path: Path) -> None:
    if kind == "target":
        target, _ = campaign_factory()
        before = (target / "campaign.json").read_bytes()
        code = _error_code(
            create_campaign,
            target,
            world_bundle_dir=tmp_path / "missing-world",
            projection_bundle_dir=tmp_path / "missing-projection",
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
        assert code == "CAMPAIGN_ALREADY_EXISTS"
        assert (target / "campaign.json").read_bytes() == before
    elif kind == "empty-target":
        target = tmp_path / "campaign"
        target.mkdir()
        code = _error_code(
            create_campaign,
            target,
            world_bundle_dir=tmp_path / "missing-world",
            projection_bundle_dir=tmp_path / "missing-projection",
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
        assert code == "CAMPAIGN_ALREADY_EXISTS"
        assert target.is_dir() and not list(target.iterdir())
    else:
        target = tmp_path / "campaign"
        lock = tmp_path / ".campaign.publish.lock"
        lock.write_bytes(b"cooperating")
        code = _error_code(
            create_campaign,
            target,
            world_bundle_dir=tmp_path / "missing-world",
            projection_bundle_dir=tmp_path / "missing-projection",
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
        assert code == "CAMPAIGN_ALREADY_EXISTS"
        assert lock.read_bytes() == b"cooperating"
