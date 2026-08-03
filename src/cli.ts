/**
 * CLI：Agent 与引擎之间的唯一接口。stdout 永远输出单行 JSON：
 *   {"ok":true,"data":...} | {"ok":false,"error":{"code","message","details?"}}
 *
 * 非法行动硬拒 + 结构化原因；Agent 据此向玩家解释"为什么不能这么做"。
 */
import path from 'node:path';
import { loadBlueprintFile, validateBlueprint } from './blueprint.ts';
import { contextFromState, evalCondition } from './conditions.ts';
import { checkExpansion, materializeFact, validateCandidate } from './expansion.ts';
import { DEFAULT_LANGUAGE, getEngineStrings, isLanguage, languageOf, SUPPORTED_LANGUAGES } from './i18n.ts';
import { addChapter } from './chapter.ts';
import { composeNovel } from './novel.ts';
import { knownByCategory, playerKnown, unknownFactIds } from './knowledge.ts';
import { legalActions, resolveAction, resolutionToHistory } from './resolve.ts';
import {
  appendHistory,
  freezeBlueprint,
  initState,
  listSaves,
  loadFrozenBlueprint,
  loadState,
  saveState,
  verifySave,
  writeManifest,
} from './save.ts';
import type { Blueprint, EngineError, GameState, HistoryEntry, Language } from './types.ts';

const BASE = process.cwd();

// ---------------------------------------------------------------------------
// 输出协议
// ---------------------------------------------------------------------------

function outputOk(data: unknown): void {
  process.stdout.write(JSON.stringify({ ok: true, data }) + '\n');
}

function outputErr(error: EngineError): void {
  process.stdout.write(JSON.stringify({ ok: false, error }) + '\n');
  process.exitCode = 1;
}

function isEngineError(err: unknown): err is EngineError {
  return typeof err === 'object' && err !== null && typeof (err as EngineError).code === 'string';
}

// ---------------------------------------------------------------------------
// 参数解析
// ---------------------------------------------------------------------------

function parseArgs(argv: string[]): { command: string; flags: Record<string, string> } {
  const [command, ...rest] = argv;
  const flags: Record<string, string> = {};
  for (let i = 0; i < rest.length; i++) {
    const arg = rest[i]!;
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const next = rest[i + 1];
      if (next !== undefined && !next.startsWith('--')) {
        flags[key] = next;
        i++;
      } else {
        flags[key] = 'true';
      }
    }
  }
  return { command: command ?? '', flags };
}

function requireFlag(flags: Record<string, string>, key: string, command: string): string {
  const value = flags[key];
  if (value === undefined || value === 'true') {
    throw { code: 'MISSING_ARG', message: `命令 ${command} 需要 --${key} 参数` } satisfies EngineError;
  }
  return value;
}

/** 确定目标世界：--world 显式指定，或健康存档唯一时自动选中。 */
async function resolveWorld(flags: Record<string, string>): Promise<string> {
  if (flags.world && flags.world !== 'true') return flags.world;
  const saves = await listSaves(BASE);
  const healthy = saves.filter((s) => s.status === 'ok' || s.status === 'needs-migration');
  if (healthy.length === 1) return healthy[0]!.world;
  throw {
    code: 'NEED_WORLD',
    message:
      saves.length === 0
        ? '没有存档。请先用 new 开局'
        : '存在多个存档，请用 --world 指定',
    details: saves.map((s) => (s.status === 'ok' ? s.world : `${s.world}（${s.status}${s.note ? `：${s.note}` : ''}）`)),
  } satisfies EngineError;
}

async function loadWorldPair(world: string): Promise<{ bp: Blueprint; state: GameState }> {
  const bp = await loadFrozenBlueprint(BASE, world).catch((err: Error) => {
    throw { code: 'SAVE_NOT_FOUND', message: `存档 "${world}" 的 blueprint.json 不可用：${err.message}` } satisfies EngineError;
  });
  const state = await loadState(BASE, world).catch((err: Error) => {
    throw { code: 'SAVE_NOT_FOUND', message: `无法读取存档 "${world}"：${err.message}` } satisfies EngineError;
  });
  // M7：存档目录与内部 world 字段必须一致，否则视为损坏。
  if (state.world !== world) {
    throw {
      code: 'SAVE_CORRUPT',
      message: `存档目录 "${world}" 与 state.world("${state.world}") 不一致`,
    } satisfies EngineError;
  }
  return { bp, state };
}

