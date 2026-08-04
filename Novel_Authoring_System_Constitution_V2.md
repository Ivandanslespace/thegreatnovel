# NOVEL AUTHORING SYSTEM CONSTITUTION

> Version: 2.0  
> Purpose: 续写、规划、审查和修订一部已经开始的长篇小说。  
> Default profile: 长篇连载、升级、求生与爽文；其他类型可以替换节奏参数和类型配置，但不得破坏事实、因果与作者控制权。

---

# 0. 产品使命

本系统不是一个收到一句提示就自由发挥的“写作聊天机器人”，也不是一个用分数自动拼装章节的模板机器。

它要完成的是：

```text
读取已经存在的小说
→ 重建已成立的事实、人物、关系、时间线、规则与叙事承诺
→ 判断读者此刻在等待什么、担忧什么、已经厌倦什么
→ 选择下一章最需要承担的叙事功能
→ 生成遵守原作因果、人物和文风的候选方案
→ 由作者选择、修改或否决
→ 写成正文
→ 校验后才写入新的小说历史
```

系统必须同时服务三件事：

1. **续得上**：不遗忘、不偷改、不让人物突然变成另一个人。
2. **写得动**：知道当前最值得推进的线程，以及下一章应该主要做什么。
3. **追得下去**：长期管理压力、爽点、悬念债务、进展、风险和重复疲劳。

公式的职责是发现失衡、分配注意力和给候选方案排序；公式无权直接创造事实，也无权代替作者决定小说的意义。

---

# 1. 不可妥协的核心循环

## 1.1 通用续写循环

所有小说类型共享的产品循环是：

```text
SOURCE READING
→ CANON RECONSTRUCTION
→ READER-STATE DIAGNOSIS
→ NARRATIVE-FUNCTION SELECTION
→ CAUSAL CHANGE
→ VOICE-CONSISTENT WRITING
→ VALIDATION
→ CANON COMMIT
```

准确中文是：

```text
读取原文
→ 重建正史
→ 诊断读者状态
→ 选择下一步叙事功能
→ 产生有因果的状态变化
→ 使用原作建立的声音写作
→ 校验
→ 经作者批准后写入正史
```

## 1.2 升级爽文体验配置

以下循环是升级、求生、系统流和成长型爽文的重要类型配置，而不是所有小说的宇宙真理：

```text
CONTROL DEFICIT
→ RULE LEGIBILITY
→ ASYMMETRIC LEVERAGE
→ COMPOUNDING CONTROL
→ RELATIONSHIP REVERSAL
→ TIER ASCENT
→ LARGER WORLD
```

```text
控制缺口
→ 看懂规则
→ 使用主角非对称杠杆
→ 将已有成果转化为更强控制力
→ 与危险、匮乏、规则和他人的关系发生反转
→ 完成当前真实阶层跃迁
→ 带着已有成果进入更大的世界并面对新的相对失控
```

当一本既有小说已经建立了这一承诺，续写不得把成长退化成随机发奖、纯数字膨胀或无因重置。

当一本小说并不以这一循环为主要承诺，系统不得强行加入等级、宝箱、打脸、排行榜或资源暴富。

---

# 2. 作者拥有最高控制权

系统必须支持三种明确模式：

- `faithful_continuation`：忠实续写。原文事实、人物、文风和已建立的叙事承诺优先。
- `constrained_innovation`：受约束创新。在不破坏正史的前提下提出新路线。
- `explicit_revision`：明确修订或重构。只有作者明确授权，才允许改写旧事实、删除情节或进行 retcon。

系统不得把“模型认为更好”当作修改原作的权限。

作者可以锁定：

- 不可改变的事实；
- 必须保留的人物命运；
- 禁止出现的内容；
- 计划中的终局与里程碑；
- 允许或禁止调整的文风范围；
- 某一公式指标的权重或阈值；
- 下一章必须完成或不得完成的叙事任务。

所有自动建议都必须能回答：

1. 为什么现在建议写这个？
2. 它依据了哪些原文事实和未兑现承诺？
3. 它会改变哪些后续状态？
4. 哪些其他候选被放弃，为什么？

---

# 3. 事实层级与正史边界

## 3.1 六种信息状态

系统中的信息必须显式标记为以下状态之一：

1. `CANON`：原文或作者已确认的事实。
2. `AUTHOR_INTENT`：作者明确说明但尚未写进正文的计划。
3. `APPROVED_OUTLINE`：作者批准的未来结构，不等于已经发生。
4. `INFERENCE`：系统依据原文作出的推断，必须带置信度。
5. `CANDIDATE`：尚未被作者采用的可能方案。
6. `PROSE_ONLY`：修辞、比喻、气氛或不应直接当作客观事实的叙述。

`INFERENCE`、`CANDIDATE` 和 `PROSE_ONLY` 不得被静默升级为 `CANON`。

## 3.2 优先级

发生冲突时，默认优先级为：

```text
作者最新明确指令
> 作者明确批准的修订记录
> 已发布正文中的明确事实
> 作者批准的大纲
> 高置信度推断
> 普通推断
> 模型候选方案
```

若原文自身存在冲突，系统必须列出冲突和来源，不得偷偷选择一个方便的版本。

## 3.3 续写边界

生成章节之前，系统必须创建 `Continuation Boundary Packet`，至少包含：

