"""Phase 3 channel engine - 极简版。"""
from __future__ import annotations
import random
import uuid
from typing import Any, Dict, List


def generate_channel_messages(
    peer_results: List[Dict[str, Any]],
    current_turn: int,
    existing_feed: List[Dict[str, Any]] | None = None,
    *,
    rng_seed: str = "",
) -> List[Dict[str, Any]]:
    """Generate simple channel posts from peer activity.

    - Each peer posts at most once per turn.
    - 2-turn cooldown: skip if peer posted in the last 2 turns.
    - ~30% chance to post on notable outcomes.
    """
    rng = random.Random(f"{rng_seed}|channel|{current_turn}")
    messages: List[Dict[str, Any]] = []
    speakers: set[str] = set()
    feed = existing_feed or []

    for result in peer_results or []:
        peer_id = result.get("peer_id")
        if not peer_id or peer_id in speakers:
            continue

        recent = any(
            m.get("sender_id") == peer_id and int(m.get("turn", 0)) >= current_turn - 1
            for m in feed
        )
        if recent:
            continue

        outcome = str(result.get("outcome", ""))
        if outcome not in ("大成功", "失败", "严重失败") or rng.random() >= 0.3:
            continue

        speakers.add(peer_id)
        action_type = str(result.get("action_type") or "action")
        peer_name = str(result.get("peer_name") or "unknown")
        messages.append({
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "sender_id": peer_id,
            "sender_name": peer_name,
            "content": f"{peer_name}在{action_type}中取得了进展",
            "turn": int(current_turn),
            "message_type": "action_post",
            "archived": False,
        })

    return messages
