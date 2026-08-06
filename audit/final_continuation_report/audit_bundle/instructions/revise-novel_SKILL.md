# revise-novel

用于在 `Novel_Authoring_System_Constitution_V2.md` 约束下执行版本化改写。改写不是续写重试，也不得把 `drafts.revision` 当作改写版本号。

## 硬边界

1. 先运行 `novel edition list`，确认 base、父版本锚点、源文件 manifest SHA-256 和当前 ACTIVE edition。
2. 改写必须在派生 edition 中完成：`novel edition create --edition-id <id> ...`。base 永远保留，不删除、不覆盖、不把变体追加到 base 正文。
3. `RevisionSpec` 必须通过 `extra=forbid` 校验并持久化到 `workspace/<book>/editions/<edition>/revision_campaigns/<campaign>/`。
4. 先 deterministic source/FTS scan，再完成 Codex 语义影响审计；任何 `MUST_REVIEW` 只能 HANDLED 或提供理由的 `EXPLICITLY_WAIVED`，不能把“扫描完成”当作“影响已处理”。
5. 只接受 `task_type=REVISION_DRAFT` 的输出；导入前核对 task/campaign/unit/edition、章节 preimage SHA-256、schema 和文件哈希。
6. 依次执行 impact → plan → draft-task/import → validate → preview。批准改写必须逐字输入 `批准改写版本`；批准只提交目标 edition，不自动启用。
7. 只有作者明确输入 `启用改写版本` 才能调用 edition activate。激活前确认目标 edition 为 VALIDATED，且 base projection/source hash 未漂移。
8. 失败事务必须回滚事件、投影、variant、物化表和快照文件；discard 只将改写草稿标记为 REJECTED，不创建 variant。

## 推荐命令

```text
novel edition create --book-id <book> --edition-id <edition> --display-name <name>
novel revision create --book-id <book> --edition-id <edition> --spec revision_spec.yaml
novel revision impact --book-id <book> --campaign-id <campaign>
novel revision impact-complete --book-id <book> --campaign-id <campaign> --decisions decisions.json
novel revision plan --book-id <book> --campaign-id <campaign>
novel revision draft-task --book-id <book> --campaign-id <campaign> --unit-id <unit>
novel revision import --book-id <book> --output output.json
novel revision validate --book-id <book> --campaign-id <campaign>
novel revision preview --book-id <book> --campaign-id <campaign>
novel revision approve --book-id <book> --campaign-id <campaign> --confirm "批准改写版本"
novel edition activate --book-id <book> --edition-id <edition> --confirm "启用改写版本"
novel export --book-id <book> --edition-id <edition>
```

真实 `book/` 只允许做源文件校验、影响分析、投影重建和导出 dry-run；未经作者明确批准，不得产生任何 revision commit 或 chapter variant。
