---
name: initialize-existing-novel
description: 按 Atlas-first 初始化合同，为已有长篇建立可审计的 Source Coverage、Arc Packets、实体解析、跨 Arc 综合、World Model、语义指标和离线视觉资产；不修改 book 或 Canon。
---

# Initialize Existing Novel

这是已有长篇首次进入本系统时的唯一初始化流程。`ingest` 只建立不可变源、章节和 source spans；它不代表理解已经完成。初始化必须使用 `workspace/<book_id>/editions/<edition_id>/initialization/<initialization_id>/`，并冻结 source manifest、effective edition、content hashes、输出 schema 和作者指令 hash。

## 阶段

按以下顺序推进，并在 `status.json`、`events.jsonl` 和报告中留下证据：

`Source Coverage -> Arc Segmentation -> Arc Extraction -> Entity Resolution -> Cross-Arc Synthesis -> Contradiction Audit -> Narrative DNA -> Current Story Atlas -> Future Possibility Space -> Semantic Metric Bootstrap -> Visual Asset Rendering`

Python 负责完整章节覆盖、唯一 Arc 归属、边界、hash、schema、稳定 ID、CANON source-span 校验、阈值和状态。Codex 桌面端负责章节/Arc 语义观察、实体别名解释、跨 Arc 关系、Narrative DNA、当前世界模型、未知、反证和未来可能性空间。不得启动 Codex subprocess、API、shell executor 或任何远程模型。

## Arc 合同

读取 `arc_tasks/<arc_id>/input.md`、`source_manifest.json`、`chapters/`、`output_schema.json` 和 `status.json`。每个有效章节必须恰好属于一个 Arc；默认 Arc 不超过 20 章和配置字符上限。只能把输出写到对应 `arc_outputs/<arc_id>/output.json`，不能覆盖 `book/`。

`CANON` 记录必须包含真实 `source_span_ids`。`INFERENCE` 必须包含 `reasoning_summary`、`confidence`、`counter_evidence` 和 `unknown_boundary`。不确定的别名、冲突和世界规则保持未知或 unresolved，不得用相似字符串自动合并。

## 就绪门槛

- `READY`：章节 100% 覆盖、Arc 100% 完成、CANON 证据达标、主角与当前边界确认、当前核心图谱齐全且无阻断冲突。
- `READY_WITH_GAPS`：至少 95% 章节覆盖、当前核心图谱齐全；只剩次要实体、远期路线或非核心语义缺口。
- `BLOCKED`：主角状态、当前核心规则/能力边界、主线程、续写边界、Edition/Source hash 或关键 Arc 缺失/冲突。

未来可能性可以不完整，但不得被伪装成当前 Canon。完成初始化后才允许进入 `STORY_ATLAS_BOOTSTRAP`、语义指标汇总和 Planning Aggregate；不得产生 Canon Commit、批准草稿或启用 Edition。

## 输出

至少保留 `initialization_manifest.json`、`source_coverage.json`、`arc_manifest.json`、`status.json`、`events.jsonl`、`arc_tasks/`、`arc_outputs/`、`entity_resolution/`、`synthesis/`、`metrics/`、`visuals/` 和 `reports/`。初始化 handoff 结果必须包含 initialization_id、Arc 完成/失败列表、覆盖率、实体/关系/图谱计数、生成视觉资产、readiness、warnings、review_queue，并固定 `canon_committed=false`、`edition_activated=false`。
