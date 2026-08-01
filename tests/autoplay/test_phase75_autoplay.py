"""Scripted end-to-end autoplay for the Phase 7.5 contract."""

from __future__ import annotations

from tgn.actions.models import ActionIntent
from tgn.autoplay import AutoplayConfig, run_autoplay
from tgn.core.models import GameState
from tgn.storage.event_store import EventStore
from tgn.storage.replay import verify_persistence_integrity

from tests.gameplay.phase75_helpers import make_phase75_state


def _phase75_policy(observation, decision_number, actor_id):
    sequence = ["DROP", "SEARCH", "EXTRACT", "TALK_TO_ACTOR"]
    if decision_number > len(sequence):
        return None
    target = sequence[decision_number - 1]
    for legal in observation["legal_actions"]:
        if legal.action_type == target:
            return ActionIntent(
                action_id=f"phase75-{decision_number}",
                actor_id=actor_id,
                action_type=legal.action_type,
                params=dict(legal.params),
            )
    return None


def test_phase75_scripted_autoplay_reaches_talk_and_records_integrity_metrics(tmp_path):
    db_path = tmp_path / "phase75.sqlite3"
    campaign_id = "phase75-autoplay"
    store = EventStore(db_path)
    result = run_autoplay(
        make_phase75_state(),
        _phase75_policy,
        AutoplayConfig(max_decisions=5, actor_id="phase75-bot"),
        event_store=store,
        campaign_id=campaign_id,
    )

    assert result.completed is True
    assert result.illegal_actions == 0
    assert result.knowledge_boundary_violations == 0
    assert result.actor_autonomous_actions == 1
    assert result.knowledge_transfers == 1
    assert result.relationship_changes == 1
    assert result.replay_verified is True
    assert result.persistence_integrity_verified is True
    assert [frame.action_type for frame in result.frames] == [
        "DROP", "SEARCH", "EXTRACT", "TALK_TO_ACTOR"
    ]
    assert result.final_state.data["named_actor"]["goal"] == "reported"
    assert result.final_state.data["named_actor"]["relationship"]["trust"] == 1
    assert result.final_state.data["player_knowledge"]["facts"] == {
        "site-1-condition": "unstable"
    }

    # run_autoplay must not close a caller-owned EventStore.
    assert store.connection.execute("SELECT 1").fetchone()[0] == 1
    store.close()
    verification = verify_persistence_integrity(campaign_id, db_path)
    assert verification.success is True
    assert verification.actual_hash == result.final_state_hash
    reopened = GameState(**verification.final_state)
    assert reopened.data["named_actor"] == result.final_state.data["named_actor"]
    assert reopened.data["player_knowledge"] == result.final_state.data["player_knowledge"]
