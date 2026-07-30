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

行动 JSON 只能使用以下意图字段：

```json
{
  "action_id": "scout-001",
  "type": "EXPLORATION",
  "target": "冰原边缘",
  "skill_id": "optional-skill-id",
  "risk_preference": "谨慎",
  "tags": ["search"],
  "goal": "寻找燃料",
  "requirements": {},
  "parameters": {},
  "stop_conditions": {}
}
```

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
根据世界注册表计算。Python 会复制临时状态按顺序预览每一步，再恢复正式状态；因此前一步
消耗的资源、获得的知识和生成的遭遇会影响后一步预览。`priority_order` 用于 20-49 的计划，
系统只执行最高优先级的可行步骤，其余步骤返回 `deferred_steps`。50-79 必须明确接受稀释：
普通计划效果乘 0.75，同一时段三个以上主要行动乘 0.55；稀释会作用于成功率、资源/关系效果、
研究信息完整度、建造质量和批量击杀效率。80以上才允许完整顺序完成。

`parameters` 和 `stop_conditions` 只能表达玩家意图或停止条件，不能藏入数值结算。
协议会递归扫描 JSON；出现引擎字段或未知顶层字段时，入口直接拒绝，不产生事件。

## 唯一状态机

```text
读取存档
  → 解析玩家输入为意图 JSON
  → 协议白名单校验
  → Python 预览（不写文件）
  → 若属于重大决策，展示预览并等待玩家确认
  → Python 执行专用结算器
  → SQLite事务写入标准事件与快照
  → 导出YAML、Markdown和回合小说视图
  → 执行后存档校验
  → 只根据 Python 返回值进行小说化叙述
```

命令行入口：

```powershell
# 预览，不写入
python tools/run_action.py saves/世界名 --action-json '{"action_id":"scout-001","type":"EXPLORATION","target":"冰原边缘","risk_preference":"谨慎"}' --dry-run

# 玩家确认后执行，并自动记录本回合
python tools/run_action.py saves/世界名 --action-json '{"action_id":"scout-001","type":"EXPLORATION","target":"冰原边缘","risk_preference":"谨慎"}' `
  --player-input '我去侦察冰原边缘。' `
  --gm-response-file response.md `
  --intent-source player_free_text
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
直接描述行动；`llm_suggestion_confirmed` 表示LLM提出方案后玩家确认；这些标签只用于审计，
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
- `ACTION_PLAN`：Python按顺序在临时状态中预览；确认后以同一稀释参数在 SQLite 事务中原子提交。
- `COMBAT`：目标必须存在于 `world.targets`、`world.combat_targets` 或 `npcs`，且目标不能已死亡；
  带地点的敌人还必须处于当前地点或有效遭遇实例中。武器和弹药来自背包。
- `BUILD`：模块必须存在于 `world.build_catalog` 或 `world.modules`。
- `BATCH_ACTION`：区域必须存在于 `world.areas` 或 `world.farm_areas`；敌群、密度、掉落、
  Farmability 参数来自区域注册表；Python按10分钟时间片更新击杀、弹药、耐久、区域人口、警戒和怪物适应，
  遇到停止条件立即截断。
- `TALENT_CHOICE`：升级后只能从 `player.pending_decision.options` 中选择一个 Python 生成的候选，
  选择前其他行动全部拒绝；放弃项不会再次出现。
- NPC与势力的日程、效用分数和自主资源变化由时间推进器写入状态，不由LLM补写。
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
