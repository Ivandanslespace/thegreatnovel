# LLM 主持器—Python 硬协议

本协议是所有 LLM 主持游戏时的唯一结算流程。`AGENTS.md` 负责叙事和主持行为；
`engine_runtime/` 与 `tools/run_action.py` 负责数值、随机性、状态增量和存档写入。

## 不可越权的边界

LLM 只提交“玩家想做什么”。以下内容必须由 Python 计算，LLM 不得填写、修改、
猜测或在叙述中覆盖：

- 行动时间、体力/精神/饥饿消耗、资源消耗
- A、D、P、K、Severity、DeathFairness、随机 roll、种子和结果等级
- 命中、闪避、伤害、死亡风险、撤退概率、武器耐久、弹药消耗和状态效果
- 经验、等级、掉落、批量击杀数、Farmability、刷怪净价值
- 基地材料、空间、建造时间、维护损耗和所有状态增量
- `resolution`、`action_ledger`、`resource_changes`、`player_delta` 等事件结果

行动 JSON 只能使用以下意图字段。移动行动的时间、体力和撤离成本不能由 LLM 填写，
而是从 `world.locations` 的路线字段派生：

```json
{
  "action_id": "scout-001",
  "type": "TRAVEL",
  "target": "冰原边缘",
  "risk_preference": "标准",
  "tags": ["move"],
  "goal": "寻找燃料",
  "requirements": {},
  "parameters": {},
  "stop_conditions": {}
}
```

空间行动类型：

- `TRAVEL` / `ENTER_LOCATION`：从当前位置进入已注册地点；目标地点必须存在，且不能在活动遭遇中绕过 `EXTRACT` 或 `LEAVE_ENCOUNTER`。
- `RETURN_TO_BASE`：离开非基地地点并返回基地；活动遭遇中必须改用 `EXTRACT`。
- `EXTRACT`：执行现场撤离路线并返回基地；有活动遭遇时检查其撤离截止时间、开放窗口、撤离钥匙和撤离点条件，成功后关闭遭遇并写入遭遇历史；没有活动遭遇时仍可作为已离开遭遇区的现场返程。
- `LEAVE_ENCOUNTER`：放弃当前遭遇但留在原地点，关闭遭遇并保留后续重新探索的空间。
- `REST`、`BUILD`、`BASE_MANAGEMENT`：只能在 `meta.current_location ==` 基地地点时执行。
- `EXPLORATION`：只在当前地点结算，不再隐含移动；必须先用 `TRAVEL` 或 `ENTER_LOCATION` 到达目标地点。

移动和撤离采用确定性路线模式：只要地点已注册、路线成本可由 Python 派生、时间/体力/精神足够且没有遭遇阻挡，
路线就会成功；它们不会再调用普通行动的随机成功概率。路线上的危险、遭遇、撤离截止和撤离条件仍然是硬门槛，
不能由叙述或 LLM 改写。Python 返回的移动结果带有 `movement_success=true`、`probability=1.0` 和
`risk_mode=deterministic_route`，领域状态只有在该结果存在时才会修改。

需要组合多个短行动时提交一个原子计划：

```json
{
  "action_id": "plan-001",
  "type": "ACTION_PLAN",
  "plan_id": "plan-001",
  "accept_dilution": true,
  "priority_order": ["step-1", "step-2"],
  "steps": [
    {"action_id": "step-1", "type": "SOCIAL_INTERACTION", "target": "npc-rivet", "goal": "确认路线"},
    {"action_id": "step-2", "type": "RESEARCH", "target": "anchor-tower", "goal": "形成工程假设"}
  ]
}
```

计划步骤只能提交目标、方法和风险偏好；属性、成本、顺序可行性和稀释程度由 Python
根据世界注册表计算。Python 会先比较模拟当前位置与每一步注册的所需地点，自动插入必要的
`TRAVEL`、`EXTRACT`，再复制临时状态按顺序预览每一步；因此前一步
消耗的资源、获得的知识和生成的遭遇会影响后一步预览。`priority_order` 用于 20-49 的计划，
系统只执行最高优先级的可行步骤，其余步骤返回 `deferred_steps`。50-79 必须明确接受稀释：
普通计划效果乘 0.75，同一时段三个以上主要行动乘 0.55；稀释会作用于成功率、资源/关系效果、
研究信息完整度、建造质量和批量击杀效率。80以上才允许完整顺序完成。

