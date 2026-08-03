# TheGreatNovel V1（TGN_Qoder）

AI 原生长线成长叙事游戏：**LLM at the edges；deterministic engine at the center**。

- 玩家用一句话描述想进入的世界；Agent（读取 `AGENTS.md`）据此起草 World Blueprint（声明式 JSON）。
- 引擎是**世界无关的通用原语解释器**：资产/时间/行动/规律/知识事实/势力计划/不可逆/阶层门槛/离屏 tick/受约束扩展，全部由 Blueprint 数据表达。
- **零运行时依赖**：Node ≥ 24 原生运行 TypeScript（type stripping），测试用内置 `node:test`。
- **开局选择语言**（`zh` / `en` / `fr` / `ar`，缺省 `zh`）：语言是表现层元数据，只影响小说与结算文案的呈现，不影响任何结算数值与确定性。

## 最高约束

`CONSTITUTION.md`（不可妥协核心体验宪章）是一切世界与功能的最高约束：
控制缺口 → 看懂规则 → 非对称杠杆 → 复利控制 → 关系反转 → 阶层跃迁 → 更大的世界。

## 快速开始

```powershell
# 校验演示世界 Blueprint
npm run cli -- validate-blueprint --file worlds/echo-harbor.blueprint.json

# 开局（存档写入 saves/<世界名>/；--language 可选，缺省 zh）
npm run cli -- new --blueprint worlds/echo-harbor.blueprint.json --world echo-harbor --seed 42 [--language <zh|en|fr|ar>]

# 回合循环
npm run cli -- status
npm run cli -- act --id gather-rumors
npm run cli -- observe --scope laws
npm run cli -- chapter-add --title "第一回合" --file temps/chapter-001.md

# 结束并合成完整小说 novel.md
npm run cli -- end --reason "阶层跃迁完成"
npm run cli -- verify
```

CLI 的 stdout 永远是单行 JSON：`{"ok":true,"data":...}` 或 `{"ok":false,"error":{...}}`。

## 测试

```powershell
npm test
```

覆盖：rng 确定性、条件求值、结算管线、离屏 tick、Blueprint 校验、杠杆检验（`leverage.enabled=false` 时合法行动集与最优路径断言式改变）、存档篡改检测、固定种子完整一局 e2e（至阶层跃迁、novel.md 生成、verify 通过）。

## 目录结构

```
CONSTITUTION.md   不可妥协核心体验宪章
AGENTS.md         游戏主持协议（Agent 入口）
worlds/           World Blueprint（纯数据）
src/              通用引擎（types/rng/conditions/save/knowledge/blueprint/tick/resolve/expansion/chapter/novel/cli）
src/__tests__/    node:test 测试
saves/            运行时存档（入库）：
                  ├─ blueprint.json        开局冻结的 Blueprint（回放自足）
                  ├─ state.json            当前状态（schema v2，不含 history 数组）
                  ├─ state.json.sha256     校验和（易变派生文件，不入库）
                  ├─ state.prev.json       上一次落盘备份（易变派生文件，不入库）
                  ├─ history.jsonl         唯一审计源（append-only，schema v2 起 state 只留游标）
                  ├─ manifest.json         存档元信息（开局时间/种子/最近动作/章节数）
                  ├─ chapters/             Agent 提交的章节 Markdown
                  └─ novel.md              end 时合成的完整小说
```
