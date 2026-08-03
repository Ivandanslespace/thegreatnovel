# Phase 1–9 Hardcoding Inventory and Superseding Boundaries

状态：**只读架构审计结果；本轮不修改下列代码。**

本文件记录当前 `phase-10-genesis-foundation` 分支在 Phase 1–9 生产代码和测试中的
硬编码、局部 profile 与结构性泄漏。它的目的不是要求推倒重写，也不是把所有常量
判成坏代码，而是为未来 Genesis 和新的 runtime profile 标出可保留的 Kernel、合法的
first slice 以及必须通过 superseding contract 处理的边界。

---

## 1. Audit scope

审计范围：

- `src/tgn/core/**`
- `src/tgn/actions/**`
- `src/tgn/gameplay/**`
- `src/tgn/worldgen/**`
- `src/tgn/projection/**`
- `src/tgn/autoplay/**`
- `src/tgn/llm_player/**`
- `src/tgn/session/**`
- `src/tgn/campaign/**`
- `src/tgn/story/**`
- `src/tgn/play/**`
- 与上述路径对应的 `tests/**`

重点核查：single mechanics profile、fixed action list/cost/base/target、
`target_searched`、phase cycle、resource/build、Mara、reducer/invariants、Projection
action schema、Autoplay/Session/Campaign/Story reconstruction imports、WorldGen
labels-only schema、Genesis seed、bundle/compiler identity。

本审计基于当前真实文件和 Git ref。当前基线为：

```text
branch: phase-10-genesis-foundation
HEAD: 17d4098771798e44a078e6a93a94137feb0bd8c0
pc1-frozen tag object: 5d31d66997d2d7fc883529ba342877a2680bb983
pc1-frozen target commit: 17d4098771798e44a078e6a93a94137feb0bd8c0
phase-9b1-frozen tag object: 53806d07a239a2e8f84db7cc64c966bd1723c11e
phase-9b1-frozen target commit: a4c79a47dfac88c3f9b39aa8ca50cc6255d48902
```

当前工作树的未跟踪 `.codex/` 与 `AGENTS.md` 是任务前已有内容；本文件不将它们
当作生产代码修改。

## 2. Evaluation criteria

### 2.1 不是“看到常量就判坏”

一个常量可能是必要的确定性语义，例如时间不能倒退、资源不能为负、Event 必须可
Replay、某个 gate 如何检查成本。也可能只是第一世界的内容，例如所有世界都只有
`site-1`、资源都叫 `salvage`、NPC 都是 Mara。

判断问题是：

> 这个值表达的是稳定、可测试的因果规则，还是一个世界的具体故事内容或固定试玩结构？

### 2.2 分类定义

| category | 解释 |
|---|---|
| `SAFE_KERNEL_FOUNDATION` | 跨世界仍是引擎完整性、持久化、hash、Replay 或安全边界所需的基础；当前应保留。 |
| `LEGITIMATE_FIRST_SLICE` | 已审查、已验证的第一条垂直切片局部规则；可以保留为 profile，但不能冒充通用世界模型。 |
| `STRUCTURAL_LEAK_IN_GENERIC_LAYER` | generic/core 或跨层服务直接认识具体玩法，未来扩展会被迫污染既有边界。 |
| `LEGACY_RUNTIME_PROFILE` | 历史兼容入口或旧运行路径，必须保留回归行为，但不能作为 Genesis 默认语义。 |
| `FUTURE_SUPERSEDING_BOUNDARY` | 当前行为可冻结保留，但未来必须用新版本、adapter、phase 或 contract 处理。 |
| `DO_NOT_GENERALIZE_YET` | 当前局部实现是合理的，但尚未有第二个结构不同 use case 证明可以抽象。 |

`safe_to_keep` 表示当前是否应保留，不表示未来永远不能 supersede；
`blocks_genesis` 表示是否会阻止本合同目标，而不是要求本轮立即修复。

## 3. Complete finding table

