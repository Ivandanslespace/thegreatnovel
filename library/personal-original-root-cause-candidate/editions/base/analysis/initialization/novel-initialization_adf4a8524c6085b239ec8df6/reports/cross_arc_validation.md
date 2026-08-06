# Cross-Arc Validation（45/45）

审计对象是当前初始化 `novel-initialization_adf4a8524c6085b239ec8df6` 已被状态文件列为完成的 45 个 Arc output，以及 `entity_resolution/entity_resolution_map.json`、`synthesis/` 和既有 `reports/contradiction_audit.md`。本报告只做证据审计，不新增正文、Canon 或续写路线。

章节 ordinal 统一从 `source_coverage.json` 的 `source_span_id -> ordinal` 映射读取；部分旧 Arc 的 `source_evidence.ordinal` 是 Arc 内序号，不能直接当作全书 ordinal。每条判断尽量同时给出 `arc_id`、ordinal 与 source span。

## 覆盖与状态

- `analysis/initialization/.../status.json`：`completed_arc_ids=45`、`failed_arc_ids=[]`、`pending_arc_ids=[]`，覆盖 379 个有效章节的全书范围 1–379；当前初始化状态仍为 `READY_WITH_GAPS`，缺口来自未来可能性空间的未决假设，而非源覆盖或 Arc output 缺失。
- 本次补审已纳入原先待补的 Arc34–35、Arc36–37、Arc40–41（294–323、338–353）；六个 output 均通过 `ArcExtractionOutput` schema 校验，章节归属与 source span 覆盖准确。当前交叉审计统计为 `45/45 Arc`、`379/379 chapters`、`audit_errors=0`、`old_name_hits=0`、`metrics=COMPLETE`。
- 既有 `reports/contradiction_audit.md` 判断没有已确认的故事边界矛盾；本报告曾发现的 Arc-level 旧名污染已按原文修复（见下文），它是证据图谱问题，不应被静默吸收。

### 补审 Arc34–41（当前事实层）

- `init-arc_0e597309ea1bcf479b928f48`（ch294–300，`span_4d4cd6b52e576119206e5f71`、`span_381068395cc2fd72ab28b241`、`span_c8f2b33b94062513c68795e5`）：鲨鲸之战后第四考闭合，第五考七圣柱挑战推进；凌岳献祭创伤仍以保护/失控风险线程存在，没有提前写成完整复活。
- `init-arc_38e6ffd157f25868b33373ae`（ch301–307，`span_bdcd51f5d104315268594b9a`、`span_6799dd6b2feac5a6cd41c9c1`、`span_ad1b35a873b4c00df1d6f7fd`、`span_b7759f8f63739276e505e599`）：第五考闭合，第六考明确使用 canonical 名“波赛川”、一炷香与前六魂技限制；规则越界撤离与第七考海神三叉戟衔接成立，未检出“波赛西”。
- `init-arc_dcac1f57b3d4f5813901b7fe`（ch308–315，`span_a7ca9884b99311094ded00d`、`span_5e312a97313b6963c256620d`）：第八考的五年、九环、全魂骨及复活凌岳条件为 CANON；武魂帝国崛起、唐晨污染线与比比宸神器对决属于终局前 ACTIVE 线程，未与 ch379 的战后闭合冲突。
- `init-arc_12da02667825008902e02788`（ch316–323，`span_dcc5777652a62396f2e0ba56`、`span_bfec8b368e11c5b051e6f6aa`、`span_14cb1f22fd693d74f3f1fc08`）：ch316–317 保留献祭后复活条件，ch318 才由海神之光、魂骨与魂环完成凌岳灵魂/身体融合复活；阿岚重生与家庭复原、昊天宗归返随后推进，未把阶段性复活提前到 ch247 或 ch257。
- `init-arc_b6f001188d49a1012754abc6`（ch338–345，`span_a4355b2312e5c1b14e8069ed`、`span_221ed41c9b397ed8b8dafd3e`、`span_d1d6c0e706012c34a2c94af9`）：暗魔邪神虎、三环同吸、神器赌约与海神三叉戟被夺均为终局前 CANON；“同时吸收三头魂环”是魂环规则例外，不是双神同时出手，不能与终局单次单一神力规则混淆。
- `init-arc_dcb9effe4d7afc3e8a34e4d4`（ch346–353，`span_b3978bf03cf60212cebbfc07`、`span_074853fc899af790b73798fa`、`span_24c710e39d5dc8010fd2d71d`）：观音泪破神、海神神念救援/海神之心消失及深海魔鲸王僵持构成终局前连续链；Arc41 的未击杀状态由 ch354+ 后续证据承接，不得在此处提前宣告终局胜负。

