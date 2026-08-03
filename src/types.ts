/**
 * TheGreatNovel V1 —— 通用纯数据接口。
 *
 * 引擎是"世界无关的原语解释器"（宪章 §2、§8）：这里不出现任何世界特定的
 * 资源名、行动名、区域名；一切差异由 World Blueprint 数据表达。
 */

/**
 * 存档模式版本，用于迁移（C2：旧档经 migrations 链式前向迁移后加载）。
 * v1→v2：state.history 数组移出 state.json，history.jsonl 成为唯一审计源。
 */
export const SCHEMA_VERSION = 2;

/** Blueprint 数据格式版本（与存档模式版本独立演进）。 */
export const BLUEPRINT_SCHEMA_VERSION = 1;

/**
 * 表现层语言代码（V1.1：开局选择语言）。纯表现层元数据，
 * 不参与任何结算数值与确定性；旧 Blueprint/存档无此字段时按 "zh" 处理。
 */
export type Language = 'zh' | 'en' | 'fr' | 'ar';

// ---------------------------------------------------------------------------
// 条件语言（唯一条件系统，供 requires / gate / trigger / leverage 共用）
// ---------------------------------------------------------------------------

/** 资产阈值：某资产数量 >= / <= n。 */
export interface AssetCondition {
  asset: string;
  gte?: number;
  lte?: number;
}

/** 事实已知：玩家已知某条事实（知识边界见 knowledge.ts，宪章 §7）。 */
export interface FactCondition {
  fact: string;
}

/** flag 已置：状态中存在某布尔标记。 */
export interface FlagCondition {
  flag: string;
}

/** 回合窗口：当前回合落在 [gte, lte] 区间（"窗口开启/关闭"）。 */
export interface TimeWindowCondition {
  window: { gte?: number; lte?: number };
}

/** 阶层阈值：当前阶层 >= / <= n。 */
export interface TierCondition {
  tier: { gte?: number; lte?: number };
}

export interface AndCondition {
  and: Condition[];
}

export interface OrCondition {
  or: Condition[];
}

export type Condition =
  | AssetCondition
  | FactCondition
  | FlagCondition
  | TimeWindowCondition
  | TierCondition
  | AndCondition
  | OrCondition;

// ---------------------------------------------------------------------------
// 效果语言
// ---------------------------------------------------------------------------

/** 资产增减（delta 可为负）。 */
export interface AssetEffect {
  asset: string;
  delta: number;
}

/** 使一条世界事实转为玩家已知（信息即资源，宪章 §7）。 */
export interface LearnFactEffect {
  learnFact: string;
}

/** 置一个布尔 flag。 */
export interface SetFlagEffect {
  setFlag: string;
}

/** 解锁一个区域（世界扩张）。 */
export interface UnlockRegionEffect {
  unlockRegion: string;
}

/** 清除一个 flag。 */
export interface ClearFlagEffect {
  clearFlag: string;
}

export type Effect =
  | AssetEffect
  | LearnFactEffect
  | SetFlagEffect
  | UnlockRegionEffect
  | ClearFlagEffect;

// ---------------------------------------------------------------------------
// Blueprint 结构
// ---------------------------------------------------------------------------

export interface BlueprintMeta {
  name: string;
  /** 玩家的一句话世界描述原文。 */
  prompt: string;
  seed: number;
  /** 控制力来源轴（知识/记忆、关系、资源生产、身份法律、时空规则或自定义，宪章 §2）。 */
  controlAxis: string;
  title?: string;
  /** 表现层语言（可选，缺省 "zh"；可被开局命令 --language 覆盖）。 */
  language?: Language;
}

/** 宪章 §12 最小检查七问（校验器检查存在性与非空）。 */
export interface DesignCheck {
  controlGap: string;
  legibleRule: string;
  leverageConversion: string;
  compounding: string;
  opportunityCost: string;
  worldFeedback: string;
  portability: string;
}

