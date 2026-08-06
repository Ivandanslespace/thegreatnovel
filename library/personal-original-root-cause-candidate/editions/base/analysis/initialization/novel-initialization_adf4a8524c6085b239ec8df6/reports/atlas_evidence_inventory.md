# Story Atlas 证据清单（隔离审计）

## 审计范围与边界

- initialization_id：novel-initialization_adf4a8524c6085b239ec8df6；book：personal-original-root-cause-candidate；edition：base。
- 只读检查了 45 Arc manifest、entity_resolution_map、synthesis/current_world_model、synthesis/graphs、synthesis/future_possibility_space、synthesis/unresolved_assumptions，以及当前 Arc outputs；本文件是隔离分析产物，不是 Atlas accepted 版本。
- manifest 共 45 个 Arc；当前 output.json 通过 ArcExtractionOutput 校验的有 43 个，失败 0 个，待补的是 Arc36（308–315，init-arc_dcac1f57b3d4f5813901b7fe）与 Arc37（316–323，init-arc_12da02667825008902e02788）。
- Arc42–45 当前边界：

| Arc | ordinal / chapter | 当前 semantic 状态 | 主线程记录 | 证据跨度 |
|---|---|---|---|---|
| init-arc_a420e2101c101910cc388554 | 354–360 | 7/7，均 PARTIAL | thread_final_god_inheritance，INFERENCE，confidence 0.88 | span_fc12ec795cbfc4c4ccb1d7ca；span_90d928d6476ba54a55f4cc90；span_131185ad3c7194d273da3761；span_3af1174b14ea9cfe5b357574；span_b75fcf1452f08f56d3179140；span_48b40569922af87b044ff287；span_8a7b786377fb3cf0e6e60b3d |
| init-arc_efe91d2432c44b074c5164b0 | 361–367 | 7/7，均 PARTIAL | thread_god_return_and_final_war，INFERENCE，confidence 0.90 | span_5338cb72f9821cfabebbcbe6；span_f13d4e22403dd29f5df79da4；span_46cb3e030548b7bfb1b2c8ab；span_b61d25a7b434e6a160815b92；span_e9645ca8126c40fef617286a；span_7a4de91056dfb12743b6f258；span_b8b555680cd55d29bb12b33d |
| init-arc_cb32179dd7cc87eb07e16243 | 368–375 | 8/8，均 PARTIAL | thread_jialing_final_battle，INFERENCE，confidence 0.94 | span_dcc7f46c9cf31ec6c14a7c07；span_1424d24caad9d4d119a3850f；span_6ac901a69d6d0850a39965b8；span_37751b85f6b38c4585bd7dbb；span_299464364a16bb0a827453d4；span_414d36fe3bc33e4715d6460b；span_57caf780220ae3b26ebebcb9；span_8886ce99a2d978eb6071de6e |
| init-arc_3113cabad757faf66982dfb6 | 376–379 | 4/4，均 ANALYZED | thread_postwar_transition，INFERENCE，confidence 0.84 | span_679c5e4110fa88c01b2f95ff；span_fa378dd5cb85560640398b82；span_eeae31dd6055c25dbe5e42bf；span_78e506ec415b579ab48eb2b9 |

Arc42–44 的逐章特征可作为有证据的 INFERENCE，不应把 PARTIAL 语义自动升级为 CANON；Arc45 的第379章是当前边界，不是自动批准的下一章路线。

## Atlas 字段约定

- information_status 使用 CANON / INFERENCE / CANDIDATE；CANDIDATE 行的证据只证明可能入口，不证明已选主线。
- constraint_level 使用 Atlas 枚举 HARD / SOFT / SPECULATIVE；HARD 表示续写必须保留的当前事实或规则。
- horizon 使用 CURRENT / NEAR / MID / FAR；FAR 不附逐章计划。
- 每个节点与边都列真实 source_span_id。INFERENCE/CANDIDATE 行同时写反证或 unknown boundary。
- 地区只写叙事拓扑，不写坐标；五行大陆只保留为远端事实 hook，不选为唯一主线。

## 1. characters 图

### 最小节点

