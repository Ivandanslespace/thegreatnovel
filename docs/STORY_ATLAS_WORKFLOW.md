# Story Atlas 工作流

Story Atlas 是 LLM 对当前小说的版本化软理解。它不是真理、Canon 数据库、世界模拟器
或固定未来大纲。Python 负责读取 source/projection/edition/hash、验证结构和登记索引；
Codex 负责跨篇章阅读、语义综合、矛盾解释、Narrative DNA 和可能性设计。

## 文件与数据库边界

Atlas 只写入：

```text
workspace/<book_id>/editions/<edition_id>/story_atlas/
├─ atlas_manifest.json
├─ narrative_dna.md
├─ current_world_model.md
├─ world_rules.yaml
├─ unresolved_assumptions.yaml
├─ expansion_grammar.yaml
├─ graphs/{characters,factions,abilities,resources_and_items,regions,
│          plot_threads,stage_transitions}.json
├─ future/{active_spine,alternative_spines,wildcard_possibilities,
│         open_design_spaces,rolling_horizon}.yaml
├─ reports/{coverage,contradiction,world_model,readiness}_report.md
└─ visuals/              # Mermaid/SVG 派生物，不是事实源
```

SQLite 的 `story_atlases` 只保存版本、父版本、source/projection/effective-content/
registry/config/analyzer/hash anchor、readiness、status 和作者接受标记；`story_atlas_usage`、
`story_atlas_actions`、`story_atlas_review_queue` 保存审计记录。未来图谱和语义解释不
复制成 Canon 表。

## 七阶段 bootstrap

1. **Source Coverage**：按卷/篇章核对章节与 source span 覆盖，缺失必须显式报告。
2. **Arc Extraction**：提取世界规则、人物、势力、能力、资源、地区、事件、线程和 Promise。
3. **Cross-Arc Synthesis**：合并别名但保留稳定 Entity ID，区分规则、例外和未知。
4. **Contradiction Audit**：分类原文矛盾、视角限制、角色误解、修订和抽取错误。
5. **Narrative DNA**：记录决策逻辑、非对称杠杆、能力/资源复利、压力/兑现、关系、节奏和创新语法。
6. **Current Story Atlas**：生成带 status/constraint/horizon/confidence/evidence 的图谱。
7. **Future Possibility Space**：分开 Active、至少两个结构签名不同的 Alternative、Wildcard 和 Open Design。

`CANON` 必须有真实 source span；`INFERENCE + SOFT` 可被推翻；`CANDIDATE +
SPECULATIVE` 不能进入 Canon。Region 只记录拓扑关系，不伪造经纬度；能力、人物和
势力的新增设计必须写清来源、解决的新问题、代价、边界、反制和 why-now。

## Rolling Horizon 与 readiness

每个 Horizon 文件必须带 `horizon_id`、`horizon_hash`、Atlas ID/version、Atlas content
hash、base projection hash 和当前章节。NEAR/MID 可以描述阶段目标；FAR 只能描述
阶段阶梯、规模变化、控制缺口与开放问题，不得出现逐章 ordinal 或固定结局。FAR
终点至少覆盖：

```text
max(当前已写章节数 × 2, batch_target_chapters × 2)
```

`READY` 表示当前边界、规则、主角状态和主要线程可用；`READY_WITH_GAPS` 表示可续写
但仍有明确缺口；`BLOCKED` 只用于当前边界、source/projection anchor 或结构合同无法
确认的情况，不因未来不完整而阻塞普通续写。

## refresh / review

`STORY_ATLAS_REFRESH` 只能产生新的 immutable child Atlas，旧版本保留并可比较；
`WORLD_MODEL_REVIEW` 只更新 review queue、矛盾和待作者决定项。任何 `ACCEPT_ATLAS`
动作都不提交 Canon，Web 端必须带 expected version/manifest hash、CSRF，并在校验失败
时 fail closed。

```powershell
novel atlas show --book-id <book_id> --edition-id <edition_id>
novel atlas validate --book-id <book_id> --edition-id <edition_id>
novel atlas history --book-id <book_id> --edition-id <edition_id>
novel workflow atlas-bootstrap --book-id <book_id> --stage ATLAS_BOOTSTRAP
novel workflow atlas-refresh --book-id <book_id> --stage ATLAS_REFRESH
novel workflow world-model-review --book-id <book_id> --stage WORLD_MODEL_REVIEW
```
