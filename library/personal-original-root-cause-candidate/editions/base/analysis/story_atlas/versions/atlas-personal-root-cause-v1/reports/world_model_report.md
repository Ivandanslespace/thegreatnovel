# World Model Report

## Model status

- 本模型覆盖 45/45 Arc、379/379 chapters；source/Arc/chapter/entity/Canon evidence coverage 分别为 **100%**（entity 口径为 21 个已登记 canonical entities，Canon 口径为本 Atlas hard-claim denominator）。
- 当前状态：`READY_WITH_GAPS`。当前世界边界足够建立下一章 Boundary Packet，但未来形式和长期规则仍需要作者选择/复核。
- 原则：**Facts are deterministic; Meaning is probabilistic.** Python/状态文件决定覆盖、ID、证据和阈值；Atlas 只记录带证据的软理解，不取代 Canon。

## 当前世界模型（CANON）

| 层 | 当前事实 | source span |
|---|---|---|
| 主角 | 唐三已复活；成年男性伴侣凌岳存活并共同完成双神共存 | `span_679c5e4110fa88c01b2f95ff`；`span_eeae31dd6055c25dbe5e42bf`；`span_78e506ec415b579ab48eb2b9` |
| 神力边界 | 双神可切换，但一次只能一神出手 | `span_eeae31dd6055c25dbe5e42bf` |
| 终局敌手 | 比比宸死亡；千仞霄神位破碎、武魂受损并获赦免；胡列昭获准存活 | `span_fa378dd5cb85560640398b82`；`span_78e506ec415b579ab48eb2b9` |
| 政治 | 嘉陵关神战/大陆战争结束；唐三退出常驻人间权力，唐门军用退出 | `span_78e506ec415b579ab48eb2b9` |
| 关系承诺 | 唐三与凌岳接受婚礼安排，但未举行仪式 | `span_78e506ec415b579ab48eb2b9` |
| 远端 hook | 五行大陆执行者遇害，仅为远端事实，不是已选任务 | `span_78e506ec415b579ab48eb2b9` |

## 关系与能力解释（INFERENCE + SOFT）

- 唐三—凌岳关系由共同承担复活代价、互救和双神共存推进；“哥/兄弟”是语境称谓，不是血缘证明（`span_f40472f2eaaabb9134b7db26`、`span_b13758a8912afe6f7fc361ff`）。
- 神级复活是肉身/神魂两层、依赖不同信仰/神力的特殊事件，不构成通用复活规则（`span_679c5e4110fa88c01b2f95ff`、`span_bfec8b368e11c5b051e6f6aa`）。
- 五行大陆、神界职责、停战执行能力和双神长期成本均保留 unknown boundary；不得因叙事上“自然”而升级为 Canon。

## 战后阶段模型

### CURRENT

已发生的终局事实、已闭合的敌手线、双神单次一神规则和唐三政治退出。

### NEAR（候选，不是批准大纲）

战后余波、婚礼/共同生活边界、伙伴逐一行动、停战与技术退出的制度反馈。

### MID（候选）

神界职责调查、伴侣共同体的职责分配、无主角常驻统治下的大陆重建。

### FAR（候选/开放）

五行大陆规则异常与跨世界尺度扩张；只写阶段阶梯、控制缺口、路线问题和约束，不能写逐章计划或固定结局。

## Model gaps / review queue

1. `continuation-form`：尾声、第二部或跨世界新篇。
2. `wedding-on-page`：婚礼兑现窗口与公开关系后果。
3. `dual-god-long-term-cost`：长期消耗、反噬、非战斗持续时间。
4. `five-elements-priority`：异常来源、通道、责任主体和介入权限。
5. `postwar-enforcement`：停战、战俘和技术退出的监督/违约成本。
6. `supporting-cast-current-state`：伙伴目标、地点和独立行动。

## Safety gates

- 新候选必须通过 Canon/Timeline/Knowledge/Character/Power 边界检查，并建立 Boundary Packet 与 Chapter Contract。
- 禁止复活比比宸、恢复千仞霄完整神位、取消政治退出、把婚礼写成既成事实，或让双神同一动作同时主动出手。
- Atlas accepted、metrics COMPLETE 或 `READY_WITH_GAPS` 均不等于作者批准写入正史。
