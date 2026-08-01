"""Phase 8 live LLM-edge and RecordedDecision replay product test."""

from __future__ import annotations

import json

from tgn.autoplay import AutoplayConfig, StopReason, run_autoplay
from tgn.core.models import GameState
from tgn.llm_player import (
    LLMPlayerPolicy,
    RecordedDecisionPolicy,
    export_recorded_decisions,
    import_recorded_decisions,
)
from tgn.storage.event_store import EventStore
from tgn.storage.replay import verify_persistence_integrity

from tests.gameplay.phase75_helpers import make_phase75_state


class _FakeCompletion:
    """Choose only from the serialized choices present in the prompt."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        self.calls += 1
        request = json.loads(prompt.split("REQUEST_JSON:\n", 1)[1])
        preferred = ("DROP", "SEARCH", "EXTRACT", "TALK_TO_ACTOR")
        for action_type in preferred:
            for choice in request["choices"]:
                if choice["action_type"] == action_type:
                    return json.dumps(
                        {"choice_id": choice["choice_id"]},
                        separators=(",", ":"),
                    )
        return '{"stop":true}'


def test_phase8_live_completion_records_and_replays_without_completion(tmp_path):
    db_path = tmp_path / "phase8.sqlite3"
    campaign_id = "phase8-live"
    completion = _FakeCompletion()
    live_policy = LLMPlayerPolicy(completion)
    store = EventStore(db_path)

    live = run_autoplay(
        make_phase75_state(),
        live_policy,
        AutoplayConfig(max_decisions=5, actor_id="phase8-bot"),
        event_store=store,
        campaign_id=campaign_id,
    )

    assert live.completed is True
    assert live.stop_reason == StopReason.POLICY_COMPLETE
    assert live.decisions == 4
    assert completion.calls == 5
    assert live.illegal_actions == 0
    assert live.knowledge_boundary_violations == 0
    assert live.actor_autonomous_actions == 1
    assert live.knowledge_transfers == 1
    assert live.relationship_changes == 1
    assert live.replay_verified is True
    assert live.persistence_integrity_verified is True
    assert [frame.action_type for frame in live.frames] == [
        "DROP",
        "SEARCH",
        "EXTRACT",
        "TALK_TO_ACTOR",
    ]
    assert live.final_state.data["named_actor"]["goal"] == "reported"
    assert live.final_state.data["named_actor"]["relationship"]["trust"] == 1
    assert live.final_state.data["player_knowledge"]["facts"] == {
        "site-1-condition": "unstable"
    }

    recorded = live_policy.recorded_decisions
    imported = import_recorded_decisions(export_recorded_decisions(recorded))
    replay_policy = RecordedDecisionPolicy(imported)
    replay = run_autoplay(
        make_phase75_state(),
        replay_policy,
        AutoplayConfig(max_decisions=5, actor_id="phase8-bot"),
    )
    replay_policy.assert_consumed()

    assert completion.calls == 5
    assert replay.completed is True
    assert replay.stop_reason == live.stop_reason
    assert replay.decisions == live.decisions
    assert [frame.action_type for frame in replay.frames] == [
        frame.action_type for frame in live.frames
    ]
    assert [frame.action_id for frame in replay.frames] == [
        frame.action_id for frame in live.frames
    ]
    assert [frame.event_type for frame in replay.frames] == [
        frame.event_type for frame in live.frames
    ]
    assert [frame.event_payload for frame in replay.frames] == [
        frame.event_payload for frame in live.frames
    ]
    assert replay.final_state_hash == live.final_state_hash
    assert replay.final_state == live.final_state
    assert replay_policy.recorded_decisions == recorded

    # Verify the persisted live run after the caller explicitly closes SQLite.
    store.close()
    verification = verify_persistence_integrity(campaign_id, db_path)
    assert verification.success is True
    assert verification.actual_hash == live.final_state_hash
    reopened = GameState(**verification.final_state)
    assert reopened == live.final_state
