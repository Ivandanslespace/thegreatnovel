# Codex Client Handoff

用户使用 Windows Codex 桌面客户端，并通过 ChatGPT Pro 账户登录。本系统不需要 OpenAI API Key，不调用 Responses API，不使用 token 计费模型，也不使用 Codex CLI 作为执行入口。

## Local File Handoff Protocol

Web 创建 `workspace/<book_id>/editions/<edition_id>/handoffs/<handoff_id>/`，包含 `task.json`、`prompt.md`、`metric_context.json`、`context_manifest.json`、`output_schema.json`、`status.json`、`events.jsonl`、`result.json` 和 `artifacts/`。所有 hash 在创建时冻结；source manifest、effective content、projection、registry、config、edition status、Atlas/Horizon 或 Planning Aggregate 漂移会使 READY/CLAIMED 任务 STALE，不能覆盖原任务。

作者在 Codex 桌面端复制 Web 给出的固定指令，必须先使用 `$process-novel-handoff` 原子领取任务，再调用 `$continue-novel`、`$revise-novel`、`$bootstrap-story-atlas` 或 `$continue-novel-batch`，并写回状态/结果。Atlas handoff 的软 artifact 只能写入 `artifacts/story_atlas/`；Batch handoff 必须绑定 `batch_id`，沿用 Boundary/Contract/十项校验，结果停在 `BATCH_VALIDATED` 而不写 Canon。Web 只读取 SQLite、状态文件、事件日志和结果文件；SSE（如启用）只传输已有状态，不能控制 Codex，也不能假装知道模型是否仍在思考。没有 heartbeat 时只显示“Codex 客户端可能已停止或等待用户操作”。

`result.json` 必须符合严格 `WorkflowHandoffResult`；COMPLETED 还要通过 artifact、edition/hash anchor 和 `status.json` 一致性检查。需要作者决定时，Codex 写 `waiting_for_user.json` 并进入 `WAITING_FOR_USER`；Web 只新增 `handoff_user_response.json`，不修改冻结的 `task.json`。

续写最终停在 `VALIDATED_DRAFT`，改写停在 `VALIDATED_CAMPAIGN` 或 requested stage；`canon_committed` 和 `edition_activated` 必须为 `false`。批准和激活仍由作者显式执行。
