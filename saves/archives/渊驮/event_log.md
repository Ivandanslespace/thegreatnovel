# 事件日志

<!-- 每次选择结算后追加一条记录。格式固定，便于回溯。 -->
<!-- 事件ID规则：EVT-T{回合数}，如 EVT-T01, EVT-T14。同一回合多事件用 EVT-T14a, EVT-T14b。 -->
<!-- 格式迁移说明：Turn 1-16 使用扩展JSON格式（event_type/actors/consequences）。 -->
<!-- 自 Turn 17 起，新事件应同时包含 event_id 字段，并遵循 engine/event_sourcing.md 标准。 -->

---

## Turn 1 | Day 1 清晨 | 世界创建

```json
{
  "event_type": "world_init",
  "turn": 1,
  "day": 1,
  "time": "清晨",
  "description": "世界「渊驮」创建。主角在脊营外围窝棚中醒来，开始第一天的生存。",
  "actors": ["player"],
  "location": "脊营·外围窝棚",
  "consequences": {
    "player_created": true,
    "base_created": "外围窝棚 Lv.1",
    "initial_npcs": ["焦叔", "阿苔", "铆钉"],
    "initial_faction": "脊营"
  },
  "narrative_flags": ["开局", "新手期开始"]
}
```

---

## Turn 2 | Day 1 上午 | 锚桩塔

```json
{
  "event_type": "npc_interaction",
  "turn": 2,
  "day": 1,
  "time": "上午",
  "description": "主角前往锚桩塔帮焦叔检查固定索。用脉感发现第三索扣下方骨面存在微裂纹。焦叔确认裂纹存在，要求保密，并邀请主角午餐。",
  "actors": ["player", "npc_001"],
  "location": "脊营·锚桩塔",
  "consequences": {
    "relationship_change": {
      "npc_001": {"trust": "+10", "respect": "+5", "intimacy": "+5"}
    },
    "player_exp": "+15",
    "player_status": "手掌擦伤（2轮）",
    "discovery": "锚桩微裂纹（第三索扣下方）",
    "shared_secret": ["player", "npc_001"],
    "invitation": "锚桩塔午餐"
  },
  "narrative_flags": ["焦叔信任线开启", "锚桩劣化伏笔激活"]
}
```

---

## Turn 3 | Day 1 正午 | 外围窝棚·静心感知

```json
{
  "event_type": "talent_use",
  "turn": 3,
  "day": 1,
  "time": "正午",
  "description": "主角在窝棚中主动使用脉感「静心感知」，深入感知渊驮本体状态。发现：1)锚桩裂纹是渊驮骨细胞的生物排异反应（试图排出异物）；2)渊驮意识到背上有人类但态度为容忍/无感；3)渊驮有明确行进方向；4)渊驮极度疲惫但不会停下。",
  "actors": ["player"],
  "location": "脊营·外围窝棚",
  "consequences": {
    "player_exp": "+10",
    "player_fatigue": "+15",
    "player_hunger": "-10（错过焦叔午餐）",
    "talent_uses_remaining": 1,
    "discoveries": [
      "锚桩裂纹=生物排异（非机械磨损）",
      "渊驮有行进方向",
      "渊驮容忍人类但非保护",
      "渊驮极度疲惫"
    ],
    "new_mysteries": [
      "渊驮在朝哪里走？",
      "如果渊驮排出锚桩，脊营怎么办？"
    ]
  },
  "narrative_flags": ["世界观深层揭示", "锚桩危机升级", "行进方向悬念埋设"]
}
```

---

## Turn 4 | Day 1 午后 | 南侧苔田

