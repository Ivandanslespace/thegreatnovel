// T3.5 回归测试（node:test，零依赖）：三处引擎 bug 各一条。
// 1. novel.ts submitChapter 哨兵值：archived 为空时合法 factsSeq 0 不得误判 duplicate；
// 2. resolve.ts：RNG 判定失败的行动不得发放正收益（宪法 §1.1 失败可学习）；
// 3. interact.ts trade：回货排除维护资源（防空转退化）且双方账目守恒（宪法红线）。
// 临时目录一律 temps/，after 清理（项目硬约束）。
import { test, after } from 'node:test';
import { deepStrictEqual, equal, ok } from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join } from 'node:path';
import type { ActionDef, WorldState } from '../src/engine/types.ts';
import type { WorldProposal } from '../src/engine/validate.ts';
import { chance } from '../src/engine/rng.ts';
import { resolveAction } from '../src/engine/resolve.ts';
import { interact } from '../src/engine/interact.ts';
import { createNovel, submitChapter } from '../src/engine/novel.ts';
import { saveWorld } from '../src/engine/store.ts';

const TEST_ROOT = join('temps', 'regression-worlds');
after(() => {
  try {
    rmSync(TEST_ROOT, { recursive: true, force: true });
  } catch {}
});

function makeState(slug: string): WorldState {
  return {
    worldSlug: slug,
    schemaVersion: 1,
    language: 'zh',
    seed: 42,
    rngCounter: 0,
    turn: 1,
    phase: 'playing',
    tier: 0,
    player: {
      resources: { supplies: 6, scrap: 5, water: 2 },
      focus: 3,
      focusMax: 3,
      knowledge: [],
      assets: [],
      absolutePower: 1,
      effectiveCapacity: 1,
      relativeStanding: 0.5,
      position: 'camp',
      capacityPenalty: 0,
    },
    npcs: [
      { id: 'n1', name: '老周', goal: 'supplies', resources: { supplies: 5, scrap: 2 }, power: 2, attitude: 0, alive: true, knowledgeIds: [], pendingEvents: [], lastActed: 0 },
    ],
    rulesKnown: [],
    unlocks: [],
    zones: { materialized: [], anchors: [] },
    windows: [],
    lastFactsSeq: 0,
    pendingPlayerEvents: [],
    lastTurnReport: null,
  };
}

/** (r1) bug 1 回归：archived 为空时 factsSeq 0 合法可提交；重复提交仍被拒。 */
test('(r1) submitChapter: factsSeq 0 accepted when nothing archived; resubmit refused', () => {
  const slug = 'regr-chapter';
  const state = makeState(slug); // lastFactsSeq = 0（accept 后的初始事实）
  saveWorld(state, TEST_ROOT);
  const proposal = { worldName: '回归海岸', language: 'zh', leverage: { name: '潮汐预感' } } as unknown as WorldProposal;
  createNovel(slug, state, proposal, TEST_ROOT);

  // 修复前：哨兵 0 使 factsSeq <= 0 一律 duplicate，合法的第 0 号事实无法绑定
  const r1 = submitChapter(slug, 0, '## 第一章\n\n潮水退去。', TEST_ROOT);
  equal(r1.ok, true, `factsSeq 0 应可提交：${JSON.stringify(r1)}`);

  // 防重复仍然成立
  const r2 = submitChapter(slug, 0, '## 重复章', TEST_ROOT);
  equal(r2.ok, false);
  if (!r2.ok) ok(r2.error.hints.some((h) => h.startsWith('chapter:duplicate:')), '重复应报 chapter:duplicate');

  // factsSeq ≠ 最新未归档事实 → notLatest（顺序校验不受影响）
  const r3 = submitChapter(slug, 7, '## 跳章', TEST_ROOT);
  equal(r3.ok, false);
  if (!r3.ok) ok(r3.error.hints.some((h) => h.startsWith('chapter:notLatest:')), '非最新事实应报 chapter:notLatest');
});

