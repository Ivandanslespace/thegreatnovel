# 冻结续写结果最终报告

审计时间：2026-08-04（Europe/Paris）  
项目根目录：`C:\dev\小说续写系统`  
书籍：`全民纜車求生，我一級一個三選一`  
工作区 book id：`real-book-smoke`  
本报告状态：`WARNING`

## 1. Executive Verdict

结论：`WARNING`。

本轮确实产生了一个目标为 ordinal 295、标题为《最小介入》的最终草稿；最终十项验证全部通过，草稿状态为 `VALIDATED`，原文 SHA-256 在审计前后保持一致，且没有 Canon Commit、approve、snapshot 或正史正文写入。因此，续写内容本身的“最终草稿验证”是 `VERIFIED_PASS`。

冻结交接不能标为无条件通过，原因是审计期间正式 SQLite 被 CLI 初始化触发 migration 5/backfill，且验证时记录的 projection hash `8c26…a7226` 与当前临时重建 hash `500f…8edae` 不一致。这两项均是 `VERIFIED_FAIL`，会阻止“正式状态未被审计触碰”和“当前数据库可确定性重放”的强结论。

本报告冻结的是现有证据与现有草稿，不批准写入正史，不要求也不执行修订。

## 2. Audit Scope

审计对象是：原文完整性、实际使用的规范与指令、从抽取到验证的工作流、Boundary Packet、Chapter Contract、三候选选择、四版草稿、指标来源与公式、状态账本、验证结果、测试/静态检查、Git 状态和冻结交接证据。

