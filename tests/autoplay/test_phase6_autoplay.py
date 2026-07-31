"""Phase 6 autoplay, replay, and SQLite persistence acceptance tests."""

import pytest
from typing import Any

from tgn.core.models import GameState
from tgn.core.hashing import state_hash
from tgn.gameplay.expedition import build_observation, get_legal_actions, execute_action
from tgn.gameplay.world_phase import get_current_phase
from tgn.autoplay.runner import run_autoplay
from tgn.autoplay.models import AutoplayConfig, StopReason
from tgn.actions.models import ActionIntent
from tgn.storage.replay import replay_events, verify_persistence_integrity
from tgn.storage.event_store import EventStore


PHASE_CYCLE_CONFIG = {
    "cycle_minutes": 120,
    "boundary_minute": 60,
    "phase_before": "DAY",
    "phase_after": "NIGHT",
    "blocked_actions_by_phase": {"NIGHT": ["DROP"]},
}


def _make_phase6_autoplay_state() -> GameState:
    """Phase 6 autoplay initial state per spec #51."""
    return GameState(
        schema_version=1, event_seq=0, decision_seq=0,
        game_minute=55, seed="phase6-autoplay",
        data={
            "player": {
                "location_id": "base-1", "stamina": 2, "max_stamina": 5,
                "hp": 10, "max_hp": 10, "attack": 5,
            },
            "inventory": {"salvage": 4, "parts": 2},
            "expedition": {
                "active": False, "base_location_id": "base-1",
                "target_location_id": "site-1", "target_searched": False,
                "target_loot": {"salvage": 2, "parts": 1}, "carried_loot": {},
            },
            "phase_cycle": dict(PHASE_CYCLE_CONFIG),
            "progression": {"tracks": {"player": 0, "base": 0}},
            "progression_gates": {
                "player": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
                "base": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
            },
        },
    )


def _phase6_policy(observation: dict[str, Any], decision: int, actor_id: str) -> ActionIntent | None:
    """Deterministic Phase 6 policy: UPGRADE_PLAYER → UPGRADE_BASE → REST → DROP."""
    actions = [
        ("UPGRADE_PLAYER", {}),
        ("UPGRADE_BASE", {}),
        ("REST", {}),
        ("DROP", {}),
    ]
    if decision <= len(actions):
        action_type, params = actions[decision - 1]
        return ActionIntent(
            action_id=f"p6-{action_type.lower()}-{decision}",
            actor_id=actor_id,
            action_type=action_type,
            params=params,
        )
    return None


# --- Scripted autoplay acceptance (spec #51, #52) ---

class TestScriptedAutoplay:
    def test_autoplay_four_decisions_complete(self):
        state = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")
        result = run_autoplay(state, _phase6_policy, config)
        assert result.completed is True
        assert result.decisions == 4
        assert result.events == 4
        assert result.rejection is None

    def test_autoplay_player_progression_observed(self):
        state = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")
        result = run_autoplay(state, _phase6_policy, config)
        # After decision 1: player stage = 1
        frame1_after = result.frames[0].observation_after
        assert frame1_after["progression"]["tracks"]["player"]["stage"] == 1

    def test_autoplay_base_progression_observed(self):
        state = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")
        result = run_autoplay(state, _phase6_policy, config)
        frame2_after = result.frames[1].observation_after
        assert frame2_after["progression"]["tracks"]["base"]["stage"] == 1

    def test_autoplay_day_to_night_observed(self):
        state = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")
        result = run_autoplay(state, _phase6_policy, config)
        assert result.frames[0].observation_before["world_phase"] == "DAY"
        assert result.frames[0].observation_after["world_phase"] == "NIGHT"

    def test_autoplay_rest_restores_stamina(self):
        state = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")
        result = run_autoplay(state, _phase6_policy, config)
        frame3_after = result.frames[2].observation_after
        assert frame3_after["stamina"] == 5

    def test_autoplay_night_drop_after_base_progression(self):
        state = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")
        result = run_autoplay(state, _phase6_policy, config)
        # Decision 4 is DROP at NIGHT — accepted
        assert result.frames[3].action_type == "DROP"
        assert result.frames[3].event_type == "EXPEDITION_DROPPED"

    def test_autoplay_time_strictly_increases(self):
        state = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")
        result = run_autoplay(state, _phase6_policy, config)
        minutes = [55]
        for frame in result.frames:
            minutes.append(frame.game_minute_after)
        for i in range(1, len(minutes)):
            assert minutes[i] > minutes[i - 1]

    def test_autoplay_deterministic_hash(self):
        s1 = _make_phase6_autoplay_state()
        s2 = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")
        r1 = run_autoplay(s1, _phase6_policy, config)
        r2 = run_autoplay(s2, _phase6_policy, config)
        assert r1.final_state_hash == r2.final_state_hash


