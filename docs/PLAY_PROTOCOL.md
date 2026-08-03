# Codex 聊天游玩协议

## 启动状态机

```text
玩家说“开始游戏”
  → hello：确认本地协议可用
  → list：恢复 ACTIVE / STOPPING Campaign
  → 无存档：取得玩家的一句话
  → 生成并 compile-world 校验候选蓝图（或明确选择内置世界）
  → start：创建 SQLite Campaign 并提交 turn-0 opening event
  → narrate：提交序章，刷新 novel_draft.md
  → 显示剧情、成长面板和合法选择
```

Codex 每次任务只在启动时读取项目 `AGENTS.md`。更新主持规则后，应新建一个项目任务再说“开始游戏”。

## 一句话世界构建

任意玩家描述不是关键词换皮入口。除非玩家明确选择内置世界，Codex 要把一句话扩展为独立 JSON 蓝图，并完成：

1. 明确控制缺口、核心因果问题和非对称杠杆；
2. 至少 16 个有时间、风险、失败后果和有限次数的基础行动；
3. 至少三个持续行动者、两个离屏过程、三个机会窗口；
4. 两条会改变未来转化效率或可用策略的复利链；
5. 明确关系反转、阶层跃迁和一个带行动/过程/里程碑的更大世界候选；
6. 杠杆消融后，合法行动或可达成长路线明显改变；
7. 与两个参考世界比较因果状态、最优顺序和机会成本，确认不是替换名词。

候选写入 `.tgn/incoming` 后运行：

```powershell
python scripts/tgn.py compile-world --file C:\absolute\candidate.world.json
```

只有 `experience_gate.passed=true` 才能进入路线验收。Codex 还要为候选世界设计一条包含恢复余量的完整路线，并运行：

```powershell
python scripts/tgn.py audit-world --file C:\absolute\candidate.world.json --prompt "玩家原句" --campaign campaign-id --seed 1 --route observe,verify,produce,reverse,tier_up,expand_action
```

`passed=true` 要求真实引擎逐步确认关系反转、阶层跃迁、更大世界 materialize，并执行至少一个扩展行动。正式启动必须再次提交同一证书：

```powershell
python scripts/tgn.py start --prompt "玩家原句" --blueprint-file C:\absolute\candidate.world.json --audit-seed 1 --audit-route observe,verify,produce,reverse,tier_up,expand_action --campaign campaign-id
```

服务层会使用同一 prompt、Campaign ID、seed 和路线重新执行，并把 blueprint hash、route、audit seed 和四项 checks 写入隐藏的 Campaign 元数据；这些字段在审计和正式 Campaign 的初始状态中完全相同，因此确定性 RNG 也相同。对外只返回 certificate hash 和 checks，不返回 seed。缺少证书、seed 不一致或 hash/路线验收失败会直接拒绝开局。门禁无法自动证明文学质量或反换皮，因此返回的 `semantic_review_required` 也必须由 Codex 完成。

## 行动协议

`actions` 只返回当前合法行动；`preview` 是纯函数，不写存档；`act` 接受一个行动并在同一决策中推进到期的 NPC / 世界过程、里程碑和扩展。行动结果由 campaign seed、接受顺序、行动 ID 和前状态决定，与 request ID 或叙事措辞无关。

玩家看见的预览至少包括：

- 时间成本与资源成本；
- 已知风险；
- 当前仍未知的变量；
- 选择它会放弃什么；
- 是否使用主角杠杆。

自由文本只能映射到一个 action。若玩家同时提出互斥计划，Codex 要求选定优先行动，不能把它们偷偷合并。

## 自动存档与叙事协议

`act` 成功返回时，状态、事件、事实和 hash chain 已经进入 SQLite；即使 Codex 随后中断，行动也不能重结算。Campaign 会保留一个 pending narration，并禁止下一行动。

Narrator 只能使用 `required_claims` 和 canonical player projection。每条 claim 的完整原文必须进入 prose；连接句可以文学化，但不能形成新的资源、能力、关系、秘密或结果。提交后系统原子刷新：

```text
saves/<campaign>/exports/novel_draft.md
```

如果写盘在数据库提交后失败，同一 narration response 是恢复凭据；`python scripts/tgn.py recover --campaign <id>` 会调用 `recover_exports`，从不可变事件与叙事记录重建派生文件，而不改历史。

## 结束与小说生成

`end` 首先提交 `campaign.ending_requested`，Campaign 进入 `STOPPING`，不再接受行动。尾声 narration 成功后生成：

- `exports/novel.md`：序章、所有已提交章节与尾声；
- `exports/history.json`：完整事件和叙事来源；
- `exports/manifest.json`：blueprint hash、event head、事件范围与内容 hash。

只有三份文件与数据库当前 event head/count/range 完全一致，Campaign 才进入 `STOPPED`。任何导出失败都保持可重试，不能把半成品宣布为最终小说。
