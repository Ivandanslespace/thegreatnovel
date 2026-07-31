"""Phase 5 autoplay and persistence/replay acceptance tests."""

import pytest
from typing import Any

from tgn.core.models import GameState, DomainEvent
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import build_observation
from tgn.autoplay.runner import run_autoplay
from tgn.autoplay.models import AutoplayConfig, StopReason
from tgn.actions.models import ActionIntent
from tgn.storage.replay import replay_events


PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120,
    "boundary_minute": 60,
    "phase_before": "DAY",
    "phase_after": "NIGHT",
    "blocked_actions_by_phase": {
        "NIGHT": ["DROP"],
    },
}


def _make_phase5_state(game_minute: int = 55) -> GameState:
    """Phase-5-enabled state starting at minute 55 (DAY, near boundary)."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=game_minute,
        seed="phase5-autoplay",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 3,
                "max_stamina": 3,
                "hp": 10,
                "max_hp": 10,
                "attack": 5,
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
            "phase_cycle": dict(PHASE_CYCLE_CONFIG),
        },
    )


# --- Scripted autoplay acceptance scenario (spec #45) ---

def _phase5_policy(observation: dict[str, Any], decision: int, actor_id: str) -> ActionIntent | None:
    """
    Deterministic Phase 5 test policy.
    
    Decision 1: WAIT 10 (cross DAY→NIGHT)
    Decision 2: WAIT 55 (cross NIGHT→DAY)
    Then stop.
    
    Consumes only observation fields (spec #46).
    """
    if decision == 1:
        return ActionIntent(
            action_id=f"p5-wait-1",
            actor_id=actor_id,
            action_type="WAIT",
            params={"minutes": 10},
        )
    elif decision == 2:
        return ActionIntent(
            action_id=f"p5-wait-2",
            actor_id=actor_id,
            action_type="WAIT",
            params={"minutes": 55},
        )
    return None


class TestScriptedAutoplay:
    def test_autoplay_crosses_both_phase_boundaries(self):
        state = _make_phase5_state(55)
        config = AutoplayConfig(max_decisions=10, actor_id="phase5-bot")
        result = run_autoplay(state, _phase5_policy, config)

        assert result.completed is True
        assert result.stop_reason == StopReason.POLICY_COMPLETE
        assert result.decisions == 2
        assert result.events == 2

    def test_autoplay_observes_day_night_day(self):
        state = _make_phase5_state(55)
        config = AutoplayConfig(max_decisions=10, actor_id="phase5-bot")
        result = run_autoplay(state, _phase5_policy, config)

        # Frame 1: starts DAY, ends NIGHT
        frame1 = result.frames[0]
        assert frame1.observation_before["world_phase"] == "DAY"
        assert frame1.observation_after["world_phase"] == "NIGHT"

        # Frame 2: starts NIGHT, ends DAY
        frame2 = result.frames[1]
        assert frame2.observation_before["world_phase"] == "NIGHT"
        assert frame2.observation_after["world_phase"] == "DAY"

    def test_autoplay_no_rejected_actions(self):
        state = _make_phase5_state(55)
        config = AutoplayConfig(max_decisions=10, actor_id="phase5-bot")
        result = run_autoplay(state, _phase5_policy, config)
        assert result.rejection is None

    def test_autoplay_time_monotonic(self):
        state = _make_phase5_state(55)
        config = AutoplayConfig(max_decisions=10, actor_id="phase5-bot")
        result = run_autoplay(state, _phase5_policy, config)

        minutes = [55]  # initial
        for frame in result.frames:
            minutes.append(frame.game_minute_after)
        for i in range(1, len(minutes)):
            assert minutes[i] > minutes[i - 1]

    def test_autoplay_state_hashes_deterministic(self):
        """Two identical runs produce identical final hashes."""
        state1 = _make_phase5_state(55)
        state2 = _make_phase5_state(55)
        config = AutoplayConfig(max_decisions=10, actor_id="phase5-bot")

        result1 = run_autoplay(state1, _phase5_policy, config)
        result2 = run_autoplay(state2, _phase5_policy, config)

        assert result1.final_state_hash == result2.final_state_hash

    def test_autoplay_drop_disappears_at_night(self):
        """After crossing to NIGHT, DROP absent from legal actions."""
        state = _make_phase5_state(55)
        config = AutoplayConfig(max_decisions=10, actor_id="phase5-bot")
        result = run_autoplay(state, _phase5_policy, config)

        # After frame 1 (minute 65, NIGHT)
        frame1_after = result.frames[0].observation_after
        legal_types = [la.action_type for la in frame1_after["legal_actions"]]
        assert "DROP" not in legal_types

    def test_autoplay_drop_reappears_at_day(self):
        """After crossing back to DAY, DROP reappears."""
        state = _make_phase5_state(55)
        config = AutoplayConfig(max_decisions=10, actor_id="phase5-bot")
        result = run_autoplay(state, _phase5_policy, config)

        # After frame 2 (minute 120, DAY)
        frame2_after = result.frames[1].observation_after
        legal_types = [la.action_type for la in frame2_after["legal_actions"]]
        assert "DROP" in legal_types


# --- Persistence / replay acceptance (spec #47) ---

class TestReplayAcrossBoundaries:
    def test_replay_matches_across_phase_boundaries(self):
        """Replay from events reproduces identical final state hash."""
        state = _make_phase5_state(55)
        config = AutoplayConfig(max_decisions=10, actor_id="phase5-bot")
        result = run_autoplay(state, _phase5_policy, config)

        # Collect events from frames
        # Re-execute to get actual DomainEvent objects
        from tgn.gameplay.expedition import execute_action
        from tgn.actions.models import ActionIntent

        replay_state = _make_phase5_state(55)
        events = []

        # Decision 1: WAIT 10
        intent1 = ActionIntent(
            action_id="p5-wait-1", actor_id="phase5-bot",
            action_type="WAIT", params={"minutes": 10},
        )
        r1 = execute_action(replay_state, intent1)
        assert r1.accepted
        events.append(r1.events[0])
        replay_state = r1.final_state

        # Decision 2: WAIT 55
        intent2 = ActionIntent(
            action_id="p5-wait-2", actor_id="phase5-bot",
            action_type="WAIT", params={"minutes": 55},
        )
        r2 = execute_action(replay_state, intent2)
        assert r2.accepted
        events.append(r2.events[0])
        replay_state = r2.final_state

        original_final_hash = state_hash(replay_state.__dict__)

        # Now replay from initial state using events
        initial = _make_phase5_state(55)
        replay_result = replay_events(initial, events)
        assert replay_result.success is True
        assert replay_result.actual_hash == original_final_hash

    def test_deterministic_final_state_hash(self):
        """Two identical sequences produce identical hashes (spec #48)."""
        def run_sequence():
            from tgn.gameplay.expedition import execute_action
            s = _make_phase5_state(55)
            i1 = ActionIntent(
                action_id="w1", actor_id="p1",
                action_type="WAIT", params={"minutes": 10},
            )
            r1 = execute_action(s, i1)
            s = r1.final_state
            i2 = ActionIntent(
                action_id="w2", actor_id="p1",
                action_type="WAIT", params={"minutes": 55},
            )
            r2 = execute_action(s, i2)
            return state_hash(r2.final_state.__dict__)

        assert run_sequence() == run_sequence()
