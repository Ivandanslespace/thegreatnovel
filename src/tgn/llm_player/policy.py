"""Provider-neutral LLM adapter and RecordedDecision replay policy."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Iterable
from typing import Any

from ..actions.models import ActionIntent
from ..core.hashing import canonical_json
from .models import (
    LLMActionChoice,
    LLMDecisionRequest,
    LLMOutputError,
    RecordedDecision,
    RecordedDecisionFormatError,
    RecordedDecisionMismatch,
)

_RECORDED_SCHEMA_VERSION = 1
_RECORD_FIELDS = frozenset(
    {
        "decision_number",
        "request_fingerprint",
        "outcome",
        "choice_id",
        "action_type",
        "params",
        "raw_response",
    }
)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _load_json(payload: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant: {value}")

    return json.loads(
        payload,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=reject_constant,
    )


def _choice_from_legal_action(index: int, legal_action: Any) -> LLMActionChoice:
    try:
        action_type = legal_action.action_type
        params = legal_action.params
        duration_minutes = legal_action.duration_minutes
        stamina_cost = legal_action.stamina_cost
    except AttributeError as exc:
        raise ValueError("legal_actions must contain LegalAction-like objects") from exc
    return LLMActionChoice(
        choice_id=f"choice-{index:03d}",
        action_type=action_type,
        params=copy.deepcopy(params),
        duration_minutes=duration_minutes,
        stamina_cost=stamina_cost,
    )


def _fingerprint_payload(
    decision_number: int,
    observation: dict[str, Any],
    choices: tuple[LLMActionChoice, ...],
) -> dict[str, Any]:
    return {
        "decision_number": decision_number,
        "observation": copy.deepcopy(observation),
        "choices": [choice.to_dict() for choice in choices],
    }


def build_llm_decision_request(
    observation: dict[str, Any],
    decision_number: int,
) -> LLMDecisionRequest:
    """Convert one existing player Observation into a detached LLM request."""

    if not isinstance(observation, dict):
        raise ValueError("observation must be dict")
    if "legal_actions" not in observation:
        raise ValueError("observation must contain legal_actions")
    legal_actions = observation["legal_actions"]
    if not isinstance(legal_actions, (tuple, list)):
        raise ValueError("observation.legal_actions must be tuple or list")

    visible_observation = copy.deepcopy(observation)
    visible_observation.pop("legal_actions", None)
    choices = tuple(
        _choice_from_legal_action(index, legal_action)
        for index, legal_action in enumerate(legal_actions)
    )
    fingerprint_payload = _fingerprint_payload(
        decision_number, visible_observation, choices
    )
    fingerprint = hashlib.sha256(
        canonical_json(fingerprint_payload).encode("utf-8")
    ).hexdigest()
    return LLMDecisionRequest(
        decision_number=decision_number,
        observation=visible_observation,
        choices=choices,
        request_fingerprint=fingerprint,
    )


def build_llm_prompt(request: LLMDecisionRequest) -> str:
    """Build one stable edge prompt without exposing engine internals."""

    request_json = canonical_json(request.to_dict())
    return (
        "You are choosing one legal game action.\n"
        "You cannot alter the world state.\n"
        "Return strict JSON only.\n"
        "REQUEST_JSON:\n"
        f"{request_json}"
    )


def parse_llm_response(
    raw_response: str,
    request: LLMDecisionRequest,
) -> LLMActionChoice | None:
    """Parse exactly one action choice or an explicit stop response."""

    if not isinstance(raw_response, str):
        raise LLMOutputError("INVALID_SCHEMA", "completion response must be string")
    try:
        parsed = _load_json(raw_response)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LLMOutputError("INVALID_JSON", "response is not one JSON object") from exc
    if not isinstance(parsed, dict):
        raise LLMOutputError("INVALID_SCHEMA", "response must be a JSON object")

    fields = set(parsed)
    if fields == {"stop"}:
        if parsed["stop"] is True:
            return None
        raise LLMOutputError("INVALID_SCHEMA", "stop must be strictly true")

    if fields != {"choice_id"}:
        raise LLMOutputError(
            "INVALID_SCHEMA", "response must contain exactly choice_id or stop"
        )
    choice_id = parsed["choice_id"]
    if not isinstance(choice_id, str) or not choice_id:
        raise LLMOutputError("INVALID_SCHEMA", "choice_id must be non-empty string")
    for choice in request.choices:
        if choice.choice_id == choice_id:
            return choice
    raise LLMOutputError("UNKNOWN_CHOICE", f"unknown choice_id: {choice_id}")


class LLMPlayerPolicy:
    """Callable edge policy that delegates exactly once per decision."""

    def __init__(self, completion: Callable[[str], str]) -> None:
        if not callable(completion):
            raise TypeError("completion must be callable")
        self._completion = completion
        self._records: list[RecordedDecision] = []

    @property
    def recorded_decisions(self) -> tuple[RecordedDecision, ...]:
        return copy.deepcopy(tuple(self._records))

    def __call__(
        self,
        observation: dict[str, Any],
        decision_number: int,
        actor_id: str,
    ) -> ActionIntent | None:
        request = build_llm_decision_request(observation, decision_number)
        prompt = build_llm_prompt(request)
        raw_response = self._completion(prompt)
        selected = parse_llm_response(raw_response, request)

        if selected is None:
            self._records.append(
                RecordedDecision(
                    decision_number=decision_number,
                    request_fingerprint=request.request_fingerprint,
                    outcome="STOP",
                    choice_id=None,
                    action_type=None,
                    params={},
                    raw_response=raw_response,
                )
            )
            return None

        self._records.append(
            RecordedDecision(
                decision_number=decision_number,
                request_fingerprint=request.request_fingerprint,
                outcome="ACTION",
                choice_id=selected.choice_id,
                action_type=selected.action_type,
                params=selected.params,
                raw_response=raw_response,
            )
        )
        return ActionIntent(
            action_id=f"{actor_id}-llm-{decision_number}",
            actor_id=actor_id,
            action_type=selected.action_type,
            params=copy.deepcopy(selected.params),
        )


def _validated_record_sequence(
    decisions: Iterable[RecordedDecision],
) -> tuple[RecordedDecision, ...]:
    records = tuple(copy.deepcopy(tuple(decisions)))
    for expected_number, record in enumerate(records, start=1):
        if not isinstance(record, RecordedDecision):
            raise RecordedDecisionFormatError(
                "INVALID_RECORD", "decisions must contain RecordedDecision objects"
            )
        if record.decision_number != expected_number:
            raise RecordedDecisionFormatError(
                "NON_CONTIGUOUS_DECISIONS",
                "decision_number values must start at 1 and be continuous",
            )
    return records


def export_recorded_decisions(
    decisions: tuple[RecordedDecision, ...],
) -> str:
    """Export a strict canonical JSON RecordedDecision bundle."""

    records = _validated_record_sequence(decisions)
    return canonical_json(
        {
            "schema_version": _RECORDED_SCHEMA_VERSION,
            "decisions": [record.to_dict() for record in records],
        }
    )


def import_recorded_decisions(payload: str) -> tuple[RecordedDecision, ...]:
    """Import and validate a strict canonical JSON RecordedDecision bundle."""

    if not isinstance(payload, str):
        raise RecordedDecisionFormatError("INVALID_JSON", "payload must be string")
    try:
        parsed = _load_json(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RecordedDecisionFormatError("INVALID_JSON", "invalid JSON bundle") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"schema_version", "decisions"}:
        raise RecordedDecisionFormatError(
            "INVALID_SCHEMA", "bundle fields must be schema_version and decisions"
        )
    if parsed["schema_version"] != _RECORDED_SCHEMA_VERSION:
        raise RecordedDecisionFormatError(
            "UNSUPPORTED_SCHEMA_VERSION", "schema_version must be 1"
        )
    if not isinstance(parsed["decisions"], list):
        raise RecordedDecisionFormatError("INVALID_SCHEMA", "decisions must be list")

    records: list[RecordedDecision] = []
    for item in parsed["decisions"]:
        if not isinstance(item, dict) or set(item) != _RECORD_FIELDS:
            raise RecordedDecisionFormatError(
                "INVALID_RECORD", "record has an invalid field set"
            )
        try:
            records.append(
                RecordedDecision(
                    decision_number=item["decision_number"],
                    request_fingerprint=item["request_fingerprint"],
                    outcome=item["outcome"],
                    choice_id=item["choice_id"],
                    action_type=item["action_type"],
                    params=item["params"],
                    raw_response=item["raw_response"],
                )
            )
        except RecordedDecisionFormatError:
            raise
        except (TypeError, ValueError) as exc:
            raise RecordedDecisionFormatError("INVALID_RECORD", str(exc)) from exc
    return _validated_record_sequence(records)


class RecordedDecisionPolicy:
    """Replay policy that never accepts or invokes a completion callable."""

    def __init__(self, decisions: tuple[RecordedDecision, ...]) -> None:
        self._records = _validated_record_sequence(decisions)
        self._index = 0

    @property
    def recorded_decisions(self) -> tuple[RecordedDecision, ...]:
        return copy.deepcopy(self._records)

    def assert_consumed(self) -> None:
        if self._index != len(self._records):
            raise RecordedDecisionMismatch(
                "RECORDS_REMAIN",
                f"{len(self._records) - self._index} recorded decisions remain",
            )

    def __call__(
        self,
        observation: dict[str, Any],
        decision_number: int,
        actor_id: str,
    ) -> ActionIntent | None:
        request = build_llm_decision_request(observation, decision_number)
        if self._index >= len(self._records):
            raise RecordedDecisionMismatch(
                "RECORDS_EXHAUSTED", "no recorded decision remains"
            )
        record = self._records[self._index]
        if record.decision_number != decision_number:
            raise RecordedDecisionMismatch(
                "DECISION_NUMBER_MISMATCH",
                f"expected {record.decision_number}, got {decision_number}",
            )
        if record.request_fingerprint != request.request_fingerprint:
            raise RecordedDecisionMismatch(
                "REQUEST_FINGERPRINT_MISMATCH", "visible request changed"
            )

        self._index += 1
        if record.outcome == "STOP":
            return None

        selected = next(
            (choice for choice in request.choices if choice.choice_id == record.choice_id),
            None,
        )
        if selected is None:
            self._index -= 1
            raise RecordedDecisionMismatch(
                "UNKNOWN_RECORDED_CHOICE", "recorded choice is not currently legal"
            )
        if record.action_type != selected.action_type:
            self._index -= 1
            raise RecordedDecisionMismatch(
                "ACTION_TYPE_MISMATCH", "recorded action_type differs from choice"
            )
        if record.params != selected.params:
            self._index -= 1
            raise RecordedDecisionMismatch(
                "PARAMS_MISMATCH", "recorded params differ from engine choice"
            )
        return ActionIntent(
            action_id=f"{actor_id}-llm-{decision_number}",
            actor_id=actor_id,
            action_type=selected.action_type,
            params=copy.deepcopy(selected.params),
        )
