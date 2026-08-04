# Codex Client Handoff

用户使用 Windows Codex 桌面客户端，并通过 ChatGPT Pro 账户登录。本系统不需要 OpenAI API Key，不调用 Responses API，不使用 token 计费模型，也不使用 Codex CLI 作为执行入口。

## Local File Handoff Protocol

Web 创建 `workspace/<book_id>/editions/<edition_id>/handoffs/<handoff_id>/`，包含 `task.json`、`prompt.md`、`metric_context.json`、`context_manifest.json`、`output_schema.json`、`status.json`、`events.jsonl`、`result.json` 和 `artifacts/`。所有 hash 在创建时冻结；指标或 projection 漂移会使任务 STALE，不能覆盖原任务。

作者在 Codex 桌面端复制 Web 给出的固定指令，使用 `$process-novel-handoff` 原子领取任务，调用 `$continue-novel` 或 `$revise-novel`，并写回状态/结果。Web 只读取 SQLite、状态文件、事件日志和结果文件；SSE（如启用）只传输已有状态，不能控制 Codex，也不能假装知道模型是否仍在思考。没有 heartbeat 时只显示“Codex 客户端可能已停止或等待用户操作”。

续写最终停在 `VALIDATED_DRAFT`，改写停在 `VALIDATED_CAMPAIGN` 或 requested stage；`canon_committed` 和 `edition_activated` 必须为 `false`。批准和激活仍由作者显式执行。
