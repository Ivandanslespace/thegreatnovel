# edition-aware 长跨度节奏诊断

## 数据边界

`chapter_features` 是派生审计表，逻辑唯一键为
`book_id + edition_id + chapter_id + effective_content_sha256 + analyzer_version + config_hash`。
它保留 raw/prose-only 首尾窗口、标题规范化与指纹、功能/情绪语义字段、来源类型、证据、配置哈希和
失效时间。Chapter Variant 或批准续章改变 effective content hash 时，旧行改为
`INVALIDATED`，新行独立保存；base 与 derived edition 不共享物理特征行。

确定性提取只使用本地文本：标题去除 Markdown heading、`第 X 章` 装饰并做 NFKC 规范化；首尾分别
取前三个非空段落、最多 300 字符；prose-only 排除系统面板、公告和属性表。标题与首尾使用可解释的
字符 2/3-gram Dice，相邻一次相似只能产生 WARNING。

语义特征必须通过 `ChapterSemanticFeaturesOutput` 文件合同导入。`evidence_quotes` 必须存在于目标
edition 当前正文，`confidence` 在 0—1；无法判断使用 UNKNOWN，并可保存
`INSUFFICIENT_EVIDENCE`，不能填默认分数。

## 诊断输出

`rhythm_diagnostic_snapshots` 保存以下并列证据，而不是 `Rhythm Score`：

- `same_function_streak`：realized function 优先，否则 planned function；
- `high_emotion_streak`：仅 HIGH/EXTREME 连续，UNKNOWN 会打断；
- `title_repetition`、`opening_similarity`、`ending_similarity` 和 `ending_mode_streak`；
- hooks 的 `HOLD`、`ADVANCE`、`RESOLVE`、`OVERDUE` 队列，以及 Age、Dormancy、Readiness、依赖和证据。

信号接入方式固定为：功能/标题/首尾 → 既有 Repetition Fatigue；高压连续 → Pressure Curve；
Promise Age/Dormancy/Readiness → Narrative Debt 与 Thread Priority。Candidate Score 权重不变，
同一重复问题不重复扣分。强诊断可以进入 Boundary Packet、候选任务和 Chapter Contract 作为可审查
约束，但不能绕过十项校验或作者批准。

## CLI 顺序

```powershell
novel features rebuild --book-id <book> --edition-id <edition>
novel features prepare --book-id <book> --edition-id <edition>
novel features import --book-id <book> --task-id <task>
novel rhythm diagnose --book-id <book> --edition-id <edition>
novel rhythm show --book-id <book> --edition-id <edition>
novel hooks diagnose --book-id <book> --edition-id <edition>
```

续写或改写必须先完成 source verify、Boundary、features、rhythm/hooks，再生成候选。批准或改写提交
后重建当前 edition 的 features 与 snapshot；所有真实 `book/` 操作仍限于只读 dry-run 和 SHA-256 复核。