- 当前续写位置；
- 最近若干章的完整文本；
- 更早章节的结构化摘要；
- 当前仍有效的事实；
- 人物当前状态和知识边界；
- 活跃目标、承诺与悬念；
- 当前资源、能力、身份和关系；
- 最近使用过的爽点、反转和章节结构；
- 文风样本与禁忌；
- 作者当前指令。

没有边界包，不得直接续写长篇正文。

---

# 4. 小说记忆不是一份摘要

系统至少维护以下记忆层。原始正文必须保持不可变；结构化状态可以重建。

## 4.1 Source Store

保存原始章节、版本、段落位置和作者修改历史。任何抽取事实都必须能回指来源。

## 4.2 Canon Ledger

记录：

- 人物、地点、物品、组织和制度；
- 已发生事件；
- 世界规则与例外；
- 能力、资源、伤势、债务、身份；
- 明确承诺、禁令与不可逆后果。

每条记录至少有：

```json
{
  "statement": "主角已获得自动物资收集能力",
  "status": "CANON",
  "source_chapter": 37,
  "source_span": "...",
  "confidence": 1.0,
  "valid_from": 37,
  "valid_to": null,
  "supersedes": null
}
```

## 4.3 Timeline Ledger

记录故事时间、事件顺序、持续时间、旅行时间、冷却、期限和并行事件。

“章节号”不等于“故事时间”。系统必须能区分：

- 写了几章；
- 故事过去多久；
- 某人物多久没有行动；
- 某承诺何时到期；
- 某能力何时恢复。

## 4.4 Character Ledger

每个重要人物至少记录：

- 当前目标；
- 恐惧、欲望、底线；
- 已知信息与误解；
- 能力和资源；
- 与他人的关系结构；
- 当前情绪惯性；
- 正在执行的计划；
- 不在场时可能继续发生的行动。

人物不是一组标签。任何显著性格变化都必须有桥梁事件。

## 4.5 Knowledge Matrix

必须区分：

```text
World Truth
≠ Character Knowledge
≠ Narrator Disclosure
≠ Reader Knowledge
```

系统不得让人物说出其不可能知道的信息，也不得因为数据库知道某事就让叙述者提前泄露。

## 4.6 Relationship Ledger

关系不只记录“好感”。至少可以包含：

- 信任；
- 利益一致度；
- 依赖；
- 债务；
- 恐惧；
- 秘密暴露程度；
- 承诺；
- 背叛成本；
- 身份和权力差。

关系变化必须由事件证明，而不是旁白宣布。

## 4.7 Resource / Power Ledger

按小说需要记录资源、能力、权限、生产力、组织规模和可用战力。

必须区分：

- `Absolute Capacity`：已经挣得的长期能力；
- `Effective Capacity`：受位置、伤势、供给、维护和政治条件限制的当前可用能力；
- `Relative Standing`：主角相对于当前真实比较群体的位置。

新地图不得无因清零旧成果。新的困难应来自更大的尺度和更复杂的约束，而不是偷偷重置主角。

## 4.8 Arc & Promise Ledger

每条活跃线程至少记录：

```json
{
  "thread_id": "resource_crystal_shortage",
  "goal": "建立足以长期维持自动防御的诡晶供给",
  "stakes": "无法自动守夜，探索时间被锁死",
  "phase": "escalation",
  "introduced_chapter": 12,
  "last_advanced_chapter": 31,
  "target_payoff_window": [35, 45],
  "importance": 0.86,
  "reader_visibility": 0.95,
  "progress": 0.72,
  "dependencies": ["auto_collection_ability"],
  "status": "active"
}
```

叙事承诺包括但不限于：

- 明确提出的问题；
- 被反复强调的资源缺口；
- 某人的未完成计划；
- 已展示但尚未兑现的能力；
- 一次选择承诺的后果；
- 被压住的冲突；
- 读者被引导期待的关系变化；
- 类型承诺，例如升级、复仇、破案或感情进展。

## 4.9 Style & Voice Profile

续写必须从原文中提取而不是凭空指定：

- 叙述人称和视角距离；
- 时态；
- 句长与段落节奏；
- 对话比例；
- 内心活动密度；
- 信息说明方式；
- 幽默、残酷、抒情和讽刺的强度；
- 角色口头禅和个体声音；
- 章节开头与结尾习惯；
- 禁用表达与作者明确不喜欢的套路。

文风指标用于发现漂移，不得把文学语言简化成机械模仿。

## 4.10 Payoff & Repetition Ledger

记录最近使用的：

- 爽点类型和子类型；
- 来源；
- 解决方式；
- 社会反馈方式；
- 场景拓扑；
- 情绪结果；
- 章节结尾方式；
- 实际后续影响；
- 同类冷却和疲劳。

“换资源名”不算新结构。

---

# 5. 章节不是固定模板，而是叙事功能组合

每章可以包含多个功能，但默认只允许一个主要功能和最多两个次要功能，避免一章同时完成所有事情。

可选功能包括：

- `setup`：建立价值、限制、目标或未来来源；
- `pressure_build`：提高威胁、匮乏、期限、关系压力或失败可能；
- `choice`：让主角作出有机会成本的决定；
- `discovery`：获得能改变判断的信息；
- `progress`：让目标或状态发生不可逆推进；
- `partial_payoff`：回答一部分问题、获得局部控制；
- `major_payoff`：兑现长期期待或完成阶段性解放；
- `reversal`：已有理解或关系发生有依据的反转；
- `aftershock`：展示上一重大事件如何改变行动、关系和世界；
- `recovery`：降低过载压力，同时让世界继续运行；
- `relationship_shift`：改变信任、依赖、债务、地位或承诺；
- `world_expansion`：在保留旧成果的前提下打开更大的问题空间。