/** (r2) bug 2 回归：失败行动不发正收益；失败代价（负数量）仍发放；成功路径不受影响。 */
test('(r2) resolveAction: failed action grants no positive resource yield', () => {
  const table: ActionDef[] = [
    {
      id: 'dive',
      label: '深潜打捞',
      timeCost: 1,
      requires: {},
      costs: {},
      risk: { level: 'low', base: 0, spread: 0 }, // base=0 → 成功时 scaleFactor=1，隔离收益分布变量
      effects: [
        { verb: 'resource', resource: 'scrap', amount: 3 }, // 正收益：仅成功发放
        { verb: 'resource', resource: 'water', amount: -1 }, // 失败代价：仅失败发放
      ],
    },
  ];

  // 确定性找一个首抽失败的种子（chance(rng, 0.85) = false）
  let failSeed = -1;
  for (let seed = 1; seed < 10000; seed++) {
    if (!chance({ seed, counter: 0 }, 0.85).value) {
      failSeed = seed;
      break;
    }
  }
  ok(failSeed > 0, '应能找到确定性失败种子');

  const sFail = makeState('regr-fail');
  sFail.seed = failSeed;
  const rFail = resolveAction(sFail, 'dive', { table });
  ok(rFail.ok);
  if (rFail.ok) {
    equal(rFail.outcome.success, false, '该种子下 dive 应确定性失败');
    equal(rFail.outcome.yield, 0, '失败 yield 为 0');
    // 正收益不得发放
    equal(rFail.newState.player.resources.scrap, 5, '失败不得发放正收益 scrap');
    // 失败代价照常发放（可扣成本，失败可学习）
    equal(rFail.newState.player.resources.water, 1, '失败代价 water-1 应发放');
    const p = rFail.events[0].payload as { resourceDeltas: Record<string, number> };
    equal(p.resourceDeltas.scrap, undefined, '事件账目中不得出现正收益');
  }

  // 对照组：确定性成功种子 → 正收益照发，负数量不发
  let okSeed = -1;
  for (let seed = 1; seed < 10000; seed++) {
    if (chance({ seed, counter: 0 }, 0.85).value) {
      okSeed = seed;
      break;
    }
  }
  const sOk = makeState('regr-ok');
  sOk.seed = okSeed;
  const rOk = resolveAction(sOk, 'dive', { table });
  ok(rOk.ok);
  if (rOk.ok) {
    equal(rOk.outcome.success, true);
    equal(rOk.newState.player.resources.scrap, 5 + 3, '成功发放正收益');
    equal(rOk.newState.player.resources.water, 2, '成功不应用失败代价');
  }
});

/** (r3) bug 3 回归：trade 回货排除 supplies（不退化为空转）且双方账目守恒。 */
test('(r3) trade: excludes maintenance resource and conserves totals on both ledgers', () => {
  // 守恒与回货选择：NPC 持有 supplies:5（最多）与 scrap:2，态度 0
  const s = makeState('regr-trade');
  const before = { supplies: 6 + 5, scrap: 5 + 2 };
  const r = interact(s, 'n1', 'trade');
  ok(r.ok);
  if (r.ok) {
    equal(r.outcome.accepted, true);
    const p = r.newState.player.resources;
    const n = r.newState.npcs[0].resources;
    // 回货必须是 scrap 而非 supplies（修复前退化为付 1 supplies 换 1 supplies 空转）
    equal(p.scrap, 6, '玩家应收到 scrap（态度 0 → 回货 1）');
    equal(p.supplies, 5, '玩家付出 1 supplies');
    equal(n.scrap, 1, 'NPC 交出 1 scrap');
    // 守恒红线：玩家付的 supplies 必须进 NPC 账目，总量不变
    equal(n.supplies, 6, 'NPC 收到 1 supplies（修复前凭空销毁）');
    equal(p.supplies + n.supplies, before.supplies, 'supplies 总量守恒');
    equal(p.scrap + n.scrap, before.scrap, 'scrap 总量守恒');
    // 确定性：同一状态重算结果一致
    const r2 = interact(s, 'n1', 'trade');
    ok(r2.ok);
    if (r2.ok) deepStrictEqual(r2.newState.player.resources, p, 'trade 必须确定性');
  }

  // 拒绝分支：态度 <0
  const sCold = makeState('regr-trade-cold');
  sCold.npcs[0].attitude = -1;
  const rCold = interact(sCold, 'n1', 'trade');
  ok(rCold.ok);
  if (rCold.ok) {
    equal(rCold.outcome.accepted, false);
    ok(rCold.outcome.notes.includes('refused:attitude'));
    deepStrictEqual(rCold.newState.player.resources, sCold.player.resources, '拒绝不得改动账目');
  }

  // 拒绝分支：资源不足
  const sPoor = makeState('regr-trade-poor');
  sPoor.player.resources.supplies = 0;
  const rPoor = interact(sPoor, 'n1', 'trade');
  ok(rPoor.ok);
  if (rPoor.ok) {
    equal(rPoor.outcome.accepted, false);
    ok(rPoor.outcome.notes.includes('refused:poor'));
  }

  // 拒绝分支：NPC 只持有维护资源 → 无可回货物（不再空转白送态度）
  const sOnly = makeState('regr-trade-only');
  sOnly.npcs[0].resources = { supplies: 4 };
  const rOnly = interact(sOnly, 'n1', 'trade');
  ok(rOnly.ok);
  if (rOnly.ok) {
    equal(rOnly.outcome.accepted, false, 'NPC 只持有 supplies 时应拒绝而非空转');
    ok(rOnly.outcome.notes.includes('refused:noGoods'));
    deepStrictEqual(rOnly.newState.player.resources, sOnly.player.resources, '拒绝不得改动账目');
    deepStrictEqual(rOnly.newState.npcs[0].resources, sOnly.npcs[0].resources, '拒绝不得改动 NPC 账目');
  }
});
