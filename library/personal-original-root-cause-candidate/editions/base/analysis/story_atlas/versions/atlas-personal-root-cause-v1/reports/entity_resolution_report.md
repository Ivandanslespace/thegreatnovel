# Entity Resolution Report

## 覆盖结论

- `entity_resolution_map.json` 登记 21 个主要实体，21/21 为 `CANON`，以本报告的 map-backed denominator 计实体证据覆盖 **100%**。
- 当前 Atlas 的 `CANON + HARD` 角色/势力节点均可回指该 map 或真实 source span；没有把未解析候选静默升格为实体。
- map 同时记录 4 类 alias/context conflict 和 1 个 unresolved identity candidate；这些是 review queue，不降低已登记实体的确定性覆盖。

## 主要 canonical entities

唐三、唐昊、凌岳、戴沐白、朱竹青、奥斯卡、宁荣辉、马红俊、白沉砚、胡列昭、千仞霄、比比宸、玉小刚、大明、二明、独孤博、唐月衡、唐啸、泰坦、雪崩、波赛川。

其中终局边界所依赖的实体证据包括：

- 唐三/凌岳：成年男性伴侣、双神共同完成者（`span_eeae31dd6055c25dbe5e42bf`、`span_78e506ec415b579ab48eb2b9`）。
- 比比宸：终局死亡；千仞霄：神位破碎、武魂受损并获赦免；胡列昭：获准存活（`span_fa378dd5cb85560640398b82`、`span_78e506ec415b579ab48eb2b9`）。
- 波赛川：第六考 canonical 名、限制条件与海神斗罗身份上下文（`span_bdcd51f5d104315268594b9a`、`span_6799dd6b2feac5a6cd41c9c1`）。

## Alias 规则

1. `大师`：在人物对话/叙述语境可映射玉小刚；普通名词用法不得强制合并。
2. `泰坦`：力之一族人物泰坦与泰坦巨猿二明必须依完整词组和上下文区分。
3. `哥/三哥/岳哥`：关系称呼；不建立血缘或正式兄弟关系（`span_f40472f2eaaabb9134b7db26`、`span_b13758a8912afe6f7fc361ff`）。
4. `海神/修罗神/天使神/罗刹神`：可能指神位/神力，也可能指承载者；人物节点与神位节点分开。

## 已修复与仍待复核

- 已修复：Arc29 ch260 的旧名“波赛西”全部改为“波赛川”；当前全 45 Arc 指定旧名扫描为 0，后续 Atlas 只使用 `波赛川` canonical alias。
- 待复核：Arc37 使用 `char_a_lan`/“阿岚”，早期 Arc 使用 `char_a_yin`/“阿银”，另有“蓝银皇”语境；entity map 没有稳定 canonical entry，不能按字符串相似度自动合并。
- 未解析候选：第 379 章的“五行大陆执行者”只有遇害事实，没有姓名、身份链或与主角的直接关系（`span_78e506ec415b579ab48eb2b9`）。

## 性别与关系边界

核心男性设定在 45/45 Arc 的 CANON 记录中未发现相反证据；唐三—凌岳应保持成年男性伴侣关系。任何“哥/兄弟”称谓仍需按说话人和场景解释，不得改写为血缘。

## Review Queue

- `阿岚/阿银/蓝银皇` 的实体合并与 source-span 级确认。
- `泰坦` 人物/物种标题消歧。
- 神位名称与承载者在后续图谱中的 node_type 分离。
- 五行大陆执行者身份链、地点和责任主体。
