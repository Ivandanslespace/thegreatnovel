# Phase 6 — Author-Controlled Innovation & Calibration

状态：`IMPLEMENTED — TRUE LIVE DESKTOP ACCEPTANCE PENDING`

本文件是 Phase 6 的冻结实验协议与结果入口。真实结果必须由
`scripts/phase6_innovation_control.py evaluate` 在所有对应 Windows Codex Desktop
handoff 完成、十项 Validator 通过且 `generation_closed=true` 后写入；本次实现阶段不伪造
Distill findings、候选、Chapter Contract 文学内容或正文。

## Frozen protocol

- boundary：`60 → 61 / 62`；每个隔离 Book 只向 Codex 暴露 `1..60`。
- Level group：`L1 = MINIMAL + AUTO`、`L3 = MEDIUM + AUTO`、`L5 = BOLD + AUTO`。
- Direction group：`MEDIUM + RELATIONSHIP`、`MEDIUM + WORLD`，与 L3 共用协议。
- Ablation C：Candidate Planning 加载 Runtime；Draft 只加载 Chapter Contract、最近正文和
  style/dialogue/narrative controls，不加载 Raw Runtime tables。
- 每个变体连续生成 61、62；62 必须使用同一变体真实 61 `VALIDATED_DRAFT` 与
  `BatchProvisionalState` provisional context。
- Distill、Candidate、Draft 均由 READY_FOR_CODEX/Operation handoff 真实生成；Python 只负责
  prepare、collect、strict schema/Validator、state audit、close 和事后 evaluate。
- hidden truth 位于 controller 独立目录，生成阶段不进入 Book、task、prompt、context manifest
  或 Skill input；只有 generation close 后才能读取。

## Evaluation contract

结果逐章保存 requested level/focus 与 realized direction/level，另行记录：

- meaningful/cosmetic novelty；
- future options opened/closed；
- earned recombinations、new relationship/world/mechanism；
- pattern distance、integration cost、DirectionAlignment；
- safety/continuity violations、SYSTEM_LANGUAGE_LEAK、style fidelity；
- Level/Direction Context Equality Gate 及 `EXPERIMENT_CONFOUNDED` 差异；
- Full Runtime Draft 与 Planning-only Runtime 的文学审阅问题。

报告不会压成唯一文学总分，也不会把 Ground Truth 当作 Innovation Target。

## Operator commands

```powershell
uv run --no-sync python scripts/phase6_innovation_control.py prepare --run-label phase6-v1
# 按 benchmark/phase6_live/WORK_QUEUE.md 处理 READY_FOR_CODEX
uv run --no-sync python scripts/phase6_innovation_control.py status --run-label phase6-v1
uv run --no-sync python scripts/phase6_innovation_control.py collect --run-label phase6-v1
uv run --no-sync python scripts/phase6_innovation_control.py evaluate --run-label phase6-v1
```

最终 draft 是外部审计工件，完成校验后必须按项目约定对精确 draft 路径执行
`git add -f`、commit 和 push；不得上传 hidden truth、数据库缓存、运行目录或 `book/` 原文。
