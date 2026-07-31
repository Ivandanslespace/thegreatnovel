# Autoplay Test Engine - 自动播放测试系统

## 概述

这是一个专为互动小说引擎设计的自动化测试系统，用于发现"单个函数都对，但跑 30 轮以后机制互相卡死"的问题。

完全不需要 LLM API，直接使用 Python import 方式快速测试机制交互。

## 架构

```
tools/
├── autoplay_test.py          # 核心测试引擎 (单局模拟)
└── autoplay_suite.py         # 批量测试运行器 (多局压力测试)

tests/
└── autoplay/
    └── fixtures/             # 测试存档和固定数据

autoplay_runs/                # 所有测试输出
    ├── run_xxx/
    │   ├── turns.jsonl      # 每轮详细数据
    │   ├── run.json         # 汇总统计
    │   ├── initial_state.json
    │   ├── final_state.json
    │   └── report.md        # Markdown 审计报告
    └── suite_xxx_summary.md # 批量测试汇总报告
```

## 使用方式

### 单个测试运行

```bash
# ABC 固定序列测试（推荐用于回归测试）
python tools/autoplay_test.py --save saves/锈铁方舟 --turns 50 --policy abc

# 随机策略测试
python tools/autoplay_test.py --save saves/锈铁方舟 --turns 100 --policy random --seed 42

# 激进策略测试（优先战斗/探索）
python tools/autoplay_test.py --save saves/锈铁方舟 --turns 50 --policy aggressive

# 建造者策略测试
python tools/autoplay_test.py --save saves/锈铁方舟 --turns 100 --policy builder
```

### 批量测试

```bash
# 一次性运行多个策略
python tools/autoplay_suite.py --turns 50
```

选项:
- `--save`: 测试存档目录（默认 `saves/锈铁方舟`）
- `--turns`: 每局回合数（默认 50）
- `--policies`: 策略列表，逗号分隔（默认 `abc,random,aggressive,builder`）
- `--seed`: 随机种子（默认 42）

## 策略类型

### 1. ABCPolicy
循环选择 A→B→C→A...
- **用途**: 回归测试、确定性 smoke test
- **特点**: 可复现、覆盖面中等

### 2. RandomPolicy
随机选择可用选项
- **用途**: 发现固定轨迹没遇到的问题
- **特点**: 需要设置 seed 保证可复现性

### 3. AggressivePolicy
优先 COMBAT、EXPLORATION、TRAVEL
- **用途**: 压力测试、边界条件
- **特点**: 触发战斗、死亡、资源耗尽

### 4. BuilderPolicy
优先 BUILD、BASE_MANAGEMENT、SOCIAL_INTERACTION
- **用途**: 长期系统测试
- **特点**: 测试基地发展、社会互动

## 遥测记录

每一轮都会记录完整状态：

```json
{
  "decision": 17,
  "requested_choice": "C",
  "actual_choice": "A",
  "reason_fallback": "C unavailable",
  "before": {
    "turn": 21,
    "world_turn": 15,
    "day": 2,
    "location": "station_03",
    "hp": 42,
    "mental": 68
  },
  "options_before": {
    "A": "搜索废墟",
    "B": "返回基地",
    "C": "和阿苔交谈"
  },
  "result": {
    "action_type": "EXPLORATION",
    "outcome": "普通成功",
    "time_cost": 120
  },
  "after": {...},
  "events_created": [...]
}
```

## 自动审计规则

系统会自动运行以下检测规则：

### P0 问题 (必须修复)

1. **STUCK_LOOP** - 连续 5 轮相同行动
2. **NO_AVAILABLE_ACTION** - 无任何可选选项
3. **TIME_NOT_ADVANCING** - 连续 10+ 次零时间行动
4. **ENCOUNTER_OPEN_END** - Encounter 进入但未退出
5. **PUBLIC_SYSTEM_PEER_DORMANT** - 公共系统推进但同行代理为 0

### P1 问题 (建议修复)

