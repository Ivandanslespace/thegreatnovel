"""Small immutable edge records for the Phase 8 LLM Player slice."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..core.hashing import canonical_json

_UNSET_PARAMS = object()


class LLMOutputError(ValueError):
    """An injected completion did not satisfy the strict response contract."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class RecordedDecisionMismatch(ValueError):
    """A recorded player choice does not match the current visible request."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class RecordedDecisionFormatError(ValueError):
    """A RecordedDecision bundle or record violates its fixed schema."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _canonical_json_dict(value: Any, path: str) -> str:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be dict")
    try:
        return canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path} must contain canonical JSON values") from exc


@dataclass(frozen=True, init=False)
class LLMActionChoice:
    """One engine-provided legal action exposed at the LLM edge."""

    choice_id: str
    action_type: str
    _params_json: str = field(repr=False)
    duration_minutes: int | None
    stamina_cost: int

    def __init__(
        self,
        choice_id: str,
        action_type: str,
        params: dict[str, Any],
        duration_minutes: int | None,
        stamina_cost: int,
    ) -> None:
        if not isinstance(choice_id, str) or not choice_id:
            raise ValueError("choice_id must be a non-empty string")
        if not isinstance(action_type, str) or not action_type:
            raise ValueError("action_type must be a non-empty string")
        if duration_minutes is not None and (
            isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int)
        ):
            raise ValueError("duration_minutes must be int or None")
        if isinstance(stamina_cost, bool) or not isinstance(stamina_cost, int):
            raise ValueError("stamina_cost must be int")
        object.__setattr__(self, "choice_id", choice_id)
        object.__setattr__(self, "action_type", action_type)
        object.__setattr__(self, "_params_json", _canonical_json_dict(params, "params"))
        object.__setattr__(self, "duration_minutes", duration_minutes)
        object.__setattr__(self, "stamina_cost", stamina_cost)

    @property
    def params(self) -> dict[str, Any]:
        """Return a detached JSON-compatible params snapshot."""

        return json.loads(self._params_json)

    def to_dict(self) -> dict[str, Any]:
        return {
            "choice_id": self.choice_id,
            "action_type": self.action_type,
            "params": self.params,
            "duration_minutes": self.duration_minutes,
            "stamina_cost": self.stamina_cost,
        }


@dataclass(frozen=True, init=False)
class LLMDecisionRequest:
    """Detached, JSON-serializable input supplied to one completion call."""

    decision_number: int
    _observation_json: str = field(repr=False)
    choices: tuple[LLMActionChoice, ...]
    request_fingerprint: str

    def __init__(
        self,
        decision_number: int,
        observation: dict[str, Any],
        choices: tuple[LLMActionChoice, ...],
        request_fingerprint: str,
    ) -> None:
        if isinstance(decision_number, bool) or not isinstance(
            decision_number, int
        ) or decision_number <= 0:
            raise ValueError("decision_number must be a positive int")
        if not isinstance(observation, dict):
            raise ValueError("observation must be dict")
        if not isinstance(choices, tuple):
            choices = tuple(choices)
        if not all(isinstance(choice, LLMActionChoice) for choice in choices):
            raise ValueError("choices must contain LLMActionChoice objects")
        if not isinstance(request_fingerprint, str) or not request_fingerprint:
            raise ValueError("request_fingerprint must be a non-empty string")
        object.__setattr__(self, "decision_number", decision_number)
        object.__setattr__(
            self, "_observation_json", _canonical_json_dict(observation, "observation")
        )
        object.__setattr__(self, "choices", tuple(choices))
        object.__setattr__(self, "request_fingerprint", request_fingerprint)

    @property
    def observation(self) -> dict[str, Any]:
        """Return a detached JSON-compatible Observation snapshot."""

        return json.loads(self._observation_json)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_number": self.decision_number,
            "observation": self.observation,
            "choices": [choice.to_dict() for choice in self.choices],
            "request_fingerprint": self.request_fingerprint,
        }


@dataclass(frozen=True, init=False)
class RecordedDecision:
    """Immutable edge artifact for one ACTION or STOP player decision."""

    decision_number: int
    request_fingerprint: str
    outcome: str
    choice_id: str | None
    action_type: str | None
    _params_json: str = field(repr=False)
    raw_response: str

    def __init__(
        self,
        decision_number: int,
        request_fingerprint: str,
        outcome: str,
        choice_id: str | None,
        action_type: str | None,
        params: dict[str, Any] | object = _UNSET_PARAMS,
        raw_response: str = "",
    ) -> None:
        if params is _UNSET_PARAMS:
            params = {}
        if isinstance(decision_number, bool) or not isinstance(
            decision_number, int
        ) or decision_number <= 0:
            raise RecordedDecisionFormatError(
                "INVALID_DECISION_NUMBER", "decision_number must be a positive int"
            )
        if not isinstance(request_fingerprint, str) or not request_fingerprint:
            raise RecordedDecisionFormatError(
                "INVALID_FINGERPRINT", "request_fingerprint must be non-empty"
            )
        if outcome not in {"ACTION", "STOP"}:
            raise RecordedDecisionFormatError(
                "INVALID_OUTCOME", "outcome must be ACTION or STOP"
            )
        if not isinstance(raw_response, str):
            raise RecordedDecisionFormatError(
                "INVALID_RAW_RESPONSE", "raw_response must be string"
            )
        try:
            params_json = _canonical_json_dict(params, "params")
        except ValueError as exc:
            raise RecordedDecisionFormatError("NON_CANONICAL_JSON", str(exc)) from exc
        if outcome == "ACTION":
            if not isinstance(choice_id, str) or not choice_id:
                raise RecordedDecisionFormatError(
                    "INVALID_ACTION_RECORD", "ACTION requires choice_id"
                )
            if not isinstance(action_type, str) or not action_type:
                raise RecordedDecisionFormatError(
                    "INVALID_ACTION_RECORD", "ACTION requires action_type"
                )
        else:
            if choice_id is not None or action_type is not None or json.loads(params_json) != {}:
                raise RecordedDecisionFormatError(
                    "INVALID_STOP_RECORD",
                    "STOP requires null choice/action type and empty params",
                )
        object.__setattr__(self, "decision_number", decision_number)
        object.__setattr__(self, "request_fingerprint", request_fingerprint)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "choice_id", choice_id)
        object.__setattr__(self, "action_type", action_type)
        object.__setattr__(self, "_params_json", params_json)
        object.__setattr__(self, "raw_response", raw_response)

    @property
    def params(self) -> dict[str, Any]:
        """Return a detached JSON-compatible params snapshot."""

        return json.loads(self._params_json)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_number": self.decision_number,
            "request_fingerprint": self.request_fingerprint,
            "outcome": self.outcome,
            "choice_id": self.choice_id,
            "action_type": self.action_type,
            "params": self.params,
            "raw_response": self.raw_response,
        }
