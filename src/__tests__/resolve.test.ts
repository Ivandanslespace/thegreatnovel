/** resolve：结算管线——可重放、非法硬拒、不可逆、成本与结束判定。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveAction, legalActions } from '../resolve.ts';
import { validateBlueprint } from '../blueprint.ts';
import { initState } from '../save.ts';
import { BLUEPRINT_SCHEMA_VERSION } from '../types.ts';
import type { Blueprint, EngineError } from '../types.ts';
import { freshState, play } from './helpers.ts';

function miniBlueprint(): Blueprint {
  return {
    schemaVersion: BLUEPRINT_SCHEMA_VERSION,
    meta: { name: 'mini', prompt: '测试世界', seed: 1, controlAxis: '测试' },
    designCheck: {
      controlGap: 'ok', legibleRule: 'ok', leverageConversion: 'ok', compounding: 'ok',
      opportunityCost: 'ok', worldFeedback: 'ok', portability: 'ok',
    },
    laws: [{ id: 'law-x', description: '测试规律' }],
    assetTypes: [
      { id: 'gold', name: '金', kind: 'currency', initial: 10 },
      { id: 'house', name: '屋', kind: 'property', initial: 1, maintenance: { asset: 'gold', perTurn: 2 } },
    ],
    actions: [
      {
        id: 'gamble', name: '赌博', description: '测试抽签', tier: 0,
        costs: { time: 1 }, risk: { seedTag: 'g' },
        outcomes: [
          { id: 'win', weight: 1, description: '赢', effects: [{ asset: 'gold', delta: 5 }] },
          { id: 'doom', weight: 1, description: '倾家荡产', irreversible: true, effects: [{ asset: 'gold', delta: -3 }] },
        ],
      },
      { id: 'locked', name: '高阶行动', description: '', tier: 1, outcomes: [{ id: 'o', weight: 1, description: 'x' }] },
    ],
    leverage: {
      id: 'lev', name: '测试杠杆', description: '', causalChain: ['law-x'],
      cost: 'c', whyExclusive: 'w', exclusiveActions: [], modifiers: [], enabled: true,
    },
    actors: [{ id: 'a', name: 'a', goals: ['g'], plans: [] }],
    facts: [{ id: 'f', description: 'f', scope: 'player' }],
    regions: [{ id: 'r', name: 'r', description: '', initiallyUnlocked: true }],
    tiers: [],
    expansion: [],
    winLose: { description: '无' },
  };
}

test('可重放：同种子同序列必达同一状态（宪章 §1.1）', () => {
  const seq = ['gather-rumors', 'casual-labor', 'rest', 'gather-rumors', 'casual-labor'];
  const a = freshState(44);
  const b = freshState(44);
  play(a.bp, a.state, seq);
  play(b.bp, b.state, seq);
  assert.deepEqual(
    { assets: a.state.assets, flags: a.state.flags, known: a.state.knownFacts, turn: a.state.turn, counters: a.state.counters },
    { assets: b.state.assets, flags: b.state.flags, known: b.state.knownFacts, turn: b.state.turn, counters: b.state.counters },
  );
});

test('非法行动硬拒：未知道事实就贸易 + 未知行动', () => {
  const { bp, state } = freshState(44);
  try {
    resolveAction(bp, state, 'trade-run');
    assert.fail('应当拒绝');
  } catch (err) {
    const e = err as EngineError;
    assert.equal(e.code, 'ILLEGAL_ACTION');
    assert.ok(e.details!.some((d) => d.includes('不知道')));
  }
  try {
    resolveAction(bp, state, 'fly-to-moon');
    assert.fail('应当拒绝');
  } catch (err) {
    assert.equal((err as EngineError).code, 'UNKNOWN_ACTION');
  }
  assert.equal(state.turn, 0, '被拒绝的行动不花费时间');
});

test('成本不足硬拒且不扣时间', () => {
  const bp = miniBlueprint();
  const state = initState(bp, 'w', 1);
  state.assets.gold = 0;
  bp.actions[0]!.costs = { time: 1, assets: { gold: 5 } };
  try {
    resolveAction(bp, state, 'gamble');
    assert.fail('应当拒绝');
  } catch (err) {
    const e = err as EngineError;
    assert.equal(e.code, 'ILLEGAL_ACTION');
    assert.match(e.message, /成本不足/);
  }
  assert.equal(state.turn, 0);
  assert.equal(state.assets.gold, 0);
});

test('不可逆结果被显式标记（宪章 §6）', () => {
  const bp = miniBlueprint();
  // 期望值由 Blueprint 数据推导（M13）：初始金 - doom 的 delta - 屋的每回合维护
  const initialGold = bp.assetTypes.find((a) => a.id === 'gold')!.initial ?? 0;
  const doomDelta = bp.actions.find((a) => a.id === 'gamble')!.outcomes
    .find((o) => o.id === 'doom')!.effects!
    .reduce((s, e) => s + ('asset' in e && e.asset === 'gold' ? e.delta : 0), 0);
  const upkeep = bp.assetTypes.find((a) => a.id === 'house')!.maintenance!.perTurn;
  let sawIrreversible = false;
  for (let seed = 1; seed <= 30 && !sawIrreversible; seed++) {
    const state = initState(bp, 'w', seed);
    const res = resolveAction(bp, state, 'gamble');
    if (res.outcomeId === 'doom') {
      sawIrreversible = true;
      assert.equal(res.irreversible, true);
      assert.ok(res.consequences.some((c) => c.text.includes('不可逆')));
      assert.equal(state.assets.gold, initialGold + doomDelta - upkeep, '输掉的金与维护费都来自数据');
    } else {
      assert.equal(res.irreversible, false);
    }
  }
  assert.ok(sawIrreversible, '30 个种子内应至少出现一次不可逆结果');
});

test('维护结算：长期资产每回合消耗（宪章 §4.1）', () => {
  const bp = miniBlueprint();
  const state = initState(bp, 'w', 7);
  const res = resolveAction(bp, state, 'gamble');
  assert.ok(res.consequences.some((c) => c.kind === 'maintenance' && c.text.includes('维护')));
});

test('阶层门槛：未达阶层的高阶行动被拒', () => {
  const bp = miniBlueprint();
  const state = initState(bp, 'w', 1);
  const info = legalActions(bp, state).find((x) => x.action.id === 'locked')!;
  assert.equal(info.legal, false);
  assert.ok(info.reasons.some((r) => r.includes('阶层')));
});

test('终局后禁止行动', () => {
  const bp = miniBlueprint();
  const state = initState(bp, 'w', 1);
  state.ended = { reason: '测试结束', turn: 3 };
  try {
    resolveAction(bp, state, 'gamble');
    assert.fail('应当拒绝');
  } catch (err) {
    assert.equal((err as EngineError).code, 'ALREADY_ENDED');
  }
});

test('胜负判定：生计归零即败（回声潮港）', () => {
  const { bp, state } = freshState(44);
  // rest 补生计：margin 0→+3→维护-1→2，不会败
  state.assets.margin = 0;
  resolveAction(bp, state, 'rest');
  assert.equal(state.ended, undefined);
  // gather-rumors 不补生计：margin 0→维护-1→-1 → 触发 lose
  state.assets.margin = 0;
  resolveAction(bp, state, 'gather-rumors');
  assert.notEqual(state.ended, undefined);
  assert.match(state.ended!.reason, /失败/);
});

/**
 * M13：最小异形世界——完全不同的资产集（灯油/信誉）、无窗口条件、无维护、
 * 无势力计划。引擎必须照常结算，证明引擎是世界无关的通用原语解释器。
 */
