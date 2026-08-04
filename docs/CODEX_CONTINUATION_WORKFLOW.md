# Codex 续写工作流

本文件解释人工/自动代理如何使用 CLI 和文件合同完成下一章。Codex 的可执行操作清单位于 `.agents/skills/continue-novel/SKILL.md`。

## 三条不可跨越的线

1. 不编辑 `book/`，也不把 workspace 续章追加回原始全集。
2. 不从全书自由联想写正文；先建立 Continuation Boundary Packet，再生成 Chapter Contract。
3. 生成草稿与写入正史是不同命令。没有当前作者的精确确认语就停在 VALIDATED_DRAFT。

## 文件合同阶段

### Extraction

`extract prepare` 按 1—10 章生成任务。`input.md` 含原文块与 source span；`schema.json` 规定 13 类抽取记录；`task.json` 锁定 chapter IDs、source hashes 和 Schema hash。Codex output 只允许 INFERENCE/PROSE_ONLY。

`novel reconcile` 报告按类型列出待审核记录。事实使用 `--fact-id`；实体、故事事件、时间线、人物状态、知识、关系、资源、能力、线程、承诺、文风和重复结构使用 `--record-type/--record-id`。接受原文记录必须具有 source span；知识边还要求被引用 fact 已先成为 CANON。

### Candidate Planning

Boundary Packet 包含最近完整章节、较早摘要、按前三线程目标经 FTS5 trigram 找到的较早原文片段、Canon facts、人物状态、知识边界、线程、承诺、资源、能力、关系、近期爽点/结构、文风、作者指令和冲突警告。Candidate task 只给前三优先线程，并要求恰好三个结构不同方案。

候选的结构维度包括 event source、solution method、protagonist strategy、risk form、opportunity cost、emotional outcome、social feedback、scene topology 和 ending state。任意两案少于三个不同维度时整个 output 被拒绝。

### Drafting

Draft task 将 Boundary Packet 与不可变 Chapter Contract 一并交给 Codex。output 除正文外必须声明：

- `state_changes` 与正文逐字证据；
- `contract_evidence`；
- 人物实际使用的 knowledge claims；
- Character/Style Fit 输入和显式违反项；
- 推进/兑现的 promises、新增重大 hooks；
- structure tags；
- payoff 的来源、代价、行为变化和余波计划。

导入器只把 prose 写入 `drafts/` 并保存内容 SHA-256；不会生成正史事件。

## 推荐序列

```powershell
$Novel = ".\.venv\Scripts\novel.exe"
$BookId = "my-book"

& $Novel status --book-id $BookId
& $Novel source verify --book-id $BookId
& $Novel directive add --book-id $BookId --type requirement --content "<明确要求>"
& $Novel boundary build --book-id $BookId
& $Novel diagnose --book-id $BookId
& $Novel plan-next --book-id $BookId
# Codex 写 candidate output.json
& $Novel plan-next --book-id $BookId --task-id <candidate-task-id>
& $Novel contract build --book-id $BookId --candidate-id <candidate-id>
& $Novel draft prepare --book-id $BookId --contract-id <contract-id>
# Codex 写 draft output.json
& $Novel draft import --book-id $BookId --task-id <draft-task-id>
& $Novel draft validate --book-id $BookId --draft-id <draft-id>
& $Novel draft show --book-id $BookId --draft-id <draft-id>
```

此时停止并向作者报告。若用户只要候选，则在 candidate import 后停止。

## 十项报告

| Validator | 主要阻断内容 |
|---|---|
| Canon | 事实覆盖、同 subject/predicate 不同值、静默 retcon |
| Timeline | 时间倒置、order rollback、未知前序、未声明并行/回忆 |
| Knowledge | 角色声称知道未建立的事实，或本章学习却未记录知识边 |
| Character | Character Fit <75、人物底线违反 |
| Economy / Power | 资源起点/守恒/负数、无来源增长、有效战力超绝对上限 |
| Contract | 不可逆变化、代价、结尾、commit updates 和 state evidence 未在 prose 出现 |
| Debt | 合同承诺未推进/兑现、新增重大 hook 超预算 |
| Payoff | 兑现没有状态变化，缺来源/代价/行为改变/四类余波 |
| Repetition | 命中禁止结构或复用近期完整 signature |
| Style | Fit 输入非法、明确 POV/声音/边界漂移；低分仅 warning |

报告带 code、severity、message、evidence、location 和 suggested fix。所有十项都执行；ERROR/FATAL 阻止 VALIDATED，WARNING 保留给作者审美判断。

## 修订

不要原地改数据库记录或旧 draft。以同一 contract 再次 `draft prepare`，Codex只针对 report 定位做新 output，导入后重跑全部十项。revision 最大为 3，即初稿 + 两轮修订。仍失败时停止并报告硬冲突。

## 批准

用户必须在当前请求中明确说：

```text
批准写入正史
```

然后执行：

```powershell
& $Novel approve --book-id $BookId --draft-id <draft-id> --confirm "批准写入正史"
```

approve 先显示 preview，并再次校验。Boundary 自草稿规划后若发生任何事件序号/投影变化，命令拒绝提交，要求从 Boundary 重新规划。成功后 `next_chapter` 指令被消费，persistent 指令保留。

## 提交后验收

```powershell
& $Novel rebuild --book-id $BookId
& $Novel source verify --book-id $BookId
& $Novel export --book-id $BookId
```

报告 draft/contract/candidate、chapter/commit、event range、projection/snapshot hash、canon/export 路径和 source verify。不得把“已生成草稿”描述成“已写入正史”。
