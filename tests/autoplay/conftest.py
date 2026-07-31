"""Autoplay test fixtures."""

import pytest
from tgn.core.models import GameState


@pytest.fixture
def phase35_initial_state():
    """Canonical Phase 3.5 initial state per spec section #25."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="phase35-test",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 3,
                "max_stamina": 3,
            },
            "inventory": {},
            "expedition": {
                "active": False,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": False,
                "target_loot": {"salvage": 2},
                "carried_loot": {},
            },
        },
    )