行动槽不是“只要时间塞得下就能全做”的容器：每个时段默认只有 1 个主要行动和 2 个短行动；
编译器自动补齐的路线步骤属于系统物流，不额外占用玩家的主要/短行动槽，但会照实计入时间、体力和精神成本。
Python 还会计算专注负荷、注册表承诺轴冲突、结构化机会窗口、NPC 是否被重复占用、地点移动兼容度；
这些因子会共同降低 Combinability，低于阈值时要求排序或接受稀释。行动 JSON 中的 `tags`
只记录 LLM 对玩家意图的描述，不参与承诺轴、窗口容量或主要行动槽的硬判定；硬约束必须来自
`world.action_targets[].constraints`、地点定义、NPC 日程和世界规则。

机会约束分为两层：`availability.allowed_periods` 判断行动在当前真实时段是否合法；
`reservation.exclusive_group`、`window_id`、`capacity` 判断同一真实时段能预留几项。
计划预览和执行会按每一步实际开始时的 `time_of_day` 重新判断，不能把”白天/黄昏”当成当前时段之外的
预先许可，也不会把尚未到达的窗口立即执行。

## 选项编译硬门槛

展示给玩家的 A/B/C 必须经过 `compile_options()` 编译。编译器对每个候选行动调用
`preview_host_action()`，只有 `preview.legal == True` 的候选才能进入最终选项列表。
这意味着时段（`allowed_periods`）、地点、物品、等级、NPC可用性等所有前置校验
都在展示之前完成；玩家永远看不到当前状态下不合法的选项。

正确流程：

```text
主持器生成候选行动列表
  → compile_options() 逐项调用 preview_host_action()
  → preview.legal == False → 丢弃（玩家看不到）
  → preview.legal == True → 检查实际状态效果 → 去重 → 编译为行动契约
  → 持久化为 OPTIONS_PRESENTED 事件 → 展示给玩家
```

错误流程（禁止）：

```text
主持器凭叙事直觉写出 A/B/C → 玩家选择 → 结算时才发现时段不合法 → 拒绝
```

这不是”有意义的失败”，而是选项生成顺序错误。合法性审核必须发生在展示之前。

如果当前时段不允许某项行动（如清晨不能探索废铁站场），编译器会自动丢弃该候选。
主持器应当提供替代方案，例如：

- 在当前地点执行不受时段限制的短行动（观察、整理、交谈）
- 返回基地准备装备或休息
- 提交含 `WAIT` 步骤的 ACTION_PLAN，等待进入合法时段后再执行

`WAIT` 行动类型只推进时间，不消耗体力或精神，不触发随机事件：

```json
{
  “action_id”: “wait-for-day”,
  “type”: “WAIT”,
  “parameters”: {“wait_minutes”: 120},
  “goal”: “等待进入白天”
}
```

`wait_minutes` 范围 5-720 分钟。在 ACTION_PLAN 中，WAIT 步骤会推进模拟时钟，
后续步骤的 `allowed_periods` 检查使用推进后的 `time_of_day`。例如：

```json
{
  “action_id”: “plan-wait-then-explore”,
  “type”: “ACTION_PLAN”,
  “plan_id”: “plan-wait-then-explore”,
  “accept_dilution”: true,
  “steps”: [
    {“action_id”: “step-wait”, “type”: “WAIT”, “parameters”: {“wait_minutes”: 120}, “goal”: “等待天亮”},
    {“action_id”: “step-explore”, “type”: “EXPLORATION”, “target”: “scrap_yard”, “goal”: “探索废铁站场”}
  ]
}
```

如果等待后进入白天，整个计划合法；如果等待后仍不在允许时段，计划预览返回
`legal: False`，编译器丢弃该候选。

