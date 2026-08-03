# TheGreatNovel 开发合同

> 状态：Phase 10G0.1 文档收敛合同；Genesis 生产实现尚未开始。
> 当前行为基线：`pc1-frozen`。
> 本合同取代提交 `9cdadc472cd92ce38e42767a896718fcad61f938` 中分散在
> `MVP_REWRITE_SPEC.md`、`GENESIS_FOUNDATION.md`、`DEFERRED.md` 与
> `PHASE1_9_HARDCODING_INVENTORY.md` 的当前开发口径；原文仍由 Git 历史保存。

本文只回答三件事：

1. 当前已经实现并冻结了什么；
2. Genesis 和后续功能应当怎样进入真实、可验证的游戏闭环；
3. 下一阶段允许做什么、以什么证据完成。

产品为什么这样设计，以 [`DESIGN_VALUES.md`](DESIGN_VALUES.md) 为准。本文不重复设计
宣言，也不把未来候选结构冒充为当前能力。

---

## 1. 文档与事实的权威顺序

不同对象使用不同权威，不能用一份文档覆盖所有事实：

| 要判断的问题 | 第一权威 | 冲突处理 |
|---|---|---|
| 当前代码实际上会怎样运行 | frozen tag 指向的代码、测试与 artifact | 文档不得重新解释 frozen 行为 |
| 产品长期要保护什么 | `DESIGN_VALUES.md` | 新实现与其冲突时，停止并修改设计或显式 supersede |
| 当前开发阶段应怎样实现与验收 | 本文 | 必须同时服从设计价值与 frozen compatibility |
| 当前仓库状态摘要 | `README.md` | README 只做索引，不创建新合同 |
| Agent 调度与改动边界 | `AGENTS.md` | 只约束执行过程，不替代产品/实现合同 |
| 历史方案和当时的 exact 草案 | Git commit/tag 中的旧文档 | 仅作证据；除非本文显式恢复，否则不是 active roadmap |

冲突时遵循以下规则：

- 不得原地改写任何 frozen implementation、accepted test、freeze tag 或旧 artifact 语义；
- 新方向必须通过明确命名的 superseding phase/milestone 落地；
- `DESIGN_VALUES.md` 决定未来方向，但不能追溯性改变旧 Campaign 的含义；
- 本文没有定义的 future feature 不因出现在路线图、Prompt 或 Narrator prose 中而存在；
- reviewer 共识不是代码事实，必须给出文件、符号、测试、hash 或 Git ref 证据。

当前 `docs/` 只保留两份权威内容文档：

- `DESIGN_VALUES.md`：为什么做、不可妥协的体验与架构价值；
- `DEV_SPEC.md`：怎么做、当前边界、active roadmap 与验收合同。

---

## 2. 当前实现事实与冻结边界

### 2.1 当前能力

当前可玩的唯一 runtime profile 仍是 `phase75_expedition_v1`。它是一条经过验证的
bounded vertical slice，包含固定 base/target、`DROP / SEARCH / EXTRACT`、固定 cost、
`target_searched`、Day/Night、progression、三个 build、Mara、Knowledge Boundary、
Projection、Session、Campaign、Story 与 PC1。

它可以换显示标题、premise、locale 和 labels，但不能因此获得新的地点拓扑、海洋物理、
载具所有权、活体 Habitat、义肢、网络入侵、peers、全民投放或通用 Capability 语义。
把任意题材映射到这条循环，只会得到换皮世界，不是 Genesis。

当前仓库没有：

- `src/tgn/genesis/**` 或 Genesis Request/Proposal/Report/Blueprint 的生产模型；
- 第二个结构不同的 runtime profile；
- Genesis WorldPack compiler、preflight、seal 或 PC2；
- 真实 LLM provider、Prompt coverage critic 或自然语言 action interpreter；
- 通用 Habitat、Peer Population、Cybernetic Intrusion、Capability Foundation。

### 2.2 冻结 registry

下表记录 tag 的 peeled commit。Annotated tag object 自身也不得移动、删除或重建。

| boundary | peeled commit |
|---|---|
| `phase1-core-v1` | `2bad219e8e12469ca4cf26459fba04dfedb452fc` |
| `phase2-action-v1` | `421e7c753af880f4450e09bdaaacd70f2c113bb3` |
| `phase3-expedition-v1` | `31f691ac9dd57f3a8271fee56fb34cf0bc45e78e` |
| `phase35-watch-v1` | `dc663512394a945afb79e32f7b8ba99cc27d39c7` |
| `phase-3.7-frozen` | `d578cf2ebd524acae72adc03293fa197666dfa11` |
| `phase-4-frozen` | `018d80ac969cf25732a0ebd576cca9047b851718` |
| `phase-5-frozen` | `a1d2c7073df1c2d2ec4252da0b0999de7a023c06` |
| `phase-6-frozen` | `d019ecdfac2b1a1f57bfac716354a0f751143061` |
| `phase-7-frozen` | `5786740eea91b0ed3dad21b81f3db0a3acffc7aa` |
| `phase-7.5-frozen` | `15de80df68de7ca343f9d36bcbbfe1a6333ddac9` |
| `phase-8-frozen` | `1dbf380b7a0639c941fe114c6ffccf72eddfbaa3` |
| `phase-9a-frozen` | `a616b1a355d2607840944e270650b26fbd439dcd` |
| `phase-9b1-frozen` | `a4c79a47dfac88c3f9b39aa8ca50cc6255d48902` |
| `phase-9b2a-frozen` | `60ebf493ba90114c4f03048558e316ac07118ee2` |
| `phase-9b2b-frozen` | `218a246add4481088872487e80ac83ad1099171b` |
| `phase-9c1-frozen` | `9bb739fdb1bd08d4c0c036e7c3d3c0ee5d083f01` |
| `phase-9c2-frozen` | `40c8a59636a6ee26e0d779228804b4c989753085` |
| `pc1-frozen` | `17d4098771798e44a078e6a93a94137feb0bd8c0` |

