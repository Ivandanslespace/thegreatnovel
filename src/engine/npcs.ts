// NPC 确定性推进规则（宪法 §7）：目标驱动（缺资源者获取，power 高者争夺窗口），
// attitude 有因±1；不在场事件入 offscreen + npc.pendingEvents。
// 玩家杠杆（revealed）永远对 NPC 不可见。
import type { GameEvent, WorldState } from './types.ts';
import { chance } from './rng.ts';
import { applyAll, nextSeq } from './state.ts';
import { NPC_CONTEST_CHANCE, NPC_GATHER_AMOUNT, NPC_GATHER_CHANCE, NPC_RESOURCE_TARGET } from './balance.ts';

/** NPC 回合推进：返回 newState、events 与 offscreen（只含 NpcActed）。 */
export function advanceNpcs(state: WorldState): { newState: WorldState; events: GameEvent[]; offscreen: GameEvent[] } {
  let rng = { seed: state.seed, counter: state.rngCounter };
  const seqStart = nextSeq(state);
  let seq = seqStart;
  const events: GameEvent[] = [];
  let working = state; // incremental updates for window contention visibility

  for (const npc of state.npcs) {
    if (!npc.alive) continue;
    const current = working.npcs.find((n) => n.id === npc.id)!;
    // Goal-driven resource gathering (Constitution §7 autonomy)
    const have = current.resources[npc.goal] ?? 0;
    if (have < NPC_RESOURCE_TARGET) {
      const hit = chance(rng, NPC_GATHER_CHANCE);
      rng = hit.state;
      if (hit.value) {
        const ev: GameEvent = { seq: seq++, turn: working.turn, type: 'NpcActed', payload: { npcId: npc.id, cause: 'gather', resourceDeltas: { [npc.goal]: NPC_GATHER_AMOUNT }, rngCounter: rng.counter } as unknown };
        events.push(ev);
        working = applyAll(working, [ev]);
      }
    }
    // Contest windows if power ≥ player absolutePower
    const opportunity = working.windows.find((w) => w.kind === 'opportunity');
    if (opportunity && current.power >= working.player.absolutePower) {
      const hit = chance(rng, NPC_CONTEST_CHANCE);
      rng = hit.state;
      if (hit.value) {
        const ev: GameEvent = { seq: seq++, turn: working.turn, type: 'NpcActed', payload: { npcId: npc.id, cause: 'contest-window', powerDelta: 1, rngCounter: rng.counter } as unknown };
        events.push(ev);
        // Close this window (player sees it close)
        const closeEv: GameEvent = { seq: seq++, turn: working.turn, type: 'WindowClosed', payload: { windowId: opportunity.id, cause: `npc:${npc.id}` } as unknown };
        events.push(closeEv);
        working = applyAll(working, [ev, closeEv]);
      }
    }
  }

  return { newState: working, events, offscreen: events.filter((e) => e.type === 'NpcActed') };
}

/** NPC attitude drift with cause (Constitution §9: ±1 has traceable reason). */
export function attitudeDrift(state: WorldState, npcId: string, delta: number, cause: string): { newState: WorldState; events: GameEvent[] } | { error: { code: string; reason: string } } {
  const npc = state.npcs.find((n) => n.id === npcId);
  if (!npc || !npc.alive) return { error: { code: 'E_ILLEGAL_ACTION', reason: `NPC ${npcId} not alive` } };
  const seq = nextSeq(state);
  const newAttitude = Math.max(-3, Math.min(3, npc.attitude + delta));
  const ev: GameEvent = { seq, turn: state.turn, type: 'NpcActed', payload: { npcId, cause, attitudeDelta: delta } as unknown };
  return { newState: applyAll(state, [ev]), events: [ev] };
}
