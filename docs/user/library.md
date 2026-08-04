# 书库快速使用

默认书库是项目根目录下的 `library/`。可以先列出已有书：

```powershell
novel library list
```

导入一份新正文（原文件不会被修改）：

```powershell
novel library import `
  --book-id cable-survival-demo `
  --source C:\dev\小说续写系统\book\全民纜車求生，我一級一個三選一_正文全集.md
```

`library import` 是兼容别名；新书主入口是 `novel library add`。两者都会完成
来源复制、前后 SHA-256、`_system/state.sqlite3`、章节/Source Spans/FTS 和
`NEEDS_INITIALIZATION` 登记。多文件目录需要显式 `--confirm-order`。

检查路径：

```powershell
novel library paths --book-id cable-survival-demo
```

Portable Snapshot 由 `novel atlas export-snapshot` 写入
`editions/base/exports/latest/`，可直接打开其中的 `index.html`。书库 Web 首页为
`/library`，不提供任意文件系统浏览器，只展示 `BookLayout` 认可的固定路径。