1. **TIME_JUMP_ANOMALY** - 异常时间跳跃 (>2 小时)
2. **MECHANISM_UNREACHABLE** - 重要机制从未触发
3. **OPTION_C_UNAVAILABLE_TOO_OFTEN** - C 位置可用性过低 (<30%)

### P2 问题 (优化建议)

1. **HIGH_OPTION_REPETITION** - 选项重复率过高 (>60%)
2. **HIGH_SEVERE_FAILURE_RATE** - 严重失败比例过高 (>15%)

## 输出文件

### turns.jsonl
每行一个 JSON 对象，包含完整决策历史

### run.json
汇总统计和问题列表

### report.md
Markdown 格式审计报告，包括:
- Result 概览
- Coverage 机制覆盖率
- Findings 发现的问题
- Final State 最终状态

示例:

```markdown
# Autoplay Audit Report

## Result
- 决策完成：50/50
- P0 问题：2
- P1 问题：3
- P2 问题：1

## Coverage
- COMBAT: 5
- EXPLORATION: 12 ⚠
- BUILD: 0 ⚠
- SOCIAL_INTERACTION: 8

## Findings

### 🔴 [P0] MECHANISM_UNREACHABLE
50 轮内从未触发：BUILD

### 🟠 [P1] HIGH_OPTION_REPETITION
选项重复率过高：68.5%
```

## 集成到 AGENTS.md

在 `AGENTS.md` 中添加:

```markdown
When asked to run a game audit:

1. Create an isolated copy of the designated test save.
2. Run:
   python tools/autoplay_suite.py --turns 50
3. Never modify the original save.
4. Read:
   - report.md for each run
   - summary_report.md
5. Inspect relevant source code for every P0/P1 warning.
6. Classify findings by priority level.
7. Do not fix code unless explicitly requested.
```

以后只需说:
> "跑一次完整 50 轮游戏审计。"

Agent 就会自动执行完整流程。

## 扩展建议

### 第二阶段：LLM 玩家

当基础系统稳定后，可以考虑增加"LLM 玩家"，让模型：
- 理解剧情上下文
- 故意做奇怪操作
- 合并多个行动
- 测试叙事连贯性

但这不是必须的，Python 玩家的统计价值已经很高。

### 第三阶段：更复杂策略

可以添加:
- **SocialBuilder**: 优先社交关系发展
- **Explorer**: 优先探索和发现
- **RiskManager**: 平衡风险和收益
- **Chaos**: 故意制造混乱场景

## 常见问题

### Q: 为什么要用 Python 而不是直接调用 API？

A: 
1. 不需要 API key
2. 速度更快（直接函数调用 vs HTTP 请求）
3. 可以直接访问 state 做 diff
4. 可以捕获 exception 并保存现场
5. 可以读取 SQLite 验证一致性

### Q: 为什么是 50 轮？

A: 
- 太短（10 轮）：不够暴露机制问题
- 太长（100+ 轮）：运行时间长，迭代慢
- 50 轮是一个好的平衡点，足够发现大部分问题

### Q: 如何添加新的审计规则？

A:
1. 在 `AutoAuditor` 类中添加新方法
2. 在 `audit()` 中调用该方法
3. 返回符合格式的 finding 字典

```python
def _detect_my_new_issue(self):
    findings = []
    # ... detection logic ...
    if issue_found:
        findings.append({
            "level": "P1",
            "category": "MY_NEW_ISSUE",
            "message": "描述信息",
        })
    return findings
```

## 性能

- 50 轮 ABC 策略：约 5-10 秒
- 100 轮随机策略：约 15-20 秒
- 批量测试 (4 种策略 × 50 轮): 约 30-40 秒

实际取决于存档复杂度和逻辑密度。

## 维护建议

1. **定期运行**: 每次重大修改后运行
2. **CI 集成**: 可以加入 CI 流程自动检测 regressions
3. **基线对比**: 保存通过测试的 baseline，对比新结果
4. **覆盖关键路径**: 确保主要机制都被触达到

## License

与项目主许可证一致。
