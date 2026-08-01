from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tgn.campaign import CampaignError, CampaignService, choose_campaign, next_campaign, verify_campaign

from .conftest import choice_for, make_projection_bundle, make_world_bundle, world_draft


def choose_action(target: Path, action_type: str) -> dict:
    current = next_campaign(target)
    choice = choice_for(current["canonical_request"], action_type)
    return choose_campaign(
        target,
        request_fingerprint=current["canonical_request"]["request_fingerprint"],
        choice_id=choice["choice_id"],
    )


def event_rows(target: Path) -> tuple[tuple, ...]:
    connection = sqlite3.connect(target / "session" / "campaign.sqlite3")
    try:
        return tuple(
            connection.execute(
                "SELECT event_seq, decision_seq, event_type, actor_id, action_id, "
                "payload_json, state_hash_before, state_hash_after "
                "FROM events ORDER BY event_seq"
            )
        )
    finally:
        connection.close()


def test_label_independence_preserves_canonical_path(campaign_factory, tmp_path: Path) -> None:
    # Reuse the fixture's source, while compiling a second matching sidecar with new labels.
    # The explicit fixture arguments below keep the test independent of presentation text.
    base_world = make_world_bundle(tmp_path, name="label-world")
    projection_a = make_projection_bundle(tmp_path, base_world, name="projection-a", suffix="A")
    projection_b = make_projection_bundle(tmp_path, base_world, name="projection-b", suffix="B")
    from tgn.campaign import create_campaign

    target_a = tmp_path / "campaign-a"
    target_b = tmp_path / "campaign-b"
    create_campaign(
        target_a,
        world_bundle_dir=base_world,
        projection_bundle_dir=projection_a,
        campaign_id="campaign-001",
        actor_id="player",
        max_decisions=10,
    )
    create_campaign(
        target_b,
        world_bundle_dir=base_world,
        projection_bundle_dir=projection_b,
        campaign_id="campaign-001",
        actor_id="player",
        max_decisions=10,
    )
    initial_a = next_campaign(target_a)
    initial_b = next_campaign(target_b)
    assert initial_a["campaign"]["worldpack_hash"] == initial_b["campaign"]["worldpack_hash"]
    assert initial_a["campaign"]["source_initial_state_hash"] == initial_b["campaign"]["source_initial_state_hash"]
    assert initial_a["campaign"]["initial_request_fingerprint"] == initial_b["campaign"]["initial_request_fingerprint"]
    assert initial_a["campaign"]["player_projection_hash"] != initial_b["campaign"]["player_projection_hash"]
    assert initial_a["campaign"]["initial_presentation_hash"] != initial_b["campaign"]["initial_presentation_hash"]
    assert initial_a["canonical_request"] == initial_b["canonical_request"]
    assert initial_a["player_presentation"]["observation"] != initial_b["player_presentation"]["observation"]

    result_a = choose_action(target_a, "DROP")
    result_b = choose_action(target_b, "DROP")
    assert result_a["result"] == result_b["result"]
    assert event_rows(target_a) == event_rows(target_b)
    assert verify_campaign(target_a)["verification"]["event_replay"] is True
    assert verify_campaign(target_b)["verification"]["event_replay"] is True


