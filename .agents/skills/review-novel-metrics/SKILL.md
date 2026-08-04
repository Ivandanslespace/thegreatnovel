---
name: review-novel-metrics
description: 审核本项目 provenance-aware 指标运行、缺失 component、作者输入和段落证据；当用户要求查看指标、补齐缺失、导入语义观察、解释贡献或确认规划是否漂移时使用。不得修改 book、正史事件或自动批准草稿。
---

# Review Novel Metrics

使用 Python 指标服务和本地 SQLite 审核一个冻结的 Metric Run。指标只诊断，正文和状态才是证据，作者负责判断。

## 工作流

1. 读取 `metric_runs`、`metric_run_results`、`metric_observations` 和 `metric_evidence_links`；确认 `book_id`、`edition_id`、projection hash、effective content hash、registry hash 和 config hash 一致。
2. 对每个结果分别报告 `status`、`score`（缺失时必须是 `null`）、completeness、confidence、missing components 和证据；不得把 UNKNOWN 转成 0/50，也不得用一个总分掩盖缺失。
3. 对段落证据检查 `segment_id` 属于当前 effective edition，quote 必须原样出现在段落；`SEMANTIC_SUPPORT` 只能表达方向、强度和理由，不能填写 `exact_delta`。
4. 作者输入只能通过 `AuthorMetricInputService` append-only 保存。`AUTHOR_OVERRIDE` 必须有理由；确定性 component 不可被覆盖。乐观 hash 不匹配必须报告 409 并要求刷新。
5. 输入变更后确认旧 run 被 INVALIDATED，candidate plan/contract 变为 STALE；不得生成 Canon Event、批准 draft 或激活 edition。

## 语义观察导入

使用 `MetricSemanticObservationsOutput` 合同；逐 component 检查 confidence、unknown_reason、registry/content hash 和 evidence links。引用正文外事实时拒绝导入，无法证明时使用 MISSING/UNKNOWN。

## 输出

给作者一个可复核表格：指标 → component 状态 → 来源优先级 → 段落/状态证据 → 缺失原因 → 建议下一步。不要输出“模型认为已经解决”之类不可审计结论。
