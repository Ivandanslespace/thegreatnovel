/**
 * 种子随机：mulberry32 + FNV-1a。
 *
 * 宪章 §1.1 可重放：所有随机一律由
 *   hash(seed + turn + actionId + seedTag + counter)
 * 派生，禁止 Math.random。同一局同一输入必得同一结果。
 */

/** FNV-1a 32-bit：把任意字符串压成无符号 32 位整数。 */
export function fnv1a(input: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    // FNV prime 0x01000193；用 Math.imul 保证 32 位语义。
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/** mulberry32：由 32 位种子产生 [0,1) 伪随机数的小状态生成器。 */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * 引擎唯一随机入口：由结算上下文确定性派生一个 [0,1) 数值。
 *
 * key 采用无歧义编码：各字段 JSON.stringify 后以 \u0000 拼接，
 * 避免分隔符与字段内容歧义（校验器禁止 id 含 \u0000）。
 */
export function deriveRandom(parts: {
  seed: number | string;
  turn: number;
  actionId: string;
  seedTag: string;
  counter: number;
}): number {
  const key = [parts.seed, parts.turn, parts.actionId, parts.seedTag, parts.counter]
    .map((p) => JSON.stringify(p))
    .join('\u0000');
  return mulberry32(fnv1a(key))();
}

/** 按权重抽签（权重必须为正数；返回选中的索引）。确定性。 */
export function pickWeighted(random: number, weights: number[]): number {
  const total = weights.reduce((s, w) => s + w, 0);
  if (total <= 0) return 0;
  let cursor = random * total;
  for (let i = 0; i < weights.length; i++) {
    cursor -= weights[i] ?? 0;
    if (cursor < 0) return i;
  }
  return weights.length - 1;
}
