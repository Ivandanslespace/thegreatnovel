// 确定性种子 PRNG（mulberry32 混合）。
// 宪法 §1.1：结果的随机差异必须遵循事先存在的条件，关键事实应能从状态与事件重放。
// 因此全局禁止 Math.random 与 Date.now 参与结算；一切随机必须经过本文件。
// 纯函数约定：next(state) 不修改入参，计数器前进 1，返回携带新状态的新对象。

/** 随机状态：seed 为世界种子，counter 为已消耗的抽取次数（存于 WorldState）。 */
export interface RngState {
  seed: number;
  counter: number;
}

export interface RngStep {
  /** [0, 1) 均匀值 */
  value: number;
  /** counter 已前进的新状态（不修改入参） */
  state: RngState;
}

/** mulberry32 单步混合：对 (seed, counter) 的组合做确定性散列。 */
function mix32(n: number): number {
  let t = n | 0;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

/** 纯函数抽取一次 [0,1) 均匀值，counter +1（对 2^32 取模防极端长线溢出）。 */
export function next(state: RngState): RngStep {
  const counter = (state.counter + 1) >>> 0;
  const value = mix32((state.seed | 0) ^ Math.imul(counter, 0x6d2b79f5));
  return { value, state: { seed: state.seed, counter } };
}

/** 伯努利判定：以概率 p 命中。 */
export function chance(state: RngState, p: number): { value: boolean; state: RngState } {
  const step = next(state);
  return { value: step.value < p, state: step.state };
}

/** 从 items 均匀选取一项（调用方保证非空）。 */
export function pick<T>(state: RngState, items: readonly T[]): { value: T; state: RngState } {
  const step = next(state);
  const index = Math.min(items.length - 1, Math.floor(step.value * items.length));
  return { value: items[index], state: step.state };
}

/** [min, max] 闭区间均匀整数。 */
export function roll(state: RngState, min: number, max: number): { value: number; state: RngState } {
  const step = next(state);
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  return { value: lo + Math.floor(step.value * (hi - lo + 1)), state: step.state };
}

/**
 * [base-spread, base+spread] 内的三角分布整数：靠近 base 的结果更常见。
 * 用于收益结算（宪法 §1.1：风险是可知分布，不是任意惩罚）。spread=0 时返回 base。
 */
export function distribution(state: RngState, base: number, spread: number): { value: number; state: RngState } {
  const a = next(state);
  const b = next(a.state);
  const mid = (a.value + b.value) / 2; // 两次均匀值均值 → 以 0.5 为中心的三角分布
  const raw = base + (mid * 2 - 1) * Math.abs(spread);
  return { value: Math.round(raw), state: b.state };
}
