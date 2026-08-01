from __future__ import annotations

from pathlib import Path

import pytest

import tgn.campaign.service as service
from tgn.campaign import CampaignError, CampaignService, create_campaign
from tgn.session import SessionError


def expect_error(callable_obj, *args, **kwargs) -> CampaignError:
    with pytest.raises(CampaignError) as error:
        callable_obj(*args, **kwargs)
    return error.value


def create_kwargs(target: Path, bundle_pair: tuple[Path, Path]) -> dict:
    return {
        "campaign_dir": target,
        "world_bundle_dir": bundle_pair[0],
        "projection_bundle_dir": bundle_pair[1],
        "campaign_id": "campaign-001",
        "actor_id": "player",
        "max_decisions": 10,
    }


def test_path_validation_rejects_non_path_objects(bundle_pair, tmp_path: Path) -> None:
    values = create_kwargs(tmp_path / "campaign", bundle_pair)
    values["campaign_dir"] = object()
    assert expect_error(create_campaign, **values).code == "INVALID_CAMPAIGN_INPUT"


def test_copied_source_result_becomes_authoritative(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    original = service.verify_external_pair
    call_count = 0

    def wrapper(world_root, projection_root):
        nonlocal call_count
        call_count += 1
        source, projection = original(world_root, projection_root)
        if call_count == 1:
            source = dict(source)
            source["external_observation"] = "not consumed"
        return source, projection

    monkeypatch.setattr(service, "verify_external_pair", wrapper)
    result = create_campaign(**create_kwargs(tmp_path / "campaign", bundle_pair))
    assert result["ok"] is True
    assert call_count == 2


def test_copied_projection_binding_race_fails_closed(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    original = service.verify_external_pair
    call_count = 0

    def wrapper(world_root, projection_root):
        nonlocal call_count
        call_count += 1
        source, projection = original(world_root, projection_root)
        if call_count == 2:
            projection = dict(projection)
            projection["source_initial_state_hash"] = "b" * 64
        return source, projection

    monkeypatch.setattr(service, "verify_external_pair", wrapper)
    error = expect_error(create_campaign, **create_kwargs(tmp_path / "campaign", bundle_pair))
    assert error.code == "PROJECTION_SOURCE_MISMATCH"
    assert not list(tmp_path.glob(".campaign.*"))


@pytest.mark.parametrize(
    "exception,expected",
    [
        (CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "wrapped"), "CAMPAIGN_INTEGRITY_MISMATCH"),
        (RuntimeError("raw"), "SESSION_BOOTSTRAP_FAILED"),
    ],
)
def test_session_bootstrap_exceptions_are_bounded(monkeypatch, bundle_pair, tmp_path: Path, exception, expected) -> None:
    def fail(*_args, **_kwargs):
        raise exception

    monkeypatch.setattr(service.frozen_session, "start_session", fail)
    error = expect_error(create_campaign, **create_kwargs(tmp_path / "campaign", bundle_pair))
    assert error.code == expected
    assert not list(tmp_path.glob(".campaign.*"))


def test_copied_world_hash_and_session_hash_bindings_fail(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    original = service.verify_external_pair

    def wrong_source(world_root, projection_root):
        source, projection = original(world_root, projection_root)
        source = dict(source)
        projection = dict(projection)
        source["worldpack_hash"] = "b" * 64
        projection["source_worldpack_hash"] = "b" * 64
        return source, projection

    monkeypatch.setattr(service, "verify_external_pair", wrong_source)
    error = expect_error(create_campaign, **create_kwargs(tmp_path / "world-hash", bundle_pair))
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(service, "verify_external_pair", original)
    monkeypatch.setattr(service, "_sqlite_initial_hash", lambda *_args: "b" * 64)
    error = expect_error(create_campaign, **create_kwargs(tmp_path / "session-hash", bundle_pair))
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_nested_bindings_and_projection_source_are_checked(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    monkeypatch.setattr(service.frozen_projection, "projection_hash", lambda _projection: "b" * 64)
    error = expect_error(create_campaign, **create_kwargs(tmp_path / "projection-hash", bundle_pair))
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.undo()
    original_loader = service.load_projection_map

    def altered_loader(root):
        projection, value = original_loader(root)
        value = dict(value)
        value["source_initial_state_hash"] = "b" * 64
        return projection, value

    monkeypatch.setattr(service, "load_projection_map", altered_loader)
    error = expect_error(create_campaign, **create_kwargs(tmp_path / "projection-source", bundle_pair))
    assert error.code == "PROJECTION_SOURCE_MISMATCH"


def test_target_appearing_before_locked_publication_is_preserved(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    target = tmp_path / "campaign"
    original = service.verify_published_campaign

    def verify_then_create_target(root, *, bootstrap=False):
        result = original(root, bootstrap=bootstrap)
        target.mkdir()
        (target / "marker.txt").write_text("preserved", encoding="utf-8")
        return result

    monkeypatch.setattr(service, "verify_published_campaign", verify_then_create_target)
    error = expect_error(create_campaign, **create_kwargs(target, bundle_pair))
    assert error.code == "CAMPAIGN_ALREADY_EXISTS"
    assert (target / "marker.txt").read_text(encoding="utf-8") == "preserved"
    assert not list(tmp_path.glob(".campaign.*"))


def test_publication_failure_is_mapped_and_cleaned(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    monkeypatch.setattr(
        service.publication,
        "_publish_directory_no_replace",
        lambda *_args: (_ for _ in ()).throw(service.publication._NoReplaceUnavailable("raw")),
    )
    error = expect_error(create_campaign, **create_kwargs(tmp_path / "unavailable", bundle_pair))
    assert error.code == "CAMPAIGN_PUBLICATION_UNAVAILABLE"
    assert not list(tmp_path.glob(".unavailable.*"))


def test_unexpected_creation_error_is_not_client_input(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    monkeypatch.setattr(service, "write_canonical_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("raw")))
    error = expect_error(create_campaign, **create_kwargs(tmp_path / "unexpected", bundle_pair))
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_lock_close_failure_is_bounded_and_cleaned(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    original_close = service.os.close

    def close_then_fail(fd):
        original_close(fd)
        raise OSError("raw close failure")

    monkeypatch.setattr(service.os, "close", close_then_fail)
    error = expect_error(create_campaign, **create_kwargs(tmp_path / "close-error", bundle_pair))
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert not (tmp_path / "close-error").exists()
    assert not list(tmp_path.glob(".close-error.*"))
    assert not service.publication.publication_lock_path(tmp_path / "close-error").exists()


def test_missing_owned_lock_is_already_cleaned(monkeypatch, bundle_pair, tmp_path: Path) -> None:
    target = tmp_path / "missing-lock"
    lock = service.publication.publication_lock_path(target)
    primitive_publish = service.publication._publish_directory_no_replace
    original_unlink = service.Path.unlink

    def publish_then_remove_lock(source, destination):
        result = primitive_publish(source, destination)

        def missing_lock(self, missing_ok=False):
            if self == lock:
                original_unlink(self, missing_ok=missing_ok)
                raise FileNotFoundError(lock)
            return original_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(service.Path, "unlink", missing_lock)
        return result

    monkeypatch.setattr(service.publication, "_publish_directory_no_replace", publish_then_remove_lock)
    result = create_campaign(**create_kwargs(target, bundle_pair))
    assert result["ok"] is True


def test_verified_session_error_maps_to_campaign_integrity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        service,
        "verify_published_campaign",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(SessionError("SESSION_NOT_FOUND", "raw")),
    )
    error = expect_error(CampaignService(tmp_path / "missing").next)
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_unexpected_published_session_operation_is_integrity_error(monkeypatch, campaign_factory) -> None:
    target, created = campaign_factory(name="unexpected-operation")
    monkeypatch.setattr(
        service.frozen_session,
        "choose_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("raw")),
    )
    error = expect_error(
        CampaignService(target).choose,
        request_fingerprint=created["canonical_request"]["request_fingerprint"],
        choice_id=created["canonical_request"]["choices"][0]["choice_id"],
    )
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(
        service.frozen_session,
        "stop_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("raw")),
    )
    error = expect_error(
        CampaignService(target).stop,
        request_fingerprint=created["canonical_request"]["request_fingerprint"],
    )
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"
