# 两个世界的体验闭环

## 霜港潮汐网：供给成为公共能力

玩家从低层配给维护员开始，先 `inspect_grid` 看见潮泵读数，再用 `trace_fault` 和 `log_cause` 把故障、维修和供给后果串成跨节点账本。`divert_barge`、`repair_valve` 和 `barter_fuel` 让玩家在低潮、驳船和盐雾风险之间承担即时机会成本；`tide_shift` 与 `salt_corrosion` 会在玩家离开时改变供给和维护债。

第一条可达路线是 `inspect_grid → trace_fault → log_cause → automate_pump → schedule_crew → audit_manifest → rest → convene_council → sign_quota`；它最多使用 `inspect_grid×3`、`trace_fault×3`、`automate_pump×2`、`schedule_crew×2`、`audit_manifest×2`，失败后可转入 `repair_valve×3`、`barter_fuel×3` 或 `train_apprentice×3`，不能靠无限重复观察刷分。正确使用杠杆会把低层潮泵交接自动化，释放连续时间，之后才能训练学徒、排班维修队并扩大网络。第二条复利链是 `divert_barge×1 → repair_valve → open_cold_storage×1 → sign_quota×1`：供给被稳定后，合作社和港务总管才愿意把分配权交给玩家。`convene_council×1` 触发从被配给者到共同调度者的关系反转；`sign_quota×1` 和 `cross_tier_three` 证明从低层维护员到生产/分配者的阶层跃迁。达到账本和网络条件后，里程碑只记录 `open_outer_route`，由引擎按 trigger 原子 materialize 外冰架候选区并解锁 `map_ice_route×1`。

杠杆消融：删除 `trace_fault`、`log_cause`、`automate_pump`、`audit_manifest` 后，`schedule_crew` 与 `cross_tier_three` 的可达路径消失，玩家只能重复手工修复，时间不会释放。错误登记或错误自动化会增加债务、维护债和伤害；错过低潮、驳船或议事窗口会改变后续路线。

## 灰印契约庭：承诺成为程序权力

玩家从边区申请人开始，先在 `gather_deposition` 中取得带来源的陈述，再用 `verify_chain`、`audit_registry` 和 `cross_examine` 检查证据链。`file_motion`、`request_extension` 和 `set_arbitration` 受程序期限约束；`clerk_deadline` 与 `faction_lobby` 在离线运行时推进期限压力和派系张力。失败的核验会增加违约记录，错误组合会冻结担保，不存在好感条或幸运跳过程序。

一条可达路线是 `rest → gather_deposition → verify_chain → file_motion → publish_affidavit → seek_witness → bind_commitment → call_alliance → set_arbitration → draft_settlement → audit_registry → expose_conflict`；`rest` 上限为 8 次，`gather_deposition×3`、`verify_chain×3`、`bind_commitment×2`、`audit_registry×2`，失败后可用 `cross_examine×3` 或 `negotiate_clause×3` 修复证据/承诺链，不能无限刷核验。第二条复利链是 `negotiate_clause → call_alliance×2 → set_arbitration×1 → draft_settlement×1`：敌对派系被放进同一套可执行条款。达到 `become_arbitration_setter` 后，书记官从审查申请人转为共同程序见证人；`enter_federal_circuit` 证明玩家从申请人跃迁为设定仲裁条件者；里程碑完成后由引擎按 `open_concord_docket` trigger 原子 materialize 联邦共同契约案卷并解锁 `ratify_concord×1`。

杠杆消融：删除 `verify_chain`、`bind_commitment`、`set_arbitration`、`audit_registry` 后，程序控制和联邦回路不可达，玩家只能接受法庭模板。错误证据链会缩短期限，错误承诺会增加违约；错过递交、证人或仲裁窗口会改变联盟和可用救济。灰印的关键载体是证据来源、期限、担保和承诺履行，不是霜港的供给、维护或资源调度。

## 共同编译边界

两个蓝图都把规则放在状态、动作、过程和事实中；Narrator 只能描述已提交的事件。注册表的关键词选择只是保守 fit hint，任意 prompt 仍必须经过同一套编译、反换皮和 replay 门禁。
