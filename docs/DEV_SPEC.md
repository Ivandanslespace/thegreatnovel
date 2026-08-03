# TheGreatNovel 开发合同

> 状态：Phase 10V1 尚未完成、尚未 accepted、尚未 frozen；当前 checkpoint 为 V1-R0。
> 当前行为基线：`pc1-frozen`。本合同只描述当前事实、权威边界、下一步安全实现和验收。
> 产品体验宪法见 [`DESIGN_VALUES.md`](DESIGN_VALUES.md)；本文不重复其长篇哲学。

## 1. Current Facts and Authority

### 1.1 权威顺序

| 问题 | 权威 | 规则 |
|---|---|---|
| frozen 行为怎样运行 | frozen code、tests、artifact | 文档不得重新解释已接受事实 |
| 产品要保护什么 | `DESIGN_VALUES.md` | 冲突时暂停并修改设计或显式 supersede |
| 当前怎样实现和验收 | 本文与 Phase Contract | 不能越过 frozen compatibility |
| 仓库入口状态 | `README.md` | 只做短索引，不复制合同 |
| Agent 执行边界 | `AGENTS.md` | 只约束执行，不替代产品合同 |
| 历史 exact 方案 | Git ref | 只作证据，不自动恢复为 active |

任何新方向必须命名为 superseding phase/milestone；不能原地改写 frozen implementation、
accepted test、tag 或旧 artifact。reviewer 共识不能替代文件、符号、测试、hash 或 Git
ref 证据。

### 1.2 当前实现事实

- 当前唯一已发布/可玩的 legacy runtime profile 仍是 `phase75_expedition_v1`，受 PC1
  compatibility 约束；它是 legacy slice，不是 Genesis 菜单或 Genesis 默认世界。
- V1-A 至 V1-D 的实验代码与 tests 已存在：Request/Proposal/Approval/Report、bounded
  Blueprint/Binding/Candidate、旧 pressure proof、static/gameplay preflight 和
  `STRUCTURAL_DIVERGENCE_V1` proof seam 均可读、可重算、可独立测试。
- Phase 10V1 尚未完成、未 accepted、未 frozen。没有 formal Generated Genesis Campaign、
  sealed generated WorldPack、生产 Runtime Expansion、真实 Prompt provider、coverage
  critic 或自然语言 action interpreter。
- V1-C/D artifact identity 绑定了旧 exclusive-upgrade pressure。该产品语义已经
  **superseded**：旧代码、schema、hash、replay、strict parsing、lineage 和 proof 技术
  可以复用来做历史实验或新 slice 的基础，但旧 pressure candidate/preflight identity
  不得作为最终 V1 产品验收证据。
- 没有把任何海洋、玄武、Habitat、载具、peers、全民投放或通用 Capability 宣称为已实现。

### 1.3 冻结边界

`pc1-frozen`、Phase 1–9 freeze tag、accepted implementation、`src/tgn/play/**`、
`tests/play/**` 及旧 artifact 保持不变。历史 tag registry 不在本文复制；需要 exact 内容时
用 `git show <ref>:<path>`。README 只保留状态、入口和链接。

## 2. Genesis Pipeline and Authority

Genesis 的目标是从 Prompt + Seed 得到一个 Campaign-specific WorldPack，而不是从预制
故事菜单选择世界：

```text
Prompt + Seed
→ Requirement Proposal
→ Coverage Approval
→ deterministic Feature Report
→ World Blueprint
→ bounded Runtime Binding
→ candidate WorldPack + candidate Initial State
→ static/gameplay/structural preflight
→ required acknowledgement
→ one atomic seal and Campaign publication
→ deterministic play + Replay + Story
```

```text
LLM proposes.
Python validates and binds.
The deterministic runtime decides.
SQLite remembers.
The narrator describes committed facts.
```

Seed 只决定生成路径；封存的 canonical WorldPack 才决定 Campaign 中什么是真的。Replay
读取保存 artifact，不重新调用 LLM。`GENERATED_GENESIS` 必须保留 Prompt/Seed lineage；
`AUTHORED_WORLD` 必须标明 authored/official/fixture/legacy，不得冒充 Genesis。

### 2.1 三类事实

- **Authoritative durable fact**：验证、绑定、提交后拥有稳定 ID，可保存、hash、进入
  WorldPack、State、Event、Replay 或 sealed expansion。
- **Candidate durable fact**：尚未接受的 Prompt 解释、Blueprint、Binding 或 expansion；
  可保存在 attempt 中，但不是 GameState、DomainEvent、Campaign 或 Narrator 事实。
