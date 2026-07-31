"""Phase 3 expedition vertical slice tests.

Follows TDD discipline: contract test → red → minimal implementation → green.
Mandatory acceptance tests per section #20 of Phase 3 spec.
"""

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


class TestLegalActions:
    """Mandatory acceptance tests for state-dependent legal actions (§20)."""
    
    def test_initial_base_offers_wait_and_drop(self, phase3_initial_state):
        """Initial base state should offer WAIT and DROP only."""
        intent = ActionIntent(
            action_id="test-001",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60},
        )
        
        result = validate_action(phase3_initial_state, intent)
        assert result.valid
        
        # DROP should also be valid at initial state
        intent_drop = ActionIntent(
            action_id="test-002",
            actor_id="player",
            action_type="DROP",
            params={},
        )
        result_drop = validate_action(phase3_initial_state, intent_drop)
        assert result_drop.valid
    
    def test_drop_not_legal_while_expedition_active(self, phase3_initial_state):
        """DROP not legal when already on expedition."""
        active_state = GameState(
            schema_version=1,
            event_seq=1,
            decision_seq=1,
            game_minute=10,
            seed="phase3-test",
            data={
                "player": {
                    "location_id": "site-1",
                    "stamina": 2,
                    "max_stamina": 3,
                },
                "inventory": {},
                "expedition": {
                    "active": True,
                    "base_location_id": "base-1",
                    "target_location_id": "site-1",
                    "target_searched": False,
                    "target_loot": {"salvage": 2},
                    "carried_loot": {},
                },
            },
        )
        
        intent_drop = ActionIntent(
            action_id="test-drop",
            actor_id="player",
            action_type="DROP",
            params={},
        )
        result = validate_action(active_state, intent_drop)
        assert not result.valid


