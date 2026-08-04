// interact：玩家与 NPC 的 cooperate/trade/ask/commit 确定性结算。
// 宪法 §9：关系是双方状态与博弈，不是好感度条——态度为负时对方会拒绝；
// 承诺产生 deadline 与责任；§7：信息是资源，打听消耗 focus 且概率受态度影响。
// 全部随机走 rng.ts，事件 payload 携带 rngCounter 保证重放。
import type { EngineError, GameEvent, WorldState } from './types.ts';
import { chance } from './rng.ts';
import { applyAll, nextSeq } from './state.ts';
import {
  ASK_ATTITUDE_STEP,
  ASK_BASE_CHANCE,
  ASK_MAX_CHANCE,
  COMMIT_DEADLINE_TURNS,
  COOPERATE_ATTITUDE_BONUS,
  COOPERATE_YIELD_BASE,
  INTERACT_ATTITUDE_ACCEPT_MIN,
  INVESTIGATE_COST_FOCUS,
  MAINTENANCE_RESOURCE,
  TRADE_GIVE_AMOUNT,
  TRADE_RECEIVE_BASE,
} from './balance.ts';

export type InteractKind = 'cooperate' | 'trade' | 'ask' | 'commit';

export const INTERACT_KINDS: readonly InteractKind[] = ['cooperate', 'trade', 'ask', 'commit'];

export interface InteractOutcome {
  kind: InteractKind;
  npcId: string;
  accepted: boolean;
  /** 机器可读备注码：refused:attitude / refused:noGoods / refused:poor / withheld / no-secret / deadline */
  notes: string[];
  /** commit 成功时的责任期限回合（宪法 §9）。 */
  deadlineTurn?: number;
}

export type InteractResult =
  | { ok: true; newState: WorldState; events: GameEvent[]; outcome: InteractOutcome }
  | { ok: false; error: EngineError };

/**
 * 结算一次交互。产出 ActionResolved（玩家侧）+ 可选 NpcActed（NPC 侧资源）+ 可选 FactRevealed（打听揭示隐藏规则）。
 * hiddenRules 来自 blueprint.proposal.rulesHidden（ask 用）。
 */
