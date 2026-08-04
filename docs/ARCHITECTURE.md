# 系统架构

## 目标与边界

系统是单机、CLI 优先的 Python 3.11+ 应用。它不运行远程 LLM SDK：Codex 通过文件任务包参与抽取、候选规划、Story Atlas 综合和正文写作，所有进入正史的变化由确定性 Python 代码校验和提交。

唯一产品规范为根目录 `Novel_Authoring_System_Constitution_V2.md`。原始 `book/` 是不可变输入，所有新派生物写入 `library/<book_id>/`；旧 `workspace/<book_id>/` 只作为 legacy 读取、迁移和历史审计输入。

## 纵向数据流

```text
book/*.txt|md
  │  scan + encoding + SHA-256 + chapter split
  ▼
Source Store (SQLite + source_manifest.json + FTS5)
  │
  ├─ Codex extraction task ──► INFERENCE / PROSE_ONLY ──► reconcile
  │
  ▼
Approved events ──► deterministic Canon Projection ──► snapshot/rebuild
  │
  ▼
metrics + top-3 threads + Continuation Boundary Packet
  │
  ├─ Versioned Soft Story Atlas
  │    ├─ Narrative DNA + Current World Model
  │    ├─ Future Possibility Space
  │    └─ Rolling Horizon (CURRENT/NEAR/MID/FAR)
  │
  ├─ Batch Provisional Projection (chunk/checkpoint)
  │
  ▼
Codex candidate task ──► exactly 3 candidates ──► hard gates + score
  │
  ▼
Chapter Contract ──► Codex draft task ──► DRAFT
  │
  ▼
10 validators ──► VALIDATED
  │ explicit author phrase only
  ▼
AUTHOR_APPROVED + state events + CANON_CHAPTER_COMMITTED
  │
  ├─ normalized query tables
  ├─ Canon Projection
  └─ Snapshot + export
```

## 组件

| 组件 | 位置 | 职责 |
|---|---|---|
| CLI | `src/novel_authoring/cli/` | 分域 Typer 命令、参数与非零失败码；根 `cli.py` 仅为 deprecated facade |
| 配置 | `config/default.yaml`、`config.py` | 宪法权重、阈值、编码和切章正则 |
| 数据库 | `db/schema.py`、`db/database.py` | SQLite schema、迁移、事务连接 |
| 不可变导入 | `ingest/` | manifest、编码、切章、来源跨度、FTS5、哈希复核 |
| 事件与投影 | `canon/` | append-only 哈希链、CANON 过滤、确定性重建、查询表物化 |
| Codex 合同 | `contracts/` | Pydantic output 模型和 JSON Schema |
| 抽取整理 | `workflows/extraction.py` | task packet、来源证据验证、隔离导入、事实 reconcile |
| 指标 | `metrics/` | 纯公式、硬门、证据化结果持久化 |
| 规划 | `planning/` | 线程排序、Boundary、三候选差异、Chapter Contract |
| Story Atlas | `atlas/` + `library/.../analysis/story_atlas/` | 版本化软理解、图谱、Narrative DNA、未来可能性、Readiness 与 Horizon hash |
| Batch | `planning/batch.py` + `batch_*` 表 | chunk 计划、临时 projection、逐章十项校验和 checkpoint |
| 草稿 | `drafting/` | 正文任务、导入、哈希、revision 和状态 |
| 校验 | `validation/` | 十项报告、validation run 与 VALIDATED 状态 |
| 批准 | `workflows/approval.py` | 明确确认、漂移校验、事务 Canon Commit、余波义务 |
| 导出 | `workflows/exporting.py` | 投影、审计、批准正文与 source verify manifest |

## 信任边界

### 不可信或待审核

- Codex `output.json`；
- 自动抽取的 INFERENCE/PROSE_ONLY；
- 三个 CANDIDATE 计划；
- DRAFT 正文；
- 尚未 reconcile 的冲突记录。
- Story Atlas 的 `INFERENCE`、`CANDIDATE`、`PROSE_ONLY`、FAR possibility 和 Batch Provisional Projection。

这些内容可以持久化，但不能被 Canon Projection 当作正史。

### 可进入正史

- 带合法 `source_span_id` 且经显式 source reconcile 的原文事实；
- 作者显式批准的 VALIDATED draft；
- `explicit_revision` 模式下有修订来源和作者批准的更正事件。

Canon Projection 只应用 `status=COMMITTED` 且 `information_state=CANON` 的受支持事件。

