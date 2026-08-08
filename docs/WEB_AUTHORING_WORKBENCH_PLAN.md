# Novel Authoring Workbench：W0 / W1 架构与交付计划

状态：W0 架构基线与 W1 可读工作台已落地。本文描述本轮已经采用的边界，以及后续接入顺序。

## 1. 目标与边界

Workbench 是现有 Novel Authoring System 的作者控制台，不是新的 Truth 层：

```text
WEB = CONTROL + PROJECTION + AUTHOR EDITING
```

FastAPI 仍是 application/API 入口，Jinja2 负责首屏，原生 JavaScript/CSS 负责桌面交互；本仓库没有引入新的前端构建链。页面复用现有 `BookLayout`、Edition chapter view、Draft service、Canon projection 与 `book_profil` 文件，不在前端重写 Canon、Timeline、Runtime、Candidate、Contract、Validator、Approval 或 Revision 规则。

W1 只覆盖真实 Library Book 的读取、章节导航、Book Profile 消费、Source 正文只读和 Draft 编辑入口。AI Candidate / Planning / Revision 等动作保留现有 service 的接入位置，后续按 command/query 边界接入。

## 2. 页面与 API

| surface | 用途 | 写入权限 |
| --- | --- | --- |
| `/` | 当前 Web 绑定 Book 的 Workbench 首屏 | 无 |
| `/books/{book}/editions/{edition}/workbench` | 指定 Book / Edition 的 Workbench | 无；Draft 保存是显式 command |
| `/api/books/{book}/editions/{edition}/workbench` | 一次返回 Explorer、Profile、Draft、Chapter Context | 无 |
| `/api/books/{book}/editions/{edition}/chapters/{chapter}/context` | 统一 `ChapterContext` 聚合接口 | 无 |
| `/api/books/{book}/editions/{edition}/drafts/{draft}/content` | 作者显式保存 Draft 正文 | 只改 Draft；清空旧 validation，不触碰 Canon |
| `/books/{book}/editions/{edition}/chapters/{chapter}` | 既有 metrics 审核页，保留用于兼容 | 既有 metrics command |

章节与 Profile 导航通过 URL 保存当前选择；原生脚本用 History API 替换 Workbench 壳，避免章节点击整页刷新。左右栏宽度与折叠状态保存在浏览器本地布局偏好中。

## 3. 三栏职责

### LEFT：Explorer

Explorer 从真实数据库、Edition chapter view、Draft 表和 `book_profil` 文件生成，当前包含：

- 概览、世界观、人物、剧情；
- 正文章节树，显示 Source / CANON 和 Draft 状态；
- 连续性账本入口占位；
- 九个 `book_profil` 分析维度；
- Revision 与 Skills / References 的后续接入位。

### CENTER：AI Authoring Workspace

中心默认显示作者画像或 `ChapterContext`。Chapter 页面支持 `BEFORE_CHAPTER`、`Chapter Delta`、`AFTER_CHAPTER` 三个只读视图，并保留原始上下文折叠区。没有状态投影时显示真实缺口，不用最新状态填充历史，也不展示 mock score。

### RIGHT：正文 / Draft 编辑器

Source 章节由 Book Library 提供并带 `readonly`；Web 不允许覆盖原文。Draft 显示 `PROVISIONAL`，保存后回到 `DRAFT` 并清空旧验证报告，需要重新验证。任何 Draft 保存都不等于批准或写入 Canon。

## 4. ChapterContext 与章节时间旅行

统一查询模型至少包含：

```text
book_id
edition_id
chapter_id
chapter_ordinal
chapter_status
selected_chapter_anchor
before_state
chapter_delta
after_state
source_content
draft_content
validation
narrative_context
```

章节点击只改变 `selected_chapter_anchor`。查询层只使用同一个 `book_id + edition_id` 和既有事件 / chapter anchor：

