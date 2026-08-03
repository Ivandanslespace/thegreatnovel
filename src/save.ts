/**
 * 存档 IO：原子写（.tmp+rename）、state.prev.json 备份、SHA-256 校验、schemaVersion 迁移。
 *
 * saves/<世界名>/ = blueprint.json（开局冻结）+ state.json + state.json.sha256
 *                 + state.prev.json + chapters/ + history.jsonl + manifest.json (+ novel.md)
 *
 * schema v2（M8）：history.jsonl 是唯一审计源（真 append），state.json 不再内嵌
 * history 数组，只保留 historyCount/historyLastTurn 游标用于完整性对账。
 * 旧档经 migrations 链式前向迁移后加载（C2），不匹配/损坏存档在 list 中报告而非隐藏。
 */
import { appendFile, mkdir, readFile, rename, writeFile, readdir, stat } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import path from 'node:path';
import { SCHEMA_VERSION } from './types.ts';
import type { Blueprint, GameState, HistoryEntry, Language } from './types.ts';
import { DEFAULT_LANGUAGE, isLanguage } from './i18n.ts';

export function savesRoot(base: string): string {
  return path.join(base, 'saves');
}

export function saveDirFor(base: string, world: string): string {
  return path.join(savesRoot(base), world);
}

export function sha256(content: string): string {
  return createHash('sha256').update(content, 'utf8').digest('hex');
}

/** slug（章节文件名用）。先 NFKD 分解并去音标（法语 La Marée d'Écho →
 * la-maree-decho），再仅保留 ASCII 拉丁字符与数字——非拉丁标题如中文/
 * 阿拉伯文经 slugify 后为空，回退为调用方给的数字编号，保持 ASCII 文件名（V1.1）。 */
