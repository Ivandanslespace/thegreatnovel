# Phase 4 四个盲测的创新性分析与对比

## 结论先行

这四个测试验证的是“受约束的创新能力是否被正确建模和隔离”，不是四次真实文学创作质量竞赛。

- 在结构层面，四个边界都成功提供了三种候选 Lens：`CONTINUITY_ACTIVE_THREAD`、`EARNED_OPPORTUNITY`、`FORWARD_EXPANSION`。
- 在治理层面，四个边界都产生了一个 `FORWARD_NOVELTY`，带有 causal source、introduction event、new state、conflicts checked，并且没有 retroactive claim。
- 在生成正文层面，四个 `generated/chapter_*.md` 去除边界数字后完全相同，长度均为 181 个字符；因此不能据此宣称 20、35、50、75 章产生了不同的文学创新。
- 隐藏真值只在 generation snapshot 之后读取。它们展示了四个边界原本可能出现的不同剧情方向，但不应被当作生成阶段已经命中的内容。

所以，本轮的准确结论是：

> Phase 4 已经证明系统能够安全地容纳 Forward Novelty；尚未证明当前 benchmark 能够测量真实生成内容的创新质量。

## 测试对象与证据

四个独立测试目录：

- `library/phase4-blind-phase4c-020`
- `library/phase4-blind-phase4c-035`
- `library/phase4-blind-phase4c-050`
- `library/phase4-blind-phase4c-075`

本报告比较了每个目录下的：

- `benchmark/phase4_run/candidate_sets/`
- `benchmark/phase4_run/contracts/`
- `benchmark/phase4_run/generated/`
- `benchmark/phase4_run/portfolio_diagnostics.json`
- `benchmark/phase4_run/evaluation.json`
- `benchmark/hidden_ground_truth/`

hidden ground truth 只用于生成结束后的事后分析；四个 generation snapshot 均记录 `truth_revealed: false`。

## 结构化创新对比

| 可见边界 | Distill 维度 | Findings | Literary Arc | Craft Controls | Continuity Candidates | 候选数 | Forward Novelty | Validator | 生成正文差异 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 20 | 9 | 12 | 1 | 2 | 1 | 3 | 1 | 10/10 | 仅编号不同 |
| 35 | 9 | 12 | 1 | 2 | 1 | 3 | 1 | 10/10 | 仅编号不同 |
| 50 | 9 | 12 | 1 | 2 | 1 | 3 | 1 | 10/10 | 仅编号不同 |
| 75 | 9 | 12 | 1 | 2 | 1 | 3 | 1 | 10/10 | 仅编号不同 |

四个测试的组合诊断也完全一致：

- `continuity_count = 1`
- `earned_usage_count = 3`
- `earned_surface_usage_coverage = 1.0`
- `forward_novelty_count = 1`
- `wildcard_count = 1`
- 三个 Lens 各一个
- 无诊断 warning

这说明四个边界的“创新接口覆盖率”一致，但不代表剧情创意一致性良好；恰恰相反，正文的一致性说明当前 fixture 的语义变化不足。

## 四个边界的内容创新对比

### 前 20 章边界

生成合同只表达了：基于可用资源作出一个带明确成本的临时选择，并把新状态保持为 provisional。

隐藏真值在生成后显示出的具体创新方向是：

- 新的丧尸威胁
- 天赋触发额外攻击
- 攻击特效继承
- 经验收益变化
- 红薯兼具食物与种子用途

当前生成正文没有具体呈现这些事件，只完成了“允许引入一个有代价的新选择”的抽象占位。

### 前 35 章边界

隐藏真值的创新方向转为：

- 转盘的幸运/厄运结构
- 力量果实带来的永久属性变化
- 新职业技能书与战地医生职业
- 资源稀缺条件下的高收益选择

当前生成正文仍然与前 20 章相同，只替换为 `change-35-c`、`required-cost-35-c` 等边界标识，没有形成“资源升级、职业分化或概率风险”的语义差异。

### 前 50 章边界

隐藏真值的创新方向是：

- 高阶舔食者造成的群体伤亡
- 液化气罐炸弹这一非系统图纸的手工知识
- 药品交换与信息交换
- 夜间“诡异”威胁和纜车安全压力

这一边界本来最适合检验“已有 Craft Control 如何转化为社会系统、资源交易和新威胁”，但当前生成正文没有展开这些具体因果。

### 前 75 章边界

隐藏真值的创新方向是：

- 长枪能力进入持续战斗
- 突刺、连击、横扫等能力组合
- 单人击杀多只猫妖后的旁观者反馈
- 跨纜线群体冲突
- 战利品、撤离与种植资源的后续管理

这些内容正好覆盖“长期写作观察”和“可用能力/资源状态”的分离场景；当前生成正文仍只有抽象的 provisional choice，没有表现出能力组合、社会反馈或资源转化。

## 创新性分层判断

| 层级 | 本轮结果 | 判断 |
|---|---|---|
| Schema innovation | 三种 Lens、Novelty Provenance、Forward Boundary 均存在 | 已通过 |
| Governance innovation | 新内容必须有 causal source、new state、conflicts checked，且不得 retroactive claim | 已通过 |
| Portfolio innovation | 每个边界都有 continuity / earned / forward 三类候选 | 仅证明接口覆盖，未证明语义差异 |
| Prose innovation | 四个生成正文归一化后完全相同 | 未通过文学差异性证明 |
| Boundary sensitivity | 20、35、50、75 的生成文本没有随可见正文增长而改变 | 未证明 |
| Hidden-future recall | token overlap 为 0.0；该指标只作辅助诊断 | 未形成语义命中结论 |

## 对四个测试的排序

如果排序的是“系统创新治理覆盖”，四个测试并列：

`20 = 35 = 50 = 75`

如果排序的是“当前生成正文的文学创新”，也只能并列为“未区分”：四个输出经过边界编号归一化后完全一致。

不能根据隐藏真值给四个生成结果打“命中率”排名，因为隐藏真值明确没有进入生成上下文。四个隐藏章节只能说明每个边界存在丰富且不同的真实后续方向，而当前 fixture 没有把这些方向注入到生成文本中。

## 下一步应如何做真正的创新对比

要回答“融合版是否比单独 Distill 更有创新”，下一轮应使用同一边界、同一作者指令，分别生成：

1. 仅使用 Distill Skill 的候选与章节。
2. 使用 Distill Package + Runtime Baseline + Context Router 的融合候选与章节。

然后对每个版本记录：

- 新事件、新实体、新能力、新地点、新社会关系的数量与证据。
- 新内容是否有 `FORWARD_NOVELTY` 和明确 causal source。
- 是否复用了已有事件模板，是否重复近期场景/句式。
- 新状态是否能改变后续选择空间，而不是只改写形容词。
- 长枪、突刺、连击、M500、动态视觉等具体能力只能从真实 source/evidence 中抽取，不能硬编码成评分规则。
- 由人工或独立评审对九个维度分别比较，而不是用 token overlap 代替文学判断。

本报告因此把当前四测定位为“创新边界与安全合同测试”，而不是“融合生成的创新质量结论”。
