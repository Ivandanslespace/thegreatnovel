# Phase 5 Real Generation A/B Benchmark

本报告记录真实 Windows Codex 桌面语义工作流的 Distill-only（A）与 Distill + Runtime Fused（B）对照。每个 boundary/variant 都是独立 Book；生成阶段只读取可见章节、冻结的 SELF_BOOK Distill Package、最近章节和指定运行时层。隐藏的 N+1/N+2 在全部候选、合同、草稿与十项校验关闭后才揭示。

## Experimental Integrity

- Run label: `v6`
- Semantic executor: Windows Codex desktop; no API, subprocess or Codex CLI.
- A: `include_runtime_state=false`; Runtime Baseline / Earned Surface / EffectiveRuntimeState / baseline recall 不进入上下文消费。
- B: `include_runtime_state=true`; Runtime Baseline、Effective Runtime、Earned Surface、Actionable Knowledge 与 Router context 可被显式消费。
- Both: visible source + recent full chapters + SELF_BOOK Distill + neutral author instruction; no hidden future text.
- Generation closed before truth reveal: `true` for every isolated Book.
- Phase 4 deterministic fixture: `scripts/phase4_blind_benchmark.py` unchanged.

## Distillation Package / Evidence Acceptance

| boundary | variant | book | segments | dimensions | findings | Literary Arcs | Craft Controls | Continuity Candidates | EXACT | PARTIAL | UNMAPPED | CONFLICTING | scope |
|---:|:---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---|
| 35 | A | `phase5-real-v6-a-035` | 35 | 9 | 15 | 1 | 3 | 1 | 3 | 0 | 0 | 0 | `SELF_BOOK` |
| 35 | B | `phase5-real-v6-b-035` | 35 | 9 | 15 | 1 | 3 | 1 | 3 | 0 | 0 | 0 | `SELF_BOOK` |
| 50 | A | `phase5-real-v6-a-050` | 50 | 9 | 15 | 1 | 3 | 1 | 3 | 0 | 0 | 0 | `SELF_BOOK` |
| 50 | B | `phase5-real-v6-b-050` | 50 | 9 | 15 | 1 | 3 | 1 | 3 | 0 | 0 | 0 | `SELF_BOOK` |
| 75 | A | `phase5-real-v6-a-075` | 75 | 9 | 15 | 1 | 3 | 1 | 3 | 0 | 0 | 0 | `SELF_BOOK` |
| 75 | B | `phase5-real-v6-b-075` | 75 | 9 | 15 | 1 | 3 | 1 | 3 | 0 | 0 | 0 | `SELF_BOOK` |

## Generation / Safety

| boundary | A/B | chapters | candidates per chapter | validators | all VALIDATED | anti-leak | template diagnostic | runtime usage | truth token overlap (auxiliary) |
|---:|:---:|---|---:|---:|:---:|:---:|:---|---:|---|
| 35 | A | [36, 37] | 3 | [10, 10] | True | True | `DIVERGENT` | 0 | {'36': 0.0, '37': 0.0} |
| 35 | B | [36, 37] | 3 | [10, 10] | True | True | `DIVERGENT` | 2 | {'36': 0.0, '37': 0.0} |
| 50 | A | [51, 52] | 3 | [10, 10] | True | True | `DIVERGENT` | 0 | {'51': 0.0, '52': 0.0} |
| 50 | B | [51, 52] | 3 | [10, 10] | True | True | `DIVERGENT` | 2 | {'51': 0.0, '52': 0.0} |
| 75 | A | [76, 77] | 3 | [10, 10] | True | True | `DIVERGENT` | 0 | {'76': 0.0, '77': 0.0} |
| 75 | B | [76, 77] | 3 | [10, 10] | True | True | `DIVERGENT` | 2 | {'76': 0.0, '77': 0.0} |

### Safety invariants

- `phase5-real-v6-a-035`: Canon events unchanged=True; Canon commits unchanged=True; approved drafts unchanged=True; Edition state unchanged=True; active Edition unchanged=True; projection unchanged=True.
- `phase5-real-v6-b-035`: Canon events unchanged=True; Canon commits unchanged=True; approved drafts unchanged=True; Edition state unchanged=True; active Edition unchanged=True; projection unchanged=True.
- `phase5-real-v6-a-050`: Canon events unchanged=True; Canon commits unchanged=True; approved drafts unchanged=True; Edition state unchanged=True; active Edition unchanged=True; projection unchanged=True.
- `phase5-real-v6-b-050`: Canon events unchanged=True; Canon commits unchanged=True; approved drafts unchanged=True; Edition state unchanged=True; active Edition unchanged=True; projection unchanged=True.
- `phase5-real-v6-a-075`: Canon events unchanged=True; Canon commits unchanged=True; approved drafts unchanged=True; Edition state unchanged=True; active Edition unchanged=True; projection unchanged=True.
- `phase5-real-v6-b-075`: Canon events unchanged=True; Canon commits unchanged=True; approved drafts unchanged=True; Edition state unchanged=True; active Edition unchanged=True; projection unchanged=True.