本次只创建 `audit\final_continuation_report\` 及其证据；没有编辑 `book\` 原文、既有 draft、boundary、contract、配置阈值或正文 Canon Commit。禁止动作均未执行：`approve`、正史写入、重写、重新选择候选、修改 boundary/contract、Git reset/clean/checkout/restore/stash/commit/push/PR。

## 3. Source Manuscript Integrity

状态：`VERIFIED_PASS`（完整性）+ `WARNING`（编号结构）。

| 项目 | 结果 |
|---|---|
| 原文路径 | `C:\dev\小说续写系统\book\全民纜車求生，我一級一個三選一_正文全集.md` |
| 字节数 | 1,863,851 |
| 编码 | UTF-8 |
| 原文 SHA-256 | `95810246d1296163fc02320446060e78addd9fa5cba56bbdd1292634a099ee6e` |
| front matter book_id | `2106587852` |
| front matter chapter_count | 294 |
| 解析 heading 数 | 294 |
| 数据库 ordinal 数 | 294，范围 1–294 |
| 本轮续写目标 | ordinal 295 |

原文 raw heading 不是可靠的唯一章节序号：重复编号为 37、128、224–233；`第000章 關於章節錯亂的說明` 位于第 17064 行；1–283 的 raw 编号还有 74、96 两个缺口。最近三条原文 heading 是 raw 第281、282、283章，但数据库 ordinal 是 292、293、294。本轮沿用 parser/database ordinal，不能把标题误报为 raw “第284章”。详细解析证据在 `audit_bundle/source/chapter_parse_report.json`。

## 4. Constitution and Instructions Actually Used

实际使用并封存了以下规范/指令：

| 文件 | SHA-256 | 状态 |
|---|---|---|
| `Novel_Authoring_System_Constitution_V2.md` | `C5C4E747827CC5D5529DE0C7AB4F4DD8A71B9EEC69ACDDD4CD23F6BB74208A78` | `VERIFIED_PASS` |
| 项目 `AGENTS.md` | `423F9C9595CDD9DB67B752211E3E307A94476A15DF02766172CD8501DCD9850F` | `VERIFIED_PASS` |
| `.agents\skills\continue-novel\SKILL.md` | `6118141AA8FAB55265DB621A0E3D717464EC06CCF62BA266EAB6F99DB8E6F87A` | `VERIFIED_PASS` |
| `config\default.yaml` | `D833AABCD137E484B94437863307DD23ADAB61D0BF9ABD72E117B974F3A304E1` | `VERIFIED_PASS` |

`revise-novel/SKILL.md` 已作为项目指令证据封存，但本轮不是版本化改写，未使用其改写流程：`NOT_RUN`。根目录 `CONSTITUTION.md` 不属于本系统最高规范，未作为规范依据。

## 5. End-to-End Workflow Reconstruction

根据数据库、任务包、输出文件和验证报告，工作流可重建为：

1. **Source lock / extract**：读取授权本地原文，形成 source manifest 和最近章节 span；extract task 为 `extract_595984bc5d9b8eda9f84e407`，状态 `VERIFIED_PASS`。
2. **Metrics**：以第275–283章证据和当前状态输入指标；本轮手工/语义输入与确定性公式分开保存，状态 `WARNING`，因为大部分输入不是自动抽取。
3. **Boundary Packet**：建立旧 boundary 后生成最终 boundary `boundary_ad5bb77726ed63ee23e6afbb`，以 event seq 64、projection hash `8c26…a7226` 为基点，状态 `VERIFIED_PASS`（但有历史摘要不足警告）。
4. **Three candidates**：plan task `plan_ed92d57df50bf6152d90adf6` 生成三个候选，分别做硬门和评分。
5. **Candidate selection**：选中 `candidate_5d28497d5e0a03eb1b5d7070`《最小介入》，选择原因记录为综合评分最高且通过硬门；`AUTHOR_DECISION`：未发现作者对候选的独立显式批准事件。
6. **Chapter Contract**：生成 `contract_b991e2e90d8e8b824fea00d9`，限定局部救援、不能击杀两只 Lv8、必须支付暴露与武器擦伤成本。
7. **Draft**：draft task `draft-task_3028f1b23f5c7e992d00a04f` 产生四个内容 hash 不同的版本；前三版经 Contract Validator 失败后迭代，最终版进入 `VALIDATED`。
8. **Freeze audit**：读取并复制证据、在临时副本进行测试/重建/导出、生成本报告、清单、ZIP；正式数据库的审计期迁移异常被保留为 `VERIFIED_FAIL`。

原始 continuation `run_id` 没有找到，故不能声称以上步骤由单一 run 记录完整串联：`NOT_AVAILABLE`。

## 6. Boundary Packet Audit

最终 packet：`boundary_ad5bb77726ed63ee23e6afbb`，状态 `READY`，版本 1。

- `base_event_seq`：64。
- `last_canon_chapter`：294（数据库 ordinal；raw heading 为 `## 第283章 牽制`）。
- `base_projection_hash`：`8c26e592893c7908c77a94e3526a6664126213ec66671bfc943cf1a33c8a7226`。
- 包含最近 ordinal 285–294 的原文 span，涵盖 raw 第274–283章。
- 有效限制：更早章节尚无结构化摘要，当前依赖 Canon Projection 与最近原文：`WARNING`。
- packet 不是 Canon Commit；它是续写输入边界，不能直接升级状态。

边界内容保留了：两只 Lv8 蓝色怪物、赵德荣铁鎚弯曲、雷暴由落雷哥布林法杖/蓝宝石引发、苏牧对地下移动的直接感知、苏牧尚未公开介入等约束。

## 7. Metrics and Formula Provenance

公式实现封存于 `audit_bundle/metrics/formulas.py`，配置封存于 `audit_bundle/metrics/default.yaml`；公式 id 为 `constitution-v2`，config hash 为 `685a5acc8a728524c2a6e407ffccc2b3b76e433e3f3c10c319fbf61b2e1b4ce3`。确定性公式本身可复算，但输入主要是 `LLM_HEURISTIC`/人工语义评估，不应误写成全自动测量。

### 7.1 三个用户关心的指标

**Pressure = 81.95**：配置权重为 threat .25、scarcity .20、deadline .20、uncertainty .15、social_conflict .10、failure_accumulation .10；输入是 95、85、90、78、30、85。

