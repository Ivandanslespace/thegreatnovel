---
name: continue-novel
description: 严格依据 Novel_Authoring_System_Constitution_V2.md，在本项目中执行可审计的下一章续写工作流。用户说“续写下一章”“给我三个续写候选”“根据校验修订草稿”或“批准写入正史”时使用；覆盖状态检查、作者指令、指标、三线程/三候选、Boundary Packet、Chapter Contract、Codex 文件任务、十项校验、最多两轮修订和显式批准。不得用于绕过批准、直接编辑 book 或采用根 CONSTITUTION.md。
---

# 宪法约束小说续写

## 硬边界

1. 项目根必须包含 `Novel_Authoring_System_Constitution_V2.md`、`AGENTS.md`、`pyproject.toml` 和 `book/`。规范只认 V2 文件；根 `CONSTITUTION.md` 与本系统无关。
2. `book/` 永久只读。任何 task、output、草稿、正史续章、报告和导出只能进入 `workspace/<book_id>/`。
3. Python 不调用远程模型。Web 只创建 `workflow_handoffs` 本地文件交接；用户在 Windows Codex 桌面端手动使用 `$process-novel-handoff`，不使用 Codex CLI、`codex exec`、API Key 或 Responses API。
4. 未通过十项校验不得批准；未在当前请求中明确说“批准写入正史”不得运行 `novel approve`。
5. 不直接编辑 SQLite，不把 INFERENCE、CANDIDATE 或 PROSE_ONLY 静默升级为 CANON。
6. 一个合同最多保留初稿加两轮修订；每轮产生新 draft，不覆盖旧草稿。
7. 长跨度节奏是证据层，不是新的文学总分：功能/标题/首尾补充 Repetition Fatigue，
   高压连续补充 Pressure Curve，Age/Dormancy/Readiness 补充 Narrative Debt 与 Thread Priority。
8. 若当前 edition 有 Story Atlas，先读取其 manifest、Readiness、Current World Model、NEAR
   Horizon 和 open questions；Atlas 的 `INFERENCE`/`CANDIDATE`/`FAR` 只能作为软约束，
   不得把它们写成 CANON。Atlas hash/projection/source 漂移时重新建立 handoff。
9. Batch 续写必须改用 `$continue-novel-batch`；不可把多章要求合并成一个正文 prompt，
   每章仍必须有 Boundary、Chapter Contract 和十项校验，Batch Provisional Projection
   不得进入批准事务。

以下示例假定在项目根运行 PowerShell，并设置：

```powershell
$Novel = ".\.venv\Scripts\novel.exe"
$BookId = "<book-id>"
```

## 工作流

### 1. 定位与只读检查

先完整读取根 `AGENTS.md`，再阅读 V2 宪法第 1—6、7—18、20—24 节中与本轮有关的约束。运行：

```powershell
& $Novel status --book-id $BookId
& $Novel source verify --book-id $BookId
```

若 `source verify` 失败、`unresolved_hard_conflicts` 大于 0、事件链损坏或状态库不存在，停止续写并给出具体修复点。待审核推断不得当作正史事实使用。

### 2. 先持久化用户要求

用户若规定下一章人物、事件、禁忌、节奏或结局，先逐条写入 `author_directives`：

```powershell
& $Novel directive add --book-id $BookId --type requirement --scope next_chapter --content "<要求>"
& $Novel directive add --book-id $BookId --type forbidden --scope next_chapter --content "<禁忌>"
```

不要只把要求临时塞进提示词。长期偏好使用 `--scope persistent`。

### 3. 建立边界和诊断

正文步骤之前必须先建立边界：

```powershell
& $Novel boundary build --book-id $BookId

# 读取或重建当前 edition 的章节特征与节奏/伏笔诊断
& $Novel features rebuild --book-id $BookId --edition-id <edition-id>
& $Novel rhythm diagnose --book-id $BookId --edition-id <edition-id>
& $Novel hooks diagnose --book-id $BookId --edition-id <edition-id>
& $Novel segments rebuild --book-id $BookId --edition-id <edition-id>
& $Novel metrics rebuild --book-id $BookId --edition-id <edition-id>
```

根据边界包、当前投影和已保存指标证据，准备 `workspace/<book_id>/metric_inputs.json`，再运行：

```powershell
& $Novel diagnose --book-id $BookId
```

指标只用于诊断和解释，不得绕过 Canon、Timeline、Knowledge、Character、Economy/Power、Author 与 Style 硬门。

缺失 component 必须在 `review-novel-metrics` Skill 下以 AUTHOR_INPUT/UNKNOWN 处理；不得填 0 或 50。

如果 handoff 的 `task.json` 存在 `distill_reference`，先读取其 `skill_root/SKILL.md` 和相关
证据索引。它只提供来源可追溯的抽象写作控制，用于 `analyze`、`design`、`revise` 或 `check`；
不得搬运来源正文、人物、设定、事件或独特措辞，也不得把 reference skill 的推断升级为 Canon。

Boundary Packet 中的 `rhythm_features`、`rhythm_diagnostics` 与 `hook_diagnostics` 必须随候选任务传递。
`same_function_streak`、标题/首尾重复和高压连续只产生建议或 WARNING；`HOLD/ADVANCE/RESOLVE/OVERDUE`
用于调整线程优先级和合同约束，不得让模型自行伪造诊断结果。

