# Phase 10G0 — Genesis Foundation Architecture Contract

状态：**文档合同；Phase 10A implementation 尚未开始。**

本文件定义 TheGreatNovel Genesis 的产品目标、逻辑 artifact、authority boundary、
Prompt/Seed 语义、支持状态和后续 Phase 10A–10E 路线。它不创建任何 Python 模块、
数据库 schema、Event、Reducer、Action、WorldPack compiler、runtime profile、LLM provider
或 PC2 实现。

本文件是未来实现的约束，不是当前能力清单。当前仓库实际仍是 PC1 冻结后的 Phase 9
系统；冻结的 `phase9b-bounded-world-v1` / `phase75_expedition_v1` 只是一个受限的
first-slice runtime profile。Phase 1–9 的硬编码证据见
[`PHASE1_9_HARDCODING_INVENTORY.md`](PHASE1_9_HARDCODING_INVENTORY.md)。

---

## 1. Product definition

Genesis 的最终产品目标是：玩家用自然语言描述一个世界并提供 Seed，系统为这个
Campaign 生成、验证、编译并封存一份专属的 WorldPack。玩家不需要从开发者手写的
世界故事模块中选择。

```text
Prompt + Seed
→ Requirement Proposal
→ Feature Requirement Report
→ Campaign-specific World Blueprint / World Bible
→ bounded Runtime Binding
→ Compiled and sealed WorldPack
→ Initial Authoritative GameState
→ Preflight
→ Campaign / Story / Verify
```

两个目标输入例子：

```text
Prompt：朋克世界，全民投放系统设定，主角有黑进别人义肢的超能力
Seed：771305
```

```text
Prompt：全民投放海洋世界。只有主角的初始载具是活体玄武。其他投放者拥有普通载具。
玄武升级不消耗木材、金属等普通建造材料，只消耗会被永久扣除的专属资源“能量晶石”。
Seed：771305
```

最终产品必须允许不同 Seed 走不同的生成路径，并在世界结构、资源循环、压力、NPC、
秘密、故事发动机和主角策略优势上产生可观察的结构差异。生成后实际被接受的结果
必须保存；Campaign 运行时不能重新询问 LLM 来恢复世界；Narrator 不能通过散文创建
未编译的事实。

> **Seed determines the generation path. The sealed WorldPack determines what the world actually is.**

这不是“LLM 写一篇世界介绍”，也不是“根据主题关键词选择预制模块”。Genesis 可以
动态生成世界内容和已支持语义的组合，但不能动态生成新的 Python 运行时规则。

## 2. Non-goals and current status

本轮只完成 Stage 0–3 的文档合同。以下内容不属于本轮：

- `src/tgn/genesis/**`、`tests/genesis/**` 或任何新的 Python 模块；
- 新的 Event、Reducer、Action、数据库表、WorldPack compiler 或 runtime profile；
- 真实 LLM provider、网络调用、自动 repair agent、通用 plugin manager、generic rule DSL；
- 自然语言 action semantics、Capability Foundation、Cybernetic Intrusion、Habitat/Xuanwu、
  Peer Population、Mass Drop、runtime lazy expansion 或 PC2；
- 修改 Phase 1–9、PC1、frozen artifacts、freeze tags 或旧 bundle 的含义。

当前实现事实必须与目标合同分开：

| 当前事实 | 证据 | 对 Genesis 的含义 |
|---|---|---|
| `WorldGenesisRequest` 只有 `schema_version` 与 `prompt` | `src/tgn/worldgen/models.py:81-90` | 它不是本合同中的自包含 Genesis Request |
| `MECHANICS_PROFILE` 只有 `phase75_expedition_v1` | `src/tgn/worldgen/models.py:10-22` | 当前是 legacy bounded profile，不是通用 Feature Catalog |
| compiler 固定绑定 base、target、salvage、Mara | `src/tgn/worldgen/compiler.py:687-713` | 当前 WorldPack 是 reviewed first slice |
| initial state 固定 expedition、Day/Night、progression、build、Mara | `src/tgn/worldgen/compiler.py:716-819` | 题材内容不会自动产生新的运行语义 |
| bundle 有 request/draft/worldpack/initial-state/report hash | `src/tgn/worldgen/bundle.py:107-131` | 是 Phase 9B1 artifact contract，不等同 Genesis 全部层级 |
| verify 会按当前 compiler 重建 artifact | `src/tgn/worldgen/bundle.py:269-281` | Genesis 必须引入不可变 compiler identity 或显式 migration boundary |
| 当前没有 Requirement Proposal、Feature Report、Blueprint、Runtime Expansion 模型 | `src/tgn/**` 与 `tests/**` 审计 | 下面的 authority matrix 是未来合同，不能冒充现有实现 |

## 3. Core authority principle

TheGreatNovel 的权威顺序保持：

```text
Simulation / State
        ↓
    Consequence
        ↓
     Narrative
```

进一步明确：

```text
LLM proposes.
Python validates and binds.
The deterministic runtime decides.
SQLite remembers.
The narrator describes committed facts.
```

Genesis 不是让 LLM 成为游戏裁判。Genesis 可以提出世界、人物、地点、资源生态、隐藏
真相、故事发动机、主角背景、能力需求、扩展区域和结构化行动候选；Python 负责验证
结构、判断支持状态、选择或拒绝确定性 binding、编译配置、建立初始权威状态、验证
行动、结算后果、保存事件以及 Replay/Verify。

LLM、Generator、World Blueprint、Feature Requirement Report 和 Narrator 都不能绕过
Engine 的 State、Event、Invariant、Projection、EventStore 和 Replay 边界。

## 4. Content requirement 与 runtime semantic requirement

### 4.1 Creative / content requirements

以下内容可以由 LLM 提出或生成：

- 朋克审美、海洋文明、巨兽背部、永夜冰原；
- 主角过去的职业、人物性格、身份、公开传说；
- 地点名称与氛围、派系文化、NPC 名称和公开目标；
- 世界历史、公开叙述、候选秘密和故事线程的文本表达；
- 不承载因果的声音、颜色、气味和叙述风格。

内容表达能力不等于运行机制已经实现。例如系统能把基地描写成玄武，不等于系统
拥有 Habitat、活体载具、生长、潜水、自愈和载具所有权机制。

### 4.2 Runtime semantic requirements

以下属于需要确定性 Feature Contract 的运行语义：

- 多地点图、移动、海流、淡水消耗、载具耐久和所有权；
- 专属升级轨道、排除普通材料的成本、永久扣除资源；
- 义肢实体、网络状态、扫描、入侵、防御等级、控制效果和暴露追踪；
- 公共投放者、peers 场外行动、公共灾难、排名、市场和公共频道；
- 压力时钟、机会窗口、NPC 自主目标、知识边界、关系变化和后果。

只有存在对应确定性 Feature Contract，且完整端到端路径可验证时，才能声称机制
受到支持。不得使用以下主题开关：

```python
if "海洋" in prompt:
    enable_ocean_world()

if "玄武" in prompt:
    enable_xuanwu()

if "朋克" in prompt:
    enable_cyberpunk()
```

自然语言解释属于 LLM edge；Python 接收严格结构化 proposal 并验证，不能靠主题词
替代运行时语义。

## 5. Three fact classes

### 5.1 Authoritative durable facts

已经通过 Python 验证、编译并接受的持久事实，例如地点 ID 和连接、NPC 身份和目标、
世界隐藏真相、初始资源、能力 binding、压力时钟、成长成本、实体所有权、初始
GameState 和已提交的运行时扩展。

它们必须有稳定 ID、可 canonical serialize、被保存、必要时被 hash，不依赖重新调用
LLM，并能进入验证、运行和 Replay。

### 5.2 Candidate durable facts

LLM 提出但尚未被 Python 接受的候选事实，例如新区域、新 NPC、隐藏派系、资源点、
故事发动机或主角能力 binding。它们在 validate、bind、seal 之前：

- 不是 GameState；
- 不是 DomainEvent；
- 不是 Campaign 事实；
- Narrator 不能把它们当成已经发生；
- 失败或拒绝不能污染正式 Campaign。

候选可以保存为 generation attempt 的审计材料，但保存不等于接受。

### 5.3 Ephemeral non-authoritative texture

只用于表现、不改变运行时事实的细节，例如雨落甲板的声音、霓虹颜色、NPC 停顿方式
和不进入因果链的装饰性路人。Narrator 可以生成这类内容，但不能创造物品、能力、
人物关系、隐藏真相、Event 或确定性后果，也不能成为 Replay source。

## 6. Genesis logical artifacts

这些是逻辑层级，不要求本轮冻结最终文件名或数据库 schema。

### 6.1 Genesis Request

职责是保存玩家的原始创世意图。概念字段至少包括：

```text
schema_version
request_id
raw_prompt
genesis_seed
content_locale
explicit_constraints (optional)
generation_policy_reference (optional)
```

它是持久的创世输入记录，可以被保存和 hash，但不是运行时世界事实，不参与普通
Gameplay Event Replay，不能被解释成已支持 Feature。`raw_prompt` 是不可信数据，
不是系统指令。

### 6.2 Requirement Proposal

职责是由 LLM edge 把 Request 提取为结构化需求候选。每项需求至少概念性包含：

```text
requirement_id
requirement_kind
source_reference
normalized_intent
required_or_optional
requested_exclusivity
requested_constraints
candidate_semantic_feature_ids
notes
```

`requirement_kind` 必须区分 content、runtime mechanic、protagonist constraint、
world rule、progression rule、public-system、exclusivity、resource/economy 和
narrative/worldbuilding。

Proposal 由 LLM 提出，非权威。Python 可以验证结构，但不能证明 Proposal 完整覆盖
自然语言 Prompt；它不得创建 Campaign、写入 GameState、触发 Reducer 或直接成为
WorldPack。覆盖率检查属于未来独立 critic、人工确认或 PC2 的用户确认。

### 6.3 Feature Requirement Report

职责是 Python 根据版本化 Feature Support Catalog，对 Proposal 做确定性分类。至少
表达：

```text
required_features
supported_features
degraded_features
unsupported_features
rejected_requirements
binding_warnings
catalog_version
report_schema_version
source_request_id
source_proposal_hash
```

每项结果都必须能追溯到 `requirement_id`。Report 是当前 catalog 版本下的支持状态
记录，不是世界运行事实，不直接进入 GameState；它可以保存、hash 和审计。未来
Compiler 必须绑定同一 catalog version，catalog 变化不能静默改变已封存 Campaign。

### 6.4 World Blueprint / World Bible

职责是描述本 Campaign 的世界设计候选，而不是固定章节脚本。未来至少表达：

- 世界物理与生存规律、历史、公开常识和隐藏真相；
- 主角背景、初始位置、独特优势需求；
- 初始基地或 Habitat、地点图、NPC、派系和资源生态；
- 长短期压力、Story Engines、初始机会和初始区域；
- 未来可扩展区域约束；
- public information 与 hidden information 的分离。

Blueprint 在 Compiler 接受前仍是 candidate durable fact。只有通过验证、绑定并封存
的部分才成为 Campaign 权威世界定义。

### 6.5 Story Engine

Story Engine 不是预写剧情，而是会在玩家行动或不行动时继续运行的因果结构。至少
应表达：

```text
stable_thread_id
involved_actors
actor_goals
hidden_truth
initial_state
resources_or_stakes
pressure_clock
triggers
unattended_progression
possible_branch_conditions
consequences
closure_or_transformation_conditions
```

例如：NPC 想隐藏关键事实，另一派系正在寻找该事实，倒计时推进；玩家可以介入、
忽略或利用，玩家不介入时线程仍然发展。只有这些状态、触发和后果进入确定性
Feature Contract 后，才可称为可运行 Story Engine。

### 6.6 Bound Runtime Configuration

职责是把 Blueprint 中的需求绑定到已实现的确定性语义。它只能引用已知、版本化的
Feature ID 和 contract version；参数必须严格验证，不允许任意代码、表达式、通用
脚本、`eval` 或动态模块加载。

它不能现场生成 Python、Reducer、Event、数据库表，不能用字符串描述替代语义，不能
强行写入 unsupported requirement，也不能把缺失机制交给 Narrator。

例如将“玄武升级只消耗能量晶石”绑定为 Habitat Entity、owner、Progression Track
和 exclusive resource cost，只有在这些 Feature Contract 真实存在并贯穿 compiler、
Reducer、Projection、Campaign、Replay 后才是合法 binding。

### 6.6.1 唯一 seal commit point

Genesis attempt 在 seal 之前都是候选流程：Request、Proposal、Report、Blueprint 和
Bound Runtime Configuration 可以被校验、拒绝、修复或重新生成，但都不是 Campaign
的独立权威。唯一的 authority transition 发生在 `seal`：Python 将已接受、规范化并
通过所有 required gates 的 binding、lineage、public/hidden artifacts 和 initial-state
materialization descriptor 写入一个新的 WorldPack，先计算其 canonical hash，再由该包
materialize Initial State 并计算 state hash；两者最后随 SealRecord 原子提交，禁止互相
嵌入未完成的 hash。

Seal 之后：

- WorldPack 是不可变的基础 artifact；Blueprint 和 Bound Runtime Configuration 只作为
  lineage/verify 输入保存，不再是可变的独立运行时 authority；
- Initial GameState 只能由该 sealed WorldPack 构建；Campaign、EventStore 和 Story 才
  能从这组已封存 artifact 原子创建；
- 新的世界扩展只能作为绑定父 WorldPack hash 的 append-only child artifact，不能修改
  父 WorldPack 或重写其 hash；
- 任何 Genesis 构建、binding 或 seal transaction 失败都发生在正式 Campaign 发布之前，
  不能留下可见的正式 Campaign、Event、GameState 或 Story；Campaign 运行期的 EventStore、
  Expansion 或 Story 事务失败按各自的 fail-closed/atomic 规则处理。