公式决定“现在最需要哪种功能”，不决定“必须出现哪只怪、哪个宝箱或哪句台词”。

---

# 6. 指标与公式的共同规则

## 6.1 归一化

除特别说明外，所有指标取 `0—100`：

- `0`：几乎不存在；
- `50`：中等；
- `100`：极强；
- 超过 `100` 仅用于表示债务或过载，不代表质量更高。

公式中的权重是默认类型配置，可以由作者和项目调整，不是文学真理。

## 6.2 公式的权限边界

公式可以：

- 标记某个问题已经成熟；
- 发现同类结构过密；
- 给候选章节排序；
- 建议目标强度；
- 检查实际章节是否完成合同。

公式不可以：

- 凭分数创造奖励来源；
- 因为压力太低就临时杀人；
- 因为需要爽点就让敌人变弱；
- 修改人物知识；
- 把尚未批准的候选写入正史；
- 证明一段文字“必然好看”。

---

# 7. 压力—释放系统

## 7.1 单线程压力

对每条活跃线程 `t`：

```text
P_t =
0.25 × Threat
+ 0.20 × Scarcity
+ 0.20 × Deadline
+ 0.15 × Uncertainty
+ 0.10 × SocialConflict
+ 0.10 × FailureAccumulation
```

其中：

- `Threat`：生命、身份、目标、情感或组织受到威胁的程度；
- `Scarcity`：资源、能力、时间、资格或机会不足；
- `Deadline`：窗口关闭或后果临近；
- `Uncertainty`：当前结果不可预测但仍可理解；
- `SocialConflict`：关系、竞争、声誉和权力压力；
- `FailureAccumulation`：最近失败、损失和受阻的累积。

全书当前压力：

```text
P_global = Σ(Salience_t × P_t) / Σ(Salience_t)
```

`Salience_t` 由线程重要性、近期出现频率和读者可见度共同决定。

## 7.2 默认压力区间

- `0—30`：低压；适合恢复、关系、探索或建立新欲望，但不能长期无进展。
- `31—55`：正常推进。
- `56—75`：明显紧张；适合决策、代价和局部兑现。
- `76—90`：高潮准备区；成熟爽点或关键反转可以爆发。
- `91—100`：极端压力；不得长期维持。

默认警报：

- 连续 `3—5` 章高于 `80`：检查是否需要局部控制、恢复或兑现；
- 连续 `5—8` 章低于 `35`：检查是否缺乏目标、风险、选择或变化。

压力不是越高越好。目标是形成可感知的曲线，而不是持续压迫。

---

# 8. 叙事承诺与悬念债务

对每一项叙事承诺 `i`：

```text
AgeRatio_i = clamp(0, 1.5, AgeChapters_i / TargetMaxAge_i)
ReminderFactor_i = 1 + 0.12 × min(ReminderCount_i, 5)

Debt_i = clamp(
  0,
  150,
  100
  × Importance_i
  × ReaderVisibility_i
  × (1 - Progress_i)^1.2
  × AgeRatio_i
  × ReminderFactor_i
)
```

其中 `Importance`、`ReaderVisibility` 和 `Progress` 取 `0—1`。

默认解释：

- `Debt < 40`：健康；
- `40—79`：应在近期推进；
- `80—109`：三章内至少明显推进；
- `110—129`：不得继续堆叠同等级新承诺；
- `≥130`：必须兑现、明确重构，或由作者批准延后并提供新的实质进展。

默认周期：

- 短承诺：`1—3` 章；
- 中承诺：`8—30` 章；
- 长承诺：`40—200+` 章，必须阶段性回答，不能只重复提醒。

滚动十章中，新增重大悬念不能长期显著高于已兑现和已推进的悬念：

```text
NewHookLoad
≤ FullPayoffCount
+ 0.6 × PartialAdvanceCount
+ GenreAllowance
```

`GenreAllowance` 默认为 `1—2`，悬疑类型可以更高，但必须仍有局部答案。

---

# 9. 不可逆进展与停滞指数

每章进展值：

```text
G =
0.20 × PermanentGrowth
+ 0.20 × WorldStateChange
+ 0.15 × RelationshipChange
+ 0.15 × KnowledgeChange
+ 0.15 × GoalAdvance
+ 0.15 × StrategyExpansion
```

只有会改变后续选择、成本、关系、知识或世界状态的变化才算进展。

示例：

- 获得少量普通消耗品：低进展；
- 第一次获得远程手段：中进展；
- 解锁自动生产或新的合法行动：高进展；
- 关系从依赖变为合作或敌对：中高进展；
- 普通资源永久毕业并开启更高层玩法：高进展；
- 基地升级为组织或城市：性质变化。

默认滚动检查：

- 每章可以低进展，但应有明确叙事用途；
- 每 `3—5` 章至少有一次 `G ≥ 25`；
- 每 `10—20` 章至少完成一个中目标；
- 每 `30—60` 章至少发生一次玩法、身份、关系或世界尺度上的性质变化。

停滞率：

```text
StagnationRate =
Count(G < 10 in last 8 chapters) / 8 × 100
```

若 `StagnationRate ≥ 62.5`，且这些章节又没有承担必要的恢复、人物塑造或准备功能，则触发灌水警报。

---

# 10. 爽点成熟度与爆发评分

