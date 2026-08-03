# TheGreatNovel 小说游戏设计：主心骨价值观

> 项目：TheGreatNovel  
> 整理日期：2026-07-31  
> 文档定位：这不是功能需求清单，而是一份“设计宪法”。  
> 以后无论新增世界、机制、Prompt、Agent、状态字段，还是审查代码，都应该先问：**它是否符合下面这些价值观？**
> 当前开发边界、冻结事实、Genesis 合同与 Active Roadmap 统一见 [`DEV_SPEC.md`](DEV_SPEC.md)。

读取规则：普通 coding、bugfix 或局部 review 不要求每次完整读取本文；至少读取一句话定义、
最短核心原则、与当前 Feature 直接相关的章节，以及 `DEV_SPEC.md` 中的当前阶段合同。只有
架构级、产品级、跨 Feature、authority、Knowledge、WorldGen、Replay 或长期路线变更，才
要求完整读取本文。减少上下文负担不等于跳过设计价值；当前实现范围、冻结边界、Active
Roadmap 和验收命令始终以 `DEV_SPEC.md` 为权威。

---

# 0. 一句话定义

**TheGreatNovel 不是“让 LLM 陪玩家写一篇小说”，而是让玩家进入一个会自行运转、资源有限、机会会消失、选择有代价、成长能改变策略空间的世界，并把这段真实模拟出来的经历写成小说。**

小说感来自叙事表现。

游戏感来自规则、约束、代价、信息差与不可逆后果。

真正的目标，是让两者建立在**同一个真实运行的世界状态**之上，而不是彼此独立。

---

# 1. 最高原则：先有真实世界，再有小说

TheGreatNovel 最重要的设计价值不是“文笔好”，而是：

> **故事必须是世界运行后的结果，而不是 LLM 为了好看临时编出来的结果。**

世界中发生的事情，应尽可能能够追溯到：

- 玩家之前做过什么；
- 玩家没有做什么；
- 时间过去了多久；
- NPC 在这段时间里做了什么；
- 哪些资源被消耗；
- 哪些机会已经消失；
- 哪些关系已经改变；
- 哪些风险已经累积；
- 哪些承诺已经无法撤回。

因此：

```text
Simulation / State
        ↓
 Consequence
        ↓
 Narrative
```

而不是：

```text
LLM 想写一个精彩情节
        ↓
临时修改世界
        ↓
再补状态解释
```

### 核心判断标准

如果删掉小说文字，只看结构化状态和事件日志，这个世界仍然应该大致成立。

---

# 2. 选择必须意味着“放弃”

这是整个游戏最核心的交互价值观之一。

玩家看到的多个行动，不应该只是：

> “你想先做哪件事？”

而应该是：

> **“你愿意为了得到什么，而放弃什么？”**

如果玩家永远可以回答：

> A、B、C 我全部做。

而系统也允许无损执行，那么 A、B、C 就不是三个选择，只是三个待办事项。

真正的选择必须至少存在一种冲突：

- 时间冲突；
- 地点冲突；
- 资源冲突；
- 风险冲突；
- 阵营冲突；
- 人际关系冲突；
- 信息不足；
- 机会窗口；
- 不可逆承诺；
- 路线锁定；
- 身份暴露；
- 对其他人的机会让渡。

### 理想状态

例如：

```text
你只有 2 小时。

A. 搜索废弃车站
   + 可能获得关键物资
   - 需要 2 小时
   - 可能遭遇敌人
   - 商队离开前无法赶回

B. 留在营地接触商队
   + 获得稀有交易机会
   + 可能得到远方情报
   - 车站中的目标可能被其他人捷足先登

C. 跟踪可疑幸存者
   + 可能发现一条隐藏剧情线
   - 暂时没有直接资源收益
   - 被发现会损害关系
```

三个选项之所以成立，不是因为文字不同，而是因为：

> **选择其中一个，会改变另外两个。**

---

# 3. 时间不是背景，是最重要的货币之一

时间必须是真正进入模拟系统的资源。

玩家的行动应该明确区分：

- 不耗时的界面 / 信息操作；
- 短时间动作；
- 长时间行动；
- 跨地点行动；
- 需要持续投入的计划；
- 会推进整个世界的行动。

世界时间推进以后：

- NPC 也应该行动；
- 其他玩家 / peers 也应该行动；
- 天气可能变化；
- 资源可能被拿走；
- 市场可能变化；
- 某个人可能离开；
- 某个伤者可能恶化；
- 某个敌人可能完成准备；
- 某条道路可能关闭；
- 某个机会可能永久消失。

### 一个重要原则

**时间成本不是“扣掉 2 小时”这么简单，而是“世界获得了 2 小时行动权”。**

这意味着：

> 玩家花掉的时间，本质上也是把行动机会让给整个世界。

时间的稀缺对象会随成长改变。已经解决的低层资源获取应逐步被自动化、委托或背景化；
这不是取消时间成本，而是让玩家把时间花在新的、更稀缺的资源、关系、责任、机会和
战略冲突上。系统不得为了维持旧循环，强迫已经建立稳定生产能力的玩家重复同一种劳动。

---

# 4. 世界必须在玩家看不到的地方继续运行

TheGreatNovel 不应该是一个：

> “玩家走到哪里，哪里才生成内容”

的主题公园。

它应该更像一个持续存在的世界。

即使玩家没有观察：

- NPC 仍然有目标；
- NPC 仍然寻找资源；
- NPC 之间会交易、合作、冲突；
- public peers 会成长、受伤、死亡、领先或落后；
- 阵营会形成；
- 资源点会被探索；
- 谣言会传播；
- 某些人物会因为玩家没有介入而走向完全不同的命运。

### 最重要的体验之一

玩家应该偶尔发现：

> “这件事发生的时候，我根本不在场。”

甚至：

> “如果我三天前做了另一个选择，现在可能完全不是这样。”

这种感觉能够制造真正的世界感。

---

# 5. 玩家不是世界中心，但应该能够成为重要变量

世界不能为了玩家自动让路。

不应该默认：

- 好东西永远等玩家来拿；
- 重要 NPC 永远等玩家出现；
- Boss 永远等玩家准备好；
- 玩家错过的信息会自动重新出现；
- 世界重大事件只有玩家到了才开始。

但与此同时，玩家的决定必须有足够大的**因果影响力**。

理想体验是：

世界不应该为了主角停止运行，也不应该让所有 NPC、资源和事件自动等待主角。

但 TheGreatNovel 同样不是一个追求“所有角色完全公平”的社会模拟器。

主角必须拥有明显高于普通人的长期成长潜力。

理想体验不是：

世界围着我转。

也不是：

我只是这个世界无数普通人中的一个。

而是：

世界不会为我停下来，但如果我活下来、理解规则并正确利用自己的优势，我能够以普通人极难复制的速度不断向上突破。

因此：

世界运行规则
对所有人基本一致

但主角拥有
更高的成长上限
+ 更强的优势复利能力
+ 更高价值的机会暴露率
+ 独特而不可轻易复制的能力结构

主角光环应该体现为长期轨迹上的明显正偏置，而不是每一次局部事件都自动获胜。

---

# 6. 主角优势必须改变玩法，而不只是提高数值

TheGreatNovel 的主角可以很强，甚至可以有非常夸张的独特能力。

但“强”不应该只意味着：

```text
攻击 +30%
搜索效率 +20%
掉落率 +15%
感知范围 +50m
```

真正好的核心能力应该改变玩家思考问题的方式。

### 一个优秀天赋应该做到

它至少改变下列一种东西：

- 玩家能够看到什么；
- 玩家能够做什么；
- 玩家如何利用世界规则；
- 哪些风险值得承担；
- 哪些资源具有特殊价值；
- 什么信息只有玩家可以获得；
- 什么组合策略只有这个主角能够成立；
- 玩家与 NPC 的博弈方式；
- 玩家对长期路线的规划方式。

### 关键不是"别人没有"

而是：

> **如果把这个能力拿掉，玩家整套最优策略都应该改变。**

这才叫独特能力。

### V2 补充：能力来源不必只属于玩家自身

长期来看，Capability 可以来自：

```text
Actor 自身
Equipment
Habitat（生存承载体）
Relationship（关系）
Team（团队配合）
Environment（环境激活）
Organization（组织授权）
World Phase（世界阶段）
```

这带出一个重要原则：

> **Capability 是一种"现在可以成立的行动可能性"，不应该默认等价于 `player.skills`。**

例如：因为与某人形成高度配合，一个原本不可能执行的联合行动成立。或者：因为当前位于某类环境，某能力产生新的用途。

### V2 补充：能力与环境发生关系

好的能力可以利用：

```text
地点
环境标签
天气
时间
世界阶段
附近实体
关系
```

而不只是 `damage +20%`。

设计目标：

> 玩家理解世界以后，能够发现"这个能力在这里有另一种用法"。

这与 Section 11"强奖励来自理解并利用系统"形成呼应。

---

## 6.1 主角光环是长期统计优势，而不是临时作弊

TheGreatNovel 应该明确承认：

这是一个主角故事。

主角不需要和普通 NPC 拥有完全相同的长期成长分布。

如果运行足够长的时间，主角应该明显更容易：

- 接触高价值机会；
- 将普通机会转化成巨大收益；
- 从危机中获得新的成长路径；
- 形成别人难以复制的组合优势；
- 获得能够继续复利的资源、关系、能力或知识；
- 突破当前社会层级的正常成长上限；
- 在一个竞争群体中逐步进入顶尖位置。

但主角光环不能表现为：

```text
快死了
→ 系统凭空救场

缺资源
→ 地上突然出现宝箱

打不过
→ 敌人突然犯蠢

错过机会
→ 世界重新把机会送回来
```

这种行为破坏世界真实性。

更理想的主角光环是：

```text
同样面对十个机会

普通人：
大部分看不到
部分无法利用
部分没有能力承担风险

主角：
更可能接触其中真正高价值的几个
并且因为独特能力、判断或已有积累
把其中一个转化成巨大的长期优势
```

因此：

幸运应该影响机会分布，而不是直接决定结果。

天赋应该改变收益函数，而不是简单提高基础数值。

主角光环应该让优秀决策获得更大的复利空间，而不是替玩家取消决策。

