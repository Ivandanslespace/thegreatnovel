/** leverage：宪章 §3 检验——移除杠杆后，合法行动集与最优路径必须发生断言式改变。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { withLeverageDisabled } from '../blueprint.ts';
import { contextFromState, evalCondition } from '../conditions.ts';
import { legalActions, expectedAssetDelta, outcomeWeightsWithLeverage } from '../resolve.ts';
import { freshState } from './helpers.ts';
import type { GameState } from '../types.ts';

/** 构造"已借到账簿、已做出预知"的中期状态。 */
function midState(): ReturnType<typeof freshState> {
  const { bp, state } = freshState(44);
  state.flags['ledger-open'] = true;
  state.flags['forecast-ready'] = true;
  state.knownFacts.push('fact-dock-gossip', 'fact-spring-tide');
  state.assets.credential = 6;
  state.assets.insight = 4;
  return { bp, state };
}

function bestAction(bp: ReturnType<typeof freshState>['bp'], state: GameState, candidates: string[]): string {
  let best = candidates[0]!;
  let bestValue = Number.NEGATIVE_INFINITY;
  for (const id of candidates) {
    const value = expectedAssetDelta(bp, state, id, 'credential');
    if (value > bestValue) {
      bestValue = value;
      best = id;
    }
  }
  return best;
}

test('合法行动集：杠杆关闭后独占行动被移出（宪章 §3）', () => {
  const { bp, state } = midState();
  const withLeverage = legalActions(bp, state).filter((x) => x.legal).map((x) => x.action.id);
  assert.ok(withLeverage.includes('echo-forecast'), '杠杆开启：预知货价窗口合法');
  assert.ok(withLeverage.includes('anchor-risk'), '杠杆开启：锚定风险合法');

  const offBp = withLeverageDisabled(bp);
  const without = legalActions(offBp, state);
  const offLegal = without.filter((x) => x.legal).map((x) => x.action.id);
  assert.ok(!offLegal.includes('echo-forecast'), '杠杆关闭：预知货价窗口不再合法');
  assert.ok(!offLegal.includes('anchor-risk'), '杠杆关闭：锚定风险不再合法');
  const reason = without.find((x) => x.action.id === 'echo-forecast')!.reasons.join(' ');
  assert.match(reason, /杠杆/, '拒绝原因必须说明是杠杆不可用');
  assert.notDeepEqual(withLeverage, offLegal, '合法行动集发生断言式改变');
});

test('抽签权重：杠杆 modifier 只在开关开启时改写分布', () => {
  const { bp, state } = midState();
  // 期望权重从 Blueprint 数据推导（M13）：基础分布 = trade-run 各 outcome 权重；
  // 开启杠杆后，套用所有 action=trade-run 且 when 条件满足的 modifier。
  const trade = bp.actions.find((a) => a.id === 'trade-run')!;
  const base = trade.outcomes.map((o) => o.weight);
  const expected = trade.outcomes.map((o) => o.weight);
  for (const mod of bp.leverage.modifiers) {
    if (mod.action !== 'trade-run') continue;
    if (mod.when !== undefined && !evalCondition(mod.when, contextFromState(state))) continue;
    const idx = trade.outcomes.findIndex((o) => o.id === mod.outcome);
    if (idx >= 0) expected[idx] = mod.setWeight;
  }
  assert.notDeepEqual(expected, base, '数据前提：当前状态下确有 modifier 改写 trade-run 分布');
  assert.deepEqual(outcomeWeightsWithLeverage(bp, state, 'trade-run'), expected, '预知后分布由 modifier 推导');
  const off = withLeverageDisabled(bp);
  assert.deepEqual(outcomeWeightsWithLeverage(off, state, 'trade-run'), base, '关闭杠杆后回到原始分布');
});

test('最优路径：移除杠杆后最优行动必须改变（宪章 §3 检验）', () => {
  const { bp, state } = midState();
  const candidates = ['trade-run', 'casual-labor', 'gather-rumors'];

  const bestWith = bestAction(bp, state, candidates);
  const bestWithout = bestAction(withLeverageDisabled(bp), state, candidates);

  assert.equal(bestWith, 'trade-run', '有杠杆+预知：最优是带着信息优势做贸易');
  assert.equal(bestWithout, 'casual-labor', '无杠杆：贸易期望为负，最优退回打零工');
  assert.notEqual(bestWith, bestWithout, '最优路径发生断言式改变');

  const tradeWith = expectedAssetDelta(bp, state, 'trade-run', 'credential');
  const tradeWithout = expectedAssetDelta(withLeverageDisabled(bp), state, 'trade-run', 'credential');
  assert.ok(tradeWith > tradeWithout, '杠杆提高同一行动的期望转化');
  assert.ok(tradeWith > 0 && tradeWithout < 0, '杠杆把负期望行动变为正期望（风险-收益关系改变）');
});

test('杠杆不是免费午餐：独占行动消耗洞察成本', () => {
  const { bp } = midState();
  const forecast = bp.actions.find((a) => a.id === 'echo-forecast')!;
  const anchor = bp.actions.find((a) => a.id === 'anchor-risk')!;
  assert.ok((forecast.costs?.assets?.insight ?? 0) > 0, '预知必须付出洞察');
  assert.ok((anchor.costs?.assets?.insight ?? 0) > 0, '锚定必须付出洞察');
  assert.ok(bp.leverage.causalChain.length > 0, '杠杆绑定因果链（law）');
});
