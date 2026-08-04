// 世界目录 = worlds/<slug>/；原子写：写 state.json.tmp 同目录 → renameSync（Windows 原子替换）。
// 所有持久化 IO 仅此一处（项目硬约束），避免破坏存档。
// 测试允许自定义 root 目录，默认 'worlds'。

import { readFileSync, writeFileSync, appendFileSync, renameSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import type { GameEvent, WorldState } from './types.ts';
import { SCHEMA_VERSION } from './types.ts';

const DEFAULT_ROOT = 'worlds';

/** 构造带 code 的结构化异常（CLI 层按 code 映射信封，避免裸崩成 E_INTERNAL）。 */
function codedError(code: string, message: string): Error & { code?: string } {
  const err = new Error(`${code}: ${message}`) as Error & { code?: string };
  err.code = code;
  return err;
}

export function worldDir(slug: string, root: string = DEFAULT_ROOT): string {
  return join(root, slug);
}

function statePath(slug: string, root: string): string {
  return join(worldDir(slug, root), 'state.json');
}

function eventsPath(slug: string, root: string): string {
  return join(worldDir(slug, root), 'events.jsonl');
}

/** 从文件系统加载状态；不存在抛 E_WORLD_NOT_FOUND，损坏抛 E_SAVE_CORRUPTED，schemaVersion 不符抛明确错误。 */
export function loadWorld(slug: string, root: string = DEFAULT_ROOT): WorldState {
  const p = statePath(slug, root);
  if (!existsSync(p)) {
    throw codedError('E_WORLD_NOT_FOUND', slug);
  }
  let state: WorldState;
  try {
    state = JSON.parse(readFileSync(p, 'utf8')) as WorldState;
  } catch (e) {
    throw codedError('E_SAVE_CORRUPTED', `state.json invalid JSON: ${(e as Error).message}`);
  }
  if (state.schemaVersion !== undefined && state.schemaVersion !== SCHEMA_VERSION) {
    throw codedError('E_SAVE_CORRUPTED', `state.json schemaVersion ${String(state.schemaVersion)} != engine ${SCHEMA_VERSION}`);
  }
  return state;
}

/** 原子写入：在 temp 文件写入后 rename（Windows 覆盖原子性，宪法 §12）。 */
export function saveWorld(state: WorldState, root: string = DEFAULT_ROOT): void {
  const dir = worldDir(state.worldSlug, root);
  mkdirSync(dir, { recursive: true });
  const target = statePath(state.worldSlug, root);
  const tmp = join(dir, 'state.json.tmp');
  writeFileSync(tmp, JSON.stringify(state, null, 2));
  renameSync(tmp, target);
}

/** 追加事件到 .jsonl（单行 JSON，重放可线性还原）。 */
export function appendEvent(slug: string, event: GameEvent, root: string = DEFAULT_ROOT): void {
  const dir = worldDir(slug, root);
  mkdirSync(dir, { recursive: true });
  appendFileSync(eventsPath(slug, root), JSON.stringify(event) + '\n');
}

/** 读取全部事件（不含初始状态，由 Init 事件携带）。损坏行抛 E_SAVE_CORRUPTED 并附行号。 */
export function readEvents(slug: string, root: string = DEFAULT_ROOT): GameEvent[] {
  const p = eventsPath(slug, root);
  if (!existsSync(p)) return [];
  const lines = readFileSync(p, 'utf8').split('\n').filter((l) => l.trim() !== '');
  const events: GameEvent[] = [];
  for (let i = 0; i < lines.length; i++) {
    try {
      events.push(JSON.parse(lines[i]) as GameEvent);
    } catch (e) {
      throw codedError('E_SAVE_CORRUPTED', `events.jsonl line ${i + 1} invalid JSON: ${(e as Error).message}`);
    }
  }
  return events;
}

// ---- T2：世界目录下的附属 JSON（world.json / blueprint.json / commitments.json / novel/meta.json）----
// 仍然遵循 tmp+rename 原子写；所有持久化 IO 集中在本文件。

/** 写入世界目录下的附属 JSON 文件（原子写）。 */
export function writeJsonFile(slug: string, name: string, data: unknown, root: string = DEFAULT_ROOT): void {
  const dir = worldDir(slug, root);
  mkdirSync(dir, { recursive: true });
  const target = join(dir, name);
  const tmp = join(dir, `${name}.tmp`);
  writeFileSync(tmp, JSON.stringify(data, null, 2));
  renameSync(tmp, target);
}

/** 读取世界目录下的附属 JSON 文件；不存在返回 null；损坏抛 E_SAVE_CORRUPTED。 */
export function readJsonFile<T>(slug: string, name: string, root: string = DEFAULT_ROOT): T | null {
  const p = join(worldDir(slug, root), name);
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, 'utf8')) as T;
  } catch (e) {
    throw codedError('E_SAVE_CORRUPTED', `${name} invalid JSON: ${(e as Error).message}`);
  }
}

/** 读取任意文本文件；不存在返回 null（小说/章节文件用）。 */
export function readTextFile(absPath: string): string | null {
  try {
    if (!existsSync(absPath)) return null;
    return readFileSync(absPath, 'utf8');
  } catch {
    return null; // 读取失败（目录/权限等）按不存在处理，CLI 层返回信封错误
  }
}

/** 写入任意文本文件（自动创建父目录）。 */
export function writeTextFile(absPath: string, content: string): void {
  mkdirSync(dirname(absPath), { recursive: true });
  writeFileSync(absPath, content);
}

/** 追加任意文本文件（自动创建父目录）。 */
export function appendTextFile(absPath: string, content: string): void {
  mkdirSync(dirname(absPath), { recursive: true });
  appendFileSync(absPath, content);
}

/** 世界目录下的子目录绝对/相对路径（novel/、exports/ 等）。 */
export function subDir(slug: string, name: string, root: string = DEFAULT_ROOT): string {
  return join(worldDir(slug, root), name);
}
