# TheGreatNovel 首版实现合同

本文件只固定并行实现所需的边界；产品权威仍是根目录 `CONSTITUTION.md`。

## 权威顺序

```text
玩家输入
→ 候选行动 / 世界蓝图
→ 纯预览与合法性检查
→ 确定性结算
→ 事件和状态在同一事务中提交
→ 生成事实绑定的叙事请求
→ 叙事提交
→ 聊天显示 / 小说草稿更新
```

LLM 输出永远是候选或派生表达，不能直接修改状态。被拒绝的输入、预览和未提交文本不进入事件历史或小说。

## 共享 JSON 边界

- `CompiledWorld`、`GameState`、`Event`、`Observation` 在模块间都以 JSON object 传递。
- `GameState` 必须包含 `campaign`、`player`、`actors`、`world`、`opportunities`、`unlocks`、`metrics`；具体子字段由世界声明。
- Patch 只允许 `set`、`add`、`append_unique`、`remove`、`merge`，路径必须落在业务状态，禁止改写 campaign identity、turn、hash 或历史。
- 每个 committed Event 具有 seq、turn、event_id、event_type、actor_id、patches、facts、details、prev_hash、state_before_hash、state_after_hash、event_hash。
- Fact 至少具有 fact_id、text、visibility（public/player/hidden/actor:<id>）、kind、source；玩家投影不得泄露 hidden 或其他 actor-scoped facts。
- 一个正时间行动必须同时推进世界时钟和到期的 NPC / world process；零时间行动必须有有限使用次数或实际状态变化。
- 事件重放只使用 initial state、sealed blueprint 和 committed events，不调用 LLM。

## 引擎接口

纯引擎公开：`compile_blueprint`、`initial_state`、`legal_actions`、`preview_action`、`resolve_action`、`apply_event`、`project_player_view`、`validate_expansion`。它不读写磁盘或 SQLite。

## 存档与故事接口

事务存储公开：创建/打开 Campaign、读取当前状态、原子提交 resolution、幂等 command、pending narration、提交 narration、校验/重放、列出存档。Story 只消费已分配 event_id 的 committed events。每次 narration 提交后原子刷新 `novel_draft.md`；结束时输出 `novel.md`、`history.json` 和带 hash 的 export manifest。

## 世界内容门禁

首版至少提供两个结构不同的完整循环：物流/基础设施世界与证据/承诺世界。每个世界必须拥有可验证的控制缺口、可学习规则、有成本和失败路径的非对称杠杆、至少两段复利解锁、NPC 离屏行动、机会窗口、关系反转、阶层跃迁和更大世界触发。移除杠杆后，可用行动或可达成长轨迹必须改变。

世界蓝图可以使用安全的条件和 patch 语言，但不能执行 Python、加载插件或修改 validator。未知字段和未知操作一律拒绝。

