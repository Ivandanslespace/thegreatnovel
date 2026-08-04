# Paragraph Evidence and Contributions

`novel segments rebuild` 以 effective edition 章节正文的空行分块，保存原文、字符偏移、类型和稳定 ID。variant 变化会使旧 content hash 的 segment 失效并创建新行；base 永不被覆盖。

证据链接分为：

- `EXACT_DELTA`：只允许 DETERMINISTIC/DERIVED，`exact_delta` 是公式可复算的精确变化；
- `SEMANTIC_SUPPORT`：语义支持/反对，只有方向、strength、confidence 和理由，不是总分贡献；
- `AUTHOR_EVIDENCE`：作者判断的正文依据；
- `STATE_EVIDENCE`：来自 event/source span 的状态依据。

段落 quote 必须逐字存在于指定 segment。一个段落可以分别支持多个 component，但每个 component 必须有独立 link。缺证据时保留 UNKNOWN/MISSING，不强行绑定段落。
