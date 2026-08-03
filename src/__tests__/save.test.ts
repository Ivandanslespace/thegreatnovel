/** save：原子写、备份、SHA-256 篡改检测、schemaVersion 迁移、verify。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import {
  applyMigrations,
  freezeBlueprint,
  initState,
  loadState,
  saveState,
  sha256,
  verifySave,
  listSaves,
} from '../save.ts';
import { loadEchoBlueprint, tmpBase } from './helpers.ts';

async function setup(): Promise<{ base: string }> {
  const base = tmpBase();
  const bp = loadEchoBlueprint();
  await freezeBlueprint(base, 'w1', bp);
  await saveState(base, initState(bp, 'w1', 44));
  return { base };
}

test('保存后可读回，且生成校验和与备份前置状态', async () => {
  const { base } = await setup();
  const state = await loadState(base, 'w1');
  assert.equal(state.world, 'w1');
  assert.equal(state.seed, 44);
  const raw = await readFile(path.join(base, 'saves', 'w1', 'state.json'), 'utf8');
  const checksum = await readFile(path.join(base, 'saves', 'w1', 'state.json.sha256'), 'utf8');
  assert.equal(checksum.trim(), sha256(raw));
});

test('第二次保存产生 state.prev.json 备份', async () => {
  const { base } = await setup();
  const state = await loadState(base, 'w1');
  state.turn = 7;
  await saveState(base, state);
  const prev = await readFile(path.join(base, 'saves', 'w1', 'state.prev.json'), 'utf8');
  assert.equal(JSON.parse(prev).turn, 0, '备份保存的是修改前的状态');
});

test('verify：干净存档通过', async () => {
  const { base } = await setup();
  const result = await verifySave(base, 'w1');
  assert.equal(result.ok, true, result.problems.join('; '));
});

test('verify：篡改 state.json 被 SHA-256 检出', async () => {
  const { base } = await setup();
  const file = path.join(base, 'saves', 'w1', 'state.json');
  const tampered = JSON.parse(await readFile(file, 'utf8'));
  tampered.assets.credential = 9999; // 作弊改资产
  await writeFile(file, JSON.stringify(tampered, null, 2), 'utf8');
  const result = await verifySave(base, 'w1');
  assert.equal(result.ok, false);
  assert.ok(result.problems.some((p) => p.includes('篡改')), result.problems.join('; '));
});

test('verify：删除校验和文件被检出', async () => {
  const { base } = await setup();
  await writeFile(path.join(base, 'saves', 'w1', 'state.json.sha256'), 'deadbeef', 'utf8');
  const result = await verifySave(base, 'w1');
  assert.equal(result.ok, false);
  assert.ok(result.problems.some((p) => p.includes('篡改')));
});

test('verify：schemaVersion 过新与篡改分开表述（C2）', async () => {
  const { base } = await setup();
  const file = path.join(base, 'saves', 'w1', 'state.json');
  const raw = JSON.parse(await readFile(file, 'utf8'));
  raw.schemaVersion = 99;
  const content = JSON.stringify(raw, null, 2);
  await writeFile(file, content, 'utf8');
  await writeFile(`${file}.sha256`, sha256(content), 'utf8'); // 校验和合法但版本过新
  const result = await verifySave(base, 'w1');
  assert.equal(result.ok, false);
  assert.ok(result.problems.some((p) => p.includes('版本过新')), result.problems.join('; '));
  assert.ok(!result.problems.some((p) => p.includes('篡改')), '版本问题不得误报为篡改');
});

test('verify：版本过旧报告需迁移而非篡改（C2）', async () => {
  const { base } = await setup();
  const file = path.join(base, 'saves', 'w1', 'state.json');
  const raw = JSON.parse(await readFile(file, 'utf8'));
  raw.schemaVersion = 1;
  const content = JSON.stringify(raw, null, 2);
  await writeFile(file, content, 'utf8');
  await writeFile(`${file}.sha256`, sha256(content), 'utf8');
  const result = await verifySave(base, 'w1');
  assert.equal(result.ok, false);
  assert.ok(result.problems.some((p) => p.includes('迁移')), result.problems.join('; '));
});

test('verify：空校验和文件视同缺失（M4）', async () => {
  const { base } = await setup();
  await writeFile(path.join(base, 'saves', 'w1', 'state.json.sha256'), '', 'utf8');
  const result = await verifySave(base, 'w1');
  assert.equal(result.ok, false);
  assert.ok(result.problems.some((p) => p.includes('为空')), result.problems.join('; '));
});

test('迁移：v1 → v2 链式前向迁移，history 数组移除并换算游标（C2/M8）', async () => {
  const { base } = await setup();
  const file = path.join(base, 'saves', 'w1', 'state.json');
  const v1 = JSON.parse(await readFile(file, 'utf8'));
  v1.schemaVersion = 1;
  delete v1.historyCount;
  delete v1.historyLastTurn;
  v1.history = [
    { turn: 0, kind: 'system', text: '开局', visible: true, source: 'engine' },
    { turn: 3, kind: 'action', text: '行动', visible: true, source: 'action:rest' },
  ];
  await writeFile(file, JSON.stringify(v1, null, 2), 'utf8');

  // 内存层：迁移链产出 v2 结构
  const { state, migrated } = applyMigrations(v1);
  assert.equal(migrated, true);
  assert.equal(state.schemaVersion, 2);
  assert.equal((state as unknown as Record<string, unknown>).history, undefined, '内嵌 history 数组被移除');
  assert.equal(state.historyCount, 2, '游标由内嵌长度换算');
  assert.equal(state.historyLastTurn, 3);

  // IO 层：loadState 自动迁移并回写落盘（幂等）
  const loaded = await loadState(base, 'w1');
  assert.equal(loaded.schemaVersion, 2);
  assert.equal(loaded.historyCount, 2);
  const persisted = JSON.parse(await readFile(file, 'utf8'));
  assert.equal(persisted.schemaVersion, 2, '迁移结果回写落盘');
  assert.equal(persisted.history, undefined);
});

test('迁移：未来版本硬拒，不得静默降级', async () => {
  assert.throws(() => applyMigrations({ schemaVersion: 99 }), /版本过新/);
});

test('list：损坏/待迁移存档报告状态而非隐藏（C2）', async () => {
  const { base } = await setup();
  const dir = path.join(base, 'saves');
  // 待迁移存档
  const v1File = path.join(dir, 'w1', 'state.json');
  const v1 = JSON.parse(await readFile(v1File, 'utf8'));
  v1.schemaVersion = 1;
  await writeFile(v1File, JSON.stringify(v1, null, 2), 'utf8');
  // 损坏存档（非 JSON）
  const { mkdir } = await import('node:fs/promises');
  await mkdir(path.join(dir, 'broken'), { recursive: true });
  await writeFile(path.join(dir, 'broken', 'state.json'), '{not json', 'utf8');
  // 未来版本存档
  const { freezeBlueprint: ff, saveState: ss, initState: ii } = await import('../save.ts');
  await ff(base, 'future', loadEchoBlueprint());
  const futureState = ii(loadEchoBlueprint(), 'future', 1);
  futureState.schemaVersion = 99;
  await ss(base, futureState);

  const saves = await listSaves(base);
  const byWorld = new Map(saves.map((s) => [s.world, s]));
  assert.equal(byWorld.get('w1')?.status, 'needs-migration', 'v1 存档报告待迁移而非被隐藏');
  assert.equal(byWorld.get('broken')?.status, 'corrupt', '损坏存档报告状态而非被隐藏');
  assert.equal(byWorld.get('future')?.status, 'future-version');
});

test('list：列出存档与进度', async () => {
  const { base } = await setup();
  const saves = await listSaves(base);
  assert.equal(saves.length, 1);
  assert.equal(saves[0]!.world, 'w1');
  assert.equal(saves[0]!.turn, 0);
  assert.equal(saves[0]!.ended, false);
});