### 6.7 Compiled Campaign WorldPack

WorldPack 保存本 Campaign 被接受并编译后的世界定义，是 Campaign 的事实来源。未来
基础 WorldPack 必须是 immutable sealed artifact；append-only 只适用于未来独立定义的
Runtime Expansion child artifact，不能表示修改基础包。WorldPack 包含：

- canonical serialization、stable IDs、schema version；
- compiler identity、feature contract versions；
- Prompt/Seed lineage 和 accepted Blueprint binding；
- public/hidden separation、hashes、initial-state materialization descriptor（不包含
  Initial State hash，避免循环哈希）；
- verify path，且 Replay 不需要调用 LLM。

WorldPack 不是 Seed、原始 Prompt、Generator 聊天记录、模型内部推理、Narrator 文本或
未来重新生成的临时结果。旧 `phase9b-bounded-world-v1` bundle 必须继续可验证；Genesis
必须使用新的 compiler identity 或显式 superseding contract，不得静默改写旧 bundle。

Hash 依赖必须是单向的，且不是字符串拼接。两种 canonical preimage 的 exact envelope
为：

```text
{
  "artifact_type": "compiled_worldpack",
  "schema_version": 1,
  "compiler_identity": {
    "compiler_id": "stable-id",
    "compiler_schema_version": 1,
    "compiler_implementation_digest": "lowercase-hex64"
  },
  "lineage": {
    "request_hash": "lowercase-hex64",
    "proposal_hash": "lowercase-hex64",
    "report_hash": "lowercase-hex64",
    "blueprint_hash": "lowercase-hex64",
    "binding_hash": "lowercase-hex64",
    "generation_metadata_hash": "lowercase-hex64"
  },
  "feature_bindings": [],
  "public_world": {},
  "hidden_world": {},
  "initial_state_materialization_descriptor": {
    "descriptor_schema_version": 1,
    "materializer_id": "stable-id",
    "materializer_schema_version": 1,
    "input_digest": "lowercase-hex64",
    "input_references": []
  }
}
```

```text
{
  "artifact_type": "initial_authoritative_game_state",
  "schema_version": 1,
  "worldpack_hash": "lowercase-hex64",
  "state_schema_version": 1,
  "state_payload": {}
}
```

`WorldPackHash` 是第一个完整对象按 canonical JSON 规则编码后的 SHA-256；
`InitialStateHash` 是第二个完整对象按同一规则编码后的 SHA-256。两个 envelope 的
顶层字段都不允许 unknown field，`state_payload` 和 world content 的内部 schema 由
对应 versioned contract 定义，但不能放入另一个 artifact 的 hash。WorldPack 不能嵌入
`InitialStateHash`，Initial State 也不能反过来重写 WorldPack；`SealRecord` 只保存两者
已经计算完成的 hash。

### 6.8 Initial Authoritative GameState

由已验证 WorldPack 构建可运行的初始状态。它必须通过核心和 Feature-local invariants、
与 WorldPack hash 绑定、不含 unsupported mechanism、不从 Narrator prose 恢复、不在
Campaign 创建后偷偷补丁，并能成为 Event Replay 起点。

### 6.9 Runtime Expansion

远方区域未来可以按需扩展，但只能沿以下边界：

```text
sealed WorldPack
+ existing World Bible
+ campaign history
+ stable expansion namespace
+ region/entity ID
+ deterministic child seed
→ candidate expansion
→ validation
→ binding
→ sealing
```

未被玩家看见不等于可以随意改写。一旦扩展被接受，必须保存实际结果、分配稳定 ID、
绑定父 WorldPack 和 Campaign、不能只靠以后重问 LLM 恢复、不能与既有事实矛盾，且
不能由 Narrator 直接提交。Runtime Expansion 只在总架构中定义边界，不是 Phase 10A
实现内容。

### 6.10 Narration Artifact

Narration 只描述已提交事实，可以组织语言、表达感官和公开情绪、改变风格、添加不承载
因果的氛围。它不能创造资源、NPC、秘密、能力、关系变化、Event，不能改写 GameState、
扩展权威世界结构，也不能让 unsupported feature 看起来已经运行。

## 7. Feature Catalog 是语义目录，不是题材菜单

Feature Catalog 描述运行语义，例如：

```text
LocationGraph       Travel              ResourceInventory
ProgressionTrack    Habitat             EntityOwnership
PressureClock       OpportunityWindow  NPCAgenda
Relationship         KnowledgeBoundary  PeerPopulation
PublicEvent          TargetableDevice   NetworkAccess
Investigation        Conversation       Combat
Crafting
```

它不应列出 `ocean`、`cyberpunk`、`ice_train`、`giant_beast` 或 `xuanwu` 作为机制开关。
本轮不得把概念列表实现为 registry、plugin manager、dynamic loader、effect DSL 或
universal handler interface。

一个新 Feature 至少需要明确状态、合法行动、验证、Event、Reducer 路径、不变量、
Projection、测试和 Replay；单凭 Feature ID、名称相似、Narrator 能描述或某个 helper
存在，不能让机制自动成立。

## 8. Authority Matrix

下表是目标合同。它描述未来 Genesis artifact 的权威边界，不声称当前仓库已有所有
模型或持久化路径。

| layer | created_by | authoritative_for | may_contain_hidden_data | Python_validation_required | persisted | hashed | enters_campaign | participates_in_gameplay_replay | can_be_regenerated | failure_effect |
|---|---|---|---|---|---|---|---|---|---|---|
| Genesis Request | player plus client | 原始创世意图和 lineage | raw prompt 可含用户私有意图，但不是系统秘密 | yes | yes | yes | 仅作为 lineage，不直接成为 State | no | 新 attempt 可以重新提交；原记录不可替换 | generation attempt 失败，不创建 Campaign |
| Requirement Proposal | LLM edge | 结构化需求候选 | yes，但在接受前不能公开为事实 | yes，限于 schema 和安全边界 | 可保存 attempt | yes | no | no | seal 前可重生成；已接受结果不被替换 | 丢弃或保留失败 attempt，不污染正式 Campaign |
| Feature Requirement Report | deterministic Python evaluator | catalog 版本下的支持状态 | no，除非引用受控 lineage | yes | yes | yes | no，作为编译门禁输入 | no | 可在相同输入/catalog 下重算；历史 report 仍保留 | required unsupported/rejected 阻止编译 |
| World Blueprint / World Bible | LLM edge plus client | 候选世界设计与故事结构 | yes，public/hidden 必须分离 | yes | yes | yes | 只通过 accepted binding 间接进入 | no | seal 前可重生成；Campaign 后不得替换 | blueprint 失败不创建 Campaign |
| Bound Runtime Configuration | deterministic compiler | seal 前的 Blueprint-to-feature binding 候选；不是独立运行时 authority | yes，按 public/hidden policy | yes，feature-local contract 必须通过 | 作为 WorldPack lineage 保存 | yes，进入 WorldPack hash | 只以嵌入 WorldPack 的形式进入 | 通过 WorldPack 间接参与 | seal 前同一 attempt 可重编译；seal 后不能替换 | binding 失败阻止 WorldPack |
| Compiled Campaign WorldPack | compiler | Campaign 的静态世界事实 | yes，隐藏事实必须隔离 | yes | yes，immutable base artifact | yes | yes | yes，是 Replay 的世界输入 | 对同一 Campaign 不可重新生成替换 | 不发布 Campaign；临时 artifact 可清理 |
| Initial Authoritative GameState | Engine from WorldPack | Campaign 的初始运行状态 | yes | yes，core and feature invariants | yes | yes，绑定 WorldPack | yes | yes，是 Event Replay 起点 | 只能由已封存包确定性构建并验证；不能靠 prose 恢复 | 不创建正式 Campaign |
| Runtime Expansion Proposal | LLM edge plus deterministic context | 候选区域/实体扩展 | yes | yes | 可保存 attempt | yes | no | no | seal 前可重生成；child seed 只约束路径 | 只丢弃 expansion attempt，不改变父 Campaign |
| Sealed Runtime Expansion | deterministic compiler | 已接受的新增区域/实体/线程事实 | yes | yes | yes，append-only | yes | yes | yes，通过 expansion Event 和状态进入 | 对同一 Campaign 不可用新生成替换 | 事务失败时无部分事实、无部分 Event |
| DomainEvent | deterministic runtime | 已提交的单个游戏后果和 transition payload | 可以含 engine-private state | yes，legality/reducer/invariants | yes | yes，event record 与 before/after state hash 应绑定 | yes | yes，是 Gameplay Replay 的核心 | 不可用 LLM 重生成；只能从记录读取 | 非法或持久化失败不提交事实 |
| EventStore history | deterministic persistence layer | DomainEvent 的有序持久化记录和查询边界，不独立创造事实 | 可保存 engine-private state | yes，事务与完整性验证 | yes | yes，记录 hash/transition hash | yes | yes，作为 Replay 输入容器 | 不重新生成；损坏则 fail closed | 事务失败不产生部分已提交历史 |
| Snapshot | EventStore derived optimization | 某一 Event seq 的可验证状态快照，不取代 Event authority | yes | yes，canonical state/invariant/hash 校验 | yes | yes，每条 snapshot 独立 hash | yes，作为优化读取 | no，Replay 可从 Event history 重建 | 可重建但不能覆盖原始历史 | 单条损坏不应静默修复，验证失败 |
| Generation metadata | generator/client | 审计信息，如 model/provider/template/version | 可含 provider metadata，不是世界事实 | yes，格式和隐私校验 | yes，按 policy | yes | 仅作为 lineage | no | 可以重新收集新的 metadata，但不能替代原记录 | metadata 失败不应改变已封存 WorldPack；缺少必需 lineage 则阻止 seal |
| Narration Request | Story reconstruction / Engine | 从 Campaign public projection 派生的叙事输入 | no，只有允许公开的 projection | yes，request identity/claims boundary | yes，Story sidecar | yes | 仅进入 Story sidecar | no | 可由同一 Campaign 重新构建 | 重建失败不改变 Engine，保留 pending/error |
| Committed Turn Artifact | narrator plus Story service | 已提交 narration claims/prose 的表达结果 | no，不能含未公开事实 | yes，claims/prose validation | yes | yes | 仅以 derived artifact 进入 Story | no | 可重生成 prose，但不能重写 committed claims/facts | 失败不提交 turn，pending 保留 |
| Narration Artifact | narrator / external client | 已提交事实的表达和叙事风格 | no，只有允许公开的 projection | yes，claims/prose boundary | yes，sidecar | yes | 仅以 derived artifact 进入 Story，不进入 GameState | no，不能作为 Gameplay Replay source | 可重新表达风格，但不可改变 claims/facts | narration 失败保留 pending，不回滚或改变 Engine |
| novel.md | Story exporter | committed turns 的派生文本导出 | no | yes，export integrity | yes | yes，derived export hash | 仅作为导出结果 | no | 可重新导出；不能反向成为事实 | 导出失败不改变 Campaign/Story authority |

核心结论：`WorldPack` 和 `Initial GameState` 才是 Campaign 创建后的世界/状态权威；
`DomainEvent` 是运行时后果权威；`Requirement Proposal`、`Feature Report` 和
`Blueprint` 在封存前都不是事实；Narration 永远是 derived presentation。

## 9. Hash / Replay Matrix

| artifact | canonical/hash contract | Gameplay Replay role | regeneration rule |
|---|---|---|---|
| Genesis Request | canonical request hash，包含 schema、request ID、raw prompt、seed、locale 和约束 | 不参与普通事件 Replay，仅作为 lineage | 新 attempt 可重新生成，但历史 Request 不可被替换 |
| Requirement Proposal | proposal schema hash，绑定 request hash 和生成 metadata | 不参与 Gameplay Replay | seal 前可重新提出；已接受 binding 不随新 Proposal 改变 |
| Feature Requirement Report | report hash，绑定 proposal hash、request ID、catalog/report schema version | 编译门禁记录，不是状态输入 | 同一 catalog 可重算；catalog 变化必须新版本，不能静默重释旧 report |
| World Blueprint | blueprint hash，分离 public/hidden 内容并追踪 requirement IDs | 不直接 Replay | seal 前可重生成；已封存部分由 WorldPack 固定 |
| Bound Runtime Configuration | canonical binding hash，包含 Feature ID 和 contract version | 通过 WorldPack 和 initial state 间接参与 | 不允许任意代码或隐式默认值；新 binding 产生新 WorldPack |
| Compiled WorldPack | canonical WorldPack hash，含 compiler identity、feature versions、lineage、hidden/public separation 和不含 State hash 的 initial-state materialization descriptor | Campaign Replay 必须读取保存的包 | 同一 Campaign 不重新生成替换；verify 使用不可变 compiler identity 或显式 migration |
| Initial GameState | state hash，绑定 WorldPack hash 和 schema | Replay 的起点 | 只能从 sealed WorldPack 确定性 materialize；不能从 narration 恢复 |
| Runtime Expansion Proposal | attempt hash，绑定 parent WorldPack、Campaign、namespace 和 child seed | 不进入 Gameplay Replay | seal 前可重试；失败 attempt 永不进入 Replay |
| Sealed Runtime Expansion | child artifact hash，绑定 parent WorldPack hash、Campaign、namespace、entity ID、child seed 和 Expansion Event | 只有 seal 后的 child artifact 与 Event/State transition 进入 Replay | seal 后只读 append-only；父 WorldPack hash 永远稳定 |
| DomainEvent | canonical event record hash 加 before/after state hash | Reducer 逐事件重放和验证 | 不重新调用 Generator；event identity/provenance 以保存记录为准 |
| Snapshot | 每条 snapshot 的 state JSON、hash、seq 与 Event transition 绑定 | 优化读取；Event history 仍是验证基线 | 可重建但不能覆盖原始历史；每条都应独立校验 |
| EventStore history | canonical ordered-history hash，绑定 campaign、event sequence、transaction boundary 和 transition hashes | Replay 的持久化输入容器；事实仍由 DomainEvent 与状态验证决定 | 不重新生成；损坏或序列断裂必须 fail closed |
| Generation metadata | canonical metadata hash，绑定 request/proposal/attempt，记录 provider/model/template/version 等审计字段 | 不参与 Gameplay Replay，仅作为 lineage/audit | 可重新收集新的 metadata，但不能替代原记录或改变已封存事实 |
| Narration Request | derived request hash，claims 绑定公开 observation 和 Story context | 不参与 Gameplay Replay；可由同一 Campaign 重建 | 可以重建，但不能改变 State、Event、WorldPack 或公开 claims |
| Committed Turn Artifact | committed claims/prose hash，绑定已提交 Event/observation 和 locale | 不参与 Gameplay Replay；是 Story sidecar 的派生结果 | 可重新表达 prose，但不能重写 committed claims/facts |
| Narration Artifact | derived narration hash，绑定 Committed Turn Artifact 的 claims | 不参与 Gameplay Replay；只能作为 presentation | 可重新生成风格文本，但不能改变 claims/facts |
| novel.md | 从 committed turns 派生的导出 hash | 不是 Replay source | 可重新导出；不能反向成为事实 |