### 主角光环必须可调节

系统应该允许通过少量全局参数控制不同作品的"爽文强度"。

概念上至少区分：

```yaml
protagonist_curve:
  heroic_intensity: standard    # 作品风格 preset，不直接参与机制计算
  progression_rate: 1.0         # 成长节奏（可被 heroic_intensity preset 覆盖）
  fortune_bias: 1.0             # 幸运偏置（可被 heroic_intensity preset 覆盖）
  talent_leverage: 1.0          # 天赋复利（可被 heroic_intensity preset 覆盖）
  diagnostic_entry_percentile: 0.25    # Autoplay diagnostic reference
  diagnostic_mastery_percentile: 0.92  # Autoplay diagnostic reference
```

这些参数的含义不是直接修改结果，而是控制长期分布。

`heroic_intensity` 是作品风格 preset，**不直接参与机制计算**。它只为 `progression_rate`、`fortune_bias`、`talent_leverage` 提供默认配置；显式子参数可以覆盖 preset。

概念示例：

- **low**: 较低 progression / fortune / leverage 默认值 → 更残酷、慢热、接近硬核生存
- **standard**: 1.0 baseline → 明显是主角，但成功仍需要策略
- **high**: 较高 progression / fortune / leverage 默认值 → 典型爽文主角，优势建立和复利速度更快

#### heroic_intensity 作为 preset

整体主角光环强度。

它可以作为其它参数的总控旋钮。

- **较低**：更残酷、更慢热、更接近硬核生存
- **标准**：明显是主角，但成功仍需要策略
- **较高**：典型爽文主角，优势建立和复利速度明显更快
- **极高**：接近龙傲天 / 无双型成长

#### progression_rate

控制：

- 主角从当前竞争群体的普通位置成长到顶尖位置，大约需要经历多少有效决策、危机和成长节点。

它不能直接：

```text
每十回合 +20 percentile
```

而应该影响：

- 成长机会出现频率；
- 高价值挑战密度；
- 能力成熟速度；
- 资源积累速度；
- 解锁新策略空间的速度。

#### fortune_bias

控制主角遇见：

- 低概率
- 高上限
- 高风险
- 可改变长期轨迹

机会的相对频率。

Luck 不代表：

```text
事情自动成功。
```

而是：

```text
主角的一生中，值得下注的牌会比普通人多。
```

#### talent_leverage

控制主角独特能力能够产生多大的复利效果。

好的特殊天赋应该允许：

```text
小优势
↓
因为玩家正确使用
↓
形成第二个优势
↓
两个优势产生组合
↓
组合打开普通人不存在的路线
↓
路线继续扩大优势
```

因此天赋价值更接近：

```text
strategy multiplier
```

而不是：

```text
stat bonus
```

---




# 7. 反对“万能信息外挂”

类似：

- 感知隐藏物资；
- 感知敌人；
- 感知危险；
- 感知结构弱点；
- 看见隐藏信息；

这类能力不是绝对不能出现。

问题在于，如果每个世界最终都生成一个类似的“高级感知”，那么：

> 世界主题变了，主角玩法没有变。

这种能力很容易成为 LLM 的安全答案：

- 容易解释；
- 很万能；
- 不容易破坏剧情；
- 看起来有用；
- 但不会真正创造独特玩法。

因此，主角能力设计必须避免：

> **把“独特优势”默认等价为“比别人多知道一点”。**

可以允许信息优势，但它必须与某个世界机制深度绑定，并带来新的策略结构，而不是成为通用外挂。

---

# 8. 世界之间必须真正不同，而不是换皮

“冰川”“废土列车”“巨兽背部”“深海”“朋克都市”“星际矿船”之间的区别，不能只是：

```text
煤炭 → 电池
辐射 → 腐蚀
废铁 → 生物材料
怪物 → 机械怪物
```

真正不同的世界应该有不同的：

- 生存逻辑；
- 稀缺资源；
- 移动方式；
- 空间结构；
- 社会结构；
- 权力来源；
- 风险模型；
- 信息传播方式；
- 战斗逻辑；
- 交易体系；
- 成长路径；
- 时间压力；
- 关键不可逆机制。

### Engine 的原则

Engine 应该认识：

```text
resource_id
item_id
location
capability
cost
duration
risk
relationship
status
rule
```

但尽量不应该天然认识：

```text
scrap
fuel
food
medical_kit
basic_weapon
```

具体世界内容应该来自 world blueprint。

### 目标

**同一套 Engine，可以产生结构上真正不同的游戏，而不是同一个求生游戏套不同名词。**

### V2 补充：不只是资源名不能硬编码，玩法结构也不能硬编码

以前我们主要警惕：

```text
煤炭 → 电池
废铁 → 生物材料
怪物 → 机器人
```

这种名词换皮。

现在进一步明确：即使资源名完全配置化，只要所有世界仍然固定变成：

```text
固定基地
→ 离开基地
→ SEARCH
→ FIGHT
→ EXTRACT
→ 回基地
→ 升级
```

它仍然属于**结构性换皮**。

不同世界应当允许真正不同的：

```text
长期承载方式
移动方式
成长方式
风险循环
生产方式
社会关系结构
能力获得方式
世界时间结构
信息模型
组织结构
核心矛盾
```

### V2 补充：Engine 不应该认识主题

Engine 长期应该理解的是：

```text
Actor
Location
Resource
Action
Event
Time
Capability
Effect
Status
Relationship
Knowledge
Rule
```

而不是某个 WorldPack 的专有实体名、专有资源名、专有成长物名称、专有敌人种族名或专有仪式名。

### V2 补充：反主题硬编码不仅检查名词，也检查假设

一个 Feature 可能完全没有主题名，但仍然是硬编码。例如：

```text
Base 永远是固定地点
Encounter 永远只发生在 expedition
所有成长都有 player.level
所有升级都必然三选一
所有世界都有 day/night
所有能力都属于 player
所有秘密都对 player observation 可见
所有世界最终都靠 loot → upgrade
```

这些都是 **structural hard-coding**。

设计审查以后必须同时检查：

```text
theme vocabulary hard-coding
+
structural assumption hard-coding
```

---

# 9. 稀缺性创造意义

如果所有东西都可以随时获得，那么获得任何东西都不会令人兴奋。

重要资源必须具有至少一种稀缺性：

- 数量稀缺；
- 时间稀缺；
- 地点稀缺；
- 信息稀缺；
- 技术门槛；
- 身份门槛；
- 风险门槛；
- 社会关系门槛；
- 只能二选一；
- 一旦错过不会自动刷新。

因此：

> 奖励的价值不是由“稀有度颜色”决定，而是由玩家为了它必须付出的真实代价决定。

---

# 10. 成长的本质是“打开新的策略空间”

好的成长不是：

```text
昨天攻击力 20
今天攻击力 25
```

而是：

> 昨天不可能成立的计划，今天开始可能成立。

例如成长可以让玩家：

- 去以前去不了的区域；
- 和以前无法谈判的人谈判；
- 承担以前承受不了的风险；
- 使用新的资源链；
- 建立新的组织；
- 改变他人的行为；
- 发现世界更深层的规则；
- 同时处理更大的问题；
- 反过来影响环境本身。

### 最理想的成长反馈

玩家回头看十天前，会觉得：

> "当时的我面对这个问题，只能做那几个选择；现在我有完全不同的解法。"

### V2 补充：成长不应默认只有 player level

未来不同世界的成长可能存在：

```text
角色成长
生存承载体成长
技能熟练
知识成长
组织成长
生产能力成长
伙伴成长
社会身份成长
```

重点不是列系统，重点是：

> **成长应该被理解成某个长期能力空间发生变化。**

如果一个成长系统只能回答"数值变大了吗？"但不能回答"玩家现在多了什么以前不可行的方案？"，它仍然是薄弱成长。

### V2 补充：ProgressionTrack 作为设计语言

为了避免把 `player.level` 当成宇宙统一成长模型，可以引入术语：

> **ProgressionTrack：一个实体某一方面的长期成长轨迹。**

例如可能是：角色能力、Habitat、技能、伙伴、组织。

这不是要求所有世界必须有 ProgressionTrack class，而是未来避免单一成长模型时的抽象语言。

### V2 补充：ProgressionGate — 成长瓶颈应该能够进入世界

好的成长节点有时不应该 `EXP 满了 → 自动升级`，而可以：

```text
积累
→ 遇到瓶颈
→ 必须进入世界完成某件事
→ 承担风险 / 消耗机会
→ 解决 Gate
→ 打开下一阶段
```

它可以支持：升级资源、资格考试、仪式、危险探索、击败目标、获得外部对象、完成承诺。

核心价值：

> **把成长和世界行动重新连接起来。**

### V2 补充：永久 Build 选择

成长中最有价值的一类选择是**永久或高成本可逆的 Build 分化**。

真正的价值是：

```text
有限候选
+
机会成本
+
持久后果
+
策略分化
```

候选可以 2 个、3 个、N 个、或世界中自己寻找。

因此：**"Three-choice"不是设计价值本身。** 不要把"每一级三选一"写成项目宪法。

### V2 补充：Progression Attachment

某些成长不是系统直接送一个选项，而是玩家从世界中获得一个对象/印记/改造，并永久或长期绑定到自己的成长路线。

它可以具有：来源、兼容条件、机会成本、有限位置、永久性、能力变化。

泛化例子：义体、职业专精、魔法刻印、基因改造、传承、外部能力印记。

这防止未来把"固定 UI 三选一"误认为所有 Build 的唯一来源。

---

## 10.1 成长采用"相对阶层跃迁循环"

TheGreatNovel 的长期成长不应该只有一条无限向上的数值曲线。

它应该同时存在：

- **Absolute Power** - 绝对能力
- **Relative Standing** - 相对于当前竞争群体的位置

Absolute Power **单调不减**。它表示主角已经永久获得的能力上限、策略权限和成长成果；
后续剧情不能把这些成果回写成从未获得。

伤势、资源短缺、位置、维护、政治压力或环境可以限制主角当前能够调动的
**Effective Capacity**，也可以让 Relative Standing 回撤，但不能删除已经获得的
Absolute Power。这样既保留长期爽点，也让时间、风险和世界竞争继续产生约束。

