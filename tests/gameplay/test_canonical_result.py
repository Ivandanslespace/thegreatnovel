"""Tests to verify canonical ActionExecutionResult type is used."""

import pytest
from tgn.actions.models import ActionIntent, ActionExecutionResult
from tgn.gameplay.expedition import execute_action


@pytest.fixture
def base_state():
    """Base state at expedition base."""
    from tgn.core.models import GameState
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="canonical-test",
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


class TestCanonicalActionExecutionResult:
    """All actions must return the same canonical ActionExecutionResult type."""
    
    def test_wait_returns_canonical_result(self, base_state):
        """WAIT returns canonical ActionExecutionResult."""
        intent = ActionIntent("w1", "p", "WAIT", {"minutes": 60})
        result = execute_action(base_state, intent)
        
        assert isinstance(result, ActionExecutionResult)
        assert isinstance(result.accepted, bool)
        assert isinstance(result.events, tuple)
    
    def test_drop_returns_canonical_result(self, base_state):
        """DROP returns canonical ActionExecutionResult."""
        intent = ActionIntent("d1", "p", "DROP", {})
        result = execute_action(base_state, intent)
        
        assert isinstance(result, ActionExecutionResult)
        assert isinstance(result.accepted, bool)
        assert isinstance(result.events, tuple)
        assert result.accepted
        assert len(result.events) == 1
    
    def test_search_returns_canonical_result(self, base_state):
        """SEARCH returns canonical ActionExecutionResult."""
        # First DROP to make SEARCH legal
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(base_state, drop_intent)
        
        # Then SEARCH
        search_intent = ActionIntent("s1", "p", "SEARCH", {})
        search_result = execute_action(drop_result.final_state, search_intent)
        
        assert isinstance(search_result, ActionExecutionResult)
        assert isinstance(search_result.accepted, bool)
        assert isinstance(search_result.events, tuple)
        assert search_result.accepted
        assert len(search_result.events) == 1
    
    def test_extract_returns_canonical_result(self, base_state):
        """EXTRACT returns canonical ActionExecutionResult."""
        # DROP and SEARCH first
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(base_state, drop_intent)
        
        search_intent = ActionIntent("s1", "p", "SEARCH", {})
        search_result = execute_action(drop_result.final_state, search_intent)
        
        # Then EXTRACT
        extract_intent = ActionIntent("e1", "p", "EXTRACT", {})
        extract_result = execute_action(search_result.final_state, extract_intent)
        
        assert isinstance(extract_result, ActionExecutionResult)
        assert isinstance(extract_result.accepted, bool)
        assert isinstance(extract_result.events, tuple)
        assert extract_result.accepted
        assert len(extract_result.events) == 1