/**
 * M9：flag 可见来源追踪。只有"玩家可见来源"设置的 flag 才进入 status 投影：
 * 规律（对所有人一致可观察）、玩家亲自结算的行动结果、visible 的计划/事件；
 * visible=false 的离屏来源设置的 flag 保持秘密（宪章 §7）。
 */
function visibleFlagSources(bp: Blueprint): Set<string> {
  const sources = new Set<string>();
  for (const law of bp.laws) sources.add(`law:${law.id}`);
  for (const action of bp.actions) {
    for (const o of action.outcomes ?? []) sources.add(`action:${action.id}`);
  }
  for (const actor of bp.actors) {
    for (const p of actor.plans ?? []) {
      if (p.visible ?? false) sources.add(`actor:${actor.id}/${p.id}`);
    }
  }
  for (const ev of bp.scheduledEvents ?? []) {
    if (ev.visible ?? false) sources.add(`event:${ev.id}`);
  }
  return sources;
}

/** minor：只读终局判定提示——winLose 在开局即满足时如实报告。 */
function initialEndNote(bp: Blueprint, state: GameState): string | undefined {
  const ctx = contextFromState(state);
  if (bp.winLose.win && evalCondition(bp.winLose.win, ctx)) return '注意：胜利条件在当前状态已满足';
  if (bp.winLose.lose && evalCondition(bp.winLose.lose, ctx)) return '注意：失败条件在当前状态已满足';
  return undefined;
}

// ---------------------------------------------------------------------------
// 命令实现
// ---------------------------------------------------------------------------

async function cmdValidateBlueprint(flags: Record<string, string>): Promise<void> {
  const file = requireFlag(flags, 'file', 'validate-blueprint');
  const { blueprint, validation, parseError } = await loadBlueprintFile(file);
  if (parseError) {
    outputErr({ code: 'BLUEPRINT_PARSE_ERROR', message: parseError });
    return;
  }
  if (!validation.ok) {
    outputErr({
      code: 'BLUEPRINT_INVALID',
      message: `Blueprint 校验未通过：${validation.issues.length} 个问题`,
      details: validation.issues.map((i) => `[${i.code}] ${i.path}: ${i.message}`),
    });
    return;
  }
  outputOk({
    valid: true,
    world: blueprint!.meta.name,
    actions: blueprint!.actions.length,
    laws: blueprint!.laws.length,
    actors: blueprint!.actors.length,
  });
}

