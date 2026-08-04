// verify 重放：load state.json; read all events.jsonl；从 Init 快照开始 apply 全部事件重建状态；
// 整体深度对比重放结果与存档（键序规范化，覆盖 phase/rngCounter/npcs/windows 等全部字段），
// 不一致返回差异清单（宪法 §1.1：关键事实能从状态与事件重放）。
import type { GameEvent, WorldState } from './types.ts';
import { loadWorld, readEvents } from './store.ts';
import { applyAll } from './state.ts';

/** 重放结果。ok=true 表示一致；否则 mismatches 包含每个顶层字段的期望 vs 重放值。 */
export interface ReplayResult {
  ok: boolean;
  mismatches: Array<{ field: string; expected: unknown; replayed: unknown }>;
}

/** 键序规范化的 JSON 序列化（深度对比不受字段插入顺序影响）。 */
function canonical(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map((v) => canonical(v)).join(',')}]`;
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonical(obj[k])}`).join(',')}}`;
}

/** 重放并校验：从 Init event 携带的初始状态，应用所有后续事件，整体深度比较。 */
export function replay(slug: string, root?: string): ReplayResult {
  const stored = loadWorld(slug, root);
  const events = readEvents(slug, root);
  const mismatches: Array<{ field: string; expected: unknown; replayed: unknown }> = [];

  if (events.length === 0 || events[0].type !== 'Init') {
    return {
      ok: false,
      mismatches: [{ field: 'history', expected: 'Init event', replayed: events.length === 0 ? 'empty' : events[0].type }],
    };
  }

  // Start from initial snapshot
  let s: WorldState = (events[0].payload as unknown as { state: WorldState }).state;
  // Apply all subsequent events
  for (const ev of events.slice(1)) {
    s = applyAll(s, [ev]);
  }

  // 整体深度对比（宪法 §1.1）：先规范化全量比对，不一致时按顶层字段定位差异
  if (canonical(stored) !== canonical(s)) {
    const storedRec = stored as unknown as Record<string, unknown>;
    const replayedRec = s as unknown as Record<string, unknown>;
    const fields = new Set<string>([...Object.keys(storedRec), ...Object.keys(replayedRec)]);
    for (const field of [...fields].sort()) {
      const exp = canonical(storedRec[field]);
      const rep = canonical(replayedRec[field]);
      if (exp !== rep) {
        mismatches.push({ field, expected: storedRec[field], replayed: replayedRec[field] });
      }
    }
    if (mismatches.length === 0) {
      // 理论上不可达：全量不同但顶层都相同（防御性兜底）
      mismatches.push({ field: '(state)', expected: stored, replayed: s });
    }
  }

  return { ok: mismatches.length === 0, mismatches };
}
