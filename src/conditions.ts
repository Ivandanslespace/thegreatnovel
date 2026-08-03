/**
 * 通用条件求值：唯一条件语言。
 *
 * 所有 requires / gate / trigger / leverage 前置共用同一求值器，
 * 保证"规则对所有人一致"（宪章 §1）。
 */
import type { Condition, GameState, Blueprint } from './types.ts';

export interface EvalContext {
  assets: Record<string, number>;
  knownFacts: string[];
  flags: Record<string, boolean>;
  turn: number;
  tier: number;
}

/** 从运行时状态构造求值上下文。 */
export function contextFromState(state: GameState): EvalContext {
  return {
    assets: state.assets,
    knownFacts: state.knownFacts,
    flags: state.flags,
    turn: state.turn,
    tier: state.tier,
  };
}

/** 求值单条条件。未知条件形态一律为 false（保守拒绝，宪章 §9）。 */
export function evalCondition(cond: Condition | undefined, ctx: EvalContext): boolean {
  if (cond === undefined) return true;

  if ('and' in cond) {
    // 防御：畸形数据（非数组）按未满足处理，不崩溃（M6 同类思路）。
    return Array.isArray(cond.and) && cond.and.every((c) => evalCondition(c, ctx));
  }
  if ('or' in cond) {
    return Array.isArray(cond.or) && cond.or.length > 0 && cond.or.some((c) => evalCondition(c, ctx));
  }
  if ('asset' in cond) {
    const value = ctx.assets[cond.asset] ?? 0;
    if (cond.gte !== undefined && value < cond.gte) return false;
    if (cond.lte !== undefined && value > cond.lte) return false;
    return true;
  }
  if ('fact' in cond) {
    return ctx.knownFacts.includes(cond.fact);
  }
  if ('flag' in cond) {
    return ctx.flags[cond.flag] === true;
  }
  if ('window' in cond) {
    const { gte, lte } = cond.window;
    if (gte !== undefined && ctx.turn < gte) return false;
    if (lte !== undefined && ctx.turn > lte) return false;
    return true;
  }
  if ('tier' in cond) {
    if (cond.tier.gte !== undefined && ctx.tier < cond.tier.gte) return false;
    if (cond.tier.lte !== undefined && ctx.tier > cond.tier.lte) return false;
    return true;
  }
  return false;
}

/** 求值条件数组（隐含 and）。 */
export function evalAll(conds: Condition[] | undefined, ctx: EvalContext): boolean {
  if (!conds || conds.length === 0) return true;
  return conds.every((c) => evalCondition(c, ctx));
}

/** 给 Agent 的人类可读未满足原因（结构化硬拒的素材）。 */
export function explainUnmet(conds: Condition[] | undefined, ctx: EvalContext, blueprint: Blueprint): string[] {
  const reasons: string[] = [];
  if (!conds) return reasons;
  for (const c of conds) {
    if (!evalCondition(c, ctx)) reasons.push(explainOne(c, ctx, blueprint));
  }
  return reasons;
}

function explainOne(cond: Condition, ctx: EvalContext, blueprint: Blueprint): string {
  if ('and' in cond) {
    return cond.and
      .filter((c) => !evalCondition(c, ctx))
      .map((c) => explainOne(c, ctx, blueprint))
      .join(' 且 ');
  }
  if ('or' in cond) {
    return `以下至少满足一项：${cond.or.map((c) => explainOne(c, ctx, blueprint)).join(' / ')}`;
  }
  if ('asset' in cond) {
    const type = blueprint.assetTypes.find((a) => a.id === cond.asset);
    const name = type ? type.name : cond.asset;
    const have = ctx.assets[cond.asset] ?? 0;
    if (cond.gte !== undefined && have < cond.gte) return `${name}不足（现有 ${have}，需要 ≥${cond.gte}）`;
    if (cond.lte !== undefined && have > cond.lte) return `${name}过多（现有 ${have}，需要 ≤${cond.lte}）`;
    return `${name}条件不满足`;
  }
  if ('fact' in cond) {
    const fact = blueprint.facts.find((f) => f.id === cond.fact);
    return `尚不知道：${fact ? fact.description : cond.fact}`;
  }
  if ('flag' in cond) {
    return `条件未成立：${cond.flag}`;
  }
  if ('window' in cond) {
    const { gte, lte } = cond.window;
    if (gte !== undefined && lte !== undefined) return `窗口未开启（回合 ${gte}–${lte}，当前 ${ctx.turn}）`;
    if (gte !== undefined) return `窗口未开启（回合 ≥${gte}，当前 ${ctx.turn}）`;
    if (lte !== undefined) return `窗口已关闭（回合 ≤${lte}，当前 ${ctx.turn}）`;
    return '窗口条件不满足';
  }
  if ('tier' in cond) {
    return `阶层条件不满足（当前阶层 ${ctx.tier}）`;
  }
  return '未知条件不满足';
}