上述六个 Arc 未引入新的旧名污染、硬规则冲突或终局状态提前升级；Arc36–37 尤其验证“献祭/分阶段复活→ch318 完整复活”的时间顺序，Arc40 的三环同吸与双神单次出手属于不同规则层。

## 1. 唐三、凌岳与全男性设定

### CANON

- `init-arc_4597f25694972da0648fa0c2`，ch61，`span_3d575e86987a38d57309425c`：唐三、凌岳和戴沐白的角色记录均明确为成年男性；凌岳被记录为裂空战狮武魂持有者。
- `init-arc_c43dea4a1a57df8c55e9a12e`，ch81，`span_34c40b584c41971253c63fc1`：唐三、凌岳、宁荣辉、朱竹青等核心队员的 CANON 记录明确为成年男性；ch96，`span_1a3713480d11e989eeb10409` 还明确记录马红俊的男性伴侣语境。
- `init-arc_f7a6d52f2c1b3c3c620e7b0d`，ch120，`span_ead79c62761f3a205ea4bad1`：宁荣辉明确为七宝琉璃塔辅助系成年男性。
- `init-arc_04ce966bd1a7a4ad6d838832`，ch51，`span_4ad40c82f819cf00854ec3ec`：素云涛与司衡均以“男伴”关系记录。
- 终局 `init-arc_3113cabad757faf66982dfb6`，ch378–379，`span_eeae31dd6055c25dbe5e42bf`、`span_78e506ec415b579ab48eb2b9`：唐三与凌岳作为成年伴侣共同存活，并非血缘或正式兄弟。

### 结论

45 个已完成 Arc 中，没有发现把唐三、凌岳、宁荣辉或上述核心男性角色标记为女性的相反 CANON 记录；“全男性核心设定”在当前证据范围内可安全沿用。对未命名角色及新增角色，性别仍应保持 UNKNOWN，不能从称谓或职业推断。

## 2. 旧名与实体别名

### RESOLVED（审计发现后已由主线程修复）：`波赛西` 旧名污染

- `entity_resolution/entity_resolution_map.json` 将 `character_bo_saichuan` 的 CANON 名称设为“波赛川”，别名为“波赛川 / 海神斗罗 / 大供奉”，首次证据为 ch260 的 `span_7c70758c033b7ba8b7056a57`。
- 但 `init-arc_b1cc5feaf8f0f9ac5ebf301c` 在同一 ch260、同一 `span_7c70758c033b7ba8b7056a57` 的 alias 记录写成 `canonical_entity: 波赛西`，并在章节特征与压力记录中重复该旧名。
- 这与既有 `reports/contradiction_audit.md` “旧表面名波赛西全局命中为 0”及实体解析 map 直接不一致。主线程随后按原文将该 Arc 的全部 9 处旧名修正为“波赛川”；当前 `init-arc_b1cc5feaf8f0f9ac5ebf301c` output 中 `波赛西` 命中为 0、`波赛川` 命中为 9，45 个已完成 Arc 的指定旧名扫描为 0，`initialize refresh` 保持 `failed=0`。因此该 blocker 已 RESOLVED，但修复前后的证据链仍保留在本节，后续 Atlas 只能使用“波赛川” canonical alias。

### WARNING：阿岚/阿银别名尚未进入实体解析 map

