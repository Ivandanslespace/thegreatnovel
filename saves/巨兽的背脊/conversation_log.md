# 《巨兽的背脊》对话记录

---

<!-- narrative-turn:1 -->
## 第1回 · Day 1 清晨

### 玩家原始输入

新游戏

### GM完整回答

你醒来时，第一感觉不是冷，也不是饿，而是大地正在呼吸。

脚下的黑色脊骨缓慢起伏，像一列没有尽头的山脉。灰白色的雾从两侧翻涌下去，雾底偶尔露出深谷般的鳞片与闭合的眼睑——你所在的并不是山，而是一头横跨天际的巨兽。几块骨板、旧帆布和粗糙木架被固定在它背部，组成了这座随时可能倾斜的移动营地。

你不记得自己是怎么来的。记忆只剩下坠落、黑暗，以及某个冷漠声音留下的三句话：活下去；不要站在裂缝边缘；巨兽翻身前，脊骨会先发出七次震动。

营地里没有同伴，没有武器，也没有一块肉干。远处，一串细小的黑影正沿着巨兽背部的鳞沟移动，像某种正在试探气味的虫群。更远处，巨兽的肩胛忽然沉了一下，整片骨坡随之倾斜。你的脚底传来第一道极轻的震动。

你本能地低头，脑海中浮出一个陌生而清晰的判断：这不是普通的颤动。巨兽正在改变姿势。

---

【系统面板】
┌─────────────────────────┐
│ 等级: 1  经验: 0/100     │
│ 力量:5 体质:5 敏捷:5 精神:5 │
│ 生命: 50/50  状态: 正常   │
│ 基地: 巨兽背部的移动营地 Lv.1 │
│ 时间: 第1天 清晨          │
│ 天赋: 脊动感知            │
└─────────────────────────┘

你准备怎么做？

A. 加固营地
   先检查木架、绳索与固定点，尽量让营地撑过巨兽的下一次动作。
   → 预期：提高短期安全性 / 消耗时间，暂时无法搜集资源

B. 侦察黑影
   沿背部低伏前进，确认正在靠近的生物是什么，再决定是否撤离或设伏。
   → 预期：获得危险信息或资源线索 / 暴露在未知生物附近

C. 寻找食物与材料
   趁巨兽尚未明显翻身，搜索营地周边的鳞沟与骨缝。
   → 预期：可能找到基础资源 / 可能错过姿态变化的预警

D. 自由行动（描述你想做什么，系统会拆解结算）

### Python结算事件（审计记录）

```json
{
  "event_id": "evt_0001_001",
  "type": "WORLD_CREATED",
  "actor": "system",
  "target": null,
  "data": {
    "world_name": "巨兽的背脊",
    "theme": "巨兽的背脊",
    "safe_base": "巨兽背部的移动营地",
    "difficulty": "标准"
  },
  "turn": 1,
  "timestamp": "Day 1 清晨"
}
```

---

<!-- narrative-turn:2 -->
## 第2回 · Day 1 清晨

### 玩家原始输入

B，但我想问我在哪里、我是谁、这个世界怎么运行？确认

### GM完整回答

你确认了行动。

你压低身体，沿着营地边缘的骨板向鳞沟靠近。巨兽的背部并不是平面：每一道鳞片都像倾斜的墙，鳞沟深处积着暗红色的黏液与碎骨。你借着第一次震动的间隙移动，脚下的脊骨却突然连续颤了两下，迫使你抓住一根外露的骨刺停在原地。

黑影比你预想得更快。它们不是一群虫，而是一片贴着鳞片爬行的细小寄生兽，身体扁平，前端长着能够刺入皮肤的口器。你没有看清它们的完整数量，也没能找到安全接近的角度。第三道震动传来时，你只能退回较高的骨脊，避免被它们包围。

侦察没有完全成功，但你获得了足够重要的判断：黑影会主动追踪温度和血腥味，暂时还没有发现营地；它们的活动路线正朝着巨兽肩胛方向延伸。那里可能有更大的伤口，也可能藏着能维持营地的资源。与此同时，脚下的震动变得更沉——巨兽仍在调整姿势，留给你的安全窗口正在缩短。

