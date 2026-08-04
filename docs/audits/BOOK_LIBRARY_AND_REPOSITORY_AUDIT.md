# Book Library & Repository Consolidation 审计

> 审计日期：2026-08-04
> 项目根目录：`C:\dev\小说续写系统`
> GitHub：<https://github.com/happyivanencoding/thegreatnovel>
> 目标分支：`小说续写_codex`
> 基线：`b19454471fe5c79e2982d05b01e779047fb555fc`
> 最高规范：`Novel_Authoring_System_Constitution_V2.md`

## 1. 审计结论与边界

本审计在 Book Library 代码、SQLite 数据库、`book/` 正文和正式运行产物迁移前完成。业务代码、数据库内容、正文和 Temp 运行产物均未在本审计阶段修改；仅向根目录既有的 `findings.md`、`progress.md` 追加审计进度记录。当前工作树在审计开始时唯一未跟踪项为既有 `audit/`，该目录不属于本次任务生成的数据，也不删除、不移动、不提交。

本次审计不改变以下硬边界：

- `book/` 是永久只读的原始来源；不得在其中生成索引、草稿、Atlas、导出或数据库。
- Atlas、指标、节奏、Boundary、Candidate、Contract、Draft、Validation、Export 都是可追溯运行产物，不是 Canon；本任务不改变算法、公式、状态或批准边界。
- `CANON`、`INFERENCE`、`CANDIDATE`、`PROSE_ONLY` 等信息状态不因目录迁移而升级；不运行 `approve`，不产生 Canon Commit。
- 所有迁移先复制到 staging 并校验哈希、路径、SQLite 计数和来源指纹；旧 Temp 目录默认保留，`cleanup-legacy` 需要精确确认。

### 审计状态

| 项目 | 结果 |
|---|---|
| Git 分支 | `小说续写_codex`，通过 |
| 远程 | `https://github.com/happyivanencoding/thegreatnovel`，通过 |
| HEAD 基线 | `b19454471fe5c79e2982d05b01e779047fb555fc`，通过 |
| `git fetch origin` | 成功，未改写工作树 |
| 当前未跟踪项 | `audit/`，已识别为既有项目级审计用户数据 |
| `book/` 修改 | 未修改 |
| 数据库修改 | 未修改 |
| 可直接删除项 | 0；没有任何 DELETE_CANDIDATE 在迁移前达到安全门槛 |

## 2. Git 与仓库清单

审计读取了 `git ls-files` 的全部 165 个 tracked paths，并按路径前缀复核了代码、测试、文档、技能、配置、原文和运行目录。前缀统计如下：

| 路径前缀 | tracked 数量 | 处理建议 |
|---|---:|---|
| `src/` | 93 | KEEP_CORE；增加 storage facade 时保持既有公开入口兼容 |
| `tests/` | 21 | KEEP_CORE；新增迁移、路径、清理和可搬迁导出测试 |
| `docs/` | 16 | KEEP_HISTORY/KEEP_PUBLIC_API；按主题归档，不删除现有合同 |
| `.agents/` | 17 | KEEP_PUBLIC_API；技能是工作流合同，路径重构后更新引用 |
| `config/` | 2 | KEEP_CORE；不将用户数据写入配置目录 |
| `examples/` | 1 | KEEP_HISTORY；明确其是否为可重建示例 |
| `book/` | 1 个文件路径前缀 | USER_DATA/KEEP_CORE；正文只读 |
| `workspace/` | 1 个 tracked placeholder | KEEP_CORE；真实运行内容由书库迁移，不把 placeholder 当正式书库 |
| `.codex/` | 1 | KEEP_PUBLIC_API/机器配置；不纳入书库数据 |
| 根目录文件 | 12 | KEEP_CORE：`AGENTS.md`、V2 Constitution、`README.md`、`PLAN.md`、`findings.md`、`progress.md`、`task_plan.md`、`pyproject.toml`、`uv.lock`、`.gitignore` 等 |

源码内共有 82 个 Python 模块。最重要的现状入口：