```json
{
  "event_type": "exploration_discovery",
  "turn": 4,
  "day": 1,
  "time": "午后",
  "description": "主角前往南侧苔田实地观察，确认渊驮行进方向为北偏东。发现资源分布方向性规律：北面迎风（净露碎裂），南面背风（苔粮丰、净露完整、雾潮晚10分钟）。与阿苔交谈，获得净露收集知识和南侧热洞情报。",
  "actors": ["player", "npc_002"],
  "location": "脊营·南侧苔田",
  "consequences": {
    "player_exp": "+10",
    "player_hunger": "+15（阿苔给了苔粮饼）",
    "relationship_change": {
      "npc_002": {"affection": "+5", "trust": "+5", "intimacy": "+5"}
    },
    "discoveries": [
      "渊驮行进方向：北偏东",
      "资源方向性：南面苔粮丰/净露完整/雾潮晚10min",
      "苔田南侧第三排毛根后有异常热洞（热气外冒，非虫洞）"
    ],
    "npc_info_gained": "阿苔姐姐有记录数据的习惯",
    "event_003_progress": "热洞信息已由阿苔主动告知（提前触发）"
  },
  "narrative_flags": ["资源规律发现", "热洞悬念前置", "阿苔姐姐线索埋设"]
}
```

---

## Turn 5 | Day 1 黄昏 | 锚桩塔·信息交换

```json
{
  "event_type": "npc_interaction",
  "turn": 5,
  "day": 1,
  "time": "黄昏",
  "description": "主角向焦叔揭示锚桩裂纹真相=渊驮生物排异。焦叔确认信任，透露锚桩为'旧人'所建（非当代人类）。交付锚桩区通行牌+满罐脂膏+月度监测委托。同时告知南面资源规律，焦叔决定明日采集队南移。",
  "actors": ["player", "npc_001"],
  "location": "脊营·锚桩塔",
  "consequences": {
    "player_exp": "+20",
    "relationship_change": {
      "npc_001": {"trust": "+15", "respect": "+10", "dependency": "+5"}
    },
    "items_gained": ["锚桩区通行牌（绿色）", "脂膏罐（满）"],
    "quest_gained": "月度锚桩排异监测",
    "camp_change": "采集队明日南移两排",
    "lore_revealed": "锚桩为'旧人'所建，非当代人类",
    "secret_shared": ["锚桩排异真相（仅player+焦叔）"]
  },
  "narrative_flags": ["焦叔信任线质变", "旧人悬念激活", "主角角色升级：散人→锚桩监测者"]
}
```

---

## Turn 6 | Day 1 夜 | 南侧苔田边缘·净露收集

```json
{
  "event_type": "resource_gathering",
  "turn": 6,
  "day": 1,
  "time": "夜",
  "description": "主角利用南面背风区毛尖水珠完整的规律，用破布+陶罐成功收集净露3单位。期间遭遇一只巡逻态皮螨（未战斗，静止回避成功）。观察到热洞夜间活跃（渊驮夜间体温升高）。",
  "actors": ["player"],
  "location": "脊营·南侧苔田边缘",
  "consequences": {
    "player_exp": "+10（+5成就）",
    "player_fatigue": "+15",
    "resources_gained": {"pure_dew": "+3"},
    "items_used": "破布捆×1（剩余1）",
    "creature_encounter": "皮螨×1（巡逻态，回避成功）",
    "discoveries": ["热洞夜间活跃", "渊驮夜间体温升高"],
    "achievement": "第一滴水"
  },
  "narrative_flags": ["首次资源自主解决", "首次生物遭遇", "热洞夜间线索"]
}
```

---

## Turn 7 | Day 1 深夜 | 南侧热洞·首次探索