README 中记录的 accepted implementation SHA 与 freeze documentation commit 可能不同；
二者都保留。PC1 accepted implementation 是
`96ffe3eefa9ea6558e3f9105f0a5a47838e3a1ce`，冻结文件边界是
`src/tgn/play/**` 与 `tests/play/**`。Phase 9C2 accepted implementation 是
`f9a8a10adb7579fe4e06e462fbbeee47cdf69aea`。未来修复只能显式 reopen，或进入新的
superseding milestone 并使用新的 implementation SHA 与 freeze tag。

### 2.3 必须保留的 Kernel

以下是跨世界完整性基础，不因 Genesis 方向重写：

- GameState metadata shell 与 DomainEvent provenance；
- canonical JSON、state/artifact hash 与 corruption detection；
- SQLite EventStore、Snapshot、Replay、Verify；
- RecordedDecision 与 choice-id/action legality 边界；
- Campaign 原子发布与旧 bundle compatibility；
- Story sidecar、pending/resume、committed-turn immutability、commit-before-print；
- public/private Observation、Actor Knowledge 与 Player Knowledge 分离；
- PC1 thin-client boundary 与 deterministic novel export。

保留 Kernel 不表示 Core 当前已经足够通用。新的 runtime feature 必须通过新接缝进入，
不能继续把所有 gameplay `elif` 堆进 frozen Core。

---

## 3. Genesis 产品定义

Genesis 的目标是让玩家用自然语言和 Seed 描述一个世界，系统生成一份 Campaign-specific
WorldPack；玩家不需要从开发者写好的故事世界菜单中挑选。

```text
Raw Prompt + Seed
→ Requirement Proposal
→ Requirement Coverage Approval
→ Feature Requirement Report
→ Campaign-specific World Blueprint / World Bible
→ bounded Runtime Binding
→ candidate WorldPack + candidate Initial State
→ static validation + scripted gameplay preflight
→ structural/depth assessment + required acknowledgements
→ one atomic seal and Campaign publication
→ deterministic play + Replay + Story
```

核心权威链不变：

```text
LLM proposes.
Python validates and binds.
The deterministic runtime decides.
SQLite remembers.
The narrator describes committed facts.
```

Seed 只决定明确生成合同下的生成路径。模型、provider、template 或服务端版本变化都可能
改变生成结果；因此 Replay 不重新询问 LLM。实际被接受、canonical serialize、hash 并
原子封存的 artifact 决定 Campaign 中什么是真的。

### 3.1 两条合法产品路线

| route | world source | 必须展示的身份 | 可否称为 Genesis |
|---|---|---|---|
| `GENERATED_GENESIS` | Prompt + Seed + accepted lineage | 生成合同、支持/降级、semantic/provenance identity | yes |
| `AUTHORED_WORLD` | 开发者/作者手工 WorldPack | authored/official/fixture/legacy 来源 | no，除非它本身完整经过 Genesis 流程 |

两条路线都必须遵守 State/Event/Replay/Narrator authority。区别只在世界如何产生，不在
游戏运行时是否可以随意编事实。

---

## 4. 事实、隐私与可见性

### 4.1 三类事实

**Authoritative durable fact**：经过 Python validate/bind/commit，拥有 stable ID，保存并
可 hash，能够进入 WorldPack、Initial State、Event、Replay 或 sealed expansion。

**Candidate durable fact**：LLM、玩家或工具提出但尚未被接受的世界、人物、秘密、
requirement、blueprint、binding 或 expansion。它可以作为 attempt 证据保存，但不是
GameState、DomainEvent、Campaign 或 Narrator 可用事实。

**Ephemeral non-authoritative texture**：气味、光影、停顿、语气等不改变因果链的表达。
它可以重新生成，但不能创建资源、关系、能力、秘密、Event 或后果。

### 4.2 隐私与世界秘密不能共用一个 `hidden_data`

未来 artifact 必须把两个轴分开：

- **输入隐私轴**：`PUBLIC_INPUT` / `PLAYER_PRIVATE_INPUT`；
- **世界可见性轴**：`PUBLIC_WORLD` / `WORLD_HIDDEN` / `ACTOR_SCOPED`。

随后由确定性 Projection 产生：

- 玩家当前可观察事实；
- 某个 Actor 当前已知事实；
- Narrator 当前允许表达的公开事实。

玩家私有创作意图不自动成为世界隐藏真相；世界隐藏真相也不自动暴露给玩家或 Narrator。
任何 visibility 变化必须来自合法 Action/Event/Rule，不能来自 prose。

---

## 5. Genesis logical artifacts

本节冻结职责和依赖方向，不冻结尚未被真实 vertical slice 证明的最终文件名、数据库表或
Python package layout。

### 5.1 Genesis Request

保存原始 Prompt、Seed、locale、显式约束、request ID 和 policy reference。它是持久的
lineage 输入，不是 runtime fact。`raw_prompt` 是不可信数据，不能读取文件、执行命令、
修改 Catalog、请求凭据、加载模块或改变 Engine 权限。

### 5.2 Requirement Proposal

由 LLM edge 或 recorded fixture 把 Request 提取为结构化候选需求。每项至少能够追踪：