export function interact(state: WorldState, npcId: string, kind: InteractKind, opts?: { hiddenRules?: string[] }): InteractResult {
  if (state.phase !== 'playing') {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: 'world is not in playing phase', hints: [] } };
  }
  const npc = state.npcs.find((n) => n.id === npcId);
  if (!npc || !npc.alive) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: `NPC ${npcId} missing or dead`, hints: [`npc:${npcId}`] } };
  }
  if (kind === 'ask' && state.player.focus < INVESTIGATE_COST_FOCUS) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: 'ask costs focus', hints: ['focus'] } };
  }

  let rng = { seed: state.seed, counter: state.rngCounter };
  let seq = nextSeq(state);
  const events: GameEvent[] = [];

  let accepted = false;
  const notes: string[] = [];
  const playerDeltas: Record<string, number> = {};
  const npcDeltas: Record<string, number> = {};
  const relationDeltas: Record<string, number> = {};
  let focusDelta: number | undefined;
  let revealedFact: string | undefined;
  let deadlineTurn: number | undefined;

  switch (kind) {
    case 'cooperate': {
      // 态度为负直接拒绝：关系是双方博弈（宪法 §9）
      if (npc.attitude >= INTERACT_ATTITUDE_ACCEPT_MIN) {
        accepted = true;
        const amount = COOPERATE_YIELD_BASE + (npc.attitude >= 2 ? COOPERATE_ATTITUDE_BONUS : 0);
        playerDeltas[npc.goal] = amount;
        npcDeltas[npc.goal] = 1;
        relationDeltas[npcId] = 1;
      } else {
        notes.push('refused:attitude');
      }
      break;
    }
    case 'trade': {
      // 玩家以维护资源换取 NPC 持有最多的资源；数量受态度与 NPC 持有上限约束（宪法 §6）。
      // 回货排除维护资源：否则 NPC 持有最多的恰是 supplies 时退化为"付 1 supplies 换 1 supplies"空转。
      const holdings = Object.entries(npc.resources)
        .filter(([k, v]) => v >= 1 && k !== MAINTENANCE_RESOURCE)
        .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
      const canPay = (state.player.resources[MAINTENANCE_RESOURCE] ?? 0) >= TRADE_GIVE_AMOUNT;
      if (npc.attitude < INTERACT_ATTITUDE_ACCEPT_MIN) {
        notes.push('refused:attitude');
      } else if (!canPay) {
        notes.push('refused:poor');
      } else if (holdings.length === 0) {
        notes.push('refused:noGoods');
      } else {
        accepted = true;
        const [giveRes] = holdings[0];
        const want = TRADE_RECEIVE_BASE + (npc.attitude >= 1 ? 1 : 0);
        const recv = Math.min(want, holdings[0][1]);
        playerDeltas[MAINTENANCE_RESOURCE] = -TRADE_GIVE_AMOUNT;
        playerDeltas[giveRes] = (playerDeltas[giveRes] ?? 0) + recv;
        npcDeltas[giveRes] = -recv;
        // 守恒（宪法红线）：玩家付出的维护资源必须进入 NPC 账目，不得凭空销毁
        npcDeltas[MAINTENANCE_RESOURCE] = (npcDeltas[MAINTENANCE_RESOURCE] ?? 0) + TRADE_GIVE_AMOUNT;
        relationDeltas[npcId] = 1;
      }
      break;
    }
    case 'ask': {
      // 信息是资源（宪法 §7）：付 focus，按态度概率获得一条尚未知晓的隐藏规则
      focusDelta = -INVESTIGATE_COST_FOCUS;
      const p = Math.min(ASK_MAX_CHANCE, ASK_BASE_CHANCE + ASK_ATTITUDE_STEP * (npc.attitude + 3));
      const hit = chance(rng, p);
      rng = hit.state;
      accepted = hit.value;
      if (accepted) {
        const hidden = (opts?.hiddenRules ?? []).find((r) => !state.rulesKnown.includes(r));
        if (hidden) {
          revealedFact = hidden;
        } else {
          notes.push('no-secret');
        }
      } else {
        notes.push('withheld');
      }
      break;
    }
    case 'commit': {
      // 承诺即行动后果：对方态度 +1（信任），同时产生 deadline 责任记录（宪法 §9）
      accepted = true;
      relationDeltas[npcId] = 1;
      deadlineTurn = state.turn + COMMIT_DEADLINE_TURNS;
      notes.push('deadline');
      break;
    }
  }

  // 玩家侧：ActionResolved（进入 pendingPlayerEvents，回合报告可见）
  const yieldSum = Object.values(playerDeltas).filter((v) => v > 0).reduce((acc, v) => acc + v, 0);
  events.push({
    seq: seq++,
    turn: state.turn,
    type: 'ActionResolved',
    payload: {
      actionId: `interact:${kind}`,
      success: accepted,
      yield: yieldSum,
      resourceDeltas: playerDeltas,
      ...(focusDelta !== undefined ? { focusDelta } : {}),
      ...(Object.keys(relationDeltas).length ? { relationDeltas } : {}),
      rngCounter: rng.counter,
    } as unknown,
  });

  // NPC 侧资源变动（有因可溯）
  if (Object.keys(npcDeltas).length > 0) {
    events.push({
      seq: seq++,
      turn: state.turn,
      type: 'NpcActed',
      payload: { npcId, cause: `interact:${kind}`, resourceDeltas: npcDeltas, rngCounter: rng.counter } as unknown,
    });
  }

  // 打听成功：隐藏规则成为世界事实（宪法 §1.1 可归因）
  if (revealedFact !== undefined) {
    events.push({
      seq: seq++,
      turn: state.turn,
      type: 'FactRevealed',
      payload: { fact: revealedFact, cause: `ask:${npcId}` } as unknown,
    });
  }

  const newState = applyAll(state, events);
  const outcome: InteractOutcome = { kind, npcId, accepted, notes, ...(deadlineTurn !== undefined ? { deadlineTurn } : {}) };
  return { ok: true, newState, events, outcome };
}
