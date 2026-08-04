# Task Plan: 小说作者辅助与续写系统 V1

## Final Hardening 当前任务

基线：`d69ce8af69a0a9de34c0e867cc9262080432b51c`；唯一分支：`小说续写_codex`。
本轮只修复 Book Library 的路径、导入、导出、Operation Workspace、SVG 可选化、清理与
代码结构矛盾；不增加指标、Atlas、续写算法或 Web 新产品功能，不修改 `book/`、Canon、
Observation、Evidence 或旧 Temp/audit 用户数据。

### Hardening 验收清单

- [x] AGENTS/README 统一为 library-first；明确禁止新分支/worktree
- [x] `novel library add` 完整一步式导入；`import` 为 deprecated alias；Web 共用 service
- [x] 所有新写入入口经 BookLayout；旧 workspace/agent_tasks/agent_outputs 仅兼容读取
- [x] extraction/metrics/features/initialization/atlas/continuation/revision/batch 统一 Operation Workspace
- [x] SVG 不再是 Atlas required artifact；显式静态图导出仍可用
- [x] Portable Snapshot 使用 script 注册、分块数据、无 fetch、manifest hashes
- [x] legacy_locations 新 Schema、兼容升级、cleanup 安全测试
- [x] existing target 永不 rmtree；默认拒绝或显式 merge/归档确认
- [x] `_system/source_manifest.json` 成为唯一权威，根镜像带兼容标记且 hash 一致
- [x] CLI 拆分 facade；DB migration 每个 SQL 独立模块
- [ ] Hardening 测试、真实书验收、质量门、直接 push 和完成邮件

## Goal

严格依据 `Novel_Authoring_System_Constitution_V2.md`，交付可安装、可测试、可追溯且不修改 `book` 原文的 Codex 驱动本地续写系统 V1。

## Current Phase

Book Library & Repository Consolidation 收口：代码与真实演示书已迁移，正在进行最终质量门、
Git diff、分支 push 和完成邮件；不改变 V2 宪法、指标、Atlas、Canon 或批准边界。

## Current Acceptance Checklist

- [x] Git/security preflight 与全量只读审计文档
- [x] BookLayout、registry、book.yaml、README 和 `--library-root`
- [x] legacy dry-run/apply、staging/hash/DB/path/source verification、atomic switch
- [x] 真实 `cable-survival-demo` 迁移、旧位置保留和 `_system/legacy_locations.json`
- [x] canonical Operation Workspace、legacy compatibility、Portable Snapshot latest
- [x] `/library`、paths、import、latest export Web surface
- [x] retention/cleanup dry-run、精确 confirmation、可恢复 archive
- [ ] 普通 wheel 重装、全量测试和最终 diff/branch/push

## Phases

### Phase 0: Requirements & Discovery

- [x] 完整读取 V2 宪法
- [x] 盘点项目树、代理规则和工具链
- [x] 记录真实 `book` 初始哈希、编码与章节风险
- **Status:** complete

### Phase 1: Foundation and Ingest

- [x] 建立 src-layout、pyproject、配置和迁移
- [x] 实现源扫描、manifest、编码检测和章节切分
- [x] 实现 SQLite/FTS5、幂等导入和哈希校验
- [x] 通过 M1 测试
- **Status:** complete

### Phase 2: Events and Canon

- [x] 实现六状态、事件、投影、快照和重建
- [x] 通过状态/重放测试
- **Status:** complete

### Phase 3: Agent Contracts and Extraction

- [x] 实现 task packet、Schema 验证、抽取导入和 reconcile
- [x] 通过文件合同测试
- **Status:** complete

### Phase 4: Metrics and Planning

- [x] 实现六指标、硬门和解释输出
- [x] 实现优先线程、三候选、Boundary、Chapter Contract
- [x] 通过宪法公式和规划测试
- **Status:** complete

### Phase 5: Draft, Validation and Approval

- [x] 实现草稿状态机、十类校验、显式批准和 Canon Commit
- [x] 通过冲突阻断与 E2E 测试
- **Status:** complete

