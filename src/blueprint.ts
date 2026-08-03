/**
 * Blueprint 加载 + 校验（宪章守门人）。
 *
 * 拒绝：引用悬空、负成本、无 seedTag 的随机、leverage 未绑定 law、
 * designCheck 缺失/空白、id 冲突等，返回逐条结构化错误。
 */
import { readFile } from 'node:fs/promises';
import { BLUEPRINT_SCHEMA_VERSION } from './types.ts';
import type { Blueprint, Condition, Effect } from './types.ts';
import { isLanguage, SUPPORTED_LANGUAGES } from './i18n.ts';

export interface BlueprintIssue {
  path: string;
  code: string;
  message: string;
}

export interface ValidationResult {
  ok: boolean;
  issues: BlueprintIssue[];
}

const DESIGN_CHECK_KEYS = [
  'controlGap',
  'legibleRule',
  'leverageConversion',
  'compounding',
  'opportunityCost',
  'worldFeedback',
  'portability',
] as const;

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/** 校验一个 Blueprint JSON（世界无关的结构性 + 宪章相关检查）。 */
export function validateBlueprint(input: unknown): ValidationResult {
  const issues: BlueprintIssue[] = [];
  const issue = (path: string, code: string, message: string) => issues.push({ path, code, message });

  if (!isRecord(input)) {
    issue('$', 'NOT_OBJECT', 'Blueprint 必须是 JSON 对象');
    return { ok: false, issues };
  }
  const bp = input as Partial<Blueprint>;

  // ---- 顶层结构与 schemaVersion ----
  if (bp.schemaVersion !== BLUEPRINT_SCHEMA_VERSION) {
    issue('schemaVersion', 'SCHEMA_VERSION', `schemaVersion 必须为 ${BLUEPRINT_SCHEMA_VERSION}（实际 ${JSON.stringify(bp.schemaVersion)}）`);
  }
  for (const key of ['meta', 'designCheck', 'laws', 'assetTypes', 'actions', 'leverage', 'actors', 'facts', 'regions', 'tiers', 'expansion', 'winLose'] as const) {
    if (bp[key] === undefined) issue(key, 'MISSING_FIELD', `缺少顶层字段 ${key}`);
  }
  if (issues.length > 0) return { ok: false, issues };

  // ---- section 类型守卫（M6）：畸形类型逐条 issue，而非 TypeError ----
  const objectSections = ['meta', 'leverage', 'winLose'] as const;
  for (const key of objectSections) {
    if (!isRecord(bp[key])) {
      issue(key, 'TYPE', `${key} 必须是 JSON 对象`);
    }
  }
  const arraySections = ['laws', 'assetTypes', 'actions', 'actors', 'facts', 'regions', 'tiers', 'expansion'] as const;
  for (const key of arraySections) {
    if (!Array.isArray(bp[key])) {
      issue(key, 'TYPE', `${key} 必须是数组`);
    }
  }
  if (bp.scheduledEvents !== undefined && !Array.isArray(bp.scheduledEvents)) {
    issue('scheduledEvents', 'TYPE', 'scheduledEvents 必须是数组');
  }
  if (issues.length > 0) return { ok: false, issues };

  const meta = bp.meta!;
  const designCheck = bp.designCheck!;
  const laws = bp.laws!;
  const assetTypes = bp.assetTypes!;
  const actions = bp.actions!;
  const leverage = bp.leverage!;
  const actors = bp.actors!;
  const facts = bp.facts!;
  const regions = bp.regions!;
  const tiers = bp.tiers!;
  const expansion = bp.expansion!;
  const winLose = bp.winLose!;
  const scheduledEvents = bp.scheduledEvents ?? [];

  // ---- meta ----
  if (!meta.name?.trim()) issue('meta.name', 'EMPTY', '世界名不能为空');
  if (!meta.prompt?.trim()) issue('meta.prompt', 'EMPTY', '玩家一句话世界描述不能为空');
  if (!meta.controlAxis?.trim()) issue('meta.controlAxis', 'EMPTY', 'controlAxis（控制力来源轴）不能为空（宪章 §2）');
  if (typeof meta.seed !== 'number' || !Number.isFinite(meta.seed)) issue('meta.seed', 'TYPE', 'seed 必须是有限数字');
  // V1.1：language 可选（缺省按 zh 处理），出现时必须是受支持的语言代码。
  if (meta.language !== undefined && !isLanguage(meta.language)) {
    issue('meta.language', 'INVALID_LANGUAGE', `language 必须是 ${SUPPORTED_LANGUAGES.join(' / ')} 之一（实际 ${JSON.stringify(meta.language)}）`);
  }

  // ---- designCheck：宪章 §12 七问必填非空 ----
  if (!isRecord(designCheck)) {
    issue('designCheck', 'TYPE', 'designCheck 必须是对象');
  } else {
    for (const key of DESIGN_CHECK_KEYS) {
      const value = (designCheck as Record<string, unknown>)[key];
      if (typeof value !== 'string' || value.trim().length === 0) {
        issue(`designCheck.${key}`, 'DESIGN_CHECK_EMPTY', `宪章 §12 最小检查问题 ${key} 必须作答且非空`);
      }
    }
  }

  // ---- id 冲突 ----
  const checkUnique = (items: { id?: unknown }[], path: string) => {
    const seen = new Map<string, number>();
    items.forEach((item, i) => {
      const id = typeof item.id === 'string' ? item.id : '';
      if (!id) {
        issue(`${path}[${i}].id`, 'MISSING_ID', `${path}[${i}] 缺少 id`);
        return;
      }
      // minor：id 含 \u0000 会与随机 key 的无歧义编码冲突。
      if (id.includes('\u0000')) {
        issue(`${path}[${i}].id`, 'BAD_ID', `${path}[${i}] 的 id 不得包含控制字符 \\u0000`);
        return;
      }
      const count = (seen.get(id) ?? 0) + 1;
      seen.set(id, count);
      if (count === 2) issue(path, 'ID_CONFLICT', `${path} 中 id "${id}" 重复`);
    });
  };
  checkUnique(laws, 'laws');
  checkUnique(assetTypes, 'assetTypes');
  checkUnique(actions, 'actions');
  checkUnique(actors, 'actors');
  checkUnique(facts, 'facts');
  checkUnique(regions, 'regions');
  checkUnique(expansion, 'expansion');
  checkUnique(scheduledEvents, 'scheduledEvents');
  {
    const seen = new Map<number, number>();
    tiers.forEach((t, i) => {
      if (typeof t.tier !== 'number') {
        issue(`tiers[${i}].tier`, 'TYPE', 'tier 必须是数字');
        return;
      }
      const count = (seen.get(t.tier) ?? 0) + 1;
      seen.set(t.tier, count);
      if (count === 2) issue('tiers', 'ID_CONFLICT', `tiers 中 tier=${t.tier} 重复`);
      if (!isRecord(t.gate) && !Array.isArray(t.gate)) issue(`tiers[${i}].gate`, 'MISSING_FIELD', '阶层门槛必须有 gate 条件');
    });
    // minor：tiers 必须是 1..n 连续整数（阶层跃迁逐级判定的前提）。
    const tierNumbers = tiers.map((t) => t.tier).filter((x): x is number => typeof x === 'number');
    const distinct = [...new Set(tierNumbers)].sort((a, b) => a - b);
    for (let i = 0; i < distinct.length; i++) {
      if (distinct[i] !== i + 1) {
        issue('tiers', 'NON_CONTIGUOUS', `tiers 必须是 1..n 连续整数（发现 ${distinct.join(', ')}）`);
        break;
      }
    }
  }

  // ---- 已知 id 集合（引用完整性检查用）----
  const assetIds = new Set(assetTypes.map((a) => a.id).filter((x): x is string => typeof x === 'string'));
  const actionIds = new Set(actions.map((a) => a.id).filter((x): x is string => typeof x === 'string'));
  const lawIds = new Set(laws.map((l) => l.id).filter((x): x is string => typeof x === 'string'));
  const factIds = new Set(facts.map((f) => f.id).filter((x): x is string => typeof x === 'string'));
  const regionIds = new Set(regions.map((r) => r.id).filter((x): x is string => typeof x === 'string'));

  // 所有 setFlag 效果产出的 flag 集合（flag 只能来自显式声明）
  const flagIds = new Set<string>();
  const collectFlagsFromEffects = (effects: Effect[] | undefined) => {
    for (const e of effects ?? []) {
      if ('setFlag' in e && typeof e.setFlag === 'string') flagIds.add(e.setFlag);
    }
  };
  for (const law of laws) collectFlagsFromEffects(law.effect);
  for (const action of actions) for (const o of action.outcomes ?? []) collectFlagsFromEffects(o.effects);
  for (const actor of actors) for (const p of actor.plans ?? []) collectFlagsFromEffects(p.effects);
  for (const ev of scheduledEvents) collectFlagsFromEffects(ev.effects);

  // ---- 效果与条件的引用完整性 ----
  const checkEffect = (e: unknown, at: string) => {
    if (!isRecord(e)) {
      issue(at, 'TYPE', '效果必须是对象');
      return;
    }
    if ('asset' in e) {
      if (!assetIds.has(e.asset as string)) issue(`${at}.asset`, 'DANGLING_REF', `效果引用了不存在的资产 "${e.asset}"`);
      if (typeof e.delta !== 'number' || !Number.isFinite(e.delta)) issue(`${at}.delta`, 'TYPE', 'asset 效果需要数字 delta');
    } else if ('learnFact' in e) {
      if (!factIds.has(e.learnFact as string)) issue(`${at}.learnFact`, 'DANGLING_REF', `效果引用了不存在的事实 "${e.learnFact}"`);
    } else if ('setFlag' in e) {
      if (typeof e.setFlag !== 'string' || !(e.setFlag as string).trim()) issue(`${at}.setFlag`, 'EMPTY', 'setFlag 需要非空字符串');
    } else if ('clearFlag' in e) {
      if (!flagIds.has(e.clearFlag as string)) issue(`${at}.clearFlag`, 'DANGLING_REF', `clearFlag 引用了从未被设置的 flag "${e.clearFlag}"`);
    } else if ('unlockRegion' in e) {
      if (!regionIds.has(e.unlockRegion as string)) issue(`${at}.unlockRegion`, 'DANGLING_REF', `效果引用了不存在的区域 "${e.unlockRegion}"`);
    } else {
      issue(at, 'UNKNOWN_EFFECT', `未知效果形态：${Object.keys(e).join(',')}`);
    }
  };

  const checkCondition = (c: unknown, at: string) => {
    if (!isRecord(c)) {
      issue(at, 'TYPE', '条件必须是对象');
      return;
    }
    if ('and' in c) {
      if (!Array.isArray(c.and) || c.and.length === 0) issue(at, 'EMPTY', 'and 条件不能为空');
      else c.and.forEach((sub, i) => checkCondition(sub, `${at}.and[${i}]`));
    } else if ('or' in c) {
      if (!Array.isArray(c.or) || c.or.length === 0) issue(at, 'EMPTY', 'or 条件不能为空');
      else c.or.forEach((sub, i) => checkCondition(sub, `${at}.or[${i}]`));
    } else if ('asset' in c) {
      if (!assetIds.has(c.asset as string)) issue(`${at}.asset`, 'DANGLING_REF', `条件引用了不存在的资产 "${c.asset}"`);
      if (c.gte !== undefined && (typeof c.gte !== 'number' || c.gte < 0)) issue(`${at}.gte`, 'NEGATIVE', '资产阈值 gte 不能为负');
    } else if ('fact' in c) {
      if (!factIds.has(c.fact as string)) issue(`${at}.fact`, 'DANGLING_REF', `条件引用了不存在的事实 "${c.fact}"`);
    } else if ('flag' in c) {
      if (!flagIds.has(c.flag as string)) issue(`${at}.flag`, 'DANGLING_REF', `条件引用了从未被任何效果设置的 flag "${c.flag}"`);
    } else if ('window' in c) {
      const w = c.window as { gte?: unknown; lte?: unknown } | undefined;
      if (!isRecord(w)) issue(`${at}.window`, 'TYPE', 'window 条件需要 {gte?, lte?} 对象');
      else if (w.gte === undefined && w.lte === undefined) issue(`${at}.window`, 'EMPTY', 'window 条件至少需要 gte 或 lte');
    } else if ('tier' in c) {
      if (!isRecord(c.tier)) issue(`${at}.tier`, 'TYPE', 'tier 条件需要 {gte?, lte?} 对象');
    } else {
      issue(at, 'UNKNOWN_CONDITION', `未知条件形态：${Object.keys(c).join(',')}`);
    }
  };

  // ---- laws（M10：effect 只允许 setFlag/clearFlag 的窗口开关）----
  laws.forEach((law, i) => {
    if (!law.description?.trim()) issue(`laws[${i}].description`, 'EMPTY', '规律必须有描述（可理解，宪章 §1）');
    if (law.trigger !== undefined) checkCondition(law.trigger, `laws[${i}].trigger`);
    const effects = law.effect ?? [];
    if (law.trigger === undefined && effects.length > 0) {
      issue(`laws[${i}].effect`, 'INCONSISTENT', '无 trigger 的恒真规律不得带 effect：窗口开关须经 trigger 表达（M10）');
    }
    effects.forEach((e, j) => {
      if (!isRecord(e) || !('setFlag' in e || 'clearFlag' in e)) {
        issue(`laws[${i}].effect[${j}]`, 'LAW_EFFECT_SCOPE', 'law.effect 只允许 setFlag/clearFlag；资产/事实/区域类效果请走 scheduledEvents 或 actor plans（M10）');
        return;
      }
      checkEffect(e, `laws[${i}].effect[${j}]`);
    });
  });

  // ---- assetTypes：维护成本不得为负 ----
  assetTypes.forEach((a, i) => {
    if (!a.name?.trim()) issue(`assetTypes[${i}].name`, 'EMPTY', '资产必须有名称');
    if (typeof a.kind !== 'string' || !a.kind.trim()) issue(`assetTypes[${i}].kind`, 'EMPTY', '资产必须有 kind');
    if (a.maintenance) {
      if (!assetIds.has(a.maintenance.asset)) issue(`assetTypes[${i}].maintenance.asset`, 'DANGLING_REF', `维护成本引用了不存在的资产 "${a.maintenance.asset}"`);
      if (typeof a.maintenance.perTurn !== 'number' || a.maintenance.perTurn < 0) {
        issue(`assetTypes[${i}].maintenance.perTurn`, 'NEGATIVE_COST', '维护成本 perTurn 不能为负（宪章 §4.1 成本必须真实）');
      }
    }
    if (a.initial !== undefined && (typeof a.initial !== 'number' || a.initial < 0)) {
      issue(`assetTypes[${i}].initial`, 'NEGATIVE_COST', '初始资产不能为负');
    }
  });

  // ---- actions：成本/随机/结果 ----
  actions.forEach((a, i) => {
    if (!a.name?.trim()) issue(`actions[${i}].name`, 'EMPTY', '行动必须有名称');
    if (typeof a.tier !== 'number' || a.tier < 0) {
      issue(`actions[${i}].tier`, 'NEGATIVE_COST', '行动 tier 必须为非负整数');
    } else if (a.tier > 0 && !tiers.some((t) => t.tier === a.tier)) {
      issue(`actions[${i}].tier`, 'DANGLING_REF', `行动属于未定义阶层 ${a.tier}（tiers 无此门槛）`);
    }
    if (a.costs) {
      if (a.costs.time !== undefined && (typeof a.costs.time !== 'number' || a.costs.time < 0)) {
        issue(`actions[${i}].costs.time`, 'NEGATIVE_COST', '时间成本不能为负');
      }
      for (const [asset, cost] of Object.entries(a.costs.assets ?? {})) {
        if (!assetIds.has(asset)) issue(`actions[${i}].costs.assets.${asset}`, 'DANGLING_REF', `成本引用了不存在的资产 "${asset}"`);
        if (typeof cost !== 'number' || cost < 0) issue(`actions[${i}].costs.assets.${asset}`, 'NEGATIVE_COST', `资产成本不能为负（实际 ${cost}）`);
      }
    }
    (a.requires ?? []).forEach((c, j) => checkCondition(c, `actions[${i}].requires[${j}]`));
    if (!Array.isArray(a.outcomes) || a.outcomes.length === 0) {
      issue(`actions[${i}].outcomes`, 'EMPTY', '行动至少需要一个结果');
      return;
    }
    // 随机抽签必须有 seedTag（宪章 §1.1 可重放）
    const random = a.outcomes.length > 1 || a.risk !== undefined;
    if (random && (typeof a.risk?.seedTag !== 'string' || a.risk.seedTag.trim().length === 0)) {
      issue(`actions[${i}].risk.seedTag`, 'MISSING_SEEDTAG', `行动 "${a.id}" 含加权抽签但缺少 seedTag（随机必须可重放）`);
    }
    if (a.risk?.chance !== undefined && (a.risk.chance < 0 || a.risk.chance > 1)) {
      issue(`actions[${i}].risk.chance`, 'RANGE', 'risk.chance 必须在 [0,1]');
    }
    const outcomeIds = new Set<string>();
    a.outcomes.forEach((o, j) => {
      if (!o.id || outcomeIds.has(o.id)) issue(`actions[${i}].outcomes[${j}].id`, 'ID_CONFLICT', `行动 "${a.id}" 内结果 id "${o.id}" 重复或缺失`);
      else outcomeIds.add(o.id);
      if (typeof o.weight !== 'number' || o.weight < 0 || !Number.isFinite(o.weight)) {
        issue(`actions[${i}].outcomes[${j}].weight`, 'NEGATIVE_COST', `结果权重必须为非负有限数（实际 ${o.weight}）`);
      }
      if (!o.description?.trim()) issue(`actions[${i}].outcomes[${j}].description`, 'EMPTY', '结果必须有描述');
      (o.effects ?? []).forEach((e, k) => checkEffect(e, `actions[${i}].outcomes[${j}].effects[${k}]`));
      (o.unlocks ?? []).forEach((r) => {
        if (!regionIds.has(r)) issue(`actions[${i}].outcomes[${j}].unlocks`, 'DANGLING_REF', `结果解锁引用了不存在的区域 "${r}"`);
      });
    });
    if (a.outcomes.every((o) => o.weight === 0)) {
      issue(`actions[${i}].outcomes`, 'DEAD_ACTION', `行动 "${a.id}" 所有结果权重为 0，永远无法结算`);
    }
  });

  // ---- leverage：必须绑定 law（宪章 §3.1） ----
  {
    const enabled = leverage.enabled === true;
    if (!leverage.id?.trim()) issue('leverage.id', 'EMPTY', '杠杆必须有 id');
    if (!leverage.description?.trim()) issue('leverage.description', 'EMPTY', '杠杆必须有描述');
    // M11：enabled=false（宪章 §3 检验用途）豁免三项论证必填；数组化杠杆留待 V2。
    if (enabled) {
      if (!Array.isArray(leverage.causalChain) || leverage.causalChain.length === 0) {
        issue('leverage.causalChain', 'LEVERAGE_UNBOUND', '杠杆必须绑定至少一条 law 的因果链（宪章 §3.1）');
      } else {
        leverage.causalChain.forEach((lawId, i) => {
          if (!lawIds.has(lawId)) issue(`leverage.causalChain[${i}]`, 'DANGLING_REF', `杠杆因果链引用了不存在的规律 "${lawId}"`);
        });
      }
      if (!leverage.cost?.trim()) issue('leverage.cost', 'EMPTY', '杠杆必须说明主角付出什么（宪章 §3.1）');
      if (!leverage.whyExclusive?.trim()) issue('leverage.whyExclusive', 'EMPTY', '杠杆必须说明普通人为何难以复制（宪章 §3.1）');
    } else {
      (leverage.causalChain ?? []).forEach((lawId, i) => {
        if (!lawIds.has(lawId)) issue(`leverage.causalChain[${i}]`, 'DANGLING_REF', `杠杆因果链引用了不存在的规律 "${lawId}"`);
      });
    }
    if (typeof leverage.enabled !== 'boolean') issue('leverage.enabled', 'TYPE', 'leverage.enabled 必须是布尔值');
    (leverage.exclusiveActions ?? []).forEach((actionId, i) => {
      const action = actions.find((a) => a.id === actionId);
      if (!action) issue(`leverage.exclusiveActions[${i}]`, 'DANGLING_REF', `独占行动引用了不存在的行动 "${actionId}"`);
      else if (!action.leverageOnly) issue(`leverage.exclusiveActions[${i}]`, 'INCONSISTENT', `行动 "${actionId}" 被声明为杠杆独占，但缺少 leverageOnly=true`);
    });
    for (const action of actions) {
      if (action.leverageOnly && !(leverage.exclusiveActions ?? []).includes(action.id)) {
        issue(`actions[${action.id}]`, 'INCONSISTENT', `行动 "${action.id}" 有 leverageOnly=true 但未列入 leverage.exclusiveActions`);
      }
    }
    (leverage.modifiers ?? []).forEach((m, i) => {
      const action = actions.find((a) => a.id === m.action);
      if (!action) {
        issue(`leverage.modifiers[${i}].action`, 'DANGLING_REF', `modifier 引用了不存在的行动 "${m.action}"`);
        return;
      }
      if (!action.outcomes.some((o) => o.id === m.outcome)) {
        issue(`leverage.modifiers[${i}].outcome`, 'DANGLING_REF', `modifier 引用了行动 "${m.action}" 中不存在的结果 "${m.outcome}"`);
      }
      if (typeof m.setWeight !== 'number' || m.setWeight < 0 || !Number.isFinite(m.setWeight)) {
        issue(`leverage.modifiers[${i}].setWeight`, 'NEGATIVE_COST', 'modifier.setWeight 必须为非负有限数');
      }
      if (m.when !== undefined) checkCondition(m.when, `leverage.modifiers[${i}].when`);
    });
    // modifier 不得杀死行动：覆盖所有 modifier 组合的可达性（M2）。
    for (const action of actions) {
      const mods = (leverage.modifiers ?? []).filter((m) => m.action === action.id);
      if (mods.length === 0) continue;
      // 1) 无条件 modifier 的组合：必然生效，直接算最终权重。
      const unconditional = mods.filter((m) => m.when === undefined);
      const weights = action.outcomes.map((o) => {
        const mod = unconditional.find((m) => m.outcome === o.id);
        return mod ? mod.setWeight : o.weight;
      });
      if (weights.every((w) => w === 0)) {
        issue('leverage.modifiers', 'DEAD_ACTION', `无条件 modifier 将行动 "${action.id}" 的全部结果权重清零`);
        continue;
      }
      // 2) 条件性 modifier：若每个 outcome 都存在可能把它置 0 的 modifier，
      //    则存在某种条件组合使全部权重归零，行动会在运行时被杀死。
      const conditional = mods.filter((m) => m.when !== undefined);
      if (conditional.length === 0) continue;
      const everyOutcomeKillable = action.outcomes.every((o) =>
        o.weight === 0 || conditional.some((m) => m.outcome === o.id && m.setWeight === 0),
      );
      if (everyOutcomeKillable) {
        issue('leverage.modifiers', 'DEAD_ACTION', `条件性 modifier 组合可能在运行时把行动 "${action.id}" 的全部结果权重清零（每个结果都存在置 0 的 modifier）`);
      }
    }
  }

  // ---- actors ----
  actors.forEach((actor, i) => {
    if (!actor.name?.trim()) issue(`actors[${i}].name`, 'EMPTY', '势力必须有名称');
    if (!Array.isArray(actor.goals) || actor.goals.length === 0) issue(`actors[${i}].goals`, 'EMPTY', '势力必须有目标（NPC 不是背景板，宪章 §7）');
    (actor.plans ?? []).forEach((p, j) => {
      checkCondition(p.trigger, `actors[${i}].plans[${j}].trigger`);
      if (!Array.isArray(p.effects) || p.effects.length === 0) issue(`actors[${i}].plans[${j}].effects`, 'EMPTY', '计划必须有效果');
      else p.effects.forEach((e, k) => checkEffect(e, `actors[${i}].plans[${j}].effects[${k}]`));
      if (!p.description?.trim()) issue(`actors[${i}].plans[${j}].description`, 'EMPTY', '计划必须有描述');
    });
  });

  // ---- scheduledEvents ----
  scheduledEvents.forEach((ev, i) => {
    checkCondition(ev.trigger, `scheduledEvents[${i}].trigger`);
    if (!Array.isArray(ev.effects) || ev.effects.length === 0) issue(`scheduledEvents[${i}].effects`, 'EMPTY', '定时事件必须有效果');
    else ev.effects.forEach((e, j) => checkEffect(e, `scheduledEvents[${i}].effects[${j}]`));
  });

  // ---- facts ----
  facts.forEach((f, i) => {
    if (f.scope !== 'player' && f.scope !== 'hidden') issue(`facts[${i}].scope`, 'TYPE', '事实 scope 必须是 player 或 hidden');
    if (!f.description?.trim()) issue(`facts[${i}].description`, 'EMPTY', '事实必须有描述');
    if (f.anchor !== undefined && (typeof f.anchor.tier !== 'number' || f.anchor.tier < 0)) {
      issue(`facts[${i}].anchor.tier`, 'TYPE', '远方锚点需要非负 tier（宪章 §7：仅名字与层级约束，无细节）');
    }
  });

  // ---- regions ----
  regions.forEach((r, i) => {
    if (!r.name?.trim()) issue(`regions[${i}].name`, 'EMPTY', '区域必须有名称');
    if (regions.filter((x) => x.initiallyUnlocked).length === 0 && i === regions.length - 1) {
      issue('regions', 'NO_START', '至少需要一个 initiallyUnlocked 的初始区域');
    }
  });

  // ---- tiers 的 unlocks 引用 ----
  tiers.forEach((t, i) => {
    checkCondition(t.gate, `tiers[${i}].gate`);
    (t.unlocks ?? []).forEach((r) => {
      if (!regionIds.has(r)) issue(`tiers[${i}].unlocks`, 'DANGLING_REF', `阶层解锁引用了不存在的区域 "${r}"`);
    });
  });

  // ---- expansion ----
  expansion.forEach((rule, i) => {
    checkCondition(rule.trigger, `expansion[${i}].trigger`);
    if (!Array.isArray(rule.constraints) || rule.constraints.length === 0) {
      issue(`expansion[${i}].constraints`, 'EMPTY', 'Lazy Expansion 规则必须带约束（宪章 §7）');
    }
  });

  // ---- winLose ----
  if (!winLose.description?.trim()) issue('winLose.description', 'EMPTY', '终局条件必须有描述');
  if (winLose.win !== undefined) checkCondition(winLose.win, 'winLose.win');
  if (winLose.lose !== undefined) checkCondition(winLose.lose, 'winLose.lose');

  return { ok: issues.length === 0, issues };
}

/** 从文件加载并校验 Blueprint。 */
export async function loadBlueprintFile(file: string): Promise<{ blueprint: Blueprint | null; validation: ValidationResult; parseError?: string }> {
  let raw: string;
  try {
    raw = await readFile(file, 'utf8');
  } catch (err) {
    return { blueprint: null, validation: { ok: false, issues: [] }, parseError: `无法读取文件：${(err as Error).message}` };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    return { blueprint: null, validation: { ok: false, issues: [] }, parseError: `JSON 解析失败：${(err as Error).message}` };
  }
  const validation = validateBlueprint(parsed);
  return { blueprint: validation.ok ? (parsed as Blueprint) : null, validation };
}

/** 用 Blueprint 构造杠杆关闭版（宪章 §3 检验用）。 */
export function withLeverageDisabled(blueprint: Blueprint): Blueprint {
  return { ...blueprint, leverage: { ...blueprint.leverage, enabled: false } };
}