- 巨型兼容 CLI：`src/novel_authoring/cli.py`；大量命令把 `Path("book")`、`Path("workspace")` 作为默认值，属于 KEEP_PUBLIC_API，后续由 storage resolver 接管默认路径。
- 数据库 schema：`src/novel_authoring/db/schema.py`；已有 `books.source_root`、`books.workspace_root`、Atlas 的 `artifact_root` 等字段，属于 KEEP_CORE/迁移兼容层。
- Atlas：`src/novel_authoring/atlas/service.py`、`models.py`、`visuals.py`、`offline.py`；保留 `novel atlas export-visuals`，将 SVG 降级为显式可重建导出。
- Web：`src/novel_authoring/web/app.py`、`routes/atlas.py`、`routes/pages.py`、`static/`、`templates/`；路径只能来自 BookLayout，禁止直接暴露任意 artifact root。
- 既有兼容 facade：`edition.py`、`editions.py`、`revision/contracts.py`、`revision/impact.py`、`revision/planning.py`、`revision/variants.py`；不要在整合时删除或重命名公开导入。

## 3. 原文、仓库运行产物和既有审计包

### `book/` 原文

| 路径 | 现状 | 分类 | 决策 |
|---|---|---|---|
| `book/.gitkeep` | 1 byte，目录占位 | KEEP_CORE/KEEP_HISTORY | 保留；不得把书库写回此目录 |
| `book/全民纜車求生，我一級一個三選一_正文全集.md` | 1,863,851 bytes，UTF-8，294 章 | USER_DATA/KEEP_CORE | 永久只读；SHA-256 `95810246d1296163fc02320446060e78addd9fa5cba56bbdd1292634a099ee6e` |

目标书 `cable-survival-demo` 的新 source 应复制到 `library/cable-survival-demo/source/`，复制后重新核验上述 SHA；不能通过移动或覆盖 `book/` 来完成迁移。

### 仓库 `workspace/real-book-smoke/`

该目录是既有真实书 smoke 运行产物，约 12,039,588 bytes、17 个目录、32 个文件，含约 11.6 MB `state.sqlite3`。目录结构已经出现 `agent_tasks/`、`agent_outputs/`、`boundaries/`、`candidates/`、`canon/`、`contracts/`、`drafts/`、`exports/`、`snapshots/`、`validation/`。数据库只读盘点为：294 chapters、295 source_spans、4 drafts、2 boundaries、1 contract、40 validation reports、64 events，且没有 Canon Commit。

分类：`USER_DATA + KEEP_HISTORY`；迁移后作为旧布局兼容样本或 archive reference 保留，不能因为新库建立就直接删除。其路径字段和文件内容会被迁移器纳入引用报告。

### `audit/`

`C:\dev\小说续写系统\audit\final_continuation_report` 共有 109 个文件、约 21.75 MB，包括报告 JSON/Markdown、证据 manifest、只读 DB、source hash、任务包、metrics、canon state、validation、环境信息和 Git 审计。`EVIDENCE_MANIFEST.json` 状态为 `VERIFIED_PASS`，`MISSING_EVIDENCE.json` 为 `WARNING`。

分类：`USER_DATA + KEEP_HISTORY`。它是项目级审计历史，不是单本书的 `library/<book_id>` 正式运行目录；保留在原位置，书库 registry 不自动索引为一本书。

## 4. Temp 已知目录清单

以下是审计时在 `C:\Users\jingx\AppData\Local\Temp` 发现的 15 个名称匹配 `novel|cable|real-book|snapshot` 的目录。大小为递归文件字节数；Temp 可能被后台进程继续写入，所以迁移器必须在 staging 前重新快照并记录清单。

