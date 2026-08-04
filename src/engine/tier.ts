// checkTierGate(state) 与 tierUp(state):
// 阶跃到下一层的硬门槛（资产等级 + 知识数 + 相对位置，宪法 §5）；
// 保留成果（absolutePower preserved）、recompute standing、旧层背景化标记、
// zone 由种子确定性展开生成后验证候选再成事实（宪法 §7）。
import type { EngineError, GameEvent, TierGate, WorldState, Zone } from './types.ts';
import { pick as rngPick } from './rng.ts';
import { apply, nextSeq } from './state.ts';
import { MAX_TIER, POWER_PER_ASSET_INVEST, TIER_COHORT_SCALE, TIER_GATES, ZONE_TRAITS } from './balance.ts';

/** 检查当前层到下一层的跃迁门槛。返回是否达标及缺失项码：assetLevel:N / knowledge:N / standing:N / maxTier。 */
export function checkTierGate(state: WorldState): { ok: boolean; missing: string[]; gate: TierGate | null } {
  if (state.tier >= MAX_TIER) return { ok: false, missing: ['maxTier'], gate: null };
  const gate = TIER_GATES[state.tier]; // current tier index → target gate
  const maxLevel = Math.max(0, ...state.player.assets.map((a) => a.level));
  const missing: string[] = [];
  if (maxLevel < gate.minAssetLevel) missing.push(`assetLevel:${gate.minAssetLevel}`);
  if (state.player.knowledge.length < gate.minKnowledge) missing.push(`knowledge:${gate.minKnowledge}`);
  if (state.player.relativeStanding < gate.minStanding) missing.push(`standing:${gate.minStanding}`);
  return { ok: missing.length === 0, missing, gate };
}

export function tierUp(state: WorldState): { ok: true; newState: WorldState; events: GameEvent[] } | { ok: false; error: EngineError } {
  const gate = checkTierGate(state);
  if (!gate.ok) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: 'tier gate not reached', hints: gate.missing } };
  }
  const newTier = state.tier + 1;
  let rng = { seed: state.seed, counter: state.rngCounter };
  const seq = nextSeq(state);

  // Materialize candidate zone by seed expansion (validate before fact, Constitution §7)
  const anchor = state.zones.anchors.length > 0 ? state.zones.anchors[0] : undefined;
  let zone: ZoneCandidate | null = null;
  for (let attempt = 0; attempt < 8 && zone === null; attempt++) {
    const traitRoll = rngPick(rng, ZONE_TRAITS);
    rng = traitRoll.state;
    const candidate: ZoneCandidate = {
      id: `${anchor ?? 'gen'}-t${newTier}`,
      anchorId: anchor || undefined,
      nameKey: `zone.${anchor ?? 'gen'}.t${newTier}`,
      tier: newTier,
      trait: traitRoll.value,
    };
    const clash = state.zones.materialized.some((z) => z.id === candidate.id && z.trait === candidate.trait);
    if (!clash) zone = candidate;
  }
  if (zone === null) return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: 'zone candidate expansion failed', hints: ['zone'] } };

  const payload: TierUpPayload = {
    newTier,
    cohortScale: TIER_COHORT_SCALE,
    zone: { id: zone.id!, anchorId: zone.anchorId, nameKey: zone.nameKey, tier: zone.tier, trait: zone.trait },
    backgroundRule: `backgrounded:tier${state.tier}`,
    rngCounter: rng.counter,
  };
  const event: GameEvent = { seq, turn: state.turn, type: 'TierUp', payload: payload as unknown };
  const newState = apply(state, event);

  return { ok: true, newState, events: [event] };
}

interface TierUpPayload {
  newTier: number;
  cohortScale: number;
  zone: Zone;
  backgroundRule: string;
  rngCounter: number;
}

interface ZoneCandidate {
  id: string;
  anchorId?: string;
  nameKey: string;
  tier: number;
  trait: typeof ZONE_TRAITS[number];
}