当前 Phase 9B1 的 `verify_bundle()` 会重编译并比较 artifact；这只是冻结 v1 的验证
路径，不是新 Genesis 的长期 authority。Genesis 必须让 Replay 与已封存 WorldPack 解耦
于未来 generator/compiler 变化，并通过 compiler identity 或显式 migration 来验证。

## 10. Prompt 与 Seed semantics

### 10.1 Seed 的含义

`genesis_seed` 是生成路径的输入：它可以影响候选排序、确定性 child seed、内容选择
和可验证的生成过程。它不是 WorldPack，也不是对 LLM API 跨版本行为的字节级保证。

以下变化都可能破坏采样 API 的 byte equality：模型版本、provider、system prompt、
generation template、tool、推理实现和服务端更新。因此 seed 只能承诺“同一明确生成
合同/实现/输入下可重复路径”，不能承诺“任何未来环境重新询问 LLM 都得到同一结果”。

### 10.2 Sealed artifact 的含义

实际被 Python 接受并保存的 WorldPack、初始状态、扩展 artifact 和 Gameplay Event 才
是历史事实。Generation metadata 用于审计，不是运行时权威。Replay 不使用 seed 重新
生成 WorldPack；它读取保存的 artifact。

### 10.3 Prompt injection boundary

`raw_prompt` 以及从它提取的文本都是不可信数据。Prompt 不能：

- 修改系统规则、Feature Catalog、冻结合同或 Python 权限；
- 要求读取文件、执行命令、访问凭据、调用网络或加载模块；
- 绕过 SUPPORTED/DEGRADED/UNSUPPORTED/REJECTED 分类；
- 要求 Narrator、Generator 或 Compiler 获得隐藏权限；
- 把 prose、字符串、表达式或代码当作 runtime rule。

安全检查是 schema/contract 层的确定性门禁，不是依赖 Narrator 自己“理解” Prompt。

## 11. Feature Requirement status policy

`Feature Requirement Report` 的状态必须使用以下严格语义：

| status | meaning | may_compile | may_appear_as_runtime_fact | may_appear_in_narration | user_acknowledgement | blocking_behavior |
|---|---|---|---|---|---|---|
| SUPPORTED | 已有确定性语义，关键意思不丢失，完整路径可验证 | yes | yes | 只能描述已提交事实 | 通常不需要；产品 UI 可展示 | 不阻止，但仍需正常 schema/invariant 门禁 |
| DEGRADED | 只能用明确、更窄的真实语义运行，必须记录丢失能力和玩家可观察差异 | yes，需满足降级 contract | yes，但只能是实际的窄语义 | 只能描述窄语义，不能暗示原完整需求 | yes，若改变核心玩法或可观察承诺 | required requirement 未获用户确认时阻止正式编译 |
| UNSUPPORTED | 需求合理，但当前没有对应确定性运行语义 | no，除非删除要求或接受已定义降级 | no | no；不得让 Narrator 伪装存在 | 不是简单确认即可；必须删除、改写或选择明确降级 | required requirement 阻止 Campaign WorldPack |
| REJECTED | 需求违反 schema、安全、合同或可验证性边界，例如要求执行代码或修改规则 | no | no | no | 不可通过用户确认绕过 | 永久阻止该 Proposal/attempt |
| Binding Warning | 不阻止分析，但存在歧义、冲突、exclusivity 未定义或内容/机制混淆 | no，直到 warning 解决 | 只有在正式 binding 后 | 只能描述 accepted result | 必须在 seal 前解决；需要时按 DEGRADED 重新确认 | `overall_status=BINDING_WARNING` 且 `seal_allowed=false`，不能被静默忽略 |

`SUPPORTED` 绝不等于“名称相似”“有一个无关数值字段”“Narrator 会写”或“未来路线
图上计划实现”。`DEGRADED` 必须同时记录原始需求、实际 binding、丢失能力、玩家观察
到的结果、核心玩法变化和是否需要用户确认。

`DEGRADED` 的确认时点已经固定为 **WorldPack seal 之前**：Report 可以先标出
`user_acknowledgement_required=true`，但在确认记录绑定 `report_hash`、accepted scope、
lost capabilities 和 user decision 之前，不得生成 seal record、Initial State 或正式
Campaign。确认只允许接受文档中已经定义的窄语义，不能把 `UNSUPPORTED` 变成
`SUPPORTED`，也不能由 Narrator 或重新生成的 prose 代替。

## 12. World Depth 与 anti-reskin criteria

Genesis 不能只完成换标题、换资源名、换基地名和换 NPC 名。结构差异至少应可从
以下方面观察：

- 地点拓扑和移动选择不同；
- 核心资源循环与稀缺性不同；
- 生存压力、压力时钟和机会窗口不同；
- 主角独特能力改变策略空间，而不是只改数值；
- NPC/派系目标、知识边界和关系后果不同；
- hidden truth 与 Story Engine 的分支互动不同；
- 玩家不行动时世界继续发展的路径不同；
- 机会可能错过并产生永久变化。

未来第一个 World Depth Slice 的正式 gate 是：至少 3 个相连地点、2 个有独立目标的
NPC、2 个同时推进的压力/机会时钟、1 个可错过且不可逆的机会、玩家不在场时可确定性
推进的 NPC/世界状态，以及 20 个有意义回合内不进入只有 WAIT 的死状态。还必须用主角
能力启用/移除的 A/B 比较证明策略空间、合法行动或资源/机会代价发生结构变化，而不是
只增加一个数值。这些不是 Phase 10A 实现要求，而是 Phase 10E 对“启用 World Depth
声明”的 hard gate；不能满足时只能撤销该声明，或以 `DEGRADED` 加明确 acknowledgement
封存，不能由 Narrator 补齐。

## 13. Anti-overengineering rules

以下路线与本合同冲突：

```text
UniversalRuleEngine
UniversalWorldSchema
GenericEffectSystem
DynamicHandlerRegistry
PluginManager
Runtime Python loading
LLM-generated Python
Arbitrary expression evaluator
General workflow engine
General entity-component-system migration
Generic command/event bus
Mega capability graph
Universal story DSL
```

正确方向是先建立清晰的生成边界，再按真实产品需求增加有限 Feature Contract，
用多个结构不同的世界压力测试这些合同。不要为了未来可能的一百种机制，预先建立
一百种抽象；也不要把所有 Phase 1–9 重写成 Genesis 前置条件。

## 14. Compatibility with Phase 1–9 and PC1

### 14.1 保留的 Kernel

以下能力是可信基础，不因 Genesis 方向而重写：GameState metadata shell、DomainEvent
provenance、canonical JSON/hash、EventStore、Snapshot、Replay、Verify、RecordedDecision、
Campaign publication/sealing、Story persistence、commit-before-print、novel export 和
PC1 frozen boundary。

### 14.2 Legacy bounded runtime profile

以下内容是当前第一条经过验证的确定性垂直切片，不是错误历史，也不是通用世界规则：

- `phase75_expedition_v1`；
- fixed base/target、DROP/SEARCH/EXTRACT、fixed costs；
- `target_searched`、Day/Night cycle、fixed resource/builds；
- Mara、单一 actor/fact、当前 Projection action schema；
- Core reducer/invariants 与 Autoplay/Session/Campaign/Story 对 expedition 的直接依赖。

它们只能通过新的 superseding contract 扩展或替代；本轮不修改这些代码和测试。

### 14.3 Superseding boundaries

未来可能需要：versioned Runtime Profile Boundary、feature-local reducer/invariant
boundary、WorldGen v2、Projection/Player Presentation v2、Story Context v2、Autoplay
adapter v2、Session/Campaign/Story gameplay adapter、Natural-language Action Proposal
boundary 和 PC2。它们是未来契约接缝，不是本轮要预建的万能框架。

## 15. Phase 10A–10E roadmap

### Phase 10A — Genesis Request and Feature Requirement Report

目标：建立最小创世输入、严格 Proposal schema、有限语义 Catalog、确定性 evaluator、
Report、canonical serialization、stable errors 和两个结构化验收 fixture。无 provider、
网络、关键词解析、Campaign、GameState、Event、Reducer、Blueprint、WorldPack compiler、
runtime profile、Capability、automatic repair 或 PC2。

#### 15.1 Phase 10A typed contract（文档冻结候选）

Phase 10A 的输入是结构化对象，不是让 evaluator 自己解析自然语言。所有对象都使用
UTF-8 canonical JSON：object key 按 Unicode code point 排序、无额外空白、数组保持合同
顺序、整数不写成浮点、字符串不允许 NUL；`sha256(canonical_json(object))` 是该对象的
hash。未声明字段、错误类型、越界长度和重复 stable ID 都是拒绝，不是静默丢弃。

`GenesisRequest` 的 exact envelope 为：

| field | type and limit | contract |
|---|---|---|
| `schema_version` | integer | exactly `1` |
| `request_id` | string, 3–64 chars | `^[a-z][a-z0-9_]{2,63}$`，由调用方稳定分配 |
| `raw_prompt` | UTF-8 string, 1–16,000 chars | trim 后非空；不得含 NUL；只是未可信意图，不是 system instruction |
| `genesis_seed` | UTF-8 string, 1–256 chars | trim 后非空；不得含 NUL；作为 generation path input |
| `content_locale` | string, 2–35 chars | BCP47-like `^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8}){0,3}$` |
| `explicit_constraints` | optional array, max 32 | item 只能是下列 typed constraint；缺省为 `[]` |
| `generation_policy_reference` | optional stable-ID string, max 128 | 只引用已批准 policy；不得内嵌 prompt、代码、路径、命令或权限 |

`explicit_constraints` 的 item 只允许 `{constraint_id, constraint_kind, value, required}`。
`constraint_id` 使用同一 stable-ID 规则；`constraint_kind` 为
`equals`、`one_of`、`excludes`、`requires`、`ownership`、`resource_cost`、`limit` 之一；
`value` 只能是有限长度 string、integer、boolean 或最多 8 个这样的 scalar；`required`
必须是 boolean。任何 executable string、表达式、文件路径、URL、模块名或命令字段均拒绝。

`RequirementProposal` 的 exact envelope 为
`{proposal_schema_version, source_request_id, source_request_hash, requirements, generation_metadata_hash?}`。
`proposal_schema_version` 必须为 `1`；`source_request_id` 必须等于 Request；
`source_request_hash` 必须是小写 64 位 hex；`requirements` 为 1–128 项，不能有重复
`requirement_id`。每个 requirement item 只允许以下字段：

| field | type and limit | allowed values / meaning |
|---|---|---|
| `requirement_id` | stable-ID string, 3–64 chars | proposal 内唯一 |
| `requirement_kind` | enum | `content` / `runtime_mechanic` / `protagonist_constraint` / `world_rule` / `progression_rule` / `public_system` / `exclusivity` / `resource_economy` / `narrative_worldbuilding` |
| `source_reference` | string, 1–256 chars | 指向 prompt/用户约束的可审计引用；不是代码或 JSONPath 执行器 |
| `normalized_intent` | string, 1–4,000 chars | 结构化语义摘要；不拥有 runtime authority |
| `required_or_optional` | enum | `required` / `optional` |
| `requested_exclusivity` | enum | `none` / `player_only` / `entity_only` / `global_exclusive` / `unspecified` |
| `requested_constraints` | array, max 16 | 使用上面的 typed constraint item |
| `candidate_semantic_feature_ids` | array, max 16 | stable Feature ID；不得含主题分支、代码、表达式或 plugin 名 |
| `notes` | optional string, max 2,000 chars | 仅审计注释；不可引入新字段语义 |

`generation_metadata_hash`（若存在）必须是小写 64 位 hex，metadata 作为单独的审计
artifact 处理；model/provider/template 信息不能改变 proposal 的 authority。一个 Report
item 对应且只对应一个 `requirement_id`，并且按 Proposal 顺序输出。Report exact
envelope 为：

```text
{
  report_schema_version: 1,
  source_request_id,
  source_request_hash,
  source_proposal_hash,
  catalog_version: "genesis-feature-catalog-v1",
  overall_status: SUPPORTED | DEGRADED | UNSUPPORTED | REJECTED | BINDING_WARNING,
  seal_allowed: boolean,
  omitted_optional_requirement_ids: [],
  items: [
    {
      requirement_id,
      status: SUPPORTED | DEGRADED | UNSUPPORTED | REJECTED | BINDING_WARNING,
      reason_code,
      bound_feature_ids: [],
      degraded_binding: null or {feature_id, accepted_scope, acknowledgement_reason},
      lost_capabilities: [],
      player_visible_effect,
      user_acknowledgement_required
    }
  ]
}
```

