"""Cablecar Survival voice pack - fast-paced progression-focused narration."""

from __future__ import annotations

from ..voice import WritingVoiceProfile


# Cablecar Survival Voice (缆车求生网文风格)
#
# Core characteristics:
# - Short paragraphs (1-3 sentences)
# - Fast pacing and high information density
# - Explicit analytical reasoning
# - System information integrated into narrative
# - Low metaphor density
# - Risk/reward focused
# - NO copying from reference works (characters, locations, plot)
#
# IMPORTANT: Facts ALWAYS override voice.
# If voice requirements conflict with facts, facts win.

CABLECAR_SURVIVAL_VOICE = WritingVoiceProfile(
    name="cablecar_survival",
    instructions="""[WRITING VOICE — CABLECAR SURVIVAL]

使用快速、清晰、高信息密度的中文求生网文叙事。

1. 以短段落为主。

通常 1–3 句即可换段，让视觉节奏快速推进。

2. 句子以短句和中等长度句为主。

不要大量使用复杂长句或持续性的文学修辞。

3. 优先顺序：

发生了什么
→ 主角观察到什么
→ 主角如何分析
→ 风险/收益是什么
→ 为什么选择当前行动
→ 行动结果

4. 主角推理允许直接显性写出。

常用逻辑结构：

观察
→ 提取信息
→ 提出可能性
→ 排除不合理选项
→ 判断风险
→ 得出结论

不要为了"文学性"隐藏有价值的推理。

5. 系统信息是正文节奏的一部分。

等级、属性、资源、物品、奖励、风险、时间等已经确认的游戏事实，可以直接出现。

但不得自行制造 Engine 没有提供的数值。

6. 数值的作用是帮助读者理解：

强弱
收益
成本
风险
成长

而不是纯装饰。

7. 动作、系统反馈、判断应快速交替。

避免连续数百字只描写环境而没有新信息或新决定。

8. 比喻密度低。

比喻应简单、直观、服务理解。

不要使用持续复杂的诗性通感。

9. 环境描写简洁。

主要服务于：

危险判断
位置判断
搜索判断
战斗判断
资源判断

10. 主角整体表现：

理性
谨慎
信息敏感
善于计算风险收益

但不得凭 Voice Pack 给角色增加 Engine/Context 未提供的人格事实。

11. 悬念主要来自：

未知规则
未知危险
下一处资源
奖励
成长
风险判断
信息差

12. 保持持续推进。

如果一句话不能：

推进动作
提供信息
解释判断
增加有效氛围

则倾向删掉。

13. 禁止复制参考作品中的：

人物名字
具体地点
剧情
世界设定
专有系统
原句

Voice Pack 学习的是叙事机制，不是内容。

最重要的是：这些要求只决定"怎么写"，绝不能改变"发生了什么"。任何写作风格要求与 FACTS 冲突时，FACTS 永远优先。""",
)