【行动结果】
侦察失败，但获得部分信息。
你没有受伤，也没有与寄生兽群正面冲突；但这次探索消耗了本轮的主要行动窗口。

---

【新获得情报】
◇ 黑影确认：寄生兽群
◇ 行为特征：追踪温度与血腥味
◇ 活动方向：巨兽肩胛区域
◇ 当前状态：尚未发现营地

你准备怎么做？

A. 立刻返回营地并加固固定点
   抓住剩余安全窗口，优先应对巨兽即将发生的姿态变化。

B. 冒险跟踪寄生兽群
   前往肩胛方向，查明巨兽是否受伤，并寻找可能的资源。

C. 在营地周边设置简易警戒
   不追击寄生兽，利用骨刺和旧帆布扩大预警范围。

D. 自由行动（描述你想做什么）

### Python结算事件（审计记录）

```json
{
  "event_id": "evt_0002_001",
  "type": "ACTION_RESOLVED",
  "actor": "player",
  "target": "巨兽背部的鳞沟",
  "data": {
    "action": {
      "action_id": "scout-001",
      "type": "EXPLORATION",
      "target": "巨兽背部的鳞沟",
      "primary_attribute": "agility"
    },
    "action_ledger": {
      "available_time_minutes": 240.0,
      "available_stamina": 100.0,
      "available_mental": 100.0,
      "actions": [
        {
          "type": "EXPLORATION",
          "target": "巨兽背部的鳞沟",
          "time_minutes": 120.0,
          "stamina_cost": 15.0,
          "mental_cost": 10.0,
          "tags": [
            "search"
          ]
        }
      ]
    },
    "resolution": {
      "formula_version": "1.0",
      "action_id": "scout-001",
      "advantage_components": {
        "ability_match": 10.0,
        "equipment_advantage": 0.0,
        "preparation": 5.0,
        "intelligence": 0.0,
        "teammate_assistance": 0.0,
        "environment_advantage": 0.0
      },
      "resistance_components": {
        "target_difficulty": 25.0,
        "environment_penalty": 0.0,
        "injury": 0.0,
        "fatigue": 0.0,
        "time_pressure": 3.0,
        "unknown_risk": 0.0
      },
      "advantage": 15.0,
      "resistance": 28.0,
      "K": 10.0,
      "probability": 0.214165,
      "random_roll": 0.703059,
      "severity": 0.0,
      "severity_band": "成功区",
      "death_fairness": 0.0,
      "outcome": "失败但获得部分信息",
      "death_allowed": false,
      "components": {
        "severity": {
          "difficulty": 5.0,
          "injury": 0.0,
          "resource_shortage": 0.0,
          "information_missing": 0.0,
          "time_pressure": 3.0,
          "continuous_errors": 0.0,
          "preparation": 5.0,
          "ability_match": 10.0,
          "teammate_support": 0.0,
          "survival_assets": 0.0
        },
        "death_fairness_inputs": {
          "risk_warning": 0.0,
          "causal_chain": 0.0,
          "avoidable": 0.0,
          "rule_consistency": 0.0,
          "player_responsibility": 0.0
        }
      }
    },
    "fatigue_delta": 15.0,
    "mental_delta": -10.0,
    "time_cost": 120.0,
    "hunger_delta": 0.0,
    "resource_changes": {}
  },
  "turn": 2,
  "timestamp": "Day 1 清晨"
}
```

---

<!-- narrative-turn:3 -->
## 第3回 · Day 1 清晨

### 玩家原始输入

A，确认加固营地。Ok

### GM完整回答

你转身返回营地。

身后的黑影没有追来，但那种被温度锁定的感觉仍黏在脊骨之间。你踩过倾斜的骨板，抓住营地外侧那根已经松动的固定索。第二道震动传来时，木架向外滑了半寸，旧帆布被风猛地掀起，露出下面几处磨损严重的连接点。

你没有时间重新搭建，只能把现有材料重新分配：先收紧承重索，再用骨刺卡住最容易脱开的节点，最后将一块松动的骨板压回原位。第三道震动比前两道沉得多，整座营地像被一只无形的手托起又放下。你的手掌被粗糙纤维磨破，但固定点没有继续滑脱。