async function cmdNew(flags: Record<string, string>): Promise<void> {
  const blueprintPath = requireFlag(flags, 'blueprint', 'new');
  const world = requireFlag(flags, 'world', 'new');
  if (!/^[a-z0-9][a-z0-9-]*$/.test(world)) {
    outputErr({ code: 'BAD_WORLD_NAME', message: '世界名只能包含小写字母、数字和连字符，且以字母数字开头' });
    return;
  }
  const existing = await listSaves(BASE);
  if (existing.some((s) => s.world === world)) {
    outputErr({ code: 'WORLD_EXISTS', message: `存档 "${world}" 已存在，不能重复开局` });
    return;
  }
  const { blueprint, validation, parseError } = await loadBlueprintFile(blueprintPath);
  if (parseError) {
    outputErr({ code: 'BLUEPRINT_PARSE_ERROR', message: parseError });
    return;
  }
  if (!validation.ok) {
    outputErr({
      code: 'BLUEPRINT_INVALID',
      message: `Blueprint 校验未通过，拒绝开局：${validation.issues.length} 个问题`,
      details: validation.issues.map((i) => `[${i.code}] ${i.path}: ${i.message}`),
    });
    return;
  }
  let seed = blueprint!.meta.seed;
  if (flags.seed !== undefined && flags.seed !== 'true') {
    seed = Number(flags.seed);
    if (!Number.isFinite(seed)) {
      outputErr({ code: 'BAD_SEED', message: `--seed 必须是数字（实际 "${flags.seed}"）` });
      return;
    }
  }
  // V1.1：开局选择语言——--language 优先，其次 blueprint.meta.language，再无则默认 zh。
  // 语言是表现层元数据，不影响任何结算数值与确定性。
  let language: Language;
  if (flags.language !== undefined) {
    if (flags.language === 'true') {
      outputErr({
        code: 'BAD_LANGUAGE',
        message: `--language 缺少值，必须是 ${SUPPORTED_LANGUAGES.join(' / ')} 之一`,
      });
      return;
    }
    if (!isLanguage(flags.language)) {
      outputErr({
        code: 'BAD_LANGUAGE',
        message: `--language 必须是 ${SUPPORTED_LANGUAGES.join(' / ')} 之一（实际 "${flags.language}"）`,
      });
      return;
    }
    language = flags.language;
  } else {
    language = isLanguage(blueprint!.meta.language) ? blueprint!.meta.language : DEFAULT_LANGUAGE;
  }
  // M1：最终解析的 language 回写冻结 Blueprint，state 与冻结副本单一事实源。
  const frozen: Blueprint = { ...blueprint!, meta: { ...blueprint!.meta, seed, language } };
  const state = initState(frozen, world, seed, language);
  const opening: HistoryEntry = {
    turn: 0,
    kind: 'system',
    text: getEngineStrings(language).openingEntry(frozen.meta.name, frozen.meta.controlAxis),
    visible: true,
    source: 'engine',
  };
  state.historyCount = 1;
  state.historyLastTurn = 0;
  // M5：先落盘状态，成功之后再追加历史。
  await freezeBlueprint(BASE, world, frozen);
  await saveState(BASE, state);
  await appendHistory(BASE, world, [opening]);
  await writeManifest(BASE, world, { createdAt: new Date().toISOString(), seed });
  outputOk({
    world,
    seed,
    language,
    title: frozen.meta.title ?? frozen.meta.name,
    controlAxis: frozen.meta.controlAxis,
    leverage: frozen.leverage.name,
    turn: state.turn,
    saveDir: path.join('saves', world),
    ...(initialEndNote(frozen, state) ? { note: initialEndNote(frozen, state) } : {}),
  });
}

async function cmdStatus(flags: Record<string, string>): Promise<void> {
  const world = await resolveWorld(flags);
  const { bp, state } = await loadWorldPair(world);
  const ctx = contextFromState(state);
  const legality = legalActions(bp, state);
  const assetRows = bp.assetTypes.map((a) => ({
    id: a.id,
    name: a.name,
    kind: a.kind,
    value: state.assets[a.id] ?? 0,
    ...(a.maintenance ? { maintenance: `${a.maintenance.perTurn}/回合（以 ${a.maintenance.asset} 支付）` } : {}),
  }));
  const flagSources = visibleFlagSources(bp);
  const setters = collectFlagSetters(bp);
  // M9：flag 的全部设置来源都可见时才投影；任一来源不可见则保持秘密（宪章 §7）。
  const visibleFlags = Object.entries(state.flags)
    .filter(([flag, v]) => {
      if (!v) return false;
      const sources = setters.get(flag) ?? [];
      if (sources.length === 0) return false; // 无声明来源：保守隐藏
      return sources.every((s) => flagSources.has(s));
    })
    .map(([k]) => k);
  outputOk({
    world,
    language: languageOf(state),
    title: bp.meta.title ?? bp.meta.name,
    controlAxis: bp.meta.controlAxis,
    seed: state.seed,
    turn: state.turn,
    tier: state.tier,
    ended: state.ended ?? null,
    assets: assetRows,
    knownFacts: playerKnown(bp, state).map((f) => ({ id: f.id, description: f.description, category: f.category ?? 'misc' })),
    unknownTopics: unknownFactIds(bp, state).length,
    flags: visibleFlags,
    regions: bp.regions.map((r) => ({ id: r.id, name: r.name, unlocked: state.unlockedRegions.includes(r.id) })),
    activeLaws: bp.laws.filter((l) => (l.trigger ? evalCondition(l.trigger, ctx) : true)).map((l) => ({ id: l.id, description: l.description })),
    leverage: { name: bp.leverage.name, enabled: bp.leverage.enabled, uses: state.leverageUses },
    legalActions: legality
      .filter((x) => x.legal)
      .map((x) => ({
        id: x.action.id,
        name: x.action.name,
        tier: x.action.tier,
        leverageOnly: x.action.leverageOnly === true,
        timeCost: x.action.costs?.time ?? 1,
        ...(x.action.costs?.assets ? { assetCosts: x.action.costs.assets } : {}),
      })),
    blockedActions: legality.filter((x) => !x.legal).map((x) => ({ id: x.action.id, name: x.action.name, reasons: x.reasons })),
    pendingExpansions: checkExpansion(bp, state),
    ...(initialEndNote(bp, state) ? { note: initialEndNote(bp, state) } : {}),
  });
}

