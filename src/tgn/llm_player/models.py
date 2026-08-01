"""Small immutable edge records for the Phase 8 LLM Player slice."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


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


def _copy_params(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be dict")
    return copy.deepcopy(value)


@dataclass(frozen=True)
class LLMActionChoice:
    """One engine-provided legal action exposed at the LLM edge."""

    choice_id: str
    action_type: str
    params: dict[str, Any]
    duration_minutes: int | None
    stamina_cost: int

    def __post_init__(self) -> None:
        if not isinstance(self.choice_id, str) or not self.choice_id:
            raise ValueError("choice_id must be a non-empty string")
        if not isinstance(self.action_type, str) or not self.action_type:
            raise ValueError("action_type must be a non-empty string")
        if self.duration_minutes is not None and (
            isinstance(self.duration_minutes, bool)
            or not isinstance(self.duration_minutes, int)
        ):
            raise ValueError("duration_minutes must be int or None")
        if isinstance(self.stamina_cost, bool) or not isinstance(self.stamina_cost, int):
            raise ValueError("stamina_cost must be int")
        object.__setattr__(self, "params", _copy_params(self.params, "params"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "choice_id": self.choice_id,
            "action_type": self.action_type,
            "params": copy.deepcopy(self.params),
            "duration_minutes": self.duration_minutes,
            "stamina_cost": self.stamina_cost,
        }


@dataclass(frozen=True)
class LLMDecisionRequest:
    """Detached, JSON-serializable input supplied to one completion call."""

    decision_number: int
    observation: dict[str, Any]
    choices: tuple[LLMActionChoice, ...]
    request_fingerprint: str

    def __post_init__(self) -> None:
        if isinstance(self.decision_number, bool) or not isinstance(
            self.decision_number, int
        ) or self.decision_number <= 0:
            raise ValueError("decision_number must be a positive int")
        if not isinstance(self.observation, dict):
            raise ValueError("observation must be dict")
        if not isinstance(self.choices, tuple):
            object.__setattr__(self, "choices", tuple(self.choices))
        if not isinstance(self.request_fingerprint, str) or not self.request_fingerprint:
            raise ValueError("request_fingerprint must be a non-empty string")
        object.__setattr__(self, "observation", copy.deepcopy(self.observation))
        object.__setattr__(self, "choices", copy.deepcopy(self.choices))

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_number": self.decision_number,
            "observation": copy.deepcopy(self.observation),
            "choices": [choice.to_dict() for choice in self.choices],
            "request_fingerprint": self.request_fingerprint,
        }


@dataclass(frozen=True)
class RecordedDecision:
    """Immutable edge artifact for one ACTION or STOP player decision."""

    decision_number: int
    request_fingerprint: str
    outcome: str
    choice_id: str | None
    action_type: str | None
    params: dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.decision_number, bool) or not isinstance(
            self.decision_number, int
        ) or self.decision_number <= 0:
            raise RecordedDecisionFormatError(
                "INVALID_DECISION_NUMBER", "decision_number must be a positive int"
            )
        if not isinstance(self.request_fingerprint, str) or not self.request_fingerprint:
            raise RecordedDecisionFormatError(
                "INVALID_FINGERPRINT", "request_fingerprint must be non-empty"
            )
        if self.outcome not in {"ACTION", "STOP"}:
            raise RecordedDecisionFormatError(
                "INVALID_OUTCOME", "outcome must be ACTION or STOP"
            )
        if not isinstance(self.raw_response, str):
            raise RecordedDecisionFormatError(
                "INVALID_RAW_RESPONSE", "raw_response must be string"
            )
        try:
            params = _copy_params(self.params, "params")
        except ValueError as exc:
            raise RecordedDecisionFormatError("INVALID_PARAMS", str(exc)) from exc
        if self.outcome == "ACTION":
            if not isinstance(self.choice_id, str) or not self.choice_id:
                raise RecordedDecisionFormatError(
                    "INVALID_ACTION_RECORD", "ACTION requires choice_id"
                )
            if not isinstance(self.action_type, str) or not self.action_type:
                raise RecordedDecisionFormatError(
                    "INVALID_ACTION_RECORD", "ACTION requires action_type"
                )
        else:
            if self.choice_id is not None or self.action_type is not None or params != {}:
                raise RecordedDecisionFormatError(
                    "INVALID_STOP_RECORD",
                    "STOP requires null choice/action type and empty params",
                )
        object.__setattr__(self, "params", params)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_number": self.decision_number,
            "request_fingerprint": self.request_fingerprint,
            "outcome": self.outcome,
            "choice_id": self.choice_id,
            "action_type": self.action_type,
            "params": copy.deepcopy(self.params),
            "raw_response": self.raw_response,
        }