- **Ephemeral texture**：只改变表达，不改变因果；不能创建事实，也不能由 prose 反推事实。

输入隐私与世界可见性是两个轴：`PUBLIC_INPUT`/`PLAYER_PRIVATE_INPUT` 与
`PUBLIC_WORLD`/`WORLD_HIDDEN`/`ACTOR_SCOPED` 分开。Projection 决定角色可观察事实；
prose 不能改变 visibility、State 或 Event。

## 3. Artifact and Feature Contracts

### 3.1 Request、Proposal、Approval、Report

Request 保存 raw Prompt、Seed、locale、约束、ID 和 policy reference；raw Prompt 是不可信
数据，不能执行命令、读取文件、索要凭据或改变权限。

Proposal 是结构化候选，不是权威。每项应能追踪 requirement ID、source、normalized intent、
requirement kind、`STRICT/DEGRADABLE/OPTIONAL` policy、typed constraints 和 candidate feature
IDs；Proposal 顶层可选 `generation_metadata_hash` 记录生成 provenance，不是每项独立字段。

Coverage Approval 是 Report 前置输入，不证明 runtime support。当前 V1-A schema 保存
`approval_schema_version`、`approval_id`、`decision`（`CONFIRMED`/`CANCELLED`）、Request/Proposal
ID 与 hash 绑定、按顺序排列的 `requirement_approvals`（`requirement_id` 与
`acceptance_policy`）以及 canonical approval hash。这些字段足够关闭当前 coverage gate；
解释、修改说明或 fixture provenance 如未来需要，必须由新的 phase、schema 和 tests 加入，
本文不假定它们已经存在。
evaluator 的纯函数合同是：

```text
evaluate(request, proposal, coverage_approval, catalog)
→ canonical FeatureRequirementReport | stable validation error
```

evaluator 不读写文件/SQLite/Campaign/GameState/EventStore/Story，不创建 Event，不负责
attempt 生命周期，不解析自然语言，不调用 LLM 或网络。产生 Report 前必须验证：

- approval 为 `CONFIRMED`，且自身通过 strict schema/canonical hash；
- request ID/hash、proposal ID/hash 与输入完全一致；
- requirement 集合、顺序/canonical identity 完全一致；
- 每项 acceptance policy 与被确认 Proposal 完全一致。

缺失、`CANCELLED`、hash 不匹配、requirement 遗漏/新增、policy 不匹配或 approval 被修改
时返回 stable validation error，不产生 Report。修改解释或 policy 必须产生新 Proposal 和
Approval，不覆盖旧 artifact。

Report item 至少保留：requirement ID、catalog layer、support status、warnings、reason、
bound feature IDs、accepted scope、lost capabilities、visible effect、acknowledgement 和
disposition。顶层至少保存：

```text
source_request_hash
source_proposal_hash
source_approval_hash
catalog_version
report_version
items[]
requirements_gate_passed
```

状态集合、计数和 UI 分组由 `items[]` 派生，不重复存储。`requirements_gate_passed=true`
必须同时满足：Approval 有效且确认；STRICT 全部 SUPPORTED；当前 V1-A 中 DEGRADABLE
若 UNSUPPORTED 也 BLOCK（当前没有 `DEGRADED` support status；未来引入真实 degraded
binding 必须由新的 phase、schema 和 tests 明确定义）；OPTIONAL unsupported 按合同 OMIT；
无 REJECTED；无未解决 warning；所有 bound feature IDs 属于当前 Catalog 并通过 layer 验证。
Approval 只证明覆盖和 policy 确认，Feature evaluator 独立判断 SUPPORTED/UNSUPPORTED/REJECTED。

### 3.2 Blueprint、Binding、Candidate

Blueprint 描述宏观世界、初始区域、事实锚点、主角、地点、Actor、派系、资源、Story
Engine、压力和远方约束；它不是脚本，也不是 runtime support。Bound Runtime Configuration
只能引用已经实现、版本化、可验证的 feature contract；禁止动态 Python、`eval`、任意 DSL、
plugin loading 和 unknown-field fallback。

Candidate bundle 保存 candidate WorldPack/Initial State、lineage hashes、compiler identity
和 gates。它可以 canonicalize/hash，但不是 authority、不是 sealed WorldPack、不是 Campaign，
不能进入存档列表。`Feature Catalog` 不预注册未来 placeholder：合理但未实现的需求返回
稳定 `NO_MATCHING_RUNTIME_CONTRACT` 或等价结果。

