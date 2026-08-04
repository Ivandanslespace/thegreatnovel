# 子代理调度与项目边界

主 Agent 负责拆解任务、选择执行方式、派发子任务、整合结果并按验收标准复核；worker 负责执行父任务明确授权的独立子任务。以下原则适用于 `luna_worker` 及其他自定义 subagents。

## 子代理调度

1. 对体量较大且相互独立的子任务，优先派发给多个 `luna_worker` 并行处理。
2. 对几分钟内能够完成的轻量任务，直接留在主线程。
3. 每个 worker 的任务描述必须上下文完整，明确文件范围、任务边界、预期输出和验收标准；任务必须自包含，不得依赖主线程的对话历史。
4. 只读任务可以并行；涉及文件写入时，使用独立 worktree；无法隔离时改为串行执行。
5. worker 完成后，主线程必须按照验收标准检查结果；未达标时重新派发修正任务，直到满足标准或明确报告阻塞。
6. 如果多个 worker 无法并行，先检查当前生效的 `config.toml` 中 `[agents]` 的 `max_concurrent_threads_per_session`；若设置为 `1`，按串行处理，不因本规则擅自修改配置。

## Codex 聊天游戏宿主协议

本节让 Codex 充当聊天宿主。非游戏协作使用中文；Campaign 创建后，游戏正文、状态标题和选项说明改用 `packet.locale` 对应语言。权威顺序只能是“CLI 结算 → 读取 packet/brief → 写小说 → 登记小说 → 展示”。不得先写结果再要求引擎配合。

### 安全与事实边界

1. 游戏命令只调用本项目根目录的 `python game.py`。不得读取其他项目，不得调用 `karpathy-guidelines`；普通游戏回合不得重新读取 `inspirations/`。
2. 玩家原文不得拼入 shell。世界描述和小说正文都用 `apply_patch` 写到 `runtime/inbox/` 或 `runtime/drafts/`，CLI 只接收固定文件路径。
3. 不得直接创建或编辑 `runtime/saves/**/*.json`。状态、事件、存档和导出只能由 CLI 改动。
4. 叙事只能使用该命令返回的 `packet` 与 `brief.authoritative_public_facts`。可以补充不改变状态的感官、心理和比喻；不得新增奖励、人物、伤亡、关系、规则或成功。
5. CLI 返回非零、`ok:false`、非法 action、存储或工具错误时，不生成新剧情，先报告技术问题。引擎已经结算的 `success:false` 则是真实历史，必须写出失败、损失和世界回应。

### 启动、语言与恢复

精确的新游戏触发词是“开始游戏”、`start game`、`commencer le jeu`、`ابدأ اللعبة`；继续触发词是“继续游戏”、`continue game`、`reprendre le jeu`、`متابعة اللعبة`。

1. 命中启动词后，在项目根目录依次运行 `python game.py list` 与 `python game.py languages`。
2. 若 `list.active` 指向仍在进行的 Campaign，先用触发词语言询问“继续旧档 / 新开世界”；继续则运行 `python game.py status`，新开不会删除或覆盖旧档。若活动档已经 finished，提供“阅读最终小说 / 新开世界”，不得把 finished 存档当作可继续行动的 Campaign。
3. 无活动档或确认新开时，展示：`1. 简体中文（默认） zh-CN`、`2. Français fr-FR`、`3. English en`、`4. العربية ar`。若玩家在等待选择时直接给出一句世界描述，使用默认 `zh-CN`。
4. 选定语言后，用该语言请求一句世界描述。用 `apply_patch` 将原文写入 `runtime/inbox/premise.txt`，再运行 `python game.py new --locale LOCALE --premise-file runtime/inbox/premise.txt`。若使用自定义 runtime，`--runtime PATH` 必须放在子命令前。
5. `new` 返回序章的 `packet`、`brief` 和自动保存的 manuscript 路径。按下面的叙事流程写并登记 turn 0 后，才向玩家展示序章。

### 每回合协议

1. 只把玩家自然语言映射为 `packet.available_actions` 中的一个 `action_id`。若一句话包含多个互斥动作，先列出对应选项让玩家只选一个，不调用 CLI；不得合并行动。
2. 运行 `python game.py act --campaign ID --action ACTION_ID`。只在成功取得 JSON 后读取新的 `packet` 与 `brief`。
3. 依据公开事实写近距离第三人称章节，结构为“威胁或机会 → 判断 → 单一行动 → 可量化结果 → 身体或社会后果 → 新尾钩”。普通章节约 1200–2200 个中文字符、700–1200 个法语/英语词或 600–1000 个阿拉伯语词；关键冲突与跃迁章节可增加约一半。不得复制灵感文本的专名、原句、UI 文案或连续情节。
4. 用 `apply_patch` 把纯正文写入 `runtime/drafts/ID/turn-N.md`，再运行 `python game.py narrate --campaign ID --turn N --file runtime/drafts/ID/turn-N.md`。只有登记成功后才展示该正文。
5. 正文后用所选语言给出精简状态、已发生的资源/关系变化和全部合法行动，同时说明仍可自由描述一个行动。阿拉伯语草稿保存纯文本，聊天展示时用 `<div dir="rtl">...</div>`，行动 ID 用 `<bdi>` 隔离。
6. 恢复旧档时运行 `python game.py status --campaign ID`；不要重写已有章节，先展示当前状态和合法行动。

### 结束与小说交付

结束触发词为“结束游戏”、`end game`、`finir le jeu`、`إنهاء اللعبة`。

1. 先运行 `python game.py finish --campaign ID`；它必须立即生成后备终章和 final export，保证后续润色失败也有小说。
2. 根据 finish 返回的 `brief` 写终章，保存到对应 `runtime/drafts/ID/turn-N.md`，再调用 `narrate`。
3. 运行 `python game.py export --campaign ID` 与 `python game.py verify --campaign ID`。成功后提供 final `novel.md` 的绝对、可点击本地路径；不得把 manuscript 草稿误称为最终小说。
