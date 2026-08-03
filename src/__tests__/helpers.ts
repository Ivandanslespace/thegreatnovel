/** 测试公共助手：加载演示 Blueprint、创建临时存档目录。 */
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import type { Blueprint, GameState } from '../types.ts';
import { initState } from '../save.ts';
import { resolveAction } from '../resolve.ts';

export const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
export const echoBlueprintPath = path.join(repoRoot, 'worlds', 'echo-harbor.blueprint.json');
export const cliScript = path.join(repoRoot, 'src', 'cli.ts');

export function loadEchoBlueprint(): Blueprint {
  return JSON.parse(readFileSync(echoBlueprintPath, 'utf8')) as Blueprint;
}

/** 临时存档根目录（禁止污染仓库根目录）。 */
export function tmpBase(): string {
  return mkdtempSync(path.join(tmpdir(), 'tgn-test-'));
}

/** 以固定种子初始化一局回声潮港。 */
export function freshState(seed = 44): { bp: Blueprint; state: GameState } {
  const bp = loadEchoBlueprint();
  return { bp, state: initState(bp, 'test-world', seed) };
}

/** 依次结算一串行动。非法行动直接抛出。 */
export function play(bp: Blueprint, state: GameState, actions: string[]): void {
  for (const id of actions) resolveAction(bp, state, id);
}
