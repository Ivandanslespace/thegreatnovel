// 小说系统（宪法 §1：世界先运行，小说后书写；叙事只表达已成立的事实）。
// - createNovel：accept 时创建 worlds/<slug>/novel/《世界名》.md（frontmatter：种子/语言/杠杆名/开局回合）。
// - makeChapterFact：endTurn 后引擎产出章节事实（factsSeq = 该回合结算后的最新事实序号）。
// - submitChapter：factsSeq 必须等于当前未归档的最新事实（防跳章/重复/乱序），通过后追加散文 +
//   引擎自动渲染的结算面板（i18n 按 state.language，数值与状态一致），并标记归档。
// - exportNovel：全书 + 引擎附录（大事记/因果账本，全部从 events.jsonl 提取）。
// - finishWorld：phase→ended，引擎生成尾声（最终状态/跃迁轨迹/人物结局），随后 exportNovel。
import type { EngineError, GameEvent, Language, WorldState } from './types.ts';
import { t } from './i18n.ts';
import { loadWorld, saveWorld, readEvents, readJsonFile, writeJsonFile, readTextFile, writeTextFile, appendTextFile, appendEvent, subDir } from './store.ts';
import { applyAll } from './state.ts';
import { join } from 'node:path';
import type { WorldProposal } from './validate.ts';

/** 文件名安全化兜底：即使上游校验被绕过，也不得让 worldName 携带路径成分（防路径穿越）。
 * 手动剥离两种分隔符下的目录成分，跨平台行为确定。 */
function safeFileName(name: string): string {
  const norm = name.replace(/\\/g, '/');
  const b = norm.slice(norm.lastIndexOf('/') + 1);
  return b === '' || b === '.' || b === '..' ? 'world' : b;
}

export interface NovelMeta {
  worldName: string;
  language: Language;
  leverageName: string;
  novelFile: string;
  /** 已归档章节绑定的 factsSeq（单调递增）。 */
  archived: number[];
}

export interface ChapterFact {
  /** 章节必须绑定的事实序号（= 该回合全部事件落盘后的最新事实）。 */
  factsSeq: number;
  turn: number;
  /** 本回合事件摘要（i18n 渲染），供 Agent 写章时参照。 */
  lines: string[];
}

export type ChapterResult =
  | { ok: true; data: { factsSeq: number; turn: number; novelFile: string } }
  | { ok: false; error: EngineError };

const META_NAME = 'novel/meta.json';

function novelFilePath(slug: string, meta: NovelMeta, root?: string): string {
  return join(subDir(slug, 'novel', root), meta.novelFile);
}

/** accept 时创建小说文件与元数据。 */
export function createNovel(slug: string, state: WorldState, proposal: WorldProposal, root?: string): { novelFile: string; path: string } {
  const novelFile = `《${safeFileName(proposal.worldName)}》.md`;
  const meta: NovelMeta = {
    worldName: proposal.worldName,
    language: state.language,
    leverageName: proposal.leverage.name,
    novelFile,
    archived: [],
  };
  const frontmatter = [
    '---',
    `world: ${proposal.worldName}`,
    `seed: ${state.seed}`,
    `language: ${state.language}`,
    `leverage: ${proposal.leverage.name}`,
    `startTurn: ${state.turn}`,
    '---',
    '',
    `# ${proposal.worldName}`,
    '',
  ].join('\n');
  const path = novelFilePath(slug, meta, root);
  writeTextFile(path, frontmatter);
  writeJsonFile(slug, META_NAME, meta, root);
  return { novelFile, path };
}

