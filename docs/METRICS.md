# 指标、公式与配置

## 原则

公式来源是 `Novel_Authoring_System_Constitution_V2.md` 第 7—18 节；实现位于 `metrics/formulas.py`，默认值位于 `config/default.yaml`。指标用于诊断、排序和解释，不能绕过正史、时间线、知识、人物、经济/战力、作者和文风硬门。

所有常规分量为 0—100。重复结构相似度的单维输入是 0—1；实现先加权，再乘 100 得到疲劳分。越界、非有限数、字段缺失/多余和非法分母会显式报错。

## 1. Pressure

宪法 7.1：

```text
P = 0.25T + 0.20S + 0.20D + 0.15U + 0.10C + 0.10F
```

| 分量 | 权重 |
|---|---:|
| threat | 0.25 |
| scarcity | 0.20 |
| deadline | 0.20 |
| uncertainty | 0.15 |
| social_conflict | 0.10 |
| failure_accumulation | 0.10 |

阈值：`≤30` 低压；`(30,55]` 正常推进；`(55,75]` 明显紧张；`(75,90]` 高潮准备；`>90` 极端压力，不应长期维持。

多线程全局压力为 salience 加权平均；总 salience 为 0 时返回 `None`，不伪造 0 分。

## 2. Narrative Debt

宪法 8：

```text
AgeRatio = clamp(0, 1.5, AgeChapters / TargetMaxAge)
ReminderFactor = 1 + 0.12 × min(ReminderCount, 5)
Debt = clamp(0, 150,
  100 × Importance × ReaderVisibility
      × (1 - PromiseProgress)^1.2
      × AgeRatio × ReminderFactor)
```

阈值：`<40` 健康；`40—<80` 近期推进；`80—<110` 高债务；`110—<130` 严重债务；`≥130` 必须兑现、重构或经作者批准延后。

新增悬念负载约束：

```text
NewHookLoad ≤ FullPayoffCount + 0.6 × PartialAdvanceCount + GenreAllowance
```

默认 `GenreAllowance=1`。Chapter Contract 还给出本章 `new_major_hooks_allowed`，Debt Validator 逐项核对承诺推进和兑现。

## 3. Progress

宪法 9：

```text
G = 0.20 PermanentGrowth
  + 0.20 WorldStateChange
  + 0.15 RelationshipChange
  + 0.15 KnowledgeChange
  + 0.15 GoalAdvance
  + 0.15 StrategyExpansion
```

阈值：`<10` 低进展；`10—<25` 局部进展；`≥25` 有效不可逆进展。默认滚动窗口 8 章；若其中低于 10 分的比例达到 `62.5%`，触发停滞警报。历史不足 8 章时返回 `None`，不提前下结论。

## 4. Payoff

宪法 10。CLI 输入 Maturity、Impact、Causality、AfterValue；Novelty 固定为：

```text
N = 100 - RepetitionFatigue
```

净爽点评分：

```text
S = clamp(0, 100,
    0.24M + 0.22I + 0.14N + 0.16C + 0.18A + 0.06SF
  - 0.12RF - 0.10FD)
```

| 组成 | 默认子权重 |
|---|---|
| Maturity | target pressure .25、setup depth .20、waiting readiness .20、cost paid .20、arc fit .15 |
| Impact | relative scale .25、constraint removal .25、behavior change .20、future capacity .15、social/visual proof .15 |
| Causality | causal chain .30、rule consistency .25、meaningful cost .25、seeded earlier .20 |
| AfterValue | new action space .30、decision change .25、higher-tier need .25、social/world effect .20 |

阈值：`<50` 不适合大兑现；`50—<65` 小型窗口；`65—<80` 中型窗口；`80—90` 阶段性大爆发；`>90` 篇章高潮级。

资源解放额外硬门：Resource Pressure `≥70`、铺垫 `≥8` 章、至少 2 次受阻决策、同类疲劳 `≤35`，并同时具有因果来源、已付代价/风险、兑现后行为变化和下一资源层级。

重大 payoff 在验证时要求来源、代价、行为变化和至少四类余波计划；批准时创建 1、1—3、2—5、3—8 章四个 Promise。

## 5. Repetition Fatigue

宪法 12。单个历史章节的结构相似度：

```text
Sim = 0.30 EventSourceSimilarity
    + 0.25 SolutionMethodSimilarity
    + 0.20 PayoffTypeSimilarity
    + 0.15 SceneTopologySimilarity
    + 0.10 EmotionalOutcomeSimilarity
```

各 similarity 为 0—1。距离衰减 `decay_i = exp(-distance_i / τ)`，默认 `τ=12`：

