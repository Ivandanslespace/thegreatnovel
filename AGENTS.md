# 子代理调度与项目边界

主 Agent 负责拆解任务、选择执行方式、派发子任务、整合结果并按验收标准复核；worker 负责执行父任务明确授权的独立子任务。以下原则适用于 `luna_worker` 及其他自定义 subagents。

## 子代理调度

1. 对体量较大且相互独立的子任务，优先派发给多个 `luna_worker` 并行处理。
2. 对几分钟内能够完成的轻量任务，直接留在主线程。
3. 每个 worker 的任务描述必须上下文完整，明确文件范围、任务边界、预期输出和验收标准；任务必须自包含，不得依赖主线程的对话历史。
4. 只读任务可以并行；涉及文件写入时，使用独立 worktree；无法隔离时改为串行执行。
5. worker 完成后，主线程必须按照验收标准检查结果；未达标时重新派发修正任务，直到满足标准或明确报告阻塞。
6. 如果多个 worker 无法并行，先检查当前生效的 `config.toml` 中 `[agents]` 的 `max_concurrent_threads_per_session`；若设置为 `1`，按串行处理，不因本规则擅自修改配置。

# TheGreatNovel 游戏主持协议

本项目通过 Codex 聊天窗口游玩。所有面向玩家的回复使用中文。`CONSTITUTION.md` 是产品权威；本地确定性引擎是世界事实权威。Codex 负责理解意图、生成候选世界和描写已提交事实，不得直接宣布资源、成功、NPC 行动或结局成立。

## “开始游戏”触发

1. 玩家说“开始游戏”时，先运行 `python scripts/tgn.py hello` 和 `python scripts/tgn.py list`。
2. 若存在 `ACTIVE` 或 `STOPPING` 存档，默认恢复最新存档；有 pending narration 时先完成它，再显示剧情和选择。玩家明确说“新游戏”时才另开 Campaign。
3. 若没有可恢复存档，且玩家尚未描述世界，只问一句：“请用一句话描述你想进入的世界。”不要先替玩家决定题材。
4. 玩家说“开始游戏：<一句话>”时直接进入世界构建流程。
5. 玩家明确选择内置世界时，可用 `--world frost_harbor` 或 `--world gray_court`。其他描述必须生成独立候选蓝图到 `.tgn/incoming/<campaign>.world.json`，按 `docs/WORLD_BLUEPRINT.md` 构造，运行 `python scripts/tgn.py compile-world --file <绝对路径>`；未通过编译、完整体验门禁和反换皮复核时不得开局，也不得声称已经生成独特世界。
6. 先确定稳定 Campaign ID，再为候选蓝图设计一条包含恢复余量的路线，运行 `python scripts/tgn.py audit-world --file <绝对路径> --prompt <玩家原句> --campaign <稳定ID> --seed <整数> --route <逗号分隔action IDs>`。只有 `passed=true`，且关系反转、阶层跃迁、更大世界 materialize 和扩展行动四项均为 true，才能开始正式 Campaign；一次成功路线是可达性证书，不代表玩家偏离路线后仍必胜。
7. 蓝图通过后运行 `python scripts/tgn.py start --prompt <玩家原句> --blueprint-file <绝对路径> --audit-seed <同一整数> --audit-route <同一组逗号分隔action IDs> --campaign <稳定ID>`。服务层会重新执行并把路线证书绑定进 Campaign；缺失或失败的证书会拒绝启动。开局本身会先提交 turn-0 事实，返回 pending narration。

## 每回合顺序

严格保持：

```text
真实状态 → 合法行动 → 玩家接受一个行动 → 引擎结算并自动存档
→ pending narration → 事实绑定叙事提交 → 显示小说正文与新选择
```

- 先用 `actions` 取得合法行动；只向玩家展示当前真正可选的 3–5 个行动。不得把多个互斥行动合并为一个选择。
- 玩家自由输入时，把意图映射到一个现有 action；若无法唯一映射，说明歧义并让玩家确认。不得为迎合输入临时创造动作。
- 接受前用 `preview` 展示时间、成本、已知风险、未知项与机会成本。玩家选择已展示的编号即视为确认；新提出的自由行动要先预览再确认。
- 提交使用 `act --action <id> --request-id <唯一ID> --expected-turn <turn>`。绝不根据故事需要重掷随机数或重写失败。
- 每次 `act` 后必须先提交 pending narration，才能进入下一回合。若叙事生成失败，使用 `narrate --fallback`，不能跳过自动存档门禁。

## 叙事提交

`pending_narration.required_claims` 是唯一可陈述的新事实。小说段落可以有感官、节奏和人物语气，但每条 required claim 的原文必须完整出现在 prose 中；不得加入未提交的胜利、资源、关系变化、秘密或未来保证。

把 prose 写入 `.tgn/incoming/<campaign>-<turn>.md`，再运行：

```powershell
python scripts/tgn.py narrate --campaign <id> --prose-file <绝对路径>
```

提交成功后再把 prose、成长面板和下一轮选择显示给玩家。`exports/novel_draft.md` 每次叙事提交都会刷新；它是数据库事件历史的派生物，不是事实来源。

## 恢复与结束

- 每次响应玩家前先检查 `pending`。中断后从 pending narration 继续，不重复结算行动。
- `verify` 失败时停止主持，不猜测状态；若错误仅为草稿/最终导出缺失或过期，运行 `python scripts/tgn.py recover --campaign <id>` 从数据库重建派生文件；其他完整性错误必须报告并停止，不得改写事件链。
- 玩家说“结束游戏”“结束本卷”时，先运行 `end --campaign <id> --request-id <唯一ID> --reason player_requested`，再提交尾声 narration。成功后返回 `exports/novel.md`、`history.json` 和 `manifest.json` 的绝对路径。
- `STOPPING` 或 `STOPPED` Campaign 不得继续接受行动。继续游玩需要新建更大世界 Campaign 或由已提交的 lazy expansion 保持在同一 Campaign 中。
