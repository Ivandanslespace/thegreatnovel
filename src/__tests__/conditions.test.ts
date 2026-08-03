/** conditions：通用条件求值（资产/事实/flag/窗口/阶层/and-or）。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { evalAll, evalCondition, explainUnmet } from '../conditions.ts';
import type { EvalContext } from '../conditions.ts';
import { loadEchoBlueprint } from './helpers.ts';

function ctx(): EvalContext {
  return {
    assets: { credential: 8, insight: 3 },
    knownFacts: ['fact-a'],
    flags: { 'tide-ebb': true },
    turn: 4,
    tier: 1,
  };
}

test('asset 条件：gte/lte 双向阈值', () => {
  assert.equal(evalCondition({ asset: 'credential', gte: 8 }, ctx()), true);
  assert.equal(evalCondition({ asset: 'credential', gte: 9 }, ctx()), false);
  assert.equal(evalCondition({ asset: 'credential', lte: 8 }, ctx()), true);
  assert.equal(evalCondition({ asset: 'credential', lte: 7 }, ctx()), false);
  assert.equal(evalCondition({ asset: 'ghost', gte: 1 }, ctx()), false);
});

test('fact 条件：只看玩家已知（知识边界，宪章 §7）', () => {
  assert.equal(evalCondition({ fact: 'fact-a' }, ctx()), true);
  assert.equal(evalCondition({ fact: 'fact-b' }, ctx()), false);
});

test('flag 条件', () => {
  assert.equal(evalCondition({ flag: 'tide-ebb' }, ctx()), true);
  assert.equal(evalCondition({ flag: 'tide-spring' }, ctx()), false);
});

test('window 条件：回合窗口开与关', () => {
  assert.equal(evalCondition({ window: { gte: 3, lte: 4 } }, ctx()), true);
  assert.equal(evalCondition({ window: { gte: 5, lte: 6 } }, ctx()), false);
  assert.equal(evalCondition({ window: { lte: 4 } }, ctx()), true);
  assert.equal(evalCondition({ window: { gte: 5 } }, ctx()), false);
});

test('tier 条件', () => {
  assert.equal(evalCondition({ tier: { gte: 1 } }, ctx()), true);
  assert.equal(evalCondition({ tier: { gte: 2 } }, ctx()), false);
});

test('and/or 组合', () => {
  assert.equal(evalCondition({ and: [{ asset: 'credential', gte: 8 }, { flag: 'tide-ebb' }] }, ctx()), true);
  assert.equal(evalCondition({ and: [{ asset: 'credential', gte: 9 }, { flag: 'tide-ebb' }] }, ctx()), false);
  assert.equal(evalCondition({ or: [{ asset: 'credential', gte: 99 }, { fact: 'fact-a' }] }, ctx()), true);
  assert.equal(evalCondition({ or: [] }, ctx()), false);
});

test('evalAll：空条件数组视为通过', () => {
  assert.equal(evalAll(undefined, ctx()), true);
  assert.equal(evalAll([], ctx()), true);
});

test('explainUnmet：给出人类可读的结构化原因', () => {
  const bp = loadEchoBlueprint();
  const reasons = explainUnmet(
    [{ asset: 'credential', gte: 99 }, { fact: 'fact-spring-tide' }],
    { ...ctx(), knownFacts: [] },
    bp,
  );
  assert.equal(reasons.length, 2);
  assert.match(reasons[0]!, /潮汐凭据不足/);
  assert.match(reasons[1]!, /尚不知道/);
});
