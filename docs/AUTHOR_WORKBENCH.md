# Local Author Workbench

Workbench 是 FastAPI + Jinja2 + 原生 JavaScript/CSS 的本地审核台，默认只绑定 `127.0.0.1`。它展示 effective edition 正文、段落、指标卡片、贡献证据、缺失输入、草稿和 handoff 状态；作者输入通过 append-only 服务保存并触发新的 Metric Run。

Web 不提供批准、revision approve 或 edition activate 按钮。它只能显示 validation/approval preview 和需要作者在 CLI/Codex 客户端执行的精确命令。Web 不接收 API Key、Provider、Model ID 或 shell 命令。

启动：

```powershell
pip install -e ".[web]"
novel web serve --book-id <book> --workspace workspace
```

远程绑定必须显式 `--allow-remote`，并承担本机防火墙/访问控制责任。