| 目录 | 文件/目录 | 字节数 | 分类 | 处理 |
|---|---:|---:|---|---|
| `novel_authoring_audit_20260804` | 191 / 38 | 17,835,988 | USER_DATA/KEEP_HISTORY | 保留审计证据；不自动纳入书库 |
| `novel_authoring_audit_runtime` | 37 / 22 | 12,322,939 | USER_DATA/ARCHIVE | 保留到审计/迁移复核完成；旧 smoke runtime |
| `novel_authoring_web_demo_20260804` | 20 / 20 | 1,531,141 | ARCHIVE/REGENERABLE | Web demo 只读归档，静态文件可重建 |
| `novel_build_2e3e23b5-4023-4292-8c11-dc04ef95cb19` | 2 / 0 | 176,319 | REGENERABLE | 仅在 retention dry-run 明确列出后处理 |
| `novel_handoff_smoke_dd70b58e-f9d3-4fc6-be59-ab5c96192023` | 10 / 16 | 639,973 | ARCHIVE/REGENERABLE | handoff smoke 证据先留存 |
| `novel_metrics_obs_1bb3bd73-8a24-4088-b19f-0a1f0fb29d46` | 2 / 11 | 635,426 | REGENERABLE | 指标 smoke 可重建，默认不删 |
| `novel_metrics_smoke_d0113f04-5d60-48d2-b1c2-fa9311f2972d` | 2 / 1 | 635,426 | REGENERABLE | 指标 smoke 可重建，默认不删 |
| `novel_metrics_smoke2_f1e6c3b9-da03-4f97-8c89-359e32e3397b` | 2 / 11 | 635,426 | REGENERABLE | 指标 smoke 可重建，默认不删 |
| `novel_real_book_demo_20260804` | 1,435 / 211 | 276,156,070 | USER_DATA/MOVE | 必须迁移 `cable-survival-demo`；旧根保留并写 `legacy_locations.json` |
| `novel-authoring-demo-e2e-a03bab3f-fbaa-4e00-b1ce-22988baaeaa8` | 20 / 20 | 1,236,483 | ARCHIVE/REGENERABLE | demo DB/handoff 先保留，后续按引用报告归档 |
| `novel-authoring-demo-final-eb4924d0-d7bf-4426-95ca-09fa680f57d8` | 20 / 20 | 1,118,225 | ARCHIVE/REGENERABLE | 同上 |
| `novel-authoring-demo-final2-882b0683-c223-483f-811e-14b4507675ad` | 20 / 20 | 1,268,718 | ARCHIVE/REGENERABLE | 同上 |
| `novel-authoring-demo-final3-6a26dc1b-28c5-4fd0-810a-fc2774c41e97` | 19 / 20 | 1,088,276 | ARCHIVE/REGENERABLE | 同上 |
| `novel-authoring-demo-probe-31da42c9-22c7-4d93-8561-9cfa16c78719` | 19 / 20 | 878,778 | ARCHIVE/REGENERABLE | 同上 |
| `novel-authoring-demo-probe-7a867f9d-827b-4547-9774-67c00b7937c9` | 20 / 20 | 1,015,825 | ARCHIVE/REGENERABLE | 同上 |

Temp 目录中只有 `novel_real_book_demo_20260804` 被确认包含目标真实书的 294 章指标/Atlas/初始化产物。其余目录不能仅凭名字推断为可删除；cleanup 需要逐目录检查 DB 引用、manifest/hash 和是否为当前 Web 进程使用。

## 5. SQLite schema、路径字段和迁移对账

### 仓库 smoke DB

数据库：`workspace/real-book-smoke/state.sqlite3`，只读检查。`books` 仅一行：

```text
book_id       = real-book-smoke
source_root   = C:\dev\小说续写系统\book
workspace_root= C:\dev\小说续写系统\workspace\real-book-smoke
active_edition_id = base
```

已验证的绝对路径字段包括：

- `boundary_packets.file_path`：2 个，均指向 `workspace/real-book-smoke/boundaries/`；
- `drafts.file_path`：4 个，均指向 `workspace/real-book-smoke/drafts/`；
- `books.source_root/workspace_root`；
- `source_documents.relative_path`：正文文件名，不是绝对路径；
- `snapshots.file_path`、revision packet/draft file paths 在本 DB 中无非空行；
- `atlas` 相关表在此 DB 无行。

### Temp 真实书 DB

数据库：`C:\Users\jingx\AppData\Local\Temp\novel_real_book_demo_20260804\cable-survival-demo\state.sqlite3`，约 70,287,360 bytes，必须复制后修改副本，不能原地更新。`books` 当前值：

