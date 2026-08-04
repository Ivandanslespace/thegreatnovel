// 世界生成：validate 通过后 acceptProposal(slug, proposal, seed) 用种子确定性展开初始 WorldState
// （NPC 数值细节、初始资源分布，宪法 §1.1 可重放），落盘 blueprint.json + Init 事件(seq 0) +
// state.json + 小说文件（novel.ts）。随机只走 rng.ts。
import type { GameEvent, Language, Npc, WorldState } from './types.ts';
import { SCHEMA_VERSION } from './types.ts';
import { roll } from './rng.ts';
import { clone, recomputeStanding } from './state.ts';
import { appendEvent, saveWorld, writeJsonFile } from './store.ts';
import { validateProposal, type ProposalIssue, type WorldProposal } from './validate.ts';
import { createNovel } from './novel.ts';
import {
  FOCUS_CAP_DEFAULT,
  INITIAL_RESOURCE_MAX,
  INITIAL_RESOURCE_MIN,
  INITIAL_SUPPLIES_MAX,
  INITIAL_SUPPLIES_MIN,
  MAINTENANCE_RESOURCE,
  NPC_GOAL_START_MAX,
  NPC_GOAL_START_MIN,
  NPC_OTHER_START_MAX,
  NPC_OTHER_START_MIN,
  PLAYER_START_POWER,
} from './balance.ts';

/** `tgn new` 写入的世界登记信息（seed 在此确定，accept 沿用）。 */
export interface WorldMeta {
  worldSlug: string;
  language: Language;
  seed: number;
}

/** 行动表与 proposal 的持久化载体：worlds/<slug>/blueprint.json。 */
export interface Blueprint {
  slug: string;
  seed: number;
  language: Language;
  proposal: WorldProposal;
}

export type AcceptResult =
  | { ok: true; state: WorldState }
  | { ok: false; issues: ProposalIssue[] };

/**
 * 校验 + 初始化世界。确定性：同一 proposal + seed 展开结果逐字段一致。
 * 存档约定：先 appendEvent Init(seq 0) 携带初始状态，再 saveWorld（verify 重放起点）。
 */
export function acceptProposal(slug: string, proposalRaw: unknown, seed: number, root?: string): AcceptResult {
  const vr = validateProposal(proposalRaw);
  if (!vr.ok) return { ok: false, issues: vr.issues };
  const p = vr.proposal;

  let rng = { seed, counter: 0 };

  // 玩家初始资源分布（种子展开）
  const playerResources: Record<string, number> = {};
  for (const res of p.resources) {
    const isMaint = res === MAINTENANCE_RESOURCE;
    const r = roll(rng, isMaint ? INITIAL_SUPPLIES_MIN : INITIAL_RESOURCE_MIN, isMaint ? INITIAL_SUPPLIES_MAX : INITIAL_RESOURCE_MAX);
    rng = r.state;
    playerResources[res] = r.value;
  }

  // NPC 数值细节（种子展开）：proposal 已给定的资源值保留，其余按目标/非目标区间抽取
  const npcs: Npc[] = p.npcs.map((spec) => {
    const res: Record<string, number> = {};
    for (const k of p.resources) {
      const given = spec.resources[k];
      if (typeof given === 'number') {
        res[k] = given;
        continue;
      }
      const isGoal = k === spec.goal;
      const r = roll(rng, isGoal ? NPC_GOAL_START_MIN : NPC_OTHER_START_MIN, isGoal ? NPC_GOAL_START_MAX : NPC_OTHER_START_MAX);
      rng = r.state;
      res[k] = r.value;
    }
    // 目标资源至少 1：NPC 的目标驱动行为从真实持有开始（宪法 §7）
    if ((res[spec.goal] ?? 0) < 1) res[spec.goal] = 1;
    return {
      id: spec.id,
      name: spec.name,
      goal: spec.goal,
      resources: res,
      power: spec.power,
      attitude: 0,
      alive: true,
      knowledgeIds: [],
      pendingEvents: [],
      lastActed: 0,
    };
  });

  // 宏观锚点按 tier 升序进入 zones.anchors（tierUp 物化时消费，宪法 §7）
  const anchors = p.expansionAnchors
    .slice()
    .sort((a, b) => a.tier - b.tier)
    .map((a) => a.id);

  const state: WorldState = {
    schemaVersion: SCHEMA_VERSION,
    worldSlug: slug,
    language: p.language,
    seed,
    rngCounter: rng.counter,
    turn: 1,
    phase: 'playing',
    tier: 0,
    player: {
      resources: playerResources,
      focus: FOCUS_CAP_DEFAULT,
      focusMax: FOCUS_CAP_DEFAULT,
      knowledge: [],
      assets: [],
      absolutePower: PLAYER_START_POWER,
      effectiveCapacity: PLAYER_START_POWER,
      relativeStanding: 0,
      position: 'start',
      capacityPenalty: 0,
    },
    npcs,
    // 明规则开局已知；隐藏规则只能经失败/调查/关系揭示（宪法 §1.1、§7）
    rulesKnown: [...p.rulesExplicit],
    unlocks: [],
    zones: { materialized: [], anchors },
    windows: [],
    lastFactsSeq: 0,
    pendingPlayerEvents: [],
    lastTurnReport: null,
  };
  state.player.relativeStanding = recomputeStanding(state);

  // 行动表 + proposal 持久化
  const blueprint: Blueprint = { slug, seed, language: p.language, proposal: p };
  writeJsonFile(slug, 'blueprint.json', blueprint, root);

  // Init 事件（seq 0）→ saveWorld
  const initEvent: GameEvent = { seq: 0, turn: 1, type: 'Init', payload: { state: clone(state) } as unknown };
  appendEvent(slug, initEvent, root);
  saveWorld(state, root);

  // 小说文件 + 元数据
  createNovel(slug, state, p, root);

  return { ok: true, state };
}
