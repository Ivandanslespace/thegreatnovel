# 个人原创小说根因修复候选

此目录由 Novel Authoring System 的 Book Library 管理。
原始来源位于 `source/`，机器运行数据位于 `_system/`；请勿手工覆盖数据库或 Canon。

- book_id: `personal-original-root-cause-candidate`
- layout: `library-v1`
- active edition: `base`
- database: `_system/state.sqlite3`
- readiness: `NEEDS_INITIALIZATION`
- source files: 1
- latest chapter: `379`
- current Atlas: `unknown`
- current initialization: `unknown`
- latest export: `editions/base/exports/latest`

## 入口

- `book.yaml`: 书库注册元数据
- `source/`: 只读来源副本
- `editions/<edition_id>/`: edition-scoped analysis、writing、operations 和 exports
- `editions/<edition_id>/exports/latest/`: 当前 Portable Snapshot Bundle（如已生成）

## 常用命令

- `novel library paths --book-id personal-original-root-cause-candidate`
- `novel atlas export-snapshot --book-id personal-original-root-cause-candidate`
- `novel library cleanup --book-id personal-original-root-cause-candidate --dry-run`

## 下一步

先核对当前 edition、Atlas readiness 和指标覆盖，再由作者决定是否创建下一次 handoff。