```text
book_id       = cable-survival-demo
source_root   = C:\Users\jingx\AppData\Local\Temp\novel_real_book_demo_20260804\_source
workspace_root= C:\Users\jingx\AppData\Local\Temp\novel_real_book_demo_20260804\cable-survival-demo
active_edition_id = base
```

非空绝对路径字段：

- `story_atlases.artifact_root`：指向 Temp `editions/base/story_atlas/versions/real-cable-survival-atlas-v1`；
- `story_atlases.manifest_path`：指向上述版本的 `atlas_manifest.json`；
- `workflow_handoffs.task_directory/prompt_path/task_manifest_path/output_schema_path/result_path/event_log_path`：均指向 Temp `editions/base/handoffs/handoff_2aab56bd3b64be32b2b3d6ca`；
- `source_documents.relative_path`：正文文件名；
- `snapshots.file_path`、revision/validation 文件路径在当前 DB 无非空行；
- `books.source_root/workspace_root` 是迁移必须改写的根字段。

迁移后的同值替换目标：

```text
source_root    -> C:\dev\小说续写系统\library\cable-survival-demo\source
workspace_root -> C:\dev\小说续写系统\library\cable-survival-demo
database       -> C:\dev\小说续写系统\library\cable-survival-demo\_system\state.sqlite3
artifact_root  -> C:\dev\小说续写系统\library\cable-survival-demo\editions\base\analysis\story_atlas\versions\real-cable-survival-atlas-v1
manifest_path  -> 上述 artifact_root\atlas_manifest.json
handoff paths  -> library\cable-survival-demo\editions\base\operations\...\(兼容导入标记)
```

不能使用字符串全局替换：迁移器必须按已知根前缀、路径字段白名单和 path containment 规则改写，并在副本上做不存在路径、跨书路径和旧 Temp 残留扫描。

### 必须保留的迁移对账计数

Temp DB 在迁移前已只读确认：

| 对象 | 计数/状态 |
|---|---:|
| `chapters` | 294 |
| `source_spans` | 295（294 章 + 前导 span） |
| `chapter_features` | 294，全部 `ACTIVE` |
| `metric_observations` | 11,760 |
| `metric_evidence_links` | 11,760 |
| `metric_runs` | 326 历史记录；306 `PROVISIONAL`、20 `INVALIDATED` |
| 最新/去重后的 provisional 章节覆盖 | 294/294 个 `as_of_chapter` |
| `metric_run_results` | 2,608（2,448 `PROVISIONAL`，160 `INCOMPLETE`） |
| `story_atlases` | 1，`READY_WITH_GAPS` |
| `workflow_handoffs` | 1，`NOVEL_INITIALIZATION/READY_FOR_CODEX` |
| Canon Commit | 0 |

验收报告必须同时显示“历史总数”和“最新章节去重覆盖”，避免把 326 条历史 run 误报成 294 条唯一章节运行。

## 6. 旧任务结构审计

本次对 17 个结构族逐一检查：`agent_tasks`、`agent_outputs`、`workflow_handoffs/handoffs`、`arc_tasks`、`arc_outputs`、`boundaries`、`candidates`、`contracts`、`drafts`、`validation`、`exports`、`story_atlas`、`visuals`、`snapshots`、`batches`、`initialization`、`metrics`。

### 已发现结构

- 仓库 `workspace/real-book-smoke/`：`agent_tasks`、`agent_outputs`、`boundaries`、`candidates`、`canon`、`contracts`、`drafts`、`exports`、`snapshots`、`validation` 共 10 类；无独立 `arc_tasks/arc_outputs` 和 `workflow_handoffs`。
- Temp 真实书根：同样有 10 类基础结构；`editions/base/` 增加 `handoffs`、`initialization`、`story_atlas`。
- Temp 真实初始化运行：增加 `arc_tasks`、`arc_outputs`、`entity_resolution`、`metrics`、`reports`、`synthesis`、`visuals`。
- 因此历史布局至少同时存在“书根任务结构”“edition handoff 结构”“初始化 Arc 结构”“Atlas 版本结构”四种并行组织方式，是本任务必须收敛但不能静默丢失的核心原因。