/** 收集每个 flag 的全部设置来源（M9 可见性判断用）。 */
function collectFlagSetters(bp: Blueprint): Map<string, string[]> {
  const map = new Map<string, string[]>();
  const add = (flag: string, source: string) => {
    let list = map.get(flag);
    if (!list) {
      list = [];
      map.set(flag, list);
    }
    list.push(source);
  };
  for (const law of bp.laws) {
    for (const e of law.effect ?? []) {
      if ('setFlag' in e) add(e.setFlag, `law:${law.id}`);
    }
  }
  for (const action of bp.actions) {
    for (const o of action.outcomes ?? []) {
      for (const e of o.effects ?? []) {
        if ('setFlag' in e) add(e.setFlag, `action:${action.id}`);
      }
    }
  }
  for (const actor of bp.actors) {
    for (const p of actor.plans ?? []) {
      for (const e of p.effects ?? []) {
        if ('setFlag' in e) add(e.setFlag, `actor:${actor.id}/${p.id}`);
      }
    }
  }
  for (const ev of bp.scheduledEvents ?? []) {
    for (const e of ev.effects ?? []) {
      if ('setFlag' in e) add(e.setFlag, `event:${ev.id}`);
    }
  }
  return map;
}

async function cmdAct(flags: Record<string, string>): Promise<void> {
  const id = requireFlag(flags, 'id', 'act');
  const world = await resolveWorld(flags);
  const { bp, state } = await loadWorldPair(world);
  const resolution = resolveAction(bp, state, id); // 非法时抛 EngineError
  const entries = resolutionToHistory(resolution);
  state.historyCount += entries.length;
  state.historyLastTurn = state.turn;
  // M5：先 saveState 成功，再 appendHistory。
  await saveState(BASE, state);
  await appendHistory(BASE, world, entries);
  await writeManifest(BASE, world, { lastAction: id, turn: state.turn });
  outputOk({
    action: id,
    outcome: resolution.outcomeId,
    turn: resolution.turn,
    tier: state.tier,
    tierUp: resolution.tierUp,
    irreversible: resolution.irreversible,
    unlocked: resolution.unlocked,
    ended: state.ended ?? null,
    consequences: resolution.consequences,
    assets: bp.assetTypes.map((a) => ({ id: a.id, name: a.name, value: state.assets[a.id] ?? 0 })),
  });
}

