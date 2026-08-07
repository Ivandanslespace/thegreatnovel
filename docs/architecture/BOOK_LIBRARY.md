# Book Library 架构

## 当前约定

默认书库为项目根目录的 `library/`，每本书由 `BookLayout` 解析为
`library/<book_id>/`。真实来源只进入 `source/`；数据库、迁移报告和机器状态进入
`_system/`；edition 产物进入 `editions/<edition_id>/`。

```text
library/<book_id>/
├─ book.yaml
├─ README.md
├─ source/                         # 只读来源副本
├─ _system/state.sqlite3
└─ editions/<edition_id>/
   ├─ analysis/                    # Atlas、初始化、指标、节奏和 distill
   │  ├─ distill/                  # preparation 与版本化 Knowledge Package
   │  │  ├─ preparations/<id>/     # selected Edition 冻结的 source/segment 输入
   │  │  ├─ skills/<distill_id>/   # Markdown skill + machine/ 严格机器合同
   │  │  ├─ latest_self_book.json  # SELF_BOOK pointer
   │  │  └─ references.json        # EXTERNAL/COMPARATIVE pointers
   │  └─ runtime_baseline/         # source-derived runtime state, 非 Distill
   ├─ writing/                     # boundary、candidate、contract、draft、validation
   ├─ operations/<operation_id>/   # manifest/status/events/input/output/artifacts/logs
   ├─ batches/
   ├─ canon/
   └─ exports/latest|archive/
```

旧 `workspace/<book_id>` 仍可被兼容服务读取；新运行入口应通过 `BookLayout` 或
CLI/Web 的 `--library-root` 解析路径，不再手工拼接书库目录。不会使用 symlink 替代真实
目录迁移。

## 边界

Book Library 只收敛存储位置，不改变 V2 宪法、指标公式、Atlas 证据语义、Canon 事件或
作者批准门。Portable Snapshot 的 JSON 是 canonical view；SVG 只能通过显式 atlas export
生成。`exports/latest` 可直接打开，不依赖服务端或 `file:// fetch`。

## Distillation Knowledge Layer

Distill Skill ≠ Canon ≠ Runtime State。`SELF_BOOK` 是当前 selected Edition 的软理解层，
可被 Story Atlas、候选规划、草稿控制、软校验和连续性发现消费，但不能直接写入 Canon；
`EXTERNAL_REFERENCE` 只能迁移抽象机制、Craft Control 和中性风格变量；
`COMPARATIVE_REFERENCE` 只接受显式 `synthesis`、`transferable_principle`、
`craft_control` 内容。Scope 会同时冻结在 preparation manifest、distill request、
published manifest、latest pointer 和 handoff `distill_reference`。

Package V1 的 `machine/package.json` 是严格 Pydantic 合同；`observations.jsonl`、
`literary_arcs.json`、`craft_controls.json`、`continuity_candidates.jsonl`、
`evidence_mappings.jsonl` 只保存结构化抽象和 locator，不保存来源长段原文。Evidence
Mapping 使用 frozen segment/chapter、selected Edition ordinal 和已有 Source Span，结果
只能是 EXACT/PARTIAL/UNMAPPED/CONFLICTING；UNMAPPED 不能作为 hard evidence，CONFLICTING
必须进入 review。Distill Literary Arc 与 Initialization Processing Arc 是两个不同模型，
不能互相写入。

Phase 5 的 A/B 入口还使用 `RuntimeContextRequest.include_runtime_state`：A 只取可见
hard boundary 与 Distill soft context，B 才取 Effective Runtime/Earned Surface。两组都
通过同一 Candidate/Contract/Draft/十项 Validator 流程，生成阶段没有 hidden future、Canon
写入、Edition activation 或作者 approval。

Phase 5.1 将真实语义边界与历史 fixture 分开：

- `scripts/phase5_real_generation_ab.py` 是 `SEMANTIC_FIXTURE_AB / NOT_LIVE_GENERATION_BENCHMARK`，其中的文学文本只用于历史确定性回归；
- `scripts/phase5_live_ab.py` 只实现 `PREPARE → Codex Desktop READY_FOR_CODEX → COLLECT → EVALUATE`，不得在 Python literal 中生成 Distill finding、候选、合同文学内容或正文；
- Distill 使用正式 `NOVEL_DISTILLATION` handoff；Candidate/Draft 使用现有 canonical `operations/<operation_id>/input|output` 文件合同。报告同时保存 workflow `handoff_id` 与 Candidate/Draft `operation_id/task_id`，不伪造不存在的 handoff；
- 默认边界为 50/75，A 为 `include_runtime_state=false`，B 为 true；可选 C 仅在 50 的 Candidate Planning 打开 Runtime，Draft 关闭，以检验 Runtime 是否应主要影响规划；
- hidden truth 由 `benchmark/phase5_live_hidden/` controller 独立持有，不进入 Book、task、prompt、context manifest 或 Skill input。只有两章 Candidate/Contract/Draft/Validator 全部关闭并写入 `generation_closed=true, truth_revealed=false` 后，`evaluate` 才可读取它；
- N+2 通过真实 N+1 `VALIDATED_DRAFT` 与 `BatchProvisionalState` 建立新 operation input，不能从 `1..N` 独立重置；所有结果仍停在 `VALIDATED_DRAFT`，不改变 Canon、Edition、Atlas 或 Approval。