一个计划中的爽点不能只看奖励大小。系统分别计算成熟度、冲击力、新奇度、合理性、后续价值、疲劳和破坏程度。

## 10.1 成熟度 M

```text
M =
0.25 × TargetPressure
+ 0.20 × SetupDepth
+ 0.20 × WaitingReadiness
+ 0.20 × CostPaid
+ 0.15 × ArcPhaseFit
```

`WaitingReadiness` 默认：

```text
WaitingReadiness = min(100, 100 × Age / TargetMinAge)
```

超过合理窗口产生的是“债务”，不会继续无限增加爽感。

## 10.2 冲击力 I

```text
I =
0.25 × RelativeScale
+ 0.25 × ConstraintRemoval
+ 0.20 × BehaviorChange
+ 0.15 × FutureCapacity
+ 0.15 × SocialOrVisualProof
```

真正重要的不是绝对数字，而是它是否改变主角的行为方式和后续能力。

## 10.3 合理性 C

```text
C =
0.30 × CausalChainCompleteness
+ 0.25 × RuleConsistency
+ 0.25 × MeaningfulCost
+ 0.20 × SourceSeededEarlier
```

## 10.4 后续价值 A

```text
A =
0.30 × NewGameplayOrActionSpace
+ 0.25 × DecisionPatternChange
+ 0.25 × HigherTierNeedOpened
+ 0.20 × SocialOrWorldEffect
```

## 10.5 新奇度 N

新奇度由最近同类事件的结构相似度反推：

```text
N = 100 - RepetitionFatigue
```

## 10.6 最终净爽点评分 S

```text
S = clamp(
  0,
  100,
  0.24 × M
  + 0.22 × I
  + 0.14 × N
  + 0.16 × C
  + 0.18 × A
  + 0.06 × StructuralFit
  - 0.12 × RepetitionFatigue
  - 0.10 × FutureDamage
)
```

`FutureDamage` 包括：

- 一次解决所有资源和冲突；
- 让旧规则失去意义；
- 迫使后续不断膨胀数字；
- 提前泄露终局；
- 让已有角色或组织全部失去作用；
- 使主角以后不再需要作选择。

默认解释：

- `0—49`：不应进行大兑现，继续铺垫或改方案；
- `50—64`：适合小奖励或局部回答；
- `65—79`：适合中型爽点；
- `80—90`：适合阶段性大爆发；
- `91—100`：留给篇章高潮、重大关系反转或世界性质变化。

高分不是自动执行命令。来源不成立、正史冲突或作者不同意时，仍不得采用。

---

# 11. 资源压力与阶段性资源解放

对核心资源 `r`：

```text
ResourcePressure_r =
0.30 × CurrentShortfall
+ 0.20 × CostIncomeImbalance
+ 0.20 × RecentlyBlockedActions
+ 0.15 × NearFutureDemand
+ 0.15 × ReaderSalience
```

读者爽感主要取决于相对尺度：

```text
CoverageChapters = RewardAmount / max(AverageChapterCost, ε)
RelativeRewardScale = RewardAmount / max(RecentNormalIncome, ε)
```

阶段性资源解放的默认硬条件：

```python
def can_trigger_resource_liberation(state):
    return (
        state.resource_pressure >= 70
        and state.setup_chapters >= 8
        and state.blocked_decisions >= 2
        and state.same_type_fatigue <= 35
        and state.has_causal_source
        and state.has_paid_cost_or_risk
        and state.has_post_payoff_behavior_change
        and state.next_resource_tier_ready
    )
```

资源解放必须完成四件事：

```text
永久解决一个旧层级问题
→ 在 1—3 章内改变主角行为
→ 开启一种此前不实际的新玩法
→ 暴露更高一级的资源、责任或战略瓶颈
```

它不得：

- 同时让食物、能源、弹药、建材和升级核心全部无限；
- 暴富后继续为已经不重要的小额消耗反复纠结；
- 下一章立即无因回收全部奖励；
- 只增加库存而不产生后果。

默认尺度：

- 小型横财：当前普通行动收益的 `1—3` 倍；
- 中型解压：近期总需求的 `2—5` 倍；
- 阶段毕业：普通使用场景下覆盖约 `20—50` 章，但面对高阶项目仍有规划需求；
- 经济体系级变化：整本书只应少量发生，每次都改变主角身份、组织规模或生产方式。

同一种低级资源通常只需要真正毕业一次。之后应写高级形态、生产渠道、加工权限、组织分配或新的消耗结构，而不是再次重复“大量获得同一普通资源”。

---

# 12. 重复疲劳

重复检测必须比较结构，而不只是名词。

候选章节 `c` 与历史章节 `h` 的相似度：

```text
Similarity(c, h) =
0.30 × EventSourceSimilarity
+ 0.25 × SolutionMethodSimilarity
+ 0.20 × PayoffTypeSimilarity
+ 0.15 × SceneTopologySimilarity
+ 0.10 × EmotionalOutcomeSimilarity
```

带时间衰减的重复疲劳：

```text
RepetitionFatigue(c) =
100 ×
Σ[exp(-Distance(c,h)/τ) × Similarity(c,h)]
/
Σ[exp(-Distance(c,h)/τ)]
```

默认 `τ = 12` 章，并额外检查最近 `20` 章和 `50` 章的同类结构次数。

默认处理：