Story Atlas 的 CANON 节点/关系必须引用真实 `source_span`；SQLite 只登记 Atlas 版本、
hash、anchor、usage、author action 和 review queue，软图谱文件不物化为 Canon 表。Atlas
版本不可覆盖，作者接受 Atlas 不会产生 Canon Commit。

## Codex 文件合同

每个边缘任务使用独立的 Operation Workspace：

```text
library/<book_id>/
└─ editions/<edition_id>/operations/<operation_id>/
   ├─ input/       # task.json、prompt.md、schema/context
   ├─ output/      # Codex output.json 或 result.json
   ├─ artifacts/
   ├─ logs/
   ├─ manifest.json
   ├─ status.json
   └─ events.jsonl
```

`task.json` 固定 book、章节/合同、来源哈希、Boundary 投影哈希和 Schema 哈希。导入器使用 Pydantic `extra=forbid`，拒绝未知字段、任务 ID 错配、非法来源和缺失证据。

Boundary 组合最近章节原文、已有分层摘要、Canon Projection，以及用前三线程目标生成的 trigram 查询所命中的较早原文片段。若早期摘要尚未建立，包会明确发出 warning，而不是伪造摘要。

## 批准事务

`approve` 在提交前重新运行十项校验，并验证：

1. 确认语精确等于“批准写入正史”；
2. draft 状态为 VALIDATED，文件 SHA-256 未改变；
3. 原始 source manifest 全部匹配；
4. 当前 event sequence 与 projection hash 等于 Chapter Contract 的 Boundary；
5. 没有同 draft 的既有 canon commit。

随后在一个 SQLite `BEGIN IMMEDIATE` 事务中创建 GENERATED_CANON 文档/章节/跨度、AUTHOR_APPROVED、所有状态事件、规范化查询记录、CANON_CHAPTER_COMMITTED、canon_commit、投影元数据、snapshot 记录和最终状态。重大 payoff 额外建立四条 Promise。事务失败时数据库回滚，函数清理本次精确生成的 canon/snapshot 文件。

## 重放与完整性

每个事件记录：

- 单调 `event_seq`；
- 规范化 JSON 的 `payload_sha256`；
- `prev_event_hash`；
- 事件头与 payload 合成的 `event_hash`；
- 来源、信息状态和可选 `canon_commit_id`。

`rebuild` 从第一个事件重新验证序列与哈希链，并只应用合法 CANON 事件。快照是审计/加速产物，不是独立事实来源；重建结果必须与快照 `state_sha256` 一致。

## Book Library layout

```text
library/<book_id>/
├─ _system/state.sqlite3
├─ _system/source_manifest.json
├─ source/               # COPY_READ_ONLY 原文
├─ editions/<edition_id>/
│  ├─ analysis/          # initialization、metrics、rhythm、Story Atlas
│  ├─ writing/           # boundaries、contracts、drafts、validation、revisions
│  ├─ operations/        # 所有 Codex/分析任务的输入、输出和审计日志
│  ├─ canon/             # 仅作者批准后的续章
│  ├─ batches/           # frozen plans and provisional checkpoints
│  └─ exports/           # latest + archive portable snapshots
└─ book.yaml / README.md
```

## Edition-scoped 改写架构

版本化改写沿用 V1 的 append-only 事件与确定性投影，但把可变状态和事件 overlay 绑定到 `edition_id`。`base` 是迁移时自动补齐且永不归档的只读基线；派生 edition 记录父版本及冻结 `base_event_seq/base_projection_hash/source_manifest_sha256`。重放派生版本时先重放父版本冻结前的事件，再按全局事件序叠加目标 edition 事件。

改写流水线为：`RevisionSpec → Impact Packet（规则扫描 + Codex 语义审计）→ Revision Plan/Units → REVISION_DRAFT → 十项改写校验 + 既有十项审计 → 作者批准 → chapter_variants/revision commit/snapshot`。批准事务失败会回滚数据库和本次创建的文件；`批准改写版本` 只提交目标版本，`启用改写版本` 才切换 books.active_edition_id，二者不合并。

## V1 有意不做

云数据库、向量数据库、LangChain、递归多代理、运行时 API Key、自动发布、无批准 retcon，以及对真实读者留存的伪精确预测仍不在范围内。Phase E 仅增加绑定本机的 FastAPI Author Workbench；Phase F 通过本地文件交接让 Windows Codex 桌面端手动执行，Web 不启动模型进程。
