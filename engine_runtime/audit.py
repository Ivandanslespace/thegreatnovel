"""回合决策来源与数据库影响的可审计日志。"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


AUDIT_JSONL = "decision_audit.jsonl"
AUDIT_MARKDOWN = "decision_audit.md"
AUDIT_VERSION = "1.0"
AUDIT_STATE_KEYS = ("player", "inventory", "base", "npcs", "factions", "relationships", "meta")
VOLATILE_META_KEYS = {"last_played"}


def _flatten(value: Any, prefix: str = "") -> Dict[str, Any]:
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for key, child in value.items():
            if prefix == "meta" and str(key) in VOLATILE_META_KEYS:
                continue
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(child, child_prefix))
        return result
    if isinstance(value, list):
        return {prefix: deepcopy(value)}
    return {prefix: deepcopy(value)}


def state_diff(before: Optional[Mapping[str, Any]], after: Optional[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """只比较会影响玩法的状态区，避免把世界静态配置和故事摘要混入审计。"""
    before = before or {}
    after = after or {}
    before_flat: Dict[str, Any] = {}
    after_flat: Dict[str, Any] = {}
    for key in AUDIT_STATE_KEYS:
        before_flat.update(_flatten(before.get(key, {}), key))
        after_flat.update(_flatten(after.get(key, {}), key))
    diff: Dict[str, Dict[str, Any]] = {}
    for path in sorted(set(before_flat) | set(after_flat)):
        old = before_flat.get(path)
        new = after_flat.get(path)
        if old != new:
            diff[path] = {"before": old, "after": new}
    return diff


def _next_audit_id(save_dir: Path, turn: int, status: str) -> str:
    return f"turn-{int(turn):04d}-{status.lower()}-{uuid.uuid4().hex[:8]}"


def append_audit_record(save_dir: str | Path, record: Mapping[str, Any]) -> Dict[str, Any]:
    """追加一条 JSONL 审计记录和对应的人类可读摘要。"""
    path = Path(save_dir)
    jsonl_path = path / AUDIT_JSONL
    markdown_path = path / AUDIT_MARKDOWN
    payload = deepcopy(dict(record))
    payload.setdefault("audit_version", AUDIT_VERSION)
    payload.setdefault("audit_id", _next_audit_id(path, int(payload.get("turn", 0)), str(payload.get("status", "UNKNOWN"))))
    payload.setdefault("recorded_at", datetime.now().astimezone().isoformat(timespec="seconds"))

    existing = jsonl_path.read_text(encoding="utf-8") if jsonl_path.exists() else ""
    if any(f'"audit_id": "{payload["audit_id"]}"' in line for line in existing.splitlines()):
        raise ValueError(f"审计记录已存在：{payload['audit_id']}")
    jsonl_path.write_text(existing.rstrip() + ("\n" if existing.strip() else "") + json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    if markdown_path.exists():
        markdown = markdown_path.read_text(encoding="utf-8")
    else:
        markdown = "# 决策审计\n\n"
    player = payload.get("player", {})
    llm = payload.get("llm", {})
    python = payload.get("python", {})
    joint = payload.get("joint", {})
    impact = payload.get("player_database_impact", {})
    markdown_block = (
        f"\n---\n\n## Turn {payload.get('turn')} · {payload.get('status')} · {payload.get('audit_id')}\n\n"
        f"- 玩家输入：{player.get('raw_input', '')}\n"
        f"- LLM职责：{', '.join(llm.get('responsibilities', []))}\n"
        f"- Python职责：{', '.join(python.get('responsibilities', []))}\n"
        f"- 联合链：{' → '.join(joint.get('decision_chain', []))}\n"
        f"- 数据库影响字段数：{len(impact.get('state_diff', {}))}\n\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```\n"
    )
    markdown_path.write_text(markdown.rstrip() + markdown_block, encoding="utf-8", newline="\n")
    return payload


def build_execution_audit(
    *,
    turn: int,
    player_input: str,
    action: Optional[Mapping[str, Any]],
    gm_response: str,
    result: Optional[Mapping[str, Any]],
    before_state: Optional[Mapping[str, Any]],
    after_state: Optional[Mapping[str, Any]],
    intent_source: str = "player_free_text",
) -> Dict[str, Any]:
    result = result or {}
    event = result.get("event", {}) if isinstance(result, Mapping) else {}
    resolution = result.get("resolution", {}) if isinstance(result, Mapping) else {}
    return {
        "turn": int(turn),
        "status": "EXECUTED",
        "event_id": event.get("event_id") if isinstance(event, Mapping) else None,
        "player": {
            "raw_input": str(player_input),
            "intent_source": intent_source,
            "confirmed": True,
            "influence_path": "玩家原话/选项 → LLM意图 → Python校验 → Python状态增量",
        },
        "llm": {
            "responsibilities": ["解析玩家意图", "选择叙事呈现", "生成GM完整回答"],
            "intent": deepcopy(dict(action)) if isinstance(action, Mapping) else None,
            "narrative_response": str(gm_response),
        },
        "python": {
            "responsibilities": ["合法性校验", "派生成本与随机种子", "执行硬公式", "生成事件", "应用数据库增量"],
            "validation": {"accepted": True, "errors": []},
            "resolution": deepcopy(resolution),
            "event_type": event.get("type") if isinstance(event, Mapping) else None,
            "action_ledger": deepcopy(event.get("data", {}).get("action_ledger", {})) if isinstance(event, Mapping) and isinstance(event.get("data"), Mapping) else {},
            "metrics": deepcopy(result.get("metrics", {})),
        },
        "joint": {
            "responsibilities": ["玩家选择行动方向", "LLM将意图转换为协议JSON", "Python将协议JSON转换为确定性后果", "LLM将后果写成小说"],
            "decision_chain": ["player_input", "llm.intent", "python.validation", "python.resolution", "python.event", "llm.narrative_response"],
        },
        "player_database_impact": {
            "action_fields": sorted(action.keys()) if isinstance(action, Mapping) else [],
            "state_diff": state_diff(before_state, after_state),
        },
    }


def build_rejected_audit(*, turn: int, player_input: str, action: Optional[Mapping[str, Any]], error: str, stage: str) -> Dict[str, Any]:
    return {
        "turn": int(turn),
        "status": "REJECTED",
        "player": {"raw_input": str(player_input or ""), "confirmed": False},
        "llm": {"responsibilities": ["提交待校验意图"], "intent": deepcopy(dict(action)) if isinstance(action, Mapping) else None},
        "python": {"responsibilities": ["拦截非法或不完整请求"], "validation": {"accepted": False, "stage": stage, "error": str(error)}},
        "joint": {"decision_chain": ["player_input", "llm.intent", "python.validation_rejected"]},
        "player_database_impact": {"action_fields": sorted(action.keys()) if isinstance(action, Mapping) else [], "state_diff": {}},
    }