| node_id / name | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| character_tang_san / 唐三 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff；span_eeae31dd6055c25dbe5e42bf；span_78e506ec415b579ab48eb2b9 | 已复活，海神/修罗神双神共存，赢得终局后退出帝国权力；不得无因降回普通魂师或恢复常驻统治。 |
| character_ling_yue / 凌岳 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff；span_eeae31dd6055c25dbe5e42bf；span_78e506ec415b579ab48eb2b9 | 成年男性伴侣、修罗魔剑载体及双神共存共同完成者；不得降格为奖励、工具或改写性别/关系。 |
| character_qian_renxiao / 千仞霄 | CANON | HARD | CURRENT | 1.00 | span_fa378dd5cb85560640398b82；span_eeae31dd6055c25dbe5e42bf；span_78e506ec415b579ab48eb2b9 | 神位破碎、武魂受损并获赦免；不得无证据恢复完整天使神位。 |
| character_bibi_chen / 比比宸 | CANON | HARD | CURRENT | 1.00 | span_fa378dd5cb85560640398b82；span_78e506ec415b579ab48eb2b9 | 最终敌手已死亡；不得无因复活。 |
| character_xue_beng / 雪崩 | CANON | HARD | NEAR | 1.00 | span_679c5e4110fa88c01b2f95ff；span_78e506ec415b579ab48eb2b9 | 天斗皇帝、唐三弟子，承接十年停战、战后约束与婚礼主持；执行细节尚未展开。 |
| character_hu_liezhao / 胡列昭 | CANON | HARD | CURRENT | 1.00 | span_fa378dd5cb85560640398b82；span_78e506ec415b579ab48eb2b9 | 获准存活；后续动机、所在地和是否主动行动均 UNKNOWN。 |
| character_shrek_network / 史莱克伙伴网络 | INFERENCE | SOFT | NEAR | 0.70 | span_679c5e4110fa88c01b2f95ff；span_78e506ec415b579ab48eb2b9 | 正文证明核心同盟和复活链参与，但没有逐一给出战后目标/地点；反证是群像状态未完整交代。 |

### 最小边

| edge_id / relation | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| relationship_tang_san_ling_yue / 唐三—凌岳成年伴侣与融合搭档 | CANON | HARD | CURRENT | 1.00 | span_eeae31dd6055c25dbe5e42bf；span_78e506ec415b579ab48eb2b9 | 共同存活、解除融合并准备成婚；不是血缘兄弟。 |
| relationship_tang_san_xue_beng / 唐三—雪崩师生与战后授权 | CANON | HARD | NEAR | 1.00 | span_78e506ec415b579ab48eb2b9 | 唐三辞去帝师但把约束交给帝国执行；长期执行机制 UNKNOWN。 |
| relationship_bibi_chen_qian_renxiao / 比比宸—千仞霄亲情牺牲 | CANON | HARD | CURRENT | 1.00 | span_fa378dd5cb85560640398b82；span_78e506ec415b579ab48eb2b9 | 终局牺牲已闭合；比比宸死亡是硬边界。 |
| relationship_tang_san_shrek / 唐三—史莱克伙伴同盟 | INFERENCE | SOFT | NEAR | 0.70 | span_679c5e4110fa88c01b2f95ff；span_78e506ec415b579ab48eb2b9 | 复活与终局合作支持同盟推断；战后分工和个人目标未证实。 |

## 2. factions 图

### 最小节点

| node_id / name | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| faction_tang_sect / 唐门 | CANON | HARD | CURRENT | 1.00 | span_78e506ec415b579ab48eb2b9 | 唐门退出战争用途，诸葛神弩收回并销毁；技术退出后的社会反馈 UNKNOWN。 |
| faction_tiandou_empire / 天斗帝国 | CANON | HARD | NEAR | 1.00 | span_78e506ec415b579ab48eb2b9 | 战后胜方，承接战俘、十年停战和约束执行；内部执行结构 UNKNOWN。 |
| faction_wuhun_empire / 武魂帝国 | CANON | HARD | CURRENT | 1.00 | span_78e506ec415b579ab48eb2b9 | 终局战败，旧主冲突闭合；后续秩序重组没有正文细节。 |
| faction_shrek_network / 史莱克伙伴网络 | INFERENCE | SOFT | NEAR | 0.70 | span_679c5e4110fa88c01b2f95ff；span_78e506ec415b579ab48eb2b9 | 作为同盟网络存续是跨章推断；个体是否继续共同行动 UNKNOWN。 |

