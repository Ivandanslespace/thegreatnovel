// T6 回归测试（node:test，零依赖）：评审修复项各一条。
// 覆盖：语言一致性 / 重复 accept / hints 透传 / unlock 链路 / 窗口过期事件保留 /
// worldName 路径穿越 / finishWorld 事件管道 + verify / 存档损坏容错。
// 临时目录一律 temps/，after 清理（项目硬约束）。
import { test, after } from 'node:test';
import { equal, ok } from 'node:assert/strict';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { runCli, type CliResult, type EnvelopeErr, type EnvelopeOk } from '../src/cli.ts';
import type { WorldState } from '../src/engine/types.ts';
import { endTurn } from '../src/engine/tick.ts';

const ROOT = join('temps', 't6-test-worlds');

after(() => {
  try {
    rmSync(ROOT, { recursive: true, force: true });
  } catch {}
});

function writeJson(path: string, data: unknown): void {
  writeFileSync(path, JSON.stringify(data, null, 2));
}

function expectOk(r: CliResult, msg?: string): Record<string, unknown> {
  ok(r.envelope.ok, msg ?? JSON.stringify(r.envelope));
  equal(r.exitCode, 0);
  return (r.envelope as EnvelopeOk).data as Record<string, unknown>;
}

function expectErr(r: CliResult, code: string, msg?: string): string[] {
  equal(r.envelope.ok, false, msg ?? JSON.stringify(r.envelope));
  equal(r.exitCode, 1);
  const e = r.envelope as EnvelopeErr;
  equal(e.code, code);
  return e.hints;
}

/** 最小合法 proposal（可定制 language / worldName / actions 追加项）。 */
function makeProposal(extraActions: Array<Record<string, unknown>> = [], lang = 'zh', worldName = 'T6测试世界'): Record<string, unknown> {
  return {
    worldName,
    language: lang,
    background: '失控是结构性的。',
    rulesExplicit: ['明规则1', '明规则2', '明规则3'],
    rulesHidden: ['hidden-rule-1'],
    resources: ['supplies', 'scrap'],
    actions: [
      {
        id: 'gather',
        label: '搜集补给',
        timeCost: 1,
        requires: {},
        costs: {},
        risk: { level: 'low', base: 3, spread: 1 },
        effects: [{ verb: 'resource', resource: 'supplies', amount: 3 }],
      },
      ...extraActions,
    ],
    leverage: {
      name: '潮汐预感',
      causalChain: '改变时间→物资的转化链',
      cost: '消耗 focus 并引来注意',
      whyUnreplicable: '独特感官记忆，无法传授',
      failureMode: '闸门改期时失准，按正常风险结算',
    },
    npcs: [
      { id: 'n1', name: '一号', goal: 'supplies', resources: {}, power: 2, personality: 'p' },
      { id: 'n2', name: '二号', goal: 'scrap', resources: {}, power: 2, personality: 'p' },
      { id: 'n3', name: '三号', goal: 'supplies', resources: {}, power: 3, personality: 'p' },
      { id: 'n4', name: '四号', goal: 'scrap', resources: {}, power: 1, personality: 'p' },
      { id: 'n5', name: '五号', goal: 'supplies', resources: {}, power: 2, personality: 'p' },
    ],
    tierGates: [
      { minAssetLevel: 1, minKnowledge: 2, minStanding: 0.3 },
      { minAssetLevel: 3, minKnowledge: 4, minStanding: 0.5 },
      { minAssetLevel: 5, minKnowledge: 7, minStanding: 0.6 },
    ],
    expansionAnchors: [
      { id: 'anchor-t2', tier: 2, description: 'd2', constraint: 'c2' },
      { id: 'anchor-t3', tier: 3, description: 'd3', constraint: 'c3' },
    ],
  };
}

/** (t6-1) 必修1：proposal.language 与 new --lang 不一致 → propose/accept 均拒绝。 */
test('(t6-1) language mismatch between proposal and registered lang is rejected', () => {
  mkdirSync(ROOT, { recursive: true });
  const slug = 't6-lang';
  const pf = join(ROOT, 'proposal-lang.json');
  writeJson(pf, makeProposal([], 'zh')); // proposal 是 zh
  expectOk(runCli(['new', slug, '--lang', 'en', '--seed', '11', '--root', ROOT]), 'new en');

  const r1 = runCli(['propose', slug, '--file', pf, '--root', ROOT]);
  const h1 = expectErr(r1, 'E_PROPOSAL_INVALID', 'propose 应拒绝语言不一致');
  ok(h1.some((h) => h.startsWith('language:')), 'hints 应给出注册语言');

  const r2 = runCli(['accept', slug, '--file', pf, '--root', ROOT]);
  expectErr(r2, 'E_PROPOSAL_INVALID', 'accept 应拒绝语言不一致');
});

