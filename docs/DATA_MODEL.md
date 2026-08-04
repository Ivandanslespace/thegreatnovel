# 数据模型

## 标识、时间和版本

业务记录使用内容派生的稳定 ID，如 `draft_<hash>`、`event_<hash>`、`canon-commit_<hash>`。时间统一保存 UTC ISO-8601；主要表带 `version`。JSON 统一使用排序 key 的 UTF-8 表示，便于稳定哈希和重放。

SQLite schema 由 `schema_migrations` 显式升级。V1 当前迁移覆盖事件完整性、规划边界、草稿任务/投影基线和 validation run。

Migration 8 追加版本化 Story Atlas 与 Batch Provisional Projection；Migration 6 追加 `chapter_features`、`rhythm_diagnostic_snapshots`、`chapter_segments`、
`metric_observations`、`metric_evidence_links`、`metric_runs`、`metric_run_results`、
`workflow_handoffs` 和 `workflow_handoff_events`。handoff event 是任务执行日志，永不写入 Canon Event Store。

## 六种信息状态

| 状态 | 含义 | 可直接进入 Canon Projection |
|---|---|---|
| CANON | 已确认发生的正史 | 是，但事件还必须 COMMITTED |
| AUTHOR_INTENT | 作者要求或偏好 | 否 |
| APPROVED_OUTLINE | 作者批准的未来结构 | 否，未来不等于已经发生 |
| INFERENCE | 自动推断 | 否 |
| CANDIDATE | 候选方案 | 否 |
| PROSE_ONLY | 只存在于文本表达的未确认内容 | 否 |

禁止 INFERENCE/CANDIDATE/PROSE_ONLY 静默升级为 CANON。事实升级必须由带来源的 reconcile 或作者显式批准触发。

## Story Atlas 与 Batch 层

`story_atlases` 是 Atlas 的 SQLite 索引，不是软图谱内容表。每个版本记录 `atlas_id`、
`atlas_version`、`parent_atlas_id`、base event/projection/source/effective-content anchor、
registry/config/analyzer hash、`atlas_content_hash`、Horizon anchor、readiness 和 author
acceptance。相同 ID 的不同内容会被拒绝，旧版本不会被 upsert 覆盖。

Atlas artifact 位于 edition workspace 的 `story_atlas/`，图谱节点/关系至少有：

```text
stable_id + information_status + constraint_level + horizon
+ confidence + evidence.source_span_ids + lifecycle_status
```

`CANON` 必须引用当前 book/edition 可查到的真实 `source_spans`；`INFERENCE`、
`CANDIDATE` 和 `PROSE_ONLY` 不进入 Canon Projection。`FuturePossibilitySpace` 的
Active/Alternative/Wildcard/Open Design 与 `RollingHorizon` 存为版本化 YAML，FAR 不
允许逐章 ordinal。SQLite 只保存 action、usage、review queue 和版本索引。

`batch_working_projections`、`batch_chunk_states`、`batch_checkpoints` 保存冻结的 Atlas/
Horizon/hash anchor、连续 chunk、逐章 provisional state、Boundary/Contract/Validator
引用和 checkpoint；Provisional state 明确禁止 Canon commit，`BATCH_VALIDATED` 也不
改变 `events` 或任何 Canon 表。

抽取阶段的非事实结构同样通过通用 reconcile 显式处理；`accept-source` 要求 source span，`accept-author` 留下作者确认事件，`reject` 保留拒绝审计。知识边不得先于其引用的 CANON fact 被接受。

## 草稿状态机

```text
DRAFT
  ├─ validation fail ─► DRAFT (新 revision 可重试)
  ├─ discard ─────────► REJECTED
  └─ 10 validators pass
         ▼
     VALIDATED
         │ exact author confirmation
         ▼
     AUTHOR_APPROVED
         │ same approval transaction
         ▼
     CANON_COMMITTED
```

AUTHOR_APPROVED 虽在同一批准事务中迅速转为最终状态，仍由独立事件和 `approved_at` 留下可审计证据。

## 表分组

### 不可变来源

| 表 | 关键内容 |
|---|---|
| `books` | 模式、原文根、workspace 根 |
| `source_documents` | 相对路径、编码、文件 SHA-256、顺序置信度、原文/生成正史状态 |
| `chapters` | 稳定 ordinal、原始标题/章号、行/字符范围、内容哈希 |
| `source_spans` | 记录级来源、excerpt、行/字符范围与 text hash |
| `chapter_fts` | trigram FTS5 中文子串搜索 |

原始 manifest 只覆盖 `book` 输入。批准后的续章作为 `GENERATED_CANON` source document 写入 workspace，并拥有独立 chapter/source span；不会被伪装成原始文件。

### 正史和查询状态