加固成功了，却并不完整。最外侧的两处连接仍然脆弱，无法保证营地在真正翻身时保持稳定；而且你刚刚失去的时间，让肩胛方向的寄生兽群更接近了。

【行动结果】
◇ 营地固定点：已加固
◇ 加固质量：部分稳定
◇ 代价：体力与精神进一步消耗
◇ 当前风险：巨兽姿态变化仍未结束

【系统面板】
┌─────────────────────────┐
│ 等级: 1  经验: 0/100     │
│ 力量:5 体质:5 敏捷:5 精神:5 │
│ 生命: 50/50  状态: 轻微擦伤 │
│ 基地: 巨兽背部的移动营地 Lv.1 │
│ 时间: 第1天 清晨          │
│ 天赋: 脊动感知            │
└─────────────────────────┘

营地暂时稳住了。下一道震动，正在靠近。

你准备怎么做？

A. 继续修补最外侧连接点
B. 观察巨兽震动，判断它下一步动作
C. 收拾营地，准备向更安全的骨脊撤离
D. 自由行动（描述你想做什么）

### Python结算事件（审计记录）

```json
{
  "event_id": "evt_0003_001",
  "type": "ACTION_RESOLVED",
  "actor": "player",
  "target": "营地固定点",
  "data": {
    "action": {
      "action_id": "secure-001",
      "type": "SHORT_ACTION",
      "target": "营地固定点",
      "primary_attribute": "strength"
    },
    "action_ledger": {
      "available_time_minutes": 120.0,
      "available_stamina": 85.0,
      "available_mental": 90.0,
      "actions": [
        {
          "type": "SHORT_ACTION",
          "target": "营地固定点",
          "time_minutes": 30.0,
          "stamina_cost": 2.0,
          "mental_cost": 4.0,
          "tags": [
            "defense"
          ]
        }
      ]
    },
    "resolution": {
      "formula_version": "1.0",
      "action_id": "secure-001",
      "advantage_components": {
        "ability_match": 10.0,
        "equipment_advantage": 0.0,
        "preparation": 5.0,
        "intelligence": 0.0,
        "teammate_assistance": 0.0,
        "environment_advantage": 0.0
      },
      "resistance_components": {
        "target_difficulty": 10.0,
        "environment_penalty": 0.0,
        "injury": 0.0,
        "fatigue": 3.0,
        "time_pressure": 3.0,
        "unknown_risk": 0.0
      },
      "advantage": 15.0,
      "resistance": 16.0,
      "K": 10.0,
      "probability": 0.475021,
      "random_roll": 0.436461,
      "severity": 0.0,
      "severity_band": "成功区",
      "death_fairness": 0.0,
      "outcome": "成功但付出代价",
      "death_allowed": false,
      "components": {
        "severity": {
          "difficulty": 2.0,
          "injury": 0.0,
          "resource_shortage": 0.0,
          "information_missing": 0.0,
          "time_pressure": 3.0,
          "continuous_errors": 0.0,
          "preparation": 5.0,
          "ability_match": 10.0,
          "teammate_support": 0.0,
          "survival_assets": 0.0
        },
        "death_fairness_inputs": {
          "risk_warning": 0.0,
          "causal_chain": 0.0,
          "avoidable": 0.0,
          "rule_consistency": 0.0,
          "player_responsibility": 0.0
        }
      }
    },
    "fatigue_delta": 2.0,
    "mental_delta": -4.0,
    "time_cost": 30.0,
    "hunger_delta": 0.0,
    "resource_changes": {}
  },
  "turn": 3,
  "timestamp": "Day 1 清晨"
}
```

---

<!-- narrative-turn:4 -->
## 第4回 · Day 1 清晨

### 玩家原始输入

B，Ok，确认观察巨兽震动。

### GM完整回答

你没有立刻继续动手。

你伏低身体，将一只手贴在脚下的黑色脊骨上。第一道震动像远处的闷雷，第二道更短，第三道却在末端拖出一阵细碎的回响。你闭上眼，把风声、帆布的拍击声和骨架的吱响一点点排除。

「脊动感知」捕捉到了节律。

巨兽不是要立刻翻身。它正在收拢左侧躯体，先抬起肩胛，再把重量向右侧转移。真正危险的不是营地中央，而是外侧那两处尚未完全稳固的连接点——如果继续留在那里，下一次震动会让它们承受最大的拉力。

