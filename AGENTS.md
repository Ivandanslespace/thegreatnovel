# Canonical Development Branch

本仓库唯一永久开发分支是 `小说续写_codex`。所有生产代码、测试、文档和本地 Web 交付均直接在该分支完成；不得创建新分支、Pull Request 或额外 worktree。允许创建保护性 tag，但不得把功能分散到其他长期分支。每次交付前必须确认当前分支、工作树和远端 `origin/小说续写_codex` 一致，并只推送该分支。

主 Agent 负责拆解、调度、整合、验收和最终提交；子代理只能执行自包含的只读审计，或在明确隔离的 Operation Workspace/artifact 目录内工作，不得修改生产代码、`book/`、Canon、远端分支或启动 Codex 子进程/API。不得创建额外 worktree；生产代码由主 Agent 在当前分支串行修改。

## Existing Novel Initialization Is Atlas-First

对已有长篇的正式初始化不是一次普通 ingest，也不是直接进入续写。初始化必须按下列可审计流水线执行：

`Source Coverage -> Arc Segmentation -> Arc Extraction -> Entity Resolution -> Cross-Arc Synthesis -> Contradiction Audit -> Narrative DNA -> Current Story Atlas -> Future Possibility Space -> Semantic Metric Bootstrap -> Optional Visual Asset Export`

`ingest` 只负责建立不可变源、章节和 source spans；它不等于初始化完成。正式续写的最低状态是 `WORLD_MODEL_READY_WITH_GAPS`，50/100 章 Batch 的最低状态是 `WORLD_MODEL_READY`。未来路线允许存在空白；但当前主角状态、当前核心规则、当前能力边界、当前主要线程和续写边界缺失时必须阻断。

初始化状态使用 `NOT_STARTED`、`SOURCE_MAPPED`、`ARC_EXTRACTION_RUNNING`、`ENTITY_RESOLUTION_RUNNING`、`SYNTHESIS_RUNNING`、`ATLAS_VALIDATION_RUNNING`、`METRIC_BOOTSTRAP_RUNNING`、`VISUAL_RENDERING_RUNNING`、`READY_WITH_GAPS`、`READY`、`BLOCKED`、`STALE`。Web 只创建本地 handoff；`$process-novel-handoff` 之后必须进入 `$initialize-existing-novel`。所有 CANON 节点和关系必须能回指真实 source span；INFERENCE/CANDIDATE/PROSE_ONLY 不得静默升级为 CANON。

架构原则：**Facts are deterministic. Meaning is probabilistic.** Python 负责完整源覆盖、边界、哈希、唯一归属、Schema、证据、状态、阈值、冲突检测、稳定 ID 和离线图渲染；Codex 桌面端负责分段语义理解、跨 Arc 综合、Narrative DNA、世界模型、未知与反证解释。初始化不得依赖 Planning Aggregate 才能建立 Atlas。

# 子代理调度与项目边界

主 Agent 负责拆解任务、选择执行方式、派发子任务、整合结果并按验收标准复核；worker 负责执行父任务明确授权的独立子任务。以下原则适用于 `luna_worker` 及其他自定义 subagents。

## 子代理调度

1. 对体量较大且相互独立的子任务，优先派发给多个 `luna_worker` 并行处理。
2. 对几分钟内能够完成的轻量任务，直接留在主线程。
3. 每个 worker 的任务描述必须上下文完整，明确文件范围、任务边界、预期输出和验收标准；任务必须自包含，不得依赖主线程的对话历史。
4. 子代理不得修改生产代码；子代理只允许执行只读审计，或写入隔离的 Operation Workspace/artifact 目录；所有生产代码修改由主 Agent 在 `小说续写_codex` 当前工作树串行完成。
5. worker 完成后，主线程必须按照验收标准检查结果；未达标时重新派发修正任务，直到满足标准或明确报告阻塞。
6. 如果多个 worker 无法并行，先检查当前生效的 `config.toml` 中 `[agents]` 的 `max_concurrent_threads_per_session`；若设置为 `1`，按串行处理，不因本规则擅自修改配置。

