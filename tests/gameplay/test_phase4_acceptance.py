"""Phase 4.1 acceptance integrity tests.

Tests canonical legality authority, encounter consistency invariants,
and reducer-level exploit resistance.
"""

import pytest
from tgn.core.models import GameState, DomainEvent
from tgn.core.hashing import state_hash
from tgn.core.reducer import reduce_event, ReducerError
from tgn.core.invariants import check_invariants, InvariantError
from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import (
    get_legal_actions,
    validate_action,
    execute_action,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_encounter_state(
    expedition_active=True,
    player_location="site-1",
    encounter_active=True,
    enemy_hp=4,
    player_hp=6,
    stamina=5,
):
    """Create configurable state for integrity tests."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="integrity-test",
        data={
            "player": {
                "location_id": player_location,
                "stamina": stamina,
                "max_stamina": 5,
                "hp": player_hp,
                "max_hp": 6,
                "attack": 2,
            },
            "inventory": {},
            "expedition": {
                "active": expedition_active,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": True,
                "target_loot": {},
                "carried_loot": {"salvage": 2},
                "encounter": {
                    "active": encounter_active,
                    "enemy_id": "enemy-1",
                    "enemy_hp": enemy_hp,
                    "enemy_max_hp": 4,
                    "enemy_attack": 2,
                },
            },
        },
    )


def make_post_search_state():
    """Create a real post-SEARCH state via actual execution."""
    state = GameState(
        schema_version=1, event_seq=0, decision_seq=0, game_minute=0,
        seed="integrity",
        data={
            "player": {
                "location_id": "base-1", "stamina": 5, "max_stamina": 5,
                "hp": 6, "max_hp": 6, "attack": 2,
            },
            "inventory": {},
            "expedition": {
                "active": False, "base_location_id": "base-1",
                "target_location_id": "site-1", "target_searched": False,
                "target_loot": {"salvage": 2}, "carried_loot": {},
                "encounter": {
                    "active": False, "enemy_id": "enemy-1",
                    "enemy_hp": 4, "enemy_max_hp": 4, "enemy_attack": 2,
                },
            },
        },
    )
    r = execute_action(state, ActionIntent("d", "p", "DROP", {}))
    state = r.final_state
    r = execute_action(state, ActionIntent("s", "p", "SEARCH", {}))
    return r.final_state


# ---------------------------------------------------------------------------
# Section 7: Canonical legality regression
# ---------------------------------------------------------------------------

class TestCanonicalLegality:
    """All three layers derive from get_legal_actions."""

    def test_wait_derives_from_canonical_source_during_encounter(self):
        """WAIT blocked at all layers because get_legal_actions excludes it."""
        state = make_post_search_state()
        
        # Layer 1: get_legal_actions does not contain WAIT
        legal = get_legal_actions(state)
        legal_types = {la.action_type for la in legal}
        assert "WAIT" not in legal_types
        
        # Layer 2: validate_action rejects with ACTION_NOT_LEGAL_IN_STATE
        wait_intent = ActionIntent(
            action_id="w", actor_id="p", action_type="WAIT", params={"minutes": 60}
        )
        validation = validate_action(state, wait_intent)
        assert not validation.valid
        assert any(e.code == "ACTION_NOT_LEGAL_IN_STATE" for e in validation.errors)
        
        # Layer 3: execute_action rejects for the same reason
        result = execute_action(state, wait_intent)
        assert not result.accepted
        assert result.final_state is None
        assert any(e.code == "ACTION_NOT_LEGAL_IN_STATE" for e in result.validation.errors)

    def test_dead_player_no_expedition_zero_actions(self):
        """Dead player with no expedition still has zero actions (Section 10)."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0, game_minute=0,
            seed="dead-no-exp",
            data={
                "player": {
                    "location_id": "base-1", "stamina": 3, "max_stamina": 3,
                    "hp": 0, "max_hp": 6, "attack": 2,
                },
                "inventory": {},
            },
        )
        legal = get_legal_actions(state)
        assert legal == ()


# ---------------------------------------------------------------------------
# Section 12: Encounter consistency invariant tests
# ---------------------------------------------------------------------------

class TestEncounterConsistencyInvariants:
    """State integrity tests for encounter consistency."""

    def test_case_a_encounter_active_expedition_inactive(self):
        """encounter.active=True + expedition.active=False must fail."""
        state = make_encounter_state(expedition_active=False, encounter_active=True)
        with pytest.raises(InvariantError, match="active expedition"):
            check_invariants(state)

    def test_case_b_encounter_active_player_at_base(self):
        """encounter.active=True + player at base must fail."""
        state = make_encounter_state(player_location="base-1", encounter_active=True)
        with pytest.raises(InvariantError, match="target"):
            check_invariants(state)

    def test_case_c_encounter_active_enemy_dead(self):
        """encounter.active=True + enemy_hp=0 must fail."""
        state = make_encounter_state(enemy_hp=0, encounter_active=True)
        with pytest.raises(InvariantError, match="dead enemy"):
            check_invariants(state)


# ---------------------------------------------------------------------------
# Section 15: Forged EXTRACT during encounter
# ---------------------------------------------------------------------------