```json
{
  "event_type": "exploration",
  "turn": 7,
  "day": 1,
  "time": "深夜",
  "description": "主角跳入南侧热洞。发现内部为渊驮皮下免疫修复腔（3m×3m×2m），膜壁搏动，温度~45-50°C。腔壁上生长有髓晶（渊驮修复副产物）。触碰晶体后触发渊驮免疫排异反应：腔体收缩、分泌液体、试图排出异物。主角紧急攀绳逃出。骨削刀遗落洞底。获得髓晶碎片×1。",
  "actors": ["player"],
  "location": "脊营·南侧热洞（渊驮皮下）",
  "consequences": {
    "player_exp": "+20（含成就+10）",
    "player_hp": "-3（轻微烫伤）",
    "player_fatigue": "+15",
    "player_status": "掌心烫伤（2轮）",
    "items_lost": ["骨削刀（洞底，可回收）"],
    "items_gained": ["髓晶碎片×1（蓝色）"],
    "discoveries": [
      "热洞=渊驮免疫修复腔",
      "髓晶是渊驮修复副产物（非矿物）",
      "渊驮免疫系统会主动排异（腔体收缩+液体冲刷）",
      "渊驮对微小异物反应温和但持续"
    ],
    "achievement": "入兽"
  },
  "narrative_flags": ["首次探索完成", "髓晶来源揭示", "渊驮免疫机制实证", "骨削刀待回收"]
}
```

---

## Turn 8 | Day 1→2 夜→清晨 | 锚桩塔·过夜

```json
{
  "event_type": "rest_and_npc_interaction",
  "turn": 8,
  "day": 2,
  "time": "清晨",
  "description": "主角带伤到锚桩塔过夜。焦叔处理伤口、提供食物和住所。主角分享免疫腔/髓晶发现。焦叔透露'骨泪'=旧人对髓晶的称呼，旧人用骨泪修复锚桩（使其与骨长为一体）。焦叔决定次日找阿苔询问其姐姐笔记。第2天清晨焦叔已出发去苔田。",
  "actors": ["player", "npc_001"],
  "location": "脊营·锚桩塔",
  "consequences": {
    "player_exp": "+10",
    "player_hunger": "+20（焦叔给食物）",
    "player_fatigue": "70→20（睡眠恢复）",
    "player_hp": "47→50（睡眠恢复）",
    "relationship_change": {
      "npc_001": {"trust": "+5", "intimacy": "+5", "status": "friend"}
    },
    "lore_revealed": "骨泪=髓晶，旧人用其修复锚桩（与骨融合）",
    "npc_action": "焦叔Day2清晨去苔田找阿苔问笔记",
    "camp_change": "采集队南移两排（执行中）"
  },
  "narrative_flags": ["Day1结束", "焦叔关系升级friend", "骨泪修复线索激活", "Day2开始"]
}
```

---

## Turn 9 | Day 2 上午 | 南侧苔田·阿苔姐姐的信息 + 升级

```json
{
  "event_type": "npc_interaction_and_levelup",
  "turn": 9,
  "day": 2,
  "time": "上午",
  "description": "主角到苔田与焦叔、阿苔会合。阿苔透露姐姐8个月前去了上游（北）未归，留下三卷兽皮笔记。关键信息：骨泪必须趁热（1时辰内）使用才能与骨融合，硬化后只能磨粉当药引。主角的髓晶碎片已失效。阿苔约定中午回棚取笔记。主角经验满，升级至Lv2。",
  "actors": ["player", "npc_001", "npc_002"],
  "location": "脊营·南侧苔田",
  "consequences": {
    "player_levelup": "Lv1→Lv2",
    "player_exp": "+10（溢出5/200）",
    "player_attributes": "全属性+1（STR6/CON6/AGI7/SPI8）",
    "player_free_points": "+2（待分配）",
    "talent_choice_pending": "A雾读/B骨步/C脂工",
    "relationship_change": {
      "npc_002": {"trust": "+5", "intimacy": "+5"}
    },
    "lore_revealed": [
      "骨泪必须趁热（1时辰内）使用",
      "硬化骨泪只能磨粉当药引",
      "阿苔姐姐8个月前去了上游（北）",
      "姐姐留下三卷兽皮笔记"
    ],
    "quest_update": "中午去阿苔棚子取笔记",
    "item_status": "髓晶碎片已硬化失效（不可修锚桩）"
  },
  "narrative_flags": ["首次升级", "骨泪时效性揭示", "阿苔姐姐线索深化", "笔记获取任务设定"]
}
```