## 项目硬边界

1. 最高产品规范是 `Novel_Authoring_System_Constitution_V2.md`；根 `CONSTITUTION.md` 不属于本系统。
2. `book/` 原文永久只读。所有新书、索引、任务、草稿、续章、报告与导出必须写入 `library/<book_id>/`，并通过 `BookLayout` 解析路径。旧 `workspace/<book_id>/` 只允许 legacy 读取、`migrate-legacy` 输入和 `cleanup-legacy` 前的保留历史；不得作为新运行产物写入目标。
3. Codex 不得脱离 Continuation Boundary Packet 和 Chapter Contract 自由续写；详细流程见 `.agents/skills/continue-novel/SKILL.md`。
4. 草稿默认停在 `VALIDATED`。未经作者当前明确说“批准写入正史”，不得运行 `novel approve` 或产生 Canon Commit。
5. 不得把 `INFERENCE`、`CANDIDATE`、`PROSE_ONLY` 静默升级为 `CANON`；所有正史变化必须可回指原文或作者批准事件。

6. Story Atlas 是版本化软理解层，不是 Truth、Canon、固定大纲或数据库正史。Atlas
   节点/关系必须区分 `information_status`、`constraint_level`、`horizon`、
   `confidence` 和真实 `source_span`；新版本使用新 ID/版本并保留父版本，旧 artifact
   不得覆盖。
7. Future Possibility Space 必须保留 Active/Alternative/Wildcard/Open Design，
   Rolling Horizon 的 FAR 不得写逐章大纲或固定结局；FAR 覆盖至少为
   `max(current_written_chapters*2, batch_target_chapters*2)`。
8. Batch Continuation 默认 chunk=5、checkpoint=10。每章必须沿用 Boundary、Chapter
   Contract 和十项校验；Batch Provisional Projection、Atlas accepted 或
   `BATCH_VALIDATED` 都不得写入 Canon 或替代作者批准。

版本化改写另遵循 `.agents/skills/revise-novel/SKILL.md`：改写只能写派生 edition，必须经过影响审计、计划、`REVISION_DRAFT`、校验和逐字批准；`批准改写版本` 与 `启用改写版本` 分离，base/真实 `book/` 不得被覆盖。

长跨度节奏诊断遵循 `.agents/skills/analyze-novel-rhythm/SKILL.md`：先建立 edition-aware
`chapter_features`，再运行 `novel rhythm diagnose` 与 `novel hooks diagnose`，最后才进入候选与合同。
章节功能、标题/首尾相似和高压连续分别补充既有 Repetition Fatigue/Pressure Curve，伏笔
 Age/Dormancy/Readiness 补充 Narrative Debt 与 Thread Priority；不改变 Candidate Score 权重，
 不把 WARNING 当作批准依据，也不允许伪造语义证据。

指标观测和本地审核台遵循 `.agents/skills/review-novel-metrics/SKILL.md`：指标只诊断，
正文/状态提供证据，缺失必须保持 null 并可追溯。Windows Codex 桌面端交接遵循
`.agents/skills/process-novel-handoff/SKILL.md`：Web 只生成和读取 handoff 文件，绝不调用
Codex subprocess、`codex exec`、OpenAI API 或任意 shell；作者必须手动在 Codex 桌面端领取任务。

## 构建与验收

Windows 中文路径使用普通 wheel，避免 editable `.pth` 的本地代码页问题：

```powershell
uv sync --python "C:\Users\jingx\anaconda3\python.exe" --extra dev --no-editable --reinstall-package novel-authoring-system
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests
uv run --no-sync mypy src
uv run --no-sync novel --help
uv run --no-sync novel features --help
uv run --no-sync novel rhythm --help
uv run --no-sync novel hooks --help
uv run --no-sync novel metrics --help
uv run --no-sync novel segments --help
uv run --no-sync novel workflow --help
uv run --no-sync novel web doctor
```
