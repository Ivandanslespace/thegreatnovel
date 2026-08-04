# 小说作者辅助与续写系统 V1 实施计划

> 状态：V1 完成  
> 最高规范：`Novel_Authoring_System_Constitution_V2.md`（Version 2.0）  
> 运行模式：Codex 驱动的本地文件工作流；Python 不直接调用远程 LLM  
> 默认续写模式：`faithful_continuation`

## 目标

交付一个 Windows 兼容、CLI 优先、可运行、可测试、可追溯的 Python 3.11+ 系统，形成以下完整纵向路径：

```text
不可变原文导入
→ 可追溯正史与事件状态
→ 宪法指标与三个优先线程
→ 三个结构不同的候选
→ Continuation Boundary Packet
→ Chapter Contract
→ Codex 独立草稿
→ 十类校验
→ 作者显式批准
→ Canon Commit、快照与一致重建
```

## MVP 边界

V1 实现：

- `.txt` / `.md` 递归扫描、UTF-8 / UTF-8-SIG / GB18030 检测、SHA-256 与幂等导入；
- 可配置中文章节切分、来源行号和字符偏移、SQLite FTS5；
- 六种信息状态、作者指令、冲突整理、事件日志、Canon Projection、快照与重建；
- Codex `input.md + schema.json → output.json` 文件合同；
- Pressure、Payoff、Narrative Debt、Progress、Repetition Fatigue、Risk Credibility；
- Canon / Timeline / Knowledge Gate 与 Character / Style Fit；
- 三线程诊断、三候选规划、解释性评分、Boundary Packet、Chapter Contract；
- 草稿状态机 `DRAFT → VALIDATED → AUTHOR_APPROVED → CANON_COMMITTED`；
- 十类校验、显式批准、状态更新、导出与完整 CLI；
- 合成中文小说测试、端到端 fixture 流程和真实 `book` 只读 smoke test。

## 明确不做

- Web 前端、REST、微服务、云数据库、向量数据库；
- LangChain、大型通用多代理框架、递归调用 Codex；
- 运行时必需 API Key 或 Python 直接调用远程模型；
- 全自动模拟每个 NPC、预测真实读者留存、自动发布；
- 未经作者明确授权的 retcon、自动批准或自动写入正史；
- 对 `book` 原始文件的任何修改、改名、格式化或覆盖。

## 数据模型

SQLite 最小表覆盖：

`source_documents`、`chapters`、`source_spans`、`entities`、`facts`、`events`、`timeline_entries`、`character_states`、`knowledge_edges`、`relationships`、`resources`、`capabilities`、`threads`、`promises`、`payoff_events`、`repetition_tags`、`style_profiles`、`author_directives`、`candidate_plans`、`chapter_contracts`、`drafts`、`validation_reports`、`canon_commits`、`snapshots`。

关键关系：

```text
Immutable Source + Approved Change Events
→ Canon Projection
→ Chapter Planning State
```

所有关键记录使用稳定 ID、UTC 创建时间、来源、信息状态和版本；事实和状态变化必须能回指来源或批准事件。

## CLI

入口命令为 `novel`，计划支持：

- `init`、`ingest`、`status`、`source verify`；
- `extract prepare`、`extract import`、`reconcile`；
- `directive add`、`diagnose`、`plan-next`；
- `boundary build`、`contract build`；
- `draft prepare`、`draft validate`、`draft show`；
- `approve`、`snapshot`、`rebuild`、`export`。

写正史命令必须指定 `draft_id` 或 `change_id`、显示变更、执行硬校验、记录事件和快照；失败返回非零退出码。

## 里程碑

| 里程碑 | 交付 | 验收 | 状态 |
|---|---|---|---|
| M1 | 项目骨架、配置、SQLite、导入、章节切分、源文件校验 | 导入/编码/中文路径/幂等/哈希测试 | 完成 |
| M2 | 事件存储、六状态、Canon Projection、快照、重建 | 重放确定性与状态升级边界测试 | 完成 |
| M3 | Codex task packet、抽取导入、reconcile | Schema 验证、INFERENCE 不升级测试 | 完成 |
| M4 | 六指标、两个硬门、解释输出 | 宪法公式和阈值单元测试 | 完成 |
| M5 | 三线程、三候选、Boundary、Contract | 结构差异、门禁、合同生成/校验测试 | 完成 |
| M6 | 草稿、十类校验、批准、Canon Commit | 未批准不污染、冲突阻断、批准 E2E | 完成 |
| M7 | AGENTS、continue-novel skill、文档、完整验收 | pytest、Ruff、类型检查、合成 E2E、真实 book smoke | 完成 |
| M8 | edition-scoped 版本化改写、影响包、Revision Unit、chapter variant、审批/激活分离、完整导出 | migration 5、事件链隔离、事务回滚、base 不变、revision CLI/skill、全量质量门 | 完成 |

## 测试策略

