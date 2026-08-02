from __future__ import annotations

import json
from pathlib import Path

from tests.play.conftest import narrator_argv, write_narrator
from tgn.campaign import verify_campaign
from tgn.play import PlayService
from tgn.story import verify_story


def test_overlay_uses_frozen_pc1_numeric_path(bundle_pair):
    _base, overlay, projection, tmp_path = bundle_pair
    narrator = write_narrator(tmp_path / "phase10-narrator.py")
    workspace = tmp_path / "phase10-play"
    output: list[str] = []

    result = PlayService(workspace).new(
        world_bundle_dir=overlay,
        projection_bundle_dir=projection,
        campaign_id="phase10-play-campaign",
        story_id="phase10-play-story",
        actor_id="player",
        max_decisions=5,
        locale="en",
        voice_id="cablecar_survival",
        narrator_argv=narrator_argv(narrator),
        input_fn=iter(("2", "2", "1", "2", "2")).__next__,
        output_fn=output.append,
    )

    assert result["terminal"] is True
    campaign = workspace / "campaign"
    story = workspace / "story"
    assert verify_campaign(campaign)["verification"]["event_replay"] is True
    assert verify_story(story, campaign_dir=campaign)["valid"] is True
    records = json.loads(
        (campaign / "session" / "recorded_decisions.json").read_text(encoding="utf-8")
    )["decisions"]
    assert [record["action_type"] for record in records if record["outcome"] == "ACTION"] == [
        "DROP",
        "SEARCH",
        "FIGHT",
        "DEVOUR_REMAINS",
        "EXTRACT",
    ]
    assert any(
        'DEVOUR_REMAINS {"capability":{"id":"devour_evolution","label":"Devour Evolution"}}'
        in line
        for line in output
    )
    assert (story / "novel.md").exists()

