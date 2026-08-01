from __future__ import annotations

import copy

import pytest

import tgn.campaign.verification as verification
from tgn.campaign import CampaignError, verify_campaign
from tgn.session import SessionError


def expect_error(callable_obj, *args, **kwargs) -> CampaignError:
    with pytest.raises(CampaignError) as error:
        callable_obj(*args, **kwargs)
    return error.value


def test_projection_object_source_binding_is_checked(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="map-source-binding")
    original = verification.load_projection_map

    def altered(root):
        projection, value = original(root)
        altered_projection = type(projection)(
            schema_version=projection.schema_version,
            projection_compiler_id=projection.projection_compiler_id,
            mechanics_profile=projection.mechanics_profile,
            source_worldpack_hash="b" * 64,
            source_initial_state_hash=projection.source_initial_state_hash,
            content_locale=projection.content_locale,
            world=projection.world,
            identities=projection.identities,
        )
        return altered_projection, value

    monkeypatch.setattr(verification, "load_projection_map", altered)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_projection_hash_and_world_artifact_hash_are_recomputed(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="hash-recompute")
    monkeypatch.setattr(verification, "projection_hash", lambda _projection: "b" * 64)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.undo()
    original_hash = verification.sha256_json

    def wrong_world_hash(value):
        if isinstance(value, dict) and "runtime_bindings" in value:
            return "b" * 64
        return original_hash(value)

    monkeypatch.setattr(verification, "sha256_json", wrong_world_hash)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("kind", ["worldgen", "runtime"])
def test_copied_public_verifier_failures_are_campaign_integrity(monkeypatch, campaign_factory, kind: str) -> None:
    target, _ = campaign_factory(name=f"public-verifier-{kind}")
    if kind == "worldgen":
        from tgn.worldgen.models import WorldGenError

        monkeypatch.setattr(verification, "verify_bundle", lambda _root: (_ for _ in ()).throw(WorldGenError("BAD", "raw")))
    else:
        monkeypatch.setattr(verification, "verify_bundle", lambda _root: (_ for _ in ()).throw(RuntimeError("raw")))
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("exception", ["worldgen", "runtime"])
def test_copied_projection_verifier_failures_are_campaign_integrity(monkeypatch, campaign_factory, exception: str) -> None:
    target, _ = campaign_factory(name=f"projection-verifier-{exception}")
    if exception == "worldgen":
        from tgn.worldgen.models import WorldGenError

        failure = WorldGenError("BAD", "raw")
    else:
        failure = RuntimeError("raw")
    monkeypatch.setattr(
        verification,
        "verify_projection_bundle",
        lambda *_args: (_ for _ in ()).throw(failure),
    )
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_copied_verification_summaries_are_bound(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="summary-bindings")
    original_source = verification.verify_bundle
    original_projection = verification.verify_projection_bundle

    def wrong_source(root):
        value = dict(original_source(root))
        value["worldpack_hash"] = "b" * 64
        return value

    monkeypatch.setattr(verification, "verify_bundle", wrong_source)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification, "verify_bundle", original_source)

    def wrong_projection(*args):
        value = dict(original_projection(*args))
        value["projection_hash"] = "b" * 64
        return value

    monkeypatch.setattr(verification, "verify_projection_bundle", wrong_projection)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_session_summary_and_replay_completion_bindings(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="session-summary")
    original_session_verify = verification.verify_session

    def wrong_summary(root):
        value = copy.deepcopy(original_session_verify(root))
        value["session"]["actor_id"] = "other"
        return value

    monkeypatch.setattr(verification, "verify_session", wrong_summary)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification, "verify_session", original_session_verify)

    def completion_call(root):
        value = copy.deepcopy(original_session_verify(root))
        value["verification"]["recorded_decision_replay_completion_calls"] = 1
        return value

    monkeypatch.setattr(verification, "verify_session", completion_call)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    def incomplete(root):
        value = copy.deepcopy(original_session_verify(root))
        value["verification"]["event_replay"] = False
        return value

    monkeypatch.setattr(verification, "verify_session", incomplete)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_current_request_binding_and_unexpected_error_are_closed(monkeypatch, campaign_factory) -> None:
    target, _ = campaign_factory(name="current-request")
    original_session_verify = verification.verify_session
    original_next = verification.next_session

    def wrong_current(root):
        value = copy.deepcopy(original_session_verify(root))
        value["session"]["current_request_fingerprint"] = "b" * 64
        return value

    monkeypatch.setattr(verification, "verify_session", wrong_current)
    assert expect_error(verify_campaign, target).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    monkeypatch.setattr(verification, "verify_session", original_session_verify)

    def raises(*_args, **_kwargs):
        raise TypeError("raw presentation detail")

    monkeypatch.setattr(verification, "build_player_presentation", raises)
    error = expect_error(verify_campaign, target)
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert "raw presentation" not in error.message