Report 的 exact field contract 为：

| field | required/type/range | exact rule |
|---|---|---|
| `report_schema_version` | required integer | exactly `1` |
| `source_request_id` | required stable-ID string | 必须等于 Request 的 `request_id` |
| `source_request_hash` | required string, exactly 64 chars | lowercase hex；必须匹配 canonical Request |
| `source_proposal_hash` | required string, exactly 64 chars | lowercase hex；必须匹配 canonical Proposal |
| `catalog_version` | required string | exactly `genesis-feature-catalog-v1` |
| `overall_status` | required enum | `SUPPORTED` / `DEGRADED` / `UNSUPPORTED` / `REJECTED` / `BINDING_WARNING` |
| `seal_allowed` | required boolean | 只有没有 required unresolved status 时才可为 `true` |
| `omitted_optional_requirement_ids` | required array, 0–128 unique stable IDs | 只能列 source Proposal 中 `optional` 且 Report item 为 `UNSUPPORTED` 的 requirement；按 ID 字典序 canonicalize |
| `items` | required array, 1–128 items | 与 Proposal requirements 一一对应、顺序相同、ID 不重复 |

每个 item 必须且只能包含以下字段：

| field | required/type/range | exact rule |
|---|---|---|
| `requirement_id` | required stable-ID string | 必须存在于 source Proposal，不能新增或丢失 |
| `status` | required enum | `SUPPORTED` / `DEGRADED` / `UNSUPPORTED` / `REJECTED` / `BINDING_WARNING` |
| `reason_code` | required enum string, 3–64 chars | 只能是 `content_only`、`legacy_exact_match`、`legacy_exact_match_failed`、`catalog_feature_supported`、`degraded_scope`、`no_runtime_contract`、`feature_id_malformed`、`feature_id_unknown`、`kind_mismatch`、`multiple_candidate_conflict`、`required_feature_missing`、`requirement_conflict`、`prompt_injection` 或 `schema_rejected` |
| `bound_feature_ids` | required array, 0–16 unique Feature IDs | 每项必须是 Catalog member；unsupported/rejected item 必须为 `[]` |
| `degraded_binding` | required `null` or exact object | 非 `DEGRADED` 必须为 `null`；对象只能有 `feature_id`、`accepted_scope`（1–256 chars）和 `acknowledgement_reason`（1–512 chars） |
| `lost_capabilities` | required array, 0–16 unique strings | 每项为 `[a-z][a-z0-9_]{2,63}`；`SUPPORTED` 必须为 `[]` |
| `player_visible_effect` | required UTF-8 string, 1–1,000 chars | 不含 NUL；只描述实际 accepted/degraded result |
| `user_acknowledgement_required` | required boolean | 只有改变核心玩法或玩家可观察承诺的 `DEGRADED` 才可为 `true` |

所有上述 object 都拒绝 unknown field；`items` 不能省略空数组来代替报告，Proposal 与
Report 的 hash、ID、catalog version 和数组顺序必须完全绑定。`omitted_optional_requirement_ids`
是唯一允许的“删除/忽略 optional unsupported”审计表示；item 仍保留在 Report 中，
但只要列入该数组就不参与 effective binding aggregate。未列入数组的 optional
`UNSUPPORTED` 仍阻断 `seal_allowed`。`Feature ID` 的 grammar
为 `^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,3}$`，长度 3–96；stable ID 仍使用
`^[a-z][a-z0-9_]{2,63}$`。`seal_allowed=false` 的唯一条件集合是：存在 `REJECTED`、
required `UNSUPPORTED`、required 未确认的 `DEGRADED` 或任意 unresolved `BINDING_WARNING`；
optional `UNSUPPORTED` 只能被明确删除/忽略，不能进入 Bound Runtime Configuration；
`overall_status` 的优先级聚合只对未列入 omission array 的 items 生效，Report 仍保留
被省略 item 供 lineage/review。

Report item 还必须满足：`reason_code` 为版本化小写错误/结果 code（例如
`content_only`、`no_runtime_contract`）；
`bound_feature_ids` 每项都在该 Catalog；`degraded_binding` 在非 `DEGRADED` 时必须为
`null`；`lost_capabilities` 最多 16 个稳定描述；`player_visible_effect` 为有限长度
可公开说明；`user_acknowledgement_required` 为 boolean。一个 requirement 不得同时有
两个 status。聚合状态的优先级为 `REJECTED > UNSUPPORTED > DEGRADED > BINDING_WARNING > SUPPORTED`；
`BINDING_WARNING` 是 item-level unresolved warning，不能被当作 `SUPPORTED`。只要任一
warning 未解决，`overall_status` 必须为 `BINDING_WARNING`（除非同时存在优先级更高的
`DEGRADED`、`UNSUPPORTED` 或 `REJECTED`），evaluator 仍返回 Report，但固定返回
`seal_allowed=false` 的 compiler-gate 结果；不能静默继续 seal。warning 解决后必须
重新计算 Report hash，不能修改旧 Report。

#### 15.1.1 Feature Catalog v1 与 evaluator mapping

Catalog 是有限的 semantic member 集合，不是自由注册表。下面的成员是 Phase 10A
合同中唯一可以被 fixture 引用的 v1 名称；“UNSUPPORTED” 仍然是有意的、可审计的
目录结果，不代表 Narrator 可以伪装实现。

| feature_id | contract version | semantic scope | v1 support state | evidence / evaluator mapping |
|---|---|---|---|---|
| `content.public_labels.v1` | 1 | title、premise、public labels 和 locale 的内容表达 | `SUPPORTED`（content-only） | `src/tgn/worldgen/models.py:12-34`；只匹配 `content`，不提供 runtime |
| `legacy.profile.phase75_expedition_v1` | 1 | 已冻结 bounded expedition 的完整 profile | `SUPPORTED`（仅 exact legacy binding） | `src/tgn/worldgen/models.py:10-22`、`compiler.py:687-819`；不接受任意新 world rule |
| `kernel.event_replay.v1` | 1 | EventStore、Replay、Verify 的既有底座 | `SUPPORTED`（kernel-only） | `src/tgn/core/**`、`src/tgn/storage/**`；不能单独满足题材机制 |
| `runtime.location_graph.v1` | 1 | 多地点拓扑、Travel 和连通性 | `UNSUPPORTED` | 当前没有 Genesis compiler/reducer/projection binding |
| `runtime.peer_population.v1` | 1 | peers、目标、离场推进与竞争 | `UNSUPPORTED` | 当前没有 population state、autonomous Event 和 replay contract |
| `runtime.protagonist_capability.v1` | 1 | 主角专属能力、合法 Action、限制与策略差异 | `UNSUPPORTED` | 现有 build choice 不是 generic protagonist capability |
| `runtime.entity_ownership.v1` | 1 | entity owner、可见性与所有权后果 | `UNSUPPORTED` | 当前 WorldPack 没有任意 entity/ownership binding |
| `runtime.network_access.v1` | 1 | 网络连接、访问边界和知识权限 | `UNSUPPORTED` | 当前没有 Network state 或 Event contract |
| `runtime.intrusion.v1` | 1 | scan、intrusion、defense、control 和 trace | `UNSUPPORTED` | 当前没有对应 Action/Reducer/Invariant/Projection 全链 |
| `runtime.habitat.v1` | 1 | 可成长 Habitat/base/vehicle 的实体轨道 | `UNSUPPORTED` | 当前固定 base/target，不是任意 Habitat |
| `runtime.vehicle.v1` | 1 | 载具实体、所有权、移动和运行后果 | `UNSUPPORTED` | 当前没有 vehicle state 或 travel binding |
| `runtime.ocean_physics.v1` | 1 | 海洋物理、生存压力和水域移动 | `UNSUPPORTED` | 当前 phase75 profile 不提供海洋语义 |
| `runtime.exclusive_resource.v1` | 1 | 排他资源、永久扣除和升级成本 | `UNSUPPORTED` | progression helper 不足以构成完整 Campaign binding |
| `runtime.pressure_clock.v1` | 1 | 多时钟、机会窗口和错过后果 | `UNSUPPORTED` | 当前没有该通用 runtime contract |

Evaluator mapping 的唯一顺序为：先做 item/schema/security validation；再按 Feature ID
grammar；再查 Catalog；再按下列 requirement-kind compatibility；最后聚合多个候选：

1. candidate array 为空时返回 `BINDING_WARNING / required_feature_missing`，不产生
   binding，且 `seal_allowed=false`；
2. 任一 ID malformed 返回 `REJECTED / feature_id_malformed`；任一 well-formed unknown
   ID 返回 `UNSUPPORTED / feature_id_unknown`；supported candidate 不能把同一 item 的
   unknown required candidate 静默覆盖；
3. known feature 与 `requirement_kind` 不兼容时返回
   `BINDING_WARNING / kind_mismatch`，不自动改写 requirement kind；
4. 多个兼容且都为 supported 的 candidate 按 Feature ID 字典序 canonicalize 并全部
   binding；多个 candidate 之间存在互斥 contract 时返回
   `BINDING_WARNING / multiple_candidate_conflict`；supported 与 unsupported 混合时，
   required item 返回 `UNSUPPORTED / no_runtime_contract` 并只保留空 binding；
5. `content.public_labels.v1` 只接受 `content` 或 `narrative_worldbuilding` 的
   content-only scope；其他当前 `UNSUPPORTED` member 的 compatibility 由其 semantic
   scope 表驱动，不能靠名称相似推断。

兼容性表固定为：

| feature family | accepted requirement kinds |
|---|---|
| `content.public_labels.v1` | `content`, `narrative_worldbuilding` |
| `legacy.profile.phase75_expedition_v1` | `runtime_mechanic`, `world_rule`, `progression_rule`, `public_system`, `resource_economy`（仅 exact legacy binding） |
| `kernel.event_replay.v1` | 不直接接受用户 requirement；只作为 compiler/replay gate |
| `runtime.location_graph.v1`, `runtime.peer_population.v1`, `runtime.ocean_physics.v1` | `world_rule`, `runtime_mechanic`, `public_system`（当前均 `UNSUPPORTED`） |
| `runtime.vehicle.v1` | `world_rule`, `runtime_mechanic`, `public_system`, `protagonist_constraint`, `exclusivity`（当前 `UNSUPPORTED`） |
| `runtime.protagonist_capability.v1`, `runtime.habitat.v1` | `protagonist_constraint`, `runtime_mechanic`, `progression_rule`（当前均 `UNSUPPORTED`） |
| `runtime.entity_ownership.v1`, `runtime.exclusive_resource.v1` | `exclusivity`, `resource_economy`, `progression_rule`, `runtime_mechanic`（当前均 `UNSUPPORTED`） |
| `runtime.network_access.v1`, `runtime.pressure_clock.v1` | `world_rule`, `runtime_mechanic`, `narrative_worldbuilding`（当前均 `UNSUPPORTED`） |
| `runtime.intrusion.v1` | `world_rule`, `runtime_mechanic`, `protagonist_constraint`, `narrative_worldbuilding`（当前 `UNSUPPORTED`） |

`legacy.profile.phase75_expedition_v1` 的“exact legacy binding”不是宽泛的 kind match，
而是以下全部谓词同时成立：

1. `candidate_semantic_feature_ids` 只能有该一个 legacy ID；
2. `normalized_intent` 必须精确等于下列有限 key 之一：
   `legacy.expedition_loop`、`legacy.location_pair`、`legacy.target_search`、
   `legacy.phase_day_night`、`legacy.salvage_resource`、`legacy.player_progression`、
   `legacy.base_progression`、`legacy.build_choice`、`legacy.combat`、
   `legacy.named_actor_mara` 或 `legacy.knowledge_transfer`；
3. `requested_constraints` 只能是空数组，或恰有一个
   `{constraint_id:"legacy_binding_key", constraint_kind:"equals", value:<same key>, required:true}`；
   不接受用户自定义 world rule、主题词、额外成本、任意 exclusivity 或新 entity；
4. `requested_exclusivity` 必须为 `none` 或 `unspecified`，且 requirement kind 必须与
   该 key 的有限 profile mapping 相符；不匹配时返回
   `UNSUPPORTED / legacy_exact_match_failed`，不返回 `SUPPORTED`。

因此兼容性表中的 legacy kinds 只是候选 kind 上界，不能单独触发支持；只有这组 exact
predicate 才可使用 `reason_code=legacy_exact_match`。例如把 `海洋物理` 或任意新
`world_rule` 搭配 legacy ID，因 intent、constraint 或 profile mapping 不匹配而失败。

well-formed 但不在这张表的 Feature ID 结果为 `UNSUPPORTED`；格式错误、包含主题
分支/代码/动态模块或试图改变 Catalog 的 Feature ID 结果为 `REJECTED`。Evaluator
只读取 canonical Request、canonical Proposal 和固定 Catalog；它不读取文件、不调用
网络、不执行代码、不随机采样、不创建任何 runtime artifact。

#### 15.1.2 Phase 10A 的副作用与 generation attempt

未来纯函数边界可以表达为：

```text
evaluate(request, proposal, catalog_v1)
    -> canonical FeatureRequirementReport | stable validation error
```

它只在内存中校验和返回对象；默认不得写 SQLite、Campaign、GameState、DomainEvent、
EventStore、Story、novel 或文件。调用方可以把 Request/Proposal/Report 保存为 attempt
审计证据，但这是外部 orchestration 的显式动作，不是 evaluator 的隐式副作用。

