# 事件溯源系统

## 核心原则

不直接修改状态。所有变化通过事件记录，状态由事件推导。

```
事件账本（只追加）→ 状态快照（定期保存）→ 当前状态（快照+后续事件）
```

## 事件账本格式

event_log.md 中每条事件使用以下结构：

```markdown
### Turn {N} | {游戏内时间}

```json
[
  {
    "event_id": "evt_0001",
    "type": "事件类型",
    "actor": "执行者",
    "target": "目标（如有）",
    "data": {},
    "turn": N,
    "timestamp": "游戏内时间"
  }
]
```

**叙述摘要**：一句话概括本轮发生了什么。
**状态变化**：列出所有数值变化。
```

Turn 1—16 的历史存档允许使用旧版 `event_type/actors/consequences` 扩展格式。
从 Turn 17 起，新增事件必须使用标准格式并提供唯一 `event_id`；校验器不会把文件头部注释当作事件字段。

涉及玩家行动的标准事件还必须在 `data.action_ledger` 中记录：

```yaml
action_ledger:
  available_time_minutes: 240
  available_stamina: 44
  available_mental: 38
  actions:
    - type: SOCIAL_INTERACTION
      target: npc_003
      time_minutes: 30
      stamina_cost: 2
      mental_cost: 4
      tags: [socially_committed]
```

由 Python 引擎结算的行动、战斗和批量行动还必须在 `data.resolution` 中保存
公式版本、输入分项、中间值、确定性随机数和最终结果。小说文本不能替代该字段：

```yaml
resolution:
  formula_version: "1.0"
  advantage: 24
  resistance: 25
  K: 10
  probability: 0.475
  random_roll: 0.41
  severity: 28
  outcome: "普通成功"
```

## 事件类型完整列表

### 物品与资源
```
ITEM_GAINED          获得物品
ITEM_CONSUMED        消耗物品
ITEM_LOST            丢失物品（死亡掉落/被偷）
ITEM_CRAFTED         制造物品
ITEM_EQUIPPED        装备物品
ITEM_UNEQUIPPED      卸下装备
ITEM_REPAIRED        修理装备
RESOURCE_GAINED      获得资源
RESOURCE_CONSUMED    消耗资源
RESOURCE_TRADED      交易资源
```

### 战斗与伤害
```
COMBAT_STARTED       战斗开始
COMBAT_ENDED         战斗结束
DAMAGE_DEALT         造成伤害
DAMAGE_TAKEN         受到伤害
INJURY_CHANGED       伤势变化
STATUS_APPLIED       状态效果施加
STATUS_REMOVED       状态效果移除
CHARACTER_DIED       角色死亡
SKILL_USED           使用技能
TALENT_TRIGGERED     天赋触发
```

### 成长
```
LEVEL_UP             升级
EXP_GAINED           获得经验
ATTRIBUTE_CHANGED    属性变化
SKILL_LEARNED        学会技能
SKILL_UPGRADED       技能升级
TALENT_CHOSEN        天赋选择（三选一）
CLASS_CHANGED        转职
BREAKTHROUGH         突破
```

### 基地
```
BUILDING_BUILT       建造模块
BUILDING_UPGRADED    升级模块
BUILDING_DESTROYED   模块被毁
BASE_UPGRADED        基地升级
BASE_DAMAGED         基地受损
BASE_REPAIRED        基地修复
DEFENSE_EVENT        防御战
```

### 探索
```
AREA_ENTERED         进入区域
AREA_LEFT            离开区域
AREA_DISCOVERED      发现新区域
EXTRACTION_SUCCESS   成功撤离
EXTRACTION_FAILED    撤离失败
DUNGEON_ENTERED      进入副本
DUNGEON_COMPLETED    完成副本
DUNGEON_FAILED       副本失败
```

### 社交与关系
```
NPC_MET              遇见NPC
RELATIONSHIP_CHANGED 关系变化
PROMISE_MADE         做出承诺
PROMISE_BROKEN       违背承诺
PROMISE_FULFILLED    兑现承诺
SECRET_SHARED        分享秘密
SECRET_DISCOVERED    发现秘密
DECEPTION_STARTED    开始欺骗
DECEPTION_REVEALED   欺骗被揭穿
FACTION_JOINED       加入势力
FACTION_LEFT         离开势力
FACTION_RANK_UP      职位晋升
BETRAYAL             背叛
```

### 知识与剧情
```
FACT_DISCOVERED      发现事实
MYSTERY_ADVANCED     悬念推进
MYSTERY_RESOLVED     悬念解决
FORESHADOW_PLANTED   埋设伏笔
FORESHADOW_TRIGGERED 伏笔触发
QUEST_STARTED        任务开始
QUEST_COMPLETED      任务完成
QUEST_FAILED         任务失败
ENDING_TRIGGERED     结局触发
```

### 世界与时间
```
DAY_ADVANCED         进入新一天
DISASTER_OCCURRED    灾难发生
DISASTER_SURVIVED    灾难幸存
AREA_POPULATION_CHANGED 区域怪物数量变化
FACTION_ACTION       势力自主行动
WORLD_EVENT          世界事件
```

## 状态快照

每10轮保存一次完整状态快照。

### 快照格式
在 event_log.md 中用特殊标记：

```markdown
---
## 📸 SNAPSHOT | Turn {N}

完整状态已保存至各 .yaml 文件。
本快照对应回合：{N}
后续事件从 Turn {N+1} 开始。
---
```

### 快照时机
- 每10轮自动保存
- 返回基地时保存
- 完成副本后保存
- 重大剧情节点保存
- 玩家手动请求保存

### 状态重建
```
当前状态 = 最近快照 + 快照后所有事件的顺序应用
```

## 事件应用规则

### 顺序性
事件必须按回合顺序应用。同一回合内的事件按发生顺序排列。

### 不可变性
已提交的事件不能修改。如果需要"撤销"，创建新的补偿事件：
```json
{
  "type": "ITEM_GAINED",
  "data": {"item": "诡晶", "quantity": -50},
  "reason": "回滚：上轮计算错误"
}
```

### 可追溯性
任何当前状态都可以追溯到产生它的事件链。
"为什么主角有200枚诡晶？" → 查看事件账本中所有RESOURCE_GAINED和RESOURCE_CONSUMED。

## 与校验器联动

事件提交前必须通过校验器（见 validators.md）。
校验不通过的事件不能提交。

## 分支存档

如果需要创建分支（如：尝试不同选择）：
1. 复制当前所有 .yaml 文件到新文件夹
2. 复制 event_log.md 到分支点
3. 从分支点开始新的事件流