/** (t6-2) 必修2：已初始化世界重复 accept 必须拒绝。 */
test('(t6-2) re-accept on initialized world is refused', () => {
  mkdirSync(ROOT, { recursive: true });
  const slug = 't6-reaccept';
  const pf = join(ROOT, 'proposal-reaccept.json');
  writeJson(pf, makeProposal());
  expectOk(runCli(['new', slug, '--lang', 'zh', '--seed', '22', '--root', ROOT]), 'new');
  expectOk(runCli(['accept', slug, '--file', pf, '--root', ROOT]), 'accept 首次');
  const hints = expectErr(runCli(['accept', slug, '--file', pf, '--root', ROOT]), 'E_ILLEGAL_ACTION', '重复 accept 应拒绝');
  ok(hints.includes('status'), 'hints 应引导用 status 续局');
});

/** (t6-3) 必修3：E_UNKNOWN_ACTION 的 hints 原样透传 actionId，不得出现 hint.* 原始键。 */
test('(t6-3) E_UNKNOWN_ACTION hints pass through raw actionIds (no hint.* keys)', () => {
  mkdirSync(ROOT, { recursive: true });
  const slug = 't6-unknown';
  const pf = join(ROOT, 'proposal-unknown.json');
  writeJson(pf, makeProposal());
  expectOk(runCli(['new', slug, '--lang', 'zh', '--seed', '33', '--root', ROOT]), 'new');
  expectOk(runCli(['accept', slug, '--file', pf, '--root', ROOT]), 'accept');
  const hints = expectErr(runCli(['act', slug, 'no-such-action', '--root', ROOT]), 'E_UNKNOWN_ACTION');
  ok(hints.length > 0, 'hints 应列出可用 actionId');
  ok(hints.includes('gather'), 'hints 应含 gather');
  for (const h of hints) {
    ok(!h.startsWith('hint.'), `不得输出原始 i18n 键：${h}`);
  }
});

/** (t6-4) 必修9：unlock 链路——缺码时本地化提示 unlock:<id>，解锁后行动放行。 */
test('(t6-4) unlock chain: locked action refused with localized hint, unlocked after unlock effect', () => {
  mkdirSync(ROOT, { recursive: true });
  const slug = 't6-unlock';
  const extra = [
    {
      id: 'open-gate',
      label: '拿到开闸时刻表',
      timeCost: 1,
      requires: {},
      costs: {},
      risk: { level: 'low', base: 0, spread: 0 },
      effects: [{ verb: 'unlock', unlock: 'rule:gate-schedule' }],
    },
    {
      id: 'gate-trade',
      label: '按开闸时刻抢收',
      timeCost: 1,
      requires: { unlocks: ['rule:gate-schedule'] },
      costs: {},
      risk: { level: 'low', base: 0, spread: 0 },
      effects: [{ verb: 'resource', resource: 'supplies', amount: 4 }],
    },
  ];
  const pf = join(ROOT, 'proposal-unlock.json');
  writeJson(pf, makeProposal(extra));
  expectOk(runCli(['new', slug, '--lang', 'zh', '--seed', '44', '--root', ROOT]), 'new');
  expectOk(runCli(['accept', slug, '--file', pf, '--root', ROOT]), 'accept');

  // 未解锁：E_ILLEGAL_ACTION + 本地化提示（zh：缺少所需解锁 (rule:gate-schedule)）
  const hints = expectErr(runCli(['act', slug, 'gate-trade', '--root', ROOT]), 'E_ILLEGAL_ACTION');
  ok(hints.some((h) => h.includes('解锁') && h.includes('rule:gate-schedule')), `应含解锁缺失本地化提示：${JSON.stringify(hints)}`);

  // 解锁后可执行
  expectOk(runCli(['act', slug, 'open-gate', '--root', ROOT]), 'open-gate');
  expectOk(runCli(['act', slug, 'gate-trade', '--root', ROOT]), 'gate-trade 解锁后放行');
});

