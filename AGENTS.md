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

## Genesis 长期边界与阶段切换

Phase 10G0（Genesis Foundation Architecture Contract）的 Stage 0–3 文档任务已经由提交
`9cdadc472cd92ce38e42767a896718fcad61f938` 完成。以下内容只属于该次一次性任务，现已过期，
不得被套用为后续开发的全局门禁：七文件 allowlist、仅允许文档写入、禁止修改 `src/**` /
`tests/**`、不得实现 Genesis，以及强制使用 G0 专用的 reviewer 流程。后续阶段应按自己的
Phase Contract 执行；只要用户或该阶段合同明确授权 coding，就可以在允许范围内修改代码、
测试、配置和运行时实现。

当前权威设计/开发文档只有 `docs/DESIGN_VALUES.md` 与 `docs/DEV_SPEC.md`。

- 每个后续 phase 开始前，建立一份自包含 Phase Contract，说明产品问题、允许修改的文件、
  frozen exclusions、验收命令和 non-goals。它用于界定本阶段工作，不是禁止后续阶段开发的
  永久模板；Phase Contract 可以直接写在任务描述、PR 说明或阶段计划中，不强制新建文件；
  没有 coding 授权时，才不得仅凭路线图文字自行实现。
- `pc1-frozen`、Phase 1–9 freeze tag、accepted implementation、旧 artifact 语义和 PC1
  文件边界保持不可变。未来若确需改变这些内容，必须通过显式 reopen 或新的 superseding
  phase/milestone；不得移动、删除或重建既有 tag。
- 不得用子代理共识替代真实代码、测试、artifact、hash 与 Git ref 证据；不得把历史
  `devour_evolution` 候选直接恢复为 Genesis 默认合同。
- 大型只读审计优先并行，写入操作隔离或串行。仅当某个阶段是文档合同变更，才沿用主 Agent
  整合与独立 reviewer 的要求；普通 coding phase 以及小型 bugfix/maintenance 不需要重复
  G0 的文档审查流程。
- 当阶段新增可玩行为时，优先在该阶段合同规定的范围内交付可验收的 vertical slice，覆盖
  该行为实际需要的 State、Action、Event、Reducer、Invariant、Projection、Persistence、
  Replay 或测试边界；不要求每个阶段预先实现所有层，也不得从 future roadmap 预建万能框架。
