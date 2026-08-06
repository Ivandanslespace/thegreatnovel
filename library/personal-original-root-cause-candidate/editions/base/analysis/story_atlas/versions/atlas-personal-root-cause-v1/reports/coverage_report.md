# Atlas Coverage Report

## 结论

当前 Atlas 隔离构建的确定性覆盖为：

| 维度 | 覆盖 | 依据 |
|---|---:|---|
| Source mapping | **100%** | initialization `source_coverage=1.0`、`source_mapping_coverage=1.0` |
| Arc outputs | **100%（45/45）** | `status.json`：`completed_arc_ids=45`、`failed_arc_ids=[]`、`pending_arc_ids=[]` |
| Chapters | **100%（379/379）** | `source_coverage.json` 全书 ordinal 1–379；cross-Arc audit `379/379 chapters` |
| Entity evidence | **100%（21/21 已登记实体）** | `entity_resolution_map.json`：21 个 `CANON` 实体；当前 Atlas 的 hard 节点均可回指实体 map 或真实 source span |
| CANON evidence | **100%（本 Atlas hard-claim denominator）** | `current_world_model.md`、`narrative_dna.md` 中所有 `CANON + HARD` 事实均列真实 `source_span_id`；无无证据升级 |
| Metric observations | **100%（379/379，15,160 observations）** | `metric_bootstrap_status=COMPLETE`；指标仍是诊断层 |

`READY_WITH_GAPS` 不是覆盖失败：它表示未来形态、作者选择和长期规则仍开放。`atlas_evidence_inventory.md` 早于最后六个 Arc 输出，仍保留 43/45 的历史快照；本报告以当前 initialization `status.json`、更新后的 `cross_arc_validation.md` 和最新 output 为准，不把该旧快照当作当前状态。

## 状态锚点

- `initialization_id=novel-initialization_adf4a8524c6085b239ec8df6`
- `source_manifest_sha256=de44e1853c51b6e676c7d07aa9d158c94a914d0ecd1f6d2a2cea3fd0ad765740`
- `effective_content_sha256=a1e5b3ac2d6fc5a57203c1667a2b491e91de60dd3dd93105479ce21d8242304e`
- `metric_bundle_hash=a751abc055c06b88602fcb992e7d15d47ec76c409868dbbe93385dcffde041ae`
- `base_projection_hash=e2ba9f4cf087717a278fa7c4dd933b6e08316074d89cc282139dae8eb2df2c0b`

## 45/45 Arc 验收摘要

- Arc34–35：海神第四/第五/第六/第七考与波赛川 canonical 名复核。
- Arc36–37：第八考五年条件、凌岳阶段性复活与 ch318 完整融合复活复核。
- Arc40–41：三环同吸、神器被夺、海神之心消失、魔鲸王未结算复核。
- 全部 output schema 通过；`audit_errors=0`、`old_name_hits=0`；历史“波赛西”污染已修复为“波赛川”。

## Gap / Review Queue

1. `continuation-form`：尾声、第二部或跨世界新篇未由作者选择。
2. `wedding-on-page`：婚礼仅有安排，是否近端兑现未决定。
3. `dual-god-long-term-cost`：双神长期成本、非战斗持续时间与独立切换边界未知。
4. `five-elements-priority`：远端执行者遇害 hook 的来源、通道、责任主体和优先级未知。
5. `postwar-enforcement`：停战、战俘和唐门军用退出的监督与违约成本未知。
6. `supporting-cast-current-state`：伙伴逐一目标、地点和战后分工未完整交代。
7. `阿岚/阿银/蓝银皇`：实体 map 仍有别名漂移，不能自动合并。

## 边界

覆盖率只证明“证据和结构已读入并可追溯”，不证明语义解释必然正确，也不批准任何未来路线。Atlas 的软理解、FAR horizon 和指标 provisional 观测都不能写入 Canon。
