"""Small deterministic builder/parser for the Phase 9C2 novel artifact."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .common import sha256_bytes, strict_int


_COUNT_RE = re.compile(r"0|[1-9][0-9]*\Z")
_MODES = frozenset({"snapshot", "final"})
_TERMINAL_REASONS = frozenset({"EXPLICIT_STOP", "MAX_DECISIONS", "NO_LEGAL_ACTIONS"})


@dataclass(frozen=True)
class NovelHeader:
    story_id: str
    campaign_id: str
    session_id: str
    export_mode: str
    accepted_decisions: int
    recorded_decision_count: int


def _parse_count(line: str, field: str) -> int:
    prefix = f"{field}: "
    if not line.startswith(prefix):
        raise ValueError("novel header is invalid")
    raw = line[len(prefix) :]
    if _COUNT_RE.fullmatch(raw) is None:
        raise ValueError("novel header count is invalid")
    return strict_int(int(raw), field, nonnegative=True)


def parse_novel_header(payload: bytes) -> NovelHeader:
    """Parse only the fixed header; turn/prose boundaries are never trusted."""

    if not isinstance(payload, bytes):
        raise ValueError("novel payload must be bytes")
    text = payload.decode("utf-8")
    if "\r" in text or not text.endswith("\n"):
        raise ValueError("novel text encoding is invalid")
    lines = text.split("\n")
    if len(lines) < 9 or lines[0:2] != ["# TheGreatNovel", ""] or lines[8] != "":
        raise ValueError("novel header is invalid")
    values: dict[str, str] = {}
    for field in ("story_id", "campaign_id", "session_id"):
        prefix = f"{field}: "
        line = lines[{"story_id": 2, "campaign_id": 3, "session_id": 4}[field]]
        if not line.startswith(prefix) or not line[len(prefix) :]:
            raise ValueError("novel identity header is invalid")
        values[field] = line[len(prefix) :]
    mode_line = lines[5]
    if not mode_line.startswith("export_mode: "):
        raise ValueError("novel mode header is invalid")
    mode = mode_line[len("export_mode: ") :]
    if mode not in _MODES:
        raise ValueError("novel mode is unsupported")
    return NovelHeader(
        story_id=values["story_id"],
        campaign_id=values["campaign_id"],
        session_id=values["session_id"],
        export_mode=mode,
        accepted_decisions=_parse_count(lines[6], "accepted_decisions"),
        recorded_decision_count=_parse_count(lines[7], "recorded_decision_count"),
    )


def build_novel(
    *,
    story_id: str,
    campaign_id: str,
    session_id: str,
    mode: str,
    accepted_decisions: int,
    recorded_decision_count: int,
    turns: Iterable[Any],
    stop_reason: str | None = None,
) -> bytes:
    """Build the exact UTF-8 Markdown representation from committed turns."""

    if mode not in _MODES:
        raise ValueError("novel mode is unsupported")
    accepted = strict_int(accepted_decisions, "accepted_decisions", nonnegative=True)
    recorded = strict_int(recorded_decision_count, "recorded_decision_count", nonnegative=True)
    if recorded < accepted:
        raise ValueError("recorded_decision_count cannot be below accepted_decisions")
    if mode == "snapshot" and stop_reason is not None:
        raise ValueError("snapshot cannot contain a stop reason")
    if mode == "final" and stop_reason not in _TERMINAL_REASONS:
        raise ValueError("final novel requires a supported stop reason")

    turn_values = tuple(turns)
    if len(turn_values) != accepted:
        raise ValueError("novel turn count does not match accepted_decisions")
    lines = [
        "# TheGreatNovel",
        "",
        f"story_id: {story_id}",
        f"campaign_id: {campaign_id}",
        f"session_id: {session_id}",
        f"export_mode: {mode}",
        f"accepted_decisions: {accepted}",
        f"recorded_decision_count: {recorded}",
        "",
    ]
    for index, turn in enumerate(turn_values, start=1):
        expected_turn_id = f"turn-{index:06d}"
        if turn.turn_id != expected_turn_id:
            raise ValueError("novel turns are not a contiguous prefix")
        lines.extend(
            [
                f"## {turn.turn_id}",
                f"locale: {turn.narration_locale}",
                f"voice_id: {turn.voice_id}",
                f"action_type: {turn.action_type}",
                "",
                turn.prose,
                "",
                "---",
                "",
            ]
        )
    if mode == "snapshot":
        lines.extend(["## status", "status: SNAPSHOT", ""])
    else:
        lines.extend(["## terminal", f"stop_reason: {stop_reason}", ""])
    return "\n".join(lines).encode("utf-8")


def novel_sha256(payload: bytes) -> str:
    return sha256_bytes(payload)


__all__ = ["NovelHeader", "build_novel", "novel_sha256", "parse_novel_header"]
