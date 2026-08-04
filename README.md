# TheGreatNovel V1

TheGreatNovel 是一个本地、可复核的状态模拟小说游戏：确定性引擎先结算世界，叙事只投影已经公开的事实。LLM（若由 Codex 在聊天边缘使用）只能理解输入和润色文本，不能改写状态；核心运行不依赖联网 API。

快速开始：在 Codex 项目聊天中输入“开始游戏”（也支持 `start game`、`commencer le jeu`、`ابدأ اللعبة`）。选择语言后，宿主优先把原文写入 premise 文件，再调用 CLI；也可直接运行：

```powershell
python game.py languages
python game.py new --locale zh-CN --premise-file runtime/inbox/premise.txt --seed 101
python game.py status
python game.py act --action observe_rule
python game.py narrate --turn 1 --file runtime/drafts/CAMPAIGN_ID/turn-1.md
python game.py verify
python game.py list
python game.py finish
python game.py export
```

所有命令输出单个 UTF-8 JSON。`--runtime PATH` 必须放在子命令前（如 `python game.py --runtime PATH status`）。运行目录默认锚定本项目的 `runtime/`，与调用时所在目录无关，也可用 `TGN_RUNTIME_DIR` 覆盖。宿主只从 `runtime/inbox/` 读取世界描述、从 `runtime/drafts/` 读取润色章节；不要把玩家原文直接拼入命令。存档位于 `runtime/saves/`，每回合自动重写的草稿小说位于 `runtime/manuscripts/<campaign_id>/novel.md`，结束后的独立小说位于 `runtime/exports/<campaign_id>/novel.md`。支持 `zh-CN`、`fr-FR`、`en`、`ar`（阿拉伯语正文保持 RTL）。

开发测试：

```powershell
python -m compileall -q src game.py tests
python -m unittest discover -s tests -v
```