选项绑定当前 `state_turn`。任何玩家行动提交后，旧选项自动清除；
时段或状态变化后，`preview_player_choice()` 会重新校验存储的契约，
不再合法的选项会被拒绝执行。

`parameters` 和 `stop_conditions` 只能表达玩家意图或停止条件，不能藏入数值结算。
协议会递归扫描 JSON；出现引擎字段或未知顶层字段时，入口直接拒绝，不产生事件。

## 唯一状态机

```text
读取存档
  → 解析玩家输入为意图 JSON
  → 协议白名单校验
  → Python 预览（不写文件）
  → 玩家选择本身即为执行授权；内部预览通过后立即执行专用结算器
  → Python 执行专用结算器
  → SQLite事务写入标准事件与快照
  → 导出YAML、Markdown和回合小说视图
  → 执行后存档校验
  → 只根据 Python 返回值进行小说化叙述
```

命令行入口：

```powershell
# 预览，不写入
python tools/run_action.py saves/世界名 --action-json '{"action_id":"travel-001","type":"TRAVEL","target":"冰原边缘"}' --dry-run

# 玩家原始输入即执行授权，并自动记录本回合
python tools/run_action.py saves/世界名 --action-json '{"action_id":"travel-001","type":"TRAVEL","target":"冰原边缘"}' `
  --player-input '我去侦察冰原边缘。' `
  --gm-response-file response.md `
  --intent-source player_free_text
```

如果本轮选择的是已经展示的 A/B/C，使用保存的契约直接执行，不重新解释选项：

```powershell
python tools/run_action.py saves/世界名 --player-choice-option A `
  --player-input '我选A。' --gm-response-file response.md --intent-source player_choice
```

执行前会校验存档；执行后再次校验。后置校验失败时，入口恢复执行前快照并报错。
执行命令必须同时提供玩家原始输入和GM完整回答，否则拒绝推进。成功后自动追加：

- `novel_draft.md`：只含可直接复制的GM连续小说正文
- `conversation_log.md`：玩家原话、GM回答和对应Python事件审计
- `decision_audit.jsonl`：每回合一条可查询结构化审计记录，区分 `player`、`llm`、`python`、`joint`
- `decision_audit.md`：同一审计记录的人类可读版本

审计记录中的 `player_database_impact.state_diff` 展示状态字段的 before/after；
例如 `player.fatigue`、`inventory.resources.xxx`、`base.space_used`、
`meta.available_time_minutes`，因此可以直接追踪玩家回答最终如何影响数据库。
`--intent-source player_choice` 表示玩家选择了LLM展示的选项；`player_free_text` 表示玩家
直接描述行动；`llm_suggestion` 表示LLM整理出的候选方案；这些标签只用于审计，
不参与游戏结果计算。

命令失败时，LLM 必须告诉玩家行动没有结算，不得编造结果、补写 YAML 或手写事件。

开局回合或需要补录时使用：

```powershell
python tools/record_turn.py saves/世界名 `
  --player-input '新游戏' `
  --gm-response-file opening.md
```

同一回合只能记录一次；重复记录会被拒绝。

审计查询示例：

```powershell
python tools/audit_report.py saves/世界名
python tools/audit_report.py saves/世界名 --turn 18
python tools/audit_report.py saves/世界名 --status REJECTED
python tools/audit_report.py saves/世界名 --field player.fatigue
```

## 专用行动数据来源

- `EXPLORATION`、`RESEARCH`、`SOCIAL_INTERACTION`、`REST`：行动效果来自 `world.action_targets`，
  Python生成发现地点、知识、资源、关系和休息恢复事件。
- `TRAVEL`、`ENTER_LOCATION`、`RETURN_TO_BASE`、`EXTRACT`、`LEAVE_ENCOUNTER`：只接受已注册地点和当前遭遇状态；
  路线时间/体力/精神成本来自 `world.locations`，不能通过 `target` 或 `parameters` 覆盖。`EXTRACT` 还会执行
  地点 `extraction_rule` 与遭遇实例上的 `extraction_deadline_at_minutes`。
