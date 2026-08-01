"""Small immutable edge and compiled-artifact models for Phase 9B1."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any


COMPILER_ID = "phase9b-bounded-world-v1"
MECHANICS_PROFILE = "phase75_expedition_v1"
REQUEST_FIELDS = frozenset({"schema_version", "prompt"})
DRAFT_FIELDS = frozenset(
    {
        "schema_version",
        "mechanics_profile",
        "world_id",
        "content_locale",
        "title",
        "premise",
        "labels",
    }
)
LABEL_FIELDS = frozenset(
    {
        "base",
        "target",
        "resource",
        "hazard",
        "named_actor",
        "named_actor_role",
        "named_actor_public_goal",
    }
)


@dataclass(frozen=True)
class ValidationIssue:
    """A deterministic, client-repairable validation issue."""

    code: str
    path: str
    message: str
    expected: Any = None
    actual: Any = None
    allowed_values: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "expected": copy.deepcopy(self.expected),
            "actual": copy.deepcopy(self.actual),
            "allowed_values": copy.deepcopy(self.allowed_values),
        }


class WorldGenError(Exception):
    """Stable machine-readable error raised at the worldgen boundary."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        issues: tuple[ValidationIssue, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.issues = tuple(issues)

    def error_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}

    def issues_dict(self) -> list[dict[str, Any]]:
        return [issue.to_dict() for issue in self.issues]


@dataclass(frozen=True)
class WorldGenesisRequest:
    schema_version: int
    prompt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "prompt": self.prompt,
        }


@dataclass(frozen=True)
class WorldDraft:
    schema_version: int
    mechanics_profile: str
    world_id: str
    content_locale: str
    title: str
    premise: str
    labels: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mechanics_profile": self.mechanics_profile,
            "world_id": self.world_id,
            "content_locale": self.content_locale,
            "title": self.title,
            "premise": self.premise,
            "labels": copy.deepcopy(self.labels),
        }


@dataclass(frozen=True)
class CompiledWorldPack:
    schema_version: int
    compiler_id: str
    mechanics_profile: str
    world_id: str
    content_locale: str
    public_content: dict[str, Any]
    runtime_bindings: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "compiler_id": self.compiler_id,
            "mechanics_profile": self.mechanics_profile,
            "world_id": self.world_id,
            "content_locale": self.content_locale,
            "public_content": copy.deepcopy(self.public_content),
            "runtime_bindings": copy.deepcopy(self.runtime_bindings),
        }


@dataclass(frozen=True)
class BootstrapResult:
    passed: bool
    accepted_decisions: int
    events: int
    illegal_actions: int
    knowledge_boundary_violations: int
    event_replay: bool
    final_state_hash: str
    final_state: Any
    error: str | None = None

    def to_report(self) -> dict[str, Any]:
        return {
            "accepted_decisions": self.accepted_decisions,
            "events": self.events,
            "illegal_actions": self.illegal_actions,
            "knowledge_boundary_violations": self.knowledge_boundary_violations,
            "event_replay": self.event_replay,
            "final_state_hash": self.final_state_hash,
        }


@dataclass(frozen=True)
class CompilationResult:
    request: WorldGenesisRequest
    draft: WorldDraft
    compiled_worldpack: CompiledWorldPack
    initial_state: Any
    report: dict[str, Any]
    worldpack_hash: str
    initial_state_hash: str
