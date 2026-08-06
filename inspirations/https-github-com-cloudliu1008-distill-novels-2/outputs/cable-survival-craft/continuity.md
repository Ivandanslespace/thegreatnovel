# 连续性账本与未闭环规则

## 纜車规则账本

- Sources: `book-01-82fe54fd · segment-0001 · 行 68-78`；`book-01-82fe54fd · segment-0053 · 行 10598-10601`
- Immutable while supported: 纜車是移动中的个人安全边界；未经许可的人不能进入；怠速平均每小时 5 公里；每日有一次落点机会；升级会改变空间、防护和功能。
- Mutable state: 当前等级、空间、护甲、武器槽、附属建筑、车体损伤、是否待机/停滞。
- Check rule: 新章节不能让人物无说明地多次降落、瞬移到其它纜車或在车体未受损时被外部直接伤害。
- Confidence: high

## 时间与昼夜账本

- Sources: `book-01-82fe54fd · segment-0011 · 行 2328-2511`；`book-01-82fe54fd · segment-0081 · 行 14766-14919`
- Immutable while supported: 白天更适合落点；夜晚有降温、浓雾和诡类威胁；制作、升级、药酒和设备都消耗可见时间。
- Mutable state: 当前时段、升级倒计时、落点距离、撤离窗口、夜间威胁是否已锁定。
- Check rule: 新章节若跨夜，必须说明人物在哪里、为何能避开夜间威胁、设备是否仍在运行；不能只用“过了一夜”跳过资源与伤势账。
- Confidence: high

## 成长与资源账本

- Sources: `book-01-82fe54fd · segment-0002 · 行 334-404`；`book-01-82fe54fd · segment-0055 · 行 10780-10955`；`book-01-82fe54fd · segment-0092 · 行 16366-16509`
- Immutable while supported: 经验推动等级；突破符有等级/属性方向；天赋选择不可随意全取；职业有转职条件；制作和攻击消耗材料、弹药、耐久或耐力。
- Mutable state: 苏牧的等级、属性、职业栏、天赋、弹药、食物、水、材料、药酒和装备耐久。
- Check rule: 新章节必须把关键消耗记入库存；不能把“量产”写成无图纸、无材料、无时间的全能生产，也不能把血参药酒的体质增益和恢复疲劳混成永久等级提升。
- Confidence: high

## 知识状态账本

- Sources: `book-01-82fe54fd · segment-0044 · 行 8866-9031`；`book-01-82fe54fd · segment-0058 · 行 11312-11324`；`book-01-82fe54fd · segment-0100 · 行 17670-17692`
- Immutable while supported: 系统面板、每日情报、日记、频道消息和旁观者视角不是同一信息源；知道怪物存在不等于知道其属性或弱点。
- Mutable state: 苏牧知道的坐标、怪物类型、攻击规则、他人伤势、外部队伍动向和敲门威胁触发条件。
- Check rule: 新章节写“苏牧早已知道”时，必须回到之前的卡片、频道、日记或观察证据；间接听说不能自动升级为亲眼确认。
- Confidence: high

## 关系与承诺账本

- Sources: `book-01-82fe54fd · segment-0028 · 行 6220-6228`；`book-01-82fe54fd · segment-0078 · 行 14462-14475`；`book-01-82fe54fd · segment-0095 · 行 16802-16820`
- Immutable while supported: 苏牧与林雨薇以信息、物资和贡献分配互惠；陈军以木箭产能换资源；周振国的组织/制符身份带来规则信息和风险。
- Mutable state: 已偿还/未偿还的人情、已公开的底牌、交易价格、合作范围、组织归属和受伤状态。
- Check rule: 关系升级必须有新增权限或共同风险；若人物突然无条件信任，必须补一个可验证事件。
- Confidence: medium-high

## 已知冲突、编辑残留与待确认项

- Sources: `book-01-82fe54fd · segment-0096 · 行 17064-17103`；`book-01-82fe54fd · segment-0100 · 行 17572-17614`
- `SOURCE_COVERAGE_GAP`：front matter 写 `chapter_count=294`，正文只识别 100 段；本知识库不能代表完整作品。
- `EDITORIAL_INSERTION`：`segment-0096` 是章节错乱说明，不能参与剧情、风格或人物状态推断。
- `TITLE_NUMBER_GAP`：标题编号不连续并重复“第37章”；使用 segment ID，不用标题序号做时间线主键。
- `NIGHT_THREAT_RULE_OPEN`：敲门威胁是否严格由亲眼看见、间接描述还是其它条件触发，当前只有角色解释和有限样本，标为待验证。
- `LEVEL_BREAKTHROUGH_OPEN`：转职后自然升级与突破符的关系在第90章由主角推测，尚未被系统明确证实。
- `CORPSE_COLLECTION_OPEN`：军火库中怪物与被救女性尸体消失，可能连接更高层威胁，但在测试快照截断处未回收。
- `LOOT_ACCOUNT_OPEN`：外来队伍拿走的箱子、军火库的五级怪物掉落和爆炸后的资源数量不完全对账。
- Confidence: high for the existence of these gaps; medium or low for their future explanation.