但 Relative Standing 应该周期性重置。

一个典型成长周期可以是：

```text
进入一个新的竞争群体

P20–P30
↓
普通甚至偏弱
↓
P50–P65
↓
已经站稳脚跟
↓
P70–P80
↓
成为明显强者
↓
P90–P97
↓
成为当前环境顶尖人物
↓
进入更大的世界
↓
在新竞争群体中重新约 P20–P30
```

这里的 percentile 是设计指标，不是强制剧情脚本。

系统不能因为：

```text
"现在剧情要求主角达到 P75。"
```

就直接修改世界状态或让竞争者变弱。

正确方式是通过：

- 世界层级；
- 新区域；
- 新组织；
- 新竞争者；
- 更复杂的资源体系；
- 更高的技术 / 能力门槛；
- 更高的政治和社会门槛；

自然产生新的 reference group。

### Cohort Stability Principle

Cohort 必须是世界中真实存在、可解释、相对稳定的参照群体。不得为了让 protagonist percentile 上升或下降而临时改变 reference group。

Cohort 的变化必须来自真实世界事件，例如：

- 进入新区域；
- 加入更高层组织；
- 获得新的竞争资格；
- 身份或社会层级变化；
- 接触一个真实存在的更高层级网络。

Percentile 是设计 / Autoplay measurement，不是 authoritative GameState target。Engine 不允许根据 percentile 不足而偷偷 buff 主角。

### P90+ 作为 pacing/diagnostic signal

P90+ 是 pacing / diagnostic signal，不是自动 tier transition trigger。

新的 cohort 必须通过世界内因果链产生，不能写：

```python
if percentile >= 0.90:
    unlock_next_tier()
```

只有当世界结构发生真实变化（新区域开放、资格认证完成、社会地位转变等），才允许自然过渡到更高层级的 cohort。

### Relative Standing 的回撤原则

Relative Standing 不要求单调上升。主角可以因为失败、伤势、政治冲突、资源损失而短期回撤，但长期成长包络应该具有明显正向漂移。

示例：

```text
P25 → P38 → P57 → P48 → P63 → P76 → P71 → P90+
```

这种波动：

- 增加故事真实性；
- 创造真正的紧张感；
- 让玩家有机会反思和调整策略；
- 符合"成长需要付出代价"的设计原则。

### Future Dimensions

理论上 Relative Standing 可以由多个维度构成，例如：

- Combat (战斗实力)
- Resource (资源控制)
- Social (社会资本)
- Influence (影响力)
- Knowledge (知识深度)

每个维度可以有独立的 percentile track。

但在当前阶段不要实现 Engine 字段支持。保持简单，只使用单一的综合 percentile 用于设计和 Autoplay monitoring。

---


# 11. 强奖励必须来自玩家理解并利用系统

爽点不应该主要来自：

> 系统突然送你一个 SSS 宝箱。

更高级的爽感来自：

1. 玩家观察到规律；
2. 玩家形成判断；
3. 玩家承担风险；
4. 玩家设计策略；
5. 世界按规则运行；
6. 策略成功；
7. 玩家获得远超普通人的收益。

这种爽感会让玩家觉得：

> **不是作者赏给我的，是我自己赢来的。**

因此 TheGreatNovel 应该奖励：

- 推理；
- 规划；
- 风险管理；
- 信息利用；
- 资源组合；
- 社会博弈；
- 长期布局；
- 对世界规律的理解。

---

# 12. 风险必须可以被理解，而不是纯随机惩罚

游戏可以残酷。

甚至可以非常残酷。

但玩家应该逐渐能够理解：

> 为什么我失败了？

坏体验：

```text
你选择探索。
随机判定失败。
你重伤。
```

更好的体验：

```text
你知道暴雨正在逼近。
你知道这片区域最近有大型生物活动。
你知道自己只有半套防护装备。

你仍然选择进去。

结果出了问题。
```

失败应该尽可能是：

- 可预见的；
- 可学习的；
- 可归因的；
- 能影响下次决策的。

### 允许未知

世界当然应该存在未知危险。

但未知本身也应该是一种可以管理的风险，而不是作者随时使用的惩罚按钮。

---

# 13. 信息本身也是资源

信息不应该只是 exposition。

真正有价值的信息应该能够：

- 改变行动优先级；
- 改变资源价格；
- 改变风险判断；
- 打开新的路线；
- 关闭旧路线；
- 改变对 NPC 的信任；
- 让玩家提前布局；
- 成为可交易的资产。

玩家获得某条信息以后，应该产生：

> "这意味着我要重新考虑我的计划。"

而不是：

> "哦，又知道了一点世界观设定。"

### V2 补充：World Truth ≠ Actor Knowledge

世界知道某事实为真，不代表 Player、NPC-A、NPC-B、Narrator 当前视角都知道。

未来系统应该能够支持：

```text
Fact X is true

Player: knows X
NPC A: knows X
NPC B: does not know X
NPC C: believes incorrect Y
```

### V2 补充：知识边界是角色真实性的一部分

如果一个角色使用了自己不可能知道的信息，这和 NPC 瞬移、凭空获得资源一样，是世界一致性破坏。

LLM 很容易因为拥有完整上下文而泄漏秘密、隐藏身份、其他 NPC 计划、未来事件。

因此：

> **信息权限必须像位置、资源、伤势一样受到世界规则约束。**

概念层级：

```text
World Truth
↓
Knowledge / Visibility
↓
Observation（角色有资格知道的世界投影）
```

玩家和 Agent 看到的不应该是 raw GameState dump，而是角色有资格知道的世界投影。

这使得秘密、调查、欺骗、信息优势和不确定性都能真正成立。

---

# 14. NPC 必须有自己的欲望，而不是剧情工具

一个真正活着的 NPC 应该至少有：

```text
目标
需求
资源
能力
关系
恐惧
信息
计划
当前行动
```

NPC 不应该只是：

- 发任务；
- 解释世界观；
- 给玩家奖励；
- 等玩家触发剧情。

NPC 应该会：

- 拒绝玩家；
- 欺骗玩家；
- 利用玩家；
- 和玩家竞争；
- 因为自身利益改变立场；
- 记住玩家之前做过的事；
- 在没有玩家的情况下继续行动。

### 最重要的结果

玩家面对 NPC 时应该产生：

> "他接下来会做什么？"

而不只是：

> "这个 NPC 能给我什么任务？"

### V2 补充：Named Actor 与 Aggregate Population 是不同层级

有些世界需要具体导师、队友、竞争者、父母、仇敌、长期盟友——他们必须有 persistent identity。

另一些背景人口可以继续 aggregate。不要为了"世界活着"就要求模拟每个路人。

设计目标：

```text
重要人物 individually persistent
+
非重要人口可以 aggregate
```

---

# 15. 关系不是好感度条，而是博弈结构

人际关系不能只简化成：

```text
好感 +5
好感 -10
```

更重要的是：

- 信任；
- 利益一致程度；
- 依赖关系；
- 债务；
- 恐惧；
- 秘密；
- 身份认同；
- 共同敌人；
- 资源控制；
- 承诺；
- 背叛成本。

一个 NPC 可以：

> 不喜欢你，但必须与你合作。

也可以：

> 很喜欢你，但在关键利益上仍然背叛你。

这比单一好感度更接近真正的社会模拟。

### V2 补充：关系可以产生能力

某些 Capability / 行动可能来自关系本身：

```text
Actor A + Actor B + relationship / coordination
→ Action C becomes possible
```

关系因此不只是对话 modifier，也可以改变：行动空间、风险、信息流、联合能力、资源获取。

但不要把所有关系都强制复杂化。

---

# 16. 承诺必须真实存在

玩家做出重大承诺以后，系统应该记住它。

例如：

- 答应帮助某人；
- 加入某个组织；
- 接受一个危险任务；
- 公开站队；
- 透露秘密；
- 签订交易；
- 选择长期建设方向。

这些行为应该影响未来选择。

### 原则

**没有约束力的承诺，只是对白。**

commitment 应该能够：

- 占用未来时间；
- 消耗资源；
- 影响关系；
- 关闭某些路线；
- 创造 deadline；
- 在违约时产生真实后果。

### V2 补充：长期身份也是结构化后果

加入组织、获得职业资格、成为导师/学徒、公开站队、成为某地居民、取得某种社会身份——应该能够影响：权限、NPC 态度、可进入地点、可获得资源、可接受行动、责任、敌对关系。

设计原则：

> **成长可以改变社会位置，而不仅仅改变战斗力。**

---

# 17. 不可逆性是故事重量的重要来源

如果所有选择都可以重来，所有路线都可以补做，所有 NPC 都永远等待，那么整个世界会变轻。

适度存在：

- 死亡；
- 错过；
- 关系破裂；
- 身份暴露；
- 阵营敌对；
- 资源永久消耗；
- 地点毁灭；
- 技术路线分叉；
- 无法同时得到的奖励；

才能让玩家真正认真思考。

### 目标不是折磨玩家

而是让：

> “我决定这么做。”

这句话拥有重量。

---

# 18. 玩家可以提出任何行动，但世界不保证配合

TheGreatNovel 不应该被固定选项限制成传统文字冒险。

玩家应该可以自由输入：

> “我不选 A/B/C，我想先制造噪音把怪物引走，再从后门进去。”

这种创造性应该受到鼓励。

但“自由输入”不能意味着：

> 玩家说什么，LLM 就让什么成功。

系统需要判断：

- 是否可能；
- 需要多久；
- 需要什么资源；
- 有什么风险；
- 是否和之前行为冲突；
- 会引发哪些世界反应。

### 核心公式

```text
自由度 ≠ 无限制

自由度 = 可以尝试任何合理行动
         +
         世界按照统一规则回应
```

### V2 补充：自由行动需要 Action Semantics

自由行动真正需要的是 Action semantics，而不是 LLM prose compliance。

玩家说"我想诱敌、绕路、伪装、利用环境"——如果世界规则允许，应该能够被解释为已有 Capability / Cost / Time / Risk / Effect，或者明确拒绝。

长期目标不是让 LLM"听起来合理，所以成功"，而是：

> **"尝试被翻译成世界中的因果行动，然后由规则裁决。"**

---