### 4. 三线程与三个候选

先生成候选任务包：

```powershell
& $Novel plan-next --book-id $BookId
```

读取命令返回的 `input`、`schema` 和 `expected_output`。在 `output.json` 中必须交付恰好三个候选，并保证任意两案至少三个结构维度不同；不能只换标题或名词。然后导入：

```powershell
& $Novel plan-next --book-id $BookId --task-id <task-id>
```

保留三个候选、门禁结果、分数、未选择原因和前三优先线程。默认采用通过硬门且综合分最高的候选；分差小于 8 时明确告诉用户它们处于同一可选区间。

如果用户说“先给我候选，不要写正文”，到此停止，输出三个候选及推荐理由。

### 5. Chapter Contract

对已选候选建立合同：

```powershell
& $Novel contract build --book-id $BookId --candidate-id <selected-candidate-id>
```

复核合同含 primary/secondary functions、不可逆变化、代价、叙事债务、Canon/Knowledge/Style 边界、禁止重复、结尾状态与 commit updates。合同不完整时不写正文。

### 6. Codex 草稿文件合同

如果任务由 Workbench 准备，先读取 handoff 目录中的 `task.json`、`prompt.md`、
`metric_context.json`、`context_manifest.json` 和 `output_schema.json`，再由
`process-novel-handoff` 原子领取；Web 不启动模型进程。

```powershell
& $Novel draft prepare --book-id $BookId --contract-id <contract-id>
```

严格按任务目录的 `schema.json` 写 `expected_output` 指向的 `output.json`。正文必须让每个关键状态变化在 prose 中出现可逐字定位的短证据，并填写 contract evidence、knowledge claims、Character/Style Fit 输入、债务推进、结构标签和 payoff/aftershock 计划。导入后只允许进入 DRAFT：

```powershell
& $Novel draft import --book-id $BookId --task-id <draft-task-id>
```

### 7. 十项校验与定向修订

```powershell
& $Novel draft validate --book-id $BookId --draft-id <draft-id>
& $Novel draft show --book-id $BookId --draft-id <draft-id>
```

必须确认以下十项报告全部存在且通过：Canon、Timeline、Knowledge、Character、Economy / Power、Contract、Debt、Payoff、Repetition、Style。

若失败，只针对报告中的冲突和定位修订：再次运行 `draft prepare` 生成新 revision，写新 output，导入并重新执行全部十项校验。最多两轮修订；仍失败则停止并报告，不能降级门槛。

### 8. 停止在 VALIDATED_DRAFT

校验全部通过后，数据库状态为 `VALIDATED`；对用户把这一交付点报告为 `VALIDATED_DRAFT`。必须输出：

- 草稿绝对路径和 `draft_id`；
- 使用的候选及另外两个未选原因；
- primary/secondary chapter functions；
- 主要状态变化；
- 十项校验结果与软警告；
- 明确说明尚未写入正史。

没有当前用户的精确批准语时就在这里结束。

### 8.1 外部审计 Git 交付

所有新生成的 draft 正文都必须保留为可审计 Git 工件。完成导入和十项校验后：

1. 确认 draft 文件位于 `library/<book_id>/editions/<edition_id>/writing/drafts/`；改写 draft
   位于对应 `writing/revisions/`；历史 benchmark 兼容路径也必须保留；
2. 由于 `library/` 默认被忽略，使用精确 draft 路径执行 `git add -f`，只 stage 本次 draft 正文
   及明确需要的审计文档；不 stage `book/`、`audit/`、Canon、数据库、operations、hidden truth
   或其它运行时缓存；
3. 在当前永久分支提交并推送，最终报告提供 draft 绝对路径、commit 和远端状态。

Draft 上传不等于批准，不改变 Canon、Edition active state 或 Approval 流程。

### 9. 显式批准

只有当前用户明确说“批准写入正史”时才运行：

```powershell
& $Novel approve --book-id $BookId --draft-id <draft-id> --confirm "批准写入正史"
```

阅读命令先显示的 approval preview。命令会重新运行十项校验、复核源文件哈希和 Boundary 投影，随后以事务写入 AUTHOR_APPROVED、状态变化、CANON_CHAPTER_COMMITTED、规范化查询表、Canon Projection 和 Snapshot。重大兑现还必须产生四类 Aftershock Obligations。

提交后运行：

```powershell
& $Novel rebuild --book-id $BookId
& $Novel source verify --book-id $BookId
& $Novel export --book-id $BookId
```

确认 rebuild 与快照哈希一致、原始 `book` 哈希不变，再报告 commit、chapter、event range、snapshot 和 export 路径。

## 异常与撤销

- 未批准草稿可用 `novel draft discard --draft-id <id>` 标记为 REJECTED；这不会删除审计记录或改变投影。
- Boundary 漂移时废弃旧合同/草稿，从 boundary build 重新开始。
- 硬冲突通过 `novel reconcile` 处理；不要在 output.json 中伪造修订。
- CLI 非零退出码表示失败。保留命令输出中的具体冲突，不用笼统“重试”掩盖原因。