```text
Authoritative Book / Edition State
        + Source-Derived Baseline
        + append-only Canon Events
        + chapter/event anchors
        ↓
Historical Projection (read-only)
        ↓
ChapterContext
```

Workbench 不会因为导航而切换数据库、覆盖 current runtime、重写 Canon Projection、创建 Canon Event、修改 Runtime Baseline、修改 Edition 或回滚当前状态。`ChapterContext` 由 `src/novel_authoring/web/workbench.py` 聚合，前端不自行比较状态。

## 5. 既有 Source Book 的能力缺口

当前 `library/cable-survival-test` 是 Source-first 的既有书：有 100 个不可变 Source 章节和 `book_profil`，但没有逐章 Canon Commit / Canon Event，也没有可供每章重放的 Source-Derived Runtime State Projection。它的当前数据库状态不能证明第 N 章之前的逐章人物、资源、能力或伏笔状态。

因此 Workbench 对这类章节明确返回：

```text
SOURCE_CHAPTER_STATE_PROJECTION_MISSING
```

并说明：当前只有 Source 章节，不能把最新状态冒充历史截面。当前实现不伪造 Canon Commit，也不把空 Delta 当成“本章没有变化”。

后续最小实现应是一个独立的 `Source Chapter State Projection` read model：

1. 以 immutable source span / chapter boundary 为证据输入；
2. 由离线初始化流程生成逐章、可追溯的 state observation / delta artifact；
3. 每条观察保留 source span、章节 ordinal、信息状态和不确定性；
4. 只作为 Source-derived projection 读取，不写入 `events`、不伪造 Canon、不替代作者批准；
5. 生成后由状态机标记版本与 stale 条件，Source 变化时重新初始化或刷新。

在该 read model 建立前，`BEFORE / AFTER / Delta` 的空态是正确结果，不是缺省回退到第 100 章。

## 6. Draft 与 Canon 的边界

如果 Canon 到第 60 章、Draft 为第 61 章：

- `before_state` 只能是已存在的 Canon 截面；
- Draft 的 `state_changes` 只能显示在 `PROVISIONAL_DRAFT_DELTA`；
- `after_state` 标记 `PROVISIONAL_DRAFT_ONLY`，不得变成 `CANON_EVENT_PROJECTION`；
- 当前 Canon boundary、events、Runtime 和 Edition 保持不变；
- 只有现有批准 / 提交流程才能产生 Canon Commit。

Revision Edition 后续沿用同样规则，分别显示 base state、edition effective state 和 revision provisional state，不把不同 Edition 混在一起。

## 7. 后续切片

- W2：接入现有 Runtime / Story Atlas 的作者可读查询，按 ChapterContext 的 anchor 返回人物、关系、能力、资源、知识、世界规则、Threads、Promises、Narrative Debt 和 Portfolio；
- W3：在中心接入现有 continuation / revision handoff、Boundary、Candidate、Contract 和 Validator application services；
- W4：补齐 Source Chapter State Projection 的离线生成、证据和 stale 审核；
- W5：接入 Revision Workbench、可审计 Diff、作者确认与导出，不改变 `book/` 只读边界。

每个阶段都必须先通过 query-only 导航回归，再增加显式 command。没有作者明确批准时，草稿停在 `VALIDATED` 或更早状态，不产生 Canon Commit。

## 8. W1 验收

最小验收覆盖：

1. 打开真实 Library Book，能看到 Book、Edition、Source chapter tree 和已有 `book_profil`；
2. 点击章节只改变 URL / `selected_chapter_anchor`，右侧正文与中间 ChapterContext 同步；
3. Source 文本为 readonly，Draft 文本可显式保存且验证状态失效；
4. 连续访问多个章节后，Canon events、projection metadata、Edition 和当前运行状态行数不变；
5. Source-only 书显示 `SOURCE_CHAPTER_STATE_PROJECTION_MISSING`，不伪造历史状态；
6. `novel web doctor` 能检查 FastAPI 路由、模板、静态资源与原生前端模式。