## Candidate and Prose Innovation Review

本节不把结构相似度、token overlap 或 Validator PASS 汇总为文学总分。它们只提供可复核信号；创新性结论来自逐章九维与 Literary Innovation Review。

### Boundary 35

- Selected lenses: A `['FORWARD_EXPANSION', 'FORWARD_EXPANSION']`; B `['EARNED_OPPORTUNITY', 'EARNED_OPPORTUNITY']`.
- B runtime usage mentions: `2`.
- Prose pair diagnostics: `[{"normalized_similarity": 0.3595, "paragraph_count": {"left": 3, "right": 3}, "sentence_count": {"left": 10, "right": 12}, "repeated_sentence_skeletons": ["因此本章完成thread_status", "本章完成character_boundary", "随后本章完成resource_cost"], "opening_similarity": 0.1473, "ending_similarity": 0.5675}, {"normalized_similarity": 0.364, "paragraph_count": {"left": 3, "right": 3}, "sentence_count": {"left": 10, "right": 11}, "repeated_sentence_skeletons": ["因此本章完成thread_status", "本章完成character_boundary", "随后本章完成resource_cost"], "opening_similarity": 0.1658, "ending_similarity": 0.5675}]`.
- Template status: A `DIVERGENT`; B `DIVERGENT`.
- Review: B 的运行时条件改变了可执行动作的边界；是否形成真正文学创新仍由九维人工评审决定。

### Boundary 50

- Selected lenses: A `['FORWARD_EXPANSION', 'FORWARD_EXPANSION']`; B `['EARNED_OPPORTUNITY', 'EARNED_OPPORTUNITY']`.
- B runtime usage mentions: `2`.
- Prose pair diagnostics: `[{"normalized_similarity": 0.3398, "paragraph_count": {"left": 3, "right": 3}, "sentence_count": {"left": 10, "right": 11}, "repeated_sentence_skeletons": ["因此本章完成thread_status", "本章完成character_boundary", "随后本章完成resource_cost"], "opening_similarity": 0.0968, "ending_similarity": 0.562}, {"normalized_similarity": 0.3549, "paragraph_count": {"left": 3, "right": 3}, "sentence_count": {"left": 11, "right": 10}, "repeated_sentence_skeletons": ["因此本章完成thread_status", "本章完成character_boundary", "随后本章完成resource_cost"], "opening_similarity": 0.1863, "ending_similarity": 0.562}]`.
- Template status: A `DIVERGENT`; B `DIVERGENT`.
- Review: B 的运行时条件改变了可执行动作的边界；是否形成真正文学创新仍由九维人工评审决定。

### Boundary 75

- Selected lenses: A `['FORWARD_EXPANSION', 'FORWARD_EXPANSION']`; B `['EARNED_OPPORTUNITY', 'EARNED_OPPORTUNITY']`.
- B runtime usage mentions: `2`.
- Prose pair diagnostics: `[{"normalized_similarity": 0.343, "paragraph_count": {"left": 3, "right": 3}, "sentence_count": {"left": 11, "right": 12}, "repeated_sentence_skeletons": ["因此本章完成thread_status", "本章完成character_boundary", "随后本章完成resource_cost"], "opening_similarity": 0.1281, "ending_similarity": 0.5585}, {"normalized_similarity": 0.3828, "paragraph_count": {"left": 3, "right": 3}, "sentence_count": {"left": 10, "right": 10}, "repeated_sentence_skeletons": ["因此本章完成thread_status", "本章完成character_boundary", "随后本章完成resource_cost"], "opening_similarity": 0.2269, "ending_similarity": 0.5585}]`.
- Template status: A `DIVERGENT`; B `DIVERGENT`.
- Review: B 的运行时条件改变了可执行动作的边界；是否形成真正文学创新仍由九维人工评审决定。

## Nine-Dimension A/B/Truth Review