/** endTurn 后产出章节事实：factsSeq 取该回合全部事件应用后的最新事实序号。 */
export function makeChapterFact(state: WorldState): ChapterFact {
  const lang = state.language;
  const lines: string[] = [];
  const r = state.lastTurnReport;
  if (r) {
    for (const ev of r.playerEvents) {
      if (ev.type === 'ActionResolved') {
        const p = ev.payload as { actionId?: string; success?: boolean; yield?: number };
        const verdict = p.success ? t(lang, 'fact.success') : t(lang, 'fact.failure');
        lines.push(`- ${p.actionId ?? '?'}: ${verdict}, yield=${p.yield ?? 0}`);
      }
    }
    if (r.offscreen.length > 0) lines.push(`- ${t(lang, 'report.offscreen')}: ${r.offscreen.length}`);
    for (const w of r.windows) {
      lines.push(`- ${t(lang, `window.${w.kind}`)}: ${t(lang, w.labelKey)} (${t(lang, 'table.turn')} ≤ ${w.expiresTurn})`);
    }
    for (const wc of r.windowsClosed) {
      lines.push(`- ${t(lang, 'window.closed')}: ${t(lang, wc.labelKey)} [${wc.cause}]`);
    }
    lines.push(`- ${t(lang, 'report.maintenancePaid')}: ${r.maintenancePaid}`);
  }
  return { factsSeq: state.lastFactsSeq, turn: state.turn, lines };
}

/**
 * 提交章节散文。防跳章/重复/乱序：
 * - factsSeq ≤ 最近已归档 → 重复/过期；
 * - factsSeq ≠ state.lastFactsSeq → 不是当前最新未归档事实（其间有新事件发生）。
 */
export function submitChapter(slug: string, factsSeq: number, markdown: string, root?: string): ChapterResult {
  let state: WorldState;
  try {
    state = loadWorld(slug, root);
  } catch (e) {
    return { ok: false, error: { code: 'E_WORLD_NOT_FOUND', reason: (e as Error).message, hints: [] } };
  }
  const meta = readJsonFile<NovelMeta>(slug, META_NAME, root);
  if (!meta) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: 'novel meta missing', hints: ['accept'] } };
  }
  if (!Number.isInteger(factsSeq) || factsSeq < 0) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: `factsSeq must be a non-negative integer, got ${String(factsSeq)}`, hints: ['chapter:integer'] } };
  }
  // 哨兵 -1：archived 为空时合法的 factsSeq 0（Init 事实）不得被误判为已归档
  const lastArchived = meta.archived.length > 0 ? Math.max(...meta.archived) : -1;
  if (factsSeq <= lastArchived) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: `factsSeq ${factsSeq} already archived or outdated (last archived ${lastArchived})`, hints: [`chapter:duplicate:${lastArchived}`] } };
  }
  if (factsSeq !== state.lastFactsSeq) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: `factsSeq ${factsSeq} is not the latest unarchived fact (expected ${state.lastFactsSeq})`, hints: [`chapter:notLatest:${state.lastFactsSeq}`] } };
  }

  const lang = state.language;
  const panel = renderSettlementPanel(state);
  const chunk = [
    '',
    '',
    `<!-- factsSeq:${factsSeq} turn:${state.turn} -->`,
    '',
    markdown.trim(),
    '',
    '---',
    '',
    `### ${t(lang, 'novel.settlement')} (${t(lang, 'novel.facts')} #${factsSeq})`,
    '',
    panel,
    '',
  ].join('\n');
  appendTextFile(novelFilePath(slug, meta, root), chunk);

  meta.archived.push(factsSeq);
  writeJsonFile(slug, META_NAME, meta, root);
  return { ok: true, data: { factsSeq, turn: state.turn, novelFile: meta.novelFile } };
}