你还察觉到另一个细节：寄生兽群的活动节奏与巨兽的收拢动作同步。它们似乎在等待巨兽皮肤绷紧后，从伤口附近寻找新的入口。

判断成功，但持续集中注意力让你的呼吸变得沉重。你没有受伤，也没有立即遭遇攻击；然而安全窗口正在快速缩短。

【获得情报】
◇ 巨兽动作：先抬起左侧肩胛，再向右侧转移重量
◇ 高危位置：营地外侧两处松动连接点
◇ 寄生兽群：正在等待巨兽皮肤绷紧

【状态变化】
疲劳：19
精神：82
剩余行动时间：约60分钟

你准备怎么做？

A. 立即拆除外侧连接，带走可用材料
B. 继续加固外侧连接点
C. 沿较安全的右侧骨脊撤离营地
D. 自由行动（描述你想做什么）

### Python结算事件（审计记录）

```json
{
  "event_id": "evt_0004_001",
  "type": "ACTION_RESOLVED",
  "actor": "player",
  "target": "巨兽脊骨震动",
  "data": {
    "action": {
      "action_id": "read-vibration-001",
      "type": "SHORT_ACTION",
      "target": "巨兽脊骨震动",
      "primary_attribute": "spirit"
    },
    "action_ledger": {
      "available_time_minutes": 90.0,
      "available_stamina": 83.0,
      "available_mental": 86.0,
      "actions": [
        {
          "type": "SHORT_ACTION",
          "target": "巨兽脊骨震动",
          "time_minutes": 30.0,
          "stamina_cost": 2.0,
          "mental_cost": 4.0,
          "tags": [
            "observe",
            "talent"
          ]
        }
      ]
    },
    "resolution": {
      "formula_version": "1.0",
      "action_id": "read-vibration-001",
      "advantage_components": {
        "ability_match": 10.0,
        "equipment_advantage": 0.0,
        "preparation": 5.0,
        "intelligence": 0.0,
        "teammate_assistance": 0.0,
        "environment_advantage": 0.0
      },
      "resistance_components": {
        "target_difficulty": 10.0,
        "environment_penalty": 0.0,
        "injury": 0.0,
        "fatigue": 3.4,
        "time_pressure": 3.0,
        "unknown_risk": 0.0
      },
      "advantage": 15.0,
      "resistance": 16.4,
      "K": 10.0,
      "probability": 0.465057,
      "random_roll": 0.259501,
      "severity": 0.0,
      "severity_band": "成功区",
      "death_fairness": 0.0,
      "outcome": "成功但付出代价",
      "death_allowed": false,
      "components": {
        "severity": {
          "difficulty": 2.0,
          "injury": 0.0,
          "resource_shortage": 0.0,
          "information_missing": 0.0,
          "time_pressure": 3.0,
          "continuous_errors": 0.0,
          "preparation": 5.0,
          "ability_match": 10.0,
          "teammate_support": 0.0,
          "survival_assets": 0.0
        },
        "death_fairness_inputs": {
          "risk_warning": 0.0,
          "causal_chain": 0.0,
          "avoidable": 0.0,
          "rule_consistency": 0.0,
          "player_responsibility": 0.0
        }
      }
    },
    "fatigue_delta": 2.0,
    "mental_delta": -4.0,
    "time_cost": 30.0,
    "hunger_delta": 0.0,
    "resource_changes": {}
  },
  "turn": 4,
  "timestamp": "Day 1 清晨"
}
```

---

<!-- narrative-turn:5 -->
## 第5回 · Day 1 清晨

### 玩家原始输入

B，Ok，确认继续加固外侧连接点。

### GM完整回答

你把身体贴向营地外侧，伸手够住第一处松动的连接。

这一次，你没有试图和巨兽的动作对抗，而是顺着它的收拢节律等待。左侧肩胛抬起时，你放松固定索；重量向右转移时，你猛地收紧绳结，把骨刺斜斜楔进连接缝里。第一处固定点发出一声刺耳的摩擦声，终于停止外滑。