# 19. LLM 负责创造可能性，不负责随意修改规则

LLM 最适合：

- 生成世界内容；
- 生成角色；
- 推演动机；
- 提出行动可能；
- 生成局部事件；
- 将状态写成小说；
- 根据已有状态进行丰富表达。

但它不应该拥有无限制的“上帝权限”。

特别不应该随意：

- 创造玩家突然拥有的资源；
- 忘记之前的伤势；
- 让 NPC 瞬移；
- 修改世界规则；
- 让已经错过的机会重新出现；
- 无成本解决冲突；
- 临时给主角增加能力；
- 为了剧情需要让敌人突然变弱。

### 理想分工

```text
LLM：
提出、解释、描写、推演

Engine：
验证、记账、限制、推进、裁决
```

### V2 补充：LLM 创造 candidate possibility，不决定结果

LLM 可以创造 candidate possibility，但不能自己决定该 possibility 是否合法、是否成功、产生多少资源、造成多少伤害、需要多少时间、是否改变持久状态。

如果 LLM 提议的新内容将影响未来玩法，必须先结构化、验证、进入正式状态/事件，才能成为事实。

---

# 20. 结构化状态是事实，小说文本是表现

同一件事情应优先存在于结构化状态中。

例如不是只写：

> “你的左腿伤得很重。”

而是同时有：

```yaml
injuries:
  left_leg:
    severity: serious
    mobility_penalty: 0.4
    untreated_hours: 6
```

小说层再根据这些事实进行表达。

### 原则

如果一个事实会影响未来游戏，就不能只存在于 prose 中。

这包括：

- 伤势；
- 承诺；
- 关系；
- 位置；
- 时间；
- 资源；
- 已知信息；
- 世界事件；
- 阵营；
- 长期计划；
- 装备状态；
- NPC 计划。

---

# 21. 系统复杂度必须服务于玩家可感知的后果

TheGreatNovel 可以有非常复杂的底层状态。

但复杂本身没有价值。

如果增加一个字段、Agent 或规则以后，玩家永远感知不到它造成的差异，那么它很可能只是技术复杂度。

任何复杂机制最好最终回答：

> **它会让玩家做出什么不同的决定？**

如果答案是"不会"，就应该重新考虑是否需要。

### V2 补充：无意义抽象同样是无意义复杂度

即使一个 abstraction 很优雅，如果当前只有一个 caller、一个世界、一个实际用途，就要问：它现在真的需要进入公共层吗？

复杂度不仅包括 runtime feature，也包括：抽象层、registry、interface、plugin boundary、generic schema。

> **TGN 必须同时抵抗 Hard-coding 与 Speculative Generalization。**

---

# 22. 不追求每一回合都有大事件

真正有世界感的节奏不应该是：

```text
事件
事件
事件
反转
宝箱
战斗
重大秘密
```

适度允许：

- 准备；
- 观察；
- 等待；
- 恢复；
- 日常互动；
- 小规模资源管理；
- 没有立即回报的长期投资。

因为低潮能够让高潮有意义。

### 但“平静”不能等于“世界停止”

即使这一回合没有重大剧情，底层世界仍然应该继续演化。

---

# 23. 爽点应该具有层级

理想的上瘾循环不是单一奖励重复。

应该存在多个时间尺度：

## 秒级 / 单回合

- 一个危险判断正确；
- 找到一个有用物品；
- 一次谈判成功；
- 避免一个损失。

## 数回合

- 完成一次探索；
- 解决资源瓶颈；
- 赢得某个 NPC 信任；
- 拼出一条信息链。

## 数天

- 建立稳定资源来源；
- 解锁新区域；
- 完成一个成长节点；
- 建立自己的优势。

## 长周期

- 改变营地结构；
- 建立组织；
- 形成自己的势力；
- 掌握世界规则；
- 改变整个区域的力量平衡。

## 超长周期 / 阶层跃迁

- 从当前群体中的普通成员成长为核心成员；
- 从追随规则的人变成能够影响规则的人；
- 从当前区域的普通竞争者进入顶尖集团；
- 超越曾经无法对抗的人；
- 回看旧区域时明确感受到自己的成长；
- 发现比当前环境更大的竞争层级；
- 带着旧世界积累进入新世界；
- 在新的强者群体中重新开始向上攀升。

长期爽点的核心循环应该是：

```text
陌生
→ 生存
→ 理解
→ 建立优势
→ 优势复利
→ 成为强者
→ 成为顶尖
→ 世界扩大
→ 再次陌生
```

玩家应该始终感觉：

> 眼前有东西值得做，远处也有东西值得期待。

---

# 24. 好奇心是最重要的长期驱动力之一

一个好的世界不会一次性解释完自己。

它应该不断制造：

```text
发现
→ 新问题
→ 局部答案
→ 更大的问题
```

例如：

> 这里为什么没有动物？

找到答案以后：

> 原来不是没有动物，而是它们都在躲某种东西。

继续调查：

> 那个东西到底是什么？

### 原则

世界秘密不能只是 lore。

它应该逐渐与：

- 生存；
- 资源；
- 主角能力；
- NPC；
- 势力；
- 长期成长；

发生实际连接。

---

# 25. 不确定性必须存在

如果玩家始终知道：

- 每个选择的准确收益；
- 每个敌人的准确战力；
- 每个 NPC 的真实意图；
- 每个事件的成功率；

游戏会迅速变成计算题。

需要保留：

- 模糊信息；
- 错误信息；
- 不完整信息；
- 主观判断；
- 敌人隐藏能力；
- NPC 私人目的。

但这些不确定性应该可以通过：

- 调查；
- 观察；
- 社交；
- 经验；
- 能力；
- 付出资源；

逐渐降低。

### V2 补充：Information Model 可以不同

不同世界可以对玩家提供完全不同的信息精度：

```text
系统型世界：精确数值
求生型世界：模糊风险
写实型世界：几乎无 HUD 数值
```

因此 Engine / Design 不应该假定玩家永远知道敌人的准确 HP、准确成功率、升级准确收益。

Information Model 应当是世界结构的一部分。

---

# 26. 最优策略不能永久固定

如果玩家发现：

```text
每天出去探索
→ 搜资源
→ 回家
→ 升级
```

就是永久最优解，那么游戏很快会被解完。

世界需要不断改变问题。

例如：

- 资源逐渐枯竭；
- 玩家变强以后吸引更强竞争者；
- 营地人口增长创造新的需求；
- 原来的安全区域变危险；
- 某种资源从核心资源变成廉价资源；
- 社会与政治问题开始超过纯生存问题。
世界层级升级也是打破永久最优策略的重要方式。

当主角已经接近当前环境顶层，并且通过真实世界因果开始接触更高层级环境时，过去形成的强势策略不应该完全失效，但在新的环境中其边际优势可能自然下降。

例如：

在小营地里：
掌握稳定食物来源 = 巨大权力

进入大型城市后：
稳定食物只是最基础的生存条件
在区域聚居地：
优秀战斗能力 = 顶尖人物

进入更高层组织后：
单人战斗力只是进入竞争的门票

因此：

成长不是把旧问题无限放大，而是让旧问题逐渐变成新问题的基础条件。

### V2 补充：问题层级随成长变化

玩家解决旧问题以后，旧问题应该消失、自动化、变得廉价、被委托或进入背景维护，然后产生新的高层问题。

抽象循环：

```text
活下来 → 稳定生存 → 释放时间 → 提高生产/能力 → 形成关系 → 承担责任 → 组织与社会冲突 → 影响更大范围
```

重要：不要把这个 progression ladder 写成所有游戏强制路线。它只是说明：

> 长周期玩法应该改变问题性质，而不是只增大数字。

### V2 补充：Automation 的真正价值是释放行动权

自动化不应该只是 `production +20%`。更重要的是：原本玩家必须花 3 小时亲自完成，现在系统/设施/NPC 可以处理，玩家获得 3 小时处理更高层问题。

这直接连接 Section 3"时间是货币"：

> **自动化的本质之一，是把时间重新交还给玩家。**

被交还的时间不会让长期选择消失，而会改变稀缺性结构：旧资源变得廉价以后，玩家要用
时间处理更高层的机会窗口、组织责任、关系承诺、维护负担、信息与战略冲突。好的长周期
玩法不是永久重复同一份生存劳动，而是让“什么值得花时间”随着世界和主角共同变化。

### V2 补充：Upkeep / 持续代价

强大的长期资产可以伴随长期负担（食物、能源、维护、工资、空间、注意力、政治成本）。

设计价值：

> **成长不应该无限免费叠加优势。**

但这是可选机制，不要求所有能力都必须 upkeep。

---

# 27. 自动游玩不是附属测试，而是设计体检

Autoplay 的意义不只是检查：

> “代码有没有 crash。”

更重要的是暴露长期机制问题，例如：

- 是否出现无限资源；
- 是否出现固定最优策略；
- NPC 是否失去活性；
- 世界是否停滞；
- 成长是否过快；
- 玩家是否可以一直全选；
- 某种天赋是否压倒一切；
- 某种行动是否永远收益最高；
- 状态是否无限膨胀；
- 世界是否最终变成重复循环。

### 因此 autoplay 应该回答

> **这个世界运行 50、100、300 回合以后，还像一个有意思的游戏吗？**

Autoplay 不仅应该监控资源、策略和状态，也应该监控主角长期成长曲线。

至少记录：

```text
current_cohort
relative_percentile
absolute_capability
cohort_entry_percentile
cohort_peak_percentile
time_to_P50
time_to_P75
time_to_P90
number_of_tier_transitions
progression_stall_duration
```

需要检测：

```text
主角长期停留在 P20–P40
→ 爽点不足 / 主角光环过弱

主角几回合直接 P99
→ 成长过快 / 缺少过程

主角永久 P99
→ 世界没有继续扩大

每次换地图所有旧优势全部失效
→ 伪成长 / 数值重置

主角无需做正确决策也自动上升
→ 主角光环变成剧情保护
```

理想状态不是固定数字，而是能够形成反复的：

```text
P25 → P60 → P75 → P90+ → 新 cohort → P25–P35 → P60 → P75 → P90+ → ...
```

同时 Absolute Power 保持单调不减，并在长期出现玩家可感知的上升。

