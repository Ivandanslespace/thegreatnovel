# Local Author Workbench

Workbench 是 FastAPI + Jinja2 autoescape + 原生 JavaScript/CSS 的本地审核台，默认只绑定 `127.0.0.1`。它展示 effective edition 正文、段落、指标卡片、贡献证据、缺失输入、完整 Observation history、草稿和 handoff 状态；作者输入通过 append-only service 保存并触发新的 Metric Run 与 Planning Aggregate stale 传播。

Web 不提供批准、revision approve 或 edition activate 按钮。它只能显示 validation/approval preview 和需要作者在 CLI/Codex 客户端执行的精确命令。Web 不接收 API Key、Provider、Model ID 或 shell 命令。

启动：

```powershell
uv sync --extra dev --no-editable
novel web serve --book-id <book> --workspace workspace --host 127.0.0.1 --port 8765
```

合成演示：

```powershell
novel demo seed-author-workbench --workspace workspace
novel web serve --book-id demo-author-workbench --workspace workspace
```

章节页使用三栏布局：左侧 edition/章节导航，中间 effective 正文与段落，右侧 sticky Metric Cards、Resolver 选择理由、证据、历史和作者输入。正文通过 Jinja `tojson`/autoescape 传递，前端只用 `textContent`，不使用 CDN、React、Node、shell、模型或 API Key。

远程绑定必须显式 `--allow-remote`，并承担本机防火墙/访问控制责任。
