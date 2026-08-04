// 引擎测试用例（node:test，零依赖）。宪法 §1.1：可理解、可归因、可重放；§3:杠杆物化。
import { test, after } from 'node:test';
import { deepStrictEqual, equal, ok, notEqual } from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join } from 'node:path';
import type { ActionDef, GameEvent, WorldState } from '../src/engine/types.ts';
import { listActions } from '../src/engine/legality.ts';
import { resolveAction } from '../src/engine/resolve.ts';
import { endTurn } from '../src/engine/tick.ts';
import { applyAll, clone } from '../src/engine/state.ts';
import { appendEvent, loadWorld, saveWorld, readEvents } from '../src/engine/store.ts';
import { replay } from '../src/engine/verify.ts';

const TEST_ROOT = join('temps', 'test-worlds');
after(() => {
  try {
    rmSync(TEST_ROOT, { recursive: true, force: true });
  } catch {}
});

/** 构建一个简单初始状态（带 NPC 以计算 standing）。 */
function makeState(): WorldState {
  return {
    worldSlug: 'test-slug',
    schemaVersion: 1,
    language: 'zh',
    seed: 42,
    rngCounter: 0,
    turn: 1,
    phase: 'playing',
    tier: 0,
    player: {
      resources: { supplies: 6, scrap: 5 },
      focus: 3,
      focusMax: 3,
      knowledge: [],
      assets: [],
      absolutePower: 1,
      effectiveCapacity: 1,
      relativeStanding: 0.5, // 1 npc power=2 < player? no → standing computed below
      position: 'camp',
      capacityPenalty: 0,
    },
    npcs: [{ id: 'n1', name: '老周', goal: 'supplies', resources: { supplies: 3 }, power: 2, attitude: 0, alive: true, knowledgeIds: [], pendingEvents: [], lastActed: 0 }],
    rulesKnown: [],
    unlocks: [],
    zones: { materialized: [], anchors: ['anchor-outskirts'] },
    windows: [],
    lastFactsSeq: 0,
    pendingPlayerEvents: [],
    lastTurnReport: null,
  };
}

/** 行动表（用于本任务测试） */
function makeTable(): ActionDef[] {
  return [
    {
      id: 'gather',
      label: 'collect supplies',
      timeCost: 1,
      requires: {},
      costs: {},
      risk: { level: 'low', base: 3, spread: 1 },
      effects: [{ verb: 'resource' as const, resource: 'supplies', amount: 3 }],
    },
    {
      id: 'investigate',
      label: 'investigate bench',
      timeCost: 1,
      requires: { resources: { supplies: 1 } },
      costs: { focus: 1 },
      risk: { level: 'low' as const, base: 0, spread: 0 },
      effects: [{ verb: 'knowledge' as const, knowledge: 'purify' }],
    },
    {
      id: 'invest',
      label: 'invest in workshop',
      timeCost: 2,
      requires: { knowledge: ['purify'], resources: { supplies: 4 } },
      costs: { resources: { supplies: 4 } },
      risk: { level: 'medium' as const, base: 2, spread: 1 },
      effects: [{ verb: 'assetInvest' as const, asset: 'workshop' }],
    },
  ];
}

/** 辅助：深拷贝世界与 actions。 */
function copyState(s: WorldState): WorldState {
  return clone(s);
}

/** (a) 确定性回放：同一种子 + 同一行动序列→最终状态逐字段一致 */
test('(a) deterministic replay: same seed + action sequence → state matches field by field', () => {
  const script = (base: WorldState): WorldState => {
    let s = copyState(base);
    // Turn 1 action: gather
    let r = resolveAction(s, 'gather', { table: makeTable() });
    ok(r.ok, 'gather should succeed deterministically given low risk');
    if (r.ok) s = r.newState;
    s = endTurn(s).newState;

    // Turn 2: investigate (low risk success ~85%)
    r = resolveAction(s, 'investigate', { table: makeTable() });
    ok(r.ok, 'investigate should succeed');
    if (r.ok) s = r.newState;
    // After knowledge gained, invest becomes legal
    // invest attempt even if not yet known — but we know it now
    r = resolveAction(s, 'invest', { table: makeTable() });
    // invest may fail due to medium risk, but that's fine
    ok(r.ok, 'invest call should be accepted');
    if (r.ok) s = r.newState;
    s = endTurn(s).newState;
    return s;
  };

  const a = script(makeState());
  const b = script(makeState());
  // Compare critical fields
  equal(a.turn, b.turn);
  equal(a.tier, b.tier);
  deepStrictEqual(a.player.resources, b.player.resources);
  deepStrictEqual(a.player.assets, b.player.assets);
  deepStrictEqual(a.player.knowledge, b.player.knowledge);
  deepStrictEqual(a.npcs, b.npcs);
});

