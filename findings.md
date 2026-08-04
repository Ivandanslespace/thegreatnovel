# Findings & Decisions

## Requirements

- 本地、CLI 优先、Windows 兼容、Python 3.11+、src layout。
- Codex 是 V1 的 LLM 边缘执行者；运行不要求 API Key。
- 原始 `book` 永久不可变；续写与状态只进入 `workspace`。
- 六信息状态、三续写模式、Boundary Packet、Chapter Contract 和显式批准是硬边界。
- 六项核心指标必须逐字遵守宪法公式与默认阈值，并保留可解释证据。
- 完整流程必须可事件重放、快照、校验和审计。

## Research Findings

- 最高规范 `Novel_Authoring_System_Constitution_V2.md` 为 Version 2.0，共 1,422 行，SHA-256 `C5C4E747827CC5D5529DE0C7AB4F4DD8A71B9EEC69ACDDD4CD23F6BB74208A78`。
- 根 `CONSTITUTION.md` 属于另一套 TGN 互动世界规范，不作为本系统产品宪法。
- 项目当前不是 Git 仓库；根据 `AGENTS.md`，无法 worktree 隔离时写任务必须串行。
- `book` 仅一份 Markdown：1,863,851 bytes，无 BOM UTF-8，38,500 个 CRLF 行，294 个 H2 章块。
- 真实章号包含第 0 章说明、缺 74/96、重复 37/128/224—233 和编号回退；不得按数字静默重排。
- 源文件初始 SHA-256 `95810246D1296163FC02320446060E78ADDD9FA5CBA56BBDD1292634A099EE6E`。
- Python 3.14.4 可用；另有 Anaconda Python 3.11.9。SQLite 3.50.4/3.45.3 均支持 FTS5。
- pytest 可用；Ruff、mypy/pyright 当前未安装。项目将声明 dev 依赖并使用项目本地 `.venv`。

## Constitution Formula Index

- Pressure：宪法 7.1，六项权重合计 1.0；默认区间与曲线警报见 7.2。
- Narrative Debt：宪法 8，含 AgeRatio、ReminderFactor、Debt clamp 0—150 与 hook load。
- Progress：宪法 9，六项权重、滚动检查和 StagnationRate。
- Payoff：宪法 10，M/I/C/A/N 与净爽点评分 S；资源解放见 11。
- Repetition Fatigue：宪法 12，结构相似度和 `τ=12` 时间衰减。
- Risk Credibility：宪法 13，五项权重与警报阈值。
- Character/Style Fit：宪法 16；线程与候选评分见 17—18。
- Aftershock、Chapter Contract、校验与批准见 20—24。

## Technical Decisions

| Decision | Rationale |
|---|---|
| `sqlite3` + 显式迁移 | 依赖最少、Windows 稳定、足够覆盖 V1 事件/投影/FTS5 |
| Pydantic v2 JSON Schema | 明确 Codex 文件合同并进行确定性验证 |
| Typer CLI | 子命令清晰且适合 Windows |
| YAML 配置 | 宪法要求权重、阈值和作者偏好可覆盖 |
| 原文 ordinal + raw heading | 同时保留源顺序和异常章号证据 |
| JSON payload 事件 + 投影表 | 兼顾 V1 可交付性与确定性重建，不预建万能本体 |
| 十项校验报告按 validation run 持久化 | approve 可证明使用了同一草稿、同一投影上的完整校验集合 |
| 正史批准同步事件、规范化查询表与投影 | 保留事件唯一来源，同时让下一轮线程/债务查询立即看到新状态 |
| 重大兑现自动建立四类 Promise | 把宪法 1/1—3/2—5/3—8 章余波义务变成可追踪债务 |
| 非事实抽取也必须显式 reconcile | 让时间线、人物、资源、线程、文风等不再依赖静默状态升级 |
| Boundary 用线程目标生成 trigram 查询 | 在最近原文与 Canon Projection 之外补充较早的可追溯相关片段 |
| 已消费 next-chapter 指令必须从下一包消失 | 成功 commit 中标记 CONSUMED；persistent 指令继续 ACTIVE |

## Issues Encountered

| Issue | Resolution |
|---|---|
| 目标 V2 宪法初次不存在且旧宪法不匹配 | 等待用户纠正后读取新出现的精确文件；不猜公式 |
| 项目无 Git，不能并行写 | worker 仅做只读审计，所有写入由主线程串行进行 |

## Resources

- `C:\dev\小说续写系统\Novel_Authoring_System_Constitution_V2.md`
- `C:\dev\小说续写系统\book`
- `C:\dev\小说续写系统\AGENTS.md`
- `C:\dev\小说续写系统\.codex\agents\luna-worker.toml`

## 2026-08-04 Book Library & Repository Consolidation 审计基线

- Git 预检：分支 `小说续写_codex`，HEAD `b19454471fe5c79e2982d05b01e779047fb555fc`，远程为 `https://github.com/happyivanencoding/thegreatnovel`；审计开始时仅有既存未跟踪 `audit/`，未执行清理。
- 已确认 `book/` 仅含 `.gitkeep` 与真实正文 Markdown；正文 SHA-256 为 `95810246d1296163fc02320446060e78addd9fa5cba56bbdd1292634a099ee6e`，294 章，原文只读。
- 已确认仓库 `workspace/real-book-smoke/` 为真实书 smoke 运行产物，含 294 章相关结果与约 11.6 MB SQLite，不视为可删除临时物。
- 已确认 `audit/` 是项目级继续审计包（109 个文件、约 21.75 MB），不是 book 原文或正式书库目录；保留为历史审计用户数据。
- 已发现 Temp 下至少 15 个名称含 novel/cable/real-book/snapshot 的候选目录；其中 `novel_real_book_demo_20260804` 含正式真实书演示数据库，必须迁移到 `library/cable-survival-demo` 后再处理旧位置。
- 本阶段分类原则：没有目录在迁移前可安全直接 DELETE；旧任务结构优先 `MOVE`/`ARCHIVE`，可重建静态 SVG、缓存和临时导出才可在引用审计与保留策略通过后列为 `REGENERABLE`。

## 2026-08-04 Book Library 实施收口

- canonical layout 已落地：`library/<book_id>/{book.yaml,README.md,source,_system,editions}`；真实演示书 source SHA 保持 `95810246d1296163fc02320446060e78addd9fa5cba56bbdd1292634a099ee6e`。
- 迁移后的 DB 路径已改写到 canonical root，`source_manifest.json` 也会在 atomic switch 后改写并同步 handoff manifest hash；旧 Temp source/workspace 不删除。
- Operation Workspace 新 handoff 使用 `editions/<edition>/operations/<operation_id>/{manifest,status,events,input,output,artifacts,logs}`；旧 handoff 保留兼容读取并标记 `legacy_imported`。
- Portable Snapshot 使用 JSON canonical 动态视图，章节分块写入 `data/chapters`；SVG 只保留 explicit export，`latest` 目录可直接打开且不使用 `fetch`。
- cleanup/retention 仅对 `REGENERABLE`/`ARCHIVE` 候选生成 dry-run；apply 需要精确 confirmation，并移动到可恢复 `.archive`，不自动删除 archive/latest/source/Canon/DB。
