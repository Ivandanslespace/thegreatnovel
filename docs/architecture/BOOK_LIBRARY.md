# Book Library 架构

## 当前约定

默认书库为项目根目录的 `library/`，每本书由 `BookLayout` 解析为
`library/<book_id>/`。真实来源只进入 `source/`；数据库、迁移报告和机器状态进入
`_system/`；edition 产物进入 `editions/<edition_id>/`。

```text
library/<book_id>/
├─ book.yaml
├─ README.md
├─ source/                         # 只读来源副本
├─ _system/state.sqlite3
└─ editions/<edition_id>/
   ├─ analysis/                    # Atlas、初始化、指标和节奏
   ├─ writing/                     # boundary、candidate、contract、draft、validation
   ├─ operations/<operation_id>/   # manifest/status/events/input/output/artifacts/logs
   ├─ batches/
   ├─ canon/
   └─ exports/latest|archive/
```

旧 `workspace/<book_id>` 仍可被兼容服务读取；新运行入口应通过 `BookLayout` 或
CLI/Web 的 `--library-root` 解析路径，不再手工拼接书库目录。不会使用 symlink 替代真实
目录迁移。

## 边界

Book Library 只收敛存储位置，不改变 V2 宪法、指标公式、Atlas 证据语义、Canon 事件或
作者批准门。Portable Snapshot 的 JSON 是 canonical view；SVG 只能通过显式 atlas export
生成。`exports/latest` 可直接打开，不依赖服务端或 `file:// fetch`。