```text
95×0.25 + 85×0.20 + 90×0.20 + 78×0.15 + 30×0.10 + 85×0.10
= 23.75 + 17.00 + 18.00 + 11.70 + 3.00 + 8.50
= 81.95
```

阈值解释：`高潮准备区`；建议检查成熟爽点或关键反转。

**Narrative Debt = 123.2316962933031**：实现为

```text
age_ratio = clamp(0, 1.5, age_chapters / target_max_age)
reminder_factor = 1 + 0.12 × min(reminder_count, 5)
raw = 100 × importance × reader_visibility
      × (1 - promise_progress)^1.2
      × age_ratio × reminder_factor
score = clamp(0, 150, raw)
```

代入本轮输入：importance=.92、reader_visibility=.95、promise_progress=.10、age=8、target=8、reminder=5，因此 `age_ratio=1.0`、`reminder_factor=1.6`：

```text
100×0.92×0.95×0.90^1.2×1.0×1.6
= 123.2316962933031
```

阈值解释：`严重债务`；建议暂停堆叠同等级新承诺。

**Outcome Uncertainty = 80.25**：配置权重为 danger_unknown .30、opponent_plan_unknown .25、motivation_unknown .20、reward_or_result_unknown .15、world_truth_unknown .10；输入为 85、80、75、85、70。

```text
85×0.30 + 80×0.25 + 75×0.20 + 85×0.15 + 70×0.10 = 80.25
```

阈值解释：`结果未知度过高`；建议给出局部答案并明确失败条件。

### 7.2 本轮全部已记录的最新指标

| 指标 | 分数 | 输入/来源性质 | 解释 |
|---|---:|---|---|
| Pressure | 81.95 | 语义输入 + 加权公式 | 高潮准备区 |
| Narrative Debt | 123.2316962933031 | 语义输入 + 年龄/提醒公式 | 严重债务 |
| Progress | 36.25 | 语义输入 + 加权公式 | 有效不可逆进展 |
| Payoff | 69.10 | 语义输入 + payoff 公式 | 中型爽点窗口 |
| Repetition Fatigue | 0.00 | 空 history 的确定性分支 | `no_history`，不是全书无重复证明 |
| Risk Credibility | 81.35 | 语义输入 + 加权公式 | 风险可信 |
| Agency | 82.2886070867877 | 五项输入的几何平均 | 路线级选择 |
| Legibility | 70.85 | 语义输入 + 加权公式 | 目标与规则可理解 |
| Outcome Uncertainty | 80.25 | 语义输入 + 加权公式 | 结果未知度过高 |

Agency 的具体实现为 `100×(0.82×0.86×0.76×0.80×0.88)^(1/5)`；Payoff 使用 maturity、impact、novelty=`100-repetition_fatigue`、causality、after_value、structural_fit、repetition_fatigue、future_damage 的配置加权。ThreadNeed 和 CandidateScore 是在输入 payload 已给出的情况下确定性加权，但其 component inputs 仍主要由语义判断提供。

Stagnation、Resource Pressure、Aftershock Debt 没有形成正式 metric result：`NOT_RUN`。

## 8. Thread/Candidate Audit

正式 projection 中有 3 条主线程、2 条 promise：

- 防线线程 `thread_a90327d3f39355457af89ebe`：目标是在两只 Lv8 蓝色单位攻击中保持营地防线；本轮 primary。
- 灰光/地下线程 `thread_430da8570538d2bf5cc56994`：查明灰光、地下存在与黄金血脉联系；本轮 secondary。
- 黄金血脉/密林异常线程 `thread_2572c7ac14fc703f8533fda2`：关联异常、动物逃亡和血脉躁动。

候选对比如下：

