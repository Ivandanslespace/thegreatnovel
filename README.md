# 小说作者辅助与续写系统

这是一个依据 `Novel_Authoring_System_Constitution_V2.md` 构建的本地、CLI 优先、Codex 驱动小说续写系统。所有新书和新运行产物都从 Book Library 开始，集中写入 `library/<book_id>/`；旧 `workspace/<book_id>/` 仅作为 legacy 读取和迁移输入，不再是新流程的默认写入位置。系统把“读取长篇原文、规划下一章、生成草稿、校验、作者批准”拆成可追溯的文件合同和事件状态，而不是让模型直接改小说。

Python 负责不可变原文、SQLite/FTS5、确定性指标、硬门、候选/合同、十项校验、批准事务、快照与重建；Codex 桌面端通过 `library/<book_id>/editions/<edition_id>/operations/<operation_id>` 文件合同读写任务。运行时不要求 OpenAI API Key。

CLI package boundary 已建立：入口位于 `src/novel_authoring/cli/`，`legacy.py` 仍是冻结的兼容实现，根 `cli.py` 仅保留兼容 facade。本轮不声称 CLI 已完全模块化；后续领域拆分不是本次验收前提。

Metric Observatory V2 增加严格指标注册表、缺失值/来源观察、段落证据和本地 Author Workbench。Workbench 使用 Local File Handoff Protocol：用户在 Windows Codex 桌面端手动复制指令并领取任务；Web 不调用 OpenAI API、不使用 Codex CLI 或 `codex exec`，也不启动 Codex 子进程。批准正史、改写 Campaign 与 Edition 激活仍须作者显式执行。

最重要的边界：`book/` 永久只读；草稿不会自动成为正史；只有精确确认“批准写入正史”才能提交。

## 新书主流程：Book Library first

不要先运行旧的 `novel init`/`novel ingest`。从一个文件或来源目录建立完整 canonical 书库：

```powershell
$Novel = ".\\.venv\\Scripts\\novel.exe"
& $Novel library add `
  --book-id my-book `
  --title "我的小说" `
  --source ".\\book\\我的小说.md" `
  --initialize-mode deferred
```

`library add` 会复制只读来源、核对复制前后 SHA-256、建立 `_system/state.sqlite3` 和 FTS、切分章节/Source Spans、生成 `_system/source_manifest.json`、`book.yaml`、README 和 `base` edition，并标记 `NEEDS_INITIALIZATION`。多文件来源先返回待确认计划，确认后补充 `--confirm-order`。随后可从下列入口继续：

```powershell
& $Novel library paths --book-id my-book
& $Novel initialize create --book-id my-book --library-root .\\library
& $Novel distill prepare --book-id my-book --library-root .\\library
& $Novel distill create --book-id my-book --library-root .\\library
& $Novel web serve --book-id my-book --library-root .\\library
& $Novel atlas export-snapshot --book-id my-book --library-root .\\library
```

Web 的“导入新书”与 `library add` 共用同一个 storage service，不会只复制文件而留下未初始化的书库。

## distill-novels 写作知识库