Sealed Genesis Bundle 只有在所有 required gates 通过后才生成；它不可变地保存 WorldPack、
Initial State、完整 lineage、proofs、acknowledgements、compiler identity 和最终 commit
record。Campaign 同时引用 semantic identity 与 sealed provenance identity，Replay 不依赖
重新生成。失败 attempt 可以保留 stable error 供修复；每次修复使用新 attempt ID，禁止
无限 repair、隐式权限升级和失败后的正式副作用。

### 3.3 Feature Catalog

Catalog 只收录已有真实运行证据的 Feature：

```text
State → legal Action → DomainEvent → Reducer → Invariant
→ Observation/Knowledge Projection → Persistence → Replay/Verify
→ tests/autoplay proof → declared non-goals
```

当前 V1-A 只有 `SUPPORTED`、`UNSUPPORTED`、`REJECTED` 三种 support status：`SUPPORTED` 必须
结合 layer 解释并使用 `BIND`；`UNSUPPORTED` 只有 OPTIONAL 才能 `OMIT`，否则 `BLOCK`（包括
当前的 DEGRADABLE）；`REJECTED` 总是 `BLOCK`；未解决 warning 阻断。`DEGRADED` 不是当前
枚举；若未来需要真实 degraded binding，必须由新的 phase、schema、tests 和产品验收合同
共同引入。helper、label、roadmap、prose、相似字段和 partial mapping 都不是 Feature 证据。

## 4. Candidate / Preflight / Publication

### 4.1 Preflight

Preflight 是 seal 前的 proof artifact，至少覆盖 schema/reference/security、Feature-local
legality/invariant/Observation、资源/路径可达、scripted gameplay、Event Replay/final hash、
`STRUCTURAL_DIVERGENCE_V1`、Approval/acknowledgement 和 frozen compatibility。任何 required
gate 失败只能创建新 attempt；不能把 candidate 当 sealed，也不能让 failure 留下正式副作用。

V1-D experimental seam 的三项 resolved gate 是：

```text
STATIC_PREFLIGHT
GAMEPLAY_PREFLIGHT
STRUCTURAL_DIVERGENCE
```

它们不授权 Runtime Catalog、publication、Campaign 或 WorldPack seal。candidate preflight
通过不等于 Phase 10V1 通过。

### 4.2 Anti-reskin 与产品 gate

正式 Genesis 最低结构门禁 `STRUCTURAL_DIVERGENCE_V1` 要求与 legacy profile 在地点/资源/
pressure/Actor goal/ownership/protagonist advantage/legal action 等至少一项真实不同；差异
必须进入运行事实和 Replay，不能只是 title、label、premise、resource name、cost 或 prose。
移除新语义后，legal action、reachable strategy、resource/opportunity cost、optimal policy
或 accepted trace 至少一项必须可测变化。

最终 Genesis 产品证明维度为：

```text
CONTROL_DEFICIT
RULE_LEGIBILITY
PROTAGONIST_LEVERAGE
ADVANTAGE_ABLATION
ACCUMULATION
COMPOUNDING
RELATIONSHIP_REVERSAL_OR_WORLD_RECOGNITION
STRATEGY_SPACE_EXPANSION
DETERMINISTIC_AUTHORITY
REPLAY_VERIFY
```

这些是证明维度，不要求建立同名 class 或通用 framework。具体证据来自 bounded Feature
Contract。旧 exclusive-upgrade pressure 的产品语义和绑定 identity 已 supersede；V1-R1
必须重新选择一个能证明上述 gate 的 recorded fixture，不能把旧 artifact 换名后继续验收。

### 4.3 唯一 authority transition

```text
candidate attempt
→ all required gates pass
→ canonical artifacts and hashes
→ no-replace atomic Campaign publication
→ authority exists
```

正式 namespace 在 commit 前不可见。WorldPack、Initial State、commit record、Campaign、
empty EventStore 和 Story bootstrap 要么全部可见，要么全部不可见；不能覆盖既有 Campaign；
crash leftover 只能是非权威 attempt；正式状态没有可加载的 PREPARED Campaign。具体路径、
平台 primitive 和恢复协议留给实现 phase，不在这里预建 workflow engine。

## 5. Replay、Persistence、Story Authority

动态事实只存在于已提交 Initial State、EventStore history 和可验证 Snapshot。所有变化遵循：

```text
Observation
→ choice/action + typed params
→ legality
→ deterministic resolution
→ DomainEvent(s)
→ pure Reducer
→ invariants
→ atomic EventStore commit
→ new Observation / Story request
```

