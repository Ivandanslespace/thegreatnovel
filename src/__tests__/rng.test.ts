/** rng：确定性、派生纪律（hash(seed+turn+actionId+seedTag+counter)）、禁 Math.random。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { deriveRandom, fnv1a, mulberry32, pickWeighted } from '../rng.ts';

test('fnv1a：相同输入恒定，不同输入不同', () => {
  assert.equal(fnv1a('seed|1|act|tag|0'), fnv1a('seed|1|act|tag|0'));
  assert.notEqual(fnv1a('seed|1|act|tag|0'), fnv1a('seed|1|act|tag|1'));
  assert.ok(fnv1a('x') >= 0 && fnv1a('x') <= 0xffffffff);
});

test('mulberry32：同种子序列确定且落在 [0,1)', () => {
  const a = mulberry32(123);
  const b = mulberry32(123);
  for (let i = 0; i < 50; i++) {
    const x = a();
    assert.equal(x, b());
    assert.ok(x >= 0 && x < 1);
  }
});

test('deriveRandom：同上下文必同结果（可重放，宪章 §1.1）', () => {
  const parts = { seed: 44, turn: 3, actionId: 'trade-run', seedTag: 'trade', counter: 2 };
  assert.equal(deriveRandom(parts), deriveRandom({ ...parts }));
});

test('deriveRandom：counter/turn/seedTag 任一变化都改变结果', () => {
  const base = { seed: 44, turn: 3, actionId: 'trade-run', seedTag: 'trade', counter: 2 };
  const r0 = deriveRandom(base);
  assert.notEqual(r0, deriveRandom({ ...base, counter: 3 }));
  assert.notEqual(r0, deriveRandom({ ...base, turn: 4 }));
  assert.notEqual(r0, deriveRandom({ ...base, seedTag: 'other' }));
  assert.notEqual(r0, deriveRandom({ ...base, seed: 45 }));
});

test('pickWeighted：权重为 0 的结果永不被选中', () => {
  for (let i = 0; i < 100; i++) {
    const r = mulberry32(i)();
    const idx = pickWeighted(r, [0, 1, 0]);
    assert.equal(idx, 1);
  }
});

test('pickWeighted：分布覆盖所有正权重结果', () => {
  const seen = new Set<number>();
  for (let i = 0; i < 1000; i++) {
    seen.add(pickWeighted(mulberry32(i * 7 + 1)(), [1, 1, 1]));
  }
  assert.deepEqual([...seen].sort(), [0, 1, 2]);
});