第二处连接更靠近边缘。你必须跪在一块不断震颤的骨板上完成最后的加固。寄生兽群在下方的鳞沟里掠过，细小的口器刮过骨面，却没有找到你的血迹。你抓住下一次震动的间隙，将剩余固定索绕过突出的骨棱，打下一个临时死结。

两处连接点都稳住了。

但这只是延缓，不是修复。固定索已经被拉到极限，骨板本身也出现了新的裂纹。巨兽还没有完成重量转移，真正的震荡即将到来。

【行动结果】
◇ 外侧连接点：暂时稳定
◇ 营地状态：能够应对下一轮姿态变化，但仍存在结构风险
◇ 寄生兽群：经过附近，暂未发现你

【状态变化】
疲劳：21
精神：78
剩余行动时间：约30分钟

巨兽的左侧肩胛已经抬到最高点。下一刻，它将把全部重量压向右侧。

你准备怎么做？

A. 留在营地中央，抓住固定索等待震荡过去
B. 立刻撤向右侧骨脊，避开营地可能的坍塌方向
C. 趁寄生兽群经过，搜索它们留下的鳞沟
D. 自由行动（描述你想做什么）

### Python结算事件（审计记录）

```json
{
  "event_id": "evt_0005_001",
  "type": "ACTION_RESOLVED",
  "actor": "player",
  "target": "营地外侧连接点",
  "data": {
    "action": {
      "action_id": "secure-outer-001",
      "type": "SHORT_ACTION",
      "target": "营地外侧连接点",
      "primary_attribute": "strength"
    },
    "action_ledger": {
      "available_time_minutes": 60.0,
      "available_stamina": 81.0,
      "available_mental": 82.0,
      "actions": [
        {
          "type": "SHORT_ACTION",
          "target": "营地外侧连接点",
          "time_minutes": 30.0,
          "stamina_cost": 2.0,
          "mental_cost": 4.0,
          "tags": [
            "defense",
            "repair"
          ]
        }
      ]
    },
    "resolution": {
      "formula_version": "1.0",
      "action_id": "secure-outer-001",
      "advantage_components": {
        "ability_match": 10.0,
        "equipment_advantage": 0.0,
        "preparation": 5.0,
        "intelligence": 0.0,
        "teammate_assistance": 0.0,
        "environment_advantage": 0.0
      },
      "resistance_components": {
        "target_difficulty": 10.0,
        "environment_penalty": 0.0,
        "injury": 0.0,
        "fatigue": 3.8,
        "time_pressure": 3.0,
        "unknown_risk": 0.0
      },
      "advantage": 15.0,
      "resistance": 16.8,
      "K": 10.0,
      "probability": 0.455121,
      "random_roll": 0.006063,
      "severity": 0.0,
      "severity_band": "成功区",
      "death_fairness": 0.0,
      "outcome": "成功但付出代价",
      "death_allowed": false,
      "components": {
        "severity": {
          "difficulty": 2.0,
          "injury": 0.0,
          "resource_shortage": 0.0,
          "information_missing": 0.0,
          "time_pressure": 3.0,
          "continuous_errors": 0.0,
          "preparation": 5.0,
          "ability_match": 10.0,
          "teammate_support": 0.0,
          "survival_assets": 0.0
        },
        "death_fairness_inputs": {
          "risk_warning": 0.0,
          "causal_chain": 0.0,
          "avoidable": 0.0,
          "rule_consistency": 0.0,
          "player_responsibility": 0.0
        }
      }
    },
    "fatigue_delta": 2.0,
    "mental_delta": -4.0,
    "time_cost": 30.0,
    "hunger_delta": 0.0,
    "resource_changes": {}
  },
  "turn": 5,
  "timestamp": "Day 1 清晨"
}
```

---

<!-- narrative-turn:6 -->
## 第6回 · Day 1 清晨

### 玩家原始输入

C，Ok，确认搜索寄生兽留下的鳞沟。

### GM完整回答

你没有撤离。

趁寄生兽群最后一只个体钻入鳞片缝隙，你翻过外侧骨板，俯身检查它们经过的鳞沟。巨兽的皮肤在你掌下绷紧，像一面即将被拉裂的鼓。你知道自己只有很短的时间。

