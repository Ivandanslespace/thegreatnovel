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
- 内部 checkpoint 可以只完成完整闭环的一部分，例如 schema/model、runtime semantics、
  compiler、preflight、publication 或 autoplay；checkpoint 可以有自己的 commit、tests
  和 review，但不得被称为完整 Feature 或完成整个 milestone。
- 任何新增可玩行为在被宣称为 `complete`、`SUPPORTED`、`accepted implementation`、
  `production ready`、`frozen` 或创建 freeze tag 之前，必须完成该行为实际需要的完整闭环：
  `State → legal Action → DomainEvent → Reducer → Invariant → Observation / Knowledge
  Projection → Persistence → Replay / Verify → tests / autoplay proof`。不得把中间
  checkpoint、helper、schema、label、fixture 或局部 cost mapping 冒充为已完成 Feature。
- 普通 coding phase 必须至少有一次与风险匹配的独立代码/合同 review，但不需要重复 G0
  专用的三轮全新文档 reviewer 流程。新增可玩行为、authority boundary、State/Event/
  Reducer、compiler、persistence、Replay/Verify、publication/atomicity、migration、安全
  或 Knowledge Boundary 时，review 强度至少覆盖真实 diff、代码、测试和 artifact。reviewer
  不能只相信主 Agent 报告；BLOCKER 必须关闭，MAJOR 必须关闭或有用户批准的 defer 理由。
  小型低风险维护或纯拼写修复可以由 Phase Contract 规定更轻的独立 review 强度。
- 不得从 future roadmap 预建万能框架；新 Feature 应在本阶段合同规定的范围内形成可验收
  vertical slice，覆盖该行为实际需要的边界，而不是机械要求每个阶段预先实现所有层。

## 文档治理

- `docs/` 默认只保留两份权威内容文档：`docs/DESIGN_VALUES.md` 与
  `docs/DEV_SPEC.md`。
- Agent 默认不得自行新增 `docs/*.md`、phase spec、architecture note、decision record、
  hardcoding inventory、review report、deferred list、migration plan 或临时设计说明。
- 每个 Phase Contract 优先写在用户任务 Prompt、PR description、issue、commit plan 或
  Agent 最终报告中；一次性阶段不自动创建永久文档。
- 只有用户明确批准，Agent 才可以新增第三份永久内容文档。若现有两份文档确实无法容纳，
  必须先停止并向用户说明原因、长期 owner、与现有文档的权威关系，以及如何防止重复和冲突。
- 长期产品价值变化时修改 `docs/DESIGN_VALUES.md`；当前实现边界、冻结 registry、
  Active Roadmap 或 Phase 验收合同变化时修改 `docs/DEV_SPEC.md`。
- README 只维护简短状态、入口和链接，不复制完整合同正文。
- 历史规范和旧 Phase Contract 只通过 `git show <ref>:<path>`、GitHub fetch 或仓库外临时
  目录读取；不得为了阅读历史而恢复到当前工作树。
- 临时审计结果、review findings 和一次性报告不自动沉淀为新文档。