- `<35`：新鲜；
- `35—59`：可用，但应改变至少一个结构维度；
- `60—74`：高疲劳，必须改变来源、解决方式或结果中的至少两个；
- `≥75`：默认拒绝，除非重复本身具有明确升级、反讽或闭环意义。

“宝箱换成尸体掉落”“震惊群聊换成排行榜公告”不一定构成结构创新。

---

# 13. 风险可信度

```text
RiskCredibility =
0.25 × RealizedCostRate
+ 0.20 × ConsequenceClarity
+ 0.20 × OppositionEffectiveness
+ 0.20 × ProtectionLimitVisibility
+ 0.15 × InformationLimits
```

其中：

- `RealizedCostRate`：此前被强调的重大风险中，实际兑现过多少真实代价；
- `ConsequenceClarity`：失败会失去什么是否清楚；
- `OppositionEffectiveness`：敌人、环境和制度是否真的能推进自己的目标；
- `ProtectionLimitVisibility`：主角底牌是否有边界；
- `InformationLimits`：主角是否存在合理未知。

默认警报：

- 连续多章 `<40`：危险可能已经沦为装饰；
- 在总压力已高于 `80` 时仍长期 `>85`：可能过度压迫，应允许局部控制、休整或真实回报。

代价不等于必须让主角惨败或死人。可以是：

- 消耗稀有物；
- 暴露底牌；
- 错过窗口；
- 受伤和恢复期；
- 关系恶化；
- 基地损坏；
- 债务和承诺；
- 失去某个候选奖励；
- 被迫提前使用未来资源。

被明确强调的风险不能永远只伤害无名路人。

---

# 14. 主角能动性

当存在重要选择时，计算：

```text
Agency = 100 ×
(ValueBalance
× ConsequenceDifference
× InformationAdequacy
× OpportunityCost
× LongTermEffect)^(1/5)
```

各项取 `0—1`。使用几何平均，是因为其中任何一项接近零都会使选择失去重量。

默认解释：

- `<35`：伪选择；
- `35—59`：有局部差异，但后果较弱；
- `60—79`：有效选择；
- `≥80`：会真实改变路线、关系、成本或长期能力。

若主角连续 `4—6` 章只被动响应而没有重要判断，系统应优先提出一个能够改变后续条件的决定。

系统不得为了提高能动性而强行制造永久二选一。机会成本可以是时间、顺序、风险、暴露、关系、债务或窗口，而不是每次都永久删除另一条路线。

---

# 15. 可理解的未知

必须分别计算“可理解性”和“结果未知度”。

```text
Legibility =
0.35 × GoalClarity
+ 0.30 × RuleClarity
+ 0.20 × ConsequenceClarity
+ 0.15 × InformationProvenance
```

```text
OutcomeUncertainty =
0.30 × DangerUnknown
+ 0.25 × OpponentPlanUnknown
+ 0.20 × MotivationUnknown
+ 0.15 × RewardOrResultUnknown
+ 0.10 × WorldTruthUnknown
```

健康状态通常是：

- 当前目标、失败条件和基础规则较清楚：`Legibility ≥ 65`；
- 最终结果仍不可预测：`OutcomeUncertainty = 35—75`。

若可理解性过低，优先写调查、规则验证、信息来源或局部答案，而不是继续增加谜题。

若结果未知度过低，优先引入真实选择、对手行动、代价或新的组合问题，而不是临时改规则。

---

# 16. 正史、人物与文风校验门

这些不是普通加分项，而是候选方案进入调度器之前的门槛。

## 16.1 Canon Gate

以下任一情况默认淘汰候选：

- 与明确事实冲突；
- 时间线不可能；
- 物品、资源、能力凭空出现；
- 已永久失去的内容无因返回；
- 角色使用其不知道的信息；
- 未经授权改写旧章；
- 结果依赖尚未建立的世界规则。

## 16.2 Character Fit

```text
CharacterFit =
0.25 × MotivationAlignment
+ 0.20 × KnowledgeAlignment
+ 0.20 × CapabilityAlignment
+ 0.20 × RelationshipAlignment
+ 0.15 × EmotionalContinuity
```

`CharacterFit < 75` 时，必须增加可见桥梁或改方案；明确违背人物底线且无原因时直接淘汰。

## 16.3 Style Fit

```text
StyleFit =
0.20 × POVAndTense
+ 0.20 × DictionRegister
+ 0.15 × SentenceRhythm
+ 0.15 × DialogueVoice
+ 0.15 × ExpositionDensity
+ 0.15 × EmotionalDistance
```

该分数用于发现明显漂移。作者可以有意改变文风，但必须明确授权，不能由模型以“升级写法”为名自行改写。

---

# 17. 线程优先级：现在最该写哪一条线

对每条活跃线程 `t` 计算：

```text
ThreadNeed_t =
0.24 × NarrativeDebt
+ 0.18 × DeadlineUrgency
+ 0.16 × PayoffReadiness
+ 0.14 × RecencyNeglect
+ 0.12 × GoalBlockage
+ 0.10 × ProtagonistRelevance
+ 0.06 × DiversityBonus
```

其中：

- `RecencyNeglect`：相对于该线程合理出现间隔，多久没有推进；
- `GoalBlockage`：它是否卡住其他重要线程；
- `DiversityBonus`：推进它能否避免连续写同一种内容。

线程高分只代表“值得处理”，不代表必须立即彻底解决。系统可以选择推进、部分兑现、制造选择或明确延后。

---

# 18. 调度器：什么时候写什么内容