class TestForgedExtractDuringEncounter:
    """Reducer rejects forged EXPEDITION_EXTRACTED during active encounter."""

    def test_forged_extract_rejected(self):
        """Syntactically valid EXTRACT event rejected when encounter active."""
        state = make_post_search_state()
        # State: encounter active, carried_loot={"salvage":2}
        assert state.data["expedition"]["encounter"]["active"] is True
        
        forged_event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="EXPEDITION_EXTRACTED",
            game_minute=state.game_minute + 15,
            decision_seq=state.decision_seq + 1,
            payload={
                "carried_loot": {"salvage": 2},
                "time": 15,
            },
        )
        
        with pytest.raises(ReducerError, match="encounter"):
            reduce_event(state, forged_event)
        
        # State unchanged
        assert state.data["inventory"] == {}
        assert state.data["expedition"]["carried_loot"] == {"salvage": 2}
        assert state.data["expedition"]["encounter"]["active"] is True
        assert state.event_seq == 2
        assert state.decision_seq == 2


# ---------------------------------------------------------------------------
# Section 17: Forged TIME_ADVANCED during encounter
# ---------------------------------------------------------------------------

class TestForgedTimeAdvancedDuringEncounter:
    """Reducer rejects forged TIME_ADVANCED during active encounter."""

    def test_forged_wait_rejected(self):
        """TIME_ADVANCED rejected when encounter active."""
        state = make_post_search_state()
        assert state.data["expedition"]["encounter"]["active"] is True
        
        forged_event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="TIME_ADVANCED",
            game_minute=state.game_minute + 60,
            decision_seq=state.decision_seq + 1,
            payload={"minutes": 60},
        )
        
        with pytest.raises(ReducerError, match="encounter"):
            reduce_event(state, forged_event)
        
        # State unchanged
        assert state.game_minute == 40  # DROP(10) + SEARCH(30)
        assert state.event_seq == 2


# ---------------------------------------------------------------------------
# Section 19: Forged remote COMBAT
# ---------------------------------------------------------------------------

class TestForgedRemoteCombat:
    """Reducer rejects COMBAT_RESOLVED from wrong location."""

    def test_combat_from_base_rejected(self):
        """Cannot fight remotely from base."""
        state = make_encounter_state(
            player_location="base-1",  # Wrong location
            expedition_active=True,
            encounter_active=False,  # Must be False for invariant to pass at base
        )
        # Manually set encounter active to simulate forged event attempt
        # But invariants would reject this state, so test reducer directly
        # with a state that has encounter active but player at base
        # The reducer should reject before invariants even run
        state.data["expedition"]["encounter"]["active"] = True
        
        forged_event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="COMBAT_RESOLVED",
            game_minute=state.game_minute + 10,
            decision_seq=state.decision_seq + 1,
            payload={
                "enemy_id": "enemy-1",
                "player_damage_dealt": 2,
                "enemy_damage_dealt": 2,
                "enemy_hp_after": 2,
                "player_hp_after": 4,
                "outcome": "ONGOING",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        
        with pytest.raises(ReducerError):
            reduce_event(state, forged_event)


# ---------------------------------------------------------------------------
# Section 20: Forged remote FLEE
# ---------------------------------------------------------------------------

class TestForgedRemoteFlee:
    """Reducer rejects EXPEDITION_FLED from wrong location."""

    def test_flee_from_base_rejected(self):
        """Cannot flee from base (not at target)."""
        state = make_encounter_state(
            player_location="base-1",
            expedition_active=True,
            encounter_active=False,
        )
        state.data["expedition"]["encounter"]["active"] = True
        
        forged_event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="EXPEDITION_FLED",
            game_minute=state.game_minute + 15,
            decision_seq=state.decision_seq + 1,
            payload={"time": 15},
        )
        
        with pytest.raises(ReducerError):
            reduce_event(state, forged_event)


# ---------------------------------------------------------------------------
# Section 29: Additional required behavioral tests
# ---------------------------------------------------------------------------

class TestAdditionalBehavioralContracts:
    """Additional required tests per Section 29."""

    def test_fight_requires_target_location_via_legal_actions(self):
        """FIGHT not offered when player not at target (via get_legal_actions)."""
        state = make_encounter_state(
            player_location="base-1",
            expedition_active=True,
            encounter_active=False,
        )
        # With encounter inactive at base, normal base logic applies
        legal = get_legal_actions(state)
        types = {la.action_type for la in legal}
        assert "FIGHT" not in types

    def test_active_encounter_at_correct_location_offers_fight_flee(self):
        """Active encounter at target with expedition active offers FIGHT/FLEE."""
        state = make_encounter_state(
            player_location="site-1",
            expedition_active=True,
            encounter_active=True,
            enemy_hp=4,
        )
        legal = get_legal_actions(state)
        types = {la.action_type for la in legal}
        assert "FIGHT" in types
        assert "FLEE" in types
        assert "WAIT" not in types
        assert "EXTRACT" not in types

    def test_forged_extract_state_immutability(self):
        """Rejected forged EXTRACT leaves state completely unchanged."""
        state = make_post_search_state()
        hash_before = state_hash(state.__dict__)
        
        forged_event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="EXPEDITION_EXTRACTED",
            game_minute=state.game_minute + 15,
            decision_seq=state.decision_seq + 1,
            payload={"carried_loot": {"salvage": 2}, "time": 15},
        )
        
        with pytest.raises(ReducerError):
            reduce_event(state, forged_event)
        
        hash_after = state_hash(state.__dict__)
        assert hash_before == hash_after

    def test_forged_time_advanced_state_immutability(self):
        """Rejected forged TIME_ADVANCED leaves state completely unchanged."""
        state = make_post_search_state()
        hash_before = state_hash(state.__dict__)
        
        forged_event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="TIME_ADVANCED",
            game_minute=state.game_minute + 60,
            decision_seq=state.decision_seq + 1,
            payload={"minutes": 60},
        )
        
        with pytest.raises(ReducerError):
            reduce_event(state, forged_event)
        
        hash_after = state_hash(state.__dict__)
        assert hash_before == hash_after