```text
RF = 100 × Σ(decay_i × Sim_i) / Σ(decay_i)
```

无历史时返回 0，并写入 `no_history` 诊断。阈值：`<35` 新鲜；`35—<60` 轻中度；`60—<75` 高疲劳；`≥75` 默认拒绝，除非方案形成升级、反讽或闭环且硬门允许。

默认审查最近 20/50 章。Repetition Validator 还检查 Chapter Contract 明确禁止的结构标签和完全重复的近期 signature。

## 6. Risk Credibility

宪法 13：

```text
R = 0.25 RealizedCostRate
  + 0.20 ConsequenceClarity
  + 0.20 OppositionEffectiveness
  + 0.20 ProtectionLimitVisibility
  + 0.15 InformationLimits
```

`<40` 表示风险可信度偏低，需要让已经强调的风险产生真实代价；`>85` 表示风险极可信，若总体压力也过高可安排局部控制或回报；其余为可信区间。

## 辅助门与排序

### Agency 诊断

宪法 14；五项输入均为 0—1，使用几何平均：

```text
Agency = 100 × (ValueBalance × ConsequenceDifference
  × InformationAdequacy × OpportunityCost × LongTermEffect)^(1/5)
```

`<35` 伪选择；`35—59` 局部差异；`60—79` 有效选择；`≥80` 路线级选择。任一维为 0 会把总分压到 0，避免用其他高分掩盖无后果选择。连续 4—6 章只有被动响应时应优先提出真实决定。

### Legibility / Outcome Uncertainty 诊断

宪法 15：

```text
Legibility = .35 GoalClarity + .30 RuleClarity
            + .20 ConsequenceClarity + .15 InformationProvenance

OutcomeUncertainty = .30 DangerUnknown + .25 OpponentPlanUnknown
                   + .20 MotivationUnknown + .15 RewardOrResultUnknown
                   + .10 WorldTruthUnknown
```

健康参考是 `Legibility ≥65` 且 `OutcomeUncertainty=35—75`。这两项和 Agency 以可选字段保留在 `MetricInputBundle`；存在输入时 `diagnose` 持久化诊断结果，但不取代六个核心指标或硬门。

### Character Fit

```text
0.25 motivation + 0.20 knowledge + 0.20 capability
+ 0.20 relationship + 0.15 emotional continuity
```

最低硬门为 75；任何 `character_bottom_line_violations` 直接 FATAL。

### Style Fit

POV/tense .20、diction .20、sentence rhythm .15、dialogue voice .15、exposition density .15、emotional distance .15。宪法没有规定数字硬门；V1 在 `<75` 时发 WARNING，明确 style boundary violation 才是 ERROR。

### Thread Need

叙事债务 .24、deadline urgency .18、payoff readiness .16、recency neglect .14、goal blockage .12、protagonist relevance .10、diversity bonus .06。每次规划只向 Codex暴露前三条优先线程。

### Candidate Score

正向：ThreadNeedFit .20、PressureCurveFit .16、DebtUtility .16、ProgressGain .15、Payoff/Setup .12、Agency .08、Risk .05、Diversity .05、Style .03；负向：RepetitionFatigue -.12、FutureDamage -.08。分差小于 8 视为同一审美可选区间。硬门先执行，失败候选分数归零但仍保存原因。

## 输入与解释输出

`novel diagnose` 读取 `MetricInputBundle` JSON，包含 `pressure`、`narrative_debt`、`progress`、`payoff`、`repetition_history`、`risk_credibility`，可选 `agency`、`legibility`、`outcome_uncertainty` 和 `evidence`。完整字段以 `metrics/engine.py` 的 Pydantic 模型为准。

每个 `MetricResult` 输出：

```json
{
  "metric": "Pressure",
  "score": 66.5,
  "inputs": {},
  "evidence": [],
  "threshold_interpretation": "明显紧张",
  "recommended_action": "安排决定、代价或局部兑现"
}
```

数据库还保存 `as_of_event_seq`、`config_hash`、`formula_id=constitution-v2` 和创建时间，确保能回答某次指标为何得到该结果。

## 配置覆盖

默认配置是 `config/default.yaml`。用单独 YAML 做最小覆盖：

```yaml
metrics:
  progress:
    stagnation_window: 10
  character_fit:
    minimum: 80
```

```powershell
.\.venv\Scripts\novel.exe diagnose --book-id my-book --config .\config\author.yaml
```

配置递归合并，未知顶层字段会被拒绝。修改权重属于方法学变化，应保留覆盖文件并让新的 `config_hash` 区分历史结果。