| finding_id | file | symbol | phase_origin | hardcoding_type | current_role | safe_to_keep | blocks_genesis | future_treatment | evidence |
|---|---|---|---|---|---|---|---|---|---|
| F-01 | `src/tgn/worldgen/models.py`; `src/tgn/worldgen/compiler.py` | `COMPILER_ID`, `MECHANICS_PROFILE`, `validate_draft` | Phase 9B1 | `LEGITIMATE_FIRST_SLICE` | 只允许 `phase75_expedition_v1` 并绑定当前 compiler identity | yes | 当前 bounded profile 不阻止；多 profile Genesis 会受限 | 新 profile 使用新 compiler/schema，不改 frozen v1 | `models.py:10-22`; `compiler.py:459-481,687-713` |
| F-02 | `src/tgn/worldgen/compiler.py` | `compile_worldpack`, `materialize_initial_state` | Phase 9B1 | `LEGITIMATE_FIRST_SLICE` | 固定 `base-1`、`site-1`、`salvage`、Mara runtime bindings | yes | 当前不阻止；结构不同 WorldPack 会受限 | profile-specific compiler；不要建立 universal binding schema | `compiler.py:47-56,687-713,727-740` |
| F-03 | `src/tgn/gameplay/expedition.py` | `get_legal_actions`, `validate_action`, `execute_action` | Phase 3–7.5 | `LEGITIMATE_FIRST_SLICE` | 固定 `WAIT/DROP/SEARCH/EXTRACT/FIGHT/FLEE/UPGRADE_PLAYER/UPGRADE_BASE/REST/CHOOSE_BUILD/TALK_TO_ACTOR` 及固定 cost；`WAIT` 是正整数 minutes 输入 | yes | 当前不阻止；直接向此模块堆机制会扩大耦合 | 新 capability 使用明确 vertical slice，不建设 generic action/effect DSL | `expedition.py:35-43,45-212,223-225,343-353,444-624` |
| F-04 | `src/tgn/worldgen/compiler.py` | `materialize_initial_state` | Phase 9B1 | `LEGITIMATE_FIRST_SLICE` | 固定 `target_searched=False`、loot、player/base progression、build choice、Mara state | yes | 当前不阻止；未来 Genesis 需要新 profile 时不能复用为宇宙规则 | 新 profile 通过 superseding compiler materialize | `compiler.py:746-810` |
| F-05 | `src/tgn/worldgen/compiler.py`; `src/tgn/gameplay/world_phase.py`; `src/tgn/core/invariants.py` | `_PHASE_CYCLE`, `get_current_phase`, `_check_phase_cycle_invariants` | Phase 5 | `DO_NOT_GENERALIZE_YET` | 当前 compiler profile 固定 120 分钟 cycle、60 分钟 boundary、`DAY → NIGHT`，NIGHT 阻塞 DROP；当前 phase-cycle state contract 限制为两个非空且不同的 phase label | yes | 当前不阻止；3+ phases 或不同 transition 的 world 会受限 | 保留 current helper/state contract；真实需求出现后建立新的 phase contract，不把它宣称为通用 phase engine | `compiler.py:49-55`; `world_phase.py:18-69`; `core/invariants.py:269-329` |
| F-06 | `src/tgn/gameplay/build_choice.py`; `src/tgn/core/invariants.py` | `_FIRST_WORLD_BUILD_DETAILS`, `SUPPORTED_BUILDS`, `_check_build_invariants` | Phase 7 | `DO_NOT_GENERALIZE_YET` | 固定 `window_runner`、`field_rest`、`quick_rest` 及效果 | yes | 当前不阻止；不应限制未来 capability source | 新 capability 建立 feature-local contract，不升级为 SkillTree/EffectSystem | `build_choice.py:19-62,122-145`; `invariants.py:395-460` |
| F-07 | `src/tgn/gameplay/named_actor.py` | Mara constants、`validate_named_actor_state`, `decide_named_actor_action` | Phase 7.5 | `LEGITIMATE_FIRST_SLICE` | 单一 Mara、单一 fact、trust 变化和 `INSPECT_SIGNAL` 行为 | yes | 当前不阻止；未来多 actor/relationship 不能直接复制 | 保持 Mara 局部；未来 actor/relationship 使用新 contract | `named_actor.py:17-32,68-123,151-240` |
| F-08 | `src/tgn/core/reducer.py` | `reduce_event` 与 phase-specific handlers | Phase 1 + 3–7.5 | `STRUCTURAL_LEAK_IN_GENERIC_LAYER` | Core 直接分支 expedition/combat/progression/build/Mara Event，并导入 gameplay | 仅保留 frozen regression | 会阻止以“继续加 elif”的方式扩展 Genesis | 新 phase 引入受控 handler seam；本轮不改 frozen reducer | `reducer.py:65-120,166-177,567-624` |
| F-09 | `src/tgn/core/invariants.py` | `check_invariants`, `_check_phase_cycle_invariants`, `_check_progression_invariants`, `_check_build_invariants` | Phase 1 + 5–7.5 | `STRUCTURAL_LEAK_IN_GENERIC_LAYER` | Core invariant 入口直接调用 Mara validation 并依赖 `SUPPORTED_BUILDS` | 仅保留 frozen compatibility | 未来 profile/capability 会继续污染 Core invariant 层 | 新 feature 应有局部 boundary validation；本轮不重构 | `invariants.py:49-81,269-444` |
| F-10 | `src/tgn/actions/validation.py` | `LEGAL_ACTION_TYPES` | Phase 2 | `LEGACY_RUNTIME_PROFILE` | 旧 Phase 2 路径固定只允许 `WAIT`，与 expedition path 并存 | yes | 若误用此入口会错误拒绝新 action | 不扩成新 gameplay registry；使用新的 vertical-slice boundary | `validation.py:15-16,44-76,134-183`; `tests/actions/test_phase2_actions.py:19-57` |
| F-11 | `src/tgn/projection/presenter.py` | `_ACTION_PARAM_SCHEMA`, `_validate_choice_schema`, `_map_choice` | Phase 9B2A | `DO_NOT_GENERALIZE_YET` | Projection 固定 action schema，只有 `CHOOSE_BUILD`、`TALK_TO_ACTOR` 有参数 | yes | 新 capability 若没有新 versioned projection 无法呈现 | 新 action 使用新 projection schema/version；不静默放宽 | `presenter.py:226-325`; `tests/projection/test_compiler_presenter.py:237-266` |
| F-12 | `src/tgn/worldgen/models.py`; `src/tgn/worldgen/compiler.py` | `DRAFT_FIELDS`, `LABEL_FIELDS`, `validate_draft` | Phase 9B1 | `DO_NOT_GENERALIZE_YET` | Draft 只能提供 title/premise/locale/labels，不能提供 runtime IDs、rules、state、events、reward | yes | 保护当前边界；也会阻止未来结构性 WorldPack | 新 reviewed profile 扩展；不把 labels-only schema 宣称为 universal schema | `models.py:12-34`; `compiler.py:505-543`; `MVP_REWRITE_SPEC.md:3861-3873` |
| F-13 | `src/tgn/autoplay/runner.py` | `run_autoplay` | Phase 3.5–8 | `STRUCTURAL_LEAK_IN_GENERIC_LAYER` | 直接导入 expedition、Mara metrics，并假定每个 accepted action 恰有一个 Event | 当前回归可保留 | 多 Event capability 或非 Mara feature 会受限 | 将 optional metrics 与通用 runner 分离；本轮不改 frozen runner | `runner.py:8-16,57-75,113-126,160-165` |
| F-14 | `src/tgn/session/service.py` | `_verify_recorded_transition_trace` | Phase 9A | `STRUCTURAL_LEAK_IN_GENERIC_LAYER` | Session 重建直接 `build_observation`/`execute_action`，绑定 expedition runtime | 当前 Session 合同可保留 | 新 action 若不能穿过稳定 execution boundary 会受限 | 新 Session contract 依赖 versioned engine boundary；本轮不改 | `service.py:20-38,277-335` |
| F-15 | `src/tgn/campaign/service.py`; `src/tgn/campaign/verification.py` | Campaign bootstrap/verification | Phase 9B2B | `STRUCTURAL_LEAK_IN_GENERIC_LAYER` | Campaign 直接导入 expedition observation，并绑定 Projection/Session/WorldGen artifacts | 当前 adapter 可保留 | 新 profile 需要新的 Campaign verification boundary | 使用 versioned artifact adapters；不原地修改 frozen Campaign | `campaign/service.py:14-36,275-318`; `campaign/verification.py:15-33,564-606` |
| F-16 | `src/tgn/story/reconstruction.py` | `_reconstruct_request`, `reconstruct_campaign` | Phase 9C1/9C2 | `STRUCTURAL_LEAK_IN_GENERIC_LAYER` | Story reconstruction 依赖 expedition observation、Projection map、固定 Session action-id | 当前 deterministic Story 可保留 | 新 action/event 结构会产生跨层扩展压力 | 新 narration/reconstruction contract 使用 versioned request builder | `reconstruction.py:9-15,207-305` |
| F-17 | `src/tgn/worldgen/models.py`; `src/tgn/worldgen/__main__.py`; `src/tgn/worldgen/compiler.py` | `WorldGenesisRequest`, CLI parser, `_validate_seed` | Phase 9B1 → Genesis seam | `FUTURE_SUPERSEDING_BOUNDARY` | Request 只有 schema/prompt；seed 由 `--seed` 或函数参数单独传入 | current v1 可保留 | 自包含 Genesis Request 必须显式绑定 seed | 新 Genesis envelope 显式携带 seed 和新 schema；不修改 v1 | `models.py:12,82-90`; `__main__.py:28-34`; `compiler.py:297-355,655-670,901-912` |
| F-18 | `src/tgn/core/models.py`; `src/tgn/storage/event_store.py`; `src/tgn/campaign/verification.py` | `GameState.seed`, `GameState.initial`, `CampaignRecord`, SQLite schema | Phase 1 legacy | `LEGACY_RUNTIME_PROFILE` | Core/EventStore/SQLite 允许空 seed 或 `default-seed`；WorldGen 才强制非空 | yes，作为历史兼容 | 新 Genesis 若绕过边界会掩盖缺失 seed | 新 schema fail closed，不继承空 seed 默认 | `core/models.py:19-38`; `event_store.py:22-52,130-145`; `campaign/verification.py:82-87,117-124` |
| F-19 | `src/tgn/worldgen/models.py`; `src/tgn/worldgen/bundle.py`; `src/tgn/projection/models.py`; `src/tgn/projection/bundle.py`; `src/tgn/campaign/verification.py` | compiler/bundle identity checks | Phase 9B1/9B2A/9B2B | `FUTURE_SUPERSEDING_BOUNDARY` | WorldGen identity 集中复用；Projection/Campaign 有重复 raw literal | yes，作为当前 provenance gate | identity migration 容易漂移，可能错误解释旧 artifact | 新 bundle/compiler 使用新 identity/version；不改当前 literal | `worldgen/models.py:10`; `worldgen/bundle.py:116,208`; `projection/models.py:14-15,227-251`; `campaign/verification.py:578-625` |
| F-20 | `tests/gameplay/conftest.py`; `tests/gameplay/phase75_helpers.py`; `tests/autoplay/conftest.py` | first-world fixtures | Phase 3–7.5 | `LEGITIMATE_FIRST_SLICE` | 固定 base/site、stamina、loot、Mara 和 Phase 7.5 state machine | yes | 当前不阻止 | 新 profile 新建 fixture，不泛化或改写旧测试 | `tests/gameplay/conftest.py:8-32`; `tests/gameplay/phase75_helpers.py:18-64` |
| F-21 | `tests/worldgen/conftest.py`; `tests/worldgen/test_phase9b_world_compiler.py`; `tests/projection/**` | WorldGen/Projection fixtures and identity assertions | Phase 9B1/9B2A | `DO_NOT_GENERALIZE_YET` | 测试断言固定 runtime bindings、projection identities、labels-only、seed 分离 | yes，当前 acceptance proof | 当前不阻止；未来结构性 WorldPack 必须新 contract/test set | 保留旧 tests；新 profile 新增独立测试 | `tests/worldgen/conftest.py:13-42`; `tests/worldgen/test_phase9b_world_compiler.py:28-54,88-139`; `tests/projection/test_models_validation.py:32-47` |
| F-22 | `tests/campaign/test_independence.py`; `tests/story/test_edges.py` | fixed action/reconstruction sequences | Phase 9B2B/9C | `LEGACY_RUNTIME_PROFILE` | 固定 `DROP → SEARCH → EXTRACT → TALK_TO_ACTOR`、Event type、cost、Session action-id | yes，作为 frozen replay/narration regression | 当前不阻止；新 capability 不能假定此序列 | 不修改旧 tests；新 action 用 superseding test contract | `tests/campaign/test_independence.py:131-173`; `tests/story/test_edges.py:52-105` |
| F-23 | `src/tgn/projection/models.py`; `src/tgn/projection/compiler.py`; `src/tgn/projection/presenter.py`; `src/tgn/projection/bundle.py` | `ProjectionDraft`, `PlayerProjectionMap`, `PROJECTION_COMPILER_ID` | Phase 9B2A | `FUTURE_SUPERSEDING_BOUNDARY` | Projection Draft 只有固定 label fields；`PlayerProjectionMap` 绑定 `schema_version`、`projection_compiler_id`、`mechanics_profile`、source WorldPack/Initial State hashes、locale、world 和 identities | yes，作为 frozen presentation contract | 当前不阻止；新的 runtime semantics 若没有 Presentation v2 无法正确呈现 | 为新 action/identity 建立 versioned Presentation v2；不静默放宽 PC1/9B2A schema | `projection/models.py:14-31,102-155`; `projection/compiler.py:134-238,390-450`; `projection/presenter.py:226-238`; `projection/bundle.py:227-251` |
| F-24 | `src/tgn/worldgen/compiler.py`; `src/tgn/autoplay/runner.py`; `tests/campaign/test_independence.py` | compiler bootstrap 与 observation smoke | Phase 9B1/9B2B | `LEGITIMATE_FIRST_SLICE` | compiler、Autoplay 和 campaign proof 共同假定 `DROP → SEARCH → EXTRACT → TALK_TO_ACTOR`、4 个 bootstrap events、Mara autonomous action、knowledge transfer 和 relationship change | yes，作为当前 bounded smoke | 当前不阻止；非 Mara、多 Event 或不同 initial loop 会受限 | 保留第一 slice；第二 profile 前建立 versioned bootstrap/observation adapter，不在 generic layer 继续加隐式假设 | `compiler.py:822-865,913-938`; `autoplay/runner.py:57-75`; `tests/campaign/test_independence.py:131-173` |
| F-25 | `src/tgn/autoplay/policy.py` | policy priority and action builders | Phase 3.5–8 | `LEGITIMATE_FIRST_SLICE` | Autoplay policy 固定 `SEARCH > FIGHT > EXTRACT > DROP` 优先级，并为当前 expedition 构造固定 action payload | yes，作为当前 bounded autoplay policy | 当前不阻止；新 profile/行动不能被迫伪装成该优先级或 payload | 新 profile 使用 versioned policy/adapter；不把当前策略提升为通用 agent planner | `autoplay/policy.py:26-131` |