`generation_attempt_id` 与未来的 `campaign_id` 永远不同：attempt 可以在 seal 前失败、
清理或重试，且不预分配 Campaign ID。若需要持久化，命名空间约定为
`genesis_attempts/<attempt_id>/`，其内容只能是 candidate、hash、Report、error 和 metadata；
只有 seal transaction 成功后，才能把 immutable base WorldPack、Initial State 和正式
Campaign 原子发布到正式 namespace。崩溃恢复只承认带有完整 seal record、WorldPack hash
和 parent lineage 的 attempt；没有 seal record 的目录一律视为 candidate，不能自动恢复
成 Campaign。保留/清理周期由未来 policy 决定，但清理 candidate 不能删除正式 sealed
artifact。

若 attempt 持久化，namespace 内的 logical paths 固定为：`manifest.json`、
`candidate/request.json`、`candidate/proposal.json`、`candidate/report.json`、
`candidate/blueprint.json`、`candidate/binding.json`、`candidate/generation_metadata.json`、
`candidate/acknowledgements/<ack_hash>.json`、`prepared/worldpack.json`、
`prepared/initial_state.json`、`prepared/seal_record.json`、`published/campaign.json` 和
`errors/<error_id>.json`。路径必须是相对路径、无 `..`、无 symlink/重解析逃逸；缺失、
额外或错放的正式 artifact 都是 recovery failure。所有 JSON 文件必须保存为本节规定
的 UTF-8 canonical bytes；恢复时先读取 bytes，再 parse、拒绝 unknown field、重新
canonicalize，并要求 `file_bytes == canonical_json(parsed_object)`，之后才计算 SHA-256。
必须同时比对 manifest、SealRecord、Report/acknowledgement、WorldPack、Initial State
和 CampaignRecord 的交叉 lineage/hash，不能只比较 SealRecord 中的字符串。

进入 `READY_TO_SEAL` 的 hard gate 是：`candidate/report.json` 的 `seal_allowed=true`；
没有 required `REJECTED`、required `UNSUPPORTED`、unresolved `BINDING_WARNING` 或未确认
`DEGRADED`；`omitted_optional_requirement_ids` 已按规则列出所有被忽略 optional 项；
所有 required acknowledgement hash 与其 source Report/assessment 相等；WorldPack
preimage、Initial State materialization descriptor 和 compiler identity 都已通过 schema
validation。任一门禁不满足时只能是 `FAILED`，不能写 READY/PREPARED。

#### 15.1.2.1 DegradedAcknowledgement

所有需要确认的 `DEGRADED`（包括 Feature Report item 和 WorldDepthAssessment）都必须
保存 exact `DegradedAcknowledgement` artifact：

```text
{
  acknowledgement_schema_version: 1,
  acknowledgement_id: stable ID,
  source_artifact_kind: FEATURE_REQUIREMENT_REPORT | WORLD_DEPTH_ASSESSMENT,
  source_artifact_hash: lowercase hex64,
  requirement_id: stable ID or null,
  decision: ACCEPT_DEGRADED,
  accepted_scope: UTF-8 string, 1–256 chars,
  lost_capabilities: sorted array of 0–16 stable tokens,
  player_visible_effect: UTF-8 string, 1–1,000 chars,
  user_acknowledged: true
}
```

Feature Report 来源必须有 `requirement_id` 且匹配一个 `user_acknowledgement_required=true`
的 item；WorldDepthAssessment 来源必须为 `requirement_id=null` 且绑定对应 assessment
hash。该对象拒绝 unknown field，`acknowledgement_hash` 是其完整 canonical object 的
SHA-256（不把自身 hash 放回 preimage）。只有有效 acknowledgement hash 出现在
AttemptManifest/SealRecord 的 `acknowledgement_hashes` 中，才可通过对应的 READY gate；
补充 metadata 不能代替用户确认，也不能修改已封存 artifact。

#### 15.1.2.2 GenerationMetadata

Generation metadata 也采用独立 exact artifact，而不是任意 provider 字典：

```text
{
  metadata_schema_version: 1,
  metadata_id: stable ID,
  generation_attempt_id: stable ID,
  producer_kind: EXTERNAL_LLM_EDGE | HUMAN | FIXTURE | DETERMINISTIC_SYSTEM,
  model_reference: string 1–128 chars or null,
  provider_reference: string 1–128 chars or null,
  template_reference: stable ID or null,
  policy_reference: stable ID or null,
  runtime_reference: string 1–128 chars,
  privacy_class: PUBLIC | PRIVATE | REDACTED,
  notes: UTF-8 string 0–1,024 chars
}
```

该 object 拒绝 unknown field；`metadata_hash` 是完整 canonical object 的 SHA-256，不写
回 preimage。`candidate/generation_metadata.json` 的 bytes 必须可重算该 hash；READY、
PREPARED 和 COMMITTED 都必须有 metadata hash。它进入 WorldPack lineage 和 SealRecord，
但不是 World/State authority；失败 attempt 的 metadata 可按 retention policy 清理，已
封存 metadata 不可用新采集结果替换。隐私字段只能使用 PRIVATE/REDACTED，不得把凭据或
原始 secret 放入 artifact。

#### 15.1.2.3 Attempt manifest 与 SealRecord

为使 crash recovery 可唯一实现，attempt manifest 的 exact schema 为：

```text
{
  attempt_manifest_schema_version: 1,
  generation_attempt_id: stable ID,
  request_hash: lowercase hex64,
  status: OPEN | FAILED | READY_TO_SEAL | PREPARED | COMMITTED | ABORTED,
  candidate_hashes: {
    proposal_hash: hex64 or null,
    report_hash: hex64 or null,
    blueprint_hash: hex64 or null,
    binding_hash: hex64 or null,
    generation_metadata_hash: hex64 or null,
    worldpack_hash: hex64 or null,
    initial_state_hash: hex64 or null,
    campaign_record_hash: hex64 or null
  },
  acknowledgement_hashes: sorted array of 0–128 lowercase hex64,
  seal_record_hash: hex64 or null,
  campaign_id: stable ID or null
}
```

该 manifest 只允许这些字段；`generation_attempt_id` 使用
`^[a-z][a-z0-9_]{2,63}$`，`campaign_id` 使用同一 grammar，所有 hash 都是 lowercase
hex64。`campaign_id` 在 COMMITTED 前必须为 `null`；它只在提交时由
`campaign_<first32hex(sha256(canonical({generation_attempt_id, worldpack_hash})))>`
确定性派生并发布，不提前创建 Campaign record。

| manifest status | required hash/state invariant |
|---|---|
| `OPEN` | 只有 request hash；candidate hash 可为空，`acknowledgement_hashes=[]`、`seal_record_hash=null`、正式 artifact 和 campaign 均为空 |
| `FAILED` | candidate/acknowledgement hashes 可部分存在，失败 error 可作为 sidecar 保存；`seal_record_hash=null`、不得有 `campaign_id` 或 COMMITTED seal |
| `READY_TO_SEAL` | proposal/report/blueprint/binding/metadata hashes 齐全，Report gate 和 acknowledgement gate 全通过；WorldPack/State/Campaign 尚未发布，seal hash/campaign ID 仍为空 |
| `PREPARED` | WorldPack/Initial State/metadata 临时 hashes、acknowledgements 和 `seal_record_hash` 齐全；仍无 Campaign record |
| `COMMITTED` | 所有 candidate hashes、acknowledgements、seal hash、CampaignRecord hash 和 campaign ID 全部齐全且交叉验证通过 |
| `ABORTED` | candidate/acknowledgement hashes 可保留为失败证据，但 `seal_record_hash=null`、`campaign_record_hash=null`、campaign 为空；临时 artifact 只能作为失败证据清理 |

基础 WorldPack 的 `SealRecord` exact schema 为：

```text
{
  seal_schema_version: 1,
  seal_id: stable ID,
  generation_attempt_id: stable ID,
  status: PREPARED | COMMITTED,
  request_hash: hex64,
  proposal_hash: hex64,
  report_hash: hex64,
  blueprint_hash: hex64,
  binding_hash: hex64,
  generation_metadata_hash: hex64,
  acknowledgement_hashes: sorted array of 0–128 lowercase hex64,
  worldpack_hash: hex64,
  initial_state_hash: hex64,
  compiler_identity: {
    compiler_id: ^[a-z][a-z0-9_.-]{2,95}$,
    compiler_schema_version: positive integer,
    compiler_implementation_digest: lowercase hex64
  },
  parent_worldpack_hash: null,
  campaign_id: stable ID or null
}
```

`SealRecord.status=PREPARED` 时 `campaign_id` 必须为 `null`；只有 `COMMITTED` 可以有
campaign ID，且其所有 hash、metadata hash 和 acknowledgement hashes 必须与 attempt
manifest 交叉相等。`ABORTED` 不生成正式 SealRecord；若需要保留失败证据，只能放在
`errors/` 下且不能被 manifest 以 `seal_record_hash` 引用。

正式 Genesis `CampaignRecord` 的 exact schema 为：

```text
{
  campaign_schema_version: 1,
  campaign_id: stable ID,
  status: PUBLISHED,
  generation_attempt_id: stable ID,
  request_hash: lowercase hex64,
  worldpack_hash: lowercase hex64,
  initial_state_hash: lowercase hex64,
  seal_record_hash: lowercase hex64,
  campaign_record_hash: lowercase hex64,
  event_store_namespace: "campaigns/<campaign_id>/events",
  story_namespace: "campaigns/<campaign_id>/story",
  current_event_seq: 0
}
```

`campaign_record_hash` 计算时不把自身字段写入 preimage；发布后再将该 hash 填入
AttemptManifest 的 `candidate_hashes.campaign_record_hash` 并复核。CampaignRecord 的
`worldpack_hash`、`initial_state_hash`、`seal_record_hash` 必须分别与 immutable
WorldPack、Initial State 和 COMMITTED SealRecord 的 canonical bytes 重算结果相等；
不接受历史 9B2B manifest 代替这套 Genesis record，也不允许先创建一个没有这些 binding
的 Campaign record。

Seal 状态机是 `READY_TO_SEAL → PREPARED → COMMITTED`，任何校验/绑定失败转为
`FAILED`，准备阶段不可恢复或 hash 不匹配转为 `ABORTED`；`PREPARED` 不等于正式
Campaign。事务顺序为：先计算不含 Initial State hash 的 WorldPack，materialize Initial
State 并计算其 hash，写入临时 immutable artifacts 和 PREPARED SealRecord，最后原子发布
WorldPack、Initial State、COMMITTED SealRecord、attempt manifest 和 Campaign record。
恢复时：PREPARED 必须从固定路径读取 canonical artifact bytes、重新计算所有 hashes、
验证 Report gate、acknowledgement、lineage 和 schema，全部相等才可幂等完成 COMMITTED；
任一不等则 ABORTED 且不创建 Campaign；COMMITTED 只做同样的完整 hash 校验，不重复生成。
未有 COMMITTED
SealRecord 的目录即使存在 candidate 文件也不能晋升。未来 child expansion 使用独立的
child seal schema/transaction，属于 deferred Runtime Expansion，不改变基础 SealRecord。

完整转移表为：`OPEN → READY_TO_SEAL` 只能在上述 hard gates 全通过时发生；`OPEN → FAILED`
表示 proposal/report/schema 阶段失败；`READY_TO_SEAL → PREPARED` 只能在 canonical
WorldPack、Initial State、metadata、acknowledgement 和 PREPARED SealRecord 临时 bytes
全部写入并重算通过时发生；`PREPARED → COMMITTED` 只能在 CampaignRecord 交叉校验通过
时发生；`PREPARED → ABORTED` 是 hash、路径、schema 或恢复校验失败。`FAILED` 和
`ABORTED` 都是 terminal，不能在同一个 attempt 上重试或“胜出”；用户修复必须创建新的
`generation_attempt_id`，可以只引用旧 attempt 的 immutable candidate hashes，不能复用
旧的 campaign ID 或 SealRecord。

#### 15.1.3 两个完整结构化 fixture

下列 fixture 是文档验收输入，不是当前实现。Request A/B、Proposal A/B 的 source hash
已按本节 canonical JSON 规则写出；实现必须重新计算并逐一比对，不能用任意字符串冒充
hash。Report hash 本身由完整 Report envelope 再计算，不需要作为 Report 字段回填。

Fixture A 的完整 Request：

```json
{
  "schema_version": 1,
  "request_id": "fixture_punk_prosthesis_a",
  "raw_prompt": "朋克世界，全民投放系统设定，主角有黑进别人义肢的超能力。",
  "genesis_seed": "771305",
  "content_locale": "zh-CN",
  "explicit_constraints": [
    {"constraint_id": "only_protagonist_power", "constraint_kind": "ownership", "value": "player_only", "required": true},
    {"constraint_id": "no_fake_runtime", "constraint_kind": "excludes", "value": "narrator_only_mechanics", "required": true}
  ],
  "generation_policy_reference": "genesis_fixture_v1"
}
```

Fixture A 的完整 Proposal item 使用下列 exact rows（每行的 `constraints`、`features`、
`notes` 都是对应 JSON 字段；未省略字段的空值分别为 `[]` 或 `""`）：

