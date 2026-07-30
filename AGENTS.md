# TheGreatNovel：互动小说引擎执行宪章

本文件只规定主持器和代码的**执行边界**。数值规则、行动经济与存档格式请查对应源文件，
不要把完整说明复制到这里。

## 发布

- 完成且验证通过的代码改动可直接推送 `origin/main`。
- 推送前检查工作区范围、远端并发和相关验证；有冲突、未解释的失败或无关脏改动时停止。
- `saves/archives/` 是只读档案。除非用户明确要求，绝不修改、格式化或迁移其中的存档。

## 五条不变量

1. SQLite 事件账本与快照是唯一事实源；YAML、Markdown 和小说只是投影。
2. A/B/C 只能执行 `meta.pending_options` 中已经保存的合同。
3. 玩家提交行动即授权。不得追加确认回合。
4. 不合法、过期或没有实际状态效果的选项不能展示。
5. 玩家叙述中不得出现实现细节或主持器内部字段。

特别是：不得直接编辑存档、手写事件结果、用叙述补偿一次失败的结算，或让小说文本反向
改变规则。所有状态改动都经由标准事件进入 SQLite。

## 唯一回合入口

```powershell
# 选项 A/B/C 或自由行动的结算
python tools/turn_controller.py saves/<存档> --player-input "A"

# 自由行动：LLM 解析意图后附上行动 JSON
python tools/turn_controller.py saves/<存档> --player-input "..." --action-json '{...}'

# 开局或选项过期时生成选项
python tools/turn_controller.py saves/<存档> --generate-options-only

# 小说写完后记录
python tools/turn_controller.py saves/<存档> record --turn-token "..." --player-input "A" --response-file response.md
```

`tools/game_turn.py` 是历史实验入口，不是主持器入口，也不能作为群体推进的替代品。

回合顺序固定为：

```text
玩家输入 → Turn Controller 解析/执行 → SQLite 提交
→ 全民世界推进公开状态 → 编译下回合合法选项
→ 返回 NarrativePackage → 写小说 → record
```

### LLM 的权限

- A/B/C：原样传给控制器；不得猜测字母的含义。
- 自由输入：只提交意图，不能填写时间、概率、成本、难度、伤害、掉落、经验、资源变化或结果。
- 属性分配：玩家说“力量+2、精神+2”即可。LLM 内部提交 `ATTRIBUTE_ALLOCATION`；属性点分配和天赋选择都是零时间、独立的正式行动。
- 执行失败时，本轮没有结算；解释可行替代方案，不能继续编小说。

自由行动与多步计划的完整字段、白名单与禁填字段见
`engine_runtime/host_protocol.md` 和 `engine_runtime/host_contract.json`。

## 新世界：原创内容与清晰开局

玩家只选择：主题、类型合同、难度、叙述长度和语言。`tools/create_save.py` 读取
`templates/world_template.yaml`，由 LLM 一次性创作世界包；Python 只负责把它编译为注册表、
成本和可重放状态。

- 职业、地点、NPC、资源、灾难、敌人和主角天赋均由本次世界包原创；不存在主题关键词对应的职业/能力列表。
- `world.genre_contract` 在创建时必须固化为完整对象，不能保留 `"1"`、`"2"` 之类选择字符串。
- 天赋必须同时给出原创描述、可执行的 `mechanical_effect` 和独占循环。前者决定世界感；效果合同决定它真正改变哪些行动；独占循环必须说明输入、转化、竞争影响与反制，不能只是泛用探测或小幅效率加成。
- 天赋 `opening_card` 必须说明：优势、第一天如何用、普通玩家缺什么、硬限制。开局必须直接展示它，不能只报一个玄而又玄的名字。

### 全民求生开局（`mass_system_survival` / `mass_reward_survival`）

`public_survival` 是 LLM 原创的公开开局合同，必须包含：

- 系统名、区域名与一条开局公告；
- 4–6 条玩家立即能理解的规则；
- 3–5 条区域频道消息；
- 3–5 名可见竞争者，各自有策略和可见优势。

第一段叙述在第一个选择前必须让玩家知道：统一起点、淘汰/灾难条件、资源或撤离规则、
公开频道、排行榜，以及主角天赋的实际优势与边界。之后每个消耗时间的正式行动都会推进
同区玩家、存活统计、区域排名和对比结果；这些变化只能通过 `PUBLIC_SYSTEM_ADVANCED` 事件写入。

孤独生存合同不展示频道、排名或伪造的其他玩家。

## 选项、空间与死局防护

- `compile_options()` 过滤非法候选后，才可以展示 A/B/C；最多三个。
- 选项是具有真实后果的完整方案；同类重大方案要争夺时间、物资、风险、立场或机会窗口。
- 没有目标注册表和状态效果的领域行动不可执行，避免“只扣时间、什么也没发生”的幽灵行动。
- `TRAVEL`/`ENTER_LOCATION` 才能移动；`EXPLORATION` 不隐含移动；遭遇中优先给战斗、撤离或离开遭遇的出口。
- `REST`、`BUILD`、`BASE_MANAGEMENT` 只能在基地；当正常候选都失效时必须提供合法等待或撤离出口。
- 玩家死亡前必须有可理解的预兆和可避免路径；死亡不是叙事补丁。

空间、计划编译和行动经济的细节见 `engine/action_economy.md`；战斗、探索、成长、基地和
社交规则分别见 `engine/` 下同名文档。

## 叙述与记录

- 只根据控制器返回的 `resolution`、可见事件和状态写作。
- 状态变化时可展示系统面板；公共模式自然穿插频道、公告与排名，不能把其他玩家当背景板。
- 每次解决一个谜团，可产生一到两个新谜团；不要用连续环境说明拖延第一项可行动决策。
- `novel_draft.md` 只放连续小说；`conversation_log.md` 和 `decision_audit.*` 由记录流程维护。
- 记录前不得把 `Python`、`SQLite`、预览、合同编号、`action_id`、确认执行等词暴露给玩家。

## 真相与验证

优先级：当前世界硬规则 → 类型合同 → 编译后的世界注册表 → SQLite 账本/快照 → YAML 投影
→ 结构化知识 → 摘要 → 小说文本。

对涉及存档与规则的改动，至少运行：

```powershell
python -m unittest discover -s tests -p "test_*.py"
python tools/replay_campaign.py <临时存档>
python tools/verify_projection.py <临时存档>
```

测试应使用临时新存档；不要为验证而触碰归档档案。