非法行动不写 Event、不推进时间、不消耗 RNG、不改变 State。RNG、before/after hash、sequence
和 Campaign identity 属于 authority；一个 decision 可以有多个 Event。Decision 的 events、
state、RNG、record 和必要 snapshot 同一事务提交；Story 失败只留下可恢复 pending，不回滚
已提交 gameplay。

Knowledge 继续分离：

```text
World Truth ≠ Actor Knowledge ≠ Player Observation ≠ Narrator Context
```

Story 顺序固定为：

```text
authoritative Event/public result
→ structured narration brief/claims
→ prose
→ immutable committed turn
→ novel export
```

Narrator 不能提交 expansion、修改 State/Event、解析 prose 反推事实或创造关系；locale 只能
改变 labels/prose/export，不能改变 stable ID、legal action、Event sequence、state hash 或 Replay。

## 6. Constrained Runtime Expansion

Expansion 只能从已 sealed 的父 WorldPack、Campaign/history、namespace 和 deterministic child
seed 产生 candidate child：

```text
candidate child
→ schema/reference/feature validation
→ runtime binding
→ preflight
→ child hashes
→ atomic child activation + Expansion Event
```

child immutable，绑定 parent semantic hash、Campaign、namespace、seed；manifest append-only；
父事实不追溯修改；State 只有在 child artifact 和 Expansion Event 同一 authority unit 后才能
引用新 entity/location/thread；Replay 不重新问 LLM；失败没有悬空引用；Narrator 不能激活 child。
未物化的远方 NPC/城市不是“已完整模拟”的事实。

## 7. Vertical Slice、测试与 review

### 7.1 完整闭环

内部 checkpoint 可以只完成局部闭环并拥有 commit、focused tests、review，但不能被标为
完整 Feature。新增可玩行为在宣称 `complete`、`SUPPORTED`、`accepted implementation`、
`production ready`、`frozen` 或创建 freeze tag 前，必须覆盖该行为实际需要的：

```text
product requirement → Feature Contract → State → legal Action → Event → Reducer
→ Invariant → Observation/Knowledge → Persistence → Replay/Verify
→ scripted/autoplay proof → metrics/regression
```

不适用的层必须在 Phase Contract 说明理由；helper、schema、fixture、label 或局部 mapping
不能冒充 vertical slice。

### 7.2 抽象边界

```text
first concrete slice
→ second structurally different slice
→ observe repeated causality
→ smallest proven abstraction
```

禁止预建 UniversalWorldSchema、GenericGrowth/Economy/Expansion/Effect/Capability framework、
动态 plugin/registry、任意 DSL、LLM-generated Reducer、entity graph、scheduler 或 workflow
engine。Feature-local 方案优先；不要把 first slice 偶然结构写进 Engine。

### 7.3 验收与独立 review

每个 active slice 按风险选择 unit/schema/legality/reducer/invariant/hash、scenario/failure/
corruption、scripted autoplay、Replay/Verify、frozen compatibility 和 design-signal tests。
通常运行：

```text
python -m pytest tests/genesis -W error -q
python -m pytest -q
python -m compileall -q src/tgn/genesis tests/genesis
git diff --check
```

普通 coding phase 不重复 G0 三轮文档 reviewer 流程；但涉及可玩行为、authority boundary、
State/Event/Reducer、compiler、persistence、Replay/Verify、publication/atomicity、migration、
安全或 Knowledge Boundary 时，至少一次独立代码/合同 review 必须读取真实 diff、代码、测试
和 artifact。全部 BLOCKER 必须关闭；MAJOR 必须关闭或有用户明确批准的 defer；review 强度
与风险匹配。LLM judge 不能覆盖 integrity gate。

Definition of Done：scope/non-goals 明确；authority/failure/hash/replay/migration 写清；
focused/affected/full tests 按风险通过；至少一个 negative/exploit proof；无 frozen code/test/
tag/artifact 越界；独立 review 无未关闭 BLOCKER；README、implementation SHA、freeze tag 只在
结果真实发生后更新。

## 8. Active Roadmap

项目只维护这一张路线。旧 Phase 10A–10E、Historical Phase 11/12、`devour_evolution` 和
`MVP_REWRITE_SPEC` 阶段顺序均为历史，不恢复为 active。

### Phase 10G0.1 — Contract Consolidation

已完成的文档边界：两份权威文档和一个执行规则文件；不修改生产代码、tests、配置、tag 或
artifact。

### Phase 10V1 — Genesis Foundation Vertical Slice

统一验收 milestone，可以分 checkpoint、commit、review，但只有一个最终 accepted implementation
和 freeze tag；checkpoint 不创建永久 spec、accepted implementation 或独立 tag。当前 Phase
10V1 未完成、未 accepted、未 frozen。