### 最小边

| edge_id / relation | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| edge_tangmen_war_exit / 唐门—天斗帝国军用退出 | CANON | HARD | CURRENT | 1.00 | span_78e506ec415b579ab48eb2b9 | 诸葛神弩收回并销毁；不得无因恢复为常备军工链。 |
| edge_tiandou_star_luo_ceasefire / 天斗—星罗十年停战 | CANON | HARD | NEAR | 1.00 | span_78e506ec415b579ab48eb2b9 | 是战后承诺，不等于已验证的长期制度。 |
| edge_shrek_postwar_unknown / 史莱克—战后秩序 | INFERENCE | SOFT | NEAR | 0.65 | span_679c5e4110fa88c01b2f95ff；span_78e506ec415b579ab48eb2b9 | 核心同盟仍在，但谁承担何种制度成本尚未交代。 |

## 3. abilities 图

### 最小节点

| node_id / name | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| ability_sea_god / 海神权柄 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff；span_fa378dd5cb85560640398b82 | 唐三现有神位与海洋信仰来源；具体神界职责未落地。 |
| ability_shura_god / 修罗神力 | CANON | HARD | CURRENT | 1.00 | span_eeae31dd6055c25dbe5e42bf；span_78e506ec415b579ab48eb2b9 | 由凌岳承载的修罗魔剑链完成双神共存；长期日常成本 UNKNOWN。 |
| ability_dual_god_switch / 双神切换 | CANON | HARD | CURRENT | 1.00 | span_eeae31dd6055c25dbe5e42bf | 一次只能有一神出手；不得推断可无成本同时叠加。 |
| ability_faith_resurrection / 神级复活与神魂归位 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff | 肉身和神魂由不同神力/信仰支撑；不得当作人人可复制或可随意重复的复活术。 |
| ability_rift_war_lion / 凌岳裂空战狮能力链 | CANON | HARD | CURRENT | 1.00 | span_eeae31dd6055c25dbe5e42bf | 当前融合链已承载修罗神力；能力上限、解除后的长期成本未展开。 |
| ability_guanyin_tear / 神级观音泪 | CANON | HARD | CURRENT | 1.00 | span_fa378dd5cb85560640398b82 | 可威胁神级目标但消耗巨大，且终局亲情选择曾打乱原计划；不得无代价连发。 |

### 最小边

| edge_id / relation | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| edge_tang_sea_god_owner / 唐三—海神权柄 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff；span_fa378dd5cb85560640398b82 | 当前承载者；后续神界职责未决定。 |
| edge_ling_shura_sword_owner / 凌岳—修罗魔剑/修罗神力 | CANON | HARD | CURRENT | 1.00 | span_eeae31dd6055c25dbe5e42bf | 凌岳为剑鞘，融合时由唐三调用；不得把剑从关系中抽离为无主外挂。 |
| edge_dual_god_single_action / 双神共存—单一神力出手限制 | CANON | HARD | CURRENT | 1.00 | span_eeae31dd6055c25dbe5e42bf | 明确硬规则；长期反噬、同时叠加和非战斗持续时间 UNKNOWN。 |
| edge_resurrection_faith_cost / 复活—信仰资源 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff | 资源依赖已证实，资源消耗曲线与可重复性 UNKNOWN。 |

## 4. resources_and_items 图

### 最小节点

| node_id / name | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| resource_faith_power / 信仰之力 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff | 支撑肉身与神魂复活；后续是否仍有可用库存/代价 UNKNOWN。 |
| resource_ocean_power / 海洋之力 | CANON | HARD | CURRENT | 1.00 | span_fa378dd5cb85560640398b82 | 支撑海神神力与终局战斗；来源与未来职责不等于无限资源。 |
| item_shura_demonic_sword / 修罗魔剑 | CANON | HARD | CURRENT | 1.00 | span_eeae31dd6055c25dbe5e42bf | 凌岳为剑鞘、融合时调用；独立使用规则 UNKNOWN。 |
| item_zhuge_crossbow / 诸葛神弩 | CANON | HARD | CURRENT | 1.00 | span_78e506ec415b579ab48eb2b9 | 战后收回并交唐门销毁；不得默认仍有可随时调动的军用库存。 |
| resource_postwar_institutional_capacity / 战后制度执行能力 | CANDIDATE | SPECULATIVE | NEAR | UNKNOWN | span_78e506ec415b579ab48eb2b9 | 十年停战和战俘约束被提出，但执行者、监督和失败成本未知；不是已存在资源。 |