export function slugify(input: string, fallback = 'untitled'): string {
  const ascii = input
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // 去掉组合音标（é → e）
    .replace(/['’‘]/g, '') // 撇号直接省略而非当分隔符（d'Écho → decho）
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return ascii.length > 0 ? ascii : fallback;
}

/** 原子写：临时文件名带 pid + 随机后缀，避免并发/残留冲突（minor）。 */
async function atomicWrite(file: string, content: string): Promise<void> {
  const tmp = `${file}.${process.pid}.${randomUUID().slice(0, 8)}.tmp`;
  await writeFile(tmp, content, 'utf8');
  await rename(tmp, file);
}

// ---------------------------------------------------------------------------
// 迁移（C2）：链式前向迁移到当前版本后再校验
// ---------------------------------------------------------------------------

export type MigrationFn = (state: unknown) => unknown;

/** v1 → v2：state.history 数组移除（history.jsonl 在 v1 已双轨写入，无需重放）。 */
function migrateV1toV2(raw: unknown): unknown {
  const s = raw as Record<string, unknown>;
  const embedded = Array.isArray(s.history) ? (s.history as HistoryEntry[]) : [];
  const next: Record<string, unknown> = { ...s };
  delete next.history;
  next.schemaVersion = 2;
  next.historyCount = embedded.length;
  next.historyLastTurn = embedded.length > 0 ? embedded[embedded.length - 1]!.turn : 0;
  return next;
}

/** 迁移表：键为源版本，值为 (v → v+1) 迁移函数。 */
export const migrations: Record<number, MigrationFn> = {
  1: migrateV1toV2,
};

/** 把任意版本的存档对象链式前向迁移到当前版本；未来版本抛错。 */
export function applyMigrations(raw: unknown): { state: GameState; migrated: boolean } {
  const record = raw as Record<string, unknown>;
  const version = typeof record.schemaVersion === 'number' ? record.schemaVersion : 0;
  if (version > SCHEMA_VERSION) {
    throw new Error(`存档版本过新（schemaVersion=${version}），当前引擎 ${SCHEMA_VERSION}，无法降级`);
  }
  let current: unknown = raw;
  let migrated = false;
  for (let v = version; v < SCHEMA_VERSION; v++) {
    const fn = migrations[v];
    if (!fn) throw new Error(`缺少 schemaVersion ${v} → ${v + 1} 的迁移函数`);
    current = fn(current);
    migrated = true;
  }
  return { state: current as GameState, migrated };
}

// ---------------------------------------------------------------------------
// 状态读写
// ---------------------------------------------------------------------------

/** 开局初始状态（schema v2：history 不在 state 内，开局条目由 CLI 写 jsonl）。
 * language 缺省取 blueprint.meta.language，再无则默认 zh（V1.1，表现层元数据）。 */
export function initState(blueprint: Blueprint, world: string, seed?: number, language?: Language): GameState {
  const assets: Record<string, number> = {};
  for (const type of blueprint.assetTypes) {
    assets[type.id] = type.initial ?? 0;
  }
  const knownFacts = blueprint.facts.filter((f) => f.scope === 'player').map((f) => f.id);
  const unlockedRegions = blueprint.regions.filter((r) => r.initiallyUnlocked).map((r) => r.id);
  return {
    schemaVersion: SCHEMA_VERSION,
    world,
    seed: seed ?? blueprint.meta.seed,
    language: language ?? (isLanguage(blueprint.meta.language) ? blueprint.meta.language : DEFAULT_LANGUAGE),
    turn: 0,
    tier: 0,
    assets,
    knownFacts,
    flags: {},
    unlockedRegions,
    plansFired: [],
    eventsFired: [],
    counters: {},
    leverageUses: 0,
    historyCount: 0,
    historyLastTurn: 0,
    chapters: [],
    chapterCursor: 1,
    lastChapterTurn: 0,
  };
}

/** 保存状态：备份旧档 → 原子写 state.json → 写校验和。 */
export async function saveState(base: string, state: GameState): Promise<void> {
  const dir = saveDirFor(base, state.world);
  await mkdir(dir, { recursive: true });
  const stateFile = path.join(dir, 'state.json');
  try {
    const prev = await readFile(stateFile, 'utf8');
    await atomicWrite(path.join(dir, 'state.prev.json'), prev);
  } catch {
    // 首次保存无旧档，正常。
  }
  const content = JSON.stringify(state, null, 2);
  await atomicWrite(stateFile, content);
  await atomicWrite(`${stateFile}.sha256`, sha256(content));
}

/**
 * 读取状态：旧版本经迁移链前向迁移到当前版本（C2），迁移结果回写落盘；
 * 未来版本抛错。不做完整性校验（校验用 verifySave）。
 */
export async function loadState(base: string, world: string): Promise<GameState> {
  const file = path.join(saveDirFor(base, world), 'state.json');
  const raw = await readFile(file, 'utf8');
  const parsed = JSON.parse(raw) as unknown;
  const { state, migrated } = applyMigrations(parsed);
  if (migrated) {
    await saveState(base, state); // 迁移结果落盘，后续读取不再重复迁移
  }
  return state;
}

/** 读取随档冻结的 Blueprint（重跑校验，防止随档文件被篡改/损坏，minor）。 */
export async function loadFrozenBlueprint(base: string, world: string): Promise<Blueprint> {
  const file = path.join(saveDirFor(base, world), 'blueprint.json');
  const raw = await readFile(file, 'utf8');
  const parsed = JSON.parse(raw) as Blueprint;
  // 延迟导入避免模块环；校验失败说明随档 Blueprint 被改动，回放不自足。
  const { validateBlueprint } = await import('./blueprint.ts');
  const validation = validateBlueprint(parsed);
  if (!validation.ok) {
    throw new Error(
      `随档 blueprint.json 未通过校验：${validation.issues.map((i) => `[${i.code}] ${i.path}`).join('; ')}`,
    );
  }
  return parsed;
}

// ---------------------------------------------------------------------------
// history.jsonl（唯一审计源，真 append，M8）
// ---------------------------------------------------------------------------

/** 追加 history 条目（append-only 审计日志）。 */
export async function appendHistory(base: string, world: string, entries: HistoryEntry[]): Promise<void> {
  if (entries.length === 0) return;
  const dir = saveDirFor(base, world);
  await mkdir(dir, { recursive: true });
  const file = path.join(dir, 'history.jsonl');
  const lines = entries.map((e) => JSON.stringify(e)).join('\n') + '\n';
  await appendFile(file, lines, 'utf8');
}

/** 读取 history.jsonl 全部条目（回放/小说合成用）。 */
export async function readHistory(base: string, world: string): Promise<HistoryEntry[]> {
  const file = path.join(saveDirFor(base, world), 'history.jsonl');
  const raw = await readFile(file, 'utf8').catch(() => '');
  const entries: HistoryEntry[] = [];
  for (const line of raw.split('\n')) {
    if (!line.trim()) continue;
    entries.push(JSON.parse(line) as HistoryEntry);
  }
  return entries;
}

// ---------------------------------------------------------------------------
// verify
// ---------------------------------------------------------------------------

export interface VerifyResult {
  ok: boolean;
  problems: string[];
  world: string;
}

/** verify：校验和、schemaVersion（区分过旧/过新/篡改）、引用一致性、章节与历史对账。 */
export async function verifySave(base: string, world: string): Promise<VerifyResult> {
  const problems: string[] = [];
  const dir = saveDirFor(base, world);
  try {
    const content = await readFile(path.join(dir, 'state.json'), 'utf8');
    const expected = sha256(content);
    let recorded: string | null = null;
    try {
      recorded = (await readFile(path.join(dir, 'state.json.sha256'), 'utf8')).trim();
    } catch {
      problems.push('缺少校验和文件 state.json.sha256');
    }
    // M4：空校验和文件视同缺失，不得静默通过。
    if (recorded !== null && recorded.length === 0) {
      problems.push('校验和文件 state.json.sha256 为空，视同缺失');
      recorded = null;
    }
    if (recorded !== null && recorded !== expected) {
      problems.push(`state.json 已被篡改（SHA-256 不匹配：期望 ${expected.slice(0, 12)}…，实际 ${recorded.slice(0, 12)}…）`);
    }
    const state = JSON.parse(content) as GameState;
    // C2：版本问题与篡改分开表述。
    if (typeof state.schemaVersion !== 'number' || state.schemaVersion < SCHEMA_VERSION) {
      const v = state.schemaVersion ?? '缺失';
      problems.push(`版本过旧需迁移（存档 ${v}，引擎 ${SCHEMA_VERSION}）：执行任一世界命令将自动前向迁移`);
    } else if (state.schemaVersion > SCHEMA_VERSION) {
      problems.push(`版本过新（存档 ${state.schemaVersion}，引擎 ${SCHEMA_VERSION}），无法校验`);
    }
    if (state.world !== world) {
      problems.push(`存档 world 字段(${state.world})与目录名(${world})不一致`);
    }
    const bp = await loadFrozenBlueprint(base, world).catch(() => null);
    if (!bp) problems.push('缺少随档冻结的 blueprint.json，回放不自足');
    else {
      for (const id of state.knownFacts ?? []) {
        if (!bp.facts.some((f) => f.id === id)) problems.push(`已知事实 ${id} 不在 Blueprint 事实集中`);
      }
      for (const id of state.unlockedRegions ?? []) {
        if (!bp.regions.some((r) => r.id === id)) problems.push(`已解锁区域 ${id} 不在 Blueprint 区域集中`);
      }
    }
    // history.jsonl 与 state 游标对账（M8）
    if (typeof state.historyCount === 'number' && state.schemaVersion === SCHEMA_VERSION) {
      const entries = await readHistory(base, world);
      if (entries.length !== state.historyCount) {
        problems.push(`history.jsonl 条目数(${entries.length})与 state.historyCount(${state.historyCount})不一致`);
      }
    }
    // 章节文件对账（AGENTS.md 硬规则的机器证据）
    for (const ch of state.chapters ?? []) {
      const chapterFile = path.join(dir, 'chapters', ch.file);
      try {
        await readFile(chapterFile, 'utf8');
      } catch {
        problems.push(`章节文件缺失：chapters/${ch.file}`);
      }
    }
  } catch (err) {
    problems.push(`无法读取 state.json：${(err as Error).message}`);
  }
  return { ok: problems.length === 0, problems, world };
}

// ---------------------------------------------------------------------------
// Blueprint 冻结 / manifest / list
// ---------------------------------------------------------------------------

/** 开局时把 Blueprint 拷贝入档（世界规则随档冻结，回放自足）。expand 物化后也经此写回。 */
export async function freezeBlueprint(base: string, world: string, blueprint: Blueprint): Promise<void> {
  const dir = saveDirFor(base, world);
  await mkdir(dir, { recursive: true });
  await atomicWrite(path.join(dir, 'blueprint.json'), JSON.stringify(blueprint, null, 2));
}

/** 写 manifest.json。 */
export async function writeManifest(
  base: string,
  world: string,
  extra: Record<string, unknown>,
): Promise<void> {
  const dir = saveDirFor(base, world);
  await mkdir(dir, { recursive: true });
  const file = path.join(dir, 'manifest.json');
  let manifest: Record<string, unknown> = {};
  try {
    manifest = JSON.parse(await readFile(file, 'utf8')) as Record<string, unknown>;
  } catch {
    // 首次写入
  }
  manifest = { ...manifest, world, updatedAt: new Date().toISOString(), ...extra };
  await atomicWrite(file, JSON.stringify(manifest, null, 2));
}

export type SaveStatus = 'ok' | 'needs-migration' | 'future-version' | 'corrupt';

export interface SaveSummary {
  world: string;
  turn: number;
  tier: number;
  ended: boolean;
  /** 表现层语言；旧存档无此字段时按 zh 报告（V1.1 向后兼容）。 */
  language: Language;
  /** C2：不匹配/损坏存档报告状态而非隐藏。 */
  status: SaveStatus;
  note?: string;
}

/** 列出所有存档：只读 state.json 原始内容，不触发迁移；异常存档带状态报告。 */
export async function listSaves(base: string): Promise<SaveSummary[]> {
  const root = savesRoot(base);
  let entries: string[];
  try {
    entries = await readdir(root);
  } catch {
    return [];
  }
  const result: SaveSummary[] = [];
  for (const name of entries) {
    const s = await stat(path.join(root, name)).catch(() => null);
    if (!s || !s.isDirectory()) continue;
    let state: Record<string, unknown>;
    try {
      state = JSON.parse(await readFile(path.join(root, name, 'state.json'), 'utf8')) as Record<string, unknown>;
    } catch {
      result.push({ world: name, turn: 0, tier: 0, ended: false, language: DEFAULT_LANGUAGE, status: 'corrupt', note: 'state.json 缺失或无法解析' });
      continue;
    }
    const version = typeof state.schemaVersion === 'number' ? state.schemaVersion : 0;
    const baseSummary = {
      world: name,
      turn: typeof state.turn === 'number' ? state.turn : 0,
      tier: typeof state.tier === 'number' ? state.tier : 0,
      ended: state.ended !== undefined,
      language: isLanguage(state.language) ? state.language : DEFAULT_LANGUAGE,
    };
    if (version > SCHEMA_VERSION) {
      result.push({ ...baseSummary, status: 'future-version', note: `schemaVersion=${version} 高于引擎 ${SCHEMA_VERSION}` });
    } else if (version < SCHEMA_VERSION) {
      result.push({ ...baseSummary, status: 'needs-migration', note: `schemaVersion=${version}，将在下次加载时前向迁移` });
    } else {
      result.push({ ...baseSummary, status: 'ok' });
    }
  }
  return result;
}