/** 结算面板：从 state 取数，经 i18n 按语言渲染（数值与事实一致，宪法 §1.1）。 */
export function renderSettlementPanel(state: WorldState): string {
  const lang = state.language;
  const p = state.player;
  const rows: Array<[string, string]> = [
    [t(lang, 'panel.tier'), String(state.tier)],
    [t(lang, 'panel.turn'), String(state.turn)],
    [t(lang, 'panel.phase'), state.phase],
    [t(lang, 'panel.resources'), Object.entries(p.resources).map(([k, v]) => `${k} ${v}`).join(', ') || '-'],
    [t(lang, 'panel.focus'), `${p.focus}/${p.focusMax}`],
    [t(lang, 'panel.knowledge'), p.knowledge.join(', ') || '-'],
    [t(lang, 'panel.assets'), p.assets.map((a) => `${a.id} Lv${a.level}`).join(', ') || '-'],
    [t(lang, 'panel.absolutePower'), String(p.absolutePower)],
    [t(lang, 'panel.effectiveCapacity'), String(p.effectiveCapacity)],
    [t(lang, 'panel.relativeStanding'), p.relativeStanding.toFixed(2)],
    [t(lang, 'panel.position'), p.position],
    [t(lang, 'panel.rulesKnown'), state.rulesKnown.join('; ') || '-'],
  ];
  let md = `| ${t(lang, 'panel.name')} | ${t(lang, 'table.summary')} |\n| --- | --- |\n`;
  for (const [k, v] of rows) md += `| ${k} | ${v} |\n`;

  // cohort 排名：主角与存活 NPC 按力量降序（宪法 §5 相对位置）
  const cohort: Array<{ name: string; power: number }> = [
    { name: 'player', power: p.absolutePower },
    ...state.npcs.filter((n) => n.alive).map((n) => ({ name: n.name, power: n.power })),
  ].sort((a, b) => b.power - a.power);
  md += `\n**${t(lang, 'panel.cohort')}**\n\n`;
  cohort.forEach((c, i) => {
    md += `${i + 1}. ${c.name} — ${t(lang, 'panel.power')} ${c.power}\n`;
  });
  return md;
}

// ---- 附录（全部从 events.jsonl 提取，宪法 §1.1 可重放） ----

function eventSummary(lang: Language, ev: GameEvent, state: WorldState): string {
  const p = ev.payload as Record<string, unknown>;
  switch (ev.type) {
    case 'ActionResolved':
      return `${String(p.actionId ?? '?')}: ${p.success ? t(lang, 'fact.success') : t(lang, 'fact.failure')}, yield=${String(p.yield ?? 0)}`;
    case 'TierUp': {
      const zone = p.zone as { id?: string } | undefined;
      return `tier ${String(p.newTier ?? '?')} (${zone?.id ?? '-'})`;
    }
    case 'KnowledgeGained':
      return String(p.knowledge ?? '?');
    case 'AssetUpgraded':
      return `${String(p.assetId ?? '?')} Lv${String(p.level ?? '?')}`;
    case 'FactRevealed':
      return `${String(p.fact ?? '?')} [${String(p.cause ?? '?')}]`;
    case 'WindowOpened': {
      const w = p.window as { labelKey?: string; kind?: string } | undefined;
      return `${w?.kind ?? '?'}: ${w?.labelKey ? t(lang, w.labelKey) : '?'}`;
    }
    case 'WindowClosed':
      return `${String(p.windowId ?? '?')} [${String(p.cause ?? '?')}]`;
    case 'NpcActed': {
      const npc = state.npcs.find((n) => n.id === p.npcId);
      return `${npc?.name ?? String(p.npcId ?? '?')}: ${String(p.cause ?? '?')}`;
    }
    case 'TimeAdvanced':
      return `${t(lang, 'report.maintenancePaid')} ${String(p.maintenancePaid ?? 0)}`;
    default:
      return '-';
  }
}

const CHRONICLE_TYPES = ['ActionResolved', 'TierUp', 'KnowledgeGained', 'AssetUpgraded', 'FactRevealed', 'WindowOpened', 'WindowClosed'];