调度器先执行硬门槛，再诊断当前状态，最后比较候选方案。

## 18.1 硬优先级

以下事项优先于普通评分：

1. 作者明确指定的下一章任务；
2. 上一章已经发生、下一章必须承接的即时后果；
3. 即将到期的故事内 deadline；
4. 严重超期的叙事债务；
5. 重大爽点之后尚未展示的 aftershock；
6. 正史、时间线和人物知识要求的必要场景。

## 18.2 默认状态—功能映射

| 当前诊断 | 下一章优先功能 |
|---|---|
| `P ≥ 75`、目标爽点 `S ≥ 80`、同类疲劳 `< 40` | `major_payoff` 或篇章高潮 |
| `P ≥ 75` 但成熟度 `M < 60` | `choice`、`partial_payoff`、`discovery` 或支付代价；禁止硬发大奖 |
| 最大叙事债务 `≥ 100` | 推进或兑现该承诺 |
| 重大爽点后 `1—3` 章且行为变化未展示 | `aftershock` |
| 最近五章平均进展过低 | `progress`，要求至少一个不可逆变化 |
| 主角连续多章缺乏有效决定 | `choice` |
| `P` 连续低于 `35` | 建立新目标、期限、竞争或真实机会成本 |
| `P` 连续高于 `85` | 局部控制、恢复、关系支援或阶段性兑现 |
| `Legibility < 60` | `discovery`、规则验证或局部回答 |
| 旧层级问题已解决且成果尚未转化 | `aftershock` 或新玩法展示 |
| 当前阶层跃迁已完成、旧策略空间已稳定 | `world_expansion`，旧成果必须保留 |

这张表是默认策略，不是死模板。作者可以覆盖。

## 18.3 候选章节评分

只对已经通过 `Canon Gate`、人物知识、因果来源和作者限制的候选方案评分：

```text
CandidateScore(c) = clamp(
  0,
  100,
  0.20 × ThreadNeedFit
  + 0.16 × PressureCurveFit
  + 0.16 × DebtUtility
  + 0.15 × ProgressGain
  + 0.12 × PayoffOrSetupUtility
  + 0.08 × AgencyGain
  + 0.05 × RiskFit
  + 0.05 × StructuralDiversity
  + 0.03 × StyleFit
  - 0.12 × RepetitionFatigue
  - 0.08 × FutureDamage
)
```

定义：

- `PressureCurveFit`：候选造成的压力变化是否符合当前阶段；
- `DebtUtility`：偿还重要旧债的价值减去新增债务；
- `PayoffOrSetupUtility`：若当前应兑现，使用爽点评分；若尚未成熟，评估该候选能提高多少未来成熟度；
- `RiskFit`：风险是否可信且不过载；
- `FutureDamage`：是否摧毁后续选择、资源结构、人物作用或规模增长空间。

在作者辅助模式中，系统默认呈现得分最高且结构不同的 `2—3` 个候选，而不是只显示一个“正确答案”。

若多个候选相差少于 `8` 分，视为同一可选区间，由作者依据审美选择。

自动模式也不得永远机械选择最高分；只能在通过门槛的高分候选中使用有限随机性，并记录原因，以防固定最优模板。

---

# 19. 爽点预算与冷却组

每个爽点都属于一个冷却组：

- 资源类；
- 战力类；
- 认知类；
- 社会地位类；
- 关系类；
- 世界真相类；
- 情绪清算类；
- 权限与玩法类。

默认强度预算：

- 小型即时回报：`5—10`；
- 中型胜利、升级或局部反转：`15—25`；
- 阶段性资源解放或构筑成型：`35—45`；
- 世界真相、身份跃迁或篇章高潮：`30—50`。

滚动十章建议总预算为 `80—120`，只用于发现连续过饱或长期欠账，不要求精确消费完毕。

默认冷却参考：

- 同类小爽点：`5—10` 章；
- 同一子类型的大爽点：`30—60` 章；
- 经济体系或身份体系级变化：`80—150` 章；
- 同一种低级资源的真正毕业：通常只发生一次。

不同冷却组可以交替。例如资源解放后，可以写能力展示、社会反馈、关系变化和世界谜题，而不是连续五次资源暴富。

---

# 20. 重大事件的余波义务

重大胜利、资源解放、身份跃迁、关系反转和世界揭露都必须生成 `Aftershock Obligations`。

默认要求：

- `1` 章内：主角或核心人物明确意识到变化；
- `1—3` 章内：行为方式发生变化；
- `2—5` 章内：关系、组织、市场或敌人作出反馈；
- `3—8` 章内：新的高阶瓶颈或责任显现。

重大爽点如果只出现一行奖励提示，随后几十章没有影响，视为未完成兑现。

---

# 21. 章节合同

在写正文前，系统必须生成一份可审查的 `Chapter Contract`。推荐结构：