async function cmdObserve(flags: Record<string, string>): Promise<void> {
  const scope = requireFlag(flags, 'scope', 'observe');
  const world = await resolveWorld(flags);
  const { bp, state } = await loadWorldPair(world);
  const ctx = contextFromState(state);
  if (scope === 'laws') {
    outputOk({
      scope,
      note: '规律对所有人一致且可观察；秘密在事实层，须经观察/调查类行动获得',
      laws: bp.laws.map((l) => ({
        id: l.id,
        description: l.description,
        activeNow: l.trigger ? evalCondition(l.trigger, ctx) : true,
      })),
    });
    return;
  }
  const byCategory = knownByCategory(bp, state);
  if (scope === 'all') {
    outputOk({ scope, categories: byCategory, unknownTopics: unknownFactIds(bp, state).length });
    return;
  }
  const known = byCategory[scope] ?? [];
  const hiddenInScope = bp.facts.filter(
    (f) => f.category === scope && f.scope === 'hidden' && !state.knownFacts.includes(f.id),
  ).length;
  outputOk({
    scope,
    knownFacts: known.map((f) => ({ id: f.id, description: f.description })),
    hiddenInScope,
    note: hiddenInScope > 0 ? '该主题下仍有未知信息，需要通过观察/调查类行动付出成本获得' : undefined,
  });
}

async function cmdChapterAdd(flags: Record<string, string>): Promise<void> {
  const title = requireFlag(flags, 'title', 'chapter-add');
  const file = requireFlag(flags, 'file', 'chapter-add');
  const world = await resolveWorld(flags);
  const { state } = await loadWorldPair(world);
  const result = await addChapter(BASE, state, title, file);
  await saveState(BASE, state);
  await writeManifest(BASE, world, { chapters: state.chapters.length });
  outputOk({ chapter: result.record, file: path.relative(BASE, result.file) });
}

async function cmdEnd(flags: Record<string, string>): Promise<void> {
  const reason = requireFlag(flags, 'reason', 'end');
  const world = await resolveWorld(flags);
  const { bp, state } = await loadWorldPair(world);
  if (!state.ended) {
    state.ended = { reason, turn: state.turn };
  }
  const entry: HistoryEntry = {
    turn: state.turn,
    kind: 'ending',
    text: getEngineStrings(languageOf(state)).endingEntry(reason),
    visible: true,
    source: 'player',
  };
  state.historyCount += 1;
  state.historyLastTurn = state.turn;
  // M5：先落盘状态，再追加历史，最后合成小说。
  await saveState(BASE, state);
  await appendHistory(BASE, world, [entry]);
  const composed = await composeNovel(BASE, bp, state, reason);
  await writeManifest(BASE, world, { endedAt: new Date().toISOString(), reason });
  outputOk({
    world,
    reason: state.ended.reason,
    turn: state.turn,
    tier: state.tier,
    novel: path.relative(BASE, composed.novelFile),
    chapters: composed.chapters,
  });
}

