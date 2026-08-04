# Book Library

这是 Novel Authoring System 的默认本地书库根目录：`<repository>/library`。

真实书籍目录默认放在 `library/<book_id>/`，由 `BookLayout` 统一解析：

- `book.yaml` 与 `README.md`：书籍注册元数据和生成说明；
- `source/`：导入后的来源副本，按合同保持只读；
- `_system/`：数据库、迁移报告和旧位置登记；
- `editions/<edition_id>/`：分析、写作、操作工作区、批次、Canon 与导出。

真实书库数据默认被 `.gitignore` 忽略，不会随代码提交。可通过 CLI 的
`--library-root` 或 Web 启动参数显式指定其他书库根目录。旧布局迁移不会默认删除旧
`source_root` 或 `workspace_root`，位置会记录在 `_system/legacy_locations.json`。