### V2 补充：Autoplay 也应检查兼容性坍缩

除了无限资源、固定最优策略、循环之外，还应该检查：

**Strategy Collapse** — 所有 Agent 是否最终都采用同一动作循环？

**World Structural Collapse** — 不同 WorldPack 是否最终都退化为 `search → fight → return → upgrade`？

**Progression Collapse** — 不同成长路线是否最终只是数字高低不同？

**Social Collapse** — NPC / 关系系统是否最终只提供奖励和任务？

---

# 28. 可复现性很重要

LLM 游戏可以有随机性，但机制调试必须尽可能可复现。

至少关键系统应该支持：

```text
seed
deterministic simulation
event log
state diff
action trace
```

否则：

> 同一个 bug 每次都换一种表现，长期很难真正修好。

随机性应该创造体验差异，而不能掩盖规则错误。

---

# 29. 创建世界必须像编译程序一样严格

World Blueprint 不是一段"灵感文字"。

它实际上是：

> **这个世界的可执行规则定义。**

因此创建世界应该经历严格验证。

不合法的世界应该：

> 立即失败，并明确告诉系统哪里不合法。

而不是运行十回合以后才发现：

- 缺关键资源；
- NPC 没行动模型（仅当 Named Actor 功能启用时）；
- 某个字段不存在；
- 世界规则互相矛盾；
- 某个模板偷偷 fallback 到废土默认值。

### V2 补充：验证是严格的，物化是惰性的

> **Validation is strict; materialization is lazy.**

严格验证不等于提前生成整个宇宙。系统应当在**当前所需的可玩契约**无效时立即失败，但不应要求所有未来 NPC、区域、组织、配方、敌人、事件、地点在第一个决策之前就全部存在。

推荐概念管线：

```text
World Request / WorldPack Draft
        ↓
Parse
        ↓
Schema Validate
        ↓
Semantic Validate
        ↓
Normalize / Bind deterministic IDs
        ↓
Bootstrap Minimal Playable World
        ↓
Bootstrap Smoke Test
        ↓
Create Campaign
        ↓
PLAYABLE NOW
        ↓
Lazy Materialization when new content becomes relevant
        ↓
Validate newly materialized content before it becomes world truth
```

验证遵循已启用的 Feature 契约。不要求未启用的 Feature 提供定义。

---

# 30. Engine 不应该偷偷替 LLM 补一个“默认世界”

Fallback 有时候可以提高鲁棒性，但对于世界定义，过度 fallback 会掩盖问题。

例如：

```text
世界没定义医疗资源
→ Engine 自动补 medical_kit
```

虽然游戏能继续跑，但它破坏了世界纯度。

更理想的行为是：

```text
ERROR:
world has injury mechanics
but no valid recovery pathway is defined
```

### 原则

**宁可在创建阶段明确失败，也不要运行一个偷偷被默认模板污染的世界。**

---

# 31. 小说感不能通过牺牲规则获得

为了让章节“更精彩”，不能随意：

- 插入没有来源的大事件；
- 强行制造巧合；
- 给主角送钱；
- 让敌人犯蠢；
- 临时新增关键人物；
- 忽略时间和距离；
- 无视之前的承诺。

真正高级的小说感应该来自：

> **规则产生复杂局面，LLM 发现其中的戏剧性。**

而不是：

> LLM 需要戏剧性，所以修改规则。
“不能强行制造巧合”不等于主角不能幸运。

TheGreatNovel 可以明确存在主角幸运偏置。

区别在于：

**错误：**

```text
剧情需要主角赢
→ 临时制造巧合
```

**正确：**

```text
世界生成事件
↓
根据预先声明的 protagonist fortune bias
提高某些高价值机会进入候选事件池的概率
↓
由 deterministic seed 得到具体结果
↓
机会正常进入世界
↓
玩家仍然必须识别、选择、承担代价并利用它
```

因此：

主角可以比别人幸运，但世界不能为了当前剧情临时作弊。

主角光环本身也是规则的一部分。

只要它：

- 预先定义；
- 可以结构化记录；
- 可以由 seed 重放；
- 不在结果产生以后偷偷修改；
- 不取消玩家决策；

它就不违反世界真实性。

---



# 32. 游戏感不能通过牺牲小说感获得

反过来也不能把系统变成纯表格。

玩家不应该每回合只看到：

```text
HP -5
Food -2
Trust +3
Time +2h
```

这些是底层事实，但表现层应该让玩家体验到：

- 氛围；
- 人物；
- 紧张；
- 犹豫；
- 后果；
- 关系变化；
- 世界细节。

### 理想结构

```text
底层：严格、结构化、可验证
上层：自然、文学化、有情绪、有节奏
```

---

# 33. 最终目标不是“无限内容”，而是“无限因果组合”

LLM 很容易生成无限文本。

但无限文本本身并不等于无限游戏。

真正追求的应该是：

> 一套有限但深度足够的规则，在不同玩家行为、世界状态、NPC 行为和随机事件组合下，产生大量不同的故事。

也就是：

```text
不是 Content Explosion
而是 Causality Explosion
```

这会让不同存档真正不同。

---

# 34. TheGreatNovel 最应该保护的玩家感受

如果设计成功，玩家应该经常产生下面这些想法：

### “我得想一下。”

说明选择有代价。

### “如果我去做这个，那个可能就没了。”

说明机会成本真实存在。

### “原来他这几天一直在做这个。”

说明 NPC 真正在世界中生活。

### “早知道当时……”

说明历史具有因果性和不可逆性。

### “等等，我好像发现了这个世界的规律。”

说明系统可以被理解。

### “这个能力还能这么用？”

说明主角能力创造策略空间。

### “这是我自己想出来的办法。”

说明自由行动和系统规则成功结合。

### “这个世界居然没等我。”

说明世界不是舞台布景。

### “现在的我已经不是刚开始那个我了。”

说明成长改变了玩法。

### “再玩一天看看会发生什么。”

这是最终要制造的长期吸引力。

---

# 35. 明确反对的设计方向

以下情况应该被视为设计警报。

## 35.1 伪选择

```text
A / B / C 最后都能全部做
```

---

## 35.2 换皮世界

```text
所有世界最终都是：
搜资源 → 打怪 → 回基地 → 升级
```

---

## 35.3 万能感知天赋

```text
主角特殊性 = 能看到别人看不到的东西
```

每个世界反复出现。

---

## 35.4 纯数值成长

```text
更强 = 数字越来越高
```

但策略没有变化。

---

## 35.5 NPC 背景板

```text
NPC 只有玩家出现时才存在
```

---

## 35.6 LLM 上帝模式

```text
为了剧情需要随时创造资源、能力、人物和规则
```

---

## 35.7 无代价自由

```text
玩家提出什么都能做，
所有行动都可以组合，
没有时间、风险和机会成本。
```

---

## 35.8 世界自动等玩家

```text
任务永不过期
NPC 永远原地等
资源永远没人拿
Boss 永远不行动
```

---

## 35.9 无意义复杂度

```text
后台有很多系统，
但它们不会改变玩家的任何决定。
```

---

## 35.10 Prompt 修补 Engine 问题

如果一个规则必须靠反复提醒 LLM：

> "请记得不要这样……"

才能成立，那么这个规则大概率应该进入 Engine。

---

## 35.11 结构性硬编码

```text
所有世界都有固定基地
所有 encounter 都属于 expedition
所有成长都基于 player.level
所有升级都三选一
所有世界都有 day/night
```

---

## 35.12 为未来建立万能框架

```text
只有一个真实用例，
却提前创建大型 Plugin/Effect/Progression framework
```

---

## 35.13 玩家全知

```text
系统知道什么
→ 玩家也自动知道什么
```

---

## 35.14 NPC 上帝视角

NPC 使用了自己从未获得的信息。

---

## 35.15 解决旧问题以后仍然要求玩家重复劳动

```text
已经建立自动生产能力
但玩家仍被迫每天重复同样采集点击
```

---

## 35.16 题材变化但策略不变化

世界表面完全不同，但 autoplay 的最优策略完全一样。

---

# 36. 功能设计的五问检查法

以后增加任何机制之前，可以问：

### 1. 它会产生新的选择吗？

如果不会，它可能只是内容。

### 2. 它会让某些选择变得不能同时拥有吗？

如果会，它开始产生策略。

### 3. 玩家能理解它造成的后果吗？

如果不能，它可能只是随机惩罚。

### 4. NPC / 世界也会受到这条规则约束吗？

如果不会，它可能是玩家专属剧本机制。

### 5. 它会在 50 回合以后仍然有意义吗？

如果不会，需要考虑长期演化。

### V2 泛化检查

### 6. 这条规则属于世界事实，还是某个题材内容？

### 7. 换一个结构完全不同的世界，它仍然成立吗？

### 8. 如果不成立，它应该属于 WorldPack / optional feature 吗？

### 9. 我们是不是只有一个真实需求，却已经建立了通用框架？

### 10. 它改变的是策略空间，还是只增加状态复杂度？

---

# 37. 代码审查时的价值观检查

以后 review GitHub 代码，不只检查：

```text
有没有 bug？
```

还应该检查：

```text
这个实现有没有偷偷破坏游戏价值观？
```

重点关注：

### 时间

- 行动是否正确消耗时间？
- 世界是否同步推进？
- 有没有“零耗时但推进世界”的异常？

### 选择

- 多行动组合是否被正确验证？
- commitment 是否有效？
- deadline / opportunity window 是否真实存在？

### 世界纯度

- Engine 是否 hard-code 某个世界的资源？
- 是否存在隐形 fallback？
- 世界是否能够真正使用完全不同的机制？

### NPC

- NPC 是否独立行动？
- 是否存在瞬移？
- 是否因为玩家不观察而停止？

### 状态

- 影响未来的事实是否结构化？
- LLM 是否可能绕过状态系统？

### 长周期

- history 是否无限增长？
- 是否存在稳定 exploit？
- 是否能够 deterministic replay？

### V2 新增：Theme Hard-coding

- 是否出现具体题材 vocabulary 进入 Core？
- 是否出现 world_type / genre 类型的大量 if/else？

### V2 新增：Structural Hard-coding

