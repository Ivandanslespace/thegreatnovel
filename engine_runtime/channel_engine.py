"""Phase 3 channel engine - 极简版。"""
from __future__ import annotations
import random
import uuid
from typing import Any, Dict, List


def format_message(template: str, **kwargs) -> str:
    """Format message template with provided variables.
    
    Args:
        template: String template with {variable} placeholders
        **kwargs: Variables to substitute
    
    Returns:
        Formatted string with all placeholders replaced
    """
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        # Fallback if template has issues
        return template


def get_world_template(world_config: dict | None, action_type: str, outcome: str, category: str = 'default') -> str:
    """Get appropriate message template based on world configuration or use default.
    
    Supports different template structures:
    - world['public_survival']['messaging_templates']
    - world['world_blueprint']['messaging_templates']
    """
    if not world_config:
        return None  # Signal to use default
    
    blueprint = world_config.get('world_blueprint', {}) if isinstance(world_config.get('world_blueprint', {}), dict) else {}
    public_config = world_config.get('public_survival', {}) if isinstance(world_config.get('public_survival', {}), dict) else {}
    
    # Try blueprint templates first
    templates = blueprint.get('messaging_templates', {}) if isinstance(blueprint.get('messaging_templates', {}), dict) else {}
    
    # Fall back to public_survival templates
    if not templates:
        templates = public_config.get('messaging_templates', {}) if isinstance(public_config.get('messaging_templates', {}), dict) else {}
    
    if not templates:
        return None
    
    # Build template keys to try in priority order (most specific to least)
    # Format: "{action_type}_{outcome}_{category}" where outcome is in Chinese like "大成功"
    template_key1 = f"{action_type}_{outcome}_{category}"
    template_key2 = f"{action_type}_{outcome}"
    template_key3 = f"{action_type}_{category}"
    default_key = "default"
    
    # Return first matching template
    for key in [template_key1, template_key2, template_key3, default_key]:
        if key in templates:
            return templates[key]
    
    return None


def generate_channel_messages(
    peer_results: List[Dict[str, Any]],
    current_turn: int,
    existing_feed: List[Dict[str, Any]] | None = None,
    *,
    rng_seed: str = "",
    world_config: dict | None = None,  # NEW: Support world-specific templates
) -> List[Dict[str, Any]]:
    """Generate simple channel posts from peer activity.

    - Each peer posts at most once per turn.
    - 2-turn cooldown: skip if peer posted in the last 2 turns.
    - ~30% chance to post on notable outcomes.
    
    Uses world-specific message templates when available, falling back to defaults.
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
        # Also post on "普通成功" (minor success) but with lower frequency
        if outcome not in ("大成功", "成功", "失败", "严重失败"):
            continue
        # Only 30% chance for normal outcomes, higher for notable ones
        if outcome in ("大成功", "失败", "严重失败"):
            pass  # Always post for notable outcomes
        elif rng.random() >= 0.3:
            continue

        speakers.add(peer_id)
        action_type = str(result.get("action_type") or "action")
        peer_name = str(result.get("peer_name") or "unknown")
        
        # Generate content using world-specific template or default
        world_template = get_world_template(world_config, action_type, outcome)
        if world_template:
            # Use template-based messaging
            content = format_message(
                world_template,
                name=peer_name,
                action_type=action_type,
                outcome=outcome,
                turn=current_turn
            )
        else:
            # Default generic message
            content = f"{peer_name}在{action_type}中取得了进展"
        
        messages.append({
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "sender_id": peer_id,
            "sender_name": peer_name,
            "content": content,
            "turn": int(current_turn),
            "message_type": "action_post",
            "archived": False,
        })

    return messages
