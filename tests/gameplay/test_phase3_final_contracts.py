"""Final contract closure tests for Phase 3."""

import pytest
from tgn.core.models import GameState, DomainEvent
from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import (
    validate_action,
    execute_action,
    get_legal_actions,
    DROP_COST,
    SEARCH_COST,
    EXTRACT_COST,
)


@pytest.fixture
def high_stamina_state():
    """State with high stamina to test target_searched constraint."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="high-stamina-test",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 10,
                "max_stamina": 10,
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


class TestExhaustedTargetDropLegality:
    """DROP must not be legal when target already searched, even with high stamina."""
    
    def test_searched_target_cannot_be_dropped_again_even_with_remaining_stamina(self, high_stamina_state):
        """After SEARCH→EXTRACT, DROP must not reappear despite high stamina."""
        # DROP
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(high_stamina_state, drop_intent)
        
        # SEARCH
        search_intent = ActionIntent("s1", "p", "SEARCH", {})
        search_result = execute_action(drop_result.final_state, search_intent)
        
        # EXTRACT
        extract_intent = ActionIntent("e1", "p", "EXTRACT", {})
        extract_result = execute_action(search_result.final_state, extract_intent)
        
        # After extract, stamina should be high (10 - 1 - 2 = 7)
        assert extract_result.final_state.data["player"]["stamina"] == 7
        assert extract_result.final_state.data["expedition"]["target_searched"] is True
        
        # DROP must NOT be legal despite high stamina
        legal_actions = get_legal_actions(extract_result.final_state)
        action_types = [a.action_type for a in legal_actions]
        
        assert "DROP" not in action_types, "DROP must not be legal after target_searched=True"
        assert "WAIT" in action_types


class TestGameplayParameterRejection:
    """DROP/SEARCH/EXTRACT must reject any parameters."""
    
    def test_drop_rejects_unexpected_params(self, high_stamina_state):
        """DROP must reject destination parameter."""
        intent = ActionIntent("d1", "p", "DROP", {"destination": "secret"})
        result = validate_action(high_stamina_state, intent)
        
        assert not result.valid
        assert result.action is None
        assert any(e.code == "UNEXPECTED_PARAMETER" for e in result.errors)
    
    def test_search_rejects_unexpected_params(self, high_stamina_state):
        """SEARCH must reject loot parameter."""
        # First DROP to make SEARCH legal
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(high_stamina_state, drop_intent)
        
        # Try SEARCH with loot param
        intent = ActionIntent("s1", "p", "SEARCH", {"loot": {"diamond": 999999}})
        result = validate_action(drop_result.final_state, intent)
        
        assert not result.valid
        assert result.action is None
        assert any(e.code == "UNEXPECTED_PARAMETER" for e in result.errors)
    
    def test_extract_rejects_unexpected_params(self, high_stamina_state):
        """EXTRACT must reject time parameter."""
        # First DROP to make EXTRACT legal
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(high_stamina_state, drop_intent)
        
        # Try EXTRACT with time param
        intent = ActionIntent("e1", "p", "EXTRACT", {"time": 0})
        result = validate_action(drop_result.final_state, intent)
        
        assert not result.valid
        assert result.action is None
        assert any(e.code == "UNEXPECTED_PARAMETER" for e in result.errors)


class TestWaitValidationReusePhase2:
    """Gameplay validate_action for WAIT must reuse Phase 2 contract."""
    
    def test_gameplay_validate_wait_preserves_phase2_validated_action(self, high_stamina_state):
        """WAIT validation must preserve params and duration_minutes."""
        intent = ActionIntent("w1", "p", "WAIT", {"minutes": 60})
        result = validate_action(high_stamina_state, intent)
        
        assert result.valid
        assert result.action is not None
        assert result.action.params == {"minutes": 60}
        assert result.action.duration_minutes == 60
        assert result.action.stamina_cost == 0
    
    def test_gameplay_validate_wait_preserves_phase2_reserved_metadata_rejection(self, high_stamina_state):
        """WAIT validation must reject forbidden engine metadata."""
        intent = ActionIntent("w1", "p", "WAIT", {"minutes": 60, "event_seq": 999})
        result = validate_action(high_stamina_state, intent)
        
        assert not result.valid
        assert result.action is None
        assert any(e.code == "FORBIDDEN_ENGINE_METADATA" for e in result.errors)


class TestEventPayloadCleanliness:
    """Generated events must not contain obsolete proof fields."""
    
    def test_search_event_does_not_contain_location_match(self, high_stamina_state):
        """SEARCH_RESOLVED event must not contain location_match."""
        # DROP
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(high_stamina_state, drop_intent)
        
        # SEARCH
        search_intent = ActionIntent("s1", "p", "SEARCH", {})
        search_result = execute_action(drop_result.final_state, search_intent)
        
        event = search_result.events[0]
        assert "location_match" not in event.payload, "Event must not contain location_match"
    
    def test_extract_event_does_not_contain_carried_matches(self, high_stamina_state):
        """EXPEDITION_EXTRACTED event must not contain carried_matches."""
        # DROP
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(high_stamina_state, drop_intent)
        
        # SEARCH
        search_intent = ActionIntent("s1", "p", "SEARCH", {})
        search_result = execute_action(drop_result.final_state, search_intent)
        
        # EXTRACT
        extract_intent = ActionIntent("e1", "p", "EXTRACT", {})
        extract_result = execute_action(search_result.final_state, extract_intent)
        
        event = extract_result.events[0]
        assert "carried_matches" not in event.payload, "Event must not contain carried_matches"


class TestLootInvariantEdgeCases:
    """Loot containers must validate resource IDs and quantities."""
    
    def test_loot_quantity_bool_rejected(self, high_stamina_state):
        """Bool loot quantity must be rejected."""
        from tgn.core.invariants import check_invariants
        
        high_stamina_state.data["inventory"]["gold"] = True
        
        with pytest.raises(Exception):
            check_invariants(high_stamina_state)
    
    def test_loot_resource_id_non_string_rejected(self, high_stamina_state):
        """Non-string resource ID must be rejected."""
        from tgn.core.invariants import check_invariants
        
        # Use integer as key (invalid)
        high_stamina_state.data["inventory"][123] = 5
        
        with pytest.raises(Exception):
            check_invariants(high_stamina_state)


class TestIndependentCostTimeTamper:
    """Reducer must independently validate payload time and event.game_minute."""
    
    def test_drop_payload_time_mismatch_rejected(self, high_stamina_state):
        """DROP with wrong payload time rejected."""
        # Manually create forged event
        forged_event = DomainEvent(
            event_seq=1,
            decision_seq=1,
            game_minute=10,  # Correct
            event_type="EXPEDITION_DROPPED",
            payload={
                "destination": "site-1",
                "time": 5,  # Wrong: should be 10
                "stamina_cost": 1,
            },
        )
        
        from tgn.core.reducer import reduce_event
        with pytest.raises(Exception):
            reduce_event(high_stamina_state, forged_event)
    
    def test_drop_event_game_minute_mismatch_rejected(self, high_stamina_state):
        """DROP with wrong event.game_minute rejected."""
        forged_event = DomainEvent(
            event_seq=1,
            decision_seq=1,
            game_minute=15,  # Wrong: should be 10
            event_type="EXPEDITION_DROPPED",
            payload={
                "destination": "site-1",
                "time": 10,  # Correct
                "stamina_cost": 1,
            },
        )
        
        from tgn.core.reducer import reduce_event
        with pytest.raises(Exception):
            reduce_event(high_stamina_state, forged_event)
    
    def test_search_payload_time_mismatch_rejected(self, high_stamina_state):
        """SEARCH with wrong payload time rejected."""
        # DROP first
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(high_stamina_state, drop_intent)
        
        forged_event = DomainEvent(
            event_seq=2,
            decision_seq=2,
            game_minute=40,  # Correct
            event_type="SEARCH_RESOLVED",
            payload={
                "loot_gained": {"salvage": 2},
                "time": 20,  # Wrong: should be 30
                "stamina_cost": 2,
            },
        )
        
        from tgn.core.reducer import reduce_event
        with pytest.raises(Exception):
            reduce_event(drop_result.final_state, forged_event)
    
    def test_extract_payload_time_mismatch_rejected(self, high_stamina_state):
        """EXTRACT with wrong payload time rejected."""
        # DROP and SEARCH first
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(high_stamina_state, drop_intent)
        
        search_intent = ActionIntent("s1", "p", "SEARCH", {})
        search_result = execute_action(drop_result.final_state, search_intent)
        
        forged_event = DomainEvent(
            event_seq=3,
            decision_seq=3,
            game_minute=55,  # Correct
            event_type="EXPEDITION_EXTRACTED",
            payload={
                "carried_loot": {"salvage": 2},
                "time": 10,  # Wrong: should be 15
            },
        )
        
        from tgn.core.reducer import reduce_event
        with pytest.raises(Exception):
            reduce_event(search_result.final_state, forged_event)
