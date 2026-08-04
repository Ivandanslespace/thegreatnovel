---
name: continue-novel-batch
description: 按 Batch Continuation 合同对已有小说执行 50/100 章等长任务的滚动续写；用户要求批量续写、多章连续生成、Batch Provisional Projection、chunk/checkpoint 或批量复核时使用。必须逐章沿用 continue-novel 的 Boundary、Chapter Contract 和十项校验，不得用一个巨型 prompt 写完整批次。
---

# Continue Novel Batch

Batch 是受 Atlas 和 Canon 锚点约束的调度与临时状态层。每章仍由作者可审查的 continuation 流程生成；Batch Provisional Projection 只承载尚未批准的临时状态，不能成为 Canon。

## 硬边界

1. 先读取 `AGENTS.md`、V2 宪法、当前 edition、source manifest、Canon projection、Atlas manifest、WorldModelReadiness、Rolling Horizon、作者指令和任务 `context_manifest.json`。
2. Source/projection/edition/Atlas/horizon/metric/config/directive 任一 hash 漂移，立即将 Batch 标记 `STALE` 并停止；不得继续写正文。
3. `book/`、正式 Canon events、真实 projection、`next_chapter` 指令和已批准 edition 不得被 Batch 直接修改。
4. 默认 `chunk_size=5`、`checkpoint_interval=10`。每次只处理当前 chunk；前一章/前一 chunk 的 provisional state 必须成为下一章输入。
5. 任何章节都必须通过 Boundary → 三候选 → Chapter Contract → 正文 → 十项 Validator。chunk 全部完成不等于验证通过。

## 创建 Batch

由 Python 生成不含正文的分块计划：

```powershell
novel source verify --book-id <book_id>
novel atlas validate --book-id <book_id> --edition-id <edition_id>
novel batch create --book-id <book_id> --edition-id <edition_id> --target-chapters 100
```

Batch manifest/plan 必须记录目标范围、base event/projection/source/effective-content hash、Atlas id/version/hash、horizon hash、metrics/config/directives hash，以及每个 chunk 的连续章节范围。不得产生一个覆盖 50/100 章正文的 prompt。

## 逐章滚动

每章读取：正式 Canon、当前 Batch Provisional Projection、Story Atlas、NEAR Horizon、相关 Metric 和作者要求；然后运行 `$continue-novel` 的完整单章合同。正文、draft、validator、候选和 contract 都写入 Batch task artifact，结果只更新 provisional state 与 `atlas_candidate_changes`。

每个 chunk 完成时必须写入 input/output provisional hash、validator summary、失败原因和 Atlas refresh flag。前一 chunk 未 `COMPLETED` 时禁止领取下一个 chunk；失败停止，不得自动跳过。

## Checkpoint

每 5 章检查节奏、Promise、重复、资源/能力、新人物/势力作用并调整 NEAR；每 10 章执行 Checkpoint：Snapshot/Rebuild 只读验证、节奏与 Review Queue 报告、Atlas Refresh handoff、Horizon Shift。Atlas 新版本必须是 immutable child，失效路线可退休，Active Spine 可切换但不改 Canon。

FAR Horizon 必须至少覆盖：

```text
max(当前已写章节数 × 2, Batch 目标章节数 × 2)
```

FAR 不得生成逐章大纲或固定结局。

## 结束状态

最终只允许停在 `BATCH_VALIDATED`：所有章节 artifact、合同和十项校验都可追溯，provisional projection 完整，Canon event 数和 source hash 与开始时一致。结果必须明确 `canon_committed=false`、`edition_activated=false`，并等待作者逐章/批次批准。不能把 Atlas accepted 或 Batch validated 当作正史批准。
