// 全部数值常量集中（项目硬约束：数字只进此文件）。每个常量后标注宪法依据条款号。
import type { RiskLevel, TierGate, WindowKind } from './types.ts';

/** +25%/级资产转化加成：已挣得成果提高后续行动效率（宪法 §4“可积累与复利”）。 */
export const ASSET_CONVERSION_BONUS = 0.25;

/** 知识转化加成：每条相关经验提高 10%（宪法 §4、§1.1 可理解性）。 */
export const KNOWLEDGE_CONVERSION_BONUS = 0.1;

/** 资产维护成本：1 单位资源/级/回合。成本保持决策空间而非惩罚成长（宪法 §4.1 积累的载体）。 */
export const MAINTENANCE_COST_PER_LEVEL = 1;

/** 维护支付使用的资源 key（由 worldgen 定义具体语义）。 */
export const MAINTENANCE_RESOURCE = 'supplies';

/** 维护不足导致的容量惩罚：0.5（保留部分能力但明显受限，损失有因可溯，宪法 §5）。 */
export const MAINTENANCE_SHORTFALL_PENALTY = 0.5;

/** Focus 恢复速度：1/回合；上限 3（宪法 §3 主角杠杆，focus>0 触发 revealed）。 */
export const FOCUS_REGEN_PER_TURN = 1;
export const FOCUS_CAP_DEFAULT = 3;

/** 调查成本：消耗 1 focus（信息边界要求为信息付费，宪法 §7）。 */
export const INVESTIGATE_COST_FOCUS = 1;

/** 风险等级成功率：风险是可知分布，不是任意惩罚（宪法 §1.1、§3）。 */
export const SUCCESS_CHANCE: Record<RiskLevel, number> = {
  low: 0.85,
  medium: 0.65,
  high: 0.45,
};

/** 最大并发机会窗口数：稀缺来自约束而非稀有度颜色（宪法 §6）。 */
export const MAX_OPEN_WINDOWS = 3;

/** 每回合开窗概率：基于种子抽取的世界反馈（宪法 §7）。 */
export const WINDOW_OPEN_CHANCE = 0.55;

/** 窗口存活回合：错过即为真实机会成本（宪法 §6）。 */
export const WINDOW_DURATION: Record<WindowKind, number> = {
  supply: 3,
  threat: 2,
  opportunity: 2,
};

/** 阶层跃迁 cohort 压力倍数：进入更大世界但保留成果（宪法 §5 关系反转与阶层跃迁）。 */
export const TIER_COHORT_SCALE = 4;

/** 阶层跃迁基础幂基线（供 worldgen 参考）。 */
export const TIER_COHORT_BASE_POWER = [2, 8, 32, 128];

/** 投资获得绝对力量增长：资本化积累（宪法 §4、§5）。 */
export const POWER_PER_ASSET_LEVEL = 2;

/** 每阶层机会事件表（≤3 类：供给波动/威胁/机会，可归因描述，宪法 §7）。 */
export const TIER_WINDOW_TABLE: Record<number, { kind: WindowKind; labelKey: string; weight: number }[]> = {
  0: [
    { kind: 'supply', labelKey: 'window.supply.convoy', weight: 4 },
    { kind: 'threat', labelKey: 'window.threat.raider', weight: 3 },
    { kind: 'opportunity', labelKey: 'window.opportunity.trade', weight: 3 },
  ],
  1: [
    { kind: 'supply', labelKey: 'window.supply.harvest', weight: 3 },
    { kind: 'threat', labelKey: 'window.threat.competition', weight: 3 },
    { kind: 'opportunity', labelKey: 'window.opportunity.contract', weight: 4 },
  ],
  2: [
    { kind: 'supply', labelKey: 'window.supply.export', weight: 3 },
    { kind: 'threat', labelKey: 'window.threat.siege', weight: 4 },
    { kind: 'opportunity', labelKey: 'window.opportunity.alliance', weight: 3 },
  ],
  3: [
    { kind: 'supply', labelKey: 'window.supply.tide', weight: 2 },
    { kind: 'threat', labelKey: 'window.threat.dominance', weight: 5 },
    { kind: 'opportunity', labelKey: 'window.opportunity.founding', weight: 3 },
  ],
};

