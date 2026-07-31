"""Additional mandatory Phase 3 gameplay tests."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from tgn.core.models import GameState, DomainEvent
from tgn.core.hashing import state_hash
from tgn.core.reducer import reduce_event
from tgn.actions.models import ActionIntent
from tgn.storage import EventStore, verify_persistence_integrity
from tgn.gameplay.expedition import (
    validate_action,
    execute_action,
    get_legal_actions,
    build_observation,
    DROP_COST,
    SEARCH_COST,
    EXTRACT_COST,
)


# Fixture
@pytest.fixture
def base_state():
    """Initial state at base."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="test",
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


class TestObservationContract:
    """Observation builder must expose player-visible state only."""
    
    def test_observation_contains_player_visible_state(self, base_state):
        """Observation includes all player-visible fields."""
        obs = build_observation(base_state)
        
        assert "game_minute" in obs
        assert "location_id" in obs
        assert "stamina" in obs
        assert "max_stamina" in obs
        assert "inventory" in obs
        assert "carried_loot" in obs
        assert "expedition_active" in obs
        assert "target_searched" in obs
        assert "legal_actions" in obs
    
    def test_observation_does_not_expose_target_loot(self, base_state):
        """Observation must NOT expose target_loot (information asymmetry)."""
        obs = build_observation(base_state)
        
        assert "target_loot" not in obs
        assert obs["carried_loot"] == {}  # Carried IS visible
    
    def test_observation_contains_carried_loot(self, base_state):
        """Observation includes carried_loot."""
        obs = build_observation(base_state)
        
        assert "carried_loot" in obs
        assert isinstance(obs["carried_loot"], dict)
    
    def test_mutating_observation_does_not_mutate_state(self, base_state):
        """Mutating observation must not mutate state."""
        obs = build_observation(base_state)
        
        # Try to mutate observation
        obs["inventory"]["forged_item"] = 999
        obs["carried_loot"]["forged"] = 123
        
        # Original state must be unchanged
        assert "forged_item" not in base_state.data["inventory"]
        assert "forged" not in base_state.data["expedition"]["carried_loot"]


class TestLegalActionStates:
    """Test legal actions across various states."""
    
    def test_drop_hidden_when_stamina_insufficient(self, base_state):
        """DROP not offered when stamina < DROP_COST."""
        # Reduce stamina to 0
        base_state.data["player"]["stamina"] = 0
        
        actions = get_legal_actions(base_state)
        action_types = [a.action_type for a in actions]
        
        assert "DROP" not in action_types
        assert "WAIT" in action_types
    
    def test_after_drop_offers_wait_search_and_extract(self, base_state):
        """Post-DROP: WAIT, SEARCH, EXTRACT."""
        # DROP
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(base_state, drop_intent)
        dropped_state = drop_result.final_state
        
        actions = get_legal_actions(dropped_state)
        action_types = [a.action_type for a in actions]
        
        assert "WAIT" in action_types
        assert "SEARCH" in action_types
        assert "EXTRACT" in action_types
        assert "DROP" not in action_types
    
    def test_search_disappears_when_stamina_insufficient(self, base_state):
        """SEARCH not offered when stamina < SEARCH_COST."""
        # DROP
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(base_state, drop_intent)
        dropped_state = drop_result.final_state
        
        # Reduce stamina to 1 (SEARCH needs 2)
        dropped_state.data["player"]["stamina"] = 1
        
        actions = get_legal_actions(dropped_state)
        action_types = [a.action_type for a in actions]
        
        assert "SEARCH" not in action_types
        assert "EXTRACT" in action_types
    
    def test_search_disappears_after_target_searched(self, base_state):
        """SEARCH not offered after target searched."""
        # DROP
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(base_state, drop_intent)
        
        # SEARCH
        search_intent = ActionIntent("s1", "p", "SEARCH", {})
        search_result = execute_action(drop_result.final_state, search_intent)
        
        actions = get_legal_actions(search_result.final_state)
        action_types = [a.action_type for a in actions]
        
        assert "SEARCH" not in action_types
        assert "EXTRACT" in action_types
    
    def test_extract_remains_available_during_active_expedition(self, base_state):
        """EXTRACT available throughout expedition."""
        # DROP
        drop_intent = ActionIntent("d1", "p", "DROP", {})
        drop_result = execute_action(base_state, drop_intent)
        
        actions = get_legal_actions(drop_result.final_state)
        action_types = [a.action_type for a in actions]
        
        assert "EXTRACT" in action_types
        
        # After SEARCH
        search_intent = ActionIntent("s1", "p", "SEARCH", {})
        search_result = execute_action(drop_result.final_state, search_intent)
        
        actions = get_legal_actions(search_result.final_state)
        action_types = [a.action_type for a in actions]
        
        assert "EXTRACT" in action_types
    
    def test_post_searched_extract_offers_wait_only(self, base_state):
        """After SEARCH + EXTRACT, only WAIT remains."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # SEARCH
        search_result = execute_action(drop_result.final_state, ActionIntent("s1", "p", "SEARCH", {}))
        
        # EXTRACT
        extract_result = execute_action(search_result.final_state, ActionIntent("e1", "p", "EXTRACT", {}))
        
        actions = get_legal_actions(extract_result.final_state)
        action_types = [a.action_type for a in actions]
        
        assert action_types == ["WAIT"]
    
    def test_validator_and_legal_action_builder_agree(self, base_state):
        """Validator rejects action not in legal actions."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # SEARCH
        search_result = execute_action(drop_result.final_state, ActionIntent("s1", "p", "SEARCH", {}))
        
        # SEARCH again should be rejected
        second_search = ActionIntent("s2", "p", "SEARCH", {})
        result = validate_action(search_result.final_state, second_search)
        
        assert not result.valid
        assert result.errors[0].code == "ACTION_NOT_LEGAL_IN_STATE"


