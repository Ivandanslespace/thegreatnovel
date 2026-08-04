# Progress Log

## Session: 2026-08-04

### Phase 0: Requirements and Discovery

- **Status:** complete
- Actions taken:
  - 读取用户完整目标与 V2 宪法 1,422 行。
  - 确认项目根、目录树、非 Git 状态和代理规则。
  - 只读审计真实 `book` 的 SHA-256、编码、行尾和章节异常。
  - 只读审计 Python、pytest、SQLite FTS5、Ruff 和类型检查器状态。
  - 建立正式 `PLAN.md` 与持久执行记录。
- Files created/modified:
  - `PLAN.md`（created）
  - `task_plan.md`（created）
  - `findings.md`（created）
  - `progress.md`（created）

### Phase 1: Foundation and Ingest

- **Status:** complete
- Actions taken:
  - 建立 pyproject、src layout、配置、显式 SQLite schema migration 和 Typer CLI。
  - 实现 UTF-8/UTF-8-SIG/GB18030 检测、source manifest、可配置中文切章、来源跨度和 FTS5 trigram。
  - 实现幂等导入、导入前后 SHA-256 校验和多文件顺序阻断。
  - 使用 Python 3.11.9 项目本地 `.venv`，完成 pytest/Ruff/mypy 质量门。
  - 对真实 `book` 只读导入 294 个章块并复核哈希。
- Files created/modified:
  - `pyproject.toml`、`.gitignore`、`README.md`
  - `src/novel_authoring/**`（M1 骨架、数据库、导入、CLI）
  - `config/default.yaml`
  - `tests/fixtures/合成求生小说.md`、M1 unit/integration tests
  - `workspace/real-book-smoke/**`（只读源导入产物）

### Phase 2: Events and Canon

- **Status:** complete
- Actions taken:
  - 实现 append-only event store、payload/前序/event 哈希链和六状态字段。
  - 实现仅接受 COMMITTED + CANON 事件的确定性 Canon Projection。
  - 实现信息状态升级隔离、事件篡改检测、snapshot 文件与 rebuild CLI。
  - 累计 19 项测试通过；Ruff 和 strict mypy 通过。
- Files created/modified:
  - `src/novel_authoring/canon/**`
  - `src/novel_authoring/db/schema.py`（migration 2）
  - `tests/unit/test_canon_projection.py`
  - `tests/integration/test_snapshot_rebuild.py`

### Phase 3: Agent Contracts and Extraction

- **Status:** complete
- Actions taken:
  - 实现按 1—10 个章块生成 `input.md`、`schema.json`、`task.json`。
  - 实现 13 类结构化抽取记录、来源范围/证据验证和固定 output.json 导入。
  - 所有 Codex 记录只允许 INFERENCE/PROSE_ONLY；显式 reconcile 后才可成为 CANON。
- Files created/modified:
  - `src/novel_authoring/contracts/extraction.py`
  - `src/novel_authoring/workflows/extraction.py`
  - `tests/integration/test_extraction_contract.py`

### Phase 4: Metrics and Planning

- **Status:** complete
- Actions taken:
  - 实现六项核心指标、资源解放、重复疲劳、Character/Style Fit、ThreadNeed 与 CandidateScore。
  - 权重/阈值进入 YAML；越界/零分母显式失败；公式黄金向量测试完成。
  - 开始实现线程排序、三候选、Boundary Packet 和 Chapter Contract。
  - 完成 Top-3 线程排序、九维候选差异、硬门优先排序、Boundary/Contract 文件与数据库记录。
- Files created/modified:
  - `src/novel_authoring/metrics/**`
  - `config/default.yaml`（宪法默认指标配置）
  - `tests/unit/test_metrics.py`、`test_metric_gates.py`
  - `src/novel_authoring/planning/**`
  - `tests/integration/test_planning_contract.py`

### Phase 5: Draft, Validation and Approval

- **Status:** complete
- Actions taken:
  - 实现 draft task/output 文件合同、三次上限、草稿哈希保护与状态机。
  - 实现宪法要求的十项校验器并持久化每项报告。
  - 实现精确确认语批准、单事务事件/规范化表/投影/快照更新。
  - 重大兑现自动创建 1、3、5、8 章上限的四类 Aftershock Obligations。
  - 通过未批准隔离、正史/时间线/知识冲突阻断、批准和重建集成测试。
- Files created/modified:
  - `src/novel_authoring/drafting/**`
  - `src/novel_authoring/validation/**`
  - `src/novel_authoring/canon/materialize.py`
  - `src/novel_authoring/workflows/approval.py`
  - `src/novel_authoring/db/schema.py`（migration 3—4）
  - `tests/integration/test_draft_approval.py`

### Phase 6: Documentation and Acceptance

- **Status:** complete
- Actions taken:
  - 补齐 directive add、通用结构化 reconcile、审计 export 和完整 CLI 退出码测试。
  - 补齐同类爽点冷却、Agency/Legibility/Outcome Uncertainty 诊断与逐项候选评分证据。
  - Boundary 使用 FTS5 trigram 召回较早相关原文，并能包含刚批准的生成正史章节。
  - 完成 README、五份 docs、简洁 AGENTS 和 `continue-novel` Skill；官方 Skill 校验通过。
  - 完成固定 agent output 合成 E2E、普通 wheel CLI、全套质量门和真实 `book` 幂等只读回归。

## Test Results

