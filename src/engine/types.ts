// 核心数据模型。项目硬约束：全部用 union type，不用 enum/namespace。
// 宪法 §1：世界先运行，小说后书写——这些结构是因果的载体，叙事只表达已成立的事实。

export type Language = 'zh' | 'en' | 'fr' | 'ar';
export type Phase = 'proposed' | 'playing' | 'ended';

/** 当前存档格式版本（WorldState.schemaVersion）。 */
export const SCHEMA_VERSION = 1;
export type RiskLevel = 'low' | 'medium' | 'high';
/** 机会窗口 ≤3 类：供给波动 / 威胁 / 机会（宪法 §6 稀缺与机会成本）。 */
export type WindowKind = 'supply' | 'threat' | 'opportunity';

export interface Asset {
  id: string;
  level: number;
}

/**
 * 三层能力字段语义（宪法 §5）：
 * - absolutePower：已挣得的长期策略容量，只增不减，除非明确损失事件带世界内因果；
 * - effectiveCapacity：当前受资源/维护/位置限制的可用能力，可回撤；
 * - relativeStanding：相对真实稳定 cohort 的位置（0..1），随 cohort 重算，可回撤。
 */
export interface PlayerState {
  resources: Record<string, number>;
  /** 专注：主角杠杆的物化货币（宪法 §3），focus>0 时行动附带 revealed 风险-收益分布。 */
  focus: number;
  focusMax: number;
  knowledge: string[];
  assets: Asset[];
  absolutePower: number;
  effectiveCapacity: number;
  relativeStanding: number;
  position: string;
  /** 维护欠缴带来的容量惩罚（0..1），由 TimeAdvanced 事件写入。 */
  capacityPenalty: number;
}

/**
 * NPC 是目标驱动的真实行动者（宪法 §7），不是等待玩家触发的背景板。
 * goal 为目标资源 id：缺资源者获取；power 高者争夺机会窗口。
 * pendingEvents：玩家不在场事件的缓冲（信息边界）。
 */
export interface Npc {
  id: string;
  name: string;
  goal: string;
  resources: Record<string, number>;
  power: number;
  /** -3..+3，±1 有因可溯（宪法 §9）。 */
  attitude: number;
  alive: boolean;
  knowledgeIds: string[];
  pendingEvents: GameEvent[];
  lastActed: number;
}

/**
 * 事件类型 union。Init 携带开局状态快照，是 verify 重放的起点；
 * 其余事件全部由纯函数 reducer（state.ts）施加。
 */
export type EventType =
  | 'Init'
  | 'ActionResolved'
  | 'TimeAdvanced'
  | 'NpcActed'
  | 'WindowOpened'
  | 'WindowClosed'
  | 'TierUp'
  | 'KnowledgeGained'
  | 'AssetUpgraded'
  | 'FactRevealed'
  | 'WorldFinished';

/** payload 为 unknown，由 reducer 按 type 收窄为对应 Payload 接口（保证可 JSON 序列化）。 */
export interface GameEvent {
  seq: number;
  turn: number;
  type: EventType;
  payload: unknown;
}

export interface InitPayload {
  state: WorldState;
}

export interface ActionResolvedPayload {
  actionId: string;
  success: boolean;
  /** 本次收益结算值（base±spread 分布 × 转化加成）。 */
  yield: number;
  /** 含成本扣除（负数）与收益（正数）。 */
  resourceDeltas: Record<string, number>;
  focusDelta?: number;
  knowledgeAdded?: string[];
  assetInvest?: { id: string; levels: number };
  powerDelta?: number;
  /** 只有携带 lossCause 的明确损失才允许 absolutePower 下降（宪法 §5）。 */
  lossCause?: string;
  relationDeltas?: Record<string, number>;
  windowsOpened?: OpportunityWindow[];
  unlocks?: string[];
  /** 结算消耗的 RNG 计数器终点（重放时恢复确定性流）。 */
  rngCounter: number;
}

export interface TimeAdvancedPayload {
  turn: number;
  focusRegen: number;
  maintenancePaid: number;
  maintenanceShortfall: number;
  capacityPenalty: number;
  resourceDeltas: Record<string, number>;
  rngCounter: number;
  turnReport: TurnReport;
}

export interface NpcActedPayload {
  npcId: string;
  /** 世界内因果描述，±1 态度漂移必须有因可溯（宪法 §9）。 */
  cause: string;
  resourceDeltas?: Record<string, number>;
  powerDelta?: number;
  attitudeDelta?: number;
  rngCounter?: number;
}

export interface WindowOpenedPayload {
  window: OpportunityWindow;
  rngCounter?: number;
}

export interface WindowClosedPayload {
  windowId: string;
  cause: string;
}

export interface TierUpPayload {
  newTier: number;
  /** 新 cohort 压力倍数：保留成果但重面相对失控（宪法 §5）。 */
  cohortScale: number;
  zone: Zone;
  /** 旧层劳动背景化标记（宪法 §1.2）。 */
  backgroundRule: string;
  rngCounter: number;
}