| 排名 | candidate | 标题 | primary function | 分数 | gate | 状态 |
|---:|---|---|---|---:|---|---|
| 1 | `candidate_5d28497d5e0a03eb1b5d7070` | 最小介入 | partial_payoff | 82.06 | PASS | SELECTED |
| 2 | `candidate_6777237d9608a2254dddf821` | 把自己放到地下 | discovery | 79.70 | PASS | NOT_SELECTED |
| 3 | `candidate_8741429eb7a7e0ca6a914122` | 把雷暴變成命令 | relationship_shift | 72.07 | PASS | NOT_SELECTED |

三案结构差异计数均为 `[9, 9]`，且前两案分差小于 tie delta 8 的语境下仍处于可选审美区间；记录的选择理由是综合评分最高且通过硬门。没有找到作者单独确认哪一案的 `AUTHOR_DECISION` 事件：`NOT_AVAILABLE`。

## 9. Contract Audit

合同 `contract_b991e2e90d8e8b824fea00d9` 指向 chapter 295、候选 1、faithful_continuation。

必须做到：局部救赵德荣、短暂形成雷暴缺口、让地下/灰光线程出现局部回应、苏牧公开行动、赵德荣退出原单点前排、支付黄金血脉暴露与长枪擦伤成本。

不得解决：击杀或完全压制牛头王；击杀落雷哥布林；揭示灰光完整身份；修复赵德荣铁鎚；用无代价高等级击杀制造大爽点。合同还要求两只怪物仍为 Lv8 蓝色、保留牛头王抗机枪子弹、保留落雷哥布林以蓝色宝石引发雷暴。

最终 Contract Validator 检查 9 项并通过：`VERIFIED_PASS`。不过合同把“利用长枪改变雷暴落点”作为候选/合同机制，原文 CANON 事实未直接证明该能力，仍保留 `INFERENCE` 风险。

## 10. Generated Continuation Inventory