### 最小边

| edge_id / relation | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| edge_faith_to_resurrection / 信仰之力—复活链 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff | 两层复活依赖不同信仰来源；不得推广为通用系统。 |
| edge_sword_to_dual_god / 修罗魔剑—双神共存 | CANON | HARD | CURRENT | 1.00 | span_eeae31dd6055c25dbe5e42bf | 剑是融合触发和承载链的一部分；长期损耗 UNKNOWN。 |
| edge_crossbow_to_tangmen_exit / 诸葛神弩—唐门退出战争 | CANON | HARD | CURRENT | 1.00 | span_78e506ec415b579ab48eb2b9 | 退出军用体系是主角主动决策的直接后果。 |
| edge_postwar_capacity_unknown / 制度执行能力—停战承诺 | CANDIDATE | SPECULATIVE | NEAR | UNKNOWN | span_78e506ec415b579ab48eb2b9 | 只有承诺文本，不能假定已有可靠监督链。 |

## 5. regions 图（仅拓扑，不含坐标）

### 最小节点

| node_id / name | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| region_jialing_pass / 嘉陵关 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff；span_fa378dd5cb85560640398b82；span_eeae31dd6055c25dbe5e42bf；span_78e506ec415b579ab48eb2b9 | 终局神战与武魂帝国败亡地点；战争已闭合。 |
| region_sea_god_island / 海神岛 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff | 海神信仰/传承来源；后续是否成为当前场景 UNKNOWN。 |
| region_divine_realm / 神界 | INFERENCE | SOFT | MID | 0.65 | span_78e506ec415b579ab48eb2b9 | 有神界职责谈话和召见信息，但唐三实际升入时间/路径未写出；不能默认下一章转场。 |
| region_five_elements_continent / 五行大陆 | CANON | SOFT | FAR | 1.00 | span_78e506ec415b579ab48eb2b9 | 仅证明远端执行者遇害这一事实 hook；没有坐标、通道、主角任务或已选路线。 |

### 最小边

| edge_id / relation | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| edge_jialing_to_sea_island / 嘉陵关—海神岛 | INFERENCE | SOFT | CURRENT | 0.72 | span_679c5e4110fa88c01b2f95ff | 由传承与复活链推断方向性连接；具体路线和时间未给出。 |
| edge_douluo_to_divine_realm / 斗罗大陆—神界 | INFERENCE | SOFT | MID | 0.72 | span_78e506ec415b579ab48eb2b9 | 只证明存在神位职责方向；不证明唐三已升神或必须马上升神。 |
| edge_five_elements_route / 神界—五行大陆 | CANDIDATE | SPECULATIVE | FAR | 0.45 | span_78e506ec415b579ab48eb2b9 | 远端执行者遇害没有给出路线或责任主体；保持断边/待证，不绘制坐标。 |

## 6. plot_threads 图

### 最小节点