/** (b) 杠杆对照：focus>0 时合法行动含 revealed，focus=0 时不含（盲选降级） */
test('(b) lever comparison: revealed present when focus>0, absent when focus=0', () => {
  const sFull = makeState();
  sFull.player.focus = 3;
  const sBlind = makeState();
  sBlind.player.focus = 0;
  const actsFull = listActions(sFull, makeTable());
  const actsBlind = listActions(sBlind, makeTable());
  // gather：合法 + base>0 → focus>0 时必有 revealed
  const gatherFull = actsFull.find((a) => a.id === 'gather')!;
  const gatherBlind = actsBlind.find((a) => a.id === 'gather')!;
  ok(gatherFull.legal, 'gather should be legal');
  ok(gatherFull.revealed !== undefined, 'gather revealed present with focus>0');
  equal(gatherBlind.revealed, undefined, 'gather revealed absent with focus=0');
  // investigate：base=0（纯知识行动，无收益分布）→ 任何情况下都不含 revealed
  const invFull = actsFull.find((a) => a.id === 'investigate')!;
  equal(invFull.revealed, undefined, 'zero-base action has no revealed even with focus');
});

/** (c) 非法行动拒绝：E_ILLEGAL_ACTION+hints */
test('(c) illegal action refused: E_ILLEGAL_ACTION + hints', () => {
  const s = makeState(); // has no 'purify'
  const res = resolveAction(s, 'invest', { table: makeTable() });
  equal(res.ok, false);
  if (!res.ok) {
    equal(res.error.code, 'E_ILLEGAL_ACTION');
    ok(res.error.hints.length > 0, 'hints must be non-empty');
    ok(res.error.hints.some((h) => h.startsWith('knowledge:')), 'hint must mention missing knowledge');
  }
});

/** (d) verify 重放：事件序列重建后与存档一致 */
test('(d) verify: replay matches saved world', () => {
  const slug = 'verify-ok';
  let s = makeState();
  s.worldSlug = slug;
  // Init event snapshot
  const initEvent: GameEvent = { seq: 0, turn: s.turn, type: 'Init' as const, payload: { state: clone(s) } as unknown };
  appendEvent(slug, initEvent, TEST_ROOT);
  const table = makeTable();

  // Execute one round
  let r = resolveAction(s, 'gather', { table });
  ok(r.ok);
  if (r.ok) {
    for (const ev of r.events) appendEvent(slug, ev, TEST_ROOT);
    s = r.newState;
  } else throw new Error('gather failed');

  let t = endTurn(s);
  for (const ev of t.events) appendEvent(slug, ev, TEST_ROOT);
  s = t.newState;

  // Save final state
  saveWorld(s, TEST_ROOT);

  // Replay & compare
  const result = replay(slug, TEST_ROOT);
  equal(result.ok, true);
  deepStrictEqual(result.mismatches, []);
});

/** (e) 篡改 state.json → verify 报错 */
test('(e) tampered state.json → verify reports differences', () => {
  const slug = 'verify-tamper';
  let s = makeState();
  s.worldSlug = slug;
  const initEvent: GameEvent = { seq: 0, turn: s.turn, type: 'Init' as const, payload: { state: clone(s) } as unknown };
  appendEvent(slug, initEvent, TEST_ROOT);
  const table = makeTable();
  let r = resolveAction(s, 'gather', { table });
  ok(r.ok);
  if (r.ok) {
    for (const ev of r.events) appendEvent(slug, ev, TEST_ROOT);
    s = r.newState;
  } else throw new Error('gather failed');
  let t = endTurn(s);
  for (const ev of t.events) appendEvent(slug, ev, TEST_ROOT);
  s = t.newState;
  saveWorld(s, TEST_ROOT);

  // Tamper by modifying loaded state and saving back
  const loaded = loadWorld(slug, TEST_ROOT);
  loaded.player.resources['supplies'] += 999;
  saveWorld(loaded, TEST_ROOT);

  const result = replay(slug, TEST_ROOT);
  equal(result.ok, false);
  ok(result.mismatches.some((m) => m.field === 'player'), 'should report mismatch on player (verify 按顶层字段报告)');
});