生成内容只存在于 `workspace\real-book-smoke\drafts\` 与审计复制件，没有追加到 `book\`：

- 目标 ordinal：295；标题：`最小介入`。
- 最终 draft id：`draft_5680fe3201e6010bacf83b91`。
- 最终文件 SHA-256：`53ae38310184db738f51903778b66ded4b247335b1f638d5f6b8bc71c255a61e`。
- 最终文件大小：5,616 bytes；正文 1,952 chars；非空白 1,835 chars；59 个段落。
- 四个版本均已复制到证据包；前三版状态为 DRAFT，最终版状态为 VALIDATED。
- 章节正文不是 CANON，未生成 Canon Commit：`VERIFIED_PASS`。

## 11. New Facts / State Delta Audit

最终 draft output 声明的草稿级变化包括：

1. 苏牧从观察者变为公开介入者，黄金血脉短暂外显；
2. 赵德荣重伤并退出最前排；
3. 东侧由单层变为内外两层；
4. 雷暴出现短暂缺口；
5. 灰光裂缝和第二次心跳出现局部回应；
6. promise `e4f784...` 被标为 paid，promise `ff9bec...` 保持未支付；
7. aftershock obligations 记录了苏牧成为可见目标、东侧防线重维持、地下回应代价未明、雷暴缺口短暂等后果。

这些是 draft `state_changes` 和 contract evidence，不是已提交的 CANON facts/events。正式数据库在 event seq 64 后没有本章 Canon Commit；因此“新事实已进入正史”是 `VERIFIED_FAIL`，而“草稿声明了这些候选变化”是 `VERIFIED_PASS`。

## 12. Canon / Timeline / Knowledge / Power Ledgers

| 账本 | 冻结时观察 | 状态 |
|---|---|---|
| Canon events | 64 条历史事件；没有本章 Canon Commit | `VERIFIED_PASS` |
| Canon facts | 9 条，包含两只 Lv8 蓝色、雷暴来源、抗机枪、岩石化等 | `VERIFIED_PASS` |
| Threads | 3 条 | `VERIFIED_PASS` |
| Promises | 2 条；草稿支付状态未写入 CANON | `WARNING` |
| Character states | 3 条历史状态；草稿新状态未成为 CANON | `VERIFIED_PASS` |
| Knowledge edges | 2 条，苏牧直接感知/现场可见 | `VERIFIED_PASS` |
| Resources | 0 条新增资源 | `VERIFIED_PASS` |
| Capabilities / power | 0 条新增能力、等级或掉落 | `VERIFIED_PASS` |
| Timeline | 0 条正式 timeline 记录 | `WARNING` |

正文中的“长枪改变雷击落点”只能标为 `INFERENCE`；不得因最终验证通过而升级为 CANON。当前投影的 resource/power 账本没有被续写草稿写入，不能据此声称正文机制已被系统证明。

## 13. Validation Report

最终验证 run：`validation_7484fd836836abab8a2c60e1`，draft `draft_5680fe3201e6010bacf83b91`。十项均通过：Canon、Timeline、Knowledge、Character、Economy / Power、Contract、Debt、Payoff、Repetition、Style：`VERIFIED_PASS`。

前三版的共同过程是 9 项通过、Contract Validator 失败，随后修订：

- v1：缺少精确 commit key 和证据标点；
- v2：commit key 与灰光证据短句仍不匹配；
- v3：`推进`/`推進` key 不一致；
- v4：10 项全部通过。

最终报告记录 `requirements_checked=9`，Style fit=84.6，Character fit=88.6。验证通过只证明验证器对给定 draft/contract 的判断，不等于原文机制已经成为 CANON，也不修复 projection hash 不一致。

## 14. Test / Static Evidence

审计时在临时复制源码树完成：

| 检查 | 结果 | 证据 |
|---|---|---|
| pytest | 53 passed，exit 0 | `audit_bundle/tests/pytest.log` |
| ruff | All checks passed，exit 0 | `audit_bundle/tests/ruff.log` |
| mypy | 51 source files，无问题，exit 0 | `audit_bundle/tests/mypy.log` |
| 临时 source verify | match=true，exit 0 | `audit_bundle/tests/source_verify_temp.log` |
| 临时 rebuild | exit 0，seq 64，hash 500f9d… | `audit_bundle/tests/rebuild_temp.log` |
| 临时 export | exit 0，0 committed chapters | `audit_bundle/tests/export_temp.log` |

这些是审计时复现的 `VERIFIED_PASS`，不是原续写运行时原始测试记录；原始测试退出码：`NOT_AVAILABLE`。

## 15. Canon Commit / Snapshot / Replay / Export

- Canon Commit：0；没有 approve；状态 `VERIFIED_PASS`（未写正史）。
- Snapshot：0；状态 `NOT_AVAILABLE`。
- 正式原运行 export：`NOT_AVAILABLE`。
- 临时副本 export：存在，export id `export_e6df8c08bfcaf483945ac313`，projection hash `500f9d…8edae`，committed_chapters=0；状态 `VERIFIED_PASS`（仅复现）。
- 验证时 base hash `8c26e…a7226` 与临时 rebuild hash `500f9…8edae` 不同；状态 `VERIFIED_FAIL`。

因此不能向外部审计员宣称“原始 validated draft 已被当前 formal state 无损 replay”。

## 16. Git / File Change Inventory

审计前捕获：

- repository：`C:/dev/小说续写系统`
- branch：`小说续写_codex_revision`
- HEAD：`1bdc60b31e6bbb412434d2cdcc10a4f2c3bfe802`
- origin：`https://github.com/Ivandanslespace/thegreatnovel.git`
- tracked worktree：clean。

审计后：tracked 文件仍无 diff；新增项目目录仅为 `audit/`（工作区 `workspace/` 被忽略）。数据库文件虽未出现在 Git diff，但已经发生 migration 5/backfill：`VERIFIED_FAIL`。原文文件未变，SHA 仍为 `958102…99ee6e`：`VERIFIED_PASS`。

## 17. Style Audit

Style Validator：`VERIFIED_PASS`，style fit=84.6。草稿遵循合同记录的第三人称限知、过去时、低对话比例、中高信息密度、动作细节密集与苏牧克制内心距离。风格通过不等于机制来源通过；长枪导雷仍是 `INFERENCE`。