### 3.1 F-03 的 exact action/cost evidence

F-03 的固定值不是未来 Genesis 的 cost contract，但必须在 inventory 中完整记录：
`DROP_COST={time:10, stamina:1}`、`SEARCH_COST={time:30, stamina:2}`、
`EXTRACT_COST={time:15, stamina:0}`、`FIGHT_COST={time:10, stamina:1}`、
`FLEE_COST={time:15, stamina:0}`、`UPGRADE_COST={time:5, stamina:0}`、
`REST_COST={time:20, stamina:0}`；`CHOOSE_BUILD` 使用 `BUILD_CHOICE_TIME=1`，
`TALK_TO_ACTOR` 使用 5 分钟。`WAIT` 没有固定 duration，而是要求正整数 `minutes`；
`REST` 默认 20 分钟，`quick_rest` 分支为 10 分钟。progression 的 resource cost
是 state gate/config mapping，不等于通用 Genesis resource economy。未来 feature 不能
通过重命名这些常数获得 `SUPPORTED`。

### 3.2 Projection 与 compiler bootstrap addenda

F-23 的固定 Projection schema 实际包括 `PROJECTION_SCHEMA_VERSION=1`、
`PROJECTION_COMPILER_ID="phase9b2a-player-projection-v1"`、13 个
`PROJECTION_DRAFT_LABEL_FIELDS`，以及 `PlayerProjectionMap` 的 schema/compiler/profile、
source WorldPack hash、source Initial State hash、content locale、world、identities 等
字段。它是当前 Presentation provenance gate，不是新 Genesis 的通用 UI schema。

