# TheGreatNovel

AI 原生的长线成长叙事游戏：玩家在聊天中做出选择，确定性引擎结算后果，
主持人（Agent）把已成事实的世界历史写成一部网文风格的长篇小说。
不是"会写小说的聊天机器人"，而是"会留下历史的世界"。

## 如何开始

在 Qoder 聊天窗口直接说：**开始游戏**。

Agent 会读取仓库根目录的 [AGENTS.md](AGENTS.md)，成为游戏主持人：
询问你的游戏语言与世界基调，创建世界，然后逐回合为你呈现面板、
行动选项与章节叙事。

## 支持语言

中文（默认）/ English / Français / العربية（`--lang zh|en|fr|ar`）。
引擎面板、错误提示与结算面板均按所选语言本地化。

## 核心设计

- **LLM at the edges, deterministic engine at the center**：主持人只叙事与提案，
  世界事实的唯一来源是 CLI 的 JSON 输出；
- 设计不变量见 [CONSTITUTION.md](CONSTITUTION.md)（控制缺口 → 看懂规则 →
  非对称杠杆 → 复利成长 → 关系反转 → 阶层跃迁 → 更大的世界）。

## 技术说明

- Node ≥23.6 原生 TypeScript（`node src/cli.ts` 直跑，需原生 type stripping），
  **零运行时依赖**；
- `npm run tgn -- <命令>` 或 `node src/cli.ts <命令>`；`npm test` 运行引擎与
  CLI 测试，`npm run typecheck` 类型检查；
- 存档在 `worlds/<slug>/`（事件溯源 events.jsonl，`tgn verify` 可重放校验）。

## 目录速览

```
AGENTS.md      主持人手册（Agent 的人机界面）
CONSTITUTION.md  宪章（设计不变量）
src/           CLI 与确定性引擎
inspirations/  开局公式参考素材
worlds/        世界存档与 proposal 模板/示例
temps/         临时文件（章节草稿等）
```