def test_theme_locale_independence_keeps_mechanics_and_changes_public_content(tmp_path: Path) -> None:
    world_a = make_world_bundle(tmp_path, name="world-a", seed="same-seed")
    world_b = make_world_bundle(
        tmp_path,
        name="world-b",
        seed="same-seed",
        draft=world_draft(
            world_id="ice-train",
            locale="fr",
            title="Train de glace",
            premise="Un train traverse un glacier.",
        ),
    )
    projection_a = make_projection_bundle(tmp_path, world_a, name="projection-a")
    projection_b = make_projection_bundle(tmp_path, world_b, name="projection-b")
    from tgn.campaign import create_campaign

    target_a = tmp_path / "campaign-a"
    target_b = tmp_path / "campaign-b"
    for target, world, projection in ((target_a, world_a, projection_a), (target_b, world_b, projection_b)):
        create_campaign(
            target,
            world_bundle_dir=world,
            projection_bundle_dir=projection,
            campaign_id="campaign-001",
            actor_id="player",
            max_decisions=10,
        )
    initial_a = next_campaign(target_a)
    initial_b = next_campaign(target_b)
    assert initial_a["campaign"]["worldpack_hash"] != initial_b["campaign"]["worldpack_hash"]
    assert initial_a["campaign"]["source_initial_state_hash"] == initial_b["campaign"]["source_initial_state_hash"]
    assert initial_a["canonical_request"] == initial_b["canonical_request"]
    assert initial_a["player_presentation"]["world"] != initial_b["player_presentation"]["world"]
    assert choose_action(target_a, "DROP")["result"] == choose_action(target_b, "DROP")["result"]
    assert event_rows(target_a) == event_rows(target_b)

    with pytest.raises(CampaignError) as error:
        create_campaign(
            tmp_path / "cross-pair",
            world_bundle_dir=world_a,
            projection_bundle_dir=projection_b,
            campaign_id="cross-pair",
            actor_id="player",
            max_decisions=10,
        )
    assert error.value.code == "PROJECTION_SOURCE_MISMATCH"


def test_knowledge_boundary_before_and_after_legitimate_talk(campaign_factory) -> None:
    target, _ = campaign_factory()
    for action in ("DROP", "SEARCH", "EXTRACT"):
        current = next_campaign(target)
        observation = current["canonical_request"]["observation"]
        presentation_observation = current["player_presentation"]["observation"]
        assert "site-1-condition" not in observation.get("actor", {}).get("facts", {})
        assert "site-1-condition" not in presentation_observation.get("actor", {}).get("facts", {})
        assert "knowledge" not in observation.get("actor", {})
        choose_action(target, action)

    before_talk = next_campaign(target)
    assert "site-1-condition" not in before_talk["canonical_request"]["observation"]["actor"]["facts"]
    assert "site-1-condition" not in before_talk["player_presentation"]["observation"]["actor"]["facts"]
    talk_result = choose_action(target, "TALK_TO_ACTOR")
    assert talk_result["result"]["event_type"] == "ACTOR_CONVERSATION_RESOLVED"
    after_talk = next_campaign(target)
    assert after_talk["canonical_request"]["observation"]["actor"]["facts"]["site-1-condition"] == "unstable"
    assert after_talk["player_presentation"]["observation"]["actor"]["facts"]["site-1-condition"]["value"] == "unstable"
    assert "last_autonomous_action" not in after_talk["player_presentation"]["observation"]


def test_close_reopen_resume_path_matches_phase9a(campaign_factory) -> None:
    target, created = campaign_factory(max_decisions=10)
    action_results: list[dict] = []
    for action in ("DROP", "SEARCH", "EXTRACT", "TALK_TO_ACTOR"):
        # A fresh service object models a real process close/reopen boundary.
        current = CampaignService(target).next()
        choice = choice_for(current["canonical_request"], action)
        result = CampaignService(target).choose(
            request_fingerprint=current["canonical_request"]["request_fingerprint"],
            choice_id=choice["choice_id"],
        )
        action_results.append(result["result"])
    assert [item["action_type"] for item in action_results] == ["DROP", "SEARCH", "EXTRACT", "TALK_TO_ACTOR"]
    current = CampaignService(target).next()
    stopped = CampaignService(target).stop(
        request_fingerprint=current["canonical_request"]["request_fingerprint"]
    )
    assert stopped["session"]["status"] == "STOPPED"
    assert stopped["canonical_request"] is None
    reopened = CampaignService(target).verify()
    assert reopened["verification"]["event_replay"] is True
    assert reopened["verification"]["recorded_decision_replay"] is True
    assert reopened["verification"]["sqlite_persistence_integrity"] is True
    records_bundle = json.loads((target / "session" / "recorded_decisions.json").read_text(encoding="utf-8"))
    records = records_bundle["decisions"]
    assert [record["outcome"] for record in records] == ["ACTION"] * 4 + ["STOP"]
    assert sum(1 for record in records if record["outcome"] == "STOP") == 1
    assert len(event_rows(target)) == 4