/** (t6-5) 必修16：过期窗口 WindowClosed 事件不再被丢弃，进入 events/turnReport。 */
test('(t6-5) expired windows produce persisted WindowClosed events and enter turnReport', () => {
  const s: WorldState = {
    worldSlug: 't6-window',
    schemaVersion: 1,
    language: 'zh',
    seed: 42,
    rngCounter: 0,
    turn: 1,
    phase: 'playing',
    tier: 0,
    player: {
      resources: { supplies: 6 },
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
    npcs: [{ id: 'n1', name: '一号', goal: 'supplies', resources: {}, power: 2, attitude: 0, alive: true, knowledgeIds: [], pendingEvents: [], lastActed: 0 }],
    rulesKnown: [],
    unlocks: [],
    zones: { materialized: [], anchors: [] },
    windows: [{ id: 'win-x', kind: 'opportunity', labelKey: 'window.opportunity.trade', openedTurn: 0, expiresTurn: 1, cause: 'test' }],
    lastFactsSeq: 0,
    pendingPlayerEvents: [],
    lastTurnReport: null,
  };

  const res = endTurn(s);
  // 事件保留（修复前被 events.length = 0 整批丢弃）
  const closed = res.events.filter((e) => e.type === 'WindowClosed');
  equal(closed.length, 1, '应产生 WindowClosed 事件');
  equal((closed[0].payload as { cause: string }).cause, 'expired');
  // 进入 turnReport（叙事可见）
  equal(res.turnReport.windowsClosed.length, 1, 'turnReport.windowsClosed 应记录');
  equal(res.turnReport.windowsClosed[0].windowId, 'win-x');
  ok(res.turnReport.offscreen.some((e) => e.type === 'WindowClosed'), 'offscreen 应含窗口关闭');
  // seq 不重复
  const seqs = res.events.map((e) => e.seq);
  equal(new Set(seqs).size, seqs.length, '事件 seq 不得重复');
  // 状态中窗口已移除
  equal(res.newState.windows.filter((w) => w.id === 'win-x').length, 0);
});

/** (t6-6) 必修25：worldName 路径穿越被 validateProposal 拒绝。 */
test('(t6-6) worldName path traversal is rejected', () => {
  mkdirSync(ROOT, { recursive: true });
  const slug = 't6-traversal';
  expectOk(runCli(['new', slug, '--lang', 'zh', '--seed', '55', '--root', ROOT]), 'new');
  for (const evil of ['../../evil', 'a/b', 'a\\b', 'a\u0001b']) {
    const pf = join(ROOT, `proposal-evil-${Math.random().toString(36).slice(2)}.json`);
    writeJson(pf, makeProposal([], 'zh', evil));
    const r = runCli(['propose', slug, '--file', pf, '--root', ROOT]);
    const hints = expectErr(r, 'E_PROPOSAL_INVALID', `worldName ${JSON.stringify(evil)} 应被拒绝`);
    ok(hints.some((h) => h.includes('worldName')), `错误应定位 worldName：${JSON.stringify(hints)}`);
  }
});

/** (t6-7) 必修27/18：finishWorld 走统一事件管道（WorldFinished 事件 + phase 由 reducer 施加），verify 可重放。 */
test('(t6-7) finishWorld emits WorldFinished event through the pipeline and verify passes', () => {
  mkdirSync(ROOT, { recursive: true });
  const slug = 't6-finish';
  const pf = join(ROOT, 'proposal-finish.json');
  writeJson(pf, makeProposal());
  expectOk(runCli(['new', slug, '--lang', 'zh', '--seed', '66', '--root', ROOT]), 'new');
  expectOk(runCli(['accept', slug, '--file', pf, '--root', ROOT]), 'accept');
  const et = expectOk(runCli(['end-turn', slug, '--root', ROOT]), 'end-turn');
  const facts = (et.chapterFact as { factsSeq: number }).factsSeq;

  const data = expectOk(runCli(['finish', slug, '--root', ROOT]), 'finish');
  ok(String(data.exportPath).includes('exports'), '应导出到 exports/');
  // 未归档章节事实提示（factsSeq 尚未绑定章节）
  equal(data.warning, 'unarchivedFacts', '应提示未归档事实');
  equal(data.unarchivedFactsSeq, facts);

  // 事件管道：events.jsonl 末尾含 WorldFinished
  const logged = expectOk(runCli(['log', slug, '--last', '3', '--root', ROOT]), 'log');
  const evs = logged.events as Array<{ type: string }>;
  ok(evs.some((e) => e.type === 'WorldFinished'), 'WorldFinished 事件应落盘');

  // phase 由 reducer 施加为 ended；act 被关闭
  expectErr(runCli(['act', slug, 'gather', '--root', ROOT]), 'E_ILLEGAL_ACTION', 'ended 后行动关闭');

  // verify 重放一致（phase 纳入比对面）
  expectOk(runCli(['verify', slug, '--root', ROOT]), 'verify 应通过');
});

/** (t6-8) 可选项29：存档 JSON 损坏 → E_SAVE_CORRUPTED（不裸崩 E_INTERNAL）。 */
test('(t6-8) corrupted state.json surfaces E_SAVE_CORRUPTED', () => {
  mkdirSync(join(ROOT, 't6-corrupt'), { recursive: true });
  writeFileSync(join(ROOT, 't6-corrupt', 'state.json'), '{ this is not json');
  expectErr(runCli(['status', 't6-corrupt', '--root', ROOT]), 'E_SAVE_CORRUPTED');
});