### Phase 6: Documentation and Acceptance

- [x] 完成 README、AGENTS、skill 与 docs
- [x] 运行全套质量门、合成 E2E 和真实 book 只读 smoke
- [x] 更新 `PLAN.md` 与最终未完成项
- **Status:** complete

## Key Questions

1. 如何以最少抽象覆盖 22 个要求表和重放关系？——使用 `sqlite3` 显式迁移、稳定 JSON payload 与小型 repository/service 边界。
2. 如何避免真实章号异常污染顺序？——以 source ordinal 排序，章号仅作为原始标签和告警证据。
3. 如何保证 Codex 不绕过正史？——所有 LLM 边缘操作均通过 task/output 文件合同和 CLI import/validate/approve 命令。

## Decisions Made

| Decision | Rationale |
|---|---|
| 写任务串行 | 项目不是 Git 仓库，无法建立安全独立 worktree |
| SQLite 标准库 + 显式版本迁移 | Windows 本地依赖更轻，仍能满足 SQLite/FTS5/可重放要求 |
| source ordinal 为章节顺序 | 真实文件包含缺号、重复号和编号回退 |
| `PLAN.md` 为正式交付计划，本文件为执行记忆 | 同时满足项目文档与持久规划技能 |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| `git status` 返回“not a git repository”并中断批量只读盘点 | 1 | 改为先检测 `.git`，确认项目非 Git 后不再执行 Git 写/状态流程 |
| 初次盘点时目标 V2 宪法文件不存在，随后用户纠正且文件出现 | 1 | 重新核验路径、哈希并完整读取 1,422 行后恢复实施 |
| FTS5 `unicode61` 无法命中连续中文中的三字子串 | 1 | 内存验证 `trigram` tokenizer 后切换索引配置 |
| 首个 trigram smoke 命令被 PowerShell 嵌套引号解析失败 | 1 | 改用 PowerShell here-string 传入 Python，验证命中 1 行 |
| `uv sync` 构建 editable 包失败：声明的 `README.md` 不存在 | 1 | 先创建真实 README 骨架，再重新同步本地环境 |
| Python 3.11 在中文路径读取 editable `.pth` 时按 GBK 解码失败 | 1 | 使用 `uv sync --no-editable` 安装普通 wheel；项目 Python 3.11 启动成功 |
| mypy 首跑指向未声明类型的已安装包 | 1 | 添加 `py.typed`，并将检查目标锁定到 `src/novel_authoring` |
| strict mypy 缺少 PyYAML 类型声明 | 1 | 将 `types-PyYAML` 加入 dev 依赖，不降低严格度 |
| Payoff 外部测试向量把疲劳 20 与新奇度 60 同时给定 | 1 | 宪法规定 `N=100-RepetitionFatigue`，修正黄金值为新奇度 80、净分 75.1 |
| Schema smoke 中 `$defs` 被 PowerShell 当变量展开 | 1 | 改查 Schema 顶层键，确认 `$defs` 正常生成 |
| 不同最近章节窗口复用了同一 Boundary Packet ID | 1 | 将窗口大小和所选 chapter IDs 纳入稳定 ID 种子，禁止覆盖不同上下文包 |
| 非 editable wheel 未因源码新增自动重装，pytest 读到旧包 | 1 | 开发测试显式配置 `pythonpath = ["src"]`，发布验证使用 `--reinstall-package` |
| wheel 中找不到项目根 `config/default.yaml` | 1 | 将默认配置作为 wheel force-include 包资源，并保留源码树 fallback |
| Windows 文本写入换行为 CRLF，导入前计算的 LF 哈希不匹配 | 1 | 受哈希保护的草稿与正史文件改为写入明确 UTF-8 bytes |
| FTS5 检索在聚合查询中调用 `bm25` 报 requested context | 1 | 去掉 GROUP BY，改用相关子查询取得 source span 后正常排序 |

## Notes

- 每个阶段结束后更新状态、测试结果和 `PLAN.md`。
- 所有 `book` 操作前后复核 SHA-256。
- 不重复失败命令；每次失败记录原因和替代方案。
