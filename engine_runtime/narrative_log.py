"""将每回合的玩家输入、GM回答和 Python 事件写入本地存档。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from .audit import append_audit_record, build_execution_audit
from .state import load_game_state


NOVEL_FILENAME = "novel_draft.md"
CONVERSATION_FILENAME = "conversation_log.md"
TURN_MARKER = "<!-- narrative-turn:{turn} -->"
INTERNAL_PROTOCOL_PATTERNS = (
    r"预览合法", r"未结算", r"dry-run", r"action_id", r"确认执行", r"SQLite", r"Python",
)


def _has_turn(text: str, turn: int) -> bool:
    return TURN_MARKER.format(turn=turn) in text


def _read_or_header(path: Path, header: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return header + "\n"


def _write_pair_atomically(novel_path: Path, novel_text: str, conversation_path: Path, conversation_text: str) -> None:
    old_novel_exists = novel_path.exists()
    old_conversation_exists = conversation_path.exists()
    old_novel = novel_path.read_text(encoding="utf-8") if old_novel_exists else ""
    old_conversation = conversation_path.read_text(encoding="utf-8") if old_conversation_exists else ""
    try:
        novel_path.write_text(novel_text, encoding="utf-8", newline="\n")
        conversation_path.write_text(conversation_text, encoding="utf-8", newline="\n")
    except Exception:
        if old_novel_exists:
            novel_path.write_text(old_novel, encoding="utf-8", newline="\n")
        elif novel_path.exists():
            novel_path.unlink()
        if old_conversation_exists:
            conversation_path.write_text(old_conversation, encoding="utf-8", newline="\n")
        elif conversation_path.exists():
            conversation_path.unlink()
        raise


def validate_player_narrative(gm_response: str, result: Dict[str, Any] | None = None) -> None:
    """阻止主持协议泄漏，以及叙述声称不存在的状态变化。"""
    for pattern in INTERNAL_PROTOCOL_PATTERNS:
        if re.search(pattern, gm_response, flags=re.IGNORECASE):
            raise ValueError(f"GM回答包含不可展示的主持协议字段：{pattern}")
    result = result or {}
    event = result.get("event", {}) if isinstance(result, dict) else {}
    payload = event.get("data", {}) if isinstance(event, dict) and isinstance(event.get("data", {}), dict) else {}
    if re.search(r"已加固|加固完成|基地防御提升", gm_response):
        has_base_effect = any(
            payload.get(key) not in (None, 0, 0.0, "", {}, [])
            for key in ("base_durability_delta", "base_defense_delta", "base_space_delta", "base_module")
        )
        if not has_base_effect:
            raise ValueError("叙述声称基地已变化，但本回合事件没有对应的基地状态增量")


def record_narrative_turn(
    save_dir: str | Path,
    player_input: str,
    gm_response: str,
    *,
    action: Dict[str, Any] | None = None,
    before_state: Dict[str, Any] | None = None,
    result: Dict[str, Any] | None = None,
    intent_source: str = "player_free_text",
) -> Dict[str, Any]:
    """记录当前存档回合；同一回合只能记录一次。"""
    # 保留玩家原话的每个字符；只用 strip 做空白判定，不能把它写回去。
    player_input = str(player_input or "")
    gm_response = str(gm_response or "")
    if not player_input.strip():
        raise ValueError("缺少玩家原始输入，不能记录小说回合")
    if not gm_response.strip():
        raise ValueError("缺少GM完整回答，不能记录小说回合")
    validate_player_narrative(gm_response, result)

    state = load_game_state(save_dir)
    turn = state.current_turn
    history = state.event_history()
    current_events = [item for item in history if int(item.get("turn", -1)) == turn]
    if not current_events:
        raise ValueError(f"当前回合 {turn} 没有对应 Python 事件，拒绝记录")
    latest = current_events[-1]
    record = latest["record"]
    validate_player_narrative(gm_response, result or {"event": record})
    world_name = str(state.data.get("world", {}).get("name") or state.meta.get("world_name") or "未命名世界")
    timestamp = str(record.get("timestamp") or state.meta.get("last_played") or "")
    marker = TURN_MARKER.format(turn=turn)

    novel_path = Path(save_dir) / NOVEL_FILENAME
    conversation_path = Path(save_dir) / CONVERSATION_FILENAME
    novel_text = _read_or_header(novel_path, f"# 《{world_name}》\n\n")
    conversation_text = _read_or_header(conversation_path, f"# 《{world_name}》对话记录\n\n")
    if _has_turn(novel_text, turn) or _has_turn(conversation_text, turn):
        raise ValueError(f"第 {turn} 回已经记录，拒绝重复写入")

    novel_block = (
        f"\n\n---\n\n{marker}\n## 第{turn}回 · {timestamp}\n\n"
        f"{gm_response}\n"
    )
    conversation_block = (
        f"\n\n---\n\n{marker}\n## 第{turn}回 · {timestamp}\n\n"
        "### 玩家原始输入\n\n"
        f"{player_input}\n\n"
        "### GM完整回答\n\n"
        f"{gm_response}\n\n"
        "### Python结算事件（审计记录）\n\n"
        "```json\n"
        f"{json.dumps(record, ensure_ascii=False, indent=2)}\n"
        "```\n"
    )
    _write_pair_atomically(novel_path, novel_text.rstrip() + novel_block, conversation_path, conversation_text.rstrip() + conversation_block)
    audit = build_execution_audit(
        turn=turn,
        player_input=player_input,
        action=action,
        gm_response=gm_response,
        result=result or {"event": record, "resolution": record.get("data", {}).get("resolution", {}) if isinstance(record.get("data"), dict) else {}},
        before_state=before_state,
        after_state=state.data,
        intent_source=intent_source,
    )
    audit_result = append_audit_record(save_dir, audit)
    return {
        "turn": turn,
        "event_id": record.get("event_id"),
        "novel_path": str(novel_path),
        "conversation_path": str(conversation_path),
        "audit_id": audit_result.get("audit_id"),
    }
