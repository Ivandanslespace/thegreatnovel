/** blueprint：非法 Blueprint 必须全部被拒，逐条结构化错误。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { validateBlueprint, withLeverageDisabled } from '../blueprint.ts';
import { loadEchoBlueprint } from './helpers.ts';
import type { Blueprint } from '../types.ts';

function clone(): Blueprint {
  return JSON.parse(JSON.stringify(loadEchoBlueprint())) as Blueprint;
}

function codes(bp: unknown): string[] {
  return validateBlueprint(bp).issues.map((i) => i.code);
}

test('演示 Blueprint 通过校验', () => {
  const result = validateBlueprint(clone());
  assert.deepEqual(result.issues, []);
  assert.equal(result.ok, true);
});

test('拒绝：悬空资产引用（DANGLING_REF）', () => {
  const bp = clone();
  bp.actions[0]!.outcomes[0]!.effects = [{ asset: 'ghost-asset', delta: 1 }];
  assert.ok(codes(bp).includes('DANGLING_REF'));
});

test('拒绝：悬空事实引用', () => {
  const bp = clone();
  bp.tiers[0]!.gate = { fact: 'ghost-fact' };
  assert.ok(codes(bp).includes('DANGLING_REF'));
});

test('拒绝：负成本（NEGATIVE_COST）', () => {
  const bp = clone();
  bp.actions.find((a) => a.id === 'trade-run')!.costs!.assets = { credential: -2 };
  assert.ok(codes(bp).includes('NEGATIVE_COST'));
});

test('拒绝：负时间成本', () => {
  const bp = clone();
  bp.actions[0]!.costs = { time: -1 };
  assert.ok(codes(bp).includes('NEGATIVE_COST'));
});

test('拒绝：含抽签的行动缺 seedTag（MISSING_SEEDTAG）', () => {
  const bp = clone();
  delete bp.actions.find((a) => a.id === 'trade-run')!.risk;
  assert.ok(codes(bp).includes('MISSING_SEEDTAG'));
});

test('拒绝：杠杆未绑定任何规律（LEVERAGE_UNBOUND，宪章 §3.1）', () => {
  const bp = clone();
  bp.leverage.causalChain = [];
  assert.ok(codes(bp).includes('LEVERAGE_UNBOUND'));
});

test('拒绝：杠杆因果链引用不存在的规律', () => {
  const bp = clone();
  bp.leverage.causalChain = ['law-ghost'];
  assert.ok(codes(bp).includes('DANGLING_REF'));
});

test('拒绝：designCheck 七问缺失/空白（宪章 §12）', () => {
  const bp = clone();
  bp.designCheck.controlGap = '   ';
  const issues = validateBlueprint(bp).issues;
  assert.ok(issues.some((i) => i.code === 'DESIGN_CHECK_EMPTY' && i.path === 'designCheck.controlGap'));
  const bp2 = clone();
  delete (bp2.designCheck as unknown as Record<string, unknown>).portability;
  assert.ok(codes(bp2).includes('DESIGN_CHECK_EMPTY'));
});

test('拒绝：id 冲突（ID_CONFLICT）', () => {
  const bp = clone();
  bp.actions[1]!.id = bp.actions[0]!.id;
  assert.ok(codes(bp).includes('ID_CONFLICT'));
});

test('拒绝：杠杆独占行动与 leverageOnly 不一致', () => {
  const bp = clone();
  bp.actions.find((a) => a.id === 'echo-forecast')!.leverageOnly = false;
  assert.ok(codes(bp).includes('INCONSISTENT'));
});

test('拒绝：modifier 引用不存在的结果', () => {
  const bp = clone();
  bp.leverage.modifiers[0]!.outcome = 'ghost-outcome';
  assert.ok(codes(bp).includes('DANGLING_REF'));
});

test('拒绝：flag 条件引用从未被设置的 flag', () => {
  const bp = clone();
  bp.actions.find((a) => a.id === 'echo-forecast')!.requires = [{ flag: 'ghost-flag' }];
  assert.ok(codes(bp).includes('DANGLING_REF'));
});

test('拒绝：缺少初始区域', () => {
  const bp = clone();
  for (const r of bp.regions) r.initiallyUnlocked = false;
  assert.ok(codes(bp).includes('NO_START'));
});

test('拒绝：schemaVersion 不匹配', () => {
  const bp = clone();
  bp.schemaVersion = 99;
  assert.ok(codes(bp).includes('SCHEMA_VERSION'));
});

test('withLeverageDisabled：仅关闭杠杆开关，其余结构不变', () => {
  const bp = clone();
  const off = withLeverageDisabled(bp);
  assert.equal(off.leverage.enabled, false);
  assert.equal(bp.leverage.enabled, true, '原 Blueprint 不被修改');
  assert.equal(off.actions.length, bp.actions.length);
});
