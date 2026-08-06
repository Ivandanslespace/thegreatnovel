# Source Coverage Report

## Deterministic coverage

- Source manifest：`source_mapping_coverage=1.0`，覆盖 379 个有效章节，full-book ordinal 为 1–379。
- Arc segmentation/output：45 个 Arc 全部完成，`completed=45`、`failed=0`、`pending=0`；Arc34–41 的补审覆盖 ch294–323、338–353，无空洞。
- Chapter semantic features：`chapter_semantic_feature_coverage=1.0`；每章有 feature record，但 feature 的意义字段不自动等于 CANON。
- Cross-Arc audit：`45/45 Arc`、`379/379 chapters`、`audit_errors=0`；Arc-local ordinal 与全书 ordinal 已区分，报告中的硬事实使用 source span 的真实 ordinal。

## Evidence contract

1. `CANON + HARD`：必须同时列 `source_span_id`；本隔离 Atlas 的当前边界、能力限制、关系和死亡/政治退出事实均满足。
2. `INFERENCE + SOFT`：允许跨 Arc 综合，但要保留 confidence、反证或 unknown boundary；不得宣称正文已选择未来路线。
3. `CANDIDATE + SPECULATIVE`：只表示可能入口；五行大陆路线、战后制度执行能力等均保持这一层级。
4. 指标上下文的 15,160 条观测为 `SEMANTIC_ESTIMATE`，选定状态为 `PROVISIONAL`，当前证据链接没有 source span；这些数值只能诊断 pressure/payoff/progress 等组件，不能补齐 Canon 证据。

## Arc34–41 source anchors

| Arc | Chapters | Representative source spans | Audit finding |
|---|---:|---|---|
| Arc34 `init-arc_0e597309ea1bcf479b928f48` | 294–300 | `span_4d4cd6b52e576119206e5f71`、`span_381068395cc2fd72ab28b241`、`span_c8f2b33b94062513c68795e5` | 第四考闭合、第五考推进、献祭创伤未提前闭合 |
| Arc35 `init-arc_38e6ffd157f25868b33373ae` | 301–307 | `span_bdcd51f5d104315268594b9a`、`span_ad1b35a873b4c00df1d6f7fd`、`span_b7759f8f63739276e505e599` | 波赛川限制、越界撤离、第七考成立 |
| Arc36 `init-arc_dcac1f57b3d4f5813901b7fe` | 308–315 | `span_a7ca9884b99311094ded00d`、`span_5e312a97313b6963c256620d` | 第八考复活条件、战争升级、前三式重创比比宸 |
| Arc37 `init-arc_12da02667825008902e02788` | 316–323 | `span_dcc5777652a62396f2e0ba56`、`span_bfec8b368e11c5b051e6f6aa`、`span_14cb1f22fd693d74f3f1fc08` | ch318 完成凌岳融合复活，阿岚/昊天宗线随后推进 |
| Arc40 `init-arc_b6f001188d49a1012754abc6` | 338–345 | `span_a4355b2312e5c1b14e8069ed`、`span_221ed41c9b397ed8b8dafd3e`、`span_d1d6c0e706012c34a2c94af9` | 三环同吸与神器赌约是终局前规则事件 |
| Arc41 `init-arc_dcb9effe4d7afc3e8a34e4d4` | 346–353 | `span_b3978bf03cf60212cebbfc07`、`span_074853fc899af790b73798fa`、`span_24c710e39d5dc8010fd2d71d` | 海神救援、海神之心消失、魔鲸王战斗未在 ch353 结算 |

## 旧名与 source integrity

- 既有 Arc29 的 9 处“波赛西”污染已按原文修复为“波赛川”；全 45 Arc 的指定旧名扫描命中 `0`，`refresh failed=0`。
- `阿岚/阿银/蓝银皇` 仍是 alias drift，不足以自动合并为同一 canonical entity；保留为 entity review queue。
- 未发现 source span 缺失、重复归属或章节越界构成的当前 blocker；`READY_WITH_GAPS` 仅指意义/未来仍开放。

## Gap / Review Queue

- 需要作者决定的未来形态不属于 source coverage 缺失：`continuation-form`、`wedding-on-page`、`five-elements-priority`。
- 需要世界规则复核的未知：`dual-god-long-term-cost`、神级复活可重复性、神界权限。
- 需要实体/群像补录的未知：`阿岚/阿银/蓝银皇`、伙伴逐一战后目标和位置。
