# Legacy Migration 操作合同

默认先执行 dry-run：

```powershell
novel library migrate-legacy `
  --book-id cable-survival-demo `
  --source-root C:\path\to\legacy\_source `
  --workspace-root C:\path\to\legacy\cable-survival-demo `
  --library-root C:\dev\小说续写系统\library `
  --dry-run
```

只有审计报告、来源 SHA、SQLite integrity/foreign key、路径改写和计数对账通过后，才
使用 `--apply`。迁移器复制到 staging，验证后 atomic switch；旧 source/workspace 默认不
删除，并在 `library/<book_id>/_system/legacy_locations.json` 记录。

迁移验收至少复核：

- source 文件 SHA 与原文一致；
- chapters/source spans/chapter features/observations/evidence 的数量不变；
- historical Metric Run 与最新去重章节覆盖分开报告；
- DB path columns 不再指向旧 Temp；
- Canon Commit 数量不因迁移增加；
- `novel web doctor` 和 Portable Snapshot 可用。

如需处理旧位置，先执行 `novel library cleanup-legacy --dry-run`。apply 必须提供报告给出的
精确 confirmation；操作只把旧位置移动到可恢复 archive，不执行默认永久删除。