F-24 之所以单独列出，是因为 WorldGen compiler 的 bootstrap、Autoplay observation 和
Campaign smoke 共同绑定当前第一条因果路径；它不是单纯的一个 action 常量。未来第二个
结构不同的 profile 必须证明新的 bootstrap、Event cardinality、actor scope 和 observation
adapter，而不能在这些既有调用点继续增加主题分支。

## 4. Highest-risk structural hardcoding

### 4.1 Core reducer 中的 gameplay logic — F-08

`src/tgn/core/reducer.py` 直接按 expedition、combat、progression、build 和 Mara Event
分支。它是当前 anti-forgery boundary，不能因为 Genesis 目标就被削弱；风险在于未来
若继续加入 `elif`，Core 会成为所有新主题和能力的耦合点。

### 4.2 Core invariants 中的 gameplay invariants — F-09

`src/tgn/core/invariants.py` 不仅检查核心完整性，也认识 phase cycle、expedition、
progression、build 和 Mara。未来应通过 feature-local validation seam 逐步隔离，但必须
以新的 superseding contract 证明旧 Replay 和 corruption detection 不变。

### 4.3 Generic layers 直接导入 expedition — F-13–F-16

Autoplay、Session、Campaign 和 Story reconstruction 直接使用 expedition 的 observation、
execution、Mara metrics 或固定 action-id 结构。这些路径当前是合法的冻结 vertical slice，
但不是可自动扩展的通用 runtime adapter。