| requirement_id | kind | required | exclusivity | normalized intent | constraints | candidate features | notes |
|---|---|---|---|---|---|---|---|
| `a_punk_content` | `content` | required | unspecified | 朋克审美和内容表达 | [] | [`content.public_labels.v1`] | content-only |
| `a_public_drop` | `public_system` | required | global_exclusive | 全民投放是世界公开系统 | [`scope=global`] | [`runtime.peer_population.v1`] | 需要真实公共机制 |
| `a_peers` | `runtime_mechanic` | required | global_exclusive | 多个投放者/peers 有自己的目标和推进 | [`population=multiple`] | [`runtime.peer_population.v1`] | 不接受 narrator-only |
| `a_protagonist_power` | `protagonist_constraint` | required | player_only | 主角拥有独有的义肢入侵能力 | [`owner=protagonist`] | [`runtime.protagonist_capability.v1`,`runtime.intrusion.v1`] | 需改变策略空间 |
| `a_prosthesis_entity` | `runtime_mechanic` | required | entity_only | 义肢是可被识别和作用的实体 | [] | [`runtime.entity_ownership.v1`] | 不是标签 |
| `a_ownership` | `exclusivity` | required | entity_only | 义肢有目标所有权 | [`owner=other_actor`] | [`runtime.entity_ownership.v1`] | 需有后果 |
| `a_network` | `world_rule` | required | global_exclusive | 义肢连接到可访问网络 | [`access=bounded`] | [`runtime.network_access.v1`] | 需要知识边界 |
| `a_scan` | `runtime_mechanic` | required | none | 玩家可扫描目标 | [] | [`runtime.intrusion.v1`] | 需要 Action/Event |
| `a_intrusion` | `runtime_mechanic` | required | player_only | 玩家可发起入侵 | [`actor=protagonist`] | [`runtime.intrusion.v1`] | 需要 Reducer |
| `a_defense` | `runtime_mechanic` | required | entity_only | 目标有安全等级和防御 | [] | [`runtime.intrusion.v1`] | 需要 Invariant |
| `a_control` | `runtime_mechanic` | required | entity_only | 入侵可产生控制效果 | [] | [`runtime.intrusion.v1`] | 需要可验证后果 |
| `a_trace` | `runtime_mechanic` | required | global_exclusive | 入侵产生追踪暴露 | [] | [`runtime.intrusion.v1`] | 需要压力/事件 |
| `a_power_limits` | `protagonist_constraint` | required | player_only | 能力有明确限制 | [`limit=explicit`] | [`runtime.protagonist_capability.v1`] | 不是无条件 buff |
| `a_power_cost` | `resource_economy` | required | player_only | 能力有可结算代价 | [`cost=explicit`] | [`runtime.exclusive_resource.v1`] | 需资源或机会成本 |

A 的 canonical Proposal 和 Report 的完整 JSON 如下。表格中的 `constraints` 单元格
按 `requested_constraints` 的 JSON array 展开，`features` 按
`candidate_semantic_feature_ids` 展开；这里进一步给出最终对象，避免把表格当成自然语言
摘要。代码块中的 source hashes 是按 canonical JSON 规则预先计算的 64 位 lowercase
hex；实现必须复算一致。

```json
{
  "proposal_schema_version": 1,
  "source_request_id": "fixture_punk_prosthesis_a",
  "source_request_hash": "f004994df8eb05f615c537211c41ceb3840e88df64d80dc96bc398c50e3db3a0",
  "requirements": [
    {"requirement_id":"a_punk_content","requirement_kind":"content","source_reference":"prompt:a#punk","normalized_intent":"朋克审美和内容表达","required_or_optional":"required","requested_exclusivity":"unspecified","requested_constraints":[],"candidate_semantic_feature_ids":["content.public_labels.v1"],"notes":"content-only"},
    {"requirement_id":"a_public_drop","requirement_kind":"public_system","source_reference":"prompt:a#public-drop","normalized_intent":"全民投放是世界公开系统","required_or_optional":"required","requested_exclusivity":"global_exclusive","requested_constraints":[{"constraint_id":"a_scope_global","constraint_kind":"equals","value":"global","required":true}],"candidate_semantic_feature_ids":["runtime.peer_population.v1"],"notes":"需要真实公共机制"},
    {"requirement_id":"a_peers","requirement_kind":"runtime_mechanic","source_reference":"prompt:a#peers","normalized_intent":"多个投放者或 peers 有自己的目标和推进","required_or_optional":"required","requested_exclusivity":"global_exclusive","requested_constraints":[{"constraint_id":"a_population_multiple","constraint_kind":"limit","value":"multiple","required":true}],"candidate_semantic_feature_ids":["runtime.peer_population.v1"],"notes":"不接受 narrator-only"},
    {"requirement_id":"a_protagonist_power","requirement_kind":"protagonist_constraint","source_reference":"prompt:a#power","normalized_intent":"主角拥有独有的义肢入侵能力","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"a_owner_protagonist","constraint_kind":"ownership","value":"protagonist","required":true}],"candidate_semantic_feature_ids":["runtime.protagonist_capability.v1","runtime.intrusion.v1"],"notes":"需改变策略空间"},
    {"requirement_id":"a_prosthesis_entity","requirement_kind":"runtime_mechanic","source_reference":"prompt:a#prosthesis","normalized_intent":"义肢是可被识别和作用的实体","required_or_optional":"required","requested_exclusivity":"entity_only","requested_constraints":[],"candidate_semantic_feature_ids":["runtime.entity_ownership.v1"],"notes":"不是标签"},
    {"requirement_id":"a_ownership","requirement_kind":"exclusivity","source_reference":"prompt:a#ownership","normalized_intent":"义肢有目标所有权","required_or_optional":"required","requested_exclusivity":"entity_only","requested_constraints":[{"constraint_id":"a_owner_other_actor","constraint_kind":"ownership","value":"other_actor","required":true}],"candidate_semantic_feature_ids":["runtime.entity_ownership.v1"],"notes":"需有后果"},
    {"requirement_id":"a_network","requirement_kind":"world_rule","source_reference":"prompt:a#network","normalized_intent":"义肢连接到有访问边界的网络","required_or_optional":"required","requested_exclusivity":"global_exclusive","requested_constraints":[{"constraint_id":"a_access_bounded","constraint_kind":"equals","value":"bounded","required":true}],"candidate_semantic_feature_ids":["runtime.network_access.v1"],"notes":"需要知识边界"},
    {"requirement_id":"a_scan","requirement_kind":"runtime_mechanic","source_reference":"prompt:a#scan","normalized_intent":"玩家可扫描目标","required_or_optional":"required","requested_exclusivity":"none","requested_constraints":[],"candidate_semantic_feature_ids":["runtime.intrusion.v1"],"notes":"需要 Action/Event"},
    {"requirement_id":"a_intrusion","requirement_kind":"runtime_mechanic","source_reference":"prompt:a#intrusion","normalized_intent":"玩家可发起义肢入侵","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"a_actor_protagonist","constraint_kind":"ownership","value":"protagonist","required":true}],"candidate_semantic_feature_ids":["runtime.intrusion.v1"],"notes":"需要 Reducer"},
    {"requirement_id":"a_defense","requirement_kind":"runtime_mechanic","source_reference":"prompt:a#defense","normalized_intent":"目标有安全等级和防御","required_or_optional":"required","requested_exclusivity":"entity_only","requested_constraints":[],"candidate_semantic_feature_ids":["runtime.intrusion.v1"],"notes":"需要 Invariant"},
    {"requirement_id":"a_control","requirement_kind":"runtime_mechanic","source_reference":"prompt:a#control","normalized_intent":"入侵可产生控制效果","required_or_optional":"required","requested_exclusivity":"entity_only","requested_constraints":[],"candidate_semantic_feature_ids":["runtime.intrusion.v1"],"notes":"需要可验证后果"},
    {"requirement_id":"a_trace","requirement_kind":"runtime_mechanic","source_reference":"prompt:a#trace","normalized_intent":"入侵产生追踪暴露","required_or_optional":"required","requested_exclusivity":"global_exclusive","requested_constraints":[],"candidate_semantic_feature_ids":["runtime.intrusion.v1"],"notes":"需要压力/事件"},
    {"requirement_id":"a_power_limits","requirement_kind":"protagonist_constraint","source_reference":"prompt:a#limits","normalized_intent":"能力有明确限制","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"a_limit_explicit","constraint_kind":"limit","value":"explicit","required":true}],"candidate_semantic_feature_ids":["runtime.protagonist_capability.v1"],"notes":"不是无条件 buff"},
    {"requirement_id":"a_power_cost","requirement_kind":"resource_economy","source_reference":"prompt:a#cost","normalized_intent":"能力有可结算代价","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"a_cost_explicit","constraint_kind":"resource_cost","value":"explicit","required":true}],"candidate_semantic_feature_ids":["runtime.exclusive_resource.v1"],"notes":"需资源或机会成本"}
  ]
}
```

A 的完整 Report envelope 为：

```json
{
  "report_schema_version": 1,
  "source_request_id": "fixture_punk_prosthesis_a",
  "source_request_hash": "f004994df8eb05f615c537211c41ceb3840e88df64d80dc96bc398c50e3db3a0",
  "source_proposal_hash": "575ff3c7d366065f984660052a098a6d34f4a5bb2df53b19e396ea08b56792c8",
  "catalog_version": "genesis-feature-catalog-v1",
  "overall_status": "UNSUPPORTED",
  "seal_allowed": false,
  "omitted_optional_requirement_ids": [],
  "items": [
    {"requirement_id":"a_punk_content","status":"SUPPORTED","reason_code":"content_only","bound_feature_ids":["content.public_labels.v1"],"degraded_binding":null,"lost_capabilities":[],"player_visible_effect":"仅提供朋克内容表达，不提供新的运行机制。","user_acknowledgement_required":false},
    {"requirement_id":"a_public_drop","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["global_public_drop"],"player_visible_effect":"只保留内容表达，不能执行全民投放公共机制。","user_acknowledgement_required":false},
    {"requirement_id":"a_peers","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["peer_population"],"player_visible_effect":"只保留内容表达，不能执行 peers 的状态或离场推进。","user_acknowledgement_required":false},
    {"requirement_id":"a_protagonist_power","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["protagonist_intrusion_capability"],"player_visible_effect":"不能提供主角专属义肢入侵能力。","user_acknowledgement_required":false},
    {"requirement_id":"a_prosthesis_entity","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["prosthesis_entity"],"player_visible_effect":"义肢只能作为内容描述，不能成为可作用实体。","user_acknowledgement_required":false},
    {"requirement_id":"a_ownership","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["entity_ownership"],"player_visible_effect":"不能结算义肢所有权及其后果。","user_acknowledgement_required":false},
    {"requirement_id":"a_network","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["network_access"],"player_visible_effect":"不能结算网络访问边界或知识权限。","user_acknowledgement_required":false},
    {"requirement_id":"a_scan","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["target_scan"],"player_visible_effect":"不能提供可验证的扫描行动。","user_acknowledgement_required":false},
    {"requirement_id":"a_intrusion","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["intrusion_action"],"player_visible_effect":"不能提供可验证的入侵行动。","user_acknowledgement_required":false},
    {"requirement_id":"a_defense","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["intrusion_defense"],"player_visible_effect":"不能结算安全等级或防御。","user_acknowledgement_required":false},
    {"requirement_id":"a_control","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["intrusion_control"],"player_visible_effect":"不能结算入侵控制效果。","user_acknowledgement_required":false},
    {"requirement_id":"a_trace","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["trace_exposure"],"player_visible_effect":"不能结算追踪暴露或其事件后果。","user_acknowledgement_required":false},
    {"requirement_id":"a_power_limits","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["capability_limits"],"player_visible_effect":"不能结算主角能力限制。","user_acknowledgement_required":false},
    {"requirement_id":"a_power_cost","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["capability_cost"],"player_visible_effect":"不能结算主角能力代价。","user_acknowledgement_required":false}
  ]
}
```

每行还包含 `source_reference`（`prompt:a` 或 `constraint:<id>`）、`requested_constraints`
的 typed object、以及 Proposal 的 `source_request_id` 和
`source_request_hash=f004994df8eb05f615c537211c41ceb3840e88df64d80dc96bc398c50e3db3a0`；
这些不是可省略的隐含字段。A 的
Report 预期为：`a_punk_content` 为 `SUPPORTED`、绑定
`content.public_labels.v1`、`reason_code=content_only`、`degraded_binding=null`、
`lost_capabilities=[]`、`user_acknowledgement_required=false`；其余 13 项均为
`UNSUPPORTED`，`bound_feature_ids=[]`、`degraded_binding=null`、
`reason_code=no_runtime_contract`、`lost_capabilities` 列出对应的能力、
`player_visible_effect` 明确写“只保留内容表达，不能执行该机制”、
`user_acknowledgement_required=false`。Report 的 `overall_status` 为 `UNSUPPORTED`。

Fixture B 的完整 Request：

```json
{
  "schema_version": 1,
  "request_id": "fixture_ocean_xuanwu_b",
  "raw_prompt": "全民投放海洋世界。只有主角的初始载具是活体玄武。其他投放者拥有普通载具。玄武升级不消耗普通建造材料，只消耗会被永久扣除的专属资源能量晶石。",
  "genesis_seed": "771305",
  "content_locale": "zh-CN",
  "explicit_constraints": [
    {"constraint_id": "xuanwu_player_only", "constraint_kind": "ownership", "value": "player_only", "required": true},
    {"constraint_id": "crystal_permanent_spend", "constraint_kind": "resource_cost", "value": "permanent_energy_crystal", "required": true},
    {"constraint_id": "exclude_normal_materials", "constraint_kind": "excludes", "value": "normal_build_materials", "required": true}
  ],
  "generation_policy_reference": "genesis_fixture_v1"
}
```

Fixture B 的 Proposal exact rows 为：