V1-A 的 Request/Proposal/Approval/Report 合同和技术 checkpoint 继续保留并可复用；旧
V1-B/C/D 中绑定 exclusive pressure 的产品验收口径标记为 **superseded**。它们的 strict
parsing、lineage、hash、replay 和 proof 技术可复用，但旧 pressure-bound artifact/proof
不得作为最终产品证据。

当前顺序：

```text
V1-R0 — Constitutional Compression and Conflict Resolution  (本 checkpoint)
V1-R1 — Recorded Fixture and Protagonist Leverage Selection
V1-R2 — Bounded Control-Conversion Runtime Slice
V1-R3 — Blueprint / Binding / Candidate / Preflight Revalidation
V1-E  — Atomic Publication / Campaign / Replay
V1-F  — Autoplay / Compatibility / Final Review
```

R1 之前不得选定世界题材、资源、战斗、能力、成长载体、主角外挂或 pressure slice。R1 选择
后，V1 只证明一个 recorded fixture 的微型闭环：

```text
control deficit
→ legible rule
→ protagonist leverage
→ earned persistent result
→ improved later conversion
→ observable recognition or relationship reversal
→ deterministic Campaign / Replay
```

V1 不得声称完成完整长期阶层循环、任意 Prompt、生产 Lazy Expansion、World Depth L1/L2 或
通用 Feature framework。

### Phase 10V2 — Proposal Edge and Coverage Automation

V1 继续使用 recorded fixture、手工/expected Proposal、recorded/expected Approval 和
deterministic evaluator，不使用真实 LLM provider。V2 才能引入 provider-neutral edge、
recorded/fake adapter、prompt-to-proposal、independent coverage critic、真实用户确认和
bounded retry。真实网络 provider、credentials、预算、模型路由和 retention 仍需独立批准。

### 后续路线

L1/L2、Natural-Language Action Semantics、Capability、产品 pressure slices 和 PC2 只能在
前一阶段证据完成后进入新的 Phase Contract。它们不是当前实现范围。

## 9. Superseded seams、Deferred 与历史

旧 exclusive-upgrade pressure 仍可用于研究 strict parsing、hash、replay、A/B proof、lineage
和 preflight 技术；其产品语义、默认资源、永久关闭来源、Upgrade/Supply Route 二选一和
固定三步 terminal trace 均不是当前 Genesis 默认，也不得写入新的最终验收身份。

延后内容包括：通用 combat/expedition/progression/talent/capability/relationship framework、
第二个以上 profile 的通用 dispatcher、settlement/organization/economy/peer simulation、
LLM NPC autonomy、real provider、free-form action interpretation、runtime plugin、generic DSL、
unlimited repair、自动架构修改 Agent、Presentation v2、Story Context v2 和 PC2。

旧文档与旧候选不复制到当前合同。需要 exact 证据时：

```powershell
git show <ref>:<path>
```

例如：

```powershell
git show 9cdadc472cd92ce38e42767a896718fcad61f938:docs/GENESIS_FOUNDATION.md
git show pc1-frozen:README.md
```

历史内容回答“当时接受了什么”，本文回答“下一步允许怎样开发”。

## 10. Phase Contract 模板与本轮边界

每个 coding phase 的 Prompt 必须写明：phase/milestone、产品问题和 pressure slice、允许
文件与 frozen 排除、State/Action/Event/Projection scope、artifact/migration identity、
success/failure/atomicity、focused/affected/full commands、coverage/warning gates、独立
review、implementation SHA/freeze plan 和 non-goals。

本轮 V1-R0 只压缩本文档与 `DESIGN_VALUES.md`；不选择具体世界或主角杠杆，不修改 src/tests/
README/AGENTS/config/artifact/tag，不实现 V1-R1 或生产 Runtime Expansion。

## 11. 文档验收边界

- `docs/` 只保留 `DESIGN_VALUES.md` 与 `DEV_SPEC.md`；
- 本文是当前 authority、artifact、gate、publication、Replay、expansion、testing 和 roadmap
  的唯一开发合同，设计体验以 `DESIGN_VALUES.md` 为准；
- 历史 ref 仅作索引，不成为 active contract；
- 当前提交不修改代码、tests、README、AGENTS、配置、artifact、tag 或 Git history；
- 没有 formal Generated Genesis Campaign、sealed generated WorldPack、生产 Runtime Expansion、
  真实 provider，也没有开始 V1-R1；
- 文档冲突必须由新的 superseding phase 解决，不靠追加永久说明或重复清单。
