// tgn CLI：手写 argv 路由（零运行时依赖，不引 commander）。
// 铁律：LLM at the edges, deterministic engine at the center——CLI 只做
// 读档 → 引擎纯函数 → appendEvent 全部新事件 → saveWorld → 输出 JSON 信封。
// 信封：成功 {ok:true, cmd, data}；失败 {ok:false, cmd, code, reason, hints[]}；exitCode 0/1。
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
import type { Language, WorldState } from './engine/types.ts';
import { t } from './engine/i18n.ts';
import { loadWorld, saveWorld, appendEvent, readEvents, readJsonFile, writeJsonFile, readTextFile } from './engine/store.ts';
import { listActions } from './engine/legality.ts';
import { resolveAction } from './engine/resolve.ts';
import { endTurn } from './engine/tick.ts';
import { checkTierGate, tierUp } from './engine/tier.ts';
import { replay } from './engine/verify.ts';
import { validateProposal, LANGUAGES } from './engine/validate.ts';
import { acceptProposal, type Blueprint, type WorldMeta } from './engine/worldgen.ts';
import { interact, INTERACT_KINDS, type InteractKind } from './engine/interact.ts';
import { makeChapterFact, submitChapter, finishWorld } from './engine/novel.ts';

export interface EnvelopeOk { ok: true; cmd: string; data: unknown }
export interface EnvelopeErr { ok: false; cmd: string; code: string; reason: string; hints: string[] }
export type Envelope = EnvelopeOk | EnvelopeErr;
export interface CliResult { envelope: Envelope; exitCode: 0 | 1 }

/** commit 产生的责任记录（宪法 §9：承诺产生 deadline）。 */
export interface Commitment {
  npcId: string;
  madeTurn: number;
  deadlineTurn: number;
}

const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function okEnv(cmd: string, data: unknown): Envelope {
  return { ok: true, cmd, data };
}
function errEnv(cmd: string, code: string, reason: string, hints: string[]): Envelope {
  return { ok: false, cmd, code, reason, hints };
}

/** 缺失原因码（tier:N/knowledge:K/…/chapter:notLatest:N）→ i18n hint.* 本地化。
 * 查不到对应 i18n 键时原样透传（如 E_UNKNOWN_ACTION 返回的 actionId 列表），不得输出原始键名。 */
function localizeHints(lang: Language, hints: string[]): string[] {
  return hints.map((h) => {
    const idx = h.indexOf(':');
    const key = idx >= 0 ? h.slice(0, idx) : h;
    const detail = idx >= 0 ? h.slice(idx + 1) : '';
    const i18nKey = `hint.${key}`;
    const label = t(lang, i18nKey);
    if (label === i18nKey) return h; // 无对应键 → 原样透传
    return detail !== '' ? `${label} (${detail})` : label;
  });
}

/** 默认种子：slug 的 sha256 前 8 位十六进制转整数（确定性）。 */
function defaultSeed(slug: string): number {
  return parseInt(createHash('sha256').update(slug).digest('hex').slice(0, 8), 16);
}

function parseArgs(argv: string[]): { pos: string[]; flags: Record<string, string> } {
  const pos: string[] = [];
  const flags: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith('--')) {
        flags[key] = next;
        i++;
      } else {
        flags[key] = 'true';
      }
    } else {
      pos.push(a);
    }
  }
  return { pos, flags };
}

function readProposalFile(cmd: string, file: string | undefined): { raw?: unknown; err?: Envelope } {
  if (!file) return { err: errEnv(cmd, 'E_INVALID_INPUT', '--file <path> is required', []) };
  try {
    return { raw: JSON.parse(readFileSync(file, 'utf8')) as unknown };
  } catch (e) {
    return { err: errEnv(cmd, 'E_INVALID_INPUT', `cannot read/parse proposal file: ${(e as Error).message}`, []) };
  }
}

function requirePlaying(cmd: string, state: WorldState): Envelope | null {
  if (state.phase !== 'playing') {
    return errEnv(cmd, 'E_ILLEGAL_ACTION', `world phase is "${state.phase}", actions are closed`, []);
  }
  return null;
}