| requirement_id | kind | required | exclusivity | normalized intent | constraints | candidate features | notes |
|---|---|---|---|---|---|---|---|
| `b_ocean_content` | `content` | required | unspecified | 海洋世界的内容表达 | [] | [`content.public_labels.v1`] | content-only |
| `b_ocean_physics` | `world_rule` | required | global_exclusive | 海洋物理和水域生存 | [`world=marine`] | [`runtime.ocean_physics.v1`] | 需真实规则 |
| `b_public_drop` | `public_system` | required | global_exclusive | 全民投放系统 | [`scope=global`] | [`runtime.peer_population.v1`] | 需公共机制 |
| `b_peers` | `runtime_mechanic` | required | global_exclusive | 其他投放者有自主状态 | [`population=multiple`] | [`runtime.peer_population.v1`] | 需离场推进 |
| `b_vehicle_entity` | `runtime_mechanic` | required | entity_only | 载具是可运行实体 | [] | [`runtime.vehicle.v1`] | 需状态和行动 |
| `b_vehicle_ownership` | `exclusivity` | required | entity_only | 载具有所有权 | [`owner=actor`] | [`runtime.entity_ownership.v1`] | 需后果 |
| `b_protagonist_xuanwu` | `protagonist_constraint` | required | player_only | 仅主角初始载具为活体玄武 | [`owner=protagonist`] | [`runtime.vehicle.v1`,`runtime.habitat.v1`] | 需独占 binding |
| `b_living_habitat` | `runtime_mechanic` | required | player_only | 活体玄武是可成长 Habitat | [`living=true`] | [`runtime.habitat.v1`] | 需成长轨道 |
| `b_xuanwu_growth` | `progression_rule` | required | player_only | 玄武拥有独立成长轨道 | [`track=xuanwu`] | [`runtime.habitat.v1`] | 不等于普通 progression |
| `b_exclusive_resource` | `resource_economy` | required | player_only | 升级使用专属能量晶石 | [`resource=energy_crystal`] | [`runtime.exclusive_resource.v1`] | 需真实扣除 |
| `b_exclude_materials` | `exclusivity` | required | player_only | 升级排除普通建造材料 | [`excludes=normal_build_materials`] | [`runtime.exclusive_resource.v1`] | 需成本不混淆 |
| `b_permanent_spend` | `progression_rule` | required | player_only | 能量晶石永久扣除 | [`deduction=permanent`] | [`runtime.exclusive_resource.v1`] | 需 Replay proof |
| `b_other_vehicles` | `world_rule` | required | entity_only | 其他投放者拥有不同普通载具 | [`different_from=xuanwu`] | [`runtime.vehicle.v1`,`runtime.peer_population.v1`] | 需比较结构 |

B 的 canonical Proposal 和 Report 的完整 JSON 为：

```json
{
  "proposal_schema_version": 1,
  "source_request_id": "fixture_ocean_xuanwu_b",
  "source_request_hash": "37ebc89b71db4d340d9b1fec769f877a7c7c8834b65cf2a5c8cb4d2108481ccd",
  "requirements": [
    {"requirement_id":"b_ocean_content","requirement_kind":"content","source_reference":"prompt:b#ocean","normalized_intent":"海洋世界的内容表达","required_or_optional":"required","requested_exclusivity":"unspecified","requested_constraints":[],"candidate_semantic_feature_ids":["content.public_labels.v1"],"notes":"content-only"},
    {"requirement_id":"b_ocean_physics","requirement_kind":"world_rule","source_reference":"prompt:b#physics","normalized_intent":"海洋物理和水域生存","required_or_optional":"required","requested_exclusivity":"global_exclusive","requested_constraints":[{"constraint_id":"b_world_marine","constraint_kind":"equals","value":"marine","required":true}],"candidate_semantic_feature_ids":["runtime.ocean_physics.v1"],"notes":"需真实规则"},
    {"requirement_id":"b_public_drop","requirement_kind":"public_system","source_reference":"prompt:b#public-drop","normalized_intent":"全民投放系统","required_or_optional":"required","requested_exclusivity":"global_exclusive","requested_constraints":[{"constraint_id":"b_scope_global","constraint_kind":"equals","value":"global","required":true}],"candidate_semantic_feature_ids":["runtime.peer_population.v1"],"notes":"需公共机制"},
    {"requirement_id":"b_peers","requirement_kind":"runtime_mechanic","source_reference":"prompt:b#peers","normalized_intent":"其他投放者有自主状态和离场推进","required_or_optional":"required","requested_exclusivity":"global_exclusive","requested_constraints":[{"constraint_id":"b_population_multiple","constraint_kind":"limit","value":"multiple","required":true}],"candidate_semantic_feature_ids":["runtime.peer_population.v1"],"notes":"需离场推进"},
    {"requirement_id":"b_vehicle_entity","requirement_kind":"runtime_mechanic","source_reference":"prompt:b#vehicle","normalized_intent":"载具是可运行实体","required_or_optional":"required","requested_exclusivity":"entity_only","requested_constraints":[],"candidate_semantic_feature_ids":["runtime.vehicle.v1"],"notes":"需状态和行动"},
    {"requirement_id":"b_vehicle_ownership","requirement_kind":"exclusivity","source_reference":"prompt:b#vehicle-ownership","normalized_intent":"载具有 actor 所有权","required_or_optional":"required","requested_exclusivity":"entity_only","requested_constraints":[{"constraint_id":"b_owner_actor","constraint_kind":"ownership","value":"actor","required":true}],"candidate_semantic_feature_ids":["runtime.entity_ownership.v1"],"notes":"需后果"},
    {"requirement_id":"b_protagonist_xuanwu","requirement_kind":"protagonist_constraint","source_reference":"prompt:b#xuanwu","normalized_intent":"仅主角初始载具为活体玄武","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"b_owner_protagonist","constraint_kind":"ownership","value":"protagonist","required":true}],"candidate_semantic_feature_ids":["runtime.vehicle.v1","runtime.habitat.v1"],"notes":"需独占 binding"},
    {"requirement_id":"b_living_habitat","requirement_kind":"runtime_mechanic","source_reference":"prompt:b#habitat","normalized_intent":"活体玄武是可成长 Habitat","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"b_living_true","constraint_kind":"equals","value":"living","required":true}],"candidate_semantic_feature_ids":["runtime.habitat.v1"],"notes":"需成长轨道"},
    {"requirement_id":"b_xuanwu_growth","requirement_kind":"progression_rule","source_reference":"prompt:b#growth","normalized_intent":"玄武拥有独立成长轨道","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"b_track_xuanwu","constraint_kind":"equals","value":"xuanwu","required":true}],"candidate_semantic_feature_ids":["runtime.habitat.v1"],"notes":"不等于普通 progression"},
    {"requirement_id":"b_exclusive_resource","requirement_kind":"resource_economy","source_reference":"prompt:b#crystal","normalized_intent":"升级使用专属能量晶石","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"b_resource_crystal","constraint_kind":"resource_cost","value":"energy_crystal","required":true}],"candidate_semantic_feature_ids":["runtime.exclusive_resource.v1"],"notes":"需真实扣除"},
    {"requirement_id":"b_exclude_materials","requirement_kind":"exclusivity","source_reference":"constraint:exclude_normal_materials","normalized_intent":"升级排除普通建造材料","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"b_excludes_normal","constraint_kind":"excludes","value":"normal_build_materials","required":true}],"candidate_semantic_feature_ids":["runtime.exclusive_resource.v1"],"notes":"需成本不混淆"},
    {"requirement_id":"b_permanent_spend","requirement_kind":"progression_rule","source_reference":"constraint:crystal_permanent_spend","normalized_intent":"能量晶石永久扣除","required_or_optional":"required","requested_exclusivity":"player_only","requested_constraints":[{"constraint_id":"b_deduction_permanent","constraint_kind":"equals","value":"permanent","required":true}],"candidate_semantic_feature_ids":["runtime.exclusive_resource.v1"],"notes":"需 Replay proof"},
    {"requirement_id":"b_other_vehicles","requirement_kind":"world_rule","source_reference":"prompt:b#other-vehicles","normalized_intent":"其他投放者拥有不同普通载具","required_or_optional":"required","requested_exclusivity":"entity_only","requested_constraints":[{"constraint_id":"b_different_vehicle","constraint_kind":"excludes","value":"xuanwu","required":true}],"candidate_semantic_feature_ids":["runtime.vehicle.v1","runtime.peer_population.v1"],"notes":"需比较结构"}
  ]
}
```

B 的完整 Report envelope 为：

```json
{
  "report_schema_version": 1,
  "source_request_id": "fixture_ocean_xuanwu_b",
  "source_request_hash": "37ebc89b71db4d340d9b1fec769f877a7c7c8834b65cf2a5c8cb4d2108481ccd",
  "source_proposal_hash": "e8f7a127eb789ab3322a6967714229c21759b964c117feeef41f8cf2e0f6c2a0",
  "catalog_version": "genesis-feature-catalog-v1",
  "overall_status": "UNSUPPORTED",
  "seal_allowed": false,
  "omitted_optional_requirement_ids": [],
  "items": [
    {"requirement_id":"b_ocean_content","status":"SUPPORTED","reason_code":"content_only","bound_feature_ids":["content.public_labels.v1"],"degraded_binding":null,"lost_capabilities":[],"player_visible_effect":"仅提供海洋内容表达，不提供新的运行机制。","user_acknowledgement_required":false},
    {"requirement_id":"b_ocean_physics","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["ocean_physics"],"player_visible_effect":"只能描述海洋，不能执行海洋物理或水域生存。","user_acknowledgement_required":false},
    {"requirement_id":"b_public_drop","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["global_public_drop"],"player_visible_effect":"不能执行全民投放公共机制。","user_acknowledgement_required":false},
    {"requirement_id":"b_peers","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["peer_population"],"player_visible_effect":"不能执行其他投放者的自主状态或离场推进。","user_acknowledgement_required":false},
    {"requirement_id":"b_vehicle_entity","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["vehicle_entity"],"player_visible_effect":"载具只能作为内容描述，不能成为可运行实体。","user_acknowledgement_required":false},
    {"requirement_id":"b_vehicle_ownership","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["vehicle_ownership"],"player_visible_effect":"不能结算载具所有权。","user_acknowledgement_required":false},
    {"requirement_id":"b_protagonist_xuanwu","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["protagonist_xuanwu_binding"],"player_visible_effect":"不能保证只有主角拥有活体玄武初始载具。","user_acknowledgement_required":false},
    {"requirement_id":"b_living_habitat","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["living_habitat"],"player_visible_effect":"不能运行活体 Habitat。","user_acknowledgement_required":false},
    {"requirement_id":"b_xuanwu_growth","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["xuanwu_growth_track"],"player_visible_effect":"不能运行玄武独立成长轨道。","user_acknowledgement_required":false},
    {"requirement_id":"b_exclusive_resource","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["exclusive_energy_crystal"],"player_visible_effect":"不能以专属能量晶石结算升级。","user_acknowledgement_required":false},
    {"requirement_id":"b_exclude_materials","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["material_exclusion"],"player_visible_effect":"不能保证升级排除普通建造材料。","user_acknowledgement_required":false},
    {"requirement_id":"b_permanent_spend","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["permanent_resource_spend"],"player_visible_effect":"不能结算能量晶石的永久扣除。","user_acknowledgement_required":false},
    {"requirement_id":"b_other_vehicles","status":"UNSUPPORTED","reason_code":"no_runtime_contract","bound_feature_ids":[],"degraded_binding":null,"lost_capabilities":["different_peer_vehicles"],"player_visible_effect":"不能保证其他投放者拥有不同的普通载具。","user_acknowledgement_required":false}
  ]
}
```

每行同样必须有 `source_reference`、完整 typed `requested_constraints`、
`source_request_hash=37ebc89b71db4d340d9b1fec769f877a7c7c8834b65cf2a5c8cb4d2108481ccd` 和
Proposal hash。B 的 Report 预期为：
`b_ocean_content` 为 `SUPPORTED` 且只绑定 `content.public_labels.v1`；其余 12 项为
`UNSUPPORTED`，理由是当前没有对应的 marine、vehicle、Habitat、peer、ownership 或
exclusive-resource runtime contract；`overall_status=UNSUPPORTED`。因此两个 fixture
都证明“可以识别和诚实报告需求”不等于“可以创建声称已实现机制的 Campaign”。

#### 15.1.4 Phase 10A 的稳定错误边界

最低错误 code 集为 `GENESIS_SCHEMA_UNKNOWN_FIELD`、`GENESIS_SCHEMA_TYPE`、
`GENESIS_SCHEMA_RANGE`、`GENESIS_SCHEMA_DUPLICATE_ID`、`GENESIS_HASH_MISMATCH`、
`GENESIS_PROMPT_INJECTION`、`GENESIS_FEATURE_ID_MALFORMED`、
`GENESIS_FEATURE_UNSUPPORTED`、`GENESIS_REQUIREMENT_CONFLICT` 和
`GENESIS_ACK_REQUIRED`。错误必须是 canonical machine-readable object；不把 stack trace、
模型原始 prose 或异常文本当作 Report。安全/合同拒绝优先于普通 unsupported；同一
attempt 的错误可以保存用于下一次修复，但不能因重试而获得新的 runtime 权限。

### Phase 10B — World Blueprint / World Bible Contracts

目标：定义 public/hidden world bible、主角、地点、 actors、派系、资源、Habitat/base、
Story Engines、压力时钟、机会窗口、初始区域和扩展约束。只做 candidate contract，
不创建 Campaign、不修改 GameState、不预写固定剧情、不一次性生成所有远方区域。

