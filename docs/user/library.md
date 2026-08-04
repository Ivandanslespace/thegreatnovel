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

检查路径：

```powershell
novel library paths --book-id cable-survival-demo
```

Portable Snapshot 由 `novel atlas export-snapshot` 写入
`editions/base/exports/latest/`，可直接打开其中的 `index.html`。书库 Web 首页为
`/library`，不提供任意文件系统浏览器，只展示 `BookLayout` 认可的固定路径。
