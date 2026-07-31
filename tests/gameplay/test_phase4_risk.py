"""Phase 4 Risk contract tests: enemy / fight / flee / injury / death.

These tests define the Phase 4 contract BEFORE implementation.
They must fail (RED) until production code satisfies them.
"""

import pytest
from tgn.core.models import GameState, DomainEvent
from tgn.core.hashing import state_hash
from tgn.core.reducer import reduce_event, ReducerError
from tgn.core.invariants import InvariantError
from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import (
    get_legal_actions,
    validate_action,
    execute_action,
    build_observation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def phase4_base_state():
    """Phase 4 initial state at base with HP and encounter data."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="phase4-test",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 5,
                "max_stamina": 5,
                "hp": 6,
                "max_hp": 6,
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
                    "enemy_hp": 4,
                    "enemy_max_hp": 4,
                    "enemy_attack": 2,
                },
            },
        },
    )


@pytest.fixture
def phase4_post_search_state(phase4_base_state):
    """State after DROP + SEARCH: encounter active, loot carried."""
    state = phase4_base_state
    # DROP
    drop_intent = ActionIntent(
        action_id="act-drop", actor_id="player-1", action_type="DROP", params={}
    )
    result = execute_action(state, drop_intent)
    assert result.accepted, f"DROP failed: {result.validation.errors}"
    state = result.final_state

    # SEARCH
    search_intent = ActionIntent(
        action_id="act-search", actor_id="player-1", action_type="SEARCH", params={}
    )
    result = execute_action(state, search_intent)
    assert result.accepted, f"SEARCH failed: {result.validation.errors}"
    return result.final_state


@pytest.fixture
def phase4_low_hp_state(phase4_post_search_state):
    """Post-search state with player HP low enough to die in one fight."""
    state = phase4_post_search_state
    # Manually set hp low for death scenario (via state construction)
    state.data["player"]["hp"] = 1
    return state


# ---------------------------------------------------------------------------
# Section 33: Legal action state machine
# ---------------------------------------------------------------------------

class TestLegalActions:
    """Legal action state machine per spec section 33."""

    def test_initial_base_no_fight_flee(self, phase4_base_state):
        """At base: WAIT and DROP legal, no FIGHT/FLEE."""
        legal = get_legal_actions(phase4_base_state)
        types = {la.action_type for la in legal}
        assert "WAIT" in types
        assert "DROP" in types
        assert "FIGHT" not in types
        assert "FLEE" not in types

    def test_after_drop_before_search_no_fight_flee(self, phase4_base_state):
        """After DROP, before SEARCH: no FIGHT/FLEE (encounter not yet active)."""
        drop_intent = ActionIntent(
            action_id="act-drop", actor_id="player-1", action_type="DROP", params={}
        )
        result = execute_action(phase4_base_state, drop_intent)
        assert result.accepted
        state = result.final_state

        legal = get_legal_actions(state)
        types = {la.action_type for la in legal}
        assert "SEARCH" in types
        assert "EXTRACT" in types
        assert "FIGHT" not in types
        assert "FLEE" not in types

    def test_after_search_encounter_active_fight_flee(self, phase4_post_search_state):
        """After SEARCH with encounter: FIGHT and FLEE legal."""
        legal = get_legal_actions(phase4_post_search_state)
        types = {la.action_type for la in legal}
        assert "FIGHT" in types
        assert "FLEE" in types

    def test_encounter_blocks_wait_search_extract_drop(self, phase4_post_search_state):
        """During active encounter: WAIT, SEARCH, EXTRACT, DROP not legal."""
        legal = get_legal_actions(phase4_post_search_state)
        types = {la.action_type for la in legal}
        assert "WAIT" not in types
        assert "SEARCH" not in types
        assert "EXTRACT" not in types
        assert "DROP" not in types

    def test_after_enemy_defeat_extract_legal(self, phase4_post_search_state):
        """After enemy defeat: EXTRACT legal, FIGHT/FLEE not."""
        state = phase4_post_search_state
        # Fight until enemy dead (enemy_hp=4, player_attack=2 -> 2 fights)
        for i in range(2):
            intent = ActionIntent(
                action_id=f"act-fight-{i}", actor_id="player-1",
                action_type="FIGHT", params={}
            )
            result = execute_action(state, intent)
            assert result.accepted, f"FIGHT {i} failed: {result.validation.errors}"
            state = result.final_state

        legal = get_legal_actions(state)
        types = {la.action_type for la in legal}
        assert "EXTRACT" in types
        assert "FIGHT" not in types
        assert "FLEE" not in types
        assert "SEARCH" not in types

    def test_after_flee_at_base(self, phase4_post_search_state):
        """After FLEE: at base, expedition inactive, normal base actions."""
        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(phase4_post_search_state, flee_intent)
        assert result.accepted
        state = result.final_state

        legal = get_legal_actions(state)
        types = {la.action_type for la in legal}
        assert "WAIT" in types
        assert "FIGHT" not in types
        assert "FLEE" not in types

    def test_dead_player_no_actions(self, phase4_low_hp_state):
        """After death: no gameplay actions legal."""
        state = phase4_low_hp_state
        # enemy_attack=2, player_hp=1 -> one fight kills player
        fight_intent = ActionIntent(
            action_id="act-fight-fatal", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight_intent)
        assert result.accepted
        state = result.final_state

        # Player should be dead
        assert state.data["player"]["hp"] == 0

        legal = get_legal_actions(state)
        types = {la.action_type for la in legal}
        assert "FIGHT" not in types
        assert "FLEE" not in types
        assert "WAIT" not in types
        assert "DROP" not in types
        assert "SEARCH" not in types
        assert "EXTRACT" not in types


# ---------------------------------------------------------------------------
# Section 16: Hidden encounter information
# ---------------------------------------------------------------------------

class TestInformationBoundary:
    """Observation boundary per spec sections 16, 31, 32, 38."""

    def test_enemy_hidden_before_encounter(self, phase4_base_state):
        """Before encounter activation, enemy data not in observation."""
        obs = build_observation(phase4_base_state)
        assert "enemy" not in obs
        assert "encounter" not in obs or not obs.get("encounter", {}).get("active")

    def test_enemy_visible_during_encounter(self, phase4_post_search_state):
        """During active encounter, enemy state visible."""
        obs = build_observation(phase4_post_search_state)
        assert "enemy" in obs
        enemy = obs["enemy"]
        assert enemy["enemy_id"] == "enemy-1"
        assert enemy["enemy_hp"] == 4
        assert enemy["enemy_max_hp"] == 4
        assert enemy["enemy_attack"] == 2

    def test_hp_visible_in_observation(self, phase4_base_state):
        """Player HP visible in observation."""
        obs = build_observation(phase4_base_state)
        assert obs["hp"] == 6
        assert obs["max_hp"] == 6

    def test_no_future_result_in_observation(self, phase4_post_search_state):
        """Observation must not contain future combat result."""
        obs = build_observation(phase4_post_search_state)
        assert "future_outcome" not in obs
        assert "combat_result" not in obs


# ---------------------------------------------------------------------------
# Section 19-21: FIGHT resolution
# ---------------------------------------------------------------------------

class TestFightResolution:
    """Deterministic combat per spec sections 19-21."""

    def test_fight_deterministic_damage(self, phase4_post_search_state):
        """FIGHT deals player.attack to enemy, enemy retaliates if alive."""
        state = phase4_post_search_state
        # player attack=2, enemy hp=4, enemy attack=2
        fight_intent = ActionIntent(
            action_id="act-fight-1", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight_intent)
        assert result.accepted
        new_state = result.final_state

        # Enemy takes 2 damage: 4 -> 2
        assert new_state.data["expedition"]["encounter"]["enemy_hp"] == 2
        # Player takes 2 retaliation: 6 -> 4
        assert new_state.data["player"]["hp"] == 4

    def test_fight_enemy_defeated_no_retaliation(self, phase4_post_search_state):
        """When enemy dies from attack, no retaliation."""
        state = phase4_post_search_state
        # First fight: enemy 4->2, player 6->4
        fight1 = ActionIntent(
            action_id="act-fight-1", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight1)
        state = result.final_state

        # Second fight: enemy 2->0 (dead), no retaliation
        fight2 = ActionIntent(
            action_id="act-fight-2", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight2)
        new_state = result.final_state

        assert new_state.data["expedition"]["encounter"]["enemy_hp"] == 0
        assert new_state.data["expedition"]["encounter"]["active"] is False
        # Player HP unchanged from retaliation (enemy died)
        assert new_state.data["player"]["hp"] == 4

    def test_fight_produces_combat_resolved_event(self, phase4_post_search_state):
        """FIGHT produces COMBAT_RESOLVED event with correct payload."""
        fight_intent = ActionIntent(
            action_id="act-fight-1", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(phase4_post_search_state, fight_intent)
        assert result.accepted
        assert len(result.events) == 1
        event = result.events[0]
        assert event.event_type == "COMBAT_RESOLVED"
        assert event.payload["enemy_id"] == "enemy-1"
        assert event.payload["player_damage_dealt"] == 2
        assert event.payload["enemy_damage_dealt"] == 2
        assert event.payload["enemy_hp_after"] == 2
        assert event.payload["player_hp_after"] == 4
        assert event.payload["outcome"] == "ONGOING"

    def test_fight_outcome_enemy_defeated(self, phase4_post_search_state):
        """Final fight produces ENEMY_DEFEATED outcome."""
        state = phase4_post_search_state
        # Two fights to kill enemy (hp=4, attack=2)
        for i in range(2):
            intent = ActionIntent(
                action_id=f"act-fight-{i}", actor_id="player-1",
                action_type="FIGHT", params={}
            )
            result = execute_action(state, intent)
            state = result.final_state

        event = result.events[0]
        assert event.payload["outcome"] == "ENEMY_DEFEATED"

    def test_fight_time_and_stamina_cost(self, phase4_post_search_state):
        """FIGHT has deterministic time and stamina cost."""
        state = phase4_post_search_state
        minute_before = state.game_minute
        stamina_before = state.data["player"]["stamina"]

        fight_intent = ActionIntent(
            action_id="act-fight-1", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight_intent)
        new_state = result.final_state

        assert new_state.game_minute == minute_before + 10
        assert new_state.data["player"]["stamina"] == stamina_before - 1


# ---------------------------------------------------------------------------
# Section 23-26: FLEE resolution
# ---------------------------------------------------------------------------

class TestFleeResolution:
    """FLEE semantics per spec sections 23-26."""

    def test_flee_returns_to_base(self, phase4_post_search_state):
        """FLEE returns player to base."""
        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(phase4_post_search_state, flee_intent)
        assert result.accepted
        new_state = result.final_state
        assert new_state.data["player"]["location_id"] == "base-1"

    def test_flee_ends_expedition(self, phase4_post_search_state):
        """FLEE deactivates expedition."""
        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(phase4_post_search_state, flee_intent)
        new_state = result.final_state
        assert new_state.data["expedition"]["active"] is False

    def test_flee_discards_carried_loot(self, phase4_post_search_state):
        """FLEE discards all carried loot (section 25)."""
        state = phase4_post_search_state
        # Verify loot is carried before flee
        assert state.data["expedition"]["carried_loot"] == {"salvage": 2}

        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(state, flee_intent)
        new_state = result.final_state

        assert new_state.data["expedition"]["carried_loot"] == {}
        # Loot NOT added to inventory
        assert new_state.data["inventory"] == {}

    def test_flee_clears_encounter(self, phase4_post_search_state):
        """FLEE clears active encounter."""
        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(phase4_post_search_state, flee_intent)
        new_state = result.final_state
        assert new_state.data["expedition"]["encounter"]["active"] is False

    def test_flee_does_not_restore_target_loot(self, phase4_post_search_state):
        """FLEE does not restore target_loot for re-farming (section 26)."""
        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(phase4_post_search_state, flee_intent)
        new_state = result.final_state
        assert new_state.data["expedition"]["target_loot"] == {}
        assert new_state.data["expedition"]["target_searched"] is True

    def test_flee_time_cost(self, phase4_post_search_state):
        """FLEE advances time."""
        state = phase4_post_search_state
        minute_before = state.game_minute

        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(state, flee_intent)
        new_state = result.final_state
        assert new_state.game_minute == minute_before + 15


# ---------------------------------------------------------------------------
# Section 28-30: Player death
# ---------------------------------------------------------------------------

class TestPlayerDeath:
    """Death mechanics per spec sections 28-30."""

    def test_death_hp_zero(self, phase4_low_hp_state):
        """Player dies when HP reaches 0."""
        state = phase4_low_hp_state
        fight_intent = ActionIntent(
            action_id="act-fight-fatal", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight_intent)
        assert result.accepted
        new_state = result.final_state
        assert new_state.data["player"]["hp"] == 0

    def test_death_event_outcome(self, phase4_low_hp_state):
        """Fatal fight produces PLAYER_DIED outcome."""
        fight_intent = ActionIntent(
            action_id="act-fight-fatal", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(phase4_low_hp_state, fight_intent)
        event = result.events[0]
        assert event.payload["outcome"] == "PLAYER_DIED"

    def test_death_irreversible(self, phase4_low_hp_state):
        """Death is irreversible - no actions restore HP."""
        state = phase4_low_hp_state
        fight_intent = ActionIntent(
            action_id="act-fight-fatal", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight_intent)
        dead_state = result.final_state

        # No legal actions
        legal = get_legal_actions(dead_state)
        assert len(legal) == 0

    def test_death_preserves_history(self, phase4_low_hp_state):
        """Death preserves event history for replay."""
        state = phase4_low_hp_state
        fight_intent = ActionIntent(
            action_id="act-fight-fatal", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight_intent)
        # Event exists and contains death info
        event = result.events[0]
        assert event.event_type == "COMBAT_RESOLVED"
        assert event.payload["player_hp_after"] == 0


# ---------------------------------------------------------------------------
# Section 40: Fight vs Flee divergence
# ---------------------------------------------------------------------------

class TestBranchDivergence:
    """Fight and Flee produce meaningfully different states (section 40)."""

    def test_fight_flee_different_hashes(self, phase4_post_search_state):
        """Same post-SEARCH state, FIGHT path vs FLEE path -> different hashes."""
        state = phase4_post_search_state

        # Branch A: Fight (2 fights to kill, then extract)
        fight_state = state
        for i in range(2):
            intent = ActionIntent(
                action_id=f"act-fight-{i}", actor_id="player-1",
                action_type="FIGHT", params={}
            )
            result = execute_action(fight_state, intent)
            fight_state = result.final_state
        # Extract
        extract_intent = ActionIntent(
            action_id="act-extract", actor_id="player-1",
            action_type="EXTRACT", params={}
        )
        result = execute_action(fight_state, extract_intent)
        fight_final = result.final_state

        # Branch B: Flee
        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(state, flee_intent)
        flee_final = result.final_state

        hash_fight = state_hash(fight_final.__dict__)
        hash_flee = state_hash(flee_final.__dict__)

        assert hash_fight != hash_flee

    def test_fight_preserves_loot_flee_loses_it(self, phase4_post_search_state):
        """FIGHT path can bank loot; FLEE path cannot."""
        state = phase4_post_search_state

        # Fight path
        fight_state = state
        for i in range(2):
            intent = ActionIntent(
                action_id=f"act-fight-{i}", actor_id="player-1",
                action_type="FIGHT", params={}
            )
            result = execute_action(fight_state, intent)
            fight_state = result.final_state
        extract_intent = ActionIntent(
            action_id="act-extract", actor_id="player-1",
            action_type="EXTRACT", params={}
        )
        result = execute_action(fight_state, extract_intent)
        fight_final = result.final_state
        assert fight_final.data["inventory"] == {"salvage": 2}

        # Flee path
        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(state, flee_intent)
        flee_final = result.final_state
        assert flee_final.data["inventory"] == {}


# ---------------------------------------------------------------------------
# Section 44: Tamper / exploit tests
# ---------------------------------------------------------------------------

class TestTamperResistance:
    """Exploit and forgery resistance per spec section 44."""

    def test_fight_without_encounter_rejected(self, phase4_base_state):
        """FIGHT without active encounter is rejected."""
        # At base, no encounter
        fight_intent = ActionIntent(
            action_id="act-fight", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(phase4_base_state, fight_intent)
        assert not result.accepted
        assert result.final_state is None

    def test_fight_while_dead_rejected(self, phase4_low_hp_state):
        """FIGHT while dead is rejected."""
        state = phase4_low_hp_state
        # Kill player first
        fight_intent = ActionIntent(
            action_id="act-fight-fatal", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight_intent)
        dead_state = result.final_state

        # Try to fight again
        fight_again = ActionIntent(
            action_id="act-fight-again", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(dead_state, fight_again)
        assert not result.accepted

    def test_flee_without_encounter_rejected(self, phase4_base_state):
        """FLEE without active encounter is rejected."""
        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(phase4_base_state, flee_intent)
        assert not result.accepted

    def test_wait_during_encounter_rejected(self, phase4_post_search_state):
        """WAIT during active encounter is rejected."""
        wait_intent = ActionIntent(
            action_id="act-wait", actor_id="player-1",
            action_type="WAIT", params={"minutes": 60}
        )
        result = execute_action(phase4_post_search_state, wait_intent)
        assert not result.accepted

    def test_extract_during_encounter_rejected(self, phase4_post_search_state):
        """EXTRACT during active encounter is rejected."""
        extract_intent = ActionIntent(
            action_id="act-extract", actor_id="player-1",
            action_type="EXTRACT", params={}
        )
        result = execute_action(phase4_post_search_state, extract_intent)
        assert not result.accepted

    def test_forged_combat_event_wrong_damage(self, phase4_post_search_state):
        """Reducer rejects forged COMBAT_RESOLVED with wrong damage."""
        state = phase4_post_search_state
        forged_event = DomainEvent(
            event_seq=state.event_seq + 1,
            event_type="COMBAT_RESOLVED",
            game_minute=state.game_minute + 10,
            decision_seq=state.decision_seq + 1,
            payload={
                "enemy_id": "enemy-1",
                "player_damage_dealt": 9999,  # forged
                "enemy_damage_dealt": 0,
                "enemy_hp_after": 0,
                "player_hp_after": 6,
                "outcome": "ENEMY_DEFEATED",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        with pytest.raises(ReducerError):
            reduce_event(state, forged_event)

    def test_forged_combat_event_no_encounter(self, phase4_base_state):
        """Reducer rejects COMBAT_RESOLVED when no encounter active."""
        state = phase4_base_state
        # Need to be on expedition for this to make sense
        drop_intent = ActionIntent(
            action_id="act-drop", actor_id="player-1", action_type="DROP", params={}
        )
        result = execute_action(state, drop_intent)
        state = result.final_state

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

    def test_flee_loot_banking_exploit(self, phase4_post_search_state):
        """FLEE cannot bank loot to inventory."""
        flee_intent = ActionIntent(
            action_id="act-flee", actor_id="player-1", action_type="FLEE", params={}
        )
        result = execute_action(phase4_post_search_state, flee_intent)
        new_state = result.final_state
        # No loot in inventory
        assert new_state.data["inventory"] == {}
        # No carried loot survives
        assert new_state.data["expedition"]["carried_loot"] == {}

    def test_death_then_action_rejected(self, phase4_low_hp_state):
        """No action possible after death."""
        state = phase4_low_hp_state
        fight_intent = ActionIntent(
            action_id="act-fight-fatal", actor_id="player-1",
            action_type="FIGHT", params={}
        )
        result = execute_action(state, fight_intent)
        dead_state = result.final_state

        # Try WAIT
        wait_intent = ActionIntent(
            action_id="act-wait", actor_id="player-1",
            action_type="WAIT", params={"minutes": 60}
        )
        result = execute_action(dead_state, wait_intent)
        assert not result.accepted

        # Try DROP
        drop_intent = ActionIntent(
            action_id="act-drop", actor_id="player-1",
            action_type="DROP", params={}
        )
        result = execute_action(dead_state, drop_intent)
        assert not result.accepted

    def test_boolean_hp_rejected_by_invariant(self):
        """Boolean HP is rejected by invariants."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0, game_minute=0,
            seed="test",
            data={
                "player": {
                    "location_id": "base-1",
                    "stamina": 3, "max_stamina": 3,
                    "hp": True, "max_hp": 6, "attack": 2,
                },
                "inventory": {},
                "expedition": {
                    "active": False,
                    "base_location_id": "base-1",
                    "target_location_id": "site-1",
                    "target_searched": False,
                    "target_loot": {},
                    "carried_loot": {},
                    "encounter": {
                        "active": False,
                        "enemy_id": "enemy-1",
                        "enemy_hp": 4, "enemy_max_hp": 4, "enemy_attack": 2,
                    },
                },
            },
        )
        from tgn.core.invariants import check_invariants
        with pytest.raises(InvariantError):
            check_invariants(state)