- 编译世界中的现场 `RESEARCH` 目标地点就是生成的研究地点；如果设计需要回基地分析，应另建一个基地分析行动，
  不能把现场研究目标错误地绑定到 `camp_core`。
- `REST`、`BUILD`、`BASE_MANAGEMENT`：基地位置是 Python 强制门槛，LLM 不能用 `requirements.location` 或标签伪造基地位置。
- `WAIT`：只推进时间（`parameters.wait_minutes`，5-720分钟），不消耗体力/精神，不触发随机事件，
  不受地点或时段限制。用于 ACTION_PLAN 中等待合法时段窗口。
- `ACTION_PLAN`：Python先编译并补齐路线，再按顺序在临时状态中预览；玩家提交后以同一稀释参数在 SQLite 事务中原子提交。
- `COMBAT`：怪物类型来自 `world.enemy_definitions`，具体目标必须来自
  `world.encounter_entities`；目标必须同时属于 `meta.current_encounter_id` 对应遭遇的
  `participants/target_ids`，且遭遇地点等于玩家当前地点。死亡或过期遭遇不可继续战斗。
  武器和弹药来自背包；稀释会重新计算命中、伤害、击倒、反击、状态效果和死亡风险。
- `BUILD`：模块必须存在于 `world.build_catalog` 或 `world.modules`。
- `BATCH_ACTION`：区域必须存在于 `world.areas` 或 `world.farm_areas`；敌群、密度、掉落、
  Farmability 参数来自区域注册表；Python按10分钟时间片更新击杀、弹药、耐久、区域人口、警戒和怪物适应，
  遇到停止条件立即截断。
- `TALENT_CHOICE`：升级后只能从 `player.pending_decision.options` 中选择一个 Python 生成的候选，
  选择前其他行动全部拒绝；放弃项不会再次出现。
- `ATTRIBUTE_ALLOCATION`：玩家可把 `player.free_points` 中的整数点数分配给 `strength`、
  `constitution`、`agility`、`spirit`（也接受中文属性名作为输入别名）。行动必须提交
  `parameters.allocations`，总点数不得超过当前余额；它不占用时间、体力或精神，且只能由
  Python 通过 `ATTRIBUTES_ALLOCATED` 事件更新属性和剩余点数。没有可分配点数、属性未知、
  点数为零/负数/小数或超过余额时，本轮拒绝且不写事件。
- 探索成功会生成带唯一实例 ID 的遭遇；战斗结束、玩家通过 `EXTRACT`/`LEAVE_ENCOUNTER` 离开或遭遇到期时，遭遇会进入历史并
  从 `active_encounters` 清理。NPC与势力的日程、效用分数和自主资源变化由时间推进器写入状态，
  不由LLM补写。
- 玩家死亡后写入 `campaign_status=ended`、`ending_id` 和死亡总结；普通行动全部拒绝，只允许
  `ENDING`、`RESTART`、`CHECKPOINT`、`LEGACY_CREATE` 终局处理动作。
- 其他行动：成本由行动类型、技能定义、世界目标配置和当前状态派生。

LLM 不得把完整目标、模块或区域对象塞进 `parameters` 以绕过注册表。

## 失败处理

以下任一情况必须停止本轮结算并返回可读错误：存档校验失败、行动字段越权、目标未注册、
技能不可用、地点/物品/知识/队友不满足、时间或状态不足、公式计算失败、执行后校验失败。
失败不是“普通失败结果”，除非 Python 已经返回了正式的失败事件；两者不可混淆。

## 保证范围

SQLite 的 `campaign.sqlite3` 是事件和投影的事实源；`event_log.md`、YAML 和小说文件是导出视图。
可以使用 `tools/replay_campaign.py` 重放事件，使用 `tools/verify_projection.py` 验证当前投影。
这套协议在 LLM 通过 `tools/run_action.py` 调用引擎、且不直接写存档时，可以把越权输入
拦截在入口并让状态只由 Python 事件更新。若把操作系统的任意文件写权限同时交给 LLM，
任何纯提示词都无法提供绝对保证；因此主持器必须把本文件、`AGENTS.md` 和命令入口作为
操作契约，禁止直接编辑 `saves/`。