| node_id / name | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| thread_final_god_inheritance / Arc42 神位传承前段 | INFERENCE | SOFT | CURRENT | 0.88 | span_fc12ec795cbfc4c4ccb1d7ca；span_90d928d6476ba54a55f4cc90；span_131185ad3c7194d273da3761；span_3af1174b14ea9cfe5b357574；span_b75fcf1452f08f56d3179140；span_48b40569922af87b044ff287；span_8a7b786377fb3cf0e6e60b3d | 魔鲸王战后进入海神/修罗神选择、波赛川献祭与传承考验；Arc42 特征 PARTIAL，最终共存方式由后续证据闭合。 |
| thread_god_return_and_final_war / Arc43 神装与返场 | INFERENCE | SOFT | CURRENT | 0.90 | span_5338cb72f9821cfabebbcbe6；span_f13d4e22403dd29f5df79da4；span_46cb3e030548b7bfb1b2c8ab；span_b61d25a7b434e6a160815b92；span_e9645ca8126c40fef617286a；span_7a4de91056dfb12743b6f258；span_b8b555680cd55d29bb12b33d | 神装、伙伴跃迁和凌岳承接修罗魔剑后回到嘉陵关；Arc43 PARTIAL，魔剑长期成本 UNKNOWN。 |
| thread_jialing_final_battle / Arc44 嘉陵关终局战争 | INFERENCE | SOFT | CURRENT | 0.94 | span_dcc7f46c9cf31ec6c14a7c07；span_1424d24caad9d4d119a3850f；span_6ac901a69d6d0850a39965b8；span_37751b85f6b38c4585bd7dbb；span_299464364a16bb0a827453d4；span_414d36fe3bc33e4715d6460b；span_57caf780220ae3b26ebebcb9；span_8886ce99a2d978eb6071de6e | 从攻城、多神对峙、唐三陨落到复活尝试的连续升级；Arc44 PARTIAL，复活结果依赖 Arc45。 |
| thread_postwar_transition / Arc45 战后秩序与新生活 | INFERENCE | SOFT | NEAR | 0.84 | span_78e506ec415b579ab48eb2b9 | 正文闭合神战并留下停战、婚礼、退出权力三组开放事项；反证是完结标记没有规定下一章主次。 |
| thread_five_elements_anomaly / 五行大陆执行者遇害 | CANDIDATE | SPECULATIVE | FAR | 0.55 | span_78e506ec415b579ab48eb2b9 | 事实 hook 为 CANON，但“成为主线”只是候选；没有主角接令、路线、对手或时点。 |

### 最小边

| edge_id / relation | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| edge_inheritance_to_return / 神位传承—嘉陵关返场 | INFERENCE | SOFT | CURRENT | 0.88 | span_8a7b786377fb3cf0e6e60b3d；span_b8b555680cd55d29bb12b33d | Arc42–43 标题与证据连续支持；因 Arc42–43 PARTIAL，不把每一项神装规则当 Canon。 |
| edge_return_to_final_war / 神装返场—终局战争 | INFERENCE | SOFT | CURRENT | 0.90 | span_b8b555680cd55d29bb12b33d；span_dcc7f46c9cf31ec6c14a7c07 | Arc43/44 形成战场接续；具体战术和胜负由后续章节证据闭合。 |
| edge_final_war_to_resurrection / 终局战争—复活 | INFERENCE | SOFT | CURRENT | 0.94 | span_57caf780220ae3b26ebebcb9；span_8886ce99a2d978eb6071de6e；span_679c5e4110fa88c01b2f95ff | Arc44 只到复活尝试，Arc45 才证明成功；不能在 Arc44 边界提前写定。 |
| edge_resurrection_to_postwar / 复活—战后边界 | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff；span_eeae31dd6055c25dbe5e42bf；span_78e506ec415b579ab48eb2b9 | 第379章已明确战争闭合、双神共存与退出权力；下一阶段形式仍由作者选择。 |

## 7. stage_transitions 图

### 最小节点

| node_id / stage | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| stage_354_whale_payoff | INFERENCE | SOFT | CURRENT | 0.88 | span_fc12ec795cbfc4c4ccb1d7ca；span_90d928d6476ba54a55f4cc90 | 魔鲸王战果转为百万年魂环/魂骨并进入神位选择；变异杀神领域与吸收代价需后文复核。 |
| stage_356_360_god_choice | INFERENCE | SOFT | CURRENT | 0.88 | span_131185ad3c7194d273da3761；span_3af1174b14ea9cfe5b357574；span_b75fcf1452f08f56d3179140；span_48b40569922af87b044ff287；span_8a7b786377fb3cf0e6e60b3d | 海神/修罗神互斥选择、献祭、神装与关系突破；Arc42 PARTIAL，不能预设单一神位结局。 |
| stage_361_367_god_return | INFERENCE | SOFT | CURRENT | 0.90 | span_5338cb72f9821cfabebbcbe6；span_7a4de91056dfb12743b6f258；span_b8b555680cd55d29bb12b33d | 海神神装、伙伴封号、凌岳承接修罗魔剑并返回嘉陵关；长期成本 UNKNOWN。 |
| stage_368_375_final_war | INFERENCE | SOFT | CURRENT | 0.94 | span_dcc7f46c9cf31ec6c14a7c07；span_414d36fe3bc33e4715d6460b；span_57caf780220ae3b26ebebcb9；span_8886ce99a2d978eb6071de6e | 终局战场从团队攻城升级为唐三陨落和复活尝试；Arc44 PARTIAL。 |
| stage_376_379_postwar_boundary | CANON | HARD | CURRENT | 1.00 | span_679c5e4110fa88c01b2f95ff；span_eeae31dd6055c25dbe5e42bf；span_78e506ec415b579ab48eb2b9 | 当前状态：复活、双神共存、敌对主线闭合、退出帝国权力、婚礼安排、远端异常；第379章“全书完”是边界。 |