# ---------------------------------------------------------------------------
# Section 36: Invariants
# ---------------------------------------------------------------------------

class TestPhase4Invariants:
    """Phase 4 invariant checks per spec section 36."""

    def test_hp_range_invariant(self):
        """HP must be 0 <= hp <= max_hp."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0, game_minute=0,
            seed="test",
            data={
                "player": {
                    "location_id": "base-1",
                    "stamina": 3, "max_stamina": 3,
                    "hp": 7, "max_hp": 6, "attack": 2,  # hp > max_hp
                },
                "inventory": {},
                "expedition": {
                    "active": False,
                    "base_location_id": "base-1",
                    "target_location_id": "site-1",
                    "target_searched": False,
                    "target_loot": {},
                    "carried_loot": {},
                    "encounter": {
                        "active": False,
                        "enemy_id": "enemy-1",
                        "enemy_hp": 4, "enemy_max_hp": 4, "enemy_attack": 2,
                    },
                },
            },
        )
        from tgn.core.invariants import check_invariants
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_negative_enemy_hp_invariant(self):
        """Enemy HP cannot be negative."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0, game_minute=0,
            seed="test",
            data={
                "player": {
                    "location_id": "base-1",
                    "stamina": 3, "max_stamina": 3,
                    "hp": 6, "max_hp": 6, "attack": 2,
                },
                "inventory": {},
                "expedition": {
                    "active": False,
                    "base_location_id": "base-1",
                    "target_location_id": "site-1",
                    "target_searched": False,
                    "target_loot": {},
                    "carried_loot": {},
                    "encounter": {
                        "active": False,
                        "enemy_id": "enemy-1",
                        "enemy_hp": -1, "enemy_max_hp": 4, "enemy_attack": 2,
                    },
                },
            },
        )
        from tgn.core.invariants import check_invariants
        with pytest.raises(InvariantError):
            check_invariants(state)

    def test_active_encounter_cannot_have_dead_enemy(self):
        """Active encounter cannot have enemy_hp <= 0."""
        state = GameState(
            schema_version=1, event_seq=0, decision_seq=0, game_minute=0,
            seed="test",
            data={
                "player": {
                    "location_id": "site-1",
                    "stamina": 3, "max_stamina": 3,
                    "hp": 6, "max_hp": 6, "attack": 2,
                },
                "inventory": {},
                "expedition": {
                    "active": True,
                    "base_location_id": "base-1",
                    "target_location_id": "site-1",
                    "target_searched": True,
                    "target_loot": {},
                    "carried_loot": {"salvage": 2},
                    "encounter": {
                        "active": True,
                        "enemy_id": "enemy-1",
                        "enemy_hp": 0, "enemy_max_hp": 4, "enemy_attack": 2,
                    },
                },
            },
        )
        from tgn.core.invariants import check_invariants
        with pytest.raises(InvariantError):
            check_invariants(state)
