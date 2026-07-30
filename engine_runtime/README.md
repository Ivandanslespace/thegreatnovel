# TheGreatNovel Python 引擎层

这是规则的可执行层。Markdown 规则描述意图，`engine_runtime/` 负责计算并输出可审计结果。

LLM 主持器必须遵守 [host_protocol.md](host_protocol.md)。`tools/run_action.py` 是唯一的
主机行动入口；不要让 LLM 直接调用 `execute_action`、`execute_combat` 等内部方法或直接写存档。
`campaign.sqlite3` 是事件源，YAML、Markdown 和小说文件是可读投影。

## 运行一次行动

```powershell
python tools/run_action.py <存档目录> --action-json '{"action_id":"scout","type":"EXPLORATION","target":"区域名","risk_preference":"谨慎"}' --player-input '我去侦察。' --gm-response-file response.md
```

加 `--dry-run` 只预览，不写入 YAML 和 `event_log.md`。

组合行动使用 `ACTION_PLAN`；Python会先计算可组合度，再在一次 SQLite 事务中提交所有步骤。

```powershell
python tools/replay_campaign.py <存档目录>
python tools/verify_projection.py <存档目录>
```

执行成功后还会自动追加：

- `novel_draft.md`：按回合排列的GM完整回答，可直接复制整理成小说
- `conversation_log.md`：玩家原话、GM回答和Python事件审计记录
- `decision_audit.jsonl` / `decision_audit.md`：玩家、LLM、Python、联合决策及数据库 before/after

开局或补录回合使用 `python tools/record_turn.py`。

测试几十轮后可用 `python tools/audit_report.py <存档目录>` 查询决策来源和数据库变化，
也可用 `--turn`、`--status`、`--field player.fatigue` 筛选。

## 结算边界

- Python 计算 A/D/P、Severity、DeathFairness、战斗、经验、技能、资源、批量行动、基地、NPC效用和叙事指标。
- Python 生成 `data.resolution`、`data.action_ledger` 和状态增量。
- 事件账本是唯一可追溯的结算记录；小说文本不能覆盖公式结果。
- LLM 负责解析玩家意图、选择需要展示的选项和把已确定结果写成小说。
- `EXPLORATION`、`RESEARCH`、`SOCIAL_INTERACTION`、`REST` 会生成正式领域效果事件。
- 天赋与装备的 `rarity` 统一使用 `G/F/E/D/C/B/A/S/SS/SSS`；怪物的普通/精英/首领品质仍是独立的经验计算维度。
- `ACTION_PLAN` 由 `GameEngine.execute_host_action` 预览并原子提交。
- `COMBAT`、`BUILD`、`BATCH_ACTION` 会由 `GameEngine.execute_host_action` 路由到专用结算器，
  数据来自世界注册表和当前状态，不来自 LLM 的数值参数。

## 行动输入最小结构

```json
{
  "action_id": "scout",
  "type": "EXPLORATION",
  "target": "区域名",
  "risk_preference": "谨慎",
  "requirements": {}
}
```

`time_minutes`、`stamina_cost`、`mental_cost`、`target_difficulty`、`seed`、
`experience_gain`、`resolution` 等字段禁止由 LLM 提交；它们由 Python 从行动类型、
技能定义、世界配置和存档状态派生。