function buildAppendix(state: WorldState, events: GameEvent[]): string {
  const lang = state.language;
  let md = `# ${t(lang, 'appendix.title')}\n\n`;

  // 大事记
  md += `## ${t(lang, 'appendix.chronicle')}\n\n`;
  md += `| ${t(lang, 'table.seq')} | ${t(lang, 'table.turn')} | ${t(lang, 'table.event')} | ${t(lang, 'table.summary')} |\n| --- | --- | --- | --- |\n`;
  for (const ev of events) {
    if (!CHRONICLE_TYPES.includes(ev.type)) continue;
    md += `| ${ev.seq} | ${ev.turn} | ${ev.type} | ${eventSummary(lang, ev, state)} |\n`;
  }

  // 因果账本：每条带原因/差量的事件一行（宪法 §1.1 可归因）
  md += `\n## ${t(lang, 'appendix.ledger')}\n\n`;
  md += `| ${t(lang, 'table.seq')} | ${t(lang, 'table.turn')} | ${t(lang, 'table.cause')} | ${t(lang, 'table.effect')} |\n| --- | --- | --- | --- |\n`;
  for (const ev of events) {
    const p = ev.payload as Record<string, unknown>;
    if (ev.type === 'ActionResolved') {
      const deltas = JSON.stringify(p.resourceDeltas ?? {});
      const focus = p.focusDelta !== undefined ? ` focus${String(p.focusDelta)}` : '';
      md += `| ${ev.seq} | ${ev.turn} | ${String(p.actionId ?? '?')} | ${deltas}${focus} |\n`;
    } else if (ev.type === 'NpcActed') {
      const deltas = JSON.stringify(p.resourceDeltas ?? {});
      const att = p.attitudeDelta !== undefined ? ` attitude${String(p.attitudeDelta)}` : '';
      const pow = p.powerDelta !== undefined ? ` power+${String(p.powerDelta)}` : '';
      md += `| ${ev.seq} | ${ev.turn} | ${String(p.npcId ?? '?')}:${String(p.cause ?? '?')} | ${deltas}${att}${pow} |\n`;
    } else if (ev.type === 'TimeAdvanced') {
      md += `| ${ev.seq} | ${ev.turn} | time | paid=${String(p.maintenancePaid ?? 0)}, shortfall=${String(p.maintenanceShortfall ?? 0)} |\n`;
    } else if (ev.type === 'WindowClosed') {
      md += `| ${ev.seq} | ${ev.turn} | ${String(p.cause ?? '?')} | closed:${String(p.windowId ?? '?')} |\n`;
    } else if (ev.type === 'TierUp') {
      md += `| ${ev.seq} | ${ev.turn} | tier | cohortScale=${String(p.cohortScale ?? '?')} |\n`;
    }
  }
  return md;
}

/** 拼接全书 + 引擎附录，输出 worlds/<slug>/exports/<世界名>-全书.md。 */
export function exportNovel(slug: string, root?: string): { ok: true; path: string } | { ok: false; error: EngineError } {
  let state: WorldState;
  try {
    state = loadWorld(slug, root);
  } catch (e) {
    return { ok: false, error: { code: 'E_WORLD_NOT_FOUND', reason: (e as Error).message, hints: [] } };
  }
  const meta = readJsonFile<NovelMeta>(slug, META_NAME, root);
  if (!meta) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: 'novel meta missing', hints: ['accept'] } };
  }
  const novelMd = readTextFile(novelFilePath(slug, meta, root)) ?? '';
  const events = readEvents(slug, root);
  const full = `${novelMd.trimEnd()}\n\n---\n\n${buildAppendix(state, events)}\n`;
  // 导出后缀按语言本地化；文件名经 safeFileName 兜底（防路径穿越）
  const path = join(subDir(slug, 'exports', root), `${safeFileName(meta.worldName)}${t(meta.language, 'export.suffix')}`);
  writeTextFile(path, full);
  return { ok: true, path };
}

/** NPC 结局判定（宪法 §9：由双方状态证明，不用措辞洗白）。 */
function npcFate(lang: Language, n: { alive: boolean; attitude: number }): string {
  if (!n.alive) return t(lang, 'fate.dead');
  if (n.attitude >= 2) return t(lang, 'fate.ally');
  if (n.attitude <= -2) return t(lang, 'fate.rival');
  return t(lang, 'fate.neutral');
}

