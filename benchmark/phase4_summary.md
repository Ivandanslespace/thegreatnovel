# Distill Integration Phase 4 Blind Benchmark Summary

生成阶段只使用各自独立 Book 的 selected Edition 可见源、SELF_BOOK Distill Package、Runtime Baseline 和 Context Router；两章隐藏真值在 generation_snapshot 封存后才读取。

Book IDs: phase4-blind-phase4c-020 / phase4-blind-phase4c-035 / phase4-blind-phase4c-050 / phase4-blind-phase4c-075。

| boundary | segments | dimensions | findings | literary arcs | craft controls | continuity candidates | mapping | lenses | forward novelty | validators | truth reveal |
|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|
| 20 | 20 | 9 | 12 | 1 | 2 | 1 | EXACT 1 / PARTIAL 0 / UNMAPPED 0 / CONFLICTING 0 | CONTINUITY_ACTIVE_THREAD,EARNED_OPPORTUNITY,FORWARD_EXPANSION | 1 | 10/10 | after generation |
| 35 | 35 | 9 | 12 | 1 | 2 | 1 | EXACT 1 / PARTIAL 0 / UNMAPPED 0 / CONFLICTING 0 | CONTINUITY_ACTIVE_THREAD,EARNED_OPPORTUNITY,FORWARD_EXPANSION | 1 | 10/10 | after generation |
| 50 | 50 | 9 | 12 | 1 | 2 | 1 | EXACT 1 / PARTIAL 0 / UNMAPPED 0 / CONFLICTING 0 | CONTINUITY_ACTIVE_THREAD,EARNED_OPPORTUNITY,FORWARD_EXPANSION | 1 | 10/10 | after generation |
| 75 | 75 | 9 | 12 | 1 | 2 | 1 | EXACT 1 / PARTIAL 0 / UNMAPPED 0 / CONFLICTING 0 | CONTINUITY_ACTIVE_THREAD,EARNED_OPPORTUNITY,FORWARD_EXPANSION | 1 | 10/10 | after generation |

## Cross-boundary findings

- 四个边界均建立独立 source copy、preparation、SELF_BOOK package、Baseline 和 Router bundle；没有复用 Phase 3 的 Distill、Atlas 或 benchmark 目录。
- 三个候选 lens 在每个边界均显式存在；Forward novelty 只携带 introduction event、causal source、new state 和 conflicts checked，不把未来真值回写为当前状态。
- provisional state 只写入 benchmark draft/validation 工件；没有进入 Canon、Edition active state 或 approved chapter。
- 真值揭示后的 token overlap 仅是辅助诊断，不被解释为语义命中分数；它用于保留盲测可审计链，不替代人工九维比较。

## Safety

- 原始 `book/测试小说.md` 保持只读；所有 benchmark 工件位于被忽略的 `library/phase4-blind-*`。
- 未批准草稿、未创建正式续章、未写入 Canon、未激活 Edition。
