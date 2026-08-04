---
name: bootstrap-story-atlas
description: 按 Novel_Authoring_System_Constitution_V2.md 为已有长篇小说分阶段构建或刷新可审计的 Versioned Soft Story Atlas；用户要求建立世界模型、Story Atlas、Narrative DNA、未来路线、Rolling Horizon、Atlas Refresh 或 World Model Review 时使用。不得把软理解写入 Canon，不得预建固定结局或逐章 FAR 大纲。
---

# Bootstrap Story Atlas

Story Atlas 是 LLM 对当前小说的版本化、带证据的最佳理解，不是 Truth、Canon、世界模拟器或固定大纲。Python 只负责校验 source/projection/edition/hash、信息边界和 artifact 合同；Codex 负责阅读、综合、解释和提出可能性。

## 硬边界

1. 先读取根 `AGENTS.md`、`Novel_Authoring_System_Constitution_V2.md` 和 handoff 目录中的 `task.json`、`prompt.md`、`context_manifest.json`、`output_schema.json`、`status.json`。
2. `book/` 永久只读；所有 Atlas 文件只能写入当前 handoff 的 `artifacts/story_atlas/`，不得直接改写 Canon、真实 projection、edition 或旧 Atlas。
3. `CANON`、`AUTHOR_INTENT`、`APPROVED_OUTLINE`、`INFERENCE`、`CANDIDATE`、`PROSE_ONLY` 是信息状态，不得混用。每个节点和关系都必须有 `information_status`、`constraint_level`、`horizon`、`confidence`、`evidence` 和稳定 ID。
4. `CANON + HARD` 必须有可回溯到真实 `source_span_id` 的证据。`INFERENCE`/`CANDIDATE`/`SPECULATIVE` 只能作为软理解或候选，不能指控正文违反正史。
5. Atlas accepted、World Model Review 完成、`BATCH_VALIDATED` 都不等于“批准写入正史”；只有作者当前明确说“批准写入正史”才可进入批准流程。

## 工作流

### 1. Source Coverage

读取章节索引和 Source Span 覆盖，识别卷、篇章、阶段边界。不得只读最近章节；覆盖不足时记录 `READY_WITH_GAPS`，不要用摘要伪装完整理解。

### 2. Arc Extraction

按篇章抽取世界规则、人物、势力、能力、物品/资源、地区、关系、事件、Promise、压力/爽点模式和设定引入方式。每条语义判断写 reasoning summary 与 evidence。

### 3. Cross-Arc Synthesis

合并别名、稳定 Entity ID、能力演化、资源层级、关系变化、势力形成/消亡、区域连接、规则例外和世界规模变化。不能因为名称相似就静默合并实体。

### 4. Contradiction Audit

区分真实原文矛盾、角色误解、视角限制、作者后期修订、抽取错误和未知问题。原文冲突必须写入 `contradiction_report.md` 与 `unresolved_assumptions.yaml`，不得自行修正文档。

### 5. Narrative DNA

在 `narrative_dna.md` 中总结主角决策逻辑、非对称杠杆、能力/资源复利、世界扩张、人物/势力引入、压力与兑现、关系演化、文风节奏、重复风险和原作创新语法。Narrative DNA 是理解，不是公式分数。

### 6. Current Atlas

生成规范化 JSON/YAML：`current_world_model.md`、`world_rules.yaml`、`graphs/*.json`、证据报告和 Mermaid 源文件。地域使用 Region Topology，不伪造经纬度；图谱节点默认只表示当前/已证实或明确标记的软候选。

### 7. Future Possibility Space

生成一个 `ACTIVE` Spine、至少两个结构签名不同的 `ALTERNATIVE` Spines、`WILDCARD` possibilities 和 open design spaces。NEAR/MID/FAR 分层；FAR 只保留阶段阶梯、规模扩张、控制缺口和开放问题，禁止逐章计划、固定结局或让所有路线汇聚到同一终点。

## 输出与完成

在 `artifacts/story_atlas/` 生成 `atlas_manifest.json` 以及目标目录中的软文件。manifest 必须冻结 `atlas_id`、`atlas_version`、`book_id`、`edition_id`、base event/projection/source hash、artifact hashes、readiness、coverage 和当前章节；新版本必须有新 ID/版本，不覆盖旧版本。

完成前运行：

```powershell
novel atlas validate --book-id <book_id> --edition-id <edition_id>
```

需要作者逐项判断时写 `waiting_for_user.json`，进入 `WAITING_FOR_USER`；完成时严格写 `result.json`/`status.json`，报告 artifact paths、Atlas version、readiness、低置信度推断、未解决矛盾和 review queue。不要声称“完全理解小说”。