- requirement ID 与 raw source reference；
- normalized intent 与 requirement kind；
- `STRICT / DEGRADABLE / OPTIONAL` acceptance policy；
- exclusivity、ownership、resource 和其他 typed constraints；
- candidate Content/Runtime Feature IDs；
- generation metadata reference。

Proposal 非权威。Python 可以验证其结构和安全边界，不能仅靠自身证明它完整理解了
自然语言。

### 5.3 Requirement Coverage Approval

在 Report/Blueprint 继续之前，系统必须展示可读的核心世界合同摘要，并把以下内容保存为
有 hash 的 approval：

- 它覆盖哪个 Request 与 Proposal；
- 哪些语句被解释成 core/strict requirement；
- 哪些被解释成 degradable/optional；
- 玩家是确认、修改还是取消；
- fixture 路径使用哪个 expected approval artifact。

Approval 不证明 runtime support；它只关闭“Proposal 漏掉了 Prompt 核心要求”的边界。
修改必须创建新 Proposal/Approval，不覆盖历史记录。

### 5.4 Feature Requirement Report

确定性 evaluator 根据版本化 Catalog 对 Proposal 做支持分类。evaluator 是纯函数：

```text
evaluate(request, proposal, catalog)
→ canonical FeatureRequirementReport | stable validation error
```

它不读写文件、SQLite、Campaign、GameState、EventStore 或 Story，也不负责 attempt 生命周期；
这些属于外层 orchestration 和后续 publication slice。规范化 item 至少包含：

```text
requirement_id
catalog_layer: CONTENT | RUNTIME
support_status: SUPPORTED | DEGRADED | UNSUPPORTED | REJECTED
warnings[]
reason_code
bound_feature_ids[]
accepted_scope
lost_capabilities[]
player_visible_effect
acknowledgement_required
disposition: BIND | BIND_DEGRADED | OMIT | BLOCK
```

Report 顶层只需保存 source hashes、catalog/report versions、`items[]` 与
`requirements_gate_passed`。状态集合、计数和 UI 分组由 `items[]` 确定性派生，不重复保存。
Report 不输出 `seal_allowed`：这时 Blueprint、Binding、WorldPack、Initial State 和
Preflight 仍不存在，最终 seal eligibility 必须由后续所有 gate 汇总。

### 5.5 World Blueprint / World Bible

描述 Campaign 的宏观世界、初始区域、远方约束、public/hidden facts、主角、地点、Actor、
派系、资源生态、Story Engines、压力与机会。它不是固定章节脚本，也不是 runtime support。
只有被后续 binding 接受的部分才能进入 WorldPack。

### 5.6 Bound Runtime Configuration

将 Blueprint 需求绑定到已经实现、版本化、可验证的 runtime semantics。它只能引用稳定
Feature ID 与 contract version；参数必须严格校验。禁止动态 Python、`eval`、表达式、
任意 DSL、plugin loading、Narrator 补机制和 unknown-field fallback。

### 5.7 Candidate Genesis Bundle

包含 candidate WorldPack、candidate Initial State、lineage hashes、compiler identity 和待跑
gate。它可以 canonicalize 和计算临时 hash，但仍不是 authority、不是 sealed WorldPack、
不是正式 Campaign，也不能进入存档列表。

### 5.8 Preflight / Structural / Depth reports

这些是最终 seal 前的机器可读 proof artifacts：

- static schema/reference/security/invariant report；
- scripted gameplay/replay report；
- `STRUCTURAL_DIVERGENCE_V1` 或更高 depth assessment；
- bounded retry/failure report；
- 必要的 degraded acknowledgement。

它们不能在 seal 后反向修改 WorldPack。若任何 required gate 未通过，只能创建新的 attempt。

### 5.9 Sealed Genesis Bundle 与 WorldPack

`WorldPack` 保存运行语义和静态世界事实；`SealedGenesisBundle` 保存 WorldPack、Initial
State、完整 lineage、proofs、acknowledgements、compiler identity 与最终 commit record。
二者都是不可变 artifact。Campaign 同时引用 semantic identity 与 sealed provenance
identity，Replay 不需要重新调用 Generator。

### 5.10 Initial Authoritative GameState

只能从 candidate WorldPack 确定性 materialize，通过 core/feature invariants 与 preflight，
随后和 WorldPack 在同一次最终 commit 中成为 authority。不能从 Prompt、Blueprint、prose
或未来模型重新生成。

### 5.11 Runtime Expansion

见第 10 节。它是绑定父 WorldPack 的 immutable child artifact，不是基础 WorldPack 的
可变尾部。

### 5.12 Narration artifacts

Narration Request、committed turn、expression/translation version 与 `novel.md` 都是
derived artifacts。它们描述已提交的公开事实，不进入 gameplay Replay，也不能反向成为
WorldPack、State 或 Event authority。

---

## 6. Feature Catalog 与 Requirement semantics

### 6.1 四层目录

| layer | 用途 | 是否接受玩家 requirement binding |
|---|---|---|
| Content Capability | title、premise、labels、locale 与不承载机制的世界表达 | yes |
| Runtime Semantic Feature | State/Action/Event/Reducer/Invariant/Projection/Replay 的运行语义 | yes |
| Kernel Guarantee | EventStore、hash、Replay、Verify、atomicity 等前置能力 | no，作为 compiler gate |
| Legacy Compatibility | 旧 profile、bundle、adapter 与 frozen regression | no，只用于旧包/fixture/迁移 |

