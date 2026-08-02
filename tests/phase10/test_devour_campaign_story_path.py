from __future__ import annotations

from pathlib import Path

from tgn.campaign import choose_campaign, create_campaign, next_campaign, verify_campaign
from tgn.story import commit_story, init_story, prepare_story, verify_story


def _choose(campaign: Path, action_type: str) -> dict:
    current = next_campaign(campaign)
    choice = next(
        item
        for item in current["canonical_request"]["choices"]
        if item["action_type"] == action_type
    )
    return choose_campaign(
        campaign,
        request_fingerprint=current["canonical_request"]["request_fingerprint"],
        choice_id=choice["choice_id"],
    )


def test_overlay_campaign_story_path_uses_generic_boundaries(bundle_pair):
    _base, overlay, projection, tmp_path = bundle_pair
    campaign = tmp_path / "phase10-campaign"
    story = tmp_path / "phase10-story"
    create_campaign(
        campaign,
        world_bundle_dir=overlay,
        projection_bundle_dir=projection,
        campaign_id="phase10-campaign",
        actor_id="player",
        max_decisions=10,
    )
    init_story(
        story,
        campaign_dir=campaign,
        story_id="phase10-story",
        initial_narration_locale="en",
        initial_voice_id="cablecar_survival",
    )

    event_types = []
    for action_type in ("DROP", "SEARCH", "FIGHT", "DEVOUR_REMAINS", "EXTRACT"):
        result = _choose(campaign, action_type)
        event_types.append(result["result"]["event_type"])
        request = prepare_story(story, campaign_dir=campaign)["request"]
        assert request["action_type"] == action_type
        committed = commit_story(
            story,
            campaign_dir=campaign,
            response={
                "schema_version": 1,
                "narration_request_id": request["narration_request_id"],
                "narration_request_hash": request["narration_request_hash"],
                "locale": request["narration_locale"],
                "claims": request["claim_requirements"],
                "prose": f"Public consequence for {action_type} was recorded.",
            },
        )
        assert committed["result"] == "committed"

    assert event_types == [
        "EXPEDITION_DROPPED",
        "SEARCH_RESOLVED",
        "COMBAT_RESOLVED",
        "DEVOUR_RESOLVED",
        "EXPEDITION_EXTRACTED",
    ]
    assert verify_campaign(campaign)["verification"]["valid"] is True
    assert verify_story(story, campaign_dir=campaign)["valid"] is True
