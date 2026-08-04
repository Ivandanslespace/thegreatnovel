# Batch Continuation 工作流

Batch 是多章调度层，不是“把 50/100 章塞进一个 prompt”。每章仍遵循
`$continue-novel` 的 Boundary Packet → 三候选 → Chapter Contract → 正文 → 十项
Validator；Batch 只保存尚未批准的 Provisional Projection。

## 创建与冻结

创建 Batch 前必须有当前 edition 的 ACTIVE、可验证 Story Atlas 和 Rolling Horizon。
Python 冻结：

- book/edition、base event seq 和 Canon projection hash；
- source manifest/effective content hash；
- Atlas ID/version/content hash 与 Horizon hash；
- registry/config/author-directives/metric bundle hash；
- 连续章节范围、chunk size 和 checkpoint interval。

默认 `chunk_size=5`、`checkpoint_interval=10`。Plan 必须连续覆盖目标章节、chunk_order
连续，并记录每个 chunk 的 input projection hash 和 prompt contract；不能生成巨型
全文 prompt。

```powershell
novel atlas validate --book-id <book_id> --edition-id <edition_id>
novel batch create --book-id <book_id> --edition-id <edition_id> --target-chapters 100
novel batch chunk-context --book-id <book_id> --batch-id <batch_id> --chunk-order 1
```

## Provisional 合同

`BatchProvisionalState` 只能包含临时 events/facts/threads、Atlas candidate changes、
未决问题和锚点 hash；`canon_committed` 固定为 false，禁止 Canon event/commit/status。
一个 chunk 完成时必须逐章给出 Boundary hash、Contract ID 和十个唯一 Validator report
ID，并且十项全部通过。前一 chunk 未完成或 input hash 漂移时不得继续。

```powershell
novel batch complete-chunk --book-id <book_id> --batch-id <batch_id> \
  --chunk-order 1 --provisional-state-file state.json \
  --validator-summary-file validators.json
```

每 10 章写入 checkpoint；checkpoint 重新锚定当前 Atlas/Horizon，并可产生 refresh
提示。若 source/projection/Atlas/Horizon/metric/config/directive hash 漂移，Batch 必须
停止并标记 stale，不能继续生成正文。

## 结束状态

只有所有 chunk 都有逐章 artifact、合同、十项校验和 provisional state 时，才可达到
`BATCH_VALIDATED`。它仍然不是 Canon 批准：`canon_committed=false`、
`edition_activated=false`，必须等待作者明确逐章/批次批准。
