/**
 * 结算管线（引擎心脏，世界无关）：
 *
 * 合法性 → 扣时间+资产 → 种子抽签 → 杠杆 modifiers → 维护结算 → 不可逆标记
 * → world tick（时间给世界行动权）→ 知识更新（在效果应用中发生）
 * → 阶层门槛/胜负 → expansion 检查 → history → 自动保存（由调用方持久化）
 * → Resolution{consequences[], unlocked, tierUp, irreversible}
 *
 * 每条后果可回答"发生了什么/为什么/玩家当时能知道什么"（宪章 §1.1）。
 */
import type {
  Action,
  Blueprint,
  Consequence,
  EngineError,
  GameState,
  HistoryEntry,
  Outcome,
  Resolution,
} from './types.ts';
import { contextFromState, evalAll, evalCondition, explainUnmet } from './conditions.ts';
import { getEngineStrings, languageOf } from './i18n.ts';
import { deriveRandom, pickWeighted } from './rng.ts';
import { applyEffects, worldTick } from './tick.ts';
import { checkExpansion } from './expansion.ts';

export interface LegalActionInfo {
  action: Action;
  legal: boolean;
  /** 不合法时的结构化原因（Agent 向玩家解释"为什么不能这么做"）。 */
  reasons: string[];
}

/** 计算所有行动的合法性（含杠杆开关影响，宪章 §3）。 */
export function legalActions(bp: Blueprint, state: GameState): LegalActionInfo[] {
  const ctx = contextFromState(state);
  return bp.actions.map((action) => {
    const reasons: string[] = [];
    if (action.tier > state.tier) {
      reasons.push(`需要阶层 ${action.tier}（当前 ${state.tier}）`);
    }
    if (action.leverageOnly && !bp.leverage.enabled) {
      reasons.push(`杠杆「${bp.leverage.name}」不可用：该行动为杠杆独占`);
    }
    reasons.push(...explainUnmet(action.requires, ctx, bp));
    return { action, legal: reasons.length === 0, reasons };
  });
}

/** 结算后的维护成本在 worldTick 内按回合结算（M3，见 tick.ts settleMaintenance）。 */

/**
 * 行动在当前状态下的最终权重分布（含杠杆 modifier；纯读取，不 mutate 状态）。
 * M1：权重计算与全零检查必须在任何状态修改之前完成。
 */
export function finalOutcomeWeights(
  bp: Blueprint,
  state: GameState,
  action: Action,
): { weights: number[]; leverageApplied: boolean } {
  const weights = action.outcomes.map((o) => o.weight);
  let leverageApplied = false;
  if (bp.leverage.enabled) {
    const ctx = contextFromState(state);
    for (const mod of bp.leverage.modifiers) {
      if (mod.action !== action.id) continue;
      if (mod.when !== undefined && !evalCondition(mod.when, ctx)) continue;
      const idx = action.outcomes.findIndex((o) => o.id === mod.outcome);
      if (idx >= 0 && weights[idx] !== mod.setWeight) {
        weights[idx] = mod.setWeight;
        leverageApplied = true;
      }
    }
  }
  return { weights, leverageApplied };
}

/** 阶层门槛判定（可连续跃迁）。返回跃迁后果。 */
function checkTierGates(bp: Blueprint, state: GameState, consequences: Consequence[]): boolean {
  const t = getEngineStrings(languageOf(state));
  let tierUp = false;
  for (;;) {
    const next = bp.tiers.find((t2) => t2.tier === state.tier + 1);
    if (!next) break;
    if (!evalCondition(next.gate, contextFromState(state))) break;
    state.tier = next.tier;
    tierUp = true;
    consequences.push({
      kind: 'tier',
      text: t.tierUp(next.name, next.description),
      visible: true,
      source: `tier:${next.tier}`,
    });
    for (const regionId of next.unlocks ?? []) {
      if (!state.unlockedRegions.includes(regionId)) {
        state.unlockedRegions.push(regionId);
        const region = bp.regions.find((r) => r.id === regionId);
        consequences.push({
          kind: 'tier',
          text: t.regionUnlocked(region ? region.name : regionId),
          visible: true,
          source: `tier:${next.tier}`,
        });
      }
    }
  }
  return tierUp;
}