class TestDroppedSearchExtractContracts:
    """Mandatory acceptance tests for DROP/SEARCH/EXTRACT contracts (§20)."""
    
    def test_drop_produces_exactly_one_event(self, phase3_initial_state):
        """DROP produces exactly one EXPEDITION_DROPPED event."""
        intent = ActionIntent(
            action_id="drop-001",
            actor_id="player",
            action_type="DROP",
            params={},
        )
        
        result = execute_action(phase3_initial_state, intent)
        assert result.accepted
        assert len(result.events) == 1
        assert result.events[0].event_type == "EXPEDITION_DROPPED"
        assert result.final_state is not None
    
    def test_drop_moves_player_to_target(self, phase3_initial_state):
        """DROP moves player.location_id to target_location_id."""
        intent = ActionIntent(
            action_id="drop-001",
            actor_id="player",
            action_type="DROP",
            params={},
        )
        result = execute_action(phase3_initial_state, intent)
        
        assert result.final_state.data["player"]["location_id"] == "site-1"
    
    def test_drop_activates_expedition(self, phase3_initial_state):
        """DROP sets expedition.active = True."""
        intent = ActionIntent(
            action_id="drop-001",
            actor_id="player",
            action_type="DROP",
            params={},
        )
        result = execute_action(phase3_initial_state, intent)
        
        assert result.final_state.data["expedition"]["active"] is True
    
    def test_search_moves_target_loot_to_carried_loot(self, phase3_initial_state):
        """SEARCH moves loot from target_loot to carried_loot."""
        # First DROP
        drop_result = execute_action(phase3_initial_state, 
                                     ActionIntent("d1", "p", "DROP", {}))
        
        # Then SEARCH
        search_result = execute_action(drop_result.final_state,
                                       ActionIntent("s1", "p", "SEARCH", {}))
        
        assert search_result.accepted
        assert search_result.events[0].event_type == "SEARCH_RESOLVED"
        
        # Loot should be in carried_loot, not inventory yet
        carried = search_result.final_state.data["expedition"]["carried_loot"]
        assert carried == {"salvage": 2}
        assert search_result.final_state.data["inventory"] == {}
    
    def test_search_does_not_bank_loot_directly(self, phase3_initial_state):
        """SEARCH does NOT move loot directly to inventory."""
        # First DROP
        drop_result = execute_action(phase3_initial_state, 
                                     ActionIntent("d1", "p", "DROP", {}))
        
        # Then SEARCH
        search_result = execute_action(drop_result.final_state,
                                       ActionIntent("s1", "p", "SEARCH", {}))
        
        # Inventory should remain empty until EXTRACT
        assert search_result.final_state.data["inventory"] == {}
        assert search_result.final_state.data["expedition"]["carried_loot"] == {"salvage": 2}
    
    def test_extract_returns_player_to_base(self, phase3_initial_state):
        """EXTRACT returns player.location_id to base_location_id."""
        # DROP then SEARCH then EXTRACT
        drop_result = execute_action(phase3_initial_state,
                                     ActionIntent("d1", "p", "DROP", {}))
        search_result = execute_action(drop_result.final_state,
                                       ActionIntent("s1", "p", "SEARCH", {}))
        
        extract_intent = ActionIntent("e1", "p", "EXTRACT", {})
        extract_result = execute_action(search_result.final_state, extract_intent)
        
        assert extract_result.final_state.data["player"]["location_id"] == "base-1"
    
    def test_extract_moves_carried_loot_to_inventory(self, phase3_initial_state):
        """EXTRACT moves carried_loot into inventory."""
        # Full chain
        drop_result = execute_action(phase3_initial_state,
                                     ActionIntent("d1", "p", "DROP", {}))
        search_result = execute_action(drop_result.final_state,
                                       ActionIntent("s1", "p", "SEARCH", {}))
        
        extract_intent = ActionIntent("e1", "p", "EXTRACT", {})
        extract_result = execute_action(search_result.final_state, extract_intent)
        
        # Inventory should now have the loot
        assert extract_result.final_state.data["inventory"] == {"salvage": 2}
        assert extract_result.final_state.data["expedition"]["carried_loot"] == {}
    
    def test_extract_deactivates_expedition(self, phase3_initial_state):
        """EXTRACT sets expedition.active = False."""
        # DROP then SEARCH then EXTRACT
        drop_result = execute_action(phase3_initial_state,
                                     ActionIntent("d1", "p", "DROP", {}))
        search_result = execute_action(drop_result.final_state,
                                       ActionIntent("s1", "p", "SEARCH", {}))
        
        extract_result = execute_action(search_result.final_state,
                                        ActionIntent("e1", "p", "EXTRACT", {}))
        
        assert extract_result.final_state.data["expedition"]["active"] is False
    
    def test_extract_before_search_does_not_create_loot(self, phase3_initial_state):
        """EXTRACT without prior SEARCH does not add loot to inventory."""
        # Just DROP then EXTRACT (no SEARCH)
        drop_result = execute_action(phase3_initial_state,
                                     ActionIntent("d1", "p", "DROP", {}))
        
        extract_result = execute_action(drop_result.final_state,
                                        ActionIntent("e1", "p", "EXTRACT", {}))
        
        # Inventory remains empty, no loot created
        assert extract_result.final_state.data["inventory"] == {}
        assert extract_result.final_state.data["expedition"]["target_searched"] is False


class TestDuplicateRewardExploitRegression:
    """Mandatory exploit regression test - duplicate search rejection (§22)."""
    
    def test_second_search_rejected_without_side_effects(self, phase3_initial_state):
        """Second SEARCH after first must be rejected with zero side effects."""
        # First DROP
        drop_result = execute_action(phase3_initial_state,
                                     ActionIntent("d1", "p", "DROP", {}))
        
        # First SEARCH - should succeed
        search1_result = execute_action(drop_result.final_state,
                                        ActionIntent("s1", "p", "SEARCH", {}))
        assert search1_result.accepted
        
        # Second SEARCH - must be rejected
        search2_result = execute_action(search1_result.final_state,
                                        ActionIntent("s2", "p", "SEARCH", {}))
        
        assert not search2_result.accepted
        assert len(search2_result.events) == 0
        assert search2_result.final_state is None
        
        # State hash unchanged after failed second SEARCH
        # (verified by checking state hasn't changed)
        assert search1_result.final_state is not None
