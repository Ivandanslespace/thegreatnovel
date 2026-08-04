# Windows 快速开始

## 1. 环境

支持 Windows PowerShell 与 Python 3.11+。项目路径包含中文时，不使用 editable install，因为 Python 3.11 可能用本地代码页读取 UTF-8 `.pth` 并在启动前失败。

```powershell
cd "C:\dev\小说续写系统"
uv sync --python "C:\Users\jingx\anaconda3\python.exe" --extra dev --no-editable --reinstall-package novel-authoring-system
$Novel = ".\.venv\Scripts\novel.exe"
& $Novel --help
```

如果使用其他 Python：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[dev]"
$Novel = ".\.venv\Scripts\novel.exe"
```

## 2. 初始化和导入

`book-id` 必须是稳定 ASCII ID；标题和路径可以是中文。

```powershell
$BookId = "my-novel"
& $Novel init --book-id $BookId --title "我的小说" --source-dir .\book
& $Novel ingest --book-id $BookId --title "我的小说" --source-dir .\book
& $Novel source verify --book-id $BookId
& $Novel status --book-id $BookId
```

输出只进入 `workspace\my-novel`。如果多文件顺序置信度不足，先打开命令返回的 `source_manifest.json` 核对，再运行：

```powershell
& $Novel ingest --book-id $BookId --title "我的小说" --source-dir .\book `
  --manifest ".\workspace\$BookId\source_manifest.json" --confirm-order
```

## 3. 首轮结构化抽取

```powershell
& $Novel extract prepare --book-id $BookId --chapter-start 1 --chapter-end 10
```

记下 JSON 中的 `task_id`、`input`、`schema` 和 `expected_output`。让 Codex读取 input/schema，只写 expected output。然后：

```powershell
& $Novel extract import --book-id $BookId --task-id <task-id>
& $Novel reconcile --book-id $BookId
```

根据报告逐条接受有原文 source span 的事实：

```powershell
& $Novel reconcile --book-id $BookId --fact-id <fact-id> `
  --decision accept-source --reason "原文直接陈述"
```

## 4. 准备指标输入

在 `workspace\<book-id>\metric_inputs.json` 写六指标输入。可从测试中的合成 fixture 或 `docs/METRICS.md` 查看字段；所有分量为 0—100，repetition similarity 为 0—1。

```powershell
& $Novel diagnose --book-id $BookId
```

## 5. 续写到已校验草稿

用户有明确要求时先保存：

```powershell
& $Novel directive add --book-id $BookId --type requirement `
  --scope next_chapter --content "下一章必须由主角主动选择"
```

依次执行：

```powershell
& $Novel boundary build --book-id $BookId
& $Novel plan-next --book-id $BookId
# Codex 写恰好三个 candidate 到 expected_output
& $Novel plan-next --book-id $BookId --task-id <candidate-task-id>
& $Novel contract build --book-id $BookId --candidate-id <selected-candidate-id>
& $Novel draft prepare --book-id $BookId --contract-id <contract-id>
# Codex 写正文及状态证据到 expected_output
& $Novel draft import --book-id $BookId --task-id <draft-task-id>
& $Novel draft validate --book-id $BookId --draft-id <draft-id>
& $Novel draft show --book-id $BookId --draft-id <draft-id>
```

`draft validate` 成功即停在 VALIDATED_DRAFT。不要因为命令成功就自动批准。

## 6. 版本化改写（V1.1）

改写旧章节必须创建派生 edition；不要把 replacement 写回 `book`。完整流程和回滚规则见 [`REVISION_WORKFLOW.md`](REVISION_WORKFLOW.md)。最小命令序列：

```powershell
& $Novel edition create --book-id $BookId --edition-id rewrite-v1 `
  --display-name "改写候选" --parent base
& $Novel revision create --book-id $BookId --edition-id rewrite-v1 `
  --spec .\examples\revision_spec.example.yaml
& $Novel revision impact --book-id $BookId --campaign-id <campaign-id>
& $Novel revision plan --book-id $BookId --campaign-id <campaign-id>
& $Novel revision draft-task --book-id $BookId --campaign-id <campaign-id> `
  --unit-id <unit-id>
# Codex 写 REVISION_DRAFT 后导入并校验
& $Novel revision import --book-id $BookId --output <revision-output.json>
& $Novel revision validate --book-id $BookId --campaign-id <campaign-id>
& $Novel revision approve --book-id $BookId --campaign-id <campaign-id> `
  --confirm "批准改写版本"
& $Novel edition export --book-id $BookId --edition-id rewrite-v1
& $Novel edition activate --book-id $BookId --edition-id rewrite-v1 `
  --confirm "启用改写版本"
```

批准不会自动激活；检查导出满意后才使用第二个精确确认语。要回到原版，启用 `base`，不会删除改写审计历史。

## 7. 显式批准

只有作者当前明确说“批准写入正史”时：

```powershell
& $Novel approve --book-id $BookId --draft-id <draft-id> `
  --confirm "批准写入正史"
```

命令先打印 preview，然后才执行批准事务。确认语错误、校验失败、源哈希变化、Boundary 漂移或重复提交均返回非零退出码。

## 8. 重建与导出

```powershell
& $Novel rebuild --book-id $BookId
& $Novel snapshot --book-id $BookId
& $Novel source verify --book-id $BookId
& $Novel export --book-id $BookId
```

批准正文位于 `workspace\<book-id>\canon`；导出位于 `exports`。不要手动拼接回 `book`。

## 9. 开发验收

```powershell
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests
uv run --no-sync mypy src
```

普通 wheel 不会在每次源码改动后自动刷新；需要验证安装产物时重新执行：

```powershell
uv sync --python "C:\Users\jingx\anaconda3\python.exe" --extra dev `
  --no-editable --reinstall-package novel-authoring-system
uv run --no-sync novel --help
```

## 常见错误

| 现象 | 原因与处理 |
|---|---|
| 启动时 `.pth` UnicodeDecodeError | 删除 editable 安装影响，按本文 `--no-editable` 重装 |
| 中文 FTS 搜不到连续子串 | 本项目必须保留 FTS5 `trigram` tokenizer |
| `source verify` 不通过 | 停止所有续写/批准，恢复或重新确认原始来源 |
| Boundary drift | 从 `boundary build` 重新规划，不能复用旧 contract/draft |
| 十项报告某项失败 | 按 location 修订新 revision，不能手工改 validation row |
| approve 退出 6 | 查看 preview/错误；必须精确确认且 draft 已 VALIDATED |
| 多文件导入退出 2 | 核对 manifest 顺序，再显式 `--confirm-order` |