## 18. Narrative Quality / Formula Audit

叙事层面，候选选择符合“高压力 + 高叙事债务 + 高未知度”下的局部兑现：救援成功但不击杀两只 Lv8，赵德荣退出单点前排，苏牧暴露并承受武器损伤，灰光只给局部回应。该判断与 Pressure 81.95、Debt 123.23、Outcome Uncertainty 80.25、Payoff 69.10、Agency 82.29 相符。

最需要外部审计员优先复核的三项：

1. `VERIFIED_FAIL`：formal DB migration 5/backfill 和验证/rebuild projection hash 不一致，冻结重放链断裂。
2. `WARNING`：Debt=123.23、Outcome Uncertainty=80.25，而 Repetition=0 是空历史策略，不能把指标看作全自动客观测量。
3. `INFERENCE`：正文的长枪改雷击落点机制没有在 CANON facts 找到直接来源，虽然合同和验证器接受了它。

## 19. Aftershock Obligations

最终 draft 明确留下四项后果：

- 苏牧成为两只 Lv8 怪物的可见目标；
- 东侧内外两层防线需要继续维持；
- 地下回应的方向与代价未明；
- 雷暴缺口只能维持短暂时间。

另有 promise `ff9becdefdd3e9452b18f217` 未支付，下一步必须追踪裂缝、心跳与雷暴的关联。Aftershock Debt 没有单独计算：`NOT_RUN`。

## 20. Known Problems

完整问题清单见 `KNOWN_ISSUES.md`。冻结级别问题是：正式数据库审计期变更、projection hash mismatch、原始 run/测试/snapshot/export 缺失、raw 章节编号异常、结构历史不完整、长枪机制来源未证实。

## 21. Claims Cannot Verify

以下声明不能从当前证据严格验证：

- 原续写运行的完整命令顺序和原始 run id；
- 原续写时是否运行过全部 pytest/ruff/mypy；
- 原始 validated projection 是否能在迁移前数据库上重放出 `8c26…a7226`；
- 候选选择是否经过作者独立、显式的 `AUTHOR_DECISION`；
- 原文是否在更早、未结构化章节中已经规定长枪可导雷；
- 当前 0 repetition fatigue 是否代表全书新鲜，而非 history 输入缺失；
- 原始 continuation 是否产生过 snapshot/export，只能确认当前 formal DB 中没有相应记录。

均标为 `NOT_AVAILABLE` 或 `INFERENCE`，没有用推测补齐。

## 22. External Auditor Checklist

- [x] 原文路径、字节数、编码、SHA-256 已封存：`VERIFIED_PASS`
- [x] Constitution、AGENTS、continue skill、配置已封存并给出 hash：`VERIFIED_PASS`
- [x] Boundary Packet、Contract、三候选、四版草稿、验证报告已封存：`VERIFIED_PASS`
- [x] 最终 draft 十项验证通过：`VERIFIED_PASS`
- [x] 未发现 Canon Commit/approve/正文追加：`VERIFIED_PASS`
- [x] 审计时临时测试和静态检查通过：`VERIFIED_PASS`
- [x] Git HEAD、branch、审计前状态已封存：`VERIFIED_PASS`
- [x] 原文审计后 hash 复核：`VERIFIED_PASS`
- [ ] 正式数据库全程未被审计触碰：`VERIFIED_FAIL`
- [ ] 当前正式状态可复现验证时 projection hash：`VERIFIED_FAIL`
- [ ] 原始 run、原始测试、snapshot、正式 export 齐全：`NOT_AVAILABLE`
- [ ] 所有正文机制均有 CANON 来源：`WARNING`，长枪导雷机制为 `INFERENCE`
- [ ] 可批准写入正史：`AUTHOR_DECISION` 尚未发生；本报告不构成批准

最终交接标签：`WARNING`。交接对象是“已验证但存在冻结完整性异常的 VALIDATED 草稿及其证据”，不是 Canon 文本。
