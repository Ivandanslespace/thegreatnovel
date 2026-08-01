from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.campaign.conftest import make_projection_bundle, make_world_bundle
from tgn.campaign import create_campaign


@pytest.fixture
def story_factory(tmp_path: Path):
    world = make_world_bundle(tmp_path, name="world")
    projection = make_projection_bundle(tmp_path, world)

    def create(*, name: str = "campaign", story_id: str = "story-001", locale: str = "en", max_decisions: int = 20):
        campaign = tmp_path / name
        create_campaign(
            campaign,
            world_bundle_dir=world,
            projection_bundle_dir=projection,
            campaign_id=f"{name}-001",
            actor_id="player",
            max_decisions=max_decisions,
        )
        story = tmp_path / f"{name}-story"
        return campaign, story, {"story_id": story_id, "locale": locale}

    return create


def response_for(request: dict[str, Any], *, prose: str = "A consequence became visible.", claims: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "narration_request_id": request["narration_request_id"],
        "narration_request_hash": request["narration_request_hash"],
        "locale": request["narration_locale"],
        "claims": request["claim_requirements"] if claims is None else claims,
        "prose": prose,
    }
