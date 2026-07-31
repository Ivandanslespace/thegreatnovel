"""Phase 7 autoplay, replay, and SQLite persistence acceptance tests."""

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
    "cycle_minutes": 120, "boundary_minute": 60,
    "phase_before": "DAY", "phase_after": "NIGHT",
    "blocked_actions_by_phase": {"NIGHT": ["DROP"]},
}


def _make_phase7_autoplay_state():
    """Phase 7 autoplay initial state: minute 60, NIGHT, player stage 1."""
    return GameState(
        schema_version=1, event_seq=0, decision_seq=0,
        game_minute=60, seed="phase7-autoplay",
        data={
            "player": {
                "location_id": "base-1", "stamina": 2, "max_stamina": 5,
                "hp": 10, "max_hp": 10, "attack": 5,
            },
            "inventory": {},
            "expedition": {
                "active": False, "base_location_id": "base-1",
                "target_location_id": "site-1", "target_searched": False,
                "target_loot": {"salvage": 2, "parts": 1}, "carried_loot": {},
            },
            "phase_cycle": dict(PHASE_CYCLE_CONFIG),
            "progression": {"tracks": {"player": 1, "base": 0}},
            "progression_gates": {
                "player": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
                "base": {"from_stage": 0, "to_stage": 1, "cost": {"salvage": 2, "parts": 1}},
            },
            "build_choice": {
                "required_track": "player", "required_stage": 1,
                "candidates": ["window_runner", "field_rest", "quick_rest"],
            },
            "build": {"selected": None},
        },
    )


def _window_runner_policy(obs: dict[str, Any], decision: int, actor_id: str) -> ActionIntent | None:
    """WindowRunnerPolicy: CHOOSE(window_runner) → REST → DROP."""
    if decision == 1:
        return ActionIntent(action_id="wr-1", actor_id=actor_id,
                            action_type="CHOOSE_BUILD", params={"build_id": "window_runner"})
    elif decision == 2:
        return ActionIntent(action_id="wr-2", actor_id=actor_id, action_type="REST", params={})
    elif decision == 3:
        return ActionIntent(action_id="wr-3", actor_id=actor_id, action_type="DROP", params={})
    return None


def _field_rest_policy(obs: dict[str, Any], decision: int, actor_id: str) -> ActionIntent | None:
    """FieldRestPolicy: CHOOSE(field_rest) → WAIT 59 → DROP → REST at target."""
    if decision == 1:
        return ActionIntent(action_id="fr-1", actor_id=actor_id,
                            action_type="CHOOSE_BUILD", params={"build_id": "field_rest"})
    elif decision == 2:
        return ActionIntent(action_id="fr-2", actor_id=actor_id,
                            action_type="WAIT", params={"minutes": 59})
    elif decision == 3:
        return ActionIntent(action_id="fr-3", actor_id=actor_id, action_type="DROP", params={})
    elif decision == 4:
        return ActionIntent(action_id="fr-4", actor_id=actor_id, action_type="REST", params={})
    return None


# --- Two-branch scripted autoplay (spec #48, #49) ---

class TestTwoBranchAutoplay:
    def test_window_runner_policy_complete(self):
        state = _make_phase7_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="wr-bot")
        result = run_autoplay(state, _window_runner_policy, config)
        assert result.completed is True
        assert result.decisions == 3
        assert result.rejection is None

    def test_field_rest_policy_complete(self):
        state = _make_phase7_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="fr-bot")
        result = run_autoplay(state, _field_rest_policy, config)
        assert result.completed is True
        assert result.decisions == 4
        assert result.rejection is None

    def test_policies_produce_different_hashes(self):
        s1 = _make_phase7_autoplay_state()
        s2 = _make_phase7_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="bot")
        r1 = run_autoplay(s1, _window_runner_policy, config)
        r2 = run_autoplay(s2, _field_rest_policy, config)
        assert r1.final_state_hash != r2.final_state_hash

    def test_window_runner_build_persisted_in_observation(self):
        state = _make_phase7_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="wr-bot")
        result = run_autoplay(state, _window_runner_policy, config)
        frame1_after = result.frames[0].observation_after
        assert frame1_after["build"]["selected"] == "window_runner"

    def test_time_monotonic_both_branches(self):
        for policy in [_window_runner_policy, _field_rest_policy]:
            state = _make_phase7_autoplay_state()
            config = AutoplayConfig(max_decisions=10, actor_id="bot")
            result = run_autoplay(state, policy, config)
            minutes = [60]
            for frame in result.frames:
                minutes.append(frame.game_minute_after)
            for i in range(1, len(minutes)):
                assert minutes[i] > minutes[i - 1]


# --- Pure replay (spec #50) ---

class TestPureReplay:
    def test_replay_window_runner_branch(self):
        state = _make_phase7_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="wr-bot")
        result = run_autoplay(state, _window_runner_policy, config)
        runtime_hash = result.final_state_hash

        # Re-execute to collect events
        replay_state = _make_phase7_autoplay_state()
        events = []
        for action_type, params in [
            ("CHOOSE_BUILD", {"build_id": "window_runner"}),
            ("REST", {}),
            ("DROP", {}),
        ]:
            intent = ActionIntent(action_id=f"r-{action_type}", actor_id="wr-bot",
                                  action_type=action_type, params=params)
            r = execute_action(replay_state, intent)
            assert r.accepted
            events.append(r.events[0])
            replay_state = r.final_state

        initial = _make_phase7_autoplay_state()
        replay_result = replay_events(initial, events)
        assert replay_result.success is True
        assert replay_result.actual_hash == runtime_hash


# --- SQLite persistence (spec #51, #52, #53) ---

class TestSQLitePersistence:
    def test_phase7_persists_reopens_and_replays(self, tmp_path):
        db_path = tmp_path / "phase7.sqlite3"
        campaign_id = "phase7-persist"

        store = EventStore(db_path)
        state = _make_phase7_autoplay_state()
        config = AutoplayConfig(max_decisions=10, actor_id="wr-bot")

        result = run_autoplay(state, _window_runner_policy, config,
                              event_store=store, campaign_id=campaign_id)
        assert result.completed is True
        assert result.decisions == 3
        runtime_hash = result.final_state_hash

        store.close()

        # Reopen
        reopened = EventStore(db_path)
        campaign = reopened.get_campaign(campaign_id)
        assert campaign is not None

        event_records = reopened.all_event_records(campaign_id)
        assert len(event_records) == 3
        assert event_records[0]["event_type"] == "BUILD_SELECTED"
        assert event_records[1]["event_type"] == "REST_RESOLVED"
        assert event_records[2]["event_type"] == "EXPEDITION_DROPPED"

        snapshot = reopened.latest_snapshot_record(campaign_id)
        assert snapshot.event_seq == 3
        assert snapshot.state["data"]["build"]["selected"] == "window_runner"
        assert snapshot.state["game_minute"] == 91
        assert snapshot.state_hash == runtime_hash

        reopened.close()

        # Full verification
        verification = verify_persistence_integrity(campaign_id, db_path)
        assert verification.success is True
        assert verification.states_replayed == 3
        assert verification.actual_hash == runtime_hash

        # Reconstruct gameplay meaning
        reconstructed = GameState(**verification.final_state)
        assert reconstructed.data["build"]["selected"] == "window_runner"
        assert reconstructed.data["progression"]["tracks"]["player"] == 1
        assert reconstructed.data["expedition"]["active"] is True
        assert reconstructed.game_minute == 91
        # Build choice permanently unavailable
        legal_types = [la.action_type for la in get_legal_actions(reconstructed)]
        assert "CHOOSE_BUILD" not in legal_types
