from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.domain.models import Severity

ValidatorName = Literal[
    "Canon Validator",
    "Timeline Validator",
    "Knowledge Validator",
    "Character Validator",
    "Economy / Power Validator",
    "Contract Validator",
    "Debt Validator",
    "Payoff Validator",
    "Repetition Validator",
    "Style Validator",
]

VALIDATOR_NAMES: tuple[ValidatorName, ...] = (
    "Canon Validator",
    "Timeline Validator",
    "Knowledge Validator",
    "Character Validator",
    "Economy / Power Validator",
    "Contract Validator",
    "Debt Validator",
    "Payoff Validator",
    "Repetition Validator",
    "Style Validator",
)


class ValidationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Severity
    message: str
    evidence: list[str] = Field(default_factory=list)
    location: str | None = None
    suggested_fix: str | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validator: ValidatorName
    passed: bool
    severity: Severity
    findings: list[ValidationFinding] = Field(default_factory=list)
    measurements: dict[str, Any] = Field(default_factory=dict)


class ValidationBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    book_id: str
    draft_id: str
    contract_id: str
    content_sha256: str
    projection_sha256: str
    through_event_seq: int
    passed: bool
    reports: list[ValidationReport] = Field(min_length=10, max_length=10)
    created_at: str
