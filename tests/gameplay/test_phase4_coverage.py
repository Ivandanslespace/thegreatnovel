"""Phase 4 additional coverage tests for invariants and reducer edge cases."""

import pytest

from tgn.core.models import GameState, DomainEvent
from tgn.core.reducer import reduce_event, ReducerError
from tgn.core.invariants import check_invariants, InvariantError
from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import execute_action, get_legal_actions


def make_state_with_encounter(active=True, enemy_hp=4, player_hp=6, stamina=5):
    """Create state with encounter for testing."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="coverage-test",
        data={
            "player": {
                "location_id": "site-1" if active else "base-1",
                "stamina": stamina,
                "max_stamina": 5,
                "hp": player_hp,
                "max_hp": 6,
                "attack": 2,
            },
            "inventory": {},
            "expedition": {
                "active": active,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": active,
                "target_loot": {},
                "carried_loot": {"salvage": 2} if active else {},
                "encounter": {
                    "active": active,
                    "enemy_id": "enemy-1",
                    "enemy_hp": enemy_hp,
                    "enemy_max_hp": 4,
                    "enemy_attack": 2,
                },
            },
        },
    )


class TestReducerEdgeCases:
    """Cover reducer error paths."""

    def test_combat_wrong_time_cost(self):
        """Reducer rejects wrong time cost in COMBAT_RESOLVED."""
        state = make_state_with_encounter(active=True)
        event = DomainEvent(
            event_seq=1,
            event_type="COMBAT_RESOLVED",
            game_minute=10,
            decision_seq=1,
            payload={
                "enemy_id": "enemy-1",
                "player_damage_dealt": 2,
                "enemy_damage_dealt": 2,
                "enemy_hp_after": 2,
                "player_hp_after": 4,
                "outcome": "ONGOING",
                "time": 99,  # Wrong
                "stamina_cost": 1,
            },
        )
        with pytest.raises(ReducerError, match="time cost"):
            reduce_event(state, event)

    def test_combat_wrong_stamina_cost(self):
        """Reducer rejects wrong stamina cost in COMBAT_RESOLVED."""
        state = make_state_with_encounter(active=True)
        event = DomainEvent(
            event_seq=1,
            event_type="COMBAT_RESOLVED",
            game_minute=10,
            decision_seq=1,
            payload={
                "enemy_id": "enemy-1",
                "player_damage_dealt": 2,
                "enemy_damage_dealt": 2,
                "enemy_hp_after": 2,
                "player_hp_after": 4,
                "outcome": "ONGOING",
                "time": 10,
                "stamina_cost": 99,  # Wrong
            },
        )
        with pytest.raises(ReducerError, match="stamina cost"):
            reduce_event(state, event)

    def test_combat_wrong_enemy_id(self):
        """Reducer rejects wrong enemy_id in COMBAT_RESOLVED."""
        state = make_state_with_encounter(active=True)
        event = DomainEvent(
            event_seq=1,
            event_type="COMBAT_RESOLVED",
            game_minute=10,
            decision_seq=1,
            payload={
                "enemy_id": "wrong-enemy",  # Wrong
                "player_damage_dealt": 2,
                "enemy_damage_dealt": 2,
                "enemy_hp_after": 2,
                "player_hp_after": 4,
                "outcome": "ONGOING",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        with pytest.raises(ReducerError, match="Enemy ID"):
            reduce_event(state, event)

    def test_combat_insufficient_stamina(self):
        """Reducer rejects combat with insufficient stamina."""
        state = make_state_with_encounter(active=True, stamina=0)
        event = DomainEvent(
            event_seq=1,
            event_type="COMBAT_RESOLVED",
            game_minute=10,
            decision_seq=1,
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
        with pytest.raises(ReducerError, match="stamina"):
            reduce_event(state, event)

    def test_flee_wrong_time_cost(self):
        """Reducer rejects wrong time cost in EXPEDITION_FLED."""
        state = make_state_with_encounter(active=True)
        event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_FLED",
            game_minute=15,
            decision_seq=1,
            payload={"time": 99},  # Wrong
        )
        with pytest.raises(ReducerError, match="time cost"):
            reduce_event(state, event)

    def test_flee_no_expedition(self):
        """Reducer rejects FLEE when expedition not active."""
        state = make_state_with_encounter(active=False)
        state.data["expedition"]["encounter"]["active"] = True
        event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_FLED",
            game_minute=15,
            decision_seq=1,
            payload={"time": 15},
        )
        with pytest.raises(ReducerError, match="expedition not active"):
            reduce_event(state, event)

    def test_flee_no_encounter(self):
        """Reducer rejects FLEE when no active encounter."""
        state = make_state_with_encounter(active=True)
        state.data["expedition"]["encounter"]["active"] = False
        event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_FLED",
            game_minute=15,
            decision_seq=1,
            payload={"time": 15},
        )
        with pytest.raises(ReducerError, match="no active encounter"):
            reduce_event(state, event)

    def test_flee_dead_player(self):
        """Reducer rejects FLEE when player is dead."""
        state = make_state_with_encounter(active=True, player_hp=0)
        event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_FLED",
            game_minute=15,
            decision_seq=1,
            payload={"time": 15},
        )
        with pytest.raises(ReducerError, match="dead"):
            reduce_event(state, event)

    def test_combat_dead_player(self):
        """Reducer rejects COMBAT_RESOLVED when player is dead."""
        state = make_state_with_encounter(active=True, player_hp=0)
        event = DomainEvent(
            event_seq=1,
            event_type="COMBAT_RESOLVED",
            game_minute=10,
            decision_seq=1,
            payload={
                "enemy_id": "enemy-1",
                "player_damage_dealt": 2,
                "enemy_damage_dealt": 0,
                "enemy_hp_after": 2,
                "player_hp_after": 0,
                "outcome": "ONGOING",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        with pytest.raises(ReducerError, match="dead"):
            reduce_event(state, event)

    def test_combat_enemy_already_dead(self):
        """Reducer rejects COMBAT_RESOLVED when enemy already dead."""
        state = make_state_with_encounter(active=True, enemy_hp=0)
        state.data["expedition"]["encounter"]["active"] = False
        event = DomainEvent(
            event_seq=1,
            event_type="COMBAT_RESOLVED",
            game_minute=10,
            decision_seq=1,
            payload={
                "enemy_id": "enemy-1",
                "player_damage_dealt": 2,
                "enemy_damage_dealt": 0,
                "enemy_hp_after": 0,
                "player_hp_after": 6,
                "outcome": "ENEMY_DEFEATED",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        with pytest.raises(ReducerError, match="encounter"):
            reduce_event(state, event)


class TestInvariantEdgeCases:
    """Cover invariant error paths."""

    def test_negative_hp(self):
        """Invariant rejects negative HP."""
        state = make_state_with_encounter(active=False, player_hp=-1)
        with pytest.raises(InvariantError, match="non-negative"):
            check_invariants(state)

    def test_bool_max_hp(self):
        """Invariant rejects boolean max_hp."""
        state = make_state_with_encounter(active=False)
        state.data["player"]["max_hp"] = True
        with pytest.raises(InvariantError, match="bool"):
            check_invariants(state)

    def test_bool_attack(self):
        """Invariant rejects boolean attack."""
        state = make_state_with_encounter(active=False)
        state.data["player"]["attack"] = True
        with pytest.raises(InvariantError, match="bool"):
            check_invariants(state)

    def test_negative_attack(self):
        """Invariant rejects negative attack."""
        state = make_state_with_encounter(active=False)
        state.data["player"]["attack"] = -1
        with pytest.raises(InvariantError, match="non-negative"):
            check_invariants(state)

    def test_bool_enemy_hp(self):
        """Invariant rejects boolean enemy_hp."""
        state = make_state_with_encounter(active=False)
        state.data["expedition"]["encounter"]["enemy_hp"] = True
        with pytest.raises(InvariantError, match="bool"):
            check_invariants(state)

    def test_bool_enemy_max_hp(self):
        """Invariant rejects boolean enemy_max_hp."""
        state = make_state_with_encounter(active=False)
        state.data["expedition"]["encounter"]["enemy_max_hp"] = True
        with pytest.raises(InvariantError, match="bool"):
            check_invariants(state)

    def test_negative_enemy_max_hp(self):
        """Invariant rejects non-positive enemy_max_hp."""
        state = make_state_with_encounter(active=False)
        state.data["expedition"]["encounter"]["enemy_max_hp"] = 0
        with pytest.raises(InvariantError, match="positive"):
            check_invariants(state)

    def test_bool_enemy_attack(self):
        """Invariant rejects boolean enemy_attack."""
        state = make_state_with_encounter(active=False)
        state.data["expedition"]["encounter"]["enemy_attack"] = True
        with pytest.raises(InvariantError, match="bool"):
            check_invariants(state)

    def test_negative_enemy_attack(self):
        """Invariant rejects negative enemy_attack."""
        state = make_state_with_encounter(active=False)
        state.data["expedition"]["encounter"]["enemy_attack"] = -1
        with pytest.raises(InvariantError, match="non-negative"):
            check_invariants(state)

    def test_non_int_hp(self):
        """Invariant rejects non-int HP."""
        state = make_state_with_encounter(active=False)
        state.data["player"]["hp"] = "six"
        with pytest.raises(InvariantError, match="int"):
            check_invariants(state)

    def test_non_int_attack(self):
        """Invariant rejects non-int attack."""
        state = make_state_with_encounter(active=False)
        state.data["player"]["attack"] = 2.5
        with pytest.raises(InvariantError, match="int"):
            check_invariants(state)


class TestExpeditionEdgeCases:
    """Cover expedition.py edge cases."""

    def test_fight_with_params_rejected(self):
        """FIGHT with unexpected params is rejected."""
        state = make_state_with_encounter(active=True)
        intent = ActionIntent(
            action_id="act-fight", actor_id="player-1",
            action_type="FIGHT", params={"power": 999}
        )
        result = execute_action(state, intent)
        assert not result.accepted
        assert any("UNEXPECTED_PARAMETER" in str(e.code) for e in result.validation.errors)

    def test_flee_with_params_rejected(self):
        """FLEE with unexpected params is rejected."""
        state = make_state_with_encounter(active=True)
        intent = ActionIntent(
            action_id="act-flee", actor_id="player-1",
            action_type="FLEE", params={"speed": 100}
        )
        result = execute_action(state, intent)
        assert not result.accepted
        assert any("UNEXPECTED_PARAMETER" in str(e.code) for e in result.validation.errors)

    def test_unknown_action_rejected(self):
        """Unknown action type is rejected."""
        state = make_state_with_encounter(active=True)
        intent = ActionIntent(
            action_id="act-unknown", actor_id="player-1",
            action_type="CAST_SPELL", params={}
        )
        result = execute_action(state, intent)
        assert not result.accepted
        assert any("UNKNOWN_ACTION" in str(e.code) for e in result.validation.errors)

    def test_fight_not_legal_without_stamina(self):
        """FIGHT not legal when stamina insufficient."""
        state = make_state_with_encounter(active=True, stamina=0)
        legal = get_legal_actions(state)
        types = {la.action_type for la in legal}
        assert "FIGHT" not in types
        assert "FLEE" in types  # FLEE has no stamina cost


class TestReducerDirectPaths:
    """Direct reducer tests to cover error paths."""

    def test_unknown_event_type(self):
        """Reducer rejects unknown event type."""
        state = make_state_with_encounter(active=False)
        event = DomainEvent(
            event_seq=1,
            event_type="UNKNOWN_EVENT",
            game_minute=0,
            decision_seq=1,
            payload={},
        )
        with pytest.raises(ReducerError, match="Unknown event type"):
            reduce_event(state, event)

    def test_drop_not_at_base(self):
        """Reducer rejects DROP when not at base."""
        state = make_state_with_encounter(active=False)
        state.data["player"]["location_id"] = "somewhere-else"
        event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_DROPPED",
            game_minute=10,
            decision_seq=1,
            payload={"destination": "site-1", "time": 10, "stamina_cost": 1},
        )
        with pytest.raises(ReducerError, match="not at base"):
            reduce_event(state, event)

    def test_drop_target_already_searched(self):
        """Reducer rejects DROP when target already searched."""
        state = make_state_with_encounter(active=False)
        state.data["expedition"]["target_searched"] = True
        event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_DROPPED",
            game_minute=10,
            decision_seq=1,
            payload={"destination": "site-1", "time": 10, "stamina_cost": 1},
        )
        with pytest.raises(ReducerError, match="already searched"):
            reduce_event(state, event)

    def test_drop_insufficient_stamina(self):
        """Reducer rejects DROP with insufficient stamina."""
        state = make_state_with_encounter(active=False, stamina=0)
        event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_DROPPED",
            game_minute=10,
            decision_seq=1,
            payload={"destination": "site-1", "time": 10, "stamina_cost": 1},
        )
        with pytest.raises(ReducerError, match="stamina"):
            reduce_event(state, event)

    def test_invariant_violation_after_event(self):
        """Reducer raises error when invariant violated after event."""
        # Create a state that will violate invariants after modification
        state = make_state_with_encounter(active=True)
        # This event would make enemy_hp negative which violates invariant
        event = DomainEvent(
            event_seq=1,
            event_type="COMBAT_RESOLVED",
            game_minute=10,
            decision_seq=1,
            payload={
                "enemy_id": "enemy-1",
                "player_damage_dealt": 999,  # Would make enemy_hp very negative
                "enemy_damage_dealt": 0,
                "enemy_hp_after": -995,  # Negative - violates invariant
                "player_hp_after": 6,
                "outcome": "ENEMY_DEFEATED",
                "time": 10,
                "stamina_cost": 1,
            },
        )
        # The reducer computes new_enemy_hp = max(0, 4-999) = 0
        # But payload says -995, so forgery check fails first
        with pytest.raises(ReducerError):
            reduce_event(state, event)

    def test_flee_game_minute_mismatch(self):
        """Reducer rejects FLEE with wrong game_minute."""
        state = make_state_with_encounter(active=True)
        event = DomainEvent(
            event_seq=1,
            event_type="EXPEDITION_FLED",
            game_minute=999,  # Wrong
            decision_seq=1,
            payload={"time": 15},
        )
        with pytest.raises(ReducerError, match="minute"):
            reduce_event(state, event)

    def test_combat_game_minute_mismatch(self):
        """Reducer rejects COMBAT with wrong game_minute."""
        state = make_state_with_encounter(active=True)
        event = DomainEvent(
            event_seq=1,
            event_type="COMBAT_RESOLVED",
            game_minute=999,  # Wrong
            decision_seq=1,
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
        with pytest.raises(ReducerError, match="minute"):
            reduce_event(state, event)

    def test_combat_forged_outcome(self):
        """Reducer rejects forged outcome."""
        state = make_state_with_encounter(active=True)
        event = DomainEvent(
            event_seq=1,
            event_type="COMBAT_RESOLVED",
            game_minute=10,
            decision_seq=1,
            payload={
                "enemy_id": "enemy-1",
                "player_damage_dealt": 2,
                "enemy_damage_dealt": 2,
                "enemy_hp_after": 2,
                "player_hp_after": 4,
                "outcome": "ENEMY_DEFEATED",  # Wrong - should be ONGOING
                "time": 10,
                "stamina_cost": 1,
            },
        )
        with pytest.raises(ReducerError, match="outcome"):
            reduce_event(state, event)