- `init-arc_07cde0f8ba0f8eb7657e00a1`，ch216–217，`span_0b90f5a16aae0ce3862fae44`、`span_a140dd7b729e5f60418ba971` 使用 `char_a_lan`，名称为“阿岚/阿银”。
- 早期 `init-arc_50c306a47c8f0a030d5b2d4d`，ch1，`span_e873d651b91177bd91933a9c` 使用 `char_a_yin`；`init-arc_b1cc5feaf8f0f9ac5ebf301c` ch260–261 又使用“蓝银皇”。当前 `entity_resolution_map.json` 没有阿岚、阿银或蓝银皇的 canonical entry。
- 这还不足以证明正文身份矛盾，但属于跨 Arc alias drift；必须保留为待解析候选，不能依字符串相似度自动合并。

### 其他旧名扫描

在 45 个已完成 output 的所有字符串字段中，没有发现 `小舞、胡列娜、千仞雪、比比东、宁荣荣`；当前稳定名使用的是 `凌岳、胡列昭、千仞霄、比比宸、宁荣辉、波赛川` 等本 Edition 名称。上面的“波赛西”是唯一检出的指定旧名污染，修复后全局命中为 0。

## 3. “哥 / 兄弟”称呼边界

### CANON 证据与安全解释

- `init-arc_84242af6b6a168d16093c925`，ch25、ch31，`span_923429d223f5cb3954aa28d7`、`span_1e1c91c7bcab0b59d5e9ff95`：工读生称凌岳“凌岳哥/老大”，属于舍长和群体称呼。
- `init-arc_04ce966bd1a7a4ad6d838832`，ch59，`span_f40472f2eaaabb9134b7db26`：alias 记录明确写“哥（昵称，非血缘）”；对应 relationship 明确写唐三与凌岳“非血缘兄弟”。
- `init-arc_b1cc5feaf8f0f9ac5ebf301c`，ch257，`span_b13758a8912afe6f7fc361ff`：特征中出现凌岳喊“哥哥”，但没有新增血缘证据。
- `init-arc_f7a6d52f2c1b3c3c620e7b0d`，ch121，`span_2ad670b42a9a942f82e6d3bd`，以及 `init-arc_d87270f15aad521b23cc93e5`，ch231，`span_143735c3014eb8fa96b104da`：二明、大明与凌岳的“兄弟”是森林盟友/共同守域关系；不是唐三—凌岳的血缘证明。
- 同一 `init-arc_d87270f15aad521b23cc93e5` ch235，`span_49ccd979a873d1a3b963fffa` 的“唐三—奥斯卡兄弟”也是团队语境；不应被升级为家族关系。
- 终局 `init-arc_3113cabad757faf66982dfb6` ch378–379，`span_eeae31dd6055c25dbe5e42bf`、`span_78e506ec415b579ab48eb2b9` 再次明确唐三—凌岳为成年伴侣，“不是血缘或正式兄弟关系”。

### 结论

“哥、哥哥、兄弟、三哥、岳哥”只能作为上下文称呼或盟友/团队关系；当前边界安全条件是不得由此推导唐三与凌岳有血缘或正式兄弟身份。其他真正的“亲兄弟”（例如杨无敌—杨无双）应单独按其角色证据处理，不能泛化到主角关系。

## 4. 双神与“单次单一出手”

- 终局前的 `init-arc_a420e2101c101910cc388554`（ch356、ch358，`span_131185ad3c7194d273da3761`、`span_b75fcf1452f08f56d3179140`）、`init-arc_efe91d2432c44b074c5164b0`（ch366–367，`span_7a4de91056dfb12743b6f258`、`span_b8b555680cd55d29bb12b33d`）和 `init-arc_cb32179dd7cc87eb07e16243`（ch374–375，`span_57caf780220ae3b26ebebcb9`、`span_8886ce99a2d978eb6071de6e`）都把双神共存、魔剑代价或终局状态保留为 INFERENCE/UNKNOWN；没有提前伪造最终规则。
- `init-arc_3113cabad757faf66982dfb6` ch378，`span_eeae31dd6055c25dbe5e42bf`：CANON 明确唐三与凌岳完成双神共存，可以在海神与修罗神之间切换，但“一次只能由一个神位出手”；对应 world rule 禁止两种神力同时发动攻击。
- `init-arc_340ff6f5dd1a5091eb0ce0d0` ch161，`span_939bf9d3b601426b103e720d` 的“一次只能使用一种武魂”是早期双生武魂规则，不等同于终局双神规则；两者不存在语义冲突，但不能互相替换。

