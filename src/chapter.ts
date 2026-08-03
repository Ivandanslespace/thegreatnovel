/**
 * 章节保存：chapters/NNN-<slug>.md，frontmatter 记录章节号与 turn 区间。
 *
 * frontmatter 的 turn 区间与 state.history 对账，是"叙事只表达已成立事实"
 * （宪章 §1）的机器证据。
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import type { ChapterRecord, GameState } from './types.ts';
import { saveDirFor, slugify } from './save.ts';

export interface AddChapterResult {
  record: ChapterRecord;
  file: string;
}

/** 构建章节 frontmatter（chapter.ts/novel.ts 共享，minor）。 */
export function buildFrontmatter(fields: Record<string, string | number>): string {
  const lines = ['---'];
  for (const [key, value] of Object.entries(fields)) {
    lines.push(typeof value === 'string' ? `${key}: ${JSON.stringify(value)}` : `${key}: ${value}`);
  }
  lines.push('---', '');
  return lines.join('\n');
}

/** 去掉入库时的 frontmatter，只留正文（chapter.ts/novel.ts 共享，minor）。 */
export function stripFrontmatter(content: string): string {
  return content.replace(/^---\n[\s\S]*?\n---\n/, '');
}

/** 把 Agent 写好的章节文本入库（内容文件可放 temps/，入库后源文件自便）。 */
export async function addChapter(
  base: string,
  state: GameState,
  title: string,
  contentFile: string,
): Promise<AddChapterResult> {
  if (!title.trim()) throw new Error('章节标题不能为空');
  const content = await readFile(contentFile, 'utf8').catch((err: Error) => {
    throw new Error(`无法读取章节内容文件：${err.message}`);
  });
  if (!content.trim()) throw new Error('章节内容不能为空');

  const dir = path.join(saveDirFor(base, state.world), 'chapters');
  await mkdir(dir, { recursive: true });

  const index = state.chapterCursor;
  const slug = slugify(title);
  const fileName = `${String(index).padStart(3, '0')}-${slug}.md`;
  const startTurn = state.lastChapterTurn;
  const endTurn = state.turn;

  const frontmatter = buildFrontmatter({
    chapter: index,
    title,
    world: state.world,
    turnStart: startTurn,
    turnEnd: endTurn,
  });

  const file = path.join(dir, fileName);
  await writeFile(file, frontmatter + content.trim() + '\n', 'utf8');

  const record: ChapterRecord = { index, title, slug, file: fileName, startTurn, endTurn };
  state.chapters.push(record);
  state.chapterCursor += 1;
  state.lastChapterTurn = state.turn;
  return { record, file };
}
