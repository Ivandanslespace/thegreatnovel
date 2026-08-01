from __future__ import annotations

from dataclasses import fields

import pytest

from tgn.campaign import CampaignError, CampaignManifest


HASH = "a" * 64
MANIFEST = {
    "schema_version": 1,
    "campaign_format_id": "phase9b2b-campaign-v1",
    "campaign_id": "campaign-001",
    "worldpack_hash": HASH,
    "source_initial_state_hash": HASH,
    "world_bundle_manifest_hash": HASH,
    "player_projection_hash": HASH,
    "projection_bundle_manifest_hash": HASH,
    "initial_request_fingerprint": HASH,
    "initial_presentation_hash": HASH,
    "session_id": "campaign-001",
    "actor_id": "player_1",
    "max_decisions": 20,
    "initial_session_state_hash": HASH,
}


def test_manifest_has_exact_scalar_contract() -> None:
    assert [field.name for field in fields(CampaignManifest)] == [
        "schema_version",
        "campaign_format_id",
        "campaign_id",
        "worldpack_hash",
        "source_initial_state_hash",
        "world_bundle_manifest_hash",
        "player_projection_hash",
        "projection_bundle_manifest_hash",
        "initial_request_fingerprint",
        "initial_presentation_hash",
        "session_id",
        "actor_id",
        "max_decisions",
        "initial_session_state_hash",
    ]
    manifest = CampaignManifest.from_dict(MANIFEST)
    assert manifest.to_dict() == MANIFEST
    with pytest.raises((AttributeError, TypeError)):
        manifest.campaign_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "change",
    [
        {"extra": True},
        {"campaign_id": "Bad"},
        {"session_id": "different"},
        {"max_decisions": True},
        {"max_decisions": 0},
        {"worldpack_hash": HASH.upper()},
        {"schema_version": 2},
        {"campaign_format_id": "phase9c"},
    ],
)
def test_manifest_rejects_non_contract_values(change: dict[str, object]) -> None:
    payload = dict(MANIFEST)
    if "extra" in change:
        payload["extra"] = True
    else:
        payload.update(change)
    expected = (
        "UNSUPPORTED_CAMPAIGN_FORMAT"
        if change.get("schema_version") == 2 or change.get("campaign_format_id") == "phase9c"
        else "CAMPAIGN_INTEGRITY_MISMATCH"
    )
    with pytest.raises(CampaignError) as error:
        CampaignManifest.from_dict(payload)
    assert error.value.code == expected


def test_manifest_to_dict_does_not_expose_mutable_nested_state() -> None:
    manifest = CampaignManifest.from_dict(MANIFEST)
    first = manifest.to_dict()
    first["campaign_id"] = "changed"
    assert manifest.campaign_id == "campaign-001"
    assert manifest.to_dict()["campaign_id"] == "campaign-001"


def test_campaign_error_is_stable_and_safe() -> None:
    error = CampaignError("NOT_A_PUBLIC_CODE", "line 1\nline 2\ud800")
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert "\n" not in error.message
    assert "\ud800" not in error.message
    assert error.to_dict()["code"] == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_manifest_constructor_type_errors_are_wrapped(monkeypatch) -> None:
    original = CampaignManifest.__post_init__
    monkeypatch.setattr(
        CampaignManifest,
        "__post_init__",
        lambda _self: (_ for _ in ()).throw(TypeError("raw constructor detail")),
    )
    with pytest.raises(CampaignError) as error:
        CampaignManifest.from_dict(MANIFEST)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    monkeypatch.setattr(CampaignManifest, "__post_init__", original)