### 4.4 Single WorldGen profile — F-01/F-02/F-12

当前 `phase75_expedition_v1` 让不同题材可以换 public labels，但不会换地点图、资源循环、
生存压力或核心行动。它必须作为 legacy profile 保留，不能被写成“Genesis 已支持任意世界”。

### 4.5 Fixed presentation action schema — F-11

即使 Engine 未来接受一个新 Action，当前 Projection presenter 仍可能因固定参数 schema
而拒绝它。新 Action 必须使用 versioned presentation contract；不能静默放宽 PC1/Phase 9B2A
冻结 schema。

## 5. 保留的 Kernel

以下内容表达的是引擎完整性，而不是题材，应保留并作为 Genesis 的底座：

- GameState metadata shell、DomainEvent provenance；
- canonical JSON、state hash、artifact hash；
- EventStore、Snapshot、Replay、Verify、corruption detection；
- RecordedDecision 记录与回放；
- Campaign publication/sealing、Story persistence、commit-before-print；
- public/private observation 与 Knowledge Boundary；
- PC1 frozen client boundary、旧 bundle compatibility 和 freeze-tag immutability。

存在这些基础设施不代表 Genesis 层级已经实现；它们只提供未来可依赖的确定性底座。

## 6. Legacy runtime profile

以下内容是第一条已验证垂直切片，应保留为明确的 profile：

