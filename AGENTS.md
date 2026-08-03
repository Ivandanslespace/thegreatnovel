# 子代理调度与项目边界

主 Agent 负责拆解任务、选择执行方式、派发子任务、整合结果并按验收标准复核；worker 负责执行父任务明确授权的独立子任务。以下原则适用于 `luna_worker` 及其他自定义 subagents。

## 子代理调度

1. 对体量较大且相互独立的子任务，优先派发给多个 `luna_worker` 并行处理。
2. 对几分钟内能够完成的轻量任务，直接留在主线程。
3. 每个 worker 的任务描述必须上下文完整，明确文件范围、任务边界、预期输出和验收标准；任务必须自包含，不得依赖主线程的对话历史。
4. 只读任务可以并行；涉及文件写入时，使用独立 worktree；无法隔离时改为串行执行。
5. worker 完成后，主线程必须按照验收标准检查结果；未达标时重新派发修正任务，直到满足标准或明确报告阻塞。
6. 如果多个 worker 无法并行，先检查当前生效的 `config.toml` 中 `[agents]` 的 `max_concurrent_threads_per_session`；若设置为 `1`，按串行处理，不因本规则擅自修改配置。

## 项目执行约束

- 这是 Python `tgn` 包；源码位于 `src/`，测试位于 `tests/`，项目测试入口为 `python -m pytest`。
- README 中标记为 frozen 的 phase、freeze tag、accepted implementation 和 PC1 冻结范围不得直接改写、移动、删除或重建；未来修复必须经过显式 reopen 或 superseding-phase 流程。
- 主 Agent 必须根据项目合同和 worker 的验收标准复核结果；worker 的“完成”不能替代主线程验收。

## Genesis Foundation 文档任务门禁

本项目的 Phase 10G0（Genesis Foundation Architecture Contract）是文档合同任务，
不是 Genesis 生产实现任务。主 Agent 必须负责目标拆解、只读委派、真实代码与文档核验、
文档写入、独立复审、问题关闭和最终提交；不得把文档任务顺手扩大为代码实现。

- 本轮严格只执行 Stage 0–3；不得创建 `src/tgn/genesis/**`、`tests/genesis/**`、
  新 Python 模块、数据库 schema、Event、Reducer、Action、WorldPack compiler、runtime
  profile、LLM provider、网络调用、自动 repair agent 或 PC2 实现。
- Stage 1 worker 只能执行只读审计，必须有自包含 prompt、明确文件范围、结构化输出、
  文件/符号/行号证据；不得写文件、commit、push、建分支或建/移动 tag。
- 大型且相互独立的只读审计优先并行；轻量检查留在主线程。文档写入必须由主 Agent
  串行完成；worker 结论不得替代主 Agent 对真实代码、真实文档和 Git ref 的复核。
- Stage 3 必须使用未参与初稿的全新只读 reviewer；每轮 reviewer 重新读取最新文档，
  最多进行三轮 `review → 主线程核验 → 修正文档`。未关闭的 BLOCKER 禁止提交。
- 本轮允许写入的路径只有：`AGENTS.md`、`README.md`、`docs/DESIGN_VALUES.md`、
  `docs/MVP_REWRITE_SPEC.md`、`docs/DEFERRED.md`、`docs/GENESIS_FOUNDATION.md`、
  `docs/PHASE1_9_HARDCODING_INVENTORY.md`。`src/**`、`tests/**`、配置、frozen artifact、
  tag 和 Git 历史必须保持不变。
- `pc1-frozen`、Phase 1–9 的 freeze tag、accepted implementation 和 PC1 文件边界均
  保持不可变。未来修改必须通过显式 reopen 或新的 superseding phase/milestone；不得
  用子代理共识代替代码证据，也不得把旧 `devour_evolution` 候选恢复为 Genesis 合同。
