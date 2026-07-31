"""Phase 3 expedition tests."""

from pathlib import Path
from tempfile import TemporaryDirectory
import pytest

from tgn.core.models import GameState
from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import validate_action, execute_action


@pytest.fixture
def phase3_initial_state():
    """Initial expedition state per spec section #24."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="phase3-test",
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