/** 宏观规律：稳定、可理解、对所有人一致（宪章 §1）。 */
export interface Law {
  id: string;
  description: string;
  /** 规律何时生效（缺省恒真）。 */
  trigger?: Condition;
  /** 规律生效时对世界的效果（如置 flag：大潮窗口开启）。 */
  effect?: Effect[];
}

/** 资产类型：由世界自定义，非固定货币/经验/好感度（宪章 §2）。 */
export interface AssetType {
  id: string;
  name: string;
  kind: string;
  description?: string;
  /** 持有维护成本：每回合扣除（长期资产带责任，宪章 §4.1）。 */
  maintenance?: { asset: string; perTurn: number };
  /** 初始持有量。 */
  initial?: number;
}

/** 行动的一个可能结果（结算时按 weight 加权抽签，种子随机）。 */
export interface Outcome {
  id: string;
  weight: number;
  description: string;
  effects?: Effect[];
  /** 不可逆结果（宪章 §6：永久后果必须可追溯）。 */
  irreversible?: boolean;
  /** 结果触发的解锁（区域等）。 */
  unlocks?: string[];
}

/** 行动：世界中的合法行为定义（引擎只解释，不发明，宪章 §9）。 */
export interface Action {
  id: string;
  name: string;
  description: string;
  /** 所属阶层门槛。 */
  tier: number;
  requires?: Condition[];
  costs?: { time?: number; assets?: Record<string, number> };
  /** 风险抽签标签：随机一律由 hash(seed+turn+actionId+seedTag+counter) 派生。 */
  risk?: { chance?: number; seedTag: string };
  outcomes: Outcome[];
  /** 杠杆独占行动：仅 leverage.enabled 时合法（宪章 §3）。 */
  leverageOnly?: boolean;
}

/** 杠杆 modifier：条件满足时改写某行动的某个结果权重（转化差异）。 */
export interface LeverageModifier {
  id: string;
  description: string;
  action: string;
  outcome: string;
  when?: Condition;
  /** 命中时该结果的最终权重。 */
  setWeight: number;
}

/** 主角非对称杠杆声明（宪章 §3、§3.1）。 */
export interface Leverage {
  id: string;
  name: string;
  description: string;
  /** 改变了哪条因果链（必须绑定至少一条 law）。 */
  causalChain: string[];
  /** 主角需要付出什么。 */
  cost: string;
  /** 普通人为什么难以复制。 */
  whyExclusive: string;
  /** 杠杆独占行动 id 列表。 */
  exclusiveActions: string[];
  modifiers: LeverageModifier[];
  /** 开关：测试用于验证"移除杠杆后最优路径必须改变"（宪章 §3 检验）。 */
  enabled: boolean;
}

/** 势力/重要 NPC 的计划项：触发条件满足时结算一次（离屏 tick 数据源）。 */
export interface ActorPlan {
  id: string;
  trigger: Condition;
  effects: Effect[];
  description: string;
  /** 后果是否对玩家可见（不可见 = "这件事发生时我不在场"，宪章 §7）。 */
  visible?: boolean;
}

/** 势力/重要 NPC：有自己的目标、资源、计划（宪章 §7）。 */
export interface Actor {
  id: string;
  name: string;
  goals: string[];
  resources?: Record<string, number>;
  plans: ActorPlan[];
}

/** 事实：世界真相的一条记录，带可见性范围（宪章 §7）。 */
export interface Fact {
  id: string;
  description: string;
  /** player：开局即玩家已知；hidden：须经观察/调查/事件转为已知。 */
  scope: 'player' | 'hidden';
  /** 主题分组（observe --scope 用）。 */
  category?: string;
  /** 远方锚点：仅有名字与层级约束，无细节，不得描述其内部（宪章 §7）。 */
  anchor?: { tier: number };
}

/** 定时事件：与势力计划同构，属于世界本身。 */
export interface ScheduledEvent {
  id: string;
  trigger: Condition;
  effects: Effect[];
  description: string;
  visible?: boolean;
}

/** 区域：世界的空间维度（可解锁）。 */
export interface Region {
  id: string;
  name: string;
  description: string;
  initiallyUnlocked?: boolean;
  tier?: number;
}