---

## Turn 10 | Day 2 午后 | 阿苔棚子·笔记研读

```json
{
  "event_type": "knowledge_acquisition",
  "turn": 10,
  "day": 2,
  "time": "午后",
  "description": "主角通读蓝的三卷笔记。关键发现：1)雾潮两年降一成（渊驮在变弱）；2)热洞分布图（5个，①号离桩80m但封闭，③号离桩300m开放中但超期）；3)热洞生命周期7-14天，③号已超期随时封闭；4)锚桩周围50m为热洞死区；5)北面400m有旧人刻痕（锚桩截面图）；6)渊驮变弱→热洞频率可能增加。",
  "actors": ["player"],
  "location": "脊营·阿苔棚子",
  "consequences": {
    "player_exp": "+10",
    "knowledge_gained": [
      "热洞分布图（5个点位）",
      "热洞生命周期7-14天",
      "③号超期（Day520起，已20+天）",
      "①号离桩80m（封闭3个月）",
      "锚桩50m死区",
      "雾潮两年降一成（渊驮变弱）",
      "北面400m旧人刻痕",
      "渊驮行进速度在降低"
    ],
    "strategic_assessment": "③号→锚桩跑程~25min，时限1时辰，可行但窗口紧",
    "urgency": "③号随时可能封闭，必须在封闭前完成采集"
  },
  "narrative_flags": ["战略情报完备", "采集窗口紧迫化", "旧人遗迹线索", "渊驮衰弱线"]
}
```

---

## Turn 11 | Day 2 午后 | ③号热洞·侦察与跑程实测

```json
{
  "event_type": "scouting",
  "turn": 11,
  "day": 2,
  "time": "午后",
  "description": "主角前往③号热洞确认状态（仍开放但愈合中，1-2天内封闭）。下洞回收骨削刀，确认剩余可采集晶体（最小×1）。实测洞口→锚桩塔跑程：4分钟（全速）。总采集耗时估算~5分钟，远在1时辰时限内。被铆钉目睹从南边跑向锚桩。",
  "actors": ["player", "npc_003（目击）"],
  "location": "脊营·③号热洞→锚桩塔",
  "consequences": {
    "player_exp": "+10",
    "items_recovered": ["骨削刀"],
    "route_timed": "③号→锚桩塔 4分钟（全速）",
    "harvest_plan": "明天清晨执行，总耗时~5分钟",
    "hole_status": "③号愈合中，腔体缩小，晶体减少至3根，1-2天封闭",
    "npc_witness": "铆钉目睹主角从南跑向锚桩（持刀、喘气）",
    "risk_flag": "铆钉可能产生怀疑/好奇"
  },
  "narrative_flags": ["采集计划成型", "骨削刀回收", "铆钉目击事件", "执行窗口锁定明天清晨"]
}
```

---

## Turn 12 | Day 2 黄昏→Day 3 寅时 | 焦叔协调 + ①号勘察 + 行动日开始

```json
{
  "event_type": "planning_and_scouting",
  "turn": 12,
  "day": 3,
  "time": "寅时",
  "description": "Day2黄昏：主角与焦叔确认明日行动计划（寅时执行，焦叔守桩接应）。随后勘察①号热洞位置：仍封闭，但脉感检测到皮下免疫活动正在聚集（2-3天后重开）。发现①号正上方骨板有旧人工程刻痕（锚桩三索+截面+中心点），证明旧人预知热洞位置。Day3寅时：主角醒来，出发执行采集。",
  "actors": ["player", "npc_001"],
  "location": "脊营·锚桩塔→①号→锚桩塔",
  "consequences": {
    "player_exp": "+5",
    "plan_confirmed": "Day3寅时执行③号采集，焦叔守桩",
    "discovery": "①号上方旧人工程刻痕（锚桩结构图）",
    "hole_status": "①号封闭中，免疫活动聚集，2-3天后重开",
    "lore_revealed": "旧人预知热洞出现位置（工程图刻在热洞正上方）",
    "npc_coordination": "焦叔确认寅时守桩接应",
    "risk_noted": "铆钉目击事件未处理（焦叔提醒）"
  },
  "narrative_flags": ["行动日", "焦叔协调完成", "旧人知识深度揭示", "①号未来备用确认"]
}
```