function checkEnd(bp: Blueprint, state: GameState, consequences: Consequence[]): void {
  if (state.ended) return;
  const t = getEngineStrings(languageOf(state));
  const ctx = contextFromState(state);
  if (bp.winLose.win && evalCondition(bp.winLose.win, ctx)) {
    state.ended = { reason: t.winReason(bp.winLose.description), turn: state.turn };
    consequences.push({ kind: 'system', text: t.endingEntry(bp.winLose.description), visible: true, source: 'winLose' });
  } else if (bp.winLose.lose && evalCondition(bp.winLose.lose, ctx)) {
    state.ended = { reason: t.loseReason(bp.winLose.description), turn: state.turn };
    consequences.push({ kind: 'system', text: t.endingEntry(bp.winLose.description), visible: true, source: 'winLose' });
  }
}

/** Resolution → history 条目（append-only 审计）。turn 取产生时的实际回合（minor）。 */
export function resolutionToHistory(resolution: Resolution): HistoryEntry[] {
  return resolution.consequences.map((c) => ({
    turn: c.atTurn ?? resolution.turn,
    kind: (c.kind === 'cost' || c.kind === 'outcome' || c.kind === 'leverage' ? 'action' : c.kind) as HistoryEntry['kind'],
    text: c.text,
    visible: c.visible,
    source: c.source,
  }));
}

/**
 * 结算一个行动。纯函数式地 mutate state；调用方（CLI）负责 history 追加与保存。
 * 非法行动硬拒：抛出带 code 与结构化 reasons 的 EngineError（宪章 §9）。
 */
export function resolveAction(bp: Blueprint, state: GameState, actionId: string): Resolution {
  if (state.ended) {
    throw { code: 'ALREADY_ENDED', message: `世界已结束（${state.ended.reason}），不能再行动` } satisfies EngineError;
  }

  const found = bp.actions.find((a) => a.id === actionId);
  if (!found) {
    throw { code: 'UNKNOWN_ACTION', message: `不存在的行动 "${actionId}"`, details: bp.actions.map((a) => a.id) } satisfies EngineError;
  }
  const action = found;

  // ---- 1. 合法性 ----
  const info = legalActions(bp, state).find((x) => x.action.id === actionId)!;
  if (!info.legal) {
    throw { code: 'ILLEGAL_ACTION', message: `行动「${action.name}」当前不可执行`, details: info.reasons } satisfies EngineError;
  }

  // ---- 1b. 最终权重计算与死行动检查：必须在任何 mutate 之前（M1）----
  const { weights, leverageApplied } = finalOutcomeWeights(bp, state, action);
  if (weights.every((w) => w <= 0)) {
    throw { code: 'DEAD_ACTION', message: `行动「${action.name}」所有结果权重为 0，无法结算` } satisfies EngineError;
  }

  const consequences: Consequence[] = [];
  // 引擎结算文案按存档语言生成（V1.1/C1：表现层元数据，不影响结算数值）。
  const t = getEngineStrings(languageOf(state));
  // 回合归因：后果在产生时记录当前回合（minor）。
  const add = (c: Omit<Consequence, 'atTurn'>) => consequences.push({ ...c, atTurn: state.turn });
  const unlocked: string[] = [];
  const trackUnlock = (regionId: string) => {
    if (!state.unlockedRegions.includes(regionId)) {
      state.unlockedRegions.push(regionId);
      unlocked.push(regionId);
      const region = bp.regions.find((r) => r.id === regionId);
      add({
        kind: 'outcome',
        text: t.regionUnlocked(region ? region.name : regionId),
        visible: true,
        source: `action:${actionId}`,
      });
    }
  };

  // ---- 2. 扣时间 + 资产成本 ----
  const timeCost = action.costs?.time ?? 1;
  for (const [assetId, cost] of Object.entries(action.costs?.assets ?? {})) {
    const have = state.assets[assetId] ?? 0;
    if (have < cost) {
      const name = bp.assetTypes.find((a) => a.id === assetId)?.name ?? assetId;
      throw {
        code: 'ILLEGAL_ACTION',
        message: `行动「${action.name}」成本不足`,
        details: [`${name}不足（现有 ${have}，需要 ${cost}）`],
      } satisfies EngineError;
    }
  }
  for (const [assetId, cost] of Object.entries(action.costs?.assets ?? {})) {
    state.assets[assetId] = (state.assets[assetId] ?? 0) - cost;
    const name = bp.assetTypes.find((a) => a.id === assetId)?.name ?? assetId;
    add({ kind: 'cost', text: t.paidAsset(name, cost), visible: true, source: `action:${actionId}` });
  }
  add({ kind: 'cost', text: t.paidTime(timeCost), visible: true, source: `action:${actionId}` });

  // ---- 3. 种子抽签（权重已含 4. 杠杆 modifiers）----
  const counter = (state.counters[actionId] ?? 0) + 1;
  state.counters[actionId] = counter;

  const random = deriveRandom({
    seed: state.seed,
    turn: state.turn,
    actionId,
    seedTag: action.risk?.seedTag ?? 'base',
    counter,
  });
  const pickedIndex = pickWeighted(random, weights);
  const outcome: Outcome = action.outcomes[pickedIndex]!;

  if (leverageApplied) {
    state.leverageUses += 1;
    add({
      kind: 'leverage',
      text: t.leverageApplied(bp.leverage.name),
      visible: true,
      source: `leverage:${bp.leverage.id}`,
    });
  }

  // ---- 5. 结果落地（含知识更新）+ 6. 不可逆标记 ----
  add({
    kind: 'outcome',
    text: t.outcome(action.name, outcome.description),
    visible: true,
    source: `action:${actionId}`,
  });
  if (outcome.effects) {
    applyEffects(bp, state, outcome.effects, `action:${actionId}`, consequences, true);
    for (const c of consequences) if (c.atTurn === undefined) c.atTurn = state.turn;
  }
  for (const regionId of outcome.unlocks ?? []) trackUnlock(regionId);
  if (outcome.irreversible) {
    add({
      kind: 'outcome',
      text: t.irreversible,
      visible: true,
      source: `action:${actionId}`,
    });
  }

  // ---- 7. world tick：时间给世界行动权（宪章 §1.2；维护在每回合 tick 内结算，M3）----
  for (let i = 0; i < timeCost; i++) {
    const tick = worldTick(bp, state);
    consequences.push(...tick.consequences);
  }

  // ---- 8. 阶层门槛 / 胜负 ----
  const tierUp = checkTierGates(bp, state, consequences);
  checkEnd(bp, state, consequences);
  for (const c of consequences) if (c.atTurn === undefined) c.atTurn = state.turn;

  // ---- 9. Lazy Expansion 检查（宪章 §7） ----
  for (const candidate of checkExpansion(bp, state)) {
    add({
      kind: 'system',
      text: t.expansionTriggered(candidate.ruleId, candidate.description),
      visible: true,
      source: `expansion:${candidate.ruleId}`,
    });
  }

  return {
    actionId,
    outcomeId: outcome.id,
    consequences,
    unlocked,
    tierUp,
    irreversible: outcome.irreversible === true,
    ended: state.ended !== undefined,
    turn: state.turn,
  };
}