目录中不得预注册尚无真实 Feature Contract 的一长串未来 ID。一个合理但未实现的需求可以
返回稳定 reason code `NO_MATCHING_RUNTIME_CONTRACT`，不需要先发明 placeholder architecture。
Compiler 可以在内部组合有限、已经实现并验证的 Runtime Feature；禁止的是把开发者写好的
故事世界/profile 当成玩家的 Genesis 菜单，不是禁止复用真实运行语义。

`SUPPORTED` 只有一个枚举值，但它必须与 `catalog_layer` 一起读：

- Content `SUPPORTED` 只表示可以忠实保存/表达内容；
- Runtime `SUPPORTED` 才表示完整确定性机制已经存在；
- Kernel/Legacy 不作为玩家 requirement 的 `SUPPORTED` item。

### 6.2 支持状态

| status | 语义 | binding 行为 |
|---|---|---|
| `SUPPORTED` | 在该 catalog layer 内关键意思不丢失，完整路径可验证 | `BIND` |
| `DEGRADED` | 有真实但更窄的运行语义，并列明损失和玩家可见差异 | 仅 `DEGRADABLE` 且确认后 `BIND_DEGRADED` |
| `UNSUPPORTED` | 需求合理但没有对应真实合同 | `OPTIONAL` 为 `OMIT`，其他为 `BLOCK` |
| `REJECTED` | 违反 schema、安全、authority 或可验证性 | 总是 `BLOCK`，确认不能绕过 |

`warnings[]` 用于歧义、冲突、exclusivity 未定义、content/runtime 混淆等。任何 unresolved
warning 都使 `requirements_gate_passed=false`；解决 warning 必须创建新 Report，不能修改
旧 hash。

### 6.3 Required、degraded 与 optional

- `STRICT`：`DEGRADED` 与 `UNSUPPORTED` 都阻断；
- `DEGRADABLE`：只允许采用 Catalog 已明确定义的窄语义，并在继续前确认；
- `OPTIONAL`：unsupported 时自动 `OMIT`，仍保留 item、reason 与可见影响，不阻断；
- exclusivity、ownership、唯一主角优势、资源排除、永久扣除等核心规则默认 `STRICT`；
- acknowledgement 不能把 `UNSUPPORTED` 或 `REJECTED` 改成 `SUPPORTED`。

一般的“能力有代价”不能自动候选 `exclusive_resource`：代价也可能是 stamina、时间、风险
或机会。只有原需求明确要求排他资源、排除普通材料和永久扣除时，才允许绑定对应的已实现
合同；没有 exact contract 时必须返回 `NO_MATCHING_RUNTIME_CONTRACT`。

### 6.4 Feature 进入 Catalog 的最低证据

一个 runtime Feature 必须同时回答：

1. stable Feature ID、contract version 与具体产品问题；
2. authoritative State 在哪里；
3. legal Action、参数与失败 code；
4. DomainEvent、Reducer 与 before/after invariants；
5. public/private/Actor Knowledge Projection；
6. persistence、Replay、Verify 与 corruption behavior；
7. scripted/autoplay proof 与 strategy consequence；
8. 与 frozen profile/bundle 的 compatibility；
9. 明确 non-goals。

只有 helper、label、roadmap entry、相似字段或 Narrator 描述时，一律不合格。

---

## 7. 世界完整度与 anti-reskin gate

### 7.1 三层世界结构

**Macro World — 开局完整**

- 世界规律、历史、文明与地理骨架；
- 核心派系、主要冲突、长期压力与核心秘密；
- 主角身份、长期非对称优势和成长方向；
- Story Engine 的稳定 ID、参与者、目标、风险与演化边界；
- 远方区域 namespace、事实锚点、约束与 child-seed policy。

**Initial Region — 开局详细可玩**

- entry location、可达地点与合法移动；
- 当前可交互 Actor、资源、压力、机会与信息边界；
- 至少一个可重复验证的短期 gameplay loop；
- 初始 Observation、legal actions、失败路径和 Replay proof。

**Remote Regions — 受约束惰性物化**

- seal 时不要求每条街道、次要 NPC、室内或配方全部存在；
- 必须先有稳定 namespace、宏观事实、已知连接、约束、预算与 child seed；
- 物化前是 candidate，物化后通过 child seal/Event 才成为 world truth；
- 不能因为玩家尚未看到就静默重写。

### 7.2 Depth L0 — `STRUCTURAL_DIVERGENCE_V1`

所有 `GENERATED_GENESIS` Campaign 的最低门禁：

- 与 `phase75_expedition_v1` 相比，至少一个结构维度真实不同：地点拓扑、资源循环、
  pressure/opportunity、Actor goal、ownership、protagonist advantage 或合法 Action；
- 差异必须进入 State/Action/Event/Projection/Replay，而非只改 title、label、premise、
  resource name 或 prose；
- A/B 移除该新语义后，legal action、reachable strategy 或 resource/opportunity cost 至少
  一项发生可测变化；
- scripted preflight 必须完成合同规定的 accepted decisions，不能退化为 WAIT-only；
- 失败不得降级成仍标为 Genesis 的 legacy reskin。

### 7.3 Depth L1 — `WORLD_DEPTH_L1`

L1 证明世界已经不仅是一个新机制切片：

- 至少一个真实可行走的地点图；第一版目标为至少 3 个相连地点；
- 至少 1 个会随时间推进的 pressure/opportunity clock；
- 至少 1 个可错过且不可逆的机会；
- 20 个有意义回合不进入 WAIT-only 或单一动作坍缩；
- 上述差异全部进入 State/Event/Projection/Replay。

### 7.4 Depth L2 — `WORLD_DEPTH_L2`

L2 证明玩家看不到的世界也在运行，并且主角优势真实改变策略：