### 结论

当前边界 SAFE：允许双神切换和凌岳作为共同完成者，但禁止同一动作叠加海神、修罗神两种主动出手。长期持续时间、非战斗消耗和是否存在额外反噬仍为 UNKNOWN（`span_eeae31dd6055c25dbe5e42bf`），不能自行补写。

## 5. 终局状态、政治退出与开放事项

### 死亡、复活与神位状态（CANON，按时间推进）

- `init-arc_cb32179dd7cc87eb07e16243` ch374–375，`span_57caf780220ae3b26ebebcb9`、`span_8886ce99a2d978eb6071de6e`：唐三死亡级反转与复活光前置，是阶段事件，不是最终状态。
- `init-arc_3113cabad757faf66982dfb6` ch376，`span_679c5e4110fa88c01b2f95ff`：唐三神魂归位并复活；ch377，`span_fa378dd5cb85560640398b82`：最终决战；ch379，`span_78e506ec415b579ab48eb2b9`：比比宸替千仞霄承受修罗魔剑后死亡，千仞霄神位破碎、武魂受损并获赦免，胡列昭获准存活。
- 凌岳的状态是逐阶段兑现而非矛盾：`init-arc_d87270f15aad521b23cc93e5` ch231 `span_143735c3014eb8fa96b104da` 献祭并提出复活条件；`init-arc_63fbd0480e965d34dfe41b16` ch247 `span_fd24cafdffcddce089b6696e` 身体先回归而灵魂仍在魂环；`init-arc_b1cc5feaf8f0f9ac5ebf301c` ch257 `span_b13758a8912afe6f7fc361ff` 为四分之一融合、ch261 `span_f475d8ad5f017b1d099f9ebf` 仍是订婚阶段；随后 `init-arc_c41fd64e91c63920a502ef06` ch324 起记录为复活后的伴侣，终局 ch378–379 存活。

### 政治退出

- `init-arc_c41fd64e91c63920a502ef06` ch324，`span_3f248e82b92d8a08ce4de2a1` 仍处于唐家军/帝师战争阶段。
- `init-arc_3113cabad757faf66982dfb6` ch379，`span_78e506ec415b579ab48eb2b9` 明确唐三退出蓝昊王、帝师与帝国战争事务，要求停战、战俘约束、唐家军解散及军用暗器退出；仅保留神级威胁出现时的干预例外。
- 没有更晚 Arc 把唐三重新放回常驻人间政务。续写若无新因果让其恢复日常统治，属于 CURRENT-BOUNDARY-UNSAFE。

### 婚礼未举行

- `init-arc_b1cc5feaf8f0f9ac5ebf301c` ch261，`span_f475d8ad5f017b1d099f9ebf` 只证明唐三与凌岳“订婚”。
- `init-arc_3113cabad757faf66982dfb6` ch379，`span_78e506ec415b579ab48eb2b9` 将婚礼记录为开放承诺（`OPEN_NEAR_HORIZON`）；正文没有婚礼仪式已经举行的证据。
- 因此“已订婚、婚礼待兑现”是 CANON 边界；“已经结婚”是越界推断。

### 五行大陆

- `init-arc_3113cabad757faf66982dfb6` ch379，`span_78e506ec415b579ab48eb2b9` 只确认“五行大陆执行者遇害”这一远端事件，hook 状态为 `OPEN_REMOTE`。
- `synthesis/graphs.json` 将其标为 `CANON_PLUS_UNKNOWN`，`synthesis/future_possibility_space.md` 仅列为候选 / wildcard；没有证据证明唐三或凌岳已接受任务、必须立即介入或该信息就是唯一续写主线。

## 6. 跨 Arc 稳定线程与冲突判定