# --- Pure replay acceptance (spec #53) ---

class TestPureReplay:
    def test_replay_matches_final_hash(self):
        state = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")
        result = run_autoplay(state, _phase6_policy, config)
        runtime_hash = result.final_state_hash

        # Re-execute to collect events
        replay_state = _make_phase6_autoplay_state()
        events = []
        for action_type in ["UPGRADE_PLAYER", "UPGRADE_BASE", "REST", "DROP"]:
            intent = ActionIntent(
                action_id=f"r-{action_type}", actor_id="phase6-bot",
                action_type=action_type, params={},
            )
            r = execute_action(replay_state, intent)
            assert r.accepted
            events.append(r.events[0])
            replay_state = r.final_state

        # Replay from initial
        initial = _make_phase6_autoplay_state()
        replay_result = replay_events(initial, events)
        assert replay_result.success is True
        assert replay_result.actual_hash == runtime_hash


# --- SQLite persistence acceptance (spec #54, #55, #56) ---

class TestSQLitePersistence:
    def test_phase6_persists_reopens_and_replays_exactly(self, tmp_path):
        db_path = tmp_path / "phase6.sqlite3"
        campaign_id = "phase6-persist-test"

        store = EventStore(db_path)
        state = _make_phase6_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="phase6-bot")

        result = run_autoplay(state, _phase6_policy, config,
                              event_store=store, campaign_id=campaign_id)

        assert result.completed is True
        assert result.decisions == 4
        runtime_hash = result.final_state_hash

        store.close()

        # Reopen
        reopened = EventStore(db_path)
        campaign = reopened.get_campaign(campaign_id)
        assert campaign is not None

        event_records = reopened.all_event_records(campaign_id)
        assert len(event_records) == 4
        assert event_records[0]["event_type"] == "PLAYER_PROGRESSION_ADVANCED"
        assert event_records[1]["event_type"] == "BASE_PROGRESSION_ADVANCED"
        assert event_records[2]["event_type"] == "REST_RESOLVED"
        assert event_records[3]["event_type"] == "EXPEDITION_DROPPED"

        snapshot = reopened.latest_snapshot_record(campaign_id)
        assert snapshot.event_seq == 4
        assert snapshot.state["game_minute"] == 95
        assert snapshot.state["data"]["progression"]["tracks"]["player"] == 1
        assert snapshot.state["data"]["progression"]["tracks"]["base"] == 1
        assert snapshot.state_hash == runtime_hash

        reopened.close()

        # Full verification
        verification = verify_persistence_integrity(campaign_id, db_path)
        assert verification.success is True
        assert verification.states_replayed == 4
        assert verification.actual_hash == runtime_hash

        # Reconstruct and prove gameplay meaning
        reconstructed = GameState(**verification.final_state)
        assert reconstructed.game_minute == 95
        assert get_current_phase(reconstructed) == "NIGHT"
        assert reconstructed.data["expedition"]["active"] is True
        assert reconstructed.data["player"]["location_id"] == "site-1"
        assert reconstructed.data["progression"]["tracks"]["player"] == 1
        assert reconstructed.data["progression"]["tracks"]["base"] == 1