- 是否假设基地一定固定？
- 是否假设 encounter 一定属于某个 loop？
- 是否假设所有成长结构相同？
- 是否假设所有能力属于玩家？

### V2 新增：Knowledge Boundary

- Observation 是否泄漏隐藏事实？
- NPC 是否拥有不合理知识？
- Narrator 是否把 engine-private truth 暴露给角色？

### V2 新增：Premature Abstraction

- 新 abstraction 有几个真实 caller？
- 是不是为"以后可能需要"创建？
- 是否有更小的 local solution？

---

# 38. 推荐的项目北极星指标

不应该只看：

- 生成文本长度；
- 每分钟 token；
- 世界数量；
- Prompt 数量；
- NPC 数量。

更值得观察的是：

### Choice Conflict Rate

玩家面对的有效选择中，有多少不能全部兼得。

### Consequence Persistence

一个决定在多少回合以后仍然能够影响世界。

### Strategy Diversity

不同 autoplay agent 是否走出不同的有效路线。

### World Divergence

不同 world blueprint 是否真的产生不同的最优策略。

### NPC Independence

重要世界事件中，有多少不是由玩家直接触发。

### Player-Caused State Change

世界变化中，有多少能够追溯到玩家过去的行为。

### Missed Opportunity Rate

是否真实存在玩家因为选择其他路线而错过的内容。

### Mechanic Discovery

玩家是否能够逐渐发现并利用世界规律。

### Long-Horizon Novelty

50 / 100 / 300 turn 后是否仍出现新的决策结构，而不只是重复资源循环。

### V2 新增候选指标

**Structural World Divergence** — 不同 WorldPack 是否产生不同的核心行动循环和长期策略。

**Capability Diversity** — 不同成长是否真正打开不同解法，而不是数字差。

**Knowledge Integrity** — 角色是否只使用自己合理知道的信息。

**Problem-Layer Transition** — 50 / 100 / 300 turn 后，玩家是否仍然解决同一种问题。

**Automation Leverage** — 成长是否真正减少低层重复劳动并释放时间。

**Theme Leakage** — Core 中是否逐步积累 WorldPack-specific vocabulary / assumptions。

这些是设计观测方向，不必要求目前代码全部实现。

---

# 39. 最终的系统哲学

TheGreatNovel 最终可以归纳成八句话（原有六条系统哲学，加上 V2 两条扩展原则）。

## 规则先于剧情

剧情应该从规则运行中长出来。

## 选择意味着放弃

没有机会成本，就没有真正的选择。

## 世界不会等玩家

时间流动，其他人也在生活。

## 成长改变可能性

不是简单让数字越来越大。

## LLM 创造表达，Engine 守护现实

一个负责想象，一个负责一致性。

## 玩家书写的不是文本，而是因果

小说只是这些因果最后呈现出来的形式。

## V2 新增：信息属于知道它的人

World Truth 不等于角色全知。秘密、调查、误解和欺骗需要真实知识边界。

## V2 新增：不为题材写 Engine

Engine 维护跨世界因果，具体题材属于 WorldPack 和经过真实需求证明的 Feature。

---

# 40. 项目宣言

> **我们想做的不是一个会写小说的聊天机器人。**
>
> **我们想做的是一个能够持续运行的世界。**
>
> 玩家进入其中，只拥有有限的时间、资源、信息和能力。
>
> 世界不会为了玩家暂停，其他人拥有自己的目标，机会会出现，也会消失。
>
> 玩家可以尝试任何合理的事情，但每个行动都必须接受同一套世界规则的裁决。
>
> 好的决定会产生优势，错误判断会留下痕迹，成长会真正改变解决问题的方法。
>
> LLM 的职责不是替玩家制造胜利，而是把规则运行后产生的复杂经历，变成值得继续读下去的故事。
>
> **最终，我们希望玩家不是在"选择下一段文字"，而是在一个真实运转的世界里留下自己的历史。**

我们也不希望第一种成功世界成为下一种世界的牢笼。TGN 应允许完全不同的世界拥有不同的生存方式、成长方式、社会结构与长期目标，而不要求它们服从同一套题材模板。

---

# 41. 最短版本：以后做设计时只记住这 8 条

1. **世界先运行，小说后书写。**
2. **每个重要选择都应该意味着放弃其他东西。**
3. **时间流逝时，整个世界都获得行动权。**
4. **NPC 和其他玩家即使不被观察，也必须继续生活。**
5. **主角能力要改变策略空间，而不是只增加数值。**
6. **不同世界必须拥有不同的生存与成长逻辑，而不是换皮。**
7. **LLM 可以创造可能性，但不能随意篡改规则和状态。**
8. **玩家最终获得的爽感，应来自理解世界、做出判断并赢得结果。**

### V2 额外记住的 4 条架构价值

9. **世界真实存在什么，不代表每个角色都知道什么。**
10. **不要把第一个世界的玩法结构写成 Engine 的宇宙规则。**
11. **抽象必须由真实需求提炼，不能为了"以后可能需要"提前造万能框架。**
12. **Feature 可以是可选的，但一旦启用，就必须成为可验证、可重放的真实世界规则。**

---

# 42. V2：反主题硬编码与结构性硬编码

本次修订通过多个"生存经济型"和"角色成长社会型"世界进行兼容性压力测试，得到核心结论：

TheGreatNovel 不只是要避免不同生存主题换皮。它还必须避免某一种基地结构、某一种成长方式、某一种战斗方式、某一种社会结构、某一种信息模型、某一种长期游戏循环偷偷成为 Engine 的默认世界观。

设计审查必须同时检查 theme vocabulary hard-coding 和 structural assumption hard-coding。

---

# 43. V2：抽象必须被真实需求挣出来

错误路线 A：第一个世界需要木筏 → Core 直接写 BoatSystem。

错误路线 B：未来可能存在一百种载具 → 现在建立 UniversalHabitatPluginFramework。

两者都错误。正确路线：

```text
实现第一个真实 vertical slice
↓
实现第二个结构不同的真实需求
↓
观察真正重复的因果结构
↓
提取最小公共抽象
```

> **Abstraction Must Be Earned.**

Feature Module 是概念边界，不意味着现在需要建立动态插件框架。明确禁止把设计价值误读成：现在去写 PluginManager、DynamicModuleLoader、DependencyResolver、UniversalRegistry。

---

# 44. V2：Core / Feature Module / WorldPack 的责任边界

长期概念上：

```text
Core：尽量维护跨世界稳定的因果规则
↓
Feature Modules：多个世界可能复用但不是所有世界都需要
↓
WorldPack：具体题材、资源、能力内容、组织内容、敌人内容、阶段参数
↓
Narrative / LLM Edge：提出 / 解释 / 描写 / 玩家决策 / 未来角色规划
```

这是责任边界，不是现在必须存在的 package hierarchy。

**Optional Does Not Mean Unimportant** — 如果 WorldPack 启用了某个 Feature（如 Market），就不能只是 Narrator 说"市场价格上涨了"而实际状态没变化。启用以后仍然必须接受 State、Event、Rule、Replay 约束。

> **Optional Feature ≠ Soft Fiction。**

---

# 45. V2：Compatibility Pressure Test

不是要求现在实现所有世界。而是在设计一个"通用"概念时问：

> 如果换成一个结构完全不同的世界，这个概念还成立吗？

至少使用三种压力类型思考：

**Type A — Survival / Expedition**：资源、机会成本、风险、撤离、环境。

**Type B — Mobile Habitat / Economy**：移动生存承载体、生产、自动化、维护、市场、聚居地、世界尺度增长。

**Type C — Character Progression / Social**：多轨成长、成长瓶颈、永久 Build、训练、导师、NPC、秘密、团队、组织、社会身份。

重要：这些只是兼容性压力类型，不是三个固定 genre enum。不要把它们设计成代码类型。

如果一个所谓通用抽象只能解释当前第一世界，它还不能证明自己是 Core。

---

# 46. V2：World Truth、Knowledge 与 Observation

World Truth ≠ Actor Knowledge 是正式价值观，不只是 future feature。

世界知道某事实为真，不代表每个角色都知道。信息权限必须像位置、资源、伤势一样受到世界规则约束。

Knowledge / Visibility 和秘密、NPC、调查、信息差、Narrator、LLM Player 直接相关。

---

# 47. V2：成长结构的泛化原则

Habitat（长期生存承载体）不一定是固定地点。它可能是固定建筑、列车、船、大型生物、飞船、潜艇、移动城市。但不是所有世界都需要 Habitat——它是 optional world structure，不是 Player 强制字段。

ProgressionTrack / ProgressionGate / Progression Attachment 是候选抽象语言，用于避免把 player.level 和三选一当成宇宙统一成长模型。它们是否最终成为 code-level abstraction，要由 `DEV_SPEC.md`、实际 vertical slices、第二/第三 WorldPack 验证。

---

# 48. V2：Local Simplicity, Global Escape Hatches

当前实现应该尽量简单：one player、one enemy、one base、one progression path 都可以。

但命名和 contract 不应该宣称"永远只能一个"。

例如 Phase 4 encounter 暂时服务 expedition 是允许的。但设计文档要明确：

> 这是当前 vertical slice 的局部约束，而不是所有 Encounter 的世界定义。

世界尺度可以成长（个人 → 团队 → Habitat → Settlement → Organization → Region），但 Core 不提前模拟文明。长期可扩展性不等于当前就模拟所有尺度。

> **Compatibility ≠ Implement Everything。今天不要把第一个世界的偶然结构误认为宇宙规则。**

---

# 49. 关系、亲密关系与联合成长

关系、亲密关系与联合成长是未来可能进入 TheGreatNovel 的长期设计问题，
不是当前 MVP 的实现承诺。本节是一组设计宪法：它规定未来系统必须守住的
边界，但不提前定义完整 Relationship Engine、关系图数据库或固定 WorldPack
schema。

## 49.1 引擎对性别组合保持中立

同一套关系与联合行动合同必须能够处理 `male-male`、`male-female`、
`female-female`，也不能把当前项目永远限制为这三种身份表达。性别身份可以
影响人物设定、私人偏好和叙事表达，但不能直接决定引擎是否支持关系。