type Flags = Record<string, string>;

function cmdNew(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'new';
  const slug = pos[1] ?? '';
  if (!SLUG_RE.test(slug) || slug.length > 40) {
    return errEnv(cmd, 'E_INVALID_INPUT', `invalid world slug "${slug}"`, ['slug: ^[a-z0-9]+(-[a-z0-9]+)*$']);
  }
  const langRaw = flags['lang'] ?? 'zh';
  if (!(LANGUAGES as readonly string[]).includes(langRaw)) {
    return errEnv(cmd, 'E_INVALID_INPUT', `invalid --lang "${langRaw}"`, [`lang: ${LANGUAGES.join('|')}`]);
  }
  let seed: number;
  if (flags['seed'] !== undefined) {
    seed = Number(flags['seed']);
    if (!Number.isInteger(seed) || seed < 0) return errEnv(cmd, 'E_INVALID_INPUT', `invalid --seed "${flags['seed']}"`, ['seed: integer >= 0']);
  } else {
    seed = defaultSeed(slug);
  }
  const existing = readJsonFile(slug, 'world.json', root);
  if (existing) return errEnv(cmd, 'E_ILLEGAL_ACTION', `world "${slug}" already exists`, []);
  const meta: WorldMeta = { worldSlug: slug, language: langRaw as Language, seed };
  writeJsonFile(slug, 'world.json', meta, root);
  return okEnv(cmd, { worldSlug: slug, language: meta.language, seed });
}

function cmdPropose(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'propose';
  const rf = readProposalFile(cmd, flags['file']);
  if (rf.err) return rf.err;
  const vr = validateProposal(rf.raw);
  if (!vr.ok) return errEnv(cmd, 'E_PROPOSAL_INVALID', `${vr.issues.length} issue(s) found`, vr.issues.map((i) => `[${i.field}] ${i.message} → ${i.fix}`));
  // 语言一致性：proposal.language 必须与 `new --lang` 注册的语言一致（防分裂存档）
  const slug = pos[1] ?? '';
  if (slug) {
    const meta = readJsonFile<WorldMeta>(slug, 'world.json', root);
    if (meta && meta.language !== vr.proposal.language) {
      return errEnv(cmd, 'E_PROPOSAL_INVALID', `proposal.language "${vr.proposal.language}" mismatches registered language "${meta.language}"`, [`language:${meta.language}`]);
    }
  }
  return okEnv(cmd, { valid: true, worldName: vr.proposal.worldName, language: vr.proposal.language });
}

function cmdAccept(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'accept';
  const slug = pos[1] ?? '';
  const meta = readJsonFile<WorldMeta>(slug, 'world.json', root);
  if (!meta) return errEnv(cmd, 'E_WORLD_NOT_FOUND', `world "${slug}" not registered`, ['new']);
  // 重复 accept 防护：已初始化的世界（playing/ended）不得再次 accept，防止静默重置存档污染事件重放链
  const existing = readJsonFile<WorldState>(slug, 'state.json', root);
  if (existing && existing.phase !== 'proposed') {
    return errEnv(cmd, 'E_ILLEGAL_ACTION', `world "${slug}" already initialized (phase "${existing.phase}"); re-accept refused`, ['status', 'new']);
  }
  const rf = readProposalFile(cmd, flags['file']);
  if (rf.err) return rf.err;
  const vr = validateProposal(rf.raw);
  if (!vr.ok) return errEnv(cmd, 'E_PROPOSAL_INVALID', `${vr.issues.length} issue(s) found`, vr.issues.map((i) => `[${i.field}] ${i.message} → ${i.fix}`));
  // 语言一致性：proposal.language 必须与 `new --lang` 注册的语言一致（防 world.json/state.json 分裂存档）
  if (meta.language !== vr.proposal.language) {
    return errEnv(cmd, 'E_PROPOSAL_INVALID', `proposal.language "${vr.proposal.language}" mismatches registered language "${meta.language}"`, [`language:${meta.language}`]);
  }
  const ar = acceptProposal(slug, vr.proposal, meta.seed, root);
  if (!ar.ok) return errEnv(cmd, 'E_PROPOSAL_INVALID', `${ar.issues.length} issue(s) found`, ar.issues.map((i) => `[${i.field}] ${i.message} → ${i.fix}`));
  return okEnv(cmd, {
    worldSlug: slug,
    seed: meta.seed,
    language: ar.state.language,
    worldName: vr.proposal.worldName,
    leverage: vr.proposal.leverage.name,
    turn: ar.state.turn,
    tier: ar.state.tier,
    resources: ar.state.player.resources,
    npcs: ar.state.npcs.map((n) => ({ id: n.id, name: n.name, goal: n.goal, power: n.power })),
  });
}

