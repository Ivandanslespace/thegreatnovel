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
