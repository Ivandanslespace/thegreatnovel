// 纯函数 reducer apply(state, event) → newState：不修改旧对象；三层能力语义：
// - absolutePower 只增不减，除非 payload.lossCause 明确的世界内因果损失（宪法 §5）
// - effectiveCapacity = round(absolutePower × (1 - capacityPenalty))，受资源/维护限制
// - relativeStanding 随 cohort 重算（player.power + npc.power 的百分位），可回撤（宪法 §5）
// 时间给世界行动权（宪法 §1.2）：windows/npcs 在玩家不在场时推进。

import type { GameEvent, OpportunityWindow, TurnReport, WorldState, Zone } from './types.ts';

/** JSON 深拷贝（引擎数据可安全序列化，宪法 §1）。 */
export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

export function nextSeq(state: WorldState): number {
  return state.lastFactsSeq + 1;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** 相对位置计算：存活 NPC 中 power ≤ player.absolutePower 的比例（含自身计 1）。 */
export function recomputeStanding(s: WorldState): number {
  const alive = s.npcs.filter((n) => n.alive);
  const size = alive.length + 1; // player + alive npcs
  const below = alive.filter((n) => n.power <= s.player.absolutePower).length;
  return clamp(Math.round(((below + 1) / size) * 100) / 100, 0, 1);
}

export function applyAll(start: WorldState, events: readonly GameEvent[]): WorldState {
  return events.reduce((s, e) => apply(s, e), start);
}

function maxCapacity(power: number, penalty: number): number {
  const val = power * (1 - penalty);
  return Math.max(0, Math.round(val));
}

export function apply(state: WorldState, event: GameEvent): WorldState {
  const s = clone(state);
  // lastFactsSeq 单调递增（历史指针）
  s.lastFactsSeq = Math.max(s.lastFactsSeq, event.seq);

  switch (event.type) {
    case 'Init': {
      const base = clone((event.payload as unknown as { state: WorldState }).state);
      base.lastFactsSeq = event.seq;
      return base;
    }

    case 'ActionResolved': {
      const p = event.payload as unknown;
      if (typeof p !== 'object' || p === null) return s;
      // resource deltas
      const resDeltas = (p as { resourceDeltas?: Record<string, unknown> }).resourceDeltas;
      if (resDeltas && typeof resDeltas === 'object') {
        for (const [k, d] of Object.entries(resDeltas)) {
          if (typeof d === 'number') {
            s.player.resources[k] = Math.max(0, (s.player.resources[k] ?? 0) + d);
          }
        }
      }
      // focusDelta
      const focusDelta = (p as { focusDelta?: number }).focusDelta;
      if (focusDelta !== undefined) {
        s.player.focus = clamp(s.player.focus + focusDelta, 0, s.player.focusMax);
      }
      // knowledgeAdded
      const knowledgeAdded = (p as { knowledgeAdded?: readonly string[] }).knowledgeAdded;
      if (Array.isArray(knowledgeAdded)) {
        for (const k of knowledgeAdded) {
          if (typeof k === 'string' && !s.player.knowledge.includes(k)) s.player.knowledge.push(k);
        }
      }
      // assetInvest
      const aiv = (p as { assetInvest?: { id: string; levels: number } }).assetInvest;
      if (aiv) {
        const found = s.player.assets.find((x) => x.id === aiv.id);
        if (found) {
          found.level += aiv.levels;
        } else {
          s.player.assets.push({ id: aiv.id, level: aiv.levels });
        }
      }
      // powerDelta（严格约束：负 delta 必须有 lossCause，宪法 §5）
      const pdelta = (p as { powerDelta?: number }).powerDelta;
      const lcause = (p as { lossCause?: string }).lossCause;
      if (pdelta !== undefined) {
        if (pdelta < 0 && !lcause) {
          // 拒绝无因负增长
        } else {
          s.player.absolutePower = Math.max(0, s.player.absolutePower + pdelta);
        }
      }
      // relationDeltas
      const relDeltas = (p as { relationDeltas?: Record<string, unknown> }).relationDeltas;
      if (relDeltas && typeof relDeltas === 'object') {
        for (const [npcId, deltaVal] of Object.entries(relDeltas)) {
          const npc = s.npcs.find((n) => n.id === npcId);
          if (npc && typeof deltaVal === 'number') {
            npc.attitude = clamp(npc.attitude + deltaVal, -3, 3);
          }
        }
      }
      // windowsOpened
      const wins = (p as { windowsOpened?: OpportunityWindow[] }).windowsOpened;
      if (Array.isArray(wins)) {
        for (const w of wins) {
          if (!s.windows.some((w2) => w2.id === w.id)) s.windows.push(w);
        }
      }
      // unlocks：解锁标记进入 state.unlocks（行动可经 requires.unlocks 引用），不混入 rulesKnown
      const unlockList = (p as { unlocks?: readonly string[] }).unlocks;
      if (Array.isArray(unlockList)) {
        if (!Array.isArray(s.unlocks)) s.unlocks = [];
        for (const u of unlockList) {
          if (typeof u === 'string' && !s.unlocks.includes(u)) s.unlocks.push(u);
        }
      }
      // rngCounter
      const cnt = (p as { rngCounter?: number }).rngCounter;
      if (typeof cnt === 'number') s.rngCounter = cnt;
      // pendingPlayerEvents（endTurn 时吸入 TurnReport）
      s.pendingPlayerEvents.push(event);
      // recompute standing & effectiveCapacity
      s.player.relativeStanding = recomputeStanding(s);
      s.player.effectiveCapacity = maxCapacity(s.player.absolutePower, s.player.capacityPenalty);
      break;
    }

    case 'TimeAdvanced': {
      const p = event.payload as unknown;
      if (typeof p !== 'object' || p === null) break;
      // turn
      s.turn = (p as { turn: number }).turn;
      // resource deltas
      const tDeltas = (p as { resourceDeltas?: Record<string, unknown> }).resourceDeltas;
      if (tDeltas && typeof tDeltas === 'object') {
        for (const [k, d] of Object.entries(tDeltas)) {
          if (typeof d === 'number') {
            s.player.resources[k] = Math.max(0, (s.player.resources[k] ?? 0) + d);
          }
        }
      }
      // focus regen（上限 focusMax）
      const focusRegen = (p as { focusRegen: number }).focusRegen;
      s.player.focus = clamp(s.player.focus + focusRegen, 0, s.player.focusMax);
      // capacity penalty
      const capPenalty = (p as { capacityPenalty: number }).capacityPenalty;
      s.player.capacityPenalty = capPenalty;
      s.player.effectiveCapacity = maxCapacity(s.player.absolutePower, capPenalty);
      // rngCounter
      const tcnt = (p as { rngCounter: number }).rngCounter;
      s.rngCounter = tcnt;
      // TurnReport snapshot
      const trpt = (p as { turnReport: TurnReport }).turnReport;
      s.lastTurnReport = trpt;
      // 清空待结算事件
      s.pendingPlayerEvents = [];
      break;
    }

    case 'NpcActed': {
      const p = event.payload as unknown;
      if (typeof p !== 'object' || p === null) break;
      const npcId = (p as { npcId: string }).npcId;
      const npc = s.npcs.find((n) => n.id === npcId);
      if (!npc || !npc.alive) break;
      // resource deltas
      const nrDeltas = (p as { resourceDeltas?: Record<string, unknown> }).resourceDeltas;
      if (nrDeltas && typeof nrDeltas === 'object') {
        for (const [k, d] of Object.entries(nrDeltas)) {
          if (typeof d === 'number') {
            npc.resources[k] = (npc.resources[k] ?? 0) + d;
          }
        }
      }
      // powerDelta
      const npdelta = (p as { powerDelta?: number }).powerDelta;
      if (npdelta) npc.power += npdelta;
      // attitudeDelta
      const adelta = (p as { attitudeDelta?: number }).attitudeDelta;
      if (adelta) npc.attitude = clamp(npc.attitude + adelta, -3, 3);
      npc.lastActed = event.turn;
      // offscreen buffer（信息边界，宪法 §7）
      npc.pendingEvents.push(event);
      // rngCounter
      const ncnt = (p as { rngCounter?: number }).rngCounter;
      if (ncnt !== undefined) s.rngCounter = ncnt;
      // standing
      s.player.relativeStanding = recomputeStanding(s);
      break;
    }

    case 'WindowOpened': {
      const p = event.payload as unknown;
      if (typeof p !== 'object' || p === null) break;
      const win = (p as { window?: OpportunityWindow }).window;
      if (win && !s.windows.some((w) => w.id === win.id)) s.windows.push(win);
      break;
    }

    case 'WindowClosed': {
      const p = event.payload as unknown;
      if (typeof p !== 'object' || p === null) break;
      const wid = (p as { windowId: string }).windowId;
      s.windows = s.windows.filter((w) => w.id !== wid);
      break;
    }

    case 'TierUp': {
      const p = event.payload as unknown;
      if (typeof p !== 'object' || p === null) break;
      const ntier = (p as { newTier: number }).newTier;
      s.tier = ntier;
      // scale npcs power（新 cohort 压力，保留成果但相对失控，宪法 §5）
      const cscale = (p as { cohortScale: number }).cohortScale;
      for (const npc of s.npcs) {
        if (npc.alive) npc.power = Math.round(npc.power * cscale);
      }
      // zone materialization（先验证候选再成事实，宪法 §7）
      const zinfo = (p as { zone: Zone }).zone;
      s.zones.materialized.push(zinfo);
      if (zinfo.anchorId) {
        const idx = s.zones.anchors.indexOf(zinfo.anchorId);
        if (idx >= 0) s.zones.anchors.splice(idx, 1);
      }
      // background rule（旧层劳动背景化，宪法 §1.2）
      const brule = (p as { backgroundRule: string }).backgroundRule;
      if (!s.rulesKnown.includes(brule)) s.rulesKnown.push(brule);
      // rngCounter（物化 zone 消耗的随机必须写回，避免后续行动复用）
      const trc = (p as { rngCounter?: number }).rngCounter;
      if (typeof trc === 'number') s.rngCounter = trc;
      // standing
      s.player.relativeStanding = recomputeStanding(s);
      break;
    }

    case 'KnowledgeGained': {
      const p = event.payload as unknown;
      if (typeof p !== 'object' || p === null) break;
      const kname = (p as { knowledge: string }).knowledge;
      if (!s.player.knowledge.includes(kname)) s.player.knowledge.push(kname);
      break;
    }

    case 'AssetUpgraded': {
      const p = event.payload as unknown;
      if (typeof p !== 'object' || p === null) break;
      const aid = (p as { assetId: string }).assetId;
      const lvl = (p as { level: number }).level;
      const a = s.player.assets.find((x) => x.id === aid);
      if (a) a.level = lvl;
      break;
    }

    case 'FactRevealed': {
      const p = event.payload as unknown;
      if (typeof p !== 'object' || p === null) break;
      const fact = (p as { fact: string }).fact;
      if (!s.rulesKnown.includes(fact)) s.rulesKnown.push(fact);
      break;
    }

    case 'WorldFinished': {
      // 完结走统一事件管道：phase→ended 由 reducer 施加（verify 重放可重建，宪法 §1.1）
      s.phase = 'ended';
      break;
    }

    default:
      // 未知类型跳过（避免破坏重放确定性）
      break;
  }

  return s;
}
