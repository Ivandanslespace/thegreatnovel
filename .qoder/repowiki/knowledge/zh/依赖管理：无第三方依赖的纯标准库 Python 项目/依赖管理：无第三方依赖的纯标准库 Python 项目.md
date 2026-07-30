---
kind: dependency_management
name: 依赖管理：无第三方依赖的纯标准库 Python 项目
category: dependency_management
scope:
    - '**'
source_files:
    - .gitignore
    - engine_runtime/state.py
    - engine_runtime/persistence.py
    - tests/test_engine_runtime.py
---

该仓库是一个基于 Python 标准库构建的文字游戏引擎，未使用任何第三方依赖包或依赖管理系统。

**系统与工具**
- 语言：Python（从 `__future__` 导入和类型注解推断为 Python 3.7+）
- 包管理器：未发现 `requirements.txt`、`pyproject.toml`、`setup.py`、`Pipfile`、`poetry.lock` 等任何依赖声明文件
- 锁定文件：不存在 `*.lock`、`go.sum`、`package-lock.json` 等锁定文件
- 私有仓库/代理：未发现 `.piprc`、`pip.conf`、`~/.config/pip/pip.conf` 等配置
- Vendoring：未发现 `vendor/` 目录或 vendoring 脚本

**已确认使用的依赖**
所有 import 均为 Python 标准库模块：
- 数据序列化：`json`、`yaml`（PyYAML，但未见声明）、`sqlite3`
- 文件系统：`pathlib.Path`、`copy.deepcopy`
- 时间/标识：`datetime`、`uuid`
- 计算/正则：`math`、`hashlib`、`re`
- 类型提示：`typing`、`dataclasses`

**架构约定**
- 项目采用纯标准库策略，避免引入外部包以降低部署复杂度
- 仅 `yaml` 模块在多处被使用（`state.py`、`tests/test_engine_runtime.py`），但未在依赖文件中声明，存在潜在运行时风险
- 测试通过 `pytest` 运行（存在 `.pytest_cache`），但同样未声明 pytest 依赖

**约束与问题**
- 缺少依赖声明文件意味着项目无法通过 `pip install -r requirements.txt` 等方式安装
- PyYAML 作为隐式依赖未被记录，可能导致在新环境中运行时失败
- 无版本锁定机制，不同环境可能加载不同版本的 stdlib 行为（如 yaml 解析差异）