function renderEpilogue(state: WorldState, events: GameEvent[]): string {
  const lang = state.language;
  let md = `## ${t(lang, 'appendix.epilogue')}\n\n`;

  md += `### ${t(lang, 'epilogue.finalState')}\n\n${renderSettlementPanel(state)}\n`;

  // 跃迁轨迹
  md += `\n### ${t(lang, 'epilogue.tierPath')}\n\n`;
  const tierUps = events.filter((e) => e.type === 'TierUp');
  if (tierUps.length === 0) {
    md += `- tier 0 (${t(lang, 'panel.turn')} ${state.turn})\n`;
  } else {
    md += `- tier 0\n`;
    for (const ev of tierUps) {
      const p = ev.payload as { newTier?: number; zone?: { id?: string } };
      md += `- tier ${String(p.newTier ?? '?')} @ ${t(lang, 'table.turn')} ${ev.turn} (${p.zone?.id ?? '-'})\n`;
    }
  }

  // 人物结局表
  md += `\n### ${t(lang, 'epilogue.npcFates')}\n\n`;
  md += `| ${t(lang, 'table.npc')} | ${t(lang, 'panel.goal')} | ${t(lang, 'panel.power')} | ${t(lang, 'panel.attitude')} | ${t(lang, 'table.fate')} |\n| --- | --- | --- | --- | --- |\n`;
  for (const n of state.npcs) {
    md += `| ${n.name} | ${n.goal} | ${n.power} | ${n.attitude} | ${npcFate(lang, n)} |\n`;
  }
  return md;
}

/** 完结世界：发射 WorldFinished 事件走统一管道（phase→ended 由 reducer 施加，verify 可重放），
 * 引擎生成尾声追加进小说，随后导出全书。存在未归档章节事实时返回 warning（不静默）。 */
export function finishWorld(slug: string, root?: string): { ok: true; data: { exportPath: string; turn: number; tier: number; warning?: string; unarchivedFactsSeq?: number } } | { ok: false; error: EngineError } {
  let state: WorldState;
  try {
    state = loadWorld(slug, root);
  } catch (e) {
    return { ok: false, error: { code: 'E_WORLD_NOT_FOUND', reason: (e as Error).message, hints: [] } };
  }
  if (state.phase === 'ended') {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: 'world already ended', hints: [] } };
  }
  const meta = readJsonFile<NovelMeta>(slug, META_NAME, root);
  if (!meta) {
    return { ok: false, error: { code: 'E_ILLEGAL_ACTION', reason: 'novel meta missing', hints: ['accept'] } };
  }

  // 未归档章节事实提示（最新 factsSeq 尚未绑定章节 → 提醒主持人补交，不静默）
  const unarchived = meta.archived.includes(state.lastFactsSeq) ? undefined : state.lastFactsSeq;

  // phase→ended 经事件管道落盘（删除叙事不能删除因果，宪法 §1.1）
  const ev: GameEvent = { seq: state.lastFactsSeq + 1, turn: state.turn, type: 'WorldFinished', payload: { turn: state.turn } as unknown };
  appendEvent(slug, ev, root);
  state = applyAll(state, [ev]);
  saveWorld(state, root);

  const events = readEvents(slug, root);
  const epilogue = renderEpilogue(state, events);
  appendTextFile(novelFilePath(slug, meta, root), `\n\n---\n\n${epilogue}\n`);

  const ex = exportNovel(slug, root);
  if (!ex.ok) return ex;
  return {
    ok: true,
    data: {
      exportPath: ex.path,
      turn: state.turn,
      tier: state.tier,
      ...(unarchived !== undefined ? { warning: 'unarchivedFacts', unarchivedFactsSeq: unarchived } : {}),
    },
  };
}