- `phase75_expedition_v1`；
- fixed base/target、DROP/SEARCH/EXTRACT、target searched；
- `salvage`/parts、Day/Night、fixed costs、three build choices；
- Mara actor、单一 world fact、relationship/knowledge slice；
- 当前 bootstrap 和 `DROP → SEARCH → EXTRACT → TALK_TO_ACTOR` smoke；
- Phase 9B1 compiler identity `phase9b-bounded-world-v1` 及旧 bundle verify path。

这些不是错误历史。它们是当前可以回归、hash、Replay 和审计的 bounded profile；错误在
于把它们提升为所有 Genesis 世界的宇宙规则。

## 7. Generic layer leaks and future superseding boundaries

未来应按真实压力逐项建立，而不是一次性建立万能框架：

| 现有压力 | 建议 superseding boundary | 本轮动作 |
|---|---|---|
| Core reducer 认识具体 Event | versioned feature-local event handler seam | 只记录，不改 reducer |
| Core invariants 认识 expedition/build/Mara | feature-local validation/invariant boundary | 只记录，不迁移 |
| Projection 固定 action schema | Presentation v2 / action schema version | 保留 frozen schema |
| Autoplay 直接导入 expedition | Autoplay adapter v2 | 保留当前 runner |
| Session/Campaign 直接绑定 expedition | versioned gameplay adapter/artifact verifier | 不修改 frozen service |
| Story reconstruction 直接重建 expedition observation | Story Context v2 | 不改变现有 Story contract |
| WorldGen 只有一个 profile | WorldGen v2 + second structurally different profile | 不添加第二 profile |
| World Draft 只有 labels | Blueprint/WorldPack v2 | Phase 10A 不实现 |
| Genesis Request 没有 seed | new Genesis Request envelope | 不修改 v1 model |
| bundle/compiler identity 迁移 | new compiler identity/migration contract | 旧 identity 不动 |
| PC1 只有固定 choice schema | PC2/new milestone | 不修改 `src/tgn/play/**` |

