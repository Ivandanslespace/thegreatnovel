"""Build narrator prompt from context."""

from __future__ import annotations

from .models import NarrationContext
from .voice import WritingVoiceProfile


def build_narrator_prompt(
    context: NarrationContext,
    voice_profile: WritingVoiceProfile | None = None,
    previous_text: str | None = None,
) -> str:
    """
    Build deterministic prompt for LLM narrator.
    
    Same context + voice profile always produces same prompt.
    
    Prompt structure (priority order):
    1. [ROLE]
    2. [NON-NEGOTIABLE FACT RULES] - highest priority
    3. [CURRENT VERIFIED FACTS]
    4. [WRITING VOICE] - can be overridden by facts
    5. [PREVIOUS NARRATION] - optional
    6. [OUTPUT REQUIREMENTS]
    
    The narrator is a PRESENTATION LAYER ONLY.
    Facts ALWAYS override voice requirements.
    """
    if voice_profile is None:
        raise ValueError("voice_profile is required - NarratorService must provide a voice profile")
    
    sections = []
    
    # Role
    sections.append("[ROLE]")
    sections.append("你是一位生存小说的旁白，负责将游戏事件转化为引人入胜的叙事。")
    sections.append("你不是游戏裁判，不能改变任何游戏事实。")
    sections.append("")
    
    # Non-negotiable rules
    sections.append("[NON-NEGOTIABLE RULES]")
    sections.append("你只能描述给定的事实。")
    sections.append("禁止创造新的：行动、物品、数量、地点、NPC、敌人、伤势、危险、奖励、时间变化、属性变化、成功/失败结果。")
    sections.append("禁止改变给定数值。")
    sections.append("禁止暗示尚未发生的未来事实。")
    sections.append("可以描写动作过程、环境氛围、角色的即时感官和动作。")
    sections.append("如果事实中没有某项信息，不要自行补充。")
    sections.append("")
    
    # Facts
    sections.append("[FACTS]")
    sections.append(f"action_type: {context.action_type}")
    sections.append(f"event_type: {context.event_type}")
    sections.append(f"time: {context.game_minute_before} → {context.game_minute_after}")
    sections.append(f"location: {context.location_before} → {context.location_after}")
    sections.append(f"stamina: {context.stamina_before} → {context.stamina_after}")
    
    # Inventory changes
    if context.inventory_before or context.inventory_after:
        sections.append("inventory_before:")
        for resource, qty in context.inventory_before.items():
            sections.append(f"  {resource}: {qty}")
        sections.append("inventory_after:")
        for resource, qty in context.inventory_after.items():
            sections.append(f"  {resource}: {qty}")
    
    # Carried loot changes
    if context.carried_before or context.carried_after:
        sections.append("carried_before:")
        for resource, qty in context.carried_before.items():
            sections.append(f"  {resource}: {qty}")
        sections.append("carried_after:")
        for resource, qty in context.carried_after.items():
            sections.append(f"  {resource}: {qty}")
    
    # Event payload (action-specific facts)
    if context.event_payload:
        sections.append("event_payload:")
        for key, value in context.event_payload.items():
            sections.append(f"  {key}: {value}")
    
    sections.append("")
    
    # Previous narration (if any)
    if previous_text:
        sections.append("[PREVIOUS NARRATION]")
        sections.append(previous_text)
        sections.append("")
    
    # Writing Voice (inserted after facts, before output requirements)
    sections.append(voice_profile.instructions)
    sections.append("")
    
    # Style examples (if any) - clearly isolated from FACTS
    if voice_profile.examples:
        sections.append("[STYLE EXAMPLES — NOT WORLD FACTS]")
        sections.append("以下内容只用于模仿写作风格。")
        sections.append("其中出现的人物、地点、物品、资源、数量、事件和世界设定，")
        sections.append("都不是当前游戏事实。")
        sections.append("")
        for example in voice_profile.examples:
            sections.append(example)
        sections.append("")
    
    # Output requirements
    sections.append("[OUTPUT REQUIREMENTS]")
    sections.append("只输出小说正文，不要包含任何元评论、解释或标签。")
    sections.append("使用中文，80-250字之间。")
    sections.append("风格：克制、具象、节奏清晰，可以包含少量系统信息。")
    sections.append("将系统事实自然融入叙事，不要让读者感觉在看数据表。")
    
    return "\n".join(sections)
