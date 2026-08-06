# 已知问题与审计限制

本文件属于冻结审计交接材料，不是续写修订指令。审计期间不回滚、不修复、不重新生成正史。

## 1. 正式数据库在审计期间发生迁移/重建痕迹

- 状态：`VERIFIED_FAIL`
- 证据：`audit_bundle/database/migration_and_edition_state.json`、`audit_bundle/database/state.sqlite3.readonly`、`audit_bundle/repository/pre_report_git_status.txt`
- 在审计前 Git 状态捕获之后调用正式 CLI 状态检查时，`Database.initialize()` 触发 schema migration 5 和 `backfill_base_editions`。
- migration 5 时间：`2026-08-04T09:36:46.980418+02:00`。
- 当前正式数据库 SHA-256：`13C86BA5F2FB667A4008A5FC62C2B03C251362B7771B0B6AB9E6EB88EC6CB5D2`。
- 未捕获到迁移前正式数据库 SHA-256，因此无法证明迁移前后字节差异的完整范围。
- 按冻结要求不回滚；该状态应由外部审计员作为环境完整性异常处理。

## 2. 验证时投影哈希与当前重建哈希不一致

- 状态：`VERIFIED_FAIL`
- 验证报告记录的 base projection hash：`8c26e592893c7908c77a94e3526a6664126213ec66671bfc943cf1a33c8a7226`。
- 在迁移后的临时副本上重建得到：`500f9d545b95dcc747707fd9c196980b2618ed711cf1152938796e8f8a38edae`。
- 两者都对应 event sequence 64，但重建结果未能复现验证时哈希；因此“验证结果可从当前数据库确定性重放”不能成立。
- 临时副本 export 只作为复现证据，不是原续写运行的原始 export。

## 3. 运行级证据不完整

- 状态：`NOT_AVAILABLE`
- 原始 continuation `run_id` 未在正式数据库中找到；只有 extract/plan/draft task id 和 validation run id。
- 原续写期间的原始命令日志、原始测试退出码、原始 snapshot、原始 export、Canon Commit 均未找到。
- 当前有 4 个草稿版本和 4 轮验证报告，可复核内容与验证结论，但不能复原所有运行时环境步骤。

## 4. 原文编号存在结构性异常

- 状态：`WARNING`
- 原文 front matter 声明 294 章，解析器也得到 294 个 ordinal；但 raw heading 存在重复编号 37、128、224–233，另有 `第000章` 的读者说明段。
- 本轮沿用数据库 ordinal 294 作为最近章节，并将目标 ordinal 设为 295；目标不是 raw heading 的“第284章”。

## 5. 续写正文含有需作者确认的机制推断

- 状态：`WARNING`
- 正文将长枪承接/改变一次雷击落点、雷暴因此出现三秒缺口写成可发生的局部机制。
- 合同允许使用已出现的长枪、黄金血脉和现场信息，最终十项验证未拒绝该机制；但证据包没有找到原文明确规定“长枪可导雷/改变落点”的 CANON 事实。
- 因而该机制只能标作 `INFERENCE`，不能升级为 `CANON`；作者批准前不得写入正史。

## 6. 结构历史不完整

- 状态：`WARNING`
- Repetition Fatigue 因输入 history 为空按实现返回 0，并记录 `no_history`；Boundary Packet 也警告更早章节尚无结构化摘要。
- 这不是“已证明没有重复”，而是“当前证据不足以计算历史相似度”。

## 7. 未执行的指标与账本

- 状态：`NOT_RUN`
- 本次没有形成 Stagnation、Resource Pressure、Aftershock Debt 的正式 metric result。
- 没有新增资源、能力、等级、掉落或 timeline 记录可供审计；这代表未写入状态，不代表这些维度已被完整证明。

## 8. 工作树与数据库的可见性差异

- 状态：`WARNING`
- Git 追踪文件在审计前后均无差异；`workspace/` 和正式 SQLite 由忽略规则管理，因此数据库迁移不会出现在普通 `git status` 的 tracked diff 中。
- 审计目录是本次唯一新增项目目录；其内容应单独交接，不应被误当作正文或正史。