### 最小边

| edge_id / transition | information_status | constraint_level | horizon | confidence | source_span_id | 证据、反证或 unknown boundary |
|---|---|---|---|---:|---|---|
| edge_whale_to_god_choice / 魔鲸王战果—神位选择 | INFERENCE | SOFT | CURRENT | 0.88 | span_90d928d6476ba54a55f4cc90；span_131185ad3c7194d273da3761 | 标题和连续章节支持阶段转移；吸收代价与神位互斥规则未完全证实。 |
| edge_god_choice_to_return / 神位选择—神装返场 | INFERENCE | SOFT | CURRENT | 0.90 | span_3af1174b14ea9cfe5b357574；span_5338cb72f9821cfabebbcbe6；span_b8b555680cd55d29bb12b33d | 传承链最终导向嘉陵关，但 Arc42–43 的 PARTIAL 状态要求保留不确定性。 |
| edge_return_to_war / 神装返场—嘉陵关神战 | INFERENCE | SOFT | CURRENT | 0.94 | span_b8b555680cd55d29bb12b33d；span_dcc7f46c9cf31ec6c14a7c07 | 返场后进入终局战争；具体阵营互动由 Arc44/45 承接。 |
| edge_war_to_postwar / 神战—战后重建与关系兑现 | CANON | HARD | CURRENT / NEAR | 1.00 | span_78e506ec415b579ab48eb2b9 | 由第379章明确转段；NEAR 的具体聚焦仍未由作者选择。 |

## 当前主角状态与硬规则汇总

1. 唐三：已复活，海神/修罗神双神共存，绝对能力仍为神级；已退出帝师、蓝昊王与常驻战争事务。
2. 凌岳：成年男性伴侣、修罗魔剑载体和双神共存共同完成者；婚礼已安排但正文未实际举行。
3. 硬能力限制：一次只能由一个神位出手；不得推断同时叠加、无成本长期持续或已知永久反噬。
4. 复活限制：肉身与神魂是两层不同机制，依赖信仰/神力；不得泛化为常规复活。
5. 人间政治限制：唐三不应持续干预人间政务；只有出现明确神级威胁时才保留干预例外。
6. 战争/技术限制：嘉陵关主战争已闭合；唐门退出战争用途，诸葛神弩收回销毁。
7. 死亡边界：比比宸已死；千仞霄神位破碎、武魂受损并获赦免；均不得无因回滚。

## 明确 UNKNOWN / 待作者选择

- Arc42–44 的 PARTIAL 语义：变异杀神领域、百万年魂环吸收代价、海神/修罗神选择机制、波赛川献祭后的完整规则、神装与修罗魔剑长期成本，需要后续证据或作者复核。
- 双神共存在日常/非生死战的持续时间、消耗、凌岳独立状态影响：正文未给出长期数据。
- 神级复活能否再次复现、需要多少信仰、是否有不可逆代价：未知。
- 婚礼实际时间、是否作为下一章前景、公开关系后的制度与社交后果：未知。
- 十年停战、战俘处置、唐门技术销毁的监督主体、违约成本和社会反馈：未知。
- 史莱克伙伴逐一战后目标、所在地和是否继续共同行动：未知。
- 神界职责：唐三是否何时升入神界、是否接替执法者、介入权限和代价：未知。
- 五行大陆：只证明远端执行者遇害；身份链、地理拓扑、通道、主角是否接令和事件优先级均未知，保持 FAR/CANDIDATE，不得视为已选主线。
- 下一章形态（战后余波、婚礼/共同生活、神界调查或五行大陆异常）尚未得到作者选择；本报告不生成固定大纲。