- 至少 2 个拥有独立目标的 Actor；
- 至少 2 个同时推进的 pressure/opportunity clocks；
- 至少一个 Actor/世界线程在玩家不在场时确定性推进；
- 主角长期非对称优势的启用/移除产生 legal action、reachable strategy 或
  resource/opportunity cost 差异；
- Rich E2E 的 20–30 回合测试不出现 WAIT-only、单一动作或所有世界同循环坍缩。

不得展示未通过的 depth claim。若 L2 失败但 L1/L0 真实通过，只能在有限重生成结束后
明确标为相应较低等级；若 L0 也失败，则不创建 Genesis Campaign。

### 7.5 主角优势与成长

每个正式 Genesis 世界都应给主角一个长期非对称成长优势，但不强制都是超能力。它可以
来自能力、载具、知识、身份、关系、装备、组织权限或环境适配。

`Absolute Power` 指已经永久获得的策略容量，单调不减；`Effective Capacity` 可以因伤势、
资源、位置、维护或机会暂时受限；`Relative Standing` 会随 cohort 改变和短期回撤。这样
既保留爽文成长，也让时间、世界竞争和错失机会继续有意义。

---

## 8. Hash、lineage 与 identity

### 8.1 `world_semantic_hash`

只表示世界在运行时是什么，至少覆盖：

- semantic schema version；
- accepted Runtime Feature IDs 与 contract versions；
- macro facts、initial-region facts、public/hidden world data；
- remote namespaces、约束与 materialization descriptors；
- stable IDs、initial-state materialization inputs。

它不包含 provider、model、template、聊天记录或生成时间。两次生成若得到完全相同的
canonical runtime semantics，可以拥有相同 semantic hash。

### 8.2 `sealed_bundle_hash`

表示这次 Campaign 的完整生成与验收历史，至少覆盖：

- `world_semantic_hash` 与 `initial_state_hash`；
- Request、Proposal、Coverage Approval、Report、Blueprint、Binding hashes；
- compiler ID/schema/implementation digest；
- generation policy 与经过隐私处理的 metadata；
- preflight、structural/depth reports 与 acknowledgements；
- seal schema version。

因此“世界语义是否相同”和“这份世界怎样产生”可以分别比较。Generation metadata 不是
world authority，但属于不可替换的 provenance。

### 8.3 Initial State 与 Event identity

`initial_state_hash` 绑定 `world_semantic_hash`、state schema 与完整 canonical payload。
Campaign manifest 同时引用 `world_semantic_hash`、`sealed_bundle_hash` 和
`initial_state_hash`。DomainEvent 继续绑定 before/after state hash、event sequence 与
Campaign identity。

禁止循环 hash：WorldPack 不嵌入尚未计算的 Initial State hash；Initial State 不反写
WorldPack。顺序固定为 semantic WorldPack → Initial State → sealed bundle → Campaign commit。

---

## 9. Preflight、seal 与原子发布

### 9.1 Preflight 必须在 seal 前

Candidate bundle 至少通过：

- schema、unknown field、reference、stable ID 与 security validation；
- Feature-local state、legality、invariant 与 initial Observation；
- 必需资源/路径可达和无零时间循环；
- scripted gameplay smoke；
- Event Replay 与 final state hash equality；
- `STRUCTURAL_DIVERGENCE_V1`，以及被声明的更高 depth gate；
- Requirement Coverage Approval 与必要 acknowledgements；
- old bundle/PC1 compatibility regression。

Preflight 使用 candidate hash 绑定输入和输出，但不把 candidate 称为 sealed WorldPack。
超时不是成功，只能 `FAIL` 或合同明确允许的 bounded degraded result。

### 9.2 唯一 authority transition

```text
candidate artifacts in an attempt workspace
→ all gates pass
→ compute final canonical artifacts and hashes
→ one no-replace atomic Campaign publication
→ authority exists
```

实现可以使用同父级 staging directory、SQLite transaction 或经过证明的等价机制，但必须
满足：

- 正式 namespace 在 commit 前不可见；
- WorldPack、Initial State、commit record、Campaign record、empty EventStore 与 Story
  bootstrap 要么全部可见，要么全部不可见；
- publication 使用 no-replace，不覆盖竞争者或既有 Campaign；
- symlink/reparse/path escape、source/target identity 与 canonical bytes 都重新验证；
- crash leftover 只能作为非权威 attempt，被清理或人工检查，不能自动晋升；
- 正式状态只有 `COMMITTED/PUBLISHED`，没有可加载的 `PREPARED` Campaign。

具体路径、manifest JSON 和平台恢复协议必须由实现 slice 根据真实故障模式冻结；G0.1
不预先创建通用 workflow engine。

### 9.3 有限重生成

失败可以产生 stable machine-readable errors。每次修复或重生成使用新的 attempt ID，不能
复用旧 seal/Campaign ID。自动重生成由版本化 policy 控制：

- 初始 Foundation slice 默认 `max_regenerations=0`；
- 产品启用前可在独立阶段证明最多 1–2 次 bounded regeneration；
- 重生成后仍失败，只能明确采用真实通过且满足所有 strict requirement 的较低 depth level，
  或失败/取消；
- 永远禁止无限 repair loop、隐式权限升级和失败后留下正式副作用。

---

## 10. Runtime Expansion 合同

Runtime Expansion 的逻辑权威边界已经确定：

```text
sealed base WorldPack semantic hash
+ sealed bundle / Campaign identity
+ macro World Bible and remote constraints
+ committed Campaign history
+ stable expansion namespace and region/entity ID
+ deterministic child seed
→ candidate expansion
→ schema/reference/feature validation
→ runtime binding
→ scripted preflight
→ child semantic/provenance hashes
→ atomic child activation + Expansion Event
```