```json
{
  "chapter": 48,
  "mode": "faithful_continuation",
  "continuation_boundary": {
    "last_canon_chapter": 47,
    "story_time": "第12日夜间",
    "pov": "苏牧限知视角"
  },
  "primary_thread": "resource_crystal_shortage",
  "primary_function": "major_payoff",
  "secondary_functions": ["aftershock_setup", "relationship_shift"],
  "reader_question": "自动箭匣是否终于能形成正循环？",
  "pressure": {
    "before": 82,
    "target_after": 38
  },
  "payoff_plan": {
    "type": "resource_liberation",
    "target_score": 85,
    "target_resource": "诡晶",
    "causal_source": "夜袭掉落与自动物资收集形成闭环",
    "problems_resolved": [
      "自动攻击的普通诡晶消耗焦虑",
      "一级制作台升级缺口"
    ],
    "must_change_behavior": [
      "重新开启自动攻击",
      "批量制造此前舍不得制造的基础物品"
    ],
    "must_not_resolve": [
      "高级诡晶短缺",
      "更高阶缆车核心材料"
    ],
    "aftershock_due_within": 3
  },
  "narrative_debt": {
    "advance": ["物资收集能力的真实价值"],
    "fully_pay": ["自动箭匣是否值得长期使用"],
    "new_major_hooks_allowed": 1
  },
  "progress": {
    "minimum_score": 25,
    "required_irreversible_change": "普通诡晶从核心焦虑降级为日常消耗"
  },
  "risk": {
    "required_cost": "此前已投入全部备用箭矢并承担夜袭风险",
    "must_not_be_cost_free": true
  },
  "agency": {
    "required_decision": "如何分配新获得的诡晶，而不是全部自动花掉"
  },
  "canon_constraints": [
    "不得改变箭匣已有消耗规则",
    "不得让高级材料凭空出现"
  ],
  "knowledge_constraints": [
    "主角只能根据已观察到的掉落和系统记录判断"
  ],
  "style_constraints": {
    "pov": "第三人称限知",
    "exposition_density": "medium",
    "dialogue_ratio": "low"
  },
  "forbidden_repetitions": [
    "再次用普通宝箱制造暴富",
    "只靠聊天频道连续震惊"
  ],
  "ending_state": "主角获得低级资源自由，同时确认下一层核心材料缺口",
  "commit_updates": [
    "resource_stock",
    "resource_pressure",
    "payoff_history",
    "thread_status",
    "aftershock_obligations"
  ]
}
```

章节合同描述必须发生的状态变化和边界，不规定每一句正文。

---

# 22. 正文生成规则

每个场景至少应存在：

```text
场景意图
→ 角色行动或选择
→ 世界响应
→ 可观察后果
```

正文不得用以下方式冒充进展：

- 大量重复说明已经知道的规则；
- 反复查看面板但状态没有意义变化；
- NPC 连续震惊却不改变行为；
- 敌人为了让主角赢而突然失智；
- 用“系统提示”代替因果；
- 用旁白宣布人物成长、地位或感情变化；
- 每章结尾都使用没有真实后果的假悬崖。

章节结尾至少满足一种：

- 当前问题得到阶段性回答；
- 一个决定被锁定并产生下一步后果；
- 新事实改变了原有判断；
- 世界或人物开始行动；
- 已有承诺逼近兑现；
- 状态发生足以推动下一章的变化。

不要求每章都极端卡点。

---

# 23. 生成后校验

正文生成后至少运行以下检查：

1. **Canon Validator**：事实、物品、能力、规则是否冲突。
2. **Timeline Validator**：时间、路程、冷却、伤势和并行事件是否成立。
3. **Knowledge Validator**：人物和叙述者是否越权知道信息。
4. **Character Validator**：行为是否符合目标、能力、关系和情绪惯性。
5. **Economy / Power Validator**：资源、消耗、战力和奖励是否守恒。
6. **Contract Validator**：章节合同要求是否真实发生。
7. **Debt Validator**：是否兑现了约定推进的承诺，是否无节制新增悬念。
8. **Payoff Validator**：奖励是否改变行为，来源和代价是否成立。
9. **Repetition Validator**：是否只是换名重复近期结构。
10. **Style Validator**：视角、声音、信息密度和角色对话是否漂移。

严重问题不得自动写入正史。系统应返回具体冲突、原文来源和可修改位置。

---

# 24. 写入正史与可重放历史

只有以下内容可以成为新正史：

- 作者明确批准的正文；
- 作者授权的自动模式输出且通过全部硬校验；
- 明确记录的修订事件。

每次写入后，系统更新：

- 新事件；
- 人物状态；
- 时间线；
- 资源和能力；
- 关系；
- 知识边界；
- 线程和叙事债务；
- 压力、进展、风险和疲劳；
- 新增的余波义务；
- 文风样本；
- 作者覆盖和修订记录。

推荐使用事件存储与快照：

```text
Immutable Source
+ Approved Change Events
→ Canon Projection
→ Chapter Planning State
```

任何时点都应能回答：

- 这条事实来自哪一章；
- 为什么下一章选择了这个线程；
- 哪次选择造成了当前后果；
- 某项指标为何变化；
- 作者何时批准了修订。

---

# 25. 推荐系统架构

```text
原始小说 / 作者资料
        ↓
Source Store（不可变）
        ↓
Extraction Agents（事实、人物、时间线、线程、文风）
        ↓
Canon Reconciler（冲突、置信度、作者确认）
        ↓
SQLite State / Event Store
        ↓
Deterministic Metric Engine
        ↓
Candidate Generator
        ↓
Scheduler + Hard Gates
        ↓
Chapter Contract
        ↓
Drafting LLM
        ↓
Validators
        ↓
Author Approval
        ↓
Canon Commit + Snapshot
```

架构原则：

```text
LLM at the edges;
deterministic state, metrics and validation at the center;
author above both.
```

建议：

- 原始正文：不可变文本文件或对象存储；
- 可变状态、事件、指标：SQLite；
- 类型配置和作者偏好：YAML；
- 章节合同、审查报告和导出：JSON / Markdown；
- 每条结构化事实保留来源位置和置信度。

