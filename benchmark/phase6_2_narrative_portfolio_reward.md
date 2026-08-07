# Phase 6.2 — Innovation Reward + Multi-Horizon Narrative Portfolio

Phase 6.2 在 Phase 6 的 `InnovationControl` 之上增加“创新元素奖励”和“多时间尺度叙事组合”。
它不是新的事实层，也不是自动批准器。

## 硬门优先

候选仍然先经过 Canon、Timeline、Knowledge、Capability、Resource、Author Directive、Edition
和其他既有 Hard Gates。任何 Hard Gate 失败的候选直接 `ineligible`，其
`InnovationRewardBreakdown.capped_innovation_reward` 与 `final_selection_score` 均为 0；创新奖励
不能覆盖事实冲突。

Hard Gate 通过后保留原有 `base_candidate_score`，再计算：

```text
final_selection_score = base_candidate_score
  + capped_innovation_reward
  - new_narrative_debt_cost
  - overdue_debt_penalty
  - integration_cost_penalty
  - cosmetic_penalty
  - orphan_penalty
  - repetition_penalty
  - over_deferral_penalty
```

`base_candidate_score` 仍使用既有配置和权重；`final_selection_score` 允许超过 100，且只在
通过 Hard Gates 的候选之间排序。`InnovationLevel` 只改变奖励倍率和上限：

| Level | multiplier | reward cap |
|---|---:|---:|
| MINIMAL | 0.35 | 6 |
| LOW | 0.65 | 12 |
| MEDIUM | 1.00 | 24 |
| HIGH | 1.35 | 36 |
| BOLD | 1.70 | 50 |

没有真实 `MEANINGFUL_NOVELTY` 元素时，BOLD 也不会凭空获得奖励。

## 结构化创新合同

`CandidateInnovationPreview` 可以声明：

- `expected_innovation_elements`：`InnovationElement`，包括 focus、meaningful/cosmetic、
  magnitude、causal source、before/after state、future options 和 horizon roles；
- `expected_element_synergies`：只有存在共同因果链、共同状态变化和共同未来效果才计入；
- `expected_cross_horizon_synergies`：连接 SHORT/MID/LONG 的因果链；
- `expected_earned_recombinations`：将已有 Earned Capability、Resource、Knowledge 或关系
  杠杆放进新的有效上下文；
- `expected_payoffs`、`expected_new_debts` 与 `expected_narrative_delta`。

同一 focus 的元素奖励按 100% / 60% / 30% / 0 递减；元素协同为 2-way +5、3-way +10、4+
+16；Earned Recombination 按 LOCAL/SUBSTANTIAL/MAJOR 为 +3/+6/+9。所有数值都是候选比较
信号，不是文学总分，也不替代作者选择。

Chapter Contract 会冻结 `innovation_commitments` 和 `narrative_portfolio`。Draft 的
`InnovationTrace` 则记录 realized elements、synergies、horizon effects、payoffs、new debt
和 before/after delta。Python 会独立重算 realized reward；请求的 level 不会被当作实际创新。

## Multi-Horizon Narrative Portfolio

`NarrativePortfolioSnapshot` 在 Candidate Planning 之前从当前 Boundary 的 active threads 和
promises 冻结，分为：

- `SHORT`：约 1–3 章，优先及时回答或推进；
- `MID`：约 4–15 章，允许连续发展；
- `LONG`：约 15–60+ 章，允许保持开放，但仍需留下可见进展。

线程生命周期为 `SETUP`、`DEVELOPING`、`PAYOFF_READY`、`PARTIALLY_PAID`、`RESOLVED`、
`DORMANT`。已有 `PAYOFF_READY` 或 overdue debt 被无代价延后会受到软惩罚；新债务也会按
horizon 和 magnitude 产生维护成本。SHORT resolve + MID advance、MID resolve + LONG advance
以及三段式 answer-and-expand 会得到额外奖励。

Question Balance 会分别记录 answered、partially paid、materially advanced 和 newly opened。
0/0/0 却新增至少两个问题时标记 `OVER_DEFERRED_NARRATIVE`；连续两次仍延后时提高软惩罚。
这不是 Validator hard fail。

## Draft 防火墙

Draft handoff 明确要求：内核、合同和 Validator 负责治理，正文只写人物的感知、选择、行动和
后果。`detect_semantic_policy_leak()` 检查反复出现的“暂不确认—保留退路—等待验证”这类治理
型叙事惯性，但不以固定句子黑名单判定。既有 `SYSTEM_LANGUAGE_LEAK` 检查继续保留。

## Live calibration

真实校准仍通过 Windows Codex Desktop 的文件 handoff，不由 Python 生成文学语义、候选或正文：

```powershell
uv run --no-sync python scripts/phase6_innovation_control.py prepare --run-label p62-live
# 按 WORK_QUEUE.md 处理 L1/L3/L5 的 READY_FOR_CODEX handoff
uv run --no-sync python scripts/phase6_innovation_control.py collect --run-label p62-live
uv run --no-sync python scripts/phase6_innovation_control.py evaluate --run-label p62-live
```

`collect` 在 Hard Gate/十项 Validator 后保存 expected/realized reward、under-delivery warning、
Question Balance 和 semantic policy leak；`evaluate` 仍只在 generation closed 后读取 hidden truth。
既有 Phase 5.1/Phase 6 结果保持为历史基线，不被 Phase 6.2 事后重写。