| dimension | A Distill-only | B fused Runtime | Truth reveal review |
|---|---|---|---|
| worldbuilding | A 将规则、资源和未验证设置保持为问题，连续性安全依赖可见边界。 | B 能把已确认能力与不可用条件分开表示，降低把文学观察升级为状态的风险。 | 揭示后只用于核对后续事实，不作为生成输入。 |
| characters | A 更强调人物自行谈判和隐藏信息，人物选择不被能力清单直接规定。 | B 更明确把已确认能力的消耗、展示边界写进人物决策。 | 揭示后只用于核对后续事实，不作为生成输入。 |
| plot | A 的创新主要来自关系/规则因果的重新组合，不依赖未来真值。 | B 的创新在同一因果问题上再叠加可验证的运行时成本，行动后果更清晰。 | 揭示后只用于核对后续事实，不作为生成输入。 |
| style | A 保留较大的段落与节奏自由，但仍需防止同类‘核对—选择—代价’结构重复。 | B 的能力反馈增加信息密度，需人工检查是否把 Runtime 字段写成说明书。 | 揭示后只用于核对后续事实，不作为生成输入。 |
| narrative | A 的创新主要来自关系/规则因果的重新组合，不依赖未来真值。 | B 的创新在同一因果问题上再叠加可验证的运行时成本，行动后果更清晰。 | 揭示后只用于核对后续事实，不作为生成输入。 |
| dialogue | A 更强调人物自行谈判和隐藏信息，人物选择不被能力清单直接规定。 | B 更明确把已确认能力的消耗、展示边界写进人物决策。 | 揭示后只用于核对后续事实，不作为生成输入。 |
| pacing | A 保留较大的段落与节奏自由，但仍需防止同类‘核对—选择—代价’结构重复。 | B 的能力反馈增加信息密度，需人工检查是否把 Runtime 字段写成说明书。 | 揭示后只用于核对后续事实，不作为生成输入。 |
| themes | A 的创新主要来自关系/规则因果的重新组合，不依赖未来真值。 | B 的创新在同一因果问题上再叠加可验证的运行时成本，行动后果更清晰。 | 揭示后只用于核对后续事实，不作为生成输入。 |
| continuity | A 将规则、资源和未验证设置保持为问题，连续性安全依赖可见边界。 | B 能把已确认能力与不可用条件分开表示，降低把文学观察升级为状态的风险。 | 揭示后只用于核对后续事实，不作为生成输入。 |

## Literary Innovation Review

评审维度：是否产生新的因果机制、是否有不可撤回的成本、是否改变关系/空间/读者问题、是否避免只换名词、是否保留连续性边界。A 的自由度更大，B 的可执行性更强；B 不自动等于更有文学创新。Phase 5 的确定性模板诊断只报告 `DIVERGENT` 或 `PROSE_TEMPLATE_COLLAPSE`，不代替人工判断。

## Answers to the eight evaluation questions

1. **A 与 B 的候选是否结构不同？** 是。两组均经过三候选合同与结构差异门；B 的选择倾向 EARNED_OPPORTUNITY，A 在边界上保留更多 forward/continuity 组合。
2. **A 与 B 的正文是否真正不同？** 是，12 份真实正文保存了不同的场景锚点、能力使用方式和关系动作；pairwise diagnostics 作为证据，未被当作文风分数。
3. **B 是否真的使用 Runtime，而不是只改变 prompt？** 是。B 的 context manifest 记录 `runtime_state_enabled=true`、Effective Runtime/Earned Surface IDs 与 runtime usage；A 的对应字段为空且经过 anti-leak audit。
4. **B 是否更安全？** 在本次盲测中，B 的安全收益来自条件化能力与成本记录；两组都必须通过十项 Validator，不能把 B PASS 解释为自动正确。
5. **B 是否更有 forward creativity？** 需要逐章人工判断。若 B 只把能力名词插入模板，属于 false innovation；本报告保留独立九维审阅与模板信号，不宣称单一数值结论。
6. **是否出现模板坍缩？** 由每个 variant 的 `template_diagnostics.json` 明确给出；任何 `PROSE_TEMPLATE_COLLAPSE` 都进入人工复核。
7. **A/B 是否泄漏未来真值？** anti-leak audit 检查生成输入未引用 hidden path、未出现隐藏正文片段；truth 只在 generation snapshot closed 后读取。
8. **能否比较 Distill-only、Runtime-only 和 Fused？** Phase 5 实际完成 A/B；Runtime-only 不在本轮新增，因为它会失去 Distill 软层，不能与本任务规定的 A/B 同时保持输入等价。

## State / Safety

- 原始 `book/测试小说.md` read-only check: `True`。
- 未修改项目用户已有 `audit/`；本 benchmark 工件位于被忽略的独立 `library/phase5-real-*`。​
- 未生成正式续章；两个章节均停在 VALIDATED_DRAFT/草稿工件，不存在作者批准或 Canon Commit。
- 未激活新 Edition；未修改 Story Atlas、Approval 流程或项目基线 Canon。
