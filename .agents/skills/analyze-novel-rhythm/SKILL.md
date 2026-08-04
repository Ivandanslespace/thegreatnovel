---
name: analyze-novel-rhythm
description: 运行本项目 edition-aware 的章节特征、长跨度节奏、开头结尾相似度、功能/情绪连续度和伏笔动作诊断；当用户要求分析小说节奏、检查重复模式、评估伏笔推进或为续写建立节奏证据时使用。不得伪造语义特征、修改 book/正文或把诊断压成单一文学总分。
---

# Edition-aware 小说节奏诊断

只在 `C:\dev\小说续写系统` 根目录工作，并先读取 `AGENTS.md` 与
`Novel_Authoring_System_Constitution_V2.md`。`book/` 永久只读；任务、语义输出、快照和报告写入对应 `workspace/<book_id>/` 或派生 edition 工作区。

## 固定顺序

1. 用 `novel status --book-id <id> --edition-id <edition>` 和
   `novel source verify --book-id <id>` 核对状态、源 SHA-256 和 edition。
2. 先重建或读取有效特征：
   `novel features rebuild --book-id <id> --edition-id <edition>`；需要 Codex 判断时使用
   `novel features prepare`，只按任务 `input.md` 与 `schema.json` 生成 `output.json`，再运行
   `novel features import`。
3. 运行 `novel rhythm diagnose` 与 `novel hooks diagnose`，把结果放进 Boundary Packet；
   续写候选必须在这些证据之后生成。
4. 用 `novel rhythm show`、`novel hooks show` 或 `novel features show` 汇报可审计快照，保留
   `edition_id`、content hash、analyzer version、config hash 和证据短句。

## 证据与判定边界

- 确定性特征包括标题规范化、标题 exact/2-gram/3-gram 相似、前后三个非空段落（最多
  300 字符）、raw/prose-only 指纹。系统面板、属性表、公告和标题不得主导 prose-only 比较。
- 语义特征必须使用现有 `NarrativeFunction`、`LOW/MEDIUM/HIGH/EXTREME/UNKNOWN`、
  opening/ending mode，并为每个非 UNKNOWN 判断提供正文短证据；证据不在该 edition 当前正文
  时拒绝导入。证据不足应为 `UNKNOWN`/`INSUFFICIENT_EVIDENCE`，不要填默认分数。
- 诊断分别报告 `same_function_streak`、HIGH/EXTREME 情绪连续、标题重复、开头相似、结尾
  相似和 ending mode streak；相邻一次相似只能是 WARNING，不能单独阻止提交。
- 伏笔输出 `HOLD`、`ADVANCE`、`RESOLVE`、`OVERDUE`，同时列出 Age、Dormancy、Readiness、
  dependency、deferred-until 和证据。作者延后或未满足依赖优先保持 HOLD；严重 OVERDUE 只限制
 继续新增同等级悬念，不强制揭晓终极真相。

## 与既有评分的关系

节奏诊断是证据层，不是第五个或第六个总分。章节功能/标题/首尾信号补充既有
`Repetition Fatigue`，情绪连续补充 `Pressure Curve`，Age/Dormancy/Readiness 补充
`Narrative Debt` 与 `Thread Priority`。第一版不改 Candidate Score 权重，也不对同一重复问题重复扣分。

Boundary、plan-next 和 Chapter Contract 可以把强诊断变成可审查约束（改变功能、避免重复结尾、
推进指定 promise），但不能替作者自动选择下一章。批准或改写提交后重建当前 edition 的特征与快照；
content hash 变化必须让旧特征失效并保留审计历史。

## 失败处理

源校验、edition 锚点、语义 task/chapter/hash、证据短句或配置合同失败时停止；不要直接改 SQLite、
不要把 UNKNOWN 当 HIGH、不要把诊断写进 `book/`，也不要因为节奏 WARNING 绕过十项校验或作者批准。