/** 投资资产等级 +1 获得的绝对力量增益。 */
export const POWER_PER_ASSET_INVEST = 2;

/** NPC 目标驱动行为常量（宪法 §7 NPC 自主性）。 */
export const NPC_GATHER_CHANCE = 0.6;
export const NPC_GATHER_AMOUNT = 2;
export const NPC_RESOURCE_TARGET = 6;
export const NPC_CONTEST_CHANCE = 0.35;

/** 阶跃到 tier N+1 的硬门槛（资产等级 + 知识数 + 相对位置）：设计达成时间约 20–30 回合（宪法 §5、§10 节奏）。 */
export const TIER_GATES: TierGate[] = [
  // →T1 ≈ 6–8 回合（资产 1 + 知识 2），→T2 ≈ 8–10 回合（资产 3 + 知识 4），→T3 ≈ 8–10 回合（资产 5 + 知识 7）
  { minAssetLevel: 1, minKnowledge: 2, minStanding: 0.3 },
  { minAssetLevel: 3, minKnowledge: 4, minStanding: 0.5 },
  { minAssetLevel: 5, minKnowledge: 7, minStanding: 0.6 },
];

export const MAX_TIER = 3;

/** 物化候选验证池：由种子确定性展开生成，先验证再成事实（宪法 §7）。 */
export const ZONE_TRAITS = ['water-source', 'shelter', 'market', 'watchpoint', 'workshop', 'crossroad'] as const;

// ---- T2：世界生成（worldgen）初始展开常量 ----

/** 主角开局绝对力量 1：低于初始 cohort 基线（TIER_COHORT_BASE_POWER[0]=2），形成真实控制缺口（宪法 §5、核心循环 CONTROL DEFICIT）。 */
export const PLAYER_START_POWER = 1;

/** 开局补给 5–9：支撑前几回合维护决策，让成本尽早进入权衡（宪法 §4.1 成本保持决策空间）。 */
export const INITIAL_SUPPLIES_MIN = 5;
export const INITIAL_SUPPLIES_MAX = 9;

/** 其余初始资源 0–4：稀缺来自获取约束而非匮乏惩罚（宪法 §6）。 */
export const INITIAL_RESOURCE_MIN = 0;
export const INITIAL_RESOURCE_MAX = 4;

/** NPC 目标资源开局 2–5：NPC 有自己的资源与目标，不是背景板（宪法 §7）。 */
export const NPC_GOAL_START_MIN = 2;
export const NPC_GOAL_START_MAX = 5;

/** NPC 非目标资源开局 0–2（宪法 §7）。 */
export const NPC_OTHER_START_MIN = 0;
export const NPC_OTHER_START_MAX = 2;

// ---- T2：interact 交互结算常量 ----

/** 态度 ≥0 才接受合作/交易：关系是双方状态与博弈，不是好感度条（宪法 §9）。 */
export const INTERACT_ATTITUDE_ACCEPT_MIN = 0;

/** 合作产出：基础 1，态度 ≥2 时 +1（宪法 §9 关系改变交易条件）。 */
export const COOPERATE_YIELD_BASE = 1;
export const COOPERATE_ATTITUDE_BONUS = 1;

/** 交易：玩家付 1 单位维护资源；回货基础 1，态度 ≥1 时 +1，受 NPC 持有上限（宪法 §6 机会成本）。 */
export const TRADE_GIVE_AMOUNT = 1;
export const TRADE_RECEIVE_BASE = 1;

/** 打听（ask）：基础概率 0.3 + 0.1×(态度+3)，上限 0.9；信息是资源，为信息付费（宪法 §7），focus 成本见 INVESTIGATE_COST_FOCUS。 */
export const ASK_BASE_CHANCE = 0.3;
export const ASK_ATTITUDE_STEP = 0.1;
export const ASK_MAX_CHANCE = 0.9;

/** 承诺（commit）期限：turn+4 回合；承诺产生 deadline 与责任，违约须有后果（宪法 §9）。 */
export const COMMIT_DEADLINE_TURNS = 4;
