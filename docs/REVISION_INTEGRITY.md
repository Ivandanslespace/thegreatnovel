# 版本化改写完整性

## Edition 与物化

所有可变投影表使用 `(book_id, edition_id, logical_record_id)` 物理主键；初始化时的显式 table
rebuild 会移除旧的跨版本全局唯一约束。Canon Projection、materialized rows、metric results 和
Boundary Packet 都按 edition 对账。`book/` 与 base source manifest 永远不被改写。

Revision Campaign 在创建时冻结目标 edition 的当前 `campaign_base_event_seq` 与
`campaign_base_projection_hash`；它们不同于 edition 创建时的父版本锚点。审批前必须重新验证当前
projection、source manifest、影响审计、所有草稿哈希和完整改写校验。

## 来源、回滚与审计

事件写入返回完整 `EventRecord`，物化记录引用真实 `event_id/event_seq/event_hash`。改写正文建立
`REVISION_VARIANT` source span，保存 edition、variant、revision commit、替换正文 hash/excerpt，
并进入 `edition_chapter_fts`。新增事实只能引用该 variant span；base preimage span 只表示旧版本。

每个 Unit 的草稿按 `r1/r2/r3` 追加保存，拥有新的 task、draft、文件、父 draft、revision number、
validation run 和 content hash；第 4 次导入拒绝，旧 REJECTED 记录不删除。批准事务失败时回滚事件、
variant、物化、projection、snapshot 和输出文件。

子 edition 只继承父版本冻结锚点之前已提交的 variant/generated chapter；父版本之后的新分叉不会渗入
旧子版本。批准改写版本与启用改写版本分离，ACTIVE edition 的生命周期不会静默回退 base。

## 检查面

改写校验实际执行 Source Preimage、Scope、Intent、Supersession、Invariant、Propagation、Stable
Entity Identity、Edition Lineage、Adult/Consent、Campaign Completeness，并继续执行 Canon、Timeline、
Knowledge、Character、Economy/Power、Contract、Debt、Payoff、Repetition、Style 十项报告。
required/invariant evidence 必须非空且逐句出现在 preimage、replacement 或合法 source span；状态变化
必须与 facts/relationships/knowledge/canon_changes 双向对应。未得到逐字批准语时，系统停在
`VALIDATED`/`VALIDATED_DRAFT`，不产生 Canon Commit。
