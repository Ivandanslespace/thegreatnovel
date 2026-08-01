from __future__ import annotations

import copy
from pathlib import Path

import pytest

import tgn.campaign.verification as verification
from tgn.campaign import CampaignError
from tgn.campaign.common import read_canonical_json, write_canonical_json
from tgn.projection import PlayerProjectionMap
from tgn.session import SessionError
from tgn.worldgen.models import WorldGenError


def expect_error(callable_obj, *args, **kwargs) -> CampaignError:
    with pytest.raises(CampaignError) as error:
        callable_obj(*args, **kwargs)
    return error.value


def test_projection_manifest_and_map_loader_error_shapes(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="projection-loader")
    manifest_path = target / "projection" / "projection_manifest.json"
    original = read_canonical_json(manifest_path)
    extra = dict(original)
    extra["extra"] = True
    write_canonical_json(manifest_path, extra)
    assert expect_error(verification.load_projection_manifest, target / "projection").code == "CAMPAIGN_INTEGRITY_MISMATCH"
    write_canonical_json(manifest_path, original)
    bad = dict(original)
    bad["player_projection_hash"] = "BAD"
    write_canonical_json(manifest_path, bad)
    assert expect_error(verification.load_projection_manifest, target / "projection").code == "CAMPAIGN_INTEGRITY_MISMATCH"
    write_canonical_json(manifest_path, original)

    original_loader = verification.PlayerProjectionMap
    monkeypatch.setattr(verification, "PlayerProjectionMap", lambda **_kwargs: (_ for _ in ()).throw(ValueError("bad map")))
    assert expect_error(verification.load_projection_map, target / "projection").code == "CAMPAIGN_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification, "PlayerProjectionMap", original_loader)

    projection_path = target / "projection" / "player_projection.json"
    projection_value = read_canonical_json(projection_path)
    projection_value.pop("world")
    write_canonical_json(projection_path, projection_value)
    assert expect_error(verification.load_projection_map, target / "projection").code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_external_verification_error_mapping(monkeypatch, bundle_pair) -> None:
    original_manifest_loader = verification.load_projection_manifest
    def source_worldgen_error(_root):
        raise WorldGenError("INVALID_BUNDLE", "raw")

    monkeypatch.setattr(verification, "verify_bundle", source_worldgen_error)
    assert expect_error(verification.verify_external_pair, bundle_pair[0], bundle_pair[1]).code == "SOURCE_BUNDLE_INVALID"

    def source_runtime_error(_root):
        raise RuntimeError("raw")

    monkeypatch.setattr(verification, "verify_bundle", source_runtime_error)
    assert expect_error(verification.verify_external_pair, bundle_pair[0], bundle_pair[1]).code == "SOURCE_BUNDLE_INVALID"

    # Restore source verification and exercise projection manifest / verifier failures.
    import tgn.worldgen as worldgen

    monkeypatch.setattr(verification, "verify_bundle", worldgen.verify_bundle)
    monkeypatch.setattr(verification, "load_projection_manifest", lambda _root: (_ for _ in ()).throw(CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "bad")))
    assert expect_error(verification.verify_external_pair, bundle_pair[0], bundle_pair[1]).code == "PROJECTION_BUNDLE_INVALID"

    from tgn.projection import verify_projection_bundle

    monkeypatch.setattr(verification, "load_projection_manifest", original_manifest_loader)
    monkeypatch.setattr(verification, "verify_projection_bundle", lambda *_args: (_ for _ in ()).throw(WorldGenError("BAD", "raw")))
    assert expect_error(verification.verify_external_pair, bundle_pair[0], bundle_pair[1]).code == "PROJECTION_BUNDLE_INVALID"
    monkeypatch.setattr(verification, "verify_projection_bundle", lambda *_args: (_ for _ in ()).throw(RuntimeError("raw")))
    assert expect_error(verification.verify_external_pair, bundle_pair[0], bundle_pair[1]).code == "PROJECTION_BUNDLE_INVALID"


def test_request_reconstruction_rejects_each_serialized_shape(campaign_factory, monkeypatch) -> None:
    target, created = campaign_factory(name="request-shapes")
    request = created["canonical_request"]
    assert expect_error(verification.reconstruct_request, {"wrong": True}).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    no_legal = copy.deepcopy(request)
    no_legal["observation"]["legal_actions"] = []
    assert expect_error(verification.reconstruct_request, no_legal).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    extra_choice = copy.deepcopy(request)
    extra_choice["choices"][0]["extra"] = True
    assert expect_error(verification.reconstruct_request, extra_choice).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    invalid_choice = copy.deepcopy(request)
    invalid_choice["choices"][0]["duration_minutes"] = "five"
    assert expect_error(verification.reconstruct_request, invalid_choice).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(verification, "build_llm_decision_request", lambda *_args: (_ for _ in ()).throw(ValueError("raw")))
    assert expect_error(verification.reconstruct_request, request).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert target.exists()


def test_initial_request_and_artifact_read_fail_closed(monkeypatch, campaign_factory, tmp_path: Path) -> None:
    target, _ = campaign_factory(name="initial-error")
    initial = target / "world" / "initial_state.json"
    initial.write_text("{}", encoding="utf-8")
    assert expect_error(verification._build_initial_request, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert expect_error(verification._artifact_hashes, target / "missing").code == "CAMPAIGN_INTEGRITY_MISMATCH"



def test_session_error_mapping_is_stable() -> None:
    for code in ("STALE_REQUEST", "UNKNOWN_CHOICE", "SESSION_TERMINAL"):
        mapped = verification._map_session_error(SessionError(code, "raw detail"), bootstrap=False)
        assert mapped.code == code
    assert verification._map_session_error(SessionError("INVALID_INITIAL_STATE", "raw"), bootstrap=True).code == "SESSION_BOOTSTRAP_FAILED"
    assert verification._map_session_error(SessionError("SESSION_NOT_FOUND", "raw"), bootstrap=False).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_published_verification_late_bindings_are_checked(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="late-bindings")
    original_read = verification.read_canonical_json
    original_manifest_loader = verification.load_projection_manifest

    def altered_world_manifest(path):
        value = original_read(path)
        if str(path).endswith("world\\bundle.json") or str(path).endswith("world/bundle.json"):
            value = dict(value)
            value["worldpack_hash"] = "b" * 64
        return value

    monkeypatch.setattr(verification, "read_canonical_json", altered_world_manifest)
    assert expect_error(verification.verify_published_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification, "read_canonical_json", original_read)

    def altered_projection_manifest(path):
        value = original_manifest_loader(path)
        if str(path).endswith("projection"):
            value = dict(value)
            value["source_worldpack_hash"] = "b" * 64
        return value

    monkeypatch.setattr(verification, "load_projection_manifest", altered_projection_manifest)
    assert expect_error(verification.verify_published_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification, "load_projection_manifest", original_manifest_loader)

    def altered_projection_hash_manifest(path):
        value = original_manifest_loader(path)
        if str(path).endswith("projection"):
            value = dict(value)
            value["player_projection_hash"] = "b" * 64
        return value

    monkeypatch.setattr(verification, "load_projection_manifest", altered_projection_hash_manifest)
    assert expect_error(verification.verify_published_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification, "load_projection_manifest", original_manifest_loader)
