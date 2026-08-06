---
name: distill-novels
description: 在小说续写系统的 Local File Handoff 中调用 CloudLiu1008/distill-novels，把参考小说抽象为可追溯、仅供参考的写作知识 skill；不把来源正文或软理解写入 Canon。
---

# 系统集成版 distill-novels

本 Skill 对接上游 [CloudLiu1008/distill-novels](https://github.com/CloudLiu1008/distill-novels)。
Python 只负责准备来源、章节边界、manifest、任务冻结和结果校验；Codex 桌面端负责语义提炼。
维度定义、输出形状和质量门分别见 [references/dimensions.md](references/dimensions.md)、
[references/output-schema.md](references/output-schema.md) 和
[references/safety-quality.md](references/safety-quality.md)。

## 输入

先完整读取 handoff 目录中的 `task.json`、`prompt.md`、`output_schema.json`、
`context_manifest.json` 和 `artifacts/distill_input/manifest.json`。任务中的
`distill.mode`、`distill.dimensions`、`distill.depth` 和 `distill.source_ids` 是冻结参数，
不得自行改写。来源正文只从 `artifacts/distill_input/normalized/` 按 bounded segment 读取；
不得修改 `book/`、Canonical source 或 SQLite。

## 语义工作

按上游 Skill 的 `analyze-only`、`create`、`compare` 或 `update` 模式执行，抽取
worldbuilding、characters、plot、style、narrative、dialogue、pacing、themes、continuity
中被选择的维度。每个来源性结论必须带 `source_id` 和 segment/行号定位，并区分事实、强推断
和候选解释；只保存机制、约束和可迁移控制，不保存长摘录、句式仿写、来源人物或来源事件。

## 输出合同

把完整 skill 写入 `artifacts/distill_skill/`，至少包含：

- `SKILL.md`：支持 `analyze`、`design`、`revise`、`check` 四种下游动作；
- `distillation-report.md`：来源数、维度、模式、深度、警告、证据覆盖和质量检查；
- `sources.md` 与所选维度文件：每项来源性主张可回指冻结输入；
- 必要的 source overview、bounded chapter cards 或 evidence index；不要复制完整原文。

然后按 `output_schema.json` 写 `result.json` 和 `status.json`：

- `completed_stage=DISTILLED`；
- `distill_id`、`distill_source_ids`、`distill_dimensions`、`distill_mode`、`distill_depth` 与
  `task.json` 完全一致；
- `distill_skill_root=artifacts/distill_skill`；`artifact_paths` 至少列出
  `artifacts/distill_skill/SKILL.md` 和 `artifacts/distill_skill/distillation-report.md`；
- `canon_committed=false`、`edition_activated=false`。

发布必须由作者随后显式运行 `novel distill import --book-id ... --handoff-id ...`。
发布后的 skill 位于 `edition.analysis/distill/skills/<distill_id>/`，只允许作为续写的
`REFERENCE_ONLY` 写作参考，不能改变 Story Atlas、Canon、作者指令或草稿审批状态。