系统接入 [CloudLiu1008/distill-novels](https://github.com/CloudLiu1008/distill-novels) 作为
Codex 桌面端的语义提炼能力。`novel distill prepare` 只做可复现的格式归一化、章节边界、
source manifest 和 bounded index；`novel distill create` 冻结输入并创建 `NOVEL_DISTILLATION`
handoff。桌面端领取后调用 `$distill-novels`，把结果写入 handoff 的
`artifacts/distill_skill/`，再由作者显式运行：

```powershell
& $Novel distill import --book-id my-book --handoff-id <handoff-id> --library-root .\\library
```

发布结果进入 `library/<book_id>/editions/<edition_id>/analysis/distill/skills/`，在后续续写
handoff 中以带 Scope 和 mapping summary 的 `distill_reference` 提供给 `$continue-novel`，
使用仍是 `REFERENCE_ONLY`。Distill Skill ≠ Canon ≠ Runtime State：SELF_BOOK 可以作为当前
小说的软理解层，EXTERNAL_REFERENCE 只能提供抽象机制、Craft Control 和中性风格变量，
COMPARATIVE_REFERENCE 只能消费 synthesis、transferable_principle、craft_control。它不会
修改 `book/`、Story Atlas、Canon、Edition 激活状态或作者批准状态。支持 `analyze-only`、
`create`、`compare`、`update` 模式，以及 `worldbuilding`、`characters`、`plot`、`style`、
`narrative`、`dialogue`、`pacing`、`themes`、`continuity` 九个维度。

导入时 Python 会把 Markdown Finding 编译成版本化 Distillation Package：

```text
analysis/distill/skills/<distill_id>/
├─ SKILL.md / distillation-report.md / <selected-dimension>.md
└─ machine/
   ├─ package.json
   ├─ observations.jsonl
   ├─ evidence_mappings.jsonl
   ├─ literary_arcs.json
   ├─ craft_controls.json
   ├─ continuity_candidates.jsonl
   ├─ character_voice_profiles.json
   └─ theme_questions.json
```

只有实际产生的 machine artifact 才会创建。`novel distill validate` 执行严格维度、来源、
Scope、内部引用、原创性和 Pydantic 合同检查；`novel distill map-evidence` 只按冻结
preparation 重新映射到当前 Edition 的 chapter/source span；`novel distill inspect` 输出
作者摘要；`novel distill export-profile` 会把最新 SELF_BOOK Package 原子导出到
`library/<book_id>/book_profil/`，外部参考不会覆盖它。Literary Arc 是 Distill 的文学结构观察，
不是 Initialization Processing Arc。

Phase 3 还提供独立的 Source-Derived Runtime Baseline：

```powershell
& $Novel runtime-baseline build --book-id my-book --input .\baseline-input.json --boundary-chapter 50
& $Novel runtime-baseline inspect --book-id my-book
```

Baseline 位于 `editions/<edition_id>/analysis/runtime_baseline/versions/`，只保存经过
selected Edition source evidence 验证的 `SOURCE_VERIFIED` / `SOURCE_PARTIAL` 条目；无法确认的
内容保持 `UNKNOWN`。`Earned Surface` 和 `Available Payoff Surface` 只由 Baseline 与当前
Canon Projection 派生，Distill Observation 只能提供检索/验证提示，不能直接产生能力、物品或
资源。候选规划、草稿和十项校验通过 Context Router 分别读取 hard boundary、earned/payoff
surface 与对应九维软控制。

## 能力

- UTF-8、UTF-8-SIG、GB18030 与中文 Windows 路径；
- 中文章节切分、来源行号/字符偏移、SHA-256、幂等导入和 FTS5 trigram；
- 六种信息状态、append-only 哈希事件链、Canon Projection、快照与确定性重建；
- Codex `input.md + schema.json + task.json → output.json` 文件合同；
- Pressure、Narrative Debt、Progress、Payoff、Repetition Fatigue、Risk Credibility；
- 三条优先线程、恰好三个结构候选、Continuation Boundary Packet 与 Chapter Contract；
- DRAFT → VALIDATED → AUTHOR_APPROVED → CANON_COMMITTED；
- 十项生成后校验、重大兑现的四类 Aftershock Obligations、审计导出。
- edition-aware `chapter_features`、长跨度节奏快照与 `HOLD/ADVANCE/RESOLVE/OVERDUE` 伏笔动作队列；
- 版本化改写的 edition 物化隔离、Variant source span/FTS、Campaign 锚点与 r1/r2/r3 草稿审计。
- Migration 8 的 provenance-aware `metric_runs`、`metric_observations`、段落 `chapter_segments`、Planning Aggregate、严格 `workflow_handoffs`、`WAITING_FOR_USER`、版本化 Soft Story Atlas 与 Batch Provisional Projection；默认本地 Web 入口为 `novel web serve`。

## Windows 安装

要求 Python 3.11+。本项目位于中文路径时，推荐普通 wheel 安装；不要使用 editable 模式：

```powershell
cd "C:\dev\小说续写系统"
uv sync --python "C:\Users\jingx\anaconda3\python.exe" --extra dev --no-editable --reinstall-package novel-authoring-system
.\.venv\Scripts\novel.exe --help
```

没有 `uv` 时：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[dev]"
.\.venv\Scripts\novel.exe --help
```

详见 `docs/WINDOWS_QUICKSTART.md`。

## 兼容旧工作流（legacy）

以下命令保留用于读取和处理旧 workspace；检测到 canonical Book Library 时应优先改用 `library add` 或显式 `--library-root`。旧 workspace 不得作为新书运行产物的默认目标。

以下命令均在项目根运行：

```powershell
$Novel = ".\.venv\Scripts\novel.exe"
$BookId = "my-book"

& $Novel init --book-id $BookId --title "我的小说" --source-dir .\book
& $Novel ingest --book-id $BookId --title "我的小说" --source-dir .\book
& $Novel source verify --book-id $BookId
& $Novel status --book-id $BookId
```

多文件顺序存在歧义时，导入会失败并生成 manifest；人工核对后使用 `--manifest <path> --confirm-order`。系统不会按异常章号静默重排，而以来源顺序建立稳定 ordinal。

## 结构化抽取与正史整理

```powershell
& $Novel extract prepare --book-id $BookId --chapter-start 1 --chapter-end 10
```

命令返回 task ID、输入、Schema 和预期输出路径。让 Codex严格按 Schema 写 `output.json` 后：

```powershell
& $Novel extract import --book-id $BookId --task-id <task-id>
& $Novel reconcile --book-id $BookId
& $Novel reconcile --book-id $BookId --fact-id <fact-id> --decision accept-source --reason "原文直接陈述"
& $Novel reconcile --book-id $BookId --record-type timeline --record-id <timeline-id> --decision accept-source --reason "原文直接建立顺序"
```

抽取结果默认只能是 INFERENCE/PROSE_ONLY；事实和其他结构记录只有显式 reconcile 才能成为 CANON。知识边要求其引用的 fact 先成为 CANON。

## Codex 续写下一章

未来对 Codex 说“续写下一章”时，应使用项目内 `.agents/skills/continue-novel/SKILL.md`。手工等价流程如下。

如果用户给了具体要求，先持久化：

```powershell
& $Novel directive add --book-id $BookId --type requirement --scope next_chapter --content "下一章必须由主角主动选择"
& $Novel directive add --book-id $BookId --type forbidden --scope next_chapter --content "不得用普通宝箱制造暴富"
```

建立边界、诊断和候选任务：

```powershell
& $Novel boundary build --book-id $BookId
& $Novel features rebuild --book-id $BookId --edition-id base
& $Novel rhythm diagnose --book-id $BookId --edition-id base
& $Novel hooks diagnose --book-id $BookId --edition-id base
& $Novel diagnose --book-id $BookId --input ".\library\$BookId\editions\base\analysis\metrics\metric_inputs.json"
& $Novel plan-next --book-id $BookId
```

`plan-next` 返回候选 task 的 `input.md`、`schema.json` 和 `expected_output`。Codex 写出恰好三个结构不同候选后导入：

```powershell
& $Novel plan-next --book-id $BookId --task-id <candidate-task-id>
& $Novel contract build --book-id $BookId --candidate-id <selected-candidate-id>
```

默认选中通过硬门且综合评分最高的候选，另外两个候选及淘汰原因仍保存在数据库和任务输出中。

## 草稿与十项校验

```powershell
& $Novel draft prepare --book-id $BookId --contract-id <contract-id>
```

Codex 依据 Boundary Packet、Chapter Contract 与 `schema.json` 写正文 `output.json`，然后：

```powershell
& $Novel draft import --book-id $BookId --task-id <draft-task-id>
& $Novel draft validate --book-id $BookId --draft-id <draft-id>
& $Novel draft show --book-id $BookId --draft-id <draft-id>
```

系统固定运行：Canon、Timeline、Knowledge、Character、Economy / Power、Contract、Debt、Payoff、Repetition、Style Validator。任何 ERROR/FATAL 都阻止 VALIDATED。失败后按报告生成新 revision；最多两轮修订。

未批准草稿可拒绝且不改变正史：

```powershell
& $Novel draft discard --book-id $BookId --draft-id <draft-id>
```

## 批准写入正史

批准命令会先输出变更预览，并重新运行十项校验、源文件哈希与 Boundary 漂移检查。确认语必须逐字匹配：

```powershell
& $Novel approve --book-id $BookId --draft-id <draft-id> --confirm "批准写入正史"
```

成功后一次事务产生 AUTHOR_APPROVED、状态变化、CANON_CHAPTER_COMMITTED、规范化查询记录、Canon Projection、Snapshot 与 `canon_commits`。重大兑现自动生成四类余波义务。原始 `book` 仍不改变，批准正文位于 `library/<book_id>/editions/<edition_id>/canon/`。

## 重建、快照与导出

```powershell
& $Novel rebuild --book-id $BookId
& $Novel snapshot --book-id $BookId
& $Novel source verify --book-id $BookId
& $Novel export --book-id $BookId
```

## Metric Observatory 与 Author Workbench

```powershell
& $Novel metrics run-chapter --book-id $BookId --chapter-id <chapter-id>
& $Novel metrics run-window --book-id $BookId --window-id current
& $Novel metrics run-promise --book-id $BookId --promise-id <promise-id>
& $Novel metrics build-planning-aggregate --book-id $BookId
& $Novel observation resolve --book-id $BookId --scope-id <scope-id> --metric-id pressure --component-id threat
& $Novel handoff list --book-id $BookId
& $Novel web doctor
& $Novel web serve --book-id $BookId --workspace workspace --host 127.0.0.1 --port 8765
```

要快速查看完整的合成纵向切片，可运行：

```powershell
& $Novel demo seed-author-workbench --workspace workspace
& $Novel web serve --book-id demo-author-workbench --workspace workspace --host 127.0.0.1 --port 8765
```

演示数据只写入指定 `workspace`，不复制真实正文、不调用 Codex/OpenAI、没有 API Key，且包含 base/derived edition、缺失/冲突/stale 指标、Rhythm 警告、过期 Promise、READY/COMPLETED handoff 和 VALIDATED Draft。

## Story Atlas 与 Batch Continuation

Story Atlas 是 edition-scoped 的软索引：Canon 仍只来自 append-only 事件与 Projection，
Atlas 文件通过 `atlas_manifest.json`、source span、版本和 hash 登记到 SQLite；登记时会
复制到 `story_atlas/versions/<atlas_id>`，已登记版本不可覆盖。Future Possibility Space
与 CURRENT/NEAR/MID/FAR Rolling Horizon 只作为审计和规划输入，不会自动批准正史。

```powershell
& $Novel atlas validate --book-id $BookId
& $Novel atlas register --book-id $BookId --artifact-root <atlas-staging-root>
& $Novel batch create --book-id $BookId --target-chapters 10 --chunk-size 5
& $Novel batch chunk-context --book-id $BookId --batch-id <batch-id> --chunk-order 1
& $Novel batch checkpoint --book-id $BookId --batch-id <batch-id>
```

Batch 按连续 chunk 推进，每章必须带 Boundary、Chapter Contract 和十项 Validator 报告；
临时结果只进入 Provisional Projection。输入 hash、Atlas 或 Horizon 漂移会将 Batch 标记
为 `STALE` 并停止继续，不会写入 Canon。详细合同见
`docs/STORY_ATLAS_WORKFLOW.md` 与 `docs/BATCH_CONTINUATION_WORKFLOW.md`。

导出目录包含 `manifest.json`、`canon_projection.json`、`audit.json` 和 `approved_canon.md`；不会复制或改写原始小说。

## 开发与验收

```powershell
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests
uv run --no-sync mypy src
uv run --no-sync novel --help
```

测试只使用合成小说和固定 agent output，不调用 Codex 或远程模型。真实 `book` 只执行扫描、导入和哈希复核，不自动生成续写。

## 版本化改写

V1.1 提供 edition-scoped 的显式改写流水线：派生版本、RevisionSpec、影响包、Revision Units、`REVISION_DRAFT` 合同、十项改写校验、chapter variants、事务提交、可回滚快照和完整 edition 导出。请先阅读 `.agents/skills/revise-novel/SKILL.md`。批准改写必须逐字输入 `批准改写版本`，启用版本必须另行逐字输入 `启用改写版本`；base 与真实 `book/` 永远不被覆盖。

长跨度节奏是独立证据层。标题/开头/结尾/功能连续补充 Repetition Fatigue，高压连续补充
Pressure Curve，Promise 的 Age/Dormancy/Readiness 补充 Narrative Debt 与 Thread Priority；
首版不增加文学总分、不改 Candidate Score 权重，同一重复问题不重复扣分。语义特征必须通过
Codex 文件合同导入并提供正文证据，无法判断就保留 UNKNOWN。

## 文档

- `docs/ARCHITECTURE.md`：组件、信任边界与事务；
- `docs/DATA_MODEL.md`：SQLite、事件、信息状态和来源；
- `docs/METRICS.md`：公式、默认权重、阈值和覆盖；
- `docs/CODEX_CONTINUATION_WORKFLOW.md`：文件合同与完整续写流程；
- `docs/WINDOWS_QUICKSTART.md`：Windows 从安装到批准；
- `PLAN.md`：实际完成状态、选择、限制和后续阶段。
