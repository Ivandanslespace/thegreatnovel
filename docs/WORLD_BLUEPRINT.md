# 世界蓝图作者指南

本目录的蓝图不是小说设定表，而是可以被纯引擎编译、预览、结算、重放的候选因果模型。作者从一句话开始，先写玩家无法控制的缺口，再写一条有代价的杠杆，最后把规则拆成动作、离屏过程、窗口、里程碑和扩展。任何尚未进入 `initial_state.unlocks` 的扩展内容都只是候选，不能提前成为事实。

## 从一句话到候选

1. 用一句话写“玩家要维持什么、什么会失效、为什么普通人无法直接修好”。霜港的句子是供给网络会随潮汐和维护债务收缩；灰印的句子是证据、期限和承诺会在派系离线游说中改变。
2. 写 `control_deficit` 和 `core_question`。缺口必须能被行动改变，不能靠旁白宣布解决。
3. 选择一个世界自己的 `causal_model`，再给主角一条有成本、边界和错误后果的 `lever`。杠杆动作必须在 `lever.action_ids` 中，至少一个动作声明 `lever.required=true`。
4. 先列 16 个以上动作，再画两条至少各含两步的复利链。动作要改变可达机会、资源、关系、程序或时间，而不只是换名词。
5. 加入至少两个有 `actor_id` 的正时间 `process`。正时间行动必须让世界时钟和到期过程一起推进；过程应体现玩家离开后仍在发生的因果。
6. 用三个机会窗口、三个 tier 里程碑、一次关系反转和一次阶层跃迁闭合循环。更大区域只放在 `expansions[].candidate`，由触发里程碑将它 materialize。

## 安全语法

条件只接受 `all`、`any`、`not`、`eq`、`ne`、`gte`、`lte`、`gt`、`lt`、`contains`、`truthy`。路径只读业务状态（例如 `player.debt`、`actors.clerk.trust`、`world.minute`、`opportunities.filing_window.close`、`metrics.chain_integrity`）。Patch 只接受 `set`、`add`、`append_unique`、`remove`、`merge`，且不能触碰 campaign、turn、hash 或历史。Fact 只表达已成立的文本、可见性、类型和来源。

蓝图不得执行 Python、加载插件、注入 DSL、依赖未知字段或让 Narrator 创造事实。每个基础动作和 `expansions[].candidate.actions[]` 都必须声明正整数 `max_uses`；引擎在成功和失败分支都计数，达到上限后动作不可再刷。`initial_state.world` 必须保留 `completed_milestones`、`process_last_run`、`materialized_expansions` 三个容器；里程碑只记录完成事实，不能直接写入 `materialized_expansions`。引擎在里程碑提交后重新评估 `expansions[].trigger`，并原子地把扩展 ID 写入 `materialized_expansions`、应用候选 `state_patches`，再解锁候选动作、过程和里程碑。

## 反换皮检查

把一个世界的资源名替换成另一个世界的名词，再比较以下项目：控制缺口、状态维度、动作标签、机会成本、最优顺序、离屏过程和杠杆消融。如果只剩标题、颜色、prose 或成本数字差异，就是换皮。霜港要求看见供给流、盐雾维护和潮汐窗口；灰印要求验证证据来源、兑现承诺和程序期限。两者不能用同一条“搜集—升级—战斗”路线证明完成。

## LLM 候选与编译门禁

LLM 只能提出候选 `premise`、动作描述和事实文本。主机先做 JSON schema、ID 引用、路径、条件和 patch 白名单检查，再做动作数量、窗口、过程、复利、关系反转、阶层跃迁、扩展和杠杆门禁。通过后才允许纯引擎 `compile_blueprint`；预览和失败不写存档。真正提交前还要做反换皮、杠杆 ablation、玩家投影可见性和 deterministic replay 检查。任何 prompt 没有足够证据时，注册表只能返回一个 reviewed world 加 `fit_warning`，不能声称已经生成完全独特机制。
