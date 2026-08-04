// T2 端到端测试（node:test，零依赖）：固定种子 + 内联 proposal 跑通
// new→propose→accept→actions→act→interact→end-turn×3→chapter→verify 全链路；
// 非法 factsSeq 被 chapter 拒绝；缺杠杆四要素的 proposal 被 propose 拒绝且含修复指引。
// 临时目录一律 temps/，after 清理（项目硬约束）。
import { test, after } from 'node:test';
import { equal, ok } from 'node:assert/strict';
import { mkdirSync, rmSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { runCli, type CliResult, type EnvelopeErr, type EnvelopeOk } from '../src/cli.ts';

const ROOT = join('temps', 'cli-test-worlds');

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

function expectErr(r: CliResult, code: string): string[] {
  equal(r.envelope.ok, false, JSON.stringify(r.envelope));
  equal(r.exitCode, 1);
  const e = r.envelope as EnvelopeErr;
  equal(e.code, code);
  return e.hints;
}

/** 内联完整 proposal（合法）。 */
function makeProposal(): Record<string, unknown> {
  return {
    worldName: '测试海岸',
    language: 'zh',
    background: '大潮汐摧毁了全部淡水设施，失控是结构性的。',
    rulesExplicit: ['明规则1', '明规则2', '明规则3'],
    rulesHidden: ['hidden-rule-1'],
    resources: ['supplies', 'scrap', 'water'],
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
      {
        id: 'study',
        label: '研究工艺',
        timeCost: 1,
        requires: {},
        costs: { focus: 1 },
        risk: { level: 'low', base: 0, spread: 0 },
        effects: [{ verb: 'knowledge', knowledge: 'craft' }],
      },
      {
        id: 'build',
        label: '建造工坊',
        timeCost: 2,
        requires: { knowledge: ['craft'] },
        costs: { resources: { supplies: 3 } },
        risk: { level: 'medium', base: 2, spread: 1 },
        effects: [{ verb: 'assetInvest', asset: 'workshop' }],
      },
      {
        id: 'greet',
        label: '示好',
        timeCost: 1,
        requires: {},
        costs: {},
        risk: { level: 'low', base: 0, spread: 0 },
        effects: [{ verb: 'relation', npcId: 'n1', delta: 1 }],
      },
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
      { id: 'n3', name: '三号', goal: 'water', resources: {}, power: 3, personality: 'p' },
      { id: 'n4', name: '四号', goal: 'supplies', resources: {}, power: 1, personality: 'p' },
      { id: 'n5', name: '五号', goal: 'scrap', resources: {}, power: 2, personality: 'p' },
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

test('full pipeline: new→accept→actions→act→end-turn×3→chapter→verify (fixed seed)', () => {
  mkdirSync(ROOT, { recursive: true });
  const slug = 'pipeline';
  const pf = join(ROOT, 'proposal.json');
  writeJson(pf, makeProposal());

  // new（固定种子，确定性）
  let r = runCli(['new', slug, '--lang', 'zh', '--seed', '20260804', '--root', ROOT]);
  const newed = expectOk(r, 'new');
  equal(newed.seed, 20260804);

  // 重复 new 被拒绝
  expectErr(runCli(['new', slug, '--root', ROOT]), 'E_ILLEGAL_ACTION');

  // propose 只校验
  r = runCli(['propose', slug, '--file', pf, '--root', ROOT]);
  expectOk(r, 'propose');

  // accept：校验 + 初始化
  r = runCli(['accept', slug, '--file', pf, '--root', ROOT]);
  const accepted = expectOk(r, 'accept');
  equal(accepted.seed, 20260804);
  equal(accepted.worldName, '测试海岸');
  const initResources = accepted.resources as Record<string, number>;
  ok(typeof initResources.supplies === 'number' && initResources.supplies >= 5, '开局 supplies 5..9（维护资源）');

  // actions：杠杆物化——focus>0 且 base>0 的合法行动附带 revealed
  r = runCli(['actions', slug, '--root', ROOT]);
  const acts = expectOk(r, 'actions').actions as Array<{ id: string; legal: boolean; revealed?: unknown }>;
  const gather = acts.find((a) => a.id === 'gather');
  ok(gather && gather.legal, 'gather 应合法');
  ok(gather && gather.revealed !== undefined, 'focus>0 时 gather 应带 revealed');

  // act：执行 gather
  r = runCli(['act', slug, 'gather', '--root', ROOT]);
  const acted = expectOk(r, 'act gather');
  ok(typeof acted.factsSeq === 'number');

  // interact：commit 产生 deadline/责任记录
  r = runCli(['interact', slug, 'n1', 'commit', '--root', ROOT]);
  const inter = expectOk(r, 'interact commit');
  const outcome = inter.outcome as { accepted: boolean; deadlineTurn?: number };
  equal(outcome.accepted, true);
  ok(outcome.deadlineTurn !== undefined, 'commit 应产生 deadline');
  ok(existsSync(join(ROOT, slug, 'commitments.json')), 'commitments.json 应落盘');

  // end-turn ×3：每次产出 chapterFact（factsSeq = 最新事实序号）
  let facts = 0;
  for (let i = 0; i < 3; i++) {
    r = runCli(['end-turn', slug, '--root', ROOT]);
    const d = expectOk(r, `end-turn ${i + 1}`);
    const cf = d.chapterFact as { factsSeq: number; turn: number };
    ok(Number.isInteger(cf.factsSeq) && cf.factsSeq > facts, 'factsSeq 单调递增');
    facts = cf.factsSeq;
  }

  // chapter：非法 factsSeq（跳章）被拒绝
  const cfFile = join(ROOT, 'chapter.md');
  writeFileSync(cfFile, '## 第一章\n\n潮水退去，主角在滩涂上第一次看懂了规则的轮廓。');
  r = runCli(['chapter', slug, '--facts', String(facts + 7), '--file', cfFile, '--root', ROOT]);
  let hints = expectErr(r, 'E_ILLEGAL_ACTION');
  ok(hints.some((h) => h.includes('章节') || h.toLowerCase().includes('chapter')), '跳章拒绝应附章节提示');

  // chapter：过期 factsSeq 也被拒绝
  r = runCli(['chapter', slug, '--facts', '1', '--file', cfFile, '--root', ROOT]);
  expectErr(r, 'E_ILLEGAL_ACTION');

  // chapter：正确 factsSeq 通过，散文 + 引擎结算面板追加进小说文件
  r = runCli(['chapter', slug, '--facts', String(facts), '--file', cfFile, '--root', ROOT]);
  expectOk(r, 'chapter submit');

  // 重复提交同一 factsSeq 被拒绝（防重复）
  r = runCli(['chapter', slug, '--facts', String(facts), '--file', cfFile, '--root', ROOT]);
  expectErr(r, 'E_ILLEGAL_ACTION');

  // 小说文件内容校验：含 frontmatter 与结算面板
  const novelPath = join(ROOT, slug, 'novel', '《测试海岸》.md');
  ok(existsSync(novelPath), '小说文件应存在');
  const novel = readFileSync(novelPath, 'utf8');
  ok(novel.includes('seed: 20260804'), 'frontmatter 含种子');
  ok(novel.includes('leverage: 潮汐预感'), 'frontmatter 含杠杆名');
  ok(novel.includes(`factsSeq:${facts}`), '章节事实标记');
  ok(novel.includes('结算面板'), '引擎自动附结算面板');

  // verify：重放一致
  r = runCli(['verify', slug, '--root', ROOT]);
  expectOk(r, 'verify');

  // log：可读事件流
  r = runCli(['log', slug, '--last', '5', '--root', ROOT]);
  const logged = expectOk(r, 'log');
  ok((logged.events as unknown[]).length <= 5);
});

test('chapter with unknown world → E_WORLD_NOT_FOUND', () => {
  mkdirSync(ROOT, { recursive: true });
  const r = runCli(['chapter', 'ghost-world', '--facts', '1', '--file', 'temps/nope.md', '--root', ROOT]);
  expectErr(r, 'E_WORLD_NOT_FOUND');
});

test('proposal missing leverage element → propose rejected with fix guide', () => {
  mkdirSync(ROOT, { recursive: true });
  const bad = makeProposal();
  const lev = bad.leverage as Record<string, unknown>;
  delete lev.failureMode; // 宪法 §3.1 四要素缺失
  const bf = join(ROOT, 'proposal-bad.json');
  writeJson(bf, bad);

  const r = runCli(['propose', 'bad-world', '--file', bf, '--root', ROOT]);
  const hints = expectErr(r, 'E_PROPOSAL_INVALID');
  ok(hints.length > 0, '应含错误列表');
  const leverErr = hints.find((h) => h.includes('leverage.failureMode'));
  ok(leverErr, '错误应定位到 leverage.failureMode');
  ok(leverErr!.includes('→'), '错误应附修复建议');
  ok(leverErr!.includes('§3.1'), '错误应引用宪法 §3.1');

  // 同样的 proposal 走 accept 也被拒绝（不会创建任何存档副作用）
  const r2 = runCli(['new', 'bad-world', '--root', ROOT]);
  expectOk(r2, 'new bad-world');
  const r3 = runCli(['accept', 'bad-world', '--file', bf, '--root', ROOT]);
  expectErr(r3, 'E_PROPOSAL_INVALID');
  ok(!existsSync(join(ROOT, 'bad-world', 'state.json')), '非法 proposal 不得产生 state.json');
});

test('illegal action refused with localized hints (self-contained world)', () => {
  mkdirSync(ROOT, { recursive: true });
  // 自建世界（独立 slug + 固定 seed）：消除对全链路用例执行顺序的依赖
  const slug = 'hints-world';
  const pf = join(ROOT, 'proposal-hints.json');
  writeJson(pf, makeProposal());
  expectOk(runCli(['new', slug, '--lang', 'zh', '--seed', '777', '--root', ROOT]), 'new hints-world');
  expectOk(runCli(['accept', slug, '--file', pf, '--root', ROOT]), 'accept hints-world');
  // build 需要 knowledge:craft——条件未满足
  const r = runCli(['act', slug, 'build', '--root', ROOT]);
  const hints = expectErr(r, 'E_ILLEGAL_ACTION');
  ok(hints.some((h) => h.includes('知识') || h.toLowerCase().includes('knowledge')), '应含知识缺失本地化提示');
});