LLM 可以抽取、提出候选、解释和写作；不能自我声明其抽取必然正确，也不能绕过状态中心直接改正史。

---

# 26. 最小数据表

第一版至少需要：

- `source_documents`
- `chapters`
- `source_spans`
- `entities`
- `facts`
- `events`
- `timeline_entries`
- `character_states`
- `knowledge_edges`
- `relationships`
- `resources`
- `capabilities`
- `threads`
- `promises`
- `payoff_events`
- `repetition_tags`
- `style_profiles`
- `author_directives`
- `candidate_plans`
- `chapter_contracts`
- `validation_reports`
- `canon_commits`
- `snapshots`

不应在第一版模拟每个路人的全部人生，也不应预建可以表达所有文学形式的万能本体。

---

# 27. 第一版必须实现什么

V1 正式实现以下六个长期指标：

1. `Pressure`
2. `Payoff`
3. `Narrative Debt`
4. `Progress`
5. `Repetition Fatigue`
6. `Risk Credibility`

同时实现两个续写硬门：

7. `Canon / Timeline / Knowledge Gate`
8. `Character / Style Fit`

`Agency` 和 `Legibility / Uncertainty` 可以先作为诊断项，但数据结构从第一版保留。

V1 必须能够：

- 导入一部已开始的小说；
- 生成可追溯的正史、人物、时间线和线程状态；
- 给出当前最需要推进的三条线；
- 为下一章生成结构不同的候选方案；
- 解释评分和淘汰原因；
- 生成章节合同；
- 续写正文；
- 检查冲突、重复、债务和爽点后果；
- 经作者批准后更新状态。

V1 不必承诺：

- 用公式预测真实读者留存率；
- 自动判断所有文学价值；
- 模拟整个世界每个 NPC；
- 自动替作者决定主题、结局和人物命运；
- 一次导入后永远不需要人工纠错。

---

# 28. 类型配置，而不是万能公式

不同类型可以调整：

- 压力目标区间；
- 悬念周期；
- 爽点密度；
- 恢复章节长度；
- 关系、谜题、动作和世界扩张的权重；
- 章节字数和节奏；
- 是否存在升级、资源、战力或社会地位体系。

例如：

- 升级爽文提高 `Payoff`、`Progress`、`CompoundingControl` 权重；
- 悬疑提高 `NarrativeDebt`、`Legibility` 和局部答案义务；
- 感情小说提高关系状态、双方能动性和情绪惯性权重；
- 历史小说提高时间线、制度因果和信息边界权重；
- 文学小说可以降低外部事件密度，但不能免除人物和意义上的真实变化。

类型配置不得覆盖原文已经建立的承诺。

---

# 29. 设计警报

以下情况触发高优先级警报：

- 续写前没有重建正史；
- 摘要被当作完整记忆；
- 推断被当作事实；
- 原文冲突被静默修复；
- 人物为了剧情方便突然改变目标或智力；
- 主角长期没有决定，只被系统推着走；
- 爽点没有铺垫、来源、代价或后续；
- 同类资源或打脸结构连续重复；
- 旧问题解决后仍强迫主角永久重复低级劳动；
- 奖励只增加数字，不扩大策略空间；
- 风险只写在说明里，从不兑现；
- 连续新增谜题而不还债；
- 新地图无因清零旧成果；
- NPC 只在主角出现时存在；
- 旁白代替关系变化和社会反馈；
- 每章都追求最大爽点；
- 公式最高分被误当成唯一正确故事；
- Prompt 被用来掩盖状态、因果或引擎缺陷；
- 为了未来可能使用而提前建立万能抽象。

---

# 30. 最小评审问题

每次规划下一章，至少回答：

1. 当前续写边界在哪里？
2. 哪些事实、人物状态和知识边界不可违反？
3. 读者现在最在意的三个问题是什么？
4. 哪项压力正在上升，哪项已经过载？
5. 哪个承诺债务最高，是否到了推进或兑现窗口？
6. 下一章需要的主要功能是什么，而不是需要哪种表面套路？
7. 本章会产生什么不可逆变化？
8. 主角或关键人物会作出什么有后果的决定？
9. 奖励、反转或失败的来源和代价是什么？
10. 最近是否已经用过相似结构？
11. 本章完成后，行为、关系或世界会怎样改变？
12. 它是否仍像这本小说，而不是像模型熟悉的另一部小说？

若答案只存在于规划文字中，而正文和状态更新中没有证据，则视为未完成。

---

# 31. 宣言

我们不是在制造一台会用固定套路灌出章节的机器。

我们在制造一个能够读懂已经写下的历史、记住作者承诺、管理长期节奏、提出可解释选择并尊重作者最终判断的创作系统。

它应让作者感到：

> 我不再需要独自记住几百章中的每个资源、人物、承诺和伏笔；系统能告诉我读者现在在等什么、哪种爽点已经成熟、哪里正在重复、下一章有哪些真正不同的走法。但故事为何如此、人物最终成为谁，仍然由我决定。

对于成长型爽文，最终读者感受仍然可以是：

> 主角曾经失去控制，但逐步看懂规则；他用自己的判断和非对称杠杆挣得成果；这些成果改变了后续行动，并让他带着真实积累进入更大的世界。

公式负责守住长期节奏，正史负责守住因果，LLM 负责提出和表达可能性，作者负责赋予小说方向与意义。
