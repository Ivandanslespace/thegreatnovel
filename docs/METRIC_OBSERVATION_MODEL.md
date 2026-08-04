# Metric Observation Model

本轮指标系统将“输入观察”和“最终分数”分离。注册表 `config/metrics_registry.yaml` 只描述展示、范围、来源类型、必填 component 和证据政策；公式仍由 Python 实现，禁止任意表达式或 `eval`。

## 来源优先级

`DETERMINISTIC > DERIVED` 适用于章节字数、Content SHA、库存和已确认状态；语义/作者 component 使用 `AUTHOR_OVERRIDE > AUTHOR_INPUT > SEMANTIC_ESTIMATE > DERIVED > UNKNOWN`。确定性事实不能被作者改写，只能标记争议并要求重算。

`metric_observations` 是 append-only。新观察通过 `supersedes_observation_id` 指向旧观察，旧观察只失效，不覆盖历史；显式撤回会保留值和 supersedes 链，Resolver 会恢复此前仍合法的观察。相同最高优先级冲突进入 `DISPUTED`，不按数据库顺序任选一个。

## 缺失与运行

`metric_runs` 冻结 edition、projection、effective content、registry、config 和 input bundle hash。`metric_run_results.score` 在必填 component 缺失时保持 `null`；completeness 与 confidence 分开，不能用 0/50 填补 UNKNOWN。作者输入会使当前 run INVALIDATED，并将 candidate/contract 标记 STALE，但不产生 Canon Event。

## 兼容入口

旧的 `novel diagnose --input` 保留用于调试和导入兼容；正常路径是 `novel metrics rebuild|run-chapter|run-window|run-promise|build-planning-aggregate|diagnose|show|missing|history|disputes`。`novel observation resolve|retract` 与 Web 共用 `ObservationResolver`/service 层。
