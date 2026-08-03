/**
 * e2e：固定种子完整一局——从开局到阶层跃迁到胜利，
 * 断言 novel.md 生成且 verify 通过（全部走 CLI 进程，模拟真实 Agent 调用链）。
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { cliScript, echoBlueprintPath, GOLDEN_SEED, GOLDEN_SEQUENCE, tmpBase } from './helpers.ts';

interface CliResult {
  ok: boolean;
  data?: any;
  error?: { code: string; message: string; details?: string[] };
}

function cli(base: string, ...args: string[]): CliResult {
  let out: string;
  try {
    out = execFileSync(process.execPath, [cliScript, ...args], {
      cwd: base,
      encoding: 'utf8',
    });
  } catch (err) {
    // CLI 以退出码 1 + 单行 JSON 表达硬拒，测试需要解析该输出
    const e = err as { stdout?: Buffer | string };
    out = typeof e.stdout === 'string' ? e.stdout : (e.stdout?.toString('utf8') ?? '');
    if (!out.trim()) throw err;
  }
  const lines = out.trim().split('\n');
  return JSON.parse(lines[lines.length - 1]!) as CliResult;
}

test('e2e：固定种子完整一局至胜利，novel.md 生成且 verify 通过', () => {
  const base = tmpBase();

  // 1. 校验 Blueprint
  const v = cli(base, 'validate-blueprint', '--file', echoBlueprintPath);
  assert.equal(v.ok, true, JSON.stringify(v.error));
  assert.equal(v.data.actions, 15);

  // 2. 开局
  const n = cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'echo-harbor', '--seed', String(GOLDEN_SEED));
  assert.equal(n.ok, true, JSON.stringify(n.error));
  assert.equal(n.data.seed, GOLDEN_SEED);

  // 3. 非法行动硬拒（宪章 §9：自由输入不能直接变成结果）
  const illegal = cli(base, 'act', '--id', 'trade-run');
  assert.equal(illegal.ok, false);
  assert.equal(illegal.error!.code, 'ILLEGAL_ACTION');
  assert.ok(illegal.error!.details!.length > 0, '硬拒必须带结构化原因');

  // 4. 按序列结算整局
  let sawTierUp = false;
  let sawTier2Up = false;
  let final: CliResult | null = null;
  for (const id of GOLDEN_SEQUENCE) {
    const res = cli(base, 'act', '--id', id);
    assert.equal(res.ok, true, `${id} 失败：${JSON.stringify(res.error)}`);
    if (res.data.tierUp && res.data.tier === 1) sawTierUp = true;
    if (res.data.tierUp && res.data.tier === 2) sawTier2Up = true;
    final = res;
    // 第 10 回合存一章
    if (res.data.turn === 10) {
      const chapterFile = path.join(base, 'chapter-a.md');
      writeFileSync(chapterFile, '潮水第一次替你说话。\n', 'utf8');
      const ch = cli(base, 'chapter-add', '--title', '潮声初闻', '--file', chapterFile);
      assert.equal(ch.ok, true, JSON.stringify(ch.error));
      assert.equal(ch.data.chapter.index, 1, JSON.stringify(ch));
      assert.equal(ch.data.chapter.endTurn, 10, JSON.stringify(ch));
    }
  }
  assert.ok(sawTierUp, '阶层 1 跃迁必须真实发生（宪章 §5）');
  assert.ok(sawTier2Up, '阶层 2 跃迁必须真实发生');
  assert.ok(final!.data.ended, '胜利终局必须被引擎判定');
  assert.match(final!.data.ended.reason, /胜利/);
  assert.ok(final!.data.turn <= 22, '15-20 回合量级可达阶层跃迁与终局');

  // 4b. 到达阶层 2 后，Lazy Expansion 规则触发待物化（C1：expand 命令的触发面）
  const st = cli(base, 'status');
  assert.equal(st.ok, true, JSON.stringify(st.error));
  assert.equal(st.data.tier, 2);
  assert.ok(
    st.data.pendingExpansions.some((p: { ruleId: string }) => p.ruleId === 'exp-tier2-far'),
    '阶层 2 后 pendingExpansions 必须含 exp-tier2-far（宪章 §7）',
  );

  // 5. 终局后行动被拒
  const after = cli(base, 'act', '--id', 'rest');
  assert.equal(after.ok, false);
  assert.equal(after.error!.code, 'ALREADY_ENDED');

  // 6. 最后一章 + 结束合成小说
  const chapterFile2 = path.join(base, 'chapter-b.md');
  writeFileSync(chapterFile2, '你带着账簿与潮图，走向外锚地。\n', 'utf8');
  const ch2 = cli(base, 'chapter-add', '--title', '外锚在望', '--file', chapterFile2);
  assert.equal(ch2.ok, true, JSON.stringify(ch2.error));

  const end = cli(base, 'end', '--reason', '成为潮制图士');
  assert.equal(end.ok, true, JSON.stringify(end.error));
  const novelPath = path.join(base, end.data.novel);
  assert.ok(existsSync(novelPath), 'novel.md 必须生成');
  const novel = readFileSync(novelPath, 'utf8');
  assert.ok(novel.includes('潮声初闻'), '小说含第一章标题');
  assert.ok(novel.includes('外锚在望'), '小说含第二章标题');
  assert.ok(novel.includes('终章'), '小说含终章');
  assert.ok(novel.includes('大事记'), '小说含可追溯大事记');

  // 7. verify 全绿 + list 可见
  const verify = cli(base, 'verify', '--world', 'echo-harbor');
  assert.equal(verify.ok, true, JSON.stringify(verify.error));
  const list = cli(base, 'list');
  assert.equal(list.ok, true);
  assert.ok(list.data.saves.some((s: { world: string; ended: boolean }) => s.world === 'echo-harbor' && s.ended));
});

test('e2e：observe 只投影玩家已知，知识边界成立（宪章 §7）', () => {
  const base = tmpBase();
  cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'echo-harbor', '--seed', '7');
  const obs = cli(base, 'observe', '--scope', 'trade');
  assert.equal(obs.ok, true);
  assert.equal(obs.data.knownFacts.length, 0, '开局未打听，trade 主题无已知事实');
  assert.ok(obs.data.hiddenInScope > 0, '该主题下存在未知信息（不泄露内容）');
  const laws = cli(base, 'observe', '--scope', 'laws');
  assert.equal(laws.ok, true);
  assert.equal(laws.data.laws.length, 3);
  const status = cli(base, 'status');
  assert.ok(!JSON.stringify(status.data.knownFacts).includes('大潮期货价剧震'), 'hidden 事实不得进入 status 投影');
});