鳞沟里没有完整的尸体，也没有可以直接带走的肉干或骨材。寄生兽留下了一层半透明的黏膜，黏在几道细小裂缝周围。黏膜上分布着暗色脉络，方向与巨兽肩胛的收拢完全一致，像某种微型的血管地图。

你用一截碎骨拨开黏膜，发现裂缝深处不是普通伤口。里面有微弱的蓝白色光点一闪而过，随巨兽的震动明灭。寄生兽群并不是随机觅食——它们在追逐某种从巨兽体内渗出的能量。

下一道震动突然提前到来。你来不及继续确认，只能抓住固定索退回营地中央。没有物品被确认取得，但你记住了这条线索：肩胛区域可能存在能量源或更深的伤口。

【行动结果】
◇ 搜索：成功但付出代价
◇ 物资：未确认获得可入库资源
◇ 新线索：寄生兽群正在追踪巨兽体内渗出的蓝白色能量
◇ 生命：50/50

【系统面板】
┌─────────────────────────┐
│ 等级: 1  经验: 0/100     │
│ 力量:5 体质:5 敏捷:5 精神:5 │
│ 生命: 50/50  状态: 正常   │
│ 基地: 巨兽背部的移动营地 Lv.1 │
│ 时间: 第1天 清晨          │
│ 天赋: 脊动感知            │
└─────────────────────────┘

最后的行动窗口已经用尽。巨兽开始把全部重量压向右侧，营地外的骨板发出沉闷的断裂声。

你准备怎么做？

A. 留在营地中央，抓住固定索等待震荡
B. 立刻撤向右侧骨脊
C. 放弃营地，直接前往肩胛区域
D. 自由行动（描述你想做什么）

### Python结算事件（审计记录）

```json
{
  "event_id": "evt_0006_001",
  "type": "ACTION_RESOLVED",
  "actor": "player",
  "target": "寄生兽经过的鳞沟",
  "data": {
    "action": {
      "action_id": "search-traces-001",
      "type": "SHORT_ACTION",
      "target": "寄生兽经过的鳞沟",
      "primary_attribute": "agility"
    },
    "action_ledger": {
      "available_time_minutes": 30.0,
      "available_stamina": 79.0,
      "available_mental": 78.0,
      "actions": [
        {
          "type": "SHORT_ACTION",
          "target": "寄生兽经过的鳞沟",
          "time_minutes": 30.0,
          "stamina_cost": 2.0,
          "mental_cost": 4.0,
          "tags": [
            "search",
            "scavenge"
          ]
        }
      ]
    },
    "resolution": {
      "formula_version": "1.0",
      "action_id": "search-traces-001",
      "advantage_components": {
        "ability_match": 10.0,
        "equipment_advantage": 0.0,
        "preparation": 5.0,
        "intelligence": 0.0,
        "teammate_assistance": 0.0,
        "environment_advantage": 0.0
      },
      "resistance_components": {
        "target_difficulty": 10.0,
        "environment_penalty": 0.0,
        "injury": 0.0,
        "fatigue": 4.2,
        "time_pressure": 3.0,
        "unknown_risk": 0.0
      },
      "advantage": 15.0,
      "resistance": 17.2,
      "K": 10.0,
      "probability": 0.445221,
      "random_roll": 0.376369,
      "severity": 0.0,
      "severity_band": "成功区",
      "death_fairness": 0.0,
      "outcome": "成功但付出代价",
      "death_allowed": false,
      "components": {
        "severity": {
          "difficulty": 2.0,
          "injury": 0.0,
          "resource_shortage": 0.0,
          "information_missing": 0.0,
          "time_pressure": 3.0,
          "continuous_errors": 0.0,
          "preparation": 5.0,
          "ability_match": 10.0,
          "teammate_support": 0.0,
          "survival_assets": 0.0
        },
        "death_fairness_inputs": {
          "risk_warning": 0.0,
          "causal_chain": 0.0,
          "avoidable": 0.0,
          "rule_consistency": 0.0,
          "player_responsibility": 0.0
        }
      }
    },
    "fatigue_delta": 2.0,
    "mental_delta": -4.0,
    "time_cost": 30.0,
    "hunger_delta": 0.0,
    "resource_changes": {}
  },
  "turn": 6,
  "timestamp": "Day 1 清晨"
}
```
