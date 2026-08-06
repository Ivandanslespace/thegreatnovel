# 外部审计复现命令

以下命令用于复核已经冻结的证据。命令按“只读正式项目 / 临时副本可写”区分。不要对正式 workspace 运行会初始化数据库的 CLI 命令；特别是不要运行正式 workspace 的 `novel status`、`novel rebuild` 或 `novel export`。

## 1. 项目与原文只读校验

```powershell
Set-Location 'C:\dev\小说续写系统'
Get-FileHash -Algorithm SHA256 'C:\dev\小说续写系统\book\全民纜車求生，我一級一個三選一_正文全集.md'
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
```

预期原文 SHA-256：`95810246d1296163fc02320446060e78addd9fa5cba56bbdd1292634a099ee6e`。

## 2. 正式 SQLite 只读查询

使用 SQLite URI 的 `mode=ro`，不要让 Python 或 CLI 初始化数据库：

```powershell
@'
import sqlite3
from pathlib import Path

db = Path(r"C:\dev\小说续写系统\workspace\real-book-smoke\state.sqlite3")
con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
for table in ("events", "facts", "threads", "promises", "drafts", "validation_reports", "canon_commits", "snapshots"):
    try:
        print(table, con.execute(f"select count(*) from {table}").fetchone()[0])
    except sqlite3.DatabaseError as exc:
        print(table, "NOT_AVAILABLE", exc)
con.close()
'@ | python -
```

## 3. 复核证据包哈希

```powershell
$bundle = 'C:\dev\小说续写系统\audit\final_continuation_report\audit_bundle'
Get-ChildItem -LiteralPath $bundle -Recurse -File |
  Get-FileHash -Algorithm SHA256
```

逐文件正式清单见 `EVIDENCE_MANIFEST.json`。

## 4. 临时副本测试与静态检查

以下命令只针对审计时复制到 `C:\Users\jingx\AppData\Local\Temp\novel_authoring_audit_20260804` 的源码树：

```powershell
$env:PYTHONPATH = 'C:\Users\jingx\AppData\Local\Temp\novel_authoring_audit_20260804\src'
$env:PYTHONDONTWRITEBYTECODE = '1'
Set-Location 'C:\Users\jingx\AppData\Local\Temp\novel_authoring_audit_20260804'
& 'C:\dev\小说续写系统\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider
& 'C:\dev\小说续写系统\.venv\Scripts\ruff.exe' check src tests
& 'C:\dev\小说续写系统\.venv\Scripts\mypy.exe' src --cache-dir .\mypy_cache_2
```

证据日志：`audit_bundle/tests/pytest.log`、`ruff.log`、`mypy.log`；三者退出码均为 0。

## 5. 临时 workspace 的源校验、重建与导出

这些命令可以写临时副本，不能把 workspace 参数改成正式的 `C:\dev\小说续写系统\workspace`：

```powershell
$novel = 'C:\dev\小说续写系统\.venv\Scripts\novel.exe'
$ws = 'C:\Users\jingx\AppData\Local\Temp\novel_authoring_audit_runtime\workspace'
$out = 'C:\Users\jingx\AppData\Local\Temp\novel_authoring_audit_runtime\export_audit_2'
& $novel source verify --book-id real-book-smoke --workspace $ws
& $novel rebuild --book-id real-book-smoke --workspace $ws --edition-id base
& $novel export --book-id real-book-smoke --workspace $ws --output-dir $out --edition-id base
```

审计时结果：源校验、重建、导出均退出码 0；重建和导出 projection hash 为 `500f9d545b95dcc747707fd9c196980b2618ed711cf1152938796e8f8a38edae`。原始验证 hash 仍为 `8c26e592893c7908c77a94e3526a6664126213ec66671bfc943cf1a33c8a7226`，两者不一致，详见 `KNOWN_ISSUES.md`。

## 6. 禁止动作

- 不运行 `novel approve`，不创建 Canon Commit。
- 不修改 `book/`、boundary、contract、draft、state 数据库或阈值配置。
- 不运行 `git reset`、`checkout`、`restore`、`clean`、`stash`、`commit`、`push`。
- 不把临时 export 复制回正式 workspace。
