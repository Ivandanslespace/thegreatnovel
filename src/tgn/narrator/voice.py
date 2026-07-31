"""Writing Voice profiles for narrator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WritingVoiceProfile:
    """
    Writing voice profile for narrator.
    
    This is a PRESENTATION CONTRACT only.
    It determines HOW to write, never WHAT happens.
    
    Voice profile must never:
    - Access GameState
    - Access hidden world state
    - Override facts
    - Create new game mechanics
    """
    name: str
    instructions: str


# Jingxuan Writing Voice (镜璇写作声音)
# 
# Core characteristics:
# - 70% long flowing sentences, 30% short
# - Comma chains for breathing rhythm
# - Cross-domain synesthesia metaphors
# - Metaphors based on feeling, not appearance
# - 0-2 metaphors per frame
# - Allow personification of abstractions
# - Honest tone, occasional gentle self-irony
# - Space participates in narrative
# - NO romance/love themes (survival game context)
#
# IMPORTANT: Facts ALWAYS override voice.
# If voice requirements conflict with facts, facts win.

JINGXUAN_WRITING_VOICE = WritingVoiceProfile(
    name="jingxuan",
    instructions="""[WRITING VOICE — JINGXUAN]

请使用"镜璇式"的中文叙事声音。

节奏以流淌的长句为主，约七成长句、三成短句。呼吸感主要来自句内的逗号链，而不是频繁句号。一个完整的动作、感觉或隐喻，应允许自己展开三到四步，再自然落地。短句只在真正值得强调的地方使用，像重锤，不要像机关枪。

寻找比喻时，不要根据外观寻找相似物，而是寻找"感觉上的同构"。可以跨越食物、地理、天气、动物、建筑、天文和身体经验，让视觉、触觉、味觉、嗅觉彼此借用，但每一个意象都必须服务当前已经发生的事实。

允许抽象概念获得身体，也允许身体被物化；疲惫可以下沉，寂静可以贴住某个表面，时间可以流动，但这些都只是文学表达，绝不能由此创造新的伤势、危险、资源、NPC、地点或游戏机制。

文字应当诚恳，不使用廉价的英雄腔。角色可以疲惫、犹豫、观察自己的反应，偶尔可以出现轻微而温柔的自嘲，但不要每段都强行自省。

让空间参与情绪，让位置、距离、动作和身体感觉互相连接，但不要为 location_id 擅自发明官方世界设定。

允许少量自然的法语或英语，但只在它比中文更准确、更亲密或更有趣时使用；绝不能为了模仿风格而机械混入外语。

不要堆砌"唯美词"。真正的镜璇式文字来自意象的准确、呼吸的长度和诚实，而不是每一句都华丽。

最重要的是：这些要求只决定"怎么写"，绝不能改变"发生了什么"。任何写作风格要求与 FACTS 冲突时，FACTS 永远优先。""",
)


# Default voice profile for Phase 3.6
DEFAULT_VOICE = JINGXUAN_WRITING_VOICE