## 8. 不应立即重构的部分

- 不因为发现固定值就修改 Phase 1–9 或 PC1；冻结边界优先于清理冲动。
- 不把现有 `build_choice.py` 改成 SkillTree、EffectSystem 或 capability registry。
- 不把 Mara 立即升级成通用 Actor/Relationship framework。
- 不把 `phase75_expedition_v1` 改成 `if world_type` 分支集合。
- 不为未来的 Ocean、Xuanwu、Cybernetic Intrusion 预留动态 plugin/DSL。
- 不把 `compile_report.json` 误称为完整 Feature Requirement Report。
- 不把 `progression.py` 的 cost mapping helper 误称为 Habitat 或专属资源机制。
- 不通过 narration prose 补齐 missing State/Event/Reducer。

## 9. Genesis development order suggested by this inventory

1. 先稳定 Genesis Request、Proposal、Feature Report 和严格 security boundary（10A）。
2. 再定义 Blueprint、World Bible、hidden/public、Story Engine 的候选结构（10B）。
3. 选择一个真实已实现语义，建立新 compiler identity、binding、WorldPack seal 和初始
   state verify（10C）。
4. 用静态检查和确定性短程 preflight 发现不可玩、死锁和 WAIT 耗尽（10D）。
5. 做至少两个结构上不同的 Prompt/WorldPack end-to-end proof，验证不是 label 换皮
   且不破坏旧 PC1/旧 bundle（10E）。
6. 只有在第二个真实 profile 证明共享因果结构以后，才考虑 feature-local migration、
   runtime profile boundary 或 Capability Foundation。

## 10. Acceptance boundary for future reviewers

未来任何声称“Genesis 支持一个机制”的实现都必须回答：

- 机制的 stable Feature ID 和 contract version 是什么？
- 状态在哪里？合法 Action、Event、Reducer、Invariant、Projection、测试和 Replay 在哪里？
- WorldPack compiler 能否 binding？Campaign 能否创建和恢复？
- 玩家看到的 degraded/unsupported 语义是什么？是否需要 acknowledgement？
- Narrator 是否只能表达已提交事实？
- 失败是否无 Campaign/State/Event 副作用？
- 第二个结构不同的 profile 会挑战哪两个假设？

如果只能回答“有一个 helper”“有一个 label”“Narrator 可以描述”或“未来会实现”，
则不能标为 `SUPPORTED`。

## 11. Boundary conclusion

当前硬编码的正确处理不是全部消除，而是分层：

```text
保留 Kernel
    +
保留并命名 legacy first-slice profile
    +
记录 generic layer leaks
    +
用新的 superseding contracts 承载真实新需求
```

本轮只建立这一审计和文档边界；不得修改最高风险代码，也不得开始 Phase 10A、10B
或后续实现。