function cmdStatus(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'status';
  const slug = pos[1] ?? '';
  const state = loadWorld(slug, root);
  const lang = state.language;
  const commitments = readJsonFile<Commitment[]>(slug, 'commitments.json', root) ?? [];
  const gate = checkTierGate(state);
  const nextStep: string[] = [];
  if (state.phase === 'playing' && gate.ok) nextStep.push(t(lang, 'hint.tierUpReady'));
  if (state.windows.some((w) => w.expiresTurn <= state.turn + 1)) nextStep.push(t(lang, 'hint.windowExpiring'));
  if (commitments.some((c) => c.deadlineTurn <= state.turn + 1)) nextStep.push(t(lang, 'hint.commitDue'));
  if (state.phase === 'playing') nextStep.push(t(lang, 'hint.endTurn'));
  const cohort = state.npcs
    .slice()
    .sort((a, b) => b.power - a.power)
    .map((n) => ({ id: n.id, name: n.name, goal: n.goal, power: n.power, attitude: n.attitude, alive: n.alive }));
  return okEnv(cmd, {
    worldSlug: slug,
    seed: state.seed,
    language: lang,
    phase: state.phase,
    turn: state.turn,
    tier: state.tier,
    panel: state.player,
    rulesKnown: state.rulesKnown,
    windows: state.windows,
    commitments,
    cohort,
    lastTurnReport: state.lastTurnReport,
    nextStep,
  });
}

function cmdActions(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'actions';
  const slug = pos[1] ?? '';
  const state = loadWorld(slug, root);
  const blueprint = readJsonFile<Blueprint>(slug, 'blueprint.json', root);
  if (!blueprint) return errEnv(cmd, 'E_ILLEGAL_ACTION', 'blueprint missing', ['accept']);
  const actions = listActions(state, blueprint.proposal.actions);
  return okEnv(cmd, { turn: state.turn, focus: state.player.focus, actions });
}

function cmdAct(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'act';
  const slug = pos[1] ?? '';
  const actionId = pos[2] ?? '';
  const state = loadWorld(slug, root);
  const closed = requirePlaying(cmd, state);
  if (closed) return closed;
  const blueprint = readJsonFile<Blueprint>(slug, 'blueprint.json', root);
  if (!blueprint) return errEnv(cmd, 'E_ILLEGAL_ACTION', 'blueprint missing', ['accept']);
  // 缺参数是调用方错误：保留 E_INVALID_ARGS 原始错误码，不得映射成 E_ILLEGAL_ACTION（会误导 Agent 归因引擎规则）
  if (!actionId) return errEnv(cmd, 'E_INVALID_ARGS', 'actionId is required', ['usage: act <world> <actionId> [--params JSON]']);
  let targetNpcId: string | undefined;
  if (flags['params'] !== undefined) {
    try {
      const pj = JSON.parse(flags['params']) as { targetNpcId?: unknown };
      if (typeof pj.targetNpcId === 'string') targetNpcId = pj.targetNpcId;
    } catch (e) {
      return errEnv(cmd, 'E_INVALID_INPUT', `invalid --params JSON: ${(e as Error).message}`, []);
    }
  }
  const res = resolveAction(state, actionId, { table: blueprint.proposal.actions, targetNpcId });
  if (!res.ok) return errEnv(cmd, res.error.code, res.error.reason, localizeHints(state.language, res.error.hints));
  for (const ev of res.events) appendEvent(slug, ev, root);
  saveWorld(res.newState, root);
  return okEnv(cmd, { outcome: res.outcome, events: res.events.length, turn: res.newState.turn, factsSeq: res.newState.lastFactsSeq });
}