/** C1：Lazy Expansion 物化——候选校验通过后才成为世界事实（宪章 §7）。 */
async function cmdExpand(flags: Record<string, string>): Promise<void> {
  const ruleId = requireFlag(flags, 'rule', 'expand');
  const id = requireFlag(flags, 'id', 'expand');
  const description = requireFlag(flags, 'desc', 'expand');
  const world = await resolveWorld(flags);
  const { bp, state } = await loadWorldPair(world);

  const validation = validateCandidate(bp, state, ruleId, { id, description });
  if (!validation.ok) {
    outputErr({
      code: 'EXPANSION_REJECTED',
      message: `候选内容未通过校验，物化被拒绝（宪章 §7：先成为经验证的候选，再成为世界事实）`,
      details: validation.problems,
    });
    return;
  }

  let anchorTier: number | undefined;
  if (flags['anchor-tier'] !== undefined && flags['anchor-tier'] !== 'true') {
    anchorTier = Number(flags['anchor-tier']);
    if (!Number.isInteger(anchorTier) || anchorTier < 0) {
      outputErr({ code: 'BAD_ANCHOR_TIER', message: `--anchor-tier 必须是非负整数（实际 "${flags['anchor-tier']}"）` });
      return;
    }
  }
  const category = flags.category !== undefined && flags.category !== 'true' ? flags.category : undefined;

  materializeFact(bp, { id, description, ...(category !== undefined ? { category } : {}), ...(anchorTier !== undefined ? { anchorTier } : {}) });

  // 物化后的 Blueprint 必须仍然通过完整校验，才允许写回（不追溯破坏既有规则）。
  const revalidation = validateBlueprint(bp);
  if (!revalidation.ok) {
    outputErr({
      code: 'EXPANSION_INVALID',
      message: '物化后的 Blueprint 未通过校验，已放弃写回',
      details: revalidation.issues.map((i) => `[${i.code}] ${i.path}: ${i.message}`),
    });
    return;
  }

  const entry: HistoryEntry = {
    turn: state.turn,
    kind: 'system',
    text: getEngineStrings(languageOf(state)).expansionMaterialized(ruleId, id, description),
    visible: true,
    source: `expansion:${ruleId}`,
  };
  state.historyCount += 1;
  state.historyLastTurn = state.turn;

  await freezeBlueprint(BASE, world, bp); // 更新后的 blueprint 写回随档冻结副本
  await saveState(BASE, state);
  await appendHistory(BASE, world, [entry]);
  await writeManifest(BASE, world, { lastExpansion: { ruleId, factId: id, turn: state.turn } });
  outputOk({
    world,
    rule: ruleId,
    fact: id,
    factsTotal: bp.facts.length,
    pendingExpansions: checkExpansion(bp, state),
  });
}

async function cmdVerify(flags: Record<string, string>): Promise<void> {
  const world = await resolveWorld(flags);
  const result = await verifySave(BASE, world);
  if (result.ok) {
    outputOk({ world, verified: true, message: '存档完整：校验和、schemaVersion、引用一致性、章节与历史对账均通过' });
  } else {
    outputErr({ code: 'VERIFY_FAILED', message: `存档 "${world}" 校验失败`, details: result.problems });
  }
}

async function cmdList(): Promise<void> {
  const saves = await listSaves(BASE);
  outputOk({ saves });
}

// ---------------------------------------------------------------------------
// 入口
// ---------------------------------------------------------------------------

const HELP = {
  commands: [
    'validate-blueprint --file <路径>',
    `new --blueprint <路径> --world <名> [--seed N] [--language <${SUPPORTED_LANGUAGES.join('|')}>]`,
    'status [--world <名>]',
    'act --id <行动id> [--world <名>]',
    'observe --scope <主题|laws|all> [--world <名>]',
    'chapter-add --title "..." --file <路径> [--world <名>]',
    'expand --rule <规则id> --id <事实id> --desc "<描述>" [--category <主题>] [--anchor-tier N] [--world <名>]',
    'end --reason "..." [--world <名>]',
    'verify [--world <名>]',
    'list',
  ],
};

async function main(): Promise<void> {
  const { command, flags } = parseArgs(process.argv.slice(2));
  switch (command) {
    case 'validate-blueprint':
      await cmdValidateBlueprint(flags);
      break;
    case 'new':
      await cmdNew(flags);
      break;
    case 'status':
      await cmdStatus(flags);
      break;
    case 'act':
      await cmdAct(flags);
      break;
    case 'observe':
      await cmdObserve(flags);
      break;
    case 'chapter-add':
      await cmdChapterAdd(flags);
      break;
    case 'expand':
      await cmdExpand(flags);
      break;
    case 'end':
      await cmdEnd(flags);
      break;
    case 'verify':
      await cmdVerify(flags);
      break;
    case 'list':
      await cmdList();
      break;
    case 'help':
    case '--help':
    case '':
      outputOk(HELP);
      break;
    default:
      outputErr({ code: 'UNKNOWN_COMMAND', message: `未知命令 "${command}"`, details: HELP.commands });
  }
}

try {
  await main();
} catch (err) {
  if (isEngineError(err)) {
    outputErr(err);
  } else if (err instanceof Error) {
    outputErr({ code: 'INTERNAL', message: err.message });
  } else {
    outputErr({ code: 'INTERNAL', message: String(err) });
  }
}
