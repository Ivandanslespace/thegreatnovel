/** tick：世界行动权——规律窗口开合、势力计划离屏推进、后果可追溯（宪章 §1.2、§7）。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { worldTick } from '../tick.ts';
import { freshState } from './helpers.ts';
import type { Blueprint, Condition } from '../types.ts';

/** M13：从条件树中递归收集全部回合窗口（期望值由 Blueprint 数据推导，不硬编码）。 */
function windowsOf(cond: Condition | undefined): { gte: number; lte: number }[] {
  if (!cond) return [];
  const out: { gte: number; lte: number }[] = [];
  if ('window' in cond && cond.window && typeof cond.window.gte === 'number' && typeof cond.window.lte === 'number') {
    out.push({ gte: cond.window.gte, lte: cond.window.lte });
  }
  for (const key of ['and', 'or'] as const) {
    const list = (cond as unknown as Record<string, unknown>)[key];
    if (Array.isArray(list)) for (const sub of list as Condition[]) out.push(...windowsOf(sub));
  }
  return out;
}

test('回合推进：turn +1', () => {
  const { bp, state } = freshState(44);
  worldTick(bp, state);
  assert.equal(state.turn, 1);
});

test('规律窗口：退潮窗口按 Blueprint 数据开合，随后切换为大潮', () => {
  const { bp, state } = freshState(44);
  const ebb = bp.laws.find((l) => l.id === 'law-ebb-flow')!;
  const spring = bp.laws.find((l) => l.id === 'law-spring-tide')!;
  const ebbWindows = windowsOf(ebb.trigger).sort((a, b) => a.gte - b.gte);
  const springWindows = windowsOf(spring.trigger).sort((a, b) => a.gte - b.gte);
  const openTurn = ebbWindows[0]!.gte;
  const closeTurn = ebbWindows[0]!.lte + 1;
  const springOpenTurn = springWindows[0]!.gte;
  assert.equal(closeTurn, springOpenTurn, '数据前提：退潮关闭即大潮开启（世界平衡约束）');

  const ebbFlag = ebb.effect!.find((e) => 'setFlag' in e) as { setFlag: string };
  const springFlag = spring.effect!.find((e) => 'setFlag' in e) as { setFlag: string };

  while (state.turn < openTurn) worldTick(bp, state);
  assert.equal(state.flags[ebbFlag.setFlag], true, `回合 ${openTurn} 退潮窗口开启`);
  while (state.turn < closeTurn) worldTick(bp, state);
  assert.notEqual(state.flags[ebbFlag.setFlag], true, `回合 ${closeTurn} 退潮窗口关闭`);
  assert.equal(state.flags[springFlag.setFlag], true, `回合 ${springOpenTurn} 大潮开启`);
});

test('势力计划：到期结算一次且只结算一次', () => {
  const { bp, state } = freshState(44);
  const plan = bp.actors.flatMap((a) => a.plans ?? []).find((p) => p.id === 'plan-dock-strike')!;
  const dueTurn = windowsOf(plan.trigger)[0]!.gte;
  const flag = plan.effects.find((e) => 'setFlag' in e) as { setFlag: string };

  while (state.turn < dueTurn - 1) worldTick(bp, state);
  assert.ok(!state.plansFired.includes(plan.id));
  worldTick(bp, state); // 到期回合
  assert.ok(state.plansFired.includes(plan.id), `回合 ${dueTurn} 互助会慢工谈判结算`);
  assert.equal(state.flags[flag.setFlag], true);
  const before = state.plansFired.length;
  worldTick(bp, state);
  assert.equal(state.plansFired.length, before, '同一计划不重复结算');
});

test('离屏后果可见性：visible=false 的计划后果不进入玩家视野但可追溯', () => {
  const { bp, state } = freshState(44);
  const hiddenBp: Blueprint = JSON.parse(JSON.stringify(bp));
  const plan = hiddenBp.actors.flatMap((a) => a.plans ?? []).find((p) => p.id === 'plan-dock-strike')!;
  const actor = hiddenBp.actors.find((a) => (a.plans ?? []).some((p) => p.id === plan.id))!;
  plan.visible = false;
  const dueTurn = windowsOf(plan.trigger)[0]!.gte;
  while (state.turn < dueTurn - 1) worldTick(hiddenBp, state);
  const tick = worldTick(hiddenBp, state); // 到期回合
  const hidden = tick.consequences.filter((c) => c.source.startsWith(`actor:${actor.id}`) && c.visible === false);
  assert.ok(hidden.length > 0, '不可见的离屏后果存在（这件事发生时我不在场）');
  assert.ok(hidden.some((c) => c.text.includes('慢工谈判')));
});

test('势力反应：洞察足够时档案守护者主动示好（世界反馈玩家成长）', () => {
  const { bp, state } = freshState(44);
  const plan = bp.actors.flatMap((a) => a.plans ?? []).find((p) => p.id === 'plan-keeper-notice')!;
  const threshold = (plan.trigger as { asset: string; gte: number }).gte;
  const gain = plan.effects.find((e) => 'asset' in e) as { asset: string; delta: number };
  state.assets.insight = threshold;
  const tick = worldTick(bp, state);
  assert.ok(state.plansFired.includes(plan.id));
  assert.equal(state.assets[gain.asset], gain.delta);
  assert.ok(tick.consequences.some((c) => c.visible && c.text.includes('注意到了你')));
});

test('定时事件：税日按 Blueprint 数据扣生计', () => {
  const { bp, state } = freshState(44);
  const ev = bp.scheduledEvents!.find((e) => e.id === 'ev-tax-day')!;
  const taxTurn = windowsOf(ev.trigger)[0]!.gte;
  const delta = ev.effects.find((e) => 'asset' in e) as { asset: string; delta: number };
  // 税日当回合内还会结算一次维护（M3：维护在 worldTick 内每回合一次）
  const upkeep = bp.assetTypes
    .filter((a) => a.maintenance?.asset === 'margin')
    .reduce((s, a) => s + a.maintenance!.perTurn, 0);
  state.assets.margin = 10;
  const before = state.assets.margin;
  while (state.turn < taxTurn - 1) worldTick(bp, state);
  const marginAtTaxDay = state.assets.margin;
  const tick = worldTick(bp, state); // 税日回合
  assert.ok(state.eventsFired.includes(ev.id));
  assert.ok(tick.consequences.some((c) => c.text.includes('宿税')));
  assert.equal(state.assets.margin, marginAtTaxDay + delta.delta - upkeep, '税日变化 = 数据 delta - 当回合维护');
  assert.ok(marginAtTaxDay < before, '税日前的回合里维护也在逐回合结算（M3）');
});
