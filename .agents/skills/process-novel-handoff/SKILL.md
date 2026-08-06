---
name: process-novel-handoff
description: 按 Local File Handoff Protocol 在 Windows Codex 桌面端领取并处理小说续写、改写、指标语义、章节特征或 distill 任务；当 task.json 状态为 READY_FOR_CODEX 且用户明确要求处理 handoff 时使用，不得启动 Codex 子进程、API 或 shell。
---

# Process Novel Handoff

Codex 桌面客户端是唯一 LLM 执行者。先读取任务目录，再由 Python CLI 和现有业务 Skill 生成文件产物；Web 不运行模型。

## 领取与冻结校验

1. 用 `handoff_id` 定位 `workspace/<book_id>/editions/<edition_id>/handoffs/<handoff_id>/`。
2. 读取 `task.json`、`prompt.md`、`metric_context.json`、`context_manifest.json`、`output_schema.json` 和 `status.json`。校验 `task_schema_version`、source/projection/metric/registry/config/edition hash、Atlas/Horizon anchor、Batch plan hash 以及 allowed paths；任何漂移都标记 STALE 并停止。
3. 只在数据库状态 `READY_FOR_CODEX` 时用 SQLite 事务原子 claim，保存 `claimed_by` 与 `claim_token`，写入 `events.jsonl`；不能让两个 Codex 线程领取同一个任务。
4. 状态按 `CLAIMED → RUNNING` 推进；需要作者选择时写 `waiting_for_user.json`、事件和 `WAITING_FOR_USER`，不要猜测。心跳只表示最近活动，Web 不得推断“仍在思考”。

## 具体业务

- `CONTINUATION`：调用 `$continue-novel`，按 `requested_stage` 走 Boundary、Contract、候选和 Validator。
- `REVISION`：调用 `$revise-novel`，按 RevisionSpec、Impact Packet、Plan/Unit 和 Validator 执行。
- 语义/特征任务：只写结构化 observation/feature 文件，不改章节正文。
- `STORY_ATLAS_BOOTSTRAP` / `STORY_ATLAS_REFRESH` / `WORLD_MODEL_REVIEW`：调用
  `$bootstrap-story-atlas`，只写 `artifacts/story_atlas/`，由 Python 校验后登记 immutable
  版本；不把软理解写入 Canon。
- `NOVEL_INITIALIZATION`：调用 `$initialize-existing-novel`，先读取初始化目录和 Arc task，
  按 Atlas-first pipeline 处理 `arc_outputs/`、`entity_resolution/`、`synthesis/`、
  `metrics/` 和 `visuals/`；不得预先创建 Planning Aggregate。
- `NOVEL_DISTILLATION`：调用 `$distill-novels`，读取冻结的
  `artifacts/distill_input/`，只把抽象写作机制写入 `artifacts/distill_skill/`；完成后停在
  `DISTILLED`，由 `novel distill import` 显式发布为 `REFERENCE_ONLY`，不得写入 Canon。
- `BATCH_CONTINUATION`：调用 `$continue-novel-batch`，必须绑定 batch/chunk，逐章保留
  Boundary、Contract、十项 Validator 和 provisional hash；`BATCH_VALIDATED` 不是批准。

禁止修改 `book/`、批准正史、批准改写 Campaign、启用 Edition、删除历史草稿或绕过 Validator。不要使用 OpenAI API、`codex exec`、模型参数、API Key、shell 命令或任何 subprocess。

## 结束合同

成功时先验证 `result.json` 符合 `output_schema.json`，并明确 `canon_committed=false`、`edition_activated=false`；再写 result、事件和 `COMPLETED`（可用 `novel workflow update --status COMPLETED --result-path <result.json>`）。续写最多停在 `VALIDATED_DRAFT`，改写最多停在 `VALIDATED_CAMPAIGN` 或请求阶段。失败写 `error.json` 和 `FAILED`，保留历史文件，不覆盖旧 handoff。
