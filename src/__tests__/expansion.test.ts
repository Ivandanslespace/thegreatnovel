/**
 * expand（C1）：Lazy Expansion 闭环——候选先校验、通过才物化、物化入库且 verify 通过。
 * 全部走 CLI 进程，模拟真实 Agent 调用链（宪章 §7）。
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { loadState, saveState, readHistory } from '../save.ts';
import { cliScript, echoBlueprintPath, tmpBase } from './helpers.ts';

interface CliResult {
  ok: boolean;
  data?: any;
  error?: { code: string; message: string; details?: string[] };
}

function cli(base: string, ...args: string[]): CliResult {
  let out: string;
  try {
    out = execFileSync(process.execPath, [cliScript, ...args], { cwd: base, encoding: 'utf8' });
  } catch (err) {
    const e = err as { stdout?: Buffer | string };
    out = typeof e.stdout === 'string' ? e.stdout : (e.stdout?.toString('utf8') ?? '');
    if (!out.trim()) throw err;
  }
  const lines = out.trim().split('\n');
  return JSON.parse(lines[lines.length - 1]!) as CliResult;
}

/** 把存档推进到阶层 2，使 exp-tier2-far 规则处于触发状态。 */
async function reachTier2(base: string): Promise<void> {
  const state = await loadState(base, 'echo-harbor');
  state.tier = 2;
  await saveState(base, state);
}

test('expand：规则未触发即物化被硬拒（宪章 §7 先验证后成为事实）', () => {
  const base = tmpBase();
  const n = cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'echo-harbor', '--seed', '1');
  assert.equal(n.ok, true, JSON.stringify(n.error));
  const res = cli(
    base, 'expand',
    '--world', 'echo-harbor', '--rule', 'exp-tier2-far',
    '--id', 'fact-fog-anchor', '--desc', '雾锚头：外海雾中的系泊遗迹',
  );
  assert.equal(res.ok, false);
  assert.equal(res.error!.code, 'EXPANSION_REJECTED');
  assert.ok(res.error!.details!.some((d) => d.includes('尚未触发')), JSON.stringify(res.error));
  // 拒绝后随档 Blueprint 不得被写入新事实
  const frozen = JSON.parse(readFileSync(path.join(base, 'saves', 'echo-harbor', 'blueprint.json'), 'utf8'));
  assert.ok(!frozen.facts.some((f: { id: string }) => f.id === 'fact-fog-anchor'));
});

test('expand：id 冲突被拒（物化不得覆盖既有事实）', async () => {
  const base = tmpBase();
  cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'echo-harbor', '--seed', '1');
  await reachTier2(base);
  const res = cli(
    base, 'expand',
    '--world', 'echo-harbor', '--rule', 'exp-tier2-far',
    '--id', 'fact-dock-gossip', '--desc', '试图覆盖既有事实',
  );
  assert.equal(res.ok, false);
  assert.equal(res.error!.code, 'EXPANSION_REJECTED');
  assert.ok(res.error!.details!.some((d) => d.includes('已存在')), JSON.stringify(res.error));
});

test('expand：合法物化入库，verify 通过且历史可追溯', async () => {
  const base = tmpBase();
  cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'echo-harbor', '--seed', '1');
  await reachTier2(base);

  const before = JSON.parse(readFileSync(path.join(base, 'saves', 'echo-harbor', 'blueprint.json'), 'utf8'));
  const res = cli(
    base, 'expand',
    '--world', 'echo-harbor', '--rule', 'exp-tier2-far',
    '--id', 'fact-fog-anchor', '--desc', '雾锚头：外海雾中的系泊遗迹，旧潮图在此断线',
    '--category', 'geography', '--anchor-tier', '2',
  );
  assert.equal(res.ok, true, JSON.stringify(res.error));
  assert.equal(res.data.fact, 'fact-fog-anchor');
  assert.equal(res.data.factsTotal, before.facts.length + 1, '仅追加一条事实');

  // 随档 Blueprint 已写回新事实，且既有条目不被追溯修改
  const after = JSON.parse(readFileSync(path.join(base, 'saves', 'echo-harbor', 'blueprint.json'), 'utf8'));
  const fact = after.facts.find((f: { id: string }) => f.id === 'fact-fog-anchor');
  assert.ok(fact, '新事实已物化进随档 Blueprint');
  assert.equal(fact.scope, 'hidden', '远方事实默认 hidden，须经观察获得（宪章 §7）');
  assert.equal(fact.anchor?.tier, 2);
  assert.deepEqual(after.actions, before.actions, '物化不得追溯修改既有行动');

  // verify 全绿（含历史对账）
  const verify = cli(base, 'verify', '--world', 'echo-harbor');
  assert.equal(verify.ok, true, JSON.stringify(verify.error));

  // 物化事件进入 append-only 历史
  const history = await readHistory(base, 'echo-harbor');
  assert.ok(history.some((h) => h.source === 'expansion:exp-tier2-far' && h.text.includes('fact-fog-anchor')));
});