/** 判定某次抽签是否受到杠杆 modifier 影响（最优路径检验辅助）。 */
export function outcomeWeightsWithLeverage(bp: Blueprint, state: GameState, actionId: string): number[] {
  const action = bp.actions.find((a) => a.id === actionId);
  if (!action) return [];
  return finalOutcomeWeights(bp, state, action).weights;
}

/** 期望收益比较辅助：给定资产 id，计算某行动单次结算的期望 delta（用于宪章 §3 检验）。 */
export function expectedAssetDelta(bp: Blueprint, state: GameState, actionId: string, assetId: string): number {
  const action = bp.actions.find((a) => a.id === actionId);
  if (!action) return 0;
  const weights = outcomeWeightsWithLeverage(bp, state, actionId);
  const total = weights.reduce((s, w) => s + w, 0);
  if (total <= 0) return 0;
  let expected = 0;
  action.outcomes.forEach((o, i) => {
    const delta = (o.effects ?? []).reduce((s, e) => s + ('asset' in e && e.asset === assetId ? e.delta : 0), 0);
    expected += ((weights[i] ?? 0) / total) * delta;
  });
  expected -= action.costs?.assets?.[assetId] ?? 0;
  return expected;
}

/** requires 是否全部满足（供测试/Agent 快速判断）。 */
export function requirementsMet(bp: Blueprint, state: GameState, actionId: string): boolean {
  const action = bp.actions.find((a) => a.id === actionId);
  if (!action) return false;
  return evalAll(action.requires, contextFromState(state));
}