必须满足：

- child artifact immutable，并绑定父 `world_semantic_hash`、Campaign、namespace 和 child seed；
- 父 WorldPack、父 hash 和已提交 child 都不可覆盖；
- State 只有在 child artifact 与引用其 hash 的 Expansion Event 成为同一 authority unit 后，
  才能引用新 entity/location/thread；
- Campaign 的 expansion manifest 是 append-only，并能从 Event history/child hashes 验证；
- Replay 读取保存的 child artifact，不重新询问 LLM；
- 失败没有部分 child、部分 Event 或悬空 State reference；
- Narrator 不能提交 expansion，也不能把 candidate 写成已发现事实；
- 具体 quota、最大深度、触发策略和存储 schema 必须在实现 phase 中版本化，但不得改变
  上述不变量。

---

## 11. Runtime authority 与行动合同

### 11.1 单一事实源

Campaign 的动态事实只存在于已提交 Initial State、EventStore history 与可验证 Snapshot。
YAML、Prompt、World Bible、Narration、UI cache 和 novel export 都不能成为 mutable save。

### 11.2 所有变化经过合法 Action 与 Reducer

```text
public/private Observation
→ offered choice/action schema
→ submitted choice_id + typed params
→ legality validation
→ deterministic resolution / RNG draw
→ DomainEvent(s)
→ pure reducer
→ invariants
→ atomic EventStore commit
→ new Observation / Story request
```

- 玩家可以表达任意意图，但 Engine 只结算当前合同能表达的行动；
- 不合法行动不写 Event、不推进时间、不消耗 RNG、不改变 State；
- 一个 accepted decision 可以产生一个或多个 Event；新 runtime 不得继承“永远单 Event”的
  legacy 偶然假设；
- RNG state 属于 authority，随机 draw 必须可 Replay；
- Reducer 和 invariant 是 anti-forgery boundary，不能由 LLM、Narrator 或客户端绕过。

### 11.3 Decision 原子性

一个 decision 的 events、state transition、RNG、decision record 与必要 snapshot 必须在
同一事务中提交。任一步失败全部回滚。外部 Story 失败不回滚已经提交的 gameplay；它保留
pending narration request 并允许幂等恢复。

---

## 12. Observation、Knowledge、Story 与语言

### 12.1 Knowledge Boundary

```text
World Truth ≠ Actor Knowledge ≠ Player Observation ≠ Narrator Context
```

NPC 只能根据自己知道的事实行动；玩家只看到合法 Projection；Narrator 只收到可公开的
committed facts。秘密、关系意愿、隐藏属性、未来成功概率或其他 Actor 私有信息不能因为
存在于 WorldPack 就自动泄露。

### 12.2 Story authority

Story sidecar 保存 deterministic Narration Request、pending/resume 与 immutable committed
turn。正确顺序是：

```text
authoritative Event / public result
→ structured narration brief and claims
→ prose
→ committed turn
→ deterministic novel export
```

不能解析散文关键词来恢复资源、伤害、关系或能力事实。Narration error 只影响 Story，
不修改 GameState/EventStore。表达修订必须创建新 version，不覆盖原 committed artifact。

### 12.3 Locale

- `input_locale` 属于玩家/LLM edge；
- `content_locale` 属于 WorldPack 显示内容；
- `narration_locale` 属于 Story 表达。

Locale 不得改变 stable ID、legal action、Event sequence、state hash 或 Replay。不同语言可以
有不同 prose/labels/export，但必须绑定相同 committed facts。

---

## 13. Vertical Slice 开发纪律

### 13.1 一个 Feature 的完整闭环

任何新机制必须在同一个可验收 slice 内完成：

```text
product requirement
→ Feature Contract
→ State
→ legal Action
→ Event
→ Reducer
→ Invariant
→ Observation / Knowledge
→ persistence
→ Replay / Verify
→ scripted/autoplay proof
→ metrics and regression
```

缺任一层就不能标 `SUPPORTED`。多个内部 checkpoint 可以按顺序开发，但在完整闭环前不
建立 accepted implementation 或 freeze tag。

### 13.2 抽象必须由真实需求挣出来

```text
first concrete vertical slice
→ second structurally different pressure slice
→ observe repeated causal structure
→ extract the smallest shared abstraction
```

禁止为了未来可能用到而预建：

- `UniversalRuleEngine`、`UniversalWorldSchema`、generic effect/ability graph；
- dynamic handler/plugin/registry/module loader；
- arbitrary expression evaluator 或 LLM-generated Python；
- generic entity graph、relationship graph、scheduler、workflow engine；
- 一次性把 frozen reducer/invariants 全部迁移。

### 13.3 Test pyramid

每个 active slice 至少包含：

1. unit tests：schema、legality、reducer、invariants、hash；
2. scenario tests：success、failure、boundary、corruption；
3. scripted autoplay：happy path、greed/exploit、resource/time pressure、deadlock；
4. replay/verify：逐 Event 与 final hash 相等；
5. compatibility：所有相关 frozen tests 和旧 artifact verify；
6. design signals：choice conflict、strategy divergence、opportunity cost、feature reachability。

LLM Judge 只能提供 soft evaluation，不能覆盖 integrity hard gate。

### 13.4 Definition of Done