export interface KnowledgeGainedPayload {
  knowledge: string;
}

export interface AssetUpgradedPayload {
  assetId: string;
  level: number;
}

export interface FactRevealedPayload {
  fact: string;
  cause: string;
}

/** 行动 effects 的固定动词表：引擎只认识这些动词，杜绝自由文本改后果（宪法 §1、§9）。 */
export type ActionEffect =
  | { verb: 'resource'; resource: string; amount: number }
  | { verb: 'knowledge'; knowledge: string }
  | { verb: 'assetInvest'; asset: string }
  | { verb: 'relation'; npcId: string; delta: number }
  | { verb: 'windowOpen'; kind: WindowKind; labelKey: string }
  | { verb: 'unlock'; unlock: string };

/** 风险是可知分布（宪法 §1.1）：base 期望收益、spread 波动幅度、hiddenTag 失败才揭示的隐藏事实。 */
export interface RiskSpec {
  level: RiskLevel;
  base: number;
  spread: number;
  hiddenTag?: string;
}

export interface ActionRequires {
  knowledge?: string[];
  assetLevel?: number;
  tier?: number;
  resources?: Record<string, number>;
  /** 需已获得的 unlock 标记（缺失原因码 unlock:<id>）。 */
  unlocks?: string[];
}

export interface ActionCosts {
  resources?: Record<string, number>;
  focus?: number;
}

export interface ActionDef {
  id: string;
  label: string;
  timeCost: number;
  requires: ActionRequires;
  costs: ActionCosts;
  risk: RiskSpec;
  effects: ActionEffect[];
}

/** 机会窗口：有开启/关闭回合与可归因来源（宪法 §6、§7）。 */
export interface OpportunityWindow {
  id: string;
  kind: WindowKind;
  labelKey: string;
  openedTurn: number;
  expiresTurn: number;
  cause: string;
}

/** 物化区：先验证候选再成事实（宪法 §7），由种子确定性展开生成。 */
export interface Zone {
  id: string;
  anchorId?: string;
  nameKey: string;
  tier: number;
  trait: string;
}

/** 回合报告：玩家事件、不在场事件、窗口快照与维护支出。 */
export interface TurnReport {
  turn: number;
  playerEvents: GameEvent[];
  offscreen: GameEvent[];
  windows: OpportunityWindow[];
  /** 本回合过期关闭的窗口（因果可见：删除叙事不能删除因果，宪法 §1.1）。 */
  windowsClosed: Array<{ windowId: string; labelKey: string; cause: string }>;
  maintenancePaid: number;
}

export interface WorldState {
  /** 存档格式版本：为未来格式演进留余地（verify 重放不做强制校验）。 */
  schemaVersion: number;
  worldSlug: string;
  language: Language;
  seed: number;
  /** RNG 计数器：所有随机消耗都记录在此，保证重放确定性。 */
  rngCounter: number;
  turn: number;
  phase: Phase;
  tier: number;
  player: PlayerState;
  npcs: Npc[];
  rulesKnown: string[];
  /** 已获得的解锁标记（unlock 效果动词产出；行动可经 requires.unlocks 引用）。 */
  unlocks: string[];
  zones: { materialized: Zone[]; anchors: string[] };
  windows: OpportunityWindow[];
  /** 历史指针：最后一条已写入事件的 seq（verify 重放对齐用）。 */
  lastFactsSeq: number;
  /** 待回合结算的玩家事件（endTurn 时吸入 TurnReport）。 */
  pendingPlayerEvents: GameEvent[];
  lastTurnReport: TurnReport | null;
}

/** 杠杆物化（宪法 §3）：focus>0 时玩家看到的完整风险-收益分布；NPC 永远拿不到。 */
export interface RevealedInfo {
  expectedYield: number;
  downsidePct: number;
  hiddenTag?: string;
}

export interface LegalAction {
  id: string;
  label: string;
  timeCost: number;
  costs: ActionCosts;
  risk: RiskSpec;
  legal: boolean;
  /** requirements 未满足原因码：tier:N / knowledge:K / assetLevel:N / resources:R / focus / standing:N */
  missing: string[];
  revealed?: RevealedInfo;
}

export type ErrorCode =
  | 'E_ILLEGAL_ACTION'
  | 'E_UNKNOWN_ACTION'
  | 'E_WORLD_NOT_FOUND'
  | 'E_REPLAY_MISMATCH';

export interface EngineError {
  code: ErrorCode;
  reason: string;
  hints: string[];
}

export interface ActionOutcome {
  actionId: string;
  success: boolean;
  yield: number;
  notes: string[];
}

export type ResolveResult =
  | { ok: true; newState: WorldState; events: GameEvent[]; outcome: ActionOutcome }
  | { ok: false; error: EngineError };

/** 阶层跃迁硬门槛（宪法 §5）：资产等级 + 知识数 + 相对位置。 */
export interface TierGate {
  minAssetLevel: number;
  minKnowledge: number;
  minStanding: number;
}
