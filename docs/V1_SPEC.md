# TheGreatNovel V1 实现合同

## 目标

交付一个由 Codex 聊天主持、确定性 Python 引擎结算的本地可玩首版。玩家通过一句话创建世界，在多回合中观察规则、使用非对称杠杆、积累成长、改变势力关系，并可随时结束生成小说。

## 边界

- Python 标准库实现，不要求联网或外部模型密钥。
- `src/tgn/` 是权威引擎；`AGENTS.md` 是 Codex 聊天宿主协议。
- `runtime/saves/`、`runtime/manuscripts/`、`runtime/exports/` 是运行产物，不写入 `inspirations/`。
- AI/Codex 可将自由文本映射到一个行动并润色叙事，但不能直接编辑存档。
- 引擎必须提供确定性后备叙事，确保自动保存与导出不依赖润色成功。

## 玩家流程

```text
开始游戏
  -> 选择 zh-CN（默认）/fr-FR/en/ar
  -> 用一句话描述世界
  -> 创建 Campaign 与序章，原子保存
  -> Codex 展示状态、叙事与合法行动
  -> 玩家自由输入，Codex 映射为一个 action_id
  -> 引擎校验并结算玩家行动 + 世界 tick
  -> 原子保存事件与后备章节
  -> 可选写入严格基于结果包的润色章节
  -> 重复或结束游戏
  -> 自动导出 novel.md
```

## 模块责任

- `models.py`：dataclass/JSON 数据合同与不变量。
- `locales.py`：四语言固定 UI、规则名和后备叙事词条。
- `worldgen.py`：从 premise + seed 生成控制轴、杠杆、势力、竞争者、机会与隐藏矛盾。
- `engine.py`：合法行动、确定性随机、单行动结算、世界 tick、解锁与层级扩展。
- `persistence.py`：原子 JSON 存档、事件哈希链、活动 Campaign 指针、读取校验。
- `narrative.py`：事实包、后备章节、AI 润色登记与原创性保护提示。
- `exporter.py`：只根据玩家已知历史导出 Markdown 小说。
- `cli.py` / `__main__.py`：供 Codex 调用的稳定 JSON 协议。

## CLI 协议

所有业务命令在成功时向 stdout 输出单个 UTF-8 JSON 对象；错误写为结构化 JSON 并以非零码退出。

项目内聊天宿主使用根目录 `game.py`，安装包后可将 `python game.py` 等价替换为 `python -m tgn`。

```text
python game.py languages
python game.py new --locale zh-CN --premise-file runtime/inbox/premise.txt [--seed 123]
python game.py status [--campaign ID]
python game.py act --action ACTION_ID [--campaign ID]
python game.py narrate --turn N --file runtime/drafts/ID/turn-N.md [--campaign ID]
python game.py finish [--campaign ID]
python game.py export [--campaign ID]
python game.py verify [--campaign ID]
python game.py list
```

`new`、成功的 `act` 与 `finish` 都必须完成保存；`finish` 必须自行导出。`act` 只接受当前结果包列出的一个 `action_id`。

## 首版状态与成长

- 资源：体力、洞察、核心资源、影响力。
- 能力：观察、采集/生产、转化、谈判、组织、规则利用。
- 世界控制轴决定主要资源、常见风险、势力行为和杠杆转化公式。
- 非对称杠杆消耗洞察与风险敞口，把核心资源按高于普通人的效率转化为永久能力/资产；精通会提高下一轮效率。
- 行动解锁必须由能力、资产、关系或层级门槛决定。
- 每个 `act` 后推进一个世界 tick：势力施压或合作、竞争者成长、机会剩余时间变化。
- 达到控制分数门槛后可执行跃迁行动；跃迁保留玩家状态并增加新层级规则。

## 叙事合同

- 近距离第三人称；一回合一个目标与因果闭环。
- 结构：威胁/机会 -> 判断 -> 行动 -> 可量化结果 -> 身体或社会后果 -> 尾钩。
- 每回合最多揭示一个新核心规则；不得泄露隐藏状态。
- 至少呈现一项可积累变化以及世界对玩家变化的回应。
- 只能使用结果包 `public_facts` 中的事实；润色不能新增奖励、成功、人物、关系或伤亡。
- 不复用 `inspirations/` 的专名、原句、UI 文案和连续情节。

## 验收命令

```powershell
python -m unittest discover -s tests -v
python game.py languages
python game.py new --locale zh-CN --premise-file runtime/inbox/premise.txt --seed 101
python game.py verify
python game.py act --action observe_rule
python game.py verify
python game.py finish
python game.py export
```

自动化测试必须把运行目录指向临时目录，并覆盖四语言、确定性、非法行动无副作用、原子存档/篡改拒绝、NPC tick、成长解锁、层级扩展及小说导出。