---

## Turn 13 | Day 3 清晨 | ③号→锚桩塔·骨泪采集与贴合（任务完成）

```json
{
  "event_type": "quest_completion",
  "turn": 13,
  "day": 3,
  "time": "清晨",
  "description": "主角寅时出发，直奔③号热洞。下洞切割最小骨泪晶体（成功）。触发加速免疫排异（第二次进入，腔体识别主角），紧急逃出。全速跑回锚桩塔（4分钟）。在焦叔接应下将骨泪贴合至裂纹处，30秒后晶体渗入骨面，裂纹封闭。渊驮心跳在贴合瞬间短暂'松弛'（感知到修复）。",
  "actors": ["player", "npc_001"],
  "location": "③号热洞→锚桩塔",
  "consequences": {
    "player_exp": "+40（采集+20，贴合+20成就）",
    "player_hp": "-3（膝盖撞伤）",
    "player_status": "掌心烫伤（新）+膝盖撞伤",
    "quest_complete": "锚桩裂纹修复",
    "anchor_status": "裂纹封闭，短期安全",
    "relationship_change": {
      "npc_001": {"trust": "+10"}
    },
    "achievement": "修桩人",
    "lore_moment": "渊驮在贴合瞬间心跳松弛（感知到修复/非排异反应）",
    "future_risk": "排异仍会继续，裂纹将复发（需长期方案）"
  },
  "narrative_flags": ["第一篇章高潮完成", "锚桩短期安全", "渊驮'感知'主角伏笔", "长期问题未解决"]
}
```

---

## Turn 14 | Day 3 上午→黄昏 | 铆钉交涉 + 蜕震预判 + 营地认知

```json
{
  "event_type": "social_and_recon",
  "turn": 14,
  "day": 3,
  "time": "黄昏",
  "description": "主角主动找铆钉，以'热洞纯脂膏'为半真 cover story 化解其疑虑。铆钉给骨刀换脂膏分成，并告知外围三根松索隐患。主角用脉感预判蜕震强度（~65%，渊驮疲劳），确认修复处可承受。焦叔今晚加辅索。主角形成初步假设：静态加固可能无法解决活体地基的排异，真正原因仍未知，旧人或北面可能提供验证线索。",
  "actors": ["player", "npc_003", "npc_001"],
  "location": "脊营·外围→锚桩塔",
  "consequences": {
    "player_exp": "+10",
    "relationship_change": {
      "npc_003": {"trust": "+5", "resentment": "-5", "status": "acquaintance"}
    },
    "items_gained": ["铆钉的骨刀（绿色）"],
    "deal_made": "下次热洞脂膏分铆钉一罐",
    "intel_gained": "外围东南三根松索（蜕震风险）",
    "talent_use": "脉感预判蜕震强度65%",
    "npc_action": "焦叔今晚加辅索",
    "hypothesis_formed": "（未确认）静态加固可能无法解决排异→需'生物相容'方向→旧人/北面可能有答案"
  },
  "narrative_flags": ["铆钉线缓和", "蜕震预判完成", "松索隐患处理", "假设形成（待验证）"]
}
```

---

## Turn 15 | Day 3 夜→Day 4 清晨 | 辅索加装 + 蜕震开始