function alienBlueprint(): Blueprint {
  return {
    schemaVersion: BLUEPRINT_SCHEMA_VERSION,
    meta: { name: 'lamp-world', prompt: '灯塔荒原', seed: 3, controlAxis: '光与信誉' },
    designCheck: {
      controlGap: 'ok', legibleRule: 'ok', leverageConversion: 'ok', compounding: 'ok',
      opportunityCost: 'ok', worldFeedback: 'ok', portability: 'ok',
    },
    laws: [{ id: 'law-storm', description: '风暴夜灯油耗尽即失明' }],
    assetTypes: [
      { id: 'oil', name: '灯油', kind: 'currency', initial: 4 },
      { id: 'repute', name: '信誉', kind: 'status', initial: 0 },
    ],
    actions: [
      {
        id: 'refine', name: '炼油', description: '从海藻中提炼灯油', tier: 0,
        costs: { time: 1 }, risk: { seedTag: 'refine' },
        outcomes: [
          { id: 'rich', weight: 2, description: '油脉丰沛', effects: [{ asset: 'oil', delta: 3 }] },
          { id: 'poor', weight: 3, description: '只够点灯', effects: [{ asset: 'oil', delta: 1 }] },
        ],
      },
      {
        id: 'light-beacon', name: '点灯引航', description: '消耗灯油为航船引航，换取信誉', tier: 0,
        costs: { time: 1, assets: { oil: 2 } },
        outcomes: [{ id: 'guided', weight: 1, description: '航船平安靠岸', effects: [{ asset: 'repute', delta: 2 }] }],
      },
    ],
    leverage: {
      id: 'lev-lamp', name: '长明术', description: '一滴油点亮更久的光（本测试中关闭，仅验证结构）', enabled: false,
      causalChain: [], cost: '', whyExclusive: '', // enabled:false 时三项必填被豁免（M11）
      exclusiveActions: [], modifiers: [],
    },
    actors: [{ id: 'keepers', name: '守灯人', goals: ['守望'], plans: [] }],
    facts: [{ id: 'fact-oil-vein', description: '东礁有油脉', scope: 'player' }],
    regions: [{ id: 'reef', name: '东礁', description: '', initiallyUnlocked: true }],
    tiers: [],
    expansion: [],
    winLose: {
      description: '信誉满五，成为灯塔主；灯油耗尽则沉入黑暗。',
      win: { asset: 'repute', gte: 5 },
      lose: { asset: 'oil', lte: 0 },
    },
  };
}