- 功能具有明确 scope 与 non-goals；
- 所有 authority、failure、hash、Replay 与 migration 语义已写清；
- focused tests、affected tests、full suite 按风险通过；
- 新代码覆盖率和 warnings 满足该 phase 的验收合同；
- 至少一个 exploit/negative scenario；
- 没有修改 frozen code/test/tag/artifact；
- 独立 reviewer 没有未关闭 BLOCKER；
- README/本合同只在结果确实发生后更新；
- commit、implementation SHA 与新 freeze tag 只在所有门禁通过后创建。

---

## 14. Active Roadmap

项目只维护一张 Active Roadmap。旧文档中的 Historical Phase 11/12、旧
`devour_evolution` Phase 10A 候选和原始 MVP 0–6 编号都属于历史，不占用当前编号。

### Phase 10G0.1 — Contract Consolidation

目标：将设计价值与开发合同收敛为两份文档，关闭 G0 的内部矛盾，不修改生产代码、测试、
配置、tag 或 artifact。

### Phase 10V1 — Genesis Foundation Vertical Slice

这是下一项可接受实现，不是 10A–10E 五个独立冻结阶段。内部 checkpoint 可以依次实现，
但必须作为一个 work item 完成：

1. 一个固定、recorded Prompt/Seed fixture；
2. Proposal + Coverage Approval + deterministic Report；
3. bounded Blueprint/Binding；
4. 一个真实、非 legacy、改变策略的最小 runtime pressure slice；
5. candidate WorldPack/Initial State；
6. static + gameplay preflight；
7. `STRUCTURAL_DIVERGENCE_V1`；
8. 一次原子 seal/Campaign publication；
9. 至少 20 个 accepted decisions 的 scripted autoplay、Replay 与 Verify；
10. old PC1/bundle/frozen suite compatibility。

进入 coding 前必须在 phase prompt 中选定唯一 pressure slice。默认建议从海洋/玄武 Prompt
中只截取“一个既有成长对象的升级明确排除普通材料，并永久消耗专属资源”这一条
resource/progression 因果链；不得顺带声称已经支持活体 Habitat、所有权、海洋物理、全民
peers、通用载具或通用 Capability framework。完整 Xuanwu/Habitat 仍属于后续产品压力
slice。若用户改选义肢入侵，也只能选择一个 bounded Action/State/Event 后果链。

### Phase 10V2 — Proposal Edge and Coverage

在 V1 已证明完整链路后，引入 provider-neutral proposal edge、recorded/fake provider、
coverage critic/用户确认与有限失败策略。真实网络 provider、凭据和预算需要独立批准，
不能混进 deterministic evaluator。

### Phase 11V1 — World Depth L1 Runtime Slice

以真实 WorldPack 压力实现 LocationGraph、一个 pressure/opportunity clock 与一个不可逆
机会，并通过 `WORLD_DEPTH_L1`。它必须形成 State/Action/Event/Projection/Replay 的完整
vertical slice，不建立尚未被 L2 需求证明的通用 Actor/scheduler framework。

### Phase 11E — Rich Generated World E2E / Depth L2

在 L1 以后增加至少两个独立 Actor goal、多时钟、off-screen deterministic progression 与
主角优势 A/B，完成 20–30 回合 Rich E2E 并通过 `WORLD_DEPTH_L2`。

### Phase 12 — Natural-Language Action Semantics

定义 intent proposal、clarification、legality binding、rejection、recording 与 Replay。
自由文本不能直接成为 Action/Event authority。

### Phase 13 — Capability Foundation

只有至少两个具体 capability slice 证明共享因果结构后，才提取最小公共抽象。禁止先写
SkillTree、EffectSystem、AbilityGraph mega-framework。

### Phase 14 — Product Pressure Slices

Cybernetic Intrusion、Xuanwu/Habitat、Mass Drop/Peer Population 等按产品优先级分别进入
bounded vertical slice。已在 10V1 使用的具体 slice 不重复实现，只在第二个真实需求出现后
评估抽象。

### PC2 — Genesis Player Client

PC1 保持冻结。PC2 只有在 Genesis Campaign 创建、resume/replay、失败清理、支持报告与
用户确认都已有生产证据后开始，并使用新的文件边界、implementation SHA 与 freeze tag。

---

## 15. 当前结构性硬编码与 superseding seams

本表是对 `pc1-frozen` 代码基线的活跃摘要，不要求 G0.1 修改代码：

| pressure | 真实代码证据 | 当前处理 | 未来 seam |
|---|---|---|---|
| 单一 WorldGen profile | `worldgen/models.py::MECHANICS_PROFILE`；`compiler.py::compile_worldpack` | 保留 legacy | 新 compiler/schema/profile identity |
| 固定 base/site/salvage/Mara | `worldgen/compiler.py::materialize_initial_state` | 合法 first slice | 新具体 profile，不在 v1 加主题分支 |
| 固定 expedition actions/costs | `gameplay/expedition.py` | 保留冻结行为 | feature-local Action contract |
| Core reducer 认识 gameplay | `core/reducer.py::reduce_event` | 不原地清理 | versioned feature handler seam |
| Core invariants 认识 phase/build/Mara | `core/invariants.py::check_invariants` | 保留 anti-forgery | feature-local invariant boundary |
| 两相 Day/Night 假设 | `gameplay/world_phase.py` | 不宣称通用 | 真实 3+ phase 需求后新 contract |
| 固定 build candidates | `gameplay/build_choice.py` | 不升级成 SkillTree | 具体 capability slice 后再抽象 |
| Projection 固定 action params | `projection/presenter.py` | 保留 schema v1 | Presentation v2 |
| Autoplay 直接导入 expedition | `autoplay/runner.py` | 保留当前 regression | versioned autoplay adapter |
| Session/Campaign 绑定 expedition | `session/service.py`、`campaign/service.py` | 保留 frozen contract | gameplay/artifact adapter v2 |
| Story reconstruction 绑定 expedition | `story/reconstruction.py` | 保留 deterministic Story | Story Context v2 |
| Request 不自带 Seed | `worldgen/models.py::WorldGenesisRequest` | 保留 v1 compatibility | new Genesis Request envelope |
| bundle/compiler identity 固定 | `worldgen/bundle.py`、`projection/bundle.py`、`campaign/verification.py` | 旧 identity 不变 | semantic/provenance v2 contract |

