# 《全民纜車求生，我一級一個三選一》蒸馏报告

## 结果

已按指定 `distill-novels` Skill 的 `create + all + standard` 路径，为用户给出的 `book/测试小说.md` 建立一份私有、来源可追溯的写作知识库。来源数量为 1；确定性预处理识别 100 个实际文本片段，无编码警告。

输出保存机制、状态、因果和可调控制项，不保存长篇原句；它不是原文替代品，也没有修改 `book/`、Library Canon 或 Edition 状态。

## 验证结果

- `prepare_sources.py`：通过；1 个来源、100 个章节片段、无编码警告。
- `validate_distilled_skill.py`：通过；32 个 Markdown、16 个代表性章节卡片、来源定位边界通过。
- 内部 Markdown 链接：通过。
- 章节索引脚本、定位归一化脚本和知识库校验脚本：Ruff 与 Python 编译检查通过。
- `book/测试小说.md`：未修改。

## 交付结构

| 入口 | 用途 |
|---|---|
| [SKILL.md](SKILL.md) | 四种动作、路由和原创护栏 |
| [sources.md](sources.md) | 来源、快照范围和元数据警告 |
| [books/book-01-82fe54fd/overview.md](books/book-01-82fe54fd/overview.md) | 作品前提、八段结构和代表章节 |
| [worldbuilding.md](worldbuilding.md) | 规则、资源、制度与威胁边界 |
| [characters.md](characters.md) | 人物目标、决策模式和关系接口 |
| [plot.md](plot.md) | 主线因果、伏笔状态和截断点 |
| [style.md](style.md) | 中性文风参数与检测信号 |
| [narrative.md](narrative.md) | POV、信息差和揭示策略 |
| [dialogue.md](dialogue.md) | 频道、交易与现场对话机制 |
| [pacing.md](pacing.md) | 章节/场景推进与张力曲线 |
| [themes.md](themes.md) | 生存、人性、信息和规则的竞争性答案 |
| [continuity.md](continuity.md) | 时间、资源、知识、能力和未闭环账本 |
| [synthesis.md](synthesis.md) | 跨维度因果模型 |
| [craft-controls.md](craft-controls.md) | 设计、修订、检查时的控制面板 |
| [chapter-index.md](books/book-01-82fe54fd/chapter-index.md) | 100 段章节导航与行号索引入口 |

## 已知警告

- front matter 写有 294 章，但当前文件实际识别到 100 段；不能把本包当成全书蒸馏。
- `segment-0096` 是关于章节错乱的编辑说明，不是故事章节；不应进入情节因果或人物状态。
- 标题编号不连续，且有两个“第37章”；所有判断使用 segment/行号，不用标题编号推断缺章。
- 文本中存在编辑残留、个别重复句和标点/词语粘连；文风统计只作趋势控制，不作质量分数。
- 若继续分析完整 294 章，应创建新的来源快照/manifest，并把本包作为旧版本保留，不能静默覆盖。

## 调用示例

```text
使用 $cable-survival-craft analyze 苏牧如何把信息优势转成资源与战斗优势，并列出 segment/行号。

使用 $cable-survival-craft check 新章节的每日降落、经验、突破符、库存、夜间规则和人物知识状态。

使用 $cable-survival-craft design 一个原创的“移动安全屋 + 有限落点 + 规则型能力”开篇，只使用抽象机制。

使用 $cable-survival-craft revise 这段求生战斗，让每次动作都改变位置、资源、伤势、信息或关系中的至少一项。
```
