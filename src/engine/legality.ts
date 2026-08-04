// 合法行动列表：给定 state + 行动表，返回每项的合法性及 missing 原因；
// 杠杆物化（宪法 §3）：若玩家 focus>0，附加 revealed 风险-收益分布；
// NPC 决策路径永远拿不到 revealed（信息边界）。

import type { ActionDef, LegalAction, RevealedInfo, WorldState } from './types.ts';
import { ASSET_CONVERSION_BONUS, KNOWLEDGE_CONVERSION_BONUS } from './balance.ts';

export function maxAssetLevel(state: WorldState): number {
  return Math.max(0, ...state.player.assets.map((a) => a.level));
}

/** 转化系数 = 1 + 资产等级加成 + 知识数量加成（可积累复利，宪法 §4）。 */
export function conversionMultiplier(state: WorldState, action: ActionDef): number {
  const maxAssetLevelVal = maxAssetLevel(state);
  const satisfiedKnowledge = action.requires.knowledge?.filter((k) => state.player.knowledge.includes(k)).length ?? 0;
  return 1 + ASSET_CONVERSION_BONUS * maxAssetLevelVal + KNOWLEDGE_CONVERSION_BONUS * satisfiedKnowledge;
}

/** 检查要求未满足项。返回错误码：tier:N / knowledge:K / assetLevel:N / resources:R / focus / standing:N / unlock:U。 */
export function checkRequirements(state: WorldState, action: ActionDef): string[] {
  const missing: string[] = [];
  const req = action.requires;
  if ((req.tier ?? 0) > state.tier) missing.push(`tier:${req.tier}`);
  for (const k of req.knowledge ?? []) {
    if (!state.player.knowledge.includes(k)) missing.push(`knowledge:${k}`);
  }
  for (const u of req.unlocks ?? []) {
    if (!(state.unlocks ?? []).includes(u)) missing.push(`unlock:${u}`);
  }
  if ((req.assetLevel ?? 0) > maxAssetLevel(state)) missing.push(`assetLevel:${req.assetLevel}`);
  // cost affordance 与 require resources
  for (const [res, amt] of Object.entries(req.resources ?? {})) {
    if ((state.player.resources[res] ?? 0) < amt) missing.push(`resources:${res}`);
  }
  for (const [res, amt] of Object.entries(action.costs.resources ?? {})) {
    if ((state.player.resources[res] ?? 0) < amt) missing.push(`resources:${res}`);
  }
  if ((action.costs.focus ?? 0) > state.player.focus) missing.push('focus');
  return [...new Set(missing)];
}

/** 列出所有行动的合法性。杠杆物化（宪法 §3）：focus>0 且行动合法时附加 revealed 完整风险-收益分布；focus=0 盲选降级。NPC 决策路径永远拿不到 revealed。 */
export function listActions(state: WorldState, table: ActionDef[]): LegalAction[] {
  return table.map((a) => {
    const missing = checkRequirements(state, a);
    const legal = missing.length === 0;
    let revealed: RevealedInfo | undefined;
    if (legal && state.player.focus > 0 && a.risk.base > 0) {
      const mult = conversionMultiplier(state, a);
      revealed = {
        expectedYield: Math.round(a.risk.base * mult),
        downsidePct: Math.round((a.risk.spread / Math.max(1, a.risk.base)) * 100),
        hiddenTag: a.risk.hiddenTag,
      };
    }
    return {
      id: a.id,
      label: a.label,
      timeCost: a.timeCost,
      costs: a.costs,
      risk: a.risk,
      legal,
      missing,
      revealed,
    };
  });
}