```json
{
  "event_type": "community_action_and_disaster",
  "turn": 15,
  "day": 4,
  "time": "清晨",
  "description": "主角帮焦叔加装外围东南三根辅索。一位外围母亲主动帮忙。铆钉目睹全程，确认辅索牢固。Day4清晨蜕震开始，强度符合预判（~65%）。",
  "actors": ["player", "npc_001", "npc_003（目击）"],
  "location": "脊营·外围东南→锚桩塔",
  "consequences": {
    "player_exp": "+5",
    "player_fatigue": "+15（体力劳动）→睡眠恢复→30",
    "relationship_change": {
      "npc_003": {"respect": "+5"}
    },
    "camp_improvement": "外围东南三根辅索加装完成",
    "social_impact": "外围居民对主角态度改善",
    "disaster_start": "Day4清晨蜕震开始（强度65%）"
  },
  "narrative_flags": ["辅索完成", "社区连接", "蜕震正式开始"]
}
```

---

## Turn 16 | Day 4 清晨 | 蜕震·双感知观测

```json
{
  "event_type": "disaster_observation",
  "turn": 16,
  "day": 4,
  "time": "清晨",
  "description": "主角选择不抱桩，站立用雾读+脉感同时感知整个脊背状态。蜕震持续约90秒，强度65%符合预判。观测结果：1)骨泪修复处承受住了（微振动但无新裂纹）；2)7只深层寄兽被震出体表，铆钉队击杀；3)雾潮异常——比预期近20%（渊驮体表温度下降导致雾层压缩）；4)③号热洞完全封闭（愈合）；5)①号热洞免疫活动急剧加速，可能提前至明天重开。",
  "actors": ["player", "npc_003（击杀寄兽）", "npc_001（守桩）"],
  "location": "脊营·锚桩塔外围",
  "consequences": {
    "player_exp": "+15（观测+5，双天赋协同+10）",
    "achievement": "震中立（在蜕震中保持站立并完成完整观测）",
    "anchor_repair_status": "骨泪贴合处完好，无新裂纹",
    "parasite_event": "7只深层寄兽被震出，铆钉队击杀",
    "fog_anomaly": "雾潮比预期近20%（渊驮体温下降→雾层压缩）",
    "hole_status_change": {
      "③号": "完全封闭",
      "①号": "免疫活动急剧加速，预计Day5重开"
    },
    "strategic_update": "①号提前重开→采集窗口可能比预期早一天"
  },
  "narrative_flags": ["蜕震完成", "双天赋协同首次", "雾潮异常线", "①号加速重开", "③号正式关闭"]
}
```

---

## 📸 SNAPSHOT | Turn 10（补录）

完整状态已保存至各 .yaml 文件。
本快照对应回合：10
后续事件从 Turn 11 开始。

Turn 10 状态摘要：
- 主角 Lv2，双天赋（脉感/雾读），位于脊营·锚桩塔
- 锚桩裂纹已发现，骨泪修复计划进行中
- 焦叔 trust 30，阿苔 trust 25，铆钉 trust 5（怀疑中）
- ③号热洞已侦察，跑程4分钟
- 蓝的三卷笔记已通读
- 活跃悬念：父母失踪 / 锚桩排异 / 旧人遗迹 / 蓝的下落

---

## 📸 SNAPSHOT | Turn 16

完整状态已保存至各 .yaml 文件。
本快照对应回合：16
后续事件从 Turn 17 开始。

Turn 16 状态摘要：
- 主角 Lv2，双天赋（脉感/雾读），位于脊营·锚桩塔外围
- 锚桩骨泪修复完成（成就「修桩人」），蜕震验证通过
- 第一次蜕震已完成（Day4清晨，强度65%）
- 焦叔 trust 40（修桩搭档），阿苔 trust 35/affection 35，铆钉 trust 10（利益联盟）
- ③号热洞封闭，①号热洞预计Day5重开
- 雾潮异常（比预期近20%），渊驮衰弱证据链增长
- 活跃悬念：父母失踪 / 渊驮衰弱 / 旧人真相 / 蓝的下落 / ①号热洞
- 未确认假设：静态加固无法解决排异，需生物相容方向

---
