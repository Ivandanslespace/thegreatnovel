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

## Genesis 后续长期门禁

Phase 10G0 的一次性 Stage 0–3 文档任务已经由提交
`9cdadc472cd92ce38e42767a896718fcad61f938` 记录；其七文件 allowlist、禁止写入
`src/**`/`tests/**` 和“本轮不得实现 Genesis”的规则不得继续阻塞未来明确授权的 coding
phase。当前权威内容文档只有 `docs/DESIGN_VALUES.md` 与 `docs/DEV_SPEC.md`。

- 每个后续 phase 必须先从 `docs/DEV_SPEC.md` 建立自包含 Phase Contract，明确产品问题、
  allowed files、frozen exclusions、完整 vertical slice、验收命令和 non-goals；没有明确
  coding 授权时，不得从路线图文字自行开始实现。
- `pc1-frozen`、Phase 1–9 freeze tag、accepted implementation、旧 artifact 语义和 PC1
  文件边界保持不可变。未来修改只能通过显式 reopen 或新的 superseding phase/milestone；
  不得移动、删除或重建既有 tag。
- 不得用子代理共识替代真实代码、测试、artifact、hash 与 Git ref 证据；不得把历史
  `devour_evolution` 候选直接恢复为 Genesis 默认合同。
- 大型只读审计仍优先并行；写入必须隔离或串行。文档合同初稿由主 Agent 整合，随后使用
  未参与初稿的全新只读 reviewer；未关闭的 BLOCKER 禁止提交。
- 新 Feature 必须在同一个可验收 vertical slice 内贯穿 State、Action、Event、Reducer、
  Invariant、Projection、Persistence、Replay 与测试。不得从 future roadmap 预建万能框架。
