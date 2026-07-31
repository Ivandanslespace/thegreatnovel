"""Phase 4 scenario, replay, and persistence tests.

Covers spec sections 40-43: branch scenarios, death scenario,
persistence scenario, FLEE persistence scenario.
"""

import pytest
from pathlib import Path
import tempfile

from tgn.core.models import GameState, DomainEvent
from tgn.core.hashing import state_hash
from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import execute_action, get_legal_actions
from tgn.storage.event_store import EventStore
from tgn.storage.replay import replay_events, verify_replay, verify_persistence_integrity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_phase4_state(stamina=5, hp=6, enemy_hp=4, enemy_attack=2):
    """Create Phase 4 initial state with configurable parameters."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="phase4-scenario",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": stamina,
                "max_stamina": stamina,
                "hp": hp,
                "max_hp": hp,
                "attack": 2,
            },
            "inventory": {},
            "expedition": {
                "active": False,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": False,
                "target_loot": {"salvage": 2},
                "carried_loot": {},
                "encounter": {
                    "active": False,
                    "enemy_id": "enemy-1",
                    "enemy_hp": enemy_hp,
                    "enemy_max_hp": enemy_hp,
                    "enemy_attack": enemy_attack,
                },
            },
        },
    )


def run_to_post_search(state):
    """Run DROP + SEARCH to reach post-search state with active encounter."""
    events = []
    
    # DROP
    drop_intent = ActionIntent(
        action_id="act-drop", actor_id="player-1", action_type="DROP", params={}
    )
    result = execute_action(state, drop_intent)
    assert result.accepted
    events.extend(result.events)
    state = result.final_state
    
    # SEARCH
    search_intent = ActionIntent(
        action_id="act-search", actor_id="player-1", action_type="SEARCH", params={}
    )
    result = execute_action(state, search_intent)
    assert result.accepted
    events.extend(result.events)
    state = result.final_state
    
    return state, events


# ---------------------------------------------------------------------------
# Section 40: Two essential branch scenarios
# ---------------------------------------------------------------------------

class TestBranchScenarios:
    """Fight and Flee branch scenarios per spec section 40."""

    def test_branch_a_fight_path(self):
        """Branch A: FIGHT -> enemy defeated -> EXTRACT -> loot banked."""
        state = make_phase4_state()
        state, events = run_to_post_search(state)
        
        initial_hp = state.data["player"]["hp"]
        initial_enemy_hp = state.data["expedition"]["encounter"]["enemy_hp"]
        
        # Fight 1: enemy 4->2, player 6->4
        fight1 = ActionIntent(
            action_id="act-fight-1", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight1)
        assert result.accepted
        events.extend(result.events)
        state = result.final_state
        
        assert state.data["expedition"]["encounter"]["enemy_hp"] == 2
        assert state.data["player"]["hp"] == 4
        
        # Fight 2: enemy 2->0 (dead), no retaliation
        fight2 = ActionIntent(
            action_id="act-fight-2", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight2)
        assert result.accepted
        events.extend(result.events)
        state = result.final_state
        
        assert state.data["expedition"]["encounter"]["enemy_hp"] == 0
        assert state.data["expedition"]["encounter"]["active"] is False
        assert state.data["player"]["hp"] == 4  # No retaliation
        
        # EXTRACT
        extract = ActionIntent(
            action_id="act-extract", actor_id="player-1",
            action_type="EXTRACT", params={}
        )
        result = execute_action(state, extract)
        assert result.accepted
        events.extend(result.events)
        state = result.final_state
        
        # Loot banked
        assert state.data["inventory"] == {"salvage": 2}
        assert state.data["expedition"]["carried_loot"] == {}
        assert state.data["player"]["location_id"] == "base-1"
        
        # Player lost HP
        assert state.data["player"]["hp"] < initial_hp

    def test_branch_b_flee_path(self):
        """Branch B: FLEE -> survive -> loot lost."""
        state = make_phase4_state()
        state, events = run_to_post_search(state)
        
        # Verify loot carried before flee
        assert state.data["expedition"]["carried_loot"] == {"salvage": 2}
        
        # FLEE
        flee = ActionIntent(
            action_id="act-flee", actor_id="player-1",
            action_type="FLEE", params={}
        )
        result = execute_action(state, flee)
        assert result.accepted
        events.extend(result.events)
        state = result.final_state
        
        # Player survives
        assert state.data["player"]["hp"] == 6
        
        # Loot lost
        assert state.data["inventory"] == {}
        assert state.data["expedition"]["carried_loot"] == {}
        
        # At base, expedition inactive
        assert state.data["player"]["location_id"] == "base-1"
        assert state.data["expedition"]["active"] is False


# ---------------------------------------------------------------------------
# Section 41: Death scenario
# ---------------------------------------------------------------------------

class TestDeathScenario:
    """Death scenario per spec section 41."""

    def test_deterministic_death(self):
        """Fixed state where FIGHT leads to player death."""
        # Player hp=1, enemy attack=2 -> one fight kills player
        state = make_phase4_state(hp=1, enemy_hp=4, enemy_attack=2)
        state, events = run_to_post_search(state)
        
        # FIGHT -> player dies
        fight = ActionIntent(
            action_id="act-fight-fatal", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight)
        assert result.accepted
        events.extend(result.events)
        state = result.final_state
        
        # Death reproduced
        assert state.data["player"]["hp"] == 0
        
        # No legal actions
        legal = get_legal_actions(state)
        assert len(legal) == 0
        
        # Event records death
        event = result.events[0]
        assert event.payload["outcome"] == "PLAYER_DIED"


# ---------------------------------------------------------------------------
# Section 42-43: Persistence scenarios
# ---------------------------------------------------------------------------

class TestPersistenceScenarios:
    """Persistence scenarios per spec sections 42-43."""

    def test_fight_path_persistence(self):
        """Complete fight path through persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = EventStore(db_path)
            campaign_id = "phase4-fight-test"
            
            try:
                state = make_phase4_state()
                store.initialize(campaign_id, state.__dict__)
                
                all_events = []
                
                # DROP
                drop = ActionIntent(
                    action_id="act-drop", actor_id="player-1",
                    action_type="DROP", params={}
                )
                result = execute_action(state, drop)
                assert result.accepted
                store.append_transition(campaign_id, result.events[0], state, result.final_state)
                all_events.extend(result.events)
                state = result.final_state
                
                # SEARCH
                search = ActionIntent(
                    action_id="act-search", actor_id="player-1",
                    action_type="SEARCH", params={}
                )
                result = execute_action(state, search)
                assert result.accepted
                store.append_transition(campaign_id, result.events[0], state, result.final_state)
                all_events.extend(result.events)
                state = result.final_state
                
                # FIGHT x2
                for i in range(2):
                    fight = ActionIntent(
                        action_id=f"act-fight-{i}", actor_id="player-1",
                        action_type="FIGHT", params={}
                    )
                    result = execute_action(state, fight)
                    assert result.accepted
                    store.append_transition(campaign_id, result.events[0], state, result.final_state)
                    all_events.extend(result.events)
                    state = result.final_state
                
                # EXTRACT
                extract = ActionIntent(
                    action_id="act-extract", actor_id="player-1",
                    action_type="EXTRACT", params={}
                )
                result = execute_action(state, extract)
                assert result.accepted
                store.append_transition(campaign_id, result.events[0], state, result.final_state)
                all_events.extend(result.events)
                live_final_state = result.final_state
                live_hash = state_hash(live_final_state.__dict__)
                
                store.close()
                
                # Verify persistence integrity
                verify_result = verify_persistence_integrity(campaign_id, db_path)
                assert verify_result.success, f"Persistence verification failed: {verify_result.error_message}"
                assert verify_result.actual_hash == live_hash
                
            finally:
                store.close()

    def test_flee_path_persistence(self):
        """FLEE path through persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = EventStore(db_path)
            campaign_id = "phase4-flee-test"
            
            try:
                state = make_phase4_state()
                store.initialize(campaign_id, state.__dict__)
                
                # DROP
                drop = ActionIntent(
                    action_id="act-drop", actor_id="player-1",
                    action_type="DROP", params={}
                )
                result = execute_action(state, drop)
                assert result.accepted
                store.append_transition(campaign_id, result.events[0], state, result.final_state)
                state = result.final_state
                
                # SEARCH
                search = ActionIntent(
                    action_id="act-search", actor_id="player-1",
                    action_type="SEARCH", params={}
                )
                result = execute_action(state, search)
                assert result.accepted
                store.append_transition(campaign_id, result.events[0], state, result.final_state)
                state = result.final_state
                
                # FLEE
                flee = ActionIntent(
                    action_id="act-flee", actor_id="player-1",
                    action_type="FLEE", params={}
                )
                result = execute_action(state, flee)
                assert result.accepted
                store.append_transition(campaign_id, result.events[0], state, result.final_state)
                live_final_state = result.final_state
                live_hash = state_hash(live_final_state.__dict__)
                
                store.close()
                
                # Verify persistence integrity
                verify_result = verify_persistence_integrity(campaign_id, db_path)
                assert verify_result.success, f"Persistence verification failed: {verify_result.error_message}"
                assert verify_result.actual_hash == live_hash
                
                # Verify FLEE consequences persisted
                final_state_dict = verify_result.final_state
                assert final_state_dict["data"]["inventory"] == {}
                assert final_state_dict["data"]["expedition"]["carried_loot"] == {}
                assert final_state_dict["data"]["expedition"]["active"] is False
                
            finally:
                store.close()


# ---------------------------------------------------------------------------
# Section 64: Replay evidence
# ---------------------------------------------------------------------------

class TestReplayScenarios:
    """Replay verification per spec section 64."""

    def test_fight_path_replay(self):
        """Fight path replay produces identical hash."""
        state = make_phase4_state()
        initial_state = GameState(**state.__dict__)
        state, events = run_to_post_search(state)
        
        # Continue fight path
        for i in range(2):
            fight = ActionIntent(
                action_id=f"act-fight-{i}", actor_id="player-1",
                action_type="FIGHT", params={}
            )
            result = execute_action(state, fight)
            events.extend(result.events)
            state = result.final_state
        
        extract = ActionIntent(
            action_id="act-extract", actor_id="player-1",
            action_type="EXTRACT", params={}
        )
        result = execute_action(state, extract)
        events.extend(result.events)
        live_hash = state_hash(result.final_state.__dict__)
        
        # Replay
        replay_result = verify_replay(initial_state, events, live_hash)
        assert replay_result.success, f"Replay failed: {replay_result.error_message}"
        assert replay_result.actual_hash == live_hash

    def test_flee_path_replay(self):
        """Flee path replay produces identical hash."""
        state = make_phase4_state()
        initial_state = GameState(**state.__dict__)
        state, events = run_to_post_search(state)
        
        # FLEE
        flee = ActionIntent(
            action_id="act-flee", actor_id="player-1",
            action_type="FLEE", params={}
        )
        result = execute_action(state, flee)
        events.extend(result.events)
        live_hash = state_hash(result.final_state.__dict__)
        
        # Replay
        replay_result = verify_replay(initial_state, events, live_hash)
        assert replay_result.success, f"Replay failed: {replay_result.error_message}"
        assert replay_result.actual_hash == live_hash

    def test_death_path_replay(self):
        """Death path replay produces identical hash."""
        state = make_phase4_state(hp=1)
        initial_state = GameState(**state.__dict__)
        state, events = run_to_post_search(state)
        
        # Fatal fight
        fight = ActionIntent(
            action_id="act-fight-fatal", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight)
        events.extend(result.events)
        live_hash = state_hash(result.final_state.__dict__)
        
        # Replay
        replay_result = verify_replay(initial_state, events, live_hash)
        assert replay_result.success, f"Replay failed: {replay_result.error_message}"
        assert replay_result.actual_hash == live_hash

    def test_fight_flee_hashes_differ(self):
        """Fight and flee paths produce different final hashes."""
        # Fight path
        fight_state = make_phase4_state()
        fight_initial = GameState(**fight_state.__dict__)
        fight_state, fight_events = run_to_post_search(fight_state)
        for i in range(2):
            fight = ActionIntent(
                action_id=f"act-fight-{i}", actor_id="player-1",
                action_type="FIGHT", params={}
            )
            result = execute_action(fight_state, fight)
            fight_events.extend(result.events)
            fight_state = result.final_state
        extract = ActionIntent(
            action_id="act-extract", actor_id="player-1",
            action_type="EXTRACT", params={}
        )
        result = execute_action(fight_state, extract)
        fight_events.extend(result.events)
        fight_hash = state_hash(result.final_state.__dict__)
        
        # Flee path
        flee_state = make_phase4_state()
        flee_initial = GameState(**flee_state.__dict__)
        flee_state, flee_events = run_to_post_search(flee_state)
        flee = ActionIntent(
            action_id="act-flee", actor_id="player-1",
            action_type="FLEE", params={}
        )
        result = execute_action(flee_state, flee)
        flee_events.extend(result.events)
        flee_hash = state_hash(result.final_state.__dict__)
        
        assert fight_hash != flee_hash