test('异形世界：无窗口/不同资产集的最小世界照常结算（引擎世界无关性，M13）', () => {
  const bp = alienBlueprint();
  const validation = validateBlueprint(bp);
  assert.deepEqual(validation.issues, [], '异形世界自身必须通过校验');

  // 结算两回合：炼油 → 点灯引航。期望资产变化全部由数据推导。
  const state = initState(bp, 'alien', 3);
  const refine = resolveAction(bp, state, 'refine');
  const refineOutcome = bp.actions.find((a) => a.id === 'refine')!.outcomes.find((o) => o.id === refine.outcomeId)!;
  const refineGain = refineOutcome.effects!.reduce((s, e) => s + ('asset' in e && e.asset === 'oil' ? e.delta : 0), 0);
  assert.equal(state.assets.oil, 4 + refineGain, '灯油变化 = 初始 + 结果 delta（无维护、无离屏干扰）');
  assert.equal(state.turn, 1);

  const beacon = resolveAction(bp, state, 'light-beacon');
  assert.equal(beacon.outcomeId, 'guided');
  assert.equal(state.assets.oil, 4 + refineGain - 2, '点灯消耗 2 灯油（来自 costs 数据）');
  assert.equal(state.assets.repute, 2, '信誉按 outcome effects 增加');
  assert.equal(state.ended, undefined, '尚未满足胜负条件');

  // 可重放：同种子同序列必达同一状态
  const replay = initState(bp, 'alien', 3);
  resolveAction(bp, replay, 'refine');
  resolveAction(bp, replay, 'light-beacon');
  assert.deepEqual({ assets: replay.assets, turn: replay.turn }, { assets: state.assets, turn: state.turn });
});