| 表 | 内容 |
|---|---|
| `entities` | 人物、地点、组织、物品等实体 |
| `facts` | subject/predicate/object、来源、有效期、supersedes、active |
| `timeline_entries` | 故事时间、order key、并行/回忆 payload |
| `character_states` | 目标、知识、资源、关系、情绪和计划 |
| `knowledge_edges` | 哪个角色以何状态知道哪条 fact |
| `relationships` | trust、alignment、debt、fear、commitment、power delta 等 |
| `resources` | owner、类型、数量、单位与守恒证据 |
| `capabilities` | absolute/effective capacity、相对位置与限制 |
| `threads` | goal、stakes、phase、progress、依赖和 payoff 窗口 |
| `promises` | 叙事债务、年龄、提醒、目标年龄和余波义务 |
| `payoff_events` | 类型、分数、来源章节、余波期限 |
| `repetition_tags` | 来源、解决方式、爽点、场景、情绪、结尾结构 |
| `style_profiles` | POV、时态、节奏、对话率、说明密度、声音样本和禁忌 |

这些表服务当前查询；事件历史仍是批准后状态的可重放来源。批准事务同时写事件与规范化表，避免下一轮规划读到旧状态。

### 作者、规划与草稿

| 表 | 内容 |
|---|---|
| `author_directives` | requirement/forbidden/preference、next_chapter/persistent、优先级与状态 |
| `metric_results` | 分数、输入、证据、阈值解释、动作、配置哈希和公式 ID |
| `boundary_packets` | event/projection 基线、包 JSON/hash 与路径 |
| `candidate_plans` | 三候选、结构、分数、硬门、选择/淘汰原因 |
| `chapter_contracts` | 不可变变化、代价、债务、边界、commit updates 与 hash |
| `drafts` | task、文件/hash、revision、状态、Boundary 基线、validation run |
| `validation_reports` | 每个 run 的十个 validator 结果与 findings |
| `canon_commits` | draft、chapter、event range、作者确认与时间 |
| `snapshots` | through event、state hash/JSON 与文件路径 |

`next_chapter` directive 在成功 Canon Commit 中标记为 CONSUMED；persistent directive 保持 ACTIVE。

## Edition 与版本化改写

迁移 5 在不删除旧表/旧数据的前提下，为所有可变查询表加入 `edition_id`（旧记录回填 `base`），并建立以下审计表：

| 表 | 作用 |
|---|---|
| `editions` | base/派生版本、父版本、冻结的 `base_event_seq`、projection/source manifest hash 与 DRAFT/VALIDATED/ACTIVE/ARCHIVED 状态 |
| `edition_projection_metadata` | 派生 edition 的确定性投影快照；base 继续使用原 `projection_metadata` |
| `revision_campaigns` | 严格 `RevisionSpec` 的意图、范围、变更、禁改、传播规则和冻结锚点 |
| `revision_impact_packets/items` | deterministic scan 与 Codex semantic audit 的分类：MUST_REWRITE、MUST_REVIEW、INFORMATIONAL、EXPLICITLY_WAIVED |
| `revision_units` | 按章节/依赖排序的最小改写单元与 source preimage |
| `revision_drafts` | 仅 `REVISION_DRAFT` 输出、替换文件哈希、校验运行与状态 |
| `revision_validation_reports` | 十项改写校验及既有十项校验的逐项结果 |
| `chapter_variants` | 稳定 `base_chapter_id` 的完整替换文本；每个 edition+chapter 至多一个 active variant |
| `revision_commits` | 一次改写批准的事件范围、variant、投影 hash、snapshot 与作者确认 |

派生投影是“父 edition 在冻结 event seq 的投影 + 目标 edition overlay 事件”，不会把新事件或 variant 反写到 base。完整 edition 导出以 ordinal 位置替换 variant，而不是把改写章节追加到末尾。

## 事件模型

`events` 的核心字段：

| 字段 | 作用 |
|---|---|
| `event_seq` | 单调重放顺序 |
| `event_id` | 由序号、类型、aggregate、payload 派生的稳定 ID |
| `event_type` | FACT_ASSERTED、RESOURCE_SET、CANON_CHAPTER_COMMITTED 等 |
| `aggregate_type/id` | 被改变的业务对象 |
| `payload_json` / `payload_sha256` | 规范化变化与完整性 |
| `prev_event_hash` / `event_hash` | 防篡改链 |
| `status` | PENDING、COMMITTED、REJECTED |
| `information_state` | 六状态之一 |
| `source_kind/source_id` | 原文章节、Codex output、作者确认或 commit |
| `canon_commit_id` | 把一组批准事件关联到同一 commit |

投影支持 FACT、TIMELINE、CHARACTER_STATE、KNOWLEDGE、RELATIONSHIP、RESOURCE、CAPABILITY、THREAD、PROMISE、PAYOFF、REPETITION、STYLE 和 CANON_CHAPTER 事件。未知或非 CANON 事件仍推进审计序号，但不改变正史集合。

## 来源追溯

原文事实通过 `source_span_id` 回到 document/chapter/行列范围。批准草稿的每个状态事件引用该生成章节的 source span，并通过 `source_draft_id`、`canon_commit_id` 和 event range 回到：

```text
状态记录
→ event_id
→ canon_commit_id
→ draft_id / contract_id / candidate_id
→ Boundary Packet
→ 原文章节与已确认状态
```

因此可以回答事实来源、候选选择原因、当前后果的上游选择和作者批准时间。