function cmdInteract(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'interact';
  const slug = pos[1] ?? '';
  const npcId = pos[2] ?? '';
  const kindRaw = pos[3] ?? '';
  const state = loadWorld(slug, root);
  const closed = requirePlaying(cmd, state);
  if (closed) return closed;
  if (!npcId) return errEnv(cmd, 'E_INVALID_INPUT', 'npcId is required', []);
  if (!(INTERACT_KINDS as readonly string[]).includes(kindRaw)) {
    return errEnv(cmd, 'E_INVALID_INPUT', `invalid interact kind "${kindRaw}"`, [`kind: ${INTERACT_KINDS.join('|')}`]);
  }
  const blueprint = readJsonFile<Blueprint>(slug, 'blueprint.json', root);
  const res = interact(state, npcId, kindRaw as InteractKind, { hiddenRules: blueprint?.proposal.rulesHidden ?? [] });
  if (!res.ok) return errEnv(cmd, res.error.code, res.error.reason, localizeHints(state.language, res.error.hints));
  for (const ev of res.events) appendEvent(slug, ev, root);
  saveWorld(res.newState, root);
  if (res.outcome.deadlineTurn !== undefined) {
    const list = readJsonFile<Commitment[]>(slug, 'commitments.json', root) ?? [];
    list.push({ npcId, madeTurn: state.turn, deadlineTurn: res.outcome.deadlineTurn });
    writeJsonFile(slug, 'commitments.json', list, root);
  }
  return okEnv(cmd, { outcome: res.outcome, events: res.events.length, factsSeq: res.newState.lastFactsSeq });
}

function cmdEndTurn(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'end-turn';
  const slug = pos[1] ?? '';
  const state = loadWorld(slug, root);
  const closed = requirePlaying(cmd, state);
  if (closed) return closed;
  const res = endTurn(state);
  for (const ev of res.events) appendEvent(slug, ev, root);
  saveWorld(res.newState, root);
  const chapterFact = makeChapterFact(res.newState);
  return okEnv(cmd, { turn: res.newState.turn, turnReport: res.turnReport, chapterFact });
}

function cmdLog(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'log';
  const slug = pos[1] ?? '';
  loadWorld(slug, root); // 世界必须存在
  const events = readEvents(slug, root);
  const n = flags['last'] !== undefined ? Number(flags['last']) : 20;
  if (!Number.isInteger(n) || n < 1) return errEnv(cmd, 'E_INVALID_INPUT', `invalid --last "${flags['last']}"`, ['last: integer >= 1']);
  return okEnv(cmd, { total: events.length, showing: Math.min(n, events.length), events: events.slice(-n) });
}

function cmdTierUp(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'tier-up';
  const slug = pos[1] ?? '';
  const state = loadWorld(slug, root);
  const closed = requirePlaying(cmd, state);
  if (closed) return closed;
  const gate = checkTierGate(state);
  if (!gate.ok) return errEnv(cmd, 'E_ILLEGAL_ACTION', 'tier gate not reached', localizeHints(state.language, gate.missing));
  const res = tierUp(state);
  if (!res.ok) return errEnv(cmd, res.error.code, res.error.reason, localizeHints(state.language, res.error.hints));
  for (const ev of res.events) appendEvent(slug, ev, root);
  saveWorld(res.newState, root);
  const payload = res.events[0].payload as { newTier?: number; zone?: { id?: string; trait?: string } };
  return okEnv(cmd, { tier: res.newState.tier, newTier: payload.newTier, zone: payload.zone, factsSeq: res.newState.lastFactsSeq });
}

function cmdChapter(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'chapter';
  const slug = pos[1] ?? '';
  const state = loadWorld(slug, root);
  if (flags['facts'] === undefined) return errEnv(cmd, 'E_INVALID_INPUT', '--facts <seq> is required', []);
  if (flags['file'] === undefined) return errEnv(cmd, 'E_INVALID_INPUT', '--file <md> is required', []);
  const facts = Number(flags['facts']);
  const md = readTextFile(flags['file']);
  if (md === null) return errEnv(cmd, 'E_INVALID_INPUT', `chapter file not found: ${flags['file']}`, []);
  const res = submitChapter(slug, facts, md, root);
  if (!res.ok) return errEnv(cmd, res.error.code, res.error.reason, localizeHints(state.language, res.error.hints));
  return okEnv(cmd, res.data);
}

