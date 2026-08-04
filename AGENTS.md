# 子代理调度与项目边界

主 Agent 负责拆解任务、选择执行方式、派发子任务、整合结果并按验收标准复核；worker 负责执行父任务明确授权的独立子任务。以下原则适用于 `luna_worker` 及其他自定义 subagents。

## 子代理调度

1. 对体量较大且相互独立的子任务，优先派发给多个 `luna_worker` 并行处理。
2. 对几分钟内能够完成的轻量任务，直接留在主线程。
3. 每个 worker 的任务描述必须上下文完整，明确文件范围、任务边界、预期输出和验收标准；任务必须自包含，不得依赖主线程的对话历史。
4. 只读任务可以并行；涉及文件写入时，使用独立 worktree；无法隔离时改为串行执行。
5. worker 完成后，主线程必须按照验收标准检查结果；未达标时重新派发修正任务，直到满足标准或明确报告阻塞。
6. 如果多个 worker 无法并行，先检查当前生效的 `config.toml` 中 `[agents]` 的 `max_concurrent_threads_per_session`；若设置为 `1`，按串行处理，不因本规则擅自修改配置。

## 项目硬边界

1. 最高产品规范是 `Novel_Authoring_System_Constitution_V2.md`；根 `CONSTITUTION.md` 不属于本系统。
2. `book/` 原文永久只读。所有索引、任务、草稿、续章、报告与导出写入 `workspace/<book_id>/`。
3. Codex 不得脱离 Continuation Boundary Packet 和 Chapter Contract 自由续写；详细流程见 `.agents/skills/continue-novel/SKILL.md`。
4. 草稿默认停在 `VALIDATED`。未经作者当前明确说“批准写入正史”，不得运行 `novel approve` 或产生 Canon Commit。
5. 不得把 `INFERENCE`、`CANDIDATE`、`PROSE_ONLY` 静默升级为 `CANON`；所有正史变化必须可回指原文或作者批准事件。

## 构建与验收

Windows 中文路径使用普通 wheel，避免 editable `.pth` 的本地代码页问题：

```powershell
uv sync --python "C:\Users\jingx\anaconda3\python.exe" --extra dev --no-editable --reinstall-package novel-authoring-system
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests
uv run --no-sync mypy src
uv run --no-sync novel --help
```