### 分类与目标

| 旧结构 | 当前分类 | 目标 |
|---|---|---|
| `agent_tasks/` + `agent_outputs/` | MOVE/MERGE/KEEP_HISTORY | 导入 `operations/<operation_id>/input|output`，写 `legacy_imported=true` |
| `handoffs/` 或 `workflow_handoffs` | KEEP_PUBLIC_API + MOVE | 兼容读取，新的 handoff 也写 Operation manifest/status/events |
| `initialization/arc_tasks` + `arc_outputs` | MOVE/MERGE | 放入初始化 operation 的 `input/output/artifacts`，保留 Arc IDs 和结果 hash |
| `boundaries/`、`candidates/`、`contracts/` | KEEP_CORE/MOVE | 继续受 Chapter Contract/Boundary 边界约束，按 edition/operation 归档 |
| `drafts/`、`validation/` | KEEP_CORE/MOVE | 不改变 VALIDATED 默认状态，不得进入 Canon |
| `story_atlas/versions/` | KEEP_CORE/MOVE | 继续版本化 immutable；artifact_root 只由 BookLayout 产生 |
| `visuals/*.svg` | REGENERABLE_EXPORT | 不再是注册必需 artifact；JSON 图谱为 canonical，SVG 仅 explicit export |
| `exports/`、旧 snapshot | ARCHIVE/REGENERABLE | 迁移到 `exports/latest` 和 `exports/archive`，保留最新 3 个 normal bundle |
| `snapshots/` | KEEP_HISTORY/MOVE | 若为 Canon snapshot 仍受事件重放合同保护，不能与 Portable Snapshot 混淆 |
| `batches/`、batch DB tables | KEEP_CORE/MOVE | 保留 provisional 语义，不能借整合进入 Canon |

## 7. 硬编码目录与引用风险

| 位置 | 证据 | 分类 | 风险 |
|---|---|---|---|
| `src/novel_authoring/cli.py` | 多处 `Path("book")`、`Path("workspace")`，`--artifact-root` | KEEP_PUBLIC_API + MERGE | 默认路径不一致；新增 `--library-root` 时旧命令需兼容 |
| `src/novel_authoring/db/schema.py` | `source_root`、`workspace_root`、`artifact_root` 列 | KEEP_CORE | schema 字段不能删除；加迁移/registry 只能向后兼容 |
| `src/novel_authoring/atlas/service.py` | 从 `books.workspace_root` 推导 `editions/.../story_atlas` | KEEP_CORE + PATH FACADE | 直接拼接旧结构，必须切到 BookLayout，仍保留旧路径读取 |
| `src/novel_authoring/atlas/offline.py` | `author_workbench_snapshot`、`workspace_root`、SVG 复制 | REFACTOR/KEEP_PUBLIC_API | 不能继续生成固定覆盖目录；需要 `exports/latest`、manifest、相对路径 |
| `src/novel_authoring/web/app.py`、`routes/atlas.py` | 从公开 index/artifact root 找视觉和 reports | KEEP_PUBLIC_API | 禁止把任意绝对 root 暴露给 Web；路径必须 scoped 到 BookLayout |
| `src/novel_authoring/workflows/*` | handoff、export、draft、validation path 由 workspace root 拼接 | KEEP_CORE/MOVE | 需将新写入统一 Operation，旧结构只读兼容 |
| `.agents/skills/*` | 明确 `workspace/<book_id>`、Atlas、handoff 目录合同 | KEEP_PUBLIC_API | 技能文档和实际 layout 必须同源，不能靠软链接 |
| `tests/integration/*` | 多个 Temp/`workspace` fixture 和 snapshot 断言 | KEEP_CORE | 测试应增加 layout override；不得把真实用户数据写回仓库 |
| `docs/*`、`PLAN.md` | 旧目录名、snapshot、visuals 和 workflow 分散描述 | KEEP_HISTORY/REORGANIZE | 需要把历史放 archive，PLAN 只保留当前未完成项 |

