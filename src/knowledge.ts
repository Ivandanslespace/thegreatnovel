/**
 * 知识边界（宪章 §7）：World Truth ≠ Player Observation。
 *
 * 全部事实 = worldTruth；玩家已知 = playerKnown 投影。
 * status / observe 只投影玩家已知的事实，秘密保持秘密。
 */
import type { Blueprint, Fact, GameState } from './types.ts';

/** 世界真相全集（含玩家尚不知道的事实）。 */
export function worldTruth(blueprint: Blueprint, state: GameState): Fact[] {
  void state;
  return blueprint.facts;
}

/** 玩家当前已知事实投影。 */
export function playerKnown(blueprint: Blueprint, state: GameState): Fact[] {
  const known = new Set(state.knownFacts);
  return blueprint.facts.filter((f) => f.scope === 'player' || known.has(f.id));
}

/** 玩家尚不知道的事实 id（仅供引擎内部/observe 主题列表，不向叙事泄露内容）。 */
export function unknownFactIds(blueprint: Blueprint, state: GameState): string[] {
  const known = new Set(state.knownFacts);
  return blueprint.facts.filter((f) => f.scope === 'hidden' && !known.has(f.id)).map((f) => f.id);
}

/** 把一条世界事实转为玩家已知；返回是否发生了新知识（幂等）。 */
export function learnFact(state: GameState, factId: string): boolean {
  if (state.knownFacts.includes(factId)) return false;
  state.knownFacts.push(factId);
  return true;
}

/** 按主题分组列出玩家已知事实（observe 输出用）。 */
export function knownByCategory(blueprint: Blueprint, state: GameState): Record<string, Fact[]> {
  const result: Record<string, Fact[]> = {};
  for (const fact of playerKnown(blueprint, state)) {
    const key = fact.category ?? 'misc';
    (result[key] ??= []).push(fact);
  }
  return result;
}