未来身份扩展属于 Actor / WorldPack 的真实需求，不应通过新增平行关系系统
解决。关系事实应以参与者和因果状态表达；`actor_id`、`participants`、
`relationship kind`、`relationship status`、`mutual consent` 是共享设计
词汇，不是要求 Core 现在采用的固定 schema。

引擎不得建立三套并行系统，也不得把以下性别化称呼变成通用字段：

```text
girlfriend
boyfriend
wife
husband
player_has_girlfriend
```

这些词可以出现在特定 WorldPack 或 Narrator 文本中。不得出现根据玩家和
NPC 性别硬编码是否允许浪漫关系的分支。

## 49.2 成年边界是不可妥协的安全 invariant

任何明确属于成人亲密或性行为的关系参与者都必须被权威 Actor 状态或
WorldPack 事实明确记录为成年人。年龄未知、未成年或年龄状态矛盾时，相关
关系或成人亲密行动必须不可用；Narrator、LLM Player 和自由文本不能临时
推断成人资格。

这个边界不应自动把普通浪漫表达、非性联合成长、团队训练、师徒关系或一般
合作都归类为成人亲密行动。具体 WorldPack 必须为其行动定义适用的年龄和
合法性范围。

## 49.3 关系是双方状态，且必须保留形成历史

关系不能建模成“玩家获得一个恋爱 NPC”或“玩家拥有一个伴侣 Buff”。它必须
表示两个独立 Actor 之间的状态、选择、利益和约束。双方身份、偏好、关系
基础、选择和当前状态都可能影响关系，但玩家提出关系不等于关系成立，NPC
也不能因为玩家是主角而失去自主意愿。

未来状态必须能够保留关系如何形成、双方在当时知道什么、是否存在压力、
交易、政治安排、依赖或控制，以及这些事实带来的长期后果。后来产生的
感情、信任、留下、服从或共同利益不能自动把过去的胁迫重写成自愿；Narrator
不得用浪漫措辞洗掉结构化历史。

## 49.4 行动可执行性不等于自愿、同意或道德正确

Engine 的“合法 Action”只表示当前规则允许该行动被确定性结算，不表示行动
道德正确、双方自愿、关系健康或结果值得肯定。未来 WorldPack 可以在真实
产品需求下建模冷酷、施压、控制、交易性、政治性、依赖性或胁迫性路径；它
必须明确记录所需的意愿、同意、压力和后果，不得把这些维度压成一个攻略数值。

对于明确要求同意的关系或联合行动，双方同意必须由合法 Action、确定性规则
和权威 Event 确认。拒绝、撤回和终止必须成为可观察到的后果；但 Engine 不
替玩家或 NPC 做道德裁判，也不能因为行动可执行就宣称 NPC 爱、原谅或自愿。

LLM Player 只能在 Engine 提供的行动中选择，包括可能冷漠、施压或控制的
行动；它不能替 NPC 表达 consent、love、forgiveness 或对过去的重写。NPC
的留下、服从、依赖、信任和爱也必须区分，不能互相推导。

## 49.5 性取向和私人偏好属于角色事实与 Knowledge Boundary

角色可以拥有 gender identity、romantic orientation、partner preferences、
current commitments 和 private feelings。这些是角色事实或角色私有状态，
不是 Engine 的宇宙常量，也不默认全部暴露给玩家。

玩家只能通过合法互动知道角色愿意公开的信息。Observation 不得直接泄露
隐藏好感、隐藏性取向、未表达的吸引、未来接受概率或私人 consent 状态。
NPC 作决定时只能使用自己合理知道的信息；World Truth、Actor Knowledge 和
Player Knowledge 必须继续分离。

## 49.6 关系不能退化为攻略数值条

数值可以是关系事实的一部分，但不能确立“好感 50 → 表白成功”“好感 100
→ 自动双修”“每天送礼 → 固定增加数值”的长期方向。共同经历、时间投入、
行为一致性、承诺、信息、目标冲突、双方选择和机会成本都可能比数值更关键。
关系的第一 vertical slice 可以很小，但必须保留玩家选择和 Actor agency。

## 49.7 Joint Growth 是 Relationship-produced Capability

双修只是第一 WorldPack 可能采用的候选题材名，不是性别系统，也不是被动
经验 Buff。通用架构语言是 `Relationship-produced Capability`、
`Mutual Joint Action` 或 `Relationship-produced Joint Capability`。

联合成长可以由浪漫关系、亲密关系、信任、师徒、团队、契约、政治联盟或
其他真实连接产生；不要预设唯一关系来源、固定 schema、固定成本或固定
同意顺序。它必须在具体 WorldPack 合同中确定参与者、行动条件、真实时间、
体力、资源、风险和机会成本，并且改变策略空间，而不是：

```text
关系存在 → 被动经验 +10%
```

选择联合成长应意味着双方放弃其他事情、错过机会、消耗资源、暴露风险或
产生承诺。结果应是单人路径无法免费获得的战略变化。

## 49.8 Narrator 不能创造关系事实

叙事层只能表达已经由结构化状态和事件确认的事实。Narrator 不得自行宣布
两人相爱、NPC 已同意、两人完成双修、关系升级或过去的行为已经被原谅，
除非对应变化已经由合法 Action、Event 和 Reducer 产生。

关系相关事实必须继续遵守：

```text
Simulation / State
        ↓
Consequence
        ↓
Narrative
```

删除浪漫叙事以后，关系、意愿、联合行动、成本、Agency 和长期后果仍应能从
结构化状态与事件成立；否则它只是文本效果，不是可验证的世界机制。

---

# 50. Historical Product Context after Phase 8 — External Client、Compiled World 与语言无关叙事

本节保留 Phase 8 之后形成的外部客户端、compiled world、transport、authority 与语言边界
等历史产品背景。这里的旧 Phase 顺序、里程碑描述和当时实现判断不再是 Active Roadmap；
当前阶段编号、实现顺序、验收条件和 freeze 计划只以 `DEV_SPEC.md` 为权威。本节仍可作为
transport、authority 和 locale 设计价值的参考。

Phase 8 冻结以后，TheGreatNovel 的下一个产品方向不是让 Engine 直接连接某个
LLM Provider，而是让外部客户端能够编排一个仍由确定性 Engine 守护的完整会话：

```text
Codex / Qoder external client
→ campaign-specific generated world
→ deterministic compilation and validation
→ atomic campaign creation
→ choice_id-based play
→ traceable multilingual narration
→ resumable autoplay
→ novel.md export
```

这是一条未来产品路线，不代表 Phase 9 已实现。每个子阶段仍必须拥有独立的
Feature Contract、State/Event/Replay 证明和外部审查。

## 50.1 External client 是合法的 LLM Edge

Codex、Qoder、未来 IDE Agent、CLI Agent 和 API Provider 都只是不同的 LLM Edge
transport。当前开发和游玩不要求 LLM API。外部客户端可以：

- 编排会话；
- 生成 World Draft；
- 扮演 LLM Player；
- 根据确定性结果生成小说文本；
- 提交可追溯的叙事 artifact。

外部客户端不是世界权威。它不得直接写入权威 GameState、EventStore 或 snapshot，
也不得自行制造 DomainEvent、ActionIntent 的隐藏字段或世界结果。它只能通过
Engine 暴露的边界提交选择或边缘 artifact；Engine 负责验证、结算、持久化和重放。

第一种实践路径可以是：

```text
external client
→ read structured request
→ choose choice_id
→ call a restricted session command
→ read deterministic result
→ generate narration
→ submit narration artifact
```

文件、stdin/stdout、CLI、MCP、HTTP 和未来 Provider SDK 都只是 transport 选择。

> **Transport may change. Authority does not.**

Codex 或 Qoder 可以出现在产品与文档边界，不应进入 Core runtime 的世界规则分支。

## 50.2 生成可以不确定，编译后的游玩必须确定

必须区分四层对象：

```text
World Genesis Request  — 用户的自由描述，不是权威状态
World Draft            — 外部客户端生成的候选内容，可以失败和修复
Compiled WorldPack     — 通过严格验证、绑定稳定 ID 的可执行世界包
Campaign               — 绑定完整 Compiled WorldPack 的正式游戏实例
```

生成请求可以是“随机朋克求生世界、移动机械城市、酸雨、机械寄生虫、黑暗成长
风格”。它不需要直接满足 Engine schema。World Draft 可以不完整、每次不同或
校验失败；失败的 Draft 不是坏存档，只是未被接受的 generation attempt。

Compiled WorldPack 的概念管线是：

```text
Parse
→ schema validation
→ semantic validation
→ enabled-feature validation
→ reference validation
→ normalization
→ stable ID binding
→ minimal playable bootstrap
→ scripted smoke test
→ canonical serialization
→ hash
```

World generation may be nondeterministic. Playing a compiled world must be deterministic。
Campaign 接受后必须完整保存 Compiled WorldPack 和 hash；Replay 读取保存的包，
不得再次调用 LLM 生成世界，Narrator 也不得静默改写包内容。

Campaign 创建必须是原子的：

```text
compile and validate in a temporary attempt area
→ all required gates pass
→ create EventStore and initial state
→ atomically publish Campaign
```

失败不得留下可被存档列表识别的半成品 Campaign、部分初始化的 SQLite 或误报成功
的加载入口。独立的 draft、generation attempt 和 error report 可以保留供修复。

## 50.3 Bounded generation 与通用生成必须分开

较早允许的是 **Bounded campaign-specific generation**：它只能使用当前已经实现并
审查过的 Action、Event 和 Feature Contract，生成题材内容、名称、描述、初始实体、
参数与现有机制组合，并在验证失败后修复一个有边界的问题。它不能创造新的运行时
语义。

仍然延期的是 **General-purpose LLM World Generator**。如果生成器要发明新的
Action、Event、Reducer、数据库字段、Python 代码、动态 Feature 或让自然语言
直接成为权威规则，必须等多个结构不同的真实 WorldPack 证明稳定的共享合同以后
再讨论。

> **LLM may generate content within an existing rule language. LLM may not invent the
> rule language during campaign creation.**

Feature-scoped validation 是边界：不存在的功能不产生配置义务。WorldPack 只需满足
已启用 Feature、当前最小可玩循环、initial Observation、legal actions、Replay 和
invariant 所需的合同。启用 Feature 后，`Optional Feature != Soft Fiction`，它仍
必须进入 State、Event、Rule、Replay 和外部审查。