判断原则：常量不等于坏代码。当前 first slice 的常量可以保留；真正的风险是把它们冒充
宇宙规则，或让 generic layer 继续认识更多世界特例。

---

## 16. Deferred 与非目标

### 16.1 在进入对应 active phase 前继续延期

- 通用 combat/expedition/progression/talent/capability/relationship framework；
- 第二个以上 runtime profile 的通用 dispatcher；
- large-scale settlement、organization、economy、peer simulation；
- LLM NPC autonomy、agent planners、vector memory、emotion inference；
- real provider、credential handling、deep model/persona matrix；
- free-form action interpretation；
- Presentation v2、Story Context v2、PC2；
- runtime feature plugin、generic DSL、dynamic Python；
- unlimited repair、unbounded retry 或自动架构修改 Agent。

Deferred 表示尚无 active contract，不表示已经规划了某个 class、schema 或 package。

### 16.2 关系与联合成长质量门禁

任何未来关系 feature 除普通 Feature Contract 外，必须同时满足：

- 所有参与者均经过确定性成年 invariant；任何未成年或年龄不明状态都不能进入成人亲密
  关系/性相关路径；
- Action 可执行性不能推导 willingness、consent、love、forgiveness 或 moral correctness；
- consent、拒绝、撤回、压力、依赖与形成历史由 State/Event 明确记录；
- Actor agency 与 Knowledge Boundary 保持；
- Narrator 不能创造、升级、洗白或抹除关系事实；
- deterministic verification、negative scenarios 与独立外部 review 通过。

### 16.3 旧 `devour_evolution` 候选

`archive/phase10a-devour-candidate-2026-08-02` / `mvp-rewrite` 上验证到
`870284cc653e400603747dd9e14e41fa6df7795a` 的候选只作历史参考。它没有本分支 accepted
freeze tag，不是 Genesis 默认能力，不能直接恢复。若其因果结构未来重新获得产品需求，
必须作为新的 bounded slice 重新走 State/Event/Projection/Replay/Review。

---

## 17. 历史证据索引

合并文档不删除 Git 历史。需要核对 G0 原始 exact 草案时使用：

```powershell
git show 9cdadc472cd92ce38e42767a896718fcad61f938:docs/GENESIS_FOUNDATION.md
git show 9cdadc472cd92ce38e42767a896718fcad61f938:docs/PHASE1_9_HARDCODING_INVENTORY.md
git show 9cdadc472cd92ce38e42767a896718fcad61f938:docs/MVP_REWRITE_SPEC.md
git show 9cdadc472cd92ce38e42767a896718fcad61f938:docs/DEFERRED.md
```

需要核对某个 frozen phase 当时的 exact contract 时，读取对应 tag 的 README、spec、代码与
测试。例如：

```powershell
git show phase-9b1-frozen:docs/MVP_REWRITE_SPEC.md
git show phase-9b2b-frozen:docs/MVP_REWRITE_SPEC.md
git show phase-9c2-frozen:docs/MVP_REWRITE_SPEC.md
git show pc1-frozen:README.md
```

历史文档用于回答“当时接受了什么”，本文用于回答“下一步允许怎样开发”。不得把历史
roadmap、示例 schema 或未冻结候选直接复制成当前实现任务。

---

## 18. 下一阶段开始前必须填写的 Phase Contract

每个 coding phase 的执行 prompt 必须明确：

```text
phase / milestone name
product problem and chosen pressure slice
allowed files and frozen exclusions
exact State / Action / Event / Projection scope
artifact and migration identity
success, failure and atomicity semantics
focused / affected / full verification commands
coverage and warning gates
independent review plan
implementation SHA / freeze-tag plan
explicit non-goals
```

以下实现细节留给 10V1 phase contract，而不是 G0.1 先猜：

- exact Python package/file layout；
- exact JSON field limits 与 stable error list；
- attempt retention/cleanup 路径；
- Windows/POSIX publication primitive；
- 第一个 runtime pressure slice 的最终选择；
- expansion quota、最大深度和成本预算；
- provider metadata 的隐私/retention policy。

它们是有 owner 的 phase-entry decisions，不是允许实现者自由发挥的永久空白。

---

## 19. G0.1 验收边界

本次文档收敛完成的条件：

- `docs/` 只保留 `DESIGN_VALUES.md` 与 `DEV_SPEC.md`；
- README 和 AGENTS 只引用这两份权威内容文档；
- 10A/attempt、seal/preflight、depth/deferred、Catalog/hash、atomicity 矛盾关闭；
- `src/**`、`tests/**`、配置、artifact、Git tag 与历史不变；
- `pc1-frozen..HEAD` 的生产代码 diff 为空；
- Markdown 链接、格式与 `git diff --check` 通过；
- 未参与初稿的独立 reviewer 重新读取最新文件，且没有未关闭 BLOCKER。

G0.1 通过只表示文档可以指导下一阶段；不表示 Genesis、World Depth、Xuanwu、Intrusion、
Peer Population、provider 或 PC2 已实现。
