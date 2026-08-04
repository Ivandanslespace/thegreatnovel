"""novelwriter —— 小说续写系统代码包。

公式负责发现问题 → 规划器提出方案 → LLM 创作 → 作者裁决
（CONSTITUTION.md 1.2）。

模块分工：
- loader：编码探测与按章切片（只读 inspirations/）
- state：唯一磁盘 I/O，JSON 原子读写
- metrics：六指标纯函数与权重常量表
- scheduler：阈值分档 + 冷却组 + 10 章预算 + 硬触发（只提建议）
- contract：章节合同 JSON + 提示词 Markdown
- llm：ManualAdapter（默认）/ ApiAdapter（可选）
- cli：init / analyze / plan / record 入口
"""

__version__ = "0.1.0"