| Test | Input | Expected | Actual | Status |
|---|---|---|---|---|
| 工作目录确认 | `Get-Location` | `C:\dev\小说续写系统` | 匹配 | PASS |
| V2 宪法完整性 | 行数/哈希 | 文件存在且可完整读取 | 1,422 行；SHA-256 `C5C4E747…A78` | PASS |
| book 基线哈希 | SHA-256 | 只读审计前后相同 | `95810246…EE6E` | PASS |
| SQLite FTS5 | 内存虚拟表 + MATCH | 返回命中 | Python 3.11/3.14 与 CLI 均命中 1 行 | PASS |
| M1 合成测试 | `pytest tests/unit tests/integration/test_ingest.py -q` | 全部通过 | 11 passed | PASS |
| M1 Ruff | `ruff check src tests` | 无问题 | All checks passed | PASS |
| M1 mypy | `mypy` | strict 无问题 | 13 source files success | PASS |
| 真实 book 导入 | `novel ingest` + `source verify` | 294 章且哈希不变 | 294；哈希匹配 | PASS |
| M2 累计测试 | `pytest ...` | 全部通过 | 19 passed | PASS |
| M2 Ruff | `ruff check src tests` | 无问题 | All checks passed | PASS |
| M2 mypy | `mypy` | strict 无问题 | 17 source files success | PASS |
| M3 累计测试 | `pytest -q` | 全部通过 | 24 passed | PASS |
| M4 累计测试 | `pytest -q` | 全部通过 | 34 passed | PASS |
| M4 Ruff/mypy | 质量门 | 全部通过 | 25 source files success | PASS |
| M5 累计测试 | `pytest -q` | 全部通过 | 37 passed | PASS |
| M5 Ruff/mypy | 质量门 | 全部通过 | 30 source files success | PASS |
| M6 累计测试 | `pytest -q` | 全部通过 | 40 passed | PASS |
| M6 Ruff/mypy | 质量门 | 全部通过 | 39 source files success | PASS |
| M7 最终累计测试 | `pytest -q` | 全部通过 | 49 passed | PASS |
| M7 Ruff | `ruff check src tests` | 无问题 | All checks passed | PASS |
| M7 strict mypy | `mypy src` | 无问题 | 41 source files success | PASS |
| 项目内 Skill | `quick_validate.py` | 合法 | Skill is valid! | PASS |
| 普通 wheel CLI | `uv sync --no-editable --reinstall-package` + help | 可安装、命令完整 | 安装成功，主/草稿/reconcile help 正常 | PASS |
| 最终真实 book 回归 | idempotent ingest + source verify + SHA-256 | 294 章且原文不变 | 294；`95810246…EE6E` 前后相同 | PASS |

## Error Log

| Timestamp | Error | Attempt | Resolution |
|---|---|---:|---|
| 2026-08-04 | `git status`：not a git repository | 1 | 后续先检测 `.git`，不再对本项目假定 Git/worktree 可用 |
| 2026-08-04 | 初次找不到 V2 宪法，旧 `CONSTITUTION.md` 产品不匹配 | 1 | 用户纠正后重新读取精确路径；禁止用旧文件替代 |
| 2026-08-04 | M1 测试中文 FTS 查询返回 0（10 passed, 1 failed） | 1 | 根因是 `unicode61` 中文连续词元；改用已验证的 `trigram` tokenizer |
| 2026-08-04 | 首个 trigram 内存 smoke 因 PowerShell 引号解析失败 | 1 | 使用 here-string 重新执行，查询返回 1 |
| 2026-08-04 | `uv sync` editable build 因缺失 `README.md` 失败 | 1 | 创建 README 后重新同步；不修改全局 Python 环境 |
| 2026-08-04 | Python 3.11 启动时读取 UTF-8 editable `.pth` 发生 GBK 解码错误 | 1 | 改用 `uv sync --no-editable`，普通 wheel 在中文项目路径启动成功 |
| 2026-08-04 | mypy 报已安装包缺少 `py.typed`，未进入源码检查 | 1 | 添加 PEP 561 标记并配置 `mypy_path/files` 指向 src |
| 2026-08-04 | strict mypy 报 PyYAML 缺少 stubs | 1 | 添加 `types-PyYAML` dev 依赖 |
| 2026-08-04 | Payoff 黄金向量期望 72.3，但宪法公式返回 75.1 | 1 | 发现向量把 fatigue=20 与 N=60 混用；按 `N=100-fatigue` 修正测试 |
| 2026-08-04 | Schema smoke 的 `$defs` 被 PowerShell 变量展开 | 1 | 改为检查顶层键，Schema 生成正常 |
| 2026-08-04 | 2 章与 3 章 Boundary Packet 路径发生覆盖 | 1 | Packet ID 种子加入窗口与 chapter IDs；不同包改为不同路径 |
| 2026-08-04 | 非 editable wheel 没有随新增子包自动重装，测试收集到旧包 | 1 | pytest 加 `pythonpath = ["src"]`；最终 wheel 验证仍强制重装 |
| 2026-08-04 | 普通 wheel 中默认 YAML 路径落到 `.venv\\Lib\\config` | 1 | Hatch force-include 默认 YAML 到包内并增加 fallback |
| 2026-08-04 | Windows CRLF 转换导致草稿文件哈希与导入哈希不同 | 1 | 哈希保护文件统一写 UTF-8 bytes |
| 2026-08-04 | FTS5 聚合查询中无法使用 `bm25` | 1 | 相关子查询取得 span，移除 GROUP BY 后保留 bm25 排序 |

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | V1 已完成并通过最终验收 |
| Where am I going? | 交付报告；后续可做三级摘要、审核 UI 和跨章可视化 |
| What's the goal? | 交付宪法 V2 约束下的可运行 V1 |
| What have I learned? | 见 `findings.md` |
| What have I done? | 完成 M1—M7，49 测试与全部质量门通过；真实 `book` 保持基线哈希 |
