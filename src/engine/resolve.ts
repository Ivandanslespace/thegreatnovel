// resolveAction(state, actionId, params) → {ok,newState,events,outcome}:
// 校验合法性→扣成本→种子 RNG 判定（success 概率由 risk.level）→应用 effects（固定动词表）→知识 flag 提高后续转化率；
// 非法行动返回 E_ILLEGAL_ACTION+hints；失败时若有 hiddenTag 则发射 FactRevealed（可理解性，宪法 §1.1）。
import type { ActionDef, ActionOutcome, EngineError, GameEvent, ResolveResult, WorldState } from './types.ts';
import { chance, distribution, pick as rngPick } from './rng.ts';
import { checkRequirements, conversionMultiplier } from './legality.ts';
import { applyAll, nextSeq } from './state.ts';
import { SUCCESS_CHANCE, POWER_PER_ASSET_INVEST, WINDOW_DURATION } from './balance.ts';

/** 解析参数：action table（世界生成层传入）与可选 targetNpcId（预留接口给 CLI）。 */
export interface ResolveParams {
  table: ActionDef[];
  targetNpcId?: string;
}

export function resolveAction(state: WorldState, actionId: string, params: ResolveParams): ResolveResult {
  const action = params.table.find((a) => a.id === actionId);
  if (!action) {
    return { ok: false, error: { code: 'E_UNKNOWN_ACTION', reason: `unknown action ${actionId}`, hints: params.table.map((a) => a.id) } };
  }
  const missing = checkRequirements(state, action);
  if (missing.length > 0) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: `action "${actionId}" conditions not met`, hints: missing } };
  }

  let rng = { seed: state.seed, counter: state.rngCounter };

  // Success roll
  const hit = chance(rng, SUCCESS_CHANCE[action.risk.level]);
  rng = hit.state;
  const success = hit.value;

  // Conversion multiplier for positive resource yields
  const mult = conversionMultiplier(state, action);
  let yieldAmount = 0;
  if (success && action.risk.base > 0) {
    const d = distribution(rng, action.risk.base, action.risk.spread);
    rng = d.state;
    yieldAmount = Math.max(0, Math.round(d.value * mult));
  }

  const scaleFactor = action.risk.base > 0 ? yieldAmount / action.risk.base : 1;

  const resourceDeltas: Record<string, number> = {};
  const notes: string[] = [];
  const knowledgeAdded: string[] = [];
  let assetInvestPayload: { id: string; levels: number } | undefined;
  let powerDelta = 0;
  const relationDeltas: Record<string, number> = {};
  const windowsOpened: Array<{ id: string; kind: 'supply' | 'threat' | 'opportunity'; labelKey: string; openedTurn: number; expiresTurn: number; cause: string }> = [];
  const unlocks: string[] = [];

  // Costs
  for (const [res, amt] of Object.entries(action.costs.resources ?? {})) {
    resourceDeltas[res] = (resourceDeltas[res] ?? 0) - amt;
  }
  const focusDelta = action.costs.focus !== undefined ? -action.costs.focus : undefined;

  // Effects (fixed verb table)
  for (const effect of action.effects) {
    switch (effect.verb) {
      case 'resource': {
        // 正收益仅成功时发放并按 scaleFactor 缩放（保留"部分成功/低收益"语义）；
        // 失败绝不发放正收益（宪法 §1.1：失败可学习，失败路径只发失败后果）。
        if (effect.amount > 0) {
          if (success) {
            resourceDeltas[effect.resource] = (resourceDeltas[effect.resource] ?? 0) + Math.round(effect.amount * scaleFactor);
          }
        } else if (effect.amount < 0 && !success) {
          // 负数量是失败代价，仅失败时应用（扣成本，失败可学习）
          resourceDeltas[effect.resource] = (resourceDeltas[effect.resource] ?? 0) + effect.amount;
        }
        break;
      }

      case 'knowledge': {
        if (success && !knowledgeAdded.includes(effect.knowledge)) knowledgeAdded.push(effect.knowledge);
        break;
      }

      case 'assetInvest': {
        if (success) {
          assetInvestPayload = { id: effect.asset, levels: 1 };
          powerDelta += POWER_PER_ASSET_INVEST;
          notes.push(`Asset investment: ${effect.asset}`);
        }
        break;
      }

      case 'relation': {
        // Relation attempts have effect regardless of success (commitment is still action)
        relationDeltas[effect.npcId] = (relationDeltas[effect.npcId] ?? 0) + effect.delta;
        break;
      }

      case 'windowOpen': {
        if (success) {
          const expires = WINDOW_DURATION[effect.kind];
          windowsOpened.push({
            id: `${state.worldSlug}-${actionId}-${nextSeq(state)}-${windowsOpened.length}`,
            kind: effect.kind,
            labelKey: effect.labelKey,
            openedTurn: state.turn,
            expiresTurn: state.turn + expires,
            cause: actionId,
          });
        }
        break;
      }

      case 'unlock': {
        if (success && !unlocks.includes(effect.unlock)) unlocks.push(effect.unlock);
        break;
      }
    }
  }

  if (focusDelta !== undefined && focusDelta < 0) {
    // ensure resource cap
    if (state.player.focus + focusDelta >= 0) {
      // validated in legality already
    }
  }

  // Events
  const seqStart = nextSeq(state);
  let seq = seqStart;

  const mainPayload: ActionResolvedPayload = {
    actionId,
    success,
    yield: yieldAmount,
    resourceDeltas,
    ...(focusDelta !== undefined ? { focusDelta } : {}),
    ...(knowledgeAdded.length ? { knowledgeAdded } : {}),
    ...(assetInvestPayload ? { assetInvest: assetInvestPayload } : {}),
    ...(powerDelta !== 0 ? { powerDelta, lossCause: undefined } : {}),
    ...Object.keys(relationDeltas).length ? { relationDeltas } : {},
    ...windowsOpened.length ? { windowsOpened } : {},
    ...(unlocks.length ? { unlocks } : {}),
    rngCounter: rng.counter,
  };

  const events: GameEvent[] = [];
  // Main action resolved
  events.push({ seq: seq++, turn: state.turn, type: 'ActionResolved', payload: mainPayload as unknown });

  // Sub-events (knowledge/asset/fact reveal)
  for (const k of knowledgeAdded) {
    events.push({ seq: seq++, turn: state.turn, type: 'KnowledgeGained', payload: { knowledge: k } as unknown });
  }
  if (assetInvestPayload) {
    const currentLevel = maxAssetLevelFor(state, assetInvestPayload.id) + (assetInvestPayload.levels || 0);
    events.push({ seq: seq++, turn: state.turn, type: 'AssetUpgraded', payload: { assetId: assetInvestPayload.id, level: currentLevel } as unknown });
  }
  // Failure reveals hiddenTag (learnable failure, Constitution §1.1)
  if (!success && action.risk.hiddenTag) {
    events.push({ seq: seq++, turn: state.turn, type: 'FactRevealed', payload: { fact: action.risk.hiddenTag!, cause: actionId } as unknown });
  }

  const newState = applyAll(state, events);
  const outcome: ActionOutcome = { actionId, success, yield: yieldAmount, notes };

  return { ok: true, newState, events, outcome };
}

function maxAssetLevelFor(state: WorldState, id: string): number {
  const a = state.player.assets.find((x) => x.id === id);
  return a ? a.level : 0;
}

interface ActionResolvedPayload {
  actionId: string;
  success: boolean;
  yield: number;
  resourceDeltas: Record<string, number>;
  focusDelta?: number;
  knowledgeAdded?: string[];
  assetInvest?: { id: string; levels: number };
  powerDelta?: number;
  lossCause?: string;
  relationDeltas?: Record<string, number>;
  windowsOpened?: Array<{ id: string; kind: 'supply' | 'threat' | 'opportunity'; labelKey: string; openedTurn: number; expiresTurn: number; cause: string }>;
  unlocks?: string[];
  rngCounter: number;
}
