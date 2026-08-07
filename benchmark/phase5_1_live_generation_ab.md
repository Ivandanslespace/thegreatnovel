# Phase 5.1 True Live Codex Handoff Benchmark

本文件定义真实 Live benchmark 的执行合同。历史 Phase 5 的
`benchmark/phase5_real_generation_ab.md` 和
`scripts/phase5_real_generation_ab.py` 保留为：

`SEMANTIC_FIXTURE_AB / NOT_LIVE_GENERATION_BENCHMARK`

## 运行方式

```powershell
uv run --no-sync python scripts/phase5_live_ab.py prepare --run-label live-v1
uv run --no-sync python scripts/phase5_live_ab.py status --run-label live-v1
uv run --no-sync python scripts/phase5_live_ab.py collect --run-label live-v1
uv run --no-sync python scripts/phase5_live_ab.py evaluate --run-label live-v1
```

`prepare` 只创建四个独立 Book：

- `phase5-live-a-050` / `phase5-live-b-050`
- `phase5-live-a-075` / `phase5-live-b-075`

每个 Book 只冻结 `1..N`。`N+1`、`N+2` 由 controller 独立保存，生成期间不会放入 Book、普通 task input 或 context manifest。

## A/B/C 输入边界

- A：visible source、最近完整章节、SELF_BOOK Distill 和中性作者指令；`include_runtime_state=false`。
- B：A 的全部输入，加 Runtime Baseline、EffectiveRuntimeState、Earned Surface、Actionable Knowledge、Available Payoff Surface 与 Router context；`include_runtime_state=true`。
- C：可选 `--include-c`，仅在 50 boundary 使用 Runtime 做 Candidate Planning，Draft 阶段关闭 Runtime，用来检验 Runtime 是否应主要影响规划。

Python 不生成九维语义、候选剧情、Chapter Contract 文学内容或小说正文。Candidate/Draft 是现有 canonical Operation handoff；Distill 是正式 `NOVEL_DISTILLATION` workflow handoff。每个结果记录 handoff/operation、task、context manifest、output artifact 和时间戳。

## 固定执行顺序

1. A50 Distill、B50 Distill、A75 Distill、B75 Distill。
2. 四个 N+1 Candidate，再是四个 N+1 Draft。
3. 四个 N+2 Candidate，再是四个 N+2 Draft。

每一阶段必须全部 output 完成后才能 `collect`。N+2 task input 明确包含真实 N+1 `VALIDATED_DRAFT` 和 `BatchProvisionalState`；不能从 N 重新独立生成。

## 真值与评价

`collect` 只验证、导入、映射和保存结果，并在两章全部通过十项 Validator 后写入：

```json
{
  "generation_closed": true,
  "truth_revealed": false
}
```

只有 `evaluate` 才读取 controller-owned hidden truth，并记录：

- retroactive unsupported invention、unsupported capability/resource、knowledge/timeline/rule conflict；
- capability/resource/actionable knowledge/relationship leverage/setup-payoff 使用；
- new person/threat/location/item/discovery/transaction/relationship/social structure/rule manifestation；
- `SYSTEM_LANGUAGE_LEAK`（Runtime、Baseline、Canon、Projection、Validator、`thread_status`、`resource_cost`、`character_boundary`、融合层等）；
- 九维文学审阅，以及 specificity、scene vividness、character agency、surprise、causal novelty、payoff strength、hook strength。

这些结果保持逐章 A/B/Truth 结构，不压成唯一文学分数。没有人工/独立 Codex review 时，文学字段必须保持 `REVIEW_REQUIRED`。

## 产物位置

运行期间的 `WORK_QUEUE.md`、状态、hidden truth、候选/正文结果和评估报告位于被忽略的 `benchmark/live_phase5/`、`benchmark/phase5_live_hidden/` 以及各自的隔离 `library/phase5-live-*`。这些运行产物不应进入版本库；本文件和编排代码才是可复核的实现合同。
