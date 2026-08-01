"""Minimal Phase 9A external-client session boundary.

The session directory is an edge protocol around the existing deterministic
engine.  GameState and DomainEvent remain authoritative in EventStore;
session.json and recorded_decisions.json contain only strict edge metadata.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..actions.models import ActionIntent
from ..core.hashing import canonical_json, state_hash
from ..core.invariants import check_invariants
from ..core.models import GameState
from ..gameplay.expedition import build_observation, execute_action
from ..llm_player import (
    RecordedDecision,
    RecordedDecisionFormatError,
    RecordedDecisionMismatch,
    RecordedDecisionPolicy,
    build_llm_decision_request,
    export_recorded_decisions,
    import_recorded_decisions,
)
from ..storage.event_store import EventStore
from ..storage.replay import (
    record_to_domain_event,
    replay_events,
    verify_persistence_integrity,
)
from .models import SessionError, SessionManifest, validate_stable_id


CAMPAIGN_DB_NAME = "campaign.sqlite3"
MANIFEST_NAME = "session.json"
DECISIONS_NAME = "recorded_decisions.json"
_SESSION_FILES = frozenset({CAMPAIGN_DB_NAME, MANIFEST_NAME, DECISIONS_NAME})
_STATE_FIELDS = frozenset(
    {"schema_version", "event_seq", "decision_seq", "game_minute", "seed", "data"}
)
_STATE_INT_FIELDS = ("schema_version", "event_seq", "decision_seq", "game_minute")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _parse_json(payload: str) -> Any:
    return json.loads(
        payload,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )


def _integrity(message: str, *, cause: Exception | None = None) -> SessionError:
    error = SessionError("SESSION_INTEGRITY_MISMATCH", message)
    if cause is not None:
        error.__cause__ = cause
    return error


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except (OSError, TypeError, ValueError) as exc:
        raise _integrity(f"cannot atomically write {path.name}", cause=exc) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:  # pragma: no cover - the temp path normally exists
                pass


def _atomic_write_json(path: Path, value: Any) -> None:
    try:
        payload = canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise _integrity(f"{path.name} is not canonical JSON", cause=exc) from exc
    _atomic_write_text(path, payload)


def _read_json_file(path: Path, *, code: str, require_canonical: bool) -> Any:
    try:
        payload = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SessionError(code, f"cannot read {path.name}") from exc
    try:
        parsed = _parse_json(payload)
        if require_canonical and canonical_json(parsed) != payload:
            raise ValueError("JSON is not in canonical form")
        return parsed
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SessionError(code, f"invalid JSON in {path.name}") from exc


def _state_from_mapping(value: Any, *, code: str) -> GameState:
    if not isinstance(value, dict) or set(value) != _STATE_FIELDS:
        raise SessionError(code, "GameState JSON must contain exactly its six fields")
    for field_name in _STATE_INT_FIELDS:
        if type(value[field_name]) is not int:
            raise SessionError(code, f"GameState.{field_name} must be an integer")
    if not isinstance(value["seed"], str):
        raise SessionError(code, "GameState.seed must be a string")
    if not isinstance(value["data"], dict):
        raise SessionError(code, "GameState.data must be an object")
    try:
        canonical_json(value)
        state = GameState(
            schema_version=value["schema_version"],
            event_seq=value["event_seq"],
            decision_seq=value["decision_seq"],
            game_minute=value["game_minute"],
            seed=value["seed"],
            data=copy.deepcopy(value["data"]),
        )
        check_invariants(state)
        return state
    except Exception as exc:
        raise SessionError(code, "GameState violates deterministic invariants") from exc


def _read_initial_state(path: str | Path) -> GameState:
    initial_path = Path(path)
    if not initial_path.is_file():
        raise SessionError("INVALID_INITIAL_STATE", "initial-state JSON file does not exist")
    try:
        payload = initial_path.read_text(encoding="utf-8")
        parsed = _parse_json(payload)
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SessionError("INVALID_INITIAL_STATE", "initial-state JSON is invalid") from exc
    return _state_from_mapping(parsed, code="INVALID_INITIAL_STATE")


def _build_request(
    state: GameState, decision_number: int, *, code: str
) -> Any:
    try:
        observation = build_observation(state)
        return build_llm_decision_request(observation, decision_number)
    except Exception as exc:
        raise SessionError(code, "current player request cannot be built") from exc


def _validate_max_decisions(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise SessionError("INVALID_SESSION_MANIFEST", "max_decisions must be a positive integer")
    return value


@dataclass(frozen=True)
class _SessionPaths:
    root: Path

    @property
    def database(self) -> Path:
        return self.root / CAMPAIGN_DB_NAME

    @property
    def manifest(self) -> Path:
        return self.root / MANIFEST_NAME

    @property
    def decisions(self) -> Path:
        return self.root / DECISIONS_NAME


@dataclass
class _SessionContext:
    paths: _SessionPaths
    manifest: SessionManifest
    records: tuple[RecordedDecision, ...]
    initial_state: GameState
    current_state: GameState
    event_records: list[dict[str, Any]]
    current_request: Any | None


def _read_manifest(paths: _SessionPaths) -> SessionManifest:
    parsed = _read_json_file(
        paths.manifest, code="INVALID_SESSION_MANIFEST", require_canonical=True
    )
    return SessionManifest.from_dict(parsed)


def _read_records(paths: _SessionPaths) -> tuple[RecordedDecision, ...]:
    try:
        payload = paths.decisions.read_text(encoding="utf-8")
        parsed = _parse_json(payload)
        if canonical_json(parsed) != payload:
            raise ValueError("RecordedDecision bundle is not canonical")
        return import_recorded_decisions(payload)
    except RecordedDecisionFormatError as exc:
        raise _integrity("recorded_decisions.json violates the RecordedDecision contract", cause=exc) from exc
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _integrity("recorded_decisions.json is invalid", cause=exc) from exc


def _require_integrity(condition: bool, message: str) -> None:
    if not condition:
        raise _integrity(message)


def _load_context(session_dir: str | Path) -> _SessionContext:
    paths = _SessionPaths(Path(session_dir))
    if not paths.root.is_dir():
        raise SessionError("SESSION_NOT_FOUND", "session directory does not exist")
    try:
        actual_files = {path.name for path in paths.root.iterdir()}
    except OSError as exc:
        raise _integrity("cannot inspect session directory", cause=exc) from exc
    unexpected = actual_files - _SESSION_FILES
    if unexpected:
        raise _integrity("session directory contains unsupported files")
    missing = _SESSION_FILES - actual_files
    if missing:
        raise _integrity("session directory is missing required files")

    manifest = _read_manifest(paths)
    records = _read_records(paths)

    try:
        persistence = verify_persistence_integrity(manifest.campaign_id, paths.database)
    except Exception as exc:
        raise _integrity("SQLite persistence verification failed", cause=exc) from exc
    _require_integrity(persistence.success, persistence.error_message or "SQLite persistence mismatch")
    _require_integrity(persistence.final_state is not None, "SQLite replay returned no final state")

    store = EventStore(paths.database)
    try:
        campaign = store.get_campaign(manifest.campaign_id)
        event_records = store.all_event_records(manifest.campaign_id)
    except Exception as exc:
        raise _integrity("cannot read authoritative EventStore records", cause=exc) from exc
    finally:
        store.close()

    _require_integrity(campaign is not None, "session campaign is missing")
    try:
        initial_mapping = _parse_json(campaign.initial_state_json)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _integrity("campaign initial state JSON is invalid", cause=exc) from exc
    initial_state = _state_from_mapping(initial_mapping, code="SESSION_INTEGRITY_MISMATCH")
    current_state = _state_from_mapping(
        persistence.final_state, code="SESSION_INTEGRITY_MISMATCH"
    )

    _require_integrity(campaign.campaign_id == manifest.campaign_id, "campaign id mismatch")
    _require_integrity(campaign.seed == initial_state.seed, "campaign seed mismatch")
    _require_integrity(
        campaign.initial_state_hash == state_hash(initial_state.__dict__),
        "campaign initial state hash mismatch",
    )
    _require_integrity(
        manifest.current_state_hash == state_hash(current_state.__dict__),
        "manifest current state hash mismatch",
    )
    _require_integrity(
        manifest.current_event_seq == current_state.event_seq,
        "manifest current event sequence mismatch",
    )
    _require_integrity(
        manifest.current_state_decision_seq == current_state.decision_seq,
        "manifest current decision sequence mismatch",
    )
    _require_integrity(len(event_records) == manifest.accepted_decisions, "event count mismatch")
    _require_integrity(
        len(records) == manifest.recorded_decision_count,
        "RecordedDecision count mismatch",
    )
    action_records = tuple(record for record in records if record.outcome == "ACTION")
    stop_records = tuple(record for record in records if record.outcome == "STOP")
    _require_integrity(len(action_records) == manifest.accepted_decisions, "accepted action count mismatch")
    _require_integrity(
        len(records) == manifest.accepted_decisions + len(stop_records),
        "recorded action/stop count mismatch",
    )
    _require_integrity(
        current_state.event_seq == initial_state.event_seq + len(event_records),
        "current event sequence does not follow persisted events",
    )
    _require_integrity(
        current_state.decision_seq == initial_state.decision_seq + len(event_records),
        "current decision sequence does not follow persisted events",
    )
    for index, record in enumerate(event_records, start=1):
        _require_integrity(
            record["event_seq"] == initial_state.event_seq + index,
            "event sequence is not contiguous",
        )
        _require_integrity(
            record["decision_seq"] == initial_state.decision_seq + index,
            "event decision sequence is not contiguous",
        )

    if manifest.status == "STOPPED":
        _require_integrity(len(stop_records) == 1 and records[-1].outcome == "STOP", "STOPPED session must end with one STOP record")
    else:
        _require_integrity(len(stop_records) == 0, "non-STOPPED session cannot contain STOP")
    if manifest.status == "MAX_DECISIONS":
        _require_integrity(
            manifest.accepted_decisions == manifest.max_decisions,
            "MAX_DECISIONS status requires the configured action limit",
        )
    else:
        _require_integrity(
            manifest.accepted_decisions <= manifest.max_decisions,
            "accepted decisions exceed configured limit",
        )

    try:
        domain_events = [record_to_domain_event(record) for record in event_records]
        event_replay = replay_events(initial_state, domain_events)
    except Exception as exc:
        raise _integrity("domain event replay could not be completed", cause=exc) from exc
    _require_integrity(event_replay.success, event_replay.error_message or "domain event replay failed")
    _require_integrity(
        event_replay.actual_hash == state_hash(current_state.__dict__),
        "domain event replay hash mismatch",
    )

    try:
        recorded_policy = RecordedDecisionPolicy(records)
        recorded_state = copy.deepcopy(initial_state)
        for record in records:
            intent = recorded_policy(
                build_observation(recorded_state),
                record.decision_number,
                manifest.actor_id,
            )
            if intent is None:
                _require_integrity(record.outcome == "STOP", "recorded replay stopped on an ACTION record")
                break
            execution = execute_action(recorded_state, intent)
            _require_integrity(
                execution.accepted and len(execution.events) == 1 and execution.final_state is not None,
                "RecordedDecision replay produced a rejected action",
            )
            recorded_state = execution.final_state
        recorded_policy.assert_consumed()
    except (RecordedDecisionMismatch, Exception) as exc:
        if isinstance(exc, SessionError):
            raise
        raise _integrity("RecordedDecision replay failed", cause=exc) from exc
    _require_integrity(
        state_hash(recorded_state.__dict__) == state_hash(current_state.__dict__),
        "RecordedDecision replay hash mismatch",
    )

    current_request = None
    if manifest.status in {"AWAITING_DECISION", "NO_LEGAL_ACTIONS"}:
        current_request = _build_request(
            current_state,
            manifest.accepted_decisions + 1,
            code="SESSION_INTEGRITY_MISMATCH",
        )
        if manifest.status == "AWAITING_DECISION":
            _require_integrity(bool(current_request.choices), "AWAITING_DECISION requires a legal choice")
            _require_integrity(
                manifest.accepted_decisions < manifest.max_decisions,
                "AWAITING_DECISION cannot exceed max_decisions",
            )
            _require_integrity(
                manifest.current_request_fingerprint == current_request.request_fingerprint,
                "current request fingerprint mismatch",
            )
        else:
            _require_integrity(not current_request.choices, "NO_LEGAL_ACTIONS has a legal choice")
            _require_integrity(manifest.current_request_fingerprint is None, "terminal session has a request fingerprint")
    else:
        _require_integrity(manifest.current_request_fingerprint is None, "terminal session has a request fingerprint")

    return _SessionContext(
        paths=paths,
        manifest=manifest,
        records=records,
        initial_state=initial_state,
        current_state=current_state,
        event_records=event_records,
        current_request=current_request,
    )


def _session_summary(context: _SessionContext) -> dict[str, Any]:
    return context.manifest.public_summary()


def _next_request(context: _SessionContext) -> dict[str, Any] | None:
    if context.current_request is None:
        return None
    return context.current_request.to_dict()


def _close_store(store: EventStore) -> None:
    try:
        store.close()
    except Exception as exc:
        raise _integrity("cannot close SQLite EventStore", cause=exc) from exc


def _append_transition(
    context: _SessionContext, intent: ActionIntent
) -> tuple[Any, Any, str, str]:
    state_before = copy.deepcopy(context.current_state)
    before_hash = state_hash(state_before.__dict__)
    try:
        execution = execute_action(state_before, intent)
    except Exception as exc:
        raise SessionError("ENGINE_REJECTED_LEGAL_CHOICE", "engine rejected the selected legal choice") from exc
    if not execution.accepted or len(execution.events) != 1 or execution.final_state is None:
        raise SessionError("ENGINE_REJECTED_LEGAL_CHOICE", "engine rejected the selected legal choice")
    event = execution.events[0]
    state_after = execution.final_state
    if state_hash(state_before.__dict__) != before_hash:
        raise _integrity("engine mutated the pre-action state")
    after_hash = state_hash(state_after.__dict__)
    store = EventStore(context.paths.database)
    try:
        store.append_transition(
            context.manifest.campaign_id,
            event,
            state_before,
            state_after,
        )
    except Exception as exc:
        raise _integrity("SQLite transition append failed", cause=exc) from exc
    finally:
        _close_store(store)
    return execution, event, before_hash, after_hash


class SessionService:
    """One-shot service facade; each method opens and closes SQLite per call."""

    def __init__(self, session_dir: str | Path) -> None:
        self.session_dir = Path(session_dir)

    @classmethod
    def start(
        cls,
        session_dir: str | Path,
        *,
        session_id: str,
        actor_id: str,
        max_decisions: int,
        initial_state_path: str | Path,
    ) -> dict[str, Any]:
        target = Path(session_dir)
        validate_stable_id(session_id, "session_id")
        validate_stable_id(actor_id, "actor_id")
        _validate_max_decisions(max_decisions)
        if target.exists():
            raise SessionError("SESSION_ALREADY_EXISTS", "session directory already exists")

        initial_state = _read_initial_state(initial_state_path)
        initial_request = _build_request(initial_state, 1, code="INVALID_INITIAL_STATE")
        status = "AWAITING_DECISION" if initial_request.choices else "NO_LEGAL_ACTIONS"
        manifest = SessionManifest.create(
            session_id=session_id,
            actor_id=actor_id,
            max_decisions=max_decisions,
            accepted_decisions=0,
            recorded_decision_count=0,
            status=status,
            stop_reason=None if status == "AWAITING_DECISION" else "NO_LEGAL_ACTIONS",
            current_event_seq=initial_state.event_seq,
            current_state_decision_seq=initial_state.decision_seq,
            current_state_hash=state_hash(initial_state.__dict__),
            current_request_fingerprint=(
                initial_request.request_fingerprint
                if status == "AWAITING_DECISION"
                else None
            ),
        )

        temporary_dir: Path | None = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary_dir = Path(
                tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent)
            )
            paths = _SessionPaths(temporary_dir)
            store = EventStore(paths.database)
            try:
                store.initialize(
                    manifest.campaign_id,
                    copy.deepcopy(initial_state.__dict__),
                    seed=initial_state.seed,
                )
            except Exception as exc:
                raise _integrity("cannot initialize session SQLite", cause=exc) from exc
            finally:
                _close_store(store)

            _atomic_write_text(
                paths.decisions,
                export_recorded_decisions(tuple()),
            )
            _atomic_write_json(paths.manifest, manifest.to_dict())
            _load_context(temporary_dir)
            try:
                os.rename(temporary_dir, target)
            except FileExistsError as exc:
                raise SessionError("SESSION_ALREADY_EXISTS", "session directory already exists") from exc
            temporary_dir = None
            return {"ok": True, "session": manifest.public_summary()}
        except SessionError:
            raise
        except Exception as exc:
            raise _integrity("session creation failed", cause=exc) from exc
        finally:
            if temporary_dir is not None:
                shutil.rmtree(temporary_dir, ignore_errors=True)

    def _load(self) -> _SessionContext:
        return _load_context(self.session_dir)

    def next(self) -> dict[str, Any]:
        context = self._load()
        return {
            "ok": True,
            "session": _session_summary(context),
            "request": _next_request(context),
        }

    def status(self) -> dict[str, Any]:
        context = self._load()
        return {"ok": True, "session": _session_summary(context)}

    def choose(self, *, request_fingerprint: str, choice_id: str) -> dict[str, Any]:
        context = self._load()
        if context.manifest.status != "AWAITING_DECISION":
            raise SessionError("SESSION_TERMINAL", "session is not accepting decisions")
        request = context.current_request
        if request is None or request_fingerprint != request.request_fingerprint:
            raise SessionError("STALE_REQUEST", "request fingerprint is stale")
        selected = next(
            (choice for choice in request.choices if choice.choice_id == choice_id),
            None,
        )
        if selected is None:
            raise SessionError("UNKNOWN_CHOICE", "choice_id is not currently legal")

        decision_number = context.manifest.accepted_decisions + 1
        action_id = (
            f"{context.manifest.actor_id}-external-"
            f"{context.manifest.session_id}-{decision_number}"
        )
        intent = ActionIntent(
            action_id=action_id,
            actor_id=context.manifest.actor_id,
            action_type=selected.action_type,
            params=selected.params,
        )
        execution, event, before_hash, after_hash = _append_transition(context, intent)
        new_records = context.records + (
            RecordedDecision(
                decision_number=decision_number,
                request_fingerprint=request.request_fingerprint,
                outcome="ACTION",
                choice_id=selected.choice_id,
                action_type=selected.action_type,
                params=selected.params,
                raw_response=canonical_json({"choice_id": selected.choice_id}),
            ),
        )
        accepted = context.manifest.accepted_decisions + 1
        next_request = None
        if accepted >= context.manifest.max_decisions:
            status = "MAX_DECISIONS"
            stop_reason = "MAX_DECISIONS"
        else:
            next_request = _build_request(
                execution.final_state,
                accepted + 1,
                code="SESSION_INTEGRITY_MISMATCH",
            )
            if next_request.choices:
                status = "AWAITING_DECISION"
                stop_reason = None
            else:
                status = "NO_LEGAL_ACTIONS"
                stop_reason = "NO_LEGAL_ACTIONS"
                next_request = None
        new_manifest = SessionManifest.create(
            session_id=context.manifest.session_id,
            actor_id=context.manifest.actor_id,
            max_decisions=context.manifest.max_decisions,
            accepted_decisions=accepted,
            recorded_decision_count=len(new_records),
            status=status,
            stop_reason=stop_reason,
            current_event_seq=execution.final_state.event_seq,
            current_state_decision_seq=execution.final_state.decision_seq,
            current_state_hash=after_hash,
            current_request_fingerprint=(
                next_request.request_fingerprint
                if status == "AWAITING_DECISION"
                else None
            ),
        )
        paths = context.paths
        _atomic_write_text(paths.decisions, export_recorded_decisions(new_records))
        _atomic_write_json(paths.manifest, new_manifest.to_dict())
        verified = self._load()
        return {
            "ok": True,
            "session": _session_summary(verified),
            "result": {
                "choice_id": selected.choice_id,
                "action_id": action_id,
                "action_type": selected.action_type,
                "event_seq": event.event_seq,
                "event_type": event.event_type,
                "state_hash_before": before_hash,
                "state_hash_after": after_hash,
            },
            "request": _next_request(verified),
        }

    def stop(self, *, request_fingerprint: str) -> dict[str, Any]:
        context = self._load()
        if context.manifest.status != "AWAITING_DECISION":
            raise SessionError("SESSION_TERMINAL", "session is not accepting a stop")
        request = context.current_request
        if request is None or request_fingerprint != request.request_fingerprint:
            raise SessionError("STALE_REQUEST", "request fingerprint is stale")
        decision_number = context.manifest.accepted_decisions + 1
        new_records = context.records + (
            RecordedDecision(
                decision_number=decision_number,
                request_fingerprint=request.request_fingerprint,
                outcome="STOP",
                choice_id=None,
                action_type=None,
                params={},
                raw_response=canonical_json({"stop": True}),
            ),
        )
        new_manifest = SessionManifest.create(
            session_id=context.manifest.session_id,
            actor_id=context.manifest.actor_id,
            max_decisions=context.manifest.max_decisions,
            accepted_decisions=context.manifest.accepted_decisions,
            recorded_decision_count=len(new_records),
            status="STOPPED",
            stop_reason="EXPLICIT_STOP",
            current_event_seq=context.current_state.event_seq,
            current_state_decision_seq=context.current_state.decision_seq,
            current_state_hash=state_hash(context.current_state.__dict__),
            current_request_fingerprint=None,
        )
        _atomic_write_text(context.paths.decisions, export_recorded_decisions(new_records))
        _atomic_write_json(context.paths.manifest, new_manifest.to_dict())
        verified = self._load()
        return {"ok": True, "session": _session_summary(verified), "request": None}

    def verify(self) -> dict[str, Any]:
        context = self._load()
        return {
            "ok": True,
            "session": _session_summary(context),
            "verification": {
                "event_replay": True,
                "recorded_decision_replay": True,
                "recorded_decision_replay_completion_calls": 0,
                "sqlite_persistence_integrity": True,
                "sqlite_close_reopen": True,
                "event_count": len(context.event_records),
                "recorded_decision_count": len(context.records),
            },
        }


def start_session(
    session_dir: str | Path,
    *,
    session_id: str,
    actor_id: str,
    max_decisions: int,
    initial_state_path: str | Path,
) -> dict[str, Any]:
    return SessionService.start(
        session_dir,
        session_id=session_id,
        actor_id=actor_id,
        max_decisions=max_decisions,
        initial_state_path=initial_state_path,
    )


def next_session(session_dir: str | Path) -> dict[str, Any]:
    return SessionService(session_dir).next()


def choose_session(
    session_dir: str | Path, *, request_fingerprint: str, choice_id: str
) -> dict[str, Any]:
    return SessionService(session_dir).choose(
        request_fingerprint=request_fingerprint, choice_id=choice_id
    )


def stop_session(
    session_dir: str | Path, *, request_fingerprint: str
) -> dict[str, Any]:
    return SessionService(session_dir).stop(request_fingerprint=request_fingerprint)


def status_session(session_dir: str | Path) -> dict[str, Any]:
    return SessionService(session_dir).status()


def verify_session(session_dir: str | Path) -> dict[str, Any]:
    return SessionService(session_dir).verify()