`DELETE_CANDIDATE` 当前为 0。没有任何代码、DB 表、旧目录、`.gitkeep` 或 Temp 运行产物可在本阶段安全删除：它们要么是公开兼容入口、用户数据、审计证据、Canon/指标历史，要么尚未完成 DB/path 引用证明。候选清理必须先生成 dry-run 清单、DB 引用结果、哈希清单和可恢复 archive；永久删除被安全策略禁止。

## 8. 目标布局约束（实现前冻结）

默认 library root：`C:\dev\小说续写系统\library`；CLI 可用 `--library-root` 覆盖。每本书的 canonical root 为 `library/<book_id>/`，并且不依赖 symlink：

```text
library/<book_id>/
├─ book.yaml
├─ README.md
├─ source/                         # 原始来源副本；只读
├─ _system/                       # 机器运行区，DB/registry/cache/logs
├─ editions/<edition_id>/
│  ├─ analysis/                    # Atlas/metrics/rhythm/initialization
│  ├─ writing/                    # boundary/candidates/contracts/drafts/validation
│  ├─ operations/<operation_id>/
│  │  ├─ manifest.json
│  │  ├─ status.json
│  │  ├─ events.jsonl
│  │  ├─ input/
│  │  ├─ output/
│  │  ├─ artifacts/
│  │  └─ logs/
│  ├─ batches/
│  ├─ canon/
│  └─ exports/
│     ├─ latest/
│     └─ archive/
```

正式迁移完成后，`cable-survival-demo` 目标为：

```text
C:\dev\小说续写系统\library\cable-survival-demo
```

`book.yaml` 必须记录 book_id、title/source filename、source SHA/size、active edition、library layout version、legacy locations、数据库相对路径和 readiness；README 必须由 registry/layout 生成，不能要求用户手工维护绝对路径。

## 9. 实现顺序与验收门

1. 先新增 `storage/models.py`、`layout.py`、`registry.py`、`migration.py`、`cleanup.py`、`retention.py`；所有新 path 经过 containment/ID 校验。
2. 增加 `novel library migrate-legacy` 的 dry-run/apply 两阶段；staging、文件 hash、DB 副本、source/path verification、snapshot/rebuild、Web doctor、atomic switch 和报告全部可追踪；默认不删除旧位置。
3. 以真实 `cable-survival-demo` 做迁移 smoke：294 chapters、11,760 observations、11,760 evidence links、294 chapter_features、唯一 provisional chapter run 覆盖 294/294、source SHA 保持不变、Canon Commit 仍为 0。
4. 统一 Operation Workspace；旧结构只读兼容并标记 `legacy_imported`，禁止重复导入、越书引用或跨 edition 写入。
5. 生成 Portable Snapshot Bundle：`exports/latest/{index.html,manifest.json,assets,data/{book.js,chapters,metrics,atlas,reports},README.txt}`；index 小、相对路径、无需 `file:// fetch`，chapters 分块，latest 固定，旧正常 bundle 只保留 3 个；没有 standalone SVG，除非显式 export。
6. Web 新增 `/library`、`/library/<book_id>/paths`、新书 import 和 latest export UI；所有路径仅来自 BookLayout。
7. 补充迁移/registry/retention/operation/portable export/Web 安全测试，再运行项目要求的 pytest、ruff、mypy、CLI help、`novel web doctor`。
8. 最终复核 `book/` 哈希、DB 对账、Git diff、远程 branch；只提交 `小说续写_codex`，不创建 PR，最后再 push。

## 10. 审计遗留项

- Temp 中有后台 Web/开发进程可能仍持有文件；迁移 apply 前需记录 PID/端口并避免覆盖正在写的旧文件。
- `novel_authoring_audit_runtime` 与 `audit/` 之间的证据关系需要在迁移报告中记录，但不应自动合并为书库数据。
- DB 中 `metric_runs` 有历史 invalidated 记录；不可为了满足“294/294”而删除历史，报告要区分历史总数、最新唯一覆盖和状态。
- 当前 Atlas `READY_WITH_GAPS`、handoff `READY_FOR_CODEX` 不能因路径迁移变为 `READY` 或完成；路径改写必须保留 readiness、hash、author_accepted 和审批边界。
- docs/skills 的目录重组需保留旧链接或增加 compatibility note；不应在代码迁移中顺手重写宪法或算法阈值。

