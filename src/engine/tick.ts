// endTurn(state) → {newState, events, turnReport}:
// 1) focus 恢复（上限 focusMax）→ 2) 维护成本扣缴（资产等级×单位，不足则 capacityPenalty 0.5）→
// 3) NPC 推进 → 4) 机会窗口开启/关闭（≤3 类：供给波动/威胁/机会，可归因描述，宪法 §7）→
// 5) 时间事件 → 6) report → turn+1。
import type { GameEvent, OpportunityWindow, TurnReport, WorldState } from './types.ts';
import { chance, next as rngNext } from './rng.ts';
import { applyAll, nextSeq } from './state.ts';
import { advanceNpcs } from './npcs.ts';
import { FOCUS_REGEN_PER_TURN, MAINTENANCE_COST_PER_LEVEL, MAINTENANCE_RESOURCE, MAINTENANCE_SHORTFALL_PENALTY, MAX_OPEN_WINDOWS, TIER_WINDOW_TABLE, WINDOW_DURATION, WINDOW_OPEN_CHANCE } from './balance.ts';

/** 回合结束：返回 newState、events 与完整 turnReport。 */
export function endTurn(state: WorldState): { newState: WorldState; events: GameEvent[]; turnReport: TurnReport } {
  let s = state;
  const events: GameEvent[] = [];
  let seq = nextSeq(s);
  let rng = { seed: s.seed, counter: s.rngCounter };
  // push 统一分配 seq（调用方传入的 seq 会被覆盖），避免双递增
  const push = (ev: GameEvent) => { const full: GameEvent = { ...ev, seq: seq++ }; events.push(full); s = applyAll(s, [full]); };

  // 1) Close expired windows (Constitution §1.2 time gives world action right)
  // 事件保留在返回的 events 中落盘：删除叙事不能删除因果（宪法 §1.1），
  // 且窗口过期必须对 turnReport 可见（进入 offscreen）。
  const now = s.turn;
  const expired = s.windows.filter((w) => w.expiresTurn <= now);
  for (const w of expired) {
    push({ seq, turn: now, type: 'WindowClosed', payload: { windowId: w.id, cause: 'expired' } as unknown });
  }

  // 2) NPC advance (offscreen)
  const npcRes = advanceNpcs(s);
  for (const ev of npcRes.events) {
    events.push(ev);
    if (ev.payload && typeof ev.payload === 'object' && 'rngCounter' in ev.payload) {
      rng.counter = (ev.payload as Record<string, unknown>).rngCounter as number;
    }
    // 每条 NPC 事件（含无 rngCounter 的 WindowClosed）都占用一个 seq，避免后续事件 seq 重复
    seq++;
  }
  s = npcRes.newState;

  // 3) Open new windows? weighted pick per tier
  if (s.windows.length < MAX_OPEN_WINDOWS) {
    const roll = chance(rng, WINDOW_OPEN_CHANCE);
    rng = roll.state;
    if (roll.value) {
      const table = TIER_WINDOW_TABLE[s.tier] ?? TIER_WINDOW_TABLE[0];
      const totalWeight = table.reduce((acc, e) => acc + e.weight, 0);
      let cum = 0;
      let chosen = table[0];
      const r = rngNext(rng).value * totalWeight;
      for (const e of table) {
        cum += e.weight;
        if (r < cum) {
          chosen = e;
          break;
        }
      }
      const duration = WINDOW_DURATION[chosen.kind];
      const win: OpportunityWindow = {
        id: `win-${now}-${seq}`,
        kind: chosen.kind,
        labelKey: chosen.labelKey,
        openedTurn: now,
        expiresTurn: now + duration,
        cause: 'world',
      };
      // We'll apply via payload that includes rngCounter update
      const ev: GameEvent = {
        seq: seq++,
        turn: now,
        type: 'WindowOpened',
        payload: { window: win, rngCounter: rng.counter } as unknown,
      };
      events.push(ev);
      s = applyAll(s, [ev]);
    }
  }

  // 4) Maintenance and focus recovery
  const totalLevels = s.player.assets.reduce((acc, a) => acc + a.level, 0);
  const cost = totalLevels * MAINTENANCE_COST_PER_LEVEL;
  const available = s.player.resources[MAINTENANCE_RESOURCE] ?? 0;
  const paid = Math.min(cost, available);
  const shortfall = cost - paid;
  const penalty = shortfall > 0 ? MAINTENANCE_SHORTFALL_PENALTY : 0;

  // Build report (playerEvents drained from pendingPlayerEvents)
  // offscreen 含 NPC 事件与窗口开闭（窗口过期的因果对叙事可见，宪法 §1.1）
  const report: TurnReport = {
    turn: now + 1,
    playerEvents: [...s.pendingPlayerEvents],
    offscreen: events.filter((e) => e.type === 'NpcActed' || e.type === 'WindowClosed' || e.type === 'WindowOpened'),
    windows: s.windows,
    windowsClosed: expired.map((w) => ({ windowId: w.id, labelKey: w.labelKey, cause: 'expired' })),
    maintenancePaid: paid,
  };

  // Apply resource drain
  const resourceDeltas: Record<string, number> = {};
  if (paid > 0) resourceDeltas[MAINTENANCE_RESOURCE] = -paid;
  const taPayload: TimeAdvancedPayload = {
    turn: now + 1,
    focusRegen: FOCUS_REGEN_PER_TURN,
    maintenancePaid: paid,
    maintenanceShortfall: shortfall,
    capacityPenalty: penalty,
    resourceDeltas,
    rngCounter: rng.counter,
    turnReport: report,
  };
  const taEv: GameEvent = {
    seq: seq++,
    turn: now,
    type: 'TimeAdvanced',
    payload: taPayload as unknown,
  };
  events.push(taEv);
  s = applyAll(s, [taEv]);

  return { newState: s, events, turnReport: report };
}

interface TimeAdvancedPayload {
  turn: number;
  focusRegen: number;
  maintenancePaid: number;
  maintenanceShortfall: number;
  capacityPenalty: number;
  resourceDeltas: Record<string, number>;
  rngCounter: number;
  turnReport: TurnReport;
}