class TestReducerHardening:
    """Reducer must reject forged events."""
    
    def test_reducer_rejects_wrong_drop_destination(self, base_state):
        """DROP event with wrong destination rejected."""
        forged_event = DomainEvent(
            event_seq=1,
            decision_seq=1,
            game_minute=10,
            event_type="EXPEDITION_DROPPED",
            payload={
                "destination": "wrong-destination",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(base_state, forged_event)
    
    def test_reducer_rejects_wrong_drop_time(self, base_state):
        """DROP event with wrong time rejected."""
        forged_event = DomainEvent(
            event_seq=1,
            decision_seq=1,
            game_minute=20,  # Wrong: should be 10
            event_type="EXPEDITION_DROPPED",
            payload={
                "destination": "site-1",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(base_state, forged_event)
    
    def test_reducer_rejects_wrong_drop_stamina_cost(self, base_state):
        """DROP event with wrong stamina cost rejected."""
        forged_event = DomainEvent(
            event_seq=1,
            decision_seq=1,
            game_minute=10,
            event_type="EXPEDITION_DROPPED",
            payload={
                "destination": "site-1",
                "time": 10,
                "stamina_cost": 5,  # Wrong: should be 1
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(base_state, forged_event)
    
    def test_reducer_rejects_drop_from_invalid_state(self, base_state):
        """DROP rejected when not at base."""
        # First, DROP to move away from base
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # Try DROP again from expedition site
        forged_event = DomainEvent(
            event_seq=2,
            decision_seq=2,
            game_minute=20,
            event_type="EXPEDITION_DROPPED",
            payload={
                "destination": "site-2",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(drop_result.final_state, forged_event)
    
    def test_reducer_rejects_forged_search_loot(self, base_state):
        """SEARCH event with forged loot rejected."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # Try SEARCH with forged loot
        forged_event = DomainEvent(
            event_seq=2,
            decision_seq=2,
            game_minute=40,
            event_type="SEARCH_RESOLVED",
            payload={
                "loot_gained": {"diamond": 999999},  # Forged!
                "time": 30,
                "stamina_cost": 2,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(drop_result.final_state, forged_event)
    
    def test_reducer_rejects_wrong_search_time(self, base_state):
        """SEARCH event with wrong time rejected."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # Try SEARCH with wrong time
        forged_event = DomainEvent(
            event_seq=2,
            decision_seq=2,
            game_minute=50,  # Wrong: should be 40
            event_type="SEARCH_RESOLVED",
            payload={
                "loot_gained": {"salvage": 2},
                "time": 30,
                "stamina_cost": 2,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(drop_result.final_state, forged_event)
    
    def test_reducer_rejects_forged_extract_loot(self, base_state):
        """EXTRACT event with forged loot rejected."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # SEARCH
        search_result = execute_action(drop_result.final_state, ActionIntent("s1", "p", "SEARCH", {}))
        
        # Try EXTRACT with forged loot (more than carried)
        forged_event = DomainEvent(
            event_seq=3,
            decision_seq=3,
            game_minute=55,
            event_type="EXPEDITION_EXTRACTED",
            payload={
                "carried_loot": {"diamond": 999999, "salvage": 2},  # Forged diamond!
                "time": 15,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(search_result.final_state, forged_event)
    
    def test_reducer_rejects_extract_when_inactive(self, base_state):
        """EXTRACT rejected when expedition not active."""
        forged_event = DomainEvent(
            event_seq=1,
            decision_seq=1,
            game_minute=15,
            event_type="EXPEDITION_EXTRACTED",
            payload={
                "carried_loot": {},
                "time": 15,
            },
        )
        
        with pytest.raises(Exception):
            reduce_event(base_state, forged_event)


class TestBranchDivergence:
    """SEARCH vs EXTRACT must produce different outcomes."""
    
    def test_search_vs_early_extract_produces_branch_divergence(self, base_state):
        """From post-DROP state, SEARCH and EXTRACT diverge."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        dropped_state = drop_result.final_state
        
        # Branch A: SEARCH
        search_result = execute_action(dropped_state, ActionIntent("s1", "p", "SEARCH", {}))
        
        # Branch B: EXTRACT (no SEARCH)
        extract_result = execute_action(dropped_state, ActionIntent("e1", "p", "EXTRACT", {}))
        
        # Hashes must differ
        hash_a = state_hash(search_result.final_state.__dict__)
        hash_b = state_hash(extract_result.final_state.__dict__)
        
        assert hash_a != hash_b
        
        # Legal actions must differ
        actions_a = get_legal_actions(search_result.final_state)
        actions_b = get_legal_actions(extract_result.final_state)
        
        action_types_a = sorted([a.action_type for a in actions_a])
        action_types_b = sorted([a.action_type for a in actions_b])
        
        assert action_types_a != action_types_b


class TestPureReplay:
    """Replay must produce same final hash."""
    
    def test_phase3_action_events_replay_to_same_final_hash(self, base_state):
        """Live execution vs replay produces same hash."""
        # Live execution: DROP → SEARCH → EXTRACT
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        search_result = execute_action(drop_result.final_state, ActionIntent("s1", "p", "SEARCH", {}))
        extract_result = execute_action(search_result.final_state, ActionIntent("e1", "p", "EXTRACT", {}))
        
        live_events = [drop_result.events[0], search_result.events[0], extract_result.events[0]]
        live_hash = state_hash(extract_result.final_state.__dict__)
        
        # Replay from initial
        from tgn.storage.replay import replay_events
        replay_result = replay_events(base_state, live_events)
        
        assert replay_result.success
        assert replay_result.actual_hash == live_hash


class TestPersistenceE2E:
    """Persistence must work end-to-end."""
    
    def test_phase3_execute_persist_reopen_verify_end_to_end(self, base_state):
        """Full E2E: DROP → SEARCH → EXTRACT, persist, reopen, verify."""
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "phase3_e2e.db"
            
            store = EventStore(db_path)
            try:
                # Initialize
                store.initialize("camp_phase3", base_state.__dict__)
                
                # DROP
                drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
                store.append_transition("camp_phase3", drop_result.events[0], base_state, drop_result.final_state)
                
                # SEARCH
                search_result = execute_action(drop_result.final_state, ActionIntent("s1", "p", "SEARCH", {}))
                store.append_transition("camp_phase3", search_result.events[0], drop_result.final_state, search_result.final_state)
                
                # EXTRACT
                extract_result = execute_action(search_result.final_state, ActionIntent("e1", "p", "EXTRACT", {}))
                store.append_transition("camp_phase3", extract_result.events[0], search_result.final_state, extract_result.final_state)
                
                live_final_hash = state_hash(extract_result.final_state.__dict__)
                
            finally:
                store.close()
            
            # Reopen and verify
            new_store = EventStore(db_path)
            try:
                verify_result = verify_persistence_integrity("camp_phase3", db_path)
                
                assert verify_result.success
                assert verify_result.actual_hash == live_final_hash
                
            finally:
                new_store.close()


class TestActionCostsExposed:
    """Legal actions must expose costs."""
    
    def test_observation_exposes_known_action_costs(self, base_state):
        """Legal actions include duration and stamina costs."""
        actions = get_legal_actions(base_state)
        
        # Find DROP action
        drop_action = next((a for a in actions if a.action_type == "DROP"), None)
        
        assert drop_action is not None
        assert drop_action.duration_minutes == DROP_COST["time"]
        assert drop_action.stamina_cost == DROP_COST["stamina"]
        
        # Drop and find SEARCH
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        actions = get_legal_actions(drop_result.final_state)
        search_action = next((a for a in actions if a.action_type == "SEARCH"), None)
        
        assert search_action is not None
        assert search_action.duration_minutes == SEARCH_COST["time"]
        assert search_action.stamina_cost == SEARCH_COST["stamina"]


class TestDuplicateSearchCanonicalHash:
    """Duplicate SEARCH must preserve exact canonical hash."""
    
    def test_second_search_preserves_canonical_hash(self, base_state):
        """After successful SEARCH, second SEARCH rejected, hash unchanged."""
        # DROP
        drop_result = execute_action(base_state, ActionIntent("d1", "p", "DROP", {}))
        
        # SEARCH
        search_result = execute_action(drop_result.final_state, ActionIntent("s1", "p", "SEARCH", {}))
        hash_before = state_hash(search_result.final_state.__dict__)
        
        # Second SEARCH (rejected)
        second_search = ActionIntent("s2", "p", "SEARCH", {})
        second_result = execute_action(search_result.final_state, second_search)
        
        assert not second_result.accepted
        assert len(second_result.events) == 0
        assert second_result.final_state is None
        
        hash_after = state_hash(search_result.final_state.__dict__)
        assert hash_before == hash_after