function cmdFinish(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'finish';
  const slug = pos[1] ?? '';
  const state = loadWorld(slug, root);
  const res = finishWorld(slug, root);
  if (!res.ok) return errEnv(cmd, res.error.code, res.error.reason, localizeHints(state.language, res.error.hints));
  return okEnv(cmd, res.data);
}

function cmdVerify(pos: string[], flags: Flags, root?: string): Envelope {
  const cmd = 'verify';
  const slug = pos[1] ?? '';
  const r = replay(slug, root);
  if (r.ok) return okEnv(cmd, { verified: true, worldSlug: slug });
  return errEnv(
    cmd,
    'E_REPLAY_MISMATCH',
    'replay does not match saved state',
    r.mismatches.map((m) => `${m.field}: expected=${JSON.stringify(m.expected)} replayed=${JSON.stringify(m.replayed)}`),
  );
}

/** 路由入口：argv → 信封 + exitCode。供 CLI 直跑与测试内联调用。 */
export function runCli(argv: string[]): CliResult {
  const { pos, flags } = parseArgs(argv);
  const cmd = pos[0] ?? '';
  const root = flags['root'];
  let envelope: Envelope;
  try {
    switch (cmd) {
      case 'new': envelope = cmdNew(pos, flags, root); break;
      case 'propose': envelope = cmdPropose(pos, flags, root); break;
      case 'accept': envelope = cmdAccept(pos, flags, root); break;
      case 'status': envelope = cmdStatus(pos, flags, root); break;
      case 'actions': envelope = cmdActions(pos, flags, root); break;
      case 'act': envelope = cmdAct(pos, flags, root); break;
      case 'interact': envelope = cmdInteract(pos, flags, root); break;
      case 'end-turn': envelope = cmdEndTurn(pos, flags, root); break;
      case 'log': envelope = cmdLog(pos, flags, root); break;
      case 'tier-up': envelope = cmdTierUp(pos, flags, root); break;
      case 'chapter': envelope = cmdChapter(pos, flags, root); break;
      case 'finish': envelope = cmdFinish(pos, flags, root); break;
      case 'verify': envelope = cmdVerify(pos, flags, root); break;
      default:
        envelope = errEnv(cmd || '(none)', 'E_UNKNOWN_COMMAND', `unknown command "${cmd}"`, [
          'new|propose|accept|status|actions|act|interact|end-turn|log|tier-up|chapter|finish|verify',
        ]);
    }
  } catch (e) {
    const err = e as Error & { code?: string };
    if (err.code === 'E_SAVE_CORRUPTED') {
      // 存档损坏：保留结构化错误码与行号 hint，不裸崩成 E_INTERNAL
      envelope = errEnv(cmd, 'E_SAVE_CORRUPTED', err.message, ['verify']);
    } else if (err.code === 'E_WORLD_NOT_FOUND') {
      // 世界未找到时无法读 state.language；尝试 world.json 注册语言本地化兜底提示
      const meta = readJsonFile<WorldMeta>(pos[1] ?? '', 'world.json', root);
      const lang = meta?.language ?? 'zh';
      envelope = errEnv(cmd, 'E_WORLD_NOT_FOUND', err.message, [t(lang, 'hint.new'), t(lang, 'hint.accept')]);
    } else {
      envelope = errEnv(cmd, 'E_INTERNAL', err.message, []);
    }
  }
  return { envelope, exitCode: envelope.ok ? 0 : 1 };
}

// 直接执行入口（被 import 时不触发）。
const entry = process.argv[1];
if (entry && import.meta.url === pathToFileURL(entry).href) {
  const result = runCli(process.argv.slice(2));
  console.log(JSON.stringify(result.envelope, null, 2));
  process.exitCode = result.exitCode;
}