10B 的最小 candidate Blueprint 必须至少包含：`schema_version=1`、`blueprint_id`、
`source_request_hash`、`source_proposal_hash`、`source_report_hash`、`public_world`、
`hidden_world`、`protagonist`、`initial_region` 和 `requirement_links`。其中
`public_world` 至少有 `display_title`、`content_locale`、`labels`、`summary`；
`hidden_world` 必须有独立 namespace 和 visibility policy；`protagonist` 必须有 stable
`actor_id`、公开身份和 requested capability references；`initial_region` 必须有 stable
region/location IDs、entry location 和显式 edges；`requirement_links` 每项把一个 proposal
requirement 映射到 candidate fact 或 report disposition。`actors`、`factions`、`resources`、
`habitats`、`story_engines`、`clocks` 和 `expansion_policy` 是可选 section，若出现也只
能是 candidate data，不能凭字段名称获得 runtime support。Story Engine、远方扩展和
任何 capability-specific binding 属于后续 contract，不能在 10B 被隐式视为已运行。

### Phase 10C — Bounded Runtime Binding and World Compiler

目标：把已验证 Blueprint 绑定到已实现 Feature Contract，编译、hash、verify 并封存新的
Campaign-specific WorldPack。required unsupported/rejected 必须阻止编译；不得动态生成
代码、加载插件、修改旧 bundle 含义或让 Narrator 补机制。

10C 的第一版输出是 immutable sealed base WorldPack，不是可覆盖的“append-only object”。
`compiler_identity` 采用最小三元组
`{compiler_id, compiler_schema_version, compiler_implementation_digest}`；accepted SHA
可以作为审计 metadata，但不能单独代替 contract identity。每次 binding 或 compiler
contract 改变都产生新的 WorldPack identity。Runtime Expansion 只能在未来独立 phase
中作为绑定父 hash 的 immutable child artifact 实现；它不得修改 base WorldPack、重写
base hash 或借“append-only”掩盖覆盖语义。

### Phase 10D — Fast Static Analysis and Scripted Preflight

目标：在正式 Campaign 前检查 schema、引用、初始行动、连通性、资源、核心循环、死锁、
策略差异、时钟/NPC/Story Engine 推进和 Replay；使用确定性短程试玩，不生成小说，不在
玩家开局前运行完整 model matrix。

10D 的输入必须是已封存 base WorldPack、由它 materialize 的 Initial GameState、对应
Feature Catalog/version 和 preflight policy；输出是 canonical machine-readable report，
每个 check 记录 `check_id`、`severity`、`status`、`reason_code`、`metrics` 和输入 hash。
硬门禁至少包括：schema/reference 完整性、初始合法行动、必需资源可达、核心 invariant、
固定短程 Replay 一致性；任何 hard gate 的 `FAIL` 或 hard timeout 都阻止 Campaign。
策略分歧、时钟/NPC/Story Engine 推进、World Depth 和 WAIT exhaustion 可以先是
diagnostic，但若 WorldPack 宣称启用相应 feature，则必须升级为该 feature 的 hard gate。
超时不是成功；只能返回 `FAIL` 或合同定义的 `DEGRADED`，不能用 prose 代替指标。

### Phase 10E — Genesis-to-Campaign End-to-End Proof

目标：证明 Prompt+Seed 到 Report、Blueprint、Binding、WorldPack、Initial State、Preflight、
Campaign、Story、Verify 的完整闭环；证明失败无正式 Campaign、成功包被封存、Replay 不
依赖 Generator、Story 不拥有 authority、结构不同 Prompt 不是 label 换皮、不支持机制
不会被 Narrator 伪装，旧 PC1 和旧 bundle 仍可验证。

10E 的 fixture gate 至少包括两类比较：

- 同一 Prompt、不同 Seed：固定 pair 使用 Fixture A 的相同 Proposal/Prompt、
  `genesis_seed="771305"` 与 `genesis_seed="771306"`，并在第一个真正支持 depth 的
  profile 上记录不同 `generation_path_digest`；至少一个 structural canonical field（地点
  拓扑、资源循环、压力时钟、actor goal 或 protagonist capability binding）必须不同。若
  出现相同结果，记录 collision，不能宣称 Seed 产生结构差异。当前 Fixture A/B 的
  required runtime features 是 `UNSUPPORTED`，所以它们只能证明诚实报告，不能冒充这项
  WorldPack structural proof；未测 seed pair 不得外推为普遍保证。
- 结构不同的 Prompt：比较 sealed WorldPack、Initial State、合法 Action、Report 和
  short Replay；必须观察到至少一项 topology/resource/pressure/NPC/strategy 差异，同时
  shared Kernel/replay contract 保持稳定。只改 title、label、premise 或 prose 不合格。

World Depth claim 的第一版 hard gate 适用于声明启用 depth 的 WorldPack：至少 3 个相连
地点、2 个有独立目标的 actor、2 个并行 active pressure/opportunity clocks、1 个可错过且
不可逆机会、off-screen deterministic progression、主角能力启用/移除后的策略空间差异，
以及 20 个有意义回合不退化为 WAIT-only。若 profile 不能满足，必须撤销 depth claim，或
以 `DEGRADED` + 玩家确认封存；不能靠 Narrator 补齐。主角 A/B proof 比较 legal action
集合、可达策略和资源/机会代价，而不是只比较一个数值 buff。

#### 15.2 WorldDepthAssessment contract（10D/10E；不是 10A Report）

`Feature Requirement Report` 只报告需求支持状态，不负责宣称 World Depth。10D/10E
另产生 exact `WorldDepthAssessment`，用来把“启用 depth”与 `DEGRADED` 路径机器化：

```text
{
  depth_schema_version: 1,
  source_worldpack_hash: lowercase hex64,
  depth_claim: NONE | WORLD_DEPTH_V1,
  status: NOT_REQUESTED | PASS | DEGRADED | FAIL,
  predicate_metrics: {
    connected_location_count: non-negative integer,
    independent_actor_goal_count: non-negative integer,
    active_clock_count: non-negative integer,
    irreversible_missable_opportunity_count: non-negative integer,
    offscreen_progression_owner: Feature ID or null,
    meaningful_turn_count: non-negative integer,
    wait_only_terminal: boolean,
    protagonist_a_b_strategy_delta: {
      legal_action_difference_count: non-negative integer,
      reachable_strategy_difference: boolean,
      resource_or_opportunity_cost_difference: boolean
    }
  },
  lost_capabilities: array of 0–16 stable tokens,
  player_visible_effect: UTF-8 string, 1–1,000 chars,
  user_acknowledgement_required: boolean,
  gate_report_hash: lowercase hex64,
  campaign_allowed: boolean
}
```

该对象只允许上述字段；`source_worldpack_hash` 绑定被检查的 immutable WorldPack，
`gate_report_hash` 绑定所有 predicate metrics，不能由 Narrator 或 prose 生成。规则为：

- `depth_claim=NONE` 时 `status=NOT_REQUESTED`、不产生 acknowledgement artifact、
  `campaign_allowed=true`，但任何产品表面都不能宣称启用 World Depth；
- `depth_claim=WORLD_DEPTH_V1` 且所有阈值通过时为 `PASS`，`campaign_allowed=true`，
  `user_acknowledgement_required=false`；
- 若只缺少可明确描述的窄能力，可为 `DEGRADED`，但 `lost_capabilities`、
  `player_visible_effect`、`user_acknowledgement_required=true` 都必须存在。对应的
  `DegradedAcknowledgement` hash 必须在 Campaign publication 前写入 SealRecord；没有它
  时 `campaign_allowed=false`，不能以浅层包冒充完整 depth；
- 任一硬阈值失败、off-screen owner 缺失、A/B strategy proof 无差异或 terminal
  WAIT-only 时为 `FAIL`，`campaign_allowed=false`；确认不能把 FAIL 变成 PASS。

`WorldDepthAssessment` 的 hash 是 Campaign publication gate/SealRecord 的 lineage，
不是反向写入 WorldPack 的 State hash，因此不会破坏 WorldPack→Initial State 的单向依赖。
Generic Feature `DEGRADED` 的确认仍按 §11 在 WorldPack seal 前完成；World Depth claim
是更晚的产品质量声明，必须在 Campaign publish 前由这份 assessment 决定。

## 16. Acceptance example A — 朋克 / 义肢入侵

输入：

```text
Prompt：朋克世界，全民投放系统设定，主角有黑进别人义肢的超能力
Seed：771305
```

至少拆出：朋克题材与审美、全民投放世界规则、多个投放者/peers、主角专属能力、
义肢实体、目标所有权、网络状态、扫描、入侵、安全等级、控制效果、追踪暴露、能力
限制与代价。

当前 `pc1-frozen` 不能声称支持全民投放社会、真实 peers、义肢实体、义肢入侵或网络
追踪。诚实报告应至少是：

| requirement | current result |
|---|---|
| 朋克审美与文字表达 | content proposal；不等于 runtime support |
| 全民投放与大规模 peers | `UNSUPPORTED`；只有未来明确本地 peer 降级 contract 才可 `DEGRADED` |
| 义肢实体、网络、扫描、入侵、防御、trace | `UNSUPPORTED` |
| 主角专属能力 | 只有在某个已实现 Feature Contract 有完整 binding 时才可支持 |

结果：不能创建一个声称义肢入侵真实可用的 Campaign。Narrator 可以描写朋克氛围，
但不能写成已拥有入侵能力或已发生网络后果。

## 17. Acceptance example B — 海洋 / 活体玄武

输入：

```text
Prompt：全民投放海洋世界。只有主角的初始载具是活体玄武。其他投放者拥有普通载具。
玄武升级不消耗普通建造材料，只消耗会被永久扣除的专属资源能量晶石。
Seed：771305
```

至少拆出：海洋题材、海洋物理、全民投放、peers、载具实体、载具所有权、主角专属
载具、活体 Habitat、玄武成长轨道、专属升级资源、排除普通材料、能量晶石永久扣除、
其他投放者不同载具。

不能因为现有 `progression.py` 或 helper 能表达某种 cost mapping，就声称完整支持。
必须检查 compiler 是否能创建任意 Habitat、Reducer 是否能升级 Habitat track、Projection
是否能展示、Campaign 是否能运行、WorldPack 是否能表达 exclusivity、peers 是否存在、
海洋物理是否存在。

当前诚实结果：

| requirement | current result |
|---|---|
| 海洋、玄武、载具的题材表达 | content proposal |
| 海洋运行物理 | `UNSUPPORTED` |
| 全民投放与 peers | `UNSUPPORTED` |
| 活体玄武 Habitat、所有权和成长 | `UNSUPPORTED` |
| 专属能量晶石升级 | 底层 progression helper 只是部分概念基础；完整 Campaign binding 尚不存在，不能标为 `SUPPORTED` |

## 18. Performance and failure budget

未来 Genesis 流程应使用有限预算：schema validation 通常低于 1 秒，static analysis 秒级，
scripted preflight 目标数秒；总流程方向性目标 P50 约 20 秒、P95 不超过 60 秒、hard timeout
约 90 秒。超时必须失败或显式降级，不能无限自动 repair。

Generation attempt 必须在临时区域完成；只有所有 required gate 通过后才可原子发布
WorldPack、Initial State 和 Campaign。失败可以保留 candidate、Report 和错误证据，但
正式 Campaign 列表、SQLite、EventStore 和 Narrative 不能留下半成品。

## 19. Explicit open questions

以下问题故意留在合同层，不在 Phase 10A 猜测实现；它们不允许成为无 owner 的运行时
承诺：

1. Requirement Proposal 的自然语言覆盖率由独立 LLM critic、人工确认还是 PC2 承担？
2. Generation policy 如何版本化，哪些 metadata 必须保存，哪些涉及隐私？
3. 第一个可运行的第二 runtime profile 应挑战哪些结构假设？
4. 已决定：需要确认的 `DEGRADED` 在 WorldPack seal 前完成，并将 acknowledgement 纳入 seal metadata/hash。
5. Hidden Blueprint 如何向玩家、NPC、Narrator 按知识边界投影？
6. compiler implementation identity 的实现落地细节仍需决定，但合同已经规定它必须是
   `{compiler_id, compiler_schema_version, compiler_implementation_digest}` 三元组；accepted
   SHA 只能作为 metadata，不能单独成为 authority。
7. Runtime expansion 的 quota、深度、child namespace 和超限行为是什么？
8. Story Engine 的具体 off-screen owner 仍待真实 Feature Contract 决定；但任何启用
   off-screen progression 的 Blueprint/WorldPack 必须列出 versioned owner、Event/Replay
   归属和预算，否则只能 `UNSUPPORTED`/`DEGRADED`，不能无 owner 地声称支持。

## 20. Intentionally deferred decisions

World Blueprint 实现、World Compiler v2、runtime profile boundary、feature-local reducer/
invariant migration、Presentation v2、Story Context v2、PC2、natural-language action
semantics、Capability Foundation、Cybernetic Intrusion、Habitat/Xuanwu、Peer Population、
Mass Drop、runtime lazy expansion、real LLM provider、automatic repair 和 deep model matrix
均延期。每项的依赖和证据门槛见 [`DEFERRED.md`](DEFERRED.md)。

---

## 21. Contract decision summary

- Genesis 可以生成内容、候选结构和 Campaign-specific WorldPack；WorldPack 不必都是开发者预制。
- Seed 是生成路径输入；sealed WorldPack 是 Campaign 事实来源。
- Proposal、Report、Blueprint 在封存前不是 State、Event 或 Narration 事实。
- Feature status 必须严格区分 `SUPPORTED`、`DEGRADED`、`UNSUPPORTED`、`REJECTED` 和 Binding Warning。
- 主题关键词不能决定 runtime；Feature Catalog 描述语义，不描述题材。
- Narrator 只能描述 committed facts，不能补齐缺失机制。
- 失败 generation attempt 无 Campaign 副作用；成功 WorldPack 必须保存、hash、seal 并可 Verify。
- Phase 1–9 与 PC1 保留；结构性泄漏通过未来 superseding boundary 处理，本轮不重构。
- Phase 10A 是无副作用的输入与支持报告合同；Phase 10B–10E 是后续路线，不在本轮实现。
