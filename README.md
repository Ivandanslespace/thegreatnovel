# TheGreatNovel

TheGreatNovel 是一款通过 Codex 聊天窗口游玩的、以确定性世界模拟为核心的长线成长叙事游戏。

当前版本从 `CONSTITUTION.md` 重新设计，不继承任何旧实现。游戏状态、行动合法性、成本、随机结果、NPC 推进、存档与回放由本地引擎决定；Codex 只负责理解玩家意图、提出受约束的世界蓝图，以及描写已经提交的事实。

玩家在本项目的**新 Codex 任务**中说“开始游戏”即可进入开局流程；若直接说“开始游戏：我想进入……”，Codex 会立即构建并校验世界。新任务很重要，因为 Codex 在任务开始时读取 `AGENTS.md`。

## 已实现的首版体验

- 严格编译的数据世界蓝图，以及面向任意一句话的 Codex 候选世界生成边界；
- 确定性行动预览、成本、风险、随机结算、事件重放和 HMAC 预览令牌；
- 随时间离屏推进的 NPC / 世界过程、机会窗口、关系反转、阶层跃迁与 Lazy Expansion；
- 玩家知识投影，隐藏目标、种子和内部调度状态不会进入叙事上下文；
- SQLite 事务存档、哈希事件链、幂等命令、损坏检测和派生导出恢复；
- turn-0 序章、每回合事实绑定叙事、自动刷新 `novel_draft.md`；
- 结束本卷后生成 `novel.md`、完整 `history.json` 和带来源哈希的 `manifest.json`。

项目附带两个经过完整路线实玩的结构化世界：

- `frost_harbor`：理解供给、维护债和潮汐，把手工救火复利成生产与分配权；
- `gray_court`：理解证据、期限和承诺，把被审查的申请人复利成仲裁条件制定者。

它们既是可直接游玩的世界，也是新世界蓝图的 schema 参考，不是对任意玩家描述的换名词 fallback。

## 本地验证入口

无需安装包：

```powershell
python scripts/tgn.py hello
python scripts/tgn.py worlds
python scripts/tgn.py list
```

直接启动已审核世界的开发示例：

```powershell
python scripts/tgn.py start --prompt "我想在潮汐与盐雾支配的港口重建供给网络" --world frost_harbor --campaign my-frost
```

命令输出统一为 `tgn.local.v1` JSON；Codex 负责把它转换成小说式正文和清晰选择。完整主持顺序见 [docs/PLAY_PROTOCOL.md](docs/PLAY_PROTOCOL.md)。