**审计结论：可以进入实现阶段；首个实现目标是中央 BookLayout + 可回滚 legacy migration，而不是删除旧目录。**

## 11. 子代理只读复核补充

三个只读子代理分别复核了 Temp 清单、SQLite schema 和代码引用；均未写入 SQLite、未初始化数据库、未修改文件。补充证据如下：

- Temp 匹配根目录合计 15 个、1,819 个文件、450 个子目录、317,175,013 bytes；其中 13 个包含 `state.sqlite3`。嵌套的 `cable-survival-demo` 已包含在 `novel_real_book_demo_20260804` 的父目录统计中，不能重复相加。
- `novel_real_book_demo_20260804\cable-survival-demo` 的最大派生产物是约 177,234,800 bytes 的 `metric_fixed_snapshot`；它和 source/database 分开处理，属于可归档/可重建导出，不是可直接删除的用户数据。
- 两个 SQLite 库 `PRAGMA integrity_check` 均为 `ok`，外键违规均为 0；应用迁移版本来自 `schema_migrations`，不是 SQLite `user_version`。真实 Temp DB 为应用迁移 1–8，仓库 smoke DB 为 1–5。
- 真实 Temp DB 的源文件 bytes/line count 为 1,863,851/38,500；章节内容 hash 294 个、span hash 295 个；这些值必须在迁移报告中保留。两库的 `chapter_id`、`span_id` 无交集，因此禁止按主键合并或简单更新 `books` 行。
- 生产代码仍有四套物理结构：根级 `agent_tasks/agent_outputs`、edition `handoffs/`、初始化 `arc_tasks/arc_outputs`、目标 `library/.../operations`；`operations` 不能用简单批量重命名替代兼容适配。
- `candidates/` 目前由 `ingest/service.py` 预创建，现有 smoke 目录为空且未发现实际读写消费者；它是唯一低风险的未来清理候选，但本审计仍不把它列为可立即删除项：必须等迁移器确认为空、DB/CLI/tests/manifest 无引用后，只能通过 cleanup dry-run/apply 归档或删除空目录。
- `Temp`、`AppData` 外部运行路径没有从静态代码中证明“当前没有外部消费者”；因此所有 Temp 根保留为 `UNKNOWN/ARCHIVE/REGENERABLE`，绝不按名称批量删除。

据此，`DELETE_CANDIDATE` 数量仍为 0；`candidates/` 仅登记为“条件候选（未批准）”，并明确其 Git/import/CLI/test/DB/manifest 证明尚未完成。

## 12. 实施后复核（不改变原始审计结论）

审计之后才进入实现阶段。当前复核结果如下：

- `BookLayout`、registry、legacy migration、cleanup/retention 已加入 `src/novel_authoring/storage/`；
  旧位置没有被默认删除。
- 真实 `cable-survival-demo` 已位于 `C:\dev\小说续写系统\library\cable-survival-demo`；
  `book.yaml`、`README.md`、`source/`、`_system/` 和 `editions/base/` 均已生成。
- 迁移前后对账保持：294 chapters、295 source spans、294 chapter features、11,760
  observations、11,760 evidence links、326 historical metric runs、2,608 run results、
  1 Story Atlas、1 handoff、0 Canon Commit。
- source SHA-256 仍为
  `95810246d1296163fc02320446060e78addd9fa5cba56bbdd1292634a099ee6e`；SQLite
  `integrity_check=ok`、foreign key violations 为 0；DB path columns 对旧 Temp 的残留为 0。
- 新 Portable Snapshot 为 `editions/base/exports/latest/`，index 约 4.4 KB，章节分块，
  不使用 `fetch(`，无 SVG；JSON 图谱由 GraphView/TimelineView/TopologyView/DependencyView
  动态渲染。旧 Temp 根仍存在并由 `legacy_locations.json` 记录。
- cleanup dry-run 没有执行 apply；当前没有实际删除文件，`audit/`、`book/`、旧 workspace 和
  旧 Temp 均保留。
