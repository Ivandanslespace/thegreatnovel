/**
 * Lazy Expansion（宪章 §7）：尚未物化的远方内容不得假称已在离屏完整模拟。
 *
 * 引擎职责：检查 expansion 规则的触发条件；新内容必须先成为"经验证的候选"，
 * 满足 constraints（不与既有事实冲突、控制力来源与 controlAxis 一致）后才能
 * 成为世界事实。物化不得追溯修改既有事实。
 */
import type { Blueprint, GameState } from './types.ts';
import { contextFromState, evalCondition } from './conditions.ts';

export interface ExpansionCandidate {
  ruleId: string;
  description: string;
  constraints: string[];
}

/** 返回当前已触发、等待候选内容物化的 expansion 规则。 */
export function checkExpansion(bp: Blueprint, state: GameState): ExpansionCandidate[] {
  const ctx = contextFromState(state);
  const candidates: ExpansionCandidate[] = [];
  for (const rule of bp.expansion) {
    if (evalCondition(rule.trigger, ctx)) {
      candidates.push({ ruleId: rule.id, description: rule.description, constraints: rule.constraints });
    }
  }
  return candidates;
}

export interface CandidateContent {
  id: string;
  description: string;
}

export interface CandidateValidation {
  ok: boolean;
  problems: string[];
}

/**
 * 候选内容入库前校验：
 * 1. 不得与既有事实/区域 id 冲突（不追溯修改既有事实）；
 * 2. 描述必须非空（有名字与约束，宪章 §7 远方锚点）；
 * 3. 触发规则必须已处于触发状态（合法触发，不迎合当下答案）。
 */
export function validateCandidate(
  bp: Blueprint,
  state: GameState,
  ruleId: string,
  candidate: CandidateContent,
): CandidateValidation {
  const problems: string[] = [];
  const rule = bp.expansion.find((r) => r.id === ruleId);
  if (!rule) problems.push(`expansion 规则 "${ruleId}" 不存在`);
  else if (!evalCondition(rule.trigger, contextFromState(state))) {
    problems.push(`expansion 规则 "${ruleId}" 尚未触发，物化不合法`);
  }
  if (!candidate.id.trim()) problems.push('候选内容缺少 id');
  if (!candidate.description.trim()) problems.push('候选内容缺少描述');
  if (bp.facts.some((f) => f.id === candidate.id)) problems.push(`事实 id "${candidate.id}" 已存在，物化不得覆盖既有事实`);
  if (bp.regions.some((r) => r.id === candidate.id)) problems.push(`区域 id "${candidate.id}" 已存在，物化不得覆盖既有区域`);
  return { ok: problems.length === 0, problems };
}

/**
 * 把通过校验的候选事实物化进（存档内冻结的）Blueprint。
 * 仅追加、绝不修改既有条目；调用方负责随后保存 blueprint 与 state。
 */
export function materializeFact(bp: Blueprint, candidate: CandidateContent & { category?: string; anchorTier?: number }): void {
  bp.facts.push({
    id: candidate.id,
    description: candidate.description,
    scope: 'hidden',
    ...(candidate.category !== undefined ? { category: candidate.category } : {}),
    ...(candidate.anchorTier !== undefined ? { anchor: { tier: candidate.anchorTier } } : {}),
  });
}