- 单元测试：编码、切章、哈希、纯指标函数、门禁、状态转换；
- 集成测试：SQLite、FTS5、任务文件合同、快照/重建、CLI 退出码；
- 合成 E2E：固定 agent output fixture，从导入走到作者批准；
- 真实数据 smoke：只读扫描/导入 `book`，前后复核 SHA-256；不生成真实续写正文；
- 质量门：`pytest`、Ruff、类型检查（若启用）。

## 已知风险与处置

| 风险 | 处置 |
|---|---|
| 项目当前不是 Git 仓库，无法使用 worktree 隔离写任务 | 所有写入由主线程串行完成；worker 只做只读审计 |
| 真实小说有重复/缺失/回退章号与第 0 章说明 | 使用来源顺序作为稳定序号，保留原始章号并报告警告，不擅自重排 |
| 自动抽取并不可靠 | 只进入 INFERENCE/待审核；Schema、来源和 reconcile 强制保留 |
| 指标被误用为剧情生成器 | 指标保持纯函数和解释输出；硬门与作者批准优先 |
| 长篇上下文过大 | 章节级抽取、分层摘要、FTS5、最近章节原文和相关来源片段组合 |
| 源文件意外变更 | 导入前后及关键流程校验 SHA-256，所有输出写入 `workspace` |

## 关键选择

- 使用轻量标准库 `sqlite3` + Pydantic v2 + Typer + PyYAML；不为 V1 引入 SQLAlchemy/Alembic，迁移由显式 `schema_migrations` 管理。
- 使用 SQLite FTS5；不加入向量数据库。
- 使用事件记录和确定性投影实现重建；快照是加速与审计点，不是事实来源。
- `book` 只读；真实导入结果只写 `workspace/<book_id>`。
- 先保证一条端到端纵向路径，再扩充次要字段和文档。

## 完成记录

- 2026-08-04：完整读取 V2 宪法；完成项目树、工具链和真实 `book` 只读审计。
- 2026-08-04：真实源文件基线 SHA-256 为 `95810246D1296163FC02320446060E78ADDD9FA5CBA56BBDD1292634A099EE6E`。
- 2026-08-04：M1 完成；合成测试 11/11，通过 Ruff 与 strict mypy；真实书导入 294 个章块且哈希不变。
- 2026-08-04：Windows 中文路径下 Python 3.11 使用 `uv sync --no-editable` 普通 wheel 安装，避免 editable `.pth` 的 GBK 解码问题。
- 2026-08-04：M2 完成；事件哈希链、六状态隔离、Canon Projection、snapshot/rebuild 通过 19 项累计测试。
- 2026-08-04：M3 完成；Codex task packet、JSON Schema、来源证据验证、INFERENCE 隔离和显式 reconcile 通过累计 24 项测试。
- 2026-08-04：M4 完成；六项核心指标、资源解放、Character/Style Fit 和候选评分严格按宪法/配置实现，累计 34 项测试通过。
- 2026-08-04：M5 完成；三线程、三个结构候选、Boundary Packet 与 Chapter Contract 通过累计 37 项测试。
- 2026-08-04：M6 完成；十项校验、显式批准、正史物化、四项余波义务、snapshot/rebuild 通过累计 40 项测试。
- 2026-08-04：M7 完成；补齐 directive/export、通用 reconcile、冷却与诊断结构、FTS5 相关片段、完整文档和项目内 Skill；累计 49 项测试、Ruff、strict mypy、普通 wheel CLI 与真实书只读回归全部通过。
- 2026-08-04：M8 完成；新增 base/derived edition、冻结父锚点、edition-scoped 事件/投影/物化、RevisionSpec/Impact Packet/Plan/Unit/REVISION_DRAFT、十项改写校验、chapter variant、批准与启用分离、七文件完整 edition 导出及 `revise-novel` skill；本地质量门与合成改写 E2E 通过。

## 未实现内容

V1 约定的核心纵向路径没有占位实现：导入、抽取/整理、指标、三线程/三候选、Boundary、Contract、草稿、十项校验、显式批准、事件/投影/快照、重建与导出均已接通。

以下属于明确的 V1/V1.1 边界或后续增强，不影响本次完成状态：

- Python 不自动调用 Codex/远程模型；agent output 仍由 Codex按文件合同生成；
- 较早章节的分层摘要字段和降级警告已支持，但摘要内容需由后续抽取批次提供，V1 不伪造自动摘要；
- 通用故事事件保留确认事件和审计来源，尚未增加独立 `story_events` 读模型；
- Web 审核台、REST、云数据库、向量检索、自动发布和真实读者预测均按计划不做。
- Codex 语义影响审计仍通过文件合同导入；系统不会假装本地规则能够替代语义判断。

下一阶段最值得实现：

1. 章节/卷/篇章三级摘要任务与增量更新，让超长小说 Boundary 更紧凑；
2. 面向 reconcile、三候选和 validation diff 的本地交互审核界面；
3. 对 payoff budget/cooldown、关系图和因果链增加跨章可视化与查询。