| 线程 | 证据链 | 判定 |
|---|---|---|
| 唐三—凌岳关系 | ch25/31 竞争与称呼（`span_923429d223f5cb3954aa28d7`、`span_1e1c91c7bcab0b59d5e9ff95`）；ch59 明确非血缘（`span_f40472f2eaaabb9134b7db26`）；ch142/153、ch190 伴侣选择；ch231/247/257/261 献祭与分离式复活；ch378/379 成年伴侣、共同存活（`span_eeae31dd6055c25dbe5e42bf`、`span_78e506ec415b579ab48eb2b9`） | CANON 阶段演化，无故事矛盾；称谓不能改写关系性质 |
| 凌岳复活线 | ch231 献祭 → ch247 身体先回归 → ch257/261 部分融合与订婚 → ch318 灵魂/身体融合复活 → ch378/379 双神共同存活 | CANON 阶段推进；后续仍不得补写未被证据支持的中间细节 |
| 双神线 | ch356–375 为 INFERENCE/UNKNOWN；ch378 明确共存与单次单一出手 | 先前未知在终局被收束，无冲突；长期代价仍 UNKNOWN |
| 终局敌手线 | ch374–375 死亡/复活前置；ch376–379 复活、决战、比比宸死亡、千仞霄神位破碎与赦免 | CANON 时间顺序闭合；不得让已死亡比比宸无因复活或恢复千仞霄完整神位 |
| 战后政治线 | ch324 仍在帝师/唐家军战争阶段；ch379 退出帝国事务并设定神级威胁例外 | CANON 阶段切换；常驻政治复归不安全 |
| 五行大陆线 | 仅 ch379 `OPEN_REMOTE` hook | CANON 事实 + UNKNOWN 介入；不可升级为唯一近端主线 |

审计期间唯一曾发现的 Arc-level blocker 是上节“波赛西”旧名污染，现已 RESOLVED；`init-arc_f7a6d52f2c1b3c3c620e7b0d` ch120–121（`span_90fc2285c840c1210a6e9ec1`、`span_2ad670b42a9a942f82e6d3bd`）记录的“对外叙述与真实经历”则已正确保留为 UNKNOWN，有意隐瞒不应被修成矛盾。当前 45/45 证据审计不再存在 blocker。

## 验收结论

### BLOCKERS

0. 当前跨 Arc 证据审计 blocker=0：45/45 Arc、379/379 chapters、`failed_arc_ids=[]`、`audit_errors=0`、`old_name_hits=0`；`波赛西` 修复后的 refresh 仍为 `failed=0`。`READY_WITH_GAPS` 仅表示未来可能性空间和作者方向仍有开放项，不是 source/Arc 覆盖 blocker。

### WARNINGS

- `阿岚/阿银/蓝银皇` 尚未在实体解析 map 形成稳定 canonical entry；Arc37 的 `char_a_lan` 与早期 `char_a_yin` 必须继续保持候选别名，不自动合并。
- “哥/哥哥/兄弟”必须继续按关系语境解释，不能升格为血缘。
- 双神长期成本、持续时间和非战斗使用方式仍 UNKNOWN。
- 未来输出应继续使用 source manifest 的全书 ordinal；不要把旧 Arc 的 Arc-local `ordinal` 当作全书章节号。

### CURRENT-BOUNDARY-SAFE

- 唐三、凌岳及核心队伍的成年男性设定；唐三—凌岳是男性伴侣而非血缘兄弟。
- 唐三已复活；凌岳已在终局存活；比比宸死亡；千仞霄神位破碎、武魂受损并获赦免；胡列昭获准存活。
- 双神可以切换，但单次只能一神出手；未确认的长期代价保持 UNKNOWN。
- 唐三退出常驻人间政治，婚礼是已订婚后的开放承诺而非已举行事实。
- 五行大陆只作为远端 hook，不能自动变成近端任务。

### CURRENT-BOUNDARY-UNSAFE

- 重新引入已修复的“波赛西”等旧名，或未经解析把“阿岚/阿银”静默合并为 canonical。
- 把“哥/哥哥/兄弟”写成唐三与凌岳有血缘或正式兄弟关系。
- 在同一动作中同时发动海神与修罗神；把双神长期成本写成已证实规则。
- 无因复活比比宸、恢复千仞霄完整神位、撤销唐三政治退出，或宣称婚礼已举行。
- 把五行大陆执行者遇害直接写成唐三或凌岳已接受的唯一续写任务。
