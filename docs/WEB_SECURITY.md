# Web Security Boundary

- 默认监听 `127.0.0.1`；非本机绑定需要显式 `--allow-remote`。
- POST 使用启动时随机 CSRF token，可通过 `X-CSRF-Token` 传递。
- URL 只接受受限 book/edition/chapter/handoff ID，不接受任意磁盘路径。
- 任务目录由数据库中的 workspace root 解析；Web 不执行 shell，不启动 subprocess，不接受命令、API Key、Provider 或 Model 字段。
- Web 不批准 Canon、Revision Campaign 或 Edition，也不写入 `book/`。
- handoff claim 使用 SQLite 事务和 claim token；结果必须声明 `canon_committed=false`、`edition_activated=false`。
- 心跳仅作为最近活动时间；超时提示可能停止/等待，不自动 FAILED。
- Migration 7 记录 stale reason、result validation、Planning Aggregate 与 `WAITING_FOR_USER`，任何旧 artifact 都不能绕过结果合同成为当前有效草稿。
