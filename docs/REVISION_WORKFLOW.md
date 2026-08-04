# 版本化明确改写工作流

本工作流在 V1 的不可变 source、append-only event hash chain、Canon Projection、快照和 Codex 文件合同之上增加 edition-scoped 的旧章节改写能力。改写永远写入派生 edition，不更新 `book/`、base edition 的原始章节或原版导出。

## 生命周期

```text
base → edition create (DRAFT)
     → revision create (AUTHOR_INTENT)
     → impact scan + semantic audit
     → revision plan / units
     → REVISION_DRAFT import
     → ten existing validators + ten revision validators
     → VALIDATED
     → “批准改写版本”
     → chapter variants + revision events + snapshot (edition VALIDATED)
     → “启用改写版本”
     → edition ACTIVE
```

`批准改写版本` 和 `启用改写版本` 是两个独立的作者确认语。批准只把通过校验的变更提交到目标 edition，不改变默认续写版本；启用才会更新 `books.active_edition_id`。切回原版时启用 `base`，或归档当前派生 edition；base 永远存在且不可删除。

## 文件合同

每个 campaign 的审计文件位于：

```text
library/<book_id>/editions/<edition_id>/writing/revisions/<campaign_id>/
```

其中包含 `revision_spec.json`、`impact_packet.json`、`revision_plan.json`、Operation Workspace 的 `input/`、`output/` 和改写输出 schema。Codex 输出必须是 `task_type=REVISION_DRAFT` 的 JSON；导入后状态只能是 `REVISION_DRAFT`，不会自动成为正史。

## 推荐命令

```powershell
novel edition create --book-id my-book --edition-id rewrite-v1 --display-name "改写候选" --parent base
novel revision create --book-id my-book --edition-id rewrite-v1 --spec .\examples\revision_spec.example.yaml
novel revision impact --book-id my-book --campaign-id <campaign-id>
novel revision impact-complete --book-id my-book --campaign-id <campaign-id> --decisions <audit.json>
novel revision plan --book-id my-book --campaign-id <campaign-id>
novel revision draft-task --book-id my-book --campaign-id <campaign-id> --unit-id <unit-id>
novel revision import --book-id my-book --output <revision-output.json>
novel revision validate --book-id my-book --campaign-id <campaign-id>
novel revision preview --book-id my-book --campaign-id <campaign-id>
novel revision approve --book-id my-book --campaign-id <campaign-id> --confirm "批准改写版本"
novel edition export --book-id my-book --edition-id rewrite-v1
novel edition activate --book-id my-book --edition-id rewrite-v1 --confirm "启用改写版本"
```

Impact 中的 `MUST_REWRITE` 必须进入 unit 并解决；`MUST_REVIEW` 必须被处理或带理由显式豁免。批准前会再次检查 source manifest、原始章节 preimage、父版本冻结锚点和全部 validator。事务失败会回滚数据库事件、variants、projection、commit 和 snapshot，并清理本次生成的 snapshot 文件。

## 导出与回滚

既有 `novel export` 继续导出 base/当前 active 版本，保持 V1 行为和原版字节一致。`novel edition export` 在派生版本目录生成完整替换版、manifest、projection、audit、variant index、unified diff 和 unresolved items。导出按稳定 `chapter_id` 选择 active variant，未改章节仍引用原始 source，variant 不会被追加到末尾。

恢复原版只需明确启用 base：

```powershell
novel edition activate --book-id my-book --edition-id base --confirm "启用改写版本"
```

这不会删除派生 edition 或审计历史；如需停用版本，可执行 `novel edition archive`，系统同样保留历史事件和文件。