/** 阶层门槛：达到 gate 时跃迁并解锁新行动组/区域（宪章 §5）。 */
export interface TierGate {
  tier: number;
  name: string;
  description: string;
  gate: Condition;
  unlocks?: string[];
}

/** Lazy Expansion 规则（宪章 §7：先候选校验，再成为世界事实）。 */
export interface ExpansionRule {
  id: string;
  description: string;
  trigger: Condition;
  constraints: string[];
}

export interface WinLose {
  win?: Condition;
  lose?: Condition;
  description: string;
}

/** World Blueprint：一个世界的完整声明式定义。 */
export interface Blueprint {
  schemaVersion: number;
  meta: BlueprintMeta;
  designCheck: DesignCheck;
  laws: Law[];
  assetTypes: AssetType[];
  actions: Action[];
  leverage: Leverage;
  actors: Actor[];
  facts: Fact[];
  scheduledEvents?: ScheduledEvent[];
  regions: Region[];
  tiers: TierGate[];
  expansion: ExpansionRule[];
  winLose: WinLose;
}

// ---------------------------------------------------------------------------
// 运行时状态
// ---------------------------------------------------------------------------

export interface ChapterRecord {
  index: number;
  title: string;
  slug: string;
  file: string;
  startTurn: number;
  endTurn: number;
}

/**
 * 单局游戏的完整状态（saves/<世界名>/state.json 的唯一事实源）。
 *
 * schema v2（M8）：history 不再内嵌——history.jsonl 是唯一审计源，
 * state 只保留计数/游标用于完整性对账。
 */
export interface GameState {
  schemaVersion: number;
  world: string;
  seed: number;
  /**
   * 表现层语言（V1.1 起开局时写入）。契约：**字段缺失恒等于 "zh"**——
   * 旧存档按中文处理，迁移链不回填该字段（零风险），任何代码不得事后改写它。
   */
  language?: Language;
  turn: number;
  tier: number;
  assets: Record<string, number>;
  /** 玩家已知事实 id 集合（knowledge.ts 投影来源）。 */
  knownFacts: string[];
  flags: Record<string, boolean>;
  unlockedRegions: string[];
  /** 已结算的势力计划 id。 */
  plansFired: string[];
  eventsFired: string[];
  /** 每行动抽签计数器（重放确定性来源）。 */
  counters: Record<string, number>;
  /** 杠杆使用记录（可追溯、不可无因清零，宪章 §5）。 */
  leverageUses: number;
  /** history.jsonl 已写入条目数（完整性对账游标，M8）。 */
  historyCount: number;
  /** history.jsonl 最后一条的回合（回放/合成辅助游标）。 */
  historyLastTurn: number;
  chapters: ChapterRecord[];
  ended?: { reason: string; turn: number };
  chapterCursor: number;
  lastChapterTurn: number;
}

/** 历史条目：append-only 审计（宪章 §1.1 可重放）。turn = 产生时的实际回合。 */
export interface HistoryEntry {
  turn: number;
  kind: 'action' | 'tick' | 'tier' | 'maintenance' | 'system' | 'ending';
  text: string;
  visible: boolean;
  source: string;
}

// ---------------------------------------------------------------------------
// 结算结果
// ---------------------------------------------------------------------------

/** 单条后果：可回答"发生了什么/为什么/玩家当时能知道什么"（宪章 §1.1）。 */
export interface Consequence {
  kind: HistoryEntry['kind'] | 'cost' | 'outcome' | 'leverage';
  text: string;
  visible: boolean;
  source: string;
  /** 产生时的实际回合（结算引擎填写；写入 history 时用于回合归因）。 */
  atTurn?: number;
}

/** act 结算返回值。 */
export interface Resolution {
  actionId: string;
  outcomeId: string | null;
  consequences: Consequence[];
  unlocked: string[];
  tierUp: boolean;
  irreversible: boolean;
  ended: boolean;
  turn: number;
}

/** 结构化错误（CLI 硬拒格式）。 */
export interface EngineError {
  code: string;
  message: string;
  details?: string[];
}
