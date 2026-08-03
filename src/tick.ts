/**
 * 世界行动权（宪章 §1.2、§7）：玩家花掉时间时，世界也获得行动权。
 *
 * 每个回合推进：维护结算 → 宏观规律生效 → 势力计划到期结算 → 定时事件结算。
 * 离屏后果记入 history；不可见后果玩家后续可发现"这件事发生时我不在场"。
 *
 * M10：law.effect 语义收紧——规律效果只允许 setFlag/clearFlag（窗口开关）；
 * 资产类后果属于世界过程，必须走 scheduledEvents 或 actor plans（校验器强制）。
 */
import type { Blueprint, Consequence, Effect, GameState } from './types.ts';
import { contextFromState, evalCondition } from './conditions.ts';
import { learnFact } from './knowledge.ts';

/** 应用一组效果到状态；每条效果产生一条后果记录。 */
export function applyEffects(
  bp: Blueprint,
  state: GameState,
  effects: Effect[],
  source: string,
  consequences: Consequence[],
  visible: boolean,
): void {
  for (const effect of effects) {
    if ('asset' in effect) {
      const before = state.assets[effect.asset] ?? 0;
      state.assets[effect.asset] = before + effect.delta;
      const type = bp.assetTypes.find((a) => a.id === effect.asset);
      const name = type ? type.name : effect.asset;
      const sign = effect.delta >= 0 ? '+' : '';
      consequences.push({
        kind: 'outcome',
        text: `${name} ${sign}${effect.delta}（现 ${state.assets[effect.asset]}）`,
        visible,
        source,
      });
    } else if ('learnFact' in effect) {
      const fact = bp.facts.find((f) => f.id === effect.learnFact);
      if (learnFact(state, effect.learnFact)) {
        consequences.push({
          kind: 'outcome',
          text: `你得知：${fact ? fact.description : effect.learnFact}`,
          visible: true,
          source,
        });
      }
    } else if ('setFlag' in effect) {
      if (!state.flags[effect.setFlag]) {
        state.flags[effect.setFlag] = true;
        consequences.push({ kind: 'outcome', text: `世界状态变化：${effect.setFlag}`, visible, source });
      }
    } else if ('clearFlag' in effect) {
      if (state.flags[effect.clearFlag]) {
        state.flags[effect.clearFlag] = false;
        consequences.push({ kind: 'outcome', text: `世界状态变化：${effect.clearFlag} 结束`, visible, source });
      }
    } else if ('unlockRegion' in effect) {
      if (!state.unlockedRegions.includes(effect.unlockRegion)) {
        state.unlockedRegions.push(effect.unlockRegion);
        const region = bp.regions.find((r) => r.id === effect.unlockRegion);
        consequences.push({
          kind: 'outcome',
          text: `新区域可达：${region ? region.name : effect.unlockRegion}`,
          visible,
          source,
        });
      }
    }
  }
}

export interface TickResult {
  consequences: Consequence[];
}

/** 维护成本结算（长期资产带责任，宪章 §4.1）。每回合一次（M3：在 worldTick 内结算）。 */
export function settleMaintenance(bp: Blueprint, state: GameState, consequences: Consequence[]): void {
  for (const type of bp.assetTypes) {
    if (!type.maintenance) continue;
    const held = state.assets[type.id] ?? 0;
    if (held <= 0) continue; // 未持有该长期资产则无维护责任
    const cost = type.maintenance.perTurn;
    if (cost <= 0) continue;
    state.assets[type.maintenance.asset] = (state.assets[type.maintenance.asset] ?? 0) - cost;
    consequences.push({
      kind: 'maintenance',
      text: `维护「${type.name}」消耗 ${bp.assetTypes.find((a) => a.id === type.maintenance!.asset)?.name ?? type.maintenance.asset} -${cost}`,
      visible: true,
      source: `maintenance:${type.id}`,
    });
  }
}

/** 推进一个回合（turn +1），结算维护/规律/势力计划/定时事件。 */
export function worldTick(bp: Blueprint, state: GameState): TickResult {
  state.turn += 1;
  const consequences: Consequence[] = [];
  const ctx = contextFromState(state);

  // 0. 维护结算：每回合一次，消除"perTurn 却按行动结算"的语义矛盾（M3）。
  settleMaintenance(bp, state, consequences);

  // 1. 宏观规律：trigger 命中则落实其效果（窗口开启）；
  //    trigger 失效则撤销其 setFlag（窗口关闭，宪章 §6 机会窗口有开有关）。
  for (const law of bp.laws) {
    if (!law.trigger || !law.effect || law.effect.length === 0) continue;
    if (evalCondition(law.trigger, ctx)) {
      applyEffects(bp, state, law.effect, `law:${law.id}`, consequences, true);
    } else {
      const reversing: Effect[] = law.effect
        .filter((e): e is Extract<Effect, { setFlag: string }> => 'setFlag' in e)
        .map((e) => ({ clearFlag: e.setFlag }));
      if (reversing.length > 0) {
        applyEffects(bp, state, reversing, `law:${law.id}`, consequences, true);
      }
    }
  }

  // 2. 势力计划：到期结算一次（V1 计划表驱动，非自主模拟）。
  for (const actor of bp.actors) {
    for (const plan of actor.plans) {
      if (state.plansFired.includes(plan.id)) continue;
      if (evalCondition(plan.trigger, ctx)) {
        state.plansFired.push(plan.id);
        applyEffects(bp, state, plan.effects, `actor:${actor.id}/${plan.id}`, consequences, plan.visible ?? false);
        consequences.push({
          kind: 'tick',
          text: plan.description,
          visible: plan.visible ?? false,
          source: `actor:${actor.id}`,
        });
      }
    }
  }

  // 3. 定时事件。
  for (const event of bp.scheduledEvents ?? []) {
    if (state.eventsFired.includes(event.id)) continue;
    if (evalCondition(event.trigger, ctx)) {
      state.eventsFired.push(event.id);
      applyEffects(bp, state, event.effects, `event:${event.id}`, consequences, event.visible ?? false);
      consequences.push({
        kind: 'tick',
        text: event.description,
        visible: event.visible ?? false,
        source: `event:${event.id}`,
      });
    }
  }

  // 回合归因：本回合产生的一切后果标记实际回合（minor）。
  for (const c of consequences) c.atTurn = state.turn;
  return { consequences };
}
