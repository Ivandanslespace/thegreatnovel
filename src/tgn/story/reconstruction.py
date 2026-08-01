"""Historical Campaign reconstruction for deterministic Story requests."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from ..core.hashing import state_hash
from ..core.models import GameState
from ..campaign.models import CampaignManifest
from ..gameplay.expedition import build_observation
from ..llm_player import build_llm_decision_request, import_recorded_decisions
from ..projection import PlayerProjectionMap, build_player_presentation
from ..storage.replay import record_to_domain_event, replay_events
from .campaign_snapshot import CampaignSnapshot, parse_snapshot_json
from .claims import derive_claim_requirements
from .common import canonical_bytes, parse_json_bytes, sha256_bytes
from .models import (
    NARRATION_REQUEST_FORMAT_ID,
    NarrationRequest,
    StoryError,
    StoryManifest,
    request_hash,
)


_CAMPAIGN_COLUMNS = (
    "campaign_id",
    "engine_version",
    "state_schema_version",
    "seed",
    "initial_state_json",
    "initial_state_hash",
    "created_at",
)
_EVENT_COLUMNS = (
    "event_id",
    "campaign_id",
    "event_seq",
    "decision_seq",
    "game_minute",
    "event_type",
    "actor_id",
    "action_id",
    "causation_id",
    "correlation_id",
    "payload_json",
    "state_hash_before",
    "state_hash_after",
    "created_at",
)
_SNAPSHOT_COLUMNS = (
    "id",
    "campaign_id",
    "event_seq",
    "state_json",
    "state_hash",
    "created_at",
)


@dataclass(frozen=True)
class ReconstructedTurn:
    request: NarrationRequest
    terminal_reason: str | None
    event_type: str


@dataclass(frozen=True)
class CampaignHistory:
    manifest: CampaignManifest
    story_manifest: StoryManifest
    snapshot: CampaignSnapshot
    projection: PlayerProjectionMap
    session: dict[str, Any]
    records: tuple[Any, ...]
    event_records: tuple[dict[str, Any], ...]
    action_turns: tuple[ReconstructedTurn, ...]
    accepted_decisions: int
    recorded_decision_count: int

    @property
    def stop_reason(self) -> str | None:
        return self.session.get("stop_reason")


def _integrity(message: str) -> StoryError:
    return StoryError("CAMPAIGN_INTEGRITY_MISMATCH", message)


def _load_projection(snapshot: CampaignSnapshot) -> PlayerProjectionMap:
    value = parse_snapshot_json(snapshot, "projection/player_projection.json")
    expected = {
        "schema_version",
        "projection_compiler_id",
        "mechanics_profile",
        "source_worldpack_hash",
        "source_initial_state_hash",
        "content_locale",
        "world",
        "identities",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise _integrity("PlayerProjectionMap has an invalid field set")
    try:
        return PlayerProjectionMap(
            schema_version=value["schema_version"],
            projection_compiler_id=value["projection_compiler_id"],
            mechanics_profile=value["mechanics_profile"],
            source_worldpack_hash=value["source_worldpack_hash"],
            source_initial_state_hash=value["source_initial_state_hash"],
            content_locale=value["content_locale"],
            world=copy.deepcopy(value["world"]),
            identities=copy.deepcopy(value["identities"]),
        )
    except Exception as exc:
        raise _integrity("PlayerProjectionMap is invalid") from exc


def _event_records(snapshot: CampaignSnapshot) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for row in snapshot.event_rows:
        if len(row) != len(_EVENT_COLUMNS):
            raise _integrity("Campaign Event row has an invalid shape")
        value = dict(zip(_EVENT_COLUMNS, row))
        payload_json = value["payload_json"]
        if not isinstance(payload_json, str):
            raise _integrity("Campaign Event payload is invalid")
        try:
            payload = parse_json_bytes(payload_json.encode("utf-8"), require_canonical=False)
        except Exception as exc:
            raise _integrity("Campaign Event payload is invalid") from exc
        if not isinstance(payload, dict):
            raise _integrity("Campaign Event payload is not an object")
        value["payload"] = payload
        records.append(value)
    return tuple(records)


def _validate_sqlite_history(snapshot: CampaignSnapshot, manifest: CampaignManifest, initial_state: GameState, events: tuple[dict[str, Any], ...]) -> None:
    if len(snapshot.campaign_row) != len(_CAMPAIGN_COLUMNS):
        raise _integrity("Campaign SQLite row has an invalid shape")
    campaign_row = dict(zip(_CAMPAIGN_COLUMNS, snapshot.campaign_row))
    if campaign_row["campaign_id"] != manifest.campaign_id:
        raise _integrity("Campaign SQLite campaign row does not match binding")
    if campaign_row["initial_state_hash"] != state_hash(initial_state.__dict__):
        raise _integrity("Campaign SQLite initial state hash does not match state")
    if len(events) != len(snapshot.snapshot_rows):
        raise _integrity("Campaign snapshot count does not match Event count")
    for index, event in enumerate(events, start=1):
        if event["campaign_id"] != manifest.campaign_id:
            raise _integrity("Campaign Event belongs to another Campaign")
        if event["event_seq"] != initial_state.event_seq + index:
            raise _integrity("Campaign Event sequence is not contiguous")
        if event["decision_seq"] != initial_state.decision_seq + index:
            raise _integrity("Campaign Event decision sequence is not contiguous")
        snapshot_row = snapshot.snapshot_rows[index - 1]
        if len(snapshot_row) != len(_SNAPSHOT_COLUMNS):
            raise _integrity("Campaign snapshot row has an invalid shape")
        snapshot_value = dict(zip(_SNAPSHOT_COLUMNS, snapshot_row))
        if (
            snapshot_value["campaign_id"] != manifest.campaign_id
            or snapshot_value["event_seq"] != event["event_seq"]
            or snapshot_value["state_hash"] != event["state_hash_after"]
        ):
            raise _integrity("Campaign snapshot does not match Event history")


def _public_brief(
    before_presentation: Any,
    after_presentation: Any,
    *,
    choice_id: str,
    action_type: str,
    action_id: str,
    accepted_decision_number: int,
    event: dict[str, Any],
) -> dict[str, Any]:
    event_seq = event["event_seq"]
    decision_seq = event["decision_seq"]
    event_type = event["event_type"]
    return {
        "observation_before": copy.deepcopy(before_presentation.observation),
        "observation_after": copy.deepcopy(after_presentation.observation),
        "action_result": {
            "choice_id": choice_id,
            "action_type": action_type,
            "action_id": action_id,
            "accepted_decision_number": accepted_decision_number,
            "event_types": [event_type],
            "event_seq_start": event_seq,
            "event_seq_end": event_seq,
            "public_event_facts": [
                {
                    "event_seq": event_seq,
                    "decision_seq": decision_seq,
                    "event_type": event_type,
                    "facts": {},
                }
            ],
        },
    }


def _reconstruct_request(
    campaign_manifest: CampaignManifest,
    story_manifest: StoryManifest,
    snapshot: CampaignSnapshot,
    projection: PlayerProjectionMap,
    records: tuple[Any, ...],
) -> tuple[ReconstructedTurn, ...]:
    initial_value = parse_snapshot_json(snapshot, "world/initial_state.json")
    try:
        initial_state = GameState(**copy.deepcopy(initial_value))
    except Exception as exc:
        raise _integrity("Campaign initial state is invalid") from exc
    events = _event_records(snapshot)
    _validate_sqlite_history(snapshot, campaign_manifest, initial_state, events)
    domain_events = []
    try:
        domain_events = [record_to_domain_event(record) for record in events]
        replay = replay_events(initial_state, domain_events, state_at_each_step=True)
    except Exception as exc:
        raise _integrity("Campaign Event replay failed") from exc
    if not replay.success:
        raise _integrity("Campaign Event replay failed")
    history = getattr(replay, "history", None)
    if not isinstance(history, list) or len(history) != len(events) + 1:
        raise _integrity("Campaign replay history is incomplete")
    state_history = [copy.deepcopy(item) for item in history]

    turns: list[ReconstructedTurn] = []
    event_index = 0
    action_count = 0
    stop_seen = False
    for recorded_index, record in enumerate(records, start=1):
        if record.decision_number != recorded_index:
            raise _integrity("RecordedDecision numbers are not contiguous")
        if stop_seen:
            raise _integrity("RecordedDecision appears after STOP")
        if record.outcome == "STOP":
            stop_seen = True
            if event_index != len(events):
                raise _integrity("STOP appears before all authoritative Events")
            continue
        if record.outcome != "ACTION":
            raise _integrity("RecordedDecision outcome is invalid")
        action_count += 1
        accepted_number = action_count
        if record.decision_number != accepted_number:
            raise _integrity("ACTION decision number does not match accepted number")
        if event_index >= len(events):
            raise _integrity("Campaign Event is missing for accepted ACTION")
        state_before_mapping = state_history[event_index]
        state_after_mapping = state_history[event_index + 1]
        try:
            state_before = GameState(**copy.deepcopy(state_before_mapping))
            state_after = GameState(**copy.deepcopy(state_after_mapping))
            before_request = build_llm_decision_request(
                build_observation(state_before), accepted_number
            )
            after_request = build_llm_decision_request(
                build_observation(state_after), accepted_number + 1
            )
        except Exception as exc:
            raise _integrity("frozen request reconstruction failed") from exc
        if record.request_fingerprint != before_request.request_fingerprint:
            raise _integrity("RecordedDecision request fingerprint does not match replay")
        selected = next(
            (choice for choice in before_request.choices if choice.choice_id == record.choice_id),
            None,
        )
        if selected is None:
            raise _integrity("RecordedDecision choice is not legal in replay")
        if record.action_type != selected.action_type or record.params != selected.params:
            raise _integrity("RecordedDecision choice does not match replay")
        expected_action_id = f"{campaign_manifest.actor_id}-external-{campaign_manifest.session_id}-{accepted_number}"
        event = events[event_index]
        event_index += 1
        if event["action_id"] != expected_action_id or event["decision_seq"] != accepted_number:
            raise _integrity("Event action/decision binding does not match Session trace")
        before_hash = state_hash(state_before.__dict__)
        after_hash = state_hash(state_after.__dict__)
        if event["state_hash_before"] != before_hash or event["state_hash_after"] != after_hash:
            raise _integrity("Event state hash binding does not match replay")
        event_seq = event["event_seq"]
        if event_seq != event["event_seq"] or event["event_seq"] < 0:
            raise _integrity("Event sequence is invalid")

        before_presentation = build_player_presentation(before_request, projection)
        after_presentation = build_player_presentation(after_request, projection)
        terminal_reason: str | None = None
        if accepted_number == campaign_manifest.max_decisions:
            terminal_reason = "MAX_DECISIONS"
        elif not after_request.choices:
            terminal_reason = "NO_LEGAL_ACTIONS"
        brief = _public_brief(
            before_presentation,
            after_presentation,
            choice_id=selected.choice_id,
            action_type=selected.action_type,
            action_id=expected_action_id,
            accepted_decision_number=accepted_number,
            event=event,
        )
        requirements = derive_claim_requirements(
            brief["observation_before"],
            brief["observation_after"],
            choice_id=selected.choice_id,
            action_type=selected.action_type,
            terminal_reason=terminal_reason,
        )
        request_value: dict[str, Any] = {
            "schema_version": 1,
            "request_format_id": NARRATION_REQUEST_FORMAT_ID,
            "narration_request_id": f"{story_manifest.story_id}:turn-{accepted_number:06d}",
            "narration_request_hash": "0" * 64,
            "story_id": story_manifest.story_id,
            "turn_id": f"turn-{accepted_number:06d}",
            "campaign_id": campaign_manifest.campaign_id,
            "session_id": campaign_manifest.session_id,
            "accepted_decision_number": accepted_number,
            "recorded_decision_index": recorded_index,
            "request_fingerprint_before": before_request.request_fingerprint,
            "source_request_hash": sha256_bytes(canonical_bytes(before_request.to_dict())),
            "choice_id": selected.choice_id,
            "action_type": selected.action_type,
            "action_id": expected_action_id,
            "params": selected.params,
            "duration_minutes": selected.duration_minutes,
            "stamina_cost": selected.stamina_cost,
            "event_seq_start": event_seq,
            "event_seq_end": event_seq,
            "state_hash_before": before_hash,
            "state_hash_after": after_hash,
            "narration_locale": story_manifest.initial_narration_locale,
            "voice_id": story_manifest.initial_voice_id,
            "public_brief": brief,
            "claim_requirements": requirements,
        }
        request_value["narration_request_hash"] = request_hash(request_value)
        try:
            request = NarrationRequest.from_dict(request_value)
        except Exception as exc:
            raise _integrity("deterministic Narration Request is invalid") from exc
        turns.append(
            ReconstructedTurn(
                request=request,
                terminal_reason=terminal_reason,
                event_type=event["event_type"],
            )
        )
    if event_index != len(events):
        raise _integrity("Campaign contains an unbound Event")
    return tuple(turns)


def reconstruct_campaign(
    story_manifest: StoryManifest,
    snapshot: CampaignSnapshot,
) -> CampaignHistory:
    """Rebuild every accepted ACTION request from one captured Campaign view."""

    try:
        session = parse_json_bytes(snapshot.session_json_canonical_bytes, require_canonical=True)
        if not isinstance(session, dict):
            raise ValueError("session manifest is not an object")
        records = import_recorded_decisions(
            snapshot.recorded_decisions_json_canonical_bytes.decode("utf-8")
        )
    except Exception as exc:
        raise _integrity("Campaign Session edge artifacts are invalid") from exc
    try:
        campaign_manifest = CampaignManifest.from_dict(
            parse_snapshot_json(snapshot, "campaign.json")
        )
    except Exception as exc:
        raise _integrity("Campaign manifest is invalid") from exc
    projection = _load_projection(snapshot)
    if projection.source_worldpack_hash != story_manifest.worldpack_hash or projection.source_initial_state_hash != story_manifest.source_initial_state_hash:
        raise _integrity("Projection binding does not match Story Campaign binding")
    try:
        action_turns = _reconstruct_request(campaign_manifest, story_manifest, snapshot, projection, records)
    except StoryError:
        raise
    except Exception as exc:
        raise _integrity("Campaign history reconstruction failed") from exc
    accepted = len(action_turns)
    if session.get("campaign_id") != campaign_manifest.campaign_id or session.get("session_id") != campaign_manifest.session_id:
        raise _integrity("Session binding does not match Campaign")
    if session.get("accepted_decisions") != accepted or session.get("recorded_decision_count") != len(records):
        raise _integrity("Session decision counts do not match history")
    return CampaignHistory(
        manifest=campaign_manifest,
        story_manifest=story_manifest,
        snapshot=snapshot,
        projection=projection,
        session=copy.deepcopy(session),
        records=tuple(records),
        event_records=_event_records(snapshot),
        action_turns=action_turns,
        accepted_decisions=accepted,
        recorded_decision_count=len(records),
    )


def request_for_turn(history: CampaignHistory, turn_id: str) -> ReconstructedTurn | None:
    for item in history.action_turns:
        if item.request.turn_id == turn_id:
            return item
    return None


__all__ = [
    "CampaignHistory",
    "ReconstructedTurn",
    "reconstruct_campaign",
    "request_for_turn",
]
