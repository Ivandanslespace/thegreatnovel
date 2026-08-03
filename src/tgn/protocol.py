"""JSON response helpers used by the Codex-facing CLI."""

from __future__ import annotations

from typing import Any


PROTOCOL_VERSION = "tgn.local.v1"
ENGINE_VERSION = "0.1.0"


def success_payload(*, command: str, data: dict[str, Any], **state: Any) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL_VERSION,
        "engine_version": ENGINE_VERSION,
        "ok": True,
        "command": command,
        **state,
        "data": data,
    }


def hello_payload() -> dict[str, Any]:
    return success_payload(
        command="hello",
        data={
            "blueprint_schema": "tgn.world.v1",
            "narration_schema": "tgn.narration.v1",
            "language": "zh-CN",
            "capabilities": [
                "deterministic_resolution",
                "event_replay",
                "offscreen_world_processes",
                "knowledge_projection",
                "transactional_autosave",
                "grounded_narration",
                "novel_draft_autosave",
                "final_novel_export",
                "lazy_expansion",
            ],
        },
    )

