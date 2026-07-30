# 知识边界系统

## 核心原则

每个事实必须记录谁知道、谁不知道。
LLM不能因为"作者知道"就让角色突然知道。
NPC不能使用不可能知道的情报。

## 知识结构

```yaml
knowledge_entry:
  id: 唯一标识
  fact: "事实描述"
  category: world_truth/npc_secret/player_secret/event/rule
  importance: 1-10
  
  # 谁知道
  known_by:
    - entity_id: "player"
      since_turn: 15
      how: "亲眼目睹"
      certainty: 100        # 确定程度(0-100)
    - entity_id: "npc_003"
      since_turn: 1
      how: "参与者"
      certainty: 100
  
  # 谁怀疑
  suspected_by:
    - entity_id: "npc_001"
      since_turn: 20
      certainty: 40         # 只是怀疑
  
  # 谁不知道（显式标注重要角色）
  unknown_to:
    - "player"              # 玩家角色不知道
    - "npc_002"
  
  # 揭示条件
  reveal_conditions:
    - "player_finds_diary"
    - "npc_003_confesses"
    - "turn > 50 and player_in_area_x"
  
  # 叙事功能
  narrative_function: "让玩家发现前代文明存在"
  linked_mystery: "mystery_001"
```

## 知识检查规则

### 写叙述前必须检查
```
对于本段叙述中涉及的每个事实：
  1. 主角是否知道这个事实？
     - 不知道 → 不能从主角视角写出
     - 怀疑 → 只能写猜测，不能写确认
  2. 在场NPC是否知道？
     - 不知道 → NPC不能提及或暗示
     - 知道 → 可以自然提及
  3. 这个事实是否应该被揭示？
     - 检查 reveal_conditions
     - 未满足 → 不能出现
```

### 禁止
- 主角"突然想到"一个从未获得线索的秘密
- NPC说出只有另一个NPC才知道的信息
- 系统面板显示主角不应该知道的数据
- 叙述中暗示主角不知道的隐藏规则
- 提前泄露世界真相（除非满足揭示条件）

### 允许
- 主角通过观察推断（但必须有可观察证据）
- NPC不小心说漏嘴（必须有合理原因）
- 系统公告公布公共信息
- 情报天赋提供额外信息（这是天赋的正当功能）

## 知识获取途径

```
直接观察：亲眼看到/亲耳听到 → certainty 80-100
他人告知：NPC/玩家告诉 → certainty 取决于信任度
文件记录：日记/档案/录音 → certainty 70-90
推理：从多个线索推断 → certainty 40-70
天赋：情报类能力 → certainty 90-100（天赋正当功能）
传闻：频道/路人 → certainty 20-50
```

## 欺骗与误导

```yaml
deception:
  id: 唯一标识
  deceiver: "entity_id"
  target: "entity_id"
  content: "虚假内容"
  believed_truth: "目标相信的假版本"
  actual_truth: "真实版本"
  since_turn: 0
  discovered: false
  discovery_conditions: []
  if_discovered:
    trust_change: -40
    resentment_change: +30
```

### 欺骗检测
```
每轮检查：
  对于每个活跃欺骗：
    if 目标获得与谎言矛盾的信息:
      触发怀疑
    if 怀疑累积 > 阈值:
      触发对质/揭穿事件
```

## 世界真相层级

```
第一层（公开）：所有玩家都知道的规则
第二层（探索）：需要到达特定区域/等级才能发现
第三层（隐藏）：需要特定事件/物品/NPC才能获知
第四层（终极）：整个游戏可能只揭示部分
```

### 真相揭示节奏
- 第一层：开局即知
- 第二层：第20-40轮开始碎片出现
- 第三层：第50-80轮关键揭示
- 第四层：第100+轮或可能永远不完全揭示

## 与事件溯源联动

知识获取本身是事件：
```json
{
  "type": "FACT_DISCOVERED",
  "actor": "player",
  "fact_id": "knowledge_007",
  "method": "阅读日记",
  "turn": 34,
  "certainty": 85
}
```

这确保知识获取可追溯、可回滚、可审计。
