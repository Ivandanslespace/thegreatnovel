# Contradiction Report

## 总结

- 45/45 Arc、379/379 chapters 交叉审计完成；`audit_errors=0`、`failed_arc_ids=[]`、`old_name_hits=0`。
- 当前 hard-claim denominator 中，所有 `CANON + HARD` 结论均有 source span，Canon evidence coverage **100%**；没有足以阻断 Atlas 的已确认故事矛盾。
- `READY_WITH_GAPS` 来自未知和作者选择，不是冲突状态。

## 已确认无冲突的边界

### 1. 阶段性复活顺序

ch231 献祭与复活条件、ch247 身体先回归、ch257/261 部分融合/订婚、ch318 海神之光完成灵魂与身体融合、ch378–379 终局存活是阶段推进而非互相矛盾（`span_143735c3014eb8fa96b104da`、`span_fd24cafdffcddce089b6696e`、`span_b13758a8912afe6f7fc361ff`、`span_bfec8b368e11c5b051e6f6aa`、`span_eeae31dd6055c25dbe5e42bf`）。

### 2. 双神与三环同吸

终局的“双神一次只能一神出手”是神力并发边界（`span_eeae31dd6055c25dbe5e42bf`）；Arc40 的“三头魂环同时吸收”是魂环吸收规则例外（`span_221ed41c9b397ed8b8dafd3e`）。两者属于不同规则层，不构成冲突。

### 3. 战争与战后

ch324 前仍处于帝师/唐家军战争阶段，ch379 才明确停战、唐家军解散、唐门退出军用体系和唐三政治退出（`span_3f248e82b92d8a08ce4de2a1`、`span_78e506ec415b579ab48eb2b9`）；这是时间上的阶段切换，不是角色立场矛盾。

## 证据图谱修复记录

- Arc29 ch260 曾出现 canonical 旧名“波赛西”，与实体 map 的“波赛川”和旧审计全局命中 0 不一致；主线程按原文修复 9 处为“波赛川”。修复后全 45 Arc 指定旧名扫描为 0、refresh `failed=0`。
- `阿岚/阿银/蓝银皇` 仍是 alias drift；没有足够证据证明是矛盾，也没有授权静默合并，保持 entity review queue。
- 章节标题跳号/拆分与有效 ordinal 1–379 是文档结构差异；Atlas 统一使用 `chapter_id` 和 source-span ordinal，不把标题数字差异误判为故事时间线冲突。

## UNKNOWN 与反证边界

- 双神长期反噬、非战斗持续时间、神级复活可重复性、神界职责与五行大陆路线均为 UNKNOWN/CANDIDATE；未知不等于矛盾。
- 婚礼尚未举行；不能把“接受安排”解释为“已完婚”（`span_78e506ec415b579ab48eb2b9`）。
- 比比宸死亡、千仞霄神位破碎/武魂受损并获赦免是当前 hard boundary；无新作者批准和因果不得回滚（`span_fa378dd5cb85560640398b82`、`span_78e506ec415b579ab48eb2b9`）。

## Review Queue

1. 续写形态与首个前景线程由作者选择。
2. 为婚礼、公开关系、停战执行和神界职责建立时间顺序。
3. 为双神单次单一出手建立下一章 Chapter Contract 硬门。
4. 对 `阿岚/阿银/蓝银皇`、泰坦标题和神位/承载者 node type 做上下文复核。
