---
kind: configuration_system
name: 配置系统 — YAML 存档与 SQLite 事件账本双源持久化
category: configuration_system
scope:
    - '**'
source_files:
    - engine_runtime/state.py
    - engine_runtime/persistence.py
    - engine_runtime/events.py
    - templates/world_template.yaml
    - saves/废土列车/meta.yaml
    - saves/废土列车/world.yaml
    - saves/废土列车/player.yaml
---

TheGreatNovel 的配置系统以「YAML 存档文件 + SQLite 事件账本」的双层持久化为核心，通过 `engine_runtime/state.py` 的 `GameState` 统一加载、投影与保存。该设计将游戏世界状态（world/player/base/inventory/npcs/factions/relationships/event_queue/meta）拆分为多个 YAML 文件，同时用 SQLite 作为唯一真相源（event_log.md 仅用于人类可读审计），实现可重放、可快照、可增量恢复的事件溯源架构。

**核心机制**
- 配置文件结构：`YAML_FILES` 常量定义 9 个标准 YAML 文件名（world.yaml、player.yaml、base.yaml、inventory.yaml、npcs.yaml、factions.yaml、relationships.yaml、event_queue.yaml、meta.yaml），每个文件对应一个数据域，由 `_load_yaml` / `_write_yaml` 统一读写。
- 启动加载顺序：`load_game_state()` 先逐个读取 YAML 文件合并为内存 `data`，再从 SQLite 的 `latest_snapshot()` 覆盖；若无快照则回退到 `event_log.md` 解析历史事件重建状态。
- 运行时写入：`apply_and_append()` 每次应用事件后同步更新 SQLite 事务并追加 event_log.md 行；`commit_pending()` 批量提交待持久化记录。
- 快照保存：`save()` 方法将当前内存状态写回所有 YAML 文件，同时将完整快照存入 campaign.sqlite3。

**配置来源与分层**
- 模板层：`templates/world_template.yaml` 提供世界创建模板，包含 theme/difficulty/narrative_style/language 等高层设定，以及 generation_bundle 生成的可执行注册表（locations/enemy_definitions/build_catalog 等）。
- 存档层：`saves/<campaign>/` 下每个存档目录包含完整的 YAML 文件集合和 meta.yaml（含 current_turn/game_day/time_of_day/rng_seed/runtime_metrics 等运行时元数据）。
- 事件层：SQLite 的 campaign.sqlite3 是绝对权威，YAML 文件是快照副本；event_log.md 是人类可读的事件追加日志。

**无环境变量/外部配置**
代码库中未发现 `.env`、`os.environ`、`getenv`、`dotenv` 等环境变量加载模式，所有运行时配置均内嵌于 YAML 存档或 meta.yaml 中（如 difficulty、language、narrative_length、rng_seed、available_time_minutes 等）。配置变更通过工具链（tools/create_save.py、turn_controller.py）生成新存档而非修改全局环境。

**约束与约定**
- world.yaml 必须包含 `world` 根键，其他 YAML 文件使用 `{key: value}` 包装结构。
- meta.yaml 中的 `event_format_version` 标记事件格式版本，用于向后兼容。
- 所有数值字段在运行时被强制转换为 float/int，类型错误会被捕获并回退默认值。
- RNG 种子由 `rng_seed` 或 `world_name` 派生，确保确定性重放。