## 50.4 生成错误必须可被机器局部修复

世界生成失败不能只返回一段自然语言。Compiler / validator 应返回稳定、语言中立
的错误结构，至少能表达：

```text
code
path
actual value
expected contract
allowed values / referenced IDs where relevant
```

例如 `UNKNOWN_LOCATION_REFERENCE` 必须能指出 `actors.mara.location_id` 和允许的
ID。错误 code 与 path 是 authority；localized message 只是 presentation。目标是：

```text
generate
→ validate
→ repair one bounded problem
→ validate again
```

这不意味着现在建立万能 schema repair framework 或无限自动 repair agent。

## 50.5 语言属于表达层，不属于规则身份

Engine 使用稳定、语言无关的 ID 和 enum，例如 `SEARCH`、`TALK_TO_ACTOR`、`ALIVE`、
`DAWN`、`actor_id`、`resource_id`、`choice_id` 和 `event_type`。显示词如“探索”、
`Search` 或 `بحث`，以及“清晨”、`Dawn` 或 `الفجر`，不得成为逻辑身份。提交给
Engine 的仍是稳定 ID 或 `choice_id`。

未来设计应区分三个 locale；它们是责任边界，不是要求现在立即建立通用 schema：

```text
input_locale      — 用户与外部客户端交互的语言，属于客户端边缘
content_locale    — WorldPack 中世界名称、人物显示名和题材内容的主要语言
narration_locale  — 当前小说输出语言，可以在 Campaign 中途改变
```

`narration_locale` 不得改变 GameState、Event、RecordedDecision、legal actions 或
state hash；不要把三者压成一个同时控制规则和叙事的 `language` 字段。

所有文本 artifact 使用 UTF-8。阿拉伯语字符可以出现在显示文本和小说中，但阿拉伯
语名称不能替代稳定 ID；Campaign 目录、数据库引用和 canonical identity 不依赖
阿拉伯语显示标题。RTL 是未来 UI / web presentation concern，不进入 Engine 或
Replay；本项目当前只定义边界，不实现网页 RTL。

同一冻结 WorldPack、初始状态和 RecordedDecision sequence，在中文、英文和阿拉伯语
叙事之间必须保持相同的 Action sequence、Event sequence、final GameState 和 state
hash。只允许 prose、localized labels、Voice Pack、narration metadata 和 exported
novel text 改变。中途切换语言不得重编译 WorldPack、迁移 GameState、改变既有
EventStore 事件或 RecordedDecision；不同语言 artifact 都应保留。

## 50.6 Narration Guard 不解析自然语言关键词

禁止用类似 `if "获得" in prose` 的关键词检查来验证小说事实。叙事顺序必须是：

```text
authoritative Event
→ player-visible narration brief
→ structured claims
→ prose
```

资源获得、伤害、死亡、地点变化、关系变化和知识获得等关键声明，应能通过结构化
claim 与公开 Event 对照。Narrator 或外部客户端只能根据公开事实生成文本；小说错误
可以被拒绝、标记或重写，但不得修改 GameState。Narration locale 不进入世界状态
hash，也不应通过解析中文、英文或阿拉伯语散文恢复游戏事实。

本原则不在本阶段定义完整 Narration Claim schema。它只固定责任边界：

```text
Simulation / State
        ↓
Consequence
        ↓
Narrative
```

## 50.7 Phase 9 的设计纪律

Phase 9A–9C 每次只实现一个最小 vertical slice。不得因为外部客户端路线提前建立
`PluginManager`、`ProviderRouter`、`LocaleFramework`、`TranslationDatabase`、
`AgentOrchestratorFramework`、`GenericWorkflowEngine`、通用 World Schema 或动态
插件框架。Phase 9D 的 multi-model matrix 是后续评估路线，不是 Phase 9A–9C 的
前置条件。真实 WorldPack 和实际会话压力决定下一步抽象。

---

# 51. Genesis Foundation：生成世界，但不生成裁判

Phase 10G0.1 将前述价值观收束为一个更精确的 Genesis 边界。完整开发合同见
[`DEV_SPEC.md`](DEV_SPEC.md)；本节只记录必须长期保持的价值判断。

## 51.1 LLM at the edges 不等于 LLM 只能写 prose

LLM 可以在边缘提出世界、人物、地点、资源生态、机会、故事线程、主角背景和结构化
行动候选。它可以把玩家的自然语言意图整理成 `Requirement Proposal`、`World Blueprint`
或 `Narration Artifact`。但“能够提出结构”不等于“结构已经成为事实”。

确定性中心负责验证 schema、判断当前 Feature Contract 是否真实存在、绑定受支持的
运行语义、建立初始状态、验证行动、结算后果、持久化事件并完成 Replay/Verify。LLM
不能成为 Engine、EventStore、GameState、DomainEvent 或 WorldPack 的事实裁判。

```text
LLM proposes.
Python validates and binds.
The deterministic runtime decides.
SQLite remembers.
The narrator describes committed facts.
```

## 51.2 Campaign-specific WorldPack 是产品目标，不是预制世界菜单

玩家不应只能从开发者手写的 `ocean_world.py`、`cyberpunk_world.py` 等模块中选择。
目标管线是：

```text
Prompt + Seed
→ structured requirements
→ Campaign-specific World Blueprint
→ supported semantic binding
→ validation and sealing
→ Campaign-specific WorldPack
```

WorldPack 可以是测试用的开发者预制包、官方精心设计世界，也可以是由 Prompt 与 Seed
生成后封存的本 Campaign 专属包。官方手工世界可以是一等游玩入口、回归基准和高质量
对照组，但必须明确标识为 authored/official，不能冒充 Genesis。Genesis 用户流程不能
降级成选择通用故事模块；生成的 Campaign 必须保留 Prompt + Seed lineage，并经过
generation attempt、semantic binding、preflight 和原子 seal。
动态生成内容不能动态生成新的 Python 规则、Event、Reducer、数据库 schema 或插件。

## 51.3 Determinism 的对象是已接受事实，不是预写所有内容

Determinism 要求已接受的持久事实、合法行动、事件结算、保存 artifact 和 Replay 可
重现；不要求开发者预先写完所有世界内容。LLM API 的 `seed`、temperature 或 provider
采样参数不能跨模型、模板、工具、推理实现和服务端版本保证字节级相同。

因此必须坚持：

> Seed determines the generation path. The sealed WorldPack determines what the world actually is.

Seed 是生成路径输入；真正被接受、canonical serialize、hash 并封存的 WorldPack
才是 Campaign 的历史事实。Replay 读取封存 artifact，不重新询问 LLM。

## 51.4 Durable facts 与 ephemeral texture 必须分离

生成结果明确区分以下三类；未来增加类别必须先扩展 Genesis authority matrix、hash/replay
规则和 failure boundary：

- `authoritative durable facts`：稳定 ID、可 canonical serialize、被保存和 hash，能进入
  State/Event/Replay 的已接受事实；
- `candidate durable facts`：LLM 提出的候选，在验证和封存前不是 GameState、DomainEvent
  或 Campaign 事实；
- `ephemeral non-authoritative texture`：只改变感官、语气和氛围，不改变因果链的表达细节。

Narrator 可以生成第三类内容，但不能把候选事实或未支持机制写成已发生的世界事实，
也不能从 prose 反向恢复 State、Event、秘密、资源、能力或人物关系。

## 51.5 World Depth 是一级产品标准

Genesis 不能只更换标题、资源名、基地名和 NPC 名。真正的 World Depth 要求结构上
存在差异：地点拓扑、资源循环、生存压力、主角策略优势、NPC 目标、派系关系、隐藏
真相、Story Engine、压力/机会时钟，以及玩家不行动时世界如何继续变化。

World Depth 不是后期 prose polish；它必须最终进入受支持的 State、Event、Rule、
Projection 和 Replay 合同。还要通过主角能力启用/移除的 A/B strategy proof，证明合法
行动、可达策略或资源/机会代价发生结构差异，而不是只改变数值。若当前引擎没有对应
运行语义，正确结果是 `UNSUPPORTED` 或明确的 `DEGRADED`，不是让 Narrator 掩盖缺口。

任何以 Genesis 名义发布给用户的 Campaign 至少必须通过开发合同中的
`STRUCTURAL_DIVERGENCE_V1`；只换 title、labels、premise 或资源名称的包不能用
`depth_claim=NONE` 绕过反换皮门禁。更高的 `WORLD_DEPTH_L1` 与 `WORLD_DEPTH_L2` 分阶段
实现：先证明地点图、压力与不可逆机会，再证明 off-screen Actor、多时钟和主角优势 A/B；
最低结构差异不是可由 prose 或 acknowledgement 取消的产品承诺。

## 51.6 主题不是运行时开关

不得把 `"海洋"`、`"玄武"`、`"朋克"` 等词作为 Python 分支条件。Feature Catalog
中的 `LocationGraph`、`Travel`、`Habitat`、`ProgressionTrack`、`PressureClock` 或
`NetworkAccess` 只是可能出现的 runtime semantic 类别示例，不代表当前 Catalog 已经
预注册了对应 Feature ID，也不代表这些 Feature 当前已经实现。实际 Feature Catalog 只
收录已经拥有明确 State、legal Action、Event、Reducer、Invariant、Projection、Persistence、
Replay/Verify、tests 和真实 vertical slice 证据的 Feature。

对尚未实现但合理的需求，系统应返回稳定的 `NO_MATCHING_RUNTIME_CONTRACT` 或等价结果，
不得为了返回 `UNSUPPORTED` 而提前创建 placeholder Feature、class、schema、registry 或
package。每个真正进入 Catalog 的 Feature 仍需自己的完整运行合同；“主题不是运行时开关”
不意味着未来语义可以先以目录条目占位。

## 51.7 安全与失败边界

玩家 Prompt 是不可信数据，不是系统指令。它不能读取文件、执行命令、修改规则、绕过
支持目录、获得隐藏权限或改写冻结合同。失败的 generation attempt 可以保存错误报告
供修复，但不能创建正式 Campaign、污染 GameState 或让 Narrator 提前使用候选事实